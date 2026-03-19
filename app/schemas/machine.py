"""Machine schemas"""
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class MachineBase(BaseModel):
    """Base machine schema"""
    name: str
    factory_section_id: int


class MachineCreate(MachineBase):
    """Machine creation schema"""
    model_config = ConfigDict(protected_namespaces=())

    model_number: str | None = None
    manufacturer: str | None = None
    next_maintenance_schedule: date | None = None
    next_maintenance_note: str | None = None
    note: str | None = None


class MachineUpdate(BaseModel):
    """Machine update schema"""
    model_config = ConfigDict(protected_namespaces=())

    name: str | None = None
    factory_section_id: int | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    next_maintenance_schedule: date | None = None
    next_maintenance_note: str | None = None
    note: str | None = None


class MachineResponse(BaseModel):
    """Machine response schema"""
    id: int
    workspace_id: int
    name: str
    is_running: bool
    factory_section_id: int

    # Machine metadata
    model_number: str | None = None
    manufacturer: str | None = None
    next_maintenance_schedule: date | None = None
    next_maintenance_note: str | None = None
    note: str | None = None

    # Audit fields
    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    # Soft delete
    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
