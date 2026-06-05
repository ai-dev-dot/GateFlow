import secrets
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


def generate_api_key() -> str:
    """Generate a unique API key with 'gf_' prefix."""
    return "gf_" + secrets.token_urlsafe(45)


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key = Column(String(64), unique=True, index=True, nullable=False)
    permissions = Column(JSON, nullable=True)  # list of permission strings
    rate_limit = Column(Integer, default=60, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    agent_type_id = Column(UUID(as_uuid=True), ForeignKey("agent_types.id"), nullable=True)

    agent_type = relationship("AgentType", lazy="joined")
