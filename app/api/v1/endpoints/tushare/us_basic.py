"""Tushare 接口: us_basic - 美股基础信息

获取美股列表信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/us-basic")
async def ts_us_basic(
    ts_code: str = Query("", description="美股代码"),
    classify: str = Query("", description="分类: ADR/GDR"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """美股基础信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if classify:
        kwargs["classify"] = classify
    df = pro.us_basic(**kwargs)
    return df_to_list(df)
