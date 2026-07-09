"""Tushare 接口: fund_portfolio - 基金持仓（季度）

获取公募基金持仓数据
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/fund-portfolio/{code}")
async def ts_fund_portfolio(
    code: str,
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金持仓（季度）"""
    pro = get_pro()
    df = pro.fund_portfolio(ts_code=code, limit=limit)
    return df_to_list(df)
