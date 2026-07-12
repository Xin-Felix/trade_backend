"""AI 仓位建议后台管理接口。

供管理员查看仓位建议记录、手动触发生成、重试失败记录。
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.base import get_db
from app.models.ai_position_advice import AiPositionAdvice
from app.models.user import User as UserModel
from app.schemas.ai_position_advice import (
    AiPositionAdviceDetailResponse,
    AiPositionAdviceListResponse,
    AiPositionAdviceUpdateRequest,
    OperationResponse,
)
from app.services import ai_position_advice_service

router = APIRouter(dependencies=[Depends(require_admin)])


class GenerateRequest(BaseModel):
    """手动生成请求"""

    user_public_id: Optional[str] = None
    report_date: Optional[str] = None  # YYYYMMDD


def _advice_to_dict(advice: AiPositionAdvice, db: Session) -> dict:
    user = (
        db.query(UserModel)
        .filter(UserModel.id == advice.user_id, UserModel.is_deleted == 0)
        .first()
    )
    return {
        "id": advice.id,
        "user_id": advice.user_id,
        "user_public_id": user.public_id if user else None,
        "user_email": user.email if user else None,
        "report_date": advice.report_date.isoformat() if advice.report_date else None,
        "status": advice.status,
        "summary": advice.summary,
        "content": advice.content,
        "error_message": advice.error_message,
        "created_at": advice.created_at.isoformat() if advice.created_at else None,
        "updated_at": advice.updated_at.isoformat() if advice.updated_at else None,
    }


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYYMMDD") from exc


@router.get("", response_model=AiPositionAdviceListResponse)
async def list_position_advices(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
    status: Optional[str] = Query(None, description="状态"),
    keyword: Optional[str] = Query(None, description="邮箱/名称搜索"),
    user_public_id: Optional[str] = Query(None, description="用户 public_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """仓位建议记录列表（分页 + 筛选 + 搜索）。"""
    target_date = _parse_date(report_date)

    query = (
        db.query(AiPositionAdvice)
        .join(UserModel, AiPositionAdvice.user_id == UserModel.id)
        .filter(AiPositionAdvice.is_deleted == 0, UserModel.is_deleted == 0)
    )
    if target_date:
        query = query.filter(AiPositionAdvice.report_date == target_date)
    if status:
        query = query.filter(AiPositionAdvice.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(UserModel.email.ilike(like), UserModel.name.ilike(like)))
    if user_public_id:
        query = query.filter(UserModel.public_id == user_public_id)

    total = query.count()
    items = (
        query.order_by(AiPositionAdvice.report_date.desc(), AiPositionAdvice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AiPositionAdviceListResponse(
        data={
            "list": [_advice_to_dict(item, db) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{advice_id}", response_model=AiPositionAdviceDetailResponse)
async def get_position_advice_detail(
    advice_id: int,
    db: Session = Depends(get_db),
):
    """仓位建议详情。"""
    advice = (
        db.query(AiPositionAdvice)
        .filter(AiPositionAdvice.id == advice_id, AiPositionAdvice.is_deleted == 0)
        .first()
    )
    if advice is None:
        raise HTTPException(status_code=404, detail="仓位建议记录不存在")
    return AiPositionAdviceDetailResponse(data=_advice_to_dict(advice, db))


@router.post("/generate", response_model=OperationResponse)
async def manual_generate_position_advice(
    body: Optional[GenerateRequest] = None,
    db: Session = Depends(get_db),
):
    """手动触发仓位建议生成。

    - 传 user_public_id：只为该用户生成（同步返回结果）。
    - 不传 user_public_id：为所有 active 会员生成（后台线程执行，接口立即返回已启动）。
    """
    if body is None:
        body = GenerateRequest()
    target_date = _parse_date(body.report_date) or date.today()

    if body.user_public_id:
        user = (
            db.query(UserModel)
            .filter(UserModel.public_id == body.user_public_id, UserModel.is_deleted == 0)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        advice = await ai_position_advice_service.generate_position_advice_for_user(
            db, user.id, target_date, force=True
        )
        return OperationResponse(message=f"仓位建议已生成，状态：{advice.status}")

    # 批量触发：后台线程执行，避免阻塞接口
    import threading

    def _run_job():
        ai_position_advice_service.generate_position_advices_for_all_members(
            report_date=target_date
        )

    threading.Thread(target=_run_job, daemon=True).start()
    return OperationResponse(message="批量仓位建议任务已启动")


@router.post("/{advice_id}/regenerate", response_model=OperationResponse)
async def regenerate_position_advice(
    advice_id: int,
    db: Session = Depends(get_db),
):
    """重新生成指定仓位建议记录。"""
    advice = (
        db.query(AiPositionAdvice)
        .filter(AiPositionAdvice.id == advice_id, AiPositionAdvice.is_deleted == 0)
        .first()
    )
    if advice is None:
        raise HTTPException(status_code=404, detail="仓位建议记录不存在")

    new_advice = await ai_position_advice_service.generate_position_advice_for_user(
        db, advice.user_id, advice.report_date, force=True
    )
    return OperationResponse(message=f"仓位建议已重新生成，状态：{new_advice.status}")


@router.put("/{advice_id}", response_model=AiPositionAdviceDetailResponse)
async def update_position_advice(
    advice_id: int,
    body: AiPositionAdviceUpdateRequest,
    db: Session = Depends(get_db),
):
    """管理员手工编辑仓位建议内容。"""
    advice = ai_position_advice_service.update_advice_content(
        db, advice_id, body.content, summary=body.summary
    )
    if advice is None:
        raise HTTPException(status_code=404, detail="仓位建议记录不存在")
    return AiPositionAdviceDetailResponse(data=_advice_to_dict(advice, db))


@router.get("/{advice_id}/portfolio-context")
async def get_position_advice_context(
    advice_id: int,
    db: Session = Depends(get_db),
):
    """获取指定仓位建议所属用户的持仓上下文（用于优化 prompt/数据源）。"""
    advice = (
        db.query(AiPositionAdvice)
        .filter(AiPositionAdvice.id == advice_id, AiPositionAdvice.is_deleted == 0)
        .first()
    )
    if advice is None:
        raise HTTPException(status_code=404, detail="仓位建议记录不存在")

    user = (
        db.query(UserModel)
        .filter(UserModel.id == advice.user_id, UserModel.is_deleted == 0)
        .first()
    )
    portfolio = ai_position_advice_service.get_user_portfolio_data(db, advice.user_id)
    return {
        "success": True,
        "data": {
            "user_id": advice.user_id,
            "user_public_id": user.public_id if user else None,
            "user_email": user.email if user else None,
            "report_date": advice.report_date.isoformat() if advice.report_date else None,
            "stocks": portfolio,
            "stock_count": len(portfolio),
        },
    }


@router.get("/users/available")
async def list_position_advice_users(
    db: Session = Depends(get_db),
):
    """获取已生成过仓位建议的用户列表（用于下拉筛选）。"""
    from sqlalchemy import func

    rows = (
        db.query(
            AiPositionAdvice.user_id,
            UserModel.public_id,
            UserModel.email,
            UserModel.name,
            func.count(AiPositionAdvice.id).label("advice_count"),
        )
        .join(UserModel, AiPositionAdvice.user_id == UserModel.id)
        .filter(AiPositionAdvice.is_deleted == 0, UserModel.is_deleted == 0)
        .group_by(AiPositionAdvice.user_id, UserModel.public_id, UserModel.email, UserModel.name)
        .order_by(func.count(AiPositionAdvice.id).desc())
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "user_id": r.user_id,
                "public_id": r.public_id,
                "email": r.email,
                "name": r.name,
                "advice_count": r.advice_count,
            }
            for r in rows
        ],
    }


@router.post("/retry-failed", response_model=OperationResponse)
async def retry_failed_position_advices(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认今天"),
    db: Session = Depends(get_db),
):
    """重试指定日期的失败仓位建议记录。"""
    target_date = _parse_date(report_date) or date.today()
    result = ai_position_advice_service.retry_failed_advices(db, target_date)
    return OperationResponse(
        message=f"重试完成：总数 {result['total']}，成功 {result['success']}，仍失败 {result['still_failed']}"
    )
