"""Tushare 接口: namechange - 股票曾用名

获取股票历史名称变更记录。
适用场景：查询股票更名历史。
Tushare接口名: namechange

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/namechange/{code}")
async def ts_namechange(
    code: str,
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股票曾用名"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.namechange(ts_code=ts_code, limit=limit)
    return df_to_list(df)
