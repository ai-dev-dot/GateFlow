from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# --- Department ---


class DepartmentCreate(BaseModel):
    name: str
    parent_id: UUID | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    parent_id: UUID | None = None


# --- Role ---


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    permissions: Any | None = None


# --- User ---


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    department_id: UUID | None = None
    role_id: UUID | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    department_id: UUID | None = None
    role_id: UUID | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    department_id: UUID | None = None
    role_id: UUID | None = None
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None
