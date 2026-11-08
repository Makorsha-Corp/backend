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
    is_active: bool = True
    is_default: bool = False
    route_id: Optional[int] = None


class ProductionFormulaCreate(BaseModel):
    """Create a recipe. A private route is created per recipe (or copied from another recipe)."""
    formula_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    version: int = Field(default=1, ge=1)
    is_active: bool = True
    is_default: bool = False
    factory_id: Optional[int] = Field(
        None,
        description="Required for a blank recipe. Ignored when copy_from_formula_id is set.",
    )
    copy_from_formula_id: Optional[int] = Field(
        None,
        description="Duplicate path, stages, and stage materials from this recipe.",
    )


class ProductionFormulaCopy(BaseModel):
    formula_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    factory_id: int
    description: Optional[str] = None


class ProductionFormulaUpdate(BaseModel):
    """Production formula update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
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
