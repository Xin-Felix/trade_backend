"""Tushare 接口: rt_k - 实时日线

获取实时日k线行情，支持按股票代码及股票代码通配符一次性提取。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/rt-k")
async def ts_rt_k(
    ts_code: str = Query("", description="股票代码，支持通配符"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """A股实时日线"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.rt_k(**kwargs)
    return df_to_list(df)
