"""Tushare 接口: margin_secs - 融资融券标的(盘前)

获取沪深京三大交易所融资融券标的（包括ETF），每天盘前更新。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/margin-secs")
async def ts_margin_secs(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """融资融券标的(盘前)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    df = pro.margin_secs(**kwargs)
    return df_to_list(df)
