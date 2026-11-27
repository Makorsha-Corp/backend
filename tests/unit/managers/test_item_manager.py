"""Unit tests for app/managers/item_manager.py.

Implements tests/unit/managers/item_manager.cases.md, one test per case. Real
Postgres session (`db` fixture). Nothing is patched (Conventions, Externals:
None); only the race-simulation card ITM-C-32 patches the manager's own SKU
check, as Conventions allow.

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/managers/item_manager.helpers.md as its only view of this file;
tests below a `# [claude] <ID>` comment are the `Author: claude` cards,
written by hand in the finishing step.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest
from psycopg2.errors import ForeignKeyViolation
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.item_manager import ItemManager, item_manager
from app.models.account import Account
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.models.machine import Machine
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.product import Product
from app.models.production_batch import ProductionBatch
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.models.production_formula_stage import ProductionFormulaStage
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
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_type import WorkOrderType
from app.schemas.item import ItemCreate, ItemUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton item_manager" (a module-level name, not a fixture)
M = item_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the four standing rows W1, W2, U1, U2)
# Each fixture depends on the one before it, so the ids rise in that order.
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 = created_by / assigned_by of every Given row; U2 = the acting user of the calls
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "These four rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts ONE row and flushes, so
# ids rise in the order the Given lines are written)
# --------------------------------------------------------------------------- #

# Item recipes I1, I2, IX (deleted), I9 (W2): name, name_normalized and the columns that differ
_ITEM_RECIPES = {
    "I1": {"name": "Bolt M8", "name_normalized": "bolt m8"},
    "I2": {"name": "Washer Ten", "name_normalized": "washer ten"},
    "IX": {"name": "Old Rivet", "name_normalized": "old rivet", "is_active": False},
    "I9": {"name": "Far Spring", "name_normalized": "far spring", "workspace": "w2"},
}

# Tag recipes T1, T2, K3, TD (deleted), T9 (W2)
_TAG_RECIPES = {
    "T1": {"name": "Spare Part", "tag_code": "spare_part"},
    "T2": {"name": "Galvanized", "tag_code": "galvanized"},
    "K3": {"name": "Zinc Coat", "tag_code": "zinc_coat"},
    "TD": {"name": "Obsolete", "tag_code": "obsolete", "is_active": False},
    "T9": {"name": "Far Crate", "tag_code": "far_crate", "workspace": "w2"},
}


# Convention "item" and the recipes I1, I2, IX, I9
@pytest.fixture
def mk_item(db, w1, w2, u1):
    """mk_item("I1", **but) -> Item for a recipe; mk_item(name=..., name_normalized=..., **but) for a plain "item".

    Defaults: workspace W1, unit "pcs", description / sku None, item_type "physical",
    is_active True, created_by U1, updated_by / updated_at None. Keywords override.
    """
    workspaces = {"w1": w1, "w2": w2}

    def _mk(recipe=None, /, **columns):
        if recipe is not None and recipe not in _ITEM_RECIPES:
            raise TypeError(f"mk_item: {recipe!r} is not a recipe (I1, I2, IX, I9); a plain item is "
                            "mk_item(name=..., name_normalized=...)")
        recipe_cols = dict(_ITEM_RECIPES[recipe]) if recipe is not None else {}
        ws = workspaces[recipe_cols.pop("workspace", "w1")]
        fields = {"workspace_id": ws.id, "unit": "pcs", "description": None, "sku": None,
                  "item_type": "physical", "is_active": True, "created_by": u1.id,
                  "updated_by": None, "updated_at": None}
        fields.update(recipe_cols)
        fields.update(columns)
        return _add(db, Item(**fields))
    return _mk


# Convention "tag" and the recipes T1, T2, K3, TD, T9
@pytest.fixture
def mk_tag(db, w1, w2):
    """mk_tag("T1", **but) -> ItemTag. Defaults: W1, not a system tag, active, usage_count 0, created_by None."""
    workspaces = {"w1": w1, "w2": w2}

    def _mk(recipe, /, **columns):
        recipe_cols = dict(_TAG_RECIPES[recipe])
        ws = workspaces[recipe_cols.pop("workspace", "w1")]
        fields = {"workspace_id": ws.id, "is_system_tag": False, "is_active": True,
                  "usage_count": 0, "created_by": None}
        fields.update(recipe_cols)
        fields.update(columns)
        return _add(db, ItemTag(**fields))
    return _mk


# Convention "link of I to T": workspace_id = I's, assigned_by U1.id, assigned_at left to the model default
@pytest.fixture
def mk_link(db, u1):
    """mk_link(of=<item>, to=<tag>, **but) -> ItemTagAssignment."""
    def _mk(*, of, to, **columns):
        fields = {"workspace_id": of.workspace_id, "item_id": of.id, "tag_id": to.id, "assigned_by": u1.id}
        fields.update(columns)
        return _add(db, ItemTagAssignment(**fields))
    return _mk


# Convention "F1" = factories row: name "Main Plant", abbreviation "MP", created_by U1, W1
@pytest.fixture
def mk_f1(db, w1, u1):
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "name": "Main Plant", "abbreviation": "MP", "created_by": u1.id}
        fields.update(columns)
        return _add(db, Factory(**fields))
    return _mk


# Convention "MC1" = machines row: name "Lathe", factory_id F1.id, W1
@pytest.fixture
def mk_mc1(db, w1):
    def _mk(*, factory, **columns):
        fields = {"workspace_id": w1.id, "name": "Lathe", "factory_id": factory.id}
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "AC1" = accounts row: name "Acme Buyer", W1
@pytest.fixture
def mk_ac1(db, w1):
    def _mk():
        return _add(db, Account(workspace_id=w1.id, name="Acme Buyer"))
    return _mk


# Convention "WT1" = work_order_types row: name "Repair", W1
@pytest.fixture
def mk_wt1(db, w1):
    def _mk():
        return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))
    return _mk


# Convention 'stage "X"' = statuses row: name "X", comment "stage", W1
@pytest.fixture
def mk_stage(db, w1):
    def _mk(name, /):
        return _add(db, Status(workspace_id=w1.id, name=name, comment="stage"))
    return _mk


# Convention "stock of I" = inventory row: factory_id F1.id, STORAGE, is_deleted False, created_by U1; the card gives qty
@pytest.fixture
def mk_stock(db, w1, u1):
    def _mk(*, of, factory, qty, **columns):
        fields = {"workspace_id": w1.id, "item_id": of.id, "factory_id": factory.id, "qty": qty,
                  "inventory_type": InventoryTypeEnum.STORAGE, "is_deleted": False, "created_by": u1.id}
        fields.update(columns)
        return _add(db, Inventory(**fields))
    return _mk


# Convention "machine stock of I" = machine_items row: machine_id MC1.id, req_qty / defective_qty None; the card gives qty
@pytest.fixture
def mk_machine_stock(db, w1):
    def _mk(*, of, machine, qty, **columns):
        fields = {"workspace_id": w1.id, "machine_id": machine.id, "item_id": of.id, "qty": qty,
                  "req_qty": None, "defective_qty": None}
        fields.update(columns)
        return _add(db, MachineItem(**fields))
    return _mk


# Convention "purchase order": po_number "PO-ITM-1", destination storage / F1.id, created_by U1, voided False
@pytest.fixture
def mk_po(db, w1, u1):
    def _mk(*, factory, current_status_id, **columns):
        fields = {"workspace_id": w1.id, "po_number": "PO-ITM-1", "destination_type": "storage",
                  "destination_id": factory.id, "created_by": u1.id, "voided": False,
                  "current_status_id": current_status_id}
        fields.update(columns)
        return _add(db, PurchaseOrder(**fields))
    return _mk


# Convention "sales order": sales_order_number "SO-ITM-1", AC1, F1, created_by U1, order_completed False
@pytest.fixture
def mk_so(db, w1, u1):
    def _mk(*, factory, account, current_status_id, **columns):
        fields = {"workspace_id": w1.id, "sales_order_number": "SO-ITM-1", "account_id": account.id,
                  "factory_id": factory.id, "created_by": u1.id, "order_completed": False,
                  "current_status_id": current_status_id}
        fields.update(columns)
        return _add(db, SalesOrder(**fields))
    return _mk


# Convention "work order": work_order_number "WO-ITM-1", WT1, title "Fix press", F1, is_deleted False; the card gives status
@pytest.fixture
def mk_wo(db, w1):
    def _mk(*, factory, wo_type, status, **columns):
        fields = {"workspace_id": w1.id, "work_order_number": "WO-ITM-1", "work_order_type_id": wo_type.id,
                  "title": "Fix press", "factory_id": factory.id, "is_deleted": False, "status": status}
        fields.update(columns)
        return _add(db, WorkOrder(**fields))
    return _mk


# Convention "transfer order": transfer_number "TR-ITM-1", storage F1 -> storage F1, created_by U1, completed_at None
@pytest.fixture
def mk_to(db, w1, u1):
    def _mk(*, factory, current_status_id, **columns):
        fields = {"workspace_id": w1.id, "transfer_number": "TR-ITM-1",
                  "source_location_type": "storage", "source_location_id": factory.id,
                  "destination_location_type": "storage", "destination_location_id": factory.id,
                  "created_by": u1.id, "completed_at": None, "current_status_id": current_status_id}
        fields.update(columns)
        return _add(db, TransferOrder(**fields))
    return _mk


# Conventions "PO line of I", "SO line of I", "WO line of I", "TO line of I": one builder, the order decides the table
def _line_fields(order, item):
    if isinstance(order, PurchaseOrder):
        return PurchaseOrderItem, {"purchase_order_id": order.id, "line_number": 1, "quantity_ordered": 5}
    if isinstance(order, SalesOrder):
        return SalesOrderItem, {"sales_order_id": order.id, "quantity_ordered": 5, "unit_price": 10, "line_total": 50}
    if isinstance(order, WorkOrder):
        return WorkOrderItem, {"work_order_id": order.id, "quantity": 2, "replaced_item_id": None, "is_deleted": False}
    if isinstance(order, TransferOrder):
        return TransferOrderItem, {"transfer_order_id": order.id, "line_number": 1, "quantity": 3}
    raise TypeError(f"mk_line: order must be a purchase, sales, work or transfer order, not {type(order).__name__}")


@pytest.fixture
def mk_line(db, w1):
    """mk_line(of=<item>, order=<po|so|wo|to>, **but) -> the line row of that order's table."""
    def _mk(*, of, order, **columns):
        model, fields = _line_fields(order, of)
        fields.update(workspace_id=w1.id, item_id=of.id)
        fields.update(columns)
        return _add(db, model(**fields))
    return _mk


# Convention "F9" = F1, but workspace_id W2, name "Far Plant", abbreviation "FP"
@pytest.fixture
def mk_f9(db, w2, u1):
    def _mk(**columns):
        fields = {"workspace_id": w2.id, "name": "Far Plant", "abbreviation": "FP", "created_by": u1.id}
        fields.update(columns)
        return _add(db, Factory(**fields))
    return _mk


# Convention "MC9" = MC1, but workspace_id W2, factory_id F9.id
@pytest.fixture
def mk_mc9(db, w2):
    def _mk(*, factory, **columns):
        fields = {"workspace_id": w2.id, "name": "Lathe", "factory_id": factory.id}
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "AC9" = AC1, but workspace_id W2, name "Far Buyer"
@pytest.fixture
def mk_ac9(db, w2):
    def _mk():
        return _add(db, Account(workspace_id=w2.id, name="Far Buyer"))
    return _mk


# Convention "WT9" = WT1, but workspace_id W2, name "Far Repair"
@pytest.fixture
def mk_wt9(db, w2):
    def _mk():
        return _add(db, WorkOrderType(workspace_id=w2.id, name="Far Repair"))
    return _mk


# Given lines 'stage "X", but workspace_id W2.id'
@pytest.fixture
def mk_st9(db, w2):
    def _mk(name, /):
        return _add(db, Status(workspace_id=w2.id, name=name, comment="stage"))
    return _mk


# Convention "finished stock of I" = products row: factory_id F1.id, not for sale, active, not deleted; the card gives qty
@pytest.fixture
def mk_product(db, w1):
    def _mk(*, of, factory, qty, **columns):
        fields = {"workspace_id": w1.id, "item_id": of.id, "factory_id": factory.id, "qty": qty,
                  "is_available_for_sale": False, "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, Product(**fields))
    return _mk


# Convention "PL1" = production_lines row: factory_id F1.id, name "Line One", W1
@pytest.fixture
def mk_pl1(db, w1):
    def _mk(*, factory):
        return _add(db, ProductionLine(workspace_id=w1.id, factory_id=factory.id, name="Line One"))
    return _mk


# Convention "PL9" = PL1, but workspace_id W2, factory_id F9.id, name "Far Line"
@pytest.fixture
def mk_pl9(db, w2):
    def _mk(*, factory):
        return _add(db, ProductionLine(workspace_id=w2.id, factory_id=factory.id, name="Far Line"))
    return _mk


# Convention "batch" = production_batches row: batch_number "PB-ITM-1", PL1, batch_date 2025-12-01; the card gives status
@pytest.fixture
def mk_batch(db, w1):
    def _mk(*, line, status, **columns):
        fields = {"workspace_id": w1.id, "batch_number": "PB-ITM-1", "production_line_id": line.id,
                  "batch_date": date(2025, 12, 1), "status": status}
        fields.update(columns)
        return _add(db, ProductionBatch(**fields))
    return _mk


# Convention "batch line of I" = production_batch_items row: batch_id = the last batch built, item_role "input"
@pytest.fixture
def mk_batch_line(db, w1):
    """mk_batch_line(of=<item>, batch=<the last batch built>, **but) -> ProductionBatchItem."""
    def _mk(*, of, batch, **columns):
        fields = {"workspace_id": w1.id, "batch_id": batch.id, "item_id": of.id, "item_role": "input"}
        fields.update(columns)
        return _add(db, ProductionBatchItem(**fields))
    return _mk


# Card ITM-D-86: "F1, but is_deleted True, is_active False"
@pytest.fixture
def mk_f1_deleted(db, w1, u1):
    def _mk():
        return _add(db, Factory(workspace_id=w1.id, name="Main Plant", abbreviation="MP", created_by=u1.id, is_deleted=True, is_active=False))
    return _mk


# Card ITM-D-86: "MC1, but is_deleted True, is_active False"
@pytest.fixture
def mk_mc1_deleted(db, w1):
    def _mk(*, factory):
        return _add(db, Machine(workspace_id=w1.id, name="Lathe", factory_id=factory.id, is_deleted=True, is_active=False))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_COUNTED = {"items": Item.__table__, "item_tags": ItemTag.__table__,
            "item_tag_assignments": ItemTagAssignment.__table__}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id from its own table
def reread(db, row):
    """Fresh copy of any Given row (or the returned item) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of any row, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of the named table in all workspaces; filters are column=value (None = IS NULL)
def count_rows(db, table_name, **filters):
    table = _COUNTED[table_name]
    stmt = select(func.count()).select_from(table)
    for column, value in filters.items():
        stmt = stmt.where(table.c[column].is_(None) if value is None else table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": row counts of items, item_tags and item_tag_assignments, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _COUNTED}


# Convention "stored_count(T)"
def stored_count(db, tag):
    return db.scalar(text("select usage_count from item_tags where id = :i"), {"i": _id_of(tag)})


# Convention "links_of(I)": expire_all, then every link row of I (any workspace), ordered by id
def links_of(db, item):
    item_id = _id_of(item)
    db.expire_all()
    a = ItemTagAssignment
    return list(db.execute(select(a).where(a.item_id == item_id).order_by(a.id)).scalars())


# Convention "tag_ids_of(I)"
def tag_ids_of(db, item):
    return sorted(link.tag_id for link in links_of(db, item))


# Convention "the link of I to T": the one row of links_of(I) with tag_id == T.id (None if there is none)
def link_of(db, item, tag):
    tag_id = _id_of(tag)
    found = [link for link in links_of(db, item) if link.tag_id == tag_id]
    return found[0] if len(found) == 1 else None


# Convention "ids(x)": sorted ids (order is never part of a check in this module)
def ids(rows):
    return sorted(r.id for r in rows)


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in item_manager.helpers.md)
# --------------------------------------------------------------------------- #

def test_itm_c_01__create_stores_the_item_with_the_values_sent_in_the_caller_s_workspace(db, w1, u2):
    """ITM-C-01 — create stores the item with the values sent, in the caller's workspace, by the caller.
    Rules: `create_item` R1, R2, Returns"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", description="Zinc plated", sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, Item)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Bolt M8"
    assert row.unit == "pcs"
    # Then 4
    assert row.description == "Zinc plated"
    assert row.sku == "B-M8"
    # Then 5
    assert row.item_type == "physical"
    # Then 6
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    # Then 7
    assert count_rows(db, "items") == 1


@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_11__an_empty_name_is_rejected_by_itemcreate(db):
    """ITM-C-11 — an empty name is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="", unit="pcs")

    # Then 2
    assert count_rows(db, "items") == 0


def test_itm_c_33__the_tags_sent_are_linked_to_the_new_item_and_counted_once_each(db, w1, u2, mk_tag):
    """ITM-C-33 — the tags sent are linked to the new item and counted once each.
    Rules: `create_item` R8; `_assign_tags_to_item` R1"""
    t1 = mk_tag("T1", usage_count=3)
    t2 = mk_tag("T2")

    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id, t2.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert tag_ids_of(db, result) == [t1.id, t2.id]
    # Then 3
    links = links_of(db, result)
    assert all(link.workspace_id == w1.id for link in links)
    assert all(link.assigned_by == u2.id for link in links)
    # Then 4
    assert stored_count(db, t1) == 4
    # Then 5
    assert stored_count(db, t2) == 1


def test_itm_u_33__a_new_tag_list_the_removed_tag_loses_its_link_and_one_count_the_new(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-33 — a new tag list: the removed tag loses its link and one count, the new tag gains both.
    Rules: `update_item` R12 (the parts that hold today); `_assign_tags_to_item` R1"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2", usage_count=6)
    k3 = mk_tag("K3")
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id, k3.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id, k3.id]
    # Then 3
    assert stored_count(db, t2) == 5
    # Then 4
    assert stored_count(db, k3) == 1
    # Then 5
    assert stored_count(db, t1) == 4
    # Then 6
    row = link_of(db, i1, k3)
    assert row.assigned_by == u2.id
    assert row.workspace_id == w1.id


@pytest.mark.xfail(strict=True, reason="BUG-934: Saving an item's tags deletes and re-creates unchanged tag links")
def test_itm_u_34__a_tag_that_stays_keeps_its_link_same_id_same_assigning_user_same_time(db, w1, u1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-34 — a tag that stays keeps its link: same id, same assigning user, same time.
    Rules: `update_item` R12 [BUG-934]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2", usage_count=6)
    k3 = mk_tag("K3")
    l1 = mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    l1_id = l1.id
    l1_at = l1.assigned_at

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id, k3.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id, k3.id]
    # Then 3
    row = link_of(db, i1, t1)
    assert row.id == l1_id
    # Then 4
    assert row.assigned_by == u1.id
    # Then 5
    assert row.assigned_at == l1_at


def test_itm_l_01__the_default_page_holds_the_workspace_s_live_items_only(db, w1, mk_item):
    """ITM-L-01 — the default page holds the workspace's live items only.
    Rules: `list_items_filtered` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    mk_item("IX")
    mk_item("I9")
    before = written(db)

    result = M.list_items_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [i1.id, i2.id]
    # Then 2
    assert written(db) == before


def test_itm_d_06__an_already_deleted_item_is_refused_its_tag_count_and_stamp_stay(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-D-06 — an already deleted item is refused; its tag count and stamp stay.
    Rules: `delete_item` R3, Errors row 3"""
    ix = mk_item("IX")
    t1 = mk_tag("T1", usage_count=3)
    mk_link(of=ix, to=t1)
    before_ix = snap(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=ix.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} is already deleted"
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert snap(db, ix) == before_ix
    # Then 5
    row = reread(db, ix)
    assert row.updated_by is None


def test_itm_d_08__each_active_tag_on_the_item_counts_one_item_less_never_below_0(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-D-08 — each active tag on the item counts one item less, never below 0.
    Rules: `delete_item` R6"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2")
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert stored_count(db, t1) == 3
    # Then 3
    assert stored_count(db, t2) == 0


@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_39__a_line_on_a_sales_order_that_is_not_completed_blocks_the_delete_and(db, w1, u2, mk_item, mk_tag, mk_link, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-39 — a line on a sales order that is not completed blocks the delete and names the order.
    Rules: `delete_item` R9 (d) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    sol = mk_line(of=i1, order=so)
    before_so = snap(db, so)
    before_sol = snap(db, sol)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "sales_order", "id": so.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert row.updated_at is None
    # Then 6
    assert stored_count(db, t1) == 4
    # Then 7
    assert snap(db, so) == before_so
    # Then 8
    assert snap(db, sol) == before_sol
    # Then 9
    assert written(db) == before


# [local-coder] ITM-C-12
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_12__a_name_of_three_spaces_is_rejected_by_itemcreate(db):
    """ITM-C-12 — a name of three spaces is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="   ", unit="pcs")

    # Then 2
    assert count_rows(db, "items") == 0


# [local-coder] ITM-C-38
def test_itm_c_38__a_user_id_that_is_no_profile_id_fails_on_flush_before_any_tag_is(db, w1, mk_tag):
    """ITM-C-38 — a user_id that is no profile id fails on flush before any tag is touched.
    Rules: `create_item` R10, Errors row 5"""
    t1 = mk_tag("T1", usage_count=3)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id]), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "items_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "items") == 0
    # Then 5
    assert count_rows(db, "item_tag_assignments") == 0
    # Then 6
    assert stored_count(db, t1) == 3


