import json
import time
import logging
from datetime import datetime

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.api_key import APIKey
from app.models.gateway import ModelConfig
from app.models.user import User
from app.services.provider_key_service import ProviderKeyService
from app.services.provider_adapters import get_adapter
from app.services.provider_adapters.base import BaseAdapter, StreamEvent
from app.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


class GatewayService:
    """Core gateway service that forwards requests to upstream LLM providers.

    Uses a BaseAdapter to handle provider-specific protocol differences
    (URL, headers, request/response format, SSE parsing).
    """

    def __init__(self, db: AsyncSession, adapter: BaseAdapter):
        self.db = db
        self.adapter = adapter

    async def forward_request(
        self,
        user: User,
        model_config: ModelConfig,
        request_body: dict,
        is_stream: bool,
        request: Request,
        path: str = "/v1/chat/completions",
        api_key_id=None,
        agent_type: str | None = None,
    ):
        """
        Main entry point: forward an LLM API request to the upstream provider.

        1. Get an available provider key
        2. Create a pending audit log
        3. Forward to upstream (stream or non-stream)
        4. Return response to client
        5. Background: update audit log, key stats, usage stats
        """
        adapter = self.adapter

        key_service = ProviderKeyService(self.db)
        provider_key = await key_service.get_available_key(model_config.provider)

        if not provider_key:
            raise GatewayError(
                status_code=503,
                detail=f"No available API key for provider: {model_config.provider}",
            )

        # Extract request token count from the request body (best effort)
        request_tokens = self._estimate_request_tokens(request_body)

        # 快照：client api key 的 name（请求发生时的状态，之后不改）
        api_key_name = None
        if api_key_id:
            api_key_name = await self.db.scalar(
                select(APIKey.name).where(APIKey.id == api_key_id)
            )

        # Create pending audit log
        audit_log = AuditLog(
            status="pending",
            user_id=user.id,
            username=user.username,
            department=user.department.name if user.department else None,
            model=request_body.get("model", model_config.model_alias),
            provider=model_config.provider,
            method="POST",
            path=path,
            request_body=json.dumps(request_body, ensure_ascii=False)[:2000],
            request_tokens=request_tokens,
            is_stream=is_stream,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500],
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            agent_type=agent_type,
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        # Build upstream request via adapter
        upstream_url = adapter.build_upstream_url(model_config.target_url)
        upstream_headers = adapter.build_headers(provider_key.key)
        forward_body = adapter.build_request_body(
            request_body,
            model_config.target_model,
            {
                "temperature": model_config.default_temperature,
                "max_tokens": model_config.default_max_tokens,
            },
        )

        start_time = time.monotonic()

        if is_stream:
            return await self._handle_stream(
                upstream_url=upstream_url,
                upstream_headers=upstream_headers,
                forward_body=forward_body,
                audit_log_id=audit_log.id,
                provider_key_id=provider_key.id,
                user=user,
                model_config=model_config,
                request_tokens=request_tokens,
                start_time=start_time,
                api_key_id=api_key_id,
                agent_type=agent_type,
            )
        else:
            return await self._handle_non_stream(
                upstream_url=upstream_url,
                upstream_headers=upstream_headers,
                forward_body=forward_body,
                audit_log_id=audit_log.id,
                provider_key_id=provider_key.id,
                user=user,
                model_config=model_config,
                request_tokens=request_tokens,
                start_time=start_time,
                api_key_id=api_key_id,
                agent_type=agent_type,
            )

    async def _handle_stream(
        self,
        upstream_url: str,
        upstream_headers: dict,
        forward_body: dict,
        audit_log_id,
        provider_key_id,
        user: User,
        model_config: ModelConfig,
        request_tokens: int,
        start_time: float,
        api_key_id=None,
        agent_type: str | None = None,
    ) -> StreamingResponse:
        """Handle streaming request: stream response directly, background log update."""

        adapter = self.adapter

        async def stream_generator():
            """Yield chunks from upstream, collect usage for background update."""
            client = await get_http_client()
            response_tokens = 0
            input_tokens = 0
            status_code = 200
            buffer_lines: list[str] = []

            try:
                async with client.stream(
                    "POST",
                    upstream_url,
                    headers=upstream_headers,
                    json=forward_body,
                    timeout=httpx.Timeout(300.0, read=300.0),
                ) as upstream_response:
                    status_code = upstream_response.status_code

                    if status_code != 200:
                        error_body = b""
                        async for chunk in upstream_response.aiter_bytes():
                            error_body += chunk
                        error_text = error_body.decode("utf-8", errors="replace")
                        logger.warning(f"Upstream error {status_code}: {error_text[:500]}")
                        yield adapter.error_sse(f"Upstream returned {status_code}")
                        return

                    async for chunk in upstream_response.aiter_bytes():
                        yield chunk
                        # Parse SSE chunks to extract usage via adapter
                        chunk_text = chunk.decode("utf-8", errors="replace")
                        for line in chunk_text.split("\n"):
                            line = line.strip()
                            if not line:
                                if buffer_lines:
                                    event = adapter.parse_stream_event(buffer_lines)
                                    if event:
                                        if event.input_tokens:
                                            input_tokens = event.input_tokens
                                        if event.output_tokens:
                                            response_tokens = event.output_tokens
                                        # Fallback: count text chunks as rough token estimate
                                        if event.text and not event.output_tokens:
                                            response_tokens += 1
                                    buffer_lines = []
                                continue
                            buffer_lines.append(line)

            except httpx.ReadTimeout:
                logger.error("Upstream read timeout")
                yield adapter.error_sse("Upstream read timeout", "timeout")
                status_code = 504
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield adapter.error_sse(str(e), "internal_error")
                status_code = 500
            finally:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                # 必须 await 而非 create_task：admin 可能在请求刚结束时立即
                # 查询审计日志/用量统计。create_task 尚未落库即返回，会出现
                # "上一笔请求的统计看不到"的现象。
                try:
                    await self._update_after_response(
                        audit_log_id=audit_log_id,
                        provider_key_id=provider_key_id,
                        status_code=status_code,
                        request_tokens=request_tokens,
                        response_tokens=response_tokens,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.error(f"Stream post-update failed: {e}", exc_info=True)

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def _handle_non_stream(
        self,
        upstream_url: str,
        upstream_headers: dict,
        forward_body: dict,
        audit_log_id,
        provider_key_id,
        user: User,
        model_config: ModelConfig,
        request_tokens: int,
        start_time: float,
        api_key_id=None,
        agent_type: str | None = None,
    ):
        """Handle non-streaming request: return response directly, background log update."""
        adapter = self.adapter
        client = await get_http_client()
        status_code = 200
        response_tokens = 0
        response_body = {}

        try:
            response = await client.post(
                upstream_url,
                headers=upstream_headers,
                json=forward_body,
                timeout=httpx.Timeout(300.0),
            )
            status_code = response.status_code
            response_body = response.json()

            if status_code == 200:
                _, _, output_tokens = adapter.extract_response(response_body)
                response_tokens = output_tokens
            else:
                logger.warning(f"Upstream error {status_code}: {response.text[:500]}")

        except httpx.ReadTimeout:
            logger.error("Upstream read timeout")
            status_code = 504
            response_body = adapter.format_error(504, {"detail": "Upstream read timeout"})
        except Exception as e:
            logger.error(f"Request error: {e}")
            status_code = 500
            response_body = adapter.format_error(500, {"detail": str(e)})

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # 必须 await 而非 create_task：保证审计日志/用量统计在响应返回前
        # 完成更新，避免 admin 立即查询看不到刚发起的请求的统计。
        try:
            await self._update_after_response(
                audit_log_id=audit_log_id,
                provider_key_id=provider_key_id,
                status_code=status_code,
                request_tokens=request_tokens,
                response_tokens=response_tokens,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(f"Non-stream post-update failed: {e}", exc_info=True)

        if status_code != 200:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=status_code, content=response_body)

        return response_body

    async def _update_after_response(
        self,
        audit_log_id,
        provider_key_id,
        status_code: int,
        request_tokens: int,
        response_tokens: int,
        latency_ms: int,
    ) -> None:
        """请求结束后：更新 audit log + provider key 统计。

        注意：用量统计从 AuditLog 实时聚合，不再单独维护 UsageStat。
        """
        try:
            from app.database import async_session

            async with async_session() as db:
                result = await db.execute(
                    select(AuditLog).where(AuditLog.id == audit_log_id)
                )
                audit_log = result.scalar_one_or_none()
                if audit_log:
                    audit_log.status = "completed" if status_code == 200 else "failed"
                    audit_log.status_code = status_code
                    audit_log.request_tokens = request_tokens
                    audit_log.response_tokens = response_tokens
                    audit_log.total_tokens = request_tokens + response_tokens
                    audit_log.latency_ms = latency_ms
                    audit_log.completed_at = datetime.utcnow()
                    await db.commit()

                key_service = ProviderKeyService(db)
                if status_code == 200:
                    await key_service.update_key_success(
                        provider_key_id, request_tokens, response_tokens
                    )
                else:
                    await key_service.update_key_error(provider_key_id, status_code)

        except Exception as e:
            logger.error(f"Background update failed: {e}", exc_info=True)

    @staticmethod
    def _estimate_request_tokens(request_body: dict) -> int:
        """Rough estimation of input tokens from request body."""
        messages = request_body.get("messages", [])
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total_chars += len(part.get("text", ""))
        return max(1, total_chars // 3)


class GatewayError(Exception):
    """Custom exception for gateway errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
