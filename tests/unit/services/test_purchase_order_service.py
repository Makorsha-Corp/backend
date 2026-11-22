# ruff: noqa: SIM117, DTZ001, FURB157
# (nested `with` blocks, naive datetimes and `Decimal("1")`-style literals are
# prescribed by the cards' Conventions.)
"""Unit tests for app/services/purchase_order_service.py.

Implements tests/unit/services/purchase_order_service.cases.md (revision 4a,
2026-11-22), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: `utcnow` of the service (autouse fixture
`clock`, NOW naive like the real helper); the commit / rollback / refresh spies
and failing variants (`patch.object(db, ...)`); the SD-10 race simulation and
the forced errors of the `Author: claude` cards. Nothing else is mocked; the
lock cards record the SQL sent with an `after_cursor_execute` listener.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.U2`,
`s.A1`). `# Then N` marks the checks of the card's Then line N.
Names the cards use that do not exist yet (`receive_replacements`,
`PurchaseOrderReturnEvent`, `PurchaseOrderReturnReplacementCreate`,
`quantity_replaced`, `has_open_return`, `warnings`) are written as the cards
show them; their tests are strict xfail.
"""

import logging
import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

import app.models.purchase_order_return as _por_models
from app.managers.invoice_payment_manager import invoice_payment_manager as ipm
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.department import Department
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.item import Item
from app.models.notification import Notification
from app.models.order_workflow import OrderWorkflow
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.status import Status
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate
from app.schemas.po_receive_event import PoReceiveEventCreate
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderItemSyncRequest,
    PurchaseOrderItemSyncUpdate,
    PurchaseOrderItemUpdate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    PurchaseOrderVoidRequest,
)
from app.schemas.purchase_order_return import (
    PurchaseOrderReturnCreate,
    PurchaseOrderReturnItemCreate,
    PurchaseOrderReturnResponse,
    PurchaseOrderReturnVoidRequest,
)
from app.services.purchase_order_service import (
    PurchaseOrderService,
    purchase_order_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> imports and constants
# --------------------------------------------------------------------------- #

svc = purchase_order_service
mgr = svc.manager
aim = svc.account_invoice_manager
assert isinstance(svc, PurchaseOrderService)

# The return event model is new (BUG-3176); read it lazily so the module imports today.
PurchaseOrderReturnEvent = getattr(_por_models, "PurchaseOrderReturnEvent", None)

MISSING = 999999999
T0 = datetime(2026, 9, 1, 8, 0)
T1 = datetime(2026, 9, 2, 9, 0)
T2 = datetime(2026, 9, 3, 10, 0)
NOW = datetime(2026, 9, 27, 12, 0, 0)
TODAY_UTC = date(2026, 9, 27)


def NF(i):
    return f"Purchase order with ID {i} not found"


def RNF(i):
    return f"Return with ID {i} not found"


FINALIZE = "Finalize the invoice before recording receiving"
PAYHIST = "Invoice has payment history — confirm and void it instead"
DRAFTP = "draft|Linked payable invoice is in draft — confirm when details look correct"
FORCE422 = "Confirm supplier, order details, and items before creating a draft invoice"
SUPP422 = "The selected supplier account was not found. Re-select the supplier."
NOSETTLE = "The return's credit note has nothing outstanding — no settlement recorded"
VOIDW = "The return's credit note is voided — no settlement recorded"
NOTFOUND = "The return's credit note could not be found — no settlement recorded"
MANUAL = '"settled_by_replacement" is recorded by the system and cannot be entered by hand'
NODEL = "A settlement by replacement cannot be deleted or edited — void it with a reason instead"


def NOTPART(i, R):
    return f"Line {i} is not part of return {R.return_number}"


def RTOO(t, n, left):
    return f"Cannot receive {t} replacement(s) for line {n} — only {left} still to replace"


_BUGS = {
    639: "A draft that once had (voided) payments cannot be deleted",
    801: "Fractional return quantity is accepted when a return starts, then permanently blocks its completion",
    1195: "Deleted purchase order vanishes without trace",
    2641: "PO list's received progress ignores refunded quantity",
    2734: "Voiding a purchase order voids its confirmed invoice and cancels payments even when the PO is completed / has goods received",
    2754: "Return read before complete / void is not locked",
    2789: "Starting a purchase return reopens a completed order",
    2810: "Replacement goods for a `replace` return on a completed PO can't be received: a completed PO refuses receiving",
    2886: "Lines of a missing purchase order answer an empty list",
    2887: "The PO line edit changes a received quantity without moving stock",
    2888: "Deleting a PO leaves its invoice behind",
    3162: 'Receiving, voiding and "Create invoice" check the PO without a row lock',
    3163: "Return credit-note line subtotals are not rounded half up",
    3164: "PO payment status is read from invoices by id without the workspace",
    3165: "An items sync that changes nothing still stamps `items_updated_at`",
    3166: '"Active orders" for a machine filters work orders by status after taking only the newest 1,000',
    3167: "Draft invoices and return credit notes are dated with the server's local date",
    3168: "A blank void reason is accepted for PO void and return cancel",
    3169: 'A voided PO can get a new draft invoice through "Create invoice"',
    3170: "Voiding a PO clears approvals only when it had an invoice",
    3171: "One receive batch can name the same PO line twice and over-receive it",
    3172: "Receive events with the same time, and each event's lines, come back in no fixed order",
    3173: '"Active orders" lists voided purchase orders',
    3174: "Completing, cancelling or receiving replacements on a PO return does not set `updated_by`",
    3175: "PO create re-raises a refusal without rolling back",
    3176: "Receiving a `replace` return's replacements does not settle its credit note",
    3177: '"Receive goods" never sets the invoice\'s `receiving_started`',
    3178: "The PO list repairs the stage of only the first stale order on a page",
    3179: "An items sync commits the lines and the draft-invoice step in two separate transactions",
    3180: 'Receive texts store a blank value as `""`, and the log repeats the untrimmed text',
    3181: "Receiving replacements can take a PO line above ordered − refunded",
    3182: "A pending PO return whose credit note is already voided can't be cancelled",
    3184: 'An empty column or table name in a database error is returned as `""` instead of `None`',
    3186: "Completing a PO return can store a negative received quantity",
    3185: "The PO's unlink event records `invoice_id: null` when a draft invoice was deleted",
}


def xfail(*ns, strict=True):
    """Expect `xfail BUG-n` -> strict xfail; `(non-strict)` -> strict=False."""
    return pytest.mark.xfail(
        strict=strict, reason="; ".join(f"BUG-{n}: {_BUGS[n]}" for n in ns)
    )


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Time: utcnow of the service returns NOW (naive, like the real helper)
@pytest.fixture(autouse=True)
def clock():
    with patch("app.services.purchase_order_service.utcnow", return_value=NOW):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.TAG = uuid.uuid4().hex[:8]
    n.W0, n.W1, n.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    for i, name in enumerate(("Rahim Uddin", "Karim Ali", "Nadia Khan", "Esha Roy"), start=1):
        setattr(n, f"U{i}", make_profile(db, name=name))
    for u, st in ((n.U1, "active"), (n.U2, "active"), (n.U3, "active"), (n.U4, "inactive")):
        _add(db, WorkspaceMember(workspace_id=n.W1.id, user_id=u.id, role="member", status=st))
    accounts = {"0": "Zeta West", "1": "Acme Supplies", "9": "Xeno Foreign"}
    for k, ws in (("0", n.W0), ("1", n.W1), ("9", n.W2)):
        for prefix, stage in (("SD", "Draft"), ("SP", "Planning"), ("SR", "Receiving"), ("SC", "Complete")):
            setattr(n, prefix + k, _add(db, Status(workspace_id=ws.id, name=stage, comment="po stage")))
        seq = [getattr(n, p + k).id for p in ("SD", "SP", "SR", "SC")]
        setattr(n, "WF" + k, _add(db, OrderWorkflow(workspace_id=ws.id, name="Purchase Order", type="purchase", status_sequence=seq)))
        setattr(n, "F" + k, _add(db, Factory(workspace_id=ws.id, name="Main Store", abbreviation=f"MS{k}", is_active=True, is_deleted=False)))
        setattr(n, "A" + k, _add(db, Account(workspace_id=ws.id, name=accounts[k], is_active=True, is_deleted=False, allow_invoices=True)))
        setattr(n, "I" + k, _add(db, Item(workspace_id=ws.id, name="Bearing", name_normalized="bearing", unit="pcs", is_active=True)))
    n.I1b = _add(db, Item(workspace_id=n.W1.id, name="Cement", name_normalized="cement", unit="bag", is_active=True))
    n.WS = {"0": n.W0, "1": n.W1, "9": n.W2}
    n.KEY = {n.W0.id: "0", n.W1.id: "1", n.W2.id: "9"}
    return n


def _k(s, ws_id):
    return s.KEY[ws_id]


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

READY = {"supplier_confirmed": True, "details_confirmed": True, "items_confirmed": True}
PROJ = {"destination_type": "project", "destination_id": 4242}


def COMPLETE(s):
    return {"current_status_id": s.SC1.id}


def VOIDED(s):
    return {"voided": True, "void_note": "Duplicate", "voided_at": T0, "voided_by": s.U1.id}


def po(db, s, n, k="1", **but):
    """Convention po "n" ("of W0" / "of W2" with k="0" / "9"); `but` = columns after "but"."""
    fields = {
        "workspace_id": s.WS[k].id,
        "po_number": f"PO-{s.TAG}-{n}",
        "account_id": getattr(s, "A" + k).id,
        "destination_type": "storage",
        "destination_id": getattr(s, "F" + k).id,
        "order_date": date(2026, 9, 1),
        "description": "Bearings for Press 4",
        "subtotal": Decimal("5000.00"),
        "total_amount": Decimal("5000.00"),
        "current_status_id": getattr(s, "SD" + k).id,
        "order_workflow_id": getattr(s, "WF" + k).id,
        "created_by": s.U1.id,
        "supplier_confirmed": False,
        "details_confirmed": False,
        "items_confirmed": False,
        "invoice_confirmed": False,
        "invoice_ever_linked": False,
        "voided": False,
        "paid": False,
    }
    fields.update(but)
    return _add(db, PurchaseOrder(**fields))


def po_many(db, s, count, start=1):
    """Givens like "101 orders po "1" … po "101"": one flush per row."""
    return [po(db, s, str(i)) for i in range(start, start + count)]


def poline(db, s, O, k, **but):
    """Convention poline(O, k)."""
    fields = {
        "workspace_id": O.workspace_id,
        "purchase_order_id": O.id,
        "line_number": k,
        "item_id": getattr(s, "I" + _k(s, O.workspace_id)).id,
        "quantity_ordered": Decimal("10.00"),
        "quantity_received": Decimal("0.00"),
        "quantity_returned": Decimal("0.00"),
        "quantity_refunded": Decimal("0.00"),
        "unit_price": Decimal("500.00"),
        "line_subtotal": Decimal("5000.00"),
    }
    fields.update(but)
    return _add(db, PurchaseOrderItem(**fields))


FINALIZED = {"invoice_status": "confirmed"}
LOCKED_INV = {"invoice_status": "locked"}
VOIDED_INV = {"invoice_status": "voided", "void_note": "dup"}


def link(db, O, V):
    """Convention "linked to O"."""
    O.invoice_id = V.id
    O.invoice_ever_linked = True
    if V.invoice_status == "confirmed" and O.supplier_confirmed and O.details_confirmed and O.items_confirmed:
        O.invoice_confirmed = True
    db.flush()


def inv(db, s, O, k=None, linked=False, **but):
    """Convention inv(O); k="0"/"9" = "of W0" / "of W2"; `linked` = "linked to O"."""
    k = k or _k(s, O.workspace_id)
    fields = {
        "workspace_id": s.WS[k].id,
        "account_id": getattr(s, "A" + k).id,
        "invoice_type": "payable",
        "invoice_status": "draft",
        "payment_status": "unpaid",
        "invoice_amount": Decimal("5000.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": date(2026, 9, 1),
        "allow_payments": True,
        "receiving_started": False,
        "created_by": s.U1.id,
        "order_type": "purchase_order",
        "order_id": O.id,
    }
    fields.update(but)
    V = _add(db, AccountInvoice(**fields))
    if linked:
        link(db, O, V)
    return V


def invl(db, s, V, k, amount):
    """Convention invl(V, k, s)."""
    return _add(
        db,
        InvoiceItem(
            workspace_id=V.workspace_id,
            invoice_id=V.id,
            line_number=k,
            description="Old line",
            quantity=Decimal("1"),
            unit_price=Decimal(amount),
            line_subtotal=Decimal(amount),
            created_by=s.U1.id,
        ),
    )


def poappr(db, s, O, U, approved=False):
    """Convention poappr(O, U) (approved = approved True, approved_at T1)."""
    return _add(
        db,
        PurchaseOrderApprover(
            workspace_id=O.workspace_id,
            purchase_order_id=O.id,
            user_id=U.id,
            assigned_by=s.U1.id,
            approved=approved,
            approved_at=T1 if approved else None,
            assigned_at=T0,
        ),
    )


REPLACE = {"return_type": "replace"}
VOIDED_RET = {"status": "voided"}


def COMPLETED(s):
    return {"status": "completed", "completed_at": T0, "completed_by": s.U1.id}


def ret(db, s, O, n, **but):
    """Convention ret "n" of O."""
    fields = {
        "workspace_id": O.workspace_id,
        "purchase_order_id": O.id,
        "return_number": f"PR-{s.TAG}-{n}",
        "return_type": "refund",
        "reason": "Faulty",
        "status": "pending",
        "paid": False,
        "created_by": s.U1.id,
    }
    fields.update(but)
    return _add(db, PurchaseOrderReturn(**fields))


def rline(db, R, L, q, **but):
    """Convention rline(R, L, q)."""
    fields = {
        "workspace_id": R.workspace_id,
        "return_id": R.id,
        "po_item_id": L.id,
        "item_id": L.item_id,
        "quantity_returned": Decimal(q),
        "unit_price": Decimal("500.00"),
    }
    fields.update(but)
    return _add(db, PurchaseOrderReturnItem(**fields))


def cn(db, s, R, a, **but):
    """Convention cn(R, a): a confirmed receivable credit note linked to R."""
    k = _k(s, R.workspace_id)
    fields = {
        "workspace_id": R.workspace_id,
        "account_id": getattr(s, "A" + k).id,
        "invoice_type": "receivable",
        "invoice_status": "confirmed",
        "payment_status": "unpaid",
        "invoice_amount": Decimal(a),
        "paid_amount": Decimal("0.00"),
        "invoice_date": date(2026, 9, 5),
        "allow_payments": True,
        "receiving_started": False,
        "created_by": s.U1.id,
        "order_type": "purchase_order",
        "order_id": R.purchase_order_id,
    }
    fields.update(but)
    CN = _add(db, AccountInvoice(**fields))
    R.invoice_id = CN.id
    db.flush()
    return CN


def cash(db, s, V, a, **but):
    """Convention cash(V, a)."""
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "payment_amount": Decimal(a),
        "payment_date": date(2026, 9, 20),
        "payment_method": "cash",
        "is_voided": False,
        "created_by": s.U1.id,
    }
    fields.update(but)
    return _add(db, InvoicePayment(**fields))


def spay(db, s, V, a, R, **but):
    """Convention spay(V, a, R)."""
    return cash(db, s, V, a, payment_method="settled_by_replacement", payment_reference=R.return_number, **but)


def ev(db, s, O, t, typ):
    """Convention ev(O, t, typ)."""
    return _add(
        db,
        PurchaseOrderEvent(
            workspace_id=O.workspace_id,
            purchase_order_id=O.id,
            event_type=typ,
            description="n",
            performed_by=s.U1.id,
            created_at=t,
        ),
    )


def repl(db, s, k="1", o_but=None, l_but=None, r_but=None, rl_but=None, cn_but=None):
    """Convention REPL (k="0" / "9" = REPL of W0 / of W2): O, V, L, R, RL, CN.
    The dicts are the columns after "but" for O, L, R, RL and CN."""
    g = SimpleNamespace()
    suffix = {"1": "", "0": "-w0", "9": "-w2"}[k]
    g.O = po(
        db, s, "1" + suffix, k,
        **{
            **READY,
            "current_status_id": getattr(s, "SC" + k).id,
            "invoice_confirmed": True,
            "actual_delivery_date": date(2026, 9, 10),
            **(o_but or {}),
        },
    )
    g.V = inv(db, s, g.O, linked=True, **FINALIZED, paid_amount=Decimal("5000.00"), payment_status="paid")
    g.L = poline(db, s, g.O, 1, **{"quantity_received": Decimal("6.00"), "quantity_returned": Decimal("4.00"), **(l_but or {})})
    g.R = ret(db, s, g.O, "1" + suffix, **{**REPLACE, **COMPLETED(s), **(r_but or {})})
    g.RL = rline(db, g.R, g.L, "4", **(rl_but or {}))
    g.CN = cn(db, s, g.R, "2000.00", **(cn_but or {}))
    return g


# --------------------------------------------------------------------------- #
# Conventions -> requests
# --------------------------------------------------------------------------- #


def RCV(*pairs, **k):
    return PoReceiveEventCreate(
        event_type="receive",
        items=[{"po_item_id": L.id, "quantity_delta": Decimal(d)} for L, d in pairs],
        **k,
    )


def COR(*pairs, note=None):
    return PoReceiveEventCreate(
        event_type="correction",
        items=[{"po_item_id": L.id, "quantity_delta": Decimal(d)} for L, d in pairs],
        correction_note=note,
    )


def RQ(*pairs):
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    return PurchaseOrderReturnReplacementCreate(
        items=[{"return_item_id": RL.id, "quantity": Decimal(q)} for RL, q in pairs]
    )


def RX(db, s, g, req):
    """Convention RX(req)."""
    return svc.receive_replacements(db, po_id=g.O.id, return_id=g.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=req)


def SRQ(*pairs, t="refund"):
    return PurchaseOrderReturnCreate(
        return_type=t,
        reason="Faulty",
        items=[
            PurchaseOrderReturnItemCreate(po_item_id=L.id, quantity_returned=Decimal(q), unit_price=Decimal("500.00"))
            for L, q in pairs
        ],
    )


def NEWPO(s, items):
    return PurchaseOrderCreate(
        account_id=s.A1.id,
        destination_type="storage",
        destination_id=s.F1.id,
        order_date=date(2026, 9, 1),
        description="Bearings",
        items=items,
    )


def NI(item, q):
    return PurchaseOrderItemCreate(item_id=item.id, quantity_ordered=Decimal(q), unit_price=Decimal("500.00"))


class FakeOrig(Exception):
    """Convention FakeOrig(msg, pgcode, table, column)."""

    def __init__(self, msg, pgcode, table, column):
        super().__init__(msg)
        self.pgcode = pgcode
        self.diag = SimpleNamespace(table_name=table, column_name=column)


def IERR(msg, pgcode, table, column):
    return IntegrityError("stmt", {}, FakeOrig(msg, pgcode, table, column))


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

_COUNT_TABLES = (
    "purchase_orders",
    "purchase_order_items",
    "purchase_order_events",
    "purchase_order_approvers",
    "purchase_order_returns",
    "purchase_order_return_items",
    "po_receive_events",
    "po_receive_event_items",
    "account_invoices",
    "invoice_items",
    "invoice_events",
    "invoice_payments",
    "notifications",
    "inventory_ledger",
    "inventory",
    "workspace_audit_logs",
)


# Named check "nothing written": row counts of the listed tables (all workspaces)
def counts(db):
    return tuple(db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES)


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


def reread(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


def gone(db, model, rid):
    db.expire_all()
    return db.get(model, rid) is None


def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


def count_where(db, model, *where):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


def rows_where(db, model, *where):
    db.expire_all()
    return list(db.scalars(select(model).where(*where).order_by(model.id)))


def EV(db, oid):
    return rows_where(db, PurchaseOrderEvent, PurchaseOrderEvent.purchase_order_id == oid)


def types(db, oid):
    return [e.event_type for e in EV(db, oid)]


def itypes(db, vid):
    return [e.event_type for e in rows_where(db, InvoiceEvent, InvoiceEvent.invoice_id == vid)]


def LINES(db, vid):
    db.expire_all()
    return list(db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == vid).order_by(InvoiceItem.line_number)))


def PAYS(db, vid):
    return rows_where(db, InvoicePayment, InvoicePayment.invoice_id == vid)


def SETTLE(db, vid):
    return [p for p in PAYS(db, vid) if p.payment_method == "settled_by_replacement"]


def LEDGER(db, src):
    return rows_where(
        db, InventoryLedger,
        InventoryLedger.source_type == "purchase_return_replacement",
        InventoryLedger.source_id == src,
    )


def RCVLEDGER(db, s):
    return rows_where(
        db, InventoryLedger,
        InventoryLedger.source_type == "po_receive_event_item",
        InventoryLedger.workspace_id == s.W1.id,
    )


def STOCK(db, s, F, I):
    db.expire_all()
    return db.scalars(
        select(Inventory).where(Inventory.workspace_id == s.W1.id, Inventory.factory_id == F.id, Inventory.item_id == I.id)
    ).one_or_none()


def WARN(r):
    return PurchaseOrderReturnResponse.model_validate(r).warnings


def REVENTS(db, rid):
    return rows_where(db, PurchaseOrderReturnEvent, PurchaseOrderReturnEvent.return_id == rid)


def AUDIT(db, s):
    db.expire_all()
    return list(
        db.execute(
            text(
                "SELECT * FROM financial_audit_logs WHERE entity_type = 'payment'"
                " AND action_type = 'created' AND workspace_id = :w ORDER BY id"
            ),
            {"w": s.W1.id},
        ).mappings()
    )


def notes(db):
    db.expire_all()
    return list(db.scalars(select(Notification).order_by(Notification.id)))


def recips(db):
    return sorted(n.recipient_user_id for n in notes(db))


def session_clean(db):
    return not db.new and not db.dirty and not db.deleted


def loaded(r):
    return inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})


def po_count(db, s, ws=None):
    return count_where(db, PurchaseOrder, PurchaseOrder.workspace_id == (ws or s.W1).id)


@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield cm, rb


