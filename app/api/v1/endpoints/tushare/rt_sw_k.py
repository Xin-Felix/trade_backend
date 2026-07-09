"""Tushare 接口: rt_sw_k - 申万实时行情

获取申万行业指数的最新截面数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-sw-k")
async def ts_rt_sw_k(
    ts_code: str = Query("", description="申万指数代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """申万实时行情"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_sw_k(**kwargs)
    return df_to_list(df)
