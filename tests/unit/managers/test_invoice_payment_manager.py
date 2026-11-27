"""Unit tests for app/managers/invoice_payment_manager.py.

Implements tests/unit/managers/invoice_payment_manager.cases.md (revision 5),
one test per case. Real Postgres session (`db` fixture). Mocks: only
`app.utils.time.datetime` (every test, frozen to NOW so utcnow() returns NOW
wherever it's imported -- manager `voided_at`, audit_logger `performed_at`,
invoice-event `created_at` column default). Race simulation: VP-19 only (see
Conventions / VoidRace below).

Revision 5 adds VP-25 (verify.md Finding 1: pins void_payment R7's lower
boundary, remaining active total 0.01 -> partial) and completes the N0
("nothing written") assertions on the cases verify.md Finding 3 routed here:
CP-09, CP-10, CP-13..CP-18, UP-04, UP-07, UP-08, UP-09, UP-23, UP-24, DP-01,
DP-02, DP-04, DP-05, VP-08, VP-09, VP-10, VP-11 now each check every part of
the Conventions "Nothing written (N0)" definition (payment-row snapshot,
invoice snapshot, 0 audit rows, 0 invoice events, PO/SO/return `paid` + 0
PO/SO events), not just the subset each previously asserted. verify.md's
Findings 2 and 4 (SY `user_id`/`performed_by` and SY event-pair checks) were
already correct in the file this revision started from -- re-verified, no
change needed.
"""
# ruff: noqa: SIM117, DTZ001, RUF059  (prescribed by the cards: nested with, naive datetimes, setup helpers return every row of a Given)
import inspect
import itertools
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, select, text

