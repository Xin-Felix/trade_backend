"""定时任务执行日志模型。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db.base import Base


class SchedulerLog(Base):
    """定时任务执行日志表"""

    __tablename__ = "scheduler_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(50),
        ForeignKey("scheduler_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="任务标识",
    )
    status = Column(String(20), nullable=False, comment="执行状态: success/failed/running")
    message = Column(Text, nullable=True, comment="执行结果/错误信息")
    duration_seconds = Column(Integer, nullable=True, comment="执行耗时(秒)")
    started_at = Column(DateTime, server_default=func.now(), nullable=False, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
