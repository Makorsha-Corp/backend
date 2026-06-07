"""Invoice payment schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class InvoicePaymentBase(BaseModel):
    """Base invoice payment schema"""
    invoice_id: int

    payment_amount: Decimal = Field(..., gt=0)
    payment_date: date
    payment_method: Optional[str] = Field(None, max_length=50)
    payment_reference: Optional[str] = Field(None, max_length=100)

    bank_name: Optional[str] = Field(None, max_length=255)
    transaction_id: Optional[str] = Field(None, max_length=100)

    notes: Optional[str] = None


class InvoicePaymentCreate(InvoicePaymentBase):
    """Schema for creating an invoice payment (workspace_id injected by service)"""
    pass


class InvoicePaymentUpdate(BaseModel):
    """Schema for updating an invoice payment (amount changes are blocked at manager level)"""
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    payment_date: Optional[date] = None
    payment_method: Optional[str] = Field(None, max_length=50)
    payment_reference: Optional[str] = Field(None, max_length=100)

    bank_name: Optional[str] = Field(None, max_length=255)
    transaction_id: Optional[str] = Field(None, max_length=100)

    notes: Optional[str] = None


class VoidPaymentRequest(BaseModel):
    """Request body for voiding a payment"""
    void_note: str = Field(..., min_length=1, description="Required reason for voiding")


class InvoicePaymentInDB(InvoicePaymentBase):
    """Invoice payment schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int

    is_voided: bool = False
    voided_at: Optional[datetime] = None
    voided_by: Optional[int] = None
    void_note: Optional[str] = None

    created_at: datetime
    created_by: Optional[int] = None


class InvoicePaymentResponse(InvoicePaymentInDB):
    """Invoice payment response schema"""
    pass
