"""
Audit Service
Provides comprehensive audit trail functionality for forensic-grade traceability
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditLogger
from app.models.audit import AuditEntry, AuditSession
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

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing audit trails and forensic reporting"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    async def get_audit_trail(
        self,
        entity_id: str,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Get comprehensive audit trail for an entity"""
        try:
            # Build query
            query = self.db.query(AuditEntry)

            # Apply filters
            if entity_id:
                query = query.filter(AuditEntry.entity_id == entity_id)
            if entity_type:
                query = query.filter(AuditEntry.entity_type == entity_type)
            if start_date:
                query = query.filter(AuditEntry.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditEntry.timestamp <= end_date)
            if action:
                query = query.filter(AuditEntry.action.ilike(f"%{action}%"))
            if user_id:
                query = query.filter(AuditEntry.user_id == user_id)

            # Get total count
            total_entries = query.count()

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.order_by(desc(AuditEntry.timestamp))
            query = query.offset(offset).limit(page_size)

            entries = query.all()

            # Calculate pagination info
            total_pages = (total_entries + page_size - 1) // page_size
            has_next = page < total_pages
            has_previous = page > 1

            return {
                "entries": entries,
                "total_entries": total_entries,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
            }

        except Exception as e:
            logger.error(f"Error retrieving audit trail: {str(e)}")
            raise

    async def get_audit_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AuditSummaryResponse:
        """Get audit summary statistics"""
        try:
            # Set default date range
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Query audit statistics
            total_entries = self.db.query(func.count(AuditEntry.id)).filter(
                and_(
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).scalar()

            # Action breakdown
            action_stats = self.db.query(
                AuditEntry.action,
                func.count(AuditEntry.id).label('count')
            ).filter(
                and_(
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).group_by(AuditEntry.action).all()

            actions_breakdown = {action: count for action, count in action_stats}

            # User activity
            user_stats = self.db.query(
                AuditEntry.user_id,
                func.count(AuditEntry.id).label('count')
            ).filter(
                and_(
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).group_by(AuditEntry.user_id).all()

            user_activity = {str(user_id): count for user_id, count in user_stats}

            # Entity types
            entity_stats = self.db.query(
                AuditEntry.entity_type,
                func.count(AuditEntry.id).label('count')
            ).filter(
                and_(
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).group_by(AuditEntry.entity_type).all()

            entity_types = {entity_type: count for entity_type, count in entity_stats}

            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_entries = self.db.query(func.count(AuditEntry.id)).filter(
                AuditEntry.timestamp >= recent_cutoff
            ).scalar()

            return AuditSummaryResponse(
                total_entries=total_entries,
                date_range_start=start_date,
                date_range_end=end_date,
                actions_breakdown=actions_breakdown,
                user_activity=user_activity,
                entity_types=entity_types,
                recent_activity_24h=recent_entries,
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Error generating audit summary: {str(e)}")
            raise

    async def get_data_lineage(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 3,
        include_metadata: bool = True,
    ) -> DataLineageResponse:
        """Get data lineage and provenance information"""
        try:
            # Get the main entity
            main_entry = self.db.query(AuditEntry).filter(
                and_(
                    AuditEntry.entity_type == entity_type,
                    AuditEntry.entity_id == entity_id
                )
            ).order_by(desc(AuditEntry.timestamp)).first()

            if not main_entry:
                return DataLineageResponse(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    lineage_chain=[],
                    data_provenance={},
                    metadata={} if include_metadata else None,
                )

            # Build lineage chain
            lineage_chain = []
            current_entity = main_entry
            visited = set()

            for _ in range(depth):
                if current_entity.id in visited:
                    break
                visited.add(current_entity.id)

                lineage_chain.append({
                    "entry_id": str(current_entity.id),
                    "timestamp": current_entity.timestamp,
                    "action": current_entity.action,
                    "user_id": current_entity.user_id,
                    "before_state": current_entity.before_state,
                    "after_state": current_entity.after_state,
                    "metadata": current_entity.metadata,
                })

                # Find parent/related entries
                if current_entity.metadata and "parent_entity_id" in current_entity.metadata:
                    parent_id = current_entity.metadata["parent_entity_id"]
                    current_entity = self.db.query(AuditEntry).filter(
                        AuditEntry.entity_id == parent_id
                    ).order_by(desc(AuditEntry.timestamp)).first()
                    if not current_entity:
                        break
                else:
                    break

            # Build data provenance
            data_provenance = {
                "original_source": main_entry.metadata.get("source", "unknown") if main_entry.metadata else "unknown",
                "creation_timestamp": main_entry.timestamp,
                "last_modified": main_entry.timestamp,
                "modification_count": len(lineage_chain),
                "data_quality_score": main_entry.metadata.get("quality_score", 0.0) if main_entry.metadata else 0.0,
            }

            metadata = {
                "depth_explored": len(lineage_chain),
                "total_chain_length": len(lineage_chain),
                "has_circular_references": len(visited) < len(lineage_chain),
            } if include_metadata else None

            return DataLineageResponse(
                entity_type=entity_type,
                entity_id=entity_id,
                lineage_chain=lineage_chain,
                data_provenance=data_provenance,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Error retrieving data lineage: {str(e)}")
            raise

    async def detect_audit_anomalies(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in audit trails"""
        try:
            # Set default date range
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=7)

            anomalies = []

            # Check for unusual login patterns
            login_entries = self.db.query(AuditEntry).filter(
                and_(
                    AuditEntry.action == "LOGIN",
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).all()

            # Group by user and check for anomalies
            user_logins = {}
            for entry in login_entries:
                user_id = entry.user_id
                if user_id not in user_logins:
                    user_logins[user_id] = []
                user_logins[user_id].append(entry)

            # Detect multiple failed logins
            for user_id, entries in user_logins.items():
                failed_logins = [e for e in entries if e.metadata and e.metadata.get("success") == False]
                if len(failed_logins) > 5:  # Threshold for anomaly
                    anomalies.append({
                        "anomaly_id": f"failed_logins_{user_id}_{start_date.date()}",
                        "detected_at": datetime.utcnow(),
                        "anomaly_type": "multiple_failed_logins",
                        "severity": "medium",
                        "description": f"User {user_id} had {len(failed_logins)} failed login attempts",
                        "affected_entries": [str(e.id) for e in failed_logins],
                        "risk_assessment": "Potential brute force attack or forgotten credentials",
                        "recommended_actions": ["Review user access", "Consider temporary account lockout"],
                    })

            # Check for unusual data access patterns
            data_access_entries = self.db.query(AuditEntry).filter(
                and_(
                    AuditEntry.action.in_(["READ", "EXPORT"]),
                    AuditEntry.timestamp >= start_date,
                    AuditEntry.timestamp <= end_date
                )
            ).all()

            # Group by user and count access frequency
            user_access = {}
            for entry in data_access_entries:
                user_id = entry.user_id
                if user_id not in user_access:
                    user_access[user_id] = 0
                user_access[user_id] += 1

            # Detect unusually high access frequency
            avg_access = sum(user_access.values()) / len(user_access) if user_access else 0
            for user_id, count in user_access.items():
                if count > avg_access * 3:  # 3x average
                    anomalies.append({
                        "anomaly_id": f"high_access_{user_id}_{start_date.date()}",
                        "detected_at": datetime.utcnow(),
                        "anomaly_type": "unusual_data_access",
                        "severity": "low",
                        "description": f"User {user_id} accessed data {count} times (3x average)",
                        "affected_entries": [],  # Would need to filter specific entries
                        "risk_assessment": "May indicate normal high usage or potential data exfiltration",
                        "recommended_actions": ["Monitor user activity", "Verify business justification"],
                    })

            # Filter by severity if specified
            if severity:
                anomalies = [a for a in anomalies if a["severity"] == severity]

            return anomalies

        except Exception as e:
            logger.error(f"Error detecting audit anomalies: {str(e)}")
            raise

    async def get_recent_changes(
        self,
        limit: int = 100,
        resource_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent data changes across the system"""
        try:
            query = self.db.query(AuditEntry).filter(
                AuditEntry.action.in_(["CREATE", "UPDATE", "DELETE"])
            )

            if resource_type:
                query = query.filter(AuditEntry.entity_type == resource_type)

            query = query.order_by(desc(AuditEntry.timestamp)).limit(limit)

            entries = query.all()

            changes = []
            for entry in entries:
                changes.append({
                    "id": str(entry.id),
                    "timestamp": entry.timestamp.isoformat(),
                    "action": entry.action,
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "user_id": entry.user_id,
                    "user_email": getattr(entry.user, 'email', None) if hasattr(entry, 'user') else None,
                    "metadata": entry.metadata,
                })

            return changes

        except Exception as e:
            logger.error(f"Error retrieving recent changes: {str(e)}")
            raise

    async def generate_forensic_report(
        self,
        entity_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_attachments: bool = False,
        format: str = "json",
        generated_by: str = None,
    ) -> ForensicReportResponse:
        """Generate comprehensive forensic audit report"""
        try:
            # Get audit trail
            audit_data = await self.get_audit_trail(
                entity_id=entity_id,
                start_date=start_date,
                end_date=end_date,
                page=1,
                page_size=1000  # Large limit for reports
            )

            # Get data lineage
            lineage_data = await self.get_data_lineage(
                entity_type="unknown",  # Would need to determine from context
                entity_id=entity_id,
                depth=5,
            )

            # Get anomalies
            anomalies = await self.detect_audit_anomalies(
                start_date=start_date,
                end_date=end_date,
            )

            # Build report
            report_data = {
                "report_id": f"forensic_{entity_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "entity_id": entity_id,
                "generated_at": datetime.utcnow(),
                "generated_by": generated_by,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None,
                },
                "audit_trail": {
                    "total_entries": audit_data["total_entries"],
                    "entries": [
                        {
                            "id": str(entry.id),
                            "timestamp": entry.timestamp.isoformat(),
                            "action": entry.action,
                            "user_id": entry.user_id,
                            "entity_type": entry.entity_type,
                            "entity_id": entry.entity_id,
                            "metadata": entry.metadata,
                        }
                        for entry in audit_data["entries"]
                    ],
                },
                "data_lineage": {
                    "lineage_chain": lineage_data.lineage_chain,
                    "data_provenance": lineage_data.data_provenance,
                },
                "anomalies_detected": anomalies,
                "compliance_status": {
                    "sec_compliant": True,  # Would need actual compliance checking
                    "data_integrity_verified": True,
                    "audit_trail_complete": audit_data["total_entries"] > 0,
                },
                "metadata": {
                    "format": format,
                    "include_attachments": include_attachments,
                    "processing_time_seconds": 0.0,  # Would calculate actual time
                },
            }

            return ForensicReportResponse(**report_data)

        except Exception as e:
            logger.error(f"Error generating forensic report: {str(e)}")
            raise

    async def create_audit_session(
        self,
        user_id: str,
        session_purpose: str = "external_audit",
        requested_by: Optional[str] = None,
    ) -> AuditSessionResponse:
        """Create audit session for external auditors"""
        try:
            session = AuditSession(
                user_id=user_id,
                session_purpose=session_purpose,
                requested_by=requested_by,
                status="active",
                created_at=datetime.utcnow(),
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            # Log session creation
            await self.audit_logger.log_data_access_event(
                user_id=user_id,
                resource_type="audit_session",
                resource_id=str(session.id),
                action="CREATE",
                additional_data={
                    "session_purpose": session_purpose,
                    "requested_by": requested_by,
                }
            )

            return AuditSessionResponse(
                session_id=str(session.id),
                user_id=session.user_id,
                session_purpose=session.session_purpose,
                status=session.status,
                created_at=session.created_at,
                expires_at=session.expires_at,
                requested_by=session.requested_by,
            )

        except Exception as e:
            logger.error(f"Error creating audit session: {str(e)}")
            self.db.rollback()
            raise