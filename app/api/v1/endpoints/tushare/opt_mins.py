"""Tushare 接口: opt_mins - 期权分钟行情

获取全市场期权合约分钟数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/opt-mins")
async def ts_opt_mins(
    ts_code: str = Query(..., description="期权合约代码"),
    freq: str = Query("1min", description="频率: 1min/5min/15min/30min/60min"),
    start_date: str = Query("", description="开始日期时间"),
    end_date: str = Query("", description="结束日期时间"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """期权分钟行情"""
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "freq": freq, "limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.opt_mins(**kwargs)
    return df_to_list(df)
