"""
Emissions calculation models
Stores emissions data, calculations, and audit trails for SEC compliance
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import GUID, JSON, AuditMixin, BaseModel


class EmissionScope(enum.Enum):
    """GHG emission scopes as defined by GHG Protocol"""

    SCOPE_1 = "scope_1"  # Direct emissions
    SCOPE_2 = "scope_2"  # Indirect emissions from purchased energy
    SCOPE_3 = "scope_3"  # Other indirect emissions (future)


class CalculationStatus(enum.Enum):
    """Status of emissions calculation"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"


class CalculationMethod(enum.Enum):
    """Calculation methodology used"""

    FUEL_COMBUSTION = "fuel_combustion"
    ELECTRICITY_CONSUMPTION = "electricity_consumption"
    PROCESS_EMISSIONS = "process_emissions"
    FUGITIVE_EMISSIONS = "fugitive_emissions"
    MOBILE_COMBUSTION = "mobile_combustion"
    STATIONARY_COMBUSTION = "stationary_combustion"


class Company(BaseModel, AuditMixin):
    """Company model for emissions reporting"""

    __tablename__ = "companies"

    # Basic company information
    name = Column(String(255), nullable=False, index=True)
    ticker = Column(String(10), unique=True, index=True, nullable=True)
    cik = Column(
        String(20), unique=True, index=True, nullable=True
    )  # SEC Central Index Key

    # Company details
    industry = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    headquarters_country = Column(String(100), default="United States", nullable=False)
    fiscal_year_end = Column(String(10), nullable=True)  # MM-DD format

    # Reporting information
    reporting_year = Column(Integer, nullable=False, index=True)
    is_public_company = Column(Boolean, default=True, nullable=False)
    market_cap_category = Column(
        String(50), nullable=True
    )  # large-cap, mid-cap, small-cap

    # Relationships
    entities = relationship(
        "CompanyEntity", back_populates="company", cascade="all, delete-orphan"
    )
    calculations = relationship(
        "EmissionsCalculation", back_populates="company", cascade="all, delete-orphan"
    )
    consolidated_emissions = relationship(
        "ConsolidatedEmissions", back_populates="company"
    )

    def __repr__(self):
        return f"<Company(name='{self.name}', ticker='{self.ticker}')>"


class CompanyEntity(BaseModel, AuditMixin):
    """Company entities/subsidiaries for consolidated reporting with hierarchical structure"""

    __tablename__ = "company_entities"

    # Entity information
    company_id = Column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)  # subsidiary, division, facility

    # Hierarchical structure (simplified for existing database)
    # parent_id, level, path fields removed to match existing schema

    # Ownership and consolidation
    ownership_percentage = Column(Float, default=100.0, nullable=False)
    consolidation_method = Column(
        String(50), nullable=False, default="full"
    )  # full, equity, proportional

    # Location information
    country = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)

    # Operational information
    primary_activity = Column(String(255), nullable=True)
    operational_control = Column(Boolean, default=True, nullable=False)
    is_active = Column(
        Boolean, default=True, nullable=True
    )  # Added back - now exists in database

    # Relationships
    company = relationship("Company", back_populates="entities")
    calculations = relationship(
        "EmissionsCalculation", back_populates="entity", cascade="all, delete-orphan"
    )

    # Additional indexes for performance
    __table_args__ = (
        Index("idx_company_entity_company_active", "company_id", "is_active"),
        Index("idx_company_entity_ownership", "ownership_percentage"),
        Index("idx_company_entity_type", "entity_type"),
    )

    def __repr__(self):
        return f"<CompanyEntity(name='{self.name}', ownership='{self.ownership_percentage}%', level={self.level})>"

    @property
    def full_path(self):
        """Get full hierarchical path"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    def get_all_children(self, session):
        """Recursively get all children entities"""
        from sqlalchemy import text

        # Use recursive CTE to get all descendants
        query = text(
            """
            WITH RECURSIVE entity_tree AS (
                -- Base case: start with current entity
                SELECT id, name, parent_id, ownership_percentage, level,
                       CAST(ownership_percentage AS FLOAT) as effective_ownership
                FROM company_entities
                WHERE id = :entity_id

                UNION ALL

                -- Recursive case: get children
                SELECT ce.id, ce.name, ce.parent_id, ce.ownership_percentage, ce.level,
                       CAST(et.effective_ownership * ce.ownership_percentage / 100.0 AS FLOAT) as effective_ownership
                FROM company_entities ce
                INNER JOIN entity_tree et ON ce.parent_id = et.id
                WHERE ce.is_active = true
            )
            SELECT * FROM entity_tree WHERE id != :entity_id
        """
        )

        result = session.execute(query, {"entity_id": str(self.id)})
        return result.fetchall()

    def get_effective_ownership(self):
        """Calculate effective ownership percentage considering parent chain"""
        if not self.parent:
            return self.ownership_percentage

        parent_effective = self.parent.get_effective_ownership()
        return (parent_effective * self.ownership_percentage) / 100.0

    def validate_ownership(self, session):
        """Validate that total ownership of children doesn't exceed 100%"""
        if not self.children:
            return True

        total_ownership = sum(
            child.ownership_percentage for child in self.children if child.is_active
        )
        return total_ownership <= 100.0


