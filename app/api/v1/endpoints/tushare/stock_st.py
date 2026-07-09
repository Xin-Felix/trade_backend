"""Tushare 接口: stock_st - ST列表

获取风险警示股票列表（ST、*ST等）。
适用场景：排除ST股票、或专做ST摘帽。
Tushare接口名: stock_st（实际用 stk_limit 或自定义）

参数说明:
- trade_date: 交易日期（可选）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stock-st")
async def ts_stock_st(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取ST股票列表"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    df = pro.stock_st(**kwargs)
    return df_to_list(df)
