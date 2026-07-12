"""用户端 AI 仓位建议接口。

- 生效会员：每日 19:00 自动生成，可直接查看。
- 非会员积分用户：可在 App 端手动点击生成，按日扣减积分。
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_feature
from app.db.base import get_db
from app.models.ai_position_advice import AiPositionAdvice
from app.models.user import User as UserModel
from app.schemas.ai_position_advice import (
    AiPositionAdviceDetailResponse,
    AiPositionAdviceListResponse,
    OperationResponse,
)
from app.schemas.user import User
from app.services import ai_position_advice_service

router = APIRouter()


def _get_db_user(db: Session, public_id: str) -> UserModel:
    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def _advice_to_dict(advice) -> dict:
    return {
        "id": advice.id,
        "user_id": advice.user_id,
        "report_date": advice.report_date.isoformat() if advice.report_date else None,
        "status": advice.status,
        "summary": advice.summary,
        "content": advice.content,
        "error_message": advice.error_message,
        "created_at": advice.created_at.isoformat() if advice.created_at else None,
        "updated_at": advice.updated_at.isoformat() if advice.updated_at else None,
    }


@router.get("/today", response_model=AiPositionAdviceDetailResponse)
async def get_today_position_advice(
    user: User = Depends(require_feature("ai_position_advice", consume=False)),
    db: Session = Depends(get_db),
):
    """获取当前登录用户今日的仓位建议。"""
    db_user = _get_db_user(db, user.id)
    advice = (
        db.query(AiPositionAdvice)
        .filter(
            AiPositionAdvice.user_id == db_user.id,
            AiPositionAdvice.report_date == date.today(),
            AiPositionAdvice.is_deleted == 0,
        )
        .first()
    )
    if advice is None or advice.status != "success":
        raise HTTPException(status_code=404, detail="今日仓位建议尚未生成，请稍后再试")
    return AiPositionAdviceDetailResponse(data=_advice_to_dict(advice))


@router.get("", response_model=AiPositionAdviceListResponse)
async def list_my_position_advices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_feature("ai_position_advice", consume=False)),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的历史仓位建议列表（按日期倒序）。"""
    db_user = _get_db_user(db, user.id)
    items, total = ai_position_advice_service.get_user_advices(
        db, db_user.id, page=page, page_size=page_size
    )
    return AiPositionAdviceListResponse(
        data={
            "list": [_advice_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{advice_id}", response_model=AiPositionAdviceDetailResponse)
async def get_position_advice_detail(
    advice_id: int,
    user: User = Depends(require_feature("ai_position_advice", consume=False)),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的仓位建议详情。"""
    db_user = _get_db_user(db, user.id)
    advice = ai_position_advice_service.get_advice_detail(db, advice_id, user_id=db_user.id)
    if advice is None:
        raise HTTPException(status_code=404, detail="仓位建议记录不存在")
    return AiPositionAdviceDetailResponse(data=_advice_to_dict(advice))


@router.post("/generate", response_model=OperationResponse)
async def generate_my_position_advice(
    user: User = Depends(require_feature("ai_position_advice", consume=True)),
    db: Session = Depends(get_db),
):
    """当前登录用户手动生成今日仓位建议（积分用户按需扣减积分）。"""
    db_user = _get_db_user(db, user.id)
    advice = await ai_position_advice_service.generate_position_advice_for_user(
        db, db_user.id, date.today()
    )
    return OperationResponse(
        message=f"仓位建议已生成，状态：{advice.status}"
    )
