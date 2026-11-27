# ruff: noqa: SIM117, DTZ001, B017, FURB157
# (nested `with` blocks, naive datetimes, `pytest.raises(Exception)` and
# `Decimal("1")`-style literals are prescribed by the cards' Conventions.)
"""Unit tests for app/services/account_invoice_service.py.

Implements tests/unit/services/account_invoice_service.cases.md (revision 2,
2026-11-21), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: the commit / rollback / refresh spies and
failing variants (`patch.object(db, ...)`), and in the one `Author: claude`
card (AIS-K-13) `app.services.account_invoice_service.notify_invoice_action`
("failing notify"). Nothing else is mocked; the lock cards record the SQL sent
with an `after_cursor_execute` listener.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.SR1`,
`s.A9`); a workspace key "0" / "1" / "9" selects W0 / W1 / W2 and that
workspace's A, F, WT, SD, WF. `# Then N` marks the checks of the card's Then
line N.
"""

import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

import app.services.account_invoice_service as ais_mod
from app.managers.account_invoice_manager import account_invoice_manager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.factory import Factory
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.item import Item
from app.models.notification import Notification
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import PurchaseOrderReturn
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from app.models.work_order import WorkOrder
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_type import WorkOrderType
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.account_invoice import (
    AccountInvoiceCreate,
    AccountInvoiceUpdate,
    VoidInvoiceRequest,
)
from app.services.account_invoice_service import account_invoice_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = account_invoice_service
mgr = account_invoice_manager

MISSING = 999999999
T0 = datetime(2026, 3, 1, 8, 0)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)


def LOCK(kind):
    return (
        "Invoice is locked — the linked "
        + kind
        + " is completed. Correct it with a credit note or return."
    )


RCVTXT = (
    "Cannot revert to draft — goods have been received on the linked order."
    " Record a return instead."
)
CNTXT = "Return credit notes cannot be reverted to draft. Void it and create a new return instead."
RECVD = "Cannot void invoice after receiving has been recorded on the linked order"
DELIVERED = "Cannot void invoice after delivery has been recorded on the linked order"
NOT_LINKED = "This invoice is not linked to an order — resync is not applicable."
DRAFT_ONLY = "Can only resync items on draft invoices."
SECTIONS = "Confirm supplier, order details, and items before finalizing"

_BUGS = {
    626: "Whitespace-only void reason accepted",
    639: "A draft that once had (voided) payments cannot be deleted",
    1202: "Purchase order with no approvers counts as fully approved",
    1205: "Sales order approvers are never notified",
    2730: "A completed sales / expense / work order's confirmed invoice can be reverted to draft",
    2731: "/void on a completed sales / expense / work order's invoice is allowed",
    2732: "Deleting a (reverted) invoice unlinks only purchase orders",
    2733: "Return credit notes are confirmed at creation but can be reverted to draft",
    2736: "The revert error advises zeroing received quantities, which can never work",
    2788: "Voiding a return credit note leaves its return untouched",
    2962: "Invoice-page finalize, void and resync check state without a row lock",
    2963: "Resync items on a sales order's invoice always fails with 500",
    2964: "Resync items on a work order's invoice deletes its only line",
    2965: "Finalizing a sales order's invoice from the invoice page skips the order's checks",
    2966: "Voiding a sales, expense or work order's invoice leaves the order tied to it",
    2967: "A sales order's invoice can be voided after goods were delivered",
    2968: "The PO's draft invoice deleted log entry records no invoice id",
    2969: "An expense or work order's invoice can be finalized on the invoice page early",
}


def xfail(*ns):
    """Expect `xfail BUG-n[, BUG-m]` -> strict xfail naming every bug."""
    return pytest.mark.xfail(
        strict=True, reason="; ".join(f"BUG-{n}: {_BUGS[n]}" for n in ns)
    )


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.TAG = uuid.uuid4().hex[:8]
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    for i, name in enumerate(
        ["Rahim Uddin", "Bob Karim", "Chitra Das", "Dev Paul", "Esha Roy"], 1
    ):
        setattr(n, f"U{i}", make_profile(db, name=name))
    for ws, user, st in (
        (n.W1, n.U1, "active"),
        (n.W1, n.U2, "active"),
        (n.W1, n.U4, "active"),
        (n.W1, n.U5, "inactive"),
        (n.W2, n.U3, "active"),
    ):
        _add(
            db,
            WorkspaceMember(
                workspace_id=ws.id, user_id=user.id, role="member", status=st
            ),
        )
    for k, ws, acct in (
        ("0", n.W0, "Zeta West"),
        ("1", n.W1, "Acme Traders"),
        ("9", n.W2, "Xeno Foreign"),
    ):
        for key, name in (
            ("SD", "Draft"),
            ("SP", "Planning"),
            ("SR", "Receiving"),
            ("SC", "Complete"),
        ):
            setattr(
                n,
                f"{key}{k}",
                _add(db, Status(workspace_id=ws.id, name=name, comment="po stage")),
            )
        seq = [getattr(n, f"{key}{k}").id for key in ("SD", "SP", "SR", "SC")]
        setattr(
            n,
            f"WF{k}",
            _add(
                db,
                OrderWorkflow(
                    workspace_id=ws.id,
                    name="Purchase Order",
                    type="purchase",
                    status_sequence=seq,
                ),
            ),
        )
        setattr(
            n,
            f"F{k}",
            _add(
                db,
                Factory(
                    workspace_id=ws.id,
                    name="Main Plant",
                    abbreviation=f"MP{k}",
                    is_active=True,
                    is_deleted=False,
                ),
            ),
        )
        setattr(n, f"WT{k}", _add(db, WorkOrderType(workspace_id=ws.id, name="Repair")))
        setattr(
            n,
            f"A{k}",
            _add(
                db,
                Account(
                    workspace_id=ws.id,
                    name=acct,
                    is_active=True,
                    is_deleted=False,
                    allow_invoices=True,
                ),
            ),
        )
    n.I1 = _add(
        db,
        Item(
            workspace_id=n.W1.id,
            name="Bolt",
            name_normalized="bolt",
            unit="pcs",
            is_active=True,
        ),
    )
    n.I2 = _add(
        db,
        Item(
            workspace_id=n.W1.id,
            name="Nut",
            name_normalized="nut",
            unit="box",
            is_active=True,
        ),
    )
    return n


def _ws(s, k):
    """'of W0' / 'of W9': the workspace and its A, F, WT, SD, WF (k = '0', '1', '9')."""
    w = {"0": s.W0, "1": s.W1, "9": s.W2}[k]
    return SimpleNamespace(
        W=w,
        A=getattr(s, f"A{k}"),
        F=getattr(s, f"F{k}"),
        WT=getattr(s, f"WT{k}"),
        SD=getattr(s, f"SD{k}"),
        WF=getattr(s, f"WF{k}"),
    )


# --------------------------------------------------------------------------- #
# Conventions -> Given rows ("but" = keyword overrides, applied last)
# --------------------------------------------------------------------------- #

# "confirmed"
CONFIRMED = {"invoice_status": "confirmed", "invoice_amount": Decimal("400.00")}
# PO "ready"
READY = {"supplier_confirmed": True, "details_confirmed": True, "items_confirmed": True}
# SO "so ready"
SO_READY = {"order_info_confirmed": True, "items_confirmed": True}


def _inv_obj(s, ws="1", confirmed=False, **but):
    w = _ws(s, ws)
    fields = {
        "workspace_id": w.W.id,
        "account_id": w.A.id,
        "invoice_type": "payable",
        "invoice_status": "draft",
        "payment_status": "unpaid",
        "invoice_amount": Decimal("0.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": date(2026, 9, 1),
        "allow_payments": True,
        "receiving_started": False,
        "created_by": s.U1.id,
        "order_type": None,
        "order_id": None,
        "description": None,
        "void_note": None,
        "last_synced_at": None,
    }
    if confirmed:
        fields.update(CONFIRMED)
    fields.update(but)
    return AccountInvoice(**fields)


# Convention "inv" (confirmed=True -> "confirmed"; ws="0"/"9" -> "of W0"/"of W9")
def inv(db, s, ws="1", confirmed=False, **but):
    return _add(db, _inv_obj(s, ws, confirmed, **but))


# Convention "N invoices, built with add_all and one flush"
def inv_many(db, s, prefix, count, confirmed=False):
    rows = [
        _inv_obj(s, confirmed=confirmed, description=f"{prefix}{k}")
        for k in range(1, count + 1)
    ]
    db.add_all(rows)
    db.flush()
    return rows


# Convention "invl(V, s, k)"
def invl(db, s, V, amount, k, **but):
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "line_number": k,
        "description": "Old line",
        "quantity": Decimal("1"),
        "unit_price": Decimal(amount),
        "line_subtotal": Decimal(amount),
        "created_by": s.U1.id,
    }
    fields.update(but)
    return _add(db, InvoiceItem(**fields))


# Convention "pay(V, a)" (voided=True -> "voided pay")
def pay(db, s, V, amount, voided=False, **but):
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "payment_amount": Decimal(amount),
        "payment_date": date(2026, 9, 2),
        "is_voided": False,
        "created_by": s.U1.id,
    }
    if voided:
        fields.update(
            is_voided=True, voided_at=T0, voided_by=s.U1.id, void_note="manual void"
        )
    fields.update(but)
    return _add(db, InvoicePayment(**fields))


# Convention "po 'n'" (ready / of V / locked by V)
def po(db, s, num, ws="1", ready=False, of=None, locked_by=None, **but):
    w = _ws(s, ws)
    fields = {
        "workspace_id": w.W.id,
        "po_number": f"PO-{s.TAG}-{num}",
        "account_id": w.A.id,
        "destination_type": "storage",
        "destination_id": w.F.id,
        "subtotal": Decimal("999.00"),
        "total_amount": Decimal("999.00"),
        "current_status_id": w.SD.id,
        "order_workflow_id": w.WF.id,
        "created_by": s.U1.id,
        "supplier_confirmed": False,
        "details_confirmed": False,
        "items_confirmed": False,
        "invoice_confirmed": False,
        "invoice_ever_linked": False,
        "paid": False,
        "voided": False,
    }
    if ready:
        fields.update(READY)
    if of is not None:
        fields.update(invoice_id=of.id, invoice_ever_linked=True)
    if locked_by is not None:
        fields.update(invoice_id=locked_by.id, invoice_ever_linked=True, **READY)
        fields.update(invoice_confirmed=True, current_status_id=s.SR1.id)
    fields.update(but)
    return _add(db, PurchaseOrder(**fields))


# Convention "poline(O, k)"
def poline(db, s, O, k, **but):
    fields = {
        "workspace_id": O.workspace_id,
        "purchase_order_id": O.id,
        "line_number": k,
        "item_id": s.I1.id,
        "quantity_ordered": Decimal("10.00"),
        "quantity_received": Decimal("0.00"),
        "unit_price": Decimal("2.00"),
        "line_subtotal": Decimal("20.00"),
    }
    fields.update(but)
    return _add(db, PurchaseOrderItem(**fields))


# Convention "poappr(O, U)" (approved=True -> "approved")
def poappr(db, s, O, U, approved=False, **but):
    fields = {
        "workspace_id": O.workspace_id,
        "purchase_order_id": O.id,
        "user_id": U.id,
        "assigned_by": s.U1.id,
        "approved": False,
        "approved_at": None,
        "assigned_at": T1,
    }
    if approved:
        fields.update(approved=True, approved_at=T2)
    fields.update(but)
    return _add(db, PurchaseOrderApprover(**fields))


# Convention "so 'n'" (so ready / of V / finalized by V)
def so(db, s, num, ws="1", so_ready=False, of=None, finalized_by=None, **but):
    w = _ws(s, ws)
    fields = {
        "workspace_id": w.W.id,
        "sales_order_number": f"SO-{s.TAG}-{num}",
        "account_id": w.A.id,
        "factory_id": w.F.id,
        "current_status_id": w.SD.id,
        "order_date": date(2026, 9, 1),
        "total_amount": Decimal("20000.00"),
        "created_by": s.U1.id,
        "order_info_confirmed": False,
        "items_confirmed": False,
        "invoice_confirmed": False,
        "is_invoiced": False,
        "paid": False,
        "order_completed": False,
    }
    if so_ready:
        fields.update(SO_READY)
    if of is not None:
        fields.update(invoice_id=of.id)
    if finalized_by is not None:
        fields.update(SO_READY)
        fields.update(
            invoice_id=finalized_by.id, invoice_confirmed=True, is_invoiced=True
        )
    fields.update(but)
    return _add(db, SalesOrder(**fields))


# Convention "soline(S)"
def soline(db, s, S, **but):
    fields = {
        "workspace_id": S.workspace_id,
        "sales_order_id": S.id,
        "item_id": s.I1.id,
        "description": "Chair",
        "quantity_ordered": Decimal("10.00"),
        "quantity_delivered": Decimal("0.00"),
        "unit_price": Decimal("2000.00"),
        "line_total": Decimal("20000.00"),
        "requires_delivery": True,
    }
    fields.update(but)
    return _add(db, SalesOrderItem(**fields))


# Convention "soappr(S, U)" (approved=True -> "approved")
def soappr(db, s, S, U, approved=False, **but):
    fields = {
        "workspace_id": S.workspace_id,
        "sales_order_id": S.id,
        "user_id": U.id,
        "assigned_at": T1,
    }
    if approved:
        fields.update(approved=True, approved_at=T2)
    fields.update(but)
    return _add(db, SalesOrderApprover(**fields))


# Convention "eo 'n'" (of V)
def eo(db, s, num, ws="1", of=None, **but):
    w = _ws(s, ws)
    fields = {
        "workspace_id": w.W.id,
        "expense_number": num,
        "expense_category": "other",
        "expense_date": date(2026, 9, 1),
        "subtotal": Decimal("45000.00"),
        "total_amount": Decimal("45000.00"),
        "description": "Machine repair",
        "created_by": s.U1.id,
        "voided": False,
        "completed_at": None,
    }
    if of is not None:
        fields.update(invoice_id=of.id)
    fields.update(but)
    return _add(db, ExpenseOrder(**fields))


# Convention "eoline(E, k)"
def eoline(db, s, E, k, **but):
    fields = {
        "workspace_id": E.workspace_id,
        "expense_order_id": E.id,
        "line_number": k,
        "description": "Paper",
        "quantity": Decimal("2"),
        "unit": "box",
        "unit_price": Decimal("5.00"),
        "line_subtotal": Decimal("10.00"),
    }
    fields.update(but)
    return _add(db, ExpenseOrderItem(**fields))


# Convention "eoappr(E, U)" (approved=True -> "approved")
def eoappr(db, s, E, U, approved=False, **but):
    fields = {
        "workspace_id": E.workspace_id,
        "expense_order_id": E.id,
        "user_id": U.id,
        "assigned_at": T1,
    }
    if approved:
        fields.update(approved=True, approved_at=T2)
    fields.update(but)
    return _add(db, ExpenseOrderApprover(**fields))


