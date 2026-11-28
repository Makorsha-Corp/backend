"""Unit tests for app/managers/ledger_manager.py.

Implements tests/unit/managers/ledger_manager.cases.md (revision 3), one test
per case. Real Postgres session (`db` fixture). No externals are mocked
(spec: "Externals to mock: none"; `utcnow` is the real clock).

No app write path creates machine/project/inventory ledger rows yet (per the
spec's Overview), so every ledger "entry" in these tests is inserted directly
through the model, one insert + flush per row (ids ascend in insertion order),
with an explicit `performed_at` (spec Notes: "set performed_at explicitly when
a test needs a definite latest row").
"""
# ruff: noqa: SIM117, DTZ001  (prescribed by the cards: nested with, naive datetimes)
import re
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DataError

from app.managers.ledger_manager import LedgerManager
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.enums import InventoryTypeEnum
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
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED
WASTE = InventoryTypeEnum.WASTE

# --------------------------------------------------------------------------- #
# Bug titles (for xfail reasons; BUG-NNN numbers per the cases file)
# --------------------------------------------------------------------------- #

BUG_341_GML_TYPE = "BUG-341: transaction_type ignored once a full date range is also given (get_machine_ledger)"
BUG_341_GML_BOUND = "BUG-341: a lone start_date or end_date bound applies no date filter at all (get_machine_ledger)"
BUG_341_GIL_TYPE = "BUG-341: transaction_type ignored once a full date range is also given (get_inventory_ledger)"
BUG_341_GIL_BOUND = "BUG-341: a lone start_date or end_date bound applies no date filter at all (get_inventory_ledger)"
BUG_341_IMS_ITEM = "BUG-341: get_item_movement_summary never filters its lists by item_id"
BUG_341_TBU = "BUG-341: get_transactions_by_user ignores start_date/end_date entirely"
BUG_640 = "BUG-640: ledger list ordering is performed_at only; tied rows are not further ordered by id descending"
BUG_641 = "BUG-641: latest-entry ('top-1') lookup breaks performed_at ties arbitrarily instead of by highest id"
BUG_643 = "BUG-643: reconcile_machine_item reads the machine_items snapshot without FOR UPDATE OF machine_items"
BUG_644 = "BUG-644: reconcile_inventory reads the inventory snapshot without FOR UPDATE OF inventory"
BUG_645 = "BUG-645: get_transactions_by_user crashes (machine/project ledger DAOs have no get_by_performer)"
BUG_646 = "BUG-646: get_item_movement_summary returns empty lists unless both dates are given"
BUG_647 = "BUG-647: get_item_movement_summary's project list is always empty"
BUG_648 = "BUG-648: get_item_movement_summary has no skip/limit (silently capped at 100 rows per ledger)"
BUG_649 = "BUG-649: reconcile reports status=error when there is nothing to reconcile"
BUG_650 = "BUG-650: reconcile raises TypeError when the latest entry's avg_price_after is NULL"
BUG_651 = "BUG-651: the reconciliation adjustment row breaks the ledger's running qty/value chain"
BUG_652 = "BUG-652: reconcile_inventory leaves the snapshot's updated_by unchanged"
BUG_653 = "BUG-653: reconcile_inventory ignores an avg_price-only mismatch when quantities already match"
BUG_654 = "BUG-654: calculate_project_component_total_cost adds outgoing movements instead of subtracting them"
BUG_655 = "BUG-655: inventory balance/reconcile raise AttributeError (InventoryLedger has no value_after)"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #


# Convention "T(d)" / "T(d, hh:mm:ss)": 2025-06-d at the given time (naive)
def T(day, time="10:00:00"):
    hh, mm, ss = (int(x) for x in time.split(":"))
    return datetime(2025, 6, day, hh, mm, ss)


# Attachment ledger's performed_at is tz-aware (server_default func.now());
# use an aware-UTC value with the same wall-clock reading as T(day, time).
def TA(day, time="10:00:00"):
    return T(day, time).replace(tzinfo=timezone.utc)


def ids(rows):
    return [r.id for r in rows]


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1, U2 = two user profiles in W1; U3 = a user profile in W2"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


@pytest.fixture
def u3(db):
    return make_profile(db)


# Convention "M = a LedgerManager() instance"
@pytest.fixture
def M():
    return LedgerManager()


def mk_factory(db, ws, name):
    row = Factory(workspace_id=ws.id, name=name, abbreviation=name[:4].upper())
    db.add(row)
    db.flush()
    return row


# Convention "F1, F2 = factories in W1; F9 = a factory in W2"
@pytest.fixture
def f1(db, w1):
    return mk_factory(db, w1, "Factory 1")


@pytest.fixture
def f2(db, w1):
    return mk_factory(db, w1, "Factory 2")


@pytest.fixture
def f9(db, w2):
    return mk_factory(db, w2, "Factory 9")


def mk_machine(db, ws, factory, name):
    row = Machine(workspace_id=ws.id, factory_id=factory.id, name=name)
    db.add(row)
    db.flush()
    return row


# Convention "M1, M2 = machines in W1; M9 = a machine in W2"
@pytest.fixture
def m1(db, w1, f1):
    return mk_machine(db, w1, f1, "Machine 1")


@pytest.fixture
def m2(db, w1, f1):
    return mk_machine(db, w1, f1, "Machine 2")


@pytest.fixture
def m9(db, w2, f9):
    return mk_machine(db, w2, f9, "Machine 9")


def mk_item(db, ws, name, *, active=True):
    row = Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs", is_active=active)
    db.add(row)
    db.flush()
    return row


# Convention "I1 = Bolt (active); I2 = Nut (active); I3 = Old Bolt (inactive); I9 = Washer (W2)"
@pytest.fixture
def i1(db, w1):
    return mk_item(db, w1, "Bolt")


@pytest.fixture
def i2(db, w1):
    return mk_item(db, w1, "Nut")


@pytest.fixture
def i3(db, w1):
    return mk_item(db, w1, "Old Bolt", active=False)


@pytest.fixture
def i9(db, w2):
    return mk_item(db, w2, "Washer")


def mk_project(db, ws, factory):
    row = Project(workspace_id=ws.id, factory_id=factory.id, name="Project", description="")
    db.add(row)
    db.flush()
    return row


def mk_pc(db, ws, project, name):
    row = ProjectComponent(workspace_id=ws.id, project_id=project.id, name=name)
    db.add(row)
    db.flush()
    return row


# Convention "PC1, PC2 = project components in W1; PC9 = a project component in W2"
@pytest.fixture
def proj1(db, w1, f1):
    return mk_project(db, w1, f1)


@pytest.fixture
def pc1(db, w1, proj1):
    return mk_pc(db, w1, proj1, "PC1")


@pytest.fixture
def pc2(db, w1, proj1):
    return mk_pc(db, w1, proj1, "PC2")


@pytest.fixture
def proj9(db, w2, f9):
    return mk_project(db, w2, f9)


@pytest.fixture
def pc9(db, w2, proj9):
    return mk_pc(db, w2, proj9, "PC9")


def mk_attachment(db, ws, uploader):
    row = Attachment(workspace_id=ws.id, file_name="file.png", mime_type="image/png",
                      file_size=100, uploaded_by=uploader.id)
    db.add(row)
    db.flush()
    return row


# Convention "A1, A2 = attachments rows in W1; A9 = an attachments row in W2"
@pytest.fixture
def a1(db, w1, u1):
    return mk_attachment(db, w1, u1)


@pytest.fixture
def a2(db, w1, u1):
    return mk_attachment(db, w1, u1)


@pytest.fixture
def a9(db, w2, u3):
    return mk_attachment(db, w2, u3)


