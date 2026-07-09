"""Tushare 接口: stk_limit - 每日涨跌停价格

获取全市场每日涨跌停价格，包含涨停价、跌停价。
适用场景：计算涨跌停空间、打板策略。
Tushare接口名: stk_limit

参数说明:
- trade_date: 交易日期 YYYYMMDD（默认today）
- ts_code: 股票代码（可选）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/stk-limit")
async def ts_stk_limit(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取每日涨跌停价格"""
    pro = get_pro()
    kwargs: dict = {"trade_date": trade_date if trade_date else today(), "limit": limit}
    if code:
        kwargs["ts_code"] = normalize_code(code)
    df = pro.stk_limit(**kwargs)
    return df_to_list(df)
