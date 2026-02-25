"""
schemas/user.py
---------------
Pydantic models for User registration, login, and responses.

Security note:
  - hashed_password is NEVER included in any response schema.
  - Passwords require min 8 chars; enforce stronger rules in production.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Used by admin to create a new user within their tenant."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.user


class UserRegister(BaseModel):
    """Self-registration endpoint — tenant_id comes from request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    tenant_id: str = Field(..., description="UUID of the tenant to join")


class UserRead(BaseModel):
    id: str
    email: str
    role: str
    tenant_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserRead
