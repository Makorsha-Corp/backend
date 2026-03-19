"""Machine maintenance log schemas"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.models.enums import MaintenanceTypeEnum


class MachineMaintenanceLogCreate(BaseModel):
    """Create maintenance log"""
    machine_id: int
    maintenance_type: MaintenanceTypeEnum
    maintenance_date: date
    summary: str
    cost: Decimal | None = None
    performed_by: str | None = None


class MachineMaintenanceLogUpdate(BaseModel):
    """Update maintenance log"""
    maintenance_type: MaintenanceTypeEnum | None = None
    maintenance_date: date | None = None
    summary: str | None = None
    cost: Decimal | None = None
    performed_by: str | None = None


class MachineMaintenanceLogResponse(BaseModel):
    """Maintenance log response"""
    id: int
    workspace_id: int
    machine_id: int
    maintenance_type: MaintenanceTypeEnum
    maintenance_date: date
    summary: str
    cost: Decimal | None = None
    performed_by: str | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
