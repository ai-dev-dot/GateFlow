import secrets
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
from app.utils.hashing import api_key_prefix, hash_api_key


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new client API key.

    Returns (full_key, key_prefix, key_hash):
    - full_key: "gf_" + 60 random chars, shown to user ONCE on creation
    - key_prefix: first 11 chars for display ("gf_" + 8 random chars)
    - key_hash: HMAC-SHA256 hex digest for indexed DB lookup

    Plaintext `full_key` is the caller's responsibility to surface
    immediately and never persist beyond the create response.
    """
    full = "gf_" + secrets.token_urlsafe(45)
    return full, api_key_prefix(full), hash_api_key(full)


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    # HMAC-SHA256 hex digest, indexed for O(1) auth lookup. Never store plaintext.
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    # Display-only short form, e.g. "gf_aB3cD4eF". Safe to log/show.
    key_prefix = Column(String(12), nullable=False)
    permissions = Column(JSON, nullable=True)  # list of permission strings
    rate_limit = Column(Integer, default=60, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    agent_type_id = Column(UUID(as_uuid=True), ForeignKey("agent_types.id"), nullable=True)

    agent_type = relationship("AgentType", lazy="joined")
