"""Tushare 接口: dc_hot - DC热榜

获取东方财富热门股票数据。
适用场景：捕捉市场热点。
Tushare接口名: dc_hot

参数说明:
- trade_date: 交易日期（可选）
- hot_type: 热榜类型（默认 A股市场）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/dc-hot")
async def ts_dc_hot(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    hot_type: str = Query("A股市场", description="热榜类型"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取DC热榜"""
    pro = get_pro()
    kwargs: dict = {"hot_type": hot_type, "limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    df = pro.dc_hot(**kwargs)
    return df_to_list(df)
