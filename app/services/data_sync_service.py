"""Tushare 数据同步服务。

负责从 Tushare Pro 拉取股票基础信息、K 线行情、日线因子、财务指标等数据，
写入 PostgreSQL/TimescaleDB。
"""

import sys
import time
from datetime import date, datetime, timedelta

import pandas as pd
import tushare as ts
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.stock import (
    IndexBasic,
    IndexDaily,
    MoneyflowHsgt,
    SectorMoneyflowConcept,
    SectorMoneyflowIndustry,
    StockBasic,
    StockDaily,
    StockDailyBasic,
    StockFinaIndicator,
    StockLimit,
    StockMoneyflow,
    StockMonthly,
    StockWeekly,
    StockYearly,
    ThsDaily,
    ThsIndex,
    ThsMember,
    TopInst,
    TopList,
)


def _log(message: str):
    print(message, flush=True)

# 初始化 Tushare Pro
_pro = None


def get_pro():
    global _pro
    if _pro is None:
        if not settings.tushare_token:
            raise RuntimeError("TUSHARE_TOKEN 未配置，请在 .env 中设置")
        ts.set_token(settings.tushare_token)
        _pro = ts.pro_api()
    return _pro


def _normalize_code(code: str) -> str:
    """把用户输入的代码标准化成 Tushare 格式。"""
    code = code.strip().upper()
    if "." in code:
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith("0") or code.startswith("3"):
        return f"{code}.SZ"
    if code.startswith("8") or code.startswith("4"):
        return f"{code}.BJ"
    if code.isdigit() and len(code) >= 5:
        return f"{code}.HK"
    return code


def _parse_date(value) -> date | None:
    """把 YYYYMMDD 字符串或 datetime 转成 date。"""
    if value is None or value == "" or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.replace("-", "").strip()
        if value == "" or value.lower() == "nan":
            return None
        try:
            return datetime.strptime(value, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _to_numeric(value, precision: int = 4):
    """把 pandas 标量转成 Decimal，空值返回 None。"""
    if value is None:
        return None

    if pd.isna(value):
        return None
    try:
        from decimal import Decimal, InvalidOperation

        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _tushare_sleep(seconds: float = 0.3):
    """Tushare 免费用户有调用频率限制，适当休眠。"""
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# 股票基础信息
# ---------------------------------------------------------------------------


def sync_stock_basic(db: Session | None = None) -> int:
    """同步股票基础信息。"""
    pro = get_pro()
    df = pro.stock_basic(exchange="", list_status="L")
    _tushare_sleep()

    if df is None or df.empty:
        return 0

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        count = 0
        for _, row in df.iterrows():
            values = {
                "ts_code": str(row.get("ts_code", "")),
                "symbol": str(row.get("symbol", "")) if row.get("symbol") is not None else None,
                "name": str(row.get("name", "")) if row.get("name") is not None else None,
                "area": str(row.get("area", "")) if row.get("area") is not None else None,
                "industry": str(row.get("industry", "")) if row.get("industry") is not None else None,
                "fullname": str(row.get("fullname", "")) if row.get("fullname") is not None else None,
                "enname": str(row.get("enname", "")) if row.get("enname") is not None else None,
                "cnspell": str(row.get("cnspell", "")) if row.get("cnspell") is not None else None,
                "market": str(row.get("market", "")) if row.get("market") is not None else None,
                "exchange": str(row.get("exchange", "")) if row.get("exchange") is not None else None,
                "curr_type": str(row.get("curr_type", "")) if row.get("curr_type") is not None else None,
                "list_status": str(row.get("list_status", "")) if row.get("list_status") is not None else None,
                "list_date": _parse_date(row.get("list_date")),
                "delist_date": _parse_date(row.get("delist_date")),
                "is_hs": str(row.get("is_hs", "")) if row.get("is_hs") is not None else None,
            }

            stmt = (
                insert(StockBasic)
                .values(values)
                .on_conflict_do_update(
                    index_elements=["ts_code"],
                    set_={k: v for k, v in values.items() if k != "ts_code"},
                )
            )
            db.execute(stmt)
            count += 1

        db.commit()
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 交易日历
# ---------------------------------------------------------------------------


def _get_trade_dates(pro, start_date: date, end_date: date, exchange: str = "SSE") -> list[str]:
    """获取指定日期范围内的交易日列表（YYYYMMDD）。"""
    df = pro.trade_cal(
        exchange=exchange,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        is_open="1",
    )
    _tushare_sleep()
    if df is None or df.empty:
        return []
    return sorted(df["cal_date"].astype(str).tolist())


# ---------------------------------------------------------------------------
# K 线行情
# ---------------------------------------------------------------------------

_KLINE_MODELS = {
    "D": StockDaily,
    "W": StockWeekly,
    "M": StockMonthly,
    "Y": StockYearly,
}

_KLINE_TUSHARE_APIS = {
    "D": "daily",
    "W": "weekly",
    "M": "monthly",
}


def _build_kline_values(row, ts_code_default: str, period: str) -> dict | None:
    """从 tushare 行数据构建 K 线字段字典。"""
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "ts_code": str(row.get("ts_code", ts_code_default)),
        "trade_date": trade_date,
        "open": _to_numeric(row.get("open")),
        "high": _to_numeric(row.get("high")),
        "low": _to_numeric(row.get("low")),
        "close": _to_numeric(row.get("close")),
        "pre_close": _to_numeric(row.get("pre_close")),
        "change": _to_numeric(row.get("change")),
        "pct_chg": _to_numeric(row.get("pct_chg")),
        "vol": _to_numeric(row.get("vol")),
        "amount": _to_numeric(row.get("amount")),
    }


