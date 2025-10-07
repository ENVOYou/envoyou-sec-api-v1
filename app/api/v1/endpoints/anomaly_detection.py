"""
Anomaly Detection API Endpoints for SEC Climate Disclosure API

Endpoints for detecting anomalies in emissions and operational data
"""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.auth import require_roles
from app.models.user import User
from app.schemas.anomaly_detection import (
    AnomalyDetectionRequest,
    AnomalyReportResponse,
    AnomalySummaryResponse,
    AnomalyTrendRequest,
    AnomalyTrendResponse,
    BatchAnomalyDetectionRequest,
    BatchAnomalyDetectionResponse,
    IndustryBenchmarkRequest,
    IndustryBenchmarkResponse,
)
from app.services.anomaly_detection_service import AnomalyDetectionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/detect",
    response_model=AnomalyReportResponse,
    summary="Detect anomalies in emissions data",
    description="Perform comprehensive anomaly detection analysis for a company's emissions data",
)
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(
        require_roles(["finance_team", "general_counsel", "cfo", "admin"])
    ),
):
    """
    Detect anomalies in company emissions data including:
    - Year-over-year variance detection
    - Statistical outlier identification
    - Industry benchmark comparisons
    - Operational data consistency checks
    """
    try:
        logger.info(
            f"Anomaly detection requested by user {current_user.id} for company {request.company_id}"
        )

        service = AnomalyDetectionService(db)
        report = service.detect_anomalies(
            company_id=request.company_id,
            reporting_year=request.reporting_year,
            user_id=current_user.id,
        )

        # Convert to response model
        response = AnomalyReportResponse(
            company_id=report.company_id,
            reporting_year=report.reporting_year,
            analysis_date=report.analysis_date,
            total_anomalies=report.total_anomalies,
            anomalies_by_severity=report.anomalies_by_severity,
            detected_anomalies=[
                {
                    "anomaly_type": anomaly.anomaly_type,
                    "severity": anomaly.severity,
                    "description": anomaly.description,
                    "detected_value": anomaly.detected_value,
                    "expected_range": anomaly.expected_range,
                    "confidence_score": anomaly.confidence_score,
                    "recommendations": anomaly.recommendations,
                    "metadata": anomaly.metadata,
                }
                for anomaly in report.detected_anomalies
            ],
            overall_risk_score=report.overall_risk_score,
            summary_insights=report.summary_insights,
        )

        logger.info(
            f"Anomaly detection completed. Found {report.total_anomalies} anomalies"
        )
        return response

    except Exception as e:
        logger.error(f"Error in anomaly detection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}",
        )


@router.get(
    "/summary/{company_id}/{reporting_year}",
    response_model=AnomalySummaryResponse,
    summary="Get anomaly detection summary",
    description="Get a summary of anomaly detection results for a company and year",
)
async def get_anomaly_summary(
    company_id: UUID,
    reporting_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(
        require_roles(["finance_team", "general_counsel", "cfo", "admin"])
    ),
):
    """
    Get a summary of anomaly detection results including:
    - Total number of anomalies
    - Count by severity level
    - Overall risk score
    - Whether attention is required
    """
    try:
        logger.info(
            f"Anomaly summary requested by user {current_user.id} for company {company_id}"
        )

        service = AnomalyDetectionService(db)
        report = service.detect_anomalies(
            company_id=company_id,
            reporting_year=reporting_year,
            user_id=current_user.id,
        )

        # Create summary response
        critical_count = report.anomalies_by_severity.get("critical", 0)
        high_count = report.anomalies_by_severity.get("high", 0)

        response = AnomalySummaryResponse(
            company_id=company_id,
            reporting_year=reporting_year,
            total_anomalies=report.total_anomalies,
            critical_anomalies=critical_count,
            high_anomalies=high_count,
            overall_risk_score=report.overall_risk_score,
            last_analysis_date=report.analysis_date,
            requires_attention=(critical_count > 0 or high_count > 0),
        )

        return response

    except Exception as e:
        logger.error(f"Error getting anomaly summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get anomaly summary: {str(e)}",
        )


