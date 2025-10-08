"""
ENVOYOU SEC API - Main FastAPI Application
Climate Disclosure Rule Compliance Platform for US Public Companies
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.middleware import AuditMiddleware, ErrorHandlingMiddleware
from app.services.background_tasks import task_manager

# Create FastAPI application
app = FastAPI(
    title="ENVOYOU SEC API",
    description="Climate Disclosure Rule Compliance Platform for US Public Companies",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS middleware for web dashboard integration (simplified)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Disable other middleware temporarily for debugging
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
# app.add_middleware(AuditMiddleware)
# app.add_middleware(ErrorHandlingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "envoyou-sec-api",
        "version": "1.0.0",
        "environment": "production",
    }


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