# [local-coder] ITM-U-02
def test_itm_u_02__fields_not_sent_and_the_creation_and_state_columns_keep_their_values(db, w1, u1, u2, mk_item):
    """ITM-U-02 — fields not sent and the creation and state columns keep their values.
    Rules: `update_item` R4, R10"""
    i1 = mk_item("I1", description="Zinc plated", sku="B-M8")
    created_before = i1.created_at

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(unit="box"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.unit == "box"
    # Then 3
    assert row.name == "Bolt M8"
    assert row.name_normalized == "bolt m8"
    # Then 4
    assert row.description == "Zinc plated"
    assert row.sku == "B-M8"
    assert row.item_type == "physical"
    # Then 5
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 6
    assert row.created_at == created_before
    # Then 7
    assert row.is_active is True


# [local-coder] ITM-U-40
@pytest.mark.xfail(strict=True, reason="BUG-935: Saving an item's tags erases its links to deleted tags")
def test_itm_u_40__re_sending_a_deleted_tag_the_item_already_carries_is_not_refused_and(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-40 — re-sending a deleted tag the item already carries is not refused and changes nothing for it.
    Rules: `update_item` R13 [BUG-935], R15"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    td = mk_tag("TD", usage_count=7)
    mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=td)
    l2_id = l2.id

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id, td.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = link_of(db, i1, td)
    assert row.id == l2_id
    # Then 3
    assert stored_count(db, td) == 7


# [local-coder] ITM-G-02
def test_itm_g_02__the_positional_call_the_services_use_returns_the_item(db, w1, mk_item):
    """ITM-G-02 — the positional call the services use returns the item.
    Rules: `get_item` R1"""
    i1 = mk_item("I1")

    result = M.get_item(db, i1.id, w1.id)

    # Then 1
    assert result is i1


# [local-coder] ITM-G-06
@pytest.mark.xfail(strict=True, reason="BUG-937: get_item returns deleted items")
def test_itm_g_06__include_deleted_true_returns_a_deleted_item_of_the_workspace(db, w1, mk_item):
    """ITM-G-06 — include_deleted=True returns a deleted item of the workspace.
    Rules: `get_item` R4 [BUG-937]"""
    ix = mk_item("IX")

    result = M.get_item(db, item_id=ix.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is ix
    # Then 2
    row = reread(db, ix)
    assert row.is_active is False


# [local-coder] ITM-L-07
def test_itm_l_07__the_filters_after_the_workspace_are_keyword_only(db, w1, mk_item):
    """ITM-L-07 — the filters after the workspace are keyword-only.
    Rules: `list_items_filtered` signature (Facts for the test designer)"""
    mk_item("I1")

    # Then 1
    with pytest.raises(TypeError):
        M.list_items_filtered(db, w1.id, 0)


# [local-coder] ITM-L-08
def test_itm_l_08__a_negative_limit_is_refused_by_the_database(db, w1, mk_item):
    """ITM-L-08 — a negative limit is refused by the database.
    Rules: `list_items_filtered` Errors"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            M.list_items_filtered(db, workspace_id=w1.id, limit=-1)

    # Then 2
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.is_active is True


# [local-coder] ITM-N-03
def test_itm_n_03__the_unit_and_tag_filters_are_passed_through_to_the_count(db, w1, mk_item, mk_tag, mk_link):
    """ITM-N-03 — the unit and tag filters are passed through to the count.
    Rules: `count_items_filtered` R1"""
    i1 = mk_item("I1", unit="kg")
    mk_item("I2", unit="kg")
    t1 = mk_tag("T1")
    mk_link(of=i1, to=t1)

    result = M.count_items_filtered(db, workspace_id=w1.id, unit="kg", tag_ids=[t1.id])

    # Then 1
    assert result == 1


# [local-coder] ITM-FS-03
def test_itm_fs_03__a_fuzzy_score_of_7_19_is_rounded_to_4_decimals_and_typed_fuzzy(db, w1, mk_item):
    """ITM-FS-03 — a fuzzy score of 7/19 is rounded to 4 decimals and typed fuzzy.
    Rules: `find_similar_items` R3, R4"""
    p = mk_item(name="Pa", name_normalized="abcdefghijklmnopq")

    result = M.find_similar_items(db, workspace_id=w1.id, name="abcdefg")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["id"] == p.id
    # Then 3
    assert result[0]["similarity_score"] == 0.3684
    # Then 4
    assert result[0]["match_type"] == "fuzzy"


# [local-coder] ITM-D-21
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_21__a_line_on_a_work_order_in_status_draft_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-21 — a line on a work order in status DRAFT blocks the delete.
    Rules: `delete_item` R9 (e) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol = mk_line(of=i1, order=wo)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-29
def test_itm_d_29__a_line_on_a_voided_purchase_order_does_not_block_the_delete_even_at(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-29 — a line on a voided purchase order does not block the delete, even at stage "Receiving".
    Rules: `delete_item` R9 (c), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Receiving")
    po = mk_po(factory=f1, current_status_id=st.id, voided=True)
    pol = mk_line(of=i1, order=po)
    before_po = snap(db, po)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, po) == before_po
    # Then 4
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-44
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_44__the_refusal_for_an_open_transfer_order_lists_the_order_not_the_line(db, w1, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line):
    """ITM-D-44 — the refusal for an open transfer order lists the order, not the line.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    mk_line(of=i1, order=to)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-A-07
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_07__one_bad_id_in_the_list_stops_every_link_valid_ids_before_and_after_it(db, w1, u2, mk_item, mk_tag):
    """ITM-A-07 — one bad id in the list stops every link: valid ids before and after it are not linked.
    Rules: `_assign_tags_to_item` R4 [BUG-944]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=3)
    t2 = mk_tag("T2", usage_count=6)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t1.id, MISSING, t2.id], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 999999999 not found"
    # Then 3
    assert links_of(db, i1) == []
    # Then 4
    assert stored_count(db, t1) == 3
    # Then 5
    assert stored_count(db, t2) == 6


# [local-coder] ITM-A-10
def test_itm_a_10__a_tag_already_on_the_item_is_skipped_no_new_link_no_count_change(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-A-10 — a tag already on the item is skipped: no new link, no count change.
    Rules: `_assign_tags_to_item` R5"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2")
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    result = M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t1.id, t2.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert tag_ids_of(db, i1) == [t1.id, t2.id]
    # Then 4
    assert stored_count(db, t1) == 4
    # Then 5
    assert stored_count(db, t2) == 1


# [local-coder] ITM-TI-01
def test_itm_ti_01__the_item_s_active_tags_of_the_workspace_are_returned(db, w1, mk_item, mk_tag, mk_link):
    """ITM-TI-01 — the item's active tags of the workspace are returned.
    Rules: `get_tags_for_item` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    t1 = mk_tag("T1")
    t2 = mk_tag("T2")
    td = mk_tag("TD")
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)
    mk_link(of=i2, to=t2)
    before = written(db)

    result = M.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert written(db) == before


# [local-coder] ITM-TS-01
def test_itm_ts_01__one_key_per_requested_item_each_with_its_active_tags_an_unmatched_id(db, w1, mk_item, mk_tag, mk_link):
    """ITM-TS-01 — one key per requested item, each with its active tags; an unmatched id gets an empty list.
    Rules: `get_tags_for_items` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    t1 = mk_tag("T1")
    t2 = mk_tag("T2")
    td = mk_tag("TD")
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)
    mk_link(of=i2, to=t2)
    before = written(db)

    result = M.get_tags_for_items(db, item_ids=[i1.id, i2.id, MISSING], workspace_id=w1.id)

    # Then 1
    assert set(result.keys()) == {i1.id, i2.id, MISSING}
    # Then 2
    assert ids(result[i1.id]) == [t1.id]
    # Then 3
    assert ids(result[i2.id]) == [t2.id]
    # Then 4
    assert result[MISSING] == []
    # Then 5
    assert written(db) == before


# [local-coder] ITM-U-08
@pytest.mark.xfail(strict=True, reason="BUG-938: Deleted items can still be edited and tagged")
def test_itm_u_08__tags_sent_for_a_deleted_item_are_neither_linked_nor_counted(db, w1, u2, mk_item, mk_tag):
    """ITM-U-08 — tags sent for a deleted item are neither linked nor counted.
    Rules: `update_item` R3 [BUG-938]"""
    ix = mk_item("IX")
    t1 = mk_tag("T1", usage_count=3)
    before_ix = snap(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=ix.id, item_data=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} not found"
    # Then 3
    assert links_of(db, ix) == []
    # Then 4
    assert stored_count(db, t1) == 3
    # Then 5
    assert snap(db, ix) == before_ix


# [local-coder] ITM-UN-01
def test_itm_un_01__the_units_of_the_workspace_s_live_items_once_each_sorted(db, w1, mk_item):
    """ITM-UN-01 — the units of the workspace's live items, once each, sorted.
    Rules: `distinct_units` R1"""
    mk_item("I1")
    mk_item("I2", unit="kg")
    mk_item("IX", unit="box")
    mk_item("I9", unit="ton")
    mk_item(name="Hex Screw", name_normalized="hex screw")
    before = written(db)

    result = M.distinct_units(db, w1.id)

    # Then 1
    assert result == ["kg", "pcs"]
    # Then 2
    assert written(db) == before


# [local-coder] ITM-C-02
def test_itm_c_02__a_new_item_is_live_and_carries_no_update_stamp(db, w1, u2):
    """ITM-C-02 — a new item is live and carries no update stamp.
    Rules: `create_item` R1"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_active is True
    # Then 3
    assert row.created_at is not None
    # Then 4
    assert row.updated_at is None
    assert row.updated_by is None


# [local-coder] ITM-C-03
def test_itm_c_03__description_and_sku_not_sent_are_stored_as_none(db, w1, u2):
    """ITM-C-03 — description and SKU not sent are stored as None.
    Rules: `create_item` R1"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.description is None
    # Then 3
    assert row.sku is None


# [local-coder] ITM-C-04
def test_itm_c_04__an_empty_description_is_stored_as_an_empty_string(db, w1, u2):
    """ITM-C-04 — an empty description is stored as an empty string.
    Rules: `create_item` R1"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", description=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.description == ""


# [local-coder] ITM-C-05
def test_itm_c_05__item_type_service_is_stored_as_sent(db, w1, u2):
    """ITM-C-05 — item type "service" is stored as sent.
    Rules: `create_item` R2"""
    result = M.create_item(db, item_data=ItemCreate(name="Fitting Labour", unit="hour", item_type="service"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_type == "service"
    # Then 3
    assert row.name == "Fitting Labour"
    assert row.unit == "hour"


# [local-coder] ITM-C-06
def test_itm_c_06__the_normalized_name_is_computed_from_the_name(db, w1, u2):
    """ITM-C-06 — the normalized name is computed from the name.
    Rules: `create_item` R5"""
    result = M.create_item(db, item_data=ItemCreate(name="Steel Rod 22 m", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name_normalized == "steel rod 22m"


# [local-coder] ITM-C-07
def test_itm_c_07__a_name_of_only_punctuation_gets_an_empty_normalized_name(db, w1, u2):
    """ITM-C-07 — a name of only punctuation gets an empty normalized name.
    Rules: `create_item` R5"""
    result = M.create_item(db, item_data=ItemCreate(name="!!!", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name_normalized == ""
    # Then 3
    assert row.name == "!!!"


# [local-coder] ITM-C-08
def test_itm_c_08__a_padded_name_still_gets_the_trimmed_collapsed_normalized_name(db, w1, u2):
    """ITM-C-08 — a padded name still gets the trimmed, collapsed normalized name.
    Rules: `create_item` R5"""
    result = M.create_item(db, item_data=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name_normalized == "steel rod 22m"


# [local-coder] ITM-C-09
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_09__the_name_is_stored_trimmed_inner_spaces_kept(db, w1, u2):
    """ITM-C-09 — the name is stored trimmed, inner spaces kept.
    Rules: `create_item` R3 [BUG-936]"""
    result = M.create_item(db, item_data=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Steel  Rod 22 m"


# [local-coder] ITM-C-10
def test_itm_c_10__inner_whitespace_and_case_of_the_name_are_kept(db, w1, u2):
    """ITM-C-10 — inner whitespace and case of the name are kept.
    Rules: `create_item` R1, R3"""
    result = M.create_item(db, item_data=ItemCreate(name="steel  ROD", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "steel  ROD"


# [local-coder] ITM-C-13
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_13__a_name_of_one_tab_is_rejected_by_itemcreate(db):
    """ITM-C-13 — a name of one tab is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="\t", unit="pcs")

    # Then 2
    assert count_rows(db, "items") == 0


# [local-coder] ITM-C-14
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_14__an_empty_unit_is_rejected_by_itemcreate(db):
    """ITM-C-14 — an empty unit is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="Bolt M8", unit="")

    # Then 2
    assert count_rows(db, "items") == 0


# [local-coder] ITM-C-15
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_c_15__a_unit_of_two_spaces_is_rejected_by_itemcreate(db):
    """ITM-C-15 — a unit of two spaces is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="Bolt M8", unit="  ")

    # Then 2
    assert count_rows(db, "items") == 0


# [local-coder] ITM-C-16
def test_itm_c_16__a_one_character_name_and_unit_are_accepted_by_itemcreate():
    """ITM-C-16 — a one-character name and unit are accepted by ItemCreate.
    Rules: `create_item` R3"""
    result = ItemCreate(name="a", unit="m")

    # Then 1
    assert result.name == "a"
    # Then 2
    assert result.unit == "m"


# [local-coder] ITM-C-17
@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_itm_c_17__the_unit_is_stored_trimmed_case_kept(db, w1, u2):
    """ITM-C-17 — the unit is stored trimmed, case kept.
    Rules: `create_item` R4 [BUG-017]"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit=" Kg "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit == "Kg"


# [local-coder] ITM-C-18
def test_itm_c_18__the_case_of_the_unit_is_kept(db, w1, u2):
    """ITM-C-18 — the case of the unit is kept.
    Rules: `create_item` R1, R4"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="Kg"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit == "Kg"


# [local-coder] ITM-C-19
def test_itm_c_19__the_exact_name_of_a_live_item_does_not_block_the_create(db, w1, u2, mk_item):
    """ITM-C-19 — the exact name of a live item does not block the create.
    Rules: `create_item` R6"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != i1.id
    # Then 3
    row = reread(db, result)
    assert row.name == "Bolt M8"
    # Then 4
    assert count_rows(db, "items", workspace_id=w1.id, name="Bolt M8") == 2
    # Then 5
    assert snap(db, i1) == before_i1


# [local-coder] ITM-C-20
def test_itm_c_20__a_name_with_the_same_normalized_form_as_a_live_item_does_not_block(db, w1, u2, mk_item):
    """ITM-C-20 — a name with the same normalized form as a live item does not block the create.
    Rules: `create_item` R5, R6"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    result = M.create_item(db, item_data=ItemCreate(name="BOLT-m8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "BOLT-m8"
    assert row.name_normalized == "bolt m8"
    # Then 3
    assert count_rows(db, "items", name_normalized="bolt m8") == 2
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-C-21
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_21__the_sku_is_stored_trimmed(db, w1, u2):
    """ITM-C-21 — the SKU is stored trimmed.
    Rules: `create_item` R7 [BUG-946]"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku=" B-M8 "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku == "B-M8"


# [local-coder] ITM-C-22
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_22__an_empty_sku_is_stored_as_none(db, w1, u2):
    """ITM-C-22 — an empty SKU is stored as None.
    Rules: `create_item` R7 [BUG-946]"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku=""), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku is None


# [local-coder] ITM-C-23
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_23__a_sku_of_three_spaces_is_stored_as_none(db, w1, u2):
    """ITM-C-23 — a SKU of three spaces is stored as None.
    Rules: `create_item` R7 [BUG-946]"""
    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku is None


# [local-coder] ITM-C-24
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_24__a_sku_used_by_a_live_item_of_the_workspace_is_refused(db, w1, u2, mk_item):
    """ITM-C-24 — a SKU used by a live item of the workspace is refused.
    Rules: `create_item` R7 [BUG-946], Errors row 2"""
    i1 = mk_item("I1", sku="B-M8")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item with SKU 'B-M8' already exists"
    # Then 3
    assert count_rows(db, "items") == 1
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-C-25
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_25__a_sku_that_differs_only_in_case_and_outer_spaces_is_refused_with_the(db, w1, u2, mk_item):
    """ITM-C-25 — a SKU that differs only in case and outer spaces is refused, with the trimmed value in the message.
    Rules: `create_item` R7 [BUG-946], Errors row 2"""
    i1 = mk_item("I1", sku="B-M8")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku=" b-m8 "), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item with SKU 'b-m8' already exists"
    # Then 3
    assert count_rows(db, "items") == 1
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-C-26
def test_itm_c_26__the_sku_of_a_deleted_item_can_be_used_again(db, w1, u2, mk_item):
    """ITM-C-26 — the SKU of a deleted item can be used again.
    Rules: `create_item` R7"""
    ix = mk_item("IX", sku="B-M8")
    before_ix = snap(db, ix)

    result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku == "B-M8"
    assert row.is_active is True
    # Then 3
    assert count_rows(db, "items") == 2
    # Then 4
    assert snap(db, ix) == before_ix


# [local-coder] ITM-C-27
def test_itm_c_27__the_sku_of_another_workspace_s_item_does_not_block_the_create(db, w1, u2, mk_item):
    """ITM-C-27 — the SKU of another workspace's item does not block the create.
    Rules: `create_item` R7"""
    i9 = mk_item("I9", sku="B-M8")
    before_i9 = snap(db, i9)

    result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku == "B-M8"
    assert row.workspace_id == w1.id
    # Then 3
    assert snap(db, i9) == before_i9


# [local-coder] ITM-C-28
def test_itm_c_28__two_items_without_a_sku_can_exist(db, w1, u2, mk_item):
    """ITM-C-28 — two items without a SKU can exist.
    Rules: `create_item` R7"""
    mk_item("I1")

    result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.sku is None
    # Then 3
    assert count_rows(db, "items", sku=None) == 2


# [local-coder] ITM-C-34
def test_itm_c_34__an_empty_tag_list_creates_the_item_without_links(db, w1, u2, mk_tag):
    """ITM-C-34 — an empty tag list creates the item without links.
    Rules: `create_item` R8"""
    t1 = mk_tag("T1", usage_count=3)

    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert links_of(db, result) == []
    # Then 3
    assert stored_count(db, t1) == 3


# [local-coder] ITM-C-35
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_c_35__an_unknown_tag_id_refuses_the_whole_create_and_nothing_is_written(db, w1, u2, mk_tag):
    """ITM-C-35 — an unknown tag id refuses the whole create and nothing is written.
    Rules: `create_item` R9 [BUG-944], Errors row 3; `_assign_tags_to_item` R2, R4"""
    t1 = mk_tag("T1", usage_count=3)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id, MISSING]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 999999999 not found"
    # Then 3
    assert count_rows(db, "items") == 0
    # Then 4
    assert count_rows(db, "item_tag_assignments") == 0
    # Then 5
    assert stored_count(db, t1) == 3


# [local-coder] ITM-C-36
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_c_36__a_tag_of_another_workspace_refuses_the_create_as_not_found(db, w1, u2, mk_tag):
    """ITM-C-36 — a tag of another workspace refuses the create as not found.
    Rules: `create_item` R9 [BUG-944], Errors row 3; `_assign_tags_to_item` R2"""
    t9 = mk_tag("T9", usage_count=2)
    before_t9 = snap(db, t9)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t9.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {t9.id} not found"
    # Then 3
    assert count_rows(db, "items") == 0
    # Then 4
    assert count_rows(db, "item_tag_assignments") == 0
    # Then 5
    assert snap(db, t9) == before_t9


# [local-coder] ITM-C-37
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_itm_c_37__a_deleted_tag_refuses_the_create(db, w1, u2, mk_tag):
    """ITM-C-37 — a deleted tag refuses the create.
    Rules: `create_item` R9 [BUG-943], Errors row 4; `_assign_tags_to_item` R3"""
    td = mk_tag("TD", usage_count=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[td.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {td.id} is not active"
    # Then 3
    assert count_rows(db, "items") == 0
    # Then 4
    assert count_rows(db, "item_tag_assignments") == 0
    # Then 5
    assert stored_count(db, td) == 5


# [local-coder] ITM-C-39
def test_itm_c_39__a_workspace_id_that_is_no_workspace_id_fails_on_flush(db, u2):
    """ITM-C-39 — a workspace_id that is no workspace id fails on flush.
    Rules: `create_item` R10, Errors row 5"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=MISSING, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "items_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "items") == 0


# [local-coder] ITM-U-01
def test_itm_u_01__a_new_name_is_stored_normalized_again_and_the_editor_is_recorded(db, w1, u2, mk_item):
    """ITM-U-01 — a new name is stored, normalized again, and the editor is recorded.
    Rules: `update_item` R4, R5, R9, R10, Returns"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Lock Nut"
    assert row.name_normalized == "lock nut"
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None
    # Then 5
    assert count_rows(db, "items") == 1


# [local-coder] ITM-U-03
def test_itm_u_03__description_sku_and_item_type_sent_with_values_are_written(db, w1, u2, mk_item):
    """ITM-U-03 — description, SKU and item type sent with values are written.
    Rules: `update_item` R4"""
    i1 = mk_item("I1", description="Zinc plated", sku="B-M8")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(description="Hot dipped", sku="HD-1", item_type="service"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.description == "Hot dipped"
    # Then 3
    assert row.sku == "HD-1"
    # Then 4
    assert row.item_type == "service"
    # Then 5
    assert row.name == "Bolt M8"
    assert row.unit == "pcs"


# [local-coder] ITM-U-04
def test_itm_u_04__an_id_that_no_item_has_is_refused_and_nothing_is_written(db, w1, u2, mk_item):
    """ITM-U-04 — an id that no item has is refused and nothing is written.
    Rules: `update_item` R1, Errors row 1"""
    i1 = mk_item("I1")
    before = written(db)
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=MISSING, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item 999999999 not found"
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-05
def test_itm_u_05__an_item_of_another_workspace_is_refused_and_not_changed(db, w1, u2, mk_item):
    """ITM-U-05 — an item of another workspace is refused and not changed.
    Rules: `update_item` R2 (the side that holds today)"""
    i9 = mk_item("I9")
    before_i9 = snap(db, i9)

    # Then 1
    with pytest.raises(ValueError):
        M.update_item(db, item_id=i9.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert snap(db, i9) == before_i9
    # Then 3
    row = reread(db, i9)
    assert row.name == "Far Spring"
    assert row.updated_by is None


# [local-coder] ITM-U-06
@pytest.mark.xfail(strict=True, reason="BUG-941: Other-workspace item reported differently from a missing one")
def test_itm_u_06__an_item_of_another_workspace_gets_the_same_message_as_a_missing_one(db, w1, u2, mk_item):
    """ITM-U-06 — an item of another workspace gets the same message as a missing one.
    Rules: `update_item` R2 [BUG-941], Errors row 1"""
    i9 = mk_item("I9")
    before_i9 = snap(db, i9)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=i9.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {i9.id} not found"
    # Then 3
    assert snap(db, i9) == before_i9


# [local-coder] ITM-U-07
@pytest.mark.xfail(strict=True, reason="BUG-938: Deleted items can still be edited and tagged")
def test_itm_u_07__a_deleted_item_is_refused_as_not_found_and_not_changed(db, w1, u2, mk_item):
    """ITM-U-07 — a deleted item is refused as not found and not changed.
    Rules: `update_item` R3 [BUG-938], Errors row 1"""
    ix = mk_item("IX")
    before_ix = snap(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=ix.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} not found"
    # Then 3
    assert snap(db, ix) == before_ix
    # Then 4
    row = reread(db, ix)
    assert row.name == "Old Rivet"
    assert row.updated_by is None


# [local-coder] ITM-U-09
def test_itm_u_09__sending_the_current_name_repairs_a_stale_normalized_name(db, w1, u2, mk_item):
    """ITM-U-09 — sending the current name repairs a stale normalized name.
    Rules: `update_item` R5"""
    i1 = mk_item("I1", name_normalized="stale")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    # Then 3
    assert row.name_normalized == "bolt m8"


# [local-coder] ITM-U-10
def test_itm_u_10__a_stale_normalized_name_is_kept_when_the_name_is_not_sent(db, w1, u2, mk_item):
    """ITM-U-10 — a stale normalized name is kept when the name is not sent.
    Rules: `update_item` R5"""
    i1 = mk_item("I1", name_normalized="stale")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(unit="box"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.unit == "box"
    # Then 3
    assert row.name_normalized == "stale"


# [local-coder] ITM-U-11
def test_itm_u_11__inner_spaces_and_punctuation_of_a_new_name_are_kept_the_normalized(db, w1, u2, mk_item):
    """ITM-U-11 — inner spaces and punctuation of a new name are kept; the normalized name collapses them.
    Rules: `update_item` R4, R5"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="New  Name-2"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "New  Name-2"
    # Then 3
    assert row.name_normalized == "new name 2"


# [local-coder] ITM-U-12
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_u_12__a_sent_name_is_stored_trimmed(db, w1, u2, mk_item):
    """ITM-U-12 — a sent name is stored trimmed.
    Rules: `update_item` R6 [BUG-936], R5"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="  Lock Nut "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name_normalized == "lock nut"
    # Then 3
    assert row.name == "Lock Nut"


# [local-coder] ITM-U-13
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_u_13__an_empty_name_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-13 — an empty name is rejected by ItemUpdate.
    Rules: `update_item` R6 [BUG-936], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(name="")

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-14
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_u_14__a_name_of_three_spaces_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-14 — a name of three spaces is rejected by ItemUpdate.
    Rules: `update_item` R6 [BUG-936], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(name="   ")

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-15
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_u_15__an_empty_unit_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-15 — an empty unit is rejected by ItemUpdate.
    Rules: `update_item` R6 [BUG-936], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(unit="")

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-16
@pytest.mark.xfail(strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed")
def test_itm_u_16__a_unit_of_one_tab_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-16 — a unit of one tab is rejected by ItemUpdate.
    Rules: `update_item` R6 [BUG-936], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(unit="\t")

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-17
@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_itm_u_17__a_sent_unit_is_stored_trimmed_case_kept(db, w1, u2, mk_item):
    """ITM-U-17 — a sent unit is stored trimmed, case kept.
    Rules: `update_item` R6a [BUG-017]"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(unit=" Kg "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.unit == "Kg"


# [local-coder] ITM-U-18
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_itm_u_18__an_explicit_null_clears_the_description(db, w1, u2, mk_item):
    """ITM-U-18 — an explicit null clears the description.
    Rules: `update_item` R7 [BUG-942]"""
    i1 = mk_item("I1", description="Zinc plated")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(description=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.description is None


# [local-coder] ITM-U-19
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_itm_u_19__an_explicit_null_clears_the_sku(db, w1, u2, mk_item):
    """ITM-U-19 — an explicit null clears the SKU.
    Rules: `update_item` R7 [BUG-942], R18"""
    i1 = mk_item("I1", sku="OLD-12")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(sku=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.sku is None


# [local-coder] ITM-U-20
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_itm_u_20__an_explicit_null_name_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-20 — an explicit null name is rejected by ItemUpdate.
    Rules: `update_item` R7 [BUG-942], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(name=None)

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-21
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_itm_u_21__an_explicit_null_unit_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-21 — an explicit null unit is rejected by ItemUpdate.
    Rules: `update_item` R7 [BUG-942], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(unit=None)

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-22
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_itm_u_22__an_explicit_null_item_type_is_rejected_by_itemupdate(db, mk_item):
    """ITM-U-22 — an explicit null item type is rejected by ItemUpdate.
    Rules: `update_item` R7 [BUG-942], Errors row 3"""
    i1 = mk_item("I1")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValidationError):
        ItemUpdate(item_type=None)

    # Then 2
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-23
@pytest.mark.xfail(strict=True, reason="BUG-947: Item edit request can delete / restore an item, bypassing tag counters")
def test_itm_u_23__is_active_sent_with_the_edit_is_ignored_the_item_stays_live(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-23 — is_active sent with the edit is ignored: the item stays live.
    Rules: `update_item` R8 [BUG-947]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Lock Nut", is_active=False), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Lock Nut"
    # Then 3
    assert row.is_active is True
    # Then 4
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-24
@pytest.mark.xfail(strict=True, reason="BUG-947: Item edit request can delete / restore an item, bypassing tag counters")
def test_itm_u_24__itemupdate_has_no_is_active_field_a_sent_value_is_dropped():
    """ITM-U-24 — ItemUpdate has no is_active field: a sent value is dropped.
    Rules: `update_item` R8 [BUG-947]"""
    result = ItemUpdate(is_active=False)

    # Then 1
    assert hasattr(result, "is_active") is False


# [local-coder] ITM-U-25
@pytest.mark.xfail(strict=True, reason="BUG-938: Deleted items can still be edited and tagged")
def test_itm_u_25__is_active_true_does_not_bring_a_deleted_item_back(db, w1, u2, mk_item):
    """ITM-U-25 — is_active true does not bring a deleted item back.
    Rules: `update_item` R3 [BUG-938], R8 [BUG-947]"""
    ix = mk_item("IX")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=ix.id, item_data=ItemUpdate(is_active=True), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} not found"
    # Then 3
    row = reread(db, ix)
    assert row.is_active is False


# [local-coder] ITM-U-26
@pytest.mark.xfail(strict=True, reason="BUG-939: updated_by stamped on no-op item updates")
def test_itm_u_26__an_empty_update_writes_nothing_and_leaves_the_stamp_empty(db, w1, u2, mk_item):
    """ITM-U-26 — an empty update writes nothing and leaves the stamp empty.
    Rules: `update_item` R9 [BUG-939]"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.updated_by is None
    # Then 3
    assert row.updated_at is None


# [local-coder] ITM-U-27
@pytest.mark.xfail(strict=True, reason="BUG-939: updated_by stamped on no-op item updates")
def test_itm_u_27__values_equal_to_the_current_ones_do_not_stamp_the_item(db, w1, u2, mk_item):
    """ITM-U-27 — values equal to the current ones do not stamp the item.
    Rules: `update_item` R9 [BUG-939]"""
    i1 = mk_item("I1")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.unit == "pcs"
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] ITM-U-28
@pytest.mark.xfail(strict=True, reason="BUG-939: updated_by stamped on no-op item updates")
def test_itm_u_28__re_sending_the_current_tag_set_does_not_stamp_the_item(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-28 — re-sending the current tag set does not stamp the item.
    Rules: `update_item` R9 [BUG-939], R12"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 3
    row = reread(db, i1)
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] ITM-U-29
@pytest.mark.xfail(strict=True, reason="BUG-939: updated_by stamped on no-op item updates")
def test_itm_u_29__repairing_a_stale_normalized_name_alone_does_not_stamp_the_item(db, w1, u2, mk_item):
    """ITM-U-29 — repairing a stale normalized name alone does not stamp the item.
    Rules: `update_item` R9 [BUG-939], R5"""
    i1 = mk_item("I1", name_normalized="stale")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name_normalized == "bolt m8"
    # Then 3
    assert row.updated_by is None


# [local-coder] ITM-U-30
def test_itm_u_30__an_empty_update_by_the_user_already_stamped_writes_nothing(db, w1, u2, mk_item):
    """ITM-U-30 — an empty update by the user already stamped writes nothing.
    Rules: `update_item` R9 (the side that holds today)"""
    i1 = mk_item("I1", updated_by=u2.id, updated_at=T0)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.updated_by == u2.id
    # Then 3
    assert row.updated_at == T0
    # Then 4
    assert row.name == "Bolt M8"


# [local-coder] ITM-U-31
def test_itm_u_31__tag_ids_not_sent_leaves_the_links_and_counts_alone(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-31 — tag_ids not sent leaves the links and counts alone.
    Rules: `update_item` R11"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(unit="box"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 4
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-32
def test_itm_u_32__tag_ids_sent_as_null_leaves_the_links_and_counts_alone(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-32 — tag_ids sent as null leaves the links and counts alone.
    Rules: `update_item` R11, R7"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(unit="box", tag_ids=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-35
@pytest.mark.xfail(strict=True, reason="BUG-934: Saving an item's tags deletes and re-creates unchanged tag links")
def test_itm_u_35__a_staying_tag_whose_count_is_0_keeps_the_count_0(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-35 — a staying tag whose count is 0 keeps the count 0.
    Rules: `update_item` R12 [BUG-934]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1")
    mk_link(of=i1, to=t1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert stored_count(db, t1) == 0
    # Then 3
    assert tag_ids_of(db, i1) == [t1.id]


# [local-coder] ITM-U-36
def test_itm_u_36__a_removed_tag_whose_count_is_0_stays_at_0(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-36 — a removed tag whose count is 0 stays at 0.
    Rules: `update_item` R12, R14"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1")
    mk_link(of=i1, to=t1)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert links_of(db, i1) == []
    # Then 3
    assert stored_count(db, t1) == 0


# [local-coder] ITM-U-37
def test_itm_u_37__an_empty_tag_list_removes_every_link_to_an_active_tag_and_counts_each(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-37 — an empty tag list removes every link to an active tag and counts each one less.
    Rules: `update_item` R14"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2", usage_count=6)
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert links_of(db, i1) == []
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert stored_count(db, t2) == 5


# [local-coder] ITM-U-38
@pytest.mark.xfail(strict=True, reason="BUG-935: Saving an item's tags erases its links to deleted tags")
def test_itm_u_38__a_tag_save_keeps_the_item_s_link_to_a_deleted_tag(db, w1, u1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-38 — a tag save keeps the item's link to a deleted tag.
    Rules: `update_item` R13 [BUG-935]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    td = mk_tag("TD", usage_count=7)
    mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=td)
    l2_id = l2.id

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id, td.id]
    # Then 3
    row = link_of(db, i1, td)
    assert row.id == l2_id
    assert row.assigned_by == u1.id


# [local-coder] ITM-U-39
def test_itm_u_39__a_tag_save_does_not_change_the_count_of_a_deleted_tag_on_the_item(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-39 — a tag save does not change the count of a deleted tag on the item.
    Rules: `update_item` R13 (the side that holds today)"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    td = mk_tag("TD", usage_count=7)
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert stored_count(db, td) == 7
    # Then 3
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-41
@pytest.mark.xfail(strict=True, reason="BUG-935: Saving an item's tags erases its links to deleted tags")
def test_itm_u_41__an_empty_tag_list_keeps_the_link_to_a_deleted_tag(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-41 — an empty tag list keeps the link to a deleted tag.
    Rules: `update_item` R14 [BUG-935]"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=7)
    mk_link(of=i1, to=td)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [td.id]
    # Then 3
    assert stored_count(db, td) == 7


# [local-coder] ITM-U-42
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_u_42__an_unknown_tag_id_refuses_the_whole_update_fields_links_and_counts(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-42 — an unknown tag id refuses the whole update: fields, links and counts stay.
    Rules: `update_item` R15 [BUG-944], Errors row 5"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Lock Nut", tag_ids=[MISSING]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 999999999 not found"
    # Then 3
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.updated_by is None
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-43
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_itm_u_43__a_deleted_tag_newly_added_refuses_the_whole_update(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-43 — a deleted tag newly added refuses the whole update.
    Rules: `update_item` R15 [BUG-943], Errors row 5"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    td = mk_tag("TD", usage_count=7)
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id, td.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {td.id} is not active"
    # Then 3
    assert snap(db, l1) == before_l1
    # Then 4
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 5
    assert stored_count(db, td) == 7
    # Then 6
    assert stored_count(db, t1) == 4


# [local-coder] ITM-U-44
def test_itm_u_44__a_user_id_that_is_no_profile_id_fails_on_flush_and_the_item_keeps_its(db, w1, mk_item):
    """ITM-U-44 — a user_id that is no profile id fails on flush and the item keeps its name.
    Rules: `update_item` R16, Errors row 6"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "items_updated_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.updated_by is None


# [local-coder] ITM-U-46
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_u_46__a_sku_used_by_another_live_item_is_refused(db, w1, u2, mk_item):
    """ITM-U-46 — a SKU used by another live item is refused.
    Rules: `update_item` R18 [BUG-946], Errors row 4"""
    i1 = mk_item("I1", sku="B-M8")
    i2 = mk_item("I2", sku="W-10")
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_item(db, item_id=i2.id, item_data=ItemUpdate(sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item with SKU 'B-M8' already exists"
    # Then 3
    row_i2 = reread(db, i2)
    assert row_i2.sku == "W-10"
    assert row_i2.updated_by is None
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-U-47
def test_itm_u_47__re_sending_the_item_s_own_sku_never_conflicts(db, w1, u2, mk_item):
    """ITM-U-47 — re-sending the item's own SKU never conflicts.
    Rules: `update_item` R18"""
    i1 = mk_item("I1", sku="B-M8")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(sku="B-M8", unit="box"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.sku == "B-M8"
    assert row.unit == "box"


# [local-coder] ITM-U-48
def test_itm_u_48__changing_only_the_case_of_the_item_s_own_sku_is_stored(db, w1, u2, mk_item):
    """ITM-U-48 — changing only the case of the item's own SKU is stored.
    Rules: `update_item` R18"""
    i1 = mk_item("I1", sku="B-M8")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(sku="b-m8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.sku == "b-m8"


# [local-coder] ITM-U-49
def test_itm_u_49__the_sku_of_a_deleted_item_can_be_taken_by_an_update(db, w1, u2, mk_item):
    """ITM-U-49 — the SKU of a deleted item can be taken by an update.
    Rules: `update_item` R18"""
    ix = mk_item("IX", sku="B-M8")
    i1 = mk_item("I1")
    before_ix = snap(db, ix)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.sku == "B-M8"
    # Then 3
    assert snap(db, ix) == before_ix


# [local-coder] ITM-U-50
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_u_50__a_sku_of_three_spaces_clears_the_sku(db, w1, u2, mk_item):
    """ITM-U-50 — a SKU of three spaces clears the SKU.
    Rules: `update_item` R18 [BUG-946]"""
    i1 = mk_item("I1", sku="B-M8")

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(sku="   "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.sku is None


# [local-coder] ITM-U-51
def test_itm_u_51__a_rename_to_the_name_of_another_live_item_is_accepted(db, w1, u2, mk_item):
    """ITM-U-51 — a rename to the name of another live item is accepted.
    Rules: `update_item` R19"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    before_i1 = snap(db, i1)

    result = M.update_item(db, item_id=i2.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i2
    # Then 2
    row = reread(db, i2)
    assert row.name == "Bolt M8"
    assert row.name_normalized == "bolt m8"
    # Then 3
    assert snap(db, i1) == before_i1


# [local-coder] ITM-G-01
def test_itm_g_01__a_live_item_of_the_workspace_is_returned_and_nothing_is_written(db, w1, mk_item):
    """ITM-G-01 — a live item of the workspace is returned and nothing is written.
    Rules: `get_item` R1, R5, Returns"""
    i1 = mk_item("I1")
    mk_item("I2")
    before = written(db)
    before_i1 = snap(db, i1)

    result = M.get_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is i1
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, i1) == before_i1


# [local-coder] ITM-G-03
def test_itm_g_03__an_id_that_no_item_has_gives_none(db, w1, mk_item):
    """ITM-G-03 — an id that no item has gives None.
    Rules: `get_item` R2"""
    mk_item("I1")
    before = written(db)

    result = M.get_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [local-coder] ITM-G-04
def test_itm_g_04__an_item_of_another_workspace_gives_none(db, w1, mk_item):
    """ITM-G-04 — an item of another workspace gives None.
    Rules: `get_item` R2"""
    i9 = mk_item("I9")
    before_i9 = snap(db, i9)

    result = M.get_item(db, item_id=i9.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, i9) == before_i9


# [local-coder] ITM-G-05
@pytest.mark.xfail(strict=True, reason="BUG-937: get_item returns deleted items")
def test_itm_g_05__a_deleted_item_gives_none_by_default(db, w1, mk_item):
    """ITM-G-05 — a deleted item gives None by default.
    Rules: `get_item` R3 [BUG-937]"""
    ix = mk_item("IX")
    before_ix = snap(db, ix)

    result = M.get_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, ix) == before_ix


# [local-coder] ITM-G-07
@pytest.mark.xfail(strict=True, reason="BUG-937: get_item returns deleted items")
def test_itm_g_07__include_deleted_true_still_gives_none_for_another_workspace_s_item(db, w1, mk_item):
    """ITM-G-07 — include_deleted=True still gives None for another workspace's item.
    Rules: `get_item` R4 [BUG-937]"""
    i9 = mk_item("I9", is_active=False)

    result = M.get_item(db, item_id=i9.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is None


# [local-coder] ITM-G-08
@pytest.mark.xfail(strict=True, reason="BUG-937: get_item returns deleted items")
def test_itm_g_08__include_deleted_true_returns_a_live_item_too(db, w1, mk_item):
    """ITM-G-08 — include_deleted=True returns a live item too.
    Rules: `get_item` R4 [BUG-937], R1"""
    i1 = mk_item("I1")

    result = M.get_item(db, item_id=i1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is i1


# [local-coder] ITM-L-02
def test_itm_l_02__the_search_filter_is_passed_through(db, w1, mk_item):
    """ITM-L-02 — the search filter is passed through.
    Rules: `list_items_filtered` R1"""
    mk_item("I1")
    i2 = mk_item("I2")

    result = M.list_items_filtered(db, workspace_id=w1.id, search="Washer")

    # Then 1
    assert ids(result) == [i2.id]


# [local-coder] ITM-L-03
def test_itm_l_03__the_unit_filter_is_passed_through(db, w1, mk_item):
    """ITM-L-03 — the unit filter is passed through.
    Rules: `list_items_filtered` R1"""
    mk_item("I1")
    i2 = mk_item("I2", unit="kg")

    result = M.list_items_filtered(db, workspace_id=w1.id, unit="kg")

    # Then 1
    assert ids(result) == [i2.id]


# [local-coder] ITM-L-04
def test_itm_l_04__the_tag_filter_is_passed_through(db, w1, mk_item, mk_tag, mk_link):
    """ITM-L-04 — the tag filter is passed through.
    Rules: `list_items_filtered` R1"""
    i1 = mk_item("I1")
    mk_item("I2")
    t1 = mk_tag("T1")
    mk_link(of=i1, to=t1)

    result = M.list_items_filtered(db, workspace_id=w1.id, tag_ids=[t1.id])

    # Then 1
    assert ids(result) == [i1.id]


# [local-coder] ITM-L-05
def test_itm_l_05__limit_is_passed_through(db, w1, mk_item):
    """ITM-L-05 — limit is passed through.
    Rules: `list_items_filtered` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")

    result = M.list_items_filtered(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in (i1.id, i2.id)


# [local-coder] ITM-L-06
def test_itm_l_06__skip_is_passed_through(db, w1, mk_item):
    """ITM-L-06 — skip is passed through.
    Rules: `list_items_filtered` R1"""
    mk_item("I1")
    mk_item("I2")

    result = M.list_items_filtered(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] ITM-N-01
def test_itm_n_01__the_count_covers_the_workspace_s_live_items_only(db, w1, mk_item):
    """ITM-N-01 — the count covers the workspace's live items only.
    Rules: `count_items_filtered` R1"""
    mk_item("I1")
    mk_item("I2")
    mk_item("IX")
    mk_item("I9")
    before = written(db)

    result = M.count_items_filtered(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 2
    # Then 3
    assert written(db) == before


# [local-coder] ITM-N-02
def test_itm_n_02__the_search_filter_is_passed_through_to_the_count(db, w1, mk_item):
    """ITM-N-02 — the search filter is passed through to the count.
    Rules: `count_items_filtered` R1"""
    mk_item("I1")
    mk_item("I2")

    result = M.count_items_filtered(db, workspace_id=w1.id, search="Washer")

    # Then 1
    assert result == 1


# [local-coder] ITM-UN-02
def test_itm_un_02__a_workspace_without_items_gives_an_empty_list(db, w2, mk_item):
    """ITM-UN-02 — a workspace without items gives an empty list.
    Rules: `distinct_units` R1"""
    mk_item("I1")

    result = M.distinct_units(db, w2.id)

    # Then 1
    assert result == []


# [local-coder] ITM-FS-01
def test_itm_fs_01__an_exact_normalized_match_comes_back_as_a_dict_with_score_1_0_and(db, w1, mk_item):
    """ITM-FS-01 — an exact normalized match comes back as a dict with score 1.0 and type exact.
    Rules: `find_similar_items` R1, R2, R3, R4, R5"""
    mk_item(name="Steel Rod 22m", name_normalized="steel rod 22m", unit="m", sku="SR-22")
    before = written(db)

    result = M.find_similar_items(db, workspace_id=w1.id, name="steel rod 22 M")

    # Then 1
    assert isinstance(result, list)
    assert len(result) == 1
    # Then 2
    assert set(result[0].keys()) == {"id", "name", "unit", "sku", "similarity_score", "match_type"}
    # Then 3
    assert result[0]["name"] == "Steel Rod 22m"
    assert result[0]["unit"] == "m"
    assert result[0]["sku"] == "SR-22"
    # Then 4
    assert isinstance(result[0]["similarity_score"], float)
    assert result[0]["similarity_score"] == 1.0
    # Then 5
    assert result[0]["match_type"] == "exact_normalized"
    # Then 6
    assert written(db) == before


# [local-coder] ITM-FS-02
def test_itm_fs_02__the_id_key_holds_the_item_s_id(db, w1, mk_item):
    """ITM-FS-02 — the id key holds the item's id.
    Rules: `find_similar_items` R2"""
    s1 = mk_item(name="Steel Rod 22m", name_normalized="steel rod 22m")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Steel Rod 22m")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["id"] == s1.id


# [local-coder] ITM-FS-04
@pytest.mark.xfail(strict=True, reason="BUG-034: Similarity score of exactly 0.35 excluded")
def test_itm_fs_04__a_score_of_7_20_is_included_and_rounded_to_0_35(db, w1, mk_item):
    """ITM-FS-04 — a score of 7/20 is included and rounded to 0.35.
    Rules: `find_similar_items` R3; item DAO `find_similar_by_name_in_workspace` [BUG-034]"""
    mk_item(name="Qa", name_normalized="abcdefghijklmnopqr")

    result = M.find_similar_items(db, workspace_id=w1.id, name="abcdefg")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["similarity_score"] == 0.35
    # Then 3
    assert result[0]["match_type"] == "fuzzy"


# [local-coder] ITM-FS-05
def test_itm_fs_05__a_stale_normalized_name_is_judged_by_the_stored_value_not_equal_means(db, w1, mk_item):
    """ITM-FS-05 — a stale normalized name is judged by the stored value: not equal means fuzzy.
    Rules: `find_similar_items` R4"""
    mk_item(name="Steel Rod", name_normalized="steel rods")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Steel Rod")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["match_type"] == "fuzzy"
    # Then 3
    assert result[0]["similarity_score"] < 1.0


# [local-coder] ITM-FS-06
def test_itm_fs_06__the_stored_name_comes_back_untrimmed(db, w1, mk_item):
    """ITM-FS-06 — the stored name comes back untrimmed.
    Rules: `find_similar_items` R2"""
    mk_item(name="  Steel Rod 22m ", name_normalized="steel rod 22m")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Steel Rod 22m")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["name"] == "  Steel Rod 22m "


# [local-coder] ITM-FS-07
def test_itm_fs_07__a_proposed_name_shorter_than_3_normalized_characters_gives_an_empty(db, w1, mk_item):
    """ITM-FS-07 — a proposed name shorter than 3 normalized characters gives an empty list.
    Rules: `find_similar_items` R1"""
    mk_item(name="AB", name_normalized="ab")

    result = M.find_similar_items(db, workspace_id=w1.id, name="ab")

    # Then 1
    assert result == []


# [local-coder] ITM-FS-08
def test_itm_fs_08__the_excluded_item_is_left_out(db, w1, mk_item):
    """ITM-FS-08 — the excluded item is left out.
    Rules: `find_similar_items` R1"""
    i1 = mk_item("I1")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Bolt M8", exclude_item_id=i1.id)

    # Then 1
    assert result == []


# [local-coder] ITM-FS-09
def test_itm_fs_09__deleted_items_and_items_of_another_workspace_are_not_matched(db, w1, mk_item):
    """ITM-FS-09 — deleted items and items of another workspace are not matched.
    Rules: `find_similar_items` R1"""
    mk_item("IX", name="Bolt M8", name_normalized="bolt m8")
    mk_item("I9", name="Bolt M8", name_normalized="bolt m8")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Bolt M8")

    # Then 1
    assert result == []


# [local-coder] ITM-FS-10
def test_itm_fs_10__limit_0_gives_an_empty_list(db, w1, mk_item):
    """ITM-FS-10 — limit 0 gives an empty list.
    Rules: `find_similar_items` R1"""
    mk_item("I1")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Bolt M8", limit=0)

    # Then 1
    assert result == []


# [local-coder] ITM-D-01
def test_itm_d_01__a_live_item_is_marked_deleted_by_the_acting_user(db, w1, u2, mk_item):
    """ITM-D-01 — a live item is marked deleted by the acting user.
    Rules: `delete_item` R4, Returns"""
    i1 = mk_item("I1")

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None
    # Then 5
    assert count_rows(db, "items") == 1


# [local-coder] ITM-D-02
def test_itm_d_02__no_other_column_of_the_item_is_changed_by_the_delete(db, w1, u1, u2, mk_item):
    """ITM-D-02 — no other column of the item is changed by the delete.
    Rules: `delete_item` R4"""
    i1 = mk_item("I1", description="Zinc plated", sku="B-M8", item_type="service")
    created_before = i1.created_at

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.name_normalized == "bolt m8"
    assert row.unit == "pcs"
    # Then 3
    assert row.description == "Zinc plated"
    assert row.sku == "B-M8"
    assert row.item_type == "service"
    # Then 4
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 5
    assert row.created_at == created_before


# [local-coder] ITM-D-03
def test_itm_d_03__an_id_that_no_item_has_is_refused_and_nothing_is_written(db, w1, u2, mk_item):
    """ITM-D-03 — an id that no item has is refused and nothing is written.
    Rules: `delete_item` R1, Errors row 1"""
    i1 = mk_item("I1")
    before = written(db)
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item 999999999 not found"
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, i1) == before_i1


# [local-coder] ITM-D-04
def test_itm_d_04__an_item_of_another_workspace_is_refused_and_stays_live(db, w1, u2, mk_item):
    """ITM-D-04 — an item of another workspace is refused and stays live.
    Rules: `delete_item` R2 (the side that holds today)"""
    i9 = mk_item("I9")
    before_i9 = snap(db, i9)

    # Then 1
    with pytest.raises(ValueError):
        M.delete_item(db, item_id=i9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert snap(db, i9) == before_i9
    # Then 3
    row = reread(db, i9)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-D-05
@pytest.mark.xfail(strict=True, reason="BUG-941: Other-workspace item reported differently from a missing one")
def test_itm_d_05__an_item_of_another_workspace_gets_the_same_message_as_a_missing_one(db, w1, u2, mk_item):
    """ITM-D-05 — an item of another workspace gets the same message as a missing one.
    Rules: `delete_item` R2 [BUG-941], Errors row 1"""
    i9 = mk_item("I9")
    before_i9 = snap(db, i9)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {i9.id} not found"
    # Then 3
    assert snap(db, i9) == before_i9


# [local-coder] ITM-D-07
def test_itm_d_07__the_item_s_tag_links_are_kept_unchanged(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-D-07 — the item's tag links are kept, unchanged.
    Rules: `delete_item` R5"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2", usage_count=6)
    l1 = mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=t2)
    before_l1 = snap(db, l1)
    before_l2 = snap(db, l2)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert snap(db, l2) == before_l2
    # Then 4
    assert tag_ids_of(db, i1) == [t1.id, t2.id]


# [local-coder] ITM-D-09
@pytest.mark.xfail(strict=True, reason="BUG-945: Deleting an item leaves its deleted tags counting it")
def test_itm_d_09__a_deleted_tag_on_the_item_also_counts_one_item_less(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-D-09 — a deleted tag on the item also counts one item less.
    Rules: `delete_item` R7 [BUG-945]"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=9)
    mk_link(of=i1, to=td)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert stored_count(db, td) == 8
    # Then 3
    assert tag_ids_of(db, i1) == [td.id]


# [local-coder] ITM-D-10
def test_itm_d_10__an_item_without_links_is_deleted_and_no_count_changes(db, w1, u2, mk_item, mk_tag):
    """ITM-D-10 — an item without links is deleted and no count changes.
    Rules: `delete_item` R8"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=3)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    # Then 3
    assert stored_count(db, t1) == 3


# [local-coder] ITM-D-11
def test_itm_d_11__a_user_id_that_is_no_profile_id_fails_on_flush_the_item_stays_live(db, w1, mk_item, mk_tag, mk_link):
    """ITM-D-11 — a user_id that is no profile id fails on flush; the item stays live and no count changes.
    Rules: `delete_item` R10, Errors row 6"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "items_updated_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert stored_count(db, t1) == 4


# [local-coder] ITM-D-14
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_14__stock_in_a_factory_blocks_the_delete_and_nothing_is_written(db, w1, u2, mk_item, mk_tag, mk_link, mk_f1, mk_stock):
    """ITM-D-14 — stock in a factory blocks the delete and nothing is written.
    Rules: `delete_item` R9 (a) [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=400)
    before_sk = snap(db, sk)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert stored_count(db, t1) == 4
    # Then 6
    assert snap(db, sk) == before_sk
    # Then 7
    assert written(db) == before


# [local-coder] ITM-D-15
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_15__damaged_stock_in_a_factory_also_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-15 — damaged stock in a factory also blocks the delete.
    Rules: `delete_item` R9 (a) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=3, inventory_type=InventoryTypeEnum.DAMAGED)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-16
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_16__a_negative_stock_quantity_also_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-16 — a negative stock quantity also blocks the delete.
    Rules: `delete_item` R9 (a) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=-2)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-18
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_18__a_line_on_a_purchase_order_at_stage_draft_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-18 — a line on a purchase order at stage "Draft" blocks the delete.
    Rules: `delete_item` R9 (c) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-19
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_19__a_line_on_a_purchase_order_at_stage_planning_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-19 — a line on a purchase order at stage "Planning" blocks the delete.
    Rules: `delete_item` R9 (c) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Planning")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-20
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_20__a_line_on_a_purchase_order_at_stage_receiving_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-20 — a line on a purchase order at stage "Receiving" blocks the delete.
    Rules: `delete_item` R9 (c) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Receiving")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    before_po = snap(db, po)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, po) == before_po
    # Then 5
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-22
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_22__a_line_on_a_work_order_in_status_in_progress_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_wo, mk_wt1, mk_line):
    """ITM-D-22 — a line on a work order in status IN_PROGRESS blocks the delete.
    Rules: `delete_item` R9 (e) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="IN_PROGRESS")
    wol = mk_line(of=i1, order=wo)
    before_wo = snap(db, wo)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, wo) == before_wo
    # Then 5
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-23
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_23__being_the_replaced_item_of_a_line_on_an_open_work_order_blocks_the(db, w1, u2, mk_item, mk_f1, mk_wo, mk_wt1, mk_line):
    """ITM-D-23 — being the replaced item of a line on an open work order blocks the delete.
    Rules: `delete_item` R9 (e) [BUG-948]"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="IN_PROGRESS")
    wol = mk_line(of=i2, order=wo, replaced_item_id=i1.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-24
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_24__a_line_on_a_transfer_order_that_is_not_completed_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line):
    """ITM-D-24 — a line on a transfer order that is not completed blocks the delete.
    Rules: `delete_item` R9 (f) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    tol = mk_line(of=i1, order=to)
    before_tol = snap(db, tol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, tol) == before_tol


# [local-coder] ITM-D-25
def test_itm_d_25__a_factory_stock_row_with_quantity_0_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-25 — a factory stock row with quantity 0 does not block the delete.
    Rules: `delete_item` R9 (a), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=0)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-26
def test_itm_d_26__a_soft_deleted_factory_stock_row_does_not_block_the_delete_whatever(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-26 — a soft-deleted factory stock row does not block the delete, whatever its quantity.
    Rules: `delete_item` R9 (a), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=400, is_deleted=True)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-27
def test_itm_d_27__machine_stock_with_quantity_0_does_not_block_the_delete_whatever_the(db, w1, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-27 — machine stock with quantity 0 does not block the delete, whatever the required and defective quantities.
    Rules: `delete_item` R9 (b), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=0, req_qty=10, defective_qty=2)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [local-coder] ITM-D-28
def test_itm_d_28__a_line_on_a_purchase_order_at_stage_complete_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-28 — a line on a purchase order at stage "Complete" does not block the delete.
    Rules: `delete_item` R9 (c), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Complete")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-30
def test_itm_d_30__a_line_on_a_completed_sales_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-30 — a line on a completed sales order does not block the delete.
    Rules: `delete_item` R9 (d), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id, order_completed=True)
    sol = mk_line(of=i1, order=so)
    before_sol = snap(db, sol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sol) == before_sol


# [local-coder] ITM-D-31
def test_itm_d_31__a_line_on_a_completed_work_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_wo, mk_wt1, mk_line):
    """ITM-D-31 — a line on a COMPLETED work order does not block the delete.
    Rules: `delete_item` R9 (e), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="COMPLETED")
    wol = mk_line(of=i1, order=wo)
    before_wol = snap(db, wol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-32
def test_itm_d_32__a_line_on_a_voided_work_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_wo, mk_wt1, mk_line):
    """ITM-D-32 — a line on a VOIDED work order does not block the delete.
    Rules: `delete_item` R9 (e), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="VOIDED")
    wol = mk_line(of=i1, order=wo)
    before_wol = snap(db, wol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-34
def test_itm_d_34__a_removed_line_on_a_draft_work_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_wo, mk_wt1, mk_line):
    """ITM-D-34 — a removed line on a DRAFT work order does not block the delete.
    Rules: `delete_item` R9 (e), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol = mk_line(of=i1, order=wo, is_deleted=True)
    before_wol = snap(db, wol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, wol) == before_wol


# [local-coder] ITM-D-35
def test_itm_d_35__a_line_on_a_completed_transfer_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line):
    """ITM-D-35 — a line on a completed transfer order does not block the delete.
    Rules: `delete_item` R9 (f), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id, completed_at=T0)
    tol = mk_line(of=i1, order=to)
    before_to = snap(db, to)
    before_tol = snap(db, tol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, to) == before_to
    # Then 4
    assert snap(db, tol) == before_tol


# [local-coder] ITM-D-36
def test_itm_d_36__an_already_deleted_item_with_stock_gets_the_already_deleted_message(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-36 — an already deleted item with stock gets the "already deleted" message.
    Rules: `delete_item` R9 (checked after R3), R3"""
    ix = mk_item("IX")
    f1 = mk_f1()
    sk = mk_stock(of=ix, factory=f1, qty=5)
    before_ix = snap(db, ix)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=ix.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} is already deleted"
    # Then 3
    assert snap(db, ix) == before_ix
    # Then 4
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-37
def test_itm_d_37__stock_of_another_item_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-37 — stock of another item does not block the delete.
    Rules: `delete_item` R9 (a), R9a"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f1 = mk_f1()
    sk = mk_stock(of=i2, factory=f1, qty=400)
    before_i2 = snap(db, i2)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, i2) == before_i2
    # Then 4
    assert snap(db, sk) == before_sk


# [local-coder] ITM-D-38
def test_itm_d_38__an_open_purchase_order_line_of_another_item_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-38 — an open purchase order line of another item does not block the delete.
    Rules: `delete_item` R9 (c), R9a"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f1 = mk_f1()
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i2, order=po)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pol) == before_pol


# [local-coder] ITM-D-40
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_40__the_refusal_for_factory_stock_lists_exactly_that_stock_row(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-40 — the refusal for factory stock lists exactly that stock row.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=400)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert len(exc.value.args) == 2
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-D-41
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_41__the_refusal_for_machine_stock_lists_exactly_that_machine_row(db, w1, u2, mk_item, mk_f1, mk_machine_stock, mk_mc1):
    """ITM-D-41 — the refusal for machine stock lists exactly that machine row.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "machine_stock", "id": ms.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-D-42
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_42__the_refusal_for_an_open_purchase_order_lists_the_order_not_the_line(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-42 — the refusal for an open purchase order lists the order, not the line.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Receiving")
    po = mk_po(factory=f1, current_status_id=st.id)
    mk_line(of=i1, order=po)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-D-43
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_43__the_refusal_for_an_open_work_order_lists_the_order_not_the_line(db, w1, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-43 — the refusal for an open work order lists the order, not the line.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="IN_PROGRESS")
    mk_line(of=i1, order=wo)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "work_order", "id": wo.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [local-coder] ITM-D-45
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_45__two_blockers_of_different_types_are_both_listed_factory_stock_before(db, w1, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line, mk_stock):
    """ITM-D-45 — two blockers of different types are both listed, factory stock before transfer order.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    tol = mk_line(of=i1, order=to)
    sk = mk_stock(of=i1, factory=f1, qty=400)
    before_sk = snap(db, sk)
    before_tol = snap(db, tol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk.id}, {"type": "transfer_order", "id": to.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk
    # Then 6
    assert snap(db, tol) == before_tol


# [local-coder] ITM-D-46
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_46__a_purchase_order_with_two_lines_of_the_item_is_listed_once(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-46 — a purchase order with two lines of the item is listed once.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol1 = mk_line(of=i1, order=po)
    pol2 = mk_line(of=i1, order=po, line_number=2)
    before_pol1 = snap(db, pol1)
    before_pol2 = snap(db, pol2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pol1) == before_pol1
    # Then 5
    assert snap(db, pol2) == before_pol2


# [local-coder] ITM-A-01
def test_itm_a_01__each_requested_active_tag_is_linked_by_the_acting_user_and_counted(db, w1, u2, mk_item, mk_tag):
    """ITM-A-01 — each requested active tag is linked by the acting user and counted once.
    Rules: `_assign_tags_to_item` R1, R7, Returns"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=3)
    t2 = mk_tag("T2")

    result = M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t1.id, t2.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id, t2.id]
    # Then 3
    links = links_of(db, i1)
    assert all(link.workspace_id == w1.id for link in links)
    assert all(link.assigned_by == u2.id for link in links)
    # Then 4
    assert all(link.assigned_at is not None for link in links)
    # Then 5
    assert stored_count(db, t1) == 4
    # Then 6
    assert stored_count(db, t2) == 1


# [local-coder] ITM-A-02
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_02__an_unknown_tag_id_is_refused_as_not_found(db, w1, u2, mk_item):
    """ITM-A-02 — an unknown tag id is refused as not found.
    Rules: `_assign_tags_to_item` R2 [BUG-944], Errors row 1"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[MISSING], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 999999999 not found"
    # Then 3
    assert links_of(db, i1) == []


# [local-coder] ITM-A-03
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_03__tag_id_0_is_refused_as_not_found(db, w1, u2, mk_item):
    """ITM-A-03 — tag id 0 is refused as not found.
    Rules: `_assign_tags_to_item` R2 [BUG-944], Errors row 1"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[0], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 0 not found"
    # Then 3
    assert links_of(db, i1) == []


# [local-coder] ITM-A-04
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_04__a_negative_tag_id_is_refused_as_not_found(db, w1, u2, mk_item):
    """ITM-A-04 — a negative tag id is refused as not found.
    Rules: `_assign_tags_to_item` R2 [BUG-944], Errors row 1"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[-1], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag -1 not found"
    # Then 3
    assert links_of(db, i1) == []


# [local-coder] ITM-A-05
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_05__a_tag_of_another_workspace_is_refused_as_not_found_and_stays_uncounted(db, w1, u2, mk_item, mk_tag):
    """ITM-A-05 — a tag of another workspace is refused as not found and stays uncounted.
    Rules: `_assign_tags_to_item` R2 [BUG-944], Errors row 1"""
    i1 = mk_item("I1")
    t9 = mk_tag("T9", usage_count=2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t9.id], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {t9.id} not found"
    # Then 3
    assert links_of(db, i1) == []
    # Then 4
    assert stored_count(db, t9) == 2


# [local-coder] ITM-A-06
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_itm_a_06__a_deleted_tag_not_yet_on_the_item_is_refused(db, w1, u2, mk_item, mk_tag):
    """ITM-A-06 — a deleted tag not yet on the item is refused.
    Rules: `_assign_tags_to_item` R3 [BUG-943], Errors row 2"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[td.id], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {td.id} is not active"
    # Then 3
    assert links_of(db, i1) == []
    # Then 4
    assert stored_count(db, td) == 5


# [local-coder] ITM-A-08
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_itm_a_08__the_error_names_the_first_rejected_id_unknown_before_deleted(db, w1, u2, mk_item, mk_tag):
    """ITM-A-08 — the error names the first rejected id: unknown before deleted.
    Rules: `_assign_tags_to_item` R4 [BUG-944]"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[MISSING, td.id], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item tag 999999999 not found"
    # Then 3
    assert links_of(db, i1) == []
    # Then 4
    assert stored_count(db, td) == 5


# [local-coder] ITM-A-09
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_itm_a_09__the_error_names_the_first_rejected_id_deleted_before_unknown(db, w1, u2, mk_item, mk_tag):
    """ITM-A-09 — the error names the first rejected id: deleted before unknown.
    Rules: `_assign_tags_to_item` R4 [BUG-943]"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=5)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[td.id, MISSING], workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item tag {td.id} is not active"
    # Then 3
    assert links_of(db, i1) == []
    # Then 4
    assert stored_count(db, td) == 5


# [local-coder] ITM-A-11
def test_itm_a_11__a_deleted_tag_already_on_the_item_is_skipped_without_an_error(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-A-11 — a deleted tag already on the item is skipped without an error.
    Rules: `_assign_tags_to_item` R5"""
    i1 = mk_item("I1")
    td = mk_tag("TD", usage_count=7)
    l2 = mk_link(of=i1, to=td)
    before_l2 = snap(db, l2)

    result = M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[td.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, l2) == before_l2
    # Then 3
    assert tag_ids_of(db, i1) == [td.id]
    # Then 4
    assert stored_count(db, td) == 7


# [local-coder] ITM-A-12
def test_itm_a_12__the_same_id_twice_is_linked_once_and_counted_once(db, w1, u2, mk_item, mk_tag):
    """ITM-A-12 — the same id twice is linked once and counted once.
    Rules: `_assign_tags_to_item` R6"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=3)

    result = M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t1.id, t1.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 3
    assert stored_count(db, t1) == 4


# [local-coder] ITM-TI-02
def test_itm_ti_02__a_deleted_item_s_tags_are_still_returned(db, w1, mk_item, mk_tag, mk_link):
    """ITM-TI-02 — a deleted item's tags are still returned.
    Rules: `get_tags_for_item` R1"""
    ix = mk_item("IX")
    t1 = mk_tag("T1")
    mk_link(of=ix, to=t1)

    result = M.get_tags_for_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [local-coder] ITM-TS-02
def test_itm_ts_02__an_empty_id_list_gives_an_empty_dict(db, w1, mk_item):
    """ITM-TS-02 — an empty id list gives an empty dict.
    Rules: `get_tags_for_items` R1"""
    mk_item("I1")

    result = M.get_tags_for_items(db, item_ids=[], workspace_id=w1.id)

    # Then 1
    assert result == {}


# --------------------------------------------------------------------------- #
# Finishing step (hand-written): the `Author: claude` cards and the cards the
# local model escalated
# --------------------------------------------------------------------------- #

def _commit_spy(db, monkeypatch):
    """Convention "rolled back": wrap db.commit (still callable) and record the calls."""
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# [claude] ITM-C-29
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_29__the_database_refuses_a_second_live_item_with_the_same_sku(db, w1, u1, mk_item):
    """ITM-C-29 — the database refuses a second live item with the same SKU in a workspace.
    Rules: `create_item` R7 [BUG-946]"""
    mk_item("I1", sku="B-M8")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Item(workspace_id=w1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="B-M8", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "items") == 1


# [claude] ITM-C-30
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_30__the_database_refuses_a_live_sku_differing_only_in_case_and_outer_spaces(db, w1, u1, mk_item):
    """ITM-C-30 — the database refuses a second live item whose SKU differs only in case and outer spaces.
    Rules: `create_item` R7 [BUG-946]"""
    mk_item("I1", sku="B-M8")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Item(workspace_id=w1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="b-m8 ", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "items") == 1


# [claude] ITM-C-31
def test_itm_c_31__the_database_accepts_a_deleted_item_with_the_sku_of_a_live_one(db, w1, u1, mk_item):
    """ITM-C-31 — the database accepts a deleted item with the SKU of a live one.
    Rules: `create_item` R7"""
    i1 = mk_item("I1", sku="B-M8")
    before_i1 = snap(db, i1)

    db.add(Item(workspace_id=w1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="B-M8", is_active=False, created_by=u1.id))
    db.flush()

    # Then 1
    assert count_rows(db, "items") == 2
    # Then 2
    assert snap(db, i1) == before_i1


# [claude] ITM-C-32
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_itm_c_32__a_duplicate_sku_past_the_python_check_gets_the_manager_s_error(db, w1, u2, mk_item):
    """ITM-C-32 — a duplicate SKU that passed the Python check is answered with the manager's error, not a database error.
    Rules: `create_item` R7 [BUG-946], Errors row 2"""
    i1 = mk_item("I1", sku="B-M8")
    before_i1 = snap(db, i1)

    # Race simulation (Conventions): the SKU-existence check reports "free". Its name is
    # not in the spec yet (Spec gap 3), hence create=True; revise with the fix.
    with patch.object(ItemManager, "_check_sku_exists", create=True, return_value=False):
        # Then 1
        with pytest.raises(ValueError) as exc:
            with db.begin_nested():
                M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == "Item with SKU 'B-M8' already exists"
    # Then 3
    assert count_rows(db, "items") == 1
    # Then 4
    assert snap(db, i1) == before_i1


# [claude] ITM-C-40
def test_itm_c_40__the_create_is_flushed_not_committed_a_rollback_removes_it(db, w1, u2, mk_tag, monkeypatch):
    """ITM-C-40 — the create is flushed but not committed: a rollback removes the item, its link and the count.
    Rules: `create_item` R11, Returns, Side effects"""
    t1 = mk_tag("T1", usage_count=3)
    sp = db.begin_nested()
    commit_spy = _commit_spy(db, monkeypatch)

    M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert count_rows(db, "items") == 1
    # Then 2
    assert stored_count(db, t1) == 4

    sp.rollback()

    # Then 3
    assert count_rows(db, "items") == 0
    # Then 4
    assert count_rows(db, "item_tag_assignments") == 0
    # Then 5
    assert stored_count(db, t1) == 3
    # Then 6
    commit_spy.assert_not_called()


# [claude] ITM-U-45
def test_itm_u_45__the_update_is_flushed_not_committed_a_rollback_restores_it(db, w1, u2, mk_item, mk_tag, mk_link, monkeypatch):
    """ITM-U-45 — the update is flushed but not committed: a rollback restores the row, the links and the counts.
    Rules: `update_item` R17, Returns, Side effects"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    k3 = mk_tag("K3")
    mk_link(of=i1, to=t1)
    sp = db.begin_nested()
    commit_spy = _commit_spy(db, monkeypatch)

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(name="Lock Nut", tag_ids=[k3.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.name == "Lock Nut"
    # Then 3
    assert tag_ids_of(db, i1) == [k3.id]

    sp.rollback()

    # Then 4
    row = reread(db, i1)
    assert row.name == "Bolt M8"
    assert row.updated_by is None
    # Then 5
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 6
    assert stored_count(db, t1) == 4
    assert stored_count(db, k3) == 0
    # Then 7
    commit_spy.assert_not_called()


# [claude] ITM-D-12
def test_itm_d_12__the_delete_is_flushed_not_committed_a_rollback_makes_the_item_live(db, w1, u2, mk_item, mk_tag, mk_link, monkeypatch):
    """ITM-D-12 — the delete is flushed but not committed: a rollback makes the item live again and restores the count.
    Rules: `delete_item` R11, Returns"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    sp = db.begin_nested()
    commit_spy = _commit_spy(db, monkeypatch)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    # Then 3
    assert stored_count(db, t1) == 3

    sp.rollback()

    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert stored_count(db, t1) == 4
    # Then 6
    commit_spy.assert_not_called()


# [claude] ITM-D-13
def test_itm_d_13__a_deleted_item_leaves_list_and_count_and_a_second_delete_is_refused(db, w1, u2, mk_item):
    """ITM-D-13 — after the delete the item leaves the catalog list and count, and a second delete is refused.
    Rules: `delete_item` R12, R3; `list_items_filtered` R1; `count_items_filtered` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert ids(M.list_items_filtered(db, workspace_id=w1.id)) == [i2.id]
    # Then 3
    assert M.count_items_filtered(db, workspace_id=w1.id) == 1
    # Then 4
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    assert str(exc.value) == f"Item {i1.id} is already deleted"


# [claude] ITM-A-13
def test_itm_a_13__links_and_counts_are_flushed_but_not_committed(db, w1, u2, mk_item, mk_tag, monkeypatch):
    """ITM-A-13 — links and counts are flushed but not committed.
    Rules: `_assign_tags_to_item` R7"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=3)
    sp = db.begin_nested()
    commit_spy = _commit_spy(db, monkeypatch)

    result = M._assign_tags_to_item(db, item_id=i1.id, tag_ids=[t1.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id]
    # Then 3
    assert stored_count(db, t1) == 4

    sp.rollback()

    # Then 4
    assert links_of(db, i1) == []
    # Then 5
    assert stored_count(db, t1) == 3
    # Then 6
    commit_spy.assert_not_called()


# [claude] ITM-FS-11  (escalated by the local model)
def test_itm_fs_11__a_negative_limit_is_refused_by_the_database(db, w1, mk_item):
    """ITM-FS-11 — a negative limit is refused by the database.
    Rules: `find_similar_items` R1, Errors"""
    i1 = mk_item("I1")

    # Then 1
    with pytest.raises(DataError):
        with db.begin_nested():
            M.find_similar_items(db, workspace_id=w1.id, name="Bolt M8", limit=-1)

    # Then 2
    row = reread(db, i1)
    assert row.name == "Bolt M8"


# [claude] ITM-D-17  (escalated by the local model)
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_17__stock_on_a_machine_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-17 — stock on a machine blocks the delete.
    Rules: `delete_item` R9 (b) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    before_ms = snap(db, ms)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, ms) == before_ms


# [claude] ITM-D-33  (escalated by the local model)
def test_itm_d_33__a_line_on_a_soft_deleted_draft_work_order_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-33 — a line on a soft-deleted DRAFT work order does not block the delete.
    Rules: `delete_item` R9 (e), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT", is_deleted=True)
    wol = mk_line(of=i1, order=wo)
    before_wo = snap(db, wo)
    before_wol = snap(db, wol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, wo) == before_wo
    # Then 4
    assert snap(db, wol) == before_wol


# [claude] ITM-D-47  (escalated by the local model)
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_47__two_blocking_stock_rows_in_one_factory_are_two_entries_by_id(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-47 — two blocking stock rows in one factory are two entries, by id.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk1 = mk_stock(of=i1, factory=f1, qty=400)
    sk2 = mk_stock(of=i1, factory=f1, qty=3, inventory_type=InventoryTypeEnum.DAMAGED)
    before_sk1 = snap(db, sk1)
    before_sk2 = snap(db, sk2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk1.id}, {"type": "factory_stock", "id": sk2.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, sk1) == before_sk1
    # Then 5
    assert snap(db, sk2) == before_sk2


# [claude] ITM-L-09
def test_itm_l_09__without_a_limit_the_page_holds_100_items(db, w1, mk_item):
    """ITM-L-09 — without a limit the page holds 100 items.
    Rules: `list_items_filtered` R1 (default `limit=100`)"""
    for n in range(101):
        mk_item(name=f"Part {n:03d}", name_normalized=f"part {n:03d}")

    result = M.list_items_filtered(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] ITM-FS-12
def test_itm_fs_12__without_a_limit_at_most_5_matches_come_back(db, w1, mk_item):
    """ITM-FS-12 — without a limit at most 5 matches come back.
    Rules: `find_similar_items` R1 (default `limit=5`)"""
    for _ in range(6):
        mk_item(name="Bolt M8", name_normalized="bolt m8")

    result = M.find_similar_items(db, workspace_id=w1.id, name="Bolt M8")

    # Then 1
    assert len(result) == 5


# [claude] ITM-D-48
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_48__an_item_in_use_deleted_by_an_unknown_user_gets_the_refusal_with_its(db, w1, mk_item, mk_tag, mk_link, mk_f1, mk_stock):
    """ITM-D-48 — an item in use deleted by an unknown user gets the refusal with its blockers, not a database error.
    Rules: `delete_item` R10a [BUG-948], R9b [BUG-948], Errors row 4

    No savepoint around the call, on purpose: the checks after it also prove the transaction stays usable (R10a)."""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=400)
    before_sk = snap(db, sk)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk.id}]
    # Then 4 (before any re-read: expire_all() would throw a pending change away)
    assert i1 not in db.dirty
    # Then 5
    assert db.flush() is None
    # Then 6
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 7
    assert row.updated_at is None
    # Then 8
    assert stored_count(db, t1) == 4
    # Then 9
    assert snap(db, sk) == before_sk
    # Then 10
    assert written(db) == before


# [claude] ITM-D-49
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_49__factory_stock_of_another_workspace_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_stock):
    """ITM-D-49 — factory stock of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (a) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    sk = mk_stock(of=i1, factory=f9, qty=400, workspace_id=w2.id)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk


# [claude] ITM-D-50
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_50__machine_stock_of_another_workspace_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock):
    """ITM-D-50 — machine stock of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (b) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    mc9 = mk_mc9(factory=f9)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5, workspace_id=w2.id)
    before_ms = snap(db, ms)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, ms) == before_ms


# [claude] ITM-D-51
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_51__an_open_purchase_order_of_another_workspace_blocks_the_delete_shown(db, w1, w2, u2, mk_item, mk_f9, mk_st9, mk_po, mk_line):
    """ITM-D-51 — an open purchase order of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (c) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    st9 = mk_st9("Receiving")
    po = mk_po(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    pol = mk_line(of=i1, order=po, workspace_id=w2.id)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pol) == before_pol


# [claude] ITM-D-52
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_52__a_sales_order_of_another_workspace_that_is_not_completed_blocks_the(db, w1, w2, u2, mk_item, mk_f9, mk_ac9, mk_st9, mk_so, mk_line):
    """ITM-D-52 — a sales order of another workspace that is not completed blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (d) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    ac9 = mk_ac9()
    st9 = mk_st9("Open")
    so = mk_so(factory=f9, account=ac9, current_status_id=st9.id, workspace_id=w2.id)
    sol = mk_line(of=i1, order=so, workspace_id=w2.id)
    before_sol = snap(db, sol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sol) == before_sol


# [claude] ITM-D-53
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_53__an_open_work_order_of_another_workspace_blocks_the_delete_shown_only_as(db, w1, w2, u2, mk_item, mk_f9, mk_wt9, mk_wo, mk_line):
    """ITM-D-53 — an open work order of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (e) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    wt9 = mk_wt9()
    wo = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id)
    wol = mk_line(of=i1, order=wo, workspace_id=w2.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-54
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_54__a_transfer_order_of_another_workspace_that_is_not_completed_blocks_the(db, w1, w2, u2, mk_item, mk_f9, mk_st9, mk_to, mk_line):
    """ITM-D-54 — a transfer order of another workspace that is not completed blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (f) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    st9 = mk_st9("Open")
    to = mk_to(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    tol = mk_line(of=i1, order=to, workspace_id=w2.id)
    before_tol = snap(db, tol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, tol) == before_tol


# [claude] ITM-D-55
def test_itm_d_55__a_purchase_order_of_another_workspace_at_its_own_stage_complete_does(db, w1, w2, u2, mk_item, mk_f9, mk_st9, mk_po, mk_line):
    """ITM-D-55 — a purchase order of another workspace at its own stage "Complete" does not block the delete.
    Rules: `delete_item` R9 (c), R9 intro: cross-workspace row, not blocking, R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    st9 = mk_st9("Complete")
    po = mk_po(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    pol = mk_line(of=i1, order=po, workspace_id=w2.id)
    # Given 6: W1 has no stage named "Complete" (no such row is built)
    before_po = snap(db, po)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, po) == before_po
    # Then 4
    assert snap(db, pol) == before_pol


# [claude] ITM-D-56
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_56__normal_blockers_come_first_by_type_and_id_blockers_of_another_workspace(db, w1, w2, u2, mk_item, mk_f1, mk_f9, mk_stock, mk_st9, mk_to, mk_line, mk_wt1, mk_wo):
    """ITM-D-56 — normal blockers come first, by type and id; blockers of another workspace are one generic entry, last.
    Rules: `delete_item` R9b [BUG-948], R9 intro: cross-workspace row [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    f9 = mk_f9()
    sk9 = mk_stock(of=i1, factory=f9, qty=7, workspace_id=w2.id)
    sk1 = mk_stock(of=i1, factory=f1, qty=400)
    st9 = mk_st9("Open")
    to9 = mk_to(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    mk_line(of=i1, order=to9, workspace_id=w2.id)
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    mk_line(of=i1, order=wo)
    before_sk9 = snap(db, sk9)
    before_sk1 = snap(db, sk1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk1.id}, {"type": "work_order", "id": wo.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk9) == before_sk9
    # Then 6
    assert snap(db, sk1) == before_sk1


# [claude] ITM-D-57
def test_itm_d_57__an_inventory_ledger_row_does_not_block_the_delete_and_stays_unchanged(db, w1, u2, mk_item, mk_f1):
    """ITM-D-57 — an inventory ledger row does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    lg = _add(db, InventoryLedger(workspace_id=w1.id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=f1.id, item_id=i1.id, transaction_type="manual_add", quantity=400, qty_before=0, qty_after=400))
    # Given 4: I1 has no `inventory` row (none is built)
    before_lg = snap(db, lg)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, lg) == before_lg


# [claude] ITM-D-58
def test_itm_d_58__a_machine_item_ledger_row_does_not_block_the_delete_and_stays_unchanged(db, w1, u1, u2, mk_item, mk_f1, mk_mc1):
    """ITM-D-58 — a machine item ledger row does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    lg = _add(db, MachineItemLedger(workspace_id=w1.id, machine_id=mc1.id, item_id=i1.id, transaction_type="manual_add", quantity=5, unit_cost=10, total_cost=50, qty_before=0, qty_after=5, source_type="manual", performed_by=u1.id))
    # Given 5: I1 has no `machine_items` row (none is built)
    before_lg = snap(db, lg)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, lg) == before_lg


# [claude] ITM-D-59
def test_itm_d_59__a_pending_purchase_return_line_on_a_completed_purchase_order_does_not(db, w1, u1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-59 — a pending purchase return line on a completed purchase order does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Complete")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    rt = _add(db, PurchaseOrderReturn(workspace_id=w1.id, purchase_order_id=po.id, return_number="PR-ITM-1", created_by=u1.id, status="pending"))
    rl = _add(db, PurchaseOrderReturnItem(workspace_id=w1.id, return_id=rt.id, po_item_id=pol.id, item_id=i1.id, quantity_returned=2))
    before_rl = snap(db, rl)
    before_rt = snap(db, rt)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, rl) == before_rl
    # Then 4
    assert snap(db, rt) == before_rt
    # Then 5
    assert snap(db, pol) == before_pol


# [claude] ITM-D-60
def test_itm_d_60__a_pending_sales_return_line_on_a_completed_sales_order_does_not_block(db, w1, u1, u2, mk_item, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-60 — a pending sales return line on a completed sales order does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id, order_completed=True)
    sol = mk_line(of=i1, order=so)
    rt = _add(db, SalesOrderReturn(workspace_id=w1.id, sales_order_id=so.id, return_number="SR-ITM-1", created_by=u1.id, status="pending"))
    rl = _add(db, SalesOrderReturnItem(workspace_id=w1.id, return_id=rt.id, so_item_id=sol.id, item_id=i1.id, quantity_returned=2))
    before_rl = snap(db, rl)
    before_rt = snap(db, rt)
    before_sol = snap(db, sol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, rl) == before_rl
    # Then 4
    assert snap(db, rt) == before_rt
    # Then 5
    assert snap(db, sol) == before_sol


# [claude] ITM-D-61
def test_itm_d_61__a_work_order_template_line_of_the_item_does_not_block_the_delete_and(db, w1, u2, mk_item, mk_wt1):
    """ITM-D-61 — a work-order template line of the item does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    wt1 = mk_wt1()
    tp = _add(db, WorkOrderTemplate(workspace_id=w1.id, template_name="Press service", work_order_type_id=wt1.id))
    tl = _add(db, WorkOrderTemplateItem(workspace_id=w1.id, work_order_template_id=tp.id, item_id=i1.id))
    before_tl = snap(db, tl)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, tl) == before_tl


# [claude] ITM-D-62
def test_itm_d_62__being_the_replaced_item_of_a_work_order_template_line_does_not_block(db, w1, u2, mk_item, mk_wt1):
    """ITM-D-62 — being the replaced item of a work-order template line does not block the delete, and the line stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    wt1 = mk_wt1()
    tp = _add(db, WorkOrderTemplate(workspace_id=w1.id, template_name="Press service", work_order_type_id=wt1.id))
    tl = _add(db, WorkOrderTemplateItem(workspace_id=w1.id, work_order_template_id=tp.id, item_id=i2.id, replaced_item_id=i1.id))
    before_tl = snap(db, tl)
    before_i2 = snap(db, i2)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, tl) == before_tl
    # Then 4
    assert snap(db, i2) == before_i2


# [claude] ITM-D-63
def test_itm_d_63__a_production_formula_line_of_the_item_does_not_block_the_delete_and(db, w1, u2, mk_item):
    """ITM-D-63 — a production formula line of the item does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    fm = _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-ITM-1", name="Zinc mix"))
    fl = _add(db, ProductionFormulaItem(workspace_id=w1.id, formula_id=fm.id, item_id=i1.id, item_role="input", quantity=3))
    before_fl = snap(db, fl)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, fl) == before_fl


# [claude] ITM-D-64
def test_itm_d_64__being_the_expected_output_of_a_production_formula_stage_does_not_block(db, w1, u2, mk_item):
    """ITM-D-64 — being the expected output of a production formula stage does not block the delete, and the stage stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    fm = _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-ITM-1", name="Zinc mix"))
    fs = _add(db, ProductionFormulaStage(workspace_id=w1.id, formula_id=fm.id, stage_order=1, name="Blend", expected_output_item_id=i1.id))
    before_fs = snap(db, fs)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, fs) == before_fs


# [claude] ITM-D-65
def test_itm_d_65__a_project_component_item_row_does_not_block_the_delete_and_stays(db, w1, u2, mk_item, mk_f1):
    """ITM-D-65 — a project component item row does not block the delete and stays unchanged.
    Rules: `delete_item` R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pj = _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Line upgrade", description="New press line"))
    pc = _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj.id, name="Frame"))
    pi = _add(db, ProjectComponentItem(workspace_id=w1.id, project_component_id=pc.id, item_id=i1.id, qty=12))
    before_pi = snap(db, pi)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pi) == before_pi


# [claude] ITM-D-66
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_66__finished_goods_stock_blocks_the_delete_is_listed_and_nothing_is_written(db, w1, u2, mk_item, mk_tag, mk_link, mk_f1, mk_product):
    """ITM-D-66 — finished-goods stock blocks the delete, is listed, and nothing is written.
    Rules: `delete_item` R9 (g) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=7)
    before_pr = snap(db, pr)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "product_stock", "id": pr.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert row.updated_at is None
    # Then 6
    assert stored_count(db, t1) == 4
    # Then 7
    assert snap(db, pr) == before_pr
    # Then 8
    assert written(db) == before


# [claude] ITM-D-67
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_67__a_negative_finished_goods_quantity_also_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-67 — a negative finished-goods quantity also blocks the delete.
    Rules: `delete_item` R9 (g) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=-3)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "product_stock", "id": pr.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pr) == before_pr


# [claude] ITM-D-68
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_68__finished_goods_stock_blocks_the_delete_even_when_the_products_row_is(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-68 — finished-goods stock blocks the delete even when the products row is inactive.
    Rules: `delete_item` R9 (g) [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=7, is_active=False)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "product_stock", "id": pr.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pr) == before_pr


# [claude] ITM-D-69
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_69__finished_goods_stock_of_another_workspace_blocks_the_delete_shown_only(db, w1, w2, u2, mk_item, mk_f9, mk_product):
    """ITM-D-69 — finished-goods stock of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (g) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    pr = mk_product(of=i1, factory=f9, qty=7, workspace_id=w2.id)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pr) == before_pr


# [claude] ITM-D-70
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_70__two_blocking_products_rows_in_one_factory_are_two_entries_by_id(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-70 — two blocking products rows in one factory are two entries, by id.
    Rules: `delete_item` R9 (g) [BUG-948], R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr1 = mk_product(of=i1, factory=f1, qty=7)
    pr2 = mk_product(of=i1, factory=f1, qty=2, is_available_for_sale=True)
    before_pr1 = snap(db, pr1)
    before_pr2 = snap(db, pr2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "product_stock", "id": pr1.id}, {"type": "product_stock", "id": pr2.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, pr1) == before_pr1
    # Then 5
    assert snap(db, pr2) == before_pr2


# [claude] ITM-D-71
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_71__a_line_on_a_draft_production_batch_blocks_the_delete_names_the_batch(db, w1, u2, mk_item, mk_tag, mk_link, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-71 — a line on a draft production batch blocks the delete, names the batch, and nothing is written.
    Rules: `delete_item` R9 (h) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl = mk_batch_line(of=i1, batch=bt)
    before_bt = snap(db, bt)
    before_bl = snap(db, bl)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "production_batch", "id": bt.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert row.updated_at is None
    # Then 6
    assert stored_count(db, t1) == 4
    # Then 7
    assert snap(db, bt) == before_bt
    # Then 8
    assert snap(db, bl) == before_bl
    # Then 9
    assert written(db) == before


# [claude] ITM-D-72
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_72__an_output_line_on_an_in_progress_production_batch_blocks_the_delete(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-72 — an output line on an in-progress production batch blocks the delete.
    Rules: `delete_item` R9 (h) [BUG-948], R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="in_progress")
    bl = mk_batch_line(of=i1, batch=bt, item_role="output")
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": bt.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, bl) == before_bl


# [claude] ITM-D-73
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_73__an_open_production_batch_of_another_workspace_blocks_the_delete_shown(db, w1, w2, u2, mk_item, mk_f9, mk_pl9, mk_batch, mk_batch_line):
    """ITM-D-73 — an open production batch of another workspace blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 (h) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    pl9 = mk_pl9(factory=f9)
    bt = mk_batch(line=pl9, status="in_progress", workspace_id=w2.id)
    bl = mk_batch_line(of=i1, batch=bt, workspace_id=w2.id)
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, bl) == before_bl


# [claude] ITM-D-74
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_74__a_production_batch_with_two_lines_of_the_item_is_listed_once(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-74 — a production batch with two lines of the item is listed once.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl1 = mk_batch_line(of=i1, batch=bt)
    bl2 = mk_batch_line(of=i1, batch=bt, item_role="output")
    before_bl1 = snap(db, bl1)
    before_bl2 = snap(db, bl2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": bt.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, bl1) == before_bl1
    # Then 5
    assert snap(db, bl2) == before_bl2


# [claude] ITM-D-75
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_75__transfer_order_finished_goods_stock_and_production_batches_are_sorted(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line, mk_product, mk_stage, mk_to, mk_line):
    """ITM-D-75 — transfer order, finished-goods stock and production batches are sorted in that order, batches by id.
    Rules: `delete_item` R9b [BUG-948]"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt1 = mk_batch(line=pl1, status="draft")
    mk_batch_line(of=i1, batch=bt1)
    bt2 = mk_batch(line=pl1, status="in_progress", batch_number="PB-ITM-2")
    mk_batch_line(of=i1, batch=bt2)
    pr = mk_product(of=i1, factory=f1, qty=7)
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    mk_line(of=i1, order=to)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to.id}, {"type": "product_stock", "id": pr.id}, {"type": "production_batch", "id": bt1.id}, {"type": "production_batch", "id": bt2.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pr) == before_pr


# [claude] ITM-D-76
def test_itm_d_76__a_products_row_with_quantity_0_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-76 — a products row with quantity 0 does not block the delete.
    Rules: `delete_item` R9 (g), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=0)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-77
def test_itm_d_77__a_soft_deleted_products_row_does_not_block_the_delete_whatever_its(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-77 — a soft-deleted products row does not block the delete, whatever its quantity.
    Rules: `delete_item` R9 (g), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=7, is_deleted=True)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-78
def test_itm_d_78__a_line_on_a_completed_production_batch_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-78 — a line on a completed production batch does not block the delete.
    Rules: `delete_item` R9 (h), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="completed")
    bl = mk_batch_line(of=i1, batch=bt)
    before_bt = snap(db, bt)
    before_bl = snap(db, bl)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, bt) == before_bt
    # Then 4
    assert snap(db, bl) == before_bl


# [claude] ITM-D-79
def test_itm_d_79__a_line_on_a_cancelled_production_batch_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-79 — a line on a cancelled production batch does not block the delete.
    Rules: `delete_item` R9 (h), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="cancelled")
    bl = mk_batch_line(of=i1, batch=bt)
    before_bt = snap(db, bt)
    before_bl = snap(db, bl)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, bt) == before_bt
    # Then 4
    assert snap(db, bl) == before_bl


# [claude] ITM-D-80
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_80__stock_rows_and_a_batch_line_of_w2_on_parents_of_w1_block_the_delete(db, w1, w2, u2, mk_item, mk_f1, mk_mc1, mk_stock, mk_machine_stock, mk_product, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-80 — stock rows and a batch line of W2 on parents of W1 block the delete, shown only as one generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (a), (b), (g), (h) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    mk_stock(of=i1, factory=f1, qty=400, workspace_id=w2.id)
    mk_machine_stock(of=i1, machine=mc1, qty=5, workspace_id=w2.id)
    mk_product(of=i1, factory=f1, qty=7, workspace_id=w2.id)
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl = mk_batch_line(of=i1, batch=bt, workspace_id=w2.id)
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, bl) == before_bl


# [claude] ITM-D-81
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_81__order_lines_of_w2_on_orders_of_w1_block_the_delete_shown_only_as_one(db, w1, w2, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line, mk_ac1, mk_so, mk_wt1, mk_wo, mk_to):
    """ITM-D-81 — order lines of W2 on orders of W1 block the delete, shown only as one generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (c), (d), (e), (f) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po, workspace_id=w2.id)
    ac1 = mk_ac1()
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    mk_line(of=i1, order=so, workspace_id=w2.id)
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    mk_line(of=i1, order=wo, workspace_id=w2.id)
    to = mk_to(factory=f1, current_status_id=st.id)
    mk_line(of=i1, order=to, workspace_id=w2.id)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pol) == before_pol


# [claude] ITM-D-82
def test_itm_d_82__a_purchase_order_of_w1_on_a_stage_complete_of_w2_does_not_block_the(db, w1, u2, mk_item, mk_f1, mk_st9, mk_po, mk_line):
    """ITM-D-82 — a purchase order of W1 on a stage "Complete" of W2 does not block the delete.
    Rules: `delete_item` R9 intro: the stage is not part of the cross-workspace test, R9 (c), R9a"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st9 = mk_st9("Complete")
    po = mk_po(factory=f1, current_status_id=st9.id)
    pol = mk_line(of=i1, order=po)
    # Given 6: W1 has no stage named "Complete" (no such row is built)
    before_po = snap(db, po)
    before_pol = snap(db, pol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, po) == before_po
    # Then 4
    assert snap(db, pol) == before_pol


# [claude] ITM-D-83
def test_itm_d_83__an_item_of_another_workspace_that_is_in_use_is_refused_without_its(db, w1, w2, u2, mk_item, mk_f9, mk_stock):
    """ITM-D-83 — an item of another workspace that is in use is refused without its blockers.
    Rules: `delete_item` R9 (checked after R1–R3), R2"""
    i9 = mk_item("I9")
    f9 = mk_f9()
    sk = mk_stock(of=i9, factory=f9, qty=400, workspace_id=w2.id)
    before_i9 = snap(db, i9)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert len(exc.value.args) == 1
    # Then 3
    assert exc.value.args[0] != "Item has stock or open orders"
    # Then 4
    assert snap(db, i9) == before_i9
    # Then 5
    assert snap(db, sk) == before_sk


# [claude] ITM-D-84
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_84__a_pending_return_does_not_free_an_order_line_that_blocks_the_orders(db, w1, u1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line, mk_ac1, mk_so):
    """ITM-D-84 — a pending return does not free an order line that blocks: the orders are listed, not the returns.
    Rules: `delete_item` R9a (the order line still counts), R9 (c), (d) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st1 = mk_stage("Receiving")
    po = mk_po(factory=f1, current_status_id=st1.id)
    pol = mk_line(of=i1, order=po)
    prt = _add(db, PurchaseOrderReturn(workspace_id=w1.id, purchase_order_id=po.id, return_number="PR-ITM-1", created_by=u1.id, status="pending"))
    prl = _add(db, PurchaseOrderReturnItem(workspace_id=w1.id, return_id=prt.id, po_item_id=pol.id, item_id=i1.id, quantity_returned=2))
    ac1 = mk_ac1()
    st2 = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st2.id)
    sol = mk_line(of=i1, order=so)
    srt = _add(db, SalesOrderReturn(workspace_id=w1.id, sales_order_id=so.id, return_number="SR-ITM-1", created_by=u1.id, status="pending"))
    srl = _add(db, SalesOrderReturnItem(workspace_id=w1.id, return_id=srt.id, so_item_id=sol.id, item_id=i1.id, quantity_returned=2))
    before_prl = snap(db, prl)
    before_srl = snap(db, srl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po.id}, {"type": "sales_order", "id": so.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, prl) == before_prl
    # Then 6
    assert snap(db, srl) == before_srl


# [claude] ITM-D-85
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_85__waste_and_byproduct_lines_with_quantity_0_on_open_batches_block_the(db, w1, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-85 — waste and byproduct lines with quantity 0 on open batches block the delete.
    Rules: `delete_item` R9 (h) [BUG-948], R9b [BUG-948]

    Quantity columns read from the model (Spec gap 9): expected_quantity, actual_quantity, variance_quantity."""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt1 = mk_batch(line=pl1, status="draft")
    bl1 = mk_batch_line(of=i1, batch=bt1, item_role="waste", expected_quantity=0, actual_quantity=0, variance_quantity=0)
    bt2 = mk_batch(line=pl1, status="in_progress", batch_number="PB-ITM-2")
    bl2 = mk_batch_line(of=i1, batch=bt2, item_role="byproduct", expected_quantity=0, actual_quantity=0, variance_quantity=0)
    before_bl1 = snap(db, bl1)
    before_bl2 = snap(db, bl2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": bt1.id}, {"type": "production_batch", "id": bt2.id}]
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert snap(db, bl1) == before_bl1
    # Then 5
    assert snap(db, bl2) == before_bl2


# [claude] ITM-D-86
def test_itm_d_86__stock_on_a_soft_deleted_factory_and_machine_does_not_block_the_delete(db, w1, u2, mk_item, mk_f1_deleted, mk_mc1_deleted, mk_stock, mk_machine_stock, mk_product):
    """ITM-D-86 — stock on a soft-deleted factory and machine does not block the delete.
    Rules: `delete_item` R9 (a), (b), (g), R9a, R9b"""
    i1 = mk_item("I1")
    f1 = mk_f1_deleted()
    mc1 = mk_mc1_deleted(factory=f1)
    sk = mk_stock(of=i1, factory=f1, qty=400)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    pr = mk_product(of=i1, factory=f1, qty=7)
    before_sk = snap(db, sk)
    before_ms = snap(db, ms)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk
    # Then 4
    assert snap(db, ms) == before_ms
    # Then 5
    assert snap(db, pr) == before_pr


# [claude] ITM-D-87
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_87__a_w1_line_on_a_purchase_order_of_w2_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_st9, mk_po, mk_line):
    """ITM-D-87 — a W1 line on a purchase order of W2 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (c) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    st9 = mk_st9("Draft")
    po = mk_po(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    pol = mk_line(of=i1, order=po)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pol) == before_pol


# [claude] ITM-D-88
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_88__a_w1_line_on_a_production_batch_of_w2_blocks_the_delete_shown_only_as(db, w1, w2, u2, mk_item, mk_f9, mk_pl9, mk_batch, mk_batch_line):
    """ITM-D-88 — a W1 line on a production batch of W2 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    pl9 = mk_pl9(factory=f9)
    bt = mk_batch(line=pl9, status="draft", workspace_id=w2.id)
    bl = mk_batch_line(of=i1, batch=bt)
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, bl) == before_bl


# [claude] ITM-D-89
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_89__a_w1_order_with_one_w1_line_and_one_w2_line_gives_its_normal_entry_and(db, w1, w2, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line):
    """ITM-D-89 — a W1 order with one W1 line and one W2 line gives its normal entry and the generic entry.
    Rules: `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (c) [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol1 = mk_line(of=i1, order=po)
    pol2 = mk_line(of=i1, order=po, line_number=2, workspace_id=w2.id)
    before_pol1 = snap(db, pol1)
    before_pol2 = snap(db, pol2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pol1) == before_pol1
    # Then 6
    assert snap(db, pol2) == before_pol2


# [claude] ITM-D-90
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_90__w1_rows_that_point_at_a_stage_or_factory_of_w2_get_their_normal_entries(db, w1, u2, mk_item, mk_f1, mk_f9, mk_st9, mk_po, mk_line, mk_stock):
    """ITM-D-90 — W1 rows that point at a stage or factory of W2 get their normal entries, not the generic one.
    Rules: `delete_item` R9 intro: the stage or factory is not part of the cross-workspace test [BUG-948], R9 (a), (c) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    f9 = mk_f9()
    st9 = mk_st9("Draft")
    po = mk_po(factory=f1, current_status_id=st9.id)
    pol = mk_line(of=i1, order=po)
    sk = mk_stock(of=i1, factory=f9, qty=400)
    before_sk = snap(db, sk)
    before_pol = snap(db, pol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk.id}, {"type": "purchase_order", "id": po.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk
    # Then 6
    assert snap(db, pol) == before_pol


# [claude] ITM-D-91
def test_itm_d_91__a_factory_stock_row_of_w2_with_quantity_0_does_not_block_the_delete(db, w1, w2, u2, mk_item, mk_f9, mk_stock):
    """ITM-D-91 — a factory stock row of W2 with quantity 0 does not block the delete.
    Rules: `delete_item` R9 intro: cross-workspace row, not blocking, R9 (a), R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    sk = mk_stock(of=i1, factory=f9, qty=0, workspace_id=w2.id)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [claude] ITM-D-92
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_92__a_factory_stock_row_of_w2_on_a_factory_of_w1_blocks_the_delete_shown(db, w1, w2, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-92 — a factory stock row of W2 on a factory of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (a) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    sk = mk_stock(of=i1, factory=f1, qty=400, workspace_id=w2.id)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk


# [claude] ITM-D-93
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_93__a_machine_stock_row_of_w2_on_a_machine_of_w1_blocks_the_delete_shown(db, w1, w2, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-93 — a machine stock row of W2 on a machine of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (b) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5, workspace_id=w2.id)
    before_ms = snap(db, ms)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, ms) == before_ms


# [claude] ITM-D-94
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_94__a_products_row_of_w2_on_a_factory_of_w1_blocks_the_delete_shown_only(db, w1, w2, u2, mk_item, mk_f1, mk_product):
    """ITM-D-94 — a products row of W2 on a factory of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (g) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pr = mk_product(of=i1, factory=f1, qty=7, workspace_id=w2.id)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pr) == before_pr


# [claude] ITM-D-95
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_95__a_w2_line_on_a_sales_order_of_w1_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-95 — a W2 line on a sales order of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    sol = mk_line(of=i1, order=so, workspace_id=w2.id)
    before_sol = snap(db, sol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sol) == before_sol


# [claude] ITM-D-96
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_96__a_w2_line_on_a_work_order_of_w1_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-96 — a W2 line on a work order of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol = mk_line(of=i1, order=wo, workspace_id=w2.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-97
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_97__a_w2_line_on_a_transfer_order_of_w1_blocks_the_delete_shown_only_as(db, w1, w2, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line):
    """ITM-D-97 — a W2 line on a transfer order of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    tol = mk_line(of=i1, order=to, workspace_id=w2.id)
    before_tol = snap(db, tol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, tol) == before_tol


# [claude] ITM-D-98
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_98__a_w2_line_on_a_production_batch_of_w1_blocks_the_delete_shown_only_as(db, w1, w2, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-98 — a W2 line on a production batch of W1 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl = mk_batch_line(of=i1, batch=bt, workspace_id=w2.id)
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, bl) == before_bl


# [claude] ITM-D-99
def test_itm_d_99__factory_stock_in_a_factory_with_only_is_deleted_true_does_not_block_the(db, w1, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-99 — factory stock in a factory with only `is_deleted True` does not block the delete.
    Rules: `delete_item` R9 (a), R9a, R9b"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    sk = mk_stock(of=i1, factory=f1, qty=7)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [claude] ITM-D-100
def test_itm_d_100__a_products_row_in_a_factory_with_only_is_deleted_true_does_not_block(db, w1, u2, mk_item, mk_f1, mk_product):
    """ITM-D-100 — a products row in a factory with only `is_deleted True` does not block the delete.
    Rules: `delete_item` R9 (g), R9a, R9b"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    pr = mk_product(of=i1, factory=f1, qty=7)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-101
def test_itm_d_101__machine_stock_on_a_deleted_machine_in_a_live_factory_does_not_block_the(db, w1, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-101 — machine stock on a deleted machine in a live factory does not block the delete.
    Rules: `delete_item` R9 (b), R9a, R9b"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1, is_deleted=True)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-102
def test_itm_d_102__machine_stock_on_a_live_machine_of_a_deleted_factory_does_not_block_the(db, w1, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-102 — machine stock on a live machine of a deleted factory does not block the delete.
    Rules: `delete_item` R9 (b), R9a, R9b"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    mc1 = mk_mc1(factory=f1)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-103
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_103__stock_of_a_machine_and_factory_that_are_only_deactivated_still_blocks(db, w1, u2, mk_item, mk_f1, mk_mc1, mk_stock, mk_machine_stock, mk_product):
    """ITM-D-103 — stock of a machine and factory that are only deactivated still blocks the delete and is listed.
    Rules: `delete_item` R9 (a), (b), (g) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_active=False)
    mc1 = mk_mc1(factory=f1, is_active=False)
    sk = mk_stock(of=i1, factory=f1, qty=400)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    pr = mk_product(of=i1, factory=f1, qty=7)
    before_sk = snap(db, sk)
    before_ms = snap(db, ms)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": sk.id}, {"type": "machine_stock", "id": ms.id}, {"type": "product_stock", "id": pr.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk
    # Then 6
    assert snap(db, ms) == before_ms
    # Then 7
    assert snap(db, pr) == before_pr


# [claude] ITM-D-104
def test_itm_d_104__a_w2_stock_row_in_a_deleted_w2_factory_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f9, mk_stock):
    """ITM-D-104 — a W2 stock row in a deleted W2 factory does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    sk = mk_stock(of=i1, factory=f9, qty=7, workspace_id=w2.id)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [claude] ITM-D-105
def test_itm_d_105__a_w2_stock_row_in_a_deleted_w1_factory_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f1, mk_stock):
    """ITM-D-105 — a W2 stock row in a deleted W1 factory does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    sk = mk_stock(of=i1, factory=f1, qty=7, workspace_id=w2.id)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [claude] ITM-D-106
def test_itm_d_106__a_w1_stock_row_in_a_deleted_w2_factory_does_not_block_the_delete(db, w1, u2, mk_item, mk_f9, mk_stock):
    """ITM-D-106 — a W1 stock row in a deleted W2 factory does not block the delete.
    Rules: `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    sk = mk_stock(of=i1, factory=f9, qty=7)
    before_sk = snap(db, sk)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk


# [claude] ITM-D-107
def test_itm_d_107__a_w2_products_row_in_a_deleted_w2_factory_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f9, mk_product):
    """ITM-D-107 — a W2 products row in a deleted W2 factory does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    pr = mk_product(of=i1, factory=f9, qty=7, workspace_id=w2.id)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-108
def test_itm_d_108__a_w2_products_row_in_a_deleted_w1_factory_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f1, mk_product):
    """ITM-D-108 — a W2 products row in a deleted W1 factory does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    pr = mk_product(of=i1, factory=f1, qty=7, workspace_id=w2.id)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-109
def test_itm_d_109__a_w1_products_row_in_a_deleted_w2_factory_does_not_block_the_delete(db, w1, u2, mk_item, mk_f9, mk_product):
    """ITM-D-109 — a W1 products row in a deleted W2 factory does not block the delete.
    Rules: `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    pr = mk_product(of=i1, factory=f9, qty=7)
    before_pr = snap(db, pr)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pr) == before_pr


# [claude] ITM-D-110
def test_itm_d_110__a_w2_machine_row_on_a_deleted_w2_machine_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock):
    """ITM-D-110 — a W2 machine row on a deleted W2 machine does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    mc9 = mk_mc9(factory=f9, is_deleted=True)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5, workspace_id=w2.id)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-111
def test_itm_d_111__a_w2_machine_row_on_a_deleted_w1_machine_does_not_block_the_delete_and(db, w1, w2, u2, mk_item, mk_f1, mk_mc1, mk_machine_stock):
    """ITM-D-111 — a W2 machine row on a deleted W1 machine does not block the delete and gets no generic entry.
    Rules: `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    mc1 = mk_mc1(factory=f1, is_deleted=True)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5, workspace_id=w2.id)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-112
def test_itm_d_112__a_w1_machine_row_on_a_deleted_w2_machine_does_not_block_the_delete(db, w1, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock):
    """ITM-D-112 — a W1 machine row on a deleted W2 machine does not block the delete.
    Rules: `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    mc9 = mk_mc9(factory=f9, is_deleted=True)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-113
def test_itm_d_113__a_w2_machine_row_on_a_live_w2_machine_of_a_deleted_w2_factory_does_not(db, w1, w2, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock):
    """ITM-D-113 — a W2 machine row on a live W2 machine of a deleted W2 factory does not block the delete.
    Rules: `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    mc9 = mk_mc9(factory=f9)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5, workspace_id=w2.id)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-114
