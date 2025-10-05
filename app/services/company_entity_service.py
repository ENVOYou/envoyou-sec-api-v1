"""
Company Entity Management Service
Handles hierarchical company structure, ownership, and entity relationships
"""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditLogger
from app.models.emissions import Company, CompanyEntity
from app.schemas.company_entity import (
    CompanyEntityCreate,
    CompanyEntityResponse,
    CompanyEntityUpdate,
    EntityHierarchyResponse,
    OwnershipValidationResult,
)

logger = logging.getLogger(__name__)


class CompanyEntityService:
    """Service for managing company entities and hierarchical structures"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    async def create_entity(
        self, entity_data: CompanyEntityCreate, user_id: str
    ) -> CompanyEntityResponse:
        """Create a new company entity"""
        try:
            # Validate company exists
            company = self._get_company(entity_data.company_id)
            
            # Validate parent entity if specified
            parent_entity = None
            if entity_data.parent_id:
                parent_entity = self._get_entity(entity_data.parent_id)
                if parent_entity.company_id != entity_data.company_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Parent entity must belong to the same company"
                    )

            # Calculate level and path
            level = 0 if not parent_entity else parent_entity.level + 1
            path = self._generate_path(parent_entity, entity_data.name)

            # Create entity
            entity = CompanyEntity(
                id=uuid4(),
                company_id=entity_data.company_id,
                name=entity_data.name,
                entity_type=entity_data.entity_type,
                parent_id=entity_data.parent_id,
                level=level,
                path=path,
                ownership_percentage=entity_data.ownership_percentage,
                consolidation_method=entity_data.consolidation_method,
                country=entity_data.country,
                state_province=entity_data.state_province,
                city=entity_data.city,
                sector=entity_data.sector,
                primary_activity=entity_data.primary_activity,
                operational_control=entity_data.operational_control,
                is_active=True
            )

            self.db.add(entity)
            self.db.flush()  # Get ID before validation

            # Validate ownership constraints
            if parent_entity:
                validation_result = await self._validate_ownership_constraints(parent_entity.id)
                if not validation_result.is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ownership validation failed: {validation_result.message}"
                    )

            self.db.commit()

            # Log entity creation
            await self.audit_logger.log_event(
                event_type="ENTITY_CREATED",
                user_id=user_id,
                details={
                    "entity_id": str(entity.id),
                    "entity_name": entity.name,
                    "company_id": str(entity.company_id),
                    "parent_id": str(entity.parent_id) if entity.parent_id else None,
                    "ownership_percentage": entity.ownership_percentage
                }
            )

            return CompanyEntityResponse.from_orm(entity)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating entity: {str(e)}")
            raise

    async def get_entity(self, entity_id: UUID) -> CompanyEntityResponse:
        """Get entity by ID"""
        entity = self._get_entity(entity_id)
        return CompanyEntityResponse.from_orm(entity)

    async def update_entity(
        self, entity_id: UUID, entity_data: CompanyEntityUpdate, user_id: str
    ) -> CompanyEntityResponse:
        """Update entity information"""
        try:
            entity = self._get_entity(entity_id)
            original_data = {
                "name": entity.name,
                "ownership_percentage": entity.ownership_percentage,
                "parent_id": str(entity.parent_id) if entity.parent_id else None
            }

            # Update fields
            for field, value in entity_data.dict(exclude_unset=True).items():
                if hasattr(entity, field):
                    setattr(entity, field, value)

            # Recalculate path if name changed
            if entity_data.name and entity_data.name != original_data["name"]:
                entity.path = self._generate_path(entity.parent, entity.name)

            # Validate ownership if changed
            if (entity_data.ownership_percentage and 
                entity_data.ownership_percentage != original_data["ownership_percentage"]):
                if entity.parent_id:
                    validation_result = await self._validate_ownership_constraints(entity.parent_id)
                    if not validation_result.is_valid:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Ownership validation failed: {validation_result.message}"
                        )

            self.db.commit()

            # Log entity update
            await self.audit_logger.log_event(
                event_type="ENTITY_UPDATED",
                user_id=user_id,
                details={
                    "entity_id": str(entity.id),
                    "original_data": original_data,
                    "updated_fields": entity_data.dict(exclude_unset=True)
                }
            )

            return CompanyEntityResponse.from_orm(entity)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating entity {entity_id}: {str(e)}")
            raise

    async def delete_entity(self, entity_id: UUID, user_id: str) -> bool:
        """Delete entity (soft delete)"""
        try:
            entity = self._get_entity(entity_id)

            # Check if entity has children
            if entity.children:
                active_children = [child for child in entity.children if child.is_active]
                if active_children:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot delete entity with active children. Delete or reassign children first."
                    )

            # Soft delete
            entity.is_active = False
            self.db.commit()

            # Log entity deletion
            await self.audit_logger.log_event(
                event_type="ENTITY_DELETED",
                user_id=user_id,
                details={
                    "entity_id": str(entity.id),
                    "entity_name": entity.name,
                    "company_id": str(entity.company_id)
                }
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting entity {entity_id}: {str(e)}")
            raise

    async def get_company_entities(
        self, company_id: UUID, include_inactive: bool = False
    ) -> List[CompanyEntityResponse]:
        """Get all entities for a company"""
        query = self.db.query(CompanyEntity).filter(CompanyEntity.company_id == company_id)
        
        if not include_inactive:
            query = query.filter(CompanyEntity.is_active == True)
            
        entities = query.order_by(CompanyEntity.level, CompanyEntity.name).all()
        return [CompanyEntityResponse.from_orm(entity) for entity in entities]

    async def get_entity_hierarchy(self, company_id: UUID) -> EntityHierarchyResponse:
        """Get complete entity hierarchy for a company"""
        entities = await self.get_company_entities(company_id)
        
        # Build hierarchy tree
        entity_map = {str(entity.id): entity for entity in entities}
        root_entities = []
        
        for entity in entities:
            if entity.parent_id is None:
                root_entities.append(self._build_hierarchy_node(entity, entity_map))
        
        return EntityHierarchyResponse(
            company_id=company_id,
            total_entities=len(entities),
            hierarchy=root_entities
        )

    async def get_entity_children(
        self, entity_id: UUID, recursive: bool = False
    ) -> List[CompanyEntityResponse]:
        """Get children of an entity"""
        entity = self._get_entity(entity_id)
        
        if recursive:
            # Use the model's recursive method
            children_data = entity.get_all_children(self.db)
            children_ids = [row.id for row in children_data]
            
            if children_ids:
                children = self.db.query(CompanyEntity).filter(
                    CompanyEntity.id.in_(children_ids),
                    CompanyEntity.is_active == True
                ).all()
            else:
                children = []
        else:
            children = self.db.query(CompanyEntity).filter(
                CompanyEntity.parent_id == entity_id,
                CompanyEntity.is_active == True
            ).all()

        return [CompanyEntityResponse.from_orm(child) for child in children]

    async def validate_ownership_structure(
        self, company_id: UUID
    ) -> OwnershipValidationResult:
        """Validate ownership structure for entire company"""
        try:
            entities = await self.get_company_entities(company_id)
            issues = []
            
            # Group entities by parent
            parent_groups = {}
            for entity in entities:
                parent_key = str(entity.parent_id) if entity.parent_id else "root"
                if parent_key not in parent_groups:
                    parent_groups[parent_key] = []
                parent_groups[parent_key].append(entity)
            
            # Validate each parent's children ownership
            for parent_key, children in parent_groups.items():
                if parent_key == "root":
                    continue
                    
                total_ownership = sum(child.ownership_percentage for child in children)
                if total_ownership > 100.0:
                    parent_name = next(
                        (e.name for e in entities if str(e.id) == parent_key), 
                        "Unknown"
                    )
                    issues.append(
                        f"Parent '{parent_name}' has children with total ownership "
                        f"{total_ownership}% (exceeds 100%)"
                    )
            
            return OwnershipValidationResult(
                is_valid=len(issues) == 0,
                total_entities=len(entities),
                issues=issues,
                message="Ownership structure is valid" if len(issues) == 0 else "Ownership validation failed"
            )

        except Exception as e:
            logger.error(f"Error validating ownership structure: {str(e)}")
            raise

    def _get_company(self, company_id: UUID) -> Company:
        """Get company by ID or raise 404"""
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found"
            )
        return company

    def _get_entity(self, entity_id: UUID) -> CompanyEntity:
        """Get entity by ID or raise 404"""
        entity = self.db.query(CompanyEntity).filter(
            CompanyEntity.id == entity_id,
            CompanyEntity.is_active == True
        ).first()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_id} not found"
            )
        return entity

    def _generate_path(self, parent_entity: Optional[CompanyEntity], entity_name: str) -> str:
        """Generate materialized path for entity"""
        if not parent_entity:
            return entity_name
        return f"{parent_entity.path} > {entity_name}"

    async def _validate_ownership_constraints(self, parent_id: UUID) -> OwnershipValidationResult:
        """Validate ownership constraints for a parent entity"""
        children = self.db.query(CompanyEntity).filter(
            CompanyEntity.parent_id == parent_id,
            CompanyEntity.is_active == True
        ).all()
        
        total_ownership = sum(child.ownership_percentage for child in children)
        
        if total_ownership > 100.0:
            return OwnershipValidationResult(
                is_valid=False,
                total_entities=len(children),
                issues=[f"Total ownership {total_ownership}% exceeds 100%"],
                message=f"Children ownership totals {total_ownership}%, which exceeds 100%"
            )
        
        return OwnershipValidationResult(
            is_valid=True,
            total_entities=len(children),
            issues=[],
            message="Ownership constraints are valid"
        )

    def _build_hierarchy_node(self, entity: CompanyEntityResponse, entity_map: Dict[str, CompanyEntityResponse]) -> Dict:
        """Build hierarchy node with children"""
        node = {
            "entity": entity,
            "children": []
        }
        
        # Find children
        for other_entity in entity_map.values():
            if other_entity.parent_id and str(other_entity.parent_id) == str(entity.id):
                child_node = self._build_hierarchy_node(other_entity, entity_map)
                node["children"].append(child_node)
        
        return node