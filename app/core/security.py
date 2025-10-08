"""
Security utilities for authentication and authorization
JWT token handling, password hashing, and security functions
"""

import hashlib

# Password hashing context
# Use pbkdf2_sha256 for testing to avoid bcrypt issues
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.models.user import UserRole

# Always use pbkdf2_sha256 to avoid bcrypt 72-byte limit issues
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class SecurityUtils:
    """Security utility functions"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        # Bcrypt has a 72 byte limit, truncate if necessary
        if len(plain_password.encode("utf-8")) > 72:
            plain_password = plain_password[:72]
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate password hash"""
        # Bcrypt has a 72 byte limit, truncate if necessary
        if len(password.encode("utf-8")) > 72:
            password = password[:72]
        return pwd_context.hash(password)

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()


class JWTManager:
    """JWT token management"""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})

        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )

        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def verify_token(
        token: str, token_type: str = "access"
    ) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )

            # Verify token type
            if payload.get("type") != token_type:
                return None

            # Check expiration
            exp = payload.get("exp")
            if exp is None or datetime.utcnow() > datetime.fromtimestamp(exp):
                return None

            return payload

        except JWTError:
            return None

    @staticmethod
    def get_user_permissions(role: UserRole) -> Dict[str, bool]:
        """Get user permissions based on role"""
        base_permissions = {
            "read_emissions": False,
            "write_emissions": False,
            "read_reports": False,
            "write_reports": False,
            "approve_reports": False,
            "read_audit_trails": False,
            "manage_epa_data": False,
            "manage_users": False,
            "read_validation": False,
            "write_validation": False,
        }

        if role == UserRole.CFO:
            return {
                **base_permissions,
                "read_emissions": True,
                "write_emissions": True,
                "read_reports": True,
                "write_reports": True,
                "approve_reports": True,
                "read_audit_trails": True,
                "read_validation": True,
                "write_validation": True,
            }

        elif role == UserRole.GENERAL_COUNSEL:
            return {
                **base_permissions,
                "read_emissions": True,
                "read_reports": True,
                "write_reports": True,
                "approve_reports": True,
                "read_audit_trails": True,
                "read_validation": True,
            }

        elif role == UserRole.FINANCE_TEAM:
            return {
                **base_permissions,
                "read_emissions": True,
                "write_emissions": True,
                "read_reports": True,
                "write_reports": True,
                "read_validation": True,
                "write_validation": True,
            }

        elif role == UserRole.AUDITOR:
            return {
                **base_permissions,
                "read_emissions": True,
                "read_reports": True,
                "read_audit_trails": True,
                "read_validation": True,
            }

        elif role == UserRole.ADMIN:
            return {
                **base_permissions,
                "read_emissions": True,
                "write_emissions": True,
                "read_reports": True,
                "write_reports": True,
                "read_audit_trails": True,
                "manage_epa_data": True,
                "manage_users": True,
                "read_validation": True,
                "write_validation": True,
            }

        return base_permissions
