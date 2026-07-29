"""AI 市场温度（Market Pulse）服务层。

后端计算温度分数（8 项指标加权），AI 生成一句话总结和热点关键词。
每个交易日生成一条快照，供首页展示。
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.market_pulse import MarketPulse
from app.services import ai_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 温度分数计算
# ---------------------------------------------------------------------------

# 指标权重
WEIGHTS = {
    "up_ratio": 0.15,         # 上涨家数占比
    "amount_change": 0.15,    # 成交额变化
    "north_money": 0.10,      # 北向资金
    "limit_up": 0.15,         # 涨停数量
    "limit_down": 0.10,       # 跌停数量（反向）
    "open_limit_rate": 0.10,  # 炸板率（反向）
    "hot_continuity": 0.15,   # 热点持续性（连续涨停概念数）
    "max_board": 0.10,        # 连板高度
}

# 等级划分
LEVELS = [
    (20, "极弱"),
    (40, "偏弱"),
    (60, "中性"),
    (80, "偏强"),
    (100, "高潮"),
]


def _get_level(score: int) -> str:
    for threshold, label in LEVELS:
        if score <= threshold:
            return label
    return "高潮"


def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(min_val, min(max_val, value))


def compute_market_pulse(trade_date: date | None = None) -> dict:
    """计算指定交易日的市场温度分数和关键指标。

    Returns:
        {
            "score": int,
            "level": str,
            "indicators": {...},  # 原始指标值
            "keywords": [str],    # 热点关键词
        }
    """
    db = SessionLocal()
    try:
        if trade_date is None:
            # 取最新有数据的交易日
            from app.models.stock import StockDaily
            trade_date = db.query(func.max(StockDaily.trade_date)).scalar()
            if trade_date is None:
                return {"score": 50, "level": "中性", "indicators": {}, "keywords": []}

        indicators = _collect_indicators(db, trade_date)
        score = _calculate_score(indicators)
        level = _get_level(score)
        keywords = _extract_hot_keywords(db, trade_date)

        return {
            "trade_date": trade_date,
            "score": score,
            "level": level,
            "indicators": indicators,
            "keywords": keywords,
        }
    finally:
        db.close()


def _collect_indicators(db: Session, trade_date: date) -> dict:
    """从本地数据库收集各项市场指标。"""
    from app.models.stock import StockDaily, MoneyflowHsgt, IndexDaily
    from app.models.analysis import LimitListD, LimitStep
    from app.analytics.intraday_sync import StockIntraday

    indicators = {}

    # 1. 上涨/下跌家数 — 优先 stock_daily，没有则从分时最新价 vs 昨收推算
    up_count = db.execute(
        select(func.count()).where(StockDaily.trade_date == trade_date, StockDaily.pct_chg > 0)
    ).scalar() or 0
    down_count = db.execute(
        select(func.count()).where(StockDaily.trade_date == trade_date, StockDaily.pct_chg < 0)
    ).scalar() or 0

    # 如果 stock_daily 没有今天数据，从分时推算
    if up_count == 0 and down_count == 0:
        try:
            # 统计分时表中今天有数据的股票，按最新 close vs 第一笔 open 判断涨跌
            result_row = db.execute(text("""
                WITH latest AS (
                    SELECT ts_code,
                           FIRST_VALUE(open) OVER (PARTITION BY ts_code ORDER BY trade_time ASC) as day_open,
                           LAST_VALUE(close) OVER (PARTITION BY ts_code ORDER BY trade_time ASC
                               ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as day_close
                    FROM stock_intraday
                    WHERE trade_date = :td
                ),
                daily_pnl AS (
                    SELECT DISTINCT ts_code, day_open, day_close
                    FROM latest
                    WHERE day_open > 0
                )
                SELECT
                    COUNT(*) FILTER (WHERE day_close > day_open) as up_cnt,
                    COUNT(*) FILTER (WHERE day_close < day_open) as down_cnt
                FROM daily_pnl
            """), {"td": trade_date}).first()
            if result_row:
                up_count = result_row[0] or 0
                down_count = result_row[1] or 0
        except Exception:
            db.rollback()
    total = up_count + down_count
    indicators["up_count"] = up_count
    indicators["down_count"] = down_count
    indicators["up_ratio"] = (up_count / total * 100) if total > 0 else 50.0

    # 2. 成交额及变化（用上证指数成交额代表大盘）
    idx_rows = (
        db.execute(
            select(IndexDaily.amount, IndexDaily.trade_date)
            .where(IndexDaily.ts_code == "000001.SH")
            .order_by(IndexDaily.trade_date.desc())
            .limit(2)
        ).all()
    )
    if idx_rows and len(idx_rows) >= 1:
        today_amount = float(idx_rows[0][0]) / 10000 if idx_rows[0][0] else 0  # 千元→亿元
        prev_amount = float(idx_rows[1][0]) / 10000 if len(idx_rows) > 1 and idx_rows[1][0] else today_amount
        amount_change_pct = ((today_amount - prev_amount) / prev_amount * 100) if prev_amount > 0 else 0
    else:
        today_amount = 0
        amount_change_pct = 0
    indicators["amount"] = round(today_amount, 2)
    indicators["amount_change_pct"] = round(amount_change_pct, 2)

    # 3. 北向资金
    north = db.execute(
        select(MoneyflowHsgt.north_money).where(MoneyflowHsgt.trade_date == trade_date)
    ).scalar()
    indicators["north_money"] = round(float(north) / 100, 2) if north else 0  # 百万→亿

    # 4. 涨停/跌停/炸板
    limit_up = db.execute(
        select(func.count()).where(LimitListD.trade_date == trade_date, LimitListD.limit == "U")
    ).scalar() or 0
    limit_down = db.execute(
        select(func.count()).where(LimitListD.trade_date == trade_date, LimitListD.limit == "D")
    ).scalar() or 0
    open_limit = db.execute(
        select(func.count()).where(LimitListD.trade_date == trade_date, LimitListD.limit == "Z")
    ).scalar() or 0
    indicators["limit_up_count"] = limit_up
    indicators["limit_down_count"] = limit_down
    indicators["open_limit_count"] = open_limit
    indicators["open_limit_rate"] = (open_limit / (limit_up + open_limit) * 100) if (limit_up + open_limit) > 0 else 0

    # 5. 连板高度
    max_board = db.execute(
        select(func.max(LimitStep.step)).where(LimitStep.trade_date == trade_date)
    ).scalar() or 0
    indicators["max_continuous_board"] = int(max_board) if max_board else 0

    # 6. 热点持续性（当天有多少个涨停概念至少 2 只以上）
    try:
        from app.models.analysis import LimitCptList
        hot_concepts = db.execute(
            select(func.count()).where(
                LimitCptList.trade_date == trade_date,
                LimitCptList.up_nums >= 2,
            )
        ).scalar() or 0
    except Exception:
        hot_concepts = 0
    indicators["hot_concept_count"] = hot_concepts

    return indicators


def _calculate_score(indicators: dict) -> int:
    """根据指标加权计算温度分数（0-100）。"""
    scores = {}

    # 上涨家数占比 → 得分（0%→0, 50%→50, 80%+→100）
    up_ratio = indicators.get("up_ratio", 50)
    scores["up_ratio"] = _clamp(up_ratio * 1.25)  # 80%涨→100分

    # 成交额变化 → 得分（-20%以下→20, 0→50, +20%以上→90）
    amt_chg = indicators.get("amount_change_pct", 0)
    scores["amount_change"] = _clamp(50 + amt_chg * 2)

    # 北向资金 → 得分（-50亿→20, 0→50, +50亿→80）
    north = indicators.get("north_money", 0)
    scores["north_money"] = _clamp(50 + north * 0.6)

    # 涨停数量 → 得分（0→10, 50→50, 100+→90）
    limit_up = indicators.get("limit_up_count", 0)
    scores["limit_up"] = _clamp(min(limit_up, 120) / 120 * 100)

    # 跌停数量（反向）→ 得分（0→90, 10→60, 30+→10）
    limit_down = indicators.get("limit_down_count", 0)
    scores["limit_down"] = _clamp(90 - limit_down * 3)

    # 炸板率（反向）→ 得分（0%→90, 30%→50, 60%+→10）
    open_rate = indicators.get("open_limit_rate", 0)
    scores["open_limit_rate"] = _clamp(90 - open_rate * 1.5)

    # 热点持续性 → 得分（0→20, 5→50, 15+→90）
    hot = indicators.get("hot_concept_count", 0)
    scores["hot_continuity"] = _clamp(20 + hot * 5)

    # 连板高度 → 得分（1→20, 3→40, 5→60, 8+→90）
    max_b = indicators.get("max_continuous_board", 0)
    scores["max_board"] = _clamp(max_b * 12)

    # 加权汇总
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return int(round(total))


def _extract_hot_keywords(db: Session, trade_date: date) -> list[str]:
    """提取当天热点关键词（基于涨停概念排名）。"""
    try:
        from app.models.analysis import LimitCptList
        rows = (
            db.execute(
                select(LimitCptList.name)
                .where(LimitCptList.trade_date == trade_date)
                .order_by(LimitCptList.rank.asc())
                .limit(6)
            ).scalars().all()
        )
        return [r for r in rows if r]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# AI 一句话总结
# ---------------------------------------------------------------------------


async def generate_ai_summary(indicators: dict, score: int, level: str, keywords: list[str]) -> str:
    """调用 AI 生成市场温度一句话总结。"""
    context_lines = [
        f"市场温度分数：{score}/100（{level}）",
        f"上涨家数：{indicators.get('up_count', 0)}，下跌家数：{indicators.get('down_count', 0)}",
        f"成交额：{indicators.get('amount', 0)}亿（较昨日{indicators.get('amount_change_pct', 0):+.1f}%）",
        f"北向资金：{indicators.get('north_money', 0):+.1f}亿",
        f"涨停：{indicators.get('limit_up_count', 0)}，跌停：{indicators.get('limit_down_count', 0)}，炸板：{indicators.get('open_limit_count', 0)}",
        f"最高连板：{indicators.get('max_continuous_board', 0)}板",
        f"热点概念：{', '.join(keywords[:5]) if keywords else '无明显热点'}",
    ]
    context = "\n".join(context_lines)

    prompt = "请根据以上市场数据，生成一段简洁的市场温度总结（2-3行，不超过80字）。"

    result = await ai_service.analyze(
        prompt=prompt, role="market_pulse", context=context, temperature=0.6
    )
    # 清理可能的多余空行
    return result.strip()


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------


def _run_async(coro):
    """在同步上下文中运行异步协程。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def generate_market_pulse(trade_date: date | None = None, force: bool = True) -> MarketPulse:
    """生成指定交易日的市场温度快照（同步）。

    Args:
        force: 为 True 时允许覆盖已有记录（盘中每 15 分钟更新）
    """
    db = SessionLocal()
    try:
        # 计算分数
        result = compute_market_pulse(trade_date)
        target_date = result.get("trade_date") or trade_date or date.today()

        # 检查是否已存在
        existing = db.query(MarketPulse).filter(MarketPulse.trade_date == target_date).first()
        if existing and existing.status == "success" and not force:
            logger.info(f"[MarketPulse] {target_date} 已存在成功记录，跳过")
            return existing

        # 创建或更新记录
        if existing is None:
            record = MarketPulse(trade_date=target_date, status="pending", score=0, level="中性")
            db.add(record)
            db.commit()
            db.refresh(record)
        else:
            record = existing
            record.status = "pending"
            db.commit()

        try:
            indicators = result["indicators"]
            score = result["score"]
            level = result["level"]
            keywords = result["keywords"]

            # AI 生成总结
            summary = _run_async(generate_ai_summary(indicators, score, level, keywords))

            # 更新记录
            record.score = score
            record.level = level
            record.summary = summary
            record.keywords = ",".join(keywords) if keywords else None
            record.up_count = indicators.get("up_count")
            record.down_count = indicators.get("down_count")
            record.amount = Decimal(str(indicators.get("amount", 0)))
            record.amount_change_pct = Decimal(str(indicators.get("amount_change_pct", 0)))
            record.north_money = Decimal(str(indicators.get("north_money", 0)))
            record.limit_up_count = indicators.get("limit_up_count")
            record.limit_down_count = indicators.get("limit_down_count")
            record.open_limit_count = indicators.get("open_limit_count")
            record.max_continuous_board = indicators.get("max_continuous_board")
            record.status = "success"
            record.error_message = None
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)[:2000]
            logger.exception(f"[MarketPulse] 生成 {target_date} 市场温度失败")

        db.commit()
        db.refresh(record)
        return record
    finally:
        db.close()


def get_market_pulse_today(db: Session) -> MarketPulse | None:
    """获取最新一条市场温度（当天或最近一个交易日的）。"""
    return (
        db.query(MarketPulse)
        .filter(MarketPulse.status == "success")
        .order_by(MarketPulse.trade_date.desc())
        .first()
    )


def get_market_pulse_by_date(db: Session, trade_date: date) -> MarketPulse | None:
    """获取指定日期的市场温度。"""
    return db.query(MarketPulse).filter(MarketPulse.trade_date == trade_date).first()


def get_market_pulse_history(db: Session, limit: int = 30) -> list[MarketPulse]:
    """获取历史市场温度列表。"""
    return (
        db.query(MarketPulse)
        .filter(MarketPulse.status == "success")
        .order_by(MarketPulse.trade_date.desc())
        .limit(limit)
        .all()
    )
