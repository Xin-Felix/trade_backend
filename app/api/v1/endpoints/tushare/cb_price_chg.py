"""Tushare 接口: cb_price_chg - 可转债转股价变动

获取可转债转股价变动。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cb-price-chg")
async def ts_cb_price_chg(
    ts_code: str = Query("", description="转债代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债转股价变动"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.cb_price_chg(**kwargs)
    return df_to_list(df)
