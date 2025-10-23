"""
Report Management Endpoints
Handles report locking, comments, and revision tracking for audit and collaboration
"""

from datetime import datetime
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
    CreateReportRequest,
    LockReportRequest,
    LockReportResponse,
    ReportCommentList,
    ReportLockInfo,
    ReportLockStatus,
    ReportResponse,
    ReportRevisionList,
    ReportsFilters,
    ReportsListResponse,
    RevisionResponse,
    UnlockReportRequest,
    UpdateReportRequest,
)
from app.services.report_lock_service import ReportLockService
from app.services.report_service import ReportService

router = APIRouter()

report_lock_service = ReportLockService
report_service = ReportService


@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify router is working"""
    return {"message": "Reports router is working"}


# CRUD Endpoints
@router.get("/", response_model=ReportsListResponse)
async def get_reports(
    status: Optional[List[str]] = None,
    report_type: Optional[List[str]] = None,
    company_id: Optional[str] = None,
    reporting_year: Optional[int] = None,
    created_by: Optional[str] = None,
    priority: Optional[List[str]] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get paginated list of reports with optional filtering"""
    try:
        filters = ReportsFilters(
            status=status,
            report_type=report_type,
            company_id=company_id,
            reporting_year=reporting_year,
            created_by=created_by,
            priority=priority,
            search=search,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        service = ReportService(db)
        result = service.get_reports(filters, page, page_size, current_user)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reports: {str(e)}",
        )


@router.post("/", response_model=ReportResponse)
async def create_report(
    report_data: CreateReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new report"""
    try:
        service = ReportService(db)
        report = service.create_report(report_data, current_user)

        return ReportResponse(
            id=str(report.id),
            title=report.title,
            report_type=report.report_type,
            status=report.status,
            version=report.version,
            created_at=report.created_at,
            updated_at=report.updated_at,
            completed_at=report.completed_at,
            workflow_id=str(report.workflow_id) if report.workflow_id else None,
            created_by=str(report.created_by),
            updated_by=str(report.updated_by) if report.updated_by else None,
            content=report.content,
            report_metadata=report.report_metadata,
            pdf_path=report.pdf_path,
            excel_path=report.excel_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create report: {str(e)}",
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific report by ID"""
    try:
        service = ReportService(db)
        report = service.get_report(report_id)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        return ReportResponse(
            id=str(report.id),
            title=report.title,
            report_type=report.report_type,
            status=report.status,
            version=report.version,
            created_at=report.created_at,
            updated_at=report.updated_at,
            completed_at=report.completed_at,
            workflow_id=str(report.workflow_id) if report.workflow_id else None,
            created_by=str(report.created_by),
            updated_by=str(report.updated_by) if report.updated_by else None,
            content=report.content,
            report_metadata=report.report_metadata,
            pdf_path=report.pdf_path,
            excel_path=report.excel_path,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get report: {str(e)}",
        )


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: str,
    report_data: UpdateReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update an existing report"""
    try:
        service = ReportService(db)
        report = service.update_report(report_id, report_data, current_user)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        return ReportResponse(
            id=str(report.id),
            title=report.title,
            report_type=report.report_type,
            status=report.status,
            version=report.version,
            created_at=report.created_at,
            updated_at=report.updated_at,
            completed_at=report.completed_at,
            workflow_id=str(report.workflow_id) if report.workflow_id else None,
            created_by=str(report.created_by),
            updated_by=str(report.updated_by) if report.updated_by else None,
            content=report.content,
            report_metadata=report.report_metadata,
            pdf_path=report.pdf_path,
            excel_path=report.excel_path,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update report: {str(e)}",
        )


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a report"""
    try:
        service = ReportService(db)
        result = service.delete_report(report_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        return {"success": True, "message": "Report deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete report: {str(e)}",
        )


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
        lock = service.lock_report(
            report_id=report_id,
            user=current_user,
            lock_reason=lock_data.lock_reason,
            expires_in_hours=lock_data.expires_in_hours or 24,
        )
        return LockReportResponse(
            id=str(lock.id),
            report_id=str(lock.report_id),
            locked_by=str(lock.locked_by),
            lock_reason=lock.lock_reason,
            locked_at=lock.locked_at.isoformat() if lock.locked_at else None,
            expires_at=lock.expires_at.isoformat() if lock.expires_at else None,
            is_active=lock.is_active,
        )
    except HTTPException:
        # Re-raise HTTPException as-is to preserve status code
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lock report: {str(e)}",
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
        result = service.unlock_report(
            report_id=report_id,
            user=current_user,
        )
        return {"success": result}
    except HTTPException:
        # Re-raise HTTPException as-is to preserve status code
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlock report: {str(e)}",
        )


@router.get("/{report_id}/lock-status", response_model=ReportLockStatus)
async def get_report_lock_status(
    report_id: str,
    db: Session = Depends(get_db),
):
    """Get current lock status for a report"""
    try:
        # Check if report exists
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        service = ReportLockService(db)
        lock = service.get_lock_status(report_id)

        if lock:
            return ReportLockStatus(
                is_locked=True,
                locked_by=str(lock.locked_by),
                lock_reason=lock.lock_reason,
                locked_at=str(lock.locked_at),
                expires_at=str(lock.expires_at) if lock.expires_at else None,
            )
        else:
            return ReportLockStatus(is_locked=False)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get lock status: {str(e)}",
        )


@router.get("/{report_id}/locks", response_model=List[LockReportResponse])
async def get_report_locks(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get history of locks for a report"""
    try:
        # Check if report exists
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        service = ReportLockService(db)
        locks = service.get_report_locks(report_id)
        return locks
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get report locks: {str(e)}",
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
        result = service.add_comment(
            report_id=report_id,
            user=current_user,
            comment_data=comment_data,
        )
        return result
    except HTTPException:
        # Re-raise HTTPException as-is to preserve status code
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add comment: {str(e)}",
        )


@router.get("/{report_id}/comments", response_model=ReportCommentList)
async def get_report_comments(
    report_id: str,
    parent_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get comments for a report"""
    try:
        # Check if report exists
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        service = ReportLockService(db)
        comments = service.get_comments(report_id, parent_id)
        return ReportCommentList(comments=comments)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get comments: {str(e)}",
        )


@router.put("/{report_id}/comments/{comment_id}/resolve")
async def resolve_report_comment(
    report_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Resolve a comment"""
    try:
        service = ReportLockService(db)
        result = service.resolve_comment(
            comment_id=comment_id,
            user=current_user,
        )
        return result
    except HTTPException:
        # Re-raise HTTPException as-is to preserve status code
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve comment: {str(e)}",
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
        change_type = revision_data.get("change_type", "update")
        changes_summary = revision_data.get("changes_summary", "")

        service = ReportLockService(db)
        result = service.create_revision(
            report_id=report_id,
            user=current_user,
            change_type=change_type,
            changes_summary=changes_summary,
        )
        return result
    except HTTPException:
        # Re-raise HTTPException as-is to preserve status code
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create revision: {str(e)}",
        )


@router.get("/{report_id}/revisions", response_model=ReportRevisionList)
async def get_report_revisions(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get revision history for a report"""
    try:
        # Check if report exists
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
            )

        service = ReportLockService(db)
        revisions = service.get_revisions(report_id)
        return ReportRevisionList(revisions=revisions)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get revisions: {str(e)}",
        )