from app.managers.invoice_payment_manager import InvoicePaymentManager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.financial_audit_log import FinancialAuditLog
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_payment import InvoicePayment
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_return import PurchaseOrderReturn
from app.models.sales_order import SalesOrder
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_return import SalesOrderReturn
from app.models.status import Status
from app.schemas.invoice_payment import (
    InvoicePaymentCreate,
    InvoicePaymentUpdate,
    VoidPaymentRequest,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "Time": NOW frozen via app.utils.time.datetime.now().
NOW = datetime(2026, 9, 27, 12, 0, 0)
# Convention "T0": a past time set on setup rows that are already voided.
T0 = datetime(2026, 9, 20, 9, 0, 0)
# Convention "NOID": an id that exists in no table used here.
NOID = 999999999

BUG_600 = "BUG-600: list_payments_by_invoice has no id tie-breaker for same-date payments"
BUG_601 = "BUG-601: void_payment does not lock the invoice row (lost-update race)"
BUG_603 = "BUG-603: payment audit rows never record IP address or user agent"
BUG_604 = "BUG-604: payment_amount accepts more than 2 decimals or 13 integer digits"
BUG_605 = "BUG-605: void_note whitespace-only / unpadded is accepted"
BUG_606 = "BUG-606: a voided payment can still be edited"
BUG_607 = "BUG-607: editing a payment leaves no audit trail"
BUG_608 = "BUG-608: an explicit null cannot clear an optional payment field"
BUG_609 = "BUG-609: a payment can be permanently deleted instead of voided"
BUG_611 = "BUG-611: amount-change error tells the user to delete, not void, the payment"

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


# --------------------------------------------------------------------------- #
# Convention "Time": patch app.utils.time.datetime so utcnow() returns NOW
# everywhere it's imported (manager voided_at, audit_logger performed_at,
# invoice_event created_at column default -- all resolve `datetime` from
# app.utils.time's own globals at call time).
# --------------------------------------------------------------------------- #

class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return NOW.replace(tzinfo=timezone.utc)
        return NOW


@pytest.fixture(autouse=True)
def _frozen_time():
    with patch("app.utils.time.datetime", _FrozenDatetime):
        yield


@pytest.fixture
def M():
    return InvoicePaymentManager()


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1 = profile, name 'Alice Rahman' ... U2 = profile, name 'Bilal
# Khan' ... U3": profiles.name is NOT NULL (baseline schema) so the spec's
# "profile whose name is NULL" is infeasible -- U3 gets a real name instead
# (best-practice default, delegated by reviewer; see cases.md revision 4).
@pytest.fixture
def u1(db):
    return make_profile(db, name="Alice Rahman")


@pytest.fixture
def u2(db):
    return make_profile(db, name="Bilal Khan")


@pytest.fixture
def u3(db):
    return make_profile(db, name="Nusrat Jahan")


def mk_account(db, ws, name, **overrides):
    fields = dict(workspace_id=ws.id, name=name)
    fields.update(overrides)
    row = Account(**fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def a1(db, w1):
    return mk_account(db, w1, "Acme Traders")


@pytest.fixture
def a2(db, w2):
    return mk_account(db, w2, "Xeno Foreign")


# Convention "INV" -- one account_invoices row with the stated defaults.
def mk_inv(db, ws, account, created_by_id, **overrides):
    fields = dict(
        workspace_id=ws.id, account_id=account.id, invoice_type="payable",
        invoice_status="confirmed", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"),
        invoice_date=date(2026, 9, 1), due_date=None, allow_payments=True,
        payment_locked_reason=None, order_type=None, order_id=None,
        created_by=created_by_id, updated_by=created_by_id,
    )
    fields.update(overrides)
    row = AccountInvoice(**fields)
    db.add(row)
    db.flush()
    return row


def reload_inv(db, inv_id):
    """A fresh AccountInvoice instance, for `_sync_linked_order(invoice=...)`."""
    db.expire_all()
    return db.execute(select(AccountInvoice).where(AccountInvoice.id == inv_id)).scalar_one()


# Convention "PAY(inv, amount, date, ...)" -- a payment row inserted directly.
def mk_pay(db, inv_row, amount, pay_date, *, created_by_id, voided=False, voided_by_id=None, **overrides):
    fields = dict(
        workspace_id=inv_row.workspace_id, invoice_id=inv_row.id,
        payment_amount=Decimal(str(amount)), payment_date=pay_date,
        payment_method=None, payment_reference=None, bank_name=None,
        transaction_id=None, notes=None, created_by=created_by_id,
        is_voided=voided,
        voided_at=T0 if voided else None,
        voided_by=voided_by_id if voided else None,
        void_note="Duplicate entry" if voided else None,
    )
    fields.update(overrides)
    row = InvoicePayment(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "PA" -- PAY(I1, 250.00, 2026-09-01, cheque, CHQ-881, City Bank,
# TXN-001, 'First instalment'). Used by update_payment and void_payment cases.
def mk_pa(db, inv_row, created_by_id, **overrides):
    fields = dict(
        payment_method="cheque", payment_reference="CHQ-881",
        bank_name="City Bank", transaction_id="TXN-001", notes="First instalment",
    )
    fields.update(overrides)
    return mk_pay(db, inv_row, "250.00", date(2026, 9, 1), created_by_id=created_by_id, **fields)


# Convention "D0" -- the default create_payment payload.
def d0(invoice_id, **overrides):
    fields = dict(
        invoice_id=invoice_id, payment_amount=Decimal("250.00"),
        payment_date=date(2026, 9, 1), payment_method="bank_transfer",
        payment_reference="TRX-7781", bank_name="City Bank",
        transaction_id="TXN-001", notes="First instalment",
    )
    fields.update(overrides)
    return InvoicePaymentCreate(**fields)


# Convention "Update wrapper upd(payment_id, data, ws)" -- calls update_payment
# with user_id only if the method's signature has gained that parameter.
def upd(M, db, payment_id, data, ws_id, user_id):
    sig = inspect.signature(M.update_payment)
    if "user_id" in sig.parameters:
        return M.update_payment(db, payment_id=payment_id, payment_data=data, workspace_id=ws_id, user_id=user_id)
    return M.update_payment(db, payment_id=payment_id, payment_data=data, workspace_id=ws_id)


# Order shorthand builders: PO / SO / PR (po return) / SR (so return).
def mk_status(db, ws):
    row = Status(workspace_id=ws.id, name="Open", comment="")
    db.add(row)
    db.flush()
    return row


def mk_factory(db, ws):
    n = _n()
    row = Factory(workspace_id=ws.id, name=f"Factory {n}", abbreviation=f"F{n}", is_active=True, is_deleted=False)
    db.add(row)
    db.flush()
    return row


def mk_po(db, ws, created_by_id, **overrides):
    status = mk_status(db, ws)
    fields = dict(
        workspace_id=ws.id, po_number=f"PO-{_n()}", destination_type="storage",
        destination_id=1, current_status_id=status.id, created_by=created_by_id,
        invoice_id=None, paid=False,
    )
    fields.update(overrides)
    row = PurchaseOrder(**fields)
    db.add(row)
    db.flush()
    return row


def mk_so(db, ws, created_by_id, **overrides):
    status = mk_status(db, ws)
    factory = mk_factory(db, ws)
    account = mk_account(db, ws, f"SO Account {_n()}")
    fields = dict(
        workspace_id=ws.id, sales_order_number=f"SO-{_n()}", account_id=account.id,
        factory_id=factory.id, current_status_id=status.id, created_by=created_by_id,
        invoice_id=None, paid=False,
    )
    fields.update(overrides)
    row = SalesOrder(**fields)
    db.add(row)
    db.flush()
    return row


def mk_por(db, ws, created_by_id, **overrides):
    parent_po = mk_po(db, ws, created_by_id)
    fields = dict(
        workspace_id=ws.id, purchase_order_id=parent_po.id, return_number=f"PR-{_n()}",
        created_by=created_by_id, invoice_id=None, paid=False,
    )
    fields.update(overrides)
    row = PurchaseOrderReturn(**fields)
    db.add(row)
    db.flush()
    return row


def mk_sor(db, ws, created_by_id, **overrides):
    parent_so = mk_so(db, ws, created_by_id)
    fields = dict(
        workspace_id=ws.id, sales_order_id=parent_so.id, return_number=f"SR-{_n()}",
        created_by=created_by_id, invoice_id=None, paid=False,
    )
    fields.update(overrides)
    row = SalesOrderReturn(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "Re-read": db.expire_all() then access the same objects again.
def reread(db, *objs):
    db.expire_all()
    return objs[0] if len(objs) == 1 else objs


# Convention "Audit rows" / "Events of X" / "PO events" / "SO events": every
# setup in this module writes none of these directly, so a fresh unfiltered
# query is equivalent to scoping to W1 U W2 (each test is its own rolled-back
# transaction -- nothing else is visible in it).
def audit_rows(db):
    return db.execute(select(FinancialAuditLog).order_by(FinancialAuditLog.id)).scalars().all()


def events_of(db, inv_id):
    return db.execute(
        select(InvoiceEvent).where(InvoiceEvent.invoice_id == inv_id).order_by(InvoiceEvent.id)
    ).scalars().all()


def po_events(db):
    return db.execute(select(PurchaseOrderEvent).order_by(PurchaseOrderEvent.id)).scalars().all()


def so_events(db):
    return db.execute(select(SalesOrderEvent).order_by(SalesOrderEvent.id)).scalars().all()


PAY_SNAP_COLS = (
    "payment_amount", "payment_date", "payment_method", "payment_reference",
    "bank_name", "transaction_id", "notes", "is_voided", "voided_at", "voided_by", "void_note",
)


def pay_snapshot(pay):
    return {c: getattr(pay, c) for c in PAY_SNAP_COLS}


INV_SNAP_COLS = ("paid_amount", "payment_status", "invoice_status", "allow_payments", "updated_by")


def inv_snapshot(inv):
    return {c: getattr(inv, c) for c in INV_SNAP_COLS}


def money(v):
    """Convention 'Audit snapshot values': numeric comparison regardless of
    whether extract_relevant_fields produced a float (BUG-141) or a string."""
    return Decimal(str(v))


def not_found_payment(payment_id):
    return f"Payment with ID {payment_id} not found"


def not_found_invoice(invoice_id):
    return f"Invoice with ID {invoice_id} not found"


# Convention "SQL capture": a before_cursor_execute listener recording
# statements run during the action only (not setup).
class SQLCapture:
    def __init__(self, engine):
        self.engine = engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    def locks_invoice(self):
        return any("account_invoices" in s and "FOR UPDATE" in s.upper() for s in self.statements)

    def selects_payment_after_lock(self):
        lock_idx = None
        for i, s in enumerate(self.statements):
            if "account_invoices" in s and "FOR UPDATE" in s.upper():
                lock_idx = i
                break
        if lock_idx is None:
            return False
        return any("invoice_payments" in s for s in self.statements[lock_idx + 1:])


# Convention "Race simulations" (VP-19 only, BUG-601): before the first
# captured account_invoices ... FOR UPDATE statement runs, write the losing
# voider's state through the SAME DBAPI connection, its own cursor.
class VoidRace:
    def __init__(self, engine, payment_id, voided_by_id, voided_at, void_note):
        self.engine = engine
        self.payment_id = payment_id
        self.voided_by_id = voided_by_id
        self.voided_at = voided_at
        self.void_note = void_note
        self._fired = False

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        if self._fired or "account_invoices" not in statement or "FOR UPDATE" not in statement.upper():
            return
        self._fired = True
        raw = cursor.connection.cursor()
        raw.execute(
            "UPDATE invoice_payments SET is_voided = true, voided_by = %s, "
            "voided_at = %s, void_note = %s WHERE id = %s",
            (self.voided_by_id, self.voided_at, self.void_note, self.payment_id),
        )
        raw.close()

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False


# Convention "Update wrapper data": an InvoicePaymentUpdate built with exactly
# the given keys "set" (exclude_unset distinguishes this from an omitted key).
def build_update(**fields):
    return InvoicePaymentUpdate(**fields)


# Convention "BUG-600 setup": reserve n ascending ids from the payment table's
# id sequence without inserting rows, so explicit-id rows can be inserted later
# in a different order.
def reserve_payment_ids(db, n):
    return [db.execute(text("SELECT nextval('invoice_payments_id_seq')")).scalar() for _ in range(n)]


# Convention "Setup L4" (list_payments_by_invoice): LA/LB/LC/LD on I1.
def mk_l4(db, i1, u1, u2, u3):
    la = mk_pay(db, i1, "100.00", date(2026, 9, 1), created_by_id=u1.id)
    lb = mk_pay(db, i1, "200.00", date(2026, 9, 5), created_by_id=u2.id)
    lc = mk_pay(db, i1, "300.00", date(2026, 9, 3), created_by_id=u3.id, voided=True, voided_by_id=u2.id)
    ld = mk_pay(db, i1, "400.00", date(2026, 9, 2), created_by_id=None)
    return la, lb, lc, ld


# =========================================================================== #
# InvoicePaymentManager.create_payment
# =========================================================================== #

def test_ipm_cp_01__happy_path_payment_row(db, M, w1, a1, u1, u2):
    """IPM-CP-01 -- a payment is created with every field from D0.
    Rules: create_payment R6."""
    i1 = mk_inv(db, w1, a1, u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert p.id is not None
    reread(db, p)
    assert p.invoice_id == i1.id
    assert p.payment_amount == Decimal("250.00")
    assert p.payment_date == date(2026, 9, 1)
    assert p.payment_method == "bank_transfer"
    assert p.payment_reference == "TRX-7781"
    assert p.bank_name == "City Bank"
    assert p.transaction_id == "TXN-001"
    assert p.notes == "First instalment"
    assert p.workspace_id == w1.id
    assert p.created_by == u1.id
    assert p.is_voided is False
    assert p.voided_at is None
    assert p.voided_by is None
    assert p.void_note is None
    assert p.created_at is not None
    rows = db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all()
    assert len(rows) == 1


def test_ipm_cp_02__invoice_paid_amount_and_status_updated(db, M, w1, a1, u1, u2):
    """IPM-CP-02 -- the invoice's paid_amount/status update; nothing else changes.
    Rules: create_payment R7, R8."""
    i1 = mk_inv(db, w1, a1, u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert p.id is not None
    reread(db, i1)
    assert i1.paid_amount == Decimal("250.00")
    assert i1.payment_status == "partial"
    assert i1.invoice_amount == Decimal("1000.00")
    assert i1.invoice_status == "confirmed"
    assert i1.allow_payments is True
    assert i1.updated_by == u2.id


def test_ipm_cp_03__payment_equal_to_outstanding_marks_paid(db, M, w1, a1, u1, u2):
    """IPM-CP-03 -- a payment exactly equal to outstanding is accepted; invoice becomes paid.
    Rules: create_payment R5, R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("400.00"), payment_status="partial")
    mk_pay(db, i1, "400.00", date(2026, 8, 15), created_by_id=u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("600.00")), workspace_id=w1.id, user_id=u1.id)
    reread(db, p, i1)
    assert p.payment_amount == Decimal("600.00")
    assert i1.paid_amount == Decimal("1000.00")
    assert i1.payment_status == "paid"
    rows = db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all()
    assert len(rows) == 2


def test_ipm_cp_04__payment_just_below_outstanding_stays_partial(db, M, w1, a1, u1, u2):
    """IPM-CP-04 -- a payment just below outstanding leaves the invoice partial.
    Rules: create_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("400.00"), payment_status="partial")
    mk_pay(db, i1, "400.00", date(2026, 8, 15), created_by_id=u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("599.99")), workspace_id=w1.id, user_id=u1.id)
    reread(db, p, i1)
    assert i1.paid_amount == Decimal("999.99")
    assert i1.payment_status == "partial"


def test_ipm_cp_05__amount_over_outstanding_rejected(db, M, w1, a1, u1, u2):
    """IPM-CP-05 -- amount over outstanding is rejected; nothing written.
    Rules: create_payment R5, R14; Errors row 4."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("400.00"), payment_status="partial")
    mk_pay(db, i1, "400.00", date(2026, 8, 15), created_by_id=u2.id)
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("600.01")), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment amount (600.01) exceeds outstanding amount (600.00)"
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    rows = db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all()
    assert len(rows) == 1


def test_ipm_cp_06__fully_paid_invoice_rejects_any_amount(db, M, w1, a1, u1, u2):
    """IPM-CP-06 -- a fully paid invoice rejects even a tiny payment; nothing written.
    Rules: create_payment R5, R14."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("1000.00"), payment_status="paid")
    pay = mk_pay(db, i1, "1000.00", date(2026, 8, 15), created_by_id=u2.id)
    inv_before = inv_snapshot(i1)
    pay_before = pay_snapshot(pay)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("0.01")), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment amount (0.01) exceeds outstanding amount (0.00)"
    reread(db, i1, pay)
    assert inv_snapshot(i1) == inv_before
    assert pay_snapshot(pay) == pay_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    rows = db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all()
    assert len(rows) == 1


def test_ipm_cp_07__overpaid_invoice_negative_outstanding(db, M, w1, a1, u1, u2):
    """IPM-CP-07 -- an overpaid invoice shows negative outstanding in the error.
    Rules: create_payment R5, R14."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("1000.50"), payment_status="paid")
    pay = mk_pay(db, i1, "1000.50", date(2026, 8, 15), created_by_id=u2.id)
    inv_before = inv_snapshot(i1)
    pay_before = pay_snapshot(pay)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("0.01")), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment amount (0.01) exceeds outstanding amount (-0.50)"
    reread(db, i1, pay)
    assert inv_snapshot(i1) == inv_before
    assert pay_snapshot(pay) == pay_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    rows = db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all()
    assert len(rows) == 1


def test_ipm_cp_08__overdue_status_becomes_partial(db, M, w1, a1, u1, u2):
    """IPM-CP-08 -- a payment on an 'overdue' invoice recomputes payment_status to partial.
    Rules: create_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="overdue")
    p = M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("100.00")), workspace_id=w1.id, user_id=u1.id)
    reread(db, p, i1)
    assert i1.paid_amount == Decimal("100.00")
    assert i1.payment_status == "partial"


def test_ipm_cp_09__invoice_missing_404(db, M, w1, a1, u1, u2):
    """IPM-CP-09 -- a non-existent invoice id raises 404; nothing written.
    Rules: create_payment R1, R14; Errors row 1."""
    i1 = mk_inv(db, w1, a1, u2.id)
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(NOID), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(NOID)
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    rows = db.execute(select(InvoicePayment)).scalars().all()
    assert rows == []


def test_ipm_cp_10__other_workspace_invoice_404(db, M, w1, w2, a1, a2, u1, u2):
    """IPM-CP-10 -- an invoice belonging to another workspace is reported 404; nothing written.
    Rules: create_payment R1, R14; Errors row 1."""
    i1 = mk_inv(db, w1, a1, u2.id)
    i2 = mk_inv(db, w2, a2, u2.id)
    i1_before, i2_before = inv_snapshot(i1), inv_snapshot(i2)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i2.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(i2.id)
    reread(db, i1, i2)
    assert inv_snapshot(i1) == i1_before
    assert inv_snapshot(i2) == i2_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert events_of(db, i2.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i2.id)).scalars().all() == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_11__other_workspace_success_isolated(db, M, w2, a2, u2):
    """IPM-CP-11 -- creating against W2 as W2's own user succeeds, audit row scoped to W2.
    Rules: create_payment R1, R6, R9."""
    i2 = mk_inv(db, w2, a2, u2.id)
    p = M.create_payment(db, payment_data=d0(i2.id), workspace_id=w2.id, user_id=u2.id)
    reread(db, p, i2)
    assert p.workspace_id == w2.id
    assert p.created_by == u2.id
    assert i2.paid_amount == Decimal("250.00")
    assert i2.payment_status == "partial"
    rows = audit_rows(db)
    assert len(rows) == 1
    assert rows[0].workspace_id == w2.id
    assert rows[0].performed_by == u2.id


