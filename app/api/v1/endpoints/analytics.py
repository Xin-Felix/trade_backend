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



@router.post("/intraday/sync")
async def sync_intraday_data(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD，默认今天"),
    user: User = Depends(get_current_user),
) -> dict:
    """触发全市场分时K线数据采集（后台运行）。

    拉取全A股当日 1 分钟 K 线数据存入数据库。
    约 5000 只股票，预计需要 10-20 分钟。
    """
    from fastapi import BackgroundTasks

    td = date.fromisoformat(trade_date) if trade_date else date.today()

    import threading
    from app.analytics.intraday_sync import sync_all_intraday

    t = threading.Thread(target=sync_all_intraday, args=(td,), daemon=True)
    t.start()

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "status": "started",
            "message": f"分时数据采集已启动 ({td})，预计 10-20 分钟完成",
        },
    }


@router.get("/intraday/status")
async def intraday_status(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
) -> dict:
    """查看分时数据采集状态（当天有多少条数据）。"""
    from sqlalchemy import text
    from app.db.base import SessionLocal

    td = date.fromisoformat(trade_date) if trade_date else date.today()

    db = SessionLocal()
    try:
        try:
            row = db.execute(
                text("SELECT COUNT(*), COUNT(DISTINCT ts_code) FROM stock_intraday WHERE trade_date = :td"),
                {"td": td}
            ).fetchone()
            total_records = row[0]
            total_stocks = row[1]
        except Exception:
            db.rollback()
            total_records = 0
            total_stocks = 0

        return {
            "success": True,
            "data": {
                "trade_date": td.isoformat(),
                "total_records": total_records,
                "total_stocks": total_stocks,
                "estimated_minutes": 240,  # A股一天 240 分钟
            },
        }
    finally:
        db.close()
