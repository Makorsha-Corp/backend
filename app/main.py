"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal

# Import exception handlers and middleware
from app.core.exceptions import (
    APIException,
    api_exception_handler,
    validation_exception_handler,
    integrity_error_handler,
    database_error_handler,
    generic_exception_handler
)
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware


# Initialize database with default data
db = SessionLocal()
try:
    init_db(db)
finally:
    db.close()


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    description="Production-ready ERP API with standardized error handling and request tracking"
)


# ==================== MIDDLEWARE ====================
# Order matters: first added = outermost layer

# Request context (adds request ID and logging)
app.add_middleware(RequestContextMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]  # Expose request ID to clients
)


# ==================== EXCEPTION HANDLERS ====================
# Register in order of specificity (most specific first)

# Custom API exceptions (our business logic errors)
app.add_exception_handler(APIException, api_exception_handler)

# Pydantic validation errors
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Database errors
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(OperationalError, database_error_handler)

# Catch-all for unexpected errors (must be last)
app.add_exception_handler(Exception, generic_exception_handler)


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "ERP API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs"
    }
