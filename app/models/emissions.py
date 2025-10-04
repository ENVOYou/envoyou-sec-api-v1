"""
Emissions calculation models
Stores emissions data, calculations, and audit trails for SEC compliance
"""

import enum
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import GUID
from app.models.base import JSON
from app.models.base import AuditMixin
from app.models.base import BaseModel


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

    def __repr__(self):
        return f"<Company(name='{self.name}', ticker='{self.ticker}')>"


class CompanyEntity(BaseModel, AuditMixin):
    """Company entities/subsidiaries for consolidated reporting"""

    __tablename__ = "company_entities"

    # Entity information
    company_id = Column(GUID(), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)  # subsidiary, division, facility

    # Ownership and consolidation
    ownership_percentage = Column(Float, default=100.0, nullable=False)
    consolidation_method = Column(
        String(50), nullable=False
    )  # full, equity, proportional

    # Location information
    country = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)

    # Operational information
    primary_activity = Column(String(255), nullable=True)
    operational_control = Column(Boolean, default=True, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="entities")
    calculations = relationship(
        "EmissionsCalculation", back_populates="entity", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CompanyEntity(name='{self.name}', ownership='{self.ownership_percentage}%')>"


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
    reporting_period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    reporting_period_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Calculation status and workflow
    status = Column(String(20), default="pending", nullable=False, index=True)
    calculated_by = Column(GUID(), nullable=False)  # User ID
    reviewed_by = Column(GUID(), nullable=True)  # User ID
    approved_by = Column(GUID(), nullable=True)  # User ID

    # Calculation results (in metric tons CO2e)
    total_co2e = Column(Float, nullable=True)
    total_co2 = Column(Float, nullable=True)
    total_ch4 = Column(Float, nullable=True)
    total_n2o = Column(Float, nullable=True)

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

    # External references
    source_documents = Column(JSON, nullable=True)  # References to source documents
    third_party_verification = Column(Boolean, default=False, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="calculations")
    entity = relationship("CompanyEntity", back_populates="calculations")
    activity_data = relationship(
        "ActivityData", back_populates="calculation", cascade="all, delete-orphan"
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
