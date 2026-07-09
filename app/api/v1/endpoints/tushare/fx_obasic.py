"""Tushare 接口: fx_obasic - 外汇基础信息(海外)

获取海外外汇基础信息，目前只有FXCM交易商的数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fx-obasic")
async def ts_fx_obasic(
    exchange: str = Query("", description="交易商"),
    classify: str = Query("", description="分类"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """外汇基础信息(海外)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if exchange:
        kwargs["exchange"] = exchange
    if classify:
        kwargs["classify"] = classify
    df = pro.fx_obasic(**kwargs)
    return df_to_list(df)