def test_ipm_cp_12__locks_the_invoice(db, M, engine, w1, a1, u1, u2):
    """IPM-CP-12 -- create_payment locks the invoice row (SELECT ... FOR UPDATE).
    Rules: create_payment R2."""
    i1 = mk_inv(db, w1, a1, u2.id)
    with SQLCapture(engine) as cap:
        p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert p.id is not None
    assert cap.locks_invoice()


def test_ipm_cp_13__draft_invoice_rejected(db, M, w1, a1, u1, u2):
    """IPM-CP-13 -- a draft invoice is rejected; nothing written.
    Rules: create_payment R3, R14; Errors row 2."""
    i1 = mk_inv(db, w1, a1, u2.id, invoice_status="draft")
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments can only be recorded against confirmed invoices (current status: 'draft')."
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_14__voided_invoice_rejected(db, M, w1, a1, u1, u2):
    """IPM-CP-14 -- a voided invoice is rejected; nothing written.
    Rules: create_payment R3, R14."""
    i1 = mk_inv(db, w1, a1, u2.id, invoice_status="voided")
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments can only be recorded against confirmed invoices (current status: 'voided')."
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_15__locked_with_reason_403(db, M, w1, a1, u1, u2):
    """IPM-CP-15 -- allow_payments false with a reason raises 403 with that reason.
    Rules: create_payment R4, R14; Errors row 3."""
    i1 = mk_inv(db, w1, a1, u2.id, allow_payments=False, payment_locked_reason="Awaiting credit approval")
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Awaiting credit approval"
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_16__locked_null_reason_default_text(db, M, w1, a1, u1, u2):
    """IPM-CP-16 -- allow_payments false with NULL reason uses the default text.
    Rules: create_payment R4, R14."""
    i1 = mk_inv(db, w1, a1, u2.id, allow_payments=False, payment_locked_reason=None)
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Payments are locked for this invoice"
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_17__locked_empty_reason_default_text(db, M, w1, a1, u1, u2):
    """IPM-CP-17 -- allow_payments false with empty-string reason uses the default text.
    Rules: create_payment R4, R14."""
    i1 = mk_inv(db, w1, a1, u2.id, allow_payments=False, payment_locked_reason="")
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Payments are locked for this invoice"
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_18__draft_checked_before_lock(db, M, w1, a1, u1, u2):
    """IPM-CP-18 -- a draft + locked invoice gets the draft error, not 403.
    Rules: create_payment R3, R4 (order)."""
    i1 = mk_inv(
        db, w1, a1, u2.id, invoice_status="draft",
        allow_payments=False, payment_locked_reason="Awaiting credit approval",
    )
    inv_before = inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments can only be recorded against confirmed invoices (current status: 'draft')."
    reread(db, i1)
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id)).scalars().all() == []


def test_ipm_cp_19__lifted_lock_reason_does_not_block(db, M, w1, a1, u1, u2):
    """IPM-CP-19 -- allow_payments true with a leftover reason text does not block.
    Rules: create_payment R4."""
    i1 = mk_inv(db, w1, a1, u2.id, allow_payments=True, payment_locked_reason="Old lock, lifted")
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert p.id is not None
    reread(db, i1)
    assert i1.paid_amount == Decimal("250.00")


def test_ipm_cp_20__audit_row_and_status_change_description(db, M, w1, a1, u1, u2):
    """IPM-CP-20 -- the create audit row and description on a status-changing payment.
    Rules: create_payment R9, R10, R10a (default), R11."""
    i1 = mk_inv(db, w1, a1, u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    rows = audit_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert r.entity_type == "payment"
    assert r.entity_id == p.id
    assert r.action_type == "created"
    assert r.performed_by == u1.id
    assert r.related_entity_type == "invoice"
    assert r.related_entity_id == i1.id
    assert r.workspace_id == w1.id
    assert r.performed_at == NOW
    assert r.ip_address is None
    assert r.user_agent is None
    assert set(r.changes.keys()) == {"after", "invoice_status_changed"}
    assert set(r.changes["after"].keys()) == {"payment_amount", "payment_date", "payment_method"}
    assert money(r.changes["after"]["payment_amount"]) == Decimal("250.00")
    assert r.changes["after"]["payment_date"] == "2026-09-01"
    assert r.changes["after"]["payment_method"] == "bank_transfer"
    assert r.changes["invoice_status_changed"] == {"before": "unpaid", "after": "partial"}
    assert r.description == f"Payment of $250.00 recorded for invoice ID {i1.id}, status changed to partial"


def test_ipm_cp_21__audit_row_no_status_change_no_suffix(db, M, w1, a1, u1, u2):
    """IPM-CP-21 -- no invoice_status_changed key, and no description suffix, when status is unchanged.
    Rules: create_payment R10, R11, R12."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("100.00"), payment_status="partial")
    mk_pay(db, i1, "100.00", date(2026, 8, 15), created_by_id=u2.id)
    M.create_payment(db, payment_data=d0(i1.id, payment_amount=Decimal("50.5")), workspace_id=w1.id, user_id=u1.id)
    reread(db, i1)
    assert i1.paid_amount == Decimal("150.50")
    assert i1.payment_status == "partial"
    rows = audit_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert "after" in r.changes
    assert "invoice_status_changed" not in r.changes
    assert r.description == f"Payment of $50.5 recorded for invoice ID {i1.id}"
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    assert evts[0].metadata_json["payment_amount"] == "50.5"
    assert evts[0].metadata_json["payment_status_before"] == "partial"
    assert evts[0].metadata_json["payment_status_after"] == "partial"


def test_ipm_cp_22__invoice_event_recorded(db, M, w1, a1, u1, u2):
    """IPM-CP-22 -- the payment_recorded invoice event has the expected shape.
    Rules: create_payment R12."""
    i1 = mk_inv(db, w1, a1, u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    e = evts[0]
    assert e.event_type == "payment_recorded"
    assert e.description == "Payment recorded"
    assert e.performed_by == u1.id
    assert e.created_at == NOW
    assert e.metadata_json == {
        "payment_id": p.id,
        "payment_amount": "250.00",
        "payment_method": "bank_transfer",
        "payment_status_before": "unpaid",
        "payment_status_after": "partial",
    }


def test_ipm_cp_23__null_payment_method_round_trips(db, M, w1, a1, u1, u2):
    """IPM-CP-23 -- payment_method=None is stored, audited and logged as null.
    Rules: create_payment R6, R10, R12."""
    i1 = mk_inv(db, w1, a1, u2.id)
    p = M.create_payment(db, payment_data=d0(i1.id, payment_method=None), workspace_id=w1.id, user_id=u1.id)
    reread(db, p)
    assert p.payment_method is None
    r = audit_rows(db)[0]
    assert r.changes["after"]["payment_method"] is None
    e = events_of(db, i1.id)[0]
    assert "payment_method" in e.metadata_json
    assert e.metadata_json["payment_method"] is None


@pytest.mark.xfail(strict=True, reason=BUG_603)
def test_ipm_cp_24__ip_and_user_agent_on_audit_row(db, M, w1, a1, u1, u2):
    """IPM-CP-24 -- the caller's IP/user agent reach the create audit row.
    Rules: create_payment R10a [BUG-603]."""
    i1 = mk_inv(db, w1, a1, u2.id)
    M.create_payment(
        db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id,
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)",
    )
    rows = audit_rows(db)
    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 (Test)"


def test_ipm_cp_25__linked_po_synced_paid(db, M, w1, a1, u1, u2):
    """IPM-CP-25 -- a fully-paying payment syncs the linked PO to paid, with a PO event.
    Rules: create_payment R13."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(
        db, w1, a1, u2.id, invoice_amount=Decimal("250.00"),
        order_type="purchase_order", order_id=po1.id,
    )
    po1.invoice_id = i1.id
    po1.paid = False
    db.add(po1)
    db.flush()
    p = M.create_payment(db, payment_data=d0(i1.id), workspace_id=w1.id, user_id=u1.id)
    assert p.id is not None
    reread(db, i1, po1)
    assert i1.payment_status == "paid"
    assert po1.paid is True
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].event_type == "payment_status_synced"
    assert evts[0].description == "Order marked paid from linked invoice"
    assert evts[0].performed_by == u1.id
    assert evts[0].metadata_json == {"paid": True}


@pytest.mark.xfail(strict=True, reason=BUG_604)
def test_ipm_cp_26__three_decimal_amount_rejected_by_schema():
    """IPM-CP-26 -- a 3-decimal payment_amount is rejected by the schema.
    Rules: create_payment R5a [BUG-604]."""
    with pytest.raises(ValidationError):
        InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("9.995"), payment_date=date(2026, 9, 1))


def test_ipm_cp_27__two_decimal_amount_accepted_by_schema():
    """IPM-CP-27 -- a 2-decimal payment_amount builds unchanged.
    Rules: create_payment R5a."""
    data = InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("9.99"), payment_date=date(2026, 9, 1))
    assert data.payment_amount == Decimal("9.99")


def test_ipm_cp_28__thirteen_integer_digit_amount_accepted_by_schema():
    """IPM-CP-28 -- a 13-integer-digit payment_amount builds unchanged.
    Rules: create_payment R5a."""
    data = InvoicePaymentCreate(
        invoice_id=1, payment_amount=Decimal("1234567890123.45"), payment_date=date(2026, 9, 1),
    )
    assert data.payment_amount == Decimal("1234567890123.45")


@pytest.mark.xfail(strict=True, reason=BUG_604)
def test_ipm_cp_29__fourteen_integer_digit_amount_rejected_by_schema():
    """IPM-CP-29 -- a 14-integer-digit payment_amount is rejected by the schema (spec G9).
    Rules: create_payment R5a [BUG-604]."""
    with pytest.raises(ValidationError):
        InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("12345678901234.00"), payment_date=date(2026, 9, 1))


# =========================================================================== #
# InvoicePaymentManager.update_payment
# =========================================================================== #

# Given for every update_payment case unless stated: I1 with paid_amount=250.00,
# payment_status="partial"; PA on I1.
def mk_up_default(db, w1, a1, u2):
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id)
    return i1, pa


