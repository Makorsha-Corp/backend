"""Work order program schemas."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import WorkOrderPriorityEnum
from app.schemas.work_order import WorkOrderSheetApproverLine, WorkOrderSheetItemLine


class WorkOrderProgramCreate(BaseModel):
    """Create a recurring program and one draft work order per occurrence."""

    machine_id: int
    work_order_type_id: int
    planned_date: date = Field(description="First occurrence (recurrence start)")
    end_date: date
    cadence: Literal["daily", "weekly", "monthly", "custom"]
    interval_days: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description="Every N days when cadence is custom",
    )
    title: str | None = None

    @model_validator(mode="after")
    def validate_custom_interval(self) -> "WorkOrderProgramCreate":
        if self.cadence == "custom":
            if self.interval_days is None:
                raise ValueError("interval_days is required when cadence is custom")
        elif self.interval_days is not None:
            raise ValueError("interval_days is only allowed when cadence is custom")
        return self
    description: str | None = None
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    assigned_to: str | None = None
    account_id: int | None = None
    cost: Decimal | None = None
    template_id: int | None = None
    shift_id: int | None = None
    planned_start_time: time | None = None
    expected_duration_minutes: int | None = Field(default=None, gt=0)
    items: List[WorkOrderSheetItemLine] = []
    approvers: List[WorkOrderSheetApproverLine] = []


class WorkOrderProgramOccurrence(BaseModel):
    work_order_id: int
    work_order_number: str
    status: str
    planned_date: date | None = None


class WorkOrderProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    factory_id: int
    machine_id: int
    work_order_type_id: int
    title: str
    work_order_template_id: int | None = None
    cadence: str
    interval_days: int | None = None
    start_date: date
    end_date: date
    shift_id: int | None = None
    planned_start_time: time | None = None
    expected_duration_minutes: int | None = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    work_order_count: int
    occurrences: list[WorkOrderProgramOccurrence] = []
