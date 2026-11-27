"""Unit tests for app/managers/work_order_manager.py.

Implements tests/unit/managers/work_order_manager.cases.md (revision 3,
2026-11-21), one test per case, in card order. Real Postgres session (`db`
fixture). Externals patched: `app.managers.work_order_manager.utcnow`
(always, fixture `_clock`), `app.managers.work_order_manager.settings`
(PROD cards) and `datetime.date` (BD-04, BD-05). No race simulations.

BUG-664 guard (Conventions): stock is seeded only with S / SD / MS (one
opening ledger row at T0); multi-step states are built directly as rows.

Built in normal mode (no local model): every test sits below a
`# [claude] <ID>` comment.
"""

# ruff: noqa: DTZ001, DTZ005, FURB157  (Conventions prescribe naive datetimes and Decimal("q") literals)
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.managers.work_order_manager import work_order_manager as WOM
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.enums import (
    InventoryTypeEnum,
    MachineEventTypeEnum,
    WorkOrderPriorityEnum,
)
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_activity_event import ProjectComponentActivityEvent
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_assignee import WorkOrderAssignee
from app.models.work_order_completer import WorkOrderCompleter
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_type import WorkOrderType
from app.models.workspace_member import WorkspaceMember
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> actors and fixed values
# --------------------------------------------------------------------------- #

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
MISSING = 999999999
NOW = datetime(2026, 3, 10, 9, 0, 0)
T0 = datetime(2026, 1, 5, 8, 0, 0)
T1 = datetime(2026, 3, 1, 8, 0, 0)

# xfail reasons: bug titles from docs/testing/bugs.md
BUGS = {
    381: "Worker display text repeats members and unmatched names",
    665: "Zero or negative quantity accepted and reverses the movement direction",
    1000: "Status event stores a work order id without checking its workspace",
    1016: "Work order accepts another workspace's machine, project component and items",
    1040: "Money rounded half to even in Python, half away from zero in the database",
    1192: "Activity row can be written for another workspace's order, project or component",
    1200: "Approvers with one `assigned_at` come back in no fixed order",
    1204: "Work order that lost its last approver can start with no approval",
    1206: "One person named twice on a sheet entry is dropped with no message",
    1228: "A soft-deleted work order type can be chosen for new work orders and templates",
    1272: "A work order's lines have no sort order",
    1273: "Voided work order lines cannot be listed",
    1279: "A deleted work order's lines stay open",
    1884: "An old work order linked to another workspace's project component gets stuck once `log_event` refuses it",
    2670: "Work order list has no tie-breaker when creation times tie",
    2912: "Line quantity <= 0, negative cost and negative required approvals are accepted",
    2913: "Work order quantity and cost with more than 2 decimals are accepted",
    2914: "A fractional quantity on a stock line is accepted until the order starts",
    2915: "No-op work order edits stamp `updated_by`, log, and clear a draft's approvals",
    2916: "Work order start, complete, void, approval and in-progress line changes take no row lock",
    2917: "Repeating a work order approval re-stamps it and logs it again",
    2918: "A blank work order void reason is accepted",
    2919: "A work order's planned date, end date and cost cannot be cleared",
    2920: "A soft-deleted factory, machine or account can be put on a work order",
    2921: "A work order's machine can sit in another factory than the order",
    2922: "A template whose approvers have all left gives a work order approved at once",
    2924: "The in-progress lock message names four fields; six are locked",
    2925: "Recurrence bulk delete takes 'today' from the server's local date",
    2926: "A work order end date before its planned date is accepted",
    2927: "A work order line's source location can be another workspace's factory or machine",
    2928: "The planning sheet can place an inactive work order template",
    2929: "A draft work order's cost and account can change after its invoice was made",
    2930: "Removing a draft work order's machine makes its Install / Replace / Borrow parts vanish",
    2931: "Work order approvers and approvals can still change after work has started",
}


def xf(*bugs, strict=True):
    """Convention "xfail cards": `xfail BUG-n` (strict) / `(non-strict)`."""
    return pytest.mark.xfail(strict=strict, reason="; ".join(f"BUG-{b}: {BUGS[b]}" for b in bugs))


def D(n):
    """Convention "D(n)" = date(2026, 3, n)."""
    return date(2026, 3, n)


def NOON(n):
    """Convention "NOON(n)"."""
    return datetime(2026, 3, n, 12, 0, 0)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "Time": every test patches the module's utcnow to NOW.
@pytest.fixture(autouse=True)
def _clock():
    with patch("app.managers.work_order_manager.utcnow", return_value=NOW) as m:
        yield m


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, built and flushed in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def s(db):
    """Convention "Standing rows" 1-8, TAG, Y and NEW. `s.W1`, `s.M1`, `s.I1`, ..."""
    r = SimpleNamespace()
    r.TAG = uuid.uuid4().hex[:8]
    r.Y = datetime.now().year
    r.NEW = f"WO-{r.Y}-001"
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
    r.WT2 = _add(db, WorkOrderType(workspace_id=r.W1.id, name="Repair"))
    r.WT9 = _add(db, WorkOrderType(workspace_id=r.W2.id, name="Service"))
    r.F0 = _add(db, Factory(workspace_id=r.W0.id, name="Plant Zero", abbreviation="P0"))
    r.F1 = _add(db, Factory(workspace_id=r.W1.id, name="Plant One", abbreviation="P1"))
    r.F2 = _add(db, Factory(workspace_id=r.W1.id, name="Plant Two", abbreviation="P2"))
    r.F9 = _add(db, Factory(workspace_id=r.W2.id, name="Plant Nine", abbreviation="P9"))
    r.M0 = _add(db, Machine(workspace_id=r.W0.id, factory_id=r.F0.id, name="Press"))
    r.M1 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F1.id, name="Lathe 3"))
    r.M2 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F1.id, name="Lathe 4"))
    r.M3 = _add(db, Machine(workspace_id=r.W1.id, factory_id=r.F2.id, name="Pump"))
    r.M9 = _add(db, Machine(workspace_id=r.W2.id, factory_id=r.F9.id, name="Press"))
    for name, ws, label in (
        ("I0", r.W0, "Bolt"), ("I1", r.W1, "Bolt"), ("I2", r.W1, "Bearing"),
        ("I3", r.W1, "Belt"), ("I9", r.W2, "Bolt"),
    ):
        setattr(r, name, _add(db, Item(workspace_id=ws.id, name=label, name_normalized=label.lower(), unit="pcs")))
    for name, ws, label in (
        ("A0", r.W0, "Rahman Traders"), ("A1", r.W1, "Rahman Traders"),
        ("A9", r.W2, "Rahman Traders"), ("A2", r.W1, "Beta Supplies"),
    ):
        setattr(r, name, _add(db, Account(workspace_id=ws.id, name=label, is_active=True, is_deleted=False)))
    r.PJ1 = _add(db, Project(workspace_id=r.W1.id, factory_id=r.F1.id, name="Project One", description="Main"))
    r.PJ9 = _add(db, Project(workspace_id=r.W2.id, factory_id=r.F9.id, name="Project Nine", description="Main"))
    r.PC1 = _add(db, ProjectComponent(workspace_id=r.W1.id, project_id=r.PJ1.id, name="Panel A"))
    r.PC9 = _add(db, ProjectComponent(workspace_id=r.W2.id, project_id=r.PJ9.id, name="Panel Z"))
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def mk_order(db, s, n, **cols):
    """Convention "order N"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": s.W1.id,
        "work_order_number": f"WO-{s.TAG}-{n}",
        "work_order_type_id": s.WT1.id,
        "title": "Service — Lathe 3",
        "factory_id": s.F1.id,
        "machine_id": s.M1.id,
        "status": "DRAFT",
        "priority": WorkOrderPriorityEnum.MEDIUM,
        "uses_inventory": True,
        "description": "Old desc",
        "cost": Decimal("100.00"),
        "planned_date": D(12),
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, WorkOrder(**fields))


def STAMPED(s):
    """Convention "stamped"."""
    return {"approved_by": s.U1.id, "approved_at": T0}


def STARTED(s):
    """Convention "started" (includes stamped)."""
    return {"status": "IN_PROGRESS", "started_by": s.U1.id, "started_at": T1, "planned_date": D(1), **STAMPED(s)}


def COMPLETED(s):
    """Convention "completed"."""
    return {"status": "COMPLETED", "completed_at": T1, "completed_by": s.U1.id}


def VOIDED(s):
    """Convention "voided"."""
    return {"status": "VOIDED", "voided_at": T1, "voided_by": s.U1.id, "void_note": "Old"}


def GONE(s):
    """Convention "gone" (order)."""
    return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": s.U1.id}


def mk_line(db, s, o, item, q, **cols):
    """Convention "line(O, I, "q")"."""
    fields = {
        "workspace_id": s.W1.id,
        "work_order_id": o.id,
        "item_id": item.id,
        "quantity": Decimal(q),
        "uses_inventory": True,
        "source_location_type": "storage",
        "source_location_id": s.F1.id,
        "action_type": "CONSUME",
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, WorkOrderItem(**fields))


def CONSUMED(s, t):
    """Convention "consumed(t)"."""
    return {"consumed_at": T1, "consumed_by": s.U1.id, "unit_cost": Decimal("2.50"), "total_cost": Decimal(t)}


def LINE_GONE(s):
    """Convention "gone" (line)."""
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": s.U1.id}


def mk_approver(db, s, o, u, **cols):
    """Convention "approver(O, U)"."""
    fields = {
        "workspace_id": s.W1.id, "work_order_id": o.id, "user_id": u.id,
        "assigned_by": s.U1.id, "assigned_at": T0, "approved": False,
    }
    fields.update(cols)
    return _add(db, WorkOrderApprover(**fields))


# Convention "approved" (approver)
APPROVED = {"approved": True, "approved_at": T0}


def mk_assignee(db, s, o, u, **cols):
    """Convention "assignee(O, U)"."""
    fields = {"workspace_id": s.W1.id, "work_order_id": o.id, "user_id": u.id}
    fields.update(cols)
    return _add(db, WorkOrderAssignee(**fields))


def mk_event(db, s, o, etype, meta, at, **cols):
    """Convention "event(O, "type", meta, at)"."""
    fields = {
        "workspace_id": s.W1.id, "work_order_id": o.id, "event_type": etype,
        "description": "Setup", "metadata_json": meta, "created_at": at,
    }
    fields.update(cols)
    return _add(db, WorkOrderEvent(**fields))


def mk_status_row(db, s, m, st, at, **cols):
    """Convention "status row(M, "S", at)"."""
    fields = {
        "workspace_id": s.W1.id, "machine_id": m.id, "event_type": "status_updated",
        "description": "Setup", "metadata_json": {"status": st}, "created_at": at,
    }
    fields.update(cols)
    return _add(db, MachineActivityEvent(**fields))


def _bucket(db, s, f, item, q, p, inv_type, **cols):
    ws_id = cols.pop("workspace_id", s.W1.id)
    inv = _add(db, Inventory(
        workspace_id=ws_id, factory_id=f.id, item_id=item.id, inventory_type=inv_type,
        qty=q, avg_price=None if p is None else Decimal(str(p)), is_deleted=False, is_active=True,
        created_by=s.U2.id, updated_by=s.U2.id, **cols,
    ))
    pd = None if p is None else Decimal(str(p))
    uc = pd or Decimal("0")
    _add(db, InventoryLedger(
        workspace_id=ws_id, inventory_type=inv_type, factory_id=f.id, item_id=item.id,
        transaction_type="opening", quantity=q, unit_cost=uc,
        total_cost=(uc * Decimal(q)).quantize(Decimal("0.01")),
        qty_before=0, qty_after=q, avg_price_before=None, avg_price_after=pd,
        source_type="manual", source_id=1, performed_by=s.U2.id, performed_at=T0,
    ))
    return inv


def mk_S(db, s, f, item, q, p, **cols):
    """Convention "S(F, I, q, p)": STORAGE bucket + opening ledger row at T0."""
    return _bucket(db, s, f, item, q, p, STORAGE, **cols)


def mk_SD(db, s, f, item, q, p, **cols):
    """Convention "SD(F, I, q, p)": DAMAGED bucket + opening ledger row at T0."""
    return _bucket(db, s, f, item, q, p, DAMAGED, **cols)


def mk_MS(db, s, m, item, q, p):
    """Convention "MS(M, I, q, p)": machine_items row + opening machine ledger row at T0."""
    mi = _add(db, MachineItem(workspace_id=s.W1.id, machine_id=m.id, item_id=item.id, qty=q))
    pd = Decimal(str(p))
    _add(db, MachineItemLedger(
        workspace_id=s.W1.id, machine_id=m.id, item_id=item.id, transaction_type="opening",
        quantity=q, unit_cost=pd, total_cost=(pd * q).quantize(Decimal("0.01")),
        qty_before=0, qty_after=q, value_before=Decimal("0"), value_after=(pd * q).quantize(Decimal("0.01")),
        avg_price_before=Decimal("0"), avg_price_after=pd,
        source_type="manual", source_id=1, performed_by=s.U2.id, performed_at=T0,
    ))
    return mi


def mk_template(db, s, **cols):
    """Convention "template"."""
    fields = {
        "workspace_id": s.W1.id, "template_name": "Oil change", "work_order_type_id": s.WT1.id,
        "uses_inventory": False, "requires_approval": False, "is_active": True, "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, WorkOrderTemplate(**fields))


# Convention "weekly" (template)
WEEKLY = {"is_recurring": True, "recurrence_type": "weekly", "recurrence_day": 0}


def mk_tline(db, s, t, item, q, **cols):
    """Convention "tline(T, I, "q")"."""
    fields = {
        "workspace_id": s.W1.id, "work_order_template_id": t.id, "item_id": item.id,
        "quantity": Decimal(q), "action_type": "CONSUME",
    }
    fields.update(cols)
    return _add(db, WorkOrderTemplateItem(**fields))


def mk_tapprover(db, s, t, u, **cols):
    """Convention "tapprover(T, U)"."""
    fields = {"workspace_id": s.W1.id, "work_order_template_id": t.id, "user_id": u.id}
    fields.update(cols)
    return _add(db, WorkOrderTemplateApprover(**fields))


def mk_invoice(db, s, st, **cols):
    """Convention "invoice("s")"."""
    fields = {
        "workspace_id": s.W1.id, "account_id": s.A1.id, "invoice_type": "receivable",
        "invoice_amount": Decimal("100.00"), "invoice_date": date(2026, 3, 1), "invoice_status": st,
    }
    fields.update(cols)
    return _add(db, AccountInvoice(**fields))


def mk_type(db, s, name, **cols):
    """A `WorkOrderType` row written in a Given (W1 unless stated)."""
    fields = {"workspace_id": s.W1.id, "name": name}
    fields.update(cols)
    return _add(db, WorkOrderType(**fields))


# Convention "gone" (factory, type) / (machine, account)
GONE_FT = {"is_deleted": True}
GONE_MA = {"is_deleted": True, "is_active": False}


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #

_MARK_TABLES = (WorkOrderEvent, MachineActivityEvent, InventoryLedger, MachineItemLedger, ProjectComponentActivityEvent)


def mark(db):
    """Convention "mark": highest id of the five event/ledger tables (0 when empty)."""
    return SimpleNamespace(**{
        m.__tablename__: db.execute(select(func.coalesce(func.max(m.id), 0))).scalar_one() for m in _MARK_TABLES
    })


def _since(mk, model):
    return getattr(mk, model.__tablename__)


def ev(db, mk, o):
    """Convention "ev(O)"."""
    db.expire_all()
    rows = db.execute(
        select(WorkOrderEvent).where(WorkOrderEvent.work_order_id == o.id, WorkOrderEvent.id > _since(mk, WorkOrderEvent))
        .order_by(WorkOrderEvent.id)
    ).scalars().all()
    return [(e.event_type, e.description) for e in rows]


def evrows(db, mk, o):
    db.expire_all()
    return db.execute(
        select(WorkOrderEvent).where(WorkOrderEvent.work_order_id == o.id, WorkOrderEvent.id > _since(mk, WorkOrderEvent))
        .order_by(WorkOrderEvent.id)
    ).scalars().all()


def evrow(db, mk, o, etype):
    """Convention "evrow(O, "t")": the one new event row of that type."""
    rows = [e for e in evrows(db, mk, o) if e.event_type == etype]
    assert len(rows) == 1, f"expected one {etype!r} event, got {len(rows)}"
    return rows[0]


def actrows(db, mk, m):
    db.expire_all()
    return db.execute(
        select(MachineActivityEvent)
        .where(MachineActivityEvent.machine_id == m.id, MachineActivityEvent.id > _since(mk, MachineActivityEvent))
        .order_by(MachineActivityEvent.id)
    ).scalars().all()


def acts(db, mk, m):
    """Convention "acts(M)"."""
    return [(a.event_type, a.description) for a in actrows(db, mk, m)]


def stat(db, mk, m):
    """Convention "stat(M)"."""
    return [a.metadata_json["status"] for a in actrows(db, mk, m) if a.event_type == "status_updated"]


def led(db, mk, s, f, item, inv_type):
    """Convention "led(F, I, TYPE)": new inventory ledger rows of (W1, TYPE, F, I), by id."""
    db.expire_all()
    return db.execute(
        select(InventoryLedger).where(
            InventoryLedger.workspace_id == s.W1.id, InventoryLedger.inventory_type == inv_type,
            InventoryLedger.factory_id == f.id, InventoryLedger.item_id == item.id,
            InventoryLedger.id > _since(mk, InventoryLedger),
        ).order_by(InventoryLedger.id)
    ).scalars().all()


def mled(db, mk, s, m, item):
    """Convention "mled(M, I)"."""
    db.expire_all()
    return db.execute(
        select(MachineItemLedger).where(
            MachineItemLedger.workspace_id == s.W1.id, MachineItemLedger.machine_id == m.id,
            MachineItemLedger.item_id == item.id, MachineItemLedger.id > _since(mk, MachineItemLedger),
        ).order_by(MachineItemLedger.id)
    ).scalars().all()


def qty(db, s, f, item, inv_type):
    """Convention "qty(F, I, TYPE)": re-read Inventory.qty of the bucket."""
    db.expire_all()
    return db.execute(
        select(Inventory.qty).where(
            Inventory.workspace_id == s.W1.id, Inventory.factory_id == f.id,
            Inventory.item_id == item.id, Inventory.inventory_type == inv_type,
        )
    ).scalar_one()


def mqty(db, s, m, item):
    """Convention "mqty(M, I)": re-read MachineItem.qty, Decimal("0") with no row."""
    db.expire_all()
    v = db.execute(
        select(MachineItem.qty).where(
            MachineItem.workspace_id == s.W1.id, MachineItem.machine_id == m.id, MachineItem.item_id == item.id,
        )
    ).scalar_one_or_none()
    return Decimal("0") if v is None else v


def pcacts(db, mk, c):
    """Convention "pcacts(C)"."""
    db.expire_all()
    return db.execute(
        select(ProjectComponentActivityEvent).where(
            ProjectComponentActivityEvent.project_component_id == c.id,
            ProjectComponentActivityEvent.id > _since(mk, ProjectComponentActivityEvent),
        ).order_by(ProjectComponentActivityEvent.id)
    ).scalars().all()


def reread(db, model, row_id):
    """Convention "re-read X"."""
    db.expire_all()
    return db.get(model, row_id)


def snap(db, row):
    """Convention "unchanged(X)": every column value, re-read."""
    model = type(row)
    db.expire_all()
    fresh = db.get(model, row.id)
    return {c.key: getattr(fresh, c.key) for c in sa_inspect(model).mapper.column_attrs}


_COUNT_TABLES = (
    "work_orders", "work_order_items", "work_order_approvers", "work_order_assignees",
    "work_order_completers", "work_order_events", "inventory", "inventory_ledger", "machine_items",
    "machine_item_ledger", "machine_activity_events", "project_component_activity_events", "account_invoices",
)


def counts(db):
    """Convention "nothing written": row counts of the 13 tables (all workspaces)."""
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in _COUNT_TABLES}


def clean(db):
    """Convention "session clean"."""
    return (not db.new, not db.dirty, not db.deleted)


def rows_of(db, model, **where):
    db.expire_all()
    q = select(model)
    for k, v in where.items():
        q = q.where(getattr(model, k) == v)
    return db.execute(q.order_by(model.id)).scalars().all()


class Recorder:
    """Convention "statement recorder": SQL sent from the start of the When."""

    def __init__(self, db):
        self.engine = db.get_bind().engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    _WRITES = ("UPDATE", "INSERT", "DELETE")

    def _first_write(self):
        return next((i for i, st in enumerate(self.statements) if st.lstrip().upper().startswith(self._WRITES)),
                    len(self.statements))

    @staticmethod
    def _names(st, table):
        """The statement is a SELECT whose FROM / JOIN part names `table`."""
        up = st.upper()
        parts = re.split(r"\bFROM\b", up, maxsplit=1)
        if not up.lstrip().startswith("SELECT") or len(parts) < 2:
            return False
        from_part = re.split(r"\bWHERE\b|\bORDER BY\b|\bLIMIT\b|\bFOR UPDATE\b|\bGROUP BY\b", parts[1])[0]
        return re.search(rf"\b{table.upper()}\b", from_part) is not None

    @staticmethod
    def _covers(st, table):
        """Convention "a lock clause covers t"."""
        up = st.upper()
        m = re.search(r"FOR UPDATE(\s+OF\s+(.*?))?(\s+NOWAIT|\s+SKIP LOCKED)?\s*$", up, re.DOTALL)
        if not m or m.group(3):
            return False
        if m.group(2) is None:
            return True
        return table.upper() in [x.strip().strip('"') for x in m.group(2).split(",")]

    def locks(self, table):
        """Convention "locks t": some SELECT naming t, lock clause covering t, before the first write."""
        return any(self._names(st, table) and self._covers(st, table)
                   for st in self.statements[:self._first_write()])

    def locks_first(self, table):
        """Convention "locks first t": the first SELECT naming t carries the lock and comes before any write."""
        first = next((i for i, st in enumerate(self.statements) if self._names(st, table)), None)
        return first is not None and first < self._first_write() and self._covers(self.statements[first], table)

    def order_part(self, table):
        """The text after ORDER BY in the first SELECT whose FROM names `table` ("" without one)."""
        st = next((st for st in self.statements if self._names(st, table)), "")
        return st.split("ORDER BY", 1)[1] if "ORDER BY" in st else ""


def PROD(b):
    """Convention "PROD(b)": production settings with WORK_ORDER_ALLOW_DEV_DELETE = b."""
    return _Prod(b)


class _Prod:
    def __init__(self, b):
        self.b = b

    def __enter__(self):
        self.p = patch("app.managers.work_order_manager.settings")
        st = self.p.__enter__()
        st.ENVIRONMENT = "production"
        st.WORK_ORDER_ALLOW_DEV_DELETE = self.b
        return st

    def __exit__(self, *exc):
        return self.p.__exit__(*exc)


# --------------------------------------------------------------------------- #
# Conventions -> Requests
# --------------------------------------------------------------------------- #


def CR(s, **k):
    from app.schemas.work_order import WorkOrderCreate
    return WorkOrderCreate(**{"work_order_type_id": s.WT1.id, "factory_id": s.F1.id, "machine_id": s.M1.id, **k})


def CREATE(db, s, data):
    return WOM.create_work_order(db, data=data, workspace_id=s.W1.id, user_id=s.U1.id)


def FROM(db, s, t, **k):
    from app.schemas.work_order_template import WorkOrderFromTemplateCreate
    return WOM.create_work_order_from_template(
        db, template_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id,
        overrides=WorkOrderFromTemplateCreate(**{"machine_id": s.M1.id, **k}),
    )


def UP(db, s, o, **k):
    from app.schemas.work_order import WorkOrderUpdate
    return WOM.update_work_order(db, wo_id=o.id, data=WorkOrderUpdate(**k), workspace_id=s.W1.id, user_id=s.U2.id)


def ITEM(s, o, **k):
    from app.schemas.work_order_item import WorkOrderItemCreate
    return WorkOrderItemCreate(**{
        "work_order_id": o.id, "item_id": s.I1.id, "quantity": Decimal("2"), "uses_inventory": True,
        "source_location_type": "storage", "source_location_id": s.F1.id, **k,
    })


def ADD(db, s, data):
    return WOM.add_item(db, data=data, workspace_id=s.W1.id, user_id=s.U2.id)


def UIT(db, s, line, **k):
    from app.schemas.work_order_item import WorkOrderItemUpdate
    return WOM.update_item(db, item_id=line.id, data=WorkOrderItemUpdate(**k), workspace_id=s.W1.id, user_id=s.U2.id)


def SHEET(s, **k):
    from app.schemas.work_order import WorkOrderSheetEntryCreate
    return WorkOrderSheetEntryCreate(**{"machine_id": s.M1.id, "work_order_type_id": s.WT1.id, "planned_date": D(12), **k})


def ENTRY(db, s, data):
    return WOM.sheet_entry(db, data=data, workspace_id=s.W1.id, user_id=s.U1.id)


def FIN(db, s, o, **k):
    return WOM.finalize_completion(db, wo=o, performed_by_user_id=s.U2.id, **k)


# =========================================================================== #
# Pure helpers
# =========================================================================== #


# [claude] WOM-LK-01
def test_wom_lk_01__completed_and_voided_locked():
    """WOM-LK-01 — completed and voided are locked.
    Rules: _is_locked R1."""
    result = [WOM._is_locked(SimpleNamespace(status=st)) for st in ["COMPLETED", "VOIDED"]]
    # Then 1
    assert result == [True, True]


# [claude] WOM-LK-02
def test_wom_lk_02__other_statuses_not_locked():
    """WOM-LK-02 — draft, in progress, lower-case and empty text are not locked.
    Rules: _is_locked R1."""
    result = [WOM._is_locked(SimpleNamespace(status=st)) for st in ["DRAFT", "IN_PROGRESS", "completed", ""]]
    # Then 1
    assert result == [False, False, False, False]


# [claude] WOM-HRA-01
def test_wom_hra_01__one_approved_is_recorded(db, s):
    """WOM-HRA-01 — one approved approver among two is a recorded approval.
    Rules: _has_recorded_approvals R1."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3, **APPROVED)
    result = WOM._has_recorded_approvals(db, o.id, s.W1.id)
    # Then 1
    assert result is True


# [claude] WOM-HRA-02
def test_wom_hra_02__no_approval_not_recorded(db, s):
    """WOM-HRA-02 — approvers with no approval, and no approvers, are not recorded approvals.
    Rules: _has_recorded_approvals R1."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    p = mk_order(db, s, "2")
    result = (WOM._has_recorded_approvals(db, o.id, s.W1.id), WOM._has_recorded_approvals(db, p.id, s.W1.id))
    # Then 1
    assert result == (False, False)


# [claude] WOM-HRA-03
def test_wom_hra_03__other_rows_do_not_count(db, s):
    """WOM-HRA-03 — approved rows of other workspaces and of the neighbour orders do not count.
    Rules: _has_recorded_approvals R1."""
    o1 = mk_order(db, s, "1")
    o2 = mk_order(db, s, "2")
    o3 = mk_order(db, s, "3")
    mk_approver(db, s, o1, s.U2, **APPROVED)
    mk_approver(db, s, o3, s.U2, **APPROVED)
    mk_approver(db, s, o2, s.U3, **APPROVED, workspace_id=s.W0.id)
    mk_approver(db, s, o2, s.U4, **APPROVED, workspace_id=s.W2.id)
    result = WOM._has_recorded_approvals(db, o2.id, s.W1.id)
    # Then 1
    assert result is False


# [claude] WOM-IA-01
def test_wom_ia_01__stored_order_approvable(db, s):
    """WOM-IA-01 — a stored order with a title and a factory is approvable.
    Rules: is_approvable R1, R2."""
    o = mk_order(db, s, "1")
    result = WOM.is_approvable(db, o)
    # Then 1
    assert result is True


# [claude] WOM-IA-02
def test_wom_ia_02__blank_title_not_approvable(db, s):
    """WOM-IA-02 — a blank or missing title is not approvable.
    Rules: is_approvable R1, R2."""
    result = [WOM.is_approvable(db, SimpleNamespace(title=t, factory_id=s.F1.id)) for t in ["   ", None, ""]]
    # Then 1
    assert result == [False, False, False]


# [claude] WOM-IA-03
def test_wom_ia_03__no_factory_not_approvable(db):
    """WOM-IA-03 — no factory is not approvable.
    Rules: is_approvable R1."""
    result = WOM.is_approvable(db, SimpleNamespace(title="Service", factory_id=None))
    # Then 1
    assert result is False


# [claude] WOM-GAP-01
def test_wom_gap_01__blank_title_first(db):
    """WOM-GAP-01 — a blank title is reported first, even with no factory.
    Rules: approvability_gap_reason R1."""
    result = [WOM.approvability_gap_reason(db, SimpleNamespace(title=t, factory_id=None)) for t in ["  ", None]]
    # Then 1
    assert result == ["Work order setup is incomplete", "Work order setup is incomplete"]


# [claude] WOM-GAP-02
def test_wom_gap_02__no_factory(db):
    """WOM-GAP-02 — a title without a factory asks for the factory.
    Rules: approvability_gap_reason R2."""
    result = WOM.approvability_gap_reason(db, SimpleNamespace(title="Service", factory_id=None))
    # Then 1
    assert result == "Set a factory before approvals can proceed"


# [claude] WOM-GAP-03
def test_wom_gap_03__complete_no_gap(db, s):
    """WOM-GAP-03 — a complete order has no gap.
    Rules: approvability_gap_reason R3."""
    o = mk_order(db, s, "1")
    result = WOM.approvability_gap_reason(db, o)
    # Then 1
    assert result is None


# [claude] WOM-FSV-01
def test_wom_fsv_01__none_dash():
    """WOM-FSV-01 — None shows as a dash.
    Rules: _format_scalar_value R1."""
    result = WOM._format_scalar_value("cost", None)
    # Then 1
    assert result == "—"


# [claude] WOM-FSV-02
def test_wom_fsv_02__dates_iso():
    """WOM-FSV-02 — dates and datetimes show as ISO text.
    Rules: _format_scalar_value R2."""
    result = [WOM._format_scalar_value("planned_date", D(10)),
              WOM._format_scalar_value("planned_date", datetime(2026, 3, 10, 9, 30, 0))]
    # Then 1
    assert result == ["2026-03-10", "2026-03-10T09:30:00"]


# [claude] WOM-FSV-03
def test_wom_fsv_03__decimal_normalised():
    """WOM-FSV-03 — a whole Decimal shows without decimals, another is normalised.
    Rules: _format_scalar_value R3."""
    result = [WOM._format_scalar_value("cost", Decimal(v)) for v in ["150.00", "150.50", "0.05", "1000"]]
    # Then 1
    assert result == ["150", "150.5", "0.05", "1000"]


# [claude] WOM-FSV-04
def test_wom_fsv_04__enum_value():
    """WOM-FSV-04 — an enum shows its value.
    Rules: _format_scalar_value R4."""
    result = WOM._format_scalar_value("priority", WorkOrderPriorityEnum.HIGH)
    # Then 1
    assert result == "HIGH"


# [claude] WOM-FSV-05
def test_wom_fsv_05__other_values_trimmed():
    """WOM-FSV-05 — other values are trimmed text; blank text shows as a dash; the field name is not used.
    Rules: _format_scalar_value R5."""
    result = [WOM._format_scalar_value("description", "  Oil  "), WOM._format_scalar_value("description", "   "),
              WOM._format_scalar_value("required_approvals", 2), WOM._format_scalar_value("cost", "  Oil  ")]
    # Then 1
    assert result == ["Oil", "—", "2", "Oil"]


# [claude] WOM-VAR-01
def test_wom_var_01__missing_gives_none():
    """WOM-VAR-01 — a missing planned date or actual time gives None.
    Rules: _variance_vs_planned R1."""
    result = (WOM._variance_vs_planned(None, NOW), WOM._variance_vs_planned(D(10), None))
    # Then 1
    assert result == (None, None)


# [claude] WOM-VAR-02
def test_wom_var_02__same_day_on_plan():
    """WOM-VAR-02 — the same day is on plan, whatever the time of day.
    Rules: _variance_vs_planned R2, R3, R4."""
    result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 10, 23, 59, 0))
    # Then 1
    assert result == {"planned_date": "2026-03-10", "variance_days": 0, "variance_label": "On plan"}


# [claude] WOM-VAR-03
def test_wom_var_03__one_day_late():
    """WOM-VAR-03 — one day late is singular.
    Rules: _variance_vs_planned R2, R3."""
    result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 11, 0, 30, 0))
    # Then 1
    assert result == {"planned_date": "2026-03-10", "variance_days": 1, "variance_label": "1 day late"}


# [claude] WOM-VAR-04
def test_wom_var_04__three_days_late():
    """WOM-VAR-04 — three days late is plural.
    Rules: _variance_vs_planned R3."""
    result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 13, 8, 0, 0))
    # Then 1
    assert result == {"planned_date": "2026-03-10", "variance_days": 3, "variance_label": "3 days late"}


# [claude] WOM-VAR-05
def test_wom_var_05__one_day_early():
    """WOM-VAR-05 — one day early is negative and singular.
    Rules: _variance_vs_planned R2, R3."""
    result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 9, 23, 0, 0))
    # Then 1
    assert result == {"planned_date": "2026-03-10", "variance_days": -1, "variance_label": "1 day early"}


# [claude] WOM-VAR-06
def test_wom_var_06__plain_date_two_days_early():
    """WOM-VAR-06 — a plain date two days early is plural.
    Rules: _variance_vs_planned R2, R3."""
    result = WOM._variance_vs_planned(D(10), D(8))
    # Then 1
    assert result == {"planned_date": "2026-03-10", "variance_days": -2, "variance_label": "2 days early"}


# [claude] WOM-SMA-01
def test_wom_sma_01__no_planned_date():
    """WOM-SMA-01 — without a planned date only the actual time is given.
    Rules: _schedule_metadata_for_actual R1, R2."""
    result = WOM._schedule_metadata_for_actual(SimpleNamespace(planned_date=None), NOW, actual_field="started_at")
    # Then 1
    assert result == {"started_at": "2026-03-10T09:00:00"}


# [claude] WOM-SMA-02
def test_wom_sma_02__variance_keys_added():
    """WOM-SMA-02 — with a planned date the variance keys are added.
    Rules: _schedule_metadata_for_actual R1, R2."""
    result = WOM._schedule_metadata_for_actual(SimpleNamespace(planned_date=D(8)), NOW, actual_field="completed_at")
    # Then 1
    assert result == {"completed_at": "2026-03-10T09:00:00", "planned_date": "2026-03-08", "variance_days": 2,
                      "variance_label": "2 days late"}


# [claude] WOM-SWM-01
def test_wom_swm_01__assigned_text_ids_starter(db, s):
    """WOM-SWM-01 — the assigned text, assignee ids in row order and the starter.
    Rules: _started_worker_metadata R1."""
    o = mk_order(db, s, "1", assigned_to="Sara Khan, Rahim Uddin")
    mk_assignee(db, s, o, s.U3)
    mk_assignee(db, s, o, s.U2)
    result = WOM._started_worker_metadata(db, o, s.W1.id, s.U1.id)
    # Then 1
    assert result == {"assigned_to": "Sara Khan, Rahim Uddin", "assignee_user_ids": [s.U3.id, s.U2.id],
                      "started_by_user_id": s.U1.id}


# [claude] WOM-SWM-02
def test_wom_swm_02__no_text_no_rows(db, s):
    """WOM-SWM-02 — no assigned text and no assignee rows.
    Rules: _started_worker_metadata R1."""
    o = mk_order(db, s, "1")
    p = mk_order(db, s, "2")
    mk_assignee(db, s, p, s.U3)
    result = WOM._started_worker_metadata(db, o, s.W1.id, s.U2.id)
    # Then 1
    assert result == {"assigned_to": None, "assignee_user_ids": [], "started_by_user_id": s.U2.id}


# [claude] WOM-CFC-01
def test_wom_cfc_01__one_changed_field(db, s):
    """WOM-CFC-01 — a changed logged field gives one entry; title and updated_by are ignored.
    Rules: _collect_field_changes R1, R3."""
    o = mk_order(db, s, "1")
    result = WOM._collect_field_changes(db, o, {"title": "Other", "updated_by": s.U2.id, "description": "New desc"})
    # Then 1
    assert result == [{"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]


# [claude] WOM-CFC-02
def test_wom_cfc_02__equal_values_no_entry(db, s):
    """WOM-CFC-02 — equal values, also 150.00 against 150, give no entry.
    Rules: _collect_field_changes R2."""
    o = mk_order(db, s, "1", cost=Decimal("150.00"))
    result = WOM._collect_field_changes(db, o, {"cost": Decimal("150"), "description": "Old desc", "planned_date": D(12)})
    # Then 1
    assert result == []


# [claude] WOM-CFC-03
def test_wom_cfc_03__logged_field_order(db, s):
    """WOM-CFC-03 — entries follow the logged-field order, not the dict's.
    Rules: _collect_field_changes R1, R3."""
    o = mk_order(db, s, "1", completion_notes=None)
    result = WOM._collect_field_changes(
        db, o, {"completion_notes": "Done", "priority": WorkOrderPriorityEnum.HIGH, "description": "New desc"})
    # Then 1
    assert [c["field"] for c in result] == ["description", "priority", "completion_notes"]
    # Then 2
    assert result[1] == {"field": "priority", "label": "Priority", "from_value": "MEDIUM", "to_value": "HIGH"}
    # Then 3
    assert result[2] == {"field": "completion_notes", "label": "Completion notes", "from_value": "—", "to_value": "Done"}


# [claude] WOM-CFC-04
def test_wom_cfc_04__type_names(db, s):
    """WOM-CFC-04 — the type change shows type names.
    Rules: _collect_field_changes R3."""
    o = mk_order(db, s, "1")
    result = WOM._collect_field_changes(db, o, {"work_order_type_id": s.WT2.id})
    # Then 1
    assert result == [{"field": "work_order_type_id", "label": "Work order type", "from_value": "Service",
                       "to_value": "Repair"}]


# [claude] WOM-CFC-05
def test_wom_cfc_05__dates_and_money_formatted(db, s):
    """WOM-CFC-05 — dates and money are formatted.
    Rules: _collect_field_changes R3."""
    o = mk_order(db, s, "1", planned_date=None)
    result = WOM._collect_field_changes(db, o, {"planned_date": D(14), "cost": Decimal("150.50")})
    # Then 1
    assert result == [
        {"field": "planned_date", "label": "Planned date", "from_value": "—", "to_value": "2026-03-14"},
        {"field": "cost", "label": "Cost", "from_value": "100", "to_value": "150.5"},
    ]


# [claude] WOM-TN-01
def test_wom_tn_01__none_dash(db, s):
    """WOM-TN-01 — None shows as a dash.
    Rules: _work_order_type_name R1."""
    result = WOM._work_order_type_name(db, None, s.W1.id)
    # Then 1
    assert result == "—"


# [claude] WOM-TN-02
def test_wom_tn_02__type_of_workspace_named(db, s):
    """WOM-TN-02 — a type of the workspace, also a deleted one, gives its name.
    Rules: _work_order_type_name R2."""
    wtd = mk_type(db, s, "Overhaul", **GONE_FT)
    result = (WOM._work_order_type_name(db, s.WT2.id, s.W1.id), WOM._work_order_type_name(db, wtd.id, s.W1.id))
    # Then 1
    assert result == ("Repair", "Overhaul")


# [claude] WOM-TN-03
def test_wom_tn_03__foreign_or_unknown_hash_id(db, s):
    """WOM-TN-03 — a type of W0 or W2, or an unknown id, shows as #id.
    Rules: _work_order_type_name R2."""
    result = [WOM._work_order_type_name(db, t, s.W1.id) for t in [s.WT0.id, s.WT9.id, MISSING]]
    # Then 1
    assert result == [f"#{s.WT0.id}", f"#{s.WT9.id}", "#999999999"]


# [claude] WOM-RIA-01
def test_wom_ria_01__set_account_returned(db, s):
    """WOM-RIA-01 — a set account is returned.
    Rules: resolve_invoice_account_id R1."""
    o = mk_order(db, s, "1", account_id=s.A1.id)
    result = WOM.resolve_invoice_account_id(o)
    # Then 1
    assert result == s.A1.id


# [claude] WOM-RIA-02
def test_wom_ria_02__no_account_422(db, s):
    """WOM-RIA-02 — no account is refused with 422.
    Rules: resolve_invoice_account_id R2."""
    o = mk_order(db, s, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.resolve_invoice_account_id(o)
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Set an account on the work order before creating an invoice"


# [claude] WOM-RIA-03
def test_wom_ria_03__account_zero_422():
    """WOM-RIA-03 — account id 0 is refused the same way.
    Rules: resolve_invoice_account_id R2."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.resolve_invoice_account_id(SimpleNamespace(account_id=0))
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Set an account on the work order before creating an invoice"


