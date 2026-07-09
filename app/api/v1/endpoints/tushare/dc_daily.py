"""Tushare 接口: dc_daily - DC板块行情

获取东方财富概念板块日线行情。
适用场景：板块趋势分析。
Tushare接口名: dc_daily

参数说明:
- ts_code: 板块代码（可选）
- trade_date: 交易日期 YYYYMMDD
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/dc-daily")
async def ts_dc_daily(
    ts_code: str = Query("", description="板块代码（可选）"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取DC板块日线行情"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.dc_daily(**kwargs)
    return df_to_list(df)
