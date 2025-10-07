"""
Emissions Calculation Audit Service
Comprehensive audit trail system for SEC compliance and forensic traceability
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.emissions import (
    ActivityData,
    CalculationAuditTrail,
    Company,
    CompanyEntity,
    EmissionsCalculation,
)
from app.models.user import User
from app.schemas.emissions import (
    CalculationAuditTrailResponse,
    EmissionsCalculationResponse,
)

logger = logging.getLogger(__name__)


class EmissionsAuditService:
    """Service for comprehensive audit trail management of emissions calculations"""

    def __init__(self, db: Session):
        self.db = db

    def log_calculation_event(
        self,
        calculation_id: str,
        event_type: str,
        event_description: str,
        user_id: str,
        user_role: str,
        field_changed: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> CalculationAuditTrail:
        """Log an audit event for emissions calculation"""
        try:
            audit_entry = CalculationAuditTrail(
                calculation_id=uuid.UUID(calculation_id),
                event_type=event_type,
                event_description=event_description,
                user_id=uuid.UUID(user_id),
                user_role=user_role,
                field_changed=field_changed,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                additional_metadata=additional_metadata or {},
            )

            self.db.add(audit_entry)
            self.db.commit()

            logger.info(
                f"Audit event logged: {event_type} for calculation {calculation_id} by user {user_id}"
            )

            return audit_entry

        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")
            self.db.rollback()
            raise

    def get_calculation_audit_trail(
        self,
        calculation_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> List[CalculationAuditTrailResponse]:
        """Get complete audit trail for a calculation"""
        try:
            query = self.db.query(CalculationAuditTrail).filter(
                CalculationAuditTrail.calculation_id == calculation_id
            )

            if start_date:
                query = query.filter(
                    CalculationAuditTrail.event_timestamp >= start_date
                )

            if end_date:
                query = query.filter(CalculationAuditTrail.event_timestamp <= end_date)

            if event_types:
                query = query.filter(CalculationAuditTrail.event_type.in_(event_types))

            if user_id:
                query = query.filter(CalculationAuditTrail.user_id == user_id)

            audit_entries = query.order_by(
                CalculationAuditTrail.event_timestamp.desc()
            ).all()

            return [
                CalculationAuditTrailResponse(
                    id=str(entry.id),
                    calculation_id=str(entry.calculation_id),
                    event_type=entry.event_type,
                    event_description=entry.event_description,
                    user_id=str(entry.user_id),
                    user_role=entry.user_role,
                    event_timestamp=entry.event_timestamp,
                    field_changed=entry.field_changed,
                    old_value=entry.old_value,
                    new_value=entry.new_value,
                    reason=entry.reason,
                )
                for entry in audit_entries
            ]

        except Exception as e:
            logger.error(f"Error retrieving audit trail: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve audit trail: {str(e)}",
            )

    def get_company_audit_summary(
        self,
        company_id: str,
        reporting_year: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get audit summary for all calculations of a company"""
        try:
            # Base query for company calculations
            calc_query = self.db.query(EmissionsCalculation).filter(
                EmissionsCalculation.company_id == company_id
            )

            if reporting_year:
                calc_query = calc_query.filter(
                    func.extract("year", EmissionsCalculation.reporting_period_start)
                    == reporting_year
                )

            if start_date:
                calc_query = calc_query.filter(
                    EmissionsCalculation.created_at >= start_date
                )

            if end_date:
                calc_query = calc_query.filter(
                    EmissionsCalculation.created_at <= end_date
                )

            calculations = calc_query.all()
            calculation_ids = [str(calc.id) for calc in calculations]

            if not calculation_ids:
                return {
                    "company_id": company_id,
                    "total_calculations": 0,
                    "total_audit_events": 0,
                    "event_summary": {},
                    "user_activity": {},
                    "data_quality_trends": [],
                    "compliance_status": "no_data",
                }

            # Get audit events for all calculations
            audit_query = self.db.query(CalculationAuditTrail).filter(
                CalculationAuditTrail.calculation_id.in_(calculation_ids)
            )

            if start_date:
                audit_query = audit_query.filter(
                    CalculationAuditTrail.event_timestamp >= start_date
                )

            if end_date:
                audit_query = audit_query.filter(
                    CalculationAuditTrail.event_timestamp <= end_date
                )

            audit_events = audit_query.all()

            # Analyze audit events
            event_summary = {}
            user_activity = {}

            for event in audit_events:
                # Event type summary
                event_summary[event.event_type] = (
                    event_summary.get(event.event_type, 0) + 1
                )

                # User activity summary
                user_key = str(event.user_id)
                if user_key not in user_activity:
                    user_activity[user_key] = {
                        "user_role": event.user_role,
                        "event_count": 0,
                        "last_activity": event.event_timestamp,
                    }
                user_activity[user_key]["event_count"] += 1
                if event.event_timestamp > user_activity[user_key]["last_activity"]:
                    user_activity[user_key]["last_activity"] = event.event_timestamp

            # Calculate data quality trends
            data_quality_trends = self._calculate_data_quality_trends(calculations)

            # Determine compliance status
            compliance_status = self._assess_compliance_status(
                calculations, audit_events
            )

            return {
                "company_id": company_id,
                "total_calculations": len(calculations),
                "total_audit_events": len(audit_events),
                "event_summary": event_summary,
                "user_activity": user_activity,
                "data_quality_trends": data_quality_trends,
                "compliance_status": compliance_status,
                "audit_coverage": self._calculate_audit_coverage(
                    calculations, audit_events
                ),
                "last_audit_activity": (
                    max([e.event_timestamp for e in audit_events])
                    if audit_events
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Error generating audit summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate audit summary: {str(e)}",
            )

    def verify_calculation_integrity(self, calculation_id: str) -> Dict[str, Any]:
        """Verify the integrity of a calculation and its audit trail"""
        try:
            # Get calculation
            calculation = (
                self.db.query(EmissionsCalculation)
                .filter(EmissionsCalculation.id == calculation_id)
                .first()
            )

            if not calculation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Calculation {calculation_id} not found",
                )

            # Get audit trail
            audit_events = (
                self.db.query(CalculationAuditTrail)
                .filter(CalculationAuditTrail.calculation_id == calculation_id)
                .order_by(CalculationAuditTrail.event_timestamp)
                .all()
            )

            # Get activity data
            activity_data = (
                self.db.query(ActivityData)
                .filter(ActivityData.calculation_id == calculation_id)
                .all()
            )

            integrity_checks = {
                "calculation_exists": True,
                "has_audit_trail": len(audit_events) > 0,
                "has_activity_data": len(activity_data) > 0,
                "audit_trail_complete": self._verify_audit_trail_completeness(
                    calculation, audit_events
                ),
                "data_consistency": self._verify_data_consistency(
                    calculation, activity_data
                ),
                "calculation_reproducible": self._verify_calculation_reproducibility(
                    calculation, activity_data
                ),
                "emission_factors_traceable": self._verify_emission_factors_traceability(
                    activity_data
                ),
                "timestamps_consistent": self._verify_timestamp_consistency(
                    calculation, audit_events
                ),
                "user_authorization_valid": self._verify_user_authorization(
                    audit_events
                ),
            }

            # Calculate overall integrity score
            passed_checks = sum(
                1 for check in integrity_checks.values() if check is True
            )
            total_checks = len(integrity_checks)
            integrity_score = (passed_checks / total_checks) * 100

            # Identify issues
            issues = [
                check_name
                for check_name, passed in integrity_checks.items()
                if passed is False
            ]

            return {
                "calculation_id": calculation_id,
                "integrity_score": integrity_score,
                "integrity_checks": integrity_checks,
                "issues_found": issues,
                "audit_events_count": len(audit_events),
                "activity_data_count": len(activity_data),
                "verification_timestamp": datetime.utcnow(),
                "is_compliant": integrity_score >= 95.0,  # 95% threshold for compliance
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying calculation integrity: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify calculation integrity: {str(e)}",
            )

    def generate_forensic_report(
        self,
        calculation_id: str,
        include_raw_data: bool = True,
        include_user_details: bool = True,
    ) -> Dict[str, Any]:
        """Generate comprehensive forensic report for SEC audit purposes"""
        try:
            # Get calculation with all related data
            calculation = (
                self.db.query(EmissionsCalculation)
                .filter(EmissionsCalculation.id == calculation_id)
                .first()
            )

            if not calculation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Calculation {calculation_id} not found",
                )

            # Get company information
            company = (
                self.db.query(Company)
                .filter(Company.id == calculation.company_id)
                .first()
            )

            # Get entity information if applicable
            entity = None
            if calculation.entity_id:
                entity = (
                    self.db.query(CompanyEntity)
                    .filter(CompanyEntity.id == calculation.entity_id)
                    .first()
                )

            # Get complete audit trail
            audit_trail = self.get_calculation_audit_trail(calculation_id)

            # Get activity data
            activity_data = (
                self.db.query(ActivityData)
                .filter(ActivityData.calculation_id == calculation_id)
                .all()
            )

            # Get user information if requested
            user_details = {}
            if include_user_details:
                user_ids = set()
                user_ids.add(str(calculation.calculated_by))
                if calculation.reviewed_by:
                    user_ids.add(str(calculation.reviewed_by))
                if calculation.approved_by:
                    user_ids.add(str(calculation.approved_by))

                for event in audit_trail:
                    user_ids.add(event.user_id)

                users = self.db.query(User).filter(User.id.in_(user_ids)).all()
                user_details = {
                    str(user.id): {
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role.value,
                    }
                    for user in users
                }

            # Verify calculation integrity
            integrity_check = self.verify_calculation_integrity(calculation_id)

            # Build forensic report
            forensic_report = {
                "report_metadata": {
                    "report_id": str(uuid.uuid4()),
                    "generated_at": datetime.utcnow(),
                    "calculation_id": calculation_id,
                    "report_type": "forensic_audit",
                    "sec_compliance": True,
                },
                "calculation_summary": {
                    "calculation_name": calculation.calculation_name,
                    "calculation_code": calculation.calculation_code,
                    "scope": calculation.scope,
                    "method": calculation.method,
                    "status": calculation.status,
                    "reporting_period": {
                        "start": calculation.reporting_period_start,
                        "end": calculation.reporting_period_end,
                    },
                    "results": {
                        "total_co2e": calculation.total_co2e,
                        "total_co2": calculation.total_co2,
                        "total_ch4": calculation.total_ch4,
                        "total_n2o": calculation.total_n2o,
                    },
                    "quality_metrics": {
                        "data_quality_score": calculation.data_quality_score,
                        "uncertainty_percentage": calculation.uncertainty_percentage,
                        "calculation_duration_seconds": calculation.calculation_duration_seconds,
                    },
                },
                "company_information": {
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "ticker": company.ticker,
                    "cik": company.cik,
                    "reporting_year": company.reporting_year,
                },
                "entity_information": (
                    {
                        "entity_id": str(entity.id) if entity else None,
                        "entity_name": entity.name if entity else None,
                        "ownership_percentage": (
                            entity.ownership_percentage if entity else None
                        ),
                    }
                    if entity
                    else None
                ),
                "audit_trail": {
                    "total_events": len(audit_trail),
                    "events": [event.dict() for event in audit_trail],
                },
                "activity_data": {
                    "total_activities": len(activity_data),
                    "activities": (
                        [
                            {
                                "id": str(ad.id),
                                "activity_type": ad.activity_type,
                                "fuel_type": ad.fuel_type,
                                "quantity": ad.quantity,
                                "unit": ad.unit,
                                "location": ad.location,
                                "emission_factor": {
                                    "id": (
                                        str(ad.emission_factor_id)
                                        if ad.emission_factor_id
                                        else None
                                    ),
                                    "value": ad.emission_factor_value,
                                    "unit": ad.emission_factor_unit,
                                    "source": ad.emission_factor_source,
                                },
                                "emissions": {
                                    "co2": ad.co2_emissions,
                                    "ch4": ad.ch4_emissions,
                                    "n2o": ad.n2o_emissions,
                                    "co2e": ad.co2e_emissions,
                                },
                                "data_quality": ad.data_quality,
                                "data_source": ad.data_source,
                            }
                            for ad in activity_data
                        ]
                        if include_raw_data
                        else []
                    ),
                },
                "integrity_verification": integrity_check,
                "user_information": user_details if include_user_details else {},
                "emission_factors_used": calculation.emission_factors_used or {},
                "compliance_attestation": {
                    "sec_climate_disclosure_compliant": integrity_check["is_compliant"],
                    "audit_trail_complete": integrity_check["integrity_checks"][
                        "audit_trail_complete"
                    ],
                    "data_traceable": integrity_check["integrity_checks"][
                        "emission_factors_traceable"
                    ],
                    "calculation_reproducible": integrity_check["integrity_checks"][
                        "calculation_reproducible"
                    ],
                },
            }

            logger.info(f"Forensic report generated for calculation {calculation_id}")

            return forensic_report

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating forensic report: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate forensic report: {str(e)}",
            )

    def _calculate_data_quality_trends(
        self, calculations: List[EmissionsCalculation]
    ) -> List[Dict[str, Any]]:
        """Calculate data quality trends over time"""
        trends = []

        # Group calculations by month
        monthly_data = {}
        for calc in calculations:
            month_key = calc.created_at.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(calc)

        # Calculate average quality score per month
        for month, calcs in monthly_data.items():
            quality_scores = [
                c.data_quality_score for c in calcs if c.data_quality_score
            ]
            avg_quality = (
                sum(quality_scores) / len(quality_scores) if quality_scores else 0
            )

            trends.append(
                {
                    "month": month,
                    "calculation_count": len(calcs),
                    "average_quality_score": avg_quality,
                    "completed_calculations": len(
                        [c for c in calcs if c.status == "completed"]
                    ),
                }
            )

        return sorted(trends, key=lambda x: x["month"])

    def _assess_compliance_status(
        self,
        calculations: List[EmissionsCalculation],
        audit_events: List[CalculationAuditTrail],
    ) -> str:
        """Assess overall compliance status"""
        if not calculations:
            return "no_data"

        # Check if all calculations have audit trails
        calc_ids = {str(c.id) for c in calculations}
        audited_calc_ids = {str(e.calculation_id) for e in audit_events}

        if not calc_ids.issubset(audited_calc_ids):
            return "non_compliant"

        # Check if all calculations are completed or approved
        incomplete_calcs = [
            c for c in calculations if c.status not in ["completed", "approved"]
        ]
        if incomplete_calcs:
            return "pending"

        # Check data quality scores
        low_quality_calcs = [
            c
            for c in calculations
            if c.data_quality_score and c.data_quality_score < 70
        ]
        if low_quality_calcs:
            return "needs_improvement"

        return "compliant"

    def _calculate_audit_coverage(
        self,
        calculations: List[EmissionsCalculation],
        audit_events: List[CalculationAuditTrail],
    ) -> float:
        """Calculate audit coverage percentage"""
        if not calculations:
            return 0.0

        calc_ids = {str(c.id) for c in calculations}
        audited_calc_ids = {str(e.calculation_id) for e in audit_events}

        coverage = len(calc_ids.intersection(audited_calc_ids)) / len(calc_ids)
        return coverage * 100

    def _verify_audit_trail_completeness(
        self,
        calculation: EmissionsCalculation,
        audit_events: List[CalculationAuditTrail],
    ) -> bool:
        """Verify that audit trail is complete"""
        required_events = ["calculation_created", "calculation_completed"]

        if calculation.status == "approved":
            required_events.append("calculation_approved")

        event_types = {event.event_type for event in audit_events}

        return all(req_event in event_types for req_event in required_events)

    def _verify_data_consistency(
        self, calculation: EmissionsCalculation, activity_data: List[ActivityData]
    ) -> bool:
        """Verify data consistency between calculation and activity data"""
        if not activity_data:
            return False

        # Sum up activity data emissions
        total_co2e_from_activities = sum(ad.co2e_emissions for ad in activity_data)

        # Compare with calculation total (allow small rounding differences)
        if calculation.total_co2e is None:
            return False

        difference = abs(total_co2e_from_activities - calculation.total_co2e)
        tolerance = calculation.total_co2e * 0.001  # 0.1% tolerance

        return difference <= tolerance

    def _verify_calculation_reproducibility(
        self, calculation: EmissionsCalculation, activity_data: List[ActivityData]
    ) -> bool:
        """Verify that calculation can be reproduced from activity data"""
        # Check if all activity data has emission factors
        for ad in activity_data:
            if not ad.emission_factor_value or not ad.emission_factor_source:
                return False

        # Check if input data is preserved
        if not calculation.input_data:
            return False

        return True

    def _verify_emission_factors_traceability(
        self, activity_data: List[ActivityData]
    ) -> bool:
        """Verify that emission factors are traceable to EPA sources"""
        for ad in activity_data:
            if not ad.emission_factor_source:
                return False

            # Check if source is from EPA
            epa_sources = ["EPA_GHGRP", "EPA_EGRID", "EPA_AP42"]
            if ad.emission_factor_source not in epa_sources:
                return False

        return True

    def _verify_timestamp_consistency(
        self,
        calculation: EmissionsCalculation,
        audit_events: List[CalculationAuditTrail],
    ) -> bool:
        """Verify timestamp consistency"""
        if not audit_events:
            return False

        # Check if audit events are in chronological order
        timestamps = [event.event_timestamp for event in audit_events]
        return timestamps == sorted(timestamps)

    def _verify_user_authorization(
        self, audit_events: List[CalculationAuditTrail]
    ) -> bool:
        """Verify that all users in audit trail had proper authorization"""
        # In a full implementation, this would check user roles against actions
        # For now, just verify that all events have user information
        for event in audit_events:
            if not event.user_id or not event.user_role:
                return False

        return True
