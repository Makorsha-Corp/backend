"""API middleware for request tracking, logging, and security"""
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import uuid
import time
import logging

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID and structured logging to all requests.

    Adds:
    - Unique request ID to every request
    - Request ID in response headers (X-Request-ID)
    - Structured logging with timing
    - Request/response logging
    """

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Log incoming request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params) if request.query_params else None,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "workspace_id": request.headers.get("x-workspace-id")
            }
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response
        log_level = logging.INFO if response.status_code < 400 else logging.ERROR
        logger.log(
            log_level,
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Adds standard security headers to protect against common attacks.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Skip security headers for Swagger UI and ReDoc to avoid blocking assets
        is_docs_path = request.url.path.startswith("/api/v1/docs") or request.url.path.startswith("/api/v1/redoc") or request.url.path.startswith("/api/v1/openapi.json")
        
        if not is_docs_path:
            # Security headers (skip for docs to allow Swagger UI to work)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

            # Only add CSP for HTML responses (not docs)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
