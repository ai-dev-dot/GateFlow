from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelConfigCreate(BaseModel):
    model_alias: str
    provider: str
    target_model: str
    target_url: str
    priority: int = 0
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None


class ModelConfigUpdate(BaseModel):
    model_alias: Optional[str] = None
    provider: Optional[str] = None
    target_model: Optional[str] = None
    target_url: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_alias: str
    provider: str
    target_model: str
    target_url: str
    is_active: bool
    priority: int
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    created_at: datetime
    updated_at: datetime
