"""Tushare 接口: forecast - 业绩预告

获取上市公司业绩预告数据。
适用场景：提前判断业绩方向、埋伏业绩超预期。
Tushare接口名: forecast

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/forecast/{code}")
async def ts_forecast(
    code: str,
    limit: int = Query(5, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取业绩预告数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.forecast(ts_code=ts_code, limit=limit)
    return df_to_list(df)
