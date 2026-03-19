"""Production Batch Item schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from decimal import Decimal


class ProductionBatchItemBase(BaseModel):
    """Base production batch item schema"""
    batch_id: int
    item_id: int
    item_role: str = Field(..., pattern=r'^(input|output|waste|byproduct)$')
    expected_quantity: Optional[int] = Field(None, gt=0)
    actual_quantity: Optional[int] = Field(None, gt=0)
    source_location_type: Optional[str] = Field(None, max_length=50)
    source_location_id: Optional[int] = None
    destination_location_type: Optional[str] = Field(None, max_length=50)
    destination_location_id: Optional[int] = None
    notes: Optional[str] = None


class ProductionBatchItemCreate(ProductionBatchItemBase):
    """Production batch item creation schema (workspace_id injected by service)"""
    pass


class ProductionBatchItemUpdate(BaseModel):
    """Production batch item update schema"""
    item_role: Optional[str] = Field(None, pattern=r'^(input|output|waste|byproduct)$')
    expected_quantity: Optional[int] = Field(None, gt=0)
    actual_quantity: Optional[int] = Field(None, gt=0)
    source_location_type: Optional[str] = Field(None, max_length=50)
    source_location_id: Optional[int] = None
    destination_location_type: Optional[str] = Field(None, max_length=50)
    destination_location_id: Optional[int] = None
    notes: Optional[str] = None


class ProductionBatchItemInDB(ProductionBatchItemBase):
    """Production batch item schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    variance_quantity: Optional[int] = None
    variance_percentage: Optional[Decimal] = None


class ProductionBatchItemResponse(ProductionBatchItemInDB):
    """Production batch item response schema"""
    pass
