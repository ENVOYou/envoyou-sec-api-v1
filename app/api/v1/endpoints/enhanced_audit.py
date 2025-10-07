"""
Enhanced Audit Trail API Endpoints
Advanced forensic and SEC compliance audit capabilities
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.audit_logger import AuditLogger
from app.core.auth import require_roles
from app.models.user import User
from app.services.enhanced_audit_service import EnhancedAuditService

router = APIRouter()


@router.get("/calculations/{calculation_id}/lineage")
async def get_data_lineage(
    calculation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive data lineage map for a calculation

    Provides complete traceability from input data to final results
    including EPA factor sources, processing steps, and quality metrics.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        lineage_map = audit_service.create_data_lineage_map(calculation_id)

        # Log the lineage access
        await audit_logger.log_event(
            event_type="DATA_LINEAGE_ACCESS",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "lineage_elements": len(lineage_map.get("processing_steps", [])),
            },
        )

        return {
            "message": "Data lineage retrieved successfully",
            "lineage": lineage_map,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="DATA_LINEAGE_ACCESS_ERROR",
            user_id=current_user.id,
            details={"calculation_id": calculation_id, "error": str(e)},
        )
        raise


@router.get("/calculations/{calculation_id}/sec-compliance")
async def get_sec_compliance_report(
    calculation_id: str,
    include_technical_details: bool = Query(
        True, description="Include technical details in report"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["cfo", "general_counsel", "admin"])),
):
    """
    Generate SEC Climate Disclosure Rule compliance report

    Comprehensive compliance verification including:
    - SEC requirements verification
    - GHG Protocol compliance
    - Data quality standards
    - Audit trail completeness
    - Emission factor standards

    Restricted to CFO, General Counsel, and Admin roles.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        compliance_report = audit_service.generate_sec_compliance_report(
            calculation_id=calculation_id,
            include_technical_details=include_technical_details,
        )

        # Log the compliance report access
        await audit_logger.log_event(
            event_type="SEC_COMPLIANCE_REPORT_GENERATED",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "compliance_score": compliance_report["executive_summary"][
                    "compliance_score"
                ],
                "compliance_status": compliance_report["executive_summary"][
                    "compliance_status"
                ],
                "include_technical_details": include_technical_details,
            },
        )

        return compliance_report

    except Exception as e:
        await audit_logger.log_event(
            event_type="SEC_COMPLIANCE_REPORT_ERROR",
            user_id=current_user.id,
            details={"calculation_id": calculation_id, "error": str(e)},
        )
        raise


@router.post("/calculations/{calculation_id}/enhanced-audit")
async def create_enhanced_audit_event(
    calculation_id: str,
    event_type: str,
    event_description: str,
    calculation_data: Optional[Dict[str, Any]] = None,
    emission_factors_snapshot: Optional[Dict[str, Any]] = None,
    data_lineage: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "auditor"])),
):
    """
    Create enhanced audit event with forensic-grade data capture

    Creates comprehensive audit trail entries with:
    - Immutable hash generation
    - Complete data snapshots
    - System metadata
    - Compliance markers

    Restricted to Admin and Auditor roles.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        audit_entry = audit_service.log_enhanced_calculation_event(
            calculation_id=calculation_id,
            event_type=event_type,
            event_description=event_description,
            user_id=str(current_user.id),
            user_role=current_user.role.value,
            calculation_data=calculation_data,
            emission_factors_snapshot=emission_factors_snapshot,
            data_lineage=data_lineage,
            reason=reason,
        )

        # Log the enhanced audit creation
        await audit_logger.log_event(
            event_type="ENHANCED_AUDIT_EVENT_CREATED",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "audit_event_type": event_type,
                "audit_entry_id": str(audit_entry.id),
            },
        )

        return {
            "message": "Enhanced audit event created successfully",
            "audit_entry_id": str(audit_entry.id),
            "event_type": event_type,
            "timestamp": audit_entry.event_timestamp,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="ENHANCED_AUDIT_EVENT_ERROR",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "event_type": event_type,
                "error": str(e),
            },
        )
        raise


@router.get("/calculations/{calculation_id}/integrity-check")
async def perform_integrity_check(
    calculation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "auditor", "cfo"])),
):
    """
    Perform comprehensive calculation integrity verification

    Verifies:
    - Audit trail completeness
    - Data consistency
    - Calculation reproducibility
    - Emission factor traceability
    - Timeline integrity
    - User authorization validity

    Returns integrity score and detailed findings.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        integrity_check = audit_service.verify_calculation_integrity(calculation_id)

        # Log the integrity check
        await audit_logger.log_event(
            event_type="CALCULATION_INTEGRITY_CHECK",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "integrity_score": integrity_check["integrity_score"],
                "is_compliant": integrity_check["is_compliant"],
                "issues_count": len(integrity_check["issues_found"]),
            },
        )

        return {
            "message": "Integrity check completed successfully",
            "integrity_verification": integrity_check,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="CALCULATION_INTEGRITY_CHECK_ERROR",
            user_id=current_user.id,
            details={"calculation_id": calculation_id, "error": str(e)},
        )
        raise


