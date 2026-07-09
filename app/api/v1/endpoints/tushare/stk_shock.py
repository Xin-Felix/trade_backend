"""Tushare 接口: stk_shock - 个股异常波动

交易所每日发布股票交易异常波动情况。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/stk-shock")
async def ts_stk_shock(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """个股异常波动"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    df = pro.stk_shock(**kwargs)
    return df_to_list(df)
