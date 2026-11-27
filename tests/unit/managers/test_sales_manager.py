# ruff: noqa: SIM117, DTZ001, DTZ003, DTZ005, DTZ011, FURB157, RUF059
# (nested savepoint + pytest.raises, naive datetimes, utcnow T0/T1 ranges,
# Y = datetime.now().year, date.today(), 2-decimal Decimal("…") literals are all
# prescribed by the Conventions; setup helpers return every row of a Given,
# and not every test reads each one.)
"""Unit tests for app/managers/sales_manager.py.

Implements tests/unit/managers/sales_manager.cases.md (revision 10), one test
per case. Real Postgres session (`db` fixture). No externals are mocked (spec
Overview: none); time is read directly in the test and checked with
before/after ranges, or via Y = datetime.now().year for numbering.
"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.sales_manager import (
    SalesManager,
    all_deliverable_items_delivered,
    all_fulfilment_items_fulfilled,
)
from app.managers.sales_order_return_manager import SalesOrderReturnManager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.delivery_method import DeliveryMethod
from app.models.factory import Factory
from app.models.item import Item
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.sales_delivery import SalesDelivery
from app.models.sales_delivery_item import SalesDeliveryItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_approver import SalesOrderApprover
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_return import SalesOrderReturn
from app.models.workspace_member import WorkspaceMember
from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryEditRequest
from app.schemas.sales_delivery_item import SalesDeliveryItemInput
from app.schemas.sales_order import SalesOrderUpdate
from app.schemas.sales_order_item import SalesOrderItemInput
from app.utils.item_name_normalize import normalize_item_name
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> bug reason strings
# --------------------------------------------------------------------------- #

BUGS = {
    "BUG-009": "Approving twice (or withdrawing when not approved) re-stamps and logs again",
    "BUG-720": "Every state-checked-then-changed transition in this module reads its row(s) without a lock",
    "BUG-721": "A delivery that is already delivered or cancelled can be completed again",
    "BUG-722": "A delivery can be created directly in any status",
    "BUG-723": "A delivery can include lines from a different sales order",
    "BUG-724": "Listing the same order line twice in one delivery bypasses the capacity check",
    "BUG-725": "A fractional quantity can be planned for a stock item that can only ship whole units",
    "BUG-726": "Order and delivery numbers collide across workspaces",
    "BUG-728": "An order can reference another workspace's customer, factory or catalog items",
    "BUG-729": "The customer does not have to be tagged as a client",
    "BUG-730": "A delivery method from another workspace (or deleted) is accepted",
    "BUG-731": "Refunded quantity is ignored by the fully-delivered / re-fulfil checks",
    "BUG-732": "Editing a planned delivery cannot clear a field",
    "BUG-733": "Delivery changes never record who made them",
    "BUG-734": "A blank completion code is handled differently by deliveries and fulfilment",
    "BUG-735": "Stock ledger notes show the order number as 'SO-SO-2026-...'",
    "BUG-736": "An order with no approvers counts as approved",
    "BUG-737": "Approvers can be added or removed after the invoice is finalized or the order is complete",
    "BUG-2790": "Starting a sales return reopens a completed order",
    "BUG-362-order": "Order lines accept zero or negative quantities and negative prices",
    "BUG-362-delivery": "Delivery lines accept zero or negative quantities",
    "BUG-362-required": "A negative required-approvals number makes approval automatically satisfied",
    "BUG-021-order": "Order line quantities/prices with more than 2 decimals (or >=10^13) are silently rounded",
    "BUG-021-delivery": "Delivery line quantities with more than 2 decimals (or >=10^13) are silently rounded",
}


def xfail(*ids):
    """Build the xfail reason string, e.g. xfail('BUG-720') -> 'BUG-720: ...'."""
    return "; ".join(f"{bug_id.split('-order')[0].split('-delivery')[0].split('-required')[0]}: {BUGS[bug_id]}" for bug_id in ids)


# --------------------------------------------------------------------------- #
# Conventions -> base fixtures
# --------------------------------------------------------------------------- #

def _ensure_status10(db, ws):
    """ST: a `statuses` row with id 10 (SalesOrderCreate.current_status_id default)."""
    exists = db.execute(text("SELECT 1 FROM statuses WHERE id = 10")).first()
    if not exists:
        db.execute(
            text("INSERT INTO statuses (id, workspace_id, name, comment) VALUES (10, :ws, 'Confirmed', '')"),
            {"ws": ws.id},
        )
        db.flush()


@pytest.fixture
def w1(db):
    ws = make_workspace(db)
    _ensure_status10(db, ws)
    return ws


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def M():
    return SalesManager()


def mk_member(db, ws, user, *, status="active", position=None, role="member"):
    row = WorkspaceMember(
        workspace_id=ws.id, user_id=user.id, role=role, position=position, status=status,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def u1(db, w1):
    """Alice Rahman — active W1 member, position 'Sales Lead'."""
    p = make_profile(db, name="Alice Rahman")
    mk_member(db, w1, p, position="Sales Lead")
    return p


@pytest.fixture
def u2(db, w1):
    """Bob Karim — active W1 member, no position."""
    p = make_profile(db, name="Bob Karim")
    mk_member(db, w1, p, position=None)
    return p


@pytest.fixture
def u3(db, w1):
    """Chitra Das — suspended W1 member, position 'Clerk'."""
    p = make_profile(db, name="Chitra Das")
    mk_member(db, w1, p, status="suspended", position="Clerk")
    return p


@pytest.fixture
def u4(db, w1):
    """Dev Paul — invited W1 member."""
    p = make_profile(db, name="Dev Paul")
    mk_member(db, w1, p, status="invited")
    return p


@pytest.fixture
def u5(db, w2):
    """Esha Roy — active W2-only member, position 'Boss' in W2; not a W1 member."""
    p = make_profile(db, name="Esha Roy")
    mk_member(db, w2, p, position="Boss")
    return p


# --------------------------------------------------------------------------- #
# Conventions -> reference rows (accounts, factories, items, tags, products,
# delivery methods). `mk_*` are plain builders; the lettered fixtures are the
# cases file's named rows (A1, F1, I1, ...).
# --------------------------------------------------------------------------- #

def mk_tag(db, ws, tag_code, *, active=True, name=None):
    row = AccountTag(
        workspace_id=ws.id, name=name or tag_code.capitalize(), tag_code=tag_code, is_active=active,
    )
    db.add(row)
    db.flush()
    return row


def mk_tag_assignment(db, account, tag, *, ws=None):
    row = AccountTagAssignment(
        workspace_id=(ws or account).workspace_id if ws is None else ws.id,
        account_id=account.id, tag_id=tag.id,
    )
    db.add(row)
    db.flush()
    return row


def mk_account(db, ws, name, *, deleted=False):
    row = Account(workspace_id=ws.id, name=name, is_deleted=deleted)
    db.add(row)
    db.flush()
    return row


def mk_factory(db, ws, name, *, deleted=False):
    row = Factory(workspace_id=ws.id, name=name, abbreviation=name[:3].upper(), is_deleted=deleted)
    db.add(row)
    db.flush()
    return row


def mk_item(db, ws, name, unit="pcs", *, active=True):
    row = Item(
        workspace_id=ws.id, name=name, name_normalized=normalize_item_name(name),
        unit=unit, is_active=active,
    )
    db.add(row)
    db.flush()
    return row


def mk_dm(db, ws, name, *, deleted=False):
    row = DeliveryMethod(workspace_id=ws.id, name=name, is_deleted=deleted)
    db.add(row)
    db.flush()
    return row


def mk_product(db, ws, factory, item, *, qty=20, avg_cost=None, available=True,
                min_order_qty=None, deleted=False):
    row = Product(
        workspace_id=ws.id, item_id=item.id, factory_id=factory.id, qty=qty,
        avg_cost=avg_cost, min_order_qty=min_order_qty,
        is_available_for_sale=available, is_deleted=deleted,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def tg_c1(db, w1):
    return mk_tag(db, w1, "client")


@pytest.fixture
def tg_s1(db, w1):
    return mk_tag(db, w1, "supplier")


@pytest.fixture
def tg_x(db, w2):
    return mk_tag(db, w2, "client")


@pytest.fixture
def tg_i(db, w1):
    """An inactive W1 'client' tag (distinct row from TGC1)."""
    return mk_tag(db, w1, "client", active=False, name="Client (legacy)")


@pytest.fixture
def a1(db, w1, tg_c1):
    acct = mk_account(db, w1, "Acme Traders")
    mk_tag_assignment(db, acct, tg_c1)
    return acct


@pytest.fixture
def a2(db, w1, tg_s1):
    acct = mk_account(db, w1, "Steel Supplier Ltd")
    mk_tag_assignment(db, acct, tg_s1)
    return acct


@pytest.fixture
def a3(db, w1, tg_i):
    acct = mk_account(db, w1, "Old Client Co")
    mk_tag_assignment(db, acct, tg_i)
    return acct


@pytest.fixture
def a_x(db, w2, tg_x):
    acct = mk_account(db, w2, "Foreign Co")
    mk_tag_assignment(db, acct, tg_x)
    return acct


@pytest.fixture
def a_d(db, w1, tg_c1):
    acct = mk_account(db, w1, "Deleted Co", deleted=True)
    mk_tag_assignment(db, acct, tg_c1)
    return acct


@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1, "Main Plant")


@pytest.fixture
def f2(db, w1):
    return mk_factory(db, w1, "Second Plant")


@pytest.fixture
def f_x(db, w2):
    return mk_factory(db, w2, "Foreign Plant")


@pytest.fixture
def f_d(db, w1):
    return mk_factory(db, w1, "Old Plant", deleted=True)


@pytest.fixture
def i1(db, w1):
    return mk_item(db, w1, "Bolt M10", "pcs")


@pytest.fixture
def i2(db, w1):
    return mk_item(db, w1, "Paint 5L", "can")


@pytest.fixture
def i_s(db, w1):
    return mk_item(db, w1, "Installation", "hour")


@pytest.fixture
def i_u(db, w1):
    return mk_item(db, w1, "Calibration", "")


@pytest.fixture
def i_x(db, w2):
    return mk_item(db, w2, "Foreign Item", "pcs")


@pytest.fixture
def i_d(db, w1):
    return mk_item(db, w1, "Discontinued", "pcs", active=False)


@pytest.fixture
def i_e(db, w1):
    """IE — item in W1 whose name is '' (inserted directly, bypassing the schema).

    Unit is also left blank: FSI-04 is about the item_name fallback (Item #<id>),
    not the unit fallback (that's IU/FSI-03), but item_unit must still be falsy
    here for the description to end "(1.00 unit(s))" as the case specifies.
    """
    row = Item(workspace_id=w1.id, name="", name_normalized="", unit="", is_active=True)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def p1(db, w1, f1, i1):
    return mk_product(db, w1, f1, i1, qty=20, avg_cost=Decimal("4.00"))


@pytest.fixture
def dm1(db, w1):
    return mk_dm(db, w1, "Courier")


@pytest.fixture
def dm2(db, w1):
    return mk_dm(db, w1, "Van")


@pytest.fixture
def dm_x(db, w2):
    return mk_dm(db, w2, "Foreign Method")


@pytest.fixture
def dm_d(db, w1):
    return mk_dm(db, w1, "Retired Method", deleted=True)


# --------------------------------------------------------------------------- #
# Conventions -> SO / line / delivery / invoice / return / approver builders
# --------------------------------------------------------------------------- #

@pytest.fixture
def so(db, w1, a1, f1, u1):
    """SO(...) builder. Defaults per Conventions; SO1 = so() with no overrides."""
    def _mk(**overrides):
        _ensure_status10(db, w1)
        fields = {
            "workspace_id": w1.id, "account_id": a1.id, "factory_id": f1.id, "current_status_id": 10,
            "order_date": date(2026, 9, 1), "sales_order_number": "SO-2026-010",
            "contact_name": "Rahim", "created_by": u1.id, "total_amount": Decimal("0"),
        }
        fields.update(overrides)
        row = SalesOrder(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


def mk_line(db, order, *, item=None, description=None, requires_delivery=True,
            ordered, delivered=Decimal("0.00"), refunded=Decimal("0.00"),
            returned=Decimal("0.00"), unit_price=Decimal("1.00"), line_total=None,
            notes=None, fulfillment_completion_code=None, ws=None):
    """L(...) builder. ordered/delivered/refunded/returned always 2-decimal Decimals."""
    if line_total is None:
        line_total = ordered
    row = SalesOrderItem(
        workspace_id=(ws or order).workspace_id if ws is None else ws.id,
        sales_order_id=order.id,
        item_id=item.id if item else None,
        description=description,
        requires_delivery=requires_delivery,
        quantity_ordered=ordered, quantity_delivered=delivered,
        quantity_refunded=refunded, quantity_returned=returned,
        unit_price=unit_price, line_total=line_total, notes=notes,
        fulfillment_completion_code=fulfillment_completion_code,
    )
    db.add(row)
    db.flush()
    return row


def mk_delivery(db, order, *, status="planned", method=None, scheduled=date(2026, 10, 5),
                 tracking="TRK-100", notes="Gate 3", created_by=None, updated_by=None,
                 completion_code=None, number="DEL-2026-004", actual_delivery_date=None, ws=None):
    """D(...) builder. D1 default."""
    row = SalesDelivery(
        workspace_id=(ws or order).workspace_id if ws is None else ws.id,
        sales_order_id=order.id, delivery_number=number, delivery_status=status,
        delivery_method_id=method.id if method else None, scheduled_date=scheduled,
        tracking_number=tracking, notes=notes,
        created_by=created_by.id if created_by else order.created_by,
        updated_by=updated_by.id if updated_by else None,
        completion_code=completion_code, actual_delivery_date=actual_delivery_date,
    )
    db.add(row)
    db.flush()
    return row


_UNSET = object()


def mk_delivery_line(db, deliv, order_line, qty, *, notes=None, item_id=_UNSET):
    """DL(line, qty) builder. item_id copied from the order line unless overridden."""
    real_item_id = order_line.item_id if item_id is _UNSET else item_id
    row = SalesDeliveryItem(
        workspace_id=deliv.workspace_id, delivery_id=deliv.id,
        sales_order_item_id=order_line.id, item_id=real_item_id,
        quantity_delivered=qty, notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def mk_invoice(db, ws, *, status="confirmed", payment_status="unpaid", account=None):
    """INV(status, payment_status, ws=W1) builder."""
    row = AccountInvoice(
        workspace_id=ws.id, account_id=(account or _default_account(db, ws)).id,
        order_type="sales_order", invoice_type="receivable",
        invoice_status=status, payment_status=payment_status,
        invoice_amount=Decimal("100.00"), invoice_date=date(2026, 9, 1),
    )
    db.add(row)
    db.flush()
    return row


def _default_account(db, ws):
    """A throwaway account for an invoice fixture that doesn't need a specific one."""
    return mk_account(db, ws, f"Invoice Payer {ws.id}")


def link_invoice(db, order, invoice):
    order.invoice_id = invoice.id
    db.add(order)
    db.flush()
    return order


_return_seq_start = 1


def mk_return(db, order, *, status="pending", created_by=None, return_type="refund", ws=None):
    """RET(order, status) builder. `ws` overrides workspace_id ("but with workspace_id W0", SM-MOC-17)."""
    global _return_seq_start
    n = _return_seq_start
    _return_seq_start += 1
    row = SalesOrderReturn(
        workspace_id=(ws.id if ws is not None else order.workspace_id), sales_order_id=order.id,
        return_number=f"SR-TEST-{n:06d}", status=status, return_type=return_type,
        created_by=(created_by or order.created_by),
    )
    db.add(row)
    db.flush()
    return row


def mk_approver(db, order, user, *, approved=False, approved_at=None, assigned_at=None,
                 assigned_by=None, ws=None):
    """AP(order, user, approved, approved_at, assigned_at) builder. W1 unless `ws` given."""
    row = SalesOrderApprover(
        workspace_id=(ws or order).workspace_id if ws is None else ws.id,
        sales_order_id=order.id, user_id=user.id,
        assigned_by=(assigned_by.id if assigned_by is not None else user.id),
        assigned_at=assigned_at or datetime(2026, 9, 1, 9, 0, 0),
        approved=approved, approved_at=approved_at,
    )
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> generic helpers
# --------------------------------------------------------------------------- #

@pytest.fixture
def Y():
    return datetime.now().year


def reread(db, model, id_):
    db.expire_all()
    return db.get(model, id_)


NW_MODELS = [
    SalesOrder, SalesOrderItem, SalesOrderApprover, SalesOrderEvent,
    SalesDelivery, SalesDeliveryItem, Product, ProductLedger,
]


def nw_snapshot(db):
    db.expire_all()
    return {m: db.query(m).count() for m in NW_MODELS}


def assert_nw(db, before):
    assert nw_snapshot(db) == before


def missing_id(db, model):
    return (db.scalar(select(func.max(model.id))) or 0) + 1000


def events_for(db, order):
    db.expire_all()
    return (
        db.query(SalesOrderEvent)
        .filter(SalesOrderEvent.sales_order_id == order.id)
        .order_by(SalesOrderEvent.id)
        .all()
    )


def all_events(db):
    db.expire_all()
    return db.query(SalesOrderEvent).order_by(SalesOrderEvent.id).all()


def approvers_for(db, order):
    db.expire_all()
    return (
        db.query(SalesOrderApprover)
        .filter(SalesOrderApprover.sales_order_id == order.id)
        .order_by(SalesOrderApprover.id)
        .all()
    )


def deliveries_for(db, order):
    db.expire_all()
    return (
        db.query(SalesDelivery)
        .filter(SalesDelivery.sales_order_id == order.id)
        .order_by(SalesDelivery.id)
        .all()
    )


def delivery_lines_for(db, deliv):
    db.expire_all()
    return (
        db.query(SalesDeliveryItem)
        .filter(SalesDeliveryItem.delivery_id == deliv.id)
        .order_by(SalesDeliveryItem.id)
        .all()
    )


def ledger_rows(db):
    db.expire_all()
    return db.query(ProductLedger).order_by(ProductLedger.id).all()


# Convention "SQL capture" (BUG-720 cases only).
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


def assert_lock_before_write(statements, lock_table, write_table, write_verb="insert into"):
    def is_write(s):
        s = s.strip().lower()
        return s.startswith(write_verb) and write_table in s

    def is_lock(s):
        s = s.lower()
        return f"from {lock_table}" in s and "for update" in s

    write_idx = next((i for i, s in enumerate(statements) if is_write(s)), None)
    assert write_idx is not None, f"no {write_verb.upper()} on {write_table} captured"
    lock_idx = next((i for i, s in enumerate(statements[:write_idx]) if is_lock(s)), None)
    assert lock_idx is not None, f"no captured SELECT on {lock_table} contains FOR UPDATE"


def assert_locks_before_write(statements, lock_tables, write_table, write_verb="insert into"):
    """Several tables must each be locked before the first write (SA-14)."""
    for t in lock_tables:
        assert_lock_before_write(statements, t, write_table, write_verb)


def transient_line(*, requires_delivery, ordered, delivered, refunded):
    """A transient SalesOrderItem (not added to the session) for DLV/FUL."""
    return SalesOrderItem(
        requires_delivery=requires_delivery, quantity_ordered=ordered,
        quantity_delivered=delivered, quantity_refunded=refunded,
    )


# =========================================================================== #
# all_deliverable_items_delivered
# =========================================================================== #

def test_sm_dlv_01__empty_list_true():
    """SM-DLV-01 — an empty list returns True (vacuous).
    Rules: R4."""
    assert all_deliverable_items_delivered([]) is True


def test_sm_dlv_02__non_delivery_lines_ignored():
    """SM-DLV-02 — non-delivery lines are ignored, so two of them return True.
    Rules: R1, R4."""
    lines = [
        transient_line(requires_delivery=False, ordered=10, delivered=0, refunded=0),
        transient_line(requires_delivery=False, ordered=10, delivered=0, refunded=0),
    ]
    assert all_deliverable_items_delivered(lines) is True


def test_sm_dlv_03__exact_delivery_true():
    """SM-DLV-03 — delivered equals ordered returns True.
    Rules: R2."""
    lines = [transient_line(requires_delivery=True, ordered=10, delivered=10, refunded=0)]
    assert all_deliverable_items_delivered(lines) is True


def test_sm_dlv_04__over_delivered_true():
    """SM-DLV-04 — delivered more than ordered still returns True.
    Rules: R2."""
    lines = [transient_line(requires_delivery=True, ordered=10, delivered=12, refunded=0)]
    assert all_deliverable_items_delivered(lines) is True


def test_sm_dlv_05__short_false():
    """SM-DLV-05 — delivered + refunded short of ordered returns False.
    Rules: R3."""
    lines = [transient_line(requires_delivery=True, ordered=10, delivered=7, refunded=2)]
    assert all_deliverable_items_delivered(lines) is False


def test_sm_dlv_06__refunded_fills_gap_true():
    """SM-DLV-06 — delivered + refunded meets ordered returns True.
    Rules: R2."""
    lines = [transient_line(requires_delivery=True, ordered=10, delivered=8, refunded=2)]
    assert all_deliverable_items_delivered(lines) is True


def test_sm_dlv_07__none_refunded_counts_as_zero():
    """SM-DLV-07 — a None refunded quantity counts as 0.
    Rules: R2."""
    a = transient_line(requires_delivery=True, ordered=10, delivered=10, refunded=None)
    b = transient_line(requires_delivery=True, ordered=10, delivered=9, refunded=None)
    assert all_deliverable_items_delivered([a]) is True
    assert all_deliverable_items_delivered([b]) is False


def test_sm_dlv_08__any_short_line_false():
    """SM-DLV-08 — one short line among several makes the whole result False.
    Rules: R3."""
    x = transient_line(requires_delivery=True, ordered=10, delivered=10, refunded=0)
    y = transient_line(requires_delivery=True, ordered=10, delivered=9, refunded=0)
    assert all_deliverable_items_delivered([x, y]) is False


def test_sm_dlv_09__non_delivery_line_ignored_among_delivery_lines():
    """SM-DLV-09 — a non-delivery line never blocks the delivery-lines check.
    Rules: R1."""
    lines = [
        transient_line(requires_delivery=True, ordered=10, delivered=10, refunded=0),
        transient_line(requires_delivery=False, ordered=10, delivered=0, refunded=0),
    ]
    assert all_deliverable_items_delivered(lines) is True


# =========================================================================== #
# all_fulfilment_items_fulfilled
# =========================================================================== #

def test_sm_ful_01__empty_list_true():
    """SM-FUL-01 — an empty list returns True (vacuous).
    Rules: R2."""
    assert all_fulfilment_items_fulfilled([]) is True


def test_sm_ful_02__delivery_lines_ignored():
    """SM-FUL-02 — requires_delivery=True lines are ignored, so two of them return True.
    Rules: R1, R2."""
    lines = [
        transient_line(requires_delivery=True, ordered=10, delivered=0, refunded=0),
        transient_line(requires_delivery=True, ordered=10, delivered=0, refunded=0),
    ]
    assert all_fulfilment_items_fulfilled(lines) is True


def test_sm_ful_03__refunded_fills_gap_true():
    """SM-FUL-03 — a non-delivery line's delivered + refunded meets ordered returns True.
    Rules: R1."""
    lines = [transient_line(requires_delivery=False, ordered=10, delivered=8, refunded=2)]
    assert all_fulfilment_items_fulfilled(lines) is True


def test_sm_ful_04__short_false():
    """SM-FUL-04 — a non-delivery line short of ordered returns False.
    Rules: R1."""
    lines = [transient_line(requires_delivery=False, ordered=10, delivered=7, refunded=2)]
    assert all_fulfilment_items_fulfilled(lines) is False


def test_sm_ful_05__none_refunded_counts_as_zero():
    """SM-FUL-05 — a None refunded quantity counts as 0.
    Rules: R1."""
    a = transient_line(requires_delivery=False, ordered=10, delivered=10, refunded=None)
    b = transient_line(requires_delivery=False, ordered=10, delivered=9, refunded=None)
    assert all_fulfilment_items_fulfilled([a]) is True
    assert all_fulfilment_items_fulfilled([b]) is False


def test_sm_ful_06__mixed_lines_true():
    """SM-FUL-06 — two done non-delivery lines plus an untouched delivery line return True.
    Rules: R1."""
    lines = [
        transient_line(requires_delivery=False, ordered=5, delivered=5, refunded=0),
        transient_line(requires_delivery=False, ordered=5, delivered=6, refunded=0),
        transient_line(requires_delivery=True, ordered=10, delivered=0, refunded=0),
    ]
    assert all_fulfilment_items_fulfilled(lines) is True


# =========================================================================== #
# SalesManager.create_sales_order_with_items
# =========================================================================== #

def default_order_data(a1, f1, **overrides):
    data = {
        "account_id": a1.id, "factory_id": f1.id, "order_date": date(2026, 9, 1),
        "contact_name": "Rahim", "total_amount": Decimal("999.00"),
    }
    data.update(overrides)
    return data


def default_items_data(i1):
    return [
        {"item_id": i1.id, "quantity_ordered": Decimal("10"), "unit_price": Decimal("5.00"),
         "line_total": Decimal("51.00")},
        {"item_id": None, "description": "Installation work", "quantity_ordered": Decimal("2"),
         "unit_price": Decimal("50.00"), "line_total": Decimal("100.00"), "requires_delivery": False},
    ]


def test_sm_co_01__happy_path_order_fields(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-01 — a default create stores the order with the right fields and defaults.
    Rules: R4, R5."""
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert isinstance(result, SalesOrder)
    assert result.id is not None
    r = reread(db, SalesOrder, result.id)
    assert r.account_id == a1.id
    assert r.factory_id == f1.id
    assert r.order_date == date(2026, 9, 1)
    assert r.contact_name == "Rahim"
    assert r.workspace_id == w1.id
    assert r.created_by == u1.id
    assert r.current_status_id == 10
    assert r.sales_order_number == f"SO-{Y}-001"
    assert r.total_amount == Decimal("999.00")
    assert r.order_info_confirmed is False
    assert r.items_confirmed is False
    assert r.invoice_confirmed is False
    assert r.order_completed is False
    assert r.is_fully_delivered is False
    assert r.is_invoiced is False
    assert r.paid is False
    assert r.required_approvals is None
    assert r.invoice_id is None
    assert r.completed_at is None
    assert r.completed_by is None
    assert r.expected_delivery_date is None
    assert r.description is None


def order_items_for(db, order):
    db.expire_all()
    return (
        db.query(SalesOrderItem)
        .filter(SalesOrderItem.sales_order_id == order.id)
        .order_by(SalesOrderItem.id)
        .all()
    )


def test_sm_co_02__order_items_stored(db, M, w1, a1, f1, u1, i1):
    """SM-CO-02 — exactly 2 order-item rows are stored with the given values, not recomputed.
    Rules: R8."""
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    items = order_items_for(db, result)
    assert len(items) == 2
    assert all(i.workspace_id == w1.id for i in items)
    l1, l2 = items
    assert l1.item_id == i1.id
    assert l1.quantity_ordered == Decimal("10")
    assert l1.unit_price == Decimal("5.00")
    assert l1.line_total == Decimal("51.00")
    assert l1.requires_delivery is True
    assert l2.item_id is None
    assert l2.description == "Installation work"
    assert l2.requires_delivery is False
    assert l2.line_total == Decimal("100.00")
    for line in items:
        assert line.quantity_delivered == Decimal("0")
        assert line.quantity_returned == Decimal("0")
        assert line.quantity_refunded == Decimal("0")
        assert line.fulfillment_completion_code is None


def test_sm_co_03__approver_row_created(db, M, w1, a1, f1, u1, i1):
    """SM-CO-03 — exactly one approver row is created for the creator.
    Rules: R6."""
    t0 = datetime.utcnow()
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    t1 = datetime.utcnow()
    aps = approvers_for(db, result)
    assert len(aps) == 1
    ap = aps[0]
    assert ap.user_id == u1.id
    assert ap.assigned_by == u1.id
    assert ap.approved is False
    assert ap.approved_at is None
    assert t0 <= ap.assigned_at <= t1


def test_sm_co_04__created_event_logged(db, M, w1, a1, f1, u1, i1):
    """SM-CO-04 — exactly one 'created' event is logged.
    Rules: R7."""
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    evs = events_for(db, result)
    assert len(evs) == 1
    assert evs[0].event_type == "created"
    assert evs[0].description == "Order created"
    assert evs[0].performed_by == u1.id
    assert evs[0].metadata_json is None
    assert evs[0].workspace_id == w1.id


def test_sm_co_05__total_amount_defaults_zero(db, M, w1, a1, f1, u1, i1):
    """SM-CO-05 — omitting total_amount stores 0.
    Rules: R4."""
    order_data = default_order_data(a1, f1)
    del order_data["total_amount"]
    result = M.create_sales_order_with_items(db, order_data, default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).total_amount == Decimal("0")


def test_sm_co_06__items_data_mutated_in_place(db, M, w1, a1, f1, u1, i1):
    """SM-CO-06 — the caller's item dicts gain sales_order_id and workspace_id.
    Rules: R9."""
    items_data = default_items_data(i1)
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), items_data, w1.id, u1.id)
    for d in items_data:
        assert d["sales_order_id"] == result.id
        assert d["workspace_id"] == w1.id


def test_sm_co_07__empty_list_raises(db, M, w1, a1, f1, u1):
    """SM-CO-07 — items_data=[] raises ValueError; nothing written.
    Rules: R1."""
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), [], w1.id, u1.id)
    assert str(exc.value) == "Sales order must have at least one item"
    assert_nw(db, before)


def test_sm_co_08__none_items_raises(db, M, w1, a1, f1, u1):
    """SM-CO-08 — items_data=None raises the same ValueError; nothing written.
    Rules: R1."""
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), None, w1.id, u1.id)
    assert str(exc.value) == "Sales order must have at least one item"
    assert_nw(db, before)


def test_sm_co_09__duplicate_catalog_item_409(db, M, w1, a1, f1, u1, i1):
    """SM-CO-09 — two lines with the same catalog item_id raise 409; nothing written.
    Rules: R2."""
    before = nw_snapshot(db)
    items = [
        {"item_id": i1.id, "quantity_ordered": Decimal("1"), "unit_price": Decimal("1"), "line_total": Decimal("1")},
        {"item_id": i1.id, "quantity_ordered": Decimal("1"), "unit_price": Decimal("1"), "line_total": Decimal("1")},
    ]
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Bolt M10 appears more than once on this order"
    assert_nw(db, before)


def test_sm_co_10__duplicate_free_text_allowed(db, M, w1, a1, f1, u1):
    """SM-CO-10 — two free-text lines with the same text are not duplicates.
    Rules: R2."""
    items = [
        {"item_id": None, "description": "Crate", "quantity_ordered": Decimal("1"), "unit_price": Decimal("1"), "line_total": Decimal("1")},
        {"item_id": None, "description": "Crate", "quantity_ordered": Decimal("1"), "unit_price": Decimal("1"), "line_total": Decimal("1")},
    ]
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert len(order_items_for(db, result)) == 2


def single_item_line(item, qty, unit_price=Decimal("5.00")):
    qty = qty if isinstance(qty, Decimal) else Decimal(qty)
    return [{"item_id": item.id, "quantity_ordered": qty, "unit_price": unit_price, "line_total": qty * unit_price}]


def test_sm_co_12__below_min_order_qty_422(db, M, w1, a1, f1, u1, i1):
    """SM-CO-12 — ordering below the sellable product's min_order_qty raises 422; nothing written.
    Rules: R3."""
    mk_product(db, w1, f1, i1, qty=20, avg_cost=Decimal("4.00"), min_order_qty=5)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), single_item_line(i1, "4"), w1.id, u1.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Minimum order quantity for Bolt M10 is 5 (requested 4)"
    assert_nw(db, before)


def test_sm_co_13__at_min_order_qty_boundary(db, M, w1, a1, f1, u1, i1):
    """SM-CO-13 — ordering exactly the minimum is accepted.
    Rules: R3."""
    mk_product(db, w1, f1, i1, qty=20, avg_cost=Decimal("4.00"), min_order_qty=5)
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), single_item_line(i1, "5"), w1.id, u1.id)
    items = order_items_for(db, result)
    assert len(items) == 1
    assert items[0].quantity_ordered == Decimal("5")


def test_sm_co_14__null_min_order_qty_accepted(db, M, w1, a1, f1, u1, i1):
    """SM-CO-14 — a null min_order_qty applies no minimum.
    Rules: R3."""
    mk_product(db, w1, f1, i1, qty=20, avg_cost=Decimal("4.00"), min_order_qty=None)
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), single_item_line(i1, "1"), w1.id, u1.id)
    assert result.id is not None


def test_sm_co_15__zero_min_order_qty_accepted(db, M, w1, a1, f1, u1, i1):
    """SM-CO-15 — a min_order_qty of 0 applies no minimum.
    Rules: R3."""
    mk_product(db, w1, f1, i1, qty=20, avg_cost=Decimal("4.00"), min_order_qty=0)
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), single_item_line(i1, "1"), w1.id, u1.id)
    assert result.id is not None


def test_sm_co_16__non_sellable_product_minimum_ignored(db, M, w1, a1, f1, u1, i1):
    """SM-CO-16 — a non-sellable product's minimum does not apply.
    Rules: R3."""
    mk_product(db, w1, f1, i1, qty=20, min_order_qty=5, available=False)
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), single_item_line(i1, "1"), w1.id, u1.id)
    assert result.id is not None


def test_sm_co_17__minimum_scoped_to_factory(db, M, w1, a1, f1, f2, u1, i1):
    """SM-CO-17 — a minimum set for a different factory does not apply to this order's factory.
    Rules: R3."""
    mk_product(db, w1, f2, i1, qty=20, min_order_qty=5)
    result = M.create_sales_order_with_items(
        db, default_order_data(a1, f1), single_item_line(i1, "1"), w1.id, u1.id
    )
    assert result.id is not None


def test_sm_co_18__duplicate_before_min_qty(db, M, w1, a1, f1, u1, i1):
    """SM-CO-18 — the duplicate-item check (R2) runs before the minimum-quantity check (R3).
    Rules: R2, R3."""
    mk_product(db, w1, f1, i1, qty=20, min_order_qty=5)
    before = nw_snapshot(db)
    items = single_item_line(i1, "1") + single_item_line(i1, "1")
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Bolt M10 appears more than once on this order"
    assert_nw(db, before)


def test_sm_co_19__invalid_line_data_partial_write(db, M, w1, a1, f1, u1, i1):
    """SM-CO-19 — a structurally invalid second line raises pydantic.ValidationError; line 1 was already written.
    Rules: R10."""
    items = single_item_line(i1, "10") + [
        {"item_id": None, "description": "X", "quantity_ordered": Decimal("1"), "unit_price": Decimal("1")}
    ]
    with pytest.raises(ValidationError):
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    db.expire_all()
    orders = db.query(SalesOrder).filter(SalesOrder.workspace_id == w1.id).all()
    assert len(orders) == 1
    order = orders[0]
    assert len(approvers_for(db, order)) == 1
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "created"
    assert len(order_items_for(db, order)) == 1


def test_sm_co_20__blank_description_no_lines_written(db, M, w1, a1, f1, u1):
    """SM-CO-20 — a blank-after-strip free-text description raises ValidationError; the order ends with 0 lines.
    Rules: R10."""
    items = [{"item_id": None, "description": "   ", "quantity_ordered": Decimal("1"),
              "unit_price": Decimal("1"), "line_total": Decimal("1")}]
    with pytest.raises(ValidationError):
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    db.expire_all()
    orders = db.query(SalesOrder).filter(SalesOrder.workspace_id == w1.id).all()
    assert len(orders) == 1
    assert len(order_items_for(db, orders[0])) == 0


def test_sm_co_21__non_dict_item_raises_typeerror(db, M, w1, a1, f1, u1):
    """SM-CO-21 — a non-dict item entry raises TypeError when the manager tries to mutate it.
    Rules: R11."""
    items = [SimpleNamespace(item_id=None, description="X", quantity_ordered=Decimal("1"),
                              unit_price=Decimal("1"), line_total=Decimal("1"))]
    with pytest.raises(TypeError):
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)


def test_sm_co_22__invalid_order_data_nothing_written(db, M, w1, a1, f1, u1, i1):
    """SM-CO-22 — a missing required order_date raises ValidationError before anything is written.
    Rules: Errors "invalid order data"."""
    before = nw_snapshot(db)
    order_data = default_order_data(a1, f1)
    del order_data["order_date"]
    with pytest.raises(ValidationError):
        M.create_sales_order_with_items(db, order_data, default_items_data(i1), w1.id, u1.id)
    assert_nw(db, before)


def bulk_insert_so_numbers(db, ws, account, factory, creator, numbers):
    _ensure_status10(db, ws)
    rows = [
        {
            "workspace_id": ws.id, "account_id": account.id, "factory_id": factory.id,
            "current_status_id": 10, "order_date": date(2026, 9, 1),
            "sales_order_number": n, "contact_name": "Rahim", "created_by": creator.id,
            "total_amount": Decimal("0"),
        }
        for n in numbers
    ]
    db.execute(SalesOrder.__table__.insert(), rows)
    db.flush()


def test_sm_co_23__next_number_sequential(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-23 — the new order number follows the highest existing sequence for the year.
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y}-{n:03d}" for n in (1, 2, 3)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-004"


def test_sm_co_24__nine_to_ten(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-24 — sequence rolls from 009 to 010.
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y}-{n:03d}" for n in range(1, 10)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-010"


def test_sm_co_25__ninety_nine_to_hundred(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-25 — sequence rolls from 099 to 100.
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y}-{n:03d}" for n in range(1, 100)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-100"


def test_sm_co_26__nine_ninety_nine_to_thousand(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-26 — sequence rolls from 999 to 1000 (bulk insert of 999 existing orders).
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y}-{n:03d}" for n in range(1, 1000)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-1000"


def test_sm_co_27__earlier_years_not_counted(db, M, w1, a1, f1, u1, i1, Y):
    """SM-CO-27 — orders from an earlier year don't affect this year's sequence.
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y - 1}-{n:03d}" for n in (1, 2)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-001"


def test_sm_co_28__other_workspace_not_counted(db, M, w1, w2, a1, f1, u1, i1, Y):
    """SM-CO-28 — another workspace's orders of the same year don't affect this workspace's sequence.
    Rules: R5."""
    bulk_insert_so_numbers(db, w1, a1, f1, u1, [f"SO-{Y}-{n:03d}" for n in (1, 2, 3)])
    acct2 = mk_account(db, w2, "W2 Acct")
    fac2 = mk_factory(db, w2, "W2 Factory")
    bulk_insert_so_numbers(db, w2, acct2, fac2, u1, [f"SO-{Y}-{n:03d}" for n in (101, 102, 103, 104, 105)])
    result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
    assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-004"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-726"))
