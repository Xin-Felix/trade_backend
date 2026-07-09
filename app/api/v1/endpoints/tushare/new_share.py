"""Tushare 接口: new_share - IPO新股

获取新股上市列表数据。
适用场景：打新跟踪、新股分析。
Tushare接口名: new_share

参数说明:
- start_date: 开始日期 YYYYMMDD
- end_date: 结束日期 YYYYMMDD
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/new-share")
async def ts_new_share(
    start_date: str = Query("", description="开始日期 YYYYMMDD"),
    end_date: str = Query("", description="结束日期 YYYYMMDD"),
    limit: int = Query(50, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取IPO新股列表"""
    pro = get_pro()
    kwargs: dict = {"limit": limit}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    df = pro.new_share(**kwargs)
    return df_to_list(df)
