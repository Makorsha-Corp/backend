# ruff: noqa: SIM117, DTZ001, FURB157, B017
# (nested pytest.raises + savepoint, naive datetimes, Decimal("0") literals and
# pytest.raises(Exception) are all prescribed by the cards.)
"""Unit tests for app/managers/account_invoice_manager.py.

Implements tests/unit/managers/account_invoice_manager.cases.md (revision 11),
one test per case. Real Postgres session (`db` fixture). Mocks: only
`app.managers.account_invoice_manager.utcnow` (every test, patched to NOW).
No race simulations (spec: none).

Revision 4 changes (see account_invoice_manager.notes.md "Revision history"):
AIM-U-38 / AIM-U-45 are now designed `xfail BUG-625` (gap G15 — the cases file
no longer assumes `AccountInvoiceUpdate` has an `order_type` field today), new
AIM-U-53 pins that on the schema directly, and AIM-EV-05 / AIM-IT-04 use a
sequence-reserving setup (G10) so their BUG-638 xfail is deterministic instead
of flaky.

Revision 5 changes: the spec's R9d ("live" order per order type: PO/EO
`voided=False`; WO `is_deleted=False` and `status != "VOIDED"`; SO any row)
added six new `create_invoice` cases (AIM-C-22..AIM-C-27, both sides of each
order type) and two new `update_invoice` cases (AIM-U-54, AIM-U-55, work-order
liveness on update). This pass also applies account_invoice_manager.verify.md's
routed findings: `synccall` no longer passes `is_manual` explicitly (finding 1,
so the production-live default is actually exercised); several cases that were
missing their "returns the invoice" assertion now capture and check the return
value (finding 2: U-13, U-14, U-15, U-16, U-21, U-27, U-42, CF-02, CF-03,
RV-02, RV-03, VD-02, VD-09, RS-02, RS-03, RS-04); AIM-RV-08 now does a full
`snap_inv` unchanged comparison instead of checking only `invoice_status`
(finding 3); and the voided-payment setups in AIM-DEL-06/DEL-07/RV-03 now pass
`created_by=u1.id` so `voided_by` matches the Conventions (U1 created every
setup row) (finding 4). Finding 5 (the spec's PO liveness note) is a
describer-side spec gap already worked around here via `mk_po`'s `voided=True`.

Revision 6 fix round 2: every case whose Then says "returns the invoice" now
asserts the returned row's id (also in the strict-xfail tests, before the
designed failing assertion), and every case whose Then says "unchanged" /
"nothing written" compares a full `snap_inv` (or W1 + W2 counts for create
errors). See the notes' Revision history for the list.

Revision 7 (2026-11-14): the completed-order freeze (spec O1, F1-F7; BUG-2730,
BUG-2731, BUG-2733, BUG-2736). New cards DEL-14..24, RV-13..46, VD-14..28,
U-61, U-62; RV-05 / RV-06 split (the exact new receiving text moved to RV-13 /
RV-14); DEL-01 / DEL-11 pin their orders as not completed; Errors-row numbers
updated. New conventions: W0 (`w0`, built before W1 and W2), ST(W, name)
(`mk_st`), PO stage (`mk_po(..., stage=...)`), CN / OI (`mk_cn` / `mk_oi`),
session clean (`assert_session_clean`) and the LOCK / CNTXT / RCVTXT texts.
"""
import itertools
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.account_invoice_manager import AccountInvoiceManager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.invoice_status_tracker import InvoiceStatusTracker
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_item_ledger import MachineItemLedger
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_return import PurchaseOrderReturn
from app.models.sales_order import SalesOrder
from app.models.sales_order_return import SalesOrderReturn
from app.models.status import Status
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.schemas.account_invoice import (
    AccountInvoiceCreate,
    AccountInvoiceUpdate,
    VoidInvoiceRequest,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Time": NOW pinned via app.managers.account_invoice_manager.utcnow;
# V0/L0 earlier timestamps set directly on setup rows.
NOW = datetime(2026, 9, 27, 12, 0, 0)
V0 = datetime(2026, 9, 1, 8, 0, 0)
L0 = datetime(2026, 9, 2, 9, 0, 0)

# Convention "NOID = 999999, an id that exists in no table used here."
NOID = 999999

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


@pytest.fixture(autouse=True)
def _utcnow():
    with patch("app.managers.account_invoice_manager.utcnow", return_value=NOW) as m:
        yield m


@pytest.fixture
def M():
    return AccountInvoiceManager()


# Convention "W0, W1, W2 = three workspaces, built in that order so
# W0.id < W1.id < W2.id" (w1 depends on w0 and w2 on w1, so the order holds in
# every test; the freeze cards that use W0 also assert it).
@pytest.fixture
def w0(db):
    return make_workspace(db)


@pytest.fixture
def w1(db, w0):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles in W1 ... U1's profile name is 'Rahim Uddin'.
# U3 = a profile in W2."
@pytest.fixture
def u1(db):
    return make_profile(db, name="Rahim Uddin")


@pytest.fixture
def u2(db):
    return make_profile(db)


@pytest.fixture
def u3(db):
    return make_profile(db)


# Convention "A1 = account 'Acme Traders' in W1. A2 = 'Beta Supplies' in W1.
# AX = 'Xeno Foreign' in W2." Both A1/A2 default is_active/is_deleted/allow_invoices.
def mk_account(db, ws, name, **overrides):
    fields = {"workspace_id": ws.id, "name": name, "is_active": True, "is_deleted": False, "allow_invoices": True}
    fields.update(overrides)
    row = Account(**fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def a1(db, w1):
    return mk_account(db, w1, "Acme Traders")


@pytest.fixture
def a2(db, w1):
    return mk_account(db, w1, "Beta Supplies")


@pytest.fixture
def ax(db, w2):
    return mk_account(db, w2, "Xeno Foreign")


# Convention "INV(k=v, ...)" — one account_invoices row with the stated defaults.
def mk_inv(db, ws, account, created_by, **overrides):
    fields = {
        "workspace_id": ws.id, "account_id": account.id, "invoice_type": "payable",
        "invoice_status": "confirmed", "payment_status": "unpaid", "invoice_amount": Decimal("1000.00"),
        "paid_amount": Decimal("0.00"), "invoice_date": date(2026, 9, 1), "due_date": None,
        "allow_payments": True, "receiving_started": False, "created_by": created_by,
        "updated_by": None, "updated_at": None, "last_synced_at": None, "void_note": None,
        "description": None, "notes": None, "invoice_number": None, "vendor_invoice_number": None,
        "payment_locked_reason": None, "order_type": None, "order_id": None,
    }
    fields.update(overrides)
    row = AccountInvoice(**fields)
    db.add(row)
    db.flush()
    return row


def inv(db, w1, a1, u1, **overrides):
    """Shorthand for the default INV row (confirmed, amount 1000.00, date 2026-09-01) on A1/W1, created by U1."""
    return mk_inv(db, w1, a1, u1.id, **overrides)


# Convention "CI = INV(description='Old desc', notes='Old notes', invoice_number='INV-1',
# due_date=2026-10-01). DI = CI with invoice_status='draft'. VI = CI voided, void_note 'Old reason'."
CI_DEFAULTS = {"description": "Old desc", "notes": "Old notes", "invoice_number": "INV-1", "due_date": date(2026, 10, 1)}


def mk_ci(db, ws, account, created_by, **overrides):
    fields = {**CI_DEFAULTS, **overrides}
    return mk_inv(db, ws, account, created_by, **fields)


def mk_di(db, ws, account, created_by, **overrides):
    fields = {**CI_DEFAULTS, "invoice_status": "draft", **overrides}
    return mk_inv(db, ws, account, created_by, **fields)


def mk_vi(db, ws, account, created_by, **overrides):
    fields = {**CI_DEFAULTS, "invoice_status": "voided", "void_note": "Old reason", **overrides}
    return mk_inv(db, ws, account, created_by, **fields)


@pytest.fixture
def ci(db, w1, a1, u1):
    return mk_ci(db, w1, a1, u1.id)


@pytest.fixture
def di(db, w1, a1, u1):
    return mk_di(db, w1, a1, u1.id)


@pytest.fixture
def vi(db, w1, a1, u1):
    return mk_vi(db, w1, a1, u1.id)


# Convention "ITEM(inv, s, line_number=1)"
def mk_item(db, inv_row, subtotal, line_number=1, *, workspace_id=None, created_by=None, **overrides):
    fields = {
        "workspace_id": workspace_id if workspace_id is not None else inv_row.workspace_id,
        "invoice_id": inv_row.id, "description": "Item", "quantity": Decimal("1"),
        "unit_price": Decimal(str(subtotal)), "line_subtotal": Decimal(str(subtotal)),
        "line_number": line_number, "created_by": created_by,
    }
    fields.update(overrides)
    row = InvoiceItem(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "PAY(inv, amt, voided=False)"
def mk_pay(db, inv_row, amt, voided=False, *, created_by=None, **overrides):
    fields = {
        "workspace_id": inv_row.workspace_id, "invoice_id": inv_row.id,
        "payment_amount": Decimal(str(amt)), "payment_date": date(2026, 9, 1),
        "is_voided": voided,
        "voided_at": V0 if voided else None,
        "voided_by": created_by if voided else None,
        "void_note": "manual void" if voided else None,
        "created_by": created_by,
    }
    fields.update(overrides)
    row = InvoicePayment(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "HIST(inv)"
def mk_hist(db, inv_row, changed_by, **overrides):
    fields = {
        "workspace_id": inv_row.workspace_id, "invoice_id": inv_row.id,
        "from_status": "draft", "to_status": "confirmed", "changed_by": changed_by, "changed_at": V0,
    }
    fields.update(overrides)
    row = InvoiceStatusTracker(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "EVT(inv, t, performed_by=None)"
def mk_evt(db, inv_row, t, performed_by=None, **overrides):
    fields = {
        "workspace_id": inv_row.workspace_id, "invoice_id": inv_row.id, "created_at": t,
        "event_type": "note", "description": "n", "metadata_json": None, "performed_by": performed_by,
    }
    fields.update(overrides)
    row = InvoiceEvent(**fields)
    db.add(row)
    db.flush()
    return row


# Order shorthand: PO(W, "number") / EO / SO / WO — one live, not completed order
# row, invoice_id None unless stated. The other required columns are filled
# neutrally. Not completed (spec Notes O1): PO stage "Draft"; SO
# order_completed=False; EO completed_at=None; WO status="DRAFT".
# "Completed" (spec F2): PO stage "Complete"; SO order_completed=True; EO
# completed_at=V0; WO status="COMPLETED".
def mk_status(db, ws):
    # Sales orders still need a current_status_id (NOT NULL); its name is never read.
    row = Status(workspace_id=ws.id, name="Open", comment="")
    db.add(row)
    db.flush()
    return row


# Convention "ST(W, 'name')" — one statuses row. Gap G16 (read from the model):
# `statuses` has `workspace_id` (NOT NULL), `name` and `comment` (both NOT NULL);
# no entity-type column. `comment` is the neutral "".
def mk_st(db, ws, name):
    row = Status(workspace_id=ws.id, name=name, comment="")
    db.add(row)
    db.flush()
    return row


def mk_factory(db, ws, name=None):
    name = name or f"Factory {_n()}"
    row = Factory(workspace_id=ws.id, name=name, abbreviation=name[:3].upper(), is_active=True, is_deleted=False)
    db.add(row)
    db.flush()
    return row


def mk_po(db, ws, number, created_by, *, stage="Draft", **overrides):
    # PurchaseOrder has no is_deleted column — its soft-delete-equivalent flag is `voided`.
    # "PO ... stage X" = current_status_id -> ST(W, "X"); the default stage is "Draft".
    status = mk_st(db, ws, stage)
    fields = {
        "workspace_id": ws.id, "po_number": number, "destination_type": "storage", "destination_id": 1,
        "current_status_id": status.id, "created_by": created_by, "voided": False,
    }
    fields.update(overrides)
    row = PurchaseOrder(**fields)
    db.add(row)
    db.flush()
    return row


def mk_eo(db, ws, number, created_by, **overrides):
    fields = {"workspace_id": ws.id, "expense_number": number, "expense_category": "other", "created_by": created_by,
                  "completed_at": None}
    fields.update(overrides)
    row = ExpenseOrder(**fields)
    db.add(row)
    db.flush()
    return row


def mk_so(db, ws, number, created_by, account=None, **overrides):
    status = mk_status(db, ws)
    factory = mk_factory(db, ws)
    account = account or mk_account(db, ws, f"SO Account {_n()}")
    fields = {
        "workspace_id": ws.id, "sales_order_number": number, "account_id": account.id,
        "factory_id": factory.id, "current_status_id": status.id, "created_by": created_by,
        "order_completed": False,
    }
    fields.update(overrides)
    row = SalesOrder(**fields)
    db.add(row)
    db.flush()
    return row


def mk_wo(db, ws, number, **overrides):
    wot = WorkOrderType(workspace_id=ws.id, name=f"Type {_n()}")
    db.add(wot)
    db.flush()
    factory = mk_factory(db, ws)
    fields = {
        "workspace_id": ws.id, "work_order_number": number, "work_order_type_id": wot.id,
        "title": f"WO {number}", "factory_id": factory.id, "status": "DRAFT",
    }
    fields.update(overrides)
    row = WorkOrder(**fields)
    db.add(row)
    db.flush()
    return row


# POR(W) / SOR(W). Gap G16 (read from the models): the order reference of a
# return row is `purchase_order_returns.purchase_order_id` /
# `sales_order_returns.sales_order_id` (both NOT NULL). `order=` points it at
# a given order (CN cards); without it the builder makes its own neutral order.
def mk_por(db, ws, created_by, order=None, **overrides):
    po = order if order is not None else mk_po(db, ws, f"PO-POR-{_n()}", created_by)
    fields = {"workspace_id": ws.id, "purchase_order_id": po.id, "return_number": f"PR-{_n()}",
              "created_by": created_by, "status": "pending", "paid": False}
    fields.update(overrides)
    row = PurchaseOrderReturn(**fields)
    db.add(row)
    db.flush()
    return row


def mk_sor(db, ws, created_by, order=None, **overrides):
    so = order if order is not None else mk_so(db, ws, f"SO-SOR-{_n()}", created_by)
    fields = {"workspace_id": ws.id, "sales_order_id": so.id, "return_number": f"SR-{_n()}",
              "created_by": created_by, "status": "pending", "paid": False}
    fields.update(overrides)
    row = SalesOrderReturn(**fields)
    db.add(row)
    db.flush()
    return row


def mk_mled(db, ws, performed_by, **overrides):
    factory = mk_factory(db, ws)
    machine = Machine(workspace_id=ws.id, name=f"M-{_n()}", factory_id=factory.id, is_running=False,
                       is_active=True, is_deleted=False)
    db.add(machine)
    db.flush()
    item = Item(workspace_id=ws.id, name=f"Item-{_n()}", name_normalized=f"item-{_n()}", unit="pcs", is_active=True)
    db.add(item)
    db.flush()
    fields = {
        "workspace_id": ws.id, "machine_id": machine.id, "item_id": item.id, "transaction_type": "issue",
        "quantity": 1, "unit_cost": Decimal("1.00"), "total_cost": Decimal("1.00"), "qty_before": 0, "qty_after": 1,
        "source_type": "manual", "performed_by": performed_by,
    }
    fields.update(overrides)
    row = MachineItemLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "CN" — a return credit note (spec F6): a confirmed receivable INV
# carrying order_type / order_id of the order. The POR(W1) / SOR(W1) row with
# invoice_id = CN.id is built by the card itself (mk_por / mk_sor, order=...).
def mk_cn(db, ws, account, created_by, order_type, order, **overrides):
    fields = {"invoice_type": "receivable", "invoice_status": "confirmed", "order_type": order_type, "order_id": order.id}
    fields.update(overrides)
    return mk_inv(db, ws, account, created_by, **fields)


# Convention "OI = INV(invoice_number='ORD-1')" — the order's own confirmed invoice.
def mk_oi(db, ws, account, created_by, **overrides):
    return mk_inv(db, ws, account, created_by, **{"invoice_number": "ORD-1", **overrides})


# Convention "Freeze texts" (spec F5, revert_to_draft R2a / R3a), compared with ==.
def LOCK(kind):
    return "Invoice is locked — the linked " + kind + " is completed. Correct it with a credit note or return."


CNTXT = "Return credit notes cannot be reverted to draft. Void it and create a new return instead."
RCVTXT = "Cannot revert to draft — goods have been received on the linked order. Record a return instead."
RETTXT = "This return is completed — its goods have already moved. Start a new return or issue a separate credit note."

# xfail reasons for the O1 cards (bug titles from docs/testing/bugs.md).
X2730 = "BUG-2730: a completed order's invoice is not frozen (delete / revert go ahead)"
X2731 = "BUG-2731: void on a completed order's invoice is allowed and cancels its payments"
X2733 = "BUG-2733: a return credit note can be reverted to draft"
X2788 = "BUG-2788: voiding a return credit note leaves its return untouched"
X2736 = "BUG-2736: the revert receiving error advises 'Zero out received quantities first', which can't work"


# Payload shorthand "CRT(k=v, ...)" — account_id defaults to A1 (G1: invoice_amount=0.00
# only while the field still exists on AccountInvoiceCreate).
@pytest.fixture
def CRT(a1):
    def _build(**overrides):
        fields = {"account_id": a1.id, "invoice_type": "payable", "invoice_date": date(2026, 9, 1)}
        fields.update(overrides)
        if "invoice_amount" not in fields and "invoice_amount" in AccountInvoiceCreate.model_fields:
            fields["invoice_amount"] = Decimal("0.00")
        return AccountInvoiceCreate(**fields)
    return _build


# Payload shorthand "UPD(k=v, ...)"
def UPD(**fields):
    return AccountInvoiceUpdate(**fields)


# --------------------------------------------------------------------------- #
# Re-read / query helpers
# --------------------------------------------------------------------------- #

INV_COLS = (
    "workspace_id", "account_id", "invoice_type", "invoice_status", "payment_status",
    "invoice_amount", "paid_amount", "invoice_date", "due_date", "allow_payments",
    "receiving_started", "created_by", "updated_by", "updated_at", "last_synced_at",
    "void_note", "description", "notes", "invoice_number", "vendor_invoice_number",
    "payment_locked_reason", "order_type", "order_id",
)


def reread_inv(db, inv_id):
    db.expire_all()
    return db.execute(select(AccountInvoice).where(AccountInvoice.id == inv_id)).scalar_one()


def reread_inv_or_none(db, inv_id):
    db.expire_all()
    return db.execute(select(AccountInvoice).where(AccountInvoice.id == inv_id)).scalar_one_or_none()


def snap_inv(db, inv_id):
    r = reread_inv(db, inv_id)
    return {c: getattr(r, c) for c in INV_COLS}


def count_invoices(db, ws_id):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(AccountInvoice).where(AccountInvoice.workspace_id == ws_id))


def count_events(db, ws_id):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(InvoiceEvent).where(InvoiceEvent.workspace_id == ws_id))


def events_of(db, inv_id):
    db.expire_all()
    return db.execute(
        select(InvoiceEvent).where(InvoiceEvent.invoice_id == inv_id).order_by(InvoiceEvent.id)
    ).scalars().all()


def assert_events(db, inv_id, expected):
    """expected: list of (event_type, description, performed_by, metadata_json), id order."""
    rows = events_of(db, inv_id)
    actual = [(e.event_type, e.description, e.performed_by, e.metadata_json) for e in rows]
    assert actual == expected


def assert_events_set(db, inv_id, expected):
    """expected: list of (event_type, description, performed_by, metadata_json), any order."""
    rows = events_of(db, inv_id)
    actual = [(e.event_type, e.description, e.performed_by, e.metadata_json) for e in rows]
    assert len(actual) == len(expected), actual
    for exp in expected:
        assert exp in actual, f"{exp} not in {actual}"


def assert_no_events(db, inv_id):
    assert events_of(db, inv_id) == []


# Convention "Session clean": right after the raise, before any re-read,
# expire_all() or savepoint rollback — three asserts.
def assert_session_clean(db):
    assert not db.new
    assert not db.dirty
    assert not db.deleted


def items_of(db, inv_id, *, any_workspace=True):
    db.expire_all()
    q = select(InvoiceItem).where(InvoiceItem.invoice_id == inv_id).order_by(InvoiceItem.id)
    return db.execute(q).scalars().all()


def reread_row(db, model, row_id):
    """Fresh copy of any setup row (orders, return rows, payments) from the database."""
    db.expire_all()
    return db.get(model, row_id)


def ids_list(rows):
    return [r.id for r in rows]


def ids_set(rows):
    return {r.id for r in rows}


# Convention "SQL capture": a before_cursor_execute listener recording statements
# run during the action only.
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

    def locks_table(self, table):
        """Convention "locks the return T": a captured SELECT from table T containing FOR UPDATE."""
        return any(s.lstrip().upper().startswith("SELECT") and table in s and "FOR UPDATE" in s.upper()
                   for s in self.statements)


# =========================================================================== #
# AccountInvoiceManager._get_or_404
# =========================================================================== #

def test_g4_01__happy_confirmed_returned(db, M, w1, a1, u1):
    """AIM-G4-01 — _get_or_404 returns a confirmed invoice of the workspace, unchanged.
    Rules: _get_or_404 R1."""
    c = mk_ci(db, w1, a1, u1.id)
    before = snap_inv(db, c.id)
    result = M._get_or_404(db, c.id, w1.id)
    assert result.id == c.id
    assert result.invoice_status == "confirmed"
    assert snap_inv(db, c.id) == before


def test_g4_02__voided_on_deleted_inactive_account_returned(db, M, w1, a1, u1):
    """AIM-G4-02 — a voided invoice is returned even when its account is deleted+inactive.
    Rules: _get_or_404 R1."""
    a1.is_deleted = True
    a1.is_active = False
    db.flush()
    v = mk_vi(db, w1, a1, u1.id)
    result = M._get_or_404(db, v.id, w1.id)
    assert result.id == v.id
    assert result.invoice_status == "voided"


def test_g4_03__draft_on_inactive_account_returned(db, M, w1, a1, u1):
    """AIM-G4-03 — a draft invoice is returned even when its account is inactive.
    Rules: _get_or_404 R1."""
    a1.is_active = False
    db.flush()
    d = mk_di(db, w1, a1, u1.id)
    result = M._get_or_404(db, d.id, w1.id)
    assert result.id == d.id
    assert result.invoice_status == "draft"


def test_g4_04__not_found_404(db, M, w1):
    """AIM-G4-04 — no invoice with that id raises 404; nothing exists in the workspace.
    Rules: _get_or_404 R2; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M._get_or_404(db, NOID, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"
    assert count_invoices(db, w1.id) == 0


def test_g4_05__other_workspace_404(db, M, w1, w2, ax, u3):
    """AIM-G4-05 — workspace isolation: another workspace's invoice is reported not found.
    Rules: _get_or_404 R3; Errors row 1."""
    other = mk_inv(db, w2, ax, u3.id)
    before = snap_inv(db, other.id)
    with pytest.raises(HTTPException) as exc:
        M._get_or_404(db, other.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Invoice with ID {other.id} not found"
    assert snap_inv(db, other.id) == before


# =========================================================================== #
# AccountInvoiceManager._log_event
# =========================================================================== #

def test_log_01__full_fields_recorded(db, M, w2, ax, u3):
    """AIM-LOG-01 — _log_event writes one event row with all given fields.
    Rules: _log_event R1, R2."""
    i = mk_inv(db, w2, ax, u3.id)
    result = M._log_event(db, i, "note_added", "Note added", performed_by=u3.id, metadata={"k": "v", "n": 2})
    assert result is None
    rows = events_of(db, i.id)
    assert len(rows) == 1
    e = rows[0]
    assert e.id is not None
    assert e.workspace_id == w2.id
    assert e.invoice_id == i.id
    assert e.event_type == "note_added"
    assert e.description == "Note added"
    assert e.performed_by == u3.id
    assert e.metadata_json == {"k": "v", "n": 2}
    assert e.created_at is not None


def test_log_02__defaults_none(db, M, ci):
    """AIM-LOG-02 — performed_by/metadata default to None; workspace matches the invoice.
    Rules: _log_event R1."""
    result = M._log_event(db, ci, "x", "y")
    assert result is None
    rows = events_of(db, ci.id)
    assert len(rows) == 1
    e = rows[0]
    assert e.event_type == "x"
    assert e.description == "y"
    assert e.performed_by is None
    assert e.metadata_json is None
    assert e.workspace_id == ci.workspace_id


def test_log_03__event_type_fifty_chars_ok(db, M, ci):
    """AIM-LOG-03 — a 50-char event_type (column limit) is stored as given.
    Rules: _log_event R1."""
    result = M._log_event(db, ci, "e" * 50, "fifty")
    assert result is None
    rows = events_of(db, ci.id)
    assert len(rows) == 1
    assert rows[0].event_type == "e" * 50


def test_log_04__event_type_fifty_one_chars_raises(db, M, ci):
    """AIM-LOG-04 — a 51-char event_type exceeds the column and raises DataError.
    Rules: _log_event R1."""
    with pytest.raises(DataError):
        with db.begin_nested():
            M._log_event(db, ci, "e" * 51, "fifty-one")
    assert events_of(db, ci.id) == []


def test_log_05__non_json_metadata_raises(db, M, ci):
    """AIM-LOG-05 — a non-JSON-serialisable metadata value raises at flush.
    Rules: _log_event Errors (non-JSON metadata)."""
    with pytest.raises(Exception):
        with db.begin_nested():
            M._log_event(db, ci, "x", "y", metadata={"when": object()})
    assert events_of(db, ci.id) == []


# =========================================================================== #
# AccountInvoiceManager._recalculate_payment_status
# =========================================================================== #

@pytest.mark.parametrize(
    "amount, paid, initial_status, expected",
    [
        pytest.param("100.00", "100.00", "unpaid", "paid", id="AIM-RPS-01"),
        pytest.param("0.00", "0.00", "unpaid", "paid", id="AIM-RPS-02"),
        pytest.param("100.00", "150.00", "partial", "paid", id="AIM-RPS-03"),
        pytest.param("100.00", "99.99", "paid", "partial", id="AIM-RPS-04"),
        pytest.param("100.00", "0.01", "unpaid", "partial", id="AIM-RPS-05"),
        pytest.param("100.00", "0.00", "partial", "unpaid", id="AIM-RPS-06"),
        pytest.param("100.00", "0.00", "overdue", "unpaid", id="AIM-RPS-07"),
    ],
)
def test_rps_01_07__derives_payment_status(M, amount, paid, initial_status, expected):
    """AIM-RPS-01..07 — _recalculate_payment_status derives paid/partial/unpaid; returns None.
    Rules: _recalculate_payment_status R1, R2, R3."""
    transient = AccountInvoice(invoice_amount=Decimal(amount), paid_amount=Decimal(paid), payment_status=initial_status)
    result = M._recalculate_payment_status(transient)
    assert result is None
    assert transient.payment_status == expected


# =========================================================================== #
# AccountInvoiceManager._recalculate_invoice_amount
# =========================================================================== #

def test_ria_01__sum_of_items_and_status_persisted(db, M, w1, a1, u1):
    """AIM-RIA-01 — invoice_amount becomes the item sum; status recomputed; survives flush.
    Rules: _recalculate_invoice_amount R1, R3."""
    d = mk_di(db, w1, a1, u1.id, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"), payment_status="unpaid")
    mk_item(db, d, "100.25", 1)
    mk_item(db, d, "50.50", 2)
    mk_item(db, d, "0.10", 3)
    result = M._recalculate_invoice_amount(db, d)
    db.flush()
    assert result is None
    assert d.invoice_amount == Decimal("150.85")
    assert d.payment_status == "unpaid"
    r = reread_inv(db, d.id)
    assert r.invoice_amount == Decimal("150.85")
    assert r.payment_status == "unpaid"


def test_ria_02__ignores_other_workspace_items(db, M, w1, w2, a1, u1):
    """AIM-RIA-02 — items sharing invoice_id in another workspace are ignored.
    Rules: _recalculate_invoice_amount R1."""
    d = mk_di(db, w1, a1, u1.id)
    mk_item(db, d, "200.00", 1)
    mk_item(db, d, "999.00", 1, workspace_id=w2.id)
    j = mk_di(db, w1, a1, u1.id)
    mk_item(db, j, "50.00", 1)
    result = M._recalculate_invoice_amount(db, d)
    assert result is None
    assert d.invoice_amount == Decimal("200.00")
    assert reread_inv(db, j.id).invoice_amount == Decimal("1000.00")


def test_ria_03__no_items_zero_and_paid(db, M, w1, a1, u1):
    """AIM-RIA-03 — no items -> amount 0.00, which makes paid(0) >= amount(0) -> paid.
    Rules: _recalculate_invoice_amount R2, R3."""
    d = mk_di(db, w1, a1, u1.id, invoice_amount=Decimal("500.00"), paid_amount=Decimal("0.00"), payment_status="unpaid")
    result = M._recalculate_invoice_amount(db, d)
    assert result is None
    assert d.invoice_amount == Decimal("0.00")
    assert d.payment_status == "paid"


def test_ria_04__partial_after_recalc(db, M, w1, a1, u1):
    """AIM-RIA-04 — amount from items with paid < amount -> partial.
    Rules: _recalculate_invoice_amount R3."""
    d = mk_di(db, w1, a1, u1.id, paid_amount=Decimal("100.00"), payment_status="unpaid")
    mk_item(db, d, "300.00", 1)
    result = M._recalculate_invoice_amount(db, d)
    assert result is None
    assert d.invoice_amount == Decimal("300.00")
    assert d.payment_status == "partial"


# =========================================================================== #
# AccountInvoiceManager.create_invoice
# =========================================================================== #

def test_c_01__happy_path_minimal(db, M, w1, a1, u1, CRT):
    """AIM-C-01 — creating a minimal invoice stores draft defaults and logs one event.
    Rules: create_invoice R5, R6, R7, R8."""
    created = M.create_invoice(db, CRT(), w1.id, u1.id)
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.workspace_id == w1.id
    assert r.account_id == a1.id
    assert r.invoice_type == "payable"
    assert r.invoice_date == date(2026, 9, 1)
    assert r.invoice_status == "draft"
    assert r.payment_status == "unpaid"
    assert r.paid_amount == Decimal("0.00")
    assert r.invoice_amount == Decimal("0.00")
    assert r.receiving_started is False
    assert r.allow_payments is True
    assert r.created_by == u1.id
    assert r.created_at is not None
    for col in ("updated_by", "updated_at", "last_synced_at", "void_note", "due_date",
                "description", "notes", "invoice_number", "vendor_invoice_number",
                "order_type", "order_id", "payment_locked_reason"):
        assert getattr(r, col) is None, col
    assert_events(db, created.id, [
        ("created", "Draft invoice created", u1.id, {"invoice_type": "payable", "account_id": a1.id}),
    ])


def test_c_02__optional_fields_and_events(db, M, w1, a2, u2, CRT):
    """AIM-C-02 — optional fields sent at create are stored as given; event names the actor.
    Rules: create_invoice R5, R6, R8."""
    created = M.create_invoice(
        db,
        CRT(account_id=a2.id, invoice_type="receivable", due_date=date(2026, 10, 15),
            description="Desc", notes="Notes", invoice_number="INV-77",
            vendor_invoice_number="V-77", payment_locked_reason="Hold", allow_payments=False),
        w1.id, u2.id,
    )
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.account_id == a2.id
    assert r.invoice_type == "receivable"
    assert r.due_date == date(2026, 10, 15)
    assert r.description == "Desc"
    assert r.notes == "Notes"
    assert r.invoice_number == "INV-77"
    assert r.vendor_invoice_number == "V-77"
    assert r.payment_locked_reason == "Hold"
    assert r.allow_payments is False
    assert r.created_by == u2.id
    assert r.invoice_status == "draft"
    assert_events(db, created.id, [
        ("created", "Draft invoice created", u2.id, {"invoice_type": "receivable", "account_id": a2.id}),
    ])


def test_c_03__account_not_found_404(db, M, w1, a1, a2, u1, CRT):
    """AIM-C-03 — a nonexistent account 404s and writes nothing.
    Rules: create_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(account_id=NOID), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Account with ID 999999 not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


def test_c_04__account_other_workspace_404(db, M, w1, w2, ax, u1, CRT):
    """AIM-C-04 — an account of another workspace is reported not found; nothing written anywhere.
    Rules: create_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(account_id=ax.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ax.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_invoices(db, w2.id) == 0
    assert count_events(db, w1.id) == 0
    assert count_events(db, w2.id) == 0


def test_c_05__deleted_account_rejected(db, M, w1, w2, a1, u1, CRT):
    """AIM-C-05 — a soft-deleted account is rejected before the active/allow checks.
    Rules: create_invoice R2; Errors row 2."""
    a1.is_deleted = True
    a1.is_active = False
    a1.allow_invoices = False
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot create invoice for deleted account"
    assert count_invoices(db, w1.id) == 0
    assert count_invoices(db, w2.id) == 0
    assert count_events(db, w1.id) == 0
    assert count_events(db, w2.id) == 0


def test_c_06__inactive_account_rejected(db, M, w1, w2, a1, u1, CRT):
    """AIM-C-06 — a live but inactive account is rejected.
    Rules: create_invoice R3; Errors row 3."""
    a1.is_active = False
    a1.allow_invoices = False
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot create invoice for inactive account"
    assert count_invoices(db, w1.id) == 0
    assert count_invoices(db, w2.id) == 0
    assert count_events(db, w1.id) == 0
    assert count_events(db, w2.id) == 0


def test_c_07__allow_invoices_false_forbidden(db, M, w1, w2, a1, u1, CRT):
    """AIM-C-07 — a live, active account with allow_invoices=False is forbidden.
    Rules: create_invoice R4; Errors row 4."""
    a1.allow_invoices = False
    db.flush()
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(), w1.id, u1.id)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Invoices are not allowed for this account"
    assert count_invoices(db, w1.id) == 0
    assert count_invoices(db, w2.id) == 0
    assert count_events(db, w1.id) == 0
    assert count_events(db, w2.id) == 0


def test_c_08__linked_order_stored(db, M, w1, a1, u1, CRT):
    """AIM-C-08 — order_type/order_id of a real, live, same-workspace order are stored.
    Rules: create_invoice R9a, R9b."""
    p1 = mk_po(db, w1, "PO-1001", u1.id)
    created = M.create_invoice(db, CRT(order_type="purchase_order", order_id=p1.id), w1.id, u1.id)
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.order_type == "purchase_order"
    assert r.order_id == p1.id
    assert r.invoice_status == "draft"


def test_c_09__known_order_types_build(CRT):
    """AIM-C-09 — each of the four known order types builds unchanged (schema target).
    Rules: create_invoice R9a."""
    for t in ("purchase_order", "expense_order", "sales_order", "work_order"):
        data = CRT(order_type=t, order_id=1)
        assert data.order_type == t
        assert data.order_id == 1


@pytest.mark.xfail(strict=True, reason="BUG-624: order_type stored as typed instead of trimmed + lower-cased")
def test_c_10__order_type_not_normalized(CRT):
    """AIM-C-10 — order_type should be trimmed + lower-cased; today it is stored as typed.
    Rules: create_invoice R9a [BUG-624]."""
    data = CRT(order_type="  Purchase_Order ", order_id=1)
    assert data.order_type == "purchase_order"


@pytest.mark.xfail(strict=True, reason="BUG-624: order_type accepts any text instead of the four known values")
def test_c_11__unknown_order_type_accepted(CRT):
    """AIM-C-11 — an unrecognised order_type should 422; today it is accepted.
    Rules: create_invoice R9a [BUG-624]; Errors row 5."""
    with pytest.raises(ValidationError):
        CRT(order_type="banana", order_id=1)


@pytest.mark.xfail(strict=True, reason="BUG-625: order_id is never validated to exist")
def test_c_12__nonexistent_order_id_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-12 — a nonexistent order_id should 404; today it is stored unchecked.
    Rules: create_invoice R9b [BUG-625]; Errors row 7."""
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="purchase_order", order_id=NOID), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order with ID 999999 not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-625: order_id from another workspace is never validated")
def test_c_13__other_workspace_order_id_accepted(db, M, w1, w2, a1, u1, CRT):
    """AIM-C-13 — an order_id belonging to another workspace's order should 404; today unchecked.
    Rules: create_invoice R9b [BUG-625]; Errors row 7."""
    pw = mk_po(db, w2, "PO-9001", u1.id)
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="purchase_order", order_id=pw.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {pw.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-625: a soft-deleted order's id is never validated")
def test_c_14__deleted_order_id_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-14 — order_id of a soft-deleted order should 404; today unchecked.
    Rules: create_invoice R9b [BUG-625]; Errors row 7."""
    pd = mk_po(db, w1, "PO-1002", u1.id, voided=True)
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="purchase_order", order_id=pd.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {pd.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-625: order_id is never validated against order_type")
def test_c_15__order_id_wrong_type_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-15 — order_id must belong to the given order_type; today the type is not checked.
    Rules: create_invoice R9b [BUG-625]; Errors row 7."""
    p1 = mk_po(db, w1, "PO-1001", u1.id)
    assert db.execute(select(ExpenseOrder).where(ExpenseOrder.id == p1.id)).scalar_one_or_none() is None
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="expense_order", order_id=p1.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {p1.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-627: AccountInvoiceCreate still has an invoice_amount field")
def test_c_16__create_schema_has_no_amount_field():
    """AIM-C-16 — invoice_amount should not be a field of AccountInvoiceCreate; today it still is.
    Rules: create_invoice R9 [BUG-627]."""
    assert "invoice_amount" not in AccountInvoiceCreate.model_fields


@pytest.mark.xfail(strict=True, reason="BUG-627: invoice_amount is still required by AccountInvoiceCreate")
def test_c_17__create_without_amount(db, M, w1, a1, u1):
    """AIM-C-17 — a draft should start at 0.00 without a client amount; today the field is required.
    Rules: create_invoice R9 [BUG-627]."""
    data = AccountInvoiceCreate(account_id=a1.id, invoice_type="payable", invoice_date=date(2026, 9, 1))
    created = M.create_invoice(db, data, w1.id, u1.id)
    r = reread_inv(db, created.id)
    assert r.invoice_amount == Decimal("0.00")
    assert r.payment_status == "unpaid"


@pytest.mark.xfail(strict=True, reason="BUG-627: a client invoice_amount is accepted instead of rejected")
def test_c_18__client_amount_rejected():
    """AIM-C-18 — a sent invoice_amount should 422; today it is accepted.
    Rules: create_invoice R9 [BUG-627]; Errors row 6."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceCreate(account_id=1, invoice_type="payable", invoice_date=date(2026, 9, 1),
                              invoice_amount=Decimal("1000.00"))
    assert any(e["loc"] == ("invoice_amount",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-625: order_id alone is accepted instead of requiring order_type too")
def test_c_19__order_id_without_type_rejected(CRT):
    """AIM-C-19 — order_id alone should 422 naming order_type; today it is accepted.
    Rules: create_invoice R9c [BUG-625]; Errors row 8."""
    with pytest.raises(ValidationError) as exc:
        CRT(order_id=5)
    assert any(e["loc"] == ("order_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-625: order_type alone is accepted instead of requiring order_id too")
def test_c_20__order_type_without_id_rejected(CRT):
    """AIM-C-20 — order_type alone should 422 naming order_id; today it is accepted.
    Rules: create_invoice R9c [BUG-625]; Errors row 8."""
    with pytest.raises(ValidationError) as exc:
        CRT(order_type="purchase_order")
    assert any(e["loc"] == ("order_id",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-625: an explicit null order_id with order_type is accepted")
def test_c_21__order_type_with_null_id_rejected(CRT):
    """AIM-C-21 — order_type with explicit null order_id should 422 naming order_id.
    Rules: create_invoice R9c [BUG-625]; Errors row 8."""
    with pytest.raises(ValidationError) as exc:
        CRT(order_type="purchase_order", order_id=None)
    assert any(e["loc"] == ("order_id",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-625: a voided (non-live) expense order's id is never validated")
def test_c_22__voided_expense_order_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-22 — order_id of a voided (non-live) expense order should 404; today unchecked.
    Rules: create_invoice R9b, R9d [BUG-625]; Errors row 7."""
    ed = mk_eo(db, w1, "EXP-1002", u1.id, voided=True)
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="expense_order", order_id=ed.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {ed.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-625: a soft-deleted (non-live) work order's id is never validated")
def test_c_23__soft_deleted_work_order_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-23 — order_id of a soft-deleted work order should 404; today unchecked.
    Rules: create_invoice R9b, R9d [BUG-625]; Errors row 7."""
    wd = mk_wo(db, w1, "WO-1002", is_deleted=True)
    assert wd.status != "VOIDED"
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="work_order", order_id=wd.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {wd.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-625: a work order with status=VOIDED's id is never validated")
def test_c_24__voided_status_work_order_accepted(db, M, w1, a1, u1, CRT):
    """AIM-C-24 — order_id of a work order with status 'VOIDED' should 404; today unchecked.
    Rules: create_invoice R9b, R9d [BUG-625]; Errors row 7."""
    wv = mk_wo(db, w1, "WO-1003", is_deleted=False, status="VOIDED")
    with pytest.raises(HTTPException) as exc:
        M.create_invoice(db, CRT(order_type="work_order", order_id=wv.id), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {wv.id} not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


def test_c_25__live_expense_order_stored(db, M, w1, a1, u1, CRT):
    """AIM-C-25 — order_type/order_id of a live (voided=False) expense order are stored.
    Rules: create_invoice R9b, R9d."""
    e1 = mk_eo(db, w1, "EXP-1001", u1.id)
    created = M.create_invoice(db, CRT(order_type="expense_order", order_id=e1.id), w1.id, u1.id)
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.order_type == "expense_order"
    assert r.order_id == e1.id
    assert r.invoice_status == "draft"
    assert_events(db, r.id, [
        ("created", "Draft invoice created", u1.id, {"invoice_type": "payable", "account_id": a1.id}),
    ])


def test_c_26__live_work_order_stored(db, M, w1, a1, u1, CRT):
    """AIM-C-26 — order_type/order_id of a live (is_deleted=False, status != VOIDED) work order are stored.
    Rules: create_invoice R9b, R9d."""
    wo1 = mk_wo(db, w1, "WO-1001")
    assert wo1.is_deleted is False
    assert wo1.status != "VOIDED"
    created = M.create_invoice(db, CRT(order_type="work_order", order_id=wo1.id), w1.id, u1.id)
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.order_type == "work_order"
    assert r.order_id == wo1.id
    assert r.invoice_status == "draft"


def test_c_27__sales_order_stored(db, M, w1, a1, u1, CRT):
    """AIM-C-27 — order_type/order_id of a sales order (no liveness flag) are stored.
    Rules: create_invoice R9b, R9d."""
    s1 = mk_so(db, w1, "SO-1001", u1.id)
    created = M.create_invoice(db, CRT(order_type="sales_order", order_id=s1.id), w1.id, u1.id)
    assert created.id is not None
    r = reread_inv(db, created.id)
    assert r.order_type == "sales_order"
    assert r.order_id == s1.id
    assert r.invoice_status == "draft"


# =========================================================================== #
# AccountInvoiceManager.get_invoice
# =========================================================================== #

def test_gi_01__happy_returns_draft(db, M, w1, a1, u1):
    """AIM-GI-01 — get_invoice returns the invoice of the workspace.
    Rules: get_invoice R1."""
    d = mk_di(db, w1, a1, u1.id)
    result = M.get_invoice(db, d.id, w1.id)
    assert result.id == d.id


def test_gi_02__other_workspace_404(db, M, w1, w2, ax, u3):
    """AIM-GI-02 — workspace isolation: another workspace's invoice 404s.
    Rules: get_invoice R1."""
    other = mk_inv(db, w2, ax, u3.id)
    with pytest.raises(HTTPException) as exc:
        M.get_invoice(db, other.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Invoice with ID {other.id} not found"


def test_gi_03__not_found_404(db, M, w1):
    """AIM-GI-03 — no invoice with that id 404s.
    Rules: get_invoice R1."""
    with pytest.raises(HTTPException) as exc:
        M.get_invoice(db, NOID, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


# =========================================================================== #
# AccountInvoiceManager.list_invoices (shared filters R1-R14)
# =========================================================================== #

def test_l_01__workspace_isolation(db, M, w1, w2, a1, ax, u1, u3):
    """AIM-L-01 — only the workspace's invoices are returned.
    Rules: list_invoices R1."""
    i1 = inv(db, w1, a1, u1)
    mk_inv(db, w2, ax, u3.id)
    result = M.list_invoices(db, w1.id)
    assert ids_list(result) == [i1.id]


def test_l_02__deleted_account_excluded_inactive_included(db, M, w1, a1, a2, u1):
    """AIM-L-02 — a soft-deleted account's invoices are excluded; an inactive account's are not.
    Rules: list_invoices R2."""
    i1 = inv(db, w1, a1, u1)
    a2.is_active = False
    db.flush()
    i2 = inv(db, w1, a2, u1)
    a3 = mk_account(db, w1, "Gamma", is_deleted=True)
    inv(db, w1, a3, u1)
    result = M.list_invoices(db, w1.id)
    assert ids_set(result) == {i1.id, i2.id}


def test_l_03__all_statuses_included_by_default(db, M, w1, a1, u1):
    """AIM-L-03 — draft, confirmed and voided invoices are all returned without a status filter.
    Rules: list_invoices R3."""
    i1 = inv(db, w1, a1, u1, invoice_status="draft")
    i2 = inv(db, w1, a1, u1, invoice_status="confirmed")
    i3 = inv(db, w1, a1, u1, invoice_status="voided")
    result = M.list_invoices(db, w1.id)
    assert ids_set(result) == {i1.id, i2.id, i3.id}


def test_l_04__account_id_filter(db, M, w1, a1, a2, u1):
    """AIM-L-04 — account_id filters to that account's invoices.
    Rules: list_invoices R4."""
    inv(db, w1, a1, u1)
    i2 = inv(db, w1, a2, u1)
    result = M.list_invoices(db, w1.id, account_id=a2.id)
    assert ids_list(result) == [i2.id]


def test_l_05__account_id_zero_is_real_filter(db, M, w1, a1, a2, u1):
    """AIM-L-05 — account_id=0 is a real filter (no account has id 0) -> empty.
    Rules: list_invoices R4."""
    inv(db, w1, a1, u1)
    inv(db, w1, a2, u1)
    assert M.list_invoices(db, w1.id, account_id=0) == []


def test_l_06__invoice_type_filter(db, M, w1, a1, u1):
    """AIM-L-06 — invoice_type filters exactly.
    Rules: list_invoices R5."""
    i1 = inv(db, w1, a1, u1, invoice_type="payable")
    inv(db, w1, a1, u1, invoice_type="receivable")
    result = M.list_invoices(db, w1.id, invoice_type="payable")
    assert ids_list(result) == [i1.id]


def test_l_07__invoice_type_case_sensitive(db, M, w1, a1, u1):
    """AIM-L-07 — invoice_type matching is case-sensitive.
    Rules: list_invoices R5."""
    inv(db, w1, a1, u1, invoice_type="payable")
    inv(db, w1, a1, u1, invoice_type="receivable")
    assert M.list_invoices(db, w1.id, invoice_type="Payable") == []


def test_l_08__invoice_type_empty_is_no_filter(db, M, w1, a1, u1):
    """AIM-L-08 — invoice_type="" applies no filter.
    Rules: list_invoices R5."""
    i1 = inv(db, w1, a1, u1, invoice_type="payable")
    i2 = inv(db, w1, a1, u1, invoice_type="receivable")
    result = M.list_invoices(db, w1.id, invoice_type="")
    assert ids_set(result) == {i1.id, i2.id}


def test_l_09__payment_status_filter(db, M, w1, a1, u1):
    """AIM-L-09 — payment_status filters exactly.
    Rules: list_invoices R5."""
    inv(db, w1, a1, u1, payment_status="unpaid")
    i2 = inv(db, w1, a1, u1, payment_status="partial", paid_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, payment_status="paid", paid_amount=Decimal("1000.00"))
    result = M.list_invoices(db, w1.id, payment_status="partial")
    assert ids_list(result) == [i2.id]


def test_l_10__invoice_status_filter(db, M, w1, a1, u1):
    """AIM-L-10 — invoice_status filters exactly.
    Rules: list_invoices R5."""
    inv(db, w1, a1, u1, invoice_status="draft")
    inv(db, w1, a1, u1, invoice_status="confirmed")
    i3 = inv(db, w1, a1, u1, invoice_status="voided")
    result = M.list_invoices(db, w1.id, invoice_status="voided")
    assert ids_list(result) == [i3.id]


def test_l_11__unknown_invoice_status_returns_nothing(db, M, w1, a1, u1):
    """AIM-L-11 — an unknown invoice_status value matches nothing.
    Rules: list_invoices R5."""
    inv(db, w1, a1, u1, invoice_status="draft")
    inv(db, w1, a1, u1, invoice_status="confirmed")
    assert M.list_invoices(db, w1.id, invoice_status="bogus") == []


def test_l_12__invoice_date_bounds_inclusive(db, M, w1, a1, u1):
    """AIM-L-12 — invoice_date_from/to are inclusive bounds; order date desc, id desc.
    Rules: list_invoices R6."""
    inv(db, w1, a1, u1, invoice_date=date(2026, 3, 1))
    i2 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 2))
    i3 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 3))
    inv(db, w1, a1, u1, invoice_date=date(2026, 3, 4))
    result = M.list_invoices(db, w1.id, invoice_date_from=date(2026, 3, 2), invoice_date_to=date(2026, 3, 3))
    assert ids_list(result) == [i3.id, i2.id]


def test_l_13__due_date_from_excludes_null(db, M, w1, a1, u1):
    """AIM-L-13 — due_date_from excludes invoices without a due date.
    Rules: list_invoices R7."""
    inv(db, w1, a1, u1, due_date=date(2026, 3, 1))
    i2 = inv(db, w1, a1, u1, due_date=date(2026, 3, 2))
    i3 = inv(db, w1, a1, u1, due_date=date(2026, 3, 3))
    inv(db, w1, a1, u1, due_date=None)
    result = M.list_invoices(db, w1.id, due_date_from=date(2026, 3, 2))
    assert ids_set(result) == {i2.id, i3.id}


def test_l_14__due_date_to_excludes_null(db, M, w1, a1, u1):
    """AIM-L-14 — due_date_to excludes invoices without a due date.
    Rules: list_invoices R7."""
    i1 = inv(db, w1, a1, u1, due_date=date(2026, 3, 1))
    i2 = inv(db, w1, a1, u1, due_date=date(2026, 3, 2))
    inv(db, w1, a1, u1, due_date=date(2026, 3, 3))
    inv(db, w1, a1, u1, due_date=None)
    result = M.list_invoices(db, w1.id, due_date_to=date(2026, 3, 2))
    assert ids_set(result) == {i1.id, i2.id}


def test_l_15__amount_bounds_inclusive(db, M, w1, a1, u1):
    """AIM-L-15 — amount_min/max are inclusive bounds on invoice_amount.
    Rules: list_invoices R8."""
    inv(db, w1, a1, u1, invoice_amount=Decimal("99.99"))
    i2 = inv(db, w1, a1, u1, invoice_amount=Decimal("100.00"))
    i3 = inv(db, w1, a1, u1, invoice_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, invoice_amount=Decimal("200.01"))
    result = M.list_invoices(db, w1.id, amount_min=Decimal("100.00"), amount_max=Decimal("200.00"))
    assert ids_set(result) == {i2.id, i3.id}


def test_l_16__amount_max_zero_is_real_bound(db, M, w1, a1, u1):
    """AIM-L-16 — amount_max=0 is a real bound, not "no filter".
    Rules: list_invoices R8."""
    i1 = inv(db, w1, a1, u1, invoice_amount=Decimal("0.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_amount=Decimal("50.00"))
    result = M.list_invoices(db, w1.id, amount_max=Decimal("0"))
    assert ids_list(result) == [i1.id]


def test_l_17__invoice_number_search_case_insensitive_middle(db, M, w1, a1, u1):
    """AIM-L-17 — invoice_number_search matches a case-insensitive substring anywhere.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="INV-2026-0042")
    inv(db, w1, a1, u1, invoice_number="INV-2026-0100")
    result = M.list_invoices(db, w1.id, invoice_number_search="v-2026-004")
    assert ids_list(result) == [i1.id]


def test_l_18__invoice_number_search_trimmed(db, M, w1, a1, u1):
    """AIM-L-18 — invoice_number_search is trimmed before matching.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="INV-2026-0042")
    inv(db, w1, a1, u1, invoice_number="INV-2026-0100")
    result = M.list_invoices(db, w1.id, invoice_number_search="  v-2026-0042  ")
    assert ids_list(result) == [i1.id]


def test_l_19__vendor_invoice_number_matches(db, M, w1, a1, u1):
    """AIM-L-19 — invoice_number_search also matches vendor_invoice_number.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number=None, vendor_invoice_number="VND-ABC-9")
    inv(db, w1, a1, u1, invoice_number=None, vendor_invoice_number="VND-XYZ-1")
    result = M.list_invoices(db, w1.id, invoice_number_search="abc")
    assert ids_list(result) == [i1.id]


def test_l_20__matches_linked_purchase_order_number(db, M, w1, a1, u1):
    """AIM-L-20 — invoice_number_search matches a linked purchase order's number.
    Rules: list_invoices R9."""
    p = mk_po(db, w1, "PO-7788", u1.id)
    i1 = inv(db, w1, a1, u1, order_type="purchase_order", order_id=p.id, invoice_number="ALPHA")
    inv(db, w1, a1, u1, invoice_number="BRAVO")
    result = M.list_invoices(db, w1.id, invoice_number_search="o-7788")
    assert ids_list(result) == [i1.id]


def test_l_21__matches_linked_expense_order_number(db, M, w1, a1, u1):
    """AIM-L-21 — invoice_number_search matches a linked expense order's number.
    Rules: list_invoices R9."""
    e = mk_eo(db, w1, "EXP-5566", u1.id)
    i1 = inv(db, w1, a1, u1, order_type="expense_order", order_id=e.id)
    inv(db, w1, a1, u1)
    result = M.list_invoices(db, w1.id, invoice_number_search="xp-55")
    assert ids_list(result) == [i1.id]


def test_l_22__matches_reverse_linked_sales_order_number(db, M, w1, a1, u1):
    """AIM-L-22 — invoice_number_search matches via a sales order whose invoice_id points back.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a1, u1)
    mk_so(db, w1, "SO-3344", u1.id, invoice_id=i1.id)
    result = M.list_invoices(db, w1.id, invoice_number_search="so-33")
    assert ids_list(result) == [i1.id]


def test_l_23__matches_reverse_linked_work_order_number(db, M, w1, a1, u1):
    """AIM-L-23 — invoice_number_search matches via a work order whose invoice_id points back.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a1, u1)
    mk_wo(db, w1, "WO-2211", invoice_id=i1.id)
    result = M.list_invoices(db, w1.id, invoice_number_search="wo-22")
    assert ids_list(result) == [i1.id]


def test_l_24__order_search_workspace_isolated(db, M, w1, w2, a1, u1):
    """AIM-L-24 — a same-id purchase order in another workspace never matches.
    Rules: list_invoices R9."""
    pw = mk_po(db, w2, "PO-9911", u1.id)
    assert db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == pw.id, PurchaseOrder.workspace_id == w1.id)
    ).scalar_one_or_none() is None
    inv(db, w1, a1, u1, order_type="purchase_order", order_id=pw.id, invoice_number="ALPHA")
    assert M.list_invoices(db, w1.id, invoice_number_search="o-9911") == []


