"""
API Dependencies
Common dependencies for FastAPI endpoints including database sessions,
authentication, and authorization
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.db.database import SessionLocal
from app.core.config import settings
from app.models.user import User
from app.core.security import JWTManager

# Security scheme for JWT token
security = HTTPBearer()


def get_db() -> Generator:
    """
    Database dependency
    Creates and yields database session, ensures proper cleanup
    """
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        db: Database session
        credentials: JWT token from Authorization header
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Extract token from credentials
        token = credentials.credentials
        
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current superuser
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current superuser
        
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user doesn't have enough privileges"
        )
    return current_user


def require_roles(allowed_roles: list):
    """
    Role-based access control dependency factory
    
    Args:
        allowed_roles: List of allowed roles for the endpoint
        
    Returns:
        Dependency function that checks user role
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}"
            )
        return current_user
    
    return role_checker


def require_permissions(required_permissions: list):
    """
    Permission-based access control dependency factory
    
    Args:
        required_permissions: List of required permissions
        
    Returns:
        Dependency function that checks user permissions
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = current_user.get_permissions()
        
        for permission in required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required permission: {permission}"
                )
        
        return current_user
    
    return permission_checker


# Specific role-based dependencies for common use cases
def require_admin():
    """Require admin role"""
    return require_roles(["admin"])


def require_cfo():
    """Require CFO role or higher"""
    return require_roles(["cfo", "admin"])


def require_general_counsel():
    """Require General Counsel role or higher"""
    return require_roles(["general_counsel", "admin"])


def require_finance_team():
    """Require Finance Team role or higher"""
    return require_roles(["finance_team", "cfo", "general_counsel", "admin"])


def require_auditor():
    """Require Auditor role or higher"""
    return require_roles(["auditor", "admin"])


# Permission-based dependencies
def require_read_emissions(current_user: User = Depends(get_current_user)) -> User:
    """Require permission to read emissions data"""
    if not current_user.can_read_emissions():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Permission required: read_emissions"
        )
    return current_user


def require_write_emissions(current_user: User = Depends(get_current_user)) -> User:
    """Require permission to write emissions data"""
    if not current_user.can_write_emissions():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Permission required: write_emissions"
        )
    return current_user


def require_approve_reports(current_user: User = Depends(get_current_user)) -> User:
    """Require permission to approve reports"""
    if not current_user.can_approve_reports():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Permission required: approve_reports"
        )
    return current_user


def require_manage_epa_data(current_user: User = Depends(get_current_user)) -> User:
    """Require permission to manage EPA data"""
    if not current_user.can_manage_epa_data():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Permission required: manage_epa_data"
        )
    return current_user


def require_access_audit_trails(current_user: User = Depends(get_current_user)) -> User:
    """Require permission to access audit trails"""
    if not current_user.can_access_audit_trails():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Permission required: access_audit_trails"
        )
    return current_user


# Optional user dependency (for public endpoints that can work with or without auth)
def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None
    Useful for endpoints that can work with or without authentication
    
    Args:
        db: Database session
        credentials: Optional JWT token from Authorization header
        
    Returns:
        Optional[User]: Current user if authenticated, None otherwise
    """
    if credentials is None:
        return None
    
    try:
        # Extract token from credentials
        token = credentials.credentials
        
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
            
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            return None
        
        return user
        
    except JWTError:
        return None