def test_ipm_up_01__rename_reference_and_date(db, M, w1, a1, u1, u2):
    """IPM-UP-01 -- updating reference/date leaves every other field unchanged.
    Rules: update_payment R4."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    data = build_update(payment_reference="CHQ-999", payment_date=date(2026, 1, 1))
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.payment_reference == "CHQ-999"
    assert pa.payment_date == date(2026, 1, 1)
    assert pa.payment_amount == Decimal("250.00")
    assert pa.payment_method == "cheque"
    assert pa.bank_name == "City Bank"
    assert pa.transaction_id == "TXN-001"
    assert pa.notes == "First instalment"
    assert pa.invoice_id == i1.id
    assert pa.created_by == u2.id
    assert pa.is_voided is False


def test_ipm_up_02__invoice_and_linked_po_untouched(db, M, w1, a1, u1, u2):
    """IPM-UP-02 -- an update never touches the invoice or runs the linked-order sync.
    Rules: update_payment R6."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(
        db, w1, a1, u2.id, invoice_amount=Decimal("250.00"), paid_amount=Decimal("250.00"),
        payment_status="paid", order_type="purchase_order", order_id=po1.id,
    )
    po1.invoice_id = i1.id
    po1.paid = False
    db.add(po1)
    db.flush()
    pa = mk_pa(db, i1, u2.id)
    res = upd(M, db, pa.id, build_update(notes="Revised"), w1.id, u1.id)
    assert res is pa
    reread(db, pa, i1, po1)
    assert pa.notes == "Revised"
    assert i1.paid_amount == Decimal("250.00")
    assert i1.payment_status == "paid"
    assert i1.updated_by == u2.id
    assert po1.paid is False
    assert po_events(db) == []


def test_ipm_up_03__empty_string_distinct_from_null(db, M, w1, a1, u1, u2):
    """IPM-UP-03 -- an empty-string bank_name is stored as "" (not treated as null).
    Rules: update_payment R4."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    res = upd(M, db, pa.id, build_update(bank_name=""), w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.bank_name == ""
    assert pa.payment_method == "cheque"
    assert pa.payment_reference == "CHQ-881"
    assert pa.transaction_id == "TXN-001"
    assert pa.notes == "First instalment"


def test_ipm_up_04__amount_change_rejected(db, M, w1, a1, u1, u2):
    """IPM-UP-04 -- changing payment_amount is rejected; nothing changes.
    Rules: update_payment R2; Errors row 2."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    pay_before, inv_before = pay_snapshot(pa), inv_snapshot(i1)
    data = build_update(payment_amount=Decimal("300.00"), notes="changed")
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pa.id, data, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail.startswith("Cannot change payment amount.")
    reread(db, pa, i1)
    assert pa.payment_amount == Decimal("250.00")
    assert pa.notes == "First instalment"
    assert pay_snapshot(pa) == pay_before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_up_05__same_amount_different_representation_ok(db, M, w1, a1, u1, u2):
    """IPM-UP-05 -- an equal amount (different Decimal representation) proceeds.
    Rules: update_payment R2."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    data = build_update(payment_amount=Decimal("250.0"), notes="Corrected")
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.payment_amount == Decimal("250.00")
    assert pa.notes == "Corrected"


def test_ipm_up_06__one_cent_amount_change_rejected(db, M, w1, a1, u1, u2):
    """IPM-UP-06 -- a one-cent amount change is rejected; nothing changes.
    Rules: update_payment R2."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before = pay_snapshot(pa)
    data = build_update(payment_amount=Decimal("250.01"))
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pa.id, data, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail.startswith("Cannot change payment amount.")
    reread(db, pa)
    assert pay_snapshot(pa) == before


def test_ipm_up_07__missing_payment_404(db, M, w1, a1, u1, u2):
    """IPM-UP-07 -- an unknown payment id raises 404; nothing changes.
    Rules: update_payment R1; Errors row 1."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before, inv_before = pay_snapshot(pa), inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        upd(M, db, NOID, build_update(notes="x"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(NOID)
    reread(db, pa, i1)
    assert pay_snapshot(pa) == before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_up_08__other_workspace_payment_404(db, M, w1, w2, a1, a2, u1, u2):
    """IPM-UP-08 -- a payment of another workspace raises 404; nothing changes.
    Rules: update_payment R1; Errors row 1."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    i2 = mk_inv(db, w2, a2, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pb = mk_pay(db, i2, "250.00", date(2026, 9, 1), created_by_id=u2.id, payment_reference="W2-REF")
    pa_before, pb_before = pay_snapshot(pa), pay_snapshot(pb)
    i1_before, i2_before = inv_snapshot(i1), inv_snapshot(i2)
    data = build_update(payment_reference="HACK")
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pb.id, data, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(pb.id)
    reread(db, pb, pa, i1, i2)
    assert pb.payment_reference == "W2-REF"
    assert pay_snapshot(pb) == pb_before
    assert pay_snapshot(pa) == pa_before
    assert inv_snapshot(i1) == i1_before
    assert inv_snapshot(i2) == i2_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert events_of(db, i2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_606)
