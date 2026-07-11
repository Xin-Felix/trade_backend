"""全市场分时K线数据采集与存储。

通过 Tushare 代理（stk_mins 接口，直接 HTTP POST）获取全A股 1 分钟 K 线。
数据用于概念资金流聚合、盘中动态分析、iOS 动画展示。

表设计：stock_intraday（主键: ts_code + trade_date + trade_time）
每天约 5000 股 × 240 分钟 = 120 万条。
仅保留最近 5 个交易日的数据。
"""

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Optional

import requests as _requests
from sqlalchemy import Column, Date, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.base import Base, SessionLocal

logger = logging.getLogger(__name__)

# 并发线程数（4 线程是最佳平衡：100% 成功率，不会被限流）
_MAX_WORKERS = 4


# ============================================================
# 模型
# ============================================================


class StockIntraday(Base):
    """股票分时K线（1分钟）"""

    __tablename__ = "stock_intraday"

    ts_code = Column(String(20), primary_key=True, comment="股票代码")
    trade_date = Column(Date, primary_key=True, comment="交易日期")
    trade_time = Column(String(5), primary_key=True, comment="时间 HH:MM")
    open = Column(Numeric(12, 4), nullable=True, comment="开盘价")
    close = Column(Numeric(12, 4), nullable=True, comment="收盘价")
    high = Column(Numeric(12, 4), nullable=True, comment="最高价")
    low = Column(Numeric(12, 4), nullable=True, comment="最低价")
    volume = Column(Numeric(20, 0), nullable=True, comment="成交量")
    amount = Column(Numeric(20, 4), nullable=True, comment="成交额(元)")

    __table_args__ = (
        Index("idx_intraday_date", "trade_date"),
        Index("idx_intraday_code_date", "ts_code", "trade_date"),
    )


# ============================================================
# Tushare 代理接口（直接 HTTP，带超时）
# ============================================================


def _get_proxy_config() -> tuple:
    """返回 (proxy_url, proxy_token)。"""
    url = settings.tushare_proxy_url or "https://tx.xiaodefa.top/"
    token = settings.tushare_proxy_token or settings.tushare_token
    return url, token


def _call_tushare(api_name: str, timeout: int = 15, **params) -> list[dict]:
    """直接 POST 调用 Tushare 代理，返回记录列表（带超时保护）。

    Returns:
        [{"field1": val1, ...}, ...] 或空列表
    """
    url, token = _get_proxy_config()
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": "",
    }
    try:
        r = _requests.post(url, json=payload, timeout=(5, timeout))
        data = r.json()
        if data.get("code") != 0:
            return []
        raw = data.get("data")
        if not raw:
            return []
        fields = raw.get("fields", [])
        items = raw.get("items", [])
        return [dict(zip(fields, row)) for row in items]
    except Exception:
        return []


def _fetch_intraday_one(ts_code: str, start_dt: str, end_dt: str) -> list[dict]:
    """通过 Tushare stk_mins 获取单只股票的分时数据。

    Args:
        ts_code: 股票代码，如 "000001.SZ"
        start_dt: 开始时间，如 "2026-07-07 09:30:00"
        end_dt: 结束时间，如 "2026-07-11 15:00:00"

    Returns:
        记录列表，每条包含 ts_code/trade_date/trade_time/open/close/high/low/volume/amount
    """
    rows = _call_tushare(
        "stk_mins",
        timeout=15,
        ts_code=ts_code,
        freq="1min",
        start_date=start_dt,
        end_date=end_dt,
    )
    if not rows:
        return []

    records = []
    for row in rows:
        try:
            # trade_time 格式: "2026-07-10 09:30:00"
            dt = datetime.strptime(row["trade_time"], "%Y-%m-%d %H:%M:%S")
            records.append({
                "ts_code": ts_code,
                "trade_date": dt.date(),
                "trade_time": dt.strftime("%H:%M"),
                "open": float(row["open"]) if row.get("open") is not None else None,
                "close": float(row["close"]) if row.get("close") is not None else None,
                "high": float(row["high"]) if row.get("high") is not None else None,
                "low": float(row["low"]) if row.get("low") is not None else None,
                "volume": int(float(row["vol"])) if row.get("vol") is not None else None,
                "amount": float(row["amount"]) if row.get("amount") is not None else None,
            })
        except (ValueError, KeyError):
            continue

    # 数据清洗：去重 + 补齐缺失分钟
    records = _normalize_records(records, ts_code)
    return records