# [claude] WOM-DT-01
def test_wom_dt_01__given_type_name_wins(db, s):
    """WOM-DT-01 — a given type name wins over the stored type.
    Rules: _derive_default_title R1, R2, R4."""
    result = WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT1.id, factory_id=s.F1.id,
                                       machine_id=s.M1.id, project_component_id=None, type_name="Overhaul")
    # Then 1
    assert result == "Overhaul — Lathe 3"


# [claude] WOM-DT-02
def test_wom_dt_02__type_name_from_type(db, s):
    """WOM-DT-02 — without a type name (or an empty one) the type's name is used.
    Rules: _derive_default_title R1, R4."""
    result = [WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT2.id, factory_id=s.F1.id,
                                        machine_id=s.M1.id, project_component_id=None, type_name=n) for n in [None, ""]]
    # Then 1
    assert result == ["Repair — Lathe 3", "Repair — Lathe 3"]


# [claude] WOM-DT-03
def test_wom_dt_03__deleted_type_names(db, s):
    """WOM-DT-03 — a deleted type of the workspace still names the order.
    Rules: _derive_default_title R1."""
    wtd = mk_type(db, s, "Overhaul", **GONE_FT)
    result = WOM._derive_default_title(db, s.W1.id, work_order_type_id=wtd.id, factory_id=s.F1.id,
                                       machine_id=s.M1.id, project_component_id=None)
    # Then 1
    assert result == "Overhaul — Lathe 3"


# [claude] WOM-DT-04
def test_wom_dt_04__foreign_type_work_order(db, s):
    """WOM-DT-04 — a type of W0 or W2 or an unknown type gives "Work order".
    Rules: _derive_default_title R1."""
    result = [WOM._derive_default_title(db, s.W1.id, work_order_type_id=t, factory_id=s.F1.id, machine_id=s.M1.id,
                                        project_component_id=None) for t in [s.WT0.id, s.WT9.id, MISSING]]
    # Then 1
    assert result == ["Work order — Lathe 3", "Work order — Lathe 3", "Work order — Lathe 3"]


# [claude] WOM-DT-05
def test_wom_dt_05__foreign_machine_hash(db, s):
    """WOM-DT-05 — a machine of another workspace shows as Machine #id; a deleted one of W1 by name.
    Rules: _derive_default_title R2."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    result = [WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT1.id, factory_id=s.F1.id, machine_id=m,
                                        project_component_id=None) for m in [s.M0.id, s.M9.id, md.id]]
    # Then 1
    assert result == [f"Service — Machine #{s.M0.id}", f"Service — Machine #{s.M9.id}", "Service — Old press"]


# [claude] WOM-DT-06
def test_wom_dt_06__machine_wins_over_component(db, s):
    """WOM-DT-06 — a machine wins over a component.
    Rules: _derive_default_title R2."""
    result = WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT1.id, factory_id=s.F1.id,
                                       machine_id=s.M2.id, project_component_id=s.PC1.id)
    # Then 1
    assert result == "Service — Lathe 4"


# [claude] WOM-DT-07
def test_wom_dt_07__component_names_target(db, s):
    """WOM-DT-07 — a component names the target; one of W2 shows as Component #id (revisit after launch).
    Rules: _derive_default_title R3."""
    result = [WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT1.id, factory_id=s.F1.id, machine_id=None,
                                        project_component_id=c) for c in [s.PC1.id, s.PC9.id]]
    # Then 1
    assert result == ["Service — Panel A", f"Service — Component #{s.PC9.id}"]


# [claude] WOM-DT-08
def test_wom_dt_08__factory_names_order(db, s):
    """WOM-DT-08 — without a target the factory names the order; an unknown or foreign factory leaves the type alone.
    Rules: _derive_default_title R5."""
    result = [WOM._derive_default_title(db, s.W1.id, work_order_type_id=s.WT1.id, factory_id=f, machine_id=None,
                                        project_component_id=None) for f in [s.F1.id, s.F0.id, s.F9.id, MISSING]]
    # Then 1
    assert result == ["Service — Plant One", "Service", "Service", "Service"]


# =========================================================================== #
# create_work_order
# =========================================================================== #


def _wo_count(db, ws):
    return db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.workspace_id == ws.id)).scalar_one()


# [claude] WOM-C-01
def test_wom_c_01__smallest_request_numbered_draft(db, s):
    """WOM-C-01 — the smallest request makes a numbered draft.
    Rules: create_work_order R4, R5."""
    result = CREATE(db, s, CR(s))
    # Then 1
    assert isinstance(result, WorkOrder)
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.workspace_id == s.W1.id
    assert row.work_order_number == s.NEW
    assert row.created_by == s.U1.id
    assert row.status == "DRAFT"
    # Then 3
    assert row.title == "Service — Lathe 3"
    assert row.priority == WorkOrderPriorityEnum.MEDIUM
    assert row.uses_inventory is True
    assert row.factory_id == s.F1.id
    assert row.machine_id == s.M1.id
    # Then 4
    assert row.description is None
    assert row.cost is None
    assert row.account_id is None
    assert row.planned_date is None
    assert row.end_date is None
    assert row.assigned_to is None
    assert row.project_component_id is None
    assert row.work_order_template_id is None
    # Then 5
    assert _wo_count(db, s.W1) == 1


# [claude] WOM-C-02
def test_wom_c_02__created_and_auto_approved(db, s):
    """WOM-C-02 — created and auto-approved events; the creator stamps the approval.
    Rules: create_work_order R6, R7."""
    mk = mark(db)
    result = CREATE(db, s, CR(s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert ev(db, mk, result) == [("created", f"Work order {s.NEW} created"),
                                  ("auto_approved", "Ready to start — no approval required")]
    # Then 3
    assert evrow(db, mk, result, "created").metadata_json is None
    # Then 4
    row = reread(db, WorkOrder, result.id)
    assert row.approved_by == s.U1.id
    assert row.approved_at == NOW


# [claude] WOM-C-03
def test_wom_c_03__planned_date_scheduled_event(db, s):
    """WOM-C-03 — a planned date adds a scheduled event between the two.
    Rules: create_work_order R7."""
    mk = mark(db)
    result = CREATE(db, s, CR(s, planned_date=D(12)))
    # Then 1
    assert result.id is not None
    # Then 2
    assert ev(db, mk, result) == [("created", f"Work order {s.NEW} created"), ("scheduled", "Scheduled for 2026-03-12"),
                                  ("auto_approved", "Ready to start — no approval required")]
    # Then 3
    assert evrow(db, mk, result, "scheduled").metadata_json == {"planned_date": "2026-03-12"}


# [claude] WOM-C-04
def test_wom_c_04__other_fields_stored(db, s):
    """WOM-C-04 — every other field is stored as sent.
    Rules: create_work_order R3, R5."""
    result = CREATE(db, s, CR(s, description="Fix seal", priority=WorkOrderPriorityEnum.HIGH, planned_date=D(12),
                              end_date=D(14), uses_inventory=False, cost=Decimal("5000.00"), account_id=s.A1.id))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.description == "Fix seal"
    assert row.priority == WorkOrderPriorityEnum.HIGH
    assert row.planned_date == D(12)
    assert row.end_date == D(14)
    # Then 3
    assert row.uses_inventory is False
    assert row.cost == Decimal("5000.00")
    assert row.account_id == s.A1.id


# [claude] WOM-C-05
def test_wom_c_05__typed_title_trimmed(db, s):
    """WOM-C-05 — a typed title is trimmed and kept.
    Rules: create_work_order R4."""
    result = CREATE(db, s, CR(s, title="  Fix leaking seal  "))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrder, result.id).title == "Fix leaking seal"


# [claude] WOM-C-06
def test_wom_c_06__blank_title_derived(db, s):
    """WOM-C-06 — a blank title is derived from type and machine.
    Rules: create_work_order R4."""
    result = CREATE(db, s, CR(s, title="   ", work_order_type_id=s.WT2.id))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrder, result.id).title == "Repair — Lathe 3"


# [claude] WOM-C-07
def test_wom_c_07__no_target_factory_names(db, s):
    """WOM-C-07 — no title and no target: the factory names the order.
    Rules: create_work_order R4."""
    result = CREATE(db, s, CR(s, machine_id=None))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Service — Plant One"
    assert row.machine_id is None


# [claude] WOM-C-08
def test_wom_c_08__assigned_text_matched(db, s):
    """WOM-C-08 — assigned text is matched to members and put in the created event.
    Rules: create_work_order R6."""
    mk = mark(db)
    result = CREATE(db, s, CR(s, assigned_to="rahim uddin; Ghost"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrder, result.id).assigned_to == "rahim uddin; Ghost"
    # Then 3
    assert [a.user_id for a in rows_of(db, WorkOrderAssignee, work_order_id=result.id)] == [s.U2.id]
    # Then 4
    assert evrow(db, mk, result, "created").metadata_json == {"assigned_to": "rahim uddin; Ghost",
                                                              "assignee_user_ids": [s.U2.id]}


# [claude] WOM-C-09
def test_wom_c_09__empty_assigned_text(db, s):
    """WOM-C-09 — an empty assigned text gives no metadata and no assignee rows.
    Rules: create_work_order R6."""
    mk = mark(db)
    result = CREATE(db, s, CR(s, assigned_to=""))
    # Then 1
    assert result.id is not None
    # Then 2
    assert evrow(db, mk, result, "created").metadata_json is None
    # Then 3
    assert len(rows_of(db, WorkOrderAssignee, work_order_id=result.id)) == 0


# [claude] WOM-C-10
def test_wom_c_10__factory_of_w2_not_found(db, s):
    """WOM-C-10 — a factory of W2 is not found.
    Rules: create_work_order R1, Errors."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, factory_id=s.F9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-C-11
def test_wom_c_11__factory_of_w0_not_found(db, s):
    """WOM-C-11 — a factory of W0 is not found.
    Rules: create_work_order R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, factory_id=s.F0.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-12
def test_wom_c_12__unknown_factory(db, s):
    """WOM-C-12 — an unknown factory is not found.
    Rules: create_work_order R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, factory_id=MISSING))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-13
