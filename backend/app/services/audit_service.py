from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    """审计日志服务：记录和查询 API 调用日志"""

    MAX_LOG_CONTENT_LENGTH = 100 * 1024  # 100KB

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pending_log(
        self,
        user,
        model: str,
        provider: str,
        request_body: Optional[str],
        is_stream: bool = False,
    ) -> UUID:
        """创建一条待处理的审计日志，返回日志 ID"""
        # 截断过长的请求体
        truncated_body = None
        if request_body:
            truncated_body = request_body[: self.MAX_LOG_CONTENT_LENGTH]

        log = AuditLog(
            user_id=user.id,
            username=user.username,
            department=user.department.name if user.department else None,
            model=model,
            provider=provider,
            method="POST",
            path="/v1/chat/completions",
            request_body=truncated_body,
            is_stream=is_stream,
            status="pending",
        )
        self.db.add(log)
        await self.db.flush()
        return log.id

    async def update_log(
        self,
        log_id: UUID,
        status_code: int,
        request_tokens: int = 0,
        response_tokens: int = 0,
        latency_ms: int = 0,
    ) -> None:
        """更新审计日志：设置状态码、token 用量和延迟"""
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if not log:
            return

        log.status_code = status_code
        log.request_tokens = request_tokens
        log.response_tokens = response_tokens
        log.total_tokens = request_tokens + response_tokens
        log.latency_ms = latency_ms
        log.completed_at = datetime.utcnow()
        log.status = "completed" if status_code < 400 else "error"
        await self.db.flush()

    async def get_logs(
        self,
        user_id: Optional[UUID] = None,
        department: Optional[str] = None,
        model: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询审计日志，支持多维度筛选和分页"""
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        # 构建筛选条件
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if department:
            filters.append(AuditLog.department == department)
        if model:
            filters.append(AuditLog.model == model)
        if start_time:
            filters.append(AuditLog.timestamp >= start_time)
        if end_time:
            filters.append(AuditLog.timestamp <= end_time)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        # 获取总数
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": logs,
        }
