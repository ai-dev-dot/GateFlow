"""Admin backup router — 4 endpoints, all require admin role.

Path: /api/backup/*
- GET  /config         → SystemConfigResponse
- PUT  /config         → update backup_dir / backup_include_audit_logs
- POST /run            → trigger pg_dump (PG-only; 501 on SQLite)
                         body: {"note": "..."} (optional)
- GET  /history        → list existing .sql files in backup_dir
                         each entry includes note from companion .meta.json

Import-safety: this module imports backup_service at module load (for
the exception classes and service functions). backup_service uses
asyncio.create_subprocess_exec only at call time (run_backup body),
not at import time — so the test env (SQLite) can collect this module
without spawning a subprocess.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import require_admin
from app.models import User
from app.schemas.backup import (
    BackupFileInfo,
    BackupResultResponse,
    BackupRunRequest,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.services.backup_service import (
    BackupFailedError,
    BackupNotSupportedError,
    get_config,
    list_backups,
    run_backup,
    update_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["Backup"])


@router.get("/config", response_model=SystemConfigResponse)
async def get_backup_config(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return the singleton SystemConfig (admin only)."""
    return await get_config(db)


@router.put("/config", response_model=SystemConfigResponse)
async def update_backup_config(
    data: SystemConfigUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update any of backup_dir, backup_include_audit_logs, pg_dump_path
    (admin only). Fields not in the request body are left untouched.
    Fields present but null or "" are explicitly cleared (pg_dump_path
    → NULL; backup_dir → 422 via Pydantic field validator).

    422 if backup_dir is empty/whitespace (Pydantic field validator).
    """
    # Translate Pydantic's "present in body" semantics to a kwargs dict
    # the service can read. We pass the model itself so the service can
    # call ``data.model_fields_set`` to know which keys were supplied.
    try:
        return await update_config(db, data=data)
    except ValueError as e:
        # Defense in depth — pydantic field_validator should catch this first.
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/run", response_model=BackupResultResponse)
async def trigger_backup(
    body: BackupRunRequest = BackupRunRequest(),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a pg_dump run and write to backup_dir (admin only).

    - 501 if DATABASE_URL is not PostgreSQL (e.g. SQLite test env)
    - 500 if pg_dump fails, binary path is invalid, or subprocess errors.
      The detail field carries the service's human-readable message so
      the admin UI can show it directly.
    """
    try:
        return await run_backup(db, note=body.note)
    except BackupNotSupportedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except BackupFailedError as e:
        # Prefer the service's message (path invalid, binary missing,
        # etc.) over a generic "pg_dump failed". Only when no message
        # is set do we synthesize one from returncode/stderr.
        detail = str(e).strip() or f"pg_dump failed (rc={e.returncode}): {(e.stderr or '')[:500]}"
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/history", response_model=list[BackupFileInfo])
async def list_backup_files(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List .sql files in backup_dir, sorted by mtime desc (admin only)."""
    return await list_backups(db)