@xf(2920)
def test_wom_c_13__deleted_factory_not_found(db, s):
    """WOM-C-13 — a soft-deleted factory is not found.
    Rules: create_work_order R1a [BUG-2920]."""
    fd = _add(db, Factory(workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", **GONE_FT))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, factory_id=fd.id, machine_id=None))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-C-14
def test_wom_c_14__type_of_w2_not_found(db, s):
    """WOM-C-14 — a type of W2 is not found.
    Rules: create_work_order R2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, work_order_type_id=s.WT9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {s.WT9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-C-15
def test_wom_c_15__type_of_w0_not_found(db, s):
    """WOM-C-15 — a type of W0 is not found.
    Rules: create_work_order R2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, work_order_type_id=s.WT0.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {s.WT0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-16
def test_wom_c_16__factory_before_type(db, s):
    """WOM-C-16 — the factory is checked before the type.
    Rules: create_work_order R2 (order of checks)."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, factory_id=s.F9.id, work_order_type_id=s.WT9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"


# [claude] WOM-C-17
def test_wom_c_17__type_before_account(db, s):
    """WOM-C-17 — the type is checked before the account.
    Rules: create_work_order R2 (order of checks)."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, work_order_type_id=s.WT9.id, account_id=s.A9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {s.WT9.id} not found"


# [claude] WOM-C-18
@xf(1228)
def test_wom_c_18__deleted_type_not_found(db, s):
    """WOM-C-18 — a soft-deleted type is not found.
    Rules: create_work_order R2 [BUG-1228]."""
    wtd = mk_type(db, s, "Overhaul", **GONE_FT)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, work_order_type_id=wtd.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {wtd.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-19
def test_wom_c_19__account_of_w2_not_found(db, s):
    """WOM-C-19 — an account of W2 is not found.
    Rules: create_work_order R3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, account_id=s.A9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-C-20
def test_wom_c_20__account_of_w0_not_found(db, s):
    """WOM-C-20 — an account of W0 is not found.
    Rules: create_work_order R3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, account_id=s.A0.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {s.A0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-21
@xf(2920)
def test_wom_c_21__deleted_account_not_found(db, s):
    """WOM-C-21 — a soft-deleted account is not found.
    Rules: create_work_order R3 [BUG-2920]."""
    ad = _add(db, Account(workspace_id=s.W1.id, name="Gone Ltd", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, account_id=ad.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {ad.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-22
@xf(2921)
def test_wom_c_22__machine_of_other_factory(db, s):
    """WOM-C-22 — a machine of another factory than the order's is refused.
    Rules: create_work_order R1b [BUG-2921]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=s.M3.id, factory_id=s.F1.id))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine Pump belongs to another factory"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-C-23
def test_wom_c_23__type_before_machine_factory(db, s):
    """WOM-C-23 — a bad type is reported before the machine's factory.
    Rules: create_work_order R1b (after R2)."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=s.M3.id, factory_id=s.F1.id, work_order_type_id=s.WT9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {s.WT9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-24
def test_wom_c_24__account_before_machine_factory(db, s):
    """WOM-C-24 — a bad account is reported before the machine's factory.
    Rules: create_work_order R1b (after R3)."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=s.M3.id, factory_id=s.F1.id, account_id=s.A9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-25
def test_wom_c_25__machine_and_component_stored(db, s):
    """WOM-C-25 — machine and component may both be stored (revisit after launch).
    Rules: create_work_order R8."""
    result = CREATE(db, s, CR(s, project_component_id=s.PC1.id))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.machine_id == s.M1.id
    assert row.project_component_id == s.PC1.id
    assert row.title == "Service — Lathe 3"


# [claude] WOM-C-26
def test_wom_c_26__component_alone_names(db, s):
    """WOM-C-26 — a component alone names the order (revisit after launch).
    Rules: create_work_order R4, R8."""
    result = CREATE(db, s, CR(s, machine_id=None, project_component_id=s.PC1.id))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Service — Panel A"
    assert row.machine_id is None


# [claude] WOM-C-27
@xf(1016)
def test_wom_c_27__machine_of_w2_not_found(db, s):
    """WOM-C-27 — a machine of W2 is not found.
    Rules: create_work_order R9 [BUG-1016]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=s.M9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-28
@xf(1016)
def test_wom_c_28__machine_of_w0_not_found(db, s):
    """WOM-C-28 — a machine of W0 is not found.
    Rules: create_work_order R9 [BUG-1016]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=s.M0.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-29
@xf(1016)
def test_wom_c_29__component_of_w2_not_found(db, s):
    """WOM-C-29 — a component of W2 is not found.
    Rules: create_work_order R9 [BUG-1016]."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=None, project_component_id=s.PC9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {s.PC9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-30
@xf(2920)
def test_wom_c_30__deleted_machine_not_found(db, s):
    """WOM-C-30 — a soft-deleted machine of W1 is not found.
    Rules: create_work_order R9 [BUG-2920]."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CREATE(db, s, CR(s, machine_id=md.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-C-31
@xf(2926)
def test_wom_c_31__end_before_planned_refused(db, s):
    """WOM-C-31 — an end date before the planned date is refused by the create schema.
    Rules: create_work_order R3b [BUG-2926]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        CR(s, planned_date=date(2026, 5, 10), end_date=date(2026, 5, 1))
    # Then 2
    assert "End date cannot be before the planned date" in str(exc.value)
    # Then 3
    assert _wo_count(db, s.W1) == 0


# [claude] WOM-C-32
def test_wom_c_32__end_equal_planned_accepted(db, s):
    """WOM-C-32 — an end date equal to the planned date is accepted.
    Rules: create_work_order R3b."""
    result = CREATE(db, s, CR(s, planned_date=date(2026, 5, 10), end_date=date(2026, 5, 10)))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.planned_date == date(2026, 5, 10)
    assert row.end_date == date(2026, 5, 10)


# [claude] WOM-C-33
def test_wom_c_33__flushes_never_commits(db, s):
    """WOM-C-33 — create flushes and never commits.
    Rules: create_work_order Side effects."""
    data = CR(s)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = CREATE(db, s, data)
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert _wo_count(db, s.W1) == 0


# [claude] WOM-C-34
@xf(2912)
def test_wom_c_34__negative_cost_schema(s):
    """WOM-C-34 — a negative cost is refused by the schema.
    Rules: create_work_order R3a [BUG-2912]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        CR(s, cost=Decimal("-5"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-C-35
def test_wom_c_35__cost_zero_and_none(s):
    """WOM-C-35 — cost 0 and no cost are accepted by the schema.
    Rules: create_work_order R3a."""
    result = (CR(s, cost=Decimal("0")), CR(s, cost=None))
    # Then 1
    assert result[0].cost == Decimal("0")
    # Then 2
    assert result[1].cost is None


# [claude] WOM-C-36
@xf(2913)
def test_wom_c_36__cost_three_decimals(s):
    """WOM-C-36 — a cost with 3 decimals is refused by the schema.
    Rules: create_work_order R3a [BUG-2913]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        CR(s, cost=Decimal("99.999"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-C-37
@xf(2913)
def test_wom_c_37__cost_fourteen_digits(s):
    """WOM-C-37 — a cost with 14 integer digits is refused by the schema.
    Rules: create_work_order R3a [BUG-2913]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        CR(s, cost=Decimal("10000000000000"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-C-38
def test_wom_c_38__largest_cost_accepted(s):
    """WOM-C-38 — the largest cost that fits is accepted by the schema.
    Rules: create_work_order R3a."""
    result = CR(s, cost=Decimal("9999999999999.99"))
    # Then 1
    assert result.cost == Decimal("9999999999999.99")


# =========================================================================== #
# create_work_order_from_template
# =========================================================================== #


# [claude] WOM-CT-01
def test_wom_ct_01__template_fields_machine_factory(db, s):
    """WOM-CT-01 — the order takes the template's fields and the machine's factory.
    Rules: create_work_order_from_template R3, R4, R6."""
    t = mk_template(db, s, priority=WorkOrderPriorityEnum.HIGH, cost=Decimal("300.00"), account_id=s.A1.id,
                    description="Change oil")
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.work_order_type_id == s.WT1.id
    assert row.priority == WorkOrderPriorityEnum.HIGH
    assert row.cost == Decimal("300.00")
    assert row.account_id == s.A1.id
    # Then 3
    assert row.factory_id == s.F1.id
    assert row.machine_id == s.M1.id
    assert row.title == "Service — Lathe 3"
    assert row.description == "Change oil"
    # Then 4
    assert row.work_order_template_id == t.id
    assert row.status == "DRAFT"
    assert row.uses_inventory is False
    assert row.planned_date is None
    assert row.assigned_to is None
    # Then 5
    assert len(rows_of(db, WorkOrderItem, work_order_id=result.id)) == 0


# [claude] WOM-CT-02
def test_wom_ct_02__last_event_names_template(db, s):
    """WOM-CT-02 — the last event says which template made the order.
    Rules: create_work_order_from_template R10."""
    t = mk_template(db, s)
    mk = mark(db)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert ev(db, mk, result) == [("created", f"Work order {s.NEW} created"),
                                  ("auto_approved", "Ready to start — no approval required"),
                                  ("created_from_template", 'Generated from template "Oil change"')]
    # Then 3
    assert evrow(db, mk, result, "created_from_template").metadata_json == {"work_order_template_id": t.id}


# [claude] WOM-CT-03
def test_wom_ct_03__machine_in_other_factory(db, s):
    """WOM-CT-03 — a machine in another factory files the order under that factory.
    Rules: create_work_order_from_template R3."""
    t = mk_template(db, s)
    result = FROM(db, s, t, machine_id=s.M3.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.factory_id == s.F2.id
    assert row.machine_id == s.M3.id
    assert row.title == "Service — Pump"


# [claude] WOM-CT-04
def test_wom_ct_04__non_empty_overrides_win(db, s):
    """WOM-CT-04 — non-empty overrides win.
    Rules: create_work_order_from_template R3."""
    t = mk_template(db, s, description="Change oil", assigned_to="Rahim Uddin")
    result = FROM(db, s, t, title="Night shift oil", description="Use 5W-30", assigned_to="Sara Khan", planned_date=D(12))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Night shift oil"
    assert row.description == "Use 5W-30"
    assert row.assigned_to == "Sara Khan"
    assert row.planned_date == D(12)


# [claude] WOM-CT-05
def test_wom_ct_05__empty_overrides_fall_back(db, s):
    """WOM-CT-05 — empty-string overrides fall back to the template.
    Rules: create_work_order_from_template R3."""
    t = mk_template(db, s, description="Change oil", assigned_to="Rahim Uddin")
    result = FROM(db, s, t, title="", description="", assigned_to="")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Service — Lathe 3"
    assert row.description == "Change oil"
    assert row.assigned_to == "Rahim Uddin"


# [claude] WOM-CT-06
def test_wom_ct_06__template_of_w2_not_found(db, s):
    """WOM-CT-06 — a template of W2 is not found.
    Rules: create_work_order_from_template R1."""
    t9 = mk_template(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT9.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t9)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order template with ID {t9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CT-07
def test_wom_ct_07__template_of_w0_not_found(db, s):
    """WOM-CT-07 — a template of W0 is not found.
    Rules: create_work_order_from_template R1."""
    t0x = mk_template(db, s, workspace_id=s.W0.id, work_order_type_id=s.WT0.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t0x)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order template with ID {t0x.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CT-08
def test_wom_ct_08__inactive_template_refused(db, s):
    """WOM-CT-08 — an inactive template is refused.
    Rules: create_work_order_from_template R1."""
    t = mk_template(db, s, is_active=False)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Template is inactive"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-CT-09
def test_wom_ct_09__machine_of_w2_not_found(db, s):
    """WOM-CT-09 — a machine of W2 is not found.
    Rules: create_work_order_from_template R2."""
    t = mk_template(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t, machine_id=s.M9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CT-10
def test_wom_ct_10__machine_of_w0_not_found(db, s):
    """WOM-CT-10 — a machine of W0 is not found.
    Rules: create_work_order_from_template R2."""
    t = mk_template(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t, machine_id=s.M0.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CT-11
@xf(2920)
def test_wom_ct_11__deleted_machine_not_found(db, s):
    """WOM-CT-11 — a soft-deleted machine is not found.
    Rules: create_work_order_from_template R2 [BUG-2920]."""
    t = mk_template(db, s)
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t, machine_id=md.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CT-12
def test_wom_ct_12__template_lines_copied(db, s):
    """WOM-CT-12 — template lines become order lines in template order.
    Rules: create_work_order_from_template R5."""
    t = mk_template(db, s, uses_inventory=True)
    mk_tline(db, s, t, s.I2, "2", notes="Check")
    mk_tline(db, s, t, s.I1, "3", action_type="REPLACE", replaced_item_id=s.I3.id)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    lines = rows_of(db, WorkOrderItem, work_order_id=result.id)
    assert [(ln.item_id, ln.quantity, ln.action_type) for ln in lines] == [
        (s.I2.id, Decimal("2.00"), "CONSUME"), (s.I1.id, Decimal("3.00"), "REPLACE")]
    # Then 3
    assert lines[0].notes == "Check"
    assert lines[0].uses_inventory is True
    assert lines[0].source_location_type == "storage"
    assert lines[0].source_location_id == s.F1.id
    assert lines[0].replaced_item_id is None
    # Then 4
    assert lines[1].replaced_item_id == s.I3.id
    assert lines[1].uses_inventory is True
    assert lines[1].source_location_id == s.F1.id


# [claude] WOM-CT-13
def test_wom_ct_13__replace_without_replaced_item(db, s):
    """WOM-CT-13 — a Replace template line with no replaced item fails the call.
    Rules: create_work_order_from_template R5."""
    t = mk_template(db, s, uses_inventory=True)
    mk_tline(db, s, t, s.I1, "1", action_type="REPLACE")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Select the item being replaced"


# [claude] WOM-CT-14
def test_wom_ct_14__same_item_twice_409(db, s):
    """WOM-CT-14 — the same item twice on a template fails the call with 409.
    Rules: create_work_order_from_template R5."""
    t = mk_template(db, s, uses_inventory=True)
    mk_tline(db, s, t, s.I1, "1")
    mk_tline(db, s, t, s.I1, "2")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FROM(db, s, t)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Bolt is already on this order"


# [claude] WOM-CT-15
def test_wom_ct_15__no_inventory_no_lines(db, s):
    """WOM-CT-15 — a template that does not use inventory copies no lines.
    Rules: create_work_order_from_template R6."""
    t = mk_template(db, s)
    mk_tline(db, s, t, s.I1, "1")
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rows_of(db, WorkOrderItem, work_order_id=result.id)) == 0


# [claude] WOM-CT-16
def test_wom_ct_16__approvers_copied(db, s):
    """WOM-CT-16 — approvers of a template that requires approval are copied; the order is no longer approved.
    Rules: create_work_order_from_template R7."""
    t = mk_template(db, s, requires_approval=True)
    mk_tapprover(db, s, t, s.U2)
    mk_tapprover(db, s, t, s.U3)
    mk = mark(db)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [(a.user_id, a.assigned_by, a.approved) for a in rows_of(db, WorkOrderApprover, work_order_id=result.id)] == [
        (s.U2.id, s.U1.id, False), (s.U3.id, s.U1.id, False)]
    # Then 3
    row = reread(db, WorkOrder, result.id)
    assert row.approved_by is None
    assert row.approved_at is None
    # Then 4
    assert [t_ for t_, _ in ev(db, mk, result)] == ["created", "auto_approved", "approver_added", "approval_revoked",
                                                   "approver_added", "created_from_template"]


# [claude] WOM-CT-17
def test_wom_ct_17__inactive_member_skipped(db, s):
    """WOM-CT-17 — an approver who is not an active member is skipped.
    Rules: create_work_order_from_template R7."""
    t = mk_template(db, s, requires_approval=True)
    mk_tapprover(db, s, t, s.U4)
    mk_tapprover(db, s, t, s.U2)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [a.user_id for a in rows_of(db, WorkOrderApprover, work_order_id=result.id)] == [s.U2.id]


# [claude] WOM-CT-18
@xf(2922)
def test_wom_ct_18__all_left_not_approved(db, s):
    """WOM-CT-18 — template approvers who all left: the order is not approved.
    Rules: create_work_order_from_template R9 [BUG-2922]."""
    t = mk_template(db, s, requires_approval=True)
    mk_tapprover(db, s, t, s.U4)
    mk = mark(db)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.required_approvals == 1
    # Then 3
    assert row.approved_at is None
    assert row.approved_by is None
    # Then 4
    assert ("approvals_needed", "Template approvers are no longer members — add an approver") in ev(db, mk, result)
    # Then 5
    assert WOM.approval_summary(db, result) == (0, 1, False)


# [claude] WOM-CT-19
def test_wom_ct_19__all_left_draft_made(db, s):
    """WOM-CT-19 — template approvers who all left: no approver row, the draft is still made.
    Rules: create_work_order_from_template R7, R9."""
    t = mk_template(db, s, requires_approval=True)
    mk_tapprover(db, s, t, s.U4)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rows_of(db, WorkOrderApprover, work_order_id=result.id)) == 0
    # Then 3
    row = reread(db, WorkOrder, result.id)
    assert row.status == "DRAFT"
    assert row.work_order_template_id == t.id


# [claude] WOM-CT-20
def test_wom_ct_20__approvers_not_copied_without_flag(db, s):
    """WOM-CT-20 — without "requires approval" template approvers are not copied.
    Rules: create_work_order_from_template R7."""
    t = mk_template(db, s)
    mk_tapprover(db, s, t, s.U2)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rows_of(db, WorkOrderApprover, work_order_id=result.id)) == 0
    # Then 3
    row = reread(db, WorkOrder, result.id)
    assert row.approved_by == s.U1.id
    assert row.approved_at == NOW


# [claude] WOM-CT-22
@xf(1206)
def test_wom_ct_22__duplicate_template_approver_409(db, s):
    """WOM-CT-22 — a template approver listed twice is a conflict that is not swallowed.
    Rules: create_work_order_from_template R8 [BUG-1206]."""
    t = mk_template(db, s, requires_approval=True)
    dup = [SimpleNamespace(user_id=s.U2.id, approver_slot=None), SimpleNamespace(user_id=s.U2.id, approver_slot=None)]
    # Then 1
    with patch("app.managers.work_order_manager.work_order_template_manager.get_approvers", return_value=dup),             pytest.raises(HTTPException) as exc:
        FROM(db, s, t)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"


# [claude] WOM-CT-23
def test_wom_ct_23__empty_type_name_maintenance(db, s):
    """WOM-CT-23 — a template whose type has an empty name titles the order "Maintenance — <machine>".
    Rules: create_work_order_from_template R3, R3a."""
    te = mk_type(db, s, "")
    t = mk_template(db, s, work_order_type_id=te.id)
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Maintenance — Lathe 3"
    assert row.work_order_type_id == te.id


# [claude] WOM-CT-21
def test_wom_ct_21__flushes_never_commits(db, s):
    """WOM-CT-21 — create from template flushes and never commits.
    Rules: create_work_order_from_template Side effects."""
    t = mk_template(db, s)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = FROM(db, s, t)
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert _wo_count(db, s.W1) == 0


# [claude] WOM-CT-24
def test_wom_ct_24__template_slot_copied(db, s):
    """WOM-CT-24 — a template approver's slot is copied to the order.
    Rules: create_work_order_from_template R7; add_approver R5."""
    t = mk_template(db, s, requires_approval=True)
    mk_tapprover(db, s, t, s.U2, approver_slot="QA")
    result = FROM(db, s, t)
    # Then 1
    assert result.id is not None
    # Then 2
    assert [(a.user_id, a.approver_slot, a.assigned_by) for a in rows_of(db, WorkOrderApprover, work_order_id=result.id)] == [
        (s.U2.id, "QA", s.U1.id)]


# =========================================================================== #
# update_work_order
# =========================================================================== #


def _wou(**k):
    from app.schemas.work_order import WorkOrderUpdate
    return WorkOrderUpdate(**k)


# [claude] WOM-U-01
def test_wom_u_01__description_change(db, s):
    """WOM-U-01 — a description change is written, logged and stamped.
    Rules: update_work_order R10, R13, R16, R19."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, description="New desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert result._approvals_reset is False
    # Then 3
    row = reread(db, WorkOrder, o.id)
    assert row.description == "New desc"
    assert row.updated_by == s.U2.id
    assert row.title == "Service — Lathe 3"
    # Then 4
    assert ev(db, mk, o) == [("updated", "Order details updated")]
    # Then 5
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]}


# [claude] WOM-U-02
def test_wom_u_02__order_of_w2_not_found(db, s):
    """WOM-U-02 — an order of W2 is not found.
    Rules: update_work_order R1."""
    o9 = mk_order(db, s, "9", workspace_id=s.W2.id, work_order_type_id=s.WT9.id, factory_id=s.F9.id, machine_id=s.M9.id)
    before = snap(db, o9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o9, description="New desc")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, o9) == before


# [claude] WOM-U-03
def test_wom_u_03__order_of_w0_not_found(db, s):
    """WOM-U-03 — an order of W0 is not found.
    Rules: update_work_order R1."""
    o0 = mk_order(db, s, "0", workspace_id=s.W0.id, work_order_type_id=s.WT0.id, factory_id=s.F0.id, machine_id=s.M0.id)
    before = snap(db, o0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o0, description="New desc")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o0.id} not found"
    # Then 4
    assert snap(db, o0) == before


# [claude] WOM-U-04
def test_wom_u_04__deleted_order_refused(db, s):
    """WOM-U-04 — a soft-deleted order is refused.
    Rules: update_work_order R2."""
    o = mk_order(db, s, "1", **STAMPED(s), **GONE(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, description="New desc")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted work order"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-05
def test_wom_u_05__title_alone_dropped(db, s):
    """WOM-U-05 — a title alone is dropped and nothing is written.
    Rules: update_work_order R3, R5."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before_o = snap(db, o)
    before = counts(db)
    result = UP(db, s, o, title="Renamed")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert result._approvals_reset is False
    # Then 3
    assert not db.dirty
    assert not db.new
    # Then 4
    assert snap(db, o) == before_o
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-06
def test_wom_u_06__title_with_description_dropped(db, s):
    """WOM-U-06 — a title sent with a description is still dropped.
    Rules: update_work_order R3."""
    o = mk_order(db, s, "1", **STAMPED(s), title="Fix seal")
    result = UP(db, s, o, title="Renamed", description="New desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.title == "Fix seal"
    assert row.description == "New desc"


# [claude] WOM-U-07
def test_wom_u_07__null_description_nothing_to_do(db, s):
    """WOM-U-07 — a description sent as null is dropped: nothing to do.
    Rules: update_work_order R4, R5."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before_o = snap(db, o)
    before = counts(db)
    result = UP(db, s, o, description=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert result._approvals_reset is False
    # Then 3
    assert snap(db, o) == before_o
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-08
def test_wom_u_08__nothing_to_do_completed(db, s):
    """WOM-U-08 — nothing to do on a completed order is not an error.
    Rules: update_work_order R5."""
    o = mk_order(db, s, "1", **STAMPED(s), **COMPLETED(s))
    before_o = snap(db, o)
    before = counts(db)
    result = UP(db, s, o, title="Renamed")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert snap(db, o) == before_o
    # Then 3
    assert counts(db) == before


# [claude] WOM-U-09
def test_wom_u_09__completed_cannot_edit(db, s):
    """WOM-U-09 — a completed order cannot be edited.
    Rules: update_work_order R6."""
    o = mk_order(db, s, "1", **STAMPED(s), **COMPLETED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, description="New desc")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed and cannot be edited"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-10
def test_wom_u_10__voided_cannot_edit(db, s):
    """WOM-U-10 — a voided order cannot be edited.
    Rules: update_work_order R6."""
    o = mk_order(db, s, "1", **STAMPED(s), **VOIDED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, planned_date=D(20))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided and cannot be edited"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-11
def test_wom_u_11__in_progress_planned_date(db, s):
    """WOM-U-11 — in progress, the planned date can change and is logged.
    Rules: update_work_order R7, R13."""
    o = mk_order(db, s, "1", **STARTED(s))
    mk = mark(db)
    result = UP(db, s, o, planned_date=D(14))
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.planned_date == D(14)
    assert row.status == "IN_PROGRESS"
    assert row.updated_by == s.U2.id
    # Then 3
    assert ev(db, mk, o) == [("updated", "Order details updated"), ("schedule_updated", "Planned date changed")]


# [claude] WOM-U-12
def test_wom_u_12__in_progress_free_fields(db, s):
    """WOM-U-12 — in progress, assigned text, end date and completion notes can change.
    Rules: update_work_order R7, R21."""
    o = mk_order(db, s, "1", **STARTED(s))
    result = UP(db, s, o, assigned_to="Sara Khan", end_date=D(20), completion_notes="Half done")
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.assigned_to == "Sara Khan"
    assert row.end_date == D(20)
    assert row.completion_notes == "Half done"


# [claude] WOM-U-13
@xf(2924)
def test_wom_u_13__in_progress_message_names_all(db, s):
    """WOM-U-13 — the in-progress refusal names every locked field.
    Rules: update_work_order R8 [BUG-2924]."""
    o = mk_order(db, s, "1", **STARTED(s))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, description="New desc")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is in progress — type, description, priority, target, cost and account are locked"


# [claude] WOM-U-14
def test_wom_u_14__in_progress_description_refused(db, s):
    """WOM-U-14 — in progress, a description edit is refused and nothing is written.
    Rules: update_work_order R7, R8."""
    o = mk_order(db, s, "1", **STARTED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, description="New desc")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail.startswith("Work order is in progress — ")
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-15 … WOM-U-21
# [claude] WOM-CI-07, WOM-CI-08
@pytest.mark.parametrize("field", [
    pytest.param("description", id="WOM-U-15"),
    pytest.param("priority", id="WOM-U-16"),
    pytest.param("cost", id="WOM-U-17"),
    pytest.param("account_id", id="WOM-U-18"),
    pytest.param("machine_id", id="WOM-U-19"),
    pytest.param("work_order_type_id", id="WOM-U-20"),
    pytest.param("project_component_id", id="WOM-U-21"),
])
def test_wom_u_15_21__in_progress_field_locked(db, s, field):
    """WOM-U-15 … WOM-U-21 — in progress, each structural field is locked (U-15: the current description; U-19: machine cleared).
    Rules: update_work_order R7, R8."""
    value = {
        "description": "Old desc", "priority": WorkOrderPriorityEnum.HIGH, "cost": Decimal("200.00"),
        "account_id": s.A1.id, "machine_id": None, "work_order_type_id": s.WT2.id, "project_component_id": s.PC1.id,
    }[field]
    o = mk_order(db, s, "1", **STARTED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, **{field: value})
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail.startswith("Work order is in progress — ")
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-22
@xf(2931)
def test_wom_u_22__in_progress_required_approvals_frozen(db, s):
    """WOM-U-22 — in progress, the required approvals are frozen.
    Rules: update_work_order R7a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, required_approvals=2)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work has started — approvals can no longer change"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-23
@xf(2931)
def test_wom_u_23__in_progress_required_approvals_null(db, s):
    """WOM-U-23 — in progress, required approvals sent as null are refused too.
    Rules: update_work_order R7a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s), required_approvals=1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, required_approvals=None)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work has started — approvals can no longer change"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-24
def test_wom_u_24__account_of_w2_not_found(db, s):
    """WOM-U-24 — an account of W2 is not found.
    Rules: update_work_order R9."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, account_id=s.A9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Selected account not found"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-25 … WOM-U-27
@pytest.mark.parametrize("which", [
    pytest.param("A0", id="WOM-U-25"),
    pytest.param("WT9", id="WOM-U-26"),
    pytest.param("WT0", id="WOM-U-27"),
])
def test_wom_u_25_27__foreign_reference_not_found(db, s, which):
    """WOM-U-25 … WOM-U-27 — an account of W0, a type of W2, a type of W0 is not found.
    Rules: update_work_order R9."""
    o = mk_order(db, s, "1", **STAMPED(s))
    k, detail = {
        "A0": ({"account_id": s.A0.id}, "Selected account not found"),
        "WT9": ({"work_order_type_id": s.WT9.id}, "Selected work order type not found"),
        "WT0": ({"work_order_type_id": s.WT0.id}, "Selected work order type not found"),
    }[which]
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, **k)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-28
@xf(1228)
def test_wom_u_28__deleted_type_not_found(db, s):
    """WOM-U-28 — a soft-deleted type is not found.
    Rules: update_work_order R9 [BUG-1228]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    wtd = mk_type(db, s, "Overhaul", **GONE_FT)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, work_order_type_id=wtd.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Selected work order type not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-29
@xf(2920)
def test_wom_u_29__deleted_account_not_found(db, s):
    """WOM-U-29 — a soft-deleted account is not found.
    Rules: update_work_order R11 [BUG-2920]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    ad = _add(db, Account(workspace_id=s.W1.id, name="Gone Ltd", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, account_id=ad.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Selected account not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-30
@xf(2912)
def test_wom_u_30__negative_cost_schema():
    """WOM-U-30 — a negative cost is refused by WorkOrderUpdate.
    Rules: update_work_order R9a [BUG-2912]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _wou(cost=Decimal("-1"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-U-31
@xf(2912)
def test_wom_u_31__negative_required_approvals_schema():
    """WOM-U-31 — negative required approvals are refused by WorkOrderUpdate.
    Rules: update_work_order R9a [BUG-2912]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _wou(required_approvals=-1)
    # Then 2
    assert "required_approvals" in str(exc.value)


# [claude] WOM-U-32
@xf(2913)
def test_wom_u_32__cost_three_decimals_schema():
    """WOM-U-32 — a cost with 3 decimals is refused by WorkOrderUpdate.
    Rules: update_work_order R9a [BUG-2913]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _wou(cost=Decimal("0.001"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-U-33
def test_wom_u_33__schema_edges_accepted():
    """WOM-U-33 — zero and null approvals and a 2-decimal cost are accepted by WorkOrderUpdate.
    Rules: update_work_order R9a."""
    result = (_wou(required_approvals=0), _wou(required_approvals=None), _wou(cost=Decimal("0.01")))
    # Then 1
    assert result[0].required_approvals == 0
    # Then 2
    assert result[1].required_approvals is None
    # Then 3
    assert result[2].cost == Decimal("0.01")


# [claude] WOM-U-34
@xf(2926)
def test_wom_u_34__end_before_stored_planned(db, s):
    """WOM-U-34 — an end date before the stored planned date is refused.
    Rules: update_work_order R9b [BUG-2926]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, end_date=D(11))
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "End date cannot be before the planned date"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-35
@xf(2926)
def test_wom_u_35__planned_after_stored_end(db, s):
    """WOM-U-35 — a planned date after the stored end date is refused (merged values).
    Rules: update_work_order R9b [BUG-2926]."""
    o = mk_order(db, s, "1", **STAMPED(s), end_date=D(14))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, planned_date=D(20))
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "End date cannot be before the planned date"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-36
def test_wom_u_36__end_equal_planned_accepted(db, s):
    """WOM-U-36 — an end date equal to the planned date is accepted.
    Rules: update_work_order R9b."""
    o = mk_order(db, s, "1", **STAMPED(s))
    result = UP(db, s, o, end_date=D(12))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).end_date == D(12)


# [claude] WOM-U-37
def test_wom_u_37__two_changes_logged_order(db, s):
    """WOM-U-37 — two changes are logged in the logged-field order.
    Rules: update_work_order R10, R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, priority=WorkOrderPriorityEnum.HIGH, description="New desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [c["field"] for c in evrow(db, mk, o, "updated").metadata_json["changes"]] == ["description", "priority"]


# [claude] WOM-U-38
def test_wom_u_38__details_change_clears_approvals(db, s):
    """WOM-U-38 — a details change on an approved draft clears the approvals.
    Rules: update_work_order R12, R18, R19; reset_approvals R1, R2."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = UP(db, s, o, description="New desc")
    # Then 1
    assert result._approvals_reset is True
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by is None
    assert row.approved_at is None
    # Then 4
    assert ev(db, mk, o) == [("approvals_reset", "Order details edited (1 approval(s) cleared)"),
                             ("updated", "Order details updated"),
                             ("approval_revoked", "No longer meets approval requirements")]


# [claude] WOM-U-39
@xf(2915)
def test_wom_u_39__same_description_resets_nothing(db, s):
    """WOM-U-39 — sending the current description on an approved draft resets nothing.
    Rules: update_work_order R12, R20 [BUG-2915]."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = UP(db, s, o, description="Old desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert result._approvals_reset is False
    # Then 3
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is True
    assert ra.approved_at == T0
    # Then 4
    assert ev(db, mk, o) == []
    # Then 5
    assert reread(db, WorkOrder, o.id).updated_by is None


# [claude] WOM-U-40
def test_wom_u_40__same_description_no_event(db, s):
    """WOM-U-40 — sending the current description on a draft logs no change.
    Rules: update_work_order R13 (no change, no event)."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, description="Old desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).description == "Old desc"
    # Then 3
    assert ev(db, mk, o) == []


# [claude] WOM-U-41
def test_wom_u_41__schedule_change_keeps_approvals(db, s):
    """WOM-U-41 — a schedule change on an approved draft keeps the approvals.
    Rules: update_work_order R12 (details only)."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    result = UP(db, s, o, planned_date=D(15))
    # Then 1
    assert result._approvals_reset is False
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is True
    assert ra.approved_at == T0
    # Then 3
    row = reread(db, WorkOrder, o.id)
    assert row.planned_date == D(15)
    assert row.approved_at == T0


_INV_LOCK = "This work order has an invoice. Delete the draft invoice first to change the cost or account."


# [claude] WOM-U-42
@xf(2929)
def test_wom_u_42__draft_invoice_cost_refused(db, s):
    """WOM-U-42 — with a draft invoice, a new cost is refused.
    Rules: update_work_order R12a [BUG-2929]."""
    inv = mk_invoice(db, s, "draft")
    o = mk_order(db, s, "1", **STAMPED(s), cost=Decimal("5000.00"), account_id=s.A1.id, invoice_id=inv.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, cost=Decimal("4200.00"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _INV_LOCK
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-43
@xf(2929)
def test_wom_u_43__confirmed_invoice_account_refused(db, s):
    """WOM-U-43 — with a confirmed invoice, a new account is refused.
    Rules: update_work_order R12a [BUG-2929]."""
    inv = mk_invoice(db, s, "confirmed")
    o = mk_order(db, s, "1", **STAMPED(s), account_id=s.A1.id, invoice_id=inv.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, account_id=s.A2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _INV_LOCK
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-44
@xf(2929)
def test_wom_u_44__draft_invoice_clear_account_refused(db, s):
    """WOM-U-44 — with a draft invoice, clearing the account is refused.
    Rules: update_work_order R12a [BUG-2929]."""
    inv = mk_invoice(db, s, "draft")
    o = mk_order(db, s, "1", **STAMPED(s), account_id=s.A1.id, invoice_id=inv.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, account_id=None)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _INV_LOCK
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-45
def test_wom_u_45__voided_invoice_cost_may_change(db, s):
    """WOM-U-45 — with a voided invoice, the cost may change.
    Rules: update_work_order R12a."""
    inv = mk_invoice(db, s, "voided")
    o = mk_order(db, s, "1", **STAMPED(s), cost=Decimal("5000.00"), account_id=s.A1.id, invoice_id=inv.id)
    result = UP(db, s, o, cost=Decimal("4200.00"))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).cost == Decimal("4200.00")


# [claude] WOM-U-46
def test_wom_u_46__draft_invoice_same_cost(db, s):
    """WOM-U-46 — with a draft invoice, resending the same cost is accepted.
    Rules: update_work_order R12a (no change)."""
    inv = mk_invoice(db, s, "draft")
    o = mk_order(db, s, "1", **STAMPED(s), cost=Decimal("5000.00"), account_id=s.A1.id, invoice_id=inv.id)
    mk = mark(db)
    result = UP(db, s, o, cost=Decimal("5000"))
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.cost == Decimal("5000.00")
    assert row.invoice_id == inv.id
    # Then 3
    assert ev(db, mk, o) == []


# [claude] WOM-U-47
def test_wom_u_47__cost_change_logged(db, s):
    """WOM-U-47 — without an invoice the cost change is logged as numbers.
    Rules: update_work_order R12a, R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, cost=Decimal("4200.50"))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).cost == Decimal("4200.50")
    # Then 3
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "cost", "label": "Cost", "from_value": "100", "to_value": "4200.5"}]}


# [claude] WOM-U-48
def test_wom_u_48__assigned_text_rematched(db, s):
    """WOM-U-48 — an assigned-text change re-matches workers and logs a workers event.
    Rules: update_work_order R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, assigned_to="Sara Khan")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("updated", "Order details updated"), ("workers_updated", "Workers updated")]
    # Then 3
    assert evrow(db, mk, o, "updated").metadata_json == {
        "changes": [{"field": "assigned_to", "label": "Assigned to", "from_value": "—", "to_value": "Sara Khan"}],
        "assignee_user_ids": [s.U3.id]}
    # Then 4
    assert evrow(db, mk, o, "workers_updated").metadata_json == {
        "from_value": "—", "to_value": "Sara Khan", "assigned_to": "Sara Khan", "assignee_user_ids": [s.U3.id]}
    # Then 5
    assert [a.user_id for a in rows_of(db, WorkOrderAssignee, work_order_id=o.id)] == [s.U3.id]


# [claude] WOM-U-49
def test_wom_u_49__planned_date_schedule_event(db, s):
    """WOM-U-49 — a planned-date change logs a schedule event.
    Rules: update_work_order R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, planned_date=D(15))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("updated", "Order details updated"), ("schedule_updated", "Planned date changed")]
    # Then 3
    assert evrow(db, mk, o, "schedule_updated").metadata_json == {
        "field": "planned_date", "from_value": "2026-03-12", "to_value": "2026-03-15",
        "changes": [{"field": "planned_date", "label": "Planned date", "from_value": "2026-03-12",
                     "to_value": "2026-03-15"}]}


# [claude] WOM-U-50
def test_wom_u_50__extra_events_follow_change_order(db, s):
    """WOM-U-50 — end date and workers change: the extra events follow the change order.
    Rules: update_work_order R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, assigned_to="Sara Khan", end_date=D(16))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("updated", "Order details updated"), ("schedule_updated", "End date changed"),
                             ("workers_updated", "Workers updated")]


_NEEDS_MACHINE = "Remove the Install / Replace / Borrow parts first — they need a machine"


# [claude] WOM-U-51
@xf(2930)
def test_wom_u_51__install_line_keeps_machine(db, s):
    """WOM-U-51 — an Install line keeps the machine from being removed.
    Rules: update_work_order R13a [BUG-2930]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, machine_id=None)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _NEEDS_MACHINE
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-U-52
@xf(2930)
def test_wom_u_52__replace_line_blocks_component(db, s):
    """WOM-U-52 — a Replace line keeps the order from moving to a component.
    Rules: update_work_order R13a [BUG-2930]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I1, "1", action_type="REPLACE", replaced_item_id=s.I2.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, project_component_id=s.PC1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _NEEDS_MACHINE
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-53
@xf(2930)
def test_wom_u_53__borrow_line_keeps_machine(db, s):
    """WOM-U-53 — a Borrow line keeps the machine from being removed.
    Rules: update_work_order R13a [BUG-2930]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I3, "1", action_type="BORROW")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, machine_id=None)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _NEEDS_MACHINE
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-54
def test_wom_u_54__install_line_other_machine_ok(db, s):
    """WOM-U-54 — with an Install line, moving to another machine is accepted.
    Rules: update_work_order R13a, R15."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL")
    result = UP(db, s, o, machine_id=s.M2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.machine_id == s.M2.id
    assert row.title == "Service — Lathe 4"


# [claude] WOM-U-55
def test_wom_u_55__consume_lines_machine_removable(db, s):
    """WOM-U-55 — with only Consume lines the machine may be removed.
    Rules: update_work_order R4, R13a, R15."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I1, "2")
    result = UP(db, s, o, machine_id=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.machine_id is None
    assert row.project_component_id is None
    assert row.title == "Service — Plant One"


# [claude] WOM-U-56
def test_wom_u_56__deleted_install_line_ignored(db, s):
    """WOM-U-56 — a deleted Install line does not keep the machine.
    Rules: update_work_order R13a (live lines only)."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **LINE_GONE(s))
    result = UP(db, s, o, machine_id=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).machine_id is None


# [claude] WOM-U-57
@xf(2921)
def test_wom_u_57__new_machine_moves_factory(db, s):
    """WOM-U-57 — a new machine moves the draft to that machine's factory.
    Rules: update_work_order R13b [BUG-2921]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, machine_id=s.M3.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).factory_id == s.F2.id
    # Then 3
    assert "Factory" in [c["label"] for c in evrow(db, mk, o, "updated").metadata_json["changes"]]


# [claude] WOM-U-58
def test_wom_u_58__new_machine_stored_logged(db, s):
    """WOM-U-58 — a new machine is stored, logged and renames the draft.
    Rules: update_work_order R10, R13, R15."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, machine_id=s.M3.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.machine_id == s.M3.id
    assert row.title == "Service — Pump"
    # Then 3
    assert {"field": "machine_id", "label": "Machine", "from_value": str(s.M1.id), "to_value": str(s.M3.id)} in \
        evrow(db, mk, o, "updated").metadata_json["changes"]


# [claude] WOM-U-59
@xf(1016)
def test_wom_u_59__machine_of_w2_not_found(db, s):
    """WOM-U-59 — a machine of W2 is not found.
    Rules: update_work_order R14 [BUG-1016]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, machine_id=s.M9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-60
@xf(1016)
def test_wom_u_60__machine_of_w0_not_found(db, s):
    """WOM-U-60 — a machine of W0 is not found.
    Rules: update_work_order R14 [BUG-1016]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, machine_id=s.M0.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-61
@xf(1016)
def test_wom_u_61__component_of_w2_not_found(db, s):
    """WOM-U-61 — a component of W2 is not found.
    Rules: update_work_order R14 [BUG-1016]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UP(db, s, o, project_component_id=s.PC9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Project component with ID {s.PC9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-U-62
def test_wom_u_62__type_change_renames(db, s):
    """WOM-U-62 — a type change renames the draft.
    Rules: update_work_order R15."""
    o = mk_order(db, s, "1", **STAMPED(s))
    result = UP(db, s, o, work_order_type_id=s.WT2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.work_order_type_id == s.WT2.id
    assert row.title == "Repair — Lathe 3"


# [claude] WOM-U-63
def test_wom_u_63__typed_title_replaced_on_machine_change(db, s):
    """WOM-U-63 — a typed title is replaced when the machine changes.
    Rules: update_work_order R15 (Q6)."""
    o = mk_order(db, s, "1", **STAMPED(s), title="Fix seal")
    result = UP(db, s, o, machine_id=s.M2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).title == "Service — Lathe 4"


# [claude] WOM-U-64
def test_wom_u_64__typed_title_survives_description(db, s):
    """WOM-U-64 — a typed title survives a description change.
    Rules: update_work_order R15."""
    o = mk_order(db, s, "1", **STAMPED(s), title="Fix seal")
    result = UP(db, s, o, description="New desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).title == "Fix seal"


# [claude] WOM-U-65
def test_wom_u_65__component_replaces_machine(db, s):
    """WOM-U-65 — a component replaces the machine (revisit after launch).
    Rules: update_work_order R4, R15."""
    o = mk_order(db, s, "1", **STAMPED(s))
    result = UP(db, s, o, project_component_id=s.PC1.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.machine_id is None
    assert row.project_component_id == s.PC1.id
    assert row.title == "Service — Panel A"


# [claude] WOM-U-66
def test_wom_u_66__null_account_clears(db, s):
    """WOM-U-66 — an account sent as null clears it.
    Rules: update_work_order R4."""
    o = mk_order(db, s, "1", **STAMPED(s), account_id=s.A1.id)
    result = UP(db, s, o, account_id=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).account_id is None


# [claude] WOM-U-67
def test_wom_u_67__null_required_approvals(db, s):
    """WOM-U-67 — required approvals sent as null on a draft means "all approvers".
    Rules: update_work_order R4."""
    o = mk_order(db, s, "1", **STAMPED(s), required_approvals=0)
    result = UP(db, s, o, required_approvals=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).required_approvals is None


# [claude] WOM-U-68
@xf(2919)
def test_wom_u_68__null_planned_date_clears(db, s):
    """WOM-U-68 — a planned date sent as null clears it.
    Rules: update_work_order R4 [BUG-2919]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    result = UP(db, s, o, planned_date=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).planned_date is None


# [claude] WOM-U-69
@xf(2919)
def test_wom_u_69__null_end_date_clears(db, s):
    """WOM-U-69 — an end date sent as null clears it.
    Rules: update_work_order R4 [BUG-2919]."""
    o = mk_order(db, s, "1", **STAMPED(s), end_date=D(14))
    result = UP(db, s, o, end_date=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).end_date is None


# [claude] WOM-U-70
@xf(2919)
def test_wom_u_70__null_cost_clears(db, s):
    """WOM-U-70 — a cost sent as null clears it on a draft.
    Rules: update_work_order R4 [BUG-2919]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    result = UP(db, s, o, cost=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).cost is None


# [claude] WOM-U-71
def test_wom_u_71__same_assigned_text_rematches(db, s):
    """WOM-U-71 — resending the stored assigned text re-matches stale assignee rows.
    Rules: update_work_order R17."""
    o = mk_order(db, s, "1", **STAMPED(s), assigned_to="Sara Khan")
    mk_assignee(db, s, o, s.U2)
    mk = mark(db)
    result = UP(db, s, o, assigned_to="Sara Khan")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [a.user_id for a in rows_of(db, WorkOrderAssignee, work_order_id=o.id)] == [s.U3.id]
    # Then 3
    assert ev(db, mk, o) == []


# [claude] WOM-U-72
def test_wom_u_72__lowering_required_stamps(db, s):
    """WOM-U-72 — lowering required approvals to the approved count stamps the draft.
    Rules: update_work_order R18; _recompute_approval_status R2."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3)
    mk = mark(db)
    result = UP(db, s, o, required_approvals=1)
    # Then 1
    assert result._approvals_reset is False
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.required_approvals == 1
    assert row.approved_by == s.U2.id
    assert row.approved_at == NOW
    # Then 3
    assert ev(db, mk, o) == [("updated", "Order details updated"), ("approved", "All required approvals collected")]


# [claude] WOM-U-73
def test_wom_u_73__raising_required_revokes(db, s):
    """WOM-U-73 — raising required approvals above the approved count revokes the stamp.
    Rules: update_work_order R18; _recompute_approval_status R3."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = UP(db, s, o, required_approvals=2)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.required_approvals == 2
    assert row.approved_by is None
    assert row.approved_at is None
    # Then 3
    assert ev(db, mk, o) == [("updated", "Order details updated"),
                             ("approval_revoked", "No longer meets approval requirements")]


# [claude] WOM-U-74
@xf(2915)
def test_wom_u_74__no_change_no_updated_by(db, s):
    """WOM-U-74 — a request that changes nothing writes no updated_by.
    Rules: update_work_order R20 [BUG-2915]."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, description="Old desc", priority=WorkOrderPriorityEnum.MEDIUM)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).updated_by is None
    # Then 3
    assert ev(db, mk, o) == []


# [claude] WOM-U-75
def test_wom_u_75__completion_notes_on_draft(db, s):
    """WOM-U-75 — completion notes may be set on a draft and are logged.
    Rules: update_work_order R21, R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, completion_notes="Parts ordered")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).completion_notes == "Parts ordered"
    # Then 3
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "completion_notes", "label": "Completion notes", "from_value": "—", "to_value": "Parts ordered"}]}


# [claude] WOM-U-76
def test_wom_u_76__flushes_never_commits(db, s):
    """WOM-U-76 — update flushes and never commits.
    Rules: update_work_order Side effects."""
    o = mk_order(db, s, "1", **STAMPED(s))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = UP(db, s, o, description="New desc")
        # Then 1
        assert result.id == o.id
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).description == "Old desc"


# [claude] WOM-U-77
def test_wom_u_77__null_with_change_dropped(db, s):
    """WOM-U-77 — a null for an ordinary field sent with a real change is dropped.
    Rules: update_work_order R4, R13."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, description=None, priority=WorkOrderPriorityEnum.HIGH)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.description == "Old desc"
    assert row.priority == WorkOrderPriorityEnum.HIGH
    # Then 3
    assert ev(db, mk, o) == [("updated", "Order details updated")]
    # Then 4
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "priority", "label": "Priority", "from_value": "MEDIUM", "to_value": "HIGH"}]}


# [claude] WOM-U-78
def test_wom_u_78__assigned_not_sent_rows_stay(db, s):
    """WOM-U-78 — assigned text not sent: assignee rows stay as they are.
    Rules: update_work_order R13, R17."""
    o = mk_order(db, s, "1", **STAMPED(s), assigned_to="Sara Khan")
    mk_assignee(db, s, o, s.U2)
    mk = mark(db)
    result = UP(db, s, o, description="New desc")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [a.user_id for a in rows_of(db, WorkOrderAssignee, work_order_id=o.id)] == [s.U2.id]
    # Then 3
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]}


# [claude] WOM-U-79
def test_wom_u_79__account_and_required_logged(db, s):
    """WOM-U-79 — account and required-approvals changes are logged with their labels.
    Rules: update_work_order R4, R13; _collect_field_changes R1, R3."""
    o = mk_order(db, s, "1", **STAMPED(s), account_id=None, required_approvals=None)
    mk = mark(db)
    result = UP(db, s, o, account_id=s.A2.id, required_approvals=0)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.account_id == s.A2.id
    assert row.required_approvals == 0
    # Then 3
    assert ev(db, mk, o)[0] == ("updated", "Order details updated")
    # Then 4
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "account_id", "label": "Account", "from_value": "—", "to_value": str(s.A2.id)},
        {"field": "required_approvals", "label": "Required approvals", "from_value": "—", "to_value": "0"}]}


# [claude] WOM-U-80
def test_wom_u_80__component_change_logged(db, s):
    """WOM-U-80 — a component change logs the cleared machine and the component (revisit after launch).
    Rules: update_work_order R4, R13; _collect_field_changes R1, R3."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = UP(db, s, o, project_component_id=s.PC1.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert evrow(db, mk, o, "updated").metadata_json == {"changes": [
        {"field": "machine_id", "label": "Machine", "from_value": str(s.M1.id), "to_value": "—"},
        {"field": "project_component_id", "label": "Project component", "from_value": "—", "to_value": str(s.PC1.id)}]}


# =========================================================================== #
# get_work_order / list_work_orders / bulk delete / delete
# =========================================================================== #


def _o0(db, s, **k):
    """"order "0", but W0 / WT0 / F0 / M0"."""
    return mk_order(db, s, "0", workspace_id=s.W0.id, work_order_type_id=s.WT0.id, factory_id=s.F0.id,
                    machine_id=s.M0.id, **k)


def _o9(db, s, **k):
    """"order "9", but W2 / WT9 / F9 / M9"."""
    return mk_order(db, s, "9", workspace_id=s.W2.id, work_order_type_id=s.WT9.id, factory_id=s.F9.id,
                    machine_id=s.M9.id, **k)


# [claude] WOM-G-01
def test_wom_g_01__order_returned(db, s):
    """WOM-G-01 — an order of the workspace is returned.
    Rules: get_work_order R1."""
    o = mk_order(db, s, "1")
    result = WOM.get_work_order(db, o.id, s.W1.id)
    # Then 1
    assert result.id == o.id


# [claude] WOM-G-02
def test_wom_g_02__foreign_and_unknown_not_found(db, s):
    """WOM-G-02 — orders of W0 and W2 and an unknown id are not found.
    Rules: get_work_order R1."""
    o0 = _o0(db, s)
    o9 = _o9(db, s)
    result = []
    for i in [o0.id, o9.id, MISSING]:
        with pytest.raises(HTTPException) as exc:
            WOM.get_work_order(db, i, s.W1.id)
        result.append((exc.value.status_code, exc.value.detail))
    # Then 1
    assert result == [(404, f"Work order with ID {o0.id} not found"), (404, f"Work order with ID {o9.id} not found"),
                      (404, "Work order with ID 999999999 not found")]


# [claude] WOM-G-03
@xf(1279)
def test_wom_g_03__deleted_not_found(db, s):
    """WOM-G-03 — a soft-deleted order is not found by default.
    Rules: get_work_order R2 [BUG-1279]."""
    o = mk_order(db, s, "1", **GONE(s))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.get_work_order(db, o.id, s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o.id} not found"


# [claude] WOM-G-04
@xf(1279)
def test_wom_g_04__include_deleted(db, s):
    """WOM-G-04 — include_deleted returns a soft-deleted order.
    Rules: get_work_order R2 [BUG-1279]."""
    o = mk_order(db, s, "1", **GONE(s))
    # Then 1
    result = WOM.get_work_order(db, o.id, s.W1.id, include_deleted=True)
    assert result.id == o.id


# [claude] WOM-L-01
def test_wom_l_01__live_w1_newest_first(db, s):
    """WOM-L-01 — the list is the DAO list of live W1 orders, newest first.
    Rules: list_work_orders R1."""
    o1 = mk_order(db, s, "1", created_at=T0)
    o2 = mk_order(db, s, "2", created_at=T1)
    mk_order(db, s, "3", **GONE(s))
    _o9(db, s)
    result = WOM.list_work_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert [o.id for o in result] == [o2.id, o1.id]


# [claude] WOM-L-02
def test_wom_l_02__status_filter(db, s):
    """WOM-L-02 — wo_status filters by status.
    Rules: list_work_orders R1."""
    mk_order(db, s, "1")
    o2 = mk_order(db, s, "2", **STARTED(s))
    result = WOM.list_work_orders(db, workspace_id=s.W1.id, wo_status="IN_PROGRESS")
    # Then 1
    assert [o.id for o in result] == [o2.id]


# [claude] WOM-L-03
@xf(2670)
def test_wom_l_03__order_ends_with_id(db, s):
    """WOM-L-03 — the list query ends its order with the id.
    Rules: list_work_orders R1 [BUG-2670]."""
    o1 = mk_order(db, s, "1")
    db.expunge_all()
    with Recorder(db) as rec:
        result = WOM.list_work_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert [o.id for o in result] == [o1.id]
    # Then 2
    sel = [st for st in rec.statements if st.lstrip().upper().startswith("SELECT") and "work_orders" in st]
    order_part = sel[0].split("ORDER BY", 1)[1]
    assert "work_orders.created_at DESC" in order_part
    assert "work_orders.id DESC" in order_part
    assert order_part.index("work_orders.id DESC") > order_part.index("work_orders.created_at DESC")


# [claude] WOM-L-04
def test_wom_l_04__other_filters_passed(db, s):
    """WOM-L-04 — every other filter is passed by keyword to the DAO.
    Rules: list_work_orders R1 (parameter list, G11)."""
    t = mk_template(db, s)
    o1 = mk_order(db, s, "1", work_order_type_id=s.WT2.id, priority=WorkOrderPriorityEnum.HIGH,
                  work_order_template_id=t.id)
    mk_order(db, s, "2")
    mk_order(db, s, "3", work_order_type_id=s.WT2.id, priority=WorkOrderPriorityEnum.HIGH, work_order_template_id=t.id,
             factory_id=s.F2.id, machine_id=s.M3.id)
    result = WOM.list_work_orders(db, workspace_id=s.W1.id, work_order_type_id=s.WT2.id,
                                  priority=WorkOrderPriorityEnum.HIGH, factory_id=s.F1.id, machine_id=s.M1.id,
                                  work_order_template_id=t.id, planned_date_from=D(10), planned_date_to=D(14),
                                  skip=0, limit=10)
    # Then 1
    assert [o.id for o in result] == [o1.id]


# [claude] WOM-L-05
def test_wom_l_05__skip_and_limit(db, s):
    """WOM-L-05 — skip and limit page the newest-first list.
    Rules: list_work_orders R1 (parameter list, G11)."""
    mk_order(db, s, "1", created_at=datetime(2026, 1, 1, 8, 0, 0))
    o2 = mk_order(db, s, "2", created_at=datetime(2026, 2, 1, 8, 0, 0))
    mk_order(db, s, "3", created_at=datetime(2026, 3, 1, 8, 0, 0))
    result = WOM.list_work_orders(db, workspace_id=s.W1.id, skip=1, limit=1)
    # Then 1
    assert [o.id for o in result] == [o2.id]


# [claude] WOM-L-06
def test_wom_l_06__paging_defaults():
    """WOM-L-06 — the list's paging defaults are skip 0 and limit 100.
    Rules: list_work_orders (signature, G11)."""
    import inspect
    result = inspect.signature(WOM.list_work_orders).parameters
    # Then 1
    assert result["limit"].default == 100
    # Then 2
    assert result["skip"].default == 0


def _bd(db, s, t, **k):
    return WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=s.W1.id, user_id=s.U2.id,
                                                    work_order_template_id=t.id, machine_id=s.M1.id, **k)


class _Today9(date):
    """Conventions "Externals" `datetime.date` (BD-03, BD-04): today() is D(9)."""

    @classmethod
    def today(cls):
        return D(9)


# [claude] WOM-BD-01
def test_wom_bd_01__future_drafts_deleted(db, s):
    """WOM-BD-01 — live drafts of the template and machine after the cutoff are soft-deleted.
    Rules: bulk_delete_future_recurrence_drafts R1, R2, R3."""
    t = mk_template(db, s, **WEEKLY)
    t2 = mk_template(db, s, template_name="Greasing")
    a = mk_order(db, s, "a", work_order_template_id=t.id, planned_date=D(12))
    b = mk_order(db, s, "b", work_order_template_id=t.id, planned_date=D(11))
    on = mk_order(db, s, "c", work_order_template_id=t.id, planned_date=D(10))
    ip = mk_order(db, s, "d", **{**STARTED(s), "work_order_template_id": t.id, "planned_date": D(13)})
    om = mk_order(db, s, "e", work_order_template_id=t.id, planned_date=D(14), machine_id=s.M2.id)
    ot = mk_order(db, s, "f", work_order_template_id=t2.id, planned_date=D(15))
    mk = mark(db)
    snaps = {x.id: snap(db, x) for x in (on, ip, om, ot)}
    result = _bd(db, s, t, after_date=D(10))
    # Then 1
    assert result == [b.id, a.id]
    # Then 2
    ra = reread(db, WorkOrder, a.id)
    assert ra.is_deleted is True
    assert ra.deleted_by == s.U2.id
    assert ra.status == "DRAFT"
    # Then 3
    rb = reread(db, WorkOrder, b.id)
    assert rb.is_deleted is True
    assert rb.deleted_by == s.U2.id
    # Then 4
    assert snap(db, on) == snaps[on.id]
    # Then 5
    assert snap(db, ip) == snaps[ip.id]
    # Then 6
    assert snap(db, om) == snaps[om.id]
    # Then 7
    assert snap(db, ot) == snaps[ot.id]
    # Then 8
    assert db.execute(select(func.count()).select_from(WorkOrderEvent).where(
        WorkOrderEvent.id > mk.work_order_events)).scalar_one() == 0


# [claude] WOM-BD-02
def test_wom_bd_02__nothing_to_delete(db, s):
    """WOM-BD-02 — nothing to delete returns an empty list.
    Rules: bulk_delete_future_recurrence_drafts R3."""
    t = mk_template(db, s, **WEEKLY)
    mk_order(db, s, "c", work_order_template_id=t.id, planned_date=D(10))
    before = counts(db)
    result = _bd(db, s, t, after_date=D(10))
    # Then 1
    assert result == []
    # Then 2
    assert counts(db) == before


# [claude] WOM-BD-03
@xf(2925)
def test_wom_bd_03__default_cutoff_utc(db, s):
    """WOM-BD-03 — without a cutoff, "today" is the UTC date.
    Rules: bulk_delete_future_recurrence_drafts R1 [BUG-2925]."""
    with patch("datetime.date", _Today9):
        t = mk_template(db, s, **WEEKLY)
        a = mk_order(db, s, "a", work_order_template_id=t.id, planned_date=D(10))
        result = _bd(db, s, t)
    # Then 1
    assert result == []
    # Then 2
    assert reread(db, WorkOrder, a.id).is_deleted is False


# [claude] WOM-BD-04
def test_wom_bd_04__default_cutoff_after_both(db, s):
    """WOM-BD-04 — without a cutoff, a draft after both "todays" is deleted.
    Rules: bulk_delete_future_recurrence_drafts R1, R2."""
    with patch("datetime.date", _Today9):
        t = mk_template(db, s, **WEEKLY)
        a = mk_order(db, s, "a", work_order_template_id=t.id, planned_date=D(12))
        result = _bd(db, s, t)
    # Then 1
    assert result == [a.id]
    # Then 2
    ra = reread(db, WorkOrder, a.id)
    assert ra.is_deleted is True
    assert ra.deleted_by == s.U2.id


# [claude] WOM-BD-05
def test_wom_bd_05__flushes_never_commits(db, s):
    """WOM-BD-05 — bulk delete flushes and never commits.
    Rules: bulk_delete_future_recurrence_drafts R2."""
    t = mk_template(db, s, **WEEKLY)
    a = mk_order(db, s, "a", work_order_template_id=t.id, planned_date=D(12))
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _bd(db, s, t, after_date=D(10))
        # Then 1
        assert result == [a.id]
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, a.id).is_deleted is False


# [claude] WOM-D-01
def test_wom_d_01__draft_soft_deleted(db, s):
    """WOM-D-01 — a draft is soft-deleted, nothing else changes, no event.
    Rules: delete_work_order R4, R6."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == s.U2.id
    assert row.deleted_at is not None
    # Then 3
    assert row.status == "DRAFT"
    assert row.updated_by is None
    # Then 4
    assert ev(db, mk, o) == []


