from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_admin
from app.models.user import User
from app.services.usage_service import UsageService

router = APIRouter(prefix="/api/usage", tags=["用量统计"])


# ---- 管理员接口 ----


@router.get("/summary")
async def get_usage_summary(
    dimension: str = Query("user", description="聚合维度: user/department/model"),
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取全局用量统计摘要（管理员）"""
    service = UsageService(db)
    summary = await service.get_summary(
        dimension=dimension,
        start_date=start_date,
        end_date=end_date,
    )
    date_range = await service.get_date_range()
    return {"dimension": dimension, "items": summary, **date_range}


@router.get("/trend")
async def get_usage_trend(
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取全局用量趋势（管理员）"""
    data = await UsageService(db).get_trend(
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


# ---- 普通用户接口（仅自身数据）----


@router.get("/my-summary")
async def get_my_usage_summary(
    dimension: str = Query("model", description="聚合维度: model/api_key"),
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的用量统计摘要"""
    service = UsageService(db)
    summary = await service.get_summary(
        dimension=dimension,
        start_date=start_date,
        end_date=end_date,
        user_id=user.id,
    )
    return {"dimension": dimension, "items": summary}


@router.get("/my-trend")
async def get_my_usage_trend(
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的用量趋势（按日聚合）"""
    data = await UsageService(db).get_trend(
        user_id=user.id,
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
