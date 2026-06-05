from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderKeyCreate(BaseModel):
    provider: str
    key: str
    name: str
    remark: str | None = None
    rpm_limit: int = 60
    tpm_limit: int = 100000


class ProviderKeyUpdate(BaseModel):
    name: str | None = None
    remark: str | None = None
    is_active: bool | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None


class ProviderKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    key: str
    name: str
    remark: str | None = None
    is_active: bool
    is_banned: bool
    ban_reason: str | None = None
    rpm_limit: int
    tpm_limit: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    consecutive_errors: int
    cool_down_until: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
