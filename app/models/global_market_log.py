"""国际市场数据日志模型。"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class GlobalMarketLog(Base):
    """全球市场数据获取日志"""

    __tablename__ = "global_market_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, comment="数据来源: akshare/tushare")
    status = Column(String(20), nullable=False, comment="状态: success/failed")
    message = Column(Text, nullable=True, comment="结果描述或错误信息")
    data_count = Column(Integer, nullable=True, comment="返回数据条数")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="记录时间")
