"""Tushare 接口: tdx_index - TDX板块分类

获取通达信概念板块分类列表。
适用场景：了解通达信板块分类体系。
Tushare接口名: tdx_index

参数说明:
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/tdx-index")
async def ts_tdx_index(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取TDX板块分类"""
    pro = get_pro()
    df = pro.tdx_index(limit=limit)
    return df_to_list(df)
