"""
Authentication and authorization schemas
Pydantic models for request/response validation
"""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
import re

from app.models.user import UserRole, UserStatus


class UserCredentials(BaseModel):
    """User login credentials"""

    email: EmailStr
    password: str

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    role: UserRole


class TokenRefresh(BaseModel):
    """Token refresh request"""

    refresh_token: str


class UserCreate(BaseModel):
    """User creation schema"""

    email: EmailStr
    username: str
    full_name: str
    password: str
    role: UserRole
    company_id: Optional[str] = None

    @validator("username")
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserResponse(BaseModel):
    """User response schema"""

    id: UUID
    email: str
    username: str
    full_name: str
    role: UserRole
    status: UserStatus
    is_active: bool
    last_login: Optional[datetime]
    company_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """User update schema"""

    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    is_active: Optional[bool] = None
    company_id: Optional[str] = None


class PasswordChange(BaseModel):
    """Password change schema"""

    current_password: str
    new_password: str
    confirm_password: str

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserPermissions(BaseModel):
    """User permissions response"""

    user_id: str
    role: UserRole
    permissions: dict

    class Config:
        from_attributes = True