# Convention "machine entry" = a machine_item_ledger row
def mk_mel(db, ws, machine, item, ttype, performed_at, *, performed_by, qty=1,
           unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"), qty_before=0, qty_after=0,
           value_before=None, value_after=None, avg_price_before=None, avg_price_after=None,
           source_type="manual"):
    row = MachineItemLedger(
        workspace_id=ws.id, machine_id=machine.id, item_id=item.id, transaction_type=ttype,
        quantity=qty, unit_cost=unit_cost, total_cost=total_cost,
        qty_before=qty_before, qty_after=qty_after, value_before=value_before, value_after=value_after,
        avg_price_before=avg_price_before, avg_price_after=avg_price_after,
        source_type=source_type, performed_by=performed_by.id, performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "inventory entry" = an inventory_ledger row
def mk_il(db, ws, itype, factory, item, ttype, performed_at, *, performed_by=None, qty=1,
          unit_cost=None, total_cost=None, qty_before=0, qty_after=0,
          avg_price_before=None, avg_price_after=None, source_type=None):
    row = InventoryLedger(
        workspace_id=ws.id, inventory_type=itype, factory_id=factory.id, item_id=item.id,
        transaction_type=ttype, quantity=qty, unit_cost=unit_cost, total_cost=total_cost,
        qty_before=qty_before, qty_after=qty_after,
        avg_price_before=avg_price_before, avg_price_after=avg_price_after,
        source_type=source_type, performed_by=(performed_by.id if performed_by else None),
        performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "project entry" = a project_component_item_ledger row
def mk_pel(db, ws, pc, item, ttype, performed_at, *, performed_by, qty=1,
           unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"), qty_before=0, qty_after=0,
           source_type="manual"):
    row = ProjectComponentItemLedger(
        workspace_id=ws.id, project_component_id=pc.id, item_id=item.id, transaction_type=ttype,
        quantity=qty, unit_cost=unit_cost, total_cost=total_cost,
        qty_before=qty_before, qty_after=qty_after, source_type=source_type,
        performed_by=performed_by.id, performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "attachment entry" = an attachment_ledger row
def mk_al(db, ws, attachment, entity_type, ttype, performed_at, *, performed_by=None):
    row = AttachmentLedger(
        workspace_id=ws.id, attachment_id=attachment.id, transaction_type=ttype, entity_type=entity_type,
        file_name=attachment.file_name, mime_type=attachment.mime_type, file_size=attachment.file_size,
        performed_by=(performed_by.id if performed_by else None), performed_at=performed_at,
    )
    db.add(row)
    db.flush()
    return row


# Convention "machine snapshot" = a machine_items row
def mk_machine_item(db, ws, machine, item, qty, *, req_qty=5, defective_qty=1):
    row = MachineItem(workspace_id=ws.id, machine_id=machine.id, item_id=item.id, qty=qty,
                       req_qty=req_qty, defective_qty=defective_qty)
    db.add(row)
    db.flush()
    return row


# Convention "inventory snapshot" = an inventory row (live unless is_deleted=True)
def mk_inventory(db, ws, factory, item, itype, qty, *, avg_price=None, is_deleted=False,
                 created_by=None, updated_by=None):
    row = Inventory(
        workspace_id=ws.id, factory_id=factory.id, item_id=item.id, inventory_type=itype,
        qty=qty, avg_price=avg_price, is_deleted=is_deleted,
        created_by=(created_by.id if created_by else None),
        updated_by=(updated_by.id if updated_by else None),
    )
    db.add(row)
    db.flush()
    return row


# Convention "Actions" wrappers (call(...) in the cases file)
def gml(db, M, machine, ws, **kw):
    return M.get_machine_ledger(db, machine.id, ws.id, **kw)


def gmb(db, M, machine, item, ws):
    return M.get_machine_balance(db, machine.id, item.id, ws.id)


def rmi(db, M, machine, item, ws, user):
    return M.reconcile_machine_item(db, machine.id, item.id, ws.id, user.id)


def pcl(db, M, pc, ws, **kw):
    return M.get_project_component_ledger(db, pc.id, ws.id, **kw)


def pct(db, M, pc, ws):
    return M.calculate_project_component_total_cost(db, pc.id, ws.id)


def gil(db, M, ws, **kw):
    return M.get_inventory_ledger(db, ws.id, **kw)


def gib(db, M, factory, item, itype, ws):
    return M.get_inventory_balance(db, factory.id, item.id, itype, ws.id)


def rinv(db, M, factory, item, itype, ws, user):
    return M.reconcile_inventory(db, factory.id, item.id, itype, ws.id, user.id)


def gal(db, M, ws, **kw):
    return M.get_attachment_ledger(db, ws.id, **kw)


def ims(db, M, item, ws, **kw):
    return M.get_item_movement_summary(db, item.id, ws.id, **kw)


def tbu(db, M, user, ws, **kw):
    return M.get_transactions_by_user(db, user.id, ws.id, **kw)


# Convention "re-read"
def reread_machine_item(db, row_id):
    db.expire_all()
    return db.get(MachineItem, row_id)


def reread_inventory(db, row_id):
    db.expire_all()
    return db.get(Inventory, row_id)


def snap_machine_item(db, row_id):
    r = reread_machine_item(db, row_id)
    return {c: getattr(r, c) for c in ("workspace_id", "machine_id", "item_id", "req_qty", "defective_qty")}


def snap_inventory(db, row_id):
    r = reread_inventory(db, row_id)
    return {c: getattr(r, c) for c in (
        "workspace_id", "factory_id", "item_id", "inventory_type", "note",
        "created_at", "created_by", "is_active", "is_deleted", "deleted_at", "deleted_by",
    )}


def mel_count(db, ws, machine, item=None):
    db.expire_all()
    q = db.query(MachineItemLedger).filter(
        MachineItemLedger.workspace_id == ws.id, MachineItemLedger.machine_id == machine.id
    )
    if item is not None:
        q = q.filter(MachineItemLedger.item_id == item.id)
    return q.count()


def il_count(db, ws, factory, item, itype):
    db.expire_all()
    return db.query(InventoryLedger).filter(
        InventoryLedger.workspace_id == ws.id, InventoryLedger.factory_id == factory.id,
        InventoryLedger.item_id == item.id, InventoryLedger.inventory_type == itype,
    ).count()


def il_workspace_count(db, ws):
    db.expire_all()
    return db.query(InventoryLedger).filter(InventoryLedger.workspace_id == ws.id).count()


def pel_count(db, ws, pc):
    db.expire_all()
    return db.query(ProjectComponentItemLedger).filter(
        ProjectComponentItemLedger.workspace_id == ws.id,
        ProjectComponentItemLedger.project_component_id == pc.id,
    ).count()


def al_count(db, ws):
    db.expire_all()
    return db.query(AttachmentLedger).filter(AttachmentLedger.workspace_id == ws.id).count()


def mae_count(db, machine):
    db.expire_all()
    return db.query(MachineActivityEvent).filter(MachineActivityEvent.machine_id == machine.id).count()


def latest_mel(db, ws, machine, item):
    db.expire_all()
    return (
        db.query(MachineItemLedger)
        .filter(MachineItemLedger.workspace_id == ws.id, MachineItemLedger.machine_id == machine.id,
                MachineItemLedger.item_id == item.id)
        .order_by(MachineItemLedger.id.desc())
        .first()
    )


def latest_il(db, ws, factory, item, itype):
    db.expire_all()
    return (
        db.query(InventoryLedger)
        .filter(InventoryLedger.workspace_id == ws.id, InventoryLedger.factory_id == factory.id,
                InventoryLedger.item_id == item.id, InventoryLedger.inventory_type == itype)
        .order_by(InventoryLedger.id.desc())
        .first()
    )


def latest_event(db, machine):
    db.expire_all()
    return (
        db.query(MachineActivityEvent)
        .filter(MachineActivityEvent.machine_id == machine.id)
        .order_by(MachineActivityEvent.id.desc())
        .first()
    )


# Convention "SQL statement listener": before_cursor_execute listener on the engine
class StatementRecorder:
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


def selects_from(statements, table):
    """Every recorded SELECT whose FROM names `table` (not `table_*`, e.g. not
    `inventory_ledger`). Fails loudly if none was recorded, so a broken
    recorder cannot pass the lock checks vacuously."""
    pat = re.compile(r"\bFROM\s+" + re.escape(table) + r"\b(?!_)", re.IGNORECASE)
    found = [s for s in statements if s.lstrip().upper().startswith("SELECT") and pat.search(s)]
    assert found, f"no {table} SELECT recorded"
    return found


def _collapse(statement):
    return re.sub(r"\s+", " ", statement).strip().lower()


def assert_exact_row_lock(statements, table):
    """Spec Gap log C1 / R11: the snapshot SELECT ends with exactly
    `FOR UPDATE OF <table>` - one FOR UPDATE, no SKIP LOCKED / NOWAIT, no lock
    on `items` (modelled on LSV-RMI-13 / LSV-RINV-15)."""
    for s in selects_from(statements, table):
        assert _collapse(s).endswith(f"for update of {table}")
        assert "SKIP LOCKED" not in s.upper()
        assert "NOWAIT" not in s.upper()
        assert _collapse(s).count("for update") == 1


# Convention "statement recorder for tie order" (BUG-640/641, revision 3 / spec
# G8): "the <table> SELECT" = every recorded SELECT whose FROM names that table
# and that has an ORDER BY. "ORDER BY ends performed_at DESC, id DESC" =
# after collapsing whitespace/case and stripping table/alias qualifiers
# (best-practice default D5), the sort keys are exactly that. For latest-entry
# ("top-1") lookups the clause must additionally be followed by LIMIT.
def _normalized_order_by(statement):
    m = re.search(r"ORDER BY\s+(.*?)(?:\s+LIMIT\b|\s+OFFSET\b|$)", statement, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    clause = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(";").strip()
    clause = re.sub(r"\b\w+\.(\w+)\b", r"\1", clause)  # strip table/alias qualifiers
    return clause.lower()


def order_by_ends_id_desc(statements, table, *, with_limit=False):
    """D4/D5: True if any recorded <table> SELECT with an ORDER BY has sort keys
    exactly 'performed_at desc, id desc' (and, for latest-entry lookups, a
    LIMIT after it). Asserts at least one such SELECT was recorded at all, so
    a broken recorder/mismatched table name fails loudly instead of silently
    reporting False."""
    pat_from = re.compile(r"\bFROM\s+" + re.escape(table) + r"\b", re.IGNORECASE)
    matches = [s for s in statements if pat_from.search(s) and re.search(r"\bORDER BY\b", s, re.IGNORECASE)]
    assert matches, f"no {table} SELECT with an ORDER BY was recorded"
    for s in matches:
        if _normalized_order_by(s) != "performed_at desc, id desc":
            continue
        if with_limit and not re.search(r"ORDER BY.*?\bLIMIT\b", s, re.IGNORECASE | re.DOTALL):
            continue
        return True
    return False


# =========================================================================== #
# LedgerManager.get_machine_ledger
# =========================================================================== #

@pytest.fixture
def ml_base(db, w1, w2, m1, m2, i1, i2, u1):
    e1 = mk_mel(db, w1, m1, i1, "transfer_in", T(1), performed_by=u1)
    e3 = mk_mel(db, w1, m1, i1, "consumption", T(2), performed_by=u1)
    e2 = mk_mel(db, w1, m1, i2, "consumption", T(3), performed_by=u1)
    e4 = mk_mel(db, w1, m2, i1, "consumption", T(4), performed_by=u1)
    e5 = mk_mel(db, w2, m1, i1, "consumption", T(5), performed_by=u1)
    return {"e1": e1, "e2": e2, "e3": e3, "e4": e4, "e5": e5}


def test_led_gml_01__happy_all_entries(db, M, ml_base, m1, w1):
    """LED-GML-01 — no filters returns all of M1's W1 entries, newest first; other machine/workspace absent.
    Rules: get_machine_ledger R6, R1."""
    b = ml_base
    result = gml(db, M, m1, w1)
    assert ids(result) == [b["e2"].id, b["e3"].id, b["e1"].id]
    assert b["e4"].id not in ids(result) and b["e5"].id not in ids(result)


def test_led_gml_02__isolation_other_workspace(db, M, ml_base, m1, w2):
    """LED-GML-02 — the same machine id scoped to W2 returns only W2's entry.
    Rules: get_machine_ledger R1."""
    b = ml_base
    assert ids(gml(db, M, m1, w2)) == [b["e5"].id]


def test_led_gml_03__item_filter(db, M, ml_base, m1, w1, i1):
    """LED-GML-03 — item_id=I1 narrows to I1's entries, newest first.
    Rules: get_machine_ledger R5."""
    b = ml_base
    assert ids(gml(db, M, m1, w1, item_id=i1.id)) == [b["e3"].id, b["e1"].id]


def test_led_gml_04__transaction_type_filter(db, M, ml_base, m1, w1):
    """LED-GML-04 — transaction_type="consumption" matches exactly, newest first.
    Rules: get_machine_ledger R4."""
    b = ml_base
    assert ids(gml(db, M, m1, w1, transaction_type="consumption")) == [b["e2"].id, b["e3"].id]


def test_led_gml_05__transaction_type_case_sensitive(db, M, ml_base, m1, w1):
    """LED-GML-05 — a case-mismatched transaction_type matches nothing.
    Rules: get_machine_ledger R4."""
    assert gml(db, M, m1, w1, transaction_type="Consumption") == []


def test_led_gml_06__item_and_type_combine(db, M, ml_base, m1, w1, i1):
    """LED-GML-06 — item_id and transaction_type combine.
    Rules: get_machine_ledger R4."""
    b = ml_base
    assert ids(gml(db, M, m1, w1, item_id=i1.id, transaction_type="consumption")) == [b["e3"].id]


def test_led_gml_07__empty_type_is_no_filter(db, M, ml_base, m1, w1):
    """LED-GML-07 — transaction_type="" applies no type filter.
    Rules: get_machine_ledger R6."""
    b = ml_base
    assert ids(gml(db, M, m1, w1, transaction_type="")) == [b["e2"].id, b["e3"].id, b["e1"].id]


def test_led_gml_08__date_range_inclusive_both_bounds(db, M, m1, w1, i1, u1):
    """LED-GML-08 — a full date range is inclusive on both ends.
    Rules: get_machine_ledger R2."""
    ea = mk_mel(db, w1, m1, i1, "consumption", T(10, "00:00:00"), performed_by=u1)
    eb = mk_mel(db, w1, m1, i1, "consumption", T(15, "12:00:00"), performed_by=u1)
    ec = mk_mel(db, w1, m1, i1, "consumption", T(20, "23:59:59"), performed_by=u1)
    ed = mk_mel(db, w1, m1, i1, "consumption", T(9, "23:59:59"), performed_by=u1)
    ee = mk_mel(db, w1, m1, i1, "consumption", T(21, "00:00:00"), performed_by=u1)
    result = gml(db, M, m1, w1, start_date=T(10, "00:00:00"), end_date=T(20, "23:59:59"))
    assert ids(result) == [ec.id, eb.id, ea.id]
    assert ed.id not in ids(result) and ee.id not in ids(result)


def test_led_gml_09__date_range_and_item_combine(db, M, m1, w1, i1, i2, u1):
    """LED-GML-09 — a full date range combines with item_id.
    Rules: get_machine_ledger R2."""
    ea = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    mk_mel(db, w1, m1, i2, "consumption", T(11), performed_by=u1)
    mk_mel(db, w1, m1, i1, "consumption", T(25), performed_by=u1)
    assert ids(gml(db, M, m1, w1, item_id=i1.id, start_date=T(5), end_date=T(20))) == [ea.id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GML_TYPE)
def test_led_gml_10__type_ignored_with_date_range(db, M, m1, w1, i1, u1):
    """LED-GML-10 — transaction_type should still combine with a full date range.
    Rules: get_machine_ledger R2 [BUG-341]."""
    ea = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    mk_mel(db, w1, m1, i1, "transfer_in", T(11), performed_by=u1)
    mk_mel(db, w1, m1, i1, "purchase_order", T(12), performed_by=u1)
    mk_mel(db, w1, m1, i1, "consumption", T(25), performed_by=u1)
    result = gml(db, M, m1, w1, start_date=T(5), end_date=T(20), transaction_type="consumption")
    assert ids(result) == [ea.id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GML_BOUND)
def test_led_gml_11__lone_start_date_ignored(db, M, m1, w1, i1, u1):
    """LED-GML-11 — start_date alone should still exclude earlier rows.
    Rules: get_machine_ledger R3 [BUG-341]."""
    mk_mel(db, w1, m1, i1, "consumption", T(9, "23:59:59"), performed_by=u1)
    eb = mk_mel(db, w1, m1, i1, "consumption", T(10, "00:00:00"), performed_by=u1)
    ec = mk_mel(db, w1, m1, i1, "consumption", T(20), performed_by=u1)
    result = gml(db, M, m1, w1, start_date=T(10, "00:00:00"))
    assert ids(result) == [ec.id, eb.id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GML_BOUND)
def test_led_gml_12__lone_end_date_ignored(db, M, m1, w1, i1, u1):
    """LED-GML-12 — end_date alone should still exclude later rows.
    Rules: get_machine_ledger R3 [BUG-341]."""
    ea = mk_mel(db, w1, m1, i1, "consumption", T(1), performed_by=u1)
    eb = mk_mel(db, w1, m1, i1, "consumption", T(10, "00:00:00"), performed_by=u1)
    mk_mel(db, w1, m1, i1, "consumption", T(10, "00:00:01"), performed_by=u1)
    result = gml(db, M, m1, w1, end_date=T(10, "00:00:00"))
    assert ids(result) == [eb.id, ea.id]


def test_led_gml_13__start_after_end_empty(db, M, ml_base, m1, w1):
    """LED-GML-13 — start_date later than end_date returns [].
    Rules: get_machine_ledger R7."""
    assert gml(db, M, m1, w1, start_date=T(3), end_date=T(1)) == []


@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_led_gml_14__ties_ordered_by_id_descending(db, M, engine, m1, w1, i1, u1):
    """LED-GML-14 — the machine_item_ledger SELECT's ORDER BY should end
    performed_at DESC, id DESC (proved from the recorded SQL, deterministic
    per spec G8); tied rows should then come back id-descending too.
    Rules: get_machine_ledger R8 [BUG-640]."""
    ea = mk_mel(db, w1, m1, i1, "consumption", T(5), performed_by=u1)
    eb = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    ec = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    ed = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = gml(db, M, m1, w1)
    assert order_by_ends_id_desc(rec.statements, "machine_item_ledger")
    assert ids(result) == [ed.id, ec.id, eb.id, ea.id]


def test_led_gml_15__filter_then_order_then_page(db, M, m1, w1, i1, i2, u1):
    """LED-GML-15 — item filter applies before ordering and paging.
    Rules: get_machine_ledger R9."""
    ps = [mk_mel(db, w1, m1, i1, "consumption", T(d), performed_by=u1) for d in range(1, 6)]
    for d in range(6, 9):
        mk_mel(db, w1, m1, i2, "consumption", T(d), performed_by=u1)
    result = gml(db, M, m1, w1, item_id=i1.id, skip=1, limit=2)
    assert ids(result) == [ps[3].id, ps[2].id]


def test_led_gml_16__limit_one(db, M, ml_base, m1, w1):
    """LED-GML-16 — limit=1 returns only the newest entry.
    Rules: get_machine_ledger R9."""
    assert ids(gml(db, M, m1, w1, limit=1)) == [ml_base["e2"].id]


def test_led_gml_17__negative_limit_raises(db, M, ml_base, m1, w1):
    """LED-GML-17 — negative limit raises DataError; nothing changes.
    Rules: get_machine_ledger Errors row."""
    with pytest.raises(DataError):
        with db.begin_nested():
            gml(db, M, m1, w1, limit=-1)
    assert mel_count(db, w1, m1) == 3


def test_led_gml_18__negative_skip_raises(db, M, ml_base, m1, w1):
    """LED-GML-18 — negative skip raises DataError; nothing changes.
    Rules: get_machine_ledger Errors row."""
    with pytest.raises(DataError):
        with db.begin_nested():
            gml(db, M, m1, w1, skip=-1)
    assert mel_count(db, w1, m1) == 3


def test_led_gml_19__unknown_machine_empty(db, M, ml_base, w1):
    """LED-GML-19 — an unknown machine id returns [] without error.
    Rules: get_machine_ledger Inputs (machine_id not checked)."""
    assert M.get_machine_ledger(db, 999999999, w1.id) == []


def test_led_gml_20__default_limit_caps_at_100(db, M, m1, w1, i1, u1):
    """LED-GML-20 — with no skip/limit given, the default caps the result at
    the 100 newest rows.
    Rules: get_machine_ledger R9, Inputs (default limit 100)."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    qs = [mk_mel(db, w1, m1, i1, "consumption", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
          for k in range(101)]
    result = gml(db, M, m1, w1)
    assert len(result) == 100
    assert ids(result) == [r.id for r in reversed(qs[1:])]
    assert qs[0].id not in ids(result)


# =========================================================================== #
# LedgerManager.get_machine_balance
# =========================================================================== #

def test_led_gmb_01__no_entries_zero(db, M, m1, i1, w1):
    """LED-GMB-01 — no entries for the bucket -> (0, Decimal('0.00')), typed.
    Rules: get_machine_balance R1."""
    qty, value = gmb(db, M, m1, i1, w1)
    assert (qty, value) == (0, Decimal("0.00"))
    assert type(qty) is int
    assert isinstance(value, Decimal)


def test_led_gmb_02__latest_by_performed_at(db, M, m1, i1, w1, u1):
    """LED-GMB-02 — latest is picked by performed_at, not insertion order.
    Rules: get_machine_balance R2."""
    mk_mel(db, w1, m1, i1, "consumption", T(9), performed_by=u1, qty_after=15, value_after=Decimal("37.50"))
    mk_mel(db, w1, m1, i1, "consumption", T(3), performed_by=u1, qty_after=5, value_after=Decimal("12.50"))
    mk_mel(db, w1, m1, i1, "consumption", T(6), performed_by=u1, qty_after=8, value_after=Decimal("20.00"))
    assert gmb(db, M, m1, i1, w1) == (15, Decimal("37.50"))


def test_led_gmb_03__null_value_after_is_zero(db, M, m1, i1, w1, u1):
    """LED-GMB-03 — the latest entry's NULL value_after reads as 0.00.
    Rules: get_machine_balance R2."""
    mk_mel(db, w1, m1, i1, "consumption", T(3), performed_by=u1, qty_after=5, value_after=Decimal("12.50"))
    mk_mel(db, w1, m1, i1, "consumption", T(9), performed_by=u1, qty_after=7, value_after=None)
    assert gmb(db, M, m1, i1, w1) == (7, Decimal("0.00"))


def test_led_gmb_04__isolation_from_decoys(db, M, m1, m2, i1, i2, w1, w2, u1):
    """LED-GMB-04 — newer entries of other machines/items/workspaces are ignored.
    Rules: get_machine_balance R2."""
    mk_mel(db, w1, m1, i1, "consumption", T(3), performed_by=u1, qty_after=5, value_after=Decimal("10.00"))
    mk_mel(db, w1, m2, i1, "consumption", T(10), performed_by=u1, qty_after=99)
    mk_mel(db, w1, m1, i2, "consumption", T(10), performed_by=u1, qty_after=98)
    mk_mel(db, w2, m1, i1, "consumption", T(10), performed_by=u1, qty_after=97)
    assert gmb(db, M, m1, i1, w1) == (5, Decimal("10.00"))


@pytest.mark.xfail(strict=True, reason=BUG_641)
def test_led_gmb_05__tie_broken_by_highest_id(db, M, engine, m1, i1, w1, u1):
    """LED-GMB-05 — the machine_item_ledger latest-entry SELECT's ORDER BY
    should end performed_at DESC, id DESC, followed by LIMIT (proved from the
    recorded SQL, deterministic per spec G8); a performed_at tie should then
    break by highest id.
    Rules: get_machine_balance R3 [BUG-641]."""
    mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1, qty_after=10, value_after=Decimal("10.00"))
    eb = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1, qty_after=20, value_after=Decimal("40.00"))
    assert eb is not None
    with StatementRecorder(engine) as rec:
        result = gmb(db, M, m1, i1, w1)
    assert order_by_ends_id_desc(rec.statements, "machine_item_ledger", with_limit=True)
    assert result == (20, Decimal("40.00"))


# =========================================================================== #
# LedgerManager.reconcile_machine_item
# =========================================================================== #

@pytest.fixture
def rm_entries(db, w1, m1, i1, u1):
    """RM-base's ledger entries only (ledger quantity 15), no snapshot."""
    ea = mk_mel(db, w1, m1, i1, "transfer_in", T(1), performed_by=u1,
                qty_after=10, avg_price_after=Decimal("2.00"), value_after=Decimal("20.00"))
    eb = mk_mel(db, w1, m1, i1, "transfer_in", T(2), performed_by=u1,
                qty_after=15, avg_price_after=Decimal("2.50"), value_after=Decimal("37.50"))
    return {"ea": ea, "eb": eb}


@pytest.fixture
def rm_base(db, w1, m1, i1, rm_entries):
    snap = mk_machine_item(db, w1, m1, i1, qty=10)
    return {**rm_entries, "snap": snap}


def test_led_rmi_01__balanced_no_writes(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-01 — snapshot already equals ledger: balanced, nothing written.
    Rules: reconcile_machine_item R6, R3."""
    snap = rm_base["snap"]
    snap.qty = 15
    db.flush()
    before = snap_machine_item(db, snap.id)
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "balanced", "ledger_qty": 15, "snapshot_qty": 15,
        "discrepancy": 0, "adjustment_created": False,
    }
    assert mel_count(db, w1, m1, i1) == 2
    assert reread_machine_item(db, snap.id).qty == 15
    assert snap_machine_item(db, snap.id) == before
    assert mae_count(db, m1) == 0


def test_led_rmi_02__no_entries_no_snapshot_bug_independent(db, M, m1, i1, w1, u1):
    """LED-RMI-02 — no entries and no snapshot: the bug-independent values are already right.
    Rules: reconcile_machine_item R4 [BUG-649]."""
    result = rmi(db, M, m1, i1, w1, u1)
    assert result["adjustment_created"] is False
    assert result["ledger_qty"] == 0
    assert result["snapshot_qty"] == 0
    assert result["discrepancy"] == 0
    assert db.query(MachineItem).filter(
        MachineItem.workspace_id == w1.id, MachineItem.machine_id == m1.id, MachineItem.item_id == i1.id
    ).first() is None
    assert mel_count(db, w1, m1, i1) == 0
    assert mae_count(db, m1) == 0


@pytest.mark.xfail(strict=True, reason=BUG_649)
def test_led_rmi_03__no_entries_no_snapshot_full_dict(db, M, m1, i1, w1, u1):
    """LED-RMI-03 — intended result is 'balanced', not 'error', with nothing to reconcile.
    Rules: reconcile_machine_item R4 [BUG-649]."""
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }


def test_led_rmi_04__no_snapshot_nonzero_ledger_error(db, M, rm_entries, m1, i1, w1, u1):
    """LED-RMI-04 — no snapshot but ledger quantity 15: reports the error dict.
    Rules: reconcile_machine_item R5."""
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15,
        "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions",
    }
    assert db.query(MachineItem).filter(
        MachineItem.workspace_id == w1.id, MachineItem.machine_id == m1.id, MachineItem.item_id == i1.id
    ).first() is None
    assert mel_count(db, w1, m1, i1) == 2
    assert mae_count(db, m1) == 0


def test_led_rmi_05__snapshot_in_other_workspace_not_found(db, M, rm_entries, m1, i1, w1, w2, u1):
    """LED-RMI-05 — a snapshot row filed under W2 is not found for W1.
    Rules: reconcile_machine_item R2, R5."""
    other = mk_machine_item(db, w2, m1, i1, qty=10)
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15,
        "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions",
    }
    assert reread_machine_item(db, other.id).qty == 10
    assert db.query(MachineItem).filter(
        MachineItem.workspace_id == w1.id, MachineItem.machine_id == m1.id, MachineItem.item_id == i1.id
    ).first() is None
    assert mel_count(db, w1, m1, i1) == 2


def test_led_rmi_06__adjusted_happy_path(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-06 — a positive discrepancy adjusts the snapshot to the ledger qty.
    Rules: reconcile_machine_item R10, R3."""
    snap = rm_base["snap"]
    before = snap_machine_item(db, snap.id)
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10,
        "discrepancy": 5, "adjustment_created": True,
    }
    assert reread_machine_item(db, snap.id).qty == 15
    assert snap_machine_item(db, snap.id) == before


def test_led_rmi_07__adjustment_row_fields_correct_today(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-07 — the new adjustment row's already-correct fields.
    Rules: reconcile_machine_item R9, R7."""
    t0 = utcnow()
    rmi(db, M, m1, i1, w1, u1)
    t1 = utcnow()
    assert mel_count(db, w1, m1, i1) == 3
    row = latest_mel(db, w1, m1, i1)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.transaction_type == "inventory_adjustment"
    assert row.unit_cost == Decimal("2.50")
    assert row.avg_price_before == Decimal("2.50")
    assert row.avg_price_after == Decimal("2.50")
    assert row.qty_after == 15
    assert row.value_after == Decimal("37.50")
    assert row.source_type == "reconciliation"
    assert row.source_id is None
    assert row.invoice_id is None
    assert row.order_type is None
    assert row.order_id is None
    assert row.transfer_source_type is None
    assert row.transfer_source_id is None
    assert row.transfer_destination_type is None
    assert row.transfer_destination_id is None
    assert row.notes == "Reconciliation adjustment: Snapshot was 10, ledger shows 15. Discrepancy: 5"
    assert row.performed_by == u1.id
    assert t0 <= row.performed_at <= t1


@pytest.mark.xfail(strict=True, reason=BUG_651)
def test_led_rmi_08__adjustment_row_keeps_chain_continuous(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-08 — the adjustment row should keep quantity 0 / qty_before=qty_after.
    Rules: reconcile_machine_item R9a [BUG-651]."""
    rmi(db, M, m1, i1, w1, u1)
    row = latest_mel(db, w1, m1, i1)
    assert row.quantity == 0
    assert row.qty_before == 15
    assert row.qty_after == 15
    assert row.total_cost == Decimal("0.00")
    assert row.value_before == Decimal("37.50")
    assert row.value_after == Decimal("37.50")


def test_led_rmi_09__activity_event_written(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-09 — one machine activity event is written on a discrepancy.
    Rules: reconcile_machine_item R10a."""
    rmi(db, M, m1, i1, w1, u1)
    assert mae_count(db, m1) == 1
    ev = latest_event(db, m1)
    assert ev.event_type == "ledger_reconciled"
    assert ev.machine_id == m1.id
    assert ev.workspace_id == w1.id
    assert ev.performed_by == u1.id
    assert ev.description == "Ledger reconciled for Bolt: snapshot 10 → 15"
    assert ev.metadata_json == {
        "item_id": i1.id, "item_name": "Bolt",
        "changes": [{"field": "qty", "label": "Quantity", "from_value": "10", "to_value": "15"}],
    }


def test_led_rmi_10__negative_discrepancy(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-10 — snapshot higher than ledger: negative discrepancy, same mechanics.
    Rules: reconcile_machine_item R10, R3, R9 (notes)."""
    snap = rm_base["snap"]
    snap.qty = 17
    db.flush()
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "adjusted", "ledger_qty": 15, "snapshot_qty": 17,
        "discrepancy": -2, "adjustment_created": True,
    }
    assert reread_machine_item(db, snap.id).qty == 15
    row = latest_mel(db, w1, m1, i1)
    assert row.qty_after == 15
    assert row.value_after == Decimal("37.50")
    assert row.notes == "Reconciliation adjustment: Snapshot was 17, ledger shows 15. Discrepancy: -2"
    ev = latest_event(db, m1)
    assert ev.description == "Ledger reconciled for Bolt: snapshot 17 → 15"


def test_led_rmi_11__empty_ledger_vs_snapshot(db, M, m1, i1, w1, u1):
    """LED-RMI-11 — no ledger entries but a snapshot with stock: adjusted to 0.
    Rules: reconcile_machine_item R7, R1."""
    snap = mk_machine_item(db, w1, m1, i1, qty=4)
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "adjusted", "ledger_qty": 0, "snapshot_qty": 4,
        "discrepancy": -4, "adjustment_created": True,
    }
    assert reread_machine_item(db, snap.id).qty == 0
    row = latest_mel(db, w1, m1, i1)
    assert row.unit_cost == Decimal("0.00")
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    assert row.total_cost == 0
    assert row.qty_after == 0
    assert row.value_after == Decimal("0.00")
    assert row.notes == "Reconciliation adjustment: Snapshot was 4, ledger shows 0. Discrepancy: -4"


@pytest.mark.xfail(strict=True, reason=BUG_650)
def test_led_rmi_12__null_avg_price_treated_as_zero(db, M, m1, i1, w1, u1):
    """LED-RMI-12 — a NULL avg_price_after on the latest entry should not crash.
    Rules: reconcile_machine_item R8 [BUG-650]."""
    mk_mel(db, w1, m1, i1, "transfer_in", T(1), performed_by=u1, qty_after=10, avg_price_after=Decimal("2.00"))
    mk_mel(db, w1, m1, i1, "transfer_in", T(2), performed_by=u1, qty_after=12, avg_price_after=None)
    mk_machine_item(db, w1, m1, i1, qty=10)
    result = rmi(db, M, m1, i1, w1, u1)
    assert result == {
        "status": "adjusted", "ledger_qty": 12, "snapshot_qty": 10,
        "discrepancy": 2, "adjustment_created": True,
    }
    row = latest_mel(db, w1, m1, i1)
    assert row.unit_cost == Decimal("0.00")
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


def test_led_rmi_13__item_name_inactive_item_included(db, M, m1, i3, w1, u1):
    """LED-RMI-13 — an inactive catalog item's name is still used.
    Rules: reconcile_machine_item R10a."""
    mk_mel(db, w1, m1, i3, "transfer_in", T(1), performed_by=u1,
           qty_after=10, avg_price_after=Decimal("2.00"), value_after=Decimal("20.00"))
    mk_mel(db, w1, m1, i3, "transfer_in", T(2), performed_by=u1,
           qty_after=15, avg_price_after=Decimal("2.50"), value_after=Decimal("37.50"))
    mk_machine_item(db, w1, m1, i3, qty=10)
    rmi(db, M, m1, i3, w1, u1)
    assert mae_count(db, m1) == 1
    ev = latest_event(db, m1)
    assert ev.description == "Ledger reconciled for Old Bolt: snapshot 10 → 15"
    assert ev.metadata_json["item_name"] == "Old Bolt"
    assert ev.metadata_json["item_id"] == i3.id


def test_led_rmi_14__item_in_other_workspace_falls_back(db, M, m1, i9, w1, u1):
    """LED-RMI-14 — an item id that belongs to W2 falls back to '#<id>'.
    Rules: reconcile_machine_item R10a."""
    mk_mel(db, w1, m1, i9, "transfer_in", T(1), performed_by=u1,
           qty_after=10, avg_price_after=Decimal("2.00"), value_after=Decimal("20.00"))
    mk_mel(db, w1, m1, i9, "transfer_in", T(2), performed_by=u1,
           qty_after=15, avg_price_after=Decimal("2.50"), value_after=Decimal("37.50"))
    mk_machine_item(db, w1, m1, i9, qty=10)
    result = rmi(db, M, m1, i9, w1, u1)
    assert result == {
        "status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10,
        "discrepancy": 5, "adjustment_created": True,
    }
    assert mae_count(db, m1) == 1
    ev = latest_event(db, m1)
    assert ev.description == f"Ledger reconciled for Item #{i9.id}: snapshot 10 → 15"
    assert ev.metadata_json["item_name"] == f"Item #{i9.id}"


def test_led_rmi_15__second_sequential_call_balanced(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-15 — calling twice in a row: the second call is balanced.
    Rules: reconcile_machine_item R11."""
    rmi(db, M, m1, i1, w1, u1)
    second = rmi(db, M, m1, i1, w1, u1)
    assert second == {
        "status": "balanced", "ledger_qty": 15, "snapshot_qty": 15,
        "discrepancy": 0, "adjustment_created": False,
    }
    assert mel_count(db, w1, m1, i1) == 3
    assert mae_count(db, m1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_643)
def test_led_rmi_16__snapshot_read_with_row_lock(db, M, engine, rm_base, m1, i1, w1, u1):
    """LED-RMI-16 — the machine_items snapshot SELECT should carry exactly FOR UPDATE OF machine_items.
    Rules: reconcile_machine_item R11 [BUG-643]."""
    with StatementRecorder(engine) as rec:
        rmi(db, M, m1, i1, w1, u1)
    assert_exact_row_lock(rec.statements, "machine_items")


@pytest.mark.xfail(strict=True, reason=BUG_651)
def test_led_rmi_17__negative_discrepancy_chain_continuous(db, M, rm_base, m1, i1, w1, u1):
    """LED-RMI-17 — a negative discrepancy should also keep the chain continuous.
    Rules: reconcile_machine_item R9a, R10 [BUG-651]."""
    snap = rm_base["snap"]
    snap.qty = 17
    db.flush()
    rmi(db, M, m1, i1, w1, u1)
    row = latest_mel(db, w1, m1, i1)
    assert row.quantity == 0
    assert row.qty_before == 15
    assert row.qty_after == 15
    assert row.total_cost == Decimal("0.00")
    assert row.value_before == Decimal("37.50")
    assert row.value_after == Decimal("37.50")


# =========================================================================== #
# LedgerManager.get_project_component_ledger
# =========================================================================== #

@pytest.fixture
def pc_base(db, w1, w2, pc1, pc2, i1, i2, u1):
    p1 = mk_pel(db, w1, pc1, i1, "consumption", T(1), performed_by=u1)
    p3 = mk_pel(db, w1, pc1, i1, "consumption", T(2), performed_by=u1)
    p2 = mk_pel(db, w1, pc1, i2, "consumption", T(3), performed_by=u1)
    p4 = mk_pel(db, w1, pc2, i1, "consumption", T(4), performed_by=u1)
    p5 = mk_pel(db, w2, pc1, i1, "consumption", T(5), performed_by=u1)
    return {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5}


def test_led_pcl_01__happy_all_entries(db, M, pc_base, pc1, w1):
    """LED-PCL-01 — no filters returns all of PC1's W1 entries, newest first.
    Rules: get_project_component_ledger R3, R1."""
    b = pc_base
    result = pcl(db, M, pc1, w1)
    assert ids(result) == [b["p2"].id, b["p3"].id, b["p1"].id]
    assert b["p4"].id not in ids(result) and b["p5"].id not in ids(result)


def test_led_pcl_02__isolation_other_workspace(db, M, pc_base, pc1, w2):
    """LED-PCL-02 — the same component id scoped to W2 returns only W2's entry.
    Rules: get_project_component_ledger R1."""
    assert ids(pcl(db, M, pc1, w2)) == [pc_base["p5"].id]


def test_led_pcl_03__item_filter(db, M, pc_base, pc1, w1, i1):
    """LED-PCL-03 — item_id=I1 narrows to I1's entries, newest first.
    Rules: get_project_component_ledger R2."""
    b = pc_base
    assert ids(pcl(db, M, pc1, w1, item_id=i1.id)) == [b["p3"].id, b["p1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_led_pcl_04__ties_ordered_by_id_descending(db, M, engine, pc1, w1, i1, u1):
    """LED-PCL-04 — the project_component_item_ledger SELECT's ORDER BY should
    end performed_at DESC, id DESC (proved from the recorded SQL, deterministic
    per spec G8); tied rows should then come back id-descending too.
    Rules: get_project_component_ledger R4 [BUG-640]."""
    pa = mk_pel(db, w1, pc1, i1, "consumption", T(5), performed_by=u1)
    pb = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    pcc = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    pd = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = pcl(db, M, pc1, w1)
    assert order_by_ends_id_desc(rec.statements, "project_component_item_ledger")
    assert ids(result) == [pd.id, pcc.id, pb.id, pa.id]


def test_led_pcl_05__filter_then_order_then_page(db, M, pc1, w1, i1, i2, u1):
    """LED-PCL-05 — item filter applies before ordering and paging.
    Rules: get_project_component_ledger R5."""
    qs = [mk_pel(db, w1, pc1, i1, "consumption", T(d), performed_by=u1) for d in range(1, 6)]
    for d in (6, 7):
        mk_pel(db, w1, pc1, i2, "consumption", T(d), performed_by=u1)
    result = pcl(db, M, pc1, w1, item_id=i1.id, skip=1, limit=2)
    assert ids(result) == [qs[3].id, qs[2].id]


def test_led_pcl_06__negative_limit_raises(db, M, pc_base, pc1, w1):
    """LED-PCL-06 — negative limit raises DataError; nothing changes.
    Rules: get_project_component_ledger Errors row."""
    with pytest.raises(DataError):
        with db.begin_nested():
            pcl(db, M, pc1, w1, limit=-1)
    assert pel_count(db, w1, pc1) == 3


def test_led_pcl_07__default_limit_caps_at_100(db, M, pc1, w1, i1, u1):
    """LED-PCL-07 — with no skip/limit given, the default caps the result at
    the 100 newest rows.
    Rules: get_project_component_ledger R5, Inputs (default limit 100)."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    qs = [mk_pel(db, w1, pc1, i1, "consumption", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
          for k in range(101)]
    result = pcl(db, M, pc1, w1)
    assert len(result) == 100
    assert ids(result) == [r.id for r in reversed(qs[1:])]
    assert qs[0].id not in ids(result)


# =========================================================================== #
# LedgerManager.calculate_project_component_total_cost
# =========================================================================== #

def _pct_item(db, ws):
    # Shared throwaway item for PCT tests (its identity is irrelevant to the sum).
    return mk_item(db, ws, "PCT Item")


def test_led_pct_01__sum_all_incoming_types(db, M, pc1, w1, u1):
    """LED-PCT-01 — the sum over several incoming types is a Decimal.
    Rules: calculate_project_component_total_cost R1."""
    item = _pct_item(db, w1)
    for ttype, cost in [
        ("purchase_order", "100.00"), ("manual_add", "50.25"), ("transfer_in", "200.00"),
        ("consumption", "10.00"), ("inventory_adjustment", "5.00"), ("cost_adjustment", "1.50"),
    ]:
        mk_pel(db, w1, pc1, item, ttype, T(1), performed_by=u1, total_cost=Decimal(cost))
    assert pct(db, M, pc1, w1) == Decimal("366.75")


def test_led_pct_02__isolation_other_component_and_workspace(db, M, pc1, pc2, w1, w2, u1):
    """LED-PCT-02 — only the given component/workspace rows are summed.
    Rules: calculate_project_component_total_cost R1."""
    item = _pct_item(db, w1)
    mk_pel(db, w1, pc1, item, "transfer_in", T(1), performed_by=u1, total_cost=Decimal("100.00"))
    mk_pel(db, w1, pc2, item, "transfer_in", T(1), performed_by=u1, total_cost=Decimal("40.00"))
    mk_pel(db, w2, pc1, item, "transfer_in", T(1), performed_by=u1, total_cost=Decimal("7.00"))
    assert pct(db, M, pc1, w1) == Decimal("100.00")


@pytest.mark.xfail(strict=True, reason=BUG_654)
def test_led_pct_03__outgoing_subtracted(db, M, pc1, w1, u1):
    """LED-PCT-03 — transfer_out should subtract, not add.
    Rules: calculate_project_component_total_cost R1 [BUG-654]."""
    item = _pct_item(db, w1)
    mk_pel(db, w1, pc1, item, "transfer_in", T(1), performed_by=u1, total_cost=Decimal("1000.00"))
    mk_pel(db, w1, pc1, item, "transfer_out", T(2), performed_by=u1, total_cost=Decimal("300.00"))
    assert pct(db, M, pc1, w1) == Decimal("700.00")


@pytest.mark.xfail(strict=True, reason=BUG_654)
def test_led_pct_04__damaged_subtracted(db, M, pc1, w1, u1):
    """LED-PCT-04 — damaged should subtract, not add.
    Rules: calculate_project_component_total_cost R1 [BUG-654]."""
    item = _pct_item(db, w1)
    mk_pel(db, w1, pc1, item, "purchase_order", T(1), performed_by=u1, total_cost=Decimal("500.00"))
    mk_pel(db, w1, pc1, item, "damaged", T(2), performed_by=u1, total_cost=Decimal("120.00"))
    assert pct(db, M, pc1, w1) == Decimal("380.00")


def test_led_pct_05__no_entries_zero(db, M, pc1, w1):
    """LED-PCT-05 — no entries for the component -> Decimal('0.00').
    Rules: calculate_project_component_total_cost R2."""
    result = pct(db, M, pc1, w1)
    assert result == Decimal("0.00")
    assert isinstance(result, Decimal)


@pytest.mark.xfail(strict=True, reason=BUG_654)
def test_led_pct_06__equal_in_and_out_nets_zero(db, M, pc1, w1, u1):
    """LED-PCT-06 — equal incoming and outgoing should net to zero.
    Rules: calculate_project_component_total_cost R2, R1 [BUG-654]."""
    item = _pct_item(db, w1)
    mk_pel(db, w1, pc1, item, "transfer_in", T(1), performed_by=u1, total_cost=Decimal("300.00"))
    mk_pel(db, w1, pc1, item, "transfer_out", T(2), performed_by=u1, total_cost=Decimal("300.00"))
    assert pct(db, M, pc1, w1) == Decimal("0.00")


def test_led_pct_07__single_zero_cost_row(db, M, pc1, w1, u1):
    """LED-PCT-07 — a single zero-cost row sums to Decimal('0.00').
    Rules: calculate_project_component_total_cost R2."""
    item = _pct_item(db, w1)
    mk_pel(db, w1, pc1, item, "consumption", T(1), performed_by=u1, total_cost=Decimal("0.00"))
    result = pct(db, M, pc1, w1)
    assert result == Decimal("0.00")
    assert isinstance(result, Decimal)


# =========================================================================== #
# LedgerManager.get_inventory_ledger
# =========================================================================== #

@pytest.fixture
def il_base(db, w1, w2, f1, f2, f9, i1, i2, i9, u1):
    n1 = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(1), performed_by=u1)
    n2 = mk_il(db, w1, DAMAGED, f1, i1, "inventory_adjustment", T(2), performed_by=u1)
    n3 = mk_il(db, w1, STORAGE, f2, i1, "inventory_adjustment", T(3), performed_by=u1)
    n4 = mk_il(db, w1, STORAGE, f1, i2, "transfer_in", T(4), performed_by=u1)
    n5 = mk_il(db, w1, WASTE, f2, i2, "inventory_adjustment", T(5), performed_by=u1)
    n9 = mk_il(db, w2, STORAGE, f9, i9, "inventory_adjustment", T(6), performed_by=u1)
    return {"n1": n1, "n2": n2, "n3": n3, "n4": n4, "n5": n5, "n9": n9}


def test_led_gil_01__happy_all_entries(db, M, il_base, w1):
    """LED-GIL-01 — no filters returns every W1 entry, newest first; W2 absent.
    Rules: get_inventory_ledger R6, R1."""
    b = il_base
    result = gil(db, M, w1)
    assert ids(result) == [b["n5"].id, b["n4"].id, b["n3"].id, b["n2"].id, b["n1"].id]
    assert b["n9"].id not in ids(result)


def test_led_gil_02__inventory_type_filter(db, M, il_base, w1):
    """LED-GIL-02 — inventory_type=DAMAGED narrows to DAMAGED entries.
    Rules: get_inventory_ledger R1, R5."""
    assert ids(gil(db, M, w1, inventory_type=DAMAGED)) == [il_base["n2"].id]


def test_led_gil_03__factory_filter(db, M, il_base, w1, f2):
    """LED-GIL-03 — factory_id=F2 narrows to F2 entries, newest first.
    Rules: get_inventory_ledger R1, R5."""
    b = il_base
    assert ids(gil(db, M, w1, factory_id=f2.id)) == [b["n5"].id, b["n3"].id]


def test_led_gil_04__item_filter(db, M, il_base, w1, i2):
    """LED-GIL-04 — item_id=I2 narrows to I2 entries, newest first.
    Rules: get_inventory_ledger R1, R5."""
    b = il_base
    assert ids(gil(db, M, w1, item_id=i2.id)) == [b["n5"].id, b["n4"].id]


def test_led_gil_05__all_scope_filters_combine(db, M, il_base, w1, f1, i1):
    """LED-GIL-05 — inventory_type/factory_id/item_id all combine.
    Rules: get_inventory_ledger R1, R5."""
    assert ids(gil(db, M, w1, inventory_type=STORAGE, factory_id=f1.id, item_id=i1.id)) == [il_base["n1"].id]


def test_led_gil_06__transaction_type_filter(db, M, il_base, w1):
    """LED-GIL-06 — transaction_type exact match, newest first.
    Rules: get_inventory_ledger R4."""
    b = il_base
    assert ids(gil(db, M, w1, transaction_type="inventory_adjustment")) == [b["n5"].id, b["n3"].id, b["n2"].id]


def test_led_gil_07__transaction_type_case_sensitive(db, M, il_base, w1):
    """LED-GIL-07 — a case-mismatched transaction_type matches nothing.
    Rules: get_inventory_ledger R4."""
    assert gil(db, M, w1, transaction_type="Inventory_Adjustment") == []


def test_led_gil_08__type_and_scope_combine(db, M, il_base, w1):
    """LED-GIL-08 — inventory_type and transaction_type combine.
    Rules: get_inventory_ledger R4, R1."""
    assert ids(gil(db, M, w1, inventory_type=STORAGE, transaction_type="inventory_adjustment")) == [il_base["n3"].id]


def test_led_gil_09__empty_type_is_no_filter(db, M, il_base, w1):
    """LED-GIL-09 — transaction_type="" applies no type filter.
    Rules: get_inventory_ledger R5."""
    b = il_base
    assert ids(gil(db, M, w1, transaction_type="")) == [b["n5"].id, b["n4"].id, b["n3"].id, b["n2"].id, b["n1"].id]


def test_led_gil_10__date_range_inclusive_both_bounds(db, M, w1, f1, i1, u1):
    """LED-GIL-10 — a full date range is inclusive on both ends.
    Rules: get_inventory_ledger R2."""
    na = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10, "00:00:00"), performed_by=u1)
    nb = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(15, "12:00:00"), performed_by=u1)
    nc = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(20, "23:59:59"), performed_by=u1)
    nd = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(9, "23:59:59"), performed_by=u1)
    ne = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(21, "00:00:00"), performed_by=u1)
    result = gil(db, M, w1, start_date=T(10, "00:00:00"), end_date=T(20, "23:59:59"))
    assert ids(result) == [nc.id, nb.id, na.id]
    assert nd.id not in ids(result) and ne.id not in ids(result)


