"""Tushare 接口: sz_daily_info - 深圳市场每日交易情况

获取深圳市场每日交易概况。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/sz-daily-info")
async def ts_sz_daily_info(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """深圳市场每日交易情况"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    df = pro.sz_daily_info(**kwargs)
    return df_to_list(df)