def test_l_25__percent_is_literal(db, M, w1, a1, u1):
    """AIM-L-25 — "%" in invoice_number_search matches a literal percent sign.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="A%B")
    inv(db, w1, a1, u1, invoice_number="AXB")
    result = M.list_invoices(db, w1.id, invoice_number_search="%")
    assert ids_list(result) == [i1.id]


def test_l_26__underscore_is_literal(db, M, w1, a1, u1):
    """AIM-L-26 — "_" in invoice_number_search matches a literal underscore.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="A_B")
    inv(db, w1, a1, u1, invoice_number="AXB")
    result = M.list_invoices(db, w1.id, invoice_number_search="_")
    assert ids_list(result) == [i1.id]


def test_l_27__backslash_is_literal(db, M, w1, a1, u1):
    """AIM-L-27 — a single backslash in invoice_number_search matches a literal backslash.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="A\\B")
    inv(db, w1, a1, u1, invoice_number="AB")
    result = M.list_invoices(db, w1.id, invoice_number_search="\\")
    assert ids_list(result) == [i1.id]


def test_l_28__empty_search_is_no_filter(db, M, w1, a1, u1):
    """AIM-L-28 — invoice_number_search="" applies no filter.
    Rules: list_invoices R9."""
    i1 = inv(db, w1, a1, u1, invoice_number="A-1")
    i2 = inv(db, w1, a1, u1, invoice_number="B-2")
    i3 = inv(db, w1, a1, u1, invoice_number=None)
    result = M.list_invoices(db, w1.id, invoice_number_search="")
    assert ids_set(result) == {i1.id, i2.id, i3.id}


@pytest.mark.xfail(strict=True, reason="BUG-637: a whitespace-only search trims to an empty pattern that matches almost nothing")
def test_l_29__whitespace_search_should_be_no_filter(db, M, w1, a1, u1):
    """AIM-L-29 — a whitespace-only search should behave like no filter; today it empties the list.
    Rules: list_invoices R9a [BUG-637]."""
    i1 = inv(db, w1, a1, u1, invoice_number="A-1")
    i2 = inv(db, w1, a1, u1, invoice_number="B-2")
    i3 = inv(db, w1, a1, u1, invoice_number=None)
    result = M.list_invoices(db, w1.id, invoice_number_search="   ")
    assert ids_set(result) == {i1.id, i2.id, i3.id}


def test_l_30__all_digit_search_matches_by_id(db, M, w1, a1, u1):
    """AIM-L-30 — an all-digit search also matches the invoice with that id.
    Rules: list_invoices R10."""
    inv(db, w1, a1, u1, invoice_number="ALPHA")
    i2 = inv(db, w1, a1, u1, invoice_number="BRAVO")
    result = M.list_invoices(db, w1.id, invoice_number_search=str(i2.id))
    assert ids_list(result) == [i2.id]


def test_l_31__digit_search_trimmed_before_id_check(db, M, w1, a1, u1):
    """AIM-L-31 — the digit-only check happens after trimming.
    Rules: list_invoices R10."""
    inv(db, w1, a1, u1, invoice_number="ALPHA")
    i2 = inv(db, w1, a1, u1, invoice_number="BRAVO")
    result = M.list_invoices(db, w1.id, invoice_number_search=f"  {i2.id}  ")
    assert ids_list(result) == [i2.id]


def test_l_32__not_all_digits_no_id_match(db, M, w1, a1, u1):
    """AIM-L-32 — a trailing non-digit character disables the id-match shortcut.
    Rules: list_invoices R10."""
    inv(db, w1, a1, u1, invoice_number="ALPHA")
    i2 = inv(db, w1, a1, u1, invoice_number="BRAVO")
    assert M.list_invoices(db, w1.id, invoice_number_search=f"{i2.id}x") == []


@pytest.mark.xfail(strict=True, reason="BUG-622: a non-ASCII digit crashes the digit-only check with ValueError")
def test_l_33__superscript_digit_no_crash(db, M, w1, a1, u1):
    """AIM-L-33 — a superscript digit should not raise; today it crashes.
    Rules: list_invoices R10 [BUG-622]."""
    inv(db, w1, a1, u1, invoice_number="ALPHA")
    inv(db, w1, a1, u1, invoice_number="BRAVO")
    assert M.list_invoices(db, w1.id, invoice_number_search="²") == []


@pytest.mark.xfail(strict=True, reason="BUG-622: Unicode isdigit() lets Arabic-Indic digits match by id")
def test_l_34__arabic_indic_digits_should_not_match_id(db, M, w1, a1, u1):
    """AIM-L-34 — Arabic-Indic digits should never trigger the id-match shortcut.
    Rules: list_invoices R10 [BUG-622]."""
    inv(db, w1, a1, u1, invoice_number="ALPHA")
    i2 = inv(db, w1, a1, u1, invoice_number="BRAVO")
    arabic = "".join(chr(0x0660 + int(ch)) for ch in str(i2.id))
    assert M.list_invoices(db, w1.id, invoice_number_search=arabic) == []


def test_l_35__account_name_search_case_insensitive(db, M, w1, a1, a2, u1):
    """AIM-L-35 — account_name_search matches a case-insensitive substring.
    Rules: list_invoices R11."""
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a2, u1)
    result = M.list_invoices(db, w1.id, account_name_search="ME TR")
    assert ids_list(result) == [i1.id]


@pytest.mark.xfail(strict=True, reason="BUG-622: account_name_search '%' is an unescaped wildcard matching every account")
def test_l_36__account_name_percent_literal(db, M, w1, a1, a2, u1):
    """AIM-L-36 — "%" in account_name_search should match a literal percent sign only.
    Rules: list_invoices R11 [BUG-622]."""
    a1.name = "100% Cotton"
    db.flush()
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a2, u1)
    result = M.list_invoices(db, w1.id, account_name_search="%")
    assert ids_list(result) == [i1.id]


@pytest.mark.xfail(strict=True, reason="BUG-622: account_name_search '_' is an unescaped wildcard matching every account")
def test_l_37__account_name_underscore_literal(db, M, w1, a1, a2, u1):
    """AIM-L-37 — "_" in account_name_search should match a literal underscore only.
    Rules: list_invoices R11 [BUG-622]."""
    a1.name = "Dhaka_Mills"
    db.flush()
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a2, u1)
    result = M.list_invoices(db, w1.id, account_name_search="_")
    assert ids_list(result) == [i1.id]


@pytest.mark.xfail(strict=True, reason="BUG-622: account_name_search backslash is not escaped (unmatched)")
def test_l_38__account_name_backslash_literal(db, M, w1, a1, a2, u1):
    """AIM-L-38 — a literal backslash in the account name should be matched by a backslash search.
    Rules: list_invoices R11 [BUG-622]."""
    a1.name = "Back\\Slash"
    db.flush()
    i1 = inv(db, w1, a1, u1)
    inv(db, w1, a2, u1)
    result = M.list_invoices(db, w1.id, account_name_search="\\")
    assert ids_list(result) == [i1.id]


def test_l_39__account_and_type_filters_combine(db, M, w1, a1, a2, u1):
    """AIM-L-39 — account_id and invoice_type combine with AND.
    Rules: list_invoices R12."""
    i1 = inv(db, w1, a1, u1, invoice_type="payable")
    inv(db, w1, a1, u1, invoice_type="receivable")
    inv(db, w1, a2, u1, invoice_type="payable")
    result = M.list_invoices(db, w1.id, account_id=a1.id, invoice_type="payable")
    assert ids_list(result) == [i1.id]


def test_l_40__order_date_desc_then_id_desc(db, M, w1, a1, u1):
    """AIM-L-40 — default order is invoice_date desc, then id desc.
    Rules: list_invoices R13."""
    i1 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 1))
    i2 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 5))
    i3 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 5))
    result = M.list_invoices(db, w1.id)
    assert ids_list(result) == [i3.id, i2.id, i1.id]


def test_l_41__skip_and_limit(db, M, w1, a1, u1):
    """AIM-L-41 — skip/limit window the ordered results.
    Rules: list_invoices R14."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 3, d)) for d in range(1, 6)]
    result = M.list_invoices(db, w1.id, skip=1, limit=2)
    assert ids_list(result) == [rows[3].id, rows[2].id]


