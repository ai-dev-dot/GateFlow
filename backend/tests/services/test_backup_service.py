"""Unit tests for backup_service.

Covers:
- Lazy init of SystemConfig singleton (get_config)
- Partial / full update of SystemConfig (update_config), incl. pg_dump_path
- Validation: empty / whitespace backup_dir rejected
- run_backup SQLite path: clean error, no subprocess call
- run_backup PG path: correct argv + env, exclude flag toggles, rc propagation
- run_backup creates backup_dir if missing
- run_backup pg_dump_path unset → clear error
- run_backup pg_dump_path points at non-existent file → clear error
- list_backups: sorted desc, .sql only, missing dir → []
"""

import os
import subprocess
from unittest.mock import MagicMock, patch

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


def _create_fake_pg_dump(tmp_path) -> str:
    """Write a tiny executable-shaped file and return its path.

    We never actually run it (subprocess.run is mocked), so any file
    that passes os.path.isfile works. Use a real file rather than
    monkeypatching isfile so the service's check is end-to-end real.
    """
    fake = tmp_path / "fake_pg_dump"
    fake.write_bytes(b"#!/bin/sh\necho fake\n")
    if os.name != "nt":
        fake.chmod(0o755)
    return str(fake)


# ---------- get_config ----------


@pytest.mark.asyncio
async def test_get_config_creates_default_if_missing(db_session):
    """Empty DB → get_config inserts row id=1 with defaults."""
    cfg = await get_config(db_session)
    assert cfg.id == 1
    assert cfg.backup_dir == DEFAULT_BACKUP_DIR
    assert cfg.backup_include_audit_logs == DEFAULT_BACKUP_INCLUDE_AUDIT_LOGS
    assert cfg.pg_dump_path is None  # admin must opt in
    assert cfg.updated_at is not None


@pytest.mark.asyncio
async def test_get_config_returns_existing_row(db_session):
    """Pre-seeded row → get_config returns the same row, no second insert."""
    cfg = await get_config(db_session)
    cfg.backup_dir = "/tmp/already-set"
    cfg.backup_include_audit_logs = True
    cfg.pg_dump_path = "/usr/bin/pg_dump"
    await db_session.commit()

    again = await get_config(db_session)
    assert again.backup_dir == "/tmp/already-set"
    assert again.backup_include_audit_logs is True
    assert again.pg_dump_path == "/usr/bin/pg_dump"


# ---------- update_config ----------


@pytest.mark.asyncio
async def test_update_config_persists_values(db_session):
    """All three fields updated; read-back matches; updated_at refreshed."""
    await get_config(db_session)
    before = (await get_config(db_session)).updated_at

    updated = await update_config(
        db_session,
        backup_dir="/var/backups/gateflow",
        backup_include_audit_logs=True,
        pg_dump_path="/usr/bin/pg_dump",
    )
    assert updated.backup_dir == "/var/backups/gateflow"
    assert updated.backup_include_audit_logs is True
    assert updated.pg_dump_path == "/usr/bin/pg_dump"
    assert updated.updated_at >= before

    again = await get_config(db_session)
    assert again.backup_dir == "/var/backups/gateflow"
    assert again.backup_include_audit_logs is True
    assert again.pg_dump_path == "/usr/bin/pg_dump"


@pytest.mark.asyncio
async def test_update_config_partial_update_keeps_other_field(db_session):
    """Only one field supplied → other fields unchanged."""
    await update_config(
        db_session,
        backup_dir="/srv/bu",
        backup_include_audit_logs=False,
        pg_dump_path="/usr/bin/pg_dump",
    )
    again = await update_config(db_session, backup_dir="/srv/bu2")
    assert again.backup_dir == "/srv/bu2"
    assert again.backup_include_audit_logs is False
    assert again.pg_dump_path == "/usr/bin/pg_dump"


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


