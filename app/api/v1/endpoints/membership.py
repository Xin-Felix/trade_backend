"""用户端会员订阅接口。

提供当前登录用户自身的会员状态查询。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.membership import MembershipStatusResponse
from app.schemas.user import User
from app.services import membership_service

router = APIRouter()


def _get_db_user(db: Session, public_id: str) -> UserModel:
    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


@router.get("/status", response_model=MembershipStatusResponse)
async def get_membership_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的会员状态。"""
    db_user = _get_db_user(db, user.id)
    active = membership_service.get_active_membership(db, db_user.id)
    balance = membership_service.points_service.get_balance(db, db_user.id)

    return MembershipStatusResponse(
        data={
            "active": active is not None,
            "tier_code": active.tier_code if active else None,
            "expires_at": active.expires_at if active else None,
            "balance": balance,
        }
    )
