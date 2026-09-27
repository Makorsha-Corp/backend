"""Payment transaction schemas"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InitiatePaymentRequest(BaseModel):
    """Request body to start a checkout session."""
    amount: Decimal = Field(..., gt=0)
    currency: str = Field("BDT", min_length=3, max_length=3)
    cus_phone: str = Field(..., min_length=3, max_length=50)
    cus_name: str | None = Field(None, max_length=255, description="Defaults to the current user's profile name")
    cus_email: str | None = Field(None, max_length=255, description="Defaults to the current user's profile email")
    value_a: str | None = Field(None, max_length=255, description="Caller-defined correlation metadata, echoed back unchanged")
    value_b: str | None = Field(None, max_length=255)
    value_c: str | None = Field(None, max_length=255)
    value_d: str | None = Field(None, max_length=255)


class InitiatePaymentResponse(BaseModel):
    tran_id: str
    status: str
    gateway_page_url: str | None = None
    failed_reason: str | None = None


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

    cus_name: str | None = None
    cus_email: str | None = None
    cus_phone: str | None = None

    value_a: str | None = None
    value_b: str | None = None
    value_c: str | None = None
    value_d: str | None = None

    session_key: str | None = None
    gateway_page_url: str | None = None

    val_id: str | None = None
    risk_level: int | None = None
    risk_title: str | None = None
    bank_tran_id: str | None = None
    card_type: str | None = None

    risk_resolved_by: int | None = None
    risk_resolved_at: datetime | None = None
    risk_resolution_note: str | None = None

    initiated_by: int | None = None
    initiated_at: datetime
    validated_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class PaymentTransactionResponse(PaymentTransactionInDB):
    initiated_by_name: str | None = None


class PaymentTransactionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_transaction_id: int
    event_type: str
    description: str
    metadata_json: dict | None = None
    performed_by: int | None = None
    created_at: datetime


class PaymentTransactionDetailResponse(PaymentTransactionResponse):
    events: list[PaymentTransactionEventResponse] = []
