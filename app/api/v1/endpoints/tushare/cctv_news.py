"""Tushare 接口: cctv_news - 新闻联播文字稿

获取新闻联播文字稿数据，数据开始于2017年。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cctv-news")
async def ts_cctv_news(
    date: str = Query("", description="日期 YYYYMMDD"),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """新闻联播文字稿"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if date: kwargs["date"] = date
    df = pro.cctv_news(**kwargs)
    return df_to_list(df)
