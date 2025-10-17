"""
Application Configuration Settings
Handles environment variables and application settings
"""

import os
from typing import List, Optional, Union

from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    APP_NAME: str = "ENVOYOU SEC API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # reCAPTCHA Configuration
    RECAPTCHA_SECRET_KEY: Optional[str] = None
    RECAPTCHA_MIN_SCORE: float = 0.5  # Minimum score for verification (0.0-1.0)
    SKIP_RECAPTCHA: bool = False  # Skip verification in development/testing

    # Staging Authentication
    STAGING_USERNAME: str = "husni"
    STAGING_PASSWORD: str = "0258520258"

    # Encryption
    ENCRYPTION_MASTER_KEY: Optional[str] = None  # Base64 encoded Fernet key
    ENCRYPT_SENSITIVE_DATA: bool = True  # Enable/disable data encryption

    # HTTPS/SSL Configuration
    FORCE_HTTPS: bool = True  # Force HTTPS in production
    SSL_CERT_PATH: Optional[str] = None  # Path to SSL certificate
    SSL_KEY_PATH: Optional[str] = None  # Path to SSL private key

    # Backup Configuration
    BACKUP_DIR: str = "./backups"  # Directory for backups
    BACKUP_RETENTION_DAYS: int = 30  # Days to keep backups
    MAX_BACKUP_COUNT: int = 10  # Maximum number of backups to keep
    BACKUP_SCHEDULE: str = "0 2 * * *"  # Daily at 2 AM (cron format)

    # CORS
    CORS_ORIGINS: List[str] = [
        "https://envoyou.com",
        "https://app.envoyou.com",
        "https://staging.envoyou.com",
        "https://staging-api.envoyou.com",  # Allow API to API calls
        "http://localhost:3000",
        "http://localhost:3001",  # Dashboard port
        "http://localhost:5173",
        "https://envoyou-sec-api-v1.onrender.com",
    ]
    ALLOWED_HOSTS: List[str] = [
        "localhost",
        "127.0.0.1",
        "testserver",
        "api.envoyou.com",
        "envoyou-sec-api-v1.onrender.com",
    ]

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/envoyou_sec"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    DATABASE_POOL_TIMEOUT: int = 30  # Connection timeout in seconds
    DATABASE_STATEMENT_TIMEOUT: int = 30000  # 30 second query timeout

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_EXPIRE_SECONDS: int = 3600

    # EPA API Configuration
    EPA_API_BASE_URL: str = "https://api.epa.gov"
    EPA_API_KEY: Optional[str] = None
    EPA_DATA_CACHE_HOURS: int = 24
    EPA_REQUEST_TIMEOUT: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 200

    # Monitoring
    PROMETHEUS_METRICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    # File Storage
    UPLOAD_MAX_SIZE_MB: int = 50
    REPORT_STORAGE_PATH: str = "./storage/reports"

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production", "testing"]:
            raise ValueError(
                "ENVIRONMENT must be development, staging, production, or testing"
            )
        return v

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle empty string case
            if not v.strip():
                return ["*"]  # Default to allow all if empty
            # Handle single URL without comma
            if "," not in v:
                return [v.strip()]
            # Handle comma-separated URLs
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        """Converts a comma-separated string from .env to a list of strings."""
        if isinstance(v, str):
            if not v.strip():
                # Jika string dari .env kosong, gunakan nilai default yang ada di kelas
                return cls.__fields__["ALLOWED_HOSTS"].default
            return [host.strip() for host in v.split(",")]
        return v

    @validator("DATABASE_URL", pre=True)
    def override_database_url_for_testing(cls, v):
        if os.getenv("TESTING") == "true":
            return "sqlite:///./test_envoyou_sec.db"
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Override settings for testing
        if os.getenv("TESTING") == "true":
            self.DATABASE_URL = "sqlite:///./test_envoyou_sec.db"
            self.ENVIRONMENT = "testing"


# Global settings instance
settings = Settings()
