"""用户端积分系统接口。

提供当前用户积分余额、积分明细和功能权限检查。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.points import (
    FeatureAccessResponse,
    PointBalanceResponse,
    PointRecordItem,
    PointRecordListResponse,
)
from app.schemas.user import User
from app.services import membership_service, points_service

router = APIRouter()


def _get_db_user(db: Session, public_id: str) -> UserModel:
    """根据 public_id 获取数据库用户对象。"""
    user = db.query(UserModel).filter(UserModel.public_id == public_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


@router.get("/balance", response_model=PointBalanceResponse)
async def get_point_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户积分余额。"""
    db_user = _get_db_user(db, user.id)
    summary = points_service.get_user_point_summary(db, db_user.id)
    return PointBalanceResponse(data=summary)


@router.get("/records", response_model=PointRecordListResponse)
async def get_point_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户积分明细。"""
    db_user = _get_db_user(db, user.id)
    records, total = points_service.get_records(
        db, db_user.id, skip=(page - 1) * page_size, limit=page_size
    )
    items = [
        PointRecordItem(
            id=r.id,
            type=r.type,
            amount=r.amount,
            balance_after=r.balance_after,
            source=r.source,
            description=r.description,
            created_at=r.created_at,
        )
        for r in records
    ]
    return PointRecordListResponse(
        data={"list": items, "total": total, "page": page, "page_size": page_size}
    )


@router.get("/features/{feature_code}", response_model=FeatureAccessResponse)
async def check_feature_access(
    feature_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检查当前用户是否有权限访问某功能（含会员、角色、免费额度、积分）。"""
    db_user = _get_db_user(db, user.id)
    result = membership_service.check_and_consume(
        db, db_user, feature_code, consume=False
    )
    return FeatureAccessResponse(data=result)
