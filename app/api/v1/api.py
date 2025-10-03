"""
API v1 Router Configuration
Aggregates all API endpoints for version 1
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, emissions, validation, reports, audit, workflow

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(emissions.router, prefix="/emissions", tags=["Emissions"])
api_router.include_router(validation.router, prefix="/validation", tags=["Validation"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["Workflow"])