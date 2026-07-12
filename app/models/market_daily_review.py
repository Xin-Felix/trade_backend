"""全市场每日一句话复盘记录模型。

系统每日收盘后生成一份全市场通用的极简复盘，供免费用户查看。
"""

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, UniqueConstraint, func

from app.db.base import Base
from app.models.mixins import SoftDeleteMixin


class MarketDailyReview(SoftDeleteMixin, Base):
    """全市场每日一句话复盘记录表"""

    __tablename__ = "market_daily_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False, unique=True, comment="复盘日期")
    level = Column(
        String(20),
        nullable=False,
        server_default="brief",
        comment="复盘层级，固定为 brief",
    )
    content = Column(Text, nullable=True, comment="AI 生成的一句话复盘内容")
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
        comment="状态: pending / running / success / failed",
    )
    error_message = Column(Text, nullable=True, comment="失败原因")
    prompt_version = Column(String(20), nullable=True, comment="生成时使用的 Prompt 版本号")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
