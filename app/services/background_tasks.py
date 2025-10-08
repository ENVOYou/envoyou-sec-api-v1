"""
Background Task Service for EPA Data Management
Handles automated refresh and maintenance tasks
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.epa_cache_service import EPACachedService

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for EPA data refresh and maintenance"""

    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False

    async def start_all_tasks(self):
        """Start all background tasks"""
        if self.is_running:
            logger.warning("Background tasks already running")
            return

        self.is_running = True
        logger.info("Starting background task manager")

        # Start EPA data refresh task
        self.tasks["epa_refresh"] = asyncio.create_task(self._epa_refresh_task())

        # Start cache maintenance task
        self.tasks["cache_maintenance"] = asyncio.create_task(
            self._cache_maintenance_task()
        )

        # Start health check task
        self.tasks["health_check"] = asyncio.create_task(self._health_check_task())

        logger.info(f"Started {len(self.tasks)} background tasks")

    async def stop_all_tasks(self):
        """Stop all background tasks"""
        if not self.is_running:
            return

        logger.info("Stopping background task manager")

        for task_name, task in self.tasks.items():
            if not task.done():
                logger.info(f"Cancelling task: {task_name}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Task cancelled: {task_name}")

        self.tasks.clear()
        self.is_running = False
        logger.info("All background tasks stopped")

    async def _epa_refresh_task(self):
        """Background task for EPA data refresh"""
        logger.info("EPA refresh task started")

        while True:
            try:
                # Wait for the configured interval
                await asyncio.sleep(settings.EPA_DATA_CACHE_HOURS * 3600)

                logger.info("Starting scheduled EPA data refresh")

                # Create database session
                db = SessionLocal()
                try:
                    async with EPACachedService(db) as epa_service:
                        refresh_results = await epa_service.refresh_epa_data()

                        if refresh_results["overall_status"] == "success":
                            logger.info(
                                "Scheduled EPA data refresh completed successfully"
                            )
                        else:
                            logger.warning(
                                f"EPA refresh completed with issues: {refresh_results}"
                            )

                            # Send notification if configured
                            await self._send_notification(
                                "EPA Refresh Warning",
                                f"EPA data refresh completed with issues: {refresh_results}",
                            )

                finally:
                    db.close()

            except asyncio.CancelledError:
                logger.info("EPA refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in EPA refresh task: {str(e)}")

                # Send error notification
                await self._send_notification(
                    "EPA Refresh Error", f"EPA data refresh failed: {str(e)}"
                )

                # Wait before retrying
                await asyncio.sleep(300)  # 5 minutes

    async def _cache_maintenance_task(self):
        """Background task for cache maintenance"""
        logger.info("Cache maintenance task started")

        while True:
            try:
                # Run maintenance every 6 hours
                await asyncio.sleep(6 * 3600)

                logger.info("Starting cache maintenance")

                db = SessionLocal()
                try:
                    async with EPACachedService(db) as epa_service:
                        # Get cache status
                        cache_status = epa_service.get_cache_status()

                        # Log cache statistics
                        logger.info(f"Cache status: {cache_status}")

                        # Check for stale cache entries
                        await self._cleanup_stale_cache(epa_service)

                        # Check memory usage
                        await self._check_memory_usage(cache_status)

                finally:
                    db.close()

            except asyncio.CancelledError:
                logger.info("Cache maintenance task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cache maintenance task: {str(e)}")
                await asyncio.sleep(300)  # Wait before retrying

    async def _health_check_task(self):
        """Background task for system health checks"""
        logger.info("Health check task started")

        while True:
            try:
                # Run health check every 15 minutes
                await asyncio.sleep(15 * 60)

                db = SessionLocal()
                try:
                    async with EPACachedService(db) as epa_service:
                        # Check database connectivity
                        db_healthy = await self._check_database_health(db)

                        # Check cache connectivity
                        cache_healthy = await self._check_cache_health(epa_service)

                        # Check EPA API availability
                        api_healthy = await self._check_epa_api_health(epa_service)

                        health_status = {
                            "database": db_healthy,
                            "cache": cache_healthy,
                            "epa_api": api_healthy,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        # Log health status
                        if all(health_status.values()):
                            logger.debug(f"System health check: All systems healthy")
                        else:
                            logger.warning(f"System health check: {health_status}")

                            # Send alert if any system is unhealthy
                            await self._send_notification(
                                "System Health Alert",
                                f"System health issues detected: {health_status}",
                            )

                finally:
                    db.close()

            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check task: {str(e)}")
                await asyncio.sleep(300)  # Wait before retrying

    async def _cleanup_stale_cache(self, epa_service: EPACachedService):
        """Clean up stale cache entries"""
        try:
            # This could be enhanced to remove very old cache entries
            # For now, just log the cache status
            cache_status = epa_service.get_cache_status()

            # Check for sources with very old cache
            for source, status in (
                cache_status.get("cache", {}).get("sources", {}).items()
            ):
                if status.get("cached_at"):
                    cached_at = datetime.fromisoformat(status["cached_at"])
                    age_days = (datetime.utcnow() - cached_at).days

                    if age_days > 30:  # Older than 30 days
                        logger.warning(
                            f"Very old cache detected for {source}: {age_days} days"
                        )
                        # Could implement automatic cleanup here

        except Exception as e:
            logger.error(f"Error in cache cleanup: {str(e)}")

    async def _check_memory_usage(self, cache_status: Dict[str, Any]):
        """Check cache memory usage"""
        try:
            cache_info = cache_status.get("cache", {})
            memory_used = cache_info.get("memory_used", "0B")

            # Log memory usage (could implement alerts for high usage)
            logger.debug(f"Cache memory usage: {memory_used}")

        except Exception as e:
            logger.error(f"Error checking memory usage: {str(e)}")

    async def _check_database_health(self, db) -> bool:
        """Check database connectivity"""
        try:
            # Simple query to test database
            db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False

    async def _check_cache_health(self, epa_service: EPACachedService) -> bool:
        """Check cache connectivity"""
        try:
            cache_status = epa_service.get_cache_status()
            return cache_status.get("cache", {}).get("connected", False)
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
            return False

    async def _check_epa_api_health(self, epa_service: EPACachedService) -> bool:
        """Check EPA API availability"""
        try:
            # This is a simplified check - could be enhanced
            # to actually test API endpoints
            return True  # Assume healthy for now
        except Exception as e:
            logger.error(f"EPA API health check failed: {str(e)}")
            return False

    async def _send_notification(self, subject: str, message: str):
        """Send notification (placeholder for actual notification system)"""
        # This could be enhanced to send actual notifications
        # via email, Slack, etc.
        logger.warning(f"NOTIFICATION - {subject}: {message}")

    def get_task_status(self) -> Dict[str, Any]:
        """Get status of all background tasks"""
        status = {"is_running": self.is_running, "tasks": {}}

        for task_name, task in self.tasks.items():
            status["tasks"][task_name] = {
                "running": not task.done(),
                "cancelled": task.cancelled(),
                "exception": (
                    str(task.exception()) if task.done() and task.exception() else None
                ),
            }

        return status


# Global task manager instance - lazy initialization for testing
import os

if os.getenv("TESTING") != "true":
    task_manager = BackgroundTaskManager()
else:
    # Mock task manager for testing
    from unittest.mock import AsyncMock, MagicMock

    task_manager = MagicMock()
    task_manager.get_task_status.return_value = {"status": "not_running"}
    task_manager.start_all_tasks = AsyncMock()
    task_manager.stop_all_tasks = AsyncMock()


@asynccontextmanager
async def lifespan_manager():
    """Context manager for application lifespan"""
    try:
        # Start background tasks
        await task_manager.start_all_tasks()
        yield
    finally:
        # Stop background tasks
        await task_manager.stop_all_tasks()
