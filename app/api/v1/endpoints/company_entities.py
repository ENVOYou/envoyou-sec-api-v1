"""
Company Entity Management API Endpoints

Handles hierarchical company structure, ownership, and entity relationships
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.auth import require_roles
from app.models.user import User
from app.schemas.company_entity import (
    BulkEntityOperation,
    BulkOperationResult,
    CompanyEntityCreate,
    CompanyEntityResponse,
    CompanyEntityUpdate,
    EntityHierarchyResponse,
    EntitySummaryResponse,
    OwnershipValidationResult,
)
from app.services.company_entity_service import CompanyEntityService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=CompanyEntityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create company entity",
    description="Create a new company entity with hierarchical structure and ownership information",
)
async def create_entity(
    entity_data: CompanyEntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo", "finance_team"])),
):
    """
    Create a new company entity.
    
    - **company_id**: Parent company ID
    - **parent_id**: Parent entity ID (null for root entities)
    - **name**: Entity name
    - **entity_type**: Type of entity (subsidiary, division, facility, etc.)
    - **ownership_percentage**: Ownership percentage (0-100)
    - **consolidation_method**: Consolidation method for reporting
    - **location**: Country, state/province, city information
    - **operational_control**: Whether company has operational control
    
    Requires: Admin, CFO, or Finance Team role
    """
    service = CompanyEntityService(db)
    return await service.create_entity(entity_data, str(current_user.id))


@router.get(
    "/{entity_id}",
    response_model=CompanyEntityResponse,
    summary="Get company entity",
    description="Retrieve a specific company entity by ID",
)
async def get_entity(
    entity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific company entity by ID."""
    service = CompanyEntityService(db)
    return await service.get_entity(entity_id)


@router.put(
    "/{entity_id}",
    response_model=CompanyEntityResponse,
    summary="Update company entity",
    description="Update company entity information and ownership structure",
)
async def update_entity(
    entity_id: UUID,
    entity_data: CompanyEntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo", "finance_team"])),
):
    """
    Update company entity information.
    
    - Validates ownership constraints when ownership percentage is changed
    - Recalculates materialized path when name is changed
    - Maintains audit trail of all changes
    
    Requires: Admin, CFO, or Finance Team role
    """
    service = CompanyEntityService(db)
    return await service.update_entity(entity_id, entity_data, str(current_user.id))


@router.delete(
    "/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete company entity",
    description="Soft delete a company entity (cannot delete entities with active children)",
)
async def delete_entity(
    entity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"])),
):
    """
    Delete a company entity (soft delete).
    
    - Cannot delete entities with active children
    - Maintains audit trail of deletion
    - Entity becomes inactive but data is preserved
    
    Requires: Admin or CFO role
    """
    service = CompanyEntityService(db)
    await service.delete_entity(entity_id, str(current_user.id))


