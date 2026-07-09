"""Tushare 接口: rt_etf_min_daily - ETF实时分钟-日累计

获取ETF实时分钟数据日累计，包括1~60min。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-etf-min-daily")
async def ts_rt_etf_min_daily(
    ts_code: str = Query(..., description="ETF代码"),
    freq: str = Query("1", description="分钟频率: 1/5/15/30/60"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF实时分钟-日累计"""
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "freq": freq, "limit": limit}
    df = pro.rt_etf_min_daily(**kwargs)
    return df_to_list(df)
