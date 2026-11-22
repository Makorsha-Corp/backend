"""Unit tests for app/services/item_orders_service.py.

Implements tests/unit/services/item_orders_service.cases.md (revision 3), one
test per card, in card order. Real Postgres session (`db` fixture), rolled back
after each test. Nothing is patched except what Conventions name: the
`db.commit` / `db.rollback` spies of IOS-G-34 and the fixed-input patch of
`_purchase_rows` in IOS-G-37.

Every test builds the Standing rows (autouse fixture `st`). Card row names are
the lower-case names here (F1 -> st.f1, I1 -> st.i1); `# Then N` marks the
checks of the card's Then line N. Order builders live on the `mk` fixture.
"""
# ruff: noqa: DTZ001, FURB157, RUF032  (cards prescribe naive datetimes, Decimal("3") string literals and Decimal(0.1))
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event

from app.core.exceptions import NotFoundError
from app.models.account import Account
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_type import WorkOrderType
from app.schemas.item_orders import ItemOrderRowResponse
from app.services.item_orders_service import (
    ItemOrdersService,
    _build_po_destination_labels,
    _dec,
    _in_date_range,
    _weighted_unit_price,
    item_orders_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

svc = item_orders_service

PRE = date(2026, 4, 30)
START = date(2026, 5, 1)
MID = date(2026, 5, 10)
END = date(2026, 5, 31)
POST = date(2026, 6, 1)
CT = datetime(2026, 5, 10, 9, 0, 0)
T0 = datetime(2020, 1, 2, 3, 4, 5)
MISSING = 999999999


def noon(d):
    """Convention noon(d)."""
    return datetime(d.year, d.month, d.day, 12, 0, 0)


def XID(k):
    """Convention XID(k): an explicit row id, unique per test process."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def GN(n):
    """Convention GN(n): the card's number n with the per-process suffix (Parallel runs)."""
    return f"{n}-{os.getpid()}"


def base(x):
    """Convention base(x): drops the GN suffix; other numbers unchanged."""
    return x.removesuffix(f"-{os.getpid()}")


# --------------------------------------------------------------------------- #
# Conventions -> xfail markers (bug titles from docs/testing/bugs.md)
# --------------------------------------------------------------------------- #

_TITLES = {
    "BUG-2490": "a partly priced PO's unit price is spread over its unpriced quantity too",
    "BUG-2491": "an order priced at 0.00 shows no line total",
    "BUG-2550": "an item's order list fails whenever the item is on a work order",
    "BUG-2551": "an item's order list has no tie-break after date and created_at",
    "BUG-2552": "voided work orders appear in an item's order list",
    "BUG-2553": "deleted work orders appear in an item's order list",
    "BUG-2554": "unit price in an item's order list is not rounded",
    "BUG-2555": "an item's order list shows another workspace's account, status, machine id or project name",
}


def bug(*ids, strict=True, raises=None):
    reason = "; ".join(f"{i}: {_TITLES[i]}" for i in ids)
    return pytest.mark.xfail(strict=strict, raises=raises, reason=reason)


# BUG-2550 cards fail in the When call itself (AttributeError on `status.value`);
# `raises=` pins the xfail to that cause, so a setup error is not hidden.
BUG_2550 = bug("BUG-2550", raises=AttributeError)


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test; flushed in this order, so in each
# table W0 ids < W1 ids < W2 ids)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


_NAMES = {
    0: {"f": ("Factory Zero", "F0"), "ac": "Zero Co", "m": "Zero Press", "pj": "Zero Build", "c": "Base"},
    1: {"f": ("Factory One", "F1"), "ac": "Acme", "m": "Press 1", "pj": "Main Build", "c": "Roof"},
    9: {"f": ("Factory Nine", "F9"), "ac": "Far Co", "m": "Far Press", "pj": "Far Build", "c": "Wing"},
}


@pytest.fixture(autouse=True)
def st(db):
    s = SimpleNamespace()
    s.w0 = make_workspace(db)
    s.w1 = make_workspace(db)
    s.w2 = make_workspace(db)
    s.u1 = make_profile(db)
    for x, w in ((0, s.w0), (1, s.w1), (9, s.w2)):
        n = _NAMES[x]
        f = _add(db, Factory(workspace_id=w.id, name=n["f"][0], abbreviation=n["f"][1]))
        setattr(s, f"f{x}", f)
        setattr(s, f"s{x}", _add(db, Status(workspace_id=w.id, name="Draft", comment="Stage")))
        setattr(s, f"ac{x}", _add(db, Account(workspace_id=w.id, name=n["ac"])))
        setattr(s, f"wt{x}", _add(db, WorkOrderType(workspace_id=w.id, name="Repair")))
        setattr(s, f"i{x}", _add(db, Item(workspace_id=w.id, name="Bolt", name_normalized="bolt", unit="pcs")))
        setattr(s, f"m{x}", _add(db, Machine(workspace_id=w.id, factory_id=f.id, name=n["m"])))
        pj = _add(db, Project(workspace_id=w.id, factory_id=f.id, name=n["pj"], description="Main"))
        setattr(s, f"pj{x}", pj)
        setattr(s, f"c{x}", _add(db, ProjectComponent(workspace_id=w.id, project_id=pj.id, name=n["c"])))
    s.i2 = _add(db, Item(workspace_id=s.w1.id, name="Nut", name_normalized="nut", unit="pcs"))
    s.s2 = _add(db, Status(workspace_id=s.w1.id, name="Closed", comment="Stage"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Order builders. "W0 x" is `w0=True`, "W2 x" is `w2=True`;
# keyword arguments are the columns listed after "but".
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, db, s):
        self.db = db
        self.s = s
        self._k = {}

    def _v(self, w0, w2):
        x = 0 if w0 else (9 if w2 else 1)
        s = self.s
        return SimpleNamespace(
            w={0: s.w0, 1: s.w1, 9: s.w2}[x], f=getattr(s, f"f{x}"), st=getattr(s, f"s{x}"),
            ac=getattr(s, f"ac{x}"), wt=getattr(s, f"wt{x}"),
        )

    def _line_no(self, key):
        self._k[key] = self._k.get(key, 0) + 1
        return self._k[key]

    @property
    def voided(self):
        """Convention: voided po."""
        return {"voided": True, "void_note": "Void", "voided_at": T0, "voided_by": self.s.u1.id}

    @property
    def deleted_wo(self):
        """Convention: deleted wo."""
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.u1.id}

    def po(self, n, *, w0=False, w2=False, **kw):
        v = self._v(w0, w2)
        f = {
            "workspace_id": v.w.id, "po_number": n, "account_id": v.ac.id, "destination_type": "storage",
            "destination_id": v.f.id, "subtotal": Decimal("0.00"), "total_amount": Decimal("0.00"),
            "current_status_id": v.st.id, "created_by": self.s.u1.id, "description": "Steel order",
            "order_date": MID, "created_at": CT,
        }
        f.update(kw)
        return _add(self.db, PurchaseOrder(**f))

    def pl(self, p, i, q, sub, **kw):
        f = {
            "workspace_id": p.workspace_id, "purchase_order_id": p.id, "line_number": self._line_no(("po", p.id)),
            "item_id": i.id, "quantity_ordered": Decimal(q), "line_subtotal": None if sub is None else Decimal(sub),
        }
        f.update(kw)
        return _add(self.db, PurchaseOrderItem(**f))

    def to(self, n, *, w0=False, w2=False, **kw):
        v = self._v(w0, w2)
        f = {
            "workspace_id": v.w.id, "transfer_number": GN(n), "source_location_type": "storage",
            "source_location_id": v.f.id, "destination_location_type": "storage",
            "destination_location_id": v.f.id, "current_status_id": v.st.id, "created_by": self.s.u1.id,
            "created_at": CT,
        }
        f.update(kw)
        return _add(self.db, TransferOrder(**f))

    def tl(self, t, i, q, **kw):
        f = {
            "workspace_id": t.workspace_id, "transfer_order_id": t.id, "line_number": self._line_no(("to", t.id)),
            "item_id": i.id, "quantity": Decimal(q),
        }
        f.update(kw)
        return _add(self.db, TransferOrderItem(**f))

    def so(self, n, *, w0=False, w2=False, **kw):
        v = self._v(w0, w2)
        f = {
            "workspace_id": v.w.id, "sales_order_number": GN(n), "account_id": v.ac.id, "factory_id": v.f.id,
            "order_date": MID, "total_amount": Decimal("0.00"), "current_status_id": v.st.id,
            "created_by": self.s.u1.id, "description": "Chairs", "created_at": CT,
        }
        f.update(kw)
        return _add(self.db, SalesOrder(**f))

    def sl(self, s_, i, q, t, **kw):
        f = {
            "workspace_id": s_.workspace_id, "sales_order_id": s_.id, "item_id": None if i is None else i.id,
            "description": "Line", "quantity_ordered": Decimal(q), "unit_price": Decimal("1.00"),
            "line_total": Decimal(t),
        }
        f.update(kw)
        return _add(self.db, SalesOrderItem(**f))

    def wo(self, n, *, w0=False, w2=False, **kw):
        v = self._v(w0, w2)
        f = {
            "workspace_id": v.w.id, "work_order_number": n, "title": "Fix press", "factory_id": v.f.id,
            "work_order_type_id": v.wt.id, "created_by": self.s.u1.id, "status": "DRAFT", "created_at": CT,
        }
        f.update(kw)
        return _add(self.db, WorkOrder(**f))

    def wl(self, w, i, q, **kw):
        f = {"workspace_id": w.workspace_id, "work_order_id": w.id, "item_id": i.id, "quantity": Decimal(q)}
        f.update(kw)
        return _add(self.db, WorkOrderItem(**f))


@pytest.fixture
def mk(db, st):
    return Builder(db, st)


def seven_pos(mk, st):
    """Given 'Seven POs PO-1 … PO-7' of IOS-G-24 … G-28."""
    for k in range(1, 8):
        p = mk.po(f"PO-{k}", order_date=date(2026, 5, 10 + k))
        mk.pl(p, st.i1, "1.00", "5.00")


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #

def nums(result):
    return [base(r.order_number) for r in result.items]


def numset(result):
    return {base(r.order_number) for r in result.items}


def row(result, n):
    (r,) = [r for r in result.items if base(r.order_number) == n]
    return r


def recorder(db):
    """Convention recorder: returns (stmts, stop)."""
    stmts = []
    conn = db.connection()

    def rec(conn_, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(conn, "before_cursor_execute", rec)
    return stmts, lambda: event.remove(conn, "before_cursor_execute", rec)


def orders(db, st, **kw):
    """The standard list call: W1, I1, limit 1000 unless given."""
    kw.setdefault("limit", 1000)
    return svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, **kw)


# =========================================================================== #
# _dec
# =========================================================================== #

def test_ios_dc_01__none_becomes_zero():
    """IOS-DC-01 — None becomes zero.
    Rules: _dec R1."""
    result = _dec(None)
    # Then 1
    assert result == Decimal(0)
    assert isinstance(result, Decimal)


def test_ios_dc_02__decimal_keeps_scale():
    """IOS-DC-02 — a Decimal keeps its scale.
    Rules: _dec R2."""
    result = _dec(Decimal("10.00"))
    # Then 1
    assert str(result) == "10.00"


def test_ios_dc_03__float_through_text():
    """IOS-DC-03 — a float goes through its text, not its binary value.
    Rules: _dec R2."""
    result = _dec(0.1)
    # Then 1
    assert result == Decimal("0.1")
    # Then 2
    assert result != Decimal(0.1)


def test_ios_dc_04__non_numeric_text_raises():
    """IOS-DC-04 — non-numeric text raises InvalidOperation.
    Rules: _dec R3."""
    # Then 1
    with pytest.raises(InvalidOperation):
        _dec("abc")


# =========================================================================== #
# _in_date_range
# =========================================================================== #

def test_ios_dr_01__both_ends_included(db, st, mk):
    """IOS-DR-01 — both ends are included, the days outside are not.
    Rules: _in_date_range R1."""
    mk.po("PO-A", order_date=PRE)
    mk.po("PO-B", order_date=START)
    mk.po("PO-C", order_date=END)
    mk.po("PO-D", order_date=POST)
    result = db.query(PurchaseOrder).filter(
        PurchaseOrder.workspace_id == st.w1.id, _in_date_range(PurchaseOrder.order_date, START, END)
    ).all()
    # Then 1
    assert {p.po_number for p in result} == {"PO-B", "PO-C"}


def test_ios_dr_02__reversed_range_matches_nothing(db, st, mk):
    """IOS-DR-02 — a reversed range matches nothing.
    Rules: _in_date_range R1."""
    mk.po("PO-A", order_date=START)
    mk.po("PO-B", order_date=END)
    result = db.query(PurchaseOrder).filter(
        PurchaseOrder.workspace_id == st.w1.id, _in_date_range(PurchaseOrder.order_date, END, START)
    ).all()
    # Then 1
    assert result == []


# =========================================================================== #
# _weighted_unit_price
# =========================================================================== #

def test_ios_wp_01__quantity_zero_gives_none():
    """IOS-WP-01 — quantity 0 gives None.
    Rules: _weighted_unit_price R1."""
    result = _weighted_unit_price(Decimal("50.00"), Decimal("0"))
    # Then 1
    assert result is None


def test_ios_wp_02__negative_quantity_gives_none():
    """IOS-WP-02 — a negative quantity gives None.
    Rules: _weighted_unit_price R1."""
    result = _weighted_unit_price(Decimal("50.00"), Decimal("-1"))
    # Then 1
    assert result is None


def test_ios_wp_03__smallest_positive_quantity_divides():
    """IOS-WP-03 — the smallest positive quantity divides.
    Rules: _weighted_unit_price R1, R2."""
    result = _weighted_unit_price(Decimal("1.00"), Decimal("0.01"))
    # Then 1
    assert result == Decimal("100")


def test_ios_wp_04__zero_total_gives_zero():
    """IOS-WP-04 — a zero total gives zero, not None.
    Rules: _weighted_unit_price R2."""
    result = _weighted_unit_price(Decimal("0"), Decimal("4"))
    # Then 1
    assert result is not None
    # Then 2
    assert result == Decimal("0")


def test_ios_wp_05__total_divided_by_quantity():
    """IOS-WP-05 — total divided by quantity.
    Rules: _weighted_unit_price R2."""
    result = _weighted_unit_price(Decimal("50.00"), Decimal("10.00"))
    # Then 1
    assert result == Decimal("5.00")
    assert isinstance(result, Decimal)


def test_ios_wp_06__repeating_quotient_within_a_cent():
    """IOS-WP-06 — a repeating quotient is within a cent of the rounded value.
    Rules: _weighted_unit_price R2, R3 (regression part of BUG-2554)."""
    result = _weighted_unit_price(Decimal("100.00"), Decimal("3"))
    # Then 1
    assert Decimal("33.33") <= result < Decimal("33.34")


@bug("BUG-2554")
def test_ios_wp_07__price_rounded_to_two_places():
    """IOS-WP-07 — the price is rounded to two places.
    Rules: _weighted_unit_price R3 [BUG-2554]."""
    result = _weighted_unit_price(Decimal("100.00"), Decimal("3"))
    # Then 1
    assert str(result) == "33.33"


@bug("BUG-2554")
def test_ios_wp_08__half_cent_rounds_up():
    """IOS-WP-08 — a half cent rounds up, not to even.
    Rules: _weighted_unit_price R3 [BUG-2554]."""
    result = _weighted_unit_price(Decimal("0.25"), Decimal("2"))
    # Then 1
    assert str(result) == "0.13"


@bug("BUG-2554")
def test_ios_wp_09__negative_half_cent_rounds_away_from_zero():
    """IOS-WP-09 — a negative half cent rounds away from zero.
    Rules: _weighted_unit_price R3 [BUG-2554]."""
    result = _weighted_unit_price(Decimal("-0.25"), Decimal("2"))
    # Then 1
    assert str(result) == "-0.13"


# =========================================================================== #
# _build_po_destination_labels
# =========================================================================== #

def test_ios_dl_01__only_falsy_ids_nothing_read(db, st):
    """IOS-DL-01 — only falsy ids: empty dict, nothing read.
    Rules: _build_po_destination_labels R1."""
    stmts, stop = recorder(db)
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("storage", 0), ("machine", None), ("project", 0)]
    )
    stop()
    # Then 1
    assert result == {}
    # Then 2
    assert stmts == []


