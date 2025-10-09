"""
ENVOYOU SEC API - Main FastAPI Application
Climate Disclosure Rule Compliance Platform for US Public Companies
"""

import uvicorn
from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.database import get_db
from app.core.middleware import AuditMiddleware, ErrorHandlingMiddleware
from app.core.health_checks import get_detailed_health_status
from app.core.metrics import MetricsMiddleware, get_metrics, PROMETHEUS_AVAILABLE
from app.core.rate_limiting import limiter, rate_limit_exceeded_handler, SLOWAPI_AVAILABLE
from app.core.security_headers import SecurityHeadersMiddleware
from app.services.background_tasks import task_manager

if SLOWAPI_AVAILABLE:
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.errors import RateLimitExceeded

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
    """Comprehensive health check endpoint for monitoring"""
    health_status = await get_detailed_health_status(db)

    # For simple health checks (like load balancers), return simple response
    # For detailed monitoring, return full status
    if health_status["status"] == "healthy":
        return {
            "status": "healthy",
            "service": "envoyou-sec-api",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "timestamp": health_status["timestamp"],
        }
    else:
        # Return detailed status for troubleshooting
        return health_status


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if settings.ENVIRONMENT not in ["production", "staging"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Metrics not available in this environment")

    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
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