class EmissionsCalculation(BaseModel, AuditMixin):
    """Main emissions calculation record"""

    __tablename__ = "emissions_calculations"

    # Calculation identification
    calculation_name = Column(String(255), nullable=False)
    calculation_code = Column(String(100), unique=True, nullable=False, index=True)

    # Company and entity references
    company_id = Column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    entity_id = Column(
        GUID(), ForeignKey("company_entities.id"), nullable=True, index=True
    )

    # Calculation details
    scope = Column(String(20), nullable=False, index=True)  # scope_1, scope_2, scope_3
    method = Column(String(50), nullable=False)  # calculation methodology
    reporting_year = Column(
        Integer, nullable=True, index=True
    )  # Added back - exists in database
    reporting_period_start = Column(Date, nullable=True)  # Keep existing field
    reporting_period_end = Column(Date, nullable=True)  # Keep existing field

    # Calculation status and workflow
    status = Column(String(20), default="pending", nullable=False, index=True)
    calculated_by = Column(GUID(), nullable=False)  # User ID
    reviewed_by = Column(GUID(), nullable=True)  # User ID
    approved_by = Column(GUID(), nullable=True)  # User ID

    # Calculation results (in metric tons CO2e)
    total_co2e = Column(Numeric(15, 3), nullable=True)
    total_scope1_co2e = Column(Numeric(15, 3), nullable=True)
    total_scope2_co2e = Column(Numeric(15, 3), nullable=True)
    total_scope3_co2e = Column(Numeric(15, 3), nullable=True)
    total_co2 = Column(Numeric(15, 3), nullable=True)
    total_ch4 = Column(Numeric(15, 3), nullable=True)
    total_n2o = Column(Numeric(15, 3), nullable=True)

    # Calculation metadata
    input_data = Column(JSON, nullable=False)  # Original input data
    calculation_parameters = Column(JSON, nullable=True)  # Calculation parameters used
    emission_factors_used = Column(
        JSON, nullable=False
    )  # EPA factors used with versions

    # Quality and uncertainty
    data_quality_score = Column(Float, nullable=True)  # 0-100 score
    uncertainty_percentage = Column(Float, nullable=True)  # Uncertainty estimate

    # Audit and compliance
    calculation_timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    calculation_duration_seconds = Column(Float, nullable=True)
    validation_errors = Column(JSON, nullable=True)
    validation_warnings = Column(JSON, nullable=True)

    # Encrypted sensitive data (for future use)
    encrypted_input_data = Column(
        Text, nullable=True
    )  # Encrypted version of input_data
    encrypted_emission_factors = Column(
        Text, nullable=True
    )  # Encrypted emission factors
    data_integrity_hash = Column(String(64), nullable=True)  # SHA256 hash for integrity

    # External references
    source_documents = Column(JSON, nullable=True)  # References to source documents
    third_party_verification = Column(Boolean, default=False, nullable=False)
    validation_status = Column(String(50), nullable=True)
    calculation_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="calculations")
    entity = relationship("CompanyEntity", back_populates="calculations")
    activity_data = relationship(
        "ActivityData", back_populates="calculation", cascade="all, delete-orphan"
    )

    # Additional indexes for performance
    __table_args__ = (
        Index("idx_emissions_calc_company_scope", "company_id", "scope"),
        Index("idx_emissions_calc_status_date", "status", "calculation_timestamp"),
        Index("idx_emissions_calc_year_scope", "reporting_year", "scope"),
        Index("idx_emissions_calc_approved", "approved_by", "status"),
    )

    def __repr__(self):
        return f"<EmissionsCalculation(code='{self.calculation_code}', scope='{self.scope}')>"