def test_ios_dl_02__falsy_dropped_real_kept(db, st):
    """IOS-DL-02 — falsy ids are dropped, real ones kept.
    Rules: _build_po_destination_labels R1, R2."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("storage", 0), ("storage", st.f1.id)]
    )
    # Then 1
    assert result == {("storage", st.f1.id): "Storage (Factory One)"}


def test_ios_dl_03__storage_labelled_with_factory(db, st):
    """IOS-DL-03 — storage is labelled with the factory name.
    Rules: _build_po_destination_labels R2."""
    result = _build_po_destination_labels(db, workspace_id=st.w1.id, destinations=[("storage", st.f1.id)])
    # Then 1
    assert result[("storage", st.f1.id)] == "Storage (Factory One)"


def test_ios_dl_04__machine_labelled_with_machine(db, st):
    """IOS-DL-04 — machine is labelled with the machine name.
    Rules: _build_po_destination_labels R3."""
    result = _build_po_destination_labels(db, workspace_id=st.w1.id, destinations=[("machine", st.m1.id)])
    # Then 1
    assert result == {("machine", st.m1.id): "Machine (Press 1)"}


def test_ios_dl_05__project_labelled_with_project_and_component(db, st):
    """IOS-DL-05 — project is labelled with project and component names.
    Rules: _build_po_destination_labels R4."""
    result = _build_po_destination_labels(db, workspace_id=st.w1.id, destinations=[("project", st.c1.id)])
    # Then 1
    assert result == {("project", st.c1.id): "Project · Main Build / Roof"}


def test_ios_dl_06__deleted_factory_and_machine_still_named(db, st):
    """IOS-DL-06 — a deleted factory and a deleted machine are still named.
    Rules: _build_po_destination_labels R5."""
    fd = _add(db, Factory(workspace_id=st.w1.id, name="Old Plant", abbreviation="OP", is_deleted=True))
    md = _add(db, Machine(workspace_id=st.w1.id, factory_id=st.f1.id, name="Press 4", is_active=False,
                          is_deleted=True))
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("storage", fd.id), ("machine", md.id)]
    )
    # Then 1
    assert result[("storage", fd.id)] == "Storage (Old Plant)"
    # Then 2
    assert result[("machine", md.id)] == "Machine (Press 4)"


def test_ios_dl_07__missing_ids_get_fallback_labels(db, st):
    """IOS-DL-07 — ids found nowhere get the fallback labels.
    Rules: _build_po_destination_labels R6, R7 (missing id keeps R6)."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id,
        destinations=[("storage", MISSING), ("machine", MISSING), ("project", MISSING)],
    )
    # Then 1
    assert result[("storage", MISSING)] == "Storage"
    # Then 2
    assert result[("machine", MISSING)] == "Machine #999999999"
    # Then 3
    assert result[("project", MISSING)] == "Component #999999999"
    # Then 4
    assert len(result) == 3


def test_ios_dl_08__unknown_type_labelled_type_and_id(db, st):
    """IOS-DL-08 — an unknown type is labelled type and id.
    Rules: _build_po_destination_labels R6."""
    result = _build_po_destination_labels(db, workspace_id=st.w1.id, destinations=[("weird", 7)])
    # Then 1
    assert result == {("weird", 7): "weird #7"}


