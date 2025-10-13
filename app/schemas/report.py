"""
Report Schemas for Audit Lock and Collaboration
Pydantic models for report locking, comments, and revision tracking
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import AuditMixin


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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
