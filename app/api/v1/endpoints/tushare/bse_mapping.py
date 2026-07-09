"""Tushare 接口: bse_mapping - 北交所新旧代码对照

获取北交所股票代码变更后新旧代码映射表数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/bse-mapping")
async def ts_bse_mapping(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """北交所新旧代码对照"""
    pro = get_pro()
    df = pro.bse_mapping(limit=limit)
    return df_to_list(df)
