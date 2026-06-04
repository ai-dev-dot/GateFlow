import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class ProviderAPIKey(Base, TimestampMixin):
    __tablename__ = "provider_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), index=True, nullable=False)
    key = Column(String(255), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    remark = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(String(255), nullable=True)
    rpm_limit = Column(Integer, default=60, nullable=False)
    tpm_limit = Column(Integer, default=100000, nullable=False)
    total_requests = Column(BigInteger, default=0, nullable=False)
    total_input_tokens = Column(BigInteger, default=0, nullable=False)
    total_output_tokens = Column(BigInteger, default=0, nullable=False)
    consecutive_errors = Column(Integer, default=0, nullable=False)
    cool_down_until = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True, index=True)