def test_ipm_up_09__voided_payment_cannot_be_edited(db, M, w1, a1, u1, u2):
    """IPM-UP-09 -- editing a voided payment is rejected; nothing changes.
    Rules: update_payment R3 [BUG-606]; Errors row 3."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("0.00"), payment_status="unpaid")
    pv = mk_pay(
        db, i1, "250.00", date(2026, 9, 1), created_by_id=u2.id,
        payment_reference="CHQ-881", voided=True, voided_by_id=u2.id,
    )
    before, inv_before = pay_snapshot(pv), inv_snapshot(i1)
    data = build_update(payment_reference="CHQ-999", payment_date=date(2026, 1, 1))
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pv.id, data, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Voided payments cannot be edited"
    reread(db, pv, i1)
    assert pay_snapshot(pv) == before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_up_10__other_workspace_voided_payment_404(db, M, w1, w2, a1, a2, u1, u2):
    """IPM-UP-10 -- another workspace's voided payment is 404, not the voided error.
    Rules: update_payment R1, R3 (order)."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    i2 = mk_inv(db, w2, a2, u2.id)
    pv2 = mk_pay(db, i2, "250.00", date(2026, 9, 1), created_by_id=u2.id, voided=True, voided_by_id=u2.id)
    before = pay_snapshot(pv2)
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pv2.id, build_update(notes="x"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(pv2.id)
    reread(db, pv2)
    assert pay_snapshot(pv2) == before


def test_ipm_up_11__voided_invoice_does_not_block_update(db, M, w1, a1, u1, u2):
    """IPM-UP-11 -- the invoice's own voided status does not block editing an active payment.
    Rules: update_payment R3."""
    i1 = mk_inv(db, w1, a1, u2.id, invoice_status="voided", paid_amount=Decimal("250.00"))
    pa = mk_pa(db, i1, u2.id)
    res = upd(M, db, pa.id, build_update(notes="Revised"), w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.notes == "Revised"


@pytest.mark.xfail(strict=True, reason=BUG_608)
def test_ipm_up_12__explicit_nulls_clear_all_text_fields(db, M, w1, a1, u1, u2):
    """IPM-UP-12 -- an explicit null clears every clearable text field.
    Rules: update_payment R5 [BUG-608]."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    data = build_update(
        payment_method=None, payment_reference=None, bank_name=None,
        transaction_id=None, notes=None,
    )
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.payment_method is None
    assert pa.payment_reference is None
    assert pa.bank_name is None
    assert pa.transaction_id is None
    assert pa.notes is None
    assert pa.payment_amount == Decimal("250.00")
    assert pa.payment_date == date(2026, 9, 1)


@pytest.mark.xfail(strict=True, reason=BUG_608)
def test_ipm_up_13__explicit_null_clears_single_field(db, M, w1, a1, u1, u2):
    """IPM-UP-13 -- an explicit null clears just the targeted field.
    Rules: update_payment R5 [BUG-608]."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    res = upd(M, db, pa.id, build_update(bank_name=None), w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.bank_name is None
    assert pa.payment_method == "cheque"
    assert pa.payment_reference == "CHQ-881"
    assert pa.transaction_id == "TXN-001"
    assert pa.notes == "First instalment"


def test_ipm_up_14__null_date_and_amount_ignored(db, M, w1, a1, u1, u2):
    """IPM-UP-14 -- an explicit null for payment_date/payment_amount is ignored; no logging.
    Rules: update_payment R5, R6a (no change)."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before = pay_snapshot(pa)
    data = build_update(payment_date=None, payment_amount=None)
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.payment_date == date(2026, 9, 1)
    assert pa.payment_amount == Decimal("250.00")
    assert pay_snapshot(pa) == before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_up_15__empty_body_no_op(db, M, w1, a1, u1, u2):
    """IPM-UP-15 -- an update with no fields changes nothing and logs nothing.
    Rules: update_payment R7, R6a (no change)."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before = pay_snapshot(pa)
    res = upd(M, db, pa.id, build_update(), w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pay_snapshot(pa) == before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_up_16__all_null_on_already_null_fields_is_noop(db, M, w1, a1, u1, u2):
    """IPM-UP-16 -- nulling fields that are already null changes nothing and logs nothing.
    Rules: update_payment R7, R6a (no change)."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pn = mk_pay(db, i1, "250.00", date(2026, 9, 1), created_by_id=u2.id)
    data = build_update(
        payment_method=None, payment_reference=None, bank_name=None,
        transaction_id=None, notes=None,
    )
    res = upd(M, db, pn.id, data, w1.id, u1.id)
    assert res is pn
    reread(db, pn)
    assert pn.payment_method is None
    assert pn.payment_reference is None
    assert pn.bank_name is None
    assert pn.transaction_id is None
    assert pn.notes is None
    assert pn.payment_amount == Decimal("250.00")
    assert pn.payment_date == date(2026, 9, 1)
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_608)
def test_ipm_up_17__clearing_one_set_field_is_audited(db, M, w1, a1, u1, u2):
    """IPM-UP-17 -- clearing the one currently-set field counts as a change (audit + event).
    Rules: update_payment R7, R5, R6a [BUG-608, BUG-607]."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pm = mk_pay(db, i1, "250.00", date(2026, 9, 1), created_by_id=u2.id, notes="Keep?")
    data = build_update(
        payment_method=None, payment_reference=None, bank_name=None,
        transaction_id=None, notes=None,
    )
    res = upd(M, db, pm.id, data, w1.id, u1.id)
    assert res is pm
    reread(db, pm)
    assert pm.notes is None
    rows = audit_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert r.action_type == "updated"
    assert r.entity_id == pm.id
    assert r.changes == {"before": {"notes": "Keep?"}, "after": {"notes": None}}
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    assert evts[0].event_type == "payment_updated"
    assert evts[0].metadata_json["changed_fields"] == ["notes"]


@pytest.mark.xfail(strict=True, reason=BUG_607)
def test_ipm_up_18__audit_row_and_event_on_change(db, M, w1, a1, u1, u2):
    """IPM-UP-18 -- a real change writes a full audit row and invoice event.
    Rules: update_payment R6a [BUG-607]."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    data = build_update(payment_reference="CHQ-999", payment_date=date(2026, 1, 1))
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    rows = audit_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert r.entity_type == "payment"
    assert r.entity_id == pa.id
    assert r.action_type == "updated"
    assert r.performed_by == u1.id
    assert r.related_entity_type == "invoice"
    assert r.related_entity_id == i1.id
    assert r.workspace_id == w1.id
    assert r.performed_at == NOW
    assert r.ip_address is None
    assert r.user_agent is None
    assert r.changes == {
        "before": {"payment_reference": "CHQ-881", "payment_date": "2026-09-01"},
        "after": {"payment_reference": "CHQ-999", "payment_date": "2026-01-01"},
    }
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    e = evts[0]
    assert e.event_type == "payment_updated"
    assert e.description == "Payment updated"
    assert e.performed_by == u1.id
    assert e.created_at == NOW
    assert e.metadata_json["payment_id"] == pa.id
    assert sorted(e.metadata_json["changed_fields"]) == ["payment_date", "payment_reference"]
    assert set(e.metadata_json.keys()) == {"payment_id", "changed_fields"}


@pytest.mark.xfail(strict=True, reason=BUG_607)
def test_ipm_up_19__only_actually_changed_field_logged(db, M, w1, a1, u1, u2):
    """IPM-UP-19 -- same-value fields are not counted; only the real change is logged.
    Rules: update_payment R6a (HR-9) [BUG-607]."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    data = build_update(
        payment_reference="CHQ-881", payment_method="cheque",
        payment_amount=Decimal("250.0"), notes="Revised",
    )
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pa.notes == "Revised"
    rows = audit_rows(db)
    assert len(rows) == 1
    assert rows[0].changes == {"before": {"notes": "First instalment"}, "after": {"notes": "Revised"}}
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    assert evts[0].metadata_json["changed_fields"] == ["notes"]


def test_ipm_up_20__same_values_sent_no_change_no_log(db, M, w1, a1, u1, u2):
    """IPM-UP-20 -- sending the current values makes no change and logs nothing.
    Rules: update_payment R6a (no change)."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before = pay_snapshot(pa)
    data = build_update(
        payment_reference="CHQ-881", payment_method="cheque", payment_amount=Decimal("250.00"),
    )
    res = upd(M, db, pa.id, data, w1.id, u1.id)
    assert res is pa
    reread(db, pa)
    assert pay_snapshot(pa) == before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_604)
def test_ipm_up_21__three_decimal_amount_rejected_by_schema():
    """IPM-UP-21 -- a 3-decimal payment_amount is rejected by the update schema.
    Rules: update_payment Inputs [BUG-604]."""
    with pytest.raises(ValidationError):
        InvoicePaymentUpdate(payment_amount=Decimal("9.995"))


def test_ipm_up_22__two_decimal_amount_accepted_by_schema():
    """IPM-UP-22 -- a 2-decimal payment_amount builds unchanged.
    Rules: update_payment Inputs."""
    data = InvoicePaymentUpdate(payment_amount=Decimal("9.99"))
    assert data.payment_amount == Decimal("9.99")


@pytest.mark.xfail(strict=True, reason=BUG_611)
def test_ipm_up_23__amount_change_message_points_to_void(db, M, w1, a1, u1, u2):
    """IPM-UP-23 -- the amount-change error tells the user to void, not delete.
    Rules: update_payment R2a [BUG-611]; Errors row 2."""
    i1, pa = mk_up_default(db, w1, a1, u2)
    before, inv_before = pay_snapshot(pa), inv_snapshot(i1)
    data = build_update(payment_amount=Decimal("300.00"), notes="changed")
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pa.id, data, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change payment amount. Void and re-create payment instead."
    reread(db, pa, i1)
    assert pay_snapshot(pa) == before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_606)
def test_ipm_up_24__voided_check_precedes_amount_check(db, M, w1, a1, u1, u2):
    """IPM-UP-24 -- a voided payment given a different amount gets the voided error, not the amount one.
    Rules: update_payment R3a, R3 [BUG-606]."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("0.00"), payment_status="unpaid")
    pv = mk_pay(db, i1, "250.00", date(2026, 9, 1), created_by_id=u2.id, voided=True, voided_by_id=u2.id)
    before, inv_before = pay_snapshot(pv), inv_snapshot(i1)
    data = build_update(payment_amount=Decimal("300.00"), notes="changed")
    with pytest.raises(HTTPException) as exc:
        upd(M, db, pv.id, data, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Voided payments cannot be edited"
    reread(db, pv, i1)
    assert pay_snapshot(pv) == before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


# =========================================================================== #
# InvoicePaymentManager.list_payments_by_invoice
# =========================================================================== #

def test_ipm_lp_01__happy_path_order_and_names(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-01 -- default call returns date-desc tuples with creator names.
    Rules: list_payments_by_invoice R2, R3, R4, Returns."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert len(result) == 4
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id, la.id]
    assert [name for _, name in result] == ["Bilal Khan", "Nusrat Jahan", None, "Alice Rahman"]
    lc_elem = result[1][0]
    assert lc_elem.is_voided is True
    assert lc_elem.voided_by == u2.id
    assert lc_elem.void_note == "Duplicate entry"


def test_ipm_lp_02__invoice_missing_404(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-02 -- an unknown invoice id raises 404.
    Rules: list_payments_by_invoice R1; Errors row 1."""
    i1 = mk_inv(db, w1, a1, u2.id)
    mk_l4(db, i1, u1, u2, u3)
    with pytest.raises(HTTPException) as exc:
        M.list_payments_by_invoice(db, NOID, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(NOID)


def test_ipm_lp_03__other_workspace_invoice_404(db, M, w1, w2, a2, u2):
    """IPM-LP-03 -- an invoice of another workspace raises 404.
    Rules: list_payments_by_invoice R1; Errors row 1."""
    i2 = mk_inv(db, w2, a2, u2.id)
    mk_pay(db, i2, "50.00", date(2026, 9, 1), created_by_id=u2.id)
    with pytest.raises(HTTPException) as exc:
        M.list_payments_by_invoice(db, i2.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(i2.id)


def test_ipm_lp_04__other_invoice_payment_absent(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-04 -- a payment of a different invoice in the same workspace is excluded.
    Rules: list_payments_by_invoice R2."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    i1b = mk_inv(db, w1, a1, u2.id)
    mk_pay(db, i1b, "999.00", date(2026, 9, 4), created_by_id=u2.id)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id, la.id]


def test_ipm_lp_05__other_workspace_payment_row_absent(db, M, w1, w2, a1, u1, u2, u3):
    """IPM-LP-05 -- a payment row stamped with another workspace is excluded.
    Rules: list_payments_by_invoice R2."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    mk_pay(db, i1, "500.00", date(2026, 9, 4), created_by_id=u2.id, workspace_id=w2.id)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id, la.id]


def test_ipm_lp_06__no_payments_returns_empty_list(db, M, w1, a1, u2):
    """IPM-LP-06 -- an invoice with no payments returns [].
    Rules: list_payments_by_invoice R2."""
    i1b = mk_inv(db, w1, a1, u2.id)
    result = M.list_payments_by_invoice(db, i1b.id, w1.id)
    assert result == []
    assert type(result) is list


def test_ipm_lp_07__voided_invoice_still_lists_payments(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-07 -- a voided invoice's payments are still listed.
    Rules: list_payments_by_invoice R6."""
    i1 = mk_inv(db, w1, a1, u2.id, invoice_status="voided")
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id, la.id]


def test_ipm_lp_08__draft_invoice_still_lists_payments(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-08 -- a draft invoice's payments are still listed.
    Rules: list_payments_by_invoice R6."""
    i1 = mk_inv(db, w1, a1, u2.id, invoice_status="draft")
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id, la.id]


@pytest.mark.xfail(strict=True, reason=BUG_600)
def test_ipm_lp_09__same_date_ties_ordered_by_id_desc(db, M, w1, a1, u2):
    """IPM-LP-09 -- same-date payments are tie-broken by id descending.
    Rules: list_payments_by_invoice R4 [BUG-600]."""
    i1 = mk_inv(db, w1, a1, u2.id)
    a_id, b_id, c_id = reserve_payment_ids(db, 3)
    for pid in (c_id, a_id, b_id):
        mk_pay(db, i1, "10.00", date(2026, 9, 1), created_by_id=u2.id, id=pid)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert [p.id for p, _ in result] == [c_id, b_id, a_id]


@pytest.mark.xfail(strict=True, reason=BUG_600)
def test_ipm_lp_10__paging_after_tie_break(db, M, w1, a1, u2):
    """IPM-LP-10 -- paging applies after the id-desc tie-break.
    Rules: list_payments_by_invoice R4, R5 [BUG-600]."""
    i1 = mk_inv(db, w1, a1, u2.id)
    a_id, b_id, c_id = reserve_payment_ids(db, 3)
    for pid in (c_id, a_id, b_id):
        mk_pay(db, i1, "10.00", date(2026, 9, 1), created_by_id=u2.id, id=pid)
    result = M.list_payments_by_invoice(db, i1.id, w1.id, skip=1, limit=1)
    assert [p.id for p, _ in result] == [b_id]


def test_ipm_lp_11__skip_one_limit_two(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-11 -- skip=1, limit=2 returns the middle window.
    Rules: list_payments_by_invoice R5."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id, skip=1, limit=2)
    assert [p.id for p, _ in result] == [lc.id, ld.id]


def test_ipm_lp_12__skip_zero_limit_three(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-12 -- skip=0, limit=3 returns the first three.
    Rules: list_payments_by_invoice R5."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id, skip=0, limit=3)
    assert [p.id for p, _ in result] == [lb.id, lc.id, ld.id]


def test_ipm_lp_13__skip_three_limit_100(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-13 -- skip=3, limit=100 returns the remainder.
    Rules: list_payments_by_invoice R5."""
    i1 = mk_inv(db, w1, a1, u2.id)
    la, lb, lc, ld = mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id, skip=3, limit=100)
    assert [p.id for p, _ in result] == [la.id]


def test_ipm_lp_14__skip_past_end_empty(db, M, w1, a1, u1, u2, u3):
    """IPM-LP-14 -- skip past the end returns [].
    Rules: list_payments_by_invoice R5."""
    i1 = mk_inv(db, w1, a1, u2.id)
    mk_l4(db, i1, u1, u2, u3)
    result = M.list_payments_by_invoice(db, i1.id, w1.id, skip=4, limit=100)
    assert result == []


def test_ipm_lp_15__default_limit_100(db, M, w1, a1, u2):
    """IPM-LP-15 -- the default limit returns at most 100, most-recent first.
    Rules: list_payments_by_invoice R5 (default limit)."""
    i1 = mk_inv(db, w1, a1, u2.id)
    for k in range(1, 102):
        mk_pay(db, i1, "10.00", date(2026, 1, 1) + timedelta(days=k), created_by_id=u2.id)
    result = M.list_payments_by_invoice(db, i1.id, w1.id)
    assert len(result) == 100
    dates = [p.payment_date for p, _ in result]
    assert dates[0] == date(2026, 1, 1) + timedelta(days=101)
    assert dates[-1] == date(2026, 1, 1) + timedelta(days=2)
    assert (date(2026, 1, 1) + timedelta(days=1)) not in dates


# =========================================================================== #
# InvoicePaymentManager.delete_payment
# =========================================================================== #

# Given for every delete_payment case unless stated: I1 with paid_amount=250.00,
# payment_status="partial", order_type="purchase_order", order_id=PO1.id;
# PO1 with invoice_id=I1.id, paid=False; PA on I1.
def mk_dp_default(db, w1, a1, u2):
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(
        db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial",
        order_type="purchase_order", order_id=po1.id,
    )
    po1.invoice_id = i1.id
    po1.paid = False
    db.add(po1)
    db.flush()
    pa = mk_pa(db, i1, u2.id)
    return i1, po1, pa


def payment_exists(db, payment_id):
    return db.execute(select(InvoicePayment).where(InvoicePayment.id == payment_id)).scalar_one_or_none() is not None


def test_ipm_dp_01__missing_payment_404(db, M, w1, a1, u1, u2):
    """IPM-DP-01 -- an unknown payment id raises 404; nothing changes.
    Rules: delete_payment R1; Errors row 1."""
    i1, po1, pa = mk_dp_default(db, w1, a1, u2)
    pay_before, inv_before = pay_snapshot(pa), inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.delete_payment(db, payment_id=NOID, workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(NOID)
    assert payment_exists(db, pa.id)
    reread(db, pa, i1, po1)
    assert pay_snapshot(pa) == pay_before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_dp_02__other_workspace_payment_404(db, M, w1, w2, a1, a2, u1, u2):
    """IPM-DP-02 -- a payment of another workspace raises 404; nothing changes.
    Rules: delete_payment R1; Errors row 1."""
    i1, po1, pa = mk_dp_default(db, w1, a1, u2)
    i2 = mk_inv(db, w2, a2, u2.id, paid_amount=Decimal("100.00"), payment_status="partial")
    pb = mk_pay(db, i2, "100.00", date(2026, 9, 1), created_by_id=u2.id)
    pa_before, pb_before = pay_snapshot(pa), pay_snapshot(pb)
    i1_before, i2_before = inv_snapshot(i1), inv_snapshot(i2)
    with pytest.raises(HTTPException) as exc:
        M.delete_payment(db, payment_id=pb.id, workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(pb.id)
    assert payment_exists(db, pb.id)
    reread(db, i2, pb, pa, i1, po1)
    assert i2.paid_amount == Decimal("100.00")
    assert i2.payment_status == "partial"
    assert pay_snapshot(pb) == pb_before
    assert pay_snapshot(pa) == pa_before
    assert inv_snapshot(i1) == i1_before
    assert inv_snapshot(i2) == i2_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert events_of(db, i2.id) == []
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ipm_dp_03__existing_payment_deletion_refused(db, M, w1, a1, u1, u2):
    """IPM-DP-03 -- deleting an existing active payment is refused; nothing changes.
    Rules: delete_payment R2 [BUG-609]; Errors row 2."""
    i1, po1, pa = mk_dp_default(db, w1, a1, u2)
    with pytest.raises(HTTPException) as exc:
        M.delete_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments cannot be deleted — void them instead"
    assert payment_exists(db, pa.id)
    reread(db, pa, i1, po1)
    assert pa.payment_amount == Decimal("250.00")
    assert i1.paid_amount == Decimal("250.00")
    assert i1.payment_status == "partial"
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert po1.paid is False
    assert po_events(db) == []


@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ipm_dp_04__voided_payment_deletion_refused(db, M, w1, a1, u1, u2):
    """IPM-DP-04 -- deleting a voided payment is also refused; nothing changes.
    Rules: delete_payment R2 [BUG-609]."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("0.00"), payment_status="unpaid")
    pv = mk_pay(db, i1, "250.00", date(2026, 9, 1), created_by_id=u2.id, voided=True, voided_by_id=u2.id)
    pay_before, inv_before = pay_snapshot(pv), inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.delete_payment(db, payment_id=pv.id, workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments cannot be deleted — void them instead"
    assert payment_exists(db, pv.id)
    reread(db, pv, i1)
    assert pv.is_voided is True
    assert pv.void_note == "Duplicate entry"
    assert pay_snapshot(pv) == pay_before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ipm_dp_05__voided_invoice_payment_deletion_refused(db, M, w1, a1, u1, u2):
    """IPM-DP-05 -- a payment of a voided invoice is also refused deletion.
    Rules: delete_payment R2 [BUG-609]."""
    i1, po1, pa = mk_dp_default(db, w1, a1, u2)
    i1.invoice_status = "voided"
    db.add(i1)
    db.flush()
    pay_before, inv_before = pay_snapshot(pa), inv_snapshot(i1)
    with pytest.raises(HTTPException) as exc:
        M.delete_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payments cannot be deleted — void them instead"
    assert payment_exists(db, pa.id)
    reread(db, pa, i1, po1)
    assert pay_snapshot(pa) == pay_before
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


# =========================================================================== #
# InvoicePaymentManager.void_payment
# =========================================================================== #

# Given for every void_payment case unless stated: I1 with paid_amount=1000.00,
# payment_status="paid"; PA on I1 (250.00, cheque, 2026-09-01); PB=PAY(I1,750.00,2026-09-02).
def mk_vp_default(db, w1, a1, u2):
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("1000.00"), payment_status="paid")
    pa = mk_pa(db, i1, u2.id)
    pb = mk_pay(db, i1, "750.00", date(2026, 9, 2), created_by_id=u2.id)
    return i1, pa, pb


def test_ipm_vp_01__happy_path_void_fields_set(db, M, w1, a1, u1, u2):
    """IPM-VP-01 -- voiding sets the void fields; the row and other payments are untouched.
    Rules: void_payment R5, R6, R8."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, pa, pb)
    assert pa.is_voided is True
    assert pa.voided_at == NOW
    assert pa.voided_by == u1.id
    assert pa.void_note == "Cheque bounced"
    assert pa.payment_amount == Decimal("250.00")
    assert pa.payment_reference == "CHQ-881"
    assert pa.created_by == u2.id
    assert pb.is_voided is False


def test_ipm_vp_02__invoice_recomputed_partial(db, M, w1, a1, u1, u2):
    """IPM-VP-02 -- voiding recomputes the invoice to the remaining active total.
    Rules: void_payment R7."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("750.00")
    assert i1.payment_status == "partial"


def test_ipm_vp_03__only_payment_voided_invoice_unpaid(db, M, w1, a1, u1, u2):
    """IPM-VP-03 -- voiding the only payment leaves the invoice unpaid.
    Rules: void_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("0.00")
    assert i1.payment_status == "unpaid"


def test_ipm_vp_04__remaining_total_still_meets_invoice_amount(db, M, w1, a1, u1, u2):
    """IPM-VP-04 -- the remaining total still meeting invoice_amount keeps the invoice paid.
    Rules: void_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("1000.01"), payment_status="paid")
    pa = mk_pa(db, i1, u2.id, payment_amount=Decimal("0.01"))
    mk_pay(db, i1, "1000.00", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("1000.00")
    assert i1.payment_status == "paid"


def test_ipm_vp_05__remaining_total_drops_below_invoice_amount(db, M, w1, a1, u1, u2):
    """IPM-VP-05 -- the remaining total dropping below invoice_amount makes the invoice partial.
    Rules: void_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("1000.00"), payment_status="paid")
    pa = mk_pa(db, i1, u2.id, payment_amount=Decimal("0.01"))
    mk_pay(db, i1, "999.99", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("999.99")
    assert i1.payment_status == "partial"


def test_ipm_vp_06__already_voided_sibling_excluded_from_recompute(db, M, w1, a1, u1, u2):
    """IPM-VP-06 -- an already-voided sibling payment does not count toward the recompute.
    Rules: void_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id)
    mk_pay(db, i1, "750.00", date(2026, 9, 2), created_by_id=u2.id, voided=True, voided_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("0.00")
    assert i1.payment_status == "unpaid"


def test_ipm_vp_07__other_workspace_row_excluded_from_recompute(db, M, w1, w2, a1, u1, u2):
    """IPM-VP-07 -- a payment row stamped with another workspace is excluded from the recompute.
    Rules: void_payment R7."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id)
    mk_pay(db, i1, "500.00", date(2026, 9, 4), created_by_id=u2.id, workspace_id=w2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("0.00")
    assert i1.payment_status == "unpaid"


def test_ipm_vp_08__missing_payment_404(db, M, w1, a1, u1, u2):
    """IPM-VP-08 -- an unknown payment id raises 404; nothing changes.
    Rules: void_payment R1; Errors row 1."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    before_i1 = inv_snapshot(i1)
    pa_before, pb_before = pay_snapshot(pa), pay_snapshot(pb)
    with pytest.raises(HTTPException) as exc:
        M.void_payment(db, payment_id=NOID, workspace_id=w1.id, user_id=u1.id, void_note="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(NOID)
    reread(db, i1, pa, pb)
    assert inv_snapshot(i1) == before_i1
    assert pay_snapshot(pa) == pa_before
    assert pay_snapshot(pb) == pb_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_vp_09__other_workspace_payment_404(db, M, w1, w2, a1, a2, u1, u2):
    """IPM-VP-09 -- a payment of another workspace raises 404; nothing changes.
    Rules: void_payment R1; Errors row 1."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    i2 = mk_inv(db, w2, a2, u2.id, paid_amount=Decimal("100.00"), payment_status="partial")
    pw = mk_pay(db, i2, "100.00", date(2026, 9, 1), created_by_id=u2.id)
    pw_before = pay_snapshot(pw)
    pa_before, pb_before = pay_snapshot(pa), pay_snapshot(pb)
    i1_before, i2_before = inv_snapshot(i1), inv_snapshot(i2)
    with pytest.raises(HTTPException) as exc:
        M.void_payment(db, payment_id=pw.id, workspace_id=w1.id, user_id=u1.id, void_note="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_payment(pw.id)
    reread(db, pw, i2, i1, pa, pb)
    assert pay_snapshot(pa) == pa_before
    assert pay_snapshot(pb) == pb_before
    assert pw.is_voided is False
    assert i2.paid_amount == Decimal("100.00")
    assert i2.payment_status == "partial"
    assert pay_snapshot(pw) == pw_before
    assert inv_snapshot(i1) == i1_before
    assert inv_snapshot(i2) == i2_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []
    assert events_of(db, i2.id) == []


def test_ipm_vp_10__already_voided_payment_rejected(db, M, w1, a1, u1, u2):
    """IPM-VP-10 -- voiding an already-voided payment is rejected; nothing changes.
    Rules: void_payment R2; Errors row 2."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("750.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id, voided=True, voided_by_id=u2.id)
    pb = mk_pay(db, i1, "750.00", date(2026, 9, 2), created_by_id=u2.id)
    inv_before = inv_snapshot(i1)
    pa_before, pb_before = pay_snapshot(pa), pay_snapshot(pb)
    with pytest.raises(HTTPException) as exc:
        M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment is already voided"
    reread(db, pa, pb, i1)
    assert pay_snapshot(pa) == pa_before
    assert pay_snapshot(pb) == pb_before
    assert pb.is_voided is False
    assert pb.payment_amount == Decimal("750.00")
    assert pa.voided_at == T0
    assert pa.voided_by == u2.id
    assert pa.void_note == "Duplicate entry"
    assert inv_snapshot(i1) == inv_before
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


def test_ipm_vp_11__invoice_missing_404(db, M, w1, w2, a2, u1, u2):
    """IPM-VP-11 -- the payment's invoice missing from this workspace raises 404 (inconsistent data).
    Rules: void_payment R3; Errors row 3."""
    i2 = mk_inv(db, w2, a2, u2.id)
    pi_ = mk_pay(db, i2, "250.00", date(2026, 9, 1), created_by_id=u2.id, workspace_id=w1.id)
    i2_before = inv_snapshot(i2)
    pi_before = pay_snapshot(pi_)
    with pytest.raises(HTTPException) as exc:
        M.void_payment(db, payment_id=pi_.id, workspace_id=w1.id, user_id=u1.id, void_note="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(i2.id)
    reread(db, pi_, i2)
    assert pi_.is_voided is False
    assert pay_snapshot(pi_) == pi_before
    assert inv_snapshot(i2) == i2_before
    assert audit_rows(db) == []
    assert events_of(db, i2.id) == []


def test_ipm_vp_12__invoice_status_and_lock_not_checked(db, M, w1, a1, u1, u2):
    """IPM-VP-12 -- a draft, payment-locked invoice does not block voiding.
    Rules: void_payment R4."""
    i1 = mk_inv(
        db, w1, a1, u2.id, paid_amount=Decimal("1000.00"), payment_status="paid",
        invoice_status="draft", allow_payments=False, payment_locked_reason="Locked",
    )
    pa = mk_pa(db, i1, u2.id)
    mk_pay(db, i1, "750.00", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, pa, i1)
    assert pa.is_voided is True
    assert i1.paid_amount == Decimal("750.00")
    assert i1.payment_status == "partial"
    assert i1.invoice_status == "draft"
    assert i1.allow_payments is False


def test_ipm_vp_13__audit_row_and_status_change_description(db, M, w1, a1, u1, u2):
    """IPM-VP-13 -- the void audit row and description on a status-changing void.
    Rules: void_payment R10, R11, R12 (default)."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    rows = audit_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert r.entity_type == "payment"
    assert r.entity_id == pa.id
    assert r.action_type == "voided"
    assert r.performed_by == u1.id
    assert r.related_entity_type == "invoice"
    assert r.related_entity_id == i1.id
    assert r.workspace_id == w1.id
    assert r.performed_at == NOW
    assert r.ip_address is None
    assert r.user_agent is None
    assert set(r.changes.keys()) == {"payment_voided", "invoice_payment_status"}
    assert set(r.changes["payment_voided"].keys()) == {"payment_amount", "payment_date", "payment_method"}
    assert money(r.changes["payment_voided"]["payment_amount"]) == Decimal("250.00")
    assert r.changes["payment_voided"]["payment_date"] == "2026-09-01"
    assert r.changes["payment_voided"]["payment_method"] == "cheque"
    assert r.changes["invoice_payment_status"] == {"before": "paid", "after": "partial"}
    assert r.description == f"Payment of $250.00 voided for invoice ID {i1.id}. Reason: Cheque bounced"


def test_ipm_vp_14__no_status_change_key_absent(db, M, w1, a1, u1, u2):
    """IPM-VP-14 -- no invoice_payment_status key, and status before/after equal, when unchanged.
    Rules: void_payment R11, R13."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("300.00"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id, payment_amount=Decimal("100.00"))
    mk_pay(db, i1, "200.00", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1)
    assert i1.paid_amount == Decimal("200.00")
    assert i1.payment_status == "partial"
    rows = audit_rows(db)
    assert len(rows) == 1
    assert "payment_voided" in rows[0].changes
    assert "invoice_payment_status" not in rows[0].changes
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    assert evts[0].metadata_json["payment_status_before"] == "partial"
    assert evts[0].metadata_json["payment_status_after"] == "partial"


def test_ipm_vp_15__invoice_event_shape(db, M, w1, a1, u1, u2):
    """IPM-VP-15 -- the payment_voided invoice event has the expected shape.
    Rules: void_payment R13."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    evts = events_of(db, i1.id)
    assert len(evts) == 1
    e = evts[0]
    assert e.event_type == "payment_voided"
    assert e.description == "Payment voided"
    assert e.performed_by == u1.id
    assert e.created_at == NOW
    assert e.metadata_json == {
        "payment_id": pa.id,
        "payment_amount": "250.00",
        "payment_method": "cheque",
        "void_note": "Cheque bounced",
        "payment_status_before": "paid",
        "payment_status_after": "partial",
    }


@pytest.mark.xfail(strict=True, reason=BUG_603)
def test_ipm_vp_16__ip_and_user_agent_on_audit_row(db, M, w1, a1, u1, u2):
    """IPM-VP-16 -- the caller's IP/user agent reach the void audit row.
    Rules: void_payment R12 [BUG-603]."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    M.void_payment(
        db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced",
        ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)",
    )
    rows = audit_rows(db)
    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 (Test)"


def test_ipm_vp_17__linked_po_synced_unpaid(db, M, w1, a1, u1, u2):
    """IPM-VP-17 -- voiding down to partial syncs the linked PO back to unpaid, with a PO event.
    Rules: void_payment R14."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(
        db, w1, a1, u2.id, paid_amount=Decimal("1000.00"), payment_status="paid",
        order_type="purchase_order", order_id=po1.id,
    )
    po1.invoice_id = i1.id
    po1.paid = True
    db.add(po1)
    db.flush()
    pa = mk_pa(db, i1, u2.id)
    mk_pay(db, i1, "750.00", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1, po1)
    assert i1.payment_status == "partial"
    assert po1.paid is False
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].event_type == "payment_status_synced"
    assert evts[0].description == "Order marked unpaid from linked invoice"
    assert evts[0].performed_by == u1.id
    assert evts[0].metadata_json == {"paid": False}


@pytest.mark.xfail(strict=True, reason=BUG_601)
def test_ipm_vp_18__locks_the_invoice(db, M, engine, w1, a1, u1, u2):
    """IPM-VP-18 -- void_payment locks the invoice before re-reading the payment.
    Rules: void_payment R9 [BUG-601]."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    with SQLCapture(engine) as cap:
        res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, pa)
    assert pa.is_voided is True
    assert cap.locks_invoice()
    assert cap.selects_payment_after_lock()


@pytest.mark.xfail(strict=True, reason=BUG_601)
def test_ipm_vp_19__concurrent_void_loses_the_race(db, M, engine, w1, a1, u1, u2):
    """IPM-VP-19 -- a concurrent void that lands first is not overwritten by the loser.
    Rules: void_payment R9, R2 [BUG-601]."""
    i1, pa, pb = mk_vp_default(db, w1, a1, u2)
    with VoidRace(engine, pa.id, u2.id, T0, "Voided by other user"):
        with pytest.raises(HTTPException) as exc:
            M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Payment is already voided"
    reread(db, pa, i1)
    assert pa.voided_by == u2.id
    assert pa.voided_at == T0
    assert pa.void_note == "Voided by other user"
    assert i1.paid_amount == Decimal("1000.00")
    assert i1.payment_status == "paid"
    assert audit_rows(db) == []
    assert events_of(db, i1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_605)
def test_ipm_vp_20__whitespace_only_note_rejected_by_schema():
    """IPM-VP-20 -- a whitespace-only void_note is rejected by the schema.
    Rules: void_payment R6, Inputs [BUG-605]."""
    with pytest.raises(ValidationError):
        VoidPaymentRequest(void_note="   ")


@pytest.mark.xfail(strict=True, reason=BUG_605)
def test_ipm_vp_21__padded_note_stored_trimmed():
    """IPM-VP-21 -- a padded note is trimmed by the schema; inner spaces kept.
    Rules: void_payment R6, Inputs [BUG-605]."""
    data = VoidPaymentRequest(void_note="  Cheque  bounced  ")
    assert data.void_note == "Cheque  bounced"


def test_ipm_vp_22__single_char_note_accepted():
    """IPM-VP-22 -- a one-character void_note builds unchanged.
    Rules: void_payment Inputs."""
    data = VoidPaymentRequest(void_note="x")
    assert data.void_note == "x"


def test_ipm_vp_23__empty_note_rejected():
    """IPM-VP-23 -- an empty void_note is rejected by the schema.
    Rules: void_payment Inputs."""
    with pytest.raises(ValidationError):
        VoidPaymentRequest(void_note="")


@pytest.mark.xfail(strict=True, reason=BUG_601)
def test_ipm_vp_24__invoice_missing_checked_before_already_voided(db, M, w1, w2, a2, u1, u2):
    """IPM-VP-24 -- the invoice-missing check precedes the already-voided check.
    Rules: void_payment R9a, R3, R2 [BUG-601]."""
    i2 = mk_inv(db, w2, a2, u2.id)
    piv = mk_pay(
        db, i2, "250.00", date(2026, 9, 1), created_by_id=u2.id,
        workspace_id=w1.id, voided=True, voided_by_id=u2.id,
    )
    with pytest.raises(HTTPException) as exc:
        M.void_payment(db, payment_id=piv.id, workspace_id=w1.id, user_id=u1.id, void_note="x")
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found_invoice(i2.id)
    reread(db, piv)
    assert piv.voided_at == T0
    assert piv.voided_by == u2.id
    assert piv.void_note == "Duplicate entry"


def test_ipm_vp_25__remaining_total_just_above_zero_stays_partial(db, M, w1, a1, u1, u2):
    """IPM-VP-25 -- a remaining active total just above zero keeps the invoice partial, not unpaid.
    Rules: void_payment R7 (lower boundary, verify.md Finding 1)."""
    i1 = mk_inv(db, w1, a1, u2.id, paid_amount=Decimal("250.01"), payment_status="partial")
    pa = mk_pa(db, i1, u2.id)
    pb = mk_pay(db, i1, "0.01", date(2026, 9, 2), created_by_id=u2.id)
    res = M.void_payment(db, payment_id=pa.id, workspace_id=w1.id, user_id=u1.id, void_note="Cheque bounced")
    assert res is pa
    reread(db, i1, pb)
    assert i1.paid_amount == Decimal("0.01")
    assert i1.payment_status == "partial"
    assert pb.is_voided is False


# =========================================================================== #
# InvoicePaymentManager._sync_linked_order
# =========================================================================== #

def test_ipm_sy_01__no_order_id_no_op(db, M, w1, a1, u1, u2):
    """IPM-SY-01 -- a null order_id does nothing, regardless of order_type.
    Rules: _sync_linked_order R1."""
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=None)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=False)
    po1 = mk_po(db, w1, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pr1, po1)
    assert pr1.paid is False
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_02__po_return_marked_paid(db, M, w1, a1, u1, u2):
    """IPM-SY-02 -- a PO return linked by invoice_id is synced; the PO itself is untouched.
    Rules: _sync_linked_order R2."""
    po1 = mk_po(db, w1, u2.id, paid=False)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=po1.id)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=False)
    po1.invoice_id = i1.id
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pr1, po1)
    assert pr1.paid is True
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_03__po_return_marked_unpaid(db, M, w1, a1, u1, u2):
    """IPM-SY-03 -- a PO return is synced back to unpaid when the invoice is no longer paid.
    Rules: _sync_linked_order R2."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="partial", order_type="purchase_order", order_id=po1.id)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=True)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pr1, po1)
    assert pr1.paid is False
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_04__po_return_already_correct_no_write(db, M, w1, a1, u1, u2):
    """IPM-SY-04 -- a PO return already at the correct paid value is left alone.
    Rules: _sync_linked_order R2."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=po1.id)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=True)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pr1, po1)
    assert pr1.paid is True
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_05__so_return_marked_paid(db, M, w1, a1, u1, u2):
    """IPM-SY-05 -- an SO return linked by invoice_id is synced; the SO itself is untouched.
    Rules: _sync_linked_order R3."""
    so1 = mk_so(db, w1, u2.id, paid=False)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="sales_order", order_id=so1.id)
    sr1 = mk_sor(db, w1, u2.id, invoice_id=i1.id, paid=False)
    so1.invoice_id = i1.id
    db.add(so1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, sr1, so1)
    assert sr1.paid is True
    assert so1.paid is False
    assert so_events(db) == []
    assert po_events(db) == []


