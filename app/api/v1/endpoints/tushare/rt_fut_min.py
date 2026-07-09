"""Tushare 接口: rt_fut_min - 实时分钟行情

获取全市场期货合约实时分钟数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-fut-min")
async def ts_rt_fut_min(
    ts_code: str = Query(..., description="合约代码"),
    freq: str = Query("1", description="分钟频率: 1/5/15/30/60"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """期货实时分钟行情"""
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "freq": freq, "limit": limit}
    df = pro.rt_fut_min(**kwargs)
    return df_to_list(df)
