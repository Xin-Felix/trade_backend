"""Tushare 接口: fut_basic - 合约信息

获取期货合约列表数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fut-basic")
async def ts_fut_basic(
    exchange: str = Query("", description="交易所: CFFEX/DCE/CZCE/SHFE/INE/GFEX"),
    fut_type: str = Query("", description="合约类型: 1主力 2连续"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """合约信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if exchange:
        kwargs["exchange"] = exchange
    if fut_type:
        kwargs["fut_type"] = fut_type
    df = pro.fut_basic(**kwargs)
    return df_to_list(df)
