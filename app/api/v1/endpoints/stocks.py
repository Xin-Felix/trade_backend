from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.stock import (
    DailyBasicData,
    IndexDailyData,
    IndexData,
    IntradayKlineData,
    KlineData,
    MoneyflowHsgtData,
    SectorMoneyflowRankResponse,
    SectorMoneyflowTrendResponse,
    StockBasicInfo,
    StockData,
    StockLimitData,
    StockMoneyflowData,
    StockSearchResult,
    ThsDailyData,
    ThsIndexData,
    ThsMemberData,
    TopInstData,
    TopListData,
)
from app.schemas.user import User
from app.schemas.watchlist import WatchlistAddRequest, WatchlistItem, WatchlistResponse
from app.services import stock_service, watchlist_service

router = APIRouter()


@router.get("/quote/{code}")
async def get_stock_quote(code: str, user: User = Depends(get_current_user)) -> StockData:
    return stock_service.get_stock_quote(code)


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="搜索关键词：股票代码、名称或拼音缩写"),
    limit: int = Query(10, ge=1, le=50, description="返回条数"),
    user: User = Depends(get_current_user),
) -> list[StockSearchResult]:
    """搜索股票，支持代码、名称、拼音缩写。"""
    return stock_service.search_stocks(q, limit=limit)


@router.get("/basics")
async def get_stock_basics(
    user: User = Depends(get_current_user),
) -> list[StockBasicInfo]:
    """获取全部股票基础信息，供 iOS 端本地缓存和搜索。"""
    return stock_service.get_stock_basics()


@router.get("/indices")
async def get_indices(user: User = Depends(get_current_user)) -> list[IndexData]:
    """获取主要大盘指数最新数据（上证、深证成指、创业板指）。"""
    return stock_service.get_indices()


