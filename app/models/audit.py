"""
Audit Models
Database models for comprehensive audit trail functionality
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class AuditEntry(Base):
    """Comprehensive audit entry for all system activities"""

    __tablename__ = "audit_entries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    audit_metadata = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        primaryjoin="AuditEntry.user_id == User.id",
        lazy="select",
    )

    __table_args__ = (
        Index("idx_audit_timestamp_action", "timestamp", "action"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_session", "session_id"),
    )

    def __repr__(self):
        return f"<AuditEntry(id={self.id}, action={self.action}, entity_type={self.entity_type}, user_id={self.user_id})>"


class AuditSession(Base):
    """Audit session for external auditors"""

    __tablename__ = "audit_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    session_purpose = Column(String(255), nullable=False)
    status = Column(
        String(50), nullable=False, default="active"
    )  # active, completed, expired
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)
    requested_by = Column(String(255), nullable=True)
    access_count = Column(Integer, default=0)
    audit_metadata = Column(JSON, nullable=True)

    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        primaryjoin="AuditSession.user_id == User.id",
        lazy="select",
    )

    __table_args__ = (
        Index("idx_audit_session_user", "user_id", "status"),
        Index("idx_audit_session_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<AuditSession(id={self.id}, user_id={self.user_id}, status={self.status})>"


class AuditAnomaly(Base):
    """Detected audit anomalies"""

    __tablename__ = "audit_anomalies"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    anomaly_id = Column(String(255), nullable=False, unique=True, index=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    anomaly_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    affected_entries = Column(JSON, nullable=True)  # List of affected audit entry IDs
    risk_assessment = Column(Text, nullable=True)
    recommended_actions = Column(JSON, nullable=True)  # List of recommended actions
    status = Column(
        String(50), nullable=False, default="open"
    )  # open, investigating, resolved, dismissed
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(255), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    audit_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_anomaly_type_severity", "anomaly_type", "severity"),
        Index("idx_anomaly_status_detected", "status", "detected_at"),
    )

    def __repr__(self):
        return f"<AuditAnomaly(id={self.id}, type={self.anomaly_type}, severity={self.severity})>"


class AuditReport(Base):
    """Generated audit reports"""

    __tablename__ = "audit_reports"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id = Column(String(255), nullable=False, unique=True, index=True)
    report_type = Column(
        String(100), nullable=False
    )  # summary, forensic, compliance, etc.
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    generated_by = Column(String(255), nullable=False)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    parameters = Column(JSON, nullable=True)  # Report generation parameters
    summary_stats = Column(JSON, nullable=True)  # Summary statistics
    file_path = Column(String(1000), nullable=True)  # Path to generated report file
    file_size = Column(Integer, nullable=True)
    status = Column(
        String(50), nullable=False, default="completed"
    )  # generating, completed, failed
    error_message = Column(Text, nullable=True)
    download_count = Column(Integer, default=0)
    last_downloaded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    audit_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_report_type_generated", "report_type", "generated_at"),
        Index("idx_report_generated_by", "generated_by", "generated_at"),
    )

    def __repr__(self):
        return (
            f"<AuditReport(id={self.id}, type={self.report_type}, title={self.title})>"
        )


class DataLineage(Base):
    """Data lineage tracking"""

    __tablename__ = "data_lineage"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=False)
    parent_entity_type = Column(String(100), nullable=True)
    parent_entity_id = Column(String(255), nullable=True)
    transformation_type = Column(String(100), nullable=True)
    transformation_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    audit_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_lineage_entity", "entity_type", "entity_id"),
        Index("idx_lineage_parent", "parent_entity_type", "parent_entity_id"),
        Index("idx_lineage_created", "created_at"),
    )

    def __repr__(self):
        return (
            f"<DataLineage(id={self.id}, entity={self.entity_type}:{self.entity_id})>"
        )


class AuditConfiguration(Base):
    """Audit system configuration"""

    __tablename__ = "audit_configuration"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    config_key = Column(String(255), nullable=False, unique=True, index=True)
    config_value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<AuditConfiguration(key={self.config_key})>"
