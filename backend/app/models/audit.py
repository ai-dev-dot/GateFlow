import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), default="pending", index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    username = Column(String(50), nullable=False)
    department = Column(String(100), nullable=True)
    api_key_id = Column(
        UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True
    )
    model = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    request_body = Column(Text, nullable=True)
    request_tokens = Column(Integer, default=0, nullable=False)
    response_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    is_stream = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_dept_timestamp", "department", "timestamp"),
        Index("ix_audit_logs_model_timestamp", "model", "timestamp"),
    )
