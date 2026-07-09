"""Tushare 接口: ths_daily - THS板块行情

获取同花顺概念板块日线行情。
适用场景：板块趋势分析。
Tushare接口名: ths_daily

参数说明:
- ts_code: 板块代码（必填，TI格式如 885760.TI，不需要normalize）
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/ths-daily/{code}")
async def ts_ths_daily(
    code: str,
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取THS板块日线行情"""
    pro = get_pro()
    kwargs: dict = {"ts_code": code, "limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.ths_daily(**kwargs)
    return df_to_list(df)