def test_l_42__default_limit_100(db, M, w1, a1, u1):
    """AIM-L-42 — the default limit caps at 100, newest first.
    Rules: list_invoices R14."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 1, 1)) for _ in range(1)]
    rows += [inv(db, w1, a1, u1, invoice_date=date(2026, 1, 1) + timedelta(days=n)) for n in range(1, 101)]
    result = M.list_invoices(db, w1.id)
    assert len(result) == 100
    assert rows[0].id not in ids_list(result)
    assert result[0].invoice_date == date(2026, 4, 11)


def test_l_43__filter_before_paging(db, M, w1, a1, u1):
    """AIM-L-43 — filtering happens before paging.
    Rules: list_invoices R12, R14."""
    payables = [inv(db, w1, a1, u1, invoice_type="payable", invoice_date=date(2026, 3, d)) for d in (1, 2, 3)]
    for d in (4, 5, 6):
        inv(db, w1, a1, u1, invoice_type="receivable", invoice_date=date(2026, 3, d))
    result = M.list_invoices(db, w1.id, invoice_type="payable", limit=2)
    assert ids_list(result) == [payables[2].id, payables[1].id]


def test_l_44__empty_status_strings_are_no_filter(db, M, w1, a1, u1):
    """AIM-L-44 — empty payment_status/invoice_status strings apply no filter on either column.
    Rules: list_invoices R5."""
    i1 = inv(db, w1, a1, u1, invoice_status="draft", payment_status="unpaid")
    i2 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="partial", paid_amount=Decimal("200.00"))
    i3 = inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid")
    result = M.list_invoices(db, w1.id, payment_status="", invoice_status="")
    assert ids_set(result) == {i1.id, i2.id, i3.id}


@pytest.mark.xfail(strict=True, reason="BUG-635: payment_status=overdue is never derived; always returns nothing")
def test_l_45__overdue_derived_filter(db, M, w1, a1, u1):
    """AIM-L-45 — payment_status=overdue should be a derived filter; today it always returns [].
    Rules: list_invoices R5a [BUG-635]."""
    i1 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=date(2026, 9, 26))
    i2 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="partial",
             paid_amount=Decimal("200.00"), due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=date(2026, 9, 27))
    inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=None)
    inv(db, w1, a1, u1, invoice_status="draft", payment_status="unpaid", due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid", due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="paid",
        paid_amount=Decimal("1000.00"), due_date=date(2020, 1, 1))
    result = M.list_invoices(db, w1.id, payment_status="overdue")
    assert ids_set(result) == {i1.id, i2.id}


def test_l_46__unpaid_filter_is_stored_column_equality(db, M, w1, a1, u1):
    """AIM-L-46 — the "unpaid" filter is plain stored-column equality, overdue or not.
    Rules: list_invoices R5, R5a."""
    i1 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=date(2026, 9, 26))
    inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="partial",
        paid_amount=Decimal("200.00"), due_date=date(2020, 1, 1))
    i3 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=date(2026, 9, 27))
    i4 = inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="unpaid", due_date=None)
    i5 = inv(db, w1, a1, u1, invoice_status="draft", payment_status="unpaid", due_date=date(2020, 1, 1))
    i6 = inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid", due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_status="confirmed", payment_status="paid",
        paid_amount=Decimal("1000.00"), due_date=date(2020, 1, 1))
    result = M.list_invoices(db, w1.id, payment_status="unpaid")
    assert ids_set(result) == {i1.id, i3.id, i4.id, i5.id, i6.id}


# =========================================================================== #
# AccountInvoiceManager.list_open_invoices_page
# =========================================================================== #

def open_page(db, M, w1, account, **kw):
    return M.list_open_invoices_page(db, workspace_id=w1.id, account_id=account.id, **kw)


def test_lo_01__open_balance_only_current_account(db, M, w1, a1, a2, u1):
    """AIM-LO-01 — open invoices are confirmed with an open balance, on the given account only.
    Rules: list_open_invoices_page R1, R2."""
    i1 = inv(db, w1, a1, u1, payment_status="unpaid")
    i2 = inv(db, w1, a1, u1, payment_status="partial", paid_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, payment_status="paid", paid_amount=Decimal("1000.00"))
    inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid")
    inv(db, w1, a2, u1, payment_status="unpaid")
    items, total = open_page(db, M, w1, a1)
    assert ids_set(items) == {i1.id, i2.id}
    assert total == 2


@pytest.mark.xfail(strict=True, reason="BUG-634: draft invoices are counted as open balances")
def test_lo_02__draft_excluded_from_open(db, M, w1, a1, u1):
    """AIM-LO-02 — a draft should not count as open; today it is included.
    Rules: list_open_invoices_page R2 [BUG-634]."""
    i1 = inv(db, w1, a1, u1, invoice_date=date(2026, 9, 2))
    inv(db, w1, a1, u1, invoice_status="draft", invoice_date=date(2026, 9, 1))
    items, total = open_page(db, M, w1, a1)
    assert ids_list(items) == [i1.id]
    assert total == 1


def test_lo_03__other_workspace_account_empty(db, M, w1, w2, ax, u3):
    """AIM-LO-03 — an account belonging to another workspace returns nothing.
    Rules: list_open_invoices_page R1."""
    inv(db, w2, ax, u3, payment_status="unpaid")
    items, total = open_page(db, M, w1, ax)
    assert items == []
    assert total == 0


def test_lo_04__deleted_account_empty(db, M, w1, a1, u1):
    """AIM-LO-04 — a soft-deleted account's invoices are excluded.
    Rules: list_open_invoices_page R1."""
    inv(db, w1, a1, u1, payment_status="unpaid")
    a1.is_deleted = True
    db.flush()
    items, total = open_page(db, M, w1, a1)
    assert items == []
    assert total == 0


def test_lo_05__order_date_desc_then_id_desc(db, M, w1, a1, u1):
    """AIM-LO-05 — default order is invoice_date desc, then id desc.
    Rules: list_open_invoices_page R3."""
    i1 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 1))
    i2 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 3))
    i3 = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 3))
    items, total = open_page(db, M, w1, a1)
    assert ids_list(items) == [i3.id, i2.id, i1.id]
    assert total == 3


def test_lo_06__prioritize_purchase_order_group_first(db, M, w1, a1, u1):
    """AIM-LO-06 — prioritize_purchase_order_id groups matching invoices first.
    Rules: list_open_invoices_page R3."""
    x = inv(db, w1, a1, u1, order_type="purchase_order", order_id=55, invoice_date=date(2026, 3, 1))
    y = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 5))
    z = inv(db, w1, a1, u1, order_type="purchase_order", order_id=55, invoice_date=date(2026, 3, 3))
    v = inv(db, w1, a1, u1, order_type="purchase_order", order_id=66, invoice_date=date(2026, 3, 4))
    e = inv(db, w1, a1, u1, order_type="expense_order", order_id=55, invoice_date=date(2026, 3, 6))
    items, total = open_page(db, M, w1, a1, prioritize_purchase_order_id=55)
    assert ids_list(items) == [z.id, x.id, e.id, y.id, v.id]
    assert total == 5


def test_lo_07__default_limit_10(db, M, w1, a1, u1):
    """AIM-LO-07 — the default limit returns at most 10, newest first; total ignores paging.
    Rules: list_open_invoices_page R4."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 9, d)) for d in range(1, 13)]
    items, total = open_page(db, M, w1, a1)
    assert ids_list(items) == [r.id for r in reversed(rows[2:])]
    assert total == 12


def test_lo_08__skip_and_limit(db, M, w1, a1, u1):
    """AIM-LO-08 — skip/limit window the ordered results; total ignores paging.
    Rules: list_open_invoices_page R4."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 3, d)) for d in range(1, 6)]
    items, total = open_page(db, M, w1, a1, skip=2, limit=2)
    assert ids_list(items) == [rows[2].id, rows[1].id]
    assert total == 5


def test_lo_09__prioritize_zero_is_real_value(db, M, w1, a1, u1):
    """AIM-LO-09 — prioritize_purchase_order_id=0 is a real filter value, not "not given".
    Rules: list_open_invoices_page R3."""
    x = inv(db, w1, a1, u1, order_type="purchase_order", order_id=0, invoice_date=date(2026, 3, 1))
    y = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 5))
    items, total = open_page(db, M, w1, a1, prioritize_purchase_order_id=0)
    assert ids_list(items) == [x.id, y.id]
    assert total == 2


# =========================================================================== #
# AccountInvoiceManager.list_invoices_page
# =========================================================================== #

def lpage(db, M, w1, **kw):
    return M.list_invoices_page(db, workspace_id=w1.id, **kw)


def test_lp_01__filters_combine(db, M, w1, w2, a1, a2, ax, u1, u3):
    """AIM-LP-01 — account, type and invoice-number filters combine with AND.
    Rules: list_invoices_page R1."""
    i1 = inv(db, w1, a1, u1, invoice_type="payable", invoice_number="INV-0042")
    inv(db, w1, a1, u1, invoice_type="payable", invoice_number="INV-0100")
    inv(db, w1, a1, u1, invoice_type="receivable", invoice_number="INV-0042B")
    inv(db, w1, a2, u1, invoice_type="payable", invoice_number="INV-0042C")
    inv(db, w2, ax, u3, invoice_type="payable", invoice_number="INV-0042")
    items, total = lpage(db, M, w1, account_id=a1.id, invoice_type="payable", invoice_number_search="v-0042")
    assert ids_list(items) == [i1.id]
    assert total == 1


def test_lp_02__deleted_account_excluded(db, M, w1, a1, u1):
    """AIM-LP-02 — a soft-deleted account's invoices are excluded; status is not filtered.
    Rules: list_invoices_page R1."""
    i1 = inv(db, w1, a1, u1, invoice_status="voided")
    i2 = inv(db, w1, a1, u1, invoice_status="draft")
    a3 = mk_account(db, w1, "Gamma", is_deleted=True)
    inv(db, w1, a3, u1)
    items, total = lpage(db, M, w1)
    assert ids_set(items) == {i1.id, i2.id}
    assert total == 2


def test_lp_03__open_balance_only(db, M, w1, a1, u1):
    """AIM-LP-03 — open_balance_only keeps only open confirmed invoices.
    Rules: list_invoices_page R2."""
    i1 = inv(db, w1, a1, u1, payment_status="unpaid")
    i2 = inv(db, w1, a1, u1, payment_status="partial", paid_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, payment_status="paid", paid_amount=Decimal("1000.00"))
    inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid")
    items, total = lpage(db, M, w1, open_balance_only=True)
    assert ids_set(items) == {i1.id, i2.id}
    assert total == 2


@pytest.mark.xfail(strict=True, reason="BUG-634: draft invoices are counted as open balances")
def test_lp_04__draft_excluded_from_open_balance(db, M, w1, a1, u1):
    """AIM-LP-04 — a draft should not count toward open_balance_only; today it is included.
    Rules: list_invoices_page R2 [BUG-634]."""
    i1 = inv(db, w1, a1, u1, invoice_date=date(2026, 9, 2))
    inv(db, w1, a1, u1, invoice_status="draft", invoice_date=date(2026, 9, 1))
    items, total = lpage(db, M, w1, open_balance_only=True)
    assert ids_list(items) == [i1.id]
    assert total == 1


def test_lp_05__prioritize_purchase_order_group_first(db, M, w1, a1, u1):
    """AIM-LP-05 — prioritize_purchase_order_id groups matching invoices first.
    Rules: list_invoices_page R3."""
    x = inv(db, w1, a1, u1, order_type="purchase_order", order_id=55, invoice_date=date(2026, 3, 1))
    y = inv(db, w1, a1, u1, invoice_date=date(2026, 3, 5))
    z = inv(db, w1, a1, u1, order_type="purchase_order", order_id=55, invoice_date=date(2026, 3, 3))
    v = inv(db, w1, a1, u1, order_type="purchase_order", order_id=66, invoice_date=date(2026, 3, 4))
    e = inv(db, w1, a1, u1, order_type="expense_order", order_id=55, invoice_date=date(2026, 3, 6))
    items, total = lpage(db, M, w1, prioritize_purchase_order_id=55)
    assert ids_list(items) == [z.id, x.id, e.id, y.id, v.id]
    assert total == 5


def test_lp_06__skip_and_limit(db, M, w1, a1, u1):
    """AIM-LP-06 — skip/limit window the ordered results; total ignores paging.
    Rules: list_invoices_page R3."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 3, d)) for d in range(1, 6)]
    items, total = lpage(db, M, w1, skip=1, limit=2)
    assert ids_list(items) == [rows[3].id, rows[2].id]
    assert total == 5


def test_lp_07__default_limit_100(db, M, w1, a1, u1):
    """AIM-LP-07 — the default limit caps at 100; total ignores paging.
    Rules: list_invoices_page R3."""
    rows = [inv(db, w1, a1, u1, invoice_date=date(2026, 1, 1))]
    rows += [inv(db, w1, a1, u1, invoice_date=date(2026, 1, 1) + timedelta(days=n)) for n in range(1, 101)]
    items, total = lpage(db, M, w1)
    assert len(items) == 100
    assert items[0].invoice_date == date(2026, 4, 11)
    assert total == 101


# =========================================================================== #
# AccountInvoiceManager.summarize_invoices
# =========================================================================== #

def summarize(db, M, w1, **kw):
    return M.summarize_invoices(db, w1.id, **kw)


def test_sum_01__counts_and_totals(db, M, w1, a1, u1):
    """AIM-SUM-01 — count covers all matches; money totals exclude voided.
    Rules: summarize_invoices R1, R2."""
    inv(db, w1, a1, u1, payment_status="partial", paid_amount=Decimal("400.00"))
    inv(db, w1, a1, u1, payment_status="paid", invoice_amount=Decimal("500.00"), paid_amount=Decimal("500.00"))
    inv(db, w1, a1, u1, invoice_status="voided", payment_status="unpaid", invoice_amount=Decimal("700.00"))
    result = summarize(db, M, w1)
    assert result == (3, Decimal("1500.00"), Decimal("900.00"), Decimal("600.00"))


def test_sum_02__account_filter(db, M, w1, a1, a2, u1):
    """AIM-SUM-02 — account_id filters the matching set.
    Rules: summarize_invoices R1."""
    inv(db, w1, a1, u1, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_amount=Decimal("200.00"), paid_amount=Decimal("0.00"))
    result = summarize(db, M, w1, account_id=a2.id)
    assert result == (1, Decimal("200.00"), Decimal("0"), Decimal("200.00"))


def test_sum_03__no_invoices_zero_decimals(db, M, w1):
    """AIM-SUM-03 — an empty match set returns zero Decimal totals, not None.
    Rules: summarize_invoices R2."""
    result = summarize(db, M, w1)
    assert result == (0, 0, 0, 0)
    assert result[0] == 0
    assert result[1] == Decimal("0")
    assert result[2] == Decimal("0")
    assert result[3] == Decimal("0")


