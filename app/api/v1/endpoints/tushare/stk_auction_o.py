"""Tushare 接口: stk_auction_o - 股票开盘集合竞价数据(盘后)

股票开盘9:30集合竞价数据，每天盘后更新。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/stk-auction-o")
async def ts_stk_auction_o(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """股票开盘集合竞价数据(盘后)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    if code: kwargs["ts_code"] = normalize_code(code)
    df = pro.stk_auction_o(**kwargs)
    return df_to_list(df)