def test_sm_co_29__number_collides_across_workspaces(db, M, w1, w2, a1, f1, u1, i1, Y):
    """SM-CO-29 — order numbers should be independent per workspace but collide today on a global unique index.
    Rules: R5."""
    acct2 = mk_account(db, w2, "W2 Acct")
    fac2 = mk_factory(db, w2, "W2 Factory")
    bulk_insert_so_numbers(db, w2, acct2, fac2, u1, [f"SO-{Y}-001"])
    with db.begin_nested():
        result = M.create_sales_order_with_items(db, default_order_data(a1, f1), default_items_data(i1), w1.id, u1.id)
        assert reread(db, SalesOrder, result.id).sales_order_number == f"SO-{Y}-001"
    db.expire_all()
    w2_order = db.query(SalesOrder).filter(SalesOrder.workspace_id == w2.id).first()
    assert w2_order.sales_order_number == f"SO-{Y}-001"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_30__foreign_account_404(db, M, w1, a_x, f1, u1, i1):
    """SM-CO-30 — an account from another workspace should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a_x, f1), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {a_x.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_31__soft_deleted_account_404(db, M, w1, a_d, f1, u1, i1):
    """SM-CO-31 — a soft-deleted account should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a_d, f1), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {a_d.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_32__nonexistent_account_404(db, M, w1, f1, a1, u1, i1):
    """SM-CO-32 — a non-existent account_id should 404 today it raises IntegrityError.
    Rules: R12."""
    before = nw_snapshot(db)
    order_data = default_order_data(a1, f1, account_id=999999999)
    with db.begin_nested():
        with pytest.raises(HTTPException) as exc:
            M.create_sales_order_with_items(db, order_data, default_items_data(i1), w1.id, u1.id)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Account with ID 999999999 not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_33__foreign_factory_404(db, M, w1, a1, f_x, u1, i1):
    """SM-CO-33 — a factory from another workspace should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a1, f_x), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f_x.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_34__soft_deleted_factory_404(db, M, w1, a1, f_d, u1, i1):
    """SM-CO-34 — a soft-deleted factory should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a1, f_d), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f_d.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_35__foreign_catalog_item_404(db, M, w1, a1, f1, u1, i_x):
    """SM-CO-35 — a catalog item from another workspace should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a1, f1), single_item_line(i_x, "1"), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {i_x.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_36__inactive_catalog_item_404(db, M, w1, a1, f1, u1, i_d):
    """SM-CO-36 — an inactive catalog item should 404; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a1, f1), single_item_line(i_d, "1"), w1.id, u1.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {i_d.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-729"))
def test_sm_co_37__supplier_only_account_400(db, M, w1, a2, f1, u1, i1):
    """SM-CO-37 — a supplier-only account (no client tag) should 400; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a2, f1), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Selected account is not a client"
    assert_nw(db, before)


def test_sm_co_38__item_input_schema_range_accepted(db):
    """SM-CO-38 — the schema accepts the extremes of its declared range today.
    Rules: R13."""
    lo = SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("0.01"), unit_price=Decimal("0"))
    assert lo.quantity_ordered == Decimal("0.01")
    hi = SalesOrderItemInput(
        item_id=1, quantity_ordered=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99")
    )
    assert hi.quantity_ordered == Decimal("9999999999999.99")
    assert hi.unit_price == Decimal("9999999999999.99")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-order"))
def test_sm_co_39__zero_quantity_rejected(db):
    """SM-CO-39 — a zero quantity should be rejected by the schema.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("0"), unit_price=Decimal("5"))
    assert "quantity_ordered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-order"))
def test_sm_co_40__negative_quantity_rejected(db):
    """SM-CO-40 — a negative quantity should be rejected by the schema.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("-5"), unit_price=Decimal("5"))
    assert "quantity_ordered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-order"))
def test_sm_co_41__negative_unit_price_rejected(db):
    """SM-CO-41 — a negative unit price should be rejected by the schema.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("1"), unit_price=Decimal("-0.01"))
    assert "unit_price" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-order"))
def test_sm_co_42__over_precision_quantity_rejected(db):
    """SM-CO-42 — a quantity with more than 2 decimal places should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("1.005"), unit_price=Decimal("10"))
    assert "quantity_ordered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-order"))
def test_sm_co_43__over_precision_price_rejected(db):
    """SM-CO-43 — a price with more than 2 decimal places should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("1"), unit_price=Decimal("10.001"))
    assert "unit_price" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-order"))
def test_sm_co_44__oversized_quantity_rejected(db):
    """SM-CO-44 — a 14-digit quantity should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("10000000000000"), unit_price=Decimal("1"))
    assert "quantity_ordered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-order"))
def test_sm_co_45__oversized_price_rejected(db):
    """SM-CO-45 — a 14-digit price should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("1"), unit_price=Decimal("10000000000000"))
    assert "unit_price" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-729"))
def test_sm_co_46__inactive_client_tag_400(db, M, w1, a3, f1, u1, i1):
    """SM-CO-46 — an account whose only client tag is inactive should 400; nothing written.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a3, f1), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Selected account is not a client"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-order"))
def test_sm_co_47__invalid_line_validated_before_any_write(db, M, w1, a1, f1, u1, i1):
    """SM-CO-47 — a negative-quantity second line should be rejected and nothing written at all.
    Rules: R13."""
    before = nw_snapshot(db)
    items = default_items_data(i1)
    items[1] = {"item_id": None, "description": "Installation work", "quantity_ordered": Decimal("-1"),
                "unit_price": Decimal("50.00"), "line_total": Decimal("-50.00"), "requires_delivery": False}
    with pytest.raises(ValidationError):
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-order"))
def test_sm_co_48__over_precision_line_validated_before_any_write(db, M, w1, a1, f1, u1, i1):
    """SM-CO-48 — an over-precision price on the second line should be rejected and nothing written at all.
    Rules: R13."""
    before = nw_snapshot(db)
    items = default_items_data(i1)
    items[1]["unit_price"] = Decimal("50.001")
    with pytest.raises(ValidationError):
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert_nw(db, before)


def test_sm_co_49__no_items_before_account_check(db, M, w1, a_x, f1, u1):
    """SM-CO-49 — the no-items check (R1) runs before the account check (R12), so ValueError wins.
    Rules: R1, R12."""
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_sales_order_with_items(db, default_order_data(a_x, f1), [], w1.id, u1.id)
    assert str(exc.value) == "Sales order must have at least one item"
    assert not isinstance(exc.value, HTTPException)
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_50__foreign_item_404_before_duplicate(db, M, w1, a1, f1, u1, i_x):
    """SM-CO-50 — a foreign-workspace item should 404 (R12) even before the duplicate check (R2) fires.
    Rules: R12, R2a, R2."""
    before = nw_snapshot(db)
    items = single_item_line(i_x, "1") + single_item_line(i_x, "1")
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(db, default_order_data(a1, f1), items, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Item with ID {i_x.id} not found"
    assert_nw(db, before)


def test_sm_co_51__missing_factory_id_key_raises_keyerror(db, M, w1, a1, f1, u1, i1):
    """SM-CO-51 — a missing factory_id key in order_data raises KeyError; nothing written.
    Rules: Inputs `factory_id` key (G10)."""
    before = nw_snapshot(db)
    order_data = default_order_data(a1, f1)
    del order_data["factory_id"]
    with pytest.raises(KeyError) as exc:
        M.create_sales_order_with_items(db, order_data, default_items_data(i1), w1.id, u1.id)
    assert exc.value.args == ("factory_id",)
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-728"))
def test_sm_co_52__account_checked_before_factory(db, M, w1, a_x, f_x, u1, i_x):
    """SM-CO-52 — the account check (R12) runs before the factory check.
    Rules: R12."""
    before = nw_snapshot(db)
    items = single_item_line(i_x, "1")
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(db, default_order_data(a_x, f_x), items, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {a_x.id} not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-729"))
def test_sm_co_53__client_tag_checked_before_factory(db, M, w1, a2, f_x, u1, i1):
    """SM-CO-53 — the client-tag check runs before the factory check.
    Rules: R12."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.create_sales_order_with_items(
            db, default_order_data(a2, f_x), default_items_data(i1), w1.id, u1.id
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Selected account is not a client"
    assert_nw(db, before)


# =========================================================================== #
# SalesManager.create_delivery_with_items
# =========================================================================== #

def cd_setup(db, so, i1, i_s, **order_overrides):
    """SO1 with invoice_confirmed=True and lines LA, LB, LB2, LS (Conventions)."""
    order_overrides.setdefault("invoice_confirmed", True)
    order = so(**order_overrides)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    LB = mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"))
    LB2 = mk_line(db, order, description="Pallet wrap", ordered=Decimal("3.00"))
    LS = mk_line(db, order, item=i_s, requires_delivery=False, ordered=Decimal("5.00"))
    return order, LA, LB, LB2, LS


def default_delivery_data(order, dm1, **overrides):
    data = {
        "sales_order_id": order.id, "delivery_method_id": dm1.id, "scheduled_date": date(2026, 10, 5),
        "tracking_number": "TRK-100", "notes": "Gate 3",
    }
    data.update(overrides)
    return data


def bulk_insert_del_numbers(db, ws, order, numbers, *, status="planned", created_by=None):
    rows = [
        {
            "workspace_id": ws.id, "sales_order_id": order.id, "delivery_number": n,
            "delivery_status": status, "scheduled_date": date(2026, 10, 5),
            "tracking_number": "TRK-100", "notes": "Gate 3",
            "created_by": (created_by or order.created_by),
        }
        for n in numbers
    ]
    db.execute(SalesDelivery.__table__.insert(), rows)
    db.flush()


def test_sm_cd_01__happy_path(db, M, w1, so, i1, i_s, dm1, u1, Y):
    """SM-CD-01 — a default delivery plan is created with its lines, and order-item quantities are untouched.
    Rules: R4, R9, R12."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    items = [
        {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("4"), "notes": "fragile"},
        {"sales_order_item_id": LB.id, "quantity_delivered": Decimal("2.50")},
    ]
    deliv, result_order = M.create_delivery_with_items(db, default_delivery_data(order, dm1), items, w1.id, u1.id)
    assert result_order.id == order.id
    r = reread(db, SalesDelivery, deliv.id)
    assert r.sales_order_id == order.id
    assert r.delivery_method_id == dm1.id
    assert r.scheduled_date == date(2026, 10, 5)
    assert r.tracking_number == "TRK-100"
    assert r.notes == "Gate 3"
    assert r.workspace_id == w1.id
    assert r.created_by == u1.id
    assert r.delivery_status == "planned"
    assert r.delivery_number == f"DEL-{Y}-001"
    lines = delivery_lines_for(db, deliv)
    assert len(lines) == 2
    l1, l2 = lines
    assert l1.sales_order_item_id == LA.id
    assert l1.item_id == i1.id
    assert l1.quantity_delivered == Decimal("4")
    assert l1.notes == "fragile"
    assert l1.workspace_id == w1.id
    assert l2.sales_order_item_id == LB.id
    assert l2.item_id is None
    assert l2.quantity_delivered == Decimal("2.50")
    assert l2.notes is None
    assert l2.workspace_id == w1.id
    assert reread(db, SalesOrderItem, LA.id).quantity_delivered == Decimal("0.00")
    assert reread(db, SalesOrderItem, LA.id).quantity_refunded == Decimal("0.00")
    assert reread(db, SalesOrderItem, LB.id).quantity_delivered == Decimal("0.00")
    assert reread(db, SalesOrderItem, LB.id).quantity_refunded == Decimal("0.00")


def test_sm_cd_02__delivery_planned_event(db, M, w1, so, i1, i_s, dm1, u1, Y):
    """SM-CD-02 — exactly one delivery_planned event is logged with the right description and metadata.
    Rules: R11."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    items = [
        {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("4"), "notes": "fragile"},
        {"sales_order_item_id": LB.id, "quantity_delivered": Decimal("2.50")},
    ]
    deliv, _ = M.create_delivery_with_items(db, default_delivery_data(order, dm1), items, w1.id, u1.id)
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_planned"
    assert evs[0].description == f"Delivery DEL-{Y}-001 planned (6.50 units across 2 items)"
    assert evs[0].metadata_json == {"delivery_id": deliv.id, "tracking_number": "TRK-100"}
    assert evs[0].performed_by == u1.id


