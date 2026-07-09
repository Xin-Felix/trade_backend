"""Tushare 接口: pledge_detail - 质押明细

获取股票质押明细数据。
适用场景：查看具体质押笔数和规模。
Tushare接口名: pledge_detail

参数说明:
- ts_code: 股票代码（必填）
- limit: 返回条数
"""

from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user
from app.schemas.user import User
from ._base import get_pro, df_to_list, normalize_code

router = APIRouter()


@router.get("/pledge-detail/{code}")
async def ts_pledge_detail(
    code: str,
    limit: int = Query(20, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """获取质押明细"""
    ts_code = normalize_code(code)
    pro = get_pro()
    df = pro.pledge_detail(ts_code=ts_code, limit=limit)
    return df_to_list(df)
