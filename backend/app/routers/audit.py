from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit", tags=["审计日志"])


@router.get("/logs")
async def get_audit_logs(
    user_id: Optional[UUID] = Query(None, description="按用户 ID 筛选"),
    department: Optional[str] = Query(None, description="按部门筛选"),
    model: Optional[str] = Query(None, description="按模型筛选"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询审计日志，非管理员只能查看自己的日志"""
    service = AuditService(db)

    # 非管理员只能查看自己的日志
    if current_user.role.name != "admin":
        user_id = current_user.id

    result = await service.get_logs(
        user_id=user_id,
        department=department,
        model=model,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )

    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": [
            {
                "id": str(log.id),
                "status": log.status,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "user_id": str(log.user_id),
                "username": log.username,
                "department": log.department,
                "model": log.model,
                "provider": log.provider,
                "request_tokens": log.request_tokens,
                "response_tokens": log.response_tokens,
                "total_tokens": log.total_tokens,
                "latency_ms": log.latency_ms,
                "status_code": log.status_code,
                "is_stream": log.is_stream,
            }
            for log in result["items"]
        ],
    }
