"""Tushare 接口: ths_index - THS板块分类

获取同花顺概念板块指数列表。
适用场景：查看所有同花顺板块分类。
Tushare接口名: ths_index

参数说明:
- exchange: 交易所（A股票 HK港股 US美股，默认A）
- type: 类型（N概念 I行业 S特色，可选）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list

router = APIRouter()


@router.get("/ths-index")
async def ts_ths_index(
    exchange: str = Query("A", description="交易所 A/HK/US"),
    type: str = Query("", description="类型 N概念 I行业 S特色"),
    limit: int = Query(500, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取THS板块分类"""
    pro = get_pro()
    kwargs: dict = {"exchange": exchange, "limit": limit}
    if type:
        kwargs["type"] = type
    df = pro.ths_index(**kwargs)
    return df_to_list(df)
