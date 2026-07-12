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

# 批量生成时最大并发数，避免同时发起过多 AI 调用
MAX_CONCURRENT_REVIEWS = 3


# ---------------------------------------------------------------------------
# 交易日辅助
# ---------------------------------------------------------------------------


def get_latest_trade_date(db: Session) -> date | None:
    """获取本地数据库中最新的交易日（基于 stock_daily 表）。"""
    from app.models.stock import StockDaily

    latest = db.query(func.max(StockDaily.trade_date)).scalar()
    return latest


def is_trading_day(db: Session, target_date: date) -> bool:
    """判断指定日期是否为交易日（本地 stock_daily 表存在该日数据）。"""
    from app.models.stock import StockDaily

    return (
        db.query(StockDaily)
        .filter(StockDaily.trade_date == target_date)
        .first()
        is not None
    )


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_or_create_review(
    db: Session, user_id: int, report_date: date, level: str = "standard"
) -> DailyReview:
    """获取或创建某用户某日某层级的复盘记录。"""
    review = (
        db.query(DailyReview)
        .filter(
            DailyReview.user_id == user_id,
            DailyReview.report_date == report_date,
            DailyReview.level == level,
            DailyReview.is_deleted == 0,
        )
        .first()
    )
    if review is None:
        review = DailyReview(
            user_id=user_id, report_date=report_date, level=level, status="pending"
        )
        db.add(review)
        db.commit()
        db.refresh(review)
    return review


def get_user_watchlist_data(db: Session, user_id: int) -> list[dict]:
    """获取用户自选股及其行情数据（结构化，供后台查看）。"""
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return []

    rows = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.public_id, Watchlist.is_deleted == 0)
        .all()
    )
    result = []
    for item in rows:
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            basic = basic_list[0] if basic_list else None
            result.append({
                "code": item.code,
                "name": item.name,
                "ts_code": item.ts_code,
                "price": quote.price if quote else None,
                "change_percent": quote.change_percent if quote else None,
                "pe": basic.get("pe") if basic else None,
                "pb": basic.get("pb") if basic else None,
                "turnover_rate": basic.get("turnover_rate") if basic else None,
            })
        except Exception as exc:
            result.append({
                "code": item.code,
                "name": item.name,
                "ts_code": item.ts_code,
                "error": str(exc),
            })
    return result


async def build_watchlist_context(db: Session, user_id: int) -> str:
    """基于用户自选股组装 AI 上下文文本（公开版本）。"""
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return "用户不存在。"

    rows = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.public_id, Watchlist.is_deleted == 0)
        .all()
    )
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
                extra = f" | PE={b.get('pe')} PB={b.get('pb')} 换手={b.get('turnover_rate')}%"
            parts.append(
                f"- {item.name}（{item.code}）: 现价 {quote.price}, 涨跌幅 {quote.change_percent}%{extra}"
            )
        except Exception as exc:
            parts.append(f"- {item.name}（{item.code}）: 行情获取失败（{exc}）")

    return "\n".join(parts)


async def _build_watchlist_context(db: Session, user: UserModel) -> str:
    """基于用户自选股组装 AI 上下文（内部兼容旧调用）。"""
    return await build_watchlist_context(db, user.id)


