"""Tushare 接口: share_float - 限售股解禁

获取限售股解禁数据。
适用场景：规避解禁压力、关注解禁日期。
Tushare接口名: share_float

参数说明:
- ts_code: 股票代码（可选）
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/share-float")
async def ts_share_float(
    code: str = Query("", description="股票代码（可选）"),
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取限售股解禁数据"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if code:
        kwargs["ts_code"] = normalize_code(code)
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.share_float(**kwargs)
    return df_to_list(df)
