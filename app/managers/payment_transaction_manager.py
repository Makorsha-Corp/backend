"""
Payment Transaction Manager

Core SSLCommerz checkout logic: session initiation, the dual-channel
(browser-redirect + IPN) idempotency wall, server-to-server validation, risk
handling, and reconciliation. Both the redirect handlers and the IPN handler
funnel into the same locked validation path so a transaction is only ever
finalized once, no matter which channel — or both — deliver the outcome.
"""
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.managers.base_manager import BaseManager
from app.models.payment_transaction import PaymentTransaction
from app.models.profile import Profile
from app.schemas.payment_transaction import InitiatePaymentRequest
from app.dao.payment_transaction import payment_transaction_dao
from app.dao.payment_transaction_event import payment_transaction_event_dao
from app.core.config import settings
from app.integrations.sslcommerz import get_sslcommerz_client
from app.integrations.sslcommerz.client import InitSessionRequest, ValidationResult

RECONCILE_TIMEOUT_MINUTES = 30


class PaymentTransactionManager(BaseManager[PaymentTransaction]):
    def __init__(self):
        super().__init__(PaymentTransaction)
        self.dao = payment_transaction_dao
        self.event_dao = payment_transaction_event_dao

    def _log_event(
        self,
        session: Session,
        txn: PaymentTransaction,
        event_type: str,
        description: str,
        performed_by: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        self.event_dao.create(session, obj_in={
            "workspace_id": txn.workspace_id,
            "payment_transaction_id": txn.id,
            "event_type": event_type,
            "description": description,
            "metadata_json": metadata,
            "performed_by": performed_by,
        })

    def _generate_tran_id(self, session: Session) -> str:
        for _ in range(5):
            candidate = secrets.token_hex(13)  # 26 chars, under SSLCommerz's 30-char limit
            if self.dao.get_by_tran_id(session, tran_id=candidate) is None:
                return candidate
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not generate a unique transaction ID")

    def initiate_payment(
        self,
        session: Session,
        *,
        workspace_id: int,
        user: Profile,
        request: InitiatePaymentRequest,
    ) -> PaymentTransaction:
        tran_id = self._generate_tran_id(session)
        api_base = f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments"

        client = get_sslcommerz_client()
        result = client.init_session(InitSessionRequest(
            tran_id=tran_id,
            amount=request.amount,
            currency=request.currency,
            success_url=f"{api_base}/success",
            fail_url=f"{api_base}/fail",
            cancel_url=f"{api_base}/cancel",
            ipn_url=f"{api_base}/ipn",
            cus_name=request.cus_name or user.name,
            cus_email=request.cus_email or user.email,
            cus_phone=request.cus_phone,
        ))

        if result.status != "SUCCESS":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SSLCommerz session initiation failed: {result.failed_reason or 'unknown error'}",
            )

        txn = self.dao.create(session, obj_in={
            "workspace_id": workspace_id,
            "tran_id": tran_id,
            "status": "INITIATED",
            "amount": request.amount,
            "currency": request.currency,
            "cus_name": request.cus_name or user.name,
            "cus_email": request.cus_email or user.email,
            "cus_phone": request.cus_phone,
            "value_a": request.value_a,
            "value_b": request.value_b,
            "value_c": request.value_c,
            "value_d": request.value_d,
            "session_key": result.session_key,
            "gateway_page_url": result.gateway_page_url,
            "initiated_by": user.id,
        })

        self._log_event(
            session, txn, "initiated",
            f"Checkout session created for {request.amount} {request.currency}",
            performed_by=user.id,
            metadata={"session_key": result.session_key},
        )
        return txn

    def _apply_validation_result(
        self, session: Session, txn: PaymentTransaction, result: ValidationResult, source: str
    ) -> PaymentTransaction:
        """Shared finalization logic for both live callbacks (validate()) and the
        reconciliation sweep (query_by_tran_id()) — same ValidationResult shape."""
        if result.tran_id and result.tran_id != txn.tran_id:
            # A validated val_id that doesn't belong to this tran_id — either a
            # gateway bug or a replay attempt. Never apply it to this row.
            txn.status = "VALIDATED_FAILED"
            txn.validated_at = datetime.utcnow()
            self._log_event(
                session, txn, "validated_failed",
                f"val_id/tran_id mismatch via {source}: gateway resolved it to tran_id={result.tran_id}",
            )
            session.flush()
            return txn

        txn.val_id = result.val_id
        txn.risk_level = result.risk_level
        txn.risk_title = result.risk_title
        txn.bank_tran_id = result.bank_tran_id
        txn.card_type = result.card_type
        txn.verify_sign = result.verify_sign
        txn.validated_at = datetime.utcnow()

        if result.status not in ("VALID", "VALIDATED"):
            txn.status = "VALIDATED_FAILED"
            self._log_event(
                session, txn, "validated_failed",
                f"Gateway validation via {source} returned status={result.status}",
            )
            session.flush()
            return txn

        if result.amount is not None and result.amount != txn.amount:
            txn.status = "VALIDATED_FAILED"
            self._log_event(
                session, txn, "validated_failed",
                f"Amount mismatch: expected {txn.amount} {txn.currency}, gateway reported {result.amount} {result.currency}",
            )
            session.flush()
            return txn

        if result.currency and result.currency != txn.currency:
            txn.status = "VALIDATED_FAILED"
            self._log_event(
                session, txn, "validated_failed",
                f"Currency mismatch: expected {txn.currency}, gateway reported {result.currency}",
            )
            session.flush()
            return txn

        if result.risk_level == 1:
            txn.status = "RISK_HOLD"
            self._log_event(
                session, txn, "risk_hold",
                f"Validated via {source} but flagged high-risk ({result.risk_title}) — held for review",
            )
        else:
            txn.status = "VALIDATED_SUCCESS"
            self._log_event(
                session, txn, "validated_success",
                f"Validated successfully via {source}",
            )
        session.flush()
        return txn

    def finalize_from_gateway(
        self, session: Session, *, tran_id: str, val_id: str, source: str
    ) -> PaymentTransaction:
        """The idempotency wall. Locks the row so a redirect and an IPN arriving
        at the same instant can't both finalize the same transaction."""
        txn = self.dao.get_by_tran_id_for_update(session, tran_id=tran_id)
        if txn is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tran_id: {tran_id}")

        if txn.status != "INITIATED":
            self._log_event(
                session, txn, "duplicate_ignored",
                f"Duplicate {source} callback ignored; transaction already {txn.status}",
            )
            session.flush()
            return txn

        self._log_event(session, txn, f"{source}_received", f"Callback received via {source}")

        client = get_sslcommerz_client()
        result = client.validate(val_id)
        return self._apply_validation_result(session, txn, result, source=f"{source} callback")

    def mark_terminal_without_validation(
        self, session: Session, *, tran_id: str, terminal_status: str, source: str
    ) -> PaymentTransaction:
        """For fail/cancel redirects that carry no val_id — nothing to validate
        server-side, so we trust the redirect outcome directly."""
        txn = self.dao.get_by_tran_id_for_update(session, tran_id=tran_id)
        if txn is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tran_id: {tran_id}")

        if txn.status != "INITIATED":
            self._log_event(
                session, txn, "duplicate_ignored",
                f"Duplicate {source} callback ignored; transaction already {txn.status}",
            )
            session.flush()
            return txn

        txn.status = terminal_status
        txn.validated_at = datetime.utcnow()
        self._log_event(session, txn, terminal_status.lower(), f"Marked {terminal_status} via {source} (no val_id to validate)")
        session.flush()
        return txn

    def resolve_risk(
        self, session: Session, *, transaction_id: int, workspace_id: int, user_id: int, approve: bool, note: str
    ) -> PaymentTransaction:
        row = self.dao.get_by_id_and_workspace_with_initiator(session, id=transaction_id, workspace_id=workspace_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Payment transaction {transaction_id} not found")
        txn, _ = row

        if txn.status != "RISK_HOLD":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Only transactions in RISK_HOLD can be resolved (current status: {txn.status})",
            )

        txn.status = "VALIDATED_SUCCESS" if approve else "VALIDATED_FAILED"
        txn.risk_resolved_by = user_id
        txn.risk_resolved_at = datetime.utcnow()
        txn.risk_resolution_note = note
        self._log_event(
            session, txn, "risk_resolved",
            f"Risk hold {'approved' if approve else 'rejected'}: {note}",
            performed_by=user_id,
        )
        session.flush()
        return txn

    def reconcile_stuck_transactions(
        self, session: Session, *, older_than_minutes: int = RECONCILE_TIMEOUT_MINUTES, limit: int = 200
    ) -> list[PaymentTransaction]:
        """Sweep INITIATED rows the dual-channel callbacks never resolved. Safe to
        call repeatedly and safe to run concurrently with live callbacks — each
        row is re-locked and re-checked immediately before acting on it."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        stuck = self.dao.get_stuck_initiated(session, older_than=cutoff, limit=limit)

        client = get_sslcommerz_client()
        resolved = []
        for stale in stuck:
            txn = self.dao.get_by_tran_id_for_update(session, tran_id=stale.tran_id)
            if txn is None or txn.status != "INITIATED":
                continue  # already resolved by a live callback between the query and the lock

            result = client.query_by_tran_id(txn.tran_id, val_id_hint=txn.val_id)
            if result.status in ("VALID", "VALIDATED"):
                self._apply_validation_result(session, txn, result, source="reconciliation")
            else:
                txn.status = "EXPIRED"
                txn.validated_at = datetime.utcnow()
                self._log_event(
                    session, txn, "expired",
                    f"No resolution found after {older_than_minutes} minutes (gateway status: {result.status})",
                )
                session.flush()
            resolved.append(txn)
        return resolved


payment_transaction_manager = PaymentTransactionManager()
