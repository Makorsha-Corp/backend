"""Unit tests for app/services/item_summary_service.py.

Implements tests/unit/services/item_summary_service.cases.md (revision 4), one
test per card, in card order. Real Postgres session (`db` fixture), rolled back
after each test. Nothing is patched except what the cards name (the spies, the
failing `db.query` / `db.execute` of ISM-GS-15).

Every test builds the Standing rows (autouse fixture `st`); card names are the
attributes of `st` as the card writes them (`W1` -> `st.W1`, `F1.id` ->
`st.F1.id`). Given-row builders are methods of the `mk` fixture; a "W2 x" /
"W0 x" row is `w="W2"` / `w="W0"`. `# Then N` marks the checks of the card's
Then line N.
"""
# ruff: noqa: SIM117, C408  (Conventions: nested `with` blocks; builders keep keyword dicts)
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event, text

from app.core.exceptions import NotFoundError
from app.models.account import Account
from app.models.enums import InventoryTypeEnum
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.models.machine import Machine
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.order_workflow import OrderWorkflow
from app.models.po_receive_event import PoReceiveEvent, PoReceiveEventItem
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_line import ProductionLine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_type import WorkOrderType
from app.services.item_summary_service import (
    _dec,
    _est_value,
    item_summary_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = item_summary_service
STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE
SCRAP = InventoryTypeEnum.SCRAP

TD = date(2026, 6, 30)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
MISSING = 999999999


# Convention "GN(n)": the per-process number suffix (Parallel runs)
def GN(n):
    return f"{n}-{os.getpid()}"


OMIT = object()  # a ledger time "not passed": the column default fills it


def D(n):
    """Convention D(n) = TD - n days."""
    return TD - timedelta(days=n)


def NOON(d):
    """Convention NOON(d)."""
    return datetime.combine(d, time(12, 0))


def TS(n):
    """Convention TS(n): naive, whole days apart."""
    return datetime(2026, 1, 1, 12, 0, 0) + timedelta(days=n)  # noqa: DTZ001


def XID(k):
    """Convention XID(k): an explicit row id, unique per test process."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def dec(v):
    """A text money value "5.00" means Decimal("5.00"); None stays None."""
    return None if v is None else Decimal(v)


def today_g():
    """Conventions TODAY / G(n): TODAY = date.today(), read once per test."""
    today = date.today()  # noqa: DTZ011  (Conventions: date.today() is read unpatched)

    def G(n):
        return today - timedelta(days=n)

    G.today = today
    return G


# xfail markers (Conventions "xfail cards")
BUG_TITLES = {
    "BUG-2485": 'Item summary "Total spend" adds sales revenue to purchase spend',
    "BUG-2486": "Item summary counts lines of closed purchase orders as open",
    "BUG-2487": "Recent activity fails when a naive and a zone-aware ledger time meet",
    "BUG-2520": "Item summary shows another workspace's names and ids reached through links",
    "BUG-2521": "Item summary counts voided purchase orders",
    "BUG-2522": "Item summary lists sort names case-sensitively with no id tie-break",
    "BUG-2523": "Supplier top 10, highlights and a supplier's last price pick at random on ties",
    "BUG-2524": "Supplier figures treat an unpriced purchase line as price 0.00",
    "BUG-2525": "Item usage counts and lists deleted work orders and projects; a deleted section is still named",
    "BUG-2526": "Usage previews repeat a work order (component, formula, batch) once per line",
    "BUG-2527": "Recent activity links no order for current purchase receipts, corrections, returns and work orders",
    "BUG-2528": "Recent activity makes up to two reads per ledger entry",
    "BUG-2529": "An inventory ledger entry's time depends on the database's time zone",
    "BUG-1339": "Summary of a removed item still shows its factory and machine stock",
    "BUG-1338": "Item summary shows finished goods of a removed item",
    "BUG-1328": "Item summary counts finished goods of a deleted factory",
    "BUG-884": "Item summary still shows and totals stock held in a soft-deleted factory",
    "BUG-1326": "An item's product rows have no sort order",
    "BUG-932": "An item's tags on its summary have no sort order",
    "BUG-640": "Ledger lists ordered by `performed_at` only; ties in no fixed order",
    "BUG-1337": "A product ledger entry's time depends on the database's time zone",
}


def xf(*bugs, strict=True, raises=None):
    reason = "; ".join(f"{b}: {BUG_TITLES[b]}" for b in bugs)
    if raises is not None:
        return pytest.mark.xfail(strict=strict, reason=reason, raises=raises)
    return pytest.mark.xfail(strict=strict, reason=reason)


# --------------------------------------------------------------------------- #
# Conventions -> Standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def st(db):
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db)
    w0, w1, w2 = s.W0.id, s.W1.id, s.W2.id
    # W0
    s.F0 = _add(db, Factory(workspace_id=w0, name="Factory Zero", abbreviation="F0"))
    s.S0 = _add(db, Status(workspace_id=w0, name="Draft", comment="Stage"))
    s.AC0 = _add(db, Account(workspace_id=w0, name="Zero Co"))
    s.M0 = _add(db, Machine(workspace_id=w0, factory_id=s.F0.id, name="Zero Press"))
    s.WT0 = _add(db, WorkOrderType(workspace_id=w0, name="Repair"))
    s.L0 = _add(db, ProductionLine(workspace_id=w0, factory_id=s.F0.id, name="Zero Line"))
    s.I0 = _add(db, Item(workspace_id=w0, name="Bolt", name_normalized="bolt", unit="pcs"))
    # W1
    s.F1 = _add(db, Factory(workspace_id=w1, name="Factory One", abbreviation="F1"))
    s.F2 = _add(db, Factory(workspace_id=w1, name="Second Plant", abbreviation="F2"))
    s.FD = _add(db, Factory(workspace_id=w1, name="Old Plant", abbreviation="OP", is_deleted=True,
                            deleted_at=T0, deleted_by=s.U1.id))
    s.S1 = _add(db, Status(workspace_id=w1, name="Draft", comment="Stage"))
    s.AC1 = _add(db, Account(workspace_id=w1, name="Acme"))
    s.AC2 = _add(db, Account(workspace_id=w1, name="Beta"))
    s.M1 = _add(db, Machine(workspace_id=w1, factory_id=s.F1.id, name="Press 1"))
    s.WT1 = _add(db, WorkOrderType(workspace_id=w1, name="Repair"))
    s.L1 = _add(db, ProductionLine(workspace_id=w1, factory_id=s.F1.id, name="Line One"))
    s.I1 = _add(db, Item(workspace_id=w1, name="Bolt", name_normalized="bolt", unit="pcs",
                         description="Steel bolt", sku="B-1", created_by=s.U1.id))
    s.I2 = _add(db, Item(workspace_id=w1, name="Nut", name_normalized="nut", unit="pcs"))
    s.IR = _add(db, Item(workspace_id=w1, name="Old Gasket", name_normalized="old gasket", unit="pcs",
                         is_active=False))
    # W2
    s.F9 = _add(db, Factory(workspace_id=w2, name="Factory Nine", abbreviation="F9"))
    s.S9 = _add(db, Status(workspace_id=w2, name="Draft", comment="Stage"))
    s.AC9 = _add(db, Account(workspace_id=w2, name="Far Co"))
    s.M9 = _add(db, Machine(workspace_id=w2, factory_id=s.F9.id, name="Far Press"))
    s.WT9 = _add(db, WorkOrderType(workspace_id=w2, name="Repair"))
    s.L9 = _add(db, ProductionLine(workspace_id=w2, factory_id=s.F9.id, name="Far Line"))
    s.I9 = _add(db, Item(workspace_id=w2, name="Bolt", name_normalized="bolt", unit="pcs"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows. Builders flush; keyword arguments are the columns
# after "but". `w="W2"` / `w="W0"` swaps the workspace and every standing W1
# reference for its W2 / W0 counterpart (the item stays I1).
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, db, s):
        self.db = db
        self.s = s
        self._lines = {}

    def _v(self, w):
        s = self.s
        if w == "W2":
            return SimpleNamespace(W=s.W2, F=s.F9, S=s.S9, AC=s.AC9, M=s.M9, WT=s.WT9, L=s.L9)
        if w == "W0":
            return SimpleNamespace(W=s.W0, F=s.F0, S=s.S0, AC=s.AC0, M=s.M0, WT=s.WT0, L=s.L0)
        return SimpleNamespace(W=s.W1, F=s.F1, S=s.S1, AC=s.AC1, M=s.M1, WT=s.WT1, L=s.L1)

    def _row(self, model, fields, over):
        fields.update(over)
        fields = {k: v for k, v in fields.items() if v is not OMIT}
        return _add(self.db, model(**fields))

    def _line_no(self, key):
        n = self._lines.get(key, 0) + 1
        self._lines[key] = n
        return n

    # closed states, spread with **
    @property
    def voided(self):
        return {"voided": True, "void_note": "Void", "voided_at": T0, "voided_by": self.s.U1.id}

    @property
    def deleted_wo(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_line(self):
        return {"is_deleted": True, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_machine(self):
        return {"is_active": False, "is_deleted": True, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_section(self):
        return {"is_deleted": True, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_proj(self):
        return {"is_deleted": True, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_account(self):
        return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": self.s.U1.id}

    @property
    def deleted_stock(self):
        return {"is_active": False, "is_deleted": True, "deleted_at": T0, "deleted_by": self.s.U1.id}

    # orders
    def po(self, no, d, w="W1", **over):
        v = self._v(w)
        return self._row(PurchaseOrder, dict(
            workspace_id=v.W.id, po_number=no, destination_type="storage", destination_id=v.F.id,
            current_status_id=v.S.id, created_by=self.s.U1.id, account_id=v.AC.id, order_date=d,
            voided=False), over)

    def pol(self, P, qty, price, sub, **over):
        return self._row(PurchaseOrderItem, dict(
            workspace_id=P.workspace_id, purchase_order_id=P.id, line_number=self._line_no(("po", P.id)),
            item_id=self.s.I1.id, quantity_ordered=qty, unit_price=price, line_subtotal=sub,
            quantity_received=Decimal("0.00"), quantity_refunded=Decimal("0.00")), over)

    def to(self, no, at, w="W1", **over):
        v = self._v(w)
        return self._row(TransferOrder, dict(
            workspace_id=v.W.id, transfer_number=GN(no), source_location_type="storage",
            source_location_id=self.s.F1.id, destination_location_type="storage",
            destination_location_id=self.s.F2.id, current_status_id=v.S.id, created_by=self.s.U1.id,
            created_at=at), over)

    def tol(self, T, qty, **over):
        return self._row(TransferOrderItem, dict(
            workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=self._line_no(("to", T.id)),
            item_id=self.s.I1.id, quantity=qty), over)

    def so(self, no, d, w="W1", **over):
        v = self._v(w)
        return self._row(SalesOrder, dict(
            workspace_id=v.W.id, sales_order_number=GN(no), account_id=v.AC.id, factory_id=v.F.id,
            current_status_id=v.S.id, created_by=self.s.U1.id, order_date=d,
            total_amount=Decimal("0.00")), over)

    def sol(self, S, qty, price, total, **over):
        return self._row(SalesOrderItem, dict(
            workspace_id=S.workspace_id, sales_order_id=S.id, item_id=self.s.I1.id, description="Line",
            quantity_ordered=qty, unit_price=price, line_total=total), over)

    def eo(self, no, w="W1", **over):
        v = self._v(w)
        return self._row(ExpenseOrder, dict(
            workspace_id=v.W.id, expense_number=no, expense_category="other", expense_date=TD,
            subtotal=Decimal("0.00"), total_amount=Decimal("20.00"), created_by=self.s.U1.id,
            description="Power bill"), over)

    def wo(self, no, w="W1", **over):
        v = self._v(w)
        return self._row(WorkOrder, dict(
            workspace_id=v.W.id, work_order_number=no, title="Fix press", factory_id=v.F.id,
            work_order_type_id=v.WT.id, created_by=self.s.U1.id), over)

    def wol(self, O, **over):
        return self._row(WorkOrderItem, dict(
            workspace_id=O.workspace_id, work_order_id=O.id, item_id=self.s.I1.id,
            quantity=Decimal(1)), over)

    # stock
    def stock(self, F, type_, qty, avg, **over):
        return self._row(Inventory, dict(
            workspace_id=self.s.W1.id, item_id=self.s.I1.id, factory_id=F.id, inventory_type=type_,
            qty=qty, avg_price=avg, created_by=self.s.U1.id, is_deleted=False), over)

    def prod(self, F, qty, cost, sell, **over):
        return self._row(Product, dict(
            workspace_id=self.s.W1.id, item_id=self.s.I1.id, factory_id=F.id, qty=qty, avg_cost=cost,
            selling_price=sell, is_available_for_sale=True), over)

    def place(self, M, qty, req, **over):
        return self._row(MachineItem, dict(
            workspace_id=self.s.W1.id, machine_id=M.id, item_id=self.s.I1.id, qty=qty, req_qty=req,
            defective_qty=None), over)

    def mach(self, name, **over):
        return self._row(Machine, dict(workspace_id=self.s.W1.id, factory_id=self.s.F1.id, name=name), over)

    def sec(self, name, **over):
        return self._row(FactorySection, dict(workspace_id=self.s.W1.id, factory_id=self.s.F1.id, name=name), over)

    def assign(self, M, S, **over):
        return self._row(MachineSectionAssignment, dict(
            workspace_id=self.s.W1.id, machine_id=M.id, factory_section_id=S.id), over)

    # usage
    def pf(self, code, name, w="W1", **over):
        v = self._v(w)
        return self._row(ProductionFormula, dict(workspace_id=v.W.id, formula_code=code, name=name), over)

    def pfl(self, PF, role, **over):
        return self._row(ProductionFormulaItem, dict(
            workspace_id=PF.workspace_id, formula_id=PF.id, item_id=self.s.I1.id, item_role=role,
            quantity=2), over)

    def batch(self, no, d, w="W1", **over):
        v = self._v(w)
        return self._row(ProductionBatch, dict(
            workspace_id=v.W.id, batch_number=no, production_line_id=v.L.id, batch_date=d,
            status="draft"), over)

    def pbl(self, B, role, **over):
        return self._row(ProductionBatchItem, dict(
            workspace_id=B.workspace_id, batch_id=B.id, item_id=self.s.I1.id, item_role=role), over)

    def proj(self, name, w="W1", **over):
        v = self._v(w)
        return self._row(Project, dict(workspace_id=v.W.id, factory_id=v.F.id, name=name, description="Main"), over)

    def comp(self, P, name, **over):
        return self._row(ProjectComponent, dict(workspace_id=P.workspace_id, project_id=P.id, name=name), over)

    def pcl(self, C, **over):
        return self._row(ProjectComponentItem, dict(
            workspace_id=C.workspace_id, project_component_id=C.id, item_id=self.s.I1.id, qty=1), over)

    # ledgers
    def ient(self, F, at, **over):
        return self._row(InventoryLedger, dict(
            workspace_id=self.s.W1.id, factory_id=F.id, item_id=self.s.I1.id, inventory_type=STORAGE,
            transaction_type="manual_add", quantity=1, qty_before=0, qty_after=1,
            performed_by=self.s.U1.id, performed_at=at, source_type=None, source_id=None), over)

    def pent(self, F, at, **over):
        return self._row(ProductLedger, dict(
            workspace_id=self.s.W1.id, factory_id=F.id, item_id=self.s.I1.id, transaction_type="sale",
            quantity=1, qty_before=5, qty_after=4, performed_at=at), over)

    def ment(self, M, at, **over):
        return self._row(MachineItemLedger, dict(
            workspace_id=self.s.W1.id, machine_id=M.id, item_id=self.s.I1.id, transaction_type="manual_add",
            quantity=1, unit_cost=Decimal("2.00"), total_cost=Decimal("2.00"), qty_before=4, qty_after=5,
            source_type="manual", performed_by=self.s.U1.id, performed_at=at), over)

    # tags
    def tag(self, name, code, **over):
        return self._row(ItemTag, dict(
            workspace_id=self.s.W1.id, name=name, tag_code=code, color=None, icon=None,
            is_system_tag=False, is_active=True, usage_count=0), over)

    def tagged(self, X, T, **over):
        return self._row(ItemTagAssignment, dict(
            workspace_id=self.s.W1.id, item_id=X.id, tag_id=T.id, assigned_by=self.s.U1.id), over)

    # receive events / returns
    def rev(self, P, **over):
        return self._row(PoReceiveEvent, dict(
            workspace_id=P.workspace_id, purchase_order_id=P.id, event_type="receive", created_at=T0), over)

    def revi(self, E, L, **over):
        return self._row(PoReceiveEventItem, dict(
            receive_event_id=E.id, po_item_id=L.id, quantity_delta=Decimal(5)), over)

    def ret(self, P, no, **over):
        return self._row(PurchaseOrderReturn, dict(
            workspace_id=P.workspace_id, purchase_order_id=P.id, return_number=GN(no),
            created_by=self.s.U1.id), over)

    def reti(self, R, L, **over):
        return self._row(PurchaseOrderReturnItem, dict(
            workspace_id=R.workspace_id, return_id=R.id, po_item_id=L.id, item_id=self.s.I1.id,
            quantity_returned=Decimal("2.00")), over)

    def wf(self, seq, w="W1", **over):
        v = self._v(w)
        return self._row(OrderWorkflow, dict(
            workspace_id=v.W.id, name="PO flow", type="test", status_sequence=seq), over)


@pytest.fixture
def mk(db, st):
    return Builder(db, st)


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #

class Recorder:
    """Convention "recorder": records (statement, params) between start() and stop()."""

    def __init__(self, db):
        self.conn = db.connection()
        self.stmts = []

    def _rec(self, conn, cursor, statement, params, context, executemany):
        self.stmts.append((statement, params))

    def start(self):
        event.listen(self.conn, "before_cursor_execute", self._rec)
        return self

    def stop(self):
        event.remove(self.conn, "before_cursor_execute", self._rec)

    def contains(self, t):
        return [s for s, _ in self.stmts if t in s]

    def selects(self, t):
        return [s for s, _ in self.stmts if s.lstrip().upper().startswith("SELECT") and t in s]


def reread(db, model, row_id):
    """Convention "re-read X"."""
    db.expire_all()
    return db.query(model).filter(model.id == row_id).one()


def summary(db, st, item=None):
    return svc.get_summary(db, item_id=(item or st.I1).id, workspace_id=st.W1.id)


def accts(snap):
    """Convention accts(snap) of the `_supplier_stats` section."""
    return sorted(s.account_id for s in snap.suppliers)


# =========================================================================== #
# _dec
# =========================================================================== #

def test_ism_dec_01__none_becomes_zero():
    """ISM-DEC-01 — None becomes zero.
    Rules: _dec R1."""
    result = _dec(None)
    # Then 1
    assert result == Decimal(0)
    # Then 2
    assert isinstance(result, Decimal)


def test_ism_dec_02__two_place_decimal_keeps_places():
    """ISM-DEC-02 — a two-place Decimal keeps its places.
    Rules: _dec R2."""
    result = _dec(Decimal("5.00"))
    # Then 1
    assert str(result) == "5.00"


def test_ism_dec_03__int_becomes_whole_decimal():
    """ISM-DEC-03 — an int becomes a whole Decimal.
    Rules: _dec R2."""
    result = _dec(3)
    # Then 1
    assert str(result) == "3"


def test_ism_dec_04__float_goes_through_text():
    """ISM-DEC-04 — a float goes through its text, not its binary value.
    Rules: _dec R2."""
    result = _dec(0.1)
    # Then 1
    assert result == Decimal("0.1")
    # Then 2
    assert result != Decimal(0.1)  # noqa: RUF032  (the card compares with the binary value)


def test_ism_dec_05__int_zero_is_a_value():
    """ISM-DEC-05 — the int zero is a value, not empty.
    Rules: _dec R2."""
    result = _dec(0)
    # Then 1
    assert str(result) == "0"


def test_ism_dec_06__text_not_a_number_raises():
    """ISM-DEC-06 — text that is not a number raises.
    Rules: _dec R3, Errors R3."""
    # Then 1
    with pytest.raises(InvalidOperation):
        _dec("abc")


# =========================================================================== #
# _est_value
# =========================================================================== #

def test_ism_est_01__no_average_price_no_value():
    """ISM-EST-01 — no average price gives no value.
    Rules: _est_value R1."""
    result = _est_value(5, None)
    # Then 1
    assert result is None


def test_ism_est_02__zero_quantity_no_value():
    """ISM-EST-02 — zero quantity gives no value.
    Rules: _est_value R2."""
    result = _est_value(0, Decimal("2.50"))
    # Then 1
    assert result is None


def test_ism_est_03__negative_quantity_no_value():
    """ISM-EST-03 — negative quantity gives no value.
    Rules: _est_value R2."""
    result = _est_value(-1, Decimal("2.50"))
    # Then 1
    assert result is None


def test_ism_est_04__quantity_one_is_valued():
    """ISM-EST-04 — quantity one is valued.
    Rules: _est_value R2, R3."""
    result = _est_value(1, Decimal("2.50"))
    # Then 1
    assert result == Decimal("2.50")


def test_ism_est_05__price_times_quantity():
    """ISM-EST-05 — value is price times quantity.
    Rules: _est_value R3."""
    result = _est_value(7, Decimal("2.50"))
    # Then 1
    assert result == Decimal("17.50")
    # Then 2
    assert str(result) == "17.50"


def test_ism_est_06__zero_price_is_a_price():
    """ISM-EST-06 — a zero price is a price.
    Rules: _est_value R3."""
    result = _est_value(3, Decimal(0))
    # Then 1
    assert result is not None
    # Then 2
    assert result == Decimal(0)


def test_ism_est_07__value_not_rounded():
    """ISM-EST-07 — the value is not rounded.
    Rules: _est_value R3."""
    result = _est_value(3, Decimal("0.125"))
    # Then 1
    assert str(result) == "0.375"


# =========================================================================== #
# get_summary
# =========================================================================== #

def test_ism_gs_01__unknown_item_not_found(db, st):
    """ISM-GS-01 — an unknown item is not found.
    Rules: get_summary R1, Errors row 1."""
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_summary(db, item_id=MISSING, workspace_id=st.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"


def test_ism_gs_02__item_of_later_workspace_not_found(db, st):
    """ISM-GS-02 — an item of a later workspace is not found.
    Rules: get_summary R1, Errors row 1."""
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_summary(db, item_id=st.I9.id, workspace_id=st.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {st.I9.id} not found"


def test_ism_gs_03__item_of_earlier_workspace_not_found_nothing_read(db, st):
    """ISM-GS-03 — an item of an earlier workspace is not found, and nothing else is read.
    Rules: get_summary R1, Errors row 1."""
    _add(db, Inventory(workspace_id=st.W0.id, item_id=st.I0.id, factory_id=st.F0.id, inventory_type=STORAGE,
                       qty=7, avg_price=Decimal("1.00"), created_by=st.U1.id, is_deleted=False))
    item_id, ws_id = st.I0.id, st.W1.id
    rec = Recorder(db).start()
    try:
        # Then 1
        with pytest.raises(NotFoundError) as exc:
            svc.get_summary(db, item_id=item_id, workspace_id=ws_id)
    finally:
        rec.stop()
    # Then 2
    assert exc.value.detail == f"Item with ID {st.I0.id} not found"
    # Then 3
    assert rec.contains("inventory") == []
    # Then 4
    assert rec.contains("purchase_order_items") == []
    # Then 5
    assert rec.contains("machine_items") == []


def test_ism_gs_04__removed_item_is_summarised(db, st):
    """ISM-GS-04 — a removed item is summarised.
    Rules: get_summary R2."""
    result = svc.get_summary(db, item_id=st.IR.id, workspace_id=st.W1.id)
    # Then 1
    assert result.item.id == st.IR.id
    # Then 2
    assert result.item.is_active is False
    # Then 3
    assert result.item.name == "Old Gasket"


def test_ism_gs_05__item_block_carries_stored_fields(db, st):
    """ISM-GS-05 — the item block carries the stored fields.
    Rules: get_summary R3."""
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.item.id == st.I1.id
    assert result.item.workspace_id == st.W1.id
    # Then 2
    assert result.item.name == "Bolt"
    assert result.item.description == "Steel bolt"
    assert result.item.unit == "pcs"
    assert result.item.sku == "B-1"
    # Then 3
    assert result.item.is_active is True
    assert result.item.created_by == st.U1.id
    assert result.item.updated_by is None
    # Then 4
    assert result.item.created_at == st.I1.created_at
    assert result.item.updated_at == st.I1.updated_at


def test_ism_gs_06__tags_are_active_tags_with_fields(db, st, mk):
    """ISM-GS-06 — tags are the item's active tags with their fields.
    Rules: get_summary R3."""
    TR = mk.tag("Red", "red")
    TB = mk.tag("Blue", "blue", is_active=False)
    mk.tagged(st.I1, TR)
    mk.tagged(st.I1, TB)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [t.name for t in result.item.tags] == ["Red"]
    # Then 2
    assert result.item.tags[0].id == TR.id
    assert result.item.tags[0].tag_code == "red"
    # Then 3
    assert result.item.tags[0].color is None
    assert result.item.tags[0].icon is None
    assert result.item.tags[0].is_system_tag is False


def test_ism_gs_07__removed_items_tags_shown(db, st, mk):
    """ISM-GS-07 — a removed item's tags are shown.
    Rules: get_summary R3."""
    TR = mk.tag("Red", "red")
    mk.tagged(st.IR, TR)
    result = svc.get_summary(db, item_id=st.IR.id, workspace_id=st.W1.id)
    # Then 1
    assert [t.id for t in result.item.tags] == [TR.id]


def test_ism_gs_08__kpi_strip_adds_up_sections(db, st, mk):
    """ISM-GS-08 — the KPI strip adds up the sections.
    Rules: get_summary R4, R6."""
    M2 = mk.mach("Press 2")
    mk.stock(st.F1, STORAGE, 5, Decimal("2.00"))
    mk.stock(st.F1, DAMAGED, 2, None)
    mk.stock(st.F2, STORAGE, 3, Decimal("1.00"))
    mk.prod(st.F1, 4, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F2, 6, Decimal("1.00"), Decimal("2.00"))
    mk.place(st.M1, 2, None)
    mk.place(M2, 0, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.kpis.storage_qty_total == 8
    # Then 2
    assert result.kpis.factory_count_with_stock == 2
    # Then 3
    assert result.kpis.product_qty_total == 10
    # Then 4
    assert result.kpis.machine_placement_count == 2
    # Then 5
    assert len(result.inventory_rows) == 3
    assert len(result.product_rows) == 2
    assert len(result.machine_placements) == 2


def test_ism_gs_09__order_stat_windows_from_today(db, st, mk):
    """ISM-GS-09 — the order-stat windows run from today back 30 and 90 days, both ends in.
    Rules: get_summary R5, R6."""
    G = today_g()
    PA = mk.po("PO-A", G(0))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", G(30))
    mk.pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    PC = mk.po("PO-C", G(31))
    mk.pol(PC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00"))
    PD = mk.po("PO-D", G(90))
    mk.pol(PD, Decimal("8.00"), Decimal("1.00"), Decimal("8.00"))
    PE = mk.po("PO-E", G(91))
    mk.pol(PE, Decimal("16.00"), Decimal("1.00"), Decimal("16.00"))
    PF = mk.po("PO-F", G(-1))
    mk.pol(PF, Decimal("32.00"), Decimal("1.00"), Decimal("32.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.order_stats.days_30.purchase_qty == Decimal("3.00")
    # Then 2
    assert result.order_stats.days_30.line_count == 2
    # Then 3
    assert result.order_stats.days_30.total_spend == Decimal("3.00")
    # Then 4
    assert result.order_stats.days_90.purchase_qty == Decimal("15.00")
    # Then 5
    assert result.order_stats.days_90.line_count == 4
    # Then 6
    assert result.order_stats.all_time.purchase_qty == Decimal("63.00")
    # Then 7
    assert result.order_stats.all_time.line_count == 6


def test_ism_gs_10__pricing_and_supplier_windows_same_today(db, st, mk):
    """ISM-GS-10 — pricing and supplier windows use the same today.
    Rules: get_summary R5, R6."""
    G = today_g()
    PA = mk.po("PO-A", G(30))
    mk.pol(PA, Decimal("1.00"), Decimal("9.00"), Decimal("9.00"))
    PB = mk.po("PO-B", G(31), account_id=st.AC2.id)
    mk.pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.pricing.period.days_30.min_unit_price == Decimal("9.00")
    # Then 2
    assert result.pricing.period.days_90.min_unit_price == Decimal("1.00")
    # Then 3
    assert [s.account_id for s in result.supplier_stats.period.days_30.suppliers] == [st.AC1.id]
    # Then 4
    assert sorted(s.account_id for s in result.supplier_stats.period.days_90.suppliers) == sorted([st.AC1.id, st.AC2.id])


def test_ism_gs_11__other_workspaces_rows_never_reach_summary(db, st, mk):
    """ISM-GS-11 — another workspace's rows of a same-named item never reach the summary.
    Rules: get_summary R6; _inventory_rows R1; _order_stats_for_item R1."""
    G = today_g()
    _add(db, Inventory(workspace_id=st.W0.id, item_id=st.I0.id, factory_id=st.F0.id, inventory_type=STORAGE,
                       qty=7, avg_price=Decimal("1.00"), created_by=st.U1.id, is_deleted=False))
    P0 = mk.po("PO-Z", G(1), w="W0")
    mk.pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00"), item_id=st.I0.id)
    mk.stock(st.F1, STORAGE, 5, Decimal("2.00"))
    P1 = mk.po("PO-1", G(1))
    mk.pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    _add(db, Inventory(workspace_id=st.W2.id, item_id=st.I9.id, factory_id=st.F9.id, inventory_type=STORAGE,
                       qty=9, avg_price=Decimal("1.00"), created_by=st.U1.id, is_deleted=False))
    P9 = mk.po("PO-N", G(1), w="W2")
    mk.pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00"), item_id=st.I9.id)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.kpis.storage_qty_total == 5
    # Then 2
    assert result.kpis.factory_count_with_stock == 1
    # Then 3
    assert result.order_stats.all_time.purchase_qty == Decimal("1.00")
    # Then 4
    assert result.order_stats.all_time.line_count == 1


@xf("BUG-1339")
def test_ism_gs_12__removed_item_shows_no_stock(db, st, mk):
    """ISM-GS-12 — a removed item shows no factory or machine stock.
    Rules: get_summary R7 [BUG-1339]; _inventory_rows R8; _machine_placements R4."""
    SR = mk.stock(st.F1, STORAGE, 5, Decimal("2.00"), item_id=st.IR.id)
    mk.place(st.M1, 2, None, item_id=st.IR.id)
    result = svc.get_summary(db, item_id=st.IR.id, workspace_id=st.W1.id)
    # Then 1
    assert result.item.id == st.IR.id
    # Then 2
    assert result.inventory_rows == []
    # Then 3
    assert result.machine_placements == []
    # Then 4
    assert result.kpis.storage_qty_total == 0
    # Then 5
    assert result.kpis.factory_count_with_stock == 0
    # Then 6
    assert result.kpis.machine_placement_count == 0
    # Then 7
    row = reread(db, Inventory, SR.id)
    assert row.qty == 5
    assert row.is_deleted is False


def test_ism_gs_13__removed_item_still_shows_orders_prices_usage_history(db, st, mk):
    """ISM-GS-13 — a removed item still shows orders, prices, suppliers, usage and history.
    Rules: get_summary R7 (the part that holds today), R6."""
    G = today_g()
    P = mk.po("PO-1", G(2))
    mk.pol(P, Decimal("2.00"), Decimal("3.00"), Decimal("6.00"), item_id=st.IR.id)
    O = mk.wo("WO-1")
    mk.wol(O, item_id=st.IR.id)
    mk.ient(st.F1, TS(1), item_id=st.IR.id)
    result = svc.get_summary(db, item_id=st.IR.id, workspace_id=st.W1.id)
    # Then 1
    assert result.order_stats.all_time.purchase_qty == Decimal("2.00")
    # Then 2
    assert result.pricing.last_unit_price == Decimal("3.00")
    # Then 3
    assert [s.account_id for s in result.supplier_stats.period.all_time.suppliers] == [st.AC1.id]
    # Then 4
    assert result.usage_counts.work_order_line_count == 1
    # Then 5
    assert len(result.recent_activity) == 1


def test_ism_gs_14__pending_changes_stay_pending_no_commit_no_rollback(db, st, mk):
    """ISM-GS-14 — the call leaves pending changes pending and never commits or rolls back.
    Rules: get_summary R8."""
    mk.stock(st.F1, STORAGE, 5, Decimal("2.00"))
    db.commit()
    I2 = st.I2
    I2.description = "Edited"
    db.add(Status(workspace_id=st.W1.id, name="Pending", comment="Stage"))
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.item.id == st.I1.id
    # Then 2
    assert I2 in db.dirty
    assert len(db.dirty) == 1
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert rb.call_count == 0


def test_ism_gs_15__failing_read_reaches_caller_no_rollback(db, st):
    """ISM-GS-15 — a failing read reaches the caller unchanged, with no rollback.
    Rules: get_summary R8."""
    E = RuntimeError("boom")
    item_id, ws_id = st.I1.id, st.W1.id
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        with patch.object(db, "query", side_effect=E), patch.object(db, "execute", side_effect=E):
            with pytest.raises(RuntimeError) as exc:
                svc.get_summary(db, item_id=item_id, workspace_id=ws_id)
    # Then 1
    assert exc.value is E
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert cm.call_count == 0


# =========================================================================== #
# _factory_name_map / _machine_name_map / _machine_location_map
# =========================================================================== #

def test_ism_fn_01__every_factory_deleted_inactive_included(db, st):
    """ISM-FN-01 — every factory of the workspace, deleted and inactive included, no other workspace's.
    Rules: _factory_name_map R1."""
    FI = _add(db, Factory(workspace_id=st.W1.id, name="Idle Plant", abbreviation="IP", is_active=False))
    result = svc._factory_name_map(db, st.W1.id)
    # Then 1
    assert result == {st.F1.id: "Factory One", st.F2.id: "Second Plant", st.FD.id: "Old Plant", FI.id: "Idle Plant"}


def test_ism_fn_02__no_factories_empty_map(db, st):
    """ISM-FN-02 — a workspace with no factories gives an empty map.
    Rules: _factory_name_map R1."""
    WX = make_workspace(db)
    result = svc._factory_name_map(db, WX.id)
    # Then 1
    assert result == {}


def test_ism_mn_01__every_machine_deleted_included(db, st, mk):
    """ISM-MN-01 — every machine of the workspace, deleted included, no other workspace's.
    Rules: _machine_name_map R1."""
    MD = mk.mach("Press 4", **mk.deleted_machine)
    result = svc._machine_name_map(db, st.W1.id)
    # Then 1
    assert result == {st.M1.id: "Press 1", MD.id: "Press 4"}


def test_ism_ml_01__machine_with_section_every_field(db, st, mk):
    """ISM-ML-01 — a machine with a section gives every location field.
    Rules: _machine_location_map R1."""
    SA = mk.sec("Bay A")
    mk.assign(st.M1, SA)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert result[st.M1.id] == {"machine_name": "Press 1", "factory_section_id": SA.id, "factory_section_name": "Bay A", "factory_id": st.F1.id, "factory_name": "Factory One"}


def test_ism_ml_02__no_section_none_other_workspaces_no_entry(db, st):
    """ISM-ML-02 — no section gives None, and other workspaces' machines have no entry.
    Rules: _machine_location_map R1, R2."""
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert set(result) == {st.M1.id}
    # Then 2
    assert result[st.M1.id]["factory_section_id"] is None
    assert result[st.M1.id]["factory_section_name"] is None


def test_ism_ml_03__soft_deleted_machine_no_entry(db, st, mk):
    """ISM-ML-03 — a soft-deleted machine has no entry.
    Rules: _machine_location_map R1."""
    mk.mach("Press 4", **mk.deleted_machine)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert set(result) == {st.M1.id}


def test_ism_ml_04__machine_of_deleted_factory_has_entry(db, st, mk):
    """ISM-ML-04 — a machine of a deleted factory still has an entry.
    Rules: _machine_location_map R5."""
    MF = mk.mach("Lost Press", factory_id=st.FD.id)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert result[MF.id]["factory_id"] == st.FD.id
    assert result[MF.id]["factory_name"] == "Old Plant"


@xf("BUG-2520")
def test_ism_ml_05__machine_factory_in_later_workspace_no_entry(db, st, mk):
    """ISM-ML-05 — a machine whose factory is in a later workspace has no entry.
    Rules: _machine_location_map R3 [BUG-2520]."""
    MX = mk.mach("Stray Press", factory_id=st.F9.id)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert st.M1.id in result
    # Then 2
    assert MX.id not in result


@xf("BUG-2520")
def test_ism_ml_06__machine_factory_in_earlier_workspace_no_entry(db, st, mk):
    """ISM-ML-06 — a machine whose factory is in an earlier workspace has no entry.
    Rules: _machine_location_map R3 [BUG-2520]."""
    MX = mk.mach("Stray Press", factory_id=st.F0.id)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert st.M1.id in result
    # Then 2
    assert MX.id not in result


@xf("BUG-2520")
def test_ism_ml_07__section_of_other_workspace_is_none(db, st, mk):
    """ISM-ML-07 — a section of another workspace is treated as none.
    Rules: _machine_location_map R3 [BUG-2520]."""
    S9X = _add(db, FactorySection(workspace_id=st.W2.id, factory_id=st.F9.id, name="Far Bay"))
    mk.assign(st.M1, S9X)
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert result[st.M1.id]["factory_id"] == st.F1.id
    assert result[st.M1.id]["factory_name"] == "Factory One"
    # Then 2
    assert result[st.M1.id]["factory_section_id"] is None
    # Then 3
    assert result[st.M1.id]["factory_section_name"] is None


@xf("BUG-2525")
def test_ism_ml_08__soft_deleted_section_is_none_assignment_untouched(db, st, mk):
    """ISM-ML-08 — a soft-deleted section is treated as none, the assignment untouched.
    Rules: _machine_location_map R4 [BUG-2525]."""
    SD = mk.sec("Old Bay", **mk.deleted_section)
    A = mk.assign(st.M1, SD)
    sd_id, a_id, m1_id, f1_id = SD.id, A.id, st.M1.id, st.F1.id
    result = svc._machine_location_map(db, st.W1.id)
    # Then 1
    assert result[m1_id]["factory_id"] == f1_id
    # Then 2
    assert reread(db, MachineSectionAssignment, a_id).factory_section_id == sd_id
    # Then 3
    assert result[m1_id]["factory_section_id"] is None
    # Then 4
    assert result[m1_id]["factory_section_name"] is None


# =========================================================================== #
# _inventory_rows
# =========================================================================== #

def test_ism_iv_01__stock_row_every_field(db, st, mk):
    """ISM-IV-01 — a stock row gives every field.
    Rules: _inventory_rows R2; get_summary R6."""
    mk.stock(st.F1, STORAGE, 7, Decimal("2.50"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert len(result.inventory_rows) == 1
    # Then 2
    assert result.inventory_rows[0].factory_id == st.F1.id
    assert result.inventory_rows[0].factory_name == "Factory One"
    # Then 3
    assert result.inventory_rows[0].inventory_type == "STORAGE"
    # Then 4
    assert result.inventory_rows[0].qty == 7
    assert result.inventory_rows[0].avg_price == Decimal("2.50")
    # Then 5
    assert result.inventory_rows[0].est_value == Decimal("17.50")


def test_ism_iv_02__every_type_listed_storage_total_any_type_in_set(db, st, mk):
    """ISM-IV-02 — every type is listed; the storage total counts STORAGE only; any type puts a factory in the set.
    Rules: _inventory_rows R3, R4, R5; get_summary R4."""
    mk.stock(st.F1, STORAGE, 5, Decimal("2.00"))
    mk.stock(st.F1, WASTE, 1, None)
    mk.stock(st.F2, DAMAGED, 3, Decimal("1.00"))
    mk.stock(st.F2, SCRAP, 2, Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert sorted((r.factory_id, r.inventory_type) for r in result.inventory_rows) == sorted([(st.F1.id, "STORAGE"), (st.F1.id, "WASTE"), (st.F2.id, "DAMAGED"), (st.F2.id, "SCRAP")])
    # Then 2
    assert result.kpis.storage_qty_total == 5
    # Then 3
    assert result.kpis.factory_count_with_stock == 2
    # Then 4
    assert [r.est_value for r in result.inventory_rows if r.inventory_type == "WASTE"] == [None]


def test_ism_iv_03__no_storage_row_total_zero(db, st, mk):
    """ISM-IV-03 — no STORAGE row gives a storage total of 0.
    Rules: _inventory_rows R4, R5."""
    mk.stock(st.F2, DAMAGED, 3, Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.kpis.storage_qty_total == 0
    # Then 2
    assert result.kpis.factory_count_with_stock == 1


def test_ism_iv_04__quantity_zero_or_below_skipped(db, st, mk):
    """ISM-IV-04 — rows with quantity 0 or below are skipped.
    Rules: _inventory_rows R1, R5."""
    mk.stock(st.F1, STORAGE, 0, Decimal("2.00"))
    mk.stock(st.F1, DAMAGED, -2, Decimal("2.00"))
    mk.stock(st.F2, STORAGE, 1, Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [(r.factory_id, r.qty) for r in result.inventory_rows] == [(st.F2.id, 1)]
    # Then 2
    assert result.kpis.storage_qty_total == 1
    # Then 3
    assert result.kpis.factory_count_with_stock == 1


def test_ism_iv_05__soft_deleted_stock_not_shown(db, st, mk):
    """ISM-IV-05 — a soft-deleted stock row is not shown.
    Rules: _inventory_rows R1."""
    mk.stock(st.F1, STORAGE, 4, Decimal("2.00"), **mk.deleted_stock)
    mk.stock(st.F2, STORAGE, 2, Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.inventory_rows] == [st.F2.id]
    # Then 2
    assert result.kpis.storage_qty_total == 2


def test_ism_iv_06__other_workspaces_and_items_stock_not_shown(db, st, mk):
    """ISM-IV-06 — other workspaces' stock and other items' stock are not shown.
    Rules: _inventory_rows R1."""
    _add(db, Inventory(workspace_id=st.W0.id, item_id=st.I0.id, factory_id=st.F0.id, inventory_type=STORAGE,
                       qty=7, avg_price=Decimal("1.00"), created_by=st.U1.id, is_deleted=False))
    mk.stock(st.F1, STORAGE, 11, Decimal("1.00"), item_id=st.I2.id)
    mk.stock(st.F1, STORAGE, 5, Decimal("1.00"))
    _add(db, Inventory(workspace_id=st.W2.id, item_id=st.I9.id, factory_id=st.F9.id, inventory_type=STORAGE,
                       qty=9, avg_price=Decimal("1.00"), created_by=st.U1.id, is_deleted=False))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [(r.factory_id, r.qty) for r in result.inventory_rows] == [(st.F1.id, 5)]
    # Then 2
    assert result.kpis.storage_qty_total == 5
    # Then 3
    assert result.kpis.factory_count_with_stock == 1


def test_ism_iv_07__factory_missing_from_map_shows_hash_id(db, st, mk):
    """ISM-IV-07 — a factory missing from the name map shows "Factory #id".
    Rules: _inventory_rows R2."""
    mk.stock(st.F1, STORAGE, 3, Decimal("1.00"))
    result = svc._inventory_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={})
    # Then 1
    assert [r.factory_name for r in result[0]] == [f"Factory #{st.F1.id}"]
    # Then 2
    assert result[1] == 3
    # Then 3
    assert set(result[2]) == {st.F1.id}


def test_ism_iv_08__type_held_as_plain_string_shown_as_text(db, st, mk):
    """ISM-IV-08 — a type held as a plain string in the session is shown as its text.
    Rules: _inventory_rows R2."""
    mk.stock(st.F1, "DAMAGED", 2, Decimal("1.00"))
    result = svc._inventory_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "Factory One"})
    # Then 1
    assert [r.inventory_type for r in result[0]] == ["DAMAGED"]
    # Then 2
    assert result[1] == 0


def test_ism_iv_09__rows_sort_by_factory_name_then_type(db, st, mk):
    """ISM-IV-09 — rows sort by factory name, then type text.
    Rules: _inventory_rows R7."""
    mk.stock(st.F1, STORAGE, 1, Decimal("1.00"))
    mk.stock(st.F2, WASTE, 1, Decimal("1.00"))
    mk.stock(st.F1, DAMAGED, 1, Decimal("1.00"))
    mk.stock(st.F2, SCRAP, 1, Decimal("1.00"))
    result = svc._inventory_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "Beta", st.F2.id: "Alpha"})
    # Then 1
    assert [(r.factory_name, r.inventory_type) for r in result[0]] == [("Alpha", "SCRAP"), ("Alpha", "WASTE"), ("Beta", "DAMAGED"), ("Beta", "STORAGE")]


@xf("BUG-2522")
def test_ism_iv_10__factory_names_sort_case_insensitively(db, st, mk):
    """ISM-IV-10 — factory names sort case-insensitively.
    Rules: _inventory_rows R7 [BUG-2522]."""
    mk.stock(st.F1, STORAGE, 1, Decimal("1.00"))
    mk.stock(st.F2, STORAGE, 1, Decimal("1.00"))
    result = svc._inventory_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "Zeta", st.F2.id: "apex"})
    # Then 1
    assert [r.factory_name for r in result[0]] == ["apex", "Zeta"]


@xf("BUG-2522")
def test_ism_iv_11__equal_factory_names_fall_back_to_id(db, st, mk):
    """ISM-IV-11 — equal factory names fall back to factory id ascending.
    Rules: _inventory_rows R7 [BUG-2522]."""
    mk.stock(st.F2, STORAGE, 1, Decimal("1.00"))
    mk.stock(st.F1, STORAGE, 1, Decimal("1.00"))
    result = svc._inventory_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "mill", st.F2.id: "Mill"})
    # Then 1
    assert [r.factory_id for r in result[0]] == [st.F1.id, st.F2.id]


@xf("BUG-2520")
def test_ism_iv_12__stock_in_later_workspaces_factory_left_out(db, st, mk):
    """ISM-IV-12 — a stock row in a later workspace's factory is left out.
    Rules: _inventory_rows R6 [BUG-2520]."""
    mk.stock(st.F9, STORAGE, 4, Decimal("1.00"))
    mk.stock(st.F1, STORAGE, 5, Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.inventory_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.storage_qty_total == 5
    # Then 3
    assert result.kpis.factory_count_with_stock == 1


@xf("BUG-2520")
def test_ism_iv_13__stock_in_earlier_workspaces_factory_left_out(db, st, mk):
    """ISM-IV-13 — a stock row in an earlier workspace's factory is left out.
    Rules: _inventory_rows R6 [BUG-2520]."""
    mk.stock(st.F0, DAMAGED, 4, Decimal("1.00"))
    mk.stock(st.F1, STORAGE, 5, Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.inventory_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.factory_count_with_stock == 1


# =========================================================================== #
# _product_rows
# =========================================================================== #

def test_ism_pd_01__product_row_every_field_and_margin(db, st, mk):
    """ISM-PD-01 — a product row gives every field and a margin.
    Rules: _product_rows R2, R3."""
    mk.prod(st.F1, 4, Decimal("1.50"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert len(result.product_rows) == 1
    # Then 2
    assert result.product_rows[0].factory_id == st.F1.id
    assert result.product_rows[0].factory_name == "Factory One"
    # Then 3
    assert result.product_rows[0].qty == 4
    assert result.product_rows[0].avg_cost == Decimal("1.50")
    assert result.product_rows[0].selling_price == Decimal("2.00")
    # Then 4
    assert result.product_rows[0].is_available_for_sale is True
    # Then 5
    assert result.product_rows[0].margin_hint == Decimal("0.50")
    # Then 6
    assert result.kpis.product_qty_total == 4


def test_ism_pd_02__margin_may_be_negative_or_zero(db, st, mk):
    """ISM-PD-02 — the margin may be negative or zero.
    Rules: _product_rows R2."""
    mk.prod(st.F1, 1, Decimal("3.00"), Decimal("2.00"))
    mk.prod(st.F2, 1, Decimal("2.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert {r.factory_id: r.margin_hint for r in result.product_rows} == {st.F1.id: Decimal("-1.00"), st.F2.id: Decimal("0.00")}


def test_ism_pd_03__missing_cost_or_price_no_margin(db, st, mk):
    """ISM-PD-03 — a missing cost or price gives no margin.
    Rules: _product_rows R2."""
    mk.prod(st.F1, 1, None, Decimal("2.00"))
    mk.prod(st.F2, 1, Decimal("2.00"), None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert {r.factory_id: r.margin_hint for r in result.product_rows} == {st.F1.id: None, st.F2.id: None}


def test_ism_pd_04__not_for_sale_shown_false(db, st, mk):
    """ISM-PD-04 — not for sale is shown as False.
    Rules: _product_rows R2."""
    mk.prod(st.F1, 1, Decimal("1.00"), Decimal("2.00"), is_available_for_sale=False)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.product_rows[0].is_available_for_sale is False


def test_ism_pd_05__quantity_zero_skipped(db, st, mk):
    """ISM-PD-05 — rows with quantity 0 are skipped.
    Rules: _product_rows R1, R3."""
    mk.prod(st.F1, 0, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F2, 1, Decimal("1.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.product_rows] == [st.F2.id]
    # Then 2
    assert result.kpis.product_qty_total == 1


def test_ism_pd_06__negative_skipped_no_row_total_zero(db, st, mk):
    """ISM-PD-06 — a negative row is skipped and no row gives a total of 0.
    Rules: _product_rows R1, R3."""
    mk.prod(st.F1, -1, Decimal("1.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.product_rows == []
    # Then 2
    assert result.kpis.product_qty_total == 0


def test_ism_pd_07__other_workspaces_and_items_products_not_shown(db, st, mk):
    """ISM-PD-07 — other workspaces' and other items' products are not shown.
    Rules: _product_rows R1."""
    _add(db, Product(workspace_id=st.W0.id, item_id=st.I0.id, factory_id=st.F0.id, qty=7, avg_cost=Decimal("1.00"),
                     selling_price=Decimal("2.00"), is_available_for_sale=True))
    mk.prod(st.F1, 11, Decimal("1.00"), Decimal("2.00"), item_id=st.I2.id)
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"))
    _add(db, Product(workspace_id=st.W2.id, item_id=st.I9.id, factory_id=st.F9.id, qty=9, avg_cost=Decimal("1.00"),
                     selling_price=Decimal("2.00"), is_available_for_sale=True))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [(r.factory_id, r.qty) for r in result.product_rows] == [(st.F1.id, 5)]
    # Then 2
    assert result.kpis.product_qty_total == 5


def test_ism_pd_08__factory_missing_from_map_shows_hash_id(db, st, mk):
    """ISM-PD-08 — a factory missing from the name map shows "Factory #id".
    Rules: _product_rows R2."""
    mk.prod(st.F1, 3, Decimal("1.00"), Decimal("2.00"))
    result = svc._product_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={})
    # Then 1
    assert [r.factory_name for r in result[0]] == [f"Factory #{st.F1.id}"]
    # Then 2
    assert result[1] == 3


def test_ism_pd_09__rows_sort_by_factory_name(db, st, mk):
    """ISM-PD-09 — rows sort by factory name.
    Rules: _product_rows R5."""
    mk.prod(st.F1, 1, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F2, 1, Decimal("1.00"), Decimal("2.00"))
    result = svc._product_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "Beta", st.F2.id: "Alpha"})
    # Then 1
    assert [r.factory_name for r in result[0]] == ["Alpha", "Beta"]


@xf("BUG-2522")
def test_ism_pd_10__factory_names_sort_case_insensitively(db, st, mk):
    """ISM-PD-10 — factory names sort case-insensitively.
    Rules: _product_rows R5 [BUG-2522]."""
    mk.prod(st.F1, 1, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F2, 1, Decimal("1.00"), Decimal("2.00"))
    result = svc._product_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "Zeta", st.F2.id: "apex"})
    # Then 1
    assert [r.factory_name for r in result[0]] == ["apex", "Zeta"]


@xf("BUG-2522")
def test_ism_pd_11__equal_factory_names_fall_back_to_id(db, st, mk):
    """ISM-PD-11 — equal factory names fall back to factory id ascending.
    Rules: _product_rows R5 [BUG-2522]."""
    mk.prod(st.F2, 1, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F1, 1, Decimal("1.00"), Decimal("2.00"))
    result = svc._product_rows(db, item_id=st.I1.id, workspace_id=st.W1.id, factory_names={st.F1.id: "mill", st.F2.id: "Mill"})
    # Then 1
    assert [r.factory_id for r in result[0]] == [st.F1.id, st.F2.id]


@xf("BUG-2520")
def test_ism_pd_12__product_in_later_workspaces_factory_left_out(db, st, mk):
    """ISM-PD-12 — a product row in a later workspace's factory is left out.
    Rules: _product_rows R4 [BUG-2520]."""
    mk.prod(st.F9, 4, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.product_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.product_qty_total == 5


@xf("BUG-2520")
def test_ism_pd_13__product_in_earlier_workspaces_factory_left_out(db, st, mk):
    """ISM-PD-13 — a product row in an earlier workspace's factory is left out.
    Rules: _product_rows R4 [BUG-2520]."""
    mk.prod(st.F0, 4, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.product_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.product_qty_total == 5


def test_ism_pd_14__margin_non_zero_last_digit_exact(db, st, mk):
    """ISM-PD-14 — a margin with a non-zero last digit stays exact.
    Rules: _product_rows R2."""
    mk.prod(st.F1, 1, Decimal("1.25"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.product_rows[0].margin_hint == Decimal("0.75")


# =========================================================================== #
# _machine_placements
# =========================================================================== #

def test_ism_mp_01__placement_every_field(db, st, mk):
    """ISM-MP-01 — a placement gives every field from the stock row and the location map.
    Rules: _machine_placements R1, R2."""
    SA = mk.sec("Bay A")
    mk.assign(st.M1, SA)
    mk.place(st.M1, 3, 5, defective_qty=1)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert len(result.machine_placements) == 1
    # Then 2
    assert result.machine_placements[0].machine_id == st.M1.id
    assert result.machine_placements[0].machine_name == "Press 1"
    # Then 3
    assert result.machine_placements[0].factory_id == st.F1.id
    assert result.machine_placements[0].factory_name == "Factory One"
    # Then 4
    assert result.machine_placements[0].factory_section_id == SA.id
    assert result.machine_placements[0].factory_section_name == "Bay A"
    # Then 5
    assert result.machine_placements[0].qty == 3
    assert result.machine_placements[0].req_qty == 5
    assert result.machine_placements[0].defective_qty == 1
    # Then 6
    assert result.machine_placements[0].is_low_stock is True


def test_ism_mp_02__low_stock_only_below_requirement(db, st, mk):
    """ISM-MP-02 — low stock only when a requirement exists and quantity is below it.
    Rules: _machine_placements R2."""
    MA = mk.mach("Alpha")
    mk.place(MA, 2, None)
    MB = mk.mach("Bravo")
    mk.place(MB, 5, 5)
    MC = mk.mach("Charlie")
    mk.place(MC, 4, 5)
    ME = mk.mach("Echo")
    mk.place(ME, 0, 0)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert {p.machine_name: p.is_low_stock for p in result.machine_placements} == {"Alpha": False, "Bravo": False, "Charlie": True, "Echo": False}


def test_ism_mp_03__placement_holding_zero_listed_and_counted(db, st, mk):
    """ISM-MP-03 — a placement holding 0 is listed and counted.
    Rules: _machine_placements R1; get_summary R4."""
    mk.place(st.M1, 0, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [(p.machine_id, p.qty) for p in result.machine_placements] == [(st.M1.id, 0)]
    # Then 2
    assert result.kpis.machine_placement_count == 1


def test_ism_mp_04__other_workspaces_and_items_placements_not_shown(db, st, mk):
    """ISM-MP-04 — other workspaces' and other items' placements are not shown.
    Rules: _machine_placements R1."""
    _add(db, MachineItem(workspace_id=st.W0.id, machine_id=st.M0.id, item_id=st.I0.id, qty=1, req_qty=None, defective_qty=None))
    mk.place(st.M1, 7, None, item_id=st.I2.id)
    mk.place(st.M1, 2, None)
    _add(db, MachineItem(workspace_id=st.W2.id, machine_id=st.M9.id, item_id=st.I9.id, qty=1, req_qty=None, defective_qty=None))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [(p.machine_id, p.qty) for p in result.machine_placements] == [(st.M1.id, 2)]
    # Then 2
    assert result.kpis.machine_placement_count == 1


def test_ism_mp_05__low_stock_first_then_factory_section_machine(db, st, mk):
    """ISM-MP-05 — low stock first, then factory, section (none first), machine name.
    Rules: _machine_placements R5."""
    SB = mk.sec("Bay")
    MA = mk.mach("Alpha", factory_id=st.F2.id)
    mk.place(MA, 1, None)
    ME = mk.mach("Echo")
    mk.place(ME, 1, None)
    MB = mk.mach("Bravo")
    mk.assign(MB, SB)
    mk.place(MB, 1, None)
    MD = mk.mach("Delta", factory_id=st.F2.id)
    mk.place(MD, 1, 5)
    MC = mk.mach("Charlie")
    mk.place(MC, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_name for p in result.machine_placements] == ["Delta", "Charlie", "Echo", "Bravo", "Alpha"]


@xf("BUG-2522")
def test_ism_mp_06__machine_names_sort_case_insensitively(db, st, mk):
    """ISM-MP-06 — machine names sort case-insensitively.
    Rules: _machine_placements R5 [BUG-2522]."""
    MZ = mk.mach("Zeta")
    mk.place(MZ, 1, None)
    MA = mk.mach("apex")
    mk.place(MA, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_name for p in result.machine_placements] == ["apex", "Zeta"]


@xf("BUG-2522")
def test_ism_mp_07__equal_machine_names_fall_back_to_id(db, st, mk):
    """ISM-MP-07 — equal machine names fall back to machine id ascending.
    Rules: _machine_placements R5 [BUG-2522]."""
    MP1 = mk.mach("press")
    mk.place(MP1, 1, None)
    MP2 = mk.mach("Press")
    mk.place(MP2, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_id for p in result.machine_placements] == [MP1.id, MP2.id]


@xf("BUG-2522")
def test_ism_mp_08__section_names_sort_case_insensitively(db, st, mk):
    """ISM-MP-08 — section names sort case-insensitively.
    Rules: _machine_placements R5 [BUG-2522]."""
    SB = mk.sec("Bay")
    SN = mk.sec("annex")
    MX = mk.mach("Xray")
    mk.assign(MX, SB)
    mk.place(MX, 1, None)
    MY = mk.mach("Yank")
    mk.assign(MY, SN)
    mk.place(MY, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_name for p in result.machine_placements] == ["Yank", "Xray"]


@xf("BUG-2522")
def test_ism_mp_09__factory_names_sort_case_insensitively(db, st, mk):
    """ISM-MP-09 — factory names sort case-insensitively.
    Rules: _machine_placements R5 [BUG-2522]."""
    FL = _add(db, Factory(workspace_id=st.W1.id, name="annex works", abbreviation="AW"))
    MX = mk.mach("Xray")
    mk.place(MX, 1, None)
    MY = mk.mach("Yank", factory_id=FL.id)
    mk.place(MY, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_name for p in result.machine_placements] == ["Yank", "Xray"]


@xf("BUG-2520")
def test_ism_mp_10__placement_on_other_workspaces_machine_left_out(db, st, mk):
    """ISM-MP-10 — a placement on another workspace's machine is left out.
    Rules: _machine_placements R3 [BUG-2520]."""
    mk.place(st.M9, 4, None)
    mk.place(st.M1, 2, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_id for p in result.machine_placements] == [st.M1.id]
    # Then 2
    assert result.kpis.machine_placement_count == 1


@xf("BUG-2520")
def test_ism_mp_11__placement_on_machine_with_foreign_factory_left_out(db, st, mk):
    """ISM-MP-11 — a placement on a machine whose factory is another workspace's is left out.
    Rules: _machine_placements R3 [BUG-2520]."""
    MX = mk.mach("Stray Press", factory_id=st.F0.id)
    mk.place(MX, 4, None)
    mk.place(st.M1, 2, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_id for p in result.machine_placements] == [st.M1.id]
    # Then 2
    assert result.kpis.machine_placement_count == 1


# =========================================================================== #
# _order_stats_for_item
# =========================================================================== #

def test_ism_os_01__purchase_line_counts_qty_subtotal_one_line(db, st, mk):
    """ISM-OS-01 — a purchase line counts its quantity, subtotal and one line.
    Rules: _order_stats_for_item R2."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("10.00")
    # Then 2
    assert result.transfer_qty == 0
    assert result.sales_qty == 0
    # Then 3
    assert result.total_quantity == Decimal("10.00")
    # Then 4
    assert result.total_spend == Decimal("50.00")
    # Then 5
    assert result.line_count == 1


def test_ism_os_02__empty_subtotal_adds_zero_receipts_refunds_not_read(db, st, mk):
    """ISM-OS-02 — an empty subtotal adds 0; receipts and refunds are not read.
    Rules: _order_stats_for_item R2."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("10.00"), None, None, quantity_received=Decimal("10.00"))
    mk.pol(P, Decimal("4.00"), Decimal("1.00"), Decimal("4.00"), quantity_refunded=Decimal("4.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("14.00")
    # Then 2
    assert result.total_spend == Decimal("4.00")
    # Then 3
    assert result.line_count == 2


def test_ism_os_03__30_day_window_both_ends(db, st, mk):
    """ISM-OS-03 — the 30-day window includes both ends and nothing outside.
    Rules: _order_stats_for_item R3."""
    PA = mk.po("PO-A", D(30))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", D(31))
    mk.pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    PC = mk.po("PO-C", TD)
    mk.pol(PC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00"))
    PE = mk.po("PO-E", D(-1))
    mk.pol(PE, Decimal("8.00"), Decimal("1.00"), Decimal("8.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=TD)
    # Then 1
    assert result.purchase_qty == Decimal("5.00")
    # Then 2
    assert result.line_count == 2
    # Then 3
    assert result.total_spend == Decimal("5.00")


def test_ism_os_04__90_day_edge(db, st, mk):
    """ISM-OS-04 — the 90-day edge: day 90 in, day 91 out.
    Rules: _order_stats_for_item R3."""
    PA = mk.po("PO-A", D(90))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", D(91))
    mk.pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(90), to_date=TD)
    # Then 1
    assert result.purchase_qty == Decimal("1.00")
    # Then 2
    assert result.line_count == 1


def test_ism_os_05__no_order_date_uses_created_at(db, st, mk):
    """ISM-OS-05 — no order date: the date part of created_at decides; an order date wins over created_at.
    Rules: _order_stats_for_item R3."""
    PN = mk.po("PO-N", None, created_at=NOON(D(30)))
    mk.pol(PN, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PM = mk.po("PO-M", None, created_at=NOON(D(31)))
    mk.pol(PM, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    PQ = mk.po("PO-O", D(31), created_at=NOON(TD))
    mk.pol(PQ, Decimal("4.00"), Decimal("1.00"), Decimal("4.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=TD)
    # Then 1
    assert result.purchase_qty == Decimal("1.00")
    # Then 2
    assert result.line_count == 1


def test_ism_os_06__only_from_date_no_filter(db, st, mk):
    """ISM-OS-06 — only a from date: no date filter.
    Rules: _order_stats_for_item R6."""
    PA = mk.po("PO-A", D(400))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", TD)
    mk.pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("3.00")


def test_ism_os_07__only_to_date_no_filter(db, st, mk):
    """ISM-OS-07 — only a to date: no date filter.
    Rules: _order_stats_for_item R6."""
    PA = mk.po("PO-A", D(400))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", TD)
    mk.pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=D(30))
    # Then 1
    assert result.purchase_qty == Decimal("3.00")


def test_ism_os_08__transfer_lines_quantity_no_money_fractions_exact(db, st, mk):
    """ISM-OS-08 — transfer lines add quantity and lines, no money; fractions sum exactly.
    Rules: _order_stats_for_item R4, R7."""
    T = mk.to("TO-1", NOON(D(5)))
    mk.tol(T, Decimal("2.50"))
    mk.tol(T, Decimal("1.25"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.transfer_qty == Decimal("3.75")
    # Then 2
    assert result.total_quantity == Decimal("3.75")
    # Then 3
    assert result.total_spend == 0
    # Then 4
    assert result.line_count == 2
    # Then 5
    assert result.purchase_qty == 0


def test_ism_os_09__transfer_dated_by_created_at(db, st, mk):
    """ISM-OS-09 — transfer lines are dated by created_at, both window ends in.
    Rules: _order_stats_for_item R4."""
    TA = mk.to("TO-A", NOON(D(30)))
    mk.tol(TA, Decimal("1.00"))
    TB = mk.to("TO-B", NOON(D(31)))
    mk.tol(TB, Decimal("2.00"))
    TC = mk.to("TO-C", NOON(TD))
    mk.tol(TC, Decimal("4.00"))
    TE = mk.to("TO-E", NOON(D(-1)))
    mk.tol(TE, Decimal("8.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=TD)
    # Then 1
    assert result.transfer_qty == Decimal("5.00")
    # Then 2
    assert result.line_count == 2


def test_ism_os_10__only_this_item_and_workspace(db, st, mk):
    """ISM-OS-10 — only this item's lines on this workspace's orders count.
    Rules: _order_stats_for_item R1."""
    P0 = mk.po("PO-Z", D(5), w="W0")
    mk.pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00"))
    TZ0 = mk.to("TO-Z", NOON(D(5)), w="W0", source_location_id=st.F0.id, destination_location_id=st.F0.id)
    mk.tol(TZ0, Decimal("7.00"))
    P1 = mk.po("PO-1", D(5))
    mk.pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    mk.pol(P1, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), item_id=st.I2.id)
    P9 = mk.po("PO-N", D(5), w="W2")
    mk.pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00"))
    T9 = mk.to("TO-N", NOON(D(5)), w="W2", source_location_id=st.F9.id, destination_location_id=st.F9.id)
    mk.tol(T9, Decimal("9.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("1.00")
    # Then 2
    assert result.transfer_qty == 0
    # Then 3
    assert result.line_count == 1
    # Then 4
    assert result.total_spend == Decimal("1.00")


def test_ism_os_11__nothing_matching_all_zeros(db, st):
    """ISM-OS-11 — nothing matching gives all zeros.
    Rules: _order_stats_for_item Returns."""
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == 0
    assert result.transfer_qty == 0
    assert result.sales_qty == 0
    # Then 2
    assert result.total_quantity == 0
    assert result.total_spend == 0
    # Then 3
    assert result.line_count == 0


@xf("BUG-2521")
def test_ism_os_12__voided_order_lines_not_counted(db, st, mk):
    """ISM-OS-12 — lines of a voided purchase order are not counted.
    Rules: _order_stats_for_item R2a [BUG-2521]."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    PV = mk.po("PO-V", D(5), **mk.voided)
    mk.pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("10.00")
    # Then 2
    assert result.total_spend == Decimal("50.00")
    # Then 3
    assert result.line_count == 1


def test_ism_os_13__spend_is_stored_subtotal_not_qty_times_price(db, st, mk):
    """ISM-OS-13 — spend is the stored line subtotal, not quantity times price.
    Rules: _order_stats_for_item R2."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("45.00"))
    mk.pol(P, Decimal("3.00"), Decimal("2.00"), Decimal("7.50"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("13.00")
    # Then 2
    assert result.total_spend == Decimal("52.50")
    # Then 3
    assert result.line_count == 2


# =========================================================================== #
# _pricing_snapshot_from_po_lines
# =========================================================================== #

def test_ism_ps_01__min_max_unrounded_weighted_average():
    """ISM-PS-01 — min, max and the unrounded weighted average of priced lines.
    Rules: _pricing_snapshot_from_po_lines R1, R2, R3."""
    lines = [(Decimal("10.00"), Decimal("5.00")), (Decimal("100.00"), Decimal("1.00")), (Decimal("1.00"), Decimal("2.00")), (Decimal("10.00"), None)]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.min_unit_price == Decimal("1.00")
    # Then 2
    assert result.max_unit_price == Decimal("5.00")
    # Then 3
    assert result.avg_unit_price_weighted == Decimal("1.369369369369369369369369369")


def test_ism_ps_02__unpriced_line_adds_no_weight():
    """ISM-PS-02 — an unpriced line adds no weight.
    Rules: _pricing_snapshot_from_po_lines R1."""
    lines = [(Decimal("10.00"), None), (Decimal("2.00"), Decimal("3.00"))]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.avg_unit_price_weighted == Decimal(3)
    # Then 2
    assert result.min_unit_price == Decimal("3.00")
    assert result.max_unit_price == Decimal("3.00")


def test_ism_ps_03__zero_quantity_counts_for_min_max_not_average():
    """ISM-PS-03 — a zero-quantity line counts for min and max but not the average.
    Rules: _pricing_snapshot_from_po_lines R2, R3."""
    lines = [(Decimal("0.00"), Decimal("9.00")), (Decimal("2.00"), Decimal("3.00"))]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.max_unit_price == Decimal("9.00")
    # Then 2
    assert result.min_unit_price == Decimal("3.00")
    # Then 3
    assert result.avg_unit_price_weighted == Decimal(3)


def test_ism_ps_04__only_zero_quantities_no_average():
    """ISM-PS-04 — only zero quantities: no average, but min and max.
    Rules: _pricing_snapshot_from_po_lines R2, R3."""
    lines = [(Decimal("0.00"), Decimal("4.00"))]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.avg_unit_price_weighted is None
    # Then 2
    assert result.min_unit_price == Decimal("4.00")
    assert result.max_unit_price == Decimal("4.00")


def test_ism_ps_05__only_unpriced_all_empty():
    """ISM-PS-05 — only unpriced lines: all empty.
    Rules: _pricing_snapshot_from_po_lines R1, R2, R3."""
    lines = [(Decimal("5.00"), None)]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.min_unit_price is None
    assert result.max_unit_price is None
    assert result.avg_unit_price_weighted is None


def test_ism_ps_06__no_lines_all_empty():
    """ISM-PS-06 — no lines: all empty.
    Rules: _pricing_snapshot_from_po_lines R4."""
    lines = []
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.min_unit_price is None
    assert result.max_unit_price is None
    assert result.avg_unit_price_weighted is None


def test_ism_ps_07__half_cent_average_unrounded():
    """ISM-PS-07 — a half-cent average stays unrounded.
    Rules: _pricing_snapshot_from_po_lines R3."""
    lines = [(Decimal("1.00"), Decimal("2.00")), (Decimal("1.00"), Decimal("2.25"))]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.avg_unit_price_weighted == Decimal("2.125")


def test_ism_ps_08__priced_quantity_between_0_and_1_gives_average():
    """ISM-PS-08 — a priced quantity between 0 and 1 still gives an average.
    Rules: _pricing_snapshot_from_po_lines R3."""
    lines = [(Decimal("0.50"), Decimal("4.00")), (Decimal("0.25"), Decimal("1.00"))]
    result = svc._pricing_snapshot_from_po_lines(lines)
    # Then 1
    assert result.avg_unit_price_weighted == Decimal(3)
    # Then 2
    assert result.min_unit_price == Decimal("1.00")
    assert result.max_unit_price == Decimal("4.00")


# =========================================================================== #
# _pricing
# =========================================================================== #

def test_ism_prc_01__last_price_newest_date_then_greatest_line_id(db, st, mk):
    """ISM-PRC-01 — last price: newest date, then the greatest line id; an older line with a higher id loses.
    Rules: _pricing R2."""
    P1 = mk.po("PO-1", TD)
    mk.pol(P1, Decimal("1.00"), Decimal("7.00"), Decimal("7.00"))
    P2 = mk.po("PO-2", D(1))
    mk.pol(P2, Decimal("1.00"), Decimal("9.00"), Decimal("9.00"))
    mk.pol(P1, Decimal("1.00"), Decimal("6.00"), Decimal("6.00"))
    P3 = mk.po("PO-3", D(2))
    mk.pol(P3, Decimal("1.00"), Decimal("8.00"), Decimal("8.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("6.00")


def test_ism_prc_02__no_order_date_created_at_dates_last_price(db, st, mk):
    """ISM-PRC-02 — with no order date, created_at dates the line for the last price.
    Rules: _pricing R1, R2."""
    PN = mk.po("PO-N", None, created_at=NOON(TD))
    mk.pol(PN, Decimal("1.00"), Decimal("4.00"), Decimal("4.00"))
    PQ = mk.po("PO-O", D(1))
    mk.pol(PQ, Decimal("1.00"), Decimal("7.00"), Decimal("7.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("4.00")


def test_ism_prc_03__no_lines_no_last_price_empty_periods(db, st):
    """ISM-PRC-03 — no lines: no last price and empty periods.
    Rules: _pricing R2, R3."""
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price is None
    # Then 2
    assert result.period.all_time.min_unit_price is None
    assert result.period.all_time.avg_unit_price_weighted is None
    # Then 3
    assert result.period.days_30.max_unit_price is None


def test_ism_prc_04__newest_priced_line_when_older_unpriced(db, st, mk):
    """ISM-PRC-04 — the newest priced line gives the last price when an older line is unpriced.
    Rules: _pricing R2, R2a (the part that holds today)."""
    PA = mk.po("PO-A", D(2))
    mk.pol(PA, Decimal("1.00"), None, None)
    PB = mk.po("PO-B", TD)
    mk.pol(PB, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("5.00")


@xf("BUG-2524")
def test_ism_prc_05__unpriced_newest_line_does_not_hide_last_price(db, st, mk):
    """ISM-PRC-05 — an unpriced newest line does not hide the last real price.
    Rules: _pricing R2a [BUG-2524]."""
    PA = mk.po("PO-A", D(2))
    mk.pol(PA, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    PB = mk.po("PO-B", TD)
    mk.pol(PB, Decimal("1.00"), None, None)
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("5.00")


def test_ism_prc_06__three_periods_each_window(db, st, mk):
    """ISM-PRC-06 — the three periods each cover their window, both ends in, the future in all time only.
    Rules: _pricing R3."""
    PA = mk.po("PO-A", TD)
    mk.pol(PA, Decimal("1.00"), Decimal("9.00"), Decimal("9.00"))
    PB = mk.po("PO-B", D(30))
    mk.pol(PB, Decimal("1.00"), Decimal("8.00"), Decimal("8.00"))
    PC = mk.po("PO-C", D(31))
    mk.pol(PC, Decimal("1.00"), Decimal("2.00"), Decimal("2.00"))
    PD = mk.po("PO-D", D(90))
    mk.pol(PD, Decimal("1.00"), Decimal("7.00"), Decimal("7.00"))
    PE = mk.po("PO-E", D(91))
    mk.pol(PE, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PF = mk.po("PO-F", D(-1))
    mk.pol(PF, Decimal("1.00"), Decimal("0.50"), Decimal("0.50"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.period.days_30.min_unit_price == Decimal("8.00")
    # Then 2
    assert result.period.days_30.max_unit_price == Decimal("9.00")
    # Then 3
    assert result.period.days_90.min_unit_price == Decimal("2.00")
    # Then 4
    assert result.period.days_90.max_unit_price == Decimal("9.00")
    # Then 5
    assert result.period.all_time.min_unit_price == Decimal("0.50")
    # Then 6
    assert result.period.all_time.max_unit_price == Decimal("9.00")


def test_ism_prc_07__only_this_item_and_workspace_priced(db, st, mk):
    """ISM-PRC-07 — only this item's lines on this workspace's orders are priced.
    Rules: _pricing R1, R3."""
    P0 = mk.po("PO-Z", TD, w="W0")
    mk.pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    P1 = mk.po("PO-1", D(3))
    mk.pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    P2 = mk.po("PO-2", TD)
    mk.pol(P2, Decimal("1.00"), Decimal("0.10"), Decimal("0.10"), item_id=st.I2.id)
    P9 = mk.po("PO-N", TD, w="W2")
    mk.pol(P9, Decimal("1.00"), Decimal("9.00"), Decimal("9.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("5.00")
    # Then 2
    assert result.period.all_time.min_unit_price == Decimal("5.00")
    # Then 3
    assert result.period.all_time.max_unit_price == Decimal("5.00")
    # Then 4
    assert result.period.days_30.min_unit_price == Decimal("5.00")
    assert result.period.days_30.max_unit_price == Decimal("5.00")
    # Then 5
    assert result.period.days_90.min_unit_price == Decimal("5.00")
    assert result.period.days_90.max_unit_price == Decimal("5.00")


@xf("BUG-2521")
def test_ism_prc_08__voided_line_left_out_of_prices(db, st, mk):
    """ISM-PRC-08 — a voided order's line is left out of the prices.
    Rules: _pricing R1a [BUG-2521]."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    PV = mk.po("PO-V", TD, **mk.voided)
    mk.pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.last_unit_price == Decimal("5.00")
    # Then 2
    assert result.period.all_time.min_unit_price == Decimal("5.00")


@xf("BUG-2521")
def test_ism_prc_09__voided_open_line_not_open(db, st, mk):
    """ISM-PRC-09 — a voided order's open line is not open.
    Rules: _pricing R4a [BUG-2521]."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    PV = mk.po("PO-V", D(3), **mk.voided)
    mk.pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


# =========================================================================== #
# _supplier_stats
# =========================================================================== #

def test_ism_ss_01__each_supplier_figures_and_highlights(db, st, mk):
    """ISM-SS-01 — each supplier's figures and both highlights.
    Rules: _supplier_stats R1, R2."""
    PA = mk.po("PO-A", D(3))
    mk.pol(PA, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    PB = mk.po("PO-B", D(4), account_id=st.AC2.id)
    mk.pol(PB, Decimal("4.00"), Decimal("2.00"), Decimal("8.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert [(s.account_id, s.account_name, s.order_count, s.total_qty, s.total_spend) for s in result.period.all_time.suppliers] == [(st.AC1.id, "Acme", 1, Decimal("10.00"), Decimal("50.00")), (st.AC2.id, "Beta", 1, Decimal("4.00"), Decimal("8.00"))]
    # Then 2
    assert result.period.all_time.highlights.cheapest.account_id == st.AC2.id
    # Then 3
    assert result.period.all_time.highlights.most_frequent.account_id == st.AC2.id


def test_ism_ss_02__order_with_no_supplier_left_out(db, st, mk):
    """ISM-SS-02 — an order with no supplier is left out.
    Rules: _supplier_stats R1."""
    P = mk.po("PO-1", D(3), account_id=None)
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.period.all_time.suppliers == []
    # Then 2
    assert result.period.all_time.highlights.cheapest is None
    assert result.period.all_time.highlights.most_frequent is None


def test_ism_ss_03__30_day_period_edge(db, st, mk):
    """ISM-SS-03 — the 30-day period: day 30 in, day 31 out.
    Rules: _supplier_stats R2."""
    PA = mk.po("PO-A", D(30))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", D(31), account_id=st.AC2.id)
    mk.pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.days_30) == [st.AC1.id]
    # Then 2
    assert accts(result.period.days_90) == sorted([st.AC1.id, st.AC2.id])


def test_ism_ss_04__90_day_period_edge_future_all_time_only(db, st, mk):
    """ISM-SS-04 — the 90-day period: day 90 in, day 91 out; a future order in all time only.
    Rules: _supplier_stats R2."""
    AC3 = _add(db, Account(workspace_id=st.W1.id, name="Gamma"))
    PA = mk.po("PO-A", D(90))
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", D(91), account_id=st.AC2.id)
    mk.pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PC = mk.po("PO-C", D(-1), account_id=AC3.id)
    mk.pol(PC, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.days_90) == [st.AC1.id]
    # Then 2
    assert accts(result.period.all_time) == sorted([st.AC1.id, st.AC2.id, AC3.id])


def test_ism_ss_05__deleted_and_inactive_supplier_listed(db, st, mk):
    """ISM-SS-05 — a deleted and an inactive supplier are listed under their names.
    Rules: _supplier_stats R4."""
    ACD = _add(db, Account(workspace_id=st.W1.id, name="Gone Co", **mk.deleted_account))
    ACI = _add(db, Account(workspace_id=st.W1.id, name="Idle Co", is_active=False))
    PA = mk.po("PO-A", D(3), account_id=ACD.id)
    mk.pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    PB = mk.po("PO-B", D(3), account_id=ACI.id)
    mk.pol(PB, Decimal("1.00"), Decimal("2.00"), Decimal("2.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert sorted(s.account_name for s in result.period.all_time.suppliers) == ["Gone Co", "Idle Co"]


def test_ism_ss_06__other_workspaces_and_items_not_listed(db, st, mk):
    """ISM-SS-06 — other workspaces' orders and other items are not listed.
    Rules: _supplier_stats R1."""
    P0 = mk.po("PO-Z", D(3), w="W0")
    mk.pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    P1 = mk.po("PO-1", D(3))
    mk.pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    P2 = mk.po("PO-2", D(3), account_id=st.AC2.id)
    mk.pol(P2, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"), item_id=st.I2.id)
    P9 = mk.po("PO-N", D(3), w="W2")
    mk.pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.all_time) == [st.AC1.id]


@xf("BUG-2520")
def test_ism_ss_07__supplier_of_later_workspace_left_out(db, st, mk):
    """ISM-SS-07 — a supplier of a later workspace on this workspace's order is left out.
    Rules: _supplier_stats R3 [BUG-2520]."""
    P1 = mk.po("PO-1", D(3))
    mk.pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    PX = mk.po("PO-X", D(3), account_id=st.AC9.id)
    mk.pol(PX, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.all_time) == [st.AC1.id]
    # Then 2
    assert result.period.all_time.highlights.cheapest.account_id == st.AC1.id


@xf("BUG-2520")
def test_ism_ss_08__supplier_of_earlier_workspace_left_out(db, st, mk):
    """ISM-SS-08 — a supplier of an earlier workspace on this workspace's order is left out.
    Rules: _supplier_stats R3 [BUG-2520]."""
    P1 = mk.po("PO-1", D(3))
    mk.pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00"))
    PX = mk.po("PO-X", D(3), account_id=st.AC0.id)
    mk.pol(PX, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.all_time) == [st.AC1.id]


@xf("BUG-2521")
def test_ism_ss_09__voided_supplier_line_left_out(db, st, mk):
    """ISM-SS-09 — a voided order's supplier line is left out.
    Rules: _supplier_stats R2a [BUG-2521]."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    PV = mk.po("PO-V", D(3), account_id=st.AC2.id, **mk.voided)
    mk.pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert accts(result.period.all_time) == [st.AC1.id]
    # Then 2
    assert result.period.all_time.highlights.cheapest.account_id == st.AC1.id


@xf("BUG-2523", strict=False)
def test_ism_ss_10__last_price_on_shared_date_from_greatest_order_id(db, st, mk):
    """ISM-SS-10 — a supplier's last price on a shared date comes from the greatest order id.
    Rules: _supplier_rows_from_po_lines R6, _supplier_stats R5 [BUG-2523]."""
    PA = mk.po("PO-A", D(1))
    mk.pol(PA, Decimal("1.00"), Decimal("3.00"), Decimal("3.00"))
    PB = mk.po("PO-B", D(1))
    mk.pol(PB, Decimal("1.00"), Decimal("4.00"), Decimal("4.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.period.all_time.suppliers[0].last_unit_price == Decimal("4.00")


@xf("BUG-2523", strict=False)
def test_ism_ss_11__within_one_order_greatest_line_id_gives_price(db, st, mk):
    """ISM-SS-11 — within one order on the latest date, the greatest line id gives the price.
    Rules: _supplier_rows_from_po_lines R6, _supplier_stats R5 [BUG-2523]."""
    P = mk.po("PO-1", D(1))
    mk.pol(P, Decimal("1.00"), Decimal("3.00"), Decimal("3.00"))
    mk.pol(P, Decimal("1.00"), Decimal("4.00"), Decimal("4.00"))
    result = svc._supplier_stats(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.period.all_time.suppliers[0].last_unit_price == Decimal("4.00")


@xf("BUG-2523")
def test_ism_ss_12__supplier_query_has_order_by(db, st, mk):
    """ISM-SS-12 — the supplier query has an ORDER BY.
    Rules: _supplier_stats R5, _supplier_period_snapshot R3, _supplier_rows_from_po_lines R6 [BUG-2523]."""
    P = mk.po("PO-1", D(1))
    mk.pol(P, Decimal("1.00"), Decimal("3.00"), Decimal("3.00"))
    ws_id, item_id, ac1 = st.W1.id, st.I1.id, st.AC1.id
    rec = Recorder(db).start()
    try:
        result = svc._supplier_stats(db, workspace_id=ws_id, item_id=item_id, today=TD)
    finally:
        rec.stop()
    # Then 1
    assert accts(result.period.all_time) == [ac1]
    # Then 2
    sel = [s for s in rec.selects("purchase_order_items") if "accounts" in s]
    assert ["ORDER BY" in s for s in sel] == [True]


# =========================================================================== #
# _supplier_period_snapshot
# =========================================================================== #

def sup(rows):
    """Supplier tuples (Conventions): the quantity, price and subtotal texts as Decimals."""
    return [(a, n, p, dec(q), dec(u), dec(s), d) for a, n, p, q, u, s, d in rows]


def ids(snap):
    """Convention ids(snap)."""
    return [s.account_id for s in snap.suppliers]


def test_ism_sp_01__window_keeps_both_ends_nothing_future():
    """ISM-SP-01 — a window keeps rows from today back n days, both ends in, nothing in the future.
    Rules: _supplier_period_snapshot R1."""
    rows = sup([(1, "A", 10, "1.00", "1.00", "1.00", D(30)), (2, "B", 11, "1.00", "1.00", "1.00", D(31)), (3, "C", 12, "1.00", "1.00", "1.00", TD), (4, "D", 13, "1.00", "1.00", "1.00", D(-1))])
    result = svc._supplier_period_snapshot(rows, today=TD, days=30)
    # Then 1
    assert sorted(ids(result)) == [1, 3]


def test_ism_sp_02__no_days_keeps_every_row():
    """ISM-SP-02 — no days keeps every row, future included.
    Rules: _supplier_period_snapshot R1."""
    rows = sup([(1, "A", 10, "1.00", "1.00", "1.00", D(400)), (4, "D", 13, "1.00", "1.00", "1.00", D(-1))])
    result = svc._supplier_period_snapshot(rows, today=TD, days=None)
    # Then 1
    assert sorted(ids(result)) == [1, 4]


def test_ism_sp_03__row_with_no_date_left_out_of_window():
    """ISM-SP-03 — a row with no date is left out of a window.
    Rules: _supplier_period_snapshot R1."""
    rows = sup([(1, "A", 10, "1.00", "1.00", "1.00", None), (2, "B", 11, "1.00", "1.00", "1.00", TD)])
    result = svc._supplier_period_snapshot(rows, today=TD, days=30)
    # Then 1
    assert ids(result) == [2]


def test_ism_sp_04__sort_by_spend_at_most_ten():
    """ISM-SP-04 — suppliers sort by spend, high to low, at most 10.
    Rules: _supplier_period_snapshot R3."""
    rows = sup([(k, f"S{k}", 100 + k, "1.00", f"{k}.00", f"{k}.00", TD) for k in range(1, 12)])
    result = svc._supplier_period_snapshot(rows, today=TD, days=None)
    # Then 1
    assert ids(result) == [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]


def test_ism_sp_05__highlights_look_at_every_supplier():
    """ISM-SP-05 — highlights look at every supplier, not only the top 10.
    Rules: _supplier_period_snapshot R2."""
    rows = sup([(k, f"S{k}", 100 + k, "1.00", f"{k}.00", f"{k}.00", TD) for k in range(2, 12)])
    rows += sup([(1, "S1", 201, "1.00", "0.25", "0.25", TD), (1, "S1", 202, "1.00", "0.25", "0.25", TD)])
    result = svc._supplier_period_snapshot(rows, today=TD, days=None)
    # Then 1
    assert 1 not in ids(result)
    # Then 2
    assert result.highlights.cheapest.account_id == 1
    # Then 3
    assert result.highlights.most_frequent.account_id == 1


def test_ism_sp_06__no_rows_no_highlights_no_suppliers():
    """ISM-SP-06 — no rows: no highlights, no suppliers.
    Rules: _supplier_period_snapshot R4."""
    rows = []
    result = svc._supplier_period_snapshot(rows, today=TD, days=30)
    # Then 1
    assert result.suppliers == []
    # Then 2
    assert result.highlights.cheapest is None
    assert result.highlights.most_frequent is None


@xf("BUG-2523")
def test_ism_sp_07__equal_spend_sorts_by_account_id():
    """ISM-SP-07 — equal spend sorts by account id ascending.
    Rules: _supplier_period_snapshot R3 [BUG-2523]."""
    rows = sup([(7, "S7", 10, "1.00", "5.00", "5.00", TD), (3, "S3", 11, "1.00", "5.00", "5.00", TD)])
    result = svc._supplier_period_snapshot(rows, today=TD, days=None)
    # Then 1
    assert ids(result) == [3, 7]


@xf("BUG-2523")
def test_ism_sp_08__tie_at_tenth_place_keeps_lower_id():
    """ISM-SP-08 — a tie at tenth place keeps the lower account id.
    Rules: _supplier_period_snapshot R3 [BUG-2523]."""
    rows = sup([(k, f"S{k}", 100 + k, "1.00", f"{k}0.00", f"{k}0.00", TD) for k in range(1, 10)])
    rows += sup([(20, "S20", 300, "1.00", "1.00", "1.00", TD), (15, "S15", 301, "1.00", "1.00", "1.00", TD)])
    result = svc._supplier_period_snapshot(rows, today=TD, days=None)
    # Then 1
    assert ids(result)[9] == 15
    # Then 2
    assert 20 not in ids(result)


# =========================================================================== #
# _supplier_rows_from_po_lines
# =========================================================================== #

def test_ism_sr_01__one_row_per_supplier():
    """ISM-SR-01 — one row per supplier: orders, quantity, spend, average, last date and price.
    Rules: _supplier_rows_from_po_lines R1, R3, R4, R5."""
    rows = sup([(1, "Acme", 10, "10.00", "5.00", "50.00", D(5)), (1, "Acme", 11, "3.00", "4.00", "12.00", D(2)), (1, "Acme", 10, "2.00", "5.00", "10.00", D(5))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].account_id == 1
    assert result[0].order_count == 2
    # Then 3
    assert result[0].total_qty == Decimal("15.00")
    assert result[0].total_spend == Decimal("72.00")
    # Then 4
    assert result[0].avg_unit_price_weighted == Decimal("4.8")
    # Then 5
    assert result[0].last_order_date == D(2)
    assert result[0].last_unit_price == Decimal("4.00")


def test_ism_sr_02__row_with_no_account_skipped():
    """ISM-SR-02 — a row with no account is skipped.
    Rules: _supplier_rows_from_po_lines R1."""
    rows = sup([(None, "Nobody", 10, "1.00", "1.00", "1.00", D(1)), (2, "Beta", 11, "1.00", "1.00", "1.00", D(1))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert [r.account_id for r in result] == [2]


def test_ism_sr_03__name_is_last_non_empty_name():
    """ISM-SR-03 — the name is the last non-empty name seen.
    Rules: _supplier_rows_from_po_lines R2."""
    rows = sup([(1, "Acme", 10, "1.00", "1.00", "1.00", D(3)), (1, "Acme Ltd", 11, "1.00", "1.00", "1.00", D(2)), (1, "", 12, "1.00", "1.00", "1.00", D(1))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].account_name == "Acme Ltd"


def test_ism_sr_04__no_name_gives_account_hash_id():
    """ISM-SR-04 — no name at all gives "Account #id".
    Rules: _supplier_rows_from_po_lines R2."""
    rows = sup([(7, "", 10, "1.00", "1.00", "1.00", D(3)), (7, None, 11, "1.00", "1.00", "1.00", D(2))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].account_name == "Account #7"


def test_ism_sr_05__empty_subtotal_adds_zero_average_uses_qty_times_price():
    """ISM-SR-05 — an empty subtotal adds 0 to spend; the average uses quantity times price.
    Rules: _supplier_rows_from_po_lines R3, R4."""
    rows = sup([(1, "Acme", 10, "10.00", "5.00", "50.00", D(3)), (1, "Acme", 11, "4.00", "2.00", None, D(4))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].total_spend == Decimal("50.00")
    # Then 2
    assert result[0].total_qty == Decimal("14.00")
    # Then 3
    assert result[0].avg_unit_price_weighted == Decimal("4.142857142857142857142857143")


def test_ism_sr_06__total_quantity_zero_no_average():
    """ISM-SR-06 — total quantity 0 gives no average.
    Rules: _supplier_rows_from_po_lines R4."""
    rows = sup([(1, "Acme", 10, "0.00", "5.00", "0.00", D(3))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].avg_unit_price_weighted is None


def test_ism_sr_07__half_cent_average_unrounded():
    """ISM-SR-07 — a half-cent average stays unrounded.
    Rules: _supplier_rows_from_po_lines R4."""
    rows = sup([(1, "Acme", 10, "1.00", "2.00", "2.00", D(3)), (1, "Acme", 11, "1.00", "2.25", "2.25", D(4))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].avg_unit_price_weighted == Decimal("2.125")


def test_ism_sr_08__unpriced_line_counts_in_qty_spend_orders():
    """ISM-SR-08 — an unpriced line still counts in quantity, spend and orders.
    Rules: _supplier_rows_from_po_lines R3, R4a (the part that holds today)."""
    rows = sup([(1, "Acme", 10, "10.00", "5.00", "50.00", D(6)), (1, "Acme", 11, "10.00", None, None, D(5))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].total_qty == Decimal("20.00")
    # Then 2
    assert result[0].total_spend == Decimal("50.00")
    # Then 3
    assert result[0].order_count == 2


@xf("BUG-2524")
def test_ism_sr_09__average_leaves_unpriced_out():
    """ISM-SR-09 — the average leaves unpriced lines out.
    Rules: _supplier_rows_from_po_lines R4a [BUG-2524]."""
    rows = sup([(1, "Acme", 10, "10.00", "5.00", "50.00", D(6)), (1, "Acme", 11, "10.00", None, None, D(5))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].avg_unit_price_weighted == Decimal(5)


@xf("BUG-2524")
def test_ism_sr_10__only_unpriced_no_average():
    """ISM-SR-10 — only unpriced lines: no average.
    Rules: _supplier_rows_from_po_lines R4a [BUG-2524]."""
    rows = sup([(1, "Acme", 10, "10.00", None, None, D(5))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].avg_unit_price_weighted is None


def test_ism_sr_11__last_date_newest_wherever_in_input():
    """ISM-SR-11 — the last date is the newest line's date, wherever it sits in the input.
    Rules: _supplier_rows_from_po_lines R5."""
    rows = sup([(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", "4.00", "4.00", D(2)), (1, "Acme", 12, "1.00", "6.00", "6.00", D(8))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_order_date == D(2)
    # Then 2
    assert result[0].last_unit_price == Decimal("4.00")


def test_ism_sr_12__unpriced_newest_line_sets_last_date():
    """ISM-SR-12 — an unpriced newest line still sets the last date.
    Rules: _supplier_rows_from_po_lines R5, R5a (the part that holds today)."""
    rows = sup([(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", None, None, D(2))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_order_date == D(2)


@xf("BUG-2524")
def test_ism_sr_13__last_price_from_newest_priced_line():
    """ISM-SR-13 — the last price comes from the newest priced line.
    Rules: _supplier_rows_from_po_lines R5a [BUG-2524]."""
    rows = sup([(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", None, None, D(2))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_unit_price == Decimal("5.00")


@xf("BUG-2524")
def test_ism_sr_14__no_priced_line_no_last_price():
    """ISM-SR-14 — no priced line: no last price.
    Rules: _supplier_rows_from_po_lines R5a [BUG-2524]."""
    rows = sup([(1, "Acme", 10, "1.00", None, None, D(2))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_unit_price is None


@xf("BUG-2523")
def test_ism_sr_15__shared_latest_date_greater_order_id_gives_price():
    """ISM-SR-15 — on a shared latest date the greater order id gives the price.
    Rules: _supplier_rows_from_po_lines R6 [BUG-2523]."""
    rows = sup([(1, "Acme", 8, "1.00", "3.00", "3.00", D(1)), (1, "Acme", 9, "1.00", "4.00", "4.00", D(1))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_unit_price == Decimal("4.00")


def test_ism_sr_16__no_rows_no_suppliers():
    """ISM-SR-16 — no rows: no suppliers.
    Rules: _supplier_rows_from_po_lines R7."""
    rows = []
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result == []


@xf("BUG-2523")
def test_ism_sr_17__same_order_on_latest_date_later_input_gives_price():
    """ISM-SR-17 — two lines of one order on the latest date: the later one in input order gives the price.
    Rules: _supplier_rows_from_po_lines R6 [BUG-2523]."""
    rows = sup([(1, "Acme", 9, "1.00", "3.00", "3.00", D(1)), (1, "Acme", 9, "1.00", "4.00", "4.00", D(1))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_unit_price == Decimal("4.00")


def test_ism_sr_18__greater_order_id_wins_even_first():
    """ISM-SR-18 — on a shared latest date the greater order id wins even when it comes first.
    Rules: _supplier_rows_from_po_lines R6."""
    rows = sup([(1, "Acme", 9, "1.00", "4.00", "4.00", D(1)), (1, "Acme", 8, "1.00", "3.00", "3.00", D(1))])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_unit_price == Decimal("4.00")
    # Then 2
    assert result[0].last_order_date == D(1)


def test_ism_sr_19__all_undated_supplier_no_last_date_or_price():
    """ISM-SR-19 — a supplier whose lines all have no date: no last date and no last price.
    Rules: _supplier_rows_from_po_lines R5b, R3, R4."""
    rows = sup([(1, "Acme", 10, "2.00", "5.00", "10.00", None), (1, "Acme", 11, "3.00", "4.00", "12.00", None)])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].order_count == 2
    assert result[0].total_qty == Decimal("5.00")
    assert result[0].total_spend == Decimal("22.00")
    # Then 3
    assert result[0].avg_unit_price_weighted == Decimal("4.4")
    # Then 4
    assert result[0].last_order_date is None
    assert result[0].last_unit_price is None


def test_ism_sr_20__undated_line_never_replaces_dated_date_or_price():
    """ISM-SR-20 — an undated line never replaces a dated line's date or price.
    Rules: _supplier_rows_from_po_lines R5b, R5."""
    rows = sup([(1, "Acme", 11, "1.00", "9.00", "9.00", None), (1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 12, "1.00", "7.00", "7.00", None)])
    result = svc._supplier_rows_from_po_lines(rows)
    # Then 1
    assert result[0].last_order_date == D(5)
    # Then 2
    assert result[0].last_unit_price == Decimal("5.00")
    # Then 3
    assert result[0].order_count == 3
    assert result[0].total_qty == Decimal("3.00")


# =========================================================================== #
# _pick_cheapest_supplier / _pick_most_frequent_supplier
# =========================================================================== #

def test_ism_ch_01__lowest_average_wins():
    """ISM-CH-01 — the lowest average wins.
    Rules: _pick_cheapest_supplier R1, Returns."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "3.00", "3.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result.account_id == 2
    # Then 2
    assert result is next(r for r in rows if r.account_id == 2)


def test_ism_ch_02__equal_averages_more_orders_wins():
    """ISM-CH-02 — equal averages: more orders wins.
    Rules: _pick_cheapest_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "1.00", "4.00", "4.00", TD), (2, "B", 11, "1.00", "4.00", "4.00", TD), (2, "B", 12, "1.00", "4.00", "4.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result.account_id == 2


def test_ism_ch_03__no_average_not_a_candidate():
    """ISM-CH-03 — a supplier with no average is not a candidate.
    Rules: _pick_cheapest_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "0.00", "1.00", "0.00", TD), (2, "B", 11, "1.00", "9.00", "9.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result.account_id == 2


def test_ism_ch_04__zero_average_is_real_price_and_wins():
    """ISM-CH-04 — an average of 0.00 is a real price and wins.
    Rules: _pick_cheapest_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(2, "B", 10, "1.00", "1.00", "1.00", TD), (1, "A", 11, "5.00", "0.00", "0.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result.account_id == 1


def test_ism_ch_05__no_candidate_none():
    """ISM-CH-05 — no candidate gives None.
    Rules: _pick_cheapest_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "0.00", "1.00", "0.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result is None


def test_ism_ch_06__empty_list_none():
    """ISM-CH-06 — an empty list gives None.
    Rules: _pick_cheapest_supplier R1."""
    rows = []
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result is None


@xf("BUG-2523")
def test_ism_ch_07__full_tie_lowest_account_id():
    """ISM-CH-07 — a full tie goes to the lowest account id.
    Rules: _pick_cheapest_supplier R2 [BUG-2523]."""
    rows = svc._supplier_rows_from_po_lines(sup([(7, "S7", 10, "1.00", "4.00", "4.00", TD), (3, "S3", 11, "1.00", "4.00", "4.00", TD)]))
    result = svc._pick_cheapest_supplier(rows)
    # Then 1
    assert result.account_id == 3


def test_ism_mf_01__empty_list_none():
    """ISM-MF-01 — an empty list gives None.
    Rules: _pick_most_frequent_supplier R1."""
    rows = []
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result is None


def test_ism_mf_02__more_orders_wins_over_lower_price():
    """ISM-MF-02 — more orders wins over a lower price.
    Rules: _pick_most_frequent_supplier R1, Returns."""
    rows = svc._supplier_rows_from_po_lines(sup([(2, "B", 10, "1.00", "1.00", "1.00", TD), (1, "A", 11, "1.00", "9.00", "9.00", TD), (1, "A", 12, "1.00", "9.00", "9.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 1
    # Then 2
    assert result is next(r for r in rows if r.account_id == 1)


def test_ism_mf_03__equal_counts_lower_average_wins():
    """ISM-MF-03 — equal order counts: the lower average wins.
    Rules: _pick_most_frequent_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "3.00", "3.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 2


def test_ism_mf_04__no_average_ranks_last_on_count_tie():
    """ISM-MF-04 — no average ranks last on a count tie.
    Rules: _pick_most_frequent_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "0.00", "1.00", "0.00", TD), (2, "B", 11, "1.00", "7.00", "7.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 2


@xf("BUG-2523")
def test_ism_mf_05__zero_average_wins_count_tie():
    """ISM-MF-05 — an average of exactly 0 wins a count tie.
    Rules: _pick_most_frequent_supplier R2 [BUG-2523]."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "0.00", "0.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 2


@xf("BUG-2523")
def test_ism_mf_06__full_tie_lowest_account_id():
    """ISM-MF-06 — a full tie goes to the lowest account id.
    Rules: _pick_most_frequent_supplier R2 [BUG-2523]."""
    rows = svc._supplier_rows_from_po_lines(sup([(7, "S7", 10, "1.00", "4.00", "4.00", TD), (3, "S3", 11, "1.00", "4.00", "4.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 3


def test_ism_mf_07__average_above_stand_in_loses_to_no_average():
    """ISM-MF-07 — an average above the 999999999 stand-in loses a count tie to no average.
    Rules: _pick_most_frequent_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(1, "A", 10, "1.00", "999999999.50", "999999999.50", TD), (2, "B", 11, "0.00", "1.00", "0.00", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 2


def test_ism_mf_08__average_below_stand_in_beats_no_average():
    """ISM-MF-08 — an average just below the 999999999 stand-in beats no average.
    Rules: _pick_most_frequent_supplier R1."""
    rows = svc._supplier_rows_from_po_lines(sup([(2, "B", 11, "0.00", "1.00", "0.00", TD), (1, "A", 10, "1.00", "999999998.50", "999999998.50", TD)]))
    result = svc._pick_most_frequent_supplier(rows)
    # Then 1
    assert result.account_id == 1


# =========================================================================== #
# _usage (read through get_summary; uc = usage_counts, ud = usage_details)
# =========================================================================== #

def test_ism_us_01__each_count_is_line_count(db, st, mk):
    """ISM-US-01 — each count is a line count; one item used twice in a formula counts 2.
    Rules: _usage R1."""
    PF = mk.pf("FM-1", "Mix")
    mk.pfl(PF, "input")
    mk.pfl(PF, "output")
    B = mk.batch("B-1", TD)
    mk.pbl(B, "input")
    P = mk.proj("Bridge")
    C = mk.comp(P, "Deck")
    mk.pcl(C)
    O = mk.wo("WO-1")
    mk.wol(O)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc = result.usage_counts
    # Then 1
    assert uc.formula_count == 2
    # Then 2
    assert uc.batch_line_count == 1
    # Then 3
    assert uc.project_component_count == 1
    # Then 4
    assert uc.work_order_line_count == 1


def test_ism_us_02__inactive_formula_cancelled_batch_count_and_show(db, st, mk):
    """ISM-US-02 — an inactive formula and a cancelled batch count and show.
    Rules: _usage R1, R3."""
    PF = mk.pf("FM-1", "Mix", is_active=False)
    mk.pfl(PF, "input")
    B = mk.batch("B-1", TD, status="cancelled", updated_by=st.U1.id)
    mk.pbl(B, "output")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.formula_count == 1
    # Then 2
    assert uc.batch_line_count == 1
    # Then 3
    assert [f.formula_id for f in ud.formulas] == [PF.id]
    # Then 4
    assert [(b.batch_id, b.status) for b in ud.batches] == [(B.id, "cancelled")]


def test_ism_us_03__other_workspaces_and_items_neither_count_nor_show(db, st, mk):
    """ISM-US-03 — lines of other workspaces and of other items neither count nor show.
    Rules: _usage R1, R3."""
    O0 = mk.wo("WO-Z", w="W0")
    mk.wol(O0)
    PF0 = mk.pf("FM-Z", "Zero Mix", w="W0")
    mk.pfl(PF0, "input", item_id=st.I0.id)
    PF0X = mk.pf("FM-Y", "Zero Blend", w="W0")
    mk.pfl(PF0X, "input")
    B0 = mk.batch("B-Z", TD, w="W0")
    mk.pbl(B0, "input")
    P0 = mk.proj("Zero Bridge", w="W0")
    C0 = mk.comp(P0, "Zero Deck")
    mk.pcl(C0)
    O1 = mk.wo("WO-1")
    mk.wol(O1)
    mk.wol(O1, item_id=st.I2.id)
    PF1 = mk.pf("FM-1", "Mix")
    mk.pfl(PF1, "input")
    B1 = mk.batch("B-1", TD)
    mk.pbl(B1, "input")
    P1 = mk.proj("Bridge")
    C1 = mk.comp(P1, "Deck")
    mk.pcl(C1)
    O9 = mk.wo("WO-N", w="W2")
    mk.wol(O9)
    PF9 = mk.pf("FM-N", "Far Mix", w="W2")
    mk.pfl(PF9, "input")
    B9 = mk.batch("B-N", TD, w="W2")
    mk.pbl(B9, "input")
    P9 = mk.proj("Far Bridge", w="W2")
    C9 = mk.comp(P9, "Far Deck")
    mk.pcl(C9)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.work_order_line_count == 1
    # Then 2
    assert uc.formula_count == 1
    # Then 3
    assert uc.batch_line_count == 1
    # Then 4
    assert uc.project_component_count == 1
    # Then 5
    assert [w.work_order_id for w in ud.work_orders] == [O1.id]
    # Then 6
    assert [f.formula_id for f in ud.formulas] == [PF1.id]
    # Then 7
    assert [b.batch_id for b in ud.batches] == [B1.id]
    # Then 8
    assert [(p.project_id, p.component_id) for p in ud.projects] == [(P1.id, C1.id)]


def test_ism_us_04__preview_entries_carry_fields(db, st, mk):
    """ISM-US-04 — preview entries carry their fields.
    Rules: _usage R3."""
    PF = mk.pf("FM-1", "Mix")
    mk.pfl(PF, "input")
    B = mk.batch("B-1", TD)
    mk.pbl(B, "output")
    P = mk.proj("Bridge")
    C = mk.comp(P, "Deck")
    mk.pcl(C)
    O = mk.wo("WO-1")
    mk.wol(O)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [(f.formula_id, f.formula_code, f.name, f.item_role) for f in ud.formulas] == [(PF.id, "FM-1", "Mix", "input")]
    # Then 2
    assert [(b.batch_id, b.batch_number, b.item_role, b.status) for b in ud.batches] == [(B.id, "B-1", "output", "draft")]
    # Then 3
    assert [(p.project_id, p.project_name, p.component_id, p.component_name) for p in ud.projects] == [(P.id, "Bridge", C.id, "Deck")]
    # Then 4
    assert [(w.work_order_id, w.work_order_number, w.title) for w in ud.work_orders] == [(O.id, "WO-1", "Fix press")]


def test_ism_us_05__work_orders_five_newest_by_line_created_at(db, st, mk):
    """ISM-US-05 — work orders: five newest by line created_at.
    Rules: _usage R4."""
    for no, n in (("WO-A", 3), ("WO-B", 6), ("WO-C", 1), ("WO-D", 5), ("WO-E", 2), ("WO-F", 4)):
        mk.wol(mk.wo(no), created_at=TS(n))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [w.work_order_number for w in ud.work_orders] == ["WO-B", "WO-D", "WO-F", "WO-A", "WO-E"]
    # Then 2
    assert uc.work_order_line_count == 6


def test_ism_us_06__equal_created_at_line_id_high_to_low(db, st, mk):
    """ISM-US-06 — work orders: equal created_at falls back to line id high to low.
    Rules: _usage R4."""
    OC = mk.wo("WO-C")
    mk.wol(OC, created_at=TS(2))
    OA = mk.wo("WO-A")
    mk.wol(OA, created_at=TS(1))
    OB = mk.wo("WO-B")
    mk.wol(OB, created_at=TS(1))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [w.work_order_number for w in ud.work_orders] == ["WO-C", "WO-B", "WO-A"]


def test_ism_us_07__batches_five_newest_by_date_then_id(db, st, mk):
    """ISM-US-07 — batches: five newest by batch date, then batch id high to low.
    Rules: _usage R4."""
    for no, n in (("B-1", 3), ("B-2", 1), ("B-3", 1), ("B-4", 5), ("B-5", 2), ("B-6", 4)):
        mk.pbl(mk.batch(no, D(n)), "input")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [b.batch_number for b in ud.batches] == ["B-3", "B-2", "B-5", "B-1", "B-6"]
    # Then 2
    assert uc.batch_line_count == 6


def test_ism_us_08__formulas_by_name_then_role_five(db, st, mk):
    """ISM-US-08 — formulas: by name, then role, five at most.
    Rules: _usage R4."""
    FMD = mk.pf("FM-4", "Delta")
    mk.pfl(FMD, "input")
    FA = mk.pf("FM-1", "Alpha")
    mk.pfl(FA, "output")
    mk.pfl(FA, "input")
    FE = mk.pf("FM-5", "Echo")
    mk.pfl(FE, "input")
    FB = mk.pf("FM-2", "Bravo")
    mk.pfl(FB, "input")
    FF = mk.pf("FM-6", "Foxtrot")
    mk.pfl(FF, "input")
    FC = mk.pf("FM-3", "Charlie")
    mk.pfl(FC, "input")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [(f.name, f.item_role) for f in ud.formulas] == [("Alpha", "input"), ("Alpha", "output"), ("Bravo", "input"), ("Charlie", "input"), ("Delta", "input")]


def test_ism_us_09__projects_by_name_then_component_five(db, st, mk):
    """ISM-US-09 — projects: by project name, then component name, five at most.
    Rules: _usage R4."""
    PB = mk.proj("Bravo")
    mk.pcl(mk.comp(PB, "Deck"))
    mk.pcl(mk.comp(PB, "Arch"))
    PA = mk.proj("Alpha")
    mk.pcl(mk.comp(PA, "Wall"))
    PC = mk.proj("Charlie")
    mk.pcl(mk.comp(PC, "Roof"))
    mk.pcl(mk.comp(PC, "Gate"))
    mk.pcl(mk.comp(PC, "Base"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [(p.project_name, p.component_name) for p in ud.projects] == [("Alpha", "Wall"), ("Bravo", "Arch"), ("Bravo", "Deck"), ("Charlie", "Base"), ("Charlie", "Gate")]
    # Then 2
    assert uc.project_component_count == 6


@xf("BUG-2522", strict=False)
def test_ism_us_10__formula_names_sort_case_insensitively(db, st, mk):
    """ISM-US-10 — formula names sort case-insensitively.
    Rules: _usage R4 [BUG-2522]."""
    FZ = mk.pf("FM-1", "Zeta")
    mk.pfl(FZ, "input")
    FA = mk.pf("FM-2", "apex")
    mk.pfl(FA, "input")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [f.name for f in ud.formulas] == ["apex", "Zeta"]


@xf("BUG-2522", strict=False)
def test_ism_us_11__six_formulas_one_name_five_lowest_ids(db, st, mk):
    """ISM-US-11 — six formulas of one name: the five lowest formula ids are shown.
    Rules: _usage R4 [BUG-2522]."""
    FK = []
    for k in range(1, 7):
        f = mk.pf(f"FM-{k}", "Mix")
        mk.pfl(f, "input")
        FK.append(f)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [f.formula_id for f in ud.formulas] == [FK[0].id, FK[1].id, FK[2].id, FK[3].id, FK[4].id]


def _after_order_by(rec, table):
    """The text after ORDER BY of each recorded SELECT reading `table` with LIMIT."""
    return [s.split("ORDER BY", 1)[1] if "ORDER BY" in s else "" for s in rec.selects(table) if "LIMIT" in s]


@xf("BUG-2522")
def test_ism_us_12__formula_preview_orders_by_formula_id(db, st, mk):
    """ISM-US-12 — the formula preview orders by the formula id after name and role.
    Rules: _usage R4 [BUG-2522] (HR-6 line)."""
    PF = mk.pf("FM-1", "Mix")
    mk.pfl(PF, "input")
    pf_id, item_id, ws_id = PF.id, st.I1.id, st.W1.id
    rec = Recorder(db).start()
    try:
        result = svc.get_summary(db, item_id=item_id, workspace_id=ws_id)
    finally:
        rec.stop()
    ud = result.usage_details
    # Then 1
    assert [f.formula_id for f in ud.formulas] == [pf_id]
    # Then 2
    tails = _after_order_by(rec, "production_formula_items")
    assert tails and all("production_formulas.id" in t for t in tails)


@xf("BUG-2522", strict=False)
def test_ism_us_13__project_names_sort_case_insensitively(db, st, mk):
    """ISM-US-13 — project names sort case-insensitively.
    Rules: _usage R4 [BUG-2522]."""
    PZ = mk.proj("Zeta")
    mk.pcl(mk.comp(PZ, "Deck"))
    PA = mk.proj("apex")
    mk.pcl(mk.comp(PA, "Deck"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [p.project_name for p in ud.projects] == ["apex", "Zeta"]


@xf("BUG-2522")
def test_ism_us_14__project_preview_orders_by_component_id(db, st, mk):
    """ISM-US-14 — the project preview orders by the component id after the names.
    Rules: _usage R4 [BUG-2522] (HR-6 line)."""
    P = mk.proj("Bridge")
    C = mk.comp(P, "Deck")
    mk.pcl(C)
    c_id, item_id, ws_id = C.id, st.I1.id, st.W1.id
    rec = Recorder(db).start()
    try:
        result = svc.get_summary(db, item_id=item_id, workspace_id=ws_id)
    finally:
        rec.stop()
    ud = result.usage_details
    # Then 1
    assert [p.component_id for p in ud.projects] == [c_id]
    # Then 2
    tails = _after_order_by(rec, "project_component_items")
    assert tails and all("project_components.id" in t for t in tails)


@xf("BUG-2525")
def test_ism_us_15__deleted_work_order_line_neither_counts_nor_shows(db, st, mk):
    """ISM-US-15 — a deleted work-order line neither counts nor shows.
    Rules: _usage R2, R5 [BUG-2525]."""
    O1 = mk.wo("WO-1")
    mk.wol(O1, **mk.deleted_line)
    O2 = mk.wo("WO-2")
    mk.wol(O2)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.work_order_line_count == 1
    # Then 2
    assert [w.work_order_number for w in ud.work_orders] == ["WO-2"]


@xf("BUG-2525")
def test_ism_us_16__line_of_deleted_work_order_neither_counts_nor_shows(db, st, mk):
    """ISM-US-16 — a line of a deleted work order neither counts nor shows.
    Rules: _usage R2, R5 [BUG-2525]."""
    OD = mk.wo("WO-DEL", **mk.deleted_wo)
    mk.wol(OD)
    O2 = mk.wo("WO-2")
    mk.wol(O2)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.work_order_line_count == 1
    # Then 2
    assert [w.work_order_number for w in ud.work_orders] == ["WO-2"]


@xf("BUG-2525")
def test_ism_us_17__component_of_deleted_project_neither_counts_nor_shows(db, st, mk):
    """ISM-US-17 — a component of a deleted project neither counts nor shows.
    Rules: _usage R2, R5 [BUG-2525]."""
    PDL = mk.proj("Old Bridge", **mk.deleted_proj)
    mk.pcl(mk.comp(PDL, "Deck"))
    P = mk.proj("Bridge")
    mk.pcl(mk.comp(P, "Deck"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.project_component_count == 1
    # Then 2
    assert [p.project_id for p in ud.projects] == [P.id]


def test_ism_us_18__two_lines_on_one_work_order_count_two(db, st, mk):
    """ISM-US-18 — two lines on one work order count as two lines.
    Rules: _usage R1, R4a (the part that holds today)."""
    O = mk.wo("WO-1")
    mk.wol(O, created_at=TS(1))
    mk.wol(O, created_at=TS(5))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc = result.usage_counts
    # Then 1
    assert uc.work_order_line_count == 2


@xf("BUG-2526")
def test_ism_us_19__work_order_appears_once_by_newest_line(db, st, mk):
    """ISM-US-19 — a work order appears once, placed by its newest line.
    Rules: _usage R4a [BUG-2526]."""
    O1 = mk.wo("WO-1")
    mk.wol(O1, created_at=TS(1))
    mk.wol(O1, created_at=TS(5))
    O2 = mk.wo("WO-2")
    mk.wol(O2, created_at=TS(3))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [w.work_order_number for w in ud.work_orders] == ["WO-1", "WO-2"]


@xf("BUG-2526")
def test_ism_us_20__repeated_lines_do_not_take_five_places(db, st, mk):
    """ISM-US-20 — repeated lines do not take the five places.
    Rules: _usage R4a [BUG-2526]."""
    O1 = mk.wo("WO-1")
    for n in (6, 7, 8, 9, 10):
        mk.wol(O1, created_at=TS(n))
    O2 = mk.wo("WO-2")
    mk.wol(O2, created_at=TS(2))
    O3 = mk.wo("WO-3")
    mk.wol(O3, created_at=TS(1))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    ud = result.usage_details
    # Then 1
    assert [w.work_order_number for w in ud.work_orders] == ["WO-1", "WO-2", "WO-3"]


@xf("BUG-2526")
def test_ism_us_21__component_appears_once(db, st, mk):
    """ISM-US-21 — a component appears once.
    Rules: _usage R4a [BUG-2526]."""
    P = mk.proj("Bridge")
    C = mk.comp(P, "Deck")
    mk.pcl(C)
    mk.pcl(C)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [p.component_id for p in ud.projects] == [C.id]
    # Then 2
    assert uc.project_component_count == 2


@xf("BUG-2526")
def test_ism_us_22__formula_appears_once_per_role(db, st, mk):
    """ISM-US-22 — a formula appears once per role.
    Rules: _usage R4a [BUG-2526]."""
    PF = mk.pf("FM-1", "Mix")
    mk.pfl(PF, "input")
    mk.pfl(PF, "input")
    mk.pfl(PF, "output")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [(f.formula_id, f.item_role) for f in ud.formulas] == [(PF.id, "input"), (PF.id, "output")]
    # Then 2
    assert uc.formula_count == 3


@xf("BUG-2526")
def test_ism_us_23__batch_appears_once_per_role(db, st, mk):
    """ISM-US-23 — a batch appears once per role.
    Rules: _usage R4a [BUG-2526]."""
    B = mk.batch("B-1", TD)
    mk.pbl(B, "input")
    mk.pbl(B, "input")
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert [(b.batch_id, b.item_role) for b in ud.batches] == [(B.id, "input")]
    # Then 2
    assert uc.batch_line_count == 2


@xf("BUG-2520")
def test_ism_us_24__line_on_other_workspaces_formula_hidden(db, st, mk):
    """ISM-US-24 — a line on another workspace's formula neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    PF0 = mk.pf("FM-Z", "Zero Mix", w="W0")
    mk.pfl(PF0, "input", workspace_id=st.W1.id)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.formula_count == 0
    # Then 2
    assert ud.formulas == []


@xf("BUG-2520")
def test_ism_us_25__line_on_other_workspaces_batch_hidden(db, st, mk):
    """ISM-US-25 — a line on another workspace's batch neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    B9 = mk.batch("B-N", TD, w="W2")
    mk.pbl(B9, "input", workspace_id=st.W1.id)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.batch_line_count == 0
    # Then 2
    assert ud.batches == []


@xf("BUG-2520")
def test_ism_us_26__line_on_other_workspaces_component_hidden(db, st, mk):
    """ISM-US-26 — a line on another workspace's component neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    P0 = mk.proj("Zero Bridge", w="W0")
    C0 = mk.comp(P0, "Zero Deck")
    mk.pcl(C0, workspace_id=st.W1.id)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.project_component_count == 0
    # Then 2
    assert ud.projects == []


@xf("BUG-2520")
def test_ism_us_27__component_under_other_workspaces_project_hidden(db, st, mk):
    """ISM-US-27 — a component of this workspace under another workspace's project neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    P9 = mk.proj("Far Bridge", w="W2")
    C = mk.comp(P9, "Stray", workspace_id=st.W1.id)
    mk.pcl(C)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.project_component_count == 0
    # Then 2
    assert ud.projects == []


@xf("BUG-2520")
def test_ism_us_28__line_on_later_workspaces_work_order_hidden(db, st, mk):
    """ISM-US-28 — a line on a later workspace's work order neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    O9 = mk.wo("WO-N", w="W2")
    mk.wol(O9, workspace_id=st.W1.id)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.work_order_line_count == 0
    # Then 2
    assert ud.work_orders == []


@xf("BUG-2520")
def test_ism_us_29__line_on_earlier_workspaces_work_order_hidden(db, st, mk):
    """ISM-US-29 — a line on an earlier workspace's work order neither counts nor shows.
    Rules: _usage R6 [BUG-2520]."""
    O0 = mk.wo("WO-Z", w="W0")
    mk.wol(O0, workspace_id=st.W1.id)
    O1 = mk.wo("WO-1")
    mk.wol(O1)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.work_order_line_count == 1
    # Then 2
    assert [w.work_order_id for w in ud.work_orders] == [O1.id]


def test_ism_us_30__nothing_used_zero_counts_empty_previews(db, st):
    """ISM-US-30 — nothing used: zero counts, empty previews.
    Rules: _usage R7."""
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    uc, ud = result.usage_counts, result.usage_details
    # Then 1
    assert uc.formula_count == 0
    assert uc.batch_line_count == 0
    assert uc.project_component_count == 0
    assert uc.work_order_line_count == 0
    # Then 2
    assert ud.formulas == []
    assert ud.batches == []
    assert ud.projects == []
    assert ud.work_orders == []


# =========================================================================== #
# _resolve_order_link
# =========================================================================== #

def test_ism_ol_01__given_type_and_id_returned(db, st, mk):
    """ISM-OL-01 — a given type and id are returned as they are.
    Rules: _resolve_order_link R1."""
    S = mk.so("SO-1", TD)
    result = svc._resolve_order_link(db, order_type="sales_order", order_id=S.id, source_type="purchase_order", source_id=5)
    # Then 1
    assert result == ("sales_order", S.id)


def test_ism_ol_02__type_with_order_id_zero_falls_through(db, st, mk):
    """ISM-OL-02 — a type with order id 0 falls through to the source.
    Rules: _resolve_order_link R1, R3."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"), id=XID(2))
    result = svc._resolve_order_link(db, order_type="work_order", order_id=0, source_type="purchase_order", source_id=L.id)
    # Then 1
    assert result == ("purchase_order", P.id)


def test_ism_ol_03__order_id_with_no_type_falls_through(db, st, mk):
    """ISM-OL-03 — an order id with no type falls through to the source.
    Rules: _resolve_order_link R1, R3."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"), id=XID(2))
    result = svc._resolve_order_link(db, order_type=None, order_id=77, source_type="purchase_order", source_id=L.id)
    # Then 1
    assert result == ("purchase_order", P.id)


def test_ism_ol_04__no_source_type_no_link(db):
    """ISM-OL-04 — no source type gives no link.
    Rules: _resolve_order_link R2."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type=None, source_id=5)
    # Then 1
    assert result == (None, None)


def test_ism_ol_05__empty_source_type_no_link(db):
    """ISM-OL-05 — an empty source type gives no link.
    Rules: _resolve_order_link R2."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="", source_id=5)
    # Then 1
    assert result == (None, None)


def test_ism_ol_06__source_id_zero_no_link_nothing_read(db):
    """ISM-OL-06 — source id 0 gives no link, nothing read.
    Rules: _resolve_order_link R2."""
    rec = Recorder(db).start()
    try:
        result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=0)
    finally:
        rec.stop()
    # Then 1
    assert result == (None, None)
    # Then 2
    assert len(rec.stmts) == 0


def test_ism_ol_07__no_source_id_no_link(db):
    """ISM-OL-07 — no source id gives no link.
    Rules: _resolve_order_link R2."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=None)
    # Then 1
    assert result == (None, None)


def test_ism_ol_08__purchase_line_links_to_order(db, st, mk):
    """ISM-OL-08 — a purchase line source links to its order, not the line.
    Rules: _resolve_order_link R3."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"), id=XID(2))
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)
    # Then 1
    assert result == ("purchase_order", XID(1))


def test_ism_ol_09__transfer_line_links_to_order(db, st, mk):
    """ISM-OL-09 — a transfer line source links to its order, not the line.
    Rules: _resolve_order_link R3."""
    T = mk.to("TO-1", NOON(TD), id=XID(1))
    TL = mk.tol(T, Decimal("1.00"), id=XID(2))
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="transfer_order", source_id=TL.id)
    # Then 1
    assert result == ("transfer_order", XID(1))


def test_ism_ol_10__missing_purchase_line_no_link(db):
    """ISM-OL-10 — a missing purchase line gives no link.
    Rules: _resolve_order_link R3."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=MISSING)
    # Then 1
    assert result == (None, None)


def test_ism_ol_11__missing_transfer_line_no_link(db):
    """ISM-OL-11 — a missing transfer line gives no link.
    Rules: _resolve_order_link R3."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="transfer_order", source_id=MISSING)
    # Then 1
    assert result == (None, None)


def test_ism_ol_12__manual_source_no_link(db):
    """ISM-OL-12 — a manual source gives no link.
    Rules: _resolve_order_link R4, R4a."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="manual", source_id=5)
    # Then 1
    assert result == (None, None)


def test_ism_ol_13__production_batch_source_no_link(db, st, mk):
    """ISM-OL-13 — a production batch source gives no link.
    Rules: _resolve_order_link R4, R4a."""
    B = mk.batch("B-1", TD)
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="production_batch", source_id=B.id)
    # Then 1
    assert result == (None, None)


def test_ism_ol_14__adjustment_source_no_link(db):
    """ISM-OL-14 — adjustment and reconciliation sources give no link.
    Rules: _resolve_order_link R4, R4a."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="adjustment", source_id=5)
    # Then 1
    assert result == (None, None)


def test_ism_ol_15__missing_receive_event_item_no_link(db):
    """ISM-OL-15 — a missing receive-event item gives no link.
    Rules: _resolve_order_link R4, R4a."""
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item", source_id=MISSING)
    # Then 1
    assert result == (None, None)


@xf("BUG-2527")
def test_ism_ol_16__receive_event_item_links_purchase_order(db, st, mk):
    """ISM-OL-16 — a receive-event item links to the purchase order.
    Rules: _resolve_order_link R4a [BUG-2527]."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"))
    E = mk.rev(P)
    EI = mk.revi(E, L)
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item", source_id=EI.id)
    # Then 1
    assert result == ("purchase_order", XID(1))


@xf("BUG-2527")
def test_ism_ol_17__receive_event_item_reversal_links_purchase_order(db, st, mk):
    """ISM-OL-17 — a receive-event item reversal links to the purchase order.
    Rules: _resolve_order_link R4a [BUG-2527]."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"))
    E = mk.rev(P)
    EI = mk.revi(E, L)
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item_reversal", source_id=EI.id)
    # Then 1
    assert result == ("purchase_order", XID(1))


@xf("BUG-2527")
def test_ism_ol_18__legacy_purchase_reversal_links_line_order(db, st, mk):
    """ISM-OL-18 — a legacy purchase reversal links to the line's order.
    Rules: _resolve_order_link R4a [BUG-2527]."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), id=XID(2))
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order_reversal", source_id=L.id)
    # Then 1
    assert result == ("purchase_order", XID(1))


@xf("BUG-2527")
def test_ism_ol_19__purchase_return_item_links_returns_order(db, st, mk):
    """ISM-OL-19 — a purchase return item links to the return's purchase order.
    Rules: _resolve_order_link R4a [BUG-2527]."""
    P = mk.po("PO-1", TD, id=XID(1))
    L = mk.pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"))
    R = mk.ret(P, "RET-1")
    RI = mk.reti(R, L)
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_return_item", source_id=RI.id)
    # Then 1
    assert result == ("purchase_order", XID(1))


@xf("BUG-2527")
def test_ism_ol_20__work_order_source_links_work_order(db, st, mk):
    """ISM-OL-20 — a work order source links to that work order.
    Rules: _resolve_order_link R4a [BUG-2527]."""
    O = mk.wo("WO-1")
    result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="work_order", source_id=O.id)
    # Then 1
    assert result == ("work_order", O.id)


# OL-21 ... OL-30, ON-10 ... ON-14, AL-04, AL-05: the fix's new required
# `workspace_id`; today the call itself raises TypeError (Conventions).
BUG_2520_WS = xf("BUG-2520", raises=TypeError)


@BUG_2520_WS
def test_ism_ol_21__with_workspace_w1_purchase_line_resolves(db, st, mk):
    """ISM-OL-21 — with the workspace given, a W1 purchase line resolves.
    Rules: _resolve_order_link R3, R5 [BUG-2520]."""
    P = mk.po("PO-1", TD)
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)
    assert result == ("purchase_order", P.id)


@BUG_2520_WS
def test_ism_ol_22__purchase_line_of_w2_no_link(db, st, mk):
    """ISM-OL-22 — a purchase line of W2 gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    P9 = mk.po("PO-N", TD, w="W2")
    L9 = mk.pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L9.id)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_23__purchase_line_of_w0_no_link(db, st, mk):
    """ISM-OL-23 — a purchase line of W0 gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    P0 = mk.po("PO-Z", TD, w="W0")
    L0 = mk.pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L0.id)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_24__transfer_line_of_w2_no_link(db, st, mk):
    """ISM-OL-24 — a transfer line of W2 gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    T9 = mk.to("TO-N", NOON(TD), w="W2", source_location_id=st.F9.id, destination_location_id=st.F9.id)
    TL9 = mk.tol(T9, Decimal("1.00"))
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="transfer_order", source_id=TL9.id)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_25__transfer_line_of_w0_no_link(db, st, mk):
    """ISM-OL-25 — a transfer line of W0 gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    T0X = mk.to("TO-Z", NOON(TD), w="W0", source_location_id=st.F0.id, destination_location_id=st.F0.id)
    TL0 = mk.tol(T0X, Decimal("1.00"))
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="transfer_order", source_id=TL0.id)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_26__w1_line_on_w2_purchase_order_no_link(db, st, mk):
    """ISM-OL-26 — a W1 line on a W2 purchase order gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    P9 = mk.po("PO-N", TD, w="W2")
    L = mk.pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"), workspace_id=st.W1.id)
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_27__given_w1_order_passes_through(db, st, mk):
    """ISM-OL-27 — a given W1 order passes through with the workspace given.
    Rules: _resolve_order_link R1, R5 [BUG-2520]."""
    S = mk.so("SO-1", TD)
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type="sales_order", order_id=S.id, source_type=None, source_id=None)
    assert result == ("sales_order", S.id)


@BUG_2520_WS
def test_ism_ol_28__given_w2_order_does_not_pass_through(db, st, mk):
    """ISM-OL-28 — a given W2 order does not pass through.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    S9 = mk.so("SO-N", TD, w="W2")
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type="sales_order", order_id=S9.id, source_type=None, source_id=None)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_29__given_w0_order_does_not_pass_through(db, st, mk):
    """ISM-OL-29 — a given W0 order does not pass through.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    S0 = mk.so("SO-Z", TD, w="W0")
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type="sales_order", order_id=S0.id, source_type=None, source_id=None)
    assert result == (None, None)


@BUG_2520_WS
def test_ism_ol_30__given_missing_order_id_does_not_pass_through(db, st):
    """ISM-OL-30 — a given order id that does not exist does not pass through.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    # Then 1
    result = svc._resolve_order_link(db, workspace_id=st.W1.id, order_type="sales_order", order_id=MISSING, source_type=None, source_id=None)
    assert result == (None, None)


# =========================================================================== #
# _resolve_order_number
# =========================================================================== #

def test_ism_on_01__no_type_no_number(db, st, mk):
    """ISM-ON-01 — no type gives no number.
    Rules: _resolve_order_number R1."""
    P = mk.po("PO-1", TD)
    result = svc._resolve_order_number(db, order_type=None, order_id=P.id)
    # Then 1
    assert result is None


def test_ism_on_02__no_id_no_number(db):
    """ISM-ON-02 — no id gives no number.
    Rules: _resolve_order_number R1."""
    result = svc._resolve_order_number(db, order_type="purchase_order", order_id=None)
    # Then 1
    assert result is None


def test_ism_on_03__purchase_order_gives_po_number(db, st, mk):
    """ISM-ON-03 — a purchase order gives its PO number.
    Rules: _resolve_order_number R2."""
    P = mk.po("PO-1", TD)
    result = svc._resolve_order_number(db, order_type="purchase_order", order_id=P.id)
    # Then 1
    assert result == "PO-1"


def test_ism_on_04__transfer_order_gives_transfer_number(db, st, mk):
    """ISM-ON-04 — a transfer order gives its transfer number.
    Rules: _resolve_order_number R2."""
    T = mk.to("TO-1", NOON(TD))
    result = svc._resolve_order_number(db, order_type="transfer_order", order_id=T.id)
    # Then 1
    assert result == GN("TO-1")


def test_ism_on_05__sales_order_gives_number(db, st, mk):
    """ISM-ON-05 — a sales order gives its sales order number.
    Rules: _resolve_order_number R2."""
    S = mk.so("SO-1", TD)
    result = svc._resolve_order_number(db, order_type="sales_order", order_id=S.id)
    # Then 1
    assert result == GN("SO-1")


def test_ism_on_06__expense_order_gives_number(db, st, mk):
    """ISM-ON-06 — an expense order gives its expense number.
    Rules: _resolve_order_number R2."""
    X = mk.eo("EX-1")
    result = svc._resolve_order_number(db, order_type="expense_order", order_id=X.id)
    # Then 1
    assert result == "EX-1"


def test_ism_on_07__work_order_gives_number(db, st, mk):
    """ISM-ON-07 — a work order gives its work order number.
    Rules: _resolve_order_number R2."""
    O = mk.wo("WO-1")
    result = svc._resolve_order_number(db, order_type="work_order", order_id=O.id)
    # Then 1
    assert result == "WO-1"


def test_ism_on_08__missing_order_no_number(db):
    """ISM-ON-08 — a missing order gives no number.
    Rules: _resolve_order_number R2."""
    result = svc._resolve_order_number(db, order_type="purchase_order", order_id=MISSING)
    # Then 1
    assert result is None


def test_ism_on_09__unknown_type_no_number(db, st, mk):
    """ISM-ON-09 — an unknown type gives no number.
    Rules: _resolve_order_number R2."""
    P = mk.po("PO-1", TD)
    result = svc._resolve_order_number(db, order_type="invoice", order_id=P.id)
    # Then 1
    assert result is None


@BUG_2520_WS
def test_ism_on_10__with_workspace_w1_po_gives_number(db, st, mk):
    """ISM-ON-10 — with the workspace given, a W1 purchase order gives its number.
    Rules: _resolve_order_number R2, R3 [BUG-2520]."""
    P = mk.po("PO-1", TD)
    # Then 1
    result = svc._resolve_order_number(db, workspace_id=st.W1.id, order_type="purchase_order", order_id=P.id)
    assert result == "PO-1"


@BUG_2520_WS
def test_ism_on_11__w2_po_no_number(db, st, mk):
    """ISM-ON-11 — a W2 purchase order gives no number.
    Rules: _resolve_order_number R3 [BUG-2520]."""
    P9 = mk.po("PO-N", TD, w="W2")
    # Then 1
    result = svc._resolve_order_number(db, workspace_id=st.W1.id, order_type="purchase_order", order_id=P9.id)
    assert result is None


@BUG_2520_WS
def test_ism_on_12__w0_po_no_number(db, st, mk):
    """ISM-ON-12 — a W0 purchase order gives no number.
    Rules: _resolve_order_number R3 [BUG-2520]."""
    P0 = mk.po("PO-Z", TD, w="W0")
    # Then 1
    result = svc._resolve_order_number(db, workspace_id=st.W1.id, order_type="purchase_order", order_id=P0.id)
    assert result is None


@BUG_2520_WS
def test_ism_on_13__w2_work_order_no_number(db, st, mk):
    """ISM-ON-13 — a W2 work order gives no number.
    Rules: _resolve_order_number R3 [BUG-2520]."""
    O9 = mk.wo("WO-N", w="W2")
    # Then 1
    result = svc._resolve_order_number(db, workspace_id=st.W1.id, order_type="work_order", order_id=O9.id)
    assert result is None


@BUG_2520_WS
def test_ism_on_14__w0_sales_order_no_number(db, st, mk):
    """ISM-ON-14 — a W0 sales order gives no number.
    Rules: _resolve_order_number R3 [BUG-2520]."""
    S0 = mk.so("SO-Z", TD, w="W0")
    # Then 1
    result = svc._resolve_order_number(db, workspace_id=st.W1.id, order_type="sales_order", order_id=S0.id)
    assert result is None


# =========================================================================== #
# _activity_from_ledger
# =========================================================================== #

def test_ism_al_01__entry_carries_given_fields_with_link(db, st, mk):
    """ISM-AL-01 — the entry carries what it is given, with the resolved link and number.
    Rules: _activity_from_ledger R1."""
    P = mk.po("PO-1", TD)
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    result = svc._activity_from_ledger(db, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=3, factory_id=st.F1.id, factory_name="Factory One", machine_id=None, machine_name=None, inventory_type="STORAGE", order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)
    # Then 1
    assert result.source == "inventory"
    assert result.performed_at == TS(1)
    assert result.transaction_type == "manual_add"
    assert result.quantity == 3
    # Then 2
    assert result.factory_id == st.F1.id
    assert result.factory_name == "Factory One"
    assert result.machine_id is None
    assert result.machine_name is None
    assert result.inventory_type == "STORAGE"
    # Then 3
    assert result.order_type == "purchase_order"
    assert result.order_id == P.id
    # Then 4
    assert result.order_number == "PO-1"


def test_ism_al_02__no_link_no_order_fields(db, st):
    """ISM-AL-02 — no link gives no order fields.
    Rules: _activity_from_ledger R1."""
    result = svc._activity_from_ledger(db, source="machine", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=None, factory_name=None, machine_id=st.M1.id, machine_name="Press 1", inventory_type=None, order_type=None, order_id=None, source_type="manual", source_id=None)
    # Then 1
    assert result.source == "machine"
    assert result.machine_id == st.M1.id
    assert result.machine_name == "Press 1"
    # Then 2
    assert result.order_type is None
    assert result.order_id is None
    assert result.order_number is None


def test_ism_al_03__unknown_source_raises_validation_error(db, st):
    """ISM-AL-03 — an unknown source raises a validation error.
    Rules: _activity_from_ledger R2."""
    # Then 1
    with pytest.raises(ValidationError):
        svc._activity_from_ledger(db, source="storage", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=st.F1.id, factory_name="Factory One", machine_id=None, machine_name=None, inventory_type="STORAGE", order_type=None, order_id=None, source_type=None, source_id=None)


@BUG_2520_WS
def test_ism_al_04__workspace_passed_on_w2_line_no_order(db, st, mk):
    """ISM-AL-04 — the workspace is passed on: a W2 source line gives no order fields.
    Rules: _activity_from_ledger R1, R3 [BUG-2520]."""
    P9 = mk.po("PO-N", TD, w="W2")
    L9 = mk.pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    # Then 1
    result = svc._activity_from_ledger(db, workspace_id=st.W1.id, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=st.F1.id, factory_name="Factory One", source_type="purchase_order", source_id=L9.id)
    assert result.source == "inventory"
    # Then 2
    assert result.order_type is None
    assert result.order_id is None
    # Then 3
    assert result.order_number is None


@BUG_2520_WS
def test_ism_al_05__workspace_passed_on_w1_line_link_and_number(db, st, mk):
    """ISM-AL-05 — the workspace is passed on: a W1 source line gives the link and number.
    Rules: _activity_from_ledger R1, R3 [BUG-2520]."""
    P = mk.po("PO-1", TD)
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    # Then 1
    result = svc._activity_from_ledger(db, workspace_id=st.W1.id, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=st.F1.id, factory_name="Factory One", source_type="purchase_order", source_id=L.id)
    assert result.order_type == "purchase_order"
    assert result.order_id == P.id
    # Then 2
    assert result.order_number == "PO-1"


def test_ism_al_06__nine_optional_keywords_default_none(db):
    """ISM-AL-06 — the nine optional keywords default to None.
    Rules: _activity_from_ledger R3."""
    result = svc._activity_from_ledger(db, source="product", performed_at=TS(1), transaction_type="sale", quantity=1)
    # Then 1
    assert result.source == "product"
    assert result.quantity == 1
    # Then 2
    assert result.factory_id is None
    assert result.factory_name is None
    assert result.machine_id is None
    assert result.machine_name is None
    assert result.inventory_type is None
    # Then 3
    assert result.order_type is None
    assert result.order_id is None
    assert result.order_number is None


def test_ism_al_07__arguments_after_db_not_positional(db):
    """ISM-AL-07 — arguments after db cannot be passed by position.
    Rules: _activity_from_ledger R3."""
    # Then 1
    with pytest.raises(TypeError):
        svc._activity_from_ledger(db, "product", TS(1), "sale", 1)


# =========================================================================== #
# _recent_activity
# =========================================================================== #

@pytest.fixture
def FMAP(st):
    """Convention FMAP."""
    return {st.F1.id: "Factory One", st.F2.id: "Second Plant", st.FD.id: "Old Plant"}


@pytest.fixture
def MMAP(st):
    """Convention MMAP."""
    return {st.M1.id: "Press 1"}


AWARE = datetime(2026, 1, 2, 15, 0, tzinfo=timezone(timedelta(hours=6)))


def limit_of(stmt, params):
    """The LIMIT value of a recorded statement, from its text or its parameters."""
    m = re.search(r"LIMIT\s+(%\((\w+)\)s|\d+)", stmt)
    if not m:
        return None
    if m.group(2):
        return params[m.group(2)]
    return int(m.group(1))


def test_ism_ra_01__inventory_entry_fields(db, st, mk, FMAP, MMAP):
    """ISM-RA-01 — an inventory entry: source, time, factory, type text, int quantity.
    Rules: _recent_activity R2."""
    mk.ient(st.F1, TS(1), inventory_type=DAMAGED, quantity=3, qty_after=3)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].source == "inventory"
    assert result[0].performed_at == TS(1)
    assert result[0].transaction_type == "manual_add"
    # Then 3
    assert result[0].factory_id == st.F1.id
    assert result[0].factory_name == "Factory One"
    assert result[0].inventory_type == "DAMAGED"
    # Then 4
    assert result[0].quantity == 3
    assert isinstance(result[0].quantity, int)
    # Then 5
    assert result[0].machine_id is None
    assert result[0].order_type is None


def test_ism_ra_02__purchase_line_source_gives_link_and_number(db, st, mk, FMAP, MMAP):
    """ISM-RA-02 — an inventory entry's purchase-line source gives the order link and number.
    Rules: _recent_activity R2; _activity_from_ledger R1."""
    P = mk.po("PO-1", TD)
    L = mk.pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    mk.ient(st.F1, TS(1), source_type="purchase_order", source_id=L.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert result[0].order_type == "purchase_order"
    assert result[0].order_id == P.id
    # Then 2
    assert result[0].order_number == "PO-1"


def test_ism_ra_03__factory_missing_from_map_no_name(db, st, mk, MMAP):
    """ISM-RA-03 — a factory missing from the map gives no factory name.
    Rules: _recent_activity R2."""
    mk.ient(st.F2, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names={st.F1.id: "Factory One"}, machine_names=MMAP)
    # Then 1
    assert result[0].factory_id == st.F2.id
    # Then 2
    assert result[0].factory_name is None


def test_ism_ra_04__product_entry_fields(db, st, mk, FMAP, MMAP):
    """ISM-RA-04 — a product entry: source product, factory, no inventory type.
    Rules: _recent_activity R2."""
    mk.pent(st.F1, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].source == "product"
    assert result[0].factory_id == st.F1.id
    assert result[0].factory_name == "Factory One"
    # Then 3
    assert result[0].inventory_type is None
    assert result[0].quantity == 1


def test_ism_ra_05__machine_entry_own_order_type_and_id(db, st, mk, FMAP, MMAP):
    """ISM-RA-05 — a machine entry: machine name, and its own order type and id.
    Rules: _recent_activity R2."""
    O = mk.wo("WO-1")
    mk.ment(st.M1, TS(1), order_type="work_order", order_id=O.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert result[0].source == "machine"
    assert result[0].machine_id == st.M1.id
    assert result[0].machine_name == "Press 1"
    # Then 2
    assert result[0].order_type == "work_order"
    assert result[0].order_id == O.id
    # Then 3
    assert result[0].order_number == "WO-1"


def test_ism_ra_06__machine_entry_no_order_falls_back_to_source(db, st, mk, FMAP, MMAP):
    """ISM-RA-06 — a machine entry with no order falls back to its source.
    Rules: _recent_activity R2."""
    T = mk.to("TO-1", NOON(TD))
    TL = mk.tol(T, Decimal("1.00"))
    mk.ment(st.M1, TS(1), source_type="transfer_order", source_id=TL.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert result[0].order_type == "transfer_order"
    assert result[0].order_id == T.id
    # Then 2
    assert result[0].order_number == GN("TO-1")


def test_ism_ra_07__machine_missing_from_map_no_name(db, st, mk, FMAP, MMAP):
    """ISM-RA-07 — a machine missing from the map gives no machine name.
    Rules: _recent_activity R2."""
    M2 = mk.mach("Press 2")
    mk.ment(M2, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert result[0].machine_id == M2.id
    # Then 2
    assert result[0].machine_name is None


def test_ism_ra_08__three_ledgers_merge_newest_first(db, st, mk, FMAP, MMAP):
    """ISM-RA-08 — the three ledgers merge newest first.
    Rules: _recent_activity R3."""
    mk.ment(st.M1, TS(2))
    mk.ient(st.F1, TS(4))
    mk.pent(st.F1, TS(3))
    mk.ient(st.F1, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert [(a.source, a.performed_at) for a in result] == [("inventory", TS(4)), ("product", TS(3)), ("machine", TS(2)), ("inventory", TS(1))]


def test_ism_ra_09__default_limit_ten_across_ledgers(db, st, mk, FMAP, MMAP):
    """ISM-RA-09 — the default limit is 10 across the three ledgers.
    Rules: _recent_activity R1, R3."""
    for k in (1, 3, 5, 7):
        mk.ient(st.F1, TS(k))
    for k in (2, 4, 6, 8):
        mk.pent(st.F1, TS(k))
    for k in (9, 10, 11, 12):
        mk.ment(st.M1, TS(k))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert [a.performed_at for a in result] == [TS(k) for k in range(12, 2, -1)]


def test_ism_ra_10__limit_above_five_returns_that_many(db, st, mk, FMAP, MMAP):
    """ISM-RA-10 — a limit above 5 returns that many newest entries.
    Rules: _recent_activity R1, R3."""
    for k in (4, 1, 7, 2, 6, 3, 5):
        mk.ient(st.F1, TS(k))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP, limit=6)
    # Then 1
    assert [a.performed_at for a in result] == [TS(7), TS(6), TS(5), TS(4), TS(3), TS(2)]


def test_ism_ra_11__limit_below_five_still_reads_five(db, st, mk, FMAP, MMAP):
    """ISM-RA-11 — a limit below 5 still reads 5 entries per ledger.
    Rules: _recent_activity R1."""
    for k in range(1, 7):
        mk.ient(st.F1, TS(k))
    ws_id, item_id = st.W1.id, st.I1.id
    rec = Recorder(db).start()
    try:
        result = svc._recent_activity(db, workspace_id=ws_id, item_id=item_id, factory_names=FMAP, machine_names=MMAP, limit=1)
    finally:
        rec.stop()
    # Then 1
    assert [a.performed_at for a in result] == [TS(6)]
    # Then 2
    limits = [limit_of(s, p) for s, p in rec.stmts if s.lstrip().upper().startswith("SELECT") and "inventory_ledger" in s]
    assert limits == [5]


def test_ism_ra_12__equal_times_inventory_product_machine(db, st, mk, FMAP, MMAP):
    """ISM-RA-12 — equal times keep the order inventory, product, machine.
    Rules: _recent_activity R3."""
    mk.ment(st.M1, TS(5))
    mk.pent(st.F1, TS(5))
    mk.ient(st.F1, TS(5))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert [a.source for a in result] == ["inventory", "product", "machine"]


def test_ism_ra_13__deleted_factory_and_machine_entries_stay(db, st, mk, FMAP):
    """ISM-RA-13 — entries of a deleted factory and a deleted machine are history and stay.
    Rules: _recent_activity R4."""
    MD = mk.mach("Press 4", **mk.deleted_machine)
    mk.ient(st.FD, TS(1))
    mk.ment(MD, TS(2))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names={st.M1.id: "Press 1", MD.id: "Press 4"})
    # Then 1
    assert [(a.source, a.factory_name, a.machine_name) for a in result] == [("machine", None, "Press 4"), ("inventory", "Old Plant", None)]


def test_ism_ra_14__removed_items_entries_stay(db, st, mk, FMAP, MMAP):
    """ISM-RA-14 — a removed item's entries stay.
    Rules: _recent_activity R4."""
    mk.ient(st.F1, TS(1), item_id=st.IR.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.IR.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert [a.performed_at for a in result] == [TS(1)]


def test_ism_ra_15__no_entries_empty_list(db, st, FMAP, MMAP):
    """ISM-RA-15 — no entries gives an empty list.
    Rules: _recent_activity R5."""
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert result == []


def test_ism_ra_16__only_this_workspace_and_item(db, st, mk, FMAP, MMAP):
    """ISM-RA-16 — only this workspace's entries of this item.
    Rules: _recent_activity R1."""
    mk.ient(st.F0, TS(5), workspace_id=st.W0.id, item_id=st.I0.id)
    mk.pent(st.F0, TS(6), workspace_id=st.W0.id)
    mk.ient(st.F1, TS(1))
    mk.ient(st.F1, TS(7), item_id=st.I2.id)
    mk.ient(st.F9, TS(8), workspace_id=st.W2.id)
    mk.ment(st.M9, TS(9), workspace_id=st.W2.id, item_id=st.I9.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert [(a.source, a.performed_at) for a in result] == [("inventory", TS(1))]


@xf("BUG-2520")
def test_ism_ra_17__entry_in_other_workspaces_factory_no_factory(db, st, mk, FMAP, MMAP):
    """ISM-RA-17 — an entry in another workspace's factory shows no factory.
    Rules: _recent_activity R6 [BUG-2520]."""
    mk.ient(st.F9, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].factory_id is None
    # Then 3
    assert result[0].factory_name is None


@xf("BUG-2520")
def test_ism_ra_18__entry_on_other_workspaces_machine_no_machine(db, st, mk, FMAP, MMAP):
    """ISM-RA-18 — an entry on another workspace's machine shows no machine.
    Rules: _recent_activity R6 [BUG-2520]."""
    mk.ment(st.M0, TS(1))
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].machine_id is None
    # Then 3
    assert result[0].machine_name is None


@xf("BUG-2520")
def test_ism_ra_19__source_line_of_other_workspace_no_link(db, st, mk, FMAP, MMAP):
    """ISM-RA-19 — a source line of another workspace gives no link.
    Rules: _resolve_order_link R5 [BUG-2520]."""
    P9 = mk.po("PO-N", TD, w="W2")
    L9 = mk.pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    mk.ient(st.F1, TS(1), source_type="purchase_order", source_id=L9.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].order_type is None
    assert result[0].order_id is None
    # Then 3
    assert result[0].order_number is None


@xf("BUG-2520")
def test_ism_ra_20__other_workspaces_order_on_machine_entry_no_number(db, st, mk, FMAP, MMAP):
    """ISM-RA-20 — another workspace's order named on a machine entry gives no link or number.
    Rules: _resolve_order_number R3 [BUG-2520]."""
    P0 = mk.po("PO-Z", TD, w="W0")
    mk.ment(st.M1, TS(1), order_type="purchase_order", order_id=P0.id)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].order_number is None
    # Then 3
    assert result[0].order_type is None
    assert result[0].order_id is None


@xf("BUG-2528")
def test_ism_ra_21__links_read_together_only_for_returned(db, st, mk, FMAP, MMAP):
    """ISM-RA-21 — links are read together, only for the returned entries.
    Rules: _recent_activity R7 [BUG-2528]."""
    for k in range(1, 13):
        Pk = mk.po(f"PO-{k}", TD)
        Lk = mk.pol(Pk, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
        mk.ient(st.F1, TS(k), source_type="purchase_order", source_id=Lk.id)
    ws_id, item_id = st.W1.id, st.I1.id
    rec = Recorder(db).start()
    try:
        result = svc._recent_activity(db, workspace_id=ws_id, item_id=item_id, factory_names=FMAP, machine_names=MMAP)
    finally:
        rec.stop()
    # Then 1
    assert [a.order_number for a in result] == [f"PO-{k}" for k in range(12, 2, -1)]
    # Then 2
    assert len(result) == 10
    # Then 3
    assert len(rec.selects("purchase_order_items")) <= 1
    # Then 4
    assert len(rec.selects("FROM purchase_orders")) <= 1


@xf("BUG-2529")
def test_ism_ra_22__inventory_entry_no_time_gets_naive_utc(db, st, mk, FMAP, MMAP):
    """ISM-RA-22 — an inventory entry with no time gets naive UTC now, not the database's local time.
    Rules: _recent_activity R3 [BUG-2529]."""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    mk.ient(st.F1, OMIT)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert abs(datetime.now(timezone.utc).replace(tzinfo=None) - result[0].performed_at.replace(tzinfo=None)) < timedelta(minutes=5)


@xf("BUG-2487", raises=TypeError)
def test_ism_ra_23__aware_machine_time_merges_by_utc_instant(db, st, mk, FMAP, MMAP):
    """ISM-RA-23 — a zone-aware machine time merges with a naive one by its UTC instant.
    Rules: _recent_activity R3, R3a [BUG-2487]."""
    mk.ient(st.F1, TS(1))
    ME = mk.ment(st.M1, AWARE)
    assert ME.performed_at.tzinfo is not None  # setup: the session's object keeps the aware value
    # Then 1
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    assert [a.source for a in result] == ["inventory", "machine"]
    # Then 2
    assert result[0].performed_at == datetime(2026, 1, 2, 12, 0)  # noqa: DTZ001
    # Then 3
    assert result[1].performed_at == datetime(2026, 1, 2, 9, 0)  # noqa: DTZ001
    # Then 4
    assert result[1].performed_at.tzinfo is None


@xf("BUG-2487")
def test_ism_ra_24__lone_aware_time_comes_back_naive_utc(db, st, mk, FMAP, MMAP):
    """ISM-RA-24 — a lone zone-aware time comes back as naive UTC.
    Rules: _recent_activity R3a [BUG-2487]."""
    ME = mk.ment(st.M1, AWARE)
    assert ME.performed_at.tzinfo is not None  # setup: the session's object keeps the aware value
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].performed_at.tzinfo is None
    # Then 3
    assert result[0].performed_at == datetime(2026, 1, 2, 9, 0)  # noqa: DTZ001


# =========================================================================== #
# DAO bugs reached through the summary
# =========================================================================== #

@xf("BUG-884")
def test_ism_dp_01__stock_in_deleted_factory_not_listed(db, st, mk):
    """ISM-DP-01 — stock in a soft-deleted factory is not listed or totalled.
    Rules: _inventory_rows R1 [BUG-884]."""
    mk.stock(st.FD, STORAGE, 4, Decimal("1.00"))
    mk.stock(st.F1, STORAGE, 5, Decimal("1.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.inventory_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.storage_qty_total == 5


@xf("BUG-1328")
def test_ism_dp_02__finished_goods_of_deleted_factory_not_listed(db, st, mk):
    """ISM-DP-02 — finished goods of a deleted factory are not listed.
    Rules: _product_rows R1 [BUG-1328]."""
    mk.prod(st.FD, 4, Decimal("1.00"), Decimal("2.00"))
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [r.factory_id for r in result.product_rows] == [st.F1.id]
    # Then 2
    assert result.kpis.product_qty_total == 5


@xf("BUG-1338")
def test_ism_dp_03__removed_item_no_finished_goods(db, st, mk):
    """ISM-DP-03 — a removed item shows no finished goods.
    Rules: _product_rows R1 [BUG-1338]; get_summary R7."""
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"), item_id=st.IR.id)
    result = svc.get_summary(db, item_id=st.IR.id, workspace_id=st.W1.id)
    # Then 1
    assert result.item.id == st.IR.id
    # Then 2
    assert result.product_rows == []
    # Then 3
    assert result.kpis.product_qty_total == 0


def test_ism_dp_04__placement_on_deleted_machine_not_listed(db, st, mk):
    """ISM-DP-04 — a placement on a deleted machine is not listed.
    Rules: _machine_placements R1 [BUG-981]."""
    MD = mk.mach("Press 4", **mk.deleted_machine)
    mk.place(MD, 3, None)
    mk.place(st.M1, 2, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_id for p in result.machine_placements] == [st.M1.id]
    # Then 2
    assert result.kpis.machine_placement_count == 1


def test_ism_dp_05__placement_on_machine_of_deleted_factory_not_listed(db, st, mk):
    """ISM-DP-05 — a placement on a machine of a deleted factory is not listed.
    Rules: _machine_placements R1 [BUG-981]; _machine_location_map R5."""
    MF = mk.mach("Lost Press", factory_id=st.FD.id)
    mk.place(MF, 3, None)
    mk.place(st.M1, 2, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert [p.machine_id for p in result.machine_placements] == [st.M1.id]
    # Then 2
    assert result.kpis.machine_placement_count == 1


def test_ism_dp_06__placements_not_capped_at_500(db, st, mk):
    """ISM-DP-06 — placements are not capped at 500.
    Rules: _machine_placements R1 [BUG-982]."""
    for k in range(1, 502):
        Mk = mk.mach(f"M{k:03d}")
        mk.place(Mk, 1, None)
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert len(result.machine_placements) == 501
    # Then 2
    assert result.kpis.machine_placement_count == 501


def _summary_recorded(db, st):
    item_id, ws_id = st.I1.id, st.W1.id
    rec = Recorder(db).start()
    try:
        result = svc.get_summary(db, item_id=item_id, workspace_id=ws_id)
    finally:
        rec.stop()
    return result, rec


def test_ism_dp_07__placement_read_has_order_by(db, st, mk):
    """ISM-DP-07 — the placement read has an ORDER BY.
    Rules: _machine_placements R5 [BUG-977]."""
    mk.place(st.M1, 2, None)
    result, rec = _summary_recorded(db, st)
    # Then 1
    assert len(result.machine_placements) == 1
    # Then 2
    sel = rec.selects("machine_items")
    assert sel and all("ORDER BY" in s for s in sel)


@xf("BUG-1326")
def test_ism_dp_08__finished_goods_read_has_order_by(db, st, mk):
    """ISM-DP-08 — the finished-goods read has an ORDER BY.
    Rules: _product_rows R5 [BUG-1326]."""
    mk.prod(st.F1, 5, Decimal("1.00"), Decimal("2.00"))
    result, rec = _summary_recorded(db, st)
    # Then 1
    assert len(result.product_rows) == 1
    # Then 2
    sel = rec.selects("FROM products")
    assert sel and all("ORDER BY" in s for s in sel)


@xf("BUG-932")
def test_ism_dp_09__tag_read_has_order_by(db, st, mk):
    """ISM-DP-09 — the item's tag read has an ORDER BY.
    Rules: get_summary R3 [BUG-932]."""
    TR = mk.tag("Red", "red")
    mk.tagged(st.I1, TR)
    tr_id = TR.id
    result, rec = _summary_recorded(db, st)
    # Then 1
    assert [t.id for t in result.item.tags] == [tr_id]
    # Then 2
    sel = rec.selects("item_tag_assignments")
    assert sel and all("ORDER BY" in s for s in sel)


@xf("BUG-640")
def test_ism_dp_10__product_ledger_read_breaks_ties_by_id(db, st, mk, FMAP, MMAP):
    """ISM-DP-10 — the product ledger read breaks time ties by id.
    Rules: _recent_activity R1 [BUG-640]."""
    mk.pent(st.F1, TS(1))
    ws_id, item_id = st.W1.id, st.I1.id
    rec = Recorder(db).start()
    try:
        result = svc._recent_activity(db, workspace_id=ws_id, item_id=item_id, factory_names=FMAP, machine_names=MMAP)
    finally:
        rec.stop()
    # Then 1
    assert [a.source for a in result] == ["product"]
    # Then 2
    tails = [s.split("ORDER BY", 1)[1] if "ORDER BY" in s else "" for s in rec.selects("product_ledger")]
    assert tails and all("product_ledger.id" in t for t in tails)


@xf("BUG-1337")
def test_ism_dp_11__product_entry_no_time_gets_naive_utc(db, st, mk, FMAP, MMAP):
    """ISM-DP-11 — a product entry with no time gets naive UTC now.
    Rules: _recent_activity R3 [BUG-1337]."""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    mk.pent(st.F1, OMIT)
    result = svc._recent_activity(db, workspace_id=st.W1.id, item_id=st.I1.id, factory_names=FMAP, machine_names=MMAP)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert abs(datetime.now(timezone.utc).replace(tzinfo=None) - result[0].performed_at.replace(tzinfo=None)) < timedelta(minutes=5)


# =========================================================================== #
# Owner answer — OQ-31 (BUG-2485)
# =========================================================================== #

@xf("BUG-2485")
def test_ism_oq31_01__sales_total_to_revenue_not_spend(db, st, mk):
    """ISM-OQ31-01 — a sales line's total goes to sales revenue, not to spend.
    Rules: _order_stats_for_item R5, R5a [BUG-2485]."""
    S = mk.so("SO-1", D(5))
    mk.sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.sales_qty == Decimal("3.00")
    # Then 2
    assert result.total_quantity == Decimal("3.00")
    # Then 3
    assert result.line_count == 1
    # Then 4
    assert result.total_spend == Decimal(0)
    # Then 5
    assert result.sales_revenue == Decimal("300.00")
    # Then 6
    assert str(result.sales_revenue) == "300.00"


@xf("BUG-2485")
def test_ism_oq31_02__total_spend_purchases_only(db, st, mk):
    """ISM-OQ31-02 — total spend is purchase subtotals only, next to a sale and a transfer.
    Rules: _order_stats_for_item R2, R4, R5, R5a [BUG-2485]."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("20.00"), Decimal("2.50"), Decimal("50.00"))
    T = mk.to("TO-1", NOON(D(5)))
    mk.tol(T, Decimal("4.00"))
    S = mk.so("SO-1", D(5))
    mk.sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.total_quantity == Decimal("27.00")
    # Then 2
    assert result.line_count == 3
    # Then 3
    assert result.total_spend == Decimal("50.00")
    # Then 4
    assert str(result.total_spend) == "50.00"
    # Then 5
    assert result.sales_revenue == Decimal("300.00")


@xf("BUG-2485")
def test_ism_oq31_03__sales_revenue_follows_window(db, st, mk):
    """ISM-OQ31-03 — sales revenue follows the window by order date, both ends in.
    Rules: _order_stats_for_item R5, R5a [BUG-2485]."""
    for no, n, q in (("SO-A", 30, "1.00"), ("SO-B", 31, "2.00"), ("SO-C", 0, "4.00"), ("SO-E", -1, "8.00")):
        S = mk.so(no, D(n))
        mk.sol(S, Decimal(q), Decimal("1.00"), Decimal(q))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=TD)
    # Then 1
    assert result.sales_qty == Decimal("5.00")
    # Then 2
    assert result.total_spend == Decimal(0)
    # Then 3
    assert result.sales_revenue == Decimal("5.00")


@xf("BUG-2485")
def test_ism_oq31_04__other_workspaces_and_items_add_no_revenue(db, st, mk):
    """ISM-OQ31-04 — other workspaces' sales lines and other items add no revenue.
    Rules: _order_stats_for_item R1, R5a [BUG-2485]."""
    S0 = mk.so("SO-Z", D(5), w="W0")
    mk.sol(S0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00"))
    S1X = mk.so("SO-1", D(5))
    mk.sol(S1X, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    mk.sol(S1X, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), item_id=st.I2.id)
    S9 = mk.so("SO-N", D(5), w="W2")
    mk.sol(S9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.sales_qty == Decimal("1.00")
    # Then 2
    assert result.line_count == 1
    # Then 3
    assert result.total_spend == Decimal(0)
    # Then 4
    assert result.sales_revenue == Decimal("1.00")


@xf("BUG-2485")
def test_ism_oq31_05__summary_all_time_spend_leaves_sales_out(db, st, mk):
    """ISM-OQ31-05 — the summary's all-time total spend leaves sales out.
    Rules: _order_stats_for_item R5a [BUG-2485]; get_summary R6."""
    G = today_g()
    P = mk.po("PO-1", G(5))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    S = mk.so("SO-1", G(5))
    mk.sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.order_stats.all_time.sales_qty == Decimal("3.00")
    # Then 2
    assert result.order_stats.all_time.total_spend == Decimal("50.00")
    # Then 3
    assert result.order_stats.all_time.sales_revenue == Decimal("300.00")


def test_ism_oq31_06__quantities_add_up_one_line_each(db, st, mk):
    """ISM-OQ31-06 — purchase, transfer and sales quantities add up, one line each.
    Rules: _order_stats_for_item R2, R4, R5."""
    P = mk.po("PO-1", D(5))
    mk.pol(P, Decimal("20.00"), Decimal("2.50"), Decimal("50.00"))
    T = mk.to("TO-1", NOON(D(5)))
    mk.tol(T, Decimal("4.00"))
    S = mk.so("SO-1", D(5))
    mk.sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.purchase_qty == Decimal("20.00")
    # Then 2
    assert result.transfer_qty == Decimal("4.00")
    # Then 3
    assert result.sales_qty == Decimal("3.00")
    # Then 4
    assert result.total_quantity == Decimal("27.00")
    # Then 5
    assert result.line_count == 3


def test_ism_oq31_07__sales_quantities_dated_by_order_date(db, st, mk):
    """ISM-OQ31-07 — sales quantities are dated by order date, both window ends in.
    Rules: _order_stats_for_item R5."""
    for no, n, q in (("SO-A", 30, "1.00"), ("SO-B", 31, "2.00"), ("SO-C", 0, "4.00"), ("SO-E", -1, "8.00")):
        S = mk.so(no, D(n))
        mk.sol(S, Decimal(q), Decimal("1.00"), Decimal(q))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=D(30), to_date=TD)
    # Then 1
    assert result.sales_qty == Decimal("5.00")
    # Then 2
    assert result.line_count == 2


def test_ism_oq31_08__other_workspaces_and_items_add_no_quantity(db, st, mk):
    """ISM-OQ31-08 — other workspaces' sales lines and other items add no quantity.
    Rules: _order_stats_for_item R1, R5."""
    S0 = mk.so("SO-Z", D(5), w="W0")
    mk.sol(S0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00"))
    S1X = mk.so("SO-1", D(5))
    mk.sol(S1X, Decimal("1.00"), Decimal("1.00"), Decimal("1.00"))
    mk.sol(S1X, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), item_id=st.I2.id)
    S9 = mk.so("SO-N", D(5), w="W2")
    mk.sol(S9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00"))
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.sales_qty == Decimal("1.00")
    # Then 2
    assert result.total_quantity == Decimal("1.00")
    # Then 3
    assert result.line_count == 1


def test_ism_oq31_09__summary_all_time_counts_sold_quantity(db, st, mk):
    """ISM-OQ31-09 — the summary's all-time stats count the sold quantity.
    Rules: _order_stats_for_item R5; get_summary R6."""
    G = today_g()
    P = mk.po("PO-1", G(5))
    mk.pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00"))
    S = mk.so("SO-1", G(5))
    mk.sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.order_stats.all_time.sales_qty == Decimal("3.00")
    # Then 2
    assert result.order_stats.all_time.total_quantity == Decimal("13.00")
    # Then 3
    assert result.order_stats.all_time.line_count == 2


@xf("BUG-2485", raises=AttributeError)
def test_ism_oq31_10__nothing_matching_zero_revenue(db, st):
    """ISM-OQ31-10 — nothing matching gives zero sales revenue.
    Rules: _order_stats_for_item Returns, R5a [BUG-2485]."""
    result = svc._order_stats_for_item(db, workspace_id=st.W1.id, item_id=st.I1.id, from_date=None, to_date=None)
    # Then 1
    assert result.total_spend == 0
    # Then 2
    assert result.sales_revenue == Decimal(0)


# =========================================================================== #
# Owner answer — OQ-32 (BUG-2486)
# =========================================================================== #

def completed(db, st):
    """SC = Status(workspace_id=W1.id, name="Completed", comment="Final")."""
    return _add(db, Status(workspace_id=st.W1.id, name="Completed", comment="Final"))


def test_ism_oq32_01__partly_received_line_open_for_rest(db, st, mk):
    """ISM-OQ32-01 — a partly received line is open for the rest.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


def test_ism_oq32_02__fully_received_not_open(db, st, mk):
    """ISM-OQ32-02 — a fully received line is not open; none open gives 0.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("10.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0
    # Then 2
    assert result.open_qty_outstanding == 0


def test_ism_oq32_03__received_plus_refunded_equal_not_open(db, st, mk):
    """ISM-OQ32-03 — received plus refunded equal to ordered is not open.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("6.00"), quantity_refunded=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0
    # Then 2
    assert result.open_qty_outstanding == 0


def test_ism_oq32_04__one_hundredth_short_is_open(db, st, mk):
    """ISM-OQ32-04 — one hundredth short is open.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("6.00"), quantity_refunded=Decimal("3.99"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("0.01")


def test_ism_oq32_05__over_received_not_open(db, st, mk):
    """ISM-OQ32-05 — an over-received line is not open.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("12.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0
    # Then 2
    assert result.open_qty_outstanding == 0


def test_ism_oq32_06__fully_refunded_not_open(db, st, mk):
    """ISM-OQ32-06 — a fully refunded line is not open.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_refunded=Decimal("10.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0


def test_ism_oq32_07__outstanding_sums_every_open_line(db, st, mk):
    """ISM-OQ32-07 — the outstanding quantity sums every open line.
    Rules: _pricing R4."""
    P = mk.po("PO-1", D(3))
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    mk.pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), quantity_refunded=Decimal("1.00"))
    mk.pol(P, Decimal("3.00"), Decimal("1.00"), Decimal("3.00"), quantity_received=Decimal("3.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 2
    # Then 2
    assert result.open_qty_outstanding == Decimal("10.00")


def test_ism_oq32_08__no_workflow_stays_open(db, st, mk):
    """ISM-OQ32-08 — an order with no workflow stays open, whatever its status is called.
    Rules: _pricing R4, R4b."""
    SC = completed(db, st)
    P = mk.po("PO-1", D(3), current_status_id=SC.id)
    mk.pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"), quantity_received=Decimal("70.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("30.00")


def test_ism_oq32_09__other_workspaces_and_items_open_lines_do_not_count(db, st, mk):
    """ISM-OQ32-09 — open lines of other workspaces and other items do not count.
    Rules: _pricing R1, R4."""
    P0 = mk.po("PO-Z", D(3), w="W0")
    mk.pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00"))
    P1 = mk.po("PO-1", D(3))
    mk.pol(P1, Decimal("2.00"), Decimal("1.00"), Decimal("2.00"))
    mk.pol(P1, Decimal("5.00"), Decimal("1.00"), Decimal("5.00"), item_id=st.I2.id)
    P9 = mk.po("PO-N", D(3), w="W2")
    mk.pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("2.00")


@xf("BUG-2486")
def test_ism_oq32_10__order_in_last_status_not_open(db, st, mk):
    """ISM-OQ32-10 — an order in its workflow's last status is not open.
    Rules: _pricing R4b [BUG-2486]."""
    SC = completed(db, st)
    WF = mk.wf([st.S1.id, SC.id])
    P = mk.po("PO-1", D(3), current_status_id=SC.id, order_workflow_id=WF.id)
    mk.pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"), quantity_received=Decimal("70.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0
    # Then 2
    assert result.open_qty_outstanding == 0


def test_ism_oq32_11__earlier_status_stays_open(db, st, mk):
    """ISM-OQ32-11 — an order at an earlier status of its workflow stays open.
    Rules: _pricing R4, R4b."""
    SC = completed(db, st)
    WF = mk.wf([st.S1.id, SC.id])
    P = mk.po("PO-1", D(3), order_workflow_id=WF.id)
    mk.pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"), quantity_received=Decimal("70.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("30.00")


@xf("BUG-2486")
def test_ism_oq32_12__last_is_position_not_name(db, st, mk):
    """ISM-OQ32-12 — "last" is the position in the sequence, not the status's name.
    Rules: _pricing R4b [BUG-2486]."""
    SC = completed(db, st)
    WF = mk.wf([SC.id, st.S1.id])
    P = mk.po("PO-1", D(3), order_workflow_id=WF.id)
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 0
    # Then 2
    assert result.open_qty_outstanding == 0


def test_ism_oq32_13__empty_sequence_leaves_open(db, st, mk):
    """ISM-OQ32-13 — a workflow with an empty sequence leaves the order open.
    Rules: _pricing R4b."""
    SC = completed(db, st)
    WF = mk.wf([])
    P = mk.po("PO-1", D(3), current_status_id=SC.id, order_workflow_id=WF.id)
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


def test_ism_oq32_14__w2_workflow_does_not_close_w1_order(db, st, mk):
    """ISM-OQ32-14 — a W2 workflow does not close a W1 order.
    Rules: _pricing R4b."""
    SC = completed(db, st)
    WF9 = mk.wf([st.S1.id, SC.id], w="W2")
    P = mk.po("PO-1", D(3), current_status_id=SC.id, order_workflow_id=WF9.id)
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


def test_ism_oq32_15__w0_workflow_does_not_close_w1_order(db, st, mk):
    """ISM-OQ32-15 — a W0 workflow does not close a W1 order.
    Rules: _pricing R4b."""
    SC = completed(db, st)
    WF0 = mk.wf([st.S1.id, SC.id], w="W0")
    P = mk.po("PO-1", D(3), current_status_id=SC.id, order_workflow_id=WF0.id)
    mk.pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


@xf("BUG-2486")
def test_ism_oq32_16__only_open_orders_lines_summed(db, st, mk):
    """ISM-OQ32-16 — only the open order's lines are summed next to a closed one.
    Rules: _pricing R4, R4b [BUG-2486]."""
    SC = completed(db, st)
    WF = mk.wf([st.S1.id, SC.id])
    PC = mk.po("PO-C", D(3), current_status_id=SC.id, order_workflow_id=WF.id)
    mk.pol(PC, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"), quantity_received=Decimal("70.00"))
    PO = mk.po("PO-O", D(3), order_workflow_id=WF.id)
    mk.pol(PO, Decimal("10.00"), Decimal("1.00"), Decimal("10.00"), quantity_received=Decimal("4.00"))
    result = svc._pricing(db, workspace_id=st.W1.id, item_id=st.I1.id, today=TD)
    # Then 1
    assert result.open_po_line_count == 1
    # Then 2
    assert result.open_qty_outstanding == Decimal("6.00")


@xf("BUG-2486")
def test_ism_oq32_17__summary_no_open_line_for_closed_order(db, st, mk):
    """ISM-OQ32-17 — the summary shows no open line for a closed order.
    Rules: _pricing R4b [BUG-2486]; get_summary R6."""
    G = today_g()
    SC = completed(db, st)
    WF = mk.wf([st.S1.id, SC.id])
    P = mk.po("PO-1", G(3), current_status_id=SC.id, order_workflow_id=WF.id)
    mk.pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00"), quantity_received=Decimal("70.00"))
    result = svc.get_summary(db, item_id=st.I1.id, workspace_id=st.W1.id)
    # Then 1
    assert result.pricing.open_po_line_count == 0
    # Then 2
    assert result.pricing.open_qty_outstanding == 0