def _normalize_records(records: list[dict], ts_code: str) -> list[dict]:
    """去重 + 补齐缺失分钟数据。

    A股交易时段：09:30-11:30 (120分钟) + 13:00-15:00 (120分钟) = 240 分钟
    - 重复的同一分钟：保留最后一条（后者覆盖前者）
    - 缺失的分钟：用前后相邻分钟的均值插值

    只在单天数据上处理，跨天数据各自独立处理。
    """
    if not records:
        return []

    # 按交易日分组
    by_date = {}
    for r in records:
        td = r["trade_date"]
        if td not in by_date:
            by_date[td] = []
        by_date[td].append(r)

    result = []
    for td, day_records in by_date.items():
        normalized = _normalize_day(day_records, ts_code, td)
        result.extend(normalized)

    return result


# A股完整的交易时间列表（HH:MM）
_MARKET_MINUTES = None


def _get_market_minutes() -> list[str]:
    """生成A股 241 个交易分钟时刻列表（含15:00收盘线）。"""
    global _MARKET_MINUTES
    if _MARKET_MINUTES is not None:
        return _MARKET_MINUTES

    minutes = []
    # 上午：09:30 ~ 11:29（共 120 分钟）
    for h in range(9, 12):
        start_m = 30 if h == 9 else 0
        end_m = 30 if h == 11 else 60
        for m in range(start_m, end_m):
            minutes.append(f"{h:02d}:{m:02d}")
    # 下午：13:00 ~ 15:00（共 121 分钟，含收盘线）
    for h in range(13, 15):
        for m in range(0, 60):
            minutes.append(f"{h:02d}:{m:02d}")
    minutes.append("15:00")

    _MARKET_MINUTES = minutes
    return minutes


def _normalize_day(day_records: list[dict], ts_code: str, trade_date) -> list[dict]:
    """对单天数据去重 + 插值补齐。"""
    # 1. 去重：同一分钟保留最后一条
    by_time = {}
    for r in day_records:
        by_time[r["trade_time"]] = r

    market_minutes = _get_market_minutes()

    # 如果数据太少（<30条），说明可能是停牌或数据异常，不补齐直接返回
    if len(by_time) < 30:
        return list(by_time.values())

    # 2. 补齐缺失分钟
    # 先按时间顺序排好已有数据
    sorted_times = sorted(by_time.keys())
    # 只补齐已有数据范围内的缺口（不补齐前后的空白，比如集合竞价的差异）
    first_time = sorted_times[0]
    last_time = sorted_times[-1]

    try:
        start_idx = market_minutes.index(first_time)
        end_idx = market_minutes.index(last_time)
    except ValueError:
        # 时间不在标准列表中，直接返回去重后的数据
        return list(by_time.values())

    result = []
    for idx in range(start_idx, end_idx + 1):
        t = market_minutes[idx]
        if t in by_time:
            result.append(by_time[t])
        else:
            # 插值：找前后最近的有效数据取均值
            interpolated = _interpolate(t, idx, market_minutes, by_time, ts_code, trade_date)
            if interpolated:
                result.append(interpolated)

    return result


