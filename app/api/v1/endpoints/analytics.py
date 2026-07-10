"""数据加工/衍生指标接口。

提供经过聚合计算的衍生数据，如概念资金流、板块动量等。
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/concept-flow")
async def get_concept_flow(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD，默认今天"),
    top_n: int = Query(20, ge=5, le=50, description="取前 N 个概念"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取概念板块资金流排名。

    聚合每个概念下所有成分股的资金流入/流出数据，
    返回按净流入排名的概念列表。

    用途：iOS 概念资金流动画、热力图展示。
    """
    from app.analytics.concept_flow import get_concept_flow_summary

    td = date.fromisoformat(trade_date) if trade_date else date.today()

    results = get_concept_flow_summary(trade_date=td, top_n=top_n)

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "concepts": results,
        },
    }


@router.get("/concept-flow/detail")
async def get_concept_flow_detail(
    concept_id: str = Query(..., description="概念ID，如 885760.TI"),
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取单个概念的详细资金流数据（含成分股明细）。"""
    from app.analytics.concept_flow import compute_concept_minute_flow

    td = date.fromisoformat(trade_date) if trade_date else date.today()

    results = compute_concept_minute_flow(
        trade_date=td,
        concept_ids=[concept_id],
        top_n_concepts=1,
    )

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "concept_id": concept_id,
            "flow": results[0] if results else None,
        },
    }
