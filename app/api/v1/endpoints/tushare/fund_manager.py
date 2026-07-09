"""Tushare 接口: fund_manager - 基金经理

获取公募基金经理数据，包括基金经理简历等。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-manager")
async def ts_fund_manager(
    code: str = Query("", description="基金代码（可选）"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金经理"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code: kwargs["ts_code"] = code
    df = pro.fund_manager(**kwargs)
    return df_to_list(df)