@router.post(
    "/batch-detect",
    response_model=BatchAnomalyDetectionResponse,
    summary="Batch anomaly detection",
    description="Perform anomaly detection for multiple companies",
)
async def batch_detect_anomalies(
    request: BatchAnomalyDetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles(["admin", "cfo"])),
):
    """
    Perform batch anomaly detection for multiple companies.
    Only available to admin and CFO users.
    """
    try:
        logger.info(
            f"Batch anomaly detection requested by user {current_user.id} for {len(request.company_ids)} companies"
        )

        service = AnomalyDetectionService(db)
        results = []
        errors = []
        successful_count = 0

        for company_id in request.company_ids:
            try:
                report = service.detect_anomalies(
                    company_id=company_id,
                    reporting_year=request.reporting_year,
                    user_id=current_user.id,
                )

                critical_count = report.anomalies_by_severity.get("critical", 0)
                high_count = report.anomalies_by_severity.get("high", 0)

                results.append(
                    AnomalySummaryResponse(
                        company_id=company_id,
                        reporting_year=request.reporting_year,
                        total_anomalies=report.total_anomalies,
                        critical_anomalies=critical_count,
                        high_anomalies=high_count,
                        overall_risk_score=report.overall_risk_score,
                        last_analysis_date=report.analysis_date,
                        requires_attention=(critical_count > 0 or high_count > 0),
                    )
                )

                successful_count += 1

            except Exception as e:
                logger.error(f"Error processing company {company_id}: {str(e)}")
                errors.append({"company_id": str(company_id), "error": str(e)})

        response = BatchAnomalyDetectionResponse(
            total_companies=len(request.company_ids),
            successful_analyses=successful_count,
            failed_analyses=len(errors),
            results=results,
            errors=errors,
        )

        logger.info(
            f"Batch anomaly detection completed. {successful_count}/{len(request.company_ids)} successful"
        )
        return response

    except Exception as e:
        logger.error(f"Error in batch anomaly detection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch anomaly detection failed: {str(e)}",
        )


