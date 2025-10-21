"""
ENVOYOU SEC API - Main FastAPI Application
Climate Disclosure Rule Compliance Platform for US Public Companies
"""

from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBasic
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

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

if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

# Create FastAPI application
app = FastAPI(
    title="ENVOYOU SEC API",
    description=("Climate Disclosure Rule Compliance Platform for US Public Companies"),
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    debug=settings.DEBUG,  # Enable debug mode for detailed error logging
)

# Security for staging authentication
security = HTTPBasic()


class StagingAuthMiddleware(BaseHTTPMiddleware):
    """Basic authentication middleware for staging environments"""

    async def dispatch(self, request, call_next):
        if settings.ENVIRONMENT in ["staging", "production"]:
            # Skip auth for health check and public auth endpoints
            if (
                request.url.path == "/health"
                or request.url.path.startswith("/v1/auth/")
                or request.method == "OPTIONS"
            ):
                return await call_next(request)

            # Check for Bearer token first (authenticated requests)
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # Valid Bearer token present, allow request
                pass
            else:
                # No Bearer token, require basic auth
                credentials = None  # Inisialisasi credentials
                try:
                    # Coba dapatkan kredensial Basic Auth
                    credentials = await security(request)
                except HTTPException as e:
                    # Tangkap HTTPException spesifik dari security()
                    # (Misalnya jika header Authorization tidak ada)
                    # Pastikan header WWW-Authenticate ada untuk browser
                    if (
                        e.status_code == HTTP_401_UNAUTHORIZED
                        and "WWW-Authenticate" not in e.headers
                    ):
                        e.headers = {"WWW-Authenticate": "Basic"}
                    # Lempar kembali HTTPException ini agar ditangani framework/ErrorHandlingMiddleware
                    raise e
                # HAPUS blok 'except Exception:' yang luas di sini

                # Jika kredensial BERHASIL didapatkan, periksa nilainya
                if not credentials or not (
                    credentials.username == settings.STAGING_USERNAME
                    and credentials.password == settings.STAGING_PASSWORD
                ):
                    # Jika kredensial salah atau tidak ada (meskipun tidak error saat diambil)
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Invalid or missing staging credentials",
                        headers={"WWW-Authenticate": "Basic"},
                    )
                # Jika kredensial benar, lanjutkan ke middleware/route berikutnya (tidak perlu raise)

        # Jika otentikasi berhasil atau tidak diperlukan
        response = await call_next(request)
        return response


# Set up rate limiting (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and SLOWAPI_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS middleware for web dashboard integration
# Enable CORS in all environments - nginx handles auth, FastAPI handles CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Staging authentication middleware - runs AFTER CORS to allow preflight requests
if settings.ENVIRONMENT in ["staging", "production"]:
    app.add_middleware(StagingAuthMiddleware)


# Response compression middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(SecurityHeadersMiddleware)

# tugas mengelola HTTPS adalah tanggung jawab reverse proxy (Nginx)
# if settings.ENVIRONMENT in ["production", "staging"]:
#     from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

#     app.add_middleware(HTTPSRedirectMiddleware)

# Metrics middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and PROMETHEUS_AVAILABLE:
    app.add_middleware(MetricsMiddleware)

# Rate limiting middleware (only in production/staging)
if settings.ENVIRONMENT in ["production", "staging"] and SLOWAPI_AVAILABLE:
    app.add_middleware(SlowAPIMiddleware)

# Security and audit middleware (only in production/staging for TrustedHost)
if settings.ENVIRONMENT in ["production", "staging"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(AuditMiddleware)

# Include API routes
app.include_router(api_router, prefix="/v1")


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Basic health check endpoint for load balancers and monitoring"""
    # Simple health check - just verify the service is running
    # Don't do comprehensive checks that might fail due to external
    # dependencies
    return {
        "status": "healthy",
        "service": "envoyou-sec-api",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health/metrics")
async def prometheus_health_metrics():
    """Prometheus-compatible health metrics endpoint"""
    # Return basic health metrics in Prometheus format
    uptime_seconds = int((datetime.utcnow() - datetime(2025, 1, 1)).total_seconds())

    metrics = f"""# HELP envoyou_api_health_status API health status
# (1=healthy, 0=unhealthy)
# TYPE envoyou_api_health_status gauge
envoyou_api_health_status 1

# HELP envoyou_api_uptime_seconds API uptime in seconds
# TYPE envoyou_api_uptime_seconds counter
envoyou_api_uptime_seconds {uptime_seconds}

# HELP envoyou_api_info API information
# TYPE envoyou_api_info gauge
envoyou_api_info{{version="1.0.0",environment="{settings.ENVIRONMENT}"}} 1
"""

    return Response(
        content=metrics, media_type="text/plain; version=0.0.4; charset=utf-8"
    )


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
            "note": ("Service is running but some dependencies may be unavailable"),
        }


@app.get("/debug/db")
async def debug_database(db: Session = Depends(get_db)):
    """Debug endpoint to test database connectivity"""
    try:
        # Test basic connectivity
        result = db.execute(
            text("SELECT 1 as test, version() as pg_version")
        ).fetchone()

        # Get database info
        db_info = {
            "connection_test": result[0] == 1,
            "postgresql_version": result[1] if len(result) > 1 else "unknown",
            "database_url": (
                settings.DATABASE_URL.replace(
                    settings.DATABASE_URL.split("@")[0].split("//")[1].split(":")[0],
                    "***",
                ).replace(
                    settings.DATABASE_URL.split("@")[0].split("//")[1].split(":")[1],
                    "***",
                )
                if "@" in settings.DATABASE_URL
                else "masked"
            ),
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
            "database_url_masked": (
                settings.DATABASE_URL.split("@")[0]
                + "@***:***@"
                + settings.DATABASE_URL.split("@")[1]
                if "@" in settings.DATABASE_URL
                else "invalid_url"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # Only check for PROMETHEUS_AVAILABLE in production/staging
    if settings.ENVIRONMENT in ["production", "staging"] and not PROMETHEUS_AVAILABLE:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Metrics not available - Prometheus client not configured",
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
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=settings.ENVIRONMENT == "development",
    )
