from fastapi import APIRouter

from app.schemas.weather import WeatherData
from app.services import weather_service

router = APIRouter()


@router.get("/beijing", response_model=WeatherData)
async def get_beijing_weather():
    return await weather_service.fetch_beijing_weather()
