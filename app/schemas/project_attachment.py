"""Project attachment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProjectAttachmentBase(BaseModel):
    """Base project attachment schema"""
    project_id: int
    attachment_id: int


class ProjectAttachmentCreate(ProjectAttachmentBase):
    """Project attachment creation schema"""
    attached_by: int


class ProjectAttachmentResponse(ProjectAttachmentBase):
    """Project attachment response schema"""
    id: int
    attached_at: datetime
    attached_by: int

    model_config = ConfigDict(from_attributes=True)