def test_itm_d_114__a_w1_machine_row_on_a_live_w2_machine_of_a_deleted_w2_factory_does_not(db, w1, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock):
    """ITM-D-114 — a W1 machine row on a live W2 machine of a deleted W2 factory does not block the delete.
    Rules: `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states"""
    i1 = mk_item("I1")
    f9 = mk_f9(is_deleted=True)
    mc9 = mk_mc9(factory=f9)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5)
    before_ms = snap(db, ms)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, ms) == before_ms


# [claude] ITM-D-115
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_115__stock_with_a_deleted_parent_beside_a_live_blocker_only_the_live_one_is(db, w1, w2, u2, mk_item, mk_f1, mk_mc1, mk_stock, mk_machine_stock, mk_product, mk_f9):
    """ITM-D-115 — stock with a deleted parent beside a live blocker: only the live one is listed.
    Rules: `delete_item` R9 (a), (b), (g) [BUG-948], R9a, R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    f2 = mk_f1(name="Side Plant", abbreviation="SP", is_deleted=False)
    mc1 = mk_mc1(factory=f1)
    sk = mk_stock(of=i1, factory=f1, qty=400)
    ms = mk_machine_stock(of=i1, machine=mc1, qty=5)
    pr = mk_product(of=i1, factory=f1, qty=7)
    f9 = mk_f9(is_deleted=True)
    sk9 = mk_stock(of=i1, factory=f9, qty=9, workspace_id=w2.id)
    lv = mk_stock(of=i1, factory=f2, qty=3)
    before_sk = snap(db, sk)
    before_ms = snap(db, ms)
    before_pr = snap(db, pr)
    before_sk9 = snap(db, sk9)
    before_lv = snap(db, lv)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "factory_stock", "id": lv.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk) == before_sk
    # Then 6
    assert snap(db, ms) == before_ms
    # Then 7
    assert snap(db, pr) == before_pr
    # Then 8
    assert snap(db, sk9) == before_sk9
    # Then 9
    assert snap(db, lv) == before_lv


# [claude] ITM-D-116
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_116__open_order_and_batch_lines_tied_to_a_deleted_factory_still_block_the(db, w1, u2, mk_item, mk_f1, mk_stage, mk_po, mk_line, mk_ac1, mk_so, mk_wt1, mk_wo, mk_to, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-116 — open order and batch lines tied to a deleted factory still block the delete and are listed.
    Rules: `delete_item` R9a (orders and batches not covered), R9 (c), (d), (e), (f), (h) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f1 = mk_f1(is_deleted=True)
    st = mk_stage("Draft")
    po = mk_po(factory=f1, current_status_id=st.id)
    pol = mk_line(of=i1, order=po)
    ac1 = mk_ac1()
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    sol = mk_line(of=i1, order=so)
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol = mk_line(of=i1, order=wo)
    to = mk_to(factory=f1, current_status_id=st.id)
    tol = mk_line(of=i1, order=to)
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl = mk_batch_line(of=i1, batch=bt)
    before_pol = snap(db, pol)
    before_sol = snap(db, sol)
    before_wol = snap(db, wol)
    before_tol = snap(db, tol)
    before_bl = snap(db, bl)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "purchase_order", "id": po.id}, {"type": "sales_order", "id": so.id}, {"type": "work_order", "id": wo.id}, {"type": "transfer_order", "id": to.id}, {"type": "production_batch", "id": bt.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, pol) == before_pol
    # Then 6
    assert snap(db, sol) == before_sol
    # Then 7
    assert snap(db, wol) == before_wol
    # Then 8
    assert snap(db, tol) == before_tol
    # Then 9
    assert snap(db, bl) == before_bl


# [claude] ITM-D-117
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_117__a_w1_line_on_a_sales_order_of_w2_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_ac9, mk_st9, mk_so, mk_line):
    """ITM-D-117 — a W1 line on a sales order of W2 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    ac9 = mk_ac9()
    st9 = mk_st9("Open")
    so = mk_so(factory=f9, account=ac9, current_status_id=st9.id, workspace_id=w2.id)
    sol = mk_line(of=i1, order=so)
    before_sol = snap(db, sol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sol) == before_sol


