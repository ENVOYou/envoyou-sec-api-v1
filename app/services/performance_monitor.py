"""
Performance Monitoring Service
Tracks API performance, database queries, and system metrics
"""

import logging
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Service for monitoring API performance and system metrics"""

    def __init__(self, max_metrics_history: int = 1000):
        self.max_history = max_metrics_history
        self.request_metrics = deque(maxlen=max_metrics_history)
        self.database_metrics = deque(maxlen=max_metrics_history)
        self.cache_metrics = deque(maxlen=max_metrics_history)
        self.endpoint_stats = defaultdict(
            lambda: {"count": 0, "total_time": 0.0, "errors": 0}
        )
        self.slow_queries = deque(maxlen=100)  # Track slow database queries

    @contextmanager
    def track_request(self, method: str, endpoint: str, user_id: Optional[str] = None):
        """Context manager to track API request performance"""
        start_time = time.time()
        start_datetime = datetime.utcnow()

        try:
            yield
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Record metrics
            metric = {
                "timestamp": start_datetime.isoformat(),
                "method": method,
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "user_id": user_id,
                "error_message": error_message,
            }

            self.request_metrics.append(metric)

            # Update endpoint statistics
            stats = self.endpoint_stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += duration_ms
            if not success:
                stats["errors"] += 1

            # Log slow requests
            if duration_ms > 1000:  # More than 1 second
                logger.warning(
                    f"Slow request: {method} {endpoint} took {duration_ms:.2f}ms"
                )

    @contextmanager
    def track_database_query(self, query_type: str, table_name: Optional[str] = None):
        """Context manager to track database query performance"""
        start_time = time.time()

        try:
            yield
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Record metrics
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "query_type": query_type,
                "table_name": table_name,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "error_message": error_message,
            }

            self.database_metrics.append(metric)

            # Track slow queries
            if duration_ms > 500:  # More than 500ms
                slow_query = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "query_type": query_type,
                    "table_name": table_name,
                    "duration_ms": duration_ms,
                    "query": getattr(self, "_current_query", "Unknown"),
                }
                self.slow_queries.append(slow_query)

                logger.warning(
                    f"Slow database query: {query_type} on {table_name or 'unknown'} took {duration_ms:.2f}ms"
                )

    @contextmanager
    def track_cache_operation(self, operation: str, key_pattern: Optional[str] = None):
        """Context manager to track cache operation performance"""
        start_time = time.time()

        try:
            yield
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Record metrics
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "operation": operation,
                "key_pattern": key_pattern,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "error_message": error_message,
            }

            self.cache_metrics.append(metric)

    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Filter recent metrics
        recent_requests = [
            m
            for m in self.request_metrics
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]

        recent_db_queries = [
            m
            for m in self.database_metrics
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]

        recent_cache_ops = [
            m
            for m in self.cache_metrics
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]

        # Calculate statistics
        request_stats = self._calculate_stats(recent_requests, "duration_ms")
        db_stats = self._calculate_stats(recent_db_queries, "duration_ms")
        cache_stats = self._calculate_stats(recent_cache_ops, "duration_ms")

        # Endpoint performance
        endpoint_performance = {}
        for endpoint, stats in self.endpoint_stats.items():
            if stats["count"] > 0:
                avg_time = stats["total_time"] / stats["count"]
                error_rate = (stats["errors"] / stats["count"]) * 100
                endpoint_performance[endpoint] = {
                    "total_requests": stats["count"],
                    "average_response_time_ms": round(avg_time, 2),
                    "error_rate_percent": round(error_rate, 2),
                    "total_errors": stats["errors"],
                }

        return {
            "time_range_hours": hours,
            "summary": {
                "total_requests": len(recent_requests),
                "total_db_queries": len(recent_db_queries),
                "total_cache_operations": len(recent_cache_ops),
                "slow_requests_count": len(
                    [r for r in recent_requests if r["duration_ms"] > 1000]
                ),
                "slow_db_queries_count": len(
                    [q for q in recent_db_queries if q["duration_ms"] > 500]
                ),
            },
            "performance_stats": {
                "api_requests": request_stats,
                "database_queries": db_stats,
                "cache_operations": cache_stats,
            },
            "endpoint_performance": dict(
                sorted(
                    endpoint_performance.items(),
                    key=lambda x: x[1]["total_requests"],
                    reverse=True,
                )[:20]
            ),  # Top 20 endpoints
            "slow_queries": list(self.slow_queries)[-10:],  # Last 10 slow queries
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status based on performance metrics"""
        summary = self.get_performance_summary(hours=1)

        # Define health thresholds
        health_status = "healthy"
        issues = []

        # Check API response times
        if summary["performance_stats"]["api_requests"]["p95"] > 2000:  # 2 seconds
            health_status = "degraded"
            issues.append("High API response times detected")

        # Check error rates
        total_requests = summary["summary"]["total_requests"]
        if total_requests > 0:
            error_rate = (
                sum(
                    stats["error_rate_percent"]
                    for stats in summary["endpoint_performance"].values()
                )
                / len(summary["endpoint_performance"])
                if summary["endpoint_performance"]
                else 0
            )

            if error_rate > 5:  # More than 5% error rate
                health_status = "unhealthy"
                issues.append(f"High error rate: {error_rate:.1f}%")

        # Check slow queries
        if len(summary["slow_queries"]) > 5:
            health_status = "degraded"
            issues.append("Multiple slow database queries detected")

        return {
            "status": health_status,
            "issues": issues,
            "metrics": summary,
        }

    def _calculate_stats(self, metrics: List[Dict], value_key: str) -> Dict[str, float]:
        """Calculate statistical metrics from a list of measurements"""
        if not metrics:
            return {
                "count": 0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        values = sorted([m[value_key] for m in metrics if value_key in m])

        if not values:
            return {
                "count": 0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        count = len(values)
        avg = sum(values) / count
        min_val = min(values)
        max_val = max(values)

        # Calculate percentiles
        p50_idx = int(count * 0.5)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)

        p50 = values[min(p50_idx, len(values) - 1)]
        p95 = values[min(p95_idx, len(values) - 1)]
        p99 = values[min(p99_idx, len(values) - 1)]

        return {
            "count": count,
            "avg": round(avg, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
        }

    def reset_metrics(self):
        """Reset all performance metrics (useful for testing)"""
        self.request_metrics.clear()
        self.database_metrics.clear()
        self.cache_metrics.clear()
        self.endpoint_stats.clear()
        self.slow_queries.clear()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
