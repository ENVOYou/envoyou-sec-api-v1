"""
Consolidation Schemas for SEC Climate Disclosure API

Pydantic models for emissions consolidation and multi-entity reporting
"""

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsolidationMethod(str, Enum):
    """Methods for consolidating emissions data"""

    OWNERSHIP_BASED = "ownership_based"  # Based on ownership percentage
    OPERATIONAL_CONTROL = "operational_control"  # Based on operational control
    FINANCIAL_CONTROL = "financial_control"  # Based on financial control
    EQUITY_SHARE = "equity_share"  # Proportional to equity share


class ConsolidationStatus(str, Enum):
    """Status of consolidation process"""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class EntityContribution(BaseModel):
    """Individual entity contribution to consolidated emissions"""

    entity_id: UUID
    entity_name: str
    ownership_percentage: float = Field(..., ge=0.0, le=100.0)
    consolidation_factor: float = Field(
        ..., ge=0.0, le=1.0, description="Factor applied for consolidation"
    )

    # Original emissions data
    original_scope1_co2e: Optional[float] = Field(None, ge=0.0)
    original_scope2_co2e: Optional[float] = Field(None, ge=0.0)
    original_scope3_co2e: Optional[float] = Field(None, ge=0.0)
    original_total_co2e: Optional[float] = Field(None, ge=0.0)

    # Consolidated contributions (after applying ownership factor)
    consolidated_scope1_co2e: Optional[float] = Field(None, ge=0.0)
    consolidated_scope2_co2e: Optional[float] = Field(None, ge=0.0)
    consolidated_scope3_co2e: Optional[float] = Field(None, ge=0.0)
    consolidated_total_co2e: Optional[float] = Field(None, ge=0.0)

    # Data quality indicators
    data_completeness: float = Field(default=0.0, ge=0.0, le=100.0)
    data_quality_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Inclusion status
    included_in_consolidation: bool = True
    exclusion_reason: Optional[str] = None


class ConsolidationRequest(BaseModel):
    """Request to perform emissions consolidation"""

    company_id: UUID
    reporting_year: int = Field(..., ge=2020, le=2030)
    reporting_period_start: date
    reporting_period_end: date

    consolidation_method: ConsolidationMethod = ConsolidationMethod.OWNERSHIP_BASED
    include_scope3: bool = Field(
        default=False, description="Whether to include Scope 3 emissions"
    )

    # Entity selection
    include_entities: Optional[List[UUID]] = Field(
        None, description="Specific entities to include (null = all active)"
    )
    exclude_entities: Optional[List[UUID]] = Field(
        None, description="Entities to exclude"
    )

    # Consolidation options
    minimum_ownership_threshold: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Minimum ownership % to include"
    )
    apply_operational_control_filter: bool = Field(
        default=False, description="Only include entities with operational control"
    )

    # Data quality requirements
    minimum_data_quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    require_complete_data: bool = Field(
        default=False, description="Require complete data for all scopes"
    )


class ConsolidationResponse(BaseModel):
    """Response containing consolidated emissions data"""

    id: UUID
    company_id: UUID
    reporting_year: int
    reporting_period_start: date
    reporting_period_end: date

    # Consolidation metadata
    consolidation_method: ConsolidationMethod
    consolidation_date: datetime
    consolidation_version: int

    # Consolidated totals
    total_scope1_co2e: Optional[float]
    total_scope2_co2e: Optional[float]
    total_scope3_co2e: Optional[float]
    total_co2e: Optional[float]

    # Gas breakdown
    total_co2: Optional[float] = None
    total_ch4_co2e: Optional[float] = None
    total_n2o_co2e: Optional[float] = None
    total_other_ghg_co2e: Optional[float] = None

    # Coverage statistics
    total_entities_included: int
    entities_with_scope1: int
    entities_with_scope2: int
    entities_with_scope3: int

    # Quality metrics
    data_completeness_score: Optional[float]
    consolidation_confidence_score: Optional[float]

    # Status
    status: ConsolidationStatus
    is_final: bool
    validation_status: Optional[str]

    # Approval info
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ConsolidationDetailResponse(ConsolidationResponse):
    """Detailed consolidation response with entity breakdown"""

    entity_contributions: List[EntityContribution]
    consolidation_adjustments: Optional[Dict] = None
    exclusions: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True)


class ConsolidationSummary(BaseModel):
    """Summary of consolidation results"""

    company_id: UUID
    reporting_year: int
    consolidation_count: int
    latest_consolidation_date: Optional[datetime]

    # Totals from latest consolidation
    latest_total_co2e: Optional[float]
    latest_scope1_co2e: Optional[float]
    latest_scope2_co2e: Optional[float]
    latest_scope3_co2e: Optional[float]

    # Coverage statistics
    total_entities_in_structure: int
    entities_included_in_latest: int
    coverage_percentage: float

    # Status overview
    approved_consolidations: int
    draft_consolidations: int


class ConsolidationComparison(BaseModel):
    """Comparison between different consolidation versions or years"""

    company_id: UUID
    comparison_type: str  # "version" or "year"

    base_consolidation: ConsolidationResponse
    compare_consolidation: ConsolidationResponse

    # Variance analysis
    total_co2e_variance: Optional[float]
    total_co2e_variance_percentage: Optional[float]
    scope1_variance: Optional[float]
    scope2_variance: Optional[float]
    scope3_variance: Optional[float]

    # Entity changes
    entities_added: List[UUID] = []
    entities_removed: List[UUID] = []
    entities_changed: List[UUID] = []

    # Summary insights
    key_changes: List[str] = []
    variance_explanation: Optional[str] = None


class ConsolidationApproval(BaseModel):
    """Request to approve/reject consolidation"""

    action: str = Field(..., pattern="^(approve|reject)$")
    approval_notes: Optional[str] = Field(None, max_length=1000)


class ConsolidationAuditEvent(BaseModel):
    """Audit event for consolidation process"""

    id: UUID
    consolidation_id: UUID
    event_type: str
    event_timestamp: datetime
    user_id: Optional[UUID]
    event_description: Optional[str]
    affected_entities: Optional[List[UUID]]
    processing_time_ms: Optional[int]

    model_config = ConfigDict(from_attributes=True)
