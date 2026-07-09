"""Tushare 接口: cn_schedule - 中国经济数据发布日程

获取国家统计局、中国人民银行等经济数据发布日程。
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/cn-schedule")
async def ts_cn_schedule(
    month: str = Query("", description="月份 YYYYMM"),
    limit: int = Query(200, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """中国经济数据发布日程"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if month:
        kwargs["month"] = month
    df = pro.cn_schedule(**kwargs)
    return df_to_list(df)
