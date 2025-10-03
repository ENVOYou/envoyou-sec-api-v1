"""
ENVOYOU SEC API - Main FastAPI Application
Climate Disclosure Rule Compliance Platform for US Public Companies
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from app.core.config import settings
from app.api.v1.api import api_router
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

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# CORS middleware for web dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Custom middleware for audit logging and error handling
app.add_middleware(AuditMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/v1")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    task_status = task_manager.get_task_status()
    
    return {
        "status": "healthy",
        "service": "envoyou-sec-api",
        "version": "1.0.0",
        "background_tasks": task_status
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ENVOYOU SEC API - Climate Disclosure Compliance Platform",
        "docs": "/docs",
        "health": "/health"
    }


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    # Start background task manager
    await task_manager.start_all_tasks()


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    # Stop background task manager
    await task_manager.stop_all_tasks()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )