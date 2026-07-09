"""Tushare 接口: stk_week_month_adj - 周月线复权行情(每日更新)

股票周/月线复权行情(每日更新)。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stk-week-month-adj")
async def ts_stk_week_month_adj(
    ts_code: str = Query("", description="股票代码"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    freq: str = Query("W", description="频率: W周/M月"),
    adj: str = Query("qfq", description="复权类型: qfq前复权/hfq后复权"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """周月线复权行情(每日更新)"""
    pro = get_pro()
    kwargs: dict = {"freq": freq, "adj": adj, "limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.stk_week_month_adj(**kwargs)
    return df_to_list(df)
