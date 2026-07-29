"""分时资金流向默认板块/概念配置请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel, Field


class SectorDefaultConfigItem(BaseModel):
    """配置项"""

    id: int
    sector_type: str
    sector_ids: list[str]
    is_enabled: bool
    created_at: str
    updated_at: str


class SectorDefaultConfigCreateRequest(BaseModel):
    """创建配置"""

    sector_type: str = Field(..., pattern=r"^(concept|industry)$")
    sector_ids: list[str] = Field(default_factory=list, max_length=30)
    is_enabled: bool = True


class SectorDefaultConfigUpdateRequest(BaseModel):
    """更新配置"""

    sector_ids: Optional[list[str]] = Field(default=None, max_length=30)
    is_enabled: Optional[bool] = None


class SectorDefaultConfigListResponse(BaseModel):
    success: bool = True
    data: list[SectorDefaultConfigItem]


class SectorDefaultConfigDetailResponse(BaseModel):
    success: bool = True
    data: SectorDefaultConfigItem


class SectorDefaultConfigOperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


class SectorDefaultConfigPublicData(BaseModel):
    """公开接口返回的数据（供 App 读取默认勾选）"""

    sector_type: str
    sector_ids: list[str]


class SectorDefaultConfigPublicResponse(BaseModel):
    success: bool = True
    data: SectorDefaultConfigPublicData