@pytest.mark.xfail(strict=True, reason="BUG-634: draft invoices are included in the money totals")
def test_sum_04__drafts_excluded_from_money_totals(db, M, w1, a1, u1):
    """AIM-SUM-04 — a draft should be excluded from invoiced/outstanding; today it is included.
    Rules: summarize_invoices R2 [BUG-634]."""
    inv(db, w1, a1, u1, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_status="draft", invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"))
    result = summarize(db, M, w1)
    assert result[1] == Decimal("1000.00")
    assert result[2] == Decimal("0")
    assert result[3] == Decimal("1000.00")


def test_sum_05__count_includes_drafts(db, M, w1, a1, u1):
    """AIM-SUM-05 — the count keeps covering all matching invoices, drafts included.
    Rules: summarize_invoices R1."""
    inv(db, w1, a1, u1, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_status="draft", invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"))
    result = summarize(db, M, w1)
    assert result[0] == 2


def test_sum_06__isolation_and_deleted_account(db, M, w1, w2, a1, u1, ax, u3):
    """AIM-SUM-06 — another workspace and a soft-deleted account's invoices never count.
    Rules: summarize_invoices R1."""
    inv(db, w1, a1, u1, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    a3 = mk_account(db, w1, "Gamma", is_deleted=True)
    inv(db, w1, a3, u1, invoice_amount=Decimal("300.00"), paid_amount=Decimal("0.00"))
    inv(db, w2, ax, u3, invoice_amount=Decimal("900.00"), paid_amount=Decimal("0.00"))
    result = summarize(db, M, w1)
    assert result == (1, Decimal("1000.00"), Decimal("0"), Decimal("1000.00"))


# =========================================================================== #
# AccountInvoiceManager.get_invoices_hub_summary
# =========================================================================== #

def hub_summary(db, M, w1):
    return M.get_invoices_hub_summary(db, workspace_id=w1.id)


def test_hs_01__workspace_kpis(db, M, w1, a1, a2, u1):
    """AIM-HS-01 — open counts, outstanding totals and account counts per type.
    Rules: get_invoices_hub_summary R2, R3, R4."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="partial",
        invoice_amount=Decimal("500.00"), paid_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("300.00"), paid_amount=Decimal("300.00"))
    inv(db, w1, a1, u1, invoice_type="payable", invoice_status="voided", payment_status="unpaid",
        invoice_amount=Decimal("700.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("250.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("400.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="partial",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("40.00"))
    result = hub_summary(db, M, w1)
    assert result == ((3, Decimal("1550.00"), 0, 2), (2, Decimal("460.00"), 0, 1), 2, 2)


def test_hs_02__deleted_excluded_inactive_counted(db, M, w1, u1):
    """AIM-HS-02 — a soft-deleted account never counts; an inactive one still does.
    Rules: get_invoices_hub_summary R1, R4."""
    a3 = mk_account(db, w1, "Gamma", is_deleted=True)
    a4 = mk_account(db, w1, "Delta", is_active=False)
    inv(db, w1, a3, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("900.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a4, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("600.00"), paid_amount=Decimal("0.00"))
    result = hub_summary(db, M, w1)
    assert result == ((1, Decimal("600.00"), 0, 1), (0, 0, 0, 0), 1, 0)


def test_hs_03__workspace_isolation(db, M, w1, w2, a1, a2, ax, u1, u3):
    """AIM-HS-03 — another workspace's invoices never count toward this workspace's KPIs.
    Rules: get_invoices_hub_summary R1."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"))
    inv(db, w2, ax, u3, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"))
    inv(db, w2, ax, u3, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("7000.00"), paid_amount=Decimal("0.00"))
    result = hub_summary(db, M, w1)
    assert result == ((1, Decimal("100.00"), 0, 1), (0, 0, 0, 0), 1, 2)


def test_hs_04__no_invoices_zero_decimals(db, M, w1, a1, a2):
    """AIM-HS-04 — no invoices gives zero counts and zero Decimal totals (not None).
    Rules: get_invoices_hub_summary R2, R3, R4."""
    result = hub_summary(db, M, w1)
    assert result == ((0, 0, 0, 0), (0, 0, 0, 0), 0, 2)
    assert result[0][1] == Decimal("0")
    assert result[1][1] == Decimal("0")


@pytest.mark.xfail(strict=True, reason="BUG-634: a draft invoice is counted as an open balance")
def test_hs_05__drafts_excluded_from_open(db, M, w1, a1, a2, u1):
    """AIM-HS-05 — a draft should not count toward payable KPIs; today it does.
    Rules: get_invoices_hub_summary R2, R3 [BUG-634]."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="payable", invoice_status="draft", payment_status="unpaid",
        invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"))
    result = hub_summary(db, M, w1)
    assert result[0] == (1, Decimal("1000.00"), 0, 1)
    assert result[2] == 1


def _hs_overdue_setup(db, w1, a1, a2, u1):
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"), due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="partial",
        invoice_amount=Decimal("500.00"), paid_amount=Decimal("100.00"), due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("200.00"), paid_amount=Decimal("0.00"), due_date=date(2099, 12, 31))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("300.00"), paid_amount=Decimal("0.00"), due_date=None)
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("400.00"), paid_amount=Decimal("400.00"), due_date=date(2020, 1, 1))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("150.00"), paid_amount=Decimal("0.00"), due_date=date(2020, 1, 1))


@pytest.mark.xfail(strict=True, reason="BUG-635: overdue is never derived; overdue_count is always 0")
def test_hs_06__overdue_counts(db, M, w1, a1, a2, u1):
    """AIM-HS-06 — overdue_count should reflect open invoices past due; today it is always 0.
    Rules: get_invoices_hub_summary R2 [BUG-635]."""
    _hs_overdue_setup(db, w1, a1, a2, u1)
    result = hub_summary(db, M, w1)
    assert result[0][2] == 2
    assert result[1][2] == 1


def test_hs_07__open_counts_and_totals_unaffected_by_overdue(db, M, w1, a1, a2, u1):
    """AIM-HS-07 — open_count/outstanding/account counts are correct regardless of overdue.
    Rules: get_invoices_hub_summary R2, R3."""
    _hs_overdue_setup(db, w1, a1, a2, u1)
    result = hub_summary(db, M, w1)
    assert result[0][0] == 4
    assert result[0][1] == Decimal("1900.00")
    assert result[0][3] == 1
    assert result[1][0] == 1
    assert result[1][1] == Decimal("150.00")
    assert result[1][3] == 1
    assert result[2] == 2
    assert result[3] == 2


def test_hs_08__any_open_balance_distinct_accounts(db, M, w1, a1, a2, u1):
    """AIM-HS-08 — an account with only a fully-paid invoice does not count toward "any".
    Rules: get_invoices_hub_summary R3."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="partial",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("50.00"))
    a3 = mk_account(db, w1, "Gamma")
    inv(db, w1, a3, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("100.00"))
    result = hub_summary(db, M, w1)
    assert result[2] == 2


def test_hs_09__active_account_count(db, M, w1, w2, a1, a2):
    """AIM-HS-09 — total_active_accounts counts only active, not-deleted accounts of this workspace.
    Rules: get_invoices_hub_summary R4."""
    mk_account(db, w1, "Gamma", is_active=False)
    mk_account(db, w1, "Delta", is_active=True, is_deleted=True)
    mk_account(db, w2, "Xeno Foreign")
    result = hub_summary(db, M, w1)
    assert result[3] == 2


@pytest.mark.xfail(strict=True, reason="BUG-635: overdue is never derived; overdue_count is always 0")
def test_hs_10__day_boundary(db, M, w1, a1, a2, u1):
    """AIM-HS-10 — due today is not overdue, the day before is; today overdue_count is always 0.
    Rules: get_invoices_hub_summary R2 [BUG-635]."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), due_date=date(2026, 9, 26))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("200.00"), paid_amount=Decimal("0.00"), due_date=date(2026, 9, 27))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("50.00"), paid_amount=Decimal("0.00"), due_date=date(2026, 9, 27))
    result = hub_summary(db, M, w1)
    assert result[0][2] == 1
    assert result[1][2] == 0


# =========================================================================== #
# AccountInvoiceManager.list_accounts_hub_page
# =========================================================================== #

def hub_page(db, M, w1, **kw):
    return M.list_accounts_hub_page(db, workspace_id=w1.id, **kw)


def row_accounts(rows):
    return [r[0] for r in rows]


def row_names(rows):
    return [r[0].name for r in rows]


def test_ah_01__deleted_excluded_inactive_without_balance_excluded(db, M, w1, w2, a1, a2):
    """AIM-AH-01 — a soft-deleted account is excluded; an inactive one with no open balance too.
    Rules: list_accounts_hub_page R1."""
    mk_account(db, w1, "Delta", is_deleted=True)
    mk_account(db, w1, "Gamma", is_active=False)
    mk_account(db, w2, "Xeno Foreign")
    rows, total = hub_page(db, M, w1)
    assert row_accounts(rows) == [a1, a2]
    assert total == 2


def test_ah_02__payable_agg_excludes_paid_and_voided(db, M, w1, a1, u1):
    """AIM-AH-02 — the payable agg sums open invoices only; the receivable agg is zeroed.
    Rules: list_accounts_hub_page R2."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="partial",
        invoice_amount=Decimal("500.00"), paid_amount=Decimal("200.00"))
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("300.00"), paid_amount=Decimal("300.00"))
    inv(db, w1, a1, u1, invoice_type="payable", invoice_status="voided", payment_status="unpaid",
        invoice_amount=Decimal("700.00"), paid_amount=Decimal("0.00"))
    rows, _total = hub_page(db, M, w1)
    row = next(r for r in rows if r[0].id == a1.id)
    assert (row[1].outstanding_total, row[1].open_count, row[1].has_overdue) == (Decimal("1300.00"), 2, False)
    assert (row[2].outstanding_total, row[2].open_count, row[2].has_overdue) == (0, 0, False)


@pytest.mark.xfail(strict=True, reason="BUG-636: an inactive account with an open balance is invisible on the hub")
def test_ah_03__inactive_with_open_balance_shown(db, M, w1, a1, u1):
    """AIM-AH-03 — an inactive account with an open balance should still be listed; today it is hidden.
    Rules: list_accounts_hub_page R1 [BUG-636]."""
    a4 = mk_account(db, w1, "Gamma", is_active=False)
    inv(db, w1, a4, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("2000.00"), paid_amount=Decimal("0.00"))
    rows, total = hub_page(db, M, w1)
    assert row_accounts(rows) == [a1, a4]
    assert total == 2
    row = next(r for r in rows if r[0].id == a4.id)
    assert (row[1].outstanding_total, row[1].open_count, row[1].has_overdue) == (Decimal("2000.00"), 1, False)


def test_ah_04__inactive_without_open_balance_excluded(db, M, w1, a1, u1):
    """AIM-AH-04 — an inactive account whose only invoice is fully paid is excluded.
    Rules: list_accounts_hub_page R1."""
    a5 = mk_account(db, w1, "Omega", is_active=False)
    inv(db, w1, a5, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("300.00"), paid_amount=Decimal("300.00"))
    rows, total = hub_page(db, M, w1)
    assert row_accounts(rows) == [a1]
    assert total == 1


@pytest.mark.xfail(strict=True, reason="BUG-634: a draft invoice is counted as an open balance")
def test_ah_05__drafts_excluded_from_agg(db, M, w1, a1, u1):
    """AIM-AH-05 — a draft should not count toward the payable agg; today it does.
    Rules: list_accounts_hub_page R2 [BUG-634]."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a1, u1, invoice_type="payable", invoice_status="draft", payment_status="unpaid",
        invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"))
    rows, _total = hub_page(db, M, w1)
    row = next(r for r in rows if r[0].id == a1.id)
    assert row[1].outstanding_total == Decimal("1000.00")
    assert row[1].open_count == 1


@pytest.mark.xfail(strict=True, reason="BUG-635: has_overdue checks payment_status='overdue', which is never stored")
def test_ah_06__has_overdue_per_type(db, M, w1, a1, u1):
    """AIM-AH-06 — has_overdue should reflect a past due_date; today it is always False.
    Rules: list_accounts_hub_page R3 [BUG-635]."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"), due_date=date(2020, 1, 1))
    inv(db, w1, a1, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("500.00"), paid_amount=Decimal("0.00"), due_date=date(2099, 12, 31))
    rows, _total = hub_page(db, M, w1)
    row = next(r for r in rows if r[0].id == a1.id)
    assert row[1].has_overdue is True
    assert row[2].has_overdue is False


def test_ah_07__no_due_date_not_overdue_paid_not_counted(db, M, w1, a1, u1):
    """AIM-AH-07 — an invoice without a due date and a fully-paid invoice do not affect the agg.
    Rules: list_accounts_hub_page R2, R3."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"), due_date=None)
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("400.00"), paid_amount=Decimal("400.00"), due_date=date(2020, 1, 1))
    rows, _total = hub_page(db, M, w1)
    row = next(r for r in rows if r[0].id == a1.id)
    assert (row[1].outstanding_total, row[1].open_count, row[1].has_overdue) == (Decimal("1000.00"), 1, False)


def test_ah_08__search_substring(db, M, w1, a1, a2):
    """AIM-AH-08 — search matches a case-insensitive substring of the account name.
    Rules: list_accounts_hub_page R4."""
    rows, total = hub_page(db, M, w1, search="ME TR")
    assert row_accounts(rows) == [a1]
    assert total == 1


@pytest.mark.xfail(strict=True, reason="BUG-622: hub search '%' is not escaped and matches every account")
def test_ah_09__percent_literal(db, M, w1, a1, a2):
    """AIM-AH-09 — "%" in search should match only a literal percent; today it matches everything.
    Rules: list_accounts_hub_page R4 [BUG-622]."""
    a1.name = "100% Cotton"
    db.flush()
    rows, total = hub_page(db, M, w1, search="%")
    assert row_accounts(rows) == [a1]
    assert total == 1


@pytest.mark.xfail(strict=True, reason="BUG-622: hub search '_' is not escaped and matches every account")
def test_ah_10__underscore_literal(db, M, w1, a1, a2):
    """AIM-AH-10 — "_" in search should match only a literal underscore; today it matches everything.
    Rules: list_accounts_hub_page R4 [BUG-622]."""
    a1.name = "Dhaka_Mills"
    db.flush()
    rows, total = hub_page(db, M, w1, search="_")
    assert row_accounts(rows) == [a1]
    assert total == 1


def _ah_section_setup(db, w1, a1, a2, u1):
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"))
    inv(db, w1, a2, u1, invoice_type="receivable", payment_status="unpaid",
        invoice_amount=Decimal("200.00"), paid_amount=Decimal("0.00"))
    a3 = mk_account(db, w1, "Gamma")
    a4 = mk_account(db, w1, "Delta")
    inv(db, w1, a4, u1, invoice_type="payable", payment_status="paid",
        invoice_amount=Decimal("50.00"), paid_amount=Decimal("50.00"))
    return a3, a4


def test_ah_11__section_payable(db, M, w1, a1, a2, u1):
    """AIM-AH-11 — section=payable keeps only accounts with a positive payable outstanding.
    Rules: list_accounts_hub_page R5."""
    _ah_section_setup(db, w1, a1, a2, u1)
    rows, total = hub_page(db, M, w1, section="payable")
    assert row_accounts(rows) == [a1]
    assert total == 1


def test_ah_12__section_receivable(db, M, w1, a1, a2, u1):
    """AIM-AH-12 — section=receivable keeps only accounts with a positive receivable outstanding.
    Rules: list_accounts_hub_page R5."""
    _ah_section_setup(db, w1, a1, a2, u1)
    rows, total = hub_page(db, M, w1, section="receivable")
    assert row_accounts(rows) == [a2]
    assert total == 1


def test_ah_13__section_overview_no_balance_filter(db, M, w1, a1, a2, u1):
    """AIM-AH-13 — section=overview applies no balance filter; ordered by name.
    Rules: list_accounts_hub_page R5."""
    a3, a4 = _ah_section_setup(db, w1, a1, a2, u1)
    rows, total = hub_page(db, M, w1, section="overview")
    assert row_accounts(rows) == [a1, a2, a4, a3]
    assert total == 4


def test_ah_14__unknown_section_same_as_overview(db, M, w1, a1, a2, u1):
    """AIM-AH-14 — an unrecognised section behaves like overview.
    Rules: list_accounts_hub_page R5."""
    a3, a4 = _ah_section_setup(db, w1, a1, a2, u1)
    rows, total = hub_page(db, M, w1, section="bogus")
    assert row_accounts(rows) == [a1, a2, a4, a3]
    assert total == 4


@pytest.mark.xfail(strict=True, reason="BUG-623: hub account order is case-sensitive")
def test_ah_15__case_insensitive_name_order(db, M, w1):
    """AIM-AH-15 — names should order case-insensitively; today the order is case-sensitive.
    Rules: list_accounts_hub_page R6 [BUG-623]."""
    n1 = mk_account(db, w1, "APEX")
    n2 = mk_account(db, w1, "Zeta")
    n3 = mk_account(db, w1, "Beta")
    n4 = mk_account(db, w1, "apex")
    rows, _total = hub_page(db, M, w1)
    assert row_accounts(rows) == [n1, n4, n3, n2]


def test_ah_16__name_order_distinct_names(db, M, w1):
    """AIM-AH-16 — distinct names order ascending regardless of insertion order.
    Rules: list_accounts_hub_page R6."""
    mk_account(db, w1, "Charlie")
    mk_account(db, w1, "Alpha")
    mk_account(db, w1, "Bravo")
    rows, _total = hub_page(db, M, w1)
    assert row_names(rows) == ["Alpha", "Bravo", "Charlie"]


def test_ah_17__skip_and_limit(db, M, w1):
    """AIM-AH-17 — skip/limit window the name-ordered results.
    Rules: list_accounts_hub_page R7."""
    for i in range(1, 6):
        mk_account(db, w1, f"Acc {i}")
    rows, total = hub_page(db, M, w1, skip=1, limit=2)
    assert row_names(rows) == ["Acc 2", "Acc 3"]
    assert total == 5


def test_ah_18__default_limit_50(db, M, w1):
    """AIM-AH-18 — the default limit returns at most 50.
    Rules: list_accounts_hub_page R7."""
    for i in range(1, 52):
        mk_account(db, w1, f"Acc {i:02d}")
    rows, total = hub_page(db, M, w1)
    assert len(rows) == 50
    assert row_names(rows)[-1] == "Acc 50"
    assert total == 51


def test_ah_19__section_filter_before_paging(db, M, w1, u1):
    """AIM-AH-19 — the section balance filter applies before skip/limit.
    Rules: list_accounts_hub_page R5, R7."""
    p = [mk_account(db, w1, f"P{i}") for i in range(1, 4)]
    for a in p:
        inv(db, w1, a, u1, invoice_type="payable", payment_status="unpaid",
            invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"))
    mk_account(db, w1, "Q1")
    mk_account(db, w1, "Q2")
    rows, total = hub_page(db, M, w1, section="payable", limit=1)
    assert row_names(rows) == ["P1"]
    assert total == 3


@pytest.mark.xfail(strict=True, reason="BUG-635: has_overdue checks payment_status='overdue', which is never stored")
def test_ah_20__day_boundary(db, M, w1, a1, a2, u1):
    """AIM-AH-20 — due today is not overdue, the day before is; today has_overdue is always False.
    Rules: list_accounts_hub_page R3 [BUG-635]."""
    inv(db, w1, a1, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), due_date=date(2026, 9, 26))
    inv(db, w1, a2, u1, invoice_type="payable", payment_status="unpaid",
        invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), due_date=date(2026, 9, 27))
    rows, _total = hub_page(db, M, w1)
    r1 = next(r for r in rows if r[0].id == a1.id)
    r2 = next(r for r in rows if r[0].id == a2.id)
    assert r1[1].has_overdue is True
    assert r2[1].has_overdue is False


def test_ah_21__equal_names_tie_break_by_id_ignores_heap_order(db, M, w1):
    """AIM-AH-21 — equal names order by id ascending, regardless of physical row order.
    Rules: list_accounts_hub_page R6."""
    s1 = mk_account(db, w1, "Same Name")
    s2 = mk_account(db, w1, "Same Name")
    b = mk_account(db, w1, "Alpha")
    db.execute(text("UPDATE accounts SET is_active = TRUE WHERE id = :id"), {"id": s1.id})
    db.flush()
    rows, total = hub_page(db, M, w1)
    assert row_accounts(rows) == [b, s1, s2]
    assert total == 3


@pytest.mark.xfail(strict=True, reason="BUG-623: hub account order is case-sensitive")
def test_ah_22__case_insensitive_equal_names_tie_break_by_id(db, M, w1):
    """AIM-AH-22 — case-insensitively equal names should order by id; today order is case-sensitive.
    Rules: list_accounts_hub_page R6 [BUG-623]."""
    k1 = mk_account(db, w1, "acme")
    k2 = mk_account(db, w1, "Acme")
    k3 = mk_account(db, w1, "acme")
    rows, total = hub_page(db, M, w1)
    assert row_accounts(rows) == [k1, k2, k3]
    assert total == 3


# =========================================================================== #
# AccountInvoiceManager.update_invoice
# =========================================================================== #
# Gap G15 note: AccountInvoiceUpdate (app/schemas/account_invoice.py) has no
# order_type field today. The cases file (revision 4) resolved this gap by
# best-practice default: under the BUG-625 fix, AccountInvoiceUpdate gains a
# nullable order_type field, so AIM-U-38 and AIM-U-45 (which rely on a sent
# order_type taking effect) are designed `xfail BUG-625`, and AIM-U-53 pins the
# field directly on the schema. Every other case either omits order_type or
# only resends it unchanged (no-op either way), so it is unaffected.

def upd(db, M, inv_row, data, u2):
    return M.update_invoice(db, inv_row.id, data, inv_row.workspace_id, u2.id)


def test_u_01__missing_id_404(db, M, w1, u2):
    """AIM-U-01 — updating an unknown id raises 404 and changes nothing.
    Rules: update_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.update_invoice(db, NOID, UPD(description="x"), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"
    assert count_invoices(db, w1.id) == 0
    assert count_events(db, w1.id) == 0


def test_u_02__other_workspace_404(db, M, w1, w2, ax, u3, u2):
    """AIM-U-02 — an invoice of another workspace is reported as not found.
    Rules: update_invoice R1; Errors row 1."""
    x = mk_ci(db, w2, ax, u3.id)
    before = snap_inv(db, x.id)
    with pytest.raises(HTTPException) as exc:
        M.update_invoice(db, x.id, UPD(due_date=date(2026, 12, 1)), w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Invoice with ID {x.id} not found"
    assert snap_inv(db, x.id) == before
    assert count_events(db, w2.id) == 0


@pytest.mark.xfail(strict=True, reason="BUG-621: update_invoice reads the invoice without FOR UPDATE")
def test_u_03__locks_invoice(db, M, engine, di, u2):
    """AIM-U-03 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: update_invoice R1 [BUG-621]."""
    with SQLCapture(engine) as cap:
        result = M.update_invoice(db, di.id, UPD(description="New"), di.workspace_id, u2.id)
    assert result.id == di.id
    assert cap.locks_invoice()
    assert reread_inv(db, di.id).description == "New"


def test_u_04__voided_invoice_rejected(db, M, vi, u2):
    """AIM-U-04 — editing a voided invoice is always rejected, nothing changes.
    Rules: update_invoice R2; Errors row 2."""
    before = snap_inv(db, vi.id)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, vi, UPD(due_date=date(2026, 12, 1), description="x"), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Voided invoices cannot be edited"
    assert snap_inv(db, vi.id) == before
    assert_no_events(db, vi.id)


def test_u_05__clearable_fields_build_with_null():
    """AIM-U-05 — seven nullable fields build with explicit null and are recorded as set.
    Rules: update_invoice R2a."""
    data = AccountInvoiceUpdate(
        due_date=None, description=None, notes=None, invoice_number=None,
        vendor_invoice_number=None, payment_locked_reason=None, order_id=None,
    )
    assert data.model_fields_set == {
        "due_date", "description", "notes", "invoice_number",
        "vendor_invoice_number", "payment_locked_reason", "order_id",
    }
    for f in data.model_fields_set:
        assert getattr(data, f) is None


@pytest.mark.xfail(strict=True, reason="BUG-630: AccountInvoiceUpdate still accepts null for account_id")
def test_u_06__null_account_id_rejected():
    """AIM-U-06 — null account_id should 422; today it is accepted.
    Rules: update_invoice R2a [BUG-630]; Errors row 3."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceUpdate(account_id=None)
    assert any(e["loc"] == ("account_id",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-630: AccountInvoiceUpdate still accepts null for invoice_type")
def test_u_07__null_invoice_type_rejected():
    """AIM-U-07 — null invoice_type should 422; today it is accepted.
    Rules: update_invoice R2a [BUG-630]; Errors row 3."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceUpdate(invoice_type=None)
    assert any(e["loc"] == ("invoice_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-630: AccountInvoiceUpdate still accepts null for invoice_date")
def test_u_08__null_invoice_date_rejected():
    """AIM-U-08 — null invoice_date should 422; today it is accepted.
    Rules: update_invoice R2a [BUG-630]; Errors row 3."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceUpdate(invoice_date=None)
    assert any(e["loc"] == ("invoice_date",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-630: AccountInvoiceUpdate still accepts null for allow_payments")
def test_u_09__null_allow_payments_rejected():
    """AIM-U-09 — null allow_payments should 422; today it is accepted.
    Rules: update_invoice R2a [BUG-630]; Errors row 3."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceUpdate(allow_payments=None)
    assert any(e["loc"] == ("allow_payments",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-630: AccountInvoiceUpdate still has an invoice_amount field")
def test_u_10__invoice_amount_rejected():
    """AIM-U-10 — a sent invoice_amount should 422; today it is accepted.
    Rules: update_invoice R2a, R11 [BUG-630]; Errors row 4."""
    with pytest.raises(ValidationError):
        AccountInvoiceUpdate(invoice_amount=Decimal("750.00"))


def test_u_11__protected_fields_not_in_schema():
    """AIM-U-11 — status, payment and receiving fields are never update-schema fields.
    Rules: update_invoice R11."""
    for f in ("invoice_status", "payment_status", "paid_amount", "void_note", "receiving_started"):
        assert f not in AccountInvoiceUpdate.model_fields


def test_u_12__confirmed_three_editable_fields(db, M, ci, u2):
    """AIM-U-12 — all three editable fields change: three events, non-editable fields untouched.
    Rules: update_invoice R3, R6, R7, R8, R9."""
    result = upd(db, M, ci, UPD(due_date=date(2026, 11, 15), allow_payments=False,
                                 payment_locked_reason="Disputed"), u2)
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.due_date == date(2026, 11, 15)
    assert r.allow_payments is False
    assert r.payment_locked_reason == "Disputed"
    assert r.updated_by == u2.id
    assert r.invoice_status == "confirmed"
    assert r.description == "Old desc"
    assert_events_set(db, ci.id, [
        ("due_date_changed", "Due date updated", u2.id,
         {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}),
        ("allow_payments_changed", "Payments disabled", u2.id, {"allow_payments": False}),
        ("payment_lock_changed", "Payment lock updated", u2.id, {"payment_locked_reason": "Disputed"}),
    ])


def test_u_13__due_date_cleared(db, M, ci, u2):
    """AIM-U-13 — clearing due_date logs the event with new_due_date null.
    Rules: update_invoice R3, R7."""
    result = upd(db, M, ci, UPD(due_date=None), u2)
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.due_date is None
    assert r.updated_by == u2.id
    assert_events(db, ci.id, [
        ("due_date_changed", "Due date updated", u2.id,
         {"old_due_date": "2026-10-01", "new_due_date": None}),
    ])


def test_u_14__due_date_set_from_null(db, M, w1, a1, u1, u2):
    """AIM-U-14 — setting due_date from null logs the event with old_due_date null.
    Rules: update_invoice R7."""
    c = mk_ci(db, w1, a1, u1.id, due_date=None)
    result = upd(db, M, c, UPD(due_date=date(2026, 11, 15)), u2)
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.due_date == date(2026, 11, 15)
    assert_events(db, c.id, [
        ("due_date_changed", "Due date updated", u2.id,
         {"old_due_date": None, "new_due_date": "2026-11-15"}),
    ])


def test_u_15__allow_payments_enabled(db, M, w1, a1, u1, u2):
    """AIM-U-15 — enabling allow_payments logs "Payments enabled".
    Rules: update_invoice R8."""
    c = mk_ci(db, w1, a1, u1.id, allow_payments=False)
    result = upd(db, M, c, UPD(allow_payments=True), u2)
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.allow_payments is True
    assert r.updated_by == u2.id
    assert_events(db, c.id, [
        ("allow_payments_changed", "Payments enabled", u2.id, {"allow_payments": True}),
    ])


def test_u_16__payment_lock_reason_cleared(db, M, w1, a1, u1, u2):
    """AIM-U-16 — clearing payment_locked_reason logs the event with null.
    Rules: update_invoice R9."""
    c = mk_ci(db, w1, a1, u1.id, payment_locked_reason="Disputed")
    result = upd(db, M, c, UPD(payment_locked_reason=None), u2)
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.payment_locked_reason is None
    assert_events(db, c.id, [
        ("payment_lock_changed", "Payment lock updated", u2.id, {"payment_locked_reason": None}),
    ])


@pytest.mark.xfail(strict=True, reason="BUG-631: a changed non-editable field on a confirmed invoice is silently dropped")
def test_u_17__confirmed_non_editable_field_rejected(db, M, ci, u2):
    """AIM-U-17 — changing "notes" on a confirmed invoice should 400; today it is dropped silently.
    Rules: update_invoice R4 [BUG-631]; Errors row 5."""
    with pytest.raises(HTTPException) as exc:
        upd(db, M, ci, UPD(notes="New notes", due_date=date(2026, 11, 15)), u2)
    assert exc.value.status_code == 400
    assert "notes" in exc.value.detail
    r = reread_inv(db, ci.id)
    assert r.due_date == date(2026, 10, 1)
    assert r.notes == "Old notes"
    assert r.updated_by is None
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason="BUG-631: changing account_id on a confirmed invoice is silently dropped")
def test_u_18__confirmed_account_change_rejected(db, M, ci, a2, u2):
    """AIM-U-18 — changing account_id on a confirmed invoice should 400; today it is ignored.
    Rules: update_invoice R4 [BUG-631]; Errors row 5."""
    with pytest.raises(HTTPException) as exc:
        upd(db, M, ci, UPD(account_id=a2.id), u2)
    assert exc.value.status_code == 400
    assert "account_id" in exc.value.detail
    r = reread_inv(db, ci.id)
    assert r.account_id == ci.account_id
    assert_no_events(db, ci.id)


def test_u_19__confirmed_unchanged_non_editable_field_allowed(db, M, ci, u2):
    """AIM-U-19 — a non-editable field resent with its stored value is a silent no-op.
    Rules: update_invoice R4a, R3, R7."""
    result = upd(db, M, ci, UPD(notes="Old notes", due_date=date(2026, 11, 15)), u2)
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.due_date == date(2026, 11, 15)
    assert r.notes == "Old notes"
    assert_events(db, ci.id, [
        ("due_date_changed", "Due date updated", u2.id,
         {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}),
    ])


def test_u_20__confirmed_empty_update_noop(db, M, ci, u2):
    """AIM-U-20 — an empty update on a confirmed invoice changes nothing.
    Rules: update_invoice R5."""
    before = snap_inv(db, ci.id)
    result = upd(db, M, ci, UPD(), u2)
    assert result.id == ci.id
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


def test_u_21__confirmed_same_value_non_editable_noop(db, M, ci, u2):
    """AIM-U-21 — resending the stored value of a non-editable field is a no-op.
    Rules: update_invoice R5, R4a."""
    before = snap_inv(db, ci.id)
    result = upd(db, M, ci, UPD(description="Old desc"), u2)
    assert result.id == ci.id
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason="BUG-620: updated_by is stamped even when nothing actually changes")
def test_u_22__confirmed_unchanged_value_keeps_updated_by(db, M, ci, u2):
    """AIM-U-22 — resending allow_payments unchanged should not stamp updated_by; today it does.
    Rules: update_invoice R6 [BUG-620]."""
    result = upd(db, M, ci, UPD(allow_payments=True), u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).updated_by is None


@pytest.mark.xfail(strict=True, reason="BUG-632: an unchanged due_date still logs an event")
def test_u_23__confirmed_unchanged_due_date_no_event(db, M, ci, u2):
    """AIM-U-23 — resending the stored due_date should log no event; today it does.
    Rules: update_invoice R7 [BUG-632]."""
    result = upd(db, M, ci, UPD(due_date=date(2026, 10, 1)), u2)
    assert result.id == ci.id
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason="BUG-632: an unchanged allow_payments still logs an event")
def test_u_24__confirmed_unchanged_allow_payments_no_event(db, M, ci, u2):
    """AIM-U-24 — resending the stored allow_payments should log no event; today it does.
    Rules: update_invoice R8 [BUG-632]."""
    result = upd(db, M, ci, UPD(allow_payments=True), u2)
    assert result.id == ci.id
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason="BUG-632: an unchanged payment_locked_reason still logs an event")
def test_u_25__confirmed_unchanged_payment_lock_no_event(db, M, w1, a1, u1, u2):
    """AIM-U-25 — resending the stored payment_locked_reason should log no event; today it does.
    Rules: update_invoice R9 [BUG-632]."""
    c = mk_ci(db, w1, a1, u1.id, payment_locked_reason="Disputed")
    result = upd(db, M, c, UPD(payment_locked_reason="Disputed"), u2)
    assert result.id == c.id
    assert_no_events(db, c.id)


def test_u_26__draft_full_edit(db, M, di, u2):
    """AIM-U-26 — a draft update applies every sent field and logs one summarizing event.
    Rules: update_invoice R11, R12, R13, R14, R15."""
    result = upd(db, M, di, UPD(
        description="New desc", notes="N1", invoice_number=None, due_date=date(2026, 12, 1),
        invoice_date=date(2026, 9, 5), invoice_type="receivable",
    ), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.description == "New desc"
    assert r.notes == "N1"
    assert r.invoice_number is None
    assert r.due_date == date(2026, 12, 1)
    assert r.invoice_date == date(2026, 9, 5)
    assert r.invoice_type == "receivable"
    assert r.invoice_status == "draft"
    assert r.invoice_amount == Decimal("1000.00")
    assert r.updated_by == u2.id
    assert r.updated_at is not None
    assert_events(db, di.id, [
        ("item_manually_updated", "Invoice details updated", u2.id, {
            "description": "New desc", "notes": "N1", "invoice_number": "None",
            "due_date": "2026-12-01", "invoice_date": "2026-09-05", "invoice_type": "receivable",
        }),
    ])


def test_u_27__draft_account_change(db, M, di, a2, u2):
    """AIM-U-27 — a draft account change applies and logs it.
    Rules: update_invoice R10, R14."""
    result = upd(db, M, di, UPD(account_id=a2.id), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.account_id == a2.id
    assert r.updated_by == u2.id
    assert_events(db, di.id, [
        ("item_manually_updated", "Invoice details updated", u2.id, {"account_id": str(a2.id)}),
    ])


def test_u_28__draft_account_other_workspace_404(db, M, di, ax, u2):
    """AIM-U-28 — a new account belonging to another workspace is not found.
    Rules: update_invoice R10; Errors row 6."""
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(account_id=ax.id), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ax.id} not found"
    assert snap_inv(db, di.id) == before
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_u_29__draft_account_missing_404(db, M, di, u2):
    """AIM-U-29 — a nonexistent new account id is not found.
    Rules: update_invoice R10; Errors row 6."""
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(account_id=NOID), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Account with ID 999999 not found"
    assert snap_inv(db, di.id) == before
    assert_no_events(db, di.id)


def test_u_30__draft_account_deleted_rejected(db, M, w1, di, u2):
    """AIM-U-30 — a soft-deleted new account is rejected.
    Rules: update_invoice R10; Errors row 7."""
    a2 = mk_account(db, w1, "Beta Supplies", is_deleted=True, is_active=False, allow_invoices=False)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(account_id=a2.id), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot assign invoice to deleted account"
    assert snap_inv(db, di.id) == before
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-629: an inactive new account is accepted instead of rejected")
def test_u_31__draft_account_inactive_rejected(db, M, w1, di, u2):
    """AIM-U-31 — an inactive new account should 400; today it is accepted.
    Rules: update_invoice R10 [BUG-629]; Errors row 8."""
    a2 = mk_account(db, w1, "Beta Supplies", is_active=False, allow_invoices=False)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(account_id=a2.id), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot assign invoice to inactive account"
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert r.updated_by is None
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-629: an allow_invoices=False new account is accepted instead of rejected")
def test_u_32__draft_account_disallowed_rejected(db, M, w1, di, u2):
    """AIM-U-32 — a new account with allow_invoices=False should 403; today it is accepted.
    Rules: update_invoice R10 [BUG-629]; Errors row 9."""
    a2 = mk_account(db, w1, "Beta Supplies", allow_invoices=False)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(account_id=a2.id), u2)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Invoices are not allowed for this account"
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert_no_events(db, di.id)


def test_u_33__draft_same_account_no_check(db, M, di, u2):
    """AIM-U-33 — resending the current account skips the account checks entirely.
    Rules: update_invoice R10."""
    acc = db.get(Account, di.account_id)
    acc.is_active = False
    acc.allow_invoices = False
    db.flush()
    result = upd(db, M, di, UPD(account_id=di.account_id, description="New desc"), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert r.description == "New desc"


def test_u_34__draft_order_id_changed(db, M, w1, di, u1, u2):
    """AIM-U-34 — changing order_id to another live order of the same type is applied.
    Rules: update_invoice R12."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    p2 = mk_po(db, w1, "PO-2", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    result = upd(db, M, di, UPD(order_id=p2.id), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.order_id == p2.id
    assert r.order_type == "purchase_order"


@pytest.mark.xfail(strict=True, reason="BUG-625: order_id is never validated to exist")
def test_u_35__order_id_nonexistent_rejected(db, M, w1, di, u1, u2):
    """AIM-U-35 — a nonexistent new order_id should 404; today it is stored unchecked.
    Rules: update_invoice R12 [BUG-625]; Errors row 12."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=NOID), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order with ID 999999 not found"
    r = reread_inv(db, di.id)
    assert r.order_id == p1.id
    assert r.updated_by is None
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-625: an order_id from another workspace is never validated")
def test_u_36__order_id_other_workspace_rejected(db, M, w1, w2, di, u1, u2):
    """AIM-U-36 — a new order_id belonging to another workspace should 404; today unchecked.
    Rules: update_invoice R12 [BUG-625]; Errors row 12."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    pw =mk_po(db, w2, "PO-9", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=pw.id), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {pw.id} not found"
    r = reread_inv(db, di.id)
    assert r.order_id == p1.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-625: a soft-deleted order's id is never validated")
def test_u_37__order_id_deleted_rejected(db, M, w1, di, u1, u2):
    """AIM-U-37 — a soft-deleted new order_id should 404; today unchecked.
    Rules: update_invoice R12, R9d [BUG-625]; Errors row 12."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    pd =mk_po(db, w1, "PO-D", u1.id, voided=True)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=pd.id), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {pd.id} not found"
    r = reread_inv(db, di.id)
    assert r.order_id == p1.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(
    strict=True,
    reason="BUG-625 (G15): AccountInvoiceUpdate has no order_type field, so UPD(order_type=...) is "
           "silently dropped by pydantic (extra='ignore') and order_type never actually clears",
)
def test_u_38__draft_order_cleared_together(db, M, w1, di, u1, u2):
    """AIM-U-38 — clearing both order_type and order_id together skips the order check; today order_type is dropped.
    Rules: update_invoice R2b, R12, R12a, R14 [BUG-625] (G15)."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    result = upd(db, M, di, UPD(order_type=None, order_id=None), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.order_type is None
    assert r.order_id is None
    assert r.updated_by == u2.id
    assert_events(db, di.id, [
        ("item_manually_updated", "Invoice details updated", u2.id,
         {"order_type": "None", "order_id": "None"}),
    ])


@pytest.mark.xfail(strict=True, reason="BUG-620: updated_by is stamped even for an empty draft update")
def test_u_39__draft_empty_update_keeps_updated_by_none(db, M, di, u2):
    """AIM-U-39 — an empty draft update should not stamp updated_by; today it does.
    Rules: update_invoice R13 [BUG-620]."""
    result = upd(db, M, di, UPD(), u2)
    assert result.id == di.id
    assert reread_inv(db, di.id).updated_by is None


@pytest.mark.xfail(strict=True, reason="BUG-632: an empty draft update still logs an event")
def test_u_40__draft_empty_update_no_event(db, M, di, u2):
    """AIM-U-40 — an empty draft update should log no event; today it logs one with metadata {}.
    Rules: update_invoice R14 [BUG-632]."""
    result = upd(db, M, di, UPD(), u2)
    assert result.id == di.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-632: metadata includes unchanged fields, not just the changed one")
def test_u_41__draft_event_metadata_only_changed_field(db, M, di, u2):
    """AIM-U-41 — metadata should contain only the field that changed; today it also has "description".
    Rules: update_invoice R14 [BUG-632]."""
    result = upd(db, M, di, UPD(description="Old desc", notes="New notes"), u2)
    assert result.id == di.id
    rows = events_of(db, di.id)
    assert len(rows) == 1
    assert rows[0].metadata_json == {"notes": "New notes"}


def test_u_42__draft_unchanged_field_resent_with_changed_one(db, M, di, u2):
    """AIM-U-42 — resending an unchanged field alongside a changed one still applies and logs once.
    Rules: update_invoice R12, R13, R14."""
    result = upd(db, M, di, UPD(description="Old desc", notes="New notes"), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.notes == "New notes"
    assert r.description == "Old desc"
    assert r.updated_by == u2.id
    rows = events_of(db, di.id)
    assert len(rows) == 1
    assert rows[0].event_type == "item_manually_updated"
    assert rows[0].metadata_json["notes"] == "New notes"


@pytest.mark.xfail(strict=True, reason="BUG-620: updated_by is stamped even when the sent value is unchanged")
def test_u_43__draft_unchanged_field_keeps_updated_by_none(db, M, di, u2):
    """AIM-U-43 — resending the stored description should not stamp updated_by; today it does.
    Rules: update_invoice R13 [BUG-620]."""
    result = upd(db, M, di, UPD(description="Old desc"), u2)
    assert result.id == di.id
    assert reread_inv(db, di.id).updated_by is None


@pytest.mark.xfail(strict=True, reason="BUG-632: an unchanged draft field still logs an event")
def test_u_44__draft_unchanged_field_no_event(db, M, di, u2):
    """AIM-U-44 — resending the stored description should log no event; today it does.
    Rules: update_invoice R14 [BUG-632]."""
    result = upd(db, M, di, UPD(description="Old desc"), u2)
    assert result.id == di.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(
    strict=True,
    reason="BUG-625 (G15): AccountInvoiceUpdate has no order_type field, so UPD(order_type=...) is "
           "silently dropped by pydantic (extra='ignore') and order_type never actually changes",
)
def test_u_45__draft_order_type_and_id_both_changed(db, M, w1, di, u1, u2):
    """AIM-U-45 — changing both order_type and order_id together to a valid link applies; today order_type is dropped.
    Rules: update_invoice R2b, R12, R12a, R14 [BUG-625] (G15)."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    e1 = mk_eo(db, w1, "EXP-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    result = upd(db, M, di, UPD(order_type="expense_order", order_id=e1.id), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.order_type == "expense_order"
    assert r.order_id == e1.id
    assert r.updated_by == u2.id
    assert_events(db, di.id, [
        ("item_manually_updated", "Invoice details updated", u2.id,
         {"order_type": "expense_order", "order_id": str(e1.id)}),
    ])


@pytest.mark.xfail(strict=True, reason="BUG-625: the stored order_id is not re-validated against a changed order_type")
def test_u_46__order_type_change_revalidates_stored_id(db, M, w1, di, u1, u2):
    """AIM-U-46 — changing only order_type should re-validate the stored id against it; today unchecked.
    Rules: update_invoice R2b, R12a [BUG-625]; Errors row 12."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    assert db.execute(select(ExpenseOrder).where(ExpenseOrder.id == p1.id)).scalar_one_or_none() is None
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_type="expense_order"), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {p1.id} not found"
    r = reread_inv(db, di.id)
    assert r.order_type == "purchase_order"
    assert r.order_id == p1.id
    assert r.updated_by is None
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-625: sending only order_id on an unlinked invoice is accepted")
def test_u_47__order_id_alone_on_unlinked_rejected(db, M, w1, di, u1, u2):
    """AIM-U-47 — sending only order_id on an unlinked invoice should 400; today it is stored.
    Rules: update_invoice R12a [BUG-625]; Errors row 13."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=p1.id), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "order_type and order_id must be set together"
    r = reread_inv(db, di.id)
    assert r.order_type is None
    assert r.order_id is None
    assert r.updated_by is None
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason="BUG-625: clearing only order_id on a linked invoice is accepted")
def test_u_48__order_id_cleared_alone_rejected(db, M, w1, di, u1, u2):
    """AIM-U-48 — clearing only order_id on a linked invoice should 400; today it is accepted.
    Rules: update_invoice R12a [BUG-625]; Errors row 13."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=None), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "order_type and order_id must be set together"
    r = reread_inv(db, di.id)
    assert r.order_id == p1.id
    assert r.order_type == "purchase_order"
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_u_49__order_id_resent_unchanged(db, M, w1, di, u1, u2):
    """AIM-U-49 — resending the same order_id alongside another field applies that field.
    Rules: update_invoice R12a."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    result = upd(db, M, di, UPD(order_type="purchase_order", order_id=p1.id, description="New desc"), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.order_id == p1.id
    assert r.order_type == "purchase_order"
    assert r.description == "New desc"


def test_u_50__order_id_resent_unchanged_order_is_deleted(db, M, w1, u1, a1, u2):
    """AIM-U-50 — resending the same order_id (even for a now-deleted order) skips the order check.
    Rules: update_invoice R12a."""
    pd = mk_po(db, w1, "PO-D", u1.id, voided=True)
    c = mk_di(db, w1, a1, u1.id, order_type="purchase_order", order_id=pd.id)
    result = upd(db, M, c, UPD(order_id=pd.id, notes="New notes"), u2)
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.order_id == pd.id
    assert r.notes == "New notes"


@pytest.mark.xfail(strict=True, reason="BUG-629: account_id=0 reaches the database as an FK integrity error, not a 404")
def test_u_51__account_id_zero_intended_404(db, M, di, u2):
    """AIM-U-51 — account_id=0 should 404; today it is a DB integrity error.
    Rules: update_invoice R10a [BUG-629]; Errors row 10."""
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            upd(db, M, di, UPD(account_id=0), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Account with ID 0 not found"
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_u_52__account_id_zero_raises_and_rolls_back(db, M, di, u2):
    """AIM-U-52 — account_id=0 raises some exception today, and the rollback leaves nothing changed.
    Rules: update_invoice R10a."""
    with pytest.raises(Exception):
        with db.begin_nested():
            upd(db, M, di, UPD(account_id=0), u2)
    r = reread_inv(db, di.id)
    assert r.account_id == di.account_id
    assert r.updated_by is None
    assert_no_events(db, di.id)


@pytest.mark.xfail(
    strict=True,
    reason="BUG-625 (G15): AccountInvoiceUpdate has no order_type field; it is silently dropped instead of being set",
)
def test_u_53__order_type_field_on_schema():
    """AIM-U-53 — AccountInvoiceUpdate should have a settable, nullable order_type field; today it has none.
    Rules: update_invoice R2b [BUG-625] (G15)."""
    for t in ("purchase_order", "expense_order", "sales_order", "work_order"):
        a = AccountInvoiceUpdate(order_type=t)
        assert "order_type" in a.model_fields_set
        assert a.order_type == t
    b = AccountInvoiceUpdate(order_type=None)
    assert "order_type" in b.model_fields_set
    assert b.order_type is None


@pytest.mark.xfail(strict=True, reason="BUG-625: a work order with status=VOIDED is never validated as not-found")
def test_u_54__order_id_voided_status_work_order_rejected(db, M, w1, di, u2):
    """AIM-U-54 — a new order_id pointing to a status='VOIDED' work order should 404; today unchecked.
    Rules: update_invoice R12, R9d [BUG-625]; Errors row 12."""
    wo1 = mk_wo(db, w1, "WO-1")
    wv =mk_wo(db, w1, "WO-V", is_deleted=False, status="VOIDED")
    di.order_type = "work_order"
    di.order_id = wo1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_id=wv.id), u2)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order with ID {wv.id} not found"
    r = reread_inv(db, di.id)
    assert r.order_type == "work_order"
    assert r.order_id == wo1.id
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_u_55__order_id_changed_between_live_work_orders(db, M, w1, di, u2):
    """AIM-U-55 — changing order_id to another live work order of the same type is applied.
    Rules: update_invoice R12, R9d."""
    wo1 = mk_wo(db, w1, "WO-1")
    wo2 = mk_wo(db, w1, "WO-2")
    assert wo1.status != "VOIDED"
    assert wo2.status != "VOIDED"
    di.order_type = "work_order"
    di.order_id = wo1.id
    db.flush()
    result = upd(db, M, di, UPD(order_id=wo2.id), u2)
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.order_type == "work_order"
    assert r.order_id == wo2.id
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason="BUG-625: AccountInvoiceUpdate has no order_type field, so an invalid value raises no error")
def test_u_56__order_type_invalid_rejected():
    """AIM-U-56 — an order_type outside the four known values should be a 422 ValidationError; today it is ignored.
    Rules: update_invoice R2b [BUG-625]; Errors row 11."""
    with pytest.raises(ValidationError) as exc:
        AccountInvoiceUpdate(order_type="banana")
    assert any(e["loc"] == ("order_type",) for e in exc.value.errors())


