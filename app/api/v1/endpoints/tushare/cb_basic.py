"""Tushare 接口: cb_basic - 可转债基础信息

获取可转债基本信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cb-basic")
async def ts_cb_basic(
    ts_code: str = Query("", description="转债代码"),
    list_date: str = Query("", description="上市日期 YYYYMMDD"),
    exchange: str = Query("", description="交易所: SSE/SZSE"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债基础信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if list_date:
        kwargs["list_date"] = list_date
    if exchange:
        kwargs["exchange"] = exchange
    df = pro.cb_basic(**kwargs)
    return df_to_list(df)