# Convention "wo 'n'" (of V)
def wo(db, s, num, ws="1", of=None, **but):
    w = _ws(s, ws)
    fields = {
        "workspace_id": w.W.id,
        "work_order_number": num,
        "work_order_type_id": w.WT.id,
        "factory_id": w.F.id,
        "title": "Pump repair",
        "status": "DRAFT",
        "cost": Decimal("5000.00"),
        "created_by": s.U1.id,
        "is_deleted": False,
    }
    if of is not None:
        fields.update(invoice_id=of.id)
    fields.update(but)
    return _add(db, WorkOrder(**fields))


def ievent(db, s, V, **but):
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "event_type": "note",
        "created_at": T1,
    }
    fields.update(but)
    return _add(db, InvoiceEvent(**fields))


def po_return(db, s, O, CN):
    return _add(
        db,
        PurchaseOrderReturn(
            workspace_id=s.W1.id,
            purchase_order_id=O.id,
            return_number=f"PR-{s.TAG}-1",
            return_type="refund",
            created_by=s.U1.id,
            invoice_id=CN.id,
        ),
    )


# Convention "CRT(**k)" (AccountInvoiceCreate has `invoice_amount`, so it is passed as 0.00)
def CRT(s, **k):
    fields = {
        "account_id": s.A1.id,
        "invoice_type": "payable",
        "invoice_date": date(2026, 9, 1),
    }
    if "invoice_amount" in AccountInvoiceCreate.model_fields:
        fields["invoice_amount"] = Decimal("0.00")
    fields.update(k)
    return AccountInvoiceCreate(**fields)


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

_COUNT_TABLES = (
    "account_invoices",
    "invoice_items",
    "invoice_events",
    "invoice_payments",
    "purchase_order_events",
    "purchase_order_approvers",
    "sales_order_events",
    "expense_order_events",
    "work_order_events",
    "notifications",
)
_ORDER_EVENT_TABLES = (
    "purchase_order_events",
    "sales_order_events",
    "expense_order_events",
    "work_order_events",
)


# Named check "nothing written": row counts of the listed tables (all workspaces)
def counts(db):
    return tuple(
        db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES
    )


# count of the four order-event tables (all workspaces)
def order_event_counts(db):
    return tuple(
        db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
        for t in _ORDER_EVENT_TABLES
    )


# Convention "commit point": the test commits; the "nothing written" snapshot is taken here
def commit_point(db):
    db.commit()
    return counts(db)


# Convention "X": a pending workspace, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Named check "unchanged(R)": every column of R, read straight from the database
def snap(db, R):
    table = type(R).__table__
    rid = R.id
    db.expire_all()
    row = db.execute(select(table).where(table.c.id == rid)).mappings().one_or_none()
    return None if row is None else dict(row)


# Named check "re-read R"
def reread(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


# Named check "gone(R)"
def gone(db, model, rid):
    db.expire_all()
    return db.get(model, rid) is None


# Named check "x_gone"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


# count of rows of `model` matching the filters, fresh query
def count_where(db, model, *where):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


_EV = {
    PurchaseOrder: (PurchaseOrderEvent, "purchase_order_id"),
    SalesOrder: (SalesOrderEvent, "sales_order_id"),
    ExpenseOrder: (ExpenseOrderEvent, "expense_order_id"),
    WorkOrder: (WorkOrderEvent, "work_order_id"),
}


# Named check "EV(O)": O's rows in its own events table, by id
def EV(db, model, oid):
    ev, col = _EV[model]
    db.expire_all()
    return list(db.scalars(select(ev).where(getattr(ev, col) == oid).order_by(ev.id)))


# Named check "types(O)"
def types(db, model, oid):
    return [e.event_type for e in EV(db, model, oid)]


# Named check "IEV(V)"
def IEV(db, vid):
    db.expire_all()
    return list(
        db.scalars(
            select(InvoiceEvent)
            .where(InvoiceEvent.invoice_id == vid)
            .order_by(InvoiceEvent.id)
        )
    )


# Named check "itypes(V)"
def itypes(db, vid):
    return [e.event_type for e in IEV(db, vid)]


# Named check "LINES(V)"
def LINES(db, vid):
    db.expire_all()
    return list(
        db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == vid)
            .order_by(InvoiceItem.line_number)
        )
    )


# Named check "notes()"
def notes(db):
    db.expire_all()
    return list(db.scalars(select(Notification).order_by(Notification.id)))


# Named check "recips()"
def recips(db):
    return sorted(n.recipient_user_id for n in notes(db))


# Named check "session clean"
def session_clean(db):
    return not db.new and not db.dirty and not db.deleted


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint(
        {c.key for c in inspect(AccountInvoice).column_attrs}
    )


