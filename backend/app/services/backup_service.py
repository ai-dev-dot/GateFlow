"""Database backup service.

Shells out to `pg_dump` to produce a SQL dump file in the configured
backup directory. The default policy EXCLUDES the audit_logs DATA
(`--exclude-table-data=public.audit_logs`) — the schema is kept but the
rows are skipped because audit_logs can be huge in production and is
explicitly designed as a leak-and-trim artifact (see
AUDIT_LOG_RETENTION_DAYS in config).

PG-only: SQLite (used in tests) raises BackupNotSupportedError cleanly
so the endpoint can return 501 instead of crashing.

pg_dump path: the admin sets it explicitly in the /backup settings UI
(``system_config.pg_dump_path``). The service does NOT auto-discover —
admin owns the choice. If the path is missing or doesn't point to an
existing file, ``run_backup`` raises ``BackupFailedError`` with a clear
message and the router surfaces it to the UI.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import glob
import logging
import os
import subprocess
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

# Default singleton row values (used when SystemConfig is first created).
DEFAULT_BACKUP_DIR = "./backups"
DEFAULT_BACKUP_INCLUDE_AUDIT_LOGS = False

# Table excluded by default from the dump DATA (rows). Schema is preserved
# so a restore still creates the table; the partial index too (PG only).
EXCLUDED_AUDIT_TABLE = "public.audit_logs"


class BackupNotSupportedError(Exception):
    """Raised when run_backup is called against a non-PostgreSQL DB."""


class BackupFailedError(Exception):
    """Raised when pg_dump returns non-zero, the binary path is missing,
    or the configured path doesn't point to a real file. Carries stderr
    for diagnostics (may be empty if the failure is pre-subprocess).
    """

    def __init__(self, message: str, *, returncode: int, stderr: str):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


# ---------- helpers ----------


def is_postgres_url(url: str) -> bool:
    return "postgresql" in url or "postgres+asyncpg" in url


def parse_pg_url(url: str) -> dict[str, str]:
    """Extract user/password/host/port/dbname from a PostgreSQL URL.

    Accepts both 'postgresql://' and 'postgresql+asyncpg://' schemes.
    Raises BackupFailedError on parse failure (caller maps to 500).
    """
    try:
        # strip the asyncpg driver suffix if present
        normalized = url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(normalized)
        if not parsed.hostname or not parsed.path.lstrip("/"):
            raise ValueError("missing host or database name")
        return {
            "user": parsed.username or "",
            "password": parsed.password or "",
            "host": parsed.hostname,
            "port": str(parsed.port or 5432),
            "database": parsed.path.lstrip("/"),
        }
    except Exception as e:  # noqa: BLE001
        raise BackupFailedError(
            f"Cannot parse DATABASE_URL: {e}", returncode=-1, stderr=str(e)
        ) from e


# ---------- config CRUD ----------


async def get_config(db: AsyncSession) -> SystemConfig:
    """Return the singleton SystemConfig row, creating it with defaults
    on first call (lazy init — no lifespan change needed).
    """
    result = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
    config = result.scalar_one_or_none()
    if config is not None:
        return config

    config = SystemConfig(
        id=1,
        backup_dir=DEFAULT_BACKUP_DIR,
        backup_include_audit_logs=DEFAULT_BACKUP_INCLUDE_AUDIT_LOGS,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def update_config(
    db: AsyncSession,
    *,
    backup_dir: str | None = None,
    backup_include_audit_logs: bool | None = None,
    pg_dump_path: str | None = None,
) -> SystemConfig:
    """Update the singleton config. All fields optional (partial update).

    To CLEAR ``pg_dump_path``, pass an empty string. The router schema
    maps "" → None before reaching this function.
    """
    config = await get_config(db)

    if backup_dir is not None:
        stripped = backup_dir.strip()
        if not stripped:
            raise ValueError("backup_dir must not be empty")
        config.backup_dir = stripped

    if backup_include_audit_logs is not None:
        config.backup_include_audit_logs = backup_include_audit_logs

    if pg_dump_path is not None:
        # Schema layer has already mapped "" → None and stripped whitespace.
        # We just assign — the run_backup check catches "file doesn't exist"
        # at call time, not at config-save time, so admin can save a path
        # before the file is reachable (e.g. before a service restart).
        config.pg_dump_path = pg_dump_path

    await db.commit()
    await db.refresh(config)
    return config


# ---------- backup execution ----------


async def run_backup(db: AsyncSession) -> dict:
    """Run pg_dump and write a timestamped .sql file to backup_dir.

    Returns a dict suitable for BackupResultResponse.
    Raises:
        BackupNotSupportedError: DATABASE_URL is not PG.
        BackupFailedError: pg_dump path is unset, file missing, or
            pg_dump returns non-zero.
    """
    settings = get_settings()
    if not is_postgres_url(settings.DATABASE_URL):
        raise BackupNotSupportedError(
            "Database backup is only supported on PostgreSQL " "(current: {})".format(
                settings.DATABASE_URL.split("://", 1)[0]
            )
        )

    config = await get_config(db)
    backup_dir = config.backup_dir
    os.makedirs(backup_dir, exist_ok=True)

    # Resolve pg_dump binary from the admin-configured path. We do NOT
    # auto-search PATH or any hardcoded locations — admin owns the choice.
    if not config.pg_dump_path:
        raise BackupFailedError(
            "pg_dump 路径未设置。请先在'备份设置'中填写 pg_dump 可执行文件的绝对路径"
            "（例如 E:\\PostgreSQL\\18\\bin\\pg_dump.exe）。",
            returncode=-1,
            stderr="",
        )
    if not os.path.isfile(config.pg_dump_path):
        raise BackupFailedError(
            f"pg_dump 路径无效：'{config.pg_dump_path}' 不存在或不是文件。"
            "请到'备份设置'中检查并修正。",
            returncode=-1,
            stderr="",
        )

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"gateflow_{timestamp}.sql"
    out_path = os.path.join(backup_dir, filename)

    pg = parse_pg_url(settings.DATABASE_URL)

    argv: list[str] = [
        config.pg_dump_path,
        "-h",
        pg["host"],
        "-p",
        pg["port"],
        "-U",
        pg["user"],
        "-d",
        pg["database"],
        "-f",
        out_path,
        "--no-owner",
        "--no-privileges",
    ]
    if not config.backup_include_audit_logs:
        # Skip just the DATA of audit_logs (schema + indexes preserved).
        # Use --exclude-table-data (table-name form) which matches the
        # actual table even with the default 'public' schema search path.
        argv.append(f"--exclude-table-data={EXCLUDED_AUDIT_TABLE}")

    env = {**os.environ, "PGPASSWORD": pg["password"]} if pg["password"] else None

    start = datetime.datetime.now()
    # Use subprocess.run in a worker thread (asyncio.to_thread) rather than
    # asyncio.create_subprocess_exec. The asyncio subprocess transport is
    # NotImplementedError on Windows' default ProactorEventLoop, so a sync
    # subprocess.run + to_thread is the cross-platform-safe option.
    try:
        completed = await asyncio.to_thread(
            lambda: subprocess.run(
                argv,
                capture_output=True,
                env=env,
                check=False,
            )
        )
    except FileNotFoundError as e:
        # Race: path passed the os.path.isfile() check but the binary
        # was removed before subprocess spawned (e.g. admin edit).
        raise BackupFailedError(
            f"pg_dump 路径已失效：'{config.pg_dump_path}' 找不到。",
            returncode=-1,
            stderr=str(e),
        ) from e

    duration_ms = int((datetime.datetime.now() - start).total_seconds() * 1000)
    stderr_text = (completed.stderr or b"").decode("utf-8", errors="replace")

    if completed.returncode != 0:
        # Best-effort cleanup of any partial file pg_dump may have left.
        if os.path.exists(out_path):
            with contextlib.suppress(OSError):
                os.unlink(out_path)
        raise BackupFailedError(
            f"pg_dump failed (rc={completed.returncode})",
            returncode=completed.returncode,
            stderr=stderr_text,
        )

    # Count tables dumped by scanning the .sql file for "CREATE TABLE" lines.
    # This is a heuristic — pg_dump doesn't return a count directly. Excludes
    # partitioned children and the standard "ALTER TABLE" follow-ups.
    tables_dumped = 0
    try:
        with open(out_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("CREATE TABLE") and " AS " not in line:
                    tables_dumped += 1
    except OSError as e:
        logger.warning(f"Could not read backup file to count tables: {e}")

    size_bytes = os.path.getsize(out_path)
    return {
        "filename": filename,
        "size_bytes": size_bytes,
        "duration_ms": duration_ms,
        "tables_dumped": tables_dumped,
        "excluded_audit_logs": not config.backup_include_audit_logs,
        "path": out_path,
    }


# ---------- history ----------


async def list_backups(db: AsyncSession) -> list[dict]:
    """List .sql files in backup_dir sorted by mtime desc.

    Returns [] if backup_dir doesn't exist (rather than raising) so the
    admin UI can render an empty state on a fresh install.
    """
    config = await get_config(db)
    if not config.backup_dir or not os.path.isdir(config.backup_dir):
        return []

    files = glob.glob(os.path.join(config.backup_dir, "*.sql"))
    files.sort(key=os.path.getmtime, reverse=True)
    return [
        {
            "filename": os.path.basename(p),
            "size_bytes": os.path.getsize(p),
            "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(p)),
        }
        for p in files
    ]