@pytest.mark.xfail(strict=True, reason="BUG-625: AccountInvoiceUpdate has no order_type field, so it is not normalised")
def test_u_57__order_type_trimmed_and_lowercased():
    """AIM-U-57 — order_type is trimmed and lower-cased on the update schema; today the field does not exist.
    Rules: update_invoice R2b [BUG-625]."""
    a = AccountInvoiceUpdate(order_type="  Purchase_Order ")
    assert a.order_type == "purchase_order"
    assert "order_type" in a.model_fields_set


@pytest.mark.xfail(
    strict=True,
    reason="BUG-625, BUG-631: needs both fixes. BUG-625 makes order_type a sent field; BUG-631 rejects a "
           "changed non-editable field on a confirmed invoice. Today the call returns the invoice unchanged",
)
def test_u_58__confirmed_order_type_change_rejected(db, M, ci, u2):
    """AIM-U-58 — changing order_type on a confirmed invoice should be a 400 naming "order_type"; today it is silently dropped.
    Rules: update_invoice R2b, R4 [BUG-625, BUG-631]; Errors row 5."""
    assert ci.order_type is None and ci.order_id is None
    with pytest.raises(HTTPException) as exc:
        upd(db, M, ci, UPD(order_type="purchase_order"), u2)
    assert exc.value.status_code == 400
    assert "order_type" in exc.value.detail
    r = reread_inv(db, ci.id)
    assert r.order_type is None
    assert r.order_id is None
    assert r.due_date == date(2026, 10, 1)
    assert r.updated_by is None
    assert_no_events(db, ci.id)


def test_u_59__confirmed_order_type_same_value_noop(db, M, w1, a1, u1, u2):
    """AIM-U-59 — resending the stored order_type on a confirmed invoice is a no-op.
    Rules: update_invoice R2b, R4a, R5."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    c = mk_ci(db, w1, a1, u1.id, order_type="purchase_order", order_id=p1.id)
    before = snap_inv(db, c.id)
    result = upd(db, M, c, UPD(order_type="purchase_order"), u2)
    assert result.id == c.id
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.order_type == "purchase_order"
    assert r.order_id == p1.id
    assert r.due_date == date(2026, 10, 1)
    assert r.updated_by is None
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason="BUG-625: order_type clear alone is accepted (schema drops order_type, nothing is checked)")
def test_u_60__order_type_cleared_alone_rejected(db, M, w1, di, u1, u2):
    """AIM-U-60 — clearing only order_type on a linked draft should 400 (half-set pair); today it is dropped.
    Rules: update_invoice R2b, R12a [BUG-625]; Errors row 13."""
    p1 = mk_po(db, w1, "PO-1", u1.id)
    di.order_type = "purchase_order"
    di.order_id = p1.id
    db.flush()
    with pytest.raises(HTTPException) as exc:
        upd(db, M, di, UPD(order_type=None), u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "order_type and order_id must be set together"
    r = reread_inv(db, di.id)
    assert r.order_type == "purchase_order"
    assert r.order_id == p1.id
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_u_61__admin_edits_allowed_on_completed_so_invoice(db, M, w1, ci, u1, u2):
    """AIM-U-61 — the three confirmed-invoice edits still apply when the linked SO is completed (no freeze on update).
    Rules: update_invoice R3b, R3, R7, R8, R9; F7."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    result = upd(db, M, ci, UPD(due_date=date(2026, 11, 15), allow_payments=False,
                                 payment_locked_reason="Disputed"), u2)
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.due_date == date(2026, 11, 15)
    assert r.allow_payments is False
    assert r.payment_locked_reason == "Disputed"
    assert r.invoice_status == "confirmed"
    assert_events_set(db, ci.id, [
        ("due_date_changed", "Due date updated", u2.id,
         {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}),
        ("allow_payments_changed", "Payments disabled", u2.id, {"allow_payments": False}),
        ("payment_lock_changed", "Payment lock updated", u2.id, {"payment_locked_reason": "Disputed"}),
    ])


def test_u_62__admin_edits_allowed_on_completed_po_invoice(db, M, w1, ci, u1, u2):
    """AIM-U-62 — the three confirmed-invoice edits still apply when the linked PO is at stage Complete.
    Rules: update_invoice R3b, R3; F7."""
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=ci.id)
    result = upd(db, M, ci, UPD(due_date=date(2026, 12, 1), allow_payments=False,
                                 payment_locked_reason="On hold"), u2)
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.due_date == date(2026, 12, 1)
    assert r.allow_payments is False
    assert r.payment_locked_reason == "On hold"
    assert r.invoice_status == "confirmed"
    evs = events_of(db, ci.id)
    assert len(evs) == 3
    assert {e.event_type for e in evs} == {"due_date_changed", "allow_payments_changed", "payment_lock_changed"}


# =========================================================================== #
# AccountInvoiceManager.delete_invoice
# =========================================================================== #

def delcall(db, M, inv_row, u2):
    return M.delete_invoice(db, inv_row.id, inv_row.workspace_id, u2.id)


def test_del_01__draft_hard_deleted_cascades_and_nulls_referrers(db, M, w1, a1, u1, u2):
    """AIM-DEL-01 — deleting a draft cascades items/events and SET NULLs a referring (not completed) order.
    Rules: delete_invoice R3."""
    d = mk_di(db, w1, a1, u1.id)
    mk_item(db, d, Decimal("100.00"))
    mk_item(db, d, Decimal("50.00"), line_number=2)
    mk_evt(db, d, V0)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=d.id)
    result = delcall(db, M, d, u2)
    assert result.id == d.id
    assert reread_inv_or_none(db, d.id) is None
    assert items_of(db, d.id) == []
    assert events_of(db, d.id) == []
    db.expire_all()
    assert db.get(PurchaseOrder, p1.id).invoice_id is None
    assert count_events(db, w1.id) == 0


def test_del_02__missing_id_404(db, M, w1, u2):
    """AIM-DEL-02 — deleting an unknown id raises 404.
    Rules: delete_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.delete_invoice(db, NOID, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_del_03__other_workspace_404(db, M, w1, w2, ax, u3, u2):
    """AIM-DEL-03 — another workspace's draft is reported as not found and survives.
    Rules: delete_invoice R1; Errors row 1."""
    x = mk_di(db, w2, ax, u3.id)
    with pytest.raises(HTTPException) as exc:
        M.delete_invoice(db, x.id, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Invoice with ID {x.id} not found"
    assert reread_inv_or_none(db, x.id) is not None


def test_del_04__confirmed_rejected(db, M, ci, u2):
    """AIM-DEL-04 — a confirmed invoice cannot be deleted.
    Rules: delete_invoice R2; Errors row 2."""
    mk_item(db, ci, Decimal("100.00"))
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == ("Only draft invoices can be deleted. "
                                 "This invoice is 'confirmed'. Use void instead.")
    assert reread_inv_or_none(db, ci.id) is not None
    assert len(items_of(db, ci.id)) == 1
    assert_no_events(db, ci.id)


def test_del_05__voided_rejected(db, M, vi, u2):
    """AIM-DEL-05 — a voided invoice cannot be deleted.
    Rules: delete_invoice R2; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, vi, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == ("Only draft invoices can be deleted. "
                                 "This invoice is 'voided'. Use void instead.")
    assert reread_inv_or_none(db, vi.id) is not None


@pytest.mark.xfail(strict=True, reason="BUG-639: a draft with payment rows fails with a generic DB integrity error")
def test_del_06__draft_with_voided_payment_clear_error(db, M, di, u1, u2):
    """AIM-DEL-06 — a draft with even a voided payment should 400 with a clear message; today it's a DB error.
    Rules: delete_invoice R4 [BUG-639]; Errors row 4."""
    # Convention PAY: "A voided setup payment has voided_by = U1" (U1 created every setup row).
    mk_pay(db, di, Decimal("100.00"), voided=True, created_by=u1.id)
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice has payment history — confirm and void it instead"
    assert reread_inv_or_none(db, di.id) is not None


def test_del_07__draft_with_voided_payment_raises_something(db, M, di, u1, u2):
    """AIM-DEL-07 — today the attempt raises some exception and nothing is deleted.
    Rules: delete_invoice R4."""
    mk_pay(db, di, Decimal("100.00"), voided=True, created_by=u1.id)
    with pytest.raises(Exception):
        with db.begin_nested():
            delcall(db, M, di, u2)
    assert reread_inv_or_none(db, di.id) is not None
    assert len(db.execute(select(InvoicePayment).where(InvoicePayment.invoice_id == di.id)).scalars().all()) == 1


@pytest.mark.xfail(strict=True, reason="BUG-621: delete_invoice reads the invoice without FOR UPDATE")
def test_del_08__locks_invoice(db, M, engine, di, u2):
    """AIM-DEL-08 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: delete_invoice R1 [BUG-621]."""
    with SQLCapture(engine) as cap:
        result = delcall(db, M, di, u2)
    assert result.id == di.id
    assert cap.locks_invoice()
    assert reread_inv_or_none(db, di.id) is None


@pytest.mark.xfail(strict=True, reason="BUG-639: a draft with legacy status-history rows fails with a generic DB error")
def test_del_09__draft_with_status_history_clear_error(db, M, di, u1, u2):
    """AIM-DEL-09 — a draft with legacy status-history rows should 400 clearly; today it's a DB error.
    Rules: delete_invoice R4 [BUG-639]; Errors row 4."""
    mk_hist(db, di, u1.id)
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice has payment history — confirm and void it instead"
    assert reread_inv_or_none(db, di.id) is not None


def test_del_10__draft_with_status_history_raises_something(db, M, di, u1, u2):
    """AIM-DEL-10 — today the attempt raises some exception and nothing is deleted.
    Rules: delete_invoice R4."""
    mk_hist(db, di, u1.id)
    with pytest.raises(Exception):
        with db.begin_nested():
            delcall(db, M, di, u2)
    assert reread_inv_or_none(db, di.id) is not None
    assert len(db.execute(
        select(InvoiceStatusTracker).where(InvoiceStatusTracker.invoice_id == di.id)
    ).scalars().all()) == 1


def test_del_11__order_referrers_nulled(db, M, w1, a1, u1, u2):
    """AIM-DEL-11 — EO/SO/WO rows (none completed) referring to the deleted invoice survive with invoice_id null.
    Rules: delete_invoice R3."""
    d = mk_di(db, w1, a1, u1.id)
    e1 = mk_eo(db, w1, "EXP-1", u1.id, completed_at=None, invoice_id=d.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=False, invoice_id=d.id)
    wo1 = mk_wo(db, w1, "WO-1", status="DRAFT", invoice_id=d.id)
    result = delcall(db, M, d, u2)
    assert result.id == d.id
    assert reread_inv_or_none(db, d.id) is None
    db.expire_all()
    assert db.get(ExpenseOrder, e1.id).invoice_id is None
    assert db.get(SalesOrder, s1.id).invoice_id is None
    assert db.get(WorkOrder, wo1.id).invoice_id is None


