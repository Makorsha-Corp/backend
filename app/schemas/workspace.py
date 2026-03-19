"""Workspace schemas"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Any


class WorkspaceBase(BaseModel):
    """Base workspace schema"""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class WorkspaceCreate(WorkspaceBase):
    """Workspace creation schema"""
    subscription_plan_id: int | None = None  # If None, use default plan
    billing_email: str | None = None


class WorkspaceUpdate(BaseModel):
    """Workspace update schema"""
    name: str | None = Field(None, min_length=1, max_length=255)
    billing_email: str | None = None
    settings: dict | None = None


class WorkspaceResponse(WorkspaceBase):
    """Workspace response schema"""
    id: int
    owner_user_id: int | None
    subscription_plan_id: int
    subscription_status: str
    trial_ends_at: datetime | None
    subscription_started_at: datetime | None
    subscription_ends_at: datetime | None
    billing_cycle: str | None
    billing_email: str | None

    # Usage stats
    current_members_count: int
    current_storage_mb: int
    current_orders_this_month: int
    current_factories_count: int
    current_machines_count: int
    current_projects_count: int

    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('trial_ends_at', 'subscription_started_at', 'subscription_ends_at', 'created_at', 'updated_at', mode='before')
    @classmethod
    def strip_datetime_whitespace(cls, v: Any) -> Any:
        """Strip whitespace from datetime strings (handles Windows line endings)"""
        if isinstance(v, str):
            return v.strip()
        return v


class WorkspaceWithPlan(WorkspaceResponse):
    """Workspace response with subscription plan details"""
    plan_name: str | None = None
    plan_display_name: str | None = None
    max_members: int | None = None
    max_storage_mb: int | None = None
    max_orders_per_month: int | None = None


class WorkspaceListItem(BaseModel):
    """Workspace list item (minimal info for workspace switcher)"""
    id: int
    name: str
    slug: str
    subscription_status: str
    role: str  # User's role in this workspace
    is_owner: bool

    model_config = ConfigDict(from_attributes=True)
