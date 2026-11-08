"""Production route schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductionRouteBase(BaseModel):
    factory_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: bool = True


class ProductionRouteCreate(ProductionRouteBase):
    pass


class ProductionRouteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ProductionRouteResponse(ProductionRouteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProductionRouteStepCreate(BaseModel):
    production_line_id: int
    step_order: int = Field(..., ge=1)
    name: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class ProductionRouteStepUpdate(BaseModel):
    production_line_id: Optional[int] = None
    step_order: Optional[int] = Field(None, ge=1)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = None


class ProductionRouteStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    route_id: int
    step_order: int
    production_line_id: int
    name: str
    notes: Optional[str] = None