def _upsert_klines(db: Session, model, rows: list[dict]) -> int:
    """批量写入 K 线数据，使用 PostgreSQL ON CONFLICT DO UPDATE。"""
    if not rows:
        return 0

    stmt = insert(model).values(rows)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in model.__table__.columns
        if c.name not in ("ts_code", "trade_date")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_code", "trade_date"],
        set_=update_dict,
    )
    db.execute(stmt)
    return len(rows)


def _upsert_daily_basic(db: Session, rows: list[dict]) -> int:
    """批量写入日线因子数据。"""
    if not rows:
        return 0

    stmt = insert(StockDailyBasic).values(rows)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in StockDailyBasic.__table__.columns
        if c.name not in ("ts_code", "trade_date")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_code", "trade_date"],
        set_=update_dict,
    )
    db.execute(stmt)
    return len(rows)


def _aggregate_yearly_from_monthly(monthly_rows: list[StockMonthly]) -> list[StockYearly]:
    """从月 K 聚合生成年 K。"""
    from collections import defaultdict

    groups: dict[int, list[StockMonthly]] = defaultdict(list)
    for m in monthly_rows:
        if m.trade_date is None:
            continue
        groups[m.trade_date.year].append(m)

    results = []
    for year in sorted(groups.keys()):
        group = sorted(groups[year], key=lambda x: x.trade_date)
        results.append(
            StockYearly(
                ts_code=group[0].ts_code,
                trade_date=date(year, 12, 31),
                open=group[0].open,
                high=max((m.high for m in group), default=group[0].high),
                low=min((m.low for m in group), default=group[0].low),
                close=group[-1].close,
                vol=sum((m.vol or 0) for m in group),
                amount=sum((m.amount or 0) for m in group),
            )
        )
    return results


def _sync_yearly_from_monthly(
    db: Session,
    ts_code: str,
    start_date: date,
    end_date: date,
) -> int:
    """从月 K 聚合同步单只股票年 K。"""
    monthly_rows = (
        db.execute(
            select(StockMonthly)
            .where(
                StockMonthly.ts_code == ts_code,
                StockMonthly.trade_date >= start_date,
                StockMonthly.trade_date <= end_date,
            )
            .order_by(StockMonthly.trade_date)
        )
        .scalars()
        .all()
    )

    if not monthly_rows:
        return 0

    yearly_rows = _aggregate_yearly_from_monthly(monthly_rows)
    values_list = [
        {
            "ts_code": r.ts_code,
            "trade_date": r.trade_date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "vol": r.vol,
            "amount": r.amount,
        }
        for r in yearly_rows
    ]

    if not values_list:
        return 0

    stmt = insert(StockYearly).values(values_list)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in StockYearly.__table__.columns
        if c.name not in ("ts_code", "trade_date")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_code", "trade_date"],
        set_=update_dict,
    )
    db.execute(stmt)
    return len(values_list)


def _sync_klines_for_code(
    db: Session,
    ts_code: str,
    period: str,
    start_date: date,
    end_date: date,
) -> int:
    """同步单只股票指定周期的 K 线数据（用于年线或指定单只股票）。"""
    pro = get_pro()
    period = period.upper()
    model = _KLINE_MODELS[period]
    api_name = _KLINE_TUSHARE_APIS.get(period, "daily")

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    df = pro.query(
        api_name,
        ts_code=ts_code,
        start_date=start_str,
        end_date=end_str,
    )
    _tushare_sleep()

    if df is None or df.empty:
        return 0

    rows = []
    for _, row in df.iterrows():
        values = _build_kline_values(row, ts_code, period)
        if values:
            rows.append(values)

    count = _upsert_klines(db, model, rows)
    return count


