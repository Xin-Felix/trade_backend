"""Tushare 接口: fund_div - 基金分红

获取公募基金分红数据
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-div/{code}")
async def ts_fund_div(
    code: str,
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金分红"""
    pro = get_pro()
    df = pro.fund_div(ts_code=code, limit=limit)
    return df_to_list(df)
