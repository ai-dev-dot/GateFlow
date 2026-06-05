from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import require_admin
from app.models import ProviderAPIKey
from app.schemas.provider_key import (
    ProviderKeyCreate,
    ProviderKeyResponse,
    ProviderKeyUpdate,
)

router = APIRouter(prefix="/api/gateway/provider-keys", tags=["上游 Key 管理"])


@router.get("", response_model=list[ProviderKeyResponse])
async def list_provider_keys(
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """列出所有上游 API Key，可按 provider 过滤"""
    stmt = select(ProviderAPIKey)
    if provider:
        stmt = stmt.where(ProviderAPIKey.provider == provider)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ProviderKeyResponse)
async def create_provider_key(
    request: ProviderKeyCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """创建上游 API Key（管理员）"""
    provider_key = ProviderAPIKey(
        provider=request.provider,
        key=request.key,
        name=request.name,
        remark=request.remark,
        rpm_limit=request.rpm_limit,
        tpm_limit=request.tpm_limit,
    )
    db.add(provider_key)
    await db.commit()
    await db.refresh(provider_key)
    return provider_key


@router.put("/{key_id}", response_model=ProviderKeyResponse)
async def update_provider_key(
    key_id: UUID,
    request: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """更新上游 API Key（管理员）"""
    result = await db.execute(select(ProviderAPIKey).where(ProviderAPIKey.id == key_id))
    provider_key = result.scalar_one_or_none()
    if not provider_key:
        raise HTTPException(status_code=404, detail="上游 Key 不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider_key, key, value)
    await db.commit()
    await db.refresh(provider_key)
    return provider_key


@router.delete("/{key_id}")
async def delete_provider_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """删除上游 API Key（管理员）"""
    result = await db.execute(select(ProviderAPIKey).where(ProviderAPIKey.id == key_id))
    provider_key = result.scalar_one_or_none()
    if not provider_key:
        raise HTTPException(status_code=404, detail="上游 Key 不存在")
    await db.delete(provider_key)
    await db.commit()
    return {"message": "上游 Key 已删除"}


@router.post("/{key_id}/reset", response_model=ProviderKeyResponse)
async def reset_provider_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """重置上游 Key 状态：清除错误计数、解除封禁（管理员）"""
    result = await db.execute(select(ProviderAPIKey).where(ProviderAPIKey.id == key_id))
    provider_key = result.scalar_one_or_none()
    if not provider_key:
        raise HTTPException(status_code=404, detail="上游 Key 不存在")
    provider_key.is_active = True
    provider_key.is_banned = False
    provider_key.ban_reason = None
    provider_key.consecutive_errors = 0
    provider_key.cool_down_until = None
    await db.commit()
    await db.refresh(provider_key)
    return provider_key
