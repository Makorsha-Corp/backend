"""Production formula stage item schemas."""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductionFormulaStageItemBase(BaseModel):
    item_id: int
    item_role: str = Field(..., pattern=r"^(input|output|waste|byproduct)$")
    quantity: Decimal = Field(..., gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    is_optional: bool = False
    tolerance_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class ProductionFormulaStageItemCreate(ProductionFormulaStageItemBase):
    formula_stage_id: int


class ProductionFormulaStageItemAddBody(ProductionFormulaStageItemBase):
    """Request body for POST; formula_stage_id comes from the URL path."""

    pass


class ProductionFormulaStageItemUpdate(BaseModel):
    item_role: Optional[str] = Field(None, pattern=r"^(input|output|waste|byproduct)$")
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    is_optional: Optional[bool] = None
    tolerance_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class ProductionFormulaStageItemInDB(ProductionFormulaStageItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    formula_stage_id: int


class ProductionFormulaStageItemResponse(ProductionFormulaStageItemInDB):
    pass
