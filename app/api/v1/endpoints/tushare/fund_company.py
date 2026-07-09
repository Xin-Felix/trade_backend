"""Tushare 接口: fund_company - 基金管理人

获取公募基金管理人列表。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-company")
async def ts_fund_company(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金管理人"""
    pro = get_pro()
    df = pro.fund_company(limit=limit)
    return df_to_list(df)
