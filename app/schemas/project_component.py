"""Project component schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import ProjectStatusEnum


class ProjectComponentBase(BaseModel):
    """Base project component schema"""
    project_id: int
    name: str
    description: str | None = None
    budget: float | None = None
    deadline: datetime | None = None
    status: ProjectStatusEnum = ProjectStatusEnum.PLANNING


class ProjectComponentCreate(ProjectComponentBase):
    """Project component creation schema"""
    pass


class ProjectComponentUpdate(BaseModel):
    """Project component update schema"""
    name: str | None = None
    description: str | None = None
    budget: float | None = None
    deadline: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: ProjectStatusEnum | None = None


class ProjectComponentResponse(ProjectComponentBase):
    """Project component response schema"""
    id: int
    created_at: datetime
    start_date: datetime | None
    end_date: datetime | None

    model_config = ConfigDict(from_attributes=True)
