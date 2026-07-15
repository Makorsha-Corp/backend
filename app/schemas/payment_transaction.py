"""Payment transaction schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class InitiatePaymentRequest(BaseModel):
    """Request body to start a checkout session."""
    amount: Decimal = Field(..., gt=0)
    currency: str = Field("BDT", min_length=3, max_length=3)
    cus_phone: str = Field(..., min_length=3, max_length=50)
    cus_name: Optional[str] = Field(None, max_length=255, description="Defaults to the current user's profile name")
    cus_email: Optional[str] = Field(None, max_length=255, description="Defaults to the current user's profile email")
    value_a: Optional[str] = Field(None, max_length=255, description="Caller-defined correlation metadata, echoed back unchanged")
    value_b: Optional[str] = Field(None, max_length=255)
    value_c: Optional[str] = Field(None, max_length=255)
    value_d: Optional[str] = Field(None, max_length=255)


class InitiatePaymentResponse(BaseModel):
    tran_id: str
    status: str
    gateway_page_url: Optional[str] = None
    failed_reason: Optional[str] = None


class ResolveRiskRequest(BaseModel):
    approve: bool
    note: str = Field(..., min_length=1, max_length=1000)


class PaymentTransactionInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    tran_id: str
    status: str

    amount: Decimal
    currency: str

    cus_name: Optional[str] = None
    cus_email: Optional[str] = None
    cus_phone: Optional[str] = None

    value_a: Optional[str] = None
    value_b: Optional[str] = None
    value_c: Optional[str] = None
    value_d: Optional[str] = None

    session_key: Optional[str] = None
    gateway_page_url: Optional[str] = None

    val_id: Optional[str] = None
    risk_level: Optional[int] = None
    risk_title: Optional[str] = None
    bank_tran_id: Optional[str] = None
    card_type: Optional[str] = None

    risk_resolved_by: Optional[int] = None
    risk_resolved_at: Optional[datetime] = None
    risk_resolution_note: Optional[str] = None

    initiated_by: Optional[int] = None
    initiated_at: datetime
    validated_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime


class PaymentTransactionResponse(PaymentTransactionInDB):
    initiated_by_name: Optional[str] = None


class PaymentTransactionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_transaction_id: int
    event_type: str
    description: str
    metadata_json: Optional[dict] = None
    performed_by: Optional[int] = None
    created_at: datetime


class PaymentTransactionDetailResponse(PaymentTransactionResponse):
    events: list[PaymentTransactionEventResponse] = []
