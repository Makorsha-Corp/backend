"""Mobile upload session schemas."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AttachmentEntityTypeEnum, MobileUploadSessionStatusEnum


class MobileUploadSessionCreateRequest(BaseModel):
    entity_type: AttachmentEntityTypeEnum
    entity_id: int = Field(..., ge=1)
    entity_label: str | None = Field(None, max_length=80)


class MobileUploadSessionCreateResponse(BaseModel):
    session_id: int
    token: str
    expires_at: datetime
    entity_label: str | None = None


class MobileUploadSessionResponse(BaseModel):
    id: int
    status: MobileUploadSessionStatusEnum
    entity_type: AttachmentEntityTypeEnum
    entity_id: int
    entity_label: str | None = None
    expires_at: datetime
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    preview_url: str | None = None


class MobileUploadPromoteRequest(BaseModel):
    file_name: str | None = Field(None, max_length=255)
    note: str | None = Field(None, max_length=500)


class MobileUploadPublicSessionResponse(BaseModel):
    status: MobileUploadSessionStatusEnum
    entity_label: str | None = None
    expires_at: datetime


class MobileUploadPublicSignRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1, max_length=128)
    file_size: int = Field(..., ge=1)


class MobileUploadPublicSignResponse(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    public_id: str
    asset_folder: str
    display_name: str
    type: str = "authenticated"
    signature: str
    resource_type: str = "image"
    upload_url: str


class MobileUploadPublicConfirmRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)
