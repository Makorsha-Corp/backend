"""Per-step material quantity schemas."""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductionBatchStageItemInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_id: int
    batch_stage_log_id: int
    item_id: int
    item_role: str
    expected_quantity: Optional[Decimal] = None
    actual_quantity: Optional[Decimal] = None


class ProductionBatchStageItemResponse(ProductionBatchStageItemInDB):
    pass


class ProductionBatchStageItemUpdate(BaseModel):
    actual_quantity: Optional[Decimal] = Field(
        None,
        description="Null clears the override and the step uses expected_quantity",
    )
