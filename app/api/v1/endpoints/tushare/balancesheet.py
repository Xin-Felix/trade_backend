"""Tushare 接口: balancesheet - 资产负债表

获取上市公司资产负债表数据。
适用场景：分析资产结构、负债水平。
Tushare接口名: balancesheet

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/balancesheet/{code}")
async def ts_balancesheet(
    code: str,
    limit: int = Query(8, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取资产负债表数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.balancesheet(ts_code=ts_code, limit=limit)
    return df_to_list(df)
