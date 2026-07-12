"""积分系统模型。

包含：
- user_points: 用户积分余额（带乐观锁）
- point_records: 积分变动明细
- point_rules: 积分获取/消耗规则
- feature_permissions: 基于积分门槛的功能权限
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserPoint(Base):
    """用户积分余额表"""

    __tablename__ = "user_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True, comment="用户 ID")
    balance = Column(Integer, nullable=False, server_default="0", comment="当前积分余额")
    total_earned = Column(Integer, nullable=False, server_default="0", comment="累计获得积分")
    total_used = Column(Integer, nullable=False, server_default="0", comment="累计消耗积分")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class PointRecord(Base):
    """积分变动明细表"""

    __tablename__ = "point_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    type = Column(String(20), nullable=False, comment="变动类型: earn=获得 use=消耗 deduct=扣减 refund=退回 manual=手工")
    amount = Column(Integer, nullable=False, comment="变动积分（正数表示增加，负数表示减少）")
    balance_after = Column(Integer, nullable=False, comment="变动后余额")
    source = Column(String(100), nullable=True, comment="来源标识（规则 code / 功能 code / manual）")
    description = Column(String(255), nullable=True, comment="变动说明")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="操作人 ID（管理员手工操作时）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id], lazy="raise")
    operator = relationship("User", foreign_keys=[operator_id], lazy="raise")


class PointRule(Base):
    """积分规则表"""

    __tablename__ = "point_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, comment="规则标识，如 daily_login / invite_user")
    name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(20), nullable=False, comment="规则类型: earn=获取规则 use=消耗规则")
    amount = Column(Integer, nullable=False, comment="积分数量（正值）")
    description = Column(String(255), nullable=True, comment="规则说明")
    daily_limit = Column(Integer, nullable=True, comment="每日上限次数，为空表示无限制")
    enabled = Column(Integer, nullable=False, server_default="1", comment="是否启用: 1=是 0=否")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class FeaturePermission(Base):
    """功能权限表（基于积分门槛或角色）"""

    __tablename__ = "feature_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False, comment="功能标识，如 ai_chat / limit_up_ladder")
    name = Column(String(100), nullable=False, comment="功能名称")
    description = Column(Text, nullable=True, comment="功能说明")
    required_points = Column(Integer, nullable=False, server_default="0", comment="所需积分（0 表示免费）")
    required_role = Column(String(20), nullable=True, comment="所需角色，如 admin / vip，为空表示不限制")
    required_tier = Column(String(20), nullable=True, comment="所需会员档位，如 vip / svip")
    free_daily_limit = Column(
        Integer, nullable=False, server_default="0", comment="非会员每日免费次数，0 表示无免费额度"
    )
    consume_points = Column(
        Integer, nullable=False, server_default="1", comment="调用时是否扣积分: 1=是 0=否"
    )
    consume_mode = Column(
        String(20),
        nullable=False,
        server_default="per_call",
        comment="计费模式: per_call=每次调用扣积分, per_day=每天首次调用扣积分(自然日)"
    )
    enabled = Column(Integer, nullable=False, server_default="1", comment="是否启用: 1=是 0=否")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
