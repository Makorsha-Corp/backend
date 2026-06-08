"""Account invoice schemas"""
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class AccountInvoiceBase(BaseModel):
    """Base account invoice schema"""
    account_id: int
    order_id: Optional[int] = None

    invoice_type: str = Field(..., pattern=r'^(payable|receivable)$')
    invoice_amount: Decimal = Field(..., ge=0)

    invoice_number: Optional[str] = Field(None, max_length=100)
    vendor_invoice_number: Optional[str] = Field(None, max_length=100)

    invoice_date: date
    due_date: Optional[date] = None

    description: Optional[str] = None
    notes: Optional[str] = None

    allow_payments: bool = True
    payment_locked_reason: Optional[str] = None


class AccountInvoiceCreate(AccountInvoiceBase):
    """Schema for creating an account invoice (workspace_id injected by service)"""
    pass


class AccountInvoiceUpdate(BaseModel):
    """Schema for updating an account invoice.

    invoice_status is NOT updatable here — use /confirm and /void endpoints.
    """
    account_id: Optional[int] = None
    order_id: Optional[int] = None

    invoice_type: Optional[str] = Field(None, pattern=r'^(payable|receivable)$')
    invoice_amount: Optional[Decimal] = Field(None, ge=0)

    invoice_number: Optional[str] = Field(None, max_length=100)
    vendor_invoice_number: Optional[str] = Field(None, max_length=100)

    invoice_date: Optional[date] = None
    due_date: Optional[date] = None

    description: Optional[str] = None
    notes: Optional[str] = None

    allow_payments: Optional[bool] = None
    payment_locked_reason: Optional[str] = None


class VoidInvoiceRequest(BaseModel):
    """Request body for voiding an invoice"""
    void_note: str = Field(..., min_length=1, description="Required reason for voiding")


class AccountInvoiceInDB(AccountInvoiceBase):
    """Account invoice schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int

    invoice_status: str  # 'draft', 'confirmed', 'locked', 'voided'
    paid_amount: Decimal
    payment_status: str

    void_note: Optional[str] = None

    created_at: datetime
    created_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None

    @computed_field
    @property
    def outstanding_amount(self) -> Decimal:
        """Calculate outstanding amount (invoice_amount - paid_amount)"""
        return self.invoice_amount - self.paid_amount


class AccountInvoiceResponse(AccountInvoiceInDB):
    """Account invoice response schema"""
    pass


class InvoiceStatusEntryResponse(BaseModel):
    """One row from invoice_status_tracker"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    from_status: str
    to_status: str
    changed_at: datetime
    changed_by: Optional[int] = None
    changed_by_name: Optional[str] = None
