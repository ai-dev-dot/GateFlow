"""SystemConfig — singleton table for runtime-mutable admin settings.

This is a "one-row" table (id is always 1) for settings that admins
need to change at runtime — the alternative (Settings from pydantic-
settings) is @lru_cache'd at process start and would require a restart.

v1 fields: backup_dir, backup_include_audit_logs. Add new ones here
and in SystemConfigUpdate schema when needed.
"""

from sqlalchemy import Boolean, CheckConstraint, Column, Integer, String
from sqlalchemy.orm import validates

from app.models.base import Base, TimestampMixin


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)
    backup_dir = Column(String(500), nullable=False, default="./backups")
    backup_include_audit_logs = Column(Boolean, nullable=False, default=False)

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
