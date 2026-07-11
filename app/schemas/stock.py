from pydantic import BaseModel
from typing import Optional


class StockData(BaseModel):
    code: str
    name: str
    price: float
    change_percent: float
    pre_close: Optional[float] = None
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


class IntradayKlineData(BaseModel):
    """分时 K 线数据（分钟级）"""

    ts_code: str
    datetime: str
    period: str  # 1/5/15/30/60
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    amount: Optional[float] = None


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


class StockMoneyflowData(BaseModel):
    """个股资金流向数据"""

    ts_code: str
    trade_date: str
    buy_sm_amount: Optional[float] = None
    sell_sm_amount: Optional[float] = None
    buy_md_amount: Optional[float] = None
    sell_md_amount: Optional[float] = None
    buy_lg_amount: Optional[float] = None
    sell_lg_amount: Optional[float] = None
    buy_elg_amount: Optional[float] = None
    sell_elg_amount: Optional[float] = None
    net_mf_amount: Optional[float] = None


class MoneyflowHsgtData(BaseModel):
    """沪深港通资金流向数据"""

    trade_date: str
    ggt_ss: Optional[float] = None
    ggt_sz: Optional[float] = None
    hgt: Optional[float] = None
    sgt: Optional[float] = None
    north_money: Optional[float] = None
    south_money: Optional[float] = None


class IndexBasicData(BaseModel):
    """指数基础信息"""

    ts_code: str
    name: Optional[str] = None
    market: Optional[str] = None
    category: Optional[str] = None
    base_date: Optional[str] = None
    base_point: Optional[float] = None


class IndexDailyData(BaseModel):
    """指数日线数据"""

    ts_code: str
    trade_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None


class StockLimitData(BaseModel):
    """涨跌停数据"""

    trade_date: str
    ts_code: str
    up_limit: Optional[float] = None
    down_limit: Optional[float] = None


class TopListData(BaseModel):
    """龙虎榜每日明细"""

    trade_date: str
    ts_code: str
    name: Optional[str] = None
    close: Optional[float] = None
    pct_change: Optional[float] = None
    turnover_rate: Optional[float] = None
    amount: Optional[float] = None
    net_amount: Optional[float] = None
    net_rate: Optional[float] = None
    reason: Optional[str] = None


class TopListResponse(BaseModel):
    """龙虎榜分页响应"""

    items: list[TopListData]
    total: int
    limit: int
    offset: int


class LimitUpConceptTag(BaseModel):
    """涨停概念板块标签"""

    name: str
    count: Optional[int] = None
    cons_count: Optional[int] = None
    pct_change: Optional[float] = None
    rank: Optional[int] = None


class LimitUpStockItem(BaseModel):
    """涨停天梯个股"""

    ts_code: str
    name: Optional[str] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    first_time: Optional[str] = None
    last_time: Optional[str] = None
    open_times: Optional[int] = None
    concept_tags: list[str] = []


class LimitUpLadderGroup(BaseModel):
    """连板分组"""

    step: int
    label: str
    stocks: list[LimitUpStockItem]


class LimitUpLadderResponse(BaseModel):
    """涨停板天梯聚合响应"""

    trade_date: str
    concept_tags: list[LimitUpConceptTag]
    ladder: list[LimitUpLadderGroup]
    opened_limit: list[LimitUpStockItem]


class TopInstData(BaseModel):
    """龙虎榜机构明细"""

    trade_date: str
    ts_code: str
    exalter: Optional[str] = None
    buy: Optional[float] = None
    buy_rate: Optional[float] = None
    sell: Optional[float] = None
    sell_rate: Optional[float] = None
    net_buy: Optional[float] = None
    side: Optional[str] = None
    reason: Optional[str] = None


class ThsIndexData(BaseModel):
    """同花顺指数基础信息"""

    ts_code: str
    name: Optional[str] = None
    count: Optional[int] = None
    type: Optional[str] = None


class ThsDailyData(BaseModel):
    """同花顺指数日线"""

    ts_code: str
    trade_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    pct_change: Optional[float] = None
    vol: Optional[float] = None
    turnover_rate: Optional[float] = None


class ThsMemberData(BaseModel):
    """同花顺指数成分股"""

    ts_code: str
    con_code: str
    con_name: Optional[str] = None
