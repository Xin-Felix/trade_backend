"""Tushare 接口: us_cashflow - 美股现金流量表

获取美股上市公司现金流量表数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/us-cashflow")
async def ts_us_cashflow(
    ts_code: str = Query("", description="美股代码"),
    ann_date: str = Query("", description="公告日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """美股现金流量表"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if ann_date:
        kwargs["ann_date"] = ann_date
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.us_cashflow(**kwargs)
    return df_to_list(df)
