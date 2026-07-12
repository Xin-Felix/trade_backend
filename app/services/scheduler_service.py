"""APScheduler 调度服务。

任务配置持久化到 scheduler_jobs 表，服务重启后自动恢复。
支持后台管理面板对每个任务单独配置触发时间。
执行日志记录到 scheduler_logs 表。
"""

import logging
import threading
import time as _time
from datetime import date, datetime, timedelta, timezone

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 1},
)


def _log_execution(job_id: str, func, kwargs):
    """执行任务并记录日志到数据库。"""
    from app.db.base import SessionLocal
    from app.models.scheduler_log import SchedulerLog

    db = SessionLocal()
    log_entry = SchedulerLog(
        job_id=job_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    start = _time.time()
    try:
        func(**kwargs)
        elapsed = int(_time.time() - start)
        log_entry.status = "success"
        log_entry.message = f"执行成功，耗时 {elapsed} 秒"
        log_entry.duration_seconds = elapsed
        log_entry.finished_at = datetime.now(timezone.utc)
    except Exception as e:
        elapsed = int(_time.time() - start)
        log_entry.status = "failed"
        log_entry.message = str(e)[:2000]
        log_entry.duration_seconds = elapsed
        log_entry.finished_at = datetime.now(timezone.utc)
        logger.error(f"[Scheduler] 任务 {job_id} 执行失败: {e}")
    finally:
        db.commit()
        db.close()


# ============================================================
# 预定义的同步任务函数
# ============================================================

def job_sync_daily_kline(days: int = 1):
    """同步日K线数据。"""
    from app.db.base import SessionLocal
    from app.services.data_sync_service import _sync_klines_by_date

    logger.info(f"[Scheduler] 开始同步日K线，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    db = SessionLocal()
    try:
        _sync_klines_by_date(db, "D", start_date, end_date)
        db.commit()
        logger.info("[Scheduler] 日K线同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 日K线同步失败: {e}")
        db.rollback()
    finally:
        db.close()


def job_sync_daily_basic(days: int = 1):
    """同步日线因子数据。"""
    from app.db.base import SessionLocal
    from app.services.data_sync_service import _sync_daily_basic_by_date

    logger.info(f"[Scheduler] 开始同步日线因子，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    db = SessionLocal()
    try:
        _sync_daily_basic_by_date(db, start_date, end_date)
        db.commit()
        logger.info("[Scheduler] 日线因子同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 日线因子同步失败: {e}")
        db.rollback()
    finally:
        db.close()


def job_sync_sector_moneyflow(days: int = 1):
    """同步板块资金流。"""
    from app.services.data_sync_service import sync_sector_moneyflow

    logger.info(f"[Scheduler] 开始同步板块资金流，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_sector_moneyflow(sector_type="industry", start_date=start_date, end_date=end_date)
        sync_sector_moneyflow(sector_type="concept", start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 板块资金流同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 板块资金流同步失败: {e}")


def job_sync_stock_moneyflow(days: int = 1):
    """同步个股资金流。"""
    from app.services.data_sync_service import sync_stock_moneyflow

    logger.info(f"[Scheduler] 开始同步个股资金流，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_stock_moneyflow(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 个股资金流同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 个股资金流同步失败: {e}")


def job_sync_index_daily(days: int = 1):
    """同步指数日线。"""
    from app.services.data_sync_service import sync_index_daily

    logger.info(f"[Scheduler] 开始同步指数日线，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_index_daily(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 指数日线同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 指数日线同步失败: {e}")


def job_sync_moneyflow_hsgt(days: int = 1):
    """同步沪深港通资金流。"""
    from app.services.data_sync_service import sync_moneyflow_hsgt

    logger.info(f"[Scheduler] 开始同步沪深港通，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_moneyflow_hsgt(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 沪深港通同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 沪深港通同步失败: {e}")


def job_sync_stock_limit(days: int = 1):
    """同步涨跌停。"""
    from app.services.data_sync_service import sync_stock_limit

    logger.info(f"[Scheduler] 开始同步涨跌停，最近 {days} 天")
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_stock_limit(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 涨跌停同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 涨跌停同步失败: {e}")


def job_sync_stock_basic(days: int = 1):
    """同步股票基础信息 + 上市公司详细信息。"""
    from app.services.data_sync_service import sync_stock_basic, sync_stock_company

    logger.info("[Scheduler] 开始同步股票基础信息")
    try:
        count_basic = sync_stock_basic()
        logger.info(f"[Scheduler] 股票基础信息同步完成: {count_basic} 条")
    except Exception as e:
        logger.error(f"[Scheduler] 股票基础信息同步失败: {e}")

    logger.info("[Scheduler] 开始同步上市公司详细信息")
    try:
        count_company = sync_stock_company()
        logger.info(f"[Scheduler] 上市公司详细信息同步完成: {count_company} 条")
    except Exception as e:
        logger.error(f"[Scheduler] 上市公司详细信息同步失败: {e}")


def job_sync_all(days: int = 1):
    """综合同步任务：日K线+日线因子+板块资金流+个股资金流+指数+沪深港通+涨跌停+龙虎榜+同花顺。"""
    from app.services.data_sync_service import sync_top_list, sync_top_inst, sync_ths_daily

    logger.info(f"[Scheduler] 开始综合同步，最近 {days} 天")
    job_sync_daily_kline(days)
    job_sync_daily_basic(days)
    job_sync_sector_moneyflow(days)
    job_sync_stock_moneyflow(days)
    job_sync_index_daily(days)
    job_sync_moneyflow_hsgt(days)
    job_sync_stock_limit(days)

    # 龙虎榜
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    try:
        sync_top_list(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 龙虎榜同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 龙虎榜同步失败: {e}")

    try:
        sync_top_inst(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 龙虎榜机构同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 龙虎榜机构同步失败: {e}")

    # 同花顺板块行情
    try:
        sync_ths_daily(start_date=start_date, end_date=end_date)
        logger.info("[Scheduler] 同花顺板块行情同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 同花顺板块行情同步失败: {e}")

    logger.info("[Scheduler] 综合同步完成")


# ============================================================
# 分析数据同步任务（打板/题材/机构/宏观/ETF/可转债）
# ============================================================


def job_sync_limit_data(days: int = 1):
    """同步打板数据（涨跌停+连板+THS榜单+涨停板块统计）。"""
    from app.services.analysis_sync_service import (
        sync_limit_cpt_list,
        sync_limit_list_d,
        sync_limit_list_ths,
        sync_limit_step,
    )
    logger.info(f"[Scheduler] 开始同步打板数据，最近 {days} 天")
    sync_limit_list_d(days=days)
    sync_limit_step(days=days)
    sync_limit_list_ths(days=days)
    sync_limit_cpt_list(days=days)
    logger.info("[Scheduler] 打板数据同步完成")


def job_sync_concept_hot(days: int = 1):
    """同步题材热点（DC概念+THS热榜+DC热榜）。"""
    from app.services.analysis_sync_service import sync_dc_concept, sync_ths_hot, sync_dc_hot
    logger.info(f"[Scheduler] 开始同步题材热点，最近 {days} 天")
    sync_dc_concept(days=days)
    sync_ths_hot(days=days)
    sync_dc_hot(days=days)
    logger.info("[Scheduler] 题材热点同步完成")


def job_sync_institution(days: int = 1):
    """同步机构行为数据（北向持仓+股东人数+增减持+筹码+两融）。"""
    from app.services.analysis_sync_service import (
        sync_hk_hold, sync_stk_holdernumber, sync_stk_holdertrade,
        sync_cyq_perf, sync_margin_detail,
    )
    logger.info(f"[Scheduler] 开始同步机构数据，最近 {days} 天")
    sync_hk_hold(days=days)
    sync_stk_holdernumber(days=max(days, 7))
    sync_stk_holdertrade(days=max(days, 7))
    sync_cyq_perf(days=days)
    sync_margin_detail(days=days)
    logger.info("[Scheduler] 机构数据同步完成")


def job_sync_research(days: int = 3):
    """同步研报数据（券商金股+盈利预测）。"""
    from app.services.analysis_sync_service import sync_broker_recommend, sync_report_rc
    logger.info(f"[Scheduler] 开始同步研报数据")
    sync_broker_recommend(days=days)
    sync_report_rc(days=days)
    logger.info("[Scheduler] 研报数据同步完成")


def job_sync_macro(days: int = 1):
    """同步宏观数据（指数估值+申万行业+CPI+PMI+LPR+社融）。"""
    from app.services.analysis_sync_service import (
        sync_index_dailybasic, sync_index_weight, sync_sw_daily,
        sync_cn_cpi, sync_cn_pmi, sync_shibor_lpr, sync_sf_month,
    )
    logger.info(f"[Scheduler] 开始同步宏观数据")
    sync_index_dailybasic(days=days)
    sync_index_weight(days=days)
    sync_sw_daily(days=days)
    sync_cn_cpi(days=days)
    sync_cn_pmi(days=days)
    sync_shibor_lpr(days=days)
    sync_sf_month(days=days)
    logger.info("[Scheduler] 宏观数据同步完成")


def job_sync_etf_cb(days: int = 1):
    """同步ETF和可转债数据。"""
    from app.services.analysis_sync_service import (
        sync_etf_basic, sync_etf_share_size, sync_cb_basic, sync_cb_daily,
    )
    logger.info(f"[Scheduler] 开始同步ETF/可转债数据，最近 {days} 天")
    sync_etf_basic(days=days)
    sync_etf_share_size(days=days)
    sync_cb_basic(days=days)
    sync_cb_daily(days=days)
    logger.info("[Scheduler] ETF/可转债同步完成")


def job_sync_intraday(days: int = 5):
    """同步全A股分时K线（最近 N 个交易日）。

    - 历史日期：Tushare 代理 stk_mins
    - 当天：16:00 前用 akshare，16:00 后用 Tushare
    """
    from app.analytics.intraday_sync import sync_all_intraday_mixed

    logger.info(f"[Scheduler] 开始同步分时K线，最近 {days} 个交易日")
    try:
        sync_all_intraday_mixed(days=days)
        logger.info("[Scheduler] 分时K线同步完成")
    except Exception as e:
        logger.error(f"[Scheduler] 分时K线同步失败: {e}")


def job_expire_memberships():
    """将会员到期记录标记为 expired。"""
    from app.db.base import SessionLocal
    from app.services import membership_service

    db = SessionLocal()
    try:
        count = membership_service.expire_memberships(db)
        logger.info(f"[Scheduler] 已处理 {count} 条过期会员")
    except Exception as e:
        logger.error(f"[Scheduler] 会员过期处理失败: {e}")
        db.rollback()
    finally:
        db.close()


def job_grant_monthly_points():
    """给活跃会员发放月度积分。"""
    from app.db.base import SessionLocal
    from app.services import membership_service

    db = SessionLocal()
    try:
        count = membership_service.grant_monthly_points_if_due(db)
        logger.info(f"[Scheduler] 已向 {count} 位会员发放月度积分")
    except Exception as e:
        logger.error(f"[Scheduler] 月度积分发放失败: {e}")
        db.rollback()
    finally:
        db.close()


def job_generate_daily_reviews(days: int = 1):
    """每日收盘后生成：
    1. 全市场一句话复盘（免费用户共用）
    2. 所有生效会员的深度复盘
    仅交易日执行。
    """
    from datetime import date
    from app.db.base import SessionLocal
    from app.services.daily_review_service import generate_deep_reviews_for_all_members
    from app.services.market_daily_review_service import generate_market_brief_sync

    logger.info("[Scheduler] 开始生成全市场一句话复盘")
    db = SessionLocal()
    try:
        report_date = date.today()
        market_report = generate_market_brief_sync(db, report_date)
        logger.info(f"[Scheduler] 全市场一句话复盘生成完成: {market_report.status}")
    except Exception as e:
        logger.error(f"[Scheduler] 全市场一句话复盘生成失败: {e}")
    finally:
        db.close()

    logger.info("[Scheduler] 开始生成会员深度复盘")
    try:
        result = generate_deep_reviews_for_all_members(
            report_date=report_date, skip_non_trading_day=True
        )
        logger.info(f"[Scheduler] 会员深度复盘生成完成: {result}")
    except Exception as e:
        logger.error(f"[Scheduler] 会员深度复盘生成失败: {e}")


def job_generate_ai_position_advices(days: int = 1):
    """为所有生效会员生成 AI 仓位建议（仅交易日执行）。"""
    from app.services.ai_position_advice_service import generate_position_advices_for_all_members
    from datetime import date

    logger.info("[Scheduler] 开始生成 AI 仓位建议")
    try:
        report_date = date.today()
        result = generate_position_advices_for_all_members(
            report_date=report_date, skip_non_trading_day=True
        )
        logger.info(f"[Scheduler] AI 仓位建议生成完成: {result}")
    except Exception as e:
        logger.error(f"[Scheduler] AI 仓位建议生成失败: {e}")


def job_generate_ai_morning_report(days: int = 1):
    """生成每日 AI 晨报（仅交易日执行）。"""
    from app.db.base import SessionLocal
    from app.services.ai_morning_report_service import generate_morning_report_sync
    from datetime import date

    logger.info("[Scheduler] 开始生成 AI 晨报")
    db = SessionLocal()
    try:
        report_date = date.today()
        report = generate_morning_report_sync(db, report_date)
        logger.info(f"[Scheduler] AI 晨报生成完成: {report.status}")
    except Exception as e:
        logger.error(f"[Scheduler] AI 晨报生成失败: {e}")
    finally:
        db.close()


# ============================================================
# 任务注册表：job_id -> 函数映射
# ============================================================

JOB_REGISTRY: dict[str, callable] = {
    # 原有任务
    "sync_daily_kline": job_sync_daily_kline,
    "sync_daily_basic": job_sync_daily_basic,
    "sync_sector_moneyflow": job_sync_sector_moneyflow,
    "sync_stock_moneyflow": job_sync_stock_moneyflow,
    "sync_index_daily": job_sync_index_daily,
    "sync_moneyflow_hsgt": job_sync_moneyflow_hsgt,
    "sync_stock_limit": job_sync_stock_limit,
    "sync_stock_basic": job_sync_stock_basic,
    "sync_all": job_sync_all,
    # 分析数据任务
    "sync_limit_data": job_sync_limit_data,
    "sync_concept_hot": job_sync_concept_hot,
    "sync_institution": job_sync_institution,
    "sync_research": job_sync_research,
    "sync_macro": job_sync_macro,
    # 分时K线
    "sync_intraday": job_sync_intraday,
    # ETF/可转债
    "sync_etf_cb": job_sync_etf_cb,
    # 会员任务
    "expire_memberships": job_expire_memberships,
    "grant_monthly_points": job_grant_monthly_points,
    "generate_daily_reviews": job_generate_daily_reviews,
    "generate_ai_position_advices": job_generate_ai_position_advices,
    "generate_ai_morning_report": job_generate_ai_morning_report,
}

JOB_DESCRIPTIONS: dict[str, str] = {
    # 盘后核心（16:00-17:30）
    "sync_daily_kline": "[盘后] 日K线行情",
    "sync_daily_basic": "[盘后] 日线因子（PE/PB/换手率/市值）",
    "sync_stock_moneyflow": "[盘后] 个股资金流向",
    "sync_sector_moneyflow": "[盘后] 板块资金流（行业+概念）",
    "sync_index_daily": "[盘后] 指数日线行情",
    "sync_moneyflow_hsgt": "[盘后] 沪深港通资金流向",
    "sync_stock_limit": "[盘后] 涨跌停数据",
    "sync_limit_data": "[盘后] 打板数据（涨跌停+连板天梯+THS榜单）",
    "sync_concept_hot": "[盘后] 题材热点（DC概念+THS热榜+DC热榜）",
    # 每日延后（18:00-20:00）
    "sync_etf_cb": "[每日] ETF+可转债（基础信息+份额+行情）",
    "sync_research": "[每日] 研报数据（券商金股+盈利预测）",
    "sync_stock_basic": "[每日] 股票基础信息+上市公司详情",
    # 每周（周六）
    "sync_institution": "[每周] 机构行为（北向持仓+股东人数+增减持+筹码+两融）",
    # 每月（1号）
    "sync_macro": "[每月] 宏观数据（指数估值+申万行业+CPI+PMI+LPR+社融+指数权重）",
    # 综合
    "sync_all": "[综合] 盘后全量同步（K线+资金+龙虎榜+板块+指数）",
    # 分时
    "sync_intraday": "[分时] 全A股1分钟K线（历史Tushare/当天akshare/16点后Tushare）",
    # 会员
    "expire_memberships": "[会员] 每日过期会员处理",
    "grant_monthly_points": "[会员] 每日月度积分发放",
    "generate_daily_reviews": "[AI] 每日自动生成全市场一句话复盘 + 会员深度复盘",
    "generate_ai_position_advices": "[AI] 每日自动生成会员仓位建议",
    "generate_ai_morning_report": "[AI] 每日自动生成市场晨报",
}


# ============================================================
# 数据库持久化 + 调度器管理
# ============================================================

def start_scheduler():
    """启动调度器并从数据库恢复任务配置。"""
    if not scheduler.running:
        scheduler.start()
        logger.info("[Scheduler] 调度器已启动")
    _restore_jobs_from_db()


def shutdown_scheduler():
    """关闭调度器。"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] 调度器已关闭")


def _restore_jobs_from_db():
    """从数据库加载已保存的任务配置，恢复到调度器。"""
    from app.db.base import SessionLocal
    from app.models.scheduler import SchedulerJob

    db = SessionLocal()
    try:
        configs = db.query(SchedulerJob).filter(SchedulerJob.enabled == 1).all()
        for cfg in configs:
            if cfg.job_id not in JOB_REGISTRY:
                logger.warning(f"[Scheduler] 跳过未知任务: {cfg.job_id}")
                continue
            try:
                _apply_job_config(cfg)
                logger.info(f"[Scheduler] 已恢复任务: {cfg.job_id} ({cfg.trigger_type})")
            except Exception as e:
                logger.error(f"[Scheduler] 恢复任务 {cfg.job_id} 失败: {e}")
        logger.info(f"[Scheduler] 从数据库恢复了 {len(configs)} 个任务配置")
    except Exception as e:
        logger.error(f"[Scheduler] 加载数据库任务配置失败: {e}")
    finally:
        db.close()


def _apply_job_config(cfg):
    """将数据库配置应用到调度器（带日志记录）。"""
    func = JOB_REGISTRY[cfg.job_id]
    job_id = cfg.job_id
    days = cfg.days or 1

    # 包装函数：调度器触发时自动记录日志
    def _logged_job(days=days):
        _log_execution(job_id, func, {"days": days})

    if cfg.trigger_type == "cron":
        trigger = CronTrigger(
            hour=cfg.cron_hour or 18,
            minute=cfg.cron_minute or 0,
            day_of_week=cfg.cron_day_of_week or "mon-fri",
        )
    elif cfg.trigger_type == "interval":
        hours = cfg.interval_hours or 0
        minutes = cfg.interval_minutes or 30
        trigger = IntervalTrigger(hours=hours, minutes=minutes)
    else:
        raise ValueError(f"未知触发类型: {cfg.trigger_type}")

    # 先移除已有的同ID任务
    existing = scheduler.get_job(cfg.job_id)
    if existing:
        scheduler.remove_job(cfg.job_id)

    scheduler.add_job(
        _logged_job,
        trigger=trigger,
        id=cfg.job_id,
        name=cfg.description or JOB_DESCRIPTIONS.get(cfg.job_id, cfg.job_id),
        kwargs={"days": days},
        replace_existing=True,
    )


def save_job_config(
    job_id: str,
    trigger_type: str = "cron",
    cron_hour: int = 18,
    cron_minute: int = 0,
    cron_day_of_week: str = "mon-fri",
    interval_hours: int = 0,
    interval_minutes: int = 30,
    days: int = 1,
    enabled: bool = True,
) -> dict:
    """保存/更新任务配置到数据库，并立即应用到调度器。

    Args:
        job_id: 任务标识
        trigger_type: 触发类型 cron/interval
        cron_hour: cron 小时
        cron_minute: cron 分钟
        cron_day_of_week: cron 星期
        interval_hours: 间隔小时
        interval_minutes: 间隔分钟
        days: 同步天数
        enabled: 是否启用

    Returns:
        保存后的任务信息
    """
    from app.db.base import SessionLocal
    from app.models.scheduler import SchedulerJob

    if job_id not in JOB_REGISTRY:
        raise ValueError(f"未知任务: {job_id}，可选: {list(JOB_REGISTRY.keys())}")

    db = SessionLocal()
    try:
        cfg = db.query(SchedulerJob).filter(SchedulerJob.job_id == job_id).first()
        if cfg is None:
            cfg = SchedulerJob(job_id=job_id)
            db.add(cfg)

        cfg.description = JOB_DESCRIPTIONS.get(job_id, job_id)
        cfg.trigger_type = trigger_type
        cfg.cron_hour = cron_hour
        cfg.cron_minute = cron_minute
        cfg.cron_day_of_week = cron_day_of_week
        cfg.interval_hours = interval_hours
        cfg.interval_minutes = interval_minutes
        cfg.days = days
        cfg.enabled = 1 if enabled else 0

        db.commit()
        db.refresh(cfg)

        # 应用到调度器
        if enabled:
            _apply_job_config(cfg)
        else:
            # 禁用则从调度器移除
            existing = scheduler.get_job(job_id)
            if existing:
                scheduler.remove_job(job_id)

        return _config_to_dict(cfg)
    finally:
        db.close()


def toggle_job(job_id: str, enabled: bool) -> dict | None:
    """启用/禁用任务。"""
    from app.db.base import SessionLocal
    from app.models.scheduler import SchedulerJob

    db = SessionLocal()
    try:
        cfg = db.query(SchedulerJob).filter(SchedulerJob.job_id == job_id).first()
        if cfg is None:
            return None

        cfg.enabled = 1 if enabled else 0
        db.commit()
        db.refresh(cfg)

        if enabled:
            _apply_job_config(cfg)
        else:
            existing = scheduler.get_job(job_id)
            if existing:
                scheduler.remove_job(job_id)

        return _config_to_dict(cfg)
    finally:
        db.close()


def get_all_job_configs() -> list[dict]:
    """获取数据库中所有任务配置（含运行状态）。"""
    from app.db.base import SessionLocal
    from app.models.scheduler import SchedulerJob

    db = SessionLocal()
    try:
        configs = db.query(SchedulerJob).order_by(SchedulerJob.id.asc()).all()
        result = []
        for cfg in configs:
            item = _config_to_dict(cfg)
            # 附加调度器运行时信息
            job = scheduler.get_job(cfg.job_id)
            if job:
                item["next_run_time"] = job.next_run_time.isoformat() if job.next_run_time else None
                item["running"] = True
            else:
                item["next_run_time"] = None
                item["running"] = False
            result.append(item)
        return result
    finally:
        db.close()


def get_available_jobs() -> list[dict]:
    """获取所有可用的任务类型（注册表）。"""
    return [
        {"job_id": k, "description": v}
        for k, v in JOB_DESCRIPTIONS.items()
    ]


def run_job_now(job_id: str, days: int = 1) -> bool:
    """立即执行某个任务（不影响调度），记录执行日志。"""
    if job_id not in JOB_REGISTRY:
        return False
    func = JOB_REGISTRY[job_id]
    t = threading.Thread(
        target=_log_execution,
        args=(job_id, func, {"days": days}),
        daemon=True,
    )
    t.start()
    return True


def _config_to_dict(cfg) -> dict:
    """将数据库配置转为字典。"""
    return {
        "id": cfg.id,
        "job_id": cfg.job_id,
        "description": cfg.description,
        "trigger_type": cfg.trigger_type,
        "cron_hour": cfg.cron_hour,
        "cron_minute": cfg.cron_minute,
        "cron_day_of_week": cfg.cron_day_of_week,
        "interval_hours": cfg.interval_hours,
        "interval_minutes": cfg.interval_minutes,
        "days": cfg.days,
        "enabled": cfg.enabled == 1,
        "created_at": cfg.created_at.strftime("%Y-%m-%d %H:%M:%S") if cfg.created_at else None,
        "updated_at": cfg.updated_at.strftime("%Y-%m-%d %H:%M:%S") if cfg.updated_at else None,
    }


def get_job_logs(job_id: str = None, status: str = None, page: int = 1, page_size: int = 30) -> dict:
    """获取任务执行日志（分页，支持 job_id 和 status 筛选）。"""
    from app.db.base import SessionLocal
    from app.models.scheduler_log import SchedulerLog

    db = SessionLocal()
    try:
        query = db.query(SchedulerLog)
        if job_id:
            query = query.filter(SchedulerLog.job_id == job_id)
        if status:
            query = query.filter(SchedulerLog.status == status)

        total = query.count()
        logs = (
            query.order_by(SchedulerLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            {
                "id": log.id,
                "job_id": log.job_id,
                "status": log.status,
                "message": log.message,
                "duration_seconds": log.duration_seconds,
                "started_at": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else None,
                "finished_at": log.finished_at.strftime("%Y-%m-%d %H:%M:%S") if log.finished_at else None,
            }
            for log in logs
        ]

        return {"list": items, "total": total, "page": page, "page_size": page_size}
    finally:
        db.close()