@contextmanager
def failing_commit(db):
    with patch.object(db, "commit", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


_FROM = re.compile(
    r"\bFROM\b(.*?)(?:\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bFOR UPDATE\b|$)",
    re.DOTALL,
)


def _from_names(sql, table):
    m = _FROM.search(sql)
    return m is not None and re.search(rf"\b{re.escape(table)}\b", m.group(1)) is not None


class Recorder:
    """Convention "Statement recorder": every SQL statement sent while active."""

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

    def selects(self):
        return [(i, st) for i, st in enumerate(self.statements) if st.lstrip().upper().startswith("SELECT")]

    def selects_from(self, table):
        return [st for _, st in self.selects() if _from_names(st, table)]

    def _lock_idx(self, table):
        for i, st in self.selects():
            if _from_names(st, table) and "FOR UPDATE" in st:
                return i
        return None

    def lock(self, table):
        """lock(T): the first recorded SELECT from T containing FOR UPDATE, or None."""
        i = self._lock_idx(table)
        return None if i is None else self.statements[i]

    def exact_lock(self, table):
        st = self.lock(table)
        return (
            st is not None
            and st.rstrip().endswith("FOR UPDATE")
            and not any(x in st for x in ("SKIP LOCKED", "NOWAIT", "FOR UPDATE OF"))
        )

    def exact_lock_of(self, table):
        st = self.lock(table)
        return (
            st is not None
            and st.rstrip().endswith(f"FOR UPDATE OF {table}")
            and "SKIP LOCKED" not in st
            and "NOWAIT" not in st
        )

    def before(self, table, other):
        """T before U: lock(T) is sent before the first SELECT naming U."""
        i = self._lock_idx(table)
        if i is None:
            return False
        firsts = [j for j, st in self.selects() if _from_names(st, other)]
        return not firsts or i < firsts[0] or (i == firsts[0])

    def locked_before(self, table, other):
        i, j = self._lock_idx(table), self._lock_idx(other)
        return i is not None and j is not None and i < j

    def first_insert(self, table):
        """Index of the first recorded `INSERT INTO <table>`, or None."""
        for i, st in enumerate(self.statements):
            if st.lstrip().upper().startswith(f"INSERT INTO {table.upper()} "):
                return i
        return None

    def no_lock(self):
        return not any("FOR UPDATE" in st for st in self.statements)


# keep imported names referenced (some are used only by later parts)
_USED = (
    logging, ValidationError, Item, PoReceiveEvent, PoReceiveEventItem, WorkspaceAuditLog,
    PurchaseOrderItemSyncRequest, PurchaseOrderItemSyncUpdate, PurchaseOrderItemUpdate,
    PurchaseOrderVoidRequest, PurchaseOrderReturnVoidRequest, InvoicePaymentCreate,
    InvoicePaymentUpdate, ipm, Status, Notification,
)


# --------------------------------------------------------------------------- #
# _integrity_context
# --------------------------------------------------------------------------- #


def test_pos_ic_01__table_and_column_from_diag():
    """POS-IC-01 — table and column come from the error's diag.
    Rules: _integrity_context IC1."""
    err = IERR("null value", "23502", "purchase_order_items", "unit_price")

    result = svc._integrity_context(err)

    # Then 1
    assert result == ("purchase_order_items", "unit_price")


def test_pos_ic_02__no_orig_gives_none():
    """POS-IC-02 — no orig gives (None, None).
    Rules: _integrity_context IC1."""
    err = IntegrityError("stmt", {}, None)

    result = svc._integrity_context(err)

    # Then 1
    assert result == (None, None)


def test_pos_ic_03__orig_without_diag_gives_none():
    """POS-IC-03 — an orig without diag gives (None, None).
    Rules: _integrity_context IC1."""
    orig = Exception("x")
    err = IntegrityError("stmt", {}, orig)

    result = svc._integrity_context(err)

    # Then 1
    assert result == (None, None)


@xfail(3184)
def test_pos_ic_04__empty_column_counts_as_missing():
    """POS-IC-04 — an empty column name counts as missing; the table is kept.
    Rules: _integrity_context IC1."""
    err = IERR("x", "23502", "account_invoices", "")

    result = svc._integrity_context(err)

    # Then 1
    assert result == ("account_invoices", None)


def test_pos_ic_05__falsy_diag_counts_as_missing():
    """POS-IC-05 — a falsy diag counts as missing.
    Rules: _integrity_context IC1."""

    class FalsyDiag:
        table_name = "account_invoices"
        column_name = "invoice_date"

        def __bool__(self):
            return False

    orig = FakeOrig("x", "23502", None, None)
    orig.diag = FalsyDiag()
    err = IntegrityError("stmt", {}, orig)

    result = svc._integrity_context(err)

    # Then 1
    assert result == (None, None)


# --------------------------------------------------------------------------- #
# _handle_item_integrity_error
# --------------------------------------------------------------------------- #


def test_pos_ie_01__check_received_400_chained():
    """POS-IE-01 — check violation on received quantity → 400 ordered-vs-received, chained.
    Rules: _handle_item_integrity_error IE1, Returns."""
    err = IERR("violates check constraint ck_quantity_received", "23514", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Ordered quantity cannot be less than received quantity"
    # Then 4
    assert exc.value.__cause__ is err


def test_pos_ie_02__text_only_check_ordered_received():
    """POS-IE-02 — text-only check violation naming "ordered" and "received" → same 400.
    Rules: _handle_item_integrity_error IE1."""
    err = IERR("CHECK CONSTRAINT: Ordered must cover Received", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Ordered quantity cannot be less than received quantity"


def test_pos_ie_03__check_paid_amount():
    """POS-IE-03 — check violation on paid amount → 400 total-vs-paid.
    Rules: _handle_item_integrity_error IE1."""
    err = IERR("violates check constraint ck_paid_amount", "23514", "account_invoices", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order total cannot be less than amount already paid on the linked invoice"


def test_pos_ie_04__other_check_business_rule():
    """POS-IE-04 — other check violation → 400 business rule.
    Rules: _handle_item_integrity_error IE1."""
    err = IERR("violates check constraint ck_unit_price", "23514", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Update violates a business rule. Check amounts and quantities."


def test_pos_ie_05__check_with_duplicate_text_is_ie1():
    """POS-IE-05 — check violation with "duplicate" in the text is still IE1 (IE1 first).
    Rules: _handle_item_integrity_error IE1, IE6."""
    err = IERR("violates check constraint ck_x duplicate", "23514", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Update violates a business rule. Check amounts and quantities."


def test_pos_ie_06__unique_on_invoices_409():
    """POS-IE-06 — unique violation on the invoices table → 409 draft exists.
    Rules: _handle_item_integrity_error IE2."""
    err = IERR("violates unique constraint uq_x", "23505", "account_invoices", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "A draft invoice for this order already exists"


def test_pos_ie_07__unique_invoice_phase_409():
    """POS-IE-07 — unique violation in the invoice phase on a lines table → 409 draft exists.
    Rules: _handle_item_integrity_error IE2."""
    err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "A draft invoice for this order already exists"


def test_pos_ie_08__unique_lines_items_phase_409():
    """POS-IE-08 — unique violation on lines in the items phase → 409 catalog item.
    Rules: _handle_item_integrity_error IE2."""
    err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "That catalog item is already on this purchase order"


def test_pos_ie_09__duplicate_text_no_pgcode_409():
    """POS-IE-09 — text "duplicate" without a pgcode → 409 catalog item.
    Rules: _handle_item_integrity_error IE2."""
    err = IERR("Duplicate key value", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "That catalog item is already on this purchase order"


def test_pos_ie_10__not_null_invoice_table_with_location():
    """POS-IE-10 — not-null on an invoice table with column → 400 sync text with location.
    Rules: _handle_item_integrity_error IE3."""
    err = IERR("null value in column", "23502", "account_invoices", "invoice_date")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Could not sync the draft invoice for this order (account_invoices.invoice_date). Save the supplier section again, then retry editing items."


def test_pos_ie_11__not_null_status_tracker():
    """POS-IE-11 — not-null on `invoice_status_tracker` → invoice sync text.
    Rules: _handle_item_integrity_error IE3."""
    err = IERR("null value in column", "23502", "invoice_status_tracker", "status")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.detail == "Could not sync the draft invoice for this order (invoice_status_tracker.status). Save the supplier section again, then retry editing items."


def test_pos_ie_12__not_null_line_with_location():
    """POS-IE-12 — not-null on a line in the items phase → line incomplete with location.
    Rules: _handle_item_integrity_error IE3."""
    err = IERR("null value in column", "23502", "purchase_order_items", "unit_price")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."


def test_pos_ie_13__not_null_no_column_no_location():
    """POS-IE-13 — not-null with the table but no column → no location.
    Rules: _handle_item_integrity_error IE3."""
    err = IERR("null value in column", "23502", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.detail == "Order line data is incomplete. Refresh the page and try again."


def test_pos_ie_14__not_null_text_invoice_phase():
    """POS-IE-14 — text "not-null constraint", invoice phase, no diag → invoice text, no location.
    Rules: _handle_item_integrity_error IE3."""
    err = IERR("violates not-null constraint", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."


def test_pos_ie_15__not_null_with_duplicate_is_ie2():
    """POS-IE-15 — not-null with "duplicate" in the text is IE2.
    Rules: _handle_item_integrity_error IE6."""
    err = IERR("null value duplicate", "23502", "purchase_order_items", "unit_price")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "That catalog item is already on this purchase order"


def test_pos_ie_16__fk_audit_logs_supplier_invalid():
    """POS-IE-16 — foreign key on `financial_audit_logs` → supplier or invoice invalid.
    Rules: _handle_item_integrity_error IE4."""
    err = IERR("violates foreign key", "23503", "financial_audit_logs", "invoice_id")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."


def test_pos_ie_17__fk_lines_catalog_missing():
    """POS-IE-17 — foreign key on lines in the items phase → catalog reference missing.
    Rules: _handle_item_integrity_error IE4."""
    err = IERR("violates foreign key", "23503", "purchase_order_items", "item_id")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."


def test_pos_ie_18__fk_text_invoice_phase():
    """POS-IE-18 — text "foreign key constraint" in the invoice phase → supplier text.
    Rules: _handle_item_integrity_error IE4."""
    err = IERR("violates foreign key constraint fk_x", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."


def test_pos_ie_19__fallback_invoice_logged(caplog):
    """POS-IE-19 — anything else in the invoice phase → fallback invoice text, logged.
    Rules: _handle_item_integrity_error IE5."""
    err = IERR("something odd", "XX000", None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with caplog.at_level(logging.ERROR):
            svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Could not sync the draft invoice after saving items. Refresh and try again."
    # Then 4
    assert len([r for r in caplog.records if r.levelname == "ERROR"]) >= 1


def test_pos_ie_20__fallback_items_chained():
    """POS-IE-20 — anything else in the items phase → fallback items text, chained.
    Rules: _handle_item_integrity_error IE5."""
    err = IERR("something odd", "XX000", None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.detail == "Could not save order items. Refresh the page and try again."
    # Then 3
    assert exc.value.__cause__ is err


def test_pos_ie_21__unknown_phase_is_items():
    """POS-IE-21 — an unknown phase behaves as items.
    Rules: _handle_item_integrity_error IE7."""
    err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="lines")
    # Then 2
    assert exc.value.detail == "That catalog item is already on this purchase order"


def test_pos_ie_22__default_phase_is_items():
    """POS-IE-22 — the default phase is items.
    Rules: _handle_item_integrity_error IE7."""
    err = IERR("something odd", "XX000", None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err)
    # Then 2
    assert exc.value.detail == "Could not save order items. Refresh the page and try again."


def test_pos_ie_23__mapper_writes_nothing(db, s):
    """POS-IE-23 — the mapper writes nothing and ends no transaction.
    Rules: _handle_item_integrity_error IE8, IE9."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)
    err = IERR("null value in column", "23502", "purchase_order_items", "unit_price")

    # Then 1
    with pytest.raises(HTTPException):
        with spies(db) as (cm, rb):
            svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert not db.dirty


def test_pos_ie_24__mapping():
    """POS-IE-24 — pgcode 23514 alone (no check text) → IE1, ordered-vs-received.
    Rules: _handle_item_integrity_error IE1 (pgcode branch)."""
    err = IERR("new row rejected: quantity_ordered below received", "23514", "purchase_order_items", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Ordered quantity cannot be less than received quantity"


def test_pos_ie_25__mapping():
    """POS-IE-25 — a check violation naming only "ordered" → business-rule text.
    Rules: _handle_item_integrity_error IE1 (both words needed)."""
    err = IERR("violates check constraint ck_ordered_positive", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Update violates a business rule. Check amounts and quantities."


def test_pos_ie_26__mapping():
    """POS-IE-26 — a check violation naming only "received" → business-rule text.
    Rules: _handle_item_integrity_error IE1 (both words needed)."""
    err = IERR("violates check constraint ck_received_nonneg", None, None, None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Update violates a business rule. Check amounts and quantities."


def test_pos_ie_27__mapping():
    """POS-IE-27 — pgcode 23505 alone (no unique text) → IE2, catalog item.
    Rules: _handle_item_integrity_error IE2 (pgcode branch)."""
    err = IERR("row rejected", "23505", "purchase_order_items", "item_id")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "That catalog item is already on this purchase order"


def test_pos_ie_28__mapping():
    """POS-IE-28 — pgcode 23502 alone (no not-null text) → IE3, line incomplete.
    Rules: _handle_item_integrity_error IE3 (pgcode branch)."""
    err = IERR("row rejected", "23502", "purchase_order_items", "unit_price")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."


def test_pos_ie_29__mapping():
    """POS-IE-29 — not-null on `financial_audit_logs` in the items phase → invoice sync text.
    Rules: _handle_item_integrity_error IE3 (table list)."""
    err = IERR("null value in column", "23502", "financial_audit_logs", "invoice_id")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Could not sync the draft invoice for this order (financial_audit_logs.invoice_id). Save the supplier section again, then retry editing items."


def test_pos_ie_30__mapping():
    """POS-IE-30 — not-null in the invoice phase with the table only → no location.
    Rules: _handle_item_integrity_error IE3 (`{loc}` needs both)."""
    err = IERR("null value in column", "23502", "account_invoices", None)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."


def test_pos_ie_31__mapping():
    """POS-IE-31 — not-null in the invoice phase with the column only → no location.
    Rules: _handle_item_integrity_error IE3 (`{loc}` needs both)."""
    err = IERR("null value in column", "23502", None, "invoice_date")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="invoice")
    # Then 2
    assert exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."


def test_pos_ie_32__mapping():
    """POS-IE-32 — foreign key on `account_invoices` in the items phase → supplier or invoice invalid.
    Rules: _handle_item_integrity_error IE4 (table list)."""
    err = IERR("violates foreign key", "23503", "account_invoices", "account_id")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._handle_item_integrity_error(err, phase="items")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."


# --------------------------------------------------------------------------- #
# _build_invoice_items_from_po
# --------------------------------------------------------------------------- #


def test_pos_bi_01__one_dict_per_line_by_number():
    """POS-BI-01 — one dict per line, by line number, with every field.
    Rules: _build_invoice_items_from_po BI1, BI2."""
    l2 = SimpleNamespace(id=72, line_number=2, item_name="Cement", item_id=8, quantity_ordered=Decimal("5.00"), quantity_received=Decimal("1.00"), item_unit="bag", unit_price=Decimal("300.00"), line_subtotal=Decimal("1500.00"))
    l1 = SimpleNamespace(id=71, line_number=1, item_name="Bearing", item_id=7, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("0.00"), item_unit="pcs", unit_price=Decimal("500.00"), line_subtotal=Decimal("5000.00"))
    p = SimpleNamespace(line_items=[l2, l1])

    result = svc._build_invoice_items_from_po(p)

    # Then 1
    assert [d["line_number"] for d in result] == [1, 2]
    # Then 2
    assert result[0] == {"line_number": 1, "description": "Bearing", "item_id": 7, "source_order_item_id": 71, "source_order_item_type": "po_item", "quantity": Decimal("10.00"), "unit": "pcs", "unit_price": Decimal("500.00"), "line_subtotal": Decimal("5000.00")}
    # Then 3
    assert result[1]["quantity"] == Decimal("5.00")


def test_pos_bi_02__no_lines_empty():
    """POS-BI-02 — no lines → empty list.
    Rules: _build_invoice_items_from_po BI1."""
    result = svc._build_invoice_items_from_po(SimpleNamespace(line_items=[]))

    # Then 1
    assert result == []


def test_pos_bi_03__line_items_none_empty():
    """POS-BI-03 — `line_items` None → empty list.
    Rules: _build_invoice_items_from_po BI1."""
    result = svc._build_invoice_items_from_po(SimpleNamespace(line_items=None))

    # Then 1
    assert result == []


def test_pos_bi_04__empty_name_falls_back():
    """POS-BI-04 — an empty item name falls back to `Item <item_id>`.
    Rules: _build_invoice_items_from_po BI2."""
    l1 = SimpleNamespace(id=71, line_number=1, item_name="", item_id=7, quantity_ordered=Decimal("10.00"), item_unit="pcs", unit_price=Decimal("500.00"), line_subtotal=Decimal("5000.00"))

    result = svc._build_invoice_items_from_po(SimpleNamespace(line_items=[l1]))

    # Then 1
    assert result[0]["description"] == "Item 7"


# --------------------------------------------------------------------------- #
# _delete_linked_draft_invoice_for_po
# --------------------------------------------------------------------------- #


def test_pos_dd_01__no_invoice_nothing_written(db, s):
    """POS-DD-01 — no invoice linked → nothing written.
    Rules: _delete_linked_draft_invoice_for_po DD1."""
    O = po(db, s, "1")
    before = commit_point(db)

    result = svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert session_clean(db)
    # Then 3
    assert counts(db) == before


def test_pos_dd_02__foreign_invoice_untouched(db, s):
    """POS-DD-02 — an invoice of another workspace linked → nothing written.
    Rules: _delete_linked_draft_invoice_for_po DD1; HR-16."""
    O = po(db, s, "1")
    V9 = inv(db, s, O, k="9", linked=True)
    commit_point(db)
    v9_before = snap(db, V9)

    svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert session_clean(db)
    # Then 2
    assert snap(db, V9) == v9_before
    # Then 3
    assert reread(db, PurchaseOrder, O.id).invoice_id == V9.id


def test_pos_dd_03__confirmed_invoice_not_deleted(db, s):
    """POS-DD-03 — a confirmed invoice is not deleted.
    Rules: _delete_linked_draft_invoice_for_po DD1."""
    O = po(db, s, "1")
    V = inv(db, s, O, linked=True, **FINALIZED)
    before = commit_point(db)
    v_before = snap(db, V)

    svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert session_clean(db)
    # Then 2
    assert snap(db, V) == v_before
    # Then 3
    assert counts(db) == before


@xfail(3185)
def test_pos_dd_04__draft_deleted_event_records_id(db, s):
    """POS-DD-04 — the draft-deleted event records the deleted draft's id.
    Rules: _delete_linked_draft_invoice_for_po DD2a [BUG-3185]."""
    O = po(db, s, "1")
    V = inv(db, s, O, linked=True)
    vid = V.id
    commit_point(db)

    svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert [e.metadata_json for e in EV(db, O.id) if e.event_type == "invoice_draft_deleted"] == [{"invoice_id": vid}]


@xfail(639)
def test_pos_dd_05__draft_with_payment_history_refused(db, s):
    """POS-DD-05 — a draft with payment history is refused by the invoice manager and stays.
    Rules: _delete_linked_draft_invoice_for_po DD2 [BUG-639] (pass-through)."""
    O = po(db, s, "1")
    V = inv(db, s, O, linked=True, paid_amount=Decimal("100.00"), payment_status="partial")
    cash(db, s, V, "100.00")
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == PAYHIST
    sp.rollback()
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.id == V.id) == 1


def test_pos_dd_06__draft_deleted_unlinked_event(db, s):
    """POS-DD-06 — a draft is deleted, the order unlinked, one event; flushed, not committed.
    Rules: _delete_linked_draft_invoice_for_po DD2 (the part that holds today and after BUG-3185)."""
    O = po(db, s, "1")
    V = inv(db, s, O, linked=True)
    vid = V.id
    commit_point(db)

    with spies(db) as (cm, rb):
        svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert reread(db, PurchaseOrder, O.id).invoice_id is None
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.id == vid) == 0
    # Then 5
    assert types(db, O.id).count("invoice_draft_deleted") == 1
    e = event_of(db, O.id, "invoice_draft_deleted")
    assert e.description == f"Draft invoice #{vid} deleted"
    assert "invoice_id" in e.metadata_json


# --------------------------------------------------------------------------- #
# _sync_draft_invoice_for_po
# --------------------------------------------------------------------------- #


def test_pos_sd_01__financially_locked_none(db, s):
    """POS-SD-01 — financially locked → None, nothing written.
    Rules: _sync_draft_invoice_for_po SD1."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **FINALIZED)
    before = commit_point(db)
    v_before = snap(db, V)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert session_clean(db)
    # Then 3
    assert snap(db, V) == v_before
    # Then 4
    assert counts(db) == before


def test_pos_sd_02__not_confirmed_draft_removed(db, s):
    """POS-SD-02 — not forced, not confirmed → the linked draft is removed.
    Rules: _sync_draft_invoice_for_po SD2."""
    O = po(db, s, "1", supplier_confirmed=True)
    V = inv(db, s, O, linked=True)
    vid = V.id
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.id == vid) == 0
    # Then 3
    assert reread(db, PurchaseOrder, O.id).invoice_id is None
    # Then 4
    assert types(db, O.id)[-1] == "invoice_draft_deleted"


def test_pos_sd_03__not_confirmed_nothing_linked(db, s):
    """POS-SD-03 — not forced, not confirmed, nothing linked → None, nothing written.
    Rules: _sync_draft_invoice_for_po SD2."""
    O = po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    poline(db, s, O, 1)
    before = commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert session_clean(db)
    # Then 3
    assert counts(db) == before


def test_pos_sd_04__forced_not_confirmed_422(db, s):
    """POS-SD-04 — forced, not confirmed → 422.
    Rules: _sync_draft_invoice_for_po SD3."""
    O = po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    poline(db, s, O, 1)
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id, force_create=True)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == FORCE422
    # Then 4
    assert session_clean(db)
    sp.rollback()


def test_pos_sd_05__no_supplier_none(db, s):
    """POS-SD-05 — confirmed but no supplier → None, nothing written.
    Rules: _sync_draft_invoice_for_po SD4."""
    O = po(db, s, "1", **READY, account_id=None)
    poline(db, s, O, 1)
    before = commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before


def test_pos_sd_06__draft_created_and_linked(db, s):
    """POS-SD-06 — confirmed, no invoice → a draft mirroring the order is created and linked.
    Rules: _sync_draft_invoice_for_po SD5, SD6."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1)
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.invoice_id == result
    assert o.invoice_ever_linked is True
    # Then 3
    v = reread(db, AccountInvoice, result)
    assert v.account_id == s.A1.id
    assert v.order_id == O.id
    assert v.order_type == "purchase_order"
    assert v.invoice_type == "payable"
    assert v.invoice_status == "draft"
    # Then 4
    assert v.invoice_number is None
    assert v.vendor_invoice_number is None
    assert v.due_date is None
    assert v.payment_locked_reason is None
    assert v.allow_payments is True
    # Then 5
    assert v.description == f"Purchase order {O.po_number}"
    assert v.notes == "Bearings for Press 4"
    assert v.invoice_amount == Decimal("5000.00")
    # Then 6
    lines = LINES(db, result)
    assert len(lines) == 1
    assert lines[0].source_order_item_id == L.id
    assert lines[0].source_order_item_type == "po_item"
    assert lines[0].quantity == Decimal("10.00")
    assert lines[0].unit_price == Decimal("500.00")
    # Then 7
    evs = EV(db, O.id)
    assert evs[-1].event_type == "invoice_draft_created"
    assert evs[-1].description == f"Draft invoice #{result} linked to {O.po_number}"
    assert evs[-1].metadata_json == {"invoice_id": result}


@xfail(3167)
def test_pos_sd_07__draft_dated_utc(db, s):
    """POS-SD-07 — the new draft is dated with the UTC clock.
    Rules: _sync_draft_invoice_for_po SD7 [BUG-3167]."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert reread(db, AccountInvoice, result).invoice_date == TODAY_UTC


def test_pos_sd_08__foreign_supplier_422(db, s):
    """POS-SD-08 — the supplier is not found in the workspace → 422 re-select.
    Rules: _sync_draft_invoice_for_po SD8; HR-16."""
    O = po(db, s, "1", **READY, account_id=s.A9.id)
    poline(db, s, O, 1)
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == SUPP422
    sp.rollback()


def test_pos_sd_09__other_refusal_passes(db, s):
    """POS-SD-09 — another refusal of the invoice create passes unchanged.
    Rules: _sync_draft_invoice_for_po SD5, SD8."""
    A2 = _add(db, Account(workspace_id=s.W1.id, name="No Bills Ltd", is_active=True, is_deleted=False, allow_invoices=False))
    O = po(db, s, "1", **READY, account_id=A2.id)
    poline(db, s, O, 1)
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    sp.rollback()


# [claude] POS-SD-10
def test_pos_sd_10__404_but_invoice_linked_meanwhile(db, s):
    """POS-SD-10 — create answers 404 but the order now has an invoice → None, no error.
    Rules: _sync_draft_invoice_for_po SD8."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    commit_point(db)

    def race(*args, **kwargs):
        inv(db, s, O, linked=True)
        raise HTTPException(404, "Account not found")

    with patch.object(aim, "create_invoice", side_effect=race):
        result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert reread(db, PurchaseOrder, O.id).invoice_id is not None


def test_pos_sd_11__voided_invoice_none(db, s):
    """POS-SD-11 — a linked voided invoice → None, nothing written.
    Rules: _sync_draft_invoice_for_po SD9."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **VOIDED_INV)
    before = commit_point(db)
    v_before = snap(db, V)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, V) == v_before
    # Then 3
    assert counts(db) == before


def test_pos_sd_12__foreign_invoice_none(db, s):
    """POS-SD-12 — a linked invoice of another workspace → None, nothing written.
    Rules: _sync_draft_invoice_for_po SD9; HR-16."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V9 = inv(db, s, O, k="9", linked=True)
    before = commit_point(db)
    v9_before = snap(db, V9)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, V9) == v9_before
    # Then 3
    assert counts(db) == before


def test_pos_sd_13__account_changed_confirmed_resets(db, s):
    """POS-SD-13 — draft account changed and invoice confirmed → unconfirm, reset, notify, event.
    Rules: _sync_draft_invoice_for_po SD10, SD11."""
    A2 = _add(db, Account(workspace_id=s.W1.id, name="Beta Traders", is_active=True, is_deleted=False, allow_invoices=True))
    O = po(db, s, "1", **READY, invoice_confirmed=True)
    poline(db, s, O, 1)
    V = inv(db, s, O, account_id=A2.id)
    O.invoice_id = V.id
    O.invoice_ever_linked = True
    db.flush()
    P3 = poappr(db, s, O, s.U3, approved=True)
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert reread(db, PurchaseOrder, O.id).invoice_confirmed is False
    # Then 3
    assert reread(db, PurchaseOrderApprover, P3.id).approved is False
    # Then 4
    assert reread(db, AccountInvoice, V.id).account_id == s.A1.id
    # Then 5
    assert [(n.recipient_user_id, n.notification_type) for n in notes(db)] == [(s.U1.id, "section_confirm")]
    # Then 6
    assert notes(db)[0].preview == "Draft invoice changed — approvals reset; re-confirm sections"
    # Then 7
    assert "invoice_unconfirmed" in types(db, O.id)
    e = next(e for e in EV(db, O.id) if e.event_type == "invoice_unconfirmed")
    assert e.description == "Draft invoice unconfirmed after order sync"
    # Then 8
    assert types(db, O.id).count("approvals_reset") == 1
    assert event_of(db, O.id, "approvals_reset").description == "Draft invoice changed after order update (1 approval(s) cleared)"
    # Then 9
    assert notes(db)[0].entity_type == "purchase_order"
    assert notes(db)[0].entity_id == O.id


def test_pos_sd_14__account_changed_not_confirmed(db, s):
    """POS-SD-14 — account changed but invoice not confirmed → account synced, no reset.
    Rules: _sync_draft_invoice_for_po SD10, SD11."""
    A2 = _add(db, Account(workspace_id=s.W1.id, name="Beta Traders", is_active=True, is_deleted=False, allow_invoices=True))
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, account_id=A2.id)
    O.invoice_id = V.id
    O.invoice_ever_linked = True
    db.flush()
    P3 = poappr(db, s, O, s.U3, approved=True)
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert reread(db, AccountInvoice, V.id).account_id == s.A1.id
    # Then 3
    assert reread(db, PurchaseOrderApprover, P3.id).approved is True
    # Then 4
    assert notes(db) == []
    # Then 5
    assert "invoice_unconfirmed" not in types(db, O.id)


def test_pos_sd_15__description_notes_updated_lines_recopied(db, s):
    """POS-SD-15 — description and notes differing are updated; lines re-copied.
    Rules: _sync_draft_invoice_for_po SD11."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, description="Old", notes="Old notes")
    invl(db, s, V, 1, "1.00")
    commit_point(db)

    result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    v = reread(db, AccountInvoice, V.id)
    assert v.description == f"Purchase order {O.po_number}"
    assert v.notes == "Bearings for Press 4"
    # Then 3
    lines = LINES(db, V.id)
    assert len(lines) == 1
    assert lines[0].source_order_item_id == L.id
    assert lines[0].unit_price == Decimal("500.00")
    # Then 4
    assert itypes(db, V.id).count("items_synced") == 1


# [claude] POS-SD-16
def test_pos_sd_16__nothing_differs_no_update(db, s):
    """POS-SD-16 — nothing differs → no update call, lines still re-copied.
    Rules: _sync_draft_invoice_for_po SD11."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, description=f"Purchase order {O.po_number}", notes="Bearings for Press 4")
    commit_point(db)

    with patch.object(aim, "update_invoice", wraps=aim.update_invoice) as up:
        result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    # Then 2
    assert up.call_count == 0
    # Then 3
    assert itypes(db, V.id).count("items_synced") == 1


# [claude] POS-SD-17
def test_pos_sd_17__empty_notes_equal_none(db, s):
    """POS-SD-17 — empty notes and `None` description count as equal.
    Rules: _sync_draft_invoice_for_po SD11."""
    O = po(db, s, "1", **READY, description=None)
    poline(db, s, O, 1)
    inv(db, s, O, linked=True, description=f"Purchase order {O.po_number}", notes="")
    commit_point(db)

    with patch.object(aim, "update_invoice", wraps=aim.update_invoice) as up:
        svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert up.call_count == 0


def test_pos_sd_18__helper_flushes_only(db, s):
    """POS-SD-18 — the helper flushes only.
    Rules: _sync_draft_invoice_for_po Returns."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    commit_point(db)

    with spies(db) as (cm, rb):
        result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


# --------------------------------------------------------------------------- #
# _emit_po_invoice_draft_notification
# --------------------------------------------------------------------------- #


def test_pos_en_01__no_invoice_id_nothing(db, s):
    """POS-EN-01 — no invoice id → nothing.
    Rules: _emit_po_invoice_draft_notification EN1."""
    O = po(db, s, "1")
    poappr(db, s, O, s.U3)
    commit_point(db)

    svc._emit_po_invoice_draft_notification(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id, invoice_id=None)

    # Then 1
    assert not db.new
    # Then 2
    assert notes(db) == []


def test_pos_en_02__draft_notifies_approver_and_creator(db, s):
    """POS-EN-02 — a new draft notifies the pending approver and the creator; flushed only.
    Rules: _emit_po_invoice_draft_notification EN2."""
    O = po(db, s, "1", **READY)
    poappr(db, s, O, s.U3)
    V = inv(db, s, O, linked=True)
    commit_point(db)

    with spies(db) as (cm, rb):
        svc._emit_po_invoice_draft_notification(db, po=O, workspace_id=s.W1.id, user_id=s.U2.id, invoice_id=V.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert recips(db) == sorted([s.U1.id, s.U3.id])
    # Then 4
    for n in notes(db):
        assert n.notification_type == "invoice_action"
        assert n.entity_type == "purchase_order"
        assert n.entity_id == O.id
        assert n.preview == DRAFTP


# --------------------------------------------------------------------------- #
# Shared: return-in-progress flag (has_open_return)
# --------------------------------------------------------------------------- #


@xfail(2789)
def test_pos_rf_01__get_with_pending_return_flag_true(db, s):
    """POS-RF-01 — GET of an order with a pending return carries `has_open_return True`.
    Rules: RF1 [BUG-2789]."""
    O = po(db, s, "1", **PROJ)
    poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    ret(db, s, O, "1")
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert result.has_open_return is True


@xfail(2789)
def test_pos_rf_02__only_closed_returns_flag_false(db, s):
    """POS-RF-02 — only completed and voided returns → `has_open_return False`.
    Rules: RF1 [BUG-2789]."""
    O = po(db, s, "1", **PROJ)
    poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    ret(db, s, O, "1", **COMPLETED(s))
    ret(db, s, O, "2", **VOIDED_RET)
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert result.has_open_return is False


@xfail(2789)
def test_pos_rf_03__foreign_pending_return_ignored(db, s):
    """POS-RF-03 — another workspace's pending return on the same order id does not count.
    Rules: RF1 [BUG-2789]; HR-16."""
    O = po(db, s, "1", **PROJ)
    ret(db, s, O, "9", workspace_id=s.W2.id)
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert result.has_open_return is False


@xfail(2789)
def test_pos_rf_04__list_rows_own_flag(db, s):
    """POS-RF-04 — list rows each carry their own flag.
    Rules: RF1 [BUG-2789]."""
    O1 = po(db, s, "1", **PROJ)
    O2 = po(db, s, "2", **PROJ)
    ret(db, s, O1, "1")
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=1000)

    # Then 1
    assert sorted(o.id for o in result.items) == sorted([O1.id, O2.id])
    # Then 2
    assert {o.id: o.has_open_return for o in result.items} == {O1.id: True, O2.id: False}


@xfail(2789)
def test_pos_rf_05__update_response_flag(db, s):
    """POS-RF-05 — the update response carries the flag.
    Rules: RF1 [BUG-2789]; update_purchase_order U5."""
    O = po(db, s, "1", **PROJ)
    ret(db, s, O, "1")
    commit_point(db)

    result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert result.has_open_return is True


@xfail(2789)
def test_pos_rf_06__completing_last_return_flag_off(db, s):
    """POS-RF-06 — completing the last pending return turns the flag off, nothing written on the order.
    Rules: RF2 [BUG-2789]."""
    O = po(db, s, "1", **PROJ, **READY, **COMPLETE(s))
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "2")
    svc.complete_return(db, po_id=O.id, return_id=R.id, workspace_id=s.W1.id, user_id=s.U2.id)
    status_before = reread(db, PurchaseOrder, O.id).current_status_id
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, PurchaseOrder, O.id).current_status_id == status_before
    # Then 3
    assert result.has_open_return is False


def test_pos_rf_07__reading_flag_writes_nothing(db, s):
    """POS-RF-07 — reading the flag writes nothing.
    Rules: RF3; TC6."""
    O = po(db, s, "1", **PROJ)
    ret(db, s, O, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert not db.new


# --------------------------------------------------------------------------- #
# create_purchase_order
# --------------------------------------------------------------------------- #


def test_pos_c_01__new_order_committed(db, s):
    """POS-C-01 — a new order is committed and returned re-read; no invoice, no notification.
    Rules: create_purchase_order C1; TC1, TC2."""
    commit_point(db)

    result = svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, PurchaseOrder)
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, PurchaseOrder, rid)
    assert row.workspace_id == s.W1.id
    assert row.account_id == s.A1.id
    assert row.created_by == s.U2.id
    assert row.current_status_id == s.SD1.id
    assert row.order_workflow_id == s.WF1.id
    assert row.invoice_id is None
    # Then 4
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == rid) == 1
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.order_type == "purchase_order", AccountInvoice.order_id == rid) == 0
    # Then 6
    assert notes(db) == []


def test_pos_c_02__status_and_workflow_in_body_ignored(db, s):
    """POS-C-02 — `current_status_id` / `order_workflow_id` in the body have no effect.
    Rules: create_purchase_order C3."""
    commit_point(db)
    body = PurchaseOrderCreate(**{**NEWPO(s, [NI(s.I1, "10")]).model_dump(), "current_status_id": s.SR1.id, "order_workflow_id": None})

    result = svc.create_purchase_order(db, po_in=body, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    row = reread(db, PurchaseOrder, rid)
    assert row.current_status_id == s.SD1.id
    assert row.order_workflow_id == s.WF1.id


# [claude] POS-C-03
def test_pos_c_03__number_clash_retried(db, s):
    """POS-C-03 — a PO-number clash is retried; the second attempt saves the order.
    Rules: create_purchase_order C2."""
    commit_point(db)
    real = mgr.create_purchase_order
    calls = []

    def first_clash(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise IERR("duplicate key violates uq_po_workspace_number", "23505", "purchase_orders", "po_number")
        return real(*args, **kwargs)

    with patch.object(mgr, "create_purchase_order", side_effect=first_clash) as m:
        result = svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert m.call_count == 2
    db.rollback()
    # Then 3
    assert po_count(db, s) == 1


# [claude] POS-C-04
def test_pos_c_04__five_clashes_409(db, s):
    """POS-C-04 — five clashes → 409, nothing saved.
    Rules: create_purchase_order C2."""
    commit_point(db)
    with patch.object(
        mgr, "create_purchase_order",
        side_effect=IERR("duplicate key value po_number", "23505", "purchase_orders", "po_number"),
    ) as m:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Could not assign a unique PO number. Please try again."
    # Then 4
    assert isinstance(exc.value.__cause__, IntegrityError)
    # Then 5
    assert m.call_count == 5
    db.rollback()
    # Then 6
    assert po_count(db, s) == 0


# [claude] POS-C-05
def test_pos_c_05__first_try_one_attempt(db, s):
    """POS-C-05 — a first-try success makes one attempt.
    Rules: create_purchase_order C2."""
    commit_point(db)

    with patch.object(mgr, "create_purchase_order", wraps=mgr.create_purchase_order) as m:
        result = svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert m.call_count == 1


# [claude] POS-C-06
def test_pos_c_06__other_integrity_error_reraised(db, s):
    """POS-C-06 — another IntegrityError is rolled back and re-raised as the same object, no retry.
    Rules: create_purchase_order C4; TC3."""
    err = IERR("violates foreign key fk_items", "23503", "purchase_order_items", "item_id")
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "create_purchase_order", side_effect=err) as m:
        # Then 1
        with pytest.raises(IntegrityError) as exc:
            svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value is err
    # Then 2
    assert X not in db
    # Then 3
    assert m.call_count == 1
    db.rollback()
    # Then 4
    assert x_gone(db, x_id)


# [claude] POS-C-07
def test_pos_c_07__non_http_error_reraised(db, s):
    """POS-C-07 — a non-HTTP error is rolled back and re-raised as the same object.
    Rules: create_purchase_order C4; TC3."""
    err = RuntimeError("manager broke")
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "create_purchase_order", side_effect=err):
        # Then 1
        with pytest.raises(RuntimeError) as exc:
            with spies(db) as (_cm, rb):
                svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value is err
    # Then 2
    assert X not in db
    # Then 3
    assert rb.call_count >= 1
    db.rollback()
    # Then 4
    assert x_gone(db, x_id)


def test_pos_c_08__repeated_item_409_passes(db, s):
    """POS-C-08 — the manager's 409 for a repeated item passes unchanged.
    Rules: create_purchase_order C5 (part that holds today)."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "5"), NI(s.I1, "3")]), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Bearing appears more than once on this order"


@xfail(3175)
def test_pos_c_09__refusal_rolled_back(db, s):
    """POS-C-09 — after the manager's 409 the session is rolled back: nothing pending.
    Rules: create_purchase_order C5 [BUG-3175]; TC3."""
    commit_point(db)
    MK = _add(db, Department(workspace_id=s.W1.id, name=f"Marker {s.TAG}"))
    MK_ID = MK.id

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "5"), NI(s.I1, "3")]), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert db.query(PurchaseOrder).filter_by(workspace_id=s.W1.id, description="Bearings").count() == 0
    # Then 4
    db.expire_all()
    assert db.get(Department, MK_ID) is None


def test_pos_c_10__failing_commit_rolled_back(db, s):
    """POS-C-10 — a failing commit is rolled back and re-raised; no order saved.
    Rules: create_purchase_order C1; TC4."""
    before = commit_point(db)
    data = NEWPO(s, [NI(s.I1, "10")])
    w1_id, u2_id = s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_purchase_order(db, po_in=data, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, PurchaseOrder, PurchaseOrder.workspace_id == w1_id) == 0
    # Then 4
    assert counts(db) == before


def test_pos_c_11__failing_refresh_keeps_order(db, s):
    """POS-C-11 — a failing re-read after the commit leaves the order saved.
    Rules: create_purchase_order C1; TC5."""
    commit_point(db)
    data = NEWPO(s, [NI(s.I1, "10")])
    w1_id, u2_id = s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_purchase_order(db, po_in=data, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert count_where(db, PurchaseOrder, PurchaseOrder.workspace_id == w1_id) == 1


# [claude] POS-C-12
def test_pos_c_12__constraint_name_only_clash_retried(db, s):
    """POS-C-12 — clashes naming only `uq_po_workspace_number` are retried too; the 5th → 409.
    Rules: create_purchase_order C2."""
    commit_point(db)
    with patch.object(
        mgr, "create_purchase_order",
        side_effect=IERR('duplicate key value violates unique constraint "uq_po_workspace_number"', "23505", "purchase_orders", None),
    ) as m:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.create_purchase_order(db, po_in=NEWPO(s, [NI(s.I1, "10")]), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Could not assign a unique PO number. Please try again."
    # Then 4
    assert m.call_count == 5
    db.rollback()
    # Then 5
    assert po_count(db, s) == 0


# --------------------------------------------------------------------------- #
# update_purchase_order
# --------------------------------------------------------------------------- #


def test_pos_u_01__edit_committed(db, s):
    """POS-U-01 — an edit is committed and returned re-read.
    Rules: update_purchase_order U1, U4; TC1, TC2."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)

    result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(description="Spare bearings"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == O.id
    db.rollback()
    # Then 3
    o = reread(db, PurchaseOrder, O.id)
    assert o.description == "Spare bearings"
    assert o.invoice_id is None
    # Then 4
    assert notes(db) == []


def test_pos_u_02__missing_order_404(db, s):
    """POS-U-02 — a missing order → 404, rolled back.
    Rules: update_purchase_order U1; TC3."""
    po(db, s, "1")
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_purchase_order(db, po_id=MISSING, po_in=PurchaseOrderUpdate(description="x"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


def test_pos_u_03__w0_order_404(db, s):
    """POS-U-03 — a W0 order id → 404, the W0 order unchanged.
    Rules: update_purchase_order U1."""
    O0 = po(db, s, "0", "0")
    po(db, s, "1")
    commit_point(db)
    o0_before = snap(db, O0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_purchase_order(db, po_id=O0.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)
    # Then 4
    assert snap(db, O0) == o0_before


def test_pos_u_04__w2_order_404(db, s):
    """POS-U-04 — a W2 order id → 404, the W2 order unchanged.
    Rules: update_purchase_order U1."""
    po(db, s, "1")
    O9 = po(db, s, "9", "9")
    commit_point(db)
    o9_before = snap(db, O9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_purchase_order(db, po_id=O9.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert snap(db, O9) == o9_before


def test_pos_u_05__last_section_drafts_invoice(db, s):
    """POS-U-05 — confirming the last section drafts the invoice in the same commit.
    Rules: update_purchase_order U3, U4."""
    O = po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    poline(db, s, O, 1)
    poappr(db, s, O, s.U3)
    commit_point(db)

    result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=True), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == O.id
    db.rollback()
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.items_confirmed is True
    assert o.invoice_id is not None
    # Then 3
    v = reread(db, AccountInvoice, o.invoice_id)
    assert v.invoice_status == "draft"
    assert v.invoice_type == "payable"
    assert v.order_id == O.id
    # Then 4
    assert "invoice_draft_created" in types(db, O.id)


def test_pos_u_06__ready_notices(db, s):
    """POS-U-06 — not ready → ready: approval-pending and draft notices.
    Rules: update_purchase_order U2, U3; _emit_po_invoice_draft_notification EN2."""
    O = po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    poline(db, s, O, 1)
    poappr(db, s, O, s.U3)
    commit_point(db)

    svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=True), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert sorted((n.recipient_user_id, n.notification_type) for n in notes(db)) == sorted([(s.U3.id, "approval_pending"), (s.U3.id, "invoice_action"), (s.U1.id, "invoice_action")])
    # Then 2
    for n in notes(db):
        if n.notification_type == "invoice_action":
            assert n.preview == DRAFTP


def test_pos_u_07__unconfirm_removes_draft_notifies(db, s):
    """POS-U-07 — an unconfirm removes the draft and tells the creator approvals were reset.
    Rules: update_purchase_order U2, U3; _sync_draft_invoice_for_po SD2."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True)
    vid = V.id
    poappr(db, s, O, s.U3, approved=True)
    commit_point(db)

    svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=False), workspace_id=s.W1.id, user_id=s.U2.id)

    db.rollback()
    # Then 1
    assert count_where(db, AccountInvoice, AccountInvoice.id == vid) == 0
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.invoice_id is None
    assert o.items_confirmed is False
    # Then 3
    assert any(
        n.recipient_user_id == s.U1.id and "Approvals were reset — re-confirm sections before approving" in n.preview
        for n in notes(db)
    )


def test_pos_u_08__edit_resyncs_draft(db, s):
    """POS-U-08 — an edit of a confirmed, unlocked order re-syncs the draft.
    Rules: update_purchase_order U3; SD11."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, description="Old")
    commit_point(db)

    svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=s.W1.id, user_id=s.U2.id)

    db.rollback()
    # Then 1
    assert reread(db, AccountInvoice, V.id).description == f"Purchase order {O.po_number}"
    # Then 2
    assert "items_synced" in itypes(db, V.id)
    # Then 3
    assert reread(db, PurchaseOrder, O.id).expected_delivery_date == date(2026, 10, 1)


def test_pos_u_09__manager_refusal_rolled_back(db, s):
    """POS-U-09 — the manager's refusal passes unchanged and is rolled back.
    Rules: update_purchase_order U1, U4; TC3."""
    O = po(db, s, "1", details_confirmed=True)
    commit_point(db)
    o_before = snap(db, O)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order details are confirmed"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, O) == o_before


# [claude] POS-U-10
def test_pos_u_10__integrity_error_invoice_phase(db, s):
    """POS-U-10 — an IntegrityError in the invoice step is translated (invoice phase) and rolls back the edit.
    Rules: update_purchase_order U4."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=IERR("null value in column", "23502", None, None)):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert reread(db, PurchaseOrder, O.id).expected_delivery_date is None


def test_pos_u_11__failing_commit_not_saved(db, s):
    """POS-U-11 — a failing commit is rolled back; the edit is not saved.
    Rules: update_purchase_order U4; TC4."""
    O = po(db, s, "1")
    commit_point(db)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_purchase_order(db, po_id=oid, po_in=PurchaseOrderUpdate(description="Spare bearings"), workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrder, oid).description == "Bearings for Press 4"


def test_pos_u_12__explicit_null_not_unconfirm(db, s):
    """POS-U-12 — a confirm field sent as explicit `null` is not an unconfirm.
    Rules: update_purchase_order U2; detect_section_unconfirmed R1 (pass-through)."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    P3 = poappr(db, s, O, s.U3, approved=True)
    commit_point(db)

    svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=None), workspace_id=s.W1.id, user_id=s.U2.id)

    db.rollback()
    # Then 1
    o = reread(db, PurchaseOrder, O.id)
    assert o.items_confirmed is True
    assert o.supplier_confirmed is True
    assert o.details_confirmed is True
    # Then 2
    assert reread(db, PurchaseOrderApprover, P3.id).approved is True
    # Then 3
    assert not any("Approvals were reset" in (n.preview or "") for n in notes(db))


# --------------------------------------------------------------------------- #
# get_purchase_order
# --------------------------------------------------------------------------- #


def test_pos_g_01__returns_order_no_commit(db, s):
    """POS-G-01 — returns the order; no commit, no rollback; summaries keep defaults.
    Rules: get_purchase_order G1, G2; TC6."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert not hasattr(result, "item_count")
    # Then 3
    assert PurchaseOrderResponse.model_validate(result).item_count == 0
    assert result.invoice_payment_status is None
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert X in db


def test_pos_g_02__w0_order_404_no_rollback(db, s):
    """POS-G-02 — a W0 order id → 404; no rollback, X still pending.
    Rules: get_purchase_order G1; TC6."""
    O0 = po(db, s, "0", "0")
    commit_point(db)
    X, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_purchase_order(db, po_id=O0.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert X in db


def test_pos_g_03__w2_order_404(db, s):
    """POS-G-03 — a W2 order id → 404.
    Rules: get_purchase_order G1."""
    po(db, s, "1")
    O9 = po(db, s, "9", "9")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_purchase_order(db, po_id=O9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)


def test_pos_g_04__voided_order_returned(db, s):
    """POS-G-04 — a voided order is returned.
    Rules: get_purchase_order G1."""
    O = po(db, s, "1", **VOIDED(s))
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.id == O.id
    assert result.voided is True


def test_pos_g_05__payment_status_from_invoice(db, s):
    """POS-G-05 — `invoice_payment_status` comes from the linked invoice.
    Rules: get_purchase_order G1; AP1."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    inv(db, s, O, linked=True, **FINALIZED, paid_amount=Decimal("100.00"), payment_status="partial")
    commit_point(db)

    result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.invoice_payment_status == "partial"


def test_pos_g_06__stale_stage_repaired_committed(db, s):
    """POS-G-06 — a stale stage is repaired and committed, with one performer-less event.
    Rules: get_purchase_order G2 (Q8 intended)."""
    O = po(db, s, "1", supplier_confirmed=True)
    commit_point(db)

    with spies(db) as (cm, _rb):
        result = svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result.current_status_id == s.SP1.id
    # Then 2
    assert cm.call_count == 1
    db.rollback()
    # Then 3
    assert reread(db, PurchaseOrder, O.id).current_status_id == s.SP1.id
    # Then 4
    upd = [e for e in EV(db, O.id) if e.event_type == "status_updated"]
    assert len(upd) == 1
    assert upd[0].performed_by is None


def test_pos_g_07__failing_repair_no_rollback(db, s):
    """POS-G-07 — a failing repair raises with no rollback.
    Rules: get_purchase_order G2."""
    db.delete(s.SP1)
    db.flush()
    O = po(db, s, "1", supplier_confirmed=True)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Purchase order stage status 'Planning' not found for this workspace"
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert cm.call_count == 0


# --------------------------------------------------------------------------- #
# mark_order_complete
# --------------------------------------------------------------------------- #


def test_pos_mc_01__completed_committed(db, s):
    """POS-MC-01 — a fully received order is completed and committed; nobody told.
    Rules: mark_order_complete MC1; TC1, TC2."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    V = inv(db, s, O, linked=True, **FINALIZED)
    commit_point(db)
    v_before = snap(db, V)

    result = svc.mark_order_complete(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == O.id
    db.rollback()
    # Then 3
    assert reread(db, PurchaseOrder, O.id).current_status_id == s.SC1.id
    # Then 4
    assert notes(db) == []
    # Then 5
    assert snap(db, V) == v_before


def test_pos_mc_02__not_fully_received_400(db, s):
    """POS-MC-02 — not fully received → 400, rolled back.
    Rules: mark_order_complete MC1; TC3."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    poline(db, s, O, 1, quantity_received=Decimal("9.00"))
    commit_point(db)
    o_before = snap(db, O)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.mark_order_complete(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "All line items must be fully received before marking the order complete"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, O) == o_before


def test_pos_mc_03__open_return_400(db, s):
    """POS-MC-03 — an open return → 400.
    Rules: mark_order_complete MC1."""
    O = po(db, s, "1", **READY, **PROJ, current_status_id=s.SR1.id)
    poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    ret(db, s, O, "1")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.mark_order_complete(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Complete all open returns before marking the order complete"


def test_pos_mc_04__failing_commit_not_complete(db, s):
    """POS-MC-04 — a failing commit leaves the order not complete.
    Rules: mark_order_complete MC1; TC4."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    commit_point(db)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.mark_order_complete(db, po_id=oid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrder, oid).current_status_id == s.SR1.id


# --------------------------------------------------------------------------- #
# list_purchase_orders
# --------------------------------------------------------------------------- #


def test_pos_lp_01__same_page_as_page_call(db, s):
    """POS-LP-01 — returns exactly the page for the same arguments.
    Rules: list_purchase_orders LP1."""
    po(db, s, "1")
    po(db, s, "2")
    po(db, s, "3")
    commit_point(db)

    result = svc.list_purchase_orders(db, workspace_id=s.W1.id, skip=0, limit=1000)

    # Then 1
    assert [o.id for o in result.items] == [o.id for o in svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=1000).items]
    # Then 2
    assert result.total == 3


def test_pos_lp_02__default_limit_100(db, s):
    """POS-LP-02 — the default limit is 100.
    Rules: list_purchase_orders LP1."""
    po_many(db, s, 101)
    commit_point(db)

    result = svc.list_purchase_orders(db, workspace_id=s.W1.id)

    # Then 1
    assert result.limit == 100
    # Then 2
    assert len(result.items) == 100
    # Then 3
    assert result.total == 101
    assert result.has_more is True


def test_pos_lp_03__unknown_filter_typeerror(db, s):
    """POS-LP-03 — an unknown keyword filter raises TypeError.
    Rules: list_purchase_orders LP1."""
    po(db, s, "1")
    commit_point(db)

    # Then 1
    with pytest.raises(TypeError):
        svc.list_purchase_orders(db, workspace_id=s.W1.id, colour="red")


def test_pos_lp_04__read_no_commit(db, s):
    """POS-LP-04 — a read: no commit, no rollback.
    Rules: list_purchase_orders LP1; TC6."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_purchase_orders(db, workspace_id=s.W1.id, skip=0, limit=1000)

    # Then 1
    assert result.total == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# _hub_filter_kwargs
# --------------------------------------------------------------------------- #


def test_pos_hf_01__defaults_eleven_keys():
    """POS-HF-01 — defaults give exactly the eleven keys.
    Rules: _hub_filter_kwargs HF1."""
    result = svc._hub_filter_kwargs()

    # Then 1
    assert result == {"account_id": None, "invoice_id": None, "date_from": None, "date_to": None, "status_ids": None, "factory_id": None, "destination_type": None, "invoice_filter": None, "search": None, "exclude_complete": False, "exclude_voided": False}


def test_pos_hf_02__values_pass_unchanged():
    """POS-HF-02 — values pass unchanged.
    Rules: _hub_filter_kwargs HF1."""
    result = svc._hub_filter_kwargs(account_id=5, invoice_id=6, date_from=date(2026, 9, 1), date_to=date(2026, 9, 30), status_ids=[1, 2], factory_id=7, destination_type="machine", invoice_filter="missing", search="Bear", exclude_complete=True, exclude_voided=True)

    # Then 1
    assert result == {"account_id": 5, "invoice_id": 6, "date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30), "status_ids": [1, 2], "factory_id": 7, "destination_type": "machine", "invoice_filter": "missing", "search": "Bear", "exclude_complete": True, "exclude_voided": True}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("", None, id="POS-HF-03"),
        pytest.param("all", None, id="POS-HF-04"),
        pytest.param("All", "All", id="POS-HF-05"),
        pytest.param(" all", " all", id="POS-HF-06"),
    ],
)
def test_pos_hf_03_06__invoice_filter_normalised(value, expected):
    """POS-HF-03 … POS-HF-06 — `invoice_filter` "" / "all" → None; "All" / " all" kept.
    Rules: _hub_filter_kwargs HF1."""
    result = svc._hub_filter_kwargs(invoice_filter=value)

    # Then 1
    if expected is None:
        assert result["invoice_filter"] is None
    else:
        assert result["invoice_filter"] == expected


# --------------------------------------------------------------------------- #
# _prepare_listed_orders
# --------------------------------------------------------------------------- #


def test_pos_pl_01__attaches_status_and_summaries(db, s):
    """POS-PL-01 — attaches payment status and summaries; same list, same order.
    Rules: _prepare_listed_orders PL1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2", **READY)
    poline(db, s, O2, 1)
    inv(db, s, O2, linked=True, **FINALIZED, payment_status="partial", paid_amount=Decimal("100.00"))
    commit_point(db)
    orders = [O2, O1]

    result = svc._prepare_listed_orders(db, workspace_id=s.W1.id, orders=orders)

    # Then 1
    assert [o.id for o in result] == [O2.id, O1.id]
    # Then 2
    assert result[0].invoice_payment_status == "partial"
    assert result[0].item_count == 1
    # Then 3
    assert result[1].invoice_payment_status is None
    assert result[1].item_count == 0


@xfail(3178)
def test_pos_pl_02__every_stale_order_repaired(db, s):
    """POS-PL-02 — every stale order on the page is repaired.
    Rules: _prepare_listed_orders PL2 [BUG-3178]."""
    O1 = po(db, s, "1", supplier_confirmed=True)
    O2 = po(db, s, "2", supplier_confirmed=True)
    O3 = po(db, s, "3", supplier_confirmed=True)
    commit_point(db)

    result = svc._prepare_listed_orders(db, workspace_id=s.W1.id, orders=[O1, O2, O3])

    # Then 1
    assert [o.id for o in result] == [O1.id, O2.id, O3.id]
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrder, O2.id).current_status_id == s.SP1.id
    # Then 3
    assert reread(db, PurchaseOrder, O3.id).current_status_id == s.SP1.id


def test_pos_pl_03__first_stale_repaired_one_commit(db, s):
    """POS-PL-03 — the first stale order is repaired and one commit is made.
    Rules: _prepare_listed_orders PL2 (part that holds today), PL3."""
    O1 = po(db, s, "1", supplier_confirmed=True)
    O2 = po(db, s, "2", supplier_confirmed=True)
    commit_point(db)

    with spies(db) as (cm, _rb):
        svc._prepare_listed_orders(db, workspace_id=s.W1.id, orders=[O1, O2])

    # Then 1
    assert cm.call_count == 1
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrder, O1.id).current_status_id == s.SP1.id


def test_pos_pl_04__nothing_stale_no_commit(db, s):
    """POS-PL-04 — nothing stale → no commit.
    Rules: _prepare_listed_orders PL3."""
    O1 = po(db, s, "1")
    commit_point(db)

    with spies(db) as (cm, rb):
        svc._prepare_listed_orders(db, workspace_id=s.W1.id, orders=[O1])

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0


def test_pos_pl_05__empty_list_writes_nothing(db, s):
    """POS-PL-05 — an empty list writes nothing.
    Rules: _prepare_listed_orders PL3."""
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, _rb):
        result = svc._prepare_listed_orders(db, workspace_id=s.W1.id, orders=[])

    # Then 1
    assert result == []
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert X in db


# --------------------------------------------------------------------------- #
# list_purchase_orders_page
# --------------------------------------------------------------------------- #


def test_pos_pg_01__has_more_while_rows_follow(db, s):
    """POS-PG-01 — `has_more` true while more rows follow; skip and limit echoed.
    Rules: list_purchase_orders_page PG1, PG2."""
    po(db, s, "1")
    po(db, s, "2")
    po(db, s, "3")
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=2)

    # Then 1
    assert result.total == 3
    assert len(result.items) == 2
    # Then 2
    assert result.skip == 0
    assert result.limit == 2
    assert result.has_more is True


def test_pos_pg_02__last_page(db, s):
    """POS-PG-02 — the last page: `has_more` false.
    Rules: list_purchase_orders_page PG2."""
    po(db, s, "1")
    po(db, s, "2")
    po(db, s, "3")
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=2, limit=2)

    # Then 1
    assert len(result.items) == 1
    assert result.total == 3
    assert result.has_more is False


def test_pos_pg_03__skip_past_end(db, s):
    """POS-PG-03 — skip past the end: empty, `has_more` false.
    Rules: list_purchase_orders_page PG2."""
    po(db, s, "1")
    po(db, s, "2")
    po(db, s, "3")
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=5, limit=2)

    # Then 1
    assert result.items == []
    assert result.total == 3
    assert result.has_more is False


def test_pos_pg_04__no_orders_total_zero(db, s):
    """POS-PG-04 — no orders: total 0.
    Rules: list_purchase_orders_page PG2."""
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=50)

    # Then 1
    assert result.total == 0
    assert result.items == []
    assert result.has_more is False


def test_pos_pg_05__foreign_orders_not_listed(db, s):
    """POS-PG-05 — W0 and W2 orders are neither listed nor counted.
    Rules: list_purchase_orders_page PG1."""
    po(db, s, "0", "0")
    O1 = po(db, s, "1")
    po(db, s, "9", "9")
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=1000)

    # Then 1
    assert [o.id for o in result.items] == [O1.id]
    assert result.total == 1


def test_pos_pg_06__invoice_filter_all_same(db, s):
    """POS-PG-06 — `invoice_filter "all"` lists the same as no filter.
    Rules: list_purchase_orders_page PG1; HF1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2", **READY)
    inv(db, s, O2, linked=True)
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=1000, invoice_filter="all")

    # Then 1
    assert sorted(o.id for o in result.items) == sorted([O1.id, O2.id])
    assert result.total == 2


def test_pos_pg_07__read_no_commit(db, s):
    """POS-PG-07 — a read with nothing stale: no commit, no rollback.
    Rules: list_purchase_orders_page PG1; TC6."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        svc.list_purchase_orders_page(db, workspace_id=s.W1.id, skip=0, limit=1000)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


def test_pos_pg_08__defaults_skip_0_limit_50(db, s):
    """POS-PG-08 — the defaults: skip 0, limit 50.
    Rules: list_purchase_orders_page PG2 (signature defaults)."""
    po_many(db, s, 51)
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert result.skip == 0
    assert result.limit == 50
    # Then 2
    assert result.total == 51
    assert len(result.items) == 50
    assert result.has_more is True


def test_pos_pg_09__closed_and_voided_listed(db, s):
    """POS-PG-09 — no filter given: fully closed and voided orders are listed.
    Rules: list_purchase_orders_page PG1; _hub_filter_kwargs HF1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2", **COMPLETE(s), paid=True)
    O3 = po(db, s, "3", **VOIDED(s))
    commit_point(db)

    result = svc.list_purchase_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total == 3
    # Then 2
    assert {o.id for o in result.items} == {O1.id, O2.id, O3.id}


# --------------------------------------------------------------------------- #
# get_purchase_order_hub_stats
# --------------------------------------------------------------------------- #


# [claude] POS-HS-01
def test_pos_hs_01__figures_are_the_daos(db, s):
    """POS-HS-01 — the five figures are the DAO's, in order.
    Rules: get_purchase_order_hub_stats HS1."""
    po(db, s, "1")
    po(db, s, "2", **COMPLETE(s), total_amount=Decimal("700.00"))
    commit_point(db)

    result = svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert (result.total_count, result.total_value, result.open_count, result.open_value, result.not_invoiced_count) == tuple(
        mgr.purchase_order_hub_stats(db, s.W1.id, **svc._hub_filter_kwargs())
    )


def test_pos_hs_02__at_most_ten_recent(db, s):
    """POS-HS-02 — at most 10 recent orders.
    Rules: get_purchase_order_hub_stats HS2."""
    po_many(db, s, 11)
    commit_point(db)

    result = svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.recent_orders) == 10


def test_pos_hs_03__empty_workspace(db, s):
    """POS-HS-03 — an empty workspace: zero counts and empty lists.
    Rules: get_purchase_order_hub_stats HS1, HS3."""
    commit_point(db)

    result = svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total_count == 0
    assert result.recent_orders == []
    # Then 2
    assert result.pending_planning == []
    assert result.missing_invoice == []
    assert result.oldest_drafts == []


def test_pos_hs_04__foreign_orders_not_counted(db, s):
    """POS-HS-04 — W0 and W2 orders are not counted.
    Rules: get_purchase_order_hub_stats HS1."""
    po(db, s, "0", "0")
    po(db, s, "1")
    po(db, s, "9", "9")
    commit_point(db)

    result = svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total_count == 1
    assert len(result.recent_orders) == 1


def test_pos_hs_05__read_no_commit(db, s):
    """POS-HS-05 — a read: no commit, no rollback.
    Rules: get_purchase_order_hub_stats HS3; TC6."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


def test_pos_hs_06__closed_and_voided_counted(db, s):
    """POS-HS-06 — no filter given: fully closed and voided orders are counted.
    Rules: get_purchase_order_hub_stats HS1."""
    po(db, s, "1")
    po(db, s, "2", **COMPLETE(s), paid=True)
    po(db, s, "3", **VOIDED(s))
    commit_point(db)

    result = svc.get_purchase_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert result.total_count == 3


# --------------------------------------------------------------------------- #
# _attach_invoice_payment_status
# --------------------------------------------------------------------------- #


def test_pos_ap_01__status_per_order_one_query(db, s):
    """POS-AP-01 — each order gets its invoice's payment status; none → None; one query.
    Rules: _attach_invoice_payment_status AP1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2")
    O3 = po(db, s, "3")
    inv(db, s, O1, linked=True, **FINALIZED, paid_amount=Decimal("100.00"), payment_status="partial")
    inv(db, s, O2, linked=True, **FINALIZED, paid_amount=Decimal("5000.00"), payment_status="paid")
    commit_point(db)
    for o in (O1, O2, O3):
        db.refresh(o)

    with Recorder(db) as rec:
        svc._attach_invoice_payment_status(db, orders=[O1, O2, O3])

    # Then 1
    assert [O1.invoice_payment_status, O2.invoice_payment_status, O3.invoice_payment_status] == ["partial", "paid", None]
    # Then 2
    assert len(rec.selects_from("account_invoices")) == 1


def test_pos_ap_02__voided_invoice_status_shown(db, s):
    """POS-AP-02 — a voided invoice's status is shown.
    Rules: _attach_invoice_payment_status AP1."""
    O1 = po(db, s, "1")
    inv(db, s, O1, linked=True, **VOIDED_INV, payment_status="unpaid")
    commit_point(db)

    svc._attach_invoice_payment_status(db, orders=[O1])

    # Then 1
    assert O1.invoice_payment_status == "unpaid"


def test_pos_ap_03__no_invoices_all_none(db, s):
    """POS-AP-03 — no order has an invoice → all None.
    Rules: _attach_invoice_payment_status AP1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2")
    commit_point(db)

    svc._attach_invoice_payment_status(db, orders=[O1, O2])

    # Then 1
    assert O1.invoice_payment_status is None
    assert O2.invoice_payment_status is None


@xfail(3164)
def test_pos_ap_04__w2_invoice_not_read(db, s):
    """POS-AP-04 — a W2 invoice linked to a W1 order is not read.
    Rules: _attach_invoice_payment_status AP2 [BUG-3164]; HR-16."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2")
    inv(db, s, O1, linked=True, **FINALIZED, payment_status="partial", paid_amount=Decimal("100.00"))
    inv(db, s, O2, k="9", linked=True, **FINALIZED, paid_amount=Decimal("5000.00"), payment_status="paid")
    commit_point(db)

    svc._attach_invoice_payment_status(db, orders=[O1, O2])

    # Then 1
    assert O1.invoice_payment_status == "partial"
    # Then 2
    assert O2.invoice_payment_status is None


@xfail(3164)
def test_pos_ap_05__w0_invoice_not_read(db, s):
    """POS-AP-05 — a W0 invoice linked to a W1 order is not read.
    Rules: _attach_invoice_payment_status AP2 [BUG-3164]; HR-16."""
    po(db, s, "0", "0")
    O1 = po(db, s, "1")
    inv(db, s, O1, k="0", linked=True, **FINALIZED, paid_amount=Decimal("5000.00"), payment_status="paid")
    commit_point(db)

    svc._attach_invoice_payment_status(db, orders=[O1])

    # Then 1
    assert O1.invoice_payment_status is None


# --------------------------------------------------------------------------- #
# _attach_item_summaries
# --------------------------------------------------------------------------- #


def test_pos_is_01__counts_totals_preview(db, s):
    """POS-IS-01 — counts, totals and name preview per order.
    Rules: _attach_item_summaries IS1."""
    O1 = po(db, s, "1")
    O2 = po(db, s, "2")
    poline(db, s, O1, 1, quantity_received=Decimal("4.00"))
    poline(db, s, O1, 2, item_id=s.I1b.id, quantity_ordered=Decimal("5.00"), line_subtotal=Decimal("2500.00"))
    commit_point(db)

    svc._attach_item_summaries(db, workspace_id=s.W1.id, orders=[O1, O2])

    # Then 1
    assert O1.item_count == 2
    assert O1.quantity_ordered_total == Decimal("15.00")
    assert O1.quantity_received_total == Decimal("4.00")
    # Then 2
    assert sorted(O1.item_names_preview) == ["Bearing", "Cement"]
    # Then 3
    assert O2.item_count == 0
    assert O2.quantity_ordered_total == Decimal(0)
    assert O2.quantity_received_total == Decimal(0)
    assert O2.item_names_preview == []


def test_pos_is_02__foreign_line_not_counted(db, s):
    """POS-IS-02 — a W2 line pointing at a W1 order is not counted.
    Rules: _attach_item_summaries IS1; HR-16."""
    O1 = po(db, s, "1")
    poline(db, s, O1, 1)
    poline(db, s, O1, 2, workspace_id=s.W2.id, item_id=s.I9.id)
    commit_point(db)

    svc._attach_item_summaries(db, workspace_id=s.W1.id, orders=[O1])

    # Then 1
    assert O1.item_count == 1
    assert O1.quantity_ordered_total == Decimal("10.00")


@xfail(2641)
def test_pos_is_03__refunded_total_attached(db, s):
    """POS-IS-03 — the refunded total is attached.
    Rules: _attach_item_summaries IS2 [BUG-2641]."""
    O1 = po(db, s, "1")
    poline(db, s, O1, 1, quantity_received=Decimal("7.00"), quantity_returned=Decimal("3.00"), quantity_refunded=Decimal("3.00"))
    commit_point(db)

    svc._attach_item_summaries(db, workspace_id=s.W1.id, orders=[O1])

    # Then 1
    assert O1.quantity_received_total == Decimal("7.00")
    # Then 2
    assert O1.quantity_refunded_total == Decimal("3.00")


# --------------------------------------------------------------------------- #
# create_receive_event
# --------------------------------------------------------------------------- #


def rcvbase(db, s, o_but=None, l_but=None, v_but=None):
    """Section convention RCVBASE: O ready at Receiving, L = poline(O, 1), V finalized and linked.
    The dicts are the columns after "but" for O, L and V."""
    O = po(db, s, "1", **{**READY, "current_status_id": s.SR1.id, **(o_but or {})})
    L = poline(db, s, O, 1, **(l_but or {}))
    V = inv(db, s, O, linked=True, **{**FINALIZED, **(v_but or {})})
    return O, L, V


def RE(db, s, O, req):
    """Section convention RE(req)."""
    return svc.create_receive_event(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id, data=req)


def event_of(db, oid, typ):
    """"the `typ` event of O": the single purchase_order_events row of that type."""
    rows = [e for e in EV(db, oid) if e.event_type == typ]
    assert len(rows) == 1
    return rows[0]


def test_pos_re_01__receive_recorded_posted_committed(db, s):
    """POS-RE-01 — a receive batch is recorded, stock posted, committed.
    Rules: create_receive_event RE6, RE8, RE12; TC1."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5")))

    # Then 1
    assert result.event_type == "receive"
    assert len(result.items) == 1
    assert result.items[0].quantity_delta == Decimal("5")
    db.rollback()
    # Then 2
    evs = rows_where(db, PoReceiveEvent, PoReceiveEvent.purchase_order_id == O.id)
    assert len(evs) == 1
    assert evs[0].performed_by == s.U2.id
    assert evs[0].workspace_id == s.W1.id
    assert evs[0].id == result.id
    # Then 3
    items = rows_where(db, PoReceiveEventItem, PoReceiveEventItem.receive_event_id == result.id)
    assert len(items) == 1
    assert items[0].quantity_delta == Decimal("5.00")
    # Then 4
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("5.00")
    # Then 5
    assert len(RCVLEDGER(db, s)) == 1
    assert RCVLEDGER(db, s)[0].transaction_type == "purchase_order"
    # Then 6
    assert "received" in types(db, O.id)


def test_pos_re_02__missing_order_404_before_try(db, s):
    """POS-RE-02 — a missing order → 404 before the `try`: no rollback, X still pending.
    Rules: create_receive_event RE1; Transaction contract (refusals before the `try`)."""
    _O, L, _V = rcvbase(db, s)
    before = commit_point(db)
    X, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_receive_event(db, po_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id, data=RCV((L, "5")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db
    # Then 6
    assert counts(db) == before


def test_pos_re_03__w0_order_404(db, s):
    """POS-RE-03 — a W0 order id → 404.
    Rules: create_receive_event RE1."""
    O0 = po(db, s, "0", "0", **READY)
    _O, L, _V = rcvbase(db, s)
    commit_point(db)
    l_before = snap(db, L)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_receive_event(db, po_id=O0.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RCV((L, "5")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)
    # Then 4
    assert snap(db, L) == l_before


def test_pos_re_04__w2_order_404(db, s):
    """POS-RE-04 — a W2 order id → 404.
    Rules: create_receive_event RE1."""
    rcvbase(db, s)
    O9 = po(db, s, "9", "9", **READY)
    L9 = poline(db, s, O9, 1)
    commit_point(db)
    l9_before = snap(db, L9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_receive_event(db, po_id=O9.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RCV((L9, "5")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert snap(db, L9) == l9_before


@xfail(3162)
def test_pos_re_05__order_row_locked_first(db, s):
    """POS-RE-05 — the order row is locked before the first state check.
    Rules: create_receive_event RE1 [BUG-3162]; HR-10."""
    O, L, _V = rcvbase(db, s)
    oid, lid, w1_id, u2_id = O.id, L.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.create_receive_event(db, po_id=oid, workspace_id=w1_id, user_id=u2_id, data=PoReceiveEventCreate(event_type="receive", items=[{"po_item_id": lid, "quantity_delta": Decimal("5")}]))

    # Then 1
    assert result.event_type == "receive"
    # Then 2
    assert rec.exact_lock_of("purchase_orders")
    # Then 3
    assert rec.before("purchase_orders", "account_invoices")
    # Then 4
    assert rec.before("purchase_orders", "purchase_order_items")


def test_pos_re_06__voided_order_400(db, s):
    """POS-RE-06 — a voided order → 400.
    Rules: create_receive_event RE2."""
    O, L, _V = rcvbase(db, s, o_but=VOIDED(s))
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot receive against a voided purchase order"
    # Then 4
    assert counts(db) == before


def test_pos_re_07__completed_order_400(db, s):
    """POS-RE-07 — a completed order → 400.
    Rules: create_receive_event RE2."""
    O, L, _V = rcvbase(db, s, o_but=COMPLETE(s))
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot receive against a completed purchase order"
    # Then 4
    assert counts(db) == before


def test_pos_re_08__no_invoice_400(db, s):
    """POS-RE-08 — no invoice linked → 400 finalize first.
    Rules: create_receive_event RE3."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == FINALIZE
    # Then 4
    assert counts(db) == before


def test_pos_re_09__draft_invoice_400(db, s):
    """POS-RE-09 — a draft invoice → 400 finalize first.
    Rules: create_receive_event RE3."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    inv(db, s, O, linked=True)
    commit_point(db)
    l_before = snap(db, L)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "5")))
    # Then 2
    assert exc.value.detail == FINALIZE
    # Then 3
    assert snap(db, L) == l_before


def test_pos_re_10__w2_finalized_invoice_400(db, s):
    """POS-RE-10 — a finalized invoice of W2 linked → 400 finalize first.
    Rules: create_receive_event RE3; HR-16."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    V9 = inv(db, s, O, k="9", linked=True, **FINALIZED)
    commit_point(db)
    v9_before = snap(db, V9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "5")))
    # Then 2
    assert exc.value.detail == FINALIZE
    # Then 3
    assert snap(db, V9) == v9_before


