"""Tushare 接口: top10_holders - 前十大股东

获取上市公司前十大股东数据。
适用场景：分析股权集中度、大股东动向。
Tushare接口名: top10_holders

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/top10-holders/{code}")
async def ts_top10_holders(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取前十大股东"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.top10_holders(ts_code=ts_code, limit=limit)
    return df_to_list(df)
