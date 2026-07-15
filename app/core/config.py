"""
Application configuration settings
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ERP API"
    VERSION: str = "1.0.0"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/marker_db"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    # Short access token + long refresh token (rotation + reuse detection
    # in the AuthService). 15 / 14 mirrors the industry default.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # SSLCommerz payment gateway
    # MOCK_MODE must be False before STORE_ID/STORE_PASSWORD are real credentials.
    SSLCOMMERZ_MOCK_MODE: bool = True
    SSLCOMMERZ_STORE_ID: str = ""
    SSLCOMMERZ_STORE_PASSWORD: str = ""
    SSLCOMMERZ_SANDBOX: bool = True
    # Base URL the frontend is served from (used to build the redirect target
    # after the mock/real gateway hands control back to us)
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    # Base URL this backend is reachable at (used to build success/fail/cancel/ipn
    # callback URLs and, in mock mode, the fake GatewayPageURL)
    BACKEND_BASE_URL: str = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()

_DEFAULT_SECRET = "your-secret-key-change-this-in-production"
if settings.ENVIRONMENT == "production" and settings.SECRET_KEY == _DEFAULT_SECRET:
    raise RuntimeError(
        "SECRET_KEY must be changed from the default before running in production."
    )
