"""
EPA emission factors and data models
Stores EPA emission factors with versioning for audit compliance
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import GUID, JSON, AuditMixin, BaseModel


class FuelType(enum.Enum):
    """EPA fuel types for Scope 1 emissions"""

    NATURAL_GAS = "natural_gas"
    DIESEL = "diesel"
    GASOLINE = "gasoline"
    PROPANE = "propane"
    COAL = "coal"
    FUEL_OIL = "fuel_oil"
    KEROSENE = "kerosene"
    BIOMASS = "biomass"
    OTHER = "other"


class ElectricityRegion(enum.Enum):
    """EPA eGRID regions for Scope 2 emissions"""

    AKGD = "akgd"  # ASCC Alaska Grid
    AKMS = "akms"  # ASCC Miscellaneous
    AZNM = "aznm"  # WECC Southwest
    CAMX = "camx"  # WECC California
    ERCT = "erct"  # ERCOT All
    FRCC = "frcc"  # FRCC All
    HIMS = "hims"  # HICC Miscellaneous
    HIOA = "hioa"  # HICC Oahu
    MROE = "mroe"  # MRO East
    MROW = "mrow"  # MRO West
    NEWE = "newe"  # NPCC New England
    NWPP = "nwpp"  # WECC Northwest
    NYCW = "nycw"  # NPCC NYC/Westchester
    NYLI = "nyli"  # NPCC Long Island
    NYUP = "nyup"  # NPCC Upstate NY
    RFCE = "rfce"  # RFC East
    RFCM = "rfcm"  # RFC Michigan
    RFCW = "rfcw"  # RFC West
    RMPA = "rmpa"  # WECC Rockies
    SPNO = "spno"  # SPP North
    SPSO = "spso"  # SPP South
    SRMV = "srmv"  # SERC Mississippi Valley
    SRMW = "srmw"  # SERC Midwest
    SRSO = "srso"  # SERC South
    SRTV = "srtv"  # SERC Tennessee Valley
    SRVC = "srvc"  # SERC Virginia/Carolina


class EmissionFactorSource(enum.Enum):
    """Source of emission factors"""

    EPA_GHGRP = "epa_ghgrp"
    EPA_EGRID = "epa_egrid"
    EPA_AP42 = "epa_ap42"
    EPA_INVENTORY = "epa_inventory"
    IPCC = "ipcc"
    OTHER = "other"


class EmissionFactor(BaseModel, AuditMixin):
    """EPA emission factors with versioning"""

    __tablename__ = "emission_factors"

    # Factor identification
    factor_name = Column(String(255), nullable=False, index=True)
    factor_code = Column(String(100), nullable=False, index=True)
    category = Column(
        String(100), nullable=False, index=True
    )  # fuel, electricity, etc.

    # Factor details
    fuel_type = Column(String(50), nullable=True)  # For fuel factors
    electricity_region = Column(String(10), nullable=True)  # For electricity factors
    unit = Column(String(50), nullable=False)  # kg CO2e/unit

    # Emission factor values
    co2_factor = Column(Float, nullable=False)  # kg CO2/unit
    ch4_factor = Column(Float, nullable=True)  # kg CH4/unit
    n2o_factor = Column(Float, nullable=True)  # kg N2O/unit
    co2e_factor = Column(Float, nullable=False)  # kg CO2e/unit (total)

    # Source and versioning
    source = Column(String(50), nullable=False, index=True)
    source_document = Column(String(500), nullable=True)
    source_url = Column(Text, nullable=True)
    publication_year = Column(Integer, nullable=False, index=True)
    version = Column(String(50), nullable=False, index=True)

    # Validity period
    valid_from = Column(DateTime(timezone=True), nullable=False, index=True)
    valid_to = Column(DateTime(timezone=True), nullable=True, index=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    # Additional metadata
    description = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    uncertainty = Column(Float, nullable=True)  # Percentage uncertainty
    additional_data = Column(JSON, nullable=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_emission_factors_current", "category", "is_current"),
        Index("idx_emission_factors_fuel", "fuel_type", "is_current"),
        Index("idx_emission_factors_region", "electricity_region", "is_current"),
        Index("idx_emission_factors_version", "factor_code", "version"),
    )

    def __repr__(self):
        return f"<EmissionFactor(name='{self.factor_name}', version='{self.version}')>"


class EPADataUpdate(BaseModel, AuditMixin):
    """Track EPA data updates for audit trail"""

    __tablename__ = "epa_data_updates"

    # Update information
    update_type = Column(String(50), nullable=False, index=True)  # FULL, INCREMENTAL
    source = Column(String(50), nullable=False)
    update_date = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Update statistics
    records_added = Column(Integer, default=0, nullable=False)
    records_updated = Column(Integer, default=0, nullable=False)
    records_deprecated = Column(Integer, default=0, nullable=False)

    # Status and metadata
    status = Column(
        String(20), default="PENDING", nullable=False
    )  # PENDING, SUCCESS, FAILED
    error_message = Column(Text, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    # File information
    source_file = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash
    file_size_bytes = Column(Integer, nullable=True)

    # Validation results
    validation_passed = Column(Boolean, default=False, nullable=False)
    validation_errors = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<EPADataUpdate(type='{self.update_type}', status='{self.status}')>"


class EPADataValidation(BaseModel):
    """EPA data validation rules and results"""

    __tablename__ = "epa_data_validations"

    # Validation rule
    rule_name = Column(String(255), nullable=False, index=True)
    rule_description = Column(Text, nullable=False)
    rule_type = Column(String(50), nullable=False)  # FORMAT, RANGE, CONSISTENCY

    # Rule parameters
    rule_parameters = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Validation statistics
    last_run = Column(DateTime(timezone=True), nullable=True)
    records_checked = Column(Integer, default=0, nullable=False)
    records_passed = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<EPADataValidation(rule='{self.rule_name}')>"
