"""Tushare 接口: mkt_idx_bmk - 基金业绩基准

获取官方发布的ETF业绩比较基准列表信息。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/mkt-idx-bmk")
async def ts_mkt_idx_bmk(
    ts_code: str = Query("", description="基金代码"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """基金业绩基准"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.mkt_idx_bmk(**kwargs)
    return df_to_list(df)
