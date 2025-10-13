"""
Database configuration and connection management
PostgreSQL with TimescaleDB extension for time-series data
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings

# Determine pool class based on database URL
pool_class = StaticPool if "sqlite" in settings.DATABASE_URL else QueuePool

# Create database engine with connection pooling
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    # Enhanced PostgreSQL connection with SSL and timeout settings
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args={
            "sslmode": "prefer",  # Allow non-SSL for local development
            "connect_timeout": 10,  # Connection timeout
            "options": "-c statement_timeout=30000",  # 30 second query timeout
        },
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables (use with caution)"""
    Base.metadata.drop_all(bind=engine)