def test_ipm_sy_06__so_return_marked_unpaid(db, M, w1, a1, u1, u2):
    """IPM-SY-06 -- an SO return is synced back to unpaid.
    Rules: _sync_linked_order R3."""
    so1 = mk_so(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="unpaid", order_type="sales_order", order_id=so1.id)
    sr1 = mk_sor(db, w1, u2.id, invoice_id=i1.id, paid=True)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, sr1)
    assert sr1.paid is False
    assert so_events(db) == []
    assert po_events(db) == []


def test_ipm_sy_07__po_synced_when_no_return(db, M, w1, a1, u1, u2):
    """IPM-SY-07 -- with no return, the PO whose invoice_id matches is synced (order_id is not used).
    Rules: _sync_linked_order R4, R5."""
    pox = mk_po(db, w1, u2.id)
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=pox.id)
    po1.invoice_id = i1.id
    po1.paid = False
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1, pox)
    assert po1.paid is True
    assert pox.paid is False
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].purchase_order_id == po1.id
    assert evts[0].event_type == "payment_status_synced"
    assert evts[0].description == "Order marked paid from linked invoice"
    assert evts[0].performed_by == u1.id
    assert evts[0].metadata_json == {"paid": True}
    assert so_events(db) == []


def test_ipm_sy_08__po_synced_to_unpaid_with_event(db, M, w1, a1, u1, u2):
    """IPM-SY-08 -- a PO synced from paid to unpaid writes an unpaid event.
    Rules: _sync_linked_order R5."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="partial", order_type="purchase_order", order_id=po1.id)
    po1.invoice_id = i1.id
    po1.paid = True
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1)
    assert po1.paid is False
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].purchase_order_id == po1.id
    assert evts[0].description == "Order marked unpaid from linked invoice"
    assert evts[0].metadata_json == {"paid": False}
    assert evts[0].performed_by == u1.id
    assert evts[0].event_type == "payment_status_synced"


def test_ipm_sy_09__po_already_paid_no_write(db, M, w1, a1, u1, u2):
    """IPM-SY-09 -- a PO already at the correct paid value gets no event.
    Rules: _sync_linked_order R5."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=po1.id)
    po1.invoice_id = i1.id
    po1.paid = True
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1)
    assert po1.paid is True
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_10__po_no_match_no_op(db, M, w1, a1, u1, u2):
    """IPM-SY-10 -- no PO/SO/return references the invoice: nothing happens.
    Rules: _sync_linked_order R4."""
    pox = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=pox.id)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pox)
    assert pox.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_11__so_synced_when_no_return(db, M, w1, a1, u1, u2):
    """IPM-SY-11 -- with no return, the SO whose invoice_id matches is synced.
    Rules: _sync_linked_order R6."""
    so1 = mk_so(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="sales_order", order_id=so1.id)
    so1.invoice_id = i1.id
    so1.paid = False
    db.add(so1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, so1)
    assert so1.paid is True
    evts = so_events(db)
    assert len(evts) == 1
    assert evts[0].sales_order_id == so1.id
    assert evts[0].event_type == "payment_status_synced"
    assert evts[0].description == "Order marked paid from linked invoice"
    assert evts[0].performed_by == u1.id
    assert evts[0].metadata_json == {"paid": True}
    assert po_events(db) == []


