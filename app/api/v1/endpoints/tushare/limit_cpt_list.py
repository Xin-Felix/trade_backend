"""Tushare 接口: limit_cpt_list - 涨停最强板块

获取涨停股票最多的板块统计。
适用场景：识别当日最强主线。
Tushare接口名: limit_cpt_list

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/limit-cpt-list")
async def ts_limit_cpt_list(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取涨停最强板块"""
    pro = get_pro()
    df = pro.limit_cpt_list(trade_date=trade_date if trade_date else today(), limit=limit)
    return df_to_list(df)
