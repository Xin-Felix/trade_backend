"""Tushare 接口: top10_cb_holders - 可转债十大持有人

获取可转债前十大持有人。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/top10-cb-holders")
async def ts_top10_cb_holders(
    ts_code: str = Query("", description="转债代码"),
    ann_date: str = Query("", description="公告日期 YYYYMMDD"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债十大持有人"""
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
    df = pro.top10_cb_holders(**kwargs)
    return df_to_list(df)
