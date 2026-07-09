"""Tushare 接口: stk_managers - 管理层

获取上市公司管理层名单。
适用场景：查看公司高管信息。
Tushare接口名: stk_managers

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/stk-managers/{code}")
async def ts_stk_managers(
    code: str,
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取上市公司管理层"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.stk_managers(ts_code=ts_code, limit=limit)
    return df_to_list(df)
