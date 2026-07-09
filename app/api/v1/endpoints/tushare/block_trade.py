"""Tushare 接口: block_trade - 大宗交易

获取大宗交易数据。
适用场景：跟踪机构大额买卖、折溢价分析。
Tushare接口名: block_trade

参数说明:
- ts_code: 股票代码（可选）
- trade_date: 交易日期 YYYYMMDD
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/block-trade")
async def ts_block_trade(
    code: str = Query("", description="股票代码（可选）"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取大宗交易数据"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code:
        kwargs["ts_code"] = normalize_code(code)
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.block_trade(**kwargs)
    return df_to_list(df)
