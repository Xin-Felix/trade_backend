"""AI 仓位建议服务层。

为会员自动生成基于其持仓（Portfolio）的 AI 仓位管理建议。
"""

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ai_position_advice import AiPositionAdvice
from app.models.membership import UserMembership
from app.models.portfolio import Portfolio
from app.models.user import User as UserModel
from app.services import ai_service, stock_service
from app.services.daily_review_service import build_watchlist_context

logger = logging.getLogger(__name__)


# 批量生成时最大并发数，避免同时发起过多 AI 调用
MAX_CONCURRENT_ADVICES = 3


# ---------------------------------------------------------------------------
# 交易日辅助（复用每日复盘逻辑）
# ---------------------------------------------------------------------------


def get_latest_trade_date(db: Session) -> date | None:
    """获取本地数据库中最新的交易日（基于 stock_daily 表）。"""
    from app.models.stock import StockDaily

    latest = db.query(func.max(StockDaily.trade_date)).scalar()
    return latest


def is_trading_day(db: Session, target_date: date) -> bool:
    """判断指定日期是否为交易日（本地有 stock_daily 数据）。"""
    latest = get_latest_trade_date(db)
    if latest is None:
        return False
    return latest == target_date


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_or_create_advice(db: Session, user_id: int, report_date: date) -> AiPositionAdvice:
    """获取或创建某用户某日的仓位建议记录。"""
    advice = (
        db.query(AiPositionAdvice)
        .filter(
            AiPositionAdvice.user_id == user_id,
            AiPositionAdvice.report_date == report_date,
            AiPositionAdvice.is_deleted == 0,
        )
        .first()
    )
    if advice is None:
        advice = AiPositionAdvice(user_id=user_id, report_date=report_date, status="pending")
        db.add(advice)
        db.commit()
        db.refresh(advice)
    return advice


def _calculate_pnl(price: float | None, cost_price: float | None, quantity: float | None) -> dict:
    """计算持仓盈亏。"""
    result = {
        "position_value": None,
        "cost_value": None,
        "unrealized_pnl": None,
        "pnl_percent": None,
    }
    if price is None or cost_price is None or quantity is None:
        return result
    result["position_value"] = price * quantity
    result["cost_value"] = cost_price * quantity
    result["unrealized_pnl"] = result["position_value"] - result["cost_value"]
    if cost_price != 0:
        result["pnl_percent"] = (price - cost_price) / cost_price * 100
    return result


def get_user_portfolio_data(db: Session, user_id: int) -> list[dict]:
    """获取用户持仓及其行情数据（结构化，供后台查看）。"""
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return []

    rows = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.public_id, Portfolio.is_deleted == 0)
        .all()
    )
    result = []
    for item in rows:
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            basic = basic_list[0] if basic_list else None
            price = quote.price if quote else None
            change_percent = quote.change_percent if quote else None
            cost_price = float(item.cost_price) if item.cost_price is not None else None
            quantity = float(item.quantity) if item.quantity is not None else None
            pnl = _calculate_pnl(price, cost_price, quantity)
            result.append({
                "code": item.code,
                "name": item.name,
                "ts_code": item.ts_code,
                "price": price,
                "change_percent": change_percent,
                "cost_price": cost_price,
                "quantity": quantity,
                "is_margin": bool(item.is_margin) if item.is_margin is not None else False,
                "position_value": pnl["position_value"],
                "cost_value": pnl["cost_value"],
                "unrealized_pnl": pnl["unrealized_pnl"],
                "pnl_percent": pnl["pnl_percent"],
                "pe": basic.get("pe") if basic else None,
                "pb": basic.get("pb") if basic else None,
                "turnover_rate": basic.get("turnover_rate") if basic else None,
            })
        except Exception as exc:
            result.append({
                "code": item.code,
                "name": item.name,
                "ts_code": item.ts_code,
                "cost_price": float(item.cost_price) if item.cost_price is not None else None,
                "quantity": float(item.quantity) if item.quantity is not None else None,
                "is_margin": bool(item.is_margin) if item.is_margin is not None else False,
                "error": str(exc),
            })
    return result


