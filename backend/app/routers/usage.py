from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_admin
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


@router.get("/trend")
async def get_usage_trend(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用量趋势（按日聚合），普通用户仅可查看自身数据"""
    usage_service = UsageService(db)

    # 非管理员只能查看自己的数据
    user_id = user.id if user.role.name != "admin" else None

    data = await usage_service.get_trend(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "data": [
            {
                "date": str(row.date),
                "request_count": row.request_count,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "total_tokens": row.total_tokens,
            }
            for row in data
        ]
    }
