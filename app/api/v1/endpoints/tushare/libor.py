"""Tushare 接口: libor - Libor利率

Libor拆借利率。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/libor")
async def ts_libor(
    date: str = Query("", description="日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    curr_type: str = Query("", description="货币类型"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Libor利率"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if date:
        kwargs["date"] = date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    if curr_type:
        kwargs["curr_type"] = curr_type
    df = pro.libor(**kwargs)
    return df_to_list(df)