async def build_portfolio_context(db: Session, user_id: int, include_watchlist: bool = True) -> str:
    """基于用户持仓组装 AI 上下文文本。"""
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return "用户不存在。"

    rows = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.public_id, Portfolio.is_deleted == 0)
        .all()
    )
    parts = [f"用户：{user.name or user.email}"]

    if rows:
        parts.append("当前持仓：")
        total_position_value = 0.0
        total_cost_value = 0.0
        total_margin_value = 0.0
        for item in rows:
            try:
                quote = stock_service.get_stock_quote(item.code)
                basic_list = stock_service.get_daily_basic(item.code, limit=1)
                extra = ""
                if basic_list:
                    b = basic_list[0]
                    extra = f" | PE={b.get('pe')} PB={b.get('pb')} 换手={b.get('turnover_rate')}%"
                price = quote.price if quote else None
                change_percent = quote.change_percent if quote else None
                cost_price = float(item.cost_price) if item.cost_price is not None else None
                quantity = float(item.quantity) if item.quantity is not None else None
                is_margin = bool(item.is_margin) if item.is_margin is not None else False
                pnl = _calculate_pnl(price, cost_price, quantity)
                position_value = pnl["position_value"]
                cost_value = pnl["cost_value"]
                unrealized_pnl = pnl["unrealized_pnl"]
                pnl_percent = pnl["pnl_percent"]
                if position_value is not None:
                    total_position_value += position_value
                if cost_value is not None:
                    total_cost_value += cost_value
                if is_margin and position_value is not None:
                    total_margin_value += position_value

                position_line = f"- {item.name}（{item.code}）: 现价 {price}, 涨跌幅 {change_percent}%"
                if cost_price is not None and quantity is not None:
                    position_line += (
                        f" | 持仓 {quantity}股, 成本 {cost_price}, "
                        f"浮盈/亏 {unrealized_pnl:+.2f} ({pnl_percent:+.2f}%)"
                    )
                if is_margin:
                    position_line += ", 融资: 是"
                position_line += extra
                parts.append(position_line)
            except Exception as exc:
                parts.append(f"- {item.name}（{item.code}）: 行情获取失败（{exc}）")

        total_pnl = total_position_value - total_cost_value if total_cost_value else None
        pnl_percent = (total_pnl / total_cost_value * 100) if total_cost_value else None
        summary_parts = [f"持仓总市值: {total_position_value:.2f}"]
        if total_cost_value:
            summary_parts.append(f"总成本: {total_cost_value:.2f}")
        if total_pnl is not None:
            summary_parts.append(f"总浮盈/亏: {total_pnl:+.2f}")
        if pnl_percent is not None:
            summary_parts.append(f"总盈亏比例: {pnl_percent:+.2f}%")
        if total_margin_value:
            summary_parts.append(f"融资仓位市值: {total_margin_value:.2f}")
        parts.append(" | ".join(summary_parts))
    else:
        parts.append("该用户当前没有持仓。")

    if include_watchlist:
        watchlist_context = await build_watchlist_context(db, user_id)
        if watchlist_context and "没有自选股" not in watchlist_context:
            parts.append("\n" + watchlist_context)

    return "\n".join(parts)


async def _generate_advice_content(user: UserModel, context: str) -> dict:
    """调用 AI 生成仓位建议内容，返回 {"summary": ..., "content": ...}。"""
    prompt = (
        f"请为以下用户生成今日的仓位管理建议。\n"
        f"用户：{user.name or user.email}\n"
        f"请结合其当前持仓的成本价、持仓数量、盈亏比例以及是否融资情况，"
        f"给出结构化的仓位分析与调整建议。对融资仓位需额外关注杠杆风险，"
        f"对亏损较大的持仓可建议止损或减仓。"
    )
    return await ai_service.analyze_json(
        prompt=prompt, role="position_advice", context=context, schema=ai_service.AiReportOutput
    )


