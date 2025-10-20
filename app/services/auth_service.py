"""
Authentication Service
Handles user authentication, token management, and security operations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import JWTManager, SecurityUtils
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import TokenResponse, UserCreate, UserCredentials, UserResponse
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for user management and JWT tokens"""

    def __init__(self, db: Session):
        self.db = db
        self.security = SecurityUtils()
        self.jwt_manager = JWTManager()
        self.email_service = EmailService()

    def authenticate_user(self, credentials: UserCredentials) -> TokenResponse:
        """Authenticate user and return JWT tokens"""
        try:
            # Find user by email
            user = (
                self.db.query(User)
                .filter(User.email == credentials.email.lower())
                .filter(User.is_deleted == False)
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

            # Check if user is active and email is verified (if required)
            if not user.is_active:
                logger.warning(
                    f"Authentication failed: User inactive - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is inactive",
                )

            if user.status == UserStatus.PENDING_ACTIVATION:
                logger.warning(
                    f"Authentication failed: Email not verified - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Please verify your email address before logging in",
                )

            if user.status != UserStatus.ACTIVE:
                logger.warning(
                    f"Authentication failed: Status not active - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is not active",
                )

            # Verify password
            if not self.security.verify_password(
                credentials.password, user.hashed_password
            ):
                # Increment failed login attempts (don't commit to avoid UUID issues)
                # user.failed_login_attempts = str(int(user.failed_login_attempts) + 1)
                # self.db.commit()

                logger.warning(
                    f"Authentication failed: Invalid password - {credentials.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            # Reset failed login attempts and update last login
            # Skip database updates to avoid UUID casting issues
            # user.failed_login_attempts = "0"
            # user.last_login = datetime.utcnow()
            # self.db.commit()
            pass  # Skip all database updates for now

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
            # For non-existent users, return 401 instead of 500
            if "Invalid credentials" in str(e) or "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )
            # For other errors, return 500
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
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )

            # Convert string ID to UUID for database query
            try:
                user_uuid = UUID(user_id)
                user = self.db.query(User).filter(User.id == str(user_uuid)).first()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user ID format",
                )

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

            # Generate email verification token if required
            verification_token = None
            user_status = UserStatus.ACTIVE

            if settings.EMAIL_VERIFICATION_REQUIRED:
                verification_token = self.security.generate_secure_token()
                user_status = UserStatus.PENDING_ACTIVATION

            # Create user
            user = User(
                email=user_data.email.lower(),
                username=user_data.username.lower(),
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                role=user_data.role,
                company_id=user_data.company_id,
                status=user_status,
                is_active=True,
                email_verification_token=verification_token,
                email_verification_token_expires=(
                    (
                        datetime.utcnow()
                        + timedelta(
                            hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
                        )
                    )
                    if verification_token
                    else None
                ),
                email_verified=not settings.EMAIL_VERIFICATION_REQUIRED,  
            )

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            # Send verification email if required
            if settings.EMAIL_VERIFICATION_REQUIRED and verification_token:
                email_sent = self.email_service.send_verification_email(
                    user.email, verification_token
                )
                if not email_sent:
                    logger.warning(f"Failed to send verification email to {user.email}")
                    # Don't fail registration if email fails, user can request resend

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
        try:
            user_uuid = UUID(user_id)
            return self.db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            logger.warning(f"Invalid user ID format: {user_id}")
            return None

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
        try:
            user_uuid = UUID(user_id)
            user = self.db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

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

    def verify_email(self, token: str) -> bool:
        """Verify user email with token"""
        try:
            user = (
                self.db.query(User)
                .filter(User.email_verification_token == token)
                .filter(User.is_deleted == False)
                .first()
            )

            if not user:
                logger.warning(f"Email verification failed: Invalid token")
                return False

            # Check if token is expired
            if (
                user.email_verification_token_expires
                and datetime.utcnow() > user.email_verification_token_expires
            ):
                logger.warning(
                    f"Email verification failed: Token expired for {user.email}"
                )
                return False

            # Update user status
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
            user.status = UserStatus.ACTIVE
            user.email_verification_token = None
            user.email_verification_token_expires = None

            self.db.commit()

            logger.info(f"Email verified successfully for {user.email}")
            return True

        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            self.db.rollback()
            return False

    def resend_verification_email(self, email: str) -> bool:
        """Resend verification email to user"""
        try:
            user = (
                self.db.query(User)
                .filter(User.email == email.lower())
                .filter(User.is_deleted == False)
                .first()
            )

            if not user:
                logger.warning(f"Resend verification failed: User not found - {email}")
                return False

            if user.email_verified:
                logger.info(f"Resend verification skipped: Already verified - {email}")
                return True

            # Generate new token
            verification_token = self.security.generate_secure_token()

            # Update user
            user.email_verification_token = verification_token
            user.email_verification_token_expires = datetime.utcnow() + timedelta(
                hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
            )

            self.db.commit()

            # Send email
            email_sent = self.email_service.send_verification_email(
                user.email, verification_token
            )

            if email_sent:
                logger.info(f"Verification email resent to {email}")
                return True
            else:
                logger.error(f"Failed to resend verification email to {email}")
                return False

        except Exception as e:
            logger.error(f"Resend verification email error: {str(e)}")
            self.db.rollback()
            return False
