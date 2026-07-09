"""Tushare 接口: npr - 国家政策库

获取国家行政机关公开披露的各类法规、条例政策、批复、通知等文本数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/npr")
async def ts_npr(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """国家政策库"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.npr(**kwargs)
    return df_to_list(df)
