"""Tushare 接口: hm_detail - 游资交易每日明细

获取每日游资交易明细，数据开始于2022年8月。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/hm-detail")
async def ts_hm_detail(
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """游资交易每日明细"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if trade_date: kwargs["trade_date"] = trade_date
    else: kwargs["trade_date"] = today()
    if code: kwargs["ts_code"] = normalize_code(code)
    df = pro.hm_detail(**kwargs)
    return df_to_list(df)
