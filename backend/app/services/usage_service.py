from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import UsageStat


class UsageService:
    """用量统计服务：按日期/用户/模型/ApiKey 聚合 token 用量"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_usage(
        self,
        user_id: UUID,
        model: str,
        department: Optional[str],
        input_tokens: int,
        output_tokens: int,
        api_key_id: Optional[UUID] = None,
        api_key_name: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> None:
        """记录用量，按 (日期, 用户, 模型, api_key_id) upsert"""
        today = date.today()

        result = await self.db.execute(
            select(UsageStat).where(
                UsageStat.date == today,
                UsageStat.user_id == user_id,
                UsageStat.model == model,
                UsageStat.api_key_id == api_key_id,
            )
        )
        stat = result.scalar_one_or_none()

        if stat:
            stat.request_count += 1
            stat.input_tokens += input_tokens
            stat.output_tokens += output_tokens
            stat.total_tokens += input_tokens + output_tokens
        else:
            stat = UsageStat(
                date=today,
                user_id=user_id,
                model=model,
                department=department,
                api_key_id=api_key_id,
                api_key_name=api_key_name,
                agent_type=agent_type,
                request_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )
            self.db.add(stat)

        await self.db.flush()

    async def get_summary(
        self,
        dimension: str = "user",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[UUID] = None,
    ) -> list:
        """按维度聚合用量统计

        dimension: "user" | "department" | "model" | "api_key"
        """
        filters = []
        if user_id:
            filters.append(UsageStat.user_id == user_id)
        if start_date:
            filters.append(UsageStat.date >= start_date)
        if end_date:
            filters.append(UsageStat.date <= end_date)

        if dimension == "user":
            query = (
                select(
                    UsageStat.user_id,
                    func.sum(UsageStat.request_count).label("request_count"),
                    func.sum(UsageStat.input_tokens).label("input_tokens"),
                    func.sum(UsageStat.output_tokens).label("output_tokens"),
                    func.sum(UsageStat.total_tokens).label("total_tokens"),
                )
                .where(*filters)
                .group_by(UsageStat.user_id)
            )
        elif dimension == "department":
            query = (
                select(
                    UsageStat.department,
                    func.sum(UsageStat.request_count).label("request_count"),
                    func.sum(UsageStat.input_tokens).label("input_tokens"),
                    func.sum(UsageStat.output_tokens).label("output_tokens"),
                    func.sum(UsageStat.total_tokens).label("total_tokens"),
                )
                .where(*filters)
                .group_by(UsageStat.department)
            )
        elif dimension == "model":
            query = (
                select(
                    UsageStat.model,
                    func.sum(UsageStat.request_count).label("request_count"),
                    func.sum(UsageStat.input_tokens).label("input_tokens"),
                    func.sum(UsageStat.output_tokens).label("output_tokens"),
                    func.sum(UsageStat.total_tokens).label("total_tokens"),
                )
                .where(*filters)
                .group_by(UsageStat.model)
            )
        elif dimension == "api_key":
            query = (
                select(
                    UsageStat.api_key_name,
                    func.sum(UsageStat.request_count).label("request_count"),
                    func.sum(UsageStat.input_tokens).label("input_tokens"),
                    func.sum(UsageStat.output_tokens).label("output_tokens"),
                    func.sum(UsageStat.total_tokens).label("total_tokens"),
                )
                .where(*filters)
                .group_by(UsageStat.api_key_name)
            )
        else:
            raise ValueError(f"不支持的聚合维度: {dimension}")

        query = query.order_by(func.sum(UsageStat.total_tokens).desc())
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "dimension": row[0] or "未知",
                "request_count": row[1],
                "input_tokens": row[2],
                "output_tokens": row[3],
                "total_tokens": row[4],
            }
            for row in rows
        ]

    async def get_trend(
        self,
        user_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        """按日聚合用量趋势"""
        query = select(
            UsageStat.date,
            func.sum(UsageStat.request_count).label("request_count"),
            func.sum(UsageStat.input_tokens).label("input_tokens"),
            func.sum(UsageStat.output_tokens).label("output_tokens"),
            func.sum(UsageStat.total_tokens).label("total_tokens"),
        )

        if user_id:
            query = query.where(UsageStat.user_id == user_id)
        if start_date:
            query = query.where(UsageStat.date >= start_date)
        if end_date:
            query = query.where(UsageStat.date <= end_date)

        query = query.group_by(UsageStat.date).order_by(UsageStat.date)
        result = await self.db.execute(query)
        return result.all()
