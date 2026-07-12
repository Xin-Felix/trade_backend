"""会员与接口级积分权限 API 测试。"""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.points import FeaturePermission
from app.models.user import User as UserModel
from app.services import membership_service, points_service
from app.services.auth_service import create_user


def _get_admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login/email",
        json={"email": "1538933906@qq.com", "password": "123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_user_and_token(client: TestClient, email: str) -> tuple[str, UserModel]:
    db = SessionLocal()
    try:
        try:
            user = create_user(db, email=email, password="123456", name="Test User")
        except ValueError:
            user = db.query(UserModel).filter(UserModel.email == email).first()
        response = client.post(
            "/api/v1/auth/login/email",
            json={"email": email, "password": "123456"},
        )
        assert response.status_code == 200
        return response.json()["access_token"], user
    finally:
        db.close()


class TestFeatureAccessAPI:
    def test_admin_access_protected_feature(self, client: TestClient):
        token = _get_admin_token(client)
        response = client.post(
            "/api/v1/ai/chat",
            json={"prompt": "测试", "role": "market_analyst", "stream": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        # admin 直接通过，后续可能因 AI 服务无响应而 500，但不会 402
        assert response.status_code != 402

    def test_feature_not_configured_allows_access(self, client: TestClient):
        token, _ = _create_user_and_token(
            client, f"not_configured_{datetime.utcnow().timestamp()}@example.com"
        )
        # 使用一个不可能被配置过的 feature_code，但依赖注入固定为 ai_chat 等
        # 这里直接调用 /points/features 检查未配置功能
        response = client.get(
            "/api/v1/points/features/not_configured_feature_xyz",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["allowed"] is True

    def test_feature_consumes_points(self, client: TestClient):
        email = f"consume_points_{datetime.utcnow().timestamp()}@example.com"
        token, user = _create_user_and_token(client, email)

        db = SessionLocal()
        try:
            # 创建功能权限
            existing = db.query(FeaturePermission).filter(FeaturePermission.code == "api_test_consume").first()
            if existing:
                db.delete(existing)
                db.commit()

            fp = FeaturePermission(
                code="api_test_consume",
                name="API 测试消费",
                required_points=30,
                free_daily_limit=0,
                consume_points=1,
                consume_mode="per_call",
                enabled=1,
            )
            db.add(fp)
            db.commit()

            # 给用户积分
            points_service.add_points(db, user.id, 50, source="test", description="测试充值")
            db.commit()
        finally:
            db.close()

        # 直接调用依赖 require_feature("api_test_consume") 的接口不方便，
        # 使用 /points/features 只校验不消费。这里直接调用服务层消费。
        db = SessionLocal()
        try:
            db_user = db.query(UserModel).filter(UserModel.id == user.id).first()
            result = membership_service.check_and_consume(db, db_user, "api_test_consume")
            assert result["allowed"] is True
            assert result["consumed"] is True
            assert result["cost"] == 30
            assert points_service.get_balance(db, user.id) == 20
        finally:
            db.close()

    def test_membership_covers_feature(self, client: TestClient):
        email = f"membership_cover_{datetime.utcnow().timestamp()}@example.com"
        token, user = _create_user_and_token(client, email)

        db = SessionLocal()
        try:
            # 确保 test_vip 档位存在
            tier = db.query(membership_service.MembershipTier).filter(
                membership_service.MembershipTier.code == "test_vip"
            ).first()
            if tier is None:
                tier = membership_service.MembershipTier(
                    code="test_vip",
                    name="测试 VIP",
                    price=2990,
                    duration_days=30,
                    monthly_points_grant=100,
                    features=["api_test_member_feature"],
                    enabled=1,
                )
                db.add(tier)
                db.commit()
                db.refresh(tier)

            existing = db.query(FeaturePermission).filter(
                FeaturePermission.code == "api_test_member_feature"
            ).first()
            if existing:
                db.delete(existing)
                db.commit()

            fp = FeaturePermission(
                code="api_test_member_feature",
                name="API 测试会员功能",
                required_points=100,
                required_tier="test_vip",
                free_daily_limit=0,
                consume_points=1,
                consume_mode="per_call",
                enabled=1,
            )
            db.add(fp)
            db.commit()

            # 开通会员
            membership_service.grant_membership_manually(
                db, user_id=user.id, tier_code="test_vip", duration_days=30, operator_id=user.id
            )

            db_user = db.query(UserModel).filter(UserModel.id == user.id).first()
            result = membership_service.check_and_consume(db, db_user, "api_test_member_feature")
            assert result["allowed"] is True
            assert result["consumed"] is False
            assert "会员" in result["reason"]
        finally:
            db.close()


class TestMembershipAdminAPI:
    def test_tiers_crud(self, client: TestClient):
        token = _get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        code = f"api_tier_{datetime.utcnow().timestamp()}"
        response = client.post(
            "/api/v1/admin/membership/tiers",
            json={
                "code": code,
                "name": "API 测试档位",
                "price": 1000,
                "duration_days": 30,
                "monthly_points_grant": 50,
                "features": ["a", "b"],
                "enabled": True,
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        tier_id = next(t["id"] for t in data["data"] if t["code"] == code)

        response = client.put(
            f"/api/v1/admin/membership/tiers/{tier_id}",
            json={"price": 2000},
            headers=headers,
        )
        assert response.status_code == 200
        updated = next(t for t in response.json()["data"] if t["id"] == tier_id)
        assert updated["price"] == 2000

        response = client.delete(
            f"/api/v1/admin/membership/tiers/{tier_id}",
            headers=headers,
        )
        assert response.status_code == 200

    def test_order_and_confirm(self, client: TestClient):
        token = _get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        db = SessionLocal()
        try:
            # 准备普通用户和档位
            email = f"order_user_{datetime.utcnow().timestamp()}@example.com"
            try:
                user = create_user(db, email=email, password="123456", name="Order User")
            except ValueError:
                user = db.query(UserModel).filter(UserModel.email == email).first()

            tier = db.query(membership_service.MembershipTier).filter(
                membership_service.MembershipTier.code == "test_vip"
            ).first()
            if tier is None:
                tier = membership_service.MembershipTier(
                    code="test_vip",
                    name="测试 VIP",
                    price=2990,
                    duration_days=30,
                    monthly_points_grant=100,
                    features=["*"],
                    enabled=1,
                )
                db.add(tier)
                db.commit()
                db.refresh(tier)

            user_public_id = user.public_id
            tier_code = tier.code
            tier_price = tier.price
        finally:
            db.close()

        response = client.post(
            "/api/v1/admin/membership/orders",
            json={"user_id": user_public_id, "tier_code": tier_code, "amount": tier_price},
            headers=headers,
        )
        assert response.status_code == 200
        order_id = response.json()["data"][0]["id"]

        response = client.post(
            f"/api/v1/admin/membership/orders/{order_id}/confirm",
            json={"out_trade_no": "TEST_TRADE_NO"},
            headers=headers,
        )
        assert response.status_code == 200

    def test_grant_membership_manually(self, client: TestClient):
        token = _get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        db = SessionLocal()
        try:
            email = f"grant_user_{datetime.utcnow().timestamp()}@example.com"
            try:
                user = create_user(db, email=email, password="123456", name="Grant User")
            except ValueError:
                user = db.query(UserModel).filter(UserModel.email == email).first()

            tier = db.query(membership_service.MembershipTier).filter(
                membership_service.MembershipTier.code == "test_vip"
            ).first()
            if tier is None:
                tier = membership_service.MembershipTier(
                    code="test_vip",
                    name="测试 VIP",
                    price=2990,
                    duration_days=30,
                    monthly_points_grant=100,
                    features=["*"],
                    enabled=1,
                )
                db.add(tier)
                db.commit()
                db.refresh(tier)

            user_public_id = user.public_id
            tier_code = tier.code
        finally:
            db.close()

        response = client.post(
            "/api/v1/admin/membership/users/grant",
            json={"user_id": user_public_id, "tier_code": tier_code, "duration_days": 30},
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(
            "/api/v1/membership/status",
            headers={"Authorization": f"Bearer {_create_user_and_token(client, email)[0]}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["active"] is True
        assert data["data"]["tier_code"] == tier.code

    def test_membership_tasks(self, client: TestClient):
        token = _get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/api/v1/admin/membership/tasks/expire", headers=headers)
        assert response.status_code == 200

        response = client.post("/api/v1/admin/membership/tasks/grant-monthly", headers=headers)
        assert response.status_code == 200
