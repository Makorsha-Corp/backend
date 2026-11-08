"""Production formula stage parameter schemas."""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductionFormulaStageParameterBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    planned_value: str = Field(..., min_length=1)
    unit: Optional[str] = Field(None, max_length=40)
    sort_order: int = Field(0, ge=0)


class ProductionFormulaStageParameterCreate(ProductionFormulaStageParameterBase):
    formula_stage_id: int


class ProductionFormulaStageParameterAddBody(ProductionFormulaStageParameterBase):
    """Request body for POST; formula_stage_id comes from the URL path."""

    pass


class ProductionFormulaStageParameterUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=120)
    planned_value: Optional[str] = Field(None, min_length=1)
    unit: Optional[str] = Field(None, max_length=40)
    sort_order: Optional[int] = Field(None, ge=0)


class ProductionFormulaStageParameterInDB(ProductionFormulaStageParameterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    formula_stage_id: int
    planned_value_numeric: Optional[Decimal] = None


class ProductionFormulaStageParameterResponse(ProductionFormulaStageParameterInDB):
    pass

