"""Tushare 接口: p_get - 成分查询

查询组合的成分列表。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/p-get")
async def ts_p_get(
    group_name: str = Query(..., description="组合名称"),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """成分查询"""
    pro = get_pro()
    df = pro.p_get(group_name=group_name)
    return df_to_list(df)
