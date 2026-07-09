"""Tushare 接口: sf_month - 社融增量(月度)

获取月度社会融资数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/sf-month")
async def ts_sf_month(
    start_m: str = Query("", description="开始月份 YYYYMM"),
    end_m: str = Query("", description="结束月份 YYYYMM"),
    limit: int = Query(12, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """社融增量(月度)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_m: kwargs["start_m"] = start_m
    if end_m: kwargs["end_m"] = end_m
    df = pro.sf_month(**kwargs)
    return df_to_list(df)
