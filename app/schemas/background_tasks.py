"""
Schemas for background task management
Request/response models for asynchronous task processing
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.emissions import Scope1CalculationRequest, Scope2CalculationRequest


class BulkCalculationRequest(BaseModel):
    """Schema for bulk calculation requests"""

    calculations: List[Dict[str, Any]] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of calculation requests (Scope 1 or Scope 2)",
    )
    batch_size: Optional[int] = Field(
        10, ge=1, le=50, description="Number of calculations to process in parallel"
    )

    class Config:
        schema_extra = {
            "example": {
                "calculations": [
                    {
                        "scope": "scope1",
                        "calculation_name": "Q4 Fuel Consumption",
                        "company_id": "company-uuid",
                        "reporting_period_start": "2024-10-01T00:00:00Z",
                        "reporting_period_end": "2024-12-31T23:59:59Z",
                        "activity_data": [
                            {
                                "activity_type": "stationary_combustion",
                                "fuel_type": "natural_gas",
                                "quantity": 1000.0,
                                "unit": "mmbtu",
                            }
                        ],
                    }
                ],
                "batch_size": 10,
            }
        }


class TaskSubmissionResponse(BaseModel):
    """Schema for task submission response"""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(
        ..., description="Task status (submitted, running, completed, failed)"
    )
    message: str = Field(..., description="Human-readable status message")
    estimated_completion_time: Optional[str] = Field(
        None, description="Estimated time to completion"
    )
    submitted_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="When the task was submitted"
    )


class TaskStatusResponse(BaseModel):
    """Schema for task status response"""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Current task status")
    message: Optional[str] = Field(None, description="Status message")
    progress: Optional[float] = Field(
        None, ge=0, le=100, description="Progress percentage (0-100)"
    )
    result: Optional[Any] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Task creation time")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    failed_at: Optional[datetime] = Field(None, description="Task failure time")


class BulkCalculationResult(BaseModel):
    """Schema for bulk calculation results"""

    batch_task_id: str = Field(..., description="Batch task identifier")
    total_calculations: int = Field(
        ..., description="Total number of calculations submitted"
    )
    successful: int = Field(..., description="Number of successful calculations")
    failed: int = Field(..., description="Number of failed calculations")
    results: List[Dict[str, Any]] = Field(
        ..., description="Individual calculation results"
    )
    completed_at: datetime = Field(..., description="Batch completion time")


class TaskQueueStatus(BaseModel):
    """Schema for task queue status"""

    active_tasks: int = Field(..., description="Number of currently active tasks")
    queued_tasks: int = Field(..., description="Number of tasks in queue")
    completed_today: int = Field(..., description="Tasks completed today")
    failed_today: int = Field(..., description="Tasks failed today")
    average_processing_time: Optional[float] = Field(
        None, description="Average task processing time in seconds"
    )


class BackgroundTaskMetrics(BaseModel):
    """Schema for background task performance metrics"""

    total_tasks_processed: int = Field(..., description="Total tasks processed")
    success_rate: float = Field(..., ge=0, le=1, description="Task success rate (0-1)")
    average_queue_time: float = Field(
        ..., description="Average time in queue (seconds)"
    )
    average_processing_time: float = Field(
        ..., description="Average processing time (seconds)"
    )
    peak_concurrent_tasks: int = Field(..., description="Peak concurrent tasks")
    tasks_by_type: Dict[str, int] = Field(..., description="Task count by type")
    errors_by_type: Dict[str, int] = Field(..., description="Error count by type")
