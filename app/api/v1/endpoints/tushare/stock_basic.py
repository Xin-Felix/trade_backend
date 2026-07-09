"""Tushare 接口: stock_basic - 股票列表

获取基础信息数据，包括股票代码、名称、上市日期、退市日期等。
适用场景：查询当前上市/退市股票清单。
Tushare接口名: stock_basic

参数说明:
- list_status: 上市状态 L上市 D退市 P暂停上市（默认L）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stock-basic")
async def ts_stock_basic(
    list_status: str = Query("L", description="上市状态 L/D/P"),
    limit: int = Query(5000, ge=1, le=10000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股票列表"""
    pro = get_pro()
    df = pro.stock_basic(list_status=list_status, limit=limit)
    return df_to_list(df)
