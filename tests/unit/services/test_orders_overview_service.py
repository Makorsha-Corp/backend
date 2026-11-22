"""Unit tests for app/services/orders_overview_service.py.

Implements tests/unit/services/orders_overview_service.cases.md (revision 4),
one test per card, in card order. Real Postgres session (`db` fixture), rolled
back after each test. Nothing is patched except what Conventions name: the
`db.commit` / `db.rollback` spies and the failing `db.query` of OOV-GS-13.

Every test builds the Standing rows (autouse fixture `st`); card row names are
the lower-case attribute names (`F1.id` -> `st.f1.id`). Order builders live on
the `mk` fixture. `# Then N` marks the checks of the card's Then line N.

Transfer and sales order numbers are unique across all workspaces, so the
builders append a per-process tag to the card's number (`"TO-1"` ->
`"TO-1-<pid>"`). No card reads an order number; the tag only keeps test files
that run side by side from blocking on each other's uncommitted inserts.
"""
# ruff: noqa: FURB157  (cards write `Decimal("0")`; kept as written)
import os
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.exc import InvalidRequestError

from app.models.account import Account
from app.models.enums import WorkOrderStatusEnum
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_approver import PurchaseOrderApprover
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_type import WorkOrderType
from app.schemas.orders_overview import OrdersOverviewStatsResponse, TopFactoryRow
from app.services.orders_overview_service import _dec, orders_overview_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

svc = orders_overview_service

START = date(2026, 5, 1)
END = date(2026, 5, 31)
PRE = date(2026, 4, 30)
POST = date(2026, 6, 1)
MID = date(2026, 5, 10)
MIDT = datetime(2026, 5, 10, 12, 0, 0)  # noqa: DTZ001
PRE_LAST = datetime(2026, 4, 30, 23, 59, 59, 999999)  # noqa: DTZ001
START_0 = datetime(2026, 5, 1, 0, 0, 0)  # noqa: DTZ001
END_LAST = datetime(2026, 5, 31, 23, 59, 59, 999999)  # noqa: DTZ001
POST_0 = datetime(2026, 6, 1, 0, 0, 0)  # noqa: DTZ001
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
MISSING = 999999999


# Approver rows: "approved" after "but".
APPROVED = {"approved": True, "approved_at": T0}


# Convention "XID(k)": an explicit row id, unique per test process
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# Convention "GN(n)" (Parallel runs): the per-process suffix for the globally
# unique transfer / sales order numbers ("TO-1" -> "TO-1-<pid>").
def GN(n):
    return f"{n}-{os.getpid()}"


# Convention "fmap()"
def fmap():
    return defaultdict(lambda: {
        "order_count": 0, "total_value": Decimal(0), "purchase_count": 0,
        "transfer_count": 0, "sales_count": 0, "work_count": 0,
    })


# --------------------------------------------------------------------------- #
# xfail markers (Expect column)
# --------------------------------------------------------------------------- #

_TITLES = {
    2480: "Orders overview mixes drafts and orders awaiting approval into every money figure",
    2481: "Orders overview adds purchases, sales and work costs into one spend / value",
    2500: "Voided purchase, expense and work orders count in the orders overview",
    2501: "Soft-deleted work orders count in the overview's top factories",
    2502: "Picking a factory on the orders overview always fails",
    2503: "Orders to a project are credited to the wrong factory",
    2504: "Orders overview shows another workspace's items, accounts and factories",
    2505: "Orders overview leaderboards cut ties arbitrarily",
    2506: "A deleted factory still appears in the overview's top factories",
}


def bug(n, strict=True, **kw):
    return pytest.mark.xfail(strict=strict, reason=f"BUG-{n}: {_TITLES[n]}", **kw)


def bugs(*ns, strict=True, **kw):
    """One xfail for a card that passes only when every bug named is fixed."""
    reason = "; ".join(f"BUG-{n}: {_TITLES[n]}" for n in ns)
    return pytest.mark.xfail(strict=strict, reason=reason, **kw)


# BUG-2502: every factory-view call raises before Then 1; `raises=` pins the cause.
BUG_2502 = bug(2502, raises=InvalidRequestError)
# FV-08 / FV-09 pass only when BUG-2502 and BUG-2504 are both fixed. Today the
# call raises (BUG-2502) before Then 1; with BUG-2502 alone fixed, Then 1's
# assertion fails (BUG-2504). `raises=` admits exactly those two causes.
BUG_2502_2504 = pytest.mark.xfail(
    strict=True, raises=(InvalidRequestError, AssertionError),
    reason=f"BUG-2502: {_TITLES[2502]}; BUG-2504: {_TITLES[2504]}",
)


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, built in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def st(db):
    s = SimpleNamespace()
    s.w0 = make_workspace(db)
    s.w1 = make_workspace(db)
    s.w2 = make_workspace(db)
    s.u1 = make_profile(db)
    s.u2 = make_profile(db)
    w0, w1, w2 = s.w0.id, s.w1.id, s.w2.id
    # W0
    s.s0 = _add(db, Status(workspace_id=w0, name="Approved", comment="Stage"))
    s.f0 = _add(db, Factory(workspace_id=w0, name="Factory Zero", abbreviation="F0"))
    s.m0 = _add(db, Machine(workspace_id=w0, factory_id=s.f0.id, name="Zero Press"))
    s.wt0 = _add(db, WorkOrderType(workspace_id=w0, name="Repair"))
    s.ac0 = _add(db, Account(workspace_id=w0, name="Zero Co"))
    s.i0 = _add(db, Item(workspace_id=w0, name="Zero Bolt", name_normalized="zero bolt", unit="pcs"))
    # W1
    s.s1 = _add(db, Status(workspace_id=w1, name="Approved", comment="Stage"))
    s.sd = _add(db, Status(workspace_id=w1, name="Draft", comment="Stage"))
    s.sp = _add(db, Status(workspace_id=w1, name="Planning", comment="Stage"))
    s.sr = _add(db, Status(workspace_id=w1, name="Receiving", comment="Stage"))
    s.sc = _add(db, Status(workspace_id=w1, name="Complete", comment="Stage"))
    s.fa = _add(db, Factory(workspace_id=w1, name="Alpha Works", abbreviation="FA"))
    s.f1 = _add(db, Factory(workspace_id=w1, name="Factory One", abbreviation="F1"))
    s.f2 = _add(db, Factory(workspace_id=w1, name="Factory Two", abbreviation="F2"))
    s.fd = _add(db, Factory(workspace_id=w1, name="Old Plant", abbreviation="OP",
                            is_deleted=True, deleted_at=T0, deleted_by=s.u1.id))
    s.fi = _add(db, Factory(workspace_id=w1, name="Idle Plant", abbreviation="IP", is_active=False))
    s.ma = _add(db, Machine(workspace_id=w1, factory_id=s.fa.id, name="Press A"))
    s.m1 = _add(db, Machine(workspace_id=w1, factory_id=s.f1.id, name="Press 1"))
    s.m2 = _add(db, Machine(workspace_id=w1, factory_id=s.f2.id, name="Press 2"))
    s.mi = _add(db, Machine(workspace_id=w1, factory_id=s.f1.id, name="Idle Press", is_active=False))
    s.wt1 = _add(db, WorkOrderType(workspace_id=w1, name="Repair"))
    s.ac1 = _add(db, Account(workspace_id=w1, name="Acme"))
    s.ac2 = _add(db, Account(workspace_id=w1, name="Beta"))
    s.ac3 = _add(db, Account(workspace_id=w1, name="Cargo"))
    s.i1 = _add(db, Item(workspace_id=w1, name="Bolt", name_normalized="bolt", unit="pcs"))
    s.i2 = _add(db, Item(workspace_id=w1, name="Nut", name_normalized="nut", unit="pcs"))
    s.i3 = _add(db, Item(workspace_id=w1, name="Washer", name_normalized="washer", unit="pcs"))
    s.pj1 = _add(db, Project(workspace_id=w1, factory_id=s.f1.id, name="Plant Upgrade", description="Main"))
    # W2
    s.s9 = _add(db, Status(workspace_id=w2, name="Approved", comment="Stage"))
    s.f9 = _add(db, Factory(workspace_id=w2, name="Factory Nine", abbreviation="F9"))
    s.m9 = _add(db, Machine(workspace_id=w2, factory_id=s.f9.id, name="Far Press"))
    s.wt9 = _add(db, WorkOrderType(workspace_id=w2, name="Repair"))
    s.ac9 = _add(db, Account(workspace_id=w2, name="Far Co"))
    s.i9 = _add(db, Item(workspace_id=w2, name="Far Crate", name_normalized="far crate", unit="pcs"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Order builders. W1 by default; `ws="w0"` / `ws="w2"` gives
# "W0 x" / "W2 x" (every W1 row the builder names replaced by that workspace's
# counterpart). Keyword arguments are the columns listed after "but".
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, db, s):
        self.db = db
        self.s = s

    def _cp(self, ws):
        s = self.s
        if ws is None:
            return SimpleNamespace(w=s.w1, s1=s.s1, f1=s.f1, f2=s.f2, ac1=s.ac1, wt1=s.wt1)
        if ws == "w0":
            return SimpleNamespace(w=s.w0, s1=s.s0, f1=s.f0, f2=s.f0, ac1=s.ac0, wt1=s.wt0)
        if ws == "w2":
            return SimpleNamespace(w=s.w2, s1=s.s9, f1=s.f9, f2=s.f9, ac1=s.ac9, wt1=s.wt9)
        raise ValueError(ws)

    def _put(self, model, kw, **fields):
        fields.update(kw)
        return _add(self.db, model(**fields))

    # -- orders --
    def po(self, number, ws=None, **kw):
        c = self._cp(ws)
        return self._put(PurchaseOrder, kw,
            workspace_id=c.w.id, po_number=number, destination_type="storage",
            destination_id=c.f1.id, order_date=MID, total_amount=Decimal("10.00"),
            current_status_id=c.s1.id, created_by=self.s.u1.id)

    def to(self, number, ws=None, **kw):
        c = self._cp(ws)
        return self._put(TransferOrder, kw,
            workspace_id=c.w.id, transfer_number=GN(number),
            source_location_type="storage", source_location_id=c.f2.id,
            destination_location_type="storage", destination_location_id=c.f1.id,
            current_status_id=c.s1.id, created_by=self.s.u1.id, created_at=MIDT)

    def so(self, number, ws=None, **kw):
        c = self._cp(ws)
        return self._put(SalesOrder, kw,
            workspace_id=c.w.id, sales_order_number=GN(number), account_id=c.ac1.id,
            factory_id=c.f1.id, order_date=MID, total_amount=Decimal("10.00"),
            current_status_id=c.s1.id, created_by=self.s.u1.id)

    def eo(self, number, ws=None, **kw):
        c = self._cp(ws)
        return self._put(ExpenseOrder, kw,
            workspace_id=c.w.id, expense_number=number, expense_category="other",
            expense_date=MID, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"),
            created_by=self.s.u1.id)

    def wo(self, number, ws=None, **kw):
        c = self._cp(ws)
        return self._put(WorkOrder, kw,
            workspace_id=c.w.id, work_order_number=number, work_order_type_id=c.wt1.id,
            title="Fix press", factory_id=c.f1.id, status=WorkOrderStatusEnum.COMPLETED,
            cost=Decimal("10.00"), created_by=self.s.u1.id, created_at=MIDT)

    # -- lines --
    def pol(self, p, item, q, sub, **kw):
        return self._put(PurchaseOrderItem, kw,
            workspace_id=p.workspace_id, purchase_order_id=p.id, line_number=1,
            item_id=item.id, quantity_ordered=q, line_subtotal=sub)

    def tol(self, t, item, q, **kw):
        return self._put(TransferOrderItem, kw,
            workspace_id=t.workspace_id, transfer_order_id=t.id, line_number=1,
            item_id=item.id, quantity=q)

    def sol(self, so, item, q, lt, **kw):
        return self._put(SalesOrderItem, kw,
            workspace_id=so.workspace_id, sales_order_id=so.id, item_id=item.id,
            description="Line", quantity_ordered=q, unit_price=Decimal("1.00"), line_total=lt)

    # -- approver rows --
    def poa(self, o, u, **kw):
        return self._put(PurchaseOrderApprover, kw,
            workspace_id=o.workspace_id, purchase_order_id=o.id, user_id=u.id, assigned_at=T0)

    def soa(self, o, u, **kw):
        return self._put(SalesOrderApprover, kw,
            workspace_id=o.workspace_id, sales_order_id=o.id, user_id=u.id, assigned_at=T0)

    def eoa(self, o, u, **kw):
        return self._put(ExpenseOrderApprover, kw,
            workspace_id=o.workspace_id, expense_order_id=o.id, user_id=u.id, assigned_at=T0)

    def woa(self, o, u, **kw):
        return self._put(WorkOrderApprover, kw,
            workspace_id=o.workspace_id, work_order_id=o.id, user_id=u.id, assigned_at=T0)

    # -- closed / stage states, spread with ** --
    @property
    def voided(self):  # voided po / eo
        return {"voided": True, "void_note": "Void", "voided_at": T0, "voided_by": self.s.u1.id}

    @property
    def voided_wo(self):
        return {"status": WorkOrderStatusEnum.VOIDED}

    @property
    def deleted_wo(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.u1.id}

    @property
    def draft(self):  # draft po / so
        return {"current_status_id": self.s.sd.id}

    @property
    def draft_wo(self):
        return {"status": WorkOrderStatusEnum.DRAFT}


@pytest.fixture
def mk(db, st):
    return Builder(db, st)


# A deleted account (built in a card)
def deleted_account(db, st, name):
    return _add(db, Account(workspace_id=st.w1.id, name=name, is_deleted=True, is_active=False,
                            deleted_at=T0, deleted_by=st.u1.id))


# --------------------------------------------------------------------------- #
# Conventions -> Calls and Named checks
# --------------------------------------------------------------------------- #

def stats(db, st, **kw):
    """The default call: get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)."""
    args = {"workspace_id": st.w1.id, "from_date": START, "to_date": END, "limit": 10}
    args.update(kw)
    return svc.get_stats(db, **args)


def top_factories(db, st, limit=10):
    return svc._build_top_factories(db, st.w1.id, START, END, limit)


def poq(db, st):
    return db.query(PurchaseOrder.id).filter(PurchaseOrder.workspace_id == st.w1.id)


def toq(db, st):
    return db.query(TransferOrder.id).filter(TransferOrder.workspace_id == st.w1.id)


def ids(q):
    return sorted(r[0] for r in q.all())


def item_ids(result):
    return [r.item_id for r in result.top_items]


def vendor_ids(result):
    return [r.account_id for r in result.top_vendors]


def customer_ids(result):
    return [r.account_id for r in result.top_customers]


def cats(result):
    return [r.category for r in result.top_expense_categories]


def _frows(result):
    return result.top_factories if isinstance(result, OrdersOverviewStatsResponse) else result


def fids(result):
    return [r.factory_id for r in _frows(result)]


def _one(rows, key, value):
    found = [r for r in rows if getattr(r, key) == value]
    assert len(found) == 1, f"expected exactly one row with {key}={value!r}, got {len(found)}"
    return found[0]


def irow(result, x):
    return _one(result.top_items, "item_id", x.id)


def vrow(result, a):
    return _one(result.top_vendors, "account_id", a.id)


def crow(result, a):
    return _one(result.top_customers, "account_id", a.id)


def erow(result, c):
    return _one(result.top_expense_categories, "category", c)


def frow(result, f):
    return _one(_frows(result), "factory_id", f.id)


@contextmanager
def recorder(db):
    """Convention "recorder": collects every statement sent while the block runs."""
    stmts = []
    conn = db.connection()

    def rec(conn_, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", rec)


def order_part(s):
    return s.split("ORDER BY")[-1].split("LIMIT")[0]


# =========================================================================== #
# _dec
# =========================================================================== #

def test_oov_d_01__none_becomes_decimal_zero():
    """OOV-D-01 — None becomes Decimal zero.
    Rules: _dec R1."""
    result = _dec(None)
    # Then 1
    assert result == Decimal(0)
    assert isinstance(result, Decimal)
    # Then 2
    assert str(result) == "0"


def test_oov_d_02__two_place_decimal_keeps_scale():
    """OOV-D-02 — a two-place Decimal keeps its scale.
    Rules: _dec R2."""
    result = _dec(Decimal("12.50"))
    # Then 1
    assert result == Decimal("12.50")
    assert isinstance(result, Decimal)
    # Then 2
    assert str(result) == "12.50"


def test_oov_d_03__int_becomes_whole_decimal():
    """OOV-D-03 — an int becomes the same whole Decimal.
    Rules: _dec R2."""
    result = _dec(3)
    # Then 1
    assert result == Decimal("3")
    assert isinstance(result, Decimal)
    # Then 2
    assert str(result) == "3"


def test_oov_d_04__float_goes_through_its_text():
    """OOV-D-04 — a float goes through its text, with no binary noise.
    Rules: _dec R2."""
    result = _dec(0.1)
    # Then 1
    assert result == Decimal("0.1")
    # Then 2
    assert str(result) == "0.1"


def test_oov_d_05__zero_is_not_the_none_path():
    """OOV-D-05 — a zero value is not the None path.
    Rules: _dec R1, R2."""
    result = _dec(Decimal("0.00"))
    # Then 1
    assert result == Decimal("0")
    # Then 2
    assert str(result) == "0.00"


def test_oov_d_06__text_not_a_number_raises():
    """OOV-D-06 — text that is not a number raises.
    Rules: _dec Errors."""
    # Then 1
    with pytest.raises(InvalidOperation) as exc:
        _dec("abc")
    assert issubclass(exc.type, InvalidOperation)


# =========================================================================== #
# _po_report_date
# =========================================================================== #

def test_oov_rd_01__order_date_wins_over_created_at(db, st, mk):
    """OOV-RD-01 — order_date wins over created_at.
    Rules: _po_report_date R1."""
    pA = mk.po("PO-A", order_date=MID, created_at=datetime(2026, 11, 10, 5, 40, 0))  # noqa: DTZ001
    mk.po("PO-B", order_date=date(2026, 11, 10), created_at=MIDT)
    result = ids(poq(db, st).filter(svc._in_date_range(svc._po_report_date(), START, END)))
    # Then 1
    assert result == [pA.id]


def test_oov_rd_02__no_order_date_created_at_day_decides(db, st, mk):
    """OOV-RD-02 — with no order_date the created_at day decides, at both edges.
    Rules: _po_report_date R1, _in_date_range R1."""
    mk.po("PO-1", order_date=None, created_at=PRE_LAST)
    p2 = mk.po("PO-2", order_date=None, created_at=START_0)
    p3 = mk.po("PO-3", order_date=None, created_at=END_LAST)
    mk.po("PO-4", order_date=None, created_at=POST_0)
    result = ids(poq(db, st).filter(svc._in_date_range(svc._po_report_date(), START, END)))
    # Then 1
    assert result == sorted([p2.id, p3.id])


# =========================================================================== #
# _in_date_range
# =========================================================================== #

def test_oov_ir_01__both_ends_in_outside_and_null_out(db, st, mk):
    """OOV-IR-01 — both ends are in, the days outside and NULL are out.
    Rules: _in_date_range R1."""
    mk.po("PO-1", order_date=PRE)
    p2 = mk.po("PO-2", order_date=START)
    p3 = mk.po("PO-3", order_date=END)
    mk.po("PO-4", order_date=POST)
    mk.po("PO-5", order_date=None, created_at=MIDT)
    result = sorted(r[0] for r in db.query(PurchaseOrder.id).filter(
        PurchaseOrder.workspace_id == st.w1.id,
        svc._in_date_range(PurchaseOrder.order_date, START, END)).all())
    # Then 1
    assert result == sorted([p2.id, p3.id])


def test_oov_ir_02__from_after_to_matches_nothing(db, st, mk):
    """OOV-IR-02 — from after to matches nothing.
    Rules: _in_date_range R1."""
    mk.so("SO-1", order_date=START)
    mk.so("SO-2", order_date=END)
    result = sorted(r[0] for r in db.query(SalesOrder.id).filter(
        SalesOrder.workspace_id == st.w1.id,
        svc._in_date_range(SalesOrder.order_date, END, START)).all())
    # Then 1
    assert result == []


def test_oov_ir_03__one_day_range_keeps_that_day(db, st, mk):
    """OOV-IR-03 — a one-day range keeps that day only.
    Rules: _in_date_range R1."""
    mk.so("SO-1", order_date=PRE)
    s2 = mk.so("SO-2", order_date=START)
    mk.so("SO-3", order_date=date(2026, 5, 2))
    result = sorted(r[0] for r in db.query(SalesOrder.id).filter(
        SalesOrder.workspace_id == st.w1.id,
        svc._in_date_range(SalesOrder.order_date, START, START)).all())
    # Then 1
    assert result == [s2.id]


# =========================================================================== #
# _filter_po_by_factory
# =========================================================================== #

def test_oov_fp_01__storage_and_damaged_of_factory_kept(db, st, mk):
    """OOV-FP-01 — storage and damaged destinations of the factory are kept.
    Rules: _filter_po_by_factory R1, R4."""
    mk.po("PO-A", destination_id=st.fa.id)
    p1 = mk.po("PO-1")
    p2 = mk.po("PO-2", destination_type="damaged")
    mk.po("PO-B", destination_id=st.f2.id)
    mk.po("PO-C", destination_type="damaged", destination_id=st.f2.id)
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == sorted([p1.id, p2.id])


def test_oov_fp_02__machine_of_factory_kept(db, st, mk):
    """OOV-FP-02 — a machine of the factory is kept, machines of other factories are not.
    Rules: _filter_po_by_factory R2, R4."""
    mk.po("PO-A", destination_type="machine", destination_id=st.ma.id)
    p1 = mk.po("PO-1", destination_type="machine", destination_id=st.m1.id)
    mk.po("PO-B", destination_type="machine", destination_id=st.m2.id)
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == [p1.id]


def test_oov_fp_03__destination_type_decides_table(db, st, mk):
    """OOV-FP-03 — the destination type decides which table the id means.
    Rules: _filter_po_by_factory R4."""
    _add(db, Machine(id=XID(1), workspace_id=st.w1.id, factory_id=st.f1.id, name="Press X"))
    mk.po("PO-1", destination_type="storage", destination_id=XID(1))
    mk.po("PO-2", destination_type="machine", destination_id=MISSING)
    mk.po("PO-3", destination_type="office", destination_id=st.f1.id)
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == []


def test_oov_fp_04__inactive_machine_still_matches(db, st, mk):
    """OOV-FP-04 — an inactive machine still matches.
    Rules: _filter_po_by_factory R5."""
    p1 = mk.po("PO-1", destination_type="machine", destination_id=st.mi.id)
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == [p1.id]


def test_oov_fp_05__deleted_factory_matches_own_storage(db, st, mk):
    """OOV-FP-05 — a deleted factory still matches its own storage.
    Rules: _filter_po_by_factory R5."""
    p1 = mk.po("PO-1", destination_id=st.fd.id)
    mk.po("PO-2")
    result = ids(svc._filter_po_by_factory(poq(db, st), st.fd.id))
    # Then 1
    assert result == [p1.id]


@bug(2504)
def test_oov_fp_06__machine_of_other_workspace_never_matches(db, st, mk):
    """OOV-FP-06 — a machine of another workspace never matches.
    Rules: _filter_po_by_factory R2a [BUG-2504]."""
    mz = _add(db, Machine(workspace_id=st.w0.id, factory_id=st.f1.id, name="Stray Zero"))
    mx = _add(db, Machine(workspace_id=st.w2.id, factory_id=st.f1.id, name="Stray Press"))
    mk.po("PO-1", destination_type="machine", destination_id=mz.id)
    mk.po("PO-2", destination_type="machine", destination_id=mx.id)
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == []


@bug(2503)
def test_oov_fp_07__po_to_component_of_factory_project_kept(db, st, mk):
    """OOV-FP-07 — a PO to a component of the factory's project is kept.
    Rules: _filter_po_by_factory R3 [BUG-2503]."""
    _add(db, ProjectComponent(id=XID(2), workspace_id=st.w1.id, project_id=st.pj1.id, name="Foundation"))
    p1 = mk.po("PO-1", destination_type="project", destination_id=XID(2))
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == [p1.id]


@bug(2503)
def test_oov_fp_08__project_with_component_id_does_not_decide(db, st, mk):
    """OOV-FP-08 — a project whose id equals the component id does not decide.
    Rules: _filter_po_by_factory R3 [BUG-2503]."""
    _add(db, Project(id=XID(3), workspace_id=st.w1.id, factory_id=st.f2.id, name="Side Shed", description="Main"))
    _add(db, ProjectComponent(id=XID(3), workspace_id=st.w1.id, project_id=st.pj1.id, name="Roof"))
    mk.po("PO-1", destination_type="project", destination_id=XID(3))
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f2.id))
    # Then 1
    assert result == []


