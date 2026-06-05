"""审计日志服务：记录和查询 API 调用日志

提供统一的 pending 创建 + 完成后更新接口。StreamForwarder 在流结束后
调用 `record_completion()` 统一处理 status 字段（"completed"/"failed"）和
token 累加（避免之前 gateway_service 与 chat_service 两处实现漂移的问题）。
"""

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

    # ---------- 写入路径（流式转发时使用）----------

    async def create_pending_log(
        self,
        user,
        model: str,
        provider: str,
        path: str,
        request_body: Optional[str],
        is_stream: bool = False,
        api_key_id: Optional[UUID] = None,
        api_key_name: Optional[str] = None,
        agent_type: Optional[str] = None,
        method: str = "POST",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """创建一条待处理的审计日志，flush() 后日志已有 id。

        注意：调用方需要负责 commit（或由 StreamForwarder 统一处理）。
        这里用 flush 而不是 commit，避免在请求作用域内强制落盘。
        """
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
            method=method,
            path=path,
            request_body=truncated_body,
            is_stream=is_stream,
            status="pending",
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            agent_type=agent_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def record_completion(
        self,
        log: AuditLog,
        status_code: int,
        request_tokens: int = 0,
        response_tokens: int = 0,
        latency_ms: int = 0,
    ) -> None:
        """记录一次请求的完成状态（在流结束/响应结束后调用）。

        状态判断统一在此处：
        - status_code == 200 → "completed"
        - 其他 → "failed"
        """
        log.status_code = status_code
        log.request_tokens = request_tokens
        log.response_tokens = response_tokens
        log.total_tokens = request_tokens + response_tokens
        log.latency_ms = latency_ms
        log.completed_at = datetime.utcnow()
        log.status = "completed" if status_code == 200 else "failed"

    # ---------- 读取路径（管理后台用）----------

    async def get_log_by_id(self, log_id: UUID, user) -> Optional[AuditLog]:
        """Get audit log by ID, non-admin can only see own logs"""
        query = select(AuditLog).where(AuditLog.id == log_id)
        if user.role.name != "admin":
            query = query.where(AuditLog.user_id == user.id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

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
