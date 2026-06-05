from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIKeyCreate(BaseModel):
    name: str
    permissions: list[str] = []
    rate_limit: int = 60
    expires_at: datetime | None = None
    agent_type_id: UUID | None = None


class APIKeyUpdate(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None
    rate_limit: int | None = None
    is_active: bool | None = None


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str
    permissions: list[str] | None = None
    rate_limit: int
    expires_at: datetime | None = None
    is_active: bool
    agent_type_id: UUID | None = None
    created_at: datetime
    last_used_at: datetime | None = None
