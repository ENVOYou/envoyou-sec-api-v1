"""
FastAPI dependencies for authentication and authorization
Role-based access control and permission checking
"""

from typing import List, Optional
from functools import wraps
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.core.security import JWTManager

security = HTTPBearer()
jwt_manager = JWTManager()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    # Verify token
    payload = jwt_manager.verify_token(token, "access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_roles(allowed_roles: List[UserRole]):
    """
    Dependency factory for role-based access control
    Usage: @router.get("/endpoint", dependencies=[Depends(require_roles([UserRole.CFO]))])
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_checker


def require_permission(permission: str):
    """
    Dependency factory for permission-based access control
    Usage: @router.get("/endpoint", dependencies=[Depends(require_permission("read_emissions"))])
    """
    def permission_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        auth_service = AuthService(db)
        
        if not auth_service.authorize_action(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required permission: {permission}"
            )
        
        return current_user
    
    return permission_checker


# Specific role dependencies for common use cases
def get_cfo_user(current_user: User = Depends(require_roles([UserRole.CFO]))) -> User:
    """Require CFO role"""
    return current_user


def get_general_counsel_user(current_user: User = Depends(require_roles([UserRole.GENERAL_COUNSEL]))) -> User:
    """Require General Counsel role"""
    return current_user


def get_finance_team_user(current_user: User = Depends(require_roles([UserRole.FINANCE_TEAM]))) -> User:
    """Require Finance Team role"""
    return current_user


def get_auditor_user(current_user: User = Depends(require_roles([UserRole.AUDITOR]))) -> User:
    """Require Auditor role"""
    return current_user


def get_admin_user(current_user: User = Depends(require_roles([UserRole.ADMIN]))) -> User:
    """Require Admin role"""
    return current_user


def get_approver_user(
    current_user: User = Depends(require_roles([UserRole.CFO, UserRole.GENERAL_COUNSEL]))
) -> User:
    """Require CFO or General Counsel role (can approve reports)"""
    return current_user


def get_audit_access_user(
    current_user: User = Depends(require_roles([UserRole.AUDITOR, UserRole.CFO, UserRole.ADMIN]))
) -> User:
    """Require roles that can access audit trails"""
    return current_user


# Permission-based dependencies
def require_read_emissions(current_user: User = Depends(require_permission("read_emissions"))) -> User:
    """Require read emissions permission"""
    return current_user


def require_write_emissions(current_user: User = Depends(require_permission("write_emissions"))) -> User:
    """Require write emissions permission"""
    return current_user


def require_read_reports(current_user: User = Depends(require_permission("read_reports"))) -> User:
    """Require read reports permission"""
    return current_user


def require_write_reports(current_user: User = Depends(require_permission("write_reports"))) -> User:
    """Require write reports permission"""
    return current_user


def require_approve_reports(current_user: User = Depends(require_permission("approve_reports"))) -> User:
    """Require approve reports permission"""
    return current_user


def require_read_audit_trails(current_user: User = Depends(require_permission("read_audit_trails"))) -> User:
    """Require read audit trails permission"""
    return current_user


def require_manage_epa_data(current_user: User = Depends(require_permission("manage_epa_data"))) -> User:
    """Require manage EPA data permission"""
    return current_user


def require_manage_users(current_user: User = Depends(require_permission("manage_users"))) -> User:
    """Require manage users permission"""
    return current_user


def require_read_validation(current_user: User = Depends(require_permission("read_validation"))) -> User:
    """Require read validation permission"""
    return current_user


def require_write_validation(current_user: User = Depends(require_permission("write_validation"))) -> User:
    """Require write validation permission"""
    return current_user