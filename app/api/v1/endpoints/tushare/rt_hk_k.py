"""Tushare 接口: rt_hk_k - 港股实时日线

获取港股实时日k线行情。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-hk-k")
async def ts_rt_hk_k(
    ts_code: str = Query("", description="港股代码，支持通配符"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """港股实时日线"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_hk_k(**kwargs)
    return df_to_list(df)
