from typing import Optional

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    """自选股列表项"""

    code: str
    name: str
    ts_code: str
    created_at: str


class WatchlistAddRequest(BaseModel):
    """添加自选股请求"""

    code: str
    name: str


class WatchlistRemoveRequest(BaseModel):
    """删除自选股请求"""

    code: str


class WatchlistResponse(BaseModel):
    """自选股列表响应"""

    items: list[WatchlistItem]
    total: int
