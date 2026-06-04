from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# --- Department ---

class DepartmentCreate(BaseModel):
    name: str
    parent_id: Optional[UUID] = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    parent_id: Optional[UUID] = None


# --- Role ---

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    permissions: Optional[List[str]] = None


# --- User ---

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    department_id: Optional[UUID] = None
    role_id: UUID


class UserUpdate(BaseModel):
    email: Optional[str] = None
    department_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    department_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
