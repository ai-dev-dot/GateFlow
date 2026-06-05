import json
import logging
import time
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
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

        # Estimate request tokens
        request_tokens = max(1, len(content) // 3)

        # Create pending audit log
        audit_log = AuditLog(
            status="pending",
            user_id=user.id,
            username=user.username,
            department=user.department.name if user.department else None,
            model=model_config.model_alias,
            provider=model_config.provider,
            method="POST",
            path="/api/chat/conversations/{id}/messages/stream",
            request_body=json.dumps({"content": content}, ensure_ascii=False)[:2000],
            request_tokens=request_tokens,
            is_stream=True,
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        conv_id = conversation_id
        user_content = content
        audit_log_id = audit_log.id
        provider_key_id = provider_key.id
        start_time = time.monotonic()

        async def stream_generator():
            """Yield OpenAI-format SSE chunks, collecting content for DB save."""
            full_content = ""
            response_tokens = 0
            input_tokens = 0
            status_code = 200
            client = await get_http_client()

            try:
                async with client.stream(
                    "POST",
                    upstream_url,
                    headers=upstream_headers,
                    json=body,
                    timeout=httpx.Timeout(300.0, read=300.0),
                ) as upstream_response:
                    status_code = upstream_response.status_code

                    if status_code != 200:
                        error_body = b""
                        async for chunk in upstream_response.aiter_bytes():
                            error_body += chunk
                        error_text = error_body.decode("utf-8", errors="replace")
                        logger.warning(
                            f"Upstream error {status_code}: {error_text[:500]}"
                        )
                        yield adapter.error_sse(
                            f"Upstream returned {status_code}"
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
                                        if event.input_tokens:
                                            input_tokens = event.input_tokens
                                        if event.output_tokens:
                                            response_tokens = event.output_tokens
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
                status_code = 504
            except Exception as e:
                logger.error(f"Chat stream error: {e}")
                yield adapter.error_sse(str(e), "internal_error")
                status_code = 500
            finally:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                # 必须 await 而非 create_task：前端 onDone 回调会立即调
                # getMessages 重新拉取消息列表。若 create_task 尚未落库就触发
                # getMessages，会出现"AI 消息输出后瞬间消失"的现象。
                # Save response and update stats before stream ends
                try:
                    await self._save_stream_response_with_stats(
                        conv_id=conv_id,
                        user_content=user_content,
                        full_content=full_content,
                        audit_log_id=audit_log_id,
                        provider_key_id=provider_key_id,
                        status_code=status_code,
                        request_tokens=request_tokens,
                        response_tokens=response_tokens,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.error(f"Stream save failed: {e}", exc_info=True)

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

    async def _save_stream_response_with_stats(
        self,
        conv_id: UUID,
        user_content: str,
        full_content: str,
        audit_log_id,
        provider_key_id,
        status_code: int,
        request_tokens: int,
        response_tokens: int,
        latency_ms: int,
    ) -> None:
        """流结束后保存：AI 消息 + 更新 audit log + 更新 provider key 统计。

        注意：用量统计从 AuditLog 实时聚合，不再单独维护 UsageStat。
        """
        try:
            from app.database import async_session

            async with async_session() as db:
                # Save AI message
                if full_content:
                    ai_message = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_content,
                        tokens=max(1, len(full_content) // 3),
                    )
                    db.add(ai_message)

                    result = await db.execute(
                        select(Conversation).where(Conversation.id == conv_id)
                    )
                    conversation = result.scalar_one_or_none()
                    if conversation and not conversation.title and user_content:
                        conversation.title = user_content[:50]

                # Update audit log
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

                # Update provider key stats
                key_service = ProviderKeyService(db)
                if status_code == 200:
                    await key_service.update_key_success(
                        provider_key_id, request_tokens, response_tokens
                    )
                else:
                    await key_service.update_key_error(provider_key_id, status_code)

                await db.commit()
                logger.info(
                    f"Saved streamed response for conversation {conv_id}"
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
