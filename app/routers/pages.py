"""HTML page routes — served by Jinja2 templates.

Path: /pages/*
All routes require authentication (cookie session).
API routes (/api/*, /v1/*) remain unchanged and use JWT.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.session import (
    COOKIE_NAME,
    get_current_user_from_cookie,
    require_admin_from_cookie,
)
from app.models import User
from app.services.auth_service import AuthService
from app.templates_config import templates

router = APIRouter(prefix="/pages", tags=["Pages"])


# --- Public ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle login form submission. Set httpOnly cookie on success."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(username, password)

    if not user:
        return templates.TemplateResponse(request, "login.html", {"error": "用户名或密码错误"})

    from app.config import get_settings
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    token = jwt.encode(
        {"sub": str(user.id), "username": user.username, "role": user.role.name if user.role else "user", "exp": expire},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    response = RedirectResponse(url="/pages/chat", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_DAYS * 86400,
    )
    return response


@router.get("/logout")
async def logout():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/pages/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# --- Authenticated (admin + user) ---

@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, user: User = Depends(get_current_user_from_cookie)):
    return templates.TemplateResponse(request, "chat.html", {"user": user})


# --- Admin only ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@router.get("/my-usage", response_class=HTMLResponse)
async def my_usage_page(request: Request, user: User = Depends(get_current_user_from_cookie)):
    return templates.TemplateResponse(request, "user_dashboard.html", {"user": user})


@router.get("/gateway", response_class=HTMLResponse)
async def gateway_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "gateway.html", {"user": user})


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "users.html", {"user": user})


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "audit.html", {"user": user})


@router.get("/usage", response_class=HTMLResponse)
async def usage_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "usage.html", {"user": user})


@router.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "api_keys.html", {"user": user})


@router.get("/backup", response_class=HTMLResponse)
async def backup_page(request: Request, user: User = Depends(require_admin_from_cookie)):
    return templates.TemplateResponse(request, "backup.html", {"user": user})
