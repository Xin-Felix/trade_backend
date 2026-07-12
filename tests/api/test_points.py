"""积分系统 API 测试。"""

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login/email",
        json={"email": "1538933906@qq.com", "password": "123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestPointsAPI:
    def test_get_balance(self, client: TestClient):
        token = _get_token(client)
        response = client.get(
            "/api/v1/points/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "balance" in data["data"]

    def test_get_records(self, client: TestClient):
        token = _get_token(client)
        response = client.get(
            "/api/v1/points/records",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "list" in data["data"]
        assert "total" in data["data"]

    def test_check_feature_access(self, client: TestClient):
        token = _get_token(client)
        response = client.get(
            "/api/v1/points/features/ai_chat",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "allowed" in data["data"]


class TestPointsAdminAPI:
    def test_point_rules_crud(self, client: TestClient):
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 创建规则
        response = client.post(
            "/api/v1/admin/points/point-rules",
            json={
                "code": "api_test_rule",
                "name": "API测试规则",
                "rule_type": "earn",
                "amount": 5,
                "daily_limit": 1,
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        rule_id = next(r["id"] for r in data["data"] if r["code"] == "api_test_rule")

        # 更新规则
        response = client.put(
            f"/api/v1/admin/points/point-rules/{rule_id}",
            json={"amount": 10},
            headers=headers,
        )
        assert response.status_code == 200
        updated = next(r for r in response.json()["data"] if r["id"] == rule_id)
        assert updated["amount"] == 10

        # 删除规则
        response = client.delete(
            f"/api/v1/admin/points/point-rules/{rule_id}",
            headers=headers,
        )
        assert response.status_code == 200

    def test_feature_permissions_crud(self, client: TestClient):
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/admin/points/feature-permissions",
            json={
                "code": "api_test_feature",
                "name": "API测试功能",
                "required_points": 100,
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        fp_id = next(fp["id"] for fp in data["data"] if fp["code"] == "api_test_feature")

        response = client.delete(
            f"/api/v1/admin/points/feature-permissions/{fp_id}",
            headers=headers,
        )
        assert response.status_code == 200

    def test_adjust_points(self, client: TestClient):
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 获取测试用户 ID
        response = client.get("/api/v1/admin/users?page=1&page_size=10", headers=headers)
        assert response.status_code == 200
        users = response.json()["data"]["list"]
        user = next(u for u in users if u["email"] == "1538933906@qq.com")

        response = client.post(
            "/api/v1/admin/points/point-records/adjust",
            json={"user_id": user["id"], "amount": 50, "description": "测试补偿"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["balance"] is not None