def test_pos_re_11__locked_invoice_passes(db, s):
    """POS-RE-11 — a `locked` invoice passes the check.
    Rules: create_receive_event RE3."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    inv(db, s, O, linked=True, **LOCKED_INV)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5")))

    # Then 1
    assert result.event_type == "receive"
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("5.00")


def test_pos_re_12__line_of_other_order_400(db, s):
    """POS-RE-12 — a line of another order → 400.
    Rules: create_receive_event RE4."""
    O, _L, _V = rcvbase(db, s)
    O2 = po(db, s, "2")
    L2 = poline(db, s, O2, 1)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L2, "5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item {L2.id} does not belong to this PO"
    # Then 4
    assert counts(db) == before


def test_pos_re_13__w2_line_400(db, s):
    """POS-RE-13 — a W2 line → 400.
    Rules: create_receive_event RE4; HR-16."""
    O, _L, _V = rcvbase(db, s)
    O9 = po(db, s, "9", "9")
    L9 = poline(db, s, O9, 1)
    commit_point(db)
    l9_before = snap(db, L9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L9, "5")))
    # Then 2
    assert exc.value.detail == f"Item {L9.id} does not belong to this PO"
    # Then 3
    assert snap(db, L9) == l9_before


def test_pos_re_14__correction_below_zero_400(db, s):
    """POS-RE-14 — a correction going below 0 → 400.
    Rules: create_receive_event RE5."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("3.00")})
    commit_point(db)
    l_before = snap(db, L)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, COR((L, "-4"), note="Miscount"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Resulting received quantity for item {L.id} cannot be negative"
    # Then 4
    assert snap(db, L) == l_before


def test_pos_re_15__exactly_zero_after_correction(db, s):
    """POS-RE-15 — exactly 0 after a correction passes.
    Rules: create_receive_event RE5."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("3.00")})
    commit_point(db)

    RE(db, s, O, COR((L, "-3"), note="Miscount"))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("0.00")


def test_pos_re_16__above_ordered_minus_refunded_400(db, s):
    """POS-RE-16 — above ordered − refunded → 400.
    Rules: create_receive_event RE5."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("7.00"), "quantity_refunded": Decimal("2.00"), "quantity_returned": Decimal("2.00")})
    commit_point(db)
    l_before = snap(db, L)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "2")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Resulting received quantity for item {L.id} exceeds ordered quantity"
    # Then 4
    assert snap(db, L) == l_before


