"""AI 晨报记录模型。

系统每日开盘前自动生成一份基于市场整体数据的 AI 晨报，每天仅一条记录。
"""

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, func

from app.db.base import Base


class AiMorningReport(Base):
    """AI 晨报记录表"""

    __tablename__ = "ai_morning_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="报告日期（当天日期）",
    )
    content = Column(Text, nullable=True, comment="AI 生成的晨报内容（Markdown）")
    summary = Column(Text, nullable=True, comment="AI 生成的晨报摘要（1-2句话，100字以内）")
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
        comment="状态: pending / running / success / failed",
    )
    error_message = Column(Text, nullable=True, comment="失败原因")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
