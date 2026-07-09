"""Tushare 接口: fut_trade_cal - 期货交易日历

获取各大期货交易所交易日历数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fut-trade-cal")
async def ts_fut_trade_cal(
    exchange: str = Query("", description="交易所: CFFEX/DCE/CZCE/SHFE/INE"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """期货交易日历"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if exchange:
        kwargs["exchange"] = exchange
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.fut_trade_cal(**kwargs)
    return df_to_list(df)