@router.get("/companies/{company_id}/audit-summary")
async def get_company_audit_summary(
    company_id: str,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["cfo", "general_counsel", "admin"])),
):
    """
    Get comprehensive audit summary for all company calculations

    Provides:
    - Total calculations and audit events
    - Event type distribution
    - User activity summary
    - Data quality trends
    - Compliance status assessment
    - Audit coverage metrics

    Restricted to CFO, General Counsel, and Admin roles.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        audit_summary = audit_service.get_company_audit_summary(
            company_id=company_id,
            reporting_year=reporting_year,
            start_date=start_date,
            end_date=end_date,
        )

        # Log the audit summary access
        await audit_logger.log_event(
            event_type="COMPANY_AUDIT_SUMMARY_ACCESS",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "total_calculations": audit_summary["total_calculations"],
                "compliance_status": audit_summary["compliance_status"],
            },
        )

        return {
            "message": "Company audit summary retrieved successfully",
            "audit_summary": audit_summary,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="COMPANY_AUDIT_SUMMARY_ERROR",
            user_id=current_user.id,
            details={"company_id": company_id, "error": str(e)},
        )
        raise


@router.post("/export/audit-trail")
async def export_audit_trail(
    calculation_ids: List[str],
    export_format: str = Query("json", description="Export format (json, csv)"),
    include_metadata: bool = Query(True, description="Include metadata in export"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "auditor"])),
):
    """
    Export audit trail data for external auditors

    Generates comprehensive audit trail export including:
    - Complete audit events
    - Integrity verification
    - Data lineage information
    - Metadata and system information

    Supports JSON and CSV formats.
    Restricted to Admin and Auditor roles.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        export_data = audit_service.generate_audit_trail_export(
            calculation_ids=calculation_ids,
            export_format=export_format,
            include_metadata=include_metadata,
        )

        # Log the audit trail export
        await audit_logger.log_event(
            event_type="AUDIT_TRAIL_EXPORT",
            user_id=current_user.id,
            details={
                "calculation_count": len(calculation_ids),
                "export_format": export_format,
                "include_metadata": include_metadata,
                "export_id": export_data["export_metadata"]["export_id"],
            },
        )

        return {
            "message": "Audit trail export generated successfully",
            "export_data": export_data,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="AUDIT_TRAIL_EXPORT_ERROR",
            user_id=current_user.id,
            details={"calculation_count": len(calculation_ids), "error": str(e)},
        )
        raise


