"""Tushare 接口: etf_basic - ETF基本信息

获取国内ETF基础信息，包括QDII。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/etf-basic")
async def ts_etf_basic(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF基本信息"""
    pro = get_pro()
    df = pro.etf_basic(limit=limit)
    return df_to_list(df)