def test_del_12__return_referrers_nulled(db, M, w1, a1, u1, u2):
    """AIM-DEL-12 — purchase/sales order return rows referring to the deleted invoice survive, nulled.
    Rules: delete_invoice R3."""
    d = mk_di(db, w1, a1, u1.id)
    por = mk_por(db, w1, u1.id, invoice_id=d.id)
    sor = mk_sor(db, w1, u1.id, invoice_id=d.id)
    result = delcall(db, M, d, u2)
    assert result.id == d.id
    assert reread_inv_or_none(db, d.id) is None
    db.expire_all()
    assert db.get(PurchaseOrderReturn, por.id).invoice_id is None
    assert db.get(SalesOrderReturn, sor.id).invoice_id is None


def test_del_13__machine_ledger_referrer_nulled(db, M, w1, a1, u1, u2):
    """AIM-DEL-13 — a machine_item_ledger row referring to the deleted invoice survives, nulled.
    Rules: delete_invoice R3."""
    d = mk_di(db, w1, a1, u1.id)
    mled = mk_mled(db, w1, u1.id, invoice_id=d.id)
    result = delcall(db, M, d, u2)
    assert result.id == d.id
    assert reread_inv_or_none(db, d.id) is None
    db.expire_all()
    assert db.get(MachineItemLedger, mled.id).invoice_id is None


# --- Revision 7: completed-order freeze (spec O1, F1-F7) on delete_invoice ---

@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_14__draft_of_completed_po_frozen(db, M, w1, di, u1, u2):
    """AIM-DEL-14 — the draft of a completed PO (stage Complete) is refused with LOCK and nothing is deleted.
    Rules: delete_invoice R2a [BUG-2730]; Errors row 3; F1, F2, F4, F5."""
    item = mk_item(db, di, Decimal("100.00"))
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert ids_list(items_of(db, di.id)) == [item.id]
    assert reread_row(db, PurchaseOrder, p1.id).invoice_id == di.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_15__draft_of_completed_so_frozen(db, M, w1, di, u1, u2):
    """AIM-DEL-15 — the draft of a completed sales order is refused with LOCK("sales order").
    Rules: delete_invoice R2a [BUG-2730]; Errors row 3; F2, F5."""
    item = mk_item(db, di, Decimal("100.00"))
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert ids_list(items_of(db, di.id)) == [item.id]
    assert reread_row(db, SalesOrder, s1.id).invoice_id == di.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_16__draft_of_completed_eo_frozen(db, M, w1, di, u1, u2):
    """AIM-DEL-16 — the draft of a completed expense order (completed_at set) is refused with LOCK("expense order").
    Rules: delete_invoice R2a [BUG-2730]; Errors row 3; F2, F5."""
    item = mk_item(db, di, Decimal("100.00"))
    e1 = mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("expense order")
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert ids_list(items_of(db, di.id)) == [item.id]
    assert reread_row(db, ExpenseOrder, e1.id).invoice_id == di.id
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_17__draft_of_completed_wo_frozen(db, M, w1, di, u1, u2):
    """AIM-DEL-17 — the draft of a completed work order (status COMPLETED) is refused with LOCK("work order").
    Rules: delete_invoice R2a [BUG-2730]; Errors row 3; F2, F5."""
    item = mk_item(db, di, Decimal("100.00"))
    wo1 = mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("work order")
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert ids_list(items_of(db, di.id)) == [item.id]
    assert reread_row(db, WorkOrder, wo1.id).invoice_id == di.id
    assert_no_events(db, di.id)


def test_del_18__po_at_receiving_not_frozen(db, M, w1, di, u1, u2):
    """AIM-DEL-18 — a PO at stage Receiving is not completed, so its draft is deleted.
    Rules: delete_invoice R2a, R3; F2."""
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Receiving", invoice_id=di.id)
    d_id = di.id
    result = delcall(db, M, di, u2)
    assert result.id == d_id
    assert reread_inv_or_none(db, d_id) is None
    assert reread_row(db, PurchaseOrder, p1.id).invoice_id is None


def test_del_19__completed_orders_of_other_workspaces_ignored(db, M, w0, w1, w2, di, u1, u2):
    """AIM-DEL-19 — completed SO of W0 and WO of W2 pointing at the draft are ignored; the draft is deleted.
    Rules: delete_invoice R2a, R3; F1."""
    assert w0.id < w1.id < w2.id
    s0 = mk_so(db, w0, "SO-0", u1.id, order_completed=True, invoice_id=di.id)
    wo2 = mk_wo(db, w2, "WO-2", status="COMPLETED", invoice_id=di.id)
    d_id = di.id
    result = delcall(db, M, di, u2)
    assert result.id == d_id
    assert reread_inv_or_none(db, d_id) is None
    s0_row = reread_row(db, SalesOrder, s0.id)
    assert s0_row is not None
    assert s0_row.invoice_id is None
    wo2_row = reread_row(db, WorkOrder, wo2.id)
    assert wo2_row is not None
    assert wo2_row.invoice_id is None


def test_del_20__completed_po_w2_and_eo_w0_ignored(db, M, w0, w1, w2, di, u1, u2):
    """AIM-DEL-20 — completed PO of W2 and EO of W0 pointing at the draft are ignored; the draft is deleted.
    Rules: delete_invoice R2a, R3; F1."""
    assert w0.id < w1.id < w2.id
    p2 = mk_po(db, w2, "PO-2", u1.id, stage="Complete", invoice_id=di.id)
    e0 = mk_eo(db, w0, "EXP-0", u1.id, completed_at=V0, invoice_id=di.id)
    d_id = di.id
    result = delcall(db, M, di, u2)
    assert result.id == d_id
    assert reread_inv_or_none(db, d_id) is None
    p2_row = reread_row(db, PurchaseOrder, p2.id)
    assert p2_row is not None
    assert p2_row.invoice_id is None
    e0_row = reread_row(db, ExpenseOrder, e0.id)
    assert e0_row is not None
    assert e0_row.invoice_id is None


def test_del_21__linked_by_type_and_id_only_not_frozen(db, M, w1, a1, u1, u2):
    """AIM-DEL-21 — a draft linked to a completed SO only through order_type / order_id is not frozen.
    Rules: delete_invoice R2a, R3; F1."""
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True)
    d = mk_di(db, w1, a1, u1.id, order_type="sales_order", order_id=s1.id)
    d_id = d.id
    result = delcall(db, M, d, u2)
    assert result.id == d_id
    assert reread_inv_or_none(db, d_id) is None
    s1_row = reread_row(db, SalesOrder, s1.id)
    assert s1_row is not None
    assert s1_row.invoice_id is None
    assert s1_row.order_completed is True


def test_del_22__not_draft_checked_before_freeze(db, M, w1, ci, u1, u2):
    """AIM-DEL-22 — a confirmed invoice of a completed SO gets the R2 "only draft" text, not LOCK.
    Rules: delete_invoice R2, R2a (check order); Errors row 2."""
    item = mk_item(db, ci, Decimal("100.00"))
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == ("Only draft invoices can be deleted. "
                                 "This invoice is 'confirmed'. Use void instead.")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert ids_list(items_of(db, ci.id)) == [item.id]
    assert reread_row(db, SalesOrder, s1.id).invoice_id == ci.id
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_23__freeze_checked_before_payment_history(db, M, w1, di, u1, u2):
    """AIM-DEL-23 — a frozen draft with a voided payment gets LOCK (freeze before the payment-history check).
    Rules: delete_invoice R2a, R4 (check order) [BUG-2730]; Errors row 3."""
    pay = mk_pay(db, di, Decimal("100.00"), voided=True, created_by=u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=di.id)
    sp = db.begin_nested()
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    sp.rollback()
    assert reread_inv_or_none(db, di.id) is not None
    assert reread_row(db, InvoicePayment, pay.id) is not None
    assert reread_row(db, SalesOrder, s1.id).invoice_id == di.id


def test_del_24__frozen_draft_with_payment_history_raises_something(db, M, w1, di, u1, u2):
    """AIM-DEL-24 — a completed SO's draft with a voided payment raises some exception; nothing is deleted.
    Rules: delete_invoice R2a, R4."""
    pay = mk_pay(db, di, Decimal("100.00"), voided=True, created_by=u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=di.id)
    with pytest.raises(Exception):
        with db.begin_nested():
            delcall(db, M, di, u2)
    assert reread_inv_or_none(db, di.id) is not None
    assert reread_row(db, InvoicePayment, pay.id) is not None
    assert reread_row(db, SalesOrder, s1.id).invoice_id == di.id


@pytest.mark.parametrize("stage", [
    pytest.param("complete", id="AIM-DEL-25"),
    pytest.param(" Complete", id="AIM-DEL-26"),
    pytest.param("Completed", id="AIM-DEL-27"),
])
def test_del_25_27__po_stage_near_miss_not_frozen(db, M, w1, di, u1, u2, stage):
    """AIM-DEL-25 / 26 / 27 — only the exact stage name "Complete" freezes: the draft is deleted.
    Rules: delete_invoice R2a, R3; F2 (exact name)."""
    p1 = mk_po(db, w1, "PO-1", u1.id, stage=stage, invoice_id=di.id)
    d_id = di.id
    result = delcall(db, M, di, u2)
    assert result.id == d_id
    assert reread_inv_or_none(db, d_id) is None
    assert reread_row(db, PurchaseOrder, p1.id).invoice_id is None


@pytest.mark.xfail(strict=True, reason=X2730)
def test_del_28__voided_completed_po_still_freezes(db, M, w1, di, u1, u2):
    """AIM-DEL-28 — a completed PO with voided=True still freezes its draft (only completion is read).
    Rules: delete_invoice R2a [BUG-2730]; Errors row 3; F3."""
    item = mk_item(db, di, Decimal("100.00"))
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Complete", voided=True, invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        delcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert ids_list(items_of(db, di.id)) == [item.id]
    assert reread_row(db, PurchaseOrder, p1.id).invoice_id == di.id
    assert_no_events(db, di.id)


# =========================================================================== #
# AccountInvoiceManager.confirm_invoice
# =========================================================================== #

def cfcall(db, M, inv_row, u2):
    return M.confirm_invoice(db, inv_row.id, inv_row.workspace_id, u2.id)


def test_cf_01__confirm_sets_amount_from_items(db, M, w1, a1, u1, u2):
    """AIM-CF-01 — confirming freezes invoice_amount at the item total and stamps last_synced_at.
    Rules: confirm_invoice R4, R5, R6."""
    d = mk_di(db, w1, a1, u1.id, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"),
              last_synced_at=None)
    mk_item(db, d, Decimal("150.00"))
    mk_item(db, d, Decimal("250.00"), line_number=2)
    result = cfcall(db, M, d, u2)
    assert result.id == d.id
    r = reread_inv(db, d.id)
    assert r.invoice_status == "confirmed"
    assert r.invoice_amount == Decimal("400.00")
    assert r.payment_status == "unpaid"
    assert r.last_synced_at == NOW
    assert_events(db, d.id, [
        ("confirmed", "Invoice finalized", u2.id, {"invoice_amount": "400.00"}),
    ])


def test_cf_02__confirm_recomputes_payment_status(db, M, w1, a1, u1, u2):
    """AIM-CF-02 — a paid_amount already present is re-evaluated against the new amount.
    Rules: confirm_invoice R4."""
    d = mk_di(db, w1, a1, u1.id, paid_amount=Decimal("100.00"))
    mk_item(db, d, Decimal("400.00"))
    result = cfcall(db, M, d, u2)
    assert result.id == d.id
    r = reread_inv(db, d.id)
    assert r.invoice_amount == Decimal("400.00")
    assert r.payment_status == "partial"


def test_cf_03__confirm_ignores_other_workspace_items(db, M, w1, w2, a1, u1, u2):
    """AIM-CF-03 — items with the same invoice id but another workspace are ignored.
    Rules: confirm_invoice R4."""
    d = mk_di(db, w1, a1, u1.id)
    mk_item(db, d, Decimal("0.10"))
    mk_item(db, d, Decimal("0.20"), line_number=2)
    mk_item(db, d, Decimal("999.00"), workspace_id=w2.id, line_number=3)
    result = cfcall(db, M, d, u2)
    assert result.id == d.id
    r = reread_inv(db, d.id)
    assert r.invoice_amount == Decimal("0.30")
    assert_events(db, d.id, [
        ("confirmed", "Invoice finalized", u2.id, {"invoice_amount": "0.30"}),
    ])


def test_cf_04__missing_id_404(db, M, w1, u2):
    """AIM-CF-04 — confirming an unknown id raises 404.
    Rules: confirm_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.confirm_invoice(db, NOID, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_cf_05__other_workspace_404(db, M, w1, w2, ax, u3, u2):
    """AIM-CF-05 — another workspace's draft is reported as not found and left alone.
    Rules: confirm_invoice R1; Errors row 1."""
    x = mk_di(db, w2, ax, u3.id)
    mk_item(db, x, Decimal("100.00"))
    with pytest.raises(HTTPException) as exc:
        M.confirm_invoice(db, x.id, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert reread_inv(db, x.id).invoice_status == "draft"
    assert_no_events(db, x.id)


def test_cf_06__voided_rejected(db, M, vi, u2):
    """AIM-CF-06 — a voided invoice cannot be confirmed.
    Rules: confirm_invoice R2; Errors row 2."""
    mk_item(db, vi, Decimal("100.00"))
    before = snap_inv(db, vi.id)
    with pytest.raises(HTTPException) as exc:
        cfcall(db, M, vi, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Voided invoices cannot be confirmed"
    assert snap_inv(db, vi.id) == before
    r = reread_inv(db, vi.id)
    assert r.invoice_amount == Decimal("1000.00")
    assert r.invoice_status == "voided"
    assert_no_events(db, vi.id)


def test_cf_07__already_confirmed_rejected(db, M, w1, a1, u1, u2):
    """AIM-CF-07 — confirming an already-confirmed invoice is rejected unchanged.
    Rules: confirm_invoice R3; Errors row 3."""
    c = mk_ci(db, w1, a1, u1.id, invoice_amount=Decimal("1000.00"), last_synced_at=L0)
    mk_item(db, c, Decimal("100.00"))
    with pytest.raises(HTTPException) as exc:
        cfcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice is already confirmed"
    r = reread_inv(db, c.id)
    assert r.invoice_amount == Decimal("1000.00")
    assert r.last_synced_at == L0
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason="BUG-628: a draft with zero line items confirms successfully at 0.00/paid")
def test_cf_08__no_items_rejected(db, M, w1, a1, u1, u2):
    """AIM-CF-08 — confirming a draft with no line items should 400; today it confirms at 0.00.
    Rules: confirm_invoice R4 [BUG-628]; Errors row 4."""
    d = mk_di(db, w1, a1, u1.id, invoice_amount=Decimal("1000.00"))
    with pytest.raises(HTTPException) as exc:
        cfcall(db, M, d, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Add at least one line item before confirming"
    r = reread_inv(db, d.id)
    assert r.invoice_status == "draft"
    assert r.invoice_amount == Decimal("1000.00")
    assert r.payment_status == "unpaid"
    assert r.last_synced_at is None
    assert_no_events(db, d.id)


@pytest.mark.xfail(strict=True, reason="BUG-633: confirm_invoice does not stamp updated_by")
def test_cf_09__stamps_updated_by(db, M, di, u2):
    """AIM-CF-09 — confirming should stamp updated_by; today it does not.
    Rules: confirm_invoice R5 [BUG-633]."""
    mk_item(db, di, Decimal("100.00"))
    result = cfcall(db, M, di, u2)
    assert result.id == di.id
    assert reread_inv(db, di.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason="BUG-621: confirm_invoice reads the invoice without FOR UPDATE")
def test_cf_10__locks_invoice(db, M, engine, di, u2):
    """AIM-CF-10 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: confirm_invoice R1 [BUG-621]."""
    mk_item(db, di, Decimal("100.00"))
    with SQLCapture(engine) as cap:
        result = cfcall(db, M, di, u2)
    assert result.id == di.id
    assert cap.locks_invoice()
    assert reread_inv(db, di.id).invoice_status == "confirmed"


# =========================================================================== #
# AccountInvoiceManager.revert_to_draft
# =========================================================================== #

def rvcall(db, M, inv_row, u2):
    return M.revert_to_draft(db, inv_row.id, inv_row.workspace_id, u2.id)


def test_rv_01__revert_happy_path(db, M, w1, a1, u1, u2):
    """AIM-RV-01 — reverting sets status to draft, leaves amount/payment status, logs one event.
    Rules: revert_to_draft R5, R6."""
    c = mk_ci(db, w1, a1, u1.id, invoice_amount=Decimal("400.00"), paid_amount=Decimal("0.00"),
              payment_status="unpaid", last_synced_at=L0)
    result = rvcall(db, M, c, u2)
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.invoice_status == "draft"
    assert r.invoice_amount == Decimal("400.00")
    assert r.payment_status == "unpaid"
    assert r.last_synced_at == L0
    assert_events(db, c.id, [
        ("reverted_to_draft", "Reverted to draft", u2.id, None),
    ])


def test_rv_02__null_paid_amount_allowed(db, M, w1, a1, u1, u2):
    """AIM-RV-02 — a null paid_amount does not block reverting.
    Rules: revert_to_draft R4."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=None)
    result = rvcall(db, M, c, u2)
    assert result.id == c.id
    assert reread_inv(db, c.id).invoice_status == "draft"


def test_rv_03__voided_payments_do_not_block(db, M, ci, u1, u2):
    """AIM-RV-03 — voided payments do not count toward "active payments".
    Rules: revert_to_draft R4."""
    # Convention PAY: "A voided setup payment has voided_by = U1" (U1 created every setup row).
    mk_pay(db, ci, Decimal("100.00"), voided=True, created_by=u1.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


def test_rv_04__active_payments_block(db, M, w1, a1, u1, u2):
    """AIM-RV-04 — a positive paid_amount blocks reverting.
    Rules: revert_to_draft R4; Errors row 6."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("0.01"), payment_status="partial")
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == ("Cannot revert to draft — invoice has active payments. "
                                 "Void all payments first.")
    assert reread_inv(db, c.id).invoice_status == "confirmed"
    assert_no_events(db, c.id)


def test_rv_05__receiving_started_blocks(db, M, w1, a1, u1, u2):
    """AIM-RV-05 — receiving_started blocks reverting (400 with a receiving text; exact text in RV-13).
    Rules: revert_to_draft R3; Errors row 5."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("0.00"))
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail.startswith("Cannot revert to draft — ")
    assert "receiv" in exc.value.detail
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.updated_by is None
    assert_no_events(db, c.id)


def test_rv_06__receiving_checked_before_payments(db, M, w1, a1, u1, u2):
    """AIM-RV-06 — the receiving check is reported even when payments are also active (exact text in RV-14).
    Rules: revert_to_draft R3, R4 (check order); Errors row 5."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("100.00"), payment_status="partial")
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert "receiv" in exc.value.detail
    assert "active payments" not in exc.value.detail
    assert_session_clean(db)
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.paid_amount == Decimal("100.00")
    assert r.updated_by is None
    assert_no_events(db, c.id)


def test_rv_07__draft_rejected(db, M, di, u2):
    """AIM-RV-07 — a draft cannot be reverted (not confirmed).
    Rules: revert_to_draft R2; Errors row 2."""
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."
    assert snap_inv(db, di.id) == before
    r = reread_inv(db, di.id)
    assert r.invoice_status == "draft"
    assert r.updated_by is None
    assert_no_events(db, di.id)


def test_rv_08__voided_rejected(db, M, vi, u2):
    """AIM-RV-08 — a voided invoice cannot be reverted.
    Rules: revert_to_draft R2; Errors row 2."""
    before = snap_inv(db, vi.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, vi, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only confirmed invoices can be reverted to draft. Current status: 'voided'."
    assert snap_inv(db, vi.id) == before
    assert_no_events(db, vi.id)


def test_rv_09__missing_id_404(db, M, w1, u2):
    """AIM-RV-09 — reverting an unknown id raises 404.
    Rules: revert_to_draft R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, NOID, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_rv_10__other_workspace_404(db, M, w1, w2, ax, u3, u2):
    """AIM-RV-10 — another workspace's confirmed invoice is reported as not found.
    Rules: revert_to_draft R1; Errors row 1."""
    x = mk_ci(db, w2, ax, u3.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, x.id, w1.id, u2.id)
    assert exc.value.status_code == 404
    assert reread_inv(db, x.id).invoice_status == "confirmed"
    assert_no_events(db, x.id)


@pytest.mark.xfail(strict=True, reason="BUG-633: revert_to_draft does not stamp updated_by")
def test_rv_11__stamps_updated_by(db, M, ci, u2):
    """AIM-RV-11 — reverting should stamp updated_by; today it does not.
    Rules: revert_to_draft R5 [BUG-633]."""
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason="BUG-621: revert_to_draft reads the invoice without FOR UPDATE")
def test_rv_12__locks_invoice(db, M, engine, ci, u2):
    """AIM-RV-12 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: revert_to_draft R1 [BUG-621]."""
    with SQLCapture(engine) as cap:
        result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert cap.locks_invoice()
    assert reread_inv(db, ci.id).invoice_status == "draft"


# --- Revision 7: receiving text (R3a), credit notes (R2a) and the freeze (R2b) ---

