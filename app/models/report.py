"""
Report Models for Audit Lock and Collaboration
Models for report locking, comments, and revision tracking
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.user import User
from app.models.workflow import Workflow


class Report(Base):
    """SEC-compliant report model"""

    __tablename__ = "reports"

    id = Column(String(36), primary_key=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        super().__init__(**kwargs)

    title = Column(String(255), nullable=False)
    report_type = Column(
        String(50), nullable=False
    )  # "sec_10k", "audit_report", "compliance_summary"
    status = Column(
        String(50), nullable=False, default="draft"
    )  # "draft", "pending_approval", "approved", "locked"
    version = Column(String(20), nullable=False, default="1.0")
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    completed_at = Column(DateTime)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="reports")
    created_by_user = relationship("User", foreign_keys=[created_by])
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    locks = relationship(
        "ReportLock", back_populates="report", cascade="all, delete-orphan"
    )
    comments = relationship(
        "Comment", back_populates="report", cascade="all, delete-orphan"
    )
    revisions = relationship(
        "Revision", back_populates="report", cascade="all, delete-orphan"
    )

    # Report content (JSON for flexibility)
    content = Column(Text)  # JSON string containing report data
    report_metadata = Column(Text, default="{}")  # JSON metadata

    # File storage
    pdf_path = Column(String(500))
    excel_path = Column(String(500))

    @property
    def is_locked(self):
        """Checks if there is an active lock on the report."""
        return any(lock.is_active for lock in self.locks)

    @property
    def active_lock(self):
        """Returns the active lock object, if any."""
        for lock in self.locks:
            if lock.is_active:
                return lock
        return None

    @property
    def locked_by(self):
        """Returns the user ID of who locked the report, if locked."""
        active_lock = self.active_lock
        return active_lock.locked_by if active_lock else None


class ReportLock(Base):
    """Report locking mechanism for audit periods"""

    __tablename__ = "report_locks"

    id = Column(String(36), primary_key=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        super().__init__(**kwargs)

    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False, index=True)
    locked_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    locked_at = Column(DateTime)
    lock_reason = Column(
        String(255), nullable=False
    )  # "audit", "review", "compliance_check"
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    unlocked_at = Column(DateTime)
    unlocked_by = Column(String(36), ForeignKey("users.id"))

    # Relationships
    report = relationship("Report", back_populates="locks")
    locked_by_user = relationship("User", foreign_keys=[locked_by])
    unlocked_by_user = relationship("User", foreign_keys=[unlocked_by])


class Comment(Base):
    """Collaboration comments on reports"""

    __tablename__ = "comments"

    id = Column(String(36), primary_key=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        super().__init__(**kwargs)

    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    parent_id = Column(
        String(36), ForeignKey("comments.id"), nullable=True
    )  # For threaded comments
    content = Column(Text, nullable=False)
    comment_type = Column(
        String(50), default="general"
    )  # "general", "question", "suggestion", "action_item"
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(String(36), ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # Relationships
    report = relationship("Report", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
    parent = relationship("Comment", remote_side=[id])
    resolver = relationship("User", foreign_keys=[resolved_by])


class Revision(Base):
    """Revision tracking for report changes"""

    __tablename__ = "revisions"

    id = Column(String(36), primary_key=True)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        super().__init__(**kwargs)

    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    revision_number = Column(Integer, nullable=False)
    changed_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    change_type = Column(
        String(50), nullable=False
    )  # "create", "update", "approve", "reject"
    changes_summary = Column(Text)  # JSON summary of changes
    previous_version = Column(String(20))
    created_at = Column(DateTime)

    # Relationships
    report = relationship("Report", back_populates="revisions")
    changed_by_user = relationship("User")


# Event listeners for automatic revision creation
@event.listens_for(Report, "before_update")
def receive_before_update(mapper, connection, target):
    """Create revision before report update"""
    if target.status != "draft":
        return  # Only track revisions for draft reports

    # Create revision record using session
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=connection)
    session = Session()

    try:
        revision = Revision(
            report_id=target.id,
            version=target.version,
            revision_number=1,  # This would be calculated in real implementation
            changed_by=target.updated_by,
            change_type="update",
            changes_summary="Manual update to report content",
        )
        session.add(revision)
        session.commit()
    except Exception as e:
        session.rollback()
        # Log error but don't fail the main operation
        print(f"Failed to create revision: {e}")
    finally:
        session.close()


@event.listens_for(Report, "after_insert")
def receive_after_insert(mapper, connection, target):
    """Create initial revision after report creation"""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=connection)
    session = Session()

    try:
        revision = Revision(
            report_id=target.id,
            version=target.version,
            revision_number=1,
            changed_by=target.created_by,
            change_type="create",
            changes_summary="Initial report creation",
        )
        session.add(revision)
        session.commit()
    except Exception as e:
        session.rollback()
        # Log error but don't fail the main operation
        print(f"Failed to create revision: {e}")
    finally:
        session.close()
