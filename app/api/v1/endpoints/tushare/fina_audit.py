"""Tushare 接口: fina_audit - 审计意见

获取上市公司财务审计意见数据。
适用场景：排查财务风险、避免审计问题股。
Tushare接口名: fina_audit

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/fina-audit/{code}")
async def ts_fina_audit(
    code: str,
    limit: int = Query(5, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取财务审计意见"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.fina_audit(ts_code=ts_code, limit=limit)
    return df_to_list(df)
