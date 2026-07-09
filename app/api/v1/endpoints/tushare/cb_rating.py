"""Tushare 接口: cb_rating - 可转债债券评级

获取可转债评级历史记录。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cb-rating")
async def ts_cb_rating(
    ts_code: str = Query("", description="转债代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债债券评级"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.cb_rating(**kwargs)
    return df_to_list(df)