def test_led_gil_11__date_range_and_factory_combine(db, M, il_base, w1, f1):
    """LED-GIL-11 — a full date range combines with factory_id.
    Rules: get_inventory_ledger R2, R1."""
    b = il_base
    result = gil(db, M, w1, factory_id=f1.id, start_date=T(1), end_date=T(3))
    assert ids(result) == [b["n2"].id, b["n1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GIL_TYPE)
def test_led_gil_12__type_ignored_with_date_range(db, M, il_base, w1):
    """LED-GIL-12 — transaction_type should still combine with a full date range.
    Rules: get_inventory_ledger R2 [BUG-341]."""
    b = il_base
    result = gil(db, M, w1, start_date=T(1), end_date=T(4), transaction_type="transfer_in")
    assert ids(result) == [b["n4"].id, b["n1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GIL_BOUND)
def test_led_gil_13__lone_start_date_ignored(db, M, il_base, w1):
    """LED-GIL-13 — start_date alone should still exclude earlier rows.
    Rules: get_inventory_ledger R3 [BUG-341]."""
    b = il_base
    result = gil(db, M, w1, start_date=T(4))
    assert ids(result) == [b["n5"].id, b["n4"].id]


@pytest.mark.xfail(strict=True, reason=BUG_341_GIL_BOUND)
def test_led_gil_14__lone_end_date_ignored(db, M, il_base, w1):
    """LED-GIL-14 — end_date alone should still exclude later rows.
    Rules: get_inventory_ledger R3 [BUG-341]."""
    b = il_base
    result = gil(db, M, w1, end_date=T(2))
    assert ids(result) == [b["n2"].id, b["n1"].id]


def test_led_gil_15__start_after_end_empty(db, M, il_base, w1):
    """LED-GIL-15 — start_date later than end_date returns [].
    Rules: get_inventory_ledger R7."""
    assert gil(db, M, w1, start_date=T(5), end_date=T(1)) == []


@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_led_gil_16__ties_ordered_by_id_descending(db, M, engine, w1, f1, i1, u1):
    """LED-GIL-16 — the inventory_ledger SELECT's ORDER BY should end
    performed_at DESC, id DESC (proved from the recorded SQL, deterministic
    per spec G8); tied rows should then come back id-descending too.
    Rules: get_inventory_ledger R8 [BUG-640]."""
    na = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(5), performed_by=u1)
    nb = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    nc = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    nd = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = gil(db, M, w1)
    assert order_by_ends_id_desc(rec.statements, "inventory_ledger")
    assert ids(result) == [nd.id, nc.id, nb.id, na.id]


def test_led_gil_17__filter_then_order_then_page(db, M, w1, f1, i1, i2, u1):
    """LED-GIL-17 — item filter applies before ordering and paging.
    Rules: get_inventory_ledger R9."""
    qs = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(d), performed_by=u1) for d in range(1, 6)]
    for d in (6, 7):
        mk_il(db, w1, STORAGE, f1, i2, "transfer_in", T(d), performed_by=u1)
    result = gil(db, M, w1, item_id=i1.id, skip=1, limit=2)
    assert ids(result) == [qs[3].id, qs[2].id]


def test_led_gil_18__negative_limit_raises(db, M, il_base, w1):
    """LED-GIL-18 — negative limit raises DataError; nothing changes.
    Rules: get_inventory_ledger Errors row."""
    with pytest.raises(DataError):
        with db.begin_nested():
            gil(db, M, w1, limit=-1)
    assert il_workspace_count(db, w1) == 5


def test_led_gil_19__default_limit_caps_at_100(db, M, w1, f1, i1, u1):
    """LED-GIL-19 — with no skip/limit given, the default caps the result at
    the 100 newest rows.
    Rules: get_inventory_ledger R9, Inputs (default limit 100)."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    qs = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
          for k in range(101)]
    result = gil(db, M, w1)
    assert len(result) == 100
    assert ids(result) == [r.id for r in reversed(qs[1:])]
    assert qs[0].id not in ids(result)


# =========================================================================== #
# LedgerManager.get_inventory_balance
# =========================================================================== #

def test_led_gib_01__no_entries_zero(db, M, f1, i1, w1):
    """LED-GIB-01 — no entries for the bucket -> (0, Decimal('0.00')).
    Rules: get_inventory_balance R1."""
    assert gib(db, M, f1, i1, STORAGE, w1) == (0, Decimal("0.00"))


def test_led_gib_02__decoys_only_zero(db, M, f1, f2, i1, i2, w1, w2, u1):
    """LED-GIB-02 — only decoy entries exist; the exact bucket is still empty.
    Rules: get_inventory_balance R2, R1."""
    mk_il(db, w1, DAMAGED, f1, i1, "transfer_in", T(10), performed_by=u1, qty_after=9)
    mk_il(db, w1, STORAGE, f2, i1, "transfer_in", T(10), performed_by=u1, qty_after=8)
    mk_il(db, w1, STORAGE, f1, i2, "transfer_in", T(10), performed_by=u1, qty_after=7)
    mk_il(db, w2, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1, qty_after=6)
    assert gib(db, M, f1, i1, STORAGE, w1) == (0, Decimal("0.00"))


def test_led_gib_03__latest_qty_and_value(db, M, f1, i1, w1, u1):
    """LED-GIB-03 — the latest entry's qty_after and computed value.
    Rules: get_inventory_balance R2 [BUG-655]."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(9), performed_by=u1,
          qty_after=50, avg_price_after=Decimal("5.00"))
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(3), performed_by=u1,
          qty_after=20, avg_price_after=Decimal("4.00"))
    assert gib(db, M, f1, i1, STORAGE, w1) == (50, Decimal("250.00"))