def test_ios_dl_09__pair_given_twice_appears_once(db, st):
    """IOS-DL-09 — a pair given twice appears once.
    Rules: _build_po_destination_labels R6 (duplicates)."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id,
        destinations=[("machine", st.m1.id), ("storage", st.f1.id), ("machine", st.m1.id)],
    )
    # Then 1
    assert result == {("machine", st.m1.id): "Machine (Press 1)", ("storage", st.f1.id): "Storage (Factory One)"}


def test_ios_dl_10__other_workspace_names_never_in_label(db, st):
    """IOS-DL-10 — another workspace's names never appear in a label.
    Rules: _build_po_destination_labels R7 (regression part of BUG-2555)."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id,
        destinations=[("storage", st.f0.id), ("storage", st.f9.id), ("machine", st.m0.id),
                      ("machine", st.m9.id), ("project", st.c0.id), ("project", st.c9.id)],
    )
    # Then 1
    assert not any("Factory Zero" in v or "Factory Nine" in v for v in result.values())
    # Then 2
    assert not any("Zero Press" in v or "Far Press" in v for v in result.values())
    # Then 3
    assert not any(s in v for v in result.values() for s in ("Zero Build", "Far Build", "Base", "Wing"))


@bug("BUG-2555")
def test_ios_dl_11__other_workspace_factory_no_label(db, st):
    """IOS-DL-11 — another workspace's factory gets no label.
    Rules: _build_po_destination_labels R7 [BUG-2555]."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id,
        destinations=[("storage", st.f0.id), ("storage", st.f9.id), ("storage", st.f1.id)],
    )
    # Then 1
    assert ("storage", st.f0.id) not in result
    # Then 2
    assert ("storage", st.f9.id) not in result
    # Then 3
    assert result[("storage", st.f1.id)] == "Storage (Factory One)"


@bug("BUG-2555")
def test_ios_dl_12__other_workspace_machine_no_label(db, st):
    """IOS-DL-12 — another workspace's machine gets no label.
    Rules: _build_po_destination_labels R7 [BUG-2555]."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("machine", st.m0.id), ("machine", st.m9.id)]
    )
    # Then 1
    assert ("machine", st.m0.id) not in result
    # Then 2
    assert ("machine", st.m9.id) not in result


@bug("BUG-2555")
def test_ios_dl_13__other_workspace_component_no_label(db, st):
    """IOS-DL-13 — another workspace's component gets no label.
    Rules: _build_po_destination_labels R7 [BUG-2555]."""
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("project", st.c0.id), ("project", st.c9.id)]
    )
    # Then 1
    assert ("project", st.c0.id) not in result
    # Then 2
    assert ("project", st.c9.id) not in result


@bug("BUG-2555")
def test_ios_dl_14__component_under_foreign_project_no_label(db, st):
    """IOS-DL-14 — this workspace's component under another workspace's project gets no label.
    Rules: _build_po_destination_labels R7 [BUG-2555]."""
    cx0 = _add(db, ProjectComponent(workspace_id=st.w1.id, project_id=st.pj0.id, name="Annex"))
    cx9 = _add(db, ProjectComponent(workspace_id=st.w1.id, project_id=st.pj9.id, name="Stray"))
    result = _build_po_destination_labels(
        db, workspace_id=st.w1.id, destinations=[("project", cx0.id), ("project", cx9.id)]
    )
    # Then 1
    assert ("project", cx0.id) not in result
    # Then 2
    assert ("project", cx9.id) not in result


# =========================================================================== #
# ItemOrdersService.get_orders_for_item
# =========================================================================== #

def test_ios_g_01__unknown_item_is_404(db, st):
    """IOS-G-01 — an unknown item is 404.
    Rules: get_orders_for_item R1; Errors row 1."""
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=MISSING, limit=1000)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 2
    assert not db.new and not db.dirty and not db.deleted


def test_ios_g_02__lower_workspace_item_404_nothing_read(db, st, mk):
    """IOS-G-02 — an item of the lower workspace is 404 and nothing else is read.
    Rules: get_orders_for_item R1; Errors row 1."""
    p0 = mk.po("PO-Z", w0=True)
    mk.pl(p0, st.i0, "1.00", "5.00")
    stmts, stop = recorder(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i0.id, limit=1000)
    stop()
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {st.i0.id} not found"
    # Then 2
    assert not any("purchase_orders" in s for s in stmts)
    # Then 3
    assert not any("sales_orders" in s or "transfer_orders" in s or "work_orders" in s for s in stmts)


def test_ios_g_03__higher_workspace_item_404(db, st, mk):
    """IOS-G-03 — an item of the higher workspace is 404.
    Rules: get_orders_for_item R1; Errors row 1."""
    p9 = mk.po("PO-N", w2=True)
    mk.pl(p9, st.i9, "1.00", "5.00")
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i9.id, limit=1000)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {st.i9.id} not found"


def test_ios_g_04__deleted_item_still_answers(db, st, mk):
    """IOS-G-04 — a deleted item still answers with its orders.
    Rules: get_orders_for_item R2."""
    idel = _add(db, Item(workspace_id=st.w1.id, name="Old bolt", name_normalized="old bolt", unit="pcs",
                         is_active=False))
    p1 = mk.po("PO-1")
    mk.pl(p1, idel, "2.00", "10.00")
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=idel.id, limit=1000)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


