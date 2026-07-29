"""市场温度（Market Pulse）模型。

每个交易日存储一条市场温度快照：分数、等级、AI总结、关键指标、热点关键词。
"""

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, Text, func

from app.db.base import Base


class MarketPulse(Base):
    """每日市场温度快照"""

    __tablename__ = "market_pulse"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, unique=True, nullable=False, comment="交易日期")

    # 温度分数与等级
    score = Column(Integer, nullable=False, comment="市场温度 0~100")
    level = Column(String(10), nullable=False, comment="等级：极弱/偏弱/中性/偏强/高潮")

    # AI 生成内容
    summary = Column(Text, nullable=True, comment="AI 一句话总结（2-3行）")
    keywords = Column(String(500), nullable=True, comment="今日热点关键词，逗号分隔")

    # 关键指标原始值（供前端展示"情绪依据"）
    up_count = Column(Integer, nullable=True, comment="上涨家数")
    down_count = Column(Integer, nullable=True, comment="下跌家数")
    amount = Column(Numeric(20, 4), nullable=True, comment="成交额（亿元）")
    amount_change_pct = Column(Numeric(10, 4), nullable=True, comment="成交额较昨日变化%")
    north_money = Column(Numeric(20, 4), nullable=True, comment="北向资金净流入（亿元）")
    limit_up_count = Column(Integer, nullable=True, comment="涨停家数")
    limit_down_count = Column(Integer, nullable=True, comment="跌停家数")
    open_limit_count = Column(Integer, nullable=True, comment="炸板家数")
    max_continuous_board = Column(Integer, nullable=True, comment="最高连板数")

    # 状态
    status = Column(String(20), nullable=False, default="success", comment="pending/success/failed")
    error_message = Column(Text, nullable=True, comment="失败原因")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
