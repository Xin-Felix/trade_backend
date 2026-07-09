"""Tushare 接口: limit_step - 连板天梯

获取涨停股票连板天梯统计。
适用场景：跟踪最高板、连板晋级率。
Tushare接口名: limit_step

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/limit-step")
async def ts_limit_step(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取连板天梯"""
    pro = get_pro()
    df = pro.limit_step(trade_date=trade_date if trade_date else today(), limit=limit)
    return df_to_list(df)