def _sync_klines_by_date(
    db: Session,
    period: str,
    start_date: date,
    end_date: date,
) -> int:
    """按交易日批量同步全市场 K 线（日线/周线/月线）。"""
    pro = get_pro()
    period = period.upper()
    model = _KLINE_MODELS[period]
    api_name = _KLINE_TUSHARE_APIS.get(period, "daily")

    trade_dates = _get_trade_dates(pro, start_date, end_date)
    if not trade_dates:
        return 0

    count = 0
    for trade_date_str in trade_dates:
        try:
            df = pro.query(api_name, trade_date=trade_date_str)
            _tushare_sleep()

            if df is None or df.empty:
                continue

            rows = []
            for _, row in df.iterrows():
                values = _build_kline_values(row, str(row.get("ts_code", "")), period)
                if values:
                    rows.append(values)

            count += _upsert_klines(db, model, rows)

            # 每个交易日批量 upsert 后立即提交，避免事务过大
            db.commit()
            _log(f"      {period} {trade_date_str} 完成 {len(rows)} 条")
        except Exception as exc:
            _log(f"[_sync_klines_by_date] failed for {period} {trade_date_str}: {exc}")
            db.rollback()
            continue

    return count


def sync_klines(
    ts_code: str | None = None,
    period: str = "D",
    years: int = 10,
    db: Session | None = None,
) -> int:
    """
    同步 K 线数据。

    - 未指定 ts_code 时，日/周/月线按交易日批量同步全市场，年线按股票同步
    - 指定 ts_code 时，按单只股票同步
    - 默认同步最近 10 年
    """
    period = period.upper()
    if period not in _KLINE_MODELS:
        raise ValueError(f"不支持的周期: {period}")

    end_date = date.today()
    start_date = end_date.replace(year=end_date.year - years)

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        count = 0
        if ts_code:
            count = _sync_klines_for_code(db, _normalize_code(ts_code), period, start_date, end_date)
        elif period == "Y":
            codes = [row[0] for row in db.execute(select(StockBasic.ts_code)).all()]
            if not codes:
                sync_stock_basic(db=db)
                codes = [row[0] for row in db.execute(select(StockBasic.ts_code)).all()]
            for code in codes:
                try:
                    count += _sync_yearly_from_monthly(db, code, start_date, end_date)
                except Exception as exc:
                    _log(f"[sync_klines] failed for {code}: {exc}")
                    continue
        else:
            count = _sync_klines_by_date(db, period, start_date, end_date)

        db.commit()
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 日线因子 daily_basic
# ---------------------------------------------------------------------------


def _build_daily_basic_values(row, ts_code_default: str) -> dict | None:
    """从 tushare 行数据构建日线因子字段字典。"""
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "ts_code": str(row.get("ts_code", ts_code_default)),
        "trade_date": trade_date,
        "close": _to_numeric(row.get("close")),
        "turnover_rate": _to_numeric(row.get("turnover_rate")),
        "turnover_rate_f": _to_numeric(row.get("turnover_rate_f")),
        "volume_ratio": _to_numeric(row.get("volume_ratio")),
        "pe": _to_numeric(row.get("pe")),
        "pe_ttm": _to_numeric(row.get("pe_ttm")),
        "pb": _to_numeric(row.get("pb")),
        "ps": _to_numeric(row.get("ps")),
        "ps_ttm": _to_numeric(row.get("ps_ttm")),
        "dv_ratio": _to_numeric(row.get("dv_ratio")),
        "dv_ttm": _to_numeric(row.get("dv_ttm")),
        "total_share": _to_numeric(row.get("total_share")),
        "float_share": _to_numeric(row.get("float_share")),
        "free_share": _to_numeric(row.get("free_share")),
        "total_mv": _to_numeric(row.get("total_mv")),
        "circ_mv": _to_numeric(row.get("circ_mv")),
    }


def _sync_daily_basic_by_date(
    db: Session,
    start_date: date,
    end_date: date,
) -> int:
    """按交易日批量同步全市场日线因子。"""
    pro = get_pro()
    trade_dates = _get_trade_dates(pro, start_date, end_date)
    if not trade_dates:
        return 0

    count = 0
    for trade_date_str in trade_dates:
        try:
            df = pro.daily_basic(trade_date=trade_date_str)
            _tushare_sleep()

            if df is None or df.empty:
                continue

            rows = []
            for _, row in df.iterrows():
                values = _build_daily_basic_values(row, str(row.get("ts_code", "")))
                if values:
                    rows.append(values)

            count += _upsert_daily_basic(db, rows)
            db.commit()
            _log(f"      daily_basic {trade_date_str} 完成 {len(rows)} 条")
        except Exception as exc:
            _log(f"[_sync_daily_basic_by_date] failed for {trade_date_str}: {exc}")
            db.rollback()
            continue

    return count


