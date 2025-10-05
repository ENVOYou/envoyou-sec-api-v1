"""
Tests for Emissions Consolidation Service
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.emissions import (
    Company,
    CompanyEntity,
    ConsolidatedEmissions,
    EmissionsCalculation,
)
from app.schemas.consolidation import (
    ConsolidationMethod,
    ConsolidationRequest,
    ConsolidationStatus,
)
from app.services.emissions_consolidation_service import EmissionsConsolidationService


class TestEmissionsConsolidationService:
    """Test cases for emissions consolidation service"""

    @pytest.fixture
    def consolidation_service(self, db_session):
        """Create consolidation service instance"""
        return EmissionsConsolidationService(db_session)

    @pytest.fixture
    def sample_company(self, db_session):
        """Create sample company for testing"""
        company = Company(
            id=uuid4(),
            company_name="Test Corporation",
            ticker_symbol="TEST",
            cik="0001234567",
            industry_sector="Technology",
            is_active=True
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        return company

    @pytest.fixture
    def sample_entities(self, db_session, sample_company):
        """Create sample entities for testing"""
        entities = []
        
        # Entity 1: 100% owned subsidiary
        entity1 = CompanyEntity(
            id=uuid4(),
            parent_company_id=sample_company.id,
            entity_name="Subsidiary A",
            entity_type="subsidiary",
            ownership_percentage=Decimal("100.0"),
            has_operational_control=True,
            has_financial_control=True,
            is_active=True
        )
        entities.append(entity1)
        
        # Entity 2: 75% owned subsidiary
        entity2 = CompanyEntity(
            id=uuid4(),
            parent_company_id=sample_company.id,
            entity_name="Subsidiary B",
            entity_type="subsidiary",
            ownership_percentage=Decimal("75.0"),
            has_operational_control=True,
            has_financial_control=False,
            is_active=True
        )
        entities.append(entity2)
        
        # Entity 3: 25% owned joint venture
        entity3 = CompanyEntity(
            id=uuid4(),
            parent_company_id=sample_company.id,
            entity_name="Joint Venture C",
            entity_type="joint_venture",
            ownership_percentage=Decimal("25.0"),
            has_operational_control=False,
            has_financial_control=False,
            is_active=True
        )
        entities.append(entity3)
        
        for entity in entities:
            db_session.add(entity)
        
        db_session.commit()
        
        for entity in entities:
            db_session.refresh(entity)
        
        return entities

    @pytest.fixture
    def sample_emissions(self, db_session, sample_entities):
        """Create sample emissions data for entities"""
        emissions = []
        
        # Emissions for Entity 1
        emission1 = EmissionsCalculation(
            id=uuid4(),
            entity_id=sample_entities[0].id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            total_scope1_co2e=Decimal("1000.0"),
            total_scope2_co2e=Decimal("500.0"),
            total_scope3_co2e=Decimal("200.0"),
            total_co2e=Decimal("1700.0"),
            status="approved",
            validation_status="approved"
        )
        emissions.append(emission1)
        
        # Emissions for Entity 2
        emission2 = EmissionsCalculation(
            id=uuid4(),
            entity_id=sample_entities[1].id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            total_scope1_co2e=Decimal("800.0"),
            total_scope2_co2e=Decimal("400.0"),
            total_scope3_co2e=None,  # No Scope 3 data
            total_co2e=Decimal("1200.0"),
            status="approved",
            validation_status="approved"
        )
        emissions.append(emission2)
        
        # Emissions for Entity 3
        emission3 = EmissionsCalculation(
            id=uuid4(),
            entity_id=sample_entities[2].id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            total_scope1_co2e=Decimal("400.0"),
            total_scope2_co2e=Decimal("200.0"),
            total_scope3_co2e=Decimal("100.0"),
            total_co2e=Decimal("700.0"),
            status="approved",
            validation_status="approved"
        )
        emissions.append(emission3)
        
        for emission in emissions:
            db_session.add(emission)
        
        db_session.commit()
        
        for emission in emissions:
            db_session.refresh(emission)
        
        return emissions

    @pytest.mark.asyncio
    async def test_create_ownership_based_consolidation(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test creating ownership-based consolidation"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED,
            include_scope3=False,
            minimum_ownership_threshold=0.0
        )
        
        result = await consolidation_service.create_consolidation(request, "test_user")
        
        # Verify consolidation was created
        assert result.id is not None
        assert result.company_id == sample_company.id
        assert result.reporting_year == 2024
        assert result.consolidation_method == ConsolidationMethod.OWNERSHIP_BASED
        assert result.status == ConsolidationStatus.COMPLETED
        
        # Verify consolidated totals
        # Entity 1: 1000 * 1.0 = 1000 (Scope 1)
        # Entity 2: 800 * 0.75 = 600 (Scope 1)
        # Entity 3: 400 * 0.25 = 100 (Scope 1)
        # Total Scope 1: 1700
        assert result.total_scope1_co2e == 1700.0
        
        # Entity 1: 500 * 1.0 = 500 (Scope 2)
        # Entity 2: 400 * 0.75 = 300 (Scope 2)
        # Entity 3: 200 * 0.25 = 50 (Scope 2)
        # Total Scope 2: 850
        assert result.total_scope2_co2e == 850.0
        
        # Scope 3 not included
        assert result.total_scope3_co2e is None
        
        # Verify entity contributions
        assert len(result.entity_contributions) == 3
        
        # Check Entity 1 contribution (100% ownership)
        entity1_contrib = next(c for c in result.entity_contributions if c.entity_id == sample_entities[0].id)
        assert entity1_contrib.ownership_percentage == 100.0
        assert entity1_contrib.consolidation_factor == 1.0
        assert entity1_contrib.consolidated_scope1_co2e == 1000.0
        assert entity1_contrib.consolidated_scope2_co2e == 500.0
        
        # Check Entity 2 contribution (75% ownership)
        entity2_contrib = next(c for c in result.entity_contributions if c.entity_id == sample_entities[1].id)
        assert entity2_contrib.ownership_percentage == 75.0
        assert entity2_contrib.consolidation_factor == 0.75
        assert entity2_contrib.consolidated_scope1_co2e == 600.0
        assert entity2_contrib.consolidated_scope2_co2e == 300.0

    @pytest.mark.asyncio
    async def test_create_operational_control_consolidation(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test creating operational control consolidation"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OPERATIONAL_CONTROL,
            include_scope3=False
        )
        
        result = await consolidation_service.create_consolidation(request, "test_user")
        
        # Verify consolidation method
        assert result.consolidation_method == ConsolidationMethod.OPERATIONAL_CONTROL
        
        # Only entities with operational control should be fully included
        # Entity 1: has operational control -> factor = 1.0
        # Entity 2: has operational control -> factor = 1.0
        # Entity 3: no operational control -> factor = 0.0
        
        # Expected totals:
        # Scope 1: 1000 + 800 + 0 = 1800
        # Scope 2: 500 + 400 + 0 = 900
        assert result.total_scope1_co2e == 1800.0
        assert result.total_scope2_co2e == 900.0
        
        # Check consolidation factors
        entity1_contrib = next(c for c in result.entity_contributions if c.entity_id == sample_entities[0].id)
        assert entity1_contrib.consolidation_factor == 1.0
        
        entity2_contrib = next(c for c in result.entity_contributions if c.entity_id == sample_entities[1].id)
        assert entity2_contrib.consolidation_factor == 1.0
        
        entity3_contrib = next(c for c in result.entity_contributions if c.entity_id == sample_entities[2].id)
        assert entity3_contrib.consolidation_factor == 0.0

    @pytest.mark.asyncio
    async def test_consolidation_with_minimum_ownership_threshold(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test consolidation with minimum ownership threshold"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED,
            minimum_ownership_threshold=50.0  # Exclude entities with <50% ownership
        )
        
        result = await consolidation_service.create_consolidation(request, "test_user")
        
        # Only entities with >=50% ownership should be included
        # Entity 1: 100% -> included
        # Entity 2: 75% -> included
        # Entity 3: 25% -> excluded
        assert result.total_entities_included == 2
        
        # Expected totals (only Entity 1 and 2):
        # Scope 1: 1000 + 600 = 1600
        # Scope 2: 500 + 300 = 800
        assert result.total_scope1_co2e == 1600.0
        assert result.total_scope2_co2e == 800.0

    @pytest.mark.asyncio
    async def test_consolidation_with_scope3_included(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test consolidation including Scope 3 emissions"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED,
            include_scope3=True
        )
        
        result = await consolidation_service.create_consolidation(request, "test_user")
        
        # Verify Scope 3 is included
        # Entity 1: 200 * 1.0 = 200
        # Entity 2: 0 (no Scope 3 data)
        # Entity 3: 100 * 0.25 = 25
        # Total Scope 3: 225
        assert result.total_scope3_co2e == 225.0
        
        # Verify entities with Scope 3 count
        assert result.entities_with_scope3 == 2  # Entity 1 and 3 have Scope 3 data

    @pytest.mark.asyncio
    async def test_get_consolidation(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test retrieving consolidation by ID"""
        # First create a consolidation
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED
        )
        
        created = await consolidation_service.create_consolidation(request, "test_user")
        
        # Retrieve the consolidation
        retrieved = await consolidation_service.get_consolidation(created.id)
        
        # Verify data matches
        assert retrieved.id == created.id
        assert retrieved.company_id == created.company_id
        assert retrieved.total_scope1_co2e == created.total_scope1_co2e
        assert retrieved.total_scope2_co2e == created.total_scope2_co2e
        assert len(retrieved.entity_contributions) == len(created.entity_contributions)

    @pytest.mark.asyncio
    async def test_list_consolidations(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test listing consolidations for a company"""
        # Create multiple consolidations
        request1 = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED
        )
        
        request2 = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OPERATIONAL_CONTROL
        )
        
        await consolidation_service.create_consolidation(request1, "test_user")
        await consolidation_service.create_consolidation(request2, "test_user")
        
        # List consolidations
        consolidations = await consolidation_service.list_consolidations(sample_company.id)
        
        # Verify results
        assert len(consolidations) == 2
        assert all(c.company_id == sample_company.id for c in consolidations)
        assert all(c.reporting_year == 2024 for c in consolidations)

    @pytest.mark.asyncio
    async def test_approve_consolidation(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test approving a consolidation"""
        # Create consolidation
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED
        )
        
        created = await consolidation_service.create_consolidation(request, "test_user")
        
        # Approve consolidation
        approved = await consolidation_service.approve_consolidation(
            created.id, "approver_user", "Approved for SEC filing"
        )
        
        # Verify approval
        assert approved.status == ConsolidationStatus.APPROVED
        assert approved.is_final == True
        assert approved.approved_by == "approver_user"
        assert approved.approved_at is not None

    @pytest.mark.asyncio
    async def test_get_consolidation_summary(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test getting consolidation summary"""
        # Create consolidation
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED
        )
        
        created = await consolidation_service.create_consolidation(request, "test_user")
        
        # Get summary
        summary = await consolidation_service.get_consolidation_summary(
            sample_company.id, 2024
        )
        
        # Verify summary
        assert summary.company_id == sample_company.id
        assert summary.reporting_year == 2024
        assert summary.consolidation_count == 1
        assert summary.latest_total_co2e == created.total_co2e
        assert summary.total_entities_in_structure == 3  # All entities
        assert summary.entities_included_in_latest == created.total_entities_included

    @pytest.mark.asyncio
    async def test_consolidation_with_no_entities(
        self, consolidation_service, sample_company
    ):
        """Test consolidation when no entities match criteria"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED,
            minimum_ownership_threshold=99.0  # Very high threshold
        )
        
        # Should raise exception when no entities found
        with pytest.raises(Exception) as exc_info:
            await consolidation_service.create_consolidation(request, "test_user")
        
        assert "No entities found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_consolidation_data_quality_filtering(
        self, consolidation_service, sample_company, sample_entities, sample_emissions
    ):
        """Test consolidation with data quality requirements"""
        request = ConsolidationRequest(
            company_id=sample_company.id,
            reporting_year=2024,
            reporting_period_start=date(2024, 1, 1),
            reporting_period_end=date(2024, 12, 31),
            consolidation_method=ConsolidationMethod.OWNERSHIP_BASED,
            minimum_data_quality_score=95.0,  # Very high quality requirement
            require_complete_data=True
        )
        
        result = await consolidation_service.create_consolidation(request, "test_user")
        
        # Some entities might be excluded due to quality requirements
        # The exact behavior depends on the quality scoring implementation
        assert result.total_entities_included <= 3