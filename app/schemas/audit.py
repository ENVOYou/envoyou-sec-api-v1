"""
Audit schemas for audit trail endpoints
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEntryResponse(BaseModel):
    """Response schema for audit entries"""

    id: str = Field(..., description="Audit entry unique identifier")
    timestamp: datetime = Field(..., description="When the audited action occurred")
    user_id: str = Field(..., description="User who performed the action")
    user_email: Optional[str] = Field(None, description="User email for reference")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: str = Field(..., description="Identifier of the affected resource")
    entity_type: Optional[str] = Field(None, description="Specific entity type")
    entity_id: Optional[str] = Field(None, description="Specific entity identifier")
    before_state: Optional[Dict[str, Any]] = Field(
        None, description="State before the action"
    )
    after_state: Optional[Dict[str, Any]] = Field(
        None, description="State after the action"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    ip_address: Optional[str] = Field(None, description="IP address of the user")
    user_agent: Optional[str] = Field(None, description="User agent string")
    session_id: Optional[str] = Field(None, description="Session identifier")


class AuditTrailResponse(BaseModel):
    """Response schema for audit trail queries"""

    total_entries: int = Field(..., description="Total number of audit entries")
    entries: List[AuditEntryResponse] = Field(
        default_factory=list, description="List of audit entries"
    )
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of entries per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")


class AuditSessionRequest(BaseModel):
    """Request schema for creating audit sessions"""

    session_name: str = Field(..., description="Name of the audit session")
    auditor_id: str = Field(..., description="ID of the auditor")
    scope: Dict[str, Any] = Field(
        default_factory=dict, description="Scope of the audit session"
    )
    start_date: Optional[datetime] = Field(
        None, description="Start date for audit period"
    )
    end_date: Optional[datetime] = Field(
        None, description="End date for audit period"
    )


class AuditSessionResponse(BaseModel):
    """Response schema for audit sessions"""

    session_id: str = Field(..., description="Unique session identifier")
    session_name: str = Field(..., description="Name of the audit session")
    auditor_id: str = Field(..., description="ID of the auditor")
    auditor_email: Optional[str] = Field(None, description="Email of the auditor")
    status: str = Field(..., description="Session status: active, completed, suspended")
    scope: Dict[str, Any] = Field(..., description="Scope of the audit session")
    start_date: Optional[datetime] = Field(
        None, description="Start date for audit period"
    )
    end_date: Optional[datetime] = Field(
        None, description="End date for audit period"
    )
    created_at: datetime = Field(..., description="When the session was created")
    last_accessed: Optional[datetime] = Field(
        None, description="When the session was last accessed"
    )
    access_count: int = Field(..., description="Number of times session was accessed")


class ForensicReportRequest(BaseModel):
    """Request schema for forensic audit reports"""

    session_id: str = Field(..., description="Audit session identifier")
    report_type: str = Field(
        ..., description="Type of report: summary, detailed, compliance"
    )
    include_attachments: bool = Field(
        True, description="Whether to include data attachments"
    )
    format: str = Field("pdf", description="Report format: pdf, json, xml")


class ForensicReportResponse(BaseModel):
    """Response schema for forensic audit reports"""

    report_id: str = Field(..., description="Unique report identifier")
    session_id: str = Field(..., description="Audit session identifier")
    report_type: str = Field(..., description="Type of report generated")
    generated_at: datetime = Field(..., description="When the report was generated")
    generated_by: str = Field(..., description="User who generated the report")
    report_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Report metadata"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict, description="Report summary statistics"
    )
    findings: List[Dict[str, Any]] = Field(
        default_factory=list, description="Key findings from the audit"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Audit recommendations"
    )
    compliance_status: str = Field(..., description="Overall compliance assessment")


class DataLineageRequest(BaseModel):
    """Request schema for data lineage queries"""

    entity_type: str = Field(..., description="Type of entity to trace")
    entity_id: str = Field(..., description="Identifier of the entity")
    depth: int = Field(3, le=10, description="Depth of lineage tracing")
    include_metadata: bool = Field(
        True, description="Whether to include metadata in response"
    )


class DataLineageResponse(BaseModel):
    """Response schema for data lineage information"""

    entity_type: str = Field(..., description="Type of entity traced")
    entity_id: str = Field(..., description="Identifier of the entity")
    lineage_chain: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chain of data transformations"
    )
    provenance_score: float = Field(
        ..., description="Data provenance confidence score"
    )
    last_updated: datetime = Field(..., description="When lineage was last updated")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional lineage metadata"
    )


class AuditSummaryResponse(BaseModel):
    """Response schema for audit summaries"""

    total_audit_entries: int = Field(..., description="Total number of audit entries")
    date_range: Dict[str, str] = Field(..., description="Date range covered")
    user_activity: Dict[str, int] = Field(
        default_factory=dict, description="Activity by user"
    )
    action_types: Dict[str, int] = Field(
        default_factory=dict, description="Count by action type"
    )
    resource_types: Dict[str, int] = Field(
        default_factory=dict, description="Count by resource type"
    )
    anomalies_detected: int = Field(..., description="Number of anomalies detected")
    compliance_score: float = Field(..., description="Overall compliance score")
    last_audit_entry: Optional[datetime] = Field(
        None, description="Timestamp of last audit entry"
    )


class AuditAnomalyResponse(BaseModel):
    """Response schema for audit anomaly detection"""

    anomaly_id: str = Field(..., description="Unique anomaly identifier")
    detected_at: datetime = Field(..., description="When anomaly was detected")
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    description: str = Field(..., description="Description of the anomaly")
    affected_entries: List[str] = Field(
        default_factory=list, description="IDs of affected audit entries"
    )
    risk_assessment: Dict[str, Any] = Field(
        default_factory=dict, description="Risk assessment details"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Recommended corrective actions"
    )