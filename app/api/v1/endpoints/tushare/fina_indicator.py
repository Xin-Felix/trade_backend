"""Tushare 接口: fina_indicator - 财务指标

获取上市公司财务指标数据，包含ROE、毛利率、净利率、EPS等。
适用场景：基本面选股、财务分析。
Tushare接口名: fina_indicator

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/fina-indicator/{code}")
async def ts_fina_indicator(
    code: str,
    limit: int = Query(8, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取财务指标数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.fina_indicator(ts_code=ts_code, limit=limit)
    return df_to_list(df)
