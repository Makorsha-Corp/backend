"""Production Formula Item schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from decimal import Decimal


class ProductionFormulaItemBase(BaseModel):
    """Base production formula item schema"""
    formula_id: int
    item_id: int
    item_role: str = Field(..., pattern=r'^(input|output|waste|byproduct)$')
    quantity: int = Field(..., gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    is_optional: bool = False
    tolerance_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class ProductionFormulaItemCreate(ProductionFormulaItemBase):
    """Production formula item creation schema (workspace_id injected by service)"""
    pass


class ProductionFormulaItemUpdate(BaseModel):
    """Production formula item update schema"""
    item_role: Optional[str] = Field(None, pattern=r'^(input|output|waste|byproduct)$')
    quantity: Optional[int] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    is_optional: Optional[bool] = None
    tolerance_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class ProductionFormulaItemInDB(ProductionFormulaItemBase):
    """Production formula item schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int


class ProductionFormulaItemResponse(ProductionFormulaItemInDB):
    """Production formula item response schema"""
    pass