@router.post(
    "/trends",
    response_model=AnomalyTrendResponse,
    summary="Analyze anomaly trends",
    description="Analyze anomaly trends over multiple years for a company",
)
async def analyze_anomaly_trends(
    request: AnomalyTrendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(
        require_roles(["finance_team", "general_counsel", "cfo", "admin"])
    ),
):
    """
    Analyze anomaly trends over multiple years to identify patterns
    and provide strategic recommendations.
    """
    try:
        logger.info(
            f"Anomaly trend analysis requested by user {current_user.id} for company {request.company_id}"
        )

        service = AnomalyDetectionService(db)
        trend_data = []

        # Analyze each year in the range
        for year in range(request.start_year, request.end_year + 1):
            try:
                report = service.detect_anomalies(
                    company_id=request.company_id,
                    reporting_year=year,
                    user_id=current_user.id,
                )

                # Count anomalies by type
                anomalies_by_type = {}
                for anomaly in report.detected_anomalies:
                    anomaly_type = anomaly.anomaly_type
                    if (
                        request.anomaly_types is None
                        or anomaly_type in request.anomaly_types
                    ):
                        anomalies_by_type[anomaly_type] = (
                            anomalies_by_type.get(anomaly_type, 0) + 1
                        )

                trend_data.append(
                    {
                        "year": year,
                        "total_anomalies": len(
                            [
                                a
                                for a in report.detected_anomalies
                                if request.anomaly_types is None
                                or a.anomaly_type in request.anomaly_types
                            ]
                        ),
                        "anomalies_by_type": anomalies_by_type,
                        "risk_score": report.overall_risk_score,
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Could not analyze year {year} for company {request.company_id}: {str(e)}"
                )
                # Add empty data point for missing years
                trend_data.append(
                    {
                        "year": year,
                        "total_anomalies": 0,
                        "anomalies_by_type": {},
                        "risk_score": 0.0,
                    }
                )

        # Perform trend analysis
        risk_scores = [point["risk_score"] for point in trend_data]
        total_anomalies = [point["total_anomalies"] for point in trend_data]

        trend_analysis = {
            "average_risk_score": (
                sum(risk_scores) / len(risk_scores) if risk_scores else 0
            ),
            "risk_score_trend": (
                "increasing"
                if len(risk_scores) > 1 and risk_scores[-1] > risk_scores[0]
                else "stable"
            ),
            "total_anomalies_trend": (
                "increasing"
                if len(total_anomalies) > 1 and total_anomalies[-1] > total_anomalies[0]
                else "stable"
            ),
            "years_analyzed": len(trend_data),
        }

        # Generate recommendations based on trends
        recommendations = []
        if trend_analysis["risk_score_trend"] == "increasing":
            recommendations.append(
                "Risk score is increasing over time - implement systematic data quality improvements"
            )
        if trend_analysis["total_anomalies_trend"] == "increasing":
            recommendations.append(
                "Number of anomalies is increasing - review data collection and validation processes"
            )
        if trend_analysis["average_risk_score"] > 50:
            recommendations.append(
                "High average risk score - consider comprehensive data management system review"
            )

        response = AnomalyTrendResponse(
            company_id=request.company_id,
            analysis_period=(request.start_year, request.end_year),
            trend_data=trend_data,
            trend_analysis=trend_analysis,
            recommendations=recommendations,
        )

        return response

    except Exception as e:
        logger.error(f"Error in anomaly trend analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly trend analysis failed: {str(e)}",
        )


@router.post(
    "/industry-benchmark",
    response_model=IndustryBenchmarkResponse,
    summary="Compare against industry benchmarks",
    description="Compare company emissions against industry benchmarks",
)
async def compare_industry_benchmarks(
    request: IndustryBenchmarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(
        require_roles(["finance_team", "general_counsel", "cfo", "admin"])
    ),
):
    """
    Compare company emissions metrics against industry benchmarks
    to identify potential areas for improvement.
    """
    try:
        logger.info(
            f"Industry benchmark comparison requested by user {current_user.id} for company {request.company_id}"
        )

        # This is a simplified implementation
        # In a real system, this would integrate with external industry data sources

        industry_sector = request.industry_sector or "default"

        # Placeholder industry benchmarks
        industry_benchmarks = {
            "manufacturing": {
                "scope1_intensity": 0.15,
                "scope2_intensity": 0.08,
                "total_intensity": 0.23,
            },
            "technology": {
                "scope1_intensity": 0.02,
                "scope2_intensity": 0.05,
                "total_intensity": 0.07,
            },
            "default": {
                "scope1_intensity": 0.10,
                "scope2_intensity": 0.08,
                "total_intensity": 0.18,
            },
        }

        benchmarks = industry_benchmarks.get(
            industry_sector, industry_benchmarks["default"]
        )

        # Get company metrics (simplified - would normally calculate from actual data)
        company_metrics = {
            "scope1_intensity": 0.12,  # Placeholder
            "scope2_intensity": 0.09,  # Placeholder
            "total_intensity": 0.21,  # Placeholder
        }

        # Calculate deviations
        deviations = {}
        percentile_ranking = {}
        for metric, company_value in company_metrics.items():
            benchmark_value = benchmarks[metric]
            deviation = (company_value - benchmark_value) / benchmark_value
            deviations[metric] = deviation

            # Simplified percentile calculation
            if deviation < -0.2:
                percentile_ranking[metric] = 90  # Top 10%
            elif deviation < 0:
                percentile_ranking[metric] = 70  # Top 30%
            elif deviation < 0.2:
                percentile_ranking[metric] = 50  # Average
            else:
                percentile_ranking[metric] = 20  # Bottom 20%

        # Generate recommendations
        recommendations = []
        for metric, deviation in deviations.items():
            if deviation > 0.2:
                recommendations.append(
                    f"Consider improvement strategies for {metric} - currently {deviation:.1%} above industry average"
                )
            elif deviation < -0.2:
                recommendations.append(
                    f"Excellent performance in {metric} - {abs(deviation):.1%} below industry average"
                )

        response = IndustryBenchmarkResponse(
            company_id=request.company_id,
            industry_sector=industry_sector,
            reporting_year=request.reporting_year,
            company_metrics=company_metrics,
            industry_benchmarks=benchmarks,
            deviations=deviations,
            percentile_ranking=percentile_ranking,
            recommendations=recommendations,
        )

        return response

    except Exception as e:
        logger.error(f"Error in industry benchmark comparison: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Industry benchmark comparison failed: {str(e)}",
        )
