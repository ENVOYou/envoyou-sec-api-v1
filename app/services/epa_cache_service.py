"""
Enhanced EPA Service with Redis Caching and Automated Refresh
Combines database storage with Redis caching for optimal performance
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.epa_data import EmissionFactorResponse, EPAFactorSummary
from app.services.epa_service import EPADataIngestionService
from app.services.redis_cache import EPACacheService

logger = logging.getLogger(__name__)


class EPACachedService:
    """EPA service with Redis caching and automated refresh capabilities"""

    def __init__(self, db: Session):
        self.db = db
        self.epa_service = EPADataIngestionService(db)
        self.cache_service = EPACacheService()
        self.refresh_interval_hours = settings.EPA_DATA_CACHE_HOURS
        self._refresh_task = None

    async def get_emission_factors(
        self,
        source: str = "EPA_GHGRP",
        category: Optional[str] = None,
        fuel_type: Optional[str] = None,
        electricity_region: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[EmissionFactorResponse]:
        """Get emission factors with cache-first strategy"""
        try:
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_factors = self.cache_service.get_emission_factors(
                    source=source, category=category, fuel_type=fuel_type
                )

                if cached_factors:
                    logger.debug(
                        f"Returning {len(cached_factors)} cached factors for {source}"
                    )
                    return [
                        EmissionFactorResponse(**factor) for factor in cached_factors
                    ]

            # Cache miss or force refresh - get from database
            logger.info(f"Cache miss for {source}, fetching from database")

            db_factors = self.epa_service.get_current_factors(
                category=category,
                fuel_type=fuel_type,
                electricity_region=electricity_region,
                source=source,
            )

            # Cache the results
            if db_factors:
                factor_dicts = [factor.dict() for factor in db_factors]
                self.cache_service.cache_emission_factors(
                    factors=factor_dicts, source=source, version="current"
                )
                logger.info(f"Cached {len(db_factors)} factors for {source}")

            return db_factors

        except Exception as e:
            logger.error(f"Error getting emission factors: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get emission factors: {str(e)}",
            )

    async def get_emission_factor_by_code(
        self,
        factor_code: str,
        version: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[EmissionFactorResponse]:
        """Get specific emission factor by code with caching"""
        try:
            # Check cache first
            if not force_refresh:
                cached_factor = self.cache_service.get_emission_factor_by_code(
                    factor_code=factor_code, version=version
                )

                if cached_factor:
                    logger.debug(f"Returning cached factor: {factor_code}")
                    return EmissionFactorResponse(**cached_factor)

            # Cache miss - get from database
            db_factor = self.epa_service.get_factor_by_code(factor_code, version)

            if db_factor:
                # Cache the result
                self.cache_service.cache.set_with_ttl(
                    self.cache_service._get_cache_key(
                        "factor", factor_code, version=version or "current"
                    ),
                    db_factor.dict(),
                    self.cache_service.default_ttl,
                )

            return db_factor

        except Exception as e:
            logger.error(f"Error getting emission factor by code: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get emission factor: {str(e)}",
            )

    async def refresh_epa_data(
        self, sources: Optional[List[str]] = None, force_update: bool = False
    ) -> Dict[str, Any]:
        """Refresh EPA data from external sources"""
        if sources is None:
            sources = ["EPA_GHGRP", "EPA_EGRID"]

        results = {}

        for source in sources:
            try:
                logger.info(f"Refreshing EPA data for source: {source}")

                # Check if cache is still fresh (unless force update)
                if not force_update and self.cache_service.is_cache_fresh(source):
                    logger.info(f"Cache for {source} is still fresh, skipping refresh")
                    results[source] = {"status": "skipped", "reason": "cache_fresh"}
                    continue

                # Fetch latest data from EPA API
                try:
                    epa_data = await self.epa_service.fetch_latest_factors(source)

                    if not epa_data.get("factors"):
                        logger.warning(f"No factors received from {source}")
                        results[source] = {"status": "warning", "reason": "no_factors"}
                        continue

                    # Update database
                    update_response = self.epa_service.cache_with_versioning(
                        factors=epa_data["factors"],
                        source=source,
                        version=epa_data["metadata"].get("version", "auto"),
                    )

                    # Invalidate old cache
                    self.cache_service.invalidate_source_cache(source)

                    # Cache new data
                    self.cache_service.cache_emission_factors(
                        factors=epa_data["factors"],
                        source=source,
                        version=epa_data["metadata"].get("version", "current"),
                    )

                    results[source] = {
                        "status": "success",
                        "records_added": update_response.records_added,
                        "records_updated": update_response.records_updated,
                        "records_deprecated": update_response.records_deprecated,
                        "processing_time": update_response.processing_time_seconds,
                    }

                    logger.info(
                        f"Successfully refreshed {source}: {update_response.records_added} added, {update_response.records_updated} updated"
                    )

                except Exception as api_error:
                    logger.error(f"Failed to fetch from {source}: {str(api_error)}")
                    results[source] = {"status": "error", "error": str(api_error)}

                    # Try to use fallback mechanism
                    await self._handle_api_fallback(source)

            except Exception as e:
                logger.error(f"Error refreshing {source}: {str(e)}")
                results[source] = {"status": "error", "error": str(e)}

        return {
            "refresh_time": datetime.utcnow().isoformat(),
            "sources": results,
            "overall_status": (
                "success"
                if all(
                    r.get("status") in ["success", "skipped"] for r in results.values()
                )
                else "partial_failure"
            ),
        }

    async def _handle_api_fallback(self, source: str):
        """Handle fallback when EPA API is unavailable"""
        try:
            logger.info(f"Attempting fallback for {source}")

            # Check if we have recent cached data
            metadata = self.cache_service.get_cache_metadata(source)
            if metadata:
                cached_at = datetime.fromisoformat(metadata["cached_at"])
                age_hours = (datetime.utcnow() - cached_at).total_seconds() / 3600

                # If cached data is less than 7 days old, extend TTL
                if age_hours < 168:  # 7 days
                    cache_key = self.cache_service._get_cache_key(
                        "factors", source, version="current"
                    )
                    extended_ttl = 24 * 3600  # Extend by 24 hours

                    cached_factors = self.cache_service.cache.get(cache_key)
                    if cached_factors:
                        self.cache_service.cache.set_with_ttl(
                            cache_key, cached_factors, extended_ttl
                        )
                        logger.info(
                            f"Extended cache TTL for {source} by 24 hours due to API unavailability"
                        )
                        return

            # If no recent cache, try to get from database
            db_factors = self.epa_service.get_current_factors(source=source)
            if db_factors:
                factor_dicts = [factor.dict() for factor in db_factors]
                self.cache_service.cache_emission_factors(
                    factors=factor_dicts, source=source, version="fallback"
                )
                logger.info(f"Used database fallback for {source}")

        except Exception as e:
            logger.error(f"Fallback failed for {source}: {str(e)}")

    async def start_auto_refresh(self):
        """Start automated refresh background task"""
        if self._refresh_task and not self._refresh_task.done():
            logger.warning("Auto-refresh task already running")
            return

        logger.info(
            f"Starting auto-refresh task (interval: {self.refresh_interval_hours} hours)"
        )
        self._refresh_task = asyncio.create_task(self._auto_refresh_loop())

    async def stop_auto_refresh(self):
        """Stop automated refresh background task"""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            logger.info("Auto-refresh task stopped")

    async def _auto_refresh_loop(self):
        """Background task for automated EPA data refresh"""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval_hours * 3600)

                logger.info("Starting scheduled EPA data refresh")
                refresh_results = await self.refresh_epa_data()

                if refresh_results["overall_status"] == "success":
                    logger.info("Scheduled EPA data refresh completed successfully")
                else:
                    logger.warning(
                        f"Scheduled EPA data refresh completed with issues: {refresh_results}"
                    )

            except asyncio.CancelledError:
                logger.info("Auto-refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-refresh loop: {str(e)}")
                # Continue the loop even if one iteration fails
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    def get_cache_status(self) -> Dict[str, Any]:
        """Get comprehensive cache and service status"""
        try:
            cache_status = self.cache_service.get_cache_status()

            # Add service-specific information
            service_status = {
                "auto_refresh_enabled": self._refresh_task is not None
                and not self._refresh_task.done(),
                "refresh_interval_hours": self.refresh_interval_hours,
                "database_connected": True,  # Assume connected if we got this far
                "last_refresh": None,  # Could be enhanced to track this
            }

            return {
                "cache": cache_status,
                "service": service_status,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting cache status: {str(e)}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def __aenter__(self):
        await self.epa_service.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_auto_refresh()
        await self.epa_service.__aexit__(exc_type, exc_val, exc_tb)
