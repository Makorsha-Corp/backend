# ruff: noqa: SIM117, DTZ001, B017, FURB157
# (nested `with` blocks, naive datetimes, `date.today()` checks, `pytest.raises(Exception)`
# and `Decimal("1")`-style literals are prescribed by the cards' Conventions.)
"""Unit tests for app/services/work_order_service.py.

Implements tests/unit/services/work_order_service.cases.md (revision 4,
2026-11-22), one test per card, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the test's own "commit
point" and the service's commits are safe and the fixture's outer rollback
discards everything.

Patched, as Conventions name them: `app.managers.work_order_manager.utcnow`
(autouse fixture `clock`, NOW naive like the real helper); the commit /
rollback / refresh spies and failing variants (`patch.object(db, ...)`); the
notification functions imported by name into the service ("failing
notify(name)"); `app.services.work_order_service.utcnow` / `date` only where a
card says so; and the manager-return patches of the `Author: claude` cards.
Nothing else is mocked; the recorder cards capture the SQL sent with a
`before_cursor_execute` listener.

BUG-664 guard: stock is seeded only with S(I, q, p) (one Inventory row and one
past-dated opening ledger row at T0); no stock is posted in setup.

Standing rows are attributes of the namespace fixture `s` (`s.W1`, `s.U2`,
`s.A1`). `# Then N` marks the checks of the card's Then line N.
"""

import dataclasses
import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, inspect, select, text

from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.enums import (
    InventoryTypeEnum,
    WorkOrderPriorityEnum,
)
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.invoice_event import InvoiceEvent
from app.models.invoice_item import InvoiceItem
from app.models.invoice_payment import InvoicePayment
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.notification import Notification
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_assignee import WorkOrderAssignee
from app.models.work_order_completer import WorkOrderCompleter
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order_type import WorkOrderType
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderSheetEntryCreate,
    WorkOrderUpdate,
)
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate
from app.schemas.work_order_template import WorkOrderFromTemplateCreate
from app.services.work_order_service import (
    WorkOrderService,
    _WorkOrderEnrichment,
    work_order_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> imports and fixed values
# --------------------------------------------------------------------------- #

svc = work_order_service
WOM = svc.manager
assert isinstance(svc, WorkOrderService)

MISSING = 999999999
NOW = datetime(2026, 3, 10, 9, 0, 0)
T0 = datetime(2026, 1, 5, 8, 0, 0)
T1 = datetime(2026, 3, 1, 8, 0, 0)


def D(n):
    """Convention "D(n)"."""
    return date(2026, 3, n)


def NOON(n):
    """Convention "NOON(n)"."""
    return datetime(2026, 3, n, 12, 0, 0)


def NF(i):
    """Convention "NF(i)"."""
    return f"Work order with ID {i} not found"


INPROG = "Work order must be in progress before it can be completed"
NOTDRAFT = "Work order must be in draft to complete as planned"
NOINV = "No invoice linked — create an invoice for this external work before completing"
INVNF = "Linked invoice not found"
VOIDINV = "Linked invoice was voided — cannot complete this order"
NOLINES = "Add at least one line item before confirming"
FINAL = (
    "This order's invoice is already finalized. Void the invoice on the invoice"
    " page first, then void the order."
)
PAYHIST = "Invoice has payment history — confirm and void it instead"
EXISTS = "Invoice already exists for this work order"
NOACC = "Set an account on the work order before creating an invoice"
NOCOST = "Set the work order's cost before creating an invoice"
ACC404 = "Cannot create invoice: selected account was not found in this workspace"
CONFDEL = "This work order has a confirmed invoice — void the invoice first"
RESETMSG = "Approvals were reset — order details changed; re-approve when ready"
DRAFTP = "draft|Linked payable invoice is in draft — confirm when details look correct"
NOTMEMBER = "User is not an active member of this workspace"
STARTED = "Work has started — approvals can no longer change"


def BULKCONF(O):
    """Convention "BULKCONF(O)"."""
    return f"Work order {O.work_order_number} has a confirmed invoice — void the invoice first"


def CONFP(O):
    """Convention "CONFP(O)"."""
    return f"confirmed|Invoice confirmed on WO-{O.id} — order locked"


def NUM(O):
    """Convention "NUM(O)"."""
    return O.work_order_number


# xfail reasons: bug titles from docs/testing/bugs.md
BUGS = {
    627: "Invoice amount entered at creation is silently discarded at confirmation",
    628: "Invoice with no line items can be confirmed",
    639: "A draft that once had (voided) payments cannot be deleted",
    1279: "A deleted work order's lines stay open",
    2916: "Work order start, complete, void, approval and in-progress line changes take no row lock",
    2917: "Repeating a work order approval re-stamps it and logs it again",
    2923: "Deleting a work order leaves its draft invoice linked",
    2931: "Work order approvers and approvals can still change after work has started",
    3222: '"Create invoice", void and "complete as planned" act on the order\'s invoice without locking the order',
    3223: '"Complete as planned" on an order that isn\'t a draft answers with an invoice error',
    3224: "Voiding a work order whose invoice is already finalized leaves a payable bill on a voided order",
    3225: "A voided or completed work order can still get a new invoice",
    3226: "The work order's invoice is dated by the server's local clock",
    3227: "Bulk-deleting future recurring drafts, or a sheet re-plan, leaves their draft invoices linked",
    3228: '"Create invoice" on a work order with no cost makes a 0.00 bill that already shows paid',
    3229: "Voiding a work order with a draft invoice logs the unlink event without the invoice id",
}


def xf(*bugs, strict=True):
    """Convention "xfail cards": `xfail BUG-n` = strict xfail."""
    return pytest.mark.xfail(strict=strict, reason="; ".join(f"BUG-{b}: {BUGS[b]}" for b in bugs))


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "Time": the manager's utcnow returns NOW in every test.
@pytest.fixture(autouse=True)
def clock():
    with patch("app.managers.work_order_manager.utcnow", return_value=NOW) as m:
        yield m


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, built and flushed in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    """Standing rows 1-5 and TAG. `s.W1`, `s.U2`, `s.M1`, `s.A1`, ..."""
    r = SimpleNamespace()
    r.TAG = uuid.uuid4().hex[:8]
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1 = make_profile(db, name="Karim Ahmed")
    r.U2 = make_profile(db, name="Rahim Uddin")
    r.U3 = make_profile(db, name="Sara Khan")
    r.U4 = make_profile(db, name="Omar Faruk")
    r.U5 = make_profile(db, name="Nadia Islam")
    for ws, u, role, st, pos in (
        (r.W1, r.U1, "manager", "active", "Supervisor"),
        (r.W1, r.U2, "member", "active", None),
        (r.W1, r.U3, "member", "active", None),
        (r.W1, r.U4, "member", "suspended", "Fitter"),
        (r.W0, r.U5, "manager", "active", None),
        (r.W2, r.U5, "manager", "active", None),
    ):
        _add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=role, status=st, position=pos))
    r.WT0 = _add(db, WorkOrderType(workspace_id=r.W0.id, name="Service"))
    r.WT1 = _add(db, WorkOrderType(workspace_id=r.W1.id, name="Service"))
    r.WT9 = _add(db, WorkOrderType(workspace_id=r.W2.id, name="Service"))
    r.F0 = _add(db, Factory(workspace_id=r.W0.id, name="Plant Zero", abbreviation="P0"))
    r.F1 = _add(db, Factory(workspace_id=r.W1.id, name="Plant One", abbreviation="P1"))
    r.F9 = _add(db, Factory(workspace_id=r.W2.id, name="Plant Nine", abbreviation="P9"))
    r.M0 = _add(db, Machine(workspace_id=r.W0.id, factory_id=r.F0.id, name="Press"))
    r.M1 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F1.id, name="Lathe 3"))
    r.M2 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F1.id, name="Lathe 4"))
    r.M9 = _add(db, Machine(workspace_id=r.W2.id, factory_id=r.F9.id, name="Press"))
    r.I1 = _add(db, Item(workspace_id=r.W1.id, name="Bolt", name_normalized="bolt", unit="pcs"))
    r.I2 = _add(db, Item(workspace_id=r.W1.id, name="Bearing", name_normalized="bearing", unit="pcs"))
    for key, ws in (("A0", r.W0), ("A1", r.W1), ("A9", r.W2)):
        setattr(r, key, _add(db, Account(
            workspace_id=ws.id, name="Karim Engineering", is_active=True,
            is_deleted=False, allow_invoices=True,
        )))
    return r


def _ws(s, ws):
    """'of W0' / 'of W2' (ws = "0", "1", "2"): workspace, type, factory, machine, account."""
    return {
        "0": (s.W0, s.WT0, s.F0, s.M0, s.A0),
        "1": (s.W1, s.WT1, s.F1, s.M1, s.A1),
        "2": (s.W2, s.WT9, s.F9, s.M9, s.A9),
    }[ws]


# --------------------------------------------------------------------------- #
# Conventions -> Given rows ("but" = keyword overrides, applied last)
# --------------------------------------------------------------------------- #


def mk_order(db, s, n, ws="1", outside=False, started=False, completed=False,
             voided=False, gone=False, **cols):
    """Convention "order N" (ws "0"/"2" = of W0 / of W2; outside, started,
    completed, voided, gone); `cols` = the other columns after "but"."""
    w, wt, f, m, a = _ws(s, ws)
    fields = {
        "workspace_id": w.id,
        "work_order_number": f"WO-{s.TAG}-{n}",
        "work_order_type_id": wt.id,
        "title": "Service — Lathe 3",
        "factory_id": f.id,
        "machine_id": m.id,
        "status": "DRAFT",
        "priority": WorkOrderPriorityEnum.MEDIUM,
        "uses_inventory": False,
        "description": "Old desc",
        "cost": Decimal("100.00"),
        "planned_date": D(12),
        "created_by": s.U1.id,
        "approved_by": s.U1.id,
        "approved_at": T0,
    }
    if outside:
        fields["account_id"] = a.id
    if started or completed:
        fields.update(status="IN_PROGRESS", started_by=s.U1.id, started_at=T1, planned_date=D(1))
    if completed:
        fields.update(status="COMPLETED", completed_at=T1, completed_by=s.U1.id)
    if voided:
        fields.update(status="VOIDED", voided_at=T1, voided_by=s.U1.id, void_note="Old")
    if gone:
        fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=s.U1.id)
    fields.update(cols)
    return _add(db, WorkOrder(**fields))


def link(db, O, V):
    """Convention "linked": O.invoice_id = V.id, then db.flush()."""
    O.invoice_id = V.id
    db.flush()


def inv(db, s, O, ws="1", confirmed=False, voided_inv=False, linked=False, **cols):
    """Convention "inv(O)" (confirmed; voided-inv; ws "0"/"2"; linked)."""
    w, _, _, _, a = _ws(s, ws)
    fields = {
        "workspace_id": w.id,
        "account_id": a.id,
        "invoice_type": "payable",
        "invoice_status": "draft",
        "payment_status": "unpaid",
        "invoice_amount": Decimal("100.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": date(2026, 3, 1),
        "allow_payments": True,
        "receiving_started": False,
        "created_by": s.U1.id,
        "order_type": "work_order",
        "order_id": O.id,
    }
    if confirmed:
        fields["invoice_status"] = "confirmed"
    if voided_inv:
        fields.update(invoice_status="voided", void_note="dup")
    fields.update(cols)
    V = _add(db, AccountInvoice(**fields))
    if linked:
        link(db, O, V)
    return V


def invl(db, s, V, amount):
    """Convention "invl(V, "s")"."""
    return _add(db, InvoiceItem(
        workspace_id=V.workspace_id, invoice_id=V.id, line_number=1, description="Old line",
        quantity=Decimal("1"), unit_price=Decimal(amount), line_subtotal=Decimal(amount),
        created_by=s.U1.id,
    ))


def pay(db, s, V, amount):
    """Convention "pay(V, "a")" (a voided payment)."""
    return _add(db, InvoicePayment(
        workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(amount),
        payment_date=date(2026, 3, 1), is_voided=True, voided_at=T0, voided_by=s.U1.id,
        void_note="manual void", created_by=s.U1.id,
    ))


def approver(db, s, O, U, approved=False, **cols):
    """Convention "approver(O, U)" (approved)."""
    fields = {
        "workspace_id": s.W1.id, "work_order_id": O.id, "user_id": U.id,
        "assigned_by": s.U1.id, "assigned_at": T0, "approved": False,
    }
    if approved:
        fields.update(approved=True, approved_at=T0)
    fields.update(cols)
    return _add(db, WorkOrderApprover(**fields))


def assignee(db, s, O, U, ws="1"):
    """Convention "assignee(O, U)" (ws "0"/"2" = of W0 / of W2)."""
    return _add(db, WorkOrderAssignee(workspace_id=_ws(s, ws)[0].id, work_order_id=O.id, user_id=U.id))


def completer(db, s, O, U, ws="1"):
    """Convention "completer(O, U)" (ws "0"/"2" = of W0 / of W2)."""
    return _add(db, WorkOrderCompleter(workspace_id=_ws(s, ws)[0].id, work_order_id=O.id, user_id=U.id))


def line(db, s, O, item, q, gone=False, **cols):
    """Convention "line(O, I, "q")" (gone)."""
    fields = {
        "workspace_id": s.W1.id, "work_order_id": O.id, "item_id": item.id,
        "quantity": Decimal(q), "uses_inventory": True, "source_location_type": "storage",
        "source_location_id": s.F1.id, "action_type": "CONSUME", "created_by": s.U1.id,
    }
    if gone:
        fields.update(is_deleted=True, deleted_at=T0, deleted_by=s.U1.id)
    fields.update(cols)
    return _add(db, WorkOrderItem(**fields))


def stock(db, s, item, q, p):
    """Convention "S(I, q, p)": a STORAGE bucket of F1 plus one opening ledger row at T0."""
    pd = Decimal(str(p))
    bucket = _add(db, Inventory(
        workspace_id=s.W1.id, factory_id=s.F1.id, item_id=item.id,
        inventory_type=InventoryTypeEnum.STORAGE, qty=q, avg_price=pd,
        is_deleted=False, is_active=True, created_by=s.U1.id, updated_by=s.U1.id,
    ))
    _add(db, InventoryLedger(
        workspace_id=s.W1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=s.F1.id,
        item_id=item.id, transaction_type="opening", quantity=q, unit_cost=pd,
        total_cost=(pd * Decimal(q)).quantize(Decimal("0.01")), qty_before=0, qty_after=q,
        avg_price_before=None, avg_price_after=pd, source_type="manual", source_id=1,
        performed_by=s.U1.id, performed_at=T0,
    ))
    return bucket


def status_row(db, s, M, st, at):
    """Convention "status row(M, "S", at)"."""
    return _add(db, MachineActivityEvent(
        workspace_id=s.W1.id, machine_id=M.id, event_type="status_updated",
        description="Setup", metadata_json={"status": st}, created_at=at,
    ))


def wo_event(db, s, O, etype, meta, at):
    """Convention "event(O, "t", meta, at)"."""
    return _add(db, WorkOrderEvent(
        workspace_id=s.W1.id, work_order_id=O.id, event_type=etype,
        description="Setup", metadata_json=meta, created_at=at,
    ))


def ran(db, s, O):
    """Convention "ran" (a started order): two status rows of M1 and the started event."""
    status_row(db, s, s.M1, "RUNNING", T0)
    status_row(db, s, s.M1, "MAINTENANCE", T1)
    wo_event(db, s, O, "started", {"previous_machine_status": "RUNNING"}, T1)


# Convention "weekly" (template)
WEEKLY = {"is_recurring": True, "recurrence_type": "weekly", "recurrence_day": 0}


def template(db, s, **cols):
    """Convention "template"."""
    fields = {
        "workspace_id": s.W1.id, "template_name": "Oil change", "work_order_type_id": s.WT1.id,
        "uses_inventory": False, "requires_approval": False, "is_active": True,
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, WorkOrderTemplate(**fields))


def tapprover(db, s, T, U):
    """Convention "tapprover(T, U)"."""
    return _add(db, WorkOrderTemplateApprover(workspace_id=s.W1.id, work_order_template_id=T.id, user_id=U.id))


# --------------------------------------------------------------------------- #
# Conventions -> requests
# --------------------------------------------------------------------------- #


def CR(s, **k):
    """Convention "CR(**k)"."""
    return WorkOrderCreate(**{"work_order_type_id": s.WT1.id, "factory_id": s.F1.id, "machine_id": s.M1.id, **k})


def SHEET(s, **k):
    """Convention "SHEET(**k)"."""
    return WorkOrderSheetEntryCreate(**{
        "machine_id": s.M1.id, "work_order_type_id": s.WT1.id, "planned_date": D(12), **k,
    })


def ITEM(s, O, **k):
    """Convention "ITEM(O, **k)"."""
    return WorkOrderItemCreate(**{
        "work_order_id": O.id, "item_id": s.I1.id, "quantity": Decimal("2"),
        "uses_inventory": True, "source_location_type": "storage",
        "source_location_id": s.F1.id, **k,
    })


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

_COUNT_TABLES = (
    "work_orders",
    "work_order_items",
    "work_order_approvers",
    "work_order_completers",
    "work_order_events",
    "account_invoices",
    "invoice_items",
    "invoice_events",
    "invoice_payments",
    "notifications",
    "machine_activity_events",
    "inventory",
    "inventory_ledger",
)


def counts(db):
    """Named check "nothing written": row counts (all workspaces) of the listed tables."""
    return tuple(db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES)


def _max_id(db, table):
    return db.execute(text(f"SELECT coalesce(max(id), 0) FROM {table}")).scalar()


def commit_point(db):
    """Convention "commit point": db.commit(); returns the counts and the marks."""
    db.commit()
    return SimpleNamespace(
        counts=counts(db),
        mark_wo=_max_id(db, "work_order_events"),
        mark_mae=_max_id(db, "machine_activity_events"),
    )


def mk_x(db):
    """Convention "X": a pending workspace, flushed, not committed; returns (X, X_ID)."""
    x = make_workspace(db)
    return x, x.id


def snap(db, R):
    """Named check "unchanged(R)": every column of R, read straight from the database."""
    table = type(R).__table__
    rid = inspect(R).identity[0]
    db.expire_all()
    row = db.execute(select(table).where(table.c.id == rid)).mappings().one_or_none()
    return None if row is None else dict(row)


def snap_id(db, model, rid):
    """unchanged(R) by id (when R itself is no longer attached)."""
    table = model.__table__
    db.expire_all()
    row = db.execute(select(table).where(table.c.id == rid)).mappings().one_or_none()
    return None if row is None else dict(row)


def reread(db, model, rid):
    """Named check "re-read R"."""
    db.expire_all()
    return db.get(model, rid)


def gone(db, model, rid):
    """Named check "gone(R)"."""
    db.expire_all()
    return db.get(model, rid) is None


def x_gone(db, x_id):
    """Named check "x_gone"."""
    return db.get(Workspace, x_id) is None


def count_where(db, model, *where):
    db.expire_all()
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


def rows_where(db, model, *where):
    db.expire_all()
    return list(db.scalars(select(model).where(*where).order_by(model.id)))


def ev(db, cp, oid):
    """Named check "ev(O)": (type, description) of O's events with id > mark, by id."""
    return [(e.event_type, e.description) for e in evrows(db, cp, oid)]


def evrows(db, cp, oid):
    db.expire_all()
    return list(db.scalars(
        select(WorkOrderEvent)
        .where(WorkOrderEvent.work_order_id == oid, WorkOrderEvent.id > cp.mark_wo)
        .order_by(WorkOrderEvent.id)
    ))


def evrow(db, cp, oid, etype):
    """Named check "evrow(O, "t")": the one such row with that type."""
    rows = [e for e in evrows(db, cp, oid) if e.event_type == etype]
    assert len(rows) == 1, rows
    return rows[0]


def stat(db, cp, mid):
    """Named check "stat(M)"."""
    db.expire_all()
    return [
        a.metadata_json["status"]
        for a in db.scalars(
            select(MachineActivityEvent)
            .where(
                MachineActivityEvent.machine_id == mid,
                MachineActivityEvent.event_type == "status_updated",
                MachineActivityEvent.id > cp.mark_mae,
            )
            .order_by(MachineActivityEvent.id)
        )
    ]


def itypes(db, vid):
    """Named check "itypes(V)"."""
    db.expire_all()
    return [
        e.event_type
        for e in db.scalars(select(InvoiceEvent).where(InvoiceEvent.invoice_id == vid).order_by(InvoiceEvent.id))
    ]


def LINES(db, vid):
    """Named check "LINES(V)"."""
    db.expire_all()
    return list(db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == vid).order_by(InvoiceItem.line_number)))


