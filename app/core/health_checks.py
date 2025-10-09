"""
Health Checks for Dependencies
Comprehensive health monitoring for database, cache, and external services
"""

import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import update_database_connections, update_redis_connections


class HealthCheckResult:
    """Result of a health check"""

    def __init__(self, name: str, status: str, response_time: float = None, error: str = None):
        self.name = name
        self.status = status  # "healthy", "unhealthy", "degraded"
        self.response_time = response_time
        self.error = error
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "response_time_ms": round(self.response_time * 1000, 2) if self.response_time else None,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Comprehensive health checker for all dependencies"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)

    async def check_database(self, db: Session) -> HealthCheckResult:
        """Check database connectivity and performance"""
        start_time = time.time()

        try:
            # Simple query to test connectivity
            result = db.execute(text("SELECT 1 as test")).fetchone()

            if result and result[0] == 1:
                response_time = time.time() - start_time
                return HealthCheckResult("database", "healthy", response_time)
            else:
                return HealthCheckResult("database", "unhealthy", error="Invalid response from database")

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("database", "unhealthy", response_time, str(e))

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and performance"""
        start_time = time.time()

        try:
            # Test Redis connectivity
            self.redis_client.ping()

            # Get connection info for metrics
            info = self.redis_client.info()
            connected_clients = info.get("connected_clients", 0)
            update_redis_connections(connected_clients)

            response_time = time.time() - start_time
            return HealthCheckResult("redis", "healthy", response_time)

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("redis", "unhealthy", response_time, str(e))

    async def check_external_services(self) -> List[HealthCheckResult]:
        """Check external service health"""
        results = []

        # EPA API health check (mock for now since it's external)
        try:
            # In production, this would be a real health check
            # For now, we'll assume it's healthy if circuit breaker is closed
            from app.core.circuit_breaker import epa_api_circuit_breaker

            state = epa_api_circuit_breaker.get_state()
            if state["state"] == "open":
                results.append(HealthCheckResult("epa_api", "degraded", error="Circuit breaker is open"))
            else:
                results.append(HealthCheckResult("epa_api", "healthy"))

        except Exception as e:
            results.append(HealthCheckResult("epa_api", "unhealthy", error=str(e)))

        return results

    async def perform_comprehensive_check(self, db: Session) -> Dict[str, Any]:
        """Perform comprehensive health check of all services"""
        start_time = time.time()

        # Run all health checks concurrently
        db_check = await self.check_database(db)
        redis_check = await self.check_redis()
        external_checks = await self.check_external_services()

        all_checks = [db_check, redis_check] + external_checks

        # Calculate overall status
        unhealthy_checks = [check for check in all_checks if check.status == "unhealthy"]
        degraded_checks = [check for check in all_checks if check.status == "degraded"]

        if unhealthy_checks:
            overall_status = "unhealthy"
        elif degraded_checks:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        total_response_time = time.time() - start_time

        # Update database connection metrics
        try:
            # This is a simplified way - in production you'd use connection pool stats
            update_database_connections("main", 1)  # Placeholder
        except:
            pass

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(total_response_time * 1000, 2),
            "checks": [check.to_dict() for check in all_checks],
            "summary": {
                "total_checks": len(all_checks),
                "healthy": len([c for c in all_checks if c.status == "healthy"]),
                "degraded": len([c for c in all_checks if c.status == "degraded"]),
                "unhealthy": len([c for c in all_checks if c.status == "unhealthy"]),
            }
        }


# Global health checker instance
health_checker = HealthChecker()


async def get_detailed_health_status(db: Session) -> Dict[str, Any]:
    """Get detailed health status for monitoring"""
    return await health_checker.perform_comprehensive_check(db)