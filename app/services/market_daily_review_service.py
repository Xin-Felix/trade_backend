"""全市场每日一句话复盘服务层。

每日收盘后生成一份全市场通用的极简复盘，供免费用户查看。
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.market_daily_review import MarketDailyReview
from app.models.stock import StockDaily
from app.services import ai_service, stock_service

logger = logging.getLogger(__name__)


def _get_or_create_market_review(db: Session, report_date: date) -> MarketDailyReview:
    """获取或创建某日期的全市场一句话复盘记录。"""
    review = (
        db.query(MarketDailyReview)
        .filter(
            MarketDailyReview.report_date == report_date,
            MarketDailyReview.is_deleted == 0,
        )
        .first()
    )
    if review is None:
        review = MarketDailyReview(report_date=report_date, status="pending")
        db.add(review)
        db.commit()
        db.refresh(review)
    return review


def get_latest_trade_date(db: Session) -> date | None:
    """获取本地数据库中最新的交易日（基于 stock_daily 表）。"""
    latest = db.query(func.max(StockDaily.trade_date)).scalar()
    return latest


def is_trading_day(db: Session, target_date: date) -> bool:
    """判断指定日期是否为交易日（本地 stock_daily 表存在该日数据）。"""
    return (
        db.query(StockDaily)
        .filter(StockDaily.trade_date == target_date)
        .first()
        is not None
    )


def _build_market_context(report_date: date) -> str:
    """基于大盘指数组装全市场一句话复盘的上下文文本。"""
    try:
        indices = stock_service.get_indices() or []
    except Exception as exc:
        logger.warning(f"[MarketDailyReview] 获取大盘指数失败: {exc}")
        indices = []

    parts = [f"报告日期：{report_date.isoformat()}"]
    if indices:
        parts.append("主要指数表现：")
        for idx in indices:
            name = idx.get("name") or idx.get("code", "")
            price = idx.get("price")
            change = idx.get("change_percent")
            if price is not None and change is not None:
                sign = "+" if change >= 0 else ""
                parts.append(f"  {name}: {price} ({sign}{change}%)")
    else:
        parts.append("暂无指数数据。")

    return "\n".join(parts)


async def _generate_market_brief_content(report_date: date) -> str:
    """调用 AI 生成全市场一句话复盘。"""
    context = _build_market_context(report_date)
    prompt = (
        "请根据以下今日市场数据，生成一句简洁的每日市场复盘。\n"
        "要求：一句话概括市场整体表现、热点方向或风险提示，不超过 100 字。"
    )
    return await ai_service.analyze(
        prompt=prompt,
        role="market_analyst",
        context=context,
    )


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


async def generate_market_brief(db: Session, report_date: date) -> MarketDailyReview:
    """生成指定日期的全市场一句话复盘（异步）。"""
    review = _get_or_create_market_review(db, report_date)
    if review.status == "running":
        logger.info(f"[MarketDailyReview] {report_date} 正在生成中，跳过")
        return review

    review.status = "running"
    db.commit()

    try:
        content = await _generate_market_brief_content(report_date)
        review.content = content
        review.status = "success"
        review.error_message = None
    except Exception as exc:
        review.status = "failed"
        review.error_message = str(exc)[:2000]
        logger.exception(f"[MarketDailyReview] 生成 {report_date} 全市场复盘失败")
    finally:
        db.commit()
        db.refresh(review)

    return review


def generate_market_brief_sync(db: Session, report_date: date) -> MarketDailyReview:
    """生成指定日期的全市场一句话复盘（同步包装）。"""
    return _run_async(generate_market_brief(db, report_date))


def get_market_brief(
    db: Session, report_date: date | None = None
) -> MarketDailyReview | None:
    """获取指定日期的全市场一句话复盘，默认今天。"""
    if report_date is None:
        report_date = date.today()
    return (
        db.query(MarketDailyReview)
        .filter(
            MarketDailyReview.report_date == report_date,
            MarketDailyReview.is_deleted == 0,
        )
        .first()
    )


def get_market_brief_list(
    db: Session, page: int = 1, page_size: int = 20
) -> tuple[list[MarketDailyReview], int]:
    """管理端：获取全市场一句话复盘列表（按日期倒序）。"""
    query = db.query(MarketDailyReview).filter(MarketDailyReview.is_deleted == 0)
    total = query.count()
    items = (
        query.order_by(MarketDailyReview.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_market_brief_content(
    db: Session, review_id: int, content: str
) -> MarketDailyReview | None:
    """管理员手工编辑全市场一句话复盘内容。"""
    review = (
        db.query(MarketDailyReview)
        .filter(MarketDailyReview.id == review_id, MarketDailyReview.is_deleted == 0)
        .first()
    )
    if review is None:
        return None
    review.content = content
    review.status = "success"
    review.error_message = None
    db.commit()
    db.refresh(review)
    return review


def get_market_brief_detail(db: Session, review_id: int) -> MarketDailyReview | None:
    """获取全市场一句话复盘详情。"""
    return (
        db.query(MarketDailyReview)
        .filter(MarketDailyReview.id == review_id, MarketDailyReview.is_deleted == 0)
        .first()
    )
