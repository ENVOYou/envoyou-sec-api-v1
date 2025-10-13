"""
Workflow and approval endpoints
Multi-level approval workflow for report submission
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.workflow import (
    ApprovalRequest,
    ApprovalResponse,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowStatusUpdate,
    WorkflowSummary,
)
from app.services.workflow_service import WorkflowService

router = APIRouter()


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    request: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new approval workflow

    Initializes a multi-level approval workflow for emissions reports
    with configurable approval stages and routing.
    """
    workflow_service = WorkflowService(db)

    try:
        workflow = await workflow_service.create_workflow(
            workflow_data=request,
            created_by=str(current_user.id),
        )

        return WorkflowResponse(
            id=str(workflow.id),
            title=workflow.title,
            description=workflow.description,
            workflow_type=workflow.workflow_type,
            status=workflow.status,
            priority=workflow.priority,
            created_by=str(workflow.created_by),
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            due_date=workflow.due_date,
            current_stage=workflow.current_stage,
            total_stages=workflow.total_stages,
            approvers=[str(a.user_id) for a in workflow.approvers],
            attachments=workflow.attachments or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workflow: {str(e)}",
        )


@router.get("/", response_model=List[WorkflowSummary])
async def get_workflows(
    status_filter: Optional[str] = Query(None, description="Filter by workflow status"),
    workflow_type: Optional[str] = Query(None, description="Filter by workflow type"),
    assigned_to_me: bool = Query(
        False, description="Show only workflows assigned to current user"
    ),
    created_by_me: bool = Query(
        False, description="Show only workflows created by current user"
    ),
    limit: int = Query(50, le=200, description="Maximum number of workflows"),
    offset: int = Query(0, ge=0, description="Number of workflows to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of workflows with optional filtering

    Provides comprehensive view of all workflows with advanced filtering
    and pagination capabilities.
    """
    workflow_service = WorkflowService(db)

    try:
        workflows = await workflow_service.get_workflows(
            user_id=str(current_user.id),
            status=status_filter,
            workflow_type=workflow_type,
            assigned_to_me=assigned_to_me,
            created_by_me=created_by_me,
            limit=limit,
            offset=offset,
        )

        return [
            WorkflowSummary(
                id=str(w.id),
                title=w.title,
                workflow_type=w.workflow_type,
                status=w.status,
                priority=w.priority,
                created_by=str(w.created_by),
                created_at=w.created_at,
                due_date=w.due_date,
                current_stage=w.current_stage,
                total_stages=w.total_stages,
                pending_approvals=len(
                    [a for a in w.approvers if a.status == "pending"]
                ),
            )
            for w in workflows
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workflows: {str(e)}",
        )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed workflow information

    Provides complete workflow details including approval history,
    current status, and next steps.
    """
    workflow_service = WorkflowService(db)

    try:
        workflow = await workflow_service.get_workflow(
            workflow_id, str(current_user.id)
        )

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )

        return WorkflowResponse(
            id=str(workflow.id),
            title=workflow.title,
            description=workflow.description,
            workflow_type=workflow.workflow_type,
            status=workflow.status,
            priority=workflow.priority,
            created_by=str(workflow.created_by),
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            due_date=workflow.due_date,
            current_stage=workflow.current_stage,
            total_stages=workflow.total_stages,
            approvers=[str(a.user_id) for a in workflow.approvers],
            attachments=workflow.attachments or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workflow: {str(e)}",
        )


@router.post("/{workflow_id}/submit")
async def submit_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit workflow for approval

    Moves workflow from draft to pending approval status and
    notifies assigned approvers.
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.submit_workflow(
            workflow_id=workflow_id,
            submitted_by=str(current_user.id),
        )

        return {
            "message": "Workflow submitted successfully",
            "workflow_id": workflow_id,
            "status": result["status"],
            "next_approvers": result["next_approvers"],
            "submitted_at": result["submitted_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit workflow: {str(e)}",
        )


@router.post("/{workflow_id}/approve", response_model=ApprovalResponse)
async def approve_workflow(
    workflow_id: str,
    request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Approve or reject a workflow stage

    Processes approval decisions and advances workflow to next stage
    or completes the workflow based on approval rules.
    """
    workflow_service = WorkflowService(db)

    try:
        approval_result = await workflow_service.approve_workflow(
            workflow_id=workflow_id,
            approver_id=str(current_user.id),
            decision=request.decision,
            comments=request.comments,
            attachments=request.attachments,
        )

        return ApprovalResponse(
            workflow_id=workflow_id,
            decision=request.decision,
            approved_by=str(current_user.id),
            approved_at=approval_result["approved_at"],
            next_stage=approval_result.get("next_stage"),
            workflow_completed=approval_result.get("workflow_completed", False),
            final_status=approval_result.get("final_status"),
            comments=request.comments,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}",
        )


@router.get("/{workflow_id}/approvals")
async def get_workflow_approvals(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get approval history for a workflow

    Provides complete audit trail of all approval actions,
    comments, and decisions made during the workflow lifecycle.
    """
    workflow_service = WorkflowService(db)

    try:
        approvals = await workflow_service.get_workflow_approvals(workflow_id)

        return {
            "workflow_id": workflow_id,
            "total_approvals": len(approvals),
            "approvals": [
                {
                    "stage": a.stage,
                    "approver_id": str(a.approver_id),
                    "decision": a.decision,
                    "comments": a.comments,
                    "approved_at": a.approved_at,
                    "attachments": a.attachments,
                }
                for a in approvals
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workflow approvals: {str(e)}",
        )


@router.put("/{workflow_id}/status")
async def update_workflow_status(
    workflow_id: str,
    request: WorkflowStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update workflow status (admin only)

    Allows administrators to manually update workflow status
    for exceptional circumstances.
    """
    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update workflow status",
        )

    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.update_workflow_status(
            workflow_id=workflow_id,
            new_status=request.status,
            updated_by=str(current_user.id),
            reason=request.reason,
        )

        return {
            "message": f"Workflow status updated to {request.status}",
            "workflow_id": workflow_id,
            "previous_status": result["previous_status"],
            "new_status": request.status,
            "updated_by": str(current_user.id),
            "updated_at": result["updated_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow status: {str(e)}",
        )


@router.get("/pending-approvals")
async def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get workflows pending current user's approval

    Shows all workflows where the current user is an assigned approver
    and their approval is still pending.
    """
    workflow_service = WorkflowService(db)

    try:
        pending_workflows = await workflow_service.get_pending_approvals(
            user_id=str(current_user.id)
        )

        return {
            "total_pending": len(pending_workflows),
            "workflows": [
                {
                    "workflow_id": str(w.id),
                    "title": w.title,
                    "workflow_type": w.workflow_type,
                    "priority": w.priority,
                    "submitted_at": w.created_at,
                    "due_date": w.due_date,
                    "current_stage": w.current_stage,
                    "total_stages": w.total_stages,
                }
                for w in pending_workflows
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending approvals: {str(e)}",
        )


@router.post("/{workflow_id}/escalate")
async def escalate_workflow(
    workflow_id: str,
    reason: str = Query(..., description="Reason for escalation"),
    priority_increase: Optional[str] = Query(
        None, description="New priority level (high, urgent)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Escalate workflow priority

    Allows users to escalate workflow priority for urgent matters
    requiring faster processing.
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.escalate_workflow(
            workflow_id=workflow_id,
            escalated_by=str(current_user.id),
            reason=reason,
            new_priority=priority_increase,
        )

        return {
            "message": "Workflow escalated successfully",
            "workflow_id": workflow_id,
            "new_priority": result["new_priority"],
            "escalated_at": result["escalated_at"],
            "escalation_reason": reason,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to escalate workflow: {str(e)}",
        )
