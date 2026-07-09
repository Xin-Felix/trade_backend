"""Tushare 接口: yc_cb - 国债收益率曲线

获取中债收益率曲线，目前可获取中债国债收益率曲线即期和到期收益率曲线数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/yc-cb")
async def ts_yc_cb(
    curve_type: str = Query("", description="曲线类型"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """国债收益率曲线"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if curve_type:
        kwargs["curve_type"] = curve_type
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.yc_cb(**kwargs)
    return df_to_list(df)
