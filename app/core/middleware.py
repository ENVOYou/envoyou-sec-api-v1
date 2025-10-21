"""
Custom middleware for audit logging and error handling
"""

import logging
import time
import uuid
from typing import Callable

import anyio
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive audit logging of all API requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
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
        except Exception as exc:
            # Check if this is a stream-related error that we should not log
            error_str = str(exc)
            if any(
                err in error_str
                for err in [
                    "EndOfStream",
                    "WouldBlock",
                    "Connection reset",
                    "Broken pipe",
                ]
            ):
                # These are client-side connection issues, not server errors
                # Re-raise to let ErrorHandlingMiddleware handle it
                raise exc

            # For other errors, just re-raise to let ErrorHandlingMiddleware handle it
            raise exc


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            # Coba jalankan request seperti biasa
            response = await call_next(request)
            return response
        except Exception as exc:
            # Blok ini HANYA untuk error tak terduga (BUKAN HTTPException)

            # Periksa apakah ini HTTPException, JIKA YA, lempar kembali agar ditangani FastAPI
            if isinstance(exc, HTTPException):
                logger.debug(
                    f"HTTPException encountered, letting FastAPI handle: {exc.status_code} - {exc.detail}"
                )
                raise exc  # Penting: Lempar kembali!

            # Tangani Client Disconnect/Stream Errors (Jangan dianggap error 500)
            if isinstance(exc, (anyio.EndOfStream, anyio.WouldBlock)):
                request_id_stream = getattr(request.state, "request_id", "N/A")
                logger.debug(
                    f"Client connection issue (ignored) - Request ID: {request_id_stream}, Error: {type(exc).__name__}"
                )
                # Cukup lempar kembali, biarkan server menangani disconnect
                raise exc

            # Ini adalah error server yang sebenarnya dan tak terduga
            request_id_unhandled = getattr(
                request.state, "request_id", str(uuid.uuid4())
            )
            logger.error(
                f"Unhandled server exception - Request ID: {request_id_unhandled}, Error: {str(exc)}",
                exc_info=True,  # Sertakan traceback lengkap di log
            )

            # Kembalikan respons 500 yang terstruktur
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred.",
                    "request_id": request_id_unhandled,
                    "support_reference": f"ERR-{request_id_unhandled[:8]}",
                },
            )
