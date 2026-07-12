"""每日复盘服务层。

为会员自动生成基于自选股的 AI 复盘报告，并提供查询/重试能力。
"""

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.daily_review import DailyReview
from app.models.membership import UserMembership
from app.models.user import User as UserModel
from app.models.watchlist import Watchlist
from app.services import ai_service, stock_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_or_create_review(db: Session, user_id: int, report_date: date) -> DailyReview:
    """获取或创建某用户某日的复盘记录。"""
    review = (
        db.query(DailyReview)
        .filter(DailyReview.user_id == user_id, DailyReview.report_date == report_date)
        .first()
    )
    if review is None:
        review = DailyReview(user_id=user_id, report_date=report_date, status="pending")
        db.add(review)
        db.commit()
        db.refresh(review)
    return review


async def _build_watchlist_context(db: Session, user: UserModel) -> str:
    """基于用户自选股组装 AI 上下文。"""
    rows = db.query(Watchlist).filter(Watchlist.user_id == user.public_id).all()
    if not rows:
        return "该用户当前没有自选股，请生成一份面向整体市场的通用收盘复盘。"

    parts = [f"用户：{user.name or user.email}", "自选股列表："]
    for item in rows:
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            extra = ""
            if basic_list:
                b = basic_list[0]
                extra = f" | PE={b.pe} PB={b.pb} 换手={b.turnover_rate}%"
            parts.append(
                f"- {item.name}（{item.code}）: 现价 {quote.price}, 涨跌幅 {quote.change_percent}%{extra}"
            )
        except Exception as exc:
            parts.append(f"- {item.name}（{item.code}）: 行情获取失败（{exc}）")

    return "\n".join(parts)


async def _generate_review_content(user: UserModel, context: str) -> str:
    """调用 AI 生成复盘内容。"""
    prompt = (
        f"请为以下用户生成今日的收盘复盘报告。\n"
        f"用户：{user.name or user.email}\n"
        f"请结合其自选股表现，给出结构化的复盘分析。"
    )
    return await ai_service.analyze(prompt=prompt, role="daily_review", context=context)


def _run_async(coro):
    """在同步上下文中运行异步协程，兼容 APScheduler 线程环境。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # 当前线程可能已有 event loop（如测试/某些运行时），新建一个运行
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------


async def generate_daily_review_for_user(
    db: Session, user_id: int, report_date: date
) -> DailyReview:
    """为单个用户生成指定日期的复盘（异步）。"""
    review = _get_or_create_review(db, user_id, report_date)

    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if user is None:
        review.status = "failed"
        review.error_message = "用户不存在"
        db.commit()
        return review

    review.status = "running"
    db.commit()

    try:
        context = await _build_watchlist_context(db, user)
        content = await _generate_review_content(user, context)
        review.content = content
        review.status = "success"
        review.error_message = None
    except Exception as exc:
        review.status = "failed"
        review.error_message = str(exc)[:2000]
        logger.exception(f"[DailyReview] 为用户 {user_id} 生成复盘失败")
    finally:
        db.commit()
        db.refresh(review)

    return review


def generate_daily_review_for_user_sync(
    db: Session, user_id: int, report_date: date
) -> DailyReview:
    """为单个用户生成指定日期的复盘（同步包装，供定时任务使用）。"""
    return _run_async(generate_daily_review_for_user(db, user_id, report_date))


def generate_daily_reviews_for_all_members(report_date: date | None = None) -> dict:
    """为所有生效会员生成指定日期的复盘。"""
    if report_date is None:
        report_date = date.today()

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        memberships = (
            db.query(UserMembership)
            .filter(UserMembership.status == "active", UserMembership.expires_at > now)
            .all()
        )
        user_ids = list({m.user_id for m in memberships})

        success = 0
        failed = 0

        for user_id in user_ids:
            try:
                review = generate_daily_review_for_user_sync(db, user_id, report_date)
                if review.status == "success":
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.exception(f"[DailyReview] 批量生成时用户 {user_id} 失败")

        logger.info(
            f"[DailyReview] {report_date} 批量生成完成：总数 {len(user_ids)}，"
            f"成功 {success}，失败 {failed}"
        )
        return {"total": len(user_ids), "success": success, "failed": failed}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 查询与重试
# ---------------------------------------------------------------------------


def get_user_reviews(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[DailyReview], int]:
    """查询指定用户的复盘列表（按日期倒序）。"""
    query = db.query(DailyReview).filter(DailyReview.user_id == user_id)
    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_review_detail(db: Session, review_id: int, user_id: int | None = None) -> DailyReview | None:
    """获取复盘详情，普通用户需校验归属。"""
    query = db.query(DailyReview).filter(DailyReview.id == review_id)
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    return query.first()


def get_admin_reviews(
    db: Session,
    user_id: int | None = None,
    report_date: date | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DailyReview], int]:
    """管理端复盘记录列表。"""
    query = db.query(DailyReview)
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    if report_date is not None:
        query = query.filter(DailyReview.report_date == report_date)
    if status is not None:
        query = query.filter(DailyReview.status == status)

    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc(), DailyReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def retry_failed_reviews(db: Session, report_date: date | None = None) -> dict:
    """重试指定日期的失败复盘。"""
    if report_date is None:
        report_date = date.today()

    failed_reviews = (
        db.query(DailyReview)
        .filter(DailyReview.report_date == report_date, DailyReview.status == "failed")
        .all()
    )

    success = 0
    still_failed = 0
    for review in failed_reviews:
        try:
            result = generate_daily_review_for_user_sync(db, review.user_id, report_date)
            if result.status == "success":
                success += 1
            else:
                still_failed += 1
        except Exception:
            still_failed += 1
            logger.exception(f"[DailyReview] 重试复盘 {review.id} 失败")

    return {"total": len(failed_reviews), "success": success, "still_failed": still_failed}
