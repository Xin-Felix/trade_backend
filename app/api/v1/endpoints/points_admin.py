"""管理端积分系统接口。

提供积分规则管理、积分明细查询、手工调整积分、功能权限管理。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.points_admin import (
    FeaturePermissionCreateRequest,
    FeaturePermissionItem,
    FeaturePermissionListResponse,
    FeaturePermissionUpdateRequest,
    OperationResponse,
    PointAdjustRequest,
    PointAdjustResponse,
    PointRecordAdminListResponse,
    PointRecordSourcesResponse,
    PointRuleCreateRequest,
    PointRuleItem,
    PointRuleListResponse,
    PointRuleUpdateRequest,
)
from app.schemas.user import User
from app.services import points_service
from app.utils.response import build_list_response

router = APIRouter(dependencies=[Depends(require_admin)])


def _get_db_user(db: Session, public_id: str) -> UserModel:
    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def _record_to_dict(record: points_service.PointRecord) -> dict:
    """将积分明细转换为字典，并附加用户信息（要求已 eager load）。"""
    return {
        "id": record.id,
        "user_id": record.user_id,
        "user_public_id": record.user.public_id if record.user else None,
        "user_email": record.user.email if record.user else None,
        "type": record.type,
        "amount": record.amount,
        "balance_after": record.balance_after,
        "source": record.source,
        "description": record.description,
        "operator_id": record.operator_id,
        "operator_email": record.operator.email if record.operator else None,
        "created_at": record.created_at,
    }


# ---------------------------------------------------------------------------
# 积分规则管理
# ---------------------------------------------------------------------------


@router.get("/point-rules", response_model=PointRuleListResponse)
async def list_point_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取积分规则列表。"""
    rules = points_service.list_rules(db)
    return build_list_response(rules, PointRuleListResponse, PointRuleItem)


@router.post("/point-rules", response_model=PointRuleListResponse)
async def create_point_rule(
    payload: PointRuleCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建积分规则。"""
    try:
        points_service.create_rule(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rules = points_service.list_rules(db)
    return build_list_response(rules, PointRuleListResponse, PointRuleItem)


@router.put("/point-rules/{rule_id}", response_model=PointRuleListResponse)
async def update_point_rule(
    rule_id: int,
    payload: PointRuleUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新积分规则。"""
    try:
        points_service.update_rule(db, rule_id, **payload.model_dump(exclude_unset=True))
    except points_service.PointRuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rules = points_service.list_rules(db)
    return build_list_response(rules, PointRuleListResponse, PointRuleItem)


@router.delete("/point-rules/{rule_id}", response_model=OperationResponse)
async def delete_point_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除积分规则。"""
    try:
        points_service.delete_rule(db, rule_id)
    except points_service.PointRuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OperationResponse(message="删除成功")


# ---------------------------------------------------------------------------
# 积分明细与手工调整
# ---------------------------------------------------------------------------


@router.get("/point-records", response_model=PointRecordAdminListResponse)
async def list_point_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str | None = Query(None, description="用户 public_id"),
    record_type: str | None = Query(None, description="变动类型"),
    source: str | None = Query(None, description="来源标识"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理端查询所有积分明细。"""
    records, total = points_service.list_all_records(
        db,
        user_id=user_id,
        record_type=record_type,
        source=source,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return PointRecordAdminListResponse(
        data={
            "list": [_record_to_dict(r) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/point-records/sources", response_model=PointRecordSourcesResponse)
async def list_point_record_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取积分明细中所有不重复的 source，用于筛选下拉框。"""
    sources = points_service.list_record_sources(db)
    return PointRecordSourcesResponse(data=sources)


@router.post("/point-records/adjust", response_model=PointAdjustResponse)
async def adjust_points(
    payload: PointAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员手工调整用户积分。"""
    operator = _get_db_user(db, current_user.id)
    target_user = (
        db.query(UserModel)
        .filter(UserModel.public_id == payload.user_id, UserModel.is_deleted == 0)
        .first()
    )
    if target_user is None:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    try:
        point, record = points_service.adjust_points(
            db,
            user_id=target_user.public_id,
            amount=payload.amount,
            description=payload.description,
            operator_id=operator.id,
        )
    except points_service.InsufficientPointsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PointAdjustResponse(
        data={
            "balance": point.balance,
            "record_id": record.id,
        }
    )


# ---------------------------------------------------------------------------
# 功能权限管理
# ---------------------------------------------------------------------------


@router.get("/feature-permissions", response_model=FeaturePermissionListResponse)
async def list_feature_permissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取功能权限列表。"""
    fps = points_service.list_feature_permissions(db)
    return build_list_response(fps, FeaturePermissionListResponse, FeaturePermissionItem)


@router.post("/feature-permissions", response_model=FeaturePermissionListResponse)
async def create_feature_permission(
    payload: FeaturePermissionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建功能权限。"""
    try:
        points_service.create_feature_permission(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fps = points_service.list_feature_permissions(db)
    return build_list_response(fps, FeaturePermissionListResponse, FeaturePermissionItem)


@router.put("/feature-permissions/{fp_id}", response_model=FeaturePermissionListResponse)
async def update_feature_permission(
    fp_id: int,
    payload: FeaturePermissionUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新功能权限。"""
    try:
        points_service.update_feature_permission(
            db, fp_id, **payload.model_dump(exclude_unset=True)
        )
    except points_service.FeaturePermissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fps = points_service.list_feature_permissions(db)
    return build_list_response(fps, FeaturePermissionListResponse, FeaturePermissionItem)


@router.delete("/feature-permissions/{fp_id}", response_model=OperationResponse)
async def delete_feature_permission(
    fp_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除功能权限。"""
    try:
        points_service.delete_feature_permission(db, fp_id)
    except points_service.FeaturePermissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OperationResponse(message="删除成功")