def notes(db):
    """Named check "notes()"."""
    db.expire_all()
    return list(db.scalars(select(Notification).order_by(Notification.id)))


def recips(db):
    """Named check "recips()"."""
    return sorted(n.recipient_user_id for n in notes(db))


def session_clean(db):
    """Named check "session clean" (asserted as three checks by the callers)."""
    return (not db.new, not db.dirty, not db.deleted)


def loaded(r):
    """Named check "loaded(r)"."""
    return inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})


def approver_of(db, oid, uid):
    """the approver row of user U on order O, fresh query."""
    db.expire_all()
    return db.scalars(
        select(WorkOrderApprover).where(WorkOrderApprover.work_order_id == oid, WorkOrderApprover.user_id == uid)
    ).one()


def inv_of(db, oid):
    """the account_invoices rows of order O (order_type work_order), by id."""
    return rows_where(db, AccountInvoice, AccountInvoice.order_type == "work_order", AccountInvoice.order_id == oid)


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


# Convention "failing refresh": the rollback spy is yielded
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


# Convention "failing notify(name)": the rollback spy is yielded
@contextmanager
def failing_notify(db, name):
    with patch(f"app.services.work_order_service.{name}", side_effect=RuntimeError("boom")):
        with patch.object(db, "rollback", wraps=db.rollback) as rb:
            yield rb


_FROM = re.compile(r"\bFROM\b(.*?)(?:\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bFOR UPDATE\b|$)", re.DOTALL)
_LOCK = re.compile(r"FOR UPDATE( OF work_orders)?\s*$")


def _from_names(sql, table):
    m = _FROM.search(sql)
    return m is not None and re.search(rf"\b{re.escape(table)}\b", m.group(1)) is not None


class Recorder:
    """Convention "Statement recorder": every SQL statement sent during the When."""

    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def names(self, table):
        """Named check "names(t)"."""
        return [st for st in self.statements if table in st]

    def _first_wo_select(self):
        for i, st in enumerate(self.statements):
            if st.lstrip().upper().startswith("SELECT") and _from_names(st, "work_orders"):
                return i, st
        return None, None

    def lock(self):
        """Named check "lock(work_orders)"."""
        _, st = self._first_wo_select()
        return st is not None and _LOCK.search(st) is not None

    def lock_first(self):
        """Named check "lock first"."""
        i, _ = self._first_wo_select()
        if i is None:
            return False
        later = [
            j for j, st in enumerate(self.statements)
            if "account_invoices" in st or st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        return not later or i < min(later)



# --------------------------------------------------------------------------- #
# _load_work_order_enrichment
# --------------------------------------------------------------------------- #


def test_wos_le_01__empty_list_three_empty_maps(db, s):
    """WOS-LE-01 — an empty list gives three empty maps and reads nothing.
    Rules: _load_work_order_enrichment W1."""
    commit_point(db)
    with Recorder(db) as rec:
        result = svc._load_work_order_enrichment(db, orders=[])
    # Then 1
    assert result.assignee_map == {}
    assert result.completer_map == {}
    assert result.profile_names == {}
    # Then 2
    assert rec.statements == []


def test_wos_le_02__assignee_key_per_order_in_row_order(db, s):
    """WOS-LE-02 — every order gets an assignee key, ids in row order, [] without assignees.
    Rules: _load_work_order_enrichment W2."""
    O1 = mk_order(db, s, "1")
    O2 = mk_order(db, s, "2")
    assignee(db, s, O1, s.U3)
    assignee(db, s, O1, s.U2)
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1, O2])
    # Then 1
    assert result.assignee_map == {O1.id: [s.U3.id, s.U2.id], O2.id: []}


def test_wos_le_03__w2_assignee_row_not_read(db, s):
    """WOS-LE-03 — an assignee row of W2 on a W1 order is not read.
    Rules: _load_work_order_enrichment W2; HR-16."""
    O1 = mk_order(db, s, "1")
    assignee(db, s, O1, s.U2)
    assignee(db, s, O1, s.U5, ws="2")
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.assignee_map == {O1.id: [s.U2.id]}


def test_wos_le_04__w0_assignee_row_not_read(db, s):
    """WOS-LE-04 — an assignee row of W0 on a W1 order is not read.
    Rules: _load_work_order_enrichment W2; HR-16."""
    O1 = mk_order(db, s, "1")
    assignee(db, s, O1, s.U5, ws="0")
    assignee(db, s, O1, s.U3)
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.assignee_map == {O1.id: [s.U3.id]}


def test_wos_le_05__two_workspaces_each_own(db, s):
    """WOS-LE-05 — orders of two workspaces are each read with their own workspace.
    Rules: _load_work_order_enrichment W2."""
    O1 = mk_order(db, s, "1")
    O9 = mk_order(db, s, "9", ws="2")
    assignee(db, s, O1, s.U2)
    assignee(db, s, O9, s.U5, ws="2")
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1, O9])
    # Then 1
    assert result.assignee_map == {O1.id: [s.U2.id], O9.id: [s.U5.id]}


def test_wos_le_06__completers_mapped(db, s):
    """WOS-LE-06 — completers are mapped the same way.
    Rules: _load_work_order_enrichment W3."""
    O1 = mk_order(db, s, "1", completed=True)
    O2 = mk_order(db, s, "2")
    completer(db, s, O1, s.U3)
    completer(db, s, O1, s.U2)
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1, O2])
    # Then 1
    assert result.completer_map == {O1.id: [s.U3.id, s.U2.id], O2.id: []}


def test_wos_le_07__w2_completer_row_not_read(db, s):
    """WOS-LE-07 — a completer row of W2 on a W1 order is not read.
    Rules: _load_work_order_enrichment W3; HR-16."""
    O1 = mk_order(db, s, "1", completed=True)
    completer(db, s, O1, s.U5, ws="2")
    completer(db, s, O1, s.U3)
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.completer_map == {O1.id: [s.U3.id]}


def test_wos_le_08__starter_and_completer_names(db, s):
    """WOS-LE-08 — names of the starter and of the completer when no names text is stored.
    Rules: _load_work_order_enrichment W4."""
    O1 = mk_order(db, s, "1", completed=True, started_by=s.U2.id, completed_by=s.U3.id, completed_by_names=None)
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.profile_names == {s.U2.id: "Rahim Uddin", s.U3.id: "Sara Khan"}


def test_wos_le_09__names_text_skips_completer(db, s):
    """WOS-LE-09 — a stored names text skips the completer's profile.
    Rules: _load_work_order_enrichment W4."""
    O1 = mk_order(db, s, "1", completed=True, started_by=s.U2.id, completed_by=s.U3.id, completed_by_names="Crew A")
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.profile_names == {s.U2.id: "Rahim Uddin"}


def test_wos_le_10__empty_names_text_reads_completer(db, s):
    """WOS-LE-10 — an empty names text reads the completer's profile.
    Rules: _load_work_order_enrichment W4."""
    O1 = mk_order(db, s, "1", completed=True, started_by=None, completed_by=s.U3.id, completed_by_names="")
    commit_point(db)
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.profile_names == {s.U3.id: "Sara Khan"}


def test_wos_le_11__id_without_profile_absent(db, s):
    """WOS-LE-11 — an id without a profile row is absent from the names.
    Rules: _load_work_order_enrichment W4."""
    O1 = mk_order(db, s, "1", started=True, started_by=s.U2.id)
    commit_point(db)
    O1.started_by = MISSING
    result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.profile_names == {}


def test_wos_le_12__no_starter_no_completer_no_profile_read(db, s):
    """WOS-LE-12 — no starter and no completer: no profile is read.
    Rules: _load_work_order_enrichment W4."""
    O1 = mk_order(db, s, "1")
    commit_point(db)
    with Recorder(db) as rec:
        result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.profile_names == {}
    # Then 2
    assert rec.names("profiles") == []


def test_wos_le_13__enrichment_no_commit_no_rollback(db, s):
    """WOS-LE-13 — the enrichment neither commits nor rolls back.
    Rules: _load_work_order_enrichment (reads); TC6."""
    O1 = mk_order(db, s, "1")
    assignee(db, s, O1, s.U2)
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc._load_work_order_enrichment(db, orders=[O1])
    # Then 1
    assert result.assignee_map == {O1.id: [s.U2.id]}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_le_14__enrichment_frozen_fields_in_order(db, s):
    """WOS-LE-14 — `_WorkOrderEnrichment` is frozen, with its three fields in order.
    Rules: _load_work_order_enrichment (Facts G4)."""
    e = _WorkOrderEnrichment(assignee_map={}, completer_map={}, profile_names={})
    # Then 1
    assert [f.name for f in dataclasses.fields(_WorkOrderEnrichment)] == ["assignee_map", "completer_map", "profile_names"]
    # Then 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.assignee_map = {1: [2]}
    # Then 3
    assert e.assignee_map == {}
    # Then 4
    assert _WorkOrderEnrichment({}, {}, {}) == e


# --------------------------------------------------------------------------- #
# _to_work_order_response
# --------------------------------------------------------------------------- #


def test_wos_r_01__own_lists_loaded(db, s):
    """WOS-R-01 — without an enrichment the order's own lists are loaded.
    Rules: _to_work_order_response W5, W7."""
    O = mk_order(db, s, "1", completed=True)
    assignee(db, s, O, s.U2)
    completer(db, s, O, s.U3)
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert type(result).__name__ == "WorkOrderResponse"
    # Then 2
    assert result.assignee_user_ids == [s.U2.id]
    assert result.completer_user_ids == [s.U3.id]


def test_wos_r_02__columns_copied(db, s):
    """WOS-R-02 — columns are copied, with the type name and the planned date as calendar date.
    Rules: _to_work_order_response W6."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("750.50"))
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.id == O.id
    assert result.work_order_number == NUM(O)
    assert result.title == "Service — Lathe 3"
    assert result.status == "DRAFT"
    # Then 2
    assert result.cost == Decimal("750.50")
    assert result.account_id == s.A1.id
    assert result.invoice_id is None
    # Then 3
    assert result.work_order_type_name == "Service"
    # Then 4
    assert result.calendar_date == D(12)


def test_wos_r_03__soft_deleted_type_keeps_name(db, s):
    """WOS-R-03 — a soft-deleted type still gives its name.
    Rules: _to_work_order_response W6."""
    WTD = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Retired service", is_deleted=True))
    O = mk_order(db, s, "1", work_order_type_id=WTD.id)
    commit_point(db)
    wtd = WTD.id
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.work_order_type_name == "Retired service"
    # Then 2
    assert result.work_order_type_id == wtd


def test_wos_r_04__no_planned_date_calendar_is_creation_day(db, s):
    """WOS-R-04 — without a planned date the calendar date is the day of creation.
    Rules: _to_work_order_response W6."""
    O = mk_order(db, s, "1", planned_date=None)
    commit_point(db)
    CREATED = O.created_at
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.calendar_date == CREATED.date()


def test_wos_r_05__given_enrichment_used(db, s):
    """WOS-R-05 — a given enrichment is used and nothing is read for the lists.
    Rules: _to_work_order_response W5, W7."""
    O = mk_order(db, s, "1")
    assignee(db, s, O, s.U2)
    commit_point(db)
    ENR = _WorkOrderEnrichment(assignee_map={O.id: [s.U4.id]}, completer_map={O.id: [s.U3.id]}, profile_names={})
    with Recorder(db) as rec:
        result = svc._to_work_order_response(db, O, enrichment=ENR)
    # Then 1
    assert result.assignee_user_ids == [s.U4.id]
    # Then 2
    assert result.completer_user_ids == [s.U3.id]
    # Then 3
    assert rec.names("work_order_assignees") == []


def test_wos_r_06__missing_from_maps_empty_lists(db, s):
    """WOS-R-06 — an order missing from the maps gets empty lists.
    Rules: _to_work_order_response W7."""
    O = mk_order(db, s, "1")
    assignee(db, s, O, s.U2)
    commit_point(db)
    ENR = _WorkOrderEnrichment(assignee_map={}, completer_map={}, profile_names={})
    result = svc._to_work_order_response(db, O, enrichment=ENR)
    # Then 1
    assert result.assignee_user_ids == []
    assert result.completer_user_ids == []


def test_wos_r_07__starter_name(db, s):
    """WOS-R-07 — a started order shows the starter's name.
    Rules: _to_work_order_response W8."""
    O = mk_order(db, s, "1", started=True, started_by=s.U2.id)
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.started_by_name == "Rahim Uddin"


def test_wos_r_08__not_started_no_starter_name(db, s):
    """WOS-R-08 — an order not started has no starter name.
    Rules: _to_work_order_response W8."""
    O = mk_order(db, s, "1")
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.started_by_name is None


def test_wos_r_09__starter_without_profile_none(db, s):
    """WOS-R-09 — a starter without a profile row gives None.
    Rules: _to_work_order_response W8."""
    O = mk_order(db, s, "1", started=True, started_by=s.U2.id)
    commit_point(db)
    O.started_by = MISSING
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.started_by_name is None


def test_wos_r_10__names_text_wins(db, s):
    """WOS-R-10 — a stored names text wins over the completer's profile.
    Rules: _to_work_order_response W9."""
    O = mk_order(db, s, "1", completed=True, completed_by=s.U3.id, completed_by_names="Crew A")
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.completed_by_name == "Crew A"
    # Then 2
    assert result.completed_by_names == "Crew A"


def test_wos_r_11__empty_names_text_falls_back(db, s):
    """WOS-R-11 — an empty names text falls back to the completer's profile; the text is copied as stored.
    Rules: _to_work_order_response W9."""
    O = mk_order(db, s, "1", completed=True, completed_by=s.U3.id, completed_by_names="")
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.completed_by_name == "Sara Khan"
    # Then 2
    assert result.completed_by_names == ""


def test_wos_r_12__no_names_no_completer_none(db, s):
    """WOS-R-12 — no names text and no completer: None.
    Rules: _to_work_order_response W9."""
    O = mk_order(db, s, "1", completed=True, completed_by=None, completed_by_names=None)
    commit_point(db)
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.completed_by_name is None


def test_wos_r_13__completer_without_profile_none(db, s):
    """WOS-R-13 — a completer without a profile row gives None.
    Rules: _to_work_order_response W9."""
    O = mk_order(db, s, "1", completed=True, completed_by=s.U3.id, completed_by_names=None)
    commit_point(db)
    O.completed_by = MISSING
    result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.completed_by_name is None


def test_wos_r_14__mapping_writes_nothing(db, s):
    """WOS-R-14 — mapping writes nothing, commits nothing, rolls nothing back.
    Rules: _to_work_order_response W10; TC6."""
    O = mk_order(db, s, "1", started=True, started_by=s.U2.id)
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc._to_work_order_response(db, O)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    assert not db.new
    # Then 5
    assert not db.dirty
    assert not db.deleted


# --------------------------------------------------------------------------- #
# _to_work_order_responses
# --------------------------------------------------------------------------- #


def test_wos_rs_01__empty_list(db, s):
    """WOS-RS-01 — an empty list gives [] and reads nothing.
    Rules: _to_work_order_responses W11."""
    commit_point(db)
    with Recorder(db) as rec:
        result = svc._to_work_order_responses(db, orders=[])
    # Then 1
    assert result == []
    # Then 2
    assert rec.statements == []


def test_wos_rs_02__given_order_one_enrichment(db, s):
    """WOS-RS-02 — orders are mapped in the given order from one enrichment.
    Rules: _to_work_order_responses W12."""
    O1 = mk_order(db, s, "1")
    O2 = mk_order(db, s, "2")
    O3 = mk_order(db, s, "3")
    assignee(db, s, O1, s.U2)
    assignee(db, s, O3, s.U3)
    commit_point(db)
    ids = (O1.id, O2.id, O3.id)
    with Recorder(db) as rec:
        result = svc._to_work_order_responses(db, orders=[O3, O1, O2])
    # Then 1
    assert [r.id for r in result] == [ids[2], ids[0], ids[1]]
    # Then 2
    assert [r.assignee_user_ids for r in result] == [[s.U3.id], [s.U2.id], []]
    # Then 3
    assert len([st for st in rec.names("work_order_assignees") if st.lstrip().upper().startswith("SELECT")]) == 1


def test_wos_rs_03__batch_no_commit_no_rollback(db, s):
    """WOS-RS-03 — the batch mapping neither commits nor rolls back.
    Rules: _to_work_order_responses W12; TC6."""
    O1 = mk_order(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc._to_work_order_responses(db, orders=[O1])
    # Then 1
    assert [r.id for r in result] == [O1.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


# --------------------------------------------------------------------------- #
# create_work_order
# --------------------------------------------------------------------------- #


def _wo_count(db, ws_id):
    return count_where(db, WorkOrder, WorkOrder.workspace_id == ws_id)


def test_wos_e_01__new_order_committed_no_invoice_no_notice(db, s):
    """WOS-E-01 — a new order is committed and returned re-read; no invoice and no notification even with account and cost.
    Rules: create_work_order E1, E2; TC1, TC2."""
    commit_point(db)
    result = svc.create_work_order(
        db, wo_in=CR(s, account_id=s.A1.id, cost=Decimal("500.00")), workspace_id=s.W1.id, user_id=s.U2.id,
    )
    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, WorkOrder)
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, rid)
    assert row.workspace_id == s.W1.id
    assert row.account_id == s.A1.id
    assert row.cost == Decimal("500.00")
    assert row.created_by == s.U2.id
    assert row.invoice_id is None
    # Then 4
    assert len(inv_of(db, rid)) == 0
    # Then 5
    assert notes(db) == []


def test_wos_e_02__manager_404_passes_extra_row_gone(db, s):
    """WOS-E-02 — the manager's 404 passes unchanged and the uncommitted extra row is gone.
    Rules: create_work_order E1; TC3."""
    cp = commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_work_order(
                db, wo_in=CR(s, factory_id=s.F9.id, machine_id=None), workspace_id=s.W1.id, user_id=s.U2.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_wos_e_03__failing_commit_no_order(db, s):
    """WOS-E-03 — a failing commit is rolled back and re-raised; no order saved.
    Rules: create_work_order E1; TC4."""
    cp = commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_work_order(db, wo_in=CR(s), workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert _wo_count(db, s.W1.id) == 0
    # Then 4
    assert counts(db) == cp.counts


def test_wos_e_04__failing_refresh_order_saved(db, s):
    """WOS-E-04 — a failing re-read after the commit leaves the order saved.
    Rules: create_work_order E1; TC5."""
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_work_order(db, wo_in=CR(s, description="Belt check"), workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    rows = rows_where(db, WorkOrder, WorkOrder.workspace_id == s.W1.id)
    assert len(rows) == 1
    # Then 3
    assert rows[0].description == "Belt check"
    assert rows[0].created_by == s.U2.id


# --------------------------------------------------------------------------- #
# create_work_order_from_template
# --------------------------------------------------------------------------- #


def test_wos_t_01__committed_no_invoice(db, s):
    """WOS-T-01 — the order is committed; no invoice even with the template's account and cost.
    Rules: create_work_order_from_template T1, T2; TC1, TC2."""
    T = template(db, s, account_id=s.A1.id, cost=Decimal("300.00"))
    commit_point(db)
    t_id = T.id
    result = svc.create_work_order_from_template(
        db, template_id=t_id, overrides=WorkOrderFromTemplateCreate(machine_id=s.M1.id),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, rid)
    assert row.work_order_template_id == t_id
    assert row.account_id == s.A1.id
    assert row.cost == Decimal("300.00")
    assert row.invoice_id is None
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == rid) == 0


def test_wos_t_02__template_approvers_not_notified(db, s):
    """WOS-T-02 — approvers copied from the template are not notified.
    Rules: create_work_order_from_template T2."""
    T = template(db, s, requires_approval=True)
    tapprover(db, s, T, s.U3)
    commit_point(db)
    result = svc.create_work_order_from_template(
        db, template_id=T.id, overrides=WorkOrderFromTemplateCreate(machine_id=s.M1.id),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    assert [a.user_id for a in rows_where(db, WorkOrderApprover, WorkOrderApprover.work_order_id == rid)] == [s.U3.id]
    # Then 3
    assert notes(db) == []


def test_wos_t_03__inactive_template_400(db, s):
    """WOS-T-03 — an inactive template: the manager's 400, the extra row is gone.
    Rules: create_work_order_from_template T1; TC3."""
    T = template(db, s, is_active=False)
    cp = commit_point(db)
    t_id = T.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.create_work_order_from_template(
                db, template_id=t_id, overrides=WorkOrderFromTemplateCreate(machine_id=s.M1.id),
                workspace_id=s.W1.id, user_id=s.U2.id,
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Template is inactive"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_t_04__failing_commit_no_order(db, s):
    """WOS-T-04 — a failing commit leaves no order.
    Rules: create_work_order_from_template T1; TC4."""
    T = template(db, s)
    commit_point(db)
    t_id = T.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_work_order_from_template(
                db, template_id=t_id, overrides=WorkOrderFromTemplateCreate(machine_id=s.M1.id),
                workspace_id=s.W1.id, user_id=s.U2.id,
            )
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, WorkOrder, WorkOrder.work_order_template_id == t_id) == 0


# --------------------------------------------------------------------------- #
# update_work_order
# --------------------------------------------------------------------------- #


def _upd(db, s, O, user, **k):
    return svc.update_work_order(
        db, wo_id=O.id, wo_in=WorkOrderUpdate(**(k or {"description": "New desc"})),
        workspace_id=s.W1.id, user_id=user.id,
    )


def test_wos_u_01__edit_committed_no_notice(db, s):
    """WOS-U-01 — an edit without recorded approvals is committed; no notification.
    Rules: update_work_order U1, U3; TC1, TC2."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3)
    commit_point(db)
    oid = O.id
    result = _upd(db, s, O, s.U2)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    assert reread(db, WorkOrder, oid).description == "New desc"
    # Then 4
    assert notes(db) == []