def test_oov_fp_09__component_of_other_workspace_matches_nothing(db, st, mk):
    """OOV-FP-09 — a component of another workspace matches nothing.
    Rules: _filter_po_by_factory R3."""
    p9 = _add(db, Project(workspace_id=st.w2.id, factory_id=st.f9.id, name="Far Site", description="Main"))
    _add(db, ProjectComponent(id=XID(4), workspace_id=st.w2.id, project_id=p9.id, name="Far Roof"))
    mk.po("PO-1", destination_type="project", destination_id=XID(4))
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == []


def test_oov_fp_10__project_of_other_factory_dropped_either_table(db, st, mk):
    """OOV-FP-10 — a project of another factory is dropped, whichever table the id is read in.
    Rules: _filter_po_by_factory R4."""
    px = _add(db, Project(id=XID(3), workspace_id=st.w1.id, factory_id=st.f2.id, name="Side Shed", description="Main"))
    _add(db, ProjectComponent(id=XID(3), workspace_id=st.w1.id, project_id=px.id, name="Roof"))
    mk.po("PO-1", destination_type="project", destination_id=XID(3))
    p2 = mk.po("PO-2")
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == [p2.id]


def test_oov_fp_11__storage_id_equal_to_project_and_component_not_project(db, st, mk):
    """OOV-FP-11 — a storage id equal to a project and component id of the factory is not a project.
    Rules: _filter_po_by_factory R1, R4."""
    _add(db, Project(id=XID(5), workspace_id=st.w1.id, factory_id=st.f1.id, name="North Wing", description="Main"))
    _add(db, ProjectComponent(id=XID(5), workspace_id=st.w1.id, project_id=st.pj1.id, name="Wall"))
    mk.po("PO-1", destination_type="storage", destination_id=XID(5))
    p2 = mk.po("PO-2")
    result = ids(svc._filter_po_by_factory(poq(db, st), st.f1.id))
    # Then 1
    assert result == [p2.id]

# =========================================================================== #
# _filter_transfer_by_factory
# =========================================================================== #

def test_oov_ft_01__storage_or_damaged_at_either_end_kept(db, st, mk):
    """OOV-FT-01 — storage or damaged of the factory at either end is kept.
    Rules: _filter_transfer_by_factory R1, R3."""
    t1 = mk.to("TO-1")
    t2 = mk.to("TO-2", source_location_id=st.f1.id, destination_location_id=st.f2.id)
    t3 = mk.to("TO-3", source_location_type="damaged", source_location_id=st.fa.id,
               destination_location_type="damaged", destination_location_id=st.f1.id)
    t4 = mk.to("TO-4", source_location_type="damaged", source_location_id=st.f1.id,
               destination_location_id=st.fa.id)
    mk.to("TO-5", source_location_id=st.fa.id, destination_location_id=st.f2.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == sorted([t1.id, t2.id, t3.id, t4.id])


def test_oov_ft_02__machine_of_factory_at_either_end_kept(db, st, mk):
    """OOV-FT-02 — a machine of the factory at either end is kept.
    Rules: _filter_transfer_by_factory R1, R3."""
    t1 = mk.to("TO-1", destination_location_type="machine", destination_location_id=st.m1.id)
    t2 = mk.to("TO-2", source_location_type="machine", source_location_id=st.m1.id,
               destination_location_type="damaged", destination_location_id=st.f2.id)
    mk.to("TO-3", source_location_type="machine", source_location_id=st.ma.id,
          destination_location_type="machine", destination_location_id=st.m2.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == sorted([t1.id, t2.id])


def test_oov_ft_03__transfer_between_factories_matches_other_too(db, st, mk):
    """OOV-FT-03 — a transfer between two factories matches the other factory too.
    Rules: _filter_transfer_by_factory R1."""
    t1 = mk.to("TO-1", destination_location_type="machine", destination_location_id=st.m1.id)
    t2 = mk.to("TO-2", source_location_type="machine", source_location_id=st.m1.id,
               destination_location_type="damaged", destination_location_id=st.f2.id)
    mk.to("TO-3", source_location_type="machine", source_location_id=st.ma.id,
          destination_location_id=st.fa.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f2.id))
    # Then 1
    assert result == sorted([t1.id, t2.id])


def test_oov_ft_04__project_source_never_considered(db, st, mk):
    """OOV-FT-04 — a project source is never considered.
    Rules: _filter_transfer_by_factory R2."""
    cmp_ = _add(db, ProjectComponent(workspace_id=st.w1.id, project_id=st.pj1.id, name="Roof"))
    mk.to("TO-1", source_location_type="project", source_location_id=st.pj1.id,
          destination_location_id=st.fa.id)
    mk.to("TO-2", source_location_type="project", source_location_id=cmp_.id,
          destination_location_id=st.fa.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == []


def test_oov_ft_05__inactive_locations_match_inside_one_factory_once(db, st, mk):
    """OOV-FT-05 — inactive locations match, and a transfer inside one factory appears once.
    Rules: _filter_transfer_by_factory R3."""
    t1 = mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="machine",
               destination_location_id=st.mi.id)
    t2 = mk.to("TO-2", source_location_id=st.f1.id, destination_location_type="damaged",
               destination_location_id=st.f1.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == sorted([t1.id, t2.id])


@bug(2503)
def test_oov_ft_06__transfer_to_component_of_factory_project_kept(db, st, mk):
    """OOV-FT-06 — a transfer to a component of the factory's project is kept.
    Rules: _filter_transfer_by_factory R2 [BUG-2503]."""
    _add(db, ProjectComponent(id=XID(2), workspace_id=st.w1.id, project_id=st.pj1.id, name="Foundation"))
    t1 = mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="project",
               destination_location_id=XID(2))
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == [t1.id]


@bug(2504)
def test_oov_ft_07__machine_of_other_workspace_never_matches(db, st, mk):
    """OOV-FT-07 — a machine of another workspace never matches.
    Rules: _filter_transfer_by_factory R2 [BUG-2504]."""
    mz = _add(db, Machine(workspace_id=st.w0.id, factory_id=st.f1.id, name="Stray Zero"))
    mx = _add(db, Machine(workspace_id=st.w2.id, factory_id=st.f1.id, name="Stray Press"))
    mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="machine",
          destination_location_id=mx.id)
    mk.to("TO-2", source_location_type="machine", source_location_id=mz.id,
          destination_location_id=st.fa.id)
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == []


def test_oov_ft_08__transfer_to_project_of_other_factory_dropped(db, st, mk):
    """OOV-FT-08 — a transfer to a project of another factory is dropped, whichever table the id is read in.
    Rules: _filter_transfer_by_factory R3."""
    px = _add(db, Project(id=XID(3), workspace_id=st.w1.id, factory_id=st.f2.id, name="Side Shed", description="Main"))
    _add(db, ProjectComponent(id=XID(3), workspace_id=st.w1.id, project_id=px.id, name="Roof"))
    mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="project",
          destination_location_id=XID(3))
    t2 = mk.to("TO-2")
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == [t2.id]


def test_oov_ft_09__storage_end_equal_to_project_and_component_not_project(db, st, mk):
    """OOV-FT-09 — a storage end whose id equals a project and component id of the factory is not a project.
    Rules: _filter_transfer_by_factory R1, R3."""
    _add(db, Project(id=XID(5), workspace_id=st.w1.id, factory_id=st.f1.id, name="North Wing", description="Main"))
    _add(db, ProjectComponent(id=XID(5), workspace_id=st.w1.id, project_id=st.pj1.id, name="Wall"))
    mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="storage",
          destination_location_id=XID(5))
    t2 = mk.to("TO-2")
    result = ids(svc._filter_transfer_by_factory(toq(db, st), st.f1.id))
    # Then 1
    assert result == [t2.id]

# =========================================================================== #
# _accumulate_factory
# =========================================================================== #

def test_oov_af_01__no_factory_id_changes_nothing():
    """OOV-AF-01 — no factory id changes nothing.
    Rules: _accumulate_factory R1."""
    m = fmap()
    result = svc._accumulate_factory(m, None, Decimal("5.00"), "purchase")
    # Then 1
    assert result is None
    # Then 2
    assert len(m) == 0


def test_oov_af_02__factory_id_zero_credited():
    """OOV-AF-02 — factory id 0 is credited with a new entry.
    Rules: _accumulate_factory R1, R2, R3."""
    m = fmap()
    result = svc._accumulate_factory(m, 0, Decimal("5.00"), "purchase")
    # Then 1
    assert result is None
    # Then 2
    assert list(m) == [0]
    # Then 3
    assert m[0]["order_count"] == 1
    assert m[0]["purchase_count"] == 1
    # Then 4
    assert m[0]["total_value"] == Decimal("5.00")
    # Then 5
    assert m[0]["transfer_count"] == 0
    assert m[0]["sales_count"] == 0
    assert m[0]["work_count"] == 0


def test_oov_af_03__unknown_kind_adds_order_no_per_kind_counter():
    """OOV-AF-03 — an unknown kind raises nothing, adds the order and no per-kind counter.
    Rules: _accumulate_factory R2, R3."""
    m = fmap()
    svc._accumulate_factory(m, 7, Decimal("1.00"), "other")
    # Then 1
    assert list(m) == [7]
    # Then 2
    assert m[7]["order_count"] == 1
    # Then 3
    assert m[7]["purchase_count"] == 0
    assert m[7]["transfer_count"] == 0
    assert m[7]["sales_count"] == 0
    assert m[7]["work_count"] == 0


def test_oov_af_04__transfer_adds_transfer_count_only():
    """OOV-AF-04 — a transfer adds to transfer_count only.
    Rules: _accumulate_factory R2, R3."""
    m = fmap()
    svc._accumulate_factory(m, 3, Decimal("0"), "transfer")
    # Then 1
    assert m[3]["order_count"] == 1
    assert m[3]["transfer_count"] == 1
    # Then 2
    assert m[3]["purchase_count"] == 0
    assert m[3]["sales_count"] == 0
    assert m[3]["work_count"] == 0


