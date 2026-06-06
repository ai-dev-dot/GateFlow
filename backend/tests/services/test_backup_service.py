"""Unit tests for backup_service.

Covers:
- Lazy init of SystemConfig singleton (get_config)
- Partial / full update of SystemConfig (update_config)
- Validation: empty / whitespace backup_dir rejected
- run_backup SQLite path: clean error, no subprocess call
- run_backup PG path: correct argv + env, exclude flag toggles, rc propagation
- run_backup creates backup_dir if missing
- list_backups: sorted desc, .sql only, missing dir → []
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import backup_service
from app.services.backup_service import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_BACKUP_INCLUDE_AUDIT_LOGS,
    EXCLUDED_AUDIT_TABLE,
    BackupFailedError,
    BackupNotSupportedError,
    get_config,
    list_backups,
    parse_pg_url,
    run_backup,
    update_config,
)

# ---------- helpers ----------


def _make_completed_proc(returncode: int = 0, stderr: bytes = b""):
    """Build an object that mimics the return of create_subprocess_exec + communicate."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    return proc


# ---------- get_config ----------


@pytest.mark.asyncio
async def test_get_config_creates_default_if_missing(db_session):
    """Empty DB → get_config inserts row id=1 with defaults."""
    cfg = await get_config(db_session)
    assert cfg.id == 1
    assert cfg.backup_dir == DEFAULT_BACKUP_DIR
    assert cfg.backup_include_audit_logs == DEFAULT_BACKUP_INCLUDE_AUDIT_LOGS
    assert cfg.updated_at is not None


@pytest.mark.asyncio
async def test_get_config_returns_existing_row(db_session):
    """Pre-seeded row → get_config returns the same row, no second insert."""
    cfg = await get_config(db_session)
    cfg.backup_dir = "/tmp/already-set"
    cfg.backup_include_audit_logs = True
    await db_session.commit()

    again = await get_config(db_session)
    assert again.backup_dir == "/tmp/already-set"
    assert again.backup_include_audit_logs is True


# ---------- update_config ----------


@pytest.mark.asyncio
async def test_update_config_persists_values(db_session):
    """Both fields updated; read-back matches; updated_at refreshed."""
    await get_config(db_session)
    before = (await get_config(db_session)).updated_at

    updated = await update_config(
        db_session,
        backup_dir="/var/backups/gateflow",
        backup_include_audit_logs=True,
    )
    assert updated.backup_dir == "/var/backups/gateflow"
    assert updated.backup_include_audit_logs is True
    assert updated.updated_at >= before

    again = await get_config(db_session)
    assert again.backup_dir == "/var/backups/gateflow"
    assert again.backup_include_audit_logs is True


@pytest.mark.asyncio
async def test_update_config_partial_update_keeps_other_field(db_session):
    """Only one field supplied → other field unchanged."""
    await update_config(db_session, backup_dir="/srv/bu", backup_include_audit_logs=False)
    again = await update_config(db_session, backup_dir="/srv/bu2")
    assert again.backup_dir == "/srv/bu2"
    assert again.backup_include_audit_logs is False  # unchanged


@pytest.mark.asyncio
async def test_update_config_rejects_empty_backup_dir(db_session):
    with pytest.raises(ValueError, match="must not be empty"):
        await update_config(db_session, backup_dir="")
    with pytest.raises(ValueError, match="must not be empty"):
        await update_config(db_session, backup_dir="   ")


@pytest.mark.asyncio
async def test_update_config_strips_whitespace(db_session):
    updated = await update_config(db_session, backup_dir="  /srv/bu  ")
    assert updated.backup_dir == "/srv/bu"


# ---------- run_backup: SQLite path ----------


@pytest.mark.asyncio
async def test_run_backup_skipped_on_sqlite(db_session, monkeypatch):
    """When DATABASE_URL is not PG, service must raise BackupNotSupportedError
    and NOT call pg_dump. The check is independent of test env (the local
    .env here is PG, so we force the URL check to fail)."""
    await get_config(db_session)
    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: False)

    with (
        patch.object(
            backup_service.asyncio,
            "create_subprocess_exec",
            new=AsyncMock(side_effect=AssertionError("must not be called")),
        ),
        pytest.raises(BackupNotSupportedError, match="PostgreSQL"),
    ):
        await run_backup(db_session)


