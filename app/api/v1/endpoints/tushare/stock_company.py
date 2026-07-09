"""Tushare 接口: stock_company - 公司信息

获取上市公司基本信息。
适用场景：了解公司主营业务、注册地址等。
Tushare接口名: stock_company

参数说明:
- ts_code: 股票代码（必填）
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/stock-company/{code}")
async def ts_stock_company(
    code: str,
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取上市公司基本信息"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.stock_company(ts_code=ts_code)
    return df_to_list(df)
