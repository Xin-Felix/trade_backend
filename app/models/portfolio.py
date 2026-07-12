from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, func

from app.db.base import Base
from app.models.mixins import SoftDeleteMixin


class Portfolio(SoftDeleteMixin, Base):
    """用户持仓表：标记用户当前持有的股票，用于复盘分析。"""

    __tablename__ = "portfolio"
    __table_args__ = (
        Index(
            "uq_portfolio_user_code_active",
            "user_id",
            "ts_code",
            unique=True,
            postgresql_where="is_deleted = 0",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(36),
        ForeignKey("users.public_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户 public_id",
    )
    ts_code = Column(String(20), nullable=False, comment="Tushare 标准代码，如 000001.SZ")
    code = Column(String(20), nullable=False, comment="原始股票代码，如 000001")
    name = Column(String(100), nullable=False, comment="股票名称")
    cost_price = Column(Numeric(12, 4), nullable=True, comment="成本价")
    quantity = Column(Numeric(15, 4), nullable=True, comment="持仓数量（股数）")
    is_margin = Column(Boolean, nullable=True, server_default="false", comment="是否融资持仓")
    note = Column(String(500), nullable=True, comment="持仓备注")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="标记时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
