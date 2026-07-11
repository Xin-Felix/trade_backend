"""H5 页面管理请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel, Field


class H5PageCreateRequest(BaseModel):
    """创建 H5 页面"""

    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    title: str = Field(..., min_length=1, max_length=200)
    content_type: str = Field(default="markdown", pattern=r"^(markdown|html)$")
    content: str = Field(..., min_length=1)
    is_published: bool = False


class H5PageUpdateRequest(BaseModel):
    """更新 H5 页面"""

    title: Optional[str] = Field(default=None, max_length=200)
    content_type: Optional[str] = Field(default=None, pattern=r"^(markdown|html)$")
    content: Optional[str] = None
    is_published: Optional[bool] = None


class H5PagePublishRequest(BaseModel):
    """发布/下架"""

    is_published: bool


class H5PageItem(BaseModel):
    """H5 页面列表/详情项"""

    id: int
    slug: str
    title: str
    content_type: str
    content: str
    is_published: bool
    created_at: str
    updated_at: str


class H5PageListData(BaseModel):
    list: list[H5PageItem]
    total: int
    page: int
    page_size: int


class H5PageListResponse(BaseModel):
    success: bool = True
    data: H5PageListData


class H5PageDetailResponse(BaseModel):
    success: bool = True
    data: H5PageItem


class H5PageOperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class H5PagePublicResponse(BaseModel):
    """公开接口返回（供 App WebView）"""

    slug: str
    title: str
    content_type: str
    content: str
    rendered_html: str
