"""Tushare 接口: fut_wsr - 仓单日报

获取仓单日报数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fut-wsr")
async def ts_fut_wsr(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    symbol: str = Query("", description="品种代码"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    exchange: str = Query("", description="交易所"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """仓单日报"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    if symbol:
        kwargs["symbol"] = symbol
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    if exchange:
        kwargs["exchange"] = exchange
    df = pro.fut_wsr(**kwargs)
    return df_to_list(df)
