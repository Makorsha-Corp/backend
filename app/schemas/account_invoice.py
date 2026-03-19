"""Account invoice schemas"""
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class AccountInvoiceBase(BaseModel):
    """Base account invoice schema"""
    account_id: int
    order_id: Optional[int] = None

    # Invoice Type
    invoice_type: str = Field(..., pattern=r'^(payable|receivable)$')

    # Amounts
    invoice_amount: Decimal = Field(..., ge=0)

    # Reference Numbers
    invoice_number: Optional[str] = Field(None, max_length=100)
    vendor_invoice_number: Optional[str] = Field(None, max_length=100)

    # Dates
    invoice_date: date
    due_date: Optional[date] = None

    # Description
    description: Optional[str] = None
    notes: Optional[str] = None

    # Admin Controls
    allow_payments: bool = True
    payment_locked_reason: Optional[str] = None


class AccountInvoiceCreate(AccountInvoiceBase):
    """Schema for creating an account invoice (workspace_id injected by service)"""
    pass


class AccountInvoiceUpdate(BaseModel):
    """Schema for updating an account invoice"""
    account_id: Optional[int] = None
    order_id: Optional[int] = None

    # Invoice Type
    invoice_type: Optional[str] = Field(None, pattern=r'^(payable|receivable)$')

    # Amounts
    invoice_amount: Optional[Decimal] = Field(None, ge=0)

    # Reference Numbers
    invoice_number: Optional[str] = Field(None, max_length=100)
    vendor_invoice_number: Optional[str] = Field(None, max_length=100)

    # Dates
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None

    # Status
    payment_status: Optional[str] = Field(None, pattern=r'^(unpaid|partial|paid|overdue)$')

    # Description
    description: Optional[str] = None
    notes: Optional[str] = None

    # Admin Controls
    allow_payments: Optional[bool] = None
    payment_locked_reason: Optional[str] = None


class AccountInvoiceInDB(AccountInvoiceBase):
    """Account invoice schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    paid_amount: Decimal
    payment_status: str
    created_at: datetime
    created_by: Optional[int]
    updated_at: Optional[datetime]
    updated_by: Optional[int]

    @computed_field
    @property
    def outstanding_amount(self) -> Decimal:
        """Calculate outstanding amount (invoice_amount - paid_amount)"""
        return self.invoice_amount - self.paid_amount


class AccountInvoiceResponse(AccountInvoiceInDB):
    """Account invoice response schema"""
    pass
