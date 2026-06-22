"""Machine activity event schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MachineActivityEventChange(BaseModel):
    field: str
    label: str
    from_value: str | None = None
    to_value: str | None = None


class MachineActivityEventMetadata(BaseModel):
    changes: list[MachineActivityEventChange] | None = None
    item_id: int | None = None
    item_name: str | None = None
    machine_item_id: int | None = None
    maintenance_log_id: int | None = None
    transfer_order_id: int | None = None
    purchase_order_id: int | None = None
    work_order_id: int | None = None
    quantity: int | None = None
    status: str | None = None


class MachineActivityEventResponse(BaseModel):
    id: int
    workspace_id: int
    machine_id: int
    event_type: str
    description: str
    metadata: MachineActivityEventMetadata | None = None
    performed_by: int | None = None
    performer_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
