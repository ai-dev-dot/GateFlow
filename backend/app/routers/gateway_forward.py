import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import AuthContext, get_auth_context
from app.models import ModelConfig
from app.services.gateway_service import GatewayError, GatewayService
from app.services.provider_adapters import get_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible Gateway"])


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    OpenAI-compatible chat completions endpoint.

    Accepts standard OpenAI chat completion requests and forwards them
    to the configured upstream provider. Supports both streaming and
    non-streaming modes.

    Usage:
        POST /v1/chat/completions
        Authorization: Bearer gf_xxx (API Key) or Bearer <jwt_token>
        Content-Type: application/json

        {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": false
        }
    """
    # Parse request body
    try:
        body = await request.json()
    except Exception as err:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from err

    # Validate required fields
    model_alias = body.get("model")
    if not model_alias:
        raise HTTPException(status_code=400, detail="Missing required field: model")

    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="Missing or invalid field: messages")

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

    # Forward request using the provider's adapter
    adapter = get_adapter(model_config.provider)
    gateway_service = GatewayService(db, adapter)

    try:
        return await gateway_service.forward_request(
            user=auth.user,
            model_config=model_config,
            request_body=body,
            is_stream=is_stream,
            request=request,
            path="/v1/chat/completions",
            api_key_id=auth.api_key_id,
            agent_type=auth.agent_type,
        )
    except GatewayError as e:
        return JSONResponse(status_code=e.status_code, content={"error": {"message": e.detail}})
    except Exception as e:
        logger.error(f"Gateway error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal gateway error", "type": "internal_error"}},
        )


@router.get("/models")
async def list_models(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    List available models (OpenAI-compatible format).

    Returns models in the OpenAI /v1/models response format,
    filtered to only active model configurations.
    """
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True))
    models = result.scalars().all()

    return {
        "object": "list",
        "data": [
            {
                "id": m.model_alias,
                "object": "model",
                "created": int(m.created_at.timestamp()) if m.created_at else 0,
                "owned_by": m.provider,
            }
            for m in models
        ],
    }
