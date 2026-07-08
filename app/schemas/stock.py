from pydantic import BaseModel
from typing import Optional


class StockData(BaseModel):
    code: str
    name: str
    price: float
    change_percent: float
    updated_at: str


class StockSearchResult(BaseModel):
    """股票搜索结果"""

    code: str
    name: str


class StockBasicInfo(BaseModel):
    """股票基础信息（用于本地缓存和搜索）"""

    code: str
    name: str
    cnspell: Optional[str] = None


class IndexData(BaseModel):
    """大盘指数数据"""

    name: str
    value: float
    change: float
    ts_code: str


class KlineData(BaseModel):
    ts_code: str
    trade_date: str
    period: str  # D=日, W=周, M=月, Y=年
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    amount: Optional[float]


class DailyBasicData(BaseModel):
    """日线因子数据"""

    ts_code: str
    trade_date: str
    close: Optional[float]
    turnover_rate: Optional[float]
    turnover_rate_f: Optional[float]
    volume_ratio: Optional[float]
    pe: Optional[float]
    pe_ttm: Optional[float]
    pb: Optional[float]
    ps: Optional[float]
    ps_ttm: Optional[float]
    dv_ratio: Optional[float]
    dv_ttm: Optional[float]
    total_share: Optional[float]
    float_share: Optional[float]
    free_share: Optional[float]
    total_mv: Optional[float]
    circ_mv: Optional[float]


class StockSyncStatus(BaseModel):
    """数据同步状态"""

    status: str
    detail: Optional[str] = None


class SectorMoneyflowData(BaseModel):
    """板块资金流数据"""

    ts_code: str
    trade_date: str
    name: Optional[str] = None
    lead_stock: Optional[str] = None
    close_price: Optional[float] = None
    pct_change: Optional[float] = None
    company_num: Optional[int] = None
    pct_change_stock: Optional[float] = None
    net_buy_amount: Optional[float] = None
    net_sell_amount: Optional[float] = None
    net_amount: Optional[float] = None


class SectorMoneyflowRankResponse(BaseModel):
    """板块资金流排行响应"""

    sectors: list[SectorMoneyflowData]
    trade_date: str
    sector_type: str  # industry / concept


class SectorMoneyflowTrendPoint(BaseModel):
    """板块资金流趋势单天数据点"""

    trade_date: str
    net_amount: float
    pct_change: Optional[float] = None


class SectorMoneyflowSeries(BaseModel):
    """板块资金流趋势单条序列"""

    ts_code: str
    name: Optional[str] = None
    values: list[SectorMoneyflowTrendPoint]


class SectorMoneyflowTrendResponse(BaseModel):
    """板块资金流动态趋势响应"""

    sector_type: str  # industry / concept
    start_date: str
    end_date: str
    dates: list[str]
    series: list[SectorMoneyflowSeries]
