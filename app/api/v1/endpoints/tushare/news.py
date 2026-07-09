"""Tushare 接口: news - 新闻快讯(短讯)

获取主流新闻网站的快讯新闻数据，提供超过6年历史。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/news")
async def ts_news(
    src: str = Query("sina", description="来源 sina/wallstreetcn/10jqka/eastmoney"),
    start_date: str = Query("", description="开始时间 YYYY-MM-DD HH:MM:SS"),
    end_date: str = Query("", description="结束时间 YYYY-MM-DD HH:MM:SS"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """新闻快讯"""
    pro = get_pro()
    kwargs: dict = {"src": src, "limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.news(**kwargs)
    return df_to_list(df)
