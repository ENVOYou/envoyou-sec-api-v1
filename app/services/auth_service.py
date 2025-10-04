"""
Authentication Service
Handles user authentication, token management, and security operations
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging

from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import UserCredentials, TokenResponse, UserCreate, UserResponse
from app.core.security import SecurityUtils, JWTManager
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for user management and JWT tokens"""

    def __init__(self, db: Session):
        self.db = db
        self.security = SecurityUtils()
        self.jwt_manager = JWTManager()

    def authenticate_user(self, credentials: UserCredentials) -> TokenResponse:
        """Authenticate user and return JWT tokens"""
        try:
            # Find user by email
            user = (
                self.db.query(User)
                .filter(User.email == credentials.email.lower())
                .first()
            )

            if not user:
                logger.warning(
                    f"Authentication failed: User not found - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            # Check if user is active
            if not user.is_active or user.status != UserStatus.ACTIVE:
                logger.warning(
                    f"Authentication failed: User inactive - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is inactive",
                )

            # Verify password
            if not self.security.verify_password(
                credentials.password, user.hashed_password
            ):
                # Increment failed login attempts
                user.failed_login_attempts = str(int(user.failed_login_attempts) + 1)
                self.db.commit()

                logger.warning(
                    f"Authentication failed: Invalid password - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            # Reset failed login attempts and update last login
            user.failed_login_attempts = "0"
            user.last_login = datetime.utcnow()
            self.db.commit()

            # Create token payload
            token_data = {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "company_id": user.company_id,
            }

            # Generate tokens
            access_token = self.jwt_manager.create_access_token(token_data)
            refresh_token = self.jwt_manager.create_refresh_token({"sub": str(user.id)})

            logger.info(f"User authenticated successfully - {credentials.email}")

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user_id=str(user.id),
                role=user.role,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )

    def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        try:
            # Verify refresh token
            payload = self.jwt_manager.verify_token(refresh_token, "refresh")
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            # Get user
            user_id = payload.get("sub")
            user = self.db.query(User).filter(User.id == user_id).first()

            if not user or not user.is_active or user.status != UserStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                )

            # Create new token payload
            token_data = {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "company_id": user.company_id,
            }

            # Generate new tokens
            access_token = self.jwt_manager.create_access_token(token_data)
            new_refresh_token = self.jwt_manager.create_refresh_token(
                {"sub": str(user.id)}
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user_id=str(user.id),
                role=user.role,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh service error",
            )

    def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create new user account"""
        try:
            # Check if user already exists
            existing_user = (
                self.db.query(User)
                .filter(
                    (User.email == user_data.email.lower())
                    | (User.username == user_data.username.lower())
                )
                .first()
            )

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email or username already exists",
                )

            # Hash password
            hashed_password = self.security.get_password_hash(user_data.password)

            # Create user
            user = User(
                email=user_data.email.lower(),
                username=user_data.username.lower(),
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                role=user_data.role,
                company_id=user_data.company_id,
                status=UserStatus.ACTIVE,
                is_active=True,
            )

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"User created successfully - {user_data.email}")

            return UserResponse.from_orm(user)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation service error",
            )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_permissions(self, user: User) -> Dict[str, Any]:
        """Get user permissions based on role"""
        permissions = self.jwt_manager.get_user_permissions(user.role)

        return {
            "user_id": str(user.id),
            "role": user.role.value,
            "permissions": permissions,
        }

    def authorize_action(self, user: User, action: str, resource: str = None) -> bool:
        """Check if user is authorized to perform an action"""
        permissions = self.jwt_manager.get_user_permissions(user.role)

        # Check specific permission
        if action in permissions:
            return permissions[action]

        # Default deny
        return False

    def create_audit_session(self, user_id: str) -> Dict[str, Any]:
        """Create audit session for external auditors"""
        user = self.get_user_by_id(user_id)

        if not user or user.role != UserRole.AUDITOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only auditors can create audit sessions",
            )

        # Generate audit session token
        session_token = self.security.generate_secure_token()
        session_data = {
            "session_id": session_token,
            "auditor_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
        }

        logger.info(f"Audit session created for user {user_id}")

        return session_data
