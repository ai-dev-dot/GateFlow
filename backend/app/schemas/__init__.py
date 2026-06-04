from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    PasswordChangeRequest,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    RoleResponse,
    DepartmentCreate,
    DepartmentResponse,
)
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
)
from app.schemas.provider_key import (
    ProviderKeyCreate,
    ProviderKeyUpdate,
    ProviderKeyResponse,
)
from app.schemas.gateway import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "PasswordChangeRequest",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "RoleResponse",
    "DepartmentCreate",
    "DepartmentResponse",
    # API Key
    "APIKeyCreate",
    "APIKeyUpdate",
    "APIKeyResponse",
    # Provider Key
    "ProviderKeyCreate",
    "ProviderKeyUpdate",
    "ProviderKeyResponse",
    # Gateway / Model Config
    "ModelConfigCreate",
    "ModelConfigUpdate",
    "ModelConfigResponse",
]