def _interpolate(
    missing_time: str,
    missing_idx: int,
    market_minutes: list[str],
    existing: dict,
    ts_code: str,
    trade_date,
) -> dict:
    """用前后相邻分钟的数据均值填充缺失分钟。"""
    # 向前找最近的有效数据
    prev = None
    for i in range(missing_idx - 1, -1, -1):
        t = market_minutes[i]
        if t in existing:
            prev = existing[t]
            break

    # 向后找最近的有效数据
    nxt = None
    for i in range(missing_idx + 1, len(market_minutes)):
        t = market_minutes[i]
        if t in existing:
            nxt = existing[t]
            break

    if prev is None and nxt is None:
        return None

    # 取可用的参考数据
    ref_a = prev or nxt
    ref_b = nxt or prev

    def _avg(a, b):
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return round((a + b) / 2, 4)

    return {
        "ts_code": ts_code,
        "trade_date": trade_date,
        "trade_time": missing_time,
        "open": _avg(ref_a.get("open"), ref_b.get("open")),
        "close": _avg(ref_a.get("close"), ref_b.get("close")),
        "high": _avg(ref_a.get("high"), ref_b.get("high")),
        "low": _avg(ref_a.get("low"), ref_b.get("low")),
        "volume": 0,  # 缺失分钟成交量设为0
        "amount": 0,  # 缺失分钟成交额设为0
    }


def _get_recent_trade_dates(n: int = 5) -> list[str]:
    """获取最近 N 个交易日列表（从今天往回找）。"""
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=n * 3)).strftime("%Y%m%d")
    rows = _call_tushare(
        "trade_cal",
        timeout=10,
        exchange="SSE",
        start_date=start,
        end_date=end,
        is_open="1",
    )
    if not rows:
        logger.error("[Intraday] 获取交易日历失败")
        return []
    dates = sorted([r["cal_date"] for r in rows], reverse=True)[:n]
    return dates


def _print(msg: str):
    """打印到 stdout 并 flush（确保控制台实时输出）。"""
    print(msg, flush=True)
    logger.info(msg)


# ============================================================
# 同步函数
# ============================================================


def sync_all_intraday(trade_date: Optional[date] = None, days: int = 5):
    """同步全A股分时K线数据（最近 N 个交易日）。

    使用 Tushare 代理 stk_mins 接口，4 线程并发采集。

    Args:
        trade_date: 结束日期，默认今天（会自动往前取 N 个交易日）
        days: 拉取最近几个交易日的数据，默认 5

    Returns:
        {"total_stocks": N, "total_records": M, "elapsed": S}
    """
    if trade_date is None:
        trade_date = date.today()

    _ensure_table()

    # 获取最近交易日
    trade_dates = _get_recent_trade_dates(n=days)
    if not trade_dates:
        _print("[Intraday] 无法获取交易日历，退出")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}

    # 计算时间范围
    earliest_date = min(trade_dates)
    latest_date = max(trade_dates)
    start_dt = f"{earliest_date[:4]}-{earliest_date[4:6]}-{earliest_date[6:]} 09:30:00"
    end_dt = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]} 15:00:00"

    _print(f"={'=' * 59}")
    _print(f"  全市场分时K线采集")
    _print(f"  交易日范围: {earliest_date} ~ {latest_date} ({len(trade_dates)} 个交易日)")
    _print(f"  数据源: Tushare 代理 (stk_mins)")
    _print(f"  并发: {_MAX_WORKERS} 线程")
    _print(f"={'=' * 59}")

    # 获取所有A股代码
    db = SessionLocal()
    try:
        codes = db.execute(
            text("SELECT ts_code FROM stock_basic ORDER BY ts_code")
        ).fetchall()
        all_codes = [row[0] for row in codes]
    finally:
        db.close()

    if not all_codes:
        _print("[Intraday] stock_basic 为空")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}

    # 过滤只保留沪深A股（排除北交所8/4开头）
    all_codes = [c for c in all_codes if not c.startswith("8") and not c.startswith("4")]
    _print(f"[Intraday] 开始采集 {len(all_codes)} 只股票")

    # 先测试第一只股票确认代理正常
    _print(f"  测试连接: {all_codes[0]}...")
    test_records = _fetch_intraday_one(all_codes[0], start_dt, end_dt)
    if not test_records:
        _print(f"  [ERROR] 连接测试失败，无法获取 {all_codes[0]} 的分时数据。")
        _print(f"  可能原因：代理不通/Token过期/非交易日无数据")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}
    _print(f"  连接OK! {all_codes[0]} 获取到 {len(test_records)} 条分时数据")

    start_time = _time.time()
    total_records = 0
    processed = 0
    errors = 0
    batch_records = []

    def _worker(ts_code: str):
        return ts_code, _fetch_intraday_one(ts_code, start_dt, end_dt)

    # 使用线程池并发采集
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        # 分批提交避免内存过大
        batch_submit_size = 200
        for batch_start in range(0, len(all_codes), batch_submit_size):
            batch_codes = all_codes[batch_start:batch_start + batch_submit_size]
            futures = {executor.submit(_worker, code): code for code in batch_codes}

            for future in as_completed(futures):
                ts_code, records = future.result()
                processed += 1

                if records:
                    batch_records.extend(records)
                else:
                    errors += 1

                # 每积累 50000 条写入数据库
                if len(batch_records) >= 50000:
                    _bulk_upsert(batch_records)
                    total_records += len(batch_records)
                    batch_records = []

                # 进度
                if processed % 200 == 0:
                    elapsed = int(_time.time() - start_time)
                    rate = processed / max(elapsed, 1)
                    eta = int((len(all_codes) - processed) / max(rate, 0.1))
                    _print(
                        f"  进度: {processed}/{len(all_codes)} | "
                        f"{total_records + len(batch_records)} 条 | "
                        f"{elapsed}s | ETA {eta}s | 错误 {errors}"
                    )

    # 写入剩余
    if batch_records:
        _bulk_upsert(batch_records)
        total_records += len(batch_records)

    elapsed = int(_time.time() - start_time)
    _print(f"[Intraday] 完成! {processed} 股, {total_records} 条, 耗时 {elapsed}s, {errors} 错误")

    # 清理：只保留最近5个交易日的数据
    _cleanup_old_data(keep_days=5)

    return {"total_stocks": processed, "total_records": total_records, "elapsed": elapsed}


