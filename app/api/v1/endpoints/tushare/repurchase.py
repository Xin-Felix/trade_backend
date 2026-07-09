"""Tushare 接口: repurchase - 股票回购

获取上市公司回购股票数据。
适用场景：跟踪公司回购计划和进展。
Tushare接口名: repurchase

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/repurchase/{code}")
async def ts_repurchase(
    code: str,
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股票回购数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.repurchase(ts_code=ts_code, limit=limit)
    return df_to_list(df)