@pytest.mark.xfail(strict=True, reason=X2736)
def test_rv_13__receiving_text_exact(db, M, w1, a1, u1, u2):
    """AIM-RV-13 — the receiving refusal uses RCVTXT; today it advises zeroing received quantities.
    Rules: revert_to_draft R3a [BUG-2736]; Errors row 5."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("0.00"))
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == RCVTXT
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2736)
def test_rv_14__receiving_text_exact_with_payments(db, M, w1, a1, u1, u2):
    """AIM-RV-14 — with payments too, the refusal is still RCVTXT (receiving before payments).
    Rules: revert_to_draft R3, R3a, R4 [BUG-2736]; Errors row 5."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("100.00"), payment_status="partial")
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == RCVTXT
    assert_session_clean(db)
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.paid_amount == Decimal("100.00")
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_15__invoice_of_completed_po_frozen(db, M, w1, a1, u1, u2):
    """AIM-RV-15 — the confirmed invoice of a completed PO (no receiving, nothing paid) is refused with LOCK.
    Rules: revert_to_draft R2b [BUG-2730]; Errors row 4; F1, F2, F5."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=False, paid_amount=Decimal("0.00"))
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.updated_by is None
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_16__invoice_of_completed_so_frozen(db, M, w1, ci, u1, u2):
    """AIM-RV-16 — the confirmed invoice of a completed sales order is refused with LOCK("sales order").
    Rules: revert_to_draft R2b [BUG-2730]; Errors row 4; F2, F5."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_17__invoice_of_completed_eo_frozen(db, M, w1, ci, u1, u2):
    """AIM-RV-17 — the confirmed invoice of a completed expense order is refused with LOCK("expense order").
    Rules: revert_to_draft R2b [BUG-2730]; Errors row 4; F2, F5."""
    mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("expense order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_18__invoice_of_completed_wo_frozen(db, M, w1, ci, u1, u2):
    """AIM-RV-18 — the confirmed invoice of a completed work order is refused with LOCK("work order").
    Rules: revert_to_draft R2b [BUG-2730]; Errors row 4; F2, F5."""
    mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("work order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


def test_rv_19__po_at_receiving_not_frozen(db, M, w1, ci, u1, u2):
    """AIM-RV-19 — a PO at stage Receiving is not completed: the revert goes ahead with its event.
    Rules: revert_to_draft R2b, R5; F2."""
    mk_po(db, w1, "PO-1", u1.id, stage="Receiving", invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"
    assert_events(db, ci.id, [
        ("reverted_to_draft", "Reverted to draft", u2.id, None),
    ])


def test_rv_20__completed_so_w0_and_wo_w2_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-RV-20 — completed SO of W0 and WO of W2 pointing at the invoice are ignored.
    Rules: revert_to_draft R2b, R5; F1."""
    assert w0.id < w1.id < w2.id
    mk_so(db, w0, "SO-0", u1.id, order_completed=True, invoice_id=ci.id)
    mk_wo(db, w2, "WO-2", status="COMPLETED", invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


def test_rv_21__completed_po_w2_and_eo_w0_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-RV-21 — completed PO of W2 and EO of W0 pointing at the invoice are ignored.
    Rules: revert_to_draft R2b, R5; F1."""
    assert w0.id < w1.id < w2.id
    mk_po(db, w2, "PO-2", u1.id, stage="Complete", invoice_id=ci.id)
    mk_eo(db, w0, "EXP-0", u1.id, completed_at=V0, invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


def test_rv_22__linked_by_type_and_id_only_not_frozen(db, M, w1, a1, u1, u2):
    """AIM-RV-22 — an invoice linked to a completed WO only through order_type / order_id is not frozen.
    Rules: revert_to_draft R2b, R5; F1."""
    wo1 = mk_wo(db, w1, "WO-1", status="COMPLETED")
    c = mk_ci(db, w1, a1, u1.id, order_type="work_order", order_id=wo1.id)
    result = rvcall(db, M, c, u2)
    assert result.id == c.id
    assert reread_inv(db, c.id).invoice_status == "draft"


@pytest.mark.parametrize("wo_status", [
    pytest.param("IN_PROGRESS", id="AIM-RV-23"),
    pytest.param("VOIDED", id="AIM-RV-24"),
])
def test_rv_23_24__work_order_not_completed_not_frozen(db, M, w1, ci, u1, u2, wo_status):
    """AIM-RV-23 / AIM-RV-24 — a work order IN_PROGRESS or VOIDED is not completed: the revert goes ahead.
    Rules: revert_to_draft R2b, R5; F2 (RV-24 also F3)."""
    mk_wo(db, w1, "WO-1", status=wo_status, invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


@pytest.mark.parametrize("stage", [
    pytest.param("complete", id="AIM-RV-25"),
    pytest.param(" Complete", id="AIM-RV-26"),
    pytest.param("Completed", id="AIM-RV-27"),
])
def test_rv_25_27__po_stage_near_miss_not_frozen(db, M, w1, ci, u1, u2, stage):
    """AIM-RV-25 / 26 / 27 — only the exact stage name "Complete" freezes: "complete", " Complete", "Completed" do not.
    Rules: revert_to_draft R2b, R5; F2 (exact name)."""
    mk_po(db, w1, "PO-1", u1.id, stage=stage, invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_28__kind_of_the_completed_order_not_of_the_first(db, M, w1, ci, u1, u2):
    """AIM-RV-28 — PO (Draft) and completed WO both point at the invoice: LOCK names the work order.
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=ci.id)
    mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("work order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_29__sales_before_work(db, M, w1, ci, u1, u2):
    """AIM-RV-29 — completed WO and completed SO: LOCK names the sales order (F5 order).
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=ci.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_30__expense_before_work(db, M, w1, ci, u1, u2):
    """AIM-RV-30 — completed WO and completed EO: LOCK names the expense order (F5 order).
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=ci.id)
    mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("expense order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_31__purchase_before_sales(db, M, w1, ci, u1, u2):
    """AIM-RV-31 — completed SO and completed PO: LOCK names the purchase order (F5 order).
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


def test_rv_32__not_confirmed_checked_before_freeze(db, M, w1, di, u1, u2):
    """AIM-RV-32 — a draft of a completed SO gets the R2 "only confirmed" text, not LOCK.
    Rules: revert_to_draft R2, R2b (check order); Errors row 2."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, di, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_33__freeze_checked_before_receiving(db, M, w1, a1, u1, u2):
    """AIM-RV-33 — a completed PO's invoice with receiving_started gets LOCK, not the receiving text.
    Rules: revert_to_draft R2b, R3 (check order) [BUG-2730]; Errors row 4."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("0.00"))
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    assert_no_events(db, c.id)


def test_rv_34__completed_po_with_receiving_refused(db, M, w1, a1, u1, u2):
    """AIM-RV-34 — a completed PO's invoice with receiving_started is refused (either text) and stays unchanged.
    Rules: revert_to_draft R2b, R3."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True, paid_amount=Decimal("0.00"))
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.receiving_started is True
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_35__freeze_checked_before_payments(db, M, w1, a1, u1, u2):
    """AIM-RV-35 — a completed SO's invoice with an active payment gets LOCK, not the payments text.
    Rules: revert_to_draft R2b, R4 (check order) [BUG-2730]; Errors row 4."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("100.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("100.00"), created_by=u1.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    assert reread_row(db, InvoicePayment, pa.id).is_voided is False
    assert_no_events(db, c.id)


def test_rv_36__completed_so_with_payments_refused(db, M, w1, a1, u1, u2):
    """AIM-RV-36 — a completed SO's invoice with an active payment is refused (either text); payment untouched.
    Rules: revert_to_draft R2b, R4."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("100.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("100.00"), created_by=u1.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, c, u2)
    assert exc.value.status_code == 400
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    assert reread_row(db, InvoicePayment, pa.id).is_voided is False
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2733)
def test_rv_37__po_return_credit_note_not_revertible(db, M, w1, a1, u1, u2):
    """AIM-RV-37 — a PO return credit note (order not completed) is refused with CNTXT.
    Rules: revert_to_draft R2a [BUG-2733]; Errors row 3; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, receiving_started=False, paid_amount=Decimal("0.00"))
    mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == CNTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    r = reread_inv(db, cn.id)
    assert r.invoice_status == "confirmed"
    assert r.updated_by is None
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2733)
def test_rv_38__so_return_credit_note_not_revertible(db, M, w1, a1, u1, u2):
    """AIM-RV-38 — an SO return credit note of a completed SO is refused with CNTXT (not LOCK).
    Rules: revert_to_draft R2a [BUG-2733]; Errors row 3; F1, F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == CNTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2733)
def test_rv_39__credit_note_checked_before_freeze(db, M, w1, a1, u1, u2):
    """AIM-RV-39 — a credit note that is also the completed SO's invoice gets CNTXT (credit note before freeze).
    Rules: revert_to_draft R2a, R2b (check order) [BUG-2733]; Errors row 3."""
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id)
    s1.invoice_id = cn.id
    db.flush()
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == CNTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2733)
def test_rv_40__credit_note_checked_before_receiving(db, M, w1, a1, u1, u2):
    """AIM-RV-40 — a PO credit note with receiving_started gets CNTXT, not the receiving text.
    Rules: revert_to_draft R2a, R3 (check order) [BUG-2733]; Errors row 3."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, receiving_started=True)
    mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == CNTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert_no_events(db, cn.id)


def test_rv_41__credit_note_with_receiving_refused(db, M, w1, a1, u1, u2):
    """AIM-RV-41 — a PO credit note with receiving_started is refused (either text) and stays unchanged.
    Rules: revert_to_draft R2a, R3."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, receiving_started=True)
    mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_inv(db, cn.id).invoice_status == "confirmed"
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2733)
def test_rv_42__credit_note_checked_before_payments(db, M, w1, a1, u1, u2):
    """AIM-RV-42 — an SO credit note with an active payment gets CNTXT, not the payments text.
    Rules: revert_to_draft R2a, R4 (check order) [BUG-2733]; Errors row 3."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, paid_amount=Decimal("100.00"), payment_status="partial")
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id)
    pa = mk_pay(db, cn, Decimal("100.00"), created_by=u1.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == CNTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_row(db, InvoicePayment, pa.id).is_voided is False
    assert_no_events(db, cn.id)


def test_rv_43__credit_note_with_payments_refused(db, M, w1, a1, u1, u2):
    """AIM-RV-43 — an SO credit note with an active payment is refused (either text); payment untouched.
    Rules: revert_to_draft R2a, R4."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, paid_amount=Decimal("100.00"), payment_status="partial")
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id)
    pa = mk_pay(db, cn, Decimal("100.00"), created_by=u1.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_row(db, InvoicePayment, pa.id).is_voided is False
    assert_no_events(db, cn.id)


def test_rv_44__not_confirmed_checked_before_credit_note(db, M, w1, a1, u1, u2):
    """AIM-RV-44 — a draft credit note gets the R2 "only confirmed" text, not CNTXT.
    Rules: revert_to_draft R2, R2a (check order); Errors row 2."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, invoice_status="draft")
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.revert_to_draft(db, cn.id, w1.id, u2.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert_no_events(db, cn.id)


def test_rv_45__return_rows_of_w0_and_w2_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-RV-45 — POR of W0 and SOR of W2 pointing at the invoice do not make it a credit note.
    Rules: revert_to_draft R2a, R5; F6."""
    assert w0.id < w1.id < w2.id
    mk_por(db, w0, u1.id, invoice_id=ci.id)
    mk_sor(db, w2, u1.id, invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


def test_rv_46__return_rows_of_w2_and_w0_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-RV-46 — POR of W2 and SOR of W0 pointing at the invoice do not make it a credit note.
    Rules: revert_to_draft R2a, R5; F6."""
    assert w0.id < w1.id < w2.id
    mk_por(db, w2, u1.id, invoice_id=ci.id)
    mk_sor(db, w0, u1.id, invoice_id=ci.id)
    result = rvcall(db, M, ci, u2)
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "draft"


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_47__sales_before_expense(db, M, w1, ci, u1, u2):
    """AIM-RV-47 — completed SO and completed EO: LOCK names the sales order (F5 order).
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=ci.id)
    mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2730)
def test_rv_48__purchase_before_expense(db, M, w1, ci, u1, u2):
    """AIM-RV-48 — completed PO and completed EO: LOCK names the purchase order (F5 order).
    Rules: revert_to_draft R2b [BUG-2730]; F5 (kind)."""
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=ci.id)
    mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        rvcall(db, M, ci, u2)
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


# =========================================================================== #
# AccountInvoiceManager.void_invoice
# =========================================================================== #

def vdcall(db, M, inv_row, u2, note):
    return M.void_invoice(db, inv_row.id, inv_row.workspace_id, u2.id, note)


def test_vd_01__void_voids_active_payments_only(db, M, w1, a1, u1, u2):
    """AIM-VD-01 — voiding voids only this invoice's active payments, leaves others untouched.
    Rules: void_invoice R4, R5, R7."""
    c = mk_ci(db, w1, a1, u1.id, invoice_amount=Decimal("1000.00"), paid_amount=Decimal("600.00"),
              payment_status="partial")
    pa = mk_pay(db, c, Decimal("400.00"), created_by=u1.id)
    pb = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    pc = mk_pay(db, c, Decimal("150.00"), voided=True, created_by=u1.id)
    j = mk_ci(db, w1, a1, u1.id)
    pj = mk_pay(db, j, Decimal("50.00"), created_by=u1.id)
    result = vdcall(db, M, c, u2, "Damaged goods")
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.invoice_status == "voided"
    assert r.void_note == "Damaged goods"
    assert r.paid_amount == Decimal("0.00")
    assert r.payment_status == "unpaid"
    assert r.invoice_amount == Decimal("1000.00")
    db.expire_all()
    note = f"Automatically voided — invoice #{c.id} was voided. Reason: Damaged goods"
    for p in (pa, pb):
        row = db.get(InvoicePayment, p.id)
        assert row.is_voided is True
        assert row.voided_at == NOW
        assert row.voided_by == u2.id
        assert row.void_note == note
    row_c = db.get(InvoicePayment, pc.id)
    assert row_c.voided_at == V0
    assert row_c.voided_by == u1.id
    assert row_c.void_note == "manual void"
    assert db.get(InvoicePayment, pj.id).is_voided is False
    assert_events(db, c.id, [
        ("voided", "Invoice voided", u2.id,
         {"prior_status": "confirmed", "payments_voided": 2, "void_note": "Damaged goods"}),
    ])
    assert_no_events(db, j.id)


def test_vd_02__void_with_no_payments(db, M, ci, u2):
    """AIM-VD-02 — voiding an invoice with no payments logs payments_voided=0.
    Rules: void_invoice R4, R7."""
    result = vdcall(db, M, ci, u2, "Wrong vendor")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "voided"
    assert_events(db, ci.id, [
        ("voided", "Invoice voided", u2.id,
         {"prior_status": "confirmed", "payments_voided": 0, "void_note": "Wrong vendor"}),
    ])


def test_vd_03__already_voided_rejected(db, M, vi, u2):
    """AIM-VD-03 — voiding an already-voided invoice is rejected unchanged.
    Rules: void_invoice R2; Errors row 2."""
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, vi, u2, "Again")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice is already voided"
    assert reread_inv(db, vi.id).void_note == "Old reason"
    assert_no_events(db, vi.id)


def test_vd_04__draft_rejected(db, M, di, u2):
    """AIM-VD-04 — a draft cannot be voided and its payments stay untouched.
    Rules: void_invoice R3; Errors row 3."""
    p = mk_pay(db, di, Decimal("100.00"), created_by=u2.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, di, u2, "x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Draft invoices cannot be voided — delete them instead"
    assert reread_inv(db, di.id).invoice_status == "draft"
    assert db.get(InvoicePayment, p.id).is_voided is False
    assert_no_events(db, di.id)


def test_vd_05__missing_id_404(db, M, w1, u2):
    """AIM-VD-05 — voiding an unknown id raises 404.
    Rules: void_invoice R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, NOID, w1.id, u2.id, "x")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_vd_06__other_workspace_404(db, M, w1, w2, ax, u3, u2):
    """AIM-VD-06 — another workspace's confirmed invoice is reported as not found, payment untouched.
    Rules: void_invoice R1; Errors row 1."""
    x = mk_ci(db, w2, ax, u3.id)
    p = mk_pay(db, x, Decimal("100.00"), created_by=u3.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, x.id, w1.id, u2.id, "x")
    assert exc.value.status_code == 404
    assert reread_inv(db, x.id).invoice_status == "confirmed"
    assert db.get(InvoicePayment, p.id).is_voided is False
    assert_no_events(db, x.id)


@pytest.mark.xfail(strict=True, reason="BUG-633: void_invoice does not stamp updated_by")
def test_vd_07__stamps_updated_by(db, M, ci, u2):
    """AIM-VD-07 — voiding should stamp updated_by; today it does not.
    Rules: void_invoice R6 [BUG-633]."""
    result = vdcall(db, M, ci, u2, "x")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason="BUG-621: void_invoice reads the invoice without FOR UPDATE")
def test_vd_08__locks_invoice(db, M, engine, ci, u2):
    """AIM-VD-08 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: void_invoice R1 [BUG-621]."""
    with SQLCapture(engine) as cap:
        result = vdcall(db, M, ci, u2, "x")
    assert result.id == ci.id
    assert cap.locks_invoice()
    assert reread_inv(db, ci.id).invoice_status == "voided"


def test_vd_09__void_note_stored_as_given(db, M, ci, u2):
    """AIM-VD-09 — the manager stores whatever void_note it receives, untrimmed.
    Rules: void_invoice R8."""
    result = vdcall(db, M, ci, u2, "  spaced note  ")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).void_note == "  spaced note  "


def test_vd_10__schema_rejects_empty_note():
    """AIM-VD-10 — VoidInvoiceRequest rejects an empty void_note.
    Rules: void_invoice R8."""
    with pytest.raises(ValidationError):
        VoidInvoiceRequest(void_note="")


def test_vd_11__schema_accepts_note():
    """AIM-VD-11 — VoidInvoiceRequest accepts and keeps a normal void_note.
    Rules: void_invoice R8."""
    data = VoidInvoiceRequest(void_note="Damaged")
    assert data.void_note == "Damaged"


@pytest.mark.xfail(strict=True, reason="BUG-626: VoidInvoiceRequest accepts a whitespace-only void_note")
def test_vd_12__schema_rejects_whitespace_only_note():
    """AIM-VD-12 — a whitespace-only void_note should 422; today it is accepted.
    Rules: void_invoice R8 [BUG-626]; Errors row 6."""
    with pytest.raises(ValidationError):
        VoidInvoiceRequest(void_note="   ")


@pytest.mark.xfail(strict=True, reason="BUG-626: VoidInvoiceRequest does not trim void_note")
def test_vd_13__schema_trims_note():
    """AIM-VD-13 — void_note should be trimmed by the schema; today it is kept as typed.
    Rules: void_invoice R8 [BUG-626]."""
    data = VoidInvoiceRequest(void_note="  Damaged  ")
    assert data.void_note == "Damaged"


# --- Revision 7: completed-order freeze (R3a) and credit notes (R3b) on void_invoice ---

@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_14__invoice_of_completed_po_frozen(db, M, w1, a1, u1, u2):
    """AIM-VD-14 — voiding a completed PO's invoice is refused with LOCK; invoice and payment untouched.
    Rules: void_invoice R3a [BUG-2731]; Errors row 4; F1, F2, F5."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("200.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, c, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.paid_amount == Decimal("200.00")
    assert r.payment_status == "partial"
    assert r.void_note is None
    assert r.updated_by is None
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    assert p.voided_by is None
    assert p.void_note is None
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_15__invoice_of_completed_so_frozen(db, M, w1, a1, u1, u2):
    """AIM-VD-15 — voiding a completed SO's invoice is refused with LOCK("sales order"); payment untouched.
    Rules: void_invoice R3a [BUG-2731]; Errors row 4; F2, F5."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("200.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, c, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_16__invoice_of_completed_eo_frozen(db, M, w1, a1, u1, u2):
    """AIM-VD-16 — voiding a completed EO's invoice is refused with LOCK("expense order"); payment untouched.
    Rules: void_invoice R3a [BUG-2731]; Errors row 4; F2, F5."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("200.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0, invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, c, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("expense order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    assert_no_events(db, c.id)


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_17__invoice_of_completed_wo_frozen(db, M, w1, a1, u1, u2):
    """AIM-VD-17 — voiding a completed WO's invoice is refused with LOCK("work order"); payment untouched.
    Rules: void_invoice R3a [BUG-2731]; Errors row 4; F2, F5."""
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("200.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    mk_wo(db, w1, "WO-1", status="COMPLETED", invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, c, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("work order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    assert_no_events(db, c.id)


def test_vd_18__po_at_receiving_not_frozen(db, M, w1, ci, u1, u2):
    """AIM-VD-18 — a PO at stage Receiving is not completed: the void goes ahead with its event.
    Rules: void_invoice R3a, R4, R5; F2."""
    mk_po(db, w1, "PO-1", u1.id, stage="Receiving", invoice_id=ci.id)
    result = vdcall(db, M, ci, u2, "Damaged")
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.invoice_status == "voided"
    assert r.void_note == "Damaged"
    assert_events(db, ci.id, [
        ("voided", "Invoice voided", u2.id,
         {"prior_status": "confirmed", "payments_voided": 0, "void_note": "Damaged"}),
    ])


def test_vd_19__completed_so_w0_and_wo_w2_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-VD-19 — completed SO of W0 and WO of W2 pointing at the invoice are ignored; the void goes ahead.
    Rules: void_invoice R3a, R5; F1."""
    assert w0.id < w1.id < w2.id
    mk_so(db, w0, "SO-0", u1.id, order_completed=True, invoice_id=ci.id)
    mk_wo(db, w2, "WO-2", status="COMPLETED", invoice_id=ci.id)
    result = vdcall(db, M, ci, u2, "Damaged")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "voided"


def test_vd_20__completed_po_w2_and_eo_w0_ignored(db, M, w0, w1, w2, ci, u1, u2):
    """AIM-VD-20 — completed PO of W2 and EO of W0 pointing at the invoice are ignored; the void goes ahead.
    Rules: void_invoice R3a, R5; F1."""
    assert w0.id < w1.id < w2.id
    mk_po(db, w2, "PO-2", u1.id, stage="Complete", invoice_id=ci.id)
    mk_eo(db, w0, "EXP-0", u1.id, completed_at=V0, invoice_id=ci.id)
    result = vdcall(db, M, ci, u2, "Damaged")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "voided"


def test_vd_21__linked_by_type_and_id_only_not_frozen(db, M, w1, a1, u1, u2):
    """AIM-VD-21 — an invoice linked to a completed EO only through order_type / order_id is not frozen.
    Rules: void_invoice R3a, R5; F1."""
    e1 = mk_eo(db, w1, "EXP-1", u1.id, completed_at=V0)
    c = mk_ci(db, w1, a1, u1.id, order_type="expense_order", order_id=e1.id)
    result = vdcall(db, M, c, u2, "Damaged")
    assert result.id == c.id
    assert reread_inv(db, c.id).invoice_status == "voided"


def test_vd_22__already_voided_checked_before_freeze(db, M, w1, vi, u1, u2):
    """AIM-VD-22 — a voided invoice of a completed SO gets "already voided", not LOCK.
    Rules: void_invoice R2, R3a (check order); Errors row 2."""
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=vi.id)
    before = snap_inv(db, vi.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, vi, u2, "Again")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice is already voided"
    assert_session_clean(db)
    assert snap_inv(db, vi.id) == before
    assert reread_inv(db, vi.id).void_note == "Old reason"
    assert_no_events(db, vi.id)


def test_vd_23__draft_checked_before_freeze(db, M, w1, di, u1, u2):
    """AIM-VD-23 — a draft of a completed SO gets the R3 draft text, not LOCK; its payment untouched.
    Rules: void_invoice R3, R3a (check order); Errors row 3."""
    pa = mk_pay(db, di, Decimal("100.00"), created_by=u1.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=di.id)
    before = snap_inv(db, di.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, di, u2, "x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Draft invoices cannot be voided — delete them instead"
    assert_session_clean(db)
    assert snap_inv(db, di.id) == before
    assert reread_row(db, InvoicePayment, pa.id).is_voided is False
    assert_no_events(db, di.id)


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_24__voided_completed_po_still_freezes(db, M, w1, ci, u1, u2):
    """AIM-VD-24 — a completed PO with voided=True still freezes its invoice (only completion is read).
    Rules: void_invoice R3a [BUG-2731]; F3."""
    mk_po(db, w1, "PO-1", u1.id, stage="Complete", voided=True, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, ci, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("purchase order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_25__deleted_completed_wo_still_freezes(db, M, w1, ci, u1, u2):
    """AIM-VD-25 — a completed WO with is_deleted=True still freezes its invoice (only completion is read).
    Rules: void_invoice R3a [BUG-2731]; F3."""
    mk_wo(db, w1, "WO-1", status="COMPLETED", is_deleted=True, invoice_id=ci.id)
    before = snap_inv(db, ci.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, ci, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("work order")
    assert_session_clean(db)
    assert snap_inv(db, ci.id) == before
    assert_no_events(db, ci.id)


def test_vd_26__po_credit_note_voidable_on_completed_po(db, M, w1, a1, u1, u2):
    """AIM-VD-26 — a PO return credit note is voided (with its payment) even though the PO is completed.
    Rules: void_invoice R3b, R3c, R4, R5, R7; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, paid_amount=Decimal("50.00"), payment_status="partial")
    mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="pending")
    pa = mk_pay(db, cn, Decimal("50.00"), created_by=u1.id)
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    r = reread_inv(db, cn.id)
    assert r.invoice_status == "voided"
    assert r.void_note == "Wrong qty"
    assert r.paid_amount == Decimal("0.00")
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is True
    assert p.voided_by == u2.id
    assert_events(db, cn.id, [
        ("voided", "Invoice voided", u2.id,
         {"prior_status": "confirmed", "payments_voided": 1, "void_note": "Wrong qty"}),
    ])
    assert reread_inv(db, oi.id).invoice_status == "confirmed"


def test_vd_27__so_credit_note_voidable_on_completed_so(db, M, w1, a1, u1, u2):
    """AIM-VD-27 — an SO return credit note is voided even though the SO is completed; the order's invoice stays.
    Rules: void_invoice R3b, R3c, R5; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="pending")
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    r = reread_inv(db, cn.id)
    assert r.invoice_status == "voided"
    assert r.void_note == "Wrong qty"
    assert reread_inv(db, oi.id).invoice_status == "confirmed"


def test_vd_28__credit_note_never_frozen_even_as_order_invoice(db, M, w1, a1, u1, u2):
    """AIM-VD-28 — a credit note that is also the completed SO's own invoice is still voidable.
    Rules: void_invoice R3b, R3a, R3c, R5; F6."""
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="pending")
    s1.invoice_id = cn.id
    db.flush()
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert reread_inv(db, cn.id).invoice_status == "voided"


@pytest.mark.xfail(strict=True, reason=X2731)
def test_vd_29__other_workspace_return_rows_do_not_make_credit_note(db, M, w0, w1, w2, a1, u1, u2):
    """AIM-VD-29 — POR of W0 and SOR of W2 do not make a frozen invoice a voidable credit note; payment stays.
    Rules: void_invoice R3a, R3b [BUG-2731]; Errors row 4; F1, F6."""
    assert w0.id < w1.id < w2.id
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("200.00"), payment_status="partial")
    pa = mk_pay(db, c, Decimal("200.00"), created_by=u1.id)
    mk_so(db, w1, "SO-1", u1.id, order_completed=True, invoice_id=c.id)
    mk_por(db, w0, u1.id, invoice_id=c.id)
    mk_sor(db, w2, u1.id, invoice_id=c.id)
    before = snap_inv(db, c.id)
    with pytest.raises(HTTPException) as exc:
        vdcall(db, M, c, u2, "Damaged")
    assert exc.value.status_code == 400
    assert exc.value.detail == LOCK("sales order")
    assert_session_clean(db)
    assert snap_inv(db, c.id) == before
    r = reread_inv(db, c.id)
    assert r.invoice_status == "confirmed"
    assert r.paid_amount == Decimal("200.00")
    assert r.void_note is None
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    assert p.voided_by is None
    assert_no_events(db, c.id)


@pytest.mark.parametrize("stage", [
    pytest.param("complete", id="AIM-VD-30"),
    pytest.param(" Complete", id="AIM-VD-31"),
    pytest.param("Completed", id="AIM-VD-32"),
])
def test_vd_30_32__po_stage_near_miss_not_frozen(db, M, w1, ci, u1, u2, stage):
    """AIM-VD-30 / 31 / 32 — only the exact stage name "Complete" freezes: the void goes ahead.
    Rules: void_invoice R3a, R5; F2 (exact name)."""
    mk_po(db, w1, "PO-1", u1.id, stage=stage, invoice_id=ci.id)
    result = vdcall(db, M, ci, u2, "Damaged")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).invoice_status == "voided"


# --- Revision 9: void_invoice R3c — a credit note's return decides its void (BUG-2788) ---

@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_33__po_credit_note_void_cancels_pending_return(db, M, w1, a1, u1, u2):
    """AIM-VD-33 — voiding a PO return's credit note also voids its pending return (status voided, paid False).
    Rules: void_invoice R3c [BUG-2788]; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, invoice_amount=Decimal("1000.00"),
               paid_amount=Decimal("1000.00"), payment_status="paid")
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="pending", paid=True)
    pa = mk_pay(db, cn, Decimal("1000.00"), created_by=u1.id)
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    c = reread_inv(db, cn.id)
    assert c.invoice_status == "voided"
    assert c.paid_amount == Decimal("0.00")
    assert reread_row(db, InvoicePayment, pa.id).is_voided is True
    ret = reread_row(db, PurchaseOrderReturn, r.id)
    assert ret.status == "voided"
    assert ret.paid is False


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_34__so_credit_note_void_cancels_pending_return(db, M, w1, a1, u1, u2):
    """AIM-VD-34 — voiding an SO return's credit note also voids its pending return (status voided, paid False).
    Rules: void_invoice R3c [BUG-2788]; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, invoice_amount=Decimal("1000.00"),
               paid_amount=Decimal("1000.00"), payment_status="paid")
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="pending", paid=True)
    pa = mk_pay(db, cn, Decimal("1000.00"), created_by=u1.id)
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    c = reread_inv(db, cn.id)
    assert c.invoice_status == "voided"
    assert c.paid_amount == Decimal("0.00")
    assert reread_row(db, InvoicePayment, pa.id).is_voided is True
    ret = reread_row(db, SalesOrderReturn, r.id)
    assert ret.status == "voided"
    assert ret.paid is False


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_35__po_completed_return_refuses_void(db, M, w1, a1, u1, u2):
    """AIM-VD-35 — a completed PO return refuses its credit note's void with RETTXT; nothing written.
    Rules: void_invoice R3c [BUG-2788]; Errors row 5; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, invoice_amount=Decimal("1000.00"),
               paid_amount=Decimal("1000.00"), payment_status="paid")
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="completed", paid=True)
    pa = mk_pay(db, cn, Decimal("1000.00"), created_by=u1.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert exc.value.status_code == 400
    assert exc.value.detail == RETTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    c = reread_inv(db, cn.id)
    assert c.invoice_status == "confirmed"
    assert c.paid_amount == Decimal("1000.00")
    assert c.void_note is None
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    ret = reread_row(db, PurchaseOrderReturn, r.id)
    assert ret.status == "completed"
    assert ret.paid is True
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_36__so_completed_return_refuses_void(db, M, w1, a1, u1, u2):
    """AIM-VD-36 — a completed SO return refuses its credit note's void with RETTXT; nothing written.
    Rules: void_invoice R3c [BUG-2788]; Errors row 5; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, invoice_amount=Decimal("1000.00"),
               paid_amount=Decimal("1000.00"), payment_status="paid")
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="completed", paid=True)
    pa = mk_pay(db, cn, Decimal("1000.00"), created_by=u1.id)
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert exc.value.status_code == 400
    assert exc.value.detail == RETTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    p = reread_row(db, InvoicePayment, pa.id)
    assert p.is_voided is False
    assert p.voided_at is None
    ret = reread_row(db, SalesOrderReturn, r.id)
    assert ret.status == "completed"
    assert ret.paid is True
    assert_no_events(db, cn.id)


def test_vd_37__po_voided_return_lets_void_through(db, M, w1, a1, u1, u2):
    """AIM-VD-37 — an already voided PO return lets the credit note's void go ahead; the return is unchanged.
    Rules: void_invoice R3c; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1)
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="voided", paid=False)
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert reread_inv(db, cn.id).invoice_status == "voided"
    ret = reread_row(db, PurchaseOrderReturn, r.id)
    assert ret.status == "voided"
    assert ret.paid is False
    assert_events(db, cn.id, [
        ("voided", "Invoice voided", u2.id,
         {"prior_status": "confirmed", "payments_voided": 0, "void_note": "Wrong qty"}),
    ])


def test_vd_38__so_voided_return_lets_void_through(db, M, w1, a1, u1, u2):
    """AIM-VD-38 — an already voided SO return lets the credit note's void go ahead; the return is unchanged.
    Rules: void_invoice R3c; F6."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="voided", paid=False)
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert reread_inv(db, cn.id).invoice_status == "voided"
    ret = reread_row(db, SalesOrderReturn, r.id)
    assert ret.status == "voided"
    assert ret.paid is False


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_39__completed_return_wins_over_completed_order(db, M, w1, a1, u1, u2):
    """AIM-VD-39 — a credit note that is also a completed SO's invoice, with a completed return, gets RETTXT, not LOCK.
    Rules: void_invoice R3a, R3b, R3c (check order) [BUG-2788]; Errors row 5."""
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="completed")
    s1.invoice_id = cn.id
    db.flush()
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert exc.value.status_code == 400
    assert exc.value.detail == RETTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_row(db, SalesOrderReturn, r.id).status == "completed"
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_40__completed_return_on_completed_po(db, M, w1, a1, u1, u2):
    """AIM-VD-40 — a completed PO return on a completed PO refuses the credit note's void with RETTXT.
    Rules: void_invoice R3b, R3c [BUG-2788]; Errors row 5."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Complete", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1)
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="completed")
    before = snap_inv(db, cn.id)
    before_oi = snap_inv(db, oi.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert exc.value.status_code == 400
    assert exc.value.detail == RETTXT
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_row(db, PurchaseOrderReturn, r.id).status == "completed"
    assert snap_inv(db, oi.id) == before_oi
    assert_no_events(db, cn.id)


def test_vd_41__already_voided_checked_before_return(db, M, w1, a1, u1, u2):
    """AIM-VD-41 — a voided credit note with a completed return gets "already voided", not RETTXT.
    Rules: void_invoice R2, R3c (check order); Errors row 2."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1, invoice_status="voided", void_note="Old reason")
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="completed")
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "Again")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invoice is already voided"
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_inv(db, cn.id).void_note == "Old reason"
    assert reread_row(db, PurchaseOrderReturn, r.id).status == "completed"
    assert_no_events(db, cn.id)


