"""
EPA Cache Management API Endpoints
Provides endpoints for managing EPA data caching and refresh
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.audit_logger import AuditLogger
from app.core.auth import require_roles
from app.models.user import User
from app.schemas.epa_data import EmissionFactorResponse, EPAFactorSummary
from app.services.epa_cache_service import EPACachedService

router = APIRouter()


@router.get("/factors", response_model=List[EmissionFactorResponse])
async def get_emission_factors(
    source: str = "EPA_GHGRP",
    category: Optional[str] = None,
    fuel_type: Optional[str] = None,
    electricity_region: Optional[str] = None,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get EPA emission factors with caching

    - **source**: EPA data source (EPA_GHGRP, EPA_EGRID, EPA_AP42)
    - **category**: Filter by emission category
    - **fuel_type**: Filter by fuel type
    - **electricity_region**: Filter by electricity region
    - **force_refresh**: Force refresh from database (bypass cache)
    """
    audit_logger = AuditLogger(db)

    try:
        async with EPACachedService(db) as epa_service:
            factors = await epa_service.get_emission_factors(
                source=source,
                category=category,
                fuel_type=fuel_type,
                electricity_region=electricity_region,
                force_refresh=force_refresh,
            )

            # Log the access
            await audit_logger.log_event(
                event_type="EPA_FACTORS_ACCESS",
                user_id=current_user.id,
                details={
                    "source": source,
                    "category": category,
                    "fuel_type": fuel_type,
                    "electricity_region": electricity_region,
                    "force_refresh": force_refresh,
                    "factors_returned": len(factors),
                },
            )

            return factors

    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_FACTORS_ACCESS_ERROR",
            user_id=current_user.id,
            details={"source": source, "error": str(e)},
        )
        raise


@router.get("/factors/{factor_code}", response_model=EmissionFactorResponse)
async def get_emission_factor_by_code(
    factor_code: str,
    version: Optional[str] = None,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get specific EPA emission factor by code

    - **factor_code**: EPA factor code
    - **version**: Specific version (optional, defaults to current)
    - **force_refresh**: Force refresh from database (bypass cache)
    """
    audit_logger = AuditLogger(db)

    try:
        async with EPACachedService(db) as epa_service:
            factor = await epa_service.get_emission_factor_by_code(
                factor_code=factor_code, version=version, force_refresh=force_refresh
            )

            if not factor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Emission factor not found: {factor_code}",
                )

            # Log the access
            await audit_logger.log_event(
                event_type="EPA_FACTOR_ACCESS",
                user_id=current_user.id,
                details={
                    "factor_code": factor_code,
                    "version": version,
                    "force_refresh": force_refresh,
                },
            )

            return factor

    except HTTPException:
        raise
    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_FACTOR_ACCESS_ERROR",
            user_id=current_user.id,
            details={"factor_code": factor_code, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get emission factor: {str(e)}",
        )


@router.post("/refresh")
async def refresh_epa_data(
    background_tasks: BackgroundTasks,
    sources: Optional[List[str]] = None,
    force_update: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"])),
):
    """
    Refresh EPA data from external sources (Admin/CFO only)

    - **sources**: List of sources to refresh (optional, defaults to all)
    - **force_update**: Force update even if cache is fresh
    """
    audit_logger = AuditLogger(db)

    try:
        # Log the refresh request
        await audit_logger.log_event(
            event_type="EPA_DATA_REFRESH_REQUESTED",
            user_id=current_user.id,
            details={"sources": sources, "force_update": force_update},
        )

        async with EPACachedService(db) as epa_service:
            refresh_results = await epa_service.refresh_epa_data(
                sources=sources, force_update=force_update
            )

            # Log the refresh results
            await audit_logger.log_event(
                event_type="EPA_DATA_REFRESH_COMPLETED",
                user_id=current_user.id,
                details=refresh_results,
            )

            return {"message": "EPA data refresh completed", "results": refresh_results}

    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_DATA_REFRESH_ERROR",
            user_id=current_user.id,
            details={"sources": sources, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh EPA data: {str(e)}",
        )


@router.get("/cache/status")
async def get_cache_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"])),
):
    """
    Get EPA cache status and statistics (Admin/CFO only)
    """
    try:
        async with EPACachedService(db) as epa_service:
            status_info = epa_service.get_cache_status()

            return {
                "message": "Cache status retrieved successfully",
                "status": status_info,
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache status: {str(e)}",
        )


@router.post("/cache/clear")
async def clear_cache(
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """
    Clear EPA cache (Admin only)

    - **source**: Specific source to clear (optional, clears all if not specified)
    """
    audit_logger = AuditLogger(db)

    try:
        async with EPACachedService(db) as epa_service:
            if source:
                # Clear specific source
                cleared = epa_service.cache_service.invalidate_source_cache(source)
                message = f"Cleared cache for source: {source}"
            else:
                # Clear all EPA cache
                cleared = epa_service.cache_service.cache.clear_pattern("epa:*")
                message = "Cleared all EPA cache"

            # Log the cache clear
            await audit_logger.log_event(
                event_type="EPA_CACHE_CLEARED",
                user_id=current_user.id,
                details={"source": source, "entries_cleared": cleared},
            )

            return {"message": message, "entries_cleared": cleared}

    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_CACHE_CLEAR_ERROR",
            user_id=current_user.id,
            details={"source": source, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


@router.post("/auto-refresh/start")
async def start_auto_refresh(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """
    Start automated EPA data refresh (Admin only)
    """
    audit_logger = AuditLogger(db)

    try:
        async with EPACachedService(db) as epa_service:
            await epa_service.start_auto_refresh()

            # Log the auto-refresh start
            await audit_logger.log_event(
                event_type="EPA_AUTO_REFRESH_STARTED",
                user_id=current_user.id,
                details={"refresh_interval_hours": epa_service.refresh_interval_hours},
            )

            return {
                "message": "Auto-refresh started successfully",
                "refresh_interval_hours": epa_service.refresh_interval_hours,
            }

    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_AUTO_REFRESH_START_ERROR",
            user_id=current_user.id,
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start auto-refresh: {str(e)}",
        )


@router.post("/auto-refresh/stop")
async def stop_auto_refresh(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """
    Stop automated EPA data refresh (Admin only)
    """
    audit_logger = AuditLogger(db)

    try:
        async with EPACachedService(db) as epa_service:
            await epa_service.stop_auto_refresh()

            # Log the auto-refresh stop
            await audit_logger.log_event(
                event_type="EPA_AUTO_REFRESH_STOPPED",
                user_id=current_user.id,
                details={},
            )

            return {"message": "Auto-refresh stopped successfully"}

    except Exception as e:
        await audit_logger.log_event(
            event_type="EPA_AUTO_REFRESH_STOP_ERROR",
            user_id=current_user.id,
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop auto-refresh: {str(e)}",
        )


@router.get("/summary", response_model=EPAFactorSummary)
async def get_factors_summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get EPA factors summary statistics
    """
    try:
        epa_service = EPACachedService(db)
        summary = epa_service.epa_service.get_factors_summary()

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get factors summary: {str(e)}",
        )
