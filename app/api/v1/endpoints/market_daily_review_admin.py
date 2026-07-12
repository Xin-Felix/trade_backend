"""全市场每日一句话复盘后台管理接口。

供管理员查看、手动触发生成、编辑全市场一句话复盘。
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.base import get_db
from app.models.market_daily_review import MarketDailyReview
from app.schemas.daily_review import (
    MarketDailyReviewDetailResponse,
    MarketDailyReviewListResponse,
    MarketDailyReviewUpdateRequest,
    OperationResponse,
)
from app.services import market_daily_review_service

router = APIRouter(dependencies=[Depends(require_admin)])


class GenerateMarketBriefRequest(BaseModel):
    """手动生成全市场一句话复盘请求"""

    report_date: Optional[str] = None  # YYYYMMDD


def _report_to_dict(report: MarketDailyReview) -> dict:
    return {
        "id": report.id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "level": report.level,
        "status": report.status,
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


@router.get("", response_model=MarketDailyReviewListResponse)
async def list_market_daily_reviews(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """全市场一句话复盘记录列表。"""
    target_date = _parse_date(report_date)

    query = db.query(MarketDailyReview).filter(MarketDailyReview.is_deleted == 0)
    if target_date:
        query = query.filter(MarketDailyReview.report_date == target_date)
    if status:
        query = query.filter(MarketDailyReview.status == status)

    total = query.count()
    items = (
        query.order_by(MarketDailyReview.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return MarketDailyReviewListResponse(
        data={
            "list": [_report_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{review_id}", response_model=MarketDailyReviewDetailResponse)
async def get_market_daily_review_detail(
    review_id: int,
    db: Session = Depends(get_db),
):
    """全市场一句话复盘详情。"""
    report = market_daily_review_service.get_market_brief_detail(db, review_id)
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return MarketDailyReviewDetailResponse(data=_report_to_dict(report))


@router.post("/generate", response_model=OperationResponse)
async def manual_generate_market_daily_review(
    body: Optional[GenerateMarketBriefRequest] = None,
    db: Session = Depends(get_db),
):
    """手动触发今日全市场一句话复盘生成。"""
    if body is None:
        body = GenerateMarketBriefRequest()
    target_date = _parse_date(body.report_date) or date.today()

    report = market_daily_review_service.generate_market_brief_sync(db, target_date)
    if report.status == "running":
        return OperationResponse(message="全市场一句话复盘正在生成中，请勿重复触发")
    return OperationResponse(message=f"全市场一句话复盘已生成，状态：{report.status}")


@router.post("/{review_id}/regenerate", response_model=OperationResponse)
async def regenerate_market_daily_review(
    review_id: int,
    db: Session = Depends(get_db),
):
    """重新生成指定全市场一句话复盘记录。"""
    report = market_daily_review_service.get_market_brief_detail(db, review_id)
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    new_report = market_daily_review_service.generate_market_brief_sync(
        db, report.report_date
    )
    if new_report.status == "running":
        return OperationResponse(message="全市场一句话复盘正在生成中，请勿重复触发")
    return OperationResponse(
        message=f"全市场一句话复盘已重新生成，状态：{new_report.status}"
    )


@router.put("/{review_id}", response_model=MarketDailyReviewDetailResponse)
async def update_market_daily_review(
    review_id: int,
    body: MarketDailyReviewUpdateRequest,
    db: Session = Depends(get_db),
):
    """管理员手工编辑全市场一句话复盘内容。"""
    report = market_daily_review_service.update_market_brief_content(
        db, review_id, body.content
    )
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return MarketDailyReviewDetailResponse(data=_report_to_dict(report))
