"""分时资金流向默认板块/概念配置模型。

后台管理通过此表配置 iOS「分时资金流向」页面默认勾选的板块或概念。
"""

from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from app.db.base import Base


class SectorDefaultConfig(Base):
    """分时资金流向默认配置表"""

    __tablename__ = "sector_default_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_type = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="板块类型: concept=概念, industry=行业",
    )
    sector_ids = Column(
        JSON,
        nullable=False,
        default=list,
        comment="默认勾选的板块/概念ID列表，按展示顺序排列",
    )
    is_enabled = Column(
        Integer, nullable=False, default=1, comment="是否启用: 1=是 0=否"
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
