"""Tushare 接口: monetary_policy - 央行货币政策执行报告

获取央行季度更新的货币政策执行报告，历史数据开始于2001年。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/monetary-policy")
async def ts_monetary_policy(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """央行货币政策执行报告"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.monetary_policy(**kwargs)
    return df_to_list(df)
