"""Tushare 接口: irm_qa_sh - 上证e互动问答

获取上交所e互动董秘问答文本数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/irm-qa-sh")
async def ts_irm_qa_sh(
    ts_code: str = Query("", description="股票代码"),
    trade_date: str = Query("", description="日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """上证e互动问答"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.irm_qa_sh(**kwargs)
    return df_to_list(df)
