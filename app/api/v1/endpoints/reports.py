"""
Report Management Endpoints
Handles report locking, comments, and revision tracking for audit and collaboration
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.db.database import get_db
from app.models.report import Comment, Report, ReportLock, Revision
from app.models.user import User
from app.schemas.report import (
    CommentCreate,
    CommentResponse,
    LockReportRequest,
    LockReportResponse,
    ReportCommentList,
    ReportLockStatus,
    ReportRevisionList,
    RevisionResponse,
    UnlockReportRequest,
)
from app.services.report_lock_service import ReportLockService

router = APIRouter()

report_lock_service = ReportLockService


@router.post("/{report_id}/lock", response_model=LockReportResponse)
async def lock_report(
    report_id: str,
    lock_data: LockReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lock a report for audit or review purposes"""
    try:
        service = ReportLockService(db)
        result = service.lock_report(
            report_id=report_id,
            user_id=current_user.id,
            lock_reason=lock_data.lock_reason,
            expires_in_hours=lock_data.expires_in_hours,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{report_id}/unlock")
async def unlock_report(
    report_id: str,
    unlock_data: UnlockReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Unlock a report"""
    try:
        service = ReportLockService(db)
        result = service.unlock_report(report_id=report_id, user_id=current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{report_id}/lock-status", response_model=ReportLockStatus)
async def get_report_lock_status(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get current lock status for a report"""
    try:
        service = ReportLockService(db)
        lock_status = service.get_lock_status(report_id=report_id)

        if lock_status:
            return ReportLockStatus(
                is_locked=True,
                locked_by=lock_status.locked_by,
                lock_reason=lock_status.lock_reason,
                locked_at=lock_status.locked_at,
                expires_at=lock_status.expires_at,
            )
        else:
            return ReportLockStatus(
                is_locked=False,
                locked_by=None,
                lock_reason=None,
                locked_at=None,
                expires_at=None,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{report_id}/locks", response_model=List[LockReportResponse])
async def get_report_locks(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get history of locks for a report"""
    try:
        service = ReportLockService(db)
        locks = service.get_report_locks(report_id=report_id)
        return locks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{report_id}/comments", response_model=CommentResponse)
async def add_comment_to_report(
    report_id: str,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a report"""
    try:
        service = ReportLockService(db)
        comment = service.add_comment(
            report_id=report_id,
            user_id=current_user.id,
            comment_data=comment_data,
        )
        return comment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{report_id}/comments", response_model=ReportCommentList)
async def get_report_comments(
    report_id: str,
    parent_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get comments for a report, optionally filtered by parent"""
    try:
        service = ReportLockService(db)
        comments = service.get_comments(
            report_id=report_id,
            parent_id=parent_id,
        )
        return ReportCommentList(comments=comments)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{report_id}/comments/{comment_id}/resolve")
async def resolve_report_comment(
    report_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Resolve a comment (mark as resolved)"""
    try:
        service = ReportLockService(db)
        comment = service.resolve_comment(
            comment_id=comment_id,
            user_id=current_user.id,
        )
        return comment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{report_id}/revisions", response_model=RevisionResponse)
async def create_report_revision(
    report_id: str,
    revision_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new revision for a report"""
    try:
        service = ReportLockService(db)
        revision = service.create_revision(
            report_id=report_id,
            user_id=current_user.id,
            change_type=revision_data.get("change_type", "update"),
            changes_summary=revision_data.get("changes_summary", "Manual revision"),
        )
        return revision
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{report_id}/revisions", response_model=ReportRevisionList)
async def get_report_revisions(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get revision history for a report"""
    try:
        service = ReportLockService(db)
        revisions = service.get_revisions(report_id=report_id)
        return ReportRevisionList(revisions=revisions)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
