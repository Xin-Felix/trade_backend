"""Tushare 接口: express - 业绩快报

获取上市公司业绩快报数据。
适用场景：快速了解最新业绩情况。
Tushare接口名: express

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/express/{code}")
async def ts_express(
    code: str,
    limit: int = Query(5, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取业绩快报数据"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.express(ts_code=ts_code, limit=limit)
    return df_to_list(df)
