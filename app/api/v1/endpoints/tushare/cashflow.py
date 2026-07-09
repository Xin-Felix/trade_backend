"""Tushare 接口: cashflow - 现金流量表

获取上市公司现金流量表数据。
适用场景：分析经营/投资/融资活动现金流。
Tushare接口名: cashflow

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/cashflow/{code}")
async def ts_cashflow(
    code: str,
    limit: int = Query(8, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取现金流量表数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.cashflow(ts_code=ts_code, limit=limit)
    return df_to_list(df)
