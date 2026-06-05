from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["问答对话"])


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户所有对话列表"""
    service = ChatService(db)
    conversations = await service.get_conversations(current_user)
    return conversations


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新对话"""
    service = ChatService(db)
    conversation = await service.create_conversation(current_user, body.model)
    return conversation


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取对话消息列表"""
    service = ChatService(db)
    messages = await service.get_messages(conversation_id, current_user)
    if not messages:
        # Could be no messages or conversation not found/not owned
        # We return empty list for empty conversations, 404 for invalid ownership
        # Check if conversation exists for this user
        conversations = await service.get_conversations(current_user)
        conv_ids = {c.id for c in conversations}
        if conversation_id not in conv_ids:
            raise HTTPException(status_code=404, detail="对话不存在")
    return messages


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def send_message(
    conversation_id: UUID,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息并获取 AI 回复"""
    service = ChatService(db)
    message = await service.send_message(conversation_id, current_user, body.content)
    if not message:
        raise HTTPException(status_code=404, detail="对话不存在")
    return message


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    response_class=StreamingResponse,
)
async def send_message_stream(
    conversation_id: UUID,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送消息并以 SSE 流式返回 AI 回复（打字机效果）"""
    service = ChatService(db)
    response = await service.send_message_stream(conversation_id, current_user, body.content)
    if not response:
        raise HTTPException(status_code=404, detail="对话不存在")
    return response


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除对话及其消息"""
    service = ChatService(db)
    deleted = await service.delete_conversation(conversation_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="对话不存在")
    return None
