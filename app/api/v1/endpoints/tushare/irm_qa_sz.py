"""Tushare 接口: irm_qa_sz - 深证易互动问答

深交所互动易投资者与上市公司直接沟通的平台问答数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/irm-qa-sz")
async def ts_irm_qa_sz(
    ts_code: str = Query("", description="股票代码"),
    trade_date: str = Query("", description="日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """深证易互动问答"""
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
    df = pro.irm_qa_sz(**kwargs)
    return df_to_list(df)