def test_wos_u_02__reset_tells_creator_once(db, s):
    """WOS-U-02 — an edit that clears approvals tells the creator once, not the approvers.
    Rules: update_work_order U2."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    result = _upd(db, s, O, s.U2)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert len(notes(db)) == 1
    # Then 3
    assert notes(db)[0].recipient_user_id == s.U1.id
    assert notes(db)[0].notification_type == "section_confirm"
    # Then 4
    assert notes(db)[0].entity_type == "work_order"
    assert notes(db)[0].entity_id == oid
    # Then 5
    assert notes(db)[0].source_type == "section"
    assert notes(db)[0].source_id == oid
    # Then 6
    assert notes(db)[0].preview == RESETMSG


def test_wos_u_03__creator_told_when_creator_edits(db, s):
    """WOS-U-03 — the creator is told also when the creator made the edit.
    Rules: update_work_order U2."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    result = _upd(db, s, O, s.U1)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id]
    # Then 3
    assert notes(db)[0].preview == RESETMSG


def test_wos_u_04__inactive_creator_no_notice(db, s):
    """WOS-U-04 — a creator who is not an active member gets no notice.
    Rules: update_work_order U2."""
    O = mk_order(db, s, "1", created_by=s.U4.id)
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    result = _upd(db, s, O, s.U2)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert notes(db) == []
    # Then 3
    assert approver_of(db, oid, s.U3.id).approved is False


def test_wos_u_05__no_creator_no_notice(db, s):
    """WOS-U-05 — no creator: no notice.
    Rules: update_work_order U2."""
    O = mk_order(db, s, "1", created_by=None)
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    result = _upd(db, s, O, s.U2)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert notes(db) == []


def test_wos_u_06__no_reset_attribute_sends_nothing(db, s):
    """WOS-U-06 — a manager result without `_approvals_reset` sends nothing.
    Rules: update_work_order U3."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    with patch.object(svc.manager, "update_work_order", return_value=O):
        result = _upd(db, s, O, s.U2)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert notes(db) == []


def test_wos_u_07__linked_draft_invoice_untouched_title_dropped(db, s):
    """WOS-U-07 — a linked draft invoice is not touched by an edit; the title in the edit is dropped.
    Rules: update_work_order U4, U4a."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _upd(db, s, O, s.U2, title="Overhaul — Lathe 3", description="New desc", end_date=D(20))
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.title == "Service — Lathe 3"
    assert row.description == "New desc"
    assert row.end_date == D(20)
    assert row.invoice_id == vid
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert [(i.description, i.unit_price) for i in LINES(db, vid)] == [("Old line", Decimal("100.00"))]


def test_wos_u_08__failing_reset_notice_undoes_edit(db, s):
    """WOS-U-08 — a failing approvals-reset notice undoes the whole edit.
    Rules: update_work_order U5; TC3."""
    O = mk_order(db, s, "1")
    P3 = approver(db, s, O, s.U3, approved=True)
    cp = commit_point(db)
    before_o, before_p = snap(db, O), snap(db, P3)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_notify(db, "notify_section_confirm_needed"):
            _upd(db, s, O, s.U2)
    assert str(exc.value) == "boom"
    # Then 2
    assert X not in db
    # Then 3
    assert snap(db, O) == before_o
    # Then 4
    assert snap(db, P3) == before_p
    # Then 5
    assert counts(db) == cp.counts
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_u_09__voided_order_400(db, s):
    """WOS-U-09 — the manager's 400 for a voided order passes unchanged; the extra row is gone.
    Rules: update_work_order U1; TC3."""
    O = mk_order(db, s, "1", voided=True)
    commit_point(db)
    before = snap(db, O)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _upd(db, s, O, s.U2)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided and cannot be edited"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, O) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_u_10__w2_order_404(db, s):
    """WOS-U-10 — another workspace's order (W2): 404, nothing changed.
    Rules: update_work_order U1; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, Z)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, s, Z, s.U2)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)
    # Then 4
    assert snap(db, Z) == before


def test_wos_u_11__failing_commit_keeps_old(db, s):
    """WOS-U-11 — a failing commit keeps the old description and sends nothing.
    Rules: update_work_order U1; TC4."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _upd(db, s, O, s.U2)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, oid).description == "Old desc"
    # Then 4
    assert notes(db) == []


# --------------------------------------------------------------------------- #
# get_work_order
# --------------------------------------------------------------------------- #


