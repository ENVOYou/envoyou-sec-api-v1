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
    # Use require for production/staging (Neon), prefer for local development
    ssl_mode = (
        "require" if settings.ENVIRONMENT in ["staging", "production"] else "prefer"
    )

    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args={
            "sslmode": ssl_mode,
            "connect_timeout": 10,  # Connection timeout
            "options": f"-c statement_timeout={settings.DATABASE_STATEMENT_TIMEOUT}",  # Query timeout
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


def get_connection_pool_stats():
    """Get database connection pool statistics"""
    pool = engine.pool
    return {
        "pool_size": getattr(pool, "size", 0),
        "checkedin": getattr(pool, "_checkedin", 0),
        "checkedout": getattr(pool, "_checkedout", 0),
        "invalid": getattr(pool, "_invalid", 0),
        "overflow": getattr(pool, "_overflow", 0),
        "pool_timeout": getattr(pool, "timeout", 0),
        "pool_recycle": getattr(pool, "recycle", 0),
    }


def health_check():
    """Perform database health check"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True, "Database connection healthy"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"
