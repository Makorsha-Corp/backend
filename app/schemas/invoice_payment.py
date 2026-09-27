"""Invoice payment schemas"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoicePaymentBase(BaseModel):
    """Base invoice payment schema"""
    invoice_id: int

    payment_amount: Decimal = Field(..., gt=0)
    payment_date: date
    payment_method: str | None = Field(None, max_length=50)
    payment_reference: str | None = Field(None, max_length=100)

    bank_name: str | None = Field(None, max_length=255)
    transaction_id: str | None = Field(None, max_length=100)

    notes: str | None = None


class InvoicePaymentCreate(InvoicePaymentBase):
    """Schema for creating an invoice payment (workspace_id injected by service)"""


class InvoicePaymentUpdate(BaseModel):
    """Schema for updating an invoice payment (amount changes are blocked at manager level)"""
    payment_amount: Decimal | None = Field(None, gt=0)
    payment_date: date | None = None
    payment_method: str | None = Field(None, max_length=50)
    payment_reference: str | None = Field(None, max_length=100)

    bank_name: str | None = Field(None, max_length=255)
    transaction_id: str | None = Field(None, max_length=100)

    notes: str | None = None


class VoidPaymentRequest(BaseModel):
    """Request body for voiding a payment"""
    void_note: str = Field(..., min_length=1, description="Required reason for voiding")


class InvoicePaymentInDB(InvoicePaymentBase):
    """Invoice payment schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int

    is_voided: bool = False
    voided_at: datetime | None = None
    voided_by: int | None = None
    void_note: str | None = None

    created_at: datetime
    created_by: int | None = None


class InvoicePaymentResponse(InvoicePaymentInDB):
    """Invoice payment response schema"""
    created_by_name: str | None = None
