"""Tushare 接口: report_rc - 券商盈利预测数据

获取券商（卖方）每天研报的盈利预测数据。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/report-rc")
async def ts_report_rc(
    code: str = Query("", description="股票代码（可选）"),
    trade_date: str = Query("", description="交易日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """券商盈利预测数据"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code: kwargs["ts_code"] = normalize_code(code)
    if trade_date: kwargs["trade_date"] = trade_date
    df = pro.report_rc(**kwargs)
    return df_to_list(df)