@router.get(
    "/company/{company_id}",
    response_model=List[CompanyEntityResponse],
    summary="Get company entities",
    description="Get all entities for a specific company",
)
async def get_company_entities(
    company_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive entities"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all entities for a specific company.
    
    - Returns entities ordered by hierarchy level and name
    - Optionally includes inactive entities
    - Shows complete entity structure
    """
    service = CompanyEntityService(db)
    return await service.get_company_entities(company_id, include_inactive)


@router.get(
    "/company/{company_id}/hierarchy",
    response_model=EntityHierarchyResponse,
    summary="Get entity hierarchy",
    description="Get complete hierarchical structure of company entities",
)
async def get_entity_hierarchy(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete entity hierarchy for a company.
    
    - Returns nested tree structure
    - Shows parent-child relationships
    - Includes ownership percentages and effective ownership
    - Useful for visualization and reporting
    """
    service = CompanyEntityService(db)
    return await service.get_entity_hierarchy(company_id)


@router.get(
    "/{entity_id}/children",
    response_model=List[CompanyEntityResponse],
    summary="Get entity children",
    description="Get children entities of a specific entity",
)
async def get_entity_children(
    entity_id: UUID,
    recursive: bool = Query(False, description="Get all descendants recursively"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get children of a specific entity.
    
    - **recursive=false**: Direct children only
    - **recursive=true**: All descendants (children, grandchildren, etc.)
    - Uses efficient recursive CTE queries for deep hierarchies
    """
    service = CompanyEntityService(db)
    return await service.get_entity_children(entity_id, recursive)


@router.get(
    "/company/{company_id}/validate-ownership",
    response_model=OwnershipValidationResult,
    summary="Validate ownership structure",
    description="Validate ownership constraints for entire company structure",
)
async def validate_ownership_structure(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo", "finance_team", "auditor"])),
):
    """
    Validate ownership structure for entire company.
    
    - Checks that children ownership doesn't exceed 100% for any parent
    - Identifies ownership constraint violations
    - Returns detailed validation report
    - Essential for compliance and audit purposes
    
    Requires: Admin, CFO, Finance Team, or Auditor role
    """
    service = CompanyEntityService(db)
    return await service.validate_ownership_structure(company_id)


@router.get(
    "/company/{company_id}/summary",
    response_model=EntitySummaryResponse,
    summary="Get entity summary statistics",
    description="Get summary statistics for company entity structure",
)
async def get_entity_summary(
    company_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get summary statistics for company entity structure.
    
    - Total and active entity counts
    - Maximum hierarchy depth
    - Consolidation method distribution
    - Ownership validation status
    """
    service = CompanyEntityService(db)
    entities = await service.get_company_entities(company_id, include_inactive=True)
    
    # Calculate summary statistics
    active_entities = [e for e in entities if e.is_active]
    inactive_entities = [e for e in entities if not e.is_active]
    max_level = max([e.level for e in entities], default=0)
    
    # Count consolidation methods
    consolidation_counts = {}
    for entity in active_entities:
        method = entity.consolidation_method
        consolidation_counts[method] = consolidation_counts.get(method, 0) + 1
    
    # Check ownership issues
    validation_result = await service.validate_ownership_structure(company_id)
    
    return EntitySummaryResponse(
        company_id=company_id,
        total_entities=len(entities),
        active_entities=len(active_entities),
        inactive_entities=len(inactive_entities),
        max_hierarchy_level=max_level,
        total_ownership_issues=len(validation_result.issues),
        consolidation_methods=consolidation_counts
    )


@router.post(
    "/company/{company_id}/bulk",
    response_model=BulkOperationResult,
    summary="Bulk entity operations",
    description="Perform bulk operations on company entities",
)
async def bulk_entity_operations(
    company_id: UUID,
    operation_data: BulkEntityOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"])),
):
    """
    Perform bulk operations on company entities.
    
    - **create**: Create multiple entities at once
    - **update**: Update multiple entities
    - **delete**: Delete multiple entities
    - Validates ownership constraints if requested
    - Returns detailed operation results
    
    Requires: Admin or CFO role
    """
    service = CompanyEntityService(db)
    
    success_count = 0
    error_count = 0
    errors = []
    created_entities = []
    
    try:
        for i, entity_data in enumerate(operation_data.entities):
            try:
                if operation_data.operation == "create":
                    # Add company_id to entity data
                    entity_data["company_id"] = company_id
                    create_data = CompanyEntityCreate(**entity_data)
                    result = await service.create_entity(create_data, str(current_user.id))
                    created_entities.append(result.id)
                    success_count += 1
                    
                elif operation_data.operation == "update":
                    entity_id = UUID(entity_data.pop("id"))
                    update_data = CompanyEntityUpdate(**entity_data)
                    await service.update_entity(entity_id, update_data, str(current_user.id))
                    success_count += 1
                    
                elif operation_data.operation == "delete":
                    entity_id = UUID(entity_data["id"])
                    await service.delete_entity(entity_id, str(current_user.id))
                    success_count += 1
                    
                else:
                    raise ValueError(f"Unsupported operation: {operation_data.operation}")
                    
            except Exception as e:
                error_count += 1
                errors.append({
                    "index": i,
                    "entity_data": entity_data,
                    "error": str(e)
                })
                logger.error(f"Bulk operation error at index {i}: {str(e)}")
        
        # Validate ownership if requested
        if operation_data.validate_ownership and operation_data.operation in ["create", "update"]:
            validation_result = await service.validate_ownership_structure(company_id)
            if not validation_result.is_valid:
                errors.append({
                    "type": "ownership_validation",
                    "error": f"Ownership validation failed: {validation_result.message}",
                    "issues": validation_result.issues
                })
        
        return BulkOperationResult(
            success_count=success_count,
            error_count=error_count,
            total_processed=len(operation_data.entities),
            errors=errors,
            created_entities=created_entities
        )
        
    except Exception as e:
        logger.error(f"Bulk operation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )