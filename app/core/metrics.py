"""
Prometheus Metrics Configuration
Provides monitoring and alerting capabilities
"""

import time
from typing import Callable

from fastapi import Request, Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Create dummy classes/functions for when prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, value=1):
            pass

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def set(self, value):
            pass

        def inc(self):
            pass

        def dec(self):
            pass

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def observe(self, value):
            pass

    def generate_latest():
        return b"# Prometheus metrics not available"

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
from starlette.middleware.base import BaseHTTPMiddleware

# Request metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

# Business metrics
EMISSIONS_CALCULATIONS = Counter(
    "emissions_calculations_total",
    "Total number of emissions calculations performed",
    ["scope", "method"],
)

EPA_API_CALLS = Counter(
    "epa_api_calls_total", "Total number of EPA API calls", ["endpoint", "status"]
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Current state of circuit breakers (0=closed, 1=open, 2=half_open)",
    ["name"],
)

# System metrics
ACTIVE_CONNECTIONS = Gauge("active_connections", "Number of active connections")

DATABASE_CONNECTIONS = Gauge(
    "database_connections_active", "Number of active database connections", ["pool"]
)

REDIS_CONNECTIONS = Gauge(
    "redis_connections_active", "Number of active Redis connections"
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Track active connections
        ACTIVE_CONNECTIONS.inc()

        try:
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
            ).inc()

            REQUEST_DURATION.labels(
                method=request.method, endpoint=request.url.path
            ).observe(duration)

            return response

        finally:
            ACTIVE_CONNECTIONS.dec()


def get_metrics() -> bytes:
    """Get current metrics in Prometheus format"""
    return generate_latest()


# Helper functions for business metrics
def record_emissions_calculation(scope: str, method: str):
    """Record an emissions calculation"""
    EMISSIONS_CALCULATIONS.labels(scope=scope, method=method).inc()


def record_epa_api_call(endpoint: str, status: str):
    """Record an EPA API call"""
    EPA_API_CALLS.labels(endpoint=endpoint, status=status).inc()


def update_circuit_breaker_state(name: str, state: str):
    """Update circuit breaker state metric"""
    state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
    CIRCUIT_BREAKER_STATE.labels(name=name).set(state_value)


def update_database_connections(pool: str, count: int):
    """Update database connection count"""
    DATABASE_CONNECTIONS.labels(pool=pool).set(count)


def update_redis_connections(count: int):
    """Update Redis connection count"""
    REDIS_CONNECTIONS.set(count)
