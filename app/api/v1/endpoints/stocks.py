from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.stock import (
    DailyBasicData,
    IndexData,
    KlineData,
    SectorMoneyflowRankResponse,
    SectorMoneyflowTrendResponse,
    StockBasicInfo,
    StockData,
    StockSearchResult,
)
from app.schemas.user import User
from app.services import stock_service

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


@router.get("/daily-basic/{code}")
async def get_daily_basic(
    code: str,
    limit: int = Query(30, ge=1, le=500),
    user: User = Depends(get_current_user),
) -> list[DailyBasicData]:
    """获取股票日线因子数据（PE/PB/换手率等）。"""
    return stock_service.get_daily_basic(code, limit=limit)


@router.get("/watchlist")
async def get_watchlist(user: User = Depends(get_current_user)) -> list[StockData]:
    return stock_service.get_user_watchlist()


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