@pytest.mark.asyncio
async def test_update_config_pg_dump_path_can_be_cleared_to_none(db_session):
    """Passing None is a no-op (existing path kept). To clear, the router
    schema maps "" → None, so the service treats both as "don't touch"."""
    await update_config(db_session, pg_dump_path="/old/path")
    # Calling with None leaves the existing value alone
    again = await update_config(db_session, pg_dump_path=None)
    assert again.pg_dump_path == "/old/path"


# ---------- run_backup: SQLite path ----------


@pytest.mark.asyncio
async def test_run_backup_skipped_on_sqlite(db_session, monkeypatch, tmp_path):
    """When DATABASE_URL is not PG, service must raise BackupNotSupportedError
    and NOT call pg_dump. The check is independent of test env (the local
    .env here is PG, so we force the URL check to fail)."""
    await get_config(db_session)
    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: False)

    with (
        patch.object(
            backup_service.subprocess,
            "run",
            new=MagicMock(side_effect=AssertionError("must not be called")),
        ),
        pytest.raises(BackupNotSupportedError, match="PostgreSQL"),
    ):
        await run_backup(db_session)


# ---------- run_backup: pg_dump_path missing / invalid ----------


@pytest.mark.asyncio
async def test_run_backup_no_pg_dump_path_raises(db_session, monkeypatch, tmp_path):
    """pg_dump_path is None → BackupFailedError with admin-friendly message."""
    await update_config(db_session, backup_dir=str(tmp_path), backup_include_audit_logs=True)
    # pg_dump_path stays None (admin never set it)

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)

    with (
        patch.object(
            backup_service.subprocess,
            "run",
            new=MagicMock(side_effect=AssertionError("must not be called")),
        ),
        pytest.raises(BackupFailedError, match="pg_dump 路径未设置"),
    ):
        await run_backup(db_session)


@pytest.mark.asyncio
async def test_run_backup_pg_dump_path_nonexistent_raises(db_session, monkeypatch, tmp_path):
    """pg_dump_path points at a file that doesn't exist → BackupFailedError."""
    await update_config(
        db_session,
        backup_dir=str(tmp_path),
        backup_include_audit_logs=True,
        pg_dump_path="/no/such/file/pg_dump",
    )

    monkeypatch.setattr(backup_service, "is_postgres_url", lambda url: True)

    with (
        patch.object(
            backup_service.subprocess,
            "run",
            new=MagicMock(side_effect=AssertionError("must not be called")),
        ),
        pytest.raises(BackupFailedError, match="pg_dump 路径无效"),
    ):
        await run_backup(db_session)


# ---------- run_backup: PG path (mocked subprocess) ----------


@pytest.mark.asyncio
async def test_run_backup_pg_path_invokes_pg_dump(db_session, monkeypatch, tmp_path):
    """Mock subprocess.run; verify argv + env + result dict shape + file written."""
    pg_dump_bin = _create_fake_pg_dump(tmp_path)
    await update_config(
        db_session,
        backup_dir=str(tmp_path),
        backup_include_audit_logs=True,
        pg_dump_path=pg_dump_bin,
    )

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

    captured = {}

    def fake_run(*args, **kwargs):
        # service calls subprocess.run(argv, ...) — the first positional arg
        # is the program+args list as a whole. Mirror that signature.
        program_argv = args[0] if args else kwargs.get("args", [])
        captured["argv"] = program_argv
        captured["env"] = kwargs.get("env")
        # Write a small dummy file at the path pg_dump would have written.
        out_idx = program_argv.index("-f") + 1
        out_path = program_argv[out_idx]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("-- PG dump\nCREATE TABLE users (\n);\nCREATE TABLE roles (\n);\n")
        return subprocess.CompletedProcess(args=program_argv, returncode=0, stderr=b"")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)

    result = await run_backup(db_session)
    assert result["filename"].startswith("gateflow_") and result["filename"].endswith(".sql")
    assert result["size_bytes"] > 0
    assert result["duration_ms"] >= 0
    assert result["tables_dumped"] == 2  # users + roles
    assert result["excluded_audit_logs"] is False
    # argv checks
    argv = captured["argv"]
    assert argv[0] == pg_dump_bin
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
    pg_dump_bin = _create_fake_pg_dump(tmp_path)
    await update_config(
        db_session,
        backup_dir=str(tmp_path),
        backup_include_audit_logs=False,
        pg_dump_path=pg_dump_bin,
    )

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

    def fake_run(*args, **kwargs):
        program_argv = args[0] if args else kwargs.get("args", [])
        captured["argv"] = program_argv
        out_idx = program_argv.index("-f") + 1
        with open(program_argv[out_idx], "w", encoding="utf-8") as f:
            f.write("-- PG dump\n")
        return subprocess.CompletedProcess(args=program_argv, returncode=0, stderr=b"")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)

    result = await run_backup(db_session)
    assert result["excluded_audit_logs"] is True
    assert any(f"--exclude-table-data={EXCLUDED_AUDIT_TABLE}" == a for a in captured["argv"])


