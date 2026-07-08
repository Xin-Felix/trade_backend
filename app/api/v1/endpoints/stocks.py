from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.stock import DailyBasicData, KlineData, StockData
from app.schemas.user import User
from app.services import stock_service

router = APIRouter()


@router.get("/quote/{code}")
async def get_stock_quote(code: str, user: User = Depends(get_current_user)) -> StockData:
    return stock_service.get_stock_quote(code)


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
