"""用户端 AI 晨报接口。

任意登录用户均可查看每日晨报。
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.ai_morning_report import AiMorningReport
from app.schemas.ai_morning_report import (
    AiMorningReportDetailResponse,
    AiMorningReportListResponse,
)
from app.schemas.user import User
from app.services import ai_morning_report_service

router = APIRouter()


def _report_to_dict(report) -> dict:
    return {
        "id": report.id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "status": report.status,
        "summary": report.summary,
        "content": report.content,
        "error_message": report.error_message,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


@router.get("/today", response_model=AiMorningReportDetailResponse)
async def get_today_morning_report(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取今日的 AI 晨报。"""
    report = ai_morning_report_service.get_morning_report_by_date(db, date.today())
    if report is None or report.status != "success":
        raise HTTPException(status_code=404, detail="今日晨报尚未生成，请稍后再试")
    return AiMorningReportDetailResponse(data=_report_to_dict(report))


@router.get("", response_model=AiMorningReportListResponse)
async def list_morning_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取历史 AI 晨报列表（按日期倒序）。"""
    items, total = ai_morning_report_service.get_morning_report_list(
        db, page=page, page_size=page_size
    )
    return AiMorningReportListResponse(
        data={
            "list": [_report_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