def test_oov_af_05__sales_adds_sales_count_only():
    """OOV-AF-05 — a sales order adds to sales_count only.
    Rules: _accumulate_factory R2, R3."""
    m = fmap()
    svc._accumulate_factory(m, 3, Decimal("2.00"), "sales")
    # Then 1
    assert m[3]["order_count"] == 1
    assert m[3]["sales_count"] == 1
    # Then 2
    assert m[3]["purchase_count"] == 0
    assert m[3]["transfer_count"] == 0
    assert m[3]["work_count"] == 0


def test_oov_af_06__work_adds_work_count_only():
    """OOV-AF-06 — a work order adds to work_count only.
    Rules: _accumulate_factory R2, R3."""
    m = fmap()
    svc._accumulate_factory(m, 3, Decimal("2.00"), "work")
    # Then 1
    assert m[3]["order_count"] == 1
    assert m[3]["work_count"] == 1
    # Then 2
    assert m[3]["purchase_count"] == 0
    assert m[3]["transfer_count"] == 0
    assert m[3]["sales_count"] == 0


def test_oov_af_07__second_purchase_adds_exactly():
    """OOV-AF-07 — a second purchase adds to the existing entry exactly.
    Rules: _accumulate_factory R2, R3."""
    m = fmap()
    svc._accumulate_factory(m, 3, Decimal("1.25"), "purchase")
    svc._accumulate_factory(m, 3, Decimal("0.05"), "purchase")
    # Then 1
    assert list(m) == [3]
    # Then 2
    assert m[3]["order_count"] == 2
    assert m[3]["purchase_count"] == 2
    # Then 3
    assert m[3]["total_value"] == Decimal("1.30")
    # Then 4
    assert str(m[3]["total_value"]) == "1.30"


# =========================================================================== #
# _build_top_factories
# =========================================================================== #

def test_oov_tf_01__po_to_storage_makes_full_row(db, st, mk):
    """OOV-TF-01 — a PO to a factory's storage makes a full row.
    Rules: _build_top_factories R2, R9, R10, _factory_from_location R1, _accumulate_factory R2, R3."""
    mk.po("PO-1", total_amount=Decimal("100.50"))
    result = top_factories(db, st)
    # Then 1
    assert len(result) == 1
    assert isinstance(result[0], TopFactoryRow)
    # Then 2
    assert result[0].factory_id == st.f1.id
    assert result[0].factory_name == "Factory One"
    # Then 3
    assert result[0].order_count == 1
    assert result[0].purchase_count == 1
    # Then 4
    assert result[0].transfer_count == 0
    assert result[0].sales_count == 0
    assert result[0].work_count == 0
    # Then 5
    assert result[0].total_value == Decimal("100.50")
    # Then 6
    assert str(result[0].total_value) == "100.50"