async def _generate_review_content(user: UserModel, context: str, level: str = "standard") -> dict:
    """调用 AI 生成复盘内容，返回 {"summary": ..., "content": ...}。"""
    prompt = (
        f"请为以下用户生成今日的收盘复盘报告。\n"
        f"用户：{user.name or user.email}\n"
        f"复盘层级：{level}\n"
        f"请结合其自选股表现，给出结构化的复盘分析。"
    )
    return await ai_service.analyze_json(
        prompt=prompt, role="daily_review", context=context, schema=ai_service.AiReportOutput
    )


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
    db: Session, user_id: int, report_date: date, level: str = "standard", force: bool = False
) -> DailyReview:
    """为单个用户生成指定日期、指定层级的复盘（异步）。

    Args:
        force: 为 True 时强制重新生成，即使状态为 running 也会覆盖。
    """
    review = _get_or_create_review(db, user_id, report_date, level=level)
    if not force and review.status == "running":
        logger.info(f"[DailyReview] 用户 {user_id} {report_date} {level} 复盘正在生成中，跳过")
        return review

    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        review.status = "failed"
        review.error_message = "用户不存在"
        db.commit()
        return review

    review.status = "running"
    db.commit()

    try:
        context = await _build_watchlist_context(db, user)
        result = await _generate_review_content(user, context, level=level)
        review.summary = result.get("summary")
        review.content = result.get("content")
        review.status = "success"
        review.error_message = None
    except Exception as exc:
        review.status = "failed"
        review.error_message = str(exc)[:2000]
        logger.exception(f"[DailyReview] 为用户 {user_id} 生成 {level} 复盘失败")
    finally:
        db.commit()
        db.refresh(review)

    return review


def generate_daily_review_for_user_sync(
    db: Session, user_id: int, report_date: date, level: str = "standard"
) -> DailyReview:
    """为单个用户生成指定日期、指定层级的复盘（同步包装，供定时任务使用）。"""
    return _run_async(generate_daily_review_for_user(db, user_id, report_date, level=level))


async def _generate_one_user(
    user_id: int, report_date: date, level: str, semaphore: asyncio.Semaphore
) -> tuple[int, bool]:
    """为一个用户生成复盘（带并发控制），使用独立 session。"""
    async with semaphore:
        db = SessionLocal()
        try:
            review = await generate_daily_review_for_user(db, user_id, report_date, level=level)
            return (user_id, review.status == "success")
        except Exception:
            logger.exception(f"[DailyReview] 批量生成时用户 {user_id} 失败")
            return (user_id, False)
        finally:
            db.close()


def generate_daily_reviews_for_all_members(
    report_date: date | None = None,
    level: str = "standard",
    skip_non_trading_day: bool = False,
    max_concurrent: int = MAX_CONCURRENT_REVIEWS,
) -> dict:
    """为所有生效会员生成指定日期、指定层级的复盘。

    Args:
        report_date: 复盘日期，默认今天
        level: 复盘层级，standard / deep
        skip_non_trading_day: 为 True 时，若 report_date 不是交易日则跳过不生成
        max_concurrent: 批量生成时的最大并发数
    """
    if report_date is None:
        report_date = date.today()

    db = SessionLocal()
    try:
        if skip_non_trading_day and not is_trading_day(db, report_date):
            latest = get_latest_trade_date(db)
            logger.info(
                f"[DailyReview] {report_date} 不是交易日（最新数据 {latest}），跳过批量生成"
            )
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": True,
                "reason": f"非交易日，最新数据 {latest}",
            }

        now = datetime.now(timezone.utc)
        memberships = (
            db.query(UserMembership)
            .filter(
                UserMembership.status == "active",
                UserMembership.expires_at > now,
                UserMembership.is_deleted == 0,
            )
            .all()
        )
        user_ids = list({m.user_id for m in memberships})

        # 过滤已删除用户
        active_user_ids = {
            u.id
            for u in db.query(UserModel.id).filter(
                UserModel.id.in_(user_ids),
                UserModel.is_deleted == 0,
            )
        }
        user_ids = [uid for uid in user_ids if uid in active_user_ids]

        # 跳过已成功或正在生成中的用户，避免重复调用 AI
        skip_statuses = ("success", "running")
        skip_user_ids = {
            r.user_id
            for r in db.query(DailyReview.user_id)
            .filter(
                DailyReview.report_date == report_date,
                DailyReview.level == level,
                DailyReview.status.in_(skip_statuses),
                DailyReview.is_deleted == 0,
            )
            .all()
        }
        eligible_user_ids = [uid for uid in user_ids if uid not in skip_user_ids]
        skipped_count = len(user_ids) - len(eligible_user_ids)
    finally:
        db.close()

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_all():
        return await asyncio.gather(
            *[
                _generate_one_user(uid, report_date, level, semaphore)
                for uid in eligible_user_ids
            ]
        )

    results = _run_async(_run_all())
    success = sum(1 for _, ok in results if ok)
    failed = len(results) - success

    logger.info(
        f"[DailyReview] {report_date} {level} 批量生成完成："
        f"生效会员 {len(user_ids)}，已存在成功记录跳过 {skipped_count}，"
        f"实际生成 {len(eligible_user_ids)}，成功 {success}，失败 {failed}"
    )
    return {
        "total": len(user_ids),
        "skipped": skipped_count,
        "generated": len(eligible_user_ids),
        "success": success,
        "failed": failed,
    }


