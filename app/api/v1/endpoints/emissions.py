"""
Emissions calculation endpoints
GHG emissions calculation with EPA factor integration
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.epa_data import (
    EmissionFactorResponse, EmissionFactorQuery, EPAFactorSummary,
    FuelEmissionFactorRequest, ElectricityEmissionFactorRequest,
    EPADataUpdateRequest, EPADataUpdateResponse
)
from app.services.epa_service import EPADataIngestionService
from app.services.epa_scheduler import epa_scheduler
from app.services.cache_service import cache_service
from app.core.dependencies import (
    get_current_active_user, require_manage_epa_data,
    require_read_emissions
)
from app.models.user import User

router = APIRouter()


@router.get("/factors", response_model=List[EmissionFactorResponse])
async def get_emission_factors(
    category: Optional[str] = Query(None, description="Filter by category (fuel, electricity)"),
    fuel_type: Optional[str] = Query(None, description="Filter by fuel type"),
    electricity_region: Optional[str] = Query(None, description="Filter by electricity region"),
    source: Optional[str] = Query(None, description="Filter by source (EPA_GHGRP, EPA_EGRID)"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Retrieve current EPA emission factors with optional filtering
    """
    epa_service = EPADataIngestionService(db)
    
    return epa_service.get_current_factors(
        category=category,
        fuel_type=fuel_type,
        electricity_region=electricity_region,
        source=source
    )


@router.get("/factors/{factor_code}", response_model=EmissionFactorResponse)
async def get_emission_factor_by_code(
    factor_code: str,
    version: Optional[str] = Query(None, description="Specific version, defaults to current"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get specific emission factor by code and version
    """
    epa_service = EPADataIngestionService(db)
    
    factor = epa_service.get_factor_by_code(factor_code, version)
    
    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor '{factor_code}' not found"
        )
    
    return factor


@router.get("/factors/summary", response_model=EPAFactorSummary)
async def get_factors_summary(
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics of EPA emission factors
    """
    epa_service = EPADataIngestionService(db)
    return epa_service.get_factors_summary()


@router.post("/factors/fuel", response_model=List[EmissionFactorResponse])
async def get_fuel_emission_factors(
    request: FuelEmissionFactorRequest,
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get emission factors for specific fuel type
    """
    epa_service = EPADataIngestionService(db)
    
    return epa_service.get_current_factors(
        category="fuel",
        fuel_type=request.fuel_type
    )


@router.post("/factors/electricity", response_model=List[EmissionFactorResponse])
async def get_electricity_emission_factors(
    request: ElectricityEmissionFactorRequest,
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get emission factors for specific electricity region
    """
    epa_service = EPADataIngestionService(db)
    
    return epa_service.get_current_factors(
        category="electricity",
        electricity_region=request.region
    )


@router.put("/factors/update", response_model=EPADataUpdateResponse)
async def update_epa_factors(
    request: EPADataUpdateRequest,
    current_user: User = Depends(require_manage_epa_data),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint for updating EPA emission factors
    """
    async with EPADataIngestionService(db) as epa_service:
        # Fetch latest data from EPA
        data = await epa_service.fetch_latest_factors(request.source)
        
        if not data or not data.get('factors'):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No data received from EPA API"
            )
        
        # Cache with versioning
        version = data.get('metadata', {}).get('version', 'manual_update')
        
        return epa_service.cache_with_versioning(
            data['factors'],
            request.source,
            version
        )


@router.post("/factors/refresh")
async def force_refresh_epa_data(
    source: Optional[str] = Query(None, description="Specific source to refresh"),
    current_user: User = Depends(require_manage_epa_data)
):
    """
    Force immediate refresh of EPA data
    """
    result = await epa_scheduler.force_refresh(source)
    
    return {
        "message": "EPA data refresh initiated",
        "results": result
    }


@router.get("/cache/status")
async def get_cache_status(
    current_user: User = Depends(require_manage_epa_data)
):
    """
    Get EPA data cache status and statistics
    """
    cache_stats = cache_service.get_cache_stats()
    scheduler_status = epa_scheduler.get_scheduler_status()
    
    return {
        "cache": cache_stats,
        "scheduler": scheduler_status
    }


@router.post("/cache/invalidate")
async def invalidate_epa_cache(
    pattern: str = Query("epa_*", description="Cache key pattern to invalidate"),
    current_user: User = Depends(require_manage_epa_data)
):
    """
    Invalidate EPA cache entries
    """
    deleted_count = cache_service.invalidate_epa_cache(pattern)
    
    return {
        "message": f"Invalidated {deleted_count} cache entries",
        "pattern": pattern,
        "deleted_count": deleted_count
    }