# [claude] WOM-D-02
def test_wom_d_02__foreign_and_unknown_not_found(db, s):
    """WOM-D-02 — orders of W0 and W2 and an unknown id are not found.
    Rules: delete_work_order R1."""
    o0 = _o0(db, s)
    o9 = _o9(db, s)
    b0, b9 = snap(db, o0), snap(db, o9)
    result = []
    for i in [o0.id, o9.id, MISSING]:
        with pytest.raises(HTTPException) as exc:
            WOM.delete_work_order(db, i, s.W1.id, s.U2.id)
        result.append((exc.value.status_code, exc.value.detail))
    # Then 1
    assert result == [(404, f"Work order with ID {o0.id} not found"), (404, f"Work order with ID {o9.id} not found"),
                      (404, "Work order with ID 999999999 not found")]
    # Then 2
    assert snap(db, o0) == b0
    # Then 3
    assert snap(db, o9) == b9


# [claude] WOM-D-03
def test_wom_d_03__already_deleted(db, s):
    """WOM-D-03 — an already deleted order is refused.
    Rules: delete_work_order R2."""
    o = mk_order(db, s, "1", **GONE(s))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is already deleted"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, o) == before


# [claude] WOM-D-04
def test_wom_d_04__prod_started_refused(db, s):
    """WOM-D-04 — in production with the switch off, a started order cannot be deleted.
    Rules: delete_work_order R3."""
    with PROD(False):
        o = mk_order(db, s, "1", **STARTED(s))
        before = snap(db, o)
        # Then 1
        with pytest.raises(HTTPException) as exc:
            WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a draft work order can be deleted — void it instead"
    # Then 4
    assert snap(db, o) == before


# [claude] WOM-D-05
def test_wom_d_05__prod_completed_refused(db, s):
    """WOM-D-05 — in production with the switch off, a completed order cannot be deleted.
    Rules: delete_work_order R3."""
    with PROD(False):
        o = mk_order(db, s, "1", **COMPLETED(s))
        before = snap(db, o)
        # Then 1
        with pytest.raises(HTTPException) as exc:
            WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Only a draft work order can be deleted — void it instead"
    # Then 4
    assert snap(db, o) == before


# [claude] WOM-D-06
def test_wom_d_06__prod_draft_deleted(db, s):
    """WOM-D-06 — in production, a draft can be deleted.
    Rules: delete_work_order R3, R4."""
    with PROD(False):
        o = mk_order(db, s, "1")
        result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).is_deleted is True


# [claude] WOM-D-07
def test_wom_d_07__prod_switch_on_started_deleted(db, s):
    """WOM-D-07 — in production with the switch on, a started order can be deleted.
    Rules: delete_work_order R3, R4."""
    with PROD(True):
        o = mk_order(db, s, "1", **STARTED(s))
        result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.is_deleted is True
    assert row.status == "IN_PROGRESS"


# [claude] WOM-D-08
def test_wom_d_08__dev_started_deleted_untouched(db, s):
    """WOM-D-08 — outside production a started order is deleted with its stock, lines and approvers untouched.
    Rules: delete_work_order R4 (Q7)."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = mk_order(db, s, "1", **STARTED(s))
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    bl, ba = snap(db, ln), snap(db, a)
    result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.is_deleted is True
    assert row.status == "IN_PROGRESS"
    # Then 3
    assert snap(db, ln) == bl
    # Then 4
    assert snap(db, a) == ba
    # Then 5
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 6
    assert led(db, mk, s, s.F1, s.I1, STORAGE) == []
    # Then 7
    assert acts(db, mk, s.M1) == []


# [claude] WOM-D-09
def test_wom_d_09__invoice_left_alone(db, s):
    """WOM-D-09 — the manager leaves a linked invoice alone (the BUG-2923 fix is in the service).
    Rules: delete_work_order R5, R6."""
    inv = mk_invoice(db, s, "draft")
    o = mk_order(db, s, "1", account_id=s.A1.id, invoice_id=inv.id)
    binv = snap(db, inv)
    result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.is_deleted is True
    assert row.invoice_id == inv.id
    # Then 3
    assert snap(db, inv) == binv


# [claude] WOM-D-10
def test_wom_d_10__flushes_never_commits(db, s):
    """WOM-D-10 — delete flushes and never commits.
    Rules: delete_work_order R6."""
    o = mk_order(db, s, "1")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = WOM.delete_work_order(db, o.id, s.W1.id, s.U2.id)
        # Then 1
        assert result.id == o.id
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).is_deleted is False


# =========================================================================== #
# Approvals: list / summary / met / reset / recompute
# =========================================================================== #


# [claude] WOM-LA-01
def test_wom_la_01__tuple_per_approver(db, s):
    """WOM-LA-01 — one tuple per approver with profile and member position.
    Rules: list_approvers R1, R2."""
    o = mk_order(db, s, "1")
    a1r = mk_approver(db, s, o, s.U1)
    a2r = mk_approver(db, s, o, s.U2, assigned_at=T1)
    result = WOM.list_approvers(db, o.id, s.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert {r.id: (p.id, pos) for r, p, pos in result} == {a1r.id: (s.U1.id, "Supervisor"), a2r.id: (s.U2.id, None)}


# [claude] WOM-LA-02
def test_wom_la_02__position_any_status(db, s):
    """WOM-LA-02 — the position is read whatever the membership status; no W1 membership gives None.
    Rules: list_approvers R2."""
    o = mk_order(db, s, "1")
    a4 = mk_approver(db, s, o, s.U4)
    a5 = mk_approver(db, s, o, s.U5)
    result = WOM.list_approvers(db, o.id, s.W1.id)
    # Then 1
    assert {r.id: (p.id, pos) for r, p, pos in result} == {a4.id: (s.U4.id, "Fitter"), a5.id: (s.U5.id, None)}


# [claude] WOM-LA-03
def test_wom_la_03__order_of_w2_not_found(db, s):
    """WOM-LA-03 — an order of W2 is not found.
    Rules: list_approvers R1."""
    o9 = _o9(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.list_approvers(db, o9.id, s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"


# [claude] WOM-LA-04
def test_wom_la_04__assignment_order(db, s):
    """WOM-LA-04 — approvers come in assignment order.
    Rules: list_approvers R2."""
    o = mk_order(db, s, "1")
    a1r = mk_approver(db, s, o, s.U2, assigned_at=T1)
    a2r = mk_approver(db, s, o, s.U3, assigned_at=T0)
    result = WOM.list_approvers(db, o.id, s.W1.id)
    # Then 1
    assert [r.id for r, _, _ in result] == [a2r.id, a1r.id]


# [claude] WOM-LA-05
@xf(1200)
def test_wom_la_05__ties_broken_by_id(db, s):
    """WOM-LA-05 — the approver query breaks ties by id.
    Rules: list_approvers R2 [BUG-1200]."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    db.expunge_all()
    with Recorder(db) as rec:
        result = WOM.list_approvers(db, o.id, s.W1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert "work_order_approvers.id" in rec.order_part("work_order_approvers")


# [claude] WOM-AS-01
def test_wom_as_01__required_defaults_to_count(db, s):
    """WOM-AS-01 — required defaults to the number of approvers.
    Rules: approval_summary R1, R2, R3, R5."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3)
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (1, 2, False)


# [claude] WOM-AS-02
def test_wom_as_02__all_approved_met(db, s):
    """WOM-AS-02 — every approver approved is met.
    Rules: approval_summary R3."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3, **APPROVED)
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (2, 2, True)


# [claude] WOM-AS-03
def test_wom_as_03__explicit_required_wins(db, s):
    """WOM-AS-03 — an explicit required count wins over the number of approvers.
    Rules: approval_summary R2, R3."""
    o = mk_order(db, s, "1", required_approvals=1)
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3)
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (1, 1, True)


# [claude] WOM-AS-04
def test_wom_as_04__zero_required_waiver(db, s):
    """WOM-AS-04 — zero required is an explicit waiver.
    Rules: approval_summary R3."""
    o = mk_order(db, s, "1", required_approvals=0)
    mk_approver(db, s, o, s.U2)
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (0, 0, True)


# [claude] WOM-AS-05
def test_wom_as_05__no_approver_met(db, s):
    """WOM-AS-05 — an order that never had an approver is 0 of 0, met.
    Rules: approval_summary R4."""
    o = mk_order(db, s, "1")
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (0, 0, True)


# [claude] WOM-AS-06
def test_wom_as_06__foreign_rows_not_counted(db, s):
    """WOM-AS-06 — approved rows of W0 and W2 on the order are not counted.
    Rules: approval_summary R1."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3, **APPROVED, workspace_id=s.W0.id)
    mk_approver(db, s, o, s.U5, **APPROVED, workspace_id=s.W2.id)
    result = WOM.approval_summary(db, o)
    # Then 1
    assert result == (0, 1, False)


# [claude] WOM-AM-01
def test_wom_am_01__met_flag(db, s):
    """WOM-AM-01 — approvals_met is the summary's met flag.
    Rules: approvals_met R1."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    p = mk_order(db, s, "2")
    mk_approver(db, s, p, s.U2, **APPROVED)
    result = (WOM.approvals_met(db, o), WOM.approvals_met(db, p))
    # Then 1
    assert result == (False, True)


# [claude] WOM-RA-01
def test_wom_ra_01__approved_rows_cleared(db, s):
    """WOM-RA-01 — approved rows are cleared and one event is logged.
    Rules: reset_approvals R1, R2, R3."""
    o = mk_order(db, s, "1", **STAMPED(s))
    a = mk_approver(db, s, o, s.U1, **APPROVED)
    b = mk_approver(db, s, o, s.U2, **APPROVED)
    c = mk_approver(db, s, o, s.U3)
    mk = mark(db)
    bc = snap(db, c)
    result = WOM.reset_approvals(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    rb = reread(db, WorkOrderApprover, b.id)
    assert rb.approved is False
    assert rb.approved_at is None
    # Then 4
    assert snap(db, c) == bc
    # Then 5
    assert ev(db, mk, o) == [("approvals_reset", "Section unconfirmed (2 approval(s) cleared)")]
    # Then 6
    assert evrow(db, mk, o, "approvals_reset").performed_by == s.U2.id
    # Then 7
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by == s.U1.id
    assert row.approved_at == T0


# [claude] WOM-RA-02
def test_wom_ra_02__given_reason(db, s):
    """WOM-RA-02 — a given reason is used in the event.
    Rules: reset_approvals R2."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = WOM.reset_approvals(db, o.id, s.W1.id, s.U2.id, reason="Items edited")
    # Then 1
    assert result is None
    # Then 2
    assert ev(db, mk, o) == [("approvals_reset", "Items edited (1 approval(s) cleared)")]


# [claude] WOM-RA-03
def test_wom_ra_03__nothing_approved_nothing_written(db, s):
    """WOM-RA-03 — nothing approved: nothing written, no event.
    Rules: reset_approvals R3."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U3)
    x = mk_approver(db, s, o, s.U2, **APPROVED, workspace_id=s.W2.id)
    bx = snap(db, x)
    before = counts(db)
    result = WOM.reset_approvals(db, o.id, s.W1.id, s.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    assert snap(db, x) == bx
    # Then 4
    assert counts(db) == before


# [claude] WOM-RAS-01
def test_wom_ras_01__auto_approved(db, s):
    """WOM-RAS-01 — a met draft with no stamp is auto-approved when nothing is required.
    Rules: _recompute_approval_status R2."""
    o = mk_order(db, s, "1")
    mk = mark(db)
    WOM._recompute_approval_status(db, o, s.W1.id, s.U2.id)
    # Then 1
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by == s.U2.id
    assert row.approved_at == NOW
    # Then 2
    assert ev(db, mk, o) == [("auto_approved", "Ready to start — no approval required")]


# [claude] WOM-RAS-02
def test_wom_ras_02__stamped_approved(db, s):
    """WOM-RAS-02 — a met draft with approvals required is stamped approved.
    Rules: _recompute_approval_status R2."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    WOM._recompute_approval_status(db, o, s.W1.id, s.U2.id)
    # Then 1
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by == s.U2.id
    assert row.approved_at == NOW
    # Then 2
    assert ev(db, mk, o) == [("approved", "All required approvals collected")]


# [claude] WOM-RAS-03
def test_wom_ras_03__unmet_loses_stamp(db, s):
    """WOM-RAS-03 — an unmet stamped draft loses its stamp.
    Rules: _recompute_approval_status R3."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_approver(db, s, o, s.U2)
    mk = mark(db)
    WOM._recompute_approval_status(db, o, s.W1.id, s.U2.id)
    # Then 1
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by is None
    assert row.approved_at is None
    # Then 2
    assert ev(db, mk, o) == [("approval_revoked", "No longer meets approval requirements")]


# [claude] WOM-RAS-04
def test_wom_ras_04__nothing_to_do(db, s):
    """WOM-RAS-04 — met and stamped, or unmet and unstamped: nothing.
    Rules: _recompute_approval_status R4."""
    o = mk_order(db, s, "1", **STAMPED(s))
    p = mk_order(db, s, "2")
    mk_approver(db, s, p, s.U2)
    bo, bp = snap(db, o), snap(db, p)
    before = counts(db)
    WOM._recompute_approval_status(db, o, s.W1.id, s.U2.id)
    WOM._recompute_approval_status(db, p, s.W1.id, s.U2.id)
    # Then 1
    assert not db.dirty
    # Then 2
    assert snap(db, o) == bo
    # Then 3
    assert snap(db, p) == bp
    # Then 4
    assert counts(db) == before


# [claude] WOM-RAS-05
def test_wom_ras_05__only_drafts(db, s):
    """WOM-RAS-05 — only drafts are looked at.
    Rules: _recompute_approval_status R1."""
    o = mk_order(db, s, "1", status="IN_PROGRESS")
    p = mk_order(db, s, "2", **COMPLETED(s), **STAMPED(s))
    mk_approver(db, s, p, s.U2)
    bo, bp = snap(db, o), snap(db, p)
    before = counts(db)
    WOM._recompute_approval_status(db, o, s.W1.id, s.U2.id)
    WOM._recompute_approval_status(db, p, s.W1.id, s.U2.id)
    # Then 1
    assert snap(db, o) == bo
    # Then 2
    assert snap(db, p) == bp
    # Then 3
    assert counts(db) == before


# =========================================================================== #
# add_approver / remove_approver
# =========================================================================== #


# [claude] WOM-AA-01
def test_wom_aa_01__member_added_stamp_lost(db, s):
    """WOM-AA-01 — an active member is added, logged, and the met draft loses its stamp.
    Rules: add_approver R1, R5, R6, R7."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk = mark(db)
    result = WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id, approver_slot="QA")
    # Then 1
    assert isinstance(result, WorkOrderApprover)
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderApprover, result.id)
    assert row.work_order_id == o.id
    assert row.user_id == s.U2.id
    assert row.workspace_id == s.W1.id
    assert row.approved is False
    assert row.assigned_by == s.U1.id
    assert row.approver_slot == "QA"
    # Then 3
    assert ev(db, mk, o) == [("approver_added", "Added Rahim Uddin as approver"),
                             ("approval_revoked", "No longer meets approval requirements")]
    # Then 4
    assert evrow(db, mk, o, "approver_added").performed_by == s.U1.id
    # Then 5
    assert evrow(db, mk, o, "approver_added").metadata_json == {"user_id": s.U2.id, "user_name": "Rahim Uddin"}
    # Then 6
    assert reread(db, WorkOrder, o.id).approved_at is None


# [claude] WOM-AA-02
def test_wom_aa_02__no_slot_none(db, s):
    """WOM-AA-02 — no slot is stored as None.
    Rules: add_approver R5."""
    o = mk_order(db, s, "1")
    result = WOM.add_approver(db, o.id, s.U3.id, s.W1.id, s.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderApprover, result.id)
    assert row.approver_slot is None
    assert row.approved_at is None


# [claude] WOM-AA-03
def test_wom_aa_03__completed_no_approver(db, s):
    """WOM-AA-03 — a completed order takes no approver.
    Rules: add_approver R2."""
    o = mk_order(db, s, "1", **COMPLETED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-AA-04
def test_wom_aa_04__voided_before_membership(db, s):
    """WOM-AA-04 — a voided order takes no approver, checked before membership.
    Rules: add_approver R2, R3 (order)."""
    o = mk_order(db, s, "1", **VOIDED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U5.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AA-05
@xf(2931)
def test_wom_aa_05__started_no_new_approver(db, s):
    """WOM-AA-05 — a started order takes no new approver.
    Rules: add_approver R2a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work has started — approvals can no longer change"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-AA-06
def test_wom_aa_06__suspended_member(db, s):
    """WOM-AA-06 — a suspended member cannot be an approver.
    Rules: add_approver R3."""
    o = mk_order(db, s, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U4.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AA-07
def test_wom_aa_07__member_of_other_workspaces(db, s):
    """WOM-AA-07 — an active member of W0 and W2 only cannot be an approver.
    Rules: add_approver R3."""
    o = mk_order(db, s, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U5.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AA-08
def test_wom_aa_08__same_person_twice(db, s):
    """WOM-AA-08 — the same person twice is a conflict.
    Rules: add_approver R4."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    ba = snap(db, a)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"
    # Then 4
    assert snap(db, a) == ba
    # Then 5
    assert counts(db) == before


# [claude] WOM-AA-09
def test_wom_aa_09__order_of_w2_not_found(db, s):
    """WOM-AA-09 — an order of W2 is not found.
    Rules: add_approver R1."""
    o9 = _o9(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.add_approver(db, o9.id, s.U2.id, s.W1.id, s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AA-10
def test_wom_aa_10__flushes_never_commits(db, s):
    """WOM-AA-10 — add approver flushes and never commits.
    Rules: add_approver R5."""
    o = mk_order(db, s, "1")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id)
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert len(rows_of(db, WorkOrderApprover, work_order_id=o.id)) == 0


# [claude] WOM-AA-11
@xf(2916)
def test_wom_aa_11__order_row_locked(db, s):
    """WOM-AA-11 — the order row is locked before its state is checked.
    Rules: add_approver R8 [BUG-2916]."""
    o = mk_order(db, s, "1")
    db.expunge_all()
    with Recorder(db) as rec:
        result = WOM.add_approver(db, o.id, s.U2.id, s.W1.id, s.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-AA-12
def test_wom_aa_12__empty_profile_name(db, s):
    """WOM-AA-12 — an approver whose profile name is empty is logged with the empty name.
    Rules: add_approver R6, R6a."""
    ue = make_profile(db, name="")
    _add(db, WorkspaceMember(workspace_id=s.W1.id, user_id=ue.id, role="member", status="active", position=None))
    o = mk_order(db, s, "1")
    mk = mark(db)
    result = WOM.add_approver(db, o.id, ue.id, s.W1.id, s.U1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert evrow(db, mk, o, "approver_added").description == "Added  as approver"
    # Then 3
    assert evrow(db, mk, o, "approver_added").metadata_json == {"user_id": ue.id, "user_name": ""}


def _appr_count(db, o):
    return len(rows_of(db, WorkOrderApprover, work_order_id=o.id))


# [claude] WOM-RMA-01
def test_wom_rma_01__deleted_logged_met(db, s):
    """WOM-RMA-01 — the row is deleted and logged; the remaining approval meets the order.
    Rules: remove_approver R1, R3, R4, R4a."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3, **APPROVED)
    mk = mark(db)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, WorkOrderApprover, id=a.id)) == 0
    # Then 3
    assert ev(db, mk, o) == [("approver_removed", "Removed Rahim Uddin as approver"),
                             ("approved", "All required approvals collected")]
    # Then 4
    assert evrow(db, mk, o, "approver_removed").performed_by == s.U1.id
    # Then 5
    assert evrow(db, mk, o, "approver_removed").metadata_json == {"user_id": s.U2.id, "user_name": "Rahim Uddin"}
    # Then 6
    assert reread(db, WorkOrder, o.id).approved_at == NOW
    # Then 7
    assert reread(db, WorkOrder, o.id).approved_by == s.U1.id
    # Then 8
    assert evrow(db, mk, o, "approved").performed_by == s.U1.id


# [claude] WOM-RMA-02
def test_wom_rma_02__no_performer(db, s):
    """WOM-RMA-02 — no performer is allowed.
    Rules: remove_approver R3."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3, **APPROVED)
    mk = mark(db)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id)
    # Then 1
    assert result is None
    # Then 2
    assert ev(db, mk, o) == [("approver_removed", "Removed Rahim Uddin as approver")]
    # Then 3
    assert evrow(db, mk, o, "approver_removed").performed_by is None


# [claude] WOM-RMA-03
def test_wom_rma_03__voided_keeps_approvers(db, s):
    """WOM-RMA-03 — a completed or voided order keeps its approvers.
    Rules: remove_approver R1."""
    o = mk_order(db, s, "1", **VOIDED(s))
    a = mk_approver(db, s, o, s.U2)
    ba = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert snap(db, a) == ba


# [claude] WOM-RMA-04
@xf(2931)
def test_wom_rma_04__started_keeps_approvers(db, s):
    """WOM-RMA-04 — a started order keeps its approvers.
    Rules: remove_approver R2a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s))
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ba = snap(db, a)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work has started — approvals can no longer change"
    # Then 4
    assert snap(db, a) == ba
    # Then 5
    assert counts(db) == before


# [claude] WOM-RMA-05
def test_wom_rma_05__not_an_approver(db, s):
    """WOM-RMA-05 — someone who is not an approver of this order is not found.
    Rules: remove_approver R2."""
    o = mk_order(db, s, "1")
    p = mk_order(db, s, "2")
    x = mk_approver(db, s, p, s.U2)
    bx = snap(db, x)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Approver not found"
    # Then 4
    assert snap(db, x) == bx
    # Then 5
    assert counts(db) == before


# [claude] WOM-RMA-06
@xf(1204)
def test_wom_rma_06__last_approver_unapproved(db, s):
    """WOM-RMA-06 — removing the last approver leaves the order unapproved.
    Rules: remove_approver R4; approval_summary R4 [BUG-1204]."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    mk_approver(db, s, o, s.U2, **APPROVED)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert _appr_count(db, o) == 0
    # Then 3
    assert WOM.approval_summary(db, o)[2] is False
    # Then 4
    assert reread(db, WorkOrder, o.id).approved_at is None


# [claude] WOM-RMA-07
def test_wom_rma_07__last_approver_row_deleted(db, s):
    """WOM-RMA-07 — removing the last approver deletes the row and logs it.
    Rules: remove_approver R3."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    assert _appr_count(db, o) == 0
    # Then 3
    assert ev(db, mk, o)[0] == ("approver_removed", "Removed Rahim Uddin as approver")


# [claude] WOM-RMA-08
def test_wom_rma_08__flushes_never_commits(db, s):
    """WOM-RMA-08 — remove approver flushes and never commits.
    Rules: remove_approver R3."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
        # Then 1
        assert _appr_count(db, o) == 1
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert _appr_count(db, o) == 2


# [claude] WOM-RMA-09
@xf(2916)
def test_wom_rma_09__order_row_locked(db, s):
    """WOM-RMA-09 — the order row is locked before its state is checked.
    Rules: remove_approver R5 [BUG-2916]."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3)
    db.expunge_all()
    with Recorder(db) as rec:
        WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 1
    assert _appr_count(db, o) == 1
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-RMA-10
def test_wom_rma_10__no_performer_stamps_none(db, s):
    """WOM-RMA-10 — without a performer, a removal that meets the order stamps no approver.
    Rules: remove_approver R4, R4a."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3, **APPROVED)
    mk = mark(db)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id)
    # Then 1
    assert result is None
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.approved_at == NOW
    assert row.approved_by is None
    # Then 3
    assert evrow(db, mk, o, "approved").performed_by is None


# [claude] WOM-RMA-11
def test_wom_rma_11__unmet_cleared_by_performer(db, s):
    """WOM-RMA-11 — a removal that leaves the order unmet clears the stamp in the performer's name.
    Rules: remove_approver R4, R4a."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_approver(db, s, o, s.U2, **APPROVED)
    mk_approver(db, s, o, s.U3)
    mk = mark(db)
    result = WOM.remove_approver(db, o.id, s.U2.id, s.W1.id, performed_by=s.U1.id)
    # Then 1
    assert result is None
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by is None
    assert row.approved_at is None
    # Then 3
    assert ev(db, mk, o) == [("approver_removed", "Removed Rahim Uddin as approver"),
                             ("approval_revoked", "No longer meets approval requirements")]
    # Then 4
    assert evrow(db, mk, o, "approval_revoked").performed_by == s.U1.id


# =========================================================================== #
# set_approval / log_event / list_events
# =========================================================================== #

_NOT_APPROVER = "You are not an assigned approver for this order"
_APPROVALS_FROZEN = "Work has started — approvals can no longer change"


# [claude] WOM-SA-01
def test_wom_sa_01__approving_stamps(db, s):
    """WOM-SA-01 — approving stamps the row, logs it and approves the order.
    Rules: set_approval R1, R2, R4, R5."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    mk = mark(db)
    result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 1
    assert result.id == a.id
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is True
    assert ra.approved_at == NOW
    # Then 3
    assert ev(db, mk, o) == [("approved", "Approved work order"), ("approved", "All required approvals collected")]
    # Then 4
    assert evrows(db, mk, o)[0].performed_by == s.U2.id
    # Then 5
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by == s.U2.id
    assert row.approved_at == NOW


# [claude] WOM-SA-02
def test_wom_sa_02__withdrawing_revokes(db, s):
    """WOM-SA-02 — withdrawing clears the row and revokes the order's stamp.
    Rules: set_approval R3, R4, R5."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, False)
    # Then 1
    assert result.id == a.id
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    assert ev(db, mk, o) == [("approval_withdrawn", "Withdrew approval"),
                             ("approval_revoked", "No longer meets approval requirements")]
    # Then 4
    assert reread(db, WorkOrder, o.id).approved_at is None


# [claude] WOM-SA-03
def test_wom_sa_03__not_approver_forbidden(db, s):
    """WOM-SA-03 — someone who is not an approver is forbidden.
    Rules: set_approval R1."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U3.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == _NOT_APPROVER
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-SA-04
def test_wom_sa_04__unknown_and_w2_are_403(db, s):
    """WOM-SA-04 — an unknown order and an order of W2 answer 403, not 404.
    Rules: set_approval R1."""
    o9 = _o9(db, s)
    a9 = mk_approver(db, s, o9, s.U2, workspace_id=s.W2.id)
    b9 = snap(db, a9)
    result = []
    for i in [o9.id, MISSING]:
        with pytest.raises(HTTPException) as exc:
            WOM.set_approval(db, i, s.U2.id, s.W1.id, True)
        result.append((exc.value.status_code, exc.value.detail))
    # Then 1
    assert result == [(403, _NOT_APPROVER), (403, _NOT_APPROVER)]
    # Then 2
    assert snap(db, a9) == b9


# [claude] WOM-SA-05
def test_wom_sa_05__completed_not_approvable(db, s):
    """WOM-SA-05 — a completed order cannot be approved.
    Rules: set_approval R2."""
    o = mk_order(db, s, "1", **COMPLETED(s))
    a = mk_approver(db, s, o, s.U2)
    ba = snap(db, a)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert snap(db, a) == ba
    # Then 5
    assert counts(db) == before


# [claude] WOM-SA-06
def test_wom_sa_06__voided_non_approver_403(db, s):
    """WOM-SA-06 — on a voided order a non-approver still gets 403 first.
    Rules: set_approval R1, R2 (order)."""
    o = mk_order(db, s, "1", **VOIDED(s))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == _NOT_APPROVER


# [claude] WOM-SA-07
def test_wom_sa_07__blank_title_gap_reason(db, s):
    """WOM-SA-07 — approving an order with a blank title is refused with the gap reason.
    Rules: set_approval R3."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    o.title = "   "
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order setup is incomplete"
    # Then 4
    assert reread(db, WorkOrderApprover, a.id).approved is False


# [claude] WOM-SA-08
def test_wom_sa_08__withdraw_not_checked(db, s):
    """WOM-SA-08 — withdrawing is not checked for approvability.
    Rules: set_approval R3."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    o.title = "   "
    result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, False)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.approved is False


# [claude] WOM-SA-09
@xf(2931)
def test_wom_sa_09__started_no_approval(db, s):
    """WOM-SA-09 — on a started order an approval can no longer be given.
    Rules: set_approval R3a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s))
    a = mk_approver(db, s, o, s.U2)
    ba = snap(db, a)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _APPROVALS_FROZEN
    # Then 4
    assert snap(db, a) == ba
    # Then 5
    assert counts(db) == before


# [claude] WOM-SA-10
@xf(2931)
def test_wom_sa_10__started_no_withdrawal(db, s):
    """WOM-SA-10 — on a started order an approval can no longer be withdrawn.
    Rules: set_approval R3a [BUG-2931]."""
    o = mk_order(db, s, "1", **STARTED(s))
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ba = snap(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U2.id, s.W1.id, False)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _APPROVALS_FROZEN
    # Then 4
    assert snap(db, a) == ba


# [claude] WOM-SA-11
def test_wom_sa_11__started_non_approver_403(db, s):
    """WOM-SA-11 — on a started order a non-approver still gets 403.
    Rules: set_approval R1, R3a (order)."""
    o = mk_order(db, s, "1", **STARTED(s))
    mk_approver(db, s, o, s.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.set_approval(db, o.id, s.U3.id, s.W1.id, True)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == _NOT_APPROVER


# [claude] WOM-SA-12
@xf(2917)
def test_wom_sa_12__approve_again_noop(db, s):
    """WOM-SA-12 — approving again writes nothing and logs nothing.
    Rules: set_approval R6 [BUG-2917]."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.approved is True
    # Then 3
    assert reread(db, WorkOrderApprover, a.id).approved_at == T0
    # Then 4
    assert ev(db, mk, o) == []


# [claude] WOM-SA-13
@xf(2917)
def test_wom_sa_13__withdraw_never_given_noop(db, s):
    """WOM-SA-13 — withdrawing an approval that was never given logs nothing.
    Rules: set_approval R6 [BUG-2917]."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    mk_approver(db, s, o, s.U3)
    mk = mark(db)
    result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, False)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert ev(db, mk, o) == []


