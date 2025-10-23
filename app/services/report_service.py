"""
Report CRUD Service
Service layer for basic report operations (Create, Read, Update, Delete)
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.user import User
from app.schemas.report import (
    CreateReportRequest,
    ReportResponse,
    ReportsFilters,
    ReportsListResponse,
    UpdateReportRequest,
)


class ReportService:
    """Service for basic report CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_reports(
        self,
        filters: Optional[ReportsFilters] = None,
        page: int = 1,
        page_size: int = 20,
        current_user: Optional[User] = None,
    ) -> ReportsListResponse:
        """Get paginated list of reports with optional filtering"""

        # Start with base query
        query = self.db.query(Report)

        # Apply filters
        if filters:
            if filters.status:
                query = query.filter(Report.status.in_(filters.status))
            if filters.report_type:
                query = query.filter(Report.report_type.in_(filters.report_type))
            if filters.company_id:
                query = query.filter(Report.company_id == filters.company_id)
            if filters.reporting_year:
                query = query.filter(Report.reporting_year == filters.reporting_year)
            if filters.created_by:
                query = query.filter(Report.created_by == filters.created_by)
            if filters.priority:
                query = query.filter(Report.priority.in_(filters.priority))
            if filters.date_from:
                query = query.filter(Report.created_at >= filters.date_from)
            if filters.date_to:
                query = query.filter(Report.created_at <= filters.date_to)
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Report.title.ilike(search_term),
                        Report.description.ilike(search_term),
                    )
                )

        # Apply sorting
        sort_by = filters.sort_by if filters else "created_at"
        sort_order = filters.sort_order if filters else "desc"

        if sort_order == "desc":
            query = query.order_by(desc(getattr(Report, sort_by)))
        else:
            query = query.order_by(getattr(Report, sort_by))

        # Get total count
        total_count = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        reports = query.offset(offset).limit(page_size).all()

        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size

        # Convert to response objects
        report_responses = [
            ReportResponse(
                id=str(report.id),
                title=report.title,
                report_type=report.report_type,
                status=report.status,
                version=report.version,
                created_at=report.created_at,
                updated_at=report.updated_at,
                completed_at=report.completed_at,
                workflow_id=str(report.workflow_id) if report.workflow_id else None,
                created_by=str(report.created_by),
                updated_by=str(report.updated_by) if report.updated_by else None,
                content=report.content,
                report_metadata=report.report_metadata,
                pdf_path=report.pdf_path,
                excel_path=report.excel_path,
            )
            for report in reports
        ]

        return ReportsListResponse(
            reports=report_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_report(self, report_id: str) -> Optional[Report]:
        """Get a single report by ID"""
        return self.db.query(Report).filter(Report.id == report_id).first()

    def create_report(
        self, report_data: CreateReportRequest, current_user: User
    ) -> Report:
        """Create a new report"""

        # Create new report
        report = Report(
            title=report_data.title,
            report_type=report_data.report_type,
            company_id=report_data.company_id,
            reporting_year=report_data.reporting_year,
            description=report_data.description,
            priority=report_data.priority or "medium",
            due_date=report_data.due_date,
            created_by=str(current_user.id),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def update_report(
        self, report_id: str, report_data: UpdateReportRequest, current_user: User
    ) -> Optional[Report]:
        """Update an existing report"""

        report = self.get_report(report_id)
        if not report:
            return None

        # Update fields if provided
        update_data = report_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(report, field):
                setattr(report, field, value)

        # Update metadata
        report.updated_by = str(current_user.id)
        report.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(report)

        return report

    def delete_report(self, report_id: str) -> bool:
        """Delete a report"""

        report = self.get_report(report_id)
        if not report:
            return False

        self.db.delete(report)
        self.db.commit()

        return True

    def get_reports_by_company(self, company_id: str) -> List[Report]:
        """Get all reports for a specific company"""
        return self.db.query(Report).filter(Report.company_id == company_id).all()

    def get_reports_by_user(self, user_id: str) -> List[Report]:
        """Get all reports created by a specific user"""
        return self.db.query(Report).filter(Report.created_by == user_id).all()
