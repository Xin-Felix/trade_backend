"""Tushare 接口: slb_len - 转融资交易汇总

转融通融资汇总数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/slb-len")
async def ts_slb_len(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """转融资交易汇总"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    df = pro.slb_len(**kwargs)
    return df_to_list(df)
