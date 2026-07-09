"""Tushare 接口: index_weight - 指数成分和权重

获取各类指数成分和权重（月度数据）。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/index-weight/{code}")
async def ts_index_weight(
    code: str,
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """指数成分和权重"""
    pro = get_pro()
    kwargs: dict = {"index_code": code, "limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.index_weight(**kwargs)
    return df_to_list(df)
