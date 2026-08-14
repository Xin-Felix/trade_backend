"""定时任务初始配置种子。

启动时将所有预定义任务写入 scheduler_jobs 表（按 job_id 检查，已存在则跳过）。
管理员可以通过后台页面修改每个任务的触发时间和启用状态。

任务频率分层：
- 盘后核心（交易日 16:00-17:30）：行情、资金流、涨跌停、龙虎榜 — 收盘后第一时间需要
- 每日延后（交易日 18:00-20:00）：板块热点、筹码、ETF/可转债、研报 — 日更但不紧急
- 每周（周六）：机构行为（北向/股东/增减持）— 数据有延迟或低频发布
- 每月（1号）：宏观数据（CPI/PMI/社融/LPR/指数权重）— 月度发布
"""

from sqlalchemy.orm import Session

from app.models.scheduler import SchedulerJob


_SEED_JOBS = [
    # ====================================================================
    # 一、盘后核心（交易日 16:00-17:30，收盘后尽快刷新）
    # 这些数据投资者盘后第一时间需要看到
    # ====================================================================
    {
        "job_id": "sync_daily_kline",
        "description": "日K线行情",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 5,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_daily_basic",
        "description": "日线因子（PE/PB/换手率/市值）",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 15,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_stock_moneyflow",
        "description": "个股资金流向",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 25,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_sector_moneyflow",
        "description": "板块资金流（行业+概念）",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 35,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_index_daily",
        "description": "指数日线行情",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 45,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_moneyflow_hsgt",
        "description": "沪深港通资金流向",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 55,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_index_global",
        "description": "全球指数日线行情",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 50,
        "cron_day_of_week": "mon-fri",
        "days": 5,
        "enabled": 1,
    },
    {
        "job_id": "sync_stock_limit",
        "description": "涨跌停数据",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 5,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_limit_data",
        "description": "打板数据（涨跌停明细+连板天梯+THS榜单）",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 15,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_concept_hot",
        "description": "题材热点（DC概念+THS热榜+DC热榜）",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 25,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_top_list",
        "description": "龙虎榜（每日明细+机构明细）",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 35,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_ths_daily",
        "description": "同花顺板块行情",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 45,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },

    # ====================================================================
    # 二、每日延后（交易日 18:00-20:00，数据日更但不紧急）
    # ====================================================================
    {
        "job_id": "sync_etf_cb",
        "description": "ETF+可转债（基础信息+份额+行情）",
        "trigger_type": "cron",
        "cron_hour": 18,
        "cron_minute": 0,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_research",
        "description": "研报数据（券商金股+盈利预测）",
        "trigger_type": "cron",
        "cron_hour": 18,
        "cron_minute": 20,
        "cron_day_of_week": "mon-fri",
        "days": 3,
        "enabled": 1,
    },

    # ====================================================================
    # 二点五、每日凌晨（低频静态数据，全天只需刷新一次）
    # ====================================================================
    {
        "job_id": "sync_stock_basic",
        "description": "股票基础信息+上市公司详情（行业/地区/公司简介等）",
        "trigger_type": "cron",
        "cron_hour": 2,
        "cron_minute": 30,
        "cron_day_of_week": "mon-sun",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_index_basic",
        "description": "指数基础信息",
        "trigger_type": "cron",
        "cron_hour": 2,
        "cron_minute": 40,
        "cron_day_of_week": "mon-sun",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_ths_index",
        "description": "同花顺指数列表+成分股",
        "trigger_type": "cron",
        "cron_hour": 3,
        "cron_minute": 0,
        "cron_day_of_week": "sat",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "sync_concept",
        "description": "概念板块成分股映射（全量同步）",
        "trigger_type": "cron",
        "cron_hour": 4,
        "cron_minute": 0,
        "cron_day_of_week": "sat",
        "days": 1,
        "enabled": 1,
    },

    # ====================================================================
    # 三、每周（周六 10:00，数据有延迟或低频发布）
    # ====================================================================
    {
        "job_id": "sync_institution",
        "description": "机构行为（北向持仓+股东人数+增减持+筹码+两融）",
        "trigger_type": "cron",
        "cron_hour": 10,
        "cron_minute": 0,
        "cron_day_of_week": "sat",
        "days": 7,
        "enabled": 1,
    },

    # ====================================================================
    # 四、每月（每月1号 8:00，月度发布的宏观/权重数据）
    # ====================================================================
    {
        "job_id": "sync_macro",
        "description": "宏观数据（指数估值+申万行业+CPI+PMI+LPR+社融+指数权重）",
        "trigger_type": "cron",
        "cron_hour": 8,
        "cron_minute": 0,
        "cron_day_of_week": "mon-sun",  # 每月1号不一定是工作日
        "days": 1,
        "enabled": 1,
    },

    {
        "job_id": "sync_intraday",
        "description": "全A股1分钟K线（最近5个交易日）",
        "trigger_type": "cron",
        "cron_hour": 16,
        "cron_minute": 30,
        "cron_day_of_week": "mon-fri",
        "days": 5,
        "enabled": 1,
    },

    # ====================================================================
    # 五、综合任务（默认禁用，手动触发或替代单项任务）
    # ====================================================================
    {
        "job_id": "sync_all",
        "description": "综合同步（包含盘后核心全部+龙虎榜+同花顺）",
        "trigger_type": "cron",
        "cron_hour": 19,
        "cron_minute": 0,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 0,  # 默认禁用，避免和单项任务重复
    },

    # ====================================================================
    # 六、会员任务（每日 00:05 / 00:10）
    # ====================================================================
    {
        "job_id": "expire_memberships",
        "description": "会员过期处理",
        "trigger_type": "cron",
        "cron_hour": 0,
        "cron_minute": 5,
        "cron_day_of_week": "mon-sun",
        "days": 1,
        "enabled": 1,
    },
    {
        "job_id": "grant_monthly_points",
        "description": "会员月度积分发放",
        "trigger_type": "cron",
        "cron_hour": 0,
        "cron_minute": 10,
        "cron_day_of_week": "mon-sun",
        "days": 1,
        "enabled": 1,
    },
    # AI 内容任务已移除

    # ====================================================================
    # 七、市场拥挤度（盘后 17:30，依赖日K和日线因子同步完成）
    # ====================================================================
    {
        "job_id": "mc_pipeline",
        "description": "市场拥挤度管道（汇总指标+拥挤度预跑+期权）",
        "trigger_type": "cron",
        "cron_hour": 17,
        "cron_minute": 50,
        "cron_day_of_week": "mon-fri",
        "days": 1,
        "enabled": 1,
    },
]


def seed_scheduler_jobs(db: Session) -> None:
    """将预定义任务配置写入数据库（已存在则跳过）。"""
    for job_data in _SEED_JOBS:
        existing = db.query(SchedulerJob).filter(
            SchedulerJob.job_id == job_data["job_id"]
        ).first()
        if existing:
            continue

        # 补充默认值
        job_data.setdefault("interval_hours", 0)
        job_data.setdefault("interval_minutes", 0)
        job = SchedulerJob(**job_data)
        db.add(job)

    db.commit()
