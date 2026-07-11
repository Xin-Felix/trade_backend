"""数据加工/衍生指标接口。

提供经过聚合计算的衍生数据，如概念资金流、板块动量等。
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.core.dependencies import get_current_user
from app.db.base import SessionLocal
from app.schemas.user import User

router = APIRouter()


def _resolve_trade_date(trade_date_str: Optional[str]) -> date:
    """解析交易日期：指定了就用指定的，否则取 stock_intraday 中最新的交易日。"""
    if trade_date_str:
        return date.fromisoformat(trade_date_str)

    # 自动取最新有数据的交易日
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT MAX(trade_date) FROM stock_intraday")
        ).scalar()
        if row:
            return row
    except Exception:
        db.rollback()
    finally:
        db.close()

    return date.today()


# ============================================================
# 概念资金流接口
# ============================================================


@router.get("/concept-flow")
async def get_concept_flow(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD，默认今天"),
    top_n: int = Query(20, ge=5, le=50, description="取前 N 个概念"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取概念板块资金流排名。

    基于 stock_intraday 分时数据聚合每个概念下所有成分股的资金流入/流出，
    按净流入排名。若无分时数据则降级为 stock_moneyflow 日级数据。

    用途：iOS 概念资金流列表排名。
    """
    from app.analytics.concept_flow import get_concept_flow_summary

    td = _resolve_trade_date(trade_date)
    results = get_concept_flow_summary(trade_date=td, top_n=top_n)

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "concepts": results,
        },
    }


@router.get("/concept-flow/minute")
async def get_concept_flow_minute(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    top_n: int = Query(10, ge=1, le=30, description="取前 N 个概念（不指定concept_ids时生效）"),
    concept_ids: Optional[str] = Query(None, description="指定概念ID列表，逗号分隔，如 885728.TI,885756.TI"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取概念板块分钟级资金流走势（多概念）。

    每个概念包含 241 个分钟数据点（09:30 ~ 15:00），
    含净流入、累计净流入、涨跌股票数等。

    - 传 concept_ids: 用指定的概念
    - 不传: 使用默认热门概念列表

    用途：iOS 概念资金流动态走势动画、多概念对比图。
    """
    from app.analytics.concept_flow import compute_concept_minute_flow

    td = _resolve_trade_date(trade_date)
    ids = concept_ids.split(",") if concept_ids else None
    results = compute_concept_minute_flow(trade_date=td, concept_ids=ids, top_n_concepts=top_n)

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "concepts": results,
        },
    }


@router.get("/industry-flow/minute")
async def get_industry_flow_minute(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    top_n: int = Query(15, ge=1, le=50, description="取前 N 个行业"),
    industries: Optional[str] = Query(None, description="指定行业名称列表，逗号分隔，如 半导体,软件服务"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取行业板块分钟级资金流走势。

    基于 stock_basic.industry 分组聚合分时数据。
    输出字段名与 concept-flow/minute 保持一致，前端可直接复用。
    """
    from app.analytics.concept_flow import compute_industry_minute_flow

    td = _resolve_trade_date(trade_date)
    ids = industries.split(",") if industries else None
    results = compute_industry_minute_flow(trade_date=td, industry_ids=ids, top_n_industries=top_n)

    return {
        "success": True,
        "data": {
            "trade_date": td.isoformat(),
            "industries": results,
        },
    }


@router.get("/industry-flow/list")
async def get_available_industries(
    user: User = Depends(get_current_user),
) -> dict:
    """获取可选的行业列表。"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT industry, COUNT(*) as cnt
            FROM stock_basic
            WHERE industry IS NOT NULL AND industry != ''
            GROUP BY industry
            ORDER BY cnt DESC
        """)).fetchall()
    finally:
        db.close()

    industries = [
        {"name": row[0], "stock_count": row[1]}
        for row in rows
    ]

    return {
        "success": True,
        "data": {
            "industries": industries,
            "total": len(industries),
        },
    }


