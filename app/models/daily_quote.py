"""每日一言模型。

用于存储首页每日一言语录池，支持按日期自动轮播和指定日期覆盖。
"""

from sqlalchemy import Column, Date, DateTime, Integer, String, func

from app.db.base import Base


class DailyQuote(Base):
    """每日一言表"""

    __tablename__ = "daily_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String(500), nullable=False, comment="语录内容")
    author = Column(String(100), nullable=True, comment="作者或来源")
    is_published = Column(
        Integer, nullable=False, default=1, comment="是否上架: 1=是 0=否"
    )
    display_date = Column(Date, nullable=True, comment="指定展示日期，为空则参与自动轮播")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
