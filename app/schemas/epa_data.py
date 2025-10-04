"""
EPA data schemas for request/response validation
"""

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import validator

from app.models.epa_data import ElectricityRegion
from app.models.epa_data import EmissionFactorSource
from app.models.epa_data import FuelType


class EmissionFactorBase(BaseModel):
    """Base emission factor schema"""

    factor_name: str
    factor_code: str
    category: str
    fuel_type: Optional[str] = None
    electricity_region: Optional[str] = None
    unit: str
    co2_factor: float
    ch4_factor: Optional[float] = None
    n2o_factor: Optional[float] = None
    co2e_factor: float
    source: str
    source_document: Optional[str] = None
    source_url: Optional[str] = None
    publication_year: int
    version: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    description: Optional[str] = None
    methodology: Optional[str] = None
    uncertainty: Optional[float] = None
    additional_data: Optional[Dict[str, Any]] = None

    @validator("co2_factor", "ch4_factor", "n2o_factor", "co2e_factor")
    def validate_positive_factors(cls, v):
        if v is not None and v < 0:
            raise ValueError("Emission factors must be non-negative")
        return v

    @validator("uncertainty")
    def validate_uncertainty(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Uncertainty must be between 0 and 100 percent")
        return v


class EmissionFactorCreate(EmissionFactorBase):
    """Schema for creating emission factors"""

    pass


class EmissionFactorUpdate(BaseModel):
    """Schema for updating emission factors"""

    factor_name: Optional[str] = None
    description: Optional[str] = None
    methodology: Optional[str] = None
    uncertainty: Optional[float] = None
    additional_data: Optional[Dict[str, Any]] = None
    valid_to: Optional[datetime] = None
    is_current: Optional[bool] = None


class EmissionFactorResponse(EmissionFactorBase):
    """Schema for emission factor responses"""

    id: str
    is_current: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class EmissionFactorQuery(BaseModel):
    """Schema for querying emission factors"""

    category: Optional[str] = None
    fuel_type: Optional[str] = None
    electricity_region: Optional[str] = None
    source: Optional[str] = None
    publication_year: Optional[int] = None
    version: Optional[str] = None
    is_current: Optional[bool] = True
    valid_date: Optional[datetime] = None


class EPADataUpdateRequest(BaseModel):
    """Schema for EPA data update requests"""

    update_type: str  # FULL, INCREMENTAL
    source: str
    source_file: Optional[str] = None
    force_update: bool = False

    @validator("update_type")
    def validate_update_type(cls, v):
        if v not in ["FULL", "INCREMENTAL"]:
            raise ValueError("Update type must be FULL or INCREMENTAL")
        return v


class EPADataUpdateResponse(BaseModel):
    """Schema for EPA data update responses"""

    id: str
    update_type: str
    source: str
    status: str
    records_added: int
    records_updated: int
    records_deprecated: int
    processing_time_seconds: Optional[float] = None
    validation_passed: bool
    validation_errors: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ValidationResult(BaseModel):
    """Schema for validation results"""

    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    records_validated: int
    records_passed: int
    records_failed: int


class EPAFactorSummary(BaseModel):
    """Schema for EPA factor summary statistics"""

    total_factors: int
    current_factors: int
    deprecated_factors: int
    categories: Dict[str, int]
    sources: Dict[str, int]
    latest_update: Optional[datetime] = None
    oldest_factor: Optional[datetime] = None


class FuelEmissionFactorRequest(BaseModel):
    """Schema for requesting fuel emission factors"""

    fuel_type: str
    year: Optional[int] = None
    region: Optional[str] = None

    @validator("fuel_type")
    def validate_fuel_type(cls, v):
        valid_fuels = [fuel.value for fuel in FuelType]
        if v not in valid_fuels:
            raise ValueError(f"Invalid fuel type. Must be one of: {valid_fuels}")
        return v


class ElectricityEmissionFactorRequest(BaseModel):
    """Schema for requesting electricity emission factors"""

    region: str
    year: Optional[int] = None

    @validator("region")
    def validate_region(cls, v):
        valid_regions = [region.value for region in ElectricityRegion]
        if v.lower() not in valid_regions:
            raise ValueError(
                f"Invalid electricity region. Must be one of: {valid_regions}"
            )
        return v.lower()


class EmissionFactorBulkUpload(BaseModel):
    """Schema for bulk upload of emission factors"""

    factors: List[EmissionFactorCreate]
    source: str
    version: str
    publication_year: int
    replace_existing: bool = False

    @validator("factors")
    def validate_factors_not_empty(cls, v):
        if not v:
            raise ValueError("At least one emission factor is required")
        return v
