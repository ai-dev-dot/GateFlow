from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, null
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User, Department


class UsageService:
    """用量统计服务：从 AuditLog 实时聚合 token 用量

    部门/用户维度 JOIN users / departments 表，保证反映的是
    用户当前的部门和用户名（admin 改部门、删部门后，stats 立即跟随）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(
        self,
        dimension: str = "user",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[UUID] = None,
    ) -> list:
        """按维度聚合用量统计（实时查 AuditLog）

        dimension: "user" | "department" | "model" | "api_key"

        返回结构对所有维度保持一致：6 个字段（dimension / username /
        request_count / input_tokens / output_tokens / total_tokens），
        非 user 维度的 username 为 null。
        """
        filters = [AuditLog.status_code.isnot(None)]  # 排除 pending
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if start_date:
            filters.append(AuditLog.timestamp >= datetime.combine(start_date, time.min))
        if end_date:
            filters.append(AuditLog.timestamp < datetime.combine(end_date, time.max) )

        if dimension == "user":
            query = (
                select(
                    AuditLog.user_id,
                    User.username.label("username"),
                    func.count().label("request_count"),
                    func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
                    func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
                )
                .join(User, User.id == AuditLog.user_id)
                .where(*filters)
                .group_by(AuditLog.user_id, User.username)
            )
        elif dimension == "department":
            # LEFT JOIN Department：用户无部门时 name 为 NULL，结果里 fallback 为 "未知"
            query = (
                select(
                    Department.name.label("dimension"),
                    null().label("username"),
                    func.count().label("request_count"),
                    func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
                    func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
                )
                .join(User, User.id == AuditLog.user_id)
                .outerjoin(Department, Department.id == User.department_id)
                .where(*filters)
                .group_by(Department.name)
            )
        elif dimension == "model":
            query = (
                select(
                    AuditLog.model.label("dimension"),
                    null().label("username"),
                    func.count().label("request_count"),
                    func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
                    func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
                )
                .where(*filters)
                .group_by(AuditLog.model)
            )
        elif dimension == "api_key":
            query = (
                select(
                    AuditLog.api_key_name.label("dimension"),
                    null().label("username"),
                    func.count().label("request_count"),
                    func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
                    func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
                )
                .where(*filters)
                .group_by(AuditLog.api_key_name)
            )
        else:
            raise ValueError(f"不支持的聚合维度: {dimension}")

        query = query.order_by(func.coalesce(func.sum(AuditLog.total_tokens), 0).desc())
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "dimension": str(row[0]) if row[0] is not None else "未知",
                "username": row[1],
                "request_count": row[2],
                "input_tokens": row[3],
                "output_tokens": row[4],
                "total_tokens": row[5],
            }
            for row in rows
        ]

    async def get_trend(
        self,
        user_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        """按日聚合用量趋势（实时查 AuditLog）"""
        query = select(
            func.date(AuditLog.timestamp).label("date"),
            func.count().label("request_count"),
            func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
        ).where(AuditLog.status_code.isnot(None))

        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if start_date:
            query = query.where(AuditLog.timestamp >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.where(AuditLog.timestamp < datetime.combine(end_date, time.max) )

        query = query.group_by(func.date(AuditLog.timestamp)).order_by(func.date(AuditLog.timestamp))
        result = await self.db.execute(query)
        return result.all()
