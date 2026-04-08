"""Account schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class AccountBase(BaseModel):
    """Base account schema"""
    name: str = Field(..., min_length=1, max_length=255)
    account_code: Optional[str] = Field(None, max_length=50)
    contact_details: Optional[str] = None
    address_fields: Optional[str] = None
    payment_terms: Optional[str] = Field(None, max_length=50)
    bank_details: Optional[str] = None

    # Admin Controls
    allow_invoices: bool = True


class AccountCreate(AccountBase):
    """Schema for creating an account (workspace_id injected by service)"""
    tag_ids: List[int] = []  # List of tag IDs to assign


class AccountUpdate(BaseModel):
    """Schema for updating an account"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_code: Optional[str] = Field(None, max_length=50)
    contact_details: Optional[str] = None
    address_fields: Optional[str] = None
    payment_terms: Optional[str] = Field(None, max_length=50)
    bank_details: Optional[str] = None

    # Admin Controls
    allow_invoices: Optional[bool] = None
    tag_ids: Optional[List[int]] = None  # Update tags if provided


class AccountInDB(AccountBase):
    """Account schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_at: datetime


class AccountResponse(AccountInDB):
    """Account response schema"""
    pass


class AccountWithTagsResponse(AccountInDB):
    """Account response schema with tags included"""
    account_tags: List[dict] = []  # List of tag objects with id, name, tag_code, color, icon
