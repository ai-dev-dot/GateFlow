from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderKeyCreate(BaseModel):
    provider: str
    key: str
    name: str
    remark: Optional[str] = None
    rpm_limit: int = 60
    tpm_limit: int = 100000


class ProviderKeyUpdate(BaseModel):
    name: Optional[str] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None


class ProviderKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    key: str
    name: str
    remark: Optional[str] = None
    is_active: bool
    is_banned: bool
    ban_reason: Optional[str] = None
    rpm_limit: int
    tpm_limit: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    consecutive_errors: int
    cool_down_until: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