@pytest.mark.asyncio
async def test_run_backup_propagates_nonzero_returncode(db_session, monkeypatch, tmp_path):
    """pg_dump returns 1 → service raises BackupFailedError + deletes partial file."""
    pg_dump_bin = _create_fake_pg_dump(tmp_path)
    await update_config(
        db_session,
        backup_dir=str(tmp_path),
        backup_include_audit_logs=True,
        pg_dump_path=pg_dump_bin,
    )

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

    def fake_run(*args, **kwargs):
        program_argv = args[0] if args else kwargs.get("args", [])
        out_idx = program_argv.index("-f") + 1
        out_path_holder["p"] = program_argv[out_idx]
        # pg_dump would have written something before failing
        with open(program_argv[out_idx], "w", encoding="utf-8") as f:
            f.write("partial content\n")
        return subprocess.CompletedProcess(
            args=program_argv, returncode=1, stderr=b"permission denied to table x"
        )

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)

    with pytest.raises(BackupFailedError) as exc_info:
        await run_backup(db_session)
    assert exc_info.value.returncode == 1
    assert "permission denied" in exc_info.value.stderr
    # Partial file should be cleaned up
    assert not os.path.exists(out_path_holder["p"])


@pytest.mark.asyncio
async def test_run_backup_handles_missing_pg_dump_at_subprocess(db_session, monkeypatch, tmp_path):
    """Race: path passed os.path.isfile but subprocess can't find it
    (e.g. admin deleted the file between the check and the spawn)."""
    pg_dump_bin = _create_fake_pg_dump(tmp_path)
    await update_config(
        db_session,
        backup_dir=str(tmp_path),
        backup_include_audit_logs=True,
        pg_dump_path=pg_dump_bin,
    )

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

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("No such file or directory")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)

    with pytest.raises(BackupFailedError, match="pg_dump 路径已失效"):
        await run_backup(db_session)


@pytest.mark.asyncio
async def test_run_backup_creates_backup_dir_if_missing(db_session, monkeypatch, tmp_path):
    """backup_dir points at a non-existent path → service makedirs it."""
    pg_dump_bin = _create_fake_pg_dump(tmp_path)
    new_dir = tmp_path / "newly_created_subdir"
    assert not new_dir.exists()
    await update_config(
        db_session,
        backup_dir=str(new_dir),
        backup_include_audit_logs=True,
        pg_dump_path=pg_dump_bin,
    )

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

    def fake_run(*args, **kwargs):
        program_argv = args[0] if args else kwargs.get("args", [])
        out_idx = program_argv.index("-f") + 1
        with open(program_argv[out_idx], "w", encoding="utf-8") as f:
            f.write("dump\n")
        return subprocess.CompletedProcess(args=program_argv, returncode=0, stderr=b"")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)

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
