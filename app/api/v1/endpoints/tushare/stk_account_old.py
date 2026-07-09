"""Tushare 接口: stk_account_old - 股票开户数据(旧)

获取股票账户开户数据旧版格式。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stk-account-old")
async def ts_stk_account_old(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """股票开户数据(旧)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.stk_account_old(**kwargs)
    return df_to_list(df)
