"""Tushare 接口: fut_weekly_detail - 期货主要品种交易周报

获取期货交易所主要品种每周交易统计信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fut-weekly-detail")
async def ts_fut_weekly_detail(
    week: str = Query("", description="周期，如 202401"),
    prd: str = Query("", description="品种代码"),
    start_week: str = Query("", description="开始周期"),
    end_week: str = Query("", description="结束周期"),
    exchange: str = Query("", description="交易所"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """期货主要品种交易周报"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if week:
        kwargs["week"] = week
    if prd:
        kwargs["prd"] = prd
    if start_week:
        kwargs["start_week"] = start_week
    if end_week:
        kwargs["end_week"] = end_week
    if exchange:
        kwargs["exchange"] = exchange
    df = pro.fut_weekly_detail(**kwargs)
    return df_to_list(df)
