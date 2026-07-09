"""Tushare 接口: hk_income - 港股利润表

获取港股上市公司财务利润表数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/hk-income")
async def ts_hk_income(
    ts_code: str = Query("", description="港股代码"),
    ann_date: str = Query("", description="公告日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """港股利润表"""
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
    df = pro.hk_income(**kwargs)
    return df_to_list(df)