# ---------- run_backup: PG path (mocked subprocess) ----------


@pytest.mark.asyncio
async def test_run_backup_pg_path_invokes_pg_dump(db_session, monkeypatch, tmp_path):
    """Mock subprocess; verify argv + env + result dict shape + file written."""
    await update_config(db_session, backup_dir=str(tmp_path), backup_include_audit_logs=True)

    # Force the URL check to pass (test env is SQLite)
    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)
    monkeypatch.setattr(
        backup_service,
        "parse_pg_url",
        lambda url: {
            "user": "alice",
            "password": "secret",
            "host": "db.local",
            "port": "5432",
            "database": "gateflow",
        },
    )

    out_path = None
    captured = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        # Write a small dummy file at the path pg_dump would have written.
        # argv layout: [pg_dump, -h, host, -p, port, -U, user, -d, db, -f, path, ...]
        out_idx = argv.index("-f") + 1
        nonlocal out_path
        out_path = argv[out_idx]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("-- PG dump\nCREATE TABLE users (\n);\nCREATE TABLE roles (\n);\n")
        return _make_completed_proc(returncode=0)

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", fake_exec)

    result = await run_backup(db_session)
    assert result["filename"].startswith("gateflow_") and result["filename"].endswith(".sql")
    assert result["size_bytes"] > 0
    assert result["duration_ms"] >= 0
    assert result["tables_dumped"] == 2  # users + roles
    assert result["excluded_audit_logs"] is False
    assert result["path"] == out_path
    # argv checks
    argv = captured["argv"]
    assert argv[0] == "pg_dump"
    assert "-h" in argv and "db.local" in argv
    assert "-U" in argv and "alice" in argv
    assert "gateflow" in argv  # db name
    assert EXCLUDED_AUDIT_TABLE not in " ".join(argv)  # include mode
    # env: PGPASSWORD should be set
    assert captured["env"] is not None
    assert captured["env"].get("PGPASSWORD") == "secret"


@pytest.mark.asyncio
async def test_run_backup_excludes_audit_logs_by_default(db_session, monkeypatch, tmp_path):
    """backup_include_audit_logs=False → argv contains --exclude-table-data=public.audit_logs."""
    await update_config(db_session, backup_dir=str(tmp_path), backup_include_audit_logs=False)

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)
    monkeypatch.setattr(
        backup_service,
        "parse_pg_url",
        lambda url: {
            "user": "u",
            "password": "p",
            "host": "h",
            "port": "5432",
            "database": "d",
        },
    )

    captured = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = argv
        out_idx = argv.index("-f") + 1
        with open(argv[out_idx], "w", encoding="utf-8") as f:
            f.write("-- PG dump\n")
        return _make_completed_proc(returncode=0)

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", fake_exec)

    result = await run_backup(db_session)
    assert result["excluded_audit_logs"] is True
    assert any(f"--exclude-table-data={EXCLUDED_AUDIT_TABLE}" == a for a in captured["argv"])


@pytest.mark.asyncio
async def test_run_backup_propagates_nonzero_returncode(db_session, monkeypatch, tmp_path):
    """pg_dump returns 1 → service raises BackupFailedError + deletes partial file."""
    await update_config(db_session, backup_dir=str(tmp_path), backup_include_audit_logs=True)

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)
    monkeypatch.setattr(
        backup_service,
        "parse_pg_url",
        lambda url: {
            "user": "u",
            "password": "p",
            "host": "h",
            "port": "5432",
            "database": "d",
        },
    )

    out_path_holder = {}

    async def fake_exec(*argv, **kwargs):
        out_idx = argv.index("-f") + 1
        out_path_holder["p"] = argv[out_idx]
        # pg_dump would have written something before failing
        with open(argv[out_idx], "w", encoding="utf-8") as f:
            f.write("partial content\n")
        return _make_completed_proc(returncode=1, stderr=b"permission denied to table x")

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(BackupFailedError) as exc_info:
        await run_backup(db_session)
    assert exc_info.value.returncode == 1
    assert "permission denied" in exc_info.value.stderr
    # Partial file should be cleaned up
    assert not os.path.exists(out_path_holder["p"])


