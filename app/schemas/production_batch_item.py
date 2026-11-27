"""Production Batch Item schemas"""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductionBatchItemBase(BaseModel):
    """Base production batch item schema"""
    batch_id: int
    item_id: int
    item_role: str = Field(..., pattern=r'^(input|output|waste|byproduct)$')
    expected_quantity: int | None = Field(None, gt=0)
    actual_quantity: int | None = Field(None, gt=0)
    source_location_type: str | None = Field(None, max_length=50)
    source_location_id: int | None = None
    destination_location_type: str | None = Field(None, max_length=50)
    destination_location_id: int | None = None
    notes: str | None = None


class ProductionBatchItemCreate(ProductionBatchItemBase):
    """Production batch item creation schema (workspace_id injected by service)"""


class ProductionBatchItemUpdate(BaseModel):
    """Production batch item update schema"""
    item_role: str | None = Field(None, pattern=r'^(input|output|waste|byproduct)$')
    expected_quantity: int | None = Field(None, gt=0)
    actual_quantity: int | None = Field(None, gt=0)
    source_location_type: str | None = Field(None, max_length=50)
    source_location_id: int | None = None
    destination_location_type: str | None = Field(None, max_length=50)
    destination_location_id: int | None = None
    notes: str | None = None


class ProductionBatchItemInDB(ProductionBatchItemBase):
    """Production batch item schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    variance_quantity: int | None = None
    variance_percentage: Decimal | None = None


class ProductionBatchItemResponse(ProductionBatchItemInDB):
    """Production batch item response schema"""
