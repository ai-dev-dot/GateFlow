from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import func, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class UsageService:
    """用量统计服务：从 AuditLog 实时聚合 token 用量

    严格遵循"日志即真相"原则：所有聚合维度（username / department /
    api_key_name）都用 audit_logs 表上的快照字段，不再 JOIN users /
    departments / api_keys。这样：
    - 用户改名后，历史统计仍按当时的 username
    - 员工换部门后，原部门的历史统计不变
    - API Key 重命名后，历史统计仍按当时的 key name
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(
        self,
        dimension: str = "user",
        start_date: date | None = None,
        end_date: date | None = None,
        user_id: UUID | None = None,
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
            filters.append(AuditLog.timestamp < datetime.combine(end_date, time.max))

        # P2-3: route each dimension to a single shared query builder. The four
        # dimensions only differ in (a) the dimension column, (b) whether the
        # username snapshot is included, and (c) the optional secondary
        # group_by column (user dimension groups by (user_id, username) so the
        # two snapshots stay aligned).
        if dimension == "user":
            # 快照：直接用 audit_logs.username（不 JOIN users）
            query = self._build_summary_query(
                AuditLog.user_id,
                include_username=True,
                group_by_extra=AuditLog.username,
                filters=filters,
            )
        elif dimension == "department":
            # 快照：直接用 audit_logs.department（不 JOIN departments）
            query = self._build_summary_query(
                AuditLog.department, include_username=False, filters=filters
            )
        elif dimension == "model":
            query = self._build_summary_query(
                AuditLog.model, include_username=False, filters=filters
            )
        elif dimension == "api_key":
            # 快照：直接用 audit_logs.api_key_name
            query = self._build_summary_query(
                AuditLog.api_key_name, include_username=False, filters=filters
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

    @staticmethod
    def _build_summary_query(
        dimension_field,
        *,
        include_username: bool,
        filters: list,
        group_by_extra=None,
    ):
        """Build the SELECT/GROUP BY for a get_summary dimension.

        The query returns six columns in a stable order:
            dimension, username, request_count,
            input_tokens, output_tokens, total_tokens

        `group_by_extra` exists because the user dimension groups by
        (user_id, username) so both snapshots stay aligned; other
        dimensions group by the single dimension field.
        """
        username_col = (
            AuditLog.username.label("username") if include_username else null().label("username")
        )
        columns = [
            dimension_field.label("dimension"),
            username_col,
            func.count().label("request_count"),
            func.coalesce(func.sum(AuditLog.request_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AuditLog.response_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AuditLog.total_tokens), 0).label("total_tokens"),
        ]
        group_by = [dimension_field]
        if group_by_extra is not None:
            group_by.append(group_by_extra)
        return select(*columns).where(*filters).group_by(*group_by)

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
            query = query.where(AuditLog.timestamp < datetime.combine(end_date, time.max))

        query = query.group_by(func.date(AuditLog.timestamp)).order_by(
            func.date(AuditLog.timestamp)
        )
        result = await self.db.execute(query)
        return result.all()
