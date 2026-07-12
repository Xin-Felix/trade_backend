"""积分系统服务层。

提供积分余额查询、积分增减、积分规则管理、功能权限管理。
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.points import FeaturePermission, PointRecord, PointRule, UserPoint
from app.models.user import User as UserModel


class InsufficientPointsError(Exception):
    """积分不足"""

    def __init__(self, balance: int, required: int):
        self.balance = balance
        self.required = required
        super().__init__(f"积分不足，当前余额 {balance}，需要 {required}")


class PointRuleNotFoundError(Exception):
    """积分规则不存在"""
    pass


class FeaturePermissionNotFoundError(Exception):
    """功能权限不存在"""
    pass


def _resolve_user_id(db: Session, public_id: str) -> int:
    """根据 public_id 获取用户数据库自增 ID。"""
    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise ValueError(f"用户不存在: {public_id}")
    return user.id


_UNSET = object()


def get_or_create_user_point(db: Session, user_id: int) -> UserPoint:
    """获取或创建用户积分账户（带行锁）。"""
    point = (
        db.query(UserPoint)
        .filter(UserPoint.user_id == user_id, UserPoint.is_deleted == 0)
        .with_for_update()
        .first()
    )
    if point is None:
        point = UserPoint(user_id=user_id, balance=0, total_earned=0, total_used=0)
        db.add(point)
        db.flush()
    return point


def get_balance(db: Session, user_id: int) -> int:
    """获取用户当前积分余额。"""
    point = get_or_create_user_point(db, user_id)
    return point.balance


def get_user_point_summary(db: Session, user_id: int) -> dict:
    """获取用户积分汇总。"""
    point = get_or_create_user_point(db, user_id)
    return {
        "balance": point.balance,
        "total_earned": point.total_earned,
        "total_used": point.total_used,
        "updated_at": point.updated_at,
    }


def add_points(
    db: Session,
    user_id: int,
    amount: int,
    source: str,
    description: str,
    record_type: str = "earn",
    operator_id: int | None = None,
) -> tuple[UserPoint, PointRecord]:
    """给用户增加积分。

    :param amount: 正整数
    :param record_type: earn / refund / manual
    """
    if amount <= 0:
        raise ValueError("增加的积分必须为正数")

    point = get_or_create_user_point(db, user_id)
    point.balance += amount
    point.total_earned += amount
    record = PointRecord(
        user_id=user_id,
        type=record_type,
        amount=amount,
        balance_after=point.balance,
        source=source,
        description=description,
        operator_id=operator_id,
    )
    db.add(record)
    db.flush()
    return point, record


def deduct_points(
    db: Session,
    user_id: int,
    amount: int,
    source: str,
    description: str,
    record_type: str = "use",
    operator_id: int | None = None,
) -> tuple[UserPoint, PointRecord]:
    """扣减用户积分。

    :param amount: 正整数
    :param record_type: use / deduct
    :raises InsufficientPointsError: 余额不足时抛出
    """
    if amount <= 0:
        raise ValueError("扣减的积分必须为正数")

    point = get_or_create_user_point(db, user_id)
    if point.balance < amount:
        raise InsufficientPointsError(point.balance, amount)

    point.balance -= amount
    point.total_used += amount
    record = PointRecord(
        user_id=user_id,
        type=record_type,
        amount=-amount,
        balance_after=point.balance,
        source=source,
        description=description,
        operator_id=operator_id,
    )
    db.add(record)
    db.flush()
    return point, record


def adjust_points(
    db: Session,
    user_id: str,
    amount: int,
    description: str,
    operator_id: int,
) -> tuple[UserPoint, PointRecord]:
    """管理员手工调整积分（可为正或负）。user_id 使用 public_id。"""
    if amount == 0:
        raise ValueError("调整积分不能为 0")

    db_user_id = _resolve_user_id(db, user_id)
    point = get_or_create_user_point(db, db_user_id)
    new_balance = point.balance + amount
    if new_balance < 0:
        raise InsufficientPointsError(point.balance, abs(amount))

    point.balance = new_balance
    if amount > 0:
        point.total_earned += amount
    else:
        point.total_used += abs(amount)
    record = PointRecord(
        user_id=db_user_id,
        type="manual",
        amount=amount,
        balance_after=point.balance,
        source="manual",
        description=description,
        operator_id=operator_id,
    )
    db.add(record)
    db.flush()
    return point, record


def get_records(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[PointRecord], int]:
    """获取用户积分明细（分页）。"""
    query = db.query(PointRecord).filter(
        PointRecord.user_id == user_id,
        PointRecord.is_deleted == 0,
    )
    total = query.count()
    records = (
        query.order_by(PointRecord.created_at.desc(), PointRecord.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return records, total


def list_all_records(
    db: Session,
    user_id: str | None = None,
    record_type: str | None = None,
    source: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[PointRecord], int]:
    """管理端：查询所有积分明细。user_id 使用 public_id，用户不存在时返回空列表。"""
    query = db.query(PointRecord).options(
        joinedload(PointRecord.user),
        joinedload(PointRecord.operator),
    ).filter(PointRecord.is_deleted == 0)
    if user_id:
        user = (
            db.query(UserModel)
            .filter(UserModel.public_id == user_id, UserModel.is_deleted == 0)
            .first()
        )
        if user is None:
            return [], 0
        query = query.filter(PointRecord.user_id == user.id)
    if record_type:
        query = query.filter(PointRecord.type == record_type)
    if source:
        query = query.filter(PointRecord.source.ilike(f"%{source}%"))

    total = query.with_entities(func.count(PointRecord.id)).scalar()
    records = (
        query.order_by(PointRecord.created_at.desc(), PointRecord.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return records, total


def list_record_sources(db: Session) -> list[str]:
    """获取积分明细中所有不重复的 source（排除空值），按字母序返回。"""
    rows = (
        db.query(PointRecord.source)
        .filter(PointRecord.source.isnot(None))
        .filter(PointRecord.source != "")
        .distinct()
        .order_by(PointRecord.source.asc())
        .all()
    )
    return [row.source for row in rows if row.source]


# ---------------------------------------------------------------------------
# 积分规则管理
# ---------------------------------------------------------------------------


def list_rules(db: Session, enabled_only: bool = False) -> list[PointRule]:
    """获取积分规则列表。"""
    query = db.query(PointRule)
    if enabled_only:
        query = query.filter(PointRule.enabled == 1)
    return query.order_by(PointRule.id.asc()).all()


def get_rule_by_code(db: Session, code: str) -> PointRule | None:
    """按 code 获取规则。"""
    return db.query(PointRule).filter(PointRule.code == code).first()


def create_rule(
    db: Session,
    code: str,
    name: str,
    rule_type: str,
    amount: int,
    description: str | None = None,
    daily_limit: int | None = None,
    enabled: bool = True,
) -> PointRule:
    """创建积分规则。"""
    if db.query(PointRule).filter(PointRule.code == code).first():
        raise ValueError(f"规则 code 已存在: {code}")

    rule = PointRule(
        code=code,
        name=name,
        rule_type=rule_type,
        amount=amount,
        description=description,
        daily_limit=daily_limit,
        enabled=1 if enabled else 0,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session,
    rule_id: int,
    name: str | object = _UNSET,
    rule_type: str | object = _UNSET,
    amount: int | object = _UNSET,
    description: str | None | object = _UNSET,
    daily_limit: int | None | object = _UNSET,
    enabled: bool | object = _UNSET,
) -> PointRule:
    """更新积分规则。"""
    rule = db.query(PointRule).filter(PointRule.id == rule_id).first()
    if rule is None:
        raise PointRuleNotFoundError("规则不存在")

    if name is not _UNSET:
        rule.name = name
    if rule_type is not _UNSET:
        rule.rule_type = rule_type
    if amount is not _UNSET:
        rule.amount = amount
    if description is not _UNSET:
        rule.description = description
    if daily_limit is not _UNSET:
        rule.daily_limit = daily_limit
    if enabled is not _UNSET:
        rule.enabled = 1 if enabled else 0

    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    """删除积分规则。"""
    rule = db.query(PointRule).filter(PointRule.id == rule_id).first()
    if rule is None:
        raise PointRuleNotFoundError("规则不存在")
    db.delete(rule)
    db.commit()


# ---------------------------------------------------------------------------
# 功能权限管理
# ---------------------------------------------------------------------------


def list_feature_permissions(db: Session, enabled_only: bool = False) -> list[FeaturePermission]:
    """获取功能权限列表。"""
    query = db.query(FeaturePermission)
    if enabled_only:
        query = query.filter(FeaturePermission.enabled == 1)
    return query.order_by(FeaturePermission.id.asc()).all()


def get_feature_permission_by_code(db: Session, code: str) -> FeaturePermission | None:
    """按 code 获取功能权限。"""
    return db.query(FeaturePermission).filter(FeaturePermission.code == code).first()


def create_feature_permission(
    db: Session,
    code: str,
    name: str,
    description: str | None = None,
    required_points: int = 0,
    required_role: str | None = None,
    required_tier: str | None = None,
    free_daily_limit: int = 0,
    consume_points: bool = True,
    consume_mode: str = "per_call",
    enabled: bool = True,
) -> FeaturePermission:
    """创建功能权限。"""
    if db.query(FeaturePermission).filter(FeaturePermission.code == code).first():
        raise ValueError(f"功能权限 code 已存在: {code}")

    fp = FeaturePermission(
        code=code,
        name=name,
        description=description,
        required_points=required_points,
        required_role=required_role,
        required_tier=required_tier,
        free_daily_limit=free_daily_limit,
        consume_points=1 if consume_points else 0,
        consume_mode=consume_mode if consume_mode in ("per_call", "per_day") else "per_call",
        enabled=1 if enabled else 0,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


def update_feature_permission(
    db: Session,
    fp_id: int,
    name: str | object = _UNSET,
    description: str | None | object = _UNSET,
    required_points: int | object = _UNSET,
    required_role: str | None | object = _UNSET,
    required_tier: str | None | object = _UNSET,
    free_daily_limit: int | object = _UNSET,
    consume_points: bool | object = _UNSET,
    consume_mode: str | object = _UNSET,
    enabled: bool | object = _UNSET,
) -> FeaturePermission:
    """更新功能权限。"""
    fp = db.query(FeaturePermission).filter(FeaturePermission.id == fp_id).first()
    if fp is None:
        raise FeaturePermissionNotFoundError("功能权限不存在")

    if name is not _UNSET:
        fp.name = name
    if description is not _UNSET:
        fp.description = description
    if required_points is not _UNSET:
        fp.required_points = required_points
    if required_role is not _UNSET:
        fp.required_role = required_role
    if required_tier is not _UNSET:
        fp.required_tier = required_tier
    if free_daily_limit is not _UNSET:
        fp.free_daily_limit = free_daily_limit
    if consume_points is not _UNSET:
        fp.consume_points = 1 if consume_points else 0
    if consume_mode is not _UNSET:
        fp.consume_mode = consume_mode if consume_mode in ("per_call", "per_day") else "per_call"
    if enabled is not _UNSET:
        fp.enabled = 1 if enabled else 0

    db.commit()
    db.refresh(fp)
    return fp


def delete_feature_permission(db: Session, fp_id: int) -> None:
    """删除功能权限。"""
    fp = db.query(FeaturePermission).filter(FeaturePermission.id == fp_id).first()
    if fp is None:
        raise FeaturePermissionNotFoundError("功能权限不存在")
    db.delete(fp)
    db.commit()


def check_feature_access(
    db: Session,
    user: UserModel,
    feature_code: str,
) -> dict:
    """检查用户是否有权限访问某功能。

    返回 {"allowed": bool, "reason": str, "required_points": int, "balance": int}
    """
    fp = get_feature_permission_by_code(db, feature_code)
    if fp is None or fp.enabled == 0:
        # 未配置则默认允许
        return {
            "allowed": True,
            "reason": "功能未配置权限限制",
            "required_points": 0,
            "balance": get_balance(db, user.id),
        }

    # 角色检查（admin 默认拥有所有权限）
    if user.role == "admin":
        return {
            "allowed": True,
            "reason": "管理员权限",
            "required_points": fp.required_points,
            "balance": get_balance(db, user.id),
        }

    if fp.required_role and fp.required_role != user.role:
        return {
            "allowed": False,
            "reason": f"需要角色 {fp.required_role}",
            "required_points": fp.required_points,
            "balance": get_balance(db, user.id),
        }

    balance = get_balance(db, user.id)
    if fp.required_points > 0 and balance < fp.required_points:
        return {
            "allowed": False,
            "reason": f"需要 {fp.required_points} 积分",
            "required_points": fp.required_points,
            "balance": balance,
        }

    return {
        "allowed": True,
        "reason": "权限校验通过",
        "required_points": fp.required_points,
        "balance": balance,
    }


def consume_feature_access(
    db: Session,
    user: UserModel,
    feature_code: str,
) -> dict:
    """检查并消耗功能所需积分。

    先调用 check_feature_access，如果通过且需要积分则扣减。
    """
    result = check_feature_access(db, user, feature_code)
    if not result["allowed"]:
        return result

    fp = get_feature_permission_by_code(db, feature_code)
    if fp and fp.required_points > 0 and user.role != "admin":
        deduct_points(
            db,
            user.id,
            fp.required_points,
            source=feature_code,
            description=f"使用功能 {fp.name}",
            record_type="use",
        )
        result["balance"] = get_balance(db, user.id)
        result["reason"] = f"已扣除 {fp.required_points} 积分"

    return result


# ---------------------------------------------------------------------------
# 按规则发放积分（带每日上限）
# ---------------------------------------------------------------------------


def apply_rule(
    db: Session,
    user_id: int,
    rule_code: str,
    description: str | None = None,
) -> tuple[UserPoint, PointRecord] | None:
    """按规则给用户发放积分，受每日上限限制。

    如果规则不存在、未启用或已达每日上限，返回 None。
    """
    rule = get_rule_by_code(db, rule_code)
    if rule is None or rule.enabled == 0 or rule.rule_type != "earn":
        return None

    if rule.daily_limit is not None:
        now = datetime.now(timezone.utc)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)
        count_today = (
            db.query(func.count(PointRecord.id))
            .filter(
                PointRecord.user_id == user_id,
                PointRecord.source == rule_code,
                PointRecord.type == "earn",
                PointRecord.created_at >= start_of_today,
                PointRecord.created_at < end_of_today,
            )
            .scalar()
            or 0
        )
        if count_today >= rule.daily_limit:
            return None

    desc = description or rule.description or rule.name
    return add_points(
        db,
        user_id=user_id,
        amount=rule.amount,
        source=rule_code,
        description=desc,
        record_type="earn",
    )
