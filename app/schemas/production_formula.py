"""Production Formula schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class ProductionFormulaBase(BaseModel):
    """Base production formula schema"""
    formula_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    version: int = Field(default=1, ge=1)
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    is_active: bool = True
    is_default: bool = False


class ProductionFormulaCreate(ProductionFormulaBase):
    """Production formula creation schema (workspace_id and created_by injected by service)"""
    pass


class ProductionFormulaUpdate(BaseModel):
    """Production formula update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ProductionFormulaInDB(ProductionFormulaBase):
    """Production formula schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProductionFormulaResponse(ProductionFormulaInDB):
    """Production formula response schema"""
    pass
