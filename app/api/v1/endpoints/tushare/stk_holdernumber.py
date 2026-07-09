"""Tushare 接口: stk_holdernumber - 股东人数

获取上市公司股东户数变化数据。
适用场景：判断筹码集中度、主力吸筹信号。
Tushare接口名: stk_holdernumber

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/stk-holdernumber/{code}")
async def ts_stk_holdernumber(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取股东人数"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.stk_holdernumber(ts_code=ts_code, limit=limit)
    return df_to_list(df)
