"""Tushare 接口: etf_share_size - ETF份额规模

获取沪深ETF每日份额和规模数据
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/etf-share-size/{code}")
async def ts_etf_share_size(
    code: str,
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """ETF份额规模"""
    pro = get_pro()
    kwargs: dict = {"ts_code": code, "limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.etf_share_size(**kwargs)
    return df_to_list(df)
