"""Tushare 接口: fund_basic - 基金列表

获取公募基金数据列表，包括场内和场外基金。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-basic")
async def ts_fund_basic(
    market: str = Query("E", description="E场内 O场外"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金列表"""
    pro = get_pro()
    df = pro.fund_basic(market=market, limit=limit)
    return df_to_list(df)
