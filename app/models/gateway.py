import uuid

from sqlalchemy import Boolean, Column, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_alias = Column(String(100), unique=True, index=True, nullable=False)
    provider = Column(String(50), index=True, nullable=False)
    target_model = Column(String(100), nullable=False)
    target_url = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    default_temperature = Column(Float, nullable=True)
    default_max_tokens = Column(Integer, nullable=True)
