"""Chat service: manages conversations, messages, and chat streaming.

Streaming goes through StreamForwarder (unified transport + audit + stats).
The chat-specific concern (save AI message + auto-title conversation) is
implemented as an `on_complete` hook.
"""

import json
import logging
from uuid import UUID

import httpx
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Conversation, Message
from app.models.gateway import ModelConfig
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.provider_adapters import get_adapter
from app.services.provider_key_service import ProviderKeyService
from app.services.stream_forwarder import StreamForwarder
from app.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, user: User, model: str) -> Conversation:
        conversation = Conversation(user_id=user.id, model=model)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversations(self, user: User) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_messages(self, conversation_id: UUID, user: User) -> list[Message]:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return []

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def delete_conversation(self, conversation_id: UUID, user: User) -> bool:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return False

        await self.db.execute(
            Message.__table__.delete().where(Message.conversation_id == conversation_id)
        )
        await self.db.delete(conversation)
        await self.db.commit()
        return True

    # ---------- 发送消息（非流式，保留兼容）----------

    async def send_message(self, conversation_id: UUID, user: User, content: str) -> Message | None:
        """发送消息并获取 AI 回复（非流式）"""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return None

        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            tokens=0,
        )
        self.db.add(user_message)
        await self.db.commit()

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        history = result.scalars().all()
        messages = [{"role": msg.role, "content": msg.content} for msg in history]

        ai_content, tokens = await self._call_llm(conversation.model, messages)

        ai_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_content or "(empty response)",
            tokens=tokens,
        )
        self.db.add(ai_message)

        if not conversation.title and content:
            conversation.title = content[:50]

        await self.db.commit()
        await self.db.refresh(ai_message)
        return ai_message

    async def _call_llm(self, model_alias: str, messages: list[dict]) -> tuple[str, int]:
        """调用上游 LLM，返回 (content, tokens)"""
        result = await self.db.execute(
            select(ModelConfig).where(
                ModelConfig.model_alias == model_alias,
                ModelConfig.is_active == True,
            )
        )
        model_config = result.scalar_one_or_none()

        if not model_config:
            logger.error(f"Model not found or inactive: {model_alias}")
            return "(error: model not found)", 0

        key_service = ProviderKeyService(self.db)
        provider_key = await key_service.get_available_key(model_config.provider)

        if not provider_key:
            logger.error(f"No available API key for provider: {model_config.provider}")
            return "(error: no available API key)", 0

        adapter = get_adapter(model_config.provider)
        upstream_url = adapter.build_upstream_url(model_config.target_url)
        headers = adapter.build_headers(provider_key.key)
        body = adapter.build_request_body(
            {"messages": messages, "stream": False},
            model_config.target_model,
            {
                "temperature": model_config.default_temperature,
                "max_tokens": model_config.default_max_tokens,
            },
        )

        try:
            client = await get_http_client()
            response = await client.post(
                upstream_url,
                headers=headers,
                json=body,
                timeout=httpx.Timeout(120.0),
            )

            if response.status_code != 200:
                logger.error(f"Upstream error {response.status_code}: {response.text[:500]}")
                return f"(error: upstream returned {response.status_code})", 0

            data = response.json()
            content, _, output_tokens = adapter.extract_response(data)
            return content or "(empty response)", output_tokens

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return f"(error: {str(e)})", 0

    # ---------- 流式发送（主路径）----------

    async def send_message_stream(
        self, conversation_id: UUID, user: User, content: str
    ) -> StreamingResponse | None:
        """发送消息并以 SSE 流式返回 AI 回复。

        通过 StreamForwarder 复用 transport + audit + stats 流水线。
        Chat 特有的事情（保存 AI 消息、自动标题）通过 on_complete 钩子实现。
        """
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return None

        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            tokens=0,
        )
        self.db.add(user_message)
        await self.db.commit()

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        history = result.scalars().all()
        messages = [{"role": msg.role, "content": msg.content} for msg in history]

        # Model config
        result = await self.db.execute(
            select(ModelConfig).where(
                ModelConfig.model_alias == conversation.model,
                ModelConfig.is_active == True,
            )
        )
        model_config = result.scalar_one_or_none()

        if not model_config:
            logger.error(f"Model not found or inactive: {conversation.model}")
            return self._error_stream_response("Model not found or inactive")

        key_service = ProviderKeyService(self.db)
        provider_key = await key_service.get_available_key(model_config.provider)

        if not provider_key:
            logger.error(f"No available API key for provider: {model_config.provider}")
            return self._error_stream_response("No available API key")

        # Build upstream request
        adapter = get_adapter(model_config.provider)
        upstream_url = adapter.build_upstream_url(model_config.target_url)
        upstream_headers = adapter.build_headers(provider_key.key)
        body = adapter.build_request_body(
            {"messages": messages, "stream": True},
            model_config.target_model,
            {
                "temperature": model_config.default_temperature,
                "max_tokens": model_config.default_max_tokens,
            },
        )

        # Estimate request tokens from full message history
        request_tokens = self._estimate_request_tokens(messages)

        # Create pending audit log via AuditService
        audit_service = AuditService(self.db)
        audit_log = await audit_service.create_pending_log(
            user=user,
            model=model_config.model_alias,
            provider=model_config.provider,
            path="/api/chat/conversations/{id}/messages/stream",
            request_body=json.dumps({"content": content}, ensure_ascii=False)[:2000],
            is_stream=True,
        )
        await self.db.commit()
        await self.db.refresh(audit_log)

        # Define on_complete hook: save AI message + auto-title
        conv_id = conversation_id
        user_content = content

        async def on_complete(db, full_content, status_code):
            if not full_content:
                return
            ai_message = Message(
                conversation_id=conv_id,
                role="assistant",
                content=full_content,
                tokens=max(1, len(full_content) // 3),
            )
            db.add(ai_message)

            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            conv = result.scalar_one_or_none()
            if conv and not conv.title and user_content:
                conv.title = user_content[:50]

        # Stream via StreamForwarder
        forwarder = StreamForwarder(self.db, adapter)
        return await forwarder.forward(
            upstream_url=upstream_url,
            upstream_headers=upstream_headers,
            forward_body=body,
            audit_log=audit_log,
            provider_key_id=provider_key.id,
            request_tokens=request_tokens,
            emit_sse=adapter.to_openai_sse,
            accumulate_text=True,
            on_complete=on_complete,
        )

    @staticmethod
    def _error_stream_response(error_message: str) -> StreamingResponse:
        """Return a StreamingResponse that yields a single error then [DONE]."""

        async def error_generator():
            error_msg = json.dumps({"error": {"message": error_message, "type": "service_error"}})
            yield f"data: {error_msg}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @staticmethod
    def _estimate_request_tokens(messages: list[dict]) -> int:
        """Estimate input tokens from full message history."""
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
