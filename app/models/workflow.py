"""
Workflow and Approval Models
Handles multi-level approval workflow for SEC compliance reports
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import GUID, JSON, AuditMixin, BaseModel


class WorkflowState(enum.Enum):
    """Workflow states for report approval process"""

    DRAFT = "draft"
    PENDING_FINANCE_APPROVAL = "pending_finance"
    PENDING_LEGAL_APPROVAL = "pending_legal"
    PENDING_CFO_APPROVAL = "pending_cfo"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_AUDIT = "under_audit"
    SUBMITTED_TO_SEC = "submitted"


class ApprovalAction(enum.Enum):
    """Actions that can be taken on approval requests"""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DELEGATE = "delegate"


class UserRole(enum.Enum):
    """User roles for approval workflow"""

    CFO = "cfo"
    GENERAL_COUNSEL = "general_counsel"
    FINANCE_TEAM = "finance_team"
    AUDITOR = "auditor"
    ADMIN = "admin"
    SUBMITTER = "submitter"


class WorkflowTemplate(BaseModel, AuditMixin):
    """Template defining approval workflow steps"""

    __tablename__ = "workflow_templates"

    # Template identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template configuration
    workflow_type = Column(
        String(100), nullable=False
    )  # "report_approval", "consolidation_approval"
    is_active = Column(Boolean, default=True, nullable=False)

    # Workflow steps configuration (JSON)
    steps_config = Column(JSON, nullable=False)  # List of approval steps with roles

    # Relationships
    workflows = relationship("Workflow", back_populates="template")

    def __repr__(self):
        return f"<WorkflowTemplate(name='{self.name}', type='{self.workflow_type}')>"


class Workflow(BaseModel, AuditMixin):
    """Main workflow instance for a specific report/item"""

    __tablename__ = "workflows"

    # Workflow identification
    template_id = Column(GUID(), ForeignKey("workflow_templates.id"), nullable=False)

    # Subject of workflow (what's being approved)
    subject_type = Column(
        String(100), nullable=False
    )  # "consolidated_emissions", "report"
    subject_id = Column(GUID(), nullable=False)  # ID of the subject being approved

    # Current workflow state
    current_state = Column(
        Enum(WorkflowState), default=WorkflowState.DRAFT, nullable=False
    )
    current_step = Column(String(100), nullable=True)  # Current approval step

    # Workflow metadata
    initiated_by = Column(GUID(), ForeignKey("users.id"), nullable=False)
    initiated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Workflow configuration
    priority = Column(
        String(20), default="normal", nullable=False
    )  # low, normal, high, urgent
    due_date = Column(DateTime(timezone=True), nullable=True)

    # Additional metadata
    workflow_metadata = Column(JSON, nullable=True)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="workflows")
    initiator = relationship("User", foreign_keys=[initiated_by])
    approval_requests = relationship(
        "ApprovalRequest", back_populates="workflow", cascade="all, delete-orphan"
    )

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("subject_type", "subject_id", name="uq_workflow_subject"),
    )

    def __repr__(self):
        return f"<Workflow(subject='{self.subject_type}:{self.subject_id}', state='{self.current_state}')>"


class ApprovalRequest(BaseModel, AuditMixin):
    """Individual approval request within a workflow"""

    __tablename__ = "approval_requests"

    # Request identification
    workflow_id = Column(GUID(), ForeignKey("workflows.id"), nullable=False)
    step_name = Column(String(100), nullable=False)
    sequence_order = Column(Integer, nullable=False)

    # Approver information
    assigned_to = Column(GUID(), ForeignKey("users.id"), nullable=False)
    assigned_role = Column(Enum(UserRole), nullable=False)

    # Request status
    status = Column(
        String(50), default="pending", nullable=False
    )  # pending, approved, rejected, delegated
    action_taken = Column(Enum(ApprovalAction), nullable=True)

    # Timing
    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)

    # Response details
    comments = Column(Text, nullable=True)
    response_metadata = Column(JSON, nullable=True)

    # Delegation (if applicable)
    delegated_to = Column(GUID(), ForeignKey("users.id"), nullable=True)
    delegation_reason = Column(Text, nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="approval_requests")
    assignee = relationship("User", foreign_keys=[assigned_to])
    delegate = relationship("User", foreign_keys=[delegated_to])

    def __repr__(self):
        return f"<ApprovalRequest(step='{self.step_name}', assignee='{self.assigned_to}', status='{self.status}')>"


class WorkflowHistory(BaseModel, AuditMixin):
    """Audit trail for workflow state changes"""

    __tablename__ = "workflow_history"

    # History identification
    workflow_id = Column(GUID(), ForeignKey("workflows.id"), nullable=False)

    # State change details
    from_state = Column(Enum(WorkflowState), nullable=True)
    to_state = Column(Enum(WorkflowState), nullable=False)
    action = Column(String(100), nullable=False)

    # Actor information
    actor_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    actor_role = Column(Enum(UserRole), nullable=False)

    # Change details
    change_timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    comments = Column(Text, nullable=True)
    change_metadata = Column(JSON, nullable=True)

    # System information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relationships
    workflow = relationship("Workflow")
    actor = relationship("User")

    def __repr__(self):
        return f"<WorkflowHistory(workflow='{self.workflow_id}', {self.from_state}→{self.to_state})>"


class NotificationQueue(BaseModel, AuditMixin):
    """Queue for workflow notifications"""

    __tablename__ = "notification_queue"

    # Notification identification
    workflow_id = Column(GUID(), ForeignKey("workflows.id"), nullable=False)
    recipient_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Notification details
    notification_type = Column(
        String(100), nullable=False
    )  # approval_request, status_change, reminder
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Delivery status
    status = Column(
        String(50), default="pending", nullable=False
    )  # pending, sent, failed
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery details
    delivery_method = Column(
        String(50), default="email", nullable=False
    )  # email, in_app, sms
    delivery_metadata = Column(JSON, nullable=True)

    # Retry information
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    workflow = relationship("Workflow")
    recipient = relationship("User")

    def __repr__(self):
        return f"<NotificationQueue(type='{self.notification_type}', recipient='{self.recipient_id}', status='{self.status}')>"
