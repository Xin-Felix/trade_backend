"""Tushare 接口: opt_basic - 期权合约信息

获取期权合约信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/opt-basic")
async def ts_opt_basic(
    exchange: str = Query("", description="交易所: SSE/SZSE/CFFEX/DCE/CZCE/SHFE"),
    opt_code: str = Query("", description="标的代码"),
    call_put: str = Query("", description="期权类型: C认购/P认沽"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """期权合约信息"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if exchange:
        kwargs["exchange"] = exchange
    if opt_code:
        kwargs["opt_code"] = opt_code
    if call_put:
        kwargs["call_put"] = call_put
    df = pro.opt_basic(**kwargs)
    return df_to_list(df)
