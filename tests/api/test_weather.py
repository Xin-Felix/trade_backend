from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


@patch("app.services.weather_service.httpx.AsyncClient")
def test_get_beijing_weather(mock_client_class, client: TestClient):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "current_weather": {
            "temperature": 25.5,
            "weathercode": 0,
        }
    }

    mock_client = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_response

    response = client.get("/api/v1/weather/beijing")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "北京"
    assert data["temperature"] == 25.5
    assert data["description"] == "晴天"
    assert "updated_at" in data
