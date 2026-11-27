"""Unit tests for app/utils/notification_entity_label.py.

Implements tests/unit/utils/notification_entity_label.cases.md (revision 2),
one test per case (parametrized cases keep one case ID per test function).
Real Postgres session (`db` fixture), nothing mocked (spec: no externals).
"""
import datetime as dt
import itertools
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.enums import InventoryTypeEnum
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.help_ticket import HelpTicket
from app.models.inventory import Inventory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.purchase_order import PurchaseOrder
from app.models.sales_order import SalesOrder
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.work_order import WorkOrder
from app.models.work_order_type import WorkOrderType
from app.utils.notification_entity_label import resolve_notification_entity_label
from tests.unit.factories import make_profile, make_workspace

BUG_200 = "BUG-200: Notification fallback label uses raw `type-id` for most entity types"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "MISSING = 2000000000, an id that no row of any type has"
MISSING = 2000000000

_seq = itertools.count(1)


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "profile/customer/supplier/inventory rows needed only to satisfy
# foreign keys ... are created in the same workspace as the entity".
# One set of FK-only rows per workspace, created lazily and cached on the session.
def _deps(db, ws):
    cache = db.info.setdefault("nel_deps", {})
    if ws.id not in cache:
        n = next(_seq)
        profile = make_profile(db)
        cache[ws.id] = {
            "profile": profile,
            "status": _add(db, Status(workspace_id=ws.id, name=f"Open {n}", comment="fk only")),
            "factory": _add(db, Factory(workspace_id=ws.id, name=f"Factory {n}", abbreviation=f"F{n}")),
            "account": _add(db, Account(workspace_id=ws.id, name=f"Account {n}")),
            "wot": _add(db, WorkOrderType(workspace_id=ws.id, name=f"Type {n}")),
        }
    return cache[ws.id]


def _project(db, ws, name, **kw):
    d = _deps(db, ws)
    return _add(db, Project(workspace_id=ws.id, factory_id=d["factory"].id,
                            name=name, description="fk only", **kw))


def _item(db, ws, *, sku, name):
    return _add(db, Item(workspace_id=ws.id, name=name, name_normalized=name.lower(),
                         unit="pcs", sku=sku))


# Local builder per entity type: make_entity(db, ws, entity_type, label) inserts
# one row of that type whose label field (spec Overview table) is `label` and
# flushes it. For "item" the label is the sku (name passed via `name=`).
def make_entity(db, ws, entity_type, label, **kw):
    d = _deps(db, ws)
    pid, sid, fid = d["profile"].id, d["status"].id, d["factory"].id
    if entity_type == "purchase_order":
        row = PurchaseOrder(workspace_id=ws.id, po_number=label, destination_type="storage",
                            destination_id=fid, current_status_id=sid, created_by=pid)
    elif entity_type == "sales_order":
        row = SalesOrder(workspace_id=ws.id, sales_order_number=label, account_id=d["account"].id,
                         factory_id=fid, current_status_id=sid, created_by=pid)
    elif entity_type == "expense_order":
        row = ExpenseOrder(workspace_id=ws.id, expense_number=label, expense_category="other",
                           created_by=pid)
    elif entity_type == "transfer_order":
        row = TransferOrder(workspace_id=ws.id, transfer_number=label,
                            source_location_type="storage", source_location_id=fid,
                            destination_location_type="storage", destination_location_id=fid,
                            current_status_id=sid, created_by=pid)
    elif entity_type == "work_order":
        row = WorkOrder(workspace_id=ws.id, work_order_number=label, work_order_type_id=d["wot"].id,
                        title="fk only", factory_id=fid)
    elif entity_type == "project":
        return _project(db, ws, label, **kw)
    elif entity_type == "project_component":
        proj = _project(db, ws, f"Parent {next(_seq)}")
        row = ProjectComponent(workspace_id=ws.id, project_id=proj.id, name=label)
    elif entity_type == "machine":
        row = Machine(workspace_id=ws.id, name=label, factory_id=fid)
    elif entity_type == "item":
        return _item(db, ws, sku=label, name=kw.pop("name", "Hex Bolt"))
    elif entity_type == "account_invoice":
        row = AccountInvoice(workspace_id=ws.id, account_id=d["account"].id,
                             invoice_type="receivable", invoice_amount=Decimal("100.00"),
                             invoice_date=dt.date(2026, 9, 1), invoice_number=label)
    elif entity_type == "support_ticket":
        row = HelpTicket(workspace_id=ws.id, ticket_number=label, title="fk only",
                         description="fk only", created_by=pid)
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(entity_type)
    for k, v in kw.items():
        setattr(row, k, v)
    return _add(db, row)


