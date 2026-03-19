"""Error response schemas (RFC 7807 Problem Details)"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any


class ErrorDetail(BaseModel):
    """Field-level error detail for validation errors"""
    field: str = Field(
        description="Field name that failed validation"
    )
    message: str = Field(
        description="Error message for this field"
    )
    code: str = Field(
        description="Machine-readable error code"
    )


class ProblemDetail(BaseModel):
    """
    RFC 7807 Problem Details for HTTP APIs.

    Standard format for error responses used by GitHub, Azure, and many others.
    Provides consistent error structure across all endpoints.

    See: https://datatracker.ietf.org/doc/html/rfc7807
    """
    type: str = Field(
        description="URI reference identifying the problem type",
        example="https://api.yourdomain.com/errors/validation_error"
    )
    title: str = Field(
        description="Short, human-readable summary of the problem",
        example="Validation Error"
    )
    status: int = Field(
        description="HTTP status code",
        example=400
    )
    detail: str = Field(
        description="Human-readable explanation specific to this occurrence",
        example="Sales order must have at least one item"
    )
    instance: str = Field(
        description="URI reference identifying the specific occurrence of the problem",
        example="/api/v1/sales-orders"
    )
    request_id: str = Field(
        description="Unique request identifier for debugging and support",
        example="req_abc123xyz789"
    )
    errors: Optional[List[ErrorDetail]] = Field(
        None,
        description="Detailed field-level validation errors (for 400 responses)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "https://api.yourdomain.com/errors/validation_error",
                "title": "Validation Error",
                "status": 400,
                "detail": "Request validation failed",
                "instance": "/api/v1/sales-orders",
                "request_id": "req_abc123xyz789",
                "errors": [
                    {
                        "field": "items",
                        "message": "At least one item is required",
                        "code": "min_items"
                    }
                ]
            }
        }
