from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_admin
from app.models import ModelConfig
from app.schemas.gateway import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
)

router = APIRouter(prefix="/api/gateway/models", tags=["模型配置管理"])


@router.get("", response_model=list[ModelConfigResponse])
async def list_model_configs(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """列出所有模型配置（登录用户可用）"""
    result = await db.execute(select(ModelConfig))
    return result.scalars().all()


@router.post("", response_model=ModelConfigResponse)
async def create_model_config(
    request: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """创建模型配置（管理员）"""
    model_config = ModelConfig(
        model_alias=request.model_alias,
        provider=request.provider,
        target_model=request.target_model,
        target_url=request.target_url,
        priority=request.priority,
        default_temperature=request.default_temperature,
        default_max_tokens=request.default_max_tokens,
    )
    db.add(model_config)
    await db.commit()
    await db.refresh(model_config)
    return model_config


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model_config(
    model_id: UUID,
    request: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """更新模型配置（管理员）"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model_config = result.scalar_one_or_none()
    if not model_config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model_config, key, value)
    await db.commit()
    await db.refresh(model_config)
    return model_config


@router.delete("/{model_id}")
async def delete_model_config(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """删除模型配置（管理员）"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model_config = result.scalar_one_or_none()
    if not model_config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    await db.delete(model_config)
    await db.commit()
    return {"message": "模型配置已删除"}