@router.get("/klines/{code}")
async def get_klines(
    code: str,
    period: str = Query("D", pattern="^(D|W|M|Y)$"),
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[KlineData]:
    """
    获取股票 K 线数据。

    - period: D=日线, W=周线, M=月线, Y=年线
    - limit: 返回条数，默认 30，最大 500
    """
    return stock_service.get_klines(code, period=period, limit=limit)


@router.get("/intraday/{code}")
async def get_intraday_klines(
    code: str,
    period: str = Query("1", pattern="^(1|5|15|30|60)$"),
    limit: int = Query(240, ge=1, le=1000),
    user: User = Depends(get_current_user),
) -> list[IntradayKlineData]:
    """
    获取股票实时分时 K 线数据（akshare 实时拉取，缓存 Redis）。

    - period: 1/5/15/30/60 分钟
    - limit: 返回条数，默认 240，最大 1000
    """
    return stock_service.get_intraday_klines(code, period=period, limit=limit)


@router.get("/daily-basic/{code}")
async def get_daily_basic(
    code: str,
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[DailyBasicData]:
    """获取股票日线因子数据（PE/PB/换手率等）。"""
    return stock_service.get_daily_basic(code, limit=limit)


@router.get("/watchlist")
async def get_watchlist(user: User = Depends(get_current_user)) -> WatchlistResponse:
    """获取用户自选股列表，按加入时间排序。"""
    items = watchlist_service.get_watchlist(user.id)
    return WatchlistResponse(items=items, total=len(items))


@router.post("/watchlist")
async def add_watchlist(
    body: WatchlistAddRequest,
    user: User = Depends(get_current_user),
) -> WatchlistItem:
    """添加自选股。"""
    return watchlist_service.add_to_watchlist(user.id, body.code, body.name)


@router.delete("/watchlist/{code}")
async def remove_watchlist(
    code: str,
    user: User = Depends(get_current_user),
) -> dict:
    """删除自选股。"""
    removed = watchlist_service.remove_from_watchlist(user.id, code)
    return {"success": removed}


@router.get("/sector-moneyflow")
async def get_sector_moneyflow(
    sector_type: str = Query("industry", pattern="^(industry|concept)$"),
    trade_date: str | None = Query(None, description="交易日期 YYYYMMDD，默认最新"),
    sort_by: str = Query("net_amount", pattern="^(net_amount|pct_change|net_amount_asc)$"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> SectorMoneyflowRankResponse:
    """获取板块资金流排行（行业/概念）。"""
    result = stock_service.get_sector_moneyflow_rank(
        sector_type=sector_type,
        trade_date=trade_date,
        sort_by=sort_by,
        limit=limit,
    )
    return SectorMoneyflowRankResponse(**result)


@router.get("/sector-moneyflow/trend")
async def get_sector_moneyflow_trend(
    sector_type: str = Query("industry", pattern="^(industry|concept)$"),
    start_date: str = Query(..., min_length=8, max_length=8, description="开始日期 YYYYMMDD"),
    end_date: str = Query(..., min_length=8, max_length=8, description="结束日期 YYYYMMDD"),
    top_n: int = Query(30, ge=1, le=100, description="返回累计净流入前 N 的板块"),
    user: User = Depends(get_current_user),
) -> SectorMoneyflowTrendResponse:
    """获取板块资金流时间段趋势（动态折线图）。"""
    result = stock_service.get_sector_moneyflow_trend(
        sector_type=sector_type,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
    )
    return SectorMoneyflowTrendResponse(**result)


@router.get("/moneyflow/{code}")
async def get_stock_moneyflow(
    code: str,
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[StockMoneyflowData]:
    """获取个股资金流向（小单/中单/大单/特大单）。"""
    return stock_service.get_stock_moneyflow(code, limit=limit)


@router.get("/moneyflow-hsgt")
async def get_moneyflow_hsgt(
    start_date: str | None = Query(None, min_length=8, max_length=8, description="开始日期 YYYYMMDD"),
    end_date: str | None = Query(None, min_length=8, max_length=8, description="结束日期 YYYYMMDD"),
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[MoneyflowHsgtData]:
    """获取沪深港通资金流向（北向/南向资金）。"""
    return stock_service.get_moneyflow_hsgt(start_date=start_date, end_date=end_date, limit=limit)


@router.get("/index-daily/{code}")
async def get_index_daily(
    code: str,
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[IndexDailyData]:
    """获取指数日线行情（如 000001.SH）。"""
    return stock_service.get_index_daily(code, limit=limit)


@router.get("/stock-limit")
async def get_stock_limit(
    trade_date: str | None = Query(None, min_length=8, max_length=8, description="交易日期 YYYYMMDD，默认最新"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[StockLimitData]:
    """获取涨跌停股票列表。"""
    return stock_service.get_stock_limit(trade_date=trade_date, limit=limit)


@router.get("/top-list")
async def get_top_list(
    trade_date: str | None = Query(None, min_length=8, max_length=8, description="交易日期 YYYYMMDD，默认最新"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[TopListData]:
    """获取龙虎榜每日明细。"""
    return stock_service.get_top_list(trade_date=trade_date, limit=limit)


@router.get("/top-inst")
async def get_top_inst(
    trade_date: str | None = Query(None, min_length=8, max_length=8, description="交易日期 YYYYMMDD"),
    code: str | None = Query(None, description="股票代码"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[TopInstData]:
    """获取龙虎榜机构明细。"""
    return stock_service.get_top_inst(trade_date=trade_date, ts_code=code, limit=limit)


@router.get("/ths-index")
async def get_ths_index(
    limit: int = Query(1000, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[ThsIndexData]:
    """获取同花顺指数列表（行业/概念）。"""
    return stock_service.get_ths_index_list(limit=limit)


@router.get("/ths-daily/{code}")
async def get_ths_daily(
    code: str,
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[ThsDailyData]:
    """获取同花顺指数日线行情。"""
    return stock_service.get_ths_daily(code, limit=limit)


@router.get("/ths-member/{code}")
async def get_ths_member(
    code: str,
    limit: int = Query(1000, ge=1, le=5000),
    user: User = Depends(get_current_user),
) -> list[ThsMemberData]:
    """获取同花顺指数成分股。"""
    return stock_service.get_ths_member(code, limit=limit)
