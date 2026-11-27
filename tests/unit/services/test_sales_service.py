# ruff: noqa: SIM117, DTZ001, B017, RUF059
# (nested `with` blocks, naive datetimes and `pytest.raises(Exception)` are
# prescribed by the cards' Conventions; setup helpers return every row of a
# Given, and not every test reads each one.)
"""Unit tests for app/services/sales_service.py.

Implements tests/unit/services/sales_service.cases.md (revision 2,
2026-11-22), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: `app.services.sales_service.utcnow`
(autouse fixture `clock`, NOW naive like the real helper); the commit /
rollback / refresh spies and failing variants (`patch.object(db, ...)`); the
`create_invoice` spies and forced errors of the `Author: claude` cards; and
`SalesService._settle_replacement_credit_notes` in SR-31. Nothing else is
mocked; the lock cards record the SQL sent during the When with an
`after_cursor_execute` listener.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.U2`,
`s.A1`, `s.CU`). `# Then N` marks the checks of the card's Then line N.
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

from app.core.exceptions import NotFoundError
from app.managers.invoice_payment_manager import invoice_payment_manager as ipm
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.delivery_method import DeliveryMethod
from app.models.factory import Factory
from app.models.financial_audit_log import FinancialAuditLog
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.item import Item
from app.models.notification import Notification
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.sales_delivery import SalesDelivery
from app.models.sales_delivery_item import SalesDeliveryItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.invoice_payment import InvoicePaymentCreate, InvoicePaymentUpdate
from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryEditRequest
from app.schemas.sales_order import SalesOrderUpdate
from app.schemas.sales_order_return import (
    SalesOrderReturnCreate,
    SalesOrderReturnItemCreate,
    SalesOrderReturnVoidRequest,
)
from app.services.sales_service import SalesService, sales_service
from app.services.sales_service import sales_order_return_manager as RM
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = sales_service
assert isinstance(svc, SalesService)

MISSING = 999999999
T0 = datetime(2026, 9, 1, 8, 0)
T1 = datetime(2026, 9, 2, 9, 0)
T2 = datetime(2026, 9, 3, 10, 0)
NOW = datetime(2026, 9, 27, 12, 0, 0)
UTCDAY = date(2026, 9, 27)
D = Decimal


def NF(i):
    return f"Sales order with ID {i} not found"


def DNF(i):
    return f"Delivery with ID {i} not found"


def RNF(i):
    return f"Return with ID {i} not found"


NOACCT = "Cannot create invoice: customer account was not found in this workspace"
NOINV = "Cannot create invoice: invoicing is disabled for this account"
PAYHIST = "Invoice has payment history — confirm and void it instead"
NEEDCONF = "Confirm order info and items before creating the invoice"
INFOLOCK = "Unconfirm order info before editing it"
FINV404 = "The order's invoice was not found in this workspace"
NOACCTCN = "Cannot create credit note: customer account was not found in this workspace"
NODEL = "A settlement by replacement cannot be deleted or edited — void it with a reason instead"
RESERVED = '"settled_by_replacement" is recorded by the system and cannot be entered by hand'


def VOIDCN(R):
    return f"Return {R.return_number}: the credit note is voided — no settlement recorded"


def LOSTCN(R):
    return f"Return {R.return_number}: the credit note could not be found — no settlement recorded"


_BUGS = {
    100: "BaseDAO list methods have no sort order",
    639: "A draft that once had (voided) payments cannot be deleted",
    627: "Invoice amount entered at creation is silently discarded at confirmation",
    1019: "Sales order links to status id 10 of whichever workspace owns it, and accepts another workspace's invoice",
    1205: "Sales order approvers are never notified",
    1270: "A sales order's lines have no sort order",
    1271: "A delivery's lines have no sort order",
    2404: 'A sales order edit can set the total, "fully delivered" and "invoiced" flags',
    2425: "A return's lines have no sort order",
    2442: "An order's deliveries come back in no fixed order",
    2443: "Status-filtered delivery list pages in no fixed order",
    2764: "Sales return read before complete / void is not locked",
    2790: "Starting a sales return reopens a completed order",
    2791: "A sales line fulfilled without delivery still adds stock back when returned",
    3192: '"Create invoice" and "Finalize invoice" check the sales order without a row lock',
    3193: "The auto-drafted sales invoice copies the order's lines in no fixed order and without a workspace filter",
    3194: "A sales order's payment status can come from another workspace's invoice",
    3196: "Sales invoice and return credit-note dates use the server's local date",
    3197: "A missing sales order or delivery answers 500",
    3198: '"Complete delivery" lets the manager\'s refusals reach the client as 500',
    3199: "A sales order edit cannot clear a field",
    3200: "Sales order edits, return completion and return cancel never set `updated_by`",
    3201: "Changing a sales order's required approvals keeps the approvals already given",
    3202: 'Sales return stock-ledger note reads "SO-SO-…"',
    3203: "A blank sales return cancel reason is accepted",
    3204: "The sales order `invoice_draft_deleted` event records no invoice id",
    3206: '"Units remaining to be delivered" ignores refunded quantity',
    3207: "A completed or invoice-locked sales order can still be edited",
    3208: "Confirmed sales order info can be edited without unconfirming it",
    3209: 'Manual "Create invoice" skips the section check and logs nothing; the next section toggle deletes the draft',
    3210: 'After a `replace` return the sales order still says "fully delivered"',
    3211: "A pending sales return whose credit note is already voided can never be cancelled",
    3212: "Some sales order responses have a missing or stale `invoice_payment_status`",
    3213: "Deliveries, items or delivery lines of an unknown sales order / delivery answer `[]`",
    3215: "A sales order edit writes no activity event",
    3216: 'The "units deducted" message counts free-text lines that moved no stock',
    3219: "Creating a sales order with no lines answers 500",
    3220: 'A free-text sales line with an empty description becomes an invoice line named "Item None"',
    3217: "Delivering a `replace` return's replacement doesn't settle the return's credit note",
    3218: "Finalize and start-return refusals show the id of another workspace's invoice or account",
}


def xfail(*bugs, strict=True):
    """Expect `xfail BUG-n` -> strict xfail naming every bug and its title."""
    return pytest.mark.xfail(
        strict=strict, reason="; ".join(f"BUG-{b}: {_BUGS[b]}" for b in bugs)
    )


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Time: the service's utcnow returns NOW (naive, like the real helper)
@pytest.fixture(autouse=True)
def clock():
    with patch("app.services.sales_service.utcnow", return_value=NOW):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


def _client_account(db, ws, name):
    acct = _add(
        db,
        Account(
            workspace_id=ws.id,
            name=name,
            is_active=True,
            is_deleted=False,
            allow_invoices=True,
        ),
    )
    tag = _add(
        db, AccountTag(workspace_id=ws.id, name="Client", tag_code="client", is_active=True)
    )
    _add(db, AccountTagAssignment(workspace_id=ws.id, account_id=acct.id, tag_id=tag.id))
    return acct


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.TAG = uuid.uuid4().hex[:8]
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    for i, name in enumerate(
        ["Alice Rahman", "Bob Karim", "Chitra Das", "Dev Paul", "Esha Roy"], 1
    ):
        setattr(n, f"U{i}", make_profile(db, name=name))
    for user, ws, st in (
        (n.U1, n.W1, "active"),
        (n.U2, n.W1, "active"),
        (n.U3, n.W1, "active"),
        (n.U4, n.W1, "inactive"),
        (n.U5, n.W2, "active"),
    ):
        _add(db, WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="member", status=st))
    n.CU = n.U2
    # ST: the statuses row with id 10 (created if missing)
    if db.execute(text("SELECT 1 FROM statuses WHERE id = 10")).first() is None:
        db.execute(
            text(
                "INSERT INTO statuses (id, workspace_id, name, comment) "
                "VALUES (10, :ws, 'Confirmed', '')"
            ),
            {"ws": n.W1.id},
        )
        db.flush()
    for k, ws, name in (("0", n.W0, "Zeta West"), ("1", n.W1, "Acme Traders"), ("9", n.W2, "Xeno Foreign")):
        setattr(n, f"A{k}", _client_account(db, ws, name))
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
    n.I1 = _add(
        db, Item(workspace_id=n.W1.id, name="Chair", name_normalized="chair", unit="pcs", is_active=True)
    )
    n.IS = _add(
        db,
        Item(
            workspace_id=n.W1.id,
            name="Installation",
            name_normalized="installation",
            unit="hour",
            is_active=True,
        ),
    )
    n.P1 = _add(
        db,
        Product(
            workspace_id=n.W1.id,
            factory_id=n.F1.id,
            item_id=n.I1.id,
            qty=100,
            is_available_for_sale=True,
            avg_cost=D("1500.00"),
            created_by=n.U1.id,
        ),
    )
    n.DM1 = _add(db, DeliveryMethod(workspace_id=n.W1.id, name="Courier"))
    return n


def _wsa(s, ws):
    """'of W0' / 'of W2': (workspace, account, factory) for ws '0', '1', '2'."""
    return {
        "0": (s.W0, s.A0, s.F0),
        "1": (s.W1, s.A1, s.F1),
        "2": (s.W2, s.A9, s.F9),
    }[ws]


# --------------------------------------------------------------------------- #
# Conventions -> Given rows ("but" = keyword overrides, applied last)
# --------------------------------------------------------------------------- #


def _so_obj(s, n, ws="1", ready=False, finalized=False, completed=False, **but):
    w, a, f = _wsa(s, ws)
    fields = {
        "workspace_id": w.id,
        "sales_order_number": f"SO-{s.TAG}-{n}",
        "account_id": a.id,
        "factory_id": f.id,
        "current_status_id": 10,
        "order_date": date(2026, 9, 1),
        "contact_name": "Rahim",
        "total_amount": D("12000.00"),
        "created_by": s.U1.id,
        "is_fully_delivered": False,
        "is_invoiced": False,
        "paid": False,
        "order_info_confirmed": False,
        "items_confirmed": False,
        "invoice_confirmed": False,
        "order_completed": False,
        "invoice_id": None,
        "required_approvals": None,
        "contact_phone": None,
        "description": None,
        "expected_delivery_date": None,
        "completed_at": None,
        "completed_by": None,
        "updated_by": None,
        "items_updated_at": None,
    }
    if ready or finalized:
        fields.update(order_info_confirmed=True, items_confirmed=True)
    if finalized:
        fields.update(invoice_confirmed=True, is_invoiced=True)
    if completed:
        fields.update(order_completed=True, completed_at=T0, completed_by=s.U1.id)
    fields.update(but)
    return SalesOrder(**fields)


# Convention 'so "n"' (ws "0"/"2" = of W0 / of W2; ready; finalized; completed)
def so(db, s, n, **kw):
    return _add(db, _so_obj(s, n, **kw))


# Convention "ln(S)" (free="D" -> free "D"; service -> service line)
def ln(db, s, S, free=None, service=False, **but):
    fields = {
        "workspace_id": S.workspace_id,
        "sales_order_id": S.id,
        "item_id": s.I1.id,
        "description": None,
        "quantity_ordered": D("4.00"),
        "quantity_delivered": D("4.00"),
        "quantity_returned": D("0.00"),
        "quantity_refunded": D("0.00"),
        "unit_price": D("3000.00"),
        "line_total": D("12000.00"),
        "requires_delivery": True,
    }
    if free is not None:
        fields.update(item_id=None, description=free)
    if service:
        fields.update(item_id=s.IS.id, requires_delivery=False)
    fields.update(but)
    return _add(db, SalesOrderItem(**fields))


# Convention "linked": S.invoice_id = V.id, then db.flush()
def link(db, S, V):
    S.invoice_id = V.id
    db.flush()


# Convention "inv(S)" (confirmed; voided-inv; ws "0"/"2"; linked)
def inv(db, s, S, ws=None, confirmed=False, voided_inv=False, linked=False, **but):
    if ws is None:
        w_id, a_id = S.workspace_id, S.account_id
    else:
        w, a, _ = _wsa(s, ws)
        w_id, a_id = w.id, a.id
    fields = {
        "workspace_id": w_id,
        "account_id": a_id,
        "invoice_type": "receivable",
        "invoice_status": "draft",
        "payment_status": "unpaid",
        "invoice_amount": D("0.00"),
        "paid_amount": D("0.00"),
        "invoice_date": date(2026, 9, 1),
        "allow_payments": True,
        "created_by": s.U1.id,
        "order_type": "sales_order",
        "order_id": S.id,
    }
    if confirmed:
        fields.update(invoice_status="confirmed", invoice_amount=D("12000.00"))
    if voided_inv:
        fields.update(invoice_status="voided", void_note="dup")
    fields.update(but)
    V = _add(db, AccountInvoice(**fields))
    if linked:
        link(db, S, V)
    return V


# Convention "cn(S, a)" (voided-inv; draft; ws "0"/"2")
def cn(db, s, S, amount, ws="1", voided_inv=False, draft=False, **but):
    w, a, _ = _wsa(s, ws)
    fields = {
        "workspace_id": w.id,
        "account_id": a.id,
        "invoice_type": "payable",
        "invoice_status": "confirmed",
        "payment_status": "unpaid",
        "invoice_amount": D(amount),
        "paid_amount": D("0.00"),
        "invoice_date": date(2026, 9, 1),
        "allow_payments": True,
        "created_by": s.U1.id,
        "order_type": "sales_order",
        "order_id": S.id,
    }
    if voided_inv:
        fields.update(invoice_status="voided", void_note="dup")
    if draft:
        fields.update(invoice_status="draft")
    fields.update(but)
    return _add(db, AccountInvoice(**fields))


# Convention "invl(V, k, s)"
def invl(db, s, V, k, amount):
    return _add(
        db,
        InvoiceItem(
            workspace_id=V.workspace_id,
            invoice_id=V.id,
            line_number=k,
            description="Old line",
            quantity=D("1"),
            unit_price=D(amount),
            line_subtotal=D(amount),
            created_by=s.U1.id,
        ),
    )


# Convention 'ret(S, "n")' (refund; done; voided; of=C; ws "0"/"2")
def ret(db, s, S, n, refund=False, done=False, voided=False, of=None, ws=None, **but):
    fields = {
        "workspace_id": S.workspace_id if ws is None else _wsa(s, ws)[0].id,
        "sales_order_id": S.id,
        "return_number": f"SR-{s.TAG}-{n}",
        "return_type": "replace",
        "reason": "Broken",
        "created_by": s.U1.id,
        "status": "pending",
        "paid": False,
        "invoice_id": None,
    }
    if refund:
        fields["return_type"] = "refund"
    if done:
        fields.update(status="completed", completed_at=T0, completed_by=s.U1.id)
    if voided:
        fields["status"] = "voided"
    if of is not None:
        fields["invoice_id"] = of.id
    fields.update(but)
    return _add(db, SalesOrderReturn(**fields))


# Convention "rl(R, L, q)"
def rl(db, R, L, q, **but):
    fields = {
        "workspace_id": R.workspace_id,
        "return_id": R.id,
        "so_item_id": L.id,
        "item_id": L.item_id,
        "quantity_returned": D(q),
        "unit_price": L.unit_price,
    }
    fields.update(but)
    return _add(db, SalesOrderReturnItem(**fields))


# Convention 'dlv(S, "n")' (delivered)
def dlv(db, s, S, n, delivered=False, **but):
    fields = {
        "workspace_id": S.workspace_id,
        "sales_order_id": S.id,
        "delivery_number": f"DEL-{s.TAG}-{n}",
        "delivery_status": "planned",
        "delivery_method_id": s.DM1.id,
        "created_by": s.U1.id,
    }
    if delivered:
        fields["delivery_status"] = "delivered"
    fields.update(but)
    return _add(db, SalesDelivery(**fields))


# Convention "dl(D, L, q)"
def dl(db, Dv, L, q, **but):
    fields = {
        "workspace_id": Dv.workspace_id,
        "delivery_id": Dv.id,
        "sales_order_item_id": L.id,
        "item_id": L.item_id,
        "quantity_delivered": D(q),
    }
    fields.update(but)
    return _add(db, SalesDeliveryItem(**fields))


# Convention "pay(V, a)" (voided -> "voided pay"; settle -> "settle pay")
def pay(db, s, V, amount, voided=False, settle=False, **but):
    fields = {
        "workspace_id": V.workspace_id,
        "invoice_id": V.id,
        "payment_amount": D(amount),
        "payment_date": date(2026, 9, 2),
        "payment_method": "cash",
        "is_voided": False,
        "created_by": s.U1.id,
    }
    if voided:
        fields.update(is_voided=True, voided_at=T0, voided_by=s.U1.id, void_note="manual void")
    if settle:
        fields["payment_method"] = "settled_by_replacement"
    fields.update(but)
    return _add(db, InvoicePayment(**fields))


# Convention "appr(S, U)" (approved -> approved True, approved_at T1)
def appr(db, s, S, U, approved=False):
    return _add(
        db,
        SalesOrderApprover(
            workspace_id=S.workspace_id,
            sales_order_id=S.id,
            user_id=U.id,
            assigned_by=s.U1.id,
            approved=approved,
            approved_at=T1 if approved else None,
            assigned_at=T0,
        ),
    )


# Convention "ev(S, t)"
def ev(db, s, S, t):
    return _add(
        db,
        SalesOrderEvent(
            workspace_id=S.workspace_id,
            sales_order_id=S.id,
            event_type="note",
            description="n",
            performed_by=s.U1.id,
            created_at=t,
        ),
    )


# Convention "SCENE" (the replacement scene); keyword dicts are the card's "but … also"
def scene(db, s, L1=None, CN=None, cn_amount="3000.00", cn_lines=("3000.00",), R1=None, D1=None, rl_q="1.00", dl_q="1.00"):
    n = SimpleNamespace()
    n.S = so(db, s, "1", finalized=True, completed=True)
    n.VR = inv(db, s, n.S, confirmed=True, linked=True)
    n.L1 = ln(db, s, n.S, **{"quantity_delivered": D("3.00"), "quantity_returned": D("1.00"), **(L1 or {})})
    n.CN = cn(db, s, n.S, cn_amount, **(CN or {}))
    for k, a in enumerate(cn_lines, 1):
        invl(db, s, n.CN, k, a)
    n.R1 = ret(db, s, n.S, "1", done=True, of=n.CN, **(R1 or {}))
    rl(db, n.R1, n.L1, rl_q)
    n.D1 = dlv(db, s, n.S, "1", **(D1 or {}))
    dl(db, n.D1, n.L1, dl_q)
    return n


# Convention "SCENE-CALL"
def scene_call(db, s, n):
    return svc.complete_delivery(db, delivery_id=n.D1.id, workspace_id=s.W1.id, current_user=s.CU)


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

_COUNT_TABLES = (
    "sales_orders",
    "sales_order_items",
    "sales_order_approvers",
    "sales_order_events",
    "sales_deliveries",
    "sales_delivery_items",
    "sales_order_returns",
    "sales_order_return_items",
    "account_invoices",
    "invoice_items",
    "invoice_events",
    "invoice_payments",
    "products",
    "product_ledger",
    "notifications",
)


# Named check "nothing written": row counts of the listed tables (all workspaces)
def counts(db):
    return tuple(db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES)


def _maxled(db):
    return db.execute(text("SELECT coalesce(max(id), 0) FROM product_ledger")).scalar()


# Convention "commit point": the test commits; "nothing written" and MAXLED are taken here
def commit_point(db):
    db.commit()
    return SimpleNamespace(counts=counts(db), maxled=_maxled(db))


# Convention "X": a pending workspace, flushed, not committed
def mk_x(db):
    return make_workspace(db)


# Named check "unchanged(R)": every column of R, straight from the database
def snap(db, R):
    table = type(R).__table__
    row = db.execute(select(table).where(table.c.id == R.id)).mappings().one_or_none()
    return None if row is None else dict(row)


def snap_id(db, model, rid):
    table = model.__table__
    row = db.execute(select(table).where(table.c.id == rid)).mappings().one_or_none()
    return None if row is None else dict(row)


# Given step "db.expunge_all()": the standing rows used in the When are loaded first,
# so their ids stay readable on the detached objects
def expunge_all(db, s):
    for row in (s.W0, s.W1, s.W2, s.U1, s.U2, s.U3, s.CU, s.A1, s.I1, s.P1):
        assert row.id is not None
    db.expunge_all()


# Named check "re-read R"
def rr(db, model, rid):
    db.expire_all()
    return db.get(model, rid)


# Named checks "x_gone" / "x_kept"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


def x_kept(db, x_id):
    return db.get(Workspace, x_id) is not None


def count_where(db, model, *where):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


def rows_where(db, model, *where):
    db.expire_all()
    return list(db.scalars(select(model).where(*where).order_by(model.id)))


def _id(x):
    return x if isinstance(x, int) else x.id


# Named check "EV(S)" / "types(S)"
def EV(db, S):
    return rows_where(db, SalesOrderEvent, SalesOrderEvent.sales_order_id == _id(S))


def types(db, S):
    return [e.event_type for e in EV(db, S)]


def ev_of(db, S, event_type):
    """The single event of that type on S (asserted one)."""
    found = [e for e in EV(db, S) if e.event_type == event_type]
    assert len(found) == 1
    return found[0]


# Named check "itypes(V)"
def iev(db, V):
    return rows_where(db, InvoiceEvent, InvoiceEvent.invoice_id == _id(V))


def itypes(db, V):
    return [e.event_type for e in iev(db, V)]


# Named check "LINES(V)"
def LINES(db, V):
    db.expire_all()
    return list(
        db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == _id(V))
            .order_by(InvoiceItem.line_number, InvoiceItem.id)
        )
    )


def line_for(db, V, so_item_id):
    found = [x for x in LINES(db, V) if x.source_order_item_id == so_item_id]
    assert len(found) == 1
    return found[0]


# Named checks "PAYS(V)" / "SETTLE(V)"
def PAYS(db, V):
    return rows_where(db, InvoicePayment, InvoicePayment.invoice_id == _id(V))


def SETTLE(db, V):
    return [p for p in PAYS(db, V) if p.payment_method == "settled_by_replacement"]


# Named check "AUD(pid)"
def AUD(db, pid):
    return rows_where(
        db,
        FinancialAuditLog,
        FinancialAuditLog.entity_type == "payment",
        FinancialAuditLog.entity_id == pid,
    )


# Named check "NEWLED"
def NEWLED(db, cp):
    return rows_where(db, ProductLedger, ProductLedger.id > cp.maxled)


# Named check "notes()"
def notes(db):
    db.expire_all()
    return list(db.scalars(select(Notification).order_by(Notification.id)))


def all_pays(db):
    return count_where(db, InvoicePayment)


# Named check "session clean"
def assert_session_clean(db):
    assert not db.new
    assert not db.dirty
    assert not db.deleted


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})


# Named check "HOR(S)"
def HOR(db, s, S):
    return RM.has_open_return(db, sales_order_id=S.id, workspace_id=s.W1.id)


# MSG / MSGD: compare type and message (and details)
def MSG(kind, txt):
    return (kind, txt)


def MSGD(kind, txt, d):
    return (kind, txt, d)


def mt(m):
    return (m.type, m.message)


def mtd(m):
    return (m.type, m.message, m.details)


def mts(msgs):
    return [mt(m) for m in msgs]


# Named check "idset(r)"
def idset(r):
    return {o.id for o in r}


def returns_msgs(msgs):
    return [m for m in msgs if m.message.startswith("Return ")]


# Convention "spies"
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield cm, rb


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with patch.object(db, "commit", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


# Convention "failing refresh"
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


# Convention "Statement recorder"
_FROM = re.compile(
    r"\bFROM\b(.*?)(?=\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bOFFSET\b|\bFOR UPDATE\b|$)",
    re.DOTALL,
)


def _from_clause(st):
    m = _FROM.search(st)
    return "" if m is None else m.group(1)


def _from_tables(st):
    clause = _from_clause(st)
    names = []
    for part in re.split(r",|\bJOIN\b", clause):
        tok = part.strip().split()
        if tok:
            names.append(tok[0].strip('"'))
    return names


def _flat(params):
    out = []
    stack = [params]
    while stack:
        p = stack.pop()
        if isinstance(p, dict):
            stack.extend(p.values())
        elif isinstance(p, (list, tuple)):
            stack.extend(p)
        else:
            out.append(p)
    return out


class Recorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append((statement, parameters))

    def __enter__(self):
        event.listen(self.bind, "after_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "after_cursor_execute", self._record)
        return False

    def selects(self):
        return [
            (i, st, p)
            for i, (st, p) in enumerate(self.statements)
            if st.lstrip().upper().startswith("SELECT")
        ]

    def first(self, table):
        for _, st, _ in self.selects():
            if table in _from_tables(st):
                return st
        return None

    def count_from(self, table):
        return len([1 for _, st, _ in self.selects() if table in _from_tables(st)])

    def row_lock(self, table):
        st = self.first(table)
        return (
            st is not None
            and _from_tables(st) == [table]
            and "JOIN" not in _from_clause(st).upper()
            and re.search(r"FOR UPDATE$", st.rstrip()) is not None
            and "SKIP LOCKED" not in st
            and "NOWAIT" not in st
        )

    def id_order(self, table):
        """id order on T: a SELECT from T whose ORDER BY starts with T.id ascending."""
        pat = re.compile(rf"ORDER BY {table}\.id\b(?!\s+DESC)")
        return any(table in _from_tables(st) and pat.search(st) for _, st, _ in self.selects())

    def cnlock(self, vid):
        for i, st, p in self.selects():
            if (
                _from_tables(st) == ["account_invoices"]
                and "JOIN" not in _from_clause(st).upper()
                and re.search(r"FOR UPDATE$", st.rstrip()) is not None
                and "SKIP LOCKED" not in st
                and "NOWAIT" not in st
                and vid in _flat(p)
            ):
                return i
        return None

    def payread(self, vid):
        for i, st, p in self.selects():
            if "invoice_payments" in _from_tables(st) and vid in _flat(p):
                return i
        return None


# The invoice data passed to a wrapped create_invoice did not set invoice_amount
def sent_invoice_amount(ci):
    kwargs = ci.call_args.kwargs
    data = kwargs.get("invoice_data", ci.call_args.args[1] if len(ci.call_args.args) > 1 else None)
    if isinstance(data, dict):
        return "invoice_amount" in data
    return "invoice_amount" in data.model_fields_set


def ret_create(rtype, *items):
    """SalesOrderReturnCreate(return_type=rtype, reason="Broken", items=[(L, q), ...])."""
    return SalesOrderReturnCreate(
        return_type=rtype,
        reason="Broken",
        items=[SalesOrderReturnItemCreate(so_item_id=L if isinstance(L, int) else L.id, quantity_returned=D(q)) for L, q in items],
    )


def dcreate(s, S):
    return SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=s.DM1.id, scheduled_date=date(2026, 10, 5))


def order_data(s, total):
    return {
        "account_id": s.A1.id,
        "factory_id": s.F1.id,
        "order_date": date(2026, 9, 1),
        "contact_name": "Rahim",
        "total_amount": D(total),
    }


def chair_line(s):
    return {
        "item_id": s.I1.id,
        "description": None,
        "quantity_ordered": D("2"),
        "unit_price": D("3000.00"),
        "line_total": D("6000.00"),
        "requires_delivery": True,
    }


def ribbon_line():
    return {
        "item_id": None,
        "description": "Ribbon",
        "quantity_ordered": D("0.50"),
        "unit_price": D("0.25"),
        "line_total": D("0.13"),
        "requires_delivery": True,
    }


# =========================================================================== #
# Shared: Order response (OR)
# =========================================================================== #


@xfail(3212)
def test_ss_or_01__create_invoice_answers_payment_status(db, s):
    """SS-OR-01 — "Create invoice" answers the new draft's payment status.
    Rules: OR1 [BUG-3212]."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert getattr(result, "invoice_payment_status", None) == "unpaid"


