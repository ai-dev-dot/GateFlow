import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

import httpx
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message
from app.models.gateway import ModelConfig
from app.models.user import User
from app.services.provider_key_service import ProviderKeyService
from app.services.provider_adapters import get_adapter
from app.services.provider_adapters.base import BaseAdapter, StreamEvent
from app.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, user: User, model: str) -> Conversation:
        """创建新对话"""
        conversation = Conversation(
            user_id=user.id,
            model=model,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversations(self, user: User) -> list[Conversation]:
        """获取用户所有对话列表"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_messages(
        self, conversation_id: UUID, user: User
    ) -> list[Message]:
        """获取对话消息列表（验证所有权）"""
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

    async def send_message(
        self, conversation_id: UUID, user: User, content: str
    ) -> Optional[Message]:
        """发送消息并获取 AI 回复"""
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

    async def send_message_stream(
        self, conversation_id: UUID, user: User, content: str
    ) -> Optional[StreamingResponse]:
        """发送消息并以 SSE 流式返回 AI 回复

        The frontend always receives OpenAI-format SSE (choices[].delta.content).
        If the upstream provider uses a different protocol (e.g. Anthropic),
        the adapter converts the events client-side.
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

        # Get model config
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

        # Use adapter for protocol handling
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

        conv_id = conversation_id
        user_content = content

        async def stream_generator():
            """Yield OpenAI-format SSE chunks, collecting content for DB save."""
            full_content = ""
            client = await get_http_client()

            try:
                async with client.stream(
                    "POST",
                    upstream_url,
                    headers=upstream_headers,
                    json=body,
                    timeout=httpx.Timeout(300.0, read=300.0),
                ) as upstream_response:
                    if upstream_response.status_code != 200:
                        error_body = b""
                        async for chunk in upstream_response.aiter_bytes():
                            error_body += chunk
                        error_text = error_body.decode("utf-8", errors="replace")
                        logger.warning(
                            f"Upstream error {upstream_response.status_code}: {error_text[:500]}"
                        )
                        yield adapter.error_sse(
                            f"Upstream returned {upstream_response.status_code}"
                        )
                        return

                    buffer_lines: list[str] = []
                    async for chunk in upstream_response.aiter_bytes():
                        chunk_text = chunk.decode("utf-8", errors="replace")
                        for line in chunk_text.split("\n"):
                            line = line.strip()
                            if not line:
                                if buffer_lines:
                                    event = adapter.parse_stream_event(buffer_lines)
                                    if event:
                                        full_content += event.text
                                        # Convert to OpenAI SSE for frontend
                                        openai_sse = adapter.to_openai_sse(event)
                                        if openai_sse:
                                            yield openai_sse
                                    buffer_lines = []
                                continue
                            buffer_lines.append(line)

            except httpx.ReadTimeout:
                logger.error("Upstream read timeout during chat stream")
                yield adapter.error_sse("Upstream read timeout", "timeout")
            except Exception as e:
                logger.error(f"Chat stream error: {e}")
                yield adapter.error_sse(str(e), "internal_error")
            finally:
                if full_content:
                    asyncio.create_task(
                        self._save_stream_response(conv_id, user_content, full_content)
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

    @staticmethod
    def _error_stream_response(error_message: str) -> StreamingResponse:
        """Return a StreamingResponse that yields a single error then [DONE]."""

        async def error_generator():
            error_msg = json.dumps(
                {"error": {"message": error_message, "type": "service_error"}}
            )
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

    async def _save_stream_response(
        self,
        conversation_id: UUID,
        user_content: str,
        ai_content: str,
    ) -> None:
        """Background task: save the streamed AI response to the database."""
        try:
            from app.database import async_session

            async with async_session() as db:
                ai_message = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=ai_content,
                    tokens=max(1, len(ai_content) // 3),
                )
                db.add(ai_message)

                result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                if conversation and not conversation.title and user_content:
                    conversation.title = user_content[:50]

                await db.commit()
                logger.info(
                    f"Saved streamed response for conversation {conversation_id}"
                )
        except Exception as e:
            logger.error(f"Failed to save streamed response: {e}", exc_info=True)

    async def delete_conversation(
        self, conversation_id: UUID, user: User
    ) -> bool:
        """删除对话及其消息"""
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
            Message.__table__.delete().where(
                Message.conversation_id == conversation_id
            )
        )
        await self.db.delete(conversation)
        await self.db.commit()
        return True

    async def _call_llm(
        self, model_alias: str, messages: list[dict]
    ) -> tuple[str, int]:
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
                logger.error(
                    f"Upstream error {response.status_code}: {response.text[:500]}"
                )
                return f"(error: upstream returned {response.status_code})", 0

            data = response.json()
            content, _, output_tokens = adapter.extract_response(data)
            return content or "(empty response)", output_tokens

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return f"(error: {str(e)})", 0
