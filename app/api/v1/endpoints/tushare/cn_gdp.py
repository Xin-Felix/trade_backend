"""Tushare 接口: cn_gdp - 国内生产总值(GDP)

获取国民经济之GDP数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cn-gdp")
async def ts_cn_gdp(
    start_q: str = Query("", description="开始季度 如2024Q1"),
    end_q: str = Query("", description="结束季度"),
    limit: int = Query(8, ge=1, le=50),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """国内生产总值(GDP)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_q: kwargs["start_q"] = start_q
    if end_q: kwargs["end_q"] = end_q
    df = pro.cn_gdp(**kwargs)
    return df_to_list(df)
