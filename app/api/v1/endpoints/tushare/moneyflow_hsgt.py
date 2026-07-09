"""Tushare 接口: moneyflow_hsgt - 沪深港通资金流向

获取沪股通、深股通、港股通每日资金流向数据（北向/南向资金）。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/moneyflow-hsgt")
async def ts_moneyflow_hsgt(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=300),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """沪深港通资金流向"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.moneyflow_hsgt(**kwargs)
    return df_to_list(df)
