"""Tushare 接口: stock_hsgt - 沪深港通股票列表

获取沪深港通标的股票列表。
适用场景：查看哪些股票纳入港股通。
Tushare接口名: stock_hsgt （实际为 hsgt_top10 / hk_hold等，此处用hs_const）

参数说明:
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/stock-hsgt")
async def ts_stock_hsgt(
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取沪深港通股票列表"""
    pro = get_pro()
    df = pro.hs_const(limit=limit)
    return df_to_list(df)
