"""Tushare 接口: top10_floatholders - 前十大流通股东

获取上市公司前十大流通股东数据。
适用场景：分析机构持仓、游资介入情况。
Tushare接口名: top10_floatholders

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/top10-floatholders/{code}")
async def ts_top10_floatholders(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取前十大流通股东"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.top10_floatholders(ts_code=ts_code, limit=limit)
    return df_to_list(df)
