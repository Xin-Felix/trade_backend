from fastapi import APIRouter

from app.api.v1.endpoints import auth, stocks, weather

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(weather.router, prefix="/weather", tags=["天气"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["股票"])
