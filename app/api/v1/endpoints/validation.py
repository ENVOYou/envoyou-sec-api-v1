"""
Data validation endpoints
Cross-validation against EPA GHGRP and other government databases
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.validation import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    ValidationHistoryResponse,
    ValidationReportResponse,
    ValidationRequest,
    ValidationResponse,
    ValidationThresholdsResponse,
)
from app.services.emissions_validation_service import EmissionsValidationService

router = APIRouter()


# Simple test endpoint
@router.get("/test")
async def test():
    """Simple test endpoint for testing"""
    return {"message": "Test endpoint working!", "service": "validation"}


@router.post("/", response_model=ValidationResponse)
async def validate_company_emissions(
    request: ValidationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Comprehensive emissions validation for a company

    Performs cross-validation against EPA GHGRP data, variance analysis,
    threshold checking, and anomaly detection for SEC compliance.
    """
    validation_service = EmissionsValidationService(db)

    try:
        # Convert string UUID to UUID object if needed
        company_id = (
            str(request.company_id)
            if isinstance(request.company_id, UUID)
            else request.company_id
        )

        # Perform comprehensive validation
        validation_result = await validation_service.validate_company_emissions(
            company_id=company_id,
            reporting_year=request.reporting_year,
            calculation_ids=request.calculation_ids,
            validation_options=request.validation_options,
        )

        # Convert ValidationResult to ValidationResponse
        return ValidationResponse(
            validation_id=validation_result.validation_id,
            company_id=validation_result.company_id,
            reporting_year=validation_result.reporting_year,
            validation_timestamp=validation_result.validation_timestamp,
            validation_status=validation_result.validation_status,
            compliance_level=validation_result.compliance_level,
            overall_confidence_score=validation_result.overall_confidence_score,
            data_quality_score=validation_result.data_quality_score,
            consistency_score=validation_result.consistency_score,
            completeness_score=validation_result.completeness_score,
            discrepancies=validation_result.discrepancies,
            recommendations=validation_result.recommendations,
            ghgrp_comparison=validation_result.ghgrp_comparison,
            variance_analysis=validation_result.variance_analysis,
            threshold_analysis=validation_result.threshold_analysis,
            anomaly_report=validation_result.anomaly_report,
            anomaly_risk_score=validation_result.anomaly_risk_score,
            validation_details=validation_result.validation_details,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.get("/report/{company_id}", response_model=ValidationReportResponse)
async def get_validation_report(
    company_id: str,
    reporting_year: int = Query(..., description="Reporting year for validation"),
    format: str = Query(
        "comprehensive", description="Report format: comprehensive, summary, executive"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get validation report for a company

    Provides detailed validation results in various formats suitable for
    SEC compliance reporting and internal review.
    """
    validation_service = EmissionsValidationService(db)

    try:
        # First perform validation to get results
        validation_result = await validation_service.validate_company_emissions(
            company_id=company_id,
            reporting_year=reporting_year,
        )

        # Generate formatted report
        report_data = await validation_service.generate_validation_report(
            validation_result, format
        )

        return ValidationReportResponse(**report_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate validation report: {str(e)}",
        )


@router.get("/ghgrp/{company_id}")
async def get_ghgrp_validation_data(
    company_id: str,
    reporting_year: int = Query(..., description="Reporting year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get EPA GHGRP data for company validation

    Retrieves government-reported emissions data for cross-validation
    against company calculations.
    """
    validation_service = EmissionsValidationService(db)

    try:
        # Get GHGRP service directly
        ghgrp_service = validation_service.ghgrp_service

        # Fetch GHGRP data for the company
        ghgrp_data = await ghgrp_service.get_company_emissions(
            company_id=company_id, reporting_year=reporting_year
        )

        return {
            "company_id": company_id,
            "reporting_year": reporting_year,
            "ghgrp_data": ghgrp_data,
            "data_source": "EPA_GHGRP",
            "last_updated": ghgrp_data.get("last_updated"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve GHGRP data: {str(e)}",
        )


@router.post("/batch")
async def validate_multiple_companies(
    company_ids: List[str] = Query(..., description="List of company IDs to validate"),
    reporting_year: int = Query(..., description="Reporting year for validation"),
    parallel: bool = Query(True, description="Run validations in parallel"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Batch validation for multiple companies

    Performs validation across multiple companies efficiently,
    useful for portfolio-wide compliance checking.
    """
    validation_service = EmissionsValidationService(db)

    try:
        results = []
        errors = []

        if parallel:
            # Run validations in parallel
            import asyncio

            async def validate_company(company_id: str):
                try:
                    result = await validation_service.validate_company_emissions(
                        company_id=company_id,
                        reporting_year=reporting_year,
                    )
                    return {
                        "company_id": company_id,
                        "status": "success",
                        "validation_result": {
                            "validation_id": result.validation_id,
                            "validation_status": result.validation_status,
                            "compliance_level": result.compliance_level,
                            "overall_confidence_score": result.overall_confidence_score,
                            "discrepancies_count": len(result.discrepancies),
                        },
                    }
                except Exception as e:
                    return {
                        "company_id": company_id,
                        "status": "error",
                        "error": str(e),
                    }

            # Execute all validations concurrently
            tasks = [validate_company(cid) for cid in company_ids]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    errors.append({"error": str(result)})
                else:
                    results.append(result)
        else:
            # Run validations sequentially
            for company_id in company_ids:
                try:
                    result = await validation_service.validate_company_emissions(
                        company_id=company_id,
                        reporting_year=reporting_year,
                    )
                    results.append(
                        {
                            "company_id": company_id,
                            "status": "success",
                            "validation_result": {
                                "validation_id": result.validation_id,
                                "validation_status": result.validation_status,
                                "compliance_level": result.compliance_level,
                                "overall_confidence_score": result.overall_confidence_score,
                                "discrepancies_count": len(result.discrepancies),
                            },
                        }
                    )
                except Exception as e:
                    errors.append(
                        {
                            "company_id": company_id,
                            "error": str(e),
                        }
                    )

        return {
            "batch_validation_id": f"batch_{reporting_year}_{len(company_ids)}",
            "reporting_year": reporting_year,
            "total_companies": len(company_ids),
            "successful_validations": len(results),
            "failed_validations": len(errors),
            "results": results,
            "errors": errors,
            "execution_mode": "parallel" if parallel else "sequential",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch validation failed: {str(e)}",
        )


@router.post("/calculate/{calculation_id}/validate-accuracy")
async def validate_calculation_accuracy(
    calculation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate accuracy of a specific emissions calculation

    Performs detailed accuracy validation including methodology checking,
    factor validation, and recalculation verification.
    """
    validation_service = EmissionsValidationService(db)

    try:
        accuracy_result = await validation_service.validate_calculation_accuracy(
            calculation_id=calculation_id
        )

        return accuracy_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calculation accuracy validation failed: {str(e)}",
        )


@router.post(
    "/companies/{company_id}/detect-anomalies", response_model=AnomalyDetectionResponse
)
async def detect_company_anomalies(
    company_id: str,
    request: AnomalyDetectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Detect anomalies in company emissions data

    Uses statistical analysis and business rules to identify
    unusual patterns or potential data quality issues.
    """
    validation_service = EmissionsValidationService(db)

    try:
        anomaly_result = await validation_service.detect_data_anomalies(
            company_id=company_id,
            reporting_year=request.reporting_year,
            anomaly_detection_config=request.config,
        )

        return AnomalyDetectionResponse(
            company_id=company_id,
            reporting_year=request.reporting_year,
            detection_timestamp=anomaly_result["detection_timestamp"],
            statistical_anomalies=anomaly_result["statistical_anomalies"],
            business_rule_anomalies=anomaly_result["business_rule_anomalies"],
            ghgrp_anomalies=anomaly_result["ghgrp_anomalies"],
            total_anomalies=anomaly_result["total_anomalies"],
            risk_level=anomaly_result["risk_level"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}",
        )


@router.get("/thresholds")
async def get_validation_thresholds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current validation thresholds and scoring methodology

    Provides transparency into the validation criteria and scoring
    system used for SEC compliance validation.
    """
    validation_service = EmissionsValidationService(db)

    return ValidationThresholdsResponse(
        variance_thresholds=validation_service.variance_thresholds,
        scoring_weights=validation_service.scoring_weights,
        validation_methodology={
            "approach": "EPA_GHGRP_CROSS_VALIDATION",
            "scoring_method": "WEIGHTED_COMPOSITE_SCORE",
            "threshold_levels": ["acceptable", "low", "medium", "high", "critical"],
            "compliance_levels": ["compliant", "needs_review", "non_compliant"],
        },
        last_updated="2024-01-01T00:00:00Z",  # Would be dynamic in production
    )


@router.get("/companies/{company_id}/validation-history")
async def get_validation_history(
    company_id: str,
    limit: int = Query(10, le=50, description="Maximum number of history records"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get validation history for a company

    Shows historical validation results and trends over time
    for compliance monitoring and improvement tracking.
    """
    # This would typically query a validation_history table
    # For now, return a placeholder structure
    return ValidationHistoryResponse(
        company_id=company_id,
        total_validations=0,
        validation_history=[],
        trends={
            "average_confidence_score_trend": [],
            "compliance_rate_trend": [],
            "discrepancies_trend": [],
        },
        note="Validation history tracking will be implemented with historical data storage",
    )
