"""Tushare 接口: index_basic - 指数基本信息

获取指数基础信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/index-basic")
async def ts_index_basic(
    market: str = Query("", description="市场 SSE/SZSE/SW等"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """指数基本信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if market: kwargs["market"] = market
    df = pro.index_basic(**kwargs)
    return df_to_list(df)
