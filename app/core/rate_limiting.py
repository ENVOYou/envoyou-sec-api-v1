"""
Rate Limiting Configuration and Middleware
Implements Redis-based rate limiting for API protection
"""

import redis

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    # Create dummy classes/functions for when slowapi is not available
    class Limiter:
        def __init__(self, **kwargs):
            pass
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def get_remote_address(request):
        return getattr(request, 'client', None) and getattr(request.client, 'host', 'unknown') or 'unknown'

    class SlowAPIMiddleware:
        def __init__(self, limiter):
            self.limiter = limiter

    class RateLimitExceeded(Exception):
        pass

from app.core.config import settings

# Initialize Redis connection for rate limiting
redis_conn = redis.from_url(settings.REDIS_URL)

# Configure rate limiter with Redis storage
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",  # Fixed window strategy
    storage_options={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
    }
)

# Custom rate limit exceeded handler
def rate_limit_exceeded_handler(request, exc):
    """Custom handler for rate limit exceeded errors"""
    return {
        "error_code": "RATE_LIMIT_EXCEEDED",
        "message": "Too many requests. Please try again later.",
        "details": {
            "retry_after": exc.retry_after,
            "limit": exc.limit,
            "remaining": exc.remaining,
        },
        "timestamp": exc.timestamp,
        "request_id": getattr(request.state, "request_id", None),
    }

# Set custom error response
limiter.error_response = rate_limit_exceeded_handler

# Rate limit rules
default_limits = [f"{settings.RATE_LIMIT_PER_MINUTE} per minute"]
burst_limits = [f"{settings.RATE_LIMIT_BURST} per minute"]

# Specific limits for different endpoints
auth_limits = ["10 per minute"]  # Stricter for auth endpoints
api_limits = [f"{settings.RATE_LIMIT_PER_MINUTE} per minute"]
health_limits = ["60 per minute"]  # More lenient for health checks