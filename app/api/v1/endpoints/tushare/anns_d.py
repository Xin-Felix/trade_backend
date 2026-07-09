"""Tushare 接口: anns_d - 上市公司公告

获取全量公告数据，提供pdf下载URL。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/anns-d")
async def ts_anns_d(
    code: str = Query("", description="股票代码（可选）"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """上市公司公告"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code: kwargs["ts_code"] = normalize_code(code)
    if trade_date: kwargs["trade_date"] = trade_date
    df = pro.anns_d(**kwargs)
    return df_to_list(df)