def sync_intraday_by_concepts(concept_ids: list[str], trade_date: Optional[date] = None) -> int:
    """只同步指定概念的成分股分时数据（更快）。"""
    if trade_date is None:
        trade_date = date.today()

    _ensure_table()

    # 获取概念成分股
    db = SessionLocal()
    try:
        placeholders = ",".join([f"'{c}'" for c in concept_ids])
        codes = db.execute(
            text(f"SELECT DISTINCT ts_code FROM stock_concept WHERE concept_id IN ({placeholders})")
        ).fetchall()
        stock_codes = [row[0] for row in codes]
    finally:
        db.close()

    if not stock_codes:
        return 0

    stock_codes = [c for c in stock_codes if not c.startswith("8") and not c.startswith("4")]
    logger.info(f"[Intraday] 采集 {len(stock_codes)} 只概念成分股分时 ({trade_date})")

    # 时间范围：当天
    start_dt = f"{trade_date.isoformat()} 09:30:00"
    end_dt = f"{trade_date.isoformat()} 15:00:00"

    all_records = []

    def _worker(ts_code: str):
        return ts_code, _fetch_intraday_one(ts_code, start_dt, end_dt)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_worker, code): code for code in stock_codes}
        for future in as_completed(futures):
            ts_code, records = future.result()
            if records:
                all_records.extend(records)
            if len(all_records) > 50000:
                _bulk_upsert(all_records)
                all_records = []

    if all_records:
        _bulk_upsert(all_records)

    total = len(all_records)
    logger.info(f"[Intraday] 概念成分股采集完成: {total} 条")
    return total


# ============================================================
# 内部函数
# ============================================================


def _ensure_table():
    """确保表存在。"""
    from app.db.base import engine
    StockIntraday.__table__.create(bind=engine, checkfirst=True)


