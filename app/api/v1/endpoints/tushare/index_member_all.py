"""Tushare 接口: index_member_all - 申万行业成分(分级)

按三级分类提取申万行业成分，也可按股票代码提取所属分类。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/index-member-all")
async def ts_index_member_all(
    ts_code: str = Query("", description="申万指数代码（可选）"),
    code: str = Query("", description="股票代码（可选，查其所属行业）"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """申万行业成分(分级)"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if ts_code: kwargs["ts_code"] = ts_code
    if code: kwargs["code"] = code
    df = pro.index_member_all(**kwargs)
    return df_to_list(df)
