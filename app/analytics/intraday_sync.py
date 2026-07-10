"""全市场分时K线数据采集与存储。

直接请求东方财富分时接口（绕过系统代理），获取全A股当日 1 分钟 K 线。
数据用于概念资金流聚合、盘中动态分析、iOS 动画展示。

表设计：stock_intraday（主键: ts_code + trade_date + trade_time）
每天约 5000 股 × 240 分钟 = 120 万条。
自动清理 3 个月前的数据。
"""

import logging
import time as _time
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Date, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import insert

from app.db.base import Base, SessionLocal

logger = logging.getLogger(__name__)


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
# 东方财富分时接口
# ============================================================

_EM_TRENDS_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
_EM_PARAMS_BASE = {
    "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
    "ut": "7eea3edcaed734bea9cbfc24409ed989",
    "ndays": "1",
    "iscr": "0",
}


def _get_secid(ts_code: str) -> str:
    """Tushare 代码转东财 secid。
    000001.SZ -> 0.000001 (深)
    600519.SH -> 1.600519 (沪)
    """
    parts = ts_code.split(".")
    if len(parts) != 2:
        return ""
    code, market = parts
    if market == "SZ":
        return f"0.{code}"
    elif market == "SH":
        return f"1.{code}"
    elif market == "BJ":
        return f"0.{code}"
    return ""


def _fetch_intraday_one(client, ts_code: str, trade_date: date) -> list[dict]:
    """从东方财富获取单只股票的分时数据。"""
    secid = _get_secid(ts_code)
    if not secid:
        return []

    params = {**_EM_PARAMS_BASE, "secid": secid}
    try:
        r = client.get(_EM_TRENDS_URL, params=params)
        if r.status_code != 200:
            return []
        data = r.json()
        trends = data.get("data", {}).get("trends", [])
        if not trends:
            return []
    except Exception as e:
        return []

    records = []
    for trend in trends:
        # 格式: "2026-07-10 09:30,price,open,high,low,volume,amount,avg"
        parts = trend.split(",")
        if len(parts) < 7:
            continue
        try:
            dt_str = parts[0]  # "2026-07-10 09:30"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if dt.date() != trade_date:
                continue
            records.append({
                "ts_code": ts_code,
                "trade_date": trade_date,
                "trade_time": dt.strftime("%H:%M"),
                "open": float(parts[2]) if parts[2] else None,
                "close": float(parts[1]) if parts[1] else None,
                "high": float(parts[3]) if parts[3] else None,
                "low": float(parts[4]) if parts[4] else None,
                "volume": int(float(parts[5])) if parts[5] else None,
                "amount": float(parts[6]) if parts[6] else None,
            })
        except (ValueError, IndexError):
            continue

    return records


def _print(msg: str):
    """打印到 stdout 并 flush（确保控制台实时输出）。"""
    print(msg, flush=True)
    logger.info(msg)


# ============================================================
# 同步函数
# ============================================================


def sync_all_intraday(trade_date: Optional[date] = None, batch_size: int = 100):
    """同步全A股当日分时K线数据。

    使用 httpx 直接请求东方财富（绕过系统代理），并发控制避免封IP。

    Args:
        trade_date: 交易日期，默认今天
        batch_size: 每批写入数据库的股票数

    Returns:
        {"total_stocks": N, "total_records": M, "elapsed": S}
    """
    import httpx

    if trade_date is None:
        trade_date = date.today()

    _ensure_table()

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
    _print(f"[Intraday] 开始采集 {len(all_codes)} 只股票分时数据 ({trade_date})")

    # 先测试第一只股票确认网络正常
    _print(f"  测试网络: {all_codes[0]}...")
    test_client = httpx.Client(proxy=None, trust_env=False, timeout=8, follow_redirects=True)
    test_records = _fetch_intraday_one(test_client, all_codes[0], trade_date)
    test_client.close()
    if not test_records:
        _print(f"  [ERROR] 网络测试失败，无法获取 {all_codes[0]} 的分时数据。")
        _print(f"  可能原因：网络不通/代理干扰/非交易日/盘前无数据")
        return {"total_stocks": 0, "total_records": 0, "elapsed": 0}
    _print(f"  网络OK! {all_codes[0]} 获取到 {len(test_records)} 条分时数据")

    start_time = _time.time()
    total_records = 0
    processed = 0
    errors = 0
    consecutive_errors = 0

    # httpx client 绕过代理
    client = httpx.Client(proxy=None, trust_env=False, timeout=8, follow_redirects=True)

    try:
        batch_records = []

        for ts_code in all_codes:
            records = _fetch_intraday_one(client, ts_code, trade_date)
            if records:
                batch_records.extend(records)
                consecutive_errors = 0
            else:
                errors += 1
                consecutive_errors += 1
                # 连续失败太多，可能被限流，等一等
                if consecutive_errors >= 10:
                    _print(f"  [!] 连续 {consecutive_errors} 个失败，等待 5 秒...")
                    _time.sleep(5)
                    consecutive_errors = 0

            processed += 1

            # 每批写入数据库
            if len(batch_records) >= batch_size * 240:
                _bulk_upsert(batch_records)
                total_records += len(batch_records)
                batch_records = []

            # 限速：每秒约 5-8 个请求
            if processed % 5 == 0:
                _time.sleep(0.2)

            # 进度
            if processed % 100 == 0:
                elapsed = int(_time.time() - start_time)
                rate = processed / max(elapsed, 1)
                eta = int((len(all_codes) - processed) / max(rate, 0.1))
                _print(f"  进度: {processed}/{len(all_codes)} | {total_records + len(batch_records)} 条 | {elapsed}s | ETA {eta}s | 错误 {errors}")

        # 写入剩余
        if batch_records:
            _bulk_upsert(batch_records)
            total_records += len(batch_records)

    finally:
        client.close()

    elapsed = int(_time.time() - start_time)
    _print(f"[Intraday] 完成! {processed} 股, {total_records} 条, 耗时 {elapsed}s, {errors} 错误")

    # 清理3个月前的数据
    _cleanup_old_data(months=3)

    return {"total_stocks": processed, "total_records": total_records, "elapsed": elapsed}


def sync_intraday_by_concepts(concept_ids: list[str], trade_date: Optional[date] = None) -> int:
    """只同步指定概念的成分股分时数据（更快）。"""
    import httpx

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

    client = httpx.Client(proxy=None, trust_env=False, timeout=10, follow_redirects=True)
    all_records = []
    try:
        for ts_code in stock_codes:
            records = _fetch_intraday_one(client, ts_code, trade_date)
            if records:
                all_records.extend(records)
            if len(all_records) > 50000:
                _bulk_upsert(all_records)
                all_records = []
            _time.sleep(0.15)
    finally:
        client.close()

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


def _cleanup_old_data(months: int = 3):
    """清理 N 个月前的分时数据。"""
    cutoff = date.today() - timedelta(days=months * 30)
    db = SessionLocal()
    try:
        result = db.execute(
            text("DELETE FROM stock_intraday WHERE trade_date < :cutoff"),
            {"cutoff": cutoff}
        )
        db.commit()
        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"[Intraday] 清理 {cutoff} 之前的数据: {deleted} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Intraday] 清理失败: {e}")
    finally:
        db.close()
