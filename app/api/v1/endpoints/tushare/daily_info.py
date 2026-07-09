"""Tushare 接口: daily_info - 沪深市场每日交易统计

获取交易所股票交易统计，包括各板块明细。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/daily-info")
async def ts_daily_info(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    exchange: str = Query("", description="交易所 SSE/SZSE"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """沪深市场每日交易统计"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    if exchange: kwargs["exchange"] = exchange
    df = pro.daily_info(**kwargs)
    return df_to_list(df)
