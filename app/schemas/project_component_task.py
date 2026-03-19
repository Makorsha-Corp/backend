"""Project component task schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import TaskPriorityEnum


class ProjectComponentTaskBase(BaseModel):
    """Base project component task schema"""
    project_component_id: int
    name: str
    description: str
    is_note: bool = False
    task_priority: TaskPriorityEnum | None = None


class ProjectComponentTaskCreate(ProjectComponentTaskBase):
    """Project component task creation schema"""
    pass


class ProjectComponentTaskUpdate(BaseModel):
    """Project component task update schema"""
    name: str | None = None
    description: str | None = None
    is_completed: bool | None = None
    is_note: bool | None = None
    task_priority: TaskPriorityEnum | None = None


class ProjectComponentTaskResponse(ProjectComponentTaskBase):
    """Project component task response schema"""
    id: int
    created_at: datetime
    is_completed: bool

    model_config = ConfigDict(from_attributes=True)
