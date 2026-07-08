from pydantic import BaseModel


class WeatherData(BaseModel):
    city: str
    temperature: float
    description: str
    updated_at: str
