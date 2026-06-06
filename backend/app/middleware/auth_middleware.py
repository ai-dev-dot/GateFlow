from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import APIKey, User
from app.utils.hashing import hash_api_key
from app.utils.security import decode_access_token

security = HTTPBearer(auto_error=False)


async def _resolve_credentials(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
) -> tuple[User, UUID | None, str | None]:
    """Resolve a Bearer credential to a User, plus optional api_key_id / agent_type.

    Supports two schemes:
      - ``gf_``-prefixed API Key (HMAC-hashed, O(1) lookup)
      - JWT (HS256) containing ``sub`` = user id

    Returns ``(user, api_key_id, agent_type)``. ``api_key_id`` and ``agent_type``
    are ``None`` for JWT auth.

    Raises 401 / 403 on invalid, expired, missing, or disabled credentials.
    """
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")

    token = credentials.credentials
    api_key_id: UUID | None = None
    agent_type: str | None = None
    user_id = None

    if token.startswith("gf_"):
        # O(1) indexed lookup by HMAC hash (plaintext is never stored).
        incoming_hash = hash_api_key(token)
        result = await db.execute(
            select(APIKey).where(APIKey.key_hash == incoming_hash, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 已过期")

        api_key.last_used_at = datetime.utcnow()
        await db.commit()

        api_key_id = api_key.id
        if hasattr(api_key, "agent_type") and api_key.agent_type:
            agent_type = api_key.agent_type.name

        user_id = api_key.user_id
    else:
        # JWT Token authentication
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")
        # auth_service stores `sub` as str(user.id); convert to UUID for a
        # portable WHERE-clause that works in both PG (UUID column) and SQLite
        # (where str→UUID binding would otherwise fail with `.hex` AttributeError).
        user_id = UUID(user_id_str)

    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.role), selectinload(User.department))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    return user, api_key_id, agent_type


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user supporting both JWT Token and API Key authentication."""
    user, _, _ = await _resolve_credentials(credentials, db)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role."""
    if user.role.name != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


@dataclass
class AuthContext:
    """Authentication context with optional API Key tracking info."""

    user: User
    api_key_id: UUID | None = None
    agent_type: str | None = None  # From APIKey.agent_type.name


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Like get_current_user but also returns api_key_id and agent_type for audit tracking."""
    user, api_key_id, agent_type = await _resolve_credentials(credentials, db)
    return AuthContext(user=user, api_key_id=api_key_id, agent_type=agent_type)
