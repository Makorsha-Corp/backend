"""Production batch stage parameter schemas."""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductionBatchStageParameterInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_id: int
    batch_stage_log_id: int
    label: str
    planned_value: str
    planned_value_numeric: Optional[Decimal] = None
    actual_value: Optional[str] = None
    actual_value_numeric: Optional[Decimal] = None
    unit: Optional[str] = None
    source_parameter_id: Optional[int] = None


class ProductionBatchStageParameterResponse(ProductionBatchStageParameterInDB):
    pass


class ProductionBatchStageParameterUpdate(BaseModel):
    actual_value: Optional[str] = Field(None, description="Null clears the actual value")
    planned_value: Optional[str] = Field(None, description="Batch-specific planned value for this condition")


# Backward-compatible alias for imports
ProductionBatchStageParameterActualUpdate = ProductionBatchStageParameterUpdate

