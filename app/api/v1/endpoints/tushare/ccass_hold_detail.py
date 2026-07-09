"""Tushare 接口: ccass_hold_detail - 中央结算系统持股明细

获取中央结算系统机构席位持股明细。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/ccass-hold-detail")
async def ts_ccass_hold_detail(
    ts_code: str = Query("", description="股票代码"),
    hk_code: str = Query("", description="港交所代码"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """中央结算系统持股明细"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if hk_code:
        kwargs["hk_code"] = hk_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.ccass_hold_detail(**kwargs)
    return df_to_list(df)
