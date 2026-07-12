"""每日复盘记录模型。

系统每日为生效会员自动生成基于其自选股的 AI 复盘报告。
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from app.db.base import Base
from app.models.mixins import SoftDeleteMixin


class DailyReview(SoftDeleteMixin, Base):
    """每日复盘记录表（个人复盘：标准/深度）"""

    __tablename__ = "daily_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户 ID",
    )
    report_date = Column(Date, nullable=False, comment="复盘日期")
    level = Column(
        String(20),
        nullable=False,
        server_default="standard",
        comment="复盘层级: standard / deep",
    )
    content = Column(Text, nullable=True, comment="AI 生成的复盘内容（Markdown）")
    summary = Column(Text, nullable=True, comment="AI 生成的复盘摘要（1-2句话，100字以内）")
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

    __table_args__ = (
        Index(
            "uix_daily_review_user_date_level_active",
            "user_id",
            "report_date",
            "level",
            unique=True,
            postgresql_where="is_deleted = 0",
        ),
    )
