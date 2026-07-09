"""Tushare 接口: shibor - Shibor利率

获取上海银行间同业拆放利率。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/shibor")
async def ts_shibor(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Shibor利率"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.shibor(**kwargs)
    return df_to_list(df)
