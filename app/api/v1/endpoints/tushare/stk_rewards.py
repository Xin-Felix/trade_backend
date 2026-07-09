"""Tushare 接口: stk_rewards - 管理层薪酬

获取上市公司管理层薪酬和持股数据。
适用场景：了解高管待遇。
Tushare接口名: stk_rewards

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/stk-rewards/{code}")
async def ts_stk_rewards(
    code: str,
    limit: int = Query(10, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取管理层薪酬"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.stk_rewards(ts_code=ts_code, limit=limit)
    return df_to_list(df)
