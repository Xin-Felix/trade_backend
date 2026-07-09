"""Tushare 接口: moneyflow_cnt_ths - 板块资金流向(THS)

获取同花顺概念板块每日资金流向。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/moneyflow-cnt-ths")
async def ts_moneyflow_cnt_ths(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    ts_code: str = Query("", description="板块代码（可选）"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """板块资金流向(THS)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    if ts_code: kwargs["ts_code"] = ts_code
    df = pro.moneyflow_cnt_ths(**kwargs)
    return df_to_list(df)
