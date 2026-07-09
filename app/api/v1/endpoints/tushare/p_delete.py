"""Tushare 接口: p_delete - 组合删除

删除自选股组合。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/p-delete")
async def ts_p_delete(
    group_name: str = Query(..., description="组合名称"),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """组合删除"""
    pro = get_pro()
    df = pro.p_delete(group_name=group_name)
    return df_to_list(df)
