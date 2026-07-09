"""Tushare 接口: p_save - 组合保存

创建或修改自选股组合。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/p-save")
async def ts_p_save(
    group_name: str = Query(..., description="组合名称"),
    ts_code: str = Query("", description="股票代码列表，逗号分隔"),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """组合保存"""
    pro = get_pro()
    kwargs: dict = {"group_name": group_name}
    if ts_code:
        kwargs["ts_code"] = ts_code
    df = pro.p_save(**kwargs)
    return df_to_list(df)