def test_led_gib_04__null_avg_price_is_zero_value(db, M, f1, i1, w1, u1):
    """LED-GIB-04 — a NULL avg_price_after on the latest entry gives value 0.00.
    Rules: get_inventory_balance R2 [BUG-655]."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(3), performed_by=u1,
          qty_after=20, avg_price_after=Decimal("4.00"))
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(9), performed_by=u1,
          qty_after=30, avg_price_after=None)
    assert gib(db, M, f1, i1, STORAGE, w1) == (30, Decimal("0.00"))


def test_led_gib_05__isolation_from_decoys(db, M, f1, f2, i1, i2, w1, w2, u1):
    """LED-GIB-05 — newer entries of other type/factory/item/workspace are ignored.
    Rules: get_inventory_balance R2 [BUG-655]."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(3), performed_by=u1,
          qty_after=12, avg_price_after=Decimal("2.00"))
    mk_il(db, w1, DAMAGED, f1, i1, "transfer_in", T(10), performed_by=u1, qty_after=99)
    mk_il(db, w1, STORAGE, f2, i1, "transfer_in", T(10), performed_by=u1, qty_after=98)
    mk_il(db, w1, STORAGE, f1, i2, "transfer_in", T(10), performed_by=u1, qty_after=97)
    mk_il(db, w2, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1, qty_after=96)
    assert gib(db, M, f1, i1, STORAGE, w1) == (12, Decimal("24.00"))


