"""每日复盘记录模型。

系统每日为生效会员自动生成基于其自选股的 AI 复盘报告。
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db.base import Base


class DailyReview(Base):
    """每日复盘记录表"""

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
    content = Column(Text, nullable=True, comment="AI 生成的复盘内容（Markdown）")
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
        UniqueConstraint("user_id", "report_date", name="uix_daily_review_user_date"),
    )
