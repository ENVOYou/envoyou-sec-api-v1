"""
Tests for Report Locking and Collaboration Features
Tests for report locking, comments, and revision tracking
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.main import app
from app.models.report import Report, ReportLock, Comment, Revision
from app.models.user import User, UserRole
from app.schemas.report import LockReportRequest, CommentCreate


@pytest.mark.parametrize("user_role", [UserRole.AUDITOR, UserRole.ADMIN, UserRole.CFO])
def test_lock_report_success(
    client: TestClient, db_session: Session, test_user: User, user_role: UserRole
):
    """Test successful report locking by authorized users"""
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

    # Update user role for this test
    test_user.role = user_role
    db_session.commit()

    print(f"DEBUG: test_user.id = {test_user.id}")
    print(f"DEBUG: test_user.role = {test_user.role}")

    # Lock the report
    lock_data = LockReportRequest(lock_reason="audit", expires_in_hours=24)
    token = generate_test_token(test_user)
    print(f"DEBUG: JWT token generated for user {test_user.id}")

    response = client.post(
        f"/v1/reports/{report.id}/lock",
        json=lock_data.dict(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    lock_response = response.json()
    assert lock_response["is_active"] is True
    assert lock_response["lock_reason"] == "audit"

    # Verify in database
    db_report = db_session.query(Report).filter(Report.id == report.id).first()
    assert db_report.is_locked is True
    assert db_report.locked_by == test_user.id


def test_lock_report_unauthorized(client: TestClient, db_session: Session, test_user: User):
    """Test report locking by unauthorized user"""
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

    # Lock the report as unauthorized user (finance team)
    lock_data = LockReportRequest(lock_reason="audit", expires_in_hours=24)
    response = client.post(
        f"/v1/reports/{report.id}/lock",
        json=lock_data.dict(),
        headers={"Authorization": f"Bearer {generate_test_token(test_user)}"},
    )

    assert response.status_code == 403
    assert "Only auditors, admins, or CFOs can lock reports" in response.json()["detail"]


def test_unlock_report_success(client: TestClient, db_session: Session, test_user: User):
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

    # Verify in database
    db_report = db_session.query(Report).filter(Report.id == report.id).first()
    assert db_report.is_locked is False
    assert db_report.locked_by is None

    db_lock = db_session.query(ReportLock).filter(ReportLock.id == lock.id).first()
    assert db_lock.is_active is False


def test_unlock_report_unauthorized(client: TestClient, db_session: Session, test_user: User):
    """Test report unlocking by unauthorized user"""
    # Create test report and lock by different user
    report = Report(
        title="Test Report",
        report_type="sec_10k",
        status="draft",
        version="1.0",
        created_by=uuid4(),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    lock = ReportLock(
        report_id=report.id,
        locked_by=uuid4(),  # Different user
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
    assert "Only the locking user or admin can unlock reports" in response.json()["detail"]


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
    db_comment = db_session.query(Comment).filter(Comment.id == comment_response["id"]).first()
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

    # Add test comments
    comment1 = Comment(
        report_id=report.id,
        user_id=test_user.id,
        content="First comment",
        comment_type="general",
    )
    comment2 = Comment(
        report_id=report.id,
        user_id=test_user.id,
        content="Second comment",
        comment_type="question",
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
    assert comments_response["comments"][0]["content"] in ["First comment", "Second comment"]


def test_resolve_comment_success(client: TestClient, db_session: Session, test_user: User):
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

    # Verify in database
    db_comment = db_session.query(Comment).filter(Comment.id == comment.id).first()
    assert db_comment.is_resolved is True
    assert db_comment.resolved_by == test_user.id


def test_create_revision_success(client: TestClient, db_session: Session, test_user: User):
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
    assert revision_response["revision_number"] == 1

    # Verify in database
    db_revision = db_session.query(Revision).filter(Revision.id == revision_response["id"]).first()
    assert db_revision.change_type == "update"
    assert db_revision.report_id == report.id


def test_get_revisions_success(client: TestClient, db_session: Session, test_user: User):
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

    # Add test revisions
    revision1 = Revision(
        report_id=report.id,
        version="1.0",
        revision_number=1,
        changed_by=test_user.id,
        change_type="create",
        changes_summary="Initial creation",
    )
    revision2 = Revision(
        report_id=report.id,
        version="1.1",
        revision_number=2,
        changed_by=test_user.id,
        change_type="update",
        changes_summary="Updated data",
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
    assert len(revisions_response["revisions"]) == 2
    assert revisions_response["revisions"][0]["revision_number"] == 2


def generate_test_token(user: User) -> str:
    """Generate a test JWT token for the user"""
    from app.core.security import JWTManager
    jwt_manager = JWTManager()
    return jwt_manager.create_access_token(data={"sub": str(user.id)})