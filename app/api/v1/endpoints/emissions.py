"""
Emissions calculation endpoints
GHG emissions calculation with EPA factor integration
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.epa_data import (
    EmissionFactorResponse, EmissionFactorQuery, EPAFactorSummary,
    FuelEmissionFactorRequest, ElectricityEmissionFactorRequest,
    EPADataUpdateRequest, EPADataUpdateResponse
)
from app.schemas.emissions import (
    Scope1CalculationRequest, Scope2CalculationRequest, EmissionsCalculationResponse,
    CalculationSummary, CompanyEmissionsSummary, CalculationAuditTrailResponse,
    CalculationApprovalRequest, CalculationValidationResult
)
from app.services.epa_service import EPADataIngestionService
from app.services.epa_scheduler import epa_scheduler
from app.services.cache_service import cache_service
from app.services.scope1_calculator import Scope1EmissionsCalculator
from app.services.scope2_calculator import Scope2EmissionsCalculator
from app.services.emissions_audit_service import EmissionsAuditService
from app.core.dependencies import (
    get_current_active_user, require_manage_epa_data,
    require_read_emissions, require_write_emissions, require_approve_reports
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


# Emissions Calculation Endpoints

@router.post("/calculate/scope1", response_model=EmissionsCalculationResponse)
async def calculate_scope1_emissions(
    request: Scope1CalculationRequest,
    current_user: User = Depends(require_write_emissions),
    db: Session = Depends(get_db)
):
    """
    Calculate Scope 1 (direct) GHG emissions from fuel combustion and other direct sources
    """
    calculator = Scope1EmissionsCalculator(db)
    return calculator.calculate_scope1_emissions(request, str(current_user.id))


@router.post("/calculate/scope2", response_model=EmissionsCalculationResponse)
async def calculate_scope2_emissions(
    request: Scope2CalculationRequest,
    current_user: User = Depends(require_write_emissions),
    db: Session = Depends(get_db)
):
    """
    Calculate Scope 2 (indirect energy) GHG emissions from purchased electricity
    """
    calculator = Scope2EmissionsCalculator(db)
    return calculator.calculate_scope2_emissions(request, str(current_user.id))


@router.get("/calculations", response_model=List[CalculationSummary])
async def get_calculations(
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    scope: Optional[str] = Query(None, description="Filter by scope (scope_1, scope_2)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get list of emissions calculations with optional filtering
    """
    from app.models.emissions import EmissionsCalculation
    
    query = db.query(EmissionsCalculation)
    
    if company_id:
        query = query.filter(EmissionsCalculation.company_id == company_id)
    
    if scope:
        query = query.filter(EmissionsCalculation.scope == scope)
    
    if status:
        query = query.filter(EmissionsCalculation.status == status)
    
    calculations = query.order_by(EmissionsCalculation.created_at.desc()).offset(offset).limit(limit).all()
    
    return [
        CalculationSummary(
            id=str(calc.id),
            calculation_name=calc.calculation_name,
            calculation_code=calc.calculation_code,
            scope=calc.scope,
            status=calc.status,
            total_co2e=calc.total_co2e,
            calculation_timestamp=calc.calculation_timestamp
        )
        for calc in calculations
    ]


