"""分时资金流向默认板块/概念配置管理接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.sector_default_config import SectorDefaultConfig
from app.schemas.sector_default_config import (
    SectorDefaultConfigCreateRequest,
    SectorDefaultConfigDetailResponse,
    SectorDefaultConfigListResponse,
    SectorDefaultConfigOperationResponse,
    SectorDefaultConfigUpdateRequest,
)
from app.schemas.user import User

router = APIRouter()


def _to_dict(config: SectorDefaultConfig) -> dict:
    return {
        "id": config.id,
        "sector_type": config.sector_type,
        "sector_ids": config.sector_ids or [],
        "is_enabled": config.is_enabled == 1,
        "created_at": config.created_at.strftime("%Y-%m-%d %H:%M:%S") if config.created_at else "",
        "updated_at": config.updated_at.strftime("%Y-%m-%d %H:%M:%S") if config.updated_at else "",
    }


@router.get("", response_model=SectorDefaultConfigListResponse)
async def list_sector_default_configs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取全部默认配置列表。"""
    items = db.query(SectorDefaultConfig).order_by(SectorDefaultConfig.id.asc()).all()
    return SectorDefaultConfigListResponse(data=[_to_dict(item) for item in items])


@router.post("", response_model=SectorDefaultConfigDetailResponse)
async def create_sector_default_config(
    payload: SectorDefaultConfigCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建默认配置。"""
    existing = (
        db.query(SectorDefaultConfig)
        .filter(SectorDefaultConfig.sector_type == payload.sector_type)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"该类型配置已存在: {payload.sector_type}")

    config = SectorDefaultConfig(
        sector_type=payload.sector_type,
        sector_ids=list(payload.sector_ids),
        is_enabled=1 if payload.is_enabled else 0,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return SectorDefaultConfigDetailResponse(data=_to_dict(config))


@router.get("/{config_id}", response_model=SectorDefaultConfigDetailResponse)
async def get_sector_default_config(
    config_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取配置详情。"""
    config = db.query(SectorDefaultConfig).filter(SectorDefaultConfig.id == config_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SectorDefaultConfigDetailResponse(data=_to_dict(config))


@router.put("/{config_id}", response_model=SectorDefaultConfigDetailResponse)
async def update_sector_default_config(
    config_id: int,
    payload: SectorDefaultConfigUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新配置。"""
    config = db.query(SectorDefaultConfig).filter(SectorDefaultConfig.id == config_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="配置不存在")

    data = payload.model_dump(exclude_none=True)
    if "sector_ids" in data:
        data["sector_ids"] = list(data["sector_ids"])
    if "is_enabled" in data:
        data["is_enabled"] = 1 if data["is_enabled"] else 0

    for field, value in data.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)
    return SectorDefaultConfigDetailResponse(data=_to_dict(config))


@router.delete("/{config_id}", response_model=SectorDefaultConfigOperationResponse)
async def delete_sector_default_config(
    config_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除配置。"""
    config = db.query(SectorDefaultConfig).filter(SectorDefaultConfig.id == config_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="配置不存在")

    db.delete(config)
    db.commit()
    return SectorDefaultConfigOperationResponse(message="删除成功")
