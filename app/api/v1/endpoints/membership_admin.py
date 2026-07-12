"""会员订阅管理接口。

提供会员档位、订阅订单、用户会员的 CRUD 和管理操作。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.membership import (
    MembershipTierCreateRequest,
    MembershipTierItem,
    MembershipTierListResponse,
    MembershipTierUpdateRequest,
    OperationResponse,
    SubscriptionOrderConfirmRequest,
    SubscriptionOrderCreateRequest,
    SubscriptionOrderItem,
    SubscriptionOrderListResponse,
    UserMembershipGrantRequest,
    UserMembershipItem,
    UserMembershipListResponse,
)
from app.schemas.user import User
from app.services import membership_service
from app.utils.response import build_list_response

router = APIRouter(dependencies=[Depends(require_admin)])


def _get_db_user(db: Session, public_id: str) -> UserModel:
    user = db.query(UserModel).filter(UserModel.public_id == public_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


# ---------------------------------------------------------------------------
# 会员档位管理
# ---------------------------------------------------------------------------


@router.get("/tiers", response_model=MembershipTierListResponse)
async def list_tiers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取会员档位列表。"""
    tiers = membership_service.list_tiers(db)
    return build_list_response(tiers, MembershipTierListResponse, MembershipTierItem)


@router.post("/tiers", response_model=MembershipTierListResponse)
async def create_tier(
    payload: MembershipTierCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建会员档位。"""
    try:
        membership_service.create_tier(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    tiers = membership_service.list_tiers(db)
    return build_list_response(tiers, MembershipTierListResponse, MembershipTierItem)


@router.put("/tiers/{tier_id}", response_model=MembershipTierListResponse)
async def update_tier(
    tier_id: int,
    payload: MembershipTierUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新会员档位。"""
    try:
        membership_service.update_tier(tier_id=tier_id, db=db, **payload.model_dump(exclude_none=True))
    except membership_service.MembershipTierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    tiers = membership_service.list_tiers(db)
    return build_list_response(tiers, MembershipTierListResponse, MembershipTierItem)


@router.delete("/tiers/{tier_id}", response_model=OperationResponse)
async def delete_tier(
    tier_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除会员档位。"""
    try:
        membership_service.delete_tier(db, tier_id)
    except membership_service.MembershipTierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OperationResponse(message="删除成功")


# ---------------------------------------------------------------------------
# 订阅订单管理
# ---------------------------------------------------------------------------


def _order_to_dict(order, db: Session) -> dict:
    user = db.query(UserModel).filter(UserModel.id == order.user_id).first()
    return {
        "id": order.id,
        "user_id": order.user_id,
        "user_public_id": user.public_id if user else None,
        "user_email": user.email if user else None,
        "tier_code": order.tier_code,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "channel": order.channel,
        "out_trade_no": order.out_trade_no,
        "paid_at": order.paid_at,
        "expires_at": order.expires_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


@router.get("/orders", response_model=SubscriptionOrderListResponse)
async def list_orders(
    user_id: str | None = Query(None, description="用户 public_id"),
    status: str | None = Query(None, description="订单状态"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取订阅订单列表。"""
    query = db.query(membership_service.SubscriptionOrder)
    if user_id:
        target = db.query(UserModel).filter(UserModel.public_id == user_id).first()
        if target is None:
            return SubscriptionOrderListResponse(data=[])
        query = query.filter(membership_service.SubscriptionOrder.user_id == target.id)
    if status:
        query = query.filter(membership_service.SubscriptionOrder.status == status)

    orders = query.order_by(membership_service.SubscriptionOrder.created_at.desc()).all()
    return build_list_response(
        orders,
        SubscriptionOrderListResponse,
        SubscriptionOrderItem,
        converter=lambda o: _order_to_dict(o, db),
    )


@router.post("/orders", response_model=SubscriptionOrderListResponse)
async def create_order(
    payload: SubscriptionOrderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建订阅订单。"""
    target = db.query(UserModel).filter(UserModel.public_id == payload.user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    membership_service.create_order(db, **{**payload.model_dump(), "user_id": target.id})
    orders = (
        db.query(membership_service.SubscriptionOrder)
        .order_by(membership_service.SubscriptionOrder.created_at.desc())
        .all()
    )
    return build_list_response(
        orders,
        SubscriptionOrderListResponse,
        SubscriptionOrderItem,
        converter=lambda o: _order_to_dict(o, db),
    )


@router.post("/orders/{order_id}/confirm", response_model=OperationResponse)
async def confirm_order(
    order_id: int,
    payload: SubscriptionOrderConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """确认订单支付并开通会员。"""
    try:
        membership_service.confirm_order_payment(
            db, order_id, out_trade_no=payload.out_trade_no
        )
    except membership_service.SubscriptionOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, membership_service.MembershipTierNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationResponse(message="支付确认成功，会员已开通")


# ---------------------------------------------------------------------------
# 用户会员管理
# ---------------------------------------------------------------------------


def _membership_to_dict(membership, db: Session) -> dict:
    user = db.query(UserModel).filter(UserModel.id == membership.user_id).first()
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "user_public_id": user.public_id if user else None,
        "user_email": user.email if user else None,
        "tier_code": membership.tier_code,
        "status": membership.status,
        "starts_at": membership.starts_at,
        "expires_at": membership.expires_at,
        "auto_renew": membership.auto_renew,
        "last_grant_at": membership.last_grant_at,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


@router.get("/users", response_model=UserMembershipListResponse)
async def list_user_memberships(
    user_id: str | None = Query(None, description="用户 public_id"),
    status: str | None = Query(None, description="会员状态"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户会员记录列表。"""
    db_user_id = None
    if user_id:
        target = db.query(UserModel).filter(UserModel.public_id == user_id).first()
        if target is None:
            return UserMembershipListResponse(data=[])
        db_user_id = target.id

    memberships, _ = membership_service.list_user_memberships(
        db, user_id=db_user_id, status=status, skip=0, limit=1000
    )
    return build_list_response(
        memberships,
        UserMembershipListResponse,
        UserMembershipItem,
        converter=lambda m: _membership_to_dict(m, db),
    )


@router.post("/users/grant", response_model=OperationResponse)
async def grant_membership(
    payload: UserMembershipGrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员手工开通会员。"""
    operator = _get_db_user(db, current_user.id)
    target = db.query(UserModel).filter(UserModel.public_id == payload.user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    try:
        membership_service.grant_membership_manually(
            db,
            user_id=target.id,
            tier_code=payload.tier_code,
            duration_days=payload.duration_days,
            operator_id=operator.id,
        )
    except membership_service.MembershipTierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OperationResponse(message="会员开通成功")


@router.post("/users/{membership_id}/cancel", response_model=OperationResponse)
async def cancel_membership(
    membership_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消会员（标记为 cancelled）。"""
    try:
        membership_service.cancel_membership(db, membership_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationResponse(message="会员已取消")


# ---------------------------------------------------------------------------
# 手动触发定时任务
# ---------------------------------------------------------------------------


@router.post("/tasks/expire", response_model=OperationResponse)
async def expire_memberships_task(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发会员过期检查。"""
    count = membership_service.expire_memberships(db)
    return OperationResponse(message=f"已处理 {count} 条过期会员")


@router.post("/tasks/grant-monthly", response_model=OperationResponse)
async def grant_monthly_points_task(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发月度积分发放。"""
    count = membership_service.grant_monthly_points_if_due(db)
    return OperationResponse(message=f"已向 {count} 位会员发放月度积分")
