"""Tushare 接口: rt_etf_sz_iopv - ETF实时参考(深市)

ETF实时净值和申购赎回数据参考，目前只提供深市。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-etf-sz-iopv")
async def ts_rt_etf_sz_iopv(
    ts_code: str = Query("", description="ETF代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF实时参考(深市)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_etf_sz_iopv(**kwargs)
    return df_to_list(df)
