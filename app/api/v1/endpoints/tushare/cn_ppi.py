"""Tushare 接口: cn_ppi - 工业生产者出厂价格指数(PPI)

获取PPI工业生产者出厂价格指数数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cn-ppi")
async def ts_cn_ppi(
    start_m: str = Query("", description="开始月份 YYYYMM"),
    end_m: str = Query("", description="结束月份 YYYYMM"),
    limit: int = Query(12, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """工业生产者出厂价格指数(PPI)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_m: kwargs["start_m"] = start_m
    if end_m: kwargs["end_m"] = end_m
    df = pro.cn_ppi(**kwargs)
    return df_to_list(df)