# [claude] ITM-D-118
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_118__a_w1_line_on_a_work_order_of_w2_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_wt9, mk_wo, mk_line):
    """ITM-D-118 — a W1 line on a work order of W2 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    wt9 = mk_wt9()
    wo = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id)
    wol = mk_line(of=i1, order=wo)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-119
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_119__a_w1_line_on_a_transfer_order_of_w2_blocks_the_delete_shown_only_as_the(db, w1, w2, u2, mk_item, mk_f9, mk_st9, mk_to, mk_line):
    """ITM-D-119 — a W1 line on a transfer order of W2 blocks the delete, shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    st9 = mk_st9("Open")
    to = mk_to(factory=f9, current_status_id=st9.id, workspace_id=w2.id)
    tol = mk_line(of=i1, order=to)
    before_tol = snap(db, tol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, tol) == before_tol


# [claude] ITM-D-120
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_120__a_w2_line_on_a_work_order_of_w1_that_replaces_the_item_is_shown_only_as(db, w1, w2, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-120 — a W2 line on a work order of W1 that replaces the item is shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol = mk_line(of=i2, order=wo, replaced_item_id=i1.id, workspace_id=w2.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-121
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_121__a_w1_line_on_a_work_order_of_w2_that_replaces_the_item_is_shown_only_as(db, w1, w2, u2, mk_item, mk_f9, mk_wt9, mk_wo, mk_line):
    """ITM-D-121 — a W1 line on a work order of W2 that replaces the item is shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f9 = mk_f9()
    wt9 = mk_wt9()
    wo = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id)
    wol = mk_line(of=i2, order=wo, replaced_item_id=i1.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-122
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_122__a_w2_line_on_a_work_order_of_w2_that_replaces_the_item_is_shown_only_as(db, w1, w2, u2, mk_item, mk_f9, mk_wt9, mk_wo, mk_line):
    """ITM-D-122 — a W2 line on a work order of W2 that replaces the item is shown only as the generic entry.
    Rules: `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    f9 = mk_f9()
    wt9 = mk_wt9()
    wo = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id)
    wol = mk_line(of=i2, order=wo, replaced_item_id=i1.id, workspace_id=w2.id)
    before_wol = snap(db, wol)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol) == before_wol


# [claude] ITM-D-123
def test_itm_d_123__w2_stock_rows_in_their_non_blocking_states_do_not_block_the_delete(db, w1, w2, u2, mk_item, mk_f9, mk_mc9, mk_stock, mk_machine_stock, mk_product):
    """ITM-D-123 — W2 stock rows in their non-blocking states do not block the delete.
    Rules: `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (a), (b), (g), R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    mc9 = mk_mc9(factory=f9)
    sk = mk_stock(of=i1, factory=f9, qty=7, workspace_id=w2.id, is_deleted=True)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=0, workspace_id=w2.id)
    pr1 = mk_product(of=i1, factory=f9, qty=0, workspace_id=w2.id)
    pr2 = mk_product(of=i1, factory=f9, qty=7, workspace_id=w2.id, is_deleted=True, is_available_for_sale=True)
    before_sk = snap(db, sk)
    before_ms = snap(db, ms)
    before_pr1 = snap(db, pr1)
    before_pr2 = snap(db, pr2)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, sk) == before_sk
    # Then 4
    assert snap(db, ms) == before_ms
    # Then 5
    assert snap(db, pr1) == before_pr1
    # Then 6
    assert snap(db, pr2) == before_pr2


