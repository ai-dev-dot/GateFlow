from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import require_admin
from app.models.user import User
from app.services.usage_service import UsageService

router = APIRouter(prefix="/api/usage", tags=["用量统计"])


@router.get("/summary")
async def get_usage_summary(
    dimension: str = Query("user", description="聚合维度: user/department/model"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取用量统计摘要，仅管理员可访问"""
    service = UsageService(db)

    summary = await service.get_summary(
        dimension=dimension,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "dimension": dimension,
        "items": summary,
    }
