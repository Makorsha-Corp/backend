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
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/erp_db"

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

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
