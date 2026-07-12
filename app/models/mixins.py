"""共享模型 mixin。"""

from sqlalchemy import Column, Integer


class SoftDeleteMixin:
    """软删除 mixin：添加 is_deleted 标记字段。"""

    is_deleted = Column(
        Integer,
        nullable=False,
        server_default="0",
        index=True,
        comment="是否已删除: 0=否 1=是",
    )
