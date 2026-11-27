"""Production Formula Item schemas"""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductionFormulaItemBase(BaseModel):
    """Base production formula item schema"""
    formula_id: int
    item_id: int
    item_role: str = Field(..., pattern=r'^(input|output|waste|byproduct)$')
    quantity: int = Field(..., gt=0)
    unit: str | None = Field(None, max_length=20)
    is_optional: bool = False
    tolerance_percentage: Decimal | None = Field(None, ge=0, le=100)


class ProductionFormulaItemCreate(ProductionFormulaItemBase):
    """Production formula item creation schema (workspace_id injected by service)"""


class ProductionFormulaItemUpdate(BaseModel):
    """Production formula item update schema"""
    item_role: str | None = Field(None, pattern=r'^(input|output|waste|byproduct)$')
    quantity: int | None = Field(None, gt=0)
    unit: str | None = Field(None, max_length=20)
    is_optional: bool | None = None
    tolerance_percentage: Decimal | None = Field(None, ge=0, le=100)


class ProductionFormulaItemInDB(ProductionFormulaItemBase):
    """Production formula item schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int


class ProductionFormulaItemResponse(ProductionFormulaItemInDB):
    """Production formula item response schema"""