def test_led_gib_06__tie_broken_by_highest_id(db, M, engine, f1, i1, w1, u1):
    """LED-GIB-06 — the inventory_ledger latest-entry SELECT's ORDER BY should
    end performed_at DESC, id DESC, followed by LIMIT (proved from the recorded
    SQL; the call crashes on BUG-655 before this can ever XPASS, so it stays
    deterministic); a performed_at tie should then break by highest id.
    Rules: get_inventory_balance R3 [BUG-641] (and BUG-655)."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1,
          qty_after=10, avg_price_after=Decimal("1.00"))
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1,
          qty_after=20, avg_price_after=Decimal("2.00"))
    with StatementRecorder(engine) as rec:
        result = gib(db, M, f1, i1, STORAGE, w1)
    assert order_by_ends_id_desc(rec.statements, "inventory_ledger", with_limit=True)
    assert result == (20, Decimal("40.00"))


# =========================================================================== #
# LedgerManager.reconcile_inventory
# =========================================================================== #

@pytest.fixture
def ri_empty(db, f1, i1, w1, u1):
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=5, avg_price=Decimal("3.00"),
                         created_by=u1, updated_by=u1)
    return {"snap": snap}


@pytest.fixture
def ri_hist(db, f1, i1, w1, u1):
    na = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(1), performed_by=u1,
               qty_after=10, avg_price_after=Decimal("2.00"))
    nb = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(2), performed_by=u1,
               qty_after=15, avg_price_after=Decimal("2.50"))
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=10, avg_price=Decimal("2.00"), updated_by=u1)
    return {"na": na, "nb": nb, "snap": snap}


def test_led_rinv_01__no_entries_no_snapshot_bug_independent(db, M, f1, i1, w1, u2):
    """LED-RINV-01 — no entries and no snapshot: the bug-independent values are already right.
    Rules: reconcile_inventory R4 [BUG-649]."""
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result["adjustment_created"] is False
    assert result["ledger_qty"] == 0
    assert result["snapshot_qty"] == 0
    assert result["discrepancy"] == 0
    assert db.query(Inventory).filter(
        Inventory.workspace_id == w1.id, Inventory.factory_id == f1.id,
        Inventory.item_id == i1.id, Inventory.inventory_type == STORAGE,
    ).first() is None
    assert il_count(db, w1, f1, i1, STORAGE) == 0


@pytest.mark.xfail(strict=True, reason=BUG_649)
def test_led_rinv_02__no_entries_no_snapshot_full_dict(db, M, f1, i1, w1, u2):
    """LED-RINV-02 — intended result is 'balanced', not 'error'.
    Rules: reconcile_inventory R4 [BUG-649]."""
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }


def test_led_rinv_03__soft_deleted_snapshot_counts_as_missing(db, M, ri_empty, f1, i1, w1, u1, u2):
    """LED-RINV-03 — a soft-deleted snapshot is treated as missing; nothing changes.
    Rules: reconcile_inventory R2."""
    snap = ri_empty["snap"]
    snap.is_deleted = True
    db.flush()
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result["adjustment_created"] is False
    assert result["ledger_qty"] == 0
    assert result["snapshot_qty"] == 0
    assert result["discrepancy"] == 0
    reread = reread_inventory(db, snap.id)
    assert reread.is_deleted is True
    assert reread.qty == 5
    assert reread.avg_price == Decimal("3.00")
    assert reread.updated_by == u1.id
    assert il_count(db, w1, f1, i1, STORAGE) == 0


@pytest.mark.xfail(strict=True, reason=BUG_649)
def test_led_rinv_04__soft_deleted_snapshot_full_dict(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-04 — intended result for a soft-deleted snapshot is 'balanced'.
    Rules: reconcile_inventory R2, R4 [BUG-649]."""
    ri_empty["snap"].is_deleted = True
    db.flush()
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }


def test_led_rinv_05__isolation_from_other_bucket_and_workspace(db, M, f1, i1, w1, w2, u1, u2):
    """LED-RINV-05 — snapshots of another type/workspace are untouched and not matched.
    Rules: reconcile_inventory R2."""
    sd = mk_inventory(db, w1, f1, i1, DAMAGED, qty=4, updated_by=u1)
    sw = mk_inventory(db, w2, f1, i1, STORAGE, qty=6, updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result["adjustment_created"] is False
    assert result["ledger_qty"] == 0
    assert result["snapshot_qty"] == 0
    assert result["discrepancy"] == 0
    assert reread_inventory(db, sd.id).qty == 4
    assert reread_inventory(db, sw.id).qty == 6
    assert il_count(db, w1, f1, i1, STORAGE) == 0


@pytest.mark.xfail(strict=True, reason=BUG_655)
def test_led_rinv_06__no_snapshot_nonzero_ledger_error(db, M, ri_hist, f1, i1, w1, u2):
    """LED-RINV-06 — ledger history without a snapshot should report the error dict.
    Rules: reconcile_inventory R5, R1 [BUG-655]."""
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15,
        "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions",
    }
    assert db.query(Inventory).filter(
        Inventory.workspace_id == w1.id, Inventory.factory_id == f1.id,
        Inventory.item_id == i1.id, Inventory.inventory_type == STORAGE,
    ).first() is None
    assert il_count(db, w1, f1, i1, STORAGE) == 2


def test_led_rinv_07__balanced_with_history(db, M, ri_hist, f1, i1, w1, u1, u2):
    """LED-RINV-07 — snapshot matching ledger qty/price with history: balanced.
    Rules: reconcile_inventory R6, R1 [BUG-655]."""
    snap = ri_hist["snap"]
    snap.qty = 15
    snap.avg_price = Decimal("2.50")
    db.flush()
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "balanced", "ledger_qty": 15, "snapshot_qty": 15,
        "discrepancy": 0, "adjustment_created": False,
    }
    assert il_count(db, w1, f1, i1, STORAGE) == 2
    assert reread_inventory(db, snap.id).updated_by == u1.id