@xfail(3212)
def test_ss_or_02__complete_delivery_answers_payment_status(db, s):
    """SS-OR-02 — "Complete delivery" answers the order's payment status, read after the commit.
    Rules: OR1 [BUG-3212]; DV5."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    commit_point(db)
    db.expire_all()
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    assert getattr(order, "invoice_payment_status", None) == "unpaid"


def test_ss_or_03__fulfil_answers_payment_status(db, s):
    """SS-OR-03 — "Fulfil line" answers the order's payment status.
    Rules: OR1 (fulfil part, already true today; spec Gap log G17)."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    LS = ln(db, s, S, service=True, quantity_ordered=D("2.00"), quantity_delivered=D("0.00"), unit_price=D("500.00"), line_total=D("1000.00"))
    commit_point(db)
    db.expire_all()
    result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    assert getattr(order, "invoice_payment_status", None) == "unpaid"


@xfail(2790)
def test_ss_or_04__pending_return_says_so(db, s):
    """SS-OR-04 — an order with a pending return says so.
    Rules: OR2 [BUG-2790]; OR3."""
    S = so(db, s, "1", finalized=True, completed=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    result = svc.get_sales_order(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert getattr(result, "has_open_return", None) is True
    # Then 3
    assert rr(db, SalesOrder, S.id).order_completed is True


@xfail(2790)
def test_ss_or_05__only_pending_return_is_open(db, s):
    """SS-OR-05 — only a pending return counts as open.
    Rules: OR2 [BUG-2790]."""
    S = so(db, s, "1", finalized=True, completed=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    R1 = ret(db, s, S, "1", done=True)
    rl(db, R1, L1, "1.00")
    ret(db, s, S, "2", voided=True)
    commit_point(db)
    result = svc.get_sales_order(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert getattr(result, "has_open_return", None) is False


# =========================================================================== #
# Shared: Notifications (N) — BUG-1205
# =========================================================================== #


@xfail(1205)
def test_ss_n_01__add_approver_notifies(db, s):
    """SS-N-01 — adding an approver notifies the new approver.
    Rules: N1 [BUG-1205]; AA2."""
    S = so(db, s, "1")
    commit_point(db)
    result = svc.add_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    # Then 1
    assert result.user_id == s.U3.id
    # Then 2
    db.rollback()
    assert any(
        n.recipient_user_id == s.U3.id and n.entity_type == "sales_order" and n.entity_id == S.id
        for n in notes(db)
    )


@xfail(1205)
def test_ss_n_02__last_section_confirm_notifies(db, s):
    """SS-N-02 — confirming the last section notifies (section and draft).
    Rules: N2, N3 [BUG-1205]; SC4."""
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    appr(db, s, S, s.U3)
    commit_point(db)
    result = svc.set_section_confirm(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, section="items", confirmed=True)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert len([n for n in notes(db) if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1


@xfail(1205)
def test_ss_n_03__finalize_notifies(db, s):
    """SS-N-03 — finalizing the invoice notifies.
    Rules: N4 [BUG-1205]."""
    S = so(db, s, "1", ready=True)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    appr(db, s, S, s.U3, approved=True)
    commit_point(db)
    result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert len([n for n in notes(db) if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1


@xfail(1205)
def test_ss_n_04__manual_create_invoice_notifies(db, s):
    """SS-N-04 — "Create invoice" by hand notifies the draft.
    Rules: N3 [BUG-1205]; I4."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    appr(db, s, S, s.U3)
    commit_point(db)
    result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert len([n for n in notes(db) if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1


# =========================================================================== #
# SalesService._attach_receivable_invoice_to_sales_order
# =========================================================================== #


def test_ss_a_01__draft_created_linked_flushed_not_committed(db, s):
    """SS-A-01 — the draft is created with its fields, linked and flushed, not committed.
    Rules: A4, A6, A8, A9."""
    S = so(db, s, "1", ready=True, description="Blue chairs")
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.commit()
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is not None
    assert row.is_invoiced is True
    assert row.items_updated_at == NOW
    # Then 5
    V = rr(db, AccountInvoice, row.invoice_id)
    assert V.workspace_id == s.W1.id
    assert V.account_id == s.A1.id
    assert V.invoice_type == "receivable"
    assert V.invoice_status == "draft"
    assert V.order_type == "sales_order"
    assert V.order_id == S.id
    # Then 6
    V = rr(db, AccountInvoice, row.invoice_id)
    assert V.description == f"Auto-created from sales order SO-{s.TAG}-1"
    assert V.notes == "Blue chairs"
    assert V.due_date is None
    assert V.allow_payments is True
    assert V.payment_locked_reason is None
    # Then 7
    V = rr(db, AccountInvoice, row.invoice_id)
    assert V.invoice_number is None
    assert V.vendor_invoice_number is None
    # Then 8
    V = rr(db, AccountInvoice, row.invoice_id)
    assert V.invoice_amount == D("12000.00")
    # Then 9
    assert itypes(db, V.id).count("items_synced") == 1
    # Then 10
    assert "created" in itypes(db, V.id)
    # Then 11
    assert len(EV(db, S.id)) == 0
    # Then 12
    assert notes(db) == []


def test_ss_a_02__each_line_copied(db, s):
    """SS-A-02 — each order line becomes one invoice line with the copied values.
    Rules: A7."""
    S = so(db, s, "1", ready=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"), line_total=D("11999.99"))
    L2 = ln(db, s, S, free="Ribbon", quantity_ordered=D("0.50"), quantity_delivered=D("0.00"), unit_price=D("0.25"), line_total=D("0.13"))
    L3 = ln(db, s, S, service=True, quantity_ordered=D("2.00"), quantity_delivered=D("0.00"), unit_price=D("500.00"), line_total=D("1000.00"))
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    vid = S.invoice_id
    # Then 1
    assert len(LINES(db, vid)) == 3
    assert sorted(x.line_number for x in LINES(db, vid)) == [1, 2, 3]
    # Then 2
    x = line_for(db, vid, L1.id)
    assert x.description == "Chair"
    assert x.item_id == s.I1.id
    assert x.source_order_item_type == "so_item"
    assert x.quantity == D("4.00")
    assert x.unit == "pcs"
    assert x.unit_price == D("3000.00")
    assert x.line_subtotal == D("11999.99")
    # Then 3
    x = line_for(db, vid, L2.id)
    assert x.description == "Ribbon"
    assert x.item_id is None
    assert x.quantity == D("0.50")
    assert x.unit is None
    assert x.unit_price == D("0.25")
    assert x.line_subtotal == D("0.13")
    # Then 4
    x = line_for(db, vid, L3.id)
    assert x.description == "Installation"
    assert x.item_id == s.IS.id
    assert x.unit == "hour"
    assert x.line_subtotal == D("1000.00")
    # Then 5
    assert rr(db, AccountInvoice, vid).invoice_amount == D("13000.12")


@xfail(3220)
def test_ss_a_03__empty_free_text_named_line_1(db, s):
    """SS-A-03 — a free-text line with an empty description is named `Line 1`, never "Item None".
    Rules: A7, A7a [BUG-3220]."""
    S = so(db, s, "1", ready=True)
    L1 = ln(db, s, S, free="", quantity_delivered=D("0.00"))
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    vid = S.invoice_id
    # Then 1
    assert len(LINES(db, vid)) == 1
    # Then 2
    x = LINES(db, vid)[0]
    assert x.line_number == 1
    assert x.description == "Line 1"
    assert "None" not in x.description
    assert x.item_id is None
    assert x.source_order_item_id == L1.id


@xfail(3193)
def test_ss_a_04__w2_line_not_copied(db, s):
    """SS-A-04 — a W2 line row under the order is not copied.
    Rules: A7 [BUG-3193]; HR-16."""
    S = so(db, s, "1", ready=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    ln(db, s, S, workspace_id=s.W2.id, quantity_delivered=D("0.00"))
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    vid = rr(db, SalesOrder, S.id).invoice_id
    assert vid is not None
    # Then 2
    assert [x.source_order_item_id for x in LINES(db, vid)] == [L1.id]


@xfail(3193)
def test_ss_a_05__w0_line_not_copied(db, s):
    """SS-A-05 — a W0 line row under the order is not copied.
    Rules: A7 [BUG-3193]; HR-16."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, workspace_id=s.W0.id, quantity_delivered=D("0.00"))
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    vid = rr(db, SalesOrder, S.id).invoice_id
    assert vid is not None
    # Then 2
    assert [x.source_order_item_id for x in LINES(db, vid)] == [L1.id]


@xfail(3196)
def test_ss_a_06__draft_dated_utc_day(db, s):
    """SS-A-06 — the draft is dated with the UTC day.
    Rules: A4 [BUG-3196]."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    vid = rr(db, SalesOrder, S.id).invoice_id
    assert vid is not None
    # Then 2
    assert rr(db, AccountInvoice, vid).invoice_date == UTCDAY


@xfail(3193)
def test_ss_a_07__lines_read_in_workspace_in_id_order(db, s):
    """SS-A-07 — the order's lines are read in this workspace, in id order.
    Rules: A7 [BUG-3193]; HR-6."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    ln(db, s, S, quantity_delivered=D("0.00"), quantity_ordered=D("1.00"), line_total=D("3000.00"))
    commit_point(db)
    sid = S.id
    expunge_all(db, s)
    S2 = db.get(SalesOrder, sid)
    with Recorder(db) as rec:
        svc._attach_receivable_invoice_to_sales_order(db, order=S2, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert rec.first("sales_order_items") is not None
    # Then 2
    assert "ORDER BY" in rec.first("sales_order_items")
    # Then 3
    assert "sales_order_items.workspace_id" in rec.first("sales_order_items")


# [claude]
@xfail(3193, strict=False)
def test_ss_a_07b__line_numbers_follow_id_order_after_rewrite(db, s):
    """SS-A-07b — invoice line numbers follow line id order after a row is rewritten.
    Rules: A7 [BUG-3193]."""
    S = so(db, s, "1", ready=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    L2 = ln(db, s, S, quantity_delivered=D("0.00"), quantity_ordered=D("1.00"), line_total=D("3000.00"))
    commit_point(db)
    db.execute(text("UPDATE sales_order_items SET unit_price = unit_price WHERE id = :i"), {"i": L1.id})
    db.expire_all()
    svc._attach_receivable_invoice_to_sales_order(db, order=db.get(SalesOrder, S.id), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert len(LINES(db, db.get(SalesOrder, S.id).invoice_id)) == 2
    # Then 2
    assert [x.source_order_item_id for x in LINES(db, db.get(SalesOrder, S.id).invoice_id)] == [L1.id, L2.id]


# [claude]
@xfail(627)
def test_ss_a_08__no_invoice_amount_sent(db, s):
    """SS-A-08 — no `invoice_amount` is sent to create_invoice.
    Rules: A4 [BUG-627]."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    with patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert ci.call_count == 1
    # Then 2
    assert not sent_invoice_amount(ci)
    # Then 3
    assert rr(db, AccountInvoice, rr(db, SalesOrder, S.id).invoice_id).invoice_amount == D("12000.00")


def test_ss_a_09__w2_account_not_found(db, s):
    """SS-A-09 — the account of W2 is not found: 422, nothing written.
    Rules: A2; HR-16."""
    S = so(db, s, "1", ready=True, account_id=s.A9.id)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCT
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is None
    assert row.is_invoiced is False


def test_ss_a_10__w0_account_not_found(db, s):
    """SS-A-10 — the account of W0 is not found: 422.
    Rules: A2; HR-16."""
    S = so(db, s, "1", ready=True, account_id=s.A0.id)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCT
    # Then 3
    assert counts(db) == cp.counts


def test_ss_a_11__invoicing_disabled(db, s):
    """SS-A-11 — an account with invoicing disabled: 422.
    Rules: A3."""
    s.A1.allow_invoices = False
    db.flush()
    S = so(db, s, "1", ready=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOINV
    # Then 3
    assert counts(db) == cp.counts


def test_ss_a_12__deleted_account_400_passes(db, s):
    """SS-A-12 — a deleted account: the invoice manager's 400 passes.
    Rules: A2, A4."""
    s.A1.is_deleted = True
    db.flush()
    S = so(db, s, "1", ready=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot create invoice for deleted account"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_a_13__inactive_account_400_passes(db, s):
    """SS-A-13 — an inactive account: the invoice manager's 400 passes.
    Rules: A4."""
    s.A1.is_active = False
    db.flush()
    S = so(db, s, "1", ready=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot create invoice for inactive account"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_a_14__invoicing_disabled_checked_before_deleted(db, s):
    """SS-A-14 — invoicing disabled is checked before deleted.
    Rules: A3."""
    s.A1.allow_invoices = False
    s.A1.is_deleted = True
    db.flush()
    S = so(db, s, "1", ready=True)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOINV


# [claude]
def test_ss_a_15__404_from_create_invoice_becomes_422(db, s):
    """SS-A-15 — a 404 from create_invoice becomes the 422, with the 404 as cause.
    Rules: A5."""
    S = so(db, s, "1", ready=True)
    nf = HTTPException(status_code=404, detail="Account with ID 1 not found")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.account_invoice_manager, "create_invoice", side_effect=nf):
            svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCT
    # Then 3
    assert exc.value.__cause__ is nf


# [claude]
def test_ss_a_16__other_http_exception_passes_as_is(db, s):
    """SS-A-16 — any other HTTPException from create_invoice passes as the same object.
    Rules: A5."""
    S = so(db, s, "1", ready=True)
    other = HTTPException(status_code=409, detail="x")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.account_invoice_manager, "create_invoice", side_effect=other):
            svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value is other


def test_ss_a_17__no_lines_gives_empty_draft(db, s):
    """SS-A-17 — an order with no lines gets an empty 0.00 draft.
    Rules: A7."""
    S = so(db, s, "1", ready=True)
    commit_point(db)
    svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    vid = rr(db, SalesOrder, S.id).invoice_id
    assert vid is not None
    # Then 2
    assert LINES(db, vid) == []
    # Then 3
    assert rr(db, AccountInvoice, vid).invoice_amount == D("0.00")


# =========================================================================== #
# SalesService._delete_linked_draft_invoice_for_so
# =========================================================================== #


def test_ss_dd_01__no_invoice_nothing_happens(db, s):
    """SS-DD-01 — no invoice linked: nothing happens.
    Rules: DD1."""
    S = so(db, s, "1", order_info_confirmed=True)
    cp = commit_point(db)
    result = svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert counts(db) == cp.counts


def test_ss_dd_02__confirmed_invoice_stays(db, s):
    """SS-DD-02 — a confirmed invoice stays linked.
    Rules: DD2."""
    S = so(db, s, "1")
    V = inv(db, s, S, confirmed=True, linked=True)
    cp = commit_point(db)
    before = snap(db, V)
    svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert counts(db) == cp.counts
    # Then 2
    assert rr(db, SalesOrder, S.id).invoice_id == V.id
    # Then 3
    assert snap(db, V) == before


def test_ss_dd_03__voided_invoice_stays(db, s):
    """SS-DD-03 — a voided invoice stays linked.
    Rules: DD2."""
    S = so(db, s, "1")
    V = inv(db, s, S, voided_inv=True, linked=True)
    cp = commit_point(db)
    svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert counts(db) == cp.counts
    # Then 2
    assert rr(db, SalesOrder, S.id).invoice_id == V.id


def test_ss_dd_04__w2_draft_not_deleted(db, s):
    """SS-DD-04 — a W2 draft linked to the order is not deleted.
    Rules: DD2; HR-16."""
    S = so(db, s, "1")
    V9 = inv(db, s, S, ws="2", linked=True)
    cp = commit_point(db)
    before = snap(db, V9)
    svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert counts(db) == cp.counts
    # Then 2
    assert rr(db, SalesOrder, S.id).invoice_id == V9.id
    # Then 3
    assert snap(db, V9) == before


def test_ss_dd_05__w0_draft_not_deleted(db, s):
    """SS-DD-05 — a W0 draft linked to the order is not deleted.
    Rules: DD2; HR-16."""
    S = so(db, s, "1")
    V0 = inv(db, s, S, ws="0", linked=True)
    cp = commit_point(db)
    svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert counts(db) == cp.counts
    # Then 2
    assert rr(db, SalesOrder, S.id).invoice_id == V0.id


def test_ss_dd_06__draft_deleted_unlinked_logged(db, s):
    """SS-DD-06 — a draft is deleted, the order unlinked and the delete logged; nothing committed.
    Rules: DD3."""
    S = so(db, s, "1", order_info_confirmed=True, is_invoiced=True, paid=True)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    vid = V.id
    commit_point(db)
    with spies(db) as (cm, rb):
        svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert rr(db, AccountInvoice, vid) is None
    # Then 4
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == vid) == 0
    # Then 5
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is None
    assert row.invoice_confirmed is False
    assert row.is_invoiced is False
    assert row.paid is False
    # Then 6
    assert types(db, S) == ["invoice_draft_deleted"]
    # Then 7
    e = EV(db, S)[0]
    assert e.description == f"Draft invoice #{vid} deleted"
    assert e.performed_by == s.U2.id


@xfail(3204)
def test_ss_dd_07__delete_log_names_invoice(db, s):
    """SS-DD-07 — the delete log entry names the deleted invoice.
    Rules: DD4 [BUG-3204]."""
    S = so(db, s, "1", order_info_confirmed=True, is_invoiced=True)
    V = inv(db, s, S, linked=True)
    vid = V.id
    commit_point(db)
    svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert types(db, S) == ["invoice_draft_deleted"]
    # Then 2
    assert EV(db, S)[0].metadata_json == {"invoice_id": vid}


@xfail(639)
def test_ss_dd_08__draft_with_payment_history_refused(db, s):
    """SS-DD-08 — a draft with payment history is refused and kept.
    Rules: DD3 [BUG-639]."""
    S = so(db, s, "1", is_invoiced=True)
    V = inv(db, s, S, paid_amount=D("100.00"), payment_status="partial", linked=True)
    pay(db, s, V, "100.00")
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active or not db.is_active:
        # a failed flush leaves the savepoint inactive but not closed (DISCREPANCY-5)
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == PAYHIST
    # Then 3
    assert rr(db, AccountInvoice, V.id) is not None
    # Then 4
    assert len(EV(db, S.id)) == 0


def test_ss_dd_09__payment_history_refused_draft_kept(db, s):
    """SS-DD-09 — a draft with payment history is refused one way or another; the draft and its payment are kept (today and after the fix).
    Rules: DD3 (holds before and after BUG-639)."""
    S = so(db, s, "1", is_invoiced=True)
    V = inv(db, s, S, paid_amount=D("100.00"), payment_status="partial", linked=True)
    P = pay(db, s, V, "100.00")
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(Exception):
        svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active or not db.is_active:
        # a failed flush leaves the savepoint inactive but not closed (DISCREPANCY-5)
        sp.rollback()
    # Then 2
    assert rr(db, AccountInvoice, V.id) is not None
    assert db.get(InvoicePayment, P.id) is not None
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id == V.id
    assert row.is_invoiced is True
    # Then 4
    assert len(EV(db, S.id)) == 0


# =========================================================================== #
# SalesService._sync_draft_invoice_for_so
# =========================================================================== #


def test_ss_y_01__financially_locked_nothing(db, s):
    """SS-Y-01 — a financially locked order: nothing happens.
    Rules: Y1."""
    S = so(db, s, "1", finalized=True)
    V = inv(db, s, S, confirmed=True, linked=True)
    cp = commit_point(db)
    before = snap(db, V)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts
    # Then 3
    assert snap(db, V) == before


def test_ss_y_02__only_info_confirmed_draft_removed(db, s):
    """SS-Y-02 — only order info confirmed and a draft linked: the draft is removed.
    Rules: Y2."""
    S = so(db, s, "1", order_info_confirmed=True, is_invoiced=True)
    V = inv(db, s, S, linked=True)
    vid = V.id
    commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert rr(db, AccountInvoice, vid) is None
    # Then 3
    assert types(db, S) == ["invoice_draft_deleted"]


def test_ss_y_03__nothing_confirmed_no_invoice(db, s):
    """SS-Y-03 — no section confirmed and no invoice: nothing happens.
    Rules: Y2."""
    S = so(db, s, "1")
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_04__only_items_confirmed_no_draft(db, s):
    """SS-Y-04 — only items confirmed and no invoice: no draft.
    Rules: Y2."""
    S = so(db, s, "1", items_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_05__only_info_confirmed_no_draft(db, s):
    """SS-Y-05 — only order info confirmed and no invoice: no draft.
    Rules: Y2."""
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_06__draft_already_linked_no_second(db, s):
    """SS-Y-06 — both confirmed and a draft already linked: no second draft.
    Rules: Y3."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    inv(db, s, S, linked=True)
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_07__voided_invoice_linked_nothing(db, s):
    """SS-Y-07 — both confirmed and a voided invoice linked: nothing happens.
    Rules: Y3."""
    S = so(db, s, "1", ready=True)
    inv(db, s, S, voided_inv=True, linked=True)
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_08__w2_invoice_linked_nothing(db, s):
    """SS-Y-08 — both confirmed and a W2 invoice linked: nothing happens.
    Rules: Y3; HR-16."""
    S = so(db, s, "1", ready=True)
    inv(db, s, S, ws="2", linked=True)
    cp = commit_point(db)
    result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == cp.counts


def test_ss_y_09__draft_made_logged_returned(db, s):
    """SS-Y-09 — both confirmed and no invoice: a draft is made, logged and its id returned; nothing committed.
    Rules: Y4."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert rr(db, SalesOrder, S.id).invoice_id == result
    # Then 5
    assert types(db, S) == ["invoice_draft_created"]
    # Then 6
    e = EV(db, S)[0]
    assert e.description == f"Draft invoice #{result} linked to SO-{s.TAG}-1"
    assert e.metadata_json == {"invoice_id": result}
    assert e.performed_by == s.U2.id


def test_ss_y_10__draft_refusal_passes(db, s):
    """SS-Y-10 — the draft step's refusal passes on.
    Rules: Y4, A3."""
    s.A1.allow_invoices = False
    db.flush()
    S = so(db, s, "1", ready=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc._sync_draft_invoice_for_so(db, order=S, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOINV
    # Then 3
    assert counts(db) == cp.counts


# =========================================================================== #
# SalesService.create_invoice_for_sales_order
# =========================================================================== #


def _inv_of(db, S):
    return rr(db, AccountInvoice, rr(db, SalesOrder, S.id).invoice_id)


def test_ss_i_01__draft_created_committed(db, s):
    """SS-I-01 — the draft is created by hand, committed, and the order returned re-read.
    Rules: I4, I5; TC1, TC2."""
    S = so(db, s, "1", ready=True, required_approvals=2)
    ln(db, s, S, quantity_delivered=D("0.00"))
    appr(db, s, S, s.U3)
    commit_point(db)
    result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == S.id
    # Then 3
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is not None
    assert row.is_invoiced is True
    # Then 4
    V = _inv_of(db, S)
    assert V.invoice_type == "receivable"
    assert V.invoice_status == "draft"
    assert V.order_id == S.id
    assert V.invoice_amount == D("12000.00")


@xfail(3209)
def test_ss_i_02__manual_create_logs_draft(db, s):
    """SS-I-02 — "Create invoice" logs the draft like the automatic one.
    Rules: I4 [BUG-3209]."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert types(db, S) == ["invoice_draft_created"]
    # Then 3
    e = EV(db, S)[0]
    assert e.description == f"Draft invoice #{result.invoice_id} linked to SO-{s.TAG}-1"
    assert e.metadata_json == {"invoice_id": result.invoice_id}
    assert e.performed_by == s.U2.id


@xfail(3209)
def test_ss_i_03__only_info_confirmed_400(db, s):
    """SS-I-03 — only order info confirmed: 400, nothing written.
    Rules: I3a [BUG-3209]; TC3."""
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDCONF
    # Then 3
    assert X not in db
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3209)
def test_ss_i_04__only_items_confirmed_400(db, s):
    """SS-I-04 — only items confirmed: 400.
    Rules: I3a [BUG-3209]."""
    S = so(db, s, "1", items_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDCONF
    # Then 3
    assert counts(db) == cp.counts


@xfail(3209)
def test_ss_i_05__neither_confirmed_400(db, s):
    """SS-I-05 — neither section confirmed: 400.
    Rules: I3a [BUG-3209]."""
    S = so(db, s, "1")
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NEEDCONF
    # Then 3
    assert counts(db) == cp.counts


def test_ss_i_06__draft_already_linked_409(db, s):
    """SS-I-06 — a draft already linked: 409, nothing written, the extra row is gone.
    Rules: I2; TC3."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    inv(db, s, S, linked=True)
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Invoice already exists for this sales order"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert_session_clean(db)
    # Then 6
    assert counts(db) == cp.counts
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_i_07__voided_invoice_linked_409(db, s):
    """SS-I-07 — a voided invoice linked: also 409.
    Rules: I2."""
    S = so(db, s, "1", ready=True)
    inv(db, s, S, voided_inv=True, linked=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Invoice already exists for this sales order"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_i_08__is_invoiced_without_link_409(db, s):
    """SS-I-08 — no invoice linked but `is_invoiced` set: 409.
    Rules: I3."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Invoice already exists for this sales order"
    # Then 3
    assert counts(db) == cp.counts


@xfail(3197)
def test_ss_i_09__unknown_order_404(db, s):
    """SS-I-09 — an unknown order: 404.
    Rules: I1, G1 [BUG-3197]."""
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)
    # Then 3
    assert counts(db) == cp.counts


def test_ss_i_10__unknown_order_rolled_back(db, s):
    """SS-I-10 — an unknown order is refused and rolled back (today and after the fix).
    Rules: I1, G1; TC3."""
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(Exception):
        svc.create_invoice_for_sales_order(db, order_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert X not in db
    # Then 3
    assert counts(db) == cp.counts
    # Then 4
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3192)
def test_ss_i_11__order_read_with_row_lock(db, s):
    """SS-I-11 — the order is read with a row lock before any check.
    Rules: I1 [BUG-3192]; HR-10."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    sid = S.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.create_invoice_for_sales_order(db, order_id=sid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == sid
    # Then 2
    assert rec.row_lock("sales_orders")


def test_ss_i_12__failing_commit_leaves_no_invoice(db, s):
    """SS-I-12 — a failing commit leaves no invoice.
    Rules: I4; TC4."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.order_type == "sales_order", AccountInvoice.order_id == S.id) == 0
    # Then 4
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is None
    assert row.is_invoiced is False


def test_ss_i_13__account_refusal_rolled_back(db, s):
    """SS-I-13 — the account refusal passes and everything is rolled back.
    Rules: I4, A2; TC3."""
    S = so(db, s, "1", ready=True, account_id=s.A9.id)
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCT
    # Then 3
    assert X not in db
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


# =========================================================================== #
# SalesService.finalize_sales_order_invoice
# =========================================================================== #


def test_ss_f_01__invoice_confirmed_order_locked_logged(db, s):
    """SS-F-01 — the invoice is confirmed, the order locked and logged; committed.
    Rules: F6, F7, F8; TC1, TC2."""
    S = so(db, s, "1", ready=True)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == S.id
    assert result.invoice_payment_status == "unpaid"
    # Then 3
    db.rollback()
    v = rr(db, AccountInvoice, V.id)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == D("12000.00")
    # Then 4
    assert "confirmed" in itypes(db, V)
    # Then 5
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_confirmed is True
    assert row.order_info_confirmed is True
    assert row.items_confirmed is True
    # Then 6
    assert types(db, S)[-1] == "invoice_confirmed"
    # Then 7
    e = EV(db, S)[-1]
    assert e.description == f"Invoice #{V.id} confirmed — order locked"
    assert e.metadata_json == {"invoice_id": V.id}
    assert e.performed_by == s.U2.id


def test_ss_f_02__only_info_confirmed_400(db, s):
    """SS-F-02 — only order info confirmed: 400, nothing written, extra row gone.
    Rules: F2; TC3."""
    S = so(db, s, "1", order_info_confirmed=True)
    V = inv(db, s, S, linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    before = snap(db, V)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirm order info and items before finalizing"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    assert snap(db, V) == before
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_f_03__only_items_confirmed_400(db, s):
    """SS-F-03 — only items confirmed: 400.
    Rules: F2."""
    S = so(db, s, "1", items_confirmed=True)
    inv(db, s, S, linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirm order info and items before finalizing"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_f_04__no_approval_given_400(db, s):
    """SS-F-04 — no approval given (all approvers required): 400.
    Rules: F3."""
    S = so(db, s, "1", ready=True)
    V = inv(db, s, S, linked=True)
    appr(db, s, S, s.U3)
    cp = commit_point(db)
    before = snap(db, V)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Requires 1 approval(s); 0 so far"
    # Then 3
    assert counts(db) == cp.counts
    # Then 4
    assert snap(db, V) == before


def test_ss_f_05__one_of_two_approvals_400(db, s):
    """SS-F-05 — one of two required approvals: 400.
    Rules: F3."""
    S = so(db, s, "1", ready=True, required_approvals=2)
    inv(db, s, S, linked=True)
    appr(db, s, S, s.U1, approved=True)
    appr(db, s, S, s.U3)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Requires 2 approval(s); 1 so far"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_f_06__two_of_two_approvals_finalized(db, s):
    """SS-F-06 — two of two required approvals: finalized.
    Rules: F3."""
    S = so(db, s, "1", ready=True, required_approvals=2)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    appr(db, s, S, s.U3, approved=True)
    commit_point(db)
    result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert rr(db, AccountInvoice, V.id).invoice_status == "confirmed"
    # Then 3
    assert rr(db, SalesOrder, S.id).invoice_confirmed is True


def test_ss_f_07__already_finalized_409(db, s):
    """SS-F-07 — already finalized: 409.
    Rules: F4."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Invoice is already finalized"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_f_08__no_invoice_draft_made_and_confirmed(db, s):
    """SS-F-08 — no invoice linked: a draft is made and confirmed, with no "draft created" event.
    Rules: F5, F6."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.invoice_id is not None
    assert row.invoice_confirmed is True
    # Then 3
    V = _inv_of(db, S)
    assert V.invoice_status == "confirmed"
    assert V.invoice_amount == D("12000.00")
    # Then 4
    assert "invoice_draft_created" not in types(db, S)
    # Then 5
    assert types(db, S)[-1] == "invoice_confirmed"


def test_ss_f_09__voided_invoice_refusal_passes(db, s):
    """SS-F-09 — a voided invoice still linked: the confirm refusal passes, nothing written.
    Rules: F6."""
    S = so(db, s, "1", ready=True)
    inv(db, s, S, voided_inv=True, linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Voided invoices cannot be confirmed"
    # Then 3
    assert counts(db) == cp.counts
    # Then 4
    assert rr(db, SalesOrder, S.id).invoice_confirmed is False


def test_ss_f_10__invoice_confirmed_earlier_400(db, s):
    """SS-F-10 — an invoice confirmed earlier on the invoice page: 400.
    Rules: F6."""
    S = so(db, s, "1", ready=True)
    inv(db, s, S, confirmed=True, linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Invoice is already confirmed"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_f_11__w2_invoice_404_untouched(db, s):
    """SS-F-11 — a W2 invoice linked: 404, nothing written, the W2 invoice untouched (today and after the fix).
    Rules: F6, F6a; HR-16."""
    S = so(db, s, "1", ready=True)
    V9 = inv(db, s, S, ws="2", linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    before_v, before_s = snap(db, V9), snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert counts(db) == cp.counts
    # Then 3
    assert snap(db, V9) == before_v
    assert snap(db, S) == before_s


@xfail(3192)
def test_ss_f_12__order_read_with_row_lock(db, s):
    """SS-F-12 — the order is read with a row lock.
    Rules: F1 [BUG-3192]; HR-10."""
    S = so(db, s, "1", ready=True)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    sid = S.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.finalize_sales_order_invoice(db, order_id=sid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == sid
    # Then 2
    assert rec.row_lock("sales_orders")


def test_ss_f_13__failing_commit_leaves_draft(db, s):
    """SS-F-13 — a failing commit leaves the invoice a draft.
    Rules: F7; TC4."""
    S = so(db, s, "1", ready=True)
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, AccountInvoice, V.id).invoice_status == "draft"
    # Then 4
    assert rr(db, SalesOrder, S.id).invoice_confirmed is False


@xfail(3197)
def test_ss_f_14__unknown_order_404(db, s):
    """SS-F-14 — an unknown order: 404.
    Rules: F1, G1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


@xfail(3218)
def test_ss_f_15__w2_invoice_refusal_names_no_id(db, s):
    """SS-F-15 — a W2 invoice linked: the refusal names no id of W2.
    Rules: F6a [BUG-3218]; HR-16."""
    S = so(db, s, "1", ready=True)
    V9 = inv(db, s, S, ws="2", linked=True)
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    before_v, before_s = snap(db, V9), snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == FINV404
    # Then 3
    assert str(V9.id) not in exc.value.detail
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    assert snap(db, V9) == before_v
    assert snap(db, S) == before_s


@xfail(3218)
def test_ss_f_16__w0_invoice_same_id_free_refusal(db, s):
    """SS-F-16 — a W0 invoice linked: the same id-free refusal.
    Rules: F6a [BUG-3218]; HR-16."""
    S = so(db, s, "1", ready=True)
    V0 = inv(db, s, S, ws="0", linked=True)
    invl(db, s, V0, 1, "12000.00")
    appr(db, s, S, s.U1, approved=True)
    cp = commit_point(db)
    before = snap(db, V0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == FINV404
    # Then 3
    assert counts(db) == cp.counts
    # Then 4
    assert snap(db, V0) == before
    assert itypes(db, V0) == []


# =========================================================================== #
# SalesService.create_sales_order_from_dict
# =========================================================================== #


def _orders_of(db, ws):
    return rows_where(db, SalesOrder, SalesOrder.workspace_id == ws.id)


def test_ss_c_01__order_created_committed(db, s):
    """SS-C-01 — a new order is created through the manager, committed and returned re-read.
    Rules: C1, C4; TC1, TC2."""
    commit_point(db)
    result = svc.create_sales_order_from_dict(db, order_data=order_data(s, "6000.00"), items_data=[chair_line(s)], workspace_id=s.W1.id, current_user=s.CU)
    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, SalesOrder)
    assert result.id is not None
    rid = result.id
    # Then 3
    db.rollback()
    row = rr(db, SalesOrder, rid)
    assert row.workspace_id == s.W1.id
    assert row.account_id == s.A1.id
    assert row.total_amount == D("6000.00")
    assert row.created_by == s.U2.id
    assert row.invoice_id is None
    # Then 4
    lines = rows_where(db, SalesOrderItem, SalesOrderItem.sales_order_id == rid)
    assert len(lines) == 1
    assert lines[0].item_id == s.I1.id
    assert lines[0].quantity_ordered == D("2.00")
    assert lines[0].line_total == D("6000.00")
    # Then 5
    aps = rows_where(db, SalesOrderApprover, SalesOrderApprover.sales_order_id == rid)
    assert len(aps) == 1
    assert aps[0].user_id == s.U2.id
    # Then 6
    assert "created" in types(db, rid)
    # Then 7
    assert count_where(db, AccountInvoice, AccountInvoice.order_type == "sales_order", AccountInvoice.order_id == rid) == 0
    # Then 8
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 9
    assert notes(db) == []


@xfail(3219)
def test_ss_c_02__no_lines_400(db, s):
    """SS-C-02 — an order with no lines: 400 with the manager's message.
    Rules: C2 [BUG-3219]."""
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_sales_order_from_dict(db, order_data=order_data(s, "0.00"), items_data=[], workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Sales order must have at least one item"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_c_03__no_lines_rolled_back(db, s):
    """SS-C-03 — an order with no lines is refused and rolled back (today and after the fix).
    Rules: C2; TC3."""
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(Exception):
        with spies(db) as (cm, rb):
            svc.create_sales_order_from_dict(db, order_data=order_data(s, "0.00"), items_data=[], workspace_id=s.W1.id, current_user=s.CU)
    # Then 2
    assert X not in db
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_c_04__failing_refresh_order_saved(db, s):
    """SS-C-04 — a failing re-read after the commit leaves the order saved.
    Rules: C1; TC5."""
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_sales_order_from_dict(db, order_data=order_data(s, "6000.00"), items_data=[chair_line(s)], workspace_id=s.W1.id, current_user=s.CU)
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    rows = _orders_of(db, s.W1)
    assert len(rows) == 1
    # Then 3
    assert rows[0].created_by == s.U2.id


def test_ss_c_05__failing_commit_no_order(db, s):
    """SS-C-05 — a failing commit leaves no order.
    Rules: C1; TC4."""
    cp = commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_sales_order_from_dict(db, order_data=order_data(s, "6000.00"), items_data=[chair_line(s)], workspace_id=s.W1.id, current_user=s.CU)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(_orders_of(db, s.W1)) == 0
    # Then 4
    assert counts(db) == cp.counts


def test_ss_c_06__totals_stored_as_given(db, s):
    """SS-C-06 — the service stores line totals and the order total exactly as given.
    Rules: C3 (service part)."""
    commit_point(db)
    result = svc.create_sales_order_from_dict(db, order_data=order_data(s, "0.39"), items_data=[ribbon_line(), ribbon_line(), ribbon_line()], workspace_id=s.W1.id, current_user=s.CU)
    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    db.rollback()
    assert rr(db, SalesOrder, rid).total_amount == D("0.39")
    # Then 3
    lines = rows_where(db, SalesOrderItem, SalesOrderItem.sales_order_id == rid)
    assert len(lines) == 3
    assert all(x.line_total == D("0.13") for x in lines)


# =========================================================================== #
# SalesService.get_sales_order
# =========================================================================== #


def test_ss_g_01__order_with_payment_status_no_commit(db, s):
    """SS-G-01 — returns the order with its invoice's payment status; neither commits nor rolls back.
    Rules: G2, PS2; TC6."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, paid_amount=D("1000.00"), payment_status="partial", linked=True)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_sales_order(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert result.invoice_payment_status == "partial"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_kept(db, X_ID)


def test_ss_g_02__no_invoice_no_status(db, s):
    """SS-G-02 — an order with no invoice has no payment status.
    Rules: G2, PS1."""
    S = so(db, s, "1")
    commit_point(db)
    result = svc.get_sales_order(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert result.invoice_payment_status is None


@xfail(3197)
def test_ss_g_03__w0_order_404(db, s):
    """SS-G-03 — a W0 order (lower workspace id): 404.
    Rules: G1 [BUG-3197]; HR-16."""
    S0 = so(db, s, "0", ws="0")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_sales_order(db, order_id=S0.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S0.id)


@xfail(3197)
def test_ss_g_04__w2_order_404(db, s):
    """SS-G-04 — a W2 order (higher workspace id): 404.
    Rules: G1 [BUG-3197]; HR-16."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_sales_order(db, order_id=S9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S9.id)


@xfail(3197)
def test_ss_g_05__unknown_id_404(db, s):
    """SS-G-05 — an unknown id: 404.
    Rules: G1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_sales_order(db, order_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


def test_ss_g_06__not_found_no_commit_no_rollback(db, s):
    """SS-G-06 — not found neither commits nor rolls back (today and after the fix).
    Rules: G1; TC6."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    X_ID = mk_x(db).id
    # Then 1
    with pytest.raises(Exception):
        with spies(db) as (cm, rb):
            svc.get_sales_order(db, order_id=S9.id, workspace_id=s.W1.id)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


# =========================================================================== #
# SalesService.get_sales_orders
# =========================================================================== #


def test_ss_l_01__workspace_orders_all_of_them(db, s):
    """SS-L-01 — the workspace's orders, all of them; W0 and W2 orders never appear.
    Rules: L1, L2."""
    so(db, s, "0", ws="0")
    Sc = so(db, s, "3", order_date=date(2026, 9, 3))
    Sa = so(db, s, "1", order_date=date(2026, 9, 1))
    Sb = so(db, s, "2", order_date=date(2026, 9, 2))
    so(db, s, "9", ws="2")
    commit_point(db)
    result = svc.get_sales_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    assert idset(result) == {Sc.id, Sa.id, Sb.id}
    # Then 2
    assert all(o.invoice_payment_status is None for o in result)


@xfail(100)
def test_ss_l_02__skip_limit_after_filter(db, s):
    """SS-L-02 — skip and limit are applied after the workspace filter.
    Rules: L1 [BUG-100]."""
    so(db, s, "0", ws="0")
    O = [so(db, s, str(k)) for k in range(1, 6)]
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_sales_orders(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert rec.id_order("sales_orders")
    # Then 2
    assert [o.id for o in result] == [O[1].id, O[2].id]


@xfail(100)
def test_ss_l_03__skip_alone(db, s):
    """SS-L-03 — skip alone is applied.
    Rules: L1 [BUG-100]."""
    O = [so(db, s, str(k)) for k in range(1, 4)]
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_sales_orders(db, workspace_id=s.W1.id, skip=1)
    # Then 1
    assert rec.id_order("sales_orders")
    # Then 2
    assert [o.id for o in result] == [O[1].id, O[2].id]


def test_ss_l_04__default_limit_100(db, s):
    """SS-L-04 — no limit given: at most 100.
    Rules: L1."""
    for k in range(1, 102):
        so(db, s, str(k))
    commit_point(db)
    result = svc.get_sales_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert all(o.workspace_id == s.W1.id for o in result)


def test_ss_l_05__limit_1000_passed_on(db, s):
    """SS-L-05 — limit=1000 is passed on.
    Rules: L1."""
    for k in range(1, 102):
        so(db, s, str(k))
    commit_point(db)
    result = svc.get_sales_orders(db, workspace_id=s.W1.id, limit=1000)
    # Then 1
    assert len(result) == 101


def test_ss_l_06__one_invoice_query_no_commit(db, s):
    """SS-L-06 — payment statuses for the page come from one invoice query; neither commits nor rolls back.
    Rules: L2, PS2; TC6."""
    Sa = so(db, s, "1")
    inv(db, s, Sa, confirmed=True, linked=True)
    Sb = so(db, s, "2")
    inv(db, s, Sb, confirmed=True, paid_amount=D("12000.00"), payment_status="paid", linked=True)
    Sc = so(db, s, "3")
    commit_point(db)
    ids = (Sa.id, Sb.id, Sc.id)
    X_ID = mk_x(db).id
    expunge_all(db, s)
    with Recorder(db) as rec:
        with spies(db) as (cm, rb):
            result = svc.get_sales_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert {o.id: o.invoice_payment_status for o in result} == {ids[0]: "unpaid", ids[1]: "paid", ids[2]: None}
    # Then 2
    assert rec.count_from("account_invoices") == 1
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x_kept(db, X_ID)


@xfail(100)
def test_ss_l_07__orders_in_id_order(db, s):
    """SS-L-07 — the workspace's orders come back in id order.
    Rules: L1 [BUG-100]."""
    Sc = so(db, s, "3", order_date=date(2026, 9, 3))
    Sa = so(db, s, "1", order_date=date(2026, 9, 1))
    Sb = so(db, s, "2", order_date=date(2026, 9, 2))
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_sales_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert rec.id_order("sales_orders")
    # Then 2
    assert [o.id for o in result] == [Sc.id, Sa.id, Sb.id]


def test_ss_l_08__skip_limit_page_of_two(db, s):
    """SS-L-08 — skip and limit give a page of two orders of this workspace (today and after the fix).
    Rules: L1 (holds before and after BUG-100)."""
    so(db, s, "0", ws="0")
    O = [so(db, s, str(k)) for k in range(1, 6)]
    commit_point(db)
    result = svc.get_sales_orders(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) <= {o.id for o in O}


def test_ss_l_09__skip_alone_drops_one(db, s):
    """SS-L-09 — skip alone drops one order (today and after the fix).
    Rules: L1 (holds before and after BUG-100)."""
    O = [so(db, s, str(k)) for k in range(1, 4)]
    commit_point(db)
    result = svc.get_sales_orders(db, workspace_id=s.W1.id, skip=1)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) <= {o.id for o in O}


# =========================================================================== #
# SalesService._attach_invoice_payment_status
# =========================================================================== #


def test_ss_ps_01__empty_list_no_query(db, s):
    """SS-PS-01 — an empty list: no query.
    Rules: PS1."""
    commit_point(db)
    with Recorder(db) as rec:
        svc._attach_invoice_payment_status(db, orders=[])
    # Then 1
    assert rec.count_from("account_invoices") == 0


def test_ss_ps_02__no_invoices_none_no_query(db, s):
    """SS-PS-02 — orders without invoices get None and no query is sent.
    Rules: PS1."""
    Sa = so(db, s, "1")
    Sb = so(db, s, "2")
    commit_point(db)
    with Recorder(db) as rec:
        svc._attach_invoice_payment_status(db, orders=[Sa, Sb])
    # Then 1
    assert Sa.invoice_payment_status is None
    # Then 2
    assert Sb.invoice_payment_status is None
    # Then 3
    assert rec.count_from("account_invoices") == 0


def test_ss_ps_03__each_order_own_status(db, s):
    """SS-PS-03 — each order gets its own invoice's status; nothing is written.
    Rules: PS2, PS4."""
    Sa = so(db, s, "1")
    inv(db, s, Sa, confirmed=True, linked=True)
    Sb = so(db, s, "2")
    inv(db, s, Sb, confirmed=True, payment_status="overdue", linked=True)
    Sc = so(db, s, "3")
    commit_point(db)
    svc._attach_invoice_payment_status(db, orders=[Sa, Sb, Sc])
    # Then 1
    assert Sa.invoice_payment_status == "unpaid"
    # Then 2
    assert Sb.invoice_payment_status == "overdue"
    # Then 3
    assert Sc.invoice_payment_status is None
    # Then 4
    assert_session_clean(db)


@xfail(3194)
def test_ss_ps_04__w2_invoice_gives_none(db, s):
    """SS-PS-04 — a W2 invoice linked to a W1 order gives None.
    Rules: PS2 [BUG-3194]; HR-16."""
    Sa = so(db, s, "1")
    inv(db, s, Sa, confirmed=True, linked=True)
    Sb = so(db, s, "2")
    inv(db, s, Sb, ws="2", confirmed=True, payment_status="paid", linked=True)
    commit_point(db)
    svc._attach_invoice_payment_status(db, orders=[Sa, Sb])
    # Then 1
    assert Sa.invoice_payment_status == "unpaid"
    # Then 2
    assert Sb.invoice_payment_status is None


@xfail(3194)
def test_ss_ps_05__w0_invoice_gives_none(db, s):
    """SS-PS-05 — a W0 invoice linked to a W1 order gives None.
    Rules: PS2 [BUG-3194]; HR-16."""
    Sb = so(db, s, "2")
    inv(db, s, Sb, ws="0", confirmed=True, payment_status="partial", linked=True)
    commit_point(db)
    svc._attach_invoice_payment_status(db, orders=[Sb])
    # Then 1
    assert Sb.invoice_payment_status is None


def test_ss_ps_06__missing_invoice_row_none(db, s):
    """SS-PS-06 — an invoice id with no invoice row gives None.
    Rules: PS3."""
    Sa = so(db, s, "1")
    commit_point(db)
    Sa.invoice_id = MISSING
    svc._attach_invoice_payment_status(db, orders=[Sa])
    # Then 1
    assert Sa.invoice_payment_status is None


def test_ss_ps_07__returns_none(db, s):
    """SS-PS-07 — the helper returns None; the result is only the attribute.
    Rules: PS5."""
    Sa = so(db, s, "1")
    inv(db, s, Sa, confirmed=True, linked=True)
    commit_point(db)
    result = svc._attach_invoice_payment_status(db, orders=[Sa])
    # Then 1
    assert result is None
    # Then 2
    assert Sa.invoice_payment_status == "unpaid"


# =========================================================================== #
# SalesService.update_sales_order
# =========================================================================== #


def _appr_row(db, aid):
    return rr(db, SalesOrderApprover, aid)


def test_ss_u_01__edit_committed_omitted_unchanged(db, s):
    """SS-U-01 — an edit is committed and the order returned re-read; omitted fields unchanged.
    Rules: U1, U5, U10; TC1, TC2."""
    S = so(db, s, "1")
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == S.id
    # Then 3
    db.rollback()
    assert rr(db, SalesOrder, S.id).contact_phone == "01700000000"
    # Then 4
    row = rr(db, SalesOrder, S.id)
    assert row.contact_name == "Rahim"
    assert row.description is None
    # Then 5
    assert notes(db) == []


@xfail(3200)
def test_ss_u_02__real_change_stamps_updated_by(db, s):
    """SS-U-02 — a real change stamps `updated_by`.
    Rules: U8 [BUG-3200]; HR-9."""
    S = so(db, s, "1")
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).contact_phone == "01700000000"
    # Then 2
    assert rr(db, SalesOrder, S.id).updated_by == s.U2.id


@xfail(3215)
def test_ss_u_03__real_change_logs_order_updated(db, s):
    """SS-U-03 — a real change logs one `order_updated` event.
    Rules: U9 [BUG-3215]."""
    S = so(db, s, "1")
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert types(db, S) == ["order_updated"]
    # Then 3
    e = EV(db, S)[0]
    assert e.description == "Order updated (contact phone)"
    assert e.metadata_json == {"fields": ["contact_phone"]}
    assert e.performed_by == s.U2.id


@xfail(3215)
def test_ss_u_04__several_fields_labels_in_fixed_order(db, s):
    """SS-U-04 — several fields: labels in the fixed order.
    Rules: U9 [BUG-3215]."""
    S = so(db, s, "1")
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(description="Blue chairs", contact_name="Karim", expected_delivery_date=date(2026, 10, 1), required_approvals=2), user_id=s.U2.id)
    # Then 1
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.description == "Blue chairs"
    assert row.contact_name == "Karim"
    assert row.expected_delivery_date == date(2026, 10, 1)
    assert row.required_approvals == 2
    # Then 2
    assert types(db, S) == ["order_updated"]
    # Then 3
    assert EV(db, S)[0].description == "Order updated (expected delivery date, contact name, description, required approvals)"
    # Then 4
    assert EV(db, S)[0].metadata_json == {"fields": ["expected_delivery_date", "contact_name", "description", "required_approvals"]}


def test_ss_u_05__stored_values_no_change(db, s):
    """SS-U-05 — sending the stored values changes nothing: no event, no stamp.
    Rules: U8, U9; HR-9."""
    S = so(db, s, "1", required_approvals=2)
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_name="Rahim", required_approvals=2), user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.updated_by is None
    assert row.contact_name == "Rahim"
    assert row.required_approvals == 2
    # Then 3
    assert len(EV(db, S)) == 0


@xfail(3199)
def test_ss_u_06__required_approvals_null_clears(db, s):
    """SS-U-06 — `required_approvals` sent as null clears it.
    Rules: U5 [BUG-3199]."""
    S = so(db, s, "1", required_approvals=2)
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=None), user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert rr(db, SalesOrder, S.id).required_approvals is None


@xfail(3199)
def test_ss_u_07__contact_phone_null_clears(db, s):
    """SS-U-07 — `contact_phone` sent as null clears it.
    Rules: U5 [BUG-3199]."""
    S = so(db, s, "1", contact_phone="017")
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone=None), user_id=s.U2.id)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).contact_name == "Rahim"
    # Then 2
    assert rr(db, SalesOrder, S.id).contact_phone is None


@xfail(3207)
def test_ss_u_08__completed_order_not_editable(db, s):
    """SS-U-08 — a completed order cannot be edited.
    Rules: U2 [BUG-3207]; TC3."""
    S = so(db, s, "1", completed=True)
    cp = commit_point(db)
    before = snap(db, S)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot edit — order is complete"
    # Then 3
    assert X not in db
    # Then 4
    assert counts(db) == cp.counts
    # Then 5
    assert snap(db, S) == before
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3207)
def test_ss_u_09__locked_order_not_editable(db, s):
    """SS-U-09 — a financially locked order cannot be edited.
    Rules: U2 [BUG-3207]."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    commit_point(db)
    before = snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=5), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot edit — invoice is locked"
    # Then 3
    assert snap(db, S) == before


@xfail(3207)
def test_ss_u_10__completed_and_locked_completion_wins(db, s):
    """SS-U-10 — completed and locked: the completion message wins.
    Rules: U2 [BUG-3207]."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot edit — order is complete"


@xfail(3207)
def test_ss_u_11__return_in_progress_not_editable(db, s):
    """SS-U-11 — "return in progress" (completed with a pending return) cannot be edited.
    Rules: U2 [BUG-3207]; RP5."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    before = snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(description="x"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot edit — order is complete"
    # Then 3
    assert snap(db, S) == before


@xfail(3208)
def test_ss_u_12__confirmed_info_contact_name_refused(db, s):
    """SS-U-12 — confirmed order info: changing the contact name is refused.
    Rules: U3 [BUG-3208]."""
    S = so(db, s, "1", order_info_confirmed=True)
    commit_point(db)
    before = snap(db, S)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_name="Karim"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == INFOLOCK
    # Then 3
    assert X not in db
    # Then 4
    assert snap(db, S) == before
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3208)
def test_ss_u_13__confirmed_info_phone_refused(db, s):
    """SS-U-13 — confirmed order info: changing the phone is refused.
    Rules: U3 [BUG-3208]."""
    S = so(db, s, "1", order_info_confirmed=True, contact_phone="017")
    commit_point(db)
    before = snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="018"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == INFOLOCK
    # Then 3
    assert snap(db, S) == before


@xfail(3208)
def test_ss_u_14__confirmed_info_delivery_date_refused(db, s):
    """SS-U-14 — confirmed order info: changing the expected delivery date is refused.
    Rules: U3 [BUG-3208]."""
    S = so(db, s, "1", order_info_confirmed=True, expected_delivery_date=date(2026, 10, 1))
    commit_point(db)
    before = snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(expected_delivery_date=date(2026, 10, 2)), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == INFOLOCK
    # Then 3
    assert snap(db, S) == before


@xfail(3208)
def test_ss_u_15__confirmed_info_description_refused(db, s):
    """SS-U-15 — confirmed order info: changing the description is refused.
    Rules: U3 [BUG-3208]."""
    S = so(db, s, "1", order_info_confirmed=True, description="Blue")
    commit_point(db)
    before = snap(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(description="Red"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == INFOLOCK
    # Then 3
    assert snap(db, S) == before


def test_ss_u_16__confirmed_info_same_name_not_a_change(db, s):
    """SS-U-16 — confirmed order info: sending the stored contact name is not a change.
    Rules: U3."""
    S = so(db, s, "1", order_info_confirmed=True)
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_name="Rahim"), user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.contact_name == "Rahim"
    assert row.order_info_confirmed is True


def test_ss_u_17__confirmed_info_required_approvals_allowed(db, s):
    """SS-U-17 — confirmed order info does not block the required approvals.
    Rules: U3, U5."""
    S = so(db, s, "1", order_info_confirmed=True)
    commit_point(db)
    result = svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=3), user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.required_approvals == 3
    assert row.order_info_confirmed is True


@pytest.mark.parametrize(
    "field",
    [
        pytest.param({"total_amount": D("1")}, id="SS-U-18", marks=xfail(2404)),
        pytest.param({"is_fully_delivered": True}, id="SS-U-19", marks=xfail(2404)),
        pytest.param({"is_invoiced": True}, id="SS-U-20", marks=xfail(2404)),
        pytest.param({"invoice_id": 1}, id="SS-U-21", marks=xfail(1019)),
    ],
)
def test_ss_u_18_21__system_fields_refused_by_schema(field):
    """SS-U-18 … SS-U-21 — `total_amount`, `is_fully_delivered`, `is_invoiced`, `invoice_id` are not accepted.
    Rules: U4 [BUG-2404, BUG-1019]."""
    # Then 1
    with pytest.raises(ValidationError):
        SalesOrderUpdate(**field)


@xfail(3201)
def test_ss_u_22__changed_required_approvals_clears_approvals(db, s):
    """SS-U-22 — changing the required approvals clears the approvals given.
    Rules: U7 [BUG-3201]."""
    S = so(db, s, "1", required_approvals=2)
    A_1 = appr(db, s, S, s.U1, approved=True)
    A_3 = appr(db, s, S, s.U3, approved=True)
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=1), user_id=s.U2.id)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).required_approvals == 1
    # Then 2
    assert _appr_row(db, A_1.id).approved is False
    # Then 3
    assert _appr_row(db, A_3.id).approved is False
    # Then 4
    assert types(db, S).count("approvals_reset") == 1


@xfail(3201)
def test_ss_u_23__null_to_number_clears_approvals(db, s):
    """SS-U-23 — a change from null to a number also clears the approvals.
    Rules: U7 [BUG-3201]."""
    S = so(db, s, "1")
    A_1 = appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=2), user_id=s.U2.id)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).required_approvals == 2
    # Then 2
    assert _appr_row(db, A_1.id).approved is False


def test_ss_u_24__same_required_approvals_keeps_approvals(db, s):
    """SS-U-24 — sending the stored required approvals keeps the approvals.
    Rules: U7."""
    S = so(db, s, "1", required_approvals=2)
    A_1 = appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=2), user_id=s.U2.id)
    # Then 1
    db.rollback()
    a = _appr_row(db, A_1.id)
    assert a.approved is True
    assert a.approved_at == T1
    # Then 2
    assert "approvals_reset" not in types(db, S)


@xfail(3215)
def test_ss_u_25__reset_event_before_edit_event(db, s):
    """SS-U-25 — the reset event comes before the edit event.
    Rules: U7, U9 [BUG-3215]."""
    S = so(db, s, "1", required_approvals=2)
    appr(db, s, S, s.U1, approved=True)
    commit_point(db)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(required_approvals=1), user_id=s.U2.id)
    # Then 1
    assert types(db, S) == ["approvals_reset", "order_updated"]
    # Then 2
    assert EV(db, S)[1].description == "Order updated (required approvals)"


@xfail(3197)
def test_ss_u_26__unknown_order_404(db, s):
    """SS-U-26 — an unknown order: 404.
    Rules: U1, G1 [BUG-3197]."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, S9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_sales_order(db, order_id=S9.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="1"), user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S9.id)
    # Then 3
    assert snap(db, S9) == before


def test_ss_u_27__other_workspace_rolled_back(db, s):
    """SS-U-27 — another workspace's order is refused and rolled back (today and after the fix).
    Rules: U1, G1; TC3; HR-16."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, S9)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(Exception):
        with spies(db) as (cm, rb):
            svc.update_sales_order(db, order_id=S9.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="1"), user_id=s.U2.id)
    # Then 2
    assert X not in db
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert snap(db, S9) == before
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_u_28__failing_commit_order_unchanged(db, s):
    """SS-U-28 — a failing commit leaves the order as it was.
    Rules: U5; TC4."""
    S = so(db, s, "1")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrder, S.id).contact_phone is None


def test_ss_u_29__no_invoice_step_draft_keeps_notes(db, s):
    """SS-U-29 — no invoice step: a linked draft keeps its notes.
    Rules: U10."""
    S = so(db, s, "1", items_confirmed=True, description="Blue")
    V = inv(db, s, S, notes="Blue", linked=True)
    commit_point(db)
    before = snap(db, V)
    svc.update_sales_order(db, order_id=S.id, workspace_id=s.W1.id, order_update=SalesOrderUpdate(description="Red"), user_id=s.U2.id)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).description == "Red"
    # Then 2
    assert snap(db, V) == before
    # Then 3
    assert notes(db) == []


# =========================================================================== #
# SalesService.create_delivery
# =========================================================================== #


def _deliveries_of(db, S):
    return rows_where(db, SalesDelivery, SalesDelivery.sales_order_id == S.id)


def test_ss_dc_01__delivery_planned_committed(db, s):
    """SS-DC-01 — a delivery is planned, committed, and both rows returned re-read.
    Rules: DC1; TC1, TC2; N5."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = svc.create_delivery(db, delivery_in=dcreate(s, S), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": D("2")}], workspace_id=s.W1.id, current_user=s.CU)
    delivery, order = result
    # Then 1
    assert loaded(delivery)
    # Then 2
    assert loaded(order)
    # Then 3
    assert order.id == S.id
    assert delivery.sales_order_id == S.id
    did = delivery.id
    # Then 4
    db.rollback()
    d = rr(db, SalesDelivery, did)
    assert d.delivery_status == "planned"
    assert d.created_by == s.U2.id
    assert d.workspace_id == s.W1.id
    # Then 5
    lines = rows_where(db, SalesDeliveryItem, SalesDeliveryItem.delivery_id == did)
    assert len(lines) == 1
    assert lines[0].sales_order_item_id == L1.id
    assert lines[0].quantity_delivered == D("2.00")
    # Then 6
    assert "delivery_planned" in types(db, S)
    # Then 7
    assert notes(db) == []


def test_ss_dc_02__value_error_becomes_400(db, s):
    """SS-DC-02 — the manager's `ValueError` becomes a 400 after the rollback.
    Rules: DC2; TC3 (departure)."""
    S = so(db, s, "1", ready=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.create_delivery(db, delivery_in=dcreate(s, S), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": D("2")}], workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Finalize the invoice before planning a delivery"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_dc_03__no_lines_400(db, s):
    """SS-DC-03 — no delivery lines: 400 with the manager's message.
    Rules: DC2."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_delivery(db, delivery_in=dcreate(s, S), delivery_items_data=[], workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Delivery must have at least one item"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_dc_04__completed_order_gap_delivery_stays_completed(db, s):
    """SS-DC-04 — a completed order with a replacement gap can get a delivery; it stays completed.
    Rules: DC3."""
    S = so(db, s, "1", finalized=True, completed=True)
    V = inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    commit_point(db)
    result = svc.create_delivery(db, delivery_in=dcreate(s, S), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": D("1")}], workspace_id=s.W1.id, current_user=s.CU)
    delivery, order = result
    did = delivery.id
    # Then 1
    assert order.id == S.id
    # Then 2
    db.rollback()
    assert rr(db, SalesDelivery, did).delivery_status == "planned"
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.order_completed is True
    assert row.completed_at == T0
    # Then 4
    assert rr(db, AccountInvoice, V.id).invoice_status == "confirmed"


def test_ss_dc_05__failing_commit_no_delivery(db, s):
    """SS-DC-05 — a failing commit leaves no delivery.
    Rules: DC1; TC4."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_delivery(db, delivery_in=dcreate(s, S), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": D("2")}], workspace_id=s.W1.id, current_user=s.CU)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(_deliveries_of(db, S)) == 0


# =========================================================================== #
# SalesService.complete_delivery
# =========================================================================== #


def _delivery_order(db, s, *, l1=None):
    """finalized S, confirmed linked V, L1 = ln(S) with overrides l1."""
    S = so(db, s, "1", finalized=True)
    V = inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, **(l1 or {"quantity_delivered": D("0.00")}))
    return S, V, L1


def test_ss_dv_01__delivery_completed_stock_out_messages(db, s):
    """SS-DV-01 — a delivery is completed, stock goes out, messages in order; committed.
    Rules: DV2, DV3, DV4, DV5, DV6; TC1, TC2; N5."""
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    cp = commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert loaded(order)
    # Then 2
    assert order.id == S.id
    # Then 3
    assert mts(msgs) == [
        MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed"),
        MSG("info", "Inventory updated: 1 items, 4.00 units deducted"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
    ]
    # Then 4
    assert msgs[1].details["item_count"] == 1
    assert D(str(msgs[1].details["total_quantity"])) == D("4.00")
    # Then 5
    db.rollback()
    assert rr(db, SalesDelivery, D1.id).delivery_status == "delivered"
    # Then 6
    assert rr(db, SalesOrderItem, L1.id).quantity_delivered == D("4.00")
    assert rr(db, SalesOrder, S.id).is_fully_delivered is True
    # Then 7
    assert rr(db, Product, s.P1.id).qty == 96
    # Then 8
    led = NEWLED(db, cp)
    assert len(led) == 1
    assert led[0].transaction_type == "sale"
    assert led[0].quantity == 4
    assert led[0].source_type == "sales_delivery"
    assert led[0].source_id == D1.id
    # Then 9
    assert notes(db) == []


def test_ss_dv_02__partial_delivery_reports_remaining(db, s):
    """SS-DV-02 — a partial delivery reports what remains.
    Rules: DV4."""
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    assert mt(msgs[2]) == MSG("info", "3.00 units remaining to be delivered")
    # Then 3
    assert len(msgs) == 3
    # Then 4
    db.rollback()
    assert rr(db, SalesOrder, S.id).is_fully_delivered is False


@xfail(3206)
def test_ss_dv_03__refunded_units_not_remaining(db, s):
    """SS-DV-03 — refunded units are not "remaining".
    Rules: DV4 [BUG-3206]."""
    S, V, L1 = _delivery_order(db, s, l1={"quantity_ordered": D("10.00"), "quantity_delivered": D("6.00"), "quantity_refunded": D("2.00"), "quantity_returned": D("2.00"), "line_total": D("30000.00")})
    ln(db, s, S, free="Crate", quantity_ordered=D("5.00"), quantity_delivered=D("2.00"), unit_price=D("100.00"), line_total=D("500.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "2.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    assert mt(msgs[2]) == MSG("info", "3.00 units remaining to be delivered")


@xfail(3206)
def test_ss_dv_04__over_delivered_line_floors_at_zero(db, s):
    """SS-DV-04 — an over-delivered line does not lower the remaining count.
    Rules: DV4 [BUG-3206]."""
    S, V, L1 = _delivery_order(db, s, l1={"quantity_delivered": D("6.00")})
    L2 = ln(db, s, S, free="Crate", quantity_ordered=D("5.00"), quantity_delivered=D("0.00"), unit_price=D("100.00"), line_total=D("500.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L2, "2.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    assert mt(msgs[2]) == MSG("info", "3.00 units remaining to be delivered")


@xfail(3216)
def test_ss_dv_05__units_deducted_counts_catalog_only(db, s):
    """SS-DV-05 — "units deducted" counts only catalog lines.
    Rules: DV3 [BUG-3216]."""
    S, V, L1 = _delivery_order(db, s)
    L2 = ln(db, s, S, free="Crate", quantity_ordered=D("1.00"), quantity_delivered=D("0.00"), unit_price=D("100.00"), line_total=D("100.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    dl(db, D1, L2, "1.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mt(msgs[0]) == MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed")
    # Then 2
    assert mt(msgs[1]) == MSG("info", "Inventory updated: 1 items, 4.00 units deducted")
    # Then 3
    assert msgs[1].details["item_count"] == 1
    assert D(str(msgs[1].details["total_quantity"])) == D("4.00")


@xfail(3216)
def test_ss_dv_06__only_free_text_no_inventory_movement(db, s):
    """SS-DV-06 — only free-text lines: "No inventory movement".
    Rules: DV3 [BUG-3216]."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    L2 = ln(db, s, S, free="Crate", quantity_ordered=D("1.00"), quantity_delivered=D("0.00"), unit_price=D("100.00"), line_total=D("100.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L2, "1.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mt(msgs[0]) == MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed")
    # Then 2
    assert mt(msgs[1]) == MSG("info", "No inventory movement")
    # Then 3
    assert msgs[1].details == {"item_count": 0, "total_quantity": 0}


def test_ss_dv_07__two_catalog_lines_counted(db, s):
    """SS-DV-07 — two catalog lines: counted and summed (today and after the fix).
    Rules: DV3."""
    S, V, L1 = _delivery_order(db, s)
    L2 = ln(db, s, S, quantity_ordered=D("1.00"), quantity_delivered=D("0.00"), line_total=D("3000.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    dl(db, D1, L2, "1.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mt(msgs[1]) == MSG("info", "Inventory updated: 2 items, 5.00 units deducted")
    # Then 2
    db.rollback()
    assert rr(db, Product, s.P1.id).qty == 95


def test_ss_dv_08__unknown_delivery_404(db, s):
    """SS-DV-08 — an unknown delivery: 404, nothing written, extra row gone.
    Rules: DV1; TC3."""
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.complete_delivery(db, delivery_id=MISSING, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(MISSING)
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_dv_09__w0_delivery_404(db, s):
    """SS-DV-09 — a W0 delivery: 404, not completed.
    Rules: DV1; HR-16."""
    S0 = so(db, s, "0", ws="0")
    L0 = ln(db, s, S0, quantity_delivered=D("0.00"))
    D0 = dlv(db, s, S0, "0")
    dl(db, D0, L0, "1.00")
    commit_point(db)
    before = snap(db, D0)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.complete_delivery(db, delivery_id=D0.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(D0.id)
    # Then 3
    assert snap(db, D0) == before


def test_ss_dv_10__w2_delivery_404(db, s):
    """SS-DV-10 — a W2 delivery: 404, not completed.
    Rules: DV1; HR-16."""
    S9 = so(db, s, "9", ws="2")
    L9 = ln(db, s, S9, quantity_delivered=D("0.00"))
    D9 = dlv(db, s, S9, "9")
    dl(db, D9, L9, "1.00")
    commit_point(db)
    before = snap(db, D9)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.complete_delivery(db, delivery_id=D9.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(D9.id)
    # Then 3
    assert snap(db, D9) == before


@xfail(3198)
def test_ss_dv_11__value_error_becomes_400(db, s):
    """SS-DV-11 — the manager's `ValueError` becomes a 400.
    Rules: DV2 [BUG-3198]."""
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "0.00")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Sale deduction quantity must be positive"


def test_ss_dv_12__manager_refusal_rolled_back(db, s):
    """SS-DV-12 — a manager refusal is rolled back (today and after the fix).
    Rules: DV2; TC3."""
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "0.00")
    commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(Exception):
        svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    # Then 2
    assert X not in db
    # Then 3
    assert rr(db, SalesDelivery, D1.id).delivery_status == "planned"
    # Then 4
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_dv_13__insufficient_stock_422_passes(db, s):
    """SS-DV-13 — insufficient stock: the 422 passes unchanged.
    Rules: DV2."""
    s.P1.qty = 2
    db.flush()
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 422
    # Then 2
    assert re.fullmatch(rf"Insufficient sellable stock for item {s.I1.id} at factory {s.F1.id}: requested 4(\.0+)?, available 2(\.0+)?", exc.value.detail) is not None
    # Then 3
    assert rr(db, SalesDelivery, D1.id).delivery_status == "planned"
    # Then 4
    assert counts(db) == cp.counts


def test_ss_dv_14__replacement_delivery_order_stays_completed(db, s):
    """SS-DV-14 — a replacement delivery on a completed order completes; the order stays completed.
    Rules: DV6; FU-2."""
    S = so(db, s, "1", finalized=True, completed=True)
    V = inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    db.rollback()
    assert rr(db, SalesDelivery, D1.id).delivery_status == "delivered"
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.order_completed is True
    assert row.completed_at == T0
    assert row.completed_by == s.U1.id
    # Then 4
    v = rr(db, AccountInvoice, V.id)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == D("12000.00")


def test_ss_dv_15__failing_commit_delivery_planned(db, s):
    """SS-DV-15 — a failing commit leaves the delivery planned and the stock untouched.
    Rules: DV5; TC4."""
    S, V, L1 = _delivery_order(db, s)
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "4.00")
    cp = commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesDelivery, D1.id).delivery_status == "planned"
    # Then 4
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 5
    assert NEWLED(db, cp) == []


# =========================================================================== #
# SalesService.cancel_delivery
# =========================================================================== #


def test_ss_dx_01__planned_delivery_cancelled(db, s):
    """SS-DX-01 — a planned delivery is cancelled, committed and returned re-read.
    Rules: DX2; TC1, TC2."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    result = svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == D1.id
    # Then 3
    db.rollback()
    assert rr(db, SalesDelivery, D1.id).delivery_status == "cancelled"


def test_ss_dx_02__unknown_delivery_404(db, s):
    """SS-DX-02 — an unknown delivery: 404.
    Rules: DX1."""
    commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.cancel_delivery(db, delivery_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(MISSING)
    # Then 3
    assert X not in db
    # Then 4
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_dx_03__w2_delivery_404(db, s):
    """SS-DX-03 — a W2 delivery: 404, not cancelled.
    Rules: DX1; HR-16."""
    S9 = so(db, s, "9", ws="2")
    D9 = dlv(db, s, S9, "9")
    commit_point(db)
    before = snap(db, D9)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.cancel_delivery(db, delivery_id=D9.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert snap(db, D9) == before


def test_ss_dx_04__delivered_refusal_400(db, s):
    """SS-DX-04 — a delivered delivery: the manager's refusal becomes a 400, rolled back.
    Rules: DX2; TC3 (departure)."""
    S = so(db, s, "1", finalized=True)
    D1 = dlv(db, s, S, "1", delivered=True)
    commit_point(db)
    before = snap(db, D1)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only planned deliveries can be cancelled (this delivery is 'delivered')"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, D1) == before
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_dx_05__failing_commit_stays_planned(db, s):
    """SS-DX-05 — a failing commit leaves the delivery planned.
    Rules: DX2; TC4."""
    S = so(db, s, "1", finalized=True)
    D1 = dlv(db, s, S, "1")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesDelivery, D1.id).delivery_status == "planned"


# =========================================================================== #
# SalesService.update_delivery
# =========================================================================== #


def test_ss_du_01__planned_delivery_edited(db, s):
    """SS-DU-01 — a planned delivery is edited, committed and returned re-read.
    Rules: DU2; TC1, TC2."""
    S = so(db, s, "1", finalized=True)
    D1 = dlv(db, s, S, "1", tracking_number="TRK-100")
    commit_point(db)
    result = svc.update_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == D1.id
    # Then 3
    db.rollback()
    assert rr(db, SalesDelivery, D1.id).tracking_number == "TRK-200"


def test_ss_du_02__unknown_delivery_404(db, s):
    """SS-DU-02 — an unknown delivery: 404.
    Rules: DU1."""
    commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_delivery(db, delivery_id=MISSING, workspace_id=s.W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(MISSING)
    # Then 3
    assert X not in db
    # Then 4
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_du_03__w0_delivery_404(db, s):
    """SS-DU-03 — a W0 delivery: 404, not edited.
    Rules: DU1; HR-16."""
    S0 = so(db, s, "0", ws="0")
    D0 = dlv(db, s, S0, "0", tracking_number="TRK-100")
    commit_point(db)
    before = snap(db, D0)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_delivery(db, delivery_id=D0.id, workspace_id=s.W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert snap(db, D0) == before


def test_ss_du_04__delivered_refusal_400(db, s):
    """SS-DU-04 — a delivered delivery: the manager's refusal becomes a 400, rolled back.
    Rules: DU2; TC3 (departure)."""
    S = so(db, s, "1", finalized=True)
    D1 = dlv(db, s, S, "1", delivered=True, tracking_number="TRK-100")
    commit_point(db)
    before = snap(db, D1)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.update_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only planned deliveries can be edited (this delivery is 'delivered')"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, D1) == before
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_du_05__failing_commit_old_tracking(db, s):
    """SS-DU-05 — a failing commit leaves the old tracking number.
    Rules: DU2; TC4."""
    S = so(db, s, "1", finalized=True)
    D1 = dlv(db, s, S, "1", tracking_number="TRK-100")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesDelivery, D1.id).tracking_number == "TRK-100"


# =========================================================================== #
# SalesService.fulfill_service_item
# =========================================================================== #


def _service_line(db, s, S, **but):
    return ln(db, s, S, service=True, **{"quantity_ordered": D("2.00"), "quantity_delivered": D("0.00"), "unit_price": D("500.00"), "line_total": D("1000.00"), **but})


def test_ss_fs_01__service_line_fulfilled(db, s):
    """SS-FS-01 — a service line is fulfilled; messages; committed; no stock.
    Rules: FS4, FS6, FS7; TC1, TC2; N5."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    LS = _service_line(db, s, S)
    cp = commit_point(db)
    result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert loaded(order)
    # Then 2
    assert order.id == S.id
    # Then 3
    assert mts(msgs) == [
        MSG("success", "Line item marked as fulfilled"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
    ]
    # Then 4
    db.rollback()
    assert rr(db, SalesOrderItem, LS.id).quantity_delivered == D("2.00")
    # Then 5
    assert len(_deliveries_of(db, S)) == 0
    # Then 6
    assert NEWLED(db, cp) == []
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 7
    assert notes(db) == []


def test_ss_fs_02__not_last_open_line_one_message(db, s):
    """SS-FS-02 — not the last open line: only the first message.
    Rules: FS7."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    LS = _service_line(db, s, S)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mts(msgs) == [MSG("success", "Line item marked as fulfilled")]
    # Then 2
    db.rollback()
    assert rr(db, SalesOrder, S.id).is_fully_delivered is False


def test_ss_fs_03__w2_line_404(db, s):
    """SS-FS-03 — a line of W2: 404.
    Rules: FS1; HR-16."""
    S = so(db, s, "1", finalized=True)
    S9 = so(db, s, "9", ws="2")
    L9 = ln(db, s, S9, service=True, quantity_delivered=D("0.00"))
    commit_point(db)
    before = snap(db, L9)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with spies(db) as (cm, rb):
            svc.fulfill_service_item(db, order_id=S.id, order_item_id=L9.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Sales order item {L9.id} not found"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, L9) == before
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_fs_04__w0_line_404(db, s):
    """SS-FS-04 — a line of W0: 404.
    Rules: FS1; HR-16."""
    S0 = so(db, s, "0", ws="0")
    L0 = ln(db, s, S0, service=True, quantity_delivered=D("0.00"))
    S = so(db, s, "1", finalized=True)
    commit_point(db)
    before = snap(db, L0)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.fulfill_service_item(db, order_id=S.id, order_item_id=L0.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Sales order item {L0.id} not found"
    # Then 3
    assert snap(db, L0) == before


def test_ss_fs_05__line_of_other_order_400(db, s):
    """SS-FS-05 — a line of another W1 order: 400, checked before "requires delivery".
    Rules: FS2, FS3."""
    S = so(db, s, "1", finalized=True)
    S2 = so(db, s, "2", finalized=True)
    L2 = ln(db, s, S2, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.fulfill_service_item(db, order_id=S.id, order_item_id=L2.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Sales order item {L2.id} does not belong to sales order {S.id}"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_fs_06__requires_delivery_422(db, s):
    """SS-FS-06 — a line that requires delivery: 422, checked before the invoice.
    Rules: FS3, FS5."""
    S = so(db, s, "1")
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.fulfill_service_item(db, order_id=S.id, order_item_id=L1.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "This line requires delivery — use the delivery workflow, not direct fulfillment"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_fs_07__invoice_not_finalized_422(db, s):
    """SS-FS-07 — the invoice is not finalized: 422.
    Rules: FS5."""
    S = so(db, s, "1", ready=True)
    LS = _service_line(db, s, S)
    commit_point(db)
    before = snap(db, LS)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Finalize the invoice before fulfilling this line"
    # Then 3
    assert snap(db, LS) == before


def test_ss_fs_08__already_fulfilled_still_answers(db, s):
    """SS-FS-08 — an already fulfilled line still answers "marked as fulfilled".
    Rules: FS7."""
    S = so(db, s, "1", finalized=True, is_fully_delivered=True)
    inv(db, s, S, confirmed=True, linked=True)
    LS = _service_line(db, s, S, quantity_delivered=D("2.00"))
    commit_point(db)
    result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mt(msgs[0]) == MSG("success", "Line item marked as fulfilled")
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderItem, LS.id).quantity_delivered == D("2.00")


def test_ss_fs_09__failing_commit_line_unfulfilled(db, s):
    """SS-FS-09 — a failing commit leaves the line unfulfilled.
    Rules: FS7; TC4."""
    S = so(db, s, "1", finalized=True)
    inv(db, s, S, confirmed=True, linked=True)
    LS = _service_line(db, s, S)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=s.W1.id, current_user=s.CU)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrderItem, LS.id).quantity_delivered == D("0.00")


# =========================================================================== #
# SalesService._settle_replacement_credit_notes — BUG-3217 (OQ-64),
# through complete_delivery / fulfill_service_item
# =========================================================================== #


def _settled_text(s, n, amount):
    return f"Return SR-{s.TAG}-{n}: credit note settled by replacement ({amount})"


def _no_return_msgs(msgs):
    return not any(m.message.startswith("Return ") for m in msgs)


def _no_success_return_msgs(msgs):
    return not any(m.type == "success" and m.message.startswith("Return ") for m in msgs)


@xfail(3217)
def test_ss_sr_01__settlement_entry_exact_fields(db, s):
    """SS-SR-01 — the replacement delivery writes the settlement entry with its exact fields; committed.
    Rules: SR1, SR2, SR3; DV6a [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    p = PAYS(db, n.CN)[0]
    assert p.payment_amount == D("3000.00")
    assert p.payment_method == "settled_by_replacement"
    assert p.is_voided is False
    assert p.workspace_id == s.W1.id
    # Then 4
    assert PAYS(db, n.CN)[0].payment_date == UTCDAY
    # Then 5
    assert PAYS(db, n.CN)[0].created_by == s.U2.id
    # Then 6
    assert PAYS(db, n.CN)[0].payment_reference == f"DEL-{s.TAG}-1"
    # Then 7
    assert PAYS(db, n.CN)[0].notes == f"Settled by replacement — DEL-{s.TAG}-1 for SR-{s.TAG}-1"


@xfail(3217)
def test_ss_sr_02__credit_note_paid_return_paid(db, s):
    """SS-SR-02 — the credit note becomes paid and the return paid.
    Rules: SR3 [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("3000.00")
    assert c.payment_status == "paid"
    # Then 3
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.invoice_status == "confirmed"
    assert c.invoice_amount == D("3000.00")
    # Then 4
    r = rr(db, SalesOrderReturn, n.R1.id)
    assert r.paid is True
    assert r.status == "completed"


@xfail(3217)
def test_ss_sr_03__one_settled_event_with_links(db, s):
    """SS-SR-03 — one `return_replacement_settled` event on the order, with the links.
    Rules: SR4, SR5 [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    assert types(db, n.S).count("return_replacement_settled") == 1
    # Then 3
    e = ev_of(db, n.S, "return_replacement_settled")
    assert e.description == f"Return SR-{s.TAG}-1 settled by replacement — 3000.00 taka credit cleared"
    assert e.performed_by == s.U2.id
    # Then 4
    assert e.metadata_json == {"return_id": n.R1.id, "invoice_id": n.CN.id, "payment_id": PAYS(db, n.CN)[0].id, "delivery_id": n.D1.id}
    # Then 5
    assert "delivery_completed" in types(db, n.S)


@xfail(3217)
def test_ss_sr_04__settlement_message_after_delivery_messages(db, s):
    """SS-SR-04 — the settlement message is appended after the delivery messages.
    Rules: SR6, DV6a [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert mt(msgs[0]) == MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed")
    # Then 2
    assert len(msgs) == 4
    # Then 3
    assert mt(msgs[2]) == MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered")
    # Then 4
    assert mt(msgs[3]) == MSG("success", _settled_text(s, 1, "3000.00"))


def test_ss_sr_05__delivery_holds_today_and_after_fix(db, s):
    """SS-SR-05 — what holds today and after the fix: delivery, stock, one ledger row, order stays completed, no notification.
    Rules: DV2, DV6, SR5, SR9; RK10."""
    n = scene(db, s)
    cp = commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert mts(msgs[:3]) == [
        MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed"),
        MSG("info", "Inventory updated: 1 items, 1.00 units deducted"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
    ]
    # Then 2
    db.rollback()
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "delivered"
    # Then 3
    line = rr(db, SalesOrderItem, n.L1.id)
    assert line.quantity_delivered == D("4.00")
    assert line.quantity_returned == D("1.00")
    # Then 4
    assert rr(db, Product, s.P1.id).qty == 99
    # Then 5
    led = NEWLED(db, cp)
    assert len(led) == 1
    assert led[0].transaction_type == "sale"
    assert led[0].quantity == 1
    assert led[0].source_type == "sales_delivery"
    assert led[0].source_id == n.D1.id
    # Then 6
    row = rr(db, SalesOrder, n.S.id)
    assert row.order_completed is True
    assert row.completed_at == T0
    # Then 7
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.invoice_status == "confirmed"
    assert c.invoice_amount == D("3000.00")
    assert rr(db, SalesOrderReturn, n.R1.id).status == "completed"
    # Then 8
    assert "delivery_completed" in types(db, n.S)
    # Then 9
    assert notes(db) == []


@xfail(3217)
def test_ss_sr_06__helper_alone_flush_only(db, s):
    """SS-SR-06 — the helper on its own: one message, entry flushed, never commits or rolls back.
    Rules: SR3, SR6; Persistence (flush only) [BUG-3217]."""
    n = scene(db, s, L1={"quantity_delivered": D("4.00")}, D1={"delivery_status": "delivered"})
    commit_point(db)
    # Then 1
    with spies(db) as (cm, rb):
        result = svc._settle_replacement_credit_notes(db, order=n.S, workspace_id=s.W1.id, user_id=s.U2.id, delivery=n.D1)
    assert mts(result) == [MSG("success", _settled_text(s, 1, "3000.00"))]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert not db.new
    # Then 5
    assert db.execute(select(func.count()).select_from(InvoicePayment).where(InvoicePayment.invoice_id == n.CN.id)).scalar() == 1


@xfail(3217)
def test_ss_sr_07__amount_is_half_up_total(db, s):
    """SS-SR-07 — the amount is the credit note's half-up total (0.50 × 0.25 → 0.13).
    Rules: SR3; RC3; HR-15 [BUG-3217]."""
    n = scene(
        db, s,
        L1={"item_id": None, "description": "Ribbon", "quantity_ordered": D("0.50"), "quantity_delivered": D("0.00"), "quantity_returned": D("0.50"), "unit_price": D("0.25"), "line_total": D("0.13")},
        cn_amount="0.13", cn_lines=("0.13",), rl_q="0.50", dl_q="0.50",
    )
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    assert PAYS(db, n.CN)[0].payment_amount == D("0.13")
    # Then 4
    assert mt(msgs[-1]) == MSG("success", _settled_text(s, 1, "0.13"))
    # Then 5
    assert ev_of(db, n.S, "return_replacement_settled").description == f"Return SR-{s.TAG}-1 settled by replacement — 0.13 taka credit cleared"


def test_ss_sr_08__partial_redelivery_settles_nothing(db, s):
    """SS-SR-08 — a partial redelivery settles nothing.
    Rules: SR2."""
    n = scene(db, s, L1={"quantity_delivered": D("2.00"), "quantity_returned": D("2.00")}, cn_amount="6000.00", cn_lines=("6000.00",), rl_q="2.00", dl_q="1.00")
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert mt(msgs[2]) == MSG("info", "1.00 units remaining to be delivered")
    # Then 2
    assert len(msgs) == 3
    # Then 3
    db.rollback()
    assert rr(db, SalesOrderItem, n.L1.id).quantity_delivered == D("3.00")
    # Then 4
    assert PAYS(db, n.CN) == []
    # Then 5
    assert snap(db, n.CN) == before
    # Then 6
    assert rr(db, SalesOrderReturn, n.R1.id).paid is False
    # Then 7
    assert "return_replacement_settled" not in types(db, n.S)


@xfail(3217)
def test_ss_sr_09__last_gap_closed_settles_whole_note(db, s):
    """SS-SR-09 — the delivery that closes the last gap settles the whole credit note.
    Rules: SR2, SR3 [BUG-3217]."""
    n = scene(db, s, L1={"quantity_delivered": D("3.00"), "quantity_returned": D("2.00")}, cn_amount="6000.00", cn_lines=("6000.00",), rl_q="2.00", dl_q="1.00")
    D0 = dlv(db, s, n.S, "0", delivered=True)
    dl(db, D0, n.L1, "1.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    assert PAYS(db, n.CN)[0].payment_amount == D("6000.00")
    assert PAYS(db, n.CN)[0].payment_reference == f"DEL-{s.TAG}-1"
    # Then 4
    assert mt(msgs[-1]) == MSG("success", _settled_text(s, 1, "6000.00"))


def test_ss_sr_10__refund_return_never_settled(db, s):
    """SS-SR-10 — a refund return is never settled.
    Rules: SR1."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_ordered=D("5.00"), quantity_delivered=D("3.00"), quantity_returned=D("1.00"), quantity_refunded=D("1.00"), line_total=D("15000.00"))
    CN = cn(db, s, S, "3000.00")
    invl(db, s, CN, 1, "3000.00")
    R1 = ret(db, s, S, "1", refund=True, done=True, of=CN)
    rl(db, R1, L1, "1.00")
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    before = snap(db, CN)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderItem, L1.id).quantity_delivered == D("4.00")
    # Then 3
    assert PAYS(db, CN) == []
    # Then 4
    assert snap(db, CN) == before


def test_ss_sr_11__pending_replace_return_never_settled(db, s):
    """SS-SR-11 — a pending replace return is never settled.
    Rules: SR1."""
    n = scene(db, s, R1={"status": "pending", "completed_at": None, "completed_by": None}, L1={"quantity_returned": D("0.00")})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 3
    assert snap(db, n.CN) == before
    # Then 4
    r = rr(db, SalesOrderReturn, n.R1.id)
    assert r.status == "pending"
    assert r.paid is False


def test_ss_sr_12__voided_replace_return_never_settled(db, s):
    """SS-SR-12 — a voided replace return is never settled.
    Rules: SR1."""
    n = scene(db, s, R1={"status": "voided", "completed_at": None, "completed_by": None})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 3
    assert snap(db, n.CN) == before


@xfail(3217)
def test_ss_sr_13__voided_credit_note_warning(db, s):
    """SS-SR-13 — a voided credit note gets a warning, nothing written.
    Rules: SR1, SR1b [BUG-3217]."""
    n = scene(db, s, CN={"voided_inv": True})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 4
    # Then 2
    assert mtd(msgs[3]) == MSGD("warning", VOIDCN(n.R1), {"return_id": n.R1.id, "invoice_id": n.CN.id})
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 4
    assert snap(db, n.CN) == before
    # Then 5
    assert "return_replacement_settled" not in types(db, n.S)


def test_ss_sr_14__draft_credit_note_skipped(db, s):
    """SS-SR-14 — a draft credit note is skipped.
    Rules: SR1."""
    n = scene(db, s, CN={"draft": True})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 3
    assert snap(db, n.CN) == before


@pytest.mark.parametrize(
    "ws",
    [
        pytest.param("0", id="SS-SR-15", marks=xfail(3217)),
        pytest.param("2", id="SS-SR-16", marks=xfail(3217)),
    ],
)
def test_ss_sr_15_16__foreign_credit_note_id_free_warning(db, s, ws):
    """SS-SR-15 / SS-SR-16 — a W0 / W2 credit note linked to the W1 return: an id-free warning, nothing paid.
    Rules: SR1, SR1c [BUG-3217]; HR-16."""
    n = scene(db, s, CN={"ws": ws})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 4
    # Then 2
    assert mtd(msgs[3]) == MSGD("warning", LOSTCN(n.R1), {"return_id": n.R1.id})
    # Then 3
    assert str(n.CN.id) not in msgs[3].message
    # Then 4
    assert all_pays(db) == 0
    # Then 5
    db.rollback()
    assert snap(db, n.CN) == before
    # Then 6
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "delivered"


@pytest.mark.parametrize(
    ("ws", "num"),
    [pytest.param("0", "0", id="SS-SR-17"), pytest.param("2", "9", id="SS-SR-18")],
)
def test_ss_sr_17_18__foreign_return_row_not_settled(db, s, ws, num):
    """SS-SR-17 / SS-SR-18 — a W0 / W2 return row under the W1 order is not settled.
    Rules: SR1; HR-16."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    CNx = cn(db, s, S, "3000.00", ws=ws)
    invl(db, s, CNx, 1, "3000.00")
    Rx = ret(db, s, S, num, ws=ws, done=True, of=CNx)
    rl(db, Rx, L1, "1.00")
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    before_c, before_r = snap(db, CNx), snap(db, Rx)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    assert all_pays(db) == 0
    # Then 3
    db.rollback()
    assert snap(db, CNx) == before_c
    # Then 4
    assert snap(db, Rx) == before_r


@xfail(3217)
def test_ss_sr_19__only_this_workspace_return_settled(db, s):
    """SS-SR-19 — only this workspace's return is settled when W0 and W2 rows sit beside it.
    Rules: SR1; HR-16 [BUG-3217]."""
    n = scene(db, s)
    CN0 = cn(db, s, n.S, "3000.00", ws="0")
    R0 = ret(db, s, n.S, "0", ws="0", done=True, of=CN0)
    rl(db, R0, n.L1, "1.00")
    CN9 = cn(db, s, n.S, "3000.00", ws="2")
    R9 = ret(db, s, n.S, "9", ws="2", done=True, of=CN9)
    rl(db, R9, n.L1, "1.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    assert PAYS(db, CN0) == []
    # Then 4
    assert PAYS(db, CN9) == []
    # Then 5
    assert types(db, n.S).count("return_replacement_settled") == 1
    # Then 6
    assert len(returns_msgs(msgs)) == 1


def _refunded_text(s, amount):
    return f"Return SR-{s.TAG}-1: the credit note already has {amount} refunded — the replacement was delivered too; settle it by hand"


@xfail(3217)
def test_ss_sr_20__partly_refunded_warning(db, s):
    """SS-SR-20 — money already refunded (partly): a warning, nothing written.
    Rules: SR7 [BUG-3217]."""
    n = scene(db, s, CN={"paid_amount": D("1000.00"), "payment_status": "partial"})
    pay(db, s, n.CN, "1000.00")
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    assert mt(msgs[-1]) == MSG("warning", _refunded_text(s, "1000.00"))
    # Then 3
    assert msgs[-1].details == {"return_id": n.R1.id, "invoice_id": n.CN.id, "paid_amount": "1000.00"}
    # Then 4
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 5
    assert snap(db, n.CN) == before


def test_ss_sr_21__partly_refunded_nothing_written(db, s):
    """SS-SR-21 — money already refunded (partly): nothing is written (today and after the fix).
    Rules: SR7."""
    n = scene(db, s, CN={"paid_amount": D("1000.00"), "payment_status": "partial"})
    P = pay(db, s, n.CN, "1000.00")
    commit_point(db)
    before_c, before_r = snap(db, n.CN), snap(db, n.R1)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert _no_success_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert [p.id for p in PAYS(db, n.CN)] == [P.id]
    # Then 3
    assert snap(db, n.CN) == before_c
    # Then 4
    assert snap(db, n.R1) == before_r
    # Then 5
    assert "return_replacement_settled" not in types(db, n.S)


@xfail(3217)
def test_ss_sr_22__fully_refunded_warning(db, s):
    """SS-SR-22 — money already refunded in full: a warning with the full amount.
    Rules: SR7 [BUG-3217]."""
    n = scene(db, s, CN={"paid_amount": D("3000.00"), "payment_status": "paid"})
    pay(db, s, n.CN, "3000.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    assert mt(msgs[-1]) == MSG("warning", _refunded_text(s, "3000.00"))
    # Then 3
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1


def test_ss_sr_23__fully_refunded_nothing_written(db, s):
    """SS-SR-23 — money already refunded in full: nothing is written (today and after the fix).
    Rules: SR7."""
    n = scene(db, s, CN={"paid_amount": D("3000.00"), "payment_status": "paid"})
    P = pay(db, s, n.CN, "3000.00")
    commit_point(db)
    before_c, before_r = snap(db, n.CN), snap(db, n.R1)
    scene_call(db, s, n)
    # Then 1
    db.rollback()
    assert [p.id for p in PAYS(db, n.CN)] == [P.id]
    # Then 2
    assert snap(db, n.CN) == before_c
    # Then 3
    assert snap(db, n.R1) == before_r
    # Then 4
    assert "return_replacement_settled" not in types(db, n.S)


@xfail(3217)
def test_ss_sr_24__voided_refund_does_not_count(db, s):
    """SS-SR-24 — a voided refund does not count: the whole outstanding amount is settled.
    Rules: SR3, SR7 [BUG-3217]."""
    n = scene(db, s)
    pay(db, s, n.CN, "3000.00", voided=True)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 2
    # Then 3
    p = PAYS(db, n.CN)[1]
    assert p.payment_amount == D("3000.00")
    assert p.payment_method == "settled_by_replacement"
    assert p.is_voided is False
    # Then 4
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("3000.00")
    assert c.payment_status == "paid"
    # Then 5
    assert mt(msgs[-1]) == MSG("success", _settled_text(s, 1, "3000.00"))


def test_ss_sr_25__active_settlement_never_doubled(db, s):
    """SS-SR-25 — an active settlement entry is never doubled and gives no warning.
    Rules: SR1, SR8."""
    n = scene(db, s, CN={"paid_amount": D("3000.00"), "payment_status": "paid"}, R1={"paid": True})
    P = pay(db, s, n.CN, "3000.00", settle=True)
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 3
    # Then 2
    assert _no_return_msgs(msgs)
    # Then 3
    db.rollback()
    assert [p.id for p in PAYS(db, n.CN)] == [P.id]
    # Then 4
    assert snap(db, n.CN) == before
    # Then 5
    assert "return_replacement_settled" not in types(db, n.S)


@xfail(3217)
def test_ss_sr_26__voided_settlement_reconsidered(db, s):
    """SS-SR-26 — a voided settlement entry makes the return count again: a new entry.
    Rules: SR1, SR8 [BUG-3217]."""
    n = scene(db, s)
    P = pay(db, s, n.CN, "3000.00", settle=True, voided=True)
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 2
    # Then 3
    assert PAYS(db, n.CN)[0].id == P.id
    assert PAYS(db, n.CN)[0].is_voided is True
    # Then 4
    p = PAYS(db, n.CN)[1]
    assert p.payment_method == "settled_by_replacement"
    assert p.is_voided is False
    assert p.created_by == s.U2.id


@xfail(3217)
def test_ss_sr_27__two_returns_settled_in_id_order(db, s):
    """SS-SR-27 — two fully replaced returns: two entries, events and messages, in return id order.
    Rules: SR1, SR4, SR6 [BUG-3217]."""
    n = scene(db, s)
    L2 = ln(db, s, n.S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    CN2 = cn(db, s, n.S, "3000.00")
    invl(db, s, CN2, 1, "3000.00")
    R2 = ret(db, s, n.S, "2", done=True, of=CN2)
    rl(db, R2, L2, "1.00")
    dl(db, n.D1, L2, "1.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    assert len(PAYS(db, CN2)) == 1
    # Then 3
    assert PAYS(db, n.CN)[0].id < PAYS(db, CN2)[0].id
    # Then 4
    assert [e.metadata_json["return_id"] for e in EV(db, n.S) if e.event_type == "return_replacement_settled"] == [n.R1.id, R2.id]
    # Then 5
    assert mts(msgs[-2:]) == [MSG("success", _settled_text(s, 1, "3000.00")), MSG("success", _settled_text(s, 2, "3000.00"))]


@xfail(3217)
def test_ss_sr_28__only_fully_replaced_return_settled(db, s):
    """SS-SR-28 — of two returns only the fully replaced one is settled.
    Rules: SR2 [BUG-3217]."""
    n = scene(db, s)
    L2 = ln(db, s, n.S, quantity_delivered=D("2.00"), quantity_returned=D("2.00"))
    CN2 = cn(db, s, n.S, "6000.00")
    invl(db, s, CN2, 1, "6000.00")
    R2 = ret(db, s, n.S, "2", done=True, of=CN2)
    rl(db, R2, L2, "2.00")
    dl(db, n.D1, L2, "1.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    assert PAYS(db, CN2) == []
    # Then 4
    assert len(returns_msgs(msgs)) == 1
    assert f"SR-{s.TAG}-1" in returns_msgs(msgs)[0].message


def test_ss_sr_29__return_with_open_line_not_settled(db, s):
    """SS-SR-29 — a return with one line still open is not settled.
    Rules: SR2."""
    n = scene(db, s, cn_amount="6000.00", cn_lines=("6000.00",))
    L2 = ln(db, s, n.S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    rl(db, n.R1, L2, "1.00")
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert _no_return_msgs(msgs)
    # Then 2
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 3
    assert snap(db, n.CN) == before


@xfail(3217)
def test_ss_sr_30__two_line_return_settled_once(db, s):
    """SS-SR-30 — a two-line return whose both gaps close is settled once, for its full note.
    Rules: SR2, SR3 [BUG-3217]."""
    n = scene(db, s, cn_amount="6000.00", cn_lines=("3000.00", "3000.00"))
    L2 = ln(db, s, n.S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    rl(db, n.R1, L2, "1.00")
    dl(db, n.D1, L2, "1.00")
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    assert PAYS(db, n.CN)[0].payment_amount == D("6000.00")
    # Then 4
    assert types(db, n.S).count("return_replacement_settled") == 1


# [claude]
@xfail(3217)
def test_ss_sr_31__failing_settlement_undoes_delivery(db, s):
    """SS-SR-31 — a failing settlement undoes the delivery too.
    Rules: DV6a; TC3 [BUG-3217]."""
    n = scene(db, s)
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(SalesService, "_settle_replacement_credit_notes", side_effect=RuntimeError("settle")):
            scene_call(db, s, n)
    assert str(exc.value) == "settle"
    # Then 2
    assert X not in db
    # Then 3
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "planned"
    # Then 4
    assert rr(db, SalesOrderItem, n.L1.id).quantity_delivered == D("3.00")
    # Then 5
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 6
    assert NEWLED(db, cp) == []
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_sr_32__failing_commit_no_delivery_no_settlement(db, s):
    """SS-SR-32 — a failing commit saves neither the delivery nor a settlement.
    Rules: DV6a; TC4."""
    n = scene(db, s)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            scene_call(db, s, n)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "planned"
    # Then 4
    assert PAYS(db, n.CN) == []
    # Then 5
    assert rr(db, AccountInvoice, n.CN.id).paid_amount == D("0.00")


def _fs_scene(db, s):
    n = SimpleNamespace()
    n.S = so(db, s, "1", finalized=True, completed=True)
    n.VR = inv(db, s, n.S, confirmed=True, linked=True)
    n.LS = ln(db, s, n.S, service=True, quantity_ordered=D("2.00"), quantity_delivered=D("1.00"), quantity_returned=D("1.00"), unit_price=D("500.00"), line_total=D("1000.00"))
    n.CN = cn(db, s, n.S, "500.00")
    invl(db, s, n.CN, 1, "500.00")
    n.R1 = ret(db, s, n.S, "1", done=True, of=n.CN)
    rl(db, n.R1, n.LS, "1.00")
    return n


@xfail(3217)
def test_ss_sr_33__direct_fulfilment_settles_with_line_link(db, s):
    """SS-SR-33 — direct fulfilment of a replaced service line settles with the line as link.
    Rules: FS8a, SR3, SR4, SR6 [BUG-3217]."""
    n = _fs_scene(db, s)
    commit_point(db)
    result = svc.fulfill_service_item(db, order_id=n.S.id, order_item_id=n.LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == n.S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, n.CN)) == 1
    # Then 3
    p = PAYS(db, n.CN)[0]
    assert p.payment_amount == D("500.00")
    assert p.payment_method == "settled_by_replacement"
    assert p.payment_date == UTCDAY
    assert p.created_by == s.U2.id
    # Then 4
    assert PAYS(db, n.CN)[0].payment_reference == f"SO-item-{n.LS.id}"
    # Then 5
    assert PAYS(db, n.CN)[0].notes == f"Settled by replacement — direct fulfilment for SR-{s.TAG}-1"
    # Then 6
    assert ev_of(db, n.S, "return_replacement_settled").metadata_json == {"return_id": n.R1.id, "invoice_id": n.CN.id, "payment_id": PAYS(db, n.CN)[0].id, "delivery_id": None}
    # Then 7
    assert mts(msgs) == [
        MSG("success", "Line item marked as fulfilled"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
        MSG("success", _settled_text(s, 1, "500.00")),
    ]


def test_ss_sr_34__direct_refulfilment_on_completed_order(db, s):
    """SS-SR-34 — direct refulfilment of a replaced line on a completed order (today and after the fix).
    Rules: FS8, FS7."""
    n = _fs_scene(db, s)
    cp = commit_point(db)
    result = svc.fulfill_service_item(db, order_id=n.S.id, order_item_id=n.LS.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mts(msgs[:2]) == [
        MSG("success", "Line item marked as fulfilled"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
    ]
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderItem, n.LS.id).quantity_delivered == D("2.00")
    # Then 3
    assert rr(db, SalesOrder, n.S.id).order_completed is True
    # Then 4
    assert NEWLED(db, cp) == []
    assert len(rows_where(db, SalesDelivery, SalesDelivery.sales_order_id == n.S.id)) == 0
    # Then 5
    assert notes(db) == []


@xfail(3217)
def test_ss_sr_35__refunded_units_count_refund_note_left_alone(db, s):
    """SS-SR-35 — refunded units count toward "fully replaced"; the refund return's note is left alone.
    Rules: SR1, SR2 [BUG-3217]."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("2.00"), quantity_returned=D("2.00"), quantity_refunded=D("1.00"))
    CNr = cn(db, s, S, "3000.00")
    invl(db, s, CNr, 1, "3000.00")
    Rr = ret(db, s, S, "0", refund=True, done=True, of=CNr)
    rl(db, Rr, L1, "1.00")
    CN = cn(db, s, S, "3000.00")
    invl(db, s, CN, 1, "3000.00")
    R1 = ret(db, s, S, "1", done=True, of=CN)
    rl(db, R1, L1, "1.00")
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    commit_point(db)
    before = snap(db, CNr)
    result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert order.id == S.id
    # Then 2
    db.rollback()
    assert len(PAYS(db, CN)) == 1
    # Then 3
    assert PAYS(db, CNr) == []
    # Then 4
    assert snap(db, CNr) == before


def test_ss_sr_36__completing_replace_return_does_not_settle(db, s):
    """SS-SR-36 — completing a replace return does not settle its credit note.
    Rules: RK10, SR2."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00")
    invl(db, s, CN, 1, "3000.00")
    R1 = ret(db, s, S, "1", of=CN)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == R1.id
    # Then 2
    db.rollback()
    r = rr(db, SalesOrderReturn, R1.id)
    assert r.status == "completed"
    assert r.paid is False
    # Then 3
    assert PAYS(db, CN) == []
    # Then 4
    c = rr(db, AccountInvoice, CN.id)
    assert c.invoice_status == "confirmed"
    assert c.paid_amount == D("0.00")
    assert c.payment_status == "unpaid"
    # Then 5
    assert rr(db, SalesOrder, S.id).order_completed is True


def test_ss_sr_37__voided_credit_note_delivery_goes_through(db, s):
    """SS-SR-37 — a voided credit note: nothing is written for it and the delivery goes through (today and after the fix).
    Rules: SR1, SR1b; DV2."""
    n = scene(db, s, CN={"voided_inv": True})
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert mts(msgs[:3]) == [
        MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed"),
        MSG("info", "Inventory updated: 1 items, 1.00 units deducted"),
        MSG("success", f"Sales order SO-{s.TAG}-1 is now fully delivered"),
    ]
    # Then 2
    assert _no_success_return_msgs(msgs)
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 4
    assert snap(db, n.CN) == before
    # Then 5
    r = rr(db, SalesOrderReturn, n.R1.id)
    assert r.paid is False
    assert r.status == "completed"
    # Then 6
    assert "return_replacement_settled" not in types(db, n.S)
    # Then 7
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "delivered"


@pytest.mark.parametrize("ws", [pytest.param("0", id="SS-SR-38"), pytest.param("2", id="SS-SR-39")])
def test_ss_sr_38_39__foreign_credit_note_not_locked_not_paid(db, s, ws):
    """SS-SR-38 / SS-SR-39 — a W0 / W2 credit note: not locked, not paid, the delivery goes through (today and after the fix).
    Rules: SR1, SR1c; HR-16."""
    n = scene(db, s, CN={"ws": ws})
    commit_point(db)
    before = snap(db, n.CN)
    cnid, did = n.CN.id, n.D1.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.complete_delivery(db, delivery_id=did, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert _no_success_return_msgs(msgs)
    # Then 2
    assert rec.cnlock(cnid) is None
    # Then 3
    assert all_pays(db) == 0
    # Then 4
    db.rollback()
    assert snap_id(db, AccountInvoice, cnid) == before
    # Then 5
    assert rr(db, SalesDelivery, did).delivery_status == "delivered"


def _second_delivery(db, s, n):
    L2 = ln(db, s, n.S, quantity_delivered=D("3.00"))
    D2 = dlv(db, s, n.S, "2")
    dl(db, D2, L2, "1.00")
    return D2


@xfail(3217)
def test_ss_sr_40__voided_note_warning_repeated(db, s):
    """SS-SR-40 — the voided-note warning is repeated on the next delivery.
    Rules: SR1b [BUG-3217]."""
    n = scene(db, s, CN={"voided_inv": True})
    D2 = _second_delivery(db, s, n)
    commit_point(db)
    scene_call(db, s, n)
    result = svc.complete_delivery(db, delivery_id=D2.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mtd(msgs[-1]) == MSGD("warning", VOIDCN(n.R1), {"return_id": n.R1.id, "invoice_id": n.CN.id})
    # Then 2
    assert len(returns_msgs(msgs)) == 1
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []


@xfail(3217)
def test_ss_sr_41__lost_note_warning_repeated(db, s):
    """SS-SR-41 — the lost-note warning is repeated on the next delivery.
    Rules: SR1c [BUG-3217]; HR-16."""
    n = scene(db, s, CN={"ws": "2"})
    D2 = _second_delivery(db, s, n)
    commit_point(db)
    scene_call(db, s, n)
    result = svc.complete_delivery(db, delivery_id=D2.id, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert mtd(msgs[-1]) == MSGD("warning", LOSTCN(n.R1), {"return_id": n.R1.id})
    # Then 2
    assert str(n.CN.id) not in msgs[-1].message
    # Then 3
    assert all_pays(db) == 0


def test_ss_sr_42__voided_note_not_fully_replaced_no_message(db, s):
    """SS-SR-42 — a voided credit note of a return not yet fully replaced: no message.
    Rules: SR1b, SR2."""
    n = scene(db, s, CN={"voided_inv": True}, cn_amount="6000.00", cn_lines=("6000.00",), L1={"quantity_delivered": D("2.00"), "quantity_returned": D("2.00")}, rl_q="2.00", dl_q="1.00")
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 3
    # Then 2
    assert _no_return_msgs(msgs)
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 4
    assert snap(db, n.CN) == before


def test_ss_sr_43__w2_note_not_fully_replaced_no_message(db, s):
    """SS-SR-43 — a W2 credit note of a return not yet fully replaced: no message.
    Rules: SR1c, SR2; HR-16."""
    n = scene(db, s, CN={"ws": "2"}, cn_amount="6000.00", cn_lines=("6000.00",), L1={"quantity_delivered": D("2.00"), "quantity_returned": D("2.00")}, rl_q="2.00", dl_q="1.00")
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 3
    # Then 2
    assert _no_return_msgs(msgs)
    # Then 3
    assert all_pays(db) == 0
    # Then 4
    db.rollback()
    assert snap(db, n.CN) == before


@xfail(3217)
def test_ss_sr_44__one_financial_audit_row(db, s):
    """SS-SR-44 — the settlement leaves one financial audit row, as any payment.
    Rules: SR3a [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    scene_call(db, s, n)
    # Then 1
    db.rollback()
    assert len(SETTLE(db, n.CN)) == 1
    P = SETTLE(db, n.CN)[0]
    # Then 2
    assert len(AUD(db, P.id)) == 1
    # Then 3
    a = AUD(db, P.id)[0]
    assert a.action_type == "created"
    assert a.related_entity_type == "invoice"
    assert a.related_entity_id == n.CN.id
    assert a.performed_by == s.U2.id
    assert a.workspace_id == s.W1.id
    # Then 4
    after = a.changes["after"]
    assert D(str(after["payment_amount"])) == D("3000.00")
    assert after["payment_date"] == "2026-09-27"
    assert after["payment_method"] == "settled_by_replacement"
    # Then 5
    assert a.changes["invoice_status_changed"] == {"before": "unpaid", "after": "paid"}


@xfail(3217)
def test_ss_sr_45__one_payment_recorded_event(db, s):
    """SS-SR-45 — the settlement leaves one `payment_recorded` invoice event.
    Rules: SR3a [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    scene_call(db, s, n)
    # Then 1
    db.rollback()
    assert itypes(db, n.CN).count("payment_recorded") == 1
    # Then 2
    e = next(x for x in iev(db, n.CN) if x.event_type == "payment_recorded")
    assert e.description == "Payment recorded"
    assert e.performed_by == s.U2.id
    # Then 3
    assert e.metadata_json == {
        "payment_id": SETTLE(db, n.CN)[0].id,
        "payment_amount": "3000.00",
        "payment_method": "settled_by_replacement",
        "payment_status_before": "unpaid",
        "payment_status_after": "paid",
    }


@xfail(3217)
def test_ss_sr_46__payment_lock_does_not_stop_settlement(db, s):
    """SS-SR-46 — a payment lock on the credit note does not stop the settlement.
    Rules: SR3a [BUG-3217]."""
    n = scene(db, s, CN={"allow_payments": False, "payment_locked_reason": "Held by finance"})
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    db.rollback()
    assert len(SETTLE(db, n.CN)) == 1
    assert SETTLE(db, n.CN)[0].payment_amount == D("3000.00")
    # Then 2
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("3000.00")
    assert c.payment_status == "paid"
    assert c.allow_payments is False
    # Then 3
    assert mt(msgs[-1]) == MSG("success", _settled_text(s, 1, "3000.00"))
    # Then 4
    assert not any(m.type == "warning" for m in msgs)


def test_ss_sr_47__payment_locked_note_delivery_completes(db, s):
    """SS-SR-47 — a payment-locked credit note: the delivery still completes (today and after the fix).
    Rules: SR3a; DV2."""
    n = scene(db, s, CN={"allow_payments": False, "payment_locked_reason": "Held by finance"})
    commit_point(db)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert mt(msgs[0]) == MSG("success", f"Delivery DEL-{s.TAG}-1 marked as completed")
    # Then 2
    db.rollback()
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "delivered"
    # Then 3
    assert rr(db, SalesOrderItem, n.L1.id).quantity_delivered == D("4.00")
    # Then 4
    assert rr(db, Product, s.P1.id).qty == 99


@xfail(3217)
def test_ss_sr_48__entry_linked_to_settlement_event(db, s):
    """SS-SR-48 — the entry is linked to the settlement event (`sales_order_event`).
    Rules: SR3c, SR4 [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    scene_call(db, s, n)
    # Then 1
    db.rollback()
    assert len(SETTLE(db, n.CN)) == 1
    P = SETTLE(db, n.CN)[0]
    # Then 2
    E = ev_of(db, n.S, "return_replacement_settled")
    # Then 3
    assert P.source_type == "sales_order_event"
    assert P.source_id == E.id
    # Then 4
    assert E.metadata_json["payment_id"] == P.id
    assert E.metadata_json["delivery_id"] == n.D1.id


@xfail(3217)
def test_ss_sr_49__direct_fulfilment_links_entry(db, s):
    """SS-SR-49 — a direct fulfilment links the entry the same way, with no delivery.
    Rules: SR3c, FS8a [BUG-3217]."""
    n = _fs_scene(db, s)
    commit_point(db)
    svc.fulfill_service_item(db, order_id=n.S.id, order_item_id=n.LS.id, workspace_id=s.W1.id, current_user=s.CU)
    # Then 1
    db.rollback()
    assert len(SETTLE(db, n.CN)) == 1
    P = SETTLE(db, n.CN)[0]
    # Then 2
    E = ev_of(db, n.S, "return_replacement_settled")
    # Then 3
    assert P.source_type == "sales_order_event"
    assert P.source_id == E.id
    # Then 4
    assert E.metadata_json["delivery_id"] is None


def test_ss_sr_50__zero_credit_note_nothing(db, s):
    """SS-SR-50 — a 0.00 credit note: no entry, no event, no message (today and after the fix).
    Rules: SR3b."""
    n = scene(db, s, cn_amount="0.00", CN={"payment_status": "paid"}, cn_lines=("0.00",))
    commit_point(db)
    before = snap(db, n.CN)
    result = scene_call(db, s, n)
    order, msgs = result
    # Then 1
    assert len(msgs) == 3
    # Then 2
    assert _no_return_msgs(msgs)
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 4
    assert snap(db, n.CN) == before
    # Then 5
    assert "return_replacement_settled" not in types(db, n.S)
    # Then 6
    assert rr(db, SalesDelivery, n.D1.id).delivery_status == "delivered"


@xfail(3217)
def test_ss_sr_51__credit_note_locked_before_payments_read(db, s):
    """SS-SR-51 — the credit note is locked before its payments are looked at.
    Rules: SR1a [BUG-3217]; HR-10."""
    n = scene(db, s)
    commit_point(db)
    cnid, did = n.CN.id, n.D1.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.complete_delivery(db, delivery_id=did, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert rec.cnlock(cnid) is not None
    # Then 2
    assert rec.payread(cnid) is None or rec.cnlock(cnid) < rec.payread(cnid)
    # Then 3
    db.rollback()
    assert len(SETTLE(db, cnid)) == 1


@xfail(3217)
def test_ss_sr_52__credit_notes_locked_in_return_id_order(db, s):
    """SS-SR-52 — two credit notes are locked in return id order.
    Rules: SR1a [BUG-3217]; HR-10."""
    S = so(db, s, "1", finalized=True, completed=True)
    inv(db, s, S, confirmed=True, linked=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    L2 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    CNb = cn(db, s, S, "3000.00")
    invl(db, s, CNb, 1, "3000.00")
    CNa = cn(db, s, S, "3000.00")
    invl(db, s, CNa, 1, "3000.00")
    R1 = ret(db, s, S, "1", done=True, of=CNa)
    rl(db, R1, L1, "1.00")
    R2 = ret(db, s, S, "2", done=True, of=CNb)
    rl(db, R2, L2, "1.00")
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "1.00")
    dl(db, D1, L2, "1.00")
    commit_point(db)
    did, a_id, b_id = D1.id, CNa.id, CNb.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.complete_delivery(db, delivery_id=did, workspace_id=s.W1.id, current_user=s.CU)
    order, msgs = result
    # Then 1
    assert rec.cnlock(a_id) is not None
    assert rec.cnlock(b_id) is not None
    # Then 2
    assert rec.cnlock(a_id) < rec.cnlock(b_id)


def _settled_scene(db, s, **pay_but):
    n = scene(db, s, CN={"paid_amount": D("3000.00"), "payment_status": "paid"}, R1={"paid": True})
    n.P = pay(db, s, n.CN, "3000.00", settle=True, **pay_but)
    return n


@xfail(3217)
def test_ss_sr_53__settlement_entry_not_deletable(db, s):
    """SS-SR-53 — a settlement entry cannot be deleted.
    Rules: SR8a [BUG-3217] (refusal in the invoice payment manager)."""
    n = _settled_scene(db, s)
    P = n.P
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.delete_payment(db, payment_id=P.id, workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NODEL
    # Then 3
    assert count_where(db, InvoicePayment, InvoicePayment.id == P.id) == 1
    # Then 4
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("3000.00")
    assert c.payment_status == "paid"


@xfail(3217)
def test_ss_sr_54__settlement_notes_not_editable(db, s):
    """SS-SR-54 — a settlement entry's notes cannot be edited.
    Rules: SR8a [BUG-3217]."""
    n = _settled_scene(db, s, notes="Settled")
    P = n.P
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(notes="edited"), workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NODEL
    # Then 3
    p = rr(db, InvoicePayment, P.id)
    assert p.notes == "Settled"
    assert p.payment_method == "settled_by_replacement"


@xfail(3217)
def test_ss_sr_55__settlement_method_not_changeable(db, s):
    """SS-SR-55 — a settlement entry's method cannot be changed to cash.
    Rules: SR8a [BUG-3217]."""
    n = _settled_scene(db, s, payment_reference="DEL-X")
    P = n.P
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(payment_method="cash", payment_reference="CASH-1", payment_date=date(2026, 9, 5)), workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NODEL
    # Then 3
    p = rr(db, InvoicePayment, P.id)
    assert p.payment_method == "settled_by_replacement"
    assert p.payment_reference == "DEL-X"
    assert p.payment_date == date(2026, 9, 2)


@xfail(3217)
def test_ss_sr_56__delivery_written_entry_refuses_deletion(db, s):
    """SS-SR-56 — the entry written by a delivery refuses deletion.
    Rules: SR3, SR8a [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    scene_call(db, s, n)
    # Given 2
    P = SETTLE(db, n.CN)[0]
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.delete_payment(db, payment_id=P.id, workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == NODEL
    # Then 3
    assert count_where(db, InvoicePayment, InvoicePayment.id == P.id) == 1


@xfail(3217)
def test_ss_sr_57__reserved_method_refused_on_new_payment(db, s):
    """SS-SR-57 — the reserved method cannot be entered by hand on a new payment.
    Rules: SR8c [BUG-3217]."""
    n = scene(db, s)
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=n.CN.id, payment_amount=D("100.00"), payment_date=date(2026, 9, 2), payment_method="settled_by_replacement"), workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RESERVED
    # Then 3
    db.rollback()
    assert PAYS(db, n.CN) == []
    # Then 4
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("0.00")
    assert c.payment_status == "unpaid"


@xfail(3217)
def test_ss_sr_58__cash_payment_not_relabelled_reserved(db, s):
    """SS-SR-58 — a cash payment cannot be re-labelled with the reserved method.
    Rules: SR8c [BUG-3217]."""
    n = scene(db, s, CN={"paid_amount": D("1000.00"), "payment_status": "partial"})
    P = pay(db, s, n.CN, "1000.00")
    commit_point(db)
    sp = db.begin_nested()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(payment_method="settled_by_replacement"), workspace_id=s.W1.id, user_id=s.U2.id)
    if sp.is_active:
        sp.rollback()
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == RESERVED
    # Then 3
    assert rr(db, InvoicePayment, P.id).payment_method == "cash"


def test_ss_sr_59__voiding_settlement_makes_note_owed_again(db, s):
    """SS-SR-59 — voiding a settlement entry makes the note owed again and the return unpaid; no stock moves.
    Rules: SR8, SR8b (holds today and after BUG-3217)."""
    n = scene(db, s, L1={"quantity_delivered": D("4.00")}, D1={"delivery_status": "delivered"}, CN={"paid_amount": D("3000.00"), "payment_status": "paid"}, R1={"paid": True})
    P = pay(db, s, n.CN, "3000.00", settle=True)
    cp = commit_point(db)
    ipm.void_payment(db, payment_id=P.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Wrong delivery")
    # Then 1
    p = rr(db, InvoicePayment, P.id)
    assert p.is_voided is True
    assert p.voided_by == s.U2.id
    assert p.void_note == "Wrong delivery"
    assert p.voided_at is not None
    # Then 2
    c = rr(db, AccountInvoice, n.CN.id)
    assert c.paid_amount == D("0.00")
    assert c.payment_status == "unpaid"
    assert c.invoice_status == "confirmed"
    # Then 3
    r = rr(db, SalesOrderReturn, n.R1.id)
    assert r.paid is False
    assert r.status == "completed"
    # Then 4
    assert itypes(db, n.CN).count("payment_voided") == 1
    # Then 5
    assert len([a for a in AUD(db, P.id) if a.action_type == "voided"]) == 1
    # Then 6
    assert NEWLED(db, cp) == []
    assert rr(db, Product, s.P1.id).qty == 100


# =========================================================================== #
# SalesService.get_deliveries_for_order
# =========================================================================== #


def test_ss_gd_01__order_deliveries_every_status(db, s):
    """SS-GD-01 — the order's deliveries of every status; W0 / W2 rows left out; no commit or rollback.
    Rules: GD1; TC6."""
    S = so(db, s, "1", finalized=True)
    dlv(db, s, S, "0", workspace_id=s.W0.id)
    Da = dlv(db, s, S, "1", delivered=True)
    Db = dlv(db, s, S, "2", delivery_status="cancelled")
    Dc = dlv(db, s, S, "3")
    dlv(db, s, S, "9", workspace_id=s.W2.id)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_deliveries_for_order(db, sales_order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    assert idset(result) == {Da.id, Db.id, Dc.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


@xfail(3213)
def test_ss_gd_02__other_workspace_order_404(db, s):
    """SS-GD-02 — another workspace's order: 404.
    Rules: GD2 [BUG-3213]; HR-16."""
    S9 = so(db, s, "9", ws="2")
    dlv(db, s, S9, "9")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_deliveries_for_order(db, sales_order_id=S9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S9.id)


@xfail(3213)
def test_ss_gd_03__unknown_order_404(db, s):
    """SS-GD-03 — an unknown order: 404.
    Rules: GD2 [BUG-3213]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_deliveries_for_order(db, sales_order_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


@xfail(2442)
def test_ss_gd_04__deliveries_in_id_order(db, s):
    """SS-GD-04 — the order's deliveries come back in id order.
    Rules: GD1 [BUG-2442]."""
    S = so(db, s, "1", finalized=True)
    Da = dlv(db, s, S, "1", delivered=True)
    Db = dlv(db, s, S, "2", delivery_status="cancelled")
    Dc = dlv(db, s, S, "3")
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_deliveries_for_order(db, sales_order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert rec.id_order("sales_deliveries")
    # Then 2
    assert [d.id for d in result] == [Da.id, Db.id, Dc.id]


# =========================================================================== #
# SalesService.get_sales_order_items
# =========================================================================== #


def test_ss_gi_01__order_lines_of_workspace(db, s):
    """SS-GI-01 — the order's lines of this workspace only; no commit or rollback.
    Rules: GI1; TC6."""
    S = so(db, s, "1")
    ln(db, s, S, workspace_id=s.W0.id)
    La = ln(db, s, S, quantity_ordered=D("2.00"), line_total=D("6000.00"))
    Lb = ln(db, s, S)
    ln(db, s, S, workspace_id=s.W2.id)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_sales_order_items(db, sales_order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    assert idset(result) == {La.id, Lb.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


@xfail(3213)
def test_ss_gi_02__other_workspace_order_404(db, s):
    """SS-GI-02 — another workspace's order: 404.
    Rules: GI2 [BUG-3213]; HR-16."""
    S0 = so(db, s, "0", ws="0")
    ln(db, s, S0)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_sales_order_items(db, sales_order_id=S0.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S0.id)


@xfail(1270)
def test_ss_gi_03__lines_in_id_order(db, s):
    """SS-GI-03 — the order's lines come back in id order.
    Rules: GI1 [BUG-1270]."""
    S = so(db, s, "1")
    La = ln(db, s, S, quantity_ordered=D("2.00"), line_total=D("6000.00"))
    Lb = ln(db, s, S)
    Lc = ln(db, s, S, free="Ribbon")
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_sales_order_items(db, sales_order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert rec.id_order("sales_order_items")
    # Then 2
    assert [x.id for x in result] == [La.id, Lb.id, Lc.id]


# =========================================================================== #
# SalesService.get_delivery
# =========================================================================== #


def test_ss_gv_01__returns_delivery_no_commit(db, s):
    """SS-GV-01 — returns the delivery; no commit or rollback.
    Rules: GV1; TC6."""
    S = so(db, s, "1")
    D1 = dlv(db, s, S, "1")
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_delivery(db, delivery_id=D1.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == D1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


@xfail(3197)
def test_ss_gv_02__unknown_delivery_not_found(db, s):
    """SS-GV-02 — an unknown delivery: NotFoundError 404.
    Rules: GV1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_delivery(db, delivery_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(MISSING)


@xfail(3197)
def test_ss_gv_03__w2_delivery_not_found(db, s):
    """SS-GV-03 — a W2 delivery: NotFoundError 404.
    Rules: GV1 [BUG-3197]; HR-16."""
    S9 = so(db, s, "9", ws="2")
    D9 = dlv(db, s, S9, "9")
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_delivery(db, delivery_id=D9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(D9.id)


def test_ss_gv_04__not_found_no_commit_no_rollback(db, s):
    """SS-GV-04 — not found neither commits nor rolls back (today and after the fix).
    Rules: GV1; TC6."""
    S0 = so(db, s, "0", ws="0")
    D0 = dlv(db, s, S0, "0")
    commit_point(db)
    X_ID = mk_x(db).id
    # Then 1
    with pytest.raises(Exception):
        with spies(db) as (cm, rb):
            svc.get_delivery(db, delivery_id=D0.id, workspace_id=s.W1.id)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


# =========================================================================== #
# SalesService.get_deliveries
# =========================================================================== #


def test_ss_ld_01__status_filter_exact_workspace(db, s):
    """SS-LD-01 — a status filter: exact match, this workspace only; no commit or rollback.
    Rules: LD1; TC6."""
    S = so(db, s, "1")
    S0 = so(db, s, "0", ws="0")
    dlv(db, s, S0, "0", delivered=True)
    Da = dlv(db, s, S, "1", delivered=True)
    dlv(db, s, S, "2")
    Db = dlv(db, s, S, "3", delivered=True)
    S9 = so(db, s, "9", ws="2")
    dlv(db, s, S9, "9", delivered=True)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="delivered")
    # Then 1
    assert len(result) == 2
    assert idset(result) == {Da.id, Db.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


def test_ss_ld_02__none_means_no_filter(db, s):
    """SS-LD-02 — `None` means no filter.
    Rules: LD1."""
    S = so(db, s, "1")
    Da = dlv(db, s, S, "1", delivered=True)
    Db = dlv(db, s, S, "2")
    S9 = so(db, s, "9", ws="2")
    dlv(db, s, S9, "9")
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status=None)
    # Then 1
    assert len(result) == 2
    assert idset(result) == {Da.id, Db.id}


def test_ss_ld_03__empty_string_means_no_filter(db, s):
    """SS-LD-03 — `""` means no filter.
    Rules: LD1."""
    S = so(db, s, "1")
    Da = dlv(db, s, S, "1", delivered=True)
    Db = dlv(db, s, S, "2")
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="")
    # Then 1
    assert len(result) == 2
    assert idset(result) == {Da.id, Db.id}


def test_ss_ld_04__filter_is_exact(db, s):
    """SS-LD-04 — the filter is exact: `"Delivered"` matches nothing at the service.
    Rules: LD1."""
    S = so(db, s, "1")
    dlv(db, s, S, "1", delivered=True)
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="Delivered")
    # Then 1
    assert result == []


@xfail(2443)
def test_ss_ld_05__skip_limit_on_filtered(db, s):
    """SS-LD-05 — skip and limit on the filtered list.
    Rules: LD1 [BUG-2443]."""
    S = so(db, s, "1")
    Ds = [dlv(db, s, S, str(k), delivered=True) for k in range(1, 5)]
    dlv(db, s, S, "5")
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="delivered", skip=1, limit=2)
    # Then 1
    assert rec.id_order("sales_deliveries")
    # Then 2
    assert [d.id for d in result] == [Ds[1].id, Ds[2].id]


@xfail(100)
def test_ss_ld_06__skip_limit_on_unfiltered(db, s):
    """SS-LD-06 — skip and limit on the unfiltered list.
    Rules: LD1 [BUG-100]."""
    S = so(db, s, "1")
    Ds = [dlv(db, s, S, str(k)) for k in range(1, 5)]
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_deliveries(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert rec.id_order("sales_deliveries")
    # Then 2
    assert [d.id for d in result] == [Ds[1].id, Ds[2].id]


def test_ss_ld_07__default_limit_100(db, s):
    """SS-LD-07 — no limit given: at most 100.
    Rules: LD1."""
    S = so(db, s, "1")
    for k in range(1, 102):
        dlv(db, s, S, str(k))
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100


def test_ss_ld_08__limit_1000_passed_on(db, s):
    """SS-LD-08 — limit=1000 is passed on.
    Rules: LD1."""
    S = so(db, s, "1")
    for k in range(1, 102):
        dlv(db, s, S, str(k))
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, limit=1000)
    # Then 1
    assert len(result) == 101


@xfail(2443)
def test_ss_ld_09__filtered_list_in_id_order(db, s):
    """SS-LD-09 — the status-filtered list comes back in id order.
    Rules: LD1 [BUG-2443]."""
    S = so(db, s, "1")
    Da = dlv(db, s, S, "1", delivered=True)
    dlv(db, s, S, "2")
    Db = dlv(db, s, S, "3", delivered=True)
    Dc = dlv(db, s, S, "4", delivered=True)
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="delivered")
    # Then 1
    assert rec.id_order("sales_deliveries")
    # Then 2
    assert [d.id for d in result] == [Da.id, Db.id, Dc.id]


def test_ss_ld_10__filtered_page_of_two(db, s):
    """SS-LD-10 — skip and limit on the filtered list give two delivered rows of this workspace (today and after the fix).
    Rules: LD1 (holds before and after BUG-2443)."""
    S = so(db, s, "1")
    Ds = [dlv(db, s, S, str(k), delivered=True) for k in range(1, 5)]
    dlv(db, s, S, "5")
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, delivery_status="delivered", skip=1, limit=2)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) <= {d.id for d in Ds}
    assert all(d.delivery_status == "delivered" for d in result)


def test_ss_ld_11__unfiltered_page_of_two(db, s):
    """SS-LD-11 — skip and limit on the unfiltered list give two rows of this workspace (today and after the fix).
    Rules: LD1 (holds before and after BUG-100)."""
    S = so(db, s, "1")
    Ds = [dlv(db, s, S, str(k)) for k in range(1, 5)]
    S9 = so(db, s, "9", ws="2")
    dlv(db, s, S9, "9")
    commit_point(db)
    result = svc.get_deliveries(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) <= {d.id for d in Ds}


# =========================================================================== #
# SalesService.get_delivery_items
# =========================================================================== #


def test_ss_gdi_01__delivery_lines_of_workspace(db, s):
    """SS-GDI-01 — the delivery's lines of this workspace only; no commit or rollback.
    Rules: GDI1; TC6."""
    S = so(db, s, "1")
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    D1 = dlv(db, s, S, "1")
    dl(db, D1, L1, "9.00", workspace_id=s.W0.id)
    Ia = dl(db, D1, L1, "1.00")
    Ib = dl(db, D1, L1, "2.00")
    dl(db, D1, L1, "8.00", workspace_id=s.W2.id)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_delivery_items(db, delivery_id=D1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    assert idset(result) == {Ia.id, Ib.id}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


@xfail(3213)
def test_ss_gdi_02__other_workspace_delivery_not_found(db, s):
    """SS-GDI-02 — another workspace's delivery: NotFoundError 404.
    Rules: GDI2 [BUG-3213]; HR-16."""
    S9 = so(db, s, "9", ws="2")
    D9 = dlv(db, s, S9, "9")
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_delivery_items(db, delivery_id=D9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == DNF(D9.id)


@xfail(1271)
def test_ss_gdi_03__delivery_lines_in_id_order(db, s):
    """SS-GDI-03 — the delivery's lines come back in id order.
    Rules: GDI1 [BUG-1271]."""
    S = so(db, s, "1")
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    D1 = dlv(db, s, S, "1")
    Ia = dl(db, D1, L1, "1.00")
    Ib = dl(db, D1, L1, "2.00")
    Ic = dl(db, D1, L1, "1.00")
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.get_delivery_items(db, delivery_id=D1.id, workspace_id=s.W1.id)
    # Then 1
    assert rec.id_order("sales_delivery_items")
    # Then 2
    assert [i.id for i in result] == [Ia.id, Ib.id, Ic.id]


# =========================================================================== #
# SalesService._attach_return_invoice_for_so
# =========================================================================== #


def test_ss_rc_01__credit_note_created_linked_confirmed(db, s):
    """SS-RC-01 — the helper creates, links and confirms the credit note; never commits or rolls back.
    Rules: RC1, RC2, RC4, RC5."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R = ret(db, s, S, "1", reason="Broken leg")
    rl(db, R, L1, "1.00")
    commit_point(db)
    with spies(db) as (cm, rb):
        svc._attach_return_invoice_for_so(db, order=S, ret=R, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    cid = rr(db, SalesOrderReturn, R.id).invoice_id
    assert cid is not None
    # Then 4
    C = rr(db, AccountInvoice, cid)
    assert C.invoice_type == "payable"
    assert C.invoice_status == "confirmed"
    assert C.account_id == s.A1.id
    assert C.order_type == "sales_order"
    assert C.order_id == S.id
    assert C.allow_payments is True
    # Then 5
    C = rr(db, AccountInvoice, cid)
    assert C.description == f"Return credit note for SO-{s.TAG}-1 (SR-{s.TAG}-1)"
    assert C.notes == "Broken leg"
    # Then 6
    assert "confirmed" in itypes(db, cid)
    # Then 7
    assert len(EV(db, S.id)) == 0


# =========================================================================== #
# SalesService.start_return
# =========================================================================== #


def _ret_order(db, s, completed=False, **so_but):
    S = so(db, s, "1", finalized=True, completed=completed, **so_but)
    V = inv(db, s, S, confirmed=True, linked=True)
    return S, V


def _returns_of(db, S):
    return rows_where(db, SalesOrderReturn, SalesOrderReturn.sales_order_id == S.id)


def test_ss_rs_01__refund_return_created_committed(db, s):
    """SS-RS-01 — a refund return is created with its line, committed and returned re-read.
    Rules: RS1, RS5, RS8; TC1, TC2; N5."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.sales_order_id == S.id
    rid = result.id
    # Then 3
    db.rollback()
    r = rr(db, SalesOrderReturn, rid)
    assert r.status == "pending"
    assert r.return_type == "refund"
    assert r.reason == "Broken"
    assert r.created_by == s.U2.id
    assert r.workspace_id == s.W1.id
    assert r.return_number.startswith("SR-")
    # Then 4
    lines = rows_where(db, SalesOrderReturnItem, SalesOrderReturnItem.return_id == rid)
    assert len(lines) == 1
    assert lines[0].so_item_id == L1.id
    assert lines[0].quantity_returned == D("1.00")
    assert lines[0].workspace_id == s.W1.id
    # Then 5
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_delivered == D("4.00")
    assert line.quantity_returned == D("0.00")
    # Then 6
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 7
    assert notes(db) == []


def test_ss_rs_02__credit_note_lines(db, s):
    """SS-RS-02 — the credit note: confirmed payable, linked, one line per return line.
    Rules: RS6, RC1, RC2, RC3, RC4."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, free="Ribbon", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("0.25"), line_total=D("0.25"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00"), (L2, "0.50")))
    rid, rnum = result.id, result.return_number
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    C = rr(db, AccountInvoice, cid)
    assert C.invoice_type == "payable"
    assert C.invoice_status == "confirmed"
    assert C.account_id == s.A1.id
    assert C.order_id == S.id
    assert C.allow_payments is True
    # Then 2
    assert C.description == f"Return credit note for SO-{s.TAG}-1 ({rnum})"
    assert C.notes == "Broken"
    # Then 3
    assert sorted(x.line_number for x in LINES(db, cid)) == [1, 2]
    # Then 4
    x = line_for(db, cid, L1.id)
    assert x.description == "Chair"
    assert x.item_id == s.I1.id
    assert x.source_order_item_id == L1.id
    assert x.source_order_item_type == "so_item"
    assert x.quantity == D("1.00")
    assert x.unit == "pcs"
    assert x.unit_price == D("3000.00")
    assert x.line_subtotal == D("3000.00")
    # Then 5
    x = line_for(db, cid, L2.id)
    assert x.description == "Ribbon"
    assert x.item_id is None
    assert x.unit is None
    assert x.quantity == D("0.50")
    assert x.line_subtotal == D("0.13")
    # Then 6
    assert rr(db, AccountInvoice, cid).invoice_amount == D("3000.13")
    # Then 7
    assert "confirmed" in itypes(db, cid)


def test_ss_rs_03__credit_note_lines_half_up(db, s):
    """SS-RS-03 — each credit-note line is rounded half up and the amount is their sum.
    Rules: RC3; HR-15."""
    S, V = _ret_order(db, s)
    La = ln(db, s, S, free="Ribbon", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("0.25"), line_total=D("0.25"))
    Lb = ln(db, s, S, free="Tape", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("0.25"), line_total=D("0.25"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (La, "0.50"), (Lb, "0.50")))
    rid = result.id
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    lines = LINES(db, cid)
    assert len(lines) == 2
    assert all(x.line_subtotal == D("0.13") for x in lines)
    # Then 2
    assert rr(db, AccountInvoice, cid).invoice_amount == D("0.26")


@xfail(3196)
def test_ss_rs_04__credit_note_dated_utc_day(db, s):
    """SS-RS-04 — the credit note is dated with the UTC day.
    Rules: RC1 [BUG-3196]."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    # Then 1
    assert result.invoice_id is not None
    cid = result.invoice_id
    # Then 2
    db.rollback()
    assert rr(db, AccountInvoice, cid).invoice_date == UTCDAY


# [claude]
@xfail(627)
def test_ss_rs_05__no_invoice_amount_sent_for_credit_note(db, s):
    """SS-RS-05 — no `invoice_amount` is sent for the credit note.
    Rules: RC1 [BUG-627]."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    with patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    # Then 1
    assert ci.call_count == 1
    # Then 2
    assert not sent_invoice_amount(ci)


def test_ss_rs_06__one_return_started_event(db, s):
    """SS-RS-06 — one `return_started` event.
    Rules: RS7, RC5."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, quantity_ordered=D("2.00"), quantity_delivered=D("2.00"), line_total=D("6000.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00"), (L2, "2.00")))
    rid, rnum, cid = result.id, result.return_number, result.invoice_id
    # Then 1
    db.rollback()
    assert types(db, S) == ["return_started"]
    # Then 2
    e = EV(db, S)[0]
    assert e.description == f"Return {rnum} started — refund (3.00 unit(s) across 2 item(s))"
    assert e.performed_by == s.U2.id
    # Then 3
    assert e.metadata_json == {"return_id": rid, "invoice_id": cid, "return_type": "refund"}


def test_ss_rs_07__nothing_delivered_400(db, s):
    """SS-RS-07 — nothing delivered yet: 400, nothing written, extra row gone.
    Rules: RS2; TC3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "No items have been delivered or fulfilled yet — nothing to return"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_rs_08__delivered_w2_line_does_not_count(db, s):
    """SS-RS-08 — a delivered W2 line under the order does not count as delivered.
    Rules: RS2; HR-16."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, quantity_delivered=D("0.00"))
    ln(db, s, S, workspace_id=s.W2.id)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "No items have been delivered or fulfilled yet — nothing to return"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_rs_09__return_manager_refusal_passes(db, s):
    """SS-RS-09 — the return manager's refusal passes and nothing is written.
    Rules: RS3."""
    S = so(db, s, "1", finalized=True)
    ln(db, s, S)
    S2 = so(db, s, "2", finalized=True)
    L2 = ln(db, s, S2)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L2, "1.00")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Item {L2.id} does not belong to this sales order"
    # Then 3
    assert counts(db) == cp.counts


@xfail(2790)
def test_ss_rs_10__completed_order_stays_completed(db, s):
    """SS-RS-10 — a return on a completed order keeps it completed.
    Rules: RS4 [BUG-2790]."""
    S, V = _ret_order(db, s, completed=True)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("replace", (L1, "1.00")))
    # Then 1
    assert result.status == "pending"
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.order_completed is True
    assert row.completed_at == T0
    assert row.completed_by == s.U1.id
    # Then 3
    assert "order_reopened" not in types(db, S)
    # Then 4
    assert HOR(db, s, S) is True


def test_ss_rs_11__not_completed_order_unchanged(db, s):
    """SS-RS-11 — a return on an order that is not completed leaves its completion alone.
    Rules: RS4, RS8."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    # Then 1
    assert result.status == "pending"
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.order_completed is False
    assert row.completed_at is None


def test_ss_rs_12__replace_return_same_credit_note(db, s):
    """SS-RS-12 — a `replace` return gets the same confirmed payable credit note.
    Rules: RS9, RC1, RC4."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("replace", (L1, "1.00")))
    # Then 1
    assert result.return_type == "replace"
    cid = result.invoice_id
    # Then 2
    db.rollback()
    C = rr(db, AccountInvoice, cid)
    assert C.invoice_type == "payable"
    assert C.invoice_status == "confirmed"
    assert C.payment_status == "unpaid"
    assert C.invoice_amount == D("3000.00")
    # Then 3
    assert PAYS(db, cid) == []


def test_ss_rs_13__invoices_not_allowed_403(db, s):
    """SS-RS-13 — invoices not allowed for the account: 403, the whole start undone.
    Rules: RC1; TC3."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    s.A1.allow_invoices = False
    db.flush()
    cp = SimpleNamespace(counts=counts(db))
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 3
    assert X not in db
    # Then 4
    assert len(_returns_of(db, S)) == 0
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_rs_14__deleted_account_400(db, s):
    """SS-RS-14 — a deleted account: 400, nothing written.
    Rules: RC1."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    s.A1.is_deleted = True
    db.flush()
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot create invoice for deleted account"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_rs_15__inactive_account_400(db, s):
    """SS-RS-15 — an inactive account: 400, nothing written.
    Rules: RC1."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    s.A1.is_active = False
    db.flush()
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot create invoice for inactive account"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_rs_16__foreign_account_refused_untouched(db, s):
    """SS-RS-16 — the order's account is another workspace's: refused, nothing written, the W2 account untouched (today and after the fix).
    Rules: RC1, RC1a; HR-16."""
    S, V = _ret_order(db, s, account_id=s.A9.id)
    L1 = ln(db, s, S)
    cp = commit_point(db)
    before_a, before_l = snap(db, s.A9), snap(db, L1)
    # Then 1
    with pytest.raises(HTTPException):
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    # Then 2
    assert counts(db) == cp.counts
    # Then 3
    assert snap(db, s.A9) == before_a
    assert snap(db, L1) == before_l


@xfail(3197)
def test_ss_rs_17__unknown_order_404(db, s):
    """SS-RS-17 — an unknown order: 404.
    Rules: RS1, G1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (1, "1.00")))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


def test_ss_rs_18__failing_commit_no_return(db, s):
    """SS-RS-18 — a failing commit leaves no return and no credit note.
    Rules: RS7; TC4."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert counts(db) == cp.counts


@xfail(3218)
def test_ss_rs_19__w2_account_422_no_id(db, s):
    """SS-RS-19 — the order's account is W2's: 422 with no id.
    Rules: RC1a [BUG-3218]; HR-16."""
    S, V = _ret_order(db, s, account_id=s.A9.id)
    L1 = ln(db, s, S)
    cp = commit_point(db)
    before = snap(db, s.A9)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00")))
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCTCN
    # Then 3
    assert str(s.A9.id) not in exc.value.detail
    # Then 4
    assert X not in db
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    assert snap(db, s.A9) == before
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3218)
def test_ss_rs_20__w0_account_same_422(db, s):
    """SS-RS-20 — the order's account is W0's: the same 422.
    Rules: RC1a [BUG-3218]; HR-16."""
    S, V = _ret_order(db, s, account_id=s.A0.id)
    L1 = ln(db, s, S)
    cp = commit_point(db)
    before = snap(db, s.A0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("replace", (L1, "1.00")))
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOACCTCN
    # Then 3
    assert counts(db) == cp.counts
    # Then 4
    assert snap(db, s.A0) == before


def test_ss_rs_21__event_total_sum_of_sent_quantities(db, s):
    """SS-RS-21 — the event total is the sum of the sent quantities (1.5 + 1.5 → 3.0).
    Rules: RS7."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, quantity_ordered=D("2.00"), quantity_delivered=D("2.00"), line_total=D("6000.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.5"), (L2, "1.5")))
    rnum = result.return_number
    # Then 1
    db.rollback()
    assert types(db, S) == ["return_started"]
    # Then 2
    assert EV(db, S)[0].description == f"Return {rnum} started — refund (3.0 unit(s) across 2 item(s))"


def test_ss_rs_22__whole_quantity_prints_without_decimals(db, s):
    """SS-RS-22 — a whole sent quantity prints without decimals (3 → 3).
    Rules: RS7."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("replace", (L1, "3")))
    rnum = result.return_number
    # Then 1
    db.rollback()
    assert ev_of(db, S, "return_started").description == f"Return {rnum} started — replace (3 unit(s) across 1 item(s))"


@xfail(2425)
def test_ss_rs_23__credit_note_lines_in_return_line_id_order(db, s):
    """SS-RS-23 — credit-note lines are numbered in return-line id order.
    Rules: RC3 [BUG-2425]."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, free="Ribbon", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("0.25"), line_total=D("0.25"))
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00"), (L2, "0.50")))
    rid = result.id
    # Then 1
    assert rec.id_order("sales_order_return_items")
    # Then 2
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    assert [(x.line_number, x.source_order_item_id) for x in LINES(db, cid)] == [(1, L1.id), (2, L2.id)]


def test_ss_rs_24__zero_priced_line_zero_credit_line(db, s):
    """SS-RS-24 — a return line priced 0.00 gets a 0.00 credit-note line, not 1.00.
    Rules: RC3."""
    S, V = _ret_order(db, s)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, free="Sample", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("0.00"), line_total=D("0.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L1, "1.00"), (L2, "1.00")))
    rid = result.id
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    x = line_for(db, cid, L2.id)
    assert x.description == "Sample"
    assert x.quantity == D("1.00")
    assert x.unit_price == D("0.00")
    assert x.line_subtotal == D("0.00")
    # Then 2
    x = line_for(db, cid, L1.id)
    assert x.unit_price == D("3000.00")
    assert x.line_subtotal == D("3000.00")
    # Then 3
    c = rr(db, AccountInvoice, cid)
    assert c.invoice_amount == D("3000.00")
    assert c.invoice_status == "confirmed"


def test_ss_rs_25__empty_item_name_falls_back_to_item_id(db, s):
    """SS-RS-25 — a catalog item with an empty name and no line description: the credit-note line reads `Item <item_id>`.
    Rules: RC3."""
    I3 = _add(db, Item(workspace_id=s.W1.id, name="", name_normalized="", unit="pcs", is_active=True))
    S, V = _ret_order(db, s)
    L2 = ln(db, s, S, item_id=I3.id, quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("10.00"), line_total=D("10.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L2, "1.00")))
    rid = result.id
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    assert len(LINES(db, cid)) == 1
    # Then 2
    x = LINES(db, cid)[0]
    assert x.description == f"Item {I3.id}"
    assert x.item_id == I3.id
    assert x.source_order_item_id == L2.id
    assert x.unit == "pcs"
    assert x.line_subtotal == D("10.00")


@xfail(3220)
def test_ss_rs_26__empty_free_text_credit_line_named_line_1(db, s):
    """SS-RS-26 — a free-text line with an empty description: the credit-note line reads `Line 1`, never "Item None".
    Rules: RC3, RC3a [BUG-3220]."""
    S, V = _ret_order(db, s)
    L2 = ln(db, s, S, free="", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("10.00"), line_total=D("10.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (L2, "1.00")))
    rid = result.id
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    assert len(LINES(db, cid)) == 1
    # Then 2
    x = LINES(db, cid)[0]
    assert x.line_number == 1
    assert x.description == "Line 1"
    assert "None" not in x.description
    assert x.item_id is None
    assert x.source_order_item_id == L2.id
    assert x.line_subtotal == D("10.00")


@xfail(3220)
def test_ss_rs_27__free_text_names_trimmed_blank_is_empty(db, s):
    """SS-RS-27 — free-text names are trimmed, and a spaces-only name counts as empty (`Line <line_number>`).
    Rules: RC3, RC3a [BUG-3220]."""
    S, V = _ret_order(db, s)
    La = ln(db, s, S, free="  Crate  ", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("10.00"), line_total=D("10.00"))
    Lb = ln(db, s, S, free="   ", quantity_ordered=D("1.00"), quantity_delivered=D("1.00"), unit_price=D("20.00"), line_total=D("20.00"))
    commit_point(db)
    result = svc.start_return(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, data=ret_create("refund", (La, "1.00"), (Lb, "1.00")))
    rid = result.id
    # Then 1
    db.rollback()
    cid = rr(db, SalesOrderReturn, rid).invoice_id
    assert len(LINES(db, cid)) == 2
    # Then 2
    assert line_for(db, cid, La.id).description == "Crate"
    # Then 3
    B = line_for(db, cid, Lb.id)
    assert B.description == f"Line {B.line_number}"
    assert B.item_id is None


# =========================================================================== #
# SalesService.complete_return
# =========================================================================== #


def _complete(db, s, S, R):
    return svc.complete_return(db, order_id=S.id, return_id=R.id, workspace_id=s.W1.id, user_id=s.U2.id)


def test_ss_rk_01__refund_return_completed(db, s):
    """SS-RK-01 — a refund return is completed: quantities, stock back, stamps; committed.
    Rules: RK1, RK4, RK5, RK7; TC1, TC2."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", refund=True, of=CN)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == R1.id
    # Then 3
    db.rollback()
    r = rr(db, SalesOrderReturn, R1.id)
    assert r.status == "completed"
    assert r.completed_at == NOW
    assert r.completed_by == s.U2.id
    # Then 4
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_returned == D("1.00")
    assert line.quantity_delivered == D("3.00")
    assert line.quantity_refunded == D("1.00")
    # Then 5
    assert rr(db, Product, s.P1.id).qty == 101
    # Then 6
    led = NEWLED(db, cp)
    assert len(led) == 1
    assert led[0].transaction_type == "return"
    assert led[0].quantity == 1
    assert led[0].qty_before == 100
    assert led[0].qty_after == 101
    assert led[0].performed_by == s.U2.id


def test_ss_rk_02__replace_return_delivered_down_refunded_not(db, s):
    """SS-RK-02 — a replace return: delivered goes down, refunded does not.
    Rules: RK4, RK10."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", of=CN)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    result = _complete(db, s, S, R1)
    # Then 1
    assert result.id == R1.id
    # Then 2
    db.rollback()
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_returned == D("1.00")
    assert line.quantity_delivered == D("3.00")
    assert line.quantity_refunded == D("0.00")
    # Then 3
    assert rr(db, Product, s.P1.id).qty == 101
    # Then 4
    c = rr(db, AccountInvoice, CN.id)
    assert c.invoice_status == "confirmed"
    assert c.paid_amount == D("0.00")


@xfail(2791)
def test_ss_rk_03__directly_fulfilled_catalog_line_no_stock_back(db, s):
    """SS-RK-03 — a directly fulfilled catalog line puts no stock back.
    Rules: RK5 [BUG-2791]."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, requires_delivery=False)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    result = _complete(db, s, S, R1)
    # Then 1
    assert result.status == "completed"
    # Then 2
    db.rollback()
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 3
    assert NEWLED(db, cp) == []


def test_ss_rk_04__directly_fulfilled_line_quantities_move(db, s):
    """SS-RK-04 — a directly fulfilled catalog line still moves its quantities (today and after the fix).
    Rules: RK4, RK5."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, requires_delivery=False)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    result = _complete(db, s, S, R1)
    # Then 1
    assert result.status == "completed"
    # Then 2
    db.rollback()
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_returned == D("1.00")
    assert line.quantity_delivered == D("3.00")
    assert line.quantity_refunded == D("1.00")


def test_ss_rk_05__free_text_line_quantities_only(db, s):
    """SS-RK-05 — a free-text line moves quantities only.
    Rules: RK4, RK5."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, free="Crate")
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    result = _complete(db, s, S, R1)
    # Then 1
    assert result.status == "completed"
    # Then 2
    db.rollback()
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_delivered == D("3.00")
    assert line.quantity_refunded == D("1.00")
    # Then 3
    assert NEWLED(db, cp) == []
    assert rr(db, Product, s.P1.id).qty == 100


@xfail(3202)
def test_ss_rk_06__ledger_note_names_order_once(db, s):
    """SS-RK-06 — the ledger note names the order number once.
    Rules: RK5a [BUG-3202]."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert len(NEWLED(db, cp)) == 1
    # Then 2
    assert NEWLED(db, cp)[0].notes == f"Return SR-{s.TAG}-1 for SO-{s.TAG}-1"


@xfail(3200)
def test_ss_rk_07__completion_stamps_updated_by(db, s):
    """SS-RK-07 — completion stamps `updated_by`.
    Rules: RK7 [BUG-3200]."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, free="Crate")
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrderReturn, R1.id).status == "completed"
    # Then 2
    assert rr(db, SalesOrderReturn, R1.id).updated_by == s.U2.id


def test_ss_rk_08__one_return_completed_event_refund(db, s):
    """SS-RK-08 — one `return_completed` event for a refund return.
    Rules: RK8."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    L2 = ln(db, s, S, free="Crate", quantity_ordered=D("2.00"), quantity_delivered=D("2.00"), unit_price=D("100.00"), line_total=D("200.00"))
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    rl(db, R1, L2, "2.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert types(db, S) == ["return_completed"]
    # Then 2
    e = EV(db, S)[0]
    assert e.description == f"Return SR-{s.TAG}-1 completed — refund (3.00 unit(s), 1 inventory line(s) posted)"
    assert e.performed_by == s.U2.id
    # Then 3
    assert e.metadata_json == {"return_id": R1.id, "return_type": "refund"}


def test_ss_rk_09__replace_event_adds_redeliver(db, s):
    """SS-RK-09 — a replace return's event adds "redeliver to close the gap".
    Rules: RK8."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert types(db, S) == ["return_completed"]
    # Then 2
    assert EV(db, S)[0].description == f"Return SR-{s.TAG}-1 completed — replace (1.00 unit(s), 1 inventory line(s) posted) — redeliver to close the gap"


@xfail(3210)
def test_ss_rk_10__replace_gap_not_fully_delivered(db, s):
    """SS-RK-10 — a replace return with a gap makes the order not fully delivered.
    Rules: RK9 [BUG-3210]."""
    S = so(db, s, "1", finalized=True, is_fully_delivered=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrderItem, L1.id).quantity_delivered == D("3.00")
    # Then 2
    assert rr(db, SalesOrder, S.id).is_fully_delivered is False


def test_ss_rk_11__refund_keeps_fully_delivered(db, s):
    """SS-RK-11 — a refund return keeps "fully delivered".
    Rules: RK9."""
    S = so(db, s, "1", finalized=True, is_fully_delivered=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrder, S.id).is_fully_delivered is True


def test_ss_rk_12__completed_return_not_again(db, s):
    """SS-RK-12 — a completed return cannot be completed again.
    Rules: RK3; TC3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    R1 = ret(db, s, S, "1", done=True)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    before = snap(db, L1)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            _complete(db, s, S, R1)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a pending return can be completed"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    assert snap(db, L1) == before
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_rk_13__voided_return_not_completed(db, s):
    """SS-RK-13 — a voided return cannot be completed.
    Rules: RK3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1", voided=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    before = snap(db, L1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, S, R1)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a pending return can be completed"
    # Then 3
    assert snap(db, L1) == before


def test_ss_rk_14__return_of_other_order_404(db, s):
    """SS-RK-14 — a return of another W1 order: 404.
    Rules: RK2."""
    S = so(db, s, "1", finalized=True)
    S2 = so(db, s, "2", finalized=True)
    L2 = ln(db, s, S2)
    R2 = ret(db, s, S2, "2")
    rl(db, R2, L2, "1.00")
    commit_point(db)
    before = snap(db, R2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, S, R2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == RNF(R2.id)
    # Then 3
    assert snap(db, R2) == before


def test_ss_rk_15__w2_return_row_404(db, s):
    """SS-RK-15 — a W2 return row under the order: 404.
    Rules: RK2; HR-16."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R9 = ret(db, s, S, "9", ws="2")
    rl(db, R9, L1, "1.00")
    commit_point(db)
    before = snap(db, L1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, S, R9)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == RNF(R9.id)
    # Then 3
    assert snap(db, L1) == before


@xfail(2764)
def test_ss_rk_16__return_read_with_row_lock(db, s):
    """SS-RK-16 — the return is read with a row lock.
    Rules: RK2 [BUG-2764]; HR-10."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, free="Crate")
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    sid, rid = S.id, R1.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.complete_return(db, order_id=sid, return_id=rid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == rid
    # Then 2
    assert rec.row_lock("sales_order_returns")


def test_ss_rk_17__fractional_catalog_quantity_400(db, s):
    """SS-RK-17 — a fractional catalog quantity: 400, the whole completion undone.
    Rules: RK6; TC3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "0.50")
    cp = commit_point(db)
    before_l, before_r = snap(db, L1), snap(db, R1)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, S, R1)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Return line has a fractional quantity; stock requires whole units"
    # Then 3
    assert X not in db
    # Then 4
    assert snap(db, L1) == before_l
    # Then 5
    assert snap(db, R1) == before_r
    # Then 6
    assert counts(db) == cp.counts
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_rk_18__foreign_line_skipped_but_counted(db, s):
    """SS-RK-18 — a return line naming a line that is not this order's (W2) is skipped but counted.
    Rules: RK4, RK8."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    S9 = so(db, s, "9", ws="2")
    L9 = ln(db, s, S9)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    rl(db, R1, L9, "1.00", workspace_id=s.W1.id)
    commit_point(db)
    before = snap(db, L9)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    assert rr(db, SalesOrderItem, L1.id).quantity_delivered == D("3.00")
    # Then 2
    assert snap(db, L9) == before
    # Then 3
    assert rr(db, Product, s.P1.id).qty == 101
    # Then 4
    assert ev_of(db, S, "return_completed").description == f"Return SR-{s.TAG}-1 completed — refund (2.00 unit(s), 1 inventory line(s) posted)"


def test_ss_rk_19__last_pending_return_shows_completed(db, s):
    """SS-RK-19 — the last pending return completed: a completed order shows "completed" again.
    Rules: RK10, RK11."""
    S = so(db, s, "1", finalized=True, completed=True)
    L1 = ln(db, s, S, free="Crate")
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _complete(db, s, S, R1)
    # Then 1
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.order_completed is True
    assert row.completed_at == T0
    # Then 2
    assert HOR(db, s, S) is False


def test_ss_rk_20__failing_commit_return_pending(db, s):
    """SS-RK-20 — a failing commit leaves the return pending and the stock untouched.
    Rules: RK10; TC4."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1", refund=True)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _complete(db, s, S, R1)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrderReturn, R1.id).status == "pending"
    # Then 4
    assert rr(db, Product, s.P1.id).qty == 100


@xfail(3197)
def test_ss_rk_21__unknown_order_404(db, s):
    """SS-RK-21 — an unknown order: 404.
    Rules: RK1, G1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.complete_return(db, order_id=MISSING, return_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


def test_ss_rk_22__second_refund_adds_to_quantities(db, s):
    """SS-RK-22 — a second refund return adds to quantities that are already non-zero.
    Rules: RK4."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, free="Crate", quantity_delivered=D("3.00"), quantity_returned=D("1.00"), quantity_refunded=D("1.00"))
    CN0 = cn(db, s, S, "3000.00")
    R0 = ret(db, s, S, "0", refund=True, done=True, of=CN0)
    rl(db, R0, L1, "1.00")
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", refund=True, of=CN)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    result = _complete(db, s, S, R1)
    # Then 1
    assert result.status == "completed"
    # Then 2
    db.rollback()
    line = rr(db, SalesOrderItem, L1.id)
    assert line.quantity_returned == D("2.00")
    assert line.quantity_refunded == D("2.00")
    assert line.quantity_delivered == D("2.00")
    # Then 3
    assert NEWLED(db, cp) == []
    assert rr(db, Product, s.P1.id).qty == 100


# =========================================================================== #
# SalesService.void_return
# =========================================================================== #


def _void(db, s, S, R, note):
    return svc.void_return(db, order_id=S.id, return_id=R.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note=note)


def test_ss_rv_01__pending_return_cancelled(db, s):
    """SS-RV-01 — a pending return is cancelled with its credit note voided; committed.
    Rules: RV1, RV3, RV4, RV5, RV7; TC1, TC2."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", of=CN)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    before = snap(db, L1)
    result = svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Customer kept it")
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == R1.id
    # Then 3
    db.rollback()
    r = rr(db, SalesOrderReturn, R1.id)
    assert r.status == "voided"
    assert r.paid is False
    # Then 4
    c = rr(db, AccountInvoice, CN.id)
    assert c.invoice_status == "voided"
    assert c.paid_amount == D("0.00")
    # Then 5
    assert types(db, S) == ["return_voided"]
    # Then 6
    e = EV(db, S)[0]
    assert e.description == f"Return SR-{s.TAG}-1 cancelled — Customer kept it"
    assert e.metadata_json == {"return_id": R1.id, "void_note": "Customer kept it"}
    assert e.performed_by == s.U2.id
    # Then 7
    assert snap(db, L1) == before
    assert rr(db, Product, s.P1.id).qty == 100
    # Then 8
    assert HOR(db, s, S) is False


def test_ss_rv_02__active_refund_payment_voided(db, s):
    """SS-RV-02 — an active refund payment on the credit note is voided with it.
    Rules: RV3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00", paid_amount=D("1000.00"), payment_status="partial")
    P = pay(db, s, CN, "1000.00")
    R1 = ret(db, s, S, "1", of=CN)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _void(db, s, S, R1, "Customer kept it")
    # Then 1
    db.rollback()
    assert rr(db, InvoicePayment, P.id).is_voided is True
    # Then 2
    c = rr(db, AccountInvoice, CN.id)
    assert c.invoice_status == "voided"
    assert c.paid_amount == D("0.00")
    # Then 3
    r = rr(db, SalesOrderReturn, R1.id)
    assert r.status == "voided"
    assert r.paid is False


@xfail(3200)
def test_ss_rv_03__cancel_stamps_updated_by(db, s):
    """SS-RV-03 — cancelling stamps `updated_by`.
    Rules: RV4 [BUG-3200]."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    _void(db, s, S, R1, "Customer kept it")
    # Then 1
    db.rollback()
    assert rr(db, SalesOrderReturn, R1.id).status == "voided"
    # Then 2
    assert rr(db, SalesOrderReturn, R1.id).updated_by == s.U2.id


def test_ss_rv_04__completed_return_not_cancelled(db, s):
    """SS-RV-04 — a completed return cannot be cancelled.
    Rules: RV2; TC3."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S, quantity_delivered=D("3.00"), quantity_returned=D("1.00"))
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", done=True, of=CN)
    rl(db, R1, L1, "1.00")
    cp = commit_point(db)
    before = snap(db, CN)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            _void(db, s, S, R1, "x")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a pending return can be cancelled"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, CN) == before
    # Then 6
    assert counts(db) == cp.counts
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_rv_05__voided_return_not_again(db, s):
    """SS-RV-05 — a voided return cannot be cancelled again.
    Rules: RV2."""
    S = so(db, s, "1", finalized=True)
    R1 = ret(db, s, S, "1", voided=True)
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, S, R1, "x")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Only a pending return can be cancelled"
    # Then 3
    assert counts(db) == cp.counts


@xfail(3211)
def test_ss_rv_06__already_voided_note_does_not_stop(db, s):
    """SS-RV-06 — a credit note already voided does not stop the cancel.
    Rules: RV3a [BUG-3211]."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN = cn(db, s, S, "3000.00", voided_inv=True)
    R1 = ret(db, s, S, "1", of=CN)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    # Then 1
    result = _void(db, s, S, R1, "Old data")
    assert result.status == "voided"
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderReturn, R1.id).status == "voided"
    # Then 3
    c = rr(db, AccountInvoice, CN.id)
    assert c.invoice_status == "voided"
    assert c.void_note == "dup"


@xfail(3211)
def test_ss_rv_07__w2_note_does_not_stop_untouched(db, s):
    """SS-RV-07 — a W2 credit note linked to the return does not stop the cancel and is not touched.
    Rules: RV3a [BUG-3211]; HR-16."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN9 = cn(db, s, S, "3000.00", ws="2")
    R1 = ret(db, s, S, "1", of=CN9)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    before = snap(db, CN9)
    # Then 1
    result = _void(db, s, S, R1, "Old data")
    assert result.status == "voided"
    # Then 2
    db.rollback()
    assert snap(db, CN9) == before


def test_ss_rv_08__w2_note_never_changed(db, s):
    """SS-RV-08 — a W2 credit note is never changed by the cancel (today and after the fix).
    Rules: RV3a; HR-16."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    CN9 = cn(db, s, S, "3000.00", ws="2")
    R1 = ret(db, s, S, "1", of=CN9)
    rl(db, R1, L1, "1.00")
    commit_point(db)
    before = snap(db, CN9)
    try:
        _void(db, s, S, R1, "Old data")
    except HTTPException:
        pass
    # Then 1
    db.rollback()
    assert snap(db, CN9) == before
    # Then 2
    assert count_where(db, InvoicePayment, InvoicePayment.invoice_id == CN9.id) == 0


def test_ss_rv_09__return_without_credit_note_cancelled(db, s):
    """SS-RV-09 — a return without a credit note is cancelled.
    Rules: RV3, RV4."""
    S = so(db, s, "1", finalized=True)
    L1 = ln(db, s, S)
    R1 = ret(db, s, S, "1")
    rl(db, R1, L1, "1.00")
    commit_point(db)
    result = _void(db, s, S, R1, "x")
    # Then 1
    assert result.status == "voided"
    # Then 2
    db.rollback()
    r = rr(db, SalesOrderReturn, R1.id)
    assert r.status == "voided"
    assert r.paid is False


@xfail(2764)
def test_ss_rv_10__return_read_with_row_lock(db, s):
    """SS-RV-10 — the return is read with a row lock.
    Rules: RV1 [BUG-2764]; HR-10."""
    S = so(db, s, "1", finalized=True)
    R1 = ret(db, s, S, "1")
    commit_point(db)
    sid, rid = S.id, R1.id
    expunge_all(db, s)
    with Recorder(db) as rec:
        result = svc.void_return(db, order_id=sid, return_id=rid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="x")
    # Then 1
    assert result.id == rid
    # Then 2
    assert rec.row_lock("sales_order_returns")


def test_ss_rv_11__return_of_other_order_404(db, s):
    """SS-RV-11 — a return of another order: 404.
    Rules: RV1."""
    S = so(db, s, "1", finalized=True)
    S2 = so(db, s, "2", finalized=True)
    R2 = ret(db, s, S2, "2")
    commit_point(db)
    before = snap(db, R2)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, S, R2, "x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == RNF(R2.id)
    # Then 3
    assert X not in db
    # Then 4
    assert snap(db, R2) == before
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(3203)
def test_ss_rv_12__spaces_only_note_refused():
    """SS-RV-12 — a spaces-only void note is refused by the schema.
    Rules: RV6 [BUG-3203]."""
    # Then 1
    with pytest.raises(ValidationError):
        SalesOrderReturnVoidRequest(void_note="   ")


@xfail(3203)
def test_ss_rv_13__note_stored_trimmed():
    """SS-RV-13 — a void note is stored trimmed.
    Rules: RV6 [BUG-3203]."""
    r = SalesOrderReturnVoidRequest(void_note="  Wrong size  ")
    # Then 1
    assert r.void_note == "Wrong size"


def test_ss_rv_14__one_char_ok_empty_refused():
    """SS-RV-14 — one character is enough; empty is refused.
    Rules: RV6."""
    r = SalesOrderReturnVoidRequest(void_note="x")
    # Then 1
    assert r.void_note == "x"
    # Then 2
    with pytest.raises(ValidationError):
        SalesOrderReturnVoidRequest(void_note="")


def test_ss_rv_15__failing_commit_return_pending(db, s):
    """SS-RV-15 — a failing commit leaves the return pending and its credit note confirmed.
    Rules: RV5; TC4."""
    S = so(db, s, "1", finalized=True)
    CN = cn(db, s, S, "3000.00")
    R1 = ret(db, s, S, "1", of=CN)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _void(db, s, S, R1, "x")
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrderReturn, R1.id).status == "pending"
    # Then 4
    assert rr(db, AccountInvoice, CN.id).invoice_status == "confirmed"


# =========================================================================== #
# SalesService.list_returns / SalesService.get_return
# =========================================================================== #


def test_ss_rl_01__returns_newest_first(db, s):
    """SS-RL-01 — the order's returns, newest first; W2 rows left out; no commit or rollback.
    Rules: RL1; TC6."""
    S = so(db, s, "1")
    Ra = ret(db, s, S, "1", created_at=T1)
    Rb = ret(db, s, S, "2", voided=True, created_at=T2)
    ret(db, s, S, "9", ws="2", created_at=T2)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.list_returns(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert [r.id for r in result] == [Rb.id, Ra.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


@xfail(3197)
def test_ss_rl_02__unknown_order_404(db, s):
    """SS-RL-02 — an unknown order: 404.
    Rules: RL1, G1 [BUG-3197]."""
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.list_returns(db, order_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(MISSING)


def test_ss_rg_01__any_status_returned(db, s):
    """SS-RG-01 — any status is returned; no commit or rollback.
    Rules: RG1; TC6."""
    S = so(db, s, "1")
    R1 = ret(db, s, S, "1", voided=True)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.get_return(db, order_id=S.id, return_id=R1.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == R1.id
    assert result.status == "voided"
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


def test_ss_rg_02__return_of_other_order_404_no_rollback(db, s):
    """SS-RG-02 — a return of another order: 404, no rollback.
    Rules: RG1; TC6."""
    S = so(db, s, "1")
    S2 = so(db, s, "2")
    R2 = ret(db, s, S2, "2")
    commit_point(db)
    X_ID = mk_x(db).id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_return(db, order_id=S.id, return_id=R2.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == RNF(R2.id)
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


# =========================================================================== #
# SalesService.mark_order_complete
# =========================================================================== #


def _complete_ready(db, s, completed=False):
    S = so(db, s, "1", finalized=True, completed=completed, is_fully_delivered=True)
    inv(db, s, S, confirmed=True, linked=True)
    ln(db, s, S)
    return S


def test_ss_mc_01__order_completed_committed(db, s):
    """SS-MC-01 — an order is completed, committed, with its payment status.
    Rules: MC1; TC1, TC2."""
    S = _complete_ready(db, s)
    commit_point(db)
    result = svc.mark_order_complete(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == S.id
    assert result.invoice_payment_status == "unpaid"
    # Then 3
    db.rollback()
    assert rr(db, SalesOrder, S.id).order_completed is True
    # Then 4
    assert "order_completed" in types(db, S)
    # Then 5
    assert notes(db) == []


def test_ss_mc_02__already_completed_one_commit(db, s):
    """SS-MC-02 — an already completed order still goes through one commit.
    Rules: MC1."""
    S = _complete_ready(db, s, completed=True)
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.mark_order_complete(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == S.id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.completed_at == T0
    assert row.completed_by == s.U1.id


def test_ss_mc_03__manager_404_passes(db, s):
    """SS-MC-03 — the manager's 404 passes and the extra row is gone.
    Rules: MC1; TC3."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, S9)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.mark_order_complete(db, order_id=S9.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == NF(S9.id)
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert snap(db, S9) == before
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_mc_04__failing_commit_order_open(db, s):
    """SS-MC-04 — a failing commit leaves the order open.
    Rules: MC1; TC4."""
    S = _complete_ready(db, s)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.mark_order_complete(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrder, S.id).order_completed is False


# =========================================================================== #
# SalesService.set_section_confirm
# =========================================================================== #


def _confirm(db, s, S, section, confirmed):
    return svc.set_section_confirm(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, section=section, confirmed=confirmed)


def test_ss_sc_01__second_section_drafts_invoice(db, s):
    """SS-SC-01 — confirming the second section drafts the invoice; committed with payment status.
    Rules: SC1, SC2; Y4; TC1, TC2."""
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = svc.set_section_confirm(db, order_id=S.id, workspace_id=s.W1.id, user_id=s.U2.id, section="items", confirmed=True)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == S.id
    assert result.invoice_payment_status == "unpaid"
    # Then 3
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.items_confirmed is True
    assert row.invoice_id is not None
    assert row.is_invoiced is True
    # Then 4
    V = _inv_of(db, S)
    assert V.invoice_status == "draft"
    assert V.invoice_amount == D("12000.00")
    # Then 5
    assert "invoice_draft_created" in types(db, S)


def test_ss_sc_02__only_info_no_draft(db, s):
    """SS-SC-02 — confirming only order info makes no draft.
    Rules: SC2; Y2."""
    S = so(db, s, "1")
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = _confirm(db, s, S, "order_info", True)
    # Then 1
    assert result.id == S.id
    assert result.invoice_payment_status is None
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.order_info_confirmed is True
    assert row.invoice_id is None
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == S.id, AccountInvoice.order_type == "sales_order") == 0


def test_ss_sc_03__unconfirming_items_deletes_draft(db, s):
    """SS-SC-03 — unconfirming items deletes the draft.
    Rules: SC2; Y2, DD3."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    V = inv(db, s, S, linked=True)
    invl(db, s, V, 1, "12000.00")
    vid = V.id
    commit_point(db)
    result = _confirm(db, s, S, "items", False)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    row = rr(db, SalesOrder, S.id)
    assert row.items_confirmed is False
    assert row.invoice_id is None
    assert row.is_invoiced is False
    # Then 3
    assert rr(db, AccountInvoice, vid) is None
    # Then 4
    assert "invoice_draft_deleted" in types(db, S)


def test_ss_sc_04__no_flag_change_still_drafts(db, s):
    """SS-SC-04 — a confirm that changes no flag still runs the draft step.
    Rules: SC2."""
    S = so(db, s, "1", ready=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    result = _confirm(db, s, S, "items", True)
    # Then 1
    assert result.id == S.id
    # Then 2
    db.rollback()
    assert rr(db, SalesOrder, S.id).invoice_id is not None


def test_ss_sc_05__invoicing_disabled_confirm_undone(db, s):
    """SS-SC-05 — invoicing disabled: 422 and the confirm is undone.
    Rules: SC3; TC3."""
    s.A1.allow_invoices = False
    db.flush()
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            _confirm(db, s, S, "items", True)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == NOINV
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert rr(db, SalesOrder, S.id).items_confirmed is False
    # Then 6
    assert counts(db) == cp.counts
    # Then 7
    db.rollback()
    assert x_gone(db, X_ID)


@xfail(639)
def test_ss_sc_06__unconfirm_with_payment_history_400(db, s):
    """SS-SC-06 — unconfirming with a draft that has payment history: 400, everything kept.
    Rules: SC3; DD3 [BUG-639]."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    V = inv(db, s, S, paid_amount=D("100.00"), payment_status="partial", linked=True)
    pay(db, s, V, "100.00")
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _confirm(db, s, S, "items", False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == PAYHIST
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.items_confirmed is True
    assert row.invoice_id == V.id
    # Then 4
    assert counts(db) == cp.counts


def test_ss_sc_07__failing_commit_unconfirmed_no_draft(db, s):
    """SS-SC-07 — a failing commit leaves the section unconfirmed and no draft.
    Rules: SC1; TC4."""
    S = so(db, s, "1", order_info_confirmed=True)
    ln(db, s, S, quantity_delivered=D("0.00"))
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _confirm(db, s, S, "items", True)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.items_confirmed is False
    assert row.invoice_id is None


def test_ss_sc_08__payment_history_refused_rolled_back(db, s):
    """SS-SC-08 — unconfirming with a draft that has payment history is refused and rolled back; everything kept (today and after the fix).
    Rules: SC3; DD3; TC3 (holds before and after BUG-639)."""
    S = so(db, s, "1", ready=True, is_invoiced=True)
    V = inv(db, s, S, paid_amount=D("100.00"), payment_status="partial", linked=True)
    P = pay(db, s, V, "100.00")
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(Exception):
        _confirm(db, s, S, "items", False)
    # Then 2
    assert X not in db
    # Then 3
    row = rr(db, SalesOrder, S.id)
    assert row.items_confirmed is True
    assert row.invoice_id == V.id
    # Then 4
    assert rr(db, AccountInvoice, V.id) is not None
    assert db.get(InvoicePayment, P.id) is not None
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


# =========================================================================== #
# Approvers and events
# =========================================================================== #


def _approvers_of(db, S):
    return rows_where(db, SalesOrderApprover, SalesOrderApprover.sales_order_id == S.id)


def test_ss_al_01__list_approvers_no_commit(db, s):
    """SS-AL-01 — list_approvers returns the manager's rows; no commit or rollback.
    Rules: AL1; TC6."""
    S = so(db, s, "1")
    A_3 = appr(db, s, S, s.U3)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.list_approvers(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 1
    assert result[0][0].id == A_3.id
    assert result[0][1].id == s.U3.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


def test_ss_al_02__list_approvers_other_workspace_404(db, s):
    """SS-AL-02 — list_approvers on another workspace's order: the 404 passes, no rollback.
    Rules: AL1; TC6."""
    S9 = so(db, s, "9", ws="2")
    commit_point(db)
    X_ID = mk_x(db).id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.list_approvers(db, order_id=S9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert x_kept(db, X_ID)


def test_ss_as_01__one_of_one_met(db, s):
    """SS-AS-01 — approval_summary: one of one approved is met; no commit or rollback.
    Rules: AS1; TC6."""
    S = so(db, s, "1")
    appr(db, s, S, s.U3, approved=True)
    commit_point(db)
    with spies(db) as (cm, rb):
        result = svc.approval_summary(db, order=S)
    # Then 1
    assert result == (1, 1, True)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


def test_ss_as_02__one_of_two_not_met(db, s):
    """SS-AS-02 — approval_summary: one of two required is not met.
    Rules: AS1."""
    S = so(db, s, "1", required_approvals=2)
    appr(db, s, S, s.U1, approved=True)
    appr(db, s, S, s.U3)
    commit_point(db)
    result = svc.approval_summary(db, order=S)
    # Then 1
    assert result == (1, 2, False)


def test_ss_aa_01__add_approver_commits(db, s):
    """SS-AA-01 — add_approver adds and commits; the row is returned re-read.
    Rules: AA1; TC1, TC2."""
    S = so(db, s, "1")
    commit_point(db)
    result = svc.add_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.user_id == s.U3.id
    assert result.sales_order_id == S.id
    # Then 3
    db.rollback()
    aps = _approvers_of(db, S)
    assert len(aps) == 1
    assert aps[0].user_id == s.U3.id
    assert aps[0].approved is False
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == S.id) == 0


def test_ss_aa_02__duplicate_approver_409(db, s):
    """SS-AA-02 — add_approver: a duplicate gets the 409 and the extra row is gone.
    Rules: AA1; TC3."""
    S = so(db, s, "1")
    appr(db, s, S, s.U3)
    commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.add_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "User is already an approver for this order"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert len(_approvers_of(db, S)) == 1
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_aa_03__inactive_member_400(db, s):
    """SS-AA-03 — add_approver: an inactive member gets the 400.
    Rules: AA1."""
    S = so(db, s, "1")
    cp = commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_approver(db, order_id=S.id, user_id=s.U4.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 3
    assert counts(db) == cp.counts


def test_ss_aa_04__failing_commit_no_approver(db, s):
    """SS-AA-04 — add_approver: a failing commit leaves no approver.
    Rules: AA1; TC4."""
    S = so(db, s, "1")
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, assigned_by=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert len(_approvers_of(db, S)) == 0


def test_ss_ar_01__remove_approver_commits(db, s):
    """SS-AR-01 — remove_approver removes, commits and returns None.
    Rules: AR1; TC1."""
    S = so(db, s, "1")
    A_3 = appr(db, s, S, s.U3)
    commit_point(db)
    result = svc.remove_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderApprover, A_3.id) is None
    # Then 3
    assert notes(db) == []


def test_ss_ar_02__not_an_approver_404(db, s):
    """SS-AR-02 — remove_approver: not an approver gets the 404 and the extra row is gone.
    Rules: AR1; TC3."""
    S = so(db, s, "1")
    commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.remove_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_ar_03__failing_commit_keeps_approver(db, s):
    """SS-AR-03 — remove_approver: a failing commit keeps the approver.
    Rules: AR1; TC4."""
    S = so(db, s, "1")
    A_3 = appr(db, s, S, s.U3)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_approver(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrderApprover, A_3.id) is not None


def test_ss_ap_01__set_approval_commits(db, s):
    """SS-AP-01 — set_approval approves, commits and returns the row re-read; no notification, no invoice step.
    Rules: AP1; TC1, TC2; N5."""
    S = so(db, s, "1", ready=True)
    A_2 = appr(db, s, S, s.U2)
    commit_point(db)
    result = svc.set_approval(db, order_id=S.id, user_id=s.U2.id, workspace_id=s.W1.id, approved=True)
    # Then 1
    assert loaded(result)
    # Then 2
    db.rollback()
    assert rr(db, SalesOrderApprover, A_2.id).approved is True
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == S.id) == 0
    # Then 4
    assert notes(db) == []


def test_ss_ap_02__not_assigned_approver_403(db, s):
    """SS-AP-02 — set_approval: not an approver gets the 403 and the extra row is gone.
    Rules: AP1; TC3."""
    S = so(db, s, "1", ready=True)
    cp = commit_point(db)
    X = mk_x(db)
    X_ID = X.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.set_approval(db, order_id=S.id, user_id=s.U3.id, workspace_id=s.W1.id, approved=True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 3
    assert X not in db
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert counts(db) == cp.counts
    # Then 6
    db.rollback()
    assert x_gone(db, X_ID)


def test_ss_ap_03__failing_commit_approval_unset(db, s):
    """SS-AP-03 — set_approval: a failing commit keeps the approval unset.
    Rules: AP1; TC4."""
    S = so(db, s, "1", ready=True)
    A_2 = appr(db, s, S, s.U2)
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.set_approval(db, order_id=S.id, user_id=s.U2.id, workspace_id=s.W1.id, approved=True)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert rr(db, SalesOrderApprover, A_2.id).approved is False


def test_ss_ev_01__list_events_newest_first(db, s):
    """SS-EV-01 — list_events returns the order's events newest first; no commit or rollback.
    Rules: EV1; TC6."""
    S = so(db, s, "1")
    Ea = ev(db, s, S, T1)
    Eb = ev(db, s, S, T2)
    commit_point(db)
    X_ID = mk_x(db).id
    with spies(db) as (cm, rb):
        result = svc.list_events(db, order_id=S.id, workspace_id=s.W1.id)
    # Then 1
    assert [e.id for (e, p) in result] == [Eb.id, Ea.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x_kept(db, X_ID)


def test_ss_ev_02__list_events_other_workspace_404(db, s):
    """SS-EV-02 — list_events on another workspace's order: the 404 passes, no rollback.
    Rules: EV1; TC6."""
    S0 = so(db, s, "0", ws="0")
    commit_point(db)
    X_ID = mk_x(db).id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.list_events(db, order_id=S0.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert x_kept(db, X_ID)
