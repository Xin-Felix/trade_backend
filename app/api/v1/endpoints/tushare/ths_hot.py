"""Tushare 接口: ths_hot - THS热榜

获取同花顺热股、热门概念等热榜数据。
适用场景：捕捉市场热点。
Tushare接口名: ths_hot

参数说明:
- trade_date: 交易日期（可选）
- hot_type: 热榜类型（热股等，默认热股）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/ths-hot")
async def ts_ths_hot(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    hot_type: str = Query("热股", description="热榜类型"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取THS热榜"""
    pro = get_pro()
    kwargs: dict = {"hot_type": hot_type, "limit": limit}
    if trade_date:
        kwargs["trade_date"] = trade_date
    df = pro.ths_hot(**kwargs)
    return df_to_list(df)
