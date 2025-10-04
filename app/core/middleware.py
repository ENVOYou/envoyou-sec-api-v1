"""
Custom middleware for audit logging and error handling
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive audit logging of all API requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Log request
        logger.info(
            f"Request started - ID: {request_id}, Method: {request.method}, "
            f"URL: {request.url}, Client: {request.client.host if request.client else 'unknown'}"
        )

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(
            f"Request completed - ID: {request_id}, Status: {response.status_code}, "
            f"Time: {process_time:.3f}s"
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling and logging"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Get request ID if available
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

            # Log the error
            logger.error(
                f"Unhandled exception - Request ID: {request_id}, "
                f"Error: {str(exc)}",
                exc_info=True,
            )

            # Return structured error response
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred",
                    "details": None,
                    "timestamp": time.time(),
                    "request_id": request_id,
                    "support_reference": f"ERR-{request_id[:8]}",
                },
            )
