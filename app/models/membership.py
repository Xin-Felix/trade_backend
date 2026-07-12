"""会员订阅系统模型。

包含：
- membership_tiers: 会员档位定义
- user_memberships: 用户会员记录
- subscription_orders: 订阅订单
- user_feature_usage: 按自然日统计功能免费使用次数
"""

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from app.db.base import Base
from app.models.mixins import SoftDeleteMixin


class MembershipTier(Base):
    """会员档位定义表"""

    __tablename__ = "membership_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, comment="档位标识: vip / svip")
    name = Column(String(100), nullable=False, comment="档位名称")
    description = Column(Text, nullable=True, comment="档位说明")
    price = Column(Integer, nullable=False, server_default="0", comment="价格（分）")
    duration_days = Column(Integer, nullable=False, comment="单次购买有效天数")
    monthly_points_grant = Column(
        Integer, nullable=False, server_default="0", comment="每月赠送积分，0 表示不赠送"
    )
    features = Column(
        JSON, nullable=False, default=list, comment="包含的功能 code 列表，['*'] 表示全部"
    )
    enabled = Column(Integer, nullable=False, server_default="1", comment="是否启用: 1=是 0=否")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class UserMembership(SoftDeleteMixin, Base):
    """用户会员记录表"""

    __tablename__ = "user_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    tier_code = Column(
        String(20), ForeignKey("membership_tiers.code"), nullable=False, comment="档位标识"
    )
    status = Column(
        String(20), nullable=False, server_default="active", comment="状态: active / expired / cancelled"
    )
    starts_at = Column(DateTime, nullable=False, server_default=func.now(), comment="开始时间")
    expires_at = Column(DateTime, nullable=False, comment="到期时间")
    auto_renew = Column(Integer, nullable=False, server_default="0", comment="是否自动续费: 1=是 0=否")
    last_grant_at = Column(DateTime, nullable=True, comment="上次发放月度积分时间")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SubscriptionOrder(SoftDeleteMixin, Base):
    """订阅订单表"""

    __tablename__ = "subscription_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    tier_code = Column(
        String(20), ForeignKey("membership_tiers.code"), nullable=False, comment="档位标识"
    )
    amount = Column(Integer, nullable=False, comment="支付金额（分）")
    currency = Column(String(10), nullable=False, server_default="CNY", comment="货币")
    status = Column(
        String(20), nullable=False, server_default="pending", comment="状态: pending / paid / cancelled / refunded"
    )
    channel = Column(String(50), nullable=True, comment="支付渠道")
    out_trade_no = Column(String(100), nullable=True, unique=True, comment="外部订单号")
    paid_at = Column(DateTime, nullable=True, comment="支付时间")
    expires_at = Column(DateTime, nullable=True, comment="该订单带来的到期时间")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class UserFeatureUsage(SoftDeleteMixin, Base):
    """用户功能每日使用计数表"""

    __tablename__ = "user_feature_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    feature_code = Column(String(100), nullable=False, comment="功能标识")
    usage_date = Column(Date, nullable=False, comment="使用日期")
    count = Column(Integer, nullable=False, server_default="0", comment="当日使用次数")

    __table_args__ = (
        Index(
            "uix_user_feature_usage_active",
            "user_id",
            "feature_code",
            "usage_date",
            unique=True,
            postgresql_where="is_deleted = 0",
        ),
    )
