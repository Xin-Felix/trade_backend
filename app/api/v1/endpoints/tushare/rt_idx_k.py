"""Tushare 接口: rt_idx_k - 指数实时日线

获取交易所指数实时日线行情。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-idx-k")
async def ts_rt_idx_k(
    ts_code: str = Query("", description="指数代码，支持通配符"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """指数实时日线"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_idx_k(**kwargs)
    return df_to_list(df)
