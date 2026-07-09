"""Tushare 接口: us_daily_adj - 美股复权行情

获取美股复权行情，支持美股全市场股票。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/us-daily-adj")
async def ts_us_daily_adj(
    ts_code: str = Query("", description="美股代码"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """美股复权行情"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.us_daily_adj(**kwargs)
    return df_to_list(df)
