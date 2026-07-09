"""Tushare 接口: hsgt_top10 - 沪深股通十大成交股

获取沪股通、深股通每日前十大成交详细数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/hsgt-top10")
async def ts_hsgt_top10(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    ts_code: str = Query("", description="股票代码"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    market_type: str = Query("", description="市场类型: 1沪/3深"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """沪深股通十大成交股"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    if ts_code:
        kwargs["ts_code"] = ts_code
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    if market_type:
        kwargs["market_type"] = market_type
    df = pro.hsgt_top10(**kwargs)
    return df_to_list(df)