# Named check "session: usable"
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


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "failing refresh": the rollback spy is yielded
@contextmanager
def failing_refresh(db):
    with (
        patch.object(db, "refresh", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Forced error "failing notify" (Author: claude card K-13)
@contextmanager
def failing_notify():
    with patch(
        "app.services.account_invoice_service.notify_invoice_action",
        side_effect=RuntimeError("boom"),
    ):
        yield


_FROM = re.compile(
    r"\bFROM\b(.*?)(?:\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bFOR UPDATE\b|$)",
    re.DOTALL,
)


def _from_names(sql, table):
    m = _FROM.search(sql)
    return bool(m) and re.search(rf"\b{re.escape(table)}\b", m.group(1)) is not None


# Convention "Statement recorder": every SQL statement sent during the When
class Recorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "after_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "after_cursor_execute", self._record)
        return False

    def _selects(self):
        return [
            (i, st)
            for i, st in enumerate(self.statements)
            if st.lstrip().upper().startswith("SELECT")
        ]

    def _lock_idx(self, table):
        for i, st in self._selects():
            if _from_names(st, table) and "FOR UPDATE" in st:
                return i
        return None

    def lock(self, table):
        """lock(T): the first SELECT from T containing FOR UPDATE, or None."""
        i = self._lock_idx(table)
        return None if i is None else self.statements[i]

    def row_lock(self, table):
        st = self.lock(table)
        if st is None:
            return False
        st = st.rstrip()
        ends = st.endswith(("FOR UPDATE", f"FOR UPDATE OF {table}"))
        return ends and "SKIP LOCKED" not in st and "NOWAIT" not in st

    def line_lock(self, table):
        st = self.lock(table)
        if st is None:
            return False
        st = st.rstrip()
        return (
            st.endswith(f"FOR UPDATE OF {table}")
            and "SKIP LOCKED" not in st
            and "NOWAIT" not in st
        )

    def before(self, table, other):
        """lock(table) is sent before the first SELECT whose FROM names `other`;
        fails when `other` is never read (cases rev 3)."""
        li = self._lock_idx(table)
        firsts = [i for i, st in self._selects() if _from_names(st, other)]
        return li is not None and bool(firsts) and li < firsts[0]

    def reads(self, table):
        """At least one recorded SELECT names `table` in its FROM."""
        return any(_from_names(st, table) for _, st in self._selects())

    def lock_before_lock(self, first, second):
        a, b = self._lock_idx(first), self._lock_idx(second)
        return a is not None and b is not None and a < b


# --------------------------------------------------------------------------- #
# create_invoice
# --------------------------------------------------------------------------- #


# [claude] AIS-C-01
def test_ais_c_01__new_draft_committed_and_reread(db, s):
    """AIS-C-01 — a new draft invoice is committed and returned re-read.
    Rules: create_invoice C1; TC1, TC2."""
    commit_point(db)

    result = svc.create_invoice(
        db, invoice_in=CRT(s, description="Rent"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, AccountInvoice)
    assert result.id is not None
    assert result.created_at is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, AccountInvoice, rid)
    assert row is not None
    assert row.workspace_id == s.W1.id
    assert row.account_id == s.A1.id
    assert row.invoice_status == "draft"
    assert row.description == "Rent"
    assert row.created_by == s.U2.id
    # Then 4
    assert len(IEV(db, rid)) == 1
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 1


# [claude] AIS-C-02
def test_ais_c_02__foreign_account_404(db, s):
    """AIS-C-02 — another workspace's account: the manager's 404 passes unchanged, nothing saved.
    Rules: create_invoice C2; TC3."""
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice(
            db,
            invoice_in=CRT(s, account_id=s.A9.id),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 4
    assert x not in db
    # Then 5
    assert session_clean(db)
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert usable(db)


# [claude] AIS-C-03
def test_ais_c_03__invoices_not_allowed_403(db, s):
    """AIS-C-03 — an account that does not allow invoices: the manager's 403 passes unchanged.
    Rules: create_invoice C2; TC3."""
    s.A1.allow_invoices = False
    db.flush()
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice(db, invoice_in=CRT(s), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


# [claude] AIS-C-04
def test_ais_c_04__deleted_account_400(db, s):
    """AIS-C-04 — a deleted account: the manager's 400 passes unchanged.
    Rules: create_invoice C2; TC3."""
    s.A1.is_deleted = True
    s.A1.is_active = False
    db.flush()
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice(db, invoice_in=CRT(s), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create invoice for deleted account"
    # Then 4
    assert counts(db) == before


# [claude] AIS-C-05
def test_ais_c_05__failing_commit_rolled_back(db, s):
    """AIS-C-05 — a failing commit is rolled back and re-raised; nothing saved.
    Rules: create_invoice C1; TC4."""
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    data = CRT(s)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_invoice(db, invoice_in=data, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == w1_id) == 0
    # Then 4
    assert count_where(db, InvoiceEvent, InvoiceEvent.workspace_id == w1_id) == 0


# [claude] AIS-C-06
def test_ais_c_06__failing_refresh_keeps_saved(db, s):
    """AIS-C-06 — a failing re-read after the commit leaves the invoice saved.
    Rules: create_invoice C1; TC5."""
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    data = CRT(s, description="Rent")

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_invoice(db, invoice_in=data, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == w1_id) == 1
    # Then 3
    row = db.scalars(
        select(AccountInvoice).where(AccountInvoice.workspace_id == w1_id)
    ).one()
    assert row.description == "Rent"
    assert row.invoice_status == "draft"


# --------------------------------------------------------------------------- #
# get_invoice
# --------------------------------------------------------------------------- #


# [claude] AIS-G-01
def test_ais_g_01__returns_invoice_no_commit(db, s):
    """AIS-G-01 — returns the workspace's invoice; neither commits nor rolls back.
    Rules: get_invoice G1; TC6."""
    V = inv(db, s)
    commit_point(db)
    vid, w1_id = V.id, s.W1.id
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_invoice(db, invoice_id=vid, workspace_id=w1_id)

    # Then 1
    assert isinstance(result, AccountInvoice)
    assert result.id == vid
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# [claude] AIS-G-02
def test_ais_g_02__w0_invoice_404(db, s):
    """AIS-G-02 — a W0 invoice (lower workspace id) gets the 404.
    Rules: get_invoice G1."""
    Z = inv(db, s, ws="0")
    inv(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_invoice(db, invoice_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {Z.id} not found"


# [claude] AIS-G-03
def test_ais_g_03__w2_invoice_404(db, s):
    """AIS-G-03 — a W2 invoice (higher workspace id) gets the 404.
    Rules: get_invoice G1."""
    inv(db, s)
    Z = inv(db, s, ws="9")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_invoice(db, invoice_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {Z.id} not found"


# [claude] AIS-G-04
def test_ais_g_04__404_no_rollback(db, s):
    """AIS-G-04 — a 404 neither rolls back nor drops a pending change.
    Rules: get_invoice G1; TC6."""
    inv(db, s)
    commit_point(db)
    w1_id = s.W1.id
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_invoice(db, invoice_id=MISSING, workspace_id=w1_id)

    # Then 1
    assert exc.value.detail == "Invoice with ID 999999999 not found"
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# Read pass-throughs
# --------------------------------------------------------------------------- #


# [claude] AIS-L-01
def test_ais_l_01__list_default_limit_100(db, s):
    """AIS-L-01 — list_invoices: 101 invoices, no limit given -> 100; nothing committed.
    Rules: L1, L3; TC6."""
    rows = inv_many(db, s, "I", 101)
    all_ids = {r.id for r in rows}
    commit_point(db)
    w1_id = s.W1.id
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_invoices(db, workspace_id=w1_id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len({r.id for r in result}) == 100
    assert {r.id for r in result} <= all_ids
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


# [claude] AIS-L-02
def test_ais_l_02__list_limit_1000_passed(db, s):
    """AIS-L-02 — list_invoices: limit=1000 is passed on.
    Rules: L1."""
    inv_many(db, s, "I", 101)
    commit_point(db)

    result = svc.list_invoices(db, workspace_id=s.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101


# [claude] AIS-L-03
def test_ais_l_03__list_skip_limit_isolated(db, s):
    """AIS-L-03 — list_invoices: skip and limit are passed on; W0 and W2 rows never appear.
    Rules: L1."""
    inv(db, s, ws="0")
    va = inv(db, s, description="A")
    vb = inv(db, s, description="B")
    vc = inv(db, s, description="C")
    vd = inv(db, s, description="D")
    inv(db, s, ws="9")
    commit_point(db)

    result = svc.list_invoices(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len({r.id for r in result}) == 2
    # Then 3
    assert {r.id for r in result} <= {va.id, vb.id, vc.id, vd.id}


# [claude] AIS-L-04
def test_ais_l_04__list_skip_alone(db, s):
    """AIS-L-04 — list_invoices: skip alone is passed on.
    Rules: L1."""
    va = inv(db, s, description="A")
    vb = inv(db, s, description="B")
    vc = inv(db, s, description="C")
    commit_point(db)

    result = svc.list_invoices(db, workspace_id=s.W1.id, skip=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {va.id, vb.id, vc.id}


# [claude] AIS-L-05
def test_ais_l_05__open_page_defaults(db, s):
    """AIS-L-05 — list_open_invoices_page: defaults skip 0 / limit 10.
    Rules: L1, L3."""
    inv_many(db, s, "O", 11, confirmed=True)
    commit_point(db)
    w1_id, a1_id = s.W1.id, s.A1.id

    with spies(db) as (cm, rb):
        result = svc.list_open_invoices_page(db, workspace_id=w1_id, account_id=a1_id)

    # Then 1
    assert isinstance(result, tuple)
    assert len(result[0]) == 10
    # Then 2
    assert result[1] == 11
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0


# [claude] AIS-L-06
def test_ais_l_06__open_page_skip_limit(db, s):
    """AIS-L-06 — list_open_invoices_page: skip and limit=1000 are passed on.
    Rules: L1."""
    inv_many(db, s, "O", 11, confirmed=True)
    commit_point(db)

    result = svc.list_open_invoices_page(
        db, workspace_id=s.W1.id, account_id=s.A1.id, skip=10, limit=1000
    )

    # Then 1
    assert len(result[0]) == 1
    # Then 2
    assert result[1] == 11


# [claude] AIS-L-07
def test_ais_l_07__account_page_default_limit_50(db, s):
    """AIS-L-07 — list_account_invoices_page: default limit is 50, not 100.
    Rules: L2, L3."""
    inv_many(db, s, "P", 51, confirmed=True)
    commit_point(db)
    w1_id, a1_id = s.W1.id, s.A1.id

    with spies(db) as (cm, rb):
        result = svc.list_account_invoices_page(
            db, workspace_id=w1_id, account_id=a1_id
        )

    # Then 1
    assert len(result[0]) == 50
    # Then 2
    assert result[1] == 51
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0


# [claude] AIS-L-08
def test_ais_l_08__account_page_skip_limit_isolated(db, s):
    """AIS-L-08 — list_account_invoices_page: skip and limit=1000 passed; other accounts and workspaces left out.
    Rules: L2."""
    a2 = _add(
        db,
        Account(
            workspace_id=s.W1.id,
            name="Beta Supplies",
            is_active=True,
            is_deleted=False,
            allow_invoices=True,
        ),
    )
    inv_many(db, s, "P", 51, confirmed=True)
    inv(db, s, confirmed=True, account_id=a2.id)
    inv(db, s, ws="9", confirmed=True)
    commit_point(db)

    result = svc.list_account_invoices_page(
        db, workspace_id=s.W1.id, account_id=s.A1.id, skip=50, limit=1000
    )

    # Then 1
    assert len(result[0]) == 1
    # Then 2
    assert result[1] == 51
    # Then 3
    assert result[0][0].account_id == s.A1.id


# [claude] AIS-L-09
def test_ais_l_09__account_page_lists_paid(db, s):
    """AIS-L-09 — list_account_invoices_page is not open-only: a paid invoice is listed.
    Rules: L2."""
    vp = inv(
        db, s, confirmed=True, paid_amount=Decimal("400.00"), payment_status="paid"
    )
    vu = inv(db, s, confirmed=True)
    commit_point(db)

    result = svc.list_account_invoices_page(
        db, workspace_id=s.W1.id, account_id=s.A1.id
    )

    # Then 1
    assert {r.id for r in result[0]} == {vp.id, vu.id}
    # Then 2
    assert result[1] == 2


# [claude] AIS-L-10
def test_ais_l_10__hub_summary_passthrough(db, s):
    """AIS-L-10 — get_invoices_hub_summary returns the manager's tuple.
    Rules: L1, L3."""
    inv(db, s, confirmed=True)
    inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        invoice_amount=Decimal("150.00"),
    )
    commit_point(db)
    w1_id = s.W1.id
    expected = mgr.get_invoices_hub_summary(db, workspace_id=w1_id)

    with spies(db) as (cm, rb):
        result = svc.get_invoices_hub_summary(db, workspace_id=w1_id)

    # Then 1
    assert result == expected
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


# [claude] AIS-L-11
def test_ais_l_11__summarize_passthrough(db, s):
    """AIS-L-11 — summarize_invoices returns the manager's tuple for the account.
    Rules: L1, L3."""
    inv(db, s, confirmed=True)
    inv(db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial")
    commit_point(db)
    w1_id, a1_id = s.W1.id, s.A1.id
    expected = mgr.summarize_invoices(db, workspace_id=w1_id, account_id=a1_id)

    with spies(db) as (cm, rb):
        result = svc.summarize_invoices(db, workspace_id=w1_id, account_id=a1_id)

    # Then 1
    assert result == expected
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


# [claude] AIS-L-12
def test_ais_l_12__get_events(db, s):
    """AIS-L-12 — get_events returns the invoice's events.
    Rules: L1, L3."""
    V = inv(db, s)
    e1 = ievent(db, s, V, description="first", created_at=T1)
    e2 = ievent(db, s, V, description="second", created_at=T2)
    commit_point(db)
    vid, w1_id = V.id, s.W1.id

    with spies(db) as (cm, _rb):
        result = svc.get_events(db, invoice_id=vid, workspace_id=w1_id)

    # DISCREPANCY-1 (card): the events are dicts (invoice_event_dao.get_by_invoice), so the
    # card's `e.id` is read as `e["id"]`; the compared values are the card's.
    # Then 1
    assert [e["id"] for e in result] == [
        e["id"] for e in mgr.get_events(db, vid, w1_id)
    ]
    # Then 2
    assert {e["id"] for e in result} == {e1.id, e2.id}
    # Then 3
    assert cm.call_count == 0


# [claude] AIS-L-13
def test_ais_l_13__get_events_foreign_404(db, s):
    """AIS-L-13 — get_events: another workspace's invoice gets the 404, no rollback.
    Rules: L1, L3; TC6."""
    Z = inv(db, s, ws="9")
    commit_point(db)
    zid, w1_id = Z.id, s.W1.id
    X, _ = mk_x(db)

    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_events(db, invoice_id=zid, workspace_id=w1_id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Invoice with ID {zid} not found"
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# [claude] AIS-L-14
def test_ais_l_14__get_items(db, s):
    """AIS-L-14 — get_items returns the invoice's lines.
    Rules: L1, L3."""
    V = inv(db, s)
    l1 = invl(db, s, V, "150.00", 1)
    l2 = invl(db, s, V, "250.00", 2)
    commit_point(db)
    vid, w1_id = V.id, s.W1.id
    ids = {l1.id, l2.id}

    with spies(db) as (cm, rb):
        result = svc.get_items(db, invoice_id=vid, workspace_id=w1_id)

    # Then 1
    assert {i.id for i in result} == ids
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


# [claude] AIS-L-15
def test_ais_l_15__get_items_missing_404(db, s):
    """AIS-L-15 — get_items: a missing invoice gets the 404.
    Rules: L1."""
    inv(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(db, invoice_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Invoice with ID 999999999 not found"


# [claude] AIS-L-16
def test_ais_l_16__open_page_prioritize_forwarded(db, s):
    """AIS-L-16 — list_open_invoices_page forwards prioritize_purchase_order_id.
    Rules: L1, L1a."""
    O = po(db, s, "1", ready=True)
    vp = inv(
        db,
        s,
        confirmed=True,
        description="PO invoice",
        order_type="purchase_order",
        order_id=O.id,
    )
    inv_many(db, s, "O", 11, confirmed=True)
    commit_point(db)
    expected = mgr.list_open_invoices_page(
        db,
        workspace_id=s.W1.id,
        account_id=s.A1.id,
        prioritize_purchase_order_id=O.id,
        skip=0,
        limit=1,
    )

    result = svc.list_open_invoices_page(
        db,
        workspace_id=s.W1.id,
        account_id=s.A1.id,
        prioritize_purchase_order_id=O.id,
        limit=1,
    )

    # Then 1
    assert [r.id for r in result[0]] == [r.id for r in expected[0]]
    # Then 2
    assert [r.id for r in result[0]] == [vp.id]
    # Then 3
    assert result[1] == 12


# [claude] AIS-L-17
def test_ais_l_17__list_filter_forwarded(db, s):
    """AIS-L-17 — list_invoices forwards a filter.
    Rules: L1, L1a."""
    inv(db, s)
    vc = inv(db, s, confirmed=True)
    commit_point(db)

    result = svc.list_invoices(db, workspace_id=s.W1.id, invoice_status="confirmed")

    # Then 1
    assert [r.id for r in result] == [vc.id]


# [claude] AIS-L-18
def test_ais_l_18__account_page_filter_forwarded(db, s):
    """AIS-L-18 — list_account_invoices_page forwards a filter.
    Rules: L2, L1a."""
    inv(db, s, confirmed=True)
    vr = inv(db, s, confirmed=True, invoice_type="receivable")
    commit_point(db)

    result = svc.list_account_invoices_page(
        db, workspace_id=s.W1.id, account_id=s.A1.id, invoice_type="receivable"
    )

    # Then 1
    assert [r.id for r in result[0]] == [vr.id]
    # Then 2
    assert result[1] == 1


# --------------------------------------------------------------------------- #
# update_invoice
# --------------------------------------------------------------------------- #


# [claude] AIS-U-01
def test_ais_u_01__draft_updated_po_untouched(db, s):
    """AIS-U-01 — a draft is updated and committed; its PO is not touched.
    Rules: update_invoice U1, U2; TC1, TC2."""
    V = inv(db, s, description="Old desc")
    O = po(db, s, "1", ready=True, of=V)
    P = poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    snap_o, snap_p = snap(db, O), snap(db, P)

    result = svc.update_invoice(
        db,
        invoice_id=V.id,
        invoice_in=AccountInvoiceUpdate(description="New desc"),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == V.id
    db.rollback()
    # Then 3
    assert reread(db, AccountInvoice, V.id).description == "New desc"
    # Then 4
    assert snap(db, O) == snap_o
    # Then 5
    assert snap(db, P) == snap_p
    # Then 6
    assert types(db, PurchaseOrder, O.id) == []


# [claude] AIS-U-02
def test_ais_u_02__confirmed_due_date_so_untouched(db, s):
    """AIS-U-02 — a confirmed invoice's due date changes; its sales order is not touched.
    Rules: update_invoice U1, U2."""
    V = inv(db, s, confirmed=True)
    S = so(db, s, "1", finalized_by=V)
    commit_point(db)
    snap_s = snap(db, S)

    result = svc.update_invoice(
        db,
        invoice_id=V.id,
        invoice_in=AccountInvoiceUpdate(due_date=date(2026, 12, 31)),
        workspace_id=s.W1.id,
        user_id=s.U2.id,
    )

    # Then 1
    assert result.id == V.id
    db.rollback()
    # Then 2
    row = reread(db, AccountInvoice, V.id)
    assert row.due_date == date(2026, 12, 31)
    assert row.invoice_status == "confirmed"
    # Then 3
    assert snap(db, S) == snap_s
    # Then 4
    assert types(db, SalesOrder, S.id) == []


# [claude] AIS-U-03
def test_ais_u_03__foreign_invoice_404(db, s):
    """AIS-U-03 — another workspace's invoice: 404 passes unchanged, nothing saved.
    Rules: update_invoice U1; TC3."""
    Z = inv(db, s, ws="9", description="Far")
    commit_point(db)
    snap_z = snap(db, Z)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_invoice(
            db,
            invoice_id=Z.id,
            invoice_in=AccountInvoiceUpdate(description="New"),
            workspace_id=s.W1.id,
            user_id=s.U2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {Z.id} not found"
    # Then 4
    assert x not in db
    # Then 5
    assert session_clean(db)
    # Then 6
    assert snap(db, Z) == snap_z
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-U-04
def test_ais_u_04__failing_commit_keeps_old(db, s):
    """AIS-U-04 — a failing commit leaves the old description.
    Rules: update_invoice U1; TC4."""
    V = inv(db, s, description="Old desc")
    commit_point(db)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_invoice(
                db,
                invoice_id=vid,
                invoice_in=AccountInvoiceUpdate(description="New desc"),
                workspace_id=w1_id,
                user_id=u2_id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, AccountInvoice, vid).description == "Old desc"


# [claude] AIS-U-05
def test_ais_u_05__commits_once(db, s):
    """AIS-U-05 — the update commits exactly once and does not roll back.
    Rules: update_invoice U1; TC1."""
    V = inv(db, s, description="Old desc")
    commit_point(db)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with spies(db) as (cm, rb):
        result = svc.update_invoice(
            db,
            invoice_id=vid,
            invoice_in=AccountInvoiceUpdate(description="New desc"),
            workspace_id=w1_id,
            user_id=u2_id,
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0


# --------------------------------------------------------------------------- #
# delete_invoice
# --------------------------------------------------------------------------- #


# [claude] AIS-D-01
def test_ais_d_01__draft_deleted_object_returned(db, s):
    """AIS-D-01 — a draft with no order is deleted and committed; the deleted object is returned.
    Rules: delete_invoice D2, D3, D6; TC1."""
    V = inv(db, s)
    invl(db, s, V, "100.00", 1)
    ievent(db, s, V, description="n", created_at=T1)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert isinstance(result, AccountInvoice)
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid) is None
    # Then 3
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == vid) == 0
    # Then 4
    assert count_where(db, InvoiceEvent, InvoiceEvent.invoice_id == vid) == 0
    # Then 5
    assert order_event_counts(db) == (0, 0, 0, 0)


# [claude] AIS-D-02
def test_ais_d_02__deleted_object_not_refreshed(db, s):
    """AIS-D-02 — the deleted object is not re-read.
    Rules: delete_invoice D3."""
    V = inv(db, s)
    commit_point(db)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with patch.object(db, "refresh", wraps=db.refresh) as rf:
        result = svc.delete_invoice(
            db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert rf.call_count == 0


# [claude] AIS-D-03
def test_ais_d_03__po_unlinked_one_event(db, s):
    """AIS-D-03 — the PO's draft invoice: the PO is unlinked with one event, sections and stage kept.
    Rules: delete_invoice D1, D4; TC1."""
    V = inv(db, s)
    O = po(
        db,
        s,
        "1",
        of=V,
        supplier_confirmed=True,
        details_confirmed=True,
        current_status_id=s.SP1.id,
    )
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.invoice_id is None
    assert o.invoice_confirmed is False
    assert o.paid is False
    # Then 3
    o = reread(db, PurchaseOrder, O.id)
    assert o.supplier_confirmed is True
    assert o.details_confirmed is True
    assert o.items_confirmed is False
    assert o.current_status_id == s.SP1.id
    # Then 4
    assert len(EV(db, PurchaseOrder, O.id)) == 1
    # Then 5
    ev = EV(db, PurchaseOrder, O.id)
    assert ev[0].event_type == "invoice_draft_deleted"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert EV(db, PurchaseOrder, O.id)[0].description == f"Draft invoice #{vid} deleted"


# [claude] AIS-D-04
@xfail(2968)
def test_ais_d_04__po_event_metadata_names_invoice(db, s):
    """AIS-D-04 — the PO's "draft invoice deleted" event names the deleted invoice in its metadata.
    Rules: delete_invoice D4a [BUG-2968]."""
    V = inv(db, s)
    O = po(db, s, "1", of=V)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    # Then 2
    assert types(db, PurchaseOrder, O.id) == ["invoice_draft_deleted"]
    # Then 3
    assert EV(db, PurchaseOrder, O.id)[0].metadata_json == {"invoice_id": vid}


# [claude] AIS-D-05
def test_ais_d_05__confirmed_refused(db, s):
    """AIS-D-05 — a confirmed invoice is refused; the PO and its events are unchanged.
    Rules: delete_invoice D1, Errors row 2; TC3."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    before = commit_point(db)
    snap_v, snap_o = snap(db, V), snap(db, O)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Only draft invoices can be deleted. This invoice is 'confirmed'. Use void instead."
    )
    # Then 4
    assert session_clean(db)
    # Then 5
    assert snap(db, V) == snap_v
    # Then 6
    assert snap(db, O) == snap_o
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-D-06
def test_ais_d_06__foreign_invoice_404(db, s):
    """AIS-D-06 — another workspace's invoice: 404, nothing deleted.
    Rules: delete_invoice D1, Errors row 1."""
    Z = inv(db, s, ws="9")
    commit_point(db)
    snap_z = snap(db, Z)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_invoice(db, invoice_id=Z.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {Z.id} not found"
    # Then 4
    assert snap(db, Z) == snap_z
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


# [claude] AIS-D-07
@xfail(639)
def test_ais_d_07__payment_history_400(db, s):
    """AIS-D-07 — a draft with payment history is refused with the 400; nothing deleted.
    Rules: delete_invoice D1, Errors row 4 [BUG-639]."""
    V = inv(db, s)
    pay(db, s, V, "100.00", voided=True)
    O = po(db, s, "1", of=V)
    commit_point(db)
    snap_v, snap_o = snap(db, V), snap(db, O)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail == "Invoice has payment history — confirm and void it instead"
    )
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, O) == snap_o


# [claude] AIS-D-08
def test_ais_d_08__payment_history_never_deleted(db, s):
    """AIS-D-08 — a draft with payment history is never deleted (today and after the fix).
    Rules: delete_invoice D1 [BUG-639]; TC3."""
    V = inv(db, s)
    P = pay(db, s, V, "100.00", voided=True)
    O = po(db, s, "1", of=V)
    commit_point(db)
    vid, pid, oid = V.id, P.id, O.id
    snap_o = snap(db, O)
    _, x_id = mk_x(db)

    with pytest.raises(Exception):
        svc.delete_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    v = reread(db, AccountInvoice, vid)
    assert v is not None
    assert v.invoice_status == "draft"
    # Then 2
    p = reread(db, InvoicePayment, pid)
    assert p is not None
    assert p.is_voided is True
    # Then 3
    assert snap(db, O) == snap_o
    # Then 4
    assert types(db, PurchaseOrder, oid) == []
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


# [claude] AIS-D-09
@xfail(2730)
def test_ais_d_09__completed_so_draft_frozen(db, s):
    """AIS-D-09 — a completed sales order's draft invoice is frozen: 400, nothing deleted.
    Rules: delete_invoice D1, Errors row 3 [BUG-2730]."""
    V = inv(db, s, invoice_type="receivable")
    S = so(db, s, "1", so_ready=True, of=V, order_completed=True)
    commit_point(db)
    snap_v, snap_s = snap(db, V), snap(db, S)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == LOCK("sales order")
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, S) == snap_s


# [claude] AIS-D-10
@xfail(2732)
def test_ais_d_10__so_unlinked_with_event(db, s):
    """AIS-D-10 — a sales order's draft invoice: the order is unlinked with its event.
    Rules: delete_invoice D5 [BUG-2732]."""
    V = inv(db, s, invoice_type="receivable")
    S = so(db, s, "1", of=V, is_invoiced=True)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, SalesOrder, S.id).invoice_id is None
    # Then 3
    row = reread(db, SalesOrder, S.id)
    assert row.is_invoiced is False
    assert row.invoice_confirmed is False
    assert row.paid is False
    # Then 4
    assert types(db, SalesOrder, S.id) == ["invoice_draft_deleted"]
    # Then 5
    ev = EV(db, SalesOrder, S.id)
    assert ev[0].description == f"Draft invoice #{vid} deleted"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert EV(db, SalesOrder, S.id)[0].metadata_json == {"invoice_id": vid}


# [claude] AIS-D-11
@xfail(2732)
def test_ais_d_11__eo_logs_delete(db, s):
    """AIS-D-11 — an expense order's draft invoice: the order logs the delete.
    Rules: delete_invoice D5 [BUG-2732]."""
    V = inv(db, s)
    E = eo(db, s, "EXP-2026-009", of=V)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, E.id).invoice_id is None
    # Then 3
    assert types(db, ExpenseOrder, E.id) == ["invoice_draft_deleted"]
    # Then 4
    ev = EV(db, ExpenseOrder, E.id)
    assert ev[0].description == f"Draft invoice #{vid} deleted"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert EV(db, ExpenseOrder, E.id)[0].metadata_json == {"invoice_id": vid}


# [claude] AIS-D-12
@xfail(2732)
def test_ais_d_12__wo_logs_delete(db, s):
    """AIS-D-12 — a work order's draft invoice: the order logs the delete.
    Rules: delete_invoice D5 [BUG-2732]."""
    V = inv(db, s, invoice_type="receivable")
    WO = wo(db, s, "WO-2026-031", of=V)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, WO.id).invoice_id is None
    # Then 3
    assert types(db, WorkOrder, WO.id) == ["invoice_draft_deleted"]
    # Then 4
    ev = EV(db, WorkOrder, WO.id)
    assert ev[0].description == f"Draft invoice #{vid} deleted"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert EV(db, WorkOrder, WO.id)[0].metadata_json == {"invoice_id": vid}


# [claude] AIS-D-13
def test_ais_d_13__orders_no_longer_point_at_deleted(db, s):
    """AIS-D-13 — sales, expense and work orders no longer point at the deleted invoice.
    Rules: delete_invoice D5 (link cleared; holds today through the database and after the fix)."""
    V = inv(db, s)
    S = so(db, s, "1", of=V)
    E = eo(db, s, "EXP-2026-009", of=V)
    WO = wo(db, s, "WO-2026-031", of=V)
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, SalesOrder, S.id).invoice_id is None
    # Then 3
    assert reread(db, ExpenseOrder, E.id).invoice_id is None
    # Then 4
    assert reread(db, WorkOrder, WO.id).invoice_id is None


# [claude] AIS-D-14
def test_ais_d_14__foreign_so_untouched(db, s):
    """AIS-D-14 — another workspace's sales order pointing at the invoice keeps its flags and gets no event.
    Rules: delete_invoice D5 (other workspace never touched); HR-16."""
    V = inv(db, s)
    S9 = so(
        db,
        s,
        "9",
        ws="9",
        invoice_id=V.id,
        is_invoiced=True,
        current_status_id=s.SD9.id,
    )
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, SalesOrder, S9.id).is_invoiced is True
    # Then 3
    assert types(db, SalesOrder, S9.id) == []


# [claude] AIS-D-15
def test_ais_d_15__failing_commit_keeps_invoice_and_link(db, s):
    """AIS-D-15 — a failing commit keeps the invoice and the PO link.
    Rules: delete_invoice D2; TC4."""
    V = inv(db, s)
    O = po(db, s, "1", of=V)
    commit_point(db)
    vid, oid, w1_id, u2_id = V.id, O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_invoice(db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, AccountInvoice, vid) is not None
    # Then 4
    assert reread(db, PurchaseOrder, oid).invoice_id == vid
    # Then 5
    assert types(db, PurchaseOrder, oid) == []


# [claude] AIS-D-16
def test_ais_d_16__delete_commits_once(db, s):
    """AIS-D-16 — delete commits exactly once and does not roll back.
    Rules: delete_invoice D2, D4; TC1."""
    V = inv(db, s)
    O = po(db, s, "1", of=V)
    vid = V.id
    commit_point(db)

    with spies(db) as (cm, rb):
        result = svc.delete_invoice(
            db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    db.rollback()
    # Then 4
    assert reread(db, PurchaseOrder, O.id).invoice_id is None
    # Then 5
    assert types(db, PurchaseOrder, O.id) == ["invoice_draft_deleted"]


# [claude] AIS-D-17
def test_ais_d_17__w0_po_not_the_pos_invoice(db, s):
    """AIS-D-17 — a W0 PO pointing at the draft is not "the PO's invoice": it keeps its flags and gets no event.
    Rules: delete_invoice D1, D4, D6; Overview "The PO's invoice"; HR-16."""
    V = inv(db, s)
    Z = po(
        db,
        s,
        "0",
        ws="0",
        invoice_id=V.id,
        invoice_ever_linked=True,
        invoice_confirmed=True,
        paid=True,
    )
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert gone(db, AccountInvoice, vid)
    # Then 3
    z = reread(db, PurchaseOrder, Z.id)
    assert z.invoice_confirmed is True
    assert z.paid is True
    # Then 4
    assert types(db, PurchaseOrder, Z.id) == []


# [claude] AIS-D-18
def test_ais_d_18__w2_po_not_the_pos_invoice(db, s):
    """AIS-D-18 — a W2 PO pointing at the draft is not "the PO's invoice": it keeps its flags and gets no event.
    Rules: delete_invoice D1, D4, D6; HR-16."""
    V = inv(db, s)
    Z = po(
        db,
        s,
        "9",
        ws="9",
        invoice_id=V.id,
        invoice_ever_linked=True,
        invoice_confirmed=True,
        paid=True,
    )
    vid = V.id
    commit_point(db)

    result = svc.delete_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert gone(db, AccountInvoice, vid)
    # Then 3
    z = reread(db, PurchaseOrder, Z.id)
    assert z.invoice_confirmed is True
    assert z.paid is True
    # Then 4
    assert types(db, PurchaseOrder, Z.id) == []


# --------------------------------------------------------------------------- #
# revert_to_draft
# --------------------------------------------------------------------------- #


# [claude] AIS-V-01
def test_ais_v_01__confirmed_po_invoice_reverted(db, s):
    """AIS-V-01 — a confirmed PO invoice goes back to draft; the PO is not touched.
    Rules: revert_to_draft V1, V2; TC1, TC2."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    P = poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    snap_o, snap_p = snap(db, O), snap(db, P)

    result = svc.revert_to_draft(
        db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == V.id
    db.rollback()
    # Then 3
    assert reread(db, AccountInvoice, V.id).invoice_status == "draft"
    # Then 4
    assert snap(db, O) == snap_o
    # Then 5
    assert snap(db, P) == snap_p
    # Then 6
    assert types(db, PurchaseOrder, O.id) == []


# [claude] AIS-V-02
def test_ais_v_02__active_payments_400(db, s):
    """AIS-V-02 — active payments: the manager's 400 passes unchanged, nothing saved.
    Rules: revert_to_draft V1; TC3."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    pay(db, s, V, "100.00")
    before = commit_point(db)
    snap_v = snap(db, V)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == (
        "Cannot revert to draft — invoice has active payments. Void all payments first."
    )
    # Then 4
    assert x not in db
    # Then 5
    assert session_clean(db)
    # Then 6
    assert snap(db, V) == snap_v
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-V-03
def test_ais_v_03__receiving_started_400_loose(db, s):
    """AIS-V-03 — receiving started: refused with a 400 about receiving; nothing saved.
    Rules: revert_to_draft V1."""
    V = inv(db, s, confirmed=True, receiving_started=True)
    O = po(db, s, "1", locked_by=V)
    commit_point(db)
    snap_v, snap_o = snap(db, V), snap(db, O)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail.startswith("Cannot revert to draft — ")
    assert "receiv" in exc.value.detail
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, O) == snap_o


# [claude] AIS-V-04
@xfail(2736)
def test_ais_v_04__receiving_started_exact_text(db, s):
    """AIS-V-04 — receiving started: the detail is the BUG-2736 text.
    Rules: revert_to_draft V1 [BUG-2736]."""
    V = inv(db, s, confirmed=True, receiving_started=True)
    commit_point(db)

    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RCVTXT


# [claude] AIS-V-05
@xfail(2730)
def test_ais_v_05__completed_eo_invoice_frozen(db, s):
    """AIS-V-05 — a completed expense order's invoice is frozen.
    Rules: revert_to_draft V1 [BUG-2730]."""
    V = inv(db, s, confirmed=True)
    eo(db, s, "EXP-2026-009", of=V, completed_at=T0)
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == LOCK("expense order")
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-V-06
@xfail(2733)
def test_ais_v_06__credit_note_not_reverted(db, s):
    """AIS-V-06 — a return credit note cannot be reverted.
    Rules: revert_to_draft V1 [BUG-2733]."""
    O = po(db, s, "1", ready=True)
    CN = inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        order_type="purchase_order",
        order_id=O.id,
    )
    po_return(db, s, O, CN)
    commit_point(db)
    snap_cn = snap(db, CN)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=CN.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == CNTXT
    # Then 4
    assert snap(db, CN) == snap_cn


# [claude] AIS-V-07
def test_ais_v_07__draft_cannot_be_reverted(db, s):
    """AIS-V-07 — a draft cannot be reverted: 400 passes unchanged.
    Rules: revert_to_draft V1."""
    V = inv(db, s)
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.revert_to_draft(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."
    )
    # Then 4
    assert snap(db, V) == snap_v


# --------------------------------------------------------------------------- #
# resync_items
# --------------------------------------------------------------------------- #


# [claude] AIS-S-01
def test_ais_s_01__po_invoice_rebuilt(db, s):
    """AIS-S-01 — a PO invoice is rebuilt from the PO lines in line order and committed.
    Rules: resync_items S4, S5; TC1, TC2."""
    O = po(db, s, "1", ready=True)
    V = inv(db, s, order_type="purchase_order", order_id=O.id)
    OL = invl(db, s, V, "999.00", 1)
    pl2 = poline(db, s, O, 2)
    pl1 = poline(
        db,
        s,
        O,
        1,
        item_id=s.I2.id,
        quantity_ordered=Decimal("3.00"),
        unit_price=Decimal("5.00"),
        line_subtotal=Decimal("15.00"),
    )
    commit_point(db)
    snap_o = snap(db, O)
    vid, olid = V.id, OL.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == vid
    db.rollback()
    # Then 3
    assert [ln.line_number for ln in LINES(db, vid)] == [1, 2]
    # Then 4
    first = LINES(db, vid)[0]
    assert first.description == "Nut"
    assert first.item_id == s.I2.id
    assert first.source_order_item_id == pl1.id
    assert first.source_order_item_type == "po_item"
    assert first.quantity == Decimal("3.00")
    assert first.unit == "box"
    assert first.unit_price == Decimal("5.00")
    assert first.line_subtotal == Decimal("15.00")
    # Then 5
    second = LINES(db, vid)[1]
    assert second.description == "Bolt"
    assert second.item_id == s.I1.id
    assert second.source_order_item_id == pl2.id
    assert second.unit == "pcs"
    assert second.line_subtotal == Decimal("20.00")
    # Then 6
    assert gone(db, InvoiceItem, olid)
    # Then 7
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_amount == Decimal("35.00")
    assert v.payment_status == "unpaid"
    assert v.last_synced_at is not None
    assert v.invoice_status == "draft"
    # Then 8
    assert itypes(db, vid) == ["items_synced"]
    # Then 9
    assert IEV(db, vid)[0].description == "Items synced from order (2 lines)"
    # Then 10
    assert snap(db, O) == snap_o


# [claude] AIS-S-02
def test_ais_s_02__voided_po_still_used(db, s):
    """AIS-S-02 — a voided PO is still found and its lines are used.
    Rules: resync_items S5."""
    O = po(db, s, "1", voided=True)
    V = inv(db, s, order_type="purchase_order", order_id=O.id)
    pl = poline(db, s, O, 1)
    commit_point(db)
    vid = V.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert len(LINES(db, vid)) == 1
    # Then 3
    assert LINES(db, vid)[0].source_order_item_id == pl.id


# [claude] AIS-S-03
def test_ais_s_03__missing_po_404(db, s):
    """AIS-S-03 — a missing PO: 404, old lines kept, nothing saved.
    Rules: resync_items S5, Errors row 4; TC3."""
    V = inv(db, s, order_type="purchase_order", order_id=MISSING)
    OL = invl(db, s, V, "999.00", 1)
    before = commit_point(db)
    snap_ol = snap(db, OL)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Purchase order with ID 999999999 not found"
    # Then 4
    assert session_clean(db)
    # Then 5
    assert snap(db, OL) == snap_ol
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-S-04
def test_ais_s_04__w0_po_not_found(db, s):
    """AIS-S-04 — a W0 PO (lower workspace id) is not found.
    Rules: resync_items S5; HR-16."""
    Z0 = po(db, s, "0", ws="0")
    poline(db, s, Z0, 1)
    V = inv(db, s, order_type="purchase_order", order_id=Z0.id)
    OL = invl(db, s, V, "999.00", 1)
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Purchase order with ID {Z0.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-05
def test_ais_s_05__w2_po_not_found(db, s):
    """AIS-S-05 — a W2 PO (higher workspace id) is not found.
    Rules: resync_items S5; HR-16."""
    V = inv(db, s, order_type="purchase_order")
    OL = invl(db, s, V, "999.00", 1)
    Z2 = po(db, s, "9", ws="9")
    poline(db, s, Z2, 1)
    V.order_id = Z2.id
    db.flush()
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Purchase order with ID {Z2.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-06
def test_ais_s_06__unpriced_po_line_fails_at_flush(db, s):
    """AIS-S-06 — an unpriced PO line fails at flush; old lines kept, nothing saved.
    Rules: resync_items S5, Errors row 7; TC3."""
    O = po(db, s, "1")
    poline(db, s, O, 1, unit_price=None, line_subtotal=None)
    V = inv(db, s, order_type="purchase_order", order_id=O.id)
    OL = invl(db, s, V, "999.00", 1)
    before = commit_point(db)
    snap_ol, snap_v = snap(db, OL), snap(db, V)
    vid = V.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(IntegrityError):
        svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert snap(db, OL) == snap_ol
    # Then 3
    assert snap(db, V) == snap_v
    # Then 4
    assert counts(db) == before
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert usable(db)


# [claude] AIS-S-07
def test_ais_s_07__confirmed_cannot_resync(db, s):
    """AIS-S-07 — a confirmed invoice cannot be resynced.
    Rules: resync_items S2, Errors row 2."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    V = inv(db, s, confirmed=True, order_type="purchase_order", order_id=O.id)
    OL = invl(db, s, V, "400.00", 1)
    before = commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DRAFT_ONLY
    # Then 4
    assert snap(db, OL) == snap_ol
    # Then 5
    assert counts(db) == before


# [claude] AIS-S-08
def test_ais_s_08__voided_cannot_resync(db, s):
    """AIS-S-08 — a voided invoice cannot be resynced.
    Rules: resync_items S2."""
    O = po(db, s, "1")
    V = inv(
        db,
        s,
        invoice_status="voided",
        void_note="Old reason",
        order_type="purchase_order",
        order_id=O.id,
    )
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DRAFT_ONLY
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-S-09
def test_ais_s_09__unlinked_confirmed_draft_error_first(db, s):
    """AIS-S-09 — an unlinked invoice that is not a draft gets the draft error first.
    Rules: resync_items S2, S3 (order of checks)."""
    V = inv(db, s, confirmed=True)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DRAFT_ONLY


# [claude] AIS-S-10
def test_ais_s_10__order_id_none_not_linked(db, s):
    """AIS-S-10 — order_id None: not linked.
    Rules: resync_items S3, Errors row 3."""
    V = inv(db, s, order_type="purchase_order")
    OL = invl(db, s, V, "999.00", 1)
    before = commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOT_LINKED
    # Then 4
    assert snap(db, OL) == snap_ol
    # Then 5
    assert counts(db) == before


# [claude] AIS-S-11
def test_ais_s_11__order_id_zero_not_linked(db, s):
    """AIS-S-11 — order_id 0: not linked.
    Rules: resync_items S3."""
    V = inv(db, s, order_type="purchase_order", order_id=0)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOT_LINKED


# [claude] AIS-S-12
def test_ais_s_12__order_type_none_not_linked(db, s):
    """AIS-S-12 — order_type None with an order id: not linked.
    Rules: resync_items S3."""
    O = po(db, s, "1")
    V = inv(db, s, order_id=O.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOT_LINKED


# [claude] AIS-S-13
def test_ais_s_13__order_type_empty_not_linked(db, s):
    """AIS-S-13 — order_type "" with an order id: not linked.
    Rules: resync_items S3."""
    O = po(db, s, "1")
    V = inv(db, s, order_type="", order_id=O.id)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOT_LINKED


# [claude] AIS-S-14
def test_ais_s_14__eo_invoice_rebuilt_renumbered(db, s):
    """AIS-S-14 — an expense order invoice is rebuilt from its lines, renumbered 1, 2.
    Rules: resync_items S4, S6."""
    E = eo(db, s, "EXP-2026-009")
    el9 = eoline(
        db,
        s,
        E,
        9,
        description="",
        quantity=Decimal("0"),
        unit_price=Decimal("7.00"),
        line_subtotal=Decimal("7.00"),
    )
    el5 = eoline(db, s, E, 5)
    V = inv(db, s, order_type="expense_order", order_id=E.id)
    OL = invl(db, s, V, "999.00", 1)
    commit_point(db)
    snap_e = snap(db, E)
    vid, olid = V.id, OL.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert [ln.line_number for ln in LINES(db, vid)] == [1, 2]
    # Then 3
    first = LINES(db, vid)[0]
    assert first.description == "Paper"
    assert first.item_id is None
    assert first.source_order_item_id == el5.id
    assert first.source_order_item_type == "eo_item"
    assert first.quantity == Decimal("2")
    assert first.unit == "box"
    assert first.unit_price == Decimal("5.00")
    assert first.line_subtotal == Decimal("10.00")
    # Then 4
    second = LINES(db, vid)[1]
    assert second.description == f"Expense item {el9.id}"
    assert second.source_order_item_id == el9.id
    assert second.quantity == Decimal("1")
    assert second.line_subtotal == Decimal("7.00")
    # Then 5
    assert gone(db, InvoiceItem, olid)
    # Then 6
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("17.00")
    # Then 7
    assert IEV(db, vid)[0].description == "Items synced from order (2 lines)"
    # Then 8
    assert snap(db, E) == snap_e


# [claude] AIS-S-15
def test_ais_s_15__foreign_eo_not_found(db, s):
    """AIS-S-15 — another workspace's expense order is not found.
    Rules: resync_items S6, Errors row 4; HR-16."""
    V = inv(db, s, order_type="expense_order")
    OL = invl(db, s, V, "999.00", 1)
    E9 = eo(db, s, "EXP-2026-900", ws="9")
    eoline(db, s, E9, 1)
    V.order_id = E9.id
    db.flush()
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Expense order with ID {E9.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-16
def test_ais_s_16__missing_eo_404(db, s):
    """AIS-S-16 — a missing expense order: 404.
    Rules: resync_items S6, Errors row 4."""
    V = inv(db, s, order_type="expense_order", order_id=MISSING)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Expense order with ID 999999999 not found"
    # Then 4
    assert counts(db) == before


# [claude] AIS-S-17
@xfail(2963)
def test_ais_s_17__so_invoice_rebuilt(db, s):
    """AIS-S-17 — a sales order invoice is rebuilt from the order lines.
    Rules: resync_items S4, S6a [BUG-2963]."""
    S = so(db, s, "1")
    la = soline(db, s, S)
    lb = soline(
        db,
        s,
        S,
        item_id=None,
        description="Crate",
        quantity_ordered=Decimal("2.00"),
        unit_price=Decimal("50.00"),
        line_total=Decimal("100.00"),
    )
    V = inv(db, s, invoice_type="receivable", order_type="sales_order", order_id=S.id)
    invl(db, s, V, "999.00", 1)
    commit_point(db)
    vid = V.id

    # Then 1
    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    assert result.id == vid
    db.rollback()
    # Then 2
    assert [ln.line_number for ln in LINES(db, vid)] == [1, 2]
    # Then 3
    first = LINES(db, vid)[0]
    assert first.description == "Bolt"
    assert first.item_id == s.I1.id
    assert first.source_order_item_id == la.id
    assert first.source_order_item_type == "so_item"
    assert first.quantity == Decimal("10.00")
    assert first.unit == "pcs"
    assert first.unit_price == Decimal("2000.00")
    assert first.line_subtotal == Decimal("20000.00")
    # Then 4
    second = LINES(db, vid)[1]
    assert second.description == "Crate"
    assert second.item_id is None
    assert second.unit is None
    assert second.source_order_item_id == lb.id
    assert second.line_subtotal == Decimal("100.00")
    # Then 5
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("20100.00")
    # Then 6
    assert IEV(db, vid)[0].description == "Items synced from order (2 lines)"


# [claude] AIS-S-18
@xfail(2963)
def test_ais_s_18__missing_so_404(db, s):
    """AIS-S-18 — a missing sales order: 404, lines kept.
    Rules: resync_items S6a, Errors row 5 [BUG-2963]."""
    V = inv(
        db, s, invoice_type="receivable", order_type="sales_order", order_id=MISSING
    )
    OL = invl(db, s, V, "999.00", 1)
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-19
@xfail(2963)
def test_ais_s_19__foreign_so_404(db, s):
    """AIS-S-19 — another workspace's sales order: 404.
    Rules: resync_items S6a [BUG-2963]; HR-16."""
    S9 = so(db, s, "9", ws="9", current_status_id=s.SD9.id)
    V = inv(db, s, invoice_type="receivable", order_type="sales_order", order_id=S9.id)
    OL = invl(db, s, V, "999.00", 1)
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Sales order with ID {S9.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-20
@xfail(2964)
def test_ais_s_20__wo_invoice_one_labour_line(db, s):
    """AIS-S-20 — a work order invoice is rebuilt as its one labour line.
    Rules: resync_items S4, S7 [BUG-2964]."""
    WO = wo(db, s, "WO-2026-031")
    V = inv(
        db,
        s,
        invoice_type="receivable",
        invoice_amount=Decimal("5000.00"),
        order_type="work_order",
        order_id=WO.id,
    )
    invl(db, s, V, "5000.00", 1)
    commit_point(db)
    vid = V.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert len(LINES(db, vid)) == 1
    # Then 3
    line = LINES(db, vid)[0]
    assert line.line_number == 1
    assert line.description == "Pump repair"
    assert line.item_id is None
    assert line.source_order_item_id is None
    assert line.source_order_item_type == "wo_labor"
    assert line.quantity == Decimal("1")
    assert line.unit is None
    assert line.unit_price == Decimal("5000.00")
    assert line.line_subtotal == Decimal("5000.00")
    # Then 4
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_amount == Decimal("5000.00")
    assert v.payment_status == "unpaid"
    # Then 5
    assert IEV(db, vid)[0].description == "Items synced from order (1 lines)"


# [claude] AIS-S-21
@xfail(2964)
def test_ais_s_21__wo_no_cost_zero_line(db, s):
    """AIS-S-21 — a work order with no cost gives one 0.00 line.
    Rules: resync_items S7 [BUG-2964]."""
    WO = wo(db, s, "WO-2026-031", cost=None)
    V = inv(db, s, invoice_type="receivable", order_type="work_order", order_id=WO.id)
    invl(db, s, V, "5000.00", 1)
    commit_point(db)
    vid = V.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert len(LINES(db, vid)) == 1
    # Then 3
    assert LINES(db, vid)[0].unit_price == Decimal("0.00")
    assert LINES(db, vid)[0].line_subtotal == Decimal("0.00")


# [claude] AIS-S-22
@xfail(2964)
def test_ais_s_22__deleted_wo_not_found(db, s):
    """AIS-S-22 — a soft-deleted work order is not found; lines kept.
    Rules: resync_items S7, Errors row 5 [BUG-2964]."""
    WO = wo(db, s, "WO-2026-031", is_deleted=True)
    V = inv(db, s, invoice_type="receivable", order_type="work_order", order_id=WO.id)
    OL = invl(db, s, V, "5000.00", 1)
    before = commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {WO.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol
    # Then 5
    assert counts(db) == before


# [claude] AIS-S-23
@xfail(2964)
def test_ais_s_23__foreign_wo_not_found(db, s):
    """AIS-S-23 — another workspace's work order is not found.
    Rules: resync_items S7 [BUG-2964]; HR-16."""
    WO9 = wo(db, s, "WO-2026-900", ws="9")
    V = inv(db, s, invoice_type="receivable", order_type="work_order", order_id=WO9.id)
    OL = invl(db, s, V, "5000.00", 1)
    commit_point(db)
    snap_ol = snap(db, OL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {WO9.id} not found"
    # Then 4
    assert snap(db, OL) == snap_ol


# [claude] AIS-S-24
@xfail(2964)
def test_ais_s_24__unknown_order_type_refused(db, s):
    """AIS-S-24 — an unknown order type is refused and the lines are kept.
    Rules: resync_items S8, Errors row 6 [BUG-2964]."""
    V = inv(
        db, s, invoice_amount=Decimal("400.00"), order_type="transfer_order", order_id=7
    )
    OL = invl(db, s, V, "400.00", 1)
    before = commit_point(db)
    snap_ol, snap_v = snap(db, OL), snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail == "Resync is not supported for order type 'transfer_order'."
    )
    # Then 4
    assert snap(db, OL) == snap_ol
    # Then 5
    assert snap(db, V) == snap_v
    # Then 6
    assert counts(db) == before


# [claude] AIS-S-25
@xfail(2962)
def test_ais_s_25__invoice_locked_before_order_read(db, s):
    """AIS-S-25 — the invoice is locked before the linked order is read.
    Rules: resync_items S1, S1a [BUG-2962]; HR-10."""
    E = eo(db, s, "EXP-2026-009")
    eoline(db, s, E, 1)
    V = inv(db, s, order_type="expense_order", order_id=E.id)
    vid = V.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.resync_items(db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.id == vid
    # Then 2
    assert rec.row_lock("account_invoices")
    assert rec.before("account_invoices", "expense_orders")
    # Then 3
    assert "JOIN" not in rec.lock("account_invoices")


# [claude] AIS-S-26
def test_ais_s_26__failing_commit_keeps_lines(db, s):
    """AIS-S-26 — a failing commit keeps the old lines.
    Rules: resync_items S4; TC4."""
    E = eo(db, s, "EXP-2026-009")
    eoline(db, s, E, 1)
    V = inv(db, s, order_type="expense_order", order_id=E.id)
    OL = invl(db, s, V, "999.00", 1)
    commit_point(db)
    snap_ol = snap(db, OL)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.resync_items(db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, OL) == snap_ol
    # Then 4
    assert len(LINES(db, vid)) == 1
    # Then 5
    assert IEV(db, vid) == []


# [claude] AIS-S-28
def test_ais_s_28__eo_lines_empty_values(db, s):
    """AIS-S-28 — expense lines with empty values: None description and prices, whitespace kept, quantity 0.00.
    Rules: resync_items S6, S6b."""
    E = eo(db, s, "EXP-2026-009")
    ea = eoline(
        db,
        s,
        E,
        4,
        description=None,
        quantity=Decimal("0.00"),
        unit=None,
        unit_price=None,
        line_subtotal=None,
    )
    eb = eoline(
        db,
        s,
        E,
        8,
        description="  ",
        unit_price=Decimal("0.00"),
        line_subtotal=Decimal("0.00"),
    )
    V = inv(db, s, order_type="expense_order", order_id=E.id)
    commit_point(db)
    vid = V.id

    result = svc.resync_items(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert [ln.line_number for ln in LINES(db, vid)] == [1, 2]
    # Then 3
    first = LINES(db, vid)[0]
    assert first.description == f"Expense item {ea.id}"
    assert first.source_order_item_id == ea.id
    assert first.quantity == Decimal("1")
    assert first.unit is None
    assert first.unit_price == Decimal("0")
    assert first.line_subtotal == Decimal("0")
    # Then 4
    second = LINES(db, vid)[1]
    assert second.description == "  "
    assert second.source_order_item_id == eb.id
    assert second.quantity == Decimal("2")
    assert second.unit_price == Decimal("0.00")
    assert second.line_subtotal == Decimal("0.00")
    # Then 5
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("0.00")


# [claude] AIS-S-27
def test_ais_s_27__foreign_invoice_404(db, s):
    """AIS-S-27 — another workspace's invoice: 404.
    Rules: resync_items S1, Errors row 1."""
    Z = inv(db, s, ws="9", order_type="purchase_order", order_id=MISSING)
    commit_point(db)
    snap_z = snap(db, Z)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.resync_items(db, invoice_id=Z.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Invoice with ID {Z.id} not found"
    # Then 4
    assert snap(db, Z) == snap_z


# [claude] AIS-S-29
def test_ais_s_29__resync_commits_once(db, s):
    """AIS-S-29 — resync commits exactly once and does not roll back.
    Rules: resync_items S4; TC1."""
    E = eo(db, s, "EXP-2026-009")
    eoline(db, s, E, 1)
    V = inv(db, s, order_type="expense_order", order_id=E.id)
    invl(db, s, V, "999.00", 1)
    vid = V.id
    commit_point(db)

    with spies(db) as (cm, rb):
        result = svc.resync_items(
            db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    db.rollback()
    # Then 4
    assert len(LINES(db, vid)) == 1


# --------------------------------------------------------------------------- #
# confirm_invoice
# --------------------------------------------------------------------------- #


# [claude] AIS-K-01
def test_ais_k_01__manual_invoice_confirmed_at_line_sum(db, s):
    """AIS-K-01 — a manual invoice is confirmed at its line sum and committed; nobody notified.
    Rules: confirm_invoice K1, K4; TC1, TC2."""
    V = inv(db, s, invoice_amount=Decimal("1000.00"))
    invl(db, s, V, "150.00", 1)
    invl(db, s, V, "250.00", 2)
    commit_point(db)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == vid
    db.rollback()
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("400.00")
    assert v.payment_status == "unpaid"
    # Then 4
    assert itypes(db, vid) == ["confirmed"]
    # Then 5
    assert notes(db) == []


# [claude] AIS-K-02
def test_ais_k_02__po_invoice_confirmed_followups(db, s):
    """AIS-K-02 — the PO's invoice: confirmed at the line sum, not the PO total; PO follow-ups committed together.
    Rules: confirm_invoice K4, K5, K5a; TC1."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, current_status_id=s.SP1.id)
    poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    vid, oid = V.id, O.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("400.00")
    # Then 3
    o = reread(db, PurchaseOrder, oid)
    assert o.invoice_confirmed is True
    assert o.supplier_confirmed is True
    assert o.details_confirmed is True
    assert o.items_confirmed is True
    # Then 4
    assert reread(db, PurchaseOrder, oid).current_status_id == s.SR1.id
    # Then 5
    assert types(db, PurchaseOrder, oid) == [
        "invoice_created",
        "invoice_confirmed",
        "status_updated",
        "invoice_confirmed",
    ]
    # Then 6
    last = EV(db, PurchaseOrder, oid)[-1]
    assert last.description == f"Invoice #{vid} confirmed — order locked"
    assert last.performed_by == s.U2.id
    # Then 7
    assert EV(db, PurchaseOrder, oid)[-1].metadata_json == {"invoice_id": vid}


# [claude] AIS-K-03
def test_ais_k_03__po_approvers_and_creator_notified(db, s):
    """AIS-K-03 — the PO's invoice: approvers and creator are notified once each, inactive members skipped.
    Rules: confirm_invoice K6."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4, approved=True)
    poappr(db, s, O, s.U5, approved=True)
    commit_point(db)
    vid, oid = V.id, O.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert recips(db) == sorted([s.U1.id, s.U4.id])
    # Then 3
    for n in notes(db):
        assert n.notification_type == "invoice_action"
        assert n.entity_type == "purchase_order"
        assert n.entity_id == oid
        assert n.source_type == "invoice"
        assert n.source_id == vid
        assert n.actor_user_id == s.U2.id
    # Then 4
    for n in notes(db):
        assert n.preview == f"confirmed|Invoice confirmed on PO-{oid} — order locked"


# [claude] AIS-K-04
def test_ais_k_04__po_items_not_confirmed_400(db, s):
    """AIS-K-04 — PO items not confirmed: 400, nothing written.
    Rules: confirm_invoice K2, Errors row 1; TC3."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", of=V, supplier_confirmed=True, details_confirmed=True)
    poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snap_v, snap_o = snap(db, V), snap(db, O)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SECTIONS
    # Then 4
    assert session_clean(db)
    # Then 5
    assert snap(db, V) == snap_v
    # Then 6
    assert snap(db, O) == snap_o
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-K-05
def test_ais_k_05__section_check_before_status(db, s):
    """AIS-K-05 — the section check comes before the invoice's own status.
    Rules: confirm_invoice K2 (order)."""
    V = inv(db, s, confirmed=True)
    invl(db, s, V, "400.00", 1)
    po(db, s, "1", of=V, details_confirmed=True, items_confirmed=True)
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SECTIONS
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-K-06
def test_ais_k_06__approver_not_approved_400(db, s):
    """AIS-K-06 — one approver not approved: 400 with the counts, nothing written.
    Rules: confirm_invoice K3, Errors row 2."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4)
    before = commit_point(db)
    snap_v, snap_o = snap(db, V), snap(db, O)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Requires 1 approval(s); 0 so far"
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, O) == snap_o
    # Then 6
    assert counts(db) == before


# [claude] AIS-K-07
def test_ais_k_07__threshold_2_one_approval_400(db, s):
    """AIS-K-07 — a threshold of 2 with one approval: 400 "Requires 2 … 1 so far".
    Rules: confirm_invoice K3."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, required_approvals=2)
    poappr(db, s, O, s.U4, approved=True)
    poappr(db, s, O, s.U5)
    poappr(db, s, O, s.U1)
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Requires 2 approval(s); 1 so far"
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-K-08
def test_ais_k_08__threshold_2_met(db, s):
    """AIS-K-08 — a threshold of 2 with two approvals is met.
    Rules: confirm_invoice K3."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, required_approvals=2)
    poappr(db, s, O, s.U4, approved=True)
    poappr(db, s, O, s.U5, approved=True)
    poappr(db, s, O, s.U1)
    commit_point(db)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"


# [claude] AIS-K-09
@xfail(1202)
def test_ais_k_09__no_approvers_one_required(db, s):
    """AIS-K-09 — no approvers and no threshold: 1 approval required.
    Rules: confirm_invoice K3 [BUG-1202]."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    po(db, s, "1", ready=True, of=V)
    before = commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Requires 1 approval(s); 0 so far"
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert counts(db) == before


# [claude] AIS-K-10
def test_ais_k_10__sections_text_wins(db, s):
    """AIS-K-10 — sections and approvals both missing: the section text wins.
    Rules: confirm_invoice K2, K3 (order)."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", of=V, supplier_confirmed=True, items_confirmed=True)
    poappr(db, s, O, s.U4)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SECTIONS


# [claude] AIS-K-11
def test_ais_k_11__already_confirmed_po_unchanged(db, s):
    """AIS-K-11 — PO checks pass but the invoice is already confirmed: manager 400, PO unchanged.
    Rules: confirm_invoice K7, K1; TC3."""
    V = inv(db, s, confirmed=True)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snap_o = snap(db, O)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Invoice is already confirmed"
    # Then 4
    assert session_clean(db)
    # Then 5
    assert snap(db, O) == snap_o
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-K-12
def test_ais_k_12__receiving_stage_missing_422(db, s):
    """AIS-K-12 — the Receiving stage row is missing: 422, the confirm is undone.
    Rules: confirm_invoice K5, K5a, Errors row 6; TC3."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, current_status_id=s.SP1.id)
    poappr(db, s, O, s.U4, approved=True)
    db.delete(s.SR1)
    db.flush()
    before = commit_point(db)
    snap_o = snap(db, O)
    vid = V.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert (
        exc.value.detail
        == "Purchase order stage status 'Receiving' not found for this workspace"
    )
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert snap(db, O) == snap_o
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-K-36
def test_ais_k_36__complete_stays_complete(db, s):
    """AIS-K-36 — a PO already at Complete stays Complete.
    Rules: confirm_invoice K5a."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, current_status_id=s.SC1.id)
    poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    vid, oid = V.id, O.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    o = reread(db, PurchaseOrder, oid)
    assert o.current_status_id == s.SC1.id
    assert o.invoice_confirmed is True
    # Then 3
    assert "status_updated" not in types(db, PurchaseOrder, oid)
    # Then 4
    assert types(db, PurchaseOrder, oid)[-1] == "invoice_confirmed"


# [claude] AIS-K-37
def test_ais_k_37__no_draft_row_backfilled(db, s):
    """AIS-K-37 — no Draft stage row: the stage rows are back-filled and the confirm goes ahead.
    Rules: confirm_invoice K5a."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V, current_status_id=s.SP1.id)
    poappr(db, s, O, s.U4, approved=True)
    db.delete(s.SD1)
    db.flush()
    commit_point(db)
    vid, oid, w1_id = V.id, O.id, s.W1.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=w1_id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    assert (
        count_where(db, Status, Status.workspace_id == w1_id, Status.name == "Draft")
        >= 1
    )
    # Then 4
    o = reread(db, PurchaseOrder, oid)
    assert db.get(Status, o.current_status_id).name == "Receiving"


# [claude] AIS-K-13
def test_ais_k_13__failing_notification_undoes_confirm(db, s):
    """AIS-K-13 — a failing notification undoes the whole confirm.
    Rules: confirm_invoice K6; TC3."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snap_o = snap(db, O)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id
    _, x_id = mk_x(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_notify():
            svc.confirm_invoice(db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 3
    assert snap(db, O) == snap_o
    # Then 4
    assert counts(db) == before
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


# [claude] AIS-K-14
def test_ais_k_14__failing_commit_saves_nothing(db, s):
    """AIS-K-14 — a failing commit saves neither the invoice nor the PO follow-ups.
    Rules: confirm_invoice K5; TC4."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snap_o = snap(db, O)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.confirm_invoice(db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 4
    assert snap(db, O) == snap_o
    # Then 5
    assert counts(db) == before


# [claude] AIS-K-15
@xfail(2962)
def test_ais_k_15__po_locked_before_approvals(db, s):
    """AIS-K-15 — the PO is locked before its approvals are read.
    Rules: confirm_invoice K3a, K3b [BUG-2962]; HR-10."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    O = po(db, s, "1", ready=True, of=V)
    poappr(db, s, O, s.U4, approved=True)
    vid = V.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.confirm_invoice(
            db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert rec.row_lock("purchase_orders")
    assert rec.before("purchase_orders", "purchase_order_approvers")
    # Then 3
    assert "JOIN" not in rec.lock("purchase_orders")
    # Then 4
    assert rec.lock("account_invoices") is None or rec.lock_before_lock(
        "purchase_orders", "account_invoices"
    )


# [claude] AIS-K-16
def test_ais_k_16__w0_po_never_the_pos_invoice(db, s):
    """AIS-K-16 — a W0 PO pointing at the invoice is never "the PO's invoice".
    Rules: confirm_invoice K1; Overview "The PO's invoice"; HR-16."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    Z0 = po(db, s, "0", ws="0", invoice_id=V.id)
    commit_point(db)
    snap_z = snap(db, Z0)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    assert snap(db, Z0) == snap_z
    # Then 4
    assert types(db, PurchaseOrder, Z0.id) == []
    # Then 5
    assert notes(db) == []


# [claude] AIS-K-17
def test_ais_k_17__w2_po_never_the_pos_invoice(db, s):
    """AIS-K-17 — a W2 PO pointing at the invoice is never "the PO's invoice".
    Rules: confirm_invoice K1; HR-16."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    Z2 = po(db, s, "9", ws="9", invoice_id=V.id)
    commit_point(db)
    snap_z = snap(db, Z2)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    assert snap(db, Z2) == snap_z
    # Then 4
    assert types(db, PurchaseOrder, Z2.id) == []


# [claude] AIS-K-18
@xfail(2969)
def test_ais_k_18__eo_invoice_refused(db, s):
    """AIS-K-18 — an expense order's invoice is refused on the invoice page; nobody notified.
    Rules: confirm_invoice K10, K8, Errors row 4 [BUG-2969]."""
    V = inv(db, s)
    invl(db, s, V, "45000.00", 1)
    E = eo(db, s, "EXP-2026-009", of=V)
    eoappr(db, s, E, s.U4)
    commit_point(db)
    snap_e = snap(db, E)
    vid = V.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when expense order EXP-2026-009 is completed."
    )
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert IEV(db, vid) == []
    # Then 6
    assert notes(db) == []
    # Then 7
    assert snap(db, E) == snap_e
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-K-19
@xfail(2969)
def test_ais_k_19__wo_invoice_refused(db, s):
    """AIS-K-19 — a work order's invoice is refused on the invoice page.
    Rules: confirm_invoice K10, Errors row 4 [BUG-2969]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "5000.00", 1)
    wo(db, s, "WO-2026-031", of=V)
    before = commit_point(db)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when work order WO-2026-031 is completed."
    )
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert counts(db) == before


# [claude] AIS-K-20
@xfail(2969)
def test_ais_k_20__voided_eo_invoice_refused(db, s):
    """AIS-K-20 — a voided expense order's invoice is refused too.
    Rules: confirm_invoice K10 [BUG-2969]."""
    V = inv(db, s)
    invl(db, s, V, "45000.00", 1)
    eo(db, s, "EXP-2026-009", of=V, voided=True)
    commit_point(db)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when expense order EXP-2026-009 is completed."
    )
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"


# [claude] AIS-K-21
@xfail(2969)
def test_ais_k_21__deleted_wo_invoice_refused(db, s):
    """AIS-K-21 — a soft-deleted work order's invoice is refused too.
    Rules: confirm_invoice K10 [BUG-2969]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "5000.00", 1)
    wo(db, s, "WO-2026-031", of=V, is_deleted=True)
    commit_point(db)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when work order WO-2026-031 is completed."
    )
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"


# [claude] AIS-K-22
@xfail(2969)
def test_ais_k_22__eo_named_over_wo(db, s):
    """AIS-K-22 — both an expense and a work order point at it: the expense order is named.
    Rules: confirm_invoice K10 [BUG-2969]."""
    V = inv(db, s)
    invl(db, s, V, "45000.00", 1)
    wo(db, s, "WO-2026-031", of=V)
    eo(db, s, "EXP-2026-009", of=V)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when expense order EXP-2026-009 is completed."
    )


# [claude] AIS-K-23
@xfail(2969)
def test_ais_k_23__eo_refusal_before_status(db, s):
    """AIS-K-23 — the expense-order refusal comes before the invoice's own status.
    Rules: confirm_invoice K10 (order) [BUG-2969]."""
    V = inv(db, s, confirmed=True)
    invl(db, s, V, "400.00", 1)
    eo(db, s, "EXP-2026-009", of=V)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert (
        exc.value.detail
        == "This invoice is finalized when expense order EXP-2026-009 is completed."
    )


# [claude] AIS-K-24
def test_ais_k_24__w0_eo_not_found_confirms(db, s):
    """AIS-K-24 — a W0 expense order pointing at the invoice is not found: it confirms, nobody notified.
    Rules: confirm_invoice K10, K8; HR-16."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    E0 = eo(db, s, "EXP-2026-800", ws="0", invoice_id=V.id)
    commit_point(db)
    snap_e = snap(db, E0)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    assert notes(db) == []
    # Then 4
    assert snap(db, E0) == snap_e


# [claude] AIS-K-25
def test_ais_k_25__w2_eo_not_found_confirms(db, s):
    """AIS-K-25 — a W2 expense order pointing at the invoice is not found: it confirms, nobody notified.
    Rules: confirm_invoice K10, K8; HR-16."""
    V = inv(db, s)
    invl(db, s, V, "400.00", 1)
    E9 = eo(db, s, "EXP-2026-900", ws="9", invoice_id=V.id)
    commit_point(db)
    snap_e = snap(db, E9)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    assert notes(db) == []
    # Then 4
    assert snap(db, E9) == snap_e


# [claude] AIS-K-30
@xfail(2965)
def test_ais_k_30__so_sections_not_confirmed_400(db, s):
    """AIS-K-30 — a sales order's sections not confirmed: 400, nothing written.
    Rules: confirm_invoice K9, Errors row 3 [BUG-2965]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", of=V, order_info_confirmed=True)
    soappr(db, s, S, s.U4, approved=True)
    before = commit_point(db)
    snap_s = snap(db, S)
    vid = V.id
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Confirm order info and items before finalizing"
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert snap(db, S) == snap_s
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-K-31
@xfail(2965)
def test_ais_k_31__so_approvals_not_met_400(db, s):
    """AIS-K-31 — a sales order's approvals not met: 400 with the counts.
    Rules: confirm_invoice K9 [BUG-2965]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", so_ready=True, of=V)
    soappr(db, s, S, s.U4, approved=True)
    soappr(db, s, S, s.U5)
    commit_point(db)
    snap_s = snap(db, S)
    vid = V.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Requires 2 approval(s); 1 so far"
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert snap(db, S) == snap_s


# [claude] AIS-K-32
@xfail(2965)
def test_ais_k_32__so_checks_before_status(db, s):
    """AIS-K-32 — the sales checks come before the invoice's own status.
    Rules: confirm_invoice K9 (order) [BUG-2965]."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    invl(db, s, V, "400.00", 1)
    so(db, s, "1", of=V)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.confirm_invoice(db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Confirm order info and items before finalizing"


# [claude] AIS-K-33
@xfail(2965)
def test_ais_k_33__so_marked_finalized_and_logged(db, s):
    """AIS-K-33 — a ready, approved sales order: the order is marked finalized and logs it.
    Rules: confirm_invoice K9 [BUG-2965]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", so_ready=True, of=V)
    soappr(db, s, S, s.U4, approved=True)
    commit_point(db)
    vid, sid = V.id, S.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 3
    row = reread(db, SalesOrder, sid)
    assert row.invoice_confirmed is True
    assert row.order_info_confirmed is True
    assert row.items_confirmed is True
    # Then 4
    last = EV(db, SalesOrder, sid)[-1]
    assert last.event_type == "invoice_confirmed"
    assert last.performed_by == s.U2.id
    # Then 5
    assert (
        EV(db, SalesOrder, sid)[-1].description
        == f"Invoice #{vid} confirmed — order locked"
    )
    # Then 6
    assert EV(db, SalesOrder, sid)[-1].metadata_json == {"invoice_id": vid}
    # Then 7
    assert types(db, SalesOrder, sid) == ["invoice_confirmed"]


# [claude] AIS-K-34
def test_ais_k_34__ready_so_invoice_confirmed_at_line_sum(db, s):
    """AIS-K-34 — a ready, approved sales order's invoice is confirmed at the line sum (today and after the fix).
    Rules: confirm_invoice K1, K9."""
    V = inv(db, s, invoice_type="receivable", invoice_amount=Decimal("1.00"))
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", so_ready=True, of=V)
    soappr(db, s, S, s.U4, approved=True)
    commit_point(db)
    vid = V.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("20000.00")
    # Then 3
    assert itypes(db, vid) == ["confirmed"]


# [claude] AIS-K-35
@xfail(2965, 1205)
def test_ais_k_35__so_approvers_and_creator_notified(db, s):
    """AIS-K-35 — a ready, approved sales order: its approvers and creator are notified.
    Rules: confirm_invoice K9 [BUG-2965]; notify_invoice_action R7a [BUG-1205]."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", so_ready=True, of=V)
    soappr(db, s, S, s.U4, approved=True)
    commit_point(db)
    vid, sid = V.id, S.id

    result = svc.confirm_invoice(
        db, invoice_id=vid, workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert recips(db) == sorted([s.U1.id, s.U4.id])
    # Then 3
    for n in notes(db):
        assert n.entity_type == "sales_order"
        assert n.entity_id == sid
        assert n.source_id == vid
        assert n.actor_user_id == s.U2.id
    # Then 4
    for n in notes(db):
        assert n.preview == f"confirmed|Invoice confirmed on SO-{sid} — order locked"


# [claude] AIS-K-38
@xfail(2962)
def test_ais_k_38__so_locked_before_checks(db, s):
    """AIS-K-38 — the sales order is locked before its checks.
    Rules: confirm_invoice K9b [BUG-2962]; HR-10."""
    V = inv(db, s, invoice_type="receivable")
    invl(db, s, V, "20000.00", 1)
    S = so(db, s, "1", so_ready=True, of=V)
    soappr(db, s, S, s.U4, approved=True)
    soappr(db, s, S, s.U5, approved=True)
    vid = V.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.confirm_invoice(
            db, invoice_id=vid, workspace_id=w1_id, user_id=u2_id
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert rec.row_lock("sales_orders")
    assert rec.before("sales_orders", "sales_order_approvers")
    # Then 3
    assert "JOIN" not in rec.lock("sales_orders")
    # Then 4
    assert rec.reads("sales_order_approvers")


# --------------------------------------------------------------------------- #
# void_invoice
# --------------------------------------------------------------------------- #

VOID_CHANGES = [
    {
        "field": "void_note",
        "label": "Void reason",
        "from_value": None,
        "to_value": "Wrong amount",
    }
]


# [claude] AIS-X-01
def test_ais_x_01__po_invoice_voided_with_payments(db, s):
    """AIS-X-01 — the PO's invoice is voided with its payments and committed.
    Rules: void_invoice X2, X6; TC1, TC2."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    P = pay(db, s, V, "100.00")
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    vid, pid = V.id, P.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == vid
    db.rollback()
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "voided"
    assert v.void_note == "Wrong amount"
    assert v.paid_amount == Decimal("0.00")
    # Then 4
    p = reread(db, InvoicePayment, pid)
    assert p.is_voided is True
    assert p.voided_by == s.U2.id


# [claude] AIS-X-02
def test_ais_x_02__po_released(db, s):
    """AIS-X-02 — the PO's invoice: approvals reset, PO unlinked, supplier and items unconfirmed, stage re-derived.
    Rules: void_invoice X3, X4, X5."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V, paid=True)
    poline(db, s, O, 1)
    A = poappr(db, s, O, s.U4, approved=True)
    commit_point(db)
    vid, oid, aid = V.id, O.id, A.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    a = reread(db, PurchaseOrderApprover, aid)
    assert a.approved is False
    assert a.approved_at is None
    # Then 3
    o = reread(db, PurchaseOrder, oid)
    assert o.invoice_id is None
    assert o.invoice_confirmed is False
    assert o.paid is False
    # Then 4
    o = reread(db, PurchaseOrder, oid)
    assert o.supplier_confirmed is False
    assert o.items_confirmed is False
    assert o.details_confirmed is True
    # Then 5
    assert reread(db, PurchaseOrder, oid).current_status_id == s.SP1.id
    # Then 6
    assert types(db, PurchaseOrder, oid) == [
        "approvals_reset",
        "invoice_voided",
        "supplier_unconfirmed",
        "items_unconfirmed",
        "status_updated",
    ]
    # Then 7
    assert EV(db, PurchaseOrder, oid)[0].description == (
        "Cleared approvals after invoice voided (1 approval(s) cleared)"
    )


# [claude] AIS-X-03
def test_ais_x_03__po_event_carries_reason(db, s):
    """AIS-X-03 — the PO's "invoice voided" event carries the void reason.
    Rules: void_invoice X4."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    commit_point(db)
    vid, oid = V.id, O.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    # Then 2
    assert types(db, PurchaseOrder, oid)[0] == "invoice_voided"
    # Then 3
    ev = EV(db, PurchaseOrder, oid)
    assert ev[0].description == f"Invoice #{vid} voided"
    assert ev[0].performed_by == s.U2.id
    # Then 4
    assert EV(db, PurchaseOrder, oid)[0].metadata_json == {
        "invoice_id": vid,
        "changes": VOID_CHANGES,
    }


# [claude] AIS-X-04
def test_ais_x_04__goods_received_400(db, s):
    """AIS-X-04 — goods received on a PO line: 400, nothing written.
    Rules: void_invoice X1, Errors row 1; TC3."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    P = pay(db, s, V, "100.00")
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    poline(db, s, O, 2, quantity_received=Decimal("0.01"))
    A = poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snaps = [snap(db, r) for r in (V, P, O, A)]
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == RECVD
    # Then 4
    assert session_clean(db)
    # Then 5
    assert snap(db, V) == snaps[0]
    # Then 6
    assert snap(db, P) == snaps[1]
    # Then 7
    assert snap(db, O) == snaps[2]
    # Then 8
    assert snap(db, A) == snaps[3]
    # Then 9
    assert counts(db) == before
    db.rollback()
    # Then 10
    assert x_gone(db, x_id)


# [claude] AIS-X-05
def test_ais_x_05__received_check_before_manager(db, s):
    """AIS-X-05 — the received-goods check runs before the manager's checks.
    Rules: void_invoice X1 (order)."""
    V = inv(db, s)
    O = po(db, s, "1", ready=True, of=V)
    poline(db, s, O, 1, quantity_received=Decimal("5.00"))
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == RECVD
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-X-06
def test_ais_x_06__foreign_received_line_does_not_block(db, s):
    """AIS-X-06 — a received line of another workspace on the PO does not block.
    Rules: void_invoice X1 (lines of the workspace); HR-16."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    poline(db, s, O, 2, workspace_id=s.W2.id, quantity_received=Decimal("5.00"))
    commit_point(db)
    vid = V.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"


# [claude] AIS-X-07
def test_ais_x_07__no_approval_no_reset_event(db, s):
    """AIS-X-07 — no approver approved: no approvals_reset event.
    Rules: void_invoice X3."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    A = poappr(db, s, O, s.U4)
    commit_point(db)
    snap_a = snap(db, A)
    vid, oid = V.id, O.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert "approvals_reset" not in types(db, PurchaseOrder, oid)
    # Then 3
    assert types(db, PurchaseOrder, oid)[0] == "invoice_voided"
    # Then 4
    assert snap(db, A) == snap_a


# [claude] AIS-X-08
@xfail(2962)
def test_ais_x_08__po_locked_before_lines(db, s):
    """AIS-X-08 — the PO is locked before its lines are read.
    Rules: void_invoice X1, X1c [BUG-2962]; K3b; HR-10."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    vid = V.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.void_invoice(
            db,
            invoice_id=vid,
            workspace_id=w1_id,
            user_id=u2_id,
            void_note="Wrong amount",
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert rec.row_lock("purchase_orders")
    assert rec.before("purchase_orders", "purchase_order_items")
    # Then 3
    assert rec.line_lock("purchase_order_items")
    # Then 4
    assert rec.lock("account_invoices") is None or rec.lock_before_lock(
        "purchase_order_items", "account_invoices"
    )


# [claude] AIS-X-09
def test_ais_x_09__missing_stage_row_422(db, s):
    """AIS-X-09 — a missing stage row: 422, none of the void is saved.
    Rules: void_invoice X6; TC3."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    P = pay(db, s, V, "100.00")
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    A = poappr(db, s, O, s.U4, approved=True)
    O.current_status_id = s.SD1.id
    # card steps 6 and 7 (cases rev 3): two flushes
    db.flush()
    db.delete(s.SP1)
    db.delete(s.SR1)
    db.delete(s.SC1)
    db.flush()
    before = commit_point(db)
    snaps = [snap(db, r) for r in (V, P, O, A)]
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert snap(db, V) == snaps[0]
    # Then 4
    assert snap(db, P) == snaps[1]
    # Then 5
    assert snap(db, O) == snaps[2]
    # Then 6
    assert snap(db, A) == snaps[3]
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-X-10
def test_ais_x_10__failing_commit_saves_nothing(db, s):
    """AIS-X-10 — a failing commit saves none of the void.
    Rules: void_invoice X6; TC4."""
    V = inv(db, s, confirmed=True)
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    A = poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snap_o, snap_a = snap(db, O), snap(db, A)
    vid, w1_id, u2_id = V.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.void_invoice(
                db,
                invoice_id=vid,
                workspace_id=w1_id,
                user_id=u2_id,
                void_note="Wrong amount",
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, AccountInvoice, vid).invoice_status == "confirmed"
    # Then 4
    assert snap(db, O) == snap_o
    # Then 5
    assert snap(db, A) == snap_a
    # Then 6
    assert counts(db) == before


# [claude] AIS-X-11
def test_ais_x_11__manual_invoice_voided(db, s):
    """AIS-X-11 — a manual invoice: only the invoice and its payments are voided.
    Rules: void_invoice X7, X2."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    P = pay(db, s, V, "100.00")
    commit_point(db)
    vid, pid = V.id, P.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Entered twice",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "voided"
    assert v.void_note == "Entered twice"
    # Then 3
    assert reread(db, InvoicePayment, pid).is_voided is True
    # Then 4
    assert order_event_counts(db) == (0, 0, 0, 0)


# [claude] AIS-X-12
def test_ais_x_12__draft_cannot_be_voided(db, s):
    """AIS-X-12 — a draft invoice: the manager's 400 passes unchanged, nothing saved.
    Rules: void_invoice X2; TC3."""
    V = inv(db, s)
    P = pay(db, s, V, "100.00")
    before = commit_point(db)
    snap_v, snap_p = snap(db, V), snap(db, P)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db, invoice_id=V.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="x"
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Draft invoices cannot be voided — delete them instead"
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, P) == snap_p
    # Then 6
    assert counts(db) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


# [claude] AIS-X-13
@xfail(2731)
def test_ais_x_13__completed_so_invoice_frozen(db, s):
    """AIS-X-13 — a completed sales order's invoice is frozen; payments kept.
    Rules: void_invoice X2 [BUG-2731]."""
    V = inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        paid_amount=Decimal("100.00"),
        payment_status="partial",
    )
    P = pay(db, s, V, "100.00")
    so(db, s, "1", finalized_by=V, order_completed=True)
    commit_point(db)
    snap_v, snap_p = snap(db, V), snap(db, P)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == LOCK("sales order")
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, P) == snap_p


# [claude] AIS-X-14
@xfail(2788)
def test_ais_x_14__credit_note_return_voided(db, s):
    """AIS-X-14 — a credit note of a pending return: the return is voided with it.
    Rules: void_invoice X2 [BUG-2788]."""
    O = po(db, s, "1", ready=True)
    CN = inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        order_type="purchase_order",
        order_id=O.id,
    )
    R = po_return(db, s, O, CN)
    commit_point(db)
    cnid, rid = CN.id, R.id

    result = svc.void_invoice(
        db,
        invoice_id=cnid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Return cancelled",
    )

    # Then 1
    assert result.id == cnid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, cnid).invoice_status == "voided"
    # Then 3
    assert reread(db, PurchaseOrderReturn, rid).status == "voided"


# [claude] AIS-X-15
@xfail(2967)
def test_ais_x_15__so_delivered_400(db, s):
    """AIS-X-15 — goods delivered on a sales order: 400, payments kept.
    Rules: void_invoice X1a, Errors row 2 [BUG-2967]."""
    V = inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        invoice_amount=Decimal("20000.00"),
        paid_amount=Decimal("8000.00"),
        payment_status="partial",
    )
    P = pay(db, s, V, "8000.00")
    S = so(db, s, "1", finalized_by=V)
    soline(db, s, S, quantity_delivered=Decimal("4.00"))
    before = commit_point(db)
    snaps = [snap(db, r) for r in (V, P, S)]
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DELIVERED
    # Then 4
    assert snap(db, V) == snaps[0]
    # Then 5
    assert snap(db, P) == snaps[1]
    # Then 6
    assert snap(db, S) == snaps[2]
    # Then 7
    assert counts(db) == before
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


# [claude] AIS-X-16
def test_ais_x_16__nothing_delivered_void_goes_ahead(db, s):
    """AIS-X-16 — nothing delivered on the sales order: the void goes ahead.
    Rules: void_invoice X1a (other side), X2."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    S = so(db, s, "1", finalized_by=V)
    soline(db, s, S)
    commit_point(db)
    vid = V.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"


# [claude] AIS-X-17
@xfail(2966)
def test_ais_x_17__so_released(db, s):
    """AIS-X-17 — a sales order is released after its invoice is voided.
    Rules: void_invoice X8 [BUG-2966]."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    S = so(db, s, "1", finalized_by=V, paid=True)
    soline(db, s, S)
    A = soappr(db, s, S, s.U4, approved=True)
    commit_point(db)
    vid, sid, aid = V.id, S.id, A.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    row = reread(db, SalesOrder, sid)
    assert row.invoice_id is None
    assert row.invoice_confirmed is False
    assert row.is_invoiced is False
    assert row.paid is False
    # Then 3
    row = reread(db, SalesOrder, sid)
    assert row.order_info_confirmed is False
    assert row.items_confirmed is False
    # Then 4
    a = reread(db, SalesOrderApprover, aid)
    assert a.approved is False
    assert a.approved_at is None
    # Then 5
    assert "invoice_voided" in types(db, SalesOrder, sid)
    # Then 6
    voided = next(
        e for e in EV(db, SalesOrder, sid) if e.event_type == "invoice_voided"
    )
    assert voided.description == f"Invoice #{vid} voided"
    assert voided.performed_by == s.U2.id
    # Then 7
    voided = next(
        e for e in EV(db, SalesOrder, sid) if e.event_type == "invoice_voided"
    )
    assert voided.metadata_json == {"invoice_id": vid, "changes": VOID_CHANGES}


# [claude] AIS-X-18
@xfail(2966)
def test_ais_x_18__eo_released_approvals_kept(db, s):
    """AIS-X-18 — an expense order is released after its invoice is voided; approvals kept.
    Rules: void_invoice X8 [BUG-2966]."""
    V = inv(db, s, confirmed=True)
    E = eo(db, s, "EXP-2026-007", of=V)
    A = eoappr(db, s, E, s.U4, approved=True)
    commit_point(db)
    snap_a = snap(db, A)
    vid, eid = V.id, E.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Fix amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, ExpenseOrder, eid).invoice_id is None
    # Then 3
    assert types(db, ExpenseOrder, eid) == ["invoice_voided"]
    # Then 4
    ev = EV(db, ExpenseOrder, eid)
    assert ev[0].description == f"Invoice #{vid} voided"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert snap(db, A) == snap_a


# [claude] AIS-X-19
def test_ais_x_19__eo_invoice_voided_approvals_stay(db, s):
    """AIS-X-19 — an expense order's invoice is voided and its approvals stay (today and after the fix).
    Rules: void_invoice X8 (approvals unchanged), X2."""
    V = inv(db, s, confirmed=True)
    E = eo(db, s, "EXP-2026-007", of=V)
    A = eoappr(db, s, E, s.U4, approved=True)
    commit_point(db)
    snap_a = snap(db, A)
    vid = V.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Fix amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"
    # Then 3
    assert snap(db, A) == snap_a


# [claude] AIS-X-20
@xfail(2966)
def test_ais_x_20__wo_released(db, s):
    """AIS-X-20 — a work order is released after its invoice is voided.
    Rules: void_invoice X8 [BUG-2966]."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    WO = wo(db, s, "WO-2026-031", of=V)
    commit_point(db)
    vid, woid = V.id, WO.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Fix amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, woid).invoice_id is None
    # Then 3
    assert types(db, WorkOrder, woid) == ["invoice_voided"]
    # Then 4
    ev = EV(db, WorkOrder, woid)
    assert ev[0].description == f"Invoice #{vid} voided"
    assert ev[0].performed_by == s.U2.id


# [claude] AIS-X-21
def test_ais_x_21__foreign_so_untouched(db, s):
    """AIS-X-21 — another workspace's sales order pointing at the invoice is not touched.
    Rules: void_invoice X8 (orders of the workspace only); HR-16."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    S9 = so(db, s, "9", ws="9", finalized_by=V, current_status_id=s.SD9.id)
    commit_point(db)
    snap_s = snap(db, S9)
    vid, sid = V.id, S9.id

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"
    # Then 3
    assert snap(db, S9) == snap_s
    # Then 4
    assert types(db, SalesOrder, sid) == []


# [claude] AIS-X-22
@xfail(626)
@pytest.mark.usefixtures("s")  # Given: standing rows only
def test_ais_x_22__blank_void_note_rejected():
    """AIS-X-22 — a blank void note is rejected by the schema.
    Rules: void_invoice Errors row 3 [BUG-626]."""
    # Then 1
    with pytest.raises(ValidationError):
        VoidInvoiceRequest(void_note="   ")


# [claude] AIS-X-23
@xfail(2967)
def test_ais_x_23__service_line_fulfilled_blocks(db, s):
    """AIS-X-23 — a service line fulfilled without any delivery also blocks the void.
    Rules: void_invoice X1a, X1b [BUG-2967]."""
    V = inv(
        db,
        s,
        confirmed=True,
        invoice_type="receivable",
        paid_amount=Decimal("100.00"),
        payment_status="partial",
    )
    P = pay(db, s, V, "100.00")
    S = so(db, s, "1", finalized_by=V)
    soline(
        db,
        s,
        S,
        requires_delivery=False,
        quantity_ordered=Decimal("1.00"),
        quantity_delivered=Decimal("1.00"),
        unit_price=Decimal("400.00"),
        line_total=Decimal("400.00"),
    )
    commit_point(db)
    snap_v, snap_p = snap(db, V), snap(db, P)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DELIVERED
    # Then 4
    assert snap(db, V) == snap_v
    # Then 5
    assert snap(db, P) == snap_p


# [claude] AIS-X-24
@xfail(2967)
def test_ais_x_24__delivered_then_returned_blocks(db, s):
    """AIS-X-24 — a line delivered and then fully returned still blocks the void.
    Rules: void_invoice X1a, X1b [BUG-2967]."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    S = so(db, s, "1", finalized_by=V)
    soline(
        db, s, S, quantity_delivered=Decimal("4.00"), quantity_returned=Decimal("4.00")
    )
    commit_point(db)
    snap_v = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_invoice(
            db,
            invoice_id=V.id,
            workspace_id=s.W1.id,
            user_id=s.U2.id,
            void_note="Wrong amount",
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == DELIVERED
    # Then 4
    assert snap(db, V) == snap_v


# [claude] AIS-X-25
@xfail(2962)
def test_ais_x_25__so_row_then_lines_locked(db, s):
    """AIS-X-25 — the sales order row, then its lines, are locked before the delivered check.
    Rules: void_invoice X1a, X1c [BUG-2962]; K9b; HR-10."""
    V = inv(db, s, confirmed=True, invoice_type="receivable")
    S = so(db, s, "1", finalized_by=V)
    soline(db, s, S)
    vid = V.id
    commit_point(db)
    w1_id, u2_id = s.W1.id, s.U2.id
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.void_invoice(
            db,
            invoice_id=vid,
            workspace_id=w1_id,
            user_id=u2_id,
            void_note="Wrong amount",
        )

    # Then 1
    assert result.id == vid
    # Then 2
    assert rec.row_lock("sales_orders")
    assert rec.before("sales_orders", "sales_order_items")
    # Then 3
    assert rec.line_lock("sales_order_items")
    # Then 4
    assert rec.lock("account_invoices") is None or rec.lock_before_lock(
        "sales_order_items", "account_invoices"
    )


# [claude] AIS-X-26
def test_ais_x_26__non_http_error_after_writes_rolled_back(db, s):
    """AIS-X-26 — a non-HTTP error after the first writes is rolled back and passes unchanged.
    Rules: void_invoice X6; TC3."""
    V = inv(
        db, s, confirmed=True, paid_amount=Decimal("100.00"), payment_status="partial"
    )
    P = pay(db, s, V, "100.00")
    O = po(db, s, "1", locked_by=V)
    poline(db, s, O, 1)
    A = poappr(db, s, O, s.U4, approved=True)
    before = commit_point(db)
    snaps = [snap(db, r) for r in (V, P, O, A)]
    x, x_id = mk_x(db)
    E = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(
                ais_mod.purchase_order_manager,
                "unconfirm_sections_after_invoice_void",
                side_effect=E,
            ),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            svc.void_invoice(
                db,
                invoice_id=V.id,
                workspace_id=s.W1.id,
                user_id=s.U2.id,
                void_note="Wrong amount",
            )
    # Then 1
    assert exc.value is E
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert x not in db
    # Then 4
    assert snap(db, V) == snaps[0]
    # Then 5
    assert snap(db, P) == snaps[1]
    # Then 6
    assert snap(db, O) == snaps[2]
    # Then 7
    assert snap(db, A) == snaps[3]
    # Then 8
    assert counts(db) == before
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


# [claude] AIS-X-27
def test_ais_x_27__w0_po_not_the_pos_invoice(db, s):
    """AIS-X-27 — a W0 PO pointing at the invoice is not "the PO's invoice": its received line does not block, it is not touched.
    Rules: void_invoice X1, X7; Overview "The PO's invoice"; HR-16."""
    V = inv(db, s, confirmed=True)
    Z = po(
        db,
        s,
        "0",
        ws="0",
        ready=True,
        invoice_id=V.id,
        invoice_ever_linked=True,
        invoice_confirmed=True,
    )
    poline(db, s, Z, 1, quantity_received=Decimal("5.00"))
    ZA = poappr(db, s, Z, s.U3, approved=True)
    vid = V.id
    commit_point(db)
    snap_z, snap_za = snap(db, Z), snap(db, ZA)

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"
    # Then 3
    assert snap(db, Z) == snap_z
    # Then 4
    assert snap(db, ZA) == snap_za
    # Then 5
    assert types(db, PurchaseOrder, Z.id) == []


# [claude] AIS-X-28
def test_ais_x_28__w2_po_not_the_pos_invoice(db, s):
    """AIS-X-28 — a W2 PO pointing at the invoice is not "the PO's invoice": its received line does not block, it is not touched.
    Rules: void_invoice X1, X7; Overview "The PO's invoice"; HR-16."""
    V = inv(db, s, confirmed=True)
    Z = po(
        db,
        s,
        "9",
        ws="9",
        ready=True,
        invoice_id=V.id,
        invoice_ever_linked=True,
        invoice_confirmed=True,
    )
    poline(db, s, Z, 1, quantity_received=Decimal("5.00"))
    ZA = poappr(db, s, Z, s.U3, approved=True)
    vid = V.id
    commit_point(db)
    snap_z, snap_za = snap(db, Z), snap(db, ZA)

    result = svc.void_invoice(
        db,
        invoice_id=vid,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        void_note="Wrong amount",
    )

    # Then 1
    assert result.id == vid
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_status == "voided"
    # Then 3
    assert snap(db, Z) == snap_z
    # Then 4
    assert snap(db, ZA) == snap_za
    # Then 5
    assert types(db, PurchaseOrder, Z.id) == []
