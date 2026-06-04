import asyncio
import json
import time
import logging
from datetime import datetime, date
from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.gateway import ModelConfig
from app.models.usage import UsageStat
from app.models.user import User
from app.services.provider_key_service import ProviderKeyService
from app.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


class GatewayService:
    """Core gateway service that forwards requests to upstream LLM providers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def forward_request(
        self,
        user: User,
        model_config: ModelConfig,
        request_body: dict,
        is_stream: bool,
        request: Request,
    ):
        """
        Main entry point: forward an LLM API request to the upstream provider.

        1. Get an available provider key
        2. Create a pending audit log
        3. Forward to upstream (stream or non-stream)
        4. Return response to client
        5. Background: update audit log, key stats, usage stats
        """
        key_service = ProviderKeyService(self.db)
        provider_key = await key_service.get_available_key(model_config.provider)

        if not provider_key:
            raise GatewayError(
                status_code=503,
                detail=f"No available API key for provider: {model_config.provider}",
            )

        # Extract request token count from the request body (best effort)
        request_tokens = self._estimate_request_tokens(request_body)

        # Create pending audit log
        audit_log = AuditLog(
            status="pending",
            user_id=user.id,
            username=user.username,
            department=getattr(user, "department", None)
            and user.department.name
            if hasattr(user, "department") and user.department
            else None,
            model=request_body.get("model", model_config.model_alias),
            provider=model_config.provider,
            method="POST",
            path="/v1/chat/completions",
            request_body=json.dumps(request_body, ensure_ascii=False)[:2000],
            request_tokens=request_tokens,
            is_stream=is_stream,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500],
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        # Build upstream URL
        upstream_url = model_config.target_url.rstrip("/") + "/chat/completions"

        # Build upstream headers
        upstream_headers = {
            "Authorization": f"Bearer {provider_key.key}",
            "Content-Type": "application/json",
        }

        # Replace model alias with target model
        forward_body = {**request_body, "model": model_config.target_model}

        # Apply model config defaults
        if model_config.default_temperature is not None and "temperature" not in request_body:
            forward_body["temperature"] = model_config.default_temperature
        if model_config.default_max_tokens is not None and "max_tokens" not in request_body:
            forward_body["max_tokens"] = model_config.default_max_tokens

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
    ) -> StreamingResponse:
        """Handle streaming request: stream response directly, background log update."""

        async def stream_generator():
            """Yield chunks from upstream, collect usage for background update."""
            client = await get_http_client()
            response_tokens = 0
            full_content = ""
            usage_data = {}
            status_code = 200

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
                        # Read error body and yield as error
                        error_body = b""
                        async for chunk in upstream_response.aiter_bytes():
                            error_body += chunk
                        error_text = error_body.decode("utf-8", errors="replace")
                        logger.warning(
                            f"Upstream error {status_code}: {error_text[:500]}"
                        )
                        # Yield error as SSE event
                        error_msg = json.dumps(
                            {
                                "error": {
                                    "message": f"Upstream returned {status_code}",
                                    "type": "upstream_error",
                                    "code": status_code,
                                }
                            }
                        )
                        yield f"data: {error_msg}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for chunk in upstream_response.aiter_bytes():
                        yield chunk
                        # Parse SSE chunks to extract usage
                        chunk_text = chunk.decode("utf-8", errors="replace")
                        response_tokens, usage_data = self._parse_stream_chunk(
                            chunk_text, response_tokens, usage_data
                        )

            except httpx.ReadTimeout:
                logger.error("Upstream read timeout")
                error_msg = json.dumps(
                    {"error": {"message": "Upstream read timeout", "type": "timeout"}}
                )
                yield f"data: {error_msg}\n\n"
                yield "data: [DONE]\n\n"
                status_code = 504
            except Exception as e:
                logger.error(f"Stream error: {e}")
                error_msg = json.dumps(
                    {"error": {"message": str(e), "type": "internal_error"}}
                )
                yield f"data: {error_msg}\n\n"
                yield "data: [DONE]\n\n"
                status_code = 500
            finally:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                # Background update: don't block the stream
                asyncio.create_task(
                    self._update_after_response(
                        audit_log_id=audit_log_id,
                        provider_key_id=provider_key_id,
                        status_code=status_code,
                        request_tokens=request_tokens,
                        response_tokens=response_tokens,
                        latency_ms=latency_ms,
                        user=user,
                        model_config=model_config,
                    )
                )

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
    ):
        """Handle non-streaming request: return response directly, background log update."""
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
                # Extract usage from response
                usage = response_body.get("usage", {})
                response_tokens = usage.get("completion_tokens", 0)
            else:
                logger.warning(
                    f"Upstream error {status_code}: {response.text[:500]}"
                )

        except httpx.ReadTimeout:
            logger.error("Upstream read timeout")
            status_code = 504
            response_body = {
                "error": {"message": "Upstream read timeout", "type": "timeout"}
            }
        except Exception as e:
            logger.error(f"Request error: {e}")
            status_code = 500
            response_body = {
                "error": {"message": str(e), "type": "internal_error"}
            }

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Background update
        asyncio.create_task(
            self._update_after_response(
                audit_log_id=audit_log_id,
                provider_key_id=provider_key_id,
                status_code=status_code,
                request_tokens=request_tokens,
                response_tokens=response_tokens,
                latency_ms=latency_ms,
                user=user,
                model_config=model_config,
            )
        )

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
        user: User,
        model_config: ModelConfig,
    ) -> None:
        """
        Background task: update audit log, provider key stats, and usage stats.
        Runs via asyncio.create_task() so it doesn't block the response.
        """
        try:
            # Use a fresh session for background work
            from app.database import async_session

            async with async_session() as db:
                # 1. Update audit log
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

                # 2. Update provider key stats
                key_service = ProviderKeyService(db)
                if status_code == 200:
                    await key_service.update_key_success(
                        provider_key_id, request_tokens, response_tokens
                    )
                else:
                    await key_service.update_key_error(provider_key_id, status_code)

                # 3. Update usage stats
                await self._update_usage_stats(
                    db=db,
                    user_id=user.id,
                    department=getattr(user, "department", None)
                    and user.department.name
                    if hasattr(user, "department") and user.department
                    else None,
                    model=model_config.model_alias,
                    request_tokens=request_tokens,
                    response_tokens=response_tokens,
                )

        except Exception as e:
            logger.error(f"Background update failed: {e}", exc_info=True)

    async def _update_usage_stats(
        self,
        db: AsyncSession,
        user_id,
        department: Optional[str],
        model: str,
        request_tokens: int,
        response_tokens: int,
    ) -> None:
        """Update daily usage stats for the user/model combination."""
        today = date.today()
        total_tokens = request_tokens + response_tokens

        result = await db.execute(
            select(UsageStat).where(
                UsageStat.user_id == user_id,
                UsageStat.model == model,
                UsageStat.date == today,
            )
        )
        stat = result.scalar_one_or_none()

        if stat:
            stat.request_count += 1
            stat.input_tokens += request_tokens
            stat.output_tokens += response_tokens
            stat.total_tokens += total_tokens
        else:
            stat = UsageStat(
                date=today,
                user_id=user_id,
                model=model,
                department=department,
                request_count=1,
                input_tokens=request_tokens,
                output_tokens=response_tokens,
                total_tokens=total_tokens,
            )
            db.add(stat)

        await db.commit()

    @staticmethod
    def _estimate_request_tokens(request_body: dict) -> int:
        """
        Rough estimation of input tokens from request body.
        A simple heuristic: ~4 chars per token for English, ~2 for CJK.
        This is a best-effort estimate; actual counts come from upstream.
        """
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

        # Rough estimate: ~3 chars per token on average
        return max(1, total_chars // 3)

    @staticmethod
    def _parse_stream_chunk(
        chunk_text: str, response_tokens: int, usage_data: dict
    ) -> tuple:
        """
        Parse SSE chunk to extract token usage.
        OpenAI sends usage in the final chunk before [DONE].
        """
        for line in chunk_text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                continue
            try:
                data = json.loads(data_str)
                # Check for usage field (sent in last chunk with stream_options)
                if "usage" in data and data["usage"]:
                    usage_data = data["usage"]
                    response_tokens = usage_data.get("completion_tokens", 0)
                # Also count tokens from delta content as fallback
                choices = data.get("choices", [])
                for choice in choices:
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        response_tokens += 1
            except json.JSONDecodeError:
                continue

        return response_tokens, usage_data


class GatewayError(Exception):
    """Custom exception for gateway errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
