"""Unit tests for app/services/invoice_payment_service.py.

Implements tests/unit/services/invoice_payment_service.cases.md (revision 2),
one test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the test's own "commit point" and the
service's commits are safe and the fixture's outer rollback discards everything.

Patched, as Conventions name them: `app.utils.time.datetime` (every test, NOW),
the commit / rollback spies (they still call the real method), the failing
commit / refresh, and the race simulation of K-28 / K-29
(`svc.invoice_payment_manager.create_payment`). Nothing else is mocked.

Standing rows are attributes of the namespace `s` (`s.W1`, `s.U1`, `s.A1`);
`# Then N` marks the checks of the card's Then line N. Cards whose "Fails today
on" is a TypeError from a parameter that does not exist yet carry
`raises=TypeError`, so the xfail holds only for that cause.
"""

# ruff: noqa: SIM117  (Conventions prescribe the nested `with`)
import hashlib
import inspect
import itertools
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.financial_audit_log import FinancialAuditLog
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_payment import InvoicePayment
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.status import Status
from app.schemas.invoice_payment import (
    InvoicePaymentCreate,
    InvoicePaymentResponse,
    InvoicePaymentUpdate,
)
from app.services.invoice_payment_service import (
    invoice_payment_service,
    to_payment_response,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = invoice_payment_service

NOW = datetime(2026, 9, 27, 12, 0, 0)  # noqa: DTZ001
T0 = datetime(2026, 9, 20, 9, 0, 0)  # noqa: DTZ001
MISSING = 999999999
KEY = "form-7f3a-0001"
DUP = "This idempotency key was already used for a different payment"

BUG_600 = "BUG-600: Invoice payment list ordered by date only, no tie-breaker"
BUG_601 = "BUG-601: `void_payment` does not lock the invoice row"
BUG_603 = "BUG-603: Invoice-payment audit rows never record IP address or user agent"
BUG_606 = "BUG-606: Voided payments can still be edited"
BUG_607 = "BUG-607: Editing a payment leaves no audit trail"
BUG_608 = "BUG-608: Optional payment details cannot be cleared"
BUG_609 = "BUG-609: Payments can be permanently deleted, even though voiding exists"
BUG_611 = "BUG-611: Amount-change error tells the user to delete the payment"
BUG_2400 = "BUG-2400: A payment's \"recorded at\" time is the database's local clock"
BUG_3002 = "BUG-3002: The same payment sent twice is recorded twice"

# A card whose call uses a parameter that does not exist yet fails with TypeError.
XF_3002_TE = pytest.mark.xfail(strict=True, raises=TypeError, reason=BUG_3002)
XF_3002 = pytest.mark.xfail(strict=True, reason=BUG_3002)

# Starts from the process id: committed rows of parallel runs must not repeat a number.
_seq = itertools.count(os.getpid() * 100_000 + 1)


def _n() -> int:
    return next(_seq)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Convention "Time": NOW frozen via app.utils.time.datetime
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


# --------------------------------------------------------------------------- #
# Convention "Standing rows": W0, W1, W2; U1, U2; A0, A1, A2
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db)
    n.U2 = make_profile(db)
    n.A0 = _add(db, Account(workspace_id=n.W0.id, name="Acme"))
    n.A1 = _add(db, Account(workspace_id=n.W1.id, name="Acme"))
    n.A2 = _add(db, Account(workspace_id=n.W2.id, name="Acme"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "INV(Wn)"; `n` is 0, 1 or 2; "but" overrides columns
def inv(db, s, n, **but):
    ws = (s.W0, s.W1, s.W2)[n]
    acc = (s.A0, s.A1, s.A2)[n]
    fields = {
        "workspace_id": ws.id,
        "account_id": acc.id,
        "invoice_type": "payable",
        "invoice_status": "confirmed",
        "invoice_amount": Decimal("1000.00"),
        "paid_amount": Decimal("0.00"),
        "payment_status": "unpaid",
        "allow_payments": True,
        "payment_locked_reason": None,
        "order_type": None,
        "order_id": None,
        "invoice_date": date(2026, 9, 1),
    }
    fields.update(but)
    return _add(db, AccountInvoice(**fields))


_NOKEY = object()


# Convention "TW(I)"; "voided"; "keyed K" (plain attribute assignments before
# db.add); `flush=False` = "db.add-ed, not flushed"; "but" overrides columns
def tw(db, s, i, *, voided=False, keyed=_NOKEY, flush=True, **but):
    fields = {
        "workspace_id": i.workspace_id,
        "invoice_id": i.id,
        "payment_amount": Decimal("400.00"),
        "payment_date": date(2026, 9, 10),
        "payment_method": "cash",
        "payment_reference": "RCPT-77",
        "bank_name": "City Bank",
        "transaction_id": "TXN-9",
        "notes": "Advance",
        "created_by": s.U2.id,
        "is_voided": False,
    }
    if voided:
        fields.update(
            is_voided=True, voided_at=T0, voided_by=s.U2.id, void_note="Duplicate entry"
        )
    fields.update(but)
    row = InvoicePayment(**fields)
    if keyed is not _NOKEY:
        row.idempotency_key = keyed
        row.idempotency_fingerprint = fp_of(row)
    db.add(row)
    if flush:
        db.flush()
    return row


# Convention "EO1": an expense order in W1, completed at T0
def eo1(db, s, invoice_id=None):
    return _add(
        db,
        ExpenseOrder(
            workspace_id=s.W1.id,
            expense_number=f"EXP-{_n()}",
            expense_category="other",
            expense_date=date(2026, 9, 1),
            created_by=s.U2.id,
            completed_at=T0,
            invoice_id=invoice_id,
        ),
    )


# Convention "PO1": a purchase order in W1 with `paid` as the card states
def po1(db, s, paid):
    st = _add(db, Status(workspace_id=s.W1.id, name="Open", comment=""))
    return _add(
        db,
        PurchaseOrder(
            workspace_id=s.W1.id,
            po_number=f"PO-{_n()}",
            destination_type="storage",
            destination_id=1,
            current_status_id=st.id,
            created_by=s.U2.id,
            invoice_id=None,
            paid=paid,
        ),
    )


# Convention "X": a pending row, flushed, not committed
def mk_x(db, s):
    return _add(db, Account(workspace_id=s.W1.id, name="Pending extra"))


# Convention "x_gone" (and G-07 / L-10's "exactly 1"): fresh count of "Pending extra"
def x_count(db):
    return db.execute(
        select(func.count()).select_from(Account).where(Account.name == "Pending extra")
    ).scalar_one()


# --------------------------------------------------------------------------- #
# Conventions -> call values, fingerprint, column query
# --------------------------------------------------------------------------- #


# Convention "BODY"; "BODY, but f v" overrides one field
def body(invoice_id, **but):
    fields = {
        "invoice_id": invoice_id,
        "payment_amount": Decimal("400.00"),
        "payment_date": date(2026, 9, 10),
        "payment_method": "cash",
        "payment_reference": "RCPT-77",
        "bank_name": "City Bank",
        "transaction_id": "TXN-9",
        "notes": "Advance",
    }
    fields.update(but)
    return InvoicePaymentCreate(**fields)


def _nz(v):
    return None if v is None or v.strip() == "" else v.strip()


# Convention "fp(uid, d)"
def fp(uid, d):
    obj = {
        "profile_id": uid,
        "invoice_id": d.invoice_id,
        "payment_amount": format(Decimal(d.payment_amount).normalize(), "f"),
        "payment_date": d.payment_date.isoformat(),
        "payment_method": _nz(d.payment_method),
        "payment_reference": _nz(d.payment_reference),
        "bank_name": _nz(d.bank_name),
        "transaction_id": _nz(d.transaction_id),
        "notes": _nz(d.notes),
    }
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# Convention "FP(P)" = fp(P.created_by, P)
def fp_of(p):
    return fp(p.created_by, p)


# Convention "col(P, c)": a column query (raises today: the column does not exist)
def col(db, p, c):
    return db.execute(
        select(getattr(InvoicePayment, c)).where(InvoicePayment.id == p.id)
    ).scalar_one()


# Convention "upd(pid, data)"
def upd(db, s, pid, data):
    if "user_id" in inspect.signature(svc.update_payment).parameters:
        return svc.update_payment(
            db, payment_id=pid, payment_in=data, workspace_id=s.W1.id, user_id=s.U1.id
        )
    return svc.update_payment(db, payment_id=pid, payment_in=data, workspace_id=s.W1.id)


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


# Convention "re-read X": expire, then select by id
def reread(db, model, row_id):
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(I)": paid_amount, payment_status, invoice_status, allow_payments
def snap_inv(db, inv_id):
    db.expire_all()
    return tuple(
        db.execute(
            select(
                AccountInvoice.paid_amount,
                AccountInvoice.payment_status,
                AccountInvoice.invoice_status,
                AccountInvoice.allow_payments,
            ).where(AccountInvoice.id == inv_id)
        ).one()
    )


# Convention "unchanged(P)": every column of the payment
def snap_pay(db, pay_id):
    db.expire_all()
    row = (
        db.execute(
            select(InvoicePayment.__table__).where(
                InvoicePayment.__table__.c.id == pay_id
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


# Convention "nothing written": counts of four tables, all workspaces
def counts(db):
    return tuple(
        db.execute(select(func.count()).select_from(m)).scalar_one()
        for m in (InvoicePayment, FinancialAuditLog, InvoiceEvent, PurchaseOrderEvent)
    )


def pay_count(db, inv_id):
    return db.execute(
        select(func.count())
        .select_from(InvoicePayment)
        .where(InvoicePayment.invoice_id == inv_id)
    ).scalar_one()


# Convention "audit(P)"
def audit(db, pay_id):
    return (
        db.execute(
            select(FinancialAuditLog).where(
                FinancialAuditLog.entity_type == "payment",
                FinancialAuditLog.entity_id == pay_id,
            )
        )
        .scalars()
        .all()
    )


# Convention "events(I)"
def events(db, inv_id):
    return (
        db.execute(select(InvoiceEvent).where(InvoiceEvent.invoice_id == inv_id))
        .scalars()
        .all()
    )


def po_events(db, po_id):
    return (
        db.execute(
            select(PurchaseOrderEvent).where(
                PurchaseOrderEvent.purchase_order_id == po_id
            )
        )
        .scalars()
        .all()
    )


# Convention "usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies"
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "Statement recorder": every statement of the When, in order
@contextmanager
def recorder(db):
    stmts = []
    conn = db.connection()

    def _on(_conn, _cursor, statement, _params, _context, _many):
        stmts.append(statement)

    event.listen(conn, "before_cursor_execute", _on)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", _on)


def lock_stmts(stmts):
    return [st for st in stmts if "FROM account_invoices" in st and "FOR UPDATE" in st]


# Convention "Race simulations" (K-28, K-29)
def race_dup(db, s, i1):
    def dup(*a, **k):
        tw(db, s, i1, keyed=KEY, created_by=s.U1.id)

    return dup


# =========================================================================== #
# to_payment_response
# =========================================================================== #


# [claude] IPS-M-01
def test_ips_m_01__every_column_copied_and_name_is_argument(db, s):
    """IPS-M-01 — every column is copied and the name is the argument.
    Rules: M1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = to_payment_response(p, created_by_name="Nadia Islam")
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    # Then 2
    assert result.id == p.id
    assert result.workspace_id == s.W1.id
    assert result.invoice_id == i1.id
    assert result.payment_amount == Decimal("400.00")
    assert result.payment_date == date(2026, 9, 10)
    # Then 3
    assert result.payment_method == "cash"
    assert result.payment_reference == "RCPT-77"
    assert result.bank_name == "City Bank"
    assert result.transaction_id == "TXN-9"
    assert result.notes == "Advance"
    # Then 4
    assert result.is_voided is False
    assert result.voided_at is None
    assert result.voided_by is None
    assert result.void_note is None
    # Then 5
    assert result.created_by == s.U2.id
    assert result.created_at == p.created_at
    assert result.created_at is not None
    # Then 6
    assert result.created_by_name == "Nadia Islam"


# [claude] IPS-M-02
def test_ips_m_02__no_name_gives_none(db, s):
    """IPS-M-02 — without a name the response has `created_by_name None`.
    Rules: M1."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1)
    db.commit()
    result = to_payment_response(p)
    # Then 1
    assert result.id == p.id
    # Then 2
    assert result.created_by_name is None


# [claude] IPS-M-03
def test_ips_m_03__voided_row_carries_void_fields(db, s):
    """IPS-M-03 — a voided row carries its void fields.
    Rules: M1."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1, voided=True)
    db.commit()
    result = to_payment_response(p, created_by_name="Nadia Islam")
    # Then 1
    assert result.is_voided is True
    assert result.voided_at == T0
    assert result.voided_by == s.U2.id
    assert result.void_note == "Duplicate entry"
    # Then 2
    assert result.payment_amount == Decimal("400.00")


# [claude] IPS-M-04
def test_ips_m_04__zero_amount_refused_by_schema(db, s):
    """IPS-M-04 — a stored amount of 0.00 is refused by the response schema.
    Rules: M2."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1)
    db.commit()
    p.payment_amount = Decimal("0.00")  # in memory only, after the commit point
    # Then 1
    with pytest.raises(ValidationError):
        to_payment_response(p, created_by_name="x")


# =========================================================================== #
# _payment_response
# =========================================================================== #


# [claude] IPS-PR-01
def test_ips_pr_01__passed_in_object_with_recorder_name(db, s):
    """IPS-PR-01 — the response is the passed-in object with the recorder's name.
    Rules: _payment_response R1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    p.notes = "In memory"
    result = svc._payment_response(db, payment=p, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p.id
    # Then 2
    assert result.notes == "In memory"
    # Then 3
    assert result.created_by_name == s.U2.name


# [claude] IPS-PR-02
def test_ips_pr_02__no_lock_and_session_clean(db, s):
    """IPS-PR-02 — the helper takes no lock and leaves the session clean.
    Rules: _payment_response R3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    with recorder(db) as stmts:
        result = svc._payment_response(db, payment=p, workspace_id=s.W1.id)
    # Then 1
    assert result.created_by_name == s.U2.name
    # Then 2
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 3
    assert not any("FOR UPDATE" in st for st in stmts)
    # Then 4
    assert not any(
        st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for st in stmts
    )


# =========================================================================== #
# create_payment
# =========================================================================== #


# [claude] IPS-C-01
def test_ips_c_01__payment_committed_response_after_commit(db, s):
    """IPS-C-01 — a payment is committed and the response is built after the commit.
    Rules: create_payment R1, R2, Returns; TC1, TC2."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    # Then 2
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.created_by == s.U1.id
    assert result.created_by_name == s.U1.name
    assert result.is_voided is False
    # Then 4
    assert result.invoice_id == i1.id
    assert result.payment_amount == Decimal("400.00")
    assert result.payment_reference == "RCPT-77"
    db.rollback()
    # Then 5
    row = reread(db, InvoicePayment, result.id)
    assert row is not None
    assert row.workspace_id == s.W1.id
    assert row.payment_amount == Decimal("400.00")
    assert row.notes == "Advance"
    # Then 6
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-C-02
def test_ips_c_02__audit_and_event_committed(db, s):
    """IPS-C-02 — the audit row and the invoice event are committed with the payment.
    Rules: create_payment R1; TC1; R6 (default None)."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    rows = audit(db, result.id)
    assert len(rows) == 1
    assert rows[0].action_type == "created"
    assert rows[0].performed_by == s.U1.id
    assert rows[0].workspace_id == s.W1.id
    # Then 3
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None
    # Then 4
    evs = events(db, i1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "payment_recorded"
    assert evs[0].performed_by == s.U1.id


# [claude] IPS-C-03
def test_ips_c_03__payment_on_invoice_of_completed_order(db, s):
    """IPS-C-03 — a payment is recorded on the invoice of a completed order.
    Rules: create_payment R7 (owner O1 / F7); TC1."""
    eo = eo1(db, s)
    i1 = inv(db, s, 1, order_type="expense_order", order_id=eo.id)
    eo.invoice_id = i1.id
    db.flush()
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.id is not None
    assert result.payment_amount == Decimal("400.00")
    db.rollback()
    # Then 2
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"
    # Then 3
    eor = reread(db, ExpenseOrder, eo.id)
    assert eor.completed_at == T0
    assert eor.invoice_id == i1.id


# [claude] IPS-C-04
def test_ips_c_04__unknown_invoice_404_pending_discarded(db, s):
    """IPS-C-04 — an unknown invoice: the manager's 404 passes, everything pending is discarded.
    Rules: create_payment R3, Errors row 1; TC3."""
    i1 = inv(db, s, 1)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(MISSING), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Invoice with ID 999999999 not found"
    # Then 4
    assert usable(db)
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_inv(db, i1.id) == i1_before
    # Then 7
    assert x_count(db) == 0


# [claude] IPS-C-05
def test_ips_c_05__invoice_of_w2_not_found(db, s):
    """IPS-C-05 — an invoice of W2 (built after W1) is not found.
    Rules: create_payment R3 (HR-16)."""
    inv(db, s, 1)
    i2 = inv(db, s, 2)
    db.commit()
    before = counts(db)
    i2_before = snap_inv(db, i2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i2.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i2.id} not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i2.id) == i2_before


# [claude] IPS-C-06
def test_ips_c_06__invoice_of_w0_not_found(db, s):
    """IPS-C-06 — an invoice of W0 (built before W1) is not found.
    Rules: create_payment R3 (HR-16)."""
    i0 = inv(db, s, 0)
    inv(db, s, 1)
    db.commit()
    before = counts(db)
    i0_before = snap_inv(db, i0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i0.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i0.id} not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i0.id) == i0_before


# [claude] IPS-C-07
def test_ips_c_07__draft_invoice_400_passes(db, s):
    """IPS-C-07 — a draft invoice: the manager's 400 passes unchanged.
    Rules: create_payment R3; TC3."""
    i1 = inv(db, s, 1, invoice_status="draft")
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Payments can only be recorded against confirmed invoices (current status: 'draft')."
    )
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert x_count(db) == 0


# [claude] IPS-C-08
def test_ips_c_08__locked_invoice_403_passes(db, s):
    """IPS-C-08 — a locked invoice: the manager's 403 passes unchanged.
    Rules: create_payment R3; TC3."""
    i1 = inv(
        db, s, 1, allow_payments=False, payment_locked_reason="Awaiting credit approval"
    )
    db.commit()
    before = counts(db)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Awaiting credit approval"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert x_count(db) == 0


# [claude] IPS-C-09
def test_ips_c_09__above_owed_400_nothing_saved(db, s):
    """IPS-C-09 — above what is owed: the manager's 400, nothing saved.
    Rules: create_payment R3; TC3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("700.00"), payment_status="partial")
    tw(db, s, i1, payment_amount=Decimal("700.00"))
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Payment amount (400.00) exceeds outstanding amount (300.00)"
    )
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert x_count(db) == 0
    # Then 7
    assert usable(db)


# [claude] IPS-C-10
def test_ips_c_10__failing_commit_rolled_back(db, s):
    """IPS-C-10 — a failing commit is rolled back and re-raised; nothing saved.
    Rules: create_payment R4, Errors row 2; TC4."""
    i1 = inv(db, s, 1)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(db, "commit", side_effect=RuntimeError("boom")),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            svc.create_payment(
                db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-C-11
def test_ips_c_11__failing_refresh_payment_stays_saved(db, s):
    """IPS-C-11 — a failing re-read after the commit leaves the payment saved.
    Rules: create_payment R4, Errors row 3; TC5."""
    i1 = inv(db, s, 1)
    db.commit()
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_payment(
                db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = (
        db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == i1.id))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].payment_amount == Decimal("400.00")
    assert rows[0].created_by == s.U1.id
    # Then 3
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-C-12
def test_ips_c_12__invoice_locked_plain_for_update(db, s):
    """IPS-C-12 — the invoice is locked with a plain `FOR UPDATE`.
    Rules: create_payment R5 (manager R2)."""
    i1 = inv(db, s, 1)
    db.commit()
    with recorder(db) as stmts:
        result = svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    locks = lock_stmts(stmts)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(locks) >= 1
    # Then 3
    assert not any("SKIP LOCKED" in st for st in locks)
    # Then 4
    assert not any("NOWAIT" in st for st in locks)


# [claude] IPS-C-13
def test_ips_c_13__one_commit_no_rollback(db, s):
    """IPS-C-13 — exactly one commit and no rollback on success.
    Rules: create_payment R1, R8, Side effects."""
    i1 = inv(db, s, 1)
    db.commit()
    with spies(db) as (cm, rb):
        result = svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0


# [claude] IPS-C-14
@pytest.mark.xfail(strict=True, raises=TypeError, reason=BUG_603)
def test_ips_c_14__ip_and_browser_reach_audit_row(db, s):
    """IPS-C-14 — pass-through BUG-603: IP and browser reach the audit row.
    Rules: create_payment R6 [BUG-603]."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 (Test)",
    )
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    rows = audit(db, result.id)
    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 (Test)"


# [claude] IPS-C-15
@pytest.mark.xfail(strict=True, reason=BUG_2400)
def test_ips_c_15__created_at_is_app_utc_clock(db, s):
    """IPS-C-15 — pass-through BUG-2400: `created_at` is the app's UTC clock.
    Rules: create_payment R2 [BUG-2400] (DAO)."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.created_at is not None
    # Then 2
    assert result.created_at == NOW


# [claude] IPS-C-16
def test_ips_c_16__linked_po_paid_committed(db, s):
    """IPS-C-16 — the linked purchase order's `paid` change is committed too.
    Rules: create_payment R1; TC1."""
    po = po1(db, s, paid=False)
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("400.00"),
        order_type="purchase_order",
        order_id=po.id,
    )
    po.invoice_id = i1.id
    db.flush()
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.payment_amount == Decimal("400.00")
    db.rollback()
    # Then 2
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "paid"
    # Then 3
    assert reread(db, PurchaseOrder, po.id).paid is True
    # Then 4
    assert len(po_events(db, po.id)) == 1


# [claude] IPS-C-17
def test_ips_c_17__database_error_passes_nothing_saved(db, s):
    """IPS-C-17 — a database error at the write passes unchanged and nothing is saved.
    Rules: create_payment R3; TC3."""
    i1 = inv(db, s, 1)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=MISSING
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_inv(db, i1.id) == i1_before
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert usable(db)


# =========================================================================== #
# create_payment — idempotency (R9–R9i, BUG-3002)
# =========================================================================== #


# [claude] IPS-K-01
@XF_3002_TE
def test_ips_k_01__key_stored_and_committed(db, s):
    """IPS-K-01 — a key is stored on the new payment and committed.
    Rules: create_payment R9a [BUG-3002]."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key=KEY,
    )
    # Then 1
    assert result.id is not None
    assert result.created_by == s.U1.id
    db.rollback()
    # Then 2
    assert col(db, result, "idempotency_key") == "form-7f3a-0001"
    # Then 3
    assert col(db, result, "idempotency_fingerprint") == fp(s.U1.id, body(i1.id))
    # Then 4
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-K-02
@XF_3002_TE
def test_ips_k_02__two_keys_two_payments(db, s):
    """IPS-K-02 — two different keys on one invoice make two payments.
    Rules: create_payment R9a [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, keyed="form-a")
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key="form-b",
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert col(db, result, "idempotency_key") == "form-b"
    # Then 4
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("800.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-K-03
@XF_3002_TE
def test_ips_k_03__new_key_still_obeys_owed_limit(db, s):
    """IPS-K-03 — a new key still obeys "never above what is owed".
    Rules: create_payment R9a [BUG-3002], R3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("800.00"), payment_status="partial")
    tw(db, s, i1, payment_amount=Decimal("800.00"), created_by=s.U1.id, keyed="form-a")
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key="form-b",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Payment amount (400.00) exceeds outstanding amount (200.00)"
    )
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-04
@XF_3002_TE
def test_ips_k_04__same_key_same_request_replays(db, s):
    """IPS-K-04 — same key, same request, same member: the first payment comes back, nothing committed.
    Rules: create_payment R9b, R9h [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    p1_before = snap_pay(db, p1.id)
    mk_x(db, s)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p1.id
    # Then 2
    assert result.payment_amount == Decimal("400.00")
    assert result.payment_reference == "RCPT-77"
    assert result.created_at == p1.created_at
    # Then 3
    assert result.created_by == s.U1.id
    assert result.created_by_name == s.U1.name
    assert result.is_voided is False
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert x_count(db) == 0
    # Then 6
    assert pay_count(db, i1.id) == 1
    # Then 7
    assert counts(db) == before
    # Then 8
    assert snap_inv(db, i1.id) == i1_before
    # Then 9
    assert snap_pay(db, p1.id) == p1_before


# [claude] IPS-K-05
@XF_3002_TE
def test_ips_k_05__another_member_same_key_409(db, s):
    """IPS-K-05 — another member sends the same key and body → 409, nothing written.
    Rules: create_payment R9c, Errors row 4 [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    p1_before = snap_pay(db, p1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == DUP
    # Then 4
    assert pay_count(db, i1.id) == 1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_inv(db, i1.id) == i1_before
    # Then 7
    assert snap_pay(db, p1.id) == p1_before
    # Then 8
    assert x_count(db) == 0


# [claude] IPS-K-06
@XF_3002_TE
def test_ips_k_06__replay_after_fully_paid_order_untouched(db, s):
    """IPS-K-06 — the replay works after the invoice became fully paid; the linked order is not touched.
    Rules: create_payment R9b, R9g, R9h [BUG-3002]."""
    po = po1(db, s, paid=True)
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("400.00"),
        paid_amount=Decimal("400.00"),
        payment_status="paid",
        order_type="purchase_order",
        order_id=po.id,
    )
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    po.invoice_id = i1.id
    db.flush()
    db.commit()
    before = counts(db)
    mk_x(db, s)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert x_count(db) == 0
    # Then 4
    assert pay_count(db, i1.id) == 1
    # Then 5
    assert counts(db) == before
    # Then 6
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "paid"
    # Then 7
    assert reread(db, PurchaseOrder, po.id).paid is True


# [claude] IPS-K-07
@XF_3002_TE
def test_ips_k_07__replay_after_payments_locked(db, s):
    """IPS-K-07 — the replay works after payments were locked on the invoice.
    Rules: create_payment R9b, R9g, R9h [BUG-3002]."""
    i1 = inv(
        db,
        s,
        1,
        paid_amount=Decimal("400.00"),
        payment_status="partial",
        allow_payments=False,
        payment_locked_reason="Awaiting credit approval",
    )
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert x_count(db) == 0
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-08
@XF_3002_TE
def test_ips_k_08__replay_of_voided_payment(db, s):
    """IPS-K-08 — the replay of a payment voided since shows it voided and records nothing.
    Rules: create_payment R9b, R9g, R9h [BUG-3002]."""
    i1 = inv(db, s, 1)
    p1 = tw(db, s, i1, created_by=s.U1.id, voided=True, keyed=KEY)
    db.commit()
    before = counts(db)
    mk_x(db, s)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    # Then 2
    assert result.is_voided is True
    assert result.void_note == "Duplicate entry"
    assert result.voided_by == s.U2.id
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert pay_count(db, i1.id) == 1
    # Then 6
    assert counts(db) == before
    # Then 7
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("0.00")
    assert i1r.payment_status == "unpaid"


def _k_409_setup(db, s):
    """K-11 … K-16 Given: I1 paid 400.00 partial; P1 = TW(I1), but created_by U1, keyed KEY."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    return i1


# [claude] IPS-K-09
@XF_3002_TE
def test_ips_k_09__different_amount_409(db, s):
    """IPS-K-09 — same key, different `payment_amount` → 409, all pending work discarded.
    Rules: create_payment R9c, Errors row 4 [BUG-3002]; TC3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1.id, payment_amount=Decimal("400.01")),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == DUP
    # Then 4
    assert pay_count(db, i1.id) == 1
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_inv(db, i1.id) == i1_before
    # Then 7
    assert x_count(db) == 0
    # Then 8
    assert usable(db)