def test_led_rinv_08__adjusted_happy_path_empty_ledger(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-08 — an empty ledger with snapshot stock: adjusted down to 0.
    Rules: reconcile_inventory R10, R7, R3."""
    snap = ri_empty["snap"]
    before = snap_inventory(db, snap.id)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 0, "snapshot_qty": 5,
        "discrepancy": -5, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 0
    assert reread.avg_price == Decimal("0.00")
    assert reread.is_deleted is False
    assert reread.factory_id == f1.id
    assert reread.item_id == i1.id
    assert reread.inventory_type == STORAGE
    assert reread.workspace_id == w1.id
    # other recorded columns (except updated_by/updated_at) unchanged
    assert snap_inventory(db, snap.id) == before
    assert db.query(MachineActivityEvent).count() == 0


@pytest.mark.xfail(strict=True, reason=BUG_652)
def test_led_rinv_09__updated_by_set_to_reconciling_user(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-09 — updated_by should become the reconciling user.
    Rules: reconcile_inventory R10 [BUG-652]."""
    snap = ri_empty["snap"]
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert reread_inventory(db, snap.id).updated_by == u2.id


def test_led_rinv_10__adjustment_row_fields_correct_today(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-10 — the new adjustment row's already-correct fields; performed_at is DB now().
    Rules: reconcile_inventory R9, R7."""
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    db_now = db.execute(text("SELECT now()::timestamp")).scalar()
    assert il_count(db, w1, f1, i1, STORAGE) == 1
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.workspace_id == w1.id
    assert row.inventory_type == STORAGE
    assert row.factory_id == f1.id
    assert row.item_id == i1.id
    assert row.transaction_type == "inventory_adjustment"
    assert row.unit_cost == Decimal("0.00")
    assert row.total_cost == Decimal("0.00")
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")
    assert row.qty_after == 0
    assert row.source_type == "reconciliation"
    assert row.source_id is None
    assert row.transfer_source_type is None
    assert row.transfer_source_id is None
    assert row.transfer_destination_type is None
    assert row.transfer_destination_id is None
    assert row.performed_by == u2.id
    assert row.performed_at == db_now
    assert row.notes.startswith("Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5")


@pytest.mark.xfail(strict=True, reason=BUG_651)
def test_led_rinv_11__adjustment_row_keeps_chain_continuous(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-11 — the adjustment row should keep quantity 0 / qty_before=qty_after.
    Rules: reconcile_inventory R9a [BUG-651]."""
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.quantity == 0
    assert row.qty_before == 0
    assert row.qty_after == 0
    assert row.total_cost == Decimal("0.00")


@pytest.mark.xfail(strict=True, reason=BUG_655)
def test_led_rinv_12__adjusted_with_history(db, M, ri_hist, f1, i1, w1, u1, u2):
    """LED-RINV-12 — a full correction with ledger history (qty + avg_price + notes).
    Rules: reconcile_inventory R3, R9, R9a, R9b, R10, R1 [BUG-655, BUG-651, BUG-652]."""
    snap = ri_hist["snap"]
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10,
        "discrepancy": 5, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 15
    assert reread.avg_price == Decimal("2.50")
    assert reread.updated_by == u2.id
    assert il_count(db, w1, f1, i1, STORAGE) == 3
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.quantity == 0
    assert row.qty_before == 15
    assert row.qty_after == 15
    assert row.unit_cost == Decimal("2.50")
    assert row.total_cost == Decimal("0.00")
    assert row.avg_price_before == Decimal("2.50")
    assert row.avg_price_after == Decimal("2.50")
    assert row.notes == (
        "Reconciliation adjustment: Snapshot was 10, ledger shows 15. Discrepancy: 5. "
        "Avg price: snapshot was 2.00, ledger shows 2.50"
    )


@pytest.mark.xfail(strict=True, reason=f"{BUG_653} (and {BUG_655.split(':')[0]})")
def test_led_rinv_13__avg_price_only_mismatch_with_history(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-13 — quantities match but avg_price differs: should still be 'adjusted'.
    Rules: reconcile_inventory R6a, R3, R9, R9b, R10 [BUG-653]."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(1), performed_by=u1,
          qty_after=10, avg_price_after=Decimal("6.50"))
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=10, avg_price=Decimal("5.00"), updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 10, "snapshot_qty": 10,
        "discrepancy": 0, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 10
    assert reread.avg_price == Decimal("6.50")
    assert reread.updated_by == u2.id
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.transaction_type == "inventory_adjustment"
    assert row.quantity == 0
    assert row.qty_before == 10
    assert row.qty_after == 10
    assert row.avg_price_before == Decimal("6.50")
    assert row.avg_price_after == Decimal("6.50")
    assert row.unit_cost == Decimal("6.50")
    assert row.source_type == "reconciliation"
    assert row.notes == (
        "Reconciliation adjustment: Snapshot was 10, ledger shows 10. Discrepancy: 0. "
        "Avg price: snapshot was 5.00, ledger shows 6.50"
    )


@pytest.mark.xfail(strict=True, reason=f"{BUG_650} (and {BUG_655.split(':')[0]})")
def test_led_rinv_14__null_avg_price_treated_as_zero(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-14 — a NULL avg_price_after on the latest entry should not crash.
    Rules: reconcile_inventory R8 [BUG-650]."""
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(1), performed_by=u1,
          qty_after=10, avg_price_after=Decimal("4.00"))
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(2), performed_by=u1,
          qty_after=12, avg_price_after=None)
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=10, avg_price=Decimal("4.00"), updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 12, "snapshot_qty": 10,
        "discrepancy": 2, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 12
    assert reread.avg_price == Decimal("0.00")
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.unit_cost == Decimal("0.00")
    assert row.avg_price_before == Decimal("0.00")
    assert row.avg_price_after == Decimal("0.00")


@pytest.mark.xfail(strict=True, reason=BUG_653)
def test_led_rinv_15__avg_price_only_mismatch_empty_ledger(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-15 — an empty ledger but a nonzero snapshot avg_price: should be 'adjusted'.
    Rules: reconcile_inventory R6a, R7, R9b [BUG-653]."""
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=0, avg_price=Decimal("5.00"), updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 0
    assert reread.avg_price == Decimal("0.00")
    assert reread.updated_by == u2.id
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.quantity == 0
    assert row.qty_before == 0
    assert row.qty_after == 0
    assert row.notes == (
        "Reconciliation adjustment: Snapshot was 0, ledger shows 0. Discrepancy: 0. "
        "Avg price: snapshot was 5.00, ledger shows 0.00"
    )


def test_led_rinv_16__second_sequential_call_balanced(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-16 — calling twice in a row: the second call should be balanced.
    Rules: reconcile_inventory R11 [BUG-655]."""
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    second = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert second == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }
    assert il_count(db, w1, f1, i1, STORAGE) == 1


@pytest.mark.xfail(strict=True, reason=BUG_644)
def test_led_rinv_17__snapshot_read_with_row_lock(db, M, engine, ri_empty, f1, i1, w1, u2):
    """LED-RINV-17 — the inventory snapshot SELECT should carry exactly FOR UPDATE OF inventory.
    Rules: reconcile_inventory R11 [BUG-644]."""
    with StatementRecorder(engine) as rec:
        rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert_exact_row_lock(rec.statements, "inventory")


@pytest.mark.xfail(strict=True, reason=BUG_651)
def test_led_rinv_18__notes_include_avg_price_suffix(db, M, ri_empty, f1, i1, w1, u2):
    """LED-RINV-18 — notes should always include the avg-price sentence.
    Rules: reconcile_inventory R9b [BUG-651]."""
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.notes == (
        "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5. "
        "Avg price: snapshot was 3.00, ledger shows 0.00"
    )


def test_led_rinv_19__null_snapshot_avg_price_with_qty_discrepancy(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-19 — a NULL snapshot avg_price does not break the normal qty correction.
    Rules: reconcile_inventory R6a, R10, R9."""
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=5, avg_price=None, updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "adjusted", "ledger_qty": 0, "snapshot_qty": 5,
        "discrepancy": -5, "adjustment_created": True,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 0
    assert reread.avg_price == Decimal("0.00")
    assert il_count(db, w1, f1, i1, STORAGE) == 1
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.notes.startswith("Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5")


@pytest.mark.xfail(strict=True, reason=BUG_651)
def test_led_rinv_20__null_snapshot_avg_price_notes_suffix(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-20 — a NULL snapshot avg_price is written as 0.00 in the avg-price sentence.
    Rules: reconcile_inventory R9b [BUG-651]."""
    mk_inventory(db, w1, f1, i1, STORAGE, qty=5, avg_price=None, updated_by=u1)
    rinv(db, M, f1, i1, STORAGE, w1, u2)
    row = latest_il(db, w1, f1, i1, STORAGE)
    assert row.notes == (
        "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5. "
        "Avg price: snapshot was 0.00, ledger shows 0.00"
    )


def test_led_rinv_21__null_avg_price_and_empty_ledger_balanced(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-21 — qty matches and a NULL snapshot avg_price compares as 0.00: balanced.
    Rules: reconcile_inventory R6a, R6."""
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=0, avg_price=None, updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 0
    assert reread.avg_price is None
    assert reread.updated_by == u1.id
    assert il_count(db, w1, f1, i1, STORAGE) == 0


def test_led_rinv_22__zero_avg_price_and_empty_ledger_balanced(db, M, f1, i1, w1, u1, u2):
    """LED-RINV-22 — qty matches and an explicit 0.00 snapshot avg_price: balanced.
    Rules: reconcile_inventory R6a, R6."""
    snap = mk_inventory(db, w1, f1, i1, STORAGE, qty=0, avg_price=Decimal("0.00"), updated_by=u1)
    result = rinv(db, M, f1, i1, STORAGE, w1, u2)
    assert result == {
        "status": "balanced", "ledger_qty": 0, "snapshot_qty": 0,
        "discrepancy": 0, "adjustment_created": False,
    }
    reread = reread_inventory(db, snap.id)
    assert reread.qty == 0
    assert reread.avg_price == Decimal("0.00")
    assert reread.updated_by == u1.id
    assert il_count(db, w1, f1, i1, STORAGE) == 0


# =========================================================================== #
# LedgerManager.get_attachment_ledger
# =========================================================================== #

@pytest.fixture
def al_base(db, w1, w2, a1, a2, a9, u1):
    g1 = mk_al(db, w1, a1, "project", "ready", TA(1), performed_by=u1)
    g2 = mk_al(db, w1, a1, "project", "deleted", TA(2), performed_by=u1)
    g3 = mk_al(db, w1, a2, "machine", "ready", TA(3), performed_by=u1)
    g4 = mk_al(db, w1, a2, "project", "ready", TA(4), performed_by=u1)
    g9 = mk_al(db, w2, a9, "project", "ready", TA(5), performed_by=u1)
    return {"g1": g1, "g2": g2, "g3": g3, "g4": g4, "g9": g9}


def test_led_gal_01__happy_all_entries(db, M, al_base, w1):
    """LED-GAL-01 — no filters returns every W1 entry, newest first; W2 absent.
    Rules: get_attachment_ledger R4, R1."""
    b = al_base
    result = gal(db, M, w1)
    assert ids(result) == [b["g4"].id, b["g3"].id, b["g2"].id, b["g1"].id]
    assert b["g9"].id not in ids(result)


def test_led_gal_02__attachment_id_filter(db, M, al_base, w1, a1):
    """LED-GAL-02 — attachment_id=A1 narrows to A1's entries, newest first.
    Rules: get_attachment_ledger R2."""
    b = al_base
    assert ids(gal(db, M, w1, attachment_id=a1.id)) == [b["g2"].id, b["g1"].id]


def test_led_gal_03__entity_type_filter(db, M, al_base, w1):
    """LED-GAL-03 — entity_type="machine" narrows to machine entries.
    Rules: get_attachment_ledger R2."""
    assert ids(gal(db, M, w1, entity_type="machine")) == [al_base["g3"].id]


def test_led_gal_04__entity_type_case_sensitive(db, M, al_base, w1):
    """LED-GAL-04 — a case-mismatched entity_type matches nothing.
    Rules: get_attachment_ledger R2."""
    assert gal(db, M, w1, entity_type="Machine") == []


def test_led_gal_05__transaction_type_filter(db, M, al_base, w1):
    """LED-GAL-05 — transaction_type="deleted" narrows to deleted entries.
    Rules: get_attachment_ledger R2."""
    assert ids(gal(db, M, w1, transaction_type="deleted")) == [al_base["g2"].id]


def test_led_gal_06__all_filters_combine(db, M, al_base, w1, a2):
    """LED-GAL-06 — attachment_id/entity_type/transaction_type all combine.
    Rules: get_attachment_ledger R2, R4."""
    b = al_base
    result = gal(db, M, w1, attachment_id=a2.id, entity_type="project", transaction_type="ready")
    assert ids(result) == [b["g4"].id]


def test_led_gal_07__empty_filters_are_no_filter(db, M, al_base, w1):
    """LED-GAL-07 — entity_type="" and transaction_type="" apply no filter.
    Rules: get_attachment_ledger R2, R4."""
    b = al_base
    result = gal(db, M, w1, entity_type="", transaction_type="")
    assert ids(result) == [b["g4"].id, b["g3"].id, b["g2"].id, b["g1"].id]


def test_led_gal_08__lone_start_date(db, M, w1, a1, u1):
    """LED-GAL-08 — start_date alone restricts to performed_at >= start_date.
    Rules: get_attachment_ledger R3."""
    mk_al(db, w1, a1, "project", "ready", TA(9, "23:59:59"), performed_by=u1)
    gb = mk_al(db, w1, a1, "project", "ready", TA(10, "00:00:00"), performed_by=u1)
    gc = mk_al(db, w1, a1, "project", "ready", TA(20), performed_by=u1)
    result = gal(db, M, w1, start_date=TA(10, "00:00:00"))
    assert ids(result) == [gc.id, gb.id]


def test_led_gal_09__lone_end_date(db, M, w1, a1, u1):
    """LED-GAL-09 — end_date alone restricts to performed_at <= end_date.
    Rules: get_attachment_ledger R3."""
    ga = mk_al(db, w1, a1, "project", "ready", TA(1), performed_by=u1)
    gb = mk_al(db, w1, a1, "project", "ready", TA(10, "00:00:00"), performed_by=u1)
    mk_al(db, w1, a1, "project", "ready", TA(10, "00:00:01"), performed_by=u1)
    result = gal(db, M, w1, end_date=TA(10, "00:00:00"))
    assert ids(result) == [gb.id, ga.id]


@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_led_gal_10__ties_ordered_by_id_descending(db, M, engine, w1, a1, u1):
    """LED-GAL-10 — the attachment_ledger SELECT's ORDER BY should end
    performed_at DESC, id DESC (proved from the recorded SQL, deterministic
    per spec G8); tied rows should then come back id-descending too.
    Rules: get_attachment_ledger R5 [BUG-640]."""
    ga = mk_al(db, w1, a1, "project", "ready", TA(5), performed_by=u1)
    gb = mk_al(db, w1, a1, "project", "ready", TA(10), performed_by=u1)
    gc = mk_al(db, w1, a1, "project", "ready", TA(10), performed_by=u1)
    gd = mk_al(db, w1, a1, "project", "ready", TA(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = gal(db, M, w1)
    assert order_by_ends_id_desc(rec.statements, "attachment_ledger")
    assert ids(result) == [gd.id, gc.id, gb.id, ga.id]


def test_led_gal_11__inclusive_bounds_combined_with_paging(db, M, w1, a1, u1):
    """LED-GAL-11 — inclusive date bounds combine correctly with skip/limit.
    Rules: get_attachment_ledger R3, R6."""
    qs = [mk_al(db, w1, a1, "project", "ready", TA(d), performed_by=u1) for d in range(1, 6)]
    ga = mk_al(db, w1, a1, "project", "ready", TA(9, "23:59:59"), performed_by=u1)
    gz = mk_al(db, w1, a1, "project", "ready", TA(10, "00:00:00"), performed_by=u1)
    result = gal(db, M, w1, start_date=TA(2), end_date=TA(10, "00:00:00"), skip=1, limit=2)
    assert ids(result) == [ga.id, qs[4].id]
    assert gz.id not in ids(result)


def test_led_gal_12__negative_limit_raises(db, M, al_base, w1):
    """LED-GAL-12 — negative limit raises DataError; nothing changes.
    Rules: get_attachment_ledger Errors row."""
    with pytest.raises(DataError):
        with db.begin_nested():
            gal(db, M, w1, limit=-1)
    assert al_count(db, w1) == 4


def test_led_gal_13__default_limit_caps_at_100(db, M, w1, a1, u1):
    """LED-GAL-13 — with no skip/limit given, the default caps the result at
    the 100 newest rows.
    Rules: get_attachment_ledger R6, Inputs (default limit 100)."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    qs = [mk_al(db, w1, a1, "project", "ready", base.replace(minute=k % 60, hour=k // 60, tzinfo=timezone.utc),
                performed_by=u1)
          for k in range(101)]
    result = gal(db, M, w1)
    assert len(result) == 100
    assert ids(result) == [r.id for r in reversed(qs[1:])]
    assert qs[0].id not in ids(result)


# =========================================================================== #
# LedgerManager.get_item_movement_summary
# =========================================================================== #

@pytest.fixture
def im_base(db, w1, w2, m1, m2, m9, f1, f2, f9, i1, u1):
    xm1 = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    xm2 = mk_mel(db, w1, m2, i1, "consumption", T(12), performed_by=u1)
    xn1 = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(11), performed_by=u1)
    xn2 = mk_il(db, w1, DAMAGED, f2, i1, "inventory_adjustment", T(13), performed_by=u1)
    mk_mel(db, w2, m9, i1, "consumption", T(11), performed_by=u1)
    mk_il(db, w2, STORAGE, f9, i1, "inventory_adjustment", T(11), performed_by=u1)
    return {"xm1": xm1, "xm2": xm2, "xn1": xn1, "xn2": xn2}


def test_led_ims_01__happy_date_range_given(db, M, im_base, i1, w1):
    """LED-IMS-01 — with both dates given, machine/inventory already work; keys exactly machine/project/inventory.
    Rules: get_item_movement_summary R2, R3, R6."""
    b = im_base
    result = ims(db, M, i1, w1, start_date=T(1), end_date=T(30))
    assert set(result.keys()) == {"machine", "project", "inventory"}
    assert ids(result["machine"]) == [b["xm2"].id, b["xm1"].id]
    assert ids(result["inventory"]) == [b["xn2"].id, b["xn1"].id]
    assert result["project"] == []


def test_led_ims_02__inclusive_date_bounds(db, M, m1, f1, i1, w1, u1):
    """LED-IMS-02 — date bounds are inclusive for both machine and inventory lists.
    Rules: get_item_movement_summary R1, R2, R3."""
    times = [T(10, "00:00:00"), T(20, "23:59:59"), T(9, "23:59:59"), T(21, "00:00:00")]
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", t, performed_by=u1) for t in times]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", t, performed_by=u1) for t in times]
    result = ims(db, M, i1, w1, start_date=T(10, "00:00:00"), end_date=T(20, "23:59:59"))
    assert ids(result["machine"]) == [m_rows[1].id, m_rows[0].id]
    assert ids(result["inventory"]) == [n_rows[1].id, n_rows[0].id]


@pytest.mark.xfail(strict=True, reason=BUG_341_IMS_ITEM)
def test_led_ims_03__item_filter_not_applied(db, M, im_base, m1, f1, i1, i2, w1, u1):
    """LED-IMS-03 — another item's entries within range should not appear.
    Rules: get_item_movement_summary R2, R3 [BUG-341]."""
    b = im_base
    mk_mel(db, w1, m1, i2, "consumption", T(14), performed_by=u1)
    mk_il(db, w1, STORAGE, f1, i2, "transfer_in", T(14), performed_by=u1)
    result = ims(db, M, i1, w1, start_date=T(1), end_date=T(30))
    assert ids(result["machine"]) == [b["xm2"].id, b["xm1"].id]
    assert ids(result["inventory"]) == [b["xn2"].id, b["xn1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_646)
def test_led_ims_04__no_dates_should_run_unbounded(db, M, im_base, i1, w1):
    """LED-IMS-04 — no dates given should still run (unbounded), not short-circuit to [].
    Rules: get_item_movement_summary R1, R2, R3 [BUG-646]."""
    b = im_base
    result = ims(db, M, i1, w1)
    assert ids(result["machine"]) == [b["xm2"].id, b["xm1"].id]
    assert ids(result["inventory"]) == [b["xn2"].id, b["xn1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_646)
def test_led_ims_05__lone_start_date_should_apply(db, M, im_base, i1, w1):
    """LED-IMS-05 — start_date alone should restrict the lists.
    Rules: get_item_movement_summary R1, R2, R3 [BUG-646]."""
    b = im_base
    result = ims(db, M, i1, w1, start_date=T(12))
    assert ids(result["machine"]) == [b["xm2"].id]
    assert ids(result["inventory"]) == [b["xn2"].id]


@pytest.mark.xfail(strict=True, reason=BUG_646)
def test_led_ims_06__lone_end_date_should_apply(db, M, im_base, i1, w1):
    """LED-IMS-06 — end_date alone should restrict the lists.
    Rules: get_item_movement_summary R1, R2, R3 [BUG-646]."""
    b = im_base
    result = ims(db, M, i1, w1, end_date=T(11))
    assert ids(result["machine"]) == [b["xm1"].id]
    assert ids(result["inventory"]) == [b["xn1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_led_ims_07__ties_ordered_by_id_descending(db, M, engine, m1, f1, i1, w1, u1):
    """LED-IMS-07 — the machine_item_ledger and inventory_ledger SELECTs' ORDER
    BY should each end performed_at DESC, id DESC (proved from the recorded
    SQL, deterministic per spec G8, replacing the earlier flaky data-only
    check — see notes Revision history); tied rows should then come back
    id-descending in both lists too.
    Rules: get_item_movement_summary R4 [BUG-640]."""
    xa = mk_mel(db, w1, m1, i1, "consumption", T(5), performed_by=u1)
    xb = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    xc = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    xd = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    na = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(5), performed_by=u1)
    nb = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    nc = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    nd = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = ims(db, M, i1, w1, start_date=T(1), end_date=T(30))
    assert order_by_ends_id_desc(rec.statements, "machine_item_ledger")
    assert order_by_ends_id_desc(rec.statements, "inventory_ledger")
    assert ids(result["machine"]) == [xd.id, xc.id, xb.id, xa.id]
    assert ids(result["inventory"]) == [nd.id, nc.id, nb.id, na.id]


def test_led_ims_08__default_cap_at_100(db, M, m1, f1, i1, w1, u1):
    """LED-IMS-08 — with 101 entries, the default cap keeps only the 100 newest.
    Rules: get_item_movement_summary R4a."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
              for k in range(101)]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
              for k in range(101)]
    result = ims(db, M, i1, w1, start_date=T(1, "00:00:00"), end_date=T(30))
    assert len(result["machine"]) == 100
    assert len(result["inventory"]) == 100
    assert ids(result["machine"]) == [r.id for r in reversed(m_rows[1:])]
    assert ids(result["inventory"]) == [r.id for r in reversed(n_rows[1:])]
    assert m_rows[0].id not in ids(result["machine"])
    assert n_rows[0].id not in ids(result["inventory"])


@pytest.mark.xfail(strict=True, reason=BUG_648)
def test_led_ims_09__skip_should_page_past_the_cap(db, M, m1, f1, i1, w1, u1):
    """LED-IMS-09 — skip=100 should reach the oldest (101st) row; today: TypeError.
    Rules: get_item_movement_summary R4a [BUG-648]."""
    base = datetime(2025, 6, 1, 0, 0, 0)
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
              for k in range(101)]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", base.replace(minute=k % 60, hour=k // 60), performed_by=u1)
              for k in range(101)]
    result = ims(db, M, i1, w1, start_date=T(1, "00:00:00"), end_date=T(30), skip=100)
    assert ids(result["machine"]) == [m_rows[0].id]
    assert ids(result["inventory"]) == [n_rows[0].id]


@pytest.mark.xfail(strict=True, reason=BUG_648)
def test_led_ims_10__limit_should_apply_per_list(db, M, im_base, i1, w1):
    """LED-IMS-10 — limit=1 should apply to each list separately; today: TypeError.
    Rules: get_item_movement_summary R4a [BUG-648]."""
    b = im_base
    result = ims(db, M, i1, w1, start_date=T(1), end_date=T(30), skip=0, limit=1)
    assert ids(result["machine"]) == [b["xm2"].id]
    assert ids(result["inventory"]) == [b["xn2"].id]


@pytest.mark.xfail(strict=True, reason=BUG_647)
def test_led_ims_11__project_list_should_show_consumption(db, M, pc1, pc2, pc9, i1, i2, w1, w2, u1):
    """LED-IMS-11 — the project list should show the item's project-component entries.
    Rules: get_item_movement_summary R5, R6 [BUG-647]."""
    px1 = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    px2 = mk_pel(db, w1, pc2, i1, "consumption", T(12), performed_by=u1)
    mk_pel(db, w1, pc1, i2, "consumption", T(11), performed_by=u1)
    mk_pel(db, w1, pc1, i1, "consumption", datetime(2025, 7, 15, 10, 0, 0), performed_by=u1)
    mk_pel(db, w2, pc9, i1, "consumption", T(11), performed_by=u1)
    result = ims(db, M, i1, w1, start_date=T(1), end_date=T(30))
    assert ids(result["project"]) == [px2.id, px1.id]


# =========================================================================== #
# LedgerManager.get_transactions_by_user
# =========================================================================== #

@pytest.fixture
def tu_base(db, w1, w2, m1, pc1, f1, i1, u1, u2):
    tm1 = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    tm2 = mk_mel(db, w1, m1, i1, "consumption", T(12), performed_by=u1)
    tm3 = mk_mel(db, w1, m1, i1, "consumption", T(11), performed_by=u2)
    tp1 = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    tp2 = mk_pel(db, w1, pc1, i1, "consumption", T(12), performed_by=u1)
    tp3 = mk_pel(db, w1, pc1, i1, "consumption", T(11), performed_by=u2)
    tn1 = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    tn2 = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(12), performed_by=u1)
    tn3 = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(11), performed_by=u2)
    mk_mel(db, w2, m1, i1, "consumption", T(11), performed_by=u1)
    mk_pel(db, w2, pc1, i1, "consumption", T(11), performed_by=u1)
    mk_il(db, w2, STORAGE, f1, i1, "transfer_in", T(11), performed_by=u1)
    return {"tm1": tm1, "tm2": tm2, "tm3": tm3, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "tn1": tn1, "tn2": tn2, "tn3": tn3}


@pytest.mark.xfail(strict=True, reason=BUG_645)
def test_led_tbu_01__crashes_today(db, M, tu_base, u1, w1):
    """LED-TBU-01 — should return per-ledger lists of the user's own-workspace entries.
    Rules: get_transactions_by_user R1, R3 [BUG-645]."""
    b = tu_base
    result = tbu(db, M, u1, w1)
    assert set(result.keys()) == {"machine", "project", "inventory"}
    assert ids(result["machine"]) == [b["tm2"].id, b["tm1"].id]
    assert ids(result["project"]) == [b["tp2"].id, b["tp1"].id]
    assert ids(result["inventory"]) == [b["tn2"].id, b["tn1"].id]


@pytest.mark.xfail(strict=True, reason=BUG_645)
def test_led_tbu_02__inclusive_date_bounds(db, M, m1, pc1, f1, i1, w1, u1):
    """LED-TBU-02 — date bounds should be inclusive on each ledger list.
    Rules: get_transactions_by_user R2 [BUG-645]."""
    times = [T(9, "23:59:59"), T(10, "00:00:00"), T(20, "23:59:59"), T(21, "00:00:00")]
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", t, performed_by=u1) for t in times]
    p_rows = [mk_pel(db, w1, pc1, i1, "consumption", t, performed_by=u1) for t in times]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", t, performed_by=u1) for t in times]
    result = tbu(db, M, u1, w1, start_date=T(10, "00:00:00"), end_date=T(20, "23:59:59"))
    assert ids(result["machine"]) == [m_rows[2].id, m_rows[1].id]
    assert ids(result["project"]) == [p_rows[2].id, p_rows[1].id]
    assert ids(result["inventory"]) == [n_rows[2].id, n_rows[1].id]


@pytest.mark.xfail(strict=True, reason=f"{BUG_645}; {BUG_341_TBU}")
def test_led_tbu_03__lone_start_date(db, M, m1, pc1, f1, i1, w1, u1):
    """LED-TBU-03 — a lone start_date should still restrict each ledger's list.
    Rules: get_transactions_by_user R2 [BUG-645] (and BUG-341)."""
    times = [T(9, "23:59:59"), T(10, "00:00:00"), T(20, "23:59:59"), T(21, "00:00:00")]
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", t, performed_by=u1) for t in times]
    p_rows = [mk_pel(db, w1, pc1, i1, "consumption", t, performed_by=u1) for t in times]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", t, performed_by=u1) for t in times]
    result = tbu(db, M, u1, w1, start_date=T(10, "00:00:00"))
    assert ids(result["machine"]) == [m_rows[3].id, m_rows[2].id, m_rows[1].id]
    assert ids(result["project"]) == [p_rows[3].id, p_rows[2].id, p_rows[1].id]
    assert ids(result["inventory"]) == [n_rows[3].id, n_rows[2].id, n_rows[1].id]


@pytest.mark.xfail(strict=True, reason=f"{BUG_645}; {BUG_341_TBU}")
def test_led_tbu_04__lone_end_date(db, M, m1, pc1, f1, i1, w1, u1):
    """LED-TBU-04 — a lone end_date should still restrict each ledger's list.
    Rules: get_transactions_by_user R2 [BUG-645] (and BUG-341)."""
    times = [T(9, "23:59:59"), T(10, "00:00:00"), T(20, "23:59:59"), T(21, "00:00:00")]
    m_rows = [mk_mel(db, w1, m1, i1, "consumption", t, performed_by=u1) for t in times]
    p_rows = [mk_pel(db, w1, pc1, i1, "consumption", t, performed_by=u1) for t in times]
    n_rows = [mk_il(db, w1, STORAGE, f1, i1, "transfer_in", t, performed_by=u1) for t in times]
    result = tbu(db, M, u1, w1, end_date=T(10, "00:00:00"))
    assert ids(result["machine"]) == [m_rows[1].id, m_rows[0].id]
    assert ids(result["project"]) == [p_rows[1].id, p_rows[0].id]
    assert ids(result["inventory"]) == [n_rows[1].id, n_rows[0].id]


@pytest.mark.xfail(strict=True, reason=f"{BUG_645}; {BUG_341_TBU}")
def test_led_tbu_05__date_filter_before_paging(db, M, m1, pc1, f1, i1, w1, u1):
    """LED-TBU-05 — the date filter should apply before paging, per ledger.
    Rules: get_transactions_by_user R2, R4 [BUG-645] (and BUG-341)."""
    mk_mel(db, w1, m1, i1, "consumption", T(5), performed_by=u1)
    rb_m = mk_mel(db, w1, m1, i1, "consumption", T(8), performed_by=u1)
    mk_mel(db, w1, m1, i1, "consumption", T(25), performed_by=u1)
    mk_pel(db, w1, pc1, i1, "consumption", T(5), performed_by=u1)
    rb_p = mk_pel(db, w1, pc1, i1, "consumption", T(8), performed_by=u1)
    mk_pel(db, w1, pc1, i1, "consumption", T(25), performed_by=u1)
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(5), performed_by=u1)
    rb_n = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(8), performed_by=u1)
    mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(25), performed_by=u1)
    result = tbu(db, M, u1, w1, start_date=T(1), end_date=T(10), limit=1)
    assert ids(result["machine"]) == [rb_m.id]
    assert ids(result["project"]) == [rb_p.id]
    assert ids(result["inventory"]) == [rb_n.id]


