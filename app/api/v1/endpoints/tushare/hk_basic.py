"""Tushare 接口: hk_basic - 港股基础信息

获取港股列表信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/hk-basic")
async def ts_hk_basic(
    ts_code: str = Query("", description="港股代码"),
    list_status: str = Query("", description="上市状态: L上市/D退市/P暂停"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """港股基础信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if list_status:
        kwargs["list_status"] = list_status
    df = pro.hk_basic(**kwargs)
    return df_to_list(df)