def test_sm_cd_03__singular_unit_description_no_tracking(db, M, w1, so, i1, i_s, dm1, u1, Y):
    """SM-CD-03 — one unit across one item is singular, and a missing tracking number is null in metadata.
    Rules: R11."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    delivery_data = default_delivery_data(order, dm1)
    del delivery_data["tracking_number"]
    deliv, _ = M.create_delivery_with_items(
        db, delivery_data, [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
    )
    evs = events_for(db, order)
    assert evs[0].description == f"Delivery DEL-{Y}-001 planned (1 unit across 1 item)"
    assert evs[0].metadata_json == {"delivery_id": deliv.id, "tracking_number": None}


def test_sm_cd_04__plural_units_description(db, M, w1, so, i1, i_s, dm1, u1, Y):
    """SM-CD-04 — two units is plural.
    Rules: R11."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("2")}], w1.id, u1.id
    )
    evs = events_for(db, order)
    assert evs[0].description.endswith("(2 units across 1 item)")


def test_sm_cd_05__fractional_total_singular_unit(db, M, w1, so, i1, i_s, dm1, u1, Y):
    """SM-CD-05 — a total of 1.00 (numerically equal to 1) is still singular 'unit'.
    Rules: R11."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [
            {"sales_order_item_id": LB.id, "quantity_delivered": Decimal("0.50")},
            {"sales_order_item_id": LB2.id, "quantity_delivered": Decimal("0.50")},
        ], w1.id, u1.id
    )
    evs = events_for(db, order)
    assert evs[0].description.endswith("(1.00 unit across 2 items)")


def test_sm_cd_06__empty_items_raises(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-06 — an empty item list raises ValueError; nothing written.
    Rules: R1."""
    order, *_ = cd_setup(db, so, i1, i_s)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(db, default_delivery_data(order, dm1), [], w1.id, u1.id)
    assert str(exc.value) == "Delivery must have at least one item"
    assert_nw(db, before)


def test_sm_cd_07__nonexistent_order_raises(db, M, w1, dm1, u1):
    """SM-CD-07 — a non-existent sales_order_id raises ValueError; nothing written.
    Rules: R2."""
    before = nw_snapshot(db)
    delivery_data = {
        "sales_order_id": 999999999, "delivery_method_id": dm1.id, "scheduled_date": date(2026, 10, 5),
        "tracking_number": "TRK-100", "notes": "Gate 3",
    }
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, delivery_data, [{"sales_order_item_id": 1, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == "Sales order 999999999 not found"
    assert_nw(db, before)


def test_sm_cd_08__foreign_order_not_found(db, M, w1, w2, so, a_x, f_x, u1, dm1):
    """SM-CD-08 — an order that exists only in another workspace is not found.
    Rules: R2."""
    sox = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id,
              sales_order_number="SO-2026-900", invoice_confirmed=True)
    lx = mk_line(db, sox, ordered=Decimal("5.00"), description="Foreign line")
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(sox, dm1),
            [{"sales_order_item_id": lx.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order {sox.id} not found"
    assert_nw(db, before)


def test_sm_cd_09__invoice_not_confirmed_raises(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-09 — planning a delivery before the invoice is finalized raises ValueError; nothing written.
    Rules: R3."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s, invoice_confirmed=False)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == "Finalize the invoice before planning a delivery"
    assert_nw(db, before)


def test_sm_cd_10__nonexistent_order_item(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-10 — a non-existent sales_order_item_id raises ValueError; no delivery lines or event written.
    Rules: R5, R10."""
    order, *_ = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": 999999999, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == "Sales order item 999999999 not found"
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


def test_sm_cd_11__foreign_order_item(db, M, w1, w2, so, a_x, f_x, i1, i_s, dm1, u1):
    """SM-CD-11 — a sales order item belonging to another workspace is not found.
    Rules: R5."""
    order, *_ = cd_setup(db, so, i1, i_s)
    sox = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id,
              sales_order_number="SO-2026-900", invoice_confirmed=True)
    lx = mk_line(db, sox, ordered=Decimal("5.00"), description="Foreign line")
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": lx.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order item {lx.id} not found"
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-723"))
def test_sm_cd_12__line_from_other_order_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-12 — a line from a different sales order in the same workspace should be rejected.
    Rules: R5."""
    order, *_ = cd_setup(db, so, i1, i_s)
    so2 = so(sales_order_number="SO-2026-012", invoice_confirmed=True)
    l2 = mk_line(db, so2, item=i1, ordered=Decimal("10.00"))
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": l2.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order item {l2.id} does not belong to sales order {order.id}"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))
    assert reread(db, SalesOrderItem, l2.id).quantity_delivered == Decimal("0.00")


def test_sm_cd_13__non_delivery_line_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-13 — a line marked requires_delivery=False cannot be planned into a delivery.
    Rules: R6."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LS.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == (
        f"Sales order item {LS.id} does not require delivery — "
        "it should be fulfilled directly, not delivered"
    )
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


def test_sm_cd_14__second_line_non_delivery_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-14 — a non-delivery line later in the request raises the same R6 error; partial write allowed.
    Rules: R10."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("2")},
                {"sales_order_item_id": LS.id, "quantity_delivered": Decimal("1")},
            ], w1.id, u1.id
        )
    assert str(exc.value) == (
        f"Sales order item {LS.id} does not require delivery — "
        "it should be fulfilled directly, not delivered"
    )
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))
    deliveries = deliveries_for(db, order)
    if deliveries:
        lines = delivery_lines_for(db, deliveries[-1])
        assert len(lines) == 1
        assert lines[0].sales_order_item_id == LA.id
        assert lines[0].quantity_delivered == Decimal("2")
    else:
        assert db.query(SalesDeliveryItem).count() == 0


def test_sm_cd_15__over_capacity_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-15 — requesting more than the remaining plannable capacity raises ValueError; nothing new written.
    Rules: R7."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    LA.quantity_delivered = Decimal("3.00")
    LA.quantity_refunded = Decimal("1.00")
    db.flush()
    d0 = mk_delivery(db, order, number="DEL-2026-001")
    mk_delivery_line(db, d0, LA, Decimal("2.00"))
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("5")}], w1.id, u1.id
        )
    assert str(exc.value) == (
        f"Cannot plan 5 unit(s) for sales order item {LA.id} — only 4.00 unit(s) are available to plan "
        "(2.00 already committed to other planned deliveries). "
        "Edit or delete an existing planned delivery to free up capacity."
    )
    assert db.query(SalesDeliveryItem).filter(SalesDeliveryItem.delivery_id != d0.id).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


def test_sm_cd_16__at_capacity_boundary_accepted(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-16 — requesting exactly the remaining capacity is accepted.
    Rules: R7."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    LA.quantity_delivered = Decimal("3.00")
    LA.quantity_refunded = Decimal("1.00")
    db.flush()
    d0 = mk_delivery(db, order, number="DEL-2026-001")
    mk_delivery_line(db, d0, LA, Decimal("2.00"))
    db.expire_all()
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("4")}], w1.id, u1.id
    )
    lines = delivery_lines_for(db, deliv)
    assert len(lines) == 1
    assert lines[0].quantity_delivered == Decimal("4")


def test_sm_cd_17__only_planned_deliveries_count(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-17 — only 'planned' deliveries reduce available capacity; delivered/cancelled/other statuses don't.
    Rules: R7."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    d_delivered = mk_delivery(db, order, number="DEL-2026-001", status="delivered")
    mk_delivery_line(db, d_delivered, LA, Decimal("2.00"))
    d_cancelled = mk_delivery(db, order, number="DEL-2026-002", status="cancelled")
    mk_delivery_line(db, d_cancelled, LA, Decimal("3.00"))
    d_shipped = mk_delivery(db, order, number="DEL-2026-003", status="shipped")
    mk_delivery_line(db, d_shipped, LA, Decimal("1.00"))
    db.expire_all()
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("10")}], w1.id, u1.id
    )
    lines = delivery_lines_for(db, deliv)
    assert len(lines) == 1
    assert lines[0].quantity_delivered == Decimal("10")


def test_sm_cd_18__capacity_floors_at_zero(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-18 — an over-delivered line floors available capacity at 0, rendered as a bare 0.
    Rules: R7."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    LB.quantity_delivered = Decimal("6.00")
    db.flush()
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LB.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == (
        f"Cannot plan 1 unit(s) for sales order item {LB.id} — only 0 unit(s) are available to plan "
        "(0 already committed to other planned deliveries). "
        "Edit or delete an existing planned delivery to free up capacity."
    )
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_cd_19__locks_order_items_before_insert(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-19 — creating a delivery should lock sales_order_items before inserting delivery lines.
    Rules: R7a."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert isinstance(result, tuple)
    assert_lock_before_write(cap.statements, "sales_order_items", "sales_delivery_items")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-724"))
def test_sm_cd_20__duplicate_line_over_capacity_bypasses_check(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-20 — listing the same order line twice, over its ordered capacity, should be rejected.
    Rules: R8."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("6")},
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("6")},
            ], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order item {LA.id} appears more than once in this delivery"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-724"))
def test_sm_cd_21__duplicate_line_within_capacity_still_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-21 — the same order line listed twice is rejected even when the combined quantity fits.
    Rules: R8."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("2")},
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("3")},
            ], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order item {LA.id} appears more than once in this delivery"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-722"))
def test_sm_cd_22__status_override_ignored(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-22 — a caller-supplied delivery_status should be ignored; the delivery is always created 'planned'.
    Rules: R4."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    delivery_data = default_delivery_data(order, dm1, delivery_status="delivered")
    deliv, _ = M.create_delivery_with_items(
        db, delivery_data, [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
    )
    assert reread(db, SalesDelivery, deliv.id).delivery_status == "planned"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-722"))
def test_sm_cd_23__status_override_blocked_and_capacity_recomputed(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-23 — the status override should be blocked, and a later capacity check should see it as 'planned'.
    Rules: R4."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    delivery_data = default_delivery_data(order, dm1, delivery_status="draft")
    deliv1, _ = M.create_delivery_with_items(
        db, delivery_data, [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("8")}], w1.id, u1.id
    )
    assert reread(db, SalesDelivery, deliv1.id).delivery_status == "planned"
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("8")}], w1.id, u1.id
        )
    assert str(exc.value) == (
        f"Cannot plan 8 unit(s) for sales order item {LA.id} — only 2.00 unit(s) are "
        "available to plan (8.00 already committed to other planned deliveries). "
        "Edit or delete an existing planned delivery to free up capacity."
    )


def test_sm_cd_24__next_delivery_number(db, M, w1, w2, so, i1, i_s, dm1, u1, Y):
    """SM-CD-24 — the next delivery number follows this workspace's existing sequence for the year only.
    Rules: R4."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    bulk_insert_del_numbers(db, w1, order, [f"DEL-{Y}-001", f"DEL-{Y}-002"], status="cancelled")
    bulk_insert_del_numbers(db, w1, order, [f"DEL-{Y - 1}-001"])
    acct2 = mk_account(db, w2, "W2 Acct")
    fac2 = mk_factory(db, w2, "W2 Factory")
    so2 = so(workspace_id=w2.id, account_id=acct2.id, factory_id=fac2.id, sales_order_number="SO-2026-900")
    bulk_insert_del_numbers(db, w2, so2, [f"DEL-{Y}-101", f"DEL-{Y}-102", f"DEL-{Y}-103"])
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
    )
    assert reread(db, SalesDelivery, deliv.id).delivery_number == f"DEL-{Y}-003"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-726"))
def test_sm_cd_25__number_collides_across_workspaces(db, M, w1, w2, so, i1, i_s, dm1, u1, Y):
    """SM-CD-25 — delivery numbers should be independent per workspace but collide today on a global unique index.
    Rules: R4."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    acct2 = mk_account(db, w2, "W2 Acct")
    fac2 = mk_factory(db, w2, "W2 Factory")
    so2 = so(workspace_id=w2.id, account_id=acct2.id, factory_id=fac2.id, sales_order_number="SO-2026-900")
    bulk_insert_del_numbers(db, w2, so2, [f"DEL-{Y}-001"])
    with db.begin_nested():
        deliv, _ = M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
        assert reread(db, SalesDelivery, deliv.id).delivery_number == f"DEL-{Y}-001"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-725"))
def test_sm_cd_26__fractional_catalog_quantity_rejected(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-26 — a fractional quantity for a catalog (stock) line should be rejected; nothing written.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("2.5")}], w1.id, u1.id
        )
    assert not isinstance(exc.value, HTTPException)
    assert str(exc.value) == "Delivery line has a fractional quantity; stock requires whole units"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


def test_sm_cd_27__whole_catalog_quantity_accepted(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-27 — a whole catalog quantity is accepted.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("3.00")}], w1.id, u1.id
    )
    assert delivery_lines_for(db, deliv)[0].quantity_delivered == Decimal("3")


def test_sm_cd_28__fractional_free_text_accepted(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-28 — a fractional quantity is fine for a free-text line.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LB.id, "quantity_delivered": Decimal("2.5")}], w1.id, u1.id
    )
    assert delivery_lines_for(db, deliv)[0].quantity_delivered == Decimal("2.5")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-730"))
def test_sm_cd_29__foreign_delivery_method_rejected(db, M, w1, so, i1, i_s, dm_x, u1):
    """SM-CD-29 — a delivery method from another workspace should be rejected; nothing written.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm_x),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == f"Delivery method {dm_x.id} not found"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-730"))
def test_sm_cd_30__deleted_delivery_method_rejected(db, M, w1, so, i1, i_s, dm_d, u1):
    """SM-CD-30 — a soft-deleted delivery method should be rejected; nothing written.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm_d),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
        )
    assert str(exc.value) == f"Delivery method {dm_d.id} not found"
    assert deliveries_for(db, order) == []


def test_sm_cd_31__alternate_delivery_method_accepted(db, M, w1, so, i1, i_s, dm2, u1):
    """SM-CD-31 — a different live W1 delivery method is accepted.
    Rules: R13."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm2),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w1.id, u1.id
    )
    assert reread(db, SalesDelivery, deliv.id).delivery_method_id == dm2.id


def test_sm_cd_32__delivery_item_input_schema_range_accepted(db):
    """SM-CD-32 — the schema accepts the extremes of its declared range today.
    Rules: R13."""
    lo = SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("0.01"))
    assert lo.quantity_delivered == Decimal("0.01")
    hi = SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("9999999999999.99"))
    assert hi.quantity_delivered == Decimal("9999999999999.99")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-delivery"))
def test_sm_cd_33__zero_quantity_rejected(db):
    """SM-CD-33 — a zero delivery quantity should be rejected by the schema.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("0"))
    assert "quantity_delivered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-delivery"))
def test_sm_cd_34__negative_quantity_rejected(db):
    """SM-CD-34 — a negative delivery quantity should be rejected by the schema.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("-3"))
    assert "quantity_delivered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-delivery"))
def test_sm_cd_35__over_precision_quantity_rejected(db):
    """SM-CD-35 — a delivery quantity with more than 2 decimal places should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("1.005"))
    assert "quantity_delivered" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-delivery"))
def test_sm_cd_36__oversized_quantity_rejected(db):
    """SM-CD-36 — a 14-digit delivery quantity should be rejected.
    Rules: R13."""
    with pytest.raises(ValidationError) as exc:
        SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("10000000000000"))
    assert "quantity_delivered" in str(exc.value)


def test_sm_cd_37__other_lines_planned_qty_does_not_reduce_this_line(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-37 — another line's planned quantity does not reduce this line's available capacity.
    Rules: R7."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    d0 = mk_delivery(db, order, number="DEL-2026-001")
    mk_delivery_line(db, d0, LB, Decimal("4.00"))
    db.expire_all()
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("10")}], w1.id, u1.id
    )
    assert delivery_lines_for(db, deliv)[0].quantity_delivered == Decimal("10")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-722"))
def test_sm_cd_38__schema_ignores_delivery_status(db):
    """SM-CD-38 — delivery_status should not be a field on SalesDeliveryCreate at all.
    Rules: R4."""
    obj = SalesDeliveryCreate(sales_order_id=1, delivery_method_id=1, delivery_status="cancelled")
    assert "delivery_status" not in obj.model_dump()


def test_sm_cd_39__plural_two_items(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-39 — two units across two items is plural for both.
    Rules: R11."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [
            {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")},
            {"sales_order_item_id": LB.id, "quantity_delivered": Decimal("1")},
        ], w1.id, u1.id
    )
    evs = events_for(db, order)
    assert evs[0].description.endswith("(2 units across 2 items)")


def test_sm_cd_40__free_text_line_fields(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-40 — a free-text line's delivery item has null item_id and null notes when not given.
    Rules: R9."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    deliv, _ = M.create_delivery_with_items(
        db, default_delivery_data(order, dm1),
        [{"sales_order_item_id": LB.id, "quantity_delivered": Decimal("1"), "notes": None}], w1.id, u1.id
    )
    line = delivery_lines_for(db, deliv)[0]
    assert line.item_id is None
    assert line.notes is None
    assert line.sales_order_item_id == LB.id
    assert line.workspace_id == w1.id


def test_sm_cd_41__other_workspace_cannot_see_order(db, M, w1, w2, so, i1, i_s, dm1, u5):
    """SM-CD-41 — calling from another workspace with another workspace's user cannot find SO1.
    Rules: R2."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")}], w2.id, u5.id
        )
    assert str(exc.value) == f"Sales order {order.id} not found"
    assert_nw(db, before)


def test_sm_cd_43__second_line_capacity_error_no_event(db, M, w1, so, i1, i_s, dm1, u1, p1):
    """SM-CD-43 — a later line that blows past capacity raises ValueError; no delivery_planned event is logged.
    Rules: R10."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValueError):
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")},
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("100")},
            ], w1.id, u1.id
        )
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-delivery"))
def test_sm_cd_44__zero_quantity_line_validated_before_any_write(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-44 — a zero-quantity second line should be rejected and nothing written at all.
    Rules: R13, R10a."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValidationError):
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")},
                {"sales_order_item_id": LB.id, "quantity_delivered": Decimal("0")},
            ], w1.id, u1.id
        )
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-021-delivery"))
def test_sm_cd_45__over_precision_line_validated_before_any_write(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-45 — an over-precision free-text quantity should be rejected and nothing written at all.
    Rules: R13, R10a."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    with pytest.raises(ValidationError):
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [{"sales_order_item_id": LB.id, "quantity_delivered": Decimal("1.005")}], w1.id, u1.id
        )
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


@pytest.mark.xfail(strict=True, reason=xfail("BUG-723"))
def test_sm_cd_46__foreign_line_validated_before_any_write(db, M, w1, so, i1, i_s, dm1, u1):
    """SM-CD-46 — a line from another order should be rejected before any delivery row is written.
    Rules: R5, R10a."""
    order, LA, LB, LB2, LS = cd_setup(db, so, i1, i_s)
    so2 = so(sales_order_number="SO-2026-012", invoice_confirmed=True)
    l2 = mk_line(db, so2, item=i1, ordered=Decimal("10.00"))
    with pytest.raises(ValueError) as exc:
        M.create_delivery_with_items(
            db, default_delivery_data(order, dm1),
            [
                {"sales_order_item_id": LA.id, "quantity_delivered": Decimal("1")},
                {"sales_order_item_id": l2.id, "quantity_delivered": Decimal("1")},
            ], w1.id, u1.id
        )
    assert str(exc.value) == f"Sales order item {l2.id} does not belong to sales order {order.id}"
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert not any(e.event_type == "delivery_planned" for e in events_for(db, order))


# =========================================================================== #
# SalesManager.complete_delivery
# =========================================================================== #

def cpd_setup(db, so, i1, u1, **order_overrides):
    """SO1 (invoice_confirmed True) with LA, LB; D1 planned with DL(LA,4.00), DL(LB,2.00)."""
    order_overrides.setdefault("invoice_confirmed", True)
    order = so(**order_overrides)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    LB = mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    mk_delivery_line(db, d1, LB, Decimal("2.00"))
    return order, LA, LB, d1


def default_complete(db, M, w1, d1, u1, **overrides):
    kwargs = {"actual_delivery_date": date(2026, 9, 29), "completion_code": "OK-77"}
    kwargs.update(overrides)
    return M.complete_delivery(db, d1.id, w1.id, u1.id, **kwargs)


def test_sm_cpd_01__completes_delivery_and_lines(db, M, w1, so, i1, p1, u1):
    """SM-CPD-01 -- completing a delivery updates its status and the order lines' delivered quantities.
    Rules: R3, R4."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    result = default_complete(db, M, w1, d1, u1)
    assert result.id == order.id
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.delivery_status == "delivered"
    assert d1r.actual_delivery_date == date(2026, 9, 29)
    assert d1r.completion_code == "OK-77"
    assert reread(db, SalesOrderItem, LA.id).quantity_delivered == Decimal("4.00")
    assert reread(db, SalesOrderItem, LB.id).quantity_delivered == Decimal("2.00")


def test_sm_cpd_02__deducts_stock_and_writes_ledger(db, M, w1, so, i1, p1, u1, a1):
    """SM-CPD-02 -- completing deducts sellable stock and writes one ledger row for the catalog line only.
    Rules: R5, R6."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    p1r = reread(db, Product, p1.id)
    assert p1r.qty == 16
    assert p1r.updated_by == u1.id
    rows = ledger_rows(db)
    assert len(rows) == 1
    r = rows[0]
    assert r.transaction_type == "sale"
    assert r.quantity == 4
    assert r.qty_before == 20
    assert r.qty_after == 16
    assert r.unit_cost == Decimal("4.00")
    assert r.total_cost == Decimal("16.00")
    assert r.avg_cost_before == Decimal("4.00")
    assert r.avg_cost_after == Decimal("4.00")
    assert r.source_type == "sales_delivery"
    assert r.source_id == d1.id
    assert r.transfer_destination_type == "customer"
    assert r.transfer_destination_id == a1.id
    assert r.performed_by == u1.id
    assert r.notes.startswith("Delivery DEL-2026-004 for ")
    assert r.notes.endswith("SO-2026-010")


@pytest.mark.xfail(strict=True, reason=xfail("BUG-735"))
def test_sm_cpd_03__ledger_notes_exact(db, M, w1, so, i1, p1, u1):
    """SM-CPD-03 -- ledger notes should read the plain order number, not doubled with 'SO-'.
    Rules: R5."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert ledger_rows(db)[0].notes == "Delivery DEL-2026-004 for SO-2026-010"


def test_sm_cpd_04__null_avg_cost(db, M, w1, f1, i1, so, u1):
    """SM-CPD-04 -- a null average cost leaves unit_cost/total_cost null on the ledger row.
    Rules: R5."""
    p = mk_product(db, w1, f1, i1, qty=20, avg_cost=None)
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    rows = ledger_rows(db)
    assert rows[0].unit_cost is None
    assert rows[0].total_cost is None
    assert reread(db, Product, p.id).qty == 16


def test_sm_cpd_05__logs_delivery_completed_event(db, M, w1, so, i1, p1, u1):
    """SM-CPD-05 -- completing logs one delivery_completed event with date and code in the description.
    Rules: R9."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "delivery_completed"
    assert ev.description == "Delivery DEL-2026-004 marked delivered on 2026-09-29 (code: OK-77)"
    assert ev.metadata_json == {"delivery_id": d1.id, "actual_delivery_date": "2026-09-29", "completion_code": "OK-77"}
    assert ev.performed_by == u1.id


