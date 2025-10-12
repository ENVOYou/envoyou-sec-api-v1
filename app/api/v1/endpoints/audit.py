"""
Audit trail endpoints
Comprehensive audit logging and forensic traceability
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_auditor_user, get_current_user, get_db
from app.models.user import User
from app.schemas.audit import (
    AuditAnomalyResponse,
    AuditEntryResponse,
    AuditSessionRequest,
    AuditSessionResponse,
    AuditSummaryResponse,
    AuditTrailResponse,
    DataLineageRequest,
    DataLineageResponse,
    ForensicReportRequest,
    ForensicReportResponse,
)
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/trail/{entity_id}", response_model=AuditTrailResponse)
async def get_audit_trail(
    entity_id: str,
    entity_type: Optional[str] = Query(None, description="Type of entity"),
    start_date: Optional[datetime] = Query(None, description="Start date for audit trail"),
    end_date: Optional[datetime] = Query(None, description="End date for audit trail"),
    action: Optional[str] = Query(None, description="Filter by specific action"),
    user_id: Optional[str] = Query(None, description="Filter by specific user"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, le=200, description="Number of entries per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive audit trail for an entity

    Provides forensic-grade audit trail with complete traceability
    of all actions performed on the specified entity.
    """
    audit_service = AuditService(db)

    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=90)  # Default 90 days

        audit_trail = await audit_service.get_audit_trail(
            entity_id=entity_id,
            entity_type=entity_type,
            start_date=start_date,
            end_date=end_date,
            action=action,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

        # Convert to response format
        entries = []
        for entry in audit_trail["entries"]:
            entries.append(AuditEntryResponse(
                id=str(entry.id),
                timestamp=entry.timestamp,
                user_id=entry.user_id,
                user_email=getattr(entry.user, 'email', None) if hasattr(entry, 'user') else None,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
                metadata=entry.metadata,
                ip_address=entry.ip_address,
                user_agent=entry.user_agent,
                session_id=entry.session_id,
            ))

        return AuditTrailResponse(
            total_entries=audit_trail["total_entries"],
            entries=entries,
            page=audit_trail["page"],
            page_size=audit_trail["page_size"],
            total_pages=audit_trail["total_pages"],
            has_next=audit_trail["has_next"],
            has_previous=audit_trail["has_previous"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit trail: {str(e)}",
        )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    start_date: Optional[datetime] = Query(None, description="Start date for summary"),
    end_date: Optional[datetime] = Query(None, description="End date for summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit summary statistics

    Provides high-level overview of audit activity, user engagement,
    and system compliance metrics.
    """
    audit_service = AuditService(db)

    try:
        # Set default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)  # Default 30 days

        summary = await audit_service.get_audit_summary(
            start_date=start_date,
            end_date=end_date,
        )

        return AuditSummaryResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audit summary: {str(e)}",
        )


@router.post("/session", response_model=AuditSessionResponse)
async def create_audit_session(
    request: AuditSessionRequest,
    current_user: User = Depends(get_auditor_user),  # Only auditors can create sessions
    db: Session = Depends(get_db),
):
    """
    Create a new audit session for external auditors

    Establishes a secure, time-bound session for external audit access
    with comprehensive logging and access controls.
    """
    audit_service = AuditService(db)

    try:
        session_data = await audit_service.create_audit_session(
            session_name=request.session_name,
            auditor_id=request.auditor_id,
            scope=request.scope,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        return AuditSessionResponse(**session_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create audit session: {str(e)}",
        )


@router.get("/session/{session_id}", response_model=AuditSessionResponse)
async def get_audit_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit session details

    Retrieves information about a specific audit session including
    access history and current status.
    """
    audit_service = AuditService(db)

    try:
        session_data = await audit_service.get_audit_session(session_id)

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit session not found",
            )

        return AuditSessionResponse(**session_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit session: {str(e)}",
        )


@router.post("/report/{session_id}", response_model=ForensicReportResponse)
async def generate_forensic_report(
    session_id: str,
    request: ForensicReportRequest,
    current_user: User = Depends(get_auditor_user),
    db: Session = Depends(get_db),
):
    """
    Generate forensic audit report

    Creates comprehensive, SEC-compliant audit reports with
    complete data lineage and forensic traceability.
    """
    audit_service = AuditService(db)

    try:
        # Validate session exists and is accessible
        session_data = await audit_service.get_audit_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit session not found",
            )

        if session_data["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audit session is not active",
            )

        report_data = await audit_service.generate_forensic_report(
            session_id=session_id,
            report_type=request.report_type,
            include_attachments=request.include_attachments,
            format=request.format,
            generated_by=str(current_user.id),
        )

        return ForensicReportResponse(**report_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate forensic report: {str(e)}",
        )


@router.get("/lineage/{entity_type}/{entity_id}", response_model=DataLineageResponse)
async def get_data_lineage(
    entity_type: str,
    entity_id: str,
    depth: int = Query(3, le=10, description="Depth of lineage tracing"),
    include_metadata: bool = Query(True, description="Include metadata in response"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get data lineage and provenance information

    Traces the complete history and transformations of data entities
    from source to final calculation, ensuring forensic traceability.
    """
    audit_service = AuditService(db)

    try:
        lineage_data = await audit_service.get_data_lineage(
            entity_type=entity_type,
            entity_id=entity_id,
            depth=depth,
            include_metadata=include_metadata,
        )

        return DataLineageResponse(**lineage_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data lineage: {str(e)}",
        )


@router.get("/anomalies", response_model=List[AuditAnomalyResponse])
async def detect_audit_anomalies(
    start_date: Optional[datetime] = Query(None, description="Start date for anomaly detection"),
    end_date: Optional[datetime] = Query(None, description="End date for anomaly detection"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Detect anomalies in audit trails

    Uses statistical analysis and business rules to identify
    unusual patterns or potential security concerns in audit data.
    """
    audit_service = AuditService(db)

    try:
        # Set default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)  # Default 7 days

        anomalies = await audit_service.detect_audit_anomalies(
            start_date=start_date,
            end_date=end_date,
            severity=severity,
        )

        # Convert to response format
        anomaly_responses = []
        for anomaly in anomalies:
            anomaly_responses.append(AuditAnomalyResponse(
                anomaly_id=anomaly["anomaly_id"],
                detected_at=anomaly["detected_at"],
                anomaly_type=anomaly["anomaly_type"],
                severity=anomaly["severity"],
                description=anomaly["description"],
                affected_entries=anomaly["affected_entries"],
                risk_assessment=anomaly["risk_assessment"],
                recommended_actions=anomaly["recommended_actions"],
            ))

        return anomaly_responses

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect audit anomalies: {str(e)}",
        )


@router.get("/changes")
async def get_recent_changes(
    limit: int = Query(100, le=500, description="Maximum number of changes"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get recent data changes across the system

    Provides a real-time feed of recent changes for monitoring
    and compliance purposes.
    """
    audit_service = AuditService(db)

    try:
        changes = await audit_service.get_recent_changes(
            limit=limit,
            resource_type=resource_type,
        )

        return {
            "total_changes": len(changes),
            "changes": changes,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent changes: {str(e)}",
        )
