"""Tushare 接口: bak_basic - 股票历史列表

获取备用基础列表，数据从2016年开始。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/bak-basic")
async def ts_bak_basic(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """股票历史列表"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    df = pro.bak_basic(**kwargs)
    return df_to_list(df)