def test_sm_cpd_06__defaults_date_and_null_code(db, M, w1, so, i1, p1, u1):
    """SM-CPD-06 -- a null date defaults to today; a null code omits the '(code:' suffix.
    Rules: R3, R9."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    today = date.today()
    default_complete(db, M, w1, d1, u1, actual_delivery_date=None, completion_code=None)
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.actual_delivery_date == today
    assert d1r.completion_code is None
    ev = events_for(db, order)[0]
    assert ev.description == f"Delivery DEL-2026-004 marked delivered on {today.isoformat()}"
    assert "(code:" not in ev.description
    assert ev.metadata_json["completion_code"] is None
    assert ev.metadata_json["actual_delivery_date"] == today.isoformat()


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_cpd_07__blank_code_should_be_null(db, M, w1, so, i1, p1, u1):
    """SM-CPD-07 -- a whitespace-only completion code should be treated as absent.
    Rules: R3, R9."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1, completion_code="   ")
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.completion_code is None
    ev = events_for(db, order)[0]
    assert "(code:" not in ev.description
    assert ev.metadata_json["completion_code"] is None


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_cpd_08__empty_code_should_be_null(db, M, w1, so, i1, p1, u1):
    """SM-CPD-08 -- an empty-string completion code should be treated as absent.
    Rules: R3."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1, completion_code="")
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.completion_code is None
    ev = events_for(db, order)[0]
    assert "(code:" not in ev.description


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_cpd_09__code_should_be_trimmed(db, M, w1, so, i1, p1, u1):
    """SM-CPD-09 -- a completion code with surrounding whitespace should be trimmed before storing.
    Rules: R3, R9."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1, completion_code="  OK-77  ")
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.completion_code == "OK-77"
    ev = events_for(db, order)[0]
    assert ev.description.endswith("(code: OK-77)")
    assert ev.metadata_json["completion_code"] == "OK-77"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_cpd_10__none_should_clear_existing_code(db, M, w1, so, i1, p1, u1):
    """SM-CPD-10 -- passing no code should clear a previously-set completion code.
    Rules: R3."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    d1.completion_code = "OLD"
    db.flush()
    db.expire_all()
    default_complete(db, M, w1, d1, u1, completion_code=None)
    assert reread(db, SalesDelivery, d1.id).completion_code is None


@pytest.mark.xfail(strict=True, reason=xfail("BUG-733"))
def test_sm_cpd_11__updated_by_not_stamped(db, M, w1, so, i1, p1, u1):
    """SM-CPD-11 -- completing a delivery should stamp who did it.
    Rules: R3."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    d1.updated_by = None
    db.flush()
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesDelivery, d1.id).updated_by == u1.id


def test_sm_cpd_12__recomputes_fully_delivered_true(db, M, w1, so, i1, p1, u1):
    """SM-CPD-12 -- completing the last units flips is_fully_delivered to True.
    Rules: R8."""
    order = so(invoice_confirmed=True, is_fully_delivered=False)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("6.00"))
    LB = mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"), delivered=Decimal("3.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    mk_delivery_line(db, d1, LB, Decimal("2.00"))
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


def test_sm_cpd_13__recomputes_fully_delivered_false(db, M, w1, so, i1, p1, u1):
    """SM-CPD-13 -- completing a delivery that doesn't finish every line leaves is_fully_delivered False.
    Rules: R8."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesOrder, order.id).is_fully_delivered is False


def test_sm_cpd_14__unknown_delivery(db, M, w1, so, i1, p1, u1):
    """SM-CPD-14 -- an unknown delivery id raises ValueError; nothing changes.
    Rules: R1."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.complete_delivery(db, missing_id(db, SalesDelivery), w1.id, u1.id)
    assert str(exc.value) == "Delivery not found"
    assert_nw(db, before)


def test_sm_cpd_15__wrong_workspace_not_found(db, M, w1, w2, so, i1, p1, u1):
    """SM-CPD-15 -- a delivery in another workspace is invisible; nothing changes.
    Rules: R1."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    d1.workspace_id = w2.id
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.complete_delivery(db, d1.id, w1.id, u1.id)
    assert str(exc.value) == "Delivery not found"
    assert_nw(db, before)
    assert reread(db, SalesDelivery, d1.id).delivery_status == "planned"
    assert reread(db, Product, p1.id).qty == 20


@pytest.mark.xfail(strict=True, reason=xfail("BUG-721"))
def test_sm_cpd_16__already_delivered_rejected(db, M, w1, so, i1, p1, u1):
    """SM-CPD-16 -- completing an already-delivered delivery should be rejected, not re-applied.
    Rules: R2."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    d1.delivery_status = "delivered"
    db.flush()
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        default_complete(db, M, w1, d1, u1)
    assert str(exc.value) == "Only planned deliveries can be completed (this delivery is 'delivered')"
    assert reread(db, SalesOrderItem, LA.id).quantity_delivered == Decimal("0.00")
    assert reread(db, SalesOrderItem, LB.id).quantity_delivered == Decimal("0.00")
    assert reread(db, Product, p1.id).qty == 20
    assert ledger_rows(db) == []
    assert events_for(db, order) == []


@pytest.mark.xfail(strict=True, reason=xfail("BUG-721"))
def test_sm_cpd_17__cancelled_rejected(db, M, w1, so, i1, p1, u1):
    """SM-CPD-17 -- completing a cancelled delivery should be rejected, not re-applied.
    Rules: R2."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    d1.delivery_status = "cancelled"
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        default_complete(db, M, w1, d1, u1)
    assert str(exc.value) == "Only planned deliveries can be completed (this delivery is 'cancelled')"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_cpd_18__locks_deliveries_before_update(db, M, w1, so, i1, p1, u1):
    """SM-CPD-18 -- completing a delivery should lock sales_deliveries before updating order items.
    Rules: R2a."""
    order, LA, LB, d1 = cpd_setup(db, so, i1, u1)
    db.expire_all()
    cap = SQLCapture(db.get_bind())
    with cap:
        result = default_complete(db, M, w1, d1, u1)
    assert result.id == order.id
    assert_lock_before_write(cap.statements, "sales_deliveries", "sales_order_items", write_verb="update")


def test_sm_cpd_19__no_cap_on_delivered_total(db, M, w1, so, i1, p1, u1):
    """SM-CPD-19 -- completing adds to delivered with no ceiling at ordered.
    Rules: R4."""
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("9.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesOrderItem, LA.id).quantity_delivered == Decimal("13.00")


def test_sm_cpd_20__zero_quantity_rejected(db, M, w1, so, i1, p1, u1):
    """SM-CPD-20 -- a zero-quantity delivery line is rejected by the stock deduction.
    Rules: R7."""
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("0.00"))
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        default_complete(db, M, w1, d1, u1)
    assert str(exc.value) == "Sale deduction quantity must be positive"
    assert reread(db, Product, p1.id).qty == 20
    assert ledger_rows(db) == []


def test_sm_cpd_21__fractional_quantity_rejected(db, M, w1, so, i1, p1, u1):
    """SM-CPD-21 -- a fractional delivered quantity on a catalog line is rejected before any stock change.
    Rules: R7."""
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("2.50"))
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        default_complete(db, M, w1, d1, u1)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"
    assert reread(db, Product, p1.id).qty == 20
    assert ledger_rows(db) == []


def test_sm_cpd_22__no_product_row_422(db, M, w1, f1, so, i1, u1):
    """SM-CPD-22 -- no sellable product row for the item/factory 422s; the delivery is already flushed delivered.
    Rules: R7."""
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        default_complete(db, M, w1, d1, u1)
    assert exc.value.status_code == 422
    assert exc.value.detail == f"Insufficient sellable stock for item {i1.id} at factory {f1.id}: requested 4, available 0"
    assert ledger_rows(db) == []
    assert reread(db, SalesDelivery, d1.id).delivery_status == "delivered"


def test_sm_cpd_23__insufficient_stock_422(db, M, w1, f1, so, i1, u1):
    """SM-CPD-23 -- insufficient stock 422s with the requested/available numbers; stock unchanged.
    Rules: R7."""
    p = mk_product(db, w1, f1, i1, qty=3)
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        default_complete(db, M, w1, d1, u1)
    assert exc.value.status_code == 422
    assert exc.value.detail == f"Insufficient sellable stock for item {i1.id} at factory {f1.id}: requested 4, available 3"
    assert reread(db, Product, p.id).qty == 3
    assert ledger_rows(db) == []


def test_sm_cpd_24__exact_stock_boundary(db, M, w1, f1, so, i1, u1):
    """SM-CPD-24 -- stock exactly equal to the requested quantity succeeds and floors at 0.
    Rules: R7."""
    p = mk_product(db, w1, f1, i1, qty=4)
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, Product, p.id).qty == 0
    assert ledger_rows(db)[0].qty_after == 0


def test_sm_cpd_25__non_sellable_product_ignored(db, M, w1, f1, f2, so, i1, u1):
    """SM-CPD-25 -- a non-sellable product at the same factory doesn't satisfy the sellable-stock check.
    Rules: R5, R7."""
    p_ns = mk_product(db, w1, f1, i1, qty=20, available=False)
    p_other = mk_product(db, w1, f2, i1, qty=20, available=True)
    order = so(invoice_confirmed=True)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    db.expire_all()
    with pytest.raises(HTTPException) as exc:
        default_complete(db, M, w1, d1, u1)
    assert exc.value.status_code == 422
    assert exc.value.detail == f"Insufficient sellable stock for item {i1.id} at factory {f1.id}: requested 4, available 0"
    assert reread(db, Product, p_ns.id).qty == 20
    assert reread(db, Product, p_other.id).qty == 20
    assert ledger_rows(db) == []


def test_sm_cpd_26__no_lines(db, M, w1, so, i1, p1, u1):
    """SM-CPD-26 -- a delivery with no lines still completes, with no stock movement.
    Rules: R10."""
    order = so(invoice_confirmed=True)
    mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"))
    d1 = mk_delivery(db, order)
    db.expire_all()
    result = default_complete(db, M, w1, d1, u1)
    assert result.id == order.id
    assert reread(db, SalesDelivery, d1.id).delivery_status == "delivered"
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_completed"
    assert ledger_rows(db) == []
    assert reread(db, SalesOrder, order.id).is_fully_delivered is False


def test_sm_cpd_27__no_invoice_check(db, M, w1, so, i1, p1, u1):
    """SM-CPD-27 -- completing a delivery does not require the invoice to be finalized.
    Rules: R11."""
    order = so(invoice_confirmed=False)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    LB = mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LA, Decimal("4.00"))
    mk_delivery_line(db, d1, LB, Decimal("2.00"))
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesDelivery, d1.id).delivery_status == "delivered"
    assert reread(db, Product, p1.id).qty == 16


def test_sm_cpd_28__free_text_line_no_stock(db, M, w1, so, i1, p1, u1):
    """SM-CPD-28 -- a free-text line's delivery updates quantity_delivered but moves no stock.
    Rules: R6."""
    order = so(invoice_confirmed=True)
    LB = mk_line(db, order, description="Custom crate", ordered=Decimal("5.00"))
    d1 = mk_delivery(db, order)
    mk_delivery_line(db, d1, LB, Decimal("2.00"))
    db.expire_all()
    default_complete(db, M, w1, d1, u1)
    assert reread(db, SalesOrderItem, LB.id).quantity_delivered == Decimal("2.00")
    p1r = reread(db, Product, p1.id)
    assert p1r.qty == 20
    assert p1r.updated_by is None
    assert ledger_rows(db) == []


# =========================================================================== #
# SalesManager.cancel_delivery
# =========================================================================== #

def can_setup(db, so, i1, dm1, **order_overrides):
    """SO1 with LA (ordered 10.00); D1 planned with DL(LA, 6.00)."""
    order = so(**order_overrides)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order, method=dm1)
    mk_delivery_line(db, d1, LA, Decimal("6.00"))
    return order, LA, d1


def test_sm_can_01__cancels_and_logs_event(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-01 -- cancelling a planned delivery flips status to cancelled and logs an event; nothing else moves.
    Rules: R3, R4."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    db.expire_all()
    result = M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert result.id == d1.id
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.delivery_status == "cancelled"
    assert d1r.tracking_number == "TRK-100"
    assert d1r.notes == "Gate 3"
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    assert reread(db, SalesOrderItem, LA.id).quantity_delivered == Decimal("0.00")
    assert reread(db, Product, p1.id).qty == 20
    assert ledger_rows(db) == []
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_cancelled"
    assert evs[0].description == "Delivery DEL-2026-004 cancelled"
    assert evs[0].metadata_json == {"delivery_id": d1.id}
    assert evs[0].performed_by == u1.id


def test_sm_can_02__frees_capacity_for_new_delivery(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-02 -- cancelling a planned delivery frees its committed quantity for a new one.
    Rules: R3."""
    order, LA, d1 = can_setup(db, so, i1, dm1, invoice_confirmed=True)
    db.expire_all()
    M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    db.expire_all()
    deliv, _ = M.create_delivery_with_items(
        db,
        {"sales_order_id": order.id, "delivery_method_id": dm1.id, "scheduled_date": date(2026, 10, 5),
         "tracking_number": "TRK-200", "notes": "Gate 4"},
        [{"sales_order_item_id": LA.id, "quantity_delivered": Decimal("10")}], w1.id, u1.id,
    )
    assert deliv.id is not None


def test_sm_can_03__null_user_event(db, M, w1, so, i1, dm1, p1):
    """SM-CAN-03 -- a null user_id is allowed; the event records a null performer.
    Rules: R4."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    db.expire_all()
    M.cancel_delivery(db, d1.id, w1.id, user_id=None)
    assert events_for(db, order)[0].performed_by is None


def test_sm_can_04__unknown_delivery(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-04 -- an unknown delivery id raises ValueError; nothing changes.
    Rules: R1."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    before = nw_snapshot(db)
    db.expire_all()
    missing = missing_id(db, SalesDelivery)
    with pytest.raises(ValueError) as exc:
        M.cancel_delivery(db, missing, w1.id, user_id=u1.id)
    assert str(exc.value) == f"Delivery {missing} not found"
    assert_nw(db, before)


def test_sm_can_05__wrong_workspace(db, M, w1, w2, so, i1, dm1, p1, u1):
    """SM-CAN-05 -- a delivery in another workspace is invisible; nothing changes.
    Rules: R1."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    d1.workspace_id = w2.id
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert str(exc.value) == f"Delivery {d1.id} not found"
    assert_nw(db, before)


