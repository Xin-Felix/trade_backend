"""Tushare 接口: moneyflow_mkt_dc - 大盘资金流向(DC)

获取东方财富大盘资金流向数据，每日盘后更新。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/moneyflow-mkt-dc")
async def ts_moneyflow_mkt_dc(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """大盘资金流向(DC)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    df = pro.moneyflow_mkt_dc(**kwargs)
    return df_to_list(df)
