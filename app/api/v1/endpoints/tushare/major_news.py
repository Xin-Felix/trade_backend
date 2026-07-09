"""Tushare 接口: major_news - 新闻通讯(长篇)

获取长篇通讯信息，覆盖主要新闻资讯网站，提供超过8年历史。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/major-news")
async def ts_major_news(
    src: str = Query("", description="来源（可选）"),
    start_date: str = Query("", description="开始时间 YYYY-MM-DD HH:MM:SS"),
    end_date: str = Query("", description="结束时间 YYYY-MM-DD HH:MM:SS"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """新闻通讯(长篇)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if src: kwargs["src"] = src
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.major_news(**kwargs)
    return df_to_list(df)
