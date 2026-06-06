"""Tests for the backup router (4 endpoints, all admin-gated).

Covers:
- 401 when no auth
- 403 when non-admin
- 200 paths for all 4 endpoints
- 422 for empty backup_dir in PUT
- 501 for /run on SQLite (test env)
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User
from app.services import backup_service


@pytest_asyncio.fixture
async def client(db_session):
    """HTTPX async client with the get_db dependency overridden."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[__import__("app.database", fromlist=["get_db"]).get_db] = (
        _override_get_db
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _override_user(target_user: User):
    async def _override():
        return target_user

    return _override


def _set_current_user(user: User):
    app.dependency_overrides[
        __import__("app.middleware.auth_middleware", fromlist=["get_current_user"]).get_current_user
    ] = lambda u=user: _sync_return(u)


def _sync_return(user):
    # The override itself is a sync function that returns a User; FastAPI
    # accepts both sync and async dependency callables.
    return user


# ---------- 401 / 403 / 200 paths ----------


@pytest.mark.asyncio
async def test_get_config_requires_auth(client):
    """No auth header → 401."""
    resp = await client.get("/api/backup/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_config_requires_admin(client, test_user):
    """Non-admin user → 403."""
    _set_current_user(test_user)
    resp = await client.get("/api/backup/config")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_config_returns_defaults_for_fresh_db(client, admin_user):
    """Admin → 200 with default values."""
    _set_current_user(admin_user)
    resp = await client.get("/api/backup/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["backup_dir"] == "./backups"
    assert body["backup_include_audit_logs"] is False
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_update_config_requires_admin(client, test_user):
    _set_current_user(test_user)
    resp = await client.put("/api/backup/config", json={"backup_dir": "/tmp/x"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_config_persists(client, admin_user):
    _set_current_user(admin_user)
    resp = await client.put(
        "/api/backup/config",
        json={"backup_dir": "/var/bu", "backup_include_audit_logs": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["backup_dir"] == "/var/bu"
    assert body["backup_include_audit_logs"] is True
    # follow-up GET
    resp2 = await client.get("/api/backup/config")
    assert resp2.json()["backup_dir"] == "/var/bu"


@pytest.mark.asyncio
async def test_update_config_rejects_empty_backup_dir(client, admin_user):
    _set_current_user(admin_user)
    resp = await client.put("/api/backup/config", json={"backup_dir": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_backup_requires_admin(client, test_user):
    _set_current_user(test_user)
    resp = await client.post("/api/backup/run")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_run_backup_returns_501_on_sqlite(client, admin_user, monkeypatch):
    """Test env uses sqlite (or whatever non-PG) → /run returns 501 with clear detail."""
    _set_current_user(admin_user)
    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: False)
    resp = await client.post("/api/backup/run")
    assert resp.status_code == 501
    assert "PostgreSQL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_backups_requires_admin(client, test_user):
    _set_current_user(test_user)
    resp = await client.get("/api/backup/history")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_backups_returns_empty_when_no_dir(client, admin_user, tmp_path, db_session):
    """Fresh admin → /history returns [] (no .sql files)."""
    from app.services.backup_service import update_config

    _set_current_user(admin_user)
    await update_config(db_session, backup_dir=str(tmp_path / "does_not_exist"))
    resp = await client.get("/api/backup/history")
    assert resp.status_code == 200
    assert resp.json() == []
