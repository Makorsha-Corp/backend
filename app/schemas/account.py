"""Account schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class AccountBase(BaseModel):
    """Base account schema"""
    name: str = Field(..., min_length=1, max_length=255)
    account_code: Optional[str] = Field(None, max_length=50)

    # Contact info
    primary_contact_person: Optional[str] = Field(None, max_length=255)
    primary_email: Optional[str] = Field(None, max_length=255)
    primary_phone: Optional[str] = Field(None, max_length=50)

    # Address
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)

    # Financial
    payment_terms: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=100)

    # Notes
    notes: Optional[str] = None

    # Admin Controls
    allow_invoices: bool = True
    invoices_disabled_reason: Optional[str] = None

    # Status
    is_active: bool = True


class AccountCreate(AccountBase):
    """Schema for creating an account (workspace_id injected by service)"""
    tag_ids: List[int] = []  # List of tag IDs to assign


class AccountUpdate(BaseModel):
    """Schema for updating an account"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_code: Optional[str] = Field(None, max_length=50)

    # Contact info
    primary_contact_person: Optional[str] = Field(None, max_length=255)
    primary_email: Optional[str] = Field(None, max_length=255)
    primary_phone: Optional[str] = Field(None, max_length=50)

    # Address
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)

    # Financial
    payment_terms: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=100)

    # Notes
    notes: Optional[str] = None

    # Admin Controls
    allow_invoices: Optional[bool] = None
    invoices_disabled_reason: Optional[str] = None

    # Status
    is_active: Optional[bool] = None
    tag_ids: Optional[List[int]] = None  # Update tags if provided


class AccountInDB(AccountBase):
    """Account schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_at: datetime
    created_by: Optional[int]
    updated_at: Optional[datetime]
    updated_by: Optional[int]
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]


class AccountResponse(AccountInDB):
    """Account response schema"""
    pass


class AccountWithTagsResponse(AccountInDB):
    """Account response schema with tags included"""
    tags: List[dict] = []  # List of tag objects with id, name, tag_code, color, icon