# [claude] WOM-SA-14
@xf(2916)
def test_wom_sa_14__order_row_locked(db, s):
    """WOM-SA-14 — the order row is locked before its state is checked.
    Rules: set_approval R9 [BUG-2916]."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    db.expunge_all()
    with Recorder(db) as rec:
        result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
    # Then 1
    assert result.approved is True
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-SA-15
def test_wom_sa_15__flushes_never_commits(db, s):
    """WOM-SA-15 — set approval flushes and never commits.
    Rules: set_approval R4."""
    o = mk_order(db, s, "1")
    a = mk_approver(db, s, o, s.U2)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = WOM.set_approval(db, o.id, s.U2.id, s.W1.id, True)
        # Then 1
        assert result.approved is True
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrderApprover, a.id).approved is False


# [claude] WOM-LE-01
def test_wom_le_01__one_event_row(db, s):
    """WOM-LE-01 — one event row with the arguments, flushed and returned.
    Rules: log_event R1."""
    o = mk_order(db, s, "1")
    result = WOM.log_event(db, o.id, s.W1.id, "note", "Checked oil", performed_by=s.U2.id, metadata={"k": 1})
    # Then 1
    assert isinstance(result, WorkOrderEvent)
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderEvent, result.id)
    assert row.work_order_id == o.id
    assert row.workspace_id == s.W1.id
    assert row.event_type == "note"
    assert row.description == "Checked oil"
    assert row.performed_by == s.U2.id
    assert row.metadata_json == {"k": 1}


# [claude] WOM-LE-02
def test_wom_le_02__json_null_no_performer(db, s):
    """WOM-LE-02 — no metadata is stored as JSON null; no performer as None.
    Rules: log_event R1."""
    o = mk_order(db, s, "1")
    result = WOM.log_event(db, o.id, s.W1.id, "note", "x")
    # Then 1
    assert result.id is not None
    # Then 2
    assert tuple(db.execute(text("SELECT metadata::text, metadata IS NULL FROM work_order_events WHERE id = :i"),
                            {"i": result.id}).one()) == ("null", False)
    # Then 3
    assert reread(db, WorkOrderEvent, result.id).performed_by is None


# [claude] WOM-LE-03
@xf(1192)
def test_wom_le_03__order_of_w2_refused(db, s):
    """WOM-LE-03 — an order of W2 is refused.
    Rules: log_event R2 [BUG-1192]."""
    o9 = _o9(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.log_event(db, o9.id, s.W1.id, "note", "x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-LE-04
@xf(1192)
def test_wom_le_04__order_of_w0_refused(db, s):
    """WOM-LE-04 — an order of W0 is refused.
    Rules: log_event R2 [BUG-1192]."""
    o0 = _o0(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.log_event(db, o0.id, s.W1.id, "note", "x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o0.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-LE-05
@xf(1192)
def test_wom_le_05__order_id_zero_refused(db, s):
    """WOM-LE-05 — order id 0 is refused.
    Rules: log_event R2 [BUG-1192]."""
    # Then 1
    with pytest.raises(HTTPException) as exc, db.begin_nested():
        WOM.log_event(db, 0, s.W1.id, "note", "x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order with ID 0 not found"


# [claude] WOM-LE-06
def test_wom_le_06__deleted_order_takes_events(db, s):
    """WOM-LE-06 — a soft-deleted order of the workspace still takes events.
    Rules: log_event R2."""
    o = mk_order(db, s, "1", **GONE(s))
    mk = mark(db)
    result = WOM.log_event(db, o.id, s.W1.id, "note", "After delete")
    # Then 1
    assert result.id is not None
    # Then 2
    assert ev(db, mk, o) == [("note", "After delete")]


# [claude] WOM-LE-07
def test_wom_le_07__flushes_never_commits(db, s):
    """WOM-LE-07 — log event flushes and never commits.
    Rules: log_event R1."""
    o = mk_order(db, s, "1")
    mk = mark(db)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = WOM.log_event(db, o.id, s.W1.id, "note", "x")
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert ev(db, mk, o) == []


# [claude] WOM-LEV-01
def test_wom_lev_01__newest_first_with_performer(db, s):
    """WOM-LEV-01 — events newest first, each with its performer or None.
    Rules: list_events R1, R2."""
    o = mk_order(db, s, "1")
    e1 = mk_event(db, s, o, "note", None, T0, performed_by=s.U2.id)
    e2 = mk_event(db, s, o, "note", None, T1)
    p = mk_order(db, s, "2")
    mk_event(db, s, p, "note", None, NOW)
    result = WOM.list_events(db, o.id, s.W1.id)
    # Then 1
    assert [(e.id, pr.id if pr else None) for e, pr in result] == [(e2.id, None), (e1.id, s.U2.id)]


# [claude] WOM-LEV-02
def test_wom_lev_02__order_of_w2_not_found(db, s):
    """WOM-LEV-02 — an order of W2 is not found.
    Rules: list_events R1."""
    o9 = _o9(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.list_events(db, o9.id, s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"


# =========================================================================== #
# _consume_item / _reverse_item_consumption / _adjust_consumed_item_quantity
# =========================================================================== #


def _stock_order(db, s, **k):
    """`O = order "1", but started` (+ the card's extra columns)."""
    return mk_order(db, s, "1", **{**STARTED(s), **k})


def _new_count(db, mk, model):
    return db.execute(select(func.count()).select_from(model).where(model.id > _since(mk, model))).scalar_one()


# [claude] WOM-CI-01
def test_wom_ci_01__storage_line_leaves_stock(db, s):
    """WOM-CI-01 — a storage line leaves stock and is stamped with the posting's cost.
    Rules: _consume_item R4, R5."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.source_type, r.source_id) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption", Decimal("3"), "work_order", o.id)]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.consumed_at == NOW
    assert row.consumed_by == s.U2.id
    assert row.unit_cost == Decimal("2.50")
    assert row.total_cost == Decimal("7.50")


# [claude] WOM-CI-02
def test_wom_ci_02__used_activity_storage(db, s):
    """WOM-CI-02 — on an order with a machine, a "used" activity names the storage source.
    Rules: _consume_item R6."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert [t for t, _ in acts(db, mk, s.M1)] == ["work_order_item_used"]
    # Then 2
    a = actrows(db, mk, s.M1)[0]
    assert a.description == f"Used 3 Bolt from storage for work order {o.work_order_number}"
    # Then 3
    assert a.metadata_json["item_id"] == s.I1.id
    assert a.metadata_json["item_name"] == "Bolt"
    assert a.metadata_json["work_order_id"] == o.id
    # Then 4
    assert set(a.metadata_json.keys()) == {"item_id", "item_name", "quantity", "work_order_id"}
    # Then 5
    assert a.metadata_json["quantity"] == 3
    assert isinstance(a.metadata_json["quantity"], int)


# [claude] WOM-CI-03
def test_wom_ci_03__machine_source(db, s):
    """WOM-CI-03 — a machine source line leaves that machine's stock and both activities are logged.
    Rules: _consume_item R4, R6."""
    mk_MS(db, s, s.M2, s.I1, 5, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", source_location_type="machine", source_location_id=s.M2.id)
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M2, s.I1) == Decimal("2")
    # Then 2
    assert [(r.transaction_type, r.quantity) for r in mled(db, mk, s, s.M2, s.I1)] == [("consumption", Decimal("3"))]
    # Then 3
    assert [t for t, _ in acts(db, mk, s.M2)] == ["consumption"]
    # Then 4
    assert actrows(db, mk, s.M2)[0].description == f"Consumed for work order {o.work_order_number}: 3 units of Bolt"
    # Then 5
    assert acts(db, mk, s.M1) == [
        ("work_order_item_used", f"Used 3 Bolt from machine #{s.M2.id} for work order {o.work_order_number}")]
    # Then 6
    row = reread(db, WorkOrderItem, ln.id)
    assert row.unit_cost == Decimal("4.00")
    assert row.total_cost == Decimal("12.00")


# [claude] WOM-CI-04
def test_wom_ci_04__no_machine_no_used_activity(db, s):
    """WOM-CI-04 — on an order with no machine no "used" activity is logged.
    Rules: _consume_item R6."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).consumed_at == NOW
    # Then 2
    assert _new_count(db, mk, MachineActivityEvent) == 0


# [claude] WOM-CI-05
def test_wom_ci_05__no_inventory_skipped(db, s):
    """WOM-CI-05 — a line not using inventory is skipped.
    Rules: _consume_item R1."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", uses_inventory=False)
    bl = snap(db, ln)
    before = counts(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert not db.dirty
    # Then 2
    assert snap(db, ln) == bl
    # Then 3
    assert counts(db) == before


# [claude] WOM-CI-06
def test_wom_ci_06__already_consumed_skipped(db, s):
    """WOM-CI-06 — an already consumed line is skipped.
    Rules: _consume_item R1."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    bl = snap(db, ln)
    before = counts(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert snap(db, ln) == bl
    # Then 2
    assert counts(db) == before


@pytest.mark.parametrize("cols", [
    pytest.param({"source_location_type": None}, id="WOM-CI-07"),
    pytest.param({"source_location_id": 0}, id="WOM-CI-08"),
])
def test_wom_ci_07_08__no_source_refused(db, s, cols):
    """WOM-CI-07 / WOM-CI-08 — an inventory line without a source type (or source id 0) is refused.
    Rules: _consume_item R2."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **cols)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} uses inventory but has no source location set"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CI-09
def test_wom_ci_09__fractional_quantity(db, s):
    """WOM-CI-09 — a fractional quantity cannot be consumed.
    Rules: _consume_item R3."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2.50")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} has a fractional quantity; inventory consumption requires whole units"
    # Then 4
    assert counts(db) == before


# [claude] WOM-CI-10
def test_wom_ci_10__insufficient_stock(db, s):
    """WOM-CI-10 — not enough stock is refused by the posting.
    Rules: _consume_item R4."""
    mk_S(db, s, s.F1, s.I1, 2, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Insufficient stock (2 available, 3 requested)"
    # Then 4
    assert led(db, mk, s, s.F1, s.I1, STORAGE) == []


# [claude] WOM-CI-11
def test_wom_ci_11__source_factory_of_w2(db, s):
    """WOM-CI-11 — a source factory of W2 is not found.
    Rules: _consume_item R4."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", source_location_id=s.F9.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"


# [claude] WOM-CI-12
@xf(665)
def test_wom_ci_12__zero_quantity_refused(db, s):
    """WOM-CI-12 — a zero quantity is refused.
    Rules: _consume_item R4 [BUG-665]."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "0")
    mk = mark(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE) == []


# [claude] WOM-CI-13
@xf(665)
def test_wom_ci_13__negative_quantity_refused(db, s):
    """WOM-CI-13 — a negative quantity never raises stock.
    Rules: _consume_item R4 [BUG-665]."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "-2")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._consume_item(db, o, ln, s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")


# [claude] WOM-CI-15
def test_wom_ci_15__component_logged(db, s):
    """WOM-CI-15 — on a component order the use is logged on the component (revisit after launch).
    Rules: _consume_item R7."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC1.id)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).consumed_at == NOW
    # Then 2
    assert [r.event_type for r in pcacts(db, mk, s.PC1)] == ["work_order_item_used"]


# [claude] WOM-CI-16
@xf(1884)
def test_wom_ci_16__foreign_component_no_entry(db, s):
    """WOM-CI-16 — a component of another workspace gets no entry.
    Rules: _consume_item R7 [BUG-1884]."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC9.id)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).consumed_at == NOW
    # Then 2
    assert _new_count(db, mk, ProjectComponentActivityEvent) == 0


# [claude] WOM-CI-17
def test_wom_ci_17__foreign_component_consumes(db, s):
    """WOM-CI-17 — a component of another workspace does not stop the consumption.
    Rules: _consume_item R7."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC9.id)
    ln = mk_line(db, s, o, s.I1, "3")
    WOM._consume_item(db, o, ln, s.U2.id)
    # Then 1
    row = reread(db, WorkOrderItem, ln.id)
    assert row.consumed_at == NOW
    assert row.total_cost == Decimal("7.50")
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")


# [claude] WOM-RIC-01
def test_wom_ric_01__whole_line_back(db, s):
    """WOM-RIC-01 — the whole line goes back at its unit cost and the line is cleared.
    Rules: _reverse_item_consumption R2, R3; G18."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    WOM._reverse_item_consumption(db, o, ln, s.U2.id)
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("3"), Decimal("2.50"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} voided — Bolt returned"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.consumed_at is None
    assert row.consumed_by is None
    assert row.unit_cost is None
    assert row.total_cost is None
    # Then 5
    assert ev(db, mk, o) == []
    # Then 6
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in led(db, mk, s, s.F1, s.I1, STORAGE))


# [claude] WOM-RIC-02
def test_wom_ric_02__machine_source_returned(db, s):
    """WOM-RIC-02 — a machine source gets its stock back with a "returned" activity.
    Rules: _reverse_item_consumption R2."""
    mk_MS(db, s, s.M2, s.I1, 2, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **{**CONSUMED(s, "12.00"), "unit_cost": Decimal("4.00")},
                 source_location_type="machine", source_location_id=s.M2.id)
    mk = mark(db)
    WOM._reverse_item_consumption(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M2, s.I1) == Decimal("5")
    # Then 2
    assert [t for t, _ in acts(db, mk, s.M2)] == ["consumption_reversed"]
    # Then 3
    assert actrows(db, mk, s.M2)[0].description == f"Returned 3 Bolt — work order {o.work_order_number} voided"


# [claude] WOM-RIC-03
def test_wom_ric_03__not_consumed_skipped(db, s):
    """WOM-RIC-03 — a line not consumed is skipped.
    Rules: _reverse_item_consumption R1."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3")
    bl = snap(db, ln)
    before = counts(db)
    WOM._reverse_item_consumption(db, o, ln, s.U2.id)
    # Then 1
    assert snap(db, ln) == bl
    # Then 2
    assert counts(db) == before


# [claude] WOM-RIC-04
def test_wom_ric_04__no_unit_cost_back_at_zero(db, s):
    """WOM-RIC-04 — a consumed line with no unit cost goes back at 0.
    Rules: _reverse_item_consumption R2."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", consumed_at=T1, consumed_by=s.U1.id, unit_cost=None, total_cost=None)
    mk = mark(db)
    WOM._reverse_item_consumption(db, o, ln, s.U2.id)
    # Then 1
    assert [(r.transaction_type, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("0"))]
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).consumed_at is None


def _adj(db, s, o, ln, old, new):
    return WOM._adjust_consumed_item_quantity(db, o, ln, old_qty=Decimal(old), new_qty=Decimal(new), user_id=s.U2.id)


# [claude] WOM-ADJ-01
def test_wom_adj_01__equal_nothing(db, s):
    """WOM-ADJ-01 — equal quantities do nothing.
    Rules: _adjust_consumed_item_quantity R1."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    bl = snap(db, ln)
    before = counts(db)
    _adj(db, s, o, ln, "3", "3")
    # Then 1
    assert snap(db, ln) == bl
    # Then 2
    assert counts(db) == before


# [claude] WOM-ADJ-02
def test_wom_adj_02__no_inventory_nothing(db, s):
    """WOM-ADJ-02 — a line not using inventory does nothing.
    Rules: _adjust_consumed_item_quantity R1."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", uses_inventory=False)
    bl = snap(db, ln)
    before = counts(db)
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert snap(db, ln) == bl
    # Then 2
    assert counts(db) == before


# [claude] WOM-ADJ-03
def test_wom_adj_03__not_in_progress(db, s):
    """WOM-ADJ-03 — an order not in progress is refused.
    Rules: _adjust_consumed_item_quantity R2."""
    o = mk_order(db, s, "1")
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _adj(db, s, o, ln, "3", "4")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Consumed item quantity can only be adjusted while the work order is in progress"
    # Then 4
    assert counts(db) == before


_POS_WHOLE = "Quantity must be a positive whole number for inventory-tracked consumed lines"


# [claude] WOM-ADJ-04 … WOM-ADJ-06
@pytest.mark.parametrize("line_q,cons,old,new", [
    pytest.param("3", "7.50", "3", "0", id="WOM-ADJ-04"),
    pytest.param("3", "7.50", "3", "3.5", id="WOM-ADJ-05"),
    pytest.param("2.50", "6.25", "2.5", "3", id="WOM-ADJ-06"),
])
def test_wom_adj_04_06__not_positive_whole(db, s, line_q, cons, old, new):
    """WOM-ADJ-04 … WOM-ADJ-06 — a new quantity of 0, a fractional new or old quantity is refused.
    Rules: _adjust_consumed_item_quantity R3."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, line_q, **CONSUMED(s, cons))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _adj(db, s, o, ln, old, new)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == _POS_WHOLE
    # Then 4
    assert counts(db) == before


# [claude] WOM-ADJ-07
def test_wom_adj_07__increase_takes_difference(db, s):
    """WOM-ADJ-07 — an increase takes the difference out and adds it to the total.
    Rules: _adjust_consumed_item_quantity R4, R6; G18."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("6")
    # Then 2
    assert [(r.transaction_type, r.quantity) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [("consumption", Decimal("1"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt qty increased by 1"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("10.00")
    assert row.unit_cost == Decimal("2.50")
    # Then 5
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in led(db, mk, s, s.F1, s.I1, STORAGE))


# [claude] WOM-ADJ-08
def test_wom_adj_08__increase_reaverages(db, s):
    """WOM-ADJ-08 — an increase at a new average cost re-averages the line.
    Rules: _adjust_consumed_item_quantity R6."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).total_cost == Decimal("11.50")
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).unit_cost == Decimal("2.88")


# [claude] WOM-ADJ-09
@xf(1040)
def test_wom_adj_09__reaverage_half_up(db, s):
    """WOM-ADJ-09 — the re-averaged unit cost rounds half up.
    Rules: _adjust_consumed_item_quantity R6 [BUG-1040]."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).total_cost == Decimal("10.50")
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).unit_cost == Decimal("2.63")


# [claude] WOM-ADJ-10
def test_wom_adj_10__total_holds(db, s):
    """WOM-ADJ-10 — the re-averaged total holds whatever the rounding.
    Rules: _adjust_consumed_item_quantity R6."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).total_cost == Decimal("10.50")
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("6")


# [claude] WOM-ADJ-11
def test_wom_adj_11__decrease_returns(db, s):
    """WOM-ADJ-11 — a decrease returns the difference at the line's unit cost.
    Rules: _adjust_consumed_item_quantity R5, R7; G18, G19."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "4", **CONSUMED(s, "10.00"))
    mk = mark(db)
    _adj(db, s, o, ln, "4", "3")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("1"), Decimal("2.50"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt qty reduced by 1"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("7.50")
    assert row.unit_cost == Decimal("2.50")
    # Then 5
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in led(db, mk, s, s.F1, s.I1, STORAGE))


# [claude] WOM-ADJ-12
def test_wom_adj_12__decrease_no_unit_cost(db, s):
    """WOM-ADJ-12 — a decrease with no unit cost leaves no total.
    Rules: _adjust_consumed_item_quantity R7."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "4", consumed_at=T1, consumed_by=s.U1.id, unit_cost=None, total_cost=None)
    _adj(db, s, o, ln, "4", "3")
    # Then 1
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost is None
    assert row.unit_cost is None
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")


# [claude] WOM-ADJ-13
def test_wom_adj_13__machine_activity(db, s):
    """WOM-ADJ-13 — on an order with a machine the adjustment is logged on it.
    Rules: _adjust_consumed_item_quantity R8."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert [t for t, _ in acts(db, mk, s.M1)] == ["work_order_item_qty_adjusted"]
    # Then 2
    a = actrows(db, mk, s.M1)[0]
    assert a.description == f"Adjusted Bolt from 3 to 4 (storage) for work order {o.work_order_number}"
    # Then 3
    assert set(a.metadata_json.keys()) == {"item_id", "item_name", "old_quantity", "new_quantity", "work_order_id"}
    # Then 4
    assert a.metadata_json["work_order_id"] == o.id
    # Then 5
    assert a.metadata_json["old_quantity"] == 3
    assert a.metadata_json["new_quantity"] == 4


# [claude] WOM-ADJ-14
def test_wom_adj_14__no_machine_no_activity(db, s):
    """WOM-ADJ-14 — on an order with no machine no activity is logged.
    Rules: _adjust_consumed_item_quantity R8."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "3", "4")
    # Then 1
    assert reread(db, WorkOrderItem, ln.id).total_cost == Decimal("10.00")
    # Then 2
    assert _new_count(db, mk, MachineActivityEvent) == 0


# [claude] WOM-ADJ-15
@xf(1040)
def test_wom_adj_15__reaverage_0_125_half_up(db, s):
    """WOM-ADJ-15 — re-averaging 0.25 over two units rounds half up to 0.13.
    Rules: _adjust_consumed_item_quantity R6, R6a [BUG-1040]."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("0.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "1", consumed_at=T1, consumed_by=s.U1.id, unit_cost=Decimal("0.25"),
                 total_cost=Decimal("0.25"))
    _adj(db, s, o, ln, "1", "2")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("6")
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).total_cost == Decimal("0.25")
    # Then 3
    assert reread(db, WorkOrderItem, ln.id).unit_cost == Decimal("0.13")


# [claude] WOM-ADJ-16
def test_wom_adj_16__decrease_after_reaverage(db, s):
    """WOM-ADJ-16 — a decrease after a re-averaged increase prices the rest at the line's unit cost.
    Rules: _adjust_consumed_item_quantity R5, R7."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "4", consumed_at=T1, consumed_by=s.U1.id, unit_cost=Decimal("2.88"),
                 total_cost=Decimal("11.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "4", "3")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("1"), Decimal("2.88"))]
    # Then 3
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("8.64")
    assert row.unit_cost == Decimal("2.88")


# [claude] WOM-ADJ-17
def test_wom_adj_17__increase_by_three(db, s):
    """WOM-ADJ-17 — an increase by 3 adds unit cost × 3 and re-averages.
    Rules: _adjust_consumed_item_quantity R4, R6."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "3", "6")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("4")
    # Then 2
    assert [(r.transaction_type, r.quantity) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [("consumption", Decimal("3"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt qty increased by 3"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("19.50")
    assert row.unit_cost == Decimal("3.25")


# [claude] WOM-ADJ-18
def test_wom_adj_18__down_to_one(db, s):
    """WOM-ADJ-18 — adjusting down to 1 is accepted.
    Rules: _adjust_consumed_item_quantity R3, R5, R7; G19."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    _adj(db, s, o, ln, "3", "1")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("8")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("2"), Decimal("2.50"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt qty reduced by 2"
    # Then 4
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("2.50")
    assert row.unit_cost == Decimal("2.50")


# [claude] WOM-ADJ-19
def test_wom_adj_19__no_total_starts_at_zero(db, s):
    """WOM-ADJ-19 — an increase on a line with no total starts from 0.
    Rules: _adjust_consumed_item_quantity R6 ("old total (or 0)")."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", consumed_at=T1, consumed_by=s.U1.id, unit_cost=Decimal("2.50"), total_cost=None)
    _adj(db, s, o, ln, "2", "3")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("6")
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("3.00")
    assert row.unit_cost == Decimal("1.00")


def _machine_line(db, s, o, total):
    """`L = line(O, I1, "3"), but consumed(total), unit_cost 4.00, source machine M2`."""
    return mk_line(db, s, o, s.I1, "3", **{**CONSUMED(s, total), "unit_cost": Decimal("4.00")},
                   source_location_type="machine", source_location_id=s.M2.id)


# [claude] WOM-ADJ-20
def test_wom_adj_20__increase_machine_source(db, s):
    """WOM-ADJ-20 — an increase from a machine source: stock, both activities and their texts.
    Rules: _adjust_consumed_item_quantity R4, R6, R8; G18, G19."""
    mk_MS(db, s, s.M2, s.I1, 5, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = _machine_line(db, s, o, "12.00")
    mk = mark(db)
    _adj(db, s, o, ln, "3", "4")
    num = o.work_order_number
    # Then 1
    assert mqty(db, s, s.M2, s.I1) == Decimal("4")
    # Then 2
    assert [(r.transaction_type, r.quantity) for r in mled(db, mk, s, s.M2, s.I1)] == [("consumption", Decimal("1"))]
    # Then 3
    assert acts(db, mk, s.M2) == [("consumption", f"Additional 1 Bolt consumed for work order {num} (qty adjustment)")]
    # Then 4
    assert acts(db, mk, s.M1) == [
        ("work_order_item_qty_adjusted", f"Adjusted Bolt from 3 to 4 (machine #{s.M2.id}) for work order {num}")]
    # Then 5
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("16.00")
    assert row.unit_cost == Decimal("4.00")
    # Then 6
    assert mled(db, mk, s, s.M2, s.I1)[0].notes == f"{num} — Bolt qty increased by 1"
    # Then 7
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in mled(db, mk, s, s.M2, s.I1))


# [claude] WOM-ADJ-21
def test_wom_adj_21__decrease_machine_source(db, s):
    """WOM-ADJ-21 — a decrease to a machine source: stock back, both activities and their texts.
    Rules: _adjust_consumed_item_quantity R5, R7, R8; G18, G19."""
    mk_MS(db, s, s.M2, s.I1, 1, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = _machine_line(db, s, o, "12.00")
    mk = mark(db)
    _adj(db, s, o, ln, "3", "2")
    num = o.work_order_number
    # Then 1
    assert mqty(db, s, s.M2, s.I1) == Decimal("2")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in mled(db, mk, s, s.M2, s.I1)] == [
        ("consumption_reversal", Decimal("1"), Decimal("4.00"))]
    # Then 3
    assert acts(db, mk, s.M2) == [("consumption_reversed", f"Returned 1 Bolt — work order {num} line qty adjusted")]
    # Then 4
    assert acts(db, mk, s.M1) == [
        ("work_order_item_qty_adjusted", f"Adjusted Bolt from 3 to 2 (machine #{s.M2.id}) for work order {num}")]
    # Then 5
    row = reread(db, WorkOrderItem, ln.id)
    assert row.total_cost == Decimal("8.00")
    assert row.unit_cost == Decimal("4.00")
    # Then 6
    assert mled(db, mk, s, s.M2, s.I1)[0].notes == f"{num} — Bolt qty reduced by 1"
    # Then 7
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in mled(db, mk, s, s.M2, s.I1))


# [claude] WOM-ADJ-22
def test_wom_adj_22__decrease_no_unit_cost_at_zero(db, s):
    """WOM-ADJ-22 — a decrease on a line with no unit cost posts the return at 0.00.
    Rules: _adjust_consumed_item_quantity R5, R7; G18 (fallback cost, ledger source, performer)."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("3.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "4", consumed_at=T1, consumed_by=s.U1.id, unit_cost=None, total_cost=None)
    mk = mark(db)
    _adj(db, s, o, ln, "4", "3")
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("1"), Decimal("0.00"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt qty reduced by 1"
    # Then 4
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in led(db, mk, s, s.F1, s.I1, STORAGE))
    # Then 5
    row = reread(db, WorkOrderItem, ln.id)
    assert row.unit_cost is None
    assert row.total_cost is None


# =========================================================================== #
# _apply_item_completion / _set_machine_status / _previous_machine_status
# =========================================================================== #


# [claude] WOM-AIC-01
def test_wom_aic_01__consume_nothing(db, s):
    """WOM-AIC-01 — a Consume line does nothing at completion.
    Rules: _apply_item_completion R1."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", **CONSUMED(s, "5.00"))
    bl = snap(db, ln)
    before = counts(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert snap(db, ln) == bl
    # Then 2
    assert counts(db) == before


# [claude] WOM-AIC-02 … WOM-AIC-04
@pytest.mark.parametrize("order_cols,line_cols", [
    pytest.param({}, {"action_type": "INSTALL"}, id="WOM-AIC-02"),
    pytest.param({}, {"action_type": "INSTALL", "uses_inventory": False, "consumed_at": T1}, id="WOM-AIC-03"),
    pytest.param({"machine_id": None}, {"action_type": "INSTALL", "consumed": True}, id="WOM-AIC-04"),
])
def test_wom_aic_02_04__install_nothing(db, s, order_cols, line_cols):
    """WOM-AIC-02 … WOM-AIC-04 — an unconsumed Install, an Install off inventory, an Install with no machine do nothing.
    Rules: _apply_item_completion R1."""
    o = _stock_order(db, s, **order_cols)
    cols = dict(line_cols)
    if cols.pop("consumed", False):
        cols.update(CONSUMED(s, "5.00"))
    ln = mk_line(db, s, o, s.I1, "2", **cols)
    before = counts(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert counts(db) == before


# [claude] WOM-AIC-05
def test_wom_aic_05__install_on_machine(db, s):
    """WOM-AIC-05 — Install puts the quantity on the order's machine at the line's cost.
    Rules: _apply_item_completion R2, R9; G18."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **CONSUMED(s, "5.00"))
    mk = mark(db)
    bl = snap(db, ln)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in mled(db, mk, s, s.M1, s.I1)] == [
        ("work_order_install", Decimal("2"), Decimal("2.50"))]
    # Then 3
    assert mled(db, mk, s, s.M1, s.I1)[0].notes == f"{o.work_order_number} — Bolt installed"
    # Then 4
    assert [t for t, _ in acts(db, mk, s.M1)] == ["item_installed"]
    # Then 5
    assert actrows(db, mk, s.M1)[0].description == f"Installed 2 Bolt — work order {o.work_order_number}"
    # Then 6
    assert snap(db, ln) == bl
    # Then 7
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in mled(db, mk, s, s.M1, s.I1))


# [claude] WOM-AIC-06
def test_wom_aic_06__replace_enough(db, s):
    """WOM-AIC-06 — Replace with enough on the machine: old part off, to damaged stock at 0, new part on.
    Rules: _apply_item_completion R3, R4, R6, R7; G18, G19."""
    mk_MS(db, s, s.M1, s.I2, 2, Decimal("300.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="REPLACE", replaced_item_id=s.I2.id, **CONSUMED(s, "5.00"))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M1, s.I2) == Decimal("0")
    # Then 2
    assert [(r.transaction_type, r.quantity) for r in mled(db, mk, s, s.M1, s.I2)] == [
        ("work_order_replace_out", Decimal("2"))]
    # Then 3
    assert qty(db, s, s.F1, s.I2, DAMAGED) == Decimal("2")
    # Then 4
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I2, DAMAGED)] == [
        ("work_order_replace_damaged", Decimal("2"), Decimal("0"))]
    # Then 5
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    # Then 6
    assert [(r.transaction_type, r.unit_cost) for r in mled(db, mk, s, s.M1, s.I1)] == [
        ("work_order_replace_in", Decimal("2.50"))]
    # Then 7
    assert [t for t, _ in acts(db, mk, s.M1)] == ["item_replaced_removed", "item_replaced"]
    # Then 8
    num = o.work_order_number
    assert acts(db, mk, s.M1) == [("item_replaced_removed", f"Removed 2 Bearing (replaced) — work order {num}"),
                                  ("item_replaced", f"Installed 2 Bolt as a replacement — work order {num}")]
    # Then 9
    assert led(db, mk, s, s.F1, s.I2, DAMAGED)[0].notes == f"{num} — Bearing moved to damaged stock"
    # Then 10
    assert mled(db, mk, s, s.M1, s.I2)[0].notes == f"{num} — Bearing removed for replacement"
    # Then 11
    assert mled(db, mk, s, s.M1, s.I1)[0].notes == f"{num} — Bolt installed (replacement)"
    # Then 12
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in mled(db, mk, s, s.M1, s.I2) + led(db, mk, s, s.F1, s.I2, DAMAGED) + mled(db, mk, s, s.M1, s.I1))


# [claude] WOM-AIC-07
def test_wom_aic_07__damaged_joins_at_zero(db, s):
    """WOM-AIC-07 — the removed part joins existing damaged stock at zero value (OQ-59).
    Rules: _apply_item_completion R6."""
    mk_MS(db, s, s.M1, s.I2, 3, Decimal("300.00"))
    mk_SD(db, s, s.F1, s.I2, 1, Decimal("50.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="REPLACE", replaced_item_id=s.I2.id, **CONSUMED(s, "5.00"))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert qty(db, s, s.F1, s.I2, DAMAGED) == Decimal("3")
    # Then 2
    assert [r.unit_cost for r in led(db, mk, s, s.F1, s.I2, DAMAGED)] == [Decimal("0")]
    # Then 3
    assert mqty(db, s, s.M1, s.I2) == Decimal("1")


# [claude] WOM-AIC-08
def test_wom_aic_08__replace_too_little(db, s):
    """WOM-AIC-08 — Replace with too little on the machine installs without removing and logs why.
    Rules: _apply_item_completion R5, R7; G18, G19."""
    mk_MS(db, s, s.M1, s.I2, 1, Decimal("300.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="REPLACE", replaced_item_id=s.I2.id, **CONSUMED(s, "5.00"))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M1, s.I2) == Decimal("1")
    # Then 2
    assert mled(db, mk, s, s.M1, s.I2) == []
    # Then 3
    assert led(db, mk, s, s.F1, s.I2, DAMAGED) == []
    # Then 4
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    # Then 5
    assert [t for t, _ in ev(db, mk, o)] == ["item_replace_degraded"]
    # Then 6
    assert ev(db, mk, o)[0][1] == ("Machine only had 1 of Bearing on hand (needed 2) — installed 2 Bolt without "
                                    "removing anything")
    # Then 7
    assert acts(db, mk, s.M1) == [("item_replaced", f"Installed 2 Bolt as a replacement — work order {o.work_order_number}")]
    # Then 8
    assert [(r.transaction_type, r.quantity, r.unit_cost, r.notes) for r in mled(db, mk, s, s.M1, s.I1)] == [
        ("work_order_replace_in", Decimal("2"), Decimal("2.50"), f"{o.work_order_number} — Bolt installed (replacement)")]
    # Then 9
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in mled(db, mk, s, s.M1, s.I1))


# [claude] WOM-AIC-09
def test_wom_aic_09__replace_no_machine_row(db, s):
    """WOM-AIC-09 — Replace with no machine row counts as 0 on hand.
    Rules: _apply_item_completion R3, R5."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "1", action_type="REPLACE", replaced_item_id=s.I2.id, **CONSUMED(s, "2.50"))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert [t for t, _ in ev(db, mk, o)] == ["item_replace_degraded"]
    # Then 2
    assert mqty(db, s, s.M1, s.I1) == Decimal("1")
    # Then 3
    assert led(db, mk, s, s.F1, s.I2, DAMAGED) == []


# [claude] WOM-AIC-10
def test_wom_aic_10__borrow_storage_returned(db, s):
    """WOM-AIC-10 — Borrow from storage gives the quantity back with a ledger row and no activity.
    Rules: _apply_item_completion R8 (G16); G18, G19."""
    mk_S(db, s, s.F1, s.I1, 8, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="BORROW", **CONSUMED(s, "5.00"))
    mk = mark(db)
    bl = snap(db, ln)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("work_order_borrow_returned", Decimal("2"), Decimal("2.50"))]
    # Then 3
    assert _new_count(db, mk, MachineActivityEvent) == 0
    # Then 4
    assert snap(db, ln) == bl
    # Then 5
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt returned"
    # Then 6
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in led(db, mk, s, s.F1, s.I1, STORAGE))


# [claude] WOM-AIC-11
def test_wom_aic_11__borrow_machine_returned(db, s):
    """WOM-AIC-11 — Borrow from a machine gives the quantity back and logs the activity on that machine.
    Rules: _apply_item_completion R8 (G16); G18, G19."""
    mk_MS(db, s, s.M2, s.I1, 3, Decimal("4.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="BORROW", **{**CONSUMED(s, "8.00"), "unit_cost": Decimal("4.00")},
                 source_location_type="machine", source_location_id=s.M2.id)
    mk = mark(db)
    bl = snap(db, ln)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M2, s.I1) == Decimal("5")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in mled(db, mk, s, s.M2, s.I1)] == [
        ("work_order_borrow_returned", Decimal("2"), Decimal("4.00"))]
    # Then 3
    assert [t for t, _ in acts(db, mk, s.M2)] == ["item_borrowed_returned"]
    # Then 4
    assert actrows(db, mk, s.M2)[0].description == f"Returned 2 Bolt — work order {o.work_order_number}"
    # Then 5
    assert acts(db, mk, s.M1) == []
    # Then 6
    assert snap(db, ln) == bl
    # Then 7
    assert mled(db, mk, s, s.M2, s.I1)[0].notes == f"{o.work_order_number} — Bolt returned"
    # Then 8
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id) for r in mled(db, mk, s, s.M2, s.I1))


# [claude] WOM-AIC-12
def test_wom_aic_12__damaged_to_order_factory(db, s):
    """WOM-AIC-12 — the removed part goes to the damaged stock of the order's factory.
    Rules: _apply_item_completion R4, R6; G18 (damaged stock factory)."""
    fx = _add(db, Factory(workspace_id=s.W1.id, name="Plant Three", abbreviation="P3"))
    mk_MS(db, s, s.M3, s.I2, 2, Decimal("300.00"))
    o = _stock_order(db, s, factory_id=fx.id, machine_id=s.M3.id)
    ln = mk_line(db, s, o, s.I1, "2", action_type="REPLACE", replaced_item_id=s.I2.id, **CONSUMED(s, "5.00"))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, fx, s.I2, DAMAGED)] == [
        ("work_order_replace_damaged", Decimal("2"), Decimal("0.00"))]
    # Then 2
    assert qty(db, s, fx, s.I2, DAMAGED) == Decimal("2")
    # Then 3
    assert led(db, mk, s, s.F1, s.I2, DAMAGED) == []
    assert led(db, mk, s, s.F2, s.I2, DAMAGED) == []
    # Then 4
    assert mqty(db, s, s.M3, s.I2) == Decimal("0")
    assert mqty(db, s, s.M3, s.I1) == Decimal("2")
    # Then 5
    assert led(db, mk, s, fx, s.I2, DAMAGED)[0].notes == f"{o.work_order_number} — Bearing moved to damaged stock"


def _uncosted(s):
    """`consumed_at T1, consumed_by U1.id, unit_cost None, total_cost None`."""
    return {"consumed_at": T1, "consumed_by": s.U1.id, "unit_cost": None, "total_cost": None}


# [claude] WOM-AIC-13
def test_wom_aic_13__install_no_cost(db, s):
    """WOM-AIC-13 — Install with no unit cost posts at 0.00.
    Rules: _apply_item_completion R2; G18 (fallback cost)."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **_uncosted(s))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in mled(db, mk, s, s.M1, s.I1)] == [
        ("work_order_install", Decimal("2"), Decimal("0.00"))]
    # Then 3
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in mled(db, mk, s, s.M1, s.I1))


# [claude] WOM-AIC-14
def test_wom_aic_14__replace_in_no_cost(db, s):
    """WOM-AIC-14 — Replace-in with no unit cost posts at 0.00.
    Rules: _apply_item_completion R4, R6, R7; G18 (fallback cost)."""
    mk_MS(db, s, s.M1, s.I2, 2, Decimal("300.00"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="REPLACE", replaced_item_id=s.I2.id, **_uncosted(s))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in mled(db, mk, s, s.M1, s.I1)] == [
        ("work_order_replace_in", Decimal("2"), Decimal("0.00"))]
    # Then 2
    assert [(r.transaction_type, r.unit_cost) for r in led(db, mk, s, s.F1, s.I2, DAMAGED)] == [
        ("work_order_replace_damaged", Decimal("0.00"))]
    # Then 3
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    assert mqty(db, s, s.M1, s.I2) == Decimal("0")


# [claude] WOM-AIC-15
def test_wom_aic_15__borrow_no_cost(db, s):
    """WOM-AIC-15 — Borrow return with no unit cost posts at 0.00.
    Rules: _apply_item_completion R8; G18 (fallback cost)."""
    mk_S(db, s, s.F1, s.I1, 8, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", action_type="BORROW", **_uncosted(s))
    mk = mark(db)
    WOM._apply_item_completion(db, o, ln, s.U2.id)
    # Then 1
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 2
    assert [(r.transaction_type, r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("work_order_borrow_returned", Decimal("2"), Decimal("0.00"))]
    # Then 3
    assert led(db, mk, s, s.F1, s.I1, STORAGE)[0].notes == f"{o.work_order_number} — Bolt returned"


def _status_rows(db, mk, m):
    return [a for a in actrows(db, mk, m) if a.event_type == "status_updated"]


# [claude] WOM-SMS-01
def test_wom_sms_01__new_status_event(db, s):
    """WOM-SMS-01 — a new status writes one status event with the order's note and id.
    Rules: _set_machine_status R1, R3, R4, R5; G18."""
    o = mk_order(db, s, "1")
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = WOM._set_machine_status(db, s.M1.id, s.W1.id, s.U2.id, MachineEventTypeEnum.MAINTENANCE,
                                     work_order_number="WO-77", work_order_id=o.id)
    # Then 1
    assert result == "RUNNING"
    # Then 2
    assert stat(db, mk, s.M1) == ["MAINTENANCE"]
    # Then 3
    a = _status_rows(db, mk, s.M1)[0]
    assert a.metadata_json["note"] == "Work order WO-77"
    assert a.metadata_json["work_order_id"] == o.id
    assert a.description == "Status set to maintenance (Work order WO-77)"
    # Then 4
    assert type(result) is str
    # Then 5
    assert a.performed_by == s.U2.id


# [claude] WOM-SMS-02
def test_wom_sms_02__same_status_nothing(db, s):
    """WOM-SMS-02 — the same status does nothing.
    Rules: _set_machine_status R2, R5."""
    mk_status_row(db, s, s.M1, "MAINTENANCE", T0)
    before = counts(db)
    result = WOM._set_machine_status(db, s.M1.id, s.W1.id, s.U2.id, MachineEventTypeEnum.MAINTENANCE,
                                     work_order_number="WO-77")
    # Then 1
    assert result == "MAINTENANCE"
    # Then 2
    assert counts(db) == before
    # Then 3
    assert type(result) is str


# [claude] WOM-SMS-03
def test_wom_sms_03__no_status_before(db, s):
    """WOM-SMS-03 — no status before: one event, returns None; no number gives no note.
    Rules: _set_machine_status R3, R4."""
    mk = mark(db)
    result = WOM._set_machine_status(db, s.M1.id, s.W1.id, s.U2.id, MachineEventTypeEnum.IDLE)
    # Then 1
    assert result is None
    # Then 2
    assert stat(db, mk, s.M1) == ["IDLE"]
    # Then 3
    a = _status_rows(db, mk, s.M1)[0]
    assert a.description == "Status set to idle"
    assert a.metadata_json["note"] is None
    assert "work_order_id" not in a.metadata_json


# [claude] WOM-SMS-04
def test_wom_sms_04__deleted_machine(db, s):
    """WOM-SMS-04 — a deleted machine is refused.
    Rules: _set_machine_status R3."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._set_machine_status(db, md.id, s.W1.id, s.U2.id, MachineEventTypeEnum.MAINTENANCE)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SMS-05