def test_ipm_sy_12__so_synced_to_unpaid_with_event(db, M, w1, a1, u1, u2):
    """IPM-SY-12 -- an SO synced from paid to unpaid writes an unpaid event.
    Rules: _sync_linked_order R6."""
    so1 = mk_so(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="partial", order_type="sales_order", order_id=so1.id)
    so1.invoice_id = i1.id
    so1.paid = True
    db.add(so1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, so1)
    assert so1.paid is False
    evts = so_events(db)
    assert len(evts) == 1
    assert evts[0].description == "Order marked unpaid from linked invoice"
    assert evts[0].metadata_json == {"paid": False}


def test_ipm_sy_13__so_already_unpaid_no_write(db, M, w1, a1, u1, u2):
    """IPM-SY-13 -- an SO already unpaid when the invoice is unpaid gets no event.
    Rules: _sync_linked_order R6."""
    so1 = mk_so(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="unpaid", order_type="sales_order", order_id=so1.id)
    so1.invoice_id = i1.id
    so1.paid = False
    db.add(so1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, so1)
    assert so1.paid is False
    assert so_events(db) == []
    assert po_events(db) == []


def test_ipm_sy_14__expense_order_type_no_op(db, M, w1, a1, u1, u2):
    """IPM-SY-14 -- an unrecognized order_type (expense_order) does nothing.
    Rules: _sync_linked_order R7."""
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="expense_order", order_id=1)
    po1 = mk_po(db, w1, u2.id, invoice_id=i1.id, paid=False)
    so1 = mk_so(db, w1, u2.id, invoice_id=i1.id, paid=False)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=False)
    sr1 = mk_sor(db, w1, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1, so1, pr1, sr1)
    assert po1.paid is False
    assert so1.paid is False
    assert pr1.paid is False
    assert sr1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_15__work_order_type_no_op(db, M, w1, a1, u1, u2):
    """IPM-SY-15 -- order_type work_order also does nothing.
    Rules: _sync_linked_order R7."""
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="work_order", order_id=1)
    po1 = mk_po(db, w1, u2.id, invoice_id=i1.id, paid=False)
    so1 = mk_so(db, w1, u2.id, invoice_id=i1.id, paid=False)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=False)
    sr1 = mk_sor(db, w1, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1, so1, pr1, sr1)
    assert po1.paid is False
    assert so1.paid is False
    assert pr1.paid is False
    assert sr1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_16__null_order_type_with_order_id_no_op(db, M, w1, a1, u1, u2):
    """IPM-SY-16 -- order_type NULL with a non-null order_id does nothing.
    Rules: _sync_linked_order R7."""
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type=None, order_id=1)
    po1 = mk_po(db, w1, u2.id, invoice_id=i1.id, paid=False)
    so1 = mk_so(db, w1, u2.id, invoice_id=i1.id, paid=False)
    pr1 = mk_por(db, w1, u2.id, invoice_id=i1.id, paid=False)
    sr1 = mk_sor(db, w1, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1, so1, pr1, sr1)
    assert po1.paid is False
    assert so1.paid is False
    assert pr1.paid is False
    assert sr1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_17__other_workspace_return_ignored_po_path_taken(db, M, w1, w2, a1, u1, u2):
    """IPM-SY-17 -- a return in another workspace is ignored; the W1 PO path is still taken.
    Rules: _sync_linked_order R8."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=po1.id)
    prx = mk_por(db, w2, u2.id, invoice_id=i1.id, paid=False)
    po1.invoice_id = i1.id
    po1.paid = False
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, prx, po1)
    assert prx.paid is False
    assert po1.paid is True
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].purchase_order_id == po1.id


def test_ipm_sy_18__other_workspace_po_ignored_no_op(db, M, w1, w2, a1, u1, u2):
    """IPM-SY-18 -- a PO in another workspace referencing the invoice id is ignored.
    Rules: _sync_linked_order R8."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="purchase_order", order_id=po1.id)
    pow_ = mk_po(db, w2, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, pow_, po1)
    assert pow_.paid is False
    assert po1.paid is False
    assert po_events(db) == []
    assert so_events(db) == []