class ActivityData(BaseModel, AuditMixin):
    """Activity data used in emissions calculations"""

    __tablename__ = "activity_data"

    # Calculation reference
    calculation_id = Column(
        GUID(), ForeignKey("emissions_calculations.id"), nullable=False, index=True
    )

    # Activity data details
    activity_type = Column(
        String(100), nullable=False, index=True
    )  # fuel_combustion, electricity, etc.
    fuel_type = Column(String(50), nullable=True)  # For fuel-based activities
    activity_description = Column(Text, nullable=True)

    # Quantity and units
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)

    # Location and time
    location = Column(String(255), nullable=True)
    activity_period_start = Column(DateTime(timezone=True), nullable=True)
    activity_period_end = Column(DateTime(timezone=True), nullable=True)

    # Data quality
    data_source = Column(String(255), nullable=True)
    data_quality = Column(String(50), nullable=True)  # measured, calculated, estimated
    measurement_method = Column(String(255), nullable=True)

    # Emission factor applied
    emission_factor_id = Column(GUID(), nullable=True)  # Reference to EPA factor
    emission_factor_value = Column(Float, nullable=False)
    emission_factor_unit = Column(String(100), nullable=False)
    emission_factor_source = Column(String(100), nullable=False)

    # Calculated emissions for this activity
    co2_emissions = Column(Float, nullable=True)
    ch4_emissions = Column(Float, nullable=True)
    n2o_emissions = Column(Float, nullable=True)
    co2e_emissions = Column(Float, nullable=False)

    # Additional metadata
    notes = Column(Text, nullable=True)
    additional_data = Column(JSON, nullable=True)

    # Relationships
    calculation = relationship("EmissionsCalculation", back_populates="activity_data")

    # Additional indexes for performance
    __table_args__ = (
        Index("idx_activity_calculation_type", "calculation_id", "activity_type"),
        Index("idx_activity_fuel_type", "fuel_type"),
        Index("idx_activity_location", "location"),
    )

    def __repr__(self):
        return f"<ActivityData(type='{self.activity_type}', quantity={self.quantity} {self.unit})>"


