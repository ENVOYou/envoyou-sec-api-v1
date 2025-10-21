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
        except HTTPException as http_exc:
            # JANGAN tangani HTTPException di sini. Biarkan FastAPI/Starlette yang urus.
            # Cukup catat jika perlu, lalu lempar kembali errornya.
            logger.debug(f"HTTPException encountered: {http_exc.status_code} - {http_exc.detail}")
            raise http_exc # Penting: Lempar kembali!
        except Exception as exc:
            # Blok ini HANYA untuk error tak terduga (bukan HTTPException)
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            error_str = str(exc)

            # Penanganan khusus untuk client disconnect (opsional, bisa di-log saja)
            if any(err in error_str for err in ["EndOfStream", "WouldBlock", "Connection reset", "Broken pipe"]):
                logger.debug(f"Client connection issue - Request ID: {request_id}, Error: {error_str}")
                # Pertimbangkan untuk raise exc di sini juga agar tidak mengembalikan 500
                raise exc # Biarkan server menangani disconnect

            # Ini adalah error server yang sebenarnya
            logger.error(
                f"Unhandled server exception - Request ID: {request_id}, Error: {error_str}",
                exc_info=True,
            )

            # Kembalikan respons 500 yang terstruktur
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred.",
                    "request_id": request_id,
                    "support_reference": f"ERR-{request_id[:8]}",
                },
            )