def _sync_daily_basic_for_code(
    db: Session,
    ts_code: str,
    start_date: date,
    end_date: date,
) -> int:
    """同步单只股票日线因子。"""
    pro = get_pro()
    df = pro.daily_basic(
        ts_code=ts_code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    _tushare_sleep()

    if df is None or df.empty:
        return 0

    rows = []
    for _, row in df.iterrows():
        values = _build_daily_basic_values(row, ts_code)
        if values:
            rows.append(values)

    count = _upsert_daily_basic(db, rows)
    return count


def sync_daily_basic(
    ts_code: str | None = None,
    years: int = 10,
    db: Session | None = None,
) -> int:
    """同步日线因子数据（daily_basic）。"""
    end_date = date.today()
    start_date = end_date.replace(year=end_date.year - years)

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if ts_code:
            count = _sync_daily_basic_for_code(db, _normalize_code(ts_code), start_date, end_date)
        else:
            count = _sync_daily_basic_by_date(db, start_date, end_date)

        db.commit()
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 财务指标 fina_indicator
# ---------------------------------------------------------------------------


def _build_fina_indicator_values(row, ts_code_default: str) -> dict | None:
    """从 tushare 行数据构建财务指标字段字典。"""
    end_date = _parse_date(row.get("end_date"))
    if end_date is None:
        return None

    values = {
        "ts_code": str(row.get("ts_code", ts_code_default)),
        "ann_date": _parse_date(row.get("ann_date")),
        "end_date": end_date,
    }

    for column in StockFinaIndicator.__table__.columns:
        name = column.name
        if name in values or name in ("created_at", "updated_at"):
            continue
        values[name] = _to_numeric(row.get(name))

    return values


def _upsert_fina_indicator(db: Session, rows: list[dict]) -> int:
    """批量写入财务指标数据，按 (ts_code, end_date) 去重。"""
    if not rows:
        return 0

    # tushare 可能返回同一报告期的多条记录（不同 report_type），去重保留最后一条
    seen = {}
    for row in rows:
        key = (row.get("ts_code"), row.get("end_date"))
        seen[key] = row
    deduped_rows = list(seen.values())

    stmt = insert(StockFinaIndicator).values(deduped_rows)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in StockFinaIndicator.__table__.columns
        if c.name not in ("ts_code", "end_date")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_code", "end_date"],
        set_=update_dict,
    )
    db.execute(stmt)
    return len(deduped_rows)


