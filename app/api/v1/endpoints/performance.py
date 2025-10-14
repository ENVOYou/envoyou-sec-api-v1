"""
Performance Monitoring Endpoints
API endpoints for monitoring system performance and metrics
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.services.performance_monitor import performance_monitor

router = APIRouter()


@router.get("/metrics")
async def get_performance_metrics(
    hours: int = Query(1, ge=1, le=24, description="Time range in hours"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get comprehensive performance metrics

    Returns detailed performance statistics including API response times,
    database query performance, cache operations, and system health status.
    """
    if not current_user.is_admin:
        # Non-admin users get limited metrics
        summary = performance_monitor.get_performance_summary(hours)
        return {
            "time_range_hours": hours,
            "summary": summary["summary"],
            "performance_stats": summary["performance_stats"],
        }

    # Admin users get full metrics
    return performance_monitor.get_performance_summary(hours)


@router.get("/health")
async def get_system_health(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get system health status based on performance metrics

    Returns overall health status and any performance issues detected.
    """
    return performance_monitor.get_health_status()


@router.get("/endpoints")
async def get_endpoint_performance(
    hours: int = Query(1, ge=1, le=24, description="Time range in hours"),
    limit: int = Query(20, ge=1, le=100, description="Maximum endpoints to return"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get performance metrics for API endpoints

    Returns response times, error rates, and usage statistics for each endpoint.
    """
    summary = performance_monitor.get_performance_summary(hours)
    endpoint_performance = summary["endpoint_performance"]

    # Sort by request count and limit results
    sorted_endpoints = sorted(
        endpoint_performance.items(), key=lambda x: x[1]["total_requests"], reverse=True
    )[:limit]

    return {
        "time_range_hours": hours,
        "total_endpoints": len(endpoint_performance),
        "endpoint_performance": dict(sorted_endpoints),
    }


@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=50, description="Maximum queries to return"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get list of slow database queries

    Returns the most recent slow database queries with their execution times.
    Admin access required.
    """
    if not current_user.is_admin:
        return {"error": "Admin access required"}

    summary = performance_monitor.get_performance_summary(hours=24)  # Last 24 hours
    slow_queries = summary["slow_queries"][-limit:]  # Most recent

    return {
        "total_slow_queries": len(summary["slow_queries"]),
        "returned_queries": len(slow_queries),
        "slow_queries": slow_queries,
    }


@router.get("/cache-stats")
async def get_cache_performance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get cache performance statistics

    Returns Redis cache statistics and hit rates.
    """
    from app.services.cache_service import cache_service

    cache_stats = cache_service.get_cache_stats()

    # Add performance metrics for cache operations
    summary = performance_monitor.get_performance_summary(hours=1)
    cache_performance = summary["performance_stats"]["cache_operations"]

    return {
        "cache_stats": cache_stats,
        "performance": cache_performance,
    }


@router.get("/database-stats")
async def get_database_performance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get database performance statistics

    Returns connection pool stats and query performance metrics.
    """
    from app.db.database import get_connection_pool_stats

    pool_stats = get_connection_pool_stats()

    # Add performance metrics for database operations
    summary = performance_monitor.get_performance_summary(hours=1)
    db_performance = summary["performance_stats"]["database_queries"]

    return {
        "pool_stats": pool_stats,
        "performance": db_performance,
    }
