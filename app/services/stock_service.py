"""股票行情服务。

从 PostgreSQL/TimescaleDB 读取股票 K 线、因子等数据，供 API 使用。
开发环境可回退到 mock 数据。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.intraday_sync import StockIntraday
from app.core.config import settings
from app.core.redis import redis_client
from app.db.base import SessionLocal
from app.models.stock import (
    IndexDaily,
    MoneyflowHsgt,
    SectorMoneyflowConcept,
    SectorMoneyflowIndustry,
    StockBasic,
    StockDaily,
    StockDailyBasic,
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
from app.schemas.stock import IntradayKlineData, KlineData, StockData


# 初始化 Tushare Pro（行情接口主要用于实时补数据，本地以库为准）
_pro = None


def get_pro():
    global _pro
    if _pro is None:
        if not settings.tushare_token:
            raise RuntimeError("TUSHARE_TOKEN 未配置，请在 .env 中设置")
        import tushare as ts

        # 优先使用代理（积分更高，支持更多接口）
        if settings.tushare_proxy_url and settings.tushare_proxy_token:
            ts.set_token(settings.tushare_proxy_token)
            _pro = ts.pro_api(settings.tushare_proxy_token)
            _pro._DataApi__http_url = settings.tushare_proxy_url
        else:
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


def _classify_board(con_code: str, con_name: str | None) -> str:
    """根据股票代码和名称判断所属板块。"""
    name = con_name or ""
    if "ST" in name.upper():
        return "st"
    if con_code.startswith("688"):
        return "star"
    if con_code.startswith("300") or con_code.startswith("301"):
        return "chuang"
    if con_code.startswith("8") or con_code.startswith("4") or con_code.startswith("920"):
        return "bj"
    if con_code.startswith("60") or con_code.startswith("00") or con_code.startswith("001"):
        return "main"
    return "other"


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
                pre_close=None,
                updated_at=datetime.now().isoformat(),
            )

        # 最新日线记录：close 为当日收盘价，pre_close 为昨收
        # iOS 端会用分时最新价覆盖 price，后端先给出基于日线的涨跌幅
        pre_close_price = latest.pre_close or latest.close
        current_price = latest.close
        change_percent = _format_change_percent(pre_close_price, current_price)

        return StockData(
            code=code,
            name=_stock_name(db, ts_code),
            price=float(current_price) if current_price else 0.0,
            change_percent=change_percent,
            pre_close=float(pre_close_price) if pre_close_price else None,
            updated_at=datetime.now().isoformat(),
        )
    finally:
        db.close()


def get_stock_quotes_batch(codes: list[str]) -> list[StockData]:
    """批量获取多只股票最新行情（单次查询，高效）。"""
    if settings.mock_stock_data:
        return [_mock_stock_quote(c) for c in codes]
    if not codes:
        return []

    from sqlalchemy import func as sql_func

    ts_codes = [_normalize_code(c) for c in codes]
    db = SessionLocal()
    try:
        # 子查询：每只股票最新交易日
        subq = (
            select(StockDaily.ts_code, sql_func.max(StockDaily.trade_date).label("max_date"))
            .where(StockDaily.ts_code.in_(ts_codes))
            .group_by(StockDaily.ts_code)
            .subquery()
        )
        # 主查询：拿到每只股票最新一条日线
        rows = (
            db.execute(
                select(StockDaily)
                .join(subq, (StockDaily.ts_code == subq.c.ts_code) & (StockDaily.trade_date == subq.c.max_date))
            )
            .scalars()
            .all()
        )

        # 构建名称映射
        name_rows = db.execute(
            select(StockBasic.ts_code, StockBasic.name)
            .where(StockBasic.ts_code.in_(ts_codes))
        ).all()
        name_map = {r[0]: r[1] for r in name_rows}

        # 构建结果映射
        quote_map: dict[str, StockData] = {}
        for r in rows:
            pre_close_price = r.pre_close or r.close
            current_price = r.close
            change_percent = _format_change_percent(pre_close_price, current_price)
            quote_map[r.ts_code] = StockData(
                code=r.ts_code,
                name=name_map.get(r.ts_code, r.ts_code),
                price=float(current_price) if current_price else 0.0,
                change_percent=change_percent,
                pre_close=float(pre_close_price) if pre_close_price else None,
                updated_at=datetime.now().isoformat(),
            )

        # 按输入顺序返回
        results = []
        for code, ts_code in zip(codes, ts_codes):
            if ts_code in quote_map:
                item = quote_map[ts_code]
                results.append(item.model_copy(update={"code": code}))
            else:
                results.append(StockData(
                    code=code,
                    name=name_map.get(ts_code, code),
                    price=0.0,
                    change_percent=0.0,
                    pre_close=None,
                    updated_at=datetime.now().isoformat(),
                ))
        return results
    finally:
        db.close()


def get_stock_detail(code: str) -> dict:
    """聚合接口：一次查询返回股票详情页所需的多项低频数据。

    包含：quote + daily_basic + concepts + moneyflow(最近5日)
    全部走本地数据库，不调外部 API，延迟可控。
    """
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        # 1. Quote（最新日线）
        latest = (
            db.execute(
                select(StockDaily)
                .where(StockDaily.ts_code == ts_code)
                .order_by(StockDaily.trade_date.desc())
            )
            .scalars()
            .first()
        )
        if latest:
            pre_close_price = latest.pre_close or latest.close
            current_price = latest.close
            change_percent = _format_change_percent(pre_close_price, current_price)
            quote = {
                "code": code,
                "name": _stock_name(db, ts_code),
                "price": float(current_price) if current_price else 0.0,
                "change_percent": change_percent,
                "pre_close": float(pre_close_price) if pre_close_price else None,
                "updated_at": datetime.now().isoformat(),
            }
        else:
            quote = {
                "code": code,
                "name": _stock_name(db, ts_code),
                "price": 0.0,
                "change_percent": 0.0,
                "pre_close": None,
                "updated_at": datetime.now().isoformat(),
            }

        # 2. Daily Basic（最新1条）
        basic_row = (
            db.execute(
                select(StockDailyBasic)
                .where(StockDailyBasic.ts_code == ts_code)
                .order_by(StockDailyBasic.trade_date.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        daily_basic = None
        if basic_row:
            daily_basic = {
                "ts_code": basic_row.ts_code,
                "trade_date": basic_row.trade_date.strftime("%Y%m%d") if basic_row.trade_date else "",
                "turnover_rate": float(basic_row.turnover_rate) if basic_row.turnover_rate else None,
                "turnover_rate_f": float(basic_row.turnover_rate_f) if basic_row.turnover_rate_f else None,
                "volume_ratio": float(basic_row.volume_ratio) if basic_row.volume_ratio else None,
                "pe": float(basic_row.pe) if basic_row.pe else None,
                "pe_ttm": float(basic_row.pe_ttm) if basic_row.pe_ttm else None,
                "pb": float(basic_row.pb) if basic_row.pb else None,
                "ps": float(basic_row.ps) if basic_row.ps else None,
                "ps_ttm": float(basic_row.ps_ttm) if basic_row.ps_ttm else None,
                "dv_ratio": float(basic_row.dv_ratio) if basic_row.dv_ratio else None,
                "dv_ttm": float(basic_row.dv_ttm) if basic_row.dv_ttm else None,
                "total_share": float(basic_row.total_share) if basic_row.total_share else None,
                "float_share": float(basic_row.float_share) if basic_row.float_share else None,
                "free_share": float(basic_row.free_share) if basic_row.free_share else None,
                "total_mv": float(basic_row.total_mv) if basic_row.total_mv else None,
                "circ_mv": float(basic_row.circ_mv) if basic_row.circ_mv else None,
            }

        # 3. Concepts
        from app.models.stock import StockConcept
        concept_rows = (
            db.execute(
                select(StockConcept)
                .where(StockConcept.ts_code == ts_code)
                .where(StockConcept.out_date.is_(None))
                .order_by(StockConcept.in_date.desc())
            )
            .scalars()
            .all()
        )
        concepts = [
            {
                "concept_id": r.concept_id,
                "concept_name": r.concept_name,
                "ts_code": r.ts_code,
                "name": r.name,
            }
            for r in concept_rows
        ]

        # 4. Moneyflow（最近5日）
        mf_rows = (
            db.execute(
                select(StockMoneyflow)
                .where(StockMoneyflow.ts_code == ts_code)
                .order_by(StockMoneyflow.trade_date.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )
        moneyflow = [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "buy_sm_amount": float(r.buy_sm_amount) if r.buy_sm_amount else None,
                "sell_sm_amount": float(r.sell_sm_amount) if r.sell_sm_amount else None,
                "buy_md_amount": float(r.buy_md_amount) if r.buy_md_amount else None,
                "sell_md_amount": float(r.sell_md_amount) if r.sell_md_amount else None,
                "buy_lg_amount": float(r.buy_lg_amount) if r.buy_lg_amount else None,
                "sell_lg_amount": float(r.sell_lg_amount) if r.sell_lg_amount else None,
                "buy_elg_amount": float(r.buy_elg_amount) if r.buy_elg_amount else None,
                "sell_elg_amount": float(r.sell_elg_amount) if r.sell_elg_amount else None,
                "net_mf_amount": float(r.net_mf_amount) if r.net_mf_amount else None,
            }
            for r in mf_rows
        ]

        return {
            "quote": quote,
            "daily_basic": daily_basic,
            "concepts": concepts,
            "moneyflow": moneyflow,
        }
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


def _akshare_symbol(code: str) -> str:
    """把用户输入代码转成 akshare 分钟线接口需要的 symbol（sh600519 / sz000001）。"""
    code = code.strip().upper()
    if "." in code:
        pure, suffix = code.split(".", 1)
        if suffix == "SH":
            return f"sh{pure}"
        if suffix == "SZ":
            return f"sz{pure}"
        if suffix == "BJ":
            return f"bj{pure}"
        return code
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith("0") or code.startswith("3"):
        return f"sz{code}"
    if code.startswith("8") or code.startswith("4"):
        return f"bj{code}"
    return code


def _intraday_cache_ttl(latest_datetime_str: str) -> int:
    """根据最新 K 线时间判断数据是否完整，返回缓存 TTL（秒）。

    - 当天交易未结束：数据还在变，缓存短（30 秒）
    - 当天已收盘或历史日期：数据不会再变，缓存长（7 天）
    """
    try:
        latest = datetime.strptime(latest_datetime_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return 30

    now = datetime.now()
    market_close = latest.replace(hour=15, minute=0, second=0, microsecond=0)

    # 最新 K 线时间早于今天，说明是历史完整数据
    if latest.date() < now.date():
        return 7 * 24 * 60 * 60

    # 今天且已收盘（>= 15:00），数据完整
    if latest >= market_close:
        return 7 * 24 * 60 * 60

    # 今天未收盘，实时数据还在更新
    return 30


def _is_valid_intraday_cache(data: list[dict], period: str) -> bool:
    """校验 Redis 缓存的分时 K 线数据格式是否正确。

    旧版代码可能把跨日、倒序、条数不对的数据写入缓存，校验失败时让后端重新生成。
    """
    if not data or not isinstance(data, list):
        return False

    if not all(isinstance(item, dict) and item.get("datetime") for item in data):
        return False

    datetimes = [item["datetime"] for item in data]
    if datetimes != sorted(datetimes):
        return False

    # 1 分钟线应为单天完整 241 条（09:30~15:00）
    if period == "1":
        dates = {d[:10] for d in datetimes}
        if len(dates) != 1 or len(data) != 241:
            return False

    return True


def _trading_minute_times() -> list[str]:
    """生成A股1分钟K线的时间序列（HH:MM），共241个点：09:30~11:30 + 13:01~15:00。"""
    times = []
    for minutes in range(9 * 60 + 30, 11 * 60 + 31):
        h, m = divmod(minutes, 60)
        times.append(f"{h:02d}:{m:02d}")
    for minutes in range(13 * 60 + 1, 15 * 60 + 1):
        h, m = divmod(minutes, 60)
        times.append(f"{h:02d}:{m:02d}")
    return times


_TRADING_MINUTE_TIMES = _trading_minute_times()


def _fill_intraday_gaps(
    rows: list[StockIntraday], ts_code: str, trade_date: date
) -> list[IntradayKlineData]:
    """把数据库查询结果补齐为完整 241 个交易分钟，缺失点用上一分钟 close 填充。"""
    row_map = {str(r.trade_time): r for r in rows}
    date_str = trade_date.strftime("%Y-%m-%d")
    result: list[IntradayKlineData] = []
    last_close: float | None = None

    for time_str in _TRADING_MINUTE_TIMES:
        if time_str in row_map:
            r = row_map[time_str]
            close = float(r.close) if r.close is not None else last_close
            if close is None:
                close = 0.0
            last_close = close
            result.append(
                IntradayKlineData(
                    ts_code=ts_code,
                    datetime=f"{date_str} {time_str}:00",
                    period="1",
                    open=float(r.open) if r.open is not None else close,
                    high=float(r.high) if r.high is not None else close,
                    low=float(r.low) if r.low is not None else close,
                    close=close,
                    volume=float(r.volume) if r.volume is not None else None,
                    amount=float(r.amount) if r.amount is not None else None,
                )
            )
        else:
            fill_close = last_close if last_close is not None else 0.0
            result.append(
                IntradayKlineData(
                    ts_code=ts_code,
                    datetime=f"{date_str} {time_str}:00",
                    period="1",
                    open=fill_close,
                    high=fill_close,
                    low=fill_close,
                    close=fill_close,
                    volume=None,
                    amount=None,
                )
            )

    return result


def _get_intraday_from_db(ts_code: str, trade_date=None, min_count: int = 240) -> list[IntradayKlineData] | None:
    """从数据库读取指定（或最近）交易日的完整分时数据，返回补齐后的列表；数据不足则返回 None。"""
    db = SessionLocal()
    try:
        if trade_date:
            target_date = trade_date
        else:
            target_date = db.execute(
                select(StockIntraday.trade_date)
                .where(StockIntraday.ts_code == ts_code)
                .order_by(StockIntraday.trade_date.desc())
                .limit(1)
            ).scalar_one_or_none()

        if target_date is None:
            return None

        rows = (
            db.execute(
                select(StockIntraday)
                .where(StockIntraday.ts_code == ts_code)
                .where(StockIntraday.trade_date == target_date)
                .order_by(StockIntraday.trade_time)
            )
            .scalars()
            .all()
        )

        if len(rows) < min_count:
            return None

        return _fill_intraday_gaps(rows, ts_code, target_date)
    finally:
        db.close()


def _fetch_intraday_from_akshare(
    ts_code: str, symbol: str, period: str, limit: int
) -> list[IntradayKlineData]:
    """通过 akshare 新浪分钟线接口拉取最新一天的分时 K 线。"""
    import akshare as ak

    df = ak.stock_zh_a_minute(symbol=symbol, period=period, adjust="")
    if df is None or df.empty:
        return []

    # 只保留最新一天的数据（解决跨日混合问题）
    df = df.sort_values("day", ascending=True).reset_index(drop=True)
    if "day" in df.columns and len(df) > 0:
        # day 格式: "2026-07-10 09:31:00"
        df["_date"] = df["day"].str[:10]
        latest_day = df["_date"].iloc[-1]
        df = df[df["_date"] == latest_day].drop(columns=["_date"])

    result = []
    for _, row in df.tail(limit).iterrows():
        result.append(
            IntradayKlineData(
                ts_code=ts_code,
                datetime=str(row["day"]),
                period=period,
                open=float(row["open"]) if row["open"] is not None else 0.0,
                high=float(row["high"]) if row["high"] is not None else 0.0,
                low=float(row["low"]) if row["low"] is not None else 0.0,
                close=float(row["close"]) if row["close"] is not None else 0.0,
                volume=float(row["volume"]) if "volume" in row and row["volume"] is not None else None,
                amount=float(row["amount"]) if "amount" in row and row["amount"] is not None else None,
            )
        )
    return result


def get_intraday_klines(code: str, period: str = "1", limit: int = 241, trade_date=None) -> list[IntradayKlineData]:
    """获取分钟 K 线。

    - trade_date 指定时：只返回该日数据（从 DB）
    - trade_date 不指定时：优先取最新交易日数据；盘中 DB 未同步当天数据时，走 akshare 实时拉取
    """
    if settings.mock_stock_data:
        return _mock_intraday_klines(code, period=period, limit=limit)

    ts_code = _normalize_code(code)
    symbol = _akshare_symbol(code)

    # 指定了日期 → 直接读 DB
    if trade_date:
        db_data = _get_intraday_from_db(ts_code, trade_date=trade_date, min_count=100)
        if db_data:
            return db_data[:limit]
        return []

    cache_key = f"stock:intraday:{ts_code}:{period}"

    # 优先读 Redis 缓存，但先校验格式（防止旧版脏缓存长期生效）
    cached = redis_client.get(cache_key)
    if cached and isinstance(cached, list) and _is_valid_intraday_cache(cached, period):
        return [IntradayKlineData(**item) for item in cached[:limit]]

    # 1 分钟线优先读数据库：历史/已收盘数据是完整 241 条
    db_data = None
    if period == "1":
        db_data = _get_intraday_from_db(ts_code, min_count=240)

    today_str = datetime.now().strftime("%Y-%m-%d")
    db_is_today = db_data and db_data[-1].datetime.startswith(today_str)

    # 数据库已有今天完整数据 → 直接返回
    if db_is_today:
        ttl = _intraday_cache_ttl(db_data[-1].datetime)
        redis_client.set(cache_key, [r.model_dump() for r in db_data], ex=ttl)
        return db_data[:limit]

    # 盘中或数据库无今天数据时，优先走 akshare 实时拉取最新一天
    try:
        live_data = _fetch_intraday_from_akshare(ts_code, symbol, period, limit)
        if live_data:
            ttl = _intraday_cache_ttl(live_data[-1].datetime)
            redis_client.set(cache_key, [r.model_dump() for r in live_data], ex=ttl)
            return live_data
    except Exception:
        # akshare 拉取失败时，有历史数据则降级返回历史，否则继续抛异常
        if db_data:
            pass
        else:
            raise

    # 无今天数据且 akshare 失败/无数据，但数据库有历史数据 → 降级返回历史
    if db_data:
        ttl = _intraday_cache_ttl(db_data[-1].datetime)
        redis_client.set(cache_key, [r.model_dump() for r in db_data], ex=ttl)
        return db_data[:limit]

    return []


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
                select(
                    StockBasic.ts_code,
                    StockBasic.symbol,
                    StockBasic.name,
                    StockBasic.cnspell,
                    StockBasic.area,
                    StockBasic.industry,
                    StockBasic.fullname,
                    StockBasic.enname,
                    StockBasic.market,
                    StockBasic.exchange,
                    StockBasic.list_status,
                    StockBasic.list_date,
                    StockBasic.is_hs,
                    StockBasic.province,
                    StockBasic.city,
                    StockBasic.introduction,
                    StockBasic.main_business,
                    StockBasic.website,
                    StockBasic.chairman,
                    StockBasic.reg_capital,
                    StockBasic.setup_date,
                    StockBasic.employees,
                )
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
                "area": row["area"],
                "industry": row["industry"],
                "fullname": row["fullname"],
                "enname": row["enname"],
                "market": row["market"],
                "exchange": row["exchange"],
                "list_status": row["list_status"],
                "list_date": row["list_date"].strftime("%Y-%m-%d") if row["list_date"] else None,
                "is_hs": row["is_hs"],
                "province": row["province"],
                "city": row["city"],
                "introduction": row["introduction"],
                "main_business": row["main_business"],
                "website": row["website"],
                "chairman": row["chairman"],
                "reg_capital": row["reg_capital"],
                "setup_date": row["setup_date"].strftime("%Y-%m-%d") if row["setup_date"] else None,
                "employees": row["employees"],
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
# 个股资金流向 / 沪深港通 / 指数 / 涨跌停 / 龙虎榜 / THS 指数
# ---------------------------------------------------------------------------


def get_stock_moneyflow(code: str, limit: int = 30) -> list[dict]:
    """获取个股资金流向。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(StockMoneyflow)
                .where(StockMoneyflow.ts_code == ts_code)
                .order_by(StockMoneyflow.trade_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "buy_sm_amount": float(r.buy_sm_amount) if r.buy_sm_amount else None,
                "sell_sm_amount": float(r.sell_sm_amount) if r.sell_sm_amount else None,
                "buy_md_amount": float(r.buy_md_amount) if r.buy_md_amount else None,
                "sell_md_amount": float(r.sell_md_amount) if r.sell_md_amount else None,
                "buy_lg_amount": float(r.buy_lg_amount) if r.buy_lg_amount else None,
                "sell_lg_amount": float(r.sell_lg_amount) if r.sell_lg_amount else None,
                "buy_elg_amount": float(r.buy_elg_amount) if r.buy_elg_amount else None,
                "sell_elg_amount": float(r.sell_elg_amount) if r.sell_elg_amount else None,
                "net_mf_amount": float(r.net_mf_amount) if r.net_mf_amount else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_moneyflow_hsgt(start_date: str | None = None, end_date: str | None = None, limit: int = 30) -> list[dict]:
    """获取沪深港通资金流向。"""
    db = SessionLocal()
    try:
        query = select(MoneyflowHsgt).order_by(MoneyflowHsgt.trade_date.desc())

        if start_date:
            d = datetime.strptime(start_date, "%Y%m%d").date()
            query = query.where(MoneyflowHsgt.trade_date >= d)
        if end_date:
            d = datetime.strptime(end_date, "%Y%m%d").date()
            query = query.where(MoneyflowHsgt.trade_date <= d)

        rows = db.execute(query.limit(limit)).scalars().all()

        return [
            {
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "ggt_ss": float(r.ggt_ss) if r.ggt_ss else None,
                "ggt_sz": float(r.ggt_sz) if r.ggt_sz else None,
                "hgt": float(r.hgt) if r.hgt else None,
                "sgt": float(r.sgt) if r.sgt else None,
                "north_money": float(r.north_money) if r.north_money else None,
                "south_money": float(r.south_money) if r.south_money else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_index_daily(code: str, limit: int = 30) -> list[dict]:
    """获取指数日线行情。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(IndexDaily)
                .where(IndexDaily.ts_code == ts_code)
                .order_by(IndexDaily.trade_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "open": float(r.open) if r.open else None,
                "high": float(r.high) if r.high else None,
                "low": float(r.low) if r.low else None,
                "close": float(r.close) if r.close else None,
                "pre_close": float(r.pre_close) if r.pre_close else None,
                "change": float(r.change) if r.change else None,
                "pct_chg": float(r.pct_chg) if r.pct_chg else None,
                "vol": float(r.vol) if r.vol else None,
                "amount": float(r.amount) if r.amount else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_stock_limit(trade_date: str | None = None, limit: int = 100) -> list[dict]:
    """获取涨跌停股票列表。"""
    db = SessionLocal()
    try:
        query = select(StockLimit)

        if trade_date:
            d = datetime.strptime(trade_date, "%Y%m%d").date()
            query = query.where(StockLimit.trade_date == d)
        else:
            latest_date = db.execute(
                select(StockLimit.trade_date).order_by(StockLimit.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
            if latest_date is None:
                return []
            query = query.where(StockLimit.trade_date == latest_date)

        rows = db.execute(query.limit(limit)).scalars().all()

        return [
            {
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "ts_code": r.ts_code,
                "up_limit": float(r.up_limit) if r.up_limit else None,
                "down_limit": float(r.down_limit) if r.down_limit else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_top_list(trade_date: str | None = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
    """获取龙虎榜每日明细（支持分页）。

    Returns:
        (items, total)
    """
    db = SessionLocal()
    try:
        query = select(TopList).order_by(TopList.net_amount.desc())

        if trade_date:
            d = datetime.strptime(trade_date, "%Y%m%d").date()
            query = query.where(TopList.trade_date == d)
        else:
            latest_date = db.execute(
                select(TopList.trade_date).order_by(TopList.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
            if latest_date is None:
                return [], 0
            query = query.where(TopList.trade_date == latest_date)

        # 总条数
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar() or 0

        rows = db.execute(query.limit(limit).offset(offset)).scalars().all()

        items = [
            {
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "ts_code": r.ts_code,
                "name": r.name,
                "close": float(r.close) if r.close else None,
                "pct_change": float(r.pct_change) if r.pct_change else None,
                "turnover_rate": float(r.turnover_rate) if r.turnover_rate else None,
                "amount": float(r.amount) if r.amount else None,
                "net_amount": float(r.net_amount) if r.net_amount else None,
                "net_rate": float(r.net_rate) if r.net_rate else None,
                "reason": r.reason,
            }
            for r in rows
        ]
        return items, total
    finally:
        db.close()


def get_ths_index_list(limit: int = 1000) -> list[dict]:
    """获取同花顺指数列表。"""
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(ThsIndex)
                .order_by(ThsIndex.ts_code)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {
                "ts_code": r.ts_code,
                "name": r.name,
                "count": int(r.count) if r.count is not None else None,
                "type": r.type,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_ths_daily(code: str, limit: int = 30) -> list[dict]:
    """获取同花顺指数日线行情。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(ThsDaily)
                .where(ThsDaily.ts_code == ts_code)
                .order_by(ThsDaily.trade_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "open": float(r.open) if r.open else None,
                "high": float(r.high) if r.high else None,
                "low": float(r.low) if r.low else None,
                "close": float(r.close) if r.close else None,
                "pre_close": float(r.pre_close) if r.pre_close else None,
                "pct_change": float(r.pct_change) if r.pct_change else None,
                "vol": float(r.vol) if r.vol else None,
                "turnover_rate": float(r.turnover_rate) if r.turnover_rate else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def get_ths_member(
    code: str,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "con_code",
    sort_order: str = "asc",
    board: str | None = None,
) -> list[dict]:
    """获取同花顺指数成分股，支持分页、排序、板块筛选，并附带最新交易日涨跌幅。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        # 板块分类表达式（SQL 层面）
        board_expr = case(
            (ThsMember.con_name.ilike("%ST%"), "st"),
            (ThsMember.con_code.like("688%"), "star"),
            (
                (ThsMember.con_code.like("300%")) | (ThsMember.con_code.like("301%")),
                "chuang",
            ),
            (
                (ThsMember.con_code.like("8%"))
                | (ThsMember.con_code.like("4%"))
                | (ThsMember.con_code.like("920%")),
                "bj",
            ),
            (
                (ThsMember.con_code.like("60%"))
                | (ThsMember.con_code.like("00%"))
                | (ThsMember.con_code.like("001%")),
                "main",
            ),
            else_="other",
        ).label("board")

        # 子查询：取每只股票最新交易日的涨跌幅
        latest_pct_sub = (
            select(
                StockDaily.ts_code.label("sd_ts_code"),
                StockDaily.pct_chg.label("sd_pct_chg"),
                func.row_number()
                .over(partition_by=StockDaily.ts_code, order_by=StockDaily.trade_date.desc())
                .label("rn"),
            )
            .where(
                StockDaily.ts_code.in_(
                    select(ThsMember.con_code).where(ThsMember.ts_code == ts_code)
                )
            )
            .subquery()
        )

        # 构建排序列
        sort_column = ThsMember.con_code
        if sort_by == "con_name":
            sort_column = ThsMember.con_name
        elif sort_by == "pct_change":
            sort_column = latest_pct_sub.c.sd_pct_chg

        sort_expr = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        offset = (page - 1) * page_size

        query = (
            select(ThsMember, latest_pct_sub.c.sd_pct_chg, board_expr)
            .where(ThsMember.ts_code == ts_code)
            .outerjoin(
                latest_pct_sub,
                (ThsMember.con_code == latest_pct_sub.c.sd_ts_code)
                & (latest_pct_sub.c.rn == 1),
            )
        )

        if board and board != "all":
            query = query.where(board_expr == board)

        query = query.order_by(sort_expr).offset(offset).limit(page_size)

        rows = db.execute(query).all()

        return [
            {
                "ts_code": member.ts_code,
                "con_code": member.con_code,
                "con_name": member.con_name,
                "pct_change": round(float(pct_chg), 2) if pct_chg is not None else None,
                "board": board_value,
            }
            for member, pct_chg, board_value in rows
        ]
    finally:
        db.close()


def get_top_inst(trade_date: str | None = None, ts_code: str | None = None, limit: int = 100) -> list[dict]:
    """获取龙虎榜机构明细。"""
    db = SessionLocal()
    try:
        query = select(TopInst).order_by(TopInst.trade_date.desc(), TopInst.net_buy.desc())

        if trade_date:
            d = datetime.strptime(trade_date, "%Y%m%d").date()
            query = query.where(TopInst.trade_date == d)
        if ts_code:
            query = query.where(TopInst.ts_code == _normalize_code(ts_code))

        rows = db.execute(query.limit(limit)).scalars().all()

        return [
            {
                "trade_date": r.trade_date.strftime("%Y%m%d") if r.trade_date else "",
                "ts_code": r.ts_code,
                "exalter": r.exalter,
                "buy": float(r.buy) if r.buy else None,
                "buy_rate": float(r.buy_rate) if r.buy_rate else None,
                "sell": float(r.sell) if r.sell else None,
                "sell_rate": float(r.sell_rate) if r.sell_rate else None,
                "net_buy": float(r.net_buy) if r.net_buy else None,
                "side": r.side,
                "reason": r.reason,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 股票概念/题材
# ---------------------------------------------------------------------------


def get_stock_concepts(code: str) -> list[dict]:
    """获取某只股票所属的全部概念/题材板块。"""
    from app.models.stock import StockConcept

    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(StockConcept)
                .where(StockConcept.ts_code == ts_code)
                .where(StockConcept.out_date.is_(None))  # 只取当前有效的
                .order_by(StockConcept.in_date.desc())
            )
            .scalars()
            .all()
        )

        return [
            {
                "concept_id": r.concept_id,
                "concept_name": r.concept_name,
                "ts_code": r.ts_code,
                "name": r.name,
                "in_date": r.in_date.strftime("%Y%m%d") if r.in_date else None,
                "out_date": r.out_date.strftime("%Y%m%d") if r.out_date else None,
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
        {
            "code": ts_code.split(".")[0],
            "name": _mock_name(ts_code),
            "cnspell": None,
            "area": "深圳" if ts_code.endswith(".SZ") else ("上海" if ts_code.endswith(".SH") else "香港"),
            "industry": "白酒" if "600519" in ts_code else "银行",
            "fullname": _mock_name(ts_code) + "股份有限公司",
            "enname": None,
            "market": "主板",
            "exchange": "SZSE" if ts_code.endswith(".SZ") else ("SSE" if ts_code.endswith(".SH") else "HKEX"),
            "list_status": "L",
            "list_date": "2000-01-01",
            "is_hs": None,
            "province": "广东" if ts_code.endswith(".SZ") else ("上海" if ts_code.endswith(".SH") else "香港"),
            "city": "深圳" if ts_code.endswith(".SZ") else ("上海" if ts_code.endswith(".SH") else "香港"),
            "introduction": f"{_mock_name(ts_code)}是一家优秀的上市公司。",
            "main_business": "主营业务示例",
            "website": "https://example.com",
            "chairman": "张三",
            "reg_capital": "100亿元",
            "setup_date": "1990-01-01",
            "employees": 10000,
        }
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


def _mock_intraday_klines(code: str, period: str = "1", limit: int = 240) -> list[IntradayKlineData]:
    """Mock 环境下生成分钟级 K 线。"""
    import random

    ts_code = _normalize_code(code)
    today = datetime.now().replace(hour=9, minute=31, second=0, microsecond=0)
    price = Decimal(str(random.uniform(10, 200)))
    result = []
    minutes = int(period) if period.isdigit() else 1

    for i in range(min(limit, 240)):
        dt = today - timedelta(minutes=i * minutes)
        change = Decimal(str(random.uniform(-0.01, 0.01)))
        open_p = price
        close = price * (Decimal("1") + change)
        high = max(open_p, close) * (Decimal("1") + Decimal(str(random.uniform(0, 0.005))))
        low = min(open_p, close) * (Decimal("1") - Decimal(str(random.uniform(0, 0.005))))
        volume = Decimal(str(random.uniform(1000, 100000)))
        result.append(
            IntradayKlineData(
                ts_code=ts_code,
                datetime=dt.strftime("%Y-%m-%d %H:%M:%S"),
                period=period,
                open=float(open_p),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
                amount=float(volume * close),
            )
        )
        price = close

    return result
