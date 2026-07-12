"""AI 仓位建议记录模型。

系统每日为生效会员自动生成基于其持仓的 AI 仓位建议报告。
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


class AiPositionAdvice(SoftDeleteMixin, Base):
    """AI 仓位建议记录表"""

    __tablename__ = "ai_position_advices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户 ID",
    )
    report_date = Column(Date, nullable=False, comment="报告日期")
    content = Column(Text, nullable=True, comment="AI 生成的仓位建议内容（Markdown）")
    summary = Column(Text, nullable=True, comment="AI 生成的仓位建议摘要（1-2句话，100字以内）")
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
        comment="状态: pending / running / success / failed",
    )
    error_message = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uix_ai_position_advice_user_date_active",
            "user_id",
            "report_date",
            unique=True,
            postgresql_where="is_deleted = 0",
        ),
    )
