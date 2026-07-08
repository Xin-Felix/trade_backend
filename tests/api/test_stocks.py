from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login/email",
        json={"email": "1538933906@qq.com", "password": "123456"},
    )
    return response.json()["access_token"]


def test_get_stock_quote_unauthorized(client: TestClient):
    response = client.get("/api/v1/stocks/quote/000001")
    assert response.status_code == 401


def test_get_stock_quote_authorized(client: TestClient):
    token = _get_token(client)
    response = client.get(
        "/api/v1/stocks/quote/000001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "000001"
    assert "price" in data


def test_get_klines_authorized(client: TestClient):
    token = _get_token(client)
    response = client.get(
        "/api/v1/stocks/klines/000001?period=D&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_daily_basic_authorized(client: TestClient):
    token = _get_token(client)
    response = client.get(
        "/api/v1/stocks/daily-basic/000001?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_watchlist(client: TestClient):
    token = _get_token(client)
    response = client.get(
        "/api/v1/stocks/watchlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
