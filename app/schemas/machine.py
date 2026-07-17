"""Machine schemas"""
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict
from app.models.enums import MachineEventTypeEnum


class MachineBase(BaseModel):
    """Base machine schema"""
    name: str
    factory_id: int
    # Optional organizational label — if given, creates a section assignment.
    factory_section_id: int | None = None


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
    factory_id: int | None = None
    # Explicit null clears the section assignment — distinguished from "not provided"
    # via model_fields_set in the manager, same convention as WorkOrderUpdate.
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
    factory_id: int
    # Read-only convenience fields resolved from machine_section_assignments —
    # not real columns on Machine, null when the machine has no section.
    factory_section_id: int | None = None
    factory_section_name: str | None = None

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

    latest_status_type: MachineEventTypeEnum | None = None
    latest_status_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
