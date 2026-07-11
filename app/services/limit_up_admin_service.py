"""涨停板天梯后台管理服务。

为后台管理页面提供：
- 数据依赖概览
- 各数据源最新状态
- 手动触发同步
- 调度任务配置查询
"""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.analysis import LimitCptList, LimitListD, LimitStep
from app.models.stock import StockConcept
from app.services.analysis_sync_service import (
    sync_limit_cpt_list,
    sync_limit_list_d,
    sync_limit_step,
)
from app.services.scheduler_service import get_all_job_configs


# 数据依赖定义
DEPENDENCIES = [
    {
        "key": "limit_cpt_list",
        "name": "涨停最强板块统计",
        "table": "limit_cpt_list",
        "description": "同花顺概念板块涨停家数统计，用于顶部概念标签",
        "has_trade_date": True,
    },
    {
        "key": "limit_step",
        "name": "涨停连板天梯",
        "table": "limit_step",
        "description": "个股连板天数，用于 8板/3板/2板/首板 分组",
        "has_trade_date": True,
    },
    {
        "key": "limit_list_d",
        "name": "涨跌停明细",
        "table": "limit_list_d",
        "description": "涨停个股首次涨停时间、打开次数、封单强度等明细",
        "has_trade_date": True,
    },
    {
        "key": "stock_concept",
        "name": "股票概念映射",
        "table": "stock_concept",
        "description": "个股所属概念，用于个股卡片下的概念标签",
        "has_trade_date": False,
    },
]


def _get_table_stats(db, table_cls, has_trade_date: bool = True):
    """获取表最新交易日和记录数。"""
    if has_trade_date:
        latest = db.execute(
            select(table_cls.trade_date).order_by(table_cls.trade_date.desc()).limit(1)
        ).scalar_one_or_none()
    else:
        latest = "长期有效"
    total = db.execute(select(func.count()).select_from(table_cls)).scalar() or 0
    return {"latest_trade_date": latest, "total_records": total}


def get_limit_up_ladder_overview() -> dict:
    """获取涨停板天梯功能的数据依赖概览。"""
    db = SessionLocal()
    try:
        # 聚合接口最新可查询日期
        latest_date = db.execute(
            select(LimitListD.trade_date).order_by(LimitListD.trade_date.desc()).limit(1)
        ).scalar_one_or_none()

        # 各依赖表状态
        table_stats = {
            "limit_cpt_list": _get_table_stats(db, LimitCptList),
            "limit_step": _get_table_stats(db, LimitStep),
            "limit_list_d": _get_table_stats(db, LimitListD),
            "stock_concept": _get_table_stats(db, StockConcept, has_trade_date=False),
        }

        dependencies = []
        for dep in DEPENDENCIES:
            stats = table_stats.get(dep["key"], {})
            dependencies.append({
                **dep,
                "latest_trade_date": stats.get("latest_trade_date"),
                "total_records": stats.get("total_records"),
            })

        # 调度任务配置
        all_jobs = get_all_job_configs()
        scheduler_job = next((j for j in all_jobs if j["job_id"] == "sync_limit_data"), None)

        return {
            "feature_name": "涨停板天梯",
            "api_endpoint": "/api/v1/stocks/limit-up-ladder",
            "latest_trade_date": latest_date.strftime("%Y%m%d") if latest_date else None,
            "scheduler_job": scheduler_job,
            "dependencies": dependencies,
        }
    finally:
        db.close()


def sync_limit_up_ladder_dependencies(trade_date: date | None = None, days: int = 1) -> dict:
    """手动触发涨停板天梯相关数据源的同步。

    Args:
        trade_date: 指定日期，不传则同步最近 days 天
        days: 同步天数
    Returns:
        {"synced_tables": [...], "start_date": "YYYYMMDD", "end_date": "YYYYMMDD"}
    """
    if trade_date:
        start_date = trade_date
        end_date = trade_date
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

    sync_limit_list_d(start_date=start_date, end_date=end_date)
    sync_limit_step(start_date=start_date, end_date=end_date)
    sync_limit_cpt_list(start_date=start_date, end_date=end_date)

    return {
        "synced_tables": ["limit_list_d", "limit_step", "limit_cpt_list"],
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
    }
