"""Attachment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttachmentEntityTypeEnum


class AttachmentSignRequest(BaseModel):
    """Request a signed upload slot."""
    entity_type: AttachmentEntityTypeEnum
    entity_id: int = Field(..., ge=1)
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1, max_length=128)
    file_size: int = Field(..., ge=1)
    note: str | None = None


class AttachmentSignResponse(BaseModel):
    """Signed upload parameters for direct browser POST to Cloudinary."""
    attachment_id: int
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


class AttachmentConfirmRequest(BaseModel):
    """Optional client hint; server verifies via Cloudinary Admin API."""
    pass


class AttachmentDerivedUrls(BaseModel):
    """URLs derived from stored Cloudinary metadata."""
    thumb_url: str | None = None
    preview_url: str | None = None
    download_url: str | None = None


class AttachmentPdfPageResponse(BaseModel):
    """Signed JPG URL for one page of a PDF attachment."""
    url: str
    page: int
    page_count: int | None = None


class AttachmentLinkInfo(BaseModel):
    entity_type: AttachmentEntityTypeEnum
    entity_id: int

    model_config = ConfigDict(from_attributes=True)


class AttachmentResponse(BaseModel):
    """Attachment with derived delivery URLs."""
    id: int
    file_name: str
    mime_type: str
    file_size: int
    note: str | None
    uploaded_by: int
    uploaded_at: datetime
    upload_status: str
    public_id: str | None
    format: str | None
    version: int | None
    width: int | None
    height: int | None
    page_count: int | None = None
    file_url: str | None
    links: list[AttachmentLinkInfo] = Field(default_factory=list)
    urls: AttachmentDerivedUrls = Field(default_factory=AttachmentDerivedUrls)

    model_config = ConfigDict(from_attributes=True)


class AttachmentListResponse(BaseModel):
    """Ready attachments for display plus slot usage for per-entity cap."""
    items: list[AttachmentResponse]
    slot_count: int
    max_per_entity: int


class AttachmentCreateInternal(BaseModel):
    """Internal create payload for pending attachment row."""
    workspace_id: int
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: int
    note: str | None = None
    storage_provider: str = "cloudinary"
    public_id: str
    asset_folder: str | None = None
    resource_type: str = "image"
    delivery_type: str = "authenticated"
    upload_status: str = "pending"
    file_url: str | None = None


class AttachmentUpdateInternal(BaseModel):
    """Internal update after Cloudinary confirm."""
    file_url: str | None = None
    file_size: int | None = None
    format: str | None = None
    version: int | None = None
    width: int | None = None
    height: int | None = None
    page_count: int | None = None
    asset_id: str | None = None
    etag: str | None = None
    upload_status: str | None = None
    mime_type: str | None = None
