"""Account invoice schemas"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AccountInvoiceBase(BaseModel):
    """Base account invoice schema"""
    account_id: int
    order_id: int | None = None
    order_type: str | None = Field(None, max_length=30)

    invoice_type: str = Field(..., pattern=r'^(payable|receivable)$')
    invoice_amount: Decimal = Field(..., ge=0)

    invoice_number: str | None = Field(None, max_length=100)
    vendor_invoice_number: str | None = Field(None, max_length=100)

    invoice_date: date
    due_date: date | None = None

    description: str | None = None
    notes: str | None = None

    allow_payments: bool = True
    payment_locked_reason: str | None = None


class AccountInvoiceCreate(AccountInvoiceBase):
    """Schema for creating an account invoice (workspace_id injected by service)"""


class AccountInvoiceUpdate(BaseModel):
    """Schema for updating an account invoice.

    invoice_status is NOT updatable here — use /confirm and /void endpoints.
    """
    account_id: int | None = None
    order_id: int | None = None

    invoice_type: str | None = Field(None, pattern=r'^(payable|receivable)$')
    invoice_amount: Decimal | None = Field(None, ge=0)

    invoice_number: str | None = Field(None, max_length=100)
    vendor_invoice_number: str | None = Field(None, max_length=100)

    invoice_date: date | None = None
    due_date: date | None = None

    description: str | None = None
    notes: str | None = None

    allow_payments: bool | None = None
    payment_locked_reason: str | None = None


class VoidInvoiceRequest(BaseModel):
    """Request body for voiding an invoice"""
    void_note: str = Field(..., min_length=1, description="Required reason for voiding")


class AccountInvoiceInDB(AccountInvoiceBase):
    """Account invoice schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int

    invoice_status: str  # 'draft', 'confirmed', 'voided'
    paid_amount: Decimal
    payment_status: str

    receiving_started: bool = False
    last_synced_at: datetime | None = None

    void_note: str | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    @computed_field
    @property
    def outstanding_amount(self) -> Decimal:
        """Outstanding balance; voided invoices always return zero."""
        if self.invoice_status == 'voided':
            return Decimal('0.00')
        return self.invoice_amount - self.paid_amount


class AccountInvoiceResponse(AccountInvoiceInDB):
    """Account invoice response schema"""


class AccountInvoiceSummaryResponse(BaseModel):
    """Aggregated invoice totals for an account with optional filters."""
    invoice_count: int
    invoiced_total: Decimal
    paid_total: Decimal
    outstanding_total: Decimal


class AccountInvoiceListResponse(BaseModel):
    """Paginated account invoice list."""
    items: list[AccountInvoiceResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class InvoiceHubTypeSummary(BaseModel):
    """Workspace-level open-balance summary for one invoice type."""
    open_count: int
    outstanding_total: Decimal
    overdue_count: int
    accounts_with_open_count: int


class AccountInvoicesHubSummaryResponse(BaseModel):
    """Workspace accounts hub invoice KPIs."""
    payable: InvoiceHubTypeSummary
    receivable: InvoiceHubTypeSummary
    total_active_accounts: int
    accounts_with_any_open_balance: int


class InvoiceStatusEntryResponse(BaseModel):
    """One row from invoice_status_tracker"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    from_status: str
    to_status: str
    changed_at: datetime
    changed_by: int | None = None
    changed_by_name: str | None = None
