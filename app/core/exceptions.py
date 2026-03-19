"""Custom exceptions and exception handlers"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from typing import Optional, List, Any
import uuid
import logging

logger = logging.getLogger(__name__)


# ==================== CUSTOM EXCEPTIONS ====================

class APIException(Exception):
    """
    Base exception for all API errors.

    Use this as base for all custom exceptions.
    Automatically formatted as RFC 7807 Problem Details.
    """
    def __init__(
        self,
        status_code: int,
        error_type: str,
        title: str,
        detail: str,
        errors: Optional[List[dict]] = None
    ):
        self.status_code = status_code
        self.error_type = error_type
        self.title = title
        self.detail = detail
        self.errors = errors
        super().__init__(self.detail)


# Client Errors (4xx)

class ValidationError(APIException):
    """400 - Request validation failed"""
    def __init__(self, detail: str, errors: Optional[List[dict]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type="validation_error",
            title="Validation Error",
            detail=detail,
            errors=errors
        )


class AuthenticationError(APIException):
    """401 - Authentication required or failed"""
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_type="authentication_error",
            title="Authentication Error",
            detail=detail
        )


class PermissionDeniedError(APIException):
    """403 - User lacks permission for this action"""
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_type="permission_denied",
            title="Permission Denied",
            detail=detail
        )


class NotFoundError(APIException):
    """404 - Resource not found"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="not_found",
            title="Resource Not Found",
            detail=detail
        )


class ConflictError(APIException):
    """409 - Resource conflict (e.g., duplicate entry)"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_type="conflict",
            title="Resource Conflict",
            detail=detail
        )


class BusinessRuleError(APIException):
    """422 - Business rule violation"""
    def __init__(self, detail: str, errors: Optional[List[dict]] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="business_rule_violation",
            title="Business Rule Violation",
            detail=detail,
            errors=errors
        )


class RateLimitError(APIException):
    """429 - Too many requests"""
    def __init__(self, detail: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_type="rate_limit_exceeded",
            title="Rate Limit Exceeded",
            detail=detail
        )


# Server Errors (5xx)

class InternalServerError(APIException):
    """500 - Internal server error"""
    def __init__(self, detail: str = "An unexpected error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="internal_error",
            title="Internal Server Error",
            detail=detail
        )


class ServiceUnavailableError(APIException):
    """503 - Service temporarily unavailable"""
    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="service_unavailable",
            title="Service Unavailable",
            detail=detail
        )


# ==================== EXCEPTION HANDLERS ====================

async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Handle custom API exceptions.
    Returns RFC 7807 Problem Details format.
    """
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex}")

    # Log error with structured data
    logger.error(
        f"API Error: {exc.title}",
        extra={
            "request_id": request_id,
            "error_type": exc.error_type,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host if request.client else None
        }
    )

    # Build RFC 7807 response
    problem_detail = {
        "type": f"https://api.yourdomain.com/errors/{exc.error_type}",
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": str(request.url.path),
        "request_id": request_id
    }

    # Add field errors if present
    if exc.errors:
        problem_detail["errors"] = exc.errors

    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": request_id},
        content=problem_detail
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    Converts to RFC 7807 format with field-level errors.
    """
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex}")

    # Format validation errors
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field_path or "body",
            "message": error["msg"],
            "code": error["type"]
        })

    # Log detailed validation errors for debugging
    logger.error(f"[VALIDATION] Request validation failed for {request.method} {request.url.path}")
    logger.error(f"[VALIDATION] Full error details: {exc.errors()}")
    logger.error(f"[VALIDATION] Formatted errors: {errors}")

    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "errors": errors,
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        headers={"X-Request-ID": request_id},
        content={
            "type": "https://api.yourdomain.com/errors/validation_error",
            "title": "Validation Error",
            "status": 400,
            "detail": "Request validation failed",
            "instance": str(request.url.path),
            "request_id": request_id,
            "errors": errors
        }
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handle database integrity errors (unique constraints, foreign keys, etc.).
    Sanitizes error message to avoid leaking database details.
    """
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex}")

    # Log full error server-side
    logger.error(
        "Database integrity error",
        extra={
            "request_id": request_id,
            "error": str(exc),
            "path": request.url.path
        },
        exc_info=True
    )

    # Sanitized error message for client
    detail = "A database constraint was violated. The resource may already exist."

    # Try to extract useful info without exposing internals
    error_str = str(exc).lower()
    if "unique" in error_str or "duplicate" in error_str:
        detail = "This resource already exists. Please use a different value."
    elif "foreign key" in error_str:
        detail = "Referenced resource does not exist."
    elif "not null" in error_str:
        detail = "Required field is missing."

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        headers={"X-Request-ID": request_id},
        content={
            "type": "https://api.yourdomain.com/errors/conflict",
            "title": "Resource Conflict",
            "status": 409,
            "detail": detail,
            "instance": str(request.url.path),
            "request_id": request_id
        }
    )


async def database_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    """
    Handle database operational errors (connection lost, timeout, etc.).
    """
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex}")

    # Log full error server-side
    logger.error(
        "Database operational error",
        extra={
            "request_id": request_id,
            "error": str(exc),
            "path": request.url.path
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"X-Request-ID": request_id},
        content={
            "type": "https://api.yourdomain.com/errors/service_unavailable",
            "title": "Service Unavailable",
            "status": 503,
            "detail": "Database service is temporarily unavailable. Please try again later.",
            "instance": str(request.url.path),
            "request_id": request_id
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unexpected exceptions.
    Logs full error server-side but returns sanitized error to client.
    """
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex}")

    # Log FULL error server-side with stack trace
    logger.exception(
        "Unexpected error",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host if request.client else None
        }
    )

    # Return SANITIZED error to client
    # Never expose internal error details in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"X-Request-ID": request_id},
        content={
            "type": "https://api.yourdomain.com/errors/internal_error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred. Please contact support with the request ID.",
            "instance": str(request.url.path),
            "request_id": request_id
        }
    )
