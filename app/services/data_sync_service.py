"""Tushare 数据同步服务。

负责从 Tushare Pro 拉取股票基础信息、K 线行情、日线因子、财务指标等数据，
写入 PostgreSQL/TimescaleDB。
"""

import time
from datetime import date, datetime, timedelta

import tushare as ts
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.stock import (
    StockBasic,
    StockDaily,
    StockDailyBasic,
    StockFinaIndicator,
    StockMonthly,
    StockWeekly,
    StockYearly,
)

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
    import pandas as pd

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
    "Y": "yearly",
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
    """批量写入 K 线数据。"""
    count = 0
    for values in rows:
        stmt = (
            insert(model)
            .values(values)
            .on_conflict_do_update(
                index_elements=["ts_code", "trade_date"],
                set_={k: v for k, v in values.items() if k not in ("ts_code", "trade_date")},
            )
        )
        db.execute(stmt)
        count += 1
    return count


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

            if count % 5000 == 0:
                db.commit()
        except Exception as exc:
            print(f"[_sync_klines_by_date] failed for {period} {trade_date_str}: {exc}")
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
                    count += _sync_klines_for_code(db, code, period, start_date, end_date)
                except Exception as exc:
                    print(f"[sync_klines] failed for {code}: {exc}")
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

            for values in rows:
                stmt = (
                    insert(StockDailyBasic)
                    .values(values)
                    .on_conflict_do_update(
                        index_elements=["ts_code", "trade_date"],
                        set_={k: v for k, v in values.items() if k not in ("ts_code", "trade_date")},
                    )
                )
                db.execute(stmt)
                count += 1

            if count % 5000 == 0:
                db.commit()
        except Exception as exc:
            print(f"[_sync_daily_basic_by_date] failed for {trade_date_str}: {exc}")
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

    count = 0
    for _, row in df.iterrows():
        values = _build_daily_basic_values(row, ts_code)
        if values is None:
            continue

        stmt = (
            insert(StockDailyBasic)
            .values(values)
            .on_conflict_do_update(
                index_elements=["ts_code", "trade_date"],
                set_={k: v for k, v in values.items() if k not in ("ts_code", "trade_date")},
            )
        )
        db.execute(stmt)
        count += 1

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

        for code in codes:
            try:
                df = pro.fina_indicator(
                    ts_code=code,
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
                _tushare_sleep()

                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    values = {
                        "ts_code": str(row.get("ts_code", code)),
                        "ann_date": _parse_date(row.get("ann_date")),
                        "end_date": _parse_date(row.get("end_date")),
                    }

                    if values["end_date"] is None:
                        continue

                    # 自动映射所有数值字段
                    for column in StockFinaIndicator.__table__.columns:
                        name = column.name
                        if name in values or name in ("created_at", "updated_at"):
                            continue
                        values[name] = _to_numeric(row.get(name))

                    stmt = (
                        insert(StockFinaIndicator)
                        .values(values)
                        .on_conflict_do_update(
                            index_elements=["ts_code", "end_date"],
                            set_={k: v for k, v in values.items() if k not in ("ts_code", "end_date")},
                        )
                    )
                    db.execute(stmt)
                    count += 1

                if count % 1000 == 0:
                    db.commit()
            except Exception as exc:
                print(f"[sync_fina_indicator] failed for {code}: {exc}")
                continue

        db.commit()
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
    return results
