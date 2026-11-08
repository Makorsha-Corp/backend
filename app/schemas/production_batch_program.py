"""Production batch program schemas."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductionBatchProgramCreate(BaseModel):
    """Fields a caller sends to start a recurring batch program."""

    factory_id: int
    formula_id: int
    first_start_at: datetime
    cadence: Literal["daily", "weekly", "monthly", "custom"]
    interval_days: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description="Every N days when cadence is custom",
    )
    end_date: date

    @model_validator(mode="after")
    def validate_custom_interval(self) -> "ProductionBatchProgramCreate":
        if self.cadence == "custom":
            if self.interval_days is None:
                raise ValueError("interval_days is required when cadence is custom")
        elif self.interval_days is not None:
            raise ValueError("interval_days is only allowed when cadence is custom")
        return self


class ProductionBatchProgramOccurrence(BaseModel):
    """One batch created by a recurring program."""

    batch_id: int
    batch_number: str
    status: str
    planned_start_at: Optional[datetime] = None


class ProductionBatchProgramResponse(BaseModel):
    """Program row plus how many batches belong to it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    factory_id: int
    formula_id: int
    first_start_at: datetime
    cadence: str
    interval_days: int | None = None
    end_date: date
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    batch_count: int
    occurrences: list[ProductionBatchProgramOccurrence] = []