def test_vd_42__draft_checked_before_return(db, M, w1, a1, u1, u2):
    """AIM-VD-42 — a draft credit note with a completed return gets the R3 draft text, not RETTXT.
    Rules: void_invoice R3, R3c (check order); Errors row 3."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1, invoice_status="draft")
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="completed")
    before = snap_inv(db, cn.id)
    with pytest.raises(HTTPException) as exc:
        M.void_invoice(db, cn.id, w1.id, u2.id, "x")
    assert exc.value.status_code == 400
    assert exc.value.detail == "Draft invoices cannot be voided — delete them instead"
    assert_session_clean(db)
    assert snap_inv(db, cn.id) == before
    assert reread_row(db, SalesOrderReturn, r.id).status == "completed"
    assert_no_events(db, cn.id)


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_43__pending_return_on_credit_note_of_completed_order(db, M, w1, a1, u1, u2):
    """AIM-VD-43 — a credit note that is also a completed SO's invoice, with a pending return: void goes ahead, return voided.
    Rules: void_invoice R3a, R3b, R3c [BUG-2788]."""
    s1 = mk_so(db, w1, "SO-1", u1.id, order_completed=True)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    r = mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="pending", paid=False)
    s1.invoice_id = cn.id
    db.flush()
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert reread_inv(db, cn.id).invoice_status == "voided"
    assert reread_row(db, SalesOrderReturn, r.id).status == "voided"


def test_vd_44__returns_of_w0_and_w2_ignored(db, M, w0, w1, w2, a1, u1, u2):
    """AIM-VD-44 — a completed POR of W0 and a pending SOR of W2 pointing at the invoice are ignored.
    Rules: void_invoice R3c; F6."""
    assert w0.id < w1.id < w2.id
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("0.00"))
    r0 = mk_por(db, w0, u1.id, invoice_id=c.id, status="completed")
    rx = mk_sor(db, w2, u1.id, invoice_id=c.id, status="pending")
    result = vdcall(db, M, c, u2, "Damaged")
    assert result.id == c.id
    assert reread_inv(db, c.id).invoice_status == "voided"
    assert reread_row(db, PurchaseOrderReturn, r0.id).status == "completed"
    assert reread_row(db, SalesOrderReturn, rx.id).status == "pending"


def test_vd_45__returns_of_w2_and_w0_ignored(db, M, w0, w1, w2, a1, u1, u2):
    """AIM-VD-45 — a pending POR of W2 and a completed SOR of W0 pointing at the invoice are ignored.
    Rules: void_invoice R3c; F6."""
    assert w0.id < w1.id < w2.id
    c = mk_ci(db, w1, a1, u1.id, paid_amount=Decimal("0.00"))
    rx = mk_por(db, w2, u1.id, invoice_id=c.id, status="pending")
    r0 = mk_sor(db, w0, u1.id, invoice_id=c.id, status="completed")
    result = vdcall(db, M, c, u2, "Damaged")
    assert result.id == c.id
    assert reread_inv(db, c.id).invoice_status == "voided"
    assert reread_row(db, PurchaseOrderReturn, rx.id).status == "pending"
    assert reread_row(db, SalesOrderReturn, r0.id).status == "completed"


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_46__locks_purchase_return(db, M, engine, w1, a1, u1, u2):
    """AIM-VD-46 — voiding a PO return's credit note locks the return row FOR UPDATE.
    Rules: void_invoice R3c [BUG-2788, HR-10]."""
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1)
    mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="pending")
    with SQLCapture(engine) as cap:
        result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert cap.locks_table("purchase_order_returns")


@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_47__locks_sales_return(db, M, engine, w1, a1, u1, u2):
    """AIM-VD-47 — voiding an SO return's credit note locks the return row FOR UPDATE.
    Rules: void_invoice R3c [BUG-2788, HR-10]."""
    oi = mk_oi(db, w1, a1, u1.id)
    s1 = mk_so(db, w1, "SO-1", u1.id, invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "sales_order", s1)
    mk_sor(db, w1, u1.id, order=s1, invoice_id=cn.id, status="pending")
    with SQLCapture(engine) as cap:
        result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert cap.locks_table("sales_order_returns")


# --- Revision 10: verify finding 16 — R3c finds the return within the workspace only ---

@pytest.mark.xfail(strict=True, reason=X2788)
def test_vd_48__only_own_workspace_return_voided(db, M, w0, w1, w2, a1, u1, u2):
    """AIM-VD-48 — foreign return rows on the credit note (completed POR of W0, pending POR of W2) neither refuse
    the void nor change; only the W1 return is voided.
    Rules: void_invoice R3c [BUG-2788]; F6."""
    assert w0.id < w1.id < w2.id
    oi = mk_oi(db, w1, a1, u1.id)
    p1 = mk_po(db, w1, "PO-1", u1.id, stage="Draft", invoice_id=oi.id)
    cn = mk_cn(db, w1, a1, u1.id, "purchase_order", p1)
    # Given order (rev 11): R0, then R, then RY; mk_por flushes after each row.
    r0 = mk_por(db, w0, u1.id, invoice_id=cn.id, status="completed")
    r = mk_por(db, w1, u1.id, order=p1, invoice_id=cn.id, status="pending", paid=False)
    ry = mk_por(db, w2, u1.id, invoice_id=cn.id, status="pending")
    assert r0.id < r.id < ry.id  # precondition: first match without a workspace filter is R0
    result = M.void_invoice(db, cn.id, w1.id, u2.id, "Wrong qty")
    assert result.id == cn.id
    assert reread_inv(db, cn.id).invoice_status == "voided"
    assert reread_row(db, PurchaseOrderReturn, r0.id).status == "completed"
    ret_y = reread_row(db, PurchaseOrderReturn, ry.id)
    assert ret_y.status == "pending"
    assert ret_y.paid is False
    ret = reread_row(db, PurchaseOrderReturn, r.id)
    assert ret.status == "voided"
    assert ret.paid is False


# =========================================================================== #
# AccountInvoiceManager.set_receiving_started
# =========================================================================== #

def rscall(db, M, inv_row, performed_by, reason=""):
    return M.set_receiving_started(db, inv_row.id, inv_row.workspace_id, performed_by, reason)


def test_rs_01__sets_flag_and_logs_reason(db, M, ci, u2):
    """AIM-RS-01 — setting the flag logs the given reason as the event description.
    Rules: set_receiving_started R3, R4."""
    result = rscall(db, M, ci, u2.id, "PO-1001 received")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).receiving_started is True
    assert_events(db, ci.id, [
        ("receiving_started_set", "PO-1001 received", u2.id, None),
    ])


def test_rs_02__defaults_blank_reason_and_performer(db, M, ci):
    """AIM-RS-02 — a blank reason falls back to the default description; performed_by may be None.
    Rules: set_receiving_started R3, R4."""
    result = rscall(db, M, ci, None, "")
    assert result.id == ci.id
    r = reread_inv(db, ci.id)
    assert r.receiving_started is True
    assert r.updated_by is None
    assert_events(db, ci.id, [
        ("receiving_started_set", "Receiving started on linked order", None, None),
    ])


def test_rs_03__works_on_draft(db, M, di, u2):
    """AIM-RS-03 — the flag can be set on a draft; status is untouched.
    Rules: set_receiving_started R3."""
    result = rscall(db, M, di, u2.id, "r")
    assert result.id == di.id
    r = reread_inv(db, di.id)
    assert r.receiving_started is True
    assert r.invoice_status == "draft"
    assert len(events_of(db, di.id)) == 1


def test_rs_04__works_on_voided(db, M, vi, u2):
    """AIM-RS-04 — the flag can be set on a voided invoice; status is untouched.
    Rules: set_receiving_started R3."""
    result = rscall(db, M, vi, u2.id, "r")
    assert result.id == vi.id
    r = reread_inv(db, vi.id)
    assert r.receiving_started is True
    assert r.invoice_status == "voided"
    assert len(events_of(db, vi.id)) == 1


def test_rs_05__already_set_is_noop(db, M, w1, a1, u1, u2):
    """AIM-RS-05 — if the flag is already set, the call is a no-op with no event.
    Rules: set_receiving_started R2."""
    c = mk_ci(db, w1, a1, u1.id, receiving_started=True)
    result = rscall(db, M, c, u2.id, "again")
    assert result.id == c.id
    r = reread_inv(db, c.id)
    assert r.receiving_started is True
    assert r.updated_by is None
    assert_no_events(db, c.id)


def test_rs_06__missing_id_returns_none(db, M, w1):
    """AIM-RS-06 — an unknown id returns None without raising or logging.
    Rules: set_receiving_started R1."""
    result = M.set_receiving_started(db, NOID, w1.id, 1, "r")
    assert result is None
    assert count_events(db, w1.id) == 0


def test_rs_07__other_workspace_returns_none(db, M, w1, w2, ax, u3, u2):
    """AIM-RS-07 — another workspace's invoice is treated as not found.
    Rules: set_receiving_started R1."""
    x = mk_ci(db, w2, ax, u3.id)
    result = M.set_receiving_started(db, x.id, w1.id, u2.id, "r")
    assert result is None
    assert reread_inv(db, x.id).receiving_started is False
    assert_no_events(db, x.id)


@pytest.mark.xfail(strict=True, reason="BUG-633: set_receiving_started does not stamp updated_by")
def test_rs_08__stamps_updated_by(db, M, ci, u2):
    """AIM-RS-08 — setting the flag should stamp updated_by; today it does not.
    Rules: set_receiving_started R3 [BUG-633]."""
    result = rscall(db, M, ci, u2.id, "r")
    assert result.id == ci.id
    assert reread_inv(db, ci.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason="BUG-621: set_receiving_started reads the invoice without FOR UPDATE")
def test_rs_09__locks_invoice(db, M, engine, ci, u2):
    """AIM-RS-09 — the invoice row should be locked FOR UPDATE; today it is not.
    Rules: set_receiving_started R1 [BUG-621]."""
    with SQLCapture(engine) as cap:
        result = rscall(db, M, ci, u2.id, "r")
    assert result.id == ci.id
    assert cap.locks_invoice()
    assert reread_inv(db, ci.id).receiving_started is True


# =========================================================================== #
# AccountInvoiceManager.sync_items_from_list
# =========================================================================== #

def synccall(db, M, inv_row, items, user_id):
    # Cases file: "Call: sync_items_from_list(session, inv, items, user_id) (never is_manual)" —
    # the default is_manual=False is production-live (every real caller relies on it), so it must
    # actually be exercised rather than always passed explicitly (verify.md finding 1).
    return M.sync_items_from_list(db, inv_row, items, user_id)


# Payload shorthand "D(desc, q, p, s, **extra)"
def D(desc, q, p, s, **extra):
    return {
        "description": desc, "quantity": Decimal(q), "unit_price": Decimal(p),
        "line_subtotal": Decimal(s), **extra,
    }


def test_sy_01__replaces_items_recalculates_and_logs(db, M, w1, w2, u2, di):
    """AIM-SY-01 — syncing a draft replaces its items, recalculates the amount, and logs items_synced.
    Rules: sync_items_from_list R2, R3, R5, R6, R7."""
    mk_item(db, di, Decimal("10.00"))
    mk_item(db, di, Decimal("20.00"), line_number=2)
    mk_item(db, di, Decimal("5.00"), workspace_id=w2.id, line_number=3)
    items = [
        D("Steel rod", "2", "50.00", "100.00", unit="pcs", line_number=1),
        D("Bolt", "10", "2.50", "25.00", unit="box", line_number=2),
    ]
    result = synccall(db, M, di, items, u2.id)
    assert result is None
    rows = items_of(db, di.id)
    assert [r.description for r in rows] == ["Steel rod", "Bolt"]
    for r in rows:
        assert r.workspace_id == w1.id
        assert r.invoice_id == di.id
        assert r.created_by == u2.id
        assert r.last_synced_at == NOW
    r = reread_inv(db, di.id)
    assert r.invoice_amount == Decimal("125.00")
    assert r.payment_status == "unpaid"
    assert r.last_synced_at == NOW
    assert r.invoice_status == "draft"
    evs = events_of(db, di.id)
    assert len(evs) == 1
    e = evs[0]
    assert e.event_type == "items_synced"
    assert e.description == "Items synced from order (2 lines)"
    assert e.performed_by == u2.id
    assert e.metadata_json["item_count"] == 2
    m0, m1 = e.metadata_json["items"]
    assert m0 == {
        "description": "Steel rod", "quantity": "2", "unit_price": "50.00",
        "line_subtotal": "100.00", "unit": "pcs",
    }
    assert m1 == {
        "description": "Bolt", "quantity": "10", "unit_price": "2.50",
        "line_subtotal": "25.00", "unit": "box",
    }
    assert set(m0.keys()) == {"description", "quantity", "unit_price", "line_subtotal", "unit"}


def test_sy_02__per_item_workspace_and_created_by_defaults(db, M, w1, w2, u1, u2, di):
    """AIM-SY-02 — workspace_id/created_by default from the invoice/user only when the dict lacks them.
    Rules: sync_items_from_list R3."""
    items = [
        D("A", "1", "10.00", "10.00", created_by=u1.id),
        D("B", "1", "7.00", "7.00", workspace_id=w2.id),
    ]
    result = synccall(db, M, di, items, u2.id)
    assert result is None
    rows = items_of(db, di.id)
    a_row = next(r for r in rows if r.description == "A")
    b_row = next(r for r in rows if r.description == "B")
    assert a_row.created_by == u1.id
    assert a_row.workspace_id == w1.id
    assert b_row.workspace_id == w2.id
    assert b_row.created_by == u2.id
    assert reread_inv(db, di.id).invoice_amount == Decimal("10.00")


def test_sy_03__caller_dict_mutated_in_place(db, M, w1, di, u2):
    """AIM-SY-03 — the caller's own dict is filled in with the defaults the sync applied.
    Rules: sync_items_from_list R3."""
    d = D("A", "1", "10.00", "10.00")
    result = synccall(db, M, di, [d], u2.id)
    assert result is None
    assert d["workspace_id"] == w1.id
    assert d["invoice_id"] == di.id
    assert d["created_by"] == u2.id
    assert d["last_synced_at"] == NOW


def test_sy_04__last_synced_at_always_overwritten(db, M, di, u2):
    """AIM-SY-04 — a caller-supplied last_synced_at is overwritten with the current time.
    Rules: sync_items_from_list R3."""
    items = [D("A", "1", "10.00", "10.00", last_synced_at=V0)]
    result = synccall(db, M, di, items, u2.id)
    assert result is None
    assert items_of(db, di.id)[0].last_synced_at == NOW


def test_sy_05__empty_list_zeroes_amount_and_logs_zero_lines(db, M, di, u2):
    """AIM-SY-05 — an empty list clears all items and zeroes the amount.
    Rules: sync_items_from_list R4, R5, R6."""
    mk_item(db, di, Decimal("10.00"))
    mk_item(db, di, Decimal("20.00"), line_number=2)
    result = synccall(db, M, di, [], u2.id)
    assert result is None
    assert items_of(db, di.id) == []
    r = reread_inv(db, di.id)
    assert r.invoice_amount == Decimal("0.00")
    assert r.payment_status == "paid"
    assert r.last_synced_at == NOW
    assert_events(db, di.id, [
        ("items_synced", "Items synced from order (0 lines)", u2.id, {"item_count": 0, "items": []}),
    ])


def test_sy_06__confirmed_invoice_is_noop(db, M, w1, a1, u1, u2):
    """AIM-SY-06 — a confirmed invoice is left untouched; the call is a no-op.
    Rules: sync_items_from_list R1."""
    c = mk_ci(db, w1, a1, u1.id, invoice_amount=Decimal("400.00"))
    k = mk_item(db, c, Decimal("400.00"))
    items = [D("New", "1", "5.00", "5.00")]
    before = snap_inv(db, c.id)
    result = synccall(db, M, c, items, u2.id)
    assert result is None
    assert snap_inv(db, c.id) == before
    assert ids_list(items_of(db, c.id)) == [k.id]
    r = reread_inv(db, c.id)
    assert r.invoice_amount == Decimal("400.00")
    assert r.last_synced_at is None
    assert_no_events(db, c.id)


def test_sy_07__voided_invoice_is_noop(db, M, vi, u2):
    """AIM-SY-07 — a voided invoice is left untouched; the call is a no-op.
    Rules: sync_items_from_list R1."""
    k = mk_item(db, vi, Decimal("400.00"))
    items = [D("New", "1", "5.00", "5.00")]
    before = snap_inv(db, vi.id)
    result = synccall(db, M, vi, items, u2.id)
    assert result is None
    assert snap_inv(db, vi.id) == before
    assert ids_list(items_of(db, vi.id)) == [k.id]
    assert reread_inv(db, vi.id).invoice_amount == Decimal("1000.00")
    assert_no_events(db, vi.id)


def test_sy_08__description_fallback_and_missing_unit_is_none(db, M, di, u2):
    """AIM-SY-08 — an empty description falls back to 'Line <n>' and a missing unit stays None.
    Rules: sync_items_from_list R7."""
    items = [
        D("", "1", "1.00", "1.00", line_number=5),
        D("", "1", "2.00", "2.00"),
    ]
    result = synccall(db, M, di, items, u2.id)
    assert result is None
    e = events_of(db, di.id)[0]
    m0, m1 = e.metadata_json["items"]
    assert m0["description"] == "Line 5"
    assert m1["description"] == "Line 2"
    rows = items_of(db, di.id)
    assert all(r.unit is None for r in rows)


def test_sy_09__none_user_id_propagates_to_item_and_event(db, M, di):
    """AIM-SY-09 — a None user_id is stored as created_by and as the event's performer.
    Rules: sync_items_from_list R6."""
    items = [D("A", "1", "10.00", "10.00")]
    result = synccall(db, M, di, items, None)
    assert result is None
    assert items_of(db, di.id)[0].created_by is None
    e = events_of(db, di.id)[0]
    assert e.performed_by is None
    assert e.description == "Items synced from order (1 lines)"


def test_sy_10__missing_required_column_raises_and_rolls_back(db, M, di, u2):
    """AIM-SY-10 — a dict missing a NOT NULL column fails at flush; the savepoint rollback restores the old items.
    Rules: sync_items_from_list R7a; Errors (missing column)."""
    k = mk_item(db, di, Decimal("10.00"))
    items = [{"description": "A", "quantity": Decimal("1"), "unit_price": Decimal("10.00")}]
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            synccall(db, M, di, items, u2.id)
    assert ids_list(items_of(db, di.id)) == [k.id]
    assert reread_inv(db, di.id).invoice_amount == Decimal("1000.00")
    assert_no_events(db, di.id)


def test_sy_11__none_value_for_required_column_raises_and_rolls_back(db, M, di, u2):
    """AIM-SY-11 — None in a NOT NULL column fails at flush the same way as a missing one.
    Rules: sync_items_from_list R7a; Errors (None column)."""
    k = mk_item(db, di, Decimal("10.00"))
    items = [D("A", "1", "10.00", "10.00")]
    items[0]["quantity"] = None
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            synccall(db, M, di, items, u2.id)
    assert ids_list(items_of(db, di.id)) == [k.id]
    assert reread_inv(db, di.id).invoice_amount == Decimal("1000.00")
    assert_no_events(db, di.id)


# =========================================================================== #
# AccountInvoiceManager.get_events
# =========================================================================== #

def test_ev_01__returns_dicts_newest_first_with_performer_name(db, M, w1, u1, di):
    """AIM-EV-01 — events come back as dicts, newest created_at first, with the performer's name joined in.
    Rules: get_events R2."""
    e1 = mk_evt(db, di, datetime(2026, 9, 1, 10, 0, 0), performed_by=u1.id)
    e2 = mk_evt(db, di, datetime(2026, 9, 2, 10, 0, 0))
    e3 = mk_evt(db, di, datetime(2026, 9, 3, 10, 0, 0), performed_by=u1.id)
    result = M.get_events(db, di.id, w1.id)
    assert [d["id"] for d in result] == [e3.id, e2.id, e1.id]
    for d in result:
        assert set(d.keys()) == {
            "id", "workspace_id", "invoice_id", "event_type", "description",
            "metadata_json", "performed_by", "performed_by_name", "created_at",
        }
    d1 = next(d for d in result if d["id"] == e1.id)
    assert d1["performed_by"] == u1.id
    assert d1["performed_by_name"] == "Rahim Uddin"
    assert d1["workspace_id"] == w1.id
    assert d1["invoice_id"] == di.id
    assert d1["event_type"] == "note"
    assert d1["description"] == "n"
    assert d1["metadata_json"] is None
    assert d1["created_at"] == datetime(2026, 9, 1, 10, 0, 0)
    d2 = next(d for d in result if d["id"] == e2.id)
    assert d2["performed_by"] is None
    assert d2["performed_by_name"] is None


def test_ev_02__isolated_by_invoice_and_workspace(db, M, w1, w2, a1, u1, di):
    """AIM-EV-02 — only this invoice's events, in this workspace, are returned.
    Rules: get_events R2."""
    e1 = mk_evt(db, di, datetime(2026, 9, 1, 10, 0, 0))
    j = mk_di(db, w1, a1, u1.id)
    mk_evt(db, j, datetime(2026, 9, 2, 10, 0, 0))
    mk_evt(db, di, datetime(2026, 9, 3, 10, 0, 0), workspace_id=w2.id)
    result = M.get_events(db, di.id, w1.id)
    assert [d["id"] for d in result] == [e1.id]


def test_ev_03__missing_id_404(db, M, w1):
    """AIM-EV-03 — an unknown invoice id raises 404.
    Rules: get_events R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.get_events(db, NOID, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_ev_04__other_workspace_404(db, M, w1, w2, ax, u3):
    """AIM-EV-04 — another workspace's invoice 404s.
    Rules: get_events R1."""
    x = mk_di(db, w2, ax, u3.id)
    mk_evt(db, x, datetime(2026, 9, 1, 10, 0, 0))
    with pytest.raises(HTTPException) as exc:
        M.get_events(db, x.id, w1.id)
    assert exc.value.status_code == 404


@pytest.mark.xfail(strict=True, reason="BUG-638: get_events has no id tie-breaker for equal timestamps")
def test_ev_05__tie_order_id_descending(db, M, w1, di):
    """AIM-EV-05 — equal timestamps should break ties by id descending; today they follow undefined physical order.
    Rules: get_events R2 [BUG-638].

    Setup per spec Notes G10: reserve three ids N1 < N2 < N3 from the table's
    own id sequence, then insert the tied rows with explicit ids in the order
    N2, N1, N3, each flushed separately. Physical order is then N2, N1, N3 and
    its reverse is N3, N1, N2 — neither matches the intended id-descending
    order [N3, N2, N1], so this xfail fails today regardless of scan direction.
    """
    t = datetime(2026, 9, 1, 10, 0, 0)
    seq = text("SELECT nextval(pg_get_serial_sequence('invoice_events', 'id'))")
    n1 = db.execute(seq).scalar()
    n2 = db.execute(seq).scalar()
    n3 = db.execute(seq).scalar()
    mk_evt(db, di, t, id=n2)
    mk_evt(db, di, t, id=n1)
    mk_evt(db, di, t, id=n3)
    result = M.get_events(db, di.id, w1.id)
    assert [d["id"] for d in result] == [n3, n2, n1]


def test_ev_06__no_paging_returns_all_newest_first(db, M, w1, di):
    """AIM-EV-06 — get_events has no paging; all rows come back, latest first.
    Rules: get_events R2."""
    base = datetime(2026, 9, 1, 0, 0, 0)
    evts = [mk_evt(db, di, base + timedelta(minutes=n)) for n in range(101)]
    result = M.get_events(db, di.id, w1.id)
    assert len(result) == 101
    assert result[0]["id"] == evts[-1].id


# =========================================================================== #
# AccountInvoiceManager.get_items
# =========================================================================== #

def test_it_01__ordered_by_line_number_isolated(db, M, w1, w2, a1, u1, di):
    """AIM-IT-01 — items come back ordered by line_number, isolated by invoice and workspace.
    Rules: get_items R2."""
    x3 = mk_item(db, di, Decimal("3.00"), line_number=3)
    x1 = mk_item(db, di, Decimal("1.00"), line_number=1)
    x2 = mk_item(db, di, Decimal("2.00"), line_number=2)
    mk_item(db, di, Decimal("0.00"), line_number=0, workspace_id=w2.id)
    j = mk_di(db, w1, a1, u1.id)
    mk_item(db, j, Decimal("9.00"), line_number=1)
    result = M.get_items(db, di.id, w1.id)
    assert ids_list(result) == [x1.id, x2.id, x3.id]


def test_it_02__missing_id_404(db, M, w1):
    """AIM-IT-02 — an unknown invoice id raises 404.
    Rules: get_items R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, NOID, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Invoice with ID 999999 not found"


def test_it_03__other_workspace_404(db, M, w1, w2, ax, u3):
    """AIM-IT-03 — another workspace's invoice 404s.
    Rules: get_items R1."""
    x = mk_di(db, w2, ax, u3.id)
    mk_item(db, x, Decimal("1.00"))
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, x.id, w1.id)
    assert exc.value.status_code == 404


@pytest.mark.xfail(strict=True, reason="BUG-638: get_items has no id tie-breaker for equal line_numbers")
def test_it_04__tie_order_id_ascending(db, M, w1, di):
    """AIM-IT-04 — equal line numbers should break ties by id ascending; today they follow undefined physical order.
    Rules: get_items R2 [BUG-638].

    Setup per spec Notes G10: reserve three ids N1 < N2 < N3 from the table's
    own id sequence, then insert the tied rows with explicit ids in the order
    N2, N1, N3, each flushed separately. Physical order is then N2, N1, N3 and
    its reverse is N3, N1, N2 — neither matches the intended id-ascending
    order [N1, N2, N3], so this xfail fails today regardless of scan direction.
    """
    seq = text("SELECT nextval(pg_get_serial_sequence('invoice_items', 'id'))")
    n1 = db.execute(seq).scalar()
    n2 = db.execute(seq).scalar()
    n3 = db.execute(seq).scalar()
    mk_item(db, di, Decimal("1.00"), line_number=1, id=n2)
    mk_item(db, di, Decimal("1.00"), line_number=1, id=n1)
    mk_item(db, di, Decimal("1.00"), line_number=1, id=n3)
    result = M.get_items(db, di.id, w1.id)
    assert ids_list(result) == [n1, n2, n3]


def test_it_05__no_paging_returns_all_ascending(db, M, w1, di):
    """AIM-IT-05 — get_items has no paging; all rows come back, line_number ascending.
    Rules: get_items R2."""
    for n in range(1, 102):
        mk_item(db, di, Decimal("1.00"), line_number=n)
    result = M.get_items(db, di.id, w1.id)
    assert len(result) == 101
    assert [r.line_number for r in result] == list(range(1, 102))