def test_wom_sms_05__machine_of_w2(db, s):
    """WOM-SMS-05 — a machine of W2 is not found.
    Rules: _set_machine_status R3."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._set_machine_status(db, s.M9.id, s.W1.id, s.U2.id, MachineEventTypeEnum.MAINTENANCE)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SMS-06
@xf(1000)
def test_wom_sms_06__not_live_order_refused(db, s):
    """WOM-SMS-06 — a work order id that is not a live order of the workspace is refused.
    Rules: _set_machine_status R3 [BUG-1000]."""
    o = mk_order(db, s, "1", **GONE(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._set_machine_status(db, s.M1.id, s.W1.id, s.U2.id, MachineEventTypeEnum.MAINTENANCE,
                                work_order_number=o.work_order_number, work_order_id=o.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-PMS-01
def test_wom_pms_01__newest_started_decides(db, s):
    """WOM-PMS-01 — the newest started event decides; other event types are ignored.
    Rules: _previous_machine_status R1."""
    o = _stock_order(db, s)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T0)
    mk_event(db, s, o, "started", {"previous_machine_status": "IDLE"}, T1)
    mk_event(db, s, o, "note", {"previous_machine_status": "OFF"}, NOW)
    result = WOM._previous_machine_status(db, o)
    # Then 1
    assert result == "IDLE"


# [claude] WOM-PMS-02
def test_wom_pms_02__no_started_event(db, s):
    """WOM-PMS-02 — no started event gives None.
    Rules: _previous_machine_status R1."""
    o = _stock_order(db, s)
    mk_event(db, s, o, "note", {"previous_machine_status": "OFF"}, T1)
    result = WOM._previous_machine_status(db, o)
    # Then 1
    assert result is None


# [claude] WOM-PMS-03
def test_wom_pms_03__started_without_key(db, s):
    """WOM-PMS-03 — a started event without the key gives None.
    Rules: _previous_machine_status R1."""
    o = _stock_order(db, s)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T0)
    mk_event(db, s, o, "started", {"items_consumed": 0}, T1)
    result = WOM._previous_machine_status(db, o)
    # Then 1
    assert result is None


# =========================================================================== #
# start_work_order and its helpers
# =========================================================================== #


def _start(db, s, o):
    return WOM.start_work_order(db, o.id, s.W1.id, s.U2.id)


def _start_given(db, s, with_line=True):
    """ST-01 … ST-03: S(F1, I1, 10, 2.50); O stamped; status row(M1, RUNNING, T0); L = line(O, I1, "3")."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    ln = mk_line(db, s, o, s.I1, "3") if with_line else None
    return o, ln


# [claude] WOM-ST-01
def test_wom_st_01__consumes_and_in_progress(db, s):
    """WOM-ST-01 — start consumes the lines and moves the order in progress.
    Rules: start_work_order R1, R4, R6; _run_start_side_effects R1."""
    o, ln = _start_given(db, s)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.status == "IN_PROGRESS"
    assert row.started_by == s.U2.id
    assert row.started_at == NOW
    assert row.planned_date == D(12)
    # Then 3
    rl = reread(db, WorkOrderItem, ln.id)
    assert rl.consumed_at == NOW
    assert rl.unit_cost == Decimal("2.50")
    assert rl.total_cost == Decimal("7.50")
    # Then 4
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")


# [claude] WOM-ST-02
def test_wom_st_02__machine_maintenance(db, s):
    """WOM-ST-02 — start puts the machine into maintenance for this order.
    Rules: start_work_order R5; _run_start_side_effects R2."""
    o, _ = _start_given(db, s)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["MAINTENANCE"]
    # Then 3
    a = _status_rows(db, mk, s.M1)[0]
    assert a.metadata_json["work_order_id"] == o.id
    assert a.metadata_json["note"] == f"Work order {o.work_order_number}"


# [claude] WOM-ST-03
def test_wom_st_03__started_event_metadata(db, s):
    """WOM-ST-03 — the started event carries the count, the status before, the schedule and the workers.
    Rules: start_work_order R7."""
    o, _ = _start_given(db, s)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("started", "Work started — 1 item(s) consumed")]
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json == {
        "items_consumed": 1, "previous_machine_status": "RUNNING", "started_at": "2026-03-10T09:00:00",
        "planned_date": "2026-03-12", "variance_days": -2, "variance_label": "2 days early", "assigned_to": None,
        "assignee_user_ids": [], "started_by_user_id": s.U2.id}


# [claude] WOM-ST-04
def test_wom_st_04__no_lines(db, s):
    """WOM-ST-04 — with no lines the event says so.
    Rules: start_work_order R7."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("started", "Work started — no inventory items to consume")]
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json["items_consumed"] == 0


# [claude] WOM-ST-05
def test_wom_st_05__empty_planned_date_today(db, s):
    """WOM-ST-05 — an empty planned date becomes today.
    Rules: start_work_order R6, R7."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=None)
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).planned_date == D(10)
    # Then 3
    meta = evrow(db, mk, o, "started").metadata_json
    assert meta["planned_date"] == "2026-03-10"
    assert meta["variance_label"] == "On plan"


# [claude] WOM-ST-06
def test_wom_st_06__in_progress_again(db, s):
    """WOM-ST-06 — an order in progress cannot be started again.
    Rules: start_work_order R2."""
    o = mk_order(db, s, "1", **STARTED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order must be in draft to be started"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-ST-07
def test_wom_st_07__voided(db, s):
    """WOM-ST-07 — a voided order cannot be started.
    Rules: start_work_order R2."""
    o = mk_order(db, s, "1", **VOIDED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order must be in draft to be started"
    # Then 4
    assert counts(db) == before


# [claude] WOM-ST-08
def test_wom_st_08__unmet_approvals(db, s):
    """WOM-ST-08 — unmet approvals block the start.
    Rules: start_work_order R3."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    mk_line(db, s, o, s.I1, "3")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Assigned approvers must approve before work can start"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-ST-09
def test_wom_st_09__zero_required_waives(db, s):
    """WOM-ST-09 — zero required approvals waives an unapproved approver.
    Rules: start_work_order R3; approval_summary R3."""
    o = mk_order(db, s, "1", **STAMPED(s), required_approvals=0)
    mk_approver(db, s, o, s.U2)
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).status == "IN_PROGRESS"


# [claude] WOM-ST-10
def test_wom_st_10__only_live_pending_consumed(db, s):
    """WOM-ST-10 — only live, pending inventory lines are consumed.
    Rules: start_work_order R4; _run_start_side_effects R1."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    mk_S(db, s, s.F1, s.I3, 10, Decimal("1.00"))
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    lp = mk_line(db, s, o, s.I1, "3")
    lg = mk_line(db, s, o, s.I2, "1", **LINE_GONE(s))
    lnn = mk_line(db, s, o, s.I3, "1", uses_inventory=False)
    lc = mk_line(db, s, o, s.I2, "2", **CONSUMED(s, "5.00"))
    mk = mark(db)
    bg, bn, bc = snap(db, lg), snap(db, lnn), snap(db, lc)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert evrow(db, mk, o, "started").metadata_json["items_consumed"] == 1
    # Then 3
    assert reread(db, WorkOrderItem, lp.id).consumed_at == NOW
    # Then 4
    assert snap(db, lg) == bg
    # Then 5
    assert snap(db, lnn) == bn
    # Then 6
    assert snap(db, lc) == bc
    # Then 7
    assert qty(db, s, s.F1, s.I3, STORAGE) == Decimal("10")


# [claude] WOM-ST-11
def test_wom_st_11__line_cannot_be_consumed(db, s):
    """WOM-ST-11 — a line that cannot be consumed stops the start.
    Rules: start_work_order R4."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    mk_S(db, s, s.F1, s.I2, 2, Decimal("5.00"))
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk_line(db, s, o, s.I1, "3")
    mk_line(db, s, o, s.I2, "5")
    mk = mark(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Insufficient stock (2 available, 5 requested)"
    # Then 4
    assert ev(db, mk, o) == []


# [claude] WOM-ST-12
def test_wom_st_12__fractional_line(db, s):
    """WOM-ST-12 — a fractional stock line stops the start.
    Rules: start_work_order R4; _consume_item R3."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    ln = mk_line(db, s, o, s.I1, "2.50")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} has a fractional quantity; inventory consumption requires whole units"


# [claude] WOM-ST-13
def test_wom_st_13__already_maintenance(db, s):
    """WOM-ST-13 — a machine already in maintenance gets no new status event.
    Rules: start_work_order R5; _set_machine_status R2."""
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "MAINTENANCE", T0)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == []
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json["previous_machine_status"] == "MAINTENANCE"


# [claude] WOM-ST-14
def test_wom_st_14__no_machine_no_status(db, s):
    """WOM-ST-14 — an order with no machine changes no machine status.
    Rules: start_work_order R5; _run_start_side_effects R2."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert _new_count(db, mk, MachineActivityEvent) == 0
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json["previous_machine_status"] is None


# [claude] WOM-ST-15
def test_wom_st_15__deleted_machine(db, s):
    """WOM-ST-15 — an order on a deleted machine cannot be started.
    Rules: start_work_order R5; _set_machine_status R3 (machine O5)."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=md.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create event for a deleted machine"


# [claude] WOM-ST-16
def test_wom_st_16__assigned_workers_in_event(db, s):
    """WOM-ST-16 — the assigned workers go into the started event.
    Rules: start_work_order R7; _started_worker_metadata R1."""
    o = mk_order(db, s, "1", **STAMPED(s), assigned_to="Sara Khan")
    mk_assignee(db, s, o, s.U3)
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert evrow(db, mk, o, "started").metadata_json["assigned_to"] == "Sara Khan"
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json["assignee_user_ids"] == [s.U3.id]


# [claude] WOM-ST-17
@xf(1279)
def test_wom_st_17__deleted_order_not_found(db, s):
    """WOM-ST-17 — a soft-deleted order is not found.
    Rules: start_work_order R1; get_work_order R2 [BUG-1279]."""
    o = mk_order(db, s, "1", **STAMPED(s), **GONE(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _start(db, s, o)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-ST-18
@xf(2916)
def test_wom_st_18__order_row_locked(db, s):
    """WOM-ST-18 — the order row is locked before its state is checked.
    Rules: start_work_order R9 [BUG-2916]."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    db.expunge_all()
    with Recorder(db) as rec:
        result = _start(db, s, o)
    # Then 1
    assert result.status == "IN_PROGRESS"
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-ST-19
@xf(1884)
def test_wom_st_19__foreign_component_no_entry(db, s):
    """WOM-ST-19 — a component of another workspace gets no entry at start.
    Rules: start_work_order R8 [BUG-1884]."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None, project_component_id=s.PC9.id)
    mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.status == "IN_PROGRESS"
    # Then 2
    assert _new_count(db, mk, ProjectComponentActivityEvent) == 0


# [claude] WOM-ST-20
def test_wom_st_20__foreign_component_starts(db, s):
    """WOM-ST-20 — a component of another workspace does not stop the start.
    Rules: start_work_order R8."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None, project_component_id=s.PC9.id)
    mk_line(db, s, o, s.I1, "3")
    result = _start(db, s, o)
    # Then 1
    assert result.status == "IN_PROGRESS"
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")


# [claude] WOM-ST-21
def test_wom_st_21__flushes_never_commits(db, s):
    """WOM-ST-21 — start flushes and never commits.
    Rules: start_work_order R6."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _start(db, s, o)
        # Then 1
        assert result.status == "IN_PROGRESS"
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).status == "DRAFT"


# [claude] WOM-ST-22
def test_wom_st_22__starter_is_performer(db, s):
    """WOM-ST-22 — the starter is the performer of the event, the status change and the consumption.
    Rules: start_work_order R4, R5, R7; G18 (performer, ledger source)."""
    o, _ = _start_given(db, s)
    mk = mark(db)
    result = _start(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert evrow(db, mk, o, "started").performed_by == s.U2.id
    # Then 3
    assert [a.performed_by for a in _status_rows(db, mk, s.M1)] == [s.U2.id]
    # Then 4
    assert [(r.transaction_type, r.quantity) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [("consumption", Decimal("3"))]
    # Then 5
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in led(db, mk, s, s.F1, s.I1, STORAGE))


# [claude] WOM-PN-01
def test_wom_pn_01__noon_naive():
    """WOM-PN-01 — noon of the date, naive.
    Rules: _planned_date_noon_utc R1."""
    result = WOM._planned_date_noon_utc(D(8))
    # Then 1
    assert result == NOON(8)
    # Then 2
    assert result.tzinfo is None


# [claude] WOM-RSE-01
def test_wom_rse_01__count_and_status_before(db, s):
    """WOM-RSE-01 — returns the count of lines consumed and the machine's status before.
    Rules: _run_start_side_effects R1, R2, R3."""
    o, _ = _start_given(db, s)
    mk = mark(db)
    result = WOM._run_start_side_effects(db, o, s.W1.id, s.U2.id)
    # Then 1
    assert result == (1, "RUNNING")
    # Then 2
    assert type(result[0]) is int
    assert type(result[1]) is str
    # Then 3
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 4
    assert stat(db, mk, s.M1) == ["MAINTENANCE"]
    # Then 5
    assert reread(db, WorkOrder, o.id).status == "DRAFT"


# [claude] WOM-RSE-02
def test_wom_rse_02__nothing(db, s):
    """WOM-RSE-02 — no lines and no machine give (0, None).
    Rules: _run_start_side_effects R1, R2, R3."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    before = counts(db)
    result = WOM._run_start_side_effects(db, o, s.W1.id, s.U2.id)
    # Then 1
    assert result == (0, None)
    # Then 2
    assert counts(db) == before


# [claude] WOM-EAM-01
def test_wom_eam_01__active_member_passes(db, s):
    """WOM-EAM-01 — an active member passes.
    Rules: _ensure_active_workspace_member R1."""
    result = WOM._ensure_active_workspace_member(db, s.W1.id, s.U2.id)
    # Then 1
    assert result is None


# [claude] WOM-EAM-02, WOM-EAM-03
@pytest.mark.parametrize("who", [pytest.param("U4", id="WOM-EAM-02"), pytest.param("U5", id="WOM-EAM-03")])
def test_wom_eam_02_03__not_active_member(db, s, who):
    """WOM-EAM-02 / WOM-EAM-03 — a suspended member, and an active member of W0 and W2 only, are refused in W1.
    Rules: _ensure_active_workspace_member R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._ensure_active_workspace_member(db, s.W1.id, getattr(s, who).id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"


# [claude] WOM-SAT-01
def test_wom_sat_01__matched_names_rows(db, s):
    """WOM-SAT-01 — matched names become the assignee rows.
    Rules: _sync_assignees_from_text R1."""
    o = mk_order(db, s, "1")
    mk_assignee(db, s, o, s.U3)
    result = WOM._sync_assignees_from_text(db, o, "rahim uddin, Ghost")
    # Then 1
    assert result == [s.U2.id]
    # Then 2
    assert [a.user_id for a in rows_of(db, WorkOrderAssignee, work_order_id=o.id)] == [s.U2.id]


# [claude] WOM-SAT-02
def test_wom_sat_02__no_text_removes(db, s):
    """WOM-SAT-02 — no text removes every assignee row.
    Rules: _sync_assignees_from_text R1."""
    o = mk_order(db, s, "1")
    mk_assignee(db, s, o, s.U3)
    result = WOM._sync_assignees_from_text(db, o, None)
    # Then 1
    assert result == []
    # Then 2
    assert len(rows_of(db, WorkOrderAssignee, work_order_id=o.id)) == 0


# [claude] WOM-SAT-03
def test_wom_sat_03__nobody_matched(db, s):
    """WOM-SAT-03 — blank text, a suspended member and a member of other workspaces match nobody.
    Rules: _sync_assignees_from_text R1."""
    o = mk_order(db, s, "1")
    p = mk_order(db, s, "2")
    result = (WOM._sync_assignees_from_text(db, o, "   "), WOM._sync_assignees_from_text(db, p, "Omar Faruk, Nadia Islam"))
    # Then 1
    assert result == ([], [])
    # Then 2
    db.expire_all()
    assert db.execute(select(func.count()).select_from(WorkOrderAssignee).where(
        WorkOrderAssignee.work_order_id.in_([o.id, p.id]))).scalar_one() == 0


# =========================================================================== #
# _resolve_completion_workers / complete_as_planned
# =========================================================================== #


def _rcw(db, s, performer, **k):
    return WOM._resolve_completion_workers(db, s.W1.id, performer.id, **k)


# [claude] WOM-RCW-01
def test_wom_rcw_01__ids_give_names(db, s):
    """WOM-RCW-01 — ids give their display names, in the order given.
    Rules: _resolve_completion_workers R1, R2."""
    result = _rcw(db, s, s.U1, completed_by_user_ids=[s.U3.id, s.U2.id])
    # Then 1
    assert result == ("Sara Khan, Rahim Uddin", [s.U3.id, s.U2.id])


# [claude] WOM-RCW-02
def test_wom_rcw_02__names_with_ids_trimmed(db, s):
    """WOM-RCW-02 — names given with ids are used trimmed.
    Rules: _resolve_completion_workers R2."""
    result = _rcw(db, s, s.U1, completed_by_user_ids=[s.U3.id], completed_by_names="  Team A  ")
    # Then 1
    assert result == ("Team A", [s.U3.id])


# [claude] WOM-RCW-03
def test_wom_rcw_03__empty_list_single_id(db, s):
    """WOM-RCW-03 — an empty id list falls back to the single id.
    Rules: _resolve_completion_workers R1."""
    result = _rcw(db, s, s.U1, completed_by_user_ids=[], completed_by_user_id=s.U3.id)
    # Then 1
    assert result == ("Sara Khan", [s.U3.id])


# [claude] WOM-RCW-04
def test_wom_rcw_04__inactive_id_refused(db, s):
    """WOM-RCW-04 — an id that is not an active member is refused.
    Rules: _resolve_completion_workers R2."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _rcw(db, s, s.U1, completed_by_user_ids=[s.U2.id, s.U4.id])
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"


# [claude] WOM-RCW-05
def test_wom_rcw_05__repeated_id_kept(db, s):
    """WOM-RCW-05 — a repeated id keeps its repeats in the ids.
    Rules: _resolve_completion_workers R2."""
    result = _rcw(db, s, s.U1, completed_by_user_ids=[s.U2.id, s.U2.id])
    # Then 1
    assert result[1] == [s.U2.id, s.U2.id]


# [claude] WOM-RCW-06
@xf(381)
def test_wom_rcw_06__repeated_id_name_once(db, s):
    """WOM-RCW-06 — a repeated id shows its name once.
    Rules: _resolve_completion_workers R2 [BUG-381]."""
    result = _rcw(db, s, s.U1, completed_by_user_ids=[s.U2.id, s.U2.id])
    # Then 1
    assert result[1] == [s.U2.id, s.U2.id]
    # Then 2
    assert result[0] == "Rahim Uddin"


# [claude] WOM-RCW-07
def test_wom_rcw_07__names_matched(db, s):
    """WOM-RCW-07 — names alone are matched to active members.
    Rules: _resolve_completion_workers R3."""
    result = _rcw(db, s, s.U1, completed_by_names="sara khan, Ghost")
    # Then 1
    assert result == ("Sara Khan, Ghost", [s.U3.id])


# [claude] WOM-RCW-08
def test_wom_rcw_08__names_match_nobody(db, s):
    """WOM-RCW-08 — names that match nobody give no ids.
    Rules: _resolve_completion_workers R3."""
    result = _rcw(db, s, s.U1, completed_by_names="Ghost")
    # Then 1
    assert result == ("Ghost", [])


# [claude] WOM-RCW-09
def test_wom_rcw_09__performer_did_it(db, s):
    """WOM-RCW-09 — neither ids nor names: the performer did the work.
    Rules: _resolve_completion_workers R4."""
    result = _rcw(db, s, s.U1, completed_by_names="   ")
    # Then 1
    assert result == ("Karim Ahmed", [s.U1.id])


# [claude] WOM-RCW-10
def test_wom_rcw_10__inactive_performer(db, s):
    """WOM-RCW-10 — a performer who is not an active member is refused.
    Rules: _resolve_completion_workers R4."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _rcw(db, s, s.U4)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"


# [claude] WOM-RCW-11
def test_wom_rcw_11__empty_name_user_hash(db, s):
    """WOM-RCW-11 — a performer whose profile name is empty shows as "User #<id>".
    Rules: _resolve_completion_workers R4, R4a."""
    ue = make_profile(db, name="")
    _add(db, WorkspaceMember(workspace_id=s.W1.id, user_id=ue.id, role="member", status="active", position=None))
    result = _rcw(db, s, ue)
    # Then 1
    assert result == (f"User #{ue.id}", [ue.id])


def _cap(db, s, o, **k):
    return WOM.complete_as_planned(db, o.id, s.W1.id, s.U2.id, **k)


# [claude] WOM-CAP-01
def test_wom_cap_01__started_and_completed_at_noon(db, s):
    """WOM-CAP-01 — a draft is started and completed at noon of its planned date.
    Rules: complete_as_planned R6, R7, R9, R10."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    result = _cap(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.status == "COMPLETED"
    assert row.started_by == s.U2.id
    assert row.started_at == NOON(8)
    assert row.completed_at == NOON(8)
    # Then 3
    assert row.completed_by == s.U2.id
    assert row.completed_by_names == "Rahim Uddin"
    # Then 4
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 5
    assert stat(db, mk, s.M1) == ["MAINTENANCE", "RUNNING"]


# [claude] WOM-CAP-02
def test_wom_cap_02__events_carry_mode(db, s):
    """WOM-CAP-02 — the started and completed events carry the planned mode.
    Rules: complete_as_planned R8, R9."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    result = _cap(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [t for t, _ in ev(db, mk, o)] == ["started", "completed"]
    # Then 3
    assert evrow(db, mk, o, "started").metadata_json == {
        "items_consumed": 1, "previous_machine_status": "RUNNING", "started_at": "2026-03-08T12:00:00",
        "planned_date": "2026-03-08", "variance_days": 0, "variance_label": "On plan", "assigned_to": None,
        "assignee_user_ids": [], "started_by_user_id": s.U2.id, "completion_mode": "complete_as_planned"}
    # Then 4
    assert evrow(db, mk, o, "completed").metadata_json == {
        "completed_at": "2026-03-08T12:00:00", "planned_date": "2026-03-08", "variance_days": 0,
        "variance_label": "On plan", "completion_mode": "complete_as_planned", "completed_by_names": "Rahim Uddin",
        "completed_by_name": "Rahim Uddin", "completed_by_user_ids": [s.U2.id], "completed_by": s.U2.id}
    # Then 5
    assert evrow(db, mk, o, "started").description == "Work started — 1 item(s) consumed"


# [claude] WOM-CAP-03
def test_wom_cap_03__borrow_out_and_back(db, s):
    """WOM-CAP-03 — a Borrow line leaves and comes back in the same call.
    Rules: complete_as_planned R6, R9; _apply_item_completion R8."""
    mk_S(db, s, s.F1, s.I3, 5, Decimal("1.00"))
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk_line(db, s, o, s.I3, "1", action_type="BORROW")
    mk = mark(db)
    result = _cap(db, s, o)
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert [r.transaction_type for r in led(db, mk, s, s.F1, s.I3, STORAGE)] == ["consumption", "work_order_borrow_returned"]
    # Then 3
    assert qty(db, s, s.F1, s.I3, STORAGE) == Decimal("5")


# [claude] WOM-CAP-04
def test_wom_cap_04__today_allowed(db, s):
    """WOM-CAP-04 — a planned date of today is allowed.
    Rules: complete_as_planned R3."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(10), machine_id=None)
    result = _cap(db, s, o)
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert reread(db, WorkOrder, o.id).completed_at == NOON(10)


# [claude] WOM-CAP-05
def test_wom_cap_05__tomorrow_refused(db, s):
    """WOM-CAP-05 — a planned date tomorrow is refused.
    Rules: complete_as_planned R3."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(11))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cap(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Complete as planned is only allowed when the planned date is today or in the past"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-CAP-06 … WOM-CAP-08
@pytest.mark.parametrize("cols,approver,detail", [
    pytest.param("started", False, "Work order must be in draft to complete as planned", id="WOM-CAP-06"),
    pytest.param("no_date", False, "Work order must have a planned date", id="WOM-CAP-07"),
    pytest.param("d8", True, "Assigned approvers must approve before work can be completed", id="WOM-CAP-08"),
])
def test_wom_cap_06_08__refused(db, s, cols, approver, detail):
    """WOM-CAP-06 … WOM-CAP-08 — not a draft, no planned date, unmet approvals are refused.
    Rules: complete_as_planned R1, R2, R4."""
    k = {"started": STARTED(s), "no_date": {**STAMPED(s), "planned_date": None}, "d8": {"planned_date": D(8)}}[cols]
    o = mk_order(db, s, "1", **k)
    if approver:
        mk_approver(db, s, o, s.U2)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cap(db, s, o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert counts(db) == before


# [claude] WOM-CAP-09 … WOM-CAP-11
@pytest.mark.parametrize("cols,approver,detail", [
    pytest.param("started_no_date", False, "Work order must be in draft to complete as planned", id="WOM-CAP-09"),
    pytest.param("no_date", True, "Work order must have a planned date", id="WOM-CAP-10"),
    pytest.param("d11", True, "Complete as planned is only allowed when the planned date is today or in the past",
                 id="WOM-CAP-11"),
])
def test_wom_cap_09_11__check_order(db, s, cols, approver, detail):
    """WOM-CAP-09 … WOM-CAP-11 — status before date, missing date before approvals, future date before approvals.
    Rules: complete_as_planned R5."""
    k = {"started_no_date": {**STARTED(s), "planned_date": None}, "no_date": {"planned_date": None},
         "d11": {"planned_date": D(11)}}[cols]
    o = mk_order(db, s, "1", **k)
    if approver:
        mk_approver(db, s, o, s.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _cap(db, s, o)
    # Then 2
    assert exc.value.detail == detail


# [claude] WOM-CAP-12
def test_wom_cap_12__options_passed(db, s):
    """WOM-CAP-12 — notes, machine status and workers are passed to the completion.
    Rules: complete_as_planned R9."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = _cap(db, s, o, completion_notes="Done", machine_status=MachineEventTypeEnum.IDLE,
                  completed_by_user_ids=[s.U3.id])
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.completion_notes == "Done"
    assert row.completed_by == s.U3.id
    assert row.completed_by_names == "Sara Khan"
    # Then 3
    assert stat(db, mk, s.M1) == ["MAINTENANCE", "IDLE"]
    # Then 4
    assert evrow(db, mk, o, "completed").metadata_json["recorded_by"] == s.U2.id


# [claude] WOM-CAP-13
@xf(2916)
def test_wom_cap_13__order_row_locked(db, s):
    """WOM-CAP-13 — the order row is locked before its state is checked.
    Rules: complete_as_planned R11 [BUG-2916]."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8), machine_id=None)
    db.expunge_all()
    with Recorder(db) as rec:
        result = _cap(db, s, o)
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-CAP-14
def test_wom_cap_14__flushes_never_commits(db, s):
    """WOM-CAP-14 — complete as planned flushes and never commits.
    Rules: complete_as_planned R10."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8), machine_id=None)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _cap(db, s, o)
        # Then 1
        assert result.status == "COMPLETED"
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).status == "DRAFT"


# [claude] WOM-CAP-15
def test_wom_cap_15__no_lines_started_text(db, s):
    """WOM-CAP-15 — with no stock lines the started event says nothing was consumed.
    Rules: complete_as_planned R8; start_work_order R7."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8), machine_id=None)
    mk = mark(db)
    result = _cap(db, s, o)
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert [t for t, _ in ev(db, mk, o)] == ["started", "completed"]
    # Then 3
    assert evrow(db, mk, o, "started").description == "Work started — no inventory items to consume"
    # Then 4
    assert evrow(db, mk, o, "started").metadata_json["items_consumed"] == 0


# [claude] WOM-CAP-16
def test_wom_cap_16__caller_is_performer(db, s):
    """WOM-CAP-16 — the caller is the performer of both events and the machine entries, not the worker.
    Rules: complete_as_planned R8, R9; finalize_completion R6, R7, R9; G18 (performer)."""
    o = mk_order(db, s, "1", **STAMPED(s), planned_date=D(8))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk = mark(db)
    result = _cap(db, s, o, completed_by_user_ids=[s.U3.id])
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert evrow(db, mk, o, "started").performed_by == s.U2.id
    assert evrow(db, mk, o, "completed").performed_by == s.U2.id
    # Then 3
    assert evrow(db, mk, o, "completed").metadata_json["recorded_by"] == s.U2.id
    # Then 4
    rows = actrows(db, mk, s.M1)
    assert sorted(a.event_type for a in rows) == ["status_updated", "status_updated", "work_order_completed"]
    assert all(a.performed_by == s.U2.id for a in rows)


# =========================================================================== #
# finalize_completion / void_work_order
# =========================================================================== #


def _fin_given(db, s):
    """FC-01 … FC-03: O started; status rows RUNNING@T0, MAINTENANCE@T1; started event (RUNNING)."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T1)
    return o


# [claude] WOM-FC-01
def test_wom_fc_01__completed_by_performer(db, s):
    """WOM-FC-01 — the order is completed by the performer and the completer rows are written.
    Rules: finalize_completion R2, R3, R4, R11; _resolve_completion_workers R4."""
    o = _fin_given(db, s)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.status == "COMPLETED"
    assert row.completed_by == s.U2.id
    assert row.completed_by_names == "Rahim Uddin"
    assert row.completed_at == NOW
    assert row.completion_notes is None
    # Then 3
    assert [c.user_id for c in rows_of(db, WorkOrderCompleter, work_order_id=o.id)] == [s.U2.id]


# [claude] WOM-FC-02
def test_wom_fc_02__completed_event(db, s):
    """WOM-FC-02 — the completed event carries schedule and workers.
    Rules: finalize_completion R9."""
    o = _fin_given(db, s)
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert ev(db, mk, o) == [("completed", f"Work order {o.work_order_number} marked complete")]
    # Then 3
    assert evrow(db, mk, o, "completed").metadata_json == {
        "completed_at": "2026-03-10T09:00:00", "planned_date": "2026-03-01", "variance_days": 9,
        "variance_label": "9 days late", "completed_by_names": "Rahim Uddin", "completed_by_name": "Rahim Uddin",
        "completed_by_user_ids": [s.U2.id], "completed_by": s.U2.id}


# [claude] WOM-FC-03
def test_wom_fc_03__machine_returns(db, s):
    """WOM-FC-03 — the machine returns to its status before start and logs the completion.
    Rules: finalize_completion R6, R7 (Q9)."""
    o = _fin_given(db, s)
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["RUNNING"]
    # Then 3
    assert ("work_order_completed", f"Work order completed: {o.work_order_number} — Service — Lathe 3") in acts(db, mk, s.M1)
    # Then 4
    assert next(a for a in actrows(db, mk, s.M1) if a.event_type == "work_order_completed").metadata_json == {
        "work_order_id": o.id}


# [claude] WOM-FC-04
def test_wom_fc_04__recorded_by(db, s):
    """WOM-FC-04 — someone else did the work: recorded_by is the performer.
    Rules: finalize_completion R3, R9."""
    o = _stock_order(db, s, machine_id=None)
    mk = mark(db)
    result = FIN(db, s, o, completed_by_user_ids=[s.U3.id])
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.completed_by == s.U3.id
    assert row.completed_by_names == "Sara Khan"
    # Then 3
    assert evrow(db, mk, o, "completed").metadata_json["recorded_by"] == s.U2.id
    # Then 4
    assert "completed_by" not in evrow(db, mk, o, "completed").metadata_json


# [claude] WOM-FC-05
def test_wom_fc_05__no_matched_completer(db, s):
    """WOM-FC-05 — no matched completer: no completed_by, neither key in the event.
    Rules: finalize_completion R3, R4, R9."""
    o = _stock_order(db, s, machine_id=None)
    mk = mark(db)
    result = FIN(db, s, o, completed_by_names="Ghost")
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.completed_by is None
    assert row.completed_by_names == "Ghost"
    # Then 3
    assert len(rows_of(db, WorkOrderCompleter, work_order_id=o.id)) == 0
    # Then 4
    assert "recorded_by" not in evrow(db, mk, o, "completed").metadata_json
    # Then 5
    assert "completed_by" not in evrow(db, mk, o, "completed").metadata_json


# [claude] WOM-FC-06
def test_wom_fc_06__given_time_and_extra(db, s):
    """WOM-FC-06 — a given completion time and extra metadata are used.
    Rules: finalize_completion R3, R9."""
    o = _stock_order(db, s, machine_id=None)
    mk = mark(db)
    result = FIN(db, s, o, completed_at=datetime(2026, 3, 9, 17, 0, 0), event_metadata_extra={"completion_mode": "manual"})
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).completed_at == datetime(2026, 3, 9, 17, 0, 0)
    # Then 3
    meta = evrow(db, mk, o, "completed").metadata_json
    assert meta["completed_at"] == "2026-03-09T17:00:00"
    assert meta["variance_label"] == "8 days late"
    assert meta["completion_mode"] == "manual"


# [claude] WOM-FC-07
def test_wom_fc_07__notes_replace(db, s):
    """WOM-FC-07 — completion notes replace the stored ones.
    Rules: finalize_completion R3."""
    o = _stock_order(db, s, machine_id=None, completion_notes="Half done")
    result = FIN(db, s, o, completion_notes="Done")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).completion_notes == "Done"


# [claude] WOM-FC-08
def test_wom_fc_08__empty_clears_none_keeps(db, s):
    """WOM-FC-08 — empty notes clear them; no notes keep them.
    Rules: finalize_completion R3."""
    o = mk_order(db, s, "1", **{**STARTED(s), "machine_id": None, "completion_notes": "Half done"})
    p = mk_order(db, s, "2", **{**STARTED(s), "machine_id": None, "completion_notes": "Half done"})
    result = (FIN(db, s, o, completion_notes=""), FIN(db, s, p))
    # Then 1
    assert result[0].id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).completion_notes == ""
    # Then 3
    assert reread(db, WorkOrder, p.id).completion_notes == "Half done"


# [claude] WOM-FC-09
def test_wom_fc_09__draft_completed(db, s):
    """WOM-FC-09 — there is no state check of its own: a draft is completed.
    Rules: finalize_completion R1."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).status == "COMPLETED"


# [claude] WOM-FC-10
def test_wom_fc_10__inactive_completer(db, s):
    """WOM-FC-10 — a completer who is not an active member stops the call before any write.
    Rules: finalize_completion R2."""
    o = _stock_order(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        FIN(db, s, o, completed_by_user_ids=[s.U4.id])
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-FC-11
def test_wom_fc_11__repeated_completer_one_row(db, s):
    """WOM-FC-11 — a repeated completer id gives one completer row.
    Rules: finalize_completion R4."""
    o = _stock_order(db, s, machine_id=None)
    mk = mark(db)
    result = FIN(db, s, o, completed_by_user_ids=[s.U3.id, s.U3.id])
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [c.user_id for c in rows_of(db, WorkOrderCompleter, work_order_id=o.id)] == [s.U3.id]
    # Then 3
    assert evrow(db, mk, o, "completed").metadata_json["completed_by_user_ids"] == [s.U3.id, s.U3.id]


# [claude] WOM-FC-12
def test_wom_fc_12__live_install_only(db, s):
    """WOM-FC-12 — live Install lines are installed; deleted ones are not.
    Rules: finalize_completion R5."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T1)
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **CONSUMED(s, "5.00"))
    mk_line(db, s, o, s.I2, "1", action_type="INSTALL", **CONSUMED(s, "2.50"), **LINE_GONE(s))
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert mqty(db, s, s.M1, s.I1) == Decimal("2")
    # Then 3
    assert mqty(db, s, s.M1, s.I2) == Decimal("0")


# [claude] WOM-FC-13
def test_wom_fc_13__chosen_status_wins(db, s):
    """WOM-FC-13 — a chosen machine status wins over the status before start.
    Rules: finalize_completion R7."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T1)
    mk = mark(db)
    result = FIN(db, s, o, machine_status=MachineEventTypeEnum.IDLE)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["IDLE"]


# [claude] WOM-FC-14
def test_wom_fc_14__no_started_event_idle(db, s):
    """WOM-FC-14 — no started event: the machine goes idle.
    Rules: finalize_completion R7."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["IDLE"]


# [claude] WOM-FC-15
def test_wom_fc_15__maintenance_before_stays(db, s):
    """WOM-FC-15 — a machine already in maintenance before start stays in it.
    Rules: finalize_completion R7 (Q9)."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T0)
    mk_event(db, s, o, "started", {"previous_machine_status": "MAINTENANCE"}, T1)
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == []


# [claude] WOM-FC-16
def test_wom_fc_16__bogus_status_value_error(db, s):
    """WOM-FC-16 — a stored status that is not a machine status raises ValueError.
    Rules: finalize_completion R7."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk_event(db, s, o, "started", {"previous_machine_status": "BOGUS"}, T1)
    # Then 1
    with pytest.raises(ValueError):
        FIN(db, s, o)


# [claude] WOM-FC-17
def test_wom_fc_17__component_with_notes(db, s):
    """WOM-FC-17 — a component order logs the completion and notes on the component (revisit after launch).
    Rules: finalize_completion R8."""
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC1.id, title="Service — Panel A")
    mk = mark(db)
    result = FIN(db, s, o, completion_notes="Done")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [(r.event_type, r.description) for r in pcacts(db, mk, s.PC1)] == [
        ("work_order_completed", f"Work order {o.work_order_number} completed: Service — Panel A. Done")]


# [claude] WOM-FC-18
def test_wom_fc_18__component_no_suffix(db, s):
    """WOM-FC-18 — without notes the component entry has no suffix (revisit after launch).
    Rules: finalize_completion R8."""
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC1.id, title="Service — Panel A")
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [r.description for r in pcacts(db, mk, s.PC1)] == [f"Work order {o.work_order_number} completed: Service — Panel A"]


# [claude] WOM-FC-19
@xf(1884)
def test_wom_fc_19__foreign_component_no_entry(db, s):
    """WOM-FC-19 — a component of another workspace gets no entry.
    Rules: finalize_completion R8 [BUG-1884]."""
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC9.id)
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert _new_count(db, mk, ProjectComponentActivityEvent) == 0


# [claude] WOM-FC-20
def test_wom_fc_20__foreign_component_completes(db, s):
    """WOM-FC-20 — a component of another workspace does not stop the completion.
    Rules: finalize_completion R8."""
    o = _stock_order(db, s, machine_id=None, project_component_id=s.PC9.id)
    result = FIN(db, s, o)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).status == "COMPLETED"


# [claude] WOM-FC-21
def test_wom_fc_21__no_machine_lines_do_nothing(db, s):
    """WOM-FC-21 — without a machine, Install / Replace / Borrow lines do nothing at completion.
    Rules: finalize_completion R10."""
    mk_S(db, s, s.F1, s.I3, 4, Decimal("1.00"))
    o = _stock_order(db, s, machine_id=None)
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **CONSUMED(s, "5.00"))
    mk_line(db, s, o, s.I3, "1", action_type="BORROW", **CONSUMED(s, "2.50"))
    mk = mark(db)
    result = FIN(db, s, o)
    # Then 1
    assert result.status == "COMPLETED"
    # Then 2
    assert _new_count(db, mk, MachineItemLedger) == 0
    # Then 3
    assert led(db, mk, s, s.F1, s.I3, STORAGE) == []


# [claude] WOM-FC-23
def test_wom_fc_23__flushes_never_commits(db, s):
    """WOM-FC-23 — finalize flushes and never commits.
    Rules: finalize_completion R3."""
    o = _stock_order(db, s, machine_id=None)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = FIN(db, s, o)
        # Then 1
        assert result.status == "COMPLETED"
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).status == "IN_PROGRESS"


# [claude] WOM-FC-24
def test_wom_fc_24__recorder_is_performer(db, s):
    """WOM-FC-24 — the recorder, not the worker, is the performer of the event, the machine entries and the postings.
    Rules: finalize_completion R5, R6, R7, R9; G18 (performer, ledger source)."""
    o = _fin_given(db, s)
    mk_line(db, s, o, s.I1, "2", action_type="INSTALL", **CONSUMED(s, "5.00"))
    mk = mark(db)
    result = FIN(db, s, o, completed_by_user_ids=[s.U3.id])
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, WorkOrder, o.id).completed_by == s.U3.id
    # Then 3
    e = evrow(db, mk, o, "completed")
    assert e.performed_by == s.U2.id
    assert e.metadata_json["recorded_by"] == s.U2.id
    # Then 4
    done = [a for a in actrows(db, mk, s.M1) if a.event_type == "work_order_completed"]
    assert [(a.performed_by, a.metadata_json) for a in done] == [(s.U2.id, {"work_order_id": o.id})]
    # Then 5
    assert [a.performed_by for a in _status_rows(db, mk, s.M1)] == [s.U2.id]
    # Then 6
    assert [(r.transaction_type, r.quantity) for r in mled(db, mk, s, s.M1, s.I1)] == [("work_order_install", Decimal("2"))]
    # Then 7
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in mled(db, mk, s, s.M1, s.I1))


def _void(db, s, o, note):
    return WOM.void_work_order(db, o.id, s.W1.id, s.U2.id, note)


def _void_given(db, s):
    """V-02 / V-03: O started; status row MAINTENANCE@T1; started event (RUNNING)."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk_event(db, s, o, "started", {"previous_machine_status": "RUNNING"}, T1)
    return o


# [claude] WOM-V-01
def test_wom_v_01__stock_back(db, s):
    """WOM-V-01 — a started order gets its consumed stock back.
    Rules: void_work_order R4, R9."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _void_given(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    result = _void(db, s, o, "Wrong machine")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 3
    row = reread(db, WorkOrderItem, ln.id)
    assert row.consumed_at is None
    assert row.is_deleted is False


# [claude] WOM-V-02
def test_wom_v_02__voided_and_logged(db, s):
    """WOM-V-02 — the order is voided with its note and logged.
    Rules: void_work_order R8."""
    o = _void_given(db, s)
    mk = mark(db)
    result = _void(db, s, o, "Wrong machine")
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, WorkOrder, o.id)
    assert row.status == "VOIDED"
    assert row.void_note == "Wrong machine"
    assert row.voided_at == NOW
    assert row.voided_by == s.U2.id
    # Then 3
    assert ev(db, mk, o) == [("voided", f"Work order {o.work_order_number} voided. Reason: Wrong machine")]
    # Then 4
    assert evrow(db, mk, o, "voided").metadata_json == {"void_note": "Wrong machine"}


# [claude] WOM-V-03
def test_wom_v_03__machine_returns(db, s):
    """WOM-V-03 — the machine returns to its status before start.
    Rules: void_work_order R5."""
    o = _void_given(db, s)
    mk = mark(db)
    result = _void(db, s, o, "Wrong machine")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["RUNNING"]


# [claude] WOM-V-04
def test_wom_v_04__no_status_before_idle(db, s):
    """WOM-V-04 — with no status before start the machine goes idle.
    Rules: void_work_order R5."""
    o = _stock_order(db, s)
    mk_status_row(db, s, s.M1, "MAINTENANCE", T1)
    mk = mark(db)
    result = _void(db, s, o, "Wrong machine")
    # Then 1
    assert result.id == o.id
    # Then 2
    assert stat(db, mk, s.M1) == ["IDLE"]


# [claude] WOM-V-05
def test_wom_v_05__draft_no_stock_change(db, s):
    """WOM-V-05 — a draft is voided with no stock or machine change.
    Rules: void_work_order R6."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = mk_order(db, s, "1", **STAMPED(s))
    mk_status_row(db, s, s.M1, "RUNNING", T0)
    ln = mk_line(db, s, o, s.I1, "3")
    mk = mark(db)
    bl = snap(db, ln)
    result = _void(db, s, o, "Not needed")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert led(db, mk, s, s.F1, s.I1, STORAGE) == []
    # Then 3
    assert acts(db, mk, s.M1) == []
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-V-06
def test_wom_v_06__approvals_cleared_stamp_kept(db, s):
    """WOM-V-06 — voiding clears the approvals but keeps the order's stamp.
    Rules: void_work_order R7."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = _void(db, s, o, "Not needed")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    row = reread(db, WorkOrder, o.id)
    assert row.approved_by == s.U2.id
    assert row.approved_at == T0
    # Then 4
    assert ev(db, mk, o) == [("approvals_reset", "Work order voided (1 approval(s) cleared)"),
                             ("voided", f"Work order {o.work_order_number} voided. Reason: Not needed")]


# [claude] WOM-V-07
def test_wom_v_07__completed_refused(db, s):
    """WOM-V-07 — a completed order cannot be voided.
    Rules: void_work_order R2."""
    o = mk_order(db, s, "1", **COMPLETED(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, o, "Late")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot void a completed work order"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-V-08
def test_wom_v_08__already_voided(db, s):
    """WOM-V-08 — a voided order cannot be voided again.
    Rules: void_work_order R3."""
    o = mk_order(db, s, "1", **VOIDED(s))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, o, "Again")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is already voided"
    # Then 4
    assert snap(db, o) == before


# [claude] WOM-V-09
def test_wom_v_09__order_of_w2(db, s):
    """WOM-V-09 — an order of W2 is not found.
    Rules: void_work_order R1."""
    o9 = _o9(db, s)
    before = snap(db, o9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _void(db, s, o9, "x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert snap(db, o9) == before


# [claude] WOM-V-10
def test_wom_v_10__deleted_line_not_returned(db, s):
    """WOM-V-10 — a deleted consumed line is not returned.
    Rules: void_work_order R4 (live lines)."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"), **LINE_GONE(s))
    bl = snap(db, ln)
    result = _void(db, s, o, "x")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("7")
    # Then 3
    assert snap(db, ln) == bl


# [claude] WOM-V-11
def test_wom_v_11__adjusted_all_back(db, s):
    """WOM-V-11 — consume 3, adjust to 4, void: all 4 come back.
    Rules: void_work_order R4; _reverse_item_consumption R2."""
    mk_S(db, s, s.F1, s.I1, 6, Decimal("2.50"))
    o = _stock_order(db, s, machine_id=None)
    mk_line(db, s, o, s.I1, "4", **CONSUMED(s, "10.00"))
    mk = mark(db)
    result = _void(db, s, o, "x")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 3
    assert [(r.quantity, r.unit_cost) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [(Decimal("4"), Decimal("2.50"))]


# [claude] WOM-V-17
def test_wom_v_17__unconsumed_line_skipped(db, s):
    """WOM-V-17 — a live line that was never consumed is skipped; the consumed one comes back.
    Rules: void_work_order R4 (only consumed live lines)."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    mk_S(db, s, s.F1, s.I2, 5, Decimal("1.00"))
    o = _stock_order(db, s, machine_id=None)
    mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    l2 = mk_line(db, s, o, s.I2, "2")
    mk = mark(db)
    b2 = snap(db, l2)
    result = _void(db, s, o, "x")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 3
    assert qty(db, s, s.F1, s.I2, STORAGE) == Decimal("5")
    assert led(db, mk, s, s.F1, s.I2, STORAGE) == []
    # Then 4
    assert snap(db, l2) == b2


# [claude] WOM-V-18
def test_wom_v_18__voider_is_performer(db, s):
    """WOM-V-18 — the voider is the performer of the event, the status change and the reversal.
    Rules: void_work_order R4, R5, R8; _reverse_item_consumption R2; G18 (performer, ledger source)."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _void_given(db, s)
    mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    result = _void(db, s, o, "Wrong machine")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert evrow(db, mk, o, "voided").performed_by == s.U2.id
    # Then 3
    assert [a.performed_by for a in _status_rows(db, mk, s.M1)] == [s.U2.id]
    # Then 4
    assert [(r.transaction_type, r.quantity, r.unit_cost, r.notes) for r in led(db, mk, s, s.F1, s.I1, STORAGE)] == [
        ("consumption_reversal", Decimal("3"), Decimal("2.50"), f"{o.work_order_number} voided — Bolt returned")]
    # Then 5
    assert all((r.source_type, r.source_id, r.performed_by) == ("work_order", o.id, s.U2.id)
               for r in led(db, mk, s, s.F1, s.I1, STORAGE))


def _void_req(**k):
    from app.schemas.work_order import WorkOrderVoidRequest
    return WorkOrderVoidRequest(**k)


# [claude] WOM-V-12
@xf(2918)
def test_wom_v_12__blank_reason_schema():
    """WOM-V-12 — a blank void reason is refused by the schema.
    Rules: void_work_order R8 [BUG-2918]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _void_req(void_note="  ")
    # Then 2
    assert "void_note" in str(exc.value)


# [claude] WOM-V-13
@xf(2918)
def test_wom_v_13__reason_trimmed():
    """WOM-V-13 — the void reason is trimmed by the schema.
    Rules: void_work_order R8 [BUG-2918]."""
    result = _void_req(void_note="  Wrong machine  ")
    # Then 1
    assert result.void_note == "Wrong machine"


# [claude] WOM-V-14
def test_wom_v_14__plain_reason():
    """WOM-V-14 — a plain reason is accepted by the schema.
    Rules: void_work_order R8."""
    result = _void_req(void_note="Wrong machine")
    # Then 1
    assert result.void_note == "Wrong machine"


# [claude] WOM-V-15
@xf(2916)
def test_wom_v_15__order_row_locked(db, s):
    """WOM-V-15 — the order row is locked before its state is checked.
    Rules: void_work_order R10 [BUG-2916]."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    db.expunge_all()
    with Recorder(db) as rec:
        result = _void(db, s, o, "x")
    # Then 1
    assert result.status == "VOIDED"
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-V-16
def test_wom_v_16__flushes_never_commits(db, s):
    """WOM-V-16 — void flushes and never commits.
    Rules: void_work_order R8."""
    o = mk_order(db, s, "1", **STAMPED(s), machine_id=None)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _void(db, s, o, "x")
        # Then 1
        assert result.status == "VOIDED"
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrder, o.id).status == "DRAFT"


# =========================================================================== #
# _ensure_catalog_item_not_on_wo / _guard_item_mutations / add_item
# =========================================================================== #


# [claude] WOM-ECI-01
def test_wom_eci_01__live_line_conflict(db, s):
    """WOM-ECI-01 — a live line with the item is a conflict.
    Rules: _ensure_catalog_item_not_on_wo R1."""
    o = mk_order(db, s, "1")
    mk_line(db, s, o, s.I1, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._ensure_catalog_item_not_on_wo(db, o.id, s.I1.id, s.W1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Bolt is already on this order"


# [claude] WOM-ECI-02
def test_wom_eci_02__no_conflict(db, s):
    """WOM-ECI-02 — a deleted line, an excluded line or a line of another order is no conflict.
    Rules: _ensure_catalog_item_not_on_wo R1."""
    o = mk_order(db, s, "1")
    mk_line(db, s, o, s.I1, "1", **LINE_GONE(s))
    lx = mk_line(db, s, o, s.I2, "1")
    p = mk_order(db, s, "2")
    mk_line(db, s, p, s.I3, "1")
    result = (WOM._ensure_catalog_item_not_on_wo(db, o.id, s.I1.id, s.W1.id),
              WOM._ensure_catalog_item_not_on_wo(db, o.id, s.I2.id, s.W1.id, exclude_item_id=lx.id),
              WOM._ensure_catalog_item_not_on_wo(db, o.id, s.I3.id, s.W1.id))
    # Then 1
    assert result == (None, None, None)


# [claude] WOM-GIM-01
def test_wom_gim_01__no_stock_items_first(db, s):
    """WOM-GIM-01 — an order without stock items is refused first, even when completed.
    Rules: _guard_item_mutations R1."""
    o = mk_order(db, s, "1", **COMPLETED(s), uses_inventory=False)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM._guard_item_mutations(o)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "This work order does not use stock items"


# [claude] WOM-GIM-02
def test_wom_gim_02__completed_voided_refused(db, s):
    """WOM-GIM-02 — completed and voided orders are refused.
    Rules: _guard_item_mutations R2."""
    o = mk_order(db, s, "1", **COMPLETED(s))
    p = mk_order(db, s, "2", **VOIDED(s))
    result = []
    for x in [o, p]:
        with pytest.raises(HTTPException) as exc:
            WOM._guard_item_mutations(x)
        result.append((exc.value.status_code, exc.value.detail))
    # Then 1
    assert result == [(400, "Work order is completed"), (400, "Work order is voided")]


# [claude] WOM-GIM-03
def test_wom_gim_03__draft_started_pass(db, s):
    """WOM-GIM-03 — drafts and started orders pass.
    Rules: _guard_item_mutations R1, R2."""
    o = mk_order(db, s, "1")
    p = mk_order(db, s, "2", **STARTED(s))
    result = (WOM._guard_item_mutations(o), WOM._guard_item_mutations(p))
    # Then 1
    assert result == (None, None)


def _stamped(db, s, **k):
    """`O = order "1", but stamped` (+ the card's extra columns)."""
    return mk_order(db, s, "1", **{**STAMPED(s), **k})


# [claude] WOM-AI-01
def test_wom_ai_01__stock_line_added(db, s):
    """WOM-AI-01 — a stock line is added to a draft and logged.
    Rules: add_item R1, R8, R9 (G17), R13."""
    o = _stamped(db, s)
    mk = mark(db)
    result = ADD(db, s, ITEM(s, o))
    # Then 1
    assert isinstance(result, WorkOrderItem)
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderItem, result.id)
    assert row.work_order_id == o.id
    assert row.item_id == s.I1.id
    assert row.quantity == Decimal("2.00")
    assert row.uses_inventory is True
    assert row.workspace_id == s.W1.id
    assert row.created_by == s.U2.id
    # Then 3
    assert row.source_location_type == "storage"
    assert row.source_location_id == s.F1.id
    assert row.action_type == "CONSUME"
    assert row.replaced_item_id is None
    assert row.notes is None
    assert row.consumed_at is None
    # Then 4
    assert ev(db, mk, o) == [("item_added", "Added 2 Bolt")]
    # Then 5
    assert evrow(db, mk, o, "item_added").metadata_json == {"item_id": s.I1.id, "item_name": "Bolt"}


# [claude] WOM-AI-02
def test_wom_ai_02__no_inventory_no_source(db, s):
    """WOM-AI-02 — a line that does not use inventory needs no source.
    Rules: add_item R2, R8."""
    o = _stamped(db, s)
    result = ADD(db, s, ITEM(s, o, uses_inventory=False, source_location_type=None, source_location_id=None, notes="Spare"))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderItem, result.id)
    assert row.uses_inventory is False
    assert row.source_location_type is None
    assert row.notes == "Spare"


# [claude] WOM-AI-03
def test_wom_ai_03__order_of_w2(db, s):
    """WOM-AI-03 — an order of W2 is not found.
    Rules: add_item R1."""
    o9 = _o9(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o9))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-04
def test_wom_ai_04__order_without_stock_items(db, s):
    """WOM-AI-04 — an order without stock items takes no line.
    Rules: add_item R1; _guard_item_mutations R1."""
    o = _stamped(db, s, uses_inventory=False)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "This work order does not use stock items"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-AI-05 … WOM-AI-11, WOM-AI-13, WOM-AI-17
@pytest.mark.parametrize("order_kind,k,detail", [
    pytest.param("completed", {}, "Work order is completed", id="WOM-AI-05"),
    pytest.param("stamped", {"source_location_type": None}, "Select a source location for this item", id="WOM-AI-06"),
    pytest.param("stamped", {"source_location_id": None}, "Select a source location for this item", id="WOM-AI-07"),
    pytest.param("stamped", {"action_type": "INSTALL", "uses_inventory": False},
                 'Install requires "uses inventory" to be on', id="WOM-AI-08"),
    pytest.param("stamped", {"action_type": "REPLACE", "uses_inventory": False},
                 'Replace requires "uses inventory" to be on', id="WOM-AI-09"),
    pytest.param("stamped", {"action_type": "BORROW", "uses_inventory": False},
                 'Borrow requires "uses inventory" to be on', id="WOM-AI-10"),
    pytest.param("no_machine", {"action_type": "INSTALL"},
                 "Install/Replace/Borrow only apply to work orders that target a machine", id="WOM-AI-11"),
    pytest.param("stamped", {"action_type": "REPLACE"}, "Select the item being replaced", id="WOM-AI-13"),
    pytest.param("stamped", {"replaced_item_id": "I2"}, "replaced_item_id only applies to Replace", id="WOM-AI-17"),
])
def test_wom_ai_400_refusals(db, s, order_kind, k, detail):
    """WOM-AI-05 … WOM-AI-11, AI-13, AI-17 — the 400 refusals of add_item, nothing written.
    Rules: add_item R1-R5; _guard_item_mutations R2."""
    o = {"completed": lambda: mk_order(db, s, "1", **COMPLETED(s)),
         "stamped": lambda: _stamped(db, s),
         "no_machine": lambda: _stamped(db, s, machine_id=None)}[order_kind]()
    k = {key: (getattr(s, v).id if key == "replaced_item_id" else v) for key, v in k.items()}
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, **k))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-12
def test_wom_ai_12__source_before_install_rules(db, s):
    """WOM-AI-12 — a missing source is reported before the Install rules.
    Rules: add_item R7 (R2 before R3)."""
    o = _stamped(db, s, machine_id=None)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, action_type="INSTALL", source_location_id=None))
    # Then 2
    assert exc.value.detail == "Select a source location for this item"


