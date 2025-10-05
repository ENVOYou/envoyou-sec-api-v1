"""
Workflow Schemas for SEC Climate Disclosure API

Pydantic models for multi-level approval workflow system
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    """Workflow states for report approval process"""
    
    DRAFT = "draft"
    PENDING_FINANCE_APPROVAL = "pending_finance"
    PENDING_LEGAL_APPROVAL = "pending_legal"
    PENDING_CFO_APPROVAL = "pending_cfo"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_AUDIT = "under_audit"
    SUBMITTED_TO_SEC = "submitted"


class ApprovalAction(str, Enum):
    """Actions that can be taken on approval requests"""
    
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"


class UserRole(str, Enum):
    """User roles for approval workflow"""
    
    CFO = "cfo"
    GENERAL_COUNSEL = "general_counsel"
    FINANCE_TEAM = "finance_team"
    AUDITOR = "auditor"
    ADMIN = "admin"
    SUBMITTER = "submitter"


class WorkflowStepConfig(BaseModel):
    """Configuration for a single workflow step"""
    
    step_name: str = Field(..., description="Name of the approval step")
    required_role: UserRole = Field(..., description="Role required for this step")
    sequence_order: int = Field(..., description="Order of this step in workflow")
    is_parallel: bool = Field(default=False, description="Can be executed in parallel with other steps")
    timeout_hours: Optional[int] = Field(None, description="Hours before step times out")
    auto_approve_conditions: Optional[Dict] = Field(None, description="Conditions for auto-approval")


class WorkflowTemplateCreate(BaseModel):
    """Schema for creating workflow templates"""
    
    name: str = Field(..., max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    workflow_type: str = Field(..., description="Type of workflow (report_approval, consolidation_approval)")
    steps_config: List[WorkflowStepConfig] = Field(..., description="List of workflow steps")


class WorkflowTemplateResponse(BaseModel):
    """Schema for workflow template responses"""
    
    id: UUID
    name: str
    description: Optional[str]
    workflow_type: str
    is_active: bool
    steps_config: List[WorkflowStepConfig]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCreate(BaseModel):
    """Schema for creating new workflows"""
    
    template_id: UUID = Field(..., description="ID of workflow template to use")
    subject_type: str = Field(..., description="Type of subject being approved")
    subject_id: UUID = Field(..., description="ID of subject being approved")
    priority: str = Field(default="normal", description="Workflow priority (low, normal, high, urgent)")
    due_date: Optional[datetime] = Field(None, description="Due date for workflow completion")
    metadata: Optional[Dict] = Field(None, description="Additional workflow metadata")


class WorkflowResponse(BaseModel):
    """Schema for workflow responses"""
    
    id: UUID
    template_id: UUID
    subject_type: str
    subject_id: UUID
    current_state: WorkflowState
    current_step: Optional[str]
    initiated_by: UUID
    initiated_at: datetime
    completed_at: Optional[datetime]
    priority: str
    due_date: Optional[datetime]
    metadata: Optional[Dict]

    model_config = {"from_attributes": True}


class ApprovalRequestCreate(BaseModel):
    """Schema for creating approval requests"""
    
    workflow_id: UUID = Field(..., description="ID of parent workflow")
    step_name: str = Field(..., description="Name of approval step")
    sequence_order: int = Field(..., description="Order of this request in workflow")
    assigned_to: UUID = Field(..., description="User ID of assignee")
    assigned_role: UserRole = Field(..., description="Role of assignee")
    due_date: Optional[datetime] = Field(None, description="Due date for this approval")
    comments: Optional[str] = Field(None, description="Initial comments or instructions")


class ApprovalRequestResponse(BaseModel):
    """Schema for approval request responses"""
    
    id: UUID
    workflow_id: UUID
    step_name: str
    sequence_order: int
    assigned_to: UUID
    assigned_role: UserRole
    status: str
    action_taken: Optional[ApprovalAction]
    assigned_at: datetime
    responded_at: Optional[datetime]
    due_date: Optional[datetime]
    comments: Optional[str]
    response_metadata: Optional[Dict]
    delegated_to: Optional[UUID]
    delegation_reason: Optional[str]

    model_config = {"from_attributes": True}


class ApprovalActionRequest(BaseModel):
    """Schema for taking action on approval requests"""
    
    action: ApprovalAction = Field(..., description="Action to take")
    comments: Optional[str] = Field(None, max_length=2000, description="Comments for the action")
    delegate_to: Optional[UUID] = Field(None, description="User to delegate to (if action is delegate)")
    delegation_reason: Optional[str] = Field(None, description="Reason for delegation")
    metadata: Optional[Dict] = Field(None, description="Additional action metadata")


class WorkflowHistoryResponse(BaseModel):
    """Schema for workflow history responses"""
    
    id: UUID
    workflow_id: UUID
    from_state: Optional[WorkflowState]
    to_state: WorkflowState
    action: str
    actor_id: UUID
    actor_role: UserRole
    change_timestamp: datetime
    comments: Optional[str]
    change_metadata: Optional[Dict]

    model_config = {"from_attributes": True}


class WorkflowSummary(BaseModel):
    """Summary view of workflow with current status"""
    
    id: UUID
    subject_type: str
    subject_id: UUID
    current_state: WorkflowState
    current_step: Optional[str]
    initiated_by: UUID
    initiated_at: datetime
    priority: str
    due_date: Optional[datetime]
    
    # Summary statistics
    total_steps: int
    completed_steps: int
    pending_steps: int
    overdue_steps: int
    
    # Current pending approvals
    pending_approvals: List[ApprovalRequestResponse] = []


class NotificationCreate(BaseModel):
    """Schema for creating notifications"""
    
    workflow_id: UUID = Field(..., description="ID of related workflow")
    recipient_id: UUID = Field(..., description="ID of notification recipient")
    notification_type: str = Field(..., description="Type of notification")
    subject: str = Field(..., max_length=255, description="Notification subject")
    message: str = Field(..., description="Notification message")
    delivery_method: str = Field(default="email", description="Delivery method")
    scheduled_at: Optional[datetime] = Field(None, description="When to send notification")


class NotificationResponse(BaseModel):
    """Schema for notification responses"""
    
    id: UUID
    workflow_id: UUID
    recipient_id: UUID
    notification_type: str
    subject: str
    message: str
    status: str
    delivery_method: str
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    retry_count: int

    model_config = {"from_attributes": True}


class WorkflowMetrics(BaseModel):
    """Metrics and analytics for workflow performance"""
    
    total_workflows: int
    active_workflows: int
    completed_workflows: int
    overdue_workflows: int
    
    # Performance metrics
    average_completion_time_hours: float
    approval_rate: float  # Percentage of workflows that get approved
    
    # By state breakdown
    workflows_by_state: Dict[WorkflowState, int]
    
    # By role metrics
    pending_by_role: Dict[UserRole, int]
    average_response_time_by_role: Dict[UserRole, float]


class BulkApprovalRequest(BaseModel):
    """Schema for bulk approval actions"""
    
    approval_request_ids: List[UUID] = Field(..., description="List of approval request IDs")
    action: ApprovalAction = Field(..., description="Action to take on all requests")
    comments: Optional[str] = Field(None, description="Comments for all approvals")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")


class WorkflowSearchRequest(BaseModel):
    """Schema for searching workflows"""
    
    subject_type: Optional[str] = Field(None, description="Filter by subject type")
    current_state: Optional[WorkflowState] = Field(None, description="Filter by current state")
    initiated_by: Optional[UUID] = Field(None, description="Filter by initiator")
    assigned_to: Optional[UUID] = Field(None, description="Filter by current assignee")
    priority: Optional[str] = Field(None, description="Filter by priority")
    overdue_only: bool = Field(default=False, description="Show only overdue workflows")
    date_from: Optional[datetime] = Field(None, description="Filter workflows created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter workflows created before this date")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")