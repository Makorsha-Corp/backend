"""Invoice payment schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class InvoicePaymentBase(BaseModel):
    """Base invoice payment schema"""
    invoice_id: int

    # Payment Details
    payment_amount: Decimal = Field(..., gt=0)
    payment_date: date
    payment_method: Optional[str] = Field(None, max_length=50)
    payment_reference: Optional[str] = Field(None, max_length=100)

    # Bank Details
    bank_name: Optional[str] = Field(None, max_length=255)
    transaction_id: Optional[str] = Field(None, max_length=100)

    # Notes
    notes: Optional[str] = None


class InvoicePaymentCreate(InvoicePaymentBase):
    """Schema for creating an invoice payment (workspace_id injected by service)"""
    pass


class InvoicePaymentUpdate(BaseModel):
    """Schema for updating an invoice payment"""
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    payment_date: Optional[date] = None
    payment_method: Optional[str] = Field(None, max_length=50)
    payment_reference: Optional[str] = Field(None, max_length=100)

    # Bank Details
    bank_name: Optional[str] = Field(None, max_length=255)
    transaction_id: Optional[str] = Field(None, max_length=100)

    # Notes
    notes: Optional[str] = None


class InvoicePaymentInDB(InvoicePaymentBase):
    """Invoice payment schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_at: datetime
    created_by: Optional[int]


class InvoicePaymentResponse(InvoicePaymentInDB):
    """Invoice payment response schema"""
    pass