def test_ios_g_05__no_type_purchase_transfer_sales(db, st, mk):
    """IOS-G-05 — no type: purchase, transfer and sales rows together.
    Rules: get_orders_for_item R3."""
    p1 = mk.po("PO-1", order_date=date(2026, 5, 12))
    mk.pl(p1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", created_at=noon(date(2026, 5, 11)))
    mk.tl(t1, st.i1, "2.00")
    s1 = mk.so("SO-1", order_date=MID)
    mk.sl(s1, st.i1, "3.00", "30.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 3
    # Then 2
    assert [(r.order_type, base(r.order_number)) for r in result.items] == [
        ("purchase_order", "PO-1"), ("transfer_order", "TO-1"), ("sales_order", "SO-1")
    ]


@BUG_2550
def test_ios_g_06__no_type_work_order_row_too(db, st, mk):
    """IOS-G-06 — no type: a work order row comes with the others.
    Rules: get_orders_for_item R3; _work_rows R5 [BUG-2550]; Errors row 2."""
    p1 = mk.po("PO-1", order_date=date(2026, 5, 13))
    mk.pl(p1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", created_at=noon(date(2026, 5, 12)))
    mk.tl(t1, st.i1, "2.00")
    s1 = mk.so("SO-1", order_date=date(2026, 5, 11))
    mk.sl(s1, st.i1, "3.00", "30.00")
    wo1 = mk.wo("WO-1", created_at=noon(MID))
    mk.wl(wo1, st.i1, "4.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 4
    # Then 2
    assert nums(result) == ["PO-1", "TO-1", "SO-1", "WO-1"]


def _four_types(mk, st):
    """Given lines 1-8 of IOS-G-07 … G-10."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1")
    mk.tl(t1, st.i1, "2.00")
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "3.00", "30.00")
    wo1 = mk.wo("WO-1")
    mk.wl(wo1, st.i1, "4.00")


def test_ios_g_07__type_purchase_only(db, st, mk):
    """IOS-G-07 — type purchase: only purchase rows, other types not read.
    Rules: get_orders_for_item R3."""
    _four_types(mk, st)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


def test_ios_g_08__type_transfer_only(db, st, mk):
    """IOS-G-08 — type transfer: only transfer rows.
    Rules: get_orders_for_item R3."""
    _four_types(mk, st)
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["TO-1"]


def test_ios_g_09__type_sales_only(db, st, mk):
    """IOS-G-09 — type sales: only sales rows.
    Rules: get_orders_for_item R3."""
    _four_types(mk, st)
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["SO-1"]


@BUG_2550
def test_ios_g_10__type_work_only(db, st, mk):
    """IOS-G-10 — type work: only work rows.
    Rules: get_orders_for_item R3; _work_rows R5 [BUG-2550]."""
    _four_types(mk, st)
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["WO-1"]


def test_ios_g_11__reversed_range_no_rows(db, st, mk):
    """IOS-G-11 — a reversed range gives no rows.
    Rules: get_orders_for_item R4, R9."""
    p1 = mk.po("PO-1", order_date=MID)
    mk.pl(p1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", created_at=noon(MID))
    mk.tl(t1, st.i1, "2.00")
    s1 = mk.so("SO-1", order_date=MID)
    mk.sl(s1, st.i1, "3.00", "30.00")
    result = orders(db, st, from_date=END, to_date=START)
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


def test_ios_g_12__one_day_range(db, st, mk):
    """IOS-G-12 — a one-day range keeps that day only.
    Rules: get_orders_for_item R4."""
    pa = mk.po("PO-A", order_date=date(2026, 5, 9))
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", order_date=MID)
    mk.pl(pb, st.i1, "1.00", "5.00")
    pc = mk.po("PO-C", order_date=date(2026, 5, 11))
    mk.pl(pc, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1", order_date=MID)
    mk.sl(s1, st.i1, "3.00", "30.00")
    result = orders(db, st, from_date=MID, to_date=MID)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-B", "SO-1"}


def _pre_post_pos(mk, st):
    pa = mk.po("PO-A", order_date=PRE)
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", order_date=POST)
    mk.pl(pb, st.i1, "1.00", "5.00")


def test_ios_g_13__from_date_alone_ignored(db, st, mk):
    """IOS-G-13 — from_date alone is ignored at the service.
    Rules: get_orders_for_item R4a (service part)."""
    _pre_post_pos(mk, st)
    result = orders(db, st, from_date=POST)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-A", "PO-B"}


def test_ios_g_14__to_date_alone_ignored(db, st, mk):
    """IOS-G-14 — to_date alone is ignored at the service.
    Rules: get_orders_for_item R4a (service part)."""
    _pre_post_pos(mk, st)
    result = orders(db, st, to_date=PRE)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-A", "PO-B"}


def test_ios_g_15__excluded_po_left_out(db, st, mk):
    """IOS-G-15 — the excluded PO is left out, POs on both sides of its id stay.
    Rules: get_orders_for_item R5; _purchase_rows R4."""
    pa = mk.po("PO-A")
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B")
    mk.pl(pb, st.i1, "1.00", "5.00")
    pc = mk.po("PO-C")
    mk.pl(pc, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "3.00", "30.00")
    result = orders(db, st, exclude_purchase_order_id=pb.id)
    # Then 1
    assert result.total == 3
    # Then 2
    assert numset(result) == {"PO-A", "PO-C", "SO-1"}


def test_ios_g_16__exclude_zero_leaves_everything(db, st, mk):
    """IOS-G-16 — exclude 0 leaves everything in.
    Rules: get_orders_for_item R5; _purchase_rows R4."""
    pa = mk.po("PO-A")
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B")
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, exclude_purchase_order_id=0)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-A", "PO-B"}


def test_ios_g_17__unknown_exclude_leaves_everything(db, st, mk):
    """IOS-G-17 — an unknown exclude id leaves everything in.
    Rules: get_orders_for_item R5; _purchase_rows R4."""
    pa = mk.po("PO-A")
    mk.pl(pa, st.i1, "1.00", "5.00")
    result = orders(db, st, exclude_purchase_order_id=MISSING)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-A"]


def test_ios_g_18__exclude_touches_pos_only(db, st, mk):
    """IOS-G-18 — exclude touches POs only: a transfer with the same id stays.
    Rules: get_orders_for_item R5."""
    px = mk.po("PO-X", id=XID(1))
    mk.pl(px, st.i1, "1.00", "5.00")
    tx = mk.to("TO-X", id=XID(1))
    mk.tl(tx, st.i1, "2.00")
    sx = mk.so("SO-X", id=XID(1))
    mk.sl(sx, st.i1, "3.00", "30.00")
    result = orders(db, st, exclude_purchase_order_id=XID(1))
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"TO-X", "SO-X"}


def test_ios_g_19__date_then_created_at_newest_first(db, st, mk):
    """IOS-G-19 — date newest first, then created_at newest first.
    Rules: get_orders_for_item R6."""
    p2 = mk.po("PO-2", order_date=date(2026, 5, 11), created_at=datetime(2026, 5, 11, 8, 0, 0))
    mk.pl(p2, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1", order_date=date(2026, 5, 11), created_at=datetime(2026, 5, 20, 9, 0, 0))
    mk.sl(s1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", created_at=datetime(2026, 5, 11, 10, 0, 0))
    mk.tl(t1, st.i1, "1.00")
    p1 = mk.po("PO-1", order_date=date(2026, 5, 12), created_at=datetime(2026, 5, 1, 8, 0, 0))
    mk.pl(p1, st.i1, "1.00", "5.00")
    p3 = mk.po("PO-3", order_date=date(2026, 5, 9), created_at=datetime(2026, 5, 30, 8, 0, 0))
    mk.pl(p3, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 5
    # Then 2
    assert nums(result) == ["PO-1", "SO-1", "TO-1", "PO-2", "PO-3"]


def test_ios_g_20__full_tie_across_types_keeps_type_order(db, st, mk):
    """IOS-G-20 — a full tie across types keeps purchase, transfer, sales.
    Rules: get_orders_for_item R6 [BUG-2551] (type key, holds today)."""
    s1 = mk.so("SO-1", order_date=MID, created_at=CT)
    mk.sl(s1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", created_at=CT)
    mk.tl(t1, st.i1, "1.00")
    p1 = mk.po("PO-1", order_date=MID, created_at=CT)
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert nums(result) == ["PO-1", "TO-1", "SO-1"]


@bug("BUG-2551", strict=False)
def test_ios_g_21__tie_in_one_type_by_id_desc(db, st, mk):
    """IOS-G-21 — a full tie inside one type is broken by order id descending.
    Rules: get_orders_for_item R6 [BUG-2551]."""
    for n, k in (("PO-B", 2), ("PO-A", 1), ("PO-D", 4), ("PO-C", 3), ("PO-F", 6), ("PO-E", 5)):
        p = mk.po(n, id=XID(k), order_date=MID, created_at=CT)
        mk.pl(p, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 6
    # Then 2
    assert nums(result) == ["PO-F", "PO-E", "PO-D", "PO-C", "PO-B", "PO-A"]


@bug("BUG-2551", strict=False)
def test_ios_g_22__page_across_tie_by_id_desc(db, st, mk):
    """IOS-G-22 — a page across a tie takes the rows by order id descending.
    Rules: get_orders_for_item R6 [BUG-2551], R8."""
    for n, k in (("PO-C", 3), ("PO-A", 1), ("PO-E", 5), ("PO-B", 2), ("PO-D", 4)):
        p = mk.po(n, id=XID(k), order_date=MID, created_at=CT)
        mk.pl(p, st.i1, "1.00", "5.00")
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=1, limit=2)
    # Then 1
    assert result.total == 5
    # Then 2
    assert nums(result) == ["PO-D", "PO-C"]


@BUG_2550
def test_ios_g_23__full_tie_work_order_last(db, st, mk):
    """IOS-G-23 — in a full tie the work order comes last.
    Rules: get_orders_for_item R6 [BUG-2551]; _work_rows R5 [BUG-2550]."""
    wo1 = mk.wo("WO-1", created_at=CT)
    mk.wl(wo1, st.i1, "1.00")
    s1 = mk.so("SO-1", order_date=MID, created_at=CT)
    mk.sl(s1, st.i1, "1.00", "5.00")
    p1 = mk.po("PO-1", order_date=MID, created_at=CT)
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert nums(result) == ["PO-1", "SO-1", "WO-1"]


def test_ios_g_24__skip_2_limit_3_of_7(db, st, mk):
    """IOS-G-24 — skip 2, limit 3 of 7.
    Rules: get_orders_for_item R7, R8."""
    seven_pos(mk, st)
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=2, limit=3)
    # Then 1
    assert result.total == 7
    # Then 2
    assert nums(result) == ["PO-5", "PO-4", "PO-3"]


def test_ios_g_25__skip_one_before_end(db, st, mk):
    """IOS-G-25 — skip one before the end gives the last row.
    Rules: get_orders_for_item R8."""
    seven_pos(mk, st)
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=6, limit=1000)
    # Then 1
    assert result.total == 7
    # Then 2
    assert nums(result) == ["PO-1"]


def test_ios_g_26__skip_at_end_empty_page(db, st, mk):
    """IOS-G-26 — skip at the end gives an empty page.
    Rules: get_orders_for_item R8."""
    seven_pos(mk, st)
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=7, limit=1000)
    # Then 1
    assert result.total == 7
    # Then 2
    assert result.items == []


def test_ios_g_27__limit_0_empty_page(db, st, mk):
    """IOS-G-27 — limit 0 gives an empty page, total unchanged.
    Rules: get_orders_for_item R7, R8."""
    seven_pos(mk, st)
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, limit=0)
    # Then 1
    assert result.total == 7
    # Then 2
    assert result.items == []


def test_ios_g_28__limit_1_newest(db, st, mk):
    """IOS-G-28 — limit 1 gives the newest row.
    Rules: get_orders_for_item R8."""
    seven_pos(mk, st)
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, limit=1)
    # Then 1
    assert result.total == 7
    # Then 2
    assert nums(result) == ["PO-7"]


def test_ios_g_29__default_limit_50(db, st, mk):
    """IOS-G-29 — the default limit is 50.
    Rules: get_orders_for_item R8 (default limit=50)."""
    for k in range(1, 52):
        p = mk.po(f"PO-{k}", order_date=date(2026, 1, 1) + timedelta(days=k))
        mk.pl(p, st.i1, "1.00", "5.00")
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id)
    # Then 1
    assert result.total == 51
    # Then 2
    assert len(result.items) == 50
    # Then 3
    assert "PO-1" not in nums(result)
    # Then 4
    assert nums(result)[0] == "PO-51"


def test_ios_g_30__voided_filtered_before_paging(db, st, mk):
    """IOS-G-30 — a voided PO is filtered before paging.
    Rules: get_orders_for_item R7, R8; _purchase_rows R2."""
    pv = mk.po("PO-V", order_date=date(2026, 5, 20), **mk.voided)
    mk.pl(pv, st.i1, "1.00", "5.00")
    for n, d in (("PO-A", 15), ("PO-B", 14), ("PO-C", 13)):
        p = mk.po(n, order_date=date(2026, 5, d))
        mk.pl(p, st.i1, "1.00", "5.00")
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=1, limit=1)
    # Then 1
    assert result.total == 3
    # Then 2
    assert nums(result) == ["PO-B"]


def test_ios_g_31__other_workspace_filtered_before_paging(db, st, mk):
    """IOS-G-31 — another workspace's order is filtered before paging.
    Rules: get_orders_for_item R7, R8, R10."""
    p0 = mk.po("PO-Z", w0=True, order_date=date(2026, 5, 21))
    mk.pl(p0, st.i1, "1.00", "5.00")
    for n, d in (("PO-A", 15), ("PO-B", 14), ("PO-C", 13)):
        p = mk.po(n, order_date=date(2026, 5, d))
        mk.pl(p, st.i1, "1.00", "5.00")
    p9 = mk.po("PO-N", w2=True, order_date=date(2026, 5, 20))
    mk.pl(p9, st.i1, "1.00", "5.00")
    result = svc.get_orders_for_item(db, workspace_id=st.w1.id, item_id=st.i1.id, skip=1, limit=1)
    # Then 1
    assert result.total == 3
    # Then 2
    assert nums(result) == ["PO-B"]


def test_ios_g_32__item_with_no_orders_empty(db, st, mk):
    """IOS-G-32 — an item with no orders gives an empty list.
    Rules: get_orders_for_item R9; _purchase_rows R1."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i2, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


def test_ios_g_33__two_lines_one_row(db, st, mk):
    """IOS-G-33 — a PO with two lines of the item is one row.
    Rules: get_orders_for_item R11; _purchase_rows R5, R6."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "4.00", "20.00")
    mk.pl(p1, st.i1, "6.00", "30.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").quantity == Decimal("10.00")
    # Then 3
    assert row(result, "PO-1").line_total == Decimal("50.00")
    # Then 4
    assert row(result, "PO-1").unit_price == Decimal("5.00")


def test_ios_g_34__nothing_written_pending_stays(db, st, mk):
    """IOS-G-34 — nothing is written, committed or rolled back; pending changes stay.
    Rules: get_orders_for_item R12."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    db.commit()  # commit point
    db.add(Item(workspace_id=st.w1.id, name="Spare", name_normalized="spare", unit="pcs"))
    st.ac1.name = "Changed"
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert len(db.new) == 1
    # Then 3
    assert st.ac1 in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert st.ac1.name == "Changed"
    # Then 6
    assert cm.call_count == 0
    assert rb.call_count == 0


def test_ios_g_35__type_rank_before_order_id(db, st, mk):
    """IOS-G-35 — in a full tie the type rank comes before the order id.
    Rules: get_orders_for_item R6 [BUG-2551] (type key, holds today), R13."""
    s1 = mk.so("SO-1", id=XID(5), order_date=MID, created_at=CT)
    mk.sl(s1, st.i1, "1.00", "5.00")
    t1 = mk.to("TO-1", id=XID(3), created_at=CT)
    mk.tl(t1, st.i1, "1.00")
    p1 = mk.po("PO-1", id=XID(1), order_date=MID, created_at=CT)
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 3
    # Then 2
    assert nums(result) == ["PO-1", "TO-1", "SO-1"]


@bug("BUG-2551", strict=False)
def test_ios_g_36__type_rank_then_id_desc(db, st, mk):
    """IOS-G-36 — in a full tie: type rank first, then order id descending inside the type.
    Rules: get_orders_for_item R6 [BUG-2551], R13."""
    p1 = mk.po("PO-1", id=XID(1), order_date=MID, created_at=CT)
    mk.pl(p1, st.i1, "1.00", "5.00")
    t4 = mk.to("TO-4", id=XID(4), created_at=CT)
    mk.tl(t4, st.i1, "1.00")
    p7 = mk.po("PO-7", id=XID(7), order_date=MID, created_at=CT)
    mk.pl(p7, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 3
    # Then 2
    assert nums(result) == ["PO-7", "PO-1", "TO-4"]


def RK(k):
    """IOS-G-37 Given 2: a tied purchase row response."""
    return ItemOrderRowResponse(
        order_type="purchase_order", order_id=k, order_number=f"PO-{k}", order_date=MID,
        quantity=Decimal("1.00"), unit_price=Decimal("5.00"), line_total=Decimal("5.00"),
        status_name="Draft", account_name=None, destination_label=None, created_at=CT,
    )


@bug("BUG-2551")
def test_ios_g_37__fixed_tied_input_by_id_desc(db, st):
    """IOS-G-37 — a fixed tied input in ascending id order comes out by order id descending.
    Rules: get_orders_for_item R6 [BUG-2551], R13."""
    with patch.object(ItemOrdersService, "_purchase_rows", return_value=[RK(1), RK(2), RK(3)]):
        result = orders(db, st)
    # Then 1
    assert result.total == 3
    # Then 2
    assert nums(result) == ["PO-3", "PO-2", "PO-1"]


# =========================================================================== #
# ItemOrdersService._purchase_rows
# =========================================================================== #

def test_ios_p_01__every_field_of_purchase_row(db, st, mk):
    """IOS-P-01 — every field of a purchase row.
    Rules: _purchase_rows R1, R5, R6, R9; get_orders_for_item R10."""
    p1 = mk.po("PO-1", order_date=MID)
    mk.pl(p1, st.i1, "10.00", "50.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert len(result.items) == 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").order_type == "purchase_order"
    assert row(result, "PO-1").order_id == p1.id
    # Then 3
    assert row(result, "PO-1").order_date == MID
    # Then 4
    assert row(result, "PO-1").quantity == Decimal("10.00")
    # Then 5
    assert row(result, "PO-1").unit_price == Decimal("5.00")
    # Then 6
    assert row(result, "PO-1").line_total == Decimal("50.00")
    # Then 7
    assert row(result, "PO-1").status_name == "Draft"
    assert row(result, "PO-1").account_name == "Acme"
    # Then 8
    assert row(result, "PO-1").destination_label == "Storage (Factory One)"
    # Then 9
    db.refresh(p1)
    assert row(result, "PO-1").created_at == p1.created_at


def test_ios_p_02__other_item_lines_ignored(db, st, mk):
    """IOS-P-02 — lines of other items are ignored.
    Rules: _purchase_rows R1, R5, R6."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "2.00", "10.00")
    mk.pl(p1, st.i2, "5.00", "99.00")
    p2 = mk.po("PO-2")
    mk.pl(p2, st.i2, "1.00", "7.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    assert nums(result) == ["PO-1"]
    # Then 2
    assert row(result, "PO-1").quantity == Decimal("2.00")
    # Then 3
    assert row(result, "PO-1").line_total == Decimal("10.00")


def test_ios_p_03__voided_po_left_out(db, st, mk):
    """IOS-P-03 — a voided PO is left out.
    Rules: _purchase_rows R2."""
    pv = mk.po("PO-V", **mk.voided)
    mk.pl(pv, st.i1, "1.00", "5.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


def test_ios_p_04__no_order_date_uses_created_at(db, st, mk):
    """IOS-P-04 — no order_date: the date of created_at is used.
    Rules: _purchase_rows R3."""
    p1 = mk.po("PO-1", order_date=None, created_at=noon(date(2026, 5, 11)))
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").order_date == date(2026, 5, 11)


def test_ios_p_05__no_order_date_range_on_created_day(db, st, mk):
    """IOS-P-05 — no order_date: the range filters on the created_at day, both edges.
    Rules: _purchase_rows R3; get_orders_for_item R4."""
    for n, d in (("PO-A", PRE), ("PO-B", START), ("PO-C", END), ("PO-D", POST)):
        p = mk.po(n, order_date=None, created_at=noon(d))
        mk.pl(p, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-B", "PO-C"}


def test_ios_p_06__order_date_range_both_edges(db, st, mk):
    """IOS-P-06 — order_date range, both edges.
    Rules: _purchase_rows R3; get_orders_for_item R4."""
    for n, od, cd in (("PO-A", PRE, START), ("PO-B", START, PRE), ("PO-C", END, POST), ("PO-D", POST, END)):
        p = mk.po(n, order_date=od, created_at=noon(cd))
        mk.pl(p, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-B", "PO-C"}


def test_ios_p_07__quantity_is_ordered_not_received(db, st, mk):
    """IOS-P-07 — quantity is ordered, not received.
    Rules: _purchase_rows R5."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "10.00", "50.00", quantity_received=Decimal("4.00"))
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("10.00")


def test_ios_p_08__no_account_name_none(db, st, mk):
    """IOS-P-08 — no account: account_name None.
    Rules: _purchase_rows R9."""
    p1 = mk.po("PO-1", account_id=None)
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").account_name is None


def test_ios_p_09__destination_id_0_label_none(db, st, mk):
    """IOS-P-09 — destination id 0: destination_label None.
    Rules: _purchase_rows R9; _build_po_destination_labels R1."""
    p1 = mk.po("PO-1", destination_id=0)
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").destination_label is None


def test_ios_p_10__machine_and_project_destinations(db, st, mk):
    """IOS-P-10 — machine and project destinations reach the row.
    Rules: _purchase_rows R9; _build_po_destination_labels R3, R4."""
    pm = mk.po("PO-M", destination_type="machine", destination_id=st.m1.id)
    mk.pl(pm, st.i1, "1.00", "5.00")
    pj = mk.po("PO-J", destination_type="project", destination_id=st.c1.id)
    mk.pl(pj, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-M").destination_label == "Machine (Press 1)"
    # Then 2
    assert row(result, "PO-J").destination_label == "Project · Main Build / Roof"


def test_ios_p_11__smallest_positive_total_shown(db, st, mk):
    """IOS-P-11 — the smallest positive total is shown.
    Rules: _purchase_rows R6, R8 (positive side)."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "0.01")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").line_total == Decimal("0.01")
    # Then 2
    assert row(result, "PO-1").unit_price == Decimal("0.01")


def test_ios_p_12__other_workspace_pos_not_listed(db, st, mk):
    """IOS-P-12 — POs of the lower and higher workspace are not listed.
    Rules: get_orders_for_item R10; _purchase_rows R1."""
    p0 = mk.po("PO-Z", w0=True)
    mk.pl(p0, st.i1, "1.00", "5.00")
    p0b = mk.po("PO-ZB", w0=True)
    mk.pl(p0b, st.i0, "1.00", "5.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    p9 = mk.po("PO-N", w2=True)
    mk.pl(p9, st.i1, "1.00", "5.00")
    p9b = mk.po("PO-NB", w2=True)
    mk.pl(p9b, st.i9, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


@bug("BUG-2555")
def test_ios_p_13__foreign_account_po_left_out(db, st, mk):
    """IOS-P-13 — a PO with another workspace's account is left out.
    Rules: _purchase_rows R10 [BUG-2555]."""
    pa = mk.po("PO-A", account_id=st.ac0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", account_id=st.ac9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


@bug("BUG-2555")
def test_ios_p_14__foreign_status_po_left_out(db, st, mk):
    """IOS-P-14 — a PO with another workspace's status is left out.
    Rules: _purchase_rows R10 [BUG-2555]."""
    pa = mk.po("PO-A", current_status_id=st.s0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", current_status_id=st.s9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


@bug("BUG-2555")
def test_ios_p_15__foreign_factory_po_left_out(db, st, mk):
    """IOS-P-15 — a PO stored at another workspace's factory is left out.
    Rules: _purchase_rows R10 [BUG-2555]; _build_po_destination_labels R7."""
    pa = mk.po("PO-A", destination_id=st.f0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", destination_id=st.f9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


@bug("BUG-2555")
def test_ios_p_16__foreign_machine_po_left_out(db, st, mk):
    """IOS-P-16 — a PO for another workspace's machine is left out.
    Rules: _purchase_rows R10 [BUG-2555]; _build_po_destination_labels R7."""
    pa = mk.po("PO-A", destination_type="machine", destination_id=st.m0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", destination_type="machine", destination_id=st.m9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


@bug("BUG-2555")
def test_ios_p_17__foreign_component_po_left_out(db, st, mk):
    """IOS-P-17 — a PO for another workspace's component is left out.
    Rules: _purchase_rows R10 [BUG-2555]; _build_po_destination_labels R7."""
    pa = mk.po("PO-A", destination_type="project", destination_id=st.c0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", destination_type="project", destination_id=st.c9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


@bug("BUG-2555")
def test_ios_p_18__component_under_foreign_project_po_left_out(db, st, mk):
    """IOS-P-18 — a PO for this workspace's component under another workspace's project is left out.
    Rules: _purchase_rows R10 [BUG-2555]; _build_po_destination_labels R7."""
    cx0 = _add(db, ProjectComponent(workspace_id=st.w1.id, project_id=st.pj0.id, name="Annex"))
    cx9 = _add(db, ProjectComponent(workspace_id=st.w1.id, project_id=st.pj9.id, name="Stray"))
    pa = mk.po("PO-A", destination_type="project", destination_id=cx0.id)
    mk.pl(pa, st.i1, "1.00", "5.00")
    pb = mk.po("PO-B", destination_type="project", destination_id=cx9.id)
    mk.pl(pb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


@bug("BUG-2554")
def test_ios_p_19__row_unit_price_rounded(db, st, mk):
    """IOS-P-19 — the row's unit price is rounded to two places.
    Rules: _purchase_rows R7 via _weighted_unit_price R3 [BUG-2554]."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "3.00", "100.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").line_total == Decimal("100.00")
    # Then 2
    assert str(row(result, "PO-1").unit_price) == "33.33"


def test_ios_p_20__repeating_price_quantity_and_total_exact(db, st, mk):
    """IOS-P-20 — quantity and total of a repeating-price PO are exact.
    Rules: _purchase_rows R5, R6, R8 (regression part of BUG-2554)."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "3.00", "100.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("3.00")
    # Then 2
    assert row(result, "PO-1").line_total == Decimal("100.00")
    # Then 3
    assert Decimal("33.33") <= row(result, "PO-1").unit_price < Decimal("33.34")


def test_ios_p_21__stored_created_day_to_last_microsecond(db, st, mk):
    """IOS-P-21 — no order_date: the stored created_at day counts, to the last microsecond.
    Rules: _purchase_rows R3; get_orders_for_item R4."""
    for n, ca in (
        ("PO-A", datetime(2026, 4, 30, 23, 59, 59, 999999)),
        ("PO-B", datetime(2026, 5, 1, 0, 0, 0)),
        ("PO-C", datetime(2026, 5, 31, 23, 59, 59, 999999)),
        ("PO-D", datetime(2026, 6, 1, 0, 0, 0)),
    ):
        p = mk.po(n, order_date=None, created_at=ca)
        mk.pl(p, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="purchase_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"PO-B", "PO-C"}
    # Then 3
    assert row(result, "PO-B").order_date == START
    assert row(result, "PO-C").order_date == END


def test_ios_p_22__direct_call_plain_list(db, st, mk):
    """IOS-P-22 — called directly, the helper returns a plain list of row responses.
    Rules: _purchase_rows R12, R1, R9."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "2.00", "10.00")
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = svc._purchase_rows(db, workspace_id=st.w1.id, item_id=st.i1.id, from_date=None, to_date=None)
    # Then 1
    assert type(result) is list
    assert len(result) == 1
    # Then 2
    assert isinstance(result[0], ItemOrderRowResponse)
    # Then 3
    assert result[0].order_type == "purchase_order"
    assert result[0].order_number == "PO-1"
    # Then 4
    assert result[0].quantity == Decimal("3.00")
    assert result[0].line_total == Decimal("15.00")
    # Then 5
    assert result[0].unit_price == Decimal("5.00")


def test_ios_p_23__direct_call_no_match_empty_list(db, st, mk):
    """IOS-P-23 — called directly with no matching PO, the helper returns an empty list.
    Rules: _purchase_rows R12."""
    p2 = mk.po("PO-2")
    mk.pl(p2, st.i2, "1.00", "5.00")
    result = svc._purchase_rows(db, workspace_id=st.w1.id, item_id=st.i1.id, from_date=None, to_date=None)
    # Then 1
    assert result == []
    assert type(result) is list


# =========================================================================== #
# ItemOrdersService._transfer_rows
# =========================================================================== #

def test_ios_t_01__every_field_two_lines_one_row(db, st, mk):
    """IOS-T-01 — every field of a transfer row; two lines are one row.
    Rules: _transfer_rows R1, R2, R3; get_orders_for_item R11."""
    t1 = mk.to("TO-1", created_at=noon(MID))
    mk.tl(t1, st.i1, "4.00")
    mk.tl(t1, st.i1, "1.50")
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 1
    assert len(result.items) == 1
    # Then 2
    assert row(result, "TO-1").order_type == "transfer_order"
    assert row(result, "TO-1").order_id == t1.id
    # Then 3
    assert row(result, "TO-1").order_date == MID
    # Then 4
    assert row(result, "TO-1").quantity == Decimal("5.50")
    # Then 5
    assert row(result, "TO-1").unit_price is None
    assert row(result, "TO-1").line_total is None
    # Then 6
    assert row(result, "TO-1").account_name is None
    assert row(result, "TO-1").destination_label is None
    # Then 7
    assert row(result, "TO-1").status_name == "Draft"


def test_ios_t_02__any_status_counts(db, st, mk):
    """IOS-T-02 — every transfer counts, whatever its status.
    Rules: _transfer_rows R1, R3."""
    ta = mk.to("TO-A", current_status_id=st.s2.id, created_at=noon(date(2026, 5, 11)))
    mk.tl(ta, st.i1, "1.00")
    tb = mk.to("TO-B", created_at=noon(MID))
    mk.tl(tb, st.i1, "1.00")
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 2
    # Then 2
    assert row(result, "TO-A").status_name == "Closed"
    # Then 3
    assert row(result, "TO-B").status_name == "Draft"


def test_ios_t_03__range_on_created_day_both_edges(db, st, mk):
    """IOS-T-03 — the range filters on the created_at day, both edges.
    Rules: _transfer_rows R2; get_orders_for_item R4."""
    for n, d in (("TO-A", PRE), ("TO-B", START), ("TO-C", END), ("TO-D", POST)):
        t = mk.to(n, created_at=noon(d))
        mk.tl(t, st.i1, "1.00")
    result = orders(db, st, order_type="transfer_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"TO-B", "TO-C"}


def test_ios_t_04__transfers_without_item_not_listed(db, st, mk):
    """IOS-T-04 — transfers without the item are not listed.
    Rules: _transfer_rows R1, R3."""
    ta = mk.to("TO-A")
    mk.tl(ta, st.i2, "9.00")
    tb = mk.to("TO-B")
    mk.tl(tb, st.i1, "2.00")
    mk.tl(tb, st.i2, "7.00")
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 1
    assert nums(result) == ["TO-B"]
    # Then 2
    assert row(result, "TO-B").quantity == Decimal("2.00")


def test_ios_t_05__other_workspace_transfers_not_listed(db, st, mk):
    """IOS-T-05 — transfers of the lower and higher workspace are not listed.
    Rules: get_orders_for_item R10; _transfer_rows R1."""
    t0 = mk.to("TO-Z", w0=True)
    mk.tl(t0, st.i1, "1.00")
    t1 = mk.to("TO-1")
    mk.tl(t1, st.i1, "1.00")
    t9 = mk.to("TO-N", w2=True)
    mk.tl(t9, st.i1, "1.00")
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["TO-1"]


@bug("BUG-2555")
def test_ios_t_06__foreign_status_transfer_left_out(db, st, mk):
    """IOS-T-06 — a transfer with another workspace's status is left out.
    Rules: _transfer_rows R4 [BUG-2555]."""
    ta = mk.to("TO-A", current_status_id=st.s0.id)
    mk.tl(ta, st.i1, "1.00")
    t1 = mk.to("TO-1")
    mk.tl(t1, st.i1, "1.00")
    tb = mk.to("TO-B", current_status_id=st.s9.id)
    mk.tl(tb, st.i1, "1.00")
    result = orders(db, st, order_type="transfer_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["TO-1"]


def test_ios_t_07__direct_call_empty_fields_none(db, st, mk):
    """IOS-T-07 — called directly, the helper returns row responses with the empty fields None.
    Rules: _purchase_rows R12 (shape shared by all four helpers); _transfer_rows R3."""
    t1 = mk.to("TO-1")
    mk.tl(t1, st.i1, "4.00")
    result = svc._transfer_rows(db, workspace_id=st.w1.id, item_id=st.i1.id, from_date=None, to_date=None)
    # Then 1
    assert type(result) is list
    assert len(result) == 1
    # Then 2
    assert isinstance(result[0], ItemOrderRowResponse)
    # Then 3
    assert result[0].order_type == "transfer_order"
    assert result[0].quantity == Decimal("4.00")
    # Then 4
    assert result[0].unit_price is None
    assert result[0].line_total is None


def test_ios_t_08__stored_created_day_to_last_microsecond(db, st, mk):
    """IOS-T-08 — the stored created_at day counts, to the last microsecond.
    Rules: _transfer_rows R2; get_orders_for_item R4."""
    for n, ca in (
        ("TO-A", datetime(2026, 4, 30, 23, 59, 59, 999999)),
        ("TO-B", datetime(2026, 5, 1, 0, 0, 0)),
        ("TO-C", datetime(2026, 5, 31, 23, 59, 59, 999999)),
        ("TO-D", datetime(2026, 6, 1, 0, 0, 0)),
    ):
        t = mk.to(n, created_at=ca)
        mk.tl(t, st.i1, "1.00")
    result = orders(db, st, order_type="transfer_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"TO-B", "TO-C"}
    # Then 3
    assert row(result, "TO-B").order_date == START
    assert row(result, "TO-C").order_date == END


# =========================================================================== #
# ItemOrdersService._sales_rows
# =========================================================================== #

def test_ios_s_01__every_field_of_sales_row(db, st, mk):
    """IOS-S-01 — every field of a sales row.
    Rules: _sales_rows R1, R2, R3, R4, R6."""
    s1 = mk.so("SO-1", order_date=MID)
    mk.sl(s1, st.i1, "3.00", "300.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    assert len(result.items) == 1
    # Then 2
    assert row(result, "SO-1").order_type == "sales_order"
    assert row(result, "SO-1").order_id == s1.id
    # Then 3
    assert row(result, "SO-1").order_date == MID
    # Then 4
    assert row(result, "SO-1").quantity == Decimal("3.00")
    # Then 5
    assert row(result, "SO-1").unit_price == Decimal("100.00")
    # Then 6
    assert row(result, "SO-1").line_total == Decimal("300.00")
    # Then 7
    assert row(result, "SO-1").account_name == "Acme"
    assert row(result, "SO-1").status_name == "Draft"
    # Then 8
    assert row(result, "SO-1").destination_label is None


def test_ios_s_02__free_text_and_other_item_lines_never_match(db, st, mk):
    """IOS-S-02 — free-text and other-item lines never match.
    Rules: _sales_rows R1, R3."""
    sa = mk.so("SO-A")
    mk.sl(sa, None, "5.00", "50.00")
    mk.sl(sa, st.i2, "2.00", "20.00")
    sb = mk.so("SO-B")
    mk.sl(sb, st.i1, "2.00", "40.00")
    mk.sl(sb, None, "9.00", "90.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    assert nums(result) == ["SO-B"]
    # Then 2
    assert row(result, "SO-B").quantity == Decimal("2.00")
    # Then 3
    assert row(result, "SO-B").line_total == Decimal("40.00")


def test_ios_s_03__any_status_counts(db, st, mk):
    """IOS-S-03 — any status counts.
    Rules: _sales_rows R1, R6."""
    sa = mk.so("SO-A", current_status_id=st.s2.id, order_date=date(2026, 5, 11))
    mk.sl(sa, st.i1, "1.00", "5.00")
    sb = mk.so("SO-B")
    mk.sl(sb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 2
    # Then 2
    assert row(result, "SO-A").status_name == "Closed"


def test_ios_s_04__order_date_range_both_edges(db, st, mk):
    """IOS-S-04 — order_date range, both edges.
    Rules: _sales_rows R2; get_orders_for_item R4."""
    for n, od, cd in (("SO-A", PRE, START), ("SO-B", START, PRE), ("SO-C", END, POST), ("SO-D", POST, END)):
        s = mk.so(n, order_date=od, created_at=noon(cd))
        mk.sl(s, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="sales_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"SO-B", "SO-C"}


def test_ios_s_05__two_lines_one_row_summed_weighted(db, st, mk):
    """IOS-S-05 — two lines: one row, summed and weighted.
    Rules: _sales_rows R3, R4; get_orders_for_item R11."""
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "1.00", "10.00")
    mk.sl(s1, st.i1, "3.00", "30.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "SO-1").quantity == Decimal("4.00")
    # Then 3
    assert row(result, "SO-1").line_total == Decimal("40.00")
    # Then 4
    assert row(result, "SO-1").unit_price == Decimal("10.00")


def test_ios_s_06__other_workspace_sales_not_listed(db, st, mk):
    """IOS-S-06 — sales orders of the lower and higher workspace are not listed.
    Rules: get_orders_for_item R10; _sales_rows R1."""
    s0 = mk.so("SO-Z", w0=True)
    mk.sl(s0, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "1.00", "5.00")
    s9 = mk.so("SO-N", w2=True)
    mk.sl(s9, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["SO-1"]


@bug("BUG-2555")
def test_ios_s_07__foreign_account_sales_left_out(db, st, mk):
    """IOS-S-07 — a sales order with another workspace's account is left out.
    Rules: _sales_rows R6 [BUG-2555]."""
    sa = mk.so("SO-A", account_id=st.ac0.id)
    mk.sl(sa, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "1.00", "5.00")
    sb = mk.so("SO-B", account_id=st.ac9.id)
    mk.sl(sb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["SO-1"]


@bug("BUG-2555")
def test_ios_s_08__foreign_status_sales_left_out(db, st, mk):
    """IOS-S-08 — a sales order with another workspace's status is left out.
    Rules: _sales_rows R6 [BUG-2555]."""
    sa = mk.so("SO-A", current_status_id=st.s0.id)
    mk.sl(sa, st.i1, "1.00", "5.00")
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "1.00", "5.00")
    sb = mk.so("SO-B", current_status_id=st.s9.id)
    mk.sl(sb, st.i1, "1.00", "5.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["SO-1"]


@bug("BUG-2554")
def test_ios_s_09__half_cent_unit_price_rounds_up(db, st, mk):
    """IOS-S-09 — a half cent unit price rounds up.
    Rules: _sales_rows R4 via _weighted_unit_price R3 [BUG-2554]."""
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "2.00", "0.25")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert row(result, "SO-1").line_total == Decimal("0.25")
    # Then 2
    assert str(row(result, "SO-1").unit_price) == "0.13"


def test_ios_s_10__half_cent_quantity_and_total_exact(db, st, mk):
    """IOS-S-10 — quantity and total of a half-cent order are exact.
    Rules: _sales_rows R3, R4 (regression part of BUG-2554)."""
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "2.00", "0.25")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert row(result, "SO-1").quantity == Decimal("2.00")
    # Then 2
    assert row(result, "SO-1").line_total == Decimal("0.25")
    # Then 3
    assert Decimal("0.12") <= row(result, "SO-1").unit_price <= Decimal("0.13")


def test_ios_s_11__direct_call_no_destination(db, st, mk):
    """IOS-S-11 — called directly, the helper returns row responses with no destination.
    Rules: _purchase_rows R12 (shape shared by all four helpers); _sales_rows R3, R4, R6."""
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "2.00", "50.00")
    result = svc._sales_rows(db, workspace_id=st.w1.id, item_id=st.i1.id, from_date=None, to_date=None)
    # Then 1
    assert type(result) is list
    assert len(result) == 1
    # Then 2
    assert isinstance(result[0], ItemOrderRowResponse)
    # Then 3
    assert result[0].order_type == "sales_order"
    assert base(result[0].order_number) == "SO-1"
    # Then 4
    assert result[0].unit_price == Decimal("25.00")
    assert result[0].line_total == Decimal("50.00")
    # Then 5
    assert result[0].destination_label is None


# =========================================================================== #
# ItemOrdersService._work_rows
# =========================================================================== #

def test_ios_w_01__only_deleted_line_not_listed(db, st, mk):
    """IOS-W-01 — a work order with only a deleted line of the item is not listed.
    Rules: _work_rows R1."""
    wo1 = mk.wo("WO-1")
    mk.wl(wo1, st.i1, "5.00", is_deleted=True)
    mk.wl(wo1, st.i2, "1.00")
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


def test_ios_w_02__no_type_deleted_line_no_order(db, st, mk):
    """IOS-W-02 — no type: a deleted work line does not bring its order in.
    Rules: _work_rows R1; get_orders_for_item R3."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    wo1 = mk.wo("WO-1")
    mk.wl(wo1, st.i1, "5.00", is_deleted=True)
    result = orders(db, st)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


@BUG_2550
def test_ios_w_03__every_field_of_work_row(db, st, mk):
    """IOS-W-03 — every field of a work row; deleted lines not counted.
    Rules: _work_rows R1, R4, R5 [BUG-2550]; get_orders_for_item R11."""
    wo1 = mk.wo("WO-1", created_at=noon(MID))
    mk.wl(wo1, st.i1, "2.00")
    mk.wl(wo1, st.i1, "3.00")
    mk.wl(wo1, st.i1, "10.00", is_deleted=True)
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 1
    assert len(result.items) == 1
    # Then 2
    assert row(result, "WO-1").order_type == "work_order"
    assert row(result, "WO-1").order_id == wo1.id
    # Then 3
    assert row(result, "WO-1").order_date == MID
    # Then 4
    assert row(result, "WO-1").quantity == Decimal("5.00")
    # Then 5
    assert row(result, "WO-1").status_name == "DRAFT"
    # Then 6
    assert row(result, "WO-1").unit_price is None
    assert row(result, "WO-1").line_total is None
    # Then 7
    assert row(result, "WO-1").account_name is None
    assert row(result, "WO-1").destination_label is None


@BUG_2550
def test_ios_w_04__in_progress_and_completed_status_text(db, st, mk):
    """IOS-W-04 — in-progress and completed work orders show their status text.
    Rules: _work_rows R2 (kept states), R5 [BUG-2550]."""
    wa = mk.wo("WO-A", status="IN_PROGRESS", created_at=noon(date(2026, 5, 11)))
    mk.wl(wa, st.i1, "1.00")
    wb = mk.wo("WO-B", status="COMPLETED", created_at=noon(MID))
    mk.wl(wb, st.i1, "1.00")
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 2
    # Then 2
    assert row(result, "WO-A").status_name == "IN_PROGRESS"
    # Then 3
    assert row(result, "WO-B").status_name == "COMPLETED"


@bug("BUG-2552")
def test_ios_w_05__voided_work_order_left_out(db, st, mk):
    """IOS-W-05 — a voided work order is left out.
    Rules: _work_rows R2 [BUG-2552]."""
    wv = mk.wo("WO-V", status="VOIDED")
    mk.wl(wv, st.i1, "50.00")
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


@bug("BUG-2553")
def test_ios_w_06__deleted_work_order_live_lines_left_out(db, st, mk):
    """IOS-W-06 — a deleted work order with live lines is left out.
    Rules: _work_rows R3 [BUG-2553]."""
    wd = mk.wo("WO-D", **mk.deleted_wo)
    mk.wl(wd, st.i1, "4.00")
    result = orders(db, st, order_type="work_order")
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


def test_ios_w_07__days_just_outside_not_listed(db, st, mk):
    """IOS-W-07 — work orders on the days just outside the range are not listed.
    Rules: _work_rows R4; get_orders_for_item R4."""
    wa = mk.wo("WO-A", created_at=noon(PRE))
    mk.wl(wa, st.i1, "1.00")
    wd = mk.wo("WO-D", created_at=noon(POST))
    mk.wl(wd, st.i1, "1.00")
    result = orders(db, st, order_type="work_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


@BUG_2550
def test_ios_w_08__first_and_last_day_listed(db, st, mk):
    """IOS-W-08 — work orders on the first and last day are listed.
    Rules: _work_rows R4, R5 [BUG-2550]; get_orders_for_item R4."""
    for n, d in (("WO-A", PRE), ("WO-B", START), ("WO-C", END), ("WO-D", POST)):
        w = mk.wo(n, created_at=noon(d))
        mk.wl(w, st.i1, "1.00")
    result = orders(db, st, order_type="work_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 2
    # Then 2
    assert numset(result) == {"WO-B", "WO-C"}


def test_ios_w_09__other_workspace_work_orders_not_listed(db, st, mk):
    """IOS-W-09 — work orders of the lower and higher workspace are not listed.
    Rules: get_orders_for_item R10; _work_rows R1."""
    wz = mk.wo("WO-Z", w0=True)
    mk.wl(wz, st.i1, "1.00")
    wn = mk.wo("WO-N", w2=True)
    mk.wl(wn, st.i1, "1.00")
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "1.00", "5.00")
    result = orders(db, st)
    # Then 1
    assert result.total == 1
    # Then 2
    assert nums(result) == ["PO-1"]


def test_ios_w_10__direct_call_only_deleted_line_empty(db, st, mk):
    """IOS-W-10 — called directly with only a deleted line, the helper returns an empty list.
    Rules: _purchase_rows R12 (shape shared by all four helpers); _work_rows R1."""
    wo1 = mk.wo("WO-1")
    mk.wl(wo1, st.i1, "5.00", is_deleted=True)
    result = svc._work_rows(db, workspace_id=st.w1.id, item_id=st.i1.id, from_date=None, to_date=None)
    # Then 1
    assert result == []
    assert type(result) is list


def test_ios_w_11__microsecond_before_and_midnight_after_not_listed(db, st, mk):
    """IOS-W-11 — work orders a microsecond before the range and at midnight after it are not listed.
    Rules: _work_rows R4; get_orders_for_item R4."""
    wa = mk.wo("WO-A", created_at=datetime(2026, 4, 30, 23, 59, 59, 999999))
    mk.wl(wa, st.i1, "1.00")
    wd = mk.wo("WO-D", created_at=datetime(2026, 6, 1, 0, 0, 0))
    mk.wl(wd, st.i1, "1.00")
    result = orders(db, st, order_type="work_order", from_date=START, to_date=END)
    # Then 1
    assert result.total == 0
    # Then 2
    assert result.items == []


# =========================================================================== #
# Priced quantity and zero totals — BUG-2490, BUG-2491 (OQ-33 answered)
# =========================================================================== #

@bug("BUG-2490", "BUG-2554")
def test_ios_oq33_01__partly_priced_divides_by_priced_quantity(db, st, mk):
    """IOS-OQ33-01 — a partly priced PO divides by the priced quantity only.
    Rules: _purchase_rows R7 [BUG-2490]."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "10.00", "50.00")
    mk.pl(p1, st.i1, "10.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("20.00")
    # Then 2
    assert row(result, "PO-1").unit_price == Decimal("5.00")
    # Then 3
    assert str(row(result, "PO-1").unit_price) == "5.00"
    # Then 4
    assert row(result, "PO-1").line_total == Decimal("50.00")


@bug("BUG-2491", "BUG-2554")
def test_ios_oq33_02__po_priced_zero_shows_zero(db, st, mk):
    """IOS-OQ33-02 — a PO priced at 0.00 shows line total 0.00 and unit price 0.00.
    Rules: _purchase_rows R8a [BUG-2491], R7."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "4.00", "0.00")
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").unit_price == Decimal("0.00")
    # Then 2
    assert row(result, "PO-1").line_total == Decimal("0.00")
    # Then 3
    assert str(row(result, "PO-1").line_total) == "0.00"
    # Then 4
    assert str(row(result, "PO-1").unit_price) == "0.00"


@bug("BUG-2490")
def test_ios_oq33_03__wholly_unpriced_no_unit_price(db, st, mk):
    """IOS-OQ33-03 — a wholly unpriced PO shows no unit price.
    Rules: _purchase_rows R7 [BUG-2490], R8a."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "5.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("5.00")
    # Then 2
    assert row(result, "PO-1").line_total is None
    # Then 3
    assert row(result, "PO-1").unit_price is None


def test_ios_oq33_04__quantity_zero_no_price_both_empty(db, st, mk):
    """IOS-OQ33-04 — quantity 0 and no price: both empty.
    Rules: _purchase_rows R7a, R8a."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "0.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").unit_price is None
    # Then 3
    assert row(result, "PO-1").line_total is None


@bug("BUG-2491")
def test_ios_oq33_05__sales_priced_zero_shows_zero(db, st, mk):
    """IOS-OQ33-05 — a sales order priced at 0.00 shows line total 0.00 and unit price 0.00.
    Rules: _sales_rows R5a [BUG-2491], R4."""
    s1 = mk.so("SO-1")
    mk.sl(s1, st.i1, "2.00", "0.00")
    result = orders(db, st, order_type="sales_order")
    # Then 1
    assert row(result, "SO-1").unit_price == Decimal("0.00")
    # Then 2
    assert row(result, "SO-1").line_total == Decimal("0.00")
    # Then 3
    assert str(row(result, "SO-1").line_total) == "0.00"


def test_ios_oq33_06__partly_priced_quantity_and_total(db, st, mk):
    """IOS-OQ33-06 — a partly priced PO: quantity counts every line, line total the priced ones.
    Rules: _purchase_rows R5, R6, R8 (the part of BUG-2490 that holds today)."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "10.00", "50.00")
    mk.pl(p1, st.i1, "10.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").quantity == Decimal("20.00")
    # Then 3
    assert row(result, "PO-1").line_total == Decimal("50.00")
    # Then 4
    assert str(row(result, "PO-1").line_total) == "50.00"


@bug("BUG-2490", "BUG-2554")
def test_ios_oq33_07__half_cent_over_priced_quantity_rounds_up(db, st, mk):
    """IOS-OQ33-07 — a half cent over the priced quantity rounds up, not to even.
    Rules: _purchase_rows R7 [BUG-2490]; _weighted_unit_price R3 [BUG-2554]."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "2.00", "0.25")
    mk.pl(p1, st.i1, "5.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("7.00")
    # Then 2
    assert row(result, "PO-1").unit_price == Decimal("0.13")
    # Then 3
    assert str(row(result, "PO-1").unit_price) == "0.13"
    # Then 4
    assert row(result, "PO-1").line_total == Decimal("0.25")


def test_ios_oq33_08__wholly_unpriced_quantity_no_total(db, st, mk):
    """IOS-OQ33-08 — a wholly unpriced PO: quantity shown, no line total.
    Rules: _purchase_rows R5, R6, R8a (the part that holds today)."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "5.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert result.total == 1
    # Then 2
    assert row(result, "PO-1").quantity == Decimal("5.00")
    # Then 3
    assert row(result, "PO-1").line_total is None


@bug("BUG-2490", "BUG-2491")
def test_ios_oq33_09__priced_quantity_zero_no_unit_price(db, st, mk):
    """IOS-OQ33-09 — a priced line of quantity 0 next to an unpriced one: no unit price, total 0.00.
    Rules: _purchase_rows R7 [BUG-2490] (priced quantity 0 -> None), R8a."""
    p1 = mk.po("PO-1")
    mk.pl(p1, st.i1, "0.00", "0.00")
    mk.pl(p1, st.i1, "5.00", None)
    result = orders(db, st, order_type="purchase_order")
    # Then 1
    assert row(result, "PO-1").quantity == Decimal("5.00")
    # Then 2
    assert row(result, "PO-1").unit_price is None
    # Then 3
    assert row(result, "PO-1").line_total == Decimal("0.00")
