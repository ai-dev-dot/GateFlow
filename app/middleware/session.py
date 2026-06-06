"""Cookie-based session middleware for HTML page routes.

Pages use httpOnly cookies to store the JWT token (set during login).
API routes (/api/*, /v1/*) continue to use the Authorization header.
"""

import uuid

from fastapi import Cookie, Depends, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import User

COOKIE_NAME = "gf_session"


def _decode_cookie_token(token: str | None = Cookie(None, alias=COOKIE_NAME)) -> dict | None:
    """Decode JWT from cookie, return payload dict or None."""
    if not token:
        return None
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def get_current_user_from_cookie(
    payload: dict | None = Depends(_decode_cookie_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: require a valid session cookie, return User.

    Uses the shared get_db dependency so tests can override it.
    """
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="未登录")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="无效的会话")

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    return user


async def require_admin_from_cookie(
    user: User = Depends(get_current_user_from_cookie),
) -> User:
    """FastAPI dependency: require admin role from session cookie."""
    role_name = user.role.name if hasattr(user.role, 'name') else str(user.role)
    if role_name != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    return user
