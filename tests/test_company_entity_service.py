"""
Unit tests for Company Entity Management Service
Tests hierarchical structure, ownership validation, and CRUD operations
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from app.services.company_entity_service import CompanyEntityService
from app.schemas.company_entity import (
    CompanyEntityCreate,
    CompanyEntityUpdate,
    EntityType,
    ConsolidationMethod
)
from app.models.emissions import Company, CompanyEntity


class TestCompanyEntityService:
    """Test company entity management service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sample_company(self):
        """Sample company for testing"""
        return Company(
            id=uuid4(),
            name="Test Company",
            industry="Manufacturing",
            headquarters_country="United States",
            reporting_year=2024
        )
    
    @pytest.fixture
    def sample_entity_data(self, sample_company):
        """Sample entity creation data"""
        return CompanyEntityCreate(
            company_id=sample_company.id,
            name="Manufacturing Division",
            entity_type=EntityType.DIVISION,
            ownership_percentage=100.0,
            consolidation_method=ConsolidationMethod.FULL,
            country="United States",
            primary_activity="Manufacturing",
            operational_control=True
        )
    
    @pytest.fixture
    def sample_entity(self, sample_company):
        """Sample company entity"""
        return CompanyEntity(
            id=uuid4(),
            company_id=sample_company.id,
            name="Manufacturing Division",
            entity_type="division",
            ownership_percentage=100.0,
            operational_control=True,
            consolidation_method="full",
            country="United States",
            primary_activity="Manufacturing",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_create_entity_success(self, mock_db, sample_company, sample_entity_data):
        """Test successful entity creation"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_company
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        
        # Mock audit logger
        with patch('app.services.company_entity_service.AuditLogger') as mock_audit:
            mock_audit_instance = Mock()
            mock_audit_instance.log_event = AsyncMock()
            mock_audit.return_value = mock_audit_instance
            
            service = CompanyEntityService(mock_db)
            
            result = await service.create_entity(sample_entity_data, "user123")
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.flush.assert_called_once()
            mock_db.commit.assert_called_once()
            
            # Verify audit logging
            mock_audit_instance.log_event.assert_called_once()
            
            # Verify result structure
            assert result.name == sample_entity_data.name
            assert result.entity_type == sample_entity_data.entity_type
            assert result.ownership_percentage == sample_entity_data.ownership_percentage
    
    @pytest.mark.asyncio
    async def test_create_entity_with_parent(self, mock_db, sample_company, sample_entity):
        """Test creating entity with parent"""
        # Create child entity data
        child_data = CompanyEntityCreate(
            company_id=sample_company.id,
            name="Production Facility",
            entity_type=EntityType.FACILITY,
            ownership_percentage=75.0,
            consolidation_method=ConsolidationMethod.FULL
        )
        
        # Mock database queries
        def mock_query_filter_first(model):
            if model == Company:
                return Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_company))))
            elif model == CompanyEntity:
                return Mock(filter=Mock(return_value=Mock(first=Mock(return_value=sample_entity))))
        
        mock_db.query.side_effect = mock_query_filter_first
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        
        # Mock ownership validation
        with patch('app.services.company_entity_service.AuditLogger') as mock_audit:
            mock_audit_instance = Mock()
            mock_audit_instance.log_event = AsyncMock()
            mock_audit.return_value = mock_audit_instance
            service = CompanyEntityService(mock_db)
            
            # Mock the validation method
            service._validate_ownership_constraints = Mock()
            service._validate_ownership_constraints.return_value = Mock(is_valid=True)
            
            result = await service.create_entity(child_data, "user123")
            
            # Verify parent relationship
            assert result.name == child_data.name
            assert result.ownership_percentage == child_data.ownership_percentage
    
    @pytest.mark.asyncio
    async def test_create_entity_company_not_found(self, mock_db, sample_entity_data):
        """Test entity creation with non-existent company"""
        # Mock company not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = CompanyEntityService(mock_db)
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await service.create_entity(sample_entity_data, "user123")
    
    @pytest.mark.asyncio
    async def test_get_entity_success(self, mock_db, sample_entity):
        """Test successful entity retrieval"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        
        service = CompanyEntityService(mock_db)
        result = await service.get_entity(sample_entity.id)
        
        assert result.id == sample_entity.id
        assert result.name == sample_entity.name
    
    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, mock_db):
        """Test entity retrieval with non-existent entity"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = CompanyEntityService(mock_db)
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await service.get_entity(uuid4())
    
    @pytest.mark.asyncio
    async def test_update_entity_success(self, mock_db, sample_entity):
        """Test successful entity update"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        mock_db.commit = Mock()
        
        update_data = CompanyEntityUpdate(
            name="Updated Division Name",
            ownership_percentage=90.0
        )
        
        with patch('app.services.company_entity_service.AuditLogger') as mock_audit:
            mock_audit_instance = Mock()
            mock_audit_instance.log_event = AsyncMock()
            mock_audit.return_value = mock_audit_instance
            
            service = CompanyEntityService(mock_db)
            
            result = await service.update_entity(sample_entity.id, update_data, "user123")
            
            # Verify update
            mock_db.commit.assert_called_once()
            assert result.name == update_data.name
            assert result.ownership_percentage == update_data.ownership_percentage
    
    @pytest.mark.asyncio
    async def test_delete_entity_success(self, mock_db, sample_entity):
        """Test successful entity deletion"""
        # Mock entity with no children
        sample_entity.children = []
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        mock_db.commit = Mock()
        
        with patch('app.services.company_entity_service.AuditLogger') as mock_audit:
            mock_audit_instance = Mock()
            mock_audit_instance.log_event = AsyncMock()
            mock_audit.return_value = mock_audit_instance
            
            service = CompanyEntityService(mock_db)
            
            result = await service.delete_entity(sample_entity.id, "user123")
            
            # Verify soft delete
            assert result is True
            assert sample_entity.is_active is False
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_entity_with_children(self, mock_db, sample_entity):
        """Test entity deletion with active children"""
        # Mock entity with active children
        child_entity = Mock()
        child_entity.is_active = True
        sample_entity.children = [child_entity]
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        
        service = CompanyEntityService(mock_db)
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await service.delete_entity(sample_entity.id, "user123")
    
    @pytest.mark.asyncio
    async def test_get_company_entities(self, mock_db, sample_company):
        """Test getting all entities for a company"""
        # Mock entities
        entities = [
            Mock(id=uuid4(), name="Division A", is_active=True),
            Mock(id=uuid4(), name="Division B", is_active=True),
            Mock(id=uuid4(), name="Facility A", is_active=True)
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = entities
        
        service = CompanyEntityService(mock_db)
        result = await service.get_company_entities(sample_company.id)
        
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_get_entity_children_direct(self, mock_db, sample_entity):
        """Test getting direct children of an entity"""
        # Mock direct children
        children = [
            Mock(id=uuid4(), name="Child A", parent_id=sample_entity.id),
            Mock(id=uuid4(), name="Child B", parent_id=sample_entity.id)
        ]
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        mock_db.query.return_value.filter.return_value.all.return_value = children
        
        service = CompanyEntityService(mock_db)
        result = await service.get_entity_children(sample_entity.id, recursive=False)
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_entity_children_recursive(self, mock_db, sample_entity):
        """Test getting all descendants of an entity"""
        # Mock recursive children data
        recursive_data = [
            Mock(id=uuid4(), name="Child A"),
            Mock(id=uuid4(), name="Grandchild A")
        ]
        
        sample_entity.get_all_children = Mock(return_value=recursive_data)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_entity
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        service = CompanyEntityService(mock_db)
        result = await service.get_entity_children(sample_entity.id, recursive=True)
        
        # Verify recursive query was called
        sample_entity.get_all_children.assert_called_once_with(mock_db)
    
    @pytest.mark.asyncio
    async def test_validate_ownership_structure_valid(self, mock_db, sample_company):
        """Test ownership structure validation - valid case"""
        # Mock entities with valid ownership
        entities = [
            Mock(id=uuid4(), ownership_percentage=100.0),
            Mock(id=uuid4(), ownership_percentage=60.0),
            Mock(id=uuid4(), ownership_percentage=40.0)
        ]
        
        service = CompanyEntityService(mock_db)
        service.get_company_entities = AsyncMock(return_value=entities)
        
        result = await service.validate_ownership_structure(sample_company.id)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_ownership_structure_invalid(self, mock_db, sample_company):
        """Test ownership structure validation - invalid case"""
        parent_id = uuid4()
        
        # Mock entities with invalid ownership (exceeds 100%)
        entities = [
            Mock(id=parent_id, ownership_percentage=100.0, name="Parent"),
            Mock(id=uuid4(), ownership_percentage=60.0),
            Mock(id=uuid4(), ownership_percentage=50.0)  # Total = 110%
        ]
        
        service = CompanyEntityService(mock_db)
        service.get_company_entities = AsyncMock(return_value=entities)
        
        result = await service.validate_ownership_structure(sample_company.id)
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        assert "110%" in result.issues[0]  # Should mention the excess percentage
    
    def test_generate_path_root_entity(self, mock_db):
        """Test path generation for root entity"""
        service = CompanyEntityService(mock_db)
        
        path = service._generate_path(None, "Root Entity")
        
        assert path == "Root Entity"
    
    def test_generate_path_child_entity(self, mock_db):
        """Test path generation for child entity"""
        parent = Mock()
        parent.path = "Parent Entity"
        
        service = CompanyEntityService(mock_db)
        
        path = service._generate_path(parent, "Child Entity")
        
        assert path == "Parent Entity > Child Entity"
    
    @pytest.mark.asyncio
    async def test_ownership_validation_constraints_valid(self, mock_db):
        """Test ownership constraints validation - valid case"""
        parent_id = uuid4()
        
        # Mock children with valid total ownership
        children = [
            Mock(ownership_percentage=50.0, is_active=True),
            Mock(ownership_percentage=30.0, is_active=True)
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = children
        
        service = CompanyEntityService(mock_db)
        result = await service._validate_ownership_constraints(parent_id)
        
        assert result.is_valid is True
        assert result.total_entities == 2
    
    @pytest.mark.asyncio
    async def test_ownership_validation_constraints_invalid(self, mock_db):
        """Test ownership constraints validation - invalid case"""
        parent_id = uuid4()
        
        # Mock children with invalid total ownership
        children = [
            Mock(ownership_percentage=60.0, is_active=True),
            Mock(ownership_percentage=50.0, is_active=True)  # Total = 110%
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = children
        
        service = CompanyEntityService(mock_db)
        result = await service._validate_ownership_constraints(parent_id)
        
        assert result.is_valid is False
        assert result.total_entities == 2
        assert "110.0%" in result.message