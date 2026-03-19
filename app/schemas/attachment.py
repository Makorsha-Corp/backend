"""Attachment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AttachmentBase(BaseModel):
    """Base attachment schema"""
    file_url: str
    file_name: str
    mime_type: str
    file_size: int
    note: str | None = None


class AttachmentCreate(AttachmentBase):
    """Attachment creation schema"""
    uploaded_by: int


class AttachmentUpdate(BaseModel):
    """Attachment update schema"""
    file_url: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    note: str | None = None


class AttachmentSoftDelete(BaseModel):
    """Attachment soft delete schema"""
    deleted_by: int


class AttachmentResponse(AttachmentBase):
    """Attachment response schema"""
    id: int
    uploaded_by: int
    uploaded_at: datetime
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: int | None

    model_config = ConfigDict(from_attributes=True)
