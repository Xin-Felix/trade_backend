"""Tushare 接口: income - 利润表

获取上市公司利润表数据，包含营收、净利润、费用等。
适用场景：分析盈利能力、费用结构。
Tushare接口名: income

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/income/{code}")
async def ts_income(
    code: str,
    limit: int = Query(8, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取利润表数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.income(ts_code=ts_code, limit=limit)
    return df_to_list(df)
