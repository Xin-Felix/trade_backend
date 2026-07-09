"""Tushare 接口: slb_len_mm - 做市借券交易汇总(停)

做市借券交易汇总。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/slb-len-mm")
async def ts_slb_len_mm(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """做市借券交易汇总"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.slb_len_mm(**kwargs)
    return df_to_list(df)
