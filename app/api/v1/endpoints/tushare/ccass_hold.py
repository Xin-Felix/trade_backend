"""Tushare 接口: ccass_hold - 中央结算系统持股统计

获取中央结算系统持股汇总数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/ccass-hold")
async def ts_ccass_hold(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """中央结算系统持股统计"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    if code: kwargs["ts_code"] = normalize_code(code)
    df = pro.ccass_hold(**kwargs)
    return df_to_list(df)