def generate_deep_reviews_for_all_members(
    report_date: date | None = None,
    skip_non_trading_day: bool = True,
    max_concurrent: int = MAX_CONCURRENT_REVIEWS,
) -> dict:
    """为所有生效会员生成深度复盘。"""
    return generate_daily_reviews_for_all_members(
        report_date=report_date,
        level="deep",
        skip_non_trading_day=skip_non_trading_day,
        max_concurrent=max_concurrent,
    )


async def generate_standard_review_for_user(
    db: Session, user_id: int, report_date: date
) -> DailyReview:
    """为积分用户手动生成标准复盘。

    调用前需由接口层完成积分扣减。
    """
    return await generate_daily_review_for_user(db, user_id, report_date, level="standard")


# ---------------------------------------------------------------------------
# 查询与重试
# ---------------------------------------------------------------------------


def get_user_reviews(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[DailyReview], int]:
    """查询指定用户的复盘列表（按日期倒序）。"""
    query = db.query(DailyReview).filter(
        DailyReview.user_id == user_id,
        DailyReview.is_deleted == 0,
    )
    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_review_detail(
    db: Session, review_id: int, user_id: int | None = None, level: str | None = None
) -> DailyReview | None:
    """获取复盘详情，普通用户需校验归属。"""
    query = db.query(DailyReview).filter(
        DailyReview.id == review_id,
        DailyReview.is_deleted == 0,
    )
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    if level is not None:
        query = query.filter(DailyReview.level == level)
    return query.first()


def get_admin_reviews(
    db: Session,
    user_id: int | None = None,
    report_date: date | None = None,
    status: str | None = None,
    level: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DailyReview], int]:
    """管理端复盘记录列表。"""
    query = db.query(DailyReview).filter(DailyReview.is_deleted == 0)
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    if report_date is not None:
        query = query.filter(DailyReview.report_date == report_date)
    if status is not None:
        query = query.filter(DailyReview.status == status)
    if level is not None:
        query = query.filter(DailyReview.level == level)

    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc(), DailyReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_review_content(
    db: Session, review_id: int, content: str, summary: str | None = None
) -> DailyReview | None:
    """管理员手工编辑复盘内容。"""
    review = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.is_deleted == 0)
        .first()
    )
    if review is None:
        return None
    review.content = content
    if summary is not None:
        review.summary = summary
    review.status = "success"
    review.error_message = None
    db.commit()
    db.refresh(review)
    return review


def retry_failed_reviews(
    db: Session, report_date: date | None = None, level: str | None = None
) -> dict:
    """重试指定日期、指定层级的失败复盘。"""
    if report_date is None:
        report_date = date.today()

    query = db.query(DailyReview).filter(
        DailyReview.report_date == report_date,
        DailyReview.status == "failed",
        DailyReview.is_deleted == 0,
    )
    if level is not None:
        query = query.filter(DailyReview.level == level)

    failed_reviews = query.all()

    success = 0
    still_failed = 0
    for review in failed_reviews:
        try:
            result = generate_daily_review_for_user_sync(
                db, review.user_id, report_date, level=review.level
            )
            if result.status == "success":
                success += 1
            else:
                still_failed += 1
        except Exception:
            still_failed += 1
            logger.exception(f"[DailyReview] 重试复盘 {review.id} 失败")

    return {"total": len(failed_reviews), "success": success, "still_failed": still_failed}
