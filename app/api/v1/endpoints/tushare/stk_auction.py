"""Tushare 接口: stk_auction - 开盘竞价成交(当日)

获取当日个股和ETF的集合竞价成交情况，每天9点26~29分可获取。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/stk-auction")
async def ts_stk_auction(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """开盘竞价成交(当日)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    if code: kwargs["ts_code"] = normalize_code(code)
    df = pro.stk_auction(**kwargs)
    return df_to_list(df)
