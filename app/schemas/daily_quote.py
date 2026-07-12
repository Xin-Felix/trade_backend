"""每日一言请求/响应模型。"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class DailyQuoteCreateRequest(BaseModel):
    """创建每日一言"""

    content: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(default=None, max_length=100)
    display_date: Optional[date] = Field(default=None)
    is_published: bool = True


class DailyQuoteUpdateRequest(BaseModel):
    """更新每日一言"""

    content: Optional[str] = Field(default=None, min_length=1, max_length=500)
    author: Optional[str] = Field(default=None, max_length=100)
    display_date: Optional[date] = Field(default=None)
    is_published: Optional[bool] = Field(default=None)


class DailyQuotePublishRequest(BaseModel):
    """上架/下架"""

    is_published: bool


class DailyQuoteItem(BaseModel):
    """每日一言列表/详情项"""

    id: int
    content: str
    author: Optional[str]
    display_date: Optional[str]
    is_published: bool
    created_at: str
    updated_at: str


class DailyQuoteListData(BaseModel):
    list: list[DailyQuoteItem]
    total: int
    page: int
    page_size: int


class DailyQuoteListResponse(BaseModel):
    success: bool = True
    data: DailyQuoteListData


class DailyQuoteDetailResponse(BaseModel):
    success: bool = True
    data: DailyQuoteItem


class DailyQuoteOperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class DailyQuotePublicData(BaseModel):
    """App 公开接口返回的当日语录"""

    id: int
    content: str
    author: Optional[str]


class DailyQuotePublicResponse(BaseModel):
    success: bool = True
    data: DailyQuotePublicData
