"""
Report Locking Service
Handles report locking, unlocking, and collaboration features
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.report import Comment, Report, ReportLock, Revision
from app.models.user import User
from app.schemas.report import (
    CommentCreate,
    LockReportRequest,
    LockReportResponse,
    ReportLockInfo,
    RevisionCreate,
)


class ReportLockService:
    """Service for managing report locks and collaboration features"""

    def __init__(self, db: Session):
        self.db = db

    def lock_report(
        self,
        report_id: UUID,
        user: User,
        lock_reason: str,
        expires_in_hours: int = 24,
    ) -> ReportLock:
        """
        Lock a report for exclusive access

        Args:
            report_id: Report UUID
            user: User requesting the lock
            lock_reason: Reason for locking
            expires_in_hours: Lock expiration time

        Returns:
            ReportLock object

        Raises:
            HTTPException: If report not found or already locked
        """
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found",
            )

        # Check if report is already locked
        if report.is_locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report is already locked",
            )

        # Check user permissions
        if user.role.value not in ["auditor", "admin", "cfo"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only auditors, admins, or CFOs can lock reports",
            )

        # Create lock
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        lock = ReportLock(
            report_id=report_id,
            locked_by=user.id,
            lock_reason=lock_reason,
            expires_at=expires_at,
            is_active=True,
        )

        self.db.add(lock)
        self.db.commit()
        self.db.refresh(lock)

        # Note: report.is_locked is a computed property, no need to set it
        # The property will automatically return True when there are active locks

        return lock

    def unlock_report(self, report_id: UUID, user: User) -> bool:
        """
        Unlock a report

        Args:
            report_id: Report UUID
            user: User requesting unlock

        Returns:
            True if unlocked successfully

        Raises:
            HTTPException: If report not found or not locked by user
        """
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found",
            )

        # Check if report is locked
        if not report.is_locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report is not locked",
            )

        # Check if user can unlock (locker or admin)
        if report.locked_by != user.id and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the locking user or admin can unlock reports",
            )

        # Find active lock
        lock = (
            self.db.query(ReportLock)
            .filter(
                ReportLock.report_id == report_id,
                ReportLock.is_active == True,
            )
            .first()
        )

        if lock:
            # Update lock
            lock.is_active = False
            lock.unlocked_at = datetime.utcnow()
            lock.unlocked_by = user.id
            self.db.commit()

        # Note: report.is_locked is a computed property, no need to set it
        # The property will automatically return False when there are no active locks

        return True

    def get_report_lock_info(self, report_id: UUID) -> Optional[ReportLockInfo]:
        """
        Get lock information for a report

        Args:
            report_id: Report UUID

        Returns:
            Lock information or None if not locked
        """
        lock = (
            self.db.query(ReportLock)
            .filter(
                ReportLock.report_id == report_id,
                ReportLock.is_active == True,
            )
            .first()
        )

        if not lock:
            return None

        return ReportLockInfo(
            is_locked=True,
            locked_by=str(lock.locked_by),
            locked_at=lock.locked_at,
            lock_reason=lock.lock_reason,
            expires_at=lock.expires_at,
        )

    def add_comment(
        self, report_id: UUID, user: User, comment_data: CommentCreate
    ) -> Comment:
        """
        Add a comment to a report

        Args:
            report_id: Report UUID
            user: Comment author
            comment_data: Comment data

        Returns:
            Created comment

        Raises:
            HTTPException: If report not found
        """
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found",
            )

        # Create comment
        comment = Comment(
            report_id=report_id,
            user_id=user.id,
            content=comment_data.content,
            comment_type=comment_data.comment_type,
            parent_id=comment_data.parent_id,
        )

        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        return comment

    def get_comments(self, report_id: UUID) -> List[Comment]:
        """
        Get all comments for a report

        Args:
            report_id: Report UUID

        Returns:
            List of comments
        """
        return (
            self.db.query(Comment)
            .filter(Comment.report_id == report_id)
            .order_by(Comment.created_at.desc())
            .all()
        )

    def resolve_comment(self, comment_id: UUID, user: User) -> Comment:
        """
        Resolve a comment

        Args:
            comment_id: Comment UUID
            user: User resolving the comment

        Returns:
            Updated comment

        Raises:
            HTTPException: If comment not found
        """
        comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comment {comment_id} not found",
            )

        comment.is_resolved = True
        comment.resolved_by = user.id
        comment.resolved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(comment)

        return comment

    def create_revision(
        self, report_id: UUID, user: User, revision_data: RevisionCreate
    ) -> Revision:
        """
        Create a revision for a report

        Args:
            report_id: Report UUID
            user: User creating revision
            revision_data: Revision data

        Returns:
            Created revision

        Raises:
            HTTPException: If report not found
        """
        # Check if report exists
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found",
            )

        # Get next revision number
        last_revision = (
            self.db.query(Revision)
            .filter(Revision.report_id == report_id)
            .order_by(Revision.revision_number.desc())
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
            changed_by=user.id,
            change_type=revision_data.change_type,
            changes_summary=revision_data.changes_summary,
            previous_version=revision_data.previous_version,
        )

        self.db.add(revision)
        self.db.commit()
        self.db.refresh(revision)

        return revision

    def get_revisions(self, report_id: UUID) -> List[Revision]:
        """
        Get all revisions for a report

        Args:
            report_id: Report UUID

        Returns:
            List of revisions
        """
        return (
            self.db.query(Revision)
            .filter(Revision.report_id == report_id)
            .order_by(Revision.revision_number.desc())
            .all()
        )