# Convention "Standard label values"
STANDARD_LABEL = {
    "purchase_order": "PO-2026-015",
    "sales_order": "SO-2026-004",
    "expense_order": "EXP-2026-007",
    "transfer_order": "TR-2026-002",
    "work_order": "WO-2026-011",
    "project": "Riverside Tower",
    "project_component": "Foundation Slab",
    "machine": "CNC Lathe 3",
    "item": "SKU-100",  # sku "SKU-100", name "Hex Bolt" -> label "SKU-100"
    "account_invoice": "INV-2026-031",
    "support_ticket": "TKT-0012",
}

# Convention "Type names (R3a)"
TYPE_NAME = {
    "purchase_order": "purchase order",
    "sales_order": "sales order",
    "expense_order": "expense order",
    "transfer_order": "transfer order",
    "work_order": "work order",
    "project": "project",
    "project_component": "project component",
    "machine": "machine",
    "item": "item",
    "account_invoice": "account invoice",
    "support_ticket": "support ticket",
}

ALL_TYPES = list(TYPE_NAME)
NON_ITEM_TYPES = [t for t in ALL_TYPES if t != "item"]


# Convention "Call shape in every case" + "Every case asserts the return value is
# a str (never None) and that no exception is raised".
def call(db, ws_id, entity_type, entity_id):
    result = resolve_notification_entity_label(
        db, workspace_id=ws_id, entity_type=entity_type, entity_id=entity_id
    )
    assert isinstance(result, str)
    return result


def _ids(case_id, types):
    return [pytest.param(t, id=f"{case_id}-{t}") for t in types]


# --------------------------------------------------------------------------- #
# resolve_notification_entity_label
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("entity_type", _ids("NEL-R-01", NON_ITEM_TYPES))
def test_nel_r_01__found_row_returns_standard_label(db, w1, entity_type):
    """NEL-R-01 — a row in W1 yields exactly its label field, per type.
    Rules: R1."""
    row = make_entity(db, w1, entity_type, STANDARD_LABEL[entity_type])
    assert call(db, w1.id, entity_type, row.id) == STANDARD_LABEL[entity_type]


def test_nel_r_02__label_not_trimmed(db, w1):
    """NEL-R-02 — project name with surrounding spaces is returned unchanged.
    Rules: R1."""
    row = make_entity(db, w1, "project", "  Riverside Tower  ")
    assert call(db, w1.id, "project", row.id) == "  Riverside Tower  "


def test_nel_r_03__each_workspace_gets_own_label(db, w1, w2):
    """NEL-R-03 — POs in W1 and W2 each resolve to their own number in their workspace.
    Rules: R1, R3."""
    a = make_entity(db, w1, "purchase_order", "PO-W1-001")
    b = make_entity(db, w2, "purchase_order", "PO-W2-001")
    assert call(db, w1.id, "purchase_order", a.id) == "PO-W1-001"
    assert call(db, w2.id, "purchase_order", b.id) == "PO-W2-001"


def test_nel_r_04__item_label_is_sku(db, w1):
    """NEL-R-04 — item with sku and name returns the sku.
    Rules: R2."""
    row = _item(db, w1, sku="SKU-100", name="Hex Bolt")
    assert call(db, w1.id, "item", row.id) == "SKU-100"


@pytest.mark.parametrize("sku", [
    pytest.param(None, id="NEL-R-05"),
    pytest.param("", id="NEL-R-06"),
])
def test_nel_r_05_06__item_without_sku_uses_name(db, w1, sku):
    """NEL-R-05 / NEL-R-06 — item with NULL / empty sku returns its name.
    Rules: R2."""
    row = _item(db, w1, sku=sku, name="Hex Bolt")
    assert call(db, w1.id, "item", row.id) == "Hex Bolt"


@pytest.mark.parametrize("entity_type", _ids("NEL-R-07", ALL_TYPES))
def test_nel_r_07__missing_id_falls_back_ending_with_id(db, w1, entity_type):
    """NEL-R-07 — unknown id yields a non-empty str ending with the id.
    Rules: R3."""
    result = call(db, w1.id, entity_type, MISSING)
    assert result != ""
    assert result.endswith("2000000000")


