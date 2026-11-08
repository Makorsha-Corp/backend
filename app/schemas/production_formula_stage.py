"""Production formula stage schemas"""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ProductionFormulaStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(..., ge=1)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    expected_output_quantity: Optional[Decimal] = Field(None, ge=0)
    expected_output_item_id: Optional[int] = None
    notes: Optional[str] = None
    is_used: bool = True


class RecipeRouteStepAdd(BaseModel):
    production_line_id: int
    name: Optional[str] = None
    factory_id: Optional[int] = Field(
        None,
        description="Required when this recipe has no private route yet (legacy rows).",
    )


class ProductionFormulaStageCreate(ProductionFormulaStageBase):
    formula_id: int


class ProductionFormulaStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    stage_order: Optional[int] = Field(None, ge=1)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    expected_output_quantity: Optional[Decimal] = Field(None, ge=0)
    expected_output_item_id: Optional[int] = None
    notes: Optional[str] = None
    is_used: Optional[bool] = None


class ProductionFormulaStageInDB(ProductionFormulaStageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    formula_id: int
    route_step_id: Optional[int] = None


class ProductionFormulaStageResponse(ProductionFormulaStageInDB):
    pass
