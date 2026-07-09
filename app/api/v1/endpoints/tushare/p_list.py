"""Tushare 接口: p_list - 组合列表

自选股组合查询。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/p-list")
async def ts_p_list(
    user: User = Depends(get_current_user),
) -> list[dict]:
    """组合列表"""
    pro = get_pro()
    df = pro.p_list()
    return df_to_list(df)