class CalculationAuditTrail(BaseModel):
    """Detailed audit trail for emissions calculations"""

    __tablename__ = "calculation_audit_trails"

    # Calculation reference
    calculation_id = Column(
        GUID(), ForeignKey("emissions_calculations.id"), nullable=False, index=True
    )

    # Audit event details
    event_type = Column(
        String(100), nullable=False, index=True
    )  # created, modified, approved, etc.
    event_description = Column(Text, nullable=False)

    # User and timestamp
    user_id = Column(GUID(), nullable=False)
    user_role = Column(String(50), nullable=False)
    event_timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Change details
    field_changed = Column(String(100), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    # System information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True)

    # Additional context
    reason = Column(Text, nullable=True)
    additional_metadata = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<CalculationAuditTrail(event='{self.event_type}', timestamp='{self.event_timestamp}')>"


class ConsolidatedEmissions(BaseModel, AuditMixin):
    """Consolidated emissions data for multi-entity companies"""

    __tablename__ = "consolidated_emissions"

    # Primary identification
    id = Column(GUID(), primary_key=True, default=uuid4)
    company_id = Column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    reporting_year = Column(Integer, nullable=False, index=True)
    reporting_period_start = Column(Date, nullable=False)
    reporting_period_end = Column(Date, nullable=False)

    # Consolidation metadata
    consolidation_method = Column(String(50), nullable=False, default="ownership_based")
    consolidation_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    consolidation_version = Column(Integer, nullable=False, default=1)

    # Consolidated emissions data (in metric tons CO2e)
    total_scope1_co2e = Column(Numeric(15, 3), nullable=True)
    total_scope2_co2e = Column(Numeric(15, 3), nullable=True)
    total_scope3_co2e = Column(Numeric(15, 3), nullable=True)
    total_co2e = Column(Numeric(15, 3), nullable=True)

    # Breakdown by gas type
    total_co2 = Column(Numeric(15, 3), nullable=True)
    total_ch4_co2e = Column(Numeric(15, 3), nullable=True)
    total_n2o_co2e = Column(Numeric(15, 3), nullable=True)
    total_other_ghg_co2e = Column(Numeric(15, 3), nullable=True)

    # Entity coverage statistics
    total_entities_included = Column(Integer, nullable=False, default=0)
    entities_with_scope1 = Column(Integer, nullable=False, default=0)
    entities_with_scope2 = Column(Integer, nullable=False, default=0)
    entities_with_scope3 = Column(Integer, nullable=False, default=0)

    # Data quality metrics
    data_completeness_score = Column(Numeric(5, 2), nullable=True)  # 0-100%
    consolidation_confidence_score = Column(Numeric(5, 2), nullable=True)  # 0-100%

    # Consolidation details (JSON)
    entity_contributions = Column(JSON, nullable=True)  # Detailed breakdown per entity
    consolidation_adjustments = Column(JSON, nullable=True)  # Any adjustments made
    exclusions = Column(JSON, nullable=True)  # Entities excluded and reasons

    # Status and validation
    status = Column(String(50), nullable=False, default="draft")
    is_final = Column(Boolean, nullable=False, default=False)
    validation_status = Column(String(50), nullable=True)
    validation_notes = Column(Text, nullable=True)

    # Approval workflow
    approved_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="consolidated_emissions")
    approver = relationship("User", foreign_keys=[approved_by])

    # Indexes for performance
    __table_args__ = (
        Index("idx_consolidated_company_year", "company_id", "reporting_year"),
        Index("idx_consolidated_status", "status"),
        Index("idx_consolidated_date", "consolidation_date"),
        UniqueConstraint(
            "company_id",
            "reporting_year",
            "consolidation_version",
            name="uq_consolidated_company_year_version",
        ),
    )

    def __repr__(self):
        return f"<ConsolidatedEmissions(company_id={self.company_id}, year={self.reporting_year}, total_co2e={self.total_co2e})>"

    @property
    def entity_count(self) -> int:
        """Total number of entities included in consolidation"""
        return self.total_entities_included

    @property
    def scope_coverage(self) -> Dict[str, bool]:
        """Which scopes are covered in this consolidation"""
        return {
            "scope1": self.total_scope1_co2e is not None and self.total_scope1_co2e > 0,
            "scope2": self.total_scope2_co2e is not None and self.total_scope2_co2e > 0,
            "scope3": self.total_scope3_co2e is not None and self.total_scope3_co2e > 0,
        }

    def get_entity_contribution(self, entity_id: UUID) -> Optional[Dict[str, Any]]:
        """Get contribution details for a specific entity"""
        if not self.entity_contributions:
            return None
        return self.entity_contributions.get(str(entity_id))

    def calculate_total_co2e(self) -> float:
        """Calculate total CO2e from all scopes"""
        total = 0.0
        if self.total_scope1_co2e:
            total += float(self.total_scope1_co2e)
        if self.total_scope2_co2e:
            total += float(self.total_scope2_co2e)
        if self.total_scope3_co2e:
            total += float(self.total_scope3_co2e)
        return total


class ConsolidationAuditTrail(BaseModel, AuditMixin):
    """Audit trail for consolidation processes"""

    __tablename__ = "consolidation_audit_trail"

    id = Column(GUID(), primary_key=True, default=uuid4)
    consolidation_id = Column(
        GUID(), ForeignKey("consolidated_emissions.id"), nullable=False
    )
    event_type = Column(String(100), nullable=False)
    event_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)

    # Event details
    event_description = Column(Text, nullable=True)
    before_values = Column(JSON, nullable=True)
    after_values = Column(JSON, nullable=True)
    affected_entities = Column(JSON, nullable=True)  # List of entity IDs affected

    # System information
    system_info = Column(JSON, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # Relationships
    consolidation = relationship("ConsolidatedEmissions")
    user = relationship("User")

    # Additional indexes for performance
    __table_args__ = (
        Index("idx_calc_audit_calculation_event", "calculation_id", "event_type"),
        Index("idx_calc_audit_user_timestamp", "user_id", "event_timestamp"),
        Index("idx_calc_audit_timestamp", "event_timestamp"),
    )

    __table_args__ = (
        Index("idx_consolidation_audit_consolidation", "consolidation_id"),
        Index("idx_consolidation_audit_timestamp", "event_timestamp"),
        Index("idx_consolidation_audit_type", "event_type"),
    )

    def __repr__(self):
        return f"<ConsolidationAuditTrail(consolidation_id={self.consolidation_id}, event={self.event_type})>"
