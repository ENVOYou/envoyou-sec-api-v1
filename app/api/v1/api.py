"""
API v1 Router Configuration
Aggregates all API endpoints for version 1
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    anomaly_detection,
    audit,
    auth,
    company_entities,
    emissions,
    emissions_validation,
    enhanced_audit,
    epa_cache,
    epa_ghgrp,
    reports,
    validation,
    workflow,
)

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(emissions.router, prefix="/emissions", tags=["Emissions"])
api_router.include_router(epa_cache.router, prefix="/epa", tags=["EPA Data & Cache"])
api_router.include_router(
    epa_ghgrp.router, prefix="/epa-ghgrp", tags=["EPA GHGRP Integration"]
)
api_router.include_router(validation.router, prefix="/validation", tags=["Validation"])
api_router.include_router(
    emissions_validation.router,
    prefix="/emissions-validation",
    tags=["Emissions Cross-Validation"],
)
api_router.include_router(
    anomaly_detection.router,
    prefix="/anomaly-detection",
    tags=["Anomaly Detection"],
)
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(
    enhanced_audit.router, prefix="/enhanced-audit", tags=["Enhanced Audit & Forensics"]
)
api_router.include_router(
    company_entities.router, prefix="/entities", tags=["Company Entities"]
)
api_router.include_router(workflow.router, prefix="/workflow", tags=["Workflow"])
