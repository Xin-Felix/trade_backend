"""Tushare 接口: stk_mins - 历史分钟

获取A股分钟数据，支持1min/5min/15min/30min/60min行情。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stk-mins")
async def ts_stk_mins(
    ts_code: str = Query(..., description="股票代码"),
    freq: str = Query("1min", description="频率: 1min/5min/15min/30min/60min"),
    start_date: str = Query("", description="开始日期时间"),
    end_date: str = Query("", description="结束日期时间"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """A股历史分钟"""
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "freq": freq, "limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.stk_mins(**kwargs)
    return df_to_list(df)
