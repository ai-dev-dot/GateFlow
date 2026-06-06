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
    """List/get response — NEVER includes the plaintext key."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    # Display-only prefix, e.g. "gf_aB3cD4eF". Full key is not recoverable
    # from this (it is HMAC-hashed, one-way).
    key_prefix: str
    permissions: list[str] | None = None
    rate_limit: int
    expires_at: datetime | None = None
    is_active: bool
    agent_type_id: UUID | None = None
    created_at: datetime
    last_used_at: datetime | None = None


class APIKeyCreated(BaseModel):
    """Create response — includes plaintext key ONE TIME.

    The frontend must display this prominently with a "save now" warning.
    After this response, the server has no way to recover the plaintext
    (it only stored the HMAC hash).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str  # Full plaintext key, e.g. "gf_aB3cD4eF5gH6iJ7kL8mN..."
    key_prefix: str
    permissions: list[str] | None = None
    rate_limit: int
    expires_at: datetime | None = None
    is_active: bool
    agent_type_id: UUID | None = None
    created_at: datetime
    last_used_at: datetime | None = None
