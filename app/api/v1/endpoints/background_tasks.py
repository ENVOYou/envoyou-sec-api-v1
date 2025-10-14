"""
Background Task Management Endpoints
API endpoints for managing asynchronous background tasks
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.background_tasks import (
    BulkCalculationRequest,
    TaskStatusResponse,
    TaskSubmissionResponse,
)
from app.services.background_tasks import background_task_service

router = APIRouter()


@router.post("/emissions/calculate", response_model=TaskSubmissionResponse)
async def submit_emissions_calculation(
    request: BulkCalculationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Submit emissions calculations for background processing

    This endpoint allows submitting multiple emissions calculations
    that will be processed asynchronously in the background.
    Useful for large datasets or complex calculations.
    """
    try:
        # Convert request to background task format
        calculations = []
        for calc in request.calculations:
            calc_dict = calc.dict()
            calc_dict["user_id"] = str(current_user.id)
            calculations.append(calc_dict)

        # Submit bulk calculation
        batch_task_id = await background_task_service.submit_bulk_calculation(
            calculations=calculations,
            user_id=str(current_user.id),
            batch_size=request.batch_size or 10,
        )

        return TaskSubmissionResponse(
            task_id=batch_task_id,
            status="submitted",
            message=f"Submitted {len(calculations)} calculations for background processing",
            estimated_completion_time=f"~{len(calculations) * 30} seconds",  # Rough estimate
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit calculations: {str(e)}",
        )


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get status of a background task

    Returns current status, progress, and results if completed.
    """
    try:
        status_info = await background_task_service.get_task_status(task_id)

        return TaskStatusResponse(
            task_id=status_info["task_id"],
            status=status_info["status"],
            message=status_info.get("message", ""),
            result=status_info.get("result"),
            error=status_info.get("error"),
            created_at=status_info.get("created_at"),
            completed_at=status_info.get("completed_at"),
            failed_at=status_info.get("failed_at"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.delete("/task/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancel a running background task

    Only the user who submitted the task can cancel it.
    """
    try:
        cancelled = await background_task_service.cancel_task(task_id)

        if cancelled:
            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task cancelled successfully",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found or already completed",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get("/tasks/active", response_model=List[TaskStatusResponse])
async def get_active_tasks(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get list of currently active background tasks for the user
    """
    try:
        active_tasks = await background_task_service.get_active_tasks()

        return [
            TaskStatusResponse(
                task_id=task["task_id"],
                status=task["status"],
                message="Task is currently running",
            )
            for task in active_tasks
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active tasks: {str(e)}",
        )