def test_sm_can_06__already_delivered_rejected(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-06 -- a delivered delivery cannot be cancelled.
    Rules: R2."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    d1.delivery_status = "delivered"
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert str(exc.value) == "Only planned deliveries can be cancelled (this delivery is 'delivered')"
    assert_nw(db, before)


def test_sm_can_07__already_cancelled_or_odd_status_rejected(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-07 -- an already-cancelled delivery, or any non-'planned' status, is rejected with that status named.
    Rules: R2."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    d1.delivery_status = "cancelled"
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert str(exc.value) == "Only planned deliveries can be cancelled (this delivery is 'cancelled')"
    assert_nw(db, before)

    order2 = so(sales_order_number="SO-2026-011")
    mk_line(db, order2, item=i1, ordered=Decimal("10.00"))
    d2 = mk_delivery(db, order2, method=dm1, number="DEL-2026-005", status="Planned")
    before2 = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc2:
        M.cancel_delivery(db, d2.id, w1.id, user_id=u1.id)
    assert str(exc2.value) == "Only planned deliveries can be cancelled (this delivery is 'Planned')"
    assert_nw(db, before2)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-733"))
def test_sm_can_08__updated_by_not_stamped(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-08 -- cancelling should stamp who did it.
    Rules: R3."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    db.expire_all()
    M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert reread(db, SalesDelivery, d1.id).updated_by == u1.id


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_can_09__locks_deliveries_before_update(db, M, w1, so, i1, dm1, p1, u1):
    """SM-CAN-09 -- cancelling should lock sales_deliveries before updating its own row.
    Rules: R2a."""
    order, LA, d1 = can_setup(db, so, i1, dm1)
    db.expire_all()
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.cancel_delivery(db, d1.id, w1.id, user_id=u1.id)
    assert result.id == d1.id
    assert_lock_before_write(cap.statements, "sales_deliveries", "sales_deliveries", write_verb="update")


# =========================================================================== #
# SalesManager.update_delivery
# =========================================================================== #

def ud_setup(db, so, i1, dm1, u2, **order_overrides):
    """D1 planned: scheduled 2026-10-05, DM1, tracking TRK-100, notes Gate 3, updated_by U2."""
    order = so(**order_overrides)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    d1 = mk_delivery(db, order, method=dm1, updated_by=u2)
    return order, LA, d1


def test_sm_ud_01__updates_all_fields_and_logs(db, M, w1, so, i1, dm1, dm2, u1, u2):
    """SM-UD-01 -- editing several fields updates them and logs one event naming them in schema order.
    Rules: R3, R4."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(
        scheduled_date=date(2026, 10, 7), delivery_method_id=dm2.id,
        tracking_number="TRK-200", notes="Gate 5",
    )
    result = M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert result.id == d1.id
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.scheduled_date == date(2026, 10, 7)
    assert d1r.delivery_method_id == dm2.id
    assert d1r.tracking_number == "TRK-200"
    assert d1r.notes == "Gate 5"
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_updated"
    assert evs[0].description == "Delivery DEL-2026-004 updated (scheduled date, delivery method, tracking number, notes)"
    assert evs[0].metadata_json == {"delivery_id": d1.id}
    assert evs[0].performed_by == u1.id


def test_sm_ud_02__unchanged_field_not_in_label(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-02 -- a field sent with its current value isn't treated as changed in the event label.
    Rules: R4."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(tracking_number="TRK-100", notes="Gate 9")
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert events_for(db, order)[0].description == "Delivery DEL-2026-004 updated (notes)"
    assert reread(db, SalesDelivery, d1.id).tracking_number == "TRK-100"


def test_sm_ud_03__label_order_is_fixed_not_input_order(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-03 -- the changed-field label order follows the schema's field order, not the call's kwarg order.
    Rules: R4."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(notes="Gate 9", scheduled_date=date(2026, 10, 8))
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert events_for(db, order)[0].description == "Delivery DEL-2026-004 updated (scheduled date, notes)"


def test_sm_ud_04__no_op_when_all_values_unchanged(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-04 -- sending every field with its current value is a no-op: no event, no re-stamp.
    Rules: R5."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(
        scheduled_date=date(2026, 10, 5), delivery_method_id=dm1.id,
        tracking_number="TRK-100", notes="Gate 3",
    )
    result = M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert result.id == d1.id
    assert events_for(db, order) == []
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    assert d1r.tracking_number == "TRK-100"
    assert d1r.notes == "Gate 3"
    assert d1r.updated_by == u2.id


def test_sm_ud_05__single_field_update(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-05 -- a single changed field updates only that field and logs its own label.
    Rules: R3."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(tracking_number="TRK-300")
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.tracking_number == "TRK-300"
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    assert d1r.notes == "Gate 3"
    assert events_for(db, order)[0].description == "Delivery DEL-2026-004 updated (tracking number)"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-732"))
def test_sm_ud_06__clearing_tracking_number(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-06 -- explicitly clearing tracking_number with None should null it and log the change.
    Rules: R3, R4."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(tracking_number=None)
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert reread(db, SalesDelivery, d1.id).tracking_number is None
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].description == "Delivery DEL-2026-004 updated (tracking number)"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-732"))
def test_sm_ud_07__clearing_two_fields(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-07 -- clearing scheduled_date and notes with None should null both and log the change.
    Rules: R3."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(scheduled_date=None, notes=None)
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.scheduled_date is None
    assert d1r.notes is None
    assert d1r.tracking_number == "TRK-100"
    assert d1r.delivery_method_id == dm1.id
    assert events_for(db, order)[0].description == "Delivery DEL-2026-004 updated (scheduled date, notes)"


@pytest.mark.xfail(strict=True, reason=xfail("BUG-732"))
def test_sm_ud_08__method_cannot_be_cleared_schema():
    """SM-UD-08 -- delivery_method_id should not be nullable on the edit schema (it's always required).
    Rules: R3."""
    with pytest.raises(ValidationError):
        SalesDeliveryEditRequest(delivery_method_id=None)


def test_sm_ud_09__schema_builds():
    """SM-UD-09 -- the edit schema accepts no fields, an explicit None, and a normal id.
    Rules: R3."""
    SalesDeliveryEditRequest()
    SalesDeliveryEditRequest(tracking_number=None)
    SalesDeliveryEditRequest(delivery_method_id=5)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-733"))
def test_sm_ud_10__updated_by_not_stamped(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-10 -- a real edit should stamp who made it.
    Rules: R3."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    data = SalesDeliveryEditRequest(tracking_number="TRK-300")
    M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert reread(db, SalesDelivery, d1.id).updated_by == u1.id


def test_sm_ud_11__arbitrary_field_with_no_label(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-11 -- update_delivery accepts any pydantic model; a field with no label still logs, with empty parens.
    Rules: R6."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()

    class _AdHocData(BaseModel):
        delivery_status: str = "planned"

    result = M.update_delivery(db, d1.id, w1.id, _AdHocData(delivery_status="cancelled"), user_id=u1.id)
    assert result.id == d1.id
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.delivery_status == "cancelled"
    assert d1r.tracking_number == "TRK-100"
    assert d1r.notes == "Gate 3"
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_updated"
    assert evs[0].description == "Delivery DEL-2026-004 updated ()"
    assert evs[0].metadata_json == {"delivery_id": d1.id}
    assert evs[0].performed_by == u1.id


def test_sm_ud_12__unknown_delivery(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-12 -- an unknown delivery id raises ValueError; nothing changes.
    Rules: R1."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    before = nw_snapshot(db)
    db.expire_all()
    missing = missing_id(db, SalesDelivery)
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, missing, w1.id, SalesDeliveryEditRequest(tracking_number="X"), user_id=u1.id)
    assert str(exc.value) == f"Delivery {missing} not found"
    assert_nw(db, before)


def test_sm_ud_13__wrong_workspace(db, M, w1, w2, so, i1, dm1, u1, u2):
    """SM-UD-13 -- a delivery in another workspace is invisible; nothing changes.
    Rules: R1."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    d1.workspace_id = w2.id
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(tracking_number="X"), user_id=u1.id)
    assert str(exc.value) == f"Delivery {d1.id} not found"
    assert_nw(db, before)


def test_sm_ud_14__delivered_rejected(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-14 -- a delivered delivery cannot be edited.
    Rules: R2."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    d1.delivery_status = "delivered"
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(tracking_number="X"), user_id=u1.id)
    assert str(exc.value) == "Only planned deliveries can be edited (this delivery is 'delivered')"
    assert_nw(db, before)


def test_sm_ud_15__cancelled_rejected(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-15 -- a cancelled delivery cannot be edited.
    Rules: R2."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    d1.delivery_status = "cancelled"
    db.flush()
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(notes="X"), user_id=u1.id)
    assert str(exc.value) == "Only planned deliveries can be edited (this delivery is 'cancelled')"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-730"))
def test_sm_ud_16__foreign_method_rejected(db, M, w1, so, i1, dm1, dm_x, u1, u2):
    """SM-UD-16 -- a delivery method from another workspace should be rejected.
    Rules: R7."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(delivery_method_id=dm_x.id), user_id=u1.id)
    assert str(exc.value) == f"Delivery method {dm_x.id} not found"
    assert_nw(db, before)
    assert reread(db, SalesDelivery, d1.id).delivery_method_id == dm1.id
    assert events_for(db, order) == []


@pytest.mark.xfail(strict=True, reason=xfail("BUG-730"))
def test_sm_ud_17__deleted_method_rejected(db, M, w1, so, i1, dm1, dm_d, u1, u2):
    """SM-UD-17 -- a soft-deleted delivery method should be rejected.
    Rules: R7."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    before = nw_snapshot(db)
    db.expire_all()
    with pytest.raises(ValueError) as exc:
        M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(delivery_method_id=dm_d.id), user_id=u1.id)
    assert str(exc.value) == f"Delivery method {dm_d.id} not found"
    assert_nw(db, before)


def test_sm_ud_18__null_user_event(db, M, w1, so, i1, dm1, u2):
    """SM-UD-18 -- a null user_id is allowed; the event records a null performer.
    Rules: R4."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(notes="Gate 9"), user_id=None)
    assert events_for(db, order)[0].performed_by is None


def test_sm_ud_19__no_op_does_not_restamp(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-19 -- a no-op edit must not stamp updated_by even after BUG-733 is fixed (paired with UD-10).
    Rules: R5."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    result = M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(tracking_number="TRK-100"), user_id=u1.id)
    assert result.id == d1.id
    assert reread(db, SalesDelivery, d1.id).updated_by == u2.id
    assert events_for(db, order) == []


def test_sm_ud_20__method_only_update(db, M, w1, so, i1, dm1, dm2, u1, u2):
    """SM-UD-20 -- changing only the delivery method updates it and logs its own label.
    Rules: R3."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()
    M.update_delivery(db, d1.id, w1.id, SalesDeliveryEditRequest(delivery_method_id=dm2.id), user_id=u1.id)
    assert reread(db, SalesDelivery, d1.id).delivery_method_id == dm2.id
    assert events_for(db, order)[0].description == "Delivery DEL-2026-004 updated (delivery method)"


def test_sm_ud_21__unset_field_not_sent_so_not_written(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-21 -- an unset field on the data model (with a non-None default) is not sent, so it is left unchanged.
    Rules: R3, R4, R6."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()

    class _AdHocData(BaseModel):
        delivery_status: str = "cancelled"
        notes: str | None = None

    data = _AdHocData(notes="Gate 9")
    result = M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert result.id == d1.id
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.notes == "Gate 9"
    assert d1r.delivery_status == "planned"
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    assert d1r.tracking_number == "TRK-100"
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "delivery_updated"
    assert evs[0].description == "Delivery DEL-2026-004 updated (notes)"
    assert evs[0].metadata_json == {"delivery_id": d1.id}
    assert evs[0].performed_by == u1.id


def test_sm_ud_22__unset_field_alone_is_not_a_change(db, M, w1, so, i1, dm1, u1, u2):
    """SM-UD-22 -- when the only sent field equals the stored value, an unset field with a differing default is not counted: no-op.
    Rules: R3, R5, R6."""
    order, LA, d1 = ud_setup(db, so, i1, dm1, u2)
    db.expire_all()

    class _AdHocData(BaseModel):
        delivery_status: str = "cancelled"
        notes: str | None = None

    data = _AdHocData(notes="Gate 3")
    result = M.update_delivery(db, d1.id, w1.id, data, user_id=u1.id)
    assert result.id == d1.id
    assert events_for(db, order) == []
    d1r = reread(db, SalesDelivery, d1.id)
    assert d1r.delivery_status == "planned"
    assert d1r.notes == "Gate 3"
    assert d1r.scheduled_date == date(2026, 10, 5)
    assert d1r.delivery_method_id == dm1.id
    assert d1r.tracking_number == "TRK-100"
    assert d1r.updated_by == u2.id


# =========================================================================== #
# SalesManager.fulfill_service_item
# =========================================================================== #

def fsi_setup(db, so, i1, i_s, i_u, **order_overrides):
    """SO1 (invoice_confirmed True) with LS (catalog IS), LT (free text), LU (catalog IU), LA (catalog I1).
    LS/LT/LU delivered 0.00/refunded 0.00, no delivery; LA requires delivery, untouched."""
    order_overrides.setdefault("invoice_confirmed", True)
    order = so(**order_overrides)
    LS = mk_line(db, order, item=i_s, requires_delivery=False, ordered=Decimal("5.00"))
    LT = mk_line(db, order, description="Site survey", requires_delivery=False, ordered=Decimal("2.00"))
    LU = mk_line(db, order, item=i_u, requires_delivery=False, ordered=Decimal("3.00"))
    LA = mk_line(db, order, item=i1, requires_delivery=True, ordered=Decimal("10.00"))
    return order, LS, LT, LU, LA


def test_sm_fsi_01__happy_path_catalog_line(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-01 -- fulfilling a catalog line sets delivered to ordered, stores the trimmed code and logs an event.
    Rules: R4, R5, R9."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    result = M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code="C-1")
    assert result.id == order.id
    r = reread(db, SalesOrderItem, LS.id)
    assert r.quantity_delivered == Decimal("5.00")
    assert r.fulfillment_completion_code == "C-1"
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "item_fulfilled"
    assert ev.description == "Installation fulfilled (5.00 hour) (code: C-1)"
    assert ev.metadata_json == {"item_id": LS.id, "completion_code": "C-1"}
    assert ev.performed_by == u1.id
    assert deliveries_for(db, order) == []
    assert db.query(SalesDeliveryItem).count() == 0
    assert ledger_rows(db) == []


def test_sm_fsi_02__free_text_line_fallback_unit(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-02 -- a free-text line is labelled by its description; no code given leaves it null.
    Rules: R4, R5."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LT.id, w1.id, u1.id, completion_code=None)
    r = reread(db, SalesOrderItem, LT.id)
    assert r.quantity_delivered == Decimal("2.00")
    assert r.fulfillment_completion_code is None
    ev = events_for(db, order)[0]
    assert ev.description == "Site survey fulfilled (2.00 unit(s))"
    assert ev.metadata_json == {"item_id": LT.id, "completion_code": None}


def test_sm_fsi_03__empty_catalog_unit_falls_back(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-03 -- a catalog item with an empty unit string falls back to 'unit(s)'.
    Rules: R5."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LU.id, w1.id, u1.id, completion_code=None)
    ev = events_for(db, order)[0]
    assert ev.description == "Calibration fulfilled (3.00 unit(s))"


def test_sm_fsi_04__blank_item_name_falls_back_to_id_label(db, M, w1, so, i1, i_s, i_u, i_e, u1):
    """SM-FSI-04 -- a catalog item whose name is '' falls back to the 'Item #<id>' label.
    Rules: R5."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LE = mk_line(db, order, item=i_e, requires_delivery=False, ordered=Decimal("1.00"))
    db.expire_all()
    M.fulfill_service_item(db, LE.id, w1.id, u1.id, completion_code=None)
    ev = events_for(db, order)[0]
    assert ev.description == f"Item #{i_e.id} fulfilled (1.00 unit(s))"


def test_sm_fsi_05__already_fulfilled_is_noop(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-05 -- a line already delivered in full is a no-op; the given code is ignored.
    Rules: R6."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.quantity_delivered = Decimal("5.00")
    db.flush()
    db.expire_all()
    result = M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code="X")
    assert result.id == order.id
    r = reread(db, SalesOrderItem, LS.id)
    assert r.quantity_delivered == Decimal("5.00")
    assert r.fulfillment_completion_code is None
    assert events_for(db, order) == []


def test_sm_fsi_06__over_delivered_is_noop(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-06 -- a line already over-delivered is also a no-op.
    Rules: R6."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.quantity_delivered = Decimal("6.00")
    db.flush()
    db.expire_all()
    result = M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code=None)
    assert result.id == order.id
    r = reread(db, SalesOrderItem, LS.id)
    assert r.quantity_delivered == Decimal("6.00")
    assert events_for(db, order) == []


def test_sm_fsi_07__partially_delivered_tops_up(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-07 -- a partially-delivered line is topped up to the ordered quantity.
    Rules: R4."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.quantity_delivered = Decimal("2.00")
    db.flush()
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code=None)
    assert reread(db, SalesOrderItem, LS.id).quantity_delivered == Decimal("5.00")
    assert len(events_for(db, order)) == 1


@pytest.mark.xfail(strict=True, reason=xfail("BUG-731"))
def test_sm_fsi_08__refunded_already_satisfies_should_be_noop(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-08 -- delivered + refunded already meeting ordered should be a no-op (refunded ignored today).
    Rules: R6."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.quantity_delivered = Decimal("3.00")
    LS.quantity_refunded = Decimal("2.00")
    db.flush()
    db.expire_all()
    result = M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code=None)
    assert result.id == order.id
    assert reread(db, SalesOrderItem, LS.id).quantity_delivered == Decimal("3.00")
    assert events_for(db, order) == []


@pytest.mark.xfail(strict=True, reason=xfail("BUG-731"))
def test_sm_fsi_09__refunded_should_reduce_target(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-09 -- the new delivered quantity should be ordered minus refunded, not plain ordered.
    Rules: R4."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.quantity_delivered = Decimal("1.00")
    LS.quantity_refunded = Decimal("2.00")
    db.flush()
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code=None)
    assert reread(db, SalesOrderItem, LS.id).quantity_delivered == Decimal("3.00")
    assert len(events_for(db, order)) == 1


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_fsi_11__whitespace_code_should_be_null(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-11 -- a whitespace-only code should be trimmed to null, dropping the '(code:' suffix.
    Rules: R4, R5."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code="   ")
    assert reread(db, SalesOrderItem, LS.id).fulfillment_completion_code is None
    ev = events_for(db, order)[0]
    assert ev.description == "Installation fulfilled (5.00 hour)"
    assert ev.metadata_json == {"item_id": LS.id, "completion_code": None}


@pytest.mark.xfail(strict=True, reason=xfail("BUG-734"))
def test_sm_fsi_12__code_should_be_trimmed(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-12 -- a padded code should be trimmed before storage, description and metadata.
    Rules: R4, R5."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code="  C-1 ")
    assert reread(db, SalesOrderItem, LS.id).fulfillment_completion_code == "C-1"
    ev = events_for(db, order)[0]
    assert ev.description == "Installation fulfilled (5.00 hour) (code: C-1)"
    assert ev.metadata_json == {"item_id": LS.id, "completion_code": "C-1"}


def test_sm_fsi_13__empty_string_code_already_null(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-13 -- an empty-string code is already falsy today: no code stored, no suffix.
    Rules: R4."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id, completion_code="")
    assert reread(db, SalesOrderItem, LS.id).fulfillment_completion_code is None
    assert events_for(db, order)[0].description == "Installation fulfilled (5.00 hour)"


def test_sm_fsi_14__recomputes_fully_delivered_true(db, M, w1, so, i1, i_s, u1):
    """SM-FSI-14 -- fulfilling the last undone line flips is_fully_delivered to True.
    Rules: R8."""
    order = so(invoice_confirmed=True)
    LS = mk_line(db, order, item=i_s, requires_delivery=False, ordered=Decimal("5.00"))
    mk_line(db, order, item=i1, requires_delivery=True, ordered=Decimal("10.00"), delivered=Decimal("10.00"))
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id)
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


def test_sm_fsi_15__recomputes_fully_delivered_false(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-15 -- fulfilling one line while another (LA) is still undelivered leaves the flag False.
    Rules: R8."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    db.expire_all()
    M.fulfill_service_item(db, LS.id, w1.id, u1.id)
    assert reread(db, SalesOrder, order.id).is_fully_delivered is False


def test_sm_fsi_16__unknown_line_raises(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-16 -- an unknown order line id raises ValueError; nothing written.
    Rules: R1; Errors row 1."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    missing = missing_id(db, SalesOrderItem)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.fulfill_service_item(db, missing, w1.id, u1.id)
    assert str(exc.value) == f"Sales order item {missing} not found"
    assert_nw(db, before)


def test_sm_fsi_17__foreign_workspace_line_not_found(db, M, w1, w2, so, i1, i_s, i_u, u1):
    """SM-FSI-17 -- a line whose own workspace_id is another workspace's is not found here.
    Rules: R1; Errors row 1."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    LS.workspace_id = w2.id
    db.flush()
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.fulfill_service_item(db, LS.id, w1.id, u1.id)
    assert str(exc.value) == f"Sales order item {LS.id} not found"
    assert_nw(db, before)


def test_sm_fsi_18__delivery_line_rejected_before_invoice_check(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-18 -- a line requiring delivery is rejected (R2) even when the invoice isn't finalized (R3).
    Rules: R2."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u, invoice_confirmed=False)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.fulfill_service_item(db, LA.id, w1.id, u1.id)
    assert str(exc.value) == "This line requires delivery — use the delivery workflow, not direct fulfillment"
    assert_nw(db, before)


def test_sm_fsi_19__invoice_not_confirmed_raises(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-19 -- an unconfirmed invoice blocks fulfilment of a non-delivery line.
    Rules: R3."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u, invoice_confirmed=False)
    before = nw_snapshot(db)
    with pytest.raises(ValueError) as exc:
        M.fulfill_service_item(db, LS.id, w1.id, u1.id)
    assert str(exc.value) == "Finalize the invoice before fulfilling this line"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_fsi_20__locks_order_item_before_update(db, M, w1, so, i1, i_s, i_u, u1):
    """SM-FSI-20 -- fulfilling should lock the order-line row before the not-yet-fulfilled check.
    Rules: R3a."""
    order, LS, LT, LU, LA = fsi_setup(db, so, i1, i_s, i_u)
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.fulfill_service_item(db, LS.id, w1.id, u1.id)
    assert result.id == order.id
    assert_lock_before_write(cap.statements, "sales_order_items", "sales_order_items", write_verb="update")


# =========================================================================== #
# SalesManager._recompute_is_fully_delivered
# =========================================================================== #

def test_sm_rfd_01__all_lines_done_flips_flag_true(db, M, w1, so):
    """SM-RFD-01 -- every line done (one over-delivered) flips the flag from False to True.
    Rules: R1, R3."""
    order = so(is_fully_delivered=False)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("10.00"), description="Line")
    mk_line(db, order, ordered=Decimal("5.00"), delivered=Decimal("6.00"), description="Line")
    mk_line(db, order, ordered=Decimal("5.00"), delivered=Decimal("5.00"), description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is True
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


def test_sm_rfd_02__one_short_line_keeps_flag_false(db, M, w1, so):
    """SM-RFD-02 -- one line short of ordered keeps the flag False.
    Rules: R1."""
    order = so(is_fully_delivered=False)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("9.00"), description="Line")
    mk_line(db, order, ordered=Decimal("5.00"), delivered=Decimal("5.00"), description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is False
    assert reread(db, SalesOrder, order.id).is_fully_delivered is False


def test_sm_rfd_03__flag_flips_back_to_false(db, M, w1, so):
    """SM-RFD-03 -- a previously-True flag is written back to False when a line is short.
    Rules: R3."""
    order = so(is_fully_delivered=True)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("9.00"), description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is False
    assert reread(db, SalesOrder, order.id).is_fully_delivered is False


def test_sm_rfd_04__no_lines_is_vacuously_true(db, M, w1, so):
    """SM-RFD-04 -- an order with no lines is vacuously fully delivered.
    Rules: R2."""
    order = so(is_fully_delivered=False)
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is True
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


@pytest.mark.xfail(strict=True, reason=xfail("BUG-731"))
def test_sm_rfd_05__refunded_should_count_toward_done(db, M, w1, so):
    """SM-RFD-05 -- delivered + refunded meeting ordered should count as done (refunded ignored today).
    Rules: R1."""
    order = so(is_fully_delivered=False)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("8.00"), refunded=Decimal("2.00"), description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is True
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


def test_sm_rfd_06__other_workspace_line_not_counted(db, M, w1, w2, so):
    """SM-RFD-06 -- a row sharing SO1's id but tagged with another workspace_id is not counted.
    Rules: R1."""
    order = so(is_fully_delivered=False)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("10.00"), description="Line")
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("0.00"), ws=w2, description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is True


def test_sm_rfd_08__already_true_and_done_stays_true(db, M, w1, so):
    """SM-RFD-08 -- an already-True flag with all lines done stays True.
    Rules: R3."""
    order = so(is_fully_delivered=True)
    mk_line(db, order, ordered=Decimal("10.00"), delivered=Decimal("10.00"), description="Line")
    result = M._recompute_is_fully_delivered(db, order, w1.id)
    assert result is True
    assert reread(db, SalesOrder, order.id).is_fully_delivered is True


# =========================================================================== #
# SalesManager._base_sections_confirmed
# =========================================================================== #

def test_sm_bsc_01__both_confirmed_true(M):
    """SM-BSC-01 -- both sections confirmed gives True regardless of the invoice flag.
    Rules: R1."""
    order = SalesOrder(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=False)
    assert M._base_sections_confirmed(order) is True


def test_sm_bsc_02__items_not_confirmed_false(M):
    """SM-BSC-02 -- items not confirmed gives False even with info and invoice confirmed.
    Rules: R1."""
    order = SalesOrder(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=True)
    assert M._base_sections_confirmed(order) is False


def test_sm_bsc_03__info_not_confirmed_false(M):
    """SM-BSC-03 -- info not confirmed gives False even with items and invoice confirmed.
    Rules: R1."""
    order = SalesOrder(order_info_confirmed=False, items_confirmed=True, invoice_confirmed=True)
    assert M._base_sections_confirmed(order) is False


def test_sm_bsc_04__neither_confirmed_false(M):
    """SM-BSC-04 -- neither section confirmed gives False.
    Rules: R1."""
    order = SalesOrder(order_info_confirmed=False, items_confirmed=False, invoice_confirmed=True)
    assert M._base_sections_confirmed(order) is False


# =========================================================================== #
# SalesManager.is_so_financially_locked
# =========================================================================== #

def test_sm_lck_01__no_invoice_false(db, M, so):
    """SM-LCK-01 -- no linked invoice is never locked.
    Rules: R1."""
    order = so()
    assert M.is_so_financially_locked(db, order) is False


def test_sm_lck_02__invoice_in_other_workspace_false(db, M, w2, so):
    """SM-LCK-02 -- an invoice id that only exists in another workspace is treated as not found.
    Rules: R2."""
    order = so()
    inv = mk_invoice(db, w2, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    assert M.is_so_financially_locked(db, order) is False


def test_sm_lck_03__confirmed_invoice_locks(db, M, w1, so):
    """SM-LCK-03 -- a confirmed linked invoice locks the order.
    Rules: R3."""
    order = so()
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    assert M.is_so_financially_locked(db, order) is True


def test_sm_lck_04__draft_invoice_not_locked(db, M, w1, so):
    """SM-LCK-04 -- a draft linked invoice does not lock the order.
    Rules: R3."""
    order = so()
    inv = mk_invoice(db, w1, status="draft", payment_status="unpaid")
    link_invoice(db, order, inv)
    assert M.is_so_financially_locked(db, order) is False


def test_sm_lck_05__voided_invoice_not_locked(db, M, w1, so):
    """SM-LCK-05 -- a voided linked invoice does not lock the order.
    Rules: R3."""
    order = so()
    inv = mk_invoice(db, w1, status="voided", payment_status="unpaid")
    link_invoice(db, order, inv)
    assert M.is_so_financially_locked(db, order) is False


# =========================================================================== #
# SalesManager.unlink_invoice_from_so
# =========================================================================== #

def unl_setup(db, so, w1, u1):
    """SO1 fully confirmed/invoiced/paid, linked to INV1 (confirmed, paid); U1 approved."""
    order = so(invoice_confirmed=True, is_invoiced=True, paid=True,
               order_info_confirmed=True, items_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    ap = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 5, 10, 0, 0))
    return order, inv, ap


def test_sm_unl_01__detaches_invoice_and_resets_flags(db, M, w1, so, u1):
    """SM-UNL-01 -- detaching the invoice clears the invoice flags but leaves section confirms and the approver alone.
    Rules: R1, R2, R3."""
    order, inv, ap = unl_setup(db, so, w1, u1)
    db.expire_all()
    result = M.unlink_invoice_from_so(db, order, u1.id, "Invoice voided")
    assert result is None
    r = reread(db, SalesOrder, order.id)
    assert r.invoice_id is None
    assert r.invoice_confirmed is False
    assert r.is_invoiced is False
    assert r.paid is False
    assert r.order_info_confirmed is True
    assert r.items_confirmed is True
    inv_r = reread(db, AccountInvoice, inv.id)
    assert inv_r is not None
    assert inv_r.invoice_status == "confirmed"
    ap_r = reread(db, SalesOrderApprover, ap.id)
    assert ap_r.approved is True
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "invoice_unlinked"
    assert ev.description == "Invoice voided"
    assert ev.performed_by == u1.id
    assert ev.metadata_json == {"invoice_id": inv.id}


def test_sm_unl_02__custom_event_type_and_null_user(db, M, w1, so, u1):
    """SM-UNL-02 -- a custom event_type and a null user are honored.
    Rules: R2."""
    order, inv, ap = unl_setup(db, so, w1, u1)
    db.expire_all()
    M.unlink_invoice_from_so(db, order, None, "Draft deleted", event_type="invoice_draft_deleted")
    ev = events_for(db, order)[0]
    assert ev.event_type == "invoice_draft_deleted"
    assert ev.description == "Draft deleted"
    assert ev.performed_by is None


def test_sm_unl_03__already_unlinked_is_idempotent(db, M, so, u1):
    """SM-UNL-03 -- an order with no linked invoice is unlinked again harmlessly; metadata invoice_id is null.
    Rules: R1, R2."""
    order = so()
    db.expire_all()
    M.unlink_invoice_from_so(db, order, u1.id, "x")
    r = reread(db, SalesOrder, order.id)
    assert r.invoice_id is None
    assert r.invoice_confirmed is False
    assert r.is_invoiced is False
    assert r.paid is False
    ev = events_for(db, order)[0]
    assert ev.metadata_json == {"invoice_id": None}


# =========================================================================== #
# SalesManager.set_section_confirm
# =========================================================================== #

def sec_setup(db, so, i1, u1, **order_overrides):
    """SO1: contact_name 'Rahim' (so() default), one line LA, all flags False, invoice_id null, not completed."""
    order = so(**order_overrides)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"))
    return order, LA


def test_sm_sec_01__confirm_order_info(db, M, w1, so, i1, u1):
    """SM-SEC-01 -- confirming order_info sets the flag and logs the matching event.
    Rules: R4, R9."""
    order, LA = sec_setup(db, so, i1, u1)
    db.expire_all()
    result = M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_info_confirmed is True
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "order_info_confirmed"
    assert ev.description == "Order info confirmed"
    assert ev.performed_by == u1.id
    assert ev.metadata_json is None


def test_sm_sec_02__confirm_items(db, M, w1, so, i1, u1):
    """SM-SEC-02 -- confirming items sets the flag and logs the matching event.
    Rules: R5, R9."""
    order, LA = sec_setup(db, so, i1, u1)
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "items", True)
    assert reread(db, SalesOrder, order.id).items_confirmed is True
    ev = events_for(db, order)[0]
    assert ev.event_type == "items_confirmed"
    assert ev.description == "Order items confirmed"


def test_sm_sec_03__unconfirm_no_approvers_no_reset_event(db, M, w1, so, i1, u1):
    """SM-SEC-03 -- unconfirming with no approvers logs only the unconfirm event, no approvals_reset.
    Rules: R9, R10."""
    order, LA = sec_setup(db, so, i1, u1, order_info_confirmed=True)
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", False)
    assert reread(db, SalesOrder, order.id).order_info_confirmed is False
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "order_info_unconfirmed"
    assert evs[0].description == "Order info unconfirmed"


def test_sm_sec_04__unconfirm_items_allowed_when_invoice_draft(db, M, w1, so, i1, u1):
    """SM-SEC-04 -- a draft (not confirmed) linked invoice does not block unconfirming items.
    Rules: R7, R9."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=True)
    inv = mk_invoice(db, w1, status="draft", payment_status="unpaid")
    link_invoice(db, order, inv)
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert reread(db, SalesOrder, order.id).items_confirmed is False
    ev = events_for(db, order)[0]
    assert ev.event_type == "items_unconfirmed"
    assert ev.description == "Order items unconfirmed"


def test_sm_sec_05__unconfirm_items_resets_approvals(db, M, w1, so, i1, u1, u2, u3):
    """SM-SEC-05 -- unconfirming items clears every approved approver and logs an approvals_reset after the unconfirm event.
    Rules: R10."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=True)
    ap1 = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 10, 10, 0, 0))
    ap2 = mk_approver(db, order, u2, approved=True, approved_at=datetime(2026, 9, 11, 10, 0, 0))
    ap3 = mk_approver(db, order, u3, approved=False, approved_at=None)
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert reread(db, SalesOrderApprover, ap1.id).approved is False
    assert reread(db, SalesOrderApprover, ap1.id).approved_at is None
    assert reread(db, SalesOrderApprover, ap2.id).approved is False
    assert reread(db, SalesOrderApprover, ap2.id).approved_at is None
    assert reread(db, SalesOrderApprover, ap3.id).approved is False
    evs = events_for(db, order)
    assert len(evs) == 2
    assert evs[0].event_type == "items_unconfirmed"
    assert evs[1].event_type == "approvals_reset"
    assert evs[1].description == "2 approval(s) cleared — Section unconfirmed"
    assert evs[1].performed_by == u1.id


def test_sm_sec_06__unknown_section_checked_before_order_lookup(db, M, w1, u1):
    """SM-SEC-06 -- an unknown section is rejected with 400 even for a non-existent order (R1 before R2).
    Rules: R1; Errors row 1."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, 999999999, w1.id, u1.id, "invoice", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unknown section 'invoice'"
    assert_nw(db, before)


def test_sm_sec_07__section_name_is_case_sensitive(db, M, w1, so, i1, u1):
    """SM-SEC-07 -- 'Items' (wrong case) is rejected the same way as any other unknown section.
    Rules: R1; Errors row 1."""
    order, LA = sec_setup(db, so, i1, u1)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "Items", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unknown section 'Items'"
    assert_nw(db, before)


def test_sm_sec_08__unknown_order_404(db, M, w1, u1):
    """SM-SEC-08 -- a non-existent order id is reported 404 once the section is known.
    Rules: R2; Errors row 1."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, 999999999, w1.id, u1.id, "items", True)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    assert_nw(db, before)


def test_sm_sec_09__foreign_workspace_order_404(db, M, w1, w2, so, a_x, f_x, u1):
    """SM-SEC-09 -- an order that exists only in another workspace is reported 404.
    Rules: R2; Errors row 1."""
    order = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "items", True)
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Sales order with ID {order.id} not found"
    assert_nw(db, before)


def test_sm_sec_10__no_op_confirm_skips_validation(db, M, w1, so, i1, u1):
    """SM-SEC-10 -- confirming a section that is already confirmed is a no-op; the blank contact_name never gets checked.
    Rules: R3."""
    order, LA = sec_setup(db, so, i1, u1, order_info_confirmed=True, contact_name=None)
    db.expire_all()
    result = M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_info_confirmed is True
    assert events_for(db, order) == []


def test_sm_sec_11__no_op_unconfirm_skips_lock_and_completion_checks(db, M, w1, so, i1, u1):
    """SM-SEC-11 -- unconfirming a section that is already unconfirmed is a no-op even on a locked, completed order.
    Rules: R3."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=False, order_completed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    ap = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    db.expire_all()
    result = M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert result.id == order.id
    assert events_for(db, order) == []
    assert reread(db, SalesOrderApprover, ap.id).approved is True


def test_sm_sec_12__null_contact_name_blocks_confirm(db, M, w1, so, i1, u1):
    """SM-SEC-12 -- a null contact_name blocks confirming order_info.
    Rules: R4; Errors row 3."""
    order, LA = sec_setup(db, so, i1, u1, contact_name=None)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Set the customer name before confirming"
    assert_nw(db, before)


def test_sm_sec_13__empty_contact_name_blocks_confirm(db, M, w1, so, i1, u1):
    """SM-SEC-13 -- an empty contact_name blocks confirming order_info.
    Rules: R4; Errors row 3."""
    order, LA = sec_setup(db, so, i1, u1, contact_name="")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Set the customer name before confirming"
    assert_nw(db, before)


def test_sm_sec_14__whitespace_contact_name_blocks_confirm(db, M, w1, so, i1, u1):
    """SM-SEC-14 -- a whitespace-only contact_name blocks confirming order_info.
    Rules: R4; Errors row 3."""
    order, LA = sec_setup(db, so, i1, u1, contact_name="   ")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Set the customer name before confirming"
    assert_nw(db, before)


def test_sm_sec_15__one_char_contact_name_allowed(db, M, w1, so, i1, u1):
    """SM-SEC-15 -- a one-character contact_name is enough to confirm order_info.
    Rules: R4."""
    order, LA = sec_setup(db, so, i1, u1, contact_name="R")
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    assert reread(db, SalesOrder, order.id).order_info_confirmed is True


def test_sm_sec_16__no_lines_blocks_items_confirm(db, M, w1, so, u1):
    """SM-SEC-16 -- an order with no lines cannot have its items section confirmed.
    Rules: R5; Errors row 3."""
    order = so()
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "items", True)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Add at least one line item before confirming"
    assert_nw(db, before)


def test_sm_sec_17__confirming_never_blocked_by_lock_or_completion(db, M, w1, so, i1, u1):
    """SM-SEC-17 -- confirming either section succeeds even on a completed, financially-locked order.
    Rules: R6."""
    order, LA = sec_setup(db, so, i1, u1, order_completed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    db.expire_all()
    M.set_section_confirm(db, order.id, w1.id, u1.id, "items", True)
    M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", True)
    r = reread(db, SalesOrder, order.id)
    assert r.items_confirmed is True
    assert r.order_info_confirmed is True
    evs = events_for(db, order)
    assert len(evs) == 2
    assert evs[0].event_type == "items_confirmed"
    assert evs[1].event_type == "order_info_confirmed"


def test_sm_sec_18__unconfirm_order_info_blocked_when_locked(db, M, w1, so, i1, u1):
    """SM-SEC-18 -- unconfirming order_info is blocked once the invoice is confirmed (locked).
    Rules: R7; Errors row 4."""
    order, LA = sec_setup(db, so, i1, u1, order_info_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    ap = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "order_info", False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot unconfirm order info after invoice is confirmed"
    assert_nw(db, before)
    assert reread(db, SalesOrder, order.id).order_info_confirmed is True
    assert reread(db, SalesOrderApprover, ap.id).approved is True


def test_sm_sec_19__unconfirm_items_blocked_when_locked(db, M, w1, so, i1, u1):
    """SM-SEC-19 -- unconfirming items is blocked once the invoice is confirmed (locked).
    Rules: R7; Errors row 4."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot unconfirm order items after invoice is confirmed"
    assert_nw(db, before)


def test_sm_sec_20__locked_check_before_completed_check(db, M, w1, so, i1, u1):
    """SM-SEC-20 -- when both locked and completed, the locked message wins (R7 before R8).
    Rules: R7, R8."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=True, order_completed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot unconfirm order items after invoice is confirmed"
    assert_nw(db, before)


def test_sm_sec_21__unconfirm_blocked_when_completed_not_locked(db, M, w1, so, i1, u1):
    """SM-SEC-21 -- a completed order with only a draft (unlocked) invoice is still blocked by R8.
    Rules: R8; Errors row 4."""
    order, LA = sec_setup(db, so, i1, u1, items_confirmed=True, order_completed=True)
    inv = mk_invoice(db, w1, status="draft", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_section_confirm(db, order.id, w1.id, u1.id, "items", False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot unconfirm — order is complete"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_sec_22__locks_order_before_insert_event(db, M, w1, so, i1, u1):
    """SM-SEC-22 -- confirming should lock the order row before the R3 current-flag check.
    Rules: R11."""
    order, LA = sec_setup(db, so, i1, u1)
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.set_section_confirm(db, order.id, w1.id, u1.id, "items", True)
    assert result.id == order.id
    assert_lock_before_write(cap.statements, "sales_orders", "sales_order_events")


# =========================================================================== #
# SalesManager.reset_approvals
# =========================================================================== #

def test_sm_ra_01__clears_approved_rows_logs_event(db, M, w1, so, u1, u2, u3):
    """SM-RA-01 -- clearing resets every approved approver and logs the count; unapproved rows are untouched.
    Rules: R1, R2."""
    order = so()
    ap1 = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 10, 0, 0, 0))
    ap2 = mk_approver(db, order, u2, approved=True, approved_at=datetime(2026, 9, 11, 0, 0, 0))
    ap3 = mk_approver(db, order, u3, approved=False)
    db.expire_all()
    result = M.reset_approvals(db, order.id, w1.id, u1.id)
    assert result is None
    assert reread(db, SalesOrderApprover, ap1.id).approved is False
    assert reread(db, SalesOrderApprover, ap1.id).approved_at is None
    assert reread(db, SalesOrderApprover, ap2.id).approved is False
    assert reread(db, SalesOrderApprover, ap2.id).approved_at is None
    assert reread(db, SalesOrderApprover, ap3.id).approved is False
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "approvals_reset"
    assert evs[0].description == "2 approval(s) cleared — Cleared approvals"
    assert evs[0].performed_by == u1.id
    assert evs[0].metadata_json is None


def test_sm_ra_02__custom_reason_and_null_user(db, M, w1, so, u1):
    """SM-RA-02 -- a custom reason is used in the event, and a null user is allowed.
    Rules: R2."""
    order = so()
    mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    db.expire_all()
    M.reset_approvals(db, order.id, w1.id, None, reason="Manual")
    ev = events_for(db, order)[0]
    assert ev.description == "1 approval(s) cleared — Manual"
    assert ev.performed_by is None


def test_sm_ra_03__no_approved_rows_is_noop(db, M, w1, so, u1, u2):
    """SM-RA-03 -- when no approver is currently approved, nothing is written or logged.
    Rules: R3."""
    order = so()
    ap1 = mk_approver(db, order, u1, approved=False)
    ap2 = mk_approver(db, order, u2, approved=False)
    db.expire_all()
    M.reset_approvals(db, order.id, w1.id, u1.id)
    assert events_for(db, order) == []
    assert reread(db, SalesOrderApprover, ap1.id).approved is False
    assert reread(db, SalesOrderApprover, ap2.id).approved is False


def test_sm_ra_04__no_approvers_is_noop(db, M, w1, so, u1):
    """SM-RA-04 -- an order with no approvers at all logs nothing and raises nothing.
    Rules: R3."""
    order = so()
    db.expire_all()
    M.reset_approvals(db, order.id, w1.id, u1.id)
    assert events_for(db, order) == []


def test_sm_ra_05__unknown_order_is_silent_noop(db, M, w1, u1):
    """SM-RA-05 -- an unknown order_id is not checked; the call just finds no approvers and returns None.
    Rules: R3."""
    result = M.reset_approvals(db, 999999999, w1.id, u1.id)
    assert result is None
    assert all_events(db) == []


def test_sm_ra_06__other_workspace_approver_not_touched(db, M, w1, w2, so, u1, u5):
    """SM-RA-06 -- an approver row sharing SO1's id but tagged with another workspace_id is untouched.
    Rules: R1."""
    order = so()
    ap1 = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    ap_w2 = mk_approver(db, order, u5, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0), ws=w2)
    db.expire_all()
    M.reset_approvals(db, order.id, w1.id, u1.id)
    assert reread(db, SalesOrderApprover, ap1.id).approved is False
    assert reread(db, SalesOrderApprover, ap_w2.id).approved is True
    ev = events_for(db, order)[0]
    assert ev.description == "1 approval(s) cleared — Cleared approvals"


# =========================================================================== #
# SalesManager.apply_post_invoice_confirms
# =========================================================================== #

def test_sm_apc_01__confirms_all_three_flags_and_logs_two_events(db, M, w1, so, u1):
    """SM-APC-01 -- with all three flags False, both confirms are logged in order, invoice_confirmed logs nothing.
    Rules: R1, R2, R3."""
    order = so(order_info_confirmed=False, items_confirmed=False, invoice_confirmed=False, contact_name=None)
    db.expire_all()
    result = M.apply_post_invoice_confirms(db, order, w1.id, u1.id)
    assert result is None
    r = reread(db, SalesOrder, order.id)
    assert r.order_info_confirmed is True
    assert r.items_confirmed is True
    assert r.invoice_confirmed is True
    evs = events_for(db, order)
    assert len(evs) == 2
    assert evs[0].event_type == "order_info_confirmed"
    assert evs[0].description == "Order info confirmed after invoice finalized"
    assert evs[0].performed_by == u1.id
    assert evs[1].event_type == "items_confirmed"
    assert evs[1].description == "Order items confirmed after invoice finalized"
    assert evs[1].performed_by == u1.id


def test_sm_apc_02__only_unconfirmed_items_gets_event(db, M, w1, so, u1):
    """SM-APC-02 -- only the still-unconfirmed items flag gets an event.
    Rules: R2, R4."""
    order = so(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=False)
    db.expire_all()
    M.apply_post_invoice_confirms(db, order, w1.id, u1.id)
    r = reread(db, SalesOrder, order.id)
    assert r.order_info_confirmed is True
    assert r.items_confirmed is True
    assert r.invoice_confirmed is True
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "items_confirmed"


def test_sm_apc_03__all_already_confirmed_logs_nothing(db, M, w1, so, u1):
    """SM-APC-03 -- all three flags already True logs nothing.
    Rules: R4."""
    order = so(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=True)
    db.expire_all()
    M.apply_post_invoice_confirms(db, order, w1.id, u1.id)
    r = reread(db, SalesOrder, order.id)
    assert r.order_info_confirmed is True
    assert r.items_confirmed is True
    assert r.invoice_confirmed is True
    assert events_for(db, order) == []


def test_sm_apc_04__only_unconfirmed_info_gets_event(db, M, w1, so, u1):
    """SM-APC-04 -- only the still-unconfirmed order_info flag gets an event; invoice_confirmed is also set silently.
    Rules: R1, R3, R4."""
    order = so(order_info_confirmed=False, items_confirmed=True, invoice_confirmed=False)
    db.expire_all()
    M.apply_post_invoice_confirms(db, order, w1.id, u1.id)
    r = reread(db, SalesOrder, order.id)
    assert r.order_info_confirmed is True
    assert r.invoice_confirmed is True
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "order_info_confirmed"


# =========================================================================== #
# SalesManager.mark_order_complete
# =========================================================================== #

def moc_setup(db, so, w1, i1, i_s, u1, *, invoice_payment_status="unpaid", **order_overrides):
    """SO1 (invoice_confirmed True, linked to INV(confirmed, <status>)); LA 10/10, LS 5/5;
    paid False, is_fully_delivered False; AP(U1, False); no returns."""
    order_overrides.setdefault("invoice_confirmed", True)
    order_overrides.setdefault("paid", False)
    order_overrides.setdefault("is_fully_delivered", False)
    order = so(**order_overrides)
    inv = mk_invoice(db, w1, status="confirmed", payment_status=invoice_payment_status)
    link_invoice(db, order, inv)
    LA = mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("10.00"))
    LS = mk_line(db, order, item=i_s, requires_delivery=False, ordered=Decimal("5.00"), delivered=Decimal("5.00"))
    ap = mk_approver(db, order, u1, approved=False)
    return order, inv, LA, LS, ap


def test_sm_moc_01__completes_order_and_logs_event(db, M, w1, so, i1, i_s, u1):
    """SM-MOC-01 -- completing stamps completed_at/completed_by and logs one event; paid stays False.
    Rules: R6, R8, R9."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1)
    db.expire_all()
    t0 = datetime.utcnow()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    t1 = datetime.utcnow()
    assert result.id == order.id
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert t0 <= r.completed_at <= t1
    assert r.completed_by == u1.id
    assert r.paid is False
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "order_completed"
    assert evs[0].description == "Order marked complete"
    assert evs[0].performed_by == u1.id


def test_sm_moc_02__syncs_paid_before_completed_event(db, M, w1, so, i1, i_s, u1):
    """SM-MOC-02 -- a paid linked invoice flips paid True and logs payment_status_synced before order_completed.
    Rules: R7."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1, invoice_payment_status="paid")
    db.expire_all()
    M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert reread(db, SalesOrder, order.id).paid is True
    evs = events_for(db, order)
    assert len(evs) == 2
    assert evs[0].event_type == "payment_status_synced"
    assert evs[1].event_type == "order_completed"


def test_sm_moc_03__already_completed_is_noop(db, M, w1, so, i1, u1, u2):
    """SM-MOC-03 -- an already-completed order is returned unchanged; no checks, no paid sync, no event.
    Rules: R2."""
    order = so(invoice_confirmed=False, paid=False, is_fully_delivered=False,
               order_completed=True, completed_at=datetime(2026, 9, 1, 8, 0, 0), completed_by=u2.id)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("0.00"))
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    r = reread(db, SalesOrder, order.id)
    assert r.completed_at == datetime(2026, 9, 1, 8, 0, 0)
    assert r.completed_by == u2.id
    assert r.paid is False
    assert events_for(db, order) == []


def test_sm_moc_04__unknown_or_foreign_order_404(db, M, w1, w2, so, a_x, f_x, u1):
    """SM-MOC-04 -- an unknown id and an order of another workspace both give 404; nothing written.
    Rules: R1; Errors row 1."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.mark_order_complete(db, 999999999, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    assert_nw(db, before)
    order = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    before2 = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc2:
        M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert exc2.value.status_code == 404
    assert exc2.value.detail == f"Sales order with ID {order.id} not found"
    assert_nw(db, before2)


def test_sm_moc_05__invoice_not_confirmed_blocks(db, M, w1, so, i1, u1):
    """SM-MOC-05 -- an unconfirmed invoice blocks completion before the lines/returns are even checked.
    Rules: R3."""
    order = so(invoice_confirmed=False)
    mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("9.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Finalize the invoice before marking the order complete"
    assert_nw(db, before)


def test_sm_moc_06__undone_line_before_open_return_check(db, M, w1, so, i1, u1):
    """SM-MOC-06 -- an undone delivery line blocks completion even with a pending return present (R4 before R5).
    Rules: R4."""
    order = so(invoice_confirmed=True)
    mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("9.00"))
    mk_return(db, order, status="pending")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Finish delivering and fulfilling all items before completing the order"
    assert_nw(db, before)


def test_sm_moc_07__undone_non_delivery_line_blocks(db, M, w1, so, i_s, u1):
    """SM-MOC-07 -- an undone non-delivery line also blocks completion with the same R4 message.
    Rules: R4."""
    order = so(invoice_confirmed=True)
    mk_line(db, order, item=i_s, requires_delivery=False, ordered=Decimal("5.00"), delivered=Decimal("4.00"))
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Finish delivering and fulfilling all items before completing the order"
    assert_nw(db, before)


def test_sm_moc_08__refunded_quantity_counts_as_done(db, M, w1, so, i1, u1):
    """SM-MOC-08 -- a line whose delivered+refunded meets ordered counts as done.
    Rules: R4."""
    order = so(invoice_confirmed=True)
    mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("8.00"), refunded=Decimal("2.00"))
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_completed is True


def test_sm_moc_09__no_lines_completes(db, M, w1, so, u1):
    """SM-MOC-09 -- an order with no lines passes the done-lines check vacuously.
    Rules: R4."""
    order = so(invoice_confirmed=True)
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_completed is True


def test_sm_moc_10__open_return_blocks(db, M, w1, so, u1):
    """SM-MOC-10 -- a pending return blocks completion.
    Rules: R5; Errors row 3."""
    order = so(invoice_confirmed=True)
    mk_return(db, order, status="pending")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Complete all open returns before marking the order complete"
    assert_nw(db, before)


def test_sm_moc_11__completed_and_voided_returns_do_not_block(db, M, w1, so, u1):
    """SM-MOC-11 -- a completed and a voided return do not count as open.
    Rules: R5."""
    order = so(invoice_confirmed=True)
    mk_return(db, order, status="completed")
    mk_return(db, order, status="voided")
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_completed is True


def test_sm_moc_12__other_orders_open_return_does_not_block(db, M, w1, so, u1):
    """SM-MOC-12 -- a pending return on a different order of the same workspace does not block this one.
    Rules: R5."""
    order = so(invoice_confirmed=True)
    so2 = so(sales_order_number="SO-2026-012", invoice_confirmed=True)
    mk_return(db, so2, status="pending")
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    assert reread(db, SalesOrder, order.id).order_completed is True


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_moc_13__locks_order_before_update(db, M, w1, so, i1, i_s, u1):
    """SM-MOC-13 -- completing should lock the order row before the R2 completion check.
    Rules: R10."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1)
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    assert result.id == order.id
    assert_lock_before_write(cap.statements, "sales_orders", "sales_orders", write_verb="update")


def test_sm_moc_14__completed_with_open_return_is_noop(db, M, w1, so, i1, i_s, u1, u2):
    """SM-MOC-14 -- a completed order with one return completed and one open: no 400, HOR True, nothing written.
    Rules: R2, RP6 (b)."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1, order_completed=True,
                                       completed_at=COMPLETED_AT, completed_by=u2.id)
    rc = mk_return(db, order, status="completed")
    ra = mk_return(db, order, status="pending")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, rc.id),
              snap_row(db, SalesOrderReturn, ra.id))
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    # Then 1
    assert result.id == order.id
    # Then 2
    assert hor(db, order) is True
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    assert r.paid is False
    # Then 4
    assert len(events_for(db, order)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, rc.id),
            snap_row(db, SalesOrderReturn, ra.id)) == before


