"""数据同步接口，供后台管理面板调用。"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.user import User

router = APIRouter()


def _run_sync_recent(days: int):
    """后台任务：增量同步最近几天的数据。"""
    from app.db.base import SessionLocal
    from app.services.data_sync_service import (
        _sync_daily_basic_by_date,
        _sync_klines_by_date,
        sync_index_daily,
        sync_moneyflow_hsgt,
        sync_sector_moneyflow,
        sync_stock_limit,
        sync_stock_moneyflow,
    )

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    try:
        _sync_klines_by_date(db, "D", start_date, end_date)
        _sync_daily_basic_by_date(db, start_date, end_date)
        db.commit()
    finally:
        db.close()

    sync_sector_moneyflow(sector_type="industry", start_date=start_date, end_date=end_date)
    sync_sector_moneyflow(sector_type="concept", start_date=start_date, end_date=end_date)
    sync_stock_moneyflow(start_date=start_date, end_date=end_date)
    sync_moneyflow_hsgt(start_date=start_date, end_date=end_date)
    sync_index_daily(start_date=start_date, end_date=end_date)
    sync_stock_limit(start_date=start_date, end_date=end_date)


@router.post("/recent")
async def sync_recent(
    background_tasks: BackgroundTasks,
    days: int = Query(3, ge=1, le=30, description="同步最近多少天"),
    user: User = Depends(get_current_user),
) -> dict:
    """触发增量同步（后台执行），同步日K线、日线因子、板块资金流等。"""
    background_tasks.add_task(_run_sync_recent, days)
    return {"status": "started", "days": days, "message": f"正在后台同步最近 {days} 天数据"}


@router.post("/daily-kline")
async def sync_daily_kline(
    background_tasks: BackgroundTasks,
    days: int = Query(1, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """仅同步日K线。"""
    from app.db.base import SessionLocal
    from app.services.data_sync_service import _sync_klines_by_date

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        db = SessionLocal()
        try:
            _sync_klines_by_date(db, "D", start_date, end_date)
            db.commit()
        finally:
            db.close()

    background_tasks.add_task(task)
    return {"status": "started", "type": "daily_kline", "days": days}


@router.post("/daily-basic")
async def sync_daily_basic_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(1, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """仅同步日线因子。"""
    from app.db.base import SessionLocal
    from app.services.data_sync_service import _sync_daily_basic_by_date

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        db = SessionLocal()
        try:
            _sync_daily_basic_by_date(db, start_date, end_date)
            db.commit()
        finally:
            db.close()

    background_tasks.add_task(task)
    return {"status": "started", "type": "daily_basic", "days": days}


@router.post("/sector-moneyflow")
async def sync_sector_moneyflow_endpoint(
    background_tasks: BackgroundTasks,
    sector_type: str = Query("industry", pattern="^(industry|concept)$"),
    days: int = Query(3, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """同步板块资金流。"""
    from app.services.data_sync_service import sync_sector_moneyflow

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        sync_sector_moneyflow(sector_type=sector_type, start_date=start_date, end_date=end_date)

    background_tasks.add_task(task)
    return {"status": "started", "type": f"sector_moneyflow_{sector_type}", "days": days}


@router.post("/stock-moneyflow")
async def sync_stock_moneyflow_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(3, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """同步个股资金流。"""
    from app.services.data_sync_service import sync_stock_moneyflow

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        sync_stock_moneyflow(start_date=start_date, end_date=end_date)

    background_tasks.add_task(task)
    return {"status": "started", "type": "stock_moneyflow", "days": days}


@router.post("/index-daily")
async def sync_index_daily_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(3, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """同步指数日线。"""
    from app.services.data_sync_service import sync_index_daily

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        sync_index_daily(start_date=start_date, end_date=end_date)

    background_tasks.add_task(task)
    return {"status": "started", "type": "index_daily", "days": days}


@router.post("/hsgt")
async def sync_hsgt_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(3, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """同步沪深港通资金流。"""
    from app.services.data_sync_service import sync_moneyflow_hsgt

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        sync_moneyflow_hsgt(start_date=start_date, end_date=end_date)

    background_tasks.add_task(task)
    return {"status": "started", "type": "moneyflow_hsgt", "days": days}


@router.post("/stock-limit")
async def sync_stock_limit_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(3, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """同步涨跌停。"""
    from app.services.data_sync_service import sync_stock_limit

    def task():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        sync_stock_limit(start_date=start_date, end_date=end_date)

    background_tasks.add_task(task)
    return {"status": "started", "type": "stock_limit", "days": days}


def _run_sync_concepts():
    """后台任务：同步全部概念板块及其成分股到 stock_concept 表。

    使用 ths_index (type=N 概念板块) + ths_member 接口，
    因为 concept/concept_detail 接口已被 Tushare 弃用。
    """
    import time
    import logging

    from sqlalchemy.dialects.postgresql import insert
    from app.db.base import SessionLocal
    from app.models.stock import StockConcept
    from app.services.stock_service import get_pro

    logger = logging.getLogger(__name__)
    pro = get_pro()

    # 1. 获取全部同花顺概念指数列表 (type=N 表示概念)
    df_concepts = pro.ths_index(exchange="A", type="N",
        fields="ts_code,name,count,exchange,list_date,type")
    if df_concepts is None or df_concepts.empty:
        logger.warning("sync_concepts: 获取概念列表为空")
        return

    logger.info(f"sync_concepts: 共 {len(df_concepts)} 个概念板块，开始逐个拉取成分股...")

    db = SessionLocal()
    total_inserted = 0
    try:
        for idx, row in df_concepts.iterrows():
            concept_code = row["ts_code"]  # 如 885760.TI
            concept_name = row["name"]

            try:
                df_members = pro.ths_member(ts_code=concept_code,
                    fields="ts_code,code,name")
            except Exception as e:
                logger.warning(f"sync_concepts: 拉取概念 {concept_code}({concept_name}) 成分失败: {e}")
                time.sleep(0.3)
                continue

            if df_members is None or df_members.empty:
                time.sleep(0.2)
                continue

            records = []
            for _, member_row in df_members.iterrows():
                con_code = member_row.get("code") or member_row.get("ts_code")
                con_name = member_row.get("name")
                if not con_code:
                    continue
                records.append({
                    "concept_id": concept_code,
                    "concept_name": concept_name,
                    "ts_code": con_code,
                    "name": con_name,
                    "in_date": None,
                    "out_date": None,
                })

            if records:
                stmt = insert(StockConcept.__table__).values(records)
                stmt = stmt.on_conflict_do_update(
                    constraint="uix_stock_concept",
                    set_={
                        "concept_name": stmt.excluded.concept_name,
                        "name": stmt.excluded.name,
                    }
                )
                db.execute(stmt)
                db.commit()
                total_inserted += len(records)

            # Tushare 限流
            time.sleep(0.35)

            if (idx + 1) % 50 == 0:
                logger.info(f"sync_concepts: 已处理 {idx + 1}/{len(df_concepts)} 个概念，累计 {total_inserted} 条记录")

        logger.info(f"sync_concepts: 完成！共处理 {len(df_concepts)} 个概念，{total_inserted} 条映射记录")
    except Exception as e:
        logger.error(f"sync_concepts: 同步异常: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/concept")
async def sync_concept_endpoint(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> dict:
    """同步全部概念板块成分股映射（耗时较长，后台执行）。"""
    background_tasks.add_task(_run_sync_concepts)
    return {"status": "started", "type": "stock_concept", "message": "正在后台同步全部概念板块成分股，预计需要几分钟"}
