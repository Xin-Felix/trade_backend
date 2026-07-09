"""Tushare 接口: limit_list_ths - THS涨跌停

获取同花顺涨跌停榜单数据。
适用场景：涨停/跌停/炸板池分析。
Tushare接口名: limit_list_ths

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit_type: 涨停池/跌停池/炸板池（默认涨停池）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/limit-list-ths")
async def ts_limit_list_ths(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit_type: str = Query("涨停池", description="涨停池/跌停池/炸板池"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取THS涨跌停数据"""
    pro = get_pro()
    df = pro.limit_list_ths(
        trade_date=trade_date if trade_date else today(),
        limit_type=limit_type,
        limit=limit,
    )
    return df_to_list(df)
