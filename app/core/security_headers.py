"""
Security Headers Middleware
Adds security headers to all HTTP responses for production hardening
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy (restrictive for API)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'none'; "
            "style-src 'none'; "
            "img-src 'none'; "
            "font-src 'none'; "
            "connect-src 'self'; "
            "media-src 'none'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # HSTS (HTTP Strict Transport Security) - only for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Remove server header for security
        response.headers.pop("server", None)

        # Add custom security headers
        response.headers["X-API-Version"] = "1.0.0"
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")

        return response