def test_wos_g_01__returns_order_no_commit(db, s):
    """WOS-G-01 — returns the order; neither commits nor rolls back; a pending row stays pending.
    Rules: get_work_order G1; TC6."""
    O = mk_order(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.get_work_order(db, wo_id=O.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, WorkOrder)
    assert result.id == O.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_g_02__voided_returned(db, s):
    """WOS-G-02 — a voided order is returned.
    Rules: get_work_order G1."""
    O = mk_order(db, s, "1", voided=True)
    commit_point(db)
    result = svc.get_work_order(db, wo_id=O.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == O.id
    assert result.status == "VOIDED"


def test_wos_g_03__completed_returned(db, s):
    """WOS-G-03 — a completed order is returned.
    Rules: get_work_order G1."""
    O = mk_order(db, s, "1", completed=True)
    commit_point(db)
    result = svc.get_work_order(db, wo_id=O.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == O.id
    assert result.status == "COMPLETED"


def test_wos_g_04__w0_order_404(db, s):
    """WOS-G-04 — a W0 order (lower workspace id) gets the 404.
    Rules: get_work_order G1; HR-16."""
    Z = mk_order(db, s, "0", ws="0")
    mk_order(db, s, "1")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order(db, wo_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(Z.id)


def test_wos_g_05__w2_order_404(db, s):
    """WOS-G-05 — a W2 order (higher workspace id) gets the 404.
    Rules: get_work_order G1; HR-16."""
    mk_order(db, s, "1")
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order(db, wo_id=Z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(Z.id)


def test_wos_g_06__404_no_rollback(db, s):
    """WOS-G-06 — a 404 neither rolls back nor drops a pending row.
    Rules: get_work_order G1; TC6."""
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_work_order(db, wo_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    assert exc.value.detail == NF(MISSING)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


@xf(1279)
def test_wos_g_07__soft_deleted_404(db, s):
    """WOS-G-07 — a soft-deleted order gets the 404.
    Rules: get_work_order G1 [BUG-1279] (manager pass-through)."""
    O = mk_order(db, s, "1", gone=True)
    commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order(db, wo_id=oid, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(oid)


# --------------------------------------------------------------------------- #
# list_work_orders
# --------------------------------------------------------------------------- #


def test_wos_l_01__manager_list_w1_only(db, s):
    """WOS-L-01 — returns the manager's list of W1 orders; W0 and W2 orders never appear; no commit, no rollback.
    Rules: list_work_orders L1; TC6."""
    mk_order(db, s, "0", ws="0")
    O1 = mk_order(db, s, "1")
    O2 = mk_order(db, s, "2")
    mk_order(db, s, "9", ws="2")
    commit_point(db)
    ids = {O1.id, O2.id}
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.list_work_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert [o.id for o in result] == [o.id for o in WOM.list_work_orders(db, workspace_id=s.W1.id)]
    # Then 2
    assert {o.id for o in result} == ids
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_wos_l_02__default_limit_100(db, s):
    """WOS-L-02 — with no limit given, 101 orders give 100.
    Rules: list_work_orders L1."""
    for k in range(1, 102):
        mk_order(db, s, str(k))
    commit_point(db)
    result = svc.list_work_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100


def test_wos_l_03__skip_and_limit_passed(db, s):
    """WOS-L-03 — skip and limit=1000 are passed on.
    Rules: list_work_orders L1."""
    for k in range(1, 4):
        mk_order(db, s, str(k))
    commit_point(db)
    result = svc.list_work_orders(db, workspace_id=s.W1.id, skip=1, limit=1000)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert [o.id for o in result] == [
        o.id for o in WOM.list_work_orders(db, workspace_id=s.W1.id, skip=1, limit=1000)
    ]


def test_wos_l_04__status_filter_passed(db, s):
    """WOS-L-04 — the status filter is passed on.
    Rules: list_work_orders L1."""
    mk_order(db, s, "1")
    O2 = mk_order(db, s, "2", started=True)
    commit_point(db)
    result = svc.list_work_orders(db, workspace_id=s.W1.id, wo_status="IN_PROGRESS")
    # Then 1
    assert [o.id for o in result] == [O2.id]


def test_wos_l_05__machine_filter_passed(db, s):
    """WOS-L-05 — the machine filter is passed on.
    Rules: list_work_orders L1."""
    mk_order(db, s, "1")
    O2 = mk_order(db, s, "2", machine_id=s.M2.id)
    commit_point(db)
    result = svc.list_work_orders(db, workspace_id=s.W1.id, machine_id=s.M2.id)
    # Then 1
    assert [o.id for o in result] == [O2.id]


# --------------------------------------------------------------------------- #
# bulk_delete_future_recurrence_drafts
# --------------------------------------------------------------------------- #


def _bulk(db, s, T):
    return svc.bulk_delete_future_recurrence_drafts(
        db, workspace_id=s.W1.id, user_id=s.U2.id, work_order_template_id=T.id,
        machine_id=s.M1.id, after_date=D(10),
    )


def test_wos_b_01__future_drafts_deleted(db, s):
    """WOS-B-01 — future drafts are deleted and committed; the response lists them; nobody told.
    Rules: bulk_delete_future_recurrence_drafts B1, B2, B4."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", work_order_template_id=T.id, planned_date=D(12))
    B = mk_order(db, s, "b", work_order_template_id=T.id, planned_date=D(11))
    commit_point(db)
    aid, bid = A.id, B.id
    result = _bulk(db, s, T)
    # Then 1
    assert type(result).__name__ == "BulkDeleteFutureRecurrenceDraftsResponse"
    # Then 2
    assert result.deleted_ids == [bid, aid]
    assert result.deleted_count == 2
    db.rollback()
    # Then 3
    a = reread(db, WorkOrder, aid)
    assert a.is_deleted is True
    assert a.deleted_by == s.U2.id
    # Then 4
    b = reread(db, WorkOrder, bid)
    assert b.is_deleted is True
    assert b.deleted_by == s.U2.id
    # Then 5
    assert notes(db) == []


def test_wos_b_02__nothing_to_delete_commit_still(db, s):
    """WOS-B-02 — nothing to delete: 0 and [], and the empty commit still happens.
    Rules: bulk_delete_future_recurrence_drafts B2."""
    T = template(db, s, **WEEKLY)
    ON = mk_order(db, s, "c", work_order_template_id=T.id, planned_date=D(10))
    commit_point(db)
    before = snap(db, ON)
    with spies(db) as (cm, _rb):
        result = _bulk(db, s, T)
    # Then 1
    assert result.deleted_count == 0
    assert result.deleted_ids == []
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert snap(db, ON) == before


def test_wos_b_03__failing_commit_deletes_nothing(db, s):
    """WOS-B-03 — a failing commit deletes nothing.
    Rules: bulk_delete_future_recurrence_drafts B1; TC4."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", work_order_template_id=T.id, planned_date=D(12))
    commit_point(db)
    aid = A.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _bulk(db, s, T)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, aid).is_deleted is False


def test_wos_b_04__manager_error_same_object(db, s):
    """WOS-B-04 — an error from the manager rolls back and passes as the same object; the extra row is gone.
    Rules: bulk_delete_future_recurrence_drafts B1; TC3."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", work_order_template_id=T.id, planned_date=D(12))
    commit_point(db)
    aid, tid = A.id, T.id
    X, x_id = mk_x(db)
    ERR = HTTPException(status_code=400, detail="x")
    with patch.object(svc.manager, "bulk_delete_future_recurrence_drafts", side_effect=ERR):
        with pytest.raises(HTTPException) as exc:
            with spies(db) as (_cm, rb):
                svc.bulk_delete_future_recurrence_drafts(
                    db, workspace_id=s.W1.id, user_id=s.U2.id, work_order_template_id=tid,
                    machine_id=s.M1.id, after_date=D(10),
                )
    # Then 1
    assert exc.value is ERR
    # Then 2
    assert X not in db
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert reread(db, WorkOrder, aid).is_deleted is False
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


@xf(3227)
def test_wos_b_05__draft_invoice_deleted_and_unlinked(db, s):
    """WOS-B-05 — a deleted draft's draft invoice is deleted and unlinked, with an event.
    Rules: bulk_delete_future_recurrence_drafts B3 [BUG-3227]."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    V = inv(db, s, A, invoice_amount=Decimal("3000.00"), linked=True)
    invl(db, s, V, "3000.00")
    V_ID = V.id
    cp = commit_point(db)
    aid, num = A.id, NUM(A)
    result = _bulk(db, s, T)
    # Then 1
    assert result.deleted_ids == [aid]
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, aid).is_deleted is True
    # Then 3
    assert gone(db, AccountInvoice, V_ID)
    # Then 4
    assert reread(db, WorkOrder, aid).invoice_id is None
    # Then 5
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == V_ID) == 0
    # Then 6
    assert ev(db, cp, aid) == [("invoice_voided", f"Invoice unlinked — work order {num} deleted")]
    # Then 7
    assert evrow(db, cp, aid, "invoice_voided").metadata_json == {"invoice_id": V_ID}
    assert evrow(db, cp, aid, "invoice_voided").performed_by == s.U2.id


def test_wos_b_06__draft_with_draft_invoice_still_deleted(db, s):
    """WOS-B-06 — a draft with a linked draft invoice is still deleted (today and after the fix).
    Rules: bulk_delete_future_recurrence_drafts B1, B3."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    inv(db, s, A, linked=True)
    commit_point(db)
    aid = A.id
    result = _bulk(db, s, T)
    # Then 1
    assert result.deleted_ids == [aid]
    db.rollback()
    # Then 2
    a = reread(db, WorkOrder, aid)
    assert a.is_deleted is True
    assert a.deleted_by == s.U2.id


@xf(3227)
def test_wos_b_07__confirmed_invoice_refuses_whole_call(db, s):
    """WOS-B-07 — a confirmed invoice on one draft refuses the whole call; nothing deleted.
    Rules: bulk_delete_future_recurrence_drafts B3 [BUG-3227]."""
    T = template(db, s, **WEEKLY)
    B = mk_order(db, s, "b", work_order_template_id=T.id, planned_date=D(11))
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    V = inv(db, s, A, confirmed=True, linked=True)
    cp = commit_point(db)
    before_a, before_b, before_v = snap(db, A), snap(db, B), snap(db, V)
    msg = BULKCONF(A)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _bulk(db, s, T)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == msg
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, A) == before_a
    # Then 6
    assert snap(db, B) == before_b
    # Then 7
    assert snap(db, V) == before_v
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_wos_b_08__confirmed_invoice_never_touched(db, s):
    """WOS-B-08 — a confirmed invoice is never deleted or changed by the bulk delete (today and after the fix).
    Rules: bulk_delete_future_recurrence_drafts B3."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    V = inv(db, s, A, confirmed=True, linked=True)
    pay(db, s, V, "50.00")
    commit_point(db)
    vid = V.id
    before_v = snap(db, V)
    try:
        _bulk(db, s, T)
    except HTTPException:
        pass
    # Then 1
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 2
    assert count_where(db, InvoicePayment, InvoicePayment.invoice_id == vid) == 1


@xf(3227)
def test_wos_b_09__voided_invoice_refuses_too(db, s):
    """WOS-B-09 — a voided invoice still linked refuses the call too.
    Rules: bulk_delete_future_recurrence_drafts B3 [BUG-3227]."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    inv(db, s, A, voided_inv=True, linked=True)
    cp = commit_point(db)
    before_a = snap(db, A)
    msg = BULKCONF(A)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _bulk(db, s, T)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == msg
    # Then 4
    assert snap(db, A) == before_a
    # Then 5
    assert counts(db) == cp.counts


@xf(3227)
def test_wos_b_10__two_refusing_first_by_planned_date(db, s):
    """WOS-B-10 — two refusing drafts: the message names the first in planned-date order.
    Rules: bulk_delete_future_recurrence_drafts B2, B3 [BUG-3227]."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    inv(db, s, A, confirmed=True, linked=True)
    B = mk_order(db, s, "b", outside=True, work_order_template_id=T.id, planned_date=D(11))
    inv(db, s, B, confirmed=True, linked=True)
    commit_point(db)
    before_a, before_b = snap(db, A), snap(db, B)
    msg = BULKCONF(B)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _bulk(db, s, T)
    # Then 2
    assert exc.value.detail == msg
    # Then 3
    assert snap(db, A) == before_a
    # Then 4
    assert snap(db, B) == before_b


def test_wos_b_11__w2_invoice_left_alone(db, s):
    """WOS-B-11 — an invoice of W2 linked to a draft is left alone; the draft is deleted.
    Rules: bulk_delete_future_recurrence_drafts B1, B3 (gap log G5); HR-16."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    V = inv(db, s, A, ws="2", confirmed=True, linked=True)
    cp = commit_point(db)
    aid, vid = A.id, V.id
    before_v = snap(db, V)
    result = _bulk(db, s, T)
    # Then 1
    assert result.deleted_ids == [aid]
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, aid).is_deleted is True
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert reread(db, WorkOrder, aid).invoice_id == vid
    # Then 5
    assert [e for e in ev(db, cp, aid) if e[0] == "invoice_voided"] == []


@xf(3227)
def test_wos_b_12__refused_call_keeps_plain_draft(db, s):
    """WOS-B-12 — a refused bulk call keeps the plain draft too.
    Rules: bulk_delete_future_recurrence_drafts B3 [BUG-3227]; TC3."""
    T = template(db, s, **WEEKLY)
    B = mk_order(db, s, "b", work_order_template_id=T.id, planned_date=D(11))
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    inv(db, s, A, voided_inv=True, linked=True)
    commit_point(db)
    bid = B.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException):
        _bulk(db, s, T)
    # Then 2
    assert X not in db
    db.rollback()
    # Then 3
    assert reread(db, WorkOrder, bid).is_deleted is False
    # Then 4
    assert x_gone(db, x_id)


def test_wos_b_13__w0_draft_invoice_not_deleted(db, s):
    """WOS-B-13 — a draft invoice of W0 linked to a draft is not deleted; the draft is deleted.
    Rules: bulk_delete_future_recurrence_drafts B1, B3 (gap log G5); HR-16."""
    T = template(db, s, **WEEKLY)
    A = mk_order(db, s, "a", outside=True, work_order_template_id=T.id, planned_date=D(12))
    V = inv(db, s, A, ws="0", linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    aid, vid = A.id, V.id
    before_v = snap(db, V)
    result = _bulk(db, s, T)
    # Then 1
    assert result.deleted_ids == [aid]
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, aid).is_deleted is True
    # Then 3
    assert reread(db, WorkOrder, aid).invoice_id == vid
    # Then 4
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 5
    assert [(i.description, i.unit_price) for i in LINES(db, vid)] == [("Old line", Decimal("100.00"))]
    # Then 6
    assert [e for e in ev(db, cp, aid) if e[0] == "invoice_voided"] == []


# --------------------------------------------------------------------------- #
# sheet_entry
# --------------------------------------------------------------------------- #


def _replan_template(db, s):
    """SE-06 ... SE-10: weekly template anchored 2 March, end 16 March, next 23 March."""
    return template(
        db, s, **WEEKLY, recurrence_start_date=D(2), recurrence_end_date=D(16), next_generation_date=D(23),
    )


def _replan(db, s, T):
    return svc.sheet_entry(
        db, data=SHEET(s, planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )


def test_wos_se_01__entry_committed_no_invoice(db, s):
    """WOS-SE-01 — an entry is committed and returned re-read; no invoice even with a cost.
    Rules: sheet_entry SE1, SE2; TC1, TC2."""
    commit_point(db)
    result = svc.sheet_entry(db, data=SHEET(s, cost=Decimal("300.00")), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, rid)
    assert row.machine_id == s.M1.id
    assert row.planned_date == D(12)
    assert row.cost == Decimal("300.00")
    assert row.invoice_id is None
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == rid) == 0
    # Then 5
    assert notes(db) == []


def test_wos_se_02__entry_approvers_not_notified(db, s):
    """WOS-SE-02 — approvers named in the entry are not notified.
    Rules: sheet_entry SE2."""
    commit_point(db)
    result = svc.sheet_entry(
        db, data=SHEET(s, approvers=[{"user_id": s.U3.id}]), workspace_id=s.W1.id, user_id=s.U2.id,
    )
    # Then 1
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 2
    assert [a.user_id for a in rows_where(db, WorkOrderApprover, WorkOrderApprover.work_order_id == rid)] == [s.U3.id]
    # Then 3
    assert notes(db) == []


def test_wos_se_03__w2_machine_404(db, s):
    """WOS-SE-03 — a machine of W2: the manager's 404, the extra row is gone.
    Rules: sheet_entry SE1; TC3; HR-16."""
    cp = commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.sheet_entry(db, data=SHEET(s, machine_id=s.M9.id), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_se_04__recurrence_refusal_saves_nothing(db, s):
    """WOS-SE-04 — a refusal from the recurrence step saves no order.
    Rules: sheet_entry SE1; TC3."""
    T = template(db, s, **WEEKLY)
    commit_point(db)
    before_t = snap(db, T)
    tid = T.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.sheet_entry(db, data=SHEET(s, planned_date=D(2), template_id=tid), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "recurrence_end_date is required when placing an unanchored recurring template"
    # Then 4
    assert X not in db
    # Then 5
    assert _wo_count(db, s.W1.id) == 0
    # Then 6
    assert snap_id(db, WorkOrderTemplate, tid) == before_t
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_se_05__failing_commit_saves_nothing(db, s):
    """WOS-SE-05 — a failing commit saves no order.
    Rules: sheet_entry SE1; TC4."""
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.sheet_entry(db, data=SHEET(s), workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert _wo_count(db, s.W1.id) == 0


@xf(3227)
def test_wos_se_06__replan_deletes_dropped_draft_invoice(db, s):
    """WOS-SE-06 — a re-plan that drops a draft deletes and unlinks its draft invoice.
    Rules: sheet_entry SE3 [BUG-3227]."""
    T = _replan_template(db, s)
    mk_order(db, s, "9", work_order_template_id=T.id, planned_date=D(9))
    O16 = mk_order(db, s, "16", outside=True, work_order_template_id=T.id, planned_date=D(16))
    V = inv(db, s, O16, linked=True)
    invl(db, s, V, "100.00")
    V_ID = V.id
    cp = commit_point(db)
    o16, num = O16.id, NUM(O16)
    result = _replan(db, s, T)
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, o16).is_deleted is True
    # Then 3
    assert gone(db, AccountInvoice, V_ID)
    # Then 4
    assert reread(db, WorkOrder, o16).invoice_id is None
    # Then 5
    assert ev(db, cp, o16) == [("invoice_voided", f"Invoice unlinked — work order {num} deleted")]
    # Then 6
    assert evrow(db, cp, o16, "invoice_voided").metadata_json == {"invoice_id": V_ID}
    assert evrow(db, cp, o16, "invoice_voided").performed_by == s.U2.id


def test_wos_se_07__replan_still_drops_draft_with_draft_invoice(db, s):
    """WOS-SE-07 — a re-plan still drops the draft that has a draft invoice (today and after the fix).
    Rules: sheet_entry SE1, SE3."""
    T = _replan_template(db, s)
    O9 = mk_order(db, s, "9", work_order_template_id=T.id, planned_date=D(9))
    O16 = mk_order(db, s, "16", outside=True, work_order_template_id=T.id, planned_date=D(16))
    inv(db, s, O16, linked=True)
    commit_point(db)
    o9, o16 = O9.id, O16.id
    result = _replan(db, s, T)
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, o16)
    assert row.is_deleted is True
    assert row.deleted_by == s.U2.id
    # Then 3
    assert reread(db, WorkOrder, o9).is_deleted is False


@xf(3227)
def test_wos_se_08__confirmed_invoice_refuses_entry(db, s):
    """WOS-SE-08 — a dropped draft with a confirmed invoice refuses the whole entry.
    Rules: sheet_entry SE3 [BUG-3227]."""
    T = _replan_template(db, s)
    mk_order(db, s, "9", work_order_template_id=T.id, planned_date=D(9))
    O16 = mk_order(db, s, "16", outside=True, work_order_template_id=T.id, planned_date=D(16))
    V = inv(db, s, O16, confirmed=True, linked=True)
    cp = commit_point(db)
    before_o, before_t, before_v = snap(db, O16), snap(db, T), snap(db, V)
    msg = BULKCONF(O16)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _replan(db, s, T)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == msg
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O16) == before_o
    # Then 6
    assert snap(db, T) == before_t
    # Then 7
    assert snap(db, V) == before_v
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_wos_se_09__confirmed_invoice_never_changed_by_replan(db, s):
    """WOS-SE-09 — a confirmed invoice is never changed by a re-plan (today and after the fix).
    Rules: sheet_entry SE3."""
    T = _replan_template(db, s)
    O16 = mk_order(db, s, "16", outside=True, work_order_template_id=T.id, planned_date=D(16))
    V = inv(db, s, O16, confirmed=True, linked=True)
    commit_point(db)
    vid = V.id
    before_v = snap(db, V)
    try:
        _replan(db, s, T)
    except HTTPException:
        pass
    # Then 1
    assert snap_id(db, AccountInvoice, vid) == before_v


def test_wos_se_10__replan_w2_invoice_left_alone(db, s):
    """WOS-SE-10 — a re-plan drops a draft whose linked invoice is of W2; the invoice is left alone.
    Rules: sheet_entry SE1, SE3 (gap log G5); HR-16."""
    T = _replan_template(db, s)
    mk_order(db, s, "9", work_order_template_id=T.id, planned_date=D(9))
    O16 = mk_order(db, s, "16", outside=True, work_order_template_id=T.id, planned_date=D(16))
    V = inv(db, s, O16, ws="2", confirmed=True, linked=True)
    cp = commit_point(db)
    o16, vid = O16.id, V.id
    before_v = snap(db, V)
    result = _replan(db, s, T)
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, o16).is_deleted is True
    # Then 3
    assert reread(db, WorkOrder, o16).invoice_id == vid
    # Then 4
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 5
    assert [e for e in ev(db, cp, o16) if e[0] == "invoice_voided"] == []


# --------------------------------------------------------------------------- #
# list_sheet_bundles
# --------------------------------------------------------------------------- #


def test_wos_sb_01__one_bundle_per_order(db, s):
    """WOS-SB-01 — one bundle per order with its mapped order, lines, approvers and summary.
    Rules: list_sheet_bundles SB1, SB2."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L1 = line(db, s, O, s.I1, "2")
    L2 = line(db, s, O, s.I2, "1")
    approver(db, s, O, s.U1, approved=True, approver_slot="QA")
    assignee(db, s, O, s.U3)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    b = result.items[0]
    a = b.approvers.approvers[0]
    sm = b.approvers.summary
    # Then 1
    assert type(result).__name__ == "WorkOrderSheetListResponse"
    assert type(b.approvers).__name__ == "WorkOrderApproversList"
    # Then 2
    assert result.total == 1
    assert len(result.items) == 1
    # Then 3
    assert b.order.id == O.id
    assert b.order.assignee_user_ids == [s.U3.id]
    # Then 4
    assert {i.id for i in b.items} == {L1.id, L2.id}
    assert len(b.items) == 2
    assert type(b.items[0]).__name__ == "WorkOrderItemResponse"
    # Then 5
    assert a.user_name == "Karim Ahmed"
    assert a.user_email == s.U1.email
    assert a.user_position == "Supervisor"
    assert a.approver_slot == "QA"
    # Then 6
    assert a.approved is True
    assert a.approved_at == T0
    assert a.assigned_by == s.U1.id
    assert a.assigned_at == T0
    # Then 7
    assert sm.approved_count == 1
    assert sm.required == 1
    assert sm.met is True


def test_wos_sb_02__approver_without_profile(db, s):
    """WOS-SB-02 — an approver without a profile shows no name or e-mail.
    Rules: list_sheet_bundles SB2."""
    O = mk_order(db, s, "1")
    AP = approver(db, s, O, s.U2)
    commit_point(db)
    with patch.object(svc.manager, "list_approvers", return_value=[(AP, None, None)]):
        result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    a = result.items[0].approvers.approvers[0]
    # Then 1
    assert a.user_name is None
    assert a.user_email is None
    assert a.user_position is None
    # Then 2
    assert a.approved is False


def test_wos_sb_03__member_without_position(db, s):
    """WOS-SB-03 — a member without a position shows None as position.
    Rules: list_sheet_bundles SB2."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U2)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    a = result.items[0].approvers.approvers[0]
    # Then 1
    assert a.user_name == "Rahim Uddin"
    assert a.user_position is None


def test_wos_sb_04__only_live_lines(db, s):
    """WOS-SB-04 — only live lines are bundled (compared as a set, BUG-1272).
    Rules: list_sheet_bundles SB2."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L1 = line(db, s, O, s.I1, "1")
    line(db, s, O, s.I2, "1", gone=True)
    L3 = line(db, s, O, s.I1, "3")
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert {i.id for i in result.items[0].items} == {L1.id, L3.id}
    assert len(result.items[0].items) == 2


def _orders(db, s, n):
    """Convention "n orders: order "k" for k = 1 ... n"."""
    return [mk_order(db, s, str(k)) for k in range(1, n + 1)]


def test_wos_sb_05__sixty_default_page(db, s):
    """WOS-SB-05 — 60 matching, default skip and limit: 50 items, echoed, has_more true.
    Rules: list_sheet_bundles SB1, SB3."""
    _orders(db, s, 60)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert result.total == 60
    assert len(result.items) == 50
    # Then 2
    assert result.skip == 0
    assert result.limit == 50
    # Then 3
    assert result.has_more is True
    # Then 4
    assert [b.order.id for b in result.items] == [
        o.id for o in WOM.list_sheet_orders(db, workspace_id=s.W1.id, skip=0, limit=50)
    ]


def test_wos_sb_06__skip_50_of_60(db, s):
    """WOS-SB-06 — skip 50 of 60: 10 items, has_more false.
    Rules: list_sheet_bundles SB3."""
    _orders(db, s, 60)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id, skip=50, limit=50)
    # Then 1
    assert result.total == 60
    assert len(result.items) == 10
    assert result.skip == 50
    # Then 2
    assert result.has_more is False


def test_wos_sb_07__skip_49_limit_10(db, s):
    """WOS-SB-07 — skip 49 of 60 with limit 10: has_more true.
    Rules: list_sheet_bundles SB3."""
    _orders(db, s, 60)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id, skip=49, limit=10)
    # Then 1
    assert len(result.items) == 10
    assert result.limit == 10
    # Then 2
    assert result.has_more is True


def test_wos_sb_08__skip_beyond_total(db, s):
    """WOS-SB-08 — skip beyond the total: no items, has_more false.
    Rules: list_sheet_bundles SB3."""
    _orders(db, s, 3)
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id, skip=70, limit=50)
    # Then 1
    assert result.total == 3
    assert result.items == []
    assert result.skip == 70
    # Then 2
    assert result.has_more is False


def test_wos_sb_09__no_match(db, s):
    """WOS-SB-09 — no match: total 0, no items, has_more false.
    Rules: list_sheet_bundles SB1, SB3."""
    mk_order(db, s, "1")
    commit_point(db)
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id, machine_id=s.M2.id)
    # Then 1
    assert result.total == 0
    assert result.items == []
    # Then 2
    assert result.has_more is False


def test_wos_sb_10__w0_w2_not_listed(db, s):
    """WOS-SB-10 — orders of W0 and W2 are neither counted nor listed.
    Rules: list_sheet_bundles SB1; HR-16."""
    mk_order(db, s, "0", ws="0")
    O = mk_order(db, s, "1")
    mk_order(db, s, "9", ws="2")
    commit_point(db)
    oid = O.id
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert result.total == 1
    # Then 2
    assert [b.order.id for b in result.items] == [oid]


def test_wos_sb_11__one_enrichment_per_page(db, s):
    """WOS-SB-11 — one enrichment serves the whole page.
    Rules: list_sheet_bundles SB2."""
    _orders(db, s, 3)
    commit_point(db)
    with Recorder(db) as rec:
        result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result.items) == 3
    # Then 2
    assert len([st for st in rec.names("work_order_assignees") if st.lstrip().upper().startswith("SELECT")]) == 1


def test_wos_sb_12__sheet_no_commit_no_rollback(db, s):
    """WOS-SB-12 — the sheet neither commits nor rolls back.
    Rules: list_sheet_bundles SB4; TC6."""
    mk_order(db, s, "1")
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert result.total == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_sb_13__completed_listed_by_default(db, s):
    """WOS-SB-13 — without `exclude_completed` a completed order is listed (default False).
    Rules: list_sheet_bundles SB1."""
    O = mk_order(db, s, "1")
    K = mk_order(db, s, "2", completed=True)
    commit_point(db)
    ids = {O.id, K.id}
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id)
    # Then 1
    assert result.total == 2
    # Then 2
    assert {b.order.id for b in result.items} == ids


def test_wos_sb_14__exclude_completed_passed(db, s):
    """WOS-SB-14 — `exclude_completed=True` is passed on.
    Rules: list_sheet_bundles SB1."""
    O = mk_order(db, s, "1")
    mk_order(db, s, "2", completed=True)
    commit_point(db)
    oid = O.id
    result = svc.list_sheet_bundles(db, workspace_id=s.W1.id, exclude_completed=True)
    # Then 1
    assert result.total == 1
    # Then 2
    assert [b.order.id for b in result.items] == [oid]


# --------------------------------------------------------------------------- #
# sheet_daily_counts
# --------------------------------------------------------------------------- #


def test_wos_sd_01__manager_map_by_iso_date(db, s):
    """WOS-SD-01 — the manager's map by ISO date; neither commits nor rolls back.
    Rules: sheet_daily_counts SD1; TC6."""
    mk_order(db, s, "1")
    mk_order(db, s, "2")
    mk_order(db, s, "3", planned_date=D(13))
    mk_order(db, s, "9", ws="2")
    commit_point(db)
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.sheet_daily_counts(db, workspace_id=s.W1.id)
    # Then 1
    assert type(result).__name__ == "WorkOrderSheetDailyCountsResponse"
    # Then 2
    assert result.counts == {"2026-03-12": 2, "2026-03-13": 1}
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert X in db


def test_wos_sd_02__no_orders_empty_map(db, s):
    """WOS-SD-02 — no orders: an empty map.
    Rules: sheet_daily_counts SD1."""
    commit_point(db)
    result = svc.sheet_daily_counts(db, workspace_id=s.W1.id)
    # Then 1
    assert result.counts == {}


def test_wos_sd_03__filter_passed(db, s):
    """WOS-SD-03 — a filter is passed on.
    Rules: sheet_daily_counts SD1."""
    mk_order(db, s, "1")
    mk_order(db, s, "2", machine_id=s.M2.id, planned_date=D(13))
    commit_point(db)
    result = svc.sheet_daily_counts(db, workspace_id=s.W1.id, machine_id=s.M2.id)
    # Then 1
    assert result.counts == {"2026-03-13": 1}


# --------------------------------------------------------------------------- #
# delete_work_order
# --------------------------------------------------------------------------- #


def _delete(db, s, oid):
    return svc.delete_work_order(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id)