def _bulk_upsert(records: list[dict]):
    """批量写入（upsert）。"""
    if not records:
        return

    db = SessionLocal()
    try:
        # 分批写入避免单语句过大
        chunk_size = 5000
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            # 去重
            seen = {}
            for r in chunk:
                key = (r["ts_code"], r["trade_date"], r["trade_time"])
                seen[key] = r
            chunk = list(seen.values())

            stmt = insert(StockIntraday.__table__).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ts_code", "trade_date", "trade_time"],
                set_={
                    "open": stmt.excluded.open,
                    "close": stmt.excluded.close,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "volume": stmt.excluded.volume,
                    "amount": stmt.excluded.amount,
                },
            )
            db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Intraday] 写入失败: {e}")
    finally:
        db.close()


def _ts_code_to_symbol(ts_code: str) -> str:
    """把 '000001.SZ' 转成 '000001'，供 akshare 使用。"""
    return ts_code.split(".")[0]


def _fetch_intraday_one_akshare(ts_code: str, trade_date: date) -> list[dict]:
    """通过 akshare 获取单只股票指定交易日的 1 分钟分时数据。

    当天盘中数据用 akshare 实时拉取，Tushare 收盘后质量更高。
    """
    import akshare as ak

    symbol = _ts_code_to_symbol(ts_code)
    start_dt = f"{trade_date.isoformat()} 09:30:00"
    end_dt = f"{trade_date.isoformat()} 15:00:00"

    try:
        df = ak.stock_zh_a_hist_min_em(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            period="1",
            adjust="",
        )
    except Exception as e:
        logger.warning(f"[Intraday] akshare 获取 {ts_code} {trade_date} 失败: {e}")
        return []

    if df is None or df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        try:
            dt = datetime.strptime(str(row["时间"]), "%Y-%m-%d %H:%M")
            records.append({
                "ts_code": ts_code,
                "trade_date": dt.date(),
                "trade_time": dt.strftime("%H:%M"),
                "open": float(row["开盘"]) if row.get("开盘") is not None else None,
                "close": float(row["收盘"]) if row.get("收盘") is not None else None,
                "high": float(row["最高"]) if row.get("最高") is not None else None,
                "low": float(row["最低"]) if row.get("最低") is not None else None,
                "volume": int(float(row["成交量"])) if row.get("成交量") is not None else None,
                "amount": float(row["成交额"]) if row.get("成交额") is not None else None,
            })
        except (ValueError, KeyError):
            continue

    return _normalize_records(records, ts_code)


