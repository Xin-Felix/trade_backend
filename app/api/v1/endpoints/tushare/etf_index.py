"""Tushare 接口: etf_index - ETF跟踪指数列表

获取ETF基准指数列表信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/etf-index")
async def ts_etf_index(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF跟踪指数列表"""
    pro = get_pro()
    df = pro.etf_index(limit=limit)
    return df_to_list(df)
