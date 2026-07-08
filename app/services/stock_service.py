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


def get_klines(code: str, period: str = "D", limit: int = 30) -> list[KlineData]:
    """获取股票 K 线数据。"""
    if settings.mock_stock_data:
        return _mock_klines(code, period=period, limit=limit)

    ts_code = _normalize_code(code)
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


def get_user_watchlist() -> list[StockData]:
    """获取示例自选股行情。"""
    codes = ["000001.SZ", "000002.SZ", "600519.SH", "00700.HK"]
    return [get_stock_quote(code) for code in codes]


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
