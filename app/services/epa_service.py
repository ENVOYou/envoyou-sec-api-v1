"""
EPA Data Ingestion Service
Handles fetching, validation, and storage of EPA emission factors
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import httpx
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditLogger
from app.core.config import settings
from app.models.epa_data import ElectricityRegion
from app.models.epa_data import EmissionFactor
from app.models.epa_data import EmissionFactorSource
from app.models.epa_data import EPADataUpdate
from app.models.epa_data import EPADataValidation
from app.models.epa_data import FuelType
from app.schemas.epa_data import EmissionFactorCreate
from app.schemas.epa_data import EmissionFactorResponse
from app.schemas.epa_data import EPADataUpdateRequest
from app.schemas.epa_data import EPADataUpdateResponse
from app.schemas.epa_data import EPAFactorSummary
from app.schemas.epa_data import ValidationResult

logger = logging.getLogger(__name__)


class EPADataIngestionService:
    """Service for ingesting and managing EPA emission factors"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.http_client = httpx.AsyncClient(
            timeout=settings.EPA_REQUEST_TIMEOUT,
            headers={"User-Agent": "ENVOYOU-SEC-API/1.0"},
        )

    async def fetch_latest_factors(self, source: str = "EPA_GHGRP") -> Dict[str, Any]:
        """Fetch latest EPA emission factors from external API"""
        try:
            logger.info(f"Fetching latest EPA factors from {source}")

            # EPA API endpoints (these would be real EPA endpoints in production)
            endpoints = {
                "EPA_GHGRP": f"{settings.EPA_API_BASE_URL}/ghgrp/emission-factors",
                "EPA_EGRID": f"{settings.EPA_API_BASE_URL}/egrid/emission-factors",
                "EPA_AP42": f"{settings.EPA_API_BASE_URL}/ap42/emission-factors",
            }

            if source not in endpoints:
                raise ValueError(f"Unsupported EPA source: {source}")

            # Add API key if available
            headers = {}
            if settings.EPA_API_KEY:
                headers["X-API-Key"] = settings.EPA_API_KEY

            # Fetch data from EPA API
            response = await self.http_client.get(endpoints[source], headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"EPA API error: {response.status_code}",
                )

            data = response.json()

            logger.info(
                f"Successfully fetched {len(data.get('factors', []))} factors from {source}"
            )

            return {
                "source": source,
                "factors": data.get("factors", []),
                "metadata": data.get("metadata", {}),
                "fetch_time": datetime.utcnow().isoformat(),
            }

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching EPA data from {source}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="EPA API timeout"
            )
        except Exception as e:
            logger.error(f"Error fetching EPA data: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"EPA data fetch error: {str(e)}",
            )

    def validate_factor_data(self, factors: List[Dict[str, Any]]) -> ValidationResult:
        """Validate EPA emission factor data"""
        errors = []
        warnings = []
        records_passed = 0
        records_failed = 0

        required_fields = [
            "factor_name",
            "factor_code",
            "category",
            "unit",
            "co2_factor",
            "co2e_factor",
            "source",
            "publication_year",
            "version",
        ]

        for i, factor in enumerate(factors):
            factor_errors = []

            # Check required fields
            for field in required_fields:
                if field not in factor or factor[field] is None:
                    factor_errors.append(f"Missing required field: {field}")

            # Validate data types and ranges
            try:
                if "co2_factor" in factor and factor["co2_factor"] < 0:
                    factor_errors.append("CO2 factor must be non-negative")

                if "co2e_factor" in factor and factor["co2e_factor"] < 0:
                    factor_errors.append("CO2e factor must be non-negative")

                if "publication_year" in factor:
                    year = int(factor["publication_year"])
                    if year < 1990 or year > datetime.now().year + 1:
                        factor_errors.append(f"Invalid publication year: {year}")

                # Validate fuel type if present
                if factor.get("fuel_type"):
                    valid_fuels = [fuel.value for fuel in FuelType]
                    if factor["fuel_type"] not in valid_fuels:
                        warnings.append(f"Unknown fuel type: {factor['fuel_type']}")

                # Validate electricity region if present
                if factor.get("electricity_region"):
                    valid_regions = [region.value for region in ElectricityRegion]
                    if factor["electricity_region"].lower() not in valid_regions:
                        warnings.append(
                            f"Unknown electricity region: {factor['electricity_region']}"
                        )

            except (ValueError, TypeError) as e:
                factor_errors.append(f"Data type error: {str(e)}")

            if factor_errors:
                errors.extend([f"Record {i+1}: {error}" for error in factor_errors])
                records_failed += 1
            else:
                records_passed += 1

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            records_validated=len(factors),
            records_passed=records_passed,
            records_failed=records_failed,
        )

    def cache_with_versioning(
        self, factors: List[Dict[str, Any]], source: str, version: str
    ) -> EPADataUpdateResponse:
        """Cache EPA factors with versioning support"""
        try:
            logger.info(
                f"Caching {len(factors)} factors from {source} version {version}"
            )

            # Create update record
            update_record = EPADataUpdate(
                update_type="FULL", source=source, status="PENDING"
            )
            self.db.add(update_record)
            self.db.flush()  # Get the ID

            start_time = datetime.utcnow()
            records_added = 0
            records_updated = 0
            records_deprecated = 0

            # Validate data first
            validation_result = self.validate_factor_data(factors)

            if not validation_result.is_valid:
                update_record.status = "FAILED"
                update_record.validation_passed = False
                update_record.validation_errors = validation_result.errors
                self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {validation_result.errors}",
                )

            # Mark existing factors as deprecated for this source
            existing_factors = (
                self.db.query(EmissionFactor)
                .filter(
                    and_(
                        EmissionFactor.source == source,
                        EmissionFactor.is_current == True,
                    )
                )
                .all()
            )

            for factor in existing_factors:
                factor.is_current = False
                factor.valid_to = datetime.utcnow()
                records_deprecated += 1

            # Add new factors
            for factor_data in factors:
                # Check if factor already exists with same code and version
                existing = (
                    self.db.query(EmissionFactor)
                    .filter(
                        and_(
                            EmissionFactor.factor_code == factor_data["factor_code"],
                            EmissionFactor.version == factor_data["version"],
                        )
                    )
                    .first()
                )

                if existing:
                    # Update existing factor
                    for key, value in factor_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.is_current = True
                    existing.valid_to = None
                    records_updated += 1
                else:
                    # Create new factor
                    factor_data["is_current"] = True
                    if "valid_from" not in factor_data:
                        factor_data["valid_from"] = datetime.utcnow()
                    new_factor = EmissionFactor(**factor_data)
                    self.db.add(new_factor)
                    records_added += 1

            # Update the update record
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            update_record.status = "SUCCESS"
            update_record.records_added = records_added
            update_record.records_updated = records_updated
            update_record.records_deprecated = records_deprecated
            update_record.processing_time_seconds = processing_time
            update_record.validation_passed = True

            self.db.commit()

            logger.info(
                f"Successfully cached EPA factors: {records_added} added, {records_updated} updated, {records_deprecated} deprecated"
            )

            return EPADataUpdateResponse(
                id=str(update_record.id),
                update_type=update_record.update_type,
                source=update_record.source,
                status=update_record.status,
                records_added=records_added,
                records_updated=records_updated,
                records_deprecated=records_deprecated,
                processing_time_seconds=processing_time,
                validation_passed=True,
                created_at=update_record.created_at,
            )

        except Exception as e:
            logger.error(f"Error caching EPA factors: {str(e)}")
            self.db.rollback()

            if "update_record" in locals():
                update_record.status = "FAILED"
                update_record.error_message = str(e)
                self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cache EPA factors: {str(e)}",
            )

    def get_current_factors(
        self,
        category: Optional[str] = None,
        fuel_type: Optional[str] = None,
        electricity_region: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[EmissionFactorResponse]:
        """Get current EPA emission factors with optional filtering"""
        try:
            query = self.db.query(EmissionFactor).filter(
                EmissionFactor.is_current == True
            )

            if category:
                query = query.filter(EmissionFactor.category == category)

            if fuel_type:
                query = query.filter(EmissionFactor.fuel_type == fuel_type)

            if electricity_region:
                query = query.filter(
                    EmissionFactor.electricity_region == electricity_region
                )

            if source:
                query = query.filter(EmissionFactor.source == source)

            factors = query.order_by(EmissionFactor.factor_name).all()

            return [EmissionFactorResponse.from_orm(factor) for factor in factors]

        except Exception as e:
            logger.error(f"Error retrieving emission factors: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve emission factors: {str(e)}",
            )

    def get_factor_by_code(
        self, factor_code: str, version: Optional[str] = None
    ) -> Optional[EmissionFactorResponse]:
        """Get specific emission factor by code and version"""
        try:
            query = self.db.query(EmissionFactor).filter(
                EmissionFactor.factor_code == factor_code
            )

            if version:
                query = query.filter(EmissionFactor.version == version)
            else:
                query = query.filter(EmissionFactor.is_current == True)

            factor = query.first()

            if factor:
                return EmissionFactorResponse.from_orm(factor)

            return None

        except Exception as e:
            logger.error(f"Error retrieving emission factor: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve emission factor: {str(e)}",
            )

    def get_factors_summary(self) -> EPAFactorSummary:
        """Get summary statistics of EPA factors"""
        try:
            total_factors = self.db.query(EmissionFactor).count()
            current_factors = (
                self.db.query(EmissionFactor)
                .filter(EmissionFactor.is_current == True)
                .count()
            )
            deprecated_factors = total_factors - current_factors

            # Category breakdown
            from sqlalchemy import func

            category_query = (
                self.db.query(EmissionFactor.category, func.count(EmissionFactor.id))
                .filter(EmissionFactor.is_current == True)
                .group_by(EmissionFactor.category)
                .all()
            )

            categories = {category: count for category, count in category_query}

            # Source breakdown
            source_query = (
                self.db.query(EmissionFactor.source, func.count(EmissionFactor.id))
                .filter(EmissionFactor.is_current == True)
                .group_by(EmissionFactor.source)
                .all()
            )

            sources = {source: count for source, count in source_query}

            # Latest update
            latest_update = (
                self.db.query(EPADataUpdate)
                .filter(EPADataUpdate.status == "SUCCESS")
                .order_by(desc(EPADataUpdate.created_at))
                .first()
            )

            # Oldest factor
            oldest_factor = (
                self.db.query(EmissionFactor)
                .filter(EmissionFactor.is_current == True)
                .order_by(EmissionFactor.valid_from)
                .first()
            )

            return EPAFactorSummary(
                total_factors=total_factors,
                current_factors=current_factors,
                deprecated_factors=deprecated_factors,
                categories=categories,
                sources=sources,
                latest_update=latest_update.created_at if latest_update else None,
                oldest_factor=oldest_factor.valid_from if oldest_factor else None,
            )

        except Exception as e:
            logger.error(f"Error getting factors summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get factors summary: {str(e)}",
            )

    async def setup_auto_refresh_schedule(self, interval_hours: int = 24):
        """Set up automatic refresh of EPA data"""
        logger.info(f"Setting up auto-refresh schedule every {interval_hours} hours")

        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)  # Convert to seconds

                logger.info("Starting scheduled EPA data refresh")

                # Fetch and update data from all sources
                sources = ["EPA_GHGRP", "EPA_EGRID"]

                for source in sources:
                    try:
                        data = await self.fetch_latest_factors(source)
                        if data["factors"]:
                            self.cache_with_versioning(
                                data["factors"],
                                source,
                                data["metadata"].get("version", "auto"),
                            )
                    except Exception as e:
                        logger.error(f"Failed to refresh {source}: {str(e)}")

                logger.info("Completed scheduled EPA data refresh")

            except Exception as e:
                logger.error(f"Error in auto-refresh schedule: {str(e)}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
