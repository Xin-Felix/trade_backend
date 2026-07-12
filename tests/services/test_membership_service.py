"""会员订阅服务单元测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.membership import MembershipTier, SubscriptionOrder, UserMembership
from app.models.points import FeaturePermission
from app.models.user import User as UserModel
from app.services import membership_service, points_service
from app.services.auth_service import create_user


@pytest.fixture(scope="function")
def test_user(db: Session):
    email = f"membership_test_{datetime.now(timezone.utc).timestamp()}@example.com"
    return create_user(db, email=email, password="123456", name="Membership Test")


@pytest.fixture(scope="function")
def another_user(db: Session):
    email = f"membership_test2_{datetime.now(timezone.utc).timestamp()}@example.com"
    return create_user(db, email=email, password="123456", name="Membership Test 2")


@pytest.fixture(scope="function")
def vip_tier(db: Session):
    existing = db.query(MembershipTier).filter(MembershipTier.code == "test_vip").first()
    if existing:
        return existing
    tier = MembershipTier(
        code="test_vip",
        name="测试 VIP",
        price=2990,
        duration_days=30,
        monthly_points_grant=100,
        features=["vip_feature", "shared_feature"],
        enabled=1,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return tier


@pytest.fixture(scope="function")
def svip_tier(db: Session):
    existing = db.query(MembershipTier).filter(MembershipTier.code == "test_svip").first()
    if existing:
        return existing
    tier = MembershipTier(
        code="test_svip",
        name="测试 SVIP",
        price=9990,
        duration_days=30,
        monthly_points_grant=500,
        features=["*"],
        enabled=1,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return tier


@pytest.fixture(scope="function")
def paid_feature(db: Session):
    code = f"test_paid_feature_{datetime.now(timezone.utc).timestamp()}"
    fp = FeaturePermission(
        code=code,
        name="测试付费功能",
        required_points=50,
        required_role=None,
        required_tier=None,
        free_daily_limit=0,
        consume_points=1,
        enabled=1,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    yield fp
    db.delete(fp)
    db.commit()


@pytest.fixture(scope="function")
def free_daily_feature(db: Session):
    code = f"test_free_daily_{datetime.now(timezone.utc).timestamp()}"
    fp = FeaturePermission(
        code=code,
        name="测试每日免费功能",
        required_points=10,
        required_role=None,
        required_tier=None,
        free_daily_limit=2,
        consume_points=1,
        enabled=1,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    yield fp
    db.delete(fp)
    db.commit()


@pytest.fixture(scope="function")
def vip_feature(db: Session):
    code = f"vip_feature_{datetime.now(timezone.utc).timestamp()}"
    # required_tier 固定指向 test_vip
    fp = FeaturePermission(
        code=code,
        name="VIP 专属功能",
        required_points=100,
        required_role=None,
        required_tier="test_vip",
        free_daily_limit=0,
        consume_points=1,
        enabled=1,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    yield fp
    db.delete(fp)
    db.commit()


@pytest.fixture(scope="function")
def per_day_feature(db: Session):
    code = f"test_per_day_{datetime.now(timezone.utc).timestamp()}"
    fp = FeaturePermission(
        code=code,
        name="测试按天计费功能",
        required_points=20,
        required_role=None,
        required_tier=None,
        free_daily_limit=0,
        consume_points=1,
        consume_mode="per_day",
        enabled=1,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    yield fp
    db.delete(fp)
    db.commit()


class TestMembershipService:
    def test_create_and_list_tiers(self, db: Session):
        code = f"test_create_tier_{datetime.now(timezone.utc).timestamp()}"
        tier = membership_service.create_tier(
            db,
            code=code,
            name="测试创建档位",
            price=100,
            duration_days=7,
            monthly_points_grant=10,
            features=["a", "b"],
        )
        assert tier.code == code

        tiers = membership_service.list_tiers(db)
        codes = [t.code for t in tiers]
        assert code in codes

    def test_create_tier_duplicate_code(self, db: Session, vip_tier: MembershipTier):
        with pytest.raises(ValueError, match="会员档位 code 已存在"):
            membership_service.create_tier(
                db,
                code=vip_tier.code,
                name="重复",
                price=1,
                duration_days=1,
            )

    def test_update_tier(self, db: Session, vip_tier: MembershipTier):
        updated = membership_service.update_tier(db, vip_tier.id, name="更新后的名称", price=1000)
        assert updated.name == "更新后的名称"
        assert updated.price == 1000

    def test_grant_membership_manually(self, db: Session, test_user: UserModel, vip_tier: MembershipTier):
        before_balance = points_service.get_balance(db, test_user.id)
        membership = membership_service.grant_membership_manually(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            duration_days=vip_tier.duration_days,
            operator_id=test_user.id,
        )
        assert membership.user_id == test_user.id
        assert membership.tier_code == vip_tier.code
        assert membership.status == "active"
        assert membership.expires_at > membership.starts_at

        # 应赠送首月积分
        after_balance = points_service.get_balance(db, test_user.id)
        assert after_balance == before_balance + vip_tier.monthly_points_grant

    def test_get_active_membership(self, db: Session, test_user: UserModel, vip_tier: MembershipTier):
        membership_service.grant_membership_manually(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            duration_days=vip_tier.duration_days,
            operator_id=test_user.id,
        )
        active = membership_service.get_active_membership(db, test_user.id)
        assert active is not None
        assert active.tier_code == vip_tier.code

    def test_tier_covers_feature(self, db: Session, vip_tier: MembershipTier, svip_tier: MembershipTier):
        assert membership_service.tier_covers_feature(db, vip_tier.code, "vip_feature") is True
        assert membership_service.tier_covers_feature(db, vip_tier.code, "shared_feature") is True
        assert membership_service.tier_covers_feature(db, vip_tier.code, "other_feature") is False
        assert membership_service.tier_covers_feature(db, svip_tier.code, "any_feature") is True

    def test_check_and_consume_admin_always_allowed(self, db: Session, test_user: UserModel):
        test_user.role = "admin"
        db.commit()
        result = membership_service.check_and_consume(db, test_user, "any_feature")
        assert result["allowed"] is True
        assert result["reason"] == "管理员权限"
        test_user.role = "user"
        db.commit()

    def test_check_and_consume_unconfigured_feature(self, db: Session, another_user: UserModel):
        result = membership_service.check_and_consume(db, another_user, "not_configured_feature_xyz")
        assert result["allowed"] is True
        assert "未配置" in result["reason"]

    def test_check_and_consume_with_membership(
        self, db: Session, another_user: UserModel, vip_tier: MembershipTier, vip_feature: FeaturePermission
    ):
        # 开通 VIP
        membership_service.grant_membership_manually(
            db,
            user_id=another_user.id,
            tier_code=vip_tier.code,
            duration_days=30,
            operator_id=another_user.id,
        )

        result = membership_service.check_and_consume(db, another_user, vip_feature.code)
        assert result["allowed"] is True
        assert result["consumed"] is False
        assert "会员" in result["reason"]

    def test_check_and_consume_free_daily_limit(
        self, db: Session, another_user: UserModel, free_daily_feature: FeaturePermission
    ):
        # 前两次应走免费额度
        for _ in range(2):
            result = membership_service.check_and_consume(db, another_user, free_daily_feature.code)
            assert result["allowed"] is True
            assert result["consumed"] is False
            assert "免费额度" in result["reason"]

        # 第三次需要积分，余额不足
        result = membership_service.check_and_consume(db, another_user, free_daily_feature.code)
        assert result["allowed"] is False

    def test_check_and_consume_points_deduction(
        self, db: Session, another_user: UserModel, paid_feature: FeaturePermission
    ):
        # 先给积分
        points_service.add_points(db, another_user.id, 80, source="test", description="测试充值")

        result = membership_service.check_and_consume(db, another_user, paid_feature.code)
        assert result["allowed"] is True
        assert result["consumed"] is True
        assert result["cost"] == paid_feature.required_points

        # 余额不足时再调用
        result = membership_service.check_and_consume(db, another_user, paid_feature.code)
        assert result["allowed"] is False

    def test_check_and_consume_without_consume(
        self, db: Session, another_user: UserModel, paid_feature: FeaturePermission
    ):
        points_service.add_points(db, another_user.id, 200, source="test", description="测试充值")
        result = membership_service.check_and_consume(db, another_user, paid_feature.code, consume=False)
        assert result["allowed"] is True
        assert result["consumed"] is False
        assert points_service.get_balance(db, another_user.id) == 200

    def test_check_and_consume_per_day_mode(
        self, db: Session, another_user: UserModel, per_day_feature: FeaturePermission
    ):
        points_service.add_points(db, another_user.id, 100, source="test", description="测试充值")

        # 第一次调用扣费
        result = membership_service.check_and_consume(db, another_user, per_day_feature.code)
        assert result["allowed"] is True
        assert result["consumed"] is True
        assert result["cost"] == per_day_feature.required_points
        assert points_service.get_balance(db, another_user.id) == 80

        # 当天再次调用免费
        result = membership_service.check_and_consume(db, another_user, per_day_feature.code)
        assert result["allowed"] is True
        assert result["consumed"] is False
        assert result["reason"] == "今日已扣费，本次免费"
        assert points_service.get_balance(db, another_user.id) == 80

    def test_increment_free_usage(self, db: Session, another_user: UserModel):
        code = f"test_feature_usage_{datetime.now(timezone.utc).timestamp()}"
        count = membership_service.increment_free_usage(db, another_user.id, code)
        assert count == 1
        count = membership_service.increment_free_usage(db, another_user.id, code)
        assert count == 2

    def test_create_and_confirm_order(self, db: Session, another_user: UserModel, vip_tier: MembershipTier):
        order = membership_service.create_order(
            db,
            user_id=another_user.id,
            tier_code=vip_tier.code,
            amount=vip_tier.price,
        )
        assert order.status == "pending"

        membership = membership_service.confirm_order_payment(db, order.id, out_trade_no="TEST123")
        assert membership.tier_code == vip_tier.code

        refreshed_order = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order.id).first()
        assert refreshed_order.status == "paid"

    def test_confirm_paid_order_fails(self, db: Session, another_user: UserModel, vip_tier: MembershipTier):
        order = membership_service.create_order(
            db,
            user_id=another_user.id,
            tier_code=vip_tier.code,
            amount=vip_tier.price,
        )
        membership_service.confirm_order_payment(db, order.id)
        with pytest.raises(ValueError, match="订单已支付"):
            membership_service.confirm_order_payment(db, order.id)

    def test_membership_renewal_extends_expires_at(
        self, db: Session, test_user: UserModel, vip_tier: MembershipTier
    ):
        membership_service.grant_membership_manually(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            duration_days=vip_tier.duration_days,
            operator_id=test_user.id,
        )
        active = membership_service.get_active_membership(db, test_user.id)
        old_expires = active.expires_at

        order = membership_service.create_order(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            amount=vip_tier.price,
        )
        membership_service.confirm_order_payment(db, order.id)

        new_active = membership_service.get_active_membership(db, test_user.id)
        assert new_active.expires_at > old_expires

    def test_expire_memberships(self, db: Session, another_user: UserModel, vip_tier: MembershipTier):
        # 创建一个已过期会员
        expired_membership = UserMembership(
            user_id=another_user.id,
            tier_code=vip_tier.code,
            status="active",
            starts_at=datetime.now(timezone.utc) - timedelta(days=60),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(expired_membership)
        db.commit()

        count = membership_service.expire_memberships(db)
        assert count >= 1

        refreshed = db.query(UserMembership).filter(UserMembership.id == expired_membership.id).first()
        assert refreshed.status == "expired"

    def test_grant_monthly_points_if_due(self, db: Session, test_user: UserModel, vip_tier: MembershipTier):
        membership_service.grant_membership_manually(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            duration_days=vip_tier.duration_days,
            operator_id=test_user.id,
        )
        active = membership_service.get_active_membership(db, test_user.id)
        active.last_grant_at = datetime.now(timezone.utc) - timedelta(days=31)
        db.commit()

        before_balance = points_service.get_balance(db, test_user.id)
        count = membership_service.grant_monthly_points_if_due(db)
        assert count >= 1

        after_balance = points_service.get_balance(db, test_user.id)
        assert after_balance == before_balance + vip_tier.monthly_points_grant

    def test_cancel_membership(self, db: Session, another_user: UserModel, vip_tier: MembershipTier):
        membership = UserMembership(
            user_id=another_user.id,
            tier_code=vip_tier.code,
            status="active",
            starts_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)

        membership_service.cancel_membership(db, membership.id)
        refreshed = db.query(UserMembership).filter(UserMembership.id == membership.id).first()
        assert refreshed.status == "cancelled"

    def test_list_user_memberships(self, db: Session, test_user: UserModel, vip_tier: MembershipTier):
        membership_service.grant_membership_manually(
            db,
            user_id=test_user.id,
            tier_code=vip_tier.code,
            duration_days=vip_tier.duration_days,
            operator_id=test_user.id,
        )
        items, total = membership_service.list_user_memberships(db, user_id=test_user.id)
        assert total >= 1
        assert all(m.user_id == test_user.id for m in items)
