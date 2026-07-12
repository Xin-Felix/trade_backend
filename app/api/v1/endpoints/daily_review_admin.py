"""每日复盘后台管理接口。

供管理员查看复盘记录、手动触发生成、重试失败记录。
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.base import get_db
from app.models.daily_review import DailyReview
from app.models.user import User as UserModel
from app.schemas.daily_review import (
    DailyReviewDetailResponse,
    DailyReviewListResponse,
    DailyReviewUpdateRequest,
    OperationResponse,
)
from app.services import daily_review_service

router = APIRouter(dependencies=[Depends(require_admin)])


class GenerateRequest(BaseModel):
    """手动生成请求"""

    user_public_id: Optional[str] = None
    report_date: Optional[str] = None  # YYYYMMDD
    level: Optional[str] = "standard"  # standard / deep


def _report_to_dict(report: DailyReview, db: Session) -> dict:
    user = (
        db.query(UserModel)
        .filter(UserModel.id == report.user_id, UserModel.is_deleted == 0)
        .first()
    )
    return {
        "id": report.id,
        "user_id": report.user_id,
        "user_public_id": user.public_id if user else None,
        "user_email": user.email if user else None,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "level": report.level,
        "status": report.status,
        "summary": report.summary,
        "content": report.content,
        "error_message": report.error_message,
        "prompt_version": report.prompt_version,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYYMMDD") from exc


@router.get("", response_model=DailyReviewListResponse)
async def list_daily_reviews(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
    status: Optional[str] = Query(None, description="状态"),
    level: Optional[str] = Query(None, description="层级 standard / deep"),
    keyword: Optional[str] = Query(None, description="邮箱/名称搜索"),
    user_public_id: Optional[str] = Query(None, description="用户 public_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """复盘记录列表（分页 + 筛选 + 搜索）。"""
    target_date = _parse_date(report_date)

    query = (
        db.query(DailyReview)
        .join(UserModel, DailyReview.user_id == UserModel.id)
        .filter(DailyReview.is_deleted == 0, UserModel.is_deleted == 0)
    )
    if target_date:
        query = query.filter(DailyReview.report_date == target_date)
    if status:
        query = query.filter(DailyReview.status == status)
    if level:
        query = query.filter(DailyReview.level == level)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(UserModel.email.ilike(like), UserModel.name.ilike(like)))
    if user_public_id:
        query = query.filter(UserModel.public_id == user_public_id)

    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc(), DailyReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return DailyReviewListResponse(
        data={
            "list": [_report_to_dict(item, db) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{review_id}", response_model=DailyReviewDetailResponse)
async def get_daily_review_detail(
    review_id: int,
    db: Session = Depends(get_db),
):
    """复盘详情。"""
    report = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.is_deleted == 0)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return DailyReviewDetailResponse(data=_report_to_dict(report, db))


@router.post("/generate", response_model=OperationResponse)
async def manual_generate_daily_review(
    body: Optional[GenerateRequest] = None,
    db: Session = Depends(get_db),
):
    """手动触发复盘生成。

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
        level = body.level or "standard"
        report = await daily_review_service.generate_daily_review_for_user(
            db, user.id, target_date, level=level, force=True
        )
        return OperationResponse(
            message=f"复盘已生成，状态：{report.status}"
        )

    # 批量触发：后台线程执行，避免阻塞接口
    import threading

    level = body.level or "standard"

    def _run_job():
        daily_review_service.generate_daily_reviews_for_all_members(
            report_date=target_date, level=level
        )

    threading.Thread(target=_run_job, daemon=True).start()
    return OperationResponse(message=f"批量 {level} 复盘任务已启动")


@router.post("/{review_id}/regenerate", response_model=OperationResponse)
async def regenerate_daily_review(
    review_id: int,
    db: Session = Depends(get_db),
):
    """重新生成指定复盘记录。"""
    report = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.is_deleted == 0)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    new_report = await daily_review_service.generate_daily_review_for_user(
        db, report.user_id, report.report_date, level=report.level, force=True
    )
    return OperationResponse(message=f"复盘已重新生成，状态：{new_report.status}")


@router.put("/{review_id}", response_model=DailyReviewDetailResponse)
async def update_daily_review(
    review_id: int,
    body: DailyReviewUpdateRequest,
    db: Session = Depends(get_db),
):
    """管理员手工编辑复盘内容。"""
    report = daily_review_service.update_review_content(
        db, review_id, body.content, summary=body.summary
    )
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return DailyReviewDetailResponse(data=_report_to_dict(report, db))


@router.get("/{review_id}/watchlist")
async def get_daily_review_watchlist(
    review_id: int,
    db: Session = Depends(get_db),
):
    """获取指定复盘所属用户的自选股数据（用于优化 prompt/数据源）。"""
    report = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.is_deleted == 0)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    user = (
        db.query(UserModel)
        .filter(UserModel.id == report.user_id, UserModel.is_deleted == 0)
        .first()
    )
    watchlist = daily_review_service.get_user_watchlist_data(db, report.user_id)
    return {
        "success": True,
        "data": {
            "user_id": report.user_id,
            "user_public_id": user.public_id if user else None,
            "user_email": user.email if user else None,
            "report_date": report.report_date.isoformat() if report.report_date else None,
            "stocks": watchlist,
            "stock_count": len(watchlist),
        },
    }


@router.get("/users/available")
async def list_daily_review_users(
    db: Session = Depends(get_db),
):
    """获取已生成过复盘的用户列表（用于下拉筛选）。"""
    from sqlalchemy import func

    rows = (
        db.query(
            DailyReview.user_id,
            UserModel.public_id,
            UserModel.email,
            UserModel.name,
            func.count(DailyReview.id).label("review_count"),
        )
        .join(UserModel, DailyReview.user_id == UserModel.id)
        .filter(DailyReview.is_deleted == 0, UserModel.is_deleted == 0)
        .group_by(DailyReview.user_id, UserModel.public_id, UserModel.email, UserModel.name)
        .order_by(func.count(DailyReview.id).desc())
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
                "review_count": r.review_count,
            }
            for r in rows
        ],
    }


@router.post("/retry-failed", response_model=OperationResponse)
async def retry_failed_daily_reviews(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认今天"),
    level: Optional[str] = Query(None, description="层级 standard / deep，默认全部"),
    db: Session = Depends(get_db),
):
    """重试指定日期的失败复盘记录。"""
    target_date = _parse_date(report_date) or date.today()
    result = daily_review_service.retry_failed_reviews(db, target_date, level=level)
    return OperationResponse(
        message=f"重试完成：总数 {result['total']}，成功 {result['success']}，仍失败 {result['still_failed']}"
    )
