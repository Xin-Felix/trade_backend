from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func

from app.db.base import Base


class Watchlist(Base):
    """用户自选股表"""

    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "ts_code", name="uq_watchlist_user_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True, comment="用户 public_id")
    ts_code = Column(String(20), nullable=False, comment="Tushare 标准代码，如 000001.SZ")
    code = Column(String(20), nullable=False, comment="原始股票代码，如 000001")
    name = Column(String(100), nullable=False, comment="股票名称")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="加入时间")
