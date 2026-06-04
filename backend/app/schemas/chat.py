from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    model: str


class ConversationResponse(BaseModel):
    id: UUID
    model: str
    title: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