def test_pos_re_17__exactly_ordered_minus_refunded(db, s):
    """POS-RE-17 — exactly ordered − refunded passes.
    Rules: create_receive_event RE5."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("7.00"), "quantity_refunded": Decimal("2.00"), "quantity_returned": Decimal("2.00")})
    commit_point(db)

    RE(db, s, O, RCV((L, "1")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("8.00")


@xfail(3171)
def test_pos_re_18__same_line_twice_running_total(db, s):
    """POS-RE-18 — the same line twice is checked on the running total.
    Rules: create_receive_event RE5 [BUG-3171]."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RE(db, s, O, RCV((L, "6"), (L, "6")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Resulting received quantity for item {L.id} exceeds ordered quantity"
    db.rollback()
    # Then 4
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("0.00")
    # Then 5
    assert count_where(db, PoReceiveEvent, PoReceiveEvent.purchase_order_id == O.id) == 0


def test_pos_re_19__same_line_twice_within_limit(db, s):
    """POS-RE-19 — the same line twice within the limit is accepted and summed.
    Rules: create_receive_event RE5, RE6 (part that holds before and after BUG-3171)."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "3"), (L, "3")))

    # Then 1
    assert len(result.items) == 2
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("6.00")


def test_pos_re_20__posting_failure_rolls_back(db, s):
    """POS-RE-20 — a posting failure after the writes rolls everything back.
    Rules: create_receive_event RE8, RE12; TC3."""
    O, L, _V = rcvbase(db, s)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            RE(db, s, O, RCV((L, "2.5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Line 1 has a fractional quantity delta; inventory requires whole units"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("0.00")
    # Then 8
    assert counts(db) == before


def test_pos_re_21__texts_stored_trimmed(db, s):
    """POS-RE-21 — texts are stored trimmed.
    Rules: create_receive_event RE7 (part that holds before and after BUG-3180)."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), rcc=" RCC-77 ", received_by=" Karim "))

    db.rollback()
    # Then 1
    e = reread(db, PoReceiveEvent, result.id)
    assert e.rcc == "RCC-77"
    assert e.received_by == "Karim"


@xfail(3180)
def test_pos_re_22__blank_text_stored_null(db, s):
    """POS-RE-22 — a blank text is stored as NULL.
    Rules: create_receive_event RE7 [BUG-3180]."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), rcc="   ", received_by="Karim"))

    db.rollback()
    # Then 1
    assert reread(db, PoReceiveEvent, result.id).received_by == "Karim"
    # Then 2
    assert reread(db, PoReceiveEvent, result.id).rcc is None


def test_pos_re_23__project_order_no_stock(db, s):
    """POS-RE-23 — a project order moves no stock and logs no posting.
    Rules: create_receive_event RE8."""
    O, L, _V = rcvbase(db, s, o_but=PROJ)
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert RCVLEDGER(db, s) == []
    # Then 2
    assert "inventory_posted" not in types(db, O.id)
    # Then 3
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("5.00")


def test_pos_re_24__storage_posting_logged(db, s):
    """POS-RE-24 — a storage posting logs `inventory_posted` with its metadata.
    Rules: create_receive_event RE8."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    e = event_of(db, O.id, "inventory_posted")
    assert e.description == "1 receive line(s) posted to factory storage"
    # Then 2
    assert e.metadata_json == {"receive_event_id": result.id, "lines_posted": 1, "destination_type": "storage", "destination_id": s.F1.id}


# [claude] POS-RE-25
def test_pos_re_25__machine_posting_text(db, s):
    """POS-RE-25 — a machine posting says "machine inventory".
    Rules: create_receive_event RE8."""
    from app.models.machine import Machine

    M1 = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Press 4", is_deleted=False))
    O, L, _V = rcvbase(db, s, o_but={"destination_type": "machine", "destination_id": M1.id})
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert event_of(db, O.id, "inventory_posted").description == "1 receive line(s) posted to machine inventory"


def test_pos_re_26__receive_log_with_texts(db, s):
    """POS-RE-26 — receive log text and metadata with RCC and "received by".
    Rules: create_receive_event RE9."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), rcc="RCC-77", received_by="Karim"))

    db.rollback()
    # Then 1
    e = event_of(db, O.id, "received")
    assert e.description == "Received 5 unit(s) across 1 item(s). RCC: RCC-77. Received by: Karim."
    assert e.performed_by == s.U2.id
    # Then 2
    assert e.metadata_json == {"receive_event_id": result.id, "rcc": "RCC-77", "received_by": "Karim"}


def test_pos_re_27__receive_log_without_texts(db, s):
    """POS-RE-27 — receive log without the optional texts.
    Rules: create_receive_event RE9."""
    O, L, _V = rcvbase(db, s, o_but=PROJ)
    L2 = poline(db, s, O, 2, item_id=s.I1b.id)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), (L2, "2.50")))

    db.rollback()
    # Then 1
    e = event_of(db, O.id, "received")
    assert e.description == "Received 7.50 unit(s) across 2 item(s)."
    # Then 2
    assert e.metadata_json == {"receive_event_id": result.id}


def test_pos_re_28__correction_log_signed_with_note(db, s):
    """POS-RE-28 — correction log is signed and carries the note.
    Rules: create_receive_event RE9."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("5.00")})
    commit_point(db)

    result = RE(db, s, O, COR((L, "-2"), note="Miscount"))

    db.rollback()
    # Then 1
    e = event_of(db, O.id, "quantity_correction")
    assert e.description == "Quantity correction: -2 unit(s) across 1 item(s). Note: Miscount"
    # Then 2
    assert e.metadata_json == {"receive_event_id": result.id, "correction_note": "Miscount"}
    # Then 3
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("3.00")


def test_pos_re_29__zero_correction_plus_zero(db, s):
    """POS-RE-29 — a zero correction prints `+0`.
    Rules: create_receive_event RE9."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("5.00")})
    commit_point(db)

    RE(db, s, O, COR((L, "0"), note="Recount"))

    db.rollback()
    # Then 1
    assert event_of(db, O.id, "quantity_correction").description == "Quantity correction: +0 unit(s) across 1 item(s). Note: Recount"


@xfail(3180)
def test_pos_re_30__log_uses_trimmed_texts(db, s):
    """POS-RE-30 — the log uses the trimmed texts.
    Rules: create_receive_event RE9 [BUG-3180]."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), rcc=" RCC-77 "))

    # Then 1
    assert result.event_type == "receive"
    db.rollback()
    # Then 2
    e = event_of(db, O.id, "received")
    assert e.description == "Received 5 unit(s) across 1 item(s). RCC: RCC-77."
    # Then 3
    assert e.metadata_json == {"receive_event_id": result.id, "rcc": "RCC-77"}


@xfail(3180)
def test_pos_re_31__blank_text_left_out_of_log(db, s):
    """POS-RE-31 — a blank text is left out of the log.
    Rules: create_receive_event RE9 [BUG-3180]."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5"), rcc="   "))

    # Then 1
    assert result.event_type == "receive"
    db.rollback()
    # Then 2
    e = event_of(db, O.id, "received")
    assert e.description == "Received 5 unit(s) across 1 item(s)."
    # Then 3
    assert "rcc" not in e.metadata_json


@xfail(3177)
def test_pos_re_32__first_receipt_marks_receiving_started(db, s):
    """POS-RE-32 — the first receipt marks the invoice "receiving started".
    Rules: create_receive_event RE10 [BUG-3177]."""
    O, L, V = rcvbase(db, s)
    commit_point(db)

    result = RE(db, s, O, RCV((L, "5")))

    # Then 1
    assert result.event_type == "receive"
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, V.id).receiving_started is True
    # Then 3
    assert itypes(db, V.id).count("receiving_started_set") == 1


def test_pos_re_33__already_receiving_started(db, s):
    """POS-RE-33 — already "receiving started": nothing more on the invoice.
    Rules: create_receive_event RE10 (side that holds today and after BUG-3177)."""
    O, L, V = rcvbase(db, s, v_but={"receiving_started": True})
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert reread(db, AccountInvoice, V.id).receiving_started is True
    # Then 2
    assert "receiving_started_set" not in itypes(db, V.id)


def test_pos_re_34__completing_batch_logs_all_received(db, s):
    """POS-RE-34 — the batch that completes every line logs `all_received`.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s, l_but={"quantity_received": Decimal("5.00")})
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert [e.description for e in EV(db, O.id) if e.event_type == "all_received"] == ["All items received"]


def test_pos_re_35__all_received_logged_once(db, s):
    """POS-RE-35 — `all_received` is logged once per order.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s, o_but=PROJ, l_but={"quantity_received": Decimal("7.00")})
    ev(db, s, O, T0, "all_received")
    commit_point(db)

    RE(db, s, O, RCV((L, "3")))

    db.rollback()
    # Then 1
    assert types(db, O.id).count("all_received") == 1


def test_pos_re_36__not_every_line_done(db, s):
    """POS-RE-36 — not every line done → no `all_received`.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s)
    poline(db, s, O, 2, item_id=s.I1b.id)
    commit_point(db)

    RE(db, s, O, RCV((L, "10")))

    db.rollback()
    # Then 1
    assert "all_received" not in types(db, O.id)


def test_pos_re_37__stage_not_repaired(db, s):
    """POS-RE-37 — the stage is not repaired by a receipt.
    Rules: create_receive_event RE12."""
    O, L, _V = rcvbase(db, s, o_but={"current_status_id": s.SP1.id})
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrder, O.id).current_status_id == s.SP1.id


def test_pos_re_38__failing_commit_saves_nothing(db, s):
    """POS-RE-38 — a failing commit saves nothing.
    Rules: create_receive_event RE12; TC4."""
    O, L, _V = rcvbase(db, s)
    before = commit_point(db)
    req = RCV((L, "5"))
    oid, lid, w1_id, u2_id = O.id, L.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_receive_event(db, po_id=oid, workspace_id=w1_id, user_id=u2_id, data=req)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderItem, lid).quantity_received == Decimal("0.00")
    # Then 4
    assert counts(db) == before


def test_pos_re_39__schema_empty_items_refused():
    """POS-RE-39 — schema: an empty items list is refused.
    Rules: create_receive_event Inputs."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PoReceiveEventCreate(event_type="receive", items=[])
    assert "At least one item must have a quantity delta" in str(exc.value)


def test_pos_re_40__schema_blank_correction_note_refused():
    """POS-RE-40 — schema: a correction with a blank note is refused.
    Rules: create_receive_event Inputs."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PoReceiveEventCreate(event_type="correction", correction_note="   ", items=[{"po_item_id": 1, "quantity_delta": Decimal("-1")}])
    assert "correction_note is required for correction events" in str(exc.value)


