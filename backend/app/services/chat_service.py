import logging
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message
from app.models.gateway import ModelConfig
from app.models.user import User
from app.services.provider_key_service import ProviderKeyService
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
        # Verify ownership
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
        """发送消息并获取 AI 回复

        1. 验证对话所有权
        2. 保存用户消息
        3. 构建上下文（历史消息）
        4. 调用上游 LLM
        5. 保存 AI 回复
        """
        # 1. Verify ownership
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return None

        # 2. Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            tokens=0,
        )
        self.db.add(user_message)
        await self.db.commit()

        # 3. Build context from conversation history
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        history = result.scalars().all()

        messages = [{"role": msg.role, "content": msg.content} for msg in history]

        # 4. Call upstream LLM via gateway infrastructure
        ai_content, tokens = await self._call_llm(conversation.model, messages)

        # 5. Save AI response
        ai_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_content or "(empty response)",
            tokens=tokens,
        )
        self.db.add(ai_message)

        # Auto-generate title from first user message if not set
        if not conversation.title and content:
            conversation.title = content[:50]

        await self.db.commit()
        await self.db.refresh(ai_message)
        return ai_message

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

        # Delete messages first
        await self.db.execute(
            Message.__table__.delete().where(
                Message.conversation_id == conversation_id
            )
        )
        # Delete conversation
        await self.db.delete(conversation)
        await self.db.commit()
        return True

    async def _call_llm(
        self, model_alias: str, messages: list[dict]
    ) -> tuple[str, int]:
        """调用上游 LLM，返回 (content, tokens)"""
        # Find model config
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

        # Get provider key
        key_service = ProviderKeyService(self.db)
        provider_key = await key_service.get_available_key(model_config.provider)

        if not provider_key:
            logger.error(f"No available API key for provider: {model_config.provider}")
            return "(error: no available API key)", 0

        # Build request
        upstream_url = model_config.target_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider_key.key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_config.target_model,
            "messages": messages,
            "stream": False,
        }
        if model_config.default_temperature is not None:
            body["temperature"] = model_config.default_temperature
        if model_config.default_max_tokens is not None:
            body["max_tokens"] = model_config.default_max_tokens

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
            usage = data.get("usage", {})
            tokens = usage.get("completion_tokens", 0)

            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return content, tokens

            return "(empty response)", tokens

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return f"(error: {str(e)})", 0
