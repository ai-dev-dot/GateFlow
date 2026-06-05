"""Anthropic Messages API gateway endpoint.

提供原生 Anthropic 兼容端点 POST /v1/messages，让 Claude Code 等 Anthropic 原生
客户端可以直接用 GateFlow。

当上游是 OpenAI 兼容 provider 时（如 DeepSeek），gateway 自动在协议之间翻译。
所有路径通过 StreamForwarder 抽象走统一审计 + 统计 + 错误处理。
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_auth_context, AuthContext
from app.models.audit import AuditLog
from app.models.gateway import ModelConfig
from app.services.audit_service import AuditService
from app.services.gateway_service import GatewayError, GatewayService
from app.services.provider_adapters import get_adapter
from app.services.provider_adapters.anthropic_adapter import AnthropicAdapter
from app.services.stream_forwarder import StreamForwarder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Anthropic Gateway"])


@router.post("/messages")
async def messages(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Anthropic Messages API endpoint.

    - 上游是 Anthropic：直接透传
    - 上游是 OpenAI 兼容：协议翻译（request + response / stream）
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model_alias = body.get("model")
    if not model_alias:
        raise HTTPException(status_code=400, detail="Missing required field: model")

    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="Missing or invalid field: messages")

    if not body.get("max_tokens"):
        raise HTTPException(status_code=400, detail="Missing required field: max_tokens")

    is_stream = body.get("stream", False)

    # Find model config
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.model_alias == model_alias,
            ModelConfig.is_active == True,
        )
    )
    model_config = result.scalar_one_or_none()

    if not model_config:
        raise HTTPException(
            status_code=404, detail=f"Model not found or inactive: {model_alias}"
        )

    upstream_adapter = get_adapter(model_config.provider)

    if upstream_adapter.provider_name == "anthropic":
        # Upstream is Anthropic: pass through directly via GatewayService
        gateway_service = GatewayService(db, upstream_adapter)
        try:
            return await gateway_service.forward_request(
                user=auth.user,
                model_config=model_config,
                request_body=body,
                is_stream=is_stream,
                request=request,
                path="/v1/messages",
                api_key_id=auth.api_key_id,
                agent_type=auth.agent_type,
            )
        except GatewayError as e:
            return JSONResponse(
                status_code=e.status_code,
                content=upstream_adapter.format_error(
                    e.status_code, {"detail": e.detail}
                ),
            )
    else:
        # Upstream is OpenAI-compatible: bridge the protocol.
        # Both streaming and non-streaming paths go through StreamForwarder
        # so audit log is written for ALL Anthropic→OpenAI bridging (P0-3 fix).
        anthropic = AnthropicAdapter()
        openai_body = anthropic.to_openai_request(body, model_config.target_model)
        openai_body["stream"] = is_stream

        from app.services.provider_key_service import ProviderKeyService
        from app.utils.http_client import get_http_client
        import httpx

        key_service = ProviderKeyService(db)
        provider_key = await key_service.get_available_key(model_config.provider)
        if not provider_key:
            return JSONResponse(
                status_code=503,
                content=anthropic.format_error(
                    503, {"detail": "No available API key"}
                ),
            )

        upstream_url = upstream_adapter.build_upstream_url(model_config.target_url)
        upstream_headers = upstream_adapter.build_headers(provider_key.key)
        forward_body = upstream_adapter.build_request_body(
            openai_body,
            model_config.target_model,
            {
                "temperature": model_config.default_temperature,
                "max_tokens": model_config.default_max_tokens,
            },
        )

        # Estimate tokens (use full message body)
        request_tokens = max(
            1, sum(len(str(m.get("content", ""))) for m in messages) // 3
        )

        # Create pending audit log via AuditService (this is the P0-3 fix:
        # previously this path wrote NO audit log)
        audit_service = AuditService(db)
        audit_log = await audit_service.create_pending_log(
            user=auth.user,
            model=model_config.model_alias,
            provider=model_config.provider,
            path="/v1/messages",
            request_body=json.dumps(body, ensure_ascii=False)[:2000],
            is_stream=is_stream,
            api_key_id=auth.api_key_id,
            api_key_name=None,  # could look up same as gateway
            agent_type=auth.agent_type,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500],
        )
        await db.commit()
        await db.refresh(audit_log)

        if is_stream:
            # Streaming bridge: convert OpenAI SSE → Anthropic SSE
            # The transform reads from a buffer that parses OpenAI events and
            # uses anthropic.from_openai_sse_chunk to emit Anthropic SSE.

            # We need a buffer to hold the latest parsed data dict so the
            # transform callback can call from_openai_sse_chunk.
            parsed_buffer: dict = {}

            def transform_event_sse(data: dict) -> str:
                """Receive parsed OpenAI data dict, emit Anthropic SSE string."""
                return anthropic.from_openai_sse_chunk(data)

            # We can't use a list capture across awaits cleanly in a sync
            # callback. The bridge needs to parse lines → dicts and emit SSE.
            # Use a custom emit_sse: but StreamForwarder parses with adapter.
            # Workaround: parse the data string ourselves in a custom path.
            #
            # Actually the cleanest way: write a small inline streaming bridge
            # that uses StreamForwarder's transport/audit/stats but does its
            # own SSE→SSE conversion. The transport layer (httpx.stream +
            # audit + key stats) is what we want to share.
            #
            # For now, implement the bridge directly but call StreamForwarder's
            # _save_after_stream to get the audit + key stats update.

            # ---- Inline streaming bridge (similar to chat_service style) ----
            import time as _time
            from app.database import async_session as _async_session

            start_time = _time.monotonic()

            async def bridge_stream():
                full_content = ""
                response_tokens = 0
                input_tokens = 0
                status_code = 200
                client = await get_http_client()
                buffer = ""

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
                            yield anthropic.error_sse(
                                f"Upstream returned {status_code}"
                            )
                            return

                        async for chunk in upstream_response.aiter_bytes():
                            chunk_text = chunk.decode("utf-8", errors="replace")
                            buffer += chunk_text
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                line = line.strip()
                                if not line or not line.startswith("data:"):
                                    continue
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(data_str)
                                    # Token capture from usage chunk
                                    usage = data.get("usage")
                                    if usage:
                                        if usage.get("prompt_tokens"):
                                            input_tokens = usage["prompt_tokens"]
                                        if usage.get("completion_tokens"):
                                            response_tokens = usage[
                                                "completion_tokens"
                                            ]
                                    # Accumulate text
                                    choices = data.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            full_content += content
                                    # Bridge to Anthropic SSE
                                    sse = anthropic.from_openai_sse_chunk(data)
                                    if sse:
                                        yield sse
                                except json.JSONDecodeError:
                                    continue

                except httpx.ReadTimeout:
                    logger.error("Bridge stream read timeout")
                    yield anthropic.error_sse("Upstream read timeout", "timeout")
                    status_code = 504
                except Exception as e:
                    logger.error(f"Bridge stream error: {e}")
                    yield anthropic.error_sse(str(e), "internal_error")
                    status_code = 500
                finally:
                    latency_ms = int((_time.monotonic() - start_time) * 1000)
                    # Persist audit + key stats via helper
                    forwarder = StreamForwarder(db, upstream_adapter)
                    await forwarder._save_after_stream(
                        audit_log_id=audit_log.id,
                        provider_key_id=provider_key.id,
                        status_code=status_code,
                        request_tokens=request_tokens,
                        response_tokens=response_tokens,
                        input_tokens=input_tokens,
                        latency_ms=latency_ms,
                        full_content="",  # bridge doesn't save message to DB
                        on_complete=None,
                    )

            return StreamingResponse(
                bridge_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # Non-streaming bridge: simple POST + transform response
            try:
                client = await get_http_client()
                response = await client.post(
                    upstream_url,
                    headers=upstream_headers,
                    json=forward_body,
                    timeout=httpx.Timeout(300.0),
                )
                if response.status_code == 200:
                    openai_response = response.json()
                    # Token capture for stats
                    usage = openai_response.get("usage", {})
                    response_tokens = usage.get("completion_tokens", 0)
                    input_tokens = usage.get("prompt_tokens", 0)

                    anthropic_response = anthropic.from_openai_response(
                        openai_response
                    )

                    # Persist audit + key stats
                    forwarder = StreamForwarder(db, upstream_adapter)
                    await forwarder._save_after_stream(
                        audit_log_id=audit_log.id,
                        provider_key_id=provider_key.id,
                        status_code=200,
                        request_tokens=request_tokens,
                        response_tokens=response_tokens,
                        input_tokens=input_tokens,
                        latency_ms=0,
                        full_content="",
                        on_complete=None,
                    )
                    return anthropic_response
                else:
                    # Persist failure stats
                    forwarder = StreamForwarder(db, upstream_adapter)
                    await forwarder._save_after_stream(
                        audit_log_id=audit_log.id,
                        provider_key_id=provider_key.id,
                        status_code=response.status_code,
                        request_tokens=request_tokens,
                        response_tokens=0,
                        input_tokens=0,
                        latency_ms=0,
                        full_content="",
                        on_complete=None,
                    )
                    return JSONResponse(
                        status_code=response.status_code,
                        content=anthropic.format_error(
                            response.status_code,
                            {"detail": response.text[:500]},
                        ),
                    )
            except Exception as e:
                logger.error(f"Anthropic bridge error: {e}")
                # Persist failure stats
                forwarder = StreamForwarder(db, upstream_adapter)
                await forwarder._save_after_stream(
                    audit_log_id=audit_log.id,
                    provider_key_id=provider_key.id,
                    status_code=500,
                    request_tokens=request_tokens,
                    response_tokens=0,
                    input_tokens=0,
                    latency_ms=0,
                    full_content="",
                    on_complete=None,
                )
                return JSONResponse(
                    status_code=500,
                    content=anthropic.format_error(500, {"detail": str(e)}),
                )