@router.get("/calculations/{calculation_id}", response_model=EmissionsCalculationResponse)
async def get_calculation(
    calculation_id: str,
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific emissions calculation
    """
    from app.models.emissions import EmissionsCalculation
    
    calculation = db.query(EmissionsCalculation).filter(
        EmissionsCalculation.id == calculation_id
    ).first()
    
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation {calculation_id} not found"
        )
    
    # Use appropriate calculator to build response
    if calculation.scope == "scope_1":
        calculator = Scope1EmissionsCalculator(db)
    else:
        calculator = Scope2EmissionsCalculator(db)
    
    return calculator._build_calculation_response(calculation)


@router.post("/calculations/{calculation_id}/approve")
async def approve_calculation(
    calculation_id: str,
    approval_request: CalculationApprovalRequest,
    request: Request,
    current_user: User = Depends(require_approve_reports),
    db: Session = Depends(get_db)
):
    """
    Approve or reject an emissions calculation (CFO/General Counsel only)
    """
    from app.models.emissions import EmissionsCalculation
    
    calculation = db.query(EmissionsCalculation).filter(
        EmissionsCalculation.id == calculation_id
    ).first()
    
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calculation {calculation_id} not found"
        )
    
    # Update calculation status
    old_status = calculation.status
    
    if approval_request.approval_status == "approved":
        calculation.status = "approved"
        calculation.approved_by = current_user.id
    elif approval_request.approval_status == "rejected":
        calculation.status = "rejected"
    else:  # needs_revision
        calculation.status = "needs_revision"
    
    db.commit()
    
    # Log approval event
    audit_service = EmissionsAuditService(db)
    audit_service.log_calculation_event(
        calculation_id=calculation_id,
        event_type=f"calculation_{approval_request.approval_status}",
        event_description=f"Calculation {approval_request.approval_status} by {current_user.role.value}",
        user_id=str(current_user.id),
        user_role=current_user.role.value,
        field_changed="status",
        old_value={"status": old_status},
        new_value={"status": calculation.status},
        reason=approval_request.comments,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {
        "message": f"Calculation {approval_request.approval_status}",
        "calculation_id": calculation_id,
        "new_status": calculation.status,
        "approved_by": str(current_user.id) if approval_request.approval_status == "approved" else None
    }


@router.get("/calculations/{calculation_id}/audit-trail", response_model=List[CalculationAuditTrailResponse])
async def get_calculation_audit_trail(
    calculation_id: str,
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get complete audit trail for an emissions calculation
    """
    audit_service = EmissionsAuditService(db)
    return audit_service.get_calculation_audit_trail(calculation_id)


@router.get("/calculations/{calculation_id}/forensic-report")
async def get_forensic_report(
    calculation_id: str,
    include_raw_data: bool = Query(True, description="Include raw activity data"),
    include_user_details: bool = Query(False, description="Include user details (admin only)"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive forensic report for SEC audit purposes
    """
    # Only admins can include user details
    if include_user_details and not current_user.is_admin:
        include_user_details = False
    
    audit_service = EmissionsAuditService(db)
    return audit_service.generate_forensic_report(
        calculation_id, 
        include_raw_data, 
        include_user_details
    )


@router.get("/companies/{company_id}/summary", response_model=CompanyEmissionsSummary)
async def get_company_emissions_summary(
    company_id: str,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get emissions summary for a company
    """
    from app.models.emissions import EmissionsCalculation, Company
    from sqlalchemy import func
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Build query
    query = db.query(EmissionsCalculation).filter(
        EmissionsCalculation.company_id == company_id,
        EmissionsCalculation.status.in_(["completed", "approved"])
    )
    
    if reporting_year:
        query = query.filter(
            func.extract('year', EmissionsCalculation.reporting_period_start) == reporting_year
        )
    
    calculations = query.all()
    
    # Calculate totals by scope
    scope1_total = sum(c.total_co2e for c in calculations if c.scope == "scope_1" and c.total_co2e)
    scope2_total = sum(c.total_co2e for c in calculations if c.scope == "scope_2" and c.total_co2e)
    scope3_total = sum(c.total_co2e for c in calculations if c.scope == "scope_3" and c.total_co2e)
    
    # Calculate average data quality
    quality_scores = [c.data_quality_score for c in calculations if c.data_quality_score]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
    
    # Get last calculation date
    last_calc = max([c.calculation_timestamp for c in calculations]) if calculations else None
    
    return CompanyEmissionsSummary(
        company_id=company_id,
        company_name=company.name,
        reporting_year=reporting_year or company.reporting_year,
        total_scope1_co2e=scope1_total if scope1_total > 0 else None,
        total_scope2_co2e=scope2_total if scope2_total > 0 else None,
        total_scope3_co2e=scope3_total if scope3_total > 0 else None,
        total_co2e=(scope1_total + scope2_total + scope3_total) if any([scope1_total, scope2_total, scope3_total]) else None,
        calculations_count=len(calculations),
        last_calculation=last_calc,
        data_quality_average=avg_quality
    )


@router.get("/companies/{company_id}/audit-summary")
async def get_company_audit_summary(
    company_id: str,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    current_user: User = Depends(require_read_emissions),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive audit summary for a company's emissions calculations
    """
    audit_service = EmissionsAuditService(db)
    return audit_service.get_company_audit_summary(company_id, reporting_year)