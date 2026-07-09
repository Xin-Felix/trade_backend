"""Tushare 接口: top_inst - 龙虎榜机构

获取龙虎榜机构交易明细。
适用场景：跟踪机构席位买卖。
Tushare接口名: top_inst

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


@router.get("/top-inst")
async def ts_top_inst(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取龙虎榜机构交易"""
    pro = get_pro()
    kwargs: dict = {"trade_date": trade_date if trade_date else today(), "limit": limit}
    if code:
        kwargs["ts_code"] = normalize_code(code)
    df = pro.top_inst(**kwargs)
    return df_to_list(df)
