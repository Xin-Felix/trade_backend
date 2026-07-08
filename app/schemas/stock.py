from pydantic import BaseModel
from typing import Optional


class StockData(BaseModel):
    code: str
    name: str
    price: float
    change_percent: float
    updated_at: str


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
