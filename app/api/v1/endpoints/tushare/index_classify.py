"""Tushare 接口: index_classify - 申万行业分类

获取申万行业分类列表（2014版或2021版）。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/index-classify")
async def ts_index_classify(
    level: str = Query("", description="L1一级/L2二级/L3三级"),
    src: str = Query("SW2021", description="SW2014/SW2021"),
    limit: int = Query(500, ge=1, le=2000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """申万行业分类"""
    pro = get_pro()
    kwargs: dict = {"src": src, "limit": limit}
    if level: kwargs["level"] = level
    df = pro.index_classify(**kwargs)
    return df_to_list(df)
