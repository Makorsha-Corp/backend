"""Project schemas"""
from datetime import datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.enums import ProjectStatusEnum, ProjectPriorityEnum, ProjectVisibilityEnum


class ProjectBase(BaseModel):
    """Base project schema"""
    factory_id: int
    name: str
    description: str
    budget: Decimal | None = None
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
    budget: Decimal | None = None
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
    visibility: ProjectVisibilityEnum = ProjectVisibilityEnum.WORKSPACE
    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: int | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('visibility', mode='before')
    @classmethod
    def default_visibility(cls, value):
        if value is None:
            return ProjectVisibilityEnum.WORKSPACE
        return value


class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMemberResponse(BaseModel):
    id: int
    workspace_id: int
    project_id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    user_position: str | None = None
    assigned_by: int | None = None
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectMembersListResponse(BaseModel):
    members: List[ProjectMemberResponse]


class ProjectVisibilityUpdate(BaseModel):
    visibility: ProjectVisibilityEnum


class ProjectEventChange(BaseModel):
    field: str
    label: str
    from_value: str | None = None
    to_value: str | None = None


class ProjectEventMetadata(BaseModel):
    changes: list[ProjectEventChange] | None = None
    user_id: int | None = None
    user_name: str | None = None


class ProjectEventResponse(BaseModel):
    id: int
    workspace_id: int
    project_id: int
    event_type: str
    description: str
    metadata: ProjectEventMetadata | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
