"""Tushare 接口: rt_min - 实时分钟

获取全A股票实时分钟数据，包括1~60min。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-min")
async def ts_rt_min(
    ts_code: str = Query(..., description="股票代码"),
    freq: str = Query("1", description="分钟频率: 1/5/15/30/60"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """A股实时分钟"""
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "freq": freq, "limit": limit}
    df = pro.rt_min(**kwargs)
    return df_to_list(df)
