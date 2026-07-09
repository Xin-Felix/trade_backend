"""Tushare 接口: dc_member - DC板块成分

获取东方财富概念板块成分股。
适用场景：了解某个DC板块包含哪些个股。
Tushare接口名: dc_member

参数说明:
- ts_code: 板块代码（可选）
- trade_date: 交易日期 YYYYMMDD（默认today）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today

router = APIRouter()


@router.get("/dc-member")
async def ts_dc_member(
    ts_code: str = Query("", description="板块代码（可选）"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取DC板块成分股"""
    pro = get_pro()
    kwargs: dict = {"trade_date": trade_date if trade_date else today(), "limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.dc_member(**kwargs)
    return df_to_list(df)
