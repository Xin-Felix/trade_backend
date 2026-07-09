"""Tushare 接口: disclosure_date - 财报披露日期

获取财报披露计划日期。
适用场景：关注财报发布时间、提前布局。
Tushare接口名: disclosure_date

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/disclosure-date/{code}")
async def ts_disclosure_date(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取财报披露日期"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.disclosure_date(ts_code=ts_code, limit=limit)
    return df_to_list(df)
