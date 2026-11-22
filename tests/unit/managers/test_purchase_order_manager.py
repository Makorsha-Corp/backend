"""Unit tests for app/managers/purchase_order_manager.py.

Implements tests/unit/managers/purchase_order_manager.cases.md (revision 4,
2026-11-21), one test per case, in card order. Real Postgres session (`db`
fixture, rolled back after each test). Externals: none is mocked; time only
through the `clock` convention (`app.managers.purchase_order_manager.utcnow`),
and WF-05 / WF-06 patch `ensure_po_workflow_record` as their cards say. No race
simulations.

Built in normal mode (no local model): every test sits below a
`# [claude] <ID>` comment and has one `# Then N` comment per Then line.
DISCREPANCY-1 and DISCREPANCY-2 of revision 2 are resolved in revision 3; GI-04 retired in revision 4
(see the notes).
"""

# ruff: noqa: DTZ001, DTZ011, FURB157  (Conventions prescribe naive datetimes, date.today() and Decimal("q") literals)
import inspect
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
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.managers.purchase_order_manager import (
    _all_items_have_positive_unit_price,
    _line_subtotal,
    _parse_unit_price,
    purchase_order_manager,
)
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.invoice_item import InvoiceItem
from app.models.item import Item
from app.models.machine import Machine
from app.models.order_workflow import OrderWorkflow
from app.models.po_receive_event import PoReceiveEvent
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import PurchaseOrderReturn
from app.models.status import Status
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderItemSyncRequest,
    PurchaseOrderItemSyncUpdate,
    PurchaseOrderItemUpdate,
    PurchaseOrderUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> actors and fixed values
# --------------------------------------------------------------------------- #

# Convention "M"
M = purchase_order_manager
# Convention "IC"
IC = PurchaseOrderItemCreate

# Convention "MISSING"
MISSING = 999999999

# Conventions "T0", "T1 ... T4", "D1 ... D3", "NOW" (naive)
T0 = datetime(2026, 3, 1, 8, 0)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)
T3 = datetime(2026, 3, 4, 11, 0)
T4 = datetime(2026, 3, 4, 12, 0)
D1 = date(2026, 3, 2)
D2 = date(2026, 3, 20)
D3 = date(2026, 4, 15)
NOW = datetime(2026, 5, 6, 7, 8, 9)

# Long dash (U+2014) used in several texts
DASH = "—"

# xfail reasons: bug titles from docs/testing/bugs.md
X2872 = "BUG-2872: Purchase order state checks run on an unlocked read"
X2873 = "BUG-2873: A purchase order update stamps `updated_by` when nothing changed"
X2874 = "BUG-2874: A PO destination can be another workspace's (or a deleted) factory or machine"
X2875 = "BUG-2875: A PO stage-change log entry can show another workspace's status name"
X2876 = "BUG-2876: PO total is summed from unrounded line subtotals"
X2877 = "BUG-2877: PO lines accept zero / negative quantities and negative prices; approval threshold accepts negatives"
X2878 = "BUG-2878: PO quantities and prices with > 2 decimals or >= 10^13 accepted"
X2879 = "BUG-2879: A purchase order edit cannot clear a field"
X2880 = "BUG-2880: Approving a PO twice, or withdrawing when not approved, is recorded again"
X2881 = "BUG-2881: PO approvers can change after the invoice is finalized or the order is complete"
X2882 = "BUG-2882: A voided purchase order can still be edited, approved, completed and given lines"
X2883 = "BUG-2883: PO activity log and approvers list read one profile per row"
X2885 = "BUG-2885: A completed PO still accepts edits to expected delivery date and approval threshold"
X2886 = "BUG-2886: Lines of a missing purchase order answer an empty list"
X2887 = "BUG-2887: The PO line edit changes a received quantity without moving stock"
X2888 = "BUG-2888: Deleting a PO leaves its invoice behind"
X1017 = "BUG-1017: Purchase order accepts another workspace's supplier, invoice and items"
X1192 = "BUG-1192: Activity row can be written for another workspace's order, project or component"
X1195 = "BUG-1195: Deleted purchase order vanishes without trace"
X1200 = "BUG-1200: Approvers with one `assigned_at` come back in no fixed order"
X1202 = "BUG-1202: Purchase order with no approvers counts as fully approved"
X1881 = "BUG-1881: Purchase order code finds stage statuses only by exact spelling"
X2637 = "BUG-2637: PO found for an invoice is arbitrary when two POs share it"
X2789 = "BUG-2789: Starting a purchase return reopens a completed order"


def xf(*reasons):
    """Convention "xfail BUG-n" (strict)."""
    return pytest.mark.xfail(strict=True, reason="; ".join(reasons))


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def s(db):
    """Convention "Standing rows" 1-4 and TAG. `s.W1`, `s.SD1`, `s.A9`, ..."""
    r = SimpleNamespace()
    r.TAG = uuid.uuid4().hex[:8]
    r.TODAY = date.today()
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    names = ("Alice Rahman", "Bob Karim", "Chitra Das", "Dev Paul", "Esha Roy")
    for i, name in enumerate(names, start=1):
        setattr(r, f"U{i}", make_profile(db, name=name))
    for user, ws, st, pos in (
        (r.U1, r.W1, "active", "Buyer"),
        (r.U2, r.W1, "active", None),
        (r.U4, r.W1, "invited", None),
        (r.U5, r.W1, "inactive", None),
        (r.U3, r.W2, "active", "Boss"),
    ):
        _add(db, WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="member", status=st, position=pos))
    accounts = {"0": "Northwind West", "1": "Northwind Traders", "9": "Northwind East"}
    for k, ws in (("0", r.W0), ("1", r.W1), ("9", r.W2)):
        for prefix, stage in (("SD", "Draft"), ("SP", "Planning"), ("SR", "Receiving"), ("SC", "Complete")):
            setattr(r, prefix + k, _add(db, Status(workspace_id=ws.id, name=stage, comment="po stage")))
        seq = [getattr(r, p + k).id for p in ("SD", "SP", "SR", "SC")]
        setattr(r, "WF" + k, _add(db, OrderWorkflow(workspace_id=ws.id, name="Purchase Order", type="purchase", status_sequence=seq)))
        f = _add(db, Factory(workspace_id=ws.id, name="Main Plant", abbreviation=f"MP{k}"))
        setattr(r, "F" + k, f)
        setattr(r, "M" + k, _add(db, Machine(workspace_id=ws.id, factory_id=f.id, name=f"Press {k}")))
        setattr(r, "A" + k, _add(db, Account(workspace_id=ws.id, name=accounts[k])))
        setattr(r, "I" + k, _add(db, Item(workspace_id=ws.id, name="Bolt", name_normalized="bolt", unit="pcs")))
    r.A3 = _add(db, Account(workspace_id=r.W1.id, name="Alpha Parts"))
    r.I2 = _add(db, Item(workspace_id=r.W1.id, name="Nut", name_normalized="nut", unit="pcs"))
    r.I3 = _add(db, Item(workspace_id=r.W1.id, name="Washer", name_normalized="washer", unit="pcs"))
    r.PJ1 = _add(db, Project(workspace_id=r.W1.id, factory_id=r.F1.id, name="Project 1", description="Main"))
    r.C1 = _add(db, ProjectComponent(workspace_id=r.W1.id, project_id=r.PJ1.id, name="Part 1"))
    r.WS = {"0": r.W0, "1": r.W1, "9": r.W2}
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def mk_po(db, s, n, k="1", **cols):
    """Convention "po "n"" ("po of W0 / W9" with k="0" / "9"); `cols` = the columns after "but"."""
    fields = {
        "workspace_id": s.WS[k].id,
        "po_number": f"PO-{s.TAG}-{n}",
        "account_id": getattr(s, "A" + k).id,
        "destination_type": "storage",
        "destination_id": getattr(s, "F" + k).id,
        "order_date": D1,
        "subtotal": Decimal("0.00"),
        "total_amount": Decimal("0.00"),
        "current_status_id": getattr(s, "SD" + k).id,
        "order_workflow_id": getattr(s, "WF" + k).id,
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, PurchaseOrder(**fields))


def stage(x):
    """Convention "stage X"."""
    return {"current_status_id": x.id}


def confirmed(s):
    """Convention "confirmed"."""
    return {"supplier_confirmed": True, "details_confirmed": True, "items_confirmed": True, "current_status_id": s.SP1.id}


def locked_by(s, v):
    """Convention "locked by V"."""
    return {
        "invoice_id": v.id,
        "invoice_ever_linked": True,
        "supplier_confirmed": True,
        "details_confirmed": True,
        "items_confirmed": True,
        "invoice_confirmed": True,
        "current_status_id": s.SR1.id,
    }


def complete_by(s, v):
    """Convention "complete by V"."""
    return {**locked_by(s, v), "current_status_id": s.SC1.id, "actual_delivery_date": D2}


def voided(s):
    """Convention "voided" (the confirms stay as the card gives them)."""
    return {"voided": True, "voided_at": T4, "voided_by": s.U1.id, "void_note": "Entered twice", "invoice_id": None}


def mk_line(db, o, k, item, **cols):
    """Convention "line k of O, I"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": o.workspace_id,
        "purchase_order_id": o.id,
        "line_number": k,
        "item_id": item.id,
        "quantity_ordered": Decimal("10.00"),
        "quantity_received": Decimal("0.00"),
        "unit_price": Decimal("2.00"),
        "line_subtotal": Decimal("20.00"),
    }
    fields.update(cols)
    return _add(db, PurchaseOrderItem(**fields))


def mk_invl(db, v, **cols):
    """Convention "invl(V)"."""
    fields = {
        "workspace_id": v.workspace_id,
        "invoice_id": v.id,
        "line_number": 1,
        "description": "Line",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("2.00"),
        "line_subtotal": Decimal("2.00"),
    }
    fields.update(cols)
    return _add(db, InvoiceItem(**fields))


def mk_inv(db, s, st, p, k="1", **cols):
    """Convention "inv(s, p)" ("of W9" with k="9")."""
    fields = {
        "workspace_id": s.WS[k].id,
        "account_id": getattr(s, "A" + k).id,
        "invoice_type": "payable",
        "invoice_status": st,
        "payment_status": p,
        "invoice_amount": Decimal("100.00"),
        "paid_amount": Decimal("0.00"),
        "invoice_date": D1,
        "allow_payments": True,
    }
    fields.update(cols)
    return _add(db, AccountInvoice(**fields))


def mk_appr(db, s, o, u, **cols):
    """Convention "appr(O, U)"."""
    fields = {
        "workspace_id": o.workspace_id,
        "purchase_order_id": o.id,
        "user_id": u.id,
        "assigned_by": s.U1.id,
        "approved": False,
        "approved_at": None,
        "assigned_at": T1,
    }
    fields.update(cols)
    return _add(db, PurchaseOrderApprover(**fields))


# Convention "approved" (on an approver)
APPROVED = {"approved": True, "approved_at": T2}


def mk_ret(db, s, o, n, **cols):
    """Convention "ret(O, "n")"."""
    fields = {
        "workspace_id": o.workspace_id,
        "purchase_order_id": o.id,
        "return_number": f"PR-{s.TAG}-{n}",
        "return_type": "refund",
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, PurchaseOrderReturn(**fields))


def ret_completed(s):
    """Convention "completed" (on a return)."""
    return {"status": "completed", "completed_at": T3, "completed_by": s.U1.id}


# Convention "cancelled" (on a return)
RET_CANCELLED = {"status": "voided"}


def mk_rev(db, o, **cols):
    """Convention "rev(O)"."""
    fields = {"workspace_id": o.workspace_id, "purchase_order_id": o.id, "event_type": "receive", "created_at": T0}
    fields.update(cols)
    return _add(db, PoReceiveEvent(**fields))


def mk_evt(db, s, o, at, **cols):
    """Convention "evt(O, at)"."""
    fields = {
        "workspace_id": o.workspace_id,
        "purchase_order_id": o.id,
        "event_type": "created",
        "description": "Logged",
        "performed_by": s.U1.id,
        "created_at": at,
    }
    fields.update(cols)
    return _add(db, PurchaseOrderEvent(**fields))


def deleted_factory(s):
    """Convention "deleted factory"."""
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": s.U1.id}


def deleted_machine(s):
    """Convention "deleted machine"."""
    return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": s.U1.id}


def mk_wx(db):
    """Convention "WX"."""
    return make_workspace(db)


def stx(db, wx, name):
    """Convention "stX(name)"."""
    return _add(db, Status(workspace_id=wx.id, name=name, comment="po stage"))


def mk_pox(db, s, wx, st, wf, **cols):
    """Card shorthand "OX = PurchaseOrder(workspace_id=WX.id, po_number=f"PO-{TAG}-X", ...)"
    of SS-06 / SS-09 (account None, factory F1, given status and workflow)."""
    fields = {
        "workspace_id": wx.id,
        "po_number": f"PO-{s.TAG}-X",
        "account_id": None,
        "destination_type": "storage",
        "destination_id": s.F1.id,
        "order_date": D1,
        "subtotal": Decimal("0.00"),
        "total_amount": Decimal("0.00"),
        "current_status_id": st.id,
        "order_workflow_id": wf.id,
        "created_by": s.U1.id,
    }
    fields.update(cols)
    return _add(db, PurchaseOrder(**fields))


def mem(**attrs):
    """Convention "mem(...)": an in-memory line, never added to the session."""
    return PurchaseOrderItem(**attrs)


def SYNC(remove_ids=(), updates=(), additions=()):
    """Convention "SYNC(remove_ids=..., updates=..., additions=...)"."""
    return PurchaseOrderItemSyncRequest(remove_ids=list(remove_ids), updates=list(updates), additions=list(additions))


def DEL(db, s, po_id):
    """Convention "DEL(id)": `user_id=U2.id` only once the parameter exists."""
    kwargs = {"po_id": po_id, "workspace_id": s.W1.id}
    if "user_id" in inspect.signature(M.delete_purchase_order).parameters:
        kwargs["user_id"] = s.U2.id
    return M.delete_purchase_order(db, **kwargs)


def clock():
    """Convention "clock"."""
    return patch("app.managers.purchase_order_manager.utcnow", return_value=NOW)


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #


def reread(db, model, row_id):
    """Convention "re-read X": expire, then SELECT X by id."""
    db.expire_all()
    return db.scalar(select(model).where(model.id == row_id))


def snap(db, row):
    """Convention "unchanged(X)": every column of X, read fresh."""
    model = type(row)
    fresh = reread(db, model, row.id)
    return {c.key: getattr(fresh, c.key) for c in sa_inspect(model).mapper.column_attrs}


def gone(db, row):
    """Convention "gone(X)" (the id is taken from the identity key, so a deleted row is not reloaded)."""
    row_id = sa_inspect(row).identity[0]
    db.expire_all()
    return db.get(type(row), row_id) is None


def EV(db, o):
    """Convention "EV(O)"."""
    db.expire_all()
    return list(
        db.scalars(
            select(PurchaseOrderEvent)
            .where(PurchaseOrderEvent.purchase_order_id == o.id)
            .order_by(PurchaseOrderEvent.id)
        )
    )


def types(db, o):
    """Convention "types(O)"."""
    return [e.event_type for e in EV(db, o)]


def LINES(db, o):
    """Convention "LINES(O)"."""
    db.expire_all()
    return list(
        db.scalars(
            select(PurchaseOrderItem)
            .where(PurchaseOrderItem.purchase_order_id == o.id)
            .order_by(PurchaseOrderItem.line_number)
        )
    )


_COUNTED = (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderApprover,
    PurchaseOrderEvent,
    Status,
    OrderWorkflow,
    AccountInvoice,
    WorkspaceAuditLog,
)


def counts(db):
    """Convention "nothing written": row counts of the eight tables, all workspaces."""
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in _COUNTED)


def assert_session_clean(db):
    """Convention "session clean": three asserts, before anything is re-read."""
    assert not db.new
    assert not db.dirty
    assert not db.deleted


def status_names(db, ws):
    """The names of a workspace's `statuses` rows, sorted."""
    db.expire_all()
    return sorted(db.scalars(select(Status.name).where(Status.workspace_id == ws.id)))


def status_count(db, ws, name=None):
    """Count of a workspace's `statuses` rows (named `name` if given)."""
    q = select(func.count()).select_from(Status).where(Status.workspace_id == ws.id)
    if name is not None:
        q = q.where(Status.name == name)
    return db.scalar(q)


def status_id(db, ws, name):
    """The id of a workspace's status named `name`."""
    db.expire_all()
    return db.scalar(select(Status.id).where(Status.workspace_id == ws.id, Status.name == name))


def purchase_workflows(db, ws):
    """A workspace's `order_workflows` rows with `type "purchase"`."""
    db.expire_all()
    return list(
        db.scalars(select(OrderWorkflow).where(OrderWorkflow.workspace_id == ws.id, OrderWorkflow.type == "purchase"))
    )


def approver_count(db, o):
    """Count of O's `purchase_order_approvers` rows."""
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(PurchaseOrderApprover).where(PurchaseOrderApprover.purchase_order_id == o.id)
    )


def approvers_of(db, o):
    """O's `purchase_order_approvers` rows by id."""
    db.expire_all()
    return list(
        db.scalars(
            select(PurchaseOrderApprover)
            .where(PurchaseOrderApprover.purchase_order_id == o.id)
            .order_by(PurchaseOrderApprover.id)
        )
    )


def hide_purchase_workflows(db):
    """Card step `UPDATE order_workflows SET type = 'purchase-hidden' WHERE type = 'purchase'`."""
    db.execute(text("UPDATE order_workflows SET type = 'purchase-hidden' WHERE type = 'purchase'"))


