"""Tushare 接口: rt_etf_k - ETF实时日线

获取ETF实时日k线行情。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-etf-k")
async def ts_rt_etf_k(
    ts_code: str = Query("", description="ETF代码，支持通配符如 51*.SH"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF实时日线"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_etf_k(**kwargs)
    return df_to_list(df)