@pytest.mark.xfail(strict=True, reason=f"{BUG_645}; {BUG_640}")
def test_led_tbu_06__ties_ordered_by_id_descending(db, M, engine, m1, pc1, f1, i1, w1, u1):
    """LED-TBU-06 — the machine_item_ledger, project_component_item_ledger and
    inventory_ledger SELECTs' ORDER BY should each end performed_at DESC, id
    DESC (proved from the recorded SQL, deterministic per spec G8 — unreachable
    today since the call raises on BUG-645 before any SQL for this call runs);
    rows tied on performed_at should then order by id descending in each list.
    Rules: get_transactions_by_user R3 [BUG-645] (and BUG-640)."""
    ra_m = mk_mel(db, w1, m1, i1, "consumption", T(5), performed_by=u1)
    rb_m = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    rc_m = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    rd_m = mk_mel(db, w1, m1, i1, "consumption", T(10), performed_by=u1)
    ra_p = mk_pel(db, w1, pc1, i1, "consumption", T(5), performed_by=u1)
    rb_p = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    rc_p = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    rd_p = mk_pel(db, w1, pc1, i1, "consumption", T(10), performed_by=u1)
    ra_n = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(5), performed_by=u1)
    rb_n = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    rc_n = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    rd_n = mk_il(db, w1, STORAGE, f1, i1, "transfer_in", T(10), performed_by=u1)
    with StatementRecorder(engine) as rec:
        result = tbu(db, M, u1, w1)
    assert order_by_ends_id_desc(rec.statements, "machine_item_ledger")
    assert order_by_ends_id_desc(rec.statements, "project_component_item_ledger")
    assert order_by_ends_id_desc(rec.statements, "inventory_ledger")
    assert ids(result["machine"]) == [rd_m.id, rc_m.id, rb_m.id, ra_m.id]
    assert ids(result["project"]) == [rd_p.id, rc_p.id, rb_p.id, ra_p.id]
    assert ids(result["inventory"]) == [rd_n.id, rc_n.id, rb_n.id, ra_n.id]


@pytest.mark.xfail(strict=True, reason=BUG_645)
def test_led_tbu_07__paging_per_ledger(db, M, tu_base, u1, w1):
    """LED-TBU-07 — skip/limit should page each ledger's list independently.
    Rules: get_transactions_by_user R4 [BUG-645]."""
    b = tu_base
    result = tbu(db, M, u1, w1, skip=1, limit=1)
    assert ids(result["machine"]) == [b["tm1"].id]
    assert ids(result["project"]) == [b["tp1"].id]
    assert ids(result["inventory"]) == [b["tn1"].id]