def commit_spy(db, call):
    """Convention "commit spy": returns `cm.call_count` (savepoint rolled back after)."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        call()
    n = cm.call_count
    sp.rollback()
    return n


class Recorder:
    """Convention "Statement recorder": the SQL the session's connection sends
    from `start()` (the start of the When) until `stop()`."""

    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []
        self.on = False

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def start(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        self.on = True
        return self

    def stop(self):
        if self.on:
            event.remove(self.bind, "before_cursor_execute", self._record)
            self.on = False

    @property
    def selects(self):
        return [st for st in self.statements if st.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [st for st in self.statements if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sel(self, table):
        """The SELECTs whose FROM names `table`."""
        return [st for st in self.selects if table in _from_tables(st)]

    def locks_first(self, table="purchase_orders"):
        """Convention "locks O first"."""
        first_write = self.written[0] if self.written else None
        cut = self.statements.index(first_write) if first_write is not None else len(self.statements)
        for st in self.statements[:cut]:
            flat = " ".join(st.split()).upper()
            if (
                flat.startswith("SELECT")
                and table in _from_tables(st)
                and "FOR UPDATE" in flat
                and "SKIP LOCKED" not in flat
                and "NOWAIT" not in flat
            ):
                return True
        return False


_FROM_END = re.compile(r"\b(WHERE|ORDER BY|GROUP BY|LIMIT|OFFSET|FOR UPDATE|HAVING)\b")


def _from_tables(statement):
    """The table names in the FROM part of a SELECT (joins included)."""
    flat = " ".join(statement.split())
    if " FROM " not in flat:
        return set()
    from_part = flat.split(" FROM ", 1)[1]
    stop = _FROM_END.search(from_part)
    if stop:
        from_part = from_part[: stop.start()]
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", from_part))


@contextmanager
def recording(db):
    """Turn the statement recorder on for the When only."""
    rec = Recorder(db).start()
    try:
        yield rec
    finally:
        rec.stop()


# =========================================================================== #
# Module functions _parse_unit_price, _line_subtotal, _all_items_have_positive_unit_price
# =========================================================================== #


# [claude] POM-PU-01
def test_pom_pu_01__no_price_gives_none():
    """POM-PU-01 — no price gives None.
    Rules: _parse_unit_price R1."""
    result = _parse_unit_price(None)
    # Then 1
    assert result is None


# [claude] POM-PU-02
def test_pom_pu_02__decimal_keeps_scale():
    """POM-PU-02 — a Decimal keeps its scale.
    Rules: _parse_unit_price R1."""
    result = _parse_unit_price(Decimal("5.00"))
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert str(result) == "5.00"


# [claude] POM-PU-03
def test_pom_pu_03__zero_is_a_price():
    """POM-PU-03 — zero is a price, not None.
    Rules: _parse_unit_price R1."""
    result = _parse_unit_price(0)
    # Then 1
    assert result is not None
    # Then 2
    assert result == Decimal("0")


# [claude] POM-PU-04
def test_pom_pu_04__float_goes_through_text():
    """POM-PU-04 — a float goes through its text.
    Rules: _parse_unit_price R1."""
    result = _parse_unit_price(2.5)
    # Then 1
    assert str(result) == "2.5"


# [claude] POM-LS-01
def test_pom_ls_01__unpriced_line_no_subtotal():
    """POM-LS-01 — an unpriced line has no subtotal.
    Rules: _line_subtotal R1."""
    result = _line_subtotal(Decimal("3.00"), None)
    # Then 1
    assert result is None


# [claude] POM-LS-02
def test_pom_ls_02__whole_cents_multiply_exactly():
    """POM-LS-02 — whole cents multiply exactly.
    Rules: _line_subtotal R2."""
    result = _line_subtotal(Decimal("2"), Decimal("3.50"))
    # Then 1
    assert result == Decimal("7.00")


# [claude] POM-LS-03
def test_pom_ls_03__zero_price_zero_subtotal():
    """POM-LS-03 — a zero price gives a zero subtotal, not None.
    Rules: _line_subtotal R1, R2."""
    result = _line_subtotal(Decimal("4"), Decimal("0"))
    # Then 1
    assert result is not None
    # Then 2
    assert result == Decimal("0")


# [claude] POM-LS-04
@xf(X2876)
def test_pom_ls_04__rounded_half_up_1_25():
    """POM-LS-04 — 1.25 x 0.10 is rounded half up to 0.13.
    Rules: _line_subtotal R2 [BUG-2876]."""
    result = _line_subtotal(Decimal("1.25"), Decimal("0.10"))
    # Then 1
    assert result == Decimal("0.13")


# [claude] POM-LS-05
@xf(X2876)
def test_pom_ls_05__rounded_half_up_0_5():
    """POM-LS-05 — 0.5 x 0.25 is rounded half up to 0.13.
    Rules: _line_subtotal R2 [BUG-2876]."""
    result = _line_subtotal(Decimal("0.5"), Decimal("0.25"))
    # Then 1
    assert result == Decimal("0.13")


# [claude] POM-PP-01
def test_pom_pp_01__no_lines_not_all_priced():
    """POM-PP-01 — no lines is not "all priced".
    Rules: _all_items_have_positive_unit_price R1."""
    result = _all_items_have_positive_unit_price([])
    # Then 1
    assert result is False


# [claude] POM-PP-02
def test_pom_pp_02__every_line_priced():
    """POM-PP-02 — every line priced above zero.
    Rules: _all_items_have_positive_unit_price R2."""
    a = mem(unit_price=Decimal("2.00"))
    b = mem(unit_price=Decimal("0.01"))
    result = _all_items_have_positive_unit_price([a, b])
    # Then 1
    assert result is True


# [claude] POM-PP-03
def test_pom_pp_03__one_unpriced_line_fails():
    """POM-PP-03 — one unpriced line fails the check.
    Rules: _all_items_have_positive_unit_price R2."""
    a = mem(unit_price=Decimal("2.00"))
    b = mem(unit_price=None)
    result = _all_items_have_positive_unit_price([a, b])
    # Then 1
    assert result is False


# [claude] POM-PP-04
def test_pom_pp_04__one_line_at_zero_fails():
    """POM-PP-04 — one line at 0.00 fails the check.
    Rules: _all_items_have_positive_unit_price R2."""
    a = mem(unit_price=Decimal("0.00"))
    b = mem(unit_price=Decimal("2.00"))
    result = _all_items_have_positive_unit_price([a, b])
    # Then 1
    assert result is False


# =========================================================================== #
# get_po_by_invoice_id
# =========================================================================== #


# [claude] POM-GI-01
def test_pom_gi_01__workspace_order_for_invoice(db, s):
    """POM-GI-01 — the workspace's order for the invoice.
    Rules: get_po_by_invoice_id R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = M.get_po_by_invoice_id(db, invoice_id=v.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == o.id


# [claude] POM-GI-02
def test_pom_gi_02__no_order_links_invoice(db, s):
    """POM-GI-02 — no order links the invoice.
    Rules: get_po_by_invoice_id R1."""
    v = mk_inv(db, s, "draft", "unpaid")
    mk_po(db, s, "1")
    result = M.get_po_by_invoice_id(db, invoice_id=v.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] POM-GI-03
def test_pom_gi_03__other_workspaces_orders_never_returned(db, s):
    """POM-GI-03 — orders of W0 and W2 on the same invoice are never returned.
    Rules: get_po_by_invoice_id R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    mk_po(db, s, "0", k="0", invoice_id=v.id)
    mk_po(db, s, "9", k="9", invoice_id=v.id)
    result = M.get_po_by_invoice_id(db, invoice_id=v.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] POM-GI-05
@xf(X2637)
def test_pom_gi_05__lookup_has_order_by(db, s):
    """POM-GI-05 — the lookup query has an ORDER BY.
    Rules: get_po_by_invoice_id R1 [BUG-2637]."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    v_id, o_id, w1_id = v.id, o.id, s.W1.id
    db.expunge_all()
    with recording(db) as rec:
        result = M.get_po_by_invoice_id(db, invoice_id=v_id, workspace_id=w1_id)
    # Then 1
    assert result.id == o_id
    # Then 2
    assert "ORDER BY" in rec.sel("purchase_orders")[0]


# =========================================================================== #
# is_po_financially_locked
# =========================================================================== #


# [claude] POM-FL-01
def test_pom_fl_01__no_invoice_not_locked(db, s):
    """POM-FL-01 — no invoice: not locked.
    Rules: is_po_financially_locked R1."""
    o = mk_po(db, s, "1")
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-02
def test_pom_fl_02__missing_invoice_id_not_locked(db, s):
    """POM-FL-02 — an invoice id that does not exist: not locked.
    Rules: is_po_financially_locked R1."""
    o = mk_po(db, s, "1")
    o.invoice_id = MISSING
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-03
def test_pom_fl_03__w2_confirmed_invoice_not_locked(db, s):
    """POM-FL-03 — a confirmed invoice of W2: not locked.
    Rules: is_po_financially_locked R1."""
    v9 = mk_inv(db, s, "confirmed", "unpaid", k="9")
    o = mk_po(db, s, "1", invoice_id=v9.id)
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-04
def test_pom_fl_04__w0_confirmed_invoice_not_locked(db, s):
    """POM-FL-04 — a confirmed invoice of W0: not locked.
    Rules: is_po_financially_locked R1."""
    v0 = _add(
        db,
        AccountInvoice(
            workspace_id=s.W0.id,
            account_id=s.A0.id,
            invoice_type="payable",
            invoice_status="confirmed",
            payment_status="unpaid",
            invoice_amount=Decimal("100.00"),
            paid_amount=Decimal("0.00"),
            invoice_date=D1,
            allow_payments=True,
        ),
    )
    o = mk_po(db, s, "1", invoice_id=v0.id)
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-05
def test_pom_fl_05__confirmed_invoice_locks(db, s):
    """POM-FL-05 — a confirmed invoice of the workspace locks.
    Rules: is_po_financially_locked R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is True


# [claude] POM-FL-06
def test_pom_fl_06__draft_invoice_does_not_lock(db, s):
    """POM-FL-06 — a draft invoice does not lock.
    Rules: is_po_financially_locked R2."""
    v = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-07
def test_pom_fl_07__voided_invoice_does_not_lock(db, s):
    """POM-FL-07 — a voided invoice does not lock.
    Rules: is_po_financially_locked R2."""
    v = mk_inv(db, s, "voided", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is False


# [claude] POM-FL-08
def test_pom_fl_08__completed_order_stays_locked(db, s):
    """POM-FL-08 — a completed order stays financially locked.
    Rules: is_po_financially_locked R2; RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    result = M.is_po_financially_locked(db, po=o)
    # Then 1
    assert result is True


# =========================================================================== #
# unlink_invoice_from_po
# =========================================================================== #


# [claude] POM-UL-01
def test_pom_ul_01__clears_link_logs_old_invoice(db, s):
    """POM-UL-01 — clears the link and logs the old invoice id.
    Rules: unlink_invoice_from_po R1, R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), paid=True)
    result = M.unlink_invoice_from_po(db, po=o, user_id=s.U2.id, reason="Invoice voided")
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.invoice_id is None
    assert row.invoice_confirmed is False
    assert row.paid is False
    # Then 2
    assert row.supplier_confirmed is True
    assert row.details_confirmed is True
    assert row.items_confirmed is True
    assert row.invoice_ever_linked is True
    # Then 3
    assert row.current_status_id == s.SR1.id
    # Then 4
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 5
    assert ev[0].event_type == "invoice_unlinked"
    assert ev[0].description == "Invoice voided"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert ev[0].metadata_json == {"invoice_id": v.id}
    # Then 7
    assert result is None


# [claude] POM-UL-02
def test_pom_ul_02__custom_event_type_extra_metadata_wins(db, s):
    """POM-UL-02 — custom event type, extra metadata wins on a clash.
    Rules: unlink_invoice_from_po R2."""
    v = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    M.unlink_invoice_from_po(
        db, po=o, user_id=s.U2.id, reason="Draft removed", event_type="invoice_deleted",
        extra_metadata={"invoice_id": 7, "note": "dup"},
    )
    ev = EV(db, o)
    # Then 1
    assert len(ev) == 1
    # Then 2
    assert ev[0].event_type == "invoice_deleted"
    assert ev[0].description == "Draft removed"
    # Then 3
    assert ev[0].metadata_json == {"invoice_id": 7, "note": "dup"}


# [claude] POM-UL-03
def test_pom_ul_03__empty_extra_metadata_adds_nothing(db, s):
    """POM-UL-03 — empty extra metadata adds nothing.
    Rules: unlink_invoice_from_po R2."""
    v = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    M.unlink_invoice_from_po(db, po=o, user_id=s.U2.id, reason="Draft removed", extra_metadata={})
    # Then 1
    assert EV(db, o)[0].metadata_json == {"invoice_id": v.id}


# [claude] POM-UL-04
def test_pom_ul_04__no_invoice_still_writes_and_logs(db, s):
    """POM-UL-04 — an order with no invoice still writes and logs.
    Rules: unlink_invoice_from_po R1, R2."""
    o = mk_po(db, s, "1", paid=True)
    M.unlink_invoice_from_po(db, po=o, user_id=None, reason="Cleanup")
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.paid is False
    assert row.invoice_id is None
    # Then 2
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 3
    assert ev[0].metadata_json == {"invoice_id": None}
    assert ev[0].performed_by is None


# [claude] POM-UL-05
def test_pom_ul_05__never_commits(db, s):
    """POM-UL-05 — unlink never commits.
    Rules: unlink_invoice_from_po (flush only)."""
    v = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    n = commit_spy(db, lambda: M.unlink_invoice_from_po(db, po=o, user_id=s.U2.id, reason="x"))
    # Then 1
    assert n == 0


# =========================================================================== #
# unconfirm_sections_after_invoice_void
# =========================================================================== #


# [claude] POM-UV-01
def test_pom_uv_01__supplier_items_back_stage_rederived(db, s):
    """POM-UV-01 — supplier and items go back, details and invoice stay, stage re-derived.
    Rules: unconfirm_sections_after_invoice_void R1, R2."""
    o = mk_po(
        db, s, "1", supplier_confirmed=True, details_confirmed=True, items_confirmed=True,
        invoice_confirmed=True, **stage(s.SR1),
    )
    a = mk_appr(db, s, o, s.U2, **APPROVED)
    result = M.unconfirm_sections_after_invoice_void(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.supplier_confirmed is False
    assert row.items_confirmed is False
    # Then 2
    assert row.details_confirmed is True
    assert row.invoice_confirmed is True
    # Then 3
    assert row.current_status_id == s.SP1.id
    # Then 4
    ar = reread(db, PurchaseOrderApprover, a.id)
    assert ar.approved is True
    assert ar.approved_at == T2
    # Then 5
    assert types(db, o) == ["supplier_unconfirmed", "items_unconfirmed", "status_updated"]
    # Then 6
    ev = EV(db, o)
    assert ev[0].description == "Supplier unconfirmed"
    assert ev[0].performed_by == s.U2.id
    # Then 7
    assert ev[1].description == "Order items unconfirmed"
    assert ev[1].performed_by == s.U2.id
    # Then 8
    assert result is None


# [claude] POM-UV-02
def test_pom_uv_02__only_items_one_event(db, s):
    """POM-UV-02 — only items set: one unconfirm event.
    Rules: unconfirm_sections_after_invoice_void R1, R2."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    M.unconfirm_sections_after_invoice_void(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.items_confirmed is False
    assert row.current_status_id == s.SD1.id
    # Then 2
    assert types(db, o) == ["items_unconfirmed", "status_updated"]


# [claude] POM-UV-03
def test_pom_uv_03__neither_set_nothing_written(db, s):
    """POM-UV-03 — neither set: nothing written, no stage sync.
    Rules: unconfirm_sections_after_invoice_void R2."""
    o = mk_po(db, s, "1", details_confirmed=True, **stage(s.SR1))
    M.unconfirm_sections_after_invoice_void(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SR1.id
    # Then 3
    assert EV(db, o) == []


# [claude] POM-UV-04
def test_pom_uv_04__never_commits(db, s):
    """POM-UV-04 — never commits.
    Rules: unconfirm_sections_after_invoice_void (flush only)."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    n = commit_spy(db, lambda: M.unconfirm_sections_after_invoice_void(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# reset_approvals
# =========================================================================== #


# [claude] POM-RA-01
def test_pom_ra_01__approved_rows_reset_one_event(db, s):
    """POM-RA-01 — approved rows reset, others untouched, one event with the count.
    Rules: reset_approvals R1, R2."""
    o = mk_po(db, s, "1")
    p1 = mk_appr(db, s, o, s.U1, **APPROVED)
    p2 = mk_appr(db, s, o, s.U2, **APPROVED)
    p4 = mk_appr(db, s, o, s.U4, assigned_at=T3)
    before4 = snap(db, p4)
    result = M.reset_approvals(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    r1 = reread(db, PurchaseOrderApprover, p1.id)
    assert r1.approved is False
    assert r1.approved_at is None
    # Then 2
    r2 = reread(db, PurchaseOrderApprover, p2.id)
    assert r2.approved is False
    assert r2.approved_at is None
    # Then 3
    assert snap(db, p4) == before4
    # Then 4
    assert approver_count(db, o) == 3
    # Then 5
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 6
    assert ev[0].event_type == "approvals_reset"
    assert ev[0].description == "Cleared approvals after invoice voided (2 approval(s) cleared)"
    assert ev[0].performed_by == s.U2.id
    # Then 7
    assert result is None


# [claude] POM-RA-02
def test_pom_ra_02__given_reason_used(db, s):
    """POM-RA-02 — a given reason is used.
    Rules: reset_approvals R2."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U2, **APPROVED)
    M.reset_approvals(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U1.id, reason="Section unconfirmed")
    # Then 1
    assert EV(db, o)[0].description == "Section unconfirmed (1 approval(s) cleared)"


# [claude] POM-RA-03
def test_pom_ra_03__nothing_approved_nothing_written(db, s):
    """POM-RA-03 — nothing approved: nothing written, no event.
    Rules: reset_approvals R2."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2)
    before = snap(db, p)
    M.reset_approvals(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert EV(db, o) == []
    # Then 3
    assert snap(db, p) == before


# [claude] POM-RA-04
def test_pom_ra_04__other_workspace_rows_not_reset(db, s):
    """POM-RA-04 — approved rows of W0 and W2 on the order are not reset.
    Rules: reset_approvals R1."""
    o = mk_po(db, s, "1")
    x0 = mk_appr(db, s, o, s.U3, **APPROVED, workspace_id=s.W0.id)
    x9 = mk_appr(db, s, o, s.U5, **APPROVED, workspace_id=s.W2.id)
    b0, b9 = snap(db, x0), snap(db, x9)
    M.reset_approvals(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert snap(db, x0) == b0
    # Then 2
    assert snap(db, x9) == b9
    # Then 3
    assert EV(db, o) == []


# [claude] POM-RA-05
def test_pom_ra_05__missing_order_resets_nothing(db, s):
    """POM-RA-05 — an id of no order resets nothing and does not raise.
    Rules: reset_approvals R2."""
    before = counts(db)
    M.reset_approvals(db, po_id=MISSING, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert counts(db) == before


# [claude] POM-RA-06
def test_pom_ra_06__never_commits(db, s):
    """POM-RA-06 — never commits.
    Rules: reset_approvals (flush only)."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U2, **APPROVED)
    n = commit_spy(db, lambda: M.reset_approvals(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U1.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# _ensure_po_stage_statuses
# =========================================================================== #


# [claude] POM-ES-01
def test_pom_es_01__empty_workspace_gets_four_stages(db):
    """POM-ES-01 — a workspace with no statuses gets the four stages.
    Rules: _ensure_po_stage_statuses R1."""
    wx = mk_wx(db)
    result = M._ensure_po_stage_statuses(db, workspace_id=wx.id)
    # Then 1
    assert status_names(db, wx) == ["Complete", "Draft", "Planning", "Receiving"]
    # Then 2
    assert result is None


# [claude] POM-ES-02
def test_pom_es_02__only_missing_three_added(db):
    """POM-ES-02 — Draft missing, Planning present: only the missing three are added.
    Rules: _ensure_po_stage_statuses R1."""
    wx = mk_wx(db)
    stx(db, wx, "Planning")
    M._ensure_po_stage_statuses(db, workspace_id=wx.id)
    # Then 1
    assert status_count(db, wx, "Planning") == 1
    # Then 2
    assert status_count(db, wx) == 4


# [claude] POM-ES-03
def test_pom_es_03__draft_present_nothing_done(db):
    """POM-ES-03 — Draft present, others missing: nothing is done.
    Rules: _ensure_po_stage_statuses R1 (Q4)."""
    wx = mk_wx(db)
    stx(db, wx, "Draft")
    M._ensure_po_stage_statuses(db, workspace_id=wx.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert status_count(db, wx) == 1


# [claude] POM-ES-04
@xf(X1881)
def test_pom_es_04__lowercase_draft_counts(db):
    """POM-ES-04 — "draft" in other capitals counts as Draft.
    Rules: _ensure_po_stage_statuses R1 [BUG-1881]."""
    wx = mk_wx(db)
    stx(db, wx, "draft")
    M._ensure_po_stage_statuses(db, workspace_id=wx.id)
    # Then 1
    assert status_count(db, wx) == 1


# [claude] POM-ES-05
@xf(X1881)
def test_pom_es_05__outer_spaces_draft_counts(db):
    """POM-ES-05 — " Draft " with outer spaces counts as Draft.
    Rules: _ensure_po_stage_statuses R1 [BUG-1881]."""
    wx = mk_wx(db)
    stx(db, wx, " Draft ")
    M._ensure_po_stage_statuses(db, workspace_id=wx.id)
    # Then 1
    assert status_count(db, wx) == 1


# [claude] POM-ES-06
def test_pom_es_06__never_commits(db):
    """POM-ES-06 — never commits.
    Rules: _ensure_po_stage_statuses (flush only)."""
    wx = mk_wx(db)
    n = commit_spy(db, lambda: M._ensure_po_stage_statuses(db, workspace_id=wx.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# _raise_po_workflow_setup_error
# =========================================================================== #


# [claude] POM-WE-01
def test_pom_we_01__migration_hint(db):
    """POM-WE-01 — another workspace has a purchase workflow: migration hint.
    Rules: _raise_po_workflow_setup_error R1."""
    wx = mk_wx(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._raise_po_workflow_setup_error(db, workspace_id=wx.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order workflow requires database migration 022_po_stage_workflow. Run: alembic upgrade head"


# [claude] POM-WE-02
def test_pom_we_02__not_configured(db):
    """POM-WE-02 — no purchase workflow anywhere else: not configured.
    Rules: _raise_po_workflow_setup_error R1."""
    wx = mk_wx(db)
    hide_purchase_workflows(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._raise_po_workflow_setup_error(db, workspace_id=wx.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order workflow is not configured for this workspace"


# =========================================================================== #
# _resolve_po_stage_status_id
# =========================================================================== #


# [claude] POM-RS-01
def test_pom_rs_01__workspace_own_stage_row(db, s):
    """POM-RS-01 — returns the workspace's own stage row.
    Rules: _resolve_po_stage_status_id R1."""
    result = M._resolve_po_stage_status_id(db, workspace_id=s.W1.id, stage_name="Receiving")
    # Then 1
    assert result == s.SR1.id


# [claude] POM-RS-02
def test_pom_rs_02__empty_workspace_backfilled(db):
    """POM-RS-02 — a workspace with no statuses is backfilled first.
    Rules: _resolve_po_stage_status_id R1."""
    wx = mk_wx(db)
    result = M._resolve_po_stage_status_id(db, workspace_id=wx.id, stage_name="Planning")
    # Then 1
    assert result == status_id(db, wx, "Planning")
    # Then 2
    assert status_count(db, wx) == 4


# [claude] POM-RS-03
def test_pom_rs_03__stage_missing_422(db):
    """POM-RS-03 — Draft present but the stage missing: 422.
    Rules: _resolve_po_stage_status_id R2 (Q4)."""
    wx = mk_wx(db)
    stx(db, wx, "Draft")
    stx(db, wx, "Receiving")
    stx(db, wx, "Complete")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._resolve_po_stage_status_id(db, workspace_id=wx.id, stage_name="Planning")
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order stage status 'Planning' not found for this workspace"
    # Then 3
    assert status_count(db, wx) == 3


# [claude] POM-RS-04
@xf(X1881)
def test_pom_rs_04__differently_spelled_stage_reused(db):
    """POM-RS-04 — a differently spelled stage row is found and reused.
    Rules: _resolve_po_stage_status_id R1 [BUG-1881]."""
    wx = mk_wx(db)
    stx(db, wx, "draft")
    px = stx(db, wx, "planning ")
    stx(db, wx, "Receiving")
    stx(db, wx, "Complete")
    result = M._resolve_po_stage_status_id(db, workspace_id=wx.id, stage_name="Planning")
    # Then 1
    assert result == px.id
    # Then 2
    assert status_count(db, wx) == 4


# =========================================================================== #
# _resolve_po_workflow_id
# =========================================================================== #


# [claude] POM-WF-01
def test_pom_wf_01__existing_workflow_gets_sequence(db, s):
    """POM-WF-01 — an existing purchase workflow gets the four stages as its sequence.
    Rules: _resolve_po_workflow_id R1."""
    s.WF1.status_sequence = [s.SD1.id]
    db.flush()
    result = M._resolve_po_workflow_id(db, workspace_id=s.W1.id)
    # Then 1
    assert result == s.WF1.id
    # Then 2
    assert reread(db, OrderWorkflow, s.WF1.id).status_sequence == [s.SD1.id, s.SP1.id, s.SR1.id, s.SC1.id]
    # Then 3
    assert len(purchase_workflows(db, s.W1)) == 1


# [claude] POM-WF-02
def test_pom_wf_02__empty_workspace_gets_workflow(db):
    """POM-WF-02 — an empty workspace gets the stages and a "Purchase Order" workflow.
    Rules: _resolve_po_workflow_id R1."""
    wx = mk_wx(db)
    result = M._resolve_po_workflow_id(db, workspace_id=wx.id)
    # Then 1
    (wf,) = purchase_workflows(db, wx)
    assert wf.id == result
    assert wf.name == "Purchase Order"
    # Then 2
    assert wf.status_sequence == [status_id(db, wx, n) for n in ("Draft", "Planning", "Receiving", "Complete")]


# [claude] POM-WF-03
def test_pom_wf_03__other_workflows_untouched(db, s):
    """POM-WF-03 — other workspaces' workflows are not touched.
    Rules: _resolve_po_workflow_id R1."""
    s.WF0.status_sequence = [s.SD0.id]
    s.WF9.status_sequence = [s.SD9.id]
    db.flush()
    result = M._resolve_po_workflow_id(db, workspace_id=s.W1.id)
    # Then 1
    assert result == s.WF1.id
    # Then 2
    assert reread(db, OrderWorkflow, s.WF0.id).status_sequence == [s.SD0.id]
    # Then 3
    assert reread(db, OrderWorkflow, s.WF9.id).status_sequence == [s.SD9.id]


# [claude] POM-WF-04
def test_pom_wf_04__never_commits(db):
    """POM-WF-04 — never commits.
    Rules: _resolve_po_workflow_id (flush only)."""
    wx = mk_wx(db)
    n = commit_spy(db, lambda: M._resolve_po_workflow_id(db, workspace_id=wx.id))
    # Then 1
    assert n == 0


# [claude] POM-WF-05
def test_pom_wf_05__seed_none_migration_hint(db, s):
    """POM-WF-05 — the seed returns no workflow: 422 with the migration hint.
    Rules: _resolve_po_workflow_id R2, _raise_po_workflow_setup_error R1."""
    # Then 1
    with (
        patch("app.managers.purchase_order_manager.ensure_po_workflow_record", return_value=None),
        pytest.raises(HTTPException) as exc,
    ):
        M._resolve_po_workflow_id(db, workspace_id=s.W1.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order workflow requires database migration 022_po_stage_workflow. Run: alembic upgrade head"


# [claude] POM-WF-06
def test_pom_wf_06__seed_none_not_configured(db, s):
    """POM-WF-06 — the seed returns no workflow and no workspace has one: not configured.
    Rules: _resolve_po_workflow_id R2, _raise_po_workflow_setup_error R1."""
    hide_purchase_workflows(db)
    # Then 1
    with (
        patch("app.managers.purchase_order_manager.ensure_po_workflow_record", return_value=None),
        pytest.raises(HTTPException) as exc,
    ):
        M._resolve_po_workflow_id(db, workspace_id=s.W1.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order workflow is not configured for this workspace"


# =========================================================================== #
# _all_items_fully_received
# =========================================================================== #


def _q(ordered, received, refunded):
    """Card shorthand `mem(quantity_ordered=..., quantity_received=..., quantity_refunded=...)`."""
    return mem(
        quantity_ordered=Decimal(ordered),
        quantity_received=None if received is None else Decimal(received),
        quantity_refunded=None if refunded is None else Decimal(refunded),
    )


# [claude] POM-FR-01
def test_pom_fr_01__no_lines_not_done():
    """POM-FR-01 — no lines is not done.
    Rules: _all_items_fully_received R1."""
    result = M._all_items_fully_received([])
    # Then 1
    assert result is False


# [claude] POM-FR-02
def test_pom_fr_02__received_plus_refunded_done():
    """POM-FR-02 — received plus refunded reaching ordered is done.
    Rules: _all_items_fully_received R2."""
    a = _q("10.00", "10.00", "0.00")
    b = _q("10.00", "7.00", "3.00")
    result = M._all_items_fully_received([a, b])
    # Then 1
    assert result is True


# [claude] POM-FR-03
def test_pom_fr_03__one_cent_short_not_done():
    """POM-FR-03 — one line a cent short is not done.
    Rules: _all_items_fully_received R2."""
    a = _q("10.00", "10.00", "0.00")
    b = _q("10.00", "6.99", "3.00")
    result = M._all_items_fully_received([a, b])
    # Then 1
    assert result is False


# [claude] POM-FR-04
def test_pom_fr_04__over_receipt_done():
    """POM-FR-04 — over-receipt counts as done.
    Rules: _all_items_fully_received R2."""
    a = _q("10.00", "12.00", "0.00")
    result = M._all_items_fully_received([a])
    # Then 1
    assert result is True


# [claude] POM-FR-05
def test_pom_fr_05__none_received_counts_zero():
    """POM-FR-05 — None received counts as 0.
    Rules: _all_items_fully_received R2."""
    a = _q("10.00", None, "10.00")
    b = _q("10.00", None, "9.00")
    result = M._all_items_fully_received([a, b])
    # Then 1
    assert result is False


# [claude] POM-FR-06
def test_pom_fr_06__none_refunded_counts_zero():
    """POM-FR-06 — None refunded counts as 0.
    Rules: _all_items_fully_received R2."""
    a = _q("10.00", "10.00", None)
    result = M._all_items_fully_received([a])
    # Then 1
    assert result is True


# =========================================================================== #
# _current_stage_name
# =========================================================================== #


# [claude] POM-CS-01
def test_pom_cs_01__workspace_status_name(db, s):
    """POM-CS-01 — the workspace's status name.
    Rules: _current_stage_name R1."""
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=s.SR1.id)
    # Then 1
    assert result == "Receiving"


# [claude] POM-CS-02
def test_pom_cs_02__w2_status_none(db, s):
    """POM-CS-02 — a status of W2 gives None.
    Rules: _current_stage_name R1."""
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=s.SR9.id)
    # Then 1
    assert result is None


# [claude] POM-CS-03
def test_pom_cs_03__w0_status_none(db, s):
    """POM-CS-03 — a status of W0 gives None.
    Rules: _current_stage_name R1."""
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=s.SC0.id)
    # Then 1
    assert result is None


# [claude] POM-CS-04
def test_pom_cs_04__missing_id_none(db, s):
    """POM-CS-04 — a missing id gives None.
    Rules: _current_stage_name R1."""
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=MISSING)
    # Then 1
    assert result is None


# [claude] POM-CS-05
def test_pom_cs_05__none_gives_none(db, s):
    """POM-CS-05 — None gives None.
    Rules: _current_stage_name R1."""
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=None)
    # Then 1
    assert result is None


# [claude] POM-CS-06
def test_pom_cs_06__stored_name_exactly(db, s):
    """POM-CS-06 — the stored name comes back exactly as stored.
    Rules: _current_stage_name R1 (G6)."""
    sl = _add(db, Status(workspace_id=s.W1.id, name=" complete ", comment="po stage"))
    result = M._current_stage_name(db, workspace_id=s.W1.id, status_id=sl.id)
    # Then 1
    assert result == " complete "


# =========================================================================== #
# _invoice_payment_status
# =========================================================================== #


# [claude] POM-IP-01
def test_pom_ip_01__linked_invoice_payment_status(db, s):
    """POM-IP-01 — the linked invoice's payment status.
    Rules: _invoice_payment_status R1."""
    v = mk_inv(db, s, "confirmed", "partial")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = M._invoice_payment_status(db, po=o)
    # Then 1
    assert result == "partial"


# [claude] POM-IP-02
def test_pom_ip_02__no_invoice_none(db, s):
    """POM-IP-02 — no invoice gives None.
    Rules: _invoice_payment_status R1."""
    o = mk_po(db, s, "1")
    result = M._invoice_payment_status(db, po=o)
    # Then 1
    assert result is None


# [claude] POM-IP-03
def test_pom_ip_03__w2_invoice_none(db, s):
    """POM-IP-03 — an invoice of W2 gives None.
    Rules: _invoice_payment_status R1."""
    v9 = mk_inv(db, s, "confirmed", "paid", k="9")
    o = mk_po(db, s, "1", invoice_id=v9.id)
    result = M._invoice_payment_status(db, po=o)
    # Then 1
    assert result is None


# =========================================================================== #
# sync_po_for_linked_invoice
# =========================================================================== #


# [claude] POM-SL-01
def test_pom_sl_01__paid_invoice_marks_order_paid(db, s):
    """POM-SL-01 — the order of a paid invoice is marked paid.
    Rules: sync_po_for_linked_invoice R1."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = M.sync_po_for_linked_invoice(db, invoice_id=v.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert reread(db, PurchaseOrder, o.id).paid is True
    # Then 2
    assert types(db, o) == ["payment_status_synced"]
    # Then 3
    assert result is None


# [claude] POM-SL-02
def test_pom_sl_02__no_order_nothing_written(db, s):
    """POM-SL-02 — no order for the invoice: nothing written.
    Rules: sync_po_for_linked_invoice R1."""
    v = mk_inv(db, s, "confirmed", "paid")
    before = counts(db)
    M.sync_po_for_linked_invoice(db, invoice_id=v.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert counts(db) == before


# [claude] POM-SL-03
def test_pom_sl_03__w2_order_not_touched(db, s):
    """POM-SL-03 — a W2 order linked to the invoice is not touched.
    Rules: sync_po_for_linked_invoice R1."""
    v = mk_inv(db, s, "confirmed", "paid")
    o9 = mk_po(db, s, "9", k="9", invoice_id=v.id)
    before = snap(db, o9)
    M.sync_po_for_linked_invoice(db, invoice_id=v.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert_session_clean(db)
    # Then 2
    assert snap(db, o9) == before
    # Then 3
    assert EV(db, o9) == []


# [claude] POM-SL-04
def test_pom_sl_04__never_commits(db, s):
    """POM-SL-04 — never commits.
    Rules: sync_po_for_linked_invoice (flush only)."""
    v = mk_inv(db, s, "confirmed", "paid")
    mk_po(db, s, "1", **locked_by(s, v))
    n = commit_spy(db, lambda: M.sync_po_for_linked_invoice(db, invoice_id=v.id, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# sync_po_paid
# =========================================================================== #


# [claude] POM-SP-01
def test_pom_sp_01__paid_invoice_marked_paid(db, s):
    """POM-SP-01 — paid invoice: marked paid, event, True.
    Rules: sync_po_paid R1, R3."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).paid is True
    # Then 3
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 4
    assert ev[0].event_type == "payment_status_synced"
    assert ev[0].description == "Order marked paid from linked invoice"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert ev[0].metadata_json == {"paid": True}


# [claude] POM-SP-02
def test_pom_sp_02__partial_marks_unpaid(db, s):
    """POM-SP-02 — partial invoice on a paid order: marked unpaid.
    Rules: sync_po_paid R1, R3."""
    v = mk_inv(db, s, "confirmed", "partial")
    o = mk_po(db, s, "1", **locked_by(s, v), paid=True)
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).paid is False
    # Then 3
    ev = EV(db, o)
    assert ev[0].description == "Order marked unpaid from linked invoice"
    # Then 4
    assert ev[0].metadata_json == {"paid": False}


# [claude] POM-SP-03
def test_pom_sp_03__overdue_unpaid(db, s):
    """POM-SP-03 — overdue invoice: unpaid.
    Rules: sync_po_paid R1."""
    v = mk_inv(db, s, "confirmed", "overdue")
    o = mk_po(db, s, "1", **locked_by(s, v), paid=True)
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).paid is False


# [claude] POM-SP-04
def test_pom_sp_04__unpaid_unpaid(db, s):
    """POM-SP-04 — unpaid invoice: unpaid.
    Rules: sync_po_paid R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), paid=True)
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).paid is False


# [claude] POM-SP-05
def test_pom_sp_05__no_invoice_already_unpaid(db, s):
    """POM-SP-05 — no invoice and already unpaid: False, nothing written.
    Rules: sync_po_paid R1, R2."""
    o = mk_po(db, s, "1")
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SP-06
def test_pom_sp_06__w2_paid_invoice_not_paid(db, s):
    """POM-SP-06 — a paid invoice of W2 does not make the order paid.
    Rules: sync_po_paid R1, R2."""
    v9 = mk_inv(db, s, "confirmed", "paid", k="9")
    o = mk_po(db, s, "1", invoice_id=v9.id)
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert reread(db, PurchaseOrder, o.id).paid is False


# [claude] POM-SP-07
def test_pom_sp_07__already_paid_no_event(db, s):
    """POM-SP-07 — already paid: False, no event.
    Rules: sync_po_paid R2."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v), paid=True)
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SP-08
def test_pom_sp_08__no_user_no_performer(db, s):
    """POM-SP-08 — no user: the event has no performer.
    Rules: sync_po_paid R3."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=None)
    # Then 1
    assert result is True
    # Then 2
    assert EV(db, o)[0].performed_by is None


# [claude] POM-SP-09
def test_pom_sp_09__never_commits(db, s):
    """POM-SP-09 — never commits.
    Rules: sync_po_paid (flush only)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    n = commit_spy(db, lambda: M.sync_po_paid(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# _is_po_complete_stage
# =========================================================================== #


# [claude] POM-CP-01
def test_pom_cp_01__exactly_complete():
    """POM-CP-01 — exactly "Complete".
    Rules: _is_po_complete_stage R1."""
    result = M._is_po_complete_stage("Complete")
    # Then 1
    assert result is True


# [claude] POM-CP-02
@xf(X1881)
def test_pom_cp_02__lower_case_complete():
    """POM-CP-02 — lower case counts as complete.
    Rules: _is_po_complete_stage R1a [BUG-1881] (OQ-13)."""
    result = M._is_po_complete_stage("complete")
    # Then 1
    assert result is True


# [claude] POM-CP-03
def test_pom_cp_03__none_not_complete():
    """POM-CP-03 — None is not complete.
    Rules: _is_po_complete_stage R1."""
    result = M._is_po_complete_stage(None)
    # Then 1
    assert result is False


# [claude] POM-CP-04
def test_pom_cp_04__receiving_not_complete():
    """POM-CP-04 — Receiving is not complete.
    Rules: _is_po_complete_stage R1."""
    result = M._is_po_complete_stage("Receiving")
    # Then 1
    assert result is False


# [claude] POM-CP-05
@xf(X1881)
def test_pom_cp_05__capitals_and_spaces_ignored():
    """POM-CP-05 — capitals and outer spaces are ignored.
    Rules: _is_po_complete_stage R1a [BUG-1881] (OQ-13)."""
    result = [M._is_po_complete_stage(x) for x in [" COMPLETE ", "Complete "]]
    # Then 1
    assert result == [True, True]


# [claude] POM-CP-06
def test_pom_cp_06__completed_and_empty_not_complete():
    """POM-CP-06 — "Completed" and the empty text are not complete.
    Rules: _is_po_complete_stage R1."""
    result = [M._is_po_complete_stage(x) for x in ["Completed", ""]]
    # Then 1
    assert result == [False, False]


# =========================================================================== #
# _derive_po_stage_name
# =========================================================================== #


# [claude] POM-DS-01
def test_pom_ds_01__received_cent_makes_receiving(db, s):
    """POM-DS-01 — a line received 0.01 makes Receiving, even with nothing confirmed.
    Rules: _derive_po_stage_name R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("0.01"))
    result = M._derive_po_stage_name(db, po=o, items=[line])
    # Then 1
    assert result == "Receiving"


# [claude] POM-DS-02
def test_pom_ds_02__negative_received_not_counted(db, s):
    """POM-DS-02 — a negative received does not count.
    Rules: _derive_po_stage_name R1, R4."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("-1.00"))
    result = M._derive_po_stage_name(db, po=o, items=[line])
    # Then 1
    assert result == "Draft"


# [claude] POM-DS-03
def test_pom_ds_03__financially_locked_receiving(db, s):
    """POM-DS-03 — financially locked with nothing received is Receiving.
    Rules: _derive_po_stage_name R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    line = mk_line(db, o, 1, s.I1)
    result = M._derive_po_stage_name(db, po=o, items=[line])
    # Then 1
    assert result == "Receiving"


# [claude] POM-DS-04
def test_pom_ds_04__supplier_confirmed_planning(db, s):
    """POM-DS-04 — supplier confirmed only is Planning.
    Rules: _derive_po_stage_name R3."""
    o = mk_po(db, s, "1", supplier_confirmed=True)
    result = M._derive_po_stage_name(db, po=o, items=[])
    # Then 1
    assert result == "Planning"


# [claude] POM-DS-05
def test_pom_ds_05__details_confirmed_planning(db, s):
    """POM-DS-05 — details confirmed only is Planning.
    Rules: _derive_po_stage_name R3."""
    o = mk_po(db, s, "1", details_confirmed=True)
    result = M._derive_po_stage_name(db, po=o, items=[])
    # Then 1
    assert result == "Planning"


# [claude] POM-DS-06
def test_pom_ds_06__items_confirmed_planning(db, s):
    """POM-DS-06 — items confirmed only is Planning.
    Rules: _derive_po_stage_name R3."""
    o = mk_po(db, s, "1", items_confirmed=True)
    result = M._derive_po_stage_name(db, po=o, items=[])
    # Then 1
    assert result == "Planning"


# [claude] POM-DS-07
def test_pom_ds_07__invoice_confirmed_alone_draft(db, s):
    """POM-DS-07 — invoice_confirmed alone is still Draft.
    Rules: _derive_po_stage_name R3, R4."""
    o = mk_po(db, s, "1", invoice_confirmed=True)
    result = M._derive_po_stage_name(db, po=o, items=[])
    # Then 1
    assert result == "Draft"


# [claude] POM-DS-08
def test_pom_ds_08__everything_done_still_receiving(db, s):
    """POM-DS-08 — everything done is still Receiving, never Complete.
    Rules: _derive_po_stage_name R1, R4."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    result = M._derive_po_stage_name(db, po=o, items=[line])
    # Then 1
    assert result == "Receiving"


# =========================================================================== #
# sync_po_stage
# =========================================================================== #


# [claude] POM-SS-01
def test_pom_ss_01__draft_to_planning_logged(db, s):
    """POM-SS-01 — Draft with the supplier confirmed moves to Planning and logs it.
    Rules: sync_po_stage R1, R3, R4."""
    o = mk_po(db, s, "1", supplier_confirmed=True)
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 3
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 4
    assert ev[0].event_type == "status_updated"
    assert ev[0].description == "Stage updated to Planning"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert ev[0].metadata_json == {
        "changes": [{"field": "current_status_id", "label": "Status", "from_value": "Draft", "to_value": "Planning"}]
    }


# [claude] POM-SS-02
def test_pom_ss_02__already_right_nothing_written(db, s):
    """POM-SS-02 — stage and workflow already right: False, nothing written.
    Rules: sync_po_stage R4."""
    o = mk_po(db, s, "1", **confirmed(s))
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.current_status_id == s.SP1.id
    assert row.order_workflow_id == s.WF1.id
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SS-03
def test_pom_ss_03__complete_stays_complete(db, s):
    """POM-SS-03 — Complete stays Complete after a return lowered the received quantity.
    Rules: sync_po_stage R1 (BUG-2810, RP1)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("4.00"), quantity_returned=Decimal("6.00"))
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SC1.id
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SS-04
def test_pom_ss_04__workflow_replaced_no_event(db, s):
    """POM-SS-04 — a different workflow is replaced by the purchase workflow, no stage event.
    Rules: sync_po_stage R2, R4."""
    wfl = _add(db, OrderWorkflow(workspace_id=s.W1.id, name="Old flow", type="legacy", status_sequence=[s.SD1.id]))
    o = mk_po(db, s, "1", order_workflow_id=wfl.id)
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.order_workflow_id == s.WF1.id
    assert row.current_status_id == s.SD1.id
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SS-05
def test_pom_ss_05__no_user_no_performer(db, s):
    """POM-SS-05 — no user: the stage event has no performer.
    Rules: sync_po_stage R3."""
    o = mk_po(db, s, "1", items_confirmed=True)
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=None)
    # Then 1
    assert result is True
    # Then 2
    ev = EV(db, o)
    assert ev[0].event_type == "status_updated"
    assert ev[0].performed_by is None


# [claude] POM-SS-06
def test_pom_ss_06__target_stage_missing_422(db, s):
    """POM-SS-06 — the target stage row is missing: 422, stage not set.
    Rules: sync_po_stage R4, R4a (G12), _resolve_po_stage_status_id R2 (Q4)."""
    wx = mk_wx(db)
    sdx = stx(db, wx, "Draft")
    stx(db, wx, "Receiving")
    stx(db, wx, "Complete")
    wfx = _add(db, OrderWorkflow(workspace_id=wx.id, name="Purchase Order", type="purchase", status_sequence=[sdx.id]))
    ox = mk_pox(db, s, wx, sdx, wfx, supplier_confirmed=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.sync_po_stage(db, po=ox, workspace_id=wx.id, user_id=s.U2.id)
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "Purchase order stage status 'Planning' not found for this workspace"
    # Then 3
    assert reread(db, PurchaseOrder, ox.id).current_status_id == sdx.id
    # Then 4
    assert EV(db, ox) == []
    # Then 5
    assert reread(db, OrderWorkflow, wfx.id).status_sequence == [sdx.id]
    # Then 6
    assert status_count(db, wx, "Planning") == 0


# [claude] POM-SS-07
@xf(X2875)
def test_pom_ss_07__old_stage_foreign_status(db, s):
    """POM-SS-07 — the old stage is a status of W2: shown as "Status #<id>".
    Rules: sync_po_stage R3, _format_field_value R5 [BUG-2875]."""
    o = mk_po(db, s, "1", **stage(s.SR9), supplier_confirmed=True)
    result = M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 3
    ev = EV(db, o)
    assert len(ev) == 1
    # Then 4
    assert ev[0].metadata_json["changes"][0]["from_value"] == f"Status #{s.SR9.id}"


# [claude] POM-SS-08
def test_pom_ss_08__never_commits(db, s):
    """POM-SS-08 — never commits.
    Rules: sync_po_stage (flush only)."""
    o = mk_po(db, s, "1", supplier_confirmed=True)
    n = commit_spy(db, lambda: M.sync_po_stage(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# [claude] POM-SS-09
def test_pom_ss_09__planning_missing_target_draft(db, s):
    """POM-SS-09 — Planning missing, target Draft: the workflow step then creates Planning.
    Rules: sync_po_stage R2, R4, R4a (G12)."""
    wx = mk_wx(db)
    sdx = stx(db, wx, "Draft")
    stx(db, wx, "Receiving")
    stx(db, wx, "Complete")
    wfl = _add(db, OrderWorkflow(workspace_id=wx.id, name="Old flow", type="legacy", status_sequence=[sdx.id]))
    ox = mk_pox(db, s, wx, sdx, wfl)
    result = M.sync_po_stage(db, po=ox, workspace_id=wx.id, user_id=s.U2.id)
    # Then 1
    assert result is True
    # Then 2
    row = reread(db, PurchaseOrder, ox.id)
    assert row.current_status_id == sdx.id
    assert row.order_workflow_id != wfl.id
    # Then 3
    assert status_names(db, wx) == ["Complete", "Draft", "Planning", "Receiving"]
    # Then 4
    (wf,) = purchase_workflows(db, wx)
    assert wf.id == reread(db, PurchaseOrder, ox.id).order_workflow_id
    assert wf.status_sequence == [status_id(db, wx, n) for n in ("Draft", "Planning", "Receiving", "Complete")]
    # Then 5
    assert EV(db, ox) == []


# =========================================================================== #
# mark_order_complete
# =========================================================================== #


def _mc(db, s, po_id):
    return M.mark_order_complete(db, po_id=po_id, workspace_id=s.W1.id, user_id=s.U2.id)


# [claude] POM-MC-01
def test_pom_mc_01__every_line_done_complete(db, s):
    """POM-MC-01 — every line done: Complete, delivered today, paid synced, one event.
    Rules: mark_order_complete R5, sync_po_paid R3."""
    today = date.today()
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_line(db, o, 2, s.I2, quantity_received=Decimal("7.00"), quantity_refunded=Decimal("3.00"))
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.current_status_id == s.SC1.id
    assert row.updated_by == s.U2.id
    assert row.actual_delivery_date == today
    # Then 3
    assert row.paid is True
    # Then 4
    assert types(db, o) == ["payment_status_synced", "order_completed"]
    # Then 5
    ev = EV(db, o)
    assert ev[1].description == "Order marked complete"
    assert ev[1].performed_by == s.U2.id


# [claude] POM-MC-02
def test_pom_mc_02__existing_delivery_date_kept(db, s):
    """POM-MC-02 — an existing delivery date is kept.
    Rules: mark_order_complete R5."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), actual_delivery_date=D3)
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.actual_delivery_date == D3
    assert row.current_status_id == s.SC1.id


# [claude] POM-MC-03
def test_pom_mc_03__unpaid_and_unapproved_do_not_block(db, s):
    """POM-MC-03 — unpaid invoice and an unapproved approver do not block.
    Rules: mark_order_complete R5."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), required_approvals=2)
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_appr(db, s, o, s.U2)
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.current_status_id == s.SC1.id
    assert row.paid is False
    # Then 3
    assert types(db, o) == ["order_completed"]


# [claude] POM-MC-04
def test_pom_mc_04__missing_order_404(db, s):
    """POM-MC-04 — a missing order: 404.
    Rules: mark_order_complete R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, MISSING)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-MC-05
def test_pom_mc_05__w0_order_404(db, s):
    """POM-MC-05 — an order of W0: 404.
    Rules: mark_order_complete R1."""
    o0 = mk_po(db, s, "0", k="0")
    mk_line(db, o0, 1, s.I0, quantity_received=Decimal("10.00"))
    before = snap(db, o0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o0.id} not found"
    # Then 3
    assert snap(db, o0) == before


# [claude] POM-MC-06
def test_pom_mc_06__w2_order_404(db, s):
    """POM-MC-06 — an order of W2: 404.
    Rules: mark_order_complete R1."""
    o9 = mk_po(db, s, "9", k="9")
    mk_line(db, o9, 1, s.I9, quantity_received=Decimal("10.00"))
    before = snap(db, o9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"
    # Then 3
    assert snap(db, o9) == before


# [claude] POM-MC-07
@xf(X2882)
def test_pom_mc_07__voided_order_refused(db, s):
    """POM-MC-07 — a voided order is refused.
    Rules: mark_order_complete R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s), **stage(s.SR1))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-MC-08
def test_pom_mc_08__already_complete_unchanged(db, s):
    """POM-MC-08 — already Complete: returned unchanged, no paid sync.
    Rules: mark_order_complete R2."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    before = snap(db, o)
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-MC-09
def test_pom_mc_09__line_short_400(db, s):
    """POM-MC-09 — a line short: 400, nothing written.
    Rules: mark_order_complete R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_line(db, o, 2, s.I2, quantity_received=Decimal("9.99"))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "All line items must be fully received before marking the order complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-MC-10
def test_pom_mc_10__no_lines_400(db, s):
    """POM-MC-10 — an order with no lines: 400.
    Rules: mark_order_complete R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "All line items must be fully received before marking the order complete"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-MC-11
def test_pom_mc_11__open_return_400(db, s):
    """POM-MC-11 — an open return: 400.
    Rules: mark_order_complete R4."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_ret(db, s, o, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete all open returns before marking the order complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-MC-12
def test_pom_mc_12__line_check_answers_first(db, s):
    """POM-MC-12 — short line and open return: the line check answers first.
    Rules: mark_order_complete R3, R4."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("5.00"))
    mk_ret(db, s, o, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _mc(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "All line items must be fully received before marking the order complete"


# [claude] POM-MC-13
def test_pom_mc_13__completed_cancelled_returns_do_not_block(db, s):
    """POM-MC-13 — completed and cancelled returns do not block.
    Rules: mark_order_complete R4, RP2 (PO)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_ret(db, s, o, "1", **ret_completed(s))
    mk_ret(db, s, o, "2", **RET_CANCELLED)
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SC1.id


# [claude] POM-MC-14
def test_pom_mc_14__foreign_pending_returns_do_not_block(db, s):
    """POM-MC-14 — pending returns filed under W0 and W2 do not block.
    Rules: mark_order_complete R4, RP2 (PO)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_ret(db, s, o, "0", workspace_id=s.W0.id)
    mk_ret(db, s, o, "9", workspace_id=s.W2.id)
    result = _mc(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SC1.id


# [claude] POM-MC-15
@xf(X2872)
def test_pom_mc_15__order_read_for_update(db, s):
    """POM-MC-15 — the order row is read FOR UPDATE before the checks.
    Rules: mark_order_complete R6 [BUG-2872]."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = _mc(db, s, o_id)
    # Then 1
    assert result.id == o_id
    # Then 2
    assert rec.locks_first()


# [claude] POM-MC-16
def test_pom_mc_16__never_commits(db, s):
    """POM-MC-16 — never commits.
    Rules: mark_order_complete (flush only)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    n = commit_spy(db, lambda: _mc(db, s, o.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# reopen_for_return
# =========================================================================== #


# [claude] POM-RO-01
def test_pom_ro_01__not_complete_false(db, s):
    """POM-RO-01 — an order not Complete: False, nothing written.
    Rules: reopen_for_return R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    result = M.reopen_for_return(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    assert_session_clean(db)
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-RO-02
@xf(X2789)
def test_pom_ro_02__completed_stays_completed(db, s):
    """POM-RO-02 — a completed order stays completed.
    Rules: reopen_for_return R2 [BUG-2789], RP1 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    mk_ret(db, s, o, "1")
    result = M.reopen_for_return(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert result is False
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.current_status_id == s.SC1.id
    assert row.actual_delivery_date == D2
    assert row.updated_by is None
    # Then 3
    assert EV(db, o) == []


# [claude] POM-RO-03
def test_pom_ro_03__invoice_lines_return_untouched(db, s):
    """POM-RO-03 — on a completed order the invoice, lines and return are untouched.
    Rules: reopen_for_return R2, RP1 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("10.00"))
    r = mk_ret(db, s, o, "1")
    bv, bl, br = snap(db, v), snap(db, line), snap(db, r)
    o = reread(db, PurchaseOrder, o.id)
    result = M.reopen_for_return(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert isinstance(result, bool)
    # Then 2
    assert snap(db, v) == bv
    # Then 3
    assert snap(db, line) == bl
    # Then 4
    assert snap(db, r) == br
    # Then 5
    row = reread(db, PurchaseOrder, o.id)
    assert row.invoice_id == v.id
    assert row.paid is False
    assert row.supplier_confirmed is True
    assert row.items_confirmed is True


# [claude] POM-RO-04
def test_pom_ro_04__never_commits(db, s):
    """POM-RO-04 — never commits.
    Rules: reopen_for_return (flush only)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    n = commit_spy(db, lambda: M.reopen_for_return(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# create_purchase_order
# =========================================================================== #


def CR(db, s, **fields):
    """The card call `M.create_purchase_order(db, data=PurchaseOrderCreate(...), workspace_id=W1.id, user_id=U2.id)`."""
    return M.create_purchase_order(db, data=PurchaseOrderCreate(**fields), workspace_id=s.W1.id, user_id=s.U2.id)


def po_count(db, ws):
    """Count of a workspace's `purchase_orders` rows."""
    db.expire_all()
    return db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.workspace_id == ws.id))


# [claude] POM-CR-01
def test_pom_cr_01__new_order_two_lines(db, s):
    """POM-CR-01 — a new order with two lines.
    Rules: create_purchase_order R1, R2, R5, R6, R7, R8."""
    result = CR(
        db, s, account_id=s.A1.id, destination_type="storage", destination_id=s.F1.id, order_date=D1,
        expected_delivery_date=D2, description="Steel for line 2",
        items=[
            IC(item_id=s.I1.id, quantity_ordered=Decimal("10"), unit_price=Decimal("2.50")),
            IC(item_id=s.I2.id, quantity_ordered=Decimal("4"), unit_price=Decimal("1.25"), notes="Zinc"),
        ],
    )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert re.fullmatch(r"PO-\d{4}-\d{3,}", row.po_number)
    assert row.workspace_id == s.W1.id
    assert row.created_by == s.U2.id
    # Then 3
    assert row.current_status_id == s.SD1.id
    assert row.order_workflow_id == s.WF1.id
    # Then 4
    assert row.account_id == s.A1.id
    assert row.destination_type == "storage"
    assert row.destination_id == s.F1.id
    assert row.order_date == D1
    assert row.expected_delivery_date == D2
    assert row.description == "Steel for line 2"
    # Then 5
    assert row.subtotal == Decimal("30.00")
    assert row.total_amount == Decimal("30.00")
    # Then 6
    assert [
        (ln.line_number, ln.item_id, ln.quantity_ordered, ln.quantity_received, ln.unit_price, ln.line_subtotal)
        for ln in LINES(db, row)
    ] == [
        (1, s.I1.id, Decimal("10.00"), Decimal("0.00"), Decimal("2.50"), Decimal("25.00")),
        (2, s.I2.id, Decimal("4.00"), Decimal("0.00"), Decimal("1.25"), Decimal("5.00")),
    ]
    # Then 7
    assert LINES(db, row)[1].notes == "Zinc"
    # Then 8
    apprs = approvers_of(db, row)
    assert len(apprs) == 1
    assert apprs[0].user_id == s.U2.id
    assert apprs[0].assigned_by == s.U2.id
    assert apprs[0].approved is False
    # Then 9
    assert types(db, row) == ["created"]
    # Then 10
    assert EV(db, row)[0].description == "Order created"


# [claude] POM-CR-02
def test_pom_cr_02__no_order_date_today(db, s):
    """POM-CR-02 — no order date sent: today.
    Rules: create_purchase_order R2."""
    today = date.today()
    result = CR(db, s, destination_type="storage", destination_id=s.F1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.order_date == today
    assert row.account_id is None


# [claude] POM-CR-03
def test_pom_cr_03__sent_stage_and_workflow_replaced(db, s):
    """POM-CR-03 — a sent stage and workflow are replaced by Draft and the purchase workflow.
    Rules: create_purchase_order R2 (Q6)."""
    wfl = _add(db, OrderWorkflow(workspace_id=s.W1.id, name="Old flow", type="legacy", status_sequence=[s.SC1.id]))
    result = CR(
        db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1,
        current_status_id=s.SC1.id, order_workflow_id=wfl.id,
    )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.current_status_id == s.SD1.id
    assert row.order_workflow_id == s.WF1.id


# [claude] POM-CR-04
def test_pom_cr_04__no_lines_totals_zero(db, s):
    """POM-CR-04 — no lines: totals 0, no lines stored.
    Rules: create_purchase_order R7."""
    result = CR(db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.subtotal == Decimal("0.00")
    assert row.total_amount == Decimal("0.00")
    # Then 3
    assert LINES(db, row) == []


# [claude] POM-CR-05
def test_pom_cr_05__unpriced_line_adds_zero(db, s):
    """POM-CR-05 — an unpriced line has no subtotal and adds 0.
    Rules: create_purchase_order R5, R7, _line_subtotal R1."""
    result = CR(
        db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1,
        items=[
            IC(item_id=s.I1.id, quantity_ordered=Decimal("3")),
            IC(item_id=s.I2.id, quantity_ordered=Decimal("2"), unit_price=Decimal("4.00")),
        ],
    )
    # Then 1
    assert result.id is not None
    # Then 2
    lines = LINES(db, result)
    assert lines[0].unit_price is None
    assert lines[0].line_subtotal is None
    # Then 3
    assert reread(db, PurchaseOrder, result.id).total_amount == Decimal("8.00")


def _three_small_lines(s):
    return [
        IC(item_id=s.I1.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")),
        IC(item_id=s.I2.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")),
        IC(item_id=s.I3.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")),
    ]


# [claude] POM-CR-06
@xf(X2876)
def test_pom_cr_06__total_is_sum_of_rounded_lines(db, s):
    """POM-CR-06 — three lines of 1.25 x 0.10: total is the sum of rounded lines.
    Rules: create_purchase_order R7 [BUG-2876]."""
    result = CR(db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1, items=_three_small_lines(s))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.subtotal == Decimal("0.39")
    assert row.total_amount == Decimal("0.39")


# [claude] POM-CR-07
def test_pom_cr_07__each_stored_line_rounded(db, s):
    """POM-CR-07 — three lines of 1.25 x 0.10: each stored line is 0.13.
    Rules: create_purchase_order R5, _line_subtotal R2."""
    result = CR(db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1, items=_three_small_lines(s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert [ln.line_subtotal for ln in LINES(db, result)] == [Decimal("0.13"), Decimal("0.13"), Decimal("0.13")]


# [claude] POM-CR-08
def test_pom_cr_08__same_item_twice_409(db, s):
    """POM-CR-08 — the same item twice: 409 after the order was flushed.
    Rules: create_purchase_order R4 (Q7)."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(
            db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1,
            items=[
                IC(item_id=s.I1.id, quantity_ordered=Decimal("1")),
                IC(item_id=s.I1.id, quantity_ordered=Decimal("2")),
            ],
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Bolt appears more than once on this order"
    # Then 3
    assert po_count(db, s.W1) == 1
    # Then 4
    order = db.scalar(select(PurchaseOrder).where(PurchaseOrder.workspace_id == s.W1.id))
    assert approver_count(db, order) == 1
    # Then 5
    ev = EV(db, order)
    assert len(ev) == 1
    assert ev[0].event_type == "created"


# [claude] POM-CR-09
@xf(X1017)
def test_pom_cr_09__w2_supplier_refused(db, s):
    """POM-CR-09 — a supplier of W2 is refused.
    Rules: create_purchase_order R3 [BUG-1017]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, account_id=s.A9.id, destination_type="storage", destination_id=s.F1.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-10
@xf(X1017)
def test_pom_cr_10__w0_supplier_refused(db, s):
    """POM-CR-10 — a supplier of W0 is refused.
    Rules: create_purchase_order R3 [BUG-1017]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, account_id=s.A0.id, destination_type="storage", destination_id=s.F1.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {s.A0.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-11
@xf(X1017)
def test_pom_cr_11__w2_line_item_refused(db, s):
    """POM-CR-11 — a line item of W2 is refused.
    Rules: create_purchase_order R3 [BUG-1017]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(
            db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1,
            items=[IC(item_id=s.I9.id, quantity_ordered=Decimal("1"))],
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-12
def test_pom_cr_12__live_machine_accepted(db, s):
    """POM-CR-12 — a live factory and a live machine of the workspace are accepted.
    Rules: create_purchase_order R3."""
    result = CR(db, s, destination_type="machine", destination_id=s.M1.id, order_date=D1)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.destination_type == "machine"
    assert row.destination_id == s.M1.id


# [claude] POM-CR-13
@xf(X2874)
def test_pom_cr_13__w2_storage_refused(db, s):
    """POM-CR-13 — a storage destination of W2 is refused.
    Rules: create_purchase_order R3 [BUG-2874]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, destination_type="storage", destination_id=s.F9.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-14
@xf(X2874)
def test_pom_cr_14__w0_storage_refused(db, s):
    """POM-CR-14 — a storage destination of W0 is refused.
    Rules: create_purchase_order R3 [BUG-2874]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, destination_type="storage", destination_id=s.F0.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory with ID {s.F0.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-15
@xf(X2874)
def test_pom_cr_15__deleted_factory_refused(db, s):
    """POM-CR-15 — a deleted factory is refused.
    Rules: create_purchase_order R3 [BUG-2874]."""
    fd = _add(db, Factory(workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", **deleted_factory(s)))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, destination_type="storage", destination_id=fd.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-16
@xf(X2874)
def test_pom_cr_16__w2_machine_refused(db, s):
    """POM-CR-16 — a machine of W2 is refused.
    Rules: create_purchase_order R3 [BUG-2874]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, destination_type="machine", destination_id=s.M9.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {s.M9.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-17
@xf(X2874)
def test_pom_cr_17__deleted_machine_refused(db, s):
    """POM-CR-17 — a deleted machine is refused.
    Rules: create_purchase_order R3 [BUG-2874]."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old Press", **deleted_machine(s)))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(db, s, destination_type="machine", destination_id=md.id, order_date=D1)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# [claude] POM-CR-18
def test_pom_cr_18__project_component_stored_as_sent(db, s):
    """POM-CR-18 — a project component destination is stored as sent (revisit after launch).
    Rules: create_purchase_order R3 (projects deferred)."""
    result = CR(db, s, destination_type="project", destination_id=s.C1.id, order_date=D1)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrder, result.id)
    assert row.destination_type == "project"
    assert row.destination_id == s.C1.id


# [claude] POM-CR-19
def test_pom_cr_19__never_commits(db, s):
    """POM-CR-19 — never commits.
    Rules: create_purchase_order (flush only)."""
    n = commit_spy(db, lambda: CR(db, s, destination_type="storage", destination_id=s.F1.id, order_date=D1))
    # Then 1
    assert n == 0


# [claude] POM-CR-20
@xf(X1017)
def test_pom_cr_20__supplier_answers_first(db, s):
    """POM-CR-20 — a foreign supplier and a foreign line item: the supplier answers first.
    Rules: create_purchase_order R3, R4 [BUG-1017] (spec Overview check order, G4)."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        CR(
            db, s, account_id=s.A9.id, destination_type="storage", destination_id=s.F1.id, order_date=D1,
            items=[IC(item_id=s.I9.id, quantity_ordered=Decimal("1"))],
        )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 3
    assert po_count(db, s.W1) == 0


# =========================================================================== #
# Schemas (app.schemas.purchase_order, target schema)
# =========================================================================== #


# [claude] POM-SCH-01
@xf(X2877)
def test_pom_sch_01__a_line_quantity_of_0_is_refused(s):
    """POM-SCH-01 — a line quantity of 0 is refused.
    Rules: create_purchase_order R5, add_item R4 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("0"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-02
@xf(X2877)
def test_pom_sch_02__a_negative_line_quantity_is_refused(s):
    """POM-SCH-02 — a negative line quantity is refused.
    Rules: create_purchase_order R5, add_item R4 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("-3"), unit_price=Decimal("2.00"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-03
@xf(X2877)
def test_pom_sch_03__a_negative_price_is_refused(s):
    """POM-SCH-03 — a negative price is refused.
    Rules: create_purchase_order R5, add_item R4 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("-0.01"))
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] POM-SCH-04
def test_pom_sch_04__quantity_0_01_and_price_0_stay_allowed(s):
    """POM-SCH-04 — quantity 0.01 and price 0 stay allowed.
    Rules: create_purchase_order R5 (P1 edges)."""
    result = PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("0.01"), unit_price=Decimal("0"))
    # Then 1
    assert result.quantity_ordered == Decimal("0.01")
    assert result.unit_price == Decimal("0")


# [claude] POM-SCH-05
@xf(X2877)
def test_pom_sch_05__an_edit_to_quantity_0_is_refused():
    """POM-SCH-05 — an edit to quantity 0 is refused.
    Rules: update_item R7 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(quantity_ordered=Decimal("0"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-06
@xf(X2877)
def test_pom_sch_06__an_edit_to_a_negative_price_is_refused():
    """POM-SCH-06 — an edit to a negative price is refused.
    Rules: update_item R7 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(unit_price=Decimal("-2"))
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] POM-SCH-07
@xf(X2877)
def test_pom_sch_07__a_sync_update_to_a_negative_quantity_is_refused():
    """POM-SCH-07 — a sync update to a negative quantity is refused.
    Rules: sync_items R6 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemSyncUpdate(id=1, quantity_ordered=Decimal("-1"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-08
@xf(X2877)
def test_pom_sch_08__a_negative_approval_threshold_on_create_is_refused(s):
    """POM-SCH-08 — a negative approval threshold on create is refused.
    Rules: approval_summary R2 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderCreate(destination_type="storage", destination_id=s.F1.id, required_approvals=-1)
    assert exc.value.errors()[0]["loc"] == ("required_approvals",)


# [claude] POM-SCH-09
@xf(X2877)
def test_pom_sch_09__a_negative_approval_threshold_on_update_is_refused():
    """POM-SCH-09 — a negative approval threshold on update is refused.
    Rules: approval_summary R2 [BUG-2877]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderUpdate(required_approvals=-1)
    assert exc.value.errors()[0]["loc"] == ("required_approvals",)


# [claude] POM-SCH-10
def test_pom_sch_10__a_threshold_of_0_stays_allowed_on_create(s):
    """POM-SCH-10 — a threshold of 0 stays allowed on create.
    Rules: approval_summary R2 (BUG-1202 waiver)."""
    result = PurchaseOrderCreate(destination_type="storage", destination_id=s.F1.id, required_approvals=0)
    # Then 1
    assert result.required_approvals == 0


# [claude] POM-SCH-11
def test_pom_sch_11__a_threshold_of_0_stays_allowed_on_update():
    """POM-SCH-11 — a threshold of 0 stays allowed on update.
    Rules: approval_summary R2 (BUG-1202 waiver)."""
    result = PurchaseOrderUpdate(required_approvals=0)
    # Then 1
    assert result.required_approvals == 0


# [claude] POM-SCH-12
@xf(X2878)
def test_pom_sch_12__a_quantity_with_3_decimals_is_refused(s):
    """POM-SCH-12 — a quantity with 3 decimals is refused.
    Rules: create_purchase_order R5, add_item R4 [BUG-2878]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("1.005"), unit_price=Decimal("10"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-13
@xf(X2878)
def test_pom_sch_13__a_price_with_3_decimals_is_refused(s):
    """POM-SCH-13 — a price with 3 decimals is refused.
    Rules: create_purchase_order R5 [BUG-2878]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("1"), unit_price=Decimal("10.001"))
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] POM-SCH-14
@xf(X2878)
def test_pom_sch_14__a_quantity_with_14_integer_digits_is_refused(s):
    """POM-SCH-14 — a quantity with 14 integer digits is refused.
    Rules: create_purchase_order R5 [BUG-2878]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("10000000000000"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-15
def test_pom_sch_15__13_integer_digits_with_2_decimals_stay_allowed(s):
    """POM-SCH-15 — 13 integer digits with 2 decimals stay allowed.
    Rules: create_purchase_order R5 (P2 edge)."""
    result = PurchaseOrderItemCreate(item_id=s.I1.id, quantity_ordered=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99"))
    # Then 1
    assert result.quantity_ordered == Decimal("9999999999999.99")


# [claude] POM-SCH-16
@xf(X2878)
def test_pom_sch_16__an_edit_price_with_3_decimals_is_refused():
    """POM-SCH-16 — an edit price with 3 decimals is refused.
    Rules: update_item R7 [BUG-2878]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(unit_price=Decimal("1.005"))
    assert exc.value.errors()[0]["loc"] == ("unit_price",)


# [claude] POM-SCH-17
@xf(X2878)
def test_pom_sch_17__a_sync_update_quantity_with_3_decimals_is_refused():
    """POM-SCH-17 — a sync update quantity with 3 decimals is refused.
    Rules: sync_items R6 [BUG-2878]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemSyncUpdate(id=1, quantity_ordered=Decimal("2.345"))
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-18
@xf(X2879)
def test_pom_sch_18__an_update_sending_destination_type_null_is_refused():
    """POM-SCH-18 — an update sending destination_type null is refused.
    Rules: update_purchase_order R2 [BUG-2879]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderUpdate(destination_type=None)
    assert exc.value.errors()[0]["loc"] == ("destination_type",)


# [claude] POM-SCH-19
@xf(X2879)
def test_pom_sch_19__an_update_sending_destination_id_null_is_refused():
    """POM-SCH-19 — an update sending destination_id null is refused.
    Rules: update_purchase_order R2 [BUG-2879]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderUpdate(destination_id=None)
    assert exc.value.errors()[0]["loc"] == ("destination_id",)


# [claude] POM-SCH-20
@xf(X2879)
def test_pom_sch_20__a_line_edit_sending_quantity_ordered_null_is_refus():
    """POM-SCH-20 — a line edit sending quantity_ordered null is refused.
    Rules: update_item R1 [BUG-2879]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(quantity_ordered=None)
    assert exc.value.errors()[0]["loc"] == ("quantity_ordered",)


# [claude] POM-SCH-21
@xf(X2887)
def test_pom_sch_21__a_line_edit_sending_quantity_received_is_refused():
    """POM-SCH-21 — a line edit sending quantity_received is refused.
    Rules: update_item R3 [BUG-2887], RP5 (PO)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(quantity_received=Decimal("5"))
    assert exc.value.errors()[0]["loc"] == ("quantity_received",)


# [claude] POM-SCH-22
@xf(X2887)
def test_pom_sch_22__quantity_received_0_the_stored_value_is_refused_to():
    """POM-SCH-22 — quantity_received 0 (the stored value) is refused too.
    Rules: update_item R3 [BUG-2887]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(quantity_ordered=Decimal("10"), quantity_received=Decimal("0"))
    assert exc.value.errors()[0]["loc"] == ("quantity_received",)


# [claude] POM-SCH-23
@xf(X2887)
def test_pom_sch_23__quantity_received_null_is_refused_too():
    """POM-SCH-23 — quantity_received null is refused too.
    Rules: update_item R3 [BUG-2887]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderItemUpdate(quantity_received=None)
    assert exc.value.errors()[0]["loc"] == ("quantity_received",)


# [claude] POM-SCH-24
def test_pom_sch_24__quantity_ordered_price_and_notes_are_still_accepte():
    """POM-SCH-24 — quantity ordered, price and notes are still accepted.
    Rules: update_item R3 (BUG-2887: what the line edit keeps)."""
    result = PurchaseOrderItemUpdate(quantity_ordered=Decimal("12"), unit_price=Decimal("2.50"), notes="Zinc")
    # Then 1
    assert result.quantity_ordered == Decimal("12")
    assert result.unit_price == Decimal("2.50")
    assert result.notes == "Zinc"


# =========================================================================== #
# update_purchase_order
# =========================================================================== #


def UPD(db, s, po_id, **fields):
    """The card call `M.update_purchase_order(db, po_id=..., data=PurchaseOrderUpdate(...), workspace_id=W1.id, user_id=U2.id)`."""
    return M.update_purchase_order(db, po_id=po_id, data=PurchaseOrderUpdate(**fields), workspace_id=s.W1.id, user_id=s.U2.id)


def changes4(ev):
    """`[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in ev.metadata_json["changes"]]`."""
    return [(c["field"], c["label"], c["from_value"], c["to_value"]) for c in ev.metadata_json["changes"]]


# [claude] POM-UP-01
def test_pom_up_01__missing_order_404(db, s):
    """POM-UP-01 — a missing order: 404.
    Rules: update_purchase_order R1, R10."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, MISSING, description="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-UP-02
def test_pom_up_02__w0_order_404(db, s):
    """POM-UP-02 — an order of W0: 404.
    Rules: update_purchase_order R1."""
    o0 = mk_po(db, s, "0", k="0")
    before = snap(db, o0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o0.id, description="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o0.id} not found"
    # Then 3
    assert snap(db, o0) == before


# [claude] POM-UP-03
def test_pom_up_03__w2_order_404(db, s):
    """POM-UP-03 — an order of W2: 404.
    Rules: update_purchase_order R1."""
    o9 = mk_po(db, s, "9", k="9")
    before = snap(db, o9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o9.id, description="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"
    # Then 3
    assert snap(db, o9) == before


# [claude] POM-UP-04
@xf(X2882)
def test_pom_up_04__voided_order_refused(db, s):
    """POM-UP-04 — a voided order is refused.
    Rules: update_purchase_order R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s), supplier_confirmed=True)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, supplier_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-UP-05
@xf(X2885)
def test_pom_up_05__completed_refuses_expected_delivery(db, s):
    """POM-UP-05 — a completed order refuses a new expected delivery date.
    Rules: update_purchase_order R1b [BUG-2885], RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v), expected_delivery_date=D2)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, expected_delivery_date=D3)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot edit {DASH} purchase order is complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-UP-06
@xf(X2885)
def test_pom_up_06__completed_refuses_threshold(db, s):
    """POM-UP-06 — a completed order refuses a new approval threshold.
    Rules: update_purchase_order R1b [BUG-2885]."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, required_approvals=5)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot edit {DASH} purchase order is complete"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-07
def test_pom_up_07__sent_status_ignored(db, s):
    """POM-UP-07 — a sent current_status_id is ignored.
    Rules: update_purchase_order R2."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, current_status_id=s.SC1.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SD1.id


# [claude] POM-UP-08
def test_pom_up_08__locked_unconfirm_supplier_refused(db, s):
    """POM-UP-08 — locked: unconfirming the supplier is refused.
    Rules: update_purchase_order R3, R10."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, supplier_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot unconfirm supplier after invoice is confirmed"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-UP-09
def test_pom_up_09__locked_unconfirm_details_refused(db, s):
    """POM-UP-09 — locked: unconfirming the details is refused.
    Rules: update_purchase_order R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, details_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot unconfirm order details after invoice is confirmed"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-10
def test_pom_up_10__locked_unconfirm_items_refused(db, s):
    """POM-UP-10 — locked: unconfirming the items is refused.
    Rules: update_purchase_order R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot unconfirm order items after invoice is confirmed"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-11
def test_pom_up_11__locked_unconfirm_invoice_refused(db, s):
    """POM-UP-11 — locked: unconfirming the draft invoice is refused.
    Rules: update_purchase_order R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, invoice_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot unconfirm draft invoice after invoice is finalized"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-12
def test_pom_up_12__locked_supplier_answers_first(db, s):
    """POM-UP-12 — locked: supplier and items both unconfirmed, the supplier answers first.
    Rules: update_purchase_order R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=False, supplier_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot unconfirm supplier after invoice is confirmed"


# [claude] POM-UP-13
def test_pom_up_13__locked_confirms_true_pass(db, s):
    """POM-UP-13 — locked: sending the confirms as true passes and logs nothing.
    Rules: update_purchase_order R3, R7, _validate_section_confirm R4."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    result = UPD(db, s, o.id, supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.supplier_confirmed is True
    assert row.invoice_confirmed is True
    assert row.current_status_id == s.SR1.id
    # Then 3
    assert EV(db, o) == []


# [claude] POM-UP-14
def test_pom_up_14__locked_same_supplier_refused(db, s):
    """POM-UP-14 — locked: sending the same supplier is refused.
    Rules: update_purchase_order R4."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before


# [claude] POM-UP-15
def test_pom_up_15__supplier_confirmed_new_supplier_refused(db, s):
    """POM-UP-15 — supplier confirmed, not locked: a new supplier is refused.
    Rules: update_purchase_order R4."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A3.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Supplier is confirmed"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-16
def test_pom_up_16__unconfirm_same_request_no_help(db, s):
    """POM-UP-16 — unconfirming the supplier in the same request does not help.
    Rules: update_purchase_order R4."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A3.id, supplier_confirmed=False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Supplier is confirmed"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-17
def test_pom_up_17__locked_new_description_refused(db, s):
    """POM-UP-17 — locked: a new description is refused.
    Rules: update_purchase_order R5."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), description="Steel")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, description="Urgent")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-18
def test_pom_up_18__details_confirmed_destination_refused(db, s):
    """POM-UP-18 — details confirmed, not locked: a destination type change is refused.
    Rules: update_purchase_order R5."""
    o = mk_po(db, s, "1", details_confirmed=True, **stage(s.SP1))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, destination_type="machine", destination_id=s.M1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order details are confirmed"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-19
def test_pom_up_19__details_confirmed_order_date_refused(db, s):
    """POM-UP-19 — details confirmed: a new order date is refused.
    Rules: update_purchase_order R5."""
    o = mk_po(db, s, "1", details_confirmed=True, **stage(s.SP1))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, order_date=D2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order details are confirmed"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-20
def test_pom_up_20__locked_expected_and_threshold_saved(db, s):
    """POM-UP-20 — locked but not complete: expected delivery and threshold are saved.
    Rules: update_purchase_order R5, R8, R9."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v), expected_delivery_date=D2)
    result = UPD(db, s, o.id, expected_delivery_date=D3, required_approvals=2)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.expected_delivery_date == D3
    assert row.required_approvals == 2
    # Then 3
    assert types(db, o) == ["details_updated", "approvals_threshold_updated"]
    # Then 4
    ev = EV(db, o)
    c0 = ev[0].metadata_json["changes"][0]
    assert c0["from_value"] == "2026-03-20"
    assert c0["to_value"] == "2026-04-15"
    assert c0["label"] == "Expected delivery"
    # Then 5
    assert ev[1].description == "Changed approval threshold"
    # Then 6
    c1 = ev[1].metadata_json["changes"][0]
    assert c1["from_value"] == "All assigned"
    assert c1["to_value"] == "2"
    assert c1["label"] == "Approval threshold"


# [claude] POM-UP-21
def test_pom_up_21__confirm_supplier_planning(db, s):
    """POM-UP-21 — confirming the supplier: event, then Planning.
    Rules: update_purchase_order R6, R7, R9, _validate_section_confirm R1."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, supplier_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.supplier_confirmed is True
    assert row.current_status_id == s.SP1.id
    # Then 3
    assert types(db, o) == ["supplier_confirmed", "status_updated"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Supplier confirmed"
    assert ev[0].performed_by == s.U2.id


# [claude] POM-UP-22
def test_pom_up_22__confirm_details_logged(db, s):
    """POM-UP-22 — confirming the details logs "Order details confirmed".
    Rules: update_purchase_order R7, _validate_section_confirm R2."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    result = UPD(db, s, o.id, details_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).details_confirmed is True
    # Then 3
    assert types(db, o) == ["details_confirmed"]
    # Then 4
    assert EV(db, o)[0].description == "Order details confirmed"


# [claude] POM-UP-23
def test_pom_up_23__confirm_priced_items_logged(db, s):
    """POM-UP-23 — confirming priced items logs "Order items confirmed".
    Rules: update_purchase_order R7, _validate_section_confirm R3."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    mk_line(db, o, 1, s.I1)
    result = UPD(db, s, o.id, items_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).items_confirmed is True
    # Then 3
    assert types(db, o) == ["items_confirmed"]
    # Then 4
    assert EV(db, o)[0].description == "Order items confirmed"


# [claude] POM-UP-24
def test_pom_up_24__unconfirm_resets_approvals_and_stage(db, s):
    """POM-UP-24 — unconfirming a section resets approvals and the stage.
    Rules: update_purchase_order R7, R9, reset_approvals R2."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    result = UPD(db, s, o.id, supplier_confirmed=False)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.supplier_confirmed is False
    assert row.current_status_id == s.SD1.id
    # Then 3
    pr = reread(db, PurchaseOrderApprover, p.id)
    assert pr.approved is False
    assert pr.approved_at is None
    # Then 4
    assert types(db, o) == ["supplier_unconfirmed", "approvals_reset", "status_updated"]
    # Then 5
    ev = EV(db, o)
    assert ev[0].description == "Supplier unconfirmed"
    # Then 6
    assert ev[1].description == "Section unconfirmed (1 approval(s) cleared)"


# [claude] POM-UP-25
def test_pom_up_25__stored_confirm_value_logs_nothing(db, s):
    """POM-UP-25 — sending a stored confirm value logs nothing.
    Rules: update_purchase_order R7."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    result = UPD(db, s, o.id, supplier_confirmed=True, details_confirmed=False)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert EV(db, o) == []
    # Then 3
    pr = reread(db, PurchaseOrderApprover, p.id)
    assert pr.approved is True
    assert pr.approved_at == T2


# [claude] POM-UP-26
def test_pom_up_26__new_supplier_logged_with_names(db, s):
    """POM-UP-26 — a new supplier logs "Changed supplier" with both names.
    Rules: update_purchase_order R8, _log_section_field_updates R1, _format_field_value R1."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, account_id=s.A3.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).account_id == s.A3.id
    # Then 3
    assert types(db, o) == ["supplier_updated"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Changed supplier"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert changes4(ev[0]) == [("account_id", "Supplier", "Northwind Traders", "Alpha Parts")]


# [claude] POM-UP-27
def test_pom_up_27__changed_details_in_field_order(db, s):
    """POM-UP-27 — changed details are listed in field order.
    Rules: update_purchase_order R8, _collect_field_changes R1."""
    o = mk_po(db, s, "1", description="Steel")
    result = UPD(db, s, o.id, description="Urgent", destination_id=s.M1.id, destination_type="machine", order_date=D1)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.destination_type == "machine"
    assert row.destination_id == s.M1.id
    assert row.description == "Urgent"
    # Then 3
    assert types(db, o) == ["details_updated"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Changed order details"
    # Then 5
    assert changes4(ev[0]) == [
        ("destination_type", "Destination type", "Storage", "Machine"),
        ("destination_id", "Destination", "Main Plant", "Press 1"),
        ("description", "Description", "Steel", "Urgent"),
    ]


# [claude] POM-UP-28
def test_pom_up_28__equal_values_log_nothing(db, s):
    """POM-UP-28 — values equal to the stored ones log nothing.
    Rules: update_purchase_order R8."""
    o = mk_po(db, s, "1", description="Steel", required_approvals=2)
    result = UPD(db, s, o.id, account_id=s.A1.id, description="Steel", required_approvals=2)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert EV(db, o) == []


# [claude] POM-UP-29
@xf(X2873)
def test_pom_up_29__empty_body_no_stamp(db, s):
    """POM-UP-29 — an empty body does not stamp updated_by.
    Rules: update_purchase_order R11 [BUG-2873]."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).updated_by is None


# [claude] POM-UP-30
@xf(X2873)
def test_pom_up_30__same_values_no_stamp(db, s):
    """POM-UP-30 — the same values do not stamp updated_by.
    Rules: update_purchase_order R11 [BUG-2873]."""
    o = mk_po(db, s, "1", description="Steel")
    result = UPD(db, s, o.id, description="Steel", order_date=D1)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).updated_by is None


# [claude] POM-UP-31
def test_pom_up_31__real_change_stamps(db, s):
    """POM-UP-31 — a real change stamps updated_by.
    Rules: update_purchase_order R9, R11."""
    o = mk_po(db, s, "1", description="Steel")
    result = UPD(db, s, o.id, description="Urgent")
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.description == "Urgent"
    assert row.updated_by == s.U2.id


# [claude] POM-UP-32
def test_pom_up_32__omitted_fields_unchanged(db, s):
    """POM-UP-32 — omitted fields stay unchanged.
    Rules: update_purchase_order R2."""
    o = mk_po(db, s, "1", description="Steel", expected_delivery_date=D2, required_approvals=2)
    result = UPD(db, s, o.id, order_date=D3)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.order_date == D3
    assert row.description == "Steel"
    assert row.expected_delivery_date == D2
    assert row.required_approvals == 2
    assert row.account_id == s.A1.id


# [claude] POM-UP-33
@xf(X2879)
def test_pom_up_33__null_clears_description(db, s):
    """POM-UP-33 — an explicit null clears the description.
    Rules: update_purchase_order R2 [BUG-2879]."""
    o = mk_po(db, s, "1", description="Steel")
    result = UPD(db, s, o.id, description=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).description is None


# [claude] POM-UP-34
@xf(X2879)
def test_pom_up_34__null_restores_all_assigned(db, s):
    """POM-UP-34 — an explicit null restores "all assigned approvers".
    Rules: update_purchase_order R2 [BUG-2879]."""
    o = mk_po(db, s, "1", required_approvals=2)
    result = UPD(db, s, o.id, required_approvals=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).required_approvals is None


# [claude] POM-UP-35
@xf(X2879)
def test_pom_up_35__null_clears_supplier(db, s):
    """POM-UP-35 — an explicit null clears the supplier while it is not confirmed.
    Rules: update_purchase_order R2 [BUG-2879]."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, account_id=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).account_id is None


# [claude] POM-UP-36
@xf(X2879)
def test_pom_up_36__null_clears_dates(db, s):
    """POM-UP-36 — an explicit null clears the order date and the expected delivery date.
    Rules: update_purchase_order R2 [BUG-2879]."""
    o = mk_po(db, s, "1", expected_delivery_date=D2)
    result = UPD(db, s, o.id, order_date=None, expected_delivery_date=None)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.order_date is None
    assert row.expected_delivery_date is None


# [claude] POM-UP-37
@xf(X2874)
def test_pom_up_37__w2_storage_destination_refused(db, s):
    """POM-UP-37 — a new storage destination of W2 is refused.
    Rules: update_purchase_order R12 [BUG-2874]."""
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, destination_id=s.F9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Factory with ID {s.F9.id} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before


# [claude] POM-UP-38
@xf(X2874)
def test_pom_up_38__w0_machine_destination_refused(db, s):
    """POM-UP-38 — a new machine destination of W0 is refused.
    Rules: update_purchase_order R12 [BUG-2874]."""
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, destination_type="machine", destination_id=s.M0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {s.M0.id} not found"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-39
@xf(X2874)
def test_pom_up_39__deleted_machine_refused(db, s):
    """POM-UP-39 — a kept machine type with a deleted machine is refused.
    Rules: update_purchase_order R12 [BUG-2874]."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old Press", **deleted_machine(s)))
    o = mk_po(db, s, "1", destination_type="machine", destination_id=s.M1.id)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, destination_id=md.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Machine with ID {md.id} not found"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-40
def test_pom_up_40__live_machine_accepted(db, s):
    """POM-UP-40 — a new live machine of the workspace is accepted.
    Rules: update_purchase_order R9, R12."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, destination_type="machine", destination_id=s.M1.id)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.destination_type == "machine"
    assert row.destination_id == s.M1.id


# [claude] POM-UP-41
@xf(X1017)
def test_pom_up_41__w2_supplier_refused(db, s):
    """POM-UP-41 — a supplier of W2 is refused.
    Rules: update_purchase_order R13 [BUG-1017]."""
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-42
@xf(X1017)
def test_pom_up_42__invoice_id_refused_by_schema(db, s):
    """POM-UP-42 — a sent invoice_id is refused by the schema.
    Rules: update_purchase_order R13, R13a [BUG-1017] (G3)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderUpdate(invoice_id=v.id)
    # Then 2
    assert "invoice_id" in exc.value.errors()[0]["loc"]
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-43
@xf(X2872)
def test_pom_up_43__order_read_for_update(db, s):
    """POM-UP-43 — the order row is read FOR UPDATE before the checks.
    Rules: update_purchase_order R14 [BUG-2872]."""
    o = mk_po(db, s, "1")
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = UPD(db, s, o_id, description="Urgent")
    # Then 1
    assert result.id == o_id
    # Then 2
    assert rec.locks_first()


# [claude] POM-UP-44
def test_pom_up_44__never_commits(db, s):
    """POM-UP-44 — never commits.
    Rules: update_purchase_order (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: UPD(db, s, o.id, description="Urgent"))
    # Then 1
    assert n == 0


# [claude] POM-UP-45
def test_pom_up_45__foreign_supplier_on_confirmed_section_guard(db, s):
    """POM-UP-45 — a foreign supplier on a supplier-confirmed order: the section guard answers.
    Rules: update_purchase_order R4, R13 (spec Overview check order, G4)."""
    o = mk_po(db, s, "1", supplier_confirmed=True, **stage(s.SP1))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A9.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Supplier is confirmed"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-46
@xf(X1017)
def test_pom_up_46__supplier_before_destination(db, s):
    """POM-UP-46 — a foreign supplier and a foreign destination: the supplier answers first.
    Rules: update_purchase_order R12 [BUG-2874], R13 [BUG-1017] (spec Overview check order, G4)."""
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, account_id=s.A9.id, destination_type="storage", destination_id=s.F9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Account with ID {s.A9.id} not found"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-47
@xf(X2882)
def test_pom_up_47__voided_before_complete(db, s):
    """POM-UP-47 — voided and complete: the voided check answers first.
    Rules: update_purchase_order R1a [BUG-2882], R1b [BUG-2885] (spec Overview check order, G4)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **{**complete_by(s, v), **voided(s)}, expected_delivery_date=D2)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, expected_delivery_date=D3)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert snap(db, o) == before
    # Then 4
    assert EV(db, o) == []


# [claude] POM-UP-48
@xf(X2885)
def test_pom_up_48__complete_before_lock_guard(db, s):
    """POM-UP-48 — complete and financially locked: the completed check answers before the lock guard.
    Rules: update_purchase_order R1b [BUG-2885], R5 (spec Overview check order, G4)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v), description="Steel")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, description="Urgent")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot edit {DASH} purchase order is complete"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-UP-49
@xf(X1017)
def test_pom_up_49__invoice_id_null_refused_by_schema():
    """POM-UP-49 — a sent invoice_id of null is refused by the schema too.
    Rules: update_purchase_order R13a [BUG-1017] (G3)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        PurchaseOrderUpdate(invoice_id=None)
    # Then 2
    assert "invoice_id" in exc.value.errors()[0]["loc"]


# [claude] POM-UP-50
def test_pom_up_50__order_date_label(db, s):
    """POM-UP-50 — a new order date is logged with the label "Order date".
    Rules: update_purchase_order R8, _collect_field_changes R1."""
    o = mk_po(db, s, "1")
    result = UPD(db, s, o.id, order_date=D2)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).order_date == D2
    # Then 3
    assert types(db, o) == ["details_updated"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Changed order details"
    assert ev[0].performed_by == s.U2.id
    # Then 5
    assert changes4(ev[0]) == [("order_date", "Order date", "2026-03-02", "2026-03-20")]


# [claude] POM-UP-51
def test_pom_up_51__unconfirm_draft_invoice_not_locked(db, s):
    """POM-UP-51 — not locked: unconfirming the draft invoice logs it and resets approvals.
    Rules: update_purchase_order R3 (not locked), R7, reset_approvals R2."""
    o = mk_po(db, s, "1", **confirmed(s), invoice_confirmed=True)
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    result = UPD(db, s, o.id, invoice_confirmed=False)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.invoice_confirmed is False
    assert row.supplier_confirmed is True
    assert row.details_confirmed is True
    assert row.items_confirmed is True
    assert row.current_status_id == s.SP1.id
    # Then 3
    pr = reread(db, PurchaseOrderApprover, p.id)
    assert pr.approved is False
    assert pr.approved_at is None
    # Then 4
    assert types(db, o) == ["invoice_unconfirmed", "approvals_reset"]
    # Then 5
    ev = EV(db, o)
    assert ev[0].description == "Draft invoice unconfirmed"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert ev[1].description == "Section unconfirmed (1 approval(s) cleared)"


# =========================================================================== #
# _validate_section_confirm (through update_purchase_order)
# =========================================================================== #


# [claude] POM-VC-01
def test_pom_vc_01__confirm_supplier_none_set(db, s):
    """POM-VC-01 — confirming the supplier with none set: 400.
    Rules: _validate_section_confirm R1, update_purchase_order R6, R10."""
    o = mk_po(db, s, "1", account_id=None)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, supplier_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select a supplier before confirming"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, o) == before
    # Then 5
    assert EV(db, o) == []


# [claude] POM-VC-02
def test_pom_vc_02__supplier_in_same_request(db, s):
    """POM-VC-02 — a supplier sent in the same request satisfies the check.
    Rules: _validate_section_confirm R1."""
    o = mk_po(db, s, "1", account_id=None)
    result = UPD(db, s, o.id, account_id=s.A1.id, supplier_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.account_id == s.A1.id
    assert row.supplier_confirmed is True


# [claude] POM-VC-03
def test_pom_vc_03__details_without_order_date(db, s):
    """POM-VC-03 — confirming the details without an order date: 400.
    Rules: _validate_section_confirm R2."""
    o = mk_po(db, s, "1", order_date=None)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, details_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete destination, location, and order date before confirming"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-VC-04
def test_pom_vc_04__details_empty_destination_type(db, s):
    """POM-VC-04 — confirming the details with an empty destination type: 400.
    Rules: _validate_section_confirm R2."""
    o = mk_po(db, s, "1", destination_type="")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, details_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete destination, location, and order date before confirming"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-VC-05
def test_pom_vc_05__order_date_in_same_request(db, s):
    """POM-VC-05 — an order date sent in the same request satisfies the check.
    Rules: _validate_section_confirm R2."""
    o = mk_po(db, s, "1", order_date=None)
    result = UPD(db, s, o.id, order_date=D2, details_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.order_date == D2
    assert row.details_confirmed is True


# [claude] POM-VC-06
def test_pom_vc_06__items_no_lines(db, s):
    """POM-VC-06 — confirming items with no lines: 400.
    Rules: _validate_section_confirm R3."""
    o = mk_po(db, s, "1")
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Add at least one line item before confirming"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-VC-07
def test_pom_vc_07__items_unpriced_line(db, s):
    """POM-VC-07 — confirming items with an unpriced line: 400.
    Rules: _validate_section_confirm R3."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I2, unit_price=None, line_subtotal=None)
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Enter unit prices to confirm"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-VC-08
def test_pom_vc_08__items_zero_price_line(db, s):
    """POM-VC-08 — confirming items with a line at 0.00: 400.
    Rules: _validate_section_confirm R3."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1, unit_price=Decimal("0.00"), line_subtotal=Decimal("0.00"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Enter unit prices to confirm"


# [claude] POM-VC-09
def test_pom_vc_09__invoice_confirm_by_hand(db, s):
    """POM-VC-09 — confirming the draft invoice by hand: 400.
    Rules: _validate_section_confirm R4."""
    o = mk_po(db, s, "1", **confirmed(s))
    before = snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, invoice_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Draft invoice is confirmed when you finalize the invoice {DASH} use Finalize Invoice instead"
    # Then 3
    assert snap(db, o) == before


# [claude] POM-VC-10
def test_pom_vc_10__supplier_answers_first(db, s):
    """POM-VC-10 — supplier and items both invalid: the supplier answers first.
    Rules: _validate_section_confirm R1, R3 (order)."""
    o = mk_po(db, s, "1", account_id=None)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UPD(db, s, o.id, items_confirmed=True, supplier_confirmed=True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Select a supplier before confirming"


# [claude] POM-VC-11
def test_pom_vc_11__confirmed_section_not_revalidated(db, s):
    """POM-VC-11 — a section already confirmed is not re-validated.
    Rules: _validate_section_confirm (only when stored false)."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    result = UPD(db, s, o.id, items_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    assert EV(db, o) == []


# [claude] POM-VC-12
def test_pom_vc_12__destination_type_in_same_request(db, s):
    """POM-VC-12 — a destination type sent in the same request satisfies the check.
    Rules: _validate_section_confirm R2 ("after the update")."""
    o = mk_po(db, s, "1", destination_type="")
    result = UPD(db, s, o.id, destination_type="machine", destination_id=s.M1.id, details_confirmed=True)
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrder, o.id)
    assert row.destination_type == "machine"
    assert row.destination_id == s.M1.id
    assert row.details_confirmed is True
    # Then 3
    assert "details_confirmed" in types(db, o)


def mem_po(s):
    """Card shorthand "R = an in-memory PurchaseOrder(...)" of VC-13 / VC-14, never added to the session."""
    return PurchaseOrder(
        workspace_id=s.W1.id, account_id=s.A1.id, destination_type=None, destination_id=None, order_date=D1,
        supplier_confirmed=False, details_confirmed=False, items_confirmed=False, invoice_confirmed=False,
    )


# [claude] POM-VC-13
def test_pom_vc_13__direct_type_and_id_arrive(db, s):
    """POM-VC-13 — direct call: destination type and id both arrive in the update.
    Rules: _validate_section_confirm R2 ("after the update")."""
    r = mem_po(s)
    result = M._validate_section_confirm(
        record=r, update_dict={"destination_type": "machine", "destination_id": s.M1.id, "details_confirmed": True},
        session=db, workspace_id=s.W1.id,
    )
    # Then 1
    assert result is None  # reached: the call returned without raising
    # Then 2
    assert_session_clean(db)


# [claude] POM-VC-14
def test_pom_vc_14__direct_only_type_arrives_400(db, s):
    """POM-VC-14 — direct call: only the type arrives and the id stays empty: 400.
    Rules: _validate_section_confirm R2."""
    r = mem_po(s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_section_confirm(
            record=r, update_dict={"destination_type": "machine", "details_confirmed": True}, session=db, workspace_id=s.W1.id,
        )
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Complete destination, location, and order date before confirming"


# =========================================================================== #
# _format_scalar_value
# =========================================================================== #


# [claude] POM-SF-01
def test_pom_sf_01__none_is_dash():
    """POM-SF-01 — None is a dash.
    Rules: _format_scalar_value R1."""
    result = M._format_scalar_value("notes", None)
    # Then 1
    assert result == DASH


# [claude] POM-SF-02
def test_pom_sf_02__date_iso():
    """POM-SF-02 — a date is ISO text.
    Rules: _format_scalar_value R2."""
    result = M._format_scalar_value("order_date", date(2026, 3, 4))
    # Then 1
    assert result == "2026-03-04"


# [claude] POM-SF-03
def test_pom_sf_03__whole_decimal_drops_fraction():
    """POM-SF-03 — a whole Decimal drops its fraction.
    Rules: _format_scalar_value R3."""
    result = M._format_scalar_value("quantity_ordered", Decimal("5.00"))
    # Then 1
    assert result == "5"


# [claude] POM-SF-04
def test_pom_sf_04__fractional_decimal_normalized():
    """POM-SF-04 — a fractional Decimal is normalized.
    Rules: _format_scalar_value R3."""
    result = M._format_scalar_value("unit_price", Decimal("1.50"))
    # Then 1
    assert result == "1.5"


# [claude] POM-SF-05
def test_pom_sf_05__text_trimmed():
    """POM-SF-05 — text is trimmed.
    Rules: _format_scalar_value R4."""
    result = M._format_scalar_value("notes", "  Zinc coat ")
    # Then 1
    assert result == "Zinc coat"


# [claude] POM-SF-06
def test_pom_sf_06__blank_text_dash():
    """POM-SF-06 — blank text is a dash.
    Rules: _format_scalar_value R4."""
    result = M._format_scalar_value("notes", "   ")
    # Then 1
    assert result == DASH


# [claude] POM-SF-07
def test_pom_sf_07__int_text():
    """POM-SF-07 — an int becomes its text.
    Rules: _format_scalar_value R4."""
    result = M._format_scalar_value("line_number", 7)
    # Then 1
    assert result == "7"


# =========================================================================== #
# _format_destination_id
# =========================================================================== #


def FDI(db, s, dtype, dest_id):
    """The card call `M._format_destination_id(db, workspace_id=W1.id, destination_type=..., destination_id=...)`."""
    return M._format_destination_id(db, workspace_id=s.W1.id, destination_type=dtype, destination_id=dest_id)


# [claude] POM-FD-01
def test_pom_fd_01__no_id_dash(db, s):
    """POM-FD-01 — no id is a dash.
    Rules: _format_destination_id R1."""
    result = FDI(db, s, "storage", None)
    # Then 1
    assert result == DASH


# [claude] POM-FD-02
def test_pom_fd_02__storage_any_case(db, s):
    """POM-FD-02 — storage names the factory, type in any case.
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "STORAGE", s.F1.id)
    # Then 1
    assert result == "Main Plant"


# [claude] POM-FD-03
def test_pom_fd_03__w2_factory_fallback(db, s):
    """POM-FD-03 — a factory of W2 falls back to "Factory #<id>".
    Rules: _format_destination_id R2."""
    s.F9.name = "East Plant"
    db.flush()
    result = FDI(db, s, "storage", s.F9.id)
    # Then 1
    assert result == f"Factory #{s.F9.id}"


# [claude] POM-FD-04
def test_pom_fd_04__w0_factory_fallback(db, s):
    """POM-FD-04 — a factory of W0 falls back too.
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "storage", s.F0.id)
    # Then 1
    assert result == f"Factory #{s.F0.id}"


# [claude] POM-FD-05
def test_pom_fd_05__missing_factory_fallback(db, s):
    """POM-FD-05 — a missing factory id falls back.
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "storage", MISSING)
    # Then 1
    assert result == f"Factory #{MISSING}"


# [claude] POM-FD-06
def test_pom_fd_06__deleted_factory_named(db, s):
    """POM-FD-06 — a deleted factory still shows its name.
    Rules: _format_destination_id R2."""
    fd = _add(db, Factory(workspace_id=s.W1.id, name="Old Plant", abbreviation="OP", **deleted_factory(s)))
    result = FDI(db, s, "storage", fd.id)
    # Then 1
    assert result == "Old Plant"


# [claude] POM-FD-07
def test_pom_fd_07__machine_named(db, s):
    """POM-FD-07 — machine names the machine.
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "machine", s.M1.id)
    # Then 1
    assert result == "Press 1"


# [claude] POM-FD-08
def test_pom_fd_08__w2_machine_fallback(db, s):
    """POM-FD-08 — a machine of W2 falls back to "Machine #<id>".
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "machine", s.M9.id)
    # Then 1
    assert result == f"Machine #{s.M9.id}"


# [claude] POM-FD-09
def test_pom_fd_09__deleted_machine_named(db, s):
    """POM-FD-09 — a deleted machine still shows its name.
    Rules: _format_destination_id R2."""
    md = _add(db, Machine(workspace_id=s.W1.id, factory_id=s.F1.id, name="Old Press", **deleted_machine(s)))
    result = FDI(db, s, "machine", md.id)
    # Then 1
    assert result == "Old Press"


# [claude] POM-FD-10
def test_pom_fd_10__project_component_named(db, s):
    """POM-FD-10 — project names the component.
    Rules: _format_destination_id R2 (revisit after launch)."""
    result = FDI(db, s, "project", s.C1.id)
    # Then 1
    assert result == "Part 1"


# [claude] POM-FD-11
def test_pom_fd_11__missing_component_fallback(db, s):
    """POM-FD-11 — a missing project component falls back.
    Rules: _format_destination_id R2 (revisit after launch)."""
    result = FDI(db, s, "project", MISSING)
    # Then 1
    assert result == f"Project component #{MISSING}"


# [claude] POM-FD-12
def test_pom_fd_12__other_type_hash_id(db, s):
    """POM-FD-12 — any other type shows "#<id>".
    Rules: _format_destination_id R2."""
    result = FDI(db, s, "dock", s.F1.id)
    # Then 1
    assert result == f"#{s.F1.id}"


# [claude] POM-FD-13
def test_pom_fd_13__no_type_hash_id(db, s):
    """POM-FD-13 — no type shows "#<id>".
    Rules: _format_destination_id R2."""
    result = FDI(db, s, None, s.F1.id)
    # Then 1
    assert result == f"#{s.F1.id}"


# =========================================================================== #
# _format_field_value
# =========================================================================== #


# [claude] POM-FV-01
def test_pom_fv_01__account_name_fallback_dash(db, s):
    """POM-FV-01 — account: name, foreign fallback, dash.
    Rules: _format_field_value R1."""
    result = [M._format_field_value(db, workspace_id=s.W1.id, field="account_id", value=v) for v in (s.A1.id, s.A9.id, None)]
    # Then 1
    assert result == ["Northwind Traders", f"Account #{s.A9.id}", DASH]


# [claude] POM-FV-02
def test_pom_fv_02__destination_type_labels(db, s):
    """POM-FV-02 — destination type labels.
    Rules: _format_field_value R2."""
    result = [
        M._format_field_value(db, workspace_id=s.W1.id, field="destination_type", value=v)
        for v in ("storage", "MACHINE", "project", "dock", "", None)
    ]
    # Then 1
    assert result == ["Storage", "Machine", "Project", "dock", DASH, DASH]


# [claude] POM-FV-03
def test_pom_fv_03__destination_id_uses_type(db, s):
    """POM-FV-03 — destination id uses the given type.
    Rules: _format_field_value R3."""
    result = M._format_field_value(db, workspace_id=s.W1.id, field="destination_id", value=s.M1.id, destination_type="machine")
    # Then 1
    assert result == "Press 1"


# [claude] POM-FV-04
def test_pom_fv_04__threshold_text(db, s):
    """POM-FV-04 — threshold: none is "All assigned", a number is its text.
    Rules: _format_field_value R4."""
    result = [M._format_field_value(db, workspace_id=s.W1.id, field="required_approvals", value=v) for v in (None, 0, 3)]
    # Then 1
    assert result == ["All assigned", "0", "3"]


# [claude] POM-FV-05
def test_pom_fv_05__status_name_fallback_dash(db, s):
    """POM-FV-05 — status: name, missing fallback, dash.
    Rules: _format_field_value R5."""
    result = [
        M._format_field_value(db, workspace_id=s.W1.id, field="current_status_id", value=v)
        for v in (s.SR1.id, MISSING, None)
    ]
    # Then 1
    assert result == ["Receiving", f"Status #{MISSING}", DASH]


# [claude] POM-FV-06
@xf(X2875)
def test_pom_fv_06__w2_status_fallback(db, s):
    """POM-FV-06 — a status of W2 is shown as "Status #<id>".
    Rules: _format_field_value R5 [BUG-2875]."""
    result = M._format_field_value(db, workspace_id=s.W1.id, field="current_status_id", value=s.SR9.id)
    # Then 1
    assert result == f"Status #{s.SR9.id}"


# [claude] POM-FV-07
@xf(X2875)
def test_pom_fv_07__w0_status_fallback(db, s):
    """POM-FV-07 — a status of W0 is shown as "Status #<id>".
    Rules: _format_field_value R5 [BUG-2875]."""
    result = M._format_field_value(db, workspace_id=s.W1.id, field="current_status_id", value=s.SD0.id)
    # Then 1
    assert result == f"Status #{s.SD0.id}"


# [claude] POM-FV-08
def test_pom_fv_08__other_field_scalar(db, s):
    """POM-FV-08 — any other field is formatted as a scalar.
    Rules: _format_field_value R6."""
    result = M._format_field_value(db, workspace_id=s.W1.id, field="expected_delivery_date", value=D2)
    # Then 1
    assert result == "2026-03-20"


# [claude] POM-FV-09
def test_pom_fv_09__none_ordinary_field_dash(db, s):
    """POM-FV-09 — None in an ordinary field is a dash.
    Rules: _format_field_value R6, _format_scalar_value R1."""
    result = [
        M._format_field_value(db, workspace_id=s.W1.id, field=f, value=None)
        for f in ("description", "order_date", "expected_delivery_date")
    ]
    # Then 1
    assert result == [DASH, DASH, DASH]


# =========================================================================== #
# _collect_field_changes, _collect_item_field_changes, _log_field_change_event
# =========================================================================== #


# [claude] POM-CF-01
def test_pom_cf_01__changed_fields_in_dict_order(db, s):
    """POM-CF-01 — changed fields in dict order; equal and absent ones skipped.
    Rules: _collect_field_changes R1."""
    o = mk_po(db, s, "1", description="Steel", expected_delivery_date=D2)
    result = M._collect_field_changes(
        db, workspace_id=s.W1.id, record=o,
        update_dict={"description": "Urgent", "order_date": D1, "expected_delivery_date": D3},
        fields={
            "destination_type": "Destination type", "order_date": "Order date",
            "expected_delivery_date": "Expected delivery", "description": "Description",
        },
    )
    # Then 1
    assert [(c["field"], c["label"], c["from_value"], c["to_value"]) for c in result] == [
        ("expected_delivery_date", "Expected delivery", "2026-03-20", "2026-04-15"),
        ("description", "Description", "Steel", "Urgent"),
    ]
    # Then 2
    assert set(result[0].keys()) == {"field", "label", "from_value", "to_value"}


# [claude] POM-CF-02
def test_pom_cf_02__nothing_changed_empty(db, s):
    """POM-CF-02 — nothing changed: an empty list.
    Rules: _collect_field_changes R1."""
    o = mk_po(db, s, "1", description="Steel")
    result = M._collect_field_changes(
        db, workspace_id=s.W1.id, record=o, update_dict={"description": "Steel"}, fields={"description": "Description", "order_date": "Order date"},
    )
    # Then 1
    assert result == []


# [claude] POM-CF-03
def test_pom_cf_03__destination_id_from_and_to_types(db, s):
    """POM-CF-03 — a destination id: "from" with the stored type, "to" with the new type.
    Rules: _collect_field_changes R1."""
    o = mk_po(db, s, "1")
    result = M._collect_field_changes(
        db, workspace_id=s.W1.id, record=o,
        update_dict={"destination_type": "machine", "destination_id": s.M1.id}, fields={"destination_id": "Destination"},
    )
    # Then 1
    assert [(c["field"], c["label"], c["from_value"], c["to_value"]) for c in result] == [("destination_id", "Destination", "Main Plant", "Press 1")]


# [claude] POM-CF-04
def test_pom_cf_04__labels(db, s):
    """POM-CF-04 — the labels of supplier, order date, status and approval threshold.
    Rules: _collect_field_changes R1 (G2)."""
    o = mk_po(db, s, "1", required_approvals=1)
    result = M._collect_field_changes(
        db, workspace_id=s.W1.id, record=o,
        update_dict={"account_id": s.A3.id, "order_date": D2, "current_status_id": s.SP1.id, "required_approvals": 2},
        fields={
            "account_id": "Supplier", "order_date": "Order date", "current_status_id": "Status",
            "required_approvals": "Approval threshold",
        },
    )
    # Then 1
    assert [(c["field"], c["label"]) for c in result] == [
        ("account_id", "Supplier"),
        ("order_date", "Order date"),
        ("current_status_id", "Status"),
        ("required_approvals", "Approval threshold"),
    ]


# [claude] POM-CI-01
def test_pom_ci_01__line_changes_with_labels(db, s):
    """POM-CI-01 — line quantity and price changes with their labels.
    Rules: _collect_item_field_changes R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, notes="Zinc")
    result = M._collect_item_field_changes(
        record=line, update_dict={"quantity_ordered": Decimal("12"), "unit_price": Decimal("2.50"), "notes": "Brass"},
    )
    # Then 1
    assert result == [
        {"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "12"},
        {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "2.5"},
        {"field": "notes", "label": "Notes", "from_value": "Zinc", "to_value": "Brass"},
    ]


# [claude] POM-CI-02
def test_pom_ci_02__numeric_equality_received_never_listed(db, s):
    """POM-CI-02 — equality is numeric; received is never listed.
    Rules: _collect_item_field_changes R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    result = M._collect_item_field_changes(
        record=line, update_dict={"quantity_ordered": Decimal("10"), "unit_price": Decimal("2.0"), "quantity_received": Decimal("4")},
    )
    # Then 1
    assert result == []


# [claude] POM-LF-01
def test_pom_lf_01__one_event_with_changes_and_extra(db, s):
    """POM-LF-01 — one event with the changes plus extra metadata.
    Rules: _log_field_change_event R1."""
    o = mk_po(db, s, "1")
    result = M._log_field_change_event(
        db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id, event_type="item_updated",
        description="Updated item: Bolt", changes=[{"field": "notes"}], extra_metadata={"line_number": 1},
    )
    ev = EV(db, o)
    # Then 1
    assert len(ev) == 1
    # Then 2
    assert ev[0].event_type == "item_updated"
    assert ev[0].description == "Updated item: Bolt"
    assert ev[0].performed_by == s.U2.id
    # Then 3
    assert ev[0].metadata_json == {"changes": [{"field": "notes"}], "line_number": 1}
    # Then 4
    assert result is None


# [claude] POM-LF-02
def test_pom_lf_02__never_commits(db, s):
    """POM-LF-02 — never commits.
    Rules: _log_field_change_event (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(
        db,
        lambda: M._log_field_change_event(
            db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id, event_type="x", description="y", changes=[],
        ),
    )
    # Then 1
    assert n == 0


# =========================================================================== #
# _confirmed_supplier/detail_update_fields, _items_structure_confirmed, _base_sections_confirmed
# =========================================================================== #

DETAIL_FIELDS = {"destination_type", "destination_id", "order_date", "description"}


# [claude] POM-CU-01
def test_pom_cu_01__locked_blocks_fields(db, s):
    """POM-CU-01 — locked: the supplier field and the four detail fields are blocked.
    Rules: _confirmed_supplier_update_fields / _confirmed_detail_update_fields R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id)
    result = (M._confirmed_supplier_update_fields(db, record=o), M._confirmed_detail_update_fields(db, record=o))
    # Then 1
    assert set(result[0]) == {"account_id"}
    # Then 2
    assert set(result[1]) == DETAIL_FIELDS


# [claude] POM-CU-02
def test_pom_cu_02__confirmed_sections_block(db, s):
    """POM-CU-02 — confirmed sections block their fields without a lock.
    Rules: _confirmed_supplier_update_fields / _confirmed_detail_update_fields R1."""
    o = mk_po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    result = (M._confirmed_supplier_update_fields(db, record=o), M._confirmed_detail_update_fields(db, record=o))
    # Then 1
    assert set(result[0]) == {"account_id"}
    # Then 2
    assert set(result[1]) == DETAIL_FIELDS


# [claude] POM-CU-03
def test_pom_cu_03__nothing_blocked(db, s):
    """POM-CU-03 — nothing confirmed, no lock: nothing blocked.
    Rules: _confirmed_supplier_update_fields / _confirmed_detail_update_fields R1."""
    v = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=v.id, items_confirmed=True)
    result = (M._confirmed_supplier_update_fields(db, record=o), M._confirmed_detail_update_fields(db, record=o))
    # Then 1
    assert set(result[0]) == set()
    # Then 2
    assert set(result[1]) == set()


# [claude] POM-IS-01
def test_pom_is_01__items_confirmed_locked_or_neither(db, s):
    """POM-IS-01 — items confirmed, locked, or neither.
    Rules: _items_structure_confirmed R1."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    oa = mk_po(db, s, "1", items_confirmed=True)
    ob = mk_po(db, s, "2", invoice_id=v.id)
    oc = mk_po(db, s, "3", supplier_confirmed=True, details_confirmed=True)
    result = [M._items_structure_confirmed(db, po=o) for o in (oa, ob, oc)]
    # Then 1
    assert result == [True, True, False]


# [claude] POM-BS-01
def test_pom_bs_01__all_three_confirmed(db, s):
    """POM-BS-01 — all three base sections confirmed; invoice flag not read.
    Rules: _base_sections_confirmed R1."""
    o = mk_po(db, s, "1", **confirmed(s))
    result = M._base_sections_confirmed(o)
    # Then 1
    assert result is True


# [claude] POM-BS-02
def test_pom_bs_02__one_section_missing(db, s):
    """POM-BS-02 — one base section missing.
    Rules: _base_sections_confirmed R1."""
    oa = mk_po(db, s, "1", supplier_confirmed=True, details_confirmed=True, invoice_confirmed=True)
    ob = mk_po(db, s, "2", supplier_confirmed=True, items_confirmed=True)
    oc = mk_po(db, s, "3", details_confirmed=True, items_confirmed=True)
    result = [M._base_sections_confirmed(o) for o in (oa, ob, oc)]
    # Then 1
    assert result == [False, False, False]


# =========================================================================== #
# apply_post_invoice_confirms
# =========================================================================== #


# [claude] POM-AP-01
def test_pom_ap_01__all_four_confirmed_five_events(db, s):
    """POM-AP-01 — nothing confirmed: all four confirmed, five events in order.
    Rules: apply_post_invoice_confirms R1, R2."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    o = reread(db, PurchaseOrder, o.id)
    result = M.apply_post_invoice_confirms(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.supplier_confirmed is True
    assert row.details_confirmed is True
    assert row.items_confirmed is True
    assert row.invoice_confirmed is True
    # Then 2
    assert row.current_status_id == s.SD1.id
    # Then 3
    assert snap(db, p) == before
    # Then 4
    assert types(db, o) == ["invoice_created", "supplier_confirmed", "details_confirmed", "items_confirmed", "invoice_confirmed"]
    # Then 5
    assert [e.description for e in EV(db, o)] == [
        "Invoice created",
        "Supplier confirmed after invoice created",
        "Order details confirmed after invoice created",
        "Order items confirmed after invoice created",
        "Draft invoice confirmed after invoice finalized",
    ]
    # Then 6
    assert result is None


# [claude] POM-AP-02
def test_pom_ap_02__already_confirmed_log_nothing(db, s):
    """POM-AP-02 — sections already confirmed log nothing.
    Rules: apply_post_invoice_confirms R2."""
    o = mk_po(db, s, "1", supplier_confirmed=True, details_confirmed=True)
    M.apply_post_invoice_confirms(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    row = reread(db, PurchaseOrder, o.id)
    assert row.items_confirmed is True
    assert row.invoice_confirmed is True
    # Then 2
    assert types(db, o) == ["invoice_created", "items_confirmed", "invoice_confirmed"]


# [claude] POM-AP-03
def test_pom_ap_03__everything_confirmed_only_created(db, s):
    """POM-AP-03 — everything confirmed: only "Invoice created".
    Rules: apply_post_invoice_confirms R1."""
    o = mk_po(db, s, "1", **confirmed(s), invoice_confirmed=True)
    M.apply_post_invoice_confirms(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert types(db, o) == ["invoice_created"]


# [claude] POM-AP-04
def test_pom_ap_04__never_commits(db, s):
    """POM-AP-04 — never commits.
    Rules: apply_post_invoice_confirms (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: M.apply_post_invoice_confirms(db, po=o, workspace_id=s.W1.id, user_id=s.U2.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# get_purchase_order
# =========================================================================== #


# [claude] POM-GP-01
def test_pom_gp_01__voided_included(db, s):
    """POM-GP-01 — the workspace's order, voided ones included.
    Rules: get_purchase_order R1."""
    o = mk_po(db, s, "1", **voided(s))
    result = M.get_purchase_order(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == o.id
    assert result.voided is True


# [claude] POM-GP-02
def test_pom_gp_02__missing_404(db, s):
    """POM-GP-02 — a missing order: 404.
    Rules: get_purchase_order R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_purchase_order(db, po_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"


# [claude] POM-GP-03
def test_pom_gp_03__w0_404(db, s):
    """POM-GP-03 — an order of W0: 404.
    Rules: get_purchase_order R1."""
    o0 = mk_po(db, s, "0", k="0")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_purchase_order(db, po_id=o0.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o0.id} not found"


# [claude] POM-GP-04
def test_pom_gp_04__w2_404(db, s):
    """POM-GP-04 — an order of W2: 404.
    Rules: get_purchase_order R1."""
    o9 = mk_po(db, s, "9", k="9")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_purchase_order(db, po_id=o9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"


# =========================================================================== #
# Hub pass-throughs
# =========================================================================== #


def add_pos(db, s, n):
    """Card step `for k in range(n): db.add(PurchaseOrder(... po_number=f"PO-{TAG}-{k:03d}" ...))`, then one flush."""
    for k in range(n):
        db.add(
            PurchaseOrder(
                workspace_id=s.W1.id, po_number=f"PO-{s.TAG}-{k:03d}", account_id=s.A1.id, destination_type="storage",
                destination_id=s.F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"),
                current_status_id=s.SD1.id, order_workflow_id=s.WF1.id, created_by=s.U1.id,
            )
        )
    db.flush()


# [claude] POM-HUB-01
def test_pom_hub_01__list_default_page(db, s):
    """POM-HUB-01 — the list returns the DAO's page with the defaults skip 0, limit 50.
    Rules: hub R1 (list_purchase_orders_for_hub)."""
    from app.dao.purchase_order import purchase_order_dao

    add_pos(db, s, 52)
    result = M.list_purchase_orders_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 50
    # Then 2
    assert result == purchase_order_dao.list_for_hub(db, workspace_id=s.W1.id, skip=0, limit=50)


# [claude] POM-HUB-02
def test_pom_hub_02__skip_limit_filters_passed(db, s):
    """POM-HUB-02 — skip, limit and filters are passed through.
    Rules: hub R1 (list_purchase_orders_for_hub)."""
    from app.dao.purchase_order import purchase_order_dao

    add_pos(db, s, 6)
    mk_po(db, s, "A", account_id=s.A3.id)
    result = M.list_purchase_orders_for_hub(db, workspace_id=s.W1.id, skip=2, limit=3, account_id=s.A1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert result == purchase_order_dao.list_for_hub(db, workspace_id=s.W1.id, skip=2, limit=3, account_id=s.A1.id)


# [claude] POM-HUB-03
def test_pom_hub_03__count_is_dao_count(db, s):
    """POM-HUB-03 — the count is the DAO's count.
    Rules: hub R1 (count_purchase_orders_for_hub)."""
    from app.dao.purchase_order import purchase_order_dao

    mk_po(db, s, "A")
    mk_po(db, s, "B", account_id=s.A3.id)
    mk_po(db, s, "9", k="9")
    result = M.count_purchase_orders_for_hub(db, workspace_id=s.W1.id, account_id=s.A1.id)
    # Then 1
    assert result == purchase_order_dao.count_for_hub(db, workspace_id=s.W1.id, account_id=s.A1.id)
    # Then 2
    assert result == 1


# [claude] POM-HUB-04
def test_pom_hub_04__stats_are_dao_stats(db, s):
    """POM-HUB-04 — the stats are the DAO's stats.
    Rules: hub R1 (purchase_order_hub_stats)."""
    from app.dao.purchase_order import purchase_order_dao

    mk_po(db, s, "A", total_amount=Decimal("40.00"), subtotal=Decimal("40.00"))
    result = M.purchase_order_hub_stats(db, workspace_id=s.W1.id)
    # Then 1
    assert result == purchase_order_dao.aggregate_hub_stats(db, workspace_id=s.W1.id)


# [claude] POM-HUB-05
def test_pom_hub_05__recent_default_limit(db, s):
    """POM-HUB-05 — recent returns the DAO's list with the default limit 10.
    Rules: hub R1 (list_purchase_orders_recent_for_hub)."""
    from app.dao.purchase_order import purchase_order_dao

    add_pos(db, s, 12)
    result = M.list_purchase_orders_recent_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 10
    # Then 2
    assert result == purchase_order_dao.list_recent_for_hub(db, workspace_id=s.W1.id, limit=10)


# [claude] POM-HUB-06
def test_pom_hub_06__pending_highlights(db, s):
    """POM-HUB-06 — pending highlights are the DAO's highlights.
    Rules: hub R1 (purchase_order_pending_highlights_for_hub)."""
    from app.dao.purchase_order import purchase_order_dao

    mk_po(db, s, "A")
    mk_po(db, s, "B", **confirmed(s))
    result = M.purchase_order_pending_highlights_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert result == purchase_order_dao.get_pending_highlights_for_hub(db, workspace_id=s.W1.id)


# =========================================================================== #
# delete_purchase_order
# =========================================================================== #


def audit_count(db):
    """Count of `workspace_audit_logs` rows (all workspaces)."""
    return db.scalar(select(func.count()).select_from(WorkspaceAuditLog))


# [claude] POM-DL-01
def test_pom_dl_01__goes_with_lines_approvers_events(db, s):
    """POM-DL-01 — an order with nothing received goes with its lines, approvers and events.
    Rules: delete_purchase_order R4."""
    o = mk_po(db, s, "1")
    l1 = mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    p = mk_appr(db, s, o, s.U2)
    e = mk_evt(db, s, o, T1)
    ok = mk_po(db, s, "2")
    lk = mk_line(db, ok, 1, s.I1)
    bok, blk = snap(db, ok), snap(db, lk)
    result = DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert gone(db, l1)
    assert gone(db, l2)
    # Then 3
    assert gone(db, p)
    assert gone(db, e)
    # Then 4
    assert snap(db, ok) == bok
    # Then 5
    assert snap(db, lk) == blk
    # Then 6
    assert result is None


# [claude] POM-DL-02
def test_pom_dl_02__missing_404(db, s):
    """POM-DL-02 — a missing order: 404.
    Rules: delete_purchase_order R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, MISSING)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-DL-03
def test_pom_dl_03__w0_404_kept(db, s):
    """POM-DL-03 — an order of W0: 404, kept.
    Rules: delete_purchase_order R1."""
    o0 = mk_po(db, s, "0", k="0")
    before = snap(db, o0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o0.id} not found"
    # Then 3
    assert snap(db, o0) == before


# [claude] POM-DL-04
def test_pom_dl_04__w2_404_kept(db, s):
    """POM-DL-04 — an order of W2: 404, kept.
    Rules: delete_purchase_order R1."""
    o9 = mk_po(db, s, "9", k="9")
    before = snap(db, o9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"
    # Then 3
    assert snap(db, o9) == before


# [claude] POM-DL-05
def test_pom_dl_05__receive_event_blocks(db, s):
    """POM-DL-05 — a receive event blocks the delete.
    Rules: delete_purchase_order R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1)
    mk_rev(db, o)
    before, bo = counts(db), snap(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot delete a purchase order with receiving history {DASH} void the order instead"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, o) == bo


# [claude] POM-DL-06
def test_pom_dl_06__foreign_receive_events_do_not_block(db, s):
    """POM-DL-06 — receive events filed under W0 or W2 do not block.
    Rules: delete_purchase_order R2."""
    o = mk_po(db, s, "1")
    mk_rev(db, o, workspace_id=s.W0.id)
    mk_rev(db, o, workspace_id=s.W2.id)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)


# [claude] POM-DL-07
def test_pom_dl_07__received_line_blocks(db, s):
    """POM-DL-07 — a line with something received blocks the delete.
    Rules: delete_purchase_order R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("0.01"))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot delete a purchase order with recorded receiving {DASH} void the order instead"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-DL-08
def test_pom_dl_08__receive_event_answers_first(db, s):
    """POM-DL-08 — a receive event and a received line: the receive event answers first.
    Rules: delete_purchase_order R2, R3."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1, quantity_received=Decimal("5.00"))
    mk_rev(db, o)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot delete a purchase order with receiving history {DASH} void the order instead"


# [claude] POM-DL-09
def test_pom_dl_09__negative_received_does_not_block(db, s):
    """POM-DL-09 — a negative received quantity does not block.
    Rules: delete_purchase_order R3, R4."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("-1.00"))
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert gone(db, line)


# [claude] POM-DL-10
def test_pom_dl_10__voided_nothing_received_deleted(db, s):
    """POM-DL-10 — a voided order with nothing received is deleted.
    Rules: delete_purchase_order R4."""
    o = mk_po(db, s, "1", **voided(s), supplier_confirmed=True)
    line = mk_line(db, o, 1, s.I1)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert gone(db, line)


# [claude] POM-DL-11
@xf(X2888)
def test_pom_dl_11__finalized_invoice_blocks(db, s):
    """POM-DL-11 — a finalized invoice blocks the delete.
    Rules: delete_purchase_order R3a [BUG-2888]."""
    v = mk_inv(db, s, "confirmed", "partial", paid_amount=Decimal("10.00"))
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1)
    before, bo, bv = counts(db), snap(db, o), snap(db, v)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot delete a purchase order with a finalized invoice {DASH} void the order instead"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert snap(db, o) == bo
    # Then 6
    assert snap(db, v) == bv


# [claude] POM-DL-12
def test_pom_dl_12__receive_event_before_finalized_invoice(db, s):
    """POM-DL-12 — a finalized invoice and a receive event: the receive event answers first.
    Rules: delete_purchase_order R2, R3a (order)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_rev(db, o)
    bv = snap(db, v)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot delete a purchase order with receiving history {DASH} void the order instead"
    # Then 3
    assert snap(db, v) == bv


# [claude] POM-DL-13
@xf(X2888)
def test_pom_dl_13__draft_invoice_deleted_with_order(db, s):
    """POM-DL-13 — a draft invoice is deleted with the order.
    Rules: delete_purchase_order R4a [BUG-2888]."""
    vd = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=vd.id, invoice_ever_linked=True)
    mk_line(db, o, 1, s.I1)
    vl = mk_invl(db, vd)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert gone(db, vd)
    # Then 3
    assert db.scalar(select(func.count()).select_from(InvoiceItem).where(InvoiceItem.invoice_id == vd.id)) == 0
    # Then 4
    assert gone(db, vl)


# [claude] POM-DL-14
def test_pom_dl_14__draft_linked_order_and_lines_go(db, s):
    """POM-DL-14 — with a draft invoice linked, the order and its lines go.
    Rules: delete_purchase_order R4, R4a."""
    vd = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", invoice_id=vd.id, invoice_ever_linked=True)
    line = mk_line(db, o, 1, s.I1)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert gone(db, line)


# [claude] POM-DL-15
def test_pom_dl_15__voided_invoice_stays(db, s):
    """POM-DL-15 — a voided invoice still linked stays as it is.
    Rules: delete_purchase_order R3a, R4."""
    vv = mk_inv(db, s, "voided", "unpaid")
    o = mk_po(db, s, "1", invoice_id=vv.id)
    bv = snap(db, vv)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert snap(db, vv) == bv


# [claude] POM-DL-16
def test_pom_dl_16__w2_confirmed_invoice_untouched(db, s):
    """POM-DL-16 — a confirmed invoice of W2 linked by mistake neither blocks nor is touched.
    Rules: delete_purchase_order R3a, R4."""
    v9 = mk_inv(db, s, "confirmed", "unpaid", k="9")
    o = mk_po(db, s, "1", invoice_id=v9.id)
    bv = snap(db, v9)
    DEL(db, s, o.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    assert snap(db, v9) == bv


# [claude] POM-DL-17
@xf(X1195)
def test_pom_dl_17__delete_writes_audit_row(db, s):
    """POM-DL-17 — a delete writes one workspace audit row.
    Rules: delete_purchase_order R5 [BUG-1195]."""
    o = mk_po(db, s, "1", total_amount=Decimal("25.00"), subtotal=Decimal("25.00"))
    fresh = reread(db, PurchaseOrder, o.id)
    number, created_at, o_id = fresh.po_number, fresh.created_at, fresh.id
    M.delete_purchase_order(db, po_id=o_id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 1
    assert gone(db, o)
    # Then 2
    rows = list(
        db.scalars(
            select(WorkspaceAuditLog).where(
                WorkspaceAuditLog.resource_type == "purchase_order", WorkspaceAuditLog.resource_id == o_id
            )
        )
    )
    assert len(rows) == 1
    # Then 3
    assert rows[0].workspace_id == s.W1.id
    assert rows[0].user_id == s.U2.id
    assert rows[0].action == "purchase_order_deleted"
    # Then 4
    assert rows[0].metadata_json == {
        "number": number, "total_amount": "25.00", "created_by": s.U1.id, "created_at": created_at.isoformat(),
    }


# [claude] POM-DL-18
@xf(X1195)
def test_pom_dl_18__refused_delete_no_audit(db, s):
    """POM-DL-18 — a refused delete writes no audit row.
    Rules: delete_purchase_order R5 [BUG-1195]."""
    o = mk_po(db, s, "1")
    mk_rev(db, o)
    before = audit_count(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_purchase_order(db, po_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert audit_count(db) == before


# [claude] POM-DL-19
@xf(X2872)
def test_pom_dl_19__order_read_for_update(db, s):
    """POM-DL-19 — the order row is read FOR UPDATE before the checks.
    Rules: delete_purchase_order R6 [BUG-2872]."""
    o = mk_po(db, s, "1")
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        DEL(db, s, o_id)
    # Then 1
    db.expire_all()
    assert db.get(PurchaseOrder, o_id) is None
    # Then 2
    assert rec.locks_first()


# [claude] POM-DL-20
def test_pom_dl_20__never_commits(db, s):
    """POM-DL-20 — never commits.
    Rules: delete_purchase_order (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: DEL(db, s, o.id))
    # Then 1
    assert n == 0


# [claude] POM-DL-21
@xf(X1195)
def test_pom_dl_21__without_user_id_type_error(db, s):
    """POM-DL-21 — a delete without user_id raises TypeError and deletes nothing.
    Rules: delete_purchase_order R5a [BUG-1195] (G13)."""
    o = mk_po(db, s, "1")
    before = audit_count(db)
    # Then 1
    with pytest.raises(TypeError):
        M.delete_purchase_order(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 2
    db.expire_all()
    assert db.get(PurchaseOrder, o.id) is not None
    # Then 3
    assert audit_count(db) == before


# =========================================================================== #
# _quantity_received_decimal, _validate_ordered_vs_received, _ensure_catalog_item_not_on_po
# =========================================================================== #


def line_count(db, o):
    """Count of O's `purchase_order_items` rows."""
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == o.id)
    )


# [claude] POM-QR-01
def test_pom_qr_01__none_received_is_zero():
    """POM-QR-01 — None received is 0.
    Rules: _quantity_received_decimal R1."""
    a = mem(quantity_received=None)
    result = M._quantity_received_decimal(a)
    # Then 1
    assert result == Decimal(0)


# [claude] POM-QR-02
def test_pom_qr_02__value_through_text():
    """POM-QR-02 — a value goes through its text.
    Rules: _quantity_received_decimal R1."""
    a = mem(quantity_received=Decimal("2.50"))
    result = M._quantity_received_decimal(a)
    # Then 1
    assert str(result) == "2.50"


# [claude] POM-VO-01
def test_pom_vo_01__below_whole_received():
    """POM-VO-01 — ordered below a whole received quantity: 400 with "7".
    Rules: _validate_ordered_vs_received R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ordered_vs_received(Decimal("6.99"), Decimal("7.00"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Ordered quantity cannot be less than received (7)"


# [claude] POM-VO-02
def test_pom_vo_02__fractional_received_normalized():
    """POM-VO-02 — a fractional received quantity is shown normalized.
    Rules: _validate_ordered_vs_received R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ordered_vs_received(Decimal("5"), Decimal("7.50"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Ordered quantity cannot be less than received (7.5)"


# [claude] POM-VO-03
def test_pom_vo_03__equal_passes():
    """POM-VO-03 — equal passes.
    Rules: _validate_ordered_vs_received R1."""
    result = M._validate_ordered_vs_received(Decimal("7"), Decimal("7.00"))
    # Then 1
    assert result is None


# [claude] POM-EC-01
def test_pom_ec_01__already_on_order_409(db, s):
    """POM-EC-01 — an item already on the order: 409 with its name.
    Rules: _ensure_catalog_item_not_on_po R1."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._ensure_catalog_item_not_on_po(db, po_id=o.id, item_id=s.I1.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Bolt is already on this purchase order"


# [claude] POM-EC-02
def test_pom_ec_02__excluded_line_not_counted(db, s):
    """POM-EC-02 — the excluded line does not count.
    Rules: _ensure_catalog_item_not_on_po R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    result = M._ensure_catalog_item_not_on_po(db, po_id=o.id, item_id=s.I1.id, workspace_id=s.W1.id, exclude_item_id=line.id)
    # Then 1
    assert result is None


# [claude] POM-EC-03
def test_pom_ec_03__other_order_not_counted(db, s):
    """POM-EC-03 — the same item on another order does not count.
    Rules: _ensure_catalog_item_not_on_po R1."""
    oa = mk_po(db, s, "1")
    o = mk_po(db, s, "2")
    oc = mk_po(db, s, "3")
    mk_line(db, oa, 1, s.I1)
    mk_line(db, oc, 1, s.I1)
    result = M._ensure_catalog_item_not_on_po(db, po_id=o.id, item_id=s.I1.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] POM-EC-04
def test_pom_ec_04__foreign_item_named_by_id(db, s):
    """POM-EC-04 — an item not of the workspace is named "Item #<id>".
    Rules: _ensure_catalog_item_not_on_po R1."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._ensure_catalog_item_not_on_po(db, po_id=o.id, item_id=s.I9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == f"Item #{s.I9.id} is already on this purchase order"


# =========================================================================== #
# add_item
# =========================================================================== #


def AI(db, s, po_id, user_id="U2", **fields):
    """The card call `M.add_item(db, po_id=..., data=IC(...), workspace_id=W1.id, user_id=U2.id)`
    (`user_id=None` when the card passes None)."""
    uid = s.U2.id if user_id == "U2" else user_id
    return M.add_item(db, po_id=po_id, data=IC(**fields), workspace_id=s.W1.id, user_id=uid)


# [claude] POM-AI-01
def test_pom_ai_01__new_line_after_highest(db, s):
    """POM-AI-01 — a new line after the highest number, totals and event.
    Rules: add_item R4, R5, R6, _recalc_totals R1."""
    o = mk_po(db, s, "1", subtotal=Decimal("40.00"), total_amount=Decimal("40.00"))
    mk_line(db, o, 1, s.I1)
    mk_line(db, o, 3, s.I3)
    result = AI(db, s, o.id, item_id=s.I2.id, quantity_ordered=Decimal("5"), unit_price=Decimal("2.50"))
    # Then 1
    assert result.id is not None
    assert result.line_number == 4
    # Then 2
    row = reread(db, PurchaseOrderItem, result.id)
    assert row.purchase_order_id == o.id
    assert row.item_id == s.I2.id
    assert row.quantity_ordered == Decimal("5.00")
    assert row.quantity_received == Decimal("0.00")
    assert row.unit_price == Decimal("2.50")
    assert row.line_subtotal == Decimal("12.50")
    # Then 3
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("52.50")
    assert po.total_amount == Decimal("52.50")
    # Then 4
    assert types(db, o) == ["item_added"]
    # Then 5
    ev = EV(db, o)
    assert ev[0].description == "Added Nut (line 4)"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert ev[0].metadata_json == {"item_id": s.I2.id, "item_name": "Nut", "line_number": 4, "quantity_ordered": "5", "unit_price": "2.5"}


# [claude] POM-AI-02
def test_pom_ai_02__empty_order_line_1_no_price_dash(db, s):
    """POM-AI-02 — an empty order gets line 1; no price shows a dash.
    Rules: add_item R4, R5."""
    o = mk_po(db, s, "1")
    result = AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("3"))
    # Then 1
    assert result.line_number == 1
    # Then 2
    row = reread(db, PurchaseOrderItem, result.id)
    assert row.unit_price is None
    assert row.line_subtotal is None
    # Then 3
    assert reread(db, PurchaseOrder, o.id).total_amount == Decimal("0.00")
    # Then 4
    assert EV(db, o)[0].metadata_json["unit_price"] == DASH


# [claude] POM-AI-03
def test_pom_ai_03__with_user_stage_synced(db, s):
    """POM-AI-03 — with a user the stage is synced.
    Rules: add_item R6."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    result = AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00"))
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SD1.id
    # Then 3
    assert types(db, o) == ["item_added", "status_updated"]


# [claude] POM-AI-04
def test_pom_ai_04__without_user_no_sync(db, s):
    """POM-AI-04 — without a user the stage is not synced.
    Rules: add_item R5, R6."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    result = AI(db, s, o.id, user_id=None, item_id=s.I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00"))
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 3
    assert types(db, o) == ["item_added"]
    # Then 4
    assert EV(db, o)[0].performed_by is None


# [claude] POM-AI-05
def test_pom_ai_05__missing_order_404(db, s):
    """POM-AI-05 — a missing order: 404.
    Rules: add_item R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, MISSING, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AI-06
def test_pom_ai_06__w2_order_404(db, s):
    """POM-AI-06 — an order of W2: 404.
    Rules: add_item R1."""
    o9 = mk_po(db, s, "9", k="9")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o9.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order not found"
    # Then 3
    assert counts(db) == before


# [claude] POM-AI-07
@xf(X2882)
def test_pom_ai_07__voided_refused(db, s):
    """POM-AI-07 — a voided order is refused.
    Rules: add_item R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AI-08
def test_pom_ai_08__items_confirmed_400(db, s):
    """POM-AI-08 — items confirmed: 400.
    Rules: add_item R2."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order items are confirmed"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AI-09
def test_pom_ai_09__locked_400(db, s):
    """POM-AI-09 — financially locked: 400 "Confirmed after invoice creation".
    Rules: add_item R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert counts(db) == before


# [claude] POM-AI-10
def test_pom_ai_10__item_already_on_order_409(db, s):
    """POM-AI-10 — the item is already on the order: 409.
    Rules: add_item R3."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Bolt is already on this purchase order"
    # Then 3
    assert line_count(db, o) == 1


# [claude] POM-AI-11
@xf(X1017)
def test_pom_ai_11__w2_item_refused(db, s):
    """POM-AI-11 — an item of W2 is refused.
    Rules: add_item R3 [BUG-1017]."""
    o = mk_po(db, s, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I9.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 3
    assert line_count(db, o) == 0


# [claude] POM-AI-12
@xf(X2872)
def test_pom_ai_12__order_read_for_update(db, s):
    """POM-AI-12 — the order row is read FOR UPDATE before the lock check.
    Rules: add_item R7 [BUG-2872]."""
    o = mk_po(db, s, "1")
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = AI(db, s, o_id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert rec.locks_first()


# [claude] POM-AI-13
def test_pom_ai_13__never_commits(db, s):
    """POM-AI-13 — never commits.
    Rules: add_item (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1")))
    # Then 1
    assert n == 0


# [claude] POM-AI-14
@xf(X1017)
def test_pom_ai_14__foreign_item_404_before_409(db, s):
    """POM-AI-14 — a foreign item that is also on the order: 404 before 409.
    Rules: add_item R3 [BUG-1017] (spec Overview check order, G4)."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I9.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 3
    assert line_count(db, o) == 1


# [claude] POM-AI-15
def test_pom_ai_15__section_guard_before_item(db, s):
    """POM-AI-15 — items confirmed and a foreign item: the section guard answers.
    Rules: add_item R2, R3 (spec Overview check order, G4)."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I9.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order items are confirmed"
    # Then 3
    assert counts(db) == before


# [claude] POM-AI-16
@xf(X2882)
def test_pom_ai_16__voided_before_guard(db, s):
    """POM-AI-16 — voided with items confirmed: the voided check answers first.
    Rules: add_item R1a [BUG-2882], R2 (spec Overview check order, G4)."""
    o = mk_po(db, s, "1", **voided(s), items_confirmed=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I1.id, quantity_ordered=Decimal("1"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert counts(db) == before


# [claude] POM-AI-17
def test_pom_ai_17__completed_order_400(db, s):
    """POM-AI-17 — a completed order: 400 "Confirmed after invoice creation".
    Rules: add_item R2, is_po_financially_locked R2; RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AI(db, s, o.id, item_id=s.I2.id, quantity_ordered=Decimal("1"), unit_price=Decimal("1.00"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert counts(db) == before


# =========================================================================== #
# update_item
# =========================================================================== #


def UI(db, s, item_id, user_id="U2", **fields):
    """The card call `M.update_item(db, item_id=..., data=PurchaseOrderItemUpdate(...), workspace_id=W1.id, user_id=U2.id)`."""
    uid = s.U2.id if user_id == "U2" else user_id
    return M.update_item(db, item_id=item_id, data=PurchaseOrderItemUpdate(**fields), workspace_id=s.W1.id, user_id=uid)


# [claude] POM-UI-01
def test_pom_ui_01__quantity_and_price_change(db, s):
    """POM-UI-01 — quantity and price change: subtotal, totals, one event.
    Rules: update_item R5, R6, R8, R9."""
    o = mk_po(db, s, "1", subtotal=Decimal("40.00"), total_amount=Decimal("40.00"))
    l1 = mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I2)
    result = UI(db, s, l1.id, quantity_ordered=Decimal("12"), unit_price=Decimal("2.50"))
    # Then 1
    assert result.id == l1.id
    # Then 2
    row = reread(db, PurchaseOrderItem, l1.id)
    assert row.quantity_ordered == Decimal("12.00")
    assert row.unit_price == Decimal("2.50")
    assert row.line_subtotal == Decimal("30.00")
    # Then 3
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("50.00")
    assert po.total_amount == Decimal("50.00")
    # Then 4
    assert types(db, o) == ["item_updated"]
    # Then 5
    ev = EV(db, o)
    assert ev[0].description == "Updated item: Bolt"
    assert ev[0].performed_by == s.U2.id
    # Then 6
    assert ev[0].metadata_json == {
        "changes": [
            {"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "12"},
            {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "2.5"},
        ],
        "item_id": s.I1.id,
        "item_name": "Bolt",
        "line_number": 1,
    }


# [claude] POM-UI-02
def test_pom_ui_02__only_price(db, s):
    """POM-UI-02 — only the price: subtotal from the stored quantity.
    Rules: update_item R5."""
    o = mk_po(db, s, "1", subtotal=Decimal("20.00"), total_amount=Decimal("20.00"))
    line = mk_line(db, o, 1, s.I1)
    result = UI(db, s, line.id, unit_price=Decimal("3.00"))
    # Then 1
    assert result.id == line.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.quantity_ordered == Decimal("10.00")
    assert row.line_subtotal == Decimal("30.00")
    # Then 3
    assert reread(db, PurchaseOrder, o.id).total_amount == Decimal("30.00")


# [claude] POM-UI-03
def test_pom_ui_03__only_notes(db, s):
    """POM-UI-03 — only the notes: subtotal untouched, "Notes" change logged.
    Rules: update_item R5, R8."""
    o = mk_po(db, s, "1", subtotal=Decimal("20.00"), total_amount=Decimal("20.00"))
    line = mk_line(db, o, 1, s.I1, line_subtotal=Decimal("20.00"))
    result = UI(db, s, line.id, notes="Zinc")
    # Then 1
    assert result.id == line.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.notes == "Zinc"
    assert row.line_subtotal == Decimal("20.00")
    # Then 3
    assert EV(db, o)[0].metadata_json["changes"] == [{"field": "notes", "label": "Notes", "from_value": DASH, "to_value": "Zinc"}]


# [claude] POM-UI-04
def test_pom_ui_04__same_values_no_event(db, s):
    """POM-UI-04 — the same values: no event.
    Rules: update_item R8."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    result = UI(db, s, line.id, quantity_ordered=Decimal("10"), unit_price=Decimal("2.00"))
    # Then 1
    assert result.id == line.id
    # Then 2
    assert EV(db, o) == []


# [claude] POM-UI-05
def test_pom_ui_05__without_user(db, s):
    """POM-UI-05 — without a user: no stage sync, event without performer.
    Rules: update_item R8, R9."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = UI(db, s, line.id, user_id=None, quantity_ordered=Decimal("11"))
    # Then 1
    assert result.id == line.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 3
    assert types(db, o) == ["item_updated"]
    # Then 4
    assert EV(db, o)[0].performed_by is None


# [claude] POM-UI-06
def test_pom_ui_06__with_user_stage_synced(db, s):
    """POM-UI-06 — with a user the stage is synced.
    Rules: update_item R9."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = UI(db, s, line.id, quantity_ordered=Decimal("11"))
    # Then 1
    assert result.id == line.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SD1.id
    # Then 3
    assert types(db, o) == ["item_updated", "status_updated"]


# [claude] POM-UI-07
def test_pom_ui_07__missing_line_404(db, s):
    """POM-UI-07 — a missing line: 404.
    Rules: update_item R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, MISSING, notes="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order item not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-UI-08
def test_pom_ui_08__w2_line_404(db, s):
    """POM-UI-08 — a line of W2: 404.
    Rules: update_item R1."""
    o9 = mk_po(db, s, "9", k="9")
    l9 = mk_line(db, o9, 1, s.I9)
    before = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, l9.id, notes="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order item not found"
    # Then 3
    assert snap(db, l9) == before


# [claude] POM-UI-09
@xf(X2882)
def test_pom_ui_09__voided_order_line_refused(db, s):
    """POM-UI-09 — a line of a voided order is refused.
    Rules: update_item R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, line.id, quantity_ordered=Decimal("12"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-UI-10
def test_pom_ui_10__items_confirmed_400(db, s):
    """POM-UI-10 — items confirmed: 400.
    Rules: update_item R2."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, line.id, quantity_ordered=Decimal("12"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order items are confirmed (receiving still allowed)"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-UI-11
def test_pom_ui_11__locked_400(db, s):
    """POM-UI-11 — financially locked: 400 "Confirmed after invoice creation (receiving still allowed)".
    Rules: update_item R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, line.id, notes="x")
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation (receiving still allowed)"
    # Then 3
    assert snap(db, line) == before


# [claude] POM-UI-12
def test_pom_ui_12__locked_empty_body_passes(db, s):
    """POM-UI-12 — locked with an empty body: passes and changes nothing.
    Rules: update_item R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    result = UI(db, s, line.id)
    # Then 1
    assert result.id == line.id
    # Then 2
    assert snap(db, line) == before
    # Then 3
    assert EV(db, o) == []


# [claude] POM-UI-13
def test_pom_ui_13__ordered_below_received_400(db, s):
    """POM-UI-13 — ordered below received: 400; equal passes.
    Rules: update_item R4, _validate_ordered_vs_received R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("6.00"))
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        UI(db, s, line.id, quantity_ordered=Decimal("5.99"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Ordered quantity cannot be less than received (6)"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-UI-14
def test_pom_ui_14__ordered_equal_received_passes(db, s):
    """POM-UI-14 — ordered equal to received passes.
    Rules: update_item R4."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("6.00"))
    result = UI(db, s, line.id, quantity_ordered=Decimal("6"))
    # Then 1
    assert result.id == line.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.quantity_ordered == Decimal("6.00")
    assert row.line_subtotal == Decimal("12.00")


# [claude] POM-UI-15
@xf(X2879)
def test_pom_ui_15__null_clears_price(db, s):
    """POM-UI-15 — an explicit null clears the price and the subtotal.
    Rules: update_item R1, R5 [BUG-2879]."""
    o = mk_po(db, s, "1", subtotal=Decimal("20.00"), total_amount=Decimal("20.00"))
    line = mk_line(db, o, 1, s.I1)
    result = UI(db, s, line.id, unit_price=None)
    # Then 1
    assert result.id == line.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.unit_price is None
    assert row.line_subtotal is None
    # Then 3
    assert reread(db, PurchaseOrder, o.id).total_amount == Decimal("0.00")


# [claude] POM-UI-16
@xf(X2879)
def test_pom_ui_16__null_clears_notes(db, s):
    """POM-UI-16 — an explicit null clears the notes.
    Rules: update_item R1 [BUG-2879]."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, notes="Zinc")
    result = UI(db, s, line.id, notes=None)
    # Then 1
    assert result.id == line.id
    # Then 2
    assert reread(db, PurchaseOrderItem, line.id).notes is None


# [claude] POM-UI-17
@xf(X2872)
def test_pom_ui_17__order_read_for_update(db, s):
    """POM-UI-17 — the order row is read FOR UPDATE before the checks.
    Rules: update_item R18 [BUG-2872]."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    line_id = line.id
    db.expunge_all()
    with recording(db) as rec:
        result = UI(db, s, line_id, quantity_ordered=Decimal("12"))
    # Then 1
    assert result.id == line_id
    # Then 2
    assert rec.locks_first()


# [claude] POM-UI-18
def test_pom_ui_18__never_commits(db, s):
    """POM-UI-18 — never commits.
    Rules: update_item (flush only)."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    n = commit_spy(db, lambda: UI(db, s, line.id, quantity_ordered=Decimal("12")))
    # Then 1
    assert n == 0


# =========================================================================== #
# remove_item
# =========================================================================== #


def RI(db, s, item_id, user_id="U2"):
    """The card call `M.remove_item(db, item_id=..., workspace_id=W1.id, user_id=U2.id)`."""
    uid = s.U2.id if user_id == "U2" else user_id
    return M.remove_item(db, item_id=item_id, workspace_id=s.W1.id, user_id=uid)


# [claude] POM-RI-01
def test_pom_ri_01__line_goes_gap_kept(db, s):
    """POM-RI-01 — the line goes, other numbers keep their gap, totals and event.
    Rules: remove_item R3."""
    o = mk_po(db, s, "1", subtotal=Decimal("60.00"), total_amount=Decimal("60.00"))
    mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    mk_line(db, o, 3, s.I3)
    result = RI(db, s, l2.id)
    # Then 1
    assert result.line_number == 2
    assert result.purchase_order_id == o.id
    # Then 2
    assert gone(db, l2)
    # Then 3
    assert [ln.line_number for ln in LINES(db, o)] == [1, 3]
    # Then 4
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("40.00")
    assert po.total_amount == Decimal("40.00")
    # Then 5
    assert types(db, o) == ["item_removed"]
    # Then 6
    ev = EV(db, o)
    assert ev[0].description == "Removed Nut (line 2)"
    # Then 7
    assert ev[0].metadata_json == {"item_id": s.I2.id, "item_name": "Nut", "line_number": 2}


# [claude] POM-RI-02
def test_pom_ri_02__with_user_stage_synced(db, s):
    """POM-RI-02 — with a user the stage is synced; without, not.
    Rules: remove_item R3."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = RI(db, s, line.id)
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SD1.id
    # Then 3
    assert types(db, o) == ["item_removed", "status_updated"]


# [claude] POM-RI-03
def test_pom_ri_03__without_user_no_sync(db, s):
    """POM-RI-03 — without a user the stage is not synced.
    Rules: remove_item R3."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = RI(db, s, line.id, user_id=None)
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 3
    assert types(db, o) == ["item_removed"]


# [claude] POM-RI-04
def test_pom_ri_04__missing_line_404(db, s):
    """POM-RI-04 — a missing line: 404.
    Rules: remove_item R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RI(db, s, MISSING)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order item not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-RI-05
def test_pom_ri_05__w2_line_404(db, s):
    """POM-RI-05 — a line of W2: 404.
    Rules: remove_item R1."""
    o9 = mk_po(db, s, "9", k="9")
    l9 = mk_line(db, o9, 1, s.I9)
    before = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RI(db, s, l9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order item not found"
    # Then 3
    assert snap(db, l9) == before


# [claude] POM-RI-06
@xf(X2882)
def test_pom_ri_06__voided_order_line_refused(db, s):
    """POM-RI-06 — a line of a voided order is refused.
    Rules: remove_item R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RI(db, s, line.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-RI-07
def test_pom_ri_07__items_confirmed_400(db, s):
    """POM-RI-07 — items confirmed: 400.
    Rules: remove_item R2."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RI(db, s, line.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order items are confirmed"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-RI-08
def test_pom_ri_08__locked_400(db, s):
    """POM-RI-08 — financially locked: 400.
    Rules: remove_item R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RI(db, s, line.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert snap(db, line) == before


# [claude] POM-RI-09
def test_pom_ri_09__received_line_not_checked(db, s):
    """POM-RI-09 — a received line is not checked here.
    Rules: remove_item R2 (Q8)."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("5.00"))
    result = RI(db, s, line.id)
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert gone(db, line)


# [claude] POM-RI-10
@xf(X2872)
def test_pom_ri_10__order_read_for_update(db, s):
    """POM-RI-10 — the order row is read FOR UPDATE before the lock check.
    Rules: remove_item R4 [BUG-2872]."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    line_id = line.id
    db.expunge_all()
    with recording(db) as rec:
        result = RI(db, s, line_id)
    # Then 1
    assert result.line_number == 1
    # Then 2
    assert rec.locks_first()


# [claude] POM-RI-11
def test_pom_ri_11__never_commits(db, s):
    """POM-RI-11 — never commits.
    Rules: remove_item (flush only)."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    n = commit_spy(db, lambda: RI(db, s, line.id))
    # Then 1
    assert n == 0


# =========================================================================== #
# sync_items
# =========================================================================== #

SU = PurchaseOrderItemSyncUpdate


def SY(db, s, po_id, data, user_id="U2"):
    """The card call `M.sync_items(db, po_id=..., data=SYNC(...), workspace_id=W1.id, user_id=U2.id)`."""
    uid = s.U2.id if user_id == "U2" else user_id
    return M.sync_items(db, po_id=po_id, data=data, workspace_id=s.W1.id, user_id=uid)


# [claude] POM-SY-01
def test_pom_sy_01__removals_updates_additions(db, s):
    """POM-SY-01 — removals, then updates, then additions, totals once.
    Rules: sync_items R3, R4, R5, R6, R8."""
    o = mk_po(db, s, "1", subtotal=Decimal("60.00"), total_amount=Decimal("60.00"))
    l1 = mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I2)
    l3 = mk_line(db, o, 3, s.I3)
    result = SY(
        db, s, o.id,
        SYNC(
            remove_ids=[l3.id],
            updates=[SU(id=l1.id, quantity_ordered=Decimal("5"), unit_price=Decimal("3.00"))],
            additions=[IC(item_id=s.I3.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00"))],
        ),
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    assert gone(db, l3)
    # Then 3
    row = reread(db, PurchaseOrderItem, l1.id)
    assert row.quantity_ordered == Decimal("5.00")
    assert row.unit_price == Decimal("3.00")
    assert row.line_subtotal == Decimal("15.00")
    # Then 4
    assert [(ln.line_number, ln.item_id) for ln in LINES(db, o)] == [(1, s.I1.id), (2, s.I2.id), (3, s.I3.id)]
    # Then 5
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("37.00")
    assert po.total_amount == Decimal("37.00")
    # Then 6
    assert types(db, o) == ["item_removed", "item_updated", "item_added"]
    # Then 7
    ev = EV(db, o)
    assert ev[0].description == "Removed Washer (line 3)"
    # Then 8
    assert ev[2].description == "Added Washer (line 3)"


# [claude] POM-SY-02
def test_pom_sy_02__missing_order_404(db, s):
    """POM-SY-02 — a missing order: 404.
    Rules: sync_items R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, MISSING, SYNC(remove_ids=[], updates=[], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order not found"
    # Then 3
    assert_session_clean(db)


# [claude] POM-SY-03
def test_pom_sy_03__w2_order_404(db, s):
    """POM-SY-03 — an order of W2: 404.
    Rules: sync_items R1."""
    o9 = mk_po(db, s, "9", k="9")
    l9 = mk_line(db, o9, 1, s.I9)
    before = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o9.id, SYNC(remove_ids=[l9.id], updates=[], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Purchase order not found"
    # Then 3
    assert snap(db, l9) == before


# [claude] POM-SY-04
@xf(X2882)
def test_pom_sy_04__voided_refused(db, s):
    """POM-SY-04 — a voided order is refused.
    Rules: sync_items R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[line.id], updates=[], additions=[]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-SY-05
def test_pom_sy_05__items_confirmed_400(db, s):
    """POM-SY-05 — items confirmed: 400.
    Rules: sync_items R2."""
    o = mk_po(db, s, "1", items_confirmed=True, **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[line.id], updates=[], additions=[]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Order items are confirmed"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, line) == before


# [claude] POM-SY-06
def test_pom_sy_06__locked_400(db, s):
    """POM-SY-06 — financially locked: 400.
    Rules: sync_items R2."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    mk_line(db, o, 1, s.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[], updates=[], additions=[IC(item_id=s.I2.id, quantity_ordered=Decimal("1"))]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirmed after invoice creation"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert line_count(db, o) == 1


# [claude] POM-SY-07
def test_pom_sy_07__remove_other_order_line_404(db, s):
    """POM-SY-07 — removing a line of another order: 404.
    Rules: sync_items R3."""
    oa = mk_po(db, s, "1")
    o = mk_po(db, s, "2")
    oc = mk_po(db, s, "3")
    mk_line(db, oa, 1, s.I1)
    mk_line(db, o, 1, s.I1)
    lc = mk_line(db, oc, 1, s.I1)
    before = snap(db, lc)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[lc.id], updates=[], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {lc.id} not found"
    # Then 3
    assert snap(db, lc) == before


# [claude] POM-SY-08
def test_pom_sy_08__remove_w2_line_404(db, s):
    """POM-SY-08 — removing a line of W2: 404.
    Rules: sync_items R3."""
    o = mk_po(db, s, "1")
    o9 = mk_po(db, s, "9", k="9")
    l9 = mk_line(db, o9, 1, s.I9)
    before = snap(db, l9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[l9.id], updates=[], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {l9.id} not found"
    # Then 3
    assert snap(db, l9) == before


# [claude] POM-SY-09
def test_pom_sy_09__removal_twice_404(db, s):
    """POM-SY-09 — a removal listed twice: 404 on the second.
    Rules: sync_items R3."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[line.id, line.id], updates=[], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {line.id} not found"


# [claude] POM-SY-10
def test_pom_sy_10__remove_received_line_400(db, s):
    """POM-SY-10 — removing a received line: 400 with its name.
    Rules: sync_items R3."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("0.01"))
    before = snap(db, line)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[line.id], updates=[], additions=[]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot remove Bolt {DASH} receiving has already been recorded"
    # Then 3
    assert snap(db, line) == before


# [claude] POM-SY-11
def test_pom_sy_11__update_removed_line_404(db, s):
    """POM-SY-11 — updating a line removed in the same call: 404.
    Rules: sync_items R4."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[l2.id], updates=[SU(id=l2.id, quantity_ordered=Decimal("4"))], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {l2.id} not found"


# [claude] POM-SY-12
def test_pom_sy_12__update_other_order_line_404(db, s):
    """POM-SY-12 — updating a line of another order: 404.
    Rules: sync_items R4."""
    o = mk_po(db, s, "1")
    oc = mk_po(db, s, "2")
    mk_line(db, o, 1, s.I1)
    lc = mk_line(db, oc, 1, s.I1)
    before = snap(db, lc)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[], updates=[SU(id=lc.id, quantity_ordered=Decimal("4"))], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {lc.id} not found"
    # Then 3
    assert snap(db, lc) == before


# [claude] POM-SY-13
def test_pom_sy_13__update_no_price_unpriced(db, s):
    """POM-SY-13 — an update with no price makes the line unpriced.
    Rules: sync_items R4."""
    o = mk_po(db, s, "1", subtotal=Decimal("20.00"), total_amount=Decimal("20.00"))
    line = mk_line(db, o, 1, s.I1)
    result = SY(db, s, o.id, SYNC(remove_ids=[], updates=[SU(id=line.id, quantity_ordered=Decimal("10"), unit_price=None)], additions=[]))
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.unit_price is None
    assert row.line_subtotal is None
    # Then 3
    assert reread(db, PurchaseOrder, o.id).total_amount == Decimal("0.00")


# [claude] POM-SY-14
def test_pom_sy_14__update_below_received_400(db, s):
    """POM-SY-14 — an update below the received quantity: 400.
    Rules: sync_items R4."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1, quantity_received=Decimal("7.50"))
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[], updates=[SU(id=line.id, quantity_ordered=Decimal("7"), unit_price=Decimal("2.00"))], additions=[]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Ordered quantity cannot be less than received (7.5)"


# [claude] POM-SY-15
def test_pom_sy_15__unchanged_update_logs_nothing(db, s):
    """POM-SY-15 — an unchanged update logs nothing.
    Rules: sync_items R5."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    result = SY(db, s, o.id, SYNC(remove_ids=[], updates=[SU(id=line.id, quantity_ordered=Decimal("10"), unit_price=Decimal("2.00"))], additions=[]))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert EV(db, o) == []


# [claude] POM-SY-16
def test_pom_sy_16__changed_update_without_user(db, s):
    """POM-SY-16 — a changed update without a user is written but not logged; no stage sync.
    Rules: sync_items R5, R8."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = SY(
        db, s, o.id,
        SYNC(remove_ids=[], updates=[SU(id=line.id, quantity_ordered=Decimal("4"), unit_price=Decimal("2.00"))], additions=[]),
        user_id=None,
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    row = reread(db, PurchaseOrderItem, line.id)
    assert row.quantity_ordered == Decimal("4.00")
    assert row.line_subtotal == Decimal("8.00")
    # Then 3
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SP1.id
    # Then 4
    assert EV(db, o) == []


# [claude] POM-SY-17
def test_pom_sy_17__with_user_stage_synced(db, s):
    """POM-SY-17 — with a user the stage is synced.
    Rules: sync_items R8."""
    o = mk_po(db, s, "1", **stage(s.SP1))
    line = mk_line(db, o, 1, s.I1)
    result = SY(db, s, o.id, SYNC(remove_ids=[], updates=[SU(id=line.id, quantity_ordered=Decimal("4"), unit_price=Decimal("2.00"))], additions=[]))
    # Then 1
    assert result.id == o.id
    # Then 2
    assert reread(db, PurchaseOrder, o.id).current_status_id == s.SD1.id
    # Then 3
    assert types(db, o) == ["item_updated", "status_updated"]


# [claude] POM-SY-18
def test_pom_sy_18__addition_of_kept_item_409(db, s):
    """POM-SY-18 — an addition of a kept line's item: 409.
    Rules: sync_items R6."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[], updates=[], additions=[IC(item_id=s.I1.id, quantity_ordered=Decimal("1"))]))
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Bolt is already on this purchase order"


# [claude] POM-SY-19
def test_pom_sy_19__two_additions_same_item_409(db, s):
    """POM-SY-19 — two additions of the same item: 409 on the second.
    Rules: sync_items R6."""
    o = mk_po(db, s, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(
            db, s, o.id,
            SYNC(
                remove_ids=[], updates=[],
                additions=[IC(item_id=s.I2.id, quantity_ordered=Decimal("1")), IC(item_id=s.I2.id, quantity_ordered=Decimal("2"))],
            ),
        )
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Nut is already on this purchase order"


# [claude] POM-SY-20
def test_pom_sy_20__addition_of_removed_item_allowed(db, s):
    """POM-SY-20 — an addition of a removed line's item is allowed.
    Rules: sync_items R6."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    result = SY(
        db, s, o.id,
        SYNC(remove_ids=[l2.id], updates=[], additions=[IC(item_id=s.I2.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00"))]),
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [(ln.line_number, ln.item_id, ln.quantity_ordered) for ln in LINES(db, o)] == [
        (1, s.I1.id, Decimal("10.00")),
        (2, s.I2.id, Decimal("3.00")),
    ]


# [claude] POM-SY-21
@xf(X1017)
def test_pom_sy_21__w2_addition_refused(db, s):
    """POM-SY-21 — an addition item of W2 is refused.
    Rules: sync_items R7 [BUG-1017]."""
    o = mk_po(db, s, "1")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[], updates=[], additions=[IC(item_id=s.I9.id, quantity_ordered=Decimal("1"))]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {s.I9.id} not found"
    # Then 3
    assert line_count(db, o) == 0


# [claude] POM-SY-22
def test_pom_sy_22__three_small_additions_total(db, s):
    """POM-SY-22 — three added lines of 1.25 x 0.10 total 0.39.
    Rules: sync_items R8, _recalc_totals R1, R1a (G15)."""
    o = mk_po(db, s, "1")
    result = SY(db, s, o.id, SYNC(remove_ids=[], updates=[], additions=_three_small_lines(s)))
    # Then 1
    assert result.id == o.id
    # Then 2
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("0.39")
    assert po.total_amount == Decimal("0.39")


# [claude] POM-SY-23
def test_pom_sy_23__refusal_after_removal_leaves_it_flushed(db, s):
    """POM-SY-23 — a refusal after a removal leaves the removal flushed for the caller to roll back.
    Rules: sync_items R8."""
    o = mk_po(db, s, "1")
    l1 = mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    before = snap(db, l1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SY(db, s, o.id, SYNC(remove_ids=[l2.id], updates=[SU(id=MISSING, quantity_ordered=Decimal("1"))], additions=[]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order item {MISSING} not found"
    # Then 3
    assert gone(db, l2)
    # Then 4
    assert snap(db, l1) == before


# [claude] POM-SY-24
@xf(X2872)
def test_pom_sy_24__order_read_for_update(db, s):
    """POM-SY-24 — the order row is read FOR UPDATE before the lock check.
    Rules: sync_items R9 [BUG-2872]."""
    o = mk_po(db, s, "1")
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = SY(db, s, o_id, SYNC(remove_ids=[], updates=[], additions=[IC(item_id=s.I1.id, quantity_ordered=Decimal("1"))]))
    # Then 1
    assert result.id == o_id
    # Then 2
    assert rec.locks_first()


# [claude] POM-SY-25
def test_pom_sy_25__never_commits(db, s):
    """POM-SY-25 — never commits.
    Rules: sync_items (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(
        db, lambda: SY(db, s, o.id, SYNC(remove_ids=[], updates=[], additions=[IC(item_id=s.I1.id, quantity_ordered=Decimal("1"))]))
    )
    # Then 1
    assert n == 0


# [claude] POM-SY-26
def test_pom_sy_26__events_carry_metadata(db, s):
    """POM-SY-26 — the removal, update and addition events carry their metadata.
    Rules: sync_items R3, R5, R6; remove_item R3, update_item R8, add_item R5."""
    o = mk_po(db, s, "1", subtotal=Decimal("60.00"), total_amount=Decimal("60.00"))
    l1 = mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I2)
    l3 = mk_line(db, o, 3, s.I3)
    result = SY(
        db, s, o.id,
        SYNC(
            remove_ids=[l3.id],
            updates=[SU(id=l1.id, quantity_ordered=Decimal("5"), unit_price=Decimal("3.00"))],
            additions=[IC(item_id=s.I3.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00"))],
        ),
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    assert types(db, o)[:3] == ["item_removed", "item_updated", "item_added"]
    # Then 3
    ev = EV(db, o)
    assert [e.performed_by for e in ev[:3]] == [s.U2.id, s.U2.id, s.U2.id]
    # Then 4
    assert ev[0].metadata_json == {"item_id": s.I3.id, "item_name": "Washer", "line_number": 3}
    # Then 5
    assert ev[1].description == "Updated item: Bolt"
    # Then 6
    assert ev[1].metadata_json == {
        "changes": [
            {"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "5"},
            {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "3"},
        ],
        "item_id": s.I1.id,
        "item_name": "Bolt",
        "line_number": 1,
    }
    # Then 7
    assert ev[2].metadata_json == {
        "item_id": s.I3.id, "item_name": "Washer", "line_number": 3, "quantity_ordered": "2", "unit_price": "1",
    }


# [claude] POM-SY-27
def test_pom_sy_27__additions_numbered_n_plus_1_and_2(db, s):
    """POM-SY-27 — two distinct additions are numbered n+1 and n+2 in the order sent.
    Rules: sync_items R6."""
    o = mk_po(db, s, "1", subtotal=Decimal("20.00"), total_amount=Decimal("20.00"))
    mk_line(db, o, 2, s.I2)
    result = SY(
        db, s, o.id,
        SYNC(
            remove_ids=[], updates=[],
            additions=[
                IC(item_id=s.I3.id, quantity_ordered=Decimal("1"), unit_price=Decimal("4.00")),
                IC(item_id=s.I1.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.50")),
            ],
        ),
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [(ln.line_number, ln.item_id) for ln in LINES(db, o)] == [(2, s.I2.id), (3, s.I3.id), (4, s.I1.id)]
    # Then 3
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("27.00")
    assert po.total_amount == Decimal("27.00")
    # Then 4
    ev = EV(db, o)
    assert [e.description for e in ev if e.event_type == "item_added"] == ["Added Washer (line 3)", "Added Bolt (line 4)"]
    # Then 5
    assert [e.metadata_json["line_number"] for e in ev if e.event_type == "item_added"] == [3, 4]


# [claude] POM-SY-28
def test_pom_sy_28__empty_order_starts_at_line_1(db, s):
    """POM-SY-28 — additions to an order with no lines start at line 1.
    Rules: sync_items R6, R8."""
    o = mk_po(db, s, "1")
    result = SY(
        db, s, o.id,
        SYNC(
            remove_ids=[], updates=[],
            additions=[
                IC(item_id=s.I1.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00")),
                IC(item_id=s.I2.id, quantity_ordered=Decimal("3"), unit_price=Decimal("2.00")),
            ],
        ),
    )
    # Then 1
    assert result.id == o.id
    # Then 2
    assert [(ln.line_number, ln.item_id) for ln in LINES(db, o)] == [(1, s.I1.id), (2, s.I2.id)]
    # Then 3
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("8.00")
    assert po.total_amount == Decimal("8.00")
    # Then 4
    assert [e.description for e in EV(db, o) if e.event_type == "item_added"] == ["Added Bolt (line 1)", "Added Nut (line 2)"]


# =========================================================================== #
# get_items, _recalc_totals
# =========================================================================== #


# [claude] POM-GT-01
def test_pom_gt_01__lines_by_line_number(db, s):
    """POM-GT-01 — the order's lines by line number.
    Rules: get_items R1."""
    o = mk_po(db, s, "1")
    oc = mk_po(db, s, "2")
    l3 = mk_line(db, o, 3, s.I3)
    l1 = mk_line(db, o, 1, s.I1)
    l2 = mk_line(db, o, 2, s.I2)
    mk_line(db, oc, 1, s.I1)
    result = M.get_items(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [l1.id, l2.id, l3.id]


# [claude] POM-GT-02
def test_pom_gt_02__no_lines_empty(db, s):
    """POM-GT-02 — an order with no lines: empty list.
    Rules: get_items R1."""
    o = mk_po(db, s, "1")
    result = M.get_items(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert list(result) == []


# [claude] POM-GT-03
@xf(X2886)
def test_pom_gt_03__missing_order_404(db, s):
    """POM-GT-03 — a missing order: 404.
    Rules: get_items R1 [BUG-2886]."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, po_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"


# [claude] POM-GT-04
@xf(X2886)
def test_pom_gt_04__w2_order_404(db, s):
    """POM-GT-04 — an order of W2: 404.
    Rules: get_items R1 [BUG-2886]."""
    o9 = mk_po(db, s, "9", k="9")
    mk_line(db, o9, 1, s.I9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, po_id=o9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"


# [claude] POM-GT-05
def test_pom_gt_05__w2_lines_never_listed(db, s):
    """POM-GT-05 — lines of W2 are never listed.
    Rules: get_items R1."""
    o = mk_po(db, s, "1")
    line = mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I9, workspace_id=s.W2.id)
    result = M.get_items(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert [ln.id for ln in result] == [line.id]


# [claude] POM-RT-01
def test_pom_rt_01__sum_of_priced_lines(db, s):
    """POM-RT-01 — totals are the sum of priced lines.
    Rules: _recalc_totals R1, R1a (G15)."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    mk_line(db, o, 2, s.I2, unit_price=None, line_subtotal=None)
    mk_line(db, o, 3, s.I3, line_subtotal=Decimal("5.00"), unit_price=Decimal("0.50"))
    result = M._recalc_totals(db, po=o)
    # Then 1
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("25.00")
    assert po.total_amount == Decimal("25.00")
    # Then 2
    assert result is None


# [claude] POM-RT-02
def test_pom_rt_02__no_lines_zero(db, s):
    """POM-RT-02 — no lines: 0.00.
    Rules: _recalc_totals R1."""
    o = mk_po(db, s, "1", subtotal=Decimal("9.00"), total_amount=Decimal("9.00"))
    M._recalc_totals(db, po=o)
    # Then 1
    po = reread(db, PurchaseOrder, o.id)
    assert po.subtotal == Decimal("0.00")
    assert po.total_amount == Decimal("0.00")


# [claude] POM-RT-03
def test_pom_rt_03__never_commits(db, s):
    """POM-RT-03 — never commits.
    Rules: _recalc_totals (flush only)."""
    o = mk_po(db, s, "1")
    mk_line(db, o, 1, s.I1)
    n = commit_spy(db, lambda: M._recalc_totals(db, po=o))
    # Then 1
    assert n == 0


# =========================================================================== #
# list_approvers
# =========================================================================== #


def order_part(statement):
    """The text of a statement after its first ORDER BY ("" if none)."""
    flat = " ".join(statement.split())
    return flat.split(" ORDER BY ", 1)[1] if " ORDER BY " in flat else ""


# [claude] POM-LA-01
def test_pom_la_01__triples_by_assigned_at(db, s):
    """POM-LA-01 — triples by assigned_at, positions from the workspace membership.
    Rules: list_approvers R2."""
    o = mk_po(db, s, "1")
    p2 = mk_appr(db, s, o, s.U2, assigned_at=T3)
    p1 = mk_appr(db, s, o, s.U1, assigned_at=T2)
    p3 = mk_appr(db, s, o, s.U3, assigned_at=T1)
    result = M.list_approvers(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert [(a.id, p.id, pos) for (a, p, pos) in result] == [
        (p3.id, s.U3.id, None),
        (p1.id, s.U1.id, "Buyer"),
        (p2.id, s.U2.id, None),
    ]


# [claude] POM-LA-02
def test_pom_la_02__missing_order_404(db, s):
    """POM-LA-02 — a missing order: 404.
    Rules: list_approvers R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, po_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"


# [claude] POM-LA-03
def test_pom_la_03__w2_order_404(db, s):
    """POM-LA-03 — an order of W2: 404.
    Rules: list_approvers R1."""
    o9 = mk_po(db, s, "9", k="9")
    mk_appr(db, s, o9, s.U3)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, po_id=o9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"


# [claude] POM-LA-04
@xf(X1200)
def test_pom_la_04__tied_assigned_at_ordered_by_id(db, s):
    """POM-LA-04 — tied assigned_at: the approvers query orders by id too.
    Rules: list_approvers R2 [BUG-1200]."""
    o = mk_po(db, s, "1")
    p1 = mk_appr(db, s, o, s.U1)
    p2 = mk_appr(db, s, o, s.U2)
    o_id, p1_id, p2_id = o.id, p1.id, p2.id
    db.expunge_all()
    with recording(db) as rec:
        result = M.list_approvers(db, po_id=o_id, workspace_id=s.W1.id)
    # Then 1
    assert {a.id for (a, p, pos) in result} == {p1_id, p2_id}
    # Then 2
    assert "purchase_order_approvers.id" in order_part(rec.sel("purchase_order_approvers")[0])


# [claude] POM-LA-05
@xf(X2883)
def test_pom_la_05__fixed_number_of_reads(db, s):
    """POM-LA-05 — reads are a fixed number, not two per approver.
    Rules: list_approvers R3 [BUG-2883]."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U1, assigned_at=T1)
    mk_appr(db, s, o, s.U2, assigned_at=T2)
    mk_appr(db, s, o, s.U4, assigned_at=T3)
    mk_appr(db, s, o, s.U5, assigned_at=T4)
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = M.list_approvers(db, po_id=o_id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 4
    # Then 2
    assert len(rec.selects) <= 4


# =========================================================================== #
# approval_summary
# =========================================================================== #


# [claude] POM-AS-01
def test_pom_as_01__threshold_2_one_approval(db, s):
    """POM-AS-01 — a threshold of 2 with one approval is not met.
    Rules: approval_summary R1, R2."""
    o = mk_po(db, s, "1", required_approvals=2)
    mk_appr(db, s, o, s.U1, **APPROVED)
    mk_appr(db, s, o, s.U2)
    mk_appr(db, s, o, s.U4)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (1, 2, False)


# [claude] POM-AS-02
def test_pom_as_02__threshold_2_two_approvals(db, s):
    """POM-AS-02 — a threshold of 2 with two approvals is met.
    Rules: approval_summary R1, R2."""
    o = mk_po(db, s, "1", required_approvals=2)
    mk_appr(db, s, o, s.U1, **APPROVED)
    mk_appr(db, s, o, s.U2, **APPROVED)
    mk_appr(db, s, o, s.U4)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (2, 2, True)


# [claude] POM-AS-03
def test_pom_as_03__threshold_0_met(db, s):
    """POM-AS-03 — a threshold of 0 is met with nobody.
    Rules: approval_summary R2."""
    o = mk_po(db, s, "1", required_approvals=0)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (0, 0, True)


# [claude] POM-AS-04
def test_pom_as_04__no_threshold_every_approver(db, s):
    """POM-AS-04 — no threshold: every approver is needed.
    Rules: approval_summary R3."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U1, **APPROVED)
    mk_appr(db, s, o, s.U2, **APPROVED)
    mk_appr(db, s, o, s.U4)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (2, 3, False)


# [claude] POM-AS-05
def test_pom_as_05__no_threshold_all_approved(db, s):
    """POM-AS-05 — no threshold, all approved: met.
    Rules: approval_summary R3."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U1, **APPROVED)
    mk_appr(db, s, o, s.U2, **APPROVED)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (2, 2, True)


# [claude] POM-AS-06
@xf(X1202)
def test_pom_as_06__no_threshold_no_approvers_not_met(db, s):
    """POM-AS-06 — no threshold and no approvers is not met.
    Rules: approval_summary R3 [BUG-1202]."""
    o = mk_po(db, s, "1")
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (0, 1, False)


# [claude] POM-AS-07
def test_pom_as_07__one_approver_no_threshold(db, s):
    """POM-AS-07 — no threshold and exactly one approver: one is needed.
    Rules: approval_summary R3."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U2)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (0, 1, False)


# [claude] POM-AS-08
def test_pom_as_08__threshold_0_with_approvers_met(db, s):
    """POM-AS-08 — a threshold of 0 with unapproved approvers is met.
    Rules: approval_summary R2 ("0 included")."""
    o = mk_po(db, s, "1", required_approvals=0)
    mk_appr(db, s, o, s.U1)
    mk_appr(db, s, o, s.U2)
    result = M.approval_summary(db, po=o)
    # Then 1
    assert result == (0, 0, True)


# =========================================================================== #
# add_approver
# =========================================================================== #


def AA(db, s, po_id, user):
    """The card call `M.add_approver(db, po_id=..., user_id=..., workspace_id=W1.id, assigned_by=U1.id)`."""
    return M.add_approver(db, po_id=po_id, user_id=user.id, workspace_id=s.W1.id, assigned_by=s.U1.id)


# [claude] POM-AA-01
def test_pom_aa_01__active_member_added(db, s):
    """POM-AA-01 — an active member becomes an approver.
    Rules: add_approver R4, R5."""
    o = mk_po(db, s, "1")
    result = AA(db, s, o.id, s.U2)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrderApprover, result.id)
    assert row.purchase_order_id == o.id
    assert row.user_id == s.U2.id
    assert row.assigned_by == s.U1.id
    assert row.approved is False
    assert row.approved_at is None
    assert row.workspace_id == s.W1.id
    # Then 3
    assert types(db, o) == ["approver_added"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Added Bob Karim as approver"
    assert ev[0].performed_by == s.U1.id
    # Then 5
    assert ev[0].metadata_json == {"user_id": s.U2.id, "user_name": "Bob Karim"}


# [claude] POM-AA-02
def test_pom_aa_02__missing_order_404(db, s):
    """POM-AA-02 — a missing order: 404.
    Rules: add_approver R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, MISSING, s.U2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AA-03
def test_pom_aa_03__w2_order_404(db, s):
    """POM-AA-03 — an order of W2: 404.
    Rules: add_approver R1."""
    o9 = mk_po(db, s, "9", k="9")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o9.id, s.U2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-04
def test_pom_aa_04__invited_member_refused(db, s):
    """POM-AA-04 — an invited member is refused.
    Rules: add_approver R2."""
    o = mk_po(db, s, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U4)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AA-05
def test_pom_aa_05__inactive_member_refused(db, s):
    """POM-AA-05 — an inactive member is refused.
    Rules: add_approver R2."""
    o = mk_po(db, s, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U5)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-06
def test_pom_aa_06__w2_only_member_refused(db, s):
    """POM-AA-06 — an active member of W2 only is refused.
    Rules: add_approver R2."""
    o = mk_po(db, s, "1")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U3)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-07
def test_pom_aa_07__w0_only_member_refused(db, s):
    """POM-AA-07 — an active member of W0 only is refused.
    Rules: add_approver R2."""
    o = mk_po(db, s, "1")
    u6 = make_profile(db, name="Farid Hasan")
    _add(db, WorkspaceMember(workspace_id=s.W0.id, user_id=u6.id, role="member", status="active"))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, u6)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-08
@xf(X2882)
def test_pom_aa_08__voided_refused(db, s):
    """POM-AA-08 — a voided order is refused.
    Rules: add_approver R2a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AA-09
def test_pom_aa_09__already_approver_409(db, s):
    """POM-AA-09 — already an approver: 409.
    Rules: add_approver R3."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U2)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U2)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "User is already an approver for this order"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-10
def test_pom_aa_10__approver_of_other_order_allowed(db, s):
    """POM-AA-10 — an approver of another order may be added to this one.
    Rules: add_approver R3."""
    oa = mk_po(db, s, "1")
    o = mk_po(db, s, "2")
    mk_appr(db, s, oa, s.U2)
    result = AA(db, s, o.id, s.U2)
    # Then 1
    assert result.purchase_order_id == o.id
    assert result.user_id == s.U2.id


# [claude] POM-AA-11
@xf(X2881)
def test_pom_aa_11__completed_refuses(db, s):
    """POM-AA-11 — a completed order refuses new approvers.
    Rules: add_approver R6 [BUG-2881], RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot change approvers {DASH} order is complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-AA-12
@xf(X2881)
def test_pom_aa_12__finalized_invoice_refuses(db, s):
    """POM-AA-12 — a finalized invoice refuses new approvers.
    Rules: add_approver R6 [BUG-2881]."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        AA(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot change approvers {DASH} invoice is finalized"
    # Then 3
    assert counts(db) == before


# [claude] POM-AA-13
def test_pom_aa_13__draft_invoice_does_not_block(db, s):
    """POM-AA-13 — a draft invoice does not block new approvers.
    Rules: add_approver R4, R6."""
    vd = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", **confirmed(s), invoice_id=vd.id)
    result = AA(db, s, o.id, s.U2)
    # Then 1
    assert result.user_id == s.U2.id


# [claude] POM-AA-14
def test_pom_aa_14__never_commits(db, s):
    """POM-AA-14 — never commits.
    Rules: add_approver (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: AA(db, s, o.id, s.U2))
    # Then 1
    assert n == 0


# [claude] POM-AA-15
@xf(X2872)
def test_pom_aa_15__order_read_for_update(db, s):
    """POM-AA-15 — the order row is read FOR UPDATE before the state checks.
    Rules: add_approver R7 [BUG-2872] (G14)."""
    o = mk_po(db, s, "1")
    o_id, u2 = o.id, SimpleNamespace(id=s.U2.id)
    db.expunge_all()
    with recording(db) as rec:
        result = AA(db, s, o_id, u2)
    # Then 1
    assert result.user_id == u2.id
    # Then 2
    assert rec.locks_first()


# =========================================================================== #
# remove_approver
# =========================================================================== #


def RM_(db, s, po_id, user, performed_by="U1"):
    """The card call `M.remove_approver(db, po_id=..., user_id=..., workspace_id=W1.id, performed_by=U1.id)`
    (`performed_by` left out when the card leaves it out)."""
    kwargs = {"po_id": po_id, "user_id": user.id, "workspace_id": s.W1.id}
    if performed_by == "U1":
        kwargs["performed_by"] = s.U1.id
    return M.remove_approver(db, **kwargs)


# [claude] POM-RM-01
def test_pom_rm_01__approved_approver_removed(db, s):
    """POM-RM-01 — an approved approver is removed and logged.
    Rules: remove_approver R2, R3."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    pk = mk_appr(db, s, o, s.U1)
    bk = snap(db, pk)
    result = RM_(db, s, o.id, s.U2)
    # Then 1
    assert gone(db, p)
    # Then 2
    assert snap(db, pk) == bk
    # Then 3
    assert types(db, o) == ["approver_removed"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Removed Bob Karim as approver"
    assert ev[0].performed_by == s.U1.id
    # Then 5
    assert ev[0].metadata_json == {"user_id": s.U2.id, "user_name": "Bob Karim"}
    # Then 6
    assert result is None


# [claude] POM-RM-02
def test_pom_rm_02__creator_removed_no_performer(db, s):
    """POM-RM-02 — the creator can be removed; no performer.
    Rules: remove_approver R2, R3."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U1)
    RM_(db, s, o.id, s.U1, performed_by=None)
    # Then 1
    assert gone(db, p)
    # Then 2
    assert EV(db, o)[0].performed_by is None


# [claude] POM-RM-03
def test_pom_rm_03__not_an_approver_404(db, s):
    """POM-RM-03 — not an approver of the order: 404.
    Rules: remove_approver R1."""
    o = mk_po(db, s, "1")
    oc = mk_po(db, s, "2")
    pc = mk_appr(db, s, oc, s.U2)
    before = snap(db, pc)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, o.id, s.U2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, pc) == before


# [claude] POM-RM-04
def test_pom_rm_04__missing_order_404(db, s):
    """POM-RM-04 — a missing order: 404 "Approver not found".
    Rules: remove_approver R1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, MISSING, s.U2)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    assert counts(db) == before


# [claude] POM-RM-05
def test_pom_rm_05__w2_order_approver_404(db, s):
    """POM-RM-05 — an approver of a W2 order: 404.
    Rules: remove_approver R1."""
    o9 = mk_po(db, s, "9", k="9")
    p9 = mk_appr(db, s, o9, s.U3)
    before = snap(db, p9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, o9.id, s.U3)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    assert snap(db, p9) == before


# [claude] POM-RM-06
@xf(X2882)
def test_pom_rm_06__voided_refused(db, s):
    """POM-RM-06 — a voided order is refused.
    Rules: remove_approver R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    p = mk_appr(db, s, o, s.U2)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-RM-07
@xf(X2881)
def test_pom_rm_07__completed_refuses(db, s):
    """POM-RM-07 — a completed order refuses removing approvers.
    Rules: remove_approver R4 [BUG-2881], RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot change approvers {DASH} order is complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-RM-08
@xf(X2881)
def test_pom_rm_08__finalized_invoice_refuses(db, s):
    """POM-RM-08 — a finalized invoice refuses removing approvers.
    Rules: remove_approver R4 [BUG-2881]."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        RM_(db, s, o.id, s.U2)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot change approvers {DASH} invoice is finalized"
    # Then 3
    assert snap(db, p) == before


# [claude] POM-RM-09
def test_pom_rm_09__never_commits(db, s):
    """POM-RM-09 — never commits.
    Rules: remove_approver (flush only)."""
    o = mk_po(db, s, "1")
    mk_appr(db, s, o, s.U2)
    n = commit_spy(db, lambda: RM_(db, s, o.id, s.U2))
    # Then 1
    assert n == 0


# [claude] POM-RM-10
@xf(X2872)
def test_pom_rm_10__order_read_for_update(db, s):
    """POM-RM-10 — the order row is read FOR UPDATE before the state checks.
    Rules: remove_approver R5 [BUG-2872] (G14)."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2)
    o_id, p_id, u2 = o.id, p.id, SimpleNamespace(id=s.U2.id)
    db.expunge_all()
    with recording(db) as rec:
        RM_(db, s, o_id, u2)
    # Then 1
    db.expire_all()
    assert db.get(PurchaseOrderApprover, p_id) is None
    # Then 2
    assert rec.locks_first()


# =========================================================================== #
# set_approval
# =========================================================================== #


def SA(db, s, po_id, user, approved):
    """The card call `M.set_approval(db, po_id=..., user_id=..., workspace_id=W1.id, approved=...)`."""
    return M.set_approval(db, po_id=po_id, user_id=user.id, workspace_id=s.W1.id, approved=approved)


# [claude] POM-SA-01
def test_pom_sa_01__approving_stamped_now(db, s):
    """POM-SA-01 — approving: stamped now, event, row returned.
    Rules: set_approval R5."""
    o = mk_po(db, s, "1", **confirmed(s))
    p = mk_appr(db, s, o, s.U2)
    with clock():
        result = SA(db, s, o.id, s.U2, True)
    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, PurchaseOrderApprover, p.id)
    assert row.approved is True
    assert row.approved_at == NOW
    # Then 3
    assert types(db, o) == ["approved"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Approved order"
    assert ev[0].performed_by == s.U2.id


# [claude] POM-SA-02
def test_pom_sa_02__withdrawing_cleared(db, s):
    """POM-SA-02 — withdrawing: cleared, event.
    Rules: set_approval R5."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    result = SA(db, s, o.id, s.U2, False)
    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, PurchaseOrderApprover, p.id)
    assert row.approved is False
    assert row.approved_at is None
    # Then 3
    assert types(db, o) == ["approval_withdrawn"]
    # Then 4
    ev = EV(db, o)
    assert ev[0].description == "Withdrew approval"
    assert ev[0].performed_by == s.U2.id


# [claude] POM-SA-03
def test_pom_sa_03__not_an_approver_403(db, s):
    """POM-SA-03 — not an approver of the order: 403.
    Rules: set_approval R1."""
    o = mk_po(db, s, "1", **confirmed(s))
    oc = mk_po(db, s, "2", **confirmed(s))
    pc = mk_appr(db, s, oc, s.U2)
    before = snap(db, pc)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o.id, s.U2, True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, pc) == before


# [claude] POM-SA-04
def test_pom_sa_04__w2_order_approver_403(db, s):
    """POM-SA-04 — an approver row of a W2 order: 403.
    Rules: set_approval R1."""
    o9 = mk_po(db, s, "9", k="9", supplier_confirmed=True, details_confirmed=True, items_confirmed=True)
    p9 = mk_appr(db, s, o9, s.U3)
    before = snap(db, p9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o9.id, s.U3, True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 3
    assert snap(db, p9) == before


# [claude] POM-SA-05
@xf(X2882)
def test_pom_sa_05__voided_refused(db, s):
    """POM-SA-05 — a voided order is refused.
    Rules: set_approval R1a [BUG-2882]."""
    o = mk_po(db, s, "1", **voided(s))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o.id, s.U2, False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Purchase order is voided"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-SA-06
def test_pom_sa_06__approving_before_sections_400(db, s):
    """POM-SA-06 — approving before the three sections are confirmed: 400.
    Rules: set_approval R2."""
    o = mk_po(db, s, "1", supplier_confirmed=True, details_confirmed=True, **stage(s.SP1))
    p = mk_appr(db, s, o, s.U2)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o.id, s.U2, True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Confirm supplier, order details, and items before approving"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-SA-07
def test_pom_sa_07__withdraw_completed_400(db, s):
    """POM-SA-07 — withdrawing on a completed order: 400.
    Rules: set_approval R3, RP5 (PO)."""
    v = mk_inv(db, s, "confirmed", "paid")
    o = mk_po(db, s, "1", **complete_by(s, v))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o.id, s.U2, False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot withdraw approval {DASH} order is complete"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-SA-08
@xf(X2881)
def test_pom_sa_08__withdraw_finalized_invoice_400(db, s):
    """POM-SA-08 — withdrawing after the invoice is finalized: 400.
    Rules: set_approval R4 [BUG-2881]."""
    v = mk_inv(db, s, "confirmed", "unpaid")
    o = mk_po(db, s, "1", **locked_by(s, v))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    before = snap(db, p)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        SA(db, s, o.id, s.U2, False)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == f"Cannot withdraw approval {DASH} invoice is finalized"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert snap(db, p) == before


# [claude] POM-SA-09
def test_pom_sa_09__withdraw_with_draft_allowed(db, s):
    """POM-SA-09 — withdrawing with a draft invoice is allowed.
    Rules: set_approval R4, R5."""
    vd = mk_inv(db, s, "draft", "unpaid")
    o = mk_po(db, s, "1", **confirmed(s), invoice_id=vd.id)
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    result = SA(db, s, o.id, s.U2, False)
    # Then 1
    assert result.id == p.id
    # Then 2
    assert reread(db, PurchaseOrderApprover, p.id).approved is False


# [claude] POM-SA-10
@xf(X2880)
def test_pom_sa_10__approving_twice_keeps_stamp(db, s):
    """POM-SA-10 — approving twice keeps the first stamp and logs nothing.
    Rules: set_approval R6 [BUG-2880]."""
    o = mk_po(db, s, "1", **confirmed(s))
    p = mk_appr(db, s, o, s.U2, **APPROVED)
    with clock():
        result = SA(db, s, o.id, s.U2, True)
    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, PurchaseOrderApprover, p.id)
    assert row.approved is True
    # Then 3
    assert row.approved_at == T2
    # Then 4
    assert EV(db, o) == []


# [claude] POM-SA-11
@xf(X2880)
def test_pom_sa_11__withdraw_when_not_approved_logs_nothing(db, s):
    """POM-SA-11 — withdrawing when not approved logs nothing.
    Rules: set_approval R6 [BUG-2880]."""
    o = mk_po(db, s, "1")
    p = mk_appr(db, s, o, s.U2)
    result = SA(db, s, o.id, s.U2, False)
    # Then 1
    assert result.id == p.id
    # Then 2
    row = reread(db, PurchaseOrderApprover, p.id)
    assert row.approved is False
    assert row.approved_at is None
    # Then 3
    assert EV(db, o) == []


# [claude] POM-SA-12
@xf(X2872)
def test_pom_sa_12__order_read_for_update(db, s):
    """POM-SA-12 — the order row is read FOR UPDATE before the checks.
    Rules: set_approval R7 [BUG-2872]."""
    o = mk_po(db, s, "1", **confirmed(s))
    p = mk_appr(db, s, o, s.U2)
    o_id, p_id, u2 = o.id, p.id, SimpleNamespace(id=s.U2.id)
    db.expunge_all()
    with recording(db) as rec:
        result = SA(db, s, o_id, u2, True)
    # Then 1
    assert result.id == p_id
    # Then 2
    assert rec.locks_first()


# [claude] POM-SA-13
def test_pom_sa_13__never_commits(db, s):
    """POM-SA-13 — never commits.
    Rules: set_approval (flush only)."""
    o = mk_po(db, s, "1", **confirmed(s))
    mk_appr(db, s, o, s.U2)
    n = commit_spy(db, lambda: SA(db, s, o.id, s.U2, True))
    # Then 1
    assert n == 0


# =========================================================================== #
# log_event
# =========================================================================== #


# [claude] POM-LE-01
def test_pom_le_01__one_event_given_values(db, s):
    """POM-LE-01 — one event with the given values.
    Rules: log_event R1."""
    o = mk_po(db, s, "1")
    result = M.log_event(
        db, po_id=o.id, workspace_id=s.W1.id, event_type="attachment_added", description="Added drawing.pdf",
        performed_by=s.U2.id, metadata={"file": "drawing.pdf"},
    )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrderEvent, result.id)
    assert row.purchase_order_id == o.id
    assert row.workspace_id == s.W1.id
    assert row.event_type == "attachment_added"
    assert row.description == "Added drawing.pdf"
    assert row.performed_by == s.U2.id
    # Then 3
    assert row.metadata_json == {"file": "drawing.pdf"}


# [claude] POM-LE-02
def test_pom_le_02__no_performer_no_metadata(db, s):
    """POM-LE-02 — no performer and no metadata.
    Rules: log_event R1."""
    o = mk_po(db, s, "1")
    result = M.log_event(db, po_id=o.id, workspace_id=s.W1.id, event_type="note", description="x")
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, PurchaseOrderEvent, result.id)
    assert row.performed_by is None
    assert row.metadata_json is None


# [claude] POM-LE-03
@xf(X1192)
def test_pom_le_03__w2_order_refused(db, s):
    """POM-LE-03 — an order of W2 is refused.
    Rules: log_event R2 [BUG-1192]."""
    o9 = mk_po(db, s, "9", k="9")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, po_id=o9.id, workspace_id=s.W1.id, event_type="note", description="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"
    # Then 3
    assert_session_clean(db)
    # Then 4
    assert counts(db) == before


# [claude] POM-LE-04
@xf(X1192)
def test_pom_le_04__w0_order_refused(db, s):
    """POM-LE-04 — an order of W0 is refused.
    Rules: log_event R2 [BUG-1192]."""
    o0 = mk_po(db, s, "0", k="0")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, po_id=o0.id, workspace_id=s.W1.id, event_type="note", description="x")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o0.id} not found"
    # Then 3
    assert counts(db) == before


# [claude] POM-LE-05
def test_pom_le_05__never_commits(db, s):
    """POM-LE-05 — never commits.
    Rules: log_event (flush only)."""
    o = mk_po(db, s, "1")
    n = commit_spy(db, lambda: M.log_event(db, po_id=o.id, workspace_id=s.W1.id, event_type="note", description="x"))
    # Then 1
    assert n == 0


# =========================================================================== #
# list_events
# =========================================================================== #


# [claude] POM-LV-01
def test_pom_lv_01__newest_first_ties_by_id_desc(db, s):
    """POM-LV-01 — newest first, ties by id descending, profile or None.
    Rules: list_events R2."""
    o = mk_po(db, s, "1")
    oc = mk_po(db, s, "2")
    ea = mk_evt(db, s, o, T3)
    eb = mk_evt(db, s, o, T1)
    ec = mk_evt(db, s, o, T3, performed_by=None)
    ed = mk_evt(db, s, o, T2, performed_by=s.U2.id)
    mk_evt(db, s, oc, T4)
    result = M.list_events(db, po_id=o.id, workspace_id=s.W1.id)
    # Then 1
    assert [e.id for (e, p) in result] == [ec.id, ea.id, ed.id, eb.id]
    # Then 2
    assert [p.id if p else None for (e, p) in result] == [None, s.U1.id, s.U2.id, s.U1.id]


# [claude] POM-LV-02
def test_pom_lv_02__missing_order_404(db, s):
    """POM-LV-02 — a missing order: 404.
    Rules: list_events R1."""
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, po_id=MISSING, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {MISSING} not found"


# [claude] POM-LV-03
def test_pom_lv_03__w2_order_404(db, s):
    """POM-LV-03 — an order of W2: 404.
    Rules: list_events R1."""
    o9 = mk_po(db, s, "9", k="9")
    mk_evt(db, s, o9, T1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, po_id=o9.id, workspace_id=s.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Purchase order with ID {o9.id} not found"


# [claude] POM-LV-04
@xf(X2883)
def test_pom_lv_04__fixed_number_of_reads(db, s):
    """POM-LV-04 — reads are a fixed number, not one per event.
    Rules: list_events R2 [BUG-2883]."""
    o = mk_po(db, s, "1")
    mk_evt(db, s, o, T1)
    mk_evt(db, s, o, T2, performed_by=s.U2.id)
    mk_evt(db, s, o, T3, performed_by=s.U4.id)
    mk_evt(db, s, o, T4, performed_by=s.U5.id)
    mk_evt(db, s, o, T4, performed_by=s.U3.id)
    o_id = o.id
    db.expunge_all()
    with recording(db) as rec:
        result = M.list_events(db, po_id=o_id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert len(rec.selects) <= 3
