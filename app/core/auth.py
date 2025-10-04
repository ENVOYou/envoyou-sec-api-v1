"""
Authentication and Authorization utilities
Role-based access control and permission management
"""

from functools import wraps
from typing import Callable, List

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.user import User, UserRole


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Decorator factory for role-based access control

    Args:
        allowed_roles: List of allowed role names

    Returns:
        Dependency function that validates user role
    """

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_dependency


def require_permissions(required_permissions: List[str]) -> Callable:
    """
    Decorator factory for permission-based access control

    Args:
        required_permissions: List of required permission names

    Returns:
        Dependency function that validates user permissions
    """

    def permission_dependency(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = current_user.get_permissions()

        missing_permissions = []
        for permission in required_permissions:
            if not user_permissions.get(permission, False):
                missing_permissions.append(permission)

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permissions: {', '.join(missing_permissions)}",
            )

        return current_user

    return permission_dependency


class AuthorizationChecker:
    """Authorization checking utilities"""

    @staticmethod
    def can_access_emissions_data(user: User, action: str = "read") -> bool:
        """Check if user can access emissions data"""
        permissions = user.get_permissions()

        if action == "read":
            return permissions.get("read_emissions", False)
        elif action == "write":
            return permissions.get("write_emissions", False)

        return False

    @staticmethod
    def can_access_reports(user: User, action: str = "read") -> bool:
        """Check if user can access reports"""
        permissions = user.get_permissions()

        if action == "read":
            return permissions.get("read_reports", False)
        elif action == "write":
            return permissions.get("write_reports", False)
        elif action == "approve":
            return permissions.get("approve_reports", False)

        return False

    @staticmethod
    def can_access_audit_trails(user: User) -> bool:
        """Check if user can access audit trails"""
        permissions = user.get_permissions()
        return permissions.get("read_audit_trails", False)

    @staticmethod
    def can_manage_epa_data(user: User) -> bool:
        """Check if user can manage EPA data"""
        permissions = user.get_permissions()
        return permissions.get("manage_epa_data", False)

    @staticmethod
    def can_manage_users(user: User) -> bool:
        """Check if user can manage users"""
        permissions = user.get_permissions()
        return permissions.get("manage_users", False)

    @staticmethod
    def can_access_validation(user: User, action: str = "read") -> bool:
        """Check if user can access validation features"""
        permissions = user.get_permissions()

        if action == "read":
            return permissions.get("read_validation", False)
        elif action == "write":
            return permissions.get("write_validation", False)

        return False

    @staticmethod
    def is_admin_or_higher(user: User) -> bool:
        """Check if user is admin or has higher privileges"""
        return user.role in [UserRole.ADMIN]

    @staticmethod
    def is_cfo_or_higher(user: User) -> bool:
        """Check if user is CFO or has higher privileges"""
        return user.role in [UserRole.CFO, UserRole.ADMIN]

    @staticmethod
    def is_general_counsel_or_higher(user: User) -> bool:
        """Check if user is General Counsel or has higher privileges"""
        return user.role in [UserRole.GENERAL_COUNSEL, UserRole.CFO, UserRole.ADMIN]

    @staticmethod
    def is_finance_team_or_higher(user: User) -> bool:
        """Check if user is Finance Team or has higher privileges"""
        return user.role in [
            UserRole.FINANCE_TEAM,
            UserRole.GENERAL_COUNSEL,
            UserRole.CFO,
            UserRole.ADMIN,
        ]

    @staticmethod
    def can_approve_calculations(user: User) -> bool:
        """Check if user can approve calculations"""
        return user.role in [UserRole.CFO, UserRole.GENERAL_COUNSEL, UserRole.ADMIN]

    @staticmethod
    def can_access_forensic_reports(user: User) -> bool:
        """Check if user can access forensic reports"""
        return user.role in [
            UserRole.CFO,
            UserRole.GENERAL_COUNSEL,
            UserRole.AUDITOR,
            UserRole.ADMIN,
        ]


# Convenience functions for common authorization checks
def require_admin():
    """Require admin role"""
    return require_roles(["admin"])


def require_cfo():
    """Require CFO role or higher"""
    return require_roles(["cfo", "admin"])


def require_general_counsel():
    """Require General Counsel role or higher"""
    return require_roles(["general_counsel", "cfo", "admin"])


def require_finance_team():
    """Require Finance Team role or higher"""
    return require_roles(["finance_team", "general_counsel", "cfo", "admin"])


def require_auditor():
    """Require Auditor role or higher"""
    return require_roles(["auditor", "admin"])


def require_emissions_read():
    """Require permission to read emissions data"""
    return require_permissions(["read_emissions"])


def require_emissions_write():
    """Require permission to write emissions data"""
    return require_permissions(["write_emissions"])


def require_reports_approve():
    """Require permission to approve reports"""
    return require_permissions(["approve_reports"])


def require_audit_access():
    """Require permission to access audit trails"""
    return require_permissions(["read_audit_trails"])


def require_epa_management():
    """Require permission to manage EPA data"""
    return require_permissions(["manage_epa_data"])
