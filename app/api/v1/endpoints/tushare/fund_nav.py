"""Tushare 接口: fund_nav - 基金净值

获取公募基金净值数据
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-nav/{code}")
async def ts_fund_nav(
    code: str,
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金净值"""
    pro = get_pro()
    df = pro.fund_nav(ts_code=code, limit=limit)
    return df_to_list(df)