def test_pos_re_41__schema_zero_receive_delta_refused():
    """POS-RE-41 — schema: a receive with a zero delta is refused.
    Rules: create_receive_event Inputs."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PoReceiveEventCreate(event_type="receive", items=[{"po_item_id": 1, "quantity_delta": Decimal("0")}])
    assert "All quantity deltas must be positive for a receive event" in str(exc.value)


def test_pos_re_42__schema_unknown_event_type_refused():
    """POS-RE-42 — schema: an unknown event type is refused.
    Rules: create_receive_event Inputs."""
    # Then 1
    with pytest.raises(ValidationError):
        PoReceiveEventCreate(event_type="return", items=[{"po_item_id": 1, "quantity_delta": Decimal("1")}])


def test_pos_re_43__refunded_completes_line(db, s):
    """POS-RE-43 — refunded quantity completes a line for `all_received`.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s, l_but={"quantity_refunded": Decimal("4.00")})
    commit_point(db)

    RE(db, s, O, RCV((L, "6")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("6.00")
    # Then 2
    assert [e.description for e in EV(db, O.id) if e.event_type == "all_received"] == ["All items received"]


def test_pos_re_44__one_unit_short(db, s):
    """POS-RE-44 — a line one unit short → no `all_received`.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s)
    commit_point(db)

    RE(db, s, O, RCV((L, "9")))

    db.rollback()
    # Then 1
    line = reread(db, PurchaseOrderItem, L.id)
    assert line.quantity_received == Decimal("9.00")
    assert line.quantity_refunded == Decimal("0.00")
    # Then 2
    assert "all_received" not in types(db, O.id)


def test_pos_re_45__other_line_at_zero(db, s):
    """POS-RE-45 — another line still at 0 of 1 ordered → no `all_received`.
    Rules: create_receive_event RE11."""
    O, L, _V = rcvbase(db, s, l_but={"quantity_received": Decimal("5.00")})
    L2 = poline(db, s, O, 2, item_id=s.I1b.id, quantity_ordered=Decimal("1.00"), line_subtotal=Decimal("500.00"))
    commit_point(db)

    RE(db, s, O, RCV((L, "5")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("10.00")
    assert reread(db, PurchaseOrderItem, L2.id).quantity_received == Decimal("0.00")
    # Then 2
    assert "all_received" not in types(db, O.id)


# --------------------------------------------------------------------------- #
# list_receive_events
# --------------------------------------------------------------------------- #


def rev(db, s, O, t, **but):
    """Section convention rev(O, t)."""
    fields = {
        "workspace_id": O.workspace_id,
        "purchase_order_id": O.id,
        "event_type": "receive",
        "performed_by": s.U1.id,
        "created_at": t,
    }
    fields.update(but)
    return _add(db, PoReceiveEvent(**fields))


def revi(db, E, L, d):
    """Section convention revi(E, L, d)."""
    return _add(db, PoReceiveEventItem(receive_event_id=E.id, po_item_id=L.id, quantity_delta=Decimal(d)))


def _order_by_tail(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


def test_pos_lr_01__missing_order_404(db, s):
    """POS-LR-01 — a missing order → 404; no rollback, X still pending.
    Rules: list_receive_events LR1; TC6."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.list_receive_events(db, po_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_pos_lr_02__newest_first(db, s):
    """POS-LR-02 — newest first; no commit, no rollback.
    Rules: list_receive_events LR2; TC6."""
    O = po(db, s, "1")
    E1 = rev(db, s, O, T0)
    E2 = rev(db, s, O, T2)
    E3 = rev(db, s, O, T1)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_receive_events(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert [e.id for e in result] == [E2.id, E3.id, E1.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# [claude] POS-LR-03
@xfail(3172, strict=False)
def test_pos_lr_03__equal_times_higher_id_first(db, s):
    """POS-LR-03 — equal times: the higher id first.
    Rules: list_receive_events LR2 [BUG-3172]."""
    O = po(db, s, "1")
    E1 = rev(db, s, O, T1)
    E2 = rev(db, s, O, T1)
    commit_point(db)

    result = svc.list_receive_events(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert [e.id for e in result] == [E2.id, E1.id]


@xfail(3172)
def test_pos_lr_04__events_query_ties_by_id(db, s):
    """POS-LR-04 — the events query breaks ties by id descending.
    Rules: list_receive_events LR2 [BUG-3172]."""
    O = po(db, s, "1")
    oid, w1_id = O.id, s.W1.id
    rev(db, s, O, T1)
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.list_receive_events(db, po_id=oid, workspace_id=w1_id)

    # Then 1
    assert len(result) == 1
    # Then 2
    st = rec.selects_from("po_receive_events")[0]
    tail = _order_by_tail(st)
    assert "created_at DESC" in tail
    assert "id DESC" in tail.split("created_at DESC", 1)[1]


def test_pos_lr_05__foreign_events_not_listed(db, s):
    """POS-LR-05 — W0 and W2 events carrying the same order id are not listed.
    Rules: list_receive_events LR2; HR-16."""
    O = po(db, s, "1")
    rev(db, s, O, T0, workspace_id=s.W0.id)
    E1 = rev(db, s, O, T1)
    rev(db, s, O, T2, workspace_id=s.W2.id)
    commit_point(db)

    result = svc.list_receive_events(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert [e.id for e in result] == [E1.id]


def test_pos_lr_06__no_events_empty(db, s):
    """POS-LR-06 — no events → empty list.
    Rules: list_receive_events LR2."""
    O = po(db, s, "1")
    commit_point(db)

    result = svc.list_receive_events(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# _build_receive_event_response
# --------------------------------------------------------------------------- #


def test_pos_br_01__columns_performer_lines(db, s):
    """POS-BR-01 — columns, performer name and lines with the PO line's name and unit.
    Rules: _build_receive_event_response BR1."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    E = rev(db, s, O, T1, performed_by=s.U2.id, rcc="RCC-1")
    revi(db, E, L, "3")
    commit_point(db)

    result = svc._build_receive_event_response(E)

    # Then 1
    assert result.id == E.id
    assert result.rcc == "RCC-1"
    assert result.performer_name == "Karim Ali"
    # Then 2
    assert len(result.items) == 1
    assert result.items[0].po_item_name == "Bearing"
    assert result.items[0].po_item_unit == "pcs"
    assert result.items[0].quantity_delta == Decimal("3.00")


def test_pos_br_02__no_performer(db, s):
    """POS-BR-02 — no performer → `performer_name None`.
    Rules: _build_receive_event_response BR1."""
    O = po(db, s, "1")
    E = rev(db, s, O, T1, performed_by=None)
    commit_point(db)

    result = svc._build_receive_event_response(E)

    # Then 1
    assert result.performer_name is None
    assert result.items == []


# [claude] POS-BR-03
def test_pos_br_03__line_without_po_line(db, s):
    """POS-BR-03 — a line whose PO line is gone shows `None` name and unit.
    Rules: _build_receive_event_response BR1."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    E = rev(db, s, O, T1)
    ei = revi(db, E, L, "1")
    commit_point(db)
    ei.po_item = None  # in memory only (autoflush is off)

    result = svc._build_receive_event_response(E)

    # Then 1
    assert result.items[0].po_item_name is None
    assert result.items[0].po_item_unit is None


@xfail(3172)
def test_pos_br_04__lines_read_in_id_order_sql(db, s):
    """POS-BR-04 — the event's lines are read in id order.
    Rules: _build_receive_event_response BR1 [BUG-3172]."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    oid, w1_id = O.id, s.W1.id
    E = rev(db, s, O, T1)
    revi(db, E, L, "1")
    revi(db, E, L, "2")
    revi(db, E, L, "3")
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.list_receive_events(db, po_id=oid, workspace_id=w1_id)

    # Then 1
    assert len(result[0].items) == 3
    # Then 2
    st = rec.selects_from("po_receive_event_items")[0]
    tail = _order_by_tail(st)
    assert re.search(r"\bid\b(?!\s+DESC)", tail) is not None


@xfail(3172, strict=False)
def test_pos_br_05__lines_in_id_order(db, s):
    """POS-BR-05 — the lines come back in id order.
    Rules: _build_receive_event_response BR1 [BUG-3172]."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    E = rev(db, s, O, T1)
    a = revi(db, E, L, "1")
    revi(db, E, L, "2")
    revi(db, E, L, "3")
    commit_point(db)
    db.execute(text("UPDATE po_receive_event_items SET quantity_delta = quantity_delta WHERE id = :i"), {"i": a.id})
    db.expire_all()

    result = svc._build_receive_event_response(E)

    # Then 1
    assert [i.quantity_delta for i in result.items] == [Decimal("1.00"), Decimal("2.00"), Decimal("3.00")]


# --------------------------------------------------------------------------- #
# _attach_return_invoice_for_po
# --------------------------------------------------------------------------- #


def AR(db, s, O, R):
    """Section convention AR(O, R)."""
    return svc._attach_return_invoice_for_po(db, po=O, ret=R, workspace_id=s.W1.id, user_id=s.U2.id)


def test_pos_ar_01__one_finalized_credit_note(db, s):
    """POS-AR-01 — one finalized receivable credit note, linked to the return only.
    Rules: _attach_return_invoice_for_po AR1, AR4."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    commit_point(db)

    AR(db, s, O, R)

    # Then 1
    CNID = reread(db, PurchaseOrderReturn, R.id).invoice_id
    assert CNID is not None
    # Then 2
    v = reread(db, AccountInvoice, CNID)
    assert v.account_id == s.A1.id
    assert v.order_id == O.id
    assert v.order_type == "purchase_order"
    assert v.invoice_type == "receivable"
    assert v.allow_payments is True
    # Then 3
    assert v.description == f"Return credit note for {O.po_number} ({R.return_number})"
    assert v.notes == "Faulty"
    # Then 4
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("2000.00")
    # Then 5
    assert itypes(db, CNID).count("confirmed") == 1
    # Then 6
    assert reread(db, PurchaseOrder, O.id).invoice_id is None


def test_pos_ar_02__one_line_per_return_line(db, s):
    """POS-AR-02 — one credit-note line per return line, numbered in id order.
    Rules: _attach_return_invoice_for_po AR2, AR3."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    L2 = poline(db, s, O, 2, item_id=s.I1b.id, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    rline(db, R, L2, "2", unit_price=Decimal("300.00"))
    commit_point(db)

    AR(db, s, O, R)

    cnid = reread(db, PurchaseOrderReturn, R.id).invoice_id
    # Then 1
    assert [(x.line_number, x.source_order_item_id) for x in LINES(db, cnid)] == [(1, L.id), (2, L2.id)]
    # Then 2
    x0 = LINES(db, cnid)[0]
    assert x0.source_order_item_type == "po_item"
    assert x0.item_id == s.I1.id
    assert x0.quantity == Decimal("4.00")
    assert x0.unit_price == Decimal("500.00")
    assert x0.line_subtotal == Decimal("2000.00")
    # Then 3
    x1 = LINES(db, cnid)[1]
    assert x1.item_id == s.I1b.id
    assert x1.quantity == Decimal("2.00")
    assert x1.unit_price == Decimal("300.00")
    assert x1.line_subtotal == Decimal("600.00")
    # Then 4
    assert reread(db, AccountInvoice, cnid).invoice_amount == Decimal("2600.00")


# [claude] POS-AR-03
def test_pos_ar_03__nameless_line_described_by_item_id(db, s):
    """POS-AR-03 — a return line without an item name is described `Item <item_id>`.
    Rules: _attach_return_invoice_for_po AR2."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    s.I1.name = ""  # item_name is the item's name property: empty name
    db.flush()
    commit_point(db)

    AR(db, s, O, R)

    # Then 1
    assert LINES(db, reread(db, PurchaseOrderReturn, R.id).invoice_id)[0].description == f"Item {s.I1.id}"


@xfail(3167)
def test_pos_ar_04__credit_note_dated_utc(db, s):
    """POS-AR-04 — the credit note is dated with the UTC clock.
    Rules: _attach_return_invoice_for_po AR1 [BUG-3167]."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    commit_point(db)

    AR(db, s, O, R)

    # Then 1
    cnid = reread(db, PurchaseOrderReturn, R.id).invoice_id
    assert cnid is not None
    # Then 2
    assert reread(db, AccountInvoice, cnid).invoice_date == TODAY_UTC


def test_pos_ar_05__stored_subtotals_rounded(db, s):
    """POS-AR-05 — stored line subtotals are rounded half up and the amount is their sum.
    Rules: _attach_return_invoice_for_po AR3; HR-15 (regression rule; BUG-3163 withdrawn)."""
    O = po(db, s, "1", **READY, **PROJ)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"), unit_price=Decimal("1.25"), line_subtotal=Decimal("12.50"))
    L2 = poline(db, s, O, 2, item_id=s.I1b.id, quantity_received=Decimal("10.00"), unit_price=Decimal("1.25"), line_subtotal=Decimal("12.50"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "0.10", unit_price=Decimal("1.25"))
    rline(db, R, L2, "0.10", unit_price=Decimal("1.25"))
    commit_point(db)

    AR(db, s, O, R)

    # Then 1
    cnid = reread(db, PurchaseOrderReturn, R.id).invoice_id
    assert cnid is not None
    # Then 2
    assert [x.line_subtotal for x in LINES(db, cnid)] == [Decimal("0.13"), Decimal("0.13")]
    # Then 3
    assert reread(db, AccountInvoice, cnid).invoice_amount == Decimal("0.26")


def test_pos_ar_06__two_place_lines_exact(db, s):
    """POS-AR-06 — 2-place lines: subtotals and amount exact.
    Rules: _attach_return_invoice_for_po AR3 (part that holds today and after BUG-3163)."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "3", unit_price=Decimal("333.33"))
    commit_point(db)

    AR(db, s, O, R)

    cnid = reread(db, PurchaseOrderReturn, R.id).invoice_id
    # Then 1
    assert LINES(db, cnid)[0].line_subtotal == Decimal("999.99")
    # Then 2
    assert reread(db, AccountInvoice, cnid).invoice_amount == Decimal("999.99")


def test_pos_ar_07__helper_flushes_only(db, s):
    """POS-AR-07 — the helper flushes only.
    Rules: _attach_return_invoice_for_po AR4."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    commit_point(db)

    with spies(db) as (cm, rb):
        AR(db, s, O, R)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert R.invoice_id is not None


def test_pos_ar_08__zero_priced_line(db, s):
    """POS-AR-08 — a return line priced 0.00 gives a 0.00 credit-note line.
    Rules: _attach_return_invoice_for_po AR2 (price 0), AR3."""
    O = po(db, s, "1", **READY)
    L = poline(db, s, O, 1, quantity_received=Decimal("10.00"))
    L2 = poline(db, s, O, 2, item_id=s.I1b.id, quantity_received=Decimal("10.00"))
    R = ret(db, s, O, "1")
    rline(db, R, L, "4")
    rline(db, R, L2, "2", unit_price=Decimal("0.00"))
    commit_point(db)

    AR(db, s, O, R)

    # Then 1
    CNID = reread(db, PurchaseOrderReturn, R.id).invoice_id
    assert CNID is not None
    # Then 2
    assert [(x.line_number, x.unit_price, x.line_subtotal) for x in LINES(db, CNID)] == [(1, Decimal("500.00"), Decimal("2000.00")), (2, Decimal("0.00"), Decimal("0.00"))]
    # Then 3
    v = reread(db, AccountInvoice, CNID)
    assert v.invoice_amount == Decimal("2000.00")
    assert v.invoice_status == "confirmed"


# --------------------------------------------------------------------------- #
# start_return
# --------------------------------------------------------------------------- #


def srbase(db, s, o_but=None, l_but=None):
    """Section convention SRBASE: O ready at Receiving, invoice confirmed; V finalized, linked; L received 10."""
    O = po(db, s, "1", **{**READY, "current_status_id": s.SR1.id, "invoice_confirmed": True, **(o_but or {})})
    V = inv(db, s, O, linked=True, **FINALIZED)
    L = poline(db, s, O, 1, **{"quantity_received": Decimal("10.00"), **(l_but or {})})
    return O, V, L


def SR(db, s, O, req):
    """Section convention SR(req)."""
    return svc.start_return(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id, data=req)


def test_pos_sr_01__return_starts_pending(db, s):
    """POS-SR-01 — a return starts pending with a finalized credit note; committed; no stock moves.
    Rules: start_return SR3, SR6, SR7; TC1, TC2."""
    O, _V, L = srbase(db, s)
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4"), t="refund"))

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.status == "pending"
    assert result.invoice_id is not None
    rid, cnid = result.id, result.invoice_id
    db.rollback()
    # Then 3
    r = reread(db, PurchaseOrderReturn, rid)
    assert r.return_type == "refund"
    assert r.reason == "Faulty"
    assert r.purchase_order_id == O.id
    assert r.workspace_id == s.W1.id
    # Then 4
    rls = rows_where(db, PurchaseOrderReturnItem, PurchaseOrderReturnItem.return_id == rid)
    assert len(rls) == 1
    assert rls[0].po_item_id == L.id
    assert rls[0].quantity_returned == Decimal("4.00")
    # Then 5
    cnv = reread(db, AccountInvoice, cnid)
    assert cnv.invoice_type == "receivable"
    assert cnv.invoice_status == "confirmed"
    assert cnv.invoice_amount == Decimal("2000.00")
    # Then 6
    line = reread(db, PurchaseOrderItem, L.id)
    assert line.quantity_received == Decimal("10.00")
    assert line.quantity_returned == Decimal("0.00")
    # Then 7
    assert count_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id) == 0
    # Then 8
    assert notes(db) == []


def test_pos_sr_02__return_started_event(db, s):
    """POS-SR-02 — the `return_started` event.
    Rules: start_return SR6."""
    O, _V, L = srbase(db, s)
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4"), t="replace"))

    rid, rnum, cnid = result.id, result.return_number, result.invoice_id
    db.rollback()
    # Then 1
    e = event_of(db, O.id, "return_started")
    assert e.description == f"Return {rnum} started — replace (4 unit(s) across 1 item(s))"
    # Then 2
    assert e.metadata_json == {"return_id": rid, "invoice_id": cnid, "return_type": "replace"}


def test_pos_sr_03__w0_order_404(db, s):
    """POS-SR-03 — a W0 order → 404.
    Rules: start_return SR1."""
    O0 = po(db, s, "0", "0", **READY)
    L0 = poline(db, s, O0, 1, quantity_received=Decimal("10.00"))
    srbase(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, po_id=O0.id, workspace_id=s.W1.id, user_id=s.U2.id, data=SRQ((L0, "4"), t="refund"))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)
    # Then 4
    assert counts(db) == before


def test_pos_sr_04__w2_order_404(db, s):
    """POS-SR-04 — a W2 order → 404.
    Rules: start_return SR1."""
    srbase(db, s)
    O9 = po(db, s, "9", "9", **READY)
    L9 = poline(db, s, O9, 1, quantity_received=Decimal("10.00"))
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, po_id=O9.id, workspace_id=s.W1.id, user_id=s.U2.id, data=SRQ((L9, "4"), t="refund"))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert counts(db) == before


def test_pos_sr_05__voided_order_400(db, s):
    """POS-SR-05 — a voided order → 400.
    Rules: start_return SR1."""
    O, _V, L = srbase(db, s, o_but=VOIDED(s))
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SR(db, s, O, SRQ((L, "4"), t="refund"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot return items on a voided purchase order"
    # Then 4
    assert counts(db) == before


def test_pos_sr_06__nothing_received_400(db, s):
    """POS-SR-06 — nothing received → 400, rolled back.
    Rules: start_return SR2, SR7; TC3."""
    O, _V, L = srbase(db, s, l_but={"quantity_received": Decimal("0.00")})
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            SR(db, s, O, SRQ((L, "4"), t="refund"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "No items have been received yet — nothing to return"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


def test_pos_sr_07__quantity_check_passes_through(db, s):
    """POS-SR-07 — the return manager's quantity check passes through.
    Rules: start_return SR3."""
    O, _V, L = srbase(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SR(db, s, O, SRQ((L, "11"), t="refund"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot return 11 of line 1 — only 10.00 available to return"
    # Then 4
    assert counts(db) == before


@xfail(801)
def test_pos_sr_08__fractional_storage_400(db, s):
    """POS-SR-08 — a fractional quantity on a storage order → 400.
    Rules: start_return SR4 [BUG-801]."""
    O, _V, L = srbase(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SR(db, s, O, SRQ((L, "4.5"), t="refund"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Return line for PO line 1 has a fractional quantity; inventory requires whole units"
    db.rollback()
    # Then 4
    assert count_where(db, PurchaseOrderReturn, PurchaseOrderReturn.purchase_order_id == O.id) == 0


def test_pos_sr_09__fractional_project_accepted(db, s):
    """POS-SR-09 — a fractional quantity on a project order is accepted.
    Rules: start_return SR4."""
    O, _V, L = srbase(db, s, o_but=PROJ)
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4.5"), t="refund"))

    # Then 1
    assert result.status == "pending"
    rid = result.id
    db.rollback()
    # Then 2
    rls = rows_where(db, PurchaseOrderReturnItem, PurchaseOrderReturnItem.return_id == rid)
    assert rls[0].quantity_returned == Decimal("4.50")


def test_pos_sr_10__completed_order_accepts_return(db, s):
    """POS-SR-10 — a completed order accepts a return.
    Rules: start_return SR1, SR5 (part that holds today and after BUG-2789)."""
    O, _V, L = srbase(db, s, o_but=COMPLETE(s))
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4"), t="replace"))

    # Then 1
    assert result.status == "pending"
    db.rollback()
    # Then 2
    assert count_where(db, PurchaseOrderReturn, PurchaseOrderReturn.purchase_order_id == O.id) == 1


@xfail(2789)
def test_pos_sr_11__completed_order_stays_completed(db, s):
    """POS-SR-11 — a completed order stays completed while the return is pending.
    Rules: start_return SR5 [BUG-2789]."""
    O, _V, L = srbase(db, s, o_but={**COMPLETE(s), "actual_delivery_date": date(2026, 9, 10)})
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4"), t="replace"))

    # Then 1
    assert result.status == "pending"
    db.rollback()
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.current_status_id == s.SC1.id
    assert o.actual_delivery_date == date(2026, 9, 10)
    # Then 3
    assert "order_reopened" not in types(db, O.id)


def test_pos_sr_12__credit_note_refused_rolls_back(db, s):
    """POS-SR-12 — the credit note refused → the return is rolled back too.
    Rules: start_return SR7; AR1; TC3."""
    A2 = _add(db, Account(workspace_id=s.W1.id, name="No Bills Ltd", is_active=True, is_deleted=False, allow_invoices=False))
    O, _V, L = srbase(db, s, o_but={"account_id": A2.id})
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SR(db, s, O, SRQ((L, "4"), t="refund"))
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert count_where(db, PurchaseOrderReturn, PurchaseOrderReturn.purchase_order_id == O.id) == 0
    # Then 7
    assert counts(db) == before


def test_pos_sr_13__failing_commit_saves_nothing(db, s):
    """POS-SR-13 — a failing commit saves no return and no credit note.
    Rules: start_return SR7; TC4."""
    O, _V, L = srbase(db, s)
    before = commit_point(db)
    req = SRQ((L, "4"), t="refund")
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.start_return(db, po_id=oid, workspace_id=w1_id, user_id=u2_id, data=req)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


@xfail(3176)
def test_pos_sr_14__response_empty_warnings(db, s):
    """POS-SR-14 — the return response carries empty warnings.
    Rules: receive_replacements RX8d [BUG-3176]."""
    O, _V, L = srbase(db, s)
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "4"), t="refund"))

    # Then 1
    assert WARN(result) == []


def test_pos_sr_15__one_unit_received_enough(db, s):
    """POS-SR-15 — exactly 1 unit received is enough to start a return.
    Rules: start_return SR2 (boundary: received > 0)."""
    O, _V, L = srbase(db, s, l_but={"quantity_received": Decimal("1.00")})
    commit_point(db)

    result = SR(db, s, O, SRQ((L, "1"), t="refund"))

    # Then 1
    assert result.status == "pending"
    assert result.invoice_id is not None
    rid = result.id
    db.rollback()
    # Then 2
    rls = rows_where(db, PurchaseOrderReturnItem, PurchaseOrderReturnItem.return_id == rid)
    assert len(rls) == 1
    assert rls[0].po_item_id == L.id
    assert rls[0].quantity_returned == Decimal("1.00")


# --------------------------------------------------------------------------- #
# complete_return
# --------------------------------------------------------------------------- #


def crbase(db, s, o_but=None, l_but=None, r_but=None, cn_but=None, with_cn=True):
    """Section convention CRBASE: O (proj, ready, Receiving, invoice confirmed), V, L, R, RL, CN."""
    g = SimpleNamespace()
    g.O = po(db, s, "1", **{**PROJ, **READY, "current_status_id": s.SR1.id, "invoice_confirmed": True, **(o_but or {})})
    g.V = inv(db, s, g.O, linked=True, **FINALIZED)
    g.L = poline(db, s, g.O, 1, **{"quantity_received": Decimal("10.00"), **(l_but or {})})
    g.R = ret(db, s, g.O, "1", **(r_but or {}))
    g.RL = rline(db, g.R, g.L, "4")
    g.CN = cn(db, s, g.R, "2000.00", **(cn_but or {})) if with_cn else None
    return g


def CR(db, s, g):
    """Section convention CR()."""
    return svc.complete_return(db, po_id=g.O.id, return_id=g.R.id, workspace_id=s.W1.id, user_id=s.U2.id)


def stock(db, s, F, I, qty, avg):
    """BUG-664 guard: a storage stock row plus one opening ledger row dated T0 (in the past)."""
    from app.models.enums import InventoryTypeEnum

    row = _add(db, Inventory(
        workspace_id=s.W1.id, item_id=I.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=F.id,
        qty=qty, avg_price=Decimal(avg), is_active=True, is_deleted=False, created_by=s.U1.id,
    ))
    _add(db, InventoryLedger(
        workspace_id=s.W1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=F.id, item_id=I.id,
        transaction_type="opening", quantity=qty, unit_cost=Decimal(avg),
        total_cost=Decimal(avg) * qty, qty_before=0, qty_after=qty, avg_price_before=None,
        avg_price_after=Decimal(avg), source_type="test_seed", source_id=1, performed_by=s.U1.id,
        performed_at=T0,
    ))
    return row


def test_pos_cr_01__refund_completes(db, s):
    """POS-CR-01 — a refund return completes: quantities, status, stamps; committed.
    Rules: complete_return CR3, CR5, CR8; TC1, TC2."""
    g = crbase(db, s)
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = CR(db, s, g)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == g.R.id
    assert result.status == "completed"
    db.rollback()
    # Then 3
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_returned == Decimal("4.00")
    assert line.quantity_received == Decimal("6.00")
    assert line.quantity_refunded == Decimal("4.00")
    # Then 4
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.completed_at == NOW
    assert r.completed_by == s.U2.id
    # Then 5
    assert snap(db, g.CN) == cn_before


def test_pos_cr_02__return_completed_event_refund(db, s):
    """POS-CR-02 — the `return_completed` event of a refund.
    Rules: complete_return CR6."""
    g = crbase(db, s)
    commit_point(db)
    db.expire_all()

    CR(db, s, g)

    db.rollback()
    # Then 1
    e = event_of(db, g.O.id, "return_completed")
    assert e.description == f"Return {g.R.return_number} completed — refund (4.00 unit(s), 0 inventory line(s) posted)"
    # Then 2
    assert e.metadata_json == {"return_id": g.R.id, "return_type": "refund"}


def test_pos_cr_03__replace_leaves_gap(db, s):
    """POS-CR-03 — a replace return leaves the gap and says so.
    Rules: complete_return CR3, CR6."""
    g = crbase(db, s, r_but=REPLACE)
    commit_point(db)
    db.expire_all()

    CR(db, s, g)

    db.rollback()
    # Then 1
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_received == Decimal("6.00")
    assert line.quantity_refunded == Decimal("0.00")
    assert line.quantity_returned == Decimal("4.00")
    # Then 2
    assert event_of(db, g.O.id, "return_completed").description == f"Return {g.R.return_number} completed — replace (4.00 unit(s), 0 inventory line(s) posted) — re-receive to close the gap"


def test_pos_cr_04__return_of_other_order_404(db, s):
    """POS-CR-04 — a return of another order → 404.
    Rules: complete_return CR1."""
    g = crbase(db, s)
    O2 = po(db, s, "2", **PROJ)
    R2 = ret(db, s, O2, "2")
    commit_point(db)
    r2_before = snap(db, R2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_return(db, po_id=g.O.id, return_id=R2.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R2.id)
    # Then 4
    assert snap(db, R2) == r2_before


def test_pos_cr_05__w0_return_404(db, s):
    """POS-CR-05 — a W0 return id → 404.
    Rules: complete_return CR1."""
    O0 = po(db, s, "0", "0", **PROJ)
    R0 = ret(db, s, O0, "0")
    g = crbase(db, s)
    commit_point(db)
    r0_before = snap(db, R0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_return(db, po_id=g.O.id, return_id=R0.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R0.id)
    # Then 4
    assert snap(db, R0) == r0_before


def test_pos_cr_06__w2_return_404(db, s):
    """POS-CR-06 — a W2 return id → 404.
    Rules: complete_return CR1."""
    g = crbase(db, s)
    O9 = po(db, s, "9", "9", **PROJ)
    R9 = ret(db, s, O9, "9")
    commit_point(db)
    r9_before = snap(db, R9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_return(db, po_id=g.O.id, return_id=R9.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R9.id)
    # Then 4
    assert snap(db, R9) == r9_before


def test_pos_cr_07__already_completed_400(db, s):
    """POS-CR-07 — an already completed return → 400, rolled back.
    Rules: complete_return CR2, CR8; TC3."""
    g = crbase(db, s, r_but=COMPLETED(s))
    commit_point(db)
    l_before = snap(db, g.L)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            CR(db, s, g)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a pending return can be completed"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, g.L) == l_before


def test_pos_cr_08__voided_return_400(db, s):
    """POS-CR-08 — a voided return → 400.
    Rules: complete_return CR2."""
    g = crbase(db, s, r_but=VOIDED_RET)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, g)
    # Then 2
    assert exc.value.detail == "Only a pending return can be completed"
    # Then 3
    assert counts(db) == before


@xfail(2754)
def test_pos_cr_09__return_row_locked(db, s):
    """POS-CR-09 — the return row is locked.
    Rules: complete_return CR1 [BUG-2754]; HR-10."""
    g = crbase(db, s)
    oid, rid, w1_id, u2_id = g.O.id, g.R.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.complete_return(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.status == "completed"
    # Then 2
    assert rec.exact_lock("purchase_order_returns")
    # Then 3
    assert rec.before("purchase_order_returns", "purchase_order_return_items")


@xfail(3174)
def test_pos_cr_10__completing_stamps_updated_by(db, s):
    """POS-CR-10 — completing stamps `updated_by`.
    Rules: complete_return CR7 [BUG-3174]."""
    g = crbase(db, s)
    commit_point(db)

    result = CR(db, s, g)

    # Then 1
    assert result.status == "completed"
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrderReturn, g.R.id).updated_by == s.U2.id


# [claude] POS-CR-11
def test_pos_cr_11__storage_posts_stock_out(db, s):
    """POS-CR-11 — a storage order posts the stock out.
    Rules: complete_return CR4, CR6."""
    g = crbase(db, s, o_but={"destination_type": "storage", "destination_id": s.F1.id})
    stock(db, s, s.F1, s.I1, 10, "500.00")
    commit_point(db)

    CR(db, s, g)

    db.rollback()
    # Then 1
    rows = rows_where(db, InventoryLedger, InventoryLedger.source_type == "purchase_return_item", InventoryLedger.source_id == g.RL.id)
    assert len(rows) == 1
    assert rows[0].quantity == 4
    # Then 2
    assert event_of(db, g.O.id, "return_completed").description.endswith(", 1 inventory line(s) posted)")


def test_pos_cr_12__not_enough_stock_400(db, s):
    """POS-CR-12 — not enough stock → 400, everything rolled back.
    Rules: complete_return CR4, CR8; TC3."""
    g = crbase(db, s, o_but={"destination_type": "storage", "destination_id": s.F1.id})
    commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, g)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Insufficient stock (0 available, 4 requested)"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.status == "pending"
    assert r.completed_at is None
    # Then 7
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_received == Decimal("10.00")
    assert line.quantity_returned == Decimal("0.00")


def test_pos_cr_13__failing_commit_pending(db, s):
    """POS-CR-13 — a failing commit leaves the return pending.
    Rules: complete_return CR8; TC4."""
    g = crbase(db, s)
    commit_point(db)
    oid, rid, lid, w1_id, u2_id = g.O.id, g.R.id, g.L.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.complete_return(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderReturn, rid).status == "pending"
    # Then 4
    assert reread(db, PurchaseOrderItem, lid).quantity_received == Decimal("10.00")


def test_pos_cr_14__stage_not_changed(db, s):
    """POS-CR-14 — the order's stage is not changed.
    Rules: complete_return CR6; RF2."""
    g = crbase(db, s, o_but=COMPLETE(s))
    commit_point(db)

    CR(db, s, g)

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrder, g.O.id).current_status_id == s.SC1.id
    # Then 2
    assert types(db, g.O.id) == ["return_completed"]


def test_pos_cr_15__foreign_order_line_skipped(db, s):
    """POS-CR-15 — a return line pointing at another order's line is skipped.
    Rules: complete_return CR3."""
    g = crbase(db, s)
    O2 = po(db, s, "2", **PROJ)
    L2 = poline(db, s, O2, 1, quantity_received=Decimal("10.00"))
    rline(db, g.R, L2, "1")
    commit_point(db)

    CR(db, s, g)

    db.rollback()
    # Then 1
    l2 = reread(db, PurchaseOrderItem, L2.id)
    assert l2.quantity_received == Decimal("10.00")
    assert l2.quantity_returned == Decimal("0.00")
    # Then 2
    assert reread(db, PurchaseOrderItem, g.L.id).quantity_received == Decimal("6.00")


@xfail(3176)
def test_pos_cr_16__response_empty_warnings(db, s):
    """POS-CR-16 — the completed return's response carries empty warnings.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = crbase(db, s)
    commit_point(db)

    result = CR(db, s, g)

    # Then 1
    assert WARN(result) == []


def test_pos_cr_17__adds_to_returned_and_refunded(db, s):
    """POS-CR-17 — completing adds to quantities already returned and refunded.
    Rules: complete_return CR3 (+=, not =)."""
    g = crbase(db, s, l_but={"quantity_received": Decimal("8.00"), "quantity_returned": Decimal("2.00"), "quantity_refunded": Decimal("2.00")})
    commit_point(db)

    CR(db, s, g)

    db.rollback()
    # Then 1
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_returned == Decimal("6.00")
    assert line.quantity_refunded == Decimal("6.00")
    assert line.quantity_received == Decimal("4.00")


@xfail(3186)
def test_pos_cr_18__line_corrected_to_zero_refused(db, s):
    """POS-CR-18 — a return whose line was corrected to 0 meanwhile is refused, nothing written.
    Rules: complete_return CR3a [BUG-3186], CR8; TC3."""
    g = SimpleNamespace()
    g.O = po(db, s, "1", **PROJ, **READY, current_status_id=s.SR1.id, invoice_confirmed=True)
    inv(db, s, g.O, linked=True, **FINALIZED)
    g.L = poline(db, s, g.O, 1)
    svc.create_receive_event(db, po_id=g.O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=RCV((g.L, "4")))
    g.R = svc.start_return(db, po_id=g.O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=SRQ((g.L, "4"), t="refund"))
    svc.create_receive_event(db, po_id=g.O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=COR((g.L, "-4"), note="Recount"))
    db.expire_all()
    line = db.get(PurchaseOrderItem, g.L.id)
    assert line.quantity_received == Decimal("0.00")
    assert line.quantity_returned == Decimal("0.00")
    assert db.get(PurchaseOrderReturn, g.R.id).status == "pending"
    rno = g.R.return_number
    before = commit_point(db)
    l_before, r_before = snap(db, g.L), snap(db, g.R)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, g)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Cannot complete return {rno} — line 1 has only 0.00 received; correct the receipt or cancel the return"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap(db, g.L) == l_before
    # Then 8
    assert snap(db, g.R) == r_before
    assert "return_completed" not in types(db, g.O.id)


@xfail(3186)
def test_pos_cr_19__one_short_line_refuses_all(db, s):
    """POS-CR-19 — one short line refuses the whole return before any line is written.
    Rules: complete_return CR3a [BUG-3186]; TC3."""
    g = crbase(db, s)
    L2 = poline(db, s, g.O, 2, quantity_received=Decimal("2.00"))
    rline(db, g.R, L2, "3")
    before = commit_point(db)
    l_before, l2_before, r_before = snap(db, g.L), snap(db, L2), snap(db, g.R)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, g)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Cannot complete return {g.R.return_number} — line 2 has only 2.00 received; correct the receipt or cancel the return"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap(db, g.L) == l_before
    assert snap(db, L2) == l2_before
    assert snap(db, g.R) == r_before


def test_pos_cr_20__line_ends_at_zero(db, s):
    """POS-CR-20 — a line that ends at exactly 0 completes.
    Rules: complete_return CR3, CR3a (exactly 0 is allowed), CR5."""
    g = crbase(db, s, l_but={"quantity_received": Decimal("4.00")})
    commit_point(db)

    result = CR(db, s, g)

    # Then 1
    assert result.status == "completed"
    db.rollback()
    # Then 2
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_received == Decimal("0.00")
    assert line.quantity_returned == Decimal("4.00")
    assert line.quantity_refunded == Decimal("4.00")
    # Then 3
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.completed_at == NOW
    assert r.completed_by == s.U2.id


# --------------------------------------------------------------------------- #
# void_return
# --------------------------------------------------------------------------- #


def VR(db, s, g, note):
    """Section convention VR(note)."""
    return svc.void_return(db, po_id=g.O.id, return_id=g.R.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note=note)


def test_pos_vr_01__cancel_voids_note_and_return(db, s):
    """POS-VR-01 — cancel voids the credit note and the return; committed; no quantities move.
    Rules: void_return VR3, VR4, VR6; TC1, TC2."""
    g = crbase(db, s)
    commit_point(db)
    l_before = snap(db, g.L)

    result = VR(db, s, g, "Wrong item")

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == g.R.id
    assert result.status == "voided"
    db.rollback()
    # Then 3
    assert reread(db, PurchaseOrderReturn, g.R.id).paid is False
    # Then 4
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.invoice_status == "voided"
    assert c.void_note == "Wrong item"
    # Then 5
    e = event_of(db, g.O.id, "return_voided")
    assert e.description == f"Return {g.R.return_number} cancelled — Wrong item"
    assert e.metadata_json == {"return_id": g.R.id, "void_note": "Wrong item"}
    # Then 6
    assert snap(db, g.L) == l_before


def test_pos_vr_02__credit_note_payments_voided(db, s):
    """POS-VR-02 — the credit note's payments are voided with it.
    Rules: void_return VR3."""
    g = crbase(db, s, cn_but={"paid_amount": Decimal("500.00"), "payment_status": "partial"})
    P = cash(db, s, g.CN, "500.00")
    commit_point(db)

    VR(db, s, g, "Wrong item")

    db.rollback()
    # Then 1
    assert reread(db, InvoicePayment, P.id).is_voided is True
    # Then 2
    assert reread(db, AccountInvoice, g.CN.id).invoice_status == "voided"


def test_pos_vr_03__return_of_other_order_404(db, s):
    """POS-VR-03 — a return of another order → 404.
    Rules: void_return VR1."""
    g = crbase(db, s)
    O2 = po(db, s, "2", **PROJ)
    R2 = ret(db, s, O2, "2")
    commit_point(db)
    r2_before = snap(db, R2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_return(db, po_id=g.O.id, return_id=R2.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R2.id)
    # Then 4
    assert snap(db, R2) == r2_before


def test_pos_vr_04__w2_return_404(db, s):
    """POS-VR-04 — a W2 return id → 404.
    Rules: void_return VR1."""
    g = crbase(db, s)
    O9 = po(db, s, "9", "9", **PROJ)
    R9 = ret(db, s, O9, "9")
    commit_point(db)
    r9_before = snap(db, R9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_return(db, po_id=g.O.id, return_id=R9.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R9.id)
    # Then 4
    assert snap(db, R9) == r9_before


def test_pos_vr_05__completed_return_400(db, s):
    """POS-VR-05 — a completed return → 400, rolled back.
    Rules: void_return VR2, VR6; TC3."""
    g = crbase(db, s, r_but=COMPLETED(s))
    commit_point(db)
    cn_before = snap(db, g.CN)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            VR(db, s, g, "x")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a pending return can be cancelled"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, g.CN) == cn_before


@xfail(2754)
def test_pos_vr_06__return_row_locked(db, s):
    """POS-VR-06 — the return row is locked.
    Rules: void_return VR1 [BUG-2754]; HR-10."""
    g = crbase(db, s)
    oid, rid, w1_id, u2_id = g.O.id, g.R.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.void_return(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, void_note="Wrong item")

    # Then 1
    assert result.status == "voided"
    # Then 2
    assert rec.exact_lock("purchase_order_returns")
    # Then 3
    assert rec.before("purchase_order_returns", "account_invoices")


@xfail(3174)
def test_pos_vr_07__cancelling_stamps_updated_by(db, s):
    """POS-VR-07 — cancelling stamps `updated_by`.
    Rules: void_return VR5 [BUG-3174]."""
    g = crbase(db, s)
    commit_point(db)

    result = VR(db, s, g, "Wrong item")

    # Then 1
    assert result.status == "voided"
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrderReturn, g.R.id).updated_by == s.U2.id


@xfail(3182)
def test_pos_vr_08__voided_credit_note_skipped(db, s):
    """POS-VR-08 — a credit note already voided is skipped and the cancel goes ahead.
    Rules: void_return VR3 [BUG-3182]."""
    g = crbase(db, s, cn_but=VOIDED_INV)
    commit_point(db)

    result = VR(db, s, g, "Wrong item")

    # Then 1
    assert result.status == "voided"
    db.rollback()
    # Then 2
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.status == "voided"
    assert r.paid is False
    # Then 3
    assert reread(db, AccountInvoice, g.CN.id).void_note == "dup"


def test_pos_vr_09__no_credit_note_cancels(db, s):
    """POS-VR-09 — a return with no credit note cancels.
    Rules: void_return VR3, VR4."""
    g = SimpleNamespace()
    g.O = po(db, s, "1", **PROJ, **READY)
    g.L = poline(db, s, g.O, 1, quantity_received=Decimal("10.00"))
    g.R = ret(db, s, g.O, "1")
    rline(db, g.R, g.L, "4")
    commit_point(db)

    result = VR(db, s, g, "Wrong item")

    # Then 1
    assert result.status == "voided"
    db.rollback()
    # Then 2
    assert "return_voided" in types(db, g.O.id)


def test_pos_vr_10__failing_commit_pending(db, s):
    """POS-VR-10 — a failing commit leaves the return pending and the note owed.
    Rules: void_return VR6; TC4."""
    g = crbase(db, s)
    commit_point(db)
    oid, rid, cnid, w1_id, u2_id = g.O.id, g.R.id, g.CN.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.void_return(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, void_note="Wrong item")

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderReturn, rid).status == "pending"
    # Then 4
    assert reread(db, AccountInvoice, cnid).invoice_status == "confirmed"


@xfail(3168)
def test_pos_vr_11__schema_blank_note_refused():
    """POS-VR-11 — schema: a whitespace-only void note is refused.
    Rules: void_return VR7 [BUG-3168]."""
    # Then 1
    with pytest.raises(ValidationError):
        PurchaseOrderReturnVoidRequest(void_note="   ")


@xfail(3168)
def test_pos_vr_12__schema_note_trimmed():
    """POS-VR-12 — schema: the void note is trimmed.
    Rules: void_return VR7 [BUG-3168]."""
    result = PurchaseOrderReturnVoidRequest(void_note=" Wrong item ")

    # Then 1
    assert result.void_note == "Wrong item"


def test_pos_vr_13__schema_empty_note_refused():
    """POS-VR-13 — schema: an empty void note is refused.
    Rules: void_return VR7 (holds today and after BUG-3168)."""
    # Then 1
    with pytest.raises(ValidationError):
        PurchaseOrderReturnVoidRequest(void_note="")


@xfail(3176)
def test_pos_vr_14__response_empty_warnings(db, s):
    """POS-VR-14 — the cancelled return's response carries empty warnings.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = crbase(db, s)
    commit_point(db)

    result = VR(db, s, g, "Wrong item")

    # Then 1
    assert WARN(result) == []


# --------------------------------------------------------------------------- #
# list_returns / get_return
# --------------------------------------------------------------------------- #


def test_pos_lrt_01__list_w2_order_404(db, s):
    """POS-LRT-01 — list: a W2 order → 404 first; no rollback.
    Rules: list_returns LRT1; TC6."""
    O9 = po(db, s, "9", "9", **PROJ)
    ret(db, s, O9, "9")
    commit_point(db)
    X, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.list_returns(db, po_id=O9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_pos_lrt_02__list_order_returns(db, s):
    """POS-LRT-02 — list: the order's returns; a read.
    Rules: list_returns LRT2; TC6."""
    O = po(db, s, "1", **PROJ)
    R1 = ret(db, s, O, "1")
    R2 = ret(db, s, O, "2", **COMPLETED(s))
    O2 = po(db, s, "2", **PROJ)
    ret(db, s, O2, "3")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_returns(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert sorted(r.id for r in result) == sorted([R1.id, R2.id])
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_pos_lrt_03__get_without_lock(db, s):
    """POS-LRT-03 — get: returns the return without a lock.
    Rules: get_return LRT2; TC6."""
    O = po(db, s, "1", **PROJ)
    R = ret(db, s, O, "1")
    oid, rid, w1_id = O.id, R.id, s.W1.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        with spies(db) as (cm, rb):
            result = svc.get_return(db, po_id=oid, return_id=rid, workspace_id=w1_id)

    # Then 1
    assert result.id == rid
    # Then 2
    assert rec.no_lock()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0


def test_pos_lrt_04__get_return_of_other_order_404(db, s):
    """POS-LRT-04 — get: a return of another order → 404.
    Rules: get_return LRT2."""
    O = po(db, s, "1", **PROJ)
    O2 = po(db, s, "2", **PROJ)
    R2 = ret(db, s, O2, "2")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_return(db, po_id=O.id, return_id=R2.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R2.id)


def test_pos_lrt_05__get_w0_order_404(db, s):
    """POS-LRT-05 — get: a W0 order → 404 before the return is read.
    Rules: get_return LRT1."""
    O0 = po(db, s, "0", "0", **PROJ)
    R0 = ret(db, s, O0, "0")
    po(db, s, "1")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_return(db, po_id=O0.id, return_id=R0.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)


# --------------------------------------------------------------------------- #
# list_active_orders_for_context
# --------------------------------------------------------------------------- #


def AO(db, s, **scope):
    """Section convention AO(**scope)."""
    return svc.list_active_orders_for_context(db, workspace_id=s.W1.id, **scope)


def mk_machine(db, s):
    from app.models.machine import Machine

    return _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Press 4", is_deleted=False))


def mk_wot(db, s):
    """A work-order type of W1 (WorkOrder needs one; the spec does not describe it)."""
    from app.models.work_order_type import WorkOrderType

    return _add(db, WorkOrderType(workspace_id=s.W1.id, name="Maintenance"))


def wo(db, s, wot, n, st, **but):
    """Card shorthand wo(n, st) of AO-18 (plus the type and factory every WorkOrder needs)."""
    from app.models.work_order import WorkOrder

    fields = {
        "workspace_id": s.W1.id,
        "work_order_number": f"WO-{s.TAG}-{n}",
        "work_order_type_id": wot.id,
        "factory_id": s.F1.id,
        "title": "Oil change",
        "status": st,
        "cost": None,
        "is_deleted": False,
    }
    fields.update(but)
    return _add(db, WorkOrder(**fields))


def test_pos_ao_01__no_scope_400(db, s):
    """POS-AO-01 — no scope → 400.
    Rules: list_active_orders_for_context AO1."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Provide exactly one of machine_id, factory_id, project_component_id"


def test_pos_ao_02__two_scopes_400(db, s):
    """POS-AO-02 — two scopes → 400.
    Rules: list_active_orders_for_context AO1."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, factory_id=s.F1.id, project_component_id=5)
    # Then 2
    assert exc.value.detail == "Provide exactly one of machine_id, factory_id, project_component_id"


def test_pos_ao_03__zero_id_counts(db, s):
    """POS-AO-03 — an id of 0 counts as given.
    Rules: list_active_orders_for_context AO1."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, machine_id=0, factory_id=s.F1.id)
    # Then 2
    assert exc.value.status_code == 400


def test_pos_ao_04__w2_factory_404(db, s):
    """POS-AO-04 — a W2 factory → 404.
    Rules: list_active_orders_for_context AO2."""
    po(db, s, "9", "9")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, factory_id=s.F9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory not found"


def test_pos_ao_05__w0_factory_404(db, s):
    """POS-AO-05 — a W0 factory → 404.
    Rules: list_active_orders_for_context AO2."""
    po(db, s, "0", "0")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, factory_id=s.F0.id)
    # Then 2
    assert exc.value.detail == "Factory not found"


def test_pos_ao_06__missing_machine_404(db, s):
    """POS-AO-06 — a missing machine → 404.
    Rules: list_active_orders_for_context AO2."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, machine_id=MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found"


def test_pos_ao_07__missing_component_404(db, s):
    """POS-AO-07 — a missing project component → 404.
    Rules: list_active_orders_for_context AO2."""
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        AO(db, s, project_component_id=MISSING)
    # Then 2
    assert exc.value.detail == "Project component not found"


def test_pos_ao_08__factory_scope_row_fields(db, s):
    """POS-AO-08 — factory scope: the factory's open POs with every row field; another factory's not listed.
    Rules: list_active_orders_for_context AO3, AO4, AO6 (part that holds today)."""
    F1b = _add(db, Factory(workspace_id=s.W1.id, name="Second Store", abbreviation="SS1", is_active=True, is_deleted=False))
    O = po(db, s, "1", current_status_id=s.SP1.id)
    po(db, s, "2", destination_id=F1b.id)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].order_kind == "purchase"
    assert result[0].id == O.id
    assert result[0].number == O.po_number
    assert result[0].summary == "Bearings for Press 4"
    # Then 3
    assert result[0].current_status_id == s.SP1.id
    assert result[0].status_name == "Planning"
    assert result[0].total_amount == Decimal("5000.00")
    assert result[0].created_at == O.created_at


def test_pos_ao_09__last_stage_skipped(db, s):
    """POS-AO-09 — a PO at the last stage of its workflow is skipped.
    Rules: list_active_orders_for_context AO3."""
    po(db, s, "1", **COMPLETE(s))
    O2 = po(db, s, "2", current_status_id=s.SR1.id)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O2.id]


def test_pos_ao_10__no_workflow_never_skipped(db, s):
    """POS-AO-10 — a PO with no workflow is never skipped.
    Rules: list_active_orders_for_context AO3."""
    O1 = po(db, s, "1", **COMPLETE(s), order_workflow_id=None)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O1.id]


def test_pos_ao_11__empty_sequence_never_skips(db, s):
    """POS-AO-11 — a workflow with an empty sequence never skips.
    Rules: list_active_orders_for_context AO3."""
    s.WF1.status_sequence = []
    db.flush()
    O1 = po(db, s, "1", **COMPLETE(s))
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O1.id]


def test_pos_ao_12__non_integer_last_never_skips(db, s):
    """POS-AO-12 — a sequence ending in a non-integer never skips.
    Rules: list_active_orders_for_context AO3."""
    s.WF1.status_sequence = [s.SD1.id, "done"]
    db.flush()
    O1 = po(db, s, "1", **COMPLETE(s))
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O1.id]


@xfail(3173)
def test_pos_ao_13__voided_po_not_listed(db, s):
    """POS-AO-13 — a voided PO is not listed.
    Rules: list_active_orders_for_context AO6 [BUG-3173]."""
    po(db, s, "1", **VOIDED(s))
    O2 = po(db, s, "2")
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O2.id]


def test_pos_ao_14__foreign_pos_not_listed(db, s):
    """POS-AO-14 — W0 and W2 POs pointing at the W1 factory are not listed.
    Rules: list_active_orders_for_context AO3; HR-16."""
    po(db, s, "0", "0", destination_id=s.F1.id)
    O1 = po(db, s, "1")
    po(db, s, "9", "9", destination_id=s.F1.id)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O1.id]


def test_pos_ao_15__soft_deleted_factory_lists(db, s):
    """POS-AO-15 — a soft-deleted factory still lists its open POs.
    Rules: list_active_orders_for_context AO2."""
    Fd = _add(db, Factory(workspace_id=s.W1.id, name="Old Store", abbreviation="OS1", is_active=False, is_deleted=True))
    O1 = po(db, s, "1", destination_id=Fd.id)
    commit_point(db)

    result = AO(db, s, factory_id=Fd.id)

    # Then 1
    assert [r.id for r in result] == [O1.id]


def test_pos_ao_16__newest_first(db, s):
    """POS-AO-16 — rows are sorted newest first.
    Rules: list_active_orders_for_context AO10."""
    O1 = po(db, s, "1")
    O1.created_at = T2
    db.flush()
    O2 = po(db, s, "2")
    O2.created_at = T0
    db.flush()
    O3 = po(db, s, "3")
    O3.created_at = T1
    db.flush()
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result] == [O1.id, O3.id, O2.id]


def test_pos_ao_17__transfers_listed_until_completed(db, s):
    """POS-AO-17 — transfers touching the scope are listed until completed.
    Rules: list_active_orders_for_context AO5, AO10."""
    from app.models.transfer_order import TransferOrder

    ta = {
        "workspace_id": s.W1.id, "transfer_number": f"TO-{s.TAG}-1", "source_location_type": "storage",
        "source_location_id": s.F1.id, "destination_location_type": "machine", "destination_location_id": MISSING,
        "current_status_id": s.SP1.id, "description": "To press", "created_at": T1, "completed_at": None,
        "created_by": s.U1.id,
    }
    TA = _add(db, TransferOrder(**ta))
    TB = _add(db, TransferOrder(**{**ta, "transfer_number": f"TO-{s.TAG}-2", "source_location_type": "machine", "source_location_id": MISSING, "destination_location_type": "storage", "destination_location_id": s.F1.id, "description": "From press"}))
    _add(db, TransferOrder(**{**ta, "transfer_number": f"TO-{s.TAG}-3", "completed_at": T2}))
    _add(db, TransferOrder(**{**ta, "workspace_id": s.W2.id, "transfer_number": f"TO-{s.TAG}-4", "source_location_id": s.F9.id, "current_status_id": s.SP9.id}))
    O1 = po(db, s, "1", created_at=T1)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert result[0].order_kind == "purchase"
    assert result[0].id == O1.id
    # Then 2
    assert {r.id for r in result if r.order_kind == "transfer"} == {TA.id, TB.id}
    # Then 3
    ra = next(r for r in result if r.order_kind == "transfer" and r.id == TA.id)
    assert ra.number == TA.transfer_number
    assert ra.summary == "To press"
    assert ra.current_status_id == s.SP1.id
    assert ra.total_amount is None
    # Then 4
    assert len(result) == 3


# [claude] POS-AO-18
def test_pos_ao_18__machine_scope_work_orders(db, s):
    """POS-AO-18 — machine scope lists in-flight work orders; factory scope lists none.
    Rules: list_active_orders_for_context AO7."""
    M1 = mk_machine(db, s)
    wot = mk_wot(db, s)
    WD = wo(db, s, wot, "1", "DRAFT", machine_id=M1.id)
    WP = wo(db, s, wot, "2", "IN_PROGRESS", machine_id=M1.id, cost=Decimal("1200.00"), title="Belt swap")
    wo(db, s, wot, "3", "COMPLETED", machine_id=M1.id)
    wo(db, s, wot, "4", "VOIDED", machine_id=M1.id)
    wo(db, s, wot, "5", "IN_PROGRESS", machine_id=M1.id, is_deleted=True)
    commit_point(db)

    result = AO(db, s, machine_id=M1.id)

    # Then 1
    assert {r.id for r in result if r.order_kind == "work"} == {WD.id, WP.id}
    # Then 2
    rp = next(r for r in result if r.order_kind == "work" and r.id == WP.id)
    assert rp.number == WP.work_order_number
    assert rp.summary == "Belt swap"
    assert rp.current_status_id is None
    assert rp.status_name == "In Progress"
    assert rp.total_amount == Decimal("1200.00")
    # Then 3
    rd = next(r for r in result if r.order_kind == "work" and r.id == WD.id)
    assert rd.status_name == "Draft"
    assert rd.total_amount is None
    # Then 4
    assert [r for r in AO(db, s, factory_id=s.F1.id) if r.order_kind == "work"] == []


# [claude] POS-AO-19
@xfail(3166)
def test_pos_ao_19__old_in_flight_behind_1000(db, s):
    """POS-AO-19 — machine scope: an old in-flight work order behind 1,000 newer ones is listed.
    Rules: list_active_orders_for_context AO9 [BUG-3166]; HR-5."""
    from sqlalchemy import insert

    from app.models.enums import WorkOrderPriorityEnum
    from app.models.work_order import WorkOrder

    M1 = mk_machine(db, s)
    wot = mk_wot(db, s)
    W_old = wo(db, s, wot, "old", "IN_PROGRESS", title="Old job", machine_id=M1.id, created_at=T0)
    db.execute(
        insert(WorkOrder),
        [
            {
                "workspace_id": s.W1.id, "work_order_number": f"WO-{s.TAG}-{i}", "work_order_type_id": wot.id,
                "factory_id": s.F1.id, "title": "Oil change", "status": "COMPLETED", "machine_id": M1.id,
                "priority": WorkOrderPriorityEnum.MEDIUM, "is_deleted": False, "is_active": True,
                "created_at": T1 + timedelta(seconds=i),
            }
            for i in range(1000)
        ],
    )
    db.flush()
    commit_point(db)

    result = AO(db, s, machine_id=M1.id)

    # Then 1
    assert [r.id for r in result if r.order_kind == "work"] == [W_old.id]


# [claude] POS-AO-20
def test_pos_ao_20__component_scope(db, s):
    """POS-AO-20 — component scope: in-flight work orders of the component (today's behaviour).
    Rules: list_active_orders_for_context AO3, AO8 (revisit after launch)."""
    from app.models.project import Project
    from app.models.project_component import ProjectComponent

    PJ = _add(db, Project(workspace_id=s.W1.id, factory_id=s.F1.id, name="Plant upgrade", description="Main"))
    PC = _add(db, ProjectComponent(workspace_id=s.W1.id, project_id=PJ.id, name="Foundation"))
    OP = po(db, s, "1", destination_type="project", destination_id=PC.id)
    wot = mk_wot(db, s)
    WD = wo(db, s, wot, "1", "DRAFT", title="Pour", project_component_id=PC.id)
    wo(db, s, wot, "2", "COMPLETED", title="Pour", project_component_id=PC.id)
    commit_point(db)

    result = AO(db, s, project_component_id=PC.id)

    # Then 1
    assert sorted((r.order_kind, r.id) for r in result) == [("purchase", OP.id), ("work", WD.id)]


# [claude] POS-AO-22
def test_pos_ao_22__other_component_skipped(db, s):
    """POS-AO-22 — component scope: a work order of another component, or of none, is skipped.
    Rules: list_active_orders_for_context AO8 (revisit after launch); branch map 1176."""
    from app.models.project import Project
    from app.models.project_component import ProjectComponent

    PJ = _add(db, Project(workspace_id=s.W1.id, factory_id=s.F1.id, name="Plant upgrade", description="Main"))
    PC = _add(db, ProjectComponent(workspace_id=s.W1.id, project_id=PJ.id, name="Foundation"))
    PJ2 = _add(db, Project(workspace_id=s.W1.id, factory_id=s.F1.id, name="Plant upgrade 2", description="Main"))
    PC2 = _add(db, ProjectComponent(workspace_id=s.W1.id, project_id=PJ2.id, name="Roof"))
    wot = mk_wot(db, s)
    WD = wo(db, s, wot, "1", "DRAFT", title="Pour", project_component_id=PC.id)
    WO2 = wo(db, s, wot, "2", "IN_PROGRESS", title="Pour", project_component_id=PC2.id)
    WN = wo(db, s, wot, "3", "DRAFT", title="Pour", project_component_id=None)
    commit_point(db)

    result = AO(db, s, project_component_id=PC.id)

    # Then 1
    assert [(r.order_kind, r.id) for r in result if r.order_kind == "work"] == [("work", WD.id)]
    # Then 2
    assert not any(r.order_kind == "work" and r.id in {WO2.id, WN.id} for r in result)


def test_pos_ao_21__read_writes_nothing(db, s):
    """POS-AO-21 — a read: no commit, no rollback, nothing written.
    Rules: list_active_orders_for_context AO10; TC6."""
    po(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db
    # Then 4
    assert not db.new


def test_pos_ao_23__machine_scope_pos_and_transfers(db, s):
    """POS-AO-23 — machine scope: POs to the machine and transfers touching it.
    Rules: list_active_orders_for_context AO3, AO5."""
    from app.models.transfer_order import TransferOrder

    M1 = mk_machine(db, s)
    OM = po(db, s, "1", destination_type="machine", destination_id=M1.id)
    po(db, s, "2")
    tm1 = {
        "workspace_id": s.W1.id, "transfer_number": f"TO-{s.TAG}-1", "source_location_type": "storage",
        "source_location_id": s.F1.id, "destination_location_type": "machine", "destination_location_id": M1.id,
        "current_status_id": s.SP1.id, "description": "To press", "created_at": T1, "completed_at": None,
        "created_by": s.U1.id,
    }
    TM1 = _add(db, TransferOrder(**tm1))
    TM2 = _add(db, TransferOrder(**{**tm1, "transfer_number": f"TO-{s.TAG}-2", "source_location_type": "machine", "source_location_id": M1.id, "destination_location_type": "storage", "destination_location_id": s.F1.id, "description": "From press"}))
    _add(db, TransferOrder(**{**tm1, "transfer_number": f"TO-{s.TAG}-3", "destination_location_type": "storage", "destination_location_id": s.F1.id}))
    commit_point(db)

    result = AO(db, s, machine_id=M1.id)

    # Then 1
    assert {(r.order_kind, r.id) for r in result if r.order_kind != "work"} == {("purchase", OM.id), ("transfer", TM1.id), ("transfer", TM2.id)}


# [claude] POS-AO-24
def test_pos_ao_24__component_scope_pos_and_transfers(db, s):
    """POS-AO-24 — component scope: POs to the component and transfers touching it.
    Rules: list_active_orders_for_context AO3, AO5 (revisit after launch)."""
    from app.models.project import Project
    from app.models.project_component import ProjectComponent
    from app.models.transfer_order import TransferOrder

    PJ = _add(db, Project(workspace_id=s.W1.id, factory_id=s.F1.id, name="Plant upgrade", description="Main"))
    PC = _add(db, ProjectComponent(workspace_id=s.W1.id, project_id=PJ.id, name="Foundation"))
    OP = po(db, s, "1", destination_type="project", destination_id=PC.id)
    po(db, s, "2")
    tp1 = {
        "workspace_id": s.W1.id, "transfer_number": f"TO-{s.TAG}-1", "source_location_type": "storage",
        "source_location_id": s.F1.id, "destination_location_type": "project", "destination_location_id": PC.id,
        "current_status_id": s.SP1.id, "description": "To site", "created_at": T1, "completed_at": None,
        "created_by": s.U1.id,
    }
    TP1 = _add(db, TransferOrder(**tp1))
    TP2 = _add(db, TransferOrder(**{**tp1, "transfer_number": f"TO-{s.TAG}-2", "source_location_type": "project", "source_location_id": PC.id, "destination_location_type": "storage", "destination_location_id": s.F1.id, "description": "From site"}))
    commit_point(db)

    result = AO(db, s, project_component_id=PC.id)

    # Then 1
    assert {(r.order_kind, r.id) for r in result if r.order_kind != "work"} == {("purchase", OP.id), ("transfer", TP1.id), ("transfer", TP2.id)}


def test_pos_ao_25__one_stage_workflow_skipped(db, s):
    """POS-AO-25 — a one-stage workflow: its only stage is the last, so the PO is skipped.
    Rules: list_active_orders_for_context AO3."""
    s.WF1.status_sequence = [s.SC1.id]
    db.flush()
    po(db, s, "1", **COMPLETE(s))
    O2 = po(db, s, "2", current_status_id=s.SR1.id)
    commit_point(db)

    result = AO(db, s, factory_id=s.F1.id)

    # Then 1
    assert [r.id for r in result if r.order_kind == "purchase"] == [O2.id]


# --------------------------------------------------------------------------- #
# delete_purchase_order
# --------------------------------------------------------------------------- #


@xfail(2888)
def test_pos_x_01__deleted_with_draft(db, s):
    """POS-X-01 — an order with a draft invoice is deleted with it; committed.
    Rules: delete_purchase_order X1; TC1."""
    O = po(db, s, "1", **READY)
    oid = O.id
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True)
    vid = V.id
    commit_point(db)

    result = svc.delete_purchase_order(db, po_id=oid, workspace_id=s.W1.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert count_where(db, PurchaseOrder, PurchaseOrder.id == oid) == 0
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.id == vid) == 0


def test_pos_x_02__w2_order_404(db, s):
    """POS-X-02 — a W2 order → 404, rolled back.
    Rules: delete_purchase_order X1; TC3."""
    po(db, s, "1")
    O9 = po(db, s, "9", "9")
    commit_point(db)
    o9_before = snap(db, O9)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.delete_purchase_order(db, po_id=O9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, O9) == o9_before


def test_pos_x_03__recorded_receiving_400(db, s):
    """POS-X-03 — recorded receiving → 400.
    Rules: delete_purchase_order X1."""
    O = po(db, s, "1")
    poline(db, s, O, 1, quantity_received=Decimal("3.00"))
    commit_point(db)
    o_before = snap(db, O)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a purchase order with recorded receiving — void the order instead"
    # Then 4
    assert snap(db, O) == o_before


def test_pos_x_04__receiving_history_400(db, s):
    """POS-X-04 — receiving history → 400.
    Rules: delete_purchase_order X1."""
    O = po(db, s, "1")
    _add(db, PoReceiveEvent(workspace_id=s.W1.id, purchase_order_id=O.id, event_type="receive", performed_by=s.U1.id, created_at=T0))
    commit_point(db)
    o_before = snap(db, O)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == "Cannot delete a purchase order with receiving history — void the order instead"
    # Then 3
    assert snap(db, O) == o_before


@xfail(2888)
def test_pos_x_05__finalized_invoice_blocks_delete(db, s):
    """POS-X-05 — a finalized invoice blocks the delete.
    Rules: delete_purchase_order X1 [BUG-2888]."""
    O = po(db, s, "1", **READY)
    V = inv(db, s, O, linked=True, **FINALIZED)
    commit_point(db)
    v_before = snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_purchase_order(db, po_id=O.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a purchase order with a finalized invoice — void the order instead"
    # Then 4
    assert snap(db, V) == v_before


@xfail(1195)
def test_pos_x_06__delete_takes_user_and_audits(db, s):
    """POS-X-06 — the delete takes `user_id` and leaves an audit row.
    Rules: delete_purchase_order X2 [BUG-1195]."""
    O = po(db, s, "1")
    oid = O.id
    commit_point(db)

    result = svc.delete_purchase_order(db, po_id=oid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert count_where(db, WorkspaceAuditLog, WorkspaceAuditLog.workspace_id == s.W1.id) == 1


def test_pos_x_07__failing_commit_keeps_order(db, s):
    """POS-X-07 — a failing commit keeps the order.
    Rules: delete_purchase_order X1; TC4."""
    O = po(db, s, "1")
    commit_point(db)
    oid, w1_id = O.id, s.W1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_purchase_order(db, po_id=oid, workspace_id=w1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, PurchaseOrder, PurchaseOrder.id == oid) == 1


def test_pos_x_08__plain_delete_committed(db, s):
    """POS-X-08 — an order with no invoice and no receiving is deleted; committed.
    Rules: delete_purchase_order X1; TC1 (holds today and after BUG-2888)."""
    O = po(db, s, "1")
    oid = O.id
    L = poline(db, s, O, 1)
    lid = L.id
    commit_point(db)

    with spies(db) as (cm, _rb):
        result = svc.delete_purchase_order(db, po_id=oid, workspace_id=s.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 1
    db.rollback()
    # Then 3
    assert count_where(db, PurchaseOrder, PurchaseOrder.id == oid) == 0
    # Then 4
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.id == lid) == 0


# --------------------------------------------------------------------------- #
# add_item
# --------------------------------------------------------------------------- #


def NEWLINE(s):
    """Section convention NEWLINE."""
    return PurchaseOrderItemCreate(item_id=s.I1b.id, quantity_ordered=Decimal("5"), unit_price=Decimal("300.00"))


def test_pos_ai_01__line_added_order_stamped(db, s):
    """POS-AI-01 — the line is added, the order stamped; committed.
    Rules: add_item AI1, AI2, AI3; TC1, TC2."""
    O = po(db, s, "1")
    commit_point(db)

    result = svc.add_item(db, po_id=O.id, item_in=NEWLINE(s), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, PurchaseOrderItem)
    assert result.purchase_order_id == O.id
    lid = result.id
    db.rollback()
    # Then 3
    line = reread(db, PurchaseOrderItem, lid)
    assert line.item_id == s.I1b.id
    assert line.quantity_ordered == Decimal("5.00")
    # Then 4
    assert reread(db, PurchaseOrder, O.id).items_updated_at == NOW


def test_pos_ai_02__no_user_no_invoice_step(db, s):
    """POS-AI-02 — without `user_id` no invoice step runs.
    Rules: add_item AI2."""
    O = po(db, s, "1", supplier_confirmed=True)
    V = inv(db, s, O, linked=True)
    commit_point(db)

    svc.add_item(db, po_id=O.id, item_in=NEWLINE(s), workspace_id=s.W1.id)

    db.rollback()
    # Then 1
    o = reread(db, PurchaseOrder, O.id)
    assert o.invoice_id == V.id
    assert o.items_updated_at == NOW
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.id == V.id) == 1


def test_pos_ai_03__with_user_invoice_step_runs(db, s):
    """POS-AI-03 — with `user_id` the invoice step runs (an unconfirmed order loses its draft).
    Rules: add_item AI2; SD2."""
    O = po(db, s, "1", supplier_confirmed=True)
    V = inv(db, s, O, linked=True)
    vid = V.id
    commit_point(db)

    svc.add_item(db, po_id=O.id, item_in=NEWLINE(s), workspace_id=s.W1.id, user_id=s.U2.id)

    db.rollback()
    # Then 1
    assert count_where(db, AccountInvoice, AccountInvoice.id == vid) == 0
    # Then 2
    assert reread(db, PurchaseOrder, O.id).invoice_id is None


def test_pos_ai_04__missing_order_404(db, s):
    """POS-AI-04 — a missing order → 404, rolled back.
    Rules: add_item AI1, AI3; TC3."""
    po(db, s, "1")
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.add_item(db, po_id=MISSING, item_in=NEWLINE(s), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Purchase order not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


# [claude] POS-AI-05
def test_pos_ai_05__integrity_error_items_phase(db, s):
    """POS-AI-05 — an IntegrityError is translated with the items phase.
    Rules: add_item AI3."""
    O = po(db, s, "1")
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "add_item", side_effect=IERR("violates foreign key", "23503", "purchase_order_items", "item_id")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.add_item(db, po_id=O.id, item_in=NEWLINE(s), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def test_pos_ai_06__items_confirmed_400(db, s):
    """POS-AI-06 — items confirmed → the manager's 400.
    Rules: add_item AI1."""
    O = po(db, s, "1", items_confirmed=True)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, po_id=O.id, item_in=NEWLINE(s), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order items are confirmed"
    # Then 4
    assert counts(db) == before


def test_pos_ai_07__failing_commit_no_line(db, s):
    """POS-AI-07 — a failing commit saves no line.
    Rules: add_item AI3; TC4."""
    O = po(db, s, "1")
    commit_point(db)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id
    item = NEWLINE(s)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_item(db, po_id=oid, item_in=item, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == oid) == 0
    # Then 4
    assert reread(db, PurchaseOrder, oid).items_updated_at is None


# --------------------------------------------------------------------------- #
# update_item
# --------------------------------------------------------------------------- #


def test_pos_ui_01__line_updated_order_stamped(db, s):
    """POS-UI-01 — the line is updated, the order stamped; committed.
    Rules: update_item UI1, UI2, UI3; TC1, TC2."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)

    result = svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == L.id
    db.rollback()
    # Then 3
    assert reread(db, PurchaseOrderItem, L.id).unit_price == Decimal("450.00")
    # Then 4
    assert reread(db, PurchaseOrder, O.id).items_updated_at == NOW


def test_pos_ui_02__no_user_not_stamped(db, s):
    """POS-UI-02 — without `user_id` the order is not stamped.
    Rules: update_item UI2."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)

    svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=s.W1.id)

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, L.id).unit_price == Decimal("450.00")
    # Then 2
    assert reread(db, PurchaseOrder, O.id).items_updated_at is None


def test_pos_ui_03__w2_line_404(db, s):
    """POS-UI-03 — a W2 line → 404, rolled back.
    Rules: update_item UI1, UI3; TC3."""
    O9 = po(db, s, "9", "9")
    L9 = poline(db, s, O9, 1)
    commit_point(db)
    l9_before = snap(db, L9)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.update_item(db, item_id=L9.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("1.00")), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Purchase order item not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, L9) == l9_before


@xfail(2887)
def test_pos_ui_04__schema_quantity_received_refused():
    """POS-UI-04 — schema: a body with `quantity_received` is refused.
    Rules: update_item UI1 [BUG-2887]."""
    # Then 1
    with pytest.raises(ValidationError):
        PurchaseOrderItemUpdate(quantity_received=Decimal("3"))


# [claude] POS-UI-05
def test_pos_ui_05__integrity_error_items_phase(db, s):
    """POS-UI-05 — an IntegrityError is translated with the items phase.
    Rules: update_item UI3."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)

    with patch.object(mgr, "update_item", side_effect=IERR("null value in column", "23502", "purchase_order_items", "unit_price")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."


def test_pos_ui_06__failing_commit_old_price(db, s):
    """POS-UI-06 — a failing commit keeps the old price.
    Rules: update_item UI3; TC4."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)
    lid, w1_id, u2_id = L.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_item(db, item_id=lid, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderItem, lid).unit_price == Decimal("500.00")


# --------------------------------------------------------------------------- #
# remove_item
# --------------------------------------------------------------------------- #


def test_pos_ri_01__line_removed_readable(db, s):
    """POS-RI-01 — the line is removed and returned readable; the order stamped; committed.
    Rules: remove_item RI1; TC1."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    lid = L.id
    commit_point(db)

    result = svc.remove_item(db, item_id=lid, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.id == lid
    assert result.line_number == 1
    db.rollback()
    # Then 2
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.id == lid) == 0
    # Then 3
    assert reread(db, PurchaseOrder, O.id).items_updated_at == NOW


def test_pos_ri_02__no_user_not_stamped(db, s):
    """POS-RI-02 — without `user_id` the order is not stamped.
    Rules: remove_item RI1."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)

    svc.remove_item(db, item_id=L.id, workspace_id=s.W1.id)

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrder, O.id).items_updated_at is None


def test_pos_ri_03__missing_line_404(db, s):
    """POS-RI-03 — a missing line → 404, rolled back.
    Rules: remove_item RI1; TC3."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)
    l_before = snap(db, L)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Purchase order item not found"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert snap(db, L) == l_before


def test_pos_ri_04__failing_commit_keeps_line(db, s):
    """POS-RI-04 — a failing commit keeps the line.
    Rules: remove_item RI1; TC4."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)
    lid, w1_id, u2_id = L.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_item(db, item_id=lid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.id == lid) == 1


# [claude] POS-RI-05
def test_pos_ri_05__integrity_error_items_phase(db, s):
    """POS-RI-05 — an IntegrityError is rolled back and translated with the items phase.
    Rules: remove_item RI1 (errors as AI3); _handle_item_integrity_error IE4; TC3."""
    O = po(db, s, "1")
    L = poline(db, s, O, 1)
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "remove_item", side_effect=IERR("violates foreign key", "23503", "purchase_order_items", "item_id")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with spies(db) as (_cm, rb):
                svc.remove_item(db, item_id=L.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."
    # Then 4
    assert isinstance(exc.value.__cause__, IntegrityError)
    # Then 5
    assert X not in db
    # Then 6
    assert rb.call_count >= 1
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert count_where(db, PurchaseOrderItem, PurchaseOrderItem.id == L.id) == 1


# --------------------------------------------------------------------------- #
# sync_items
# --------------------------------------------------------------------------- #


def SYNC(remove_ids, updates, additions):
    """Section convention SYNC(remove_ids, updates, additions)."""
    return PurchaseOrderItemSyncRequest(remove_ids=remove_ids, updates=updates, additions=additions)


def SY(db, s, O, body, **k):
    """Section convention SY(body, **k)."""
    return svc.sync_items(db, po_id=O.id, sync_in=body, workspace_id=s.W1.id, **k)


def line_count(db, oid):
    return count_where(db, PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == oid)


def test_pos_sy_01__addition_saved_stamped(db, s):
    """POS-SY-01 — an addition is saved and the order stamped; committed.
    Rules: sync_items SY1, SY3, SY4 (side that holds today); TC1, TC2."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)

    result = SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == O.id
    db.rollback()
    # Then 3
    assert line_count(db, O.id) == 2
    # Then 4
    assert reread(db, PurchaseOrder, O.id).items_updated_at == NOW


@xfail(3179)
def test_pos_sy_02__one_commit(db, s):
    """POS-SY-02 — the lines and the invoice step are one commit.
    Rules: sync_items SY2 [BUG-3179]."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)

    with spies(db) as (cm, _rb):
        result = SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)

    # Then 1
    assert result.id == O.id
    # Then 2
    assert cm.call_count == 1


@xfail(3179)
def test_pos_sy_03__invoice_failure_keeps_lines_unsaved(db, s):
    """POS-SY-03 — an invoice-step failure keeps the lines unsaved.
    Rules: sync_items SY2 [BUG-3179]."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, paid_amount=Decimal("100.00"), payment_status="partial")
    cash(db, s, V, "100.00")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    db.rollback()
    # Then 3
    assert line_count(db, O.id) == 1


def test_pos_sy_04__invoice_refusal_reaches_caller(db, s):
    """POS-SY-04 — an invoice-step refusal reaches the caller and the draft stays.
    Rules: sync_items SY3 (part that holds today and after BUG-3179)."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, paid_amount=Decimal("100.00"), payment_status="partial")
    cash(db, s, V, "100.00")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.id == V.id) == 1


@xfail(3165)
def test_pos_sy_05__empty_request_not_stamped(db, s):
    """POS-SY-05 — an empty request does not stamp the order.
    Rules: sync_items SY4 [BUG-3165]; HR-9."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)

    result = SY(db, s, O, SYNC([], [], []), user_id=s.U2.id)

    # Then 1
    assert result.id == O.id
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrder, O.id).items_updated_at is None


def test_pos_sy_06__no_user_no_step(db, s):
    """POS-SY-06 — without `user_id`: no invoice step, no stamp.
    Rules: sync_items SY3."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True)
    commit_point(db)

    SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]))

    db.rollback()
    # Then 1
    assert line_count(db, O.id) == 2
    # Then 2
    o = reread(db, PurchaseOrder, O.id)
    assert o.items_updated_at is None
    assert o.invoice_id == V.id


def test_pos_sy_07__no_supplier_no_step(db, s):
    """POS-SY-07 — no supplier: no invoice step, no stamp.
    Rules: sync_items SY3."""
    O = po(db, s, "1", account_id=None)
    poline(db, s, O, 1)
    commit_point(db)

    SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)

    db.rollback()
    # Then 1
    assert line_count(db, O.id) == 2
    # Then 2
    assert reread(db, PurchaseOrder, O.id).items_updated_at is None


