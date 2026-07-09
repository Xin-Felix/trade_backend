"""Tushare 接口: dc_concept - DC题材列表

获取东方财富概念题材列表（每日更新）。
适用场景：了解当前市场关注的题材概念。
Tushare接口名: dc_concept

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/dc-concept")
async def ts_dc_concept(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取DC题材列表"""
    pro = get_pro()
    df = pro.dc_concept(trade_date=trade_date if trade_date else today(), limit=limit)
    return df_to_list(df)
