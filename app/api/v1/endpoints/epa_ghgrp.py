"""
EPA GHGRP Data Integration API Endpoints
Provides endpoints for EPA GHGRP data search, validation, and cross-verification
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.audit_logger import AuditLogger
from app.core.auth import require_roles
from app.models.user import User
from app.services.epa_ghgrp_service import EPAGHGRPService

router = APIRouter()


@router.get("/companies/{company_id}/search")
async def search_company_in_ghgrp(
    company_id: str,
    additional_criteria: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search for company in EPA GHGRP database

    - **company_id**: Internal company ID
    - **additional_criteria**: Additional search criteria (CIK, ticker, name, etc.)

    Returns company matches with confidence scores and ranking.
    """
    ghgrp_service = EPAGHGRPService(db)
    audit_logger = AuditLogger(db)

    try:
        search_result = await ghgrp_service.search_company_in_ghgrp(
            company_id=company_id, search_criteria=additional_criteria
        )

        # Log the search
        await audit_logger.log_event(
            event_type="GHGRP_COMPANY_SEARCH",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "total_matches": search_result["total_matches"],
                "best_match_confidence": search_result["match_confidence"],
                "additional_criteria": additional_criteria,
            },
        )

        return {
            "message": "GHGRP company search completed",
            "search_result": search_result,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="GHGRP_COMPANY_SEARCH_ERROR",
            user_id=current_user.id,
            details={"company_id": company_id, "error": str(e)},
        )
        raise


@router.get("/companies/{company_id}/emissions/{reporting_year}")
async def get_ghgrp_emissions_data(
    company_id: str,
    reporting_year: int,
    ghgrp_facility_id: Optional[str] = Query(
        None, description="Specific GHGRP facility ID"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get emissions data from EPA GHGRP for a specific company and year

    - **company_id**: Internal company ID
    - **reporting_year**: Year for emissions data
    - **ghgrp_facility_id**: Specific GHGRP facility ID (optional)

    Returns comprehensive GHGRP emissions data including Scope 1 and 2 emissions.
    """
    ghgrp_service = EPAGHGRPService(db)
    audit_logger = AuditLogger(db)

    try:
        emissions_data = await ghgrp_service.get_ghgrp_emissions_data(
            company_id=company_id,
            reporting_year=reporting_year,
            ghgrp_facility_id=ghgrp_facility_id,
        )

        # Log the data retrieval
        await audit_logger.log_event(
            event_type="GHGRP_EMISSIONS_DATA_RETRIEVED",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "ghgrp_facility_id": ghgrp_facility_id,
                "data_available": emissions_data["ghgrp_data_available"],
                "total_emissions": emissions_data.get("emissions_data", {}).get(
                    "total_emissions_co2e_tonnes", 0
                ),
            },
        )

        return {
            "message": "GHGRP emissions data retrieved successfully",
            "emissions_data": emissions_data,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="GHGRP_EMISSIONS_DATA_ERROR",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "error": str(e),
            },
        )
        raise


@router.post("/validate/calculations/{calculation_id}")
async def validate_calculation_against_ghgrp(
    calculation_id: str,
    reporting_year: int,
    company_id: Optional[str] = Query(
        None, description="Company ID (auto-detected if not provided)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate emissions calculation against EPA GHGRP data

    - **calculation_id**: Emissions calculation ID to validate
    - **reporting_year**: Reporting year for validation
    - **company_id**: Company ID (auto-detected from calculation if not provided)

    Performs comprehensive validation including:
    - Emissions data comparison
    - Variance analysis
    - Discrepancy identification
    - Confidence scoring
    - Actionable recommendations
    """
    ghgrp_service = EPAGHGRPService(db)
    audit_logger = AuditLogger(db)

    try:
        # Auto-detect company_id if not provided
        if not company_id:
            from app.models.emissions import EmissionsCalculation

            calculation = (
                db.query(EmissionsCalculation)
                .filter(EmissionsCalculation.id == calculation_id)
                .first()
            )

            if not calculation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Calculation {calculation_id} not found",
                )

            company_id = str(calculation.company_id)

        validation_result = await ghgrp_service.validate_company_emissions(
            company_id=company_id,
            calculation_id=calculation_id,
            reporting_year=reporting_year,
        )

        # Log the validation
        await audit_logger.log_event(
            event_type="GHGRP_VALIDATION_PERFORMED",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "company_id": company_id,
                "reporting_year": reporting_year,
                "validation_status": validation_result["validation_status"],
                "confidence_level": validation_result.get("confidence_level", 0),
            },
        )

        return {
            "message": "GHGRP validation completed successfully",
            "validation_result": validation_result,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="GHGRP_VALIDATION_ERROR",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "company_id": company_id,
                "reporting_year": reporting_year,
                "error": str(e),
            },
        )
        raise