def test_ipm_sy_19__other_workspace_so_and_return_ignored(db, M, w1, w2, a1, u1, u2):
    """IPM-SY-19 -- an SO and SO return in another workspace referencing the invoice are ignored.
    Rules: _sync_linked_order R8."""
    so1 = mk_so(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="paid", order_type="sales_order", order_id=so1.id)
    sow = mk_so(db, w2, u2.id, invoice_id=i1.id, paid=False)
    srw = mk_sor(db, w2, u2.id, invoice_id=i1.id, paid=False)
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, sow, srw)
    assert sow.paid is False
    assert srw.paid is False
    assert so_events(db) == []
    assert po_events(db) == []


def test_ipm_sy_20__overdue_is_not_paid(db, M, w1, a1, u1, u2):
    """IPM-SY-20 -- 'paid' means exactly payment_status == 'paid'; overdue syncs to unpaid.
    Rules: _sync_linked_order R5 ("paid" = exactly "paid")."""
    po1 = mk_po(db, w1, u2.id)
    i1 = mk_inv(db, w1, a1, u2.id, payment_status="overdue", order_type="purchase_order", order_id=po1.id)
    po1.invoice_id = i1.id
    po1.paid = True
    db.add(po1)
    db.flush()
    res = M._sync_linked_order(db, reload_inv(db, i1.id), user_id=u1.id)
    assert res is None
    reread(db, po1)
    assert po1.paid is False
    evts = po_events(db)
    assert len(evts) == 1
    assert evts[0].metadata_json == {"paid": False}
