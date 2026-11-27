"""Production formula stage schemas"""

from pydantic import BaseModel, ConfigDict, Field


class ProductionFormulaStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(..., ge=1)
    production_line_id: int | None = None
    machine_id: int | None = None
    expected_duration_minutes: int | None = Field(None, ge=0)
    expected_output_quantity: int | None = Field(None, ge=0)
    expected_output_item_id: int | None = None
    notes: str | None = None


class ProductionFormulaStageCreate(ProductionFormulaStageBase):
    formula_id: int


class ProductionFormulaStageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    stage_order: int | None = Field(None, ge=1)
    production_line_id: int | None = None
    machine_id: int | None = None
    expected_duration_minutes: int | None = Field(None, ge=0)
    expected_output_quantity: int | None = Field(None, ge=0)
    expected_output_item_id: int | None = None
    notes: str | None = None


class ProductionFormulaStageInDB(ProductionFormulaStageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    formula_id: int


class ProductionFormulaStageResponse(ProductionFormulaStageInDB):
    pass
