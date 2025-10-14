"""
Tests for Report Locking and Collaboration Features
Tests for report locking, comments, and revision tracking
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.report import Comment, Report, ReportLock, Revision
from app.models.user import User, UserRole
from app.schemas.report import CommentCreate, LockReportRequest


def test_lock_report_success_auditor(
    client: TestClient, db_session: Session, auditor_user: User
):
    """Test successful report locking by auditor"""
    _test_lock_report_success(client, db_session, auditor_user)


def test_lock_report_success_admin(
    client: TestClient, db_session: Session, admin_user: User
):
    """Test successful report locking by admin"""
    _test_lock_report_success(client, db_session, admin_user)


def test_lock_report_success_cfo(
    client: TestClient, db_session: Session, cfo_user: User
):
    """Test successful report locking by CFO"""
    _test_lock_report_success(client, db_session, cfo_user)


def _test_lock_report_success(client: TestClient, db_session: Session, user: User):
    """Helper function for testing successful report locking"""
    print(
        f"DEBUG: Starting _test_lock_report_success for user {user.id} with role {user.role}"
    )

    # Check if report_locks table exists
    try:
        from sqlalchemy import text

        result = db_session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='report_locks'"
            )
        )
        if not result.fetchone():
            print("ERROR: report_locks table does not exist!")
            raise Exception("report_locks table missing")
    except Exception as e:
        print(f"ERROR: Could not check report_locks table: {e}")
        raise

    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    print(f"DEBUG: user.id = {user.id}")
    print(f"DEBUG: user.role = {user.role}")

    # Lock the report
    lock_data = LockReportRequest(lock_reason="audit", expires_in_hours=24)
    token = generate_test_token(user)
    print(f"DEBUG: JWT token generated for user {user.id}")

    response = client.post(
        f"/v1/reports/{report.id}/lock",
        json=lock_data.model_dump(),
        headers={"Authorization": f"Bearer {token}"},
    )

    print(f"DEBUG: Response status: {response.status_code}")
    print(f"DEBUG: Response content: {response.text}")

    assert response.status_code == 200
    lock_response = response.json()
    assert lock_response["is_active"] is True
    assert lock_response["lock_reason"] == "audit"

    # Verify in database
    db_report = db_session.query(Report).filter(Report.id == report.id).first()
    assert db_report.is_locked is True
    assert db_report.locked_by == user.id


def test_lock_report_unauthorized(client: TestClient, db_session: Session):
    """Test report locking by unauthorized user"""
    import uuid

    from app.core.security import SecurityUtils
    from app.models.user import UserRole, UserStatus

    # Create unauthorized user (finance team)
    unique_id = str(uuid.uuid4())[:8]
    security = SecurityUtils()

    unauthorized_user = User(
        email=f"finance{unique_id}@example.com",
        username=f"finance{unique_id}",
        full_name="Finance User",
        hashed_password=security.get_password_hash("FinancePass123!"),
        role=UserRole.FINANCE_TEAM,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    db_session.add(unauthorized_user)
    db_session.commit()
    db_session.refresh(unauthorized_user)

    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=unauthorized_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # Lock the report as unauthorized user (finance team)
    lock_data = LockReportRequest(lock_reason="audit", expires_in_hours=24)
    response = client.post(
        f"/v1/reports/{report.id}/lock",
        json=lock_data.dict(),
        headers={"Authorization": f"Bearer {generate_test_token(unauthorized_user)}"},
    )

    assert response.status_code == 403
    assert (
        "Only auditors, admins, or CFOs can lock reports" in response.json()["detail"]
    )


def test_unlock_report_success(
    client: TestClient, db_session: Session, test_user: User
):
    """Test successful report unlocking by authorized user"""
    # Create test report and lock
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # Create lock
    lock = ReportLock(
        report_id=report.id,
        locked_by=test_user.id,
        lock_reason="audit",
        is_active=True,
    )
    db_session.add(lock)
    db_session.commit()
    db_session.refresh(lock)

    # Unlock the report
    response = client.post(
        f"/v1/reports/{report.id}/unlock",
        json={},
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    unlock_response = response.json()
    assert unlock_response["success"] is True

    # Verify in database - re-query to ensure fresh data
    db_session.expire_all()  # Expire all objects in session to force refresh
    db_report = db_session.query(Report).filter(Report.id == report.id).first()
    assert db_report.is_locked is False
    assert db_report.locked_by is None

    db_lock = db_session.query(ReportLock).filter(ReportLock.id == lock.id).first()
    assert db_lock.is_active is False


def test_unlock_report_unauthorized(
    client: TestClient, db_session: Session, test_user: User
):
    """Test report unlocking by unauthorized user"""
    # Create test report and lock by different user
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=str(uuid4()),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    lock = ReportLock(
        report_id=report.id,
        locked_by=str(uuid4()),  # Different user
        lock_reason="audit",
        is_active=True,
    )
    db_session.add(lock)
    db_session.commit()
    db_session.refresh(lock)

    # Try to unlock as unauthorized user
    response = client.post(
        f"/v1/reports/{report.id}/unlock",
        json={},
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 403
    assert (
        "Only the locking user or admin can unlock reports" in response.json()["detail"]
    )


def test_add_comment_success(client: TestClient, db_session: Session, test_user: User):
    """Test adding a comment to a report"""
    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # Add comment
    comment_data = CommentCreate(
        content="This is a test comment",
        comment_type="general",
        parent_id=None,
    )
    response = client.post(
        f"/v1/reports/{report.id}/comments",
        json=comment_data.dict(),
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    comment_response = response.json()
    assert comment_response["content"] == "This is a test comment"
    assert comment_response["is_resolved"] is False

    # Verify in database
    db_comment = (
        db_session.query(Comment).filter(Comment.id == comment_response["id"]).first()
    )
    assert db_comment.content == "This is a test comment"
    assert db_comment.report_id == report.id


def test_get_comments_success(client: TestClient, db_session: Session, test_user: User):
    """Test getting comments for a report"""
    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    from datetime import datetime

    # Add test comments
    now = datetime.utcnow()
    comment1 = Comment(
        report_id=report.id,
        user_id=test_user.id,
        content="First comment",
        comment_type="general",
        created_at=now,
        updated_at=now,
    )
    comment2 = Comment(
        report_id=report.id,
        user_id=test_user.id,
        content="Second comment",
        comment_type="question",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([comment1, comment2])
    db_session.commit()

    # Get comments
    response = client.get(
        f"/v1/reports/{report.id}/comments",
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    comments_response = response.json()
    assert len(comments_response["comments"]) == 2
    assert comments_response["comments"][0]["content"] in [
        "First comment",
        "Second comment",
    ]


def test_resolve_comment_success(
    client: TestClient, db_session: Session, test_user: User
):
    """Test resolving a comment"""
    # Create test report and comment
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    comment = Comment(
        report_id=report.id,
        user_id=test_user.id,
        content="Unresolved comment",
        comment_type="question",
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)

    # Resolve comment
    response = client.put(
        f"/v1/reports/{report.id}/comments/{comment.id}/resolve",
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    resolved_comment = response.json()
    assert resolved_comment["is_resolved"] is True
    assert resolved_comment["resolved_by"] == str(test_user.id)

    # Verify in database - expire session to force refresh
    db_session.expire_all()
    db_comment = db_session.query(Comment).filter(Comment.id == comment.id).first()
    assert db_comment.is_resolved is True
    assert db_comment.resolved_by == test_user.id


def test_create_revision_success(
    client: TestClient, db_session: Session, test_user: User
):
    """Test creating a revision for a report"""
    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # Create revision
    revision_data = {
        "change_type": "update",
        "changes_summary": "Updated emissions data",
    }
    response = client.post(
        f"/v1/reports/{report.id}/revisions",
        json=revision_data,
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    revision_response = response.json()
    assert revision_response["change_type"] == "update"
    # Note: revision_number starts from 2 because event listener creates revision 1 on report creation
    assert revision_response["revision_number"] == 2

    # Verify in database
    db_revision = (
        db_session.query(Revision)
        .filter(Revision.id == revision_response["id"])
        .first()
    )
    assert db_revision.change_type == "update"
    assert db_revision.report_id == report.id


def test_get_revisions_success(
    client: TestClient, db_session: Session, test_user: User
):
    """Test getting revisions for a report"""
    # Create test report
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=test_user.id,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    from datetime import datetime

    # Add test revisions
    now = datetime.utcnow()
    revision1 = Revision(
        report_id=report.id,
        version="1.0",
        revision_number=1,
        changed_by=test_user.id,
        change_type="create",
        changes_summary="Initial creation",
        created_at=now,
    )
    revision2 = Revision(
        report_id=report.id,
        version="1.1",
        revision_number=2,
        changed_by=test_user.id,
        change_type="update",
        changes_summary="Updated data",
        created_at=now,
    )
    db_session.add_all([revision1, revision2])
    db_session.commit()

    # Get revisions
    response = client.get(
        f"/v1/reports/{report.id}/revisions",
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 200
    revisions_response = response.json()
    # Expect 3 revisions: 1 from event listener + 2 manual additions
    assert len(revisions_response["revisions"]) == 3
    # Sort by revision_number descending to check the latest ones
    sorted_revisions = sorted(
        revisions_response["revisions"],
        key=lambda x: x["revision_number"],
        reverse=True,
    )
    assert sorted_revisions[0]["revision_number"] == 2  # Manual revision 2
    assert (
        sorted_revisions[1]["revision_number"] == 1
    )  # Manual revision 1 or auto-created


def generate_test_token(user: User) -> str:
    """Generate a test JWT token for the user"""
    from app.core.security import JWTManager

    jwt_manager = JWTManager()
    return jwt_manager.create_access_token(data={"sub": str(user.id)})
