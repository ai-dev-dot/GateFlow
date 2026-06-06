"""Tests for the HTML page routes (/pages/*).

Verifies:
- Public pages are accessible without auth
- Protected pages return 401 without cookie
- Admin-only pages reject non-admin users
- All pages return 200 with valid cookie
- Login POST sets cookie and redirects
- Logout clears cookie
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.session import COOKIE_NAME
from app.main import app


@pytest_asyncio.fixture
async def client(db_session):
    """HTTPX async client bound to the FastAPI app with test DB."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[__import__("app.database", fromlist=["get_db"]).get_db] = (
        _override_get_db
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_client_with_cookie(client: AsyncClient, user):
    """Return a new client with cookies set on the instance."""
    token = _make_token(user)
    client.cookies.set(COOKIE_NAME, token)
    return client


def _make_token(user) -> str:
    """Generate a JWT token for testing cookie auth."""
    from app.config import get_settings
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    role_name = user.role.name if hasattr(user.role, 'name') else str(user.role)
    return jwt.encode(
        {"sub": str(user.id), "username": user.username, "role": role_name, "exp": expire},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )


# --- Public page ---

@pytest.mark.asyncio
async def test_login_page_accessible(client: AsyncClient):
    resp = await client.get("/pages/login")
    assert resp.status_code == 200
    assert "登录" in resp.text


# --- Protected pages without auth ---

@pytest.mark.asyncio
async def test_chat_page_without_auth_returns_401(client: AsyncClient):
    resp = await client.get("/pages/chat")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_page_without_auth_returns_401(client: AsyncClient):
    resp = await client.get("/pages/dashboard")
    assert resp.status_code == 401


# --- Protected pages with admin cookie ---

@pytest.mark.asyncio
async def test_all_pages_accessible_with_admin_cookie(client: AsyncClient, admin_user):
    _make_client_with_cookie(client, admin_user)

    pages = [
        "/pages/chat",
        "/pages/dashboard",
        "/pages/gateway",
        "/pages/users",
        "/pages/audit",
        "/pages/usage",
        "/pages/api-keys",
        "/pages/backup",
    ]
    for page in pages:
        resp = await client.get(page)
        assert resp.status_code == 200, f"{page} returned {resp.status_code}"


# --- Admin-only pages reject normal user ---

@pytest.mark.asyncio
async def test_admin_pages_reject_normal_user(client: AsyncClient, test_user):
    _make_client_with_cookie(client, test_user)

    admin_pages = [
        "/pages/dashboard",
        "/pages/gateway",
        "/pages/users",
        "/pages/audit",
        "/pages/usage",
        "/pages/api-keys",
        "/pages/backup",
    ]
    for page in admin_pages:
        resp = await client.get(page)
        assert resp.status_code == 403, f"{page} should be 403 for normal user, got {resp.status_code}"


# --- Normal user can access chat ---

@pytest.mark.asyncio
async def test_normal_user_can_access_chat(client: AsyncClient, test_user):
    _make_client_with_cookie(client, test_user)
    resp = await client.get("/pages/chat")
    assert resp.status_code == 200


# --- Login POST ---

@pytest.mark.asyncio
async def test_login_post_success(client: AsyncClient, db_session: AsyncSession):
    from app.models.user import User, Role, Department
    from app.utils.security import get_password_hash

    dept = Department(name="Test")
    db_session.add(dept)
    role = Role(name="admin", permissions={})
    db_session.add(role)
    await db_session.flush()
    user = User(username="loginuser", email="login@test", is_active=True, department_id=dept.id, role_id=role.id,
                hashed_password=get_password_hash("testpass123"))
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/pages/login",
        data={"username": "loginuser", "password": "testpass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert COOKIE_NAME in resp.cookies


@pytest.mark.asyncio
async def test_login_post_wrong_password(client: AsyncClient, db_session: AsyncSession):
    from app.models.user import User, Role, Department
    from app.utils.security import get_password_hash

    dept = Department(name="Test")
    db_session.add(dept)
    role = Role(name="admin", permissions={})
    db_session.add(role)
    await db_session.flush()
    user = User(username="loginuser2", email="login2@test", is_active=True, department_id=dept.id, role_id=role.id,
                hashed_password=get_password_hash("correctpass"))
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/pages/login",
        data={"username": "loginuser2", "password": "wrongpass"},
    )
    assert resp.status_code == 200
    assert "用户名或密码错误" in resp.text


# --- Logout ---

@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient, test_user):
    _make_client_with_cookie(client, test_user)
    resp = await client.get("/pages/logout", follow_redirects=False)
    assert resp.status_code == 303
    set_cookie = resp.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie


# --- Root redirect ---

@pytest.mark.asyncio
async def test_root_redirects_to_login_when_not_logged_in(client: AsyncClient):
    """未登录时根路径应跳转到登录页"""
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 302, 303)
    assert "/pages/login" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_root_redirects_to_chat_when_logged_in(client: AsyncClient):
    """已登录时根路径应跳转到首页（chat）"""
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import get_settings

    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    token = jwt.encode(
        {"sub": "917a6ad5-a8ab-4f6e-b531-a9c9bb629bbe", "username": "admin", "role": "admin", "exp": expire},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    resp = await client.get("/", follow_redirects=False, cookies={"gf_session": token})
    assert resp.status_code in (307, 302, 303)
    assert "/pages/chat" in resp.headers.get("location", "")