def _run_async(coro):
    """在同步上下文中运行异步协程，兼容 APScheduler 线程环境。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------


async def generate_position_advice_for_user(
    db: Session, user_id: int, report_date: date, force: bool = False
) -> AiPositionAdvice:
    """为单个用户生成指定日期的仓位建议（异步）。

    Args:
        force: 为 True 时强制重新生成，即使状态为 running 也会覆盖。
    """
    advice = _get_or_create_advice(db, user_id, report_date)
    if not force and advice.status == "running":
        logger.info(f"[AiPositionAdvice] 用户 {user_id} {report_date} 仓位建议正在生成中，跳过")
        return advice

    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        advice.status = "failed"
        advice.error_message = "用户不存在"
        db.commit()
        return advice

    advice.status = "running"
    db.commit()

    try:
        context = await build_portfolio_context(db, user_id)
        result = await _generate_advice_content(user, context)
        advice.summary = result.get("summary")
        advice.content = result.get("content")
        advice.status = "success"
        advice.error_message = None
    except Exception as exc:
        advice.status = "failed"
        advice.error_message = str(exc)[:2000]
        logger.exception(f"[AiPositionAdvice] 为用户 {user_id} 生成仓位建议失败")
    finally:
        db.commit()
        db.refresh(advice)

    return advice


def generate_position_advice_for_user_sync(
    db: Session, user_id: int, report_date: date
) -> AiPositionAdvice:
    """为单个用户生成指定日期的仓位建议（同步包装，供定时任务使用）。"""
    return _run_async(generate_position_advice_for_user(db, user_id, report_date))


async def _generate_one_user(
    user_id: int, report_date: date, semaphore: asyncio.Semaphore
) -> tuple[int, bool]:
    """为一个用户生成仓位建议（带并发控制），使用独立 session。"""
    async with semaphore:
        db = SessionLocal()
        try:
            advice = await generate_position_advice_for_user(db, user_id, report_date)
            return (user_id, advice.status == "success")
        except Exception:
            logger.exception(f"[AiPositionAdvice] 批量生成时用户 {user_id} 失败")
            return (user_id, False)
        finally:
            db.close()


def generate_position_advices_for_all_members(
    report_date: date | None = None,
    skip_non_trading_day: bool = False,
    max_concurrent: int = MAX_CONCURRENT_ADVICES,
) -> dict:
    """为所有生效会员生成指定日期的仓位建议。

    Args:
        report_date: 报告日期，默认今天
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
                f"[AiPositionAdvice] {report_date} 不是交易日（最新数据 {latest}），跳过批量生成"
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
            for r in db.query(AiPositionAdvice.user_id)
            .filter(
                AiPositionAdvice.report_date == report_date,
                AiPositionAdvice.status.in_(skip_statuses),
                AiPositionAdvice.is_deleted == 0,
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
            *[_generate_one_user(uid, report_date, semaphore) for uid in eligible_user_ids]
        )

    results = _run_async(_run_all())
    success = sum(1 for _, ok in results if ok)
    failed = len(results) - success

    logger.info(
        f"[AiPositionAdvice] {report_date} 批量生成完成："
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


# ---------------------------------------------------------------------------
# 查询与重试
# ---------------------------------------------------------------------------


def get_user_advices(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[AiPositionAdvice], int]:
    """查询指定用户的仓位建议列表（按日期倒序）。"""
    query = db.query(AiPositionAdvice).filter(
        AiPositionAdvice.user_id == user_id,
        AiPositionAdvice.is_deleted == 0,
    )
    total = query.count()
    items = (
        query.order_by(AiPositionAdvice.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_advice_detail(db: Session, advice_id: int, user_id: int | None = None) -> AiPositionAdvice | None:
    """获取仓位建议详情，普通用户需校验归属。"""
    query = db.query(AiPositionAdvice).filter(
        AiPositionAdvice.id == advice_id,
        AiPositionAdvice.is_deleted == 0,
    )
    if user_id is not None:
        query = query.filter(AiPositionAdvice.user_id == user_id)
    return query.first()


def get_admin_advices(
    db: Session,
    user_id: int | None = None,
    report_date: date | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AiPositionAdvice], int]:
    """管理端仓位建议记录列表。"""
    query = db.query(AiPositionAdvice).filter(AiPositionAdvice.is_deleted == 0)
    if user_id is not None:
        query = query.filter(AiPositionAdvice.user_id == user_id)
    if report_date is not None:
        query = query.filter(AiPositionAdvice.report_date == report_date)
    if status is not None:
        query = query.filter(AiPositionAdvice.status == status)

    total = query.count()
    items = (
        query.order_by(AiPositionAdvice.report_date.desc(), AiPositionAdvice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_advice_content(
    db: Session, advice_id: int, content: str, summary: str | None = None
) -> AiPositionAdvice | None:
    """管理员手工编辑仓位建议内容。"""
    advice = (
        db.query(AiPositionAdvice)
        .filter(AiPositionAdvice.id == advice_id, AiPositionAdvice.is_deleted == 0)
        .first()
    )
    if advice is None:
        return None
    advice.content = content
    if summary is not None:
        advice.summary = summary
    advice.status = "success"
    advice.error_message = None
    db.commit()
    db.refresh(advice)
    return advice


def retry_failed_advices(db: Session, report_date: date | None = None) -> dict:
    """重试指定日期的失败仓位建议。"""
    if report_date is None:
        report_date = date.today()

    failed_advices = (
        db.query(AiPositionAdvice)
        .filter(
            AiPositionAdvice.report_date == report_date,
            AiPositionAdvice.status == "failed",
            AiPositionAdvice.is_deleted == 0,
        )
        .all()
    )

    success = 0
    still_failed = 0
    for advice in failed_advices:
        try:
            result = generate_position_advice_for_user_sync(db, advice.user_id, report_date)
            if result.status == "success":
                success += 1
            else:
                still_failed += 1
        except Exception:
            still_failed += 1
            logger.exception(f"[AiPositionAdvice] 重试仓位建议 {advice.id} 失败")

    return {"total": len(failed_advices), "success": success, "still_failed": still_failed}
