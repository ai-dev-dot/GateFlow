"""Pydantic schemas for the backup feature.

SystemConfigUpdate is intentionally a "partial update" — both fields are
Optional, so PUTs can update one at a time. The router/service still
validates non-empty backup_dir when it is supplied.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SystemConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    backup_dir: str
    backup_include_audit_logs: bool
    pg_dump_path: str | None = None
    updated_at: datetime


class SystemConfigUpdate(BaseModel):
    """Partial update — all fields optional. Empty strings rejected."""

    backup_dir: str | None = None
    backup_include_audit_logs: bool | None = None
    pg_dump_path: str | None = None

    @field_validator("backup_dir")
    @classmethod
    def _strip_backup_dir(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("backup_dir must not be empty")
        return stripped

    @field_validator("pg_dump_path")
    @classmethod
    def _strip_pg_dump_path(cls, v: str | None) -> str | None:
        # Empty string from UI = "clear it". Treat as None. Whitespace-only
        # also rejected so admin gets clear feedback rather than a silently
        # blank path.
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        return stripped


class BackupFileInfo(BaseModel):
    filename: str
    size_bytes: int
    mtime: datetime


class BackupResultResponse(BaseModel):
    filename: str
    size_bytes: int
    duration_ms: int
    tables_dumped: int
    excluded_audit_logs: bool
    path: str
