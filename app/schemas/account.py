"""Account schemas"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccountBase(BaseModel):
    """Base account schema"""
    name: str = Field(..., min_length=1, max_length=255)
    account_code: str | None = Field(None, max_length=50)

    # Contact info
    primary_contact_person: str | None = Field(None, max_length=255)
    primary_email: str | None = Field(None, max_length=255)
    primary_phone: str | None = Field(None, max_length=50)
    secondary_contact_person: str | None = Field(None, max_length=255)
    secondary_email: str | None = Field(None, max_length=255)
    secondary_phone: str | None = Field(None, max_length=50)

    # Address
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)

    # Payment Preferences
    payment_preferences: str | None = None

    # Banking Info
    bank_details: str | None = None

    # Admin Controls
    allow_invoices: bool = True


class AccountCreate(AccountBase):
    """Schema for creating an account (workspace_id injected by service)"""
    tag_ids: list[int] = []  # List of tag IDs to assign


class AccountUpdate(BaseModel):
    """Schema for updating an account"""
    name: str | None = Field(None, min_length=1, max_length=255)
    account_code: str | None = Field(None, max_length=50)

    # Contact info
    primary_contact_person: str | None = Field(None, max_length=255)
    primary_email: str | None = Field(None, max_length=255)
    primary_phone: str | None = Field(None, max_length=50)
    secondary_contact_person: str | None = Field(None, max_length=255)
    secondary_email: str | None = Field(None, max_length=255)
    secondary_phone: str | None = Field(None, max_length=50)

    # Address
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)

    # Payment Preferences
    payment_preferences: str | None = None

    # Banking Info
    bank_details: str | None = None

    # Admin Controls
    allow_invoices: bool | None = None
    is_active: bool | None = None
    tag_ids: list[int] | None = None  # Update tags if provided


class AccountInDB(AccountBase):
    """Account schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    is_active: bool
    created_at: datetime


class AccountResponse(AccountInDB):
    """Account response schema"""


class AccountWithTagsResponse(AccountInDB):
    """Account response schema with tags included"""
    account_tags: list[dict] = []  # List of tag objects with id, name, tag_code, color, icon


class AccountOpenBalanceRollup(BaseModel):
    """Open invoice balances for one account."""
    payable_outstanding: Decimal = Decimal(0)
    receivable_outstanding: Decimal = Decimal(0)
    open_payable_count: int = 0
    open_receivable_count: int = 0
    has_overdue_payable: bool = False
    has_overdue_receivable: bool = False


class AccountHubRowResponse(AccountWithTagsResponse):
    """Account row for the accounts hub with open-balance rollups."""
    open_balance: AccountOpenBalanceRollup


class AccountHubListResponse(BaseModel):
    """Paginated accounts hub list."""
    items: list[AccountHubRowResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