@pytest.mark.xfail(strict=True, reason=BUG_200)
@pytest.mark.parametrize("entity_type", _ids("NEL-R-08", ALL_TYPES))
def test_nel_r_08__missing_id_friendly_fallback(db, w1, entity_type):
    """NEL-R-08 — unknown id yields exactly "<type name> #2000000000".
    Rules: R3, R3a [BUG-200]."""
    assert call(db, w1.id, entity_type, MISSING) == f"{TYPE_NAME[entity_type]} #2000000000"


@pytest.mark.parametrize("entity_type", _ids("NEL-R-09", ALL_TYPES))
def test_nel_r_09__other_workspace_row_not_leaked(db, w1, w2, entity_type):
    """NEL-R-09 — a row existing only in W2 is not labelled when asked for W1.
    Rules: R3."""
    row = make_entity(db, w2, entity_type, STANDARD_LABEL[entity_type])
    result = call(db, w1.id, entity_type, row.id)
    assert result != STANDARD_LABEL[entity_type]
    if entity_type == "item":
        assert result != "Hex Bolt"
    assert result != ""
    assert result.endswith(str(row.id))


@pytest.mark.xfail(strict=True, reason=BUG_200)
@pytest.mark.parametrize("entity_type", _ids("NEL-R-10", ALL_TYPES))
def test_nel_r_10__other_workspace_row_friendly_fallback(db, w1, w2, entity_type):
    """NEL-R-10 — a row only in W2 yields exactly "<type name> #<id>" for W1.
    Rules: R3, R3a [BUG-200]."""
    row = make_entity(db, w2, entity_type, STANDARD_LABEL[entity_type])
    assert call(db, w1.id, entity_type, row.id) == f"{TYPE_NAME[entity_type]} #{row.id}"


# NEL-R-11 / NEL-R-12 parameter sets: (entity_type, builder)
_EMPTY_LABEL_ROWS = {
    "a": ("account_invoice", lambda db, ws: make_entity(db, ws, "account_invoice", None)),
    "b": ("account_invoice", lambda db, ws: make_entity(db, ws, "account_invoice", "")),
    "c": ("item", lambda db, ws: _item(db, ws, sku="", name="")),
    "d": ("item", lambda db, ws: _item(db, ws, sku=None, name="")),
    "e": ("project", lambda db, ws: make_entity(db, ws, "project", "")),
}


@pytest.mark.parametrize("variant", [pytest.param(k, id=f"NEL-R-11-{k}") for k in _EMPTY_LABEL_ROWS])
def test_nel_r_11__empty_label_falls_back(db, w1, variant):
    """NEL-R-11 — a found row with empty/NULL label yields a non-empty fallback ending with the id.
    Rules: R4."""
    entity_type, build = _EMPTY_LABEL_ROWS[variant]
    row = build(db, w1)
    result = call(db, w1.id, entity_type, row.id)
    assert result != ""
    assert result is not None
    assert result.endswith(str(row.id))


@pytest.mark.xfail(strict=True, reason=BUG_200)
@pytest.mark.parametrize("variant", [pytest.param(k, id=f"NEL-R-12-{k}") for k in _EMPTY_LABEL_ROWS])
def test_nel_r_12__empty_label_friendly_fallback(db, w1, variant):
    """NEL-R-12 — a found row with empty/NULL label yields exactly "<type name> #<id>".
    Rules: R4, R4a [BUG-200]."""
    entity_type, build = _EMPTY_LABEL_ROWS[variant]
    row = build(db, w1)
    assert call(db, w1.id, entity_type, row.id) == f"{TYPE_NAME[entity_type]} #{row.id}"


@pytest.mark.parametrize("entity_type,label", [
    pytest.param("work_order", "WO-2026-099", id="NEL-R-13-a"),
    pytest.param("project", "Old Depot", id="NEL-R-13-b"),
    pytest.param("machine", "Press 7", id="NEL-R-13-c"),
])
def test_nel_r_13__soft_deleted_row_still_labelled(db, w1, entity_type, label):
    """NEL-R-13 — soft-deleted work order / project / machine still yields its label.
    Rules: R5."""
    row = make_entity(db, w1, entity_type, label, is_deleted=True)
    assert call(db, w1.id, entity_type, row.id) == label


