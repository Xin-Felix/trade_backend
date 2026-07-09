"""Tushare 接口: sge_basic - 上海黄金基础信息

获取上海黄金交易所现货合约基础信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/sge-basic")
async def ts_sge_basic(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """上海黄金基础信息"""
    pro = get_pro()
    df = pro.sge_basic(limit=limit)
    return df_to_list(df)
