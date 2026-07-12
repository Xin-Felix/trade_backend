"""每日复盘相关请求/响应模型。"""

from datetime import date
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 公共字段
# ---------------------------------------------------------------------------


class DailyReviewItem(BaseModel):
    """复盘记录项"""

    id: int
    user_id: int
    user_public_id: Optional[str] = None
    user_email: Optional[str] = None
    report_date: Optional[date] = None
    level: Optional[str] = "standard"
    status: str
    summary: Optional[str] = None
    content: Optional[str] = None
    error_message: Optional[str] = None
    prompt_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# 用户端响应
# ---------------------------------------------------------------------------


class DailyReviewTodayResponse(BaseModel):
    """今日复盘响应（根据用户身份可能是 deep / brief）"""

    success: bool = True
    level: str  # deep / standard / brief
    data: dict


class DailyReviewDetailResponse(BaseModel):
    success: bool = True
    data: DailyReviewItem


class DailyReviewListData(BaseModel):
    list: list[DailyReviewItem]
    total: int
    page: int
    page_size: int


class DailyReviewListResponse(BaseModel):
    success: bool = True
    data: DailyReviewListData


# ---------------------------------------------------------------------------
# 全市场一句话复盘
# ---------------------------------------------------------------------------


class MarketDailyReviewItem(BaseModel):
    """全市场一句话复盘记录项"""

    id: int
    report_date: Optional[date] = None
    level: str = "brief"
    status: str
    content: Optional[str] = None
    error_message: Optional[str] = None
    prompt_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MarketDailyReviewDetailResponse(BaseModel):
    success: bool = True
    data: MarketDailyReviewItem


class MarketDailyReviewListData(BaseModel):
    list: list[MarketDailyReviewItem]
    total: int
    page: int
    page_size: int


class MarketDailyReviewListResponse(BaseModel):
    success: bool = True
    data: MarketDailyReviewListData


# ---------------------------------------------------------------------------
# 管理端响应
# ---------------------------------------------------------------------------


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class DailyReviewUpdateRequest(BaseModel):
    """管理员编辑复盘内容请求"""

    summary: Optional[str] = None
    content: str


class MarketDailyReviewUpdateRequest(BaseModel):
    """管理员编辑全市场一句话复盘内容请求"""

    content: str
