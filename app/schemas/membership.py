"""会员订阅系统请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 会员档位
# ---------------------------------------------------------------------------


class MembershipTierItem(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    price: int
    duration_days: int
    monthly_points_grant: int
    features: list[str]
    enabled: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MembershipTierListResponse(BaseModel):
    success: bool = True
    data: list[MembershipTierItem]


class MembershipTierCreateRequest(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    price: int = Field(..., ge=0)
    duration_days: int = Field(..., ge=1)
    monthly_points_grant: int = Field(0, ge=0)
    features: list[str] = Field(default_factory=list)
    enabled: bool = True


class MembershipTierUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = Field(None, ge=0)
    duration_days: Optional[int] = Field(None, ge=1)
    monthly_points_grant: Optional[int] = Field(None, ge=0)
    features: Optional[list[str]] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# 订阅订单
# ---------------------------------------------------------------------------


class SubscriptionOrderItem(BaseModel):
    id: int
    user_id: int
    user_public_id: Optional[str] = None
    user_email: Optional[str] = None
    tier_code: str
    amount: int
    currency: str
    status: str
    channel: Optional[str] = None
    out_trade_no: Optional[str] = None
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubscriptionOrderListResponse(BaseModel):
    success: bool = True
    data: list[SubscriptionOrderItem]


class SubscriptionOrderCreateRequest(BaseModel):
    user_id: str
    tier_code: str
    amount: int = Field(..., ge=0)
    currency: str = "CNY"
    channel: Optional[str] = None
    out_trade_no: Optional[str] = None


class SubscriptionOrderConfirmRequest(BaseModel):
    out_trade_no: Optional[str] = None


# ---------------------------------------------------------------------------
# 用户会员
# ---------------------------------------------------------------------------


class UserMembershipItem(BaseModel):
    id: int
    user_id: int
    user_public_id: Optional[str] = None
    user_email: Optional[str] = None
    tier_code: str
    status: str
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    auto_renew: int
    last_grant_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserMembershipListResponse(BaseModel):
    success: bool = True
    data: list[UserMembershipItem]


class UserMembershipGrantRequest(BaseModel):
    user_id: str
    tier_code: str
    duration_days: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# 通用响应
# ---------------------------------------------------------------------------


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class MembershipStatusResponse(BaseModel):
    success: bool = True
    data: dict
