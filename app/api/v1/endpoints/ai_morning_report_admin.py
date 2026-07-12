"""AI 晨报后台管理接口。

供管理员查看晨报记录、手动触发生成、重试失败记录。
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.base import get_db
from app.models.ai_morning_report import AiMorningReport
from app.schemas.ai_morning_report import (
    AiMorningReportDetailResponse,
    AiMorningReportListResponse,
    AiMorningReportUpdateRequest,
    OperationResponse,
)
from app.services import ai_morning_report_service

router = APIRouter(dependencies=[Depends(require_admin)])


class GenerateRequest(BaseModel):
    """手动生成请求"""

    report_date: Optional[str] = None  # YYYYMMDD


def _report_to_dict(report: AiMorningReport) -> dict:
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


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYYMMDD") from exc


@router.get("", response_model=AiMorningReportListResponse)
async def list_morning_reports(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """晨报记录列表（分页 + 筛选）。"""
    target_date = _parse_date(report_date)

    query = db.query(AiMorningReport)
    if target_date:
        query = query.filter(AiMorningReport.report_date == target_date)
    if status:
        query = query.filter(AiMorningReport.status == status)

    total = query.count()
    items = (
        query.order_by(AiMorningReport.report_date.desc(), AiMorningReport.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AiMorningReportListResponse(
        data={
            "list": [_report_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{report_id}", response_model=AiMorningReportDetailResponse)
async def get_morning_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
):
    """晨报详情。"""
    report = db.query(AiMorningReport).filter(AiMorningReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="晨报记录不存在")
    return AiMorningReportDetailResponse(data=_report_to_dict(report))


@router.post("/generate", response_model=OperationResponse)
async def manual_generate_morning_report(
    body: Optional[GenerateRequest] = None,
    db: Session = Depends(get_db),
):
    """手动触发晨报生成（指定日期，默认今天）。"""
    if body is None:
        body = GenerateRequest()
    target_date = _parse_date(body.report_date) or date.today()
    report = await ai_morning_report_service.generate_morning_report(
        db, target_date, force=True
    )
    return OperationResponse(message=f"晨报已生成，状态：{report.status}")


@router.post("/{report_id}/regenerate", response_model=OperationResponse)
async def regenerate_morning_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """重新生成指定晨报记录。"""
    report = db.query(AiMorningReport).filter(AiMorningReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="晨报记录不存在")

    new_report = await ai_morning_report_service.generate_morning_report(
        db, report.report_date, force=True
    )
    return OperationResponse(message=f"晨报已重新生成，状态：{new_report.status}")


@router.put("/{report_id}", response_model=AiMorningReportDetailResponse)
async def update_morning_report(
    report_id: int,
    body: AiMorningReportUpdateRequest,
    db: Session = Depends(get_db),
):
    """管理员手工编辑晨报内容。"""
    report = ai_morning_report_service.update_morning_report_content(
        db, report_id, body.content, summary=body.summary
    )
    if report is None:
        raise HTTPException(status_code=404, detail="晨报记录不存在")
    return AiMorningReportDetailResponse(data=_report_to_dict(report))


@router.post("/retry-failed", response_model=OperationResponse)
async def retry_failed_morning_report(
    report_date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认今天"),
    db: Session = Depends(get_db),
):
    """重试指定日期的失败晨报记录。"""
    target_date = _parse_date(report_date) or date.today()
    result = ai_morning_report_service.retry_failed_morning_report(db, target_date)
    return OperationResponse(
        message=f"重试完成：总数 {result['total']}，成功 {result['success']}，仍失败 {result['still_failed']}"
    )
