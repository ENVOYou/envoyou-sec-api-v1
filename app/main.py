"""
ENVOYOU SEC API - Main FastAPI Application
Climate Disclosure Rule Compliance Platform for US Public Companies
"""

import uvicorn
from datetime import datetime
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.health_checks import get_detailed_health_status
from app.core.metrics import PROMETHEUS_AVAILABLE, MetricsMiddleware, get_metrics
from app.core.middleware import AuditMiddleware, ErrorHandlingMiddleware
from app.core.rate_limiting import (
    SLOWAPI_AVAILABLE,
    limiter,
    rate_limit_exceeded_handler,
)
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.database import get_db
from app.services.background_tasks import task_manager

if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

# Create FastAPI application
app = FastAPI(
    title="ENVOYOU SEC API",
    description="Climate Disclosure Rule Compliance Platform for US Public Companies",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Set up rate limiting (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and SLOWAPI_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS middleware for web dashboard integration (simplified)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Response compression middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(SecurityHeadersMiddleware)

# Metrics middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and PROMETHEUS_AVAILABLE:
    app.add_middleware(MetricsMiddleware)

# Rate limiting middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and SLOWAPI_AVAILABLE:
    app.add_middleware(SlowAPIMiddleware)

# Security and audit middleware (only in production/staging for TrustedHost)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(AuditMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/v1")


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Basic health check endpoint for load balancers and monitoring"""
    # Simple health check - just verify the service is running
    # Don't do comprehensive checks that might fail due to external dependencies
    return {
        "status": "healthy",
        "service": "envoyou-sec-api",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Comprehensive health check with dependency verification"""
    try:
        health_status = await get_detailed_health_status(db)
        return health_status
    except Exception as e:
        # Return degraded status if detailed check fails
        return {
            "status": "degraded",
            "service": "envoyou-sec-api",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "error": f"Detailed health check failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Service is running but some dependencies may be unavailable"
        }


@app.get("/debug/db")
async def debug_database(db: Session = Depends(get_db)):
    """Debug endpoint to test database connectivity"""
    try:
        # Test basic connectivity
        result = db.execute(text("SELECT 1 as test, version() as pg_version")).fetchone()

        # Get database info
        db_info = {
            "connection_test": result[0] == 1,
            "postgresql_version": result[1] if len(result) > 1 else "unknown",
            "database_url": settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0].split('//')[1].split(':')[0], "***").replace(settings.DATABASE_URL.split('@')[0].split('//')[1].split(':')[1], "***") if '@' in settings.DATABASE_URL else "masked",
        }

        return {
            "status": "connected",
            "database_info": db_info,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_url_masked": settings.DATABASE_URL.split('@')[0] + "@***:***@" + settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "invalid_url",
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if settings.ENVIRONMENT not in ["production", "staging"]:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="Metrics not available in this environment"
        )

    return Response(
        content=get_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ENVOYOU SEC API - Climate Disclosure Compliance Platform",
        "docs": "/docs",
        "health": "/health",
    }


# Disable startup/shutdown events temporarily
# @app.on_event("startup")
# async def startup_event():
#     """Application startup event"""
#     pass

# @app.on_event("shutdown")
# async def shutdown_event():
#     """Application shutdown event"""
#     pass


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
    )
