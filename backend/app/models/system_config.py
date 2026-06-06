"""SystemConfig — singleton table for runtime-mutable admin settings.

This is a "one-row" table (id is always 1) for settings that admins
need to change at runtime — the alternative (Settings from pydantic-
settings) is @lru_cache'd at process start and would require a restart.

v1 fields: backup_dir, backup_include_audit_logs. Add new ones here
and in SystemConfigUpdate schema when needed.
"""

import logging

from sqlalchemy import Boolean, CheckConstraint, Column, Integer, String, inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import validates
from sqlalchemy.sql import text

from app.models.base import Base, TimestampMixin

logger = logging.getLogger(__name__)


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)
    backup_dir = Column(String(500), nullable=False, default="./backups")
    backup_include_audit_logs = Column(Boolean, nullable=False, default=False)
    # Absolute path to the pg_dump binary. The admin fills this in via the
    # /backup settings UI; the service does NOT search PATH or hardcoded
    # common install locations. If NULL, run_backup raises a clear error
    # telling the admin to set it. Default NULL (admin must opt in).
    pg_dump_path = Column(String(500), nullable=True, default=None)

    # Enforce the singleton invariant at the DB layer. If anything tries
    # to insert a second row, PG/SQLite both reject it.
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_config_singleton"),)

    @validates("backup_dir")
    def _validate_backup_dir(self, key, value):
        # Reject empty / whitespace-only paths at the ORM level. The
        # service layer's update_config() raises a friendlier error that
        # the router maps to 422; this is the last line of defense.
        if not value or not value.strip():
            raise ValueError("backup_dir must not be empty")
        return value.strip()


async def ensure_columns(engine: AsyncEngine) -> None:
    """Idempotently add columns that were added in newer versions.

    SQLAlchemy ``create_all`` only creates MISSING TABLES — it does not
    add new columns to existing tables. Until Alembic is wired up (P2-5
    in the backlog), we manually ``ALTER TABLE`` for each new column
    if it's missing. Safe to call on every startup.

    Currently adds:
    - pg_dump_path (added with the backup feature)
    """
    async with engine.begin() as conn:
        # `inspect` is sync; use a sync def via run_sync.
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("system_config")}

        existing = await conn.run_sync(_get_columns)

    new_columns = []
    if "pg_dump_path" not in existing:
        new_columns.append("ADD COLUMN pg_dump_path VARCHAR(500)")

    if not new_columns:
        return

    # One ALTER per missing column. VARCHAR(500) works on both PG and
    # SQLite. Wrap in try/except — if two workers race the ALTER, the
    # second one fails with "duplicate column"; that's harmless.
    for ddl in new_columns:
        sql = f"ALTER TABLE system_config {ddl}"
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
            logger.info(f"[system_config] applied: {sql}")
        except Exception as e:  # noqa: BLE001
            # "duplicate column" race is fine; anything else surfaces.
            if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                logger.warning(f"[system_config] ALTER failed ({sql}): {e}")
