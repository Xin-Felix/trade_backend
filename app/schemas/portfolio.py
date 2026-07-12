from pydantic import BaseModel


class PortfolioItem(BaseModel):
    """持仓列表项"""

    code: str
    name: str
    ts_code: str
    cost_price: float | None = None
    quantity: float | None = None
    is_margin: bool = False
    note: str | None = None
    created_at: str


class PortfolioAddRequest(BaseModel):
    """添加持仓请求"""

    code: str
    name: str
    cost_price: float | None = None
    quantity: float | None = None
    is_margin: bool | None = None
    note: str | None = None


class PortfolioUpdateRequest(BaseModel):
    """更新持仓请求（支持部分更新）"""

    cost_price: float | None = None
    quantity: float | None = None
    is_margin: bool | None = None
    note: str | None = None


class PortfolioResponse(BaseModel):
    """持仓列表响应"""

    items: list[PortfolioItem]
    total: int
