"""Tushare 接口: hm_list - 游资名录

获取市场游资名录数据。
适用场景：了解知名游资席位。
Tushare接口名: hm_list

参数说明:
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/hm-list")
async def ts_hm_list(
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取游资名录"""
    pro = get_pro()
    df = pro.hm_list(limit=limit)
    return df_to_list(df)
