"""Tushare 接口: stk_holdertrade - 股东增减持

获取上市公司大股东增减持明细。
适用场景：跟踪大股东操作、判断信心。
Tushare接口名: stk_holdertrade

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/stk-holdertrade/{code}")
async def ts_stk_holdertrade(
    code: str,
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股东增减持"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.stk_holdertrade(ts_code=ts_code, limit=limit)
    return df_to_list(df)
