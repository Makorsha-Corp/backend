"""Production formula stage schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ProductionFormulaStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(..., ge=1)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    expected_output_quantity: Optional[int] = Field(None, ge=0)
    expected_output_item_id: Optional[int] = None
    notes: Optional[str] = None


class ProductionFormulaStageCreate(ProductionFormulaStageBase):
    formula_id: int


class ProductionFormulaStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    stage_order: Optional[int] = Field(None, ge=1)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    expected_output_quantity: Optional[int] = Field(None, ge=0)
    expected_output_item_id: Optional[int] = None
    notes: Optional[str] = None


class ProductionFormulaStageInDB(ProductionFormulaStageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    formula_id: int


class ProductionFormulaStageResponse(ProductionFormulaStageInDB):
    pass
