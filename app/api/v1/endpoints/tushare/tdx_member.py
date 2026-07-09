"""Tushare 接口: tdx_member - TDX板块成分

获取通达信概念板块成分股。
适用场景：了解某个TDX板块包含哪些个股。
Tushare接口名: tdx_member

参数说明:
- ts_code: 板块代码（必填，不需要normalize）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/tdx-member/{code}")
async def ts_tdx_member(
    code: str,
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取TDX板块成分股"""
    pro = get_pro()
    df = pro.tdx_member(ts_code=code, limit=limit)
    return df_to_list(df)
