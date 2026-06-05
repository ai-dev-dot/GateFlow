from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User, APIKey
from app.utils.security import decode_access_token

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user supporting both JWT Token and API Key authentication"""

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")

    token = credentials.credentials

    # Check if it's API Key (starts with gf_)
    if token.startswith("gf_"):
        result = await db.execute(
            select(APIKey).where(APIKey.key == token, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 已过期")

        api_key.last_used_at = datetime.utcnow()
        await db.commit()

        result = await db.execute(
            select(User).where(User.id == api_key.user_id).options(selectinload(User.role))
        )
        user = result.scalar_one_or_none()
    else:
        # JWT Token authentication
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")

        result = await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.role))
        )
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if user.role.name != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


@dataclass
class AuthContext:
    """Authentication context with optional API Key tracking info."""
    user: User
    api_key_id: Optional[UUID] = None
    agent_type: Optional[str] = None  # From APIKey.agent_type.name


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Like get_current_user but also returns api_key_id and agent_type for audit tracking."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")

    token = credentials.credentials
    api_key_id = None
    agent_type = None

    if token.startswith("gf_"):
        result = await db.execute(
            select(APIKey).where(APIKey.key == token, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 已过期")

        api_key.last_used_at = datetime.utcnow()
        await db.commit()

        api_key_id = api_key.id
        if hasattr(api_key, 'agent_type') and api_key.agent_type:
            agent_type = api_key.agent_type.name

        result = await db.execute(
            select(User).where(User.id == api_key.user_id).options(selectinload(User.role))
        )
        user = result.scalar_one_or_none()
    else:
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token")

        result = await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.role))
        )
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    return AuthContext(user=user, api_key_id=api_key_id, agent_type=agent_type)
