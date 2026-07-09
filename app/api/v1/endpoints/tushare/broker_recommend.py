"""Tushare 接口: broker_recommend - 券商月度金股

获取券商月度金股推荐，一般1日~3日内更新当月数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/broker-recommend")
async def ts_broker_recommend(
    month: str = Query("", description="月份 YYYYMM"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """券商月度金股"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if month: kwargs["month"] = month
    df = pro.broker_recommend(**kwargs)
    return df_to_list(df)
