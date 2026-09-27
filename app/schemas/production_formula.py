"""Production Formula schemas"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductionFormulaBase(BaseModel):
    """Base production formula schema"""
    formula_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    version: int = Field(default=1, ge=1)
    estimated_duration_minutes: int | None = Field(None, ge=0)
    is_active: bool = True
    is_default: bool = False


class ProductionFormulaCreate(ProductionFormulaBase):
    """Production formula creation schema (workspace_id and created_by injected by service)"""


class ProductionFormulaUpdate(BaseModel):
    """Production formula update schema"""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    estimated_duration_minutes: int | None = Field(None, ge=0)
    is_active: bool | None = None
    is_default: bool | None = None


class ProductionFormulaInDB(ProductionFormulaBase):
    """Production formula schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime


class ProductionFormulaResponse(ProductionFormulaInDB):
    """Production formula response schema"""