def test_sm_moc_15__last_return_completed_is_noop(db, M, w1, so, i1, i_s, u1, u2):
    """SM-MOC-15 -- a completed order whose last return was completed: HOR False, nothing written.
    Rules: R2, RP6 (c)."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1, order_completed=True,
                                       completed_at=COMPLETED_AT, completed_by=u2.id)
    rc = mk_return(db, order, status="completed")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, rc.id))
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    # Then 1
    assert result.id == order.id
    # Then 2
    assert hor(db, order) is False
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    assert r.paid is False
    # Then 4
    assert len(events_for(db, order)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, rc.id)) == before


def test_sm_moc_16__last_return_cancelled_is_noop(db, M, w1, so, i1, i_s, u1, u2):
    """SM-MOC-16 -- a completed order whose last pending return was cancelled (voided): HOR False, nothing written.
    Rules: R2, RP6 (c), RP7."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1, order_completed=True,
                                       completed_at=COMPLETED_AT, completed_by=u2.id)
    rc = mk_return(db, order, status="completed")
    rv = mk_return(db, order, status="voided")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, rc.id),
              snap_row(db, SalesOrderReturn, rv.id))
    db.expire_all()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    # Then 1
    assert result.id == order.id
    # Then 2
    assert hor(db, order) is False
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    assert r.paid is False
    # Then 4
    assert len(events_for(db, order)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, rc.id),
            snap_row(db, SalesOrderReturn, rv.id)) == before


def test_sm_moc_17__other_workspaces_pending_returns_ignored(db, w0, M, w1, w2, so, i1, i_s, u1):
    """SM-MOC-17 -- pending returns of SO1 that sit in W0 and W2 neither block completion nor count for HOR.
    Rules: R5, RP2 (returns of this workspace only)."""
    assert w0.id < w1.id < w2.id  # Conventions guard: W0 before W1, W2 after
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1)
    r0 = mk_return(db, order, status="pending", ws=w0)
    r2x = mk_return(db, order, status="pending", ws=w2)
    db.expire_all()
    t0 = datetime.utcnow()
    result = M.mark_order_complete(db, order.id, w1.id, u1.id)
    t1 = datetime.utcnow()
    # Then 1
    assert result.id == order.id
    # Then 2
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_by == u1.id
    assert t0 <= r.completed_at <= t1
    # Then 3
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "order_completed"
    assert evs[0].description == "Order marked complete"
    assert evs[0].performed_by == u1.id
    # Then 4
    assert hor(db, order) is False
    # Then 5
    rr0 = reread(db, SalesOrderReturn, r0.id)
    assert rr0.status == "pending"
    assert rr0.workspace_id == w0.id
    # Then 6
    rr2x = reread(db, SalesOrderReturn, r2x.id)
    assert rr2x.status == "pending"
    assert rr2x.workspace_id == w2.id


def test_sm_moc_18__never_commits(db, M, w1, so, i1, i_s, u1):
    """SM-MOC-18 -- flush only: completing the order never commits.
    Rules: Side effects "flush only"."""
    order, inv, LA, LS, ap = moc_setup(db, so, w1, i1, i_s, u1)
    db.expire_all()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = M.mark_order_complete(db, order.id, w1.id, u1.id)
        # Then 1
        assert result.id == order.id
        # Then 2
        assert cm.call_count == 0
        # Then 3
        assert reread(db, SalesOrder, order.id).order_completed is True
        sp.rollback()


# =========================================================================== #
# SalesManager.reopen_for_return
# =========================================================================== #

def test_sm_ror_01__not_completed_is_noop(db, M, w1, so, u1):
    """SM-ROR-01 -- an order that is not completed is left alone; returns False.
    Rules: R1."""
    order = so(order_completed=False)
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    assert result is False
    assert events_for(db, order) == []
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is False
    assert r.completed_at is None
    assert r.completed_by is None


# Convention W0: a third workspace built BEFORE W1 (W0.id < W1.id < W2.id).
# Tests that use it list `w0` before `w1` in their arguments, so pytest builds
# it first; each such test guards the ordering before acting.
@pytest.fixture
def w0(db):
    return make_workspace(db)


# Convention A0: an account of W0 tagged with a `client` tag of W0.
@pytest.fixture
def a0(db, w0):
    acct = mk_account(db, w0, "W0 Client Co")
    mk_tag_assignment(db, acct, mk_tag(db, w0, "client"))
    return acct


# Convention F0: a factory of W0.
@pytest.fixture
def f0(db, w0):
    return mk_factory(db, w0, "W0 Plant")


def mk_so0(so, w0, a0, f0, **overrides):
    """SO0 = SO(...) of W0, number SO-2026-899, account A0, factory F0."""
    return so(workspace_id=w0.id, account_id=a0.id, factory_id=f0.id,
              sales_order_number="SO-2026-899", **overrides)


def mk_sox(so, w2, a_x, f_x, **overrides):
    """SOX = SO(...) of W2, number SO-2026-900, account AX, factory FX."""
    return so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id,
              sales_order_number="SO-2026-900", **overrides)


def snap_row(db, model, id_):
    """NW 'every field of the rows named in the case': all mapped columns, re-read."""
    r = reread(db, model, id_)
    return {c.key: getattr(r, c.key) for c in model.__mapper__.column_attrs}


def table_count(db, model):
    db.expire_all()
    return db.query(model).count()


COMPLETED_AT = datetime(2026, 9, 1, 8, 0, 0)


def hor(db, order):
    """Convention HOR(order): SalesOrderReturnManager.has_open_return, read after the action and a flush."""
    db.flush()
    return SalesOrderReturnManager().has_open_return(
        db, sales_order_id=order.id, workspace_id=order.workspace_id)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_02__completed_order_stays_completed(db, M, w1, so, u1, u2):
    """SM-ROR-02 -- with a return just started, a completed order stays completed: returns False, HOR True,
    stamps kept, no event, invoice frozen.
    Rules: R2, R2a, RP1 [BUG-2790]."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               invoice_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    ret = mk_return(db, order, status="pending")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id), snap_row(db, SalesOrderReturn, ret.id))
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    r_inv = reread(db, AccountInvoice, inv.id)
    assert r_inv.invoice_status == "confirmed"
    assert r_inv.payment_status == "unpaid"
    # Then 2
    assert hor(db, order) is True
    # Then 3
    assert result is False
    # Then 4
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    assert r.invoice_id == inv.id
    # Then 5
    assert len(events_for(db, order)) == 0
    # Then 6
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id), snap_row(db, SalesOrderReturn, ret.id)) == before


def test_sm_ror_03__invoice_link_flags_return_and_stock_untouched(db, M, w1, so, i1, p1, u1, u2):
    """SM-ROR-03 -- whatever it returns, the invoice, link, other flags, the return and stock are untouched.
    Rules: R2, RP4 (holds today and after the fix)."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               order_info_confirmed=True, items_confirmed=True, invoice_confirmed=True, paid=False)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    la = mk_line(db, order, item=i1, ordered=Decimal("10.00"), delivered=Decimal("10.00"))
    ret = mk_return(db, order, status="pending")
    n_inv = table_count(db, AccountInvoice)
    n_ledger = table_count(db, ProductLedger)
    n_deliv = table_count(db, SalesDelivery)
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    assert isinstance(result, bool)
    # Then 2
    r_inv = reread(db, AccountInvoice, inv.id)
    assert r_inv.invoice_status == "confirmed"
    assert r_inv.payment_status == "unpaid"
    assert r_inv.workspace_id == w1.id
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.invoice_id == inv.id
    assert r.invoice_confirmed is True
    assert r.order_info_confirmed is True
    assert r.items_confirmed is True
    assert r.paid is False
    # Then 4
    assert reread(db, SalesOrderReturn, ret.id).status == "pending"
    # Then 5
    r_la = reread(db, SalesOrderItem, la.id)
    assert r_la.quantity_delivered == Decimal("10.00")
    assert r_la.quantity_returned == Decimal("0.00")
    # Then 6
    assert reread(db, Product, p1.id).qty == 20
    # Then 7
    assert table_count(db, AccountInvoice) == n_inv
    # Then 8
    assert table_count(db, ProductLedger) == n_ledger
    # Then 9
    assert table_count(db, SalesDelivery) == n_deliv
    # Then 10
    assert hor(db, order) is True


