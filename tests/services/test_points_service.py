"""积分服务单元测试。"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.points import FeaturePermission, PointRule
from app.models.user import User as UserModel
from app.services import points_service
from app.services.auth_service import create_user


@pytest.fixture(scope="function")
def test_user(db: Session):
    email = f"points_test_{datetime.now(timezone.utc).timestamp()}@example.com"
    return create_user(db, email=email, password="123456", name="Points Test")


@pytest.fixture(scope="function")
def earn_rule(db: Session):
    existing = db.query(PointRule).filter(PointRule.code == "test_daily_login").first()
    if existing:
        db.delete(existing)
        db.commit()
    rule = PointRule(
        code="test_daily_login",
        name="每日登录",
        rule_type="earn",
        amount=10,
        description="测试规则",
        daily_limit=1,
        enabled=1,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


class TestPointsService:
    def test_get_or_create_user_point(self, db: Session, test_user: UserModel):
        point = points_service.get_or_create_user_point(db, test_user.id)
        assert point.user_id == test_user.id
        assert point.balance == 0

    def test_add_points(self, db: Session, test_user: UserModel):
        point, record = points_service.add_points(
            db, test_user.id, 100, source="signup", description="注册奖励"
        )
        assert point.balance == 100
        assert record.amount == 100
        assert record.balance_after == 100

    def test_deduct_points_success(self, db: Session, test_user: UserModel):
        points_service.add_points(db, test_user.id, 100, source="test", description="初始积分")
        point, record = points_service.deduct_points(
            db, test_user.id, 30, source="feature", description="使用功能"
        )
        assert point.balance == 70
        assert record.amount == -30

    def test_deduct_points_insufficient(self, db: Session, test_user: UserModel):
        with pytest.raises(points_service.InsufficientPointsError):
            points_service.deduct_points(
                db, test_user.id, 9999, source="feature", description="余额不足"
            )

    def test_apply_rule_daily_limit(self, db: Session, test_user: UserModel, earn_rule: PointRule):
        # 应用规则增加 10 积分
        result = points_service.apply_rule(db, test_user.id, earn_rule.code)
        assert result is not None
        assert result[0].balance == 10

        # 再次应用应受每日上限限制
        result = points_service.apply_rule(db, test_user.id, earn_rule.code)
        assert result is None

    def test_adjust_points(self, db: Session, test_user: UserModel):
        point, record = points_service.adjust_points(
            db, test_user.id, 20, "管理员补偿", operator_id=test_user.id
        )
        assert point.balance == 20
        assert record.type == "manual"

    def test_feature_permission(self, db: Session, test_user: UserModel):
        existing = db.query(FeaturePermission).filter(FeaturePermission.code == "test_feature").first()
        if existing:
            db.delete(existing)
            db.commit()

        points_service.add_points(db, test_user.id, 100, source="test", description="初始积分")
        fp = points_service.create_feature_permission(
            db, code="test_feature", name="测试功能", required_points=60
        )
        result = points_service.check_feature_access(db, test_user, fp.code)
        assert result["allowed"] is True
        assert result["required_points"] == 60

        # 消耗积分（余额 100 -> 40）
        result = points_service.consume_feature_access(db, test_user, fp.code)
        assert result["allowed"] is True
        assert points_service.get_balance(db, test_user.id) == 40

        # 再消耗一次应不足
        result = points_service.consume_feature_access(db, test_user, fp.code)
        assert result["allowed"] is False

        points_service.delete_feature_permission(db, fp.id)
