"""Tushare 接口: cn_pmi - 采购经理指数(PMI)

采购经理人指数。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cn-pmi")
async def ts_cn_pmi(
    start_m: str = Query("", description="开始月份 YYYYMM"),
    end_m: str = Query("", description="结束月份 YYYYMM"),
    limit: int = Query(12, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """采购经理指数(PMI)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_m: kwargs["start_m"] = start_m
    if end_m: kwargs["end_m"] = end_m
    df = pro.cn_pmi(**kwargs)
    return df_to_list(df)
