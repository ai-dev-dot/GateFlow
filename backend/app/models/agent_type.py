"""AgentType model — admin-managed enum for tagging API Keys by client/tool."""

import uuid

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class AgentType(Base, TimestampMixin):
    __tablename__ = "agent_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
