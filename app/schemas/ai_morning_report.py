"""AI 晨报相关请求/响应模型。"""

from datetime import date
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 公共字段
# ---------------------------------------------------------------------------


class AiMorningReportItem(BaseModel):
    """晨报记录项"""

    id: int
    report_date: Optional[date] = None
    status: str
    summary: Optional[str] = None
    content: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# 用户端响应
# ---------------------------------------------------------------------------


class AiMorningReportDetailResponse(BaseModel):
    success: bool = True
    data: AiMorningReportItem


class AiMorningReportListData(BaseModel):
    list: list[AiMorningReportItem]
    total: int
    page: int
    page_size: int


class AiMorningReportListResponse(BaseModel):
    success: bool = True
    data: AiMorningReportListData


# ---------------------------------------------------------------------------
# 管理端响应
# ---------------------------------------------------------------------------


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class AiMorningReportUpdateRequest(BaseModel):
    """管理员编辑晨报内容请求"""

    summary: Optional[str] = None
    content: str
