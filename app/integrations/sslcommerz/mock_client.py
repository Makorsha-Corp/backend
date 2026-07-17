"""Mock SSLCommerz client for local development and the billing trial page.

Real SSLCommerz has no server for us to call in mock mode, so this client is
self-contained: instead of storing session state, it packs everything a
validation response needs into a signed `val_id` token at the moment the mock
gateway page is "completed" (see app/api/v1/endpoints/payments.py — the
mock-gateway routes). `validate()` just verifies and decodes that token. This
keeps the mock stateless while still exercising the exact same signature-check
+ server-to-server-validate code path the real integration will use later.
"""
import base64
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Optional

from app.core.config import settings
from app.integrations.sslcommerz.client import (
    InitSessionRequest,
    InitSessionResult,
    SSLCommerzClient,
    ValidationResult,
)

_SIGNED_FIELDS = ["status", "tran_id", "amount", "currency", "risk_level"]


def _sign(payload: dict) -> str:
    signable = "|".join(str(payload[f]) for f in _SIGNED_FIELDS)
    return hmac.new(settings.SECRET_KEY.encode(), signable.encode(), hashlib.sha256).hexdigest()


class MockSSLCommerzClient(SSLCommerzClient):
    def init_session(self, req: InitSessionRequest) -> InitSessionResult:
        session_key = base64.urlsafe_b64encode(hashlib.sha256(req.tran_id.encode()).digest()).decode().rstrip("=")
        gateway_page_url = (
            f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments/mock-gateway/{req.tran_id}"
        )
        return InitSessionResult(status="SUCCESS", session_key=session_key, gateway_page_url=gateway_page_url)

    def build_val_id(
        self,
        *,
        tran_id: str,
        amount: Decimal,
        currency: str,
        status: str,
        risk_level: int = 0,
    ) -> str:
        """Mock-only helper: called by the mock-gateway "complete" endpoint to
        mint a val_id token that encodes the simulated outcome. Not part of the
        SSLCommerzClient interface — a real client never mints its own val_id."""
        payload = {
            "tran_id": tran_id,
            "amount": str(amount),
            "currency": currency,
            "status": status,
            "risk_level": risk_level,
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        signature = _sign(payload)
        return f"{encoded}.{signature}"

    def _decode_val_id(self, val_id: str) -> Optional[dict]:
        try:
            encoded, signature = val_id.rsplit(".", 1)
            payload = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
        except (ValueError, TypeError, UnicodeDecodeError):
            return None
        if not hmac.compare_digest(_sign(payload), signature):
            return None
        return payload

    def validate(self, val_id: str) -> ValidationResult:
        payload = self._decode_val_id(val_id)
        if payload is None:
            return ValidationResult(status="INVALID_TRANSACTION", tran_id="")

        risk_level = payload["risk_level"]
        return ValidationResult(
            status=payload["status"],
            tran_id=payload["tran_id"],
            val_id=val_id,
            amount=Decimal(payload["amount"]),
            currency=payload["currency"],
            risk_level=risk_level,
            risk_title="Risky" if risk_level == 1 else "Safe",
            bank_tran_id=f"MOCKBANK-{payload['tran_id']}",
            card_type="mock-visa",
            verify_sign=val_id.rsplit(".", 1)[1],
            verify_key=",".join(_SIGNED_FIELDS),
        )

    def query_by_tran_id(self, tran_id: str, val_id_hint: Optional[str] = None) -> ValidationResult:
        if val_id_hint:
            result = self.validate(val_id_hint)
            if result.tran_id == tran_id:
                return result
        return ValidationResult(status="UNATTEMPTED", tran_id=tran_id)

    def verify_signature(self, payload: dict) -> bool:
        verify_sign = payload.get("verify_sign")
        if not verify_sign:
            return False
        signable = {f: payload.get(f) for f in _SIGNED_FIELDS}
        if any(v is None for v in signable.values()):
            return False
        return hmac.compare_digest(_sign(signable), verify_sign)