@pytest.mark.asyncio
async def test_run_backup_handles_missing_pg_dump_binary(db_session, monkeypatch, tmp_path):
    """FileNotFoundError on create_subprocess_exec → BackupFailedError."""
    await update_config(db_session, backup_dir=str(tmp_path), backup_include_audit_logs=True)

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)
    monkeypatch.setattr(
        backup_service,
        "parse_pg_url",
        lambda url: {
            "user": "u",
            "password": "p",
            "host": "h",
            "port": "5432",
            "database": "d",
        },
    )

    async def fake_exec(*args, **kwargs):
        raise FileNotFoundError("No such file or directory: 'pg_dump'")

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(BackupFailedError, match="pg_dump binary not found"):
        await run_backup(db_session)


@pytest.mark.asyncio
async def test_run_backup_creates_backup_dir_if_missing(db_session, monkeypatch, tmp_path):
    """backup_dir points at a non-existent path → service makedirs it."""
    new_dir = tmp_path / "newly_created_subdir"
    assert not new_dir.exists()
    await update_config(db_session, backup_dir=str(new_dir), backup_include_audit_logs=True)

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)
    monkeypatch.setattr(
        backup_service,
        "parse_pg_url",
        lambda url: {
            "user": "u",
            "password": "p",
            "host": "h",
            "port": "5432",
            "database": "d",
        },
    )

    async def fake_exec(*argv, **kwargs):
        out_idx = argv.index("-f") + 1
        with open(argv[out_idx], "w", encoding="utf-8") as f:
            f.write("dump\n")
        return _make_completed_proc(returncode=0)

    monkeypatch.setattr(backup_service.asyncio, "create_subprocess_exec", fake_exec)

    await run_backup(db_session)
    assert new_dir.is_dir()


# ---------- list_backups ----------


@pytest.mark.asyncio
async def test_list_backups_returns_sql_files_sorted_desc(db_session, tmp_path):
    """Create 2 .sql files (different mtimes) and 1 .txt → return 2 .sql sorted desc."""
    # Create files with controlled mtimes
    a = tmp_path / "a.sql"
    b = tmp_path / "b.sql"
    c = tmp_path / "c.txt"  # should be ignored
    a.write_text("old")
    b.write_text("new")
    c.write_text("ignore me")
    # Set mtimes explicitly
    os.utime(a, (1000, 1000))
    os.utime(b, (2000, 2000))

    await update_config(db_session, backup_dir=str(tmp_path))
    files = await list_backups(db_session)
    filenames = [f["filename"] for f in files]
    assert filenames == ["b.sql", "a.sql"]  # newer first
    # c.txt excluded
    assert all(f["filename"].endswith(".sql") for f in files)
    # size_bytes correct
    assert {f["filename"]: f["size_bytes"] for f in files} == {
        "a.sql": 3,
        "b.sql": 3,
    }


@pytest.mark.asyncio
async def test_list_backups_handles_missing_dir_gracefully(db_session, tmp_path):
    """backup_dir doesn't exist → return [] (don't raise)."""
    nonexistent = tmp_path / "does_not_exist"
    await update_config(db_session, backup_dir=str(nonexistent))
    files = await list_backups(db_session)
    assert files == []


# ---------- parse_pg_url ----------


def test_parse_pg_url_basic_postgres_scheme():
    parsed = parse_pg_url("postgresql://user:pass@db.example.com:5433/mydb")
    assert parsed["user"] == "user"
    assert parsed["password"] == "pass"
    assert parsed["host"] == "db.example.com"
    assert parsed["port"] == "5433"
    assert parsed["database"] == "mydb"


def test_parse_pg_url_asyncpg_scheme():
    parsed = parse_pg_url("postgresql+asyncpg://u:p@h/d")
    assert parsed["user"] == "u"
    assert parsed["host"] == "h"
    assert parsed["database"] == "d"
    # default port
    assert parsed["port"] == "5432"


def test_parse_pg_url_invalid_raises_backup_failed():
    with pytest.raises(BackupFailedError):
        parse_pg_url("not a url at all")
