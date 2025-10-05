# Database models package

# AuditLog imported separately to avoid circular imports
from app.models.base import AuditMixin, BaseModel, TimestampMixin, UUIDMixin
from app.models.emissions import (
    ActivityData,
    CalculationAuditTrail,
    CalculationMethod,
    CalculationStatus,
    Company,
    CompanyEntity,
    EmissionsCalculation,
    EmissionScope,
)
from app.models.epa_data import (
    ElectricityRegion,
    EmissionFactor,
    EmissionFactorSource,
    EPADataUpdate,
    EPADataValidation,
    FuelType,
)
from app.models.user import User, UserRole, UserStatus

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "UUIDMixin",
    "AuditMixin",
    "User",
    "UserRole",
    "UserStatus",
    "EmissionFactor",
    "EPADataUpdate",
    "EPADataValidation",
    "FuelType",
    "ElectricityRegion",
    "EmissionFactorSource",
    "Company",
    "CompanyEntity",
    "EmissionsCalculation",
    "ActivityData",
    "CalculationAuditTrail",
    "EmissionScope",
    "CalculationStatus",
    "CalculationMethod",
    # "AuditLog",  # Imported separately to avoid circular imports
]
