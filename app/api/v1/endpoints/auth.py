"""
Authentication endpoints
JWT-based authentication with role-based access control
"""

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditLogger
from app.core.dependencies import get_admin_user, get_current_active_user, require_auditor
from app.core.rate_limiting import SLOWAPI_AVAILABLE, limiter
from app.core.security import JWTManager

if SLOWAPI_AVAILABLE:
    from slowapi.util import get_remote_address
else:

    def get_remote_address(request):
        return (
            getattr(request, "client", None)
            and getattr(request.client, "host", "unknown")
            or "unknown"
        )


# Conditional rate limiting decorator
def conditional_rate_limit(limit_string: str):
    """Apply rate limiting only when not in testing environment"""

    def decorator(func):
        # Don't apply rate limiting during testing
        if SLOWAPI_AVAILABLE and os.getenv("TESTING") != "true":
            return limiter.limit(limit_string)(func)
        return func  # Return function unchanged if rate limiting not applicable

    return decorator


from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserCredentials,
    UserPermissions,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()
jwt_manager = JWTManager()


@router.post("/login", response_model=TokenResponse)
@conditional_rate_limit("5 per minute")
async def login(
    credentials: UserCredentials, request: Request, db: Session = Depends(get_db)
):
    """
    User authentication endpoint
    Returns JWT access and refresh tokens
    """
    auth_service = AuthService(db)
    audit_logger = AuditLogger(db)

    # Get request metadata
    request_id = getattr(request.state, "request_id", None)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        token_response = auth_service.authenticate_user(credentials)

        # Log successful authentication
        audit_logger.log_authentication_event(
            event_type="LOGIN_SUCCESS",
            user_email=credentials.email,
            success=True,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return token_response

    except HTTPException as e:
        # Log failed authentication
        audit_logger.log_authentication_event(
            event_type="LOGIN_FAILED",
            user_email=credentials.email,
            success=False,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=e.detail,
        )
        raise


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token
    """
    auth_service = AuthService(db)
    return auth_service.refresh_token(token_data.refresh_token)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    User logout endpoint
    In a stateless JWT system, logout is handled client-side
    This endpoint can be used for audit logging
    """
    audit_logger = AuditLogger(db)

    # Log logout event
    audit_logger.log_authentication_event(
        event_type="LOGOUT",
        user_email=current_user.email,
        success=True,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        additional_data={"user_id": str(current_user.id)},
    )

    return {"message": "Successfully logged out", "user_id": str(current_user.id)}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information
    """
    return UserResponse.from_orm(current_user)


@router.get("/permissions", response_model=UserPermissions)
async def get_user_permissions(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """
    Get current user permissions based on role
    """
    auth_service = AuthService(db)
    permissions_data = auth_service.get_user_permissions(current_user)

    return UserPermissions(
        user_id=permissions_data["user_id"],
        role=current_user.role,
        permissions=permissions_data["permissions"],
    )


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),  # Use admin dependency
):
    """
    Register new user (Admin only)
    """
    auth_service = AuthService(db)
    audit_logger = AuditLogger(db)

    try:
        new_user = auth_service.create_user(user_data)

        # Log user creation
        audit_logger.log_data_access_event(
            user=current_user,
            resource_type="user",
            resource_id=str(new_user.id),
            action="CREATE",
            request_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
            endpoint="/v1/auth/register",
            additional_data={
                "new_user_email": new_user.email,
                "new_user_role": new_user.role.value,
            },
        )

        return new_user

    except Exception as e:
        # Log failed user creation
        audit_logger.log_data_access_event(
            user=current_user,
            resource_type="user",
            resource_id="unknown",
            action="CREATE_FAILED",
            request_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
            endpoint="/v1/auth/register",
            additional_data={"attempted_email": user_data.email, "error": str(e)},
        )
        raise


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Change user password
    """
    from datetime import datetime

    auth_service = AuthService(db)

    # Verify current password
    if not auth_service.security.verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    current_user.hashed_password = auth_service.security.get_password_hash(
        password_data.new_password
    )
    current_user.password_changed_at = datetime.utcnow()

    db.commit()

    return {"message": "Password changed successfully"}


@router.post("/audit-session")
async def create_audit_session(
    current_user: User = Depends(require_auditor), db: Session = Depends(get_db)
):
    """
    Create audit session for external auditors
    """
    auth_service = AuthService(db)
    return auth_service.create_audit_session(str(current_user.id))