def test_sm_ror_04__w0_open_order_noop(db, w0, a0, f0, M, w1, w2, so, u1):
    """SM-ROR-04 -- another workspace's (W0, built before W1) open order: returns False, nothing written.
    Rules: R1."""
    assert w0.id < w1.id < w2.id  # Conventions guard: W0 built before W1
    so0 = mk_so0(so, w0, a0, f0, order_completed=False, completed_at=None, completed_by=None)
    so1 = so(order_completed=False)
    before = (nw_snapshot(db), snap_row(db, SalesOrder, so0.id), snap_row(db, SalesOrder, so1.id))
    db.expire_all()
    result = M.reopen_for_return(db, so0, w1.id, u1.id)
    # Then 1
    assert result is False
    # Then 2
    r = reread(db, SalesOrder, so0.id)
    assert r.order_completed is False
    assert r.completed_at is None
    assert r.completed_by is None
    assert r.workspace_id == w0.id
    # Then 3
    assert len(all_events(db)) == 0
    # Then 4
    assert (nw_snapshot(db), snap_row(db, SalesOrder, so0.id), snap_row(db, SalesOrder, so1.id)) == before


def test_sm_ror_05__w2_open_order_noop(db, M, w1, w2, so, a_x, f_x, u1):
    """SM-ROR-05 -- another workspace's (W2, built after W1) open order: returns False, nothing written.
    Rules: R1."""
    assert w1.id < w2.id  # Conventions guard: W2 built after W1
    sox = mk_sox(so, w2, a_x, f_x, order_completed=False, completed_at=None, completed_by=None)
    so1 = so(order_completed=False)
    before = (nw_snapshot(db), snap_row(db, SalesOrder, sox.id), snap_row(db, SalesOrder, so1.id))
    db.expire_all()
    result = M.reopen_for_return(db, sox, w1.id, u1.id)
    # Then 1
    assert result is False
    # Then 2
    r = reread(db, SalesOrder, sox.id)
    assert r.order_completed is False
    assert r.completed_at is None
    assert r.completed_by is None
    assert r.workspace_id == w2.id
    # Then 3
    assert len(all_events(db)) == 0
    # Then 4
    assert (nw_snapshot(db), snap_row(db, SalesOrder, sox.id), snap_row(db, SalesOrder, so1.id)) == before


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_06__w0_completed_order_stays_completed(db, w0, a0, f0, M, w1, w2, so, u1):
    """SM-ROR-06 -- another workspace's (W0) completed order stays completed; its invoice stays frozen.
    Rules: R2, R2a, RP1 [BUG-2790]."""
    assert w0.id < w1.id < w2.id  # Conventions guard: W0 built before W1
    so0 = mk_so0(so, w0, a0, f0, order_completed=True, completed_at=COMPLETED_AT,
                 completed_by=u1.id, invoice_confirmed=True)
    inv0 = mk_invoice(db, w0, status="confirmed", payment_status="unpaid")
    link_invoice(db, so0, inv0)
    assert all_events(db) == []  # Given: no events anywhere
    before = (nw_snapshot(db), snap_row(db, SalesOrder, so0.id))
    db.expire_all()
    result = M.reopen_for_return(db, so0, w1.id, u1.id)
    # Then 1
    r_inv = reread(db, AccountInvoice, inv0.id)
    assert r_inv.invoice_status == "confirmed"
    assert r_inv.payment_status == "unpaid"
    # Then 2
    assert result is False
    # Then 3
    r = reread(db, SalesOrder, so0.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u1.id
    assert r.workspace_id == w0.id
    # Then 4
    assert len(all_events(db)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, so0.id)) == before


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_07__w2_completed_order_stays_completed(db, M, w1, w2, so, a_x, f_x, u1, u5):
    """SM-ROR-07 -- another workspace's (W2) completed order stays completed; its invoice stays frozen.
    Rules: R2, R2a, RP1 [BUG-2790]."""
    assert w1.id < w2.id  # Conventions guard: W2 built after W1
    sox = mk_sox(so, w2, a_x, f_x, order_completed=True, completed_at=COMPLETED_AT,
                 completed_by=u5.id, invoice_confirmed=True)
    invx = mk_invoice(db, w2, status="confirmed", payment_status="unpaid")
    link_invoice(db, sox, invx)
    assert all_events(db) == []  # Given: no events anywhere
    before = (nw_snapshot(db), snap_row(db, SalesOrder, sox.id))
    db.expire_all()
    result = M.reopen_for_return(db, sox, w1.id, u1.id)
    # Then 1
    r_inv = reread(db, AccountInvoice, invx.id)
    assert r_inv.invoice_status == "confirmed"
    assert r_inv.payment_status == "unpaid"
    # Then 2
    assert result is False
    # Then 3
    r = reread(db, SalesOrder, sox.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u5.id
    assert r.workspace_id == w2.id
    # Then 4
    assert len(all_events(db)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, sox.id)) == before


def test_sm_ror_08__w0_call_leaves_w0_invoice_and_w1_order(db, w0, a0, f0, M, w1, w2, so, u1, u2):
    """SM-ROR-08 -- a call on W0's completed order leaves its invoice and W1's own completed order alone.
    Rules: R2a (holds today and after the fix)."""
    assert w0.id < w1.id < w2.id  # Conventions guard: W0 built before W1
    so0 = mk_so0(so, w0, a0, f0, order_completed=True, completed_at=COMPLETED_AT,
                 completed_by=u1.id, invoice_confirmed=True)
    inv0 = mk_invoice(db, w0, status="confirmed", payment_status="unpaid")
    link_invoice(db, so0, inv0)
    so1 = so(order_completed=True, completed_at=datetime(2026, 9, 2, 9, 0, 0), completed_by=u2.id)
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, so1, inv1)
    db.expire_all()
    result = M.reopen_for_return(db, so0, w1.id, u1.id)
    # Then 1
    assert isinstance(result, bool)
    # Then 2
    r_inv0 = reread(db, AccountInvoice, inv0.id)
    assert r_inv0.invoice_status == "confirmed"
    assert r_inv0.payment_status == "unpaid"
    assert r_inv0.workspace_id == w0.id
    # Then 3
    r0 = reread(db, SalesOrder, so0.id)
    assert r0.invoice_id == inv0.id
    assert r0.invoice_confirmed is True
    # Then 4
    r1 = reread(db, SalesOrder, so1.id)
    assert r1.order_completed is True
    assert r1.completed_at == datetime(2026, 9, 2, 9, 0, 0)
    assert r1.completed_by == u2.id
    # Then 5
    r_inv1 = reread(db, AccountInvoice, inv1.id)
    assert r_inv1.invoice_status == "confirmed"
    assert r_inv1.payment_status == "unpaid"
    # Then 6
    assert len(events_for(db, so1)) == 0


def test_sm_ror_09__w2_call_leaves_w2_invoice_and_w1_order(db, M, w1, w2, so, a_x, f_x, u1, u2, u5):
    """SM-ROR-09 -- a call on W2's completed order leaves its invoice and W1's own completed order alone.
    Rules: R2a (holds today and after the fix)."""
    assert w1.id < w2.id  # Conventions guard: W2 built after W1
    sox = mk_sox(so, w2, a_x, f_x, order_completed=True, completed_at=COMPLETED_AT,
                 completed_by=u5.id, invoice_confirmed=True)
    invx = mk_invoice(db, w2, status="confirmed", payment_status="unpaid")
    link_invoice(db, sox, invx)
    so1 = so(order_completed=True, completed_at=datetime(2026, 9, 2, 9, 0, 0), completed_by=u2.id)
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, so1, inv1)
    db.expire_all()
    result = M.reopen_for_return(db, sox, w1.id, u1.id)
    # Then 1
    assert isinstance(result, bool)
    # Then 2
    r_invx = reread(db, AccountInvoice, invx.id)
    assert r_invx.invoice_status == "confirmed"
    assert r_invx.payment_status == "unpaid"
    assert r_invx.workspace_id == w2.id
    # Then 3
    rx = reread(db, SalesOrder, sox.id)
    assert rx.invoice_id == invx.id
    assert rx.invoice_confirmed is True
    # Then 4
    r1 = reread(db, SalesOrder, so1.id)
    assert r1.order_completed is True
    assert r1.completed_at == datetime(2026, 9, 2, 9, 0, 0)
    assert r1.completed_by == u2.id
    # Then 5
    r_inv1 = reread(db, AccountInvoice, inv1.id)
    assert r_inv1.invoice_status == "confirmed"
    assert r_inv1.payment_status == "unpaid"
    # Then 6
    assert len(events_for(db, so1)) == 0


def test_sm_ror_10__never_commits(db, M, w1, so, u1, u2):
    """SM-ROR-10 -- flush only: the call never commits.
    Rules: R2a; Side effects "flush only"."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id)
    db.expire_all()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = M.reopen_for_return(db, order, w1.id, u1.id)
        # Then 1
        assert isinstance(result, bool)
        # Then 2
        assert cm.call_count == 0
        sp.rollback()


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_11__two_open_returns_order_stays_completed(db, M, w1, so, u1, u2):
    """SM-ROR-11 -- two returns open at once: the completed order stays completed, returns False, nothing written.
    Rules: R2a, RP6 (a) [BUG-2790]."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               invoice_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    ra = mk_return(db, order, status="pending")
    rb = mk_return(db, order, status="pending")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, ra.id),
              snap_row(db, SalesOrderReturn, rb.id))
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    assert hor(db, order) is True
    # Then 2
    assert result is False
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    # Then 4
    assert reread(db, SalesOrderReturn, ra.id).status == "pending"
    assert reread(db, SalesOrderReturn, rb.id).status == "pending"
    # Then 5
    assert len(events_for(db, order)) == 0
    # Then 6
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, ra.id),
            snap_row(db, SalesOrderReturn, rb.id)) == before


def test_sm_ror_12__two_open_returns_stay_pending(db, M, w1, so, u1, u2):
    """SM-ROR-12 -- two returns open at once: whatever it returns, both stay pending, HOR True, invoice frozen.
    Rules: R2a, RP6 (a) (holds today and after the fix)."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               invoice_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    ra = mk_return(db, order, status="pending")
    rb = mk_return(db, order, status="pending")
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    assert isinstance(result, bool)
    # Then 2
    assert hor(db, order) is True
    # Then 3
    assert reread(db, SalesOrderReturn, ra.id).status == "pending"
    # Then 4
    assert reread(db, SalesOrderReturn, rb.id).status == "pending"
    # Then 5
    r_inv = reread(db, AccountInvoice, inv.id)
    assert r_inv.invoice_status == "confirmed"
    assert r_inv.payment_status == "unpaid"
    # Then 6
    db.expire_all()
    assert db.query(SalesOrderReturn).filter(SalesOrderReturn.sales_order_id == order.id).count() == 2


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_13__one_completed_one_open_order_stays_completed(db, M, w1, so, u1, u2):
    """SM-ROR-13 -- one return completed, another still open: the order stays completed, returns False.
    Rules: R2a, RP6 (b) [BUG-2790]."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               invoice_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    rc = mk_return(db, order, status="completed")
    ra = mk_return(db, order, status="pending")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, rc.id),
              snap_row(db, SalesOrderReturn, ra.id))
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    assert hor(db, order) is True
    # Then 2
    assert result is False
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    # Then 4
    assert reread(db, SalesOrderReturn, rc.id).status == "completed"
    # Then 5
    assert reread(db, SalesOrderReturn, ra.id).status == "pending"
    # Then 6
    assert len(events_for(db, order)) == 0
    # Then 7
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, rc.id),
            snap_row(db, SalesOrderReturn, ra.id)) == before


@pytest.mark.xfail(strict=True, reason=xfail("BUG-2790"))
def test_sm_ror_14__no_return_pending_order_stays_completed(db, M, w1, so, u1, u2):
    """SM-ROR-14 -- no return pending (the last one was cancelled): the order stays completed, returns False.
    Rules: R2, RP6 (c), RP7 [BUG-2790]."""
    order = so(order_completed=True, completed_at=COMPLETED_AT, completed_by=u2.id,
               invoice_confirmed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    rc = mk_return(db, order, status="completed")
    rv = mk_return(db, order, status="voided")
    assert events_for(db, order) == []  # Given: no events on SO1
    before = (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
              snap_row(db, SalesOrderReturn, rc.id),
              snap_row(db, SalesOrderReturn, rv.id))
    db.expire_all()
    result = M.reopen_for_return(db, order, w1.id, u1.id)
    # Then 1
    assert hor(db, order) is False
    # Then 2
    assert result is False
    # Then 3
    r = reread(db, SalesOrder, order.id)
    assert r.order_completed is True
    assert r.completed_at == COMPLETED_AT
    assert r.completed_by == u2.id
    # Then 4
    assert len(events_for(db, order)) == 0
    # Then 5
    assert (nw_snapshot(db), snap_row(db, SalesOrder, order.id),
            snap_row(db, SalesOrderReturn, rc.id),
            snap_row(db, SalesOrderReturn, rv.id)) == before


# =========================================================================== #
# SalesManager._invoice_payment_status
# =========================================================================== #

def test_sm_ips_01__no_invoice_none(db, M, so):
    """SM-IPS-01 -- no linked invoice gives None.
    Rules: R1."""
    order = so()
    assert M._invoice_payment_status(db, order) is None


def test_sm_ips_02__invoice_in_other_workspace_none(db, M, w2, so):
    """SM-IPS-02 -- an invoice id only found in another workspace gives None.
    Rules: R2."""
    order = so()
    inv = mk_invoice(db, w2, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    assert M._invoice_payment_status(db, order) is None


def test_sm_ips_03__returns_payment_status_string(db, M, w1, so):
    """SM-IPS-03 -- the linked invoice's payment_status is returned as-is, whichever value it holds.
    Rules: R3."""
    for status in ("unpaid", "partial", "paid", "overdue"):
        order = so(sales_order_number=f"SO-2026-ips-{status}")
        inv = mk_invoice(db, w1, status="confirmed", payment_status=status)
        link_invoice(db, order, inv)
        assert M._invoice_payment_status(db, order) == status


# =========================================================================== #
# SalesManager.sync_so_for_linked_invoice
# =========================================================================== #

def test_sm_sli_01__invoice_not_linked_to_any_order_noop(db, M, w1, so, u1):
    """SM-SLI-01 -- an invoice no order links to leaves everything alone.
    Rules: R1."""
    order = so(paid=False)
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    result = M.sync_so_for_linked_invoice(db, inv1.id, w1.id, u1.id)
    assert result is None
    assert all_events(db) == []
    assert reread(db, SalesOrder, order.id).paid is False


def test_sm_sli_02__order_in_other_workspace_not_found(db, M, w1, w2, so, a_x, f_x, u1):
    """SM-SLI-02 -- an order of another workspace that links this invoice is not found here.
    Rules: R1."""
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    sox = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900", paid=False)
    link_invoice(db, sox, inv1)
    M.sync_so_for_linked_invoice(db, inv1.id, w1.id, u1.id)
    assert all_events(db) == []
    assert reread(db, SalesOrder, sox.id).paid is False


def test_sm_sli_03__syncs_linked_order_to_paid(db, M, w1, so, u1):
    """SM-SLI-03 -- the linked order is synced to paid and logs one event.
    Rules: R2."""
    order = so(paid=False)
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv1)
    db.expire_all()
    M.sync_so_for_linked_invoice(db, inv1.id, w1.id, u1.id)
    assert reread(db, SalesOrder, order.id).paid is True
    evs = events_for(db, order)
    assert len(evs) == 1
    assert evs[0].event_type == "payment_status_synced"


def test_sm_sli_04__only_one_of_several_linked_orders_synced(db, M, w1, so, u1):
    """SM-SLI-04 -- when several orders link the same invoice, exactly one of them is synced.
    Rules: R2."""
    order1 = so(paid=False)
    order2 = so(sales_order_number="SO-2026-012", paid=False)
    inv1 = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order1, inv1)
    link_invoice(db, order2, inv1)
    db.expire_all()
    M.sync_so_for_linked_invoice(db, inv1.id, w1.id, u1.id)
    r1 = reread(db, SalesOrder, order1.id)
    r2 = reread(db, SalesOrder, order2.id)
    assert [r1.paid, r2.paid].count(True) == 1
    synced = [e for e in all_events(db) if e.event_type == "payment_status_synced"]
    assert len(synced) == 1


# =========================================================================== #
# SalesManager.sync_so_paid
# =========================================================================== #

def test_sm_sp_01__unpaid_to_paid(db, M, w1, so, u1):
    """SM-SP-01 -- a paid linked invoice flips the flag True and logs an event.
    Rules: R1, R3."""
    order = so(paid=False)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, u1.id)
    assert result is True
    assert reread(db, SalesOrder, order.id).paid is True
    ev = events_for(db, order)[0]
    assert ev.event_type == "payment_status_synced"
    assert ev.description == "Order marked paid from linked invoice"
    assert ev.metadata_json == {"paid": True}
    assert ev.performed_by == u1.id


def test_sm_sp_02__paid_to_unpaid(db, M, w1, so):
    """SM-SP-02 -- a partially-paid linked invoice flips the flag False with a null performer.
    Rules: R1, R3."""
    order = so(paid=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="partial")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, None)
    assert result is True
    assert reread(db, SalesOrder, order.id).paid is False
    ev = events_for(db, order)[0]
    assert ev.description == "Order marked unpaid from linked invoice"
    assert ev.metadata_json == {"paid": False}
    assert ev.performed_by is None


def test_sm_sp_03__unpaid_or_overdue_stays_false(db, M, w1, so):
    """SM-SP-03 -- an unpaid or overdue linked invoice leaves an already-False flag False, no event.
    Rules: R1, R2."""
    for status in ("unpaid", "overdue"):
        order = so(sales_order_number=f"SO-2026-sp-{status}", paid=False)
        inv = mk_invoice(db, w1, status="confirmed", payment_status=status)
        link_invoice(db, order, inv)
        db.expire_all()
        result = M.sync_so_paid(db, order, w1.id, None)
        assert result is False
        assert events_for(db, order) == []


def test_sm_sp_04__paid_with_no_invoice_flips_false(db, M, w1, so):
    """SM-SP-04 -- a paid order with no linked invoice is synced back to False.
    Rules: R1."""
    order = so(paid=True)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, None)
    assert result is True
    assert reread(db, SalesOrder, order.id).paid is False


def test_sm_sp_05__invoice_in_other_workspace_ignored(db, M, w1, w2, so):
    """SM-SP-05 -- an invoice id only found in another workspace is treated as no invoice; no event.
    Rules: R1."""
    order = so(paid=False)
    inv = mk_invoice(db, w2, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, None)
    assert result is False
    assert events_for(db, order) == []


def test_sm_sp_06__voided_invoice_status_not_considered(db, M, w1, so):
    """SM-SP-06 -- a voided invoice still syncs to paid=True; invoice_status itself is not considered.
    Rules: R1."""
    order = so(paid=False)
    inv = mk_invoice(db, w1, status="voided", payment_status="paid")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, None)
    assert result is True
    assert reread(db, SalesOrder, order.id).paid is True


def test_sm_sp_07__already_paid_is_noop(db, M, w1, so):
    """SM-SP-07 -- an order already matching the target value is a no-op; no event.
    Rules: R2."""
    order = so(paid=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="paid")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.sync_so_paid(db, order, w1.id, None)
    assert result is False
    assert events_for(db, order) == []


# =========================================================================== #
# SalesManager.list_approvers
# =========================================================================== #

def test_sm_la_01__unknown_or_foreign_order_404(db, M, w1, w2, so, a_x, f_x):
    """SM-LA-01 -- an unknown id and an order of another workspace both give 404.
    Rules: R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, 999999999, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    order = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    with pytest.raises(HTTPException) as exc2:
        M.list_approvers(db, order.id, w1.id)
    assert exc2.value.status_code == 404
    assert exc2.value.detail == f"Sales order with ID {order.id} not found"


def test_sm_la_02__no_approvers_empty_list(db, M, w1, so):
    """SM-LA-02 -- an order with no approvers returns an empty list.
    Rules: R2."""
    order = so()
    assert M.list_approvers(db, order.id, w1.id) == []


def test_sm_la_03__ordered_by_assigned_at_with_profile_and_position(db, M, w1, so, u1, u2, u3):
    """SM-LA-03 -- approvers are returned ordered by assigned_at, each paired with its profile and workspace position.
    Rules: R2, R3, R4."""
    order = so()
    mk_approver(db, order, u2, assigned_at=datetime(2026, 9, 2))
    mk_approver(db, order, u1, assigned_at=datetime(2026, 9, 1))
    mk_approver(db, order, u3, assigned_at=datetime(2026, 9, 3))
    db.expire_all()
    result = M.list_approvers(db, order.id, w1.id)
    assert len(result) == 3
    assert [r[1].id for r in result] == [u1.id, u2.id, u3.id]
    assert [r[2] for r in result] == ["Sales Lead", None, "Clerk"]


def test_sm_la_04__non_member_user_has_no_position(db, M, w1, so, u5):
    """SM-LA-04 -- an approver who is not a W1 member (only a W2 member) gets a null position.
    Rules: R3."""
    order = so()
    mk_approver(db, order, u5)
    db.expire_all()
    result = M.list_approvers(db, order.id, w1.id)
    assert len(result) == 1
    assert result[0][2] is None


def test_sm_la_05__other_workspace_approver_row_excluded(db, M, w1, w2, so, u1, u5):
    """SM-LA-05 -- an approver row sharing SO1's id but tagged with another workspace_id is excluded.
    Rules: R2."""
    order = so()
    ap1 = mk_approver(db, order, u1)
    mk_approver(db, order, u5, ws=w2)
    db.expire_all()
    result = M.list_approvers(db, order.id, w1.id)
    assert len(result) == 1
    assert result[0][0].id == ap1.id


# =========================================================================== #
# SalesManager.approval_summary
# =========================================================================== #

def test_sm_as_01__counts_approved_against_assigned(db, M, w1, so, u1, u2):
    """SM-AS-01 -- with required_approvals null, required falls back to the number of assigned approvers.
    Rules: R1, R2, R3."""
    order = so(required_approvals=None)
    mk_approver(db, order, u1, approved=True)
    mk_approver(db, order, u2, approved=False)
    db.expire_all()
    assert M.approval_summary(db, order) == (1, 2, False)


def test_sm_as_02__all_approved_met(db, M, w1, so, u1, u2):
    """SM-AS-02 -- every assigned approver approved meets the (null) required count.
    Rules: R3."""
    order = so(required_approvals=None)
    mk_approver(db, order, u1, approved=True)
    mk_approver(db, order, u2, approved=True)
    db.expire_all()
    assert M.approval_summary(db, order) == (2, 2, True)


def test_sm_as_03__explicit_required_above_approvers(db, M, w1, so, u1, u2):
    """SM-AS-03 -- an explicit required_approvals above the approved count is not met.
    Rules: R2, R3."""
    order = so(required_approvals=3)
    mk_approver(db, order, u1, approved=True)
    mk_approver(db, order, u2, approved=True)
    db.expire_all()
    assert M.approval_summary(db, order) == (2, 3, False)


def test_sm_as_04__explicit_required_met_below_assigned_count(db, M, w1, so, u1, u2):
    """SM-AS-04 -- an explicit required_approvals below the assigned count is met once reached.
    Rules: R2, R3."""
    order = so(required_approvals=1)
    mk_approver(db, order, u1, approved=True)
    mk_approver(db, order, u2, approved=False)
    db.expire_all()
    assert M.approval_summary(db, order) == (1, 1, True)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-736"))
def test_sm_as_05__no_approvers_should_not_be_automatically_met(db, M, w1, so):
    """SM-AS-05 -- with zero approvers and null required_approvals, approval should not be vacuously met.
    Rules: R2, R3."""
    order = so(required_approvals=None)
    db.expire_all()
    assert M.approval_summary(db, order) == (0, 1, False)


def test_sm_as_06__no_approvers_explicit_required(db, M, w1, so):
    """SM-AS-06 -- zero approvers against an explicit required_approvals is simply not met.
    Rules: R2."""
    order = so(required_approvals=2)
    db.expire_all()
    assert M.approval_summary(db, order) == (0, 2, False)


def test_sm_as_07__other_workspace_approver_excluded(db, M, w1, w2, so, u1, u5):
    """SM-AS-07 -- an approver row sharing SO1's id but tagged with another workspace_id is excluded from the count.
    Rules: R1."""
    order = so(required_approvals=None)
    mk_approver(db, order, u1, approved=True)
    mk_approver(db, order, u5, approved=True, ws=w2)
    db.expire_all()
    assert M.approval_summary(db, order) == (1, 1, True)


def test_sm_as_08__single_approver_met(db, M, w1, so, u1):
    """SM-AS-08 -- a single approved approver with null required_approvals is met.
    Rules: R2."""
    order = so(required_approvals=None)
    mk_approver(db, order, u1, approved=True)
    db.expire_all()
    assert M.approval_summary(db, order) == (1, 1, True)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-required"))
def test_sm_as_09__zero_required_approvals_should_be_rejected(db):
    """SM-AS-09 -- the schema should reject required_approvals=0.
    Rules: R2."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderUpdate(required_approvals=0)
    assert "required_approvals" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-362-required"))
