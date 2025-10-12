"""
Validation schemas for emissions data validation endpoints
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    """Request schema for emissions validation"""

    company_id: UUID = Field(..., description="Company UUID to validate")
    reporting_year: int = Field(..., description="Reporting year for validation")
    calculation_ids: Optional[List[str]] = Field(
        None, description="Optional specific calculation IDs to validate"
    )
    validation_options: Optional[Dict[str, Any]] = Field(
        None, description="Optional validation configuration options"
    )


class ValidationDiscrepancy(BaseModel):
    """Schema for validation discrepancy"""

    type: str = Field(..., description="Type of discrepancy")
    category: str = Field(..., description="Category of discrepancy")
    description: str = Field(..., description="Description of the discrepancy")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    source: str = Field(..., description="Source of the discrepancy")
    variance_percentage: Optional[float] = Field(
        None, description="Variance percentage if applicable"
    )


class ValidationResponse(BaseModel):
    """Response schema for comprehensive validation results"""

    validation_id: str = Field(..., description="Unique validation identifier")
    company_id: str = Field(..., description="Company identifier")
    reporting_year: int = Field(..., description="Reporting year validated")
    validation_timestamp: datetime = Field(..., description="When validation was performed")

    # Status and compliance
    validation_status: str = Field(
        ..., description="Validation status: pending, passed, failed, warning"
    )
    compliance_level: str = Field(
        ..., description="Compliance level: compliant, non_compliant, needs_review"
    )

    # Confidence scores (0-100)
    overall_confidence_score: float = Field(..., description="Overall confidence score")
    data_quality_score: float = Field(..., description="Data quality score")
    consistency_score: float = Field(..., description="Consistency score")
    completeness_score: float = Field(..., description="Completeness score")

    # Detailed results
    discrepancies: List[ValidationDiscrepancy] = Field(
        default_factory=list, description="List of identified discrepancies"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )

    # Cross-validation data
    ghgrp_comparison: Dict[str, Any] = Field(
        default_factory=dict, description="EPA GHGRP comparison results"
    )
    variance_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Variance analysis results"
    )
    threshold_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Threshold analysis results"
    )

    # Anomaly detection
    anomaly_report: Optional[Dict[str, Any]] = Field(
        None, description="Anomaly detection report"
    )
    anomaly_risk_score: float = Field(
        0.0, description="Anomaly risk score (0-100)"
    )

    # Additional details
    validation_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional validation details"
    )


class ValidationReportResponse(BaseModel):
    """Response schema for validation reports"""

    validation_id: str = Field(..., description="Validation identifier")
    company_id: str = Field(..., description="Company identifier")
    reporting_year: int = Field(..., description="Reporting year")
    validation_timestamp: str = Field(..., description="Validation timestamp")
    validation_status: str = Field(..., description="Validation status")
    compliance_level: str = Field(..., description="Compliance level")

    # Report-specific fields
    executive_summary: Optional[Dict[str, Any]] = Field(
        None, description="Executive summary for executive format"
    )
    summary: Optional[Dict[str, Any]] = Field(
        None, description="Summary data for summary format"
    )
    detailed_scores: Optional[Dict[str, float]] = Field(
        None, description="Detailed scores for comprehensive format"
    )
    ghgrp_comparison: Optional[Dict[str, Any]] = Field(
        None, description="GHGRP comparison for comprehensive format"
    )
    variance_analysis: Optional[Dict[str, Any]] = Field(
        None, description="Variance analysis for comprehensive format"
    )
    threshold_analysis: Optional[Dict[str, Any]] = Field(
        None, description="Threshold analysis for comprehensive format"
    )
    discrepancies: Optional[List[ValidationDiscrepancy]] = Field(
        None, description="Discrepancies for comprehensive format"
    )
    recommendations: Optional[List[str]] = Field(
        None, description="Recommendations for comprehensive format"
    )
    validation_details: Optional[Dict[str, Any]] = Field(
        None, description="Validation details for comprehensive format"
    )
    methodology: Optional[Dict[str, Any]] = Field(
        None, description="Methodology information for comprehensive format"
    )


class AnomalyDetectionRequest(BaseModel):
    """Request schema for anomaly detection"""

    reporting_year: int = Field(..., description="Reporting year for anomaly detection")
    config: Optional[Dict[str, Any]] = Field(
        None, description="Optional anomaly detection configuration"
    )


class AnomalyDetectionResponse(BaseModel):
    """Response schema for anomaly detection results"""

    company_id: str = Field(..., description="Company identifier")
    reporting_year: int = Field(..., description="Reporting year analyzed")
    detection_timestamp: str = Field(..., description="When detection was performed")

    statistical_anomalies: List[Dict[str, Any]] = Field(
        default_factory=list, description="Statistical anomalies detected"
    )
    business_rule_anomalies: List[Dict[str, Any]] = Field(
        default_factory=list, description="Business rule anomalies detected"
    )
    ghgrp_anomalies: List[Dict[str, Any]] = Field(
        default_factory=list, description="GHGRP-based anomalies detected"
    )

    total_anomalies: int = Field(..., description="Total number of anomalies detected")
    risk_level: str = Field(..., description="Overall risk level assessment")


class ValidationThresholdsResponse(BaseModel):
    """Response schema for validation thresholds and methodology"""

    variance_thresholds: Dict[str, float] = Field(
        ..., description="Variance thresholds by level"
    )
    scoring_weights: Dict[str, float] = Field(
        ..., description="Scoring weights for confidence calculation"
    )
    validation_methodology: Dict[str, Any] = Field(
        ..., description="Validation methodology details"
    )
    last_updated: str = Field(..., description="When thresholds were last updated")


class ValidationHistoryItem(BaseModel):
    """Schema for individual validation history item"""

    validation_id: str = Field(..., description="Validation identifier")
    validation_timestamp: str = Field(..., description="When validation occurred")
    validation_status: str = Field(..., description="Validation status")
    compliance_level: str = Field(..., description="Compliance level")
    overall_confidence_score: float = Field(..., description="Confidence score")
    discrepancies_count: int = Field(..., description="Number of discrepancies")
    reporting_year: int = Field(..., description="Reporting year")


class ValidationHistoryResponse(BaseModel):
    """Response schema for validation history"""

    company_id: str = Field(..., description="Company identifier")
    total_validations: int = Field(..., description="Total number of validations")
    validation_history: List[ValidationHistoryItem] = Field(
        default_factory=list, description="List of validation history items"
    )
    trends: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict, description="Validation trends over time"
    )
    note: Optional[str] = Field(
        None, description="Additional notes about the history data"
    )