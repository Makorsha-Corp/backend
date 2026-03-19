"""Status schemas"""
from pydantic import BaseModel, ConfigDict


class StatusBase(BaseModel):
    """Base status schema"""
    name: str
    comment: str


class StatusCreate(StatusBase):
    """Status creation schema"""
    pass


class StatusUpdate(BaseModel):
    """Status update schema"""
    name: str | None = None
    comment: str | None = None


class StatusResponse(StatusBase):
    """Status response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
