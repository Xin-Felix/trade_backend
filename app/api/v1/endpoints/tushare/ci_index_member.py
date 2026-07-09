"""Tushare 接口: ci_index_member - 中信行业成分

按三级分类提取中信行业成分。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/ci-index-member")
async def ts_ci_index_member(
    ts_code: str = Query("", description="中信指数代码（可选）"),
    code: str = Query("", description="股票代码（可选）"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """中信行业成分"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code: kwargs["ts_code"] = ts_code
    if code: kwargs["code"] = code
    df = pro.ci_index_member(**kwargs)
    return df_to_list(df)
