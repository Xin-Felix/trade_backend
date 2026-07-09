"""Tushare 接口: dividend - 分红送股

获取上市公司历史分红送股数据。
适用场景：高股息策略、分红记录查询。
Tushare接口名: dividend

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/dividend/{code}")
async def ts_dividend(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取分红送股数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.dividend(ts_code=ts_code, limit=limit)
    return df_to_list(df)
