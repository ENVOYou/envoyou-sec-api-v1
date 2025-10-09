"""
Application Configuration Settings
Handles environment variables and application settings
"""

import os
from typing import List, Optional

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

    # CORS
    CORS_ORIGINS: List[str] = [
        "https://envoyou.com",
        "https://app.envoyou.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://envoyou-sec-api-v1.onrender.com",
    ]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "testserver"]

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/envoyou_sec"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

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
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            # Handle empty string case
            if not v.strip():
                return []
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
