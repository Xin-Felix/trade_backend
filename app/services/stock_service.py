"""股票行情服务。

从 PostgreSQL/TimescaleDB 读取股票 K 线、因子等数据，供 API 使用。
开发环境可回退到 mock 数据。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.stock import (
    SectorMoneyflowConcept,
    SectorMoneyflowIndustry,
    StockBasic,
    StockDaily,
    StockDailyBasic,
    StockMonthly,
    StockWeekly,
    StockYearly,
)
from app.schemas.stock import KlineData, StockData


# 初始化 Tushare Pro（行情接口主要用于实时补数据，本地以库为准）
_pro = None


def get_pro():
    global _pro
    if _pro is None:
        if not settings.tushare_token:
            raise RuntimeError("TUSHARE_TOKEN 未配置，请在 .env 中设置")
        import tushare as ts

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


def _format_change_percent(prev_close: Decimal, close: Decimal) -> float:
    if prev_close == 0:
        return 0.0
    return round(float((close - prev_close) / prev_close * 100), 2)


def _get_kline_model(period: str):
    mapping = {
        "D": StockDaily,
        "W": StockWeekly,
        "M": StockMonthly,
        "Y": StockYearly,
    }
    period = period.upper()
    if period not in mapping:
        raise ValueError(f"不支持的周期: {period}")
    return mapping[period]


def _stock_name(db: Session, ts_code: str) -> str:
    basic = db.execute(select(StockBasic.name).where(StockBasic.ts_code == ts_code)).scalar_one_or_none()
    return basic or ts_code


# ---------------------------------------------------------------------------
# 行情接口
# ---------------------------------------------------------------------------


def get_stock_quote(code: str) -> StockData:
    """获取单只股票最新行情。"""
    if settings.mock_stock_data:
        return _mock_stock_quote(code)

    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        latest = (
            db.execute(
                select(StockDaily)
                .where(StockDaily.ts_code == ts_code)
                .order_by(StockDaily.trade_date.desc())
            )
            .scalars()
            .first()
        )

        if latest is None:
            return StockData(
                code=code,
                name=_stock_name(db, ts_code),
                price=0.0,
                change_percent=0.0,
                updated_at=datetime.now().isoformat(),
            )

        prev_close = latest.pre_close or latest.open
        change_percent = _format_change_percent(prev_close, latest.close)

        return StockData(
            code=code,
            name=_stock_name(db, ts_code),
            price=float(latest.close) if latest.close else 0.0,
            change_percent=change_percent,
            updated_at=datetime.now().isoformat(),
        )
    finally:
        db.close()


def _is_index_code(ts_code: str) -> bool:
    """判断 ts_code 是否为大盘指数代码。"""
    ts_code = ts_code.upper()
    if ts_code.endswith(".SH") and ts_code.split(".")[0].startswith("000"):
        return True
    if ts_code.endswith(".SZ") and ts_code.split(".")[0].startswith("399"):
        return True
    return False


def get_klines(code: str, period: str = "D", limit: int = 30) -> list[KlineData]:
    """获取股票或指数 K 线数据。"""
    if settings.mock_stock_data:
        return _mock_klines(code, period=period, limit=limit)

    ts_code = _normalize_code(code)

    # 大盘指数走 Tushare index_daily，本地表只存了个股 K 线
    if _is_index_code(ts_code) and period.upper() == "D":
        return _get_index_klines(ts_code, limit=limit)

    model = _get_kline_model(period)

    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(model)
                .where(model.ts_code == ts_code)
                .order_by(model.trade_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            KlineData(
                ts_code=r.ts_code,
                trade_date=r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                period=period,
                open=float(r.open) if r.open else 0.0,
                high=float(r.high) if r.high else 0.0,
                low=float(r.low) if r.low else 0.0,
                close=float(r.close) if r.close else 0.0,
                volume=float(r.vol) if r.vol else None,
                amount=float(r.amount) if r.amount else None,
            )
            for r in rows
        ]
    finally:
        db.close()


def _get_index_klines(ts_code: str, limit: int = 30) -> list[KlineData]:
    """通过 Tushare 获取指数日线 K 线。"""
    try:
        pro = get_pro()
    except RuntimeError:
        return []

    try:
        df = pro.index_daily(ts_code=ts_code, limit=limit)
        if df is None or df.empty:
            return []

        klines = []
        for _, row in df.iterrows():
            klines.append(
                KlineData(
                    ts_code=ts_code,
                    trade_date=str(row["trade_date"]),
                    period="D",
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["vol"]) if "vol" in row and row["vol"] is not None else None,
                    amount=float(row["amount"]) if "amount" in row and row["amount"] is not None else None,
                )
            )

        return sorted(klines, key=lambda k: k.trade_date, reverse=True)
    except Exception:
        return []


def get_user_watchlist() -> list[StockData]:
    """获取示例自选股行情。"""
    codes = ["000001.SZ", "000002.SZ", "600519.SH", "00700.HK"]
    return [get_stock_quote(code) for code in codes]


def search_stocks(query: str, limit: int = 10) -> list[dict]:
    """根据代码、名称或拼音缩写搜索股票。"""
    if settings.mock_stock_data:
        return _mock_search_stocks(query, limit=limit)

    q = query.strip()
    if not q:
        return []

    db = SessionLocal()
    try:
        from sqlalchemy import or_

        # 前缀匹配，能走 B-tree 索引，比 %%q%% 的全表扫描快很多
        like_pattern = f"{q}%"
        rows = (
            db.execute(
                select(StockBasic)
                .where(
                    or_(
                        StockBasic.ts_code.ilike(like_pattern),
                        StockBasic.symbol.ilike(like_pattern),
                        StockBasic.name.ilike(like_pattern),
                        StockBasic.cnspell.ilike(like_pattern),
                    )
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {"code": basic.symbol or basic.ts_code.split(".")[0], "name": basic.name or basic.ts_code}
            for basic in rows
        ]
    finally:
        db.close()


def get_stock_basics() -> list[dict]:
    """获取全部股票基础信息，用于 iOS 端本地缓存和搜索。"""
    if settings.mock_stock_data:
        return _mock_stock_basics()

    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(StockBasic.ts_code, StockBasic.symbol, StockBasic.name, StockBasic.cnspell)
                .order_by(StockBasic.ts_code)
            )
            .mappings()
            .all()
        )

        return [
            {
                "code": row["symbol"] or row["ts_code"].split(".")[0],
                "name": row["name"] or row["ts_code"],
                "cnspell": row["cnspell"],
            }
            for row in rows
        ]
    finally:
        db.close()


def get_indices() -> list[dict]:
    """获取主要大盘指数最新数据（上证、深证成指、创业板指）。"""
    if settings.mock_stock_data:
        return _mock_indices()

    index_codes = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
    }

    try:
        pro = get_pro()
    except RuntimeError:
        return _mock_indices()

    result = []
    for ts_code, name in index_codes.items():
        try:
            df = pro.index_daily(ts_code=ts_code, limit=2)
            if df is None or df.empty or len(df) < 2:
                continue

            latest = df.iloc[0]
            prev = df.iloc[1]
            close = float(latest["close"])
            prev_close = float(prev["close"])
            change = round((close - prev_close) / prev_close * 100, 2) if prev_close != 0 else 0.0

            result.append({"name": name, "value": close, "change": change, "ts_code": ts_code})
        except Exception:
            continue

    return result if result else _mock_indices()


# ---------------------------------------------------------------------------
# 因子接口（策略用）
# ---------------------------------------------------------------------------


def get_daily_basic(code: str, limit: int = 30) -> list[dict]:
    """获取股票日线因子数据。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(StockDailyBasic)
                .where(StockDailyBasic.ts_code == ts_code)
                .order_by(StockDailyBasic.trade_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "close": float(r.close) if r.close else None,
                "turnover_rate": float(r.turnover_rate) if r.turnover_rate else None,
                "turnover_rate_f": float(r.turnover_rate_f) if r.turnover_rate_f else None,
                "volume_ratio": float(r.volume_ratio) if r.volume_ratio else None,
                "pe": float(r.pe) if r.pe else None,
                "pe_ttm": float(r.pe_ttm) if r.pe_ttm else None,
                "pb": float(r.pb) if r.pb else None,
                "ps": float(r.ps) if r.ps else None,
                "ps_ttm": float(r.ps_ttm) if r.ps_ttm else None,
                "dv_ratio": float(r.dv_ratio) if r.dv_ratio else None,
                "dv_ttm": float(r.dv_ttm) if r.dv_ttm else None,
                "total_share": float(r.total_share) if r.total_share else None,
                "float_share": float(r.float_share) if r.float_share else None,
                "free_share": float(r.free_share) if r.free_share else None,
                "total_mv": float(r.total_mv) if r.total_mv else None,
                "circ_mv": float(r.circ_mv) if r.circ_mv else None,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 板块资金流接口
# ---------------------------------------------------------------------------


_SECTOR_MONEYFLOW_MODELS = {
    "industry": SectorMoneyflowIndustry,
    "concept": SectorMoneyflowConcept,
}


def get_sector_moneyflow_rank(
    sector_type: str = "industry",
    trade_date: str | None = None,
    sort_by: str = "net_amount",
    limit: int = 20,
) -> dict:
    """获取板块资金流排行。"""
    sector_type = sector_type.lower()
    if sector_type not in _SECTOR_MONEYFLOW_MODELS:
        raise ValueError(f"不支持的板块类型: {sector_type}")

    model = _SECTOR_MONEYFLOW_MODELS[sector_type]
    db = SessionLocal()
    try:
        query = select(model)

        if trade_date:
            from datetime import datetime

            d = datetime.strptime(trade_date, "%Y%m%d").date()
            query = query.where(model.trade_date == d)
        else:
            # 取最新有数据的日期
            latest_date = db.execute(
                select(model.trade_date).order_by(model.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
            if latest_date is None:
                return {"sectors": [], "trade_date": "", "sector_type": sector_type}
            query = query.where(model.trade_date == latest_date)
            trade_date = latest_date.strftime("%Y%m%d")

        if sort_by == "net_amount":
            query = query.order_by(model.net_amount.desc())
        elif sort_by == "pct_change":
            query = query.order_by(model.pct_change.desc())
        elif sort_by == "net_amount_asc":
            query = query.order_by(model.net_amount.asc())
        else:
            query = query.order_by(model.net_amount.desc())

        rows = db.execute(query.limit(limit)).scalars().all()

        sectors = []
        for r in rows:
            name = r.industry if sector_type == "industry" else r.name
            sectors.append(
                {
                    "ts_code": r.ts_code,
                    "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                    "name": name,
                    "lead_stock": r.lead_stock,
                    "close_price": float(r.close_price) if r.close_price else None,
                    "pct_change": float(r.pct_change) if r.pct_change else None,
                    "company_num": int(r.company_num) if r.company_num is not None else None,
                    "pct_change_stock": float(r.pct_change_stock) if r.pct_change_stock else None,
                    "net_buy_amount": float(r.net_buy_amount) if r.net_buy_amount else None,
                    "net_sell_amount": float(r.net_sell_amount) if r.net_sell_amount else None,
                    "net_amount": float(r.net_amount) if r.net_amount else None,
                }
            )

        return {"sectors": sectors, "trade_date": trade_date, "sector_type": sector_type}
    finally:
        db.close()


def get_sector_moneyflow_trend(
    sector_type: str = "industry",
    start_date: str | None = None,
    end_date: str | None = None,
    top_n: int | None = None,
) -> dict:
    """获取板块资金流时间段趋势。"""
    sector_type = sector_type.lower()
    if sector_type not in _SECTOR_MONEYFLOW_MODELS:
        raise ValueError(f"不支持的板块类型: {sector_type}")

    model = _SECTOR_MONEYFLOW_MODELS[sector_type]
    db = SessionLocal()
    try:
        query = select(model)

        if start_date:
            d = datetime.strptime(start_date, "%Y%m%d").date()
            query = query.where(model.trade_date >= d)
        if end_date:
            d = datetime.strptime(end_date, "%Y%m%d").date()
            query = query.where(model.trade_date <= d)

        query = query.order_by(model.trade_date.asc(), model.ts_code.asc())
        rows = db.execute(query).scalars().all()

        dates_set: set[str] = set()
        series_map: dict[str, dict] = {}

        for r in rows:
            date_str = r.trade_date.strftime("%Y%m%d") if r.trade_date else ""
            if not date_str:
                continue
            dates_set.add(date_str)

            name = r.industry if sector_type == "industry" else r.name

            if r.ts_code not in series_map:
                series_map[r.ts_code] = {
                    "ts_code": r.ts_code,
                    "name": name,
                    "values": [],
                }

            series_map[r.ts_code]["values"].append(
                {
                    "trade_date": date_str,
                    "net_amount": float(r.net_amount) if r.net_amount else 0.0,
                    "pct_change": float(r.pct_change) if r.pct_change else None,
                }
            )

        sorted_dates = sorted(dates_set)
        series = list(series_map.values())

        # 按时间段累计净流入排序，返回 Top N
        if top_n is not None and top_n > 0:
            series = sorted(
                series,
                key=lambda s: sum(v["net_amount"] for v in s["values"]),
                reverse=True,
            )[:top_n]

        return {
            "sector_type": sector_type,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "dates": sorted_dates,
            "series": series,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Mock 数据（开发环境无 Tushare token 时使用）
# ---------------------------------------------------------------------------

_MOCK_KLINES_CACHE: dict[tuple[str, str], list[StockDaily]] = {}


def _mock_name(code: str) -> str:
    names = {
        "000001.SZ": "平安银行",
        "000002.SZ": "万科A",
        "600519.SH": "贵州茅台",
        "00700.HK": "腾讯控股",
    }
    return names.get(code, f"股票 {code}")


def _mock_search_stocks(query: str, limit: int = 10) -> list[dict]:
    """Mock 环境下按名称/代码搜索股票。"""
    q = query.strip().lower()
    mock_codes = ["000001.SZ", "000002.SZ", "600519.SH", "00700.HK"]
    results = []
    for ts_code in mock_codes:
        name = _mock_name(ts_code)
        code = ts_code.split(".")[0]
        if q in ts_code.lower() or q in code or q in name:
            results.append({"code": code, "name": name})
        if len(results) >= limit:
            break
    return results


def _mock_stock_basics() -> list[dict]:
    """Mock 环境下返回全部股票基础信息。"""
    mock_codes = ["000001.SZ", "000002.SZ", "600519.SH", "00700.HK"]
    return [
        {"code": ts_code.split(".")[0], "name": _mock_name(ts_code), "cnspell": None}
        for ts_code in mock_codes
    ]


def _mock_indices() -> list[dict]:
    """Mock 环境下返回大盘指数数据。"""
    return [
        {"name": "上证指数", "value": 3050.23, "change": 0.68, "ts_code": "000001.SH"},
        {"name": "深证成指", "value": 9876.54, "change": 1.23, "ts_code": "399001.SZ"},
        {"name": "创业板指", "value": 1890.12, "change": -0.45, "ts_code": "399006.SZ"},
    ]


def _generate_mock_klines(ts_code: str, period: str = "D", limit: int = 60) -> list[StockDaily]:
    """用随机游走生成 mock K 线。"""
    period = period.upper()
    key = (ts_code, period)
    if key in _MOCK_KLINES_CACHE:
        return _MOCK_KLINES_CACHE[key]

    import random

    random.seed(hash(ts_code))
    base_price = random.uniform(10, 2000)
    price = Decimal(str(base_price))
    klines: list[StockDaily] = []

    today = date.today()
    for i in range(limit):
        if period == "D":
            day = today - timedelta(days=i + 1)
            trade_date = day
        elif period == "W":
            day = today - timedelta(weeks=i + 1)
            trade_date = day
        elif period == "M":
            month = today.month - i - 1
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            from calendar import monthrange

            last_day = monthrange(year, month)[1]
            trade_date = date(year, month, last_day)
        else:  # Y
            year = today.year - i - 1
            trade_date = date(year, 12, 31)

        change = Decimal(str(random.uniform(-0.05, 0.05)))
        open_price = price
        close = price * (Decimal("1") + change)
        high = max(open_price, close) * (Decimal("1") + Decimal(str(random.uniform(0, 0.03))))
        low = min(open_price, close) * (Decimal("1") - Decimal(str(random.uniform(0, 0.03))))
        volume = Decimal(str(random.uniform(10000, 1000000)))

        klines.append(
            StockDaily(
                ts_code=ts_code,
                trade_date=trade_date,
                open=round(open_price, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                vol=round(volume, 4),
                amount=round(volume * close, 4),
            )
        )
        price = close

    klines = sorted(klines, key=lambda x: x.trade_date)
    _MOCK_KLINES_CACHE[key] = klines
    return klines


def _mock_stock_quote(code: str) -> StockData:
    ts_code = _normalize_code(code)
    klines = _generate_mock_klines(ts_code, period="D", limit=5)
    latest = klines[-1]
    prev = klines[-2] if len(klines) > 1 else latest
    change_percent = _format_change_percent(prev.close, latest.close)
    return StockData(
        code=code,
        name=_mock_name(ts_code),
        price=float(latest.close),
        change_percent=change_percent,
        updated_at=datetime.now().isoformat(),
    )


def _mock_klines(code: str, period: str = "D", limit: int = 30) -> list[KlineData]:
    ts_code = _normalize_code(code)
    rows = _generate_mock_klines(ts_code, period=period, limit=limit)
    rows = sorted(rows, key=lambda x: x.trade_date, reverse=True)[:limit]

    return [
        KlineData(
            ts_code=r.ts_code,
            trade_date=r.trade_date.strftime("%Y%m%d"),
            period=period,
            open=float(r.open),
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            volume=float(r.vol) if r.vol else None,
            amount=float(r.amount) if r.amount else None,
        )
        for r in rows
    ]
