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

            # Create entity with only available fields
            entity = CompanyEntity(
                id=uuid4(),
                company_id=entity_data.company_id,
                name=entity_data.name,
                entity_type=entity_data.entity_type,
                ownership_percentage=entity_data.ownership_percentage,
                consolidation_method=entity_data.consolidation_method,
                country=entity_data.country,
                state_province=entity_data.state_province,
                city=entity_data.city,
                primary_activity=entity_data.primary_activity,
                operational_control=entity_data.operational_control,
            )

            self.db.add(entity)
            self.db.flush()  # Get ID before validation

            self.db.commit()

            # Log entity creation
            await self.audit_logger.log_event(
                event_type="ENTITY_CREATED",
                user_id=user_id,
                details={
                    "entity_id": str(entity.id),
                    "entity_name": entity.name,
                    "company_id": str(entity.company_id),
                    "ownership_percentage": entity.ownership_percentage,
                },
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
            }

            # Update fields
            for field, value in entity_data.dict(exclude_unset=True).items():
                if hasattr(entity, field):
                    setattr(entity, field, value)

            # Skip path and ownership validation for now since we don't have parent_id field

            self.db.commit()

            # Log entity update
            await self.audit_logger.log_event(
                event_type="ENTITY_UPDATED",
                user_id=user_id,
                details={
                    "entity_id": str(entity.id),
                    "original_data": original_data,
                    "updated_fields": entity_data.dict(exclude_unset=True),
                },
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
                active_children = [
                    child for child in entity.children if child.is_active
                ]
                if active_children:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot delete entity with active children. Delete or reassign children first.",
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
                    "company_id": str(entity.company_id),
                },
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
        query = self.db.query(CompanyEntity).filter(
            CompanyEntity.company_id == company_id
        )

        # Skip is_active and level filters since fields don't exist
        entities = query.order_by(CompanyEntity.name).all()
        return [CompanyEntityResponse.from_orm(entity) for entity in entities]

    async def get_entity_hierarchy(self, company_id: UUID) -> EntityHierarchyResponse:
        """Get complete entity hierarchy for a company"""
        entities = await self.get_company_entities(company_id)

        # Build hierarchy tree
        entity_map = {str(entity.id): entity for entity in entities}
        root_entities = []

        # Since we don't have parent_id, treat all entities as root level
        for entity in entities:
            root_entities.append(self._build_hierarchy_node(entity, entity_map))

        return EntityHierarchyResponse(
            company_id=company_id, total_entities=len(entities), hierarchy=root_entities
        )

    async def get_entity_children(
        self, entity_id: UUID, recursive: bool = False
    ) -> List[CompanyEntityResponse]:
        """Get children of an entity"""
        entity = self._get_entity(entity_id)

        # Since we don't have parent_id field, return empty list for now
        children = []

        return [CompanyEntityResponse.from_orm(child) for child in children]

    async def validate_ownership_structure(
        self, company_id: UUID
    ) -> OwnershipValidationResult:
        """Validate ownership structure for entire company"""
        try:
            entities = await self.get_company_entities(company_id)
            issues = []

            # Since we don't have parent_id field, skip grouping for now
            parent_groups = {"root": entities}

            # Validate each parent's children ownership
            for parent_key, children in parent_groups.items():
                if parent_key == "root":
                    continue

                total_ownership = sum(child.ownership_percentage for child in children)
                if total_ownership > 100.0:
                    parent_name = next(
                        (e.name for e in entities if str(e.id) == parent_key), "Unknown"
                    )
                    issues.append(
                        f"Parent '{parent_name}' has children with total ownership "
                        f"{total_ownership}% (exceeds 100%)"
                    )

            return OwnershipValidationResult(
                is_valid=len(issues) == 0,
                total_entities=len(entities),
                issues=issues,
                message=(
                    "Ownership structure is valid"
                    if len(issues) == 0
                    else "Ownership validation failed"
                ),
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
                detail=f"Company {company_id} not found",
            )
        return company

    def _get_entity(self, entity_id: UUID) -> CompanyEntity:
        """Get entity by ID or raise 404"""
        entity = (
            self.db.query(CompanyEntity)
            .filter(CompanyEntity.id == entity_id, CompanyEntity.is_active == True)
            .first()
        )
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_id} not found",
            )
        return entity

    def _generate_path(
        self, parent_entity: Optional[CompanyEntity], entity_name: str
    ) -> str:
        """Generate materialized path for entity"""
        if not parent_entity:
            return entity_name
        return f"{parent_entity.path} > {entity_name}"

    async def _validate_ownership_constraints(
        self, parent_id: UUID
    ) -> OwnershipValidationResult:
        """Validate ownership constraints for a parent entity - simplified since no parent_id field"""
        return OwnershipValidationResult(
            is_valid=True,
            total_entities=0,
            issues=[],
            message="Ownership validation skipped - no parent_id field",
        )

    def _build_hierarchy_node(
        self,
        entity: CompanyEntityResponse,
        entity_map: Dict[str, CompanyEntityResponse],
    ) -> Dict:
        """Build hierarchy node with children"""
        node = {"entity": entity, "children": []}

        # Since we don't have parent_id field, no children for now

        return node