def test_nel_r_14__scratch_falls_back_ending_with_id(db, w1):
    """NEL-R-14 — "scratch" yields a non-empty str ending with the id.
    Rules: R6."""
    result = call(db, w1.id, "scratch", 5)
    assert result != ""
    assert result.endswith("5")


@pytest.mark.xfail(strict=True, reason=BUG_200)
def test_nel_r_15__scratch_friendly_fallback(db, w1):
    """NEL-R-15 — "scratch" yields exactly "scratch #5".
    Rules: R6 [BUG-200]."""
    assert call(db, w1.id, "scratch", 5) == "scratch #5"


def test_nel_r_16__inventory_without_row(db, w1):
    """NEL-R-16 — "inventory" with no row yields "inventory #7".
    Rules: R7."""
    assert call(db, w1.id, "inventory", 7) == "inventory #7"


def test_nel_r_17__inventory_row_is_not_looked_up(db, w1):
    """NEL-R-17 — an existing inventory row still yields "inventory #<id>".
    Rules: R7."""
    # Any valid inventory (Inventory has no name column); per the case, one for
    # an item named "Main Warehouse Stock".
    item = _item(db, w1, sku=None, name="Main Warehouse Stock")
    inv = _add(db, Inventory(workspace_id=w1.id, item_id=item.id,
                             inventory_type=InventoryTypeEnum.STORAGE,
                             factory_id=_deps(db, w1)["factory"].id))
    assert call(db, w1.id, "inventory", inv.id) == f"inventory #{inv.id}"


def test_nel_r_18__unknown_type_underscores_to_spaces(db, w1):
    """NEL-R-18 — unknown "custom_thing" yields "custom thing #9".
    Rules: R8."""
    assert call(db, w1.id, "custom_thing", 9) == "custom thing #9"


def test_nel_r_19__type_match_is_case_sensitive(db, w1):
    """NEL-R-19 — "Purchase_Order" is not a known type: case kept, no lookup.
    Rules: R8."""
    po = make_entity(db, w1, "purchase_order", "PO-2026-015")
    assert call(db, w1.id, "Purchase_Order", po.id) == f"Purchase Order #{po.id}"


def test_nel_r_20__empty_type(db, w1):
    """NEL-R-20 — empty type yields " #4".
    Rules: R8."""
    assert call(db, w1.id, "", 4) == " #4"


def test_nel_r_21__every_underscore_replaced(db, w1):
    """NEL-R-21 — "a__b_c" yields "a  b c #1".
    Rules: R8."""
    assert call(db, w1.id, "a__b_c", 1) == "a  b c #1"


def test_nel_r_22__plain_unknown_type(db, w1):
    """NEL-R-22 — "widget" yields "widget #2".
    Rules: R8."""
    assert call(db, w1.id, "widget", 2) == "widget #2"


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_nel_r_23__never_writes(db, w1):
    """NEL-R-23 — a series of calls leaves the session clean and rows unchanged.
    Rules: R9."""
    po = make_entity(db, w1, "purchase_order", "PO-2026-015")
    item = _item(db, w1, sku="SKU-100", name="Hex Bolt")
    inv = make_entity(db, w1, "account_invoice", None)
    db.flush()
    before = {m: _count(db, m) for m in (PurchaseOrder, Item, AccountInvoice)}

    assert call(db, w1.id, "purchase_order", po.id) == "PO-2026-015"
    r = call(db, w1.id, "purchase_order", MISSING)
    assert r != "" and r.endswith("2000000000")
    assert call(db, w1.id, "item", item.id) == "SKU-100"
    r = call(db, w1.id, "account_invoice", inv.id)
    assert r != "" and r.endswith(str(inv.id))
    assert call(db, w1.id, "inventory", 7) == "inventory #7"
    r = call(db, w1.id, "scratch", 3)
    assert r != "" and r.endswith("3")
    assert call(db, w1.id, "custom_thing", 1) == "custom thing #1"

    assert not db.new
    assert not db.dirty
    assert not db.deleted
    assert {m: _count(db, m) for m in (PurchaseOrder, Item, AccountInvoice)} == before
    db.expire_all()
    assert db.get(PurchaseOrder, po.id).po_number == "PO-2026-015"
    re_item = db.get(Item, item.id)
    assert re_item.sku == "SKU-100"
    assert re_item.name == "Hex Bolt"
    assert db.get(AccountInvoice, inv.id).invoice_number is None