# [claude] ITM-D-124
def test_itm_d_124__w2_purchase_sales_and_transfer_orders_in_their_non_blocking_states_do(db, w1, w2, u2, mk_item, mk_f9, mk_ac9, mk_st9, mk_po, mk_line, mk_so, mk_to):
    """ITM-D-124 — W2 purchase, sales and transfer orders in their non-blocking states do not block the delete.
    Rules: `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (c), (d), (f), R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    ac9 = mk_ac9()
    st9 = mk_st9("Open")
    po = mk_po(factory=f9, current_status_id=st9.id, workspace_id=w2.id, voided=True)
    pol = mk_line(of=i1, order=po, workspace_id=w2.id)
    so = mk_so(factory=f9, account=ac9, current_status_id=st9.id, workspace_id=w2.id, order_completed=True)
    sol = mk_line(of=i1, order=so, workspace_id=w2.id)
    to = mk_to(factory=f9, current_status_id=st9.id, workspace_id=w2.id, completed_at=T0)
    tol = mk_line(of=i1, order=to, workspace_id=w2.id)
    before_pol = snap(db, pol)
    before_sol = snap(db, sol)
    before_tol = snap(db, tol)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, pol) == before_pol
    # Then 4
    assert snap(db, sol) == before_sol
    # Then 5
    assert snap(db, tol) == before_tol


# [claude] ITM-D-125
def test_itm_d_125__w2_work_orders_in_their_non_blocking_states_do_not_block_the_delete(db, w1, w2, u2, mk_item, mk_f9, mk_wt9, mk_wo, mk_line):
    """ITM-D-125 — W2 work orders in their non-blocking states do not block the delete.
    Rules: `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (e), R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    wt9 = mk_wt9()
    wo1 = mk_wo(factory=f9, wo_type=wt9, status="COMPLETED", workspace_id=w2.id)
    wol1 = mk_line(of=i1, order=wo1, workspace_id=w2.id)
    wo2 = mk_wo(factory=f9, wo_type=wt9, status="VOIDED", workspace_id=w2.id, work_order_number="WO-ITM-2")
    wol2 = mk_line(of=i1, order=wo2, workspace_id=w2.id)
    wo3 = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id, work_order_number="WO-ITM-3", is_deleted=True)
    wol3 = mk_line(of=i1, order=wo3, workspace_id=w2.id)
    wo4 = mk_wo(factory=f9, wo_type=wt9, status="DRAFT", workspace_id=w2.id, work_order_number="WO-ITM-4")
    wol4 = mk_line(of=i1, order=wo4, workspace_id=w2.id, is_deleted=True)
    before_wol1 = snap(db, wol1)
    before_wol2 = snap(db, wol2)
    before_wol3 = snap(db, wol3)
    before_wol4 = snap(db, wol4)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, wol1) == before_wol1
    # Then 4
    assert snap(db, wol2) == before_wol2
    # Then 5
    assert snap(db, wol3) == before_wol3
    # Then 6
    assert snap(db, wol4) == before_wol4


# [claude] ITM-D-126
def test_itm_d_126__w2_batches_completed_and_cancelled_do_not_block_the_delete(db, w1, w2, u2, mk_item, mk_f9, mk_pl9, mk_batch, mk_batch_line):
    """ITM-D-126 — W2 batches `completed` and `cancelled` do not block the delete.
    Rules: `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (h), R9a"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    pl9 = mk_pl9(factory=f9)
    bt1 = mk_batch(line=pl9, status="completed", workspace_id=w2.id)
    bl1 = mk_batch_line(of=i1, batch=bt1, workspace_id=w2.id)
    bt2 = mk_batch(line=pl9, status="cancelled", workspace_id=w2.id, batch_number="PB-ITM-2")
    bl2 = mk_batch_line(of=i1, batch=bt2, workspace_id=w2.id)
    before_bl1 = snap(db, bl1)
    before_bl2 = snap(db, bl2)

    result = M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    # Then 3
    assert snap(db, bl1) == before_bl1
    # Then 4
    assert snap(db, bl2) == before_bl2


