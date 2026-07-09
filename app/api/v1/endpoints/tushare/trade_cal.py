"""Tushare 接口: trade_cal - 交易日历

获取各大交易所交易日历数据。
适用场景：判断某天是否为交易日、查询交易日区间。
Tushare接口名: trade_cal

参数说明:
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- is_open: 是否交易 0休市 1交易
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/trade-cal")
async def ts_trade_cal(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    is_open: str = Query("", description="是否交易 0休市 1交易"),
    limit: int = Query(60, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取交易日历"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    if is_open:
        kwargs["is_open"] = is_open
    df = pro.trade_cal(**kwargs)
    return df_to_list(df)