@router.get("/calculations/{calculation_id}/forensic-report")
async def get_forensic_report(
    calculation_id: str,
    include_raw_data: bool = Query(True, description="Include raw calculation data"),
    include_user_details: bool = Query(True, description="Include user information"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(["admin", "auditor", "cfo", "general_counsel"])
    ),
):
    """
    Generate comprehensive forensic report for SEC audit purposes

    Provides complete forensic analysis including:
    - Calculation summary and results
    - Complete audit trail
    - Activity data and emission factors
    - Integrity verification
    - User information and authorization
    - Compliance attestation

    Restricted to Admin, Auditor, CFO, and General Counsel roles.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        forensic_report = audit_service.generate_forensic_report(
            calculation_id=calculation_id,
            include_raw_data=include_raw_data,
            include_user_details=include_user_details,
        )

        # Log the forensic report access
        await audit_logger.log_event(
            event_type="FORENSIC_REPORT_GENERATED",
            user_id=current_user.id,
            details={
                "calculation_id": calculation_id,
                "report_id": forensic_report["report_metadata"]["report_id"],
                "include_raw_data": include_raw_data,
                "include_user_details": include_user_details,
                "integrity_score": forensic_report["integrity_verification"][
                    "integrity_score"
                ],
            },
        )

        return forensic_report

    except Exception as e:
        await audit_logger.log_event(
            event_type="FORENSIC_REPORT_ERROR",
            user_id=current_user.id,
            details={"calculation_id": calculation_id, "error": str(e)},
        )
        raise


@router.get("/companies/{company_id}/anomaly-insights")
async def get_audit_anomaly_insights(
    company_id: str,
    reporting_year: Optional[int] = Query(None, description="Filter by reporting year"),
    include_historical: bool = Query(
        True, description="Include historical anomaly trends"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(["admin", "auditor", "cfo", "general_counsel"])
    ),
):
    """
    Get anomaly detection insights for audit purposes

    Provides comprehensive anomaly analysis including:
    - Current year anomaly detection results
    - Historical anomaly trends
    - Risk assessment and recommendations
    - Integration with audit findings

    Restricted to Admin, Auditor, CFO, and General Counsel roles.
    """
    from app.services.anomaly_detection_service import AnomalyDetectionService

    audit_service = EnhancedAuditService(db)
    anomaly_service = AnomalyDetectionService(db)
    audit_logger = AuditLogger(db)

    try:
        # Get current year or specified year anomalies
        target_year = reporting_year or datetime.utcnow().year

        anomaly_report = anomaly_service.detect_anomalies(
            company_id=company_id, reporting_year=target_year, user_id=current_user.id
        )

        # Get historical trends if requested
        historical_data = {}
        if include_historical:
            for year in range(target_year - 2, target_year):
                try:
                    historical_report = anomaly_service.detect_anomalies(
                        company_id=company_id,
                        reporting_year=year,
                        user_id=current_user.id,
                    )
                    historical_data[str(year)] = {
                        "total_anomalies": historical_report.total_anomalies,
                        "risk_score": historical_report.overall_risk_score,
                        "severity_breakdown": historical_report.anomalies_by_severity,
                    }
                except Exception as e:
                    historical_data[str(year)] = {
                        "error": f"Data not available: {str(e)}"
                    }

        # Create audit-focused summary
        audit_summary = {
            "company_id": company_id,
            "reporting_year": target_year,
            "audit_timestamp": datetime.utcnow().isoformat(),
            "anomaly_overview": {
                "total_anomalies": anomaly_report.total_anomalies,
                "overall_risk_score": anomaly_report.overall_risk_score,
                "severity_breakdown": anomaly_report.anomalies_by_severity,
                "detection_types": anomaly_report.anomalies_by_type,
            },
            "critical_findings": [
                {
                    "anomaly_id": anomaly.anomaly_id,
                    "type": anomaly.anomaly_type,
                    "description": anomaly.description,
                    "severity": anomaly.severity,
                    "confidence": anomaly.confidence_score,
                    "recommendations": anomaly.recommendations,
                    "affected_data": anomaly.affected_data_points,
                }
                for anomaly in anomaly_report.detected_anomalies
                if anomaly.severity in ["critical", "high"]
            ],
            "audit_recommendations": anomaly_report.summary_insights,
            "historical_trends": historical_data if include_historical else None,
            "compliance_impact": {
                "requires_investigation": anomaly_report.total_anomalies > 0,
                "high_risk_areas": [
                    anomaly.anomaly_type
                    for anomaly in anomaly_report.detected_anomalies
                    if anomaly.severity == "critical"
                ],
                "recommended_actions": (
                    [
                        "Review critical anomalies before SEC filing",
                        "Validate data sources for high-risk areas",
                        "Document investigation results in audit trail",
                    ]
                    if anomaly_report.total_anomalies > 0
                    else ["No immediate action required"]
                ),
            },
        }

        # Log the anomaly insights access
        await audit_logger.log_event(
            event_type="ANOMALY_INSIGHTS_ACCESSED",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": target_year,
                "total_anomalies": anomaly_report.total_anomalies,
                "risk_score": anomaly_report.overall_risk_score,
                "include_historical": include_historical,
            },
        )

        return {
            "message": "Anomaly insights retrieved successfully",
            "data": audit_summary,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="ANOMALY_INSIGHTS_ERROR",
            user_id=current_user.id,
            details={
                "company_id": company_id,
                "reporting_year": reporting_year,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve anomaly insights: {str(e)}",
        )


@router.post("/audit-sessions/{session_id}/anomaly-review")
async def create_anomaly_review_task(
    session_id: str,
    anomaly_ids: List[str],
    reviewer_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "auditor", "cfo"])),
):
    """
    Create anomaly review task within an audit session

    Allows auditors to formally review and document anomaly findings
    as part of the audit process.
    """
    audit_service = EnhancedAuditService(db)
    audit_logger = AuditLogger(db)

    try:
        # Create audit task for anomaly review
        review_task = {
            "task_id": f"anomaly_review_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "session_id": session_id,
            "task_type": "anomaly_review",
            "assigned_to": current_user.id,
            "anomaly_ids": anomaly_ids,
            "reviewer_notes": reviewer_notes,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": {
                "anomaly_count": len(anomaly_ids),
                "review_priority": "high" if len(anomaly_ids) > 5 else "medium",
            },
        }

        # Log the review task creation
        await audit_logger.log_event(
            event_type="ANOMALY_REVIEW_TASK_CREATED",
            user_id=current_user.id,
            details={
                "session_id": session_id,
                "task_id": review_task["task_id"],
                "anomaly_count": len(anomaly_ids),
                "reviewer_notes_provided": bool(reviewer_notes),
            },
        )

        return {
            "message": "Anomaly review task created successfully",
            "data": review_task,
        }

    except Exception as e:
        await audit_logger.log_event(
            event_type="ANOMALY_REVIEW_TASK_ERROR",
            user_id=current_user.id,
            details={"session_id": session_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create anomaly review task: {str(e)}",
        )