# [claude] ITM-D-127
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_127__w1_rows_on_w2_machines_factories_accounts_types_stages_and_production(db, w1, u2, mk_item, mk_f9, mk_mc9, mk_machine_stock, mk_ac9, mk_st9, mk_so, mk_line, mk_wt9, mk_wo, mk_to, mk_product, mk_pl9, mk_batch, mk_batch_line):
    """ITM-D-127 — W1 rows on W2 machines, factories, accounts, types, stages and production lines get their normal entries.
    Rules: `delete_item` R9 intro: the factory, machine, stage or production line is not part of the cross-workspace test [BUG-948], R9 (b), (d), (e), (f), (g), (h) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    mc9 = mk_mc9(factory=f9)
    ms = mk_machine_stock(of=i1, machine=mc9, qty=5)
    ac9 = mk_ac9()
    st9 = mk_st9("Open")
    so = mk_so(factory=f9, account=ac9, current_status_id=st9.id)
    mk_line(of=i1, order=so)
    wt9 = mk_wt9()
    wo = mk_wo(factory=f9, wo_type=wt9, status="DRAFT")
    mk_line(of=i1, order=wo)
    to = mk_to(factory=f9, current_status_id=st9.id)
    mk_line(of=i1, order=to)
    pr = mk_product(of=i1, factory=f9, qty=7)
    pl9 = mk_pl9(factory=f9)
    bt = mk_batch(line=pl9, status="draft")
    mk_batch_line(of=i1, batch=bt)
    before_ms = snap(db, ms)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "machine_stock", "id": ms.id}, {"type": "sales_order", "id": so.id}, {"type": "work_order", "id": wo.id}, {"type": "transfer_order", "id": to.id}, {"type": "product_stock", "id": pr.id}, {"type": "production_batch", "id": bt.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, ms) == before_ms
    # Then 6
    assert snap(db, pr) == before_pr


# [claude] ITM-D-128
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_128__a_w1_sales_order_with_one_w1_line_and_one_w2_line_gives_its_normal(db, w1, w2, u2, mk_item, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-128 — a W1 sales order with one W1 line and one W2 line gives its normal entry and the generic entry.
    Rules: `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    sol1 = mk_line(of=i1, order=so)
    sol2 = mk_line(of=i1, order=so, workspace_id=w2.id)
    before_sol1 = snap(db, sol1)
    before_sol2 = snap(db, sol2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "sales_order", "id": so.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sol1) == before_sol1
    # Then 6
    assert snap(db, sol2) == before_sol2


# [claude] ITM-D-129
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_129__a_w1_work_order_with_one_w1_line_and_one_w2_line_gives_its_normal_entry(db, w1, w2, u2, mk_item, mk_f1, mk_wt1, mk_wo, mk_line):
    """ITM-D-129 — a W1 work order with one W1 line and one W2 line gives its normal entry and the generic entry.
    Rules: `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    wol1 = mk_line(of=i1, order=wo)
    wol2 = mk_line(of=i1, order=wo, workspace_id=w2.id)
    before_wol1 = snap(db, wol1)
    before_wol2 = snap(db, wol2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "work_order", "id": wo.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, wol1) == before_wol1
    # Then 6
    assert snap(db, wol2) == before_wol2


# [claude] ITM-D-130
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_130__a_w1_transfer_order_with_one_w1_line_and_one_w2_line_gives_its_normal(db, w1, w2, u2, mk_item, mk_f1, mk_stage, mk_to, mk_line):
    """ITM-D-130 — a W1 transfer order with one W1 line and one W2 line gives its normal entry and the generic entry.
    Rules: `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    tol1 = mk_line(of=i1, order=to)
    tol2 = mk_line(of=i1, order=to, line_number=2, workspace_id=w2.id)
    before_tol1 = snap(db, tol1)
    before_tol2 = snap(db, tol2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "transfer_order", "id": to.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, tol1) == before_tol1
    # Then 6
    assert snap(db, tol2) == before_tol2


