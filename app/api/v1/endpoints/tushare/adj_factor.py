"""Tushare 接口: adj_factor - 复权因子

获取股票复权因子数据，用于计算前/后复权价格。
适用场景：自行计算复权价格。
Tushare接口名: adj_factor

参数说明:
- ts_code: 股票代码（必填）
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/adj-factor/{code}")
async def ts_adj_factor(
    code: str,
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股票复权因子"""
    ts_code = normalize_code(code)
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.adj_factor(**kwargs)
    return df_to_list(df)
