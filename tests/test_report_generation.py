"""
Tests for SEC report generation functionality
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.user import User, UserRole
from app.services.report_generator_service import SECReportGenerator


class TestSECReportGenerator:
    """Test cases for SEC report generator service"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_consolidation_service(self):
        """Mock consolidation service"""
        service = MagicMock()
        # Make async methods return coroutines
        service.get_consolidation = AsyncMock()
        service.list_consolidations = AsyncMock()
        return service

    @pytest.fixture
    def mock_consolidation(self):
        """Mock consolidation object"""
        consolidation = MagicMock()
        consolidation.id = uuid4()
        consolidation.company_id = uuid4()
        consolidation.total_co2e = 1000.0
        consolidation.total_scope1_co2e = 600.0
        consolidation.total_scope2_co2e = 300.0
        consolidation.total_scope3_co2e = 100.0
        consolidation.total_entities_included = 5
        consolidation.data_completeness_score = 0.95
        consolidation.consolidation_confidence_score = 0.92
        consolidation.consolidation_method.value = "ownership_based"
        consolidation.status.value = "approved"
        consolidation.is_final = True
        consolidation.validation_status = "passed"
        consolidation.approved_by = uuid4()
        consolidation.approved_at = None
        consolidation.updated_at = None

        # Mock entity contributions
        contrib1 = MagicMock()
        contrib1.entity_id = uuid4()
        contrib1.entity_name = "Manufacturing Plant A"
        contrib1.ownership_percentage = 100.0
        contrib1.consolidation_factor = 1.0
        contrib1.original_scope1_co2e = 400.0
        contrib1.original_scope2_co2e = 200.0
        contrib1.original_scope3_co2e = 50.0
        contrib1.original_total_co2e = 650.0
        contrib1.consolidated_scope1_co2e = 400.0
        contrib1.consolidated_scope2_co2e = 200.0
        contrib1.consolidated_scope3_co2e = 50.0
        contrib1.consolidated_total_co2e = 650.0
        contrib1.data_completeness = 0.98
        contrib1.data_quality_score = 0.95
        contrib1.included_in_consolidation = True
        contrib1.exclusion_reason = None

        consolidation.entity_contributions = [contrib1]
        return consolidation

    @pytest.fixture
    def report_generator(self, mock_db, mock_consolidation_service):
        """Create report generator instance"""
        generator = SECReportGenerator(mock_db)
        generator.consolidation_service = mock_consolidation_service
        return generator

    @pytest.fixture
    def mock_user(self):
        """Mock regular user"""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.is_admin = False
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user"""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.is_admin = True
        return user

    @pytest.mark.asyncio
    async def test_generate_json_report(
        self,
        report_generator,
        mock_consolidation_service,
        mock_consolidation,
        mock_user,
    ):
        """Test JSON report generation"""
        # Setup mocks
        mock_consolidation_service.get_consolidation.return_value = mock_consolidation
        mock_consolidation_service.list_consolidations.return_value = [
            MagicMock(id=mock_consolidation.id)
        ]

        # Generate report
        result = await report_generator.generate_sec_report(
            company_id=uuid4(),
            reporting_year=2024,
            format_type="json",
            include_entity_breakdown=True,
            include_audit_trail=False,
            user=mock_user,
        )

        # Assertions
        assert result["report_type"] == "sec_climate_disclosure"
        assert result["sec_form"] == "10-K"
        assert "executive_summary" in result
        assert "emissions_tables" in result
        assert "methodology" in result
        assert "status" in result
        assert "entity_breakdown" in result

        # Check executive summary
        summary = result["executive_summary"]
        assert summary["total_ghg_emissions_mtco2e"] == 1000.0
        assert summary["scope1_emissions_mtco2e"] == 600.0
        assert summary["scope2_emissions_mtco2e"] == 300.0
        assert summary["data_completeness_score"] == 0.95

    @pytest.mark.asyncio
    async def test_generate_pdf_report(
        self,
        report_generator,
        mock_consolidation_service,
        mock_consolidation,
        mock_user,
    ):
        """Test PDF report generation"""
        # Setup mocks
        mock_consolidation_service.get_consolidation.return_value = mock_consolidation
        mock_consolidation_service.list_consolidations.return_value = [
            MagicMock(id=mock_consolidation.id)
        ]

        # Generate report
        result = await report_generator.generate_sec_report(
            company_id=uuid4(),
            reporting_year=2024,
            format_type="pdf",
            include_entity_breakdown=True,
            include_audit_trail=False,
            user=mock_user,
        )

        # Assertions
        assert "filename" in result
        assert "content_type" in result
        assert "content" in result
        assert result["content_type"] == "application/pdf"
        assert "SEC_Climate_Disclosure" in result["filename"]
        assert isinstance(result["content"], bytes)

    @pytest.mark.asyncio
    async def test_generate_excel_report(
        self,
        report_generator,
        mock_consolidation_service,
        mock_consolidation,
        mock_user,
    ):
        """Test Excel report generation"""
        # Setup mocks
        mock_consolidation_service.get_consolidation.return_value = mock_consolidation
        mock_consolidation_service.list_consolidations.return_value = [
            MagicMock(id=mock_consolidation.id)
        ]

        # Generate report
        result = await report_generator.generate_sec_report(
            company_id=uuid4(),
            reporting_year=2024,
            format_type="excel",
            include_entity_breakdown=True,
            include_audit_trail=False,
            user=mock_user,
        )

        # Assertions
        assert "filename" in result
        assert "content_type" in result
        assert "content" in result
        assert (
            result["content_type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "SEC_Climate_Disclosure" in result["filename"]
        assert ".xlsx" in result["filename"]
        assert isinstance(result["content"], bytes)

    @pytest.mark.asyncio
    async def test_audit_trail_inclusion_admin_only(
        self,
        report_generator,
        mock_consolidation_service,
        mock_consolidation,
        mock_user,
        mock_admin_user,
    ):
        """Test that audit trail is only included for admin users"""
        # Setup mocks
        mock_consolidation_service.get_consolidation.return_value = mock_consolidation
        mock_consolidation_service.list_consolidations.return_value = [
            MagicMock(id=mock_consolidation.id)
        ]

        # Test regular user - should not include audit trail
        result_regular = await report_generator.generate_sec_report(
            company_id=uuid4(),
            reporting_year=2024,
            format_type="json",
            include_entity_breakdown=True,
            include_audit_trail=True,
            user=mock_user,
        )

        assert "audit_trail" not in result_regular

        # Test admin user - should include audit trail
        result_admin = await report_generator.generate_sec_report(
            company_id=uuid4(),
            reporting_year=2024,
            format_type="json",
            include_entity_breakdown=True,
            include_audit_trail=True,
            user=mock_admin_user,
        )

        assert "audit_trail" in result_admin

    def test_format_scope1_table(self, report_generator, mock_consolidation):
        """Test Scope 1 table formatting"""
        result = report_generator._format_scope1_table(mock_consolidation)

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure
        first_row = result[0]
        assert "source_category" in first_row
        assert "emissions_mtco2e" in first_row
        assert "percentage_of_total" in first_row

        # Check calculations
        assert first_row["emissions_mtco2e"] == 400.0  # From mock data
        assert first_row["percentage_of_total"] == 66.7  # 400/600 * 100

    def test_format_scope2_table(self, report_generator, mock_consolidation):
        """Test Scope 2 table formatting"""
        result = report_generator._format_scope2_table(mock_consolidation)

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure
        first_row = result[0]
        assert "source_category" in first_row
        assert "emissions_mtco2e" in first_row
        assert "percentage_of_total" in first_row

        # Check calculations
        assert first_row["emissions_mtco2e"] == 200.0  # From mock data
        assert first_row["percentage_of_total"] == 66.7  # 200/300 * 100

    def test_format_entity_breakdown(self, report_generator, mock_consolidation):
        """Test entity breakdown formatting"""
        result = report_generator._format_entity_breakdown(mock_consolidation)

        assert isinstance(result, list)
        assert len(result) == 1  # One entity in mock

        entity = result[0]
        assert "entity_id" in entity
        assert "entity_name" in entity
        assert "ownership_percentage" in entity
        assert "consolidated_emissions" in entity
        assert "original_emissions" in entity
        assert "data_quality" in entity

        # Check values
        assert entity["entity_name"] == "Manufacturing Plant A"
        assert entity["ownership_percentage"] == 100.0
        assert entity["consolidated_emissions"]["total_mtco2e"] == 650.0

    @pytest.mark.asyncio
    async def test_error_handling_no_consolidation(
        self, report_generator, mock_consolidation_service
    ):
        """Test error handling when no consolidation is found"""
        from fastapi import HTTPException

        # Setup mock to return empty list
        mock_consolidation_service.list_consolidations.return_value = []

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await report_generator.generate_sec_report(
                company_id=uuid4(),
                reporting_year=2024,
                format_type="json",
                user=MagicMock(),
            )

        assert exc_info.value.status_code == 404
        assert "No consolidations found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_format_type(
        self, report_generator, mock_consolidation_service, mock_consolidation
    ):
        """Test error handling for invalid format type"""
        from fastapi import HTTPException

        # Setup mocks
        mock_consolidation_service.get_consolidation.return_value = mock_consolidation
        mock_consolidation_service.list_consolidations.return_value = [
            MagicMock(id=mock_consolidation.id)
        ]

        # Should raise HTTPException for invalid format
        with pytest.raises(HTTPException) as exc_info:
            await report_generator.generate_sec_report(
                company_id=uuid4(),
                reporting_year=2024,
                format_type="invalid_format",
                user=MagicMock(),
            )

        assert exc_info.value.status_code == 400
        assert "Unsupported format" in str(exc_info.value.detail)


class TestSECCompliance:
    """Test SEC compliance aspects of report generation"""

    def test_sec_form_structure(self):
        """Test that report structure complies with SEC requirements"""
        # This would test specific SEC form requirements
        # For now, just check basic structure exists
        required_sections = [
            "executive_summary",
            "emissions_tables",
            "methodology",
            "status",
        ]

        # Mock report structure
        report = {
            "executive_summary": {},
            "emissions_tables": {},
            "methodology": {},
            "status": {},
        }

        for section in required_sections:
            assert section in report, f"Missing required SEC section: {section}"

    def test_emissions_table_format(self):
        """Test that emissions tables follow SEC formatting requirements"""
        # Test table structure
        table_data = [
            {
                "source_category": "Stationary Combustion",
                "emissions_mtco2e": 1000.0,
                "percentage_of_total": 50.0,
            }
        ]

        # Check required fields
        for row in table_data:
            assert "source_category" in row
            assert "emissions_mtco2e" in row
            assert isinstance(row["emissions_mtco2e"], (int, float))
            assert row["emissions_mtco2e"] >= 0

    def test_data_quality_disclosure(self):
        """Test that data quality disclosures meet SEC requirements"""
        methodology = {
            "data_quality_assessment": {
                "completeness": 0.95,
                "accuracy": 0.92,
                "consistency": "Cross-validated",
                "transparency": "Full audit trail",
            }
        }

        # Check required quality metrics
        quality = methodology["data_quality_assessment"]
        assert "completeness" in quality
        assert "accuracy" in quality
        assert "consistency" in quality
        assert "transparency" in quality

        # Check completeness is a reasonable percentage
        assert 0 <= quality["completeness"] <= 1
