"""Tushare 接口: research_report - 券商研究报告

获取券商研究报告（个股、行业等），历史从20170101开始。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/research-report")
async def ts_research_report(
    code: str = Query("", description="股票代码（可选）"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """券商研究报告"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code: kwargs["ts_code"] = normalize_code(code)
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.research_report(**kwargs)
    return df_to_list(df)
