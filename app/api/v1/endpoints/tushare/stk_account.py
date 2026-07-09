"""Tushare 接口: stk_account - 股票开户数据(停)

获取股票账户开户数据，统计周期为一周。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stk-account")
async def ts_stk_account(
    date: str = Query("", description="日期"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """股票开户数据"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if date:
        kwargs["date"] = date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.stk_account(**kwargs)
    return df_to_list(df)
