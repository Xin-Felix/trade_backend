"""Tushare 接口: sw_daily - 申万日线行情

获取申万行业日线行情
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/sw-daily/{code}")
async def ts_sw_daily(
    code: str,
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """申万日线行情"""
    pro = get_pro()
    kwargs: dict = {"ts_code": code, "limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.sw_daily(**kwargs)
    return df_to_list(df)