def test_wos_x_01__soft_deleted_committed(db, s):
    """WOS-X-01 — an order without an invoice is soft-deleted and committed; nobody told.
    Rules: delete_work_order X1, X4; TC1, TC2."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    result = _delete(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.is_deleted is True
    assert row.deleted_by == s.U2.id
    # Then 4
    assert notes(db) == []


def test_wos_x_02__missing_404(db, s):
    """WOS-X-02 — a missing order: 404, the extra row is gone.
    Rules: delete_work_order X1; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _delete(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_x_03__already_deleted_400(db, s):
    """WOS-X-03 — an already deleted order: 400, nothing written.
    Rules: delete_work_order X1."""
    O = mk_order(db, s, "1", gone=True)
    commit_point(db)
    before = snap(db, O)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, O.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is already deleted"
    # Then 4
    assert snap(db, O) == before


def test_wos_x_04__w2_order_404(db, s):
    """WOS-X-04 — another workspace's order (W2): 404, not deleted.
    Rules: delete_work_order X1; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, Z)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, zid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)
    # Then 4
    assert snap(db, Z) == before


def test_wos_x_05__failing_commit_keeps_order(db, s):
    """WOS-X-05 — a failing commit keeps the order.
    Rules: delete_work_order X1; TC4."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _delete(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, oid).is_deleted is False


@xf(2923)
def test_wos_x_06__draft_invoice_deleted_and_unlinked(db, s):
    """WOS-X-06 — a linked draft invoice is deleted with its lines and events and unlinked, with an event.
    Rules: delete_work_order X2 [BUG-2923]."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("2000.00"))
    V = inv(db, s, O, invoice_amount=Decimal("2000.00"), linked=True)
    invl(db, s, V, "2000.00")
    V_ID = V.id
    cp = commit_point(db)
    oid, num = O.id, NUM(O)
    result = _delete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).is_deleted is True
    # Then 3
    assert gone(db, AccountInvoice, V_ID)
    # Then 4
    assert reread(db, WorkOrder, oid).invoice_id is None
    # Then 5
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == V_ID) == 0
    # Then 6
    assert itypes(db, V_ID) == []
    # Then 7
    assert ev(db, cp, oid) == [("invoice_voided", f"Invoice unlinked — work order {num} deleted")]
    # Then 8
    assert evrow(db, cp, oid, "invoice_voided").metadata_json == {"invoice_id": V_ID}
    assert evrow(db, cp, oid, "invoice_voided").performed_by == s.U2.id


def test_wos_x_07__order_with_draft_invoice_still_deleted(db, s):
    """WOS-X-07 — an order with a linked draft invoice is still deleted (today and after the fix).
    Rules: delete_work_order X1, X2."""
    O = mk_order(db, s, "1", outside=True)
    inv(db, s, O, linked=True)
    commit_point(db)
    oid = O.id
    result = _delete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.is_deleted is True
    assert row.deleted_by == s.U2.id


@xf(2923)
def test_wos_x_08__payment_history_refuses(db, s):
    """WOS-X-08 — a draft invoice with payment history refuses the delete; nothing saved.
    Rules: delete_work_order X2 [BUG-2923]."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    P = pay(db, s, V, "100.00")
    cp = commit_point(db)
    before_o, before_v, before_p = snap(db, O), snap(db, V), snap(db, P)
    oid, vid = O.id, V.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == PAYHIST
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before_o
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert snap(db, P) == before_p
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)
    # Then 9
    assert reread(db, WorkOrder, oid).invoice_id == vid
    # Then 10
    assert [e for e in ev(db, cp, oid) if e[0] == "invoice_voided"] == []


@xf(2923)
def test_wos_x_09__confirmed_invoice_refuses(db, s):
    """WOS-X-09 — a confirmed invoice refuses the delete; nothing written.
    Rules: delete_work_order X3 [BUG-2923]."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid, vid = O.id, V.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == CONFDEL
    # Then 4
    assert X not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, O) == before_o
    # Then 7
    assert snap(db, V) == before_v
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)
    # Then 10
    assert reread(db, WorkOrder, oid).invoice_id == vid
    # Then 11
    assert [e for e in ev(db, cp, oid) if e[0] == "invoice_voided"] == []


def test_wos_x_10__confirmed_invoice_never_touched(db, s):
    """WOS-X-10 — a confirmed invoice is never deleted or changed by the delete (today and after the fix).
    Rules: delete_work_order X3."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    pay(db, s, V, "50.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    try:
        _delete(db, s, oid)
    except HTTPException:
        pass
    # Then 1
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 2
    assert count_where(db, InvoicePayment, InvoicePayment.invoice_id == vid) == 1


@xf(2923)
def test_wos_x_11__voided_invoice_refuses(db, s):
    """WOS-X-11 — a voided invoice still linked refuses the delete too.
    Rules: delete_work_order X3 [BUG-2923]."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, voided_inv=True, linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid, vid = O.id, V.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == CONFDEL
    # Then 4
    assert snap(db, O) == before_o
    # Then 5
    assert snap(db, V) == before_v
    db.rollback()
    # Then 6
    assert reread(db, WorkOrder, oid).invoice_id == vid
    # Then 7
    assert [e for e in ev(db, cp, oid) if e[0] == "invoice_voided"] == []


def test_wos_x_12__w2_invoice_left_alone(db, s):
    """WOS-X-12 — a linked invoice of W2 is left alone and the delete goes ahead.
    Rules: delete_work_order X3; HR-16."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, ws="2", confirmed=True, linked=True)
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _delete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).is_deleted is True
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v


def test_wos_x_13__w0_invoice_left_alone(db, s):
    """WOS-X-13 — a linked invoice of W0 is left alone and the delete goes ahead.
    Rules: delete_work_order X3; HR-16."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, ws="0", linked=True)
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _delete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).is_deleted is True
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v


def test_wos_x_14__manager_checks_first(db, s):
    """WOS-X-14 — the manager's checks come first: an already deleted order keeps its draft invoice.
    Rules: delete_work_order X1, X2."""
    O = mk_order(db, s, "1", outside=True, gone=True)
    V = inv(db, s, O, linked=True)
    cp = commit_point(db)
    before_v = snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _delete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is already deleted"
    # Then 4
    assert snap(db, V) == before_v
    # Then 5
    assert counts(db) == cp.counts


# --------------------------------------------------------------------------- #
# start_work_order
# --------------------------------------------------------------------------- #


def _start(db, s, oid):
    return svc.start_work_order(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id)


def test_wos_s_01__draft_started_committed(db, s):
    """WOS-S-01 — a draft with an account and no invoice is started and committed; nobody told.
    Rules: start_work_order S1, S2; TC1, TC2."""
    O = mk_order(db, s, "1", outside=True)
    status_row(db, s, s.M1, "RUNNING", T0)
    commit_point(db)
    oid = O.id
    result = _start(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "IN_PROGRESS"
    assert row.started_by == s.U2.id
    assert row.started_at == NOW
    assert row.invoice_id is None
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 0
    # Then 5
    assert notes(db) == []


def test_wos_s_02__insufficient_stock_saves_nothing(db, s):
    """WOS-S-02 — a line that cannot be consumed saves nothing; the extra row is gone.
    Rules: start_work_order S1; TC3."""
    B1 = stock(db, s, s.I1, 10, Decimal("2.50"))
    B2 = stock(db, s, s.I2, 2, Decimal("5.00"))
    O = mk_order(db, s, "1", uses_inventory=True)
    status_row(db, s, s.M1, "RUNNING", T0)
    line(db, s, O, s.I1, "3")
    line(db, s, O, s.I2, "5")
    cp = commit_point(db)
    before = snap(db, O)
    oid, b1, b2 = O.id, B1.id, B2.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _start(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Insufficient stock (2 available, 5 requested)"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, O) == before
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)
    # Then 9
    assert reread(db, Inventory, b1).qty == 10
    assert reread(db, Inventory, b2).qty == 2


def test_wos_s_03__started_order_400(db, s):
    """WOS-S-03 — a started order: the manager's 400 passes unchanged.
    Rules: start_work_order S1."""
    O = mk_order(db, s, "1", started=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order must be in draft to be started"
    # Then 4
    assert snap(db, O) == before


def test_wos_s_04__failing_commit_keeps_draft(db, s):
    """WOS-S-04 — a failing commit keeps the order a draft.
    Rules: start_work_order S1; TC4."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _start(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "DRAFT"
    assert row.started_by is None


# --------------------------------------------------------------------------- #
# complete_work_order
# --------------------------------------------------------------------------- #


def _complete(db, s, oid, **k):
    return svc.complete_work_order(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id, **k)


