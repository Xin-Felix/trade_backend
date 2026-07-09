"""Tushare 接口: stk_nineturn - 神奇九转指标

基于TD序列的趋势反转指标
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, today, normalize_code

router = APIRouter()


@router.get("/stk-nineturn/{code}")
async def ts_stk_nineturn(
    code: str,
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """神奇九转指标"""
    ts_code = normalize_code(code)
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "limit": limit}
    if start_date: kwargs["start_date"] = start_date
    if end_date: kwargs["end_date"] = end_date
    df = pro.stk_nineturn(**kwargs)
    return df_to_list(df)
