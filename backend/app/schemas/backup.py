"""Pydantic schemas for the backup feature.

SystemConfigUpdate is a "partial update" — the service uses
``model_fields_set`` to know which fields the request body actually
contained. Fields NOT in the body are left untouched in the DB. Fields
that are present but null/empty are explicitly cleared (e.g. to clear
pg_dump_path, send ``{"pg_dump_path": null}`` or an empty string).
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
    """Partial update — fields default to None.

    Use ``instance.model_fields_set`` to know which fields the client
    sent (vs. left out). See ``backup_service.update_config``.
    """

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
        if v is None:
            return None
        return v.strip()  # "" stays ""; service treats "" as "clear"


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