def test_pos_sy_08__unknown_removal_404(db, s):
    """POS-SY-08 — the manager's 404 for an unknown removal id; rolled back.
    Rules: sync_items SY1; TC3."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, O, SYNC([MISSING], [], []), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Purchase order item {MISSING} not found"
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


def test_pos_sy_09__failing_commit_no_line(db, s):
    """POS-SY-09 — a failing commit saves no line.
    Rules: sync_items SY1; TC4."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id
    body = SYNC([], [], [NI(s.I1b, "5")])

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.sync_items(db, po_id=oid, sync_in=body, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert line_count(db, oid) == 1


# [claude] POS-SY-10
def test_pos_sy_10__line_phase_integrity_error(db, s):
    """POS-SY-10 — a line-phase IntegrityError is rolled back and translated with the items phase.
    Rules: sync_items SY1; _handle_item_integrity_error IE3; TC3."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "sync_items", side_effect=IERR("null value in column", "23502", "purchase_order_items", "quantity_ordered")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with spies(db) as (cm, rb):
                SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Order line data is incomplete (purchase_order_items.quantity_ordered). Refresh the page and try again."
    # Then 4
    assert isinstance(exc.value.__cause__, IntegrityError)
    # Then 5
    assert X not in db
    # Then 6
    assert cm.call_count == 0
    # Then 7
    assert rb.call_count >= 1
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)
    # Then 9
    assert line_count(db, O.id) == 1


# [claude] POS-SY-11
def test_pos_sy_11__invoice_step_integrity_error(db, s):
    """POS-SY-11 — an invoice-step IntegrityError is translated with the invoice phase.
    Rules: sync_items SY3; _handle_item_integrity_error IE4 (phase='invoice')."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    commit_point(db)

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=IERR("violates foreign key", "23503", "purchase_order_items", "item_id")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with spies(db) as (_cm, rb):
                SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."
    # Then 4
    assert isinstance(exc.value.__cause__, IntegrityError)
    # Then 5
    assert rb.call_count >= 1


# [claude] POS-SY-12
@xfail(3179)
def test_pos_sy_12__invoice_step_error_undoes_lines(db, s):
    """POS-SY-12 — an invoice-step IntegrityError undoes the line changes and every pending row.
    Rules: sync_items SY2 [BUG-3179], SY3; TC3."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=IERR("violates foreign key", "23503", "purchase_order_items", "item_id")):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert X not in db
    db.rollback()
    # Then 4
    assert line_count(db, O.id) == 1
    # Then 5
    assert x_gone(db, x_id)


# [claude] POS-SY-13
def test_pos_sy_13__other_invoice_step_error_reraised(db, s):
    """POS-SY-13 — any other invoice-step error is rolled back and re-raised as the same object.
    Rules: sync_items SY3; TC2."""
    O = po(db, s, "1", supplier_confirmed=True)
    poline(db, s, O, 1)
    commit_point(db)
    boom = RuntimeError("sync boom")

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=boom):
        with pytest.raises(RuntimeError) as exc:
            with spies(db) as (_cm, rb):
                SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 1
    assert exc.value is boom
    # Then 2
    assert rb.call_count >= 1


# [claude] POS-SY-14
def test_pos_sy_14__line_phase_non_http_error(db, s):
    """POS-SY-14 — a non-HTTP error in the line phase is rolled back and re-raised as the same object.
    Rules: sync_items SY1; TC3."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    boom = RuntimeError("line boom")
    commit_point(db)
    X, x_id = mk_x(db)

    with patch.object(mgr, "sync_items", side_effect=boom):
        with pytest.raises(RuntimeError) as exc:
            with spies(db) as (cm, rb):
                SY(db, s, O, SYNC([], [], [NI(s.I1b, "5")]), user_id=s.U2.id)
    # Then 1
    assert exc.value is boom
    # Then 2
    assert X not in db
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count >= 1
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert line_count(db, O.id) == 1


# --------------------------------------------------------------------------- #
# get_items / list_events / list_approvers
# --------------------------------------------------------------------------- #


def test_pos_pt_01__get_items_by_line_number(db, s):
    """POS-PT-01 — get_items: lines by line number; a read.
    Rules: get_items PT1; TC6."""
    O = po(db, s, "1")
    L2 = poline(db, s, O, 2, item_id=s.I1b.id)
    L1 = poline(db, s, O, 1)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_items(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert [x.id for x in result] == [L1.id, L2.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


@xfail(2886)
def test_pos_pt_02__get_items_w2_order_404(db, s):
    """POS-PT-02 — get_items: a W2 order → 404.
    Rules: get_items PT1 [BUG-2886]."""
    O9 = po(db, s, "9", "9")
    poline(db, s, O9, 1)
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_items(db, po_id=O9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)


def test_pos_pt_03__list_events_newest_first(db, s):
    """POS-PT-03 — list_events: newest first; a read.
    Rules: list_events PT1, PT2; TC6."""
    O = po(db, s, "1")
    E1 = ev(db, s, O, T0, "note")
    E2 = ev(db, s, O, T2, "note")
    E3 = ev(db, s, O, T1, "note")
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, _rb):
        result = svc.list_events(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert [e[0].id for e in result] == [E2.id, E3.id, E1.id]
    # Then 2
    assert all(e[1] is not None and e[1].id == s.U1.id for e in result)
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert X in db


def test_pos_pt_04__list_approvers(db, s):
    """POS-PT-04 — list_approvers: the order's approvers; a read.
    Rules: list_approvers PT1, PT2; TC6."""
    O = po(db, s, "1")
    poappr(db, s, O, s.U1)
    poappr(db, s, O, s.U3)
    O2 = po(db, s, "2")
    poappr(db, s, O2, s.U2)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, _rb):
        result = svc.list_approvers(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert sorted(a[0].user_id for a in result) == sorted([s.U1.id, s.U3.id])
    # Then 2
    assert all(len(a) == 3 for a in result)
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# approval_summary_for
# --------------------------------------------------------------------------- #


def test_pos_as_01__summary_tuple(db, s):
    """POS-AS-01 — the manager's summary tuple; a read.
    Rules: approval_summary_for AS1; TC6."""
    O = po(db, s, "1", **READY)
    poappr(db, s, O, s.U1, approved=True)
    poappr(db, s, O, s.U3)
    commit_point(db)
    X, _ = mk_x(db)

    with spies(db) as (cm, _rb):
        result = svc.approval_summary_for(db, po_id=O.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 3
    assert result[0] == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert X in db


def test_pos_as_02__w2_order_404(db, s):
    """POS-AS-02 — a W2 order → 404.
    Rules: approval_summary_for AS1."""
    O9 = po(db, s, "9", "9")
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.approval_summary_for(db, po_id=O9.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)


# --------------------------------------------------------------------------- #
# add_approver
# --------------------------------------------------------------------------- #


def test_pos_aa_01__approver_added_and_told(db, s):
    """POS-AA-01 — the approver is added and told; committed.
    Rules: add_approver AA1, AA2, AA3; TC1, TC2."""
    O = po(db, s, "1")
    commit_point(db)

    result = svc.add_approver(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.user_id == s.U3.id
    assert result.purchase_order_id == O.id
    db.rollback()
    # Then 3
    apprs = rows_where(db, PurchaseOrderApprover, PurchaseOrderApprover.purchase_order_id == O.id)
    assert len(apprs) == 1
    assert apprs[0].user_id == s.U3.id
    # Then 4
    assert s.U3.id in recips(db)


def test_pos_aa_02__ready_order_others_told(db, s):
    """POS-AA-02 — a ready order: the other pending approvers are told again.
    Rules: add_approver AA2."""
    O = po(db, s, "1", **READY)
    poappr(db, s, O, s.U1)
    commit_point(db)

    svc.add_approver(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)

    db.rollback()
    # Then 1
    assert s.U3.id in recips(db)
    # Then 2
    assert any(n.recipient_user_id == s.U1.id and n.notification_type == "approval_pending" for n in notes(db))


def test_pos_aa_03__already_approver_409(db, s):
    """POS-AA-03 — already an approver → 409, rolled back.
    Rules: add_approver AA1, AA3; TC3."""
    O = po(db, s, "1")
    poappr(db, s, O, s.U3)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.add_approver(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


def test_pos_aa_04__inactive_member_400(db, s):
    """POS-AA-04 — an inactive member → 400.
    Rules: add_approver AA1."""
    O = po(db, s, "1")
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_approver(db, po_id=O.id, user_id=s.U4.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


def test_pos_aa_05__failing_commit_saves_nothing(db, s):
    """POS-AA-05 — a failing commit saves neither the approver nor the notification.
    Rules: add_approver AA3; TC4."""
    O = po(db, s, "1")
    before = commit_point(db)
    oid, u3_id, w1_id, u2_id = O.id, s.U3.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_approver(db, po_id=oid, user_id=u3_id, workspace_id=w1_id, assigned_by=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# remove_approver
# --------------------------------------------------------------------------- #


def test_pos_ra_01__removed_committed(db, s):
    """POS-RA-01 — removed, committed, returns None, nobody told.
    Rules: remove_approver RA1; TC1."""
    O = po(db, s, "1")
    P3 = poappr(db, s, O, s.U3)
    pid = P3.id
    commit_point(db)

    result = svc.remove_approver(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U2.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert count_where(db, PurchaseOrderApprover, PurchaseOrderApprover.id == pid) == 0
    # Then 3
    assert notes(db) == []


def test_pos_ra_02__not_approver_404(db, s):
    """POS-RA-02 — not an approver → 404, rolled back.
    Rules: remove_approver RA1; TC3."""
    O = po(db, s, "1")
    commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.remove_approver(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Approver not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_pos_ra_03__failing_commit_keeps_approver(db, s):
    """POS-RA-03 — a failing commit keeps the approver.
    Rules: remove_approver RA1; TC4."""
    O = po(db, s, "1")
    P3 = poappr(db, s, O, s.U3)
    commit_point(db)
    oid, pid, u3_id, w1_id, u2_id = O.id, P3.id, s.U3.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_approver(db, po_id=oid, user_id=u3_id, workspace_id=w1_id, performed_by=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, PurchaseOrderApprover, PurchaseOrderApprover.id == pid) == 1


# --------------------------------------------------------------------------- #
# set_approval
# --------------------------------------------------------------------------- #


def test_pos_sa_01__approval_committed(db, s):
    """POS-SA-01 — an approval is committed; nobody told, no invoice step.
    Rules: set_approval SA1; TC1, TC2."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    P3 = poappr(db, s, O, s.U3)
    commit_point(db)

    result = svc.set_approval(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, approved=True)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == P3.id
    assert result.approved is True
    db.rollback()
    # Then 3
    assert reread(db, PurchaseOrderApprover, P3.id).approved is True
    # Then 4
    assert notes(db) == []
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == O.id) == 0


def test_pos_sa_02__not_approver_403(db, s):
    """POS-SA-02 — not an approver → 403, rolled back.
    Rules: set_approval SA1; TC3."""
    O = po(db, s, "1", **READY)
    commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.set_approval(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, approved=True)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def test_pos_sa_03__approving_before_confirm_400(db, s):
    """POS-SA-03 — approving before the sections are confirmed → 400.
    Rules: set_approval SA1."""
    O = po(db, s, "1")
    P3 = poappr(db, s, O, s.U3)
    commit_point(db)
    p3_before = snap(db, P3)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_approval(db, po_id=O.id, user_id=s.U3.id, workspace_id=s.W1.id, approved=True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Confirm supplier, order details, and items before approving"
    # Then 4
    assert snap(db, P3) == p3_before


def test_pos_sa_04__failing_commit_unapproved(db, s):
    """POS-SA-04 — a failing commit keeps the approver unapproved.
    Rules: set_approval SA1; TC4."""
    O = po(db, s, "1", **READY)
    P3 = poappr(db, s, O, s.U3)
    commit_point(db)
    oid, pid, u3_id, w1_id = O.id, P3.id, s.U3.id, s.W1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.set_approval(db, po_id=oid, user_id=u3_id, workspace_id=w1_id, approved=True)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderApprover, pid).approved is False


# --------------------------------------------------------------------------- #
# void_purchase_order
# --------------------------------------------------------------------------- #


def vbase(db, s, v_but=None):
    """Section convention VBASE: O ready, L, V (draft) linked, P3 approved."""
    g = SimpleNamespace()
    g.O = po(db, s, "1", **READY)
    g.L = poline(db, s, g.O, 1)
    g.V = inv(db, s, g.O, linked=True, **(v_but or {}))
    g.vid = g.V.id
    g.P3 = poappr(db, s, g.O, s.U3, approved=True)
    return g


def VOID(db, s, O, note):
    """Section convention VOID(note)."""
    return svc.void_purchase_order(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note=note)


def test_pos_v_01__voided_draft_deleted_approvals_cleared(db, s):
    """POS-V-01 — the order is voided, its draft deleted, approvals cleared; committed; nobody told.
    Rules: void_purchase_order V4, V5, V6, V7, V9; TC1, TC2."""
    g = vbase(db, s)
    commit_point(db)
    l_before = snap(db, g.L)

    result = VOID(db, s, g.O, "Duplicate")

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == g.O.id
    assert result.voided is True
    db.rollback()
    # Then 3
    o = reread(db, PurchaseOrder, g.O.id)
    assert o.void_note == "Duplicate"
    assert o.voided_at == NOW
    assert o.voided_by == s.U2.id
    assert o.invoice_id is None
    # Then 4
    assert o.current_status_id == s.SD1.id
    assert o.supplier_confirmed is True
    assert o.items_confirmed is True
    # Then 5
    assert count_where(db, AccountInvoice, AccountInvoice.id == g.vid) == 0
    # Then 6
    assert reread(db, PurchaseOrderApprover, g.P3.id).approved is False
    # Then 7
    assert notes(db) == []
    # Then 8
    assert snap(db, g.L) == l_before


@xfail(3185)
def test_pos_v_02__unlink_event_records_id(db, s):
    """POS-V-02 — the unlink event records the id the order was linked to.
    Rules: void_purchase_order V5a [BUG-3185]."""
    g = vbase(db, s)
    commit_point(db)

    VOID(db, s, g.O, "Duplicate")

    db.rollback()
    # Then 1
    assert event_of(db, g.O.id, "invoice_voided").metadata_json["invoice_id"] == g.vid


def test_pos_v_03__w0_order_404(db, s):
    """POS-V-03 — a W0 order → 404.
    Rules: void_purchase_order V1."""
    O0 = po(db, s, "0", "0")
    vbase(db, s)
    commit_point(db)
    o0_before = snap(db, O0)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_purchase_order(db, po_id=O0.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O0.id)
    # Then 4
    assert snap(db, O0) == o0_before


def test_pos_v_04__w2_order_404(db, s):
    """POS-V-04 — a W2 order → 404.
    Rules: void_purchase_order V1."""
    vbase(db, s)
    O9 = po(db, s, "9", "9")
    commit_point(db)
    o9_before = snap(db, O9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.void_purchase_order(db, po_id=O9.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Duplicate")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert snap(db, O9) == o9_before


def test_pos_v_05__already_voided_400(db, s):
    """POS-V-05 — already voided → 400, rolled back.
    Rules: void_purchase_order V2, V9; TC3."""
    O = po(db, s, "1", **VOIDED(s))
    commit_point(db)
    o_before = snap(db, O)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            VOID(db, s, O, "Again")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Purchase order is already voided"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert snap(db, O) == o_before


@xfail(3162)
def test_pos_v_06__order_row_locked_first(db, s):
    """POS-V-06 — the order row is locked before the first state check.
    Rules: void_purchase_order V1 [BUG-3162]; HR-10."""
    g = vbase(db, s)
    oid, w1_id, u2_id = g.O.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.void_purchase_order(db, po_id=oid, workspace_id=w1_id, user_id=u2_id, void_note="Duplicate")

    # Then 1
    assert result.voided is True
    # Then 2
    assert rec.exact_lock_of("purchase_orders")
    # Then 3
    assert rec.before("purchase_orders", "purchase_order_items")
    # Then 4
    assert rec.before("purchase_orders", "account_invoices")


@xfail(2734)
def test_pos_v_07__completed_order_not_voided(db, s):
    """POS-V-07 — a completed order cannot be voided.
    Rules: void_purchase_order V2a [BUG-2734]."""
    O = po(db, s, "1", **READY, **COMPLETE(s))
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **FINALIZED)
    commit_point(db)
    o_before, v_before = snap(db, O), snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        VOID(db, s, O, "Duplicate")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a completed purchase order — record a return instead"
    # Then 4
    assert snap(db, O) == o_before
    # Then 5
    assert snap(db, V) == v_before


@xfail(2734)
def test_pos_v_08__goods_received_not_voided(db, s):
    """POS-V-08 — an order with goods received cannot be voided.
    Rules: void_purchase_order V2b, V10 [BUG-2734]."""
    O = po(db, s, "1", **READY, **PROJ, current_status_id=s.SR1.id)
    poline(db, s, O, 1, quantity_received=Decimal("3.00"))
    V = inv(db, s, O, linked=True, **FINALIZED)
    commit_point(db)
    o_before, v_before = snap(db, O), snap(db, V)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        VOID(db, s, O, "Duplicate")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a purchase order with goods received — record a return instead"
    # Then 4
    assert snap(db, O) == o_before
    # Then 5
    assert snap(db, V) == v_before


def test_pos_v_09__finalized_invoice_voided(db, s):
    """POS-V-09 — a finalized invoice is voided with the order's reason; its payments voided.
    Rules: void_purchase_order V2b (other side), V4."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **FINALIZED, paid_amount=Decimal("100.00"), payment_status="partial")
    P = cash(db, s, V, "100.00")
    commit_point(db)

    result = VOID(db, s, O, "Duplicate")

    # Then 1
    assert result.voided is True
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, V.id)
    assert v.invoice_status == "voided"
    assert v.void_note == "Purchase order voided: Duplicate"
    # Then 3
    assert reread(db, InvoicePayment, P.id).is_voided is True
    # Then 4
    assert reread(db, PurchaseOrder, O.id).invoice_id is None


@xfail(639)
def test_pos_v_10__draft_with_payment_history_rolls_back(db, s):
    """POS-V-10 — a draft with payment history is not deleted; the void is rolled back.
    Rules: void_purchase_order V4 [BUG-639] (pass-through), V9; TC3."""
    g = vbase(db, s, v_but={"paid_amount": Decimal("100.00"), "payment_status": "partial"})
    cash(db, s, g.V, "100.00")
    commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        VOID(db, s, g.O, "Duplicate")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == PAYHIST
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    o = reread(db, PurchaseOrder, g.O.id)
    assert o.voided is False
    assert o.invoice_id == g.vid


def test_pos_v_11__voided_invoice_left_unlinked(db, s):
    """POS-V-11 — a linked voided invoice is left as it is; still unlinked.
    Rules: void_purchase_order V4, V5."""
    g = vbase(db, s, v_but=VOIDED_INV)
    commit_point(db)
    v_before = snap(db, g.V)

    VOID(db, s, g.O, "Duplicate")

    db.rollback()
    # Then 1
    assert snap(db, g.V) == v_before
    # Then 2
    o = reread(db, PurchaseOrder, g.O.id)
    assert o.invoice_id is None
    assert o.voided is True
    # Then 3
    assert "invoice_voided" in types(db, g.O.id)


def test_pos_v_12__w2_invoice_untouched(db, s):
    """POS-V-12 — a W2 invoice linked is not touched; the order is unlinked and approvals cleared.
    Rules: void_purchase_order V4, V5; HR-16."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V9 = inv(db, s, O, k="9", linked=True)
    P3 = poappr(db, s, O, s.U3, approved=True)
    commit_point(db)
    v9_before = snap(db, V9)

    VOID(db, s, O, "Duplicate")

    db.rollback()
    # Then 1
    assert snap(db, V9) == v9_before
    # Then 2
    assert reread(db, PurchaseOrder, O.id).invoice_id is None
    # Then 3
    assert reread(db, PurchaseOrderApprover, P3.id).approved is False


@xfail(3170)
def test_pos_v_13__no_invoice_approvals_cleared(db, s):
    """POS-V-13 — without an invoice, approvals are still cleared.
    Rules: void_purchase_order V8 [BUG-3170]."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    P3 = poappr(db, s, O, s.U3, approved=True)
    commit_point(db)

    result = VOID(db, s, O, "Duplicate")

    # Then 1
    assert result.voided is True
    db.rollback()
    # Then 2
    assert reread(db, PurchaseOrderApprover, P3.id).approved is False


def test_pos_v_14__no_invoice_voided_no_unlink(db, s):
    """POS-V-14 — without an invoice: voided, no unlink event, `updated_by` untouched.
    Rules: void_purchase_order V3, V5, V6, V11."""
    O = po(db, s, "1")
    poline(db, s, O, 1)
    commit_point(db)

    VOID(db, s, O, "Duplicate")

    db.rollback()
    # Then 1
    o = reread(db, PurchaseOrder, O.id)
    assert o.voided is True
    assert o.updated_by is None
    # Then 2
    assert "invoice_voided" not in types(db, O.id)
    # Then 3
    assert "inventory_reversed" not in types(db, O.id)
    # Then 4
    assert types(db, O.id)[-1] == "po_voided"


def test_pos_v_15__failing_commit_unchanged(db, s):
    """POS-V-15 — a failing commit leaves the order and its invoice as they were.
    Rules: void_purchase_order V9; TC4."""
    g = vbase(db, s)
    commit_point(db)
    oid, w1_id, u2_id = g.O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.void_purchase_order(db, po_id=oid, workspace_id=w1_id, user_id=u2_id, void_note="Duplicate")

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    o = reread(db, PurchaseOrder, oid)
    assert o.voided is False
    assert o.invoice_id == g.vid
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.id == g.vid) == 1


@xfail(3168)
def test_pos_v_16__schema_blank_note_refused():
    """POS-V-16 — schema: a whitespace-only void note is refused.
    Rules: void_purchase_order V12 [BUG-3168]."""
    # Then 1
    with pytest.raises(ValidationError):
        PurchaseOrderVoidRequest(void_note="   ")


@xfail(3168)
def test_pos_v_17__schema_empty_note_refused():
    """POS-V-17 — schema: an empty void note is refused.
    Rules: void_purchase_order V12 [BUG-3168]."""
    # Then 1
    with pytest.raises(ValidationError):
        PurchaseOrderVoidRequest(void_note="")


@xfail(3168)
def test_pos_v_18__schema_note_trimmed():
    """POS-V-18 — schema: the void note is trimmed.
    Rules: void_purchase_order V12 [BUG-3168]."""
    result = PurchaseOrderVoidRequest(void_note=" Duplicate ")

    # Then 1
    assert result.void_note == "Duplicate"


def test_pos_v_19__schema_plain_note_accepted():
    """POS-V-19 — schema: a plain void note is accepted.
    Rules: void_purchase_order V12 (holds today and after BUG-3168)."""
    result = PurchaseOrderVoidRequest(void_note="Duplicate")

    # Then 1
    assert result.void_note == "Duplicate"


def test_pos_v_20__receipt_and_correction_reversed(db, s):
    """POS-V-20 — a receipt and its full correction are both reversed on void.
    Rules: void_purchase_order V3, V2b [BUG-2734] (other side: nothing left received)."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **LOCKED_INV)
    svc.create_receive_event(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=RCV((L, "3")))
    svc.create_receive_event(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=COR((L, "-3"), note="Miscount"))
    # BUG-664 guard: the two Given postings share the transaction's now(); date them in the past, in id order
    for i, row in enumerate(rows_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id)):
        row.performed_at = T0 + timedelta(minutes=i)
    db.flush()
    commit_point(db)
    n0 = count_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id)
    assert reread(db, PurchaseOrderItem, L.id).quantity_received == Decimal("0.00")

    VOID(db, s, O, "Duplicate")

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrder, O.id).voided is True
    # Then 2
    rows = rows_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id)
    assert len(rows) == n0 + 2
    # Then 3
    newest = rows[-2:]
    assert all(r.transaction_type == "inventory_adjustment" for r in newest)
    assert sorted(abs(r.quantity) for r in newest) == [3, 3]
    # Then 4
    assert STOCK(db, s, s.F1, s.I1).qty == 0
    # Then 5
    e = event_of(db, O.id, "inventory_reversed")
    assert e.description == "2 inventory posting(s) reversed for void"
    assert e.metadata_json["reversed_count"] == 2
    # Then 6
    assert reread(db, AccountInvoice, V.id).invoice_status == "locked"


def test_pos_v_21__void_events(db, s):
    """POS-V-21 — the void's events: approvals reset, invoice unlinked with its change list, then voided.
    Rules: void_purchase_order V5, V6; PurchaseOrderManager.reset_approvals R2 (pass-through)."""
    g = vbase(db, s)
    commit_point(db)

    VOID(db, s, g.O, "Duplicate")

    db.rollback()
    ts = types(db, g.O.id)
    # Then 1
    assert ts.count("approvals_reset") == 1
    assert ts.count("invoice_voided") == 1
    assert ts[-1] == "po_voided"
    # Then 2
    assert ts.index("approvals_reset") < ts.index("invoice_voided") < ts.index("po_voided")
    # Then 3
    assert event_of(db, g.O.id, "approvals_reset").description == "Cleared approvals — PO voided (1 approval(s) cleared)"
    # Then 4
    e = event_of(db, g.O.id, "invoice_voided")
    assert e.description == f"Invoice unlinked — PO #{g.O.po_number} voided"
    # Then 5
    assert set(e.metadata_json) == {"invoice_id", "changes"}
    assert e.metadata_json["changes"] == [{"field": "void_note", "label": "Void reason", "from_value": None, "to_value": "Duplicate"}]
    # Then 6
    evs = EV(db, g.O.id)
    assert evs[-1].description == f"Purchase order #{g.O.po_number} voided. Reason: Duplicate"
    assert evs[-1].metadata_json == {"void_note": "Duplicate"}
    # Then 7
    assert "inventory_reversed" not in ts


def test_pos_v_22__one_reversed_posting_logged(db, s):
    """POS-V-22 — exactly one reversed posting is still logged.
    Rules: void_purchase_order V3 (reversed_count 1 boundary)."""
    O = po(db, s, "1", **READY, current_status_id=s.SR1.id)
    L = poline(db, s, O, 1)
    inv(db, s, O, linked=True, **LOCKED_INV)
    svc.create_receive_event(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U1.id, data=RCV((L, "3")))
    L.quantity_received = Decimal("0.00")
    db.flush()
    # BUG-664 guard: date the Given posting in the past so the reversal reads one unique newest row
    for row in rows_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id):
        row.performed_at = T0
    db.flush()
    commit_point(db)
    n0 = count_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id)
    assert STOCK(db, s, s.F1, s.I1).qty == 3

    VOID(db, s, O, "Duplicate")

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrder, O.id).voided is True
    # Then 2
    rows = rows_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id)
    assert len(rows) == n0 + 1
    assert rows[-1].transaction_type == "inventory_adjustment"
    assert abs(rows[-1].quantity) == 3
    # Then 3
    assert STOCK(db, s, s.F1, s.I1).qty == 0
    # Then 4
    assert types(db, O.id).count("inventory_reversed") == 1
    e = event_of(db, O.id, "inventory_reversed")
    assert e.description == "1 inventory posting(s) reversed for void"
    assert e.metadata_json["reversed_count"] == 1


# --------------------------------------------------------------------------- #
# create_invoice_for_purchase_order
# --------------------------------------------------------------------------- #


def CI(db, s, O):
    """Section convention CI()."""
    return svc.create_invoice_for_purchase_order(db, po_id=O.id, workspace_id=s.W1.id, user_id=s.U2.id)


def test_pos_ci_01__ready_order_gets_draft(db, s):
    """POS-CI-01 — a ready order without an invoice gets a draft; committed; nobody told.
    Rules: create_invoice_for_purchase_order CI3, CI4; TC1, TC2."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    poappr(db, s, O, s.U3)
    commit_point(db)

    result = CI(db, s, O)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == O.id
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 3
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "draft"
    assert v.invoice_type == "payable"
    assert v.order_id == O.id
    # Then 4
    assert notes(db) == []


def test_pos_ci_02__w2_order_404(db, s):
    """POS-CI-02 — a W2 order → 404, rolled back.
    Rules: create_invoice_for_purchase_order CI1, CI5; TC3."""
    O9 = po(db, s, "9", "9", **READY)
    poline(db, s, O9, 1)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_purchase_order(db, po_id=O9.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(O9.id)
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before


@xfail(3162)
def test_pos_ci_03__order_row_locked_first(db, s):
    """POS-CI-03 — the order row is locked before the first state check.
    Rules: create_invoice_for_purchase_order CI1 [BUG-3162]; HR-10."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.create_invoice_for_purchase_order(db, po_id=oid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert rec.exact_lock_of("purchase_orders")
    # Then 3
    assert rec.before("purchase_orders", "account_invoices")


@xfail(3169)
def test_pos_ci_04__voided_order_400(db, s):
    """POS-CI-04 — a voided order → 400, nothing written.
    Rules: create_invoice_for_purchase_order CI2 [BUG-3169]."""
    O = po(db, s, "1", **READY, **VOIDED(s))
    poline(db, s, O, 1)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CI(db, s, O)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Purchase order is voided"
    # Then 4
    assert counts(db) == before


def test_pos_ci_05__not_confirmed_422(db, s):
    """POS-CI-05 — sections not all confirmed → 422, rolled back.
    Rules: create_invoice_for_purchase_order CI3, CI5; SD3."""
    O = po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    poline(db, s, O, 1)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            CI(db, s, O)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == FORCE422
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


def test_pos_ci_06__financially_locked_unchanged(db, s):
    """POS-CI-06 — a financially locked order is returned unchanged.
    Rules: create_invoice_for_purchase_order CI3; SD1."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, **FINALIZED)
    commit_point(db)
    v_before = snap(db, V)

    result = CI(db, s, O)

    # Then 1
    assert result.invoice_id == V.id
    # Then 2
    assert snap(db, V) == v_before
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == O.id) == 1


def test_pos_ci_07__linked_draft_resynced(db, s):
    """POS-CI-07 — a linked draft is re-synced.
    Rules: create_invoice_for_purchase_order CI3; SD11."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True, description="Old")
    commit_point(db)

    result = CI(db, s, O)

    # Then 1
    assert result.invoice_id == V.id
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, V.id).description == f"Purchase order {O.po_number}"
    # Then 3
    assert "items_synced" in itypes(db, V.id)


def test_pos_ci_08__no_supplier_422(db, s):
    """POS-CI-08 — confirmed sections but no supplier → 422.
    Rules: create_invoice_for_purchase_order CI4."""
    O = po(db, s, "1", **READY, account_id=None)
    poline(db, s, O, 1)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        CI(db, s, O)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Assign a supplier before a draft invoice can be created"
    # Then 4
    assert counts(db) == before


# [claude] POS-CI-09
def test_pos_ci_09__integrity_error_with_invoice_returned(db, s):
    """POS-CI-09 — an IntegrityError after which the order has an invoice: returned, no error.
    Rules: create_invoice_for_purchase_order CI6."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    V = inv(db, s, O, linked=True)
    commit_point(db)

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=IERR("duplicate key", "23505", "account_invoices", None)):
        with spies(db) as (cm, rb):
            result = CI(db, s, O)

    # Then 1
    assert result.id == O.id
    assert result.invoice_id == V.id
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert cm.call_count == 0


# [claude] POS-CI-10
def test_pos_ci_10__integrity_error_no_invoice_409(db, s):
    """POS-CI-10 — an IntegrityError with still no invoice is translated (invoice phase).
    Rules: create_invoice_for_purchase_order CI6."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    commit_point(db)

    with patch.object(svc, "_sync_draft_invoice_for_po", side_effect=IERR("duplicate key", "23505", "purchase_order_items", None)):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            CI(db, s, O)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "A draft invoice for this order already exists"


def test_pos_ci_11__failing_commit_no_draft(db, s):
    """POS-CI-11 — a failing commit saves no draft.
    Rules: create_invoice_for_purchase_order CI5; TC4."""
    O = po(db, s, "1", **READY)
    poline(db, s, O, 1)
    before = commit_point(db)
    oid, w1_id, u2_id = O.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_invoice_for_purchase_order(db, po_id=oid, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# receive_replacements (new — BUG-2810, settlement BUG-3176)
# --------------------------------------------------------------------------- #


def PEV(db, oid):
    """Section convention "PO event": the `return_replacement_received` event of O."""
    return event_of(db, oid, "return_replacement_received")


def RQRAW(rlid, q):
    from app.schemas.purchase_order_return import PurchaseOrderReturnReplacementCreate

    return PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": rlid, "quantity": Decimal(q)}])


W2CN = "9"  # "CN built of W2"
W0CN = "0"  # "CN built of W0"


def cn_of(s, k):
    return {"workspace_id": s.WS[k].id, "account_id": getattr(s, "A" + k).id}


@xfail(2810)
def test_pos_rx_01__quantities_committed(db, s):
    """POS-RX-01 — replacements are received: return line and PO line quantities; committed.
    Rules: receive_replacements RX5, RX7, RX10; TC1, TC2."""
    g = repl(db, s)
    commit_point(db)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == g.R.id
    assert result.status == "completed"
    db.rollback()
    # Then 3
    rl = reread(db, PurchaseOrderReturnItem, g.RL.id)
    assert rl.quantity_replaced == Decimal("4.00")
    assert rl.quantity_returned == Decimal("4.00")
    # Then 4
    line = reread(db, PurchaseOrderItem, g.L.id)
    assert line.quantity_received == Decimal("10.00")
    assert line.quantity_returned == Decimal("4.00")


@xfail(2810)
def test_pos_rx_02__one_ledger_row_per_line(db, s):
    """POS-RX-02 — one stock-in ledger row per return line, linked to the return.
    Rules: receive_replacements RX6, RX8g [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert len(LEDGER(db, g.RL.id)) == 1
    # Then 2
    row = LEDGER(db, g.RL.id)[0]
    assert row.workspace_id == s.W1.id
    assert row.item_id == s.I1.id
    assert row.quantity == 4
    assert row.unit_cost == Decimal("500.00")
    assert row.total_cost == Decimal("2000.00")
    # Then 3
    assert row.notes == f"Replacement for return {g.R.return_number} — PO {g.O.po_number} line 1"
    # Then 4
    assert row.transaction_type == "purchase_order"


@xfail(2810)
def test_pos_rx_03__two_lines_two_rows(db, s):
    """POS-RX-03 — two return lines: two ledger rows.
    Rules: receive_replacements RX6."""
    g = repl(db, s, cn_but={"invoice_amount": Decimal("3000.00")})
    L2 = poline(db, s, g.O, 2, item_id=s.I1b.id, quantity_received=Decimal("8.00"), quantity_returned=Decimal("2.00"))
    RL2 = rline(db, g.R, L2, "2")
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4"), (RL2, "2")))

    db.rollback()
    # Then 1
    assert len(LEDGER(db, g.RL.id)) == 1
    assert len(LEDGER(db, RL2.id)) == 1
    # Then 2
    row = LEDGER(db, RL2.id)[0]
    assert row.item_id == s.I1b.id
    assert row.quantity == 2
    assert row.total_cost == Decimal("1000.00")
    # Then 3
    assert reread(db, PurchaseOrderItem, L2.id).quantity_received == Decimal("10.00")


@xfail(2810)
def test_pos_rx_04__cost_is_po_line_price(db, s):
    """POS-RX-04 — the ledger cost is the PO line's price, not the return line's.
    Rules: receive_replacements RX6 (RR6)."""
    g = repl(db, s, rl_but={"unit_price": Decimal("450.00")})
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    row = LEDGER(db, g.RL.id)[0]
    assert row.unit_cost == Decimal("500.00")
    assert row.total_cost == Decimal("2000.00")


@xfail(2810)
def test_pos_rx_05__unpriced_po_line_uses_return_price(db, s):
    """POS-RX-05 — an unpriced PO line: the return line's price is the cost.
    Rules: receive_replacements RX6 (RR6)."""
    g = repl(db, s, l_but={"unit_price": None, "line_subtotal": None}, rl_but={"unit_price": Decimal("450.00")})
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    row = LEDGER(db, g.RL.id)[0]
    assert row.unit_cost == Decimal("450.00")
    assert row.total_cost == Decimal("1800.00")


@xfail(2810)
def test_pos_rx_06__stock_rises_at_cost(db, s):
    """POS-RX-06 — stock rises at the order's factory at the original cost.
    Rules: receive_replacements RX6."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert STOCK(db, s, s.F1, s.I1).qty == 4
    # Then 2
    assert STOCK(db, s, s.F1, s.I1).avg_price == Decimal("500.00")


@xfail(2810)
def test_pos_rx_07__project_order_no_stock(db, s):
    """POS-RX-07 — a project order moves no stock; quantities still move.
    Rules: receive_replacements RX5, RX6."""
    g = repl(db, s, o_but=PROJ)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert LEDGER(db, g.RL.id) == []
    # Then 2
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    # Then 3
    assert reread(db, PurchaseOrderItem, g.L.id).quantity_received == Decimal("10.00")


@xfail(3174)
def test_pos_rx_08__stays_completed_stamped(db, s):
    """POS-RX-08 — the return stays completed and is stamped `updated_by`.
    Rules: receive_replacements RX7 [BUG-3174]."""
    g = repl(db, s)
    commit_point(db)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert result.status == "completed"
    db.rollback()
    # Then 2
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.updated_by == s.U2.id
    assert r.completed_at == T0


@xfail(2810)
def test_pos_rx_09__order_untouched(db, s):
    """POS-RX-09 — the order, its approvals and its invoice are untouched; no new invoice.
    Rules: receive_replacements RX8."""
    g = repl(db, s)
    P3 = poappr(db, s, g.O, s.U3, approved=True)
    commit_point(db)
    v_before = snap(db, g.V)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    o = reread(db, PurchaseOrder, g.O.id)
    assert o.current_status_id == s.SC1.id
    assert o.actual_delivery_date == date(2026, 9, 10)
    assert o.invoice_id == g.V.id
    # Then 2
    assert reread(db, PurchaseOrderApprover, P3.id).approved is True
    # Then 3
    assert snap(db, g.V) == v_before
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.workspace_id == s.W1.id) == 2


@xfail(2810)
def test_pos_rx_10__po_activity_entry(db, s):
    """POS-RX-10 — the PO activity entry; nobody told.
    Rules: receive_replacements RX9."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    e = PEV(db, g.O.id)
    assert e.description == f"Replacements received for return {g.R.return_number} — 4 unit(s)"
    assert e.performed_by == s.U2.id
    # Then 2
    assert e.metadata_json["return_id"] == g.R.id
    assert e.metadata_json["total_quantity"] == "4"
    # Then 3
    assert notes(db) == []


@xfail(2810)
def test_pos_rx_11__missing_order_404(db, s):
    """POS-RX-11 — a missing order → 404.
    Rules: receive_replacements RX1."""
    g = repl(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=MISSING, return_id=g.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((g.RL, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_12__w0_order_404(db, s):
    """POS-RX-12 — a W0 order id → 404; W0's return untouched.
    Rules: receive_replacements RX1."""
    g0 = repl(db, s, "0")
    repl(db, s)
    commit_point(db)
    rl0_before, cn0_before = snap(db, g0.RL), snap(db, g0.CN)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=g0.O.id, return_id=g0.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((g0.RL, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(g0.O.id)
    # Then 4
    assert snap(db, g0.RL) == rl0_before
    # Then 5
    assert snap(db, g0.CN) == cn0_before


@xfail(2810)
def test_pos_rx_13__w2_order_404(db, s):
    """POS-RX-13 — a W2 order id → 404; W2's return untouched.
    Rules: receive_replacements RX1."""
    repl(db, s)
    g9 = repl(db, s, "9")
    commit_point(db)
    rl9_before, cn9_before = snap(db, g9.RL), snap(db, g9.CN)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=g9.O.id, return_id=g9.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((g9.RL, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(g9.O.id)
    # Then 4
    assert snap(db, g9.RL) == rl9_before
    # Then 5
    assert snap(db, g9.CN) == cn9_before


@xfail(2810)
def test_pos_rx_14__return_of_other_order_404(db, s):
    """POS-RX-14 — a return of another W1 order → 404.
    Rules: receive_replacements RX1."""
    g = repl(db, s)
    O2 = po(db, s, "2", **READY, **COMPLETE(s))
    L2 = poline(db, s, O2, 1, quantity_received=Decimal("6.00"), quantity_returned=Decimal("4.00"))
    R2 = ret(db, s, O2, "2", **REPLACE, **COMPLETED(s))
    RL2 = rline(db, R2, L2, "4")
    commit_point(db)
    rl2_before = snap(db, RL2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=g.O.id, return_id=R2.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((RL2, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(R2.id)
    # Then 4
    assert snap(db, RL2) == rl2_before


@xfail(2810)
def test_pos_rx_15__w0_return_404(db, s):
    """POS-RX-15 — a W0 return id under the W1 order → 404.
    Rules: receive_replacements RX1."""
    g0 = repl(db, s, "0")
    g = repl(db, s)
    commit_point(db)
    rl0_before = snap(db, g0.RL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=g.O.id, return_id=g0.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((g0.RL, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(g0.R.id)
    # Then 4
    assert snap(db, g0.RL) == rl0_before


@xfail(2810)
def test_pos_rx_16__w2_return_404(db, s):
    """POS-RX-16 — a W2 return id under the W1 order → 404.
    Rules: receive_replacements RX1."""
    g = repl(db, s)
    g9 = repl(db, s, "9")
    commit_point(db)
    rl9_before = snap(db, g9.RL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.receive_replacements(db, po_id=g.O.id, return_id=g9.R.id, workspace_id=s.W1.id, user_id=s.U2.id, data=RQ((g9.RL, "4")))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == RNF(g9.R.id)
    # Then 4
    assert snap(db, g9.RL) == rl9_before


@xfail(2810)
def test_pos_rx_17__return_row_locked(db, s):
    """POS-RX-17 — the return row is locked.
    Rules: receive_replacements RX1; HR-10."""
    g = repl(db, s)
    oid, rid, rlid, w1_id, u2_id = g.O.id, g.R.id, g.RL.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, data=RQRAW(rlid, "4"))

    # Then 1
    assert result.id == rid
    # Then 2
    assert rec.exact_lock("purchase_order_returns")
    # Then 3
    assert rec.before("purchase_order_returns", "purchase_order_return_items")


@xfail(2810)
def test_pos_rx_18__refund_return_400(db, s):
    """POS-RX-18 — a refund return → 400.
    Rules: receive_replacements RX2 (RR1)."""
    g = repl(db, s, r_but={"return_type": "refund"}, l_but={"quantity_refunded": Decimal("4.00")})
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g.RL, "4")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a replace return can receive replacements"
    # Then 4
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_19__pending_return_400(db, s):
    """POS-RX-19 — a pending return → 400.
    Rules: receive_replacements RX2 (RR2)."""
    g = repl(
        db, s,
        r_but={"status": "pending", "completed_at": None, "completed_by": None},
        l_but={"quantity_received": Decimal("10.00"), "quantity_returned": Decimal("0.00")},
    )
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g.RL, "4")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Complete the return before receiving replacements"
    # Then 4
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_20__w2_line_not_part(db, s):
    """POS-RX-20 — a W2 return line in the request → 400 not part of the return.
    Rules: receive_replacements RX2 (RR4); HR-16."""
    g = repl(db, s)
    g9 = repl(db, s, "9")
    before = commit_point(db)
    rl9_before = snap(db, g9.RL)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g9.RL, "1")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTPART(g9.RL.id, g.R)
    # Then 4
    assert snap(db, g9.RL) == rl9_before
    # Then 5
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_21__other_return_line_not_part(db, s):
    """POS-RX-21 — a line of another W1 return → 400 not part of the return.
    Rules: receive_replacements RX2 (RR4)."""
    g = repl(db, s)
    R2 = ret(db, s, g.O, "2", **REPLACE, **COMPLETED(s))
    RL2 = rline(db, R2, g.L, "1")
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((RL2, "1")))
    # Then 2
    assert exc.value.detail == NOTPART(RL2.id, g.R)
    # Then 3
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_22__more_than_went_back_400(db, s):
    """POS-RX-22 — more than went back → 400.
    Rules: receive_replacements RX2 (RR5)."""
    g = repl(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g.RL, "5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == RTOO("5", 1, "4.00")
    # Then 4
    assert counts(db) == before


# [claude] POS-RX-23
@xfail(2810)
def test_pos_rx_23__limit_counts_already_replaced(db, s):
    """POS-RX-23 — the limit counts what was already replaced.
    Rules: receive_replacements RX2 (RR5)."""
    g = repl(db, s, rl_but={"quantity_replaced": Decimal("3.00")}, l_but={"quantity_received": Decimal("9.00")})
    commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g.RL, "2")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == RTOO("2", 1, "1.00")


@xfail(2810)
def test_pos_rx_24__fractional_storage_400(db, s):
    """POS-RX-24 — a fractional quantity on a storage order → 400, rolled back.
    Rules: receive_replacements RX3, RX10; TC3."""
    g = repl(db, s)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            RX(db, s, g, RQ((g.RL, "1.5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Line 1 has a fractional quantity; inventory requires whole units"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)
    # Then 7
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_25__fractional_project_accepted(db, s):
    """POS-RX-25 — a fractional quantity on a project order is accepted.
    Rules: receive_replacements RX3."""
    g = repl(db, s, o_but=PROJ)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "1.5")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("1.50")
    # Then 2
    assert reread(db, PurchaseOrderItem, g.L.id).quantity_received == Decimal("7.50")


@xfail(3181)
def test_pos_rx_26__line_already_fully_received_400(db, s):
    """POS-RX-26 — a line already re-received the normal way cannot be filled again.
    Rules: receive_replacements RX4 [BUG-3181]."""
    g = repl(db, s, l_but={"quantity_received": Decimal("10.00")})
    before = commit_point(db)
    l_before = snap(db, g.L)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        RX(db, s, g, RQ((g.RL, "4")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot receive 4 replacement(s) for line 1 — the line is already fully received"
    # Then 4
    assert snap(db, g.L) == l_before
    # Then 5
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_27__exactly_up_to_limit(db, s):
    """POS-RX-27 — the PO line limit: exactly up to ordered − refunded passes.
    Rules: receive_replacements RX4 [BUG-3181] (other side)."""
    g = repl(db, s, l_but={"quantity_received": Decimal("7.00")})
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "3")))

    db.rollback()
    # Then 1
    assert reread(db, PurchaseOrderItem, g.L.id).quantity_received == Decimal("10.00")
    # Then 2
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("3.00")


@xfail(2810)
def test_pos_rx_28__failing_commit_saves_nothing(db, s):
    """POS-RX-28 — a failing commit saves nothing: no quantities, stock, entry or events.
    Rules: receive_replacements RX10; TC4."""
    g = repl(db, s)
    before = commit_point(db)
    req = RQ((g.RL, "4"))
    oid, rid, lid, w1_id, u2_id = g.O.id, g.R.id, g.L.id, s.W1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, data=req)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, PurchaseOrderItem, lid).quantity_received == Decimal("6.00")
    # Then 4
    assert counts(db) == before


@xfail(2810)
def test_pos_rx_29__stock_in_failure_rolls_back(db, s):
    """POS-RX-29 — a stock-in failure after the writes rolls everything back.
    Rules: receive_replacements RX6, RX10; TC3."""
    s.F1.is_deleted = True
    s.F1.is_active = False
    db.flush()
    g = repl(db, s)
    before = commit_point(db)
    X, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException):
        RX(db, s, g, RQ((g.RL, "4")))
    # Then 2
    assert X not in db
    db.rollback()
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("0.00")
    # Then 5
    assert counts(db) == before


@xfail(3176)
def test_pos_rx_30__settlement_entry(db, s):
    """POS-RX-30 — the settlement entry: method, amount, UTC date, actor, workspace; no warning.
    Rules: receive_replacements RX8a, RX8d [BUG-3176] (OQ-63)."""
    g = repl(db, s)
    commit_point(db)

    result = RX(db, s, g, RQ((g.RL, "4")))

    warnings = WARN(result)
    db.rollback()
    # Then 1
    assert len(SETTLE(db, g.CN.id)) == 1
    P = SETTLE(db, g.CN.id)[0]
    # Then 2
    assert P.payment_amount == Decimal("2000.00")
    assert P.payment_method == "settled_by_replacement"
    # Then 3
    assert P.payment_date == TODAY_UTC
    assert P.created_by == s.U2.id
    assert P.is_voided is False
    # Then 4
    assert P.workspace_id == s.W1.id
    assert P.invoice_id == g.CN.id
    # Then 5
    assert len(PAYS(db, g.CN.id)) == 1
    # Then 6
    assert warnings == []


@xfail(3176)
def test_pos_rx_31__two_lines_one_entry(db, s):
    """POS-RX-31 — two lines settle in one entry: the sum of their values.
    Rules: receive_replacements RX8a [BUG-3176]."""
    g = repl(db, s, cn_but={"invoice_amount": Decimal("3000.00")})
    L2 = poline(db, s, g.O, 2, item_id=s.I1b.id, quantity_received=Decimal("8.00"), quantity_returned=Decimal("2.00"))
    RL2 = rline(db, g.R, L2, "2")
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4"), (RL2, "2")))

    db.rollback()
    # Then 1
    assert len(SETTLE(db, g.CN.id)) == 1
    # Then 2
    assert SETTLE(db, g.CN.id)[0].payment_amount == Decimal("3000.00")


@xfail(3176)
def test_pos_rx_32__amount_uses_return_price(db, s):
    """POS-RX-32 — the amount uses the return line's price.
    Rules: receive_replacements RX8a [BUG-3176]."""
    g = repl(db, s, rl_but={"unit_price": Decimal("450.00")})
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert SETTLE(db, g.CN.id)[0].payment_amount == Decimal("1800.00")


@xfail(3176)
def test_pos_rx_33__lines_rounded_before_sum(db, s):
    """POS-RX-33 — each line is rounded half up before summing.
    Rules: receive_replacements RX8a [BUG-3176]; HR-15."""
    g = repl(
        db, s,
        o_but=PROJ,
        l_but={"unit_price": Decimal("1.25"), "line_subtotal": Decimal("12.50"), "quantity_received": Decimal("9.90"), "quantity_returned": Decimal("0.10")},
        rl_but={"quantity_returned": Decimal("0.10"), "unit_price": Decimal("1.25")},
        cn_but={"invoice_amount": Decimal("1.00")},
    )
    L2 = poline(db, s, g.O, 2, item_id=s.I1b.id, unit_price=Decimal("1.25"), line_subtotal=Decimal("12.50"), quantity_received=Decimal("9.90"), quantity_returned=Decimal("0.10"))
    RL2 = rline(db, g.R, L2, "0.10", unit_price=Decimal("1.25"))
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "0.10"), (RL2, "0.10")))

    db.rollback()
    # Then 1
    assert SETTLE(db, g.CN.id)[0].payment_amount == Decimal("0.26")


@xfail(3176)
def test_pos_rx_34__full_settlement_pays(db, s):
    """POS-RX-34 — a full settlement pays the credit note and the return.
    Rules: receive_replacements RX8a, RX8c [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("2000.00")
    assert c.payment_status == "paid"
    assert c.invoice_status == "confirmed"
    # Then 2
    assert reread(db, PurchaseOrderReturn, g.R.id).paid is True


@xfail(3176)
def test_pos_rx_35__entry_links_to_receipt(db, s):
    """POS-RX-35 — the entry links to its receipt.
    Rules: receive_replacements RX8b [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert SETTLE(db, g.CN.id)[0].payment_reference == g.R.return_number
    # Then 2
    assert SETTLE(db, g.CN.id)[0].notes == f"Settled by replacement — 4 unit(s) received for return {g.R.return_number}"
    # Then 3
    assert SETTLE(db, g.CN.id)[0].source_type == "purchase_order_event"
    # Then 4
    assert SETTLE(db, g.CN.id)[0].source_id == next(e.id for e in EV(db, g.O.id) if e.event_type == "return_replacement_received")


@xfail(3176)
def test_pos_rx_36__partial_receipt_share(db, s):
    """POS-RX-36 — a partial receipt settles only its share.
    Rules: receive_replacements RX8c [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "3")))

    db.rollback()
    # Then 1
    assert [p.payment_amount for p in SETTLE(db, g.CN.id)] == [Decimal("1500.00")]
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("1500.00")
    assert c.payment_status == "partial"
    # Then 3
    assert reread(db, PurchaseOrderReturn, g.R.id).paid is False
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("3.00")


# [claude] POS-RX-37
@xfail(3176)
def test_pos_rx_37__rest_settles_remainder(db, s):
    """POS-RX-37 — the rest of a partial receipt settles the remainder.
    Rules: receive_replacements RX8c [BUG-3176]."""
    g = repl(
        db, s,
        rl_but={"quantity_replaced": Decimal("3.00")},
        l_but={"quantity_received": Decimal("9.00")},
        cn_but={"paid_amount": Decimal("1500.00"), "payment_status": "partial"},
    )
    spay(db, s, g.CN, "1500.00", g.R)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "1")))

    db.rollback()
    # Then 1
    assert [p.payment_amount for p in SETTLE(db, g.CN.id)] == [Decimal("1500.00"), Decimal("500.00")]
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("2000.00")
    assert c.payment_status == "paid"
    # Then 3
    assert reread(db, PurchaseOrderReturn, g.R.id).paid is True


@xfail(3176)
def test_pos_rx_38__capped_at_outstanding(db, s):
    """POS-RX-38 — cash already collected: the entry is capped at what is outstanding.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("500.00"), "payment_status": "partial"})
    cash(db, s, g.CN, "500.00")
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert [p.payment_amount for p in SETTLE(db, g.CN.id)] == [Decimal("1500.00")]
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("2000.00")
    assert c.payment_status == "paid"
    # Then 3
    assert len(PAYS(db, g.CN.id)) == 2


@xfail(3176)
def test_pos_rx_39__cap_one_cent_below(db, s):
    """POS-RX-39 — the cap one cent below the value.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("0.01"), "payment_status": "partial"})
    cash(db, s, g.CN, "0.01")
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert [p.payment_amount for p in SETTLE(db, g.CN.id)] == [Decimal("1999.99")]


@xfail(3176)
def test_pos_rx_40__fully_refunded_warning(db, s):
    """POS-RX-40 — already fully refunded in cash: no entry, a warning, the receipt goes ahead.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("2000.00"), "payment_status": "paid"}, r_but={"paid": True})
    cash(db, s, g.CN, "2000.00")
    commit_point(db)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [NOSETTLE]
    db.rollback()
    # Then 2
    assert SETTLE(db, g.CN.id) == []
    # Then 3
    assert len(PAYS(db, g.CN.id)) == 1
    # Then 4
    assert reread(db, AccountInvoice, g.CN.id).paid_amount == Decimal("2000.00")
    # Then 5
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    # Then 6
    assert len(LEDGER(db, g.RL.id)) == 1


@xfail(3176)
def test_pos_rx_41__voided_credit_note_warning(db, s):
    """POS-RX-41 — a voided credit note: no entry, a warning, the receipt goes ahead.
    Rules: receive_replacements RX8d [BUG-3176]."""
    g = repl(db, s, cn_but=VOIDED_INV)
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [VOIDW]
    db.rollback()
    # Then 2
    assert PAYS(db, g.CN.id) == []
    # Then 3
    assert snap(db, g.CN) == cn_before
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    # Then 5
    assert len(LEDGER(db, g.RL.id)) == 1


@xfail(3176)
def test_pos_rx_42__no_entry_zero_settled(db, s):
    """POS-RX-42 — with no entry the PO activity entry records 0.00 and a null payment id.
    Rules: receive_replacements RX8d, RX8f [BUG-3176]."""
    g = repl(db, s, cn_but=VOIDED_INV)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert PEV(db, g.O.id).metadata_json["settled_amount"] == "0.00"
    # Then 2
    assert PEV(db, g.O.id).metadata_json["payment_id"] is None


@xfail(3176)
def test_pos_rx_43__activity_entry_settled_amount(db, s):
    """POS-RX-43 — the PO activity entry carries the settled amount and the payment id.
    Rules: receive_replacements RX8f, RX9 [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert PEV(db, g.O.id).metadata_json["settled_amount"] == "2000.00"
    # Then 2
    assert PEV(db, g.O.id).metadata_json["payment_id"] == SETTLE(db, g.CN.id)[0].id


@xfail(3176)
def test_pos_rx_44__return_event(db, s):
    """POS-RX-44 — the return gets its own `replacement_received` event.
    Rules: receive_replacements RX8e [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "3")))

    db.rollback()
    # Then 1
    assert len(REVENTS(db, g.R.id)) == 1
    E = REVENTS(db, g.R.id)[0]
    # Then 2
    assert E.event_type == "replacement_received"
    assert E.performed_by == s.U2.id
    assert E.workspace_id == s.W1.id
    # Then 3
    assert E.description == "Replacements received — 3 unit(s), 1500.00 settled"
    # Then 4
    assert E.metadata_json == {"return_id": g.R.id, "total_quantity": "3", "settled_amount": "1500.00", "payment_id": SETTLE(db, g.CN.id)[0].id}


@xfail(3176)
def test_pos_rx_45__settlement_not_deletable(db, s):
    """POS-RX-45 — a settlement entry cannot be deleted.
    Rules: receive_replacements RX8h [BUG-3176] (fix in invoice_payment_manager)."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("2000.00"), "payment_status": "paid"})
    P = spay(db, s, g.CN, "2000.00", g.R)
    commit_point(db)
    pid = P.id

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.delete_payment(db, payment_id=pid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NODEL
    sp.rollback()
    # Then 4
    assert count_where(db, InvoicePayment, InvoicePayment.id == pid) == 1


@xfail(3176)
def test_pos_rx_46__settlement_not_editable(db, s):
    """POS-RX-46 — a settlement entry cannot be edited.
    Rules: receive_replacements RX8h [BUG-3176]."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("2000.00"), "payment_status": "paid"})
    P = spay(db, s, g.CN, "2000.00", g.R, notes="Settled")
    commit_point(db)
    pid = P.id

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.update_payment(db, payment_id=pid, payment_data=InvoicePaymentUpdate(notes="edited"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NODEL
    sp.rollback()
    # Then 4
    assert reread(db, InvoicePayment, pid).notes == "Settled"


# [claude] POS-RX-47
@xfail(3176)
def test_pos_rx_47__receipt_entry_refuses_delete(db, s):
    """POS-RX-47 — the entry made by a receipt refuses deletion.
    Rules: receive_replacements RX8a, RX8h [BUG-3176]."""
    g = repl(db, s)
    RX(db, s, g, RQ((g.RL, "4")))
    P = SETTLE(db, g.CN.id)[0]
    pid = P.id
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.delete_payment(db, payment_id=pid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.detail == NODEL
    sp.rollback()
    # Then 3
    assert count_where(db, InvoicePayment, InvoicePayment.id == pid) == 1


def test_pos_rx_48__settlement_voidable(db, s):
    """POS-RX-48 — a settlement entry can be voided: owed again, return unpaid, stock untouched.
    Rules: receive_replacements RX8i, RX8l (hold today and after BUG-3176)."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("2000.00"), "payment_status": "paid"}, r_but={"paid": True})
    P = spay(db, s, g.CN, "2000.00", g.R)
    commit_point(db)

    ipm.void_payment(db, payment_id=P.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Wrong count")

    # Then 1
    p = reread(db, InvoicePayment, P.id)
    assert p.is_voided is True
    assert p.voided_by == s.U2.id
    assert p.void_note == "Wrong count"
    assert p.voided_at is not None
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("0.00")
    assert c.payment_status == "unpaid"
    # Then 3
    r = reread(db, PurchaseOrderReturn, g.R.id)
    assert r.paid is False
    assert r.status == "completed"
    assert r.return_type == "replace"
    assert r.completed_by == s.U1.id
    # Then 4
    assert count_where(db, InventoryLedger, InventoryLedger.workspace_id == s.W1.id) == 0


# [claude] POS-RX-49
@xfail(3176)
def test_pos_rx_49__void_keeps_replacement_stock(db, s):
    """POS-RX-49 — voiding the entry made by a receipt keeps the replacement stock.
    Rules: receive_replacements RX8i, RX8l [BUG-3176]."""
    g = repl(db, s)
    RX(db, s, g, RQ((g.RL, "4")))
    P = SETTLE(db, g.CN.id)[0]
    pid = P.id
    commit_point(db)

    ipm.void_payment(db, payment_id=pid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Wrong count")

    # Then 1
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("0.00")
    assert c.payment_status == "unpaid"
    # Then 2
    assert STOCK(db, s, s.F1, s.I1).qty == 4
    # Then 3
    assert len(LEDGER(db, g.RL.id)) == 1
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    # Then 5
    assert reread(db, PurchaseOrderReturn, g.R.id).paid is False


@xfail(3176)
def test_pos_rx_50__workspace_isolation(db, s):
    """POS-RX-50 — workspace isolation: W0 and W2 returns, credit notes and stock untouched.
    Rules: receive_replacements RX8a [BUG-3176]; HR-16."""
    g0 = repl(db, s, "0")
    g = repl(db, s)
    g9 = repl(db, s, "9")
    commit_point(db)
    cn0_b, cn9_b, rl0_b, rl9_b = snap(db, g0.CN), snap(db, g9.CN), snap(db, g0.RL), snap(db, g9.RL)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert len(SETTLE(db, g.CN.id)) == 1
    assert SETTLE(db, g.CN.id)[0].workspace_id == s.W1.id
    # Then 2
    assert PAYS(db, g0.CN.id) == []
    # Then 3
    assert PAYS(db, g9.CN.id) == []
    # Then 4
    assert snap(db, g0.CN) == cn0_b
    # Then 5
    assert snap(db, g9.CN) == cn9_b
    # Then 6
    assert snap(db, g0.RL) == rl0_b
    # Then 7
    assert snap(db, g9.RL) == rl9_b
    # Then 8
    assert LEDGER(db, g0.RL.id) == []
    assert LEDGER(db, g9.RL.id) == []


@xfail(3176)
def test_pos_rx_51__w2_credit_note_left_alone(db, s):
    """POS-RX-51 — a W2 credit note linked to the W1 return: left alone, warning, receipt goes ahead.
    Rules: receive_replacements RX8k [BUG-3176]; HR-16."""
    g = repl(db, s, cn_but=cn_of(s, W2CN))
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [NOTFOUND]
    db.rollback()
    # Then 2
    assert PAYS(db, g.CN.id) == []
    # Then 3
    assert snap(db, g.CN) == cn_before
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    assert len(LEDGER(db, g.RL.id)) == 1
    # Then 5
    assert PEV(db, g.O.id).metadata_json["settled_amount"] == "0.00"
    assert PEV(db, g.O.id).metadata_json["payment_id"] is None


@xfail(3176)
def test_pos_rx_52__credit_note_locked_before_entry(db, s):
    """POS-RX-52 — the credit note is locked before the entry is written.
    Rules: receive_replacements RX8a [BUG-3176]; HR-10."""
    g = repl(db, s)
    oid, rid, rlid, w1_id, u2_id = g.O.id, g.R.id, g.RL.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, data=RQRAW(rlid, "4"))

    # Then 1
    assert rec.exact_lock("account_invoices")
    # Then 2
    ins = rec.first_insert("invoice_payments")
    assert ins is not None
    assert rec._lock_idx("account_invoices") < ins


@xfail(3176)
def test_pos_rx_53__draft_credit_note_warning(db, s):
    """POS-RX-53 — a draft credit note: no entry, the voided warning, the receipt goes ahead.
    Rules: receive_replacements RX8d [BUG-3176] (any status other than `confirmed`)."""
    g = repl(db, s, cn_but={"invoice_status": "draft"})
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [VOIDW]
    db.rollback()
    # Then 2
    assert PAYS(db, g.CN.id) == []
    # Then 3
    assert snap(db, g.CN) == cn_before
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    assert len(LEDGER(db, g.RL.id)) == 1


@xfail(3176)
def test_pos_rx_54__no_credit_note_warning(db, s):
    """POS-RX-54 — a return with no credit note: no entry, warning, the receipt goes ahead.
    Rules: receive_replacements RX8k [BUG-3176]."""
    g = repl(db, s)
    g.R.invoice_id = None
    db.flush()
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [NOTFOUND]
    db.rollback()
    # Then 2
    assert PAYS(db, g.CN.id) == []
    # Then 3
    assert snap(db, g.CN) == cn_before
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")
    assert reread(db, PurchaseOrderItem, g.L.id).quantity_received == Decimal("10.00")
    # Then 5
    assert PEV(db, g.O.id).metadata_json["settled_amount"] == "0.00"
    assert PEV(db, g.O.id).metadata_json["payment_id"] is None
    # Then 6
    assert len(REVENTS(db, g.R.id)) == 1
    assert REVENTS(db, g.R.id)[0].description == "Replacements received — 4 unit(s), 0.00 settled"


@xfail(3176)
def test_pos_rx_55__w0_credit_note_left_alone(db, s):
    """POS-RX-55 — a W0 credit note linked to the W1 return: left alone, warning.
    Rules: receive_replacements RX8k [BUG-3176]; HR-16."""
    g = repl(db, s, cn_but=cn_of(s, W0CN))
    commit_point(db)
    cn_before = snap(db, g.CN)

    result = RX(db, s, g, RQ((g.RL, "4")))

    # Then 1
    assert WARN(result) == [NOTFOUND]
    db.rollback()
    # Then 2
    assert PAYS(db, g.CN.id) == []
    # Then 3
    assert snap(db, g.CN) == cn_before
    # Then 4
    assert reread(db, PurchaseOrderReturnItem, g.RL.id).quantity_replaced == Decimal("4.00")


@xfail(3176)
def test_pos_rx_56__api_cannot_create_settlement(db, s):
    """POS-RX-56 — the payments API cannot create a settlement by hand.
    Rules: receive_replacements RX8m [BUG-3176] (fix in invoice_payment_manager)."""
    g = repl(db, s)
    commit_point(db)

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=g.CN.id, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, 20), payment_method="settled_by_replacement"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == MANUAL
    sp.rollback()
    # Then 4
    assert PAYS(db, g.CN.id) == []
    # Then 5
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("0.00")
    assert c.payment_status == "unpaid"


@xfail(3176)
def test_pos_rx_57__api_cannot_turn_cash_into_settlement(db, s):
    """POS-RX-57 — the payments API cannot turn a cash payment into a settlement.
    Rules: receive_replacements RX8m [BUG-3176] (fix in invoice_payment_manager)."""
    g = repl(db, s, cn_but={"paid_amount": Decimal("100.00"), "payment_status": "partial"})
    P = cash(db, s, g.CN, "100.00")
    commit_point(db)
    pid = P.id

    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.update_payment(db, payment_id=pid, payment_data=InvoicePaymentUpdate(payment_method="settled_by_replacement"), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == MANUAL
    sp.rollback()
    # Then 4
    assert reread(db, InvoicePayment, pid).payment_method == "cash"


def test_pos_rx_58__cash_payment_recorded(db, s):
    """POS-RX-58 — a cash payment on a credit note is still recorded by hand.
    Rules: receive_replacements RX8m (other side; holds today and after BUG-3176)."""
    g = repl(db, s)
    commit_point(db)

    result = ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=g.CN.id, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, 20), payment_method="cash"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert result.payment_method == "cash"
    assert result.payment_amount == Decimal("100.00")
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("100.00")
    assert c.payment_status == "partial"


@xfail(3176)
def test_pos_rx_59__through_payment_path(db, s):
    """POS-RX-59 — the settlement goes through the payment path: audit row and invoice event.
    Rules: receive_replacements RX8j [BUG-3176]."""
    g = repl(db, s)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert len(AUDIT(db, s)) == 1
    # Then 2
    assert itypes(db, g.CN.id).count("payment_recorded") == 1
    # Then 3
    e = next(e for e in rows_where(db, InvoiceEvent, InvoiceEvent.invoice_id == g.CN.id) if e.event_type == "payment_recorded")
    assert e.metadata_json["payment_method"] == "settled_by_replacement"
    assert e.metadata_json["payment_id"] == SETTLE(db, g.CN.id)[0].id


@xfail(3176)
def test_pos_rx_60__locked_payments_still_settled(db, s):
    """POS-RX-60 — a credit note with payments locked is still settled.
    Rules: receive_replacements RX8j [BUG-3176] (the `allow_payments` refusal is skipped)."""
    g = repl(db, s, cn_but={"allow_payments": False})
    commit_point(db)

    result = RX(db, s, g, RQ((g.RL, "4")))

    warnings = WARN(result)
    db.rollback()
    # Then 1
    assert [p.payment_amount for p in SETTLE(db, g.CN.id)] == [Decimal("2000.00")]
    # Then 2
    c = reread(db, AccountInvoice, g.CN.id)
    assert c.paid_amount == Decimal("2000.00")
    assert c.payment_status == "paid"
    assert c.allow_payments is False
    # Then 3
    assert warnings == []


@xfail(3176)
def test_pos_rx_61__foreign_credit_note_not_locked(db, s):
    """POS-RX-61 — a foreign credit note is not locked.
    Rules: receive_replacements RX8k [BUG-3176]; HR-16."""
    g = repl(db, s, cn_but=cn_of(s, W2CN))
    oid, rid, rlid, w1_id, u2_id = g.O.id, g.R.id, g.RL.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, data=RQRAW(rlid, "4"))

    # Then 1
    assert WARN(result) == [NOTFOUND]
    # Then 2
    assert rec.lock("account_invoices") is None
    # Then 3
    assert rec.first_insert("invoice_payments") is None


@xfail(3176)
def test_pos_rx_62__no_entry_return_event_zero(db, s):
    """POS-RX-62 — with no entry the return event records 0.00 settled.
    Rules: receive_replacements RX8e [BUG-3176]."""
    g = repl(db, s, cn_but=VOIDED_INV)
    commit_point(db)

    RX(db, s, g, RQ((g.RL, "4")))

    db.rollback()
    # Then 1
    assert len(REVENTS(db, g.R.id)) == 1
    E = REVENTS(db, g.R.id)[0]
    # Then 2
    assert E.description == "Replacements received — 4 unit(s), 0.00 settled"
    # Then 3
    assert E.metadata_json == {"return_id": g.R.id, "total_quantity": "4", "settled_amount": "0.00", "payment_id": None}


@xfail(2810)
def test_pos_rx_63__lock_order(db, s):
    """POS-RX-63 — lock order: the order first, then the return, then the credit note.
    Rules: receive_replacements RX1a, RX1, RX8a [BUG-2810 / BUG-3176]; HR-10."""
    g = repl(db, s)
    oid, rid, rlid, w1_id, u2_id = g.O.id, g.R.id, g.RL.id, s.W1.id, s.U2.id
    commit_point(db)
    db.expunge_all()

    with Recorder(db) as rec:
        result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=w1_id, user_id=u2_id, data=RQRAW(rlid, "4"))

    # Then 1
    assert result.id == rid
    # Then 2
    assert rec.exact_lock_of("purchase_orders")
    # Then 3
    assert rec.locked_before("purchase_orders", "purchase_order_returns")
    # Then 4
    assert rec.locked_before("purchase_order_returns", "account_invoices")
    # Then 5
    assert rec.before("purchase_orders", "purchase_order_items")
