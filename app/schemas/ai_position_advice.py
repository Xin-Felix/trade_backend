"""AI 仓位建议相关请求/响应模型。"""

from datetime import date
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 公共字段
# ---------------------------------------------------------------------------


class AiPositionAdviceItem(BaseModel):
    """仓位建议记录项"""

    id: int
    user_id: int
    user_public_id: Optional[str] = None
    user_email: Optional[str] = None
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


class AiPositionAdviceDetailResponse(BaseModel):
    success: bool = True
    data: AiPositionAdviceItem


class AiPositionAdviceListData(BaseModel):
    list: list[AiPositionAdviceItem]
    total: int
    page: int
    page_size: int


class AiPositionAdviceListResponse(BaseModel):
    success: bool = True
    data: AiPositionAdviceListData


# ---------------------------------------------------------------------------
# 管理端响应
# ---------------------------------------------------------------------------


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class AiPositionAdviceUpdateRequest(BaseModel):
    """管理员编辑仓位建议内容请求"""

    summary: Optional[str] = None
    content: str
