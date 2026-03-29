"""Project component note schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ProjectComponentNoteBase(BaseModel):
    """Base project component note schema"""
    project_component_id: int
    name: str
    description: str


class ProjectComponentNoteCreate(ProjectComponentNoteBase):
    """Project component note creation schema"""
    pass


class ProjectComponentNoteUpdate(BaseModel):
    """Project component note update schema"""
    name: str | None = None
    description: str | None = None



class ProjectComponentNoteResponse(ProjectComponentNoteBase):
    """Project component note response schema"""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
