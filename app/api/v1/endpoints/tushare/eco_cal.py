"""Tushare 接口: eco_cal - 全球财经事件日历

获取全球财经日历、包括经济事件数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/eco-cal")
async def ts_eco_cal(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """全球财经事件日历"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.eco_cal(**kwargs)
    return df_to_list(df)
