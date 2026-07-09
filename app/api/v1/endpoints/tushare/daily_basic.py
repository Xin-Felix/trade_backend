"""Tushare 接口: daily_basic - 每日指标

获取全部股票每日重要的基本面指标，可用于选股分析。
包含PE/PB/换手率/总市值/流通市值等。
适用场景：估值筛选、市值排序。
Tushare接口名: daily_basic

参数说明:
- trade_date: 交易日期 YYYYMMDD（与code二选一，默认today）
- ts_code: 股票代码（可选）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/daily-basic-ts")
async def ts_daily_basic(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取每日指标（PE/PB/换手率/市值等）"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code:
        kwargs["ts_code"] = normalize_code(code)
    else:
        kwargs["trade_date"] = trade_date if trade_date else today()
    df = pro.daily_basic(**kwargs)
    return df_to_list(df)
