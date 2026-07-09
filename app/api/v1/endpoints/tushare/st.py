"""Tushare 接口: st - ST风险警示板股票

ST风险警示板股票列表。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/st")
async def ts_st(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ST风险警示板股票"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    df = pro.st(**kwargs)
    return df_to_list(df)