def sync_fina_indicator(
    ts_code: str | None = None,
    years: int = 10,
    db: Session | None = None,
) -> int:
    """同步财务指标数据（fina_indicator）。"""
    pro = get_pro()

    end_date = date.today()
    start_date = end_date.replace(year=end_date.year - years)

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        count = 0
        if ts_code:
            codes = [_normalize_code(ts_code)]
        else:
            codes = [row[0] for row in db.execute(select(StockBasic.ts_code)).all()]
            if not codes:
                sync_stock_basic(db=db)
                codes = [row[0] for row in db.execute(select(StockBasic.ts_code)).all()]

        for idx, code in enumerate(codes, start=1):
            try:
                df = pro.fina_indicator(
                    ts_code=code,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
                _tushare_sleep()

                if df is None or df.empty:
                    continue

                rows = []
                for _, row in df.iterrows():
                    values = _build_fina_indicator_values(row, code)
                    if values:
                        rows.append(values)

                count += _upsert_fina_indicator(db, rows)

                if idx % 100 == 0:
                    db.commit()
                    _log(f"      fina_indicator 进度: {idx}/{len(codes)}, 累计 {count} 条")
            except Exception as exc:
                _log(f"[sync_fina_indicator] failed for {code}: {exc}")
                db.rollback()
                continue

        db.commit()
        _log(f"      fina_indicator 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 板块资金流（同花顺）
# ---------------------------------------------------------------------------


_SECTOR_MONEYFLOW_API_MAP = {
    "industry": ("moneyflow_ind_ths", SectorMoneyflowIndustry),
    "concept": ("moneyflow_cnt_ths", SectorMoneyflowConcept),
}


def _build_sector_moneyflow_values(
    row, sector_type: str, ts_code_default: str
) -> dict | None:
    """从 tushare 行数据构建板块资金流字段字典。"""
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None

    ts_code = str(row.get("ts_code", ts_code_default))
    values = {
        "ts_code": ts_code,
        "trade_date": trade_date,
        "lead_stock": str(row.get("lead_stock", "")) if row.get("lead_stock") is not None else None,
        "pct_change": _to_numeric(row.get("pct_change")),
        "company_num": _to_numeric(row.get("company_num")),
        "pct_change_stock": _to_numeric(row.get("pct_change_stock")),
        "close_price": _to_numeric(row.get("close_price")),
        "net_buy_amount": _to_numeric(row.get("net_buy_amount")),
        "net_sell_amount": _to_numeric(row.get("net_sell_amount")),
        "net_amount": _to_numeric(row.get("net_amount")),
    }

    if sector_type == "industry":
        values["industry"] = str(row.get("industry", "")) if row.get("industry") is not None else None
        values["close"] = _to_numeric(row.get("close"))
    else:
        values["name"] = str(row.get("name", "")) if row.get("name") is not None else None
        values["industry_index"] = _to_numeric(row.get("industry_index"))

    return values


def _upsert_sector_moneyflow(
    db: Session, model, rows: list[dict]
) -> int:
    """批量写入板块资金流数据，按 (ts_code, trade_date) 去重。"""
    if not rows:
        return 0

    stmt = insert(model).values(rows)
    update_dict = {
        c.name: stmt.excluded[c.name]
        for c in model.__table__.columns
        if c.name not in ("ts_code", "trade_date")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_code", "trade_date"],
        set_=update_dict,
    )
    db.execute(stmt)
    return len(rows)


def sync_sector_moneyflow(
    sector_type: str = "industry",
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """
    同步同花顺板块资金流数据。

    - sector_type: industry（行业）或 concept（概念）
    - 默认从数据库中最新日期同步到最近一个交易日；首次从 2024-09-10 开始
    """
    if sector_type not in _SECTOR_MONEYFLOW_API_MAP:
        raise ValueError(f"不支持的板块类型: {sector_type}")

    api_name, model = _SECTOR_MONEYFLOW_API_MAP[sector_type]
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            latest = db.execute(
                select(model.trade_date).order_by(model.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
            if latest is None:
                # 同花顺板块资金流数据最早从 2024-09-10 开始提供
                start_date = date(2024, 9, 10)
            else:
                start_date = latest

        trade_dates = _get_trade_dates(pro, start_date, end_date)
        if not trade_dates:
            return 0

        count = 0
        for trade_date_str in trade_dates:
            try:
                df = pro.query(api_name, trade_date=trade_date_str)
                _tushare_sleep()

                if df is None or df.empty:
                    continue

                rows = []
                for _, row in df.iterrows():
                    values = _build_sector_moneyflow_values(
                        row, sector_type, str(row.get("ts_code", ""))
                    )
                    if values:
                        rows.append(values)

                count += _upsert_sector_moneyflow(db, model, rows)
                db.commit()
                _log(f"      {api_name} {trade_date_str} 完成 {len(rows)} 条")
            except Exception as exc:
                _log(f"[sync_sector_moneyflow] {api_name} failed for {trade_date_str}: {exc}")
                db.rollback()
                continue

        _log(f"      {api_name} 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 更多股票相关数据（10000+ 积分可访问）
# ---------------------------------------------------------------------------


def _sync_by_trade_date(
    db: Session,
    pro,
    api_name: str,
    model,
    build_values: callable,
    start_date: date,
    end_date: date,
    log_prefix: str = "",
) -> int:
    """通用按交易日同步逻辑。"""
    trade_dates = _get_trade_dates(pro, start_date, end_date)
    if not trade_dates:
        return 0

    count = 0
    for trade_date_str in trade_dates:
        try:
            df = pro.query(api_name, trade_date=trade_date_str)
            _tushare_sleep()

            if df is None or df.empty:
                continue

            rows = []
            for _, row in df.iterrows():
                values = build_values(row)
                if values:
                    rows.append(values)

            if rows:
                pk_columns = [c.name for c in model.__table__.primary_key.columns]
                # 按主键去重（同一批次 Tushare 可能返回完全重复的行）
                seen = {}
                for r in rows:
                    key = tuple(r.get(c) for c in pk_columns)
                    seen[key] = r
                rows = list(seen.values())
                pk_columns = [c.name for c in model.__table__.primary_key.columns]
                stmt = insert(model).values(rows)
                update_dict = {
                    c.name: stmt.excluded[c.name]
                    for c in model.__table__.columns
                    if c.name not in pk_columns and c.name not in ("created_at", "updated_at")
                }
                if update_dict:
                    stmt = stmt.on_conflict_do_update(index_elements=pk_columns, set_=update_dict)
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)
                db.execute(stmt)
                db.commit()

            count += len(rows)
            _log(f"      {log_prefix}{api_name} {trade_date_str} 完成 {len(rows)} 条")
        except Exception as exc:
            _log(f"[_sync_by_trade_date] {api_name} failed for {trade_date_str}: {exc}")
            db.rollback()
            continue

    return count


def _latest_trade_date(db: Session, model, date_column) -> date | None:
    """获取某表最新交易日期。"""
    return db.execute(select(date_column).order_by(date_column.desc()).limit(1)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# 个股资金流向
# ---------------------------------------------------------------------------


def _build_stock_moneyflow_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "ts_code": str(row.get("ts_code", "")),
        "trade_date": trade_date,
        "buy_sm_vol": _to_numeric(row.get("buy_sm_vol")),
        "buy_sm_amount": _to_numeric(row.get("buy_sm_amount")),
        "sell_sm_vol": _to_numeric(row.get("sell_sm_vol")),
        "sell_sm_amount": _to_numeric(row.get("sell_sm_amount")),
        "buy_md_vol": _to_numeric(row.get("buy_md_vol")),
        "buy_md_amount": _to_numeric(row.get("buy_md_amount")),
        "sell_md_vol": _to_numeric(row.get("sell_md_vol")),
        "sell_md_amount": _to_numeric(row.get("sell_md_amount")),
        "buy_lg_vol": _to_numeric(row.get("buy_lg_vol")),
        "buy_lg_amount": _to_numeric(row.get("buy_lg_amount")),
        "sell_lg_vol": _to_numeric(row.get("sell_lg_vol")),
        "sell_lg_amount": _to_numeric(row.get("sell_lg_amount")),
        "buy_elg_vol": _to_numeric(row.get("buy_elg_vol")),
        "buy_elg_amount": _to_numeric(row.get("buy_elg_amount")),
        "sell_elg_vol": _to_numeric(row.get("sell_elg_vol")),
        "sell_elg_amount": _to_numeric(row.get("sell_elg_amount")),
        "net_mf_vol": _to_numeric(row.get("net_mf_vol")),
        "net_mf_amount": _to_numeric(row.get("net_mf_amount")),
    }


def sync_stock_moneyflow(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步个股资金流向（全市场按交易日）。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, StockMoneyflow, StockMoneyflow.trade_date)
            start_date = latest if latest else date(2024, 9, 10)

        count = _sync_by_trade_date(
            db, pro, "moneyflow", StockMoneyflow, _build_stock_moneyflow_values,
            start_date, end_date, log_prefix="个股资金 "
        )
        _log(f"      moneyflow 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 沪深港通资金流向
# ---------------------------------------------------------------------------


def _build_moneyflow_hsgt_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "trade_date": trade_date,
        "ggt_ss": _to_numeric(row.get("ggt_ss")),
        "ggt_sz": _to_numeric(row.get("ggt_sz")),
        "hgt": _to_numeric(row.get("hgt")),
        "sgt": _to_numeric(row.get("sgt")),
        "north_money": _to_numeric(row.get("north_money")),
        "south_money": _to_numeric(row.get("south_money")),
    }


def sync_moneyflow_hsgt(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步沪深港通资金流向。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, MoneyflowHsgt, MoneyflowHsgt.trade_date)
            start_date = latest if latest else date(2014, 11, 17)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        df = pro.moneyflow_hsgt(start_date=start_str, end_date=end_str)
        _tushare_sleep()

        if df is None or df.empty:
            return 0

        rows = [_build_moneyflow_hsgt_values(r) for _, r in df.iterrows()]
        rows = [r for r in rows if r]

        stmt = insert(MoneyflowHsgt).values(rows)
        update_dict = {
            c.name: stmt.excluded[c.name]
            for c in MoneyflowHsgt.__table__.columns
            if c.name != "trade_date"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["trade_date"], set_=update_dict)
        db.execute(stmt)
        db.commit()

        _log(f"      moneyflow_hsgt 完成: 累计 {len(rows)} 条")
        return len(rows)
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 指数基础信息 & 指数日线
# ---------------------------------------------------------------------------


def sync_index_basic(db: Session | None = None) -> int:
    """同步指数基础信息。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        df = pro.index_basic()
        _tushare_sleep()

        if df is None or df.empty:
            return 0

        rows = []
        for _, row in df.iterrows():
            rows.append({
                "ts_code": str(row.get("ts_code", "")),
                "name": str(row.get("name", "")) if row.get("name") is not None else None,
                "market": str(row.get("market", "")) if row.get("market") is not None else None,
                "publisher": str(row.get("publisher", "")) if row.get("publisher") is not None else None,
                "category": str(row.get("category", "")) if row.get("category") is not None else None,
                "base_date": _parse_date(row.get("base_date")),
                "base_point": _to_numeric(row.get("base_point")),
                "list_date": _parse_date(row.get("list_date")),
            })

        stmt = insert(IndexBasic).values(rows)
        update_dict = {
            c.name: stmt.excluded[c.name]
            for c in IndexBasic.__table__.columns
            if c.name != "ts_code"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["ts_code"], set_=update_dict)
        db.execute(stmt)
        db.commit()

        _log(f"      index_basic 完成: 累计 {len(rows)} 条")
        return len(rows)
    finally:
        if should_close_db:
            db.close()


def _build_index_daily_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "ts_code": str(row.get("ts_code", "")),
        "trade_date": trade_date,
        "open": _to_numeric(row.get("open")),
        "high": _to_numeric(row.get("high")),
        "low": _to_numeric(row.get("low")),
        "close": _to_numeric(row.get("close")),
        "pre_close": _to_numeric(row.get("pre_close")),
        "change": _to_numeric(row.get("change")),
        "pct_chg": _to_numeric(row.get("pct_chg")),
        "vol": _to_numeric(row.get("vol")),
        "amount": _to_numeric(row.get("amount")),
    }


def sync_index_daily(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步指数日线行情。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, IndexDaily, IndexDaily.trade_date)
            start_date = latest if latest else date(1990, 12, 19)

        count = _sync_by_trade_date(
            db, pro, "index_daily", IndexDaily, _build_index_daily_values,
            start_date, end_date, log_prefix="指数日线 "
        )
        _log(f"      index_daily 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 涨跌停（stk_limit）
# ---------------------------------------------------------------------------


def _build_stock_limit_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "trade_date": trade_date,
        "ts_code": str(row.get("ts_code", "")),
        "up_limit": _to_numeric(row.get("up_limit")),
        "down_limit": _to_numeric(row.get("down_limit")),
    }


def sync_stock_limit(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步涨跌停股票数据。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, StockLimit, StockLimit.trade_date)
            start_date = latest if latest else date(2024, 9, 10)

        count = _sync_by_trade_date(
            db, pro, "stk_limit", StockLimit, _build_stock_limit_values,
            start_date, end_date, log_prefix="涨跌停 "
        )
        _log(f"      stk_limit 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 龙虎榜
# ---------------------------------------------------------------------------


def _build_top_list_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    reason = str(row.get("reason", "")) if row.get("reason") is not None else ""
    return {
        "trade_date": trade_date,
        "ts_code": str(row.get("ts_code", "")),
        "reason": reason,
        "name": str(row.get("name", "")) if row.get("name") is not None else None,
        "close": _to_numeric(row.get("close")),
        "pct_change": _to_numeric(row.get("pct_change")),
        "turnover_rate": _to_numeric(row.get("turnover_rate")),
        "amount": _to_numeric(row.get("amount")),
        "l_sell": _to_numeric(row.get("l_sell")),
        "l_buy": _to_numeric(row.get("l_buy")),
        "l_amount": _to_numeric(row.get("l_amount")),
        "net_amount": _to_numeric(row.get("net_amount")),
        "net_rate": _to_numeric(row.get("net_rate")),
        "amount_rate": _to_numeric(row.get("amount_rate")),
        "float_values": _to_numeric(row.get("float_values")),
    }


def sync_top_list(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步龙虎榜每日明细。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, TopList, TopList.trade_date)
            start_date = latest if latest else date(2024, 9, 10)

        count = _sync_by_trade_date(
            db, pro, "top_list", TopList, _build_top_list_values,
            start_date, end_date, log_prefix="龙虎榜 "
        )
        _log(f"      top_list 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


def _build_top_inst_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    reason = str(row.get("reason", "")) if row.get("reason") is not None else ""
    return {
        "trade_date": trade_date,
        "ts_code": str(row.get("ts_code", "")),
        "exalter": str(row.get("exalter", "")) if row.get("exalter") is not None else "",
        "side": str(row.get("side", "")) if row.get("side") is not None else "",
        "reason": reason,
        "buy": _to_numeric(row.get("buy")),
        "buy_rate": _to_numeric(row.get("buy_rate")),
        "sell": _to_numeric(row.get("sell")),
        "sell_rate": _to_numeric(row.get("sell_rate")),
        "net_buy": _to_numeric(row.get("net_buy")),
    }


def sync_top_inst(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步龙虎榜机构明细。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, TopInst, TopInst.trade_date)
            start_date = latest if latest else date(2024, 9, 10)

        count = _sync_by_trade_date(
            db, pro, "top_inst", TopInst, _build_top_inst_values,
            start_date, end_date, log_prefix="龙虎榜机构 "
        )
        _log(f"      top_inst 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 同花顺指数
# ---------------------------------------------------------------------------


def sync_ths_index(db: Session | None = None) -> int:
    """同步同花顺指数基础信息。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        df = pro.ths_index()
        _tushare_sleep()

        if df is None or df.empty:
            return 0

        rows = []
        for _, row in df.iterrows():
            rows.append({
                "ts_code": str(row.get("ts_code", "")),
                "name": str(row.get("name", "")) if row.get("name") is not None else None,
                "count": _to_numeric(row.get("count")),
                "exchange": str(row.get("exchange", "")) if row.get("exchange") is not None else None,
                "list_date": _parse_date(row.get("list_date")),
                "type": str(row.get("type", "")) if row.get("type") is not None else None,
            })

        stmt = insert(ThsIndex).values(rows)
        update_dict = {
            c.name: stmt.excluded[c.name]
            for c in ThsIndex.__table__.columns
            if c.name != "ts_code"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["ts_code"], set_=update_dict)
        db.execute(stmt)
        db.commit()

        _log(f"      ths_index 完成: 累计 {len(rows)} 条")
        return len(rows)
    finally:
        if should_close_db:
            db.close()


def _build_ths_daily_values(row) -> dict | None:
    trade_date = _parse_date(row.get("trade_date"))
    if trade_date is None:
        return None
    return {
        "ts_code": str(row.get("ts_code", "")),
        "trade_date": trade_date,
        "open": _to_numeric(row.get("open")),
        "high": _to_numeric(row.get("high")),
        "low": _to_numeric(row.get("low")),
        "close": _to_numeric(row.get("close")),
        "pre_close": _to_numeric(row.get("pre_close")),
        "avg_price": _to_numeric(row.get("avg_price")),
        "change": _to_numeric(row.get("change")),
        "pct_change": _to_numeric(row.get("pct_change")),
        "vol": _to_numeric(row.get("vol")),
        "turnover_rate": _to_numeric(row.get("turnover_rate")),
    }


def sync_ths_daily(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session | None = None,
) -> int:
    """同步同花顺指数日线。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            latest = _latest_trade_date(db, ThsDaily, ThsDaily.trade_date)
            start_date = latest if latest else date(2024, 9, 10)

        count = _sync_by_trade_date(
            db, pro, "ths_daily", ThsDaily, _build_ths_daily_values,
            start_date, end_date, log_prefix="THS日线 "
        )
        _log(f"      ths_daily 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


def sync_ths_member(db: Session | None = None) -> int:
    """同步同花顺指数成分股。"""
    pro = get_pro()

    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        codes = [row[0] for row in db.execute(select(ThsIndex.ts_code)).all()]
        if not codes:
            sync_ths_index(db=db)
            codes = [row[0] for row in db.execute(select(ThsIndex.ts_code)).all()]

        count = 0
        for idx, ts_code in enumerate(codes, start=1):
            try:
                df = pro.ths_member(ts_code=ts_code)
                _tushare_sleep()

                if df is None or df.empty:
                    continue

                rows = []
                for _, row in df.iterrows():
                    rows.append({
                        "ts_code": ts_code,
                        "con_code": str(row.get("con_code", "")),
                        "con_name": str(row.get("con_name", "")) if row.get("con_name") is not None else None,
                    })

                if rows:
                    stmt = insert(ThsMember).values(rows)
                    stmt = stmt.on_conflict_do_nothing(index_elements=["ts_code", "con_code"])
                    db.execute(stmt)

                count += len(rows)
                if idx % 50 == 0:
                    db.commit()
                    _log(f"      ths_member 进度: {idx}/{len(codes)}, 累计 {count} 条")
            except Exception as exc:
                _log(f"[sync_ths_member] failed for {ts_code}: {exc}")
                db.rollback()
                continue

        db.commit()
        _log(f"      ths_member 完成: 累计 {count} 条")
        return count
    finally:
        if should_close_db:
            db.close()


# ---------------------------------------------------------------------------
# 全量同步入口
# ---------------------------------------------------------------------------


def sync_all(years: int = 10) -> dict:
    """同步所有股票数据。"""
    results = {}
    results["stock_basic"] = sync_stock_basic()
    results["daily"] = sync_klines(period="D", years=years)
    results["weekly"] = sync_klines(period="W", years=years)
    results["monthly"] = sync_klines(period="M", years=years)
    results["yearly"] = sync_klines(period="Y", years=years)
    results["daily_basic"] = sync_daily_basic(years=years)
    results["fina_indicator"] = sync_fina_indicator(years=years)
    results["sector_moneyflow_industry"] = sync_sector_moneyflow("industry")
    results["sector_moneyflow_concept"] = sync_sector_moneyflow("concept")
    results["stock_moneyflow"] = sync_stock_moneyflow()
    results["moneyflow_hsgt"] = sync_moneyflow_hsgt()
    results["index_basic"] = sync_index_basic()
    results["index_daily"] = sync_index_daily()
    results["stock_limit"] = sync_stock_limit()
    results["top_list"] = sync_top_list()
    results["top_inst"] = sync_top_inst()
    results["ths_index"] = sync_ths_index()
    results["ths_daily"] = sync_ths_daily()
    results["ths_member"] = sync_ths_member()
    return results
