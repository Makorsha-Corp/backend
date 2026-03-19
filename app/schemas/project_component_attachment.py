"""Project component attachment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProjectComponentAttachmentBase(BaseModel):
    """Base project component attachment schema"""
    project_component_id: int
    attachment_id: int


class ProjectComponentAttachmentCreate(ProjectComponentAttachmentBase):
    """Project component attachment creation schema"""
    attached_by: int


class ProjectComponentAttachmentResponse(ProjectComponentAttachmentBase):
    """Project component attachment response schema"""
    id: int
    attached_at: datetime
    attached_by: int

    model_config = ConfigDict(from_attributes=True)
