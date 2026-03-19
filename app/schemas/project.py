"""Project schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import ProjectStatusEnum, ProjectPriorityEnum


class ProjectBase(BaseModel):
    """Base project schema"""
    factory_id: int
    name: str
    description: str
    budget: float | None = None
    deadline: datetime | None = None
    priority: ProjectPriorityEnum = ProjectPriorityEnum.LOW
    status: ProjectStatusEnum = ProjectStatusEnum.PLANNING


class ProjectCreate(ProjectBase):
    """Project creation schema"""
    pass


class ProjectUpdate(BaseModel):
    """Project update schema"""
    name: str | None = None
    description: str | None = None
    budget: float | None = None
    deadline: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    priority: ProjectPriorityEnum | None = None
    status: ProjectStatusEnum | None = None


class ProjectResponse(ProjectBase):
    """Project response schema"""
    id: int
    workspace_id: int
    created_at: datetime
    created_by: int | None
    updated_at: datetime | None
    updated_by: int | None
    start_date: datetime | None
    end_date: datetime | None
    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: int | None

    model_config = ConfigDict(from_attributes=True)
