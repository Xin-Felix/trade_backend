"""会员订阅与功能权限校验服务层。

提供会员开通/续费、过期处理、月度积分发放、功能权限评估与积分消费。
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.membership import (
    MembershipTier,
    SubscriptionOrder,
    UserFeatureUsage,
    UserMembership,
)
from app.models.points import FeaturePermission, PointRecord
from app.models.user import User as UserModel
from app.services import points_service


class MembershipTierNotFoundError(Exception):
    """会员档位不存在"""
    pass


class SubscriptionOrderNotFoundError(Exception):
    """订阅订单不存在"""
    pass


def get_active_membership(db: Session, user_id: int) -> UserMembership | None:
    """查询用户当前生效的会员记录。"""
    now = datetime.now(timezone.utc)
    return (
        db.query(UserMembership)
        .filter(
            UserMembership.user_id == user_id,
            UserMembership.status == "active",
            UserMembership.expires_at > now,
            UserMembership.is_deleted == 0,
        )
        .order_by(UserMembership.expires_at.desc())
        .first()
    )


def tier_covers_feature(db: Session, tier_code: str, feature_code: str) -> bool:
    """判断某会员档位是否包含指定功能。"""
    tier = db.query(MembershipTier).filter(MembershipTier.code == tier_code).first()
    if tier is None or tier.enabled == 0:
        return False
    features = tier.features or []
    return "*" in features or feature_code in features


def _get_today_usage(
    db: Session, user_id: int, feature_code: str
) -> UserFeatureUsage | None:
    """获取用户今天某功能的使用计数记录。"""
    return (
        db.query(UserFeatureUsage)
        .filter(
            UserFeatureUsage.user_id == user_id,
            UserFeatureUsage.feature_code == feature_code,
            UserFeatureUsage.usage_date == date.today(),
            UserFeatureUsage.is_deleted == 0,
        )
        .with_for_update()
        .first()
    )


def increment_free_usage(db: Session, user_id: int, feature_code: str) -> int:
    """增加用户今日某功能的免费使用计数，返回当前次数。"""
    usage = _get_today_usage(db, user_id, feature_code)
    if usage is None:
        usage = UserFeatureUsage(
            user_id=user_id,
            feature_code=feature_code,
            usage_date=date.today(),
            count=0,
        )
        db.add(usage)
    usage.count += 1
    db.flush()
    return usage.count


def get_today_usage_count(db: Session, user_id: int, feature_code: str) -> int:
    """获取用户今日某功能已使用次数。"""
    usage = (
        db.query(UserFeatureUsage)
        .filter(
            UserFeatureUsage.user_id == user_id,
            UserFeatureUsage.feature_code == feature_code,
            UserFeatureUsage.usage_date == date.today(),
            UserFeatureUsage.is_deleted == 0,
        )
        .first()
    )
    return usage.count if usage else 0


def _has_consumed_today(db: Session, user_id: int, feature_code: str) -> bool:
    """检查用户今天是否已经为某功能扣过积分（UTC 自然日）。"""
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    count = (
        db.query(func.count(PointRecord.id))
        .filter(
            PointRecord.user_id == user_id,
            PointRecord.source == feature_code,
            PointRecord.type == "use",
            PointRecord.created_at >= start_of_today,
            PointRecord.created_at < end_of_today,
            PointRecord.is_deleted == 0,
        )
        .scalar()
        or 0
    )
    return count > 0


def check_and_consume(
    db: Session,
    user: UserModel,
    feature_code: str,
    consume: bool = True,
) -> dict:
    """评估用户是否有权限使用某功能，并在需要时扣减积分/消耗免费额度。

    评估优先级：
    1. admin 直接通过
    2. 功能未配置或已禁用 → 通过
    3. 生效会员覆盖该功能 → 通过（不扣积分）
    4. required_role 匹配 → 通过
    5. 每日免费额度内 → 通过
    6. 积分充足 → 扣积分通过
    7. 否则拒绝

    返回 dict，包含 allowed / reason / consumed / cost / balance /
    required_points / tier / commit_needed
    """
    fp = db.query(FeaturePermission).filter(FeaturePermission.code == feature_code).first()

    # 1/2. admin 或未配置/禁用
    if user.role == "admin":
        return {
            "allowed": True,
            "reason": "管理员权限",
            "consumed": False,
            "cost": 0,
            "balance": points_service.get_balance(db, user.id),
            "commit_needed": False,
        }

    if fp is None or fp.enabled == 0:
        return {
            "allowed": True,
            "reason": "功能未配置权限限制",
            "consumed": False,
            "cost": 0,
            "balance": points_service.get_balance(db, user.id),
            "commit_needed": False,
        }

    # 3. 生效会员
    membership = get_active_membership(db, user.id)
    if membership:
        # 精确匹配所需 tier
        if fp.required_tier and membership.tier_code == fp.required_tier:
            return {
                "allowed": True,
                "reason": f"{membership.tier_code} 会员权限",
                "consumed": False,
                "cost": 0,
                "balance": points_service.get_balance(db, user.id),
                "tier": membership.tier_code,
                "commit_needed": False,
            }
        # 套餐功能列表覆盖
        if tier_covers_feature(db, membership.tier_code, feature_code):
            return {
                "allowed": True,
                "reason": f"{membership.tier_code} 会员包含该功能",
                "consumed": False,
                "cost": 0,
                "balance": points_service.get_balance(db, user.id),
                "tier": membership.tier_code,
                "commit_needed": False,
            }

    # 4. required_role 匹配
    if fp.required_role and fp.required_role == user.role:
        return {
            "allowed": True,
            "reason": f"角色 {user.role} 权限",
            "consumed": False,
            "cost": 0,
            "balance": points_service.get_balance(db, user.id),
            "commit_needed": False,
        }

    # 5. 免费每日额度
    if fp.free_daily_limit and fp.free_daily_limit > 0:
        used = get_today_usage_count(db, user.id, feature_code)
        if used < fp.free_daily_limit:
            if consume:
                increment_free_usage(db, user.id, feature_code)
            return {
                "allowed": True,
                "reason": f"免费额度内（{used + 1}/{fp.free_daily_limit}）",
                "consumed": False,
                "cost": 0,
                "balance": points_service.get_balance(db, user.id),
                "commit_needed": consume,
            }

    # 6. 积分消费
    balance = points_service.get_balance(db, user.id)
    if fp.required_points == 0 or fp.consume_points == 0:
        return {
            "allowed": True,
            "reason": "免费功能" if fp.required_points == 0 else "仅校验权限",
            "consumed": False,
            "cost": 0,
            "balance": balance,
            "commit_needed": False,
        }

    # 按自然日计费：今天已扣过则免费
    if fp.consume_mode == "per_day" and _has_consumed_today(db, user.id, feature_code):
        return {
            "allowed": True,
            "reason": "今日已扣费，本次免费",
            "consumed": False,
            "cost": 0,
            "balance": balance,
            "commit_needed": False,
        }

    if balance < fp.required_points:
        reason = f"需要 {fp.required_points} 积分，当前余额 {balance}"
        if fp.required_tier:
            reason += f"，或开通 {fp.required_tier} 会员"
        return {
            "allowed": False,
            "reason": reason,
            "consumed": False,
            "cost": fp.required_points,
            "required_points": fp.required_points,
            "required_tier": fp.required_tier,
            "balance": balance,
            "commit_needed": False,
        }

    if consume:
        points_service.deduct_points(
            db,
            user.id,
            fp.required_points,
            source=feature_code,
            description=f"使用功能 {fp.name or feature_code}",
            record_type="use",
        )
        return {
            "allowed": True,
            "reason": f"已扣除 {fp.required_points} 积分",
            "consumed": True,
            "cost": fp.required_points,
            "balance": points_service.get_balance(db, user.id),
            "commit_needed": True,
        }

    return {
        "allowed": True,
        "reason": "积分充足",
        "consumed": False,
        "cost": fp.required_points,
        "balance": balance,
        "commit_needed": False,
    }


# ---------------------------------------------------------------------------
# 会员档位管理
# ---------------------------------------------------------------------------


def list_tiers(db: Session) -> list[MembershipTier]:
    """获取所有会员档位。"""
    return db.query(MembershipTier).order_by(MembershipTier.id.asc()).all()


def get_tier_by_code(db: Session, code: str) -> MembershipTier | None:
    """按 code 获取会员档位。"""
    return db.query(MembershipTier).filter(MembershipTier.code == code).first()


def create_tier(
    db: Session,
    code: str,
    name: str,
    price: int,
    duration_days: int,
    monthly_points_grant: int = 0,
    features: list[str] | None = None,
    description: str | None = None,
    enabled: bool = True,
) -> MembershipTier:
    """创建会员档位。"""
    if get_tier_by_code(db, code):
        raise ValueError(f"会员档位 code 已存在: {code}")

    tier = MembershipTier(
        code=code,
        name=name,
        price=price,
        duration_days=duration_days,
        monthly_points_grant=monthly_points_grant,
        features=features or [],
        description=description,
        enabled=1 if enabled else 0,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return tier


def update_tier(
    db: Session,
    tier_id: int,
    name: str | None = None,
    price: int | None = None,
    duration_days: int | None = None,
    monthly_points_grant: int | None = None,
    features: list[str] | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> MembershipTier:
    """更新会员档位。"""
    tier = db.query(MembershipTier).filter(MembershipTier.id == tier_id).first()
    if tier is None:
        raise MembershipTierNotFoundError("会员档位不存在")

    if name is not None:
        tier.name = name
    if price is not None:
        tier.price = price
    if duration_days is not None:
        tier.duration_days = duration_days
    if monthly_points_grant is not None:
        tier.monthly_points_grant = monthly_points_grant
    if features is not None:
        tier.features = features
    if description is not None:
        tier.description = description
    if enabled is not None:
        tier.enabled = 1 if enabled else 0

    db.commit()
    db.refresh(tier)
    return tier


def delete_tier(db: Session, tier_id: int) -> None:
    """删除会员档位。"""
    tier = db.query(MembershipTier).filter(MembershipTier.id == tier_id).first()
    if tier is None:
        raise MembershipTierNotFoundError("会员档位不存在")
    db.delete(tier)
    db.commit()


# ---------------------------------------------------------------------------
# 订单与会员开通
# ---------------------------------------------------------------------------


def create_order(
    db: Session,
    user_id: int,
    tier_code: str,
    amount: int,
    currency: str = "CNY",
    channel: str | None = None,
    out_trade_no: str | None = None,
) -> SubscriptionOrder:
    """创建待支付订单。"""
    order = SubscriptionOrder(
        user_id=user_id,
        tier_code=tier_code,
        amount=amount,
        currency=currency,
        channel=channel,
        out_trade_no=out_trade_no,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> SubscriptionOrder | None:
    """按 ID 获取订单。"""
    return db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order_id).first()


def confirm_order_payment(
    db: Session,
    order_id: int,
    out_trade_no: str | None = None,
) -> UserMembership:
    """确认订单支付并开通/续费会员。"""
    order = get_order(db, order_id)
    if order is None:
        raise SubscriptionOrderNotFoundError("订单不存在")
    if order.status == "paid":
        raise ValueError("订单已支付")

    tier = get_tier_by_code(db, order.tier_code)
    if tier is None:
        raise MembershipTierNotFoundError("会员档位不存在")

    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    if out_trade_no:
        order.out_trade_no = out_trade_no

    # 从当前生效会员的到期时间续费，否则从当前时间开始
    existing = get_active_membership(db, order.user_id)
    base_time = existing.expires_at if existing else datetime.now(timezone.utc)
    expires = base_time + timedelta(days=tier.duration_days)

    membership = UserMembership(
        user_id=order.user_id,
        tier_code=tier.code,
        status="active",
        starts_at=base_time,
        expires_at=expires,
    )
    db.add(membership)
    order.expires_at = expires

    # 赠送首月积分
    if tier.monthly_points_grant > 0:
        points_service.add_points(
            db,
            order.user_id,
            tier.monthly_points_grant,
            source="membership_monthly_grant",
            description=f"{tier.name} 月度积分",
            record_type="earn",
        )
        membership.last_grant_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(membership)
    return membership


def grant_membership_manually(
    db: Session,
    user_id: int,
    tier_code: str,
    duration_days: int,
    operator_id: int,
) -> UserMembership:
    """管理员手工开通会员。"""
    tier = get_tier_by_code(db, tier_code)
    if tier is None:
        raise MembershipTierNotFoundError("会员档位不存在")

    existing = get_active_membership(db, user_id)
    base_time = existing.expires_at if existing else datetime.now(timezone.utc)
    expires = base_time + timedelta(days=duration_days)

    membership = UserMembership(
        user_id=user_id,
        tier_code=tier_code,
        status="active",
        starts_at=base_time,
        expires_at=expires,
    )
    db.add(membership)

    # 赠送首月积分
    if tier.monthly_points_grant > 0:
        points_service.add_points(
            db,
            user_id,
            tier.monthly_points_grant,
            source="membership_monthly_grant",
            description=f"{tier.name} 月度积分（手工开通）",
            record_type="earn",
            operator_id=operator_id,
        )
        membership.last_grant_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(membership)
    return membership


# ---------------------------------------------------------------------------
# 用户会员查询与管理
# ---------------------------------------------------------------------------


def list_user_memberships(
    db: Session,
    user_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[UserMembership], int]:
    """查询用户会员记录列表。"""
    query = db.query(UserMembership).filter(UserMembership.is_deleted == 0)
    if user_id is not None:
        query = query.filter(UserMembership.user_id == user_id)
    if status:
        query = query.filter(UserMembership.status == status)

    total = query.count()
    items = (
        query.order_by(UserMembership.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def cancel_membership(db: Session, membership_id: int) -> None:
    """取消会员（标记为 cancelled，不续费）。"""
    membership = db.query(UserMembership).filter(
        UserMembership.id == membership_id, UserMembership.is_deleted == 0
    ).first()
    if membership is None:
        raise ValueError("会员记录不存在")
    membership.status = "cancelled"
    db.commit()


# ---------------------------------------------------------------------------
# 定时任务：过期与月度积分发放
# ---------------------------------------------------------------------------


def expire_memberships(db: Session) -> int:
    """将已过期的会员状态改为 expired，返回更新数量。"""
    now = datetime.now(timezone.utc)
    result = (
        db.query(UserMembership)
        .filter(
            UserMembership.status == "active",
            UserMembership.expires_at <= now,
            UserMembership.is_deleted == 0,
        )
        .update({"status": "expired"}, synchronize_session=False)
    )
    db.commit()
    return result


def grant_monthly_points_if_due(db: Session) -> int:
    """给活跃会员发放月度积分，返回发放人数。"""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    memberships = (
        db.query(UserMembership)
        .filter(
            UserMembership.status == "active",
            UserMembership.expires_at > now,
            UserMembership.is_deleted == 0,
            (
                (UserMembership.last_grant_at.is_(None))
                | (UserMembership.last_grant_at <= thirty_days_ago)
            ),
        )
        .all()
    )

    # 预加载未删除用户，避免为已删除用户发放积分
    user_ids = {m.user_id for m in memberships}
    active_user_ids = {
        u.id
        for u in db.query(UserModel.id).filter(
            UserModel.id.in_(user_ids), UserModel.is_deleted == 0
        )
    }

    count = 0
    for m in memberships:
        if m.user_id not in active_user_ids:
            continue
        tier = get_tier_by_code(db, m.tier_code)
        if tier is None or tier.monthly_points_grant <= 0:
            continue

        points_service.add_points(
            db,
            m.user_id,
            tier.monthly_points_grant,
            source="membership_monthly_grant",
            description=f"{tier.name} 月度积分",
            record_type="earn",
        )
        m.last_grant_at = now
        count += 1

    if count > 0:
        db.commit()
    return count
