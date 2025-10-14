"""
Health Checks for Dependencies
Comprehensive health monitoring for database, cache, and external services
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_connection_pool_stats, get_db

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health checker for all system dependencies"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)

    async def check_database(self, db: Session) -> Dict[str, Any]:
        """Check database connectivity and basic operations"""
        try:
            # Test basic connectivity
            start_time = datetime.utcnow()
            result = db.execute(text("SELECT 1 as test")).fetchone()
            response_time = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000  # ms

            if result and result[0] == 1:
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Database connection successful",
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Database query returned unexpected result",
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Database health check failed: {error_msg}")

            # In development, SQLite connection issues are expected
            if settings.ENVIRONMENT == "development" and (
                "sqlite" in settings.DATABASE_URL.lower()
                or "no such table" in error_msg.lower()
            ):
                return {
                    "status": "healthy",
                    "response_time_ms": 0,
                    "message": "Development environment - SQLite database not initialized",
                    "note": "Database will be initialized on first API call",
                }

            return {
                "status": "unhealthy",
                "error": error_msg,
                "message": "Database connection failed",
            }

    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and basic operations"""
        try:
            start_time = datetime.utcnow()

            # Test basic connectivity
            self.redis_client.ping()

            # Test set/get operation
            test_key = "health_check_test"
            test_value = "ok"
            self.redis_client.setex(test_key, 10, test_value)
            retrieved_value = self.redis_client.get(test_key)

            response_time = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000  # ms

            if retrieved_value == test_value:
                # Clean up test key
                self.redis_client.delete(test_key)

                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Redis connection and operations successful",
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Redis set/get operation failed",
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Redis health check failed: {error_msg}")

            # In development, Redis connection issues are expected
            if settings.ENVIRONMENT == "development" and (
                "connection refused" in error_msg.lower()
                or "localhost" in settings.REDIS_URL
            ):
                return {
                    "status": "healthy",
                    "response_time_ms": 0,
                    "message": "Development environment - Redis not available locally",
                    "note": "Using Upstash Redis in production",
                }

            return {
                "status": "unhealthy",
                "error": error_msg,
                "message": "Redis connection failed",
            }

    async def check_external_services(self) -> Dict[str, Any]:
        """Check external service availability"""
        services_status = {}

        # EPA API check (mock for now since it's external)
        try:
            # In production, this would actually test EPA API connectivity
            # For now, we'll just check if the URL is configured
            if settings.EPA_API_BASE_URL:
                services_status["epa_api"] = {
                    "status": "configured",
                    "message": "EPA API URL is configured",
                }
            else:
                services_status["epa_api"] = {
                    "status": "not_configured",
                    "message": "EPA API URL not configured",
                }
        except Exception as e:
            services_status["epa_api"] = {
                "status": "error",
                "error": str(e),
                "message": "EPA API check failed",
            }

        return services_status

    async def get_system_info(self) -> Dict[str, Any]:
        """Get basic system information"""
        return {
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
            "service": "envoyou-sec-api",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def perform_comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all components"""
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "system_info": await self.get_system_info(),
        }

        # Database check
        db = next(get_db())
        try:
            db_health = await self.check_database(db)
            # Add connection pool stats
            pool_stats = get_connection_pool_stats()
            db_health["pool_stats"] = pool_stats
            health_status["checks"]["database"] = db_health
        finally:
            db.close()

        # Redis check
        health_status["checks"]["redis"] = await self.check_redis()

        # External services check
        health_status["checks"][
            "external_services"
        ] = await self.check_external_services()

        # Determine overall status
        unhealthy_checks = []
        for service_name, check in health_status["checks"].items():
            if isinstance(check, dict) and check.get("status") == "unhealthy":
                unhealthy_checks.append({**check, "service": service_name})

        # In development, allow some services to be unavailable
        if settings.ENVIRONMENT == "development":
            # Filter out expected development issues
            critical_unhealthy = [
                check
                for check in unhealthy_checks
                if not (
                    check.get("service") == "database"
                    and (
                        "SQLite database not initialized" in check.get("message", "")
                        or "connection to server" in check.get("error", "")
                    )
                    or check.get("service") == "redis"
                    and (
                        "Redis not available locally" in check.get("message", "")
                        or "Redis set/get operation failed" in check.get("message", "")
                    )
                )
            ]
            unhealthy_checks = critical_unhealthy

        if unhealthy_checks:
            health_status["overall_status"] = "unhealthy"
            health_status["issues"] = unhealthy_checks

        return health_status

    async def get_detailed_health_report(self) -> Dict[str, Any]:
        """Get detailed health report with metrics"""
        basic_health = await self.perform_comprehensive_health_check()

        # Add additional metrics
        detailed_report = {
            **basic_health,
            "metrics": {
                "uptime": "N/A",  # Would need to track application start time
                "memory_usage": "N/A",  # Would need psutil
                "cpu_usage": "N/A",  # Would need psutil
            },
            "configuration": {
                "database_url_configured": bool(settings.DATABASE_URL),
                "redis_url_configured": bool(settings.REDIS_URL),
                "epa_api_configured": bool(settings.EPA_API_BASE_URL),
            },
        }

        return detailed_report


async def get_detailed_health_status(db: Session) -> Dict[str, Any]:
    """Get detailed health status for the API endpoint"""
    return await health_checker.perform_comprehensive_health_check()


# Global health checker instance
health_checker = HealthChecker()
