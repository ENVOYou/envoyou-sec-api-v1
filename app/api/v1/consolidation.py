"""
Consolidation API endpoints for SEC Climate Disclosure API
Handles multi-entity emissions consolidation
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User
from app.schemas.consolidation import (
    ConsolidationApproval,
    ConsolidationComparison,
    ConsolidationDetailResponse,
    ConsolidationRequest,
    ConsolidationResponse,
    ConsolidationStatus,
    ConsolidationSummary,
)
from app.services.emissions_consolidation_service import EmissionsConsolidationService

router = APIRouter(prefix="/consolidation", tags=["consolidation"])


@router.post(
    "/", response_model=ConsolidationDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_consolidation(
    request: ConsolidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new emissions consolidation for multi-entity companies.

    This endpoint consolidates emissions data from multiple entities based on
    ownership structure and consolidation method.
    """
    service = EmissionsConsolidationService(db)
    return await service.create_consolidation(request, str(current_user.id))


@router.get("/{consolidation_id}", response_model=ConsolidationDetailResponse)
async def get_consolidation(
    consolidation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed consolidation data including entity contributions.
    """
    service = EmissionsConsolidationService(db)
    return await service.get_consolidation(consolidation_id)


@router.get("/company/{company_id}", response_model=List[ConsolidationResponse])
async def list_company_consolidations(
    company_id: UUID,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    status: Optional[ConsolidationStatus] = Query(
        None, description="Filter by consolidation status"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all consolidations for a specific company.

    Results are ordered by consolidation date (most recent first).
    """
    service = EmissionsConsolidationService(db)
    return await service.list_consolidations(
        company_id=company_id,
        reporting_year=reporting_year,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/company/{company_id}/summary/{reporting_year}",
    response_model=ConsolidationSummary,
)
async def get_consolidation_summary(
    company_id: UUID,
    reporting_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get consolidation summary for a company and reporting year.

    Provides overview of all consolidations, coverage statistics, and latest totals.
    """
    service = EmissionsConsolidationService(db)
    return await service.get_consolidation_summary(company_id, reporting_year)


@router.post("/{consolidation_id}/approve", response_model=ConsolidationResponse)
async def approve_consolidation(
    consolidation_id: UUID,
    approval: ConsolidationApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve or reject a consolidation.

    Only approved consolidations can be used for SEC reporting.
    """
    service = EmissionsConsolidationService(db)

    if approval.action == "approve":
        return await service.approve_consolidation(
            consolidation_id=consolidation_id,
            user_id=str(current_user.id),
            approval_notes=approval.approval_notes,
        )
    else:
        # Handle rejection logic here
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Consolidation rejection not yet implemented",
        )


@router.get("/{consolidation_id}/audit-trail")
async def get_consolidation_audit_trail(
    consolidation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get audit trail for a specific consolidation.

    Shows all events and changes made to the consolidation.
    """
    # This would be implemented to return audit trail
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Audit trail endpoint not yet implemented",
    )


@router.post(
    "/{consolidation_id}/recalculate", response_model=ConsolidationDetailResponse
)
async def recalculate_consolidation(
    consolidation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recalculate an existing consolidation with updated data.

    Creates a new version of the consolidation with current entity data.
    """
    # This would implement recalculation logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Recalculation endpoint not yet implemented",
    )


@router.get("/compare/{base_id}/{compare_id}", response_model=ConsolidationComparison)
async def compare_consolidations(
    base_id: UUID,
    compare_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare two consolidations to analyze differences.

    Useful for understanding changes between versions or years.
    """
    # This would implement comparison logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Comparison endpoint not yet implemented",
    )


@router.get("/company/{company_id}/validation/{reporting_year}")
async def validate_consolidation_readiness(
    company_id: UUID,
    reporting_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate if a company is ready for consolidation.

    Checks data availability, entity structure, and other prerequisites.
    """
    # This would implement validation logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Validation endpoint not yet implemented",
    )


@router.delete("/{consolidation_id}")
async def delete_consolidation(
    consolidation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a consolidation (soft delete).

    Only draft consolidations can be deleted.
    """
    # This would implement soft delete logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Delete endpoint not yet implemented",
    )


@router.get("/methods")
async def get_consolidation_methods():
    """
    Get available consolidation methods and their descriptions.
    """
    return {
        "methods": [
            {
                "value": "ownership_based",
                "name": "Ownership Based",
                "description": "Consolidate based on ownership percentage",
            },
            {
                "value": "operational_control",
                "name": "Operational Control",
                "description": "Consolidate entities with operational control (100% or 0%)",
            },
            {
                "value": "financial_control",
                "name": "Financial Control",
                "description": "Consolidate entities with financial control (100% or 0%)",
            },
            {
                "value": "equity_share",
                "name": "Equity Share",
                "description": "Consolidate based on equity share percentage",
            },
        ]
    }