# [claude] WOM-AI-14, WOM-AI-15
@pytest.mark.parametrize("item", [pytest.param("I9", id="WOM-AI-14"), pytest.param("I0", id="WOM-AI-15")])
def test_wom_ai_14_15__foreign_replaced_item(db, s, item):
    """WOM-AI-14 / WOM-AI-15 — a replaced item of W2 / W0 is not found.
    Rules: add_item R4."""
    o = _stamped(db, s)
    ri = getattr(s, item)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, action_type="REPLACE", replaced_item_id=ri.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {ri.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-16
def test_wom_ai_16__replace_line_stored(db, s):
    """WOM-AI-16 — a Replace line with its replaced item is stored.
    Rules: add_item R4, R8."""
    o = _stamped(db, s)
    result = ADD(db, s, ITEM(s, o, action_type="REPLACE", replaced_item_id=s.I2.id))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderItem, result.id)
    assert row.action_type == "REPLACE"
    assert row.replaced_item_id == s.I2.id


# [claude] WOM-AI-18
def test_wom_ai_18__replaced_item_on_install(db, s):
    """WOM-AI-18 — a replaced item on an Install line is refused.
    Rules: add_item R5."""
    o = _stamped(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, action_type="INSTALL", replaced_item_id=s.I2.id))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "replaced_item_id only applies to Replace"


# [claude] WOM-AI-19
@xf(2912)
def test_wom_ai_19__quantity_zero_schema(db, s):
    """WOM-AI-19 — quantity 0 is refused by WorkOrderItemCreate.
    Rules: add_item R5a [BUG-2912]."""
    o = mk_order(db, s, "1")
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ITEM(s, o, quantity=Decimal("0"))
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-AI-20
@xf(2912)
def test_wom_ai_20__negative_quantity_schema(db, s):
    """WOM-AI-20 — a negative quantity is refused by WorkOrderItemCreate.
    Rules: add_item R5a [BUG-2912]."""
    o = mk_order(db, s, "1")
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ITEM(s, o, quantity=Decimal("-2"))
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-AI-21
@xf(2913)
def test_wom_ai_21__three_decimals_schema(db, s):
    """WOM-AI-21 — a quantity with 3 decimals is refused by WorkOrderItemCreate.
    Rules: add_item R5a [BUG-2913]."""
    o = mk_order(db, s, "1")
    # Then 1
    with pytest.raises(ValidationError) as exc:
        ITEM(s, o, quantity=Decimal("1.005"), uses_inventory=False)
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-AI-22
def test_wom_ai_22__schema_edges(db, s):
    """WOM-AI-22 — the smallest positive quantity and the default are accepted; an unknown action is not.
    Rules: add_item R5a; Inputs (action_type)."""
    from app.schemas.work_order_item import WorkOrderItemCreate
    o = mk_order(db, s, "1")
    result = (ITEM(s, o, quantity=Decimal("0.01")), WorkOrderItemCreate(work_order_id=o.id, item_id=s.I1.id))
    # Then 1
    assert result[0].quantity == Decimal("0.01")
    # Then 2
    assert result[1].quantity == 1
    assert result[1].uses_inventory is False
    assert result[1].action_type == "CONSUME"
    # Then 3
    with pytest.raises(ValidationError):
        ITEM(s, o, action_type="SWAP")


# [claude] WOM-AI-23
@xf(2914)
def test_wom_ai_23__fractional_stock_line_refused(db, s):
    """WOM-AI-23 — a fractional stock line is refused when added.
    Rules: add_item R5b [BUG-2914]."""
    o = _stamped(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, quantity=Decimal("2.5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Bolt has a fractional quantity; inventory consumption requires whole units"
    # Then 4
    assert not db.new
    assert not db.dirty
    assert not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] WOM-AI-24
def test_wom_ai_24__fractional_off_inventory_ok(db, s):
    """WOM-AI-24 — a fractional line that does not use inventory is accepted.
    Rules: add_item R5b."""
    o = _stamped(db, s)
    result = ADD(db, s, ITEM(s, o, quantity=Decimal("2.5"), uses_inventory=False, source_location_type=None,
                             source_location_id=None))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrderItem, result.id).quantity == Decimal("2.50")


# [claude] WOM-AI-25
def test_wom_ai_25__same_item_twice(db, s):
    """WOM-AI-25 — the same item twice is a conflict.
    Rules: add_item R6."""
    o = _stamped(db, s)
    mk_line(db, s, o, s.I1, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o))
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Bolt is already on this order"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-26
def test_wom_ai_26__deleted_line_no_block(db, s):
    """WOM-AI-26 — a deleted line of the item does not block a new one.
    Rules: add_item R6."""
    o = _stamped(db, s)
    mk_line(db, s, o, s.I1, "1", **LINE_GONE(s))
    result = ADD(db, s, ITEM(s, o))
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rows_of(db, WorkOrderItem, work_order_id=o.id, is_deleted=False)) == 1


# [claude] WOM-AI-27 … WOM-AI-30
@pytest.mark.parametrize("which", [
    pytest.param("F9", id="WOM-AI-27"),
    pytest.param("M9", id="WOM-AI-28"),
    pytest.param("FD", id="WOM-AI-29"),
    pytest.param("shelf", id="WOM-AI-30"),
])
@xf(2927)
def test_wom_ai_27_30__bad_source_refused(db, s, which):
    """WOM-AI-27 … WOM-AI-30 — a source factory / machine of W2, a deleted factory of W1, an unknown type are refused.
    Rules: add_item R6a [BUG-2927]."""
    fd = _add(db, Factory(workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", **GONE_FT)) if which == "FD" else None
    o = _stamped(db, s)
    k, code, detail = {
        "F9": ({"source_location_id": s.F9.id}, 404, f"Factory with ID {s.F9.id} not found"),
        "M9": ({"source_location_type": "machine", "source_location_id": s.M9.id}, 404,
               f"Machine with ID {s.M9.id} not found"),
        "FD": ({"source_location_id": fd.id if fd else None}, 404, f"Factory with ID {fd.id if fd else None} not found"),
        "shelf": ({"source_location_type": "shelf"}, 400, "Unsupported source location type: shelf"),
    }[which]
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, **k))
    # Then 2
    assert exc.value.status_code == code
    # Then 3
    assert exc.value.detail == detail
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-31
def test_wom_ai_31__other_w1_sources_valid(db, s):
    """WOM-AI-31 — another live factory or machine of W1 is a valid source.
    Rules: add_item R6a."""
    o = _stamped(db, s)
    result = (ADD(db, s, ITEM(s, o, source_location_id=s.F2.id)),
              ADD(db, s, ITEM(s, o, item_id=s.I2.id, source_location_type="machine", source_location_id=s.M2.id)))
    # Then 1
    assert result[0].id is not None
    assert result[1].id is not None
    # Then 2
    assert reread(db, WorkOrderItem, result[0].id).source_location_id == s.F2.id
    # Then 3
    r1 = reread(db, WorkOrderItem, result[1].id)
    assert r1.source_location_type == "machine"
    assert r1.source_location_id == s.M2.id


# [claude] WOM-AI-32
def test_wom_ai_32__duplicate_before_foreign_source(db, s):
    """WOM-AI-32 — a duplicate is reported before a foreign source.
    Rules: add_item R7 (R6 before R6a)."""
    o = _stamped(db, s)
    mk_line(db, s, o, s.I1, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, source_location_id=s.F9.id))
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Bolt is already on this order"


# [claude] WOM-AI-33
@xf(2914)
def test_wom_ai_33__fractional_before_duplicate(db, s):
    """WOM-AI-33 — a fractional quantity is reported before a duplicate.
    Rules: add_item R7 (R5b before R6) [BUG-2914]."""
    o = _stamped(db, s)
    mk_line(db, s, o, s.I1, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, quantity=Decimal("2.5")))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Bolt has a fractional quantity; inventory consumption requires whole units"


# [claude] WOM-AI-34
def test_wom_ai_34__approved_draft_cleared(db, s):
    """WOM-AI-34 — adding to an approved draft clears the approvals.
    Rules: add_item R10."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    result = ADD(db, s, ITEM(s, o))
    # Then 1
    assert result.id is not None
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    assert ("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(db, mk, o)


# [claude] WOM-AI-35
def test_wom_ai_35__started_consumed_at_once(db, s):
    """WOM-AI-35 — adding to a started order consumes the line at once.
    Rules: add_item R11."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    result = ADD(db, s, ITEM(s, o))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrderItem, result.id)
    assert row.consumed_at == NOW
    assert row.consumed_by == s.U2.id
    assert row.total_cost == Decimal("5.00")
    # Then 3
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("8")


# [claude] WOM-AI-36
@xf(1016)
def test_wom_ai_36__item_of_w2(db, s):
    """WOM-AI-36 — an item of W2 is not found.
    Rules: add_item R12 [BUG-1016]."""
    o = _stamped(db, s)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ADD(db, s, ITEM(s, o, item_id=s.I9.id, uses_inventory=False, source_location_type=None, source_location_id=None))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-AI-37
@xf(2916)
def test_wom_ai_37__started_order_locked(db, s):
    """WOM-AI-37 — on a started order the order row is locked before the state check.
    Rules: add_item R14 [BUG-2916]."""
    o = _stock_order(db, s)
    db.expunge_all()
    with Recorder(db) as rec:
        result = ADD(db, s, ITEM(s, o, uses_inventory=False, source_location_type=None, source_location_id=None))
    # Then 1
    assert result.id is not None
    # Then 2
    assert rec.locks_first("work_orders")


# [claude] WOM-AI-38
def test_wom_ai_38__flushes_never_commits(db, s):
    """WOM-AI-38 — add item flushes and never commits.
    Rules: add_item R8."""
    o = _stamped(db, s)
    data = ITEM(s, o)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = ADD(db, s, data)
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert len(rows_of(db, WorkOrderItem, work_order_id=o.id)) == 0


# =========================================================================== #
# update_item / remove_item / get_items
# =========================================================================== #


def _l9(db, s):
    """O9 of W2 with L9 = line(O9, I9, "1"), but W2 / F9."""
    o9 = _o9(db, s)
    return mk_line(db, s, o9, s.I9, "1", workspace_id=s.W2.id, source_location_id=s.F9.id)


def _wiu(**k):
    from app.schemas.work_order_item import WorkOrderItemUpdate
    return WorkOrderItemUpdate(**k)


# [claude] WOM-UI-01
def test_wom_ui_01__unconsumed_line_written(db, s):
    """WOM-UI-01 — a line not yet consumed is written and logged.
    Rules: update_item R2, R7."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    mk = mark(db)
    result = UIT(db, s, ln, quantity=Decimal("3"), notes="Check")
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.quantity == Decimal("3.00")
    assert row.notes == "Check"
    assert row.updated_by == s.U2.id
    # Then 3
    assert ev(db, mk, o) == [("item_updated", f"Item line {ln.id} updated")]


# [claude] WOM-UI-02
def test_wom_ui_02__line_of_w2(db, s):
    """WOM-UI-02 — a line of W2 is not found.
    Rules: update_item R1."""
    l9 = _l9(db, s)
    before = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, l9, notes="x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert snap(db, l9) == before


# [claude] WOM-UI-03
def test_wom_ui_03__deleted_line(db, s):
    """WOM-UI-03 — a deleted line is not found.
    Rules: update_item R1."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2", **LINE_GONE(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, notes="x")
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-UI-04
def test_wom_ui_04__completed_order_line(db, s):
    """WOM-UI-04 — a line of a completed order cannot change.
    Rules: update_item R2."""
    o = mk_order(db, s, "1", **COMPLETED(s))
    ln = mk_line(db, s, o, s.I1, "2")
    before = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, notes="x")
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is completed"
    # Then 4
    assert snap(db, ln) == before


# [claude] WOM-UI-05
def test_wom_ui_05__only_nulls(db, s):
    """WOM-UI-05 — only nulls: the line is returned unchanged.
    Rules: update_item R3."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    bl = snap(db, ln)
    before = counts(db)
    result = UIT(db, s, ln, notes=None, quantity=None)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert snap(db, ln) == bl
    # Then 3
    assert counts(db) == before


# [claude] WOM-UI-06
def test_wom_ui_06__consumed_source_locked(db, s):
    """WOM-UI-06 — a consumed line cannot change its source.
    Rules: update_item R4."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    bl = snap(db, ln)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, source_location_id=s.F2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Consumed lines only support quantity and notes updates"
    # Then 4
    assert snap(db, ln) == bl
    # Then 5
    assert counts(db) == before


# [claude] WOM-UI-07
def test_wom_ui_07__consumed_inventory_locked(db, s):
    """WOM-UI-07 — a consumed line cannot stop using inventory.
    Rules: update_item R4."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, uses_inventory=False)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Consumed lines only support quantity and notes updates"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-UI-08
def test_wom_ui_08__consumed_quantity_moves_stock(db, s):
    """WOM-UI-08 — a consumed line's new quantity moves stock and is logged; approvals stay.
    Rules: update_item R5."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    mk = mark(db)
    ba = snap(db, a)
    db.expire(ln)
    result = UIT(db, s, ln, quantity=Decimal("4"))
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("6")
    # Then 3
    row = reread(db, WorkOrderItem, ln.id)
    assert row.quantity == Decimal("4.00")
    assert row.total_cost == Decimal("10.00")
    assert row.updated_by == s.U2.id
    # Then 4
    assert [t for t, _ in ev(db, mk, o)] == ["item_quantity_adjusted"]
    # Then 5
    assert ev(db, mk, o)[0][1] == "Adjusted Bolt from 3.00 to 4"
    # Then 6
    assert set(evrow(db, mk, o, "item_quantity_adjusted").metadata_json.keys()) == {"item_id", "old_quantity", "new_quantity"}
    # Then 7
    assert snap(db, a) == ba
    # Then 8
    meta = evrow(db, mk, o, "item_quantity_adjusted").metadata_json
    assert meta["old_quantity"] == "3.00"
    assert meta["new_quantity"] == "4"


# [claude] WOM-UI-09
def test_wom_ui_09__consumed_notes_only(db, s):
    """WOM-UI-09 — a consumed line's notes are written with no event and no stock move.
    Rules: update_item R6."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    result = UIT(db, s, ln, quantity=Decimal("3"), notes="Torque checked")
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.notes == "Torque checked"
    assert row.total_cost == Decimal("7.50")
    # Then 3
    assert ev(db, mk, o) == []
    # Then 4
    assert led(db, mk, s, s.F1, s.I1, STORAGE) == []


# [claude] WOM-UI-10
@xf(2927)
def test_wom_ui_10__foreign_source_refused(db, s):
    """WOM-UI-10 — a changed source of W2 is refused.
    Rules: update_item R7a [BUG-2927]."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, source_location_id=s.F9.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-UI-11
