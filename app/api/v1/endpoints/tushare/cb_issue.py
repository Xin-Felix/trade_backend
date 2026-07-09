"""Tushare 接口: cb_issue - 可转债发行

获取可转债发行数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cb-issue")
async def ts_cb_issue(
    ts_code: str = Query("", description="转债代码"),
    ann_date: str = Query("", description="发行公告日 YYYYMMDD"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """可转债发行"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if ann_date:
        kwargs["ann_date"] = ann_date
    df = pro.cb_issue(**kwargs)
    return df_to_list(df)
