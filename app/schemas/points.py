"""用户端积分系统请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PointSummary(BaseModel):
    """用户积分汇总"""
    balance: int
    total_earned: int
    total_used: int
    updated_at: Optional[datetime] = None


class PointBalanceResponse(BaseModel):
    success: bool = True
    data: PointSummary


class PointRecordItem(BaseModel):
    """积分明细项"""
    id: int
    type: str
    amount: int
    balance_after: int
    source: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class PointRecordListData(BaseModel):
    list: list[PointRecordItem]
    total: int
    page: int
    page_size: int


class PointRecordListResponse(BaseModel):
    success: bool = True
    data: PointRecordListData


class FeatureAccessResult(BaseModel):
    """功能权限检查结果"""
    allowed: bool
    reason: str
    required_points: Optional[int] = None
    balance: int


class FeatureAccessResponse(BaseModel):
    success: bool = True
    data: FeatureAccessResult
