"""H5 页面管理模型。

用于存储可在 App 内通过 WebView 动态加载的页面内容，支持 Markdown 和 HTML 两种格式。
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class H5Page(Base):
    """H5 页面表"""

    __tablename__ = "h5_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, comment="页面标识，如 help-feedback")
    title = Column(String(200), nullable=False, comment="页面标题")
    content_type = Column(
        String(20),
        nullable=False,
        default="markdown",
        comment="内容类型: markdown / html",
    )
    content = Column(Text, nullable=False, comment="原始内容（Markdown 或 HTML）")
    is_published = Column(
        Integer, nullable=False, default=0, comment="是否发布: 1=是 0=否"
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