@xf(2912)
def test_wom_ui_11__quantity_zero_schema():
    """WOM-UI-11 — quantity 0 is refused by WorkOrderItemUpdate.
    Rules: update_item R7b [BUG-2912]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _wiu(quantity=Decimal("0"))
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-UI-12
@xf(2913)
def test_wom_ui_12__three_decimals_schema():
    """WOM-UI-12 — a quantity with 3 decimals is refused by WorkOrderItemUpdate.
    Rules: update_item R7b [BUG-2913]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        _wiu(quantity=Decimal("1.005"))
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-UI-13
def test_wom_ui_13__smallest_accepted():
    """WOM-UI-13 — 0.01 is accepted by WorkOrderItemUpdate.
    Rules: update_item R7b."""
    result = _wiu(quantity=Decimal("0.01"))
    # Then 1
    assert result.quantity == Decimal("0.01")


# [claude] WOM-UI-14
@xf(2914)
def test_wom_ui_14__fractional_stock_line_refused(db, s):
    """WOM-UI-14 — a fractional quantity on a stock line is refused when updated.
    Rules: update_item R7c [BUG-2914]."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, quantity=Decimal("2.5"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} has a fractional quantity; inventory consumption requires whole units"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-UI-15
@xf(2914)
def test_wom_ui_15__switch_fractional_to_inventory(db, s):
    """WOM-UI-15 — switching a fractional line to inventory is refused.
    Rules: update_item R7c [BUG-2914]."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2.50", uses_inventory=False)
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, uses_inventory=True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} has a fractional quantity; inventory consumption requires whole units"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-UI-16
def test_wom_ui_16__fractional_off_inventory_ok(db, s):
    """WOM-UI-16 — a fractional quantity on a line that does not use inventory is accepted.
    Rules: update_item R7c."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    result = UIT(db, s, ln, quantity=Decimal("2.5"))
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).quantity == Decimal("2.50")


# [claude] WOM-UI-17
def test_wom_ui_17__approved_draft_cleared(db, s):
    """WOM-UI-17 — editing a line of an approved draft clears the approvals.
    Rules: update_item R8."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ln = mk_line(db, s, o, s.I1, "2")
    mk = mark(db)
    result = UIT(db, s, ln, quantity=Decimal("3"))
    # Then 1
    assert result.id == ln.id
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is False
    assert ra.approved_at is None
    # Then 3
    assert ("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(db, mk, o)


# [claude] WOM-UI-18
def test_wom_ui_18__switched_to_inventory_consumed(db, s):
    """WOM-UI-18 — on a started order a line switched to inventory is consumed now.
    Rules: update_item R9."""
    mk_S(db, s, s.F1, s.I1, 10, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False, source_location_type=None, source_location_id=None)
    result = UIT(db, s, ln, uses_inventory=True, source_location_type="storage", source_location_id=s.F1.id)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.uses_inventory is True
    assert row.consumed_at == NOW
    # Then 3
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("8")


# [claude] WOM-UI-19
def test_wom_ui_19__switched_without_source(db, s):
    """WOM-UI-19 — on a started order a line switched to inventory without a source is refused.
    Rules: update_item R9."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False, source_location_type=None, source_location_id=None)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UIT(db, s, ln, uses_inventory=True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item line {ln.id} uses inventory but has no source location set"


# [claude] WOM-UI-20
@xf(2915)
def test_wom_ui_20__no_change_noop(db, s):
    """WOM-UI-20 — a request that changes nothing writes, logs and resets nothing.
    Rules: update_item R10 [BUG-2915]."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ln = mk_line(db, s, o, s.I1, "2", notes="Check")
    mk = mark(db)
    result = UIT(db, s, ln, notes="Check", quantity=Decimal("2"))
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderItem, ln.id).updated_by is None
    # Then 3
    assert ev(db, mk, o) == []
    # Then 4
    assert reread(db, WorkOrderApprover, a.id).approved is True


# [claude] WOM-UI-21
def test_wom_ui_21__no_change_keeps_values(db, s):
    """WOM-UI-21 — a request that changes nothing keeps the line's values.
    Rules: update_item R10."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2", notes="Check")
    result = UIT(db, s, ln, notes="Check")
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.notes == "Check"
    assert row.quantity == Decimal("2.00")


# [claude] WOM-UI-22
@xf(2916)
def test_wom_ui_22__order_and_line_locked(db, s):
    """WOM-UI-22 — on a started order the order and line rows are locked.
    Rules: update_item R11 [BUG-2916]."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    db.expunge_all()
    with Recorder(db) as rec:
        result = UIT(db, s, ln, notes="x")
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert rec.locks_first("work_orders")
    # Then 3
    assert rec.locks("work_order_items")


# [claude] WOM-UI-23
def test_wom_ui_23__flushes_never_commits(db, s):
    """WOM-UI-23 — update item flushes and never commits.
    Rules: update_item R7."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = UIT(db, s, ln, notes="x")
        # Then 1
        assert result.id == ln.id
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrderItem, ln.id).notes is None


# [claude] WOM-UI-24
def test_wom_ui_24__null_notes_with_quantity(db, s):
    """WOM-UI-24 — a null for notes sent with a new quantity keeps the notes.
    Rules: update_item R3, R7."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2", notes="Keep")
    mk = mark(db)
    result = UIT(db, s, ln, quantity=Decimal("3"), notes=None)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.quantity == Decimal("3.00")
    assert row.notes == "Keep"
    # Then 3
    assert ev(db, mk, o) == [("item_updated", f"Item line {ln.id} updated")]


def _ri(db, s, ln):
    return WOM.remove_item(db, ln.id, s.W1.id, s.U2.id)


# [claude] WOM-RI-01
def test_wom_ri_01__draft_line_removed(db, s):
    """WOM-RI-01 — a draft line is soft-deleted and logged as removed.
    Rules: remove_item R1, R4, R5, R7."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    mk = mark(db)
    result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    row = reread(db, WorkOrderItem, ln.id)
    assert row.is_deleted is True
    assert row.deleted_at == NOW
    assert row.deleted_by == s.U2.id
    # Then 3
    assert ev(db, mk, o) == [("item_removed", "Removed Bolt")]


# [claude] WOM-RI-02
def test_wom_ri_02__consumed_line_voided(db, s):
    """WOM-RI-02 — a consumed line on a started order goes back to stock and is logged as voided.
    Rules: remove_item R3, R5."""
    mk_S(db, s, s.F1, s.I1, 7, Decimal("2.50"))
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "3", **CONSUMED(s, "7.50"))
    mk = mark(db)
    result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert qty(db, s, s.F1, s.I1, STORAGE) == Decimal("10")
    # Then 3
    row = reread(db, WorkOrderItem, ln.id)
    assert row.is_deleted is True
    assert row.consumed_at is None
    # Then 4
    assert ev(db, mk, o) == [("item_voided", "Voided Bolt")]


# [claude] WOM-RI-03
def test_wom_ri_03__unconsumed_started_removed(db, s):
    """WOM-RI-03 — a line not consumed on a started order is logged as removed.
    Rules: remove_item R5."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    mk = mark(db)
    result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert ev(db, mk, o) == [("item_removed", "Removed Bolt")]


# [claude] WOM-RI-04
def test_wom_ri_04__deleted_line(db, s):
    """WOM-RI-04 — a deleted line is not found.
    Rules: remove_item R1."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2", **LINE_GONE(s))
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, s, ln)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-RI-05
def test_wom_ri_05__line_of_w2(db, s):
    """WOM-RI-05 — a line of W2 is not found.
    Rules: remove_item R1."""
    l9 = _l9(db, s)
    bl = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, s, l9)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order item not found"
    # Then 4
    assert snap(db, l9) == bl


# [claude] WOM-RI-06
def test_wom_ri_06__voided_order_line(db, s):
    """WOM-RI-06 — a line of a voided order cannot be removed.
    Rules: remove_item R1."""
    o = mk_order(db, s, "1", **VOIDED(s))
    ln = mk_line(db, s, o, s.I1, "2")
    bl = snap(db, ln)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, s, ln)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order is voided"
    # Then 4
    assert snap(db, ln) == bl


# [claude] WOM-RI-07
def test_wom_ri_07__order_without_stock_items(db, s):
    """WOM-RI-07 — a line of an order without stock items cannot be removed.
    Rules: remove_item R1."""
    o = _stamped(db, s, uses_inventory=False)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, s, ln)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "This work order does not use stock items"


# [claude] WOM-RI-08
def test_wom_ri_08__approved_draft_cleared(db, s):
    """WOM-RI-08 — removing a line from an approved draft clears the approvals.
    Rules: remove_item R6."""
    o = mk_order(db, s, "1", approved_by=s.U2.id, approved_at=T0)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ln = mk_line(db, s, o, s.I1, "2")
    mk = mark(db)
    result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert reread(db, WorkOrderApprover, a.id).approved is False
    # Then 3
    assert ("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(db, mk, o)


# [claude] WOM-RI-09
@xf(2916)
def test_wom_ri_09__order_and_line_locked(db, s):
    """WOM-RI-09 — on a started order the order and line rows are locked.
    Rules: remove_item R9 [BUG-2916]."""
    o = _stock_order(db, s)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    db.expunge_all()
    with Recorder(db) as rec:
        result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    assert rec.locks_first("work_orders")
    # Then 3
    assert rec.locks("work_order_items")


# [claude] WOM-RI-10
def test_wom_ri_10__flushes_never_commits(db, s):
    """WOM-RI-10 — remove item flushes and never commits.
    Rules: remove_item R4."""
    o = _stamped(db, s)
    ln = mk_line(db, s, o, s.I1, "2")
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _ri(db, s, ln)
        # Then 1
        assert result.id == ln.id
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert reread(db, WorkOrderItem, ln.id).is_deleted is False


# [claude] WOM-RI-11
def test_wom_ri_11__started_keeps_approvals(db, s):
    """WOM-RI-11 — removing a line from a started order keeps its approvals.
    Rules: remove_item R5, R6 (draft only)."""
    o = _stock_order(db, s)
    a = mk_approver(db, s, o, s.U2, **APPROVED)
    ln = mk_line(db, s, o, s.I1, "2", uses_inventory=False)
    mk = mark(db)
    result = _ri(db, s, ln)
    # Then 1
    assert result.id == ln.id
    # Then 2
    ra = reread(db, WorkOrderApprover, a.id)
    assert ra.approved is True
    assert ra.approved_at == T0
    # Then 3
    assert ev(db, mk, o) == [("item_removed", "Removed Bolt")]


# [claude] WOM-GI-01
def test_wom_gi_01__live_lines_id_order(db, s):
    """WOM-GI-01 — the live lines of the order, in id order.
    Rules: get_items R1, R2."""
    o = mk_order(db, s, "1")
    l1 = mk_line(db, s, o, s.I1, "1")
    mk_line(db, s, o, s.I2, "1", **LINE_GONE(s))
    l2 = mk_line(db, s, o, s.I3, "1")
    p = mk_order(db, s, "2")
    mk_line(db, s, p, s.I1, "1")
    result = WOM.get_items(db, o.id, s.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [l1.id, l2.id]


# [claude] WOM-GI-02
def test_wom_gi_02__order_of_w2(db, s):
    """WOM-GI-02 — an order of W2 is not found.
    Rules: get_items R1."""
    o9 = _o9(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        WOM.get_items(db, o9.id, s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order with ID {o9.id} not found"


# [claude] WOM-GI-03
@xf(1273)
def test_wom_gi_03__include_deleted(db, s):
    """WOM-GI-03 — include_deleted also returns deleted lines.
    Rules: get_items R3 [BUG-1273]."""
    o = mk_order(db, s, "1")
    l1 = mk_line(db, s, o, s.I1, "1")
    lg = mk_line(db, s, o, s.I2, "1", **LINE_GONE(s))
    # Then 1
    result = WOM.get_items(db, o.id, s.W1.id, include_deleted=True)
    assert [ln.id for ln in result] == [l1.id, lg.id]


# [claude] WOM-GI-04
@xf(1272)
def test_wom_gi_04__order_by_sent(db, s):
    """WOM-GI-04 — the line query sends an ORDER BY.
    Rules: get_items R2 [BUG-1272]."""
    o = mk_order(db, s, "1")
    mk_line(db, s, o, s.I1, "1")
    db.expunge_all()
    with Recorder(db) as rec:
        result = WOM.get_items(db, o.id, s.W1.id)
    # Then 1
    assert len(result) == 1
    # Then 2
    sel = [st for st in rec.statements if st.lstrip().upper().startswith("SELECT") and "work_order_items" in st]
    assert any("ORDER BY" in st and "work_order_items.id" in st.split("ORDER BY", 1)[1] for st in sel)


# =========================================================================== #
# _apply_sheet_entry_lines / sheet_entry
# =========================================================================== #


def _asl(db, s, o, items, approvers):
    return WOM._apply_sheet_entry_lines(db, o, items=items, approvers=approvers, machine_id=s.M1.id, factory_id=s.F1.id,
                                        workspace_id=s.W1.id, user_id=s.U1.id)


# [claude] WOM-ASL-01
def test_wom_asl_01__item_dict_storage_line(db, s):
    """WOM-ASL-01 — an item dict becomes a storage Consume line of the factory.
    Rules: _apply_sheet_entry_lines R1."""
    o = _stamped(db, s)
    _asl(db, s, o, [{"item_id": s.I1.id, "quantity": 2}], [])
    # Then 1
    assert [(ln.item_id, ln.quantity, ln.uses_inventory, ln.source_location_type, ln.source_location_id, ln.action_type)
            for ln in rows_of(db, WorkOrderItem, work_order_id=o.id)] == [
        (s.I1.id, Decimal("2.00"), True, "storage", s.F1.id, "CONSUME")]


# [claude] WOM-ASL-02
def test_wom_asl_02__machine_source_default(db, s):
    """WOM-ASL-02 — a machine source with no id uses the entry's machine; a given id is kept.
    Rules: _apply_sheet_entry_lines R1."""
    o = _stamped(db, s)
    _asl(db, s, o, [{"item_id": s.I2.id, "quantity": 1, "source_location_type": "machine"},
                    {"item_id": s.I3.id, "quantity": 1, "source_location_type": "storage", "source_location_id": s.F2.id}],
         [])
    # Then 1
    assert [(ln.item_id, ln.source_location_type, ln.source_location_id)
            for ln in rows_of(db, WorkOrderItem, work_order_id=o.id)] == [
        (s.I2.id, "machine", s.M1.id), (s.I3.id, "storage", s.F2.id)]


# [claude] WOM-ASL-03
def test_wom_asl_03__action_and_replaced(db, s):
    """WOM-ASL-03 — a given action and replaced item are passed on.
    Rules: _apply_sheet_entry_lines R1."""
    o = _stamped(db, s)
    _asl(db, s, o, [{"item_id": s.I1.id, "quantity": 1, "action_type": "REPLACE", "replaced_item_id": s.I2.id}], [])
    # Then 1
    assert [(ln.action_type, ln.replaced_item_id) for ln in rows_of(db, WorkOrderItem, work_order_id=o.id)] == [
        ("REPLACE", s.I2.id)]


# [claude] WOM-ASL-04
def test_wom_asl_04__approver_with_slot(db, s):
    """WOM-ASL-04 — an approver dict is added with its slot.
    Rules: _apply_sheet_entry_lines R2."""
    o = mk_order(db, s, "1")
    _asl(db, s, o, [], [{"user_id": s.U2.id, "approver_slot": "QA"}])
    # Then 1
    assert [(a.user_id, a.approver_slot, a.assigned_by) for a in rows_of(db, WorkOrderApprover, work_order_id=o.id)] == [
        (s.U2.id, "QA", s.U1.id)]


# [claude] WOM-ASL-05
@xf(1206)
def test_wom_asl_05__existing_approver_409(db, s):
    """WOM-ASL-05 — an approver already on the order is a 409 that propagates.
    Rules: _apply_sheet_entry_lines R2 [BUG-1206]."""
    o = mk_order(db, s, "1")
    mk_approver(db, s, o, s.U2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _asl(db, s, o, [], [{"user_id": s.U2.id}])
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"


# [claude] WOM-ASL-06
def test_wom_asl_06__other_refusal_propagates(db, s):
    """WOM-ASL-06 — any other approver refusal propagates.
    Rules: _apply_sheet_entry_lines R2."""
    o = mk_order(db, s, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _asl(db, s, o, [], [{"user_id": s.U4.id}])
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"


# [claude] WOM-SE-01
def test_wom_se_01__entry_without_items(db, s):
    """WOM-SE-01 — an entry without items makes a draft that uses no stock.
    Rules: sheet_entry R3, R6, R10."""
    result = ENTRY(db, s, SHEET(s))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.title == "Service — Lathe 3"
    assert row.factory_id == s.F1.id
    assert row.machine_id == s.M1.id
    assert row.planned_date == D(12)
    assert row.status == "DRAFT"
    # Then 3
    assert row.uses_inventory is False
    assert row.work_order_template_id is None


# [claude] WOM-SE-02
def test_wom_se_02__machine_factory(db, s):
    """WOM-SE-02 — the factory is the machine's.
    Rules: sheet_entry R3."""
    result = ENTRY(db, s, SHEET(s, machine_id=s.M3.id))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.factory_id == s.F2.id
    assert row.title == "Service — Pump"


# [claude] WOM-SE-03
def test_wom_se_03__other_fields_stored(db, s):
    """WOM-SE-03 — the other entry fields are stored.
    Rules: sheet_entry R3."""
    result = ENTRY(db, s, SHEET(s, assigned_to="Sara Khan", description="Grease", priority=WorkOrderPriorityEnum.HIGH,
                                account_id=s.A1.id, cost=Decimal("250.00")))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, WorkOrder, result.id)
    assert row.assigned_to == "Sara Khan"
    assert row.description == "Grease"
    assert row.priority == WorkOrderPriorityEnum.HIGH
    assert row.account_id == s.A1.id
    assert row.cost == Decimal("250.00")


# [claude] WOM-SE-04
def test_wom_se_04__items_make_lines(db, s):
    """WOM-SE-04 — items make stock lines and an order that uses stock.
    Rules: sheet_entry R3, R5."""
    result = ENTRY(db, s, SHEET(s, items=[{"item_id": s.I1.id, "quantity": 2, "action_type": "CONSUME"}]))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrder, result.id).uses_inventory is True
    # Then 3
    assert [(ln.item_id, ln.quantity, ln.source_location_type, ln.source_location_id)
            for ln in rows_of(db, WorkOrderItem, work_order_id=result.id)] == [(s.I1.id, Decimal("2.00"), "storage", s.F1.id)]


# [claude] WOM-SE-05, WOM-SE-06
@pytest.mark.parametrize("which", [pytest.param("M9", id="WOM-SE-05"), pytest.param("M0", id="WOM-SE-06")])
def test_wom_se_05_06__foreign_machine(db, s, which):
    """WOM-SE-05 / WOM-SE-06 — a machine of W2 / W0 is not found.
    Rules: sheet_entry R1."""
    m = getattr(s, which)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, machine_id=m.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SE-07
@xf(2920)
def test_wom_se_07__deleted_machine(db, s):
    """WOM-SE-07 — a soft-deleted machine is not found.
    Rules: sheet_entry R1 [BUG-2920]."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old press", **GONE_MA))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, machine_id=md.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SE-08
def test_wom_se_08__type_of_w2(db, s):
    """WOM-SE-08 — a type of W2 is not found.
    Rules: sheet_entry R2."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, work_order_type_id=s.WT9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SE-09
@xf(1228)
def test_wom_se_09__deleted_type(db, s):
    """WOM-SE-09 — a soft-deleted type is not found.
    Rules: sheet_entry R2 [BUG-1228]."""
    wtd = mk_type(db, s, "Overhaul", **GONE_FT)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, work_order_type_id=wtd.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type not found"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SE-10
def test_wom_se_10__non_recurring_template_linked(db, s):
    """WOM-SE-10 — an active non-recurring template is linked and makes no drafts.
    Rules: sheet_entry R4, R8, R9."""
    t = mk_template(db, s)
    result = ENTRY(db, s, SHEET(s, template_id=t.id))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, WorkOrder, result.id).work_order_template_id == t.id
    # Then 3
    assert len(rows_of(db, WorkOrder, work_order_template_id=t.id)) == 1


# [claude] WOM-SE-11
def test_wom_se_11__template_of_w2(db, s):
    """WOM-SE-11 — a template of W2 is not found.
    Rules: sheet_entry R9."""
    t9 = mk_template(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT9.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, template_id=t9.id))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order template with ID {t9.id} not found"


# [claude] WOM-SE-12
@xf(2928)
def test_wom_se_12__inactive_template(db, s):
    """WOM-SE-12 — an inactive template is refused.
    Rules: sheet_entry R9 [BUG-2928]."""
    t = mk_template(db, s, is_active=False)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, template_id=t.id))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Template is inactive"
    # Then 4
    assert counts(db) == before


# [claude] WOM-SE-13
def test_wom_se_13__approvers_added(db, s):
    """WOM-SE-13 — approvers are added.
    Rules: sheet_entry R7."""
    result = ENTRY(db, s, SHEET(s, approvers=[{"user_id": s.U2.id}, {"user_id": s.U3.id, "approver_slot": "QA"}]))
    # Then 1
    assert result.id is not None
    # Then 2
    assert [(a.user_id, a.approver_slot) for a in rows_of(db, WorkOrderApprover, work_order_id=result.id)] == [
        (s.U2.id, None), (s.U3.id, "QA")]
    # Then 3
    assert reread(db, WorkOrder, result.id).approved_at is None


# [claude] WOM-SE-14
@xf(1206)
def test_wom_se_14__same_approver_twice_409(db, s):
    """WOM-SE-14 — the same approver twice is a 409.
    Rules: sheet_entry R7 [BUG-1206]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, approvers=[{"user_id": s.U2.id}, {"user_id": s.U2.id}]))
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"


# [claude] WOM-SE-15
def test_wom_se_15__inactive_approver_400(db, s):
    """WOM-SE-15 — an approver who is not an active member propagates 400.
    Rules: sheet_entry R7."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        ENTRY(db, s, SHEET(s, approvers=[{"user_id": s.U4.id}]))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"


# [claude] WOM-SE-16
def test_wom_se_16__recurring_template_seeds(db, s):
    """WOM-SE-16 — a recurring template placed with an end date seeds its drafts.
    Rules: sheet_entry R8; _maybe_seed_template_recurrence R3."""
    t = mk_template(db, s, **WEEKLY)
    result = ENTRY(db, s, SHEET(s, planned_date=D(2), template_id=t.id, recurrence_end_date=D(16)))
    # Then 1
    assert result.planned_date == D(2)
    # Then 2
    assert sorted((o.planned_date, o.machine_id, o.status)
                  for o in rows_of(db, WorkOrder, work_order_template_id=t.id, is_deleted=False)) == [
        (D(2), s.M1.id, "DRAFT"), (D(9), s.M1.id, "DRAFT"), (D(16), s.M1.id, "DRAFT")]


# [claude] WOM-SE-17
@xf(2912)
def test_wom_se_17__negative_sheet_line_schema(s):
    """WOM-SE-17 — a negative sheet line quantity is refused by the schema.
    Rules: sheet_entry Inputs; P1 [BUG-2912]."""
    from app.schemas.work_order import WorkOrderSheetItemLine
    # Then 1
    with pytest.raises(ValidationError) as exc:
        WorkOrderSheetItemLine(item_id=s.I1.id, quantity=Decimal("-1"))
    # Then 2
    assert "quantity" in str(exc.value)


# [claude] WOM-SE-18
@xf(2912)
def test_wom_se_18__negative_sheet_cost_schema(s):
    """WOM-SE-18 — a negative sheet entry cost is refused by the schema.
    Rules: sheet_entry Inputs; P1 [BUG-2912]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        SHEET(s, cost=Decimal("-5"))
    # Then 2
    assert "cost" in str(exc.value)


# [claude] WOM-SE-19
def test_wom_se_19__flushes_never_commits(db, s):
    """WOM-SE-19 — sheet entry flushes and never commits.
    Rules: sheet_entry R10."""
    data = SHEET(s)
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = ENTRY(db, s, data)
        # Then 1
        assert result.id is not None
        # Then 2
        assert cm.call_count == 0
        sp.rollback()
    # Then 3
    assert _wo_count(db, s.W1) == 0


# =========================================================================== #
# sync_recurrence_drafts_for_machine / _maybe_seed_template_recurrence / sheet lists
# =========================================================================== #


def _anchored(db, s, start, end, nxt):
    """`T = template, but weekly, recurrence_start_date …, recurrence_end_date …, next_generation_date …`."""
    return mk_template(db, s, **WEEKLY, recurrence_start_date=start, recurrence_end_date=end, next_generation_date=nxt)


def _live_template_orders(db, t):
    return rows_of(db, WorkOrder, work_order_template_id=t.id, is_deleted=False)


def _srd(db, s, t):
    return WOM.sync_recurrence_drafts_for_machine(db, workspace_id=s.W1.id, user_id=s.U2.id, template=t,
                                                   machine_id=s.M1.id, range_start=D(2), range_end=D(9))


# [claude] WOM-SRD-01
def test_wom_srd_01__outside_deleted_range_regenerated(db, s):
    """WOM-SRD-01 — drafts outside the range are soft-deleted; the range is regenerated.
    Rules: sync_recurrence_drafts_for_machine R1, R2."""
    t = _anchored(db, s, D(2), D(9), D(9))
    oa = mk_order(db, s, "a", work_order_template_id=t.id, planned_date=date(2026, 2, 23))
    oc = mk_order(db, s, "c", work_order_template_id=t.id, planned_date=D(9))
    ob = mk_order(db, s, "b", work_order_template_id=t.id, planned_date=D(16))
    _srd(db, s, t)
    # Then 1
    ra = reread(db, WorkOrder, oa.id)
    assert ra.is_deleted is True
    assert ra.deleted_by == s.U2.id
    # Then 2
    rb = reread(db, WorkOrder, ob.id)
    assert rb.is_deleted is True
    assert rb.deleted_by == s.U2.id
    # Then 3
    assert reread(db, WorkOrder, oc.id).is_deleted is False
    # Then 4
    assert len(_live_template_orders(db, t)) == 1
    # Then 5
    assert reread(db, WorkOrderTemplate, t.id).next_generation_date == D(16)


# [claude] WOM-SRD-02
def test_wom_srd_02__started_and_other_machines_left(db, s):
    """WOM-SRD-02 — started orders and other machines' drafts are left alone.
    Rules: sync_recurrence_drafts_for_machine R1."""
    t = _anchored(db, s, D(2), D(9), D(9))
    oc = mk_order(db, s, "c", work_order_template_id=t.id, planned_date=D(9))
    ip = mk_order(db, s, "d", **{**STARTED(s), "work_order_template_id": t.id, "planned_date": D(16)})
    om = mk_order(db, s, "e", work_order_template_id=t.id, planned_date=D(16), machine_id=s.M2.id)
    bip, bom = snap(db, ip), snap(db, om)
    _srd(db, s, t)
    # Then 1
    assert snap(db, ip) == bip
    # Then 2
    assert snap(db, om) == bom
    # Then 3
    assert reread(db, WorkOrder, oc.id).is_deleted is False


def _msr(db, s, t, end, planned=None):
    return WOM._maybe_seed_template_recurrence(db, template_id=t.id, workspace_id=s.W1.id, user_id=s.U2.id,
                                               machine_id=s.M1.id, planned_date=planned or D(2), recurrence_end_date=end)


# [claude] WOM-MSR-01
def test_wom_msr_01__not_recurring_nothing(db, s):
    """WOM-MSR-01 — a template that does not recur does nothing.
    Rules: _maybe_seed_template_recurrence R1."""
    t = mk_template(db, s)
    bt = snap(db, t)
    before = counts(db)
    result = _msr(db, s, t, D(16))
    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t) == bt
    # Then 3
    assert counts(db) == before


# [claude] WOM-MSR-02
def test_wom_msr_02__template_of_w2(db, s):
    """WOM-MSR-02 — a template of W2 is not found.
    Rules: _maybe_seed_template_recurrence R1."""
    t9 = mk_template(db, s, workspace_id=s.W2.id, work_order_type_id=s.WT9.id, **WEEKLY)
    bt = snap(db, t9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _msr(db, s, t9, D(16))
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order template with ID {t9.id} not found"
    # Then 4
    assert snap(db, t9) == bt


# [claude] WOM-MSR-03
def test_wom_msr_03__unanchored_without_end(db, s):
    """WOM-MSR-03 — an unanchored recurring template without an end date is refused.
    Rules: _maybe_seed_template_recurrence R2."""
    t = mk_template(db, s, **WEEKLY)
    bt = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _msr(db, s, t, None)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "recurrence_end_date is required when placing an unanchored recurring template"
    # Then 4
    assert snap(db, t) == bt


# [claude] WOM-MSR-04
def test_wom_msr_04__anchored_without_end_nothing(db, s):
    """WOM-MSR-04 — an anchored template without an end date does nothing.
    Rules: _maybe_seed_template_recurrence R2."""
    t = _anchored(db, s, D(2), D(16), D(9))
    bt = snap(db, t)
    before = counts(db)
    result = _msr(db, s, t, None)
    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t) == bt
    # Then 3
    assert counts(db) == before


# [claude] WOM-MSR-05
def test_wom_msr_05__unanchored_anchored_and_drafts(db, s):
    """WOM-MSR-05 — an unanchored template is anchored on the placement and its drafts are made.
    Rules: _maybe_seed_template_recurrence R3."""
    t = mk_template(db, s, **WEEKLY)
    result = _msr(db, s, t, D(16))
    # Then 1
    assert result is None
    # Then 2
    rt = reread(db, WorkOrderTemplate, t.id)
    assert rt.recurrence_start_date == D(2)
    assert rt.recurrence_end_date == D(16)
    assert rt.recurrence_day is None
    assert rt.next_generation_date == D(23)
    # Then 3
    assert sorted(o.planned_date for o in _live_template_orders(db, t)) == [D(9), D(16)]


# [claude] WOM-MSR-06
def test_wom_msr_06__over_183_days(db, s):
    """WOM-MSR-06 — a range over 183 days is refused with the recurrence message.
    Rules: _maybe_seed_template_recurrence R3."""
    t = mk_template(db, s, **WEEKLY)
    bt = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _msr(db, s, t, date(2026, 9, 30))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Recurrence range cannot exceed 183 days (~6 months)"
    # Then 4
    assert snap(db, t) == bt
    # Then 5
    assert len(rows_of(db, WorkOrder, work_order_template_id=t.id)) == 0


# [claude] WOM-MSR-07
def test_wom_msr_07__same_anchor_nothing(db, s):
    """WOM-MSR-07 — the same start and end as the anchor does nothing.
    Rules: _maybe_seed_template_recurrence R4."""
    t = _anchored(db, s, D(2), D(16), D(9))
    bt = snap(db, t)
    before = counts(db)
    result = _msr(db, s, t, D(16))
    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t) == bt
    # Then 3
    assert counts(db) == before


# [claude] WOM-MSR-08
def test_wom_msr_08__reanchor_drops_outside(db, s):
    """WOM-MSR-08 — a new range re-anchors the template and drops drafts outside it.
    Rules: _maybe_seed_template_recurrence R5; sync_recurrence_drafts_for_machine R1, R2."""
    t = _anchored(db, s, D(2), D(16), D(23))
    o9 = mk_order(db, s, "9", work_order_template_id=t.id, planned_date=D(9))
    o16 = mk_order(db, s, "16", work_order_template_id=t.id, planned_date=D(16))
    result = _msr(db, s, t, D(9))
    # Then 1
    assert result is None
    # Then 2
    rt = reread(db, WorkOrderTemplate, t.id)
    assert rt.recurrence_end_date == D(9)
    assert rt.next_generation_date == D(16)
    # Then 3
    r16 = reread(db, WorkOrder, o16.id)
    assert r16.is_deleted is True
    assert r16.deleted_by == s.U2.id
    # Then 4
    assert reread(db, WorkOrder, o9.id).is_deleted is False
    # Then 5
    assert len(_live_template_orders(db, t)) == 1


# [claude] WOM-MSR-09
def test_wom_msr_09__reanchor_over_183_days(db, s):
    """WOM-MSR-09 — a re-anchor over 183 days is refused.
    Rules: _maybe_seed_template_recurrence R5."""
    t = _anchored(db, s, D(2), D(16), D(23))
    bt = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _msr(db, s, t, date(2026, 9, 30))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Recurrence range cannot exceed 183 days (~6 months)"
    # Then 4
    assert snap(db, t) == bt


# [claude] WOM-SH-01
def test_wom_sh_01__sheet_lists_workspace(db, s):
    """WOM-SH-01 — the sheet lists the workspace's orders.
    Rules: list_sheet_orders R1."""
    o = mk_order(db, s, "1")
    _o9(db, s)
    result = WOM.list_sheet_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert [x.id for x in result] == [o.id]


# [claude] WOM-SH-02
def test_wom_sh_02__default_limit_50(db, s):
    """WOM-SH-02 — the sheet list holds 50 rows by default.
    Rules: list_sheet_orders R1."""
    for k in range(1, 52):
        mk_order(db, s, str(k))
    result = WOM.list_sheet_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 50


# [claude] WOM-SH-03
def test_wom_sh_03__count_workspace(db, s):
    """WOM-SH-03 — the sheet count counts the workspace's orders.
    Rules: count_sheet_orders R1."""
    mk_order(db, s, "1")
    mk_order(db, s, "2")
    _o9(db, s)
    result = WOM.count_sheet_orders(db, workspace_id=s.W1.id)
    # Then 1
    assert result == 2


# [claude] WOM-SH-04
def test_wom_sh_04__daily_counts_iso_keys(db, s):
    """WOM-SH-04 — daily counts are keyed by ISO date text.
    Rules: sheet_daily_counts R2."""
    mk_order(db, s, "1", planned_date=D(10))
    mk_order(db, s, "2", planned_date=D(10))
    mk_order(db, s, "3", planned_date=D(12))
    result = WOM.sheet_daily_counts(db, workspace_id=s.W1.id)
    # Then 1
    assert result == {"2026-03-10": 2, "2026-03-12": 1}


# [claude] WOM-SH-05
def test_wom_sh_05__no_orders_empty(db, s):
    """WOM-SH-05 — no orders give an empty dict.
    Rules: sheet_daily_counts R2."""
    result = WOM.sheet_daily_counts(db, workspace_id=s.W1.id)
    # Then 1
    assert result == {}


def _sheet_filter_given(db, s):
    o = mk_order(db, s, "1")
    mk_order(db, s, "2", factory_id=s.F2.id, machine_id=s.M3.id)
    mk_order(db, s, "3", planned_date=D(20))
    mk_order(db, s, "4", work_order_type_id=s.WT2.id)
    return o


def _sheet_filters(s):
    return {"factory_id": s.F1.id, "machine_id": s.M1.id, "planned_date_from": D(10), "planned_date_to": D(14),
            "work_order_type_id": s.WT1.id, "priority": WorkOrderPriorityEnum.MEDIUM}


# [claude] WOM-SH-06
def test_wom_sh_06__list_filters(db, s):
    """WOM-SH-06 — the sheet list passes its filters by keyword.
    Rules: list_sheet_orders R0, R1."""
    o = _sheet_filter_given(db, s)
    result = WOM.list_sheet_orders(db, workspace_id=s.W1.id, **_sheet_filters(s), skip=0, limit=10)
    # Then 1
    assert [x.id for x in result] == [o.id]


# [claude] WOM-SH-07
def test_wom_sh_07__count_filters(db, s):
    """WOM-SH-07 — the sheet count passes the same filters.
    Rules: count_sheet_orders R0, R1."""
    _sheet_filter_given(db, s)
    result = WOM.count_sheet_orders(db, workspace_id=s.W1.id, **_sheet_filters(s))
    # Then 1
    assert result == 1


# [claude] WOM-SH-08
def test_wom_sh_08__daily_filters(db, s):
    """WOM-SH-08 — daily counts pass their filters.
    Rules: sheet_daily_counts R0, R2."""
    _sheet_filter_given(db, s)
    result = WOM.sheet_daily_counts(db, workspace_id=s.W1.id, **_sheet_filters(s))
    # Then 1
    assert result == {"2026-03-12": 1}


# [claude] WOM-SH-09
def test_wom_sh_09__exclude_completed_default():
    """WOM-SH-09 — the sheet list and count do not exclude completed orders by default.
    Rules: list_sheet_orders · count_sheet_orders R0 (signature, G11)."""
    import inspect
    result = [inspect.signature(f).parameters["exclude_completed"].default
              for f in (WOM.list_sheet_orders, WOM.count_sheet_orders)]
    # Then 1
    assert result == [False, False]
    assert all(r is False for r in result)
