"""WorkspaceAuditLog schemas"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class WorkspaceAuditLogBase(BaseModel):
    """Base workspace audit log schema"""

    model_config = ConfigDict(populate_by_name=True)

    workspace_id: int | None
    user_id: int | None
    action: str
    resource_type: str | None = None
    resource_id: int | None = None
    metadata: dict | None = Field(default=None, alias="metadata_json")


class WorkspaceAuditLogCreate(WorkspaceAuditLogBase):
    """Workspace audit log creation schema"""
    ip_address: str | None = None
    user_agent: str | None = None


class WorkspaceAuditLogResponse(WorkspaceAuditLogBase):
    """Workspace audit log response schema"""
    id: int
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkspaceAuditLogWithDetails(WorkspaceAuditLogResponse):
    """Workspace audit log response with user details"""
    user_name: str | None = None
    user_email: str | None = None
