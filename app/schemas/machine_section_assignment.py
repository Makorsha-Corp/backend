"""Machine section assignment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MachineSectionAssignmentCreate(BaseModel):
    machine_id: int
    factory_section_id: int


class MachineSectionAssignmentResponse(BaseModel):
    id: int
    workspace_id: int
    machine_id: int
    factory_section_id: int
    created_at: datetime
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
