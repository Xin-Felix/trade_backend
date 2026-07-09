"""Tushare 接口: limit_list_d - 涨跌停炸板

获取每日涨跌停和炸板数据，含连板天数、封单等。
适用场景：打板策略、连板分析。
Tushare接口名: limit_list_d

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit_type: U涨停 D跌停 Z炸板（默认U）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/limit-list-d")
async def ts_limit_list_d(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit_type: str = Query("U", description="U涨停 D跌停 Z炸板"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取涨跌停炸板数据"""
    pro = get_pro()
    df = pro.limit_list_d(
        trade_date=trade_date if trade_date else today(),
        limit_type=limit_type,
        limit=limit,
    )
    return df_to_list(df)