def sync_all_intraday_mixed(days: int = 5) -> dict:
    """同步最近 N 个交易日全 A 股分时数据（混合数据源）。

    - 历史交易日：Tushare 代理 stk_mins
    - 当天：16:00 之前用 akshare，16:00 之后用 Tushare
    - 只保留最近 5 个交易日数据

    Returns:
        {"total_stocks": N, "total_records": M, "elapsed": S}
    """
    _ensure_table()

    trade_dates = _get_recent_trade_dates(n=days)
    if not trade_dates:
        _print("[IntradayMixed] 无法获取交易日历，退出")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}

    today = date.today()
    today_str = today.strftime("%Y%m%d")
    now_time = datetime.now().time()
    use_tushare_today = now_time >= datetime.strptime("16:00", "%H:%M").time()

    # Tushare 覆盖的日期范围：历史日期 + （16:00 以后包含今天）
    tushare_dates = [d for d in trade_dates if d != today_str]
    if use_tushare_today and today_str in trade_dates:
        tushare_dates.append(today_str)

    akshare_dates = []
    if not use_tushare_today and today_str in trade_dates:
        akshare_dates.append(today_str)

    tushare_start_dt = None
    tushare_end_dt = None
    if tushare_dates:
        earliest = min(tushare_dates)
        latest = max(tushare_dates)
        tushare_start_dt = f"{earliest[:4]}-{earliest[4:6]}-{earliest[6:]} 09:30:00"
        tushare_end_dt = f"{latest[:4]}-{latest[4:6]}-{latest[6:]} 15:00:00"

    _print(f"={'=' * 59}")
    _print(f"  全市场分时K线采集（混合源）")
    _print(f"  交易日: {trade_dates}")
    _print(f"  Tushare 覆盖: {tushare_dates or '无'}")
    _print(f"  AKShare 覆盖: {akshare_dates or '无'}")
    _print(f"={'=' * 59}")

    # 获取所有 A 股代码
    db = SessionLocal()
    try:
        codes = db.execute(
            text("SELECT ts_code FROM stock_basic ORDER BY ts_code")
        ).fetchall()
        all_codes = [row[0] for row in codes]
    finally:
        db.close()

    if not all_codes:
        _print("[IntradayMixed] stock_basic 为空")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}

    # 排除北交所
    all_codes = [c for c in all_codes if not c.startswith("8") and not c.startswith("4")]
    _print(f"[IntradayMixed] 开始采集 {len(all_codes)} 只股票")

    start_time = _time.time()
    total_records = 0
    processed = 0
    errors = 0
    batch_records = []

    def _worker(ts_code: str):
        records: list[dict] = []
        if tushare_start_dt and tushare_end_dt:
            records.extend(_fetch_intraday_one(ts_code, tushare_start_dt, tushare_end_dt))
        for td in akshare_dates:
            records.extend(_fetch_intraday_one_akshare(ts_code, today))
        return ts_code, records

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        batch_submit_size = 200
        for batch_start in range(0, len(all_codes), batch_submit_size):
            batch_codes = all_codes[batch_start:batch_start + batch_submit_size]
            futures = {executor.submit(_worker, code): code for code in batch_codes}

            for future in as_completed(futures):
                ts_code, records = future.result()
                processed += 1

                if records:
                    batch_records.extend(records)
                else:
                    errors += 1

                if len(batch_records) >= 50000:
                    _bulk_upsert(batch_records)
                    total_records += len(batch_records)
                    batch_records = []

                if processed % 200 == 0:
                    elapsed = int(_time.time() - start_time)
                    rate = processed / max(elapsed, 1)
                    eta = int((len(all_codes) - processed) / max(rate, 0.1))
                    _print(
                        f"  进度: {processed}/{len(all_codes)} | "
                        f"{total_records + len(batch_records)} 条 | "
                        f"{elapsed}s | ETA {eta}s | 错误 {errors}"
                    )

    if batch_records:
        _bulk_upsert(batch_records)
        total_records += len(batch_records)

    elapsed = int(_time.time() - start_time)
    _print(
        f"[IntradayMixed] 完成! {processed} 股, {total_records} 条, "
        f"耗时 {elapsed}s, {errors} 错误"
    )

    _cleanup_old_data(keep_days=5)

    return {"total_stocks": processed, "total_records": total_records, "elapsed": elapsed}

    """只保留最近 N 个交易日的分时数据，删除更早的。"""
    trade_dates = _get_recent_trade_dates(n=keep_days)
    if not trade_dates:
        # 降级：按自然日清理
        cutoff = date.today() - timedelta(days=keep_days + 3)
        db = SessionLocal()
        try:
            result = db.execute(
                text("DELETE FROM stock_intraday WHERE trade_date < :cutoff"),
                {"cutoff": cutoff},
            )
            db.commit()
            deleted = result.rowcount
            if deleted > 0:
                _print(f"[Intraday] 清理 {cutoff} 之前的数据: {deleted} 条")
        except Exception as e:
            db.rollback()
            logger.error(f"[Intraday] 清理失败: {e}")
        finally:
            db.close()
        return

    # 保留最近 N 个交易日，删除其余
    earliest_keep = min(trade_dates)
    cutoff_date = date(
        int(earliest_keep[:4]), int(earliest_keep[4:6]), int(earliest_keep[6:])
    )
    db = SessionLocal()
    try:
        result = db.execute(
            text("DELETE FROM stock_intraday WHERE trade_date < :cutoff"),
            {"cutoff": cutoff_date},
        )
        db.commit()
        deleted = result.rowcount
        if deleted > 0:
            _print(f"[Intraday] 清理 {cutoff_date} 之前的数据: {deleted} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Intraday] 清理失败: {e}")
    finally:
        db.close()