# [claude] ITM-D-131
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_131__a_w1_batch_with_one_w1_line_and_one_w2_line_gives_its_normal_entry_and(db, w1, w2, u2, mk_item, mk_f1, mk_pl1, mk_batch, mk_batch_line):
    """ITM-D-131 — a W1 batch with one W1 line and one W2 line gives its normal entry and the generic entry.
    Rules: `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    bl1 = mk_batch_line(of=i1, batch=bt)
    bl2 = mk_batch_line(of=i1, batch=bt, item_role="output", workspace_id=w2.id)
    before_bl1 = snap(db, bl1)
    before_bl2 = snap(db, bl2)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "production_batch", "id": bt.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, bl1) == before_bl1
    # Then 6
    assert snap(db, bl2) == before_bl2


# [claude] ITM-D-132
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_132__work_order_transfer_order_finished_goods_stock_and_batch_keep_their(db, w1, w2, u2, mk_item, mk_f1, mk_f9, mk_stock, mk_pl1, mk_batch, mk_batch_line, mk_product, mk_stage, mk_to, mk_line, mk_wt1, mk_wo):
    """ITM-D-132 — work order, transfer order, finished-goods stock and batch keep their order, and the generic entry stays last.
    Rules: `delete_item` R9b [BUG-948], R9 intro: cross-workspace row [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f1 = mk_f1()
    f9 = mk_f9()
    sk9 = mk_stock(of=i1, factory=f9, qty=4, workspace_id=w2.id)
    pl1 = mk_pl1(factory=f1)
    bt = mk_batch(line=pl1, status="draft")
    mk_batch_line(of=i1, batch=bt)
    pr = mk_product(of=i1, factory=f1, qty=7)
    st = mk_stage("Open")
    to = mk_to(factory=f1, current_status_id=st.id)
    mk_line(of=i1, order=to)
    wt1 = mk_wt1()
    wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")
    mk_line(of=i1, order=wo)
    before_sk9 = snap(db, sk9)
    before_pr = snap(db, pr)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "work_order", "id": wo.id}, {"type": "transfer_order", "id": to.id}, {"type": "product_stock", "id": pr.id}, {"type": "production_batch", "id": bt.id}, {"type": "other_workspace"}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert snap(db, sk9) == before_sk9
    # Then 6
    assert snap(db, pr) == before_pr


# [claude] ITM-D-133
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_itm_d_133__an_item_whose_only_blocker_is_cross_workspace_deleted_by_an_unknown(db, w1, w2, mk_item, mk_f9, mk_stock):
    """ITM-D-133 — an item whose only blocker is cross-workspace, deleted by an unknown user, gets the refusal, not a database error.
    Rules: `delete_item` R10a [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5"""
    i1 = mk_item("I1")
    f9 = mk_f9()
    sk = mk_stock(of=i1, factory=f9, qty=400, workspace_id=w2.id)
    before_sk = snap(db, sk)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 4
    assert i1 not in db.dirty
    # Then 5
    assert db.flush() is None
    # Then 6
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 7
    assert snap(db, sk) == before_sk
