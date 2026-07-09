"""Tushare 接口: pro_bar - 复权行情

获取股票复权行情数据，支持前复权/后复权。
适用场景：查看真实涨跌幅、策略回测。
Tushare接口名: pro_bar（通过 ts.pro_bar 调用）

参数说明:
- ts_code: 股票代码（必填，如 000001.SZ）
- adj: 复权类型 qfq前复权 hfq后复权 None不复权
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import df_to_list, normalize_code

router = APIRouter()


@router.get("/pro-bar/{code}")
async def ts_pro_bar(
    code: str,
    adj: str = Query("qfq", description="复权类型 qfq/hfq/None"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(60, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股票复权行情"""
    import tushare as ts
    ts_code = normalize_code(code)
    kwargs: dict = {"ts_code": ts_code, "adj": adj if adj != "None" else None, "limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = ts.pro_bar(**kwargs)
    return df_to_list(df)
