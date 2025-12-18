from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


class TokenData(BaseModel):
    """Token data schema"""

    email: Optional[str] = None


class Token(BaseModel):
    """Token response schema"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""

    refresh_token: str


class UserResponse(BaseModel):
    """User response schema"""

    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# Update forward reference
LoginResponse.model_rebuild()
