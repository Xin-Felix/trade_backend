"""数据源注册表模型。

记录所有接入数据源（Tushare / AKShare / 自定义）的接口元信息，
方便后台统一管理、文档查阅和权限检测。
"""

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func

from app.db.base import Base


class DataSource(Base):
    """数据源接口注册表

    provider 字段区分不同数据源提供商：
    - tushare: Tushare Pro 数据接口
    - akshare: AKShare 开源数据接口
    - custom: 自建/第三方自定义接口
    """

    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False, default="tushare", comment="数据源提供商: tushare/akshare/custom")
    api_name = Column(String(80), nullable=False, comment="接口名，如 daily / stock_zh_a_hist")
    title = Column(String(100), nullable=False, comment="中文名称，如 历史日线")
    category = Column(String(50), nullable=False, comment="分类，如 股票数据,行情数据")
    description = Column(Text, nullable=True, comment="接口描述")
    proxy_path = Column(String(100), nullable=True, comment="本地代理路径，如 /api/v1/ts/daily")
    doc_url = Column(String(300), nullable=True, comment="在线文档链接")
    has_local_table = Column(Integer, nullable=False, default=0, comment="是否有本地存储表: 1=有 0=仅代理")
    local_table_name = Column(String(50), nullable=True, comment="本地存储表名，如 stock_daily")
    enabled = Column(Integer, nullable=False, default=1, comment="是否启用: 1=启用 0=禁用")
    has_permission = Column(Integer, nullable=False, default=-1, comment="是否有调用权限: 1=有 0=无 -1=未检测")
    permission_msg = Column(String(500), nullable=True, comment="权限检测返回的消息")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        # 同一 provider 下 api_name 唯一
        Index("uix_provider_api_name", "provider", "api_name", unique=True),
    )
