"""SSLCommerz client interface.

Field names deliberately mirror SSLCommerz's own API vocabulary (tran_id, val_id,
sessionkey, GatewayPageURL, risk_level, ...) so the mock and any future real
implementation, plus the business logic that calls them, all speak the same
language as the official docs (https://developer.sslcommerz.com/doc/v4/).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class InitSessionRequest:
    tran_id: str
    amount: Decimal
    currency: str
    success_url: str
    fail_url: str
    cancel_url: str
    ipn_url: str
    cus_name: str
    cus_email: str
    cus_phone: str
    product_name: str = "Workspace Subscription"
    product_category: str = "subscription"


@dataclass
class InitSessionResult:
    status: str  # 'SUCCESS' | 'FAILED'
    session_key: Optional[str] = None
    gateway_page_url: Optional[str] = None
    failed_reason: Optional[str] = None


@dataclass
class ValidationResult:
    """Shape returned by both the validationserverAPI (val_id lookup) and the
    merchantTransIDvalidationAPI (tran_id lookup) — SSLCommerz's real API returns
    the same fields from either endpoint."""
    status: str  # 'VALID' | 'VALIDATED' | 'FAILED' | 'CANCELLED' | 'EXPIRED' | 'UNATTEMPTED' | 'INVALID_TRANSACTION'
    tran_id: str
    val_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    risk_level: Optional[int] = None  # 0 = safe, 1 = risky
    risk_title: Optional[str] = None
    bank_tran_id: Optional[str] = None
    card_type: Optional[str] = None
    verify_sign: Optional[str] = None
    verify_key: Optional[str] = None


class SSLCommerzClient(ABC):
    """Everything payment business logic needs from SSLCommerz. Never call the
    gateway directly from a manager/service — always go through this interface."""

    @abstractmethod
    def init_session(self, req: InitSessionRequest) -> InitSessionResult:
        """POST gwprocess/v4/api.php — start a checkout session, get back a
        GatewayPageURL to redirect the customer's browser to."""
        raise NotImplementedError

    @abstractmethod
    def validate(self, val_id: str) -> ValidationResult:
        """GET validator/api/validationserverAPI.php — the authoritative,
        server-to-server check of a val_id received via redirect or IPN.
        Never trust val_id-bearing payloads without calling this first."""
        raise NotImplementedError

    @abstractmethod
    def query_by_tran_id(self, tran_id: str, val_id_hint: Optional[str] = None) -> ValidationResult:
        """GET validator/api/merchantTransIDvalidationAPI.php — used by the
        reconciliation sweep to resolve a tran_id that never received a
        redirect or IPN callback."""
        raise NotImplementedError

    @abstractmethod
    def verify_signature(self, payload: dict) -> bool:
        """Cheap first-pass check of an incoming IPN payload's verify_sign
        before spending a round-trip on validate(). Never a substitute for it."""
        raise NotImplementedError
