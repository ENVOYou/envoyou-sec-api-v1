"""
User model for authentication and authorization
Supports role-based access control for SEC compliance
"""

from sqlalchemy import Column, String, Boolean, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel, AuditMixin


class UserRole(enum.Enum):
    """User roles for SEC Climate Disclosure compliance"""

    CFO = "cfo"
    GENERAL_COUNSEL = "general_counsel"
    FINANCE_TEAM = "finance_team"
    AUDITOR = "auditor"
    ADMIN = "admin"


class UserStatus(enum.Enum):
    """User account status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_ACTIVATION = "pending_activation"


class User(BaseModel, AuditMixin):
    """User model with role-based access control"""

    __tablename__ = "users"

    # Basic user information
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)

    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)

    # Role and permissions
    role = Column(SQLEnum(UserRole), nullable=False)

    # Security tracking
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(String(10), default="0", nullable=False)
    password_changed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Company association (for multi-tenant support)
    company_id = Column(String(36), nullable=True)  # Will be foreign key later

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role.value}')>"

    @property
    def is_cfo(self) -> bool:
        return self.role == UserRole.CFO

    @property
    def is_general_counsel(self) -> bool:
        return self.role == UserRole.GENERAL_COUNSEL

    @property
    def is_finance_team(self) -> bool:
        return self.role == UserRole.FINANCE_TEAM

    @property
    def is_auditor(self) -> bool:
        return self.role == UserRole.AUDITOR

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def can_approve_reports(self) -> bool:
        """Check if user can approve reports"""
        return self.role in [UserRole.CFO, UserRole.GENERAL_COUNSEL]

    def can_access_audit_trails(self) -> bool:
        """Check if user can access audit trails"""
        return self.role in [UserRole.AUDITOR, UserRole.CFO, UserRole.ADMIN]

    def can_manage_epa_data(self) -> bool:
        """Check if user can manage EPA emission factors"""
        return self.role == UserRole.ADMIN

    def can_read_emissions(self) -> bool:
        """Check if user can read emissions data"""
        return self.role in [
            UserRole.CFO,
            UserRole.GENERAL_COUNSEL,
            UserRole.FINANCE_TEAM,
            UserRole.AUDITOR,
            UserRole.ADMIN,
        ]

    def can_write_emissions(self) -> bool:
        """Check if user can write emissions data"""
        return self.role in [UserRole.CFO, UserRole.FINANCE_TEAM, UserRole.ADMIN]

    def get_permissions(self) -> dict:
        """Get all permissions for the user based on their role"""
        from app.core.security import JWTManager

        return JWTManager.get_user_permissions(self.role)
