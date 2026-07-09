"""Tushare 接口: etf_sh_cons - 每日篮子组合(沪市PCF)

获取上交所场内所有ETF每日盘前披露的一篮子组合信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/etf-sh-cons")
async def ts_etf_sh_cons(
    ts_code: str = Query("", description="ETF代码"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(2000, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """每日篮子组合(沪市PCF)"""
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
    df = pro.etf_sh_cons(**kwargs)
    return df_to_list(df)
