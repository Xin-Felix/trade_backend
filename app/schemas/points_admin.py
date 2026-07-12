"""管理端积分系统请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PointRuleItem(BaseModel):
    """积分规则项"""
    id: int
    code: str
    name: str
    rule_type: str
    amount: int
    description: Optional[str] = None
    daily_limit: Optional[int] = None
    enabled: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PointRuleListResponse(BaseModel):
    success: bool = True
    data: list[PointRuleItem]


class PointRuleCreateRequest(BaseModel):
    code: str
    name: str
    rule_type: str = Field(..., pattern="^(earn|use)$")
    amount: int = Field(..., gt=0)
    description: Optional[str] = None
    daily_limit: Optional[int] = None
    enabled: bool = True


class PointRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = Field(None, pattern="^(earn|use)$")
    amount: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None
    daily_limit: Optional[int] = None
    enabled: Optional[bool] = None


class PointRecordAdminListData(BaseModel):
    list: list[dict]
    total: int
    page: int
    page_size: int


class PointRecordAdminListResponse(BaseModel):
    success: bool = True
    data: PointRecordAdminListData


class PointRecordSourcesResponse(BaseModel):
    success: bool = True
    data: list[str]


class PointAdjustRequest(BaseModel):
    user_id: str
    amount: int
    description: str


class PointAdjustResponse(BaseModel):
    success: bool = True
    data: dict


class FeaturePermissionItem(BaseModel):
    """功能权限项"""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    required_points: int
    required_role: Optional[str] = None
    required_tier: Optional[str] = None
    free_daily_limit: int
    consume_points: int
    consume_mode: str
    enabled: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FeaturePermissionListResponse(BaseModel):
    success: bool = True
    data: list[FeaturePermissionItem]


class FeaturePermissionCreateRequest(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    required_points: int = 0
    required_role: Optional[str] = None
    required_tier: Optional[str] = None
    free_daily_limit: int = 0
    consume_points: bool = True
    consume_mode: str = Field("per_call", pattern="^(per_call|per_day)$")
    enabled: bool = True


class FeaturePermissionUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    required_points: Optional[int] = None
    required_role: Optional[str] = None
    required_tier: Optional[str] = None
    free_daily_limit: Optional[int] = None
    consume_points: Optional[bool] = None
    consume_mode: Optional[str] = Field(None, pattern="^(per_call|per_day)$")
    enabled: Optional[bool] = None


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"
