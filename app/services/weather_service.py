from datetime import datetime

import httpx

from app.schemas.weather import WeatherData


async def fetch_beijing_weather() -> WeatherData:
    """代理 Open-Meteo 北京天气。"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=39.9042&longitude=116.4074&current_weather=true"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()

    current = data["current_weather"]
    weather_code = current["weathercode"]

    descriptions = {
        0: "晴天",
        1: "多云",
        2: "多云",
        3: "多云",
        45: "雾",
        48: "雾",
        51: "小雨",
        53: "小雨",
        55: "中雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        95: "雷暴",
        96: "雷暴",
        99: "雷暴",
    }

    return WeatherData(
        city="北京",
        temperature=current["temperature"],
        description=descriptions.get(weather_code, "未知"),
        updated_at=datetime.now().isoformat(),
    )
