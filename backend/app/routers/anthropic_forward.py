"""Anthropic Messages API gateway endpoint.

Provides a native Anthropic-compatible endpoint at POST /v1/messages
so that Claude Code and other Anthropic-native clients can use GateFlow
directly with their SDK.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_auth_context, AuthContext
from app.models import ModelConfig
from app.services.gateway_service import GatewayError, GatewayService
from app.services.provider_adapters import get_adapter

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
    upstream provider. Supports both streaming and non-streaming modes.

    Usage:
        POST /v1/messages
        Authorization: Bearer gf_xxx (API Key) or Bearer <jwt_token>
        x-api-key: gf_xxx  (also accepted)
        Content-Type: application/json

        {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": false
        }
    """
    # Parse request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Validate required fields
    model_alias = body.get("model")
    if not model_alias:
        raise HTTPException(status_code=400, detail="Missing required field: model")

    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(
            status_code=400, detail="Missing or invalid field: messages"
        )

    # Anthropic requires max_tokens
    if not body.get("max_tokens"):
        raise HTTPException(
            status_code=400, detail="Missing required field: max_tokens"
        )

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
            status_code=404,
            detail=f"Model not found or inactive: {model_alias}",
        )

    # Use Anthropic adapter (regardless of model_config.provider, since the
    # client is sending Anthropic-format requests)
    adapter = get_adapter("anthropic")
    gateway_service = GatewayService(db, adapter)

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
            content=adapter.format_error(e.status_code, {"detail": e.detail}),
        )
    except Exception as e:
        logger.error(f"Anthropic gateway error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=adapter.format_error(500, {"detail": "Internal gateway error"}),
        )
