"""
Report Locking and Collaboration Service
Handles report locking, comments, and revision tracking for audit and collaboration
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models.report import Comment, Report, ReportLock, Revision
from app.models.user import User, UserRole
from app.schemas.report import (
    CommentCreate,
    CommentResponse,
    LockReportRequest,
    LockReportResponse,
    RevisionResponse,
    UnlockReportRequest,
)

logger = logging.getLogger(__name__)


class ReportLockService:
    """Service for managing report locking and collaboration features"""

    def __init__(self, db: Session):
        self.db = db

    def lock_report(
        self,
        report_id: str,
        user_id: str,
        lock_reason: str,
        expires_in_hours: int = 24,
    ) -> LockReportResponse:
        """Lock a report for audit or review purposes"""
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")

        # Check if already locked
        if report.is_locked:
            raise ValueError(f"Report {report_id} is already locked")

        # Check user permissions
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        allowed_roles = [UserRole.AUDITOR, UserRole.ADMIN, UserRole.CFO]
        if user.role not in allowed_roles:
            raise PermissionError("Only auditors, admins, or CFOs can lock reports")

        # Create lock record
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        lock = ReportLock(
            report_id=report_id,
            locked_by=user_id,
            lock_reason=lock_reason,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(lock)

        # Note: Report locking is handled through the ReportLock relationship
        # The report.is_locked property will reflect this automatically

        self.db.commit()
        self.db.refresh(lock)

        logger.info(
            f"Report {report_id} locked by user {user_id} for reason: {lock_reason}"
        )

        return LockReportResponse(
            id=str(lock.id),
            report_id=report_id,
            locked_by=user_id,
            lock_reason=lock_reason,
            locked_at=lock.locked_at,
            expires_at=expires_at,
            is_active=True,
        )

    def unlock_report(self, report_id: str, user_id: str) -> dict:
        """Unlock a report"""
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")

        if not report.is_locked:
            raise ValueError(f"Report {report_id} is not locked")

        # Check permissions - only locker or admin can unlock
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if str(report.locked_by) != user_id and user.role != UserRole.ADMIN:
            raise PermissionError("Only the locking user or admin can unlock reports")

        # Find active lock
        active_lock = (
            self.db.query(ReportLock)
            .filter(
                and_(
                    ReportLock.report_id == report_id,
                    ReportLock.is_active == True,
                )
            )
            .first()
        )

        if active_lock:
            active_lock.is_active = False
            active_lock.unlocked_at = datetime.utcnow()
            active_lock.unlocked_by = user_id

        # Note: Report unlocking is handled through the ReportLock relationship
        # The report.is_locked property will reflect this automatically

        self.db.commit()

        logger.info(f"Report {report_id} unlocked by user {user_id}")

        return {"success": True, "message": "Report unlocked successfully"}

    def get_lock_status(self, report_id: str) -> Optional[ReportLock]:
        """Get current lock status for a report"""
        return (
            self.db.query(ReportLock)
            .filter(
                and_(
                    ReportLock.report_id == report_id,
                    ReportLock.is_active == True,
                )
            )
            .first()
        )

    def get_report_locks(self, report_id: str) -> List[LockReportResponse]:
        """Get history of locks for a report"""
        locks = (
            self.db.query(ReportLock)
            .filter(ReportLock.report_id == report_id)
            .order_by(desc(ReportLock.locked_at))
            .all()
        )

        return [
            LockReportResponse(
                id=str(lock.id),
                report_id=lock.report_id,
                locked_by=str(lock.locked_by),
                lock_reason=lock.lock_reason,
                locked_at=lock.locked_at,
                expires_at=lock.expires_at,
                is_active=lock.is_active,
            )
            for lock in locks
        ]

    def add_comment(
        self,
        report_id: str,
        user_id: str,
        comment_data: CommentCreate,
    ) -> CommentResponse:
        """Add a comment to a report"""
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")

        # Create comment
        comment = Comment(
            report_id=report_id,
            user_id=user_id,
            content=comment_data.content,
            comment_type=comment_data.comment_type,
            parent_id=comment_data.parent_id,
            is_resolved=False,
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        logger.info(f"Comment added to report {report_id} by user {user_id}")

        return CommentResponse.from_orm(comment)

    def get_comments(
        self,
        report_id: str,
        parent_id: Optional[str] = None,
    ) -> List[CommentResponse]:
        """Get comments for a report"""
        query = self.db.query(Comment).filter(Comment.report_id == report_id)

        if parent_id:
            query = query.filter(Comment.parent_id == parent_id)
        else:
            query = query.filter(Comment.parent_id.is_(None))  # Top-level comments only

        comments = query.order_by(desc(Comment.created_at)).all()

        return [CommentResponse.from_orm(comment) for comment in comments]

    def resolve_comment(self, comment_id: str, user_id: str) -> CommentResponse:
        """Resolve a comment"""
        comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        # Check permissions - comment author or admin can resolve
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if str(comment.user_id) != user_id and user.role != UserRole.ADMIN:
            raise PermissionError("Only comment author or admin can resolve comments")

        comment.is_resolved = True
        comment.resolved_by = user_id
        comment.resolved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(comment)

        logger.info(f"Comment {comment_id} resolved by user {user_id}")

        return CommentResponse.from_orm(comment)

    def create_revision(
        self,
        report_id: str,
        user_id: str,
        change_type: str,
        changes_summary: str,
    ) -> RevisionResponse:
        """Create a new revision for a report"""
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")

        # Get next revision number
        last_revision = (
            self.db.query(Revision)
            .filter(Revision.report_id == report_id)
            .order_by(desc(Revision.revision_number))
            .first()
        )

        next_revision_number = (
            (last_revision.revision_number + 1) if last_revision else 1
        )

        # Create revision
        revision = Revision(
            report_id=report_id,
            version=report.version,
            revision_number=next_revision_number,
            changed_by=user_id,
            change_type=change_type,
            changes_summary=changes_summary,
            previous_version=last_revision.version if last_revision else None,
        )
        self.db.add(revision)
        self.db.commit()
        self.db.refresh(revision)

        logger.info(
            f"Revision {next_revision_number} created for report {report_id} by user {user_id}"
        )

        return RevisionResponse.from_orm(revision)

    def get_revisions(self, report_id: str) -> List[RevisionResponse]:
        """Get revision history for a report"""
        revisions = (
            self.db.query(Revision)
            .filter(Revision.report_id == report_id)
            .order_by(desc(Revision.revision_number))
            .all()
        )

        return [RevisionResponse.from_orm(revision) for revision in revisions]
