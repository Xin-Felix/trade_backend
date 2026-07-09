"""Tushare 接口: kpl_list - KP榜单

获取KP榜单数据（涨停/跌停/炸板等）。
适用场景：快速了解当日市场情绪。
Tushare接口名: kpl_list

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- tag: 标签（涨停/跌停/炸板等，默认涨停）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/kpl-list")
async def ts_kpl_list(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    tag: str = Query("涨停", description="标签：涨停/跌停/炸板等"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取KP榜单数据"""
    pro = get_pro()
    df = pro.kpl_list(
        trade_date=trade_date if trade_date else today(),
        tag=tag,
        limit=limit,
    )
    return df_to_list(df)
