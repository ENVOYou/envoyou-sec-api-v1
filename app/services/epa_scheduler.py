"""
EPA Data Refresh Scheduler
Automated scheduling for EPA data updates with fallback mechanisms
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.epa_data import EPADataUpdate
from app.services.cache_service import cache_service
from app.services.epa_service import EPADataIngestionService

logger = logging.getLogger(__name__)


class EPADataScheduler:
    """Scheduler for automated EPA data refresh"""

    def __init__(self):
        self.is_running = False
        self.refresh_interval_hours = settings.EPA_DATA_CACHE_HOURS
        self.max_retries = 3
        self.retry_delay_minutes = 30

    async def start_scheduler(self):
        """Start the EPA data refresh scheduler"""
        if self.is_running:
            logger.warning("EPA scheduler is already running")
            return

        self.is_running = True
        logger.info(
            f"Starting EPA data scheduler with {self.refresh_interval_hours}h interval"
        )

        # Start the scheduler loop
        asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """Stop the EPA data refresh scheduler"""
        self.is_running = False
        logger.info("EPA data scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                # Wait for the next refresh interval
                await asyncio.sleep(self.refresh_interval_hours * 3600)

                if not self.is_running:
                    break

                logger.info("Starting scheduled EPA data refresh")
                await self._perform_scheduled_refresh()

            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                # Continue running even if one iteration fails
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    async def _perform_scheduled_refresh(self):
        """Perform scheduled EPA data refresh"""
        db = SessionLocal()

        try:
            async with EPADataIngestionService(db) as epa_service:
                # EPA data sources to refresh
                sources = ["EPA_GHGRP", "EPA_EGRID"]

                for source in sources:
                    await self._refresh_source_with_retry(epa_service, source)

                # Update cache staleness indicators
                await self._update_cache_staleness()

                logger.info("Completed scheduled EPA data refresh")

        except Exception as e:
            logger.error(f"Error in scheduled refresh: {str(e)}")
        finally:
            db.close()

    async def _refresh_source_with_retry(
        self, epa_service: EPADataIngestionService, source: str
    ):
        """Refresh EPA data source with retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Refreshing {source} (attempt {attempt + 1}/{self.max_retries})"
                )

                # Fetch latest data
                data = await epa_service.fetch_latest_factors(source)

                if data and data.get("factors"):
                    # Cache the data with versioning
                    version = data.get("metadata", {}).get(
                        "version", f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                    )

                    update_result = epa_service.cache_with_versioning(
                        data["factors"], source, version
                    )

                    # Update Redis cache
                    await self._update_redis_cache(source, data["factors"])

                    # Clear staleness indicator
                    cache_service.set_cache_staleness_indicator(
                        f"epa_factors_{source.lower()}", False
                    )

                    logger.info(
                        f"Successfully refreshed {source}: {update_result.records_added} added, {update_result.records_updated} updated"
                    )
                    break  # Success, exit retry loop
                else:
                    logger.warning(f"No data received from {source}")

            except Exception as e:
                logger.error(
                    f"Failed to refresh {source} (attempt {attempt + 1}): {str(e)}"
                )

                if attempt < self.max_retries - 1:
                    # Wait before retrying
                    await asyncio.sleep(self.retry_delay_minutes * 60)
                else:
                    # Mark cache as stale after all retries failed
                    cache_service.set_cache_staleness_indicator(
                        f"epa_factors_{source.lower()}", True
                    )
                    logger.error(
                        f"All retry attempts failed for {source}, marking cache as stale"
                    )

    async def _update_redis_cache(self, source: str, factors: List[Dict[str, Any]]):
        """Update Redis cache with fresh EPA data"""
        try:
            # Group factors by category for efficient caching
            categories = {}
            for factor in factors:
                category = factor.get("category", "unknown")
                if category not in categories:
                    categories[category] = []
                categories[category].append(factor)

            # Cache each category
            for category, category_factors in categories.items():
                cache_key = f"{source.lower()}_{category}"
                success = cache_service.set_epa_factors(
                    cache_key, category_factors, settings.EPA_DATA_CACHE_HOURS
                )

                if success:
                    logger.debug(
                        f"Updated Redis cache for {cache_key}: {len(category_factors)} factors"
                    )

            # Also cache individual factors by code for quick lookup
            for factor in factors:
                factor_code = factor.get("factor_code")
                if factor_code:
                    cache_service.set_factor_by_code(
                        factor_code, factor, settings.EPA_DATA_CACHE_HOURS
                    )

        except Exception as e:
            logger.error(f"Error updating Redis cache for {source}: {str(e)}")

    async def _update_cache_staleness(self):
        """Update cache staleness indicators based on last successful update"""
        db = SessionLocal()

        try:
            # Check when each source was last successfully updated
            sources = ["EPA_GHGRP", "EPA_EGRID"]
            staleness_threshold = timedelta(
                hours=self.refresh_interval_hours * 2
            )  # 2x the refresh interval

            for source in sources:
                last_update = (
                    db.query(EPADataUpdate)
                    .filter(
                        EPADataUpdate.source == source,
                        EPADataUpdate.status == "SUCCESS",
                    )
                    .order_by(EPADataUpdate.created_at.desc())
                    .first()
                )

                if last_update:
                    time_since_update = datetime.utcnow() - last_update.created_at
                    is_stale = time_since_update > staleness_threshold

                    cache_service.set_cache_staleness_indicator(
                        f"epa_factors_{source.lower()}", is_stale
                    )

                    if is_stale:
                        logger.warning(
                            f"{source} data is stale (last update: {last_update.created_at})"
                        )
                else:
                    # No successful updates found, mark as stale
                    cache_service.set_cache_staleness_indicator(
                        f"epa_factors_{source.lower()}", True
                    )
                    logger.warning(
                        f"No successful updates found for {source}, marking as stale"
                    )

        except Exception as e:
            logger.error(f"Error updating cache staleness: {str(e)}")
        finally:
            db.close()

    async def force_refresh(self, source: str = None) -> Dict[str, Any]:
        """Force immediate refresh of EPA data"""
        logger.info(f"Force refresh requested for {source or 'all sources'}")

        db = SessionLocal()
        results = {}

        try:
            async with EPADataIngestionService(db) as epa_service:
                sources_to_refresh = [source] if source else ["EPA_GHGRP", "EPA_EGRID"]

                for src in sources_to_refresh:
                    try:
                        # Fetch and cache data
                        data = await epa_service.fetch_latest_factors(src)

                        if data and data.get("factors"):
                            version = (
                                f"force_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                            )

                            update_result = epa_service.cache_with_versioning(
                                data["factors"], src, version
                            )

                            # Update Redis cache
                            await self._update_redis_cache(src, data["factors"])

                            # Clear staleness indicator
                            cache_service.set_cache_staleness_indicator(
                                f"epa_factors_{src.lower()}", False
                            )

                            results[src] = {
                                "status": "success",
                                "records_added": update_result.records_added,
                                "records_updated": update_result.records_updated,
                                "records_deprecated": update_result.records_deprecated,
                            }
                        else:
                            results[src] = {
                                "status": "no_data",
                                "message": "No data received from EPA API",
                            }

                    except Exception as e:
                        logger.error(f"Force refresh failed for {src}: {str(e)}")
                        results[src] = {"status": "error", "error": str(e)}

                return results

        except Exception as e:
            logger.error(f"Error in force refresh: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            "is_running": self.is_running,
            "refresh_interval_hours": self.refresh_interval_hours,
            "max_retries": self.max_retries,
            "retry_delay_minutes": self.retry_delay_minutes,
            "cache_health": cache_service.health_check(),
        }


# Global scheduler instance - lazy initialization to avoid database connection at module load
import os

if os.getenv("TESTING") != "true":
    epa_scheduler = EPADataScheduler()
else:
    # Mock scheduler for testing
    from unittest.mock import AsyncMock, MagicMock

    epa_scheduler = MagicMock()
    epa_scheduler.get_scheduler_status.return_value = {
        "is_running": False,
        "refresh_interval_hours": 24,
        "cache_health": True,
    }
    epa_scheduler.force_refresh = AsyncMock(return_value={})
    epa_scheduler.start_scheduler = AsyncMock()
    epa_scheduler.stop_scheduler = AsyncMock()