def test_wos_c_01__started_with_draft_invoice_completed(db, s):
    """WOS-C-01 — a started order with a draft invoice is completed and committed.
    Rules: complete_work_order C7, C10; TC1, TC2."""
    O = mk_order(db, s, "1", started=True, outside=True, cost=Decimal("750.50"))
    ran(db, s, O)
    V = inv(db, s, O, invoice_amount=Decimal("750.50"), linked=True)
    invl(db, s, V, "750.50")
    cp = commit_point(db)
    oid, vid, num = O.id, V.id, NUM(O)
    result = _complete(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "COMPLETED"
    assert row.completed_by == s.U2.id
    assert row.completed_at == NOW
    assert row.invoice_id == vid
    # Then 4
    assert ("completed", f"Work order {num} marked complete") in ev(db, cp, oid)


def test_wos_c_02__draft_confirmed_at_line_sum(db, s):
    """WOS-C-02 — the draft is confirmed at its line sum, with the `confirmed` event.
    Rules: complete_work_order C7."""
    O = mk_order(db, s, "1", started=True, outside=True, cost=Decimal("750.50"))
    ran(db, s, O)
    V = inv(db, s, O, invoice_amount=Decimal("0.00"), linked=True)
    invl(db, s, V, "750.50")
    commit_point(db)
    oid, vid = O.id, V.id
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("750.50")
    # Then 3
    assert itypes(db, vid)[-1] == "confirmed"


def test_wos_c_03__confirmed_notice_recipients(db, s):
    """WOS-C-03 — the confirmed notice goes to the creator and every approver, active members only.
    Rules: complete_work_order C7."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    approver(db, s, O, s.U3, approved=True)
    approver(db, s, O, s.U4, approved=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid = O.id
    preview = CONFP(O)
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id, s.U3.id]
    # Then 3
    for n in notes(db):
        assert n.notification_type == "invoice_action"
        assert n.entity_type == "work_order"
        assert n.entity_id == oid
    # Then 4
    for n in notes(db):
        assert n.preview == preview


def test_wos_c_04__completed_returned_as_is(db, s):
    """WOS-C-04 — an already completed order is returned as it is: no write, no commit, no rollback.
    Rules: complete_work_order C2."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert snap(db, O) == before_o
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert ev(db, cp, oid) == []
    # Then 8
    assert notes(db) == []


def test_wos_c_05__completed_no_invoice_returned(db, s):
    """WOS-C-05 — a completed order with an account and no invoice is returned without the invoice check.
    Rules: complete_work_order C2."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    assert result.status == "COMPLETED"
    # Then 2
    assert snap(db, O) == before


def test_wos_c_06__draft_400(db, s):
    """WOS-C-06 — a draft: 400, nothing written, the extra row is gone.
    Rules: complete_work_order C3; TC3."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INPROG
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before_o
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_wos_c_07__voided_400(db, s):
    """WOS-C-07 — a voided order: 400, nothing written.
    Rules: complete_work_order C3."""
    O = mk_order(db, s, "1", voided=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INPROG
    # Then 4
    assert snap(db, O) == before


def test_wos_c_08__account_no_invoice_400(db, s):
    """WOS-C-08 — an account and no invoice: 400 asking for an invoice.
    Rules: complete_work_order C4."""
    O = mk_order(db, s, "1", started=True, outside=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOINV
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_c_09__w2_invoice_not_found(db, s):
    """WOS-C-09 — the linked invoice is a W2 invoice: "Linked invoice not found", no id shown.
    Rules: complete_work_order C5; HR-16."""
    O = mk_order(db, s, "1", started=True, outside=True)
    V = inv(db, s, O, ws="2", linked=True)
    commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INVNF
    # Then 4
    assert snap(db, O) == before_o
    # Then 5
    assert snap(db, V) == before_v


def test_wos_c_10__w0_invoice_not_found(db, s):
    """WOS-C-10 — the linked invoice is a W0 invoice: "Linked invoice not found".
    Rules: complete_work_order C5; HR-16."""
    O = mk_order(db, s, "1", started=True, outside=True)
    V = inv(db, s, O, ws="0", linked=True)
    commit_point(db)
    before_v = snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INVNF
    # Then 4
    assert snap(db, V) == before_v


def test_wos_c_11__voided_invoice_400(db, s):
    """WOS-C-11 — the linked invoice was voided: 400, nothing written.
    Rules: complete_work_order C6."""
    O = mk_order(db, s, "1", started=True, outside=True)
    V = inv(db, s, O, voided_inv=True, linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == VOIDINV
    # Then 4
    assert snap(db, O) == before_o
    # Then 5
    assert snap(db, V) == before_v
    # Then 6
    assert counts(db) == cp.counts


@xf(628)
def test_wos_c_12__empty_draft_cannot_be_confirmed(db, s):
    """WOS-C-12 — a draft with no lines cannot be confirmed: 400, the order is not completed.
    Rules: complete_work_order C7, Errors row C7 [BUG-628] (invoice manager pass-through)."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, invoice_amount=Decimal("0.00"), linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOLINES
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before_o
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_wos_c_13__confirmed_invoice_left(db, s):
    """WOS-C-13 — an invoice already confirmed is left as it is; the order is completed, nobody told.
    Rules: complete_work_order C8."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, confirmed=True, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).status == "COMPLETED"
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert itypes(db, vid).count("confirmed") == 0
    # Then 5
    assert notes(db) == []


def test_wos_c_14__no_account_draft_invoice_ignored(db, s):
    """WOS-C-14 — without an account a linked draft invoice is not looked at.
    Rules: complete_work_order C9."""
    O = mk_order(db, s, "1", started=True)
    ran(db, s, O)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.status == "COMPLETED"
    assert row.invoice_id == vid
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert notes(db) == []


def test_wos_c_15__no_account_no_invoice_completes(db, s):
    """WOS-C-15 — without an account and without an invoice the order completes.
    Rules: complete_work_order C9, C10."""
    O = mk_order(db, s, "1", started=True)
    ran(db, s, O)
    commit_point(db)
    oid = O.id
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.status == "COMPLETED"
    assert row.invoice_id is None
    # Then 3
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 0
    # Then 4
    assert notes(db) == []


def test_wos_c_16__completion_refusal_undoes_confirm(db, s):
    """WOS-C-16 — a refusal in the completion undoes the invoice confirm and its notices.
    Rules: complete_work_order C10; TC3."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _complete(db, s, oid, completed_by_user_ids=[s.U4.id])
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTMEMBER
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert snap(db, O) == before_o
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_wos_c_17__notes_workers_performer_passed(db, s):
    """WOS-C-17 — notes, workers and the performer are passed to the completion.
    Rules: complete_work_order C10."""
    O = mk_order(db, s, "1", started=True)
    ran(db, s, O)
    cp = commit_point(db)
    oid = O.id
    result = _complete(db, s, oid, completion_notes="Pump rebuilt", completed_by_user_ids=[s.U3.id])
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.completion_notes == "Pump rebuilt"
    assert row.completed_by_names == "Sara Khan"
    # Then 3
    assert [c.user_id for c in rows_where(db, WorkOrderCompleter, WorkOrderCompleter.work_order_id == oid)] == [s.U3.id]
    # Then 4
    assert evrow(db, cp, oid, "completed").performed_by == s.U2.id


@pytest.mark.parametrize(
    "ms, expected",
    [
        pytest.param("IDLE", ["IDLE"], id="WOS-C-18"),
        pytest.param("OFF", ["OFF"], id="WOS-C-19"),
        pytest.param("", ["RUNNING"], id="WOS-C-20"),
        pytest.param(None, ["RUNNING"], id="WOS-C-21"),
    ],
)
def test_wos_c_18_21__machine_status(db, s, ms, expected):
    """WOS-C-18 … WOS-C-21 — machine status "IDLE" / "OFF" is used; empty or none restores the status before start.
    Rules: complete_work_order C11."""
    O = mk_order(db, s, "1", started=True)
    ran(db, s, O)
    cp = commit_point(db)
    oid = O.id
    result = _complete(db, s, oid, machine_status=ms)
    # Then 1
    assert result.id == oid
    # Then 2
    assert stat(db, cp, s.M1.id) == expected


def test_wos_c_22__unknown_machine_status_valueerror(db, s):
    """WOS-C-22 — an unknown machine status raises ValueError; nothing saved.
    Rules: complete_work_order C11, Errors row C11; TC3."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(ValueError):
        _complete(db, s, oid, machine_status="BROKEN")
    # Then 2
    assert X not in db
    # Then 3
    assert snap(db, O) == before_o
    # Then 4
    assert snap(db, V) == before_v
    # Then 5
    assert counts(db) == cp.counts
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_c_23__pending_approver_does_not_stop(db, s):
    """WOS-C-23 — approvals are not checked: a pending approver does not stop the completion.
    Rules: complete_work_order C12."""
    O = mk_order(db, s, "1", started=True)
    ran(db, s, O)
    approver(db, s, O, s.U3)
    commit_point(db)
    oid = O.id
    result = _complete(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).status == "COMPLETED"


def test_wos_c_24__missing_404(db, s):
    """WOS-C-24 — a missing order: 404, the extra row is gone.
    Rules: complete_work_order C1, Errors row C1; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def test_wos_c_25__w2_order_404(db, s):
    """WOS-C-25 — another workspace's order (W2): 404, not completed.
    Rules: complete_work_order C1; HR-16."""
    Z = mk_order(db, s, "9", ws="2", started=True)
    commit_point(db)
    before = snap(db, Z)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _complete(db, s, zid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)
    # Then 4
    assert snap(db, Z) == before


def test_wos_c_26__failing_commit_saves_neither(db, s):
    """WOS-C-26 — a failing commit saves neither the confirm nor the completion.
    Rules: complete_work_order C10; TC4."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _complete(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, oid).status == "IN_PROGRESS"
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"
    # Then 5
    assert notes(db) == []


@xf(2916)
def test_wos_c_27__row_lock_before_checks(db, s):
    """WOS-C-27 — the order is read with a row lock before any check.
    Rules: complete_work_order C1 [BUG-2916]; HR-10."""
    O = mk_order(db, s, "1", started=True, outside=True)
    ran(db, s, O)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = svc.complete_work_order(db, wo_id=oid, workspace_id=w1, user_id=u2)
    # Then 1
    assert result.id == oid
    # Then 2
    assert rec.lock()
    # Then 3
    assert rec.lock_first()


# --------------------------------------------------------------------------- #
# complete_work_order_as_planned
# --------------------------------------------------------------------------- #


def _plan(db, s, oid, **k):
    return svc.complete_work_order_as_planned(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id, **k)


def test_wos_p_01__past_due_draft_completed_at_noon(db, s):
    """WOS-P-01 — a past-due draft with a draft invoice is started, completed at noon of its day and committed.
    Rules: complete_work_order_as_planned P4, P6; TC1, TC2."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8), cost=Decimal("750.50"))
    status_row(db, s, s.M1, "RUNNING", T0)
    V = inv(db, s, O, invoice_amount=Decimal("0.00"), linked=True)
    invl(db, s, V, "750.50")
    commit_point(db)
    oid, vid = O.id, V.id
    result = _plan(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "COMPLETED"
    assert row.started_at == NOON(8)
    assert row.completed_at == NOON(8)
    assert row.started_by == s.U2.id
    # Then 4
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "confirmed"
    assert v.invoice_amount == Decimal("750.50")


def test_wos_p_02__confirmed_notice_to_creator(db, s):
    """WOS-P-02 — the confirm sends the confirmed notice to the creator.
    Rules: complete_work_order_as_planned P4."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid = O.id
    preview = CONFP(O)
    result = _plan(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id]
    # Then 3
    assert notes(db)[0].notification_type == "invoice_action"
    assert notes(db)[0].preview == preview


def test_wos_p_03__completed_returned_as_is(db, s):
    """WOS-P-03 — an already completed order is returned as it is: no write, no commit, no rollback.
    Rules: complete_work_order_as_planned P2."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = _plan(db, s, oid)
    # Then 1
    assert result.id == oid
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db
    # Then 5
    assert snap(db, O) == before
    # Then 6
    assert ev(db, cp, oid) == []


@xf(3223)
def test_wos_p_04__started_with_account_told_draft(db, s):
    """WOS-P-04 — a started order with an account and no invoice is told it must be a draft.
    Rules: complete_work_order_as_planned P3 [BUG-3223]."""
    O = mk_order(db, s, "1", started=True, outside=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTDRAFT
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


@xf(3223)
def test_wos_p_05__voided_with_account_told_draft(db, s):
    """WOS-P-05 — a voided order with an account and no invoice is told it must be a draft.
    Rules: complete_work_order_as_planned P3 [BUG-3223]."""
    O = mk_order(db, s, "1", voided=True, outside=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.detail == NOTDRAFT
    # Then 3
    assert snap(db, O) == before


@xf(3223)
def test_wos_p_06__started_refused_before_invoice_touched(db, s):
    """WOS-P-06 — a started order with a draft invoice is refused before the invoice is touched.
    Rules: complete_work_order_as_planned P3 [BUG-3223]."""
    O = mk_order(db, s, "1", started=True, outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.complete_work_order_as_planned(db, wo_id=oid, workspace_id=w1, user_id=u2)
    # Then 2
    assert exc.value.detail == NOTDRAFT
    # Then 3
    assert not [st for st in rec.names("account_invoices") if st.lstrip().upper().startswith("UPDATE")]


def test_wos_p_07__started_no_account_told_draft(db, s):
    """WOS-P-07 — a started order without an account: "must be in draft", nothing written (today and after the fix).
    Rules: complete_work_order_as_planned P3, P5; TC3."""
    O = mk_order(db, s, "1", started=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTDRAFT
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_p_08__started_draft_invoice_stays_draft(db, s):
    """WOS-P-08 — a started order's draft invoice stays a draft (today and after the fix).
    Rules: complete_work_order_as_planned P3, P6; TC3."""
    O = mk_order(db, s, "1", started=True, outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    before_v, before_o = snap(db, V), snap(db, O)
    oid = O.id
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 1
    assert exc.value.status_code == 400
    # Then 2
    assert snap(db, V) == before_v
    # Then 3
    assert snap(db, O) == before_o
    # Then 4
    assert notes(db) == []


def test_wos_p_09__draft_account_no_invoice_400(db, s):
    """WOS-P-09 — a draft with an account and no invoice: 400 asking for an invoice.
    Rules: complete_work_order_as_planned P4."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOINV
    # Then 4
    assert snap(db, O) == before
    # Then 5
    assert counts(db) == cp.counts


def test_wos_p_10__w2_invoice_not_found(db, s):
    """WOS-P-10 — the linked invoice is a W2 invoice: "Linked invoice not found".
    Rules: complete_work_order_as_planned P4; HR-16."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, ws="2", linked=True)
    commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INVNF
    # Then 4
    assert snap(db, O) == before_o
    # Then 5
    assert snap(db, V) == before_v


def test_wos_p_11__voided_invoice_400(db, s):
    """WOS-P-11 — the linked invoice was voided: 400.
    Rules: complete_work_order_as_planned P4."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    inv(db, s, O, voided_inv=True, linked=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == VOIDINV
    # Then 4
    assert snap(db, O) == before


def test_wos_p_12__confirmed_invoice_left(db, s):
    """WOS-P-12 — an invoice already confirmed is left; the order completes, nobody told.
    Rules: complete_work_order_as_planned P4."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, confirmed=True, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _plan(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).status == "COMPLETED"
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert notes(db) == []


def test_wos_p_13__no_account_draft_invoice_ignored(db, s):
    """WOS-P-13 — without an account a linked draft invoice is not looked at.
    Rules: complete_work_order_as_planned P5."""
    O = mk_order(db, s, "1", planned_date=D(8))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _plan(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrder, oid).status == "COMPLETED"
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert notes(db) == []


def test_wos_p_14__future_planned_date_refused(db, s):
    """WOS-P-14 — a future planned date is refused and the invoice confirm is undone.
    Rules: complete_work_order_as_planned P6; TC3."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(11))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_v, before_o = snap(db, V), snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Complete as planned is only allowed when the planned date is today or in the past"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, V) == before_v
    # Then 7
    assert snap(db, O) == before_o
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


def test_wos_p_15__no_planned_date_no_invoice_invoice_error(db, s):
    """WOS-P-15 — no planned date and no invoice: the invoice error wins (today and after the fix).
    Rules: complete_work_order_as_planned P4, P6."""
    O = mk_order(db, s, "1", outside=True, planned_date=None)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOINV
    # Then 4
    assert snap(db, O) == before


def test_wos_p_16__unmet_approvals_refused(db, s):
    """WOS-P-16 — unmet approvals are refused and the invoice confirm is undone.
    Rules: complete_work_order_as_planned P6; TC3."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8), approved_by=None, approved_at=None)
    approver(db, s, O, s.U3)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    before_v = snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Assigned approvers must approve before work can be completed"
    # Then 4
    assert snap(db, V) == before_v
    # Then 5
    assert notes(db) == []


def test_wos_p_17__unknown_machine_status_valueerror(db, s):
    """WOS-P-17 — an unknown machine status raises ValueError; nothing saved.
    Rules: complete_work_order_as_planned P7."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(ValueError):
        _plan(db, s, oid, machine_status="BROKEN")
    # Then 2
    assert X not in db
    # Then 3
    assert snap(db, O) == before_o
    # Then 4
    assert snap(db, V) == before_v
    # Then 5
    assert counts(db) == cp.counts
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_p_18__notes_workers_passed(db, s):
    """WOS-P-18 — notes and workers are passed to the manager.
    Rules: complete_work_order_as_planned P6, P7."""
    O = mk_order(db, s, "1", planned_date=D(8))
    status_row(db, s, s.M1, "RUNNING", T0)
    cp = commit_point(db)
    oid = O.id
    result = _plan(
        db, s, oid, completion_notes="Belt replaced", machine_status="OFF", completed_by_user_ids=[s.U3.id],
    )
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.completion_notes == "Belt replaced"
    assert row.completed_by_names == "Sara Khan"
    # Then 3
    assert [c.user_id for c in rows_where(db, WorkOrderCompleter, WorkOrderCompleter.work_order_id == oid)] == [s.U3.id]
    # Then 4
    assert stat(db, cp, s.M1.id)[-1] == "OFF"


def test_wos_p_19__missing_404(db, s):
    """WOS-P-19 — a missing order: 404, the extra row is gone.
    Rules: complete_work_order_as_planned P1; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _plan(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def test_wos_p_20__failing_commit_saves_neither(db, s):
    """WOS-P-20 — a failing commit saves neither the confirm nor the completion.
    Rules: complete_work_order_as_planned P6; TC4."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _plan(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, oid).status == "DRAFT"
    # Then 4
    assert reread(db, AccountInvoice, vid).invoice_status == "draft"


@xf(3222)
def test_wos_p_21__row_lock_before_checks(db, s):
    """WOS-P-21 — the order is read with a row lock before any check.
    Rules: complete_work_order_as_planned P1 [BUG-3222]; HR-10."""
    O = mk_order(db, s, "1", outside=True, planned_date=D(8))
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = svc.complete_work_order_as_planned(db, wo_id=oid, workspace_id=w1, user_id=u2)
    # Then 1
    assert result.id == oid
    # Then 2
    assert rec.lock()
    # Then 3
    assert rec.lock_first()


# --------------------------------------------------------------------------- #
# void_work_order
# --------------------------------------------------------------------------- #


def _void(db, s, oid):
    return svc.void_work_order(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id, void_note="Cancelled")


def test_wos_v_01__voided_committed(db, s):
    """WOS-V-01 — an order without an invoice is voided and committed; nobody told.
    Rules: void_work_order V3, V6, V7; TC1, TC2."""
    O = mk_order(db, s, "1")
    cp = commit_point(db)
    oid, num = O.id, NUM(O)
    result = _void(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "VOIDED"
    assert row.void_note == "Cancelled"
    assert row.voided_by == s.U2.id
    assert row.voided_at == NOW
    # Then 4
    assert ev(db, cp, oid) == [("voided", f"Work order {num} voided. Reason: Cancelled")]
    # Then 5
    assert notes(db) == []


def test_wos_v_02__draft_invoice_deleted_unlinked(db, s):
    """WOS-V-02 — a linked draft invoice is deleted with its lines and events; the order is unlinked.
    Rules: void_work_order V4."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("500.00"))
    V = inv(db, s, O, invoice_amount=Decimal("500.00"), linked=True)
    invl(db, s, V, "500.00")
    V_ID = V.id
    commit_point(db)
    oid = O.id
    result = _void(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    assert gone(db, AccountInvoice, V_ID)
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.invoice_id is None
    assert row.status == "VOIDED"
    # Then 4
    assert count_where(db, InvoiceItem, InvoiceItem.invoice_id == V_ID) == 0
    # Then 5
    assert itypes(db, V_ID) == []
    # Then 6
    assert notes(db) == []


@xf(3229)
def test_wos_v_03__unlink_event_before_voided(db, s):
    """WOS-V-03 — the unlink event comes before the voided event and keeps the deleted invoice's id.
    Rules: void_work_order V4, V4a [BUG-3229], V6."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    V_ID = V.id
    cp = commit_point(db)
    oid, num = O.id, NUM(O)
    result = _void(db, s, oid)
    # Then 1
    assert result.id == oid
    # Then 2
    assert ev(db, cp, oid) == [
        ("invoice_voided", f"Invoice unlinked — work order {num} voided"),
        ("voided", f"Work order {num} voided. Reason: Cancelled"),
    ]
    # Then 3
    assert evrow(db, cp, oid, "invoice_voided").metadata_json == {"invoice_id": V_ID}
    # Then 4
    assert evrow(db, cp, oid, "invoice_voided").performed_by == s.U2.id


@xf(639)
def test_wos_v_04__payment_history_400(db, s):
    """WOS-V-04 — a draft with payment history: the invoice manager's 400, the whole void undone.
    Rules: void_work_order V4, Errors row V4 [BUG-639] (invoice manager pass-through)."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    pay(db, s, V, "100.00")
    commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == PAYHIST
    # Then 4
    assert snap(db, O) == before_o
    # Then 5
    assert snap(db, V) == before_v


def test_wos_v_05__payment_history_never_deleted(db, s):
    """WOS-V-05 — a draft with payment history is never deleted and the order not voided (today and after the fix).
    Rules: void_work_order V4; TC3."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    P = pay(db, s, V, "100.00")
    cp = commit_point(db)
    before_o = snap(db, O)
    oid, vid, pid = O.id, V.id, P.id
    X, x_id = mk_x(db)
    with pytest.raises(Exception):
        _void(db, s, oid)
    # Then 1
    assert X not in db
    # Then 2
    v = reread(db, AccountInvoice, vid)
    assert v is not None
    assert v.invoice_status == "draft"
    # Then 3
    p = reread(db, InvoicePayment, pid)
    assert p is not None
    assert p.is_voided is True
    # Then 4
    assert snap_id(db, WorkOrder, oid) == before_o
    # Then 5
    assert ev(db, cp, oid) == []
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_v_06__voided_invoice_kept_linked(db, s):
    """WOS-V-06 — a linked invoice already voided is not touched; the order keeps the link and is voided.
    Rules: void_work_order V5."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, voided_inv=True, linked=True)
    cp = commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _void(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.status == "VOIDED"
    assert row.invoice_id == vid
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 4
    assert [t for t, _ in ev(db, cp, oid)] == ["voided"]


@pytest.mark.parametrize("ws", [pytest.param("2", id="WOS-V-07"), pytest.param("0", id="WOS-V-08")])
def test_wos_v_07_08__other_workspace_invoice_kept(db, s, ws):
    """WOS-V-07 / WOS-V-08 — a linked W2 / W0 invoice is not touched; the order keeps the link and is voided.
    Rules: void_work_order V5; HR-16."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, ws=ws, linked=True)
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = _void(db, s, oid)
    # Then 1
    assert result.id == oid
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.status == "VOIDED"
    assert row.invoice_id == vid
    # Then 3
    assert snap_id(db, AccountInvoice, vid) == before_v


@xf(3224)
def test_wos_v_09__confirmed_invoice_refuses_void(db, s):
    """WOS-V-09 — a confirmed invoice refuses the void; order, approvals, invoice and payments kept.
    Rules: void_work_order V5a, Errors row V5a [BUG-3224]."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("40000.00"))
    P3 = approver(db, s, O, s.U3, approved=True)
    V = inv(db, s, O, confirmed=True, invoice_amount=Decimal("40000.00"), linked=True)
    P = pay(db, s, V, "10000.00")
    cp = commit_point(db)
    before = [snap(db, r) for r in (O, P3, V, P)]
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == FINAL
    # Then 4
    assert X not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, O) == before[0]
    # Then 7
    assert snap(db, P3) == before[1]
    # Then 8
    assert snap(db, V) == before[2]
    # Then 9
    assert snap(db, P) == before[3]
    # Then 10
    assert counts(db) == cp.counts
    db.rollback()
    # Then 11
    assert x_gone(db, x_id)


def test_wos_v_10__confirmed_invoice_never_changed(db, s):
    """WOS-V-10 — a confirmed invoice is never deleted or changed by the void (today and after the fix).
    Rules: void_work_order V5, V5a."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, confirmed=True, invoice_amount=Decimal("40000.00"), linked=True)
    P = pay(db, s, V, "10000.00")
    commit_point(db)
    oid, vid, pid = O.id, V.id, P.id
    before_v, before_p = snap(db, V), snap(db, P)
    try:
        _void(db, s, oid)
    except HTTPException:
        pass
    # Then 1
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 2
    assert snap_id(db, InvoicePayment, pid) == before_p
    # Then 3
    assert count_where(db, InvoicePayment, InvoicePayment.invoice_id == vid) == 1


def test_wos_v_11__completed_400(db, s):
    """WOS-V-11 — a completed order with its confirmed invoice: the "completed" 400, nothing written.
    Rules: void_work_order V2, Errors row V2."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    cp = commit_point(db)
    before_o, before_v = snap(db, O), snap(db, V)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _void(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a completed work order"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, O) == before_o
    # Then 7
    assert snap(db, V) == before_v
    # Then 8
    assert counts(db) == cp.counts
    db.rollback()
    # Then 9
    assert x_gone(db, x_id)


@xf(3224)
def test_wos_v_12__completed_refused_before_invoice(db, s):
    """WOS-V-12 — a completed order with a leftover draft is refused before the invoice is touched.
    Rules: void_work_order V2 [BUG-3224]."""
    O = mk_order(db, s, "1", completed=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.void_work_order(db, wo_id=oid, workspace_id=w1, user_id=u2, void_note="Cancelled")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a completed work order"
    # Then 4
    assert rec.names("account_invoices") == []


def test_wos_v_13__voided_400_draft_kept(db, s):
    """WOS-V-13 — a voided order with a leftover draft: the "already voided" 400, the draft kept (today and after the fix).
    Rules: void_work_order V2, Errors row V2."""
    O = mk_order(db, s, "1", voided=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    cp = commit_point(db)
    before_v, before_o = snap(db, V), snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is already voided"
    # Then 4
    assert snap(db, V) == before_v
    # Then 5
    assert snap(db, O) == before_o
    # Then 6
    assert counts(db) == cp.counts


@xf(3224)
def test_wos_v_14__voided_refused_before_invoice(db, s):
    """WOS-V-14 — a voided order with a leftover draft is refused before the invoice is touched.
    Rules: void_work_order V2 [BUG-3224]."""
    O = mk_order(db, s, "1", voided=True)
    inv(db, s, O, linked=True)
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.void_work_order(db, wo_id=oid, workspace_id=w1, user_id=u2, void_note="Cancelled")
    # Then 2
    assert exc.value.detail == "Work order is already voided"
    # Then 3
    assert rec.names("account_invoices") == []


def test_wos_v_15__missing_404(db, s):
    """WOS-V-15 — a missing order: 404, the extra row is gone.
    Rules: void_work_order V1, Errors row V1; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def test_wos_v_16__w2_order_404(db, s):
    """WOS-V-16 — another workspace's order (W2): 404, not voided.
    Rules: void_work_order V1; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    before = snap(db, Z)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, zid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)
    # Then 4
    assert snap(db, Z) == before


def test_wos_v_17__failing_commit_keeps_order_and_draft(db, s):
    """WOS-V-17 — a failing commit keeps the order and its draft invoice.
    Rules: void_work_order V6; TC4."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _void(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, WorkOrder, oid)
    assert row.status == "DRAFT"
    assert row.invoice_id == vid
    # Then 4
    v = reread(db, AccountInvoice, vid)
    assert v is not None
    assert v.invoice_status == "draft"


@xf(3222)
def test_wos_v_18__row_lock_before_checks(db, s):
    """WOS-V-18 — the order is read with a row lock before any check.
    Rules: void_work_order V1 [BUG-3222]; HR-10."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = svc.void_work_order(db, wo_id=oid, workspace_id=w1, user_id=u2, void_note="Cancelled")
    # Then 1
    assert result.id == oid
    # Then 2
    assert rec.lock()
    # Then 3
    assert rec.lock_first()


def test_wos_v_19__unlink_event_before_voided_by_actor(db, s):
    """WOS-V-19 — the unlink event is written before the voided event, by the actor (today and after the fix).
    Rules: void_work_order V4, V6."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    V_ID = V.id
    cp = commit_point(db)
    oid, num = O.id, NUM(O)
    result = _void(db, s, oid)
    # Then 1
    assert result.id == oid
    # Then 2
    assert ev(db, cp, oid) == [
        ("invoice_voided", f"Invoice unlinked — work order {num} voided"),
        ("voided", f"Work order {num} voided. Reason: Cancelled"),
    ]
    # Then 3
    assert evrow(db, cp, oid, "invoice_voided").performed_by == s.U2.id
    # Then 4
    assert set(evrow(db, cp, oid, "invoice_voided").metadata_json) == {"invoice_id"}
    db.rollback()
    # Then 5
    assert gone(db, AccountInvoice, V_ID)
    assert reread(db, WorkOrder, oid).invoice_id is None


# --------------------------------------------------------------------------- #
# create_invoice_for_work_order
# --------------------------------------------------------------------------- #


def _cinv(db, s, oid):
    return svc.create_invoice_for_work_order(db, wo_id=oid, workspace_id=s.W1.id, user_id=s.U2.id)


def test_wos_i_01__draft_invoice_committed_linked(db, s):
    """WOS-I-01 — a draft order with account and cost gets its draft invoice, committed and linked.
    Rules: create_invoice_for_work_order I6, I8, I10; TC1, TC2."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("750.50"))
    commit_point(db)
    oid = O.id
    result = _cinv(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == oid
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 3
    assert reread(db, WorkOrder, oid).invoice_id == vid
    # Then 4
    v = reread(db, AccountInvoice, vid)
    assert v.invoice_status == "draft"
    assert v.invoice_amount == Decimal("750.50")
    # Then 5
    assert len(inv_of(db, oid)) == 1


def test_wos_i_02__invoice_header(db, s):
    """WOS-I-02 — the invoice header carries the order's account, link, due date, description and notes.
    Rules: create_invoice_for_work_order I6."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("750.50"), end_date=D(20))
    commit_point(db)
    oid, num = O.id, NUM(O)
    result = _cinv(db, s, oid)
    db.expire_all()
    INV = db.get(AccountInvoice, result.invoice_id)
    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert INV.workspace_id == s.W1.id
    assert INV.account_id == s.A1.id
    assert INV.invoice_type == "payable"
    assert INV.invoice_status == "draft"
    # Then 3
    assert INV.order_type == "work_order"
    assert INV.order_id == oid
    # Then 4
    assert INV.due_date == D(20)
    assert INV.description == f"Auto-created from work order {num}"
    assert INV.notes == "Old desc"
    # Then 5
    assert INV.allow_payments is True
    assert INV.invoice_number is None
    assert INV.vendor_invoice_number is None
    assert INV.payment_locked_reason is None


def test_wos_i_03__one_invoice_line(db, s):
    """WOS-I-03 — exactly one invoice line: the title, 1 × the cost, `wo_labor`, no rounding.
    Rules: create_invoice_for_work_order I8."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("750.50"))
    commit_point(db)
    result = _cinv(db, s, O.id)
    db.expire_all()
    LS = LINES(db, result.invoice_id)
    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert len(LS) == 1
    # Then 3
    assert LS[0].line_number == 1
    assert LS[0].description == "Service — Lathe 3"
    assert LS[0].item_id is None
    assert LS[0].source_order_item_id is None
    assert LS[0].source_order_item_type == "wo_labor"
    # Then 4
    assert LS[0].quantity == Decimal("1")
    assert LS[0].unit is None
    assert LS[0].unit_price == Decimal("750.50")
    assert LS[0].line_subtotal == Decimal("750.50")


def test_wos_i_04__events(db, s):
    """WOS-I-04 — one `invoice_created` order event; the invoice has its `created` and `items_synced` events.
    Rules: create_invoice_for_work_order I9, I8."""
    O = mk_order(db, s, "1", outside=True)
    cp = commit_point(db)
    oid = O.id
    result = _cinv(db, s, oid)
    # Then 1
    assert result.invoice_id is not None
    vid = result.invoice_id
    # Then 2
    assert ev(db, cp, oid) == [("invoice_created", f"Invoice #{vid} created from work order")]
    # Then 3
    assert evrow(db, cp, oid, "invoice_created").metadata_json == {"invoice_id": vid}
    assert evrow(db, cp, oid, "invoice_created").performed_by == s.U2.id
    db.rollback()
    # Then 4
    assert itypes(db, vid) == ["created", "items_synced"]


def test_wos_i_05__draft_notice_to_creator(db, s):
    """WOS-I-05 — the draft notice goes to the creator.
    Rules: create_invoice_for_work_order I10."""
    O = mk_order(db, s, "1", outside=True)
    commit_point(db)
    oid = O.id
    result = _cinv(db, s, oid)
    # Then 1
    assert result.invoice_id is not None
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id]
    # Then 3
    assert notes(db)[0].notification_type == "invoice_action"
    assert notes(db)[0].entity_type == "work_order"
    assert notes(db)[0].entity_id == oid
    # Then 4
    assert notes(db)[0].preview == DRAFTP


def test_wos_i_06__pending_approver_told(db, s):
    """WOS-I-06 — approvals are not required; a pending approver is told too.
    Rules: create_invoice_for_work_order I5, I10."""
    O = mk_order(db, s, "1", outside=True, approved_by=None, approved_at=None)
    approver(db, s, O, s.U3)
    commit_point(db)
    result = _cinv(db, s, O.id)
    # Then 1
    assert result.invoice_id is not None
    db.rollback()
    # Then 2
    assert recips(db) == [s.U1.id, s.U3.id]


def test_wos_i_07__no_end_date_no_due_date(db, s):
    """WOS-I-07 — no end date: the invoice has no due date.
    Rules: create_invoice_for_work_order I6."""
    O = mk_order(db, s, "1", outside=True)
    commit_point(db)
    result = _cinv(db, s, O.id)
    # Then 1
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).due_date is None


def test_wos_i_08__started_order_may_get_invoice(db, s):
    """WOS-I-08 — a started order may get an invoice.
    Rules: create_invoice_for_work_order I3."""
    O = mk_order(db, s, "1", started=True, outside=True)
    commit_point(db)
    oid = O.id
    result = _cinv(db, s, oid)
    # Then 1
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 2
    row = reread(db, WorkOrder, oid)
    assert row.status == "IN_PROGRESS"
    assert row.invoice_id == vid


def test_wos_i_09__already_linked_409(db, s):
    """WOS-I-09 — a draft already linked: 409, the extra row is gone.
    Rules: create_invoice_for_work_order I2, Errors row I2; TC3."""
    O = mk_order(db, s, "1", outside=True)
    inv(db, s, O, linked=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == EXISTS
    # Then 4
    assert X not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, O) == before
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_wos_i_10__voided_invoice_still_counts_409(db, s):
    """WOS-I-10 — a voided invoice linked still counts: 409.
    Rules: create_invoice_for_work_order I2."""
    O = mk_order(db, s, "1", outside=True)
    inv(db, s, O, voided_inv=True, linked=True)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == EXISTS
    # Then 4
    assert counts(db) == cp.counts


def test_wos_i_11__confirmed_invoice_409(db, s):
    """WOS-I-11 — a confirmed invoice linked: 409.
    Rules: create_invoice_for_work_order I2."""
    O = mk_order(db, s, "1", outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    commit_point(db)
    before_v = snap(db, V)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == EXISTS
    # Then 4
    assert snap(db, V) == before_v


@xf(3225)
def test_wos_i_12__voided_order_400(db, s):
    """WOS-I-12 — a voided order gets no invoice: 400.
    Rules: create_invoice_for_work_order I3, Errors row I3 [BUG-3225]."""
    O = mk_order(db, s, "1", voided=True, outside=True, cost=Decimal("500.00"))
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided"
    # Then 4
    assert X not in db
    # Then 5
    assert snap(db, O) == before
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


@xf(3225)
def test_wos_i_13__completed_order_400(db, s):
    """WOS-I-13 — a completed order without an invoice gets no invoice: 400.
    Rules: create_invoice_for_work_order I3 [BUG-3225]."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert snap(db, O) == before
    # Then 5
    assert counts(db) == cp.counts


def test_wos_i_14__voided_with_invoice_never_second(db, s):
    """WOS-I-14 — a voided order with an invoice linked never gets a second one (today and after the fix).
    Rules: create_invoice_for_work_order I2, I3."""
    O = mk_order(db, s, "1", voided=True, outside=True)
    inv(db, s, O, voided_inv=True, linked=True)
    commit_point(db)
    before = snap(db, O)
    oid = O.id
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 1
    assert exc.value.status_code in (400, 409)
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 1
    # Then 3
    assert snap(db, O) == before


@xf(3225)
def test_wos_i_15__voided_with_invoice_400_not_409(db, s):
    """WOS-I-15 — a voided order with an invoice linked gets the "voided" 400, not the 409.
    Rules: create_invoice_for_work_order I3 (checked before I2) [BUG-3225]."""
    O = mk_order(db, s, "1", voided=True, outside=True)
    inv(db, s, O, voided_inv=True, linked=True)
    commit_point(db)
    oid = O.id
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 1
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Work order is voided"


@xf(3225)
def test_wos_i_16__completed_with_invoice_400_not_409(db, s):
    """WOS-I-16 — a completed order with an invoice linked gets the "completed" 400, not the 409.
    Rules: create_invoice_for_work_order I3 (checked before I2) [BUG-3225]."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    inv(db, s, O, confirmed=True, linked=True)
    commit_point(db)
    oid = O.id
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 1
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Work order is completed"


def test_wos_i_17__completed_with_invoice_never_second(db, s):
    """WOS-I-17 — a completed order with its confirmed invoice never gets a second one (today and after the fix).
    Rules: create_invoice_for_work_order I2, I3."""
    O = mk_order(db, s, "1", completed=True, outside=True)
    V = inv(db, s, O, confirmed=True, linked=True)
    commit_point(db)
    before_v = snap(db, V)
    oid = O.id
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 1
    assert exc.value.status_code in (400, 409)
    # Then 2
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 1
    # Then 3
    assert snap(db, V) == before_v


def test_wos_i_18__no_account_422(db, s):
    """WOS-I-18 — no account: 422, nothing written, the extra row is gone.
    Rules: create_invoice_for_work_order I4, Errors row I4; TC3."""
    O = mk_order(db, s, "1")
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == NOACC
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, O) == before
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


def test_wos_i_19__account_id_zero_422(db, s):
    """WOS-I-19 — account id 0 counts as no account: 422.
    Rules: create_invoice_for_work_order I4."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    O.account_id = 0
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == NOACC
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 0


@xf(3228)
def test_wos_i_20__no_cost_422(db, s):
    """WOS-I-20 — an account and no cost: 422, no invoice.
    Rules: create_invoice_for_work_order I4a, Errors row I4a [BUG-3228]."""
    O = mk_order(db, s, "1", outside=True, cost=None)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == NOCOST
    # Then 4
    assert X not in db
    # Then 5
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 6
    assert snap(db, O) == before
    # Then 7
    assert counts(db) == cp.counts
    db.rollback()
    # Then 8
    assert x_gone(db, x_id)


@pytest.mark.parametrize(
    "cost",
    [pytest.param(Decimal("0.00"), id="WOS-I-21"), pytest.param(Decimal("-5.00"), id="WOS-I-22")],
)
@xf(3228)
def test_wos_i_21_22__zero_or_negative_cost_422(db, s, cost):
    """WOS-I-21 / WOS-I-22 — an account and a cost of 0.00 / a negative cost: 422, no invoice.
    Rules: create_invoice_for_work_order I4a [BUG-3228]."""
    O = mk_order(db, s, "1", outside=True, cost=cost)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == NOCOST
    # Then 4
    assert snap(db, O) == before
    # Then 5
    assert counts(db) == cp.counts


def test_wos_i_23__cost_one_cent_enough(db, s):
    """WOS-I-23 — a cost of 0.01 is enough (today and after the fix).
    Rules: create_invoice_for_work_order I4a, I8."""
    O = mk_order(db, s, "1", outside=True, cost=Decimal("0.01"))
    commit_point(db)
    result = _cinv(db, s, O.id)
    # Then 1
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 2
    assert [(i.unit_price, i.line_subtotal) for i in LINES(db, vid)] == [(Decimal("0.01"), Decimal("0.01"))]
    # Then 3
    assert reread(db, AccountInvoice, vid).invoice_amount == Decimal("0.01")


def test_wos_i_24__no_account_no_cost_account_first(db, s):
    """WOS-I-24 — neither account nor cost: the account is asked for first (today and after the fix).
    Rules: create_invoice_for_work_order I4, I4a (order)."""
    O = mk_order(db, s, "1", cost=None)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == NOACC
    # Then 4
    assert counts(db) == cp.counts


def _acct(db, s, name, **cols):
    fields = {"workspace_id": s.W1.id, "name": name, "is_active": True, "is_deleted": False, "allow_invoices": True}
    fields.update(cols)
    return _add(db, Account(**fields))


def test_wos_i_25__deleted_account_400(db, s):
    """WOS-I-25 — a deleted account: the invoice manager's 400 passes unchanged.
    Rules: create_invoice_for_work_order I7."""
    AD = _acct(db, s, "Gone Traders", is_deleted=True)
    O = mk_order(db, s, "1", account_id=AD.id)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create invoice for deleted account"
    # Then 4
    assert snap(db, O) == before
    # Then 5
    assert counts(db) == cp.counts


def test_wos_i_26__inactive_account_400(db, s):
    """WOS-I-26 — an inactive account: the invoice manager's 400 passes unchanged.
    Rules: create_invoice_for_work_order I7."""
    AI = _acct(db, s, "Idle Traders", is_active=False)
    O = mk_order(db, s, "1", account_id=AI.id)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create invoice for inactive account"
    # Then 4
    assert counts(db) == cp.counts


def test_wos_i_27__no_invoices_account_403(db, s):
    """WOS-I-27 — an account that does not allow invoices: 403 passes unchanged.
    Rules: create_invoice_for_work_order I7."""
    AN = _acct(db, s, "Cash Only", allow_invoices=False)
    O = mk_order(db, s, "1", account_id=AN.id)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "Invoices are not allowed for this account"
    # Then 4
    assert counts(db) == cp.counts


def test_wos_i_28__w2_account_422_with_404_cause(db, s):
    """WOS-I-28 — a W2 account becomes the 422 "not found in this workspace", the 404 as its cause.
    Rules: create_invoice_for_work_order I7, Errors row I7; HR-16."""
    O = mk_order(db, s, "1", account_id=s.A9.id)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == ACC404
    # Then 4
    assert isinstance(exc.value.__cause__, HTTPException)
    assert exc.value.__cause__.status_code == 404
    # Then 5
    assert counts(db) == cp.counts


def test_wos_i_29__w0_account_422(db, s):
    """WOS-I-29 — a W0 account becomes the same 422.
    Rules: create_invoice_for_work_order I7; HR-16."""
    O = mk_order(db, s, "1", account_id=s.A0.id)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == ACC404
    # Then 4
    assert counts(db) == cp.counts


@xf(3226)
def test_wos_i_30__invoice_date_is_utc_date(db, s):
    """WOS-I-30 — the invoice date is the UTC date.
    Rules: create_invoice_for_work_order I6 [BUG-3226]."""
    O = mk_order(db, s, "1", outside=True)
    commit_point(db)
    oid = O.id
    with patch("app.services.work_order_service.utcnow", return_value=NOW, create=True):
        result = _cinv(db, s, oid)
    # Then 1
    assert result.invoice_id is not None
    vid = result.invoice_id
    db.rollback()
    # Then 2
    assert reread(db, AccountInvoice, vid).invoice_date == date(2026, 3, 10)


@xf(627)
def test_wos_i_31__no_invoice_amount_sent(db, s):
    """WOS-I-31 — no invoice amount is sent to the invoice manager.
    Rules: create_invoice_for_work_order I6 [BUG-627]."""
    O = mk_order(db, s, "1", outside=True)
    commit_point(db)
    oid = O.id
    with patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci:
        result = _cinv(db, s, oid)
    args = list(ci.call_args.args) + list(ci.call_args.kwargs.values())
    SENT = next(a for a in args if type(a).__name__ == "AccountInvoiceCreate")
    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert "invoice_amount" not in SENT.model_fields_set


def test_wos_i_32__missing_404(db, s):
    """WOS-I-32 — a missing order: 404, the extra row is gone.
    Rules: create_invoice_for_work_order I1, Errors row I1; TC3."""
    cp = commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(MISSING)
    # Then 4
    assert X not in db
    # Then 5
    assert counts(db) == cp.counts
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_i_33__w2_order_404(db, s):
    """WOS-I-33 — another workspace's order (W2): 404, no invoice.
    Rules: create_invoice_for_work_order I1; HR-16."""
    Z = mk_order(db, s, "9", ws="2", outside=True)
    cp = commit_point(db)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, zid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)
    # Then 4
    assert counts(db) == cp.counts


@xf(1279)
def test_wos_i_34__soft_deleted_404(db, s):
    """WOS-I-34 — a soft-deleted order: 404, no invoice.
    Rules: create_invoice_for_work_order I1 [BUG-1279] (manager pass-through)."""
    O = mk_order(db, s, "1", outside=True, gone=True)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cinv(db, s, oid)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(oid)
    # Then 4
    assert counts(db) == cp.counts


def test_wos_i_35__failing_commit_no_invoice(db, s):
    """WOS-I-35 — a failing commit leaves no invoice and no link.
    Rules: create_invoice_for_work_order I10; TC4."""
    O = mk_order(db, s, "1", outside=True)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _cinv(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrder, oid).invoice_id is None
    # Then 4
    assert counts(db) == cp.counts


def test_wos_i_36__failing_draft_notice_undoes(db, s):
    """WOS-I-36 — a failing draft notice undoes the invoice and the link.
    Rules: create_invoice_for_work_order I10; TC3."""
    O = mk_order(db, s, "1", outside=True)
    cp = commit_point(db)
    before = snap(db, O)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_notify(db, "notify_invoice_action"):
            _cinv(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert X not in db
    # Then 3
    assert snap(db, O) == before
    # Then 4
    assert counts(db) == cp.counts
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


@xf(3222)
def test_wos_i_37__row_lock_before_checks(db, s):
    """WOS-I-37 — the order is read with a row lock before any check.
    Rules: create_invoice_for_work_order I1 [BUG-3222]; HR-10."""
    O = mk_order(db, s, "1", outside=True)
    oid = O.id
    commit_point(db)
    w1, u2 = s.W1.id, s.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = svc.create_invoice_for_work_order(db, wo_id=oid, workspace_id=w1, user_id=u2)
    # Then 1
    assert result.invoice_id is not None
    # Then 2
    assert rec.lock()
    # Then 3
    assert rec.lock_first()


# --------------------------------------------------------------------------- #
# list_approvers / approval_summary_for
# --------------------------------------------------------------------------- #


def test_wos_la_01__manager_tuples(db, s):
    """WOS-LA-01 — returns the manager's approver tuples; neither commits nor rolls back.
    Rules: list_approvers A1; TC6."""
    O = mk_order(db, s, "1")
    R1 = approver(db, s, O, s.U1)
    R2 = approver(db, s, O, s.U2)
    commit_point(db)
    oid, r1, r2 = O.id, R1.id, R2.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.list_approvers(db, wo_id=oid, workspace_id=s.W1.id)
    # Then 1
    assert {r.id: (p.id, pos) for r, p, pos in result} == {r1: (s.U1.id, "Supervisor"), r2: (s.U2.id, None)}
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_la_02__w2_order_404_no_rollback(db, s):
    """WOS-LA-02 — another workspace's order: 404, no rollback.
    Rules: list_approvers A1; TC6; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)
    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.list_approvers(db, wo_id=zid, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    assert exc.value.detail == NF(zid)
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


def test_wos_as_01__one_of_two(db, s):
    """WOS-AS-01 — one of two approved: (1, 2, False); neither commits nor rolls back.
    Rules: approval_summary_for A2; TC6."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U2, approved=True)
    approver(db, s, O, s.U3)
    commit_point(db)
    oid = O.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.approval_summary_for(db, wo_id=oid, workspace_id=s.W1.id)
    # Then 1
    assert result == (1, 2, False)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_as_02__no_approvers_met(db, s):
    """WOS-AS-02 — no approvers: 0 of 0, met.
    Rules: approval_summary_for A2."""
    O = mk_order(db, s, "1")
    commit_point(db)
    result = svc.approval_summary_for(db, wo_id=O.id, workspace_id=s.W1.id)
    # Then 1
    assert result == (0, 0, True)


def test_wos_as_03__w0_order_404(db, s):
    """WOS-AS-03 — a W0 order: 404.
    Rules: approval_summary_for A2; HR-16."""
    Z = mk_order(db, s, "0", ws="0")
    commit_point(db)
    zid = Z.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.approval_summary_for(db, wo_id=zid, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == NF(zid)


def test_wos_as_04__w2_order_404_no_rollback(db, s):
    """WOS-AS-04 — a W2 order: 404, no rollback.
    Rules: approval_summary_for A2; TC6; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)
    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.approval_summary_for(db, wo_id=zid, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    assert exc.value.detail == NF(zid)
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


# --------------------------------------------------------------------------- #
# add_approver / remove_approver
# --------------------------------------------------------------------------- #


def _add_appr(db, s, oid, user, by, **k):
    return svc.add_approver(db, wo_id=oid, user_id=user.id, workspace_id=s.W1.id, assigned_by=by.id, **k)


def test_wos_aa_01__added_committed_told(db, s):
    """WOS-AA-01 — the approver is added and committed; the new approver is told.
    Rules: add_approver A3, A4; TC1, TC2."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    result = _add_appr(db, s, oid, s.U3, s.U2, approver_slot="QA")
    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, WorkOrderApprover)
    assert result.user_id == s.U3.id
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, WorkOrderApprover, rid)
    assert row.work_order_id == oid
    assert row.assigned_by == s.U2.id
    assert row.approver_slot == "QA"
    # Then 4
    assert [(n.recipient_user_id, n.notification_type) for n in notes(db) if n.recipient_user_id == s.U3.id] == [
        (s.U3.id, "approval_assigned")
    ]


def test_wos_aa_02__ready_order_pending_reminded(db, s):
    """WOS-AA-02 — ready order: the new approver is assigned, the other pending approver is reminded.
    Rules: add_approver A4."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U2)
    commit_point(db)
    result = _add_appr(db, s, O.id, s.U3, s.U1)
    # Then 1
    assert result.user_id == s.U3.id
    db.rollback()
    # Then 2
    assert sorted((n.recipient_user_id, n.notification_type) for n in notes(db)) == sorted(
        [(s.U3.id, "approval_assigned"), (s.U2.id, "approval_pending")]
    )


def test_wos_aa_03__not_ready_creator_gap_notice(db, s):
    """WOS-AA-03 — order not ready: the new approver is assigned, the creator gets the gap notice.
    Rules: add_approver A4."""
    O = mk_order(db, s, "1", title="   ")
    commit_point(db)
    result = _add_appr(db, s, O.id, s.U3, s.U2)
    # Then 1
    assert result.user_id == s.U3.id
    db.rollback()
    # Then 2
    assert sorted((n.recipient_user_id, n.notification_type) for n in notes(db)) == sorted(
        [(s.U3.id, "approval_assigned"), (s.U1.id, "section_confirm")]
    )
    # Then 3
    n = next(n for n in notes(db) if n.recipient_user_id == s.U1.id)
    assert "Work order setup is incomplete" in n.preview


def test_wos_aa_04__duplicate_409(db, s):
    """WOS-AA-04 — a duplicate approver: 409 passes unchanged, the extra row is gone.
    Rules: add_approver A3; TC3."""
    O = mk_order(db, s, "1")
    approver(db, s, O, s.U3)
    cp = commit_point(db)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _add_appr(db, s, oid, s.U3, s.U2)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_aa_05__suspended_member_400(db, s):
    """WOS-AA-05 — a suspended member: 400 passes unchanged, nobody told.
    Rules: add_approver A3."""
    O = mk_order(db, s, "1")
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_appr(db, s, oid, s.U4, s.U2)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NOTMEMBER
    # Then 4
    assert counts(db) == cp.counts


def test_wos_aa_06__completed_order_400(db, s):
    """WOS-AA-06 — a completed order: 400 passes unchanged.
    Rules: add_approver A3."""
    O = mk_order(db, s, "1", completed=True)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_appr(db, s, oid, s.U3, s.U2)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert counts(db) == cp.counts


@xf(2931)
def test_wos_aa_07__started_order_no_new_approver(db, s):
    """WOS-AA-07 — a started order takes no new approver.
    Rules: add_approver A3 [BUG-2931] (manager pass-through)."""
    O = mk_order(db, s, "1", started=True)
    cp = commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_appr(db, s, oid, s.U3, s.U2)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STARTED
    # Then 4
    assert counts(db) == cp.counts


def test_wos_aa_08__failing_commit_no_approver(db, s):
    """WOS-AA-08 — a failing commit leaves no approver and no notification.
    Rules: add_approver A3; TC4."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _add_appr(db, s, oid, s.U3, s.U2)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, WorkOrderApprover, WorkOrderApprover.work_order_id == oid) == 0
    # Then 4
    assert notes(db) == []


def test_wos_aa_09__failing_notification_undoes_add(db, s):
    """WOS-AA-09 — a failing approver notification undoes the add.
    Rules: add_approver A4; TC3."""
    O = mk_order(db, s, "1")
    cp = commit_point(db)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_notify(db, "handle_add_approver"):
            _add_appr(db, s, oid, s.U3, s.U2)
    assert str(exc.value) == "boom"
    # Then 2
    assert X not in db
    # Then 3
    assert count_where(db, WorkOrderApprover, WorkOrderApprover.work_order_id == oid) == 0
    # Then 4
    assert counts(db) == cp.counts
    db.rollback()
    # Then 5
    assert x_gone(db, x_id)


def _rm_appr(db, s, oid, user):
    return svc.remove_approver(db, wo_id=oid, user_id=user.id, workspace_id=s.W1.id, performed_by=s.U2.id)


def test_wos_ra_01__removed_committed_none(db, s):
    """WOS-RA-01 — the approver is removed and committed; returns None; nobody told even when approvals become met.
    Rules: remove_approver A5."""
    O = mk_order(db, s, "1", approved_by=None, approved_at=None)
    R3 = approver(db, s, O, s.U3)
    approver(db, s, O, s.U2, approved=True)
    commit_point(db)
    r3 = R3.id
    result = _rm_appr(db, s, O.id, s.U3)
    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert count_where(db, WorkOrderApprover, WorkOrderApprover.id == r3) == 0
    # Then 3
    assert notes(db) == []


def test_wos_ra_02__not_an_approver_404(db, s):
    """WOS-RA-02 — not an approver: 404 passes unchanged, the extra row is gone.
    Rules: remove_approver A5; TC3."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _rm_appr(db, s, oid, s.U3)
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


@xf(2931)
def test_wos_ra_03__started_keeps_approvers(db, s):
    """WOS-RA-03 — a started order keeps its approvers.
    Rules: remove_approver A5 [BUG-2931] (manager pass-through)."""
    O = mk_order(db, s, "1", started=True)
    R3 = approver(db, s, O, s.U3)
    commit_point(db)
    before = snap(db, R3)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _rm_appr(db, s, oid, s.U3)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STARTED
    # Then 4
    assert snap(db, R3) == before


def test_wos_ra_04__failing_commit_keeps_approver(db, s):
    """WOS-RA-04 — a failing commit keeps the approver.
    Rules: remove_approver A5; TC4."""
    O = mk_order(db, s, "1")
    R3 = approver(db, s, O, s.U3)
    commit_point(db)
    before = snap(db, R3)
    oid, r3 = O.id, R3.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _rm_appr(db, s, oid, s.U3)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap_id(db, WorkOrderApprover, r3) == before


# --------------------------------------------------------------------------- #
# approve_as_me / unapprove_as_me
# --------------------------------------------------------------------------- #


def _approve(db, s, oid):
    return svc.approve_as_me(db, wo_id=oid, user_id=s.U2.id, workspace_id=s.W1.id)


def _unapprove(db, s, oid):
    return svc.unapprove_as_me(db, wo_id=oid, user_id=s.U2.id, workspace_id=s.W1.id)


def test_wos_ap_01__approval_recorded(db, s):
    """WOS-AP-01 — the approval is recorded and committed; no invoice, nobody told even when the order becomes ready.
    Rules: approve_as_me A6, A7; TC1, TC2."""
    O = mk_order(db, s, "1", outside=True, approved_by=None, approved_at=None)
    R2 = approver(db, s, O, s.U2)
    commit_point(db)
    oid, r2 = O.id, R2.id
    result = _approve(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == r2
    db.rollback()
    # Then 3
    row = reread(db, WorkOrderApprover, r2)
    assert row.approved is True
    assert row.approved_at == NOW
    # Then 4
    assert count_where(db, AccountInvoice, AccountInvoice.order_id == oid) == 0
    # Then 5
    assert notes(db) == []


def test_wos_ap_02__not_an_approver_403(db, s):
    """WOS-AP-02 — not an approver: 403 passes unchanged, the extra row is gone.
    Rules: approve_as_me A6; TC3."""
    O = mk_order(db, s, "1")
    commit_point(db)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _approve(db, s, oid)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


@xf(2931)
def test_wos_ap_03__started_no_approval(db, s):
    """WOS-AP-03 — a started order takes no approval.
    Rules: approve_as_me A6 [BUG-2931] (manager pass-through)."""
    O = mk_order(db, s, "1", started=True)
    R2 = approver(db, s, O, s.U2)
    commit_point(db)
    before = snap(db, R2)
    oid = O.id
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _approve(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STARTED
    # Then 4
    assert snap(db, R2) == before


@xf(2917)
def test_wos_ap_04__approving_again_changes_nothing(db, s):
    """WOS-AP-04 — approving again changes nothing.
    Rules: approve_as_me A6 [BUG-2917] (manager pass-through)."""
    O = mk_order(db, s, "1", approved_by=s.U2.id)
    R2 = approver(db, s, O, s.U2, approved=True)
    cp = commit_point(db)
    oid, r2 = O.id, R2.id
    result = _approve(db, s, oid)
    # Then 1
    assert result.id == r2
    assert result.approved is True
    db.rollback()
    # Then 2
    assert reread(db, WorkOrderApprover, r2).approved_at == T0
    # Then 3
    assert ev(db, cp, oid) == []


def test_wos_ap_05__failing_commit_unrecorded(db, s):
    """WOS-AP-05 — a failing commit leaves the approval unrecorded.
    Rules: approve_as_me A6; TC4."""
    O = mk_order(db, s, "1")
    R2 = approver(db, s, O, s.U2)
    commit_point(db)
    oid, r2 = O.id, R2.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _approve(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, WorkOrderApprover, r2)
    assert row.approved is False
    assert row.approved_at is None


def test_wos_ua_01__withdrawn_committed(db, s):
    """WOS-UA-01 — the approval is withdrawn and committed; nobody told.
    Rules: unapprove_as_me A6, A7; TC1, TC2."""
    O = mk_order(db, s, "1", approved_by=s.U2.id)
    R2 = approver(db, s, O, s.U2, approved=True)
    commit_point(db)
    oid, r2 = O.id, R2.id
    result = _unapprove(db, s, oid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == r2
    db.rollback()
    # Then 3
    assert reread(db, WorkOrderApprover, r2).approved is False
    # Then 4
    assert notes(db) == []


def test_wos_ua_02__completed_400(db, s):
    """WOS-UA-02 — a completed order: 400 passes unchanged, the extra row is gone.
    Rules: unapprove_as_me A6; TC3."""
    O = mk_order(db, s, "1", completed=True)
    R2 = approver(db, s, O, s.U2, approved=True)
    commit_point(db)
    before = snap(db, R2)
    oid = O.id
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _unapprove(db, s, oid)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert snap(db, R2) == before
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_ua_03__failing_commit_keeps_approval(db, s):
    """WOS-UA-03 — a failing commit keeps the approval.
    Rules: unapprove_as_me A6; TC4."""
    O = mk_order(db, s, "1", approved_by=s.U2.id)
    R2 = approver(db, s, O, s.U2, approved=True)
    commit_point(db)
    oid, r2 = O.id, R2.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _unapprove(db, s, oid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    row = reread(db, WorkOrderApprover, r2)
    assert row.approved is True
    assert row.approved_at == T0


# --------------------------------------------------------------------------- #
# list_events
# --------------------------------------------------------------------------- #


def test_wos_n_01__events_newest_first(db, s):
    """WOS-N-01 — returns the order's events newest first with their performer; neither commits nor rolls back.
    Rules: list_events N1; TC6."""
    O = mk_order(db, s, "1")
    E1 = wo_event(db, s, O, "note", None, T0)
    E1.performed_by = s.U2.id
    db.flush()
    E2 = wo_event(db, s, O, "note", None, T1)
    commit_point(db)
    oid, e1, e2 = O.id, E1.id, E2.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.list_events(db, wo_id=oid, workspace_id=s.W1.id)
    # Then 1
    assert [(e.id, p.id if p else None) for e, p in result] == [(e2, None), (e1, s.U2.id)]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_n_02__w2_order_404_no_rollback(db, s):
    """WOS-N-02 — another workspace's order: 404, no rollback.
    Rules: list_events N1; TC6; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)
    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.list_events(db, wo_id=zid, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    assert exc.value.detail == NF(zid)
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db


# --------------------------------------------------------------------------- #
# add_item / update_item / remove_item / get_items
# --------------------------------------------------------------------------- #


def test_wos_ai_01__line_added_invoice_untouched(db, s):
    """WOS-AI-01 — a line is added and committed; a linked draft invoice is not touched; nobody told.
    Rules: add_item M1, M2; TC1, TC2."""
    O = mk_order(db, s, "1", outside=True, uses_inventory=True)
    V = inv(db, s, O, linked=True)
    invl(db, s, V, "100.00")
    commit_point(db)
    oid, vid = O.id, V.id
    before_v = snap(db, V)
    result = svc.add_item(db, item_in=ITEM(s, O), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, WorkOrderItem)
    assert result.id is not None
    rid = result.id
    db.rollback()
    # Then 3
    row = reread(db, WorkOrderItem, rid)
    assert row.work_order_id == oid
    assert row.item_id == s.I1.id
    assert row.quantity == Decimal("2")
    assert row.created_by == s.U2.id
    # Then 4
    assert snap_id(db, AccountInvoice, vid) == before_v
    # Then 5
    assert [(i.description, i.unit_price) for i in LINES(db, vid)] == [("Old line", Decimal("100.00"))]
    # Then 6
    assert notes(db) == []


def test_wos_ai_02__line_clears_approvals_no_notice(db, s):
    """WOS-AI-02 — a line that clears approvals writes no notification.
    Rules: add_item M2."""
    O = mk_order(db, s, "1", uses_inventory=True)
    R3 = approver(db, s, O, s.U3, approved=True)
    commit_point(db)
    r3 = R3.id
    result = svc.add_item(db, item_in=ITEM(s, O), workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id is not None
    db.rollback()
    # Then 2
    assert reread(db, WorkOrderApprover, r3).approved is False
    # Then 3
    assert notes(db) == []


def test_wos_ai_03__no_stock_items_400(db, s):
    """WOS-AI-03 — the manager's 400 passes unchanged, the extra row is gone.
    Rules: add_item M1; TC3."""
    O = mk_order(db, s, "1")
    cp = commit_point(db)
    req = ITEM(s, O)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.add_item(db, item_in=req, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "This work order does not use stock items"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    # Then 6
    assert counts(db) == cp.counts
    db.rollback()
    # Then 7
    assert x_gone(db, x_id)


def test_wos_ai_04__stock_refusal_started(db, s):
    """WOS-AI-04 — a stock refusal on a started order saves nothing.
    Rules: add_item M1; TC3."""
    stock(db, s, s.I2, 2, Decimal("5.00"))
    O = mk_order(db, s, "1", started=True, uses_inventory=True)
    cp = commit_point(db)
    req = ITEM(s, O, item_id=s.I2.id, quantity=Decimal("5"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, item_in=req, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Insufficient stock (2 available, 5 requested)"
    # Then 4
    assert counts(db) == cp.counts


def test_wos_ai_05__failing_commit_no_line(db, s):
    """WOS-AI-05 — a failing commit leaves no line.
    Rules: add_item M1; TC4."""
    O = mk_order(db, s, "1", uses_inventory=True)
    commit_point(db)
    oid = O.id
    req = ITEM(s, O)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_item(db, item_in=req, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_where(db, WorkOrderItem, WorkOrderItem.work_order_id == oid) == 0


def _upd_item(db, s, item_id):
    return svc.update_item(
        db, item_id=item_id, item_in=WorkOrderItemUpdate(quantity=Decimal("3")),
        workspace_id=s.W1.id, user_id=s.U2.id,
    )


def test_wos_ui_01__line_edit_committed(db, s):
    """WOS-UI-01 — a line edit is committed and returned re-read.
    Rules: update_item M1; TC1, TC2."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L = line(db, s, O, s.I1, "2")
    commit_point(db)
    lid = L.id
    result = _upd_item(db, s, lid)
    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == lid
    db.rollback()
    # Then 3
    row = reread(db, WorkOrderItem, lid)
    assert row.quantity == Decimal("3")
    assert row.updated_by == s.U2.id


def test_wos_ui_02__line_edit_clears_approvals_no_notice(db, s):
    """WOS-UI-02 — a line edit that clears approvals writes no notification and touches no invoice.
    Rules: update_item M2."""
    O = mk_order(db, s, "1", outside=True, uses_inventory=True)
    R3 = approver(db, s, O, s.U3, approved=True)
    L = line(db, s, O, s.I1, "2")
    V = inv(db, s, O, linked=True)
    commit_point(db)
    lid, r3, vid = L.id, R3.id, V.id
    before_v = snap(db, V)
    result = _upd_item(db, s, lid)
    # Then 1
    assert result.id == lid
    db.rollback()
    # Then 2
    assert reread(db, WorkOrderApprover, r3).approved is False
    # Then 3
    assert notes(db) == []
    # Then 4
    assert snap_id(db, AccountInvoice, vid) == before_v


def test_wos_ui_03__missing_line_404(db, s):
    """WOS-UI-03 — a missing line: 404 passes unchanged, the extra row is gone.
    Rules: update_item M1; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            _upd_item(db, s, MISSING)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_ui_04__failing_commit_keeps_quantity(db, s):
    """WOS-UI-04 — a failing commit keeps the old quantity.
    Rules: update_item M1; TC4."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L = line(db, s, O, s.I1, "2")
    commit_point(db)
    lid = L.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            _upd_item(db, s, lid)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrderItem, lid).quantity == Decimal("2")


def test_wos_ri_01__line_removed_no_refresh(db, s):
    """WOS-RI-01 — the line is removed and committed; the line is returned without a refresh; nobody told.
    Rules: remove_item M3, M4."""
    O = mk_order(db, s, "1", outside=True, uses_inventory=True)
    L = line(db, s, O, s.I1, "2")
    V = inv(db, s, O, linked=True)
    commit_point(db)
    oid, lid, vid = O.id, L.id, V.id
    before_v = snap(db, V)
    with patch.object(db, "refresh", wraps=db.refresh) as rf:
        result = svc.remove_item(db, item_id=lid, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result.id == lid
    assert result.is_deleted is True
    assert result.deleted_by == s.U2.id
    assert result.work_order_id == oid
    # Then 2
    assert rf.call_count == 0
    db.rollback()
    # Then 3
    assert reread(db, WorkOrderItem, lid).is_deleted is True
    # Then 4
    assert notes(db) == []
    # Then 5
    assert snap_id(db, AccountInvoice, vid) == before_v


def test_wos_ri_02__missing_line_404(db, s):
    """WOS-RI-02 — a missing line: 404, the extra row is gone.
    Rules: remove_item M3; TC3."""
    commit_point(db)
    X, x_id = mk_x(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (_cm, rb):
            svc.remove_item(db, item_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert X not in db
    # Then 5
    assert rb.call_count >= 1
    db.rollback()
    # Then 6
    assert x_gone(db, x_id)


def test_wos_ri_03__failing_commit_keeps_line(db, s):
    """WOS-RI-03 — a failing commit keeps the line.
    Rules: remove_item M3; TC4."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L = line(db, s, O, s.I1, "2")
    commit_point(db)
    lid = L.id
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_item(db, item_id=lid, workspace_id=s.W1.id, user_id=s.U2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, WorkOrderItem, lid).is_deleted is False


def test_wos_gi_01__live_lines(db, s):
    """WOS-GI-01 — returns the order's live lines (compared as a set, BUG-1272); neither commits nor rolls back.
    Rules: get_items M5; TC6."""
    O = mk_order(db, s, "1", uses_inventory=True)
    L1 = line(db, s, O, s.I1, "1")
    line(db, s, O, s.I2, "1", gone=True)
    L3 = line(db, s, O, s.I1, "3")
    commit_point(db)
    oid, l1, l3 = O.id, L1.id, L3.id
    X, _ = mk_x(db)
    with spies(db) as (cm, rb):
        result = svc.get_items(db, wo_id=oid, workspace_id=s.W1.id)
    # Then 1
    assert {i.id for i in result} == {l1, l3}
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert X in db


def test_wos_gi_02__w2_order_404_no_rollback(db, s):
    """WOS-GI-02 — another workspace's order: 404, no rollback.
    Rules: get_items M5; TC6; HR-16."""
    Z = mk_order(db, s, "9", ws="2")
    commit_point(db)
    zid = Z.id
    X, _ = mk_x(db)
    with spies(db) as (_cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_items(db, wo_id=zid, workspace_id=s.W1.id)
    # Then 1
    assert exc.value.status_code == 404
    assert exc.value.detail == NF(zid)
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert X in db