# [claude] IPS-K-10
@XF_3002_TE
def test_ips_k_10__different_invoice_409(db, s):
    """IPS-K-10 — same key, different `invoice_id` → 409, neither invoice changes.
    Rules: create_payment R9c [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    i1b = inv(db, s, 1)
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    i1b_before = snap_inv(db, i1b.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1b.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == DUP
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert snap_inv(db, i1b.id) == i1b_before


@XF_3002_TE
@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("payment_date", date(2026, 9, 11), id="IPS-K-11"),
        pytest.param("payment_method", "Cash", id="IPS-K-12"),
        pytest.param("payment_reference", "RCPT-78", id="IPS-K-13"),
        pytest.param("bank_name", "City Bank Ltd", id="IPS-K-14"),
        pytest.param("transaction_id", "TXN-10", id="IPS-K-15"),
        pytest.param("notes", None, id="IPS-K-16"),
    ],
)
def test_ips_k_11_to_16__one_field_differs_409(db, s, field, value):
    """IPS-K-11 … K-16 — same key, one body field different (date, method "Cash", reference,
    bank, transaction id, notes left out) → 409.
    Rules: create_payment R9c [BUG-3002]."""
    i1 = _k_409_setup(db, s)
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1.id, **{field: value}),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == DUP
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-17
@XF_3002_TE
def test_ips_k_17__key_case_sensitive(db, s):
    """IPS-K-17 — the key is case-sensitive: capitals are a new key.
    Rules: create_payment Inputs `idempotency_key`, R9a [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key="FORM-7F3A-0001",
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert col(db, result, "idempotency_key") == "FORM-7F3A-0001"
    # Then 4
    assert reread(db, AccountInvoice, i1.id).paid_amount == Decimal("800.00")


@XF_3002_TE
@pytest.mark.parametrize(
    "key",
    [
        pytest.param(" form-7f3a-0001", id="IPS-K-18"),
        pytest.param("7f3a", id="IPS-K-19"),
        pytest.param("form_7f3a-0001", id="IPS-K-20"),
    ],
)
def test_ips_k_18_to_20__key_compared_exactly(db, s, key):
    """IPS-K-18 … K-20 — the key is compared exactly: a leading space, a part, `_` for `-`
    are each a new key and make a second payment.
    Rules: create_payment Inputs `idempotency_key`, R9a [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key=key,
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert col(db, result, "idempotency_key") == key


# [claude] IPS-K-21
@XF_3002_TE
def test_ips_k_21__same_key_in_w0_is_another_key(db, s):
    """IPS-K-21 — the same key in W0 (built before W1) is another key: a normal new payment.
    Rules: create_payment R9d [BUG-3002] (HR-16)."""
    i0 = inv(db, s, 0, paid_amount=Decimal("400.00"), payment_status="partial")
    p0 = tw(db, s, i0, keyed=KEY)
    i1 = inv(db, s, 1)
    db.commit()
    p0_before = snap_pay(db, p0.id)
    i0_before = snap_inv(db, i0.id)
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key=KEY,
    )
    # Then 1
    assert result.id != p0.id
    assert result.workspace_id == s.W1.id
    assert result.invoice_id == i1.id
    # Then 2
    assert result.created_by == s.U1.id
    db.rollback()
    # Then 3
    assert pay_count(db, i1.id) == 1
    # Then 4
    assert col(db, result, "idempotency_key") == "form-7f3a-0001"
    # Then 5
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"
    # Then 6
    assert snap_pay(db, p0.id) == p0_before
    # Then 7
    assert snap_inv(db, i0.id) == i0_before


# [claude] IPS-K-22
@XF_3002_TE
def test_ips_k_22__same_key_in_w2_is_another_key(db, s):
    """IPS-K-22 — the same key in W2 (built after W1) is another key: a normal new payment.
    Rules: create_payment R9d [BUG-3002] (HR-16)."""
    i1 = inv(db, s, 1)
    i2 = inv(db, s, 2, paid_amount=Decimal("250.00"), payment_status="partial")
    p2 = tw(db, s, i2, payment_amount=Decimal("250.00"), keyed=KEY)
    db.commit()
    p2_before = snap_pay(db, p2.id)
    i2_before = snap_inv(db, i2.id)
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key=KEY,
    )
    # Then 1
    assert result.id != p2.id
    assert result.workspace_id == s.W1.id
    assert result.payment_amount == Decimal("400.00")
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 1
    # Then 3
    assert col(db, result, "idempotency_key") == "form-7f3a-0001"
    # Then 4
    assert reread(db, AccountInvoice, i1.id).paid_amount == Decimal("400.00")
    # Then 5
    assert snap_pay(db, p2.id) == p2_before
    # Then 6
    assert snap_inv(db, i2.id) == i2_before


# [claude] IPS-K-23
def test_ips_k_23__no_key_same_body_twice_two_payments(db, s):
    """IPS-K-23 — no key: the same body twice makes two payments (today's behaviour, kept).
    Rules: create_payment R9."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1)
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("800.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-K-24
def test_ips_k_24__no_key_second_that_no_longer_fits_400(db, s):
    """IPS-K-24 — no key: a second identical payment that no longer fits gets the manager's 400.
    Rules: create_payment R9, R3."""
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("600.00"),
        paid_amount=Decimal("400.00"),
        payment_status="partial",
    )
    tw(db, s, i1)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Payment amount (400.00) exceeds outstanding amount (200.00)"
    )
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-25
def test_ips_k_25__no_key_never_blocked_by_keyed(db, s):
    """IPS-K-25 — no key is never blocked by a keyed payment with the same body.
    Rules: create_payment R9, R9d."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    result = svc.create_payment(
        db, payment_in=body(i1.id), workspace_id=s.W1.id, user_id=s.U1.id
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert reread(db, AccountInvoice, i1.id).paid_amount == Decimal("800.00")


# [claude] IPS-K-26
@XF_3002_TE
def test_ips_k_26__explicit_none_key_is_no_key(db, s):
    """IPS-K-26 — an explicit `idempotency_key=None` is "no key": NULL key and fingerprint.
    Rules: create_payment R9, R9f, Inputs [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key=None,
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert col(db, result, "idempotency_key") is None
    # Then 4
    assert col(db, result, "idempotency_fingerprint") is None


def _is_key_lookup(st):
    """A select from invoice_payments whose WHERE clause filters on idempotency_key."""
    if "FROM invoice_payments" not in st or "WHERE" not in st:
        return False
    return "idempotency_key" in st.split("WHERE", 1)[1]


# [claude] IPS-K-27
@XF_3002_TE
def test_ips_k_27__key_looked_up_after_plain_lock(db, s):
    """IPS-K-27 — the key is looked up after the invoice lock, with a plain `FOR UPDATE`.
    Rules: create_payment R9g, R9e, R5 [BUG-3002]."""
    i1 = inv(db, s, 1)
    db.commit()
    with recorder(db) as stmts:
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    locks = lock_stmts(stmts)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(locks) >= 1
    # Then 3
    assert not any("SKIP LOCKED" in st for st in locks)
    # Then 4
    assert not any("NOWAIT" in st for st in locks)
    # Then 5
    assert not any("FOR UPDATE OF" in st for st in locks)
    # Then 6
    first_lock = stmts.index(locks[0])
    lookups = [i for i, st in enumerate(stmts) if _is_key_lookup(st) and i > first_lock]
    assert lookups
    # Then 7
    assert "FOR UPDATE" not in stmts[lookups[0]]


# [claude] IPS-K-28
@XF_3002_TE
def test_ips_k_28__lost_race_same_body_replays(db, s):
    """IPS-K-28 — lost race on the index, same body: answered with the first payment, never 500.
    Rules: create_payment R9e, R9b, R9h [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    i1_before = snap_inv(db, i1.id)
    with spies(db) as (cm, _rb):
        with patch.object(
            svc.invoice_payment_manager,
            "create_payment",
            side_effect=race_dup(db, s, i1),
        ):
            result = svc.create_payment(
                db,
                payment_in=body(i1.id),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
                idempotency_key=KEY,
            )
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert pay_count(db, i1.id) == 1
    # Then 4
    assert snap_inv(db, i1.id) == i1_before
    # Then 5
    assert usable(db)


# [claude] IPS-K-29
@XF_3002_TE
def test_ips_k_29__lost_race_different_body_409(db, s):
    """IPS-K-29 — lost race on the index, different body: 409, never 500.
    Rules: create_payment R9e, R9c [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(
            svc.invoice_payment_manager,
            "create_payment",
            side_effect=race_dup(db, s, i1),
        ):
            svc.create_payment(
                db,
                payment_in=body(i1.id, payment_amount=Decimal("400.01")),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
                idempotency_key=KEY,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == DUP
    # Then 4
    assert pay_count(db, i1.id) == 1
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert x_count(db) == 0
    # Then 7
    assert usable(db)


# [claude] IPS-K-30
@XF_3002
def test_ips_k_30__database_refuses_second_row_same_key(db, s):
    """IPS-K-30 — the database refuses a second row with the same key in one workspace.
    Rules: create_payment R9d, R9e [BUG-3002] (target database)."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()  # commit point before the not-flushed row, so the flush is the When
    tw(db, s, i1, payment_amount=Decimal("100.00"), keyed=KEY, flush=False)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"


# [claude] IPS-K-31
def test_ips_k_31__two_payments_without_key_never_collide(db, s):
    """IPS-K-31 — two payments without a key never collide.
    Rules: create_payment R9d (target database)."""
    i1 = inv(db, s, 1)
    tw(db, s, i1)
    db.commit()  # commit point before the not-flushed row, so the flush is the When
    p2 = tw(db, s, i1, payment_amount=Decimal("100.00"), flush=False)
    db.flush()
    # Then 1
    assert p2.id is not None
    # Then 2
    assert pay_count(db, i1.id) == 2


# [claude] IPS-K-32
def test_ips_k_32__same_key_in_w1_and_w2_no_collision(db, s):
    """IPS-K-32 — the same key in W1 and W2 does not collide.
    Rules: create_payment R9d (target database)."""
    i1 = inv(db, s, 1)
    i2 = inv(db, s, 2)
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()  # commit point before the not-flushed row, so the flush is the When
    p2 = tw(db, s, i2, keyed=KEY, flush=False)
    db.flush()
    # Then 1
    assert p2.id is not None
    # Then 2
    n_w2 = db.execute(
        select(func.count())
        .select_from(InvoicePayment)
        .where(InvoicePayment.workspace_id == s.W2.id)
    ).scalar_one()
    assert n_w2 == 1


# [claude] IPS-K-33
@XF_3002
def test_ips_k_33__index_is_exact_partial_unique_index(db, s):
    """IPS-K-33 — the index is exactly the partial unique index of R9g.
    Rules: create_payment R9d, R9g [BUG-3002] (target database)."""
    db.commit()
    defs = (
        db.execute(
            text(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_invoice_payments_workspace_idempotency_key'"
            )
        )
        .scalars()
        .all()
    )
    # Then 1
    assert len(defs) == 1
    # Then 2
    assert defs[0] == (
        "CREATE UNIQUE INDEX ix_invoice_payments_workspace_idempotency_key ON public.invoice_payments "
        "USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)"
    )


# [claude] IPS-K-34
@XF_3002_TE
def test_ips_k_34__400_equals_400_00_replay(db, s):
    """IPS-K-34 — `400` and `400.00` are the same request: replay.
    Rules: create_payment R9f, R9b, R9h [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id, payment_amount=Decimal(400)),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    assert result.payment_amount == Decimal("400.00")
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert pay_count(db, i1.id) == 1
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-35
@XF_3002_TE
def test_ips_k_35__omitted_notes_equals_spaces_replay(db, s):
    """IPS-K-35 — omitted notes and notes of spaces only are the same request: replay.
    Rules: create_payment R9f, R9b, R9h [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, notes=None, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id, notes="  "),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    assert result.notes is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert pay_count(db, i1.id) == 1
    # Then 4
    assert counts(db) == before


# [claude] IPS-K-36
@XF_3002_TE
def test_ips_k_36__stored_fingerprint_is_literal_sha256(db, s):
    """IPS-K-36 — the stored fingerprint is the SHA-256 of the canonical request.
    Rules: create_payment R9f, R9a [BUG-3002]."""
    make_profile(db, id=910001)
    inv(db, s, 1, id=920001)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(920001),
        workspace_id=s.W1.id,
        user_id=910001,
        idempotency_key=KEY,
    )
    # Then 1
    assert result.invoice_id == 920001
    assert result.created_by == 910001
    db.rollback()
    # Then 2
    assert (
        col(db, result, "idempotency_fingerprint")
        == "1c1ff19a34151a4391d80de9b66a31ed5aa0442ea613439a825707398de6c7e1"
    )
    # Then 3
    assert col(db, result, "idempotency_key") == "form-7f3a-0001"


# [claude] IPS-K-37
@XF_3002
def test_ips_k_37__notes_edit_keeps_fingerprint(db, s):
    """IPS-K-37 — a later notes edit does not change the stored fingerprint.
    Rules: create_payment R9f [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    result = upd(db, s, p1.id, InvoicePaymentUpdate(notes="Edited later"))
    # Then 1
    assert result.notes == "Edited later"
    db.rollback()
    # Then 2
    assert col(db, p1, "idempotency_fingerprint") == fp(s.U1.id, body(i1.id))
    # Then 3
    assert col(db, p1, "idempotency_key") == "form-7f3a-0001"


# [claude] IPS-K-38
@XF_3002_TE
def test_ips_k_38__empty_key_is_ordinary_and_stored(db, s):
    """IPS-K-38 — called directly, `""` is an ordinary key and is stored.
    Rules: create_payment R9i, R9a [BUG-3002]."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key="",
    )
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    assert col(db, result, "idempotency_key") == ""
    # Then 3
    assert col(db, result, "idempotency_fingerprint") == fp(s.U1.id, body(i1.id))


# [claude] IPS-K-39
@XF_3002_TE
def test_ips_k_39__empty_key_is_replayed(db, s):
    """IPS-K-39 — called directly, `""` is replayed like any other key.
    Rules: create_payment R9i, R9b, R9h [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed="")
    db.commit()
    before = counts(db)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key="",
        )
    # Then 1
    assert result.id == p1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert pay_count(db, i1.id) == 1
    # Then 4
    assert counts(db) == before


# [claude] IPS-K-40
@XF_3002_TE
def test_ips_k_40__101_char_key_data_error(db, s):
    """IPS-K-40 — a 101-character key fails on the column: `DataError`, nothing saved.
    Rules: create_payment R9i, Errors row 5 [BUG-3002]; TC3."""
    i1 = inv(db, s, 1)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(DataError):
        svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key="k" * 101,
        )
    # Then 2
    assert counts(db) == before
    # Then 3
    assert snap_inv(db, i1.id) == i1_before
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert usable(db)


# [claude] IPS-K-41
@XF_3002_TE
def test_ips_k_41__100_char_key_stored_whole(db, s):
    """IPS-K-41 — a 100-character key is stored whole.
    Rules: create_payment R9i, R9g [BUG-3002]."""
    i1 = inv(db, s, 1)
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key="k" * 100,
    )
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    assert col(db, result, "idempotency_key") == "k" * 100


# [claude] IPS-K-42
@XF_3002_TE
def test_ips_k_42__abc_and_lower_abc_two_payments(db, s):
    """IPS-K-42 — `"ABC"` stored and `"abc"` sent are two keys: two payments.
    Rules: create_payment R9i, R9a [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed="ABC")
    db.commit()
    result = svc.create_payment(
        db,
        payment_in=body(i1.id),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        idempotency_key="abc",
    )
    # Then 1
    assert result.id != p1.id
    db.rollback()
    # Then 2
    assert pay_count(db, i1.id) == 2
    # Then 3
    assert col(db, result, "idempotency_key") == "abc"
    # Then 4
    assert reread(db, AccountInvoice, i1.id).paid_amount == Decimal("800.00")


# [claude] IPS-K-43
@XF_3002_TE
def test_ips_k_43__replay_on_invoice_no_longer_confirmed(db, s):
    """IPS-K-43 — the replay works on an invoice that is no longer confirmed.
    Rules: create_payment R9b, R9g, R9h [BUG-3002]."""
    i1 = inv(
        db,
        s,
        1,
        invoice_status="voided",
        paid_amount=Decimal("400.00"),
        payment_status="partial",
    )
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    with spies(db) as (cm, _rb):
        result = svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 1
    assert result.id == p1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert x_count(db) == 0
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-K-44
@XF_3002_TE
def test_ips_k_44__key_reused_with_unknown_invoice_404(db, s):
    """IPS-K-44 — a key reused with an unknown `invoice_id` gets the 404, not 409.
    Rules: create_payment R9g, R3 [BUG-3002]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p1 = tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    db.commit()
    before = counts(db)
    p1_before = snap_pay(db, p1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(MISSING),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Invoice with ID 999999999 not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_pay(db, p1.id) == p1_before


# [claude] IPS-K-45
@XF_3002_TE
def test_ips_k_45__key_reused_with_w2_invoice_404(db, s):
    """IPS-K-45 — a key reused with another workspace's invoice gets the 404, not 409.
    Rules: create_payment R9g, R3 [BUG-3002] (HR-16)."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1, created_by=s.U1.id, keyed=KEY)
    i2 = inv(db, s, 2)
    db.commit()
    before = counts(db)
    i2_before = snap_inv(db, i2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_payment(
            db,
            payment_in=body(i2.id),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i2.id} not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i2.id) == i2_before


# [claude] IPS-K-46
@XF_3002_TE
def test_ips_k_46__other_integrity_error_not_translated(db, s):
    """IPS-K-46 — with a key, an `IntegrityError` on another constraint is not translated.
    Rules: create_payment R9e, R3 [BUG-3002]; TC3."""
    i1 = inv(db, s, 1)
    db.commit()
    before = counts(db)
    mk_x(db, s)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_payment(
            db,
            payment_in=body(i1.id),
            workspace_id=s.W1.id,
            user_id=MISSING,
            idempotency_key=KEY,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert counts(db) == before
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert usable(db)


# =========================================================================== #
# get_payment
# =========================================================================== #


# [claude] IPS-G-01
def test_ips_g_01__payment_with_recorder_name(db, s):
    """IPS-G-01 — a payment of the workspace with its recorder's name.
    Rules: get_payment R1, Returns."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = svc.get_payment(db, payment_id=p.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p.id
    # Then 2
    assert result.payment_amount == Decimal("400.00")
    assert result.notes == "Advance"
    # Then 3
    assert result.created_by == s.U2.id
    assert result.created_by_name == s.U2.name


# [claude] IPS-G-02
def test_ips_g_02__voided_payment_returned(db, s):
    """IPS-G-02 — a voided payment is returned with its void fields.
    Rules: get_payment R1."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1, voided=True)
    db.commit()
    result = svc.get_payment(db, payment_id=p.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == p.id
    # Then 2
    assert result.is_voided is True
    assert result.voided_at == T0
    assert result.voided_by == s.U2.id
    assert result.void_note == "Duplicate entry"
    # Then 3
    assert result.created_by_name == s.U2.name


# [claude] IPS-G-03
def test_ips_g_03__no_recorder_name_none(db, s):
    """IPS-G-03 — a payment with no recorder has `created_by_name None`.
    Rules: get_payment Returns; _payment_response R1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1, created_by=None)
    db.commit()
    result = svc.get_payment(db, payment_id=p.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == p.id
    assert result.created_by is None
    # Then 2
    assert result.created_by_name is None


# [claude] IPS-G-04
def test_ips_g_04__unknown_id_404(db, s):
    """IPS-G-04 — an unknown id is a 404 raised by the service.
    Rules: get_payment R2, Errors row 1."""
    inv(db, s, 1)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_payment(db, payment_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Payment with ID 999999999 not found"


# [claude] IPS-G-05
def test_ips_g_05__payment_of_w2_not_found(db, s):
    """IPS-G-05 — a payment of W2 (built after W1) is not found.
    Rules: get_payment R2 (HR-16)."""
    i1 = inv(db, s, 1)
    tw(db, s, i1)
    i2 = inv(db, s, 2)
    p2 = tw(db, s, i2)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_payment(db, payment_id=p2.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p2.id} not found"


# [claude] IPS-G-06
def test_ips_g_06__payment_of_w0_not_found(db, s):
    """IPS-G-06 — a payment of W0 (built before W1) is not found.
    Rules: get_payment R2 (HR-16)."""
    i0 = inv(db, s, 0)
    p0 = tw(db, s, i0)
    i1 = inv(db, s, 1)
    tw(db, s, i1)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_payment(db, payment_id=p0.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p0.id} not found"


# [claude] IPS-G-07
def test_ips_g_07__read_no_commit_no_rollback(db, s):
    """IPS-G-07 — a read neither commits nor rolls back, also on the 404.
    Rules: get_payment R3; TC6."""
    inv(db, s, 1)
    db.commit()
    mk_x(db, s)
    with spies(db) as (cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_payment(db, payment_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db) == 1


# [claude] IPS-G-08
def test_ips_g_08__found_no_commit_no_rollback_pending_stays(db, s):
    """IPS-G-08 — a found payment: no commit, no rollback, pending work stays pending.
    Rules: get_payment R3; TC6."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    y = Account(workspace_id=s.W1.id, name="Pending new")
    db.add(y)
    s.A1.name = "Renamed"
    with spies(db) as (cm, rb):
        result = svc.get_payment(db, payment_id=p.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == p.id
    assert result.created_by_name == s.U2.name
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert y in db.new
    # Then 5
    assert s.A1 in db.dirty


# =========================================================================== #
# list_payments_by_invoice
# =========================================================================== #


# [claude] IPS-L-01
def test_ips_l_01__newest_first_voided_included_names(db, s):
    """IPS-L-01 — the invoice's payments, newest date first, voided included, with names.
    Rules: list_payments_by_invoice R1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("300.00"), payment_status="partial")
    i1b = inv(db, s, 1, paid_amount=Decimal("50.00"), payment_status="partial")
    la = tw(
        db,
        s,
        i1,
        payment_amount=Decimal("100.00"),
        payment_date=date(2026, 9, 1),
        created_by=s.U1.id,
    )
    lb = tw(db, s, i1, payment_amount=Decimal("200.00"), payment_date=date(2026, 9, 5))
    lc = tw(
        db,
        s,
        i1,
        payment_amount=Decimal("300.00"),
        payment_date=date(2026, 9, 3),
        voided=True,
    )
    tw(db, s, i1b, payment_amount=Decimal("50.00"), payment_date=date(2026, 9, 4))
    db.commit()
    result = svc.list_payments_by_invoice(db, invoice_id=i1.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, list)
    assert all(isinstance(r, InvoicePaymentResponse) for r in result)
    # Then 2
    assert [r.id for r in result] == [lb.id, lc.id, la.id]
    # Then 3
    assert [r.created_by_name for r in result] == [s.U2.name, s.U2.name, s.U1.name]
    # Then 4
    assert result[1].is_voided is True
    assert result[1].void_note == "Duplicate entry"


# [claude] IPS-L-02
@pytest.mark.xfail(strict=True, reason=BUG_600)
def test_ips_l_02__same_date_ties_by_id_desc(db, s):
    """IPS-L-02 — pass-through BUG-600: same date ties break by id descending.
    Rules: list_payments_by_invoice R1 [BUG-600]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("300.00"), payment_status="partial")
    a, b, c = (
        db.execute(
            text("SELECT nextval(pg_get_serial_sequence('invoice_payments', 'id'))")
        ).scalar_one()
        for _ in range(3)
    )
    for pid in (c, a, b):
        tw(
            db,
            s,
            i1,
            id=pid,
            payment_amount=Decimal("100.00"),
            payment_date=date(2026, 9, 10),
        )
    db.commit()
    result = svc.list_payments_by_invoice(db, invoice_id=i1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert [r.id for r in result] == [c, b, a]


# [claude] IPS-L-03
def test_ips_l_03__no_payments_empty_list(db, s):
    """IPS-L-03 — an invoice with no payments gives `[]`.
    Rules: list_payments_by_invoice R2."""
    i1 = inv(db, s, 1)
    i1b = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1b)
    db.commit()
    result = svc.list_payments_by_invoice(db, invoice_id=i1.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []
    assert type(result) is list


# [claude] IPS-L-04
def test_ips_l_04__unknown_invoice_404(db, s):
    """IPS-L-04 — an unknown invoice: the manager's 404 passes unchanged.
    Rules: list_payments_by_invoice R3, Errors."""
    inv(db, s, 1)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.list_payments_by_invoice(db, invoice_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Invoice with ID 999999999 not found"


# [claude] IPS-L-05
def test_ips_l_05__invoice_of_w2_not_found(db, s):
    """IPS-L-05 — an invoice of W2 (built after W1) is not found.
    Rules: list_payments_by_invoice R1 (HR-16)."""
    inv(db, s, 1)
    i2 = inv(db, s, 2, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i2)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.list_payments_by_invoice(db, invoice_id=i2.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i2.id} not found"


# [claude] IPS-L-06
def test_ips_l_06__invoice_of_w0_not_found(db, s):
    """IPS-L-06 — an invoice of W0 (built before W1) is not found.
    Rules: list_payments_by_invoice R1 (HR-16)."""
    i0 = inv(db, s, 0, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i0)
    inv(db, s, 1)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.list_payments_by_invoice(db, invoice_id=i0.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i0.id} not found"


# [claude] IPS-L-07
def test_ips_l_07__skip_and_limit_passed_on(db, s):
    """IPS-L-07 — `skip` and `limit` are passed on.
    Rules: list_payments_by_invoice R1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = [
        tw(db, s, i1, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, k))
        for k in (1, 2, 3, 4)
    ]
    db.commit()
    result = svc.list_payments_by_invoice(
        db, invoice_id=i1.id, workspace_id=s.W1.id, skip=1, limit=2
    )
    # Then 1
    assert [r.id for r in result] == [p[2].id, p[1].id]


def _hundred_and_one(db, s):
    """L-08 / L-09 Given: I1 with 101 payments of 10.00, dated 2026-01-01 + k days."""
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("1000000.00"),
        paid_amount=Decimal("1010.00"),
        payment_status="partial",
    )
    db.add_all(
        [
            InvoicePayment(
                workspace_id=i1.workspace_id,
                invoice_id=i1.id,
                payment_amount=Decimal("10.00"),
                payment_date=date(2026, 1, 1) + timedelta(days=k),
                payment_method="cash",
                payment_reference="RCPT-77",
                bank_name="City Bank",
                transaction_id="TXN-9",
                notes="Advance",
                created_by=s.U2.id,
                is_voided=False,
            )
            for k in range(1, 102)
        ]
    )
    db.flush()
    db.commit()
    return i1


# [claude] IPS-L-08
def test_ips_l_08__default_limit_100(db, s):
    """IPS-L-08 — the default limit is 100.
    Rules: list_payments_by_invoice R1 (signature default)."""
    i1 = _hundred_and_one(db, s)
    result = svc.list_payments_by_invoice(db, invoice_id=i1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].payment_date == date(2026, 4, 12)
    assert result[-1].payment_date == date(2026, 1, 3)


# [claude] IPS-L-09
def test_ips_l_09__limit_1000_returns_all(db, s):
    """IPS-L-09 — `limit=1000` returns all 101.
    Rules: list_payments_by_invoice R1."""
    i1 = _hundred_and_one(db, s)
    result = svc.list_payments_by_invoice(
        db, invoice_id=i1.id, workspace_id=s.W1.id, skip=0, limit=1000
    )
    # Then 1
    assert len(result) == 101


# [claude] IPS-L-10
def test_ips_l_10__list_no_commit_no_rollback(db, s):
    """IPS-L-10 — a list neither commits nor rolls back.
    Rules: list_payments_by_invoice R3; TC6."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    mk_x(db, s)
    with spies(db) as (cm, rb):
        result = svc.list_payments_by_invoice(
            db, invoice_id=i1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert [r.id for r in result] == [p.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_count(db) == 1


# =========================================================================== #
# update_payment
# =========================================================================== #


# [claude] IPS-U-01
def test_ips_u_01__edit_committed_invoice_untouched(db, s):
    """IPS-U-01 — an edit is committed, the invoice is untouched, the recorder's name is shown.
    Rules: update_payment R1, Returns; TC1, TC2."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = upd(db, s, p.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p.id
    # Then 2
    assert result.payment_reference == "RCPT-99"
    assert result.created_by_name == s.U2.name
    assert result.created_at is not None
    db.rollback()
    # Then 3
    pr = reread(db, InvoicePayment, p.id)
    assert pr.payment_reference == "RCPT-99"
    assert pr.payment_amount == Decimal("400.00")
    assert pr.notes == "Advance"
    # Then 4
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("400.00")
    assert i1r.payment_status == "partial"


# [claude] IPS-U-02
def test_ips_u_02__unknown_id_404_pending_discarded(db, s):
    """IPS-U-02 — an unknown id: the manager's 404 passes, pending work discarded.
    Rules: update_payment R2; TC3."""
    inv(db, s, 1)
    db.commit()
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(db, s, MISSING, InvoicePaymentUpdate(notes="x"))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Payment with ID 999999999 not found"
    # Then 4
    assert x_count(db) == 0
    # Then 5
    assert usable(db)


# [claude] IPS-U-03
def test_ips_u_03__payment_of_w2_not_found(db, s):
    """IPS-U-03 — a payment of W2 (built after W1) is not found.
    Rules: update_payment R2 (HR-16)."""
    inv(db, s, 1)
    i2 = inv(db, s, 2, paid_amount=Decimal("400.00"), payment_status="partial")
    p2 = tw(db, s, i2)
    db.commit()
    p2_before = snap_pay(db, p2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(db, s, p2.id, InvoicePaymentUpdate(payment_reference="HACK"))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p2.id} not found"
    # Then 4
    assert snap_pay(db, p2.id) == p2_before


# [claude] IPS-U-04
def test_ips_u_04__payment_of_w0_not_found(db, s):
    """IPS-U-04 — a payment of W0 (built before W1) is not found.
    Rules: update_payment R2 (HR-16)."""
    i0 = inv(db, s, 0, paid_amount=Decimal("400.00"), payment_status="partial")
    p0 = tw(db, s, i0)
    inv(db, s, 1)
    db.commit()
    p0_before = snap_pay(db, p0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(db, s, p0.id, InvoicePaymentUpdate(payment_reference="HACK"))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p0.id} not found"
    # Then 4
    assert snap_pay(db, p0.id) == p0_before


# [claude] IPS-U-05
def test_ips_u_05__amount_change_400_nothing_saved(db, s):
    """IPS-U-05 — an amount change: the manager's 400 passes, nothing saved.
    Rules: update_payment R2; TC3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    p_before = snap_pay(db, p.id)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(
            db,
            s,
            p.id,
            InvoicePaymentUpdate(payment_amount=Decimal("300.00"), notes="changed"),
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail.startswith("Cannot change payment amount.")
    # Then 4
    assert snap_pay(db, p.id) == p_before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert x_count(db) == 0


# [claude] IPS-U-06
@pytest.mark.xfail(strict=True, reason=BUG_611)
def test_ips_u_06__amount_message_says_void(db, s):
    """IPS-U-06 — pass-through BUG-611: the amount message says "Void and re-create".
    Rules: update_payment R2 [BUG-611]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(db, s, p.id, InvoicePaymentUpdate(payment_amount=Decimal("300.00")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Cannot change payment amount. Void and re-create payment instead."
    )


# [claude] IPS-U-07
@pytest.mark.xfail(strict=True, reason=BUG_606)
def test_ips_u_07__voided_payment_cannot_be_edited(db, s):
    """IPS-U-07 — pass-through BUG-606: a voided payment cannot be edited.
    Rules: update_payment R2 [BUG-606]."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1, voided=True)
    db.commit()
    p_before = snap_pay(db, p.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        upd(db, s, p.id, InvoicePaymentUpdate(notes="Edited after void"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Voided payments cannot be edited"
    # Then 4
    assert snap_pay(db, p.id) == p_before
    # Then 5
    assert x_count(db) == 0


# [claude] IPS-U-08
@pytest.mark.xfail(strict=True, reason=BUG_608)
def test_ips_u_08__bank_name_none_clears(db, s):
    """IPS-U-08 — pass-through BUG-608: sending `bank_name None` clears it.
    Rules: update_payment R1 [BUG-608]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = upd(db, s, p.id, InvoicePaymentUpdate(bank_name=None))
    # Then 1
    assert result.id == p.id
    db.rollback()
    # Then 2
    pr = reread(db, InvoicePayment, p.id)
    assert pr.bank_name is None
    # Then 3
    assert pr.payment_reference == "RCPT-77"
    assert pr.notes == "Advance"


# [claude] IPS-U-09
@pytest.mark.xfail(strict=True, raises=TypeError, reason=BUG_607)
def test_ips_u_09__editor_named_on_audit_and_event(db, s):
    """IPS-U-09 — BUG-607: the editor is passed on and named on the committed audit row and event.
    Rules: update_payment R4, R1 [BUG-607]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = svc.update_payment(
        db,
        payment_id=p.id,
        payment_in=InvoicePaymentUpdate(payment_reference="RCPT-99"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
    )
    # Then 1
    assert result.payment_reference == "RCPT-99"
    db.rollback()
    # Then 2
    rows = audit(db, p.id)
    assert len(rows) == 1
    assert rows[0].action_type == "updated"
    assert rows[0].performed_by == s.U1.id
    # Then 3
    evs = events(db, i1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "payment_updated"
    assert evs[0].performed_by == s.U1.id


# [claude] IPS-U-10
def test_ips_u_10__empty_update_commits_unchanged(db, s):
    """IPS-U-10 — an empty update commits and returns the payment unchanged.
    Rules: update_payment R5."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    p_before = snap_pay(db, p.id)
    with spies(db) as (cm, _rb):
        result = upd(db, s, p.id, InvoicePaymentUpdate())
    # Then 1
    assert result.id == p.id
    assert result.payment_reference == "RCPT-77"
    assert result.notes == "Advance"
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert snap_pay(db, p.id) == p_before


# [claude] IPS-U-11
def test_ips_u_11__failing_commit_edit_not_saved(db, s):
    """IPS-U-11 — a failing commit is rolled back and re-raised; the edit is not saved.
    Rules: update_payment R3; TC4."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(db, "commit", side_effect=RuntimeError("boom")),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            upd(db, s, p.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, InvoicePayment, p.id).payment_reference == "RCPT-77"


# [claude] IPS-U-12
def test_ips_u_12__failing_refresh_edit_saved(db, s):
    """IPS-U-12 — a failing re-read after the commit leaves the edit saved.
    Rules: update_payment R3; TC5."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            upd(db, s, p.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert reread(db, InvoicePayment, p.id).payment_reference == "RCPT-99"


# =========================================================================== #
# delete_payment
# =========================================================================== #


# [claude] IPS-D-01
def test_ips_d_01__unknown_id_404_nothing_written(db, s):
    """IPS-D-01 — an unknown id: the service's 404, rolled back, nothing written.
    Rules: delete_payment R1, Errors row 1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    tw(db, s, i1)
    db.commit()
    before = counts(db)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(
            db, payment_id=MISSING, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Payment with ID 999999999 not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert x_count(db) == 0


# [claude] IPS-D-02
def test_ips_d_02__payment_of_w2_not_found_stays(db, s):
    """IPS-D-02 — a payment of W2 (built after W1) is not found and stays.
    Rules: delete_payment R1 (HR-16)."""
    inv(db, s, 1)
    i2 = inv(db, s, 2, paid_amount=Decimal("400.00"), payment_status="partial")
    p2 = tw(db, s, i2)
    db.commit()
    p2_before = snap_pay(db, p2.id)
    i2_before = snap_inv(db, i2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(db, payment_id=p2.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p2.id} not found"
    # Then 4
    assert snap_pay(db, p2.id) == p2_before
    # Then 5
    assert snap_inv(db, i2.id) == i2_before


# [claude] IPS-D-03
def test_ips_d_03__payment_of_w0_not_found_stays(db, s):
    """IPS-D-03 — a payment of W0 (built before W1) is not found and stays.
    Rules: delete_payment R1 (HR-16)."""
    i0 = inv(db, s, 0, paid_amount=Decimal("400.00"), payment_status="partial")
    p0 = tw(db, s, i0)
    inv(db, s, 1)
    db.commit()
    p0_before = snap_pay(db, p0.id)
    i0_before = snap_inv(db, i0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(db, payment_id=p0.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p0.id} not found"
    # Then 4
    assert snap_pay(db, p0.id) == p0_before
    # Then 5
    assert snap_inv(db, i0.id) == i0_before


# [claude] IPS-D-04
@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ips_d_04__active_payment_never_deleted(db, s):
    """IPS-D-04 — BUG-609: an active payment is never deleted; 400, all unchanged.
    Rules: delete_payment R2, R3, Errors row 2 [BUG-609]; TC3."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    before = counts(db)
    p_before = snap_pay(db, p.id)
    i1_before = snap_inv(db, i1.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(db, payment_id=p.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Payments cannot be deleted — void them instead"
    # Then 4
    assert snap_pay(db, p.id) == p_before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before
    # Then 6
    assert counts(db) == before
    # Then 7
    assert x_count(db) == 0


# [claude] IPS-D-05
@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ips_d_05__voided_payment_never_deleted(db, s):
    """IPS-D-05 — BUG-609: a voided payment is never deleted either.
    Rules: delete_payment R2 [BUG-609]."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1, voided=True)
    db.commit()
    p_before = snap_pay(db, p.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(db, payment_id=p.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Payments cannot be deleted — void them instead"
    # Then 4
    assert snap_pay(db, p.id) == p_before


# [claude] IPS-D-06
@pytest.mark.xfail(strict=True, reason=BUG_609)
def test_ips_d_06__linked_order_keeps_paid(db, s):
    """IPS-D-06 — BUG-609: the linked order keeps its `paid` flag.
    Rules: delete_payment R2 [BUG-609]."""
    po = po1(db, s, paid=True)
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("400.00"),
        paid_amount=Decimal("400.00"),
        payment_status="paid",
        order_type="purchase_order",
        order_id=po.id,
    )
    p = tw(db, s, i1)
    po.invoice_id = i1.id
    db.flush()
    db.commit()
    before = counts(db)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_payment(db, payment_id=p.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert reread(db, PurchaseOrder, po.id).paid is True
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap_inv(db, i1.id) == i1_before


# [claude] IPS-D-07
def test_ips_d_07__failing_commit_or_refusal_payment_stays(db, s):
    """IPS-D-07 — a failing commit (today) or the refusal (after BUG-609): the payment stays either way.
    Rules: delete_payment R4; TC4."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    i1_before = snap_inv(db, i1.id)
    with pytest.raises((RuntimeError, HTTPException)) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            svc.delete_payment(
                db, payment_id=p.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 1
    assert isinstance(exc.value, (RuntimeError, HTTPException))
    # Then 2
    n = db.execute(
        select(func.count())
        .select_from(InvoicePayment)
        .where(InvoicePayment.id == p.id)
    ).scalar_one()
    assert n == 1
    # Then 3
    assert snap_inv(db, i1.id) == i1_before


# =========================================================================== #
# void_payment
# =========================================================================== #


# [claude] IPS-V-01
def test_ips_v_01__void_committed_names_recorder(db, s):
    """IPS-V-01 — a void is committed; the response names the recorder, not the voider.
    Rules: void_payment R1, Returns; TC1, TC2."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = svc.void_payment(
        db,
        payment_id=p.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        void_note="Cheque bounced",
    )
    # Then 1
    assert isinstance(result, InvoicePaymentResponse)
    assert result.id == p.id
    # Then 2
    assert result.is_voided is True
    assert result.voided_at == NOW
    assert result.voided_by == s.U1.id
    assert result.void_note == "Cheque bounced"
    # Then 3
    assert result.created_by == s.U2.id
    assert result.created_by_name == s.U2.name
    db.rollback()
    # Then 4
    pr = reread(db, InvoicePayment, p.id)
    assert pr.is_voided is True
    assert pr.voided_by == s.U1.id
    assert pr.void_note == "Cheque bounced"
    # Then 5
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("0.00")
    assert i1r.payment_status == "unpaid"


# [claude] IPS-V-02
def test_ips_v_02__void_audit_and_event_committed(db, s):
    """IPS-V-02 — the void's audit row and invoice event are committed.
    Rules: void_payment R1, R5 (default None); TC1."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = svc.void_payment(
        db,
        payment_id=p.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        void_note="Cheque bounced",
    )
    # Then 1
    assert result.is_voided is True
    db.rollback()
    # Then 2
    rows = audit(db, p.id)
    assert len(rows) == 1
    assert rows[0].action_type == "voided"
    assert rows[0].performed_by == s.U1.id
    # Then 3
    assert rows[0].ip_address is None
    assert rows[0].user_agent is None
    # Then 4
    evs = events(db, i1.id)
    assert len(evs) == 1
    assert evs[0].event_type == "payment_voided"
    assert evs[0].performed_by == s.U1.id


# [claude] IPS-V-03
def test_ips_v_03__void_on_invoice_of_completed_order(db, s):
    """IPS-V-03 — a payment on the invoice of a completed order can be voided.
    Rules: void_payment R1 (owner O1 / F7); TC1."""
    eo = eo1(db, s)
    i1 = inv(
        db,
        s,
        1,
        paid_amount=Decimal("400.00"),
        payment_status="partial",
        order_type="expense_order",
        order_id=eo.id,
    )
    p = tw(db, s, i1)
    eo.invoice_id = i1.id
    db.flush()
    db.commit()
    result = svc.void_payment(
        db,
        payment_id=p.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        void_note="Cheque bounced",
    )
    # Then 1
    assert result.is_voided is True
    db.rollback()
    # Then 2
    assert reread(db, InvoicePayment, p.id).is_voided is True
    # Then 3
    i1r = reread(db, AccountInvoice, i1.id)
    assert i1r.paid_amount == Decimal("0.00")
    assert i1r.payment_status == "unpaid"
    # Then 4
    eor = reread(db, ExpenseOrder, eo.id)
    assert eor.completed_at == T0
    assert eor.invoice_id == i1.id


# [claude] IPS-V-04
def test_ips_v_04__unknown_id_404_pending_discarded(db, s):
    """IPS-V-04 — an unknown id: the manager's 404 passes, pending work discarded.
    Rules: void_payment R2; TC3."""
    inv(db, s, 1)
    db.commit()
    before = counts(db)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_payment(
            db,
            payment_id=MISSING,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Payment with ID 999999999 not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    assert x_count(db) == 0


# [claude] IPS-V-05
def test_ips_v_05__payment_of_w2_not_found(db, s):
    """IPS-V-05 — a payment of W2 (built after W1) is not found.
    Rules: void_payment R2 (HR-16)."""
    inv(db, s, 1)
    i2 = inv(db, s, 2, paid_amount=Decimal("400.00"), payment_status="partial")
    p2 = tw(db, s, i2)
    db.commit()
    p2_before = snap_pay(db, p2.id)
    i2_before = snap_inv(db, i2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_payment(
            db,
            payment_id=p2.id,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p2.id} not found"
    # Then 4
    assert snap_pay(db, p2.id) == p2_before
    # Then 5
    assert snap_inv(db, i2.id) == i2_before


# [claude] IPS-V-06
def test_ips_v_06__payment_of_w0_not_found(db, s):
    """IPS-V-06 — a payment of W0 (built before W1) is not found.
    Rules: void_payment R2 (HR-16)."""
    i0 = inv(db, s, 0, paid_amount=Decimal("400.00"), payment_status="partial")
    p0 = tw(db, s, i0)
    inv(db, s, 1)
    db.commit()
    p0_before = snap_pay(db, p0.id)
    i0_before = snap_inv(db, i0.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_payment(
            db,
            payment_id=p0.id,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Payment with ID {p0.id} not found"
    # Then 4
    assert snap_pay(db, p0.id) == p0_before
    # Then 5
    assert snap_inv(db, i0.id) == i0_before


# [claude] IPS-V-07
def test_ips_v_07__second_void_400_writes_nothing(db, s):
    """IPS-V-07 — a second void is a 400, not a replay, and writes nothing.
    Rules: void_payment R2, R6; TC3."""
    i1 = inv(db, s, 1)
    p = tw(db, s, i1, voided=True)
    db.commit()
    before = counts(db)
    p_before = snap_pay(db, p.id)
    mk_x(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_payment(
            db,
            payment_id=p.id,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Payment is already voided"
    # Then 4
    assert snap_pay(db, p.id) == p_before
    # Then 5
    assert counts(db) == before
    # Then 6
    assert x_count(db) == 0


# [claude] IPS-V-08
def test_ips_v_08__payment_pointing_at_missing_invoice_404(db, s):
    """IPS-V-08 — a payment pointing at a missing invoice: the manager's 404 passes.
    Rules: void_payment R2."""
    i2 = inv(db, s, 2)
    p = tw(db, s, i2, workspace_id=s.W1.id)
    db.commit()
    p_before = snap_pay(db, p.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_payment(
            db,
            payment_id=p.id,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {i2.id} not found"
    # Then 4
    assert snap_pay(db, p.id) == p_before


# [claude] IPS-V-09
def test_ips_v_09__failing_commit_payment_stays_active(db, s):
    """IPS-V-09 — a failing commit is rolled back; the payment stays active.
    Rules: void_payment R3; TC4."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    before = counts(db)
    p_before = snap_pay(db, p.id)
    i1_before = snap_inv(db, i1.id)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(db, "commit", side_effect=RuntimeError("boom")),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            svc.void_payment(
                db,
                payment_id=p.id,
                workspace_id=s.W1.id,
                user_id=s.U1.id,
                void_note="Cheque bounced",
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap_pay(db, p.id) == p_before
    # Then 4
    assert snap_inv(db, i1.id) == i1_before
    # Then 5
    assert counts(db) == before


# [claude] IPS-V-10
def test_ips_v_10__failing_refresh_void_saved(db, s):
    """IPS-V-10 — a failing re-read after the commit leaves the void saved.
    Rules: void_payment R3; TC5."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.void_payment(
                db,
                payment_id=p.id,
                workspace_id=s.W1.id,
                user_id=s.U1.id,
                void_note="Cheque bounced",
            )
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    pr = reread(db, InvoicePayment, p.id)
    assert pr.is_voided is True
    assert pr.void_note == "Cheque bounced"
    # Then 3
    assert reread(db, AccountInvoice, i1.id).paid_amount == Decimal("0.00")


# [claude] IPS-V-11
@pytest.mark.xfail(strict=True, reason=BUG_601)
def test_ips_v_11__void_locks_invoice_plain_for_update(db, s):
    """IPS-V-11 — pass-through BUG-601: the void locks the invoice with a plain `FOR UPDATE`.
    Rules: void_payment R4 [BUG-601]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    with recorder(db) as stmts:
        result = svc.void_payment(
            db,
            payment_id=p.id,
            workspace_id=s.W1.id,
            user_id=s.U1.id,
            void_note="Cheque bounced",
        )
    locks = lock_stmts(stmts)
    # Then 1
    assert result.is_voided is True
    # Then 2
    assert len(locks) >= 1
    # Then 3
    assert not any("SKIP LOCKED" in st for st in locks)
    # Then 4
    assert not any("NOWAIT" in st for st in locks)


# [claude] IPS-V-12
@pytest.mark.xfail(strict=True, raises=TypeError, reason=BUG_603)
def test_ips_v_12__ip_and_browser_reach_void_audit_row(db, s):
    """IPS-V-12 — BUG-603: IP and browser reach the void's audit row.
    Rules: void_payment R5 [BUG-603]."""
    i1 = inv(db, s, 1, paid_amount=Decimal("400.00"), payment_status="partial")
    p = tw(db, s, i1)
    db.commit()
    result = svc.void_payment(
        db,
        payment_id=p.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        void_note="Cheque bounced",
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 (Test)",
    )
    # Then 1
    assert result.is_voided is True
    db.rollback()
    # Then 2
    rows = audit(db, p.id)
    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "Mozilla/5.0 (Test)"


# [claude] IPS-V-13
def test_ips_v_13__linked_po_paid_change_committed(db, s):
    """IPS-V-13 — the linked purchase order's `paid` change is committed.
    Rules: void_payment R1; TC1."""
    po = po1(db, s, paid=True)
    i1 = inv(
        db,
        s,
        1,
        invoice_amount=Decimal("400.00"),
        paid_amount=Decimal("400.00"),
        payment_status="paid",
        order_type="purchase_order",
        order_id=po.id,
    )
    p = tw(db, s, i1)
    po.invoice_id = i1.id
    db.flush()
    db.commit()
    result = svc.void_payment(
        db,
        payment_id=p.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        void_note="Cheque bounced",
    )
    # Then 1
    assert result.is_voided is True
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrder, po.id).paid is False
    # Then 3
    assert reread(db, AccountInvoice, i1.id).payment_status == "unpaid"
