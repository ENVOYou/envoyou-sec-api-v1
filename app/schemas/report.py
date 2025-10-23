"""
Report Schemas for Audit Lock and Collaboration
Pydantic models for report locking, comments, and revision tracking
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import AuditMixin


# Basic CRUD Schemas
class ReportResponse(BaseModel):
    """Response schema for a report"""

    id: str
    title: str
    report_type: str
    status: str
    version: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    workflow_id: Optional[str] = None
    created_by: str
    updated_by: Optional[str] = None
    content: Optional[str] = None
    report_metadata: Optional[str] = None
    pdf_path: Optional[str] = None
    excel_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CreateReportRequest(BaseModel):
    """Request schema for creating a report"""

    title: str = Field(..., min_length=1, max_length=255)
    report_type: str = Field(
        ..., pattern="^(sec_10k|ghg_report|sustainability_report|esg_report)$"
    )
    company_id: str = Field(..., description="Company UUID")
    reporting_year: int = Field(..., ge=2020, le=2030)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    priority: Optional[str] = Field(
        default="medium", pattern="^(low|medium|high|urgent)$"
    )
    due_date: Optional[datetime] = None


class UpdateReportRequest(BaseModel):
    """Request schema for updating a report"""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    report_type: Optional[str] = Field(
        None, pattern="^(sec_10k|ghg_report|sustainability_report|esg_report)$"
    )
    status: Optional[str] = Field(
        None, pattern="^(draft|in_review|approved|locked|archived)$"
    )
    reporting_year: Optional[int] = Field(None, ge=2020, le=2030)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    due_date: Optional[datetime] = None
    content: Optional[str] = None
    report_metadata: Optional[str] = None


class ReportsListResponse(BaseModel):
    """Response schema for listing reports"""

    reports: List[ReportResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class ReportsFilters(BaseModel):
    """Filters for listing reports"""

    status: Optional[List[str]] = None
    report_type: Optional[List[str]] = None
    company_id: Optional[str] = None
    reporting_year: Optional[int] = None
    created_by: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sort_by: Optional[str] = Field(
        default="created_at", pattern="^(created_at|updated_at|title|status|priority)$"
    )
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")


class LockReportRequest(BaseModel):
    """Request to lock a report"""

    lock_reason: str = Field(..., min_length=1, max_length=255)
    expires_in_hours: Optional[int] = Field(None, ge=1, le=168)  # 1-7 days


class LockReportResponse(BaseModel):
    """Response when locking a report"""

    id: str
    report_id: str
    locked_by: str
    lock_reason: str
    locked_at: str
    expires_at: Optional[str] = None
    is_active: bool


class UnlockReportRequest(BaseModel):
    """Request to unlock a report"""

    reason: Optional[str] = Field(None, max_length=255)


class ReportLockStatus(BaseModel):
    """Current lock status of a report"""

    is_locked: bool
    locked_by: Optional[str] = None
    lock_reason: Optional[str] = None
    locked_at: Optional[str] = None
    expires_at: Optional[str] = None


class CommentCreate(BaseModel):
    """Request to create a comment"""

    content: str = Field(..., min_length=1, max_length=5000)
    comment_type: str = Field(
        default="general", pattern="^(general|question|suggestion|action_item)$"
    )
    parent_id: Optional[str] = None  # UUID string


class CommentResponse(BaseModel):
    """Response for a comment"""

    id: str
    report_id: str
    user_id: str
    parent_id: Optional[str] = None
    content: str
    comment_type: str
    is_resolved: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportCommentList(BaseModel):
    """List of comments for a report"""

    comments: List[CommentResponse]


class RevisionResponse(BaseModel):
    """Response for a revision"""

    id: str
    report_id: str
    version: str
    revision_number: int
    changed_by: str
    change_type: str
    changes_summary: Optional[str] = None
    previous_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportRevisionList(BaseModel):
    """List of revisions for a report"""

    revisions: List[RevisionResponse]


class ReportLockInfo(BaseModel):
    """Lock information for a report"""

    is_locked: bool
    locked_by: Optional[str] = None
    locked_at: Optional[str] = None
    lock_reason: Optional[str] = None
    expires_at: Optional[str] = None


class RevisionCreate(BaseModel):
    """Request to create a revision"""

    change_type: str = Field(..., pattern="^(create|update|approve|reject)$")
    changes_summary: str = Field(..., min_length=1, max_length=1000)
    previous_version: Optional[str] = None


# Audit mixin for report-related models
class ReportAuditMixin(AuditMixin):
    """Audit mixin specifically for report models"""

    pass
