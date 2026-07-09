"""Tushare 接口: stk_weekly_monthly - 周月线行情(每日更新)

股票周/月线行情(每日更新)。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stk-weekly-monthly")
async def ts_stk_weekly_monthly(
    ts_code: str = Query("", description="股票代码"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    freq: str = Query("W", description="频率: W周/M月"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """周月线行情(每日更新)"""
    pro = get_pro()
    kwargs: dict = {"freq": freq, "limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.stk_weekly_monthly(**kwargs)
    return df_to_list(df)
