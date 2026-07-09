"""Tushare 接口: dc_index - DC板块分类

获取东方财富概念板块列表。
适用场景：查看所有DC概念板块。
Tushare接口名: dc_index

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/dc-index")
async def ts_dc_index(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取DC板块分类"""
    pro = get_pro()
    df = pro.dc_index(trade_date=trade_date if trade_date else today(), limit=limit)
    return df_to_list(df)