@router.get("/companies/{company_id}/validation-summary")
async def get_ghgrp_validation_summary(
    company_id: str,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["cfo", "general_counsel", "admin"])),
):
    """
    Get summary of all GHGRP validations for a company

    - **company_id**: Company ID
    - **reporting_year**: Optional filter by reporting year

    Provides comprehensive validation summary including:
    - Total validations performed
    - Validation status distribution
    - Average confidence levels
    - Compliance status assessment

    Restricted to CFO, General Counsel, and Admin roles.
    """
    ghgrp_service = EPAGHGRPService(db)
    audit_logger = AuditLogger(db)

    try:
        validation_summary = await ghgrp_service.get_ghgrp_validation_summary(
            company_id=company_id, reporting_year=reporting_year
        )

        # Log the summary access
        await audit_logger.log_event(
            event_type="GHGRP_VALIDATION_SUMMARY_ACCESS",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "total_calculations": validation_summary["total_calculations"],
            },
        )

        return {
            "message": "GHGRP validation summary retrieved successfully",
            "validation_summary": validation_summary,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="GHGRP_VALIDATION_SUMMARY_ERROR",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "error": str(e),
            },
        )
        raise


@router.get("/sectors")
async def get_ghgrp_sectors(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get list of EPA GHGRP sectors and their mappings

    Returns available GHGRP sectors and their corresponding industry classifications.
    Useful for understanding sector coverage and mapping.
    """
    ghgrp_service = EPAGHGRPService(db)

    try:
        sectors_info = {
            "ghgrp_sectors": list(ghgrp_service.sector_mappings.keys()),
            "sector_mappings": ghgrp_service.sector_mappings,
            "total_sectors": len(ghgrp_service.sector_mappings),
            "coverage_description": "EPA GHGRP covers major industrial sectors and large emission sources",
            "reporting_threshold": "25,000 metric tons CO2e per year",
            "last_updated": datetime.utcnow().isoformat(),
        }

        return {
            "message": "GHGRP sectors information retrieved successfully",
            "sectors_info": sectors_info,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GHGRP sectors: {str(e)}",
        )


@router.get("/validation-metrics")
async def get_validation_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date for metrics"),
    end_date: Optional[datetime] = Query(None, description="End date for metrics"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"])),
):
    """
    Get GHGRP validation metrics and statistics

    - **start_date**: Start date for metrics calculation
    - **end_date**: End date for metrics calculation

    Provides system-wide validation metrics including:
    - Total validations performed
    - Success rates and confidence levels
    - Common variance patterns
    - Data quality trends

    Restricted to Admin and CFO roles.
    """
    try:
        # This would be implemented to provide actual metrics
        # For now, return mock metrics structure
        validation_metrics = {
            "metrics_period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "validation_statistics": {
                "total_validations": 0,
                "successful_validations": 0,
                "failed_validations": 0,
                "average_confidence": 0,
                "validation_success_rate": 0,
            },
            "variance_analysis": {
                "acceptable_variance": 0,
                "minor_variance": 0,
                "significant_variance": 0,
                "average_variance_percentage": 0,
            },
            "data_quality_trends": {
                "average_ghgrp_quality": 0,
                "average_internal_quality": 0,
                "quality_improvement_trend": "stable",
            },
            "sector_coverage": {"sectors_validated": [], "coverage_percentage": 0},
        }

        return {
            "message": "GHGRP validation metrics retrieved successfully",
            "metrics": validation_metrics,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get validation metrics: {str(e)}",
        )