def test_oov_tf_02__two_pos_add_up_damaged_included(db, st, mk):
    """OOV-TF-02 — two POs of one factory add up exactly, damaged included.
    Rules: _build_top_factories R2, _factory_from_location R1, _accumulate_factory R2."""
    mk.po("PO-1", total_amount=Decimal("1234.56"))
    mk.po("PO-2", destination_type="damaged", total_amount=Decimal("0.05"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 2
    assert frow(result, st.f1).purchase_count == 2
    # Then 3
    assert frow(result, st.f1).total_value == Decimal("1234.61")
    # Then 4
    assert str(frow(result, st.f1).total_value) == "1234.61"


def test_oov_tf_03__machine_po_for_machine_factory_unresolved_nowhere(db, st, mk):
    """OOV-TF-03 — a PO to a machine counts for the machine's factory; unresolved POs count nowhere.
    Rules: _build_top_factories R2, _factory_from_location R2, R4, _accumulate_factory R1."""
    mk.po("PO-1", destination_type="machine", destination_id=st.m2.id)
    mk.po("PO-2", destination_type="machine", destination_id=MISSING)
    mk.po("PO-3", destination_type="office", destination_id=st.f1.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 1
    assert frow(result, st.f2).purchase_count == 1


def test_oov_tf_04__transfer_counts_for_destination_only(db, st, mk):
    """OOV-TF-04 — a transfer counts for its destination's factory only and adds no value.
    Rules: _build_top_factories R3, R10, _factory_from_location R2."""
    mk.to("TO-1", destination_location_type="machine", destination_location_id=st.m1.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 1
    assert frow(result, st.f1).transfer_count == 1
    # Then 3
    assert frow(result, st.f1).purchase_count == 0
    assert frow(result, st.f1).sales_count == 0
    assert frow(result, st.f1).work_count == 0
    # Then 4
    assert frow(result, st.f1).total_value == Decimal("0")


def test_oov_tf_05__no_destination_factory_source_decides(db, st, mk):
    """OOV-TF-05 — with no destination factory the source decides; a project source never does.
    Rules: _build_top_factories R3, _factory_from_location R2, R3, _accumulate_factory R1."""
    mk.to("TO-1", destination_location_type="machine", destination_location_id=MISSING)
    mk.to("TO-2", source_location_type="machine", source_location_id=MISSING,
          destination_location_type="machine", destination_location_id=MISSING)
    mk.to("TO-3", source_location_type="project", source_location_id=st.pj1.id,
          destination_location_type="machine", destination_location_id=MISSING)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 1
    assert frow(result, st.f2).transfer_count == 1


def test_oov_tf_06__sales_order_counts_for_own_factory(db, st, mk):
    """OOV-TF-06 — a sales order counts for its own factory.
    Rules: _build_top_factories R4, R10."""
    mk.so("SO-1", factory_id=st.f2.id, total_amount=Decimal("30.05"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 1
    assert frow(result, st.f2).sales_count == 1
    assert frow(result, st.f2).purchase_count == 0


def test_oov_tf_07__work_orders_count_for_their_factory(db, st, mk):
    """OOV-TF-07 — work orders count for their factory.
    Rules: _build_top_factories R5, R10."""
    mk.wo("WO-1", cost=Decimal("12.34"))
    mk.wo("WO-2", cost=None)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 2
    assert frow(result, st.f1).work_count == 2
    assert frow(result, st.f1).sales_count == 0


def test_oov_tf_08__expense_orders_never_count(db, st, mk):
    """OOV-TF-08 — expense orders never count; nothing resolved gives [].
    Rules: _build_top_factories R6, R8."""
    mk.eo("EX-1", expense_category="factory", total_amount=Decimal("99.00"))
    mk.eo("EX-2", account_id=st.ac1.id)
    result = top_factories(db, st)
    # Then 1
    assert result == []


def test_oov_tf_09__w0_and_w2_orders_count_nowhere(db, st, mk):
    """OOV-TF-09 — orders of W0 and W2 count nowhere, also when they point at W1 rows.
    Rules: _build_top_factories R1."""
    mk.po("PO-Z", ws="w0")
    mk.to("TO-Z", ws="w0")
    mk.so("SO-Z", ws="w0")
    mk.wo("WO-Z", ws="w0")
    mk.po("PO-1", total_amount=Decimal("7.00"))
    mk.po("PO-9", ws="w2")
    mk.to("TO-9", ws="w2")
    mk.so("SO-9", ws="w2")
    mk.wo("WO-9", ws="w2")
    mk.po("PO-9B", ws="w2", destination_id=st.f2.id)
    mk.so("SO-9B", ws="w2", factory_id=st.f2.id)
    mk.wo("WO-9B", ws="w2", factory_id=st.f2.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 1
    assert frow(result, st.f1).total_value == Decimal("7.00")


def test_oov_tf_10__po_report_days_at_both_edges(db, st, mk):
    """OOV-TF-10 — PO report days at both edges, with and without order_date.
    Rules: _build_top_factories R1, _po_report_date R1."""
    mk.po("PO-1", order_date=PRE)
    mk.po("PO-2", order_date=START, destination_id=st.f2.id)
    mk.po("PO-3", order_date=END, destination_id=st.f2.id)
    mk.po("PO-4", order_date=POST)
    mk.po("PO-5", order_date=None, created_at=PRE_LAST)
    mk.po("PO-6", order_date=None, created_at=START_0, destination_id=st.f2.id)
    mk.po("PO-7", order_date=None, created_at=POST_0)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 3


def test_oov_tf_11__transfer_days_at_both_edges(db, st, mk):
    """OOV-TF-11 — transfer days (created_at) at both edges.
    Rules: _build_top_factories R1."""
    mk.to("TO-1", created_at=PRE_LAST)
    mk.to("TO-2", created_at=START_0, source_location_id=st.fa.id, destination_location_id=st.f2.id)
    mk.to("TO-3", created_at=END_LAST, source_location_id=st.fa.id, destination_location_id=st.f2.id)
    mk.to("TO-4", created_at=POST_0)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 2
    assert frow(result, st.f2).transfer_count == 2


def test_oov_tf_12__sales_days_at_both_edges(db, st, mk):
    """OOV-TF-12 — sales days at both edges.
    Rules: _build_top_factories R1."""
    mk.so("SO-1", order_date=PRE)
    mk.so("SO-2", order_date=START, factory_id=st.f2.id)
    mk.so("SO-3", order_date=END, factory_id=st.f2.id)
    mk.so("SO-4", order_date=POST)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 2
    assert frow(result, st.f2).sales_count == 2


def test_oov_tf_13__work_order_days_at_both_edges(db, st, mk):
    """OOV-TF-13 — work order days (created_at) at both edges.
    Rules: _build_top_factories R1."""
    mk.wo("WO-1", created_at=PRE_LAST)
    mk.wo("WO-2", created_at=START_0, factory_id=st.f2.id)
    mk.wo("WO-3", created_at=END_LAST, factory_id=st.f2.id)
    mk.wo("WO-4", created_at=POST_0)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 2
    assert frow(result, st.f2).work_count == 2


def test_oov_tf_14__sorted_by_count_then_value(db, st, mk):
    """OOV-TF-14 — sorted by order count, then value, both descending.
    Rules: _build_top_factories R11."""
    mk.po("PO-A", destination_id=st.fa.id, total_amount=Decimal("500.00"))
    mk.po("PO-1", total_amount=Decimal("1.00"))
    mk.po("PO-2", total_amount=Decimal("1.00"))
    mk.po("PO-B", destination_id=st.f2.id, total_amount=Decimal("900.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id, st.f2.id, st.fa.id]


def test_oov_tf_15__cut_to_limit_after_sorting(db, st, mk):
    """OOV-TF-15 — cut to limit after sorting.
    Rules: _build_top_factories R11."""
    for n in ("PO-A1", "PO-A2", "PO-A3"):
        mk.po(n, destination_id=st.fa.id)
    mk.po("PO-1")
    for n in ("PO-B1", "PO-B2"):
        mk.po(n, destination_id=st.f2.id)
    result = top_factories(db, st, 2)
    # Then 1
    assert fids(result) == [st.fa.id, st.f2.id]


def test_oov_tf_16__missing_or_empty_name_falls_back(db, st, mk):
    """OOV-TF-16 — a missing or empty factory name falls back to "Factory #id".
    Rules: _build_top_factories R9."""
    fe = _add(db, Factory(workspace_id=st.w1.id, name="", abbreviation="FE"))
    mk.po("PO-1", destination_id=MISSING, total_amount=Decimal("2.00"))
    mk.po("PO-2", destination_id=fe.id, total_amount=Decimal("1.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [MISSING, fe.id]
    # Then 2
    assert result[0].factory_name == "Factory #999999999"
    # Then 3
    assert result[1].factory_name == f"Factory #{fe.id}"


def test_oov_tf_17__storage_id_zero_credited_as_factory_zero(db, st, mk):
    """OOV-TF-17 — storage id 0 is credited as factory 0.
    Rules: _accumulate_factory R1, _build_top_factories R9."""
    mk.po("PO-1", destination_id=0)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [0]
    # Then 2
    assert result[0].factory_name == "Factory #0"
    assert result[0].order_count == 1


def test_oov_tf_18__inactive_factory_is_a_row(db, st, mk):
    """OOV-TF-18 — an inactive factory is a row.
    Rules: _build_top_factories R9a."""
    mk.po("PO-1", destination_id=st.fi.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.fi.id]
    # Then 2
    assert result[0].factory_name == "Idle Plant"


@bug(2506)
def test_oov_tf_19__deleted_factory_not_a_row(db, st, mk):
    """OOV-TF-19 — a deleted factory is not a row.
    Rules: _build_top_factories R9a [BUG-2506]."""
    mk.po("PO-1", destination_id=st.fd.id)
    mk.po("PO-2")
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2500)
def test_oov_tf_20__voided_po_counts_nowhere(db, st, mk):
    """OOV-TF-20 — a voided PO counts nowhere.
    Rules: _build_top_factories R2a [BUG-2500]."""
    mk.po("PO-1")
    mk.po("PO-2", **mk.voided, total_amount=Decimal("1000.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 1
    assert frow(result, st.f1).total_value == Decimal("10.00")


@bug(2500)
def test_oov_tf_21__voided_work_order_counts_nowhere(db, st, mk):
    """OOV-TF-21 — a VOIDED work order counts nowhere.
    Rules: _build_top_factories R5a [BUG-2500]."""
    mk.wo("WO-1", cost=Decimal("5.00"))
    mk.wo("WO-2", **mk.voided_wo, cost=Decimal("50.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 1
    assert frow(result, st.f1).work_count == 1


@bug(2501)
def test_oov_tf_22__deleted_work_order_counts_nowhere(db, st, mk):
    """OOV-TF-22 — a deleted work order counts nowhere.
    Rules: _build_top_factories R5a [BUG-2501]."""
    mk.wo("WO-1", cost=Decimal("5.00"))
    mk.wo("WO-2", **mk.deleted_wo, cost=Decimal("50.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 1
    assert frow(result, st.f1).work_count == 1


@bug(2504)
def test_oov_tf_23__sales_on_other_workspace_factory_credits_none(db, st, mk):
    """OOV-TF-23 — a W1 sales order on another workspace's factory credits no factory.
    Rules: _build_top_factories R8a [BUG-2504]."""
    mk.so("SO-0", factory_id=st.f0.id)
    mk.so("SO-1")
    mk.so("SO-9", factory_id=st.f9.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert [r.factory_name for r in result] == ["Factory One"]


@bug(2504)
def test_oov_tf_24__work_on_other_workspace_factory_credits_none(db, st, mk):
    """OOV-TF-24 — a W1 work order on another workspace's factory credits no factory.
    Rules: _build_top_factories R8a [BUG-2504]."""
    mk.wo("WO-0", factory_id=st.f0.id)
    mk.wo("WO-1")
    mk.wo("WO-9", factory_id=st.f9.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2504)
def test_oov_tf_25__po_to_other_workspace_storage_credits_none(db, st, mk):
    """OOV-TF-25 — a W1 PO to another workspace's factory storage credits no factory.
    Rules: _build_top_factories R8a [BUG-2504]."""
    mk.po("PO-0", destination_id=st.f0.id)
    mk.po("PO-1")
    mk.po("PO-9", destination_type="damaged", destination_id=st.f9.id)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2504)
def test_oov_tf_26__transfer_to_other_workspace_factory_credits_none(db, st, mk):
    """OOV-TF-26 — a W1 transfer to another workspace's factory credits no factory.
    Rules: _build_top_factories R8a [BUG-2504]."""
    mk.to("TO-0", source_location_type="machine", source_location_id=MISSING,
          destination_location_id=st.f0.id)
    mk.to("TO-9", source_location_type="machine", source_location_id=MISSING,
          destination_location_id=st.f9.id)
    result = top_factories(db, st)
    # Then 1
    assert result == []


@bug(2504)
def test_oov_tf_27__transfer_from_other_workspace_factory_credits_none(db, st, mk):
    """OOV-TF-27 — a W1 transfer from another workspace's factory credits no factory.
    Rules: _build_top_factories R8a [BUG-2504]."""
    mk.to("TO-0", source_location_id=st.f0.id, destination_location_type="machine",
          destination_location_id=MISSING)
    mk.to("TO-9", source_location_type="damaged", source_location_id=st.f9.id,
          destination_location_type="machine", destination_location_id=MISSING)
    result = top_factories(db, st)
    # Then 1
    assert result == []


@bug(2504)
def test_oov_tf_28__po_to_other_workspace_machine_credits_none(db, st, mk):
    """OOV-TF-28 — a W1 PO to another workspace's machine credits no factory.
    Rules: _factory_from_location R2a [BUG-2504], _build_top_factories R8a."""
    mk.po("PO-0", destination_type="machine", destination_id=st.m0.id)
    mk.po("PO-9", destination_type="machine", destination_id=st.m9.id)
    result = top_factories(db, st)
    # Then 1
    assert result == []


@bug(2504)
def test_oov_tf_29__other_workspace_machine_naming_w1_factory_credits_nothing(db, st, mk):
    """OOV-TF-29 — another workspace's machine that names a W1 factory credits nothing.
    Rules: _factory_from_location R2a [BUG-2504]."""
    mx = _add(db, Machine(workspace_id=st.w2.id, factory_id=st.f1.id, name="Stray Press"))
    mk.po("PO-1", destination_type="machine", destination_id=mx.id)
    result = top_factories(db, st)
    # Then 1
    assert result == []


@bug(2503)
def test_oov_tf_30__po_to_component_counts_for_project_factory(db, st, mk):
    """OOV-TF-30 — a PO to a project component counts for the component's project's factory.
    Rules: _factory_from_location R3 [BUG-2503], _build_top_factories R2."""
    _add(db, ProjectComponent(id=XID(2), workspace_id=st.w1.id, project_id=st.pj1.id, name="Foundation"))
    mk.po("PO-1", destination_type="project", destination_id=XID(2))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2503)
def test_oov_tf_31__project_with_component_id_does_not_take_po(db, st, mk):
    """OOV-TF-31 — a project with the component's id does not take the PO.
    Rules: _factory_from_location R3 [BUG-2503]."""
    _add(db, Project(id=XID(3), workspace_id=st.w1.id, factory_id=st.f2.id, name="Side Shed", description="Main"))
    _add(db, ProjectComponent(id=XID(3), workspace_id=st.w1.id, project_id=st.pj1.id, name="Roof"))
    mk.po("PO-1", destination_type="project", destination_id=XID(3))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2503)
def test_oov_tf_32__transfer_to_component_counts_for_that_factory(db, st, mk):
    """OOV-TF-32 — a transfer to a project component counts for that factory, not the source's.
    Rules: _factory_from_location R3 [BUG-2503], _build_top_factories R3."""
    _add(db, ProjectComponent(id=XID(2), workspace_id=st.w1.id, project_id=st.pj1.id, name="Foundation"))
    mk.to("TO-1", source_location_id=st.fa.id, destination_location_type="project",
          destination_location_id=XID(2))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]


@bug(2505)
def test_oov_tf_33__tied_factories_by_name_before_cut(db, st, mk):
    """OOV-TF-33 — tied factories are ordered by name case-insensitive before the cut.
    Rules: _build_top_factories R11a [BUG-2505]."""
    fz = _add(db, Factory(workspace_id=st.w1.id, name="zeta Mill", abbreviation="FZ"))
    fb = _add(db, Factory(workspace_id=st.w1.id, name="Beta Mill", abbreviation="FB"))
    fc = _add(db, Factory(workspace_id=st.w1.id, name="alpha Mill", abbreviation="FC"))
    mk.to("TO-Z", destination_location_id=fz.id)
    mk.so("SO-B", factory_id=fb.id, total_amount=Decimal("0.00"))
    mk.wo("WO-C", factory_id=fc.id, cost=None)
    result = top_factories(db, st, 2)
    # Then 1
    assert len(result) == 2
    assert [r.order_count for r in result] == [1, 1]
    # Then 2
    assert fids(result) == [fc.id, fb.id]


@bug(2505)
def test_oov_tf_34__factories_tied_on_name_by_id(db, st, mk):
    """OOV-TF-34 — factories tied on name case-insensitive are ordered by id.
    Rules: _build_top_factories R11a [BUG-2505]."""
    fs1 = _add(db, Factory(workspace_id=st.w1.id, name="Same Mill", abbreviation="S1"))
    fs2 = _add(db, Factory(workspace_id=st.w1.id, name="SAME MILL", abbreviation="S2"))
    mk.to("TO-S", destination_location_id=fs2.id)
    mk.wo("WO-S", factory_id=fs1.id, cost=None)
    result = top_factories(db, st)
    # Then 1
    assert sorted(fids(result)) == sorted([fs1.id, fs2.id])
    # Then 2
    assert fids(result) == [fs1.id, fs2.id]


def test_oov_tf_35__po_totals_add_exactly(db, st, mk):
    """OOV-TF-35 — two PO totals 0.10 + 0.20 add up exactly to 0.30.
    Rules: _build_top_factories R2, _accumulate_factory R2; HR-15 exactness."""
    mk.po("PO-1", total_amount=Decimal("0.10"))
    mk.po("PO-2", total_amount=Decimal("0.20"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).total_value == Decimal("0.30")
    # Then 3
    assert str(frow(result, st.f1).total_value) == "0.30"


def test_oov_tf_36__unresolved_destination_source_machine_decides(db, st, mk):
    """OOV-TF-36 — with the destination unresolved a source machine decides.
    Rules: _build_top_factories R3, _factory_from_location R2."""
    mk.to("TO-1", source_location_type="machine", source_location_id=st.m2.id,
          destination_location_type="machine", destination_location_id=MISSING)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).order_count == 1
    assert frow(result, st.f2).transfer_count == 1

# =========================================================================== #
# get_stats — limit, workspace, session
# =========================================================================== #

def test_oov_gs_01__empty_workspace_five_empty_lists(db, st):
    """OOV-GS-01 — an empty workspace gives five empty lists.
    Rules: get_stats Returns, _build_top_factories R8."""
    result = stats(db, st)
    # Then 1
    assert isinstance(result, OrdersOverviewStatsResponse)
    # Then 2
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 3
    assert result.top_expense_categories == []
    assert result.top_factories == []


def test_oov_gs_02__limit_zero_acts_as_one(db, st, mk):
    """OOV-GS-02 — limit 0 acts as 1 in every list.
    Rules: get_stats R1, R21."""
    p1 = mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("50.00"))
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("50.00"))
    p2 = mk.po("PO-2", account_id=st.ac2.id, destination_id=st.f2.id, total_amount=Decimal("30.00"))
    mk.pol(p2, st.i2, Decimal("3.00"), Decimal("30.00"))
    mk.so("SO-1", total_amount=Decimal("20.00"))
    mk.so("SO-2", account_id=st.ac2.id, total_amount=Decimal("10.00"))
    mk.eo("EX-1", expense_category="factory", total_amount=Decimal("9.00"))
    mk.eo("EX-2", total_amount=Decimal("4.00"))
    result = stats(db, st, limit=0)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert vendor_ids(result) == [st.ac1.id]
    # Then 3
    assert customer_ids(result) == [st.ac1.id]
    # Then 4
    assert cats(result) == ["factory"]
    # Then 5
    assert fids(result) == [st.f1.id]


def test_oov_gs_03__limit_one_gives_one_row(db, st, mk):
    """OOV-GS-03 — limit 1 gives one row.
    Rules: get_stats R1."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("5.00"))
    mk.pol(p1, st.i2, Decimal("3.00"), Decimal("3.00"), line_number=2)
    result = stats(db, st, limit=1)
    # Then 1
    assert item_ids(result) == [st.i1.id]


def _parts(db, st, mk, n):
    """Items IT1 … ITn ("Part k") on one PO, line k with quantity k."""
    its = [_add(db, Item(workspace_id=st.w1.id, name=f"Part {k}", name_normalized=f"part {k}", unit="pcs"))
           for k in range(1, n + 1)]
    p1 = mk.po("PO-1")
    for k, it in enumerate(its, start=1):
        mk.pol(p1, it, Decimal(k), Decimal("1.00"), line_number=k)
    return its


def test_oov_gs_04__limit_eleven_acts_as_ten(db, st, mk):
    """OOV-GS-04 — limit 11 acts as 10.
    Rules: get_stats R1."""
    its = _parts(db, st, mk, 11)
    result = stats(db, st, limit=11)
    # Then 1
    assert len(result.top_items) == 10
    # Then 2
    assert its[0].id not in item_ids(result)
    # Then 3
    assert item_ids(result)[0] == its[10].id


def test_oov_gs_05__limit_ten_with_eleven_candidates(db, st, mk):
    """OOV-GS-05 — limit 10 with 11 candidates gives 10.
    Rules: get_stats R1."""
    its = _parts(db, st, mk, 11)
    result = stats(db, st, limit=10)
    # Then 1
    assert len(result.top_items) == 10
    # Then 2
    assert its[0].id not in item_ids(result)


def test_oov_gs_06__default_limit_is_five(db, st, mk):
    """OOV-GS-06 — the default limit is 5.
    Rules: get_stats Inputs (limit=5), R1."""
    its = _parts(db, st, mk, 6)
    result = svc.get_stats(db, workspace_id=st.w1.id, from_date=START, to_date=END)
    # Then 1
    assert item_ids(result) == [its[5].id, its[4].id, its[3].id, its[2].id, its[1].id]


def test_oov_gs_07__limit_eleven_for_vendors_and_customers(db, st, mk):
    """OOV-GS-07 — limit 11 acts as 10 for vendors and customers.
    Rules: get_stats R1, R14, R17."""
    accts = [_add(db, Account(workspace_id=st.w1.id, name=f"Firm {k}")) for k in range(1, 12)]
    for k, a in enumerate(accts, start=1):
        mk.po(f"PO-{k}", account_id=a.id, total_amount=Decimal(k))
    for k, a in enumerate(accts, start=1):
        mk.so(f"SO-{k}", account_id=a.id, total_amount=Decimal(k))
    result = stats(db, st, limit=11)
    # Then 1
    assert len(result.top_vendors) == 10
    # Then 2
    assert accts[0].id not in vendor_ids(result)
    # Then 3
    assert len(result.top_customers) == 10
    # Then 4
    assert accts[0].id not in customer_ids(result)


def test_oov_gs_08__from_after_to_five_empty_lists(db, st, mk):
    """OOV-GS-08 — from after to gives five empty lists.
    Rules: get_stats Inputs, R2, _in_date_range R1."""
    p1 = mk.po("PO-1", account_id=st.ac1.id, order_date=START)
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("5.00"))
    mk.so("SO-1", order_date=END)
    mk.eo("EX-1", account_id=st.ac2.id, expense_date=START)
    mk.wo("WO-1", created_at=END_LAST)
    result = stats(db, st, from_date=END, to_date=START)
    # Then 1
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 2
    assert result.top_expense_categories == []
    assert result.top_factories == []


def test_oov_gs_09__w0_and_w2_orders_in_no_list(db, st, mk):
    """OOV-GS-09 — orders of W0 and W2 count in no list.
    Rules: get_stats R2."""
    pz = mk.po("PO-Z", ws="w0", account_id=st.ac0.id)
    mk.pol(pz, st.i0, Decimal("5.00"), Decimal("5.00"))
    tz = mk.to("TO-Z", ws="w0")
    mk.tol(tz, st.i0, Decimal("5.00"))
    sz = mk.so("SO-Z", ws="w0")
    mk.sol(sz, st.i0, Decimal("5.00"), Decimal("5.00"))
    mk.eo("EX-Z", ws="w0", account_id=st.ac0.id)
    p1 = mk.po("PO-1", account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"))
    mk.so("SO-1")
    mk.eo("EX-1", account_id=st.ac1.id)
    p9 = mk.po("PO-9", ws="w2", account_id=st.ac9.id)
    mk.pol(p9, st.i9, Decimal("5.00"), Decimal("5.00"))
    t9 = mk.to("TO-9", ws="w2")
    mk.tol(t9, st.i9, Decimal("5.00"))
    s9 = mk.so("SO-9", ws="w2")
    mk.sol(s9, st.i9, Decimal("5.00"), Decimal("5.00"))
    mk.eo("EX-9", ws="w2", account_id=st.ac9.id, expense_category="department")
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert vendor_ids(result) == [st.ac1.id]
    # Then 3
    assert customer_ids(result) == [st.ac1.id]
    # Then 4
    assert cats(result) == ["other"]
    # Then 5
    assert fids(result) == [st.f1.id]


def test_oov_gs_10__w2_orders_pointing_at_w1_rows_in_no_list(db, st, mk):
    """OOV-GS-10 — W2 orders that point at W1 rows count in no list.
    Rules: get_stats R2."""
    p9 = mk.po("PO-9", ws="w2", account_id=st.ac1.id, destination_id=st.f1.id)
    mk.pol(p9, st.i1, Decimal("5.00"), Decimal("5.00"))
    t9 = mk.to("TO-9", ws="w2", destination_location_id=st.f1.id)
    mk.tol(t9, st.i2, Decimal("5.00"))
    s9 = mk.so("SO-9", ws="w2", account_id=st.ac1.id, factory_id=st.f1.id)
    mk.sol(s9, st.i3, Decimal("5.00"), Decimal("5.00"))
    mk.eo("EX-9", ws="w2", account_id=st.ac1.id)
    mk.wo("WO-9", ws="w2", factory_id=st.f1.id)
    result = stats(db, st)
    # Then 1
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 2
    assert result.top_expense_categories == []
    assert result.top_factories == []


def test_oov_gs_11__read_neither_commits_nor_rolls_back(db, st, mk):
    """OOV-GS-11 — the read neither commits nor rolls back.
    Rules: get_stats R2 (TC6)."""
    p1 = mk.po("PO-1", account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"))
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0


def test_oov_gs_12__pending_changes_stay_pending(db, st):
    """OOV-GS-12 — pending changes stay pending.
    Rules: get_stats R2 (TC6)."""
    new = Item(workspace_id=st.w1.id, name="Pending", name_normalized="pending", unit="pcs")
    db.add(new)
    st.i1.name = "Bolt Edited"
    result = stats(db, st)
    # Then 1
    assert result.top_items == []
    # Then 2
    assert new in db.new
    assert len(db.new) == 1
    # Then 3
    assert st.i1 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert st.i1.name == "Bolt Edited"


def test_oov_gs_13__database_error_reaches_caller_unchanged(db, st):
    """OOV-GS-13 — a database error reaches the caller unchanged.
    Rules: get_stats R2 (TC6)."""
    e = RuntimeError("boom")
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
        patch.object(db, "query", side_effect=e),
        pytest.raises(RuntimeError) as exc,
    ):
        stats(db, st)
    # Then 1
    assert exc.value is e
    # Then 2
    assert rb.call_count == 0
    assert cm.call_count == 0


def test_oov_gs_14__read_writes_nothing(db, st, mk):
    """OOV-GS-14 — the read writes nothing.
    Rules: get_stats Side effects."""
    p1 = mk.po("PO-1", account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"))
    with recorder(db) as stmts:
        result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert [s for s in stmts if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))] == []
    # Then 3
    assert len(stmts) >= 1


def test_oov_gs_15__lines_scoped_by_order_workspace(db, st, mk):
    """OOV-GS-15 — lines are scoped by their order's workspace, not their own.
    Rules: get_stats R2 (Facts: line workspace_id is never read)."""
    p1 = mk.po("PO-1")
    _add(db, PurchaseOrderItem(workspace_id=st.w2.id, purchase_order_id=p1.id, line_number=1, item_id=st.i1.id,
                               quantity_ordered=Decimal("4.00"), line_subtotal=Decimal("4.00")))
    t1 = mk.to("TO-1")
    _add(db, TransferOrderItem(workspace_id=st.w0.id, transfer_order_id=t1.id, line_number=1, item_id=st.i1.id,
                               quantity=Decimal("2.00")))
    p9 = mk.po("PO-9", ws="w2")
    _add(db, PurchaseOrderItem(workspace_id=st.w1.id, purchase_order_id=p9.id, line_number=1, item_id=st.i2.id,
                               quantity_ordered=Decimal("9.00"), line_subtotal=Decimal("9.00")))
    t0 = mk.to("TO-0", ws="w0")
    _add(db, TransferOrderItem(workspace_id=st.w1.id, transfer_order_id=t0.id, line_number=1, item_id=st.i3.id,
                               quantity=Decimal("7.00")))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).purchase_qty == Decimal("4.00")
    assert irow(result, st.i1).transfer_qty == Decimal("2.00")
    assert irow(result, st.i1).line_count == 2


# =========================================================================== #
# get_stats — top items
# =========================================================================== #

def test_oov_ti_01__one_po_line_fills_every_field(db, st, mk):
    """OOV-TI-01 — one PO line fills every field of the item row.
    Rules: get_stats R3, R4, R8."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("50.00"), Decimal("1234.56"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).item_name == "Bolt"
    assert irow(result, st.i1).item_unit == "pcs"
    assert irow(result, st.i1).line_count == 1
    # Then 3
    assert irow(result, st.i1).total_quantity == Decimal("50.00")
    assert irow(result, st.i1).purchase_qty == Decimal("50.00")
    # Then 4
    assert str(irow(result, st.i1).purchase_qty) == "50.00"
    # Then 5
    assert irow(result, st.i1).transfer_qty == Decimal("0")
    assert irow(result, st.i1).sales_qty == Decimal("0")
    # Then 6
    assert str(irow(result, st.i1).transfer_qty) == "0"
    # Then 7
    assert irow(result, st.i1).total_spend == Decimal("1234.56")
    # Then 8
    assert str(irow(result, st.i1).total_spend) == "1234.56"


def test_oov_ti_02__lines_on_two_pos_add_up(db, st, mk):
    """OOV-TI-02 — lines of one item on two POs add up exactly.
    Rules: get_stats R4, R6."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("10.00"), Decimal("0.05"))
    p2 = mk.po("PO-2", destination_id=st.f2.id)
    mk.pol(p2, st.i1, Decimal("5.50"), Decimal("1234.56"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_quantity == Decimal("15.50")
    assert irow(result, st.i1).purchase_qty == Decimal("15.50")
    # Then 3
    assert irow(result, st.i1).total_spend == Decimal("1234.61")
    # Then 4
    assert str(irow(result, st.i1).total_spend) == "1234.61"
    # Then 5
    assert irow(result, st.i1).line_count == 2


def test_oov_ti_03__line_with_no_subtotal_adds_no_spend(db, st, mk):
    """OOV-TI-03 — a line with no subtotal adds no spend.
    Rules: get_stats R4."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("3.00"), None)
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("2.00"), line_number=2)
    p2 = mk.po("PO-2")
    mk.pol(p2, st.i2, Decimal("1.00"), None)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id, st.i2.id]
    # Then 2
    assert irow(result, st.i1).total_spend == Decimal("2.00")
    assert irow(result, st.i1).line_count == 2
    # Then 3
    assert irow(result, st.i2).total_spend == Decimal("0")
    assert irow(result, st.i2).line_count == 1


def test_oov_ti_04__transfer_line_adds_quantity_no_spend(db, st, mk):
    """OOV-TI-04 — a transfer line adds quantity but no spend.
    Rules: get_stats R3, R6."""
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i1, Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).transfer_qty == Decimal("7.00")
    assert irow(result, st.i1).total_quantity == Decimal("7.00")
    # Then 3
    assert irow(result, st.i1).purchase_qty == Decimal("0")
    assert irow(result, st.i1).sales_qty == Decimal("0")
    # Then 4
    assert irow(result, st.i1).total_spend == Decimal("0")
    assert irow(result, st.i1).line_count == 1


def test_oov_ti_05__sales_line_adds_quantity_free_text_not_counted(db, st, mk):
    """OOV-TI-05 — a sales line adds quantity; a free-text line is not counted.
    Rules: get_stats R3, R6."""
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("3.00"), Decimal("300.00"))
    _add(db, SalesOrderItem(workspace_id=st.w1.id, sales_order_id=s1.id, item_id=None, description="Line",
                            quantity_ordered=Decimal("9.00"), unit_price=Decimal("1.00"),
                            line_total=Decimal("900.00")))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).sales_qty == Decimal("3.00")
    assert irow(result, st.i1).total_quantity == Decimal("3.00")
    # Then 3
    assert irow(result, st.i1).purchase_qty == Decimal("0")
    assert irow(result, st.i1).transfer_qty == Decimal("0")
    # Then 4
    assert irow(result, st.i1).line_count == 1


def test_oov_ti_06__empty_item_name_falls_back_with_unit(db, st, mk):
    """OOV-TI-06 — an item with an empty name is "Item #id", with its unit.
    Rules: get_stats R8."""
    ie = _add(db, Item(workspace_id=st.w1.id, name="", name_normalized="", unit="kg"))
    p1 = mk.po("PO-1")
    mk.pol(p1, ie, Decimal("1.00"), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [ie.id]
    # Then 2
    assert irow(result, ie).item_name == f"Item #{ie.id}"
    assert irow(result, ie).item_unit == "kg"


def test_oov_ti_07__items_sorted_by_quantity_then_spend(db, st, mk):
    """OOV-TI-07 — items sorted by quantity, then spend, both descending.
    Rules: get_stats R9."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("10.00"), Decimal("5.00"))
    mk.pol(p1, st.i2, Decimal("20.00"), Decimal("1.00"), line_number=2)
    mk.pol(p1, st.i3, Decimal("10.00"), Decimal("9.00"), line_number=3)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i2.id, st.i3.id, st.i1.id]


def test_oov_ti_08__items_cut_to_limit_after_sorting(db, st, mk):
    """OOV-TI-08 — items cut to limit after sorting.
    Rules: get_stats R9."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"))
    mk.pol(p1, st.i2, Decimal("3.00"), Decimal("1.00"), line_number=2)
    mk.pol(p1, st.i3, Decimal("2.00"), Decimal("1.00"), line_number=3)
    result = stats(db, st, limit=2)
    # Then 1
    assert item_ids(result) == [st.i2.id, st.i3.id]


def test_oov_ti_09__po_lines_report_days_at_both_edges(db, st, mk):
    """OOV-TI-09 — PO lines: report days at both edges, with and without order_date.
    Rules: get_stats R2, R4, _po_report_date R1."""
    for number, q, kw in (
        ("PO-A", "1.00", {"order_date": PRE}),
        ("PO-B", "10.00", {"order_date": START}),
        ("PO-C", "100.00", {"order_date": END}),
        ("PO-D", "1000.00", {"order_date": POST}),
        ("PO-E", "10000.00", {"order_date": None, "created_at": END_LAST}),
        ("PO-F", "100000.00", {"order_date": None, "created_at": PRE_LAST}),
        ("PO-G", "1000000.00", {"order_date": None, "created_at": POST_0}),
    ):
        p = mk.po(number, **kw)
        mk.pol(p, st.i1, Decimal(q), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert irow(result, st.i1).purchase_qty == Decimal("10110.00")
    assert irow(result, st.i1).line_count == 3


def test_oov_ti_10__transfer_lines_days_at_both_edges(db, st, mk):
    """OOV-TI-10 — transfer lines: created_at days at both edges.
    Rules: get_stats R2, R6."""
    for number, q, at in (("TO-A", "1.00", PRE_LAST), ("TO-B", "10.00", START_0),
                          ("TO-C", "100.00", END_LAST), ("TO-D", "1000.00", POST_0)):
        t = mk.to(number, created_at=at)
        mk.tol(t, st.i1, Decimal(q))
    result = stats(db, st)
    # Then 1
    assert irow(result, st.i1).transfer_qty == Decimal("110.00")
    assert irow(result, st.i1).line_count == 2


def test_oov_ti_11__sales_lines_days_at_both_edges(db, st, mk):
    """OOV-TI-11 — sales lines: order days at both edges.
    Rules: get_stats R2, R6."""
    for number, q, d in (("SO-A", "1.00", PRE), ("SO-B", "10.00", START),
                         ("SO-C", "100.00", END), ("SO-D", "1000.00", POST)):
        s = mk.so(number, order_date=d)
        mk.sol(s, st.i1, Decimal(q), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert irow(result, st.i1).sales_qty == Decimal("110.00")
    assert irow(result, st.i1).line_count == 2


@bug(2500)
def test_oov_ti_12__lines_of_voided_po_count_nowhere(db, st, mk):
    """OOV-TI-12 — lines of a voided PO count nowhere.
    Rules: get_stats R4a [BUG-2500]."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("10.00"))
    p2 = mk.po("PO-2", **mk.voided)
    mk.pol(p2, st.i1, Decimal("50.00"), Decimal("1000.00"))
    p3 = mk.po("PO-3", **mk.voided)
    mk.pol(p3, st.i2, Decimal("9.00"), Decimal("9.00"))
    result = stats(db, st)
    # Then 1
    assert st.i1.id in item_ids(result)
    # Then 2
    assert irow(result, st.i1).purchase_qty == Decimal("5.00")
    assert irow(result, st.i1).total_spend == Decimal("10.00")
    assert irow(result, st.i1).line_count == 1
    # Then 3
    assert item_ids(result) == [st.i1.id]


@bug(2504)
def test_oov_ti_13__po_line_of_other_workspace_item_left_out(db, st, mk):
    """OOV-TI-13 — a PO line of another workspace's item is left out.
    Rules: get_stats R6a [BUG-2504]."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i0, Decimal("5.00"), Decimal("5.00"))
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"), line_number=2)
    mk.pol(p1, st.i9, Decimal("7.00"), Decimal("7.00"), line_number=3)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]


@bug(2504)
def test_oov_ti_14__transfer_line_of_other_workspace_item_left_out(db, st, mk):
    """OOV-TI-14 — a transfer line of another workspace's item is left out.
    Rules: get_stats R6a [BUG-2504]."""
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i0, Decimal("5.00"))
    mk.tol(t1, st.i1, Decimal("1.00"), line_number=2)
    mk.tol(t1, st.i9, Decimal("7.00"), line_number=3)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]


@bug(2504)
def test_oov_ti_15__sales_line_of_other_workspace_item_left_out(db, st, mk):
    """OOV-TI-15 — a sales line of another workspace's item is left out.
    Rules: get_stats R6a [BUG-2504]."""
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i0, Decimal("5.00"), Decimal("5.00"))
    mk.sol(s1, st.i1, Decimal("1.00"), Decimal("1.00"))
    mk.sol(s1, st.i9, Decimal("7.00"), Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]


@bug(2505)
def test_oov_ti_16__tied_items_by_name_before_cut(db, st, mk):
    """OOV-TI-16 — tied items are ordered by name case-insensitive before the cut.
    Rules: get_stats R9a [BUG-2505]."""
    iz = _add(db, Item(workspace_id=st.w1.id, name="zeta Rod", name_normalized="zeta rod", unit="pcs"))
    ib = _add(db, Item(workspace_id=st.w1.id, name="Beta Rod", name_normalized="beta rod", unit="pcs"))
    ia = _add(db, Item(workspace_id=st.w1.id, name="alpha Rod", name_normalized="alpha rod", unit="pcs"))
    t1 = mk.to("TO-1")
    mk.tol(t1, iz, Decimal("5.00"))
    mk.tol(t1, ib, Decimal("5.00"), line_number=2)
    s1 = mk.so("SO-1")
    mk.sol(s1, ia, Decimal("5.00"), Decimal("0.00"))
    result = stats(db, st, limit=2)
    # Then 1
    assert len(result.top_items) == 2
    # Then 2
    assert item_ids(result) == [ia.id, ib.id]


@bug(2505)
def test_oov_ti_17__items_tied_on_name_by_id(db, st, mk):
    """OOV-TI-17 — items tied on name case-insensitive are ordered by id.
    Rules: get_stats R9a [BUG-2505]."""
    is1 = _add(db, Item(workspace_id=st.w1.id, name="Same Rod", name_normalized="same rod", unit="pcs"))
    is2 = _add(db, Item(workspace_id=st.w1.id, name="SAME ROD", name_normalized="same rod", unit="pcs"))
    t1 = mk.to("TO-1")
    mk.tol(t1, is2, Decimal("5.00"))
    s1 = mk.so("SO-1")
    mk.sol(s1, is1, Decimal("5.00"), Decimal("0.00"))
    result = stats(db, st)
    # Then 1
    assert sorted(item_ids(result)) == sorted([is1.id, is2.id])
    # Then 2
    assert item_ids(result) == [is1.id, is2.id]


def test_oov_ti_18__transfer_only_item_named_with_unit_empty_falls_back(db, st, mk):
    """OOV-TI-18 — an item seen only on transfer lines is named with its unit; an empty name falls back.
    Rules: get_stats R6, R8."""
    ie = _add(db, Item(workspace_id=st.w1.id, name="", name_normalized="", unit="box"))
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i2, Decimal("3.00"))
    t2 = mk.to("TO-2")
    mk.tol(t2, ie, Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert sorted(item_ids(result)) == sorted([st.i2.id, ie.id])
    # Then 2
    assert irow(result, st.i2).item_name == "Nut"
    assert irow(result, st.i2).item_unit == "pcs"
    # Then 3
    assert irow(result, ie).item_name == f"Item #{ie.id}"
    assert irow(result, ie).item_unit == "box"
    # Then 4
    assert irow(result, st.i2).transfer_qty == Decimal("3.00")


def test_oov_ti_19__sales_only_item_named_with_unit_empty_falls_back(db, st, mk):
    """OOV-TI-19 — an item seen only on sales lines is named with its unit; an empty name falls back.
    Rules: get_stats R6, R8."""
    is_ = _add(db, Item(workspace_id=st.w1.id, name="", name_normalized="", unit="kg"))
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i3, Decimal("2.00"), Decimal("8.00"))
    s2 = mk.so("SO-2")
    mk.sol(s2, is_, Decimal("1.00"), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert sorted(item_ids(result)) == sorted([st.i3.id, is_.id])
    # Then 2
    assert irow(result, st.i3).item_name == "Washer"
    assert irow(result, st.i3).item_unit == "pcs"
    # Then 3
    assert irow(result, is_).item_name == f"Item #{is_.id}"
    assert irow(result, is_).item_unit == "kg"
    # Then 4
    assert irow(result, st.i3).sales_qty == Decimal("2.00")


def test_oov_ti_20__empty_unit_is_none_on_every_line_kind(db, st, mk):
    """OOV-TI-20 — an empty unit is shown as no unit, on every line kind.
    Rules: get_stats R8c."""
    ip = _add(db, Item(workspace_id=st.w1.id, name="Pipe", name_normalized="pipe", unit=""))
    it = _add(db, Item(workspace_id=st.w1.id, name="Tape", name_normalized="tape", unit=""))
    iq = _add(db, Item(workspace_id=st.w1.id, name="Quill", name_normalized="quill", unit=""))
    p1 = mk.po("PO-1")
    mk.pol(p1, ip, Decimal("1.00"), Decimal("1.00"))
    t1 = mk.to("TO-1")
    mk.tol(t1, it, Decimal("1.00"))
    s1 = mk.so("SO-1")
    mk.sol(s1, iq, Decimal("1.00"), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert sorted(item_ids(result)) == sorted([ip.id, it.id, iq.id])
    # Then 2
    assert irow(result, ip).item_unit is None
    assert irow(result, ip).item_name == "Pipe"
    # Then 3
    assert irow(result, it).item_unit is None
    assert irow(result, it).item_name == "Tape"
    # Then 4
    assert irow(result, iq).item_unit is None
    assert irow(result, iq).item_name == "Quill"


def test_oov_ti_21__po_line_subtotals_add_exactly(db, st, mk):
    """OOV-TI-21 — PO line subtotals 0.10 + 0.20 add up exactly to 0.30.
    Rules: get_stats R4; HR-15 exactness."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("0.10"))
    p2 = mk.po("PO-2")
    mk.pol(p2, st.i1, Decimal("1.00"), Decimal("0.20"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_spend == Decimal("0.30")
    # Then 3
    assert str(irow(result, st.i1).total_spend) == "0.30"

# =========================================================================== #
# get_stats — top vendors
# =========================================================================== #

def test_oov_tv_01__po_with_account_makes_vendor_row(db, st, mk):
    """OOV-TV-01 — a PO with an account makes a vendor row.
    Rules: get_stats R10, R13."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("1234.56"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).account_name == "Acme"
    assert vrow(result, st.ac1).order_count == 1
    # Then 3
    assert vrow(result, st.ac1).total_spend == Decimal("1234.56")
    # Then 4
    assert str(vrow(result, st.ac1).total_spend) == "1234.56"


def test_oov_tv_02__pos_and_expenses_of_one_account_one_row(db, st, mk):
    """OOV-TV-02 — POs and expense orders of one account make one row.
    Rules: get_stats R10."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("100.00"))
    mk.eo("EX-1", account_id=st.ac1.id, total_amount=Decimal("0.05"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("100.05")
    assert vrow(result, st.ac1).order_count == 2
    # Then 3
    assert str(vrow(result, st.ac1).total_spend) == "100.05"


def test_oov_tv_03__orders_without_account_left_out(db, st, mk):
    """OOV-TV-03 — orders without an account are left out.
    Rules: get_stats R10."""
    mk.po("PO-1", total_amount=Decimal("500.00"))
    mk.eo("EX-1", total_amount=Decimal("600.00"))
    mk.po("PO-2", account_id=st.ac2.id, total_amount=Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac2.id]
    # Then 2
    assert vrow(result, st.ac2).total_spend == Decimal("1.00")
    assert vrow(result, st.ac2).order_count == 1


def test_oov_tv_04__empty_name_falls_back_deleted_keeps_name(db, st, mk):
    """OOV-TV-04 — empty name falls back; a deleted account keeps its row and name.
    Rules: get_stats R13."""
    ae = _add(db, Account(workspace_id=st.w1.id, name=""))
    ax = deleted_account(db, st, "Gone Co")
    mk.po("PO-1", account_id=ae.id, total_amount=Decimal("2.00"))
    mk.eo("EX-1", account_id=ax.id, total_amount=Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [ae.id, ax.id]
    # Then 2
    assert vrow(result, ae).account_name == f"Account #{ae.id}"
    # Then 3
    assert vrow(result, ax).account_name == "Gone Co"


def test_oov_tv_05__vendors_sorted_by_spend_and_cut(db, st, mk):
    """OOV-TV-05 — vendors sorted by spend descending and cut to limit.
    Rules: get_stats R14."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("10.00"))
    mk.po("PO-2", account_id=st.ac2.id, total_amount=Decimal("30.00"))
    mk.eo("EX-3", account_id=st.ac3.id, total_amount=Decimal("20.00"))
    result = stats(db, st, limit=2)
    # Then 1
    assert vendor_ids(result) == [st.ac2.id, st.ac3.id]


def test_oov_tv_06__po_vendor_report_days_at_both_edges(db, st, mk):
    """OOV-TV-06 — PO vendors: report days at both edges, with and without order_date.
    Rules: get_stats R2, R10."""
    mk.po("PO-A", account_id=st.ac1.id, order_date=PRE, total_amount=Decimal("1.00"))
    mk.po("PO-B", account_id=st.ac1.id, order_date=START, total_amount=Decimal("10.00"))
    mk.po("PO-C", account_id=st.ac1.id, order_date=END, total_amount=Decimal("100.00"))
    mk.po("PO-D", account_id=st.ac1.id, order_date=POST, total_amount=Decimal("1000.00"))
    mk.po("PO-E", account_id=st.ac1.id, order_date=None, created_at=START_0, total_amount=Decimal("10000.00"))
    mk.po("PO-F", account_id=st.ac1.id, order_date=None, created_at=PRE_LAST, total_amount=Decimal("100000.00"))
    result = stats(db, st)
    # Then 1
    assert vrow(result, st.ac1).total_spend == Decimal("10110.00")
    assert vrow(result, st.ac1).order_count == 3


def test_oov_tv_07__expense_vendor_days_at_both_edges(db, st, mk):
    """OOV-TV-07 — expense vendors: expense days at both edges.
    Rules: get_stats R2, R10."""
    mk.eo("EX-A", account_id=st.ac1.id, expense_date=PRE, total_amount=Decimal("1.00"))
    mk.eo("EX-B", account_id=st.ac1.id, expense_date=START, total_amount=Decimal("10.00"))
    mk.eo("EX-C", account_id=st.ac1.id, expense_date=END, total_amount=Decimal("100.00"))
    mk.eo("EX-D", account_id=st.ac1.id, expense_date=POST, total_amount=Decimal("1000.00"))
    result = stats(db, st)
    # Then 1
    assert vrow(result, st.ac1).total_spend == Decimal("110.00")
    assert vrow(result, st.ac1).order_count == 2


@bug(2500)
def test_oov_tv_08__voided_po_in_no_vendor(db, st, mk):
    """OOV-TV-08 — a voided PO counts in no vendor.
    Rules: get_stats R11a [BUG-2500]."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("10.00"))
    mk.po("PO-2", **mk.voided, account_id=st.ac1.id, total_amount=Decimal("1000.00"))
    mk.po("PO-3", **mk.voided, account_id=st.ac2.id, total_amount=Decimal("5.00"))
    result = stats(db, st)
    # Then 1
    assert st.ac1.id in vendor_ids(result)
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")
    assert vrow(result, st.ac1).order_count == 1
    # Then 3
    assert vendor_ids(result) == [st.ac1.id]


@bug(2500)
def test_oov_tv_09__voided_expense_in_no_vendor(db, st, mk):
    """OOV-TV-09 — a voided expense order counts in no vendor.
    Rules: get_stats R11a [BUG-2500]."""
    mk.eo("EX-1", account_id=st.ac1.id, total_amount=Decimal("10.00"))
    mk.eo("EX-2", **mk.voided, account_id=st.ac1.id, total_amount=Decimal("300.00"))
    mk.eo("EX-3", **mk.voided, account_id=st.ac2.id, total_amount=Decimal("5.00"))
    result = stats(db, st)
    # Then 1
    assert st.ac1.id in vendor_ids(result)
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")
    assert vrow(result, st.ac1).order_count == 1
    # Then 3
    assert vendor_ids(result) == [st.ac1.id]


@bug(2504)
def test_oov_tv_10__po_with_other_workspace_account_left_out(db, st, mk):
    """OOV-TV-10 — a W1 PO with another workspace's account is left out.
    Rules: get_stats R13a [BUG-2504]."""
    mk.po("PO-0", account_id=st.ac0.id, total_amount=Decimal("50.00"))
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("1.00"))
    mk.po("PO-9", account_id=st.ac9.id, total_amount=Decimal("90.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]


@bug(2504)
def test_oov_tv_11__expense_with_other_workspace_account_left_out(db, st, mk):
    """OOV-TV-11 — a W1 expense order with another workspace's account is left out.
    Rules: get_stats R13a [BUG-2504]."""
    mk.eo("EX-0", account_id=st.ac0.id, total_amount=Decimal("50.00"))
    mk.eo("EX-1", account_id=st.ac1.id, total_amount=Decimal("1.00"))
    mk.eo("EX-9", account_id=st.ac9.id, total_amount=Decimal("90.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]


@bug(2505)
def test_oov_tv_12__tied_vendors_by_name_before_cut(db, st, mk):
    """OOV-TV-12 — tied vendors are ordered by name case-insensitive before the cut.
    Rules: get_stats R14a [BUG-2505]."""
    az = _add(db, Account(workspace_id=st.w1.id, name="zeta Supply"))
    ab = _add(db, Account(workspace_id=st.w1.id, name="Beta Supply"))
    aa = _add(db, Account(workspace_id=st.w1.id, name="alpha Supply"))
    mk.po("PO-Z", account_id=az.id)
    mk.po("PO-B", account_id=ab.id)
    mk.eo("EX-A", account_id=aa.id)
    result = stats(db, st, limit=2)
    # Then 1
    assert len(result.top_vendors) == 2
    # Then 2
    assert vendor_ids(result) == [aa.id, ab.id]


@bug(2505)
def test_oov_tv_13__vendors_tied_on_name_by_id(db, st, mk):
    """OOV-TV-13 — vendors tied on name case-insensitive are ordered by id.
    Rules: get_stats R14a [BUG-2505]."""
    as1 = _add(db, Account(workspace_id=st.w1.id, name="Same Supply"))
    as2 = _add(db, Account(workspace_id=st.w1.id, name="SAME SUPPLY"))
    mk.po("PO-S", account_id=as2.id)
    mk.eo("EX-S", account_id=as1.id)
    result = stats(db, st)
    # Then 1
    assert sorted(vendor_ids(result)) == sorted([as1.id, as2.id])
    # Then 2
    assert vendor_ids(result) == [as1.id, as2.id]


def test_oov_tv_14__sales_orders_never_in_top_vendors(db, st, mk):
    """OOV-TV-14 — sales orders never count in top vendors.
    Rules: get_stats R10."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("10.00"))
    mk.so("SO-1", total_amount=Decimal("50.00"))
    mk.so("SO-2", account_id=st.ac3.id, total_amount=Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")
    assert vrow(result, st.ac1).order_count == 1


def test_oov_tv_15__deleted_account_keeps_po_vendor_row_and_name(db, st, mk):
    """OOV-TV-15 — a deleted account keeps its PO vendor row and name.
    Rules: get_stats R13."""
    ax = deleted_account(db, st, "Gone Co")
    mk.po("PO-1", account_id=ax.id, total_amount=Decimal("3.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [ax.id]
    # Then 2
    assert vrow(result, ax).account_name == "Gone Co"
    assert vrow(result, ax).total_spend == Decimal("3.00")


def test_oov_tv_16__expense_only_vendor_empty_name_falls_back(db, st, mk):
    """OOV-TV-16 — an expense-only vendor with an empty name falls back to Account #id.
    Rules: get_stats R10, R13."""
    ae = _add(db, Account(workspace_id=st.w1.id, name=""))
    mk.eo("EX-1", account_id=ae.id, total_amount=Decimal("4.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [ae.id]
    # Then 2
    assert vrow(result, ae).account_name == f"Account #{ae.id}"
    assert vrow(result, ae).order_count == 1


def test_oov_tv_17__po_and_expense_totals_add_exactly(db, st, mk):
    """OOV-TV-17 — PO and expense totals 0.10 + 0.20 add up exactly to 0.30.
    Rules: get_stats R10; HR-15 exactness."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("0.10"))
    mk.eo("EX-1", account_id=st.ac1.id, total_amount=Decimal("0.20"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("0.30")
    # Then 3
    assert str(vrow(result, st.ac1).total_spend) == "0.30"

# =========================================================================== #
# get_stats — top customers
# =========================================================================== #

def test_oov_tc_01__sales_grouped_by_account_exact(db, st, mk):
    """OOV-TC-01 — sales orders grouped by account with exact sums and counts.
    Rules: get_stats R16, R17."""
    mk.so("SO-1", total_amount=Decimal("1234.56"))
    mk.so("SO-2", total_amount=Decimal("0.05"))
    mk.so("SO-3", account_id=st.ac2.id, total_amount=Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id, st.ac2.id]
    # Then 2
    assert crow(result, st.ac1).account_name == "Acme"
    assert crow(result, st.ac1).order_count == 2
    # Then 3
    assert crow(result, st.ac1).total_spend == Decimal("1234.61")
    # Then 4
    assert str(crow(result, st.ac1).total_spend) == "1234.61"
    # Then 5
    assert crow(result, st.ac2).account_name == "Beta"
    assert crow(result, st.ac2).order_count == 1
    assert crow(result, st.ac2).total_spend == Decimal("7.00")


def test_oov_tc_02__empty_customer_name_falls_back_deleted_kept(db, st, mk):
    """OOV-TC-02 — empty customer name falls back; a deleted account keeps its row.
    Rules: get_stats R16 (name as R13)."""
    ae = _add(db, Account(workspace_id=st.w1.id, name=""))
    ax = deleted_account(db, st, "Gone Co")
    mk.so("SO-1", account_id=ae.id, total_amount=Decimal("2.00"))
    mk.so("SO-2", account_id=ax.id, total_amount=Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [ae.id, ax.id]
    # Then 2
    assert crow(result, ae).account_name == f"Account #{ae.id}"
    # Then 3
    assert crow(result, ax).account_name == "Gone Co"


def test_oov_tc_03__customers_sorted_and_cut(db, st, mk):
    """OOV-TC-03 — customers sorted by total descending and cut to limit.
    Rules: get_stats R17."""
    mk.so("SO-1", total_amount=Decimal("10.00"))
    mk.so("SO-2", account_id=st.ac2.id, total_amount=Decimal("30.00"))
    mk.so("SO-3", account_id=st.ac3.id, total_amount=Decimal("20.00"))
    result = stats(db, st, limit=2)
    # Then 1
    assert customer_ids(result) == [st.ac2.id, st.ac3.id]


def test_oov_tc_04__sales_days_at_both_edges(db, st, mk):
    """OOV-TC-04 — sales days at both edges.
    Rules: get_stats R2, R16."""
    mk.so("SO-A", order_date=PRE, total_amount=Decimal("1.00"))
    mk.so("SO-B", order_date=START, total_amount=Decimal("10.00"))
    mk.so("SO-C", order_date=END, total_amount=Decimal("100.00"))
    mk.so("SO-D", order_date=POST, total_amount=Decimal("1000.00"))
    result = stats(db, st)
    # Then 1
    assert crow(result, st.ac1).total_spend == Decimal("110.00")
    assert crow(result, st.ac1).order_count == 2


@bug(2504)
def test_oov_tc_05__sales_with_other_workspace_account_left_out(db, st, mk):
    """OOV-TC-05 — a W1 sales order with another workspace's account is left out.
    Rules: get_stats R16 [BUG-2504]."""
    mk.so("SO-0", account_id=st.ac0.id, total_amount=Decimal("50.00"))
    mk.so("SO-1", total_amount=Decimal("1.00"))
    mk.so("SO-9", account_id=st.ac9.id, total_amount=Decimal("90.00"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]


@bug(2505, strict=False)
def test_oov_tc_06__tied_customers_by_name_then_id(db, st, mk):
    """OOV-TC-06 — tied customers are ordered by name case-insensitive, then id.
    Rules: get_stats R17a [BUG-2505]."""
    az = _add(db, Account(workspace_id=st.w1.id, name="zeta Buyer"))
    ab = _add(db, Account(workspace_id=st.w1.id, name="Beta Buyer"))
    aa = _add(db, Account(workspace_id=st.w1.id, name="alpha Buyer"))
    mk.so("SO-Z", account_id=az.id)
    mk.so("SO-B", account_id=ab.id)
    mk.so("SO-A", account_id=aa.id)
    result = stats(db, st, limit=2)
    # Then 1
    assert customer_ids(result) == [aa.id, ab.id]


@bug(2505)
def test_oov_tc_07__customers_sql_cut_orders_by_name_and_id(db, st, mk):
    """OOV-TC-07 — the customers' SQL cut orders by name and id after the total.
    Rules: get_stats R17, R17a [BUG-2505]."""
    mk.so("SO-1", total_amount=Decimal("10.00"))
    with recorder(db) as stmts:
        result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]
    # Then 2
    cs = [s for s in stmts if "sales_orders" in s and "GROUP BY" in s and "LIMIT" in s]
    assert len(cs) == 1
    # Then 3
    assert "name" in order_part(cs[0])
    # Then 4
    assert "accounts.id" in order_part(cs[0]) or "account_id" in order_part(cs[0])


def test_oov_tc_08__sales_totals_add_exactly(db, st, mk):
    """OOV-TC-08 — sales totals 0.10 + 0.20 add up exactly to 0.30.
    Rules: get_stats R16; HR-15 exactness."""
    mk.so("SO-1", total_amount=Decimal("0.10"))
    mk.so("SO-2", total_amount=Decimal("0.20"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]
    # Then 2
    assert crow(result, st.ac1).total_spend == Decimal("0.30")
    # Then 3
    assert str(crow(result, st.ac1).total_spend) == "0.30"

# =========================================================================== #
# get_stats — top expense categories
# =========================================================================== #

def test_oov_te_01__expenses_grouped_by_category(db, st, mk):
    """OOV-TE-01 — expense orders grouped by category, with or without an account.
    Rules: get_stats R19."""
    mk.eo("EX-1", expense_category="factory", total_amount=Decimal("1234.56"))
    mk.eo("EX-2", expense_category="factory", account_id=st.ac1.id, total_amount=Decimal("0.05"))
    mk.eo("EX-3", total_amount=Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert cats(result) == ["factory", "other"]
    # Then 2
    assert result.top_expense_categories[0].total_spend == Decimal("1234.61")
    assert result.top_expense_categories[0].order_count == 2
    # Then 3
    assert str(result.top_expense_categories[0].total_spend) == "1234.61"
    # Then 4
    assert result.top_expense_categories[1].total_spend == Decimal("7.00")
    assert result.top_expense_categories[1].order_count == 1


def test_oov_te_02__categories_sorted_and_cut(db, st, mk):
    """OOV-TE-02 — categories sorted by total descending and cut to limit.
    Rules: get_stats R19."""
    mk.eo("EX-1", expense_category="department", total_amount=Decimal("10.00"))
    mk.eo("EX-2", expense_category="factory", total_amount=Decimal("30.00"))
    mk.eo("EX-3", total_amount=Decimal("20.00"))
    result = stats(db, st, limit=2)
    # Then 1
    assert cats(result) == ["factory", "other"]


def test_oov_te_03__expense_days_at_both_edges(db, st, mk):
    """OOV-TE-03 — expense days at both edges.
    Rules: get_stats R2, R19."""
    mk.eo("EX-A", expense_date=PRE, total_amount=Decimal("1.00"))
    mk.eo("EX-B", expense_date=START, total_amount=Decimal("10.00"))
    mk.eo("EX-C", expense_date=END, total_amount=Decimal("100.00"))
    mk.eo("EX-D", expense_date=POST, total_amount=Decimal("1000.00"))
    result = stats(db, st)
    # Then 1
    assert cats(result) == ["other"]
    # Then 2
    assert result.top_expense_categories[0].total_spend == Decimal("110.00")
    assert result.top_expense_categories[0].order_count == 2


@bug(2500)
def test_oov_te_04__voided_expense_in_no_category(db, st, mk):
    """OOV-TE-04 — a voided expense order counts in no category.
    Rules: get_stats R19, R11a [BUG-2500]."""
    mk.eo("EX-1", total_amount=Decimal("10.00"))
    mk.eo("EX-2", **mk.voided, total_amount=Decimal("300.00"))
    mk.eo("EX-3", **mk.voided, expense_category="factory", total_amount=Decimal("5.00"))
    result = stats(db, st)
    # Then 1
    assert "other" in cats(result)
    # Then 2
    assert result.top_expense_categories[cats(result).index("other")].total_spend == Decimal("10.00")
    assert result.top_expense_categories[cats(result).index("other")].order_count == 1
    # Then 3
    assert cats(result) == ["other"]


@bug(2505, strict=False)
def test_oov_te_05__tied_categories_by_text(db, st, mk):
    """OOV-TE-05 — tied categories are ordered by category text.
    Rules: get_stats R19a [BUG-2505]."""
    mk.eo("EX-1", total_amount=Decimal("5.00"))
    mk.eo("EX-2", expense_category="factory", total_amount=Decimal("5.00"))
    mk.eo("EX-3", expense_category="department", total_amount=Decimal("5.00"))
    result = stats(db, st, limit=2)
    # Then 1
    assert cats(result) == ["department", "factory"]


@bug(2505)
def test_oov_te_06__categories_sql_cut_orders_by_category(db, st, mk):
    """OOV-TE-06 — the categories' SQL cut orders by category text after the total.
    Rules: get_stats R19, R19a [BUG-2505]."""
    mk.eo("EX-1")
    with recorder(db) as stmts:
        result = stats(db, st)
    # Then 1
    assert cats(result) == ["other"]
    # Then 2
    es = [s for s in stmts if "expense_orders" in s and "GROUP BY" in s and "LIMIT" in s
          and "expense_category" in s.split("GROUP BY")[-1]]
    assert len(es) == 1
    # Then 3
    assert "expense_category" in order_part(es[0])


# =========================================================================== #
# get_stats — factory view (factory_id)
# =========================================================================== #

@BUG_2502
def test_oov_fv_01__po_and_sales_lines_kept_for_factory(db, st, mk):
    """OOV-FV-01 — PO and sales lines are kept only for the factory.
    Rules: get_stats R5 [BUG-2502]."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("5.00"))
    p2 = mk.po("PO-2", destination_id=st.f2.id)
    mk.pol(p2, st.i2, Decimal("7.00"), Decimal("7.00"))
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i3, Decimal("2.00"), Decimal("2.00"))
    iv = _add(db, Item(workspace_id=st.w1.id, name="Valve", name_normalized="valve", unit="pcs"))
    s2 = mk.so("SO-2", factory_id=st.f2.id)
    mk.sol(s2, iv, Decimal("9.00"), Decimal("9.00"))
    result = stats(db, st, factory_id=st.f1.id)
    # Then 1
    assert sorted(item_ids(result)) == sorted([st.i1.id, st.i3.id])


@BUG_2502
def test_oov_fv_02__transfer_counts_in_destination_view(db, st, mk):
    """OOV-FV-02 — a transfer between two factories counts in the destination's view.
    Rules: get_stats R12 [BUG-2502]."""
    t1 = mk.to("TO-1", destination_location_type="machine", destination_location_id=st.m1.id)
    mk.tol(t1, st.i1, Decimal("4.00"))
    t2 = mk.to("TO-2", source_location_id=st.fa.id, destination_location_id=st.fa.id)
    mk.tol(t2, st.i2, Decimal("6.00"))
    result = stats(db, st, factory_id=st.f1.id)
    # Then 1
    assert item_ids(result) == [st.i1.id]


@BUG_2502
def test_oov_fv_03__transfer_counts_in_source_view(db, st, mk):
    """OOV-FV-03 — the same transfer counts in the source factory's view.
    Rules: get_stats R12 [BUG-2502]."""
    t1 = mk.to("TO-1", destination_location_type="machine", destination_location_id=st.m1.id)
    mk.tol(t1, st.i1, Decimal("4.00"))
    t2 = mk.to("TO-2", source_location_id=st.fa.id, destination_location_id=st.fa.id)
    mk.tol(t2, st.i2, Decimal("6.00"))
    result = stats(db, st, factory_id=st.f2.id)
    # Then 1
    assert item_ids(result) == [st.i1.id]


@BUG_2502
def test_oov_fv_04__vendors_from_factory_pos_only(db, st, mk):
    """OOV-FV-04 — vendors come from the factory's POs only; expense orders are not read.
    Rules: get_stats R15 [BUG-2502]."""
    mk.po("PO-1", account_id=st.ac1.id, total_amount=Decimal("10.00"))
    mk.po("PO-2", account_id=st.ac2.id, destination_id=st.f2.id, total_amount=Decimal("20.00"))
    mk.eo("EX-1", account_id=st.ac3.id, expense_category="factory", total_amount=Decimal("30.00"))
    mk.eo("EX-2", account_id=st.ac1.id, total_amount=Decimal("40.00"))
    result = stats(db, st, factory_id=st.f1.id)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")
    assert vrow(result, st.ac1).order_count == 1


@BUG_2502
def test_oov_fv_05__customers_filtered_before_cut(db, st, mk):
    """OOV-FV-05 — customers are filtered to the factory before the cut.
    Rules: get_stats R18 [BUG-2502]."""
    mk.so("SO-1", account_id=st.ac2.id, factory_id=st.f2.id, total_amount=Decimal("100.00"))
    mk.so("SO-2", total_amount=Decimal("10.00"))
    result = stats(db, st, factory_id=st.f1.id, limit=1)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]
    # Then 2
    assert crow(result, st.ac1).total_spend == Decimal("10.00")
    assert crow(result, st.ac1).order_count == 1


@BUG_2502
def test_oov_fv_06__categories_and_factories_empty_in_factory_view(db, st, mk):
    """OOV-FV-06 — categories and factories are empty in a factory view.
    Rules: get_stats R20, R21 [BUG-2502]."""
    mk.eo("EX-1", expense_category="factory", total_amount=Decimal("30.00"))
    mk.po("PO-1", total_amount=Decimal("10.00"))
    mk.wo("WO-1")
    result = stats(db, st, factory_id=st.f1.id)
    # Then 1
    assert result.top_expense_categories == []
    # Then 2
    assert result.top_factories == []


@BUG_2502
def test_oov_fv_07__factory_with_no_orders_five_empty_lists(db, st, mk):
    """OOV-FV-07 — a factory with no orders gives five empty lists.
    Rules: get_stats R5, R12, R15, R18, R20, R21 [BUG-2502]; Errors row."""
    p1 = mk.po("PO-1", account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("1.00"), Decimal("1.00"))
    mk.so("SO-1")
    result = stats(db, st, factory_id=st.fa.id)
    # Then 1
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 2
    assert result.top_expense_categories == []
    assert result.top_factories == []


@BUG_2502_2504
def test_oov_fv_08__factory_view_on_w2_factory_shows_nothing(db, st, mk):
    """OOV-FV-08 — a factory view on a W2 factory shows nothing of that workspace.
    Rules: _build_top_factories R8b [BUG-2504]; get_stats R5, R12, R18 [BUG-2502]."""
    p1 = mk.po("PO-1", destination_id=st.f9.id, account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("4.00"), Decimal("4.00"))
    t1 = mk.to("TO-1", destination_location_id=st.f9.id)
    mk.tol(t1, st.i2, Decimal("2.00"))
    s1 = mk.so("SO-1", factory_id=st.f9.id)
    mk.sol(s1, st.i3, Decimal("3.00"), Decimal("3.00"))
    mk.wo("WO-1", factory_id=st.f9.id)
    p2 = mk.po("PO-2", ws="w2", account_id=st.ac9.id)
    mk.pol(p2, st.i9, Decimal("5.00"), Decimal("5.00"))
    s2 = mk.so("SO-2", ws="w2")
    mk.sol(s2, st.i9, Decimal("6.00"), Decimal("6.00"))
    result = stats(db, st, factory_id=st.f9.id)
    # Then 1
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 2
    assert result.top_expense_categories == []
    assert result.top_factories == []


@BUG_2502_2504
def test_oov_fv_09__factory_view_on_w0_factory_shows_nothing(db, st, mk):
    """OOV-FV-09 — a factory view on a W0 factory shows nothing of that workspace.
    Rules: _build_top_factories R8b [BUG-2504]; get_stats R5, R12, R18 [BUG-2502]."""
    p1 = mk.po("PO-1", destination_id=st.f0.id, account_id=st.ac1.id)
    mk.pol(p1, st.i1, Decimal("4.00"), Decimal("4.00"))
    t1 = mk.to("TO-1", destination_location_id=st.f0.id)
    mk.tol(t1, st.i2, Decimal("2.00"))
    s1 = mk.so("SO-1", factory_id=st.f0.id)
    mk.sol(s1, st.i3, Decimal("3.00"), Decimal("3.00"))
    mk.wo("WO-1", factory_id=st.f0.id)
    p2 = mk.po("PO-2", ws="w0", account_id=st.ac0.id)
    mk.pol(p2, st.i0, Decimal("5.00"), Decimal("5.00"))
    s2 = mk.so("SO-2", ws="w0")
    mk.sol(s2, st.i0, Decimal("6.00"), Decimal("6.00"))
    result = stats(db, st, factory_id=st.f0.id)
    # Then 1
    assert result.top_items == []
    assert result.top_vendors == []
    assert result.top_customers == []
    # Then 2
    assert result.top_expense_categories == []
    assert result.top_factories == []


# =========================================================================== #
# OQ-29 -> BUG-2480 — committed / projected / total
# =========================================================================== #

def test_oov_oq29_01__draft_po_lines_count_in_top_items(db, st, mk):
    """OOV-OQ29-01 — lines of a draft PO count in top items.
    Rules: get_stats R4, Money stage D1, D8."""
    p1 = mk.po("PO-1", **mk.draft)
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("50.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).purchase_qty == Decimal("5.00")
    assert irow(result, st.i1).total_spend == Decimal("50.00")


def test_oov_oq29_02__draft_po_counts_in_vendor_spend(db, st, mk):
    """OOV-OQ29-02 — a draft PO counts in its vendor's spend.
    Rules: get_stats R11, R14, Money stage D1."""
    mk.po("PO-1", **mk.draft, account_id=st.ac1.id, total_amount=Decimal("200000.00"))
    mk.po("PO-2", account_id=st.ac2.id, total_amount=Decimal("5.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id, st.ac2.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("200000.00")
    assert vrow(result, st.ac1).order_count == 1


def test_oov_oq29_03__draft_sales_order_counts_in_customers(db, st, mk):
    """OOV-OQ29-03 — a draft sales order counts in top customers.
    Rules: get_stats R16, Money stage D1, D8."""
    mk.so("SO-1", **mk.draft, total_amount=Decimal("70.00"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]
    # Then 2
    assert crow(result, st.ac1).total_spend == Decimal("70.00")
    assert crow(result, st.ac1).order_count == 1


def test_oov_oq29_04__draft_orders_each_count_for_factory(db, st, mk):
    """OOV-OQ29-04 — draft PO, sales and work orders each count for their factory.
    Rules: _build_top_factories R2, R4, R5, R7, Money stage D8."""
    mk.po("PO-1", **mk.draft, total_amount=Decimal("30.00"))
    mk.so("SO-1", **mk.draft, factory_id=st.f2.id, total_amount=Decimal("20.00"))
    mk.wo("WO-1", **mk.draft_wo, factory_id=st.fa.id, cost=Decimal("10.00"))
    result = top_factories(db, st)
    # Then 1
    assert sorted(fids(result)) == sorted([st.f1.id, st.f2.id, st.fa.id])
    # Then 2
    assert frow(result, st.f1).purchase_count == 1
    assert frow(result, st.f2).sales_count == 1
    assert frow(result, st.fa).work_count == 1


@bug(2480)
def test_oov_oq29_05__item_purchase_spend_split_across_po_stages(db, st, mk):
    """OOV-OQ29-05 — an item's purchase spend is split across every PO stage path.
    Rules: get_stats R4b [BUG-2480], Money stage D1, D3, D4."""
    pr = mk.po("PO-R", current_status_id=st.sr.id)
    mk.pol(pr, st.i1, Decimal("1.00"), Decimal("100.00"))
    pc = mk.po("PO-C", current_status_id=st.sc.id)
    mk.pol(pc, st.i1, Decimal("1.00"), Decimal("20.00"))
    pa = mk.po("PO-A", **mk.draft)
    mk.pol(pa, st.i1, Decimal("1.00"), Decimal("5000.00"))
    mk.poa(pa, st.u1, **APPROVED)
    mk.poa(pa, st.u2, **APPROVED)
    pd = mk.po("PO-D", **mk.draft)
    mk.pol(pd, st.i1, Decimal("1.00"), Decimal("3.00"))
    pp = mk.po("PO-P", current_status_id=st.sp.id)
    mk.pol(pp, st.i1, Decimal("1.00"), Decimal("0.40"))
    ph = mk.po("PO-H", **mk.draft)
    mk.pol(ph, st.i1, Decimal("1.00"), Decimal("0.06"))
    mk.poa(ph, st.u1, **APPROVED)
    mk.poa(ph, st.u2)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_spend == Decimal("5123.46")
    assert irow(result, st.i1).line_count == 6
    # Then 3
    assert irow(result, st.i1).total_spend_committed == Decimal("5120.00")
    # Then 4
    assert str(irow(result, st.i1).total_spend_committed) == "5120.00"
    # Then 5
    assert irow(result, st.i1).total_spend_projected == Decimal("3.46")
    # Then 6
    assert str(irow(result, st.i1).total_spend_projected) == "3.46"


@bugs(2480, 2500)
def test_oov_oq29_06__voided_pos_in_none_of_item_spend_figures(db, st, mk):
    """OOV-OQ29-06 — voided POs are in none of an item's three spend figures.
    Rules: get_stats R4a, R4b [BUG-2480], Money stage D2."""
    pr = mk.po("PO-R", current_status_id=st.sr.id)
    mk.pol(pr, st.i1, Decimal("1.00"), Decimal("10.00"))
    pv = mk.po("PO-V", **mk.voided, current_status_id=st.sr.id)
    mk.pol(pv, st.i1, Decimal("50.00"), Decimal("1000.00"))
    pw = mk.po("PO-W", **mk.voided, current_status_id=st.sd.id)
    mk.pol(pw, st.i1, Decimal("9.00"), Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert st.i1.id in item_ids(result)
    # Then 2
    assert irow(result, st.i1).total_spend_committed == Decimal("10.00")
    # Then 3
    assert irow(result, st.i1).total_spend_projected == Decimal("0")
    # Then 4
    assert irow(result, st.i1).total_spend == Decimal("10.00")
    # Then 5
    assert irow(result, st.i1).purchase_qty == Decimal("1.00")


@bugs(2480, 2481)
def test_oov_oq29_07__item_sales_revenue_split_across_sales_stages(db, st, mk):
    """OOV-OQ29-07 — an item's sales revenue is split across every sales stage path.
    Rules: get_stats R7a [BUG-2480], Money stage D1, D3, D5."""
    s1 = mk.so("SO-1", order_completed=True)
    mk.sol(s1, st.i1, Decimal("1.00"), Decimal("300.00"))
    s2 = mk.so("SO-2")
    mk.sol(s2, st.i1, Decimal("1.00"), Decimal("40.00"))
    mk.soa(s2, st.u1, **APPROVED)
    s3 = mk.so("SO-3")
    mk.sol(s3, st.i1, Decimal("1.00"), Decimal("5.00"))
    s4 = mk.so("SO-4")
    mk.sol(s4, st.i1, Decimal("1.00"), Decimal("0.60"))
    mk.soa(s4, st.u1, **APPROVED)
    mk.soa(s4, st.u2)
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).sales_qty == Decimal("4.00")
    assert irow(result, st.i1).line_count == 4
    # Then 3
    assert irow(result, st.i1).sales_revenue_committed == Decimal("340.00")
    # Then 4
    assert str(irow(result, st.i1).sales_revenue_committed) == "340.00"
    # Then 5
    assert irow(result, st.i1).sales_revenue_projected == Decimal("5.60")
    # Then 6
    assert irow(result, st.i1).sales_revenue == Decimal("345.60")


@bug(2480)
def test_oov_oq29_08__vendor_spend_split_across_po_and_expense_stages(db, st, mk):
    """OOV-OQ29-08 — a vendor's spend is split across PO and expense stage paths.
    Rules: get_stats R11b [BUG-2480], Money stage D1, D3, D4, D6, D8."""
    mk.po("PO-R", account_id=st.ac1.id, current_status_id=st.sr.id, total_amount=Decimal("100.00"))
    mk.po("PO-D", **mk.draft, account_id=st.ac1.id, total_amount=Decimal("2.00"))
    mk.eo("EX-C", account_id=st.ac1.id, completed_at=T0, total_amount=Decimal("30.00"))
    mk.eo("EX-Z", account_id=st.ac1.id, required_approvals=0, total_amount=Decimal("4.00"))
    e5 = mk.eo("EX-A", account_id=st.ac1.id, total_amount=Decimal("600.00"))
    mk.eoa(e5, st.u1, **APPROVED)
    mk.eo("EX-N", account_id=st.ac1.id, total_amount=Decimal("0.50"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).order_count == 6
    # Then 3
    assert vrow(result, st.ac1).total_spend == Decimal("736.50")
    # Then 4
    assert vrow(result, st.ac1).total_spend_committed == Decimal("734.00")
    # Then 5
    assert str(vrow(result, st.ac1).total_spend_committed) == "734.00"
    # Then 6
    assert vrow(result, st.ac1).total_spend_projected == Decimal("2.50")
    # Then 7
    assert str(vrow(result, st.ac1).total_spend_projected) == "2.50"


@bug(2480)
def test_oov_oq29_09__expense_approved_at_not_the_mark(db, st, mk):
    """OOV-OQ29-09 — expense approved_at is not the mark; required_approvals overrides the row count.
    Rules: get_stats R11b [BUG-2480], Money stage D3, D6."""
    mk.eo("EX-1", account_id=st.ac1.id, approved_at=T0, approved_by=st.u1.id, total_amount=Decimal("9.00"))
    e2 = mk.eo("EX-2", account_id=st.ac1.id, required_approvals=1, total_amount=Decimal("1.00"))
    mk.eoa(e2, st.u1, **APPROVED)
    mk.eoa(e2, st.u2)
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")
    # Then 3
    assert vrow(result, st.ac1).total_spend_committed == Decimal("1.00")
    # Then 4
    assert vrow(result, st.ac1).total_spend_projected == Decimal("9.00")


@bug(2480)
def test_oov_oq29_10__customer_total_split_across_sales_stages(db, st, mk):
    """OOV-OQ29-10 — a customer's total is split across every sales stage path.
    Rules: get_stats R16a [BUG-2480], Money stage D1, D3, D5, D8."""
    mk.so("SO-1", order_completed=True, total_amount=Decimal("70.00"))
    s2 = mk.so("SO-2", total_amount=Decimal("8.00"))
    mk.soa(s2, st.u1, **APPROVED)
    mk.so("SO-3", total_amount=Decimal("0.25"))
    result = stats(db, st)
    # Then 1
    assert customer_ids(result) == [st.ac1.id]
    # Then 2
    assert crow(result, st.ac1).order_count == 3
    # Then 3
    assert crow(result, st.ac1).total_spend == Decimal("78.25")
    # Then 4
    assert crow(result, st.ac1).total_spend_committed == Decimal("78.00")
    # Then 5
    assert crow(result, st.ac1).total_spend_projected == Decimal("0.25")
    # Then 6
    assert str(crow(result, st.ac1).total_spend_projected) == "0.25"


@bug(2480)
def test_oov_oq29_11__category_total_split_across_expense_stages(db, st, mk):
    """OOV-OQ29-11 — a category's total is split across every expense stage path.
    Rules: get_stats R19b [BUG-2480], Money stage D1, D3, D6, D8."""
    mk.eo("EX-C", completed_at=T0, total_amount=Decimal("10.00"))
    mk.eo("EX-N", total_amount=Decimal("1.00"))
    e3 = mk.eo("EX-H", total_amount=Decimal("0.10"))
    mk.eoa(e3, st.u1, **APPROVED)
    mk.eoa(e3, st.u2)
    e4 = mk.eo("EX-R", required_approvals=1, total_amount=Decimal("200.00"))
    mk.eoa(e4, st.u1, **APPROVED)
    mk.eoa(e4, st.u2)
    result = stats(db, st)
    # Then 1
    assert cats(result) == ["other"]
    # Then 2
    assert erow(result, "other").order_count == 4
    # Then 3
    assert erow(result, "other").total_spend == Decimal("211.10")
    # Then 4
    assert erow(result, "other").total_spend_committed == Decimal("210.00")
    # Then 5
    assert erow(result, "other").total_spend_projected == Decimal("1.10")
    # Then 6
    assert str(erow(result, "other").total_spend_projected) == "1.10"


@bugs(2480, 2481)
def test_oov_oq29_12__factory_money_measures_each_split(db, st, mk):
    """OOV-OQ29-12 — a factory's purchase spend, sales revenue and work cost are each split.
    Rules: _build_top_factories R7a [BUG-2480], Money stage D1, D3, D4, D5, D7, D8."""
    mk.po("PO-R", current_status_id=st.sr.id, total_amount=Decimal("100.00"))
    mk.po("PO-D", **mk.draft, total_amount=Decimal("2.00"))
    mk.so("SO-C", order_completed=True, total_amount=Decimal("50.00"))
    mk.so("SO-N", total_amount=Decimal("5.00"))
    mk.wo("WO-C", cost=Decimal("7.00"))
    mk.wo("WO-I", status=WorkOrderStatusEnum.IN_PROGRESS, cost=Decimal("3.00"))
    mk.wo("WO-D", **mk.draft_wo, cost=Decimal("0.50"))
    w8 = mk.wo("WO-A", **mk.draft_wo, cost=Decimal("0.25"))
    mk.woa(w8, st.u1, **APPROVED)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 8
    # Then 3
    assert frow(result, st.f1).purchase_spend_committed == Decimal("100.00")
    # Then 4
    assert frow(result, st.f1).purchase_spend_projected == Decimal("2.00")
    assert frow(result, st.f1).purchase_spend == Decimal("102.00")
    # Then 5
    assert frow(result, st.f1).sales_revenue_committed == Decimal("50.00")
    # Then 6
    assert frow(result, st.f1).sales_revenue_projected == Decimal("5.00")
    assert frow(result, st.f1).sales_revenue == Decimal("55.00")
    # Then 7
    assert frow(result, st.f1).work_cost_committed == Decimal("10.25")
    # Then 8
    assert frow(result, st.f1).work_cost_projected == Decimal("0.50")
    assert frow(result, st.f1).work_cost == Decimal("10.75")
    # Then 9
    assert str(frow(result, st.f1).work_cost_committed) == "10.25"


@bugs(2480, 2481, 2500, 2501)
def test_oov_oq29_13__voided_and_deleted_in_none_of_factory_figures(db, st, mk):
    """OOV-OQ29-13 — voided and deleted orders are in none of a factory's figures.
    Rules: _build_top_factories R2a, R5a, R7a [BUG-2480], Money stage D2."""
    mk.po("PO-R", current_status_id=st.sr.id, total_amount=Decimal("10.00"))
    mk.po("PO-V", **mk.voided, current_status_id=st.sr.id, total_amount=Decimal("1000.00"))
    mk.po("PO-W", **mk.voided, current_status_id=st.sd.id, total_amount=Decimal("3.00"))
    mk.wo("WO-C", cost=Decimal("1.00"))
    mk.wo("WO-V", **mk.voided_wo, cost=Decimal("50.00"))
    mk.wo("WO-X", **mk.deleted_wo, cost=Decimal("60.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).purchase_spend_committed == Decimal("10.00")
    # Then 3
    assert frow(result, st.f1).purchase_spend_projected == Decimal("0")
    # Then 4
    assert frow(result, st.f1).work_cost_committed == Decimal("1.00")
    # Then 5
    assert frow(result, st.f1).work_cost_projected == Decimal("0")


@bug(2480)
def test_oov_oq29_14__other_workspace_approver_rows_do_not_meet(db, st, mk):
    """OOV-OQ29-14 — approver rows of W0 and W2 do not meet a W1 order's approvals.
    Rules: get_stats R4b [BUG-2480], Money stage D3 (approvers scoped to the order's workspace)."""
    pa = mk.po("PO-A", **mk.draft)
    mk.pol(pa, st.i1, Decimal("1.00"), Decimal("1.00"))
    _add(db, PurchaseOrderApprover(workspace_id=st.w0.id, purchase_order_id=pa.id, user_id=st.u1.id,
                                   assigned_at=T0, approved=True, approved_at=T0))
    pb = mk.po("PO-B", **mk.draft)
    mk.pol(pb, st.i1, Decimal("1.00"), Decimal("2.00"))
    _add(db, PurchaseOrderApprover(workspace_id=st.w2.id, purchase_order_id=pb.id, user_id=st.u1.id,
                                   assigned_at=T0, approved=True, approved_at=T0))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_spend == Decimal("3.00")
    # Then 3
    assert irow(result, st.i1).total_spend_committed == Decimal("0")
    # Then 4
    assert irow(result, st.i1).total_spend_projected == Decimal("3.00")


def test_oov_oq29_15__rankings_use_total_projected_included(db, st, mk):
    """OOV-OQ29-15 — rankings use the total, projected money included.
    Rules: get_stats R14, Money stage D1."""
    mk.po("PO-1", **mk.draft, account_id=st.ac1.id, total_amount=Decimal("100.00"))
    mk.po("PO-2", account_id=st.ac2.id, current_status_id=st.sr.id, total_amount=Decimal("50.00"))
    result = stats(db, st)
    # Then 1
    assert vendor_ids(result) == [st.ac1.id, st.ac2.id]
    # Then 2
    assert vrow(result, st.ac1).total_spend == Decimal("100.00")


@bugs(2480, 2500)
def test_oov_oq29_16__voided_in_none_of_vendor_figures(db, st, mk):
    """OOV-OQ29-16 — voided POs and expense orders are in none of a vendor's three figures.
    Rules: get_stats R11a, R11b [BUG-2480], Money stage D2."""
    mk.po("PO-R", account_id=st.ac1.id, current_status_id=st.sr.id, total_amount=Decimal("10.00"))
    mk.po("PO-V", **mk.voided, account_id=st.ac1.id, current_status_id=st.sr.id, total_amount=Decimal("1000.00"))
    mk.eo("EX-V", **mk.voided, account_id=st.ac1.id, completed_at=T0, total_amount=Decimal("300.00"))
    mk.eo("EX-W", **mk.voided, account_id=st.ac1.id, total_amount=Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert st.ac1.id in vendor_ids(result)
    # Then 2
    assert vrow(result, st.ac1).total_spend_committed == Decimal("10.00")
    # Then 3
    assert vrow(result, st.ac1).total_spend_projected == Decimal("0")
    # Then 4
    assert vrow(result, st.ac1).total_spend == Decimal("10.00")


@bugs(2480, 2500)
def test_oov_oq29_17__voided_in_none_of_category_figures(db, st, mk):
    """OOV-OQ29-17 — voided expense orders are in none of a category's three figures.
    Rules: get_stats R19, R19b [BUG-2480], Money stage D2."""
    mk.eo("EX-C", completed_at=T0, total_amount=Decimal("10.00"))
    mk.eo("EX-V", **mk.voided, completed_at=T0, total_amount=Decimal("300.00"))
    mk.eo("EX-W", **mk.voided, total_amount=Decimal("7.00"))
    result = stats(db, st)
    # Then 1
    assert "other" in cats(result)
    # Then 2
    assert erow(result, "other").total_spend_committed == Decimal("10.00")
    # Then 3
    assert erow(result, "other").total_spend_projected == Decimal("0")
    # Then 4
    assert erow(result, "other").total_spend == Decimal("10.00")


# =========================================================================== #
# OQ-30 -> BUG-2481 — purchase spend, sales revenue and work cost apart
# =========================================================================== #

@bug(2481)
def test_oov_oq30_01__item_spend_is_purchases_only(db, st, mk):
    """OOV-OQ30-01 — an item's spend is purchases only; sales go to sales_revenue.
    Rules: get_stats R7a [BUG-2481], R6."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("10.00"), Decimal("100.00"))
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i1, Decimal("10.00"))
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("10.00"), Decimal("120.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_quantity == Decimal("30.00")
    assert irow(result, st.i1).line_count == 3
    # Then 3
    assert irow(result, st.i1).purchase_qty == Decimal("10.00")
    assert irow(result, st.i1).transfer_qty == Decimal("10.00")
    # Then 4
    assert irow(result, st.i1).sales_qty == Decimal("10.00")
    # Then 5
    assert irow(result, st.i1).total_spend == Decimal("100.00")
    # Then 6
    assert irow(result, st.i1).sales_revenue == Decimal("120.00")
    # Then 7
    assert str(irow(result, st.i1).sales_revenue) == "120.00"


@bug(2481)
def test_oov_oq30_02__items_ranked_by_purchased_quantity(db, st, mk):
    """OOV-OQ30-02 — items are ranked by purchased quantity.
    Rules: get_stats R9 [BUG-2481]."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("5.00"), Decimal("5.00"))
    mk.pol(p1, st.i2, Decimal("20.00"), Decimal("20.00"), line_number=2)
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("20.00"), Decimal("1.00"))
    result = stats(db, st, limit=1)
    # Then 1
    assert item_ids(result) == [st.i2.id]


@bug(2481)
def test_oov_oq30_03__factory_keeps_money_apart(db, st, mk):
    """OOV-OQ30-03 — a factory keeps purchase spend, sales revenue and work cost apart.
    Rules: _build_top_factories R7a [BUG-2481], R3."""
    mk.po("PO-1", total_amount=Decimal("10000.00"))
    mk.so("SO-1", total_amount=Decimal("12000.00"))
    mk.wo("WO-1", cost=Decimal("5.00"))
    mk.to("TO-1")
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 4
    # Then 3
    assert frow(result, st.f1).purchase_count == 1
    assert frow(result, st.f1).transfer_count == 1
    assert frow(result, st.f1).sales_count == 1
    assert frow(result, st.f1).work_count == 1
    # Then 4
    assert frow(result, st.f1).total_value == Decimal("10000.00")
    # Then 5
    assert frow(result, st.f1).purchase_spend == Decimal("10000.00")
    # Then 6
    assert frow(result, st.f1).sales_revenue == Decimal("12000.00")
    # Then 7
    assert frow(result, st.f1).work_cost == Decimal("5.00")


def test_oov_oq30_04__factories_ranked_by_count_of_every_kind(db, st, mk):
    """OOV-OQ30-04 — factories are ranked by the order count of every kind.
    Rules: _build_top_factories R7, R11, Money stage D8."""
    mk.po("PO-1", total_amount=Decimal("1.00"))
    mk.so("SO-1", total_amount=Decimal("1.00"))
    mk.po("PO-2", destination_id=st.f2.id, total_amount=Decimal("900.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id, st.f2.id]


def test_oov_oq30_05__total_quantity_adds_every_kind(db, st, mk):
    """OOV-OQ30-05 — total_quantity adds purchase, transfer and sales quantities.
    Rules: get_stats R7, R6."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("10.00"), Decimal("100.00"))
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i1, Decimal("2.50"))
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("0.25"), Decimal("120.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).total_quantity == Decimal("12.75")
    assert irow(result, st.i1).line_count == 3
    # Then 3
    assert irow(result, st.i1).purchase_qty == Decimal("10.00")
    assert irow(result, st.i1).transfer_qty == Decimal("2.50")
    assert irow(result, st.i1).sales_qty == Decimal("0.25")


def test_oov_oq30_06__factory_counts_add_every_kind(db, st, mk):
    """OOV-OQ30-06 — a factory's counts add every order kind.
    Rules: _build_top_factories R7, R10."""
    mk.po("PO-1", total_amount=Decimal("10000.00"))
    mk.so("SO-1", total_amount=Decimal("12000.00"))
    mk.wo("WO-1", cost=Decimal("5.00"))
    mk.to("TO-1")
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 4
    # Then 3
    assert frow(result, st.f1).purchase_count == 1
    assert frow(result, st.f1).transfer_count == 1
    assert frow(result, st.f1).sales_count == 1
    assert frow(result, st.f1).work_count == 1


@bug(2481)
def test_oov_oq30_07__factory_money_tie_break_is_purchase_spend(db, st, mk):
    """OOV-OQ30-07 — the money tie-break between factories is purchase spend.
    Rules: _build_top_factories R11 [BUG-2481]."""
    mk.so("SO-1", total_amount=Decimal("900.00"))
    mk.po("PO-2", destination_id=st.f2.id, total_amount=Decimal("5.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id, st.f1.id]


@bugs(2481, 2480)
def test_oov_oq30_08__spec_example_approved_and_draft_pos_completed_sale(db, st, mk):
    """OOV-OQ30-08 — the spec's example: a factory with approved and draft POs and a completed sale.
    Rules: _build_top_factories R7a [BUG-2481, BUG-2480]."""
    mk.po("PO-1", current_status_id=st.sr.id, total_amount=Decimal("10000.00"))
    mk.po("PO-2", **mk.draft, total_amount=Decimal("2000.00"))
    mk.so("SO-1", order_completed=True, total_amount=Decimal("12000.00"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).order_count == 3
    # Then 3
    assert frow(result, st.f1).total_value == Decimal("12000.00")
    # Then 4
    assert frow(result, st.f1).purchase_spend == Decimal("12000.00")
    # Then 5
    assert frow(result, st.f1).purchase_spend_committed == Decimal("10000.00")
    assert frow(result, st.f1).purchase_spend_projected == Decimal("2000.00")
    # Then 6
    assert frow(result, st.f1).sales_revenue == Decimal("12000.00")
    assert frow(result, st.f1).sales_revenue_committed == Decimal("12000.00")
    # Then 7
    assert frow(result, st.f1).work_cost == Decimal("0")


@bug(2481)
def test_oov_oq30_09__never_purchased_item_after_purchased(db, st, mk):
    """OOV-OQ30-09 — an item never purchased comes after any purchased item.
    Rules: get_stats R9 [BUG-2481]."""
    t1 = mk.to("TO-1")
    mk.tol(t1, st.i3, Decimal("500.00"))
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i2, Decimal("1.00"), Decimal("1.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i2.id, st.i3.id]


@bug(2481)
def test_oov_oq30_10__equal_purchased_quantity_by_purchase_spend(db, st, mk):
    """OOV-OQ30-10 — equal purchased quantity is broken by purchase spend only.
    Rules: get_stats R9 [BUG-2481]."""
    p1 = mk.po("PO-1")
    mk.pol(p1, st.i1, Decimal("10.00"), Decimal("5.00"))
    mk.pol(p1, st.i2, Decimal("10.00"), Decimal("9.00"), line_number=2)
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("1.00"), Decimal("900.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i2.id, st.i1.id]


@bug(2481)
def test_oov_oq30_11__sold_only_item_no_spend_revenue_is_line_total(db, st, mk):
    """OOV-OQ30-11 — a sold-only item has no spend and its line total as sales revenue.
    Rules: get_stats R7a [BUG-2481], R6."""
    s1 = mk.so("SO-1")
    mk.sol(s1, st.i1, Decimal("3.00"), Decimal("300.00"))
    result = stats(db, st)
    # Then 1
    assert item_ids(result) == [st.i1.id]
    # Then 2
    assert irow(result, st.i1).sales_qty == Decimal("3.00")
    # Then 3
    assert irow(result, st.i1).total_spend == Decimal("0")
    # Then 4
    assert irow(result, st.i1).sales_revenue == Decimal("300.00")
    # Then 5
    assert str(irow(result, st.i1).sales_revenue) == "300.00"


@bug(2481)
def test_oov_oq30_12__sales_order_adds_revenue_not_total_value(db, st, mk):
    """OOV-OQ30-12 — a sales order adds sales revenue, not total_value, to its factory.
    Rules: _build_top_factories R4, R7a [BUG-2481]."""
    mk.so("SO-1", factory_id=st.f2.id, total_amount=Decimal("30.05"))
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f2.id]
    # Then 2
    assert frow(result, st.f2).sales_count == 1
    # Then 3
    assert frow(result, st.f2).total_value == Decimal("0")
    # Then 4
    assert frow(result, st.f2).sales_revenue == Decimal("30.05")
    # Then 5
    assert str(frow(result, st.f2).sales_revenue) == "30.05"


@bug(2481)
def test_oov_oq30_13__work_orders_add_work_cost_not_total_value(db, st, mk):
    """OOV-OQ30-13 — work orders add work cost, not total_value; a missing cost adds 0.
    Rules: _build_top_factories R5, R7a [BUG-2481]."""
    mk.wo("WO-1", cost=Decimal("12.34"))
    mk.wo("WO-2", cost=None)
    result = top_factories(db, st)
    # Then 1
    assert fids(result) == [st.f1.id]
    # Then 2
    assert frow(result, st.f1).work_count == 2
    # Then 3
    assert frow(result, st.f1).total_value == Decimal("0")
    # Then 4
    assert frow(result, st.f1).work_cost == Decimal("12.34")
    # Then 5
    assert str(frow(result, st.f1).work_cost) == "12.34"
