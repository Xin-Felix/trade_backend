"""Tushare 接口: fina_mainbz - 主营业务构成

获取上市公司主营业务构成数据，按产品或地区分。
适用场景：分析公司收入来源结构。
Tushare接口名: fina_mainbz

参数说明:
- ts_code: 股票代码（必填）
- period: 报告期（可选，如 20231231）
- type: 类型 P按产品 D按地区（默认P）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/fina-mainbz/{code}")
async def ts_fina_mainbz(
    code: str,
    period: str = Query("", description="报告期 如 20231231"),
    type: str = Query("P", description="类型 P按产品 D按地区"),
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取主营业务构成"""
    ts_code = normalize_code(code)
    pro = get_pro()
    kwargs: dict = {"ts_code": ts_code, "type": type, "limit": limit}
    if period:
        kwargs["period"] = period
    df = pro.fina_mainbz(**kwargs)
    return df_to_list(df)
