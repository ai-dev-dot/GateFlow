from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelConfigCreate(BaseModel):
    model_alias: str
    provider: str
    target_model: str
    target_url: str
    priority: int = 0
    default_temperature: float | None = None
    default_max_tokens: int | None = None


class ModelConfigUpdate(BaseModel):
    model_alias: str | None = None
    provider: str | None = None
    target_model: str | None = None
    target_url: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    default_temperature: float | None = None
    default_max_tokens: int | None = None


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_alias: str
    provider: str
    target_model: str
    target_url: str
    is_active: bool
    priority: int
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    created_at: datetime
    updated_at: datetime
