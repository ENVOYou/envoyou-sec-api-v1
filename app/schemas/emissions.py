"""
Emissions calculation schemas for request/response validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActivityDataInput(BaseModel):
    """Schema for activity data input"""

    activity_type: str = Field(
        ..., description="Type of activity (fuel_combustion, electricity, etc.)"
    )
    fuel_type: Optional[str] = Field(
        None, description="Type of fuel (for fuel-based activities)"
    )
    activity_description: Optional[str] = Field(
        None, description="Description of the activity"
    )

    quantity: float = Field(..., gt=0, description="Quantity of activity data")
    unit: str = Field(..., description="Unit of measurement")

    location: Optional[str] = Field(
        None, description="Location where activity occurred"
    )
    activity_period_start: Optional[datetime] = Field(
        None, description="Start of activity period"
    )
    activity_period_end: Optional[datetime] = Field(
        None, description="End of activity period"
    )

    data_source: Optional[str] = Field(None, description="Source of the data")
    data_quality: Optional[str] = Field(
        "measured", description="Quality of data (measured, calculated, estimated)"
    )
    measurement_method: Optional[str] = Field(
        None, description="Method used to measure/calculate"
    )

    notes: Optional[str] = Field(None, description="Additional notes")
    additional_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )

    @field_validator("data_quality")
    @classmethod
    def validate_data_quality(cls, v):
        valid_qualities = ["measured", "calculated", "estimated"]
        if v and v not in valid_qualities:
            raise ValueError(f"Data quality must be one of: {valid_qualities}")
        return v


class Scope1CalculationRequest(BaseModel):
    """Schema for Scope 1 emissions calculation request"""

    calculation_name: str = Field(..., description="Name for this calculation")
    company_id: str = Field(..., description="Company UUID")
    entity_id: Optional[str] = Field(
        None, description="Entity UUID (optional for company-level)"
    )

    reporting_period_start: datetime = Field(
        ..., description="Start of reporting period"
    )
    reporting_period_end: datetime = Field(..., description="End of reporting period")

    activity_data: List[ActivityDataInput] = Field(
        ..., min_items=1, description="List of activity data"
    )

    calculation_parameters: Optional[Dict[str, Any]] = Field(
        None, description="Additional calculation parameters"
    )
    source_documents: Optional[List[str]] = Field(
        None, description="References to source documents"
    )
    notes: Optional[str] = Field(None, description="Calculation notes")

    @field_validator("reporting_period_end")
    @classmethod
    def validate_reporting_period(cls, v, info):
        if (
            info.data.get("reporting_period_start")
            and v <= info.data["reporting_period_start"]
        ):
            raise ValueError("Reporting period end must be after start")
        return v

    @field_validator("activity_data")
    @classmethod
    def validate_scope1_activities(cls, v):
        valid_scope1_activities = [
            "stationary_combustion",
            "mobile_combustion",
            "process_emissions",
            "fugitive_emissions",
            "fuel_combustion",
        ]
        for activity in v:
            if activity.activity_type not in valid_scope1_activities:
                raise ValueError(
                    f"Invalid Scope 1 activity type: {activity.activity_type}"
                )
        return v


class Scope2CalculationRequest(BaseModel):
    """Schema for Scope 2 emissions calculation request"""

    calculation_name: str = Field(..., description="Name for this calculation")
    company_id: str = Field(..., description="Company UUID")
    entity_id: Optional[str] = Field(
        None, description="Entity UUID (optional for company-level)"
    )

    reporting_period_start: datetime = Field(
        ..., description="Start of reporting period"
    )
    reporting_period_end: datetime = Field(..., description="End of reporting period")

    electricity_consumption: List[ActivityDataInput] = Field(
        ..., min_items=1, description="Electricity consumption data"
    )

    calculation_method: str = Field(
        "location_based",
        description="Calculation method (location_based, market_based)",
    )
    calculation_parameters: Optional[Dict[str, Any]] = Field(
        None, description="Additional calculation parameters"
    )
    source_documents: Optional[List[str]] = Field(
        None, description="References to source documents"
    )
    notes: Optional[str] = Field(None, description="Calculation notes")

    @field_validator("calculation_method")
    @classmethod
    def validate_calculation_method(cls, v):
        valid_methods = ["location_based", "market_based"]
        if v not in valid_methods:
            raise ValueError(f"Calculation method must be one of: {valid_methods}")
        return v

    @field_validator("electricity_consumption")
    @classmethod
    def validate_scope2_activities(cls, v):
        for activity in v:
            if activity.activity_type != "electricity_consumption":
                raise ValueError(
                    "Scope 2 calculations only accept electricity_consumption "
                    "activities"
                )
        return v


class ActivityDataResponse(BaseModel):
    """Schema for activity data response"""

    id: str
    activity_type: str
    fuel_type: Optional[str]
    activity_description: Optional[str]

    quantity: float
    unit: str
    location: Optional[str]

    emission_factor_value: float
    emission_factor_unit: str
    emission_factor_source: str

    co2_emissions: Optional[float]
    ch4_emissions: Optional[float]
    n2o_emissions: Optional[float]
    co2e_emissions: float

    data_quality: Optional[str]
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class EmissionsCalculationResponse(BaseModel):
    """Schema for emissions calculation response"""

    id: str
    calculation_name: str
    calculation_code: str

    company_id: str
    entity_id: Optional[str]

    scope: str
    method: str
    status: str

    reporting_period_start: datetime
    reporting_period_end: datetime

    total_co2e: Optional[float]
    total_co2: Optional[float]
    total_ch4: Optional[float]
    total_n2o: Optional[float]

    data_quality_score: Optional[float]
    uncertainty_percentage: Optional[float]

    calculated_by: str
    reviewed_by: Optional[str]
    approved_by: Optional[str]

    calculation_timestamp: datetime
    calculation_duration_seconds: Optional[float]

    activity_data: List[ActivityDataResponse]

    validation_errors: Optional[List[str]]
    validation_warnings: Optional[List[str]]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalculationSummary(BaseModel):
    """Schema for calculation summary"""

    id: str
    calculation_name: str
    calculation_code: str
    scope: str
    status: str
    total_co2e: Optional[float]
    calculation_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyEmissionsSummary(BaseModel):
    """Schema for company emissions summary"""

    company_id: str
    company_name: str
    reporting_year: int

    total_scope1_co2e: Optional[float]
    total_scope2_co2e: Optional[float]
    total_scope3_co2e: Optional[float]
    total_co2e: Optional[float]

    calculations_count: int
    last_calculation: Optional[datetime]

    data_quality_average: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class CalculationValidationResult(BaseModel):
    """Schema for calculation validation results"""

    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []

    data_completeness_score: float
    data_quality_score: float
    calculation_accuracy_score: float

    recommendations: List[str] = []


class CalculationApprovalRequest(BaseModel):
    """Schema for calculation approval"""

    calculation_id: str
    approval_status: str = Field(..., description="approved, rejected, needs_revision")
    comments: Optional[str] = Field(None, description="Approval comments")

    @field_validator("approval_status")
    @classmethod
    def validate_approval_status(cls, v):
        valid_statuses = ["approved", "rejected", "needs_revision"]
        if v not in valid_statuses:
            raise ValueError(f"Approval status must be one of: {valid_statuses}")
        return v


class CalculationAuditTrailResponse(BaseModel):
    """Schema for calculation audit trail response"""

    id: str
    calculation_id: str

    event_type: str
    event_description: str

    user_id: str
    user_role: str
    event_timestamp: datetime

    field_changed: Optional[str]
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]

    reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BulkCalculationRequest(BaseModel):
    """Schema for bulk calculation requests"""

    calculations: List[Scope1CalculationRequest]
    processing_mode: str = Field("sequential", description="sequential or parallel")

    @field_validator("processing_mode")
    @classmethod
    def validate_processing_mode(cls, v):
        valid_modes = ["sequential", "parallel"]
        if v not in valid_modes:
            raise ValueError(f"Processing mode must be one of: {valid_modes}")
        return v


class CalculationExportRequest(BaseModel):
    """Schema for calculation export requests"""

    calculation_ids: List[str] = Field(..., min_items=1)
    export_format: str = Field("excel", description="excel, csv, pdf")
    include_audit_trail: bool = Field(
        False, description="Include audit trail in export"
    )
    include_source_data: bool = Field(True, description="Include source activity data")

    @field_validator("export_format")
    @classmethod
    def validate_export_format(cls, v):
        valid_formats = ["excel", "csv", "pdf"]
        if v not in valid_formats:
            raise ValueError(f"Export format must be one of: {valid_formats}")
        return v
