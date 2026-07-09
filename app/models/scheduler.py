"""定时任务配置模型。

将任务调度配置持久化到数据库，服务重启后自动恢复。
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class SchedulerJob(Base):
    """定时任务配置表"""

    __tablename__ = "scheduler_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(50), unique=True, nullable=False, comment="任务标识，如 sync_daily_kline")
    description = Column(String(200), nullable=True, comment="任务描述")

    # 触发方式: cron / interval
    trigger_type = Column(String(20), nullable=False, default="cron", comment="触发类型: cron/interval")

    # cron 参数
    cron_hour = Column(Integer, nullable=True, default=18, comment="cron 小时 (0-23)")
    cron_minute = Column(Integer, nullable=True, default=0, comment="cron 分钟 (0-59)")
    cron_day_of_week = Column(String(20), nullable=True, default="mon-fri", comment="cron 星期，如 mon-fri")

    # interval 参数
    interval_hours = Column(Integer, nullable=True, default=0, comment="间隔小时")
    interval_minutes = Column(Integer, nullable=True, default=30, comment="间隔分钟")

    # 任务参数
    days = Column(Integer, nullable=False, default=1, comment="同步天数")

    # 状态
    enabled = Column(Integer, nullable=False, default=1, comment="是否启用: 1=启用 0=禁用")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