@router.get("/concept-flow/concepts")
async def get_available_concepts(
    user: User = Depends(get_current_user),
) -> dict:
    """获取可选的概念板块列表（含默认推荐）。

    返回所有概念及其成分股数量，并标记推荐的默认概念。
    用途：iOS 端概念选择器。
    """
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT concept_id, concept_name, COUNT(*) as cnt
            FROM stock_concept
            GROUP BY concept_id, concept_name
            ORDER BY cnt DESC
            LIMIT 100
        """)).fetchall()
    finally:
        db.close()

    # 默认推荐概念（排除过于宽泛的如融资融券/沪深股通）
    default_ids = [
        "885728.TI",  # 人工智能
        "885756.TI",  # 芯片概念
        "885431.TI",  # 新能源汽车
        "886100.TI",  # DeepSeek概念
        "885921.TI",  # 储能
        "885700.TI",  # 军工
        "885531.TI",  # 光伏概念
        "886069.TI",  # 人形机器人
        "885517.TI",  # 机器人概念
        "886067.TI",  # 低空经济
        "885806.TI",  # 华为概念
        "885800.TI",  # 消费电子概念
    ]

    concepts = []
    for row in rows:
        concepts.append({
            "concept_id": row[0],
            "concept_name": row[1],
            "stock_count": row[2],
            "is_default": row[0] in default_ids,
        })

    return {
        "success": True,
        "data": {
            "concepts": concepts,
            "default_ids": default_ids,
        },
    }


@router.get("/concept-flow/detail")
async def get_concept_flow_detail(
    concept_id: str = Query(..., description="概念ID，如 885760.TI"),
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取单个概念的分钟级资金流走势。

    包含该概念每分钟的净流入、累计净流入、流入/流出金额、涨跌股票数。
    用于 iOS 概念详情页的资金流分钟走势折线图。
    """
    from app.analytics.concept_flow import get_concept_minute_trend

    td = _resolve_trade_date(trade_date)
    result = get_concept_minute_trend(concept_id=concept_id, trade_date=td)

    return {
        "success": True,
        "data": result,
    }


@router.get("/stock-flow/minute")
async def get_stock_flow_minute(
    code: str = Query(..., description="股票代码，如 000001.SZ"),
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取单只股票的分时资金流走势。

    基于分时K线：close >= open 为流入，否则为流出。
    每分钟包含净流入、累计净流入、成交量、收盘价。

    用途：iOS 个股详情页资金流分时图。
    """
    from app.analytics.concept_flow import get_stock_intraday_flow

    td = _resolve_trade_date(trade_date)
    result = get_stock_intraday_flow(ts_code=code, trade_date=td)

    return {
        "success": True,
        "data": result,
    }


# ============================================================
# 分时数据管理接口
# ============================================================


@router.post("/intraday/sync")
async def sync_intraday_data(
    days: int = Query(5, ge=1, le=10, description="采集最近几个交易日，默认5"),
    user: User = Depends(get_current_user),
) -> dict:
    """触发全市场分时K线数据采集（后台运行）。

    拉取全A股最近 N 个交易日的 1 分钟 K 线数据存入数据库。
    约 5500 只股票 × N天，4 线程并发，预计 40-50 分钟/天。
    """
    import threading
    from app.analytics.intraday_sync import sync_all_intraday

    t = threading.Thread(target=sync_all_intraday, kwargs={"days": days}, daemon=True)
    t.start()

    return {
        "success": True,
        "data": {
            "days": days,
            "status": "started",
            "message": f"分时数据采集已启动 (最近{days}个交易日)，预计 {days * 45} 分钟完成",
        },
    }


@router.get("/intraday/status")
async def intraday_status(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
) -> dict:
    """查看分时数据状态（各交易日有多少条数据）。"""
    from sqlalchemy import text
    from app.db.base import SessionLocal

    td = date.fromisoformat(trade_date) if trade_date else None

    db = SessionLocal()
    try:
        if td:
            # 单天查询
            row = db.execute(
                text("SELECT COUNT(*), COUNT(DISTINCT ts_code) FROM stock_intraday WHERE trade_date = :td"),
                {"td": td},
            ).fetchone()
            return {
                "success": True,
                "data": {
                    "trade_date": td.isoformat(),
                    "total_records": row[0],
                    "total_stocks": row[1],
                    "minutes_per_day": 241,
                },
            }
        else:
            # 查所有交易日的汇总
            rows = db.execute(
                text("""
                    SELECT trade_date, COUNT(*) as records, COUNT(DISTINCT ts_code) as stocks
                    FROM stock_intraday
                    GROUP BY trade_date
                    ORDER BY trade_date DESC
                """)
            ).fetchall()
            days_data = [
                {"trade_date": str(row[0]), "records": row[1], "stocks": row[2]}
                for row in rows
            ]
            return {
                "success": True,
                "data": {
                    "days": days_data,
                    "total_days": len(days_data),
                },
            }
    except Exception:
        db.rollback()
        return {"success": True, "data": {"days": [], "total_days": 0}}
    finally:
        db.close()
