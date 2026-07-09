"""Tushare 接口: cb_call - 可转债赎回信息

获取可转债到期赎回、强制赎回等信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cb-call")
async def ts_cb_call(
    ts_code: str = Query("", description="转债代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债赎回信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.cb_call(**kwargs)
    return df_to_list(df)
