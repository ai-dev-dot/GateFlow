from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models import APIKey, User
from app.models.api_key import generate_api_key
from app.schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyResponse, APIKeyUpdate

router = APIRouter(prefix="/api/api-keys", tags=["API Key 管理"])


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's API keys (display-only, no full plaintext)."""
    result = await db.execute(select(APIKey).where(APIKey.user_id == user.id))
    return result.scalars().all()


@router.post("", response_model=APIKeyCreated, status_code=201)
async def create_api_key(
    request: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new API key. The plaintext key is returned ONCE in this
    response — the server cannot recover it later (only the HMAC hash is
    stored). Frontend must display with a copy button + save warning.
    """
    full_key, key_prefix, key_hash = generate_api_key()
    api_key = APIKey(
        user_id=user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        permissions=request.permissions,
        rate_limit=request.rate_limit,
        expires_at=request.expires_at,
        agent_type_id=request.agent_type_id,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    # Inject the one-time plaintext key into the response (not stored on the model)
    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions,
        rate_limit=api_key.rate_limit,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        agent_type_id=api_key.agent_type_id,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: UUID,
    request: APIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(api_key, key, value)
    await db.commit()
    await db.refresh(api_key)
    return api_key


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    await db.delete(api_key)
    await db.commit()
    return {"message": "API Key 已删除"}
