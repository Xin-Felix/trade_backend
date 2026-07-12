from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    ai,
    analytics,
    auth,
    daily_quote,
    data_browser,
    datasource,
    global_market,
    h5_page,
    limit_up_admin,
    membership,
    membership_admin,
    points,
    points_admin,
    scheduler,
    stocks,
    sync,
    upload,
    weather,
)
from app.api.v1.endpoints.tushare import router as tushare_router

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(upload.router, prefix="/upload", tags=["文件上传"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI中心"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["数据加工"])
api_router.include_router(global_market.router, prefix="/global-market", tags=["国际市场"])
api_router.include_router(admin.router, prefix="/admin", tags=["后台管理"])
api_router.include_router(limit_up_admin.router, prefix="/admin/limit-up-ladder", tags=["涨停板天梯管理"])
api_router.include_router(points_admin.router, prefix="/admin/points", tags=["积分管理"])
api_router.include_router(membership_admin.router, prefix="/admin/membership", tags=["会员管理"])
api_router.include_router(membership.router, prefix="/membership", tags=["会员"])
api_router.include_router(points.router, prefix="/points", tags=["积分"])
api_router.include_router(h5_page.router, prefix="/h5-pages", tags=["H5页面管理"])
api_router.include_router(daily_quote.router, prefix="/daily-quotes", tags=["每日一言"])
api_router.include_router(data_browser.router, prefix="/data", tags=["数据浏览"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["调度管理"])
api_router.include_router(datasource.router, prefix="/datasource", tags=["数据源管理"])
api_router.include_router(weather.router, prefix="/weather", tags=["天气"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["股票"])
api_router.include_router(sync.router, prefix="/sync", tags=["数据同步"])
api_router.include_router(tushare_router, prefix="/ts", tags=["Tushare代理"])
