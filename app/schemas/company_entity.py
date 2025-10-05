"""
Company Entity Schemas for SEC Climate Disclosure API

Pydantic models for company entity management and hierarchical structures
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class EntityType(str, Enum):
    """Types of company entities"""
    
    SUBSIDIARY = "subsidiary"
    DIVISION = "division"
    FACILITY = "facility"
    BRANCH = "branch"
    JOINT_VENTURE = "joint_venture"


class ConsolidationMethod(str, Enum):
    """Consolidation methods for financial reporting"""
    
    FULL = "full"  # Full consolidation (>50% ownership)
    EQUITY = "equity"  # Equity method (20-50% ownership)
    PROPORTIONAL = "proportional"  # Proportional consolidation


class CompanyEntityBase(BaseModel):
    """Base schema for company entity"""
    
    name: str = Field(..., min_length=1, max_length=255, description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    ownership_percentage: float = Field(
        default=100.0, 
        ge=0.0, 
        le=100.0, 
        description="Ownership percentage (0-100)"
    )
    consolidation_method: ConsolidationMethod = Field(
        default=ConsolidationMethod.FULL,
        description="Consolidation method for reporting"
    )
    country: Optional[str] = Field(None, max_length=100, description="Country location")
    state_province: Optional[str] = Field(None, max_length=100, description="State or province")
    city: Optional[str] = Field(None, max_length=100, description="City location")
    sector: Optional[str] = Field(None, max_length=100, description="Industry sector")
    primary_activity: Optional[str] = Field(None, max_length=255, description="Primary business activity")
    operational_control: bool = Field(default=True, description="Whether company has operational control")

    @validator("ownership_percentage")
    def validate_ownership_percentage(cls, v):
        if not 0.0 <= v <= 100.0:
            raise ValueError("Ownership percentage must be between 0 and 100")
        return v


class CompanyEntityCreate(CompanyEntityBase):
    """Schema for creating a company entity"""
    
    company_id: UUID = Field(..., description="Parent company ID")
    parent_id: Optional[UUID] = Field(None, description="Parent entity ID (null for root entities)")

    class Config:
        schema_extra = {
            "example": {
                "company_id": "123e4567-e89b-12d3-a456-426614174000",
                "parent_id": None,
                "name": "Manufacturing Division",
                "entity_type": "division",
                "ownership_percentage": 100.0,
                "consolidation_method": "full",
                "country": "United States",
                "state_province": "California",
                "city": "San Francisco",
                "sector": "Manufacturing",
                "primary_activity": "Electronics manufacturing",
                "operational_control": True
            }
        }


class CompanyEntityUpdate(BaseModel):
    """Schema for updating a company entity"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    entity_type: Optional[EntityType] = None
    ownership_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    consolidation_method: Optional[ConsolidationMethod] = None
    country: Optional[str] = Field(None, max_length=100)
    state_province: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    sector: Optional[str] = Field(None, max_length=100)
    primary_activity: Optional[str] = Field(None, max_length=255)
    operational_control: Optional[bool] = None
    is_active: Optional[bool] = None

    @validator("ownership_percentage")
    def validate_ownership_percentage(cls, v):
        if v is not None and not 0.0 <= v <= 100.0:
            raise ValueError("Ownership percentage must be between 0 and 100")
        return v


class CompanyEntityResponse(CompanyEntityBase):
    """Schema for company entity response"""
    
    id: UUID
    company_id: UUID
    parent_id: Optional[UUID]
    level: int = Field(..., description="Hierarchy level (0=root, 1=child, etc.)")
    path: Optional[str] = Field(None, description="Materialized path in hierarchy")
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    effective_ownership: Optional[float] = Field(None, description="Effective ownership considering parent chain")
    full_path: Optional[str] = Field(None, description="Full hierarchical path")

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "company_id": "123e4567-e89b-12d3-a456-426614174001",
                "parent_id": None,
                "name": "Manufacturing Division",
                "entity_type": "division",
                "level": 0,
                "path": "Manufacturing Division",
                "ownership_percentage": 100.0,
                "consolidation_method": "full",
                "country": "United States",
                "state_province": "California",
                "city": "San Francisco",
                "sector": "Manufacturing",
                "primary_activity": "Electronics manufacturing",
                "operational_control": True,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "effective_ownership": 100.0,
                "full_path": "Manufacturing Division"
            }
        }


class EntityHierarchyNode(BaseModel):
    """Node in entity hierarchy tree"""
    
    entity: CompanyEntityResponse
    children: List['EntityHierarchyNode'] = []

    class Config:
        from_attributes = True


# Update forward reference
EntityHierarchyNode.model_rebuild()


class EntityHierarchyResponse(BaseModel):
    """Response schema for entity hierarchy"""
    
    company_id: UUID
    total_entities: int
    hierarchy: List[EntityHierarchyNode]

    class Config:
        from_attributes = True


class OwnershipValidationResult(BaseModel):
    """Result of ownership validation"""
    
    is_valid: bool
    total_entities: int
    issues: List[str] = []
    message: str

    class Config:
        schema_extra = {
            "example": {
                "is_valid": True,
                "total_entities": 5,
                "issues": [],
                "message": "Ownership structure is valid"
            }
        }


class EntitySummaryResponse(BaseModel):
    """Summary response for entity statistics"""
    
    company_id: UUID
    total_entities: int
    active_entities: int
    inactive_entities: int
    max_hierarchy_level: int
    total_ownership_issues: int
    consolidation_methods: Dict[str, int]

    class Config:
        schema_extra = {
            "example": {
                "company_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_entities": 10,
                "active_entities": 8,
                "inactive_entities": 2,
                "max_hierarchy_level": 3,
                "total_ownership_issues": 0,
                "consolidation_methods": {
                    "full": 6,
                    "equity": 2,
                    "proportional": 0
                }
            }
        }


class BulkEntityOperation(BaseModel):
    """Schema for bulk entity operations"""
    
    operation: str = Field(..., description="Operation type: create, update, delete")
    entities: List[Dict] = Field(..., description="List of entity data")
    validate_ownership: bool = Field(default=True, description="Whether to validate ownership constraints")

    class Config:
        schema_extra = {
            "example": {
                "operation": "create",
                "entities": [
                    {
                        "name": "Subsidiary A",
                        "entity_type": "subsidiary",
                        "ownership_percentage": 75.0
                    },
                    {
                        "name": "Subsidiary B", 
                        "entity_type": "subsidiary",
                        "ownership_percentage": 25.0
                    }
                ],
                "validate_ownership": True
            }
        }


class BulkOperationResult(BaseModel):
    """Result of bulk entity operation"""
    
    success_count: int
    error_count: int
    total_processed: int
    errors: List[Dict] = []
    created_entities: List[UUID] = []

    class Config:
        schema_extra = {
            "example": {
                "success_count": 2,
                "error_count": 0,
                "total_processed": 2,
                "errors": [],
                "created_entities": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ]
            }
        }