from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIKeyCreate(BaseModel):
    name: str
    permissions: List[str] = []
    rate_limit: int = 60
    expires_at: Optional[datetime] = None
    agent_type_id: Optional[UUID] = None


class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    rate_limit: Optional[int] = None
    is_active: Optional[bool] = None


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str
    permissions: Optional[List[str]] = None
    rate_limit: int
    expires_at: Optional[datetime] = None
    is_active: bool
    agent_type_id: Optional[UUID] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