def test_sm_as_10__negative_required_approvals_should_be_rejected(db):
    """SM-AS-10 -- the schema should reject a negative required_approvals.
    Rules: R2."""
    with pytest.raises(ValidationError) as exc:
        SalesOrderUpdate(required_approvals=-1)
    assert "required_approvals" in str(exc.value)


def test_sm_as_11__valid_required_approvals_values_build(db):
    """SM-AS-11 -- a positive required_approvals and an explicit None both build today.
    Rules: R2."""
    a = SalesOrderUpdate(required_approvals=1)
    b = SalesOrderUpdate(required_approvals=None)
    assert a.required_approvals == 1
    assert b.required_approvals is None


# =========================================================================== #
# SalesManager.add_approver
# =========================================================================== #

def aa_setup(db, so, u1, **order_overrides):
    """SO1 is not completed, invoice_id null, and has AP(U1)."""
    order = so(**order_overrides)
    ap1 = mk_approver(db, order, u1)
    return order, ap1


def test_sm_aa_01__adds_approver_and_logs_event(db, M, w1, so, u1, u2):
    """SM-AA-01 -- adding an approver creates the row and logs an event naming the new approver.
    Rules: R4, R5."""
    order, ap1 = aa_setup(db, so, u1)
    db.expire_all()
    t0 = datetime.utcnow()
    result = M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    t1 = datetime.utcnow()
    assert result.id is not None
    r = reread(db, SalesOrderApprover, result.id)
    assert r.sales_order_id == order.id
    assert r.user_id == u2.id
    assert r.approved is False
    assert r.approved_at is None
    assert r.assigned_by == u1.id
    assert t0 <= r.assigned_at <= t1
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "approver_added"
    assert ev.description == "Added Bob Karim as approver"
    assert ev.metadata_json == {"user_id": u2.id, "user_name": "Bob Karim"}
    assert ev.performed_by == u1.id


def test_sm_aa_02__unknown_or_foreign_order_404(db, M, w1, w2, so, a_x, f_x, u1, u2):
    """SM-AA-02 -- an unknown id and an order of another workspace both give 404; nothing written.
    Rules: R1; Errors row 1."""
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, 999999999, u2.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    assert_nw(db, before)
    order = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    before2 = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc2:
        M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    assert exc2.value.status_code == 404
    assert exc2.value.detail == f"Sales order with ID {order.id} not found"
    assert_nw(db, before2)


def test_sm_aa_03__non_member_rejected(db, M, w1, so, u1, u5):
    """SM-AA-03 -- a user who isn't a member of this workspace at all is rejected.
    Rules: R2; Errors row 2."""
    order, ap1 = aa_setup(db, so, u1)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u5.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert_nw(db, before)


def test_sm_aa_04__suspended_or_invited_member_rejected(db, M, w1, so, u1, u3, u4):
    """SM-AA-04 -- a suspended or invited member is also not an active member.
    Rules: R2; Errors row 2."""
    order, ap1 = aa_setup(db, so, u1)
    before = nw_snapshot(db)
    for user in (u3, u4):
        with pytest.raises(HTTPException) as exc:
            M.add_approver(db, order.id, user.id, w1.id, assigned_by=u1.id)
        assert exc.value.status_code == 400
        assert exc.value.detail == "User is not an active member of this workspace"
    assert_nw(db, before)


def test_sm_aa_05__already_approver_conflict(db, M, w1, so, u1):
    """SM-AA-05 -- a user already an approver of this order is rejected with 409.
    Rules: R3; Errors row 3."""
    order, ap1 = aa_setup(db, so, u1)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u1.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "User is already an approver for this order"
    assert_nw(db, before)


def test_sm_aa_06__member_check_runs_before_duplicate_check(db, M, w1, so, u1, u3):
    """SM-AA-06 -- even an existing approver is rejected on the member check first if not active (R2 before R3).
    Rules: R2, R3."""
    order, ap1 = aa_setup(db, so, u1)
    mk_approver(db, order, u3)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u3.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not an active member of this workspace"
    assert_nw(db, before)


def test_sm_aa_07__duplicate_check_runs_before_completion_check(db, M, w1, so, u1):
    """SM-AA-07 -- a completed order still reports 409 (already approver) before any completion check (R3 before R6).
    Rules: R3, R6."""
    order, ap1 = aa_setup(db, so, u1, order_completed=True)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u1.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "User is already an approver for this order"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_aa_08__completed_order_should_block_adding(db, M, w1, so, u1, u2):
    """SM-AA-08 -- adding an approver to a completed order should be rejected.
    Rules: R6; Errors row 4."""
    order, ap1 = aa_setup(db, so, u1, order_completed=True)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — order is complete"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_aa_09__locked_order_should_block_adding(db, M, w1, so, u1, u2):
    """SM-AA-09 -- adding an approver to a financially-locked order should be rejected.
    Rules: R6; Errors row 5."""
    order, ap1 = aa_setup(db, so, u1)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — invoice is locked"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_aa_10__completed_check_before_locked_check(db, M, w1, so, u1, u2):
    """SM-AA-10 -- when both completed and locked, the order-complete message should win.
    Rules: R6."""
    order, ap1 = aa_setup(db, so, u1, order_completed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — order is complete"
    assert_nw(db, before)


def test_sm_aa_11__draft_invoice_does_not_block_adding(db, M, w1, so, u1, u2):
    """SM-AA-11 -- a draft (not confirmed) linked invoice does not block adding an approver.
    Rules: R6."""
    order, ap1 = aa_setup(db, so, u1)
    inv = mk_invoice(db, w1, status="draft", payment_status="unpaid")
    link_invoice(db, order, inv)
    db.expire_all()
    result = M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    assert result.user_id == u2.id


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_aa_13__locked_order_add_should_be_fully_rejected(db, M, w1, so, u1, u2):
    """SM-AA-13 -- on a locked order, adding should be rejected outright: only AP(U1) remains, no event logged.
    Rules: R6."""
    order, ap1 = aa_setup(db, so, u1)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    with pytest.raises(HTTPException):
        M.add_approver(db, order.id, u2.id, w1.id, assigned_by=u1.id)
    rows = approvers_for(db, order)
    assert [r.user_id for r in rows] == [u1.id]
    assert all(e.event_type != "approver_added" for e in events_for(db, order))


# =========================================================================== #
# SalesManager.remove_approver
# =========================================================================== #

def rma_setup(db, so, u1, u2, **order_overrides):
    """AP(U1, approved True) and AP(U2, False) on SO1, not completed, not locked."""
    order = so(**order_overrides)
    ap1 = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    ap2 = mk_approver(db, order, u2, approved=False)
    return order, ap1, ap2


def test_sm_rma_01__removes_approver_and_logs_event(db, M, w1, so, u1, u2):
    """SM-RMA-01 -- removing an approver deletes its row and logs an event naming the removed approver.
    Rules: R2, R3."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2)
    db.expire_all()
    result = M.remove_approver(db, order.id, u2.id, w1.id, performed_by=u1.id)
    assert result is None
    db.expire_all()
    assert db.get(SalesOrderApprover, ap2.id) is None
    assert db.get(SalesOrderApprover, ap1.id) is not None
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "approver_removed"
    assert ev.description == "Removed Bob Karim as approver"
    assert ev.metadata_json == {"user_id": u2.id, "user_name": "Bob Karim"}
    assert ev.performed_by == u1.id


def test_sm_rma_02__last_approver_can_be_removed(db, M, w1, so, u1):
    """SM-RMA-02 -- the last (even approved) approver can be removed; a null performer is allowed.
    Rules: R2, R3."""
    order = so()
    ap1 = mk_approver(db, order, u1, approved=True, approved_at=datetime(2026, 9, 1, 9, 0, 0))
    db.expire_all()
    M.remove_approver(db, order.id, u1.id, w1.id, performed_by=None)
    db.expire_all()
    assert db.get(SalesOrderApprover, ap1.id) is None
    ev = events_for(db, order)[0]
    assert ev.performed_by is None


def test_sm_rma_03__non_approver_404(db, M, w1, so, u1, u2, u3):
    """SM-RMA-03 -- a user who is not an approver of this order gives 404.
    Rules: R1; Errors row 1."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, order.id, u3.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert_nw(db, before)


def test_sm_rma_04__unknown_or_foreign_order_404(db, M, w1, w2, so, a_x, f_x, u1, u2):
    """SM-RMA-04 -- an unknown order_id and an order of another workspace both give 404.
    Rules: R1; Errors row 1."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, 999999999, u2.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert_nw(db, before)
    sox = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    before2 = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc2:
        M.remove_approver(db, sox.id, u2.id, w1.id, performed_by=u1.id)
    assert exc2.value.status_code == 404
    assert exc2.value.detail == "Approver not found"
    assert_nw(db, before2)


def test_sm_rma_05__not_found_check_runs_before_completion_check(db, M, w1, so, u1, u2, u3):
    """SM-RMA-05 -- a non-approver on a completed order still gives 404, not the completion message (R1 before R4).
    Rules: R1, R4."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2, order_completed=True)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, order.id, u3.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Approver not found"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_rma_06__completed_order_should_block_removal(db, M, w1, so, u1, u2):
    """SM-RMA-06 -- removing an approver from a completed order should be rejected; the row should stay.
    Rules: R4; Errors row 2."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2, order_completed=True)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, order.id, u1.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — order is complete"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_rma_07__locked_order_should_block_removal(db, M, w1, so, u1, u2):
    """SM-RMA-07 -- removing an approver from a financially-locked order should be rejected.
    Rules: R4; Errors row 3."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, order.id, u1.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — invoice is locked"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-737"))
def test_sm_rma_08__completed_check_before_locked_check(db, M, w1, so, u1, u2):
    """SM-RMA-08 -- when both completed and locked, the order-complete message should win.
    Rules: R4."""
    order, ap1, ap2 = rma_setup(db, so, u1, u2, order_completed=True)
    inv = mk_invoice(db, w1, status="confirmed", payment_status="unpaid")
    link_invoice(db, order, inv)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.remove_approver(db, order.id, u2.id, w1.id, performed_by=u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot change approvers — order is complete"
    assert_nw(db, before)


# =========================================================================== #
# SalesManager.set_approval
# =========================================================================== #

def sa_setup(db, so, w1, u1, u2, *, invoice_status="draft", **order_overrides):
    """SO1: order_info_confirmed & items_confirmed True, not completed, linked to INV(<status>,unpaid).
    Approvers: AP(U1, False, null), AP(U2, True, 2026-03-01 10:00)."""
    order_overrides.setdefault("order_info_confirmed", True)
    order_overrides.setdefault("items_confirmed", True)
    order = so(**order_overrides)
    inv = mk_invoice(db, w1, status=invoice_status, payment_status="unpaid")
    link_invoice(db, order, inv)
    ap1 = mk_approver(db, order, u1, approved=False, approved_at=None)
    ap2 = mk_approver(db, order, u2, approved=True, approved_at=datetime(2026, 3, 1, 10, 0, 0))
    return order, inv, ap1, ap2


def test_sm_sa_01__approve_sets_flag_and_logs_event(db, M, w1, so, u1, u2):
    """SM-SA-01 -- approving stamps approved_at and logs an 'approved' event.
    Rules: R5."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    db.expire_all()
    t0 = datetime.utcnow()
    result = M.set_approval(db, order.id, u1.id, w1.id, True)
    t1 = datetime.utcnow()
    assert result.id == ap1.id
    r = reread(db, SalesOrderApprover, ap1.id)
    assert r.approved is True
    assert t0 <= r.approved_at <= t1
    evs = events_for(db, order)
    assert len(evs) == 1
    ev = evs[0]
    assert ev.event_type == "approved"
    assert ev.description == "Approved order"
    assert ev.performed_by == u1.id
    assert ev.metadata_json is None


def test_sm_sa_02__withdraw_clears_flag_and_logs_event(db, M, w1, so, u1, u2):
    """SM-SA-02 -- withdrawing clears approved_at and logs an 'approval_withdrawn' event.
    Rules: R4, R5."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    db.expire_all()
    result = M.set_approval(db, order.id, u2.id, w1.id, False)
    assert result.id == ap2.id
    r = reread(db, SalesOrderApprover, ap2.id)
    assert r.approved is False
    assert r.approved_at is None
    ev = events_for(db, order)[0]
    assert ev.event_type == "approval_withdrawn"
    assert ev.description == "Withdrew approval"
    assert ev.performed_by == u2.id


def test_sm_sa_03__non_approver_forbidden(db, M, w1, so, u1, u2, u3):
    """SM-SA-03 -- a user who is not an assigned approver is forbidden.
    Rules: R1; Errors row 1."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, order.id, u3.id, w1.id, True)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not an assigned approver for this order"
    assert_nw(db, before)


def test_sm_sa_04__foreign_workspace_or_unknown_order_forbidden(db, M, w1, w2, so, u1, u2):
    """SM-SA-04 -- the same workspace's approver row is invisible from another workspace; an unknown order too.
    Rules: R1; Errors row 1."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, order.id, u1.id, w2.id, True)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not an assigned approver for this order"
    with pytest.raises(HTTPException) as exc2:
        M.set_approval(db, 999999999, u1.id, w1.id, True)
    assert exc2.value.status_code == 403
    assert exc2.value.detail == "You are not an assigned approver for this order"
    assert_nw(db, before)


def test_sm_sa_05__approve_requires_both_base_sections(db, M, w1, so, u1, u2):
    """SM-SA-05 -- approving is blocked unless both order_info and items are confirmed.
    Rules: R2; Errors row 2."""
    combos = [(True, False), (False, True), (False, False)]
    for i, (info, items) in enumerate(combos):
        order, inv, ap1, ap2 = sa_setup(
            db, so, w1, u1, u2,
            order_info_confirmed=info, items_confirmed=items,
            sales_order_number=f"SO-2026-sa05-{i}",
        )
        before = nw_snapshot(db)
        with pytest.raises(HTTPException) as exc:
            M.set_approval(db, order.id, u1.id, w1.id, True)
        assert exc.value.status_code == 400
        assert exc.value.detail == "Confirm customer, order details, and items before approving"
        assert_nw(db, before)


def test_sm_sa_06__withdraw_allowed_without_base_sections_confirmed(db, M, w1, so, u1, u2):
    """SM-SA-06 -- withdrawing is never blocked by R2, which applies only to approving.
    Rules: R2."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2, order_info_confirmed=False, items_confirmed=False)
    db.expire_all()
    result = M.set_approval(db, order.id, u2.id, w1.id, False)
    assert result.id == ap2.id
    assert reread(db, SalesOrderApprover, ap2.id).approved is False


def test_sm_sa_07__approve_allowed_when_completed_and_locked(db, M, w1, so, u1, u2):
    """SM-SA-07 -- approving is never blocked by completion or the financial lock.
    Rules: R3."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2, order_completed=True, invoice_status="confirmed")
    db.expire_all()
    result = M.set_approval(db, order.id, u1.id, w1.id, True)
    assert result.id == ap1.id
    assert reread(db, SalesOrderApprover, ap1.id).approved is True
    assert len(events_for(db, order)) == 1


def test_sm_sa_08__withdraw_blocked_when_completed(db, M, w1, so, u1, u2):
    """SM-SA-08 -- withdrawing on a completed order is rejected.
    Rules: R4; Errors row 3."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2, order_completed=True)
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, order.id, u2.id, w1.id, False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot withdraw approval — order is complete"
    assert_nw(db, before)


def test_sm_sa_09__withdraw_blocked_when_locked(db, M, w1, so, u1, u2):
    """SM-SA-09 -- withdrawing on a financially-locked order is rejected.
    Rules: R4; Errors row 4."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2, invoice_status="confirmed")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, order.id, u2.id, w1.id, False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot withdraw approval — invoice is locked"
    assert_nw(db, before)


def test_sm_sa_10__completed_check_before_locked_check(db, M, w1, so, u1, u2):
    """SM-SA-10 -- when both completed and locked, the order-complete message wins.
    Rules: R4."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2, order_completed=True, invoice_status="confirmed")
    before = nw_snapshot(db)
    with pytest.raises(HTTPException) as exc:
        M.set_approval(db, order.id, u2.id, w1.id, False)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot withdraw approval — order is complete"
    assert_nw(db, before)


@pytest.mark.xfail(strict=True, reason=xfail("BUG-009"))
def test_sm_sa_11__reapproving_should_be_noop(db, M, w1, so, u1, u2):
    """SM-SA-11 -- re-approving an already-approved user should not re-stamp approved_at or log a new event.
    Rules: R6."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    db.expire_all()
    result = M.set_approval(db, order.id, u2.id, w1.id, True)
    assert result.id == ap2.id
    assert reread(db, SalesOrderApprover, ap2.id).approved_at == datetime(2026, 3, 1, 10, 0, 0)
    assert events_for(db, order) == []


@pytest.mark.xfail(strict=True, reason=xfail("BUG-009"))
def test_sm_sa_12__re_withdrawing_should_be_noop(db, M, w1, so, u1, u2):
    """SM-SA-12 -- withdrawing from a user who hasn't approved should not log a new event.
    Rules: R6."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    db.expire_all()
    result = M.set_approval(db, order.id, u1.id, w1.id, False)
    assert result.id == ap1.id
    assert events_for(db, order) == []


def test_sm_sa_13__noop_transitions_same_outcome_either_way(db, M, w1, so, u1, u2):
    """SM-SA-13 -- these two particular no-op transitions produce the same observable state today and after BUG-009.
    Rules: R5, R6."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    db.expire_all()
    r1 = M.set_approval(db, order.id, u2.id, w1.id, True)
    assert r1.id == ap2.id
    assert reread(db, SalesOrderApprover, ap2.id).approved is True
    r2 = M.set_approval(db, order.id, u1.id, w1.id, False)
    assert r2.id == ap1.id
    rr = reread(db, SalesOrderApprover, ap1.id)
    assert rr.approved is False
    assert rr.approved_at is None


@pytest.mark.xfail(strict=True, reason=xfail("BUG-720"))
def test_sm_sa_14__locks_approver_and_order_before_insert_event(db, M, w1, so, u1, u2):
    """SM-SA-14 -- approving should lock both the approver row and the order row before logging the event.
    Rules: R7."""
    order, inv, ap1, ap2 = sa_setup(db, so, w1, u1, u2)
    cap = SQLCapture(db.get_bind())
    with cap:
        result = M.set_approval(db, order.id, u1.id, w1.id, True)
    assert result.id == ap1.id
    assert_locks_before_write(cap.statements, ["sales_order_approvers", "sales_orders"], "sales_order_events")


# =========================================================================== #
# SalesManager.log_event
# =========================================================================== #

def test_sm_le_01__logs_event_with_all_fields(db, M, w1, so, u1):
    """SM-LE-01 -- logging an event stores every given field and stamps created_at.
    Rules: R1."""
    order = so()
    t0 = datetime.utcnow()
    result = M.log_event(db, order.id, w1.id, "note_added", "Hello", performed_by=u1.id, metadata={"k": 1})
    t1 = datetime.utcnow()
    assert result.id is not None
    r = reread(db, SalesOrderEvent, result.id)
    assert r.workspace_id == w1.id
    assert r.sales_order_id == order.id
    assert r.event_type == "note_added"
    assert r.description == "Hello"
    assert r.performed_by == u1.id
    assert r.metadata_json == {"k": 1}
    assert t0 <= r.created_at <= t1


def test_sm_le_02__defaults_null_performer_and_metadata(db, M, w1, so):
    """SM-LE-02 -- omitted performed_by/metadata default to null.
    Rules: R1."""
    order = so()
    result = M.log_event(db, order.id, w1.id, "x", "y")
    r = reread(db, SalesOrderEvent, result.id)
    assert r.performed_by is None
    assert r.metadata_json is None


def test_sm_le_03__fifty_char_event_type_stored(db, M, w1, so):
    """SM-LE-03 -- a 50-character event_type is within the column limit and stores fully.
    Rules: R2."""
    order = so()
    result = M.log_event(db, order.id, w1.id, "a" * 50, "y")
    r = reread(db, SalesOrderEvent, result.id)
    assert len(r.event_type) == 50


def test_sm_le_04__fifty_one_char_event_type_raises_dataerror(db, M, w1, so):
    """SM-LE-04 -- a 51-character event_type exceeds the column limit and fails at flush.
    Rules: R2; Errors row 1."""
    order = so()
    with pytest.raises(DataError):
        with db.begin_nested():
            M.log_event(db, order.id, w1.id, "a" * 51, "y")


def test_sm_le_05__unknown_order_raises_integrity_error(db, M, w1):
    """SM-LE-05 -- a non-existent order_id fails the FK constraint at flush.
    Rules: R2; Errors row 1."""
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            M.log_event(db, 999999999, w1.id, "x", "y")


def test_sm_le_06__workspace_not_validated(db, M, w1, w2, so):
    """SM-LE-06 -- the given workspace_id is stored as-is; it is never checked against the order's own.
    Rules: R2."""
    order = so()
    result = M.log_event(db, order.id, w2.id, "x", "y")
    r = reread(db, SalesOrderEvent, result.id)
    assert r.workspace_id == w2.id
    assert r.sales_order_id == order.id


# =========================================================================== #
# SalesManager.list_events
# =========================================================================== #

def test_sm_lev_01__unknown_or_foreign_order_404(db, M, w1, w2, so, a_x, f_x):
    """SM-LEV-01 -- an unknown id and an order of another workspace both give 404.
    Rules: R1; Errors row 1."""
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, 999999999, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Sales order with ID 999999999 not found"
    order = so(workspace_id=w2.id, account_id=a_x.id, factory_id=f_x.id, sales_order_number="SO-2026-900")
    with pytest.raises(HTTPException) as exc2:
        M.list_events(db, order.id, w1.id)
    assert exc2.value.status_code == 404
    assert exc2.value.detail == f"Sales order with ID {order.id} not found"


def test_sm_lev_02__no_events_empty_list(db, M, w1, so):
    """SM-LEV-02 -- an order with no events returns an empty list.
    Rules: R2."""
    order = so()
    assert M.list_events(db, order.id, w1.id) == []


def test_sm_lev_03__ordered_newest_first_tie_by_id(db, M, w1, so, u1, u2):
    """SM-LEV-03 -- events come back newest created_at first, ties broken by the higher id first.
    Rules: R2, R3."""
    order = so()

    def mk_event(created_at, performed_by):
        ev = SalesOrderEvent(
            workspace_id=w1.id, sales_order_id=order.id, event_type="note_added",
            description="x", performed_by=performed_by, created_at=created_at,
        )
        db.add(ev)
        db.flush()
        return ev

    e1 = mk_event(datetime(2026, 9, 1), u1.id)
    e2 = mk_event(datetime(2026, 9, 3), u2.id)
    e3 = mk_event(datetime(2026, 9, 2), None)
    e4 = mk_event(datetime(2026, 9, 3), u1.id)
    db.expire_all()
    result = M.list_events(db, order.id, w1.id)
    assert [e.id for e, _ in result] == [e4.id, e2.id, e3.id, e1.id]
    assert [p.id if p else None for _, p in result] == [u1.id, u2.id, None, u1.id]


def test_sm_lev_04__excludes_other_workspace_and_other_order_events(db, M, w1, w2, so, u1):
    """SM-LEV-04 -- an event tagged with another workspace_id, and an event of a different order, are both excluded.
    Rules: R2."""
    order = so()
    so2 = so(sales_order_number="SO-2026-012")
    e1 = SalesOrderEvent(workspace_id=w1.id, sales_order_id=order.id, event_type="x", description="y", performed_by=u1.id)
    db.add(e1)
    db.flush()
    other_ws_event = SalesOrderEvent(workspace_id=w2.id, sales_order_id=order.id, event_type="x", description="y")
    db.add(other_ws_event)
    other_order_event = SalesOrderEvent(workspace_id=w1.id, sales_order_id=so2.id, event_type="x", description="y")
    db.add(other_order_event)
    db.flush()
    db.expire_all()
    result = M.list_events(db, order.id, w1.id)
    assert [e.id for e, _ in result] == [e1.id]
