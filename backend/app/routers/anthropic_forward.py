"""Anthropic Messages API gateway endpoint.

Provides a native Anthropic-compatible endpoint at POST /v1/messages
so that Claude Code and other Anthropic-native clients can use GateFlow
directly with their SDK.

When the upstream provider is OpenAI-compatible (e.g. DeepSeek), the gateway
automatically translates between Anthropic and OpenAI protocols.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_auth_context, AuthContext
from app.models import ModelConfig
from app.services.gateway_service import GatewayError, GatewayService
from app.services.provider_adapters import get_adapter
from app.services.provider_adapters.anthropic_adapter import AnthropicAdapter

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

    Accepts Anthropic-format requests and forwards them to the configured
    upstream provider. If the upstream is OpenAI-compatible, the gateway
    automatically translates the protocol.
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
        raise HTTPException(status_code=404, detail=f"Model not found or inactive: {model_alias}")

    # Determine which adapter to use based on upstream provider
    upstream_adapter = get_adapter(model_config.provider)

    if upstream_adapter.provider_name == "anthropic":
        # Upstream is Anthropic: pass through directly
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
                content=upstream_adapter.format_error(e.status_code, {"detail": e.detail}),
            )
    else:
        # Upstream is OpenAI-compatible: bridge the protocol
        anthropic = AnthropicAdapter()
        openai_body = anthropic.to_openai_request(body, model_config.target_model)
        openai_body["stream"] = is_stream

        gateway_service = GatewayService(db, upstream_adapter)

        if is_stream:
            # Streaming bridge: convert OpenAI SSE chunks to Anthropic SSE
            async def anthropic_stream():
                from app.utils.http_client import get_http_client
                from app.services.provider_key_service import ProviderKeyService
                import time
                import asyncio

                key_service = ProviderKeyService(db)
                provider_key = await key_service.get_available_key(model_config.provider)
                if not provider_key:
                    yield anthropic.error_sse("No available API key")
                    return

                upstream_url = upstream_adapter.build_upstream_url(model_config.target_url)
                upstream_headers = upstream_adapter.build_headers(provider_key.key)
                forward_body = upstream_adapter.build_request_body(
                    openai_body,
                    model_config.target_model,
                    {"temperature": model_config.default_temperature, "max_tokens": model_config.default_max_tokens},
                )

                client = await get_http_client()
                start_time = time.monotonic()

                try:
                    async with client.stream(
                        "POST", upstream_url,
                        headers=upstream_headers,
                        json=forward_body,
                        timeout=__import__('httpx').Timeout(300.0, read=300.0),
                    ) as upstream_response:
                        if upstream_response.status_code != 200:
                            error_body = b""
                            async for chunk in upstream_response.aiter_bytes():
                                error_body += chunk
                            yield anthropic.error_sse(f"Upstream returned {upstream_response.status_code}")
                            return

                        buffer = ""
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
                                    import json
                                    data = json.loads(data_str)
                                    anthropic_events = anthropic.from_openai_sse_chunk(data)
                                    if anthropic_events:
                                        yield anthropic_events
                                except json.JSONDecodeError:
                                    continue
                except Exception as e:
                    logger.error(f"Anthropic bridge stream error: {e}")
                    yield anthropic.error_sse(str(e))

            return StreamingResponse(
                anthropic_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        else:
            # Non-streaming bridge
            from app.utils.http_client import get_http_client
            from app.services.provider_key_service import ProviderKeyService
            import httpx as httpx_lib

            key_service = ProviderKeyService(db)
            provider_key = await key_service.get_available_key(model_config.provider)
            if not provider_key:
                return JSONResponse(status_code=503, content=anthropic.format_error(503, {"detail": "No available API key"}))

            upstream_url = upstream_adapter.build_upstream_url(model_config.target_url)
            upstream_headers = upstream_adapter.build_headers(provider_key.key)
            forward_body = upstream_adapter.build_request_body(
                openai_body,
                model_config.target_model,
                {"temperature": model_config.default_temperature, "max_tokens": model_config.default_max_tokens},
            )

            try:
                client = await get_http_client()
                response = await client.post(
                    upstream_url, headers=upstream_headers, json=forward_body,
                    timeout=httpx_lib.Timeout(300.0),
                )
                if response.status_code == 200:
                    openai_response = response.json()
                    anthropic_response = anthropic.from_openai_response(openai_response)
                    return anthropic_response
                else:
                    return JSONResponse(
                        status_code=response.status_code,
                        content=anthropic.format_error(response.status_code, {"detail": response.text[:500]}),
                    )
            except Exception as e:
                logger.error(f"Anthropic bridge error: {e}")
                return JSONResponse(status_code=500, content=anthropic.format_error(500, {"detail": str(e)}))
