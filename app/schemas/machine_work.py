"""Schemas for upcoming machine work (open work orders)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MachineUpcomingWorkSources(BaseModel):
    """Counts of upcoming work items by source type."""

    work_orders: int = 0


class MachineUpcomingWorkItem(BaseModel):
    """A single upcoming work item for a machine."""

    kind: str = Field(description="work_order")
    source_id: int
    date: date
    title: str
    status: str | None = None
    work_order_type_name: str | None = None


class MachineUpcomingWorkRow(BaseModel):
    """Aggregated upcoming work for one machine."""

    machine_id: int
    name: str
    factory_id: int
    factory_section_id: int | None = None
    section_name: str | None = None
    earliest_date: date
    count: int
    sources: MachineUpcomingWorkSources
    items: list[MachineUpcomingWorkItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
