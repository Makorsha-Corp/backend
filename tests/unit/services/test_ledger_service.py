"""Unit tests for app/services/ledger_service.py.

Implements tests/unit/services/ledger_service.cases.md (revision 2), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the test's own "commit point" and the service's
commits are safe and the fixture's outer rollback discards everything.

Patched, as Conventions name them: the commit / rollback spies (they still call
the real method), the failing commit, the "patched manager" (`patch.object` on
`svc.ledger_manager`) and "writes then raises" (the real manager method wrapped
so it writes, then raises ERR). Nothing else is mocked; the project access check
is the real `project_manager.require_component_access`.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows are attributes of the namespace `s` (`s.W1`, `s.M1`);
`# Then N` marks the checks of the card's Then line N. For xfail cards whose
"Fails today on" line says "the call raises ...", the exception escapes at the
When call, before the `# Then 1` block (the call is the first thing Then 1 needs).
"""

# ruff: noqa: SIM117  (Conventions prescribe the nested `with`)
import inspect
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError

from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.department import Department
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
from app.models.workspace_member import WorkspaceMember
from app.services.ledger_service import ledger_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Bug titles (xfail reasons)
# --------------------------------------------------------------------------- #

BUG_341 = "BUG-341: a scope filter is accepted but not applied (ledger date range + type / item)"
BUG_640 = "BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order"
BUG_641 = (
    'BUG-641: "Latest entry" balance lookups pick an arbitrary row on a timestamp tie'
)
BUG_643 = "BUG-643: Machine-item reconcile does not lock the snapshot row"
BUG_644 = "BUG-644: Inventory reconcile does not lock the snapshot row"
BUG_645 = "BUG-645: User transaction report always crashes"
BUG_646 = "BUG-646: Item movement report is empty unless both dates are given"
BUG_648 = "BUG-648: Item movement report silently stops at 100 entries per ledger"
BUG_649 = "BUG-649: Reconcile reports an error when there is nothing to reconcile"
BUG_650 = "BUG-650: Reconcile crashes when the latest ledger entry has no average price"
BUG_652 = "BUG-652: Inventory reconcile does not record who changed the stock row"
BUG_653 = (
    "BUG-653: Inventory reconcile ignores a wrong average price when quantities match"
)
BUG_1278 = (
    "BUG-1278: The members and components of a deleted project stay open; "
    "BUG-1954: A deleted project still opens by id"
)
BUG_3042 = 'BUG-3042: A price-only inventory correction says "0 units adjusted"'
BUG_3043 = "BUG-3043: Ledger balance endpoints return stock value as a binary float"

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = ledger_service"
svc = ledger_service

# Convention "MISSING"
MISSING = 999999999

STORAGE = InventoryTypeEnum.STORAGE
DAMAGED = InventoryTypeEnum.DAMAGED


# Convention "T(d)" = 2025-06-d 10:00:00; naive (machine / inventory / project
# ledgers have naive `performed_at`) ...
def T(d):
    return datetime(2025, 6, d, 10, 0, 0)  # noqa: DTZ001


# ... and aware UTC for the attachment ledger (`DateTime(timezone=True)`)
def TA(d):
    return T(d).replace(tzinfo=timezone.utc)


# "datetime(2025, 6, d) + timedelta(minutes=k)" of the 101-row cards (naive, as T)
def TM(d, k):
    return datetime(2025, 6, d) + timedelta(minutes=k)  # noqa: DTZ001


# Convention "returns ids"
def ids(rows):
    return [r.id for r in rows]


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows (every test)
# --------------------------------------------------------------------------- #


def _member(db, ws, user, role):
    db.add(
        WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=role, status="active")
    )
    db.flush()


def _factory(db, ws, name, abbr):
    row = Factory(workspace_id=ws.id, name=name, abbreviation=abbr)
    db.add(row)
    db.flush()
    return row


def _machine(db, ws, factory, name):
    row = Machine(workspace_id=ws.id, factory_id=factory.id, name=name)
    db.add(row)
    db.flush()
    return row


def _item(db, ws, name):
    row = Item(workspace_id=ws.id, name=name, name_normalized=name.lower(), unit="pcs")
    db.add(row)
    db.flush()
    return row


def _attachment(db, ws, uploader):
    row = Attachment(
        workspace_id=ws.id,
        file_name="a.pdf",
        mime_type="application/pdf",
        file_size=10,
        uploaded_by=uploader.id,
    )
    db.add(row)
    db.flush()
    return row


def _project(db, ws, factory, creator, **but):
    fields = {
        "workspace_id": ws.id,
        "factory_id": factory.id,
        "name": "Project",
        "description": "",
        "visibility": "workspace",
        "created_by": creator.id,
    }
    fields.update(but)
    row = Project(**fields)
    db.add(row)
    db.flush()
    return row


def _component(db, ws, project, name):
    row = ProjectComponent(workspace_id=ws.id, project_id=project.id, name=name)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def s(db):
    """W0, W1, W2 (in that order), U1/U2/U3 members of W1, U9 of W2; items,
    machines, factories, attachments, projects and components of Conventions."""
    n = SimpleNamespace()
    n.U1 = make_profile(db)
    n.U2 = make_profile(db)
    n.U3 = make_profile(db)
    n.U9 = make_profile(db)
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db, owner_user_id=n.U1.id)
    n.W2 = make_workspace(db)
    _member(db, n.W1, n.U1, "owner")
    _member(db, n.W1, n.U2, "ground-team")
    _member(db, n.W1, n.U3, "ground-team")
    _member(db, n.W2, n.U9, "ground-team")
    n.I1 = _item(db, n.W1, "Bolt")
    n.I2 = _item(db, n.W1, "Nut")
    n.I0 = _item(db, n.W0, "Bolt")
    n.I9 = _item(db, n.W2, "Washer")
    n.F1 = _factory(db, n.W1, "Factory 1", "F1")
    n.F2 = _factory(db, n.W1, "Factory 2", "F2")
    n.F0 = _factory(db, n.W0, "Factory 0", "F0")
    n.F9 = _factory(db, n.W2, "Factory 9", "F9")
    n.M1 = _machine(db, n.W1, n.F1, "Machine 1")
    n.M2 = _machine(db, n.W1, n.F1, "Machine 2")
    n.M0 = _machine(db, n.W0, n.F0, "Machine 0")
    n.M9 = _machine(db, n.W2, n.F9, "Machine 9")
    n.A1 = _attachment(db, n.W1, n.U1)
    n.A2 = _attachment(db, n.W1, n.U1)
    n.A0 = _attachment(db, n.W0, n.U1)
    n.A9 = _attachment(db, n.W2, n.U9)
    n.PA = _project(db, n.W1, n.F1, n.U1)
    n.PP = _project(db, n.W1, n.F1, n.U1, visibility="invited_only")
    n.PD = _project(
        db, n.W1, n.F1, n.U1, is_deleted=True, deleted_at=T(1), deleted_by=n.U1.id
    )
    n.C1 = _component(db, n.W1, n.PA, "C1")
    n.C2 = _component(db, n.W1, n.PA, "C2")
    n.CP = _component(db, n.W1, n.PP, "CP")
    n.CD = _component(db, n.W1, n.PD, "CD")
    n.P0 = _project(db, n.W0, n.F0, n.U1)
    n.C0 = _component(db, n.W0, n.P0, "C0")
    n.P9 = _project(db, n.W2, n.F9, n.U9)
    n.C9 = _component(db, n.W2, n.P9, "C9")
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "mentry" (other NOT NULL column: source_type "manual")
def mentry(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "machine_id": s.M1.id,
        "item_id": s.I1.id,
        "transaction_type": "consumption",
        "quantity": 1,
        "qty_before": 0,
        "qty_after": 1,
        "unit_cost": Decimal("2.00"),
        "total_cost": Decimal("2.00"),
        "value_before": Decimal("0.00"),
        "value_after": Decimal("2.00"),
        "avg_price_before": Decimal("2.00"),
        "avg_price_after": Decimal("2.00"),
        "source_type": "manual",
        "performed_by": s.U1.id,
        "performed_at": T(1),
    }
    fields.update(but)
    row = MachineItemLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "ientry"
def ientry(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "inventory_type": STORAGE,
        "factory_id": s.F1.id,
        "item_id": s.I1.id,
        "transaction_type": "transfer_in",
        "quantity": 1,
        "qty_before": 0,
        "qty_after": 1,
        "unit_cost": Decimal("2.00"),
        "total_cost": Decimal("2.00"),
        "avg_price_before": Decimal("2.00"),
        "avg_price_after": Decimal("2.00"),
        "performed_by": s.U1.id,
        "performed_at": T(1),
    }
    fields.update(but)
    row = InventoryLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "pentry" (other NOT NULL columns: unit_cost 10.00, qty_before 0,
# qty_after 1, source_type "manual")
def pentry(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "project_component_id": s.C1.id,
        "item_id": s.I1.id,
        "transaction_type": "transfer_in",
        "quantity": 1,
        "total_cost": Decimal("10.00"),
        "unit_cost": Decimal("10.00"),
        "qty_before": 0,
        "qty_after": 1,
        "source_type": "manual",
        "performed_by": s.U1.id,
        "performed_at": T(1),
    }
    fields.update(but)
    row = ProjectComponentItemLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "aentry" (performed_at aware: TA)
def aentry(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "attachment_id": s.A1.id,
        "entity_type": "machine",
        "transaction_type": "ready",
        "file_name": "a.pdf",
        "mime_type": "application/pdf",
        "file_size": 10,
        "performed_by": s.U1.id,
        "performed_at": TA(1),
    }
    fields.update(but)
    row = AttachmentLedger(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "msnap"
def msnap(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "machine_id": s.M1.id,
        "item_id": s.I1.id,
        "qty": 10,
    }
    fields.update(but)
    row = MachineItem(**fields)
    db.add(row)
    db.flush()
    return row


# Convention "isnap"
def isnap(db, s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "factory_id": s.F1.id,
        "item_id": s.I1.id,
        "inventory_type": STORAGE,
        "qty": 4,
        "avg_price": Decimal("0.00"),
        "created_by": s.U1.id,
        "updated_by": s.U1.id,
        "is_deleted": False,
    }
    fields.update(but)
    row = Inventory(**fields)
    db.add(row)
    db.flush()
    return row


# RM rows of reconcile_machine_item: RE1, RE2 (ledger quantity 15)
def re1(db, s):
    return mentry(
        db,
        s,
        qty_after=10,
        avg_price_after=Decimal("2.00"),
        value_after=Decimal("20.00"),
        performed_at=T(1),
    )


def re2(db, s):
    return mentry(
        db,
        s,
        qty_after=15,
        avg_price_after=Decimal("2.50"),
        value_after=Decimal("37.50"),
        performed_at=T(2),
    )


# IL rows of get_inventory_ledger
def g1(db, s):
    return ientry(db, s, performed_at=T(1))


def g2(db, s):
    return ientry(
        db, s, inventory_type=DAMAGED, transaction_type="damaged", performed_at=T(2)
    )


def g3(db, s):
    return ientry(db, s, factory_id=s.F2.id, performed_at=T(3))


def g4(db, s):
    return ientry(
        db, s, item_id=s.I2.id, transaction_type="consumption", performed_at=T(4)
    )


def g0(db, s):
    return ientry(
        db,
        s,
        workspace_id=s.W0.id,
        factory_id=s.F0.id,
        item_id=s.I0.id,
        performed_at=T(5),
    )


def g9(db, s):
    return ientry(
        db,
        s,
        workspace_id=s.W2.id,
        factory_id=s.F9.id,
        item_id=s.I9.id,
        performed_at=T(6),
    )


# AL rows of get_attachment_ledger
def l1(db, s):
    return aentry(db, s, performed_at=TA(1))


def l2(db, s):
    return aentry(
        db, s, entity_type="project", transaction_type="deleted", performed_at=TA(2)
    )


def l3(db, s):
    return aentry(
        db, s, attachment_id=s.A2.id, transaction_type="deleted", performed_at=TA(3)
    )


def l0(db, s):
    return aentry(
        db, s, workspace_id=s.W0.id, attachment_id=s.A0.id, performed_at=TA(4)
    )


def l9(db, s):
    return aentry(
        db, s, workspace_id=s.W2.id, attachment_id=s.A9.id, performed_at=TA(5)
    )


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "extra X" (after the commit point)
def extra_x(db, s):
    x = Department(workspace_id=s.W2.id, name="Extra", created_by=s.U1.id)
    db.add(x)
    db.flush()
    return x


# Convention "pending Q" (after the commit point)
def pending_q(db, s):
    q = Department(workspace_id=s.W2.id, name="Pending", created_by=s.U1.id)
    db.add(q)
    return q


# Convention "edit E(r)" (after the commit point)
def edit_e(r):
    r.notes = "Edited"


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


# Convention "spies"
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "recorder": before_cursor_execute on db.connection()
@contextmanager
def recorder(db):
    stmts = []

    def rec(conn, cursor, statement, parameters, context, executemany):
        stmts.append(statement)

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", rec)
    try:
        yield stmts
    finally:
        event.remove(conn, "before_cursor_execute", rec)


# Convention "writes then raises"
@contextmanager
def writes_then_raises(method):
    real = getattr(svc.ledger_manager, method)
    err = RuntimeError("after write")

    def f(*a, **k):
        real(*a, **k)
        raise err

    with patch.object(svc.ledger_manager, method, side_effect=f):
        yield err


# Convention "the <table> SELECT": recorded SELECTs whose FROM names the table
def selects_from(stmts, table):
    pat = re.compile(r"\bFROM\s+" + re.escape(table) + r"\b(?!_)", re.IGNORECASE)
    found = [
        st
        for st in stmts
        if st.lstrip().upper().startswith("SELECT") and pat.search(st)
    ]
    assert found, f"no {table} SELECT recorded"
    return found


def _collapse(st):
    return re.sub(r"\s+", " ", st).strip().lower()


# "ORDER BY is `performed_at DESC, id DESC`" (case, whitespace, qualifiers ignored)
def order_by_of(st):
    m = re.search(
        r"ORDER BY\s+(.*?)(?:\s+LIMIT\b|\s+OFFSET\b|\s+FOR\s+UPDATE\b|$)",
        st,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    clause = _collapse(m.group(1)).rstrip(";").strip()
    return re.sub(r"\b\w+\.(\w+)\b", r"\1", clause)


def names_table(stmts, table):
    return any(
        re.search(r"\b" + re.escape(table) + r"\b", st, re.IGNORECASE) for st in stmts
    )


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Counts (fresh queries)
def dept_count(db, name):
    db.expire_all()
    return db.execute(
        select(func.count()).select_from(Department).where(Department.name == name)
    ).scalar_one()


def mel_count(db, s):
    db.expire_all()
    return db.execute(
        select(func.count())
        .select_from(MachineItemLedger)
        .where(
            MachineItemLedger.machine_id == s.M1.id,
            MachineItemLedger.item_id == s.I1.id,
        )
    ).scalar_one()


def mi_count(db, s):
    db.expire_all()
    return db.execute(
        select(func.count())
        .select_from(MachineItem)
        .where(MachineItem.machine_id == s.M1.id, MachineItem.item_id == s.I1.id)
    ).scalar_one()


def mae_count(db, machine=None):
    db.expire_all()
    q = select(func.count()).select_from(MachineActivityEvent)
    if machine is not None:
        q = q.where(MachineActivityEvent.machine_id == machine.id)
    return db.execute(q).scalar_one()


def il_count_w1(db, s):
    db.expire_all()
    return db.execute(
        select(func.count())
        .select_from(InventoryLedger)
        .where(InventoryLedger.workspace_id == s.W1.id)
    ).scalar_one()


def il_rows_bucket(db, s):
    db.expire_all()
    return (
        db.execute(
            select(InventoryLedger)
            .where(
                InventoryLedger.workspace_id == s.W1.id,
                InventoryLedger.factory_id == s.F1.id,
                InventoryLedger.item_id == s.I1.id,
                InventoryLedger.inventory_type == STORAGE,
            )
            .order_by(InventoryLedger.id)
        )
        .scalars()
        .all()
    )


def inv_count(db, s):
    db.expire_all()
    return db.execute(
        select(func.count())
        .select_from(Inventory)
        .where(
            Inventory.workspace_id == s.W1.id,
            Inventory.factory_id == s.F1.id,
            Inventory.item_id == s.I1.id,
        )
    ).scalar_one()


def adjustment_mel(db, s):
    db.expire_all()
    return db.execute(
        select(MachineItemLedger).where(
            MachineItemLedger.machine_id == s.M1.id,
            MachineItemLedger.item_id == s.I1.id,
            MachineItemLedger.transaction_type == "inventory_adjustment",
        )
    ).scalar_one()


def the_event(db, s):
    db.expire_all()
    return db.execute(
        select(MachineActivityEvent).where(MachineActivityEvent.machine_id == s.M1.id)
    ).scalar_one()


# Convention "re-read"
def reread_msnap(db, row_id):
    db.expire_all()
    return db.get(MachineItem, row_id)


def reread_isnap(db, row_id):
    db.expire_all()
    return db.get(Inventory, row_id)


# =========================================================================== #
# LedgerService.get_machine_ledger
# =========================================================================== #


# [claude] LSV-GML-01
def test_lsv_gml_01__no_optional_argument_every_entry_of_the_machine_newest_first(
    db, s
):
    """LSV-GML-01 — with no optional argument every entry of the machine comes back newest first.
    Rules: get_machine_ledger R1"""
    e1 = mentry(db, s, transaction_type="transfer_in", performed_at=T(1))
    e2 = mentry(db, s, performed_at=T(2))
    e3 = mentry(db, s, item_id=s.I2.id, performed_at=T(3))
    mentry(db, s, machine_id=s.M2.id, performed_at=T(4))
    commit_point(db)
    result = svc.get_machine_ledger(db, machine_id=s.M1.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] LSV-GML-02
def test_lsv_gml_02__the_workspace_reaches_the_manager(db, s):
    """LSV-GML-02 — the workspace reaches the manager.
    Rules: get_machine_ledger R1; HR-16"""
    mentry(db, s, performed_at=T(1))
    mentry(db, s, performed_at=T(2))
    commit_point(db)
    result = svc.get_machine_ledger(db, machine_id=s.M1.id, workspace_id=s.W2.id)
    # Then 1
    assert result == []


# [claude] LSV-GML-03
def test_lsv_gml_03__item_id_reaches_the_manager(db, s):
    """LSV-GML-03 — item_id reaches the manager.
    Rules: get_machine_ledger R1"""
    e1 = mentry(db, s, performed_at=T(1))
    mentry(db, s, item_id=s.I2.id, performed_at=T(2))
    e3 = mentry(db, s, performed_at=T(3))
    commit_point(db)
    result = svc.get_machine_ledger(
        db, machine_id=s.M1.id, workspace_id=s.W1.id, item_id=s.I1.id
    )
    # Then 1
    assert ids(result) == [e3.id, e1.id]


# [claude] LSV-GML-04
def test_lsv_gml_04__transaction_type_reaches_the_manager(db, s):
    """LSV-GML-04 — transaction_type reaches the manager.
    Rules: get_machine_ledger R1"""
    mentry(db, s, transaction_type="transfer_in", performed_at=T(1))
    e2 = mentry(db, s, performed_at=T(2))
    e3 = mentry(db, s, item_id=s.I2.id, performed_at=T(3))
    commit_point(db)
    result = svc.get_machine_ledger(
        db, machine_id=s.M1.id, workspace_id=s.W1.id, transaction_type="consumption"
    )
    # Then 1
    assert ids(result) == [e3.id, e2.id]


# [claude] LSV-GML-05
def test_lsv_gml_05__a_full_date_range_reaches_the_manager(db, s):
    """LSV-GML-05 — a full date range reaches the manager.
    Rules: get_machine_ledger R1"""
    mentry(db, s, performed_at=T(1))
    e2 = mentry(db, s, performed_at=T(2))
    e3 = mentry(db, s, performed_at=T(3))
    mentry(db, s, performed_at=T(4))
    commit_point(db)
    result = svc.get_machine_ledger(
        db, machine_id=s.M1.id, workspace_id=s.W1.id, start_date=T(2), end_date=T(3)
    )
    # Then 1
    assert ids(result) == [e3.id, e2.id]


# [claude] LSV-GML-06
def test_lsv_gml_06__skip_and_limit_reach_the_manager_in_their_places(db, s):
    """LSV-GML-06 — skip and limit reach the manager in their places.
    Rules: get_machine_ledger R1"""
    e = {k: mentry(db, s, performed_at=T(k)) for k in range(1, 6)}
    commit_point(db)
    result = svc.get_machine_ledger(
        db, machine_id=s.M1.id, workspace_id=s.W1.id, skip=1, limit=2
    )
    # Then 1
    assert ids(result) == [e[4].id, e[3].id]


# [claude] LSV-GML-07
def test_lsv_gml_07__the_default_limit_is_100(db, s):
    """LSV-GML-07 — the default limit is 100.
    Rules: get_machine_ledger R1 (defaults)"""
    q = {k: mentry(db, s, performed_at=TM(1, k)) for k in range(101)}
    commit_point(db)
    result = svc.get_machine_ledger(db, machine_id=s.M1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert q[0].id not in [r.id for r in result]
    # Then 3
    assert result[0].id == q[100].id


# [claude] LSV-GML-08
def test_lsv_gml_08__a_database_error_from_the_manager_passes_on_without_commit_or_rollback(
    db, s
):
    """LSV-GML-08 — a database error from the manager passes on with no commit and no rollback.
    Rules: get_machine_ledger R2; TC6"""
    mentry(db, s)
    commit_point(db)
    sp = db.begin_nested()
    q = pending_q(db, s)
    with spies(db) as (cm, rb):
        with pytest.raises(DataError) as exc:
            svc.get_machine_ledger(
                db, machine_id=s.M1.id, workspace_id=s.W1.id, limit=-1
            )
    # Then 1
    assert isinstance(exc.value, DataError)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    sp.rollback()
    assert usable(db)


# [claude] LSV-GML-09
def test_lsv_gml_09__the_read_neither_commits_nor_rolls_back(db, s):
    """LSV-GML-09 — the read neither commits nor rolls back.
    Rules: get_machine_ledger R2; TC6"""
    mentry(db, s, performed_at=T(1))
    e2 = mentry(db, s, performed_at=T(2))
    commit_point(db)
    q = pending_q(db, s)
    edit_e(e2)
    with spies(db) as (cm, rb):
        result = svc.get_machine_ledger(db, machine_id=s.M1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert e2 in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    db.rollback()
    assert dept_count(db, "Pending") == 0


# [claude] LSV-GML-10
@pytest.mark.xfail(strict=True, reason=BUG_640)
def test_lsv_gml_10__pass_through_bug_640_ordered_by_performed_at_then_id(db, s):
    """LSV-GML-10 — pass-through BUG-640: the list is ordered by performed_at then id.
    Rules: get_machine_ledger R1 [BUG-640]"""
    mentry(db, s, performed_at=T(5))
    mentry(db, s, performed_at=T(5))
    commit_point(db)
    with recorder(db) as stmts:
        result = svc.get_machine_ledger(db, machine_id=s.M1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    for st in selects_from(stmts, "machine_item_ledger"):
        assert order_by_of(st) == "performed_at desc, id desc"


# [claude] LSV-GML-11
@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_lsv_gml_11__pass_through_bug_341_a_date_range_and_a_type_combine(db, s):
    """LSV-GML-11 — pass-through BUG-341: a date range and a type combine.
    Rules: get_machine_ledger R1 [BUG-341]"""
    e1 = mentry(db, s, performed_at=T(10))
    mentry(db, s, transaction_type="transfer_in", performed_at=T(11))
    mentry(db, s, performed_at=T(25))
    commit_point(db)
    result = svc.get_machine_ledger(
        db,
        machine_id=s.M1.id,
        workspace_id=s.W1.id,
        start_date=T(5),
        end_date=T(20),
        transaction_type="consumption",
    )
    # Then 1
    assert ids(result) == [e1.id]


# =========================================================================== #
# LedgerService.get_machine_balance
# =========================================================================== #


# [claude] LSV-GMB-01
def test_lsv_gmb_01__a_bucket_with_history_ids_echoed_latest_quantity_and_value(db, s):
    """LSV-GMB-01 — a bucket with history: ids echoed, latest quantity and value.
    Rules: get_machine_balance R1, R2 (value part that holds today), Returns"""
    mentry(db, s, qty_after=5, value_after=Decimal("12.50"), performed_at=T(3))
    mentry(db, s, qty_after=40, value_after=Decimal("1234.50"), performed_at=T(9))
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert set(result.keys()) == {"machine_id", "item_id", "quantity", "total_value"}
    # Then 2
    assert result["machine_id"] == s.M1.id
    assert result["item_id"] == s.I1.id
    # Then 3
    assert result["quantity"] == 40
    assert isinstance(result["quantity"], int)
    # Then 4
    assert result["total_value"] == Decimal("1234.50")


# [claude] LSV-GMB-02
@pytest.mark.xfail(strict=True, reason=BUG_3043)
def test_lsv_gmb_02__bug_3043_the_value_of_a_bucket_with_history_is_the_exact_decimal(
    db, s
):
    """LSV-GMB-02 — BUG-3043: the value of a bucket with history is the exact Decimal.
    Rules: get_machine_balance R2 [BUG-3043]"""
    mentry(db, s, qty_after=40, value_after=Decimal("1234.50"), performed_at=T(9))
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result["quantity"] == 40
    # Then 2
    assert isinstance(result["total_value"], Decimal)
    # Then 3
    assert str(result["total_value"]) == "1234.50"


# [claude] LSV-GMB-03
def test_lsv_gmb_03__an_empty_bucket_gives_quantity_0_and_value_0(db, s):
    """LSV-GMB-03 — an empty bucket gives quantity 0 and value 0.
    Rules: get_machine_balance R1, R2 (value part that holds today)"""
    mentry(db, s, item_id=s.I2.id, qty_after=7)
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result["machine_id"] == s.M1.id
    assert result["item_id"] == s.I1.id
    # Then 2
    assert result["quantity"] == 0
    # Then 3
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GMB-04
@pytest.mark.xfail(strict=True, reason=BUG_3043)
def test_lsv_gmb_04__bug_3043_an_empty_buckets_value_is_decimal_0_00(db, s):
    """LSV-GMB-04 — BUG-3043: an empty bucket's value is Decimal("0.00").
    Rules: get_machine_balance R2 [BUG-3043]"""
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert isinstance(result["total_value"], Decimal)
    # Then 3
    assert str(result["total_value"]) == "0.00"


# [claude] LSV-GMB-05
def test_lsv_gmb_05__a_w2_machines_bucket_is_not_visible_from_w1(db, s):
    """LSV-GMB-05 — a W2 machine's bucket is not visible from W1.
    Rules: get_machine_balance R1; HR-16"""
    mentry(
        db,
        s,
        workspace_id=s.W2.id,
        machine_id=s.M9.id,
        item_id=s.I9.id,
        qty_after=30,
        value_after=Decimal("60.00"),
    )
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M9.id, item_id=s.I9.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result["machine_id"] == s.M9.id
    assert result["item_id"] == s.I9.id
    # Then 2
    assert result["quantity"] == 0
    # Then 3
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GMB-06
def test_lsv_gmb_06__a_w0_machines_bucket_is_not_visible_from_w1(db, s):
    """LSV-GMB-06 — a W0 machine's bucket is not visible from W1.
    Rules: get_machine_balance R1; HR-16"""
    mentry(
        db,
        s,
        workspace_id=s.W0.id,
        machine_id=s.M0.id,
        item_id=s.I0.id,
        qty_after=30,
        value_after=Decimal("60.00"),
    )
    commit_point(db)
    result = svc.get_machine_balance(
        db, machine_id=s.M0.id, item_id=s.I0.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GMB-07
def test_lsv_gmb_07__the_balance_read_neither_commits_nor_rolls_back(db, s):
    """LSV-GMB-07 — the balance read neither commits nor rolls back.
    Rules: get_machine_balance R3; TC6"""
    e1 = mentry(db, s, qty_after=3)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(e1)
    with spies(db) as (cm, rb):
        result = svc.get_machine_balance(
            db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert result["quantity"] == 3
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert e1 in db.dirty
    # Then 6
    assert len(db.dirty) == 1


# [claude] LSV-GMB-08
@pytest.mark.xfail(strict=True, reason=BUG_641)
def test_lsv_gmb_08__pass_through_bug_641_the_latest_entry_breaks_ties_by_id(db, s):
    """LSV-GMB-08 — pass-through BUG-641: the latest entry breaks ties by id.
    Rules: get_machine_balance R1 [BUG-641]"""
    mentry(db, s, qty_after=10, value_after=Decimal("10.00"), performed_at=T(10))
    mentry(db, s, qty_after=20, value_after=Decimal("40.00"), performed_at=T(10))
    commit_point(db)
    with recorder(db) as stmts:
        result = svc.get_machine_balance(
            db, machine_id=s.M1.id, item_id=s.I1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert result["machine_id"] == s.M1.id
    # Then 2
    for st in selects_from(stmts, "machine_item_ledger"):
        assert order_by_of(st) == "performed_at desc, id desc"
        assert re.search(r"ORDER BY.*?\bLIMIT\b", st, re.IGNORECASE | re.DOTALL)
    # Then 3
    assert result["quantity"] == 20


# =========================================================================== #
# LedgerService.reconcile_machine_item
# =========================================================================== #


# [claude] LSV-RMI-01
def test_lsv_rmi_01__balanced_one_success_message_committed_nothing_written(db, s):
    """LSV-RMI-01 — balanced: one success message, committed, nothing written.
    Rules: reconcile_machine_item R1, R2, R6; TC1"""
    re1(db, s)
    re2(db, s)
    snap = msnap(db, s, qty=15)
    commit_point(db)
    extra_x(db, s)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "balanced",
        "ledger_qty": 15,
        "snapshot_qty": 15,
        "discrepancy": 0,
        "adjustment_created": False,
    }
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].type.value == "success"
    assert messages[0].message == "Machine inventory is balanced at 15 units."
    assert messages[0].details is None
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 1
    # Then 5
    assert mel_count(db, s) == 2
    # Then 6
    assert reread_msnap(db, snap.id).qty == 15
    # Then 7
    assert mae_count(db, s.M1) == 0


# [claude] LSV-RMI-02
def test_lsv_rmi_02__adjusted_a_warning_with_the_result_then_a_success_message(db, s):
    """LSV-RMI-02 — adjusted: a warning with the result, then a success message.
    Rules: reconcile_machine_item R1, R3"""
    re1(db, s)
    re2(db, s)
    msnap(db, s)
    commit_point(db)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "adjusted",
        "ledger_qty": 15,
        "snapshot_qty": 10,
        "discrepancy": 5,
        "adjustment_created": True,
    }
    # Then 2
    assert len(messages) == 2
    # Then 3
    assert messages[0].type.value == "warning"
    assert messages[0].message == "Discrepancy found and corrected: 5 units adjusted."
    # Then 4
    assert messages[0].details == result
    # Then 5
    assert messages[1].type.value == "success"
    assert messages[1].message == "Snapshot updated to match ledger."
    assert messages[1].details is None


# [claude] LSV-RMI-03
def test_lsv_rmi_03__adjusted_snapshot_adjustment_row_and_event_committed_as_the_current_user(
    db, s
):
    """LSV-RMI-03 — adjusted: the snapshot, the adjustment row and the event are committed as the current user.
    Rules: reconcile_machine_item R1, R6; TC1"""
    re1(db, s)
    re2(db, s)
    snap = msnap(db, s)
    commit_point(db)
    result, _messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["status"] == "adjusted"
    # Then 2
    db.rollback()
    assert reread_msnap(db, snap.id).qty == 15
    # Then 3
    assert mel_count(db, s) == 3
    # Then 4
    adj = adjustment_mel(db, s)
    assert adj.source_type == "reconciliation"
    assert adj.performed_by == s.U2.id
    assert adj.qty_after == 15
    # Then 5
    assert mae_count(db, s.M1) == 1
    # Then 6
    ev = the_event(db, s)
    assert ev.event_type == "ledger_reconciled"
    assert ev.performed_by == s.U2.id
    assert ev.description == "Ledger reconciled for Bolt: snapshot 10 → 15"


# [claude] LSV-RMI-04
def test_lsv_rmi_04__a_negative_discrepancy_is_reported_as_its_absolute_value(db, s):
    """LSV-RMI-04 — a negative discrepancy is reported as its absolute value.
    Rules: reconcile_machine_item R3"""
    re1(db, s)
    msnap(db, s, qty=15)
    commit_point(db)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["discrepancy"] == -5
    assert result["status"] == "adjusted"
    # Then 2
    assert len(messages) == 2
    # Then 3
    assert messages[0].message == "Discrepancy found and corrected: 5 units adjusted."


# [claude] LSV-RMI-05
def test_lsv_rmi_05__error_snapshot_missing_one_warning_committed_nothing_written(
    db, s
):
    """LSV-RMI-05 — error (snapshot missing, ledger holds stock): one warning, committed, nothing written.
    Rules: reconcile_machine_item R4"""
    re1(db, s)
    re2(db, s)
    commit_point(db)
    extra_x(db, s)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "error",
        "ledger_qty": 15,
        "snapshot_qty": 0,
        "discrepancy": 15,
        "adjustment_created": False,
        "error": "Snapshot missing for item with ledger transactions",
    }
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].type.value == "warning"
    assert (
        messages[0].message
        == "Reconciliation issue: Snapshot missing for item with ledger transactions"
    )
    assert messages[0].details is None
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 1
    # Then 5
    assert mi_count(db, s) == 0
    # Then 6
    assert mel_count(db, s) == 2


# [claude] LSV-RMI-06
def test_lsv_rmi_06__an_error_result_without_an_error_text_says_unknown_error(db, s):
    """LSV-RMI-06 — an error result without an error text says "Unknown error".
    Rules: reconcile_machine_item R4"""
    r = {
        "status": "error",
        "ledger_qty": 3,
        "snapshot_qty": 0,
        "discrepancy": 3,
        "adjustment_created": False,
    }
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_machine_item", return_value=r):
        result, messages = svc.reconcile_machine_item(
            db,
            machine_id=s.M1.id,
            item_id=s.I1.id,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].type.value == "warning"
    assert messages[0].message == "Reconciliation issue: Unknown error"
    assert messages[0].details is None
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 1


# [claude] LSV-RMI-07
def test_lsv_rmi_07__any_other_status_gives_no_message_and_still_commits(db, s):
    """LSV-RMI-07 — any other status gives no message and still commits.
    Rules: reconcile_machine_item R5"""
    r = {
        "status": "pending",
        "ledger_qty": 3,
        "snapshot_qty": 3,
        "discrepancy": 0,
        "adjustment_created": False,
    }
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_machine_item", return_value=r):
        result, messages = svc.reconcile_machine_item(
            db,
            machine_id=s.M1.id,
            item_id=s.I1.id,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert messages == []
    # Then 3
    db.rollback()
    assert dept_count(db, "Extra") == 1


# [claude] LSV-RMI-08
def test_lsv_rmi_08__an_empty_bucket_with_no_snapshot_one_message_nothing_written_committed(
    db, s
):
    """LSV-RMI-08 — an empty bucket with no snapshot: one message, nothing written, committed.
    Rules: reconcile_machine_item R2, R4 (bug-independent part of BUG-649)"""
    commit_point(db)
    extra_x(db, s)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["ledger_qty"] == 0
    assert result["adjustment_created"] is False
    # Then 2
    assert len(messages) == 1
    # Then 3
    db.rollback()
    assert dept_count(db, "Extra") == 1
    # Then 4
    assert mi_count(db, s) == 0
    # Then 5
    assert mel_count(db, s) == 0
    # Then 6
    assert mae_count(db, s.M1) == 0


# [claude] LSV-RMI-09
@pytest.mark.xfail(strict=True, reason=BUG_649)
def test_lsv_rmi_09__pass_through_bug_649_an_empty_bucket_is_balanced_at_0_units(db, s):
    """LSV-RMI-09 — pass-through BUG-649: an empty bucket is balanced at 0 units.
    Rules: reconcile_machine_item R2 [BUG-649]"""
    commit_point(db)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert len(messages) == 1
    # Then 2
    assert messages[0].type.value == "success"
    assert messages[0].message == "Machine inventory is balanced at 0 units."
    # Then 3
    assert result["status"] == "balanced"


# [claude] LSV-RMI-10
def test_lsv_rmi_10__an_exception_after_the_manager_wrote_rolled_back_same_object_nothing_saved(
    db, s
):
    """LSV-RMI-10 — an exception after the manager wrote: rolled back, same object, nothing saved.
    Rules: reconcile_machine_item R7; TC3"""
    re1(db, s)
    re2(db, s)
    snap = msnap(db, s)
    commit_point(db)
    extra_x(db, s)
    with writes_then_raises("reconcile_machine_item") as err:
        with spies(db) as (_cm, rb):
            with pytest.raises(RuntimeError) as exc:
                svc.reconcile_machine_item(
                    db,
                    machine_id=s.M1.id,
                    item_id=s.I1.id,
                    workspace_id=s.W1.id,
                    current_user=s.U2,
                )
    # Then 1
    assert exc.value is err
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    db.rollback()
    assert reread_msnap(db, snap.id).qty == 10
    # Then 4
    assert mel_count(db, s) == 2
    # Then 5
    assert mae_count(db, s.M1) == 0
    # Then 6
    assert dept_count(db, "Extra") == 0
    # Then 7
    assert usable(db)


# [claude] LSV-RMI-11
def test_lsv_rmi_11__an_exception_while_building_the_messages_rolls_back(db, s):
    """LSV-RMI-11 — an exception while building the messages rolls back.
    Rules: reconcile_machine_item R7; TC3"""
    r = {"status": "balanced"}
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_machine_item", return_value=r):
        with spies(db) as (cm, rb):
            with pytest.raises(KeyError) as exc:
                svc.reconcile_machine_item(
                    db,
                    machine_id=s.M1.id,
                    item_id=s.I1.id,
                    workspace_id=s.W1.id,
                    current_user=s.U2,
                )
    # Then 1
    assert exc.value.args == ("ledger_qty",)
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert cm.call_count == 0
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 0


# [claude] LSV-RMI-12
def test_lsv_rmi_12__a_failing_commit_is_rolled_back_and_re_raised_nothing_saved(db, s):
    """LSV-RMI-12 — a failing commit is rolled back and re-raised, nothing saved.
    Rules: reconcile_machine_item R8; TC4"""
    re1(db, s)
    re2(db, s)
    snap = msnap(db, s)
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(db, "commit", side_effect=RuntimeError("boom")),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            svc.reconcile_machine_item(
                db,
                machine_id=s.M1.id,
                item_id=s.I1.id,
                workspace_id=s.W1.id,
                current_user=s.U2,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_msnap(db, snap.id).qty == 10
    # Then 4
    assert mel_count(db, s) == 2
    # Then 5
    assert mae_count(db, s.M1) == 0


# [claude] LSV-RMI-13
@pytest.mark.xfail(strict=True, reason=BUG_643)
def test_lsv_rmi_13__bug_643_the_snapshot_is_read_with_for_update_of_machine_items(
    db, s
):
    """LSV-RMI-13 — BUG-643: the snapshot is read with FOR UPDATE OF machine_items.
    Rules: reconcile_machine_item R9 [BUG-643]; HR-10"""
    re1(db, s)
    re2(db, s)
    msnap(db, s)
    commit_point(db)
    with recorder(db) as stmts:
        result, _messages = svc.reconcile_machine_item(
            db,
            machine_id=s.M1.id,
            item_id=s.I1.id,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result["status"] == "adjusted"
    # Then 2
    found = selects_from(stmts, "machine_items")
    for st in found:
        assert _collapse(st).endswith("for update of machine_items")
    # Then 3
    for st in found:
        assert "SKIP LOCKED" not in st.upper()
        assert "NOWAIT" not in st.upper()
        assert _collapse(st).count("for update") == 1


# [claude] LSV-RMI-14
@pytest.mark.xfail(strict=True, reason=BUG_650)
def test_lsv_rmi_14__pass_through_bug_650_an_empty_average_price_still_reconciles(
    db, s
):
    """LSV-RMI-14 — pass-through BUG-650: an empty average price on the latest entry still reconciles.
    Rules: reconcile_machine_item R1, R3, R6 [BUG-650]"""
    re1(db, s)
    mentry(db, s, qty_after=12, avg_price_after=None, performed_at=T(2))
    snap = msnap(db, s)
    commit_point(db)
    result, messages = svc.reconcile_machine_item(
        db,
        machine_id=s.M1.id,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["status"] == "adjusted"
    assert result["discrepancy"] == 2
    # Then 2
    assert messages[0].message == "Discrepancy found and corrected: 2 units adjusted."
    # Then 3
    db.rollback()
    assert reread_msnap(db, snap.id).qty == 12


# =========================================================================== #
# LedgerService.get_project_component_ledger (revisit after launch)
# =========================================================================== #


# [claude] LSV-PCL-01
def test_lsv_pcl_01__an_allowed_user_gets_the_components_entries_newest_first(db, s):
    """LSV-PCL-01 — an allowed user gets the component's entries newest first.
    Rules: get_project_component_ledger R1, R2"""
    p1 = pentry(db, s, performed_at=T(1))
    p2 = pentry(db, s, item_id=s.I2.id, performed_at=T(3))
    p3 = pentry(db, s, performed_at=T(2))
    pentry(db, s, project_component_id=s.C2.id, performed_at=T(4))
    commit_point(db)
    result = svc.get_project_component_ledger(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
    )
    # Then 1
    assert ids(result) == [p2.id, p3.id, p1.id]


# [claude] LSV-PCL-02
def test_lsv_pcl_02__item_id_reaches_the_manager(db, s):
    """LSV-PCL-02 — item_id reaches the manager.
    Rules: get_project_component_ledger R2"""
    p1 = pentry(db, s, performed_at=T(1))
    pentry(db, s, item_id=s.I2.id, performed_at=T(3))
    p3 = pentry(db, s, performed_at=T(2))
    commit_point(db)
    result = svc.get_project_component_ledger(
        db,
        project_component_id=s.C1.id,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        item_id=s.I1.id,
    )
    # Then 1
    assert ids(result) == [p3.id, p1.id]


# [claude] LSV-PCL-03
def test_lsv_pcl_03__skip_and_limit_reach_the_manager_in_their_places(db, s):
    """LSV-PCL-03 — skip and limit reach the manager in their places.
    Rules: get_project_component_ledger R2"""
    p = {k: pentry(db, s, performed_at=T(k)) for k in range(1, 5)}
    commit_point(db)
    result = svc.get_project_component_ledger(
        db,
        project_component_id=s.C1.id,
        workspace_id=s.W1.id,
        user_id=s.U2.id,
        skip=1,
        limit=2,
    )
    # Then 1
    assert ids(result) == [p[3].id, p[2].id]


# [claude] LSV-PCL-04
def test_lsv_pcl_04__the_default_limit_is_100(db, s):
    """LSV-PCL-04 — the default limit is 100.
    Rules: get_project_component_ledger R2 (defaults)"""
    p = {k: pentry(db, s, performed_at=TM(1, k)) for k in range(101)}
    commit_point(db)
    result = svc.get_project_component_ledger(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
    )
    # Then 1
    assert len(result) == 100
    # Then 2
    assert p[0].id not in [r.id for r in result]


# [claude] LSV-PCL-05
def test_lsv_pcl_05__an_unknown_component_404_the_ledger_is_not_read(db, s):
    """LSV-PCL-05 — an unknown component: 404, the ledger is not read.
    Rules: get_project_component_ledger R1, R3"""
    pentry(db, s)
    commit_point(db)
    with recorder(db) as stmts:
        with pytest.raises(HTTPException) as exc:
            svc.get_project_component_ledger(
                db, project_component_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id
            )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Project component not found"
    # Then 3
    assert not names_table(stmts, "project_component_item_ledger")


# [claude] LSV-PCL-06
def test_lsv_pcl_06__a_w2_component_404(db, s):
    """LSV-PCL-06 — a W2 component: 404.
    Rules: get_project_component_ledger R1; HR-16"""
    pentry(db, s, workspace_id=s.W2.id, project_component_id=s.C9.id, item_id=s.I9.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_project_component_ledger(
            db, project_component_id=s.C9.id, workspace_id=s.W1.id, user_id=s.U2.id
        )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Project component not found"


# [claude] LSV-PCL-07
def test_lsv_pcl_07__a_w0_component_404(db, s):
    """LSV-PCL-07 — a W0 component: 404.
    Rules: get_project_component_ledger R1; HR-16"""
    pentry(db, s, workspace_id=s.W0.id, project_component_id=s.C0.id, item_id=s.I0.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_project_component_ledger(
            db, project_component_id=s.C0.id, workspace_id=s.W1.id, user_id=s.U2.id
        )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Project component not found"


# [claude] LSV-PCL-08
def test_lsv_pcl_08__a_private_project_the_user_may_not_open_403(db, s):
    """LSV-PCL-08 — a private project the user may not open: 403.
    Rules: get_project_component_ledger R1"""
    pentry(db, s, project_component_id=s.CP.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_project_component_ledger(
            db, project_component_id=s.CP.id, workspace_id=s.W1.id, user_id=s.U3.id
        )
    # Then 1
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You do not have access to this project"


# [claude] LSV-PCL-09
def test_lsv_pcl_09__a_refusal_neither_commits_nor_rolls_back(db, s):
    """LSV-PCL-09 — a refusal neither commits nor rolls back.
    Rules: get_project_component_ledger R3; TC6"""
    p1 = pentry(db, s)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(p1)
    with spies(db) as (cm, rb):
        with pytest.raises(HTTPException) as exc:
            svc.get_project_component_ledger(
                db, project_component_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id
            )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert p1 in db.dirty


# [claude] LSV-PCL-10
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_lsv_pcl_10__bug_1278_a_component_of_a_deleted_project_gets_the_project_404(
    db, s
):
    """LSV-PCL-10 — BUG-1278: a component of a deleted project gets the project 404, the ledger is not read.
    Rules: get_project_component_ledger R1a [BUG-1278, BUG-1954]"""
    pentry(db, s, project_component_id=s.CD.id)
    commit_point(db)
    with recorder(db) as stmts:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.get_project_component_ledger(
                db, project_component_id=s.CD.id, workspace_id=s.W1.id, user_id=s.U2.id
            )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Project with ID {s.PD.id} not found"
    # Then 3
    assert not names_table(stmts, "project_component_item_ledger")


# =========================================================================== #
# LedgerService.get_project_component_total_cost (revisit after launch)
# =========================================================================== #


# [claude] LSV-PCL-11
def test_lsv_pcl_11__an_allowed_read_neither_commits_nor_rolls_back(db, s):
    """LSV-PCL-11 — an allowed read neither commits nor rolls back.
    Rules: get_project_component_ledger R2, R3; TC6"""
    p1 = pentry(db, s, performed_at=T(1))
    pentry(db, s, performed_at=T(2))
    commit_point(db)
    q = pending_q(db, s)
    edit_e(p1)
    with spies(db) as (cm, rb):
        result = svc.get_project_component_ledger(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
        )
    # Then 1
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert p1 in db.dirty
    # Then 6
    assert len(db.dirty) == 1


# [claude] LSV-PCT-01
def test_lsv_pct_01__an_allowed_user_gets_the_components_summed_cost_as_a_float(db, s):
    """LSV-PCT-01 — an allowed user gets the component's summed cost as a float.
    Rules: get_project_component_total_cost R1, R2, Returns"""
    pentry(db, s, total_cost=Decimal("1000.00"))
    pentry(db, s, transaction_type="consumption", total_cost=Decimal("250.50"))
    pentry(db, s, project_component_id=s.C2.id, total_cost=Decimal("99.00"))
    commit_point(db)
    result = svc.get_project_component_total_cost(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
    )
    # Then 1
    assert set(result.keys()) == {"project_component_id", "total_cost"}
    # Then 2
    assert result["project_component_id"] == s.C1.id
    # Then 3
    assert result["total_cost"] == 1250.5
    assert isinstance(result["total_cost"], float)


# [claude] LSV-PCT-02
def test_lsv_pct_02__no_rows_gives_0_0(db, s):
    """LSV-PCT-02 — no rows gives 0.0.
    Rules: get_project_component_total_cost R2"""
    pentry(db, s, project_component_id=s.C2.id, total_cost=Decimal("99.00"))
    commit_point(db)
    result = svc.get_project_component_total_cost(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
    )
    # Then 1
    assert result == {"project_component_id": s.C1.id, "total_cost": 0.0}
    # Then 2
    assert isinstance(result["total_cost"], float)


# [claude] LSV-PCT-03
def test_lsv_pct_03__an_unknown_component_404_the_cost_is_not_computed(db, s):
    """LSV-PCT-03 — an unknown component: 404, the cost is not computed.
    Rules: get_project_component_total_cost R1"""
    pentry(db, s)
    commit_point(db)
    with recorder(db) as stmts:
        with pytest.raises(HTTPException) as exc:
            svc.get_project_component_total_cost(
                db, project_component_id=MISSING, workspace_id=s.W1.id, user_id=s.U2.id
            )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Project component not found"
    # Then 3
    assert not names_table(stmts, "project_component_item_ledger")


# [claude] LSV-PCT-04
def test_lsv_pct_04__a_w2_component_404(db, s):
    """LSV-PCT-04 — a W2 component: 404.
    Rules: get_project_component_total_cost R1; HR-16"""
    pentry(db, s, workspace_id=s.W2.id, project_component_id=s.C9.id, item_id=s.I9.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_project_component_total_cost(
            db, project_component_id=s.C9.id, workspace_id=s.W1.id, user_id=s.U2.id
        )
    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Project component not found"


# [claude] LSV-PCT-05
def test_lsv_pct_05__a_private_project_the_user_may_not_open_403(db, s):
    """LSV-PCT-05 — a private project the user may not open: 403.
    Rules: get_project_component_total_cost R1"""
    pentry(db, s, project_component_id=s.CP.id)
    commit_point(db)
    with pytest.raises(HTTPException) as exc:
        svc.get_project_component_total_cost(
            db, project_component_id=s.CP.id, workspace_id=s.W1.id, user_id=s.U3.id
        )
    # Then 1
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You do not have access to this project"


# [claude] LSV-PCT-06
def test_lsv_pct_06__the_cost_read_neither_commits_nor_rolls_back(db, s):
    """LSV-PCT-06 — the cost read neither commits nor rolls back.
    Rules: get_project_component_total_cost R3; TC6"""
    p1 = pentry(db, s)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(p1)
    with spies(db) as (cm, rb):
        result = svc.get_project_component_total_cost(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id, user_id=s.U2.id
        )
    # Then 1
    assert result["project_component_id"] == s.C1.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert p1 in db.dirty


# [claude] LSV-PCT-07
@pytest.mark.xfail(strict=True, reason=BUG_1278)
def test_lsv_pct_07__bug_1278_a_component_of_a_deleted_project_gets_the_project_404(
    db, s
):
    """LSV-PCT-07 — BUG-1278: a component of a deleted project gets the project 404, the cost is not computed.
    Rules: get_project_component_total_cost R1a [BUG-1278, BUG-1954]"""
    pentry(db, s, project_component_id=s.CD.id, total_cost=Decimal("40.00"))
    commit_point(db)
    with recorder(db) as stmts:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            svc.get_project_component_total_cost(
                db, project_component_id=s.CD.id, workspace_id=s.W1.id, user_id=s.U2.id
            )
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Project with ID {s.PD.id} not found"
    # Then 3
    assert not names_table(stmts, "project_component_item_ledger")


# =========================================================================== #
# LedgerService.get_inventory_ledger
# =========================================================================== #


# [claude] LSV-GIL-01
def test_lsv_gil_01__only_the_workspace_every_w1_entry_newest_first(db, s):
    """LSV-GIL-01 — only the workspace: every W1 entry newest first, W0 and W2 left out.
    Rules: get_inventory_ledger R1; HR-16"""
    g0(db, s)
    r1 = g1(db, s)
    r2 = g2(db, s)
    r3 = g3(db, s)
    r4 = g4(db, s)
    g9(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [r4.id, r3.id, r2.id, r1.id]


# [claude] LSV-GIL-02
def test_lsv_gil_02__inventory_type_reaches_the_manager(db, s):
    """LSV-GIL-02 — inventory_type reaches the manager.
    Rules: get_inventory_ledger R1"""
    g1(db, s)
    r2 = g2(db, s)
    g3(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(
        db, workspace_id=s.W1.id, inventory_type=InventoryTypeEnum.DAMAGED
    )
    # Then 1
    assert ids(result) == [r2.id]


# [claude] LSV-GIL-03
def test_lsv_gil_03__factory_id_reaches_the_manager(db, s):
    """LSV-GIL-03 — factory_id reaches the manager.
    Rules: get_inventory_ledger R1"""
    g1(db, s)
    r3 = g3(db, s)
    g4(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(db, workspace_id=s.W1.id, factory_id=s.F2.id)
    # Then 1
    assert ids(result) == [r3.id]


# [claude] LSV-GIL-04
def test_lsv_gil_04__item_id_reaches_the_manager(db, s):
    """LSV-GIL-04 — item_id reaches the manager.
    Rules: get_inventory_ledger R1"""
    g1(db, s)
    g3(db, s)
    r4 = g4(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(db, workspace_id=s.W1.id, item_id=s.I2.id)
    # Then 1
    assert ids(result) == [r4.id]


# [claude] LSV-GIL-05
def test_lsv_gil_05__transaction_type_reaches_the_manager(db, s):
    """LSV-GIL-05 — transaction_type reaches the manager.
    Rules: get_inventory_ledger R1"""
    r1 = g1(db, s)
    g2(db, s)
    r3 = g3(db, s)
    g4(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(
        db, workspace_id=s.W1.id, transaction_type="transfer_in"
    )
    # Then 1
    assert ids(result) == [r3.id, r1.id]


# [claude] LSV-GIL-06
def test_lsv_gil_06__a_full_date_range_reaches_the_manager(db, s):
    """LSV-GIL-06 — a full date range reaches the manager.
    Rules: get_inventory_ledger R1"""
    g1(db, s)
    r2 = g2(db, s)
    r3 = g3(db, s)
    g4(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(
        db, workspace_id=s.W1.id, start_date=T(2), end_date=T(3)
    )
    # Then 1
    assert ids(result) == [r3.id, r2.id]


# [claude] LSV-GIL-07
def test_lsv_gil_07__skip_and_limit_reach_the_manager_in_their_places(db, s):
    """LSV-GIL-07 — skip and limit reach the manager in their places.
    Rules: get_inventory_ledger R1"""
    g1(db, s)
    r2 = g2(db, s)
    r3 = g3(db, s)
    g4(db, s)
    commit_point(db)
    result = svc.get_inventory_ledger(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert ids(result) == [r3.id, r2.id]


# [claude] LSV-GIL-08
def test_lsv_gil_08__the_default_limit_is_100(db, s):
    """LSV-GIL-08 — the default limit is 100.
    Rules: get_inventory_ledger R1 (defaults)"""
    q = {k: ientry(db, s, performed_at=TM(1, k)) for k in range(101)}
    commit_point(db)
    result = svc.get_inventory_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert q[0].id not in [r.id for r in result]


# [claude] LSV-GIL-09
def test_lsv_gil_09__the_read_neither_commits_nor_rolls_back(db, s):
    """LSV-GIL-09 — the read neither commits nor rolls back.
    Rules: get_inventory_ledger R2; TC6"""
    g1(db, s)
    r2 = g2(db, s)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(r2)
    with spies(db) as (cm, rb):
        result = svc.get_inventory_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert r2 in db.dirty
    # Then 6
    assert len(db.dirty) == 1


# =========================================================================== #
# LedgerService.get_inventory_balance
# =========================================================================== #


# [claude] LSV-GIB-01
def test_lsv_gib_01__an_empty_bucket_ids_and_the_enum_value_echoed_quantity_0_value_0(
    db, s
):
    """LSV-GIB-01 — an empty bucket: ids and the enum value echoed, quantity 0, value 0.
    Rules: get_inventory_balance R1, R2, R3 (value part that holds today), Returns"""
    commit_point(db)
    result = svc.get_inventory_balance(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.DAMAGED,
        workspace_id=s.W1.id,
    )
    # Then 1
    assert set(result.keys()) == {
        "factory_id",
        "item_id",
        "inventory_type",
        "quantity",
        "total_value",
    }
    # Then 2
    assert result["factory_id"] == s.F1.id
    assert result["item_id"] == s.I1.id
    # Then 3
    assert result["inventory_type"] == "DAMAGED"
    # Then 4
    assert type(result["inventory_type"]) is str
    # Then 5
    assert result["quantity"] == 0
    # Then 6
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GIB-02
@pytest.mark.xfail(strict=True, reason=BUG_3043)
def test_lsv_gib_02__bug_3043_an_empty_buckets_value_is_decimal_0_00(db, s):
    """LSV-GIB-02 — BUG-3043: an empty bucket's value is Decimal("0.00").
    Rules: get_inventory_balance R3 [BUG-3043]"""
    commit_point(db)
    result = svc.get_inventory_balance(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
    )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert isinstance(result["total_value"], Decimal)
    # Then 3
    assert str(result["total_value"]) == "0.00"


# [claude] LSV-GIB-03
def test_lsv_gib_03__a_value_without_value_is_echoed_as_given(db, s):
    """LSV-GIB-03 — a value without .value is echoed as given.
    Rules: get_inventory_balance R2"""
    commit_point(db)
    with patch.object(
        svc.ledger_manager, "get_inventory_balance", return_value=(0, Decimal("0.00"))
    ):
        result = svc.get_inventory_balance(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type="STORAGE",
            workspace_id=s.W1.id,
        )
    # Then 1
    assert result["inventory_type"] == "STORAGE"
    # Then 2
    assert result["quantity"] == 0


# [claude] LSV-GIB-04
def test_lsv_gib_04__the_managers_quantity_and_value_are_shaped_into_the_dict(db, s):
    """LSV-GIB-04 — the manager's quantity and value are shaped into the dict.
    Rules: get_inventory_balance R1, R3 (value part that holds today)"""
    commit_point(db)
    with patch.object(
        svc.ledger_manager,
        "get_inventory_balance",
        return_value=(50, Decimal("1234.50")),
    ):
        result = svc.get_inventory_balance(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
        )
    # Then 1
    assert result["quantity"] == 50
    # Then 2
    assert result["total_value"] == Decimal("1234.50")
    # Then 3
    assert result["inventory_type"] == "STORAGE"
    # Then 4
    assert type(result["inventory_type"]) is str


# [claude] LSV-GIB-05
@pytest.mark.xfail(strict=True, reason=BUG_3043)
def test_lsv_gib_05__bug_3043_a_non_zero_value_stays_the_exact_decimal(db, s):
    """LSV-GIB-05 — BUG-3043: a non-zero value stays the exact Decimal.
    Rules: get_inventory_balance R3 [BUG-3043]"""
    commit_point(db)
    with patch.object(
        svc.ledger_manager,
        "get_inventory_balance",
        return_value=(50, Decimal("1234.50")),
    ):
        result = svc.get_inventory_balance(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
        )
    # Then 1
    assert result["quantity"] == 50
    # Then 2
    assert isinstance(result["total_value"], Decimal)
    # Then 3
    assert str(result["total_value"]) == "1234.50"


# [claude] LSV-GIB-06
def test_lsv_gib_06__pass_through_bug_655_a_bucket_with_history_answers_its_balance(
    db, s
):
    """LSV-GIB-06 — pass-through BUG-655: a bucket with history answers its balance.
    Rules: get_inventory_balance R1 [BUG-655]"""
    ientry(db, s, qty_after=10, avg_price_after=Decimal("5.00"), performed_at=T(1))
    ientry(db, s, qty_after=40, avg_price_after=Decimal("6.50"), performed_at=T(2))
    commit_point(db)
    result = svc.get_inventory_balance(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
    )
    # Then 1
    assert result["quantity"] == 40
    # Then 2
    assert result["total_value"] == Decimal("260.00")


# [claude] LSV-GIB-07
def test_lsv_gib_07__a_w2_factorys_bucket_is_not_visible_from_w1(db, s):
    """LSV-GIB-07 — a W2 factory's bucket is not visible from W1.
    Rules: get_inventory_balance R1; HR-16"""
    ientry(
        db, s, workspace_id=s.W2.id, factory_id=s.F9.id, item_id=s.I9.id, qty_after=30
    )
    commit_point(db)
    result = svc.get_inventory_balance(
        db,
        factory_id=s.F9.id,
        item_id=s.I9.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
    )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GIB-08
def test_lsv_gib_08__a_w0_factorys_bucket_is_not_visible_from_w1(db, s):
    """LSV-GIB-08 — a W0 factory's bucket is not visible from W1.
    Rules: get_inventory_balance R1; HR-16"""
    ientry(
        db, s, workspace_id=s.W0.id, factory_id=s.F0.id, item_id=s.I0.id, qty_after=30
    )
    commit_point(db)
    result = svc.get_inventory_balance(
        db,
        factory_id=s.F0.id,
        item_id=s.I0.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
    )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert result["total_value"] == Decimal("0.00")


# [claude] LSV-GIB-09
def test_lsv_gib_09__the_balance_read_neither_commits_nor_rolls_back(db, s):
    """LSV-GIB-09 — the balance read neither commits nor rolls back.
    Rules: get_inventory_balance R4; TC6"""
    r2 = ientry(db, s, item_id=s.I2.id)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(r2)
    with spies(db) as (cm, rb):
        result = svc.get_inventory_balance(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
        )
    # Then 1
    assert result["quantity"] == 0
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert r2 in db.dirty
    # Then 6
    assert len(db.dirty) == 1


# =========================================================================== #
# LedgerService.reconcile_inventory
# =========================================================================== #


# [claude] LSV-RINV-01
def test_lsv_rinv_01__balanced_one_success_message_committed_nothing_written(db, s):
    """LSV-RINV-01 — balanced: one success message, committed, nothing written.
    Rules: reconcile_inventory R1, R2, R6; TC1"""
    snap = isnap(db, s, qty=0, avg_price=Decimal("0.00"))
    commit_point(db)
    extra_x(db, s)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "balanced",
        "ledger_qty": 0,
        "snapshot_qty": 0,
        "discrepancy": 0,
        "adjustment_created": False,
    }
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].type.value == "success"
    assert messages[0].message == "Inventory is balanced at 0 units."
    assert messages[0].details is None
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 1
    # Then 5
    assert il_count_w1(db, s) == 0
    # Then 6
    row = reread_isnap(db, snap.id)
    assert row.qty == 0
    assert row.updated_by == s.U1.id


# [claude] LSV-RINV-02
def test_lsv_rinv_02__adjusted_a_warning_with_the_result_then_a_success_message(db, s):
    """LSV-RINV-02 — adjusted: a warning with the result, then a success message.
    Rules: reconcile_inventory R1, R3"""
    isnap(db, s)
    commit_point(db)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "adjusted",
        "ledger_qty": 0,
        "snapshot_qty": 4,
        "discrepancy": -4,
        "adjustment_created": True,
    }
    # Then 2
    assert len(messages) == 2
    # Then 3
    assert messages[0].type.value == "warning"
    assert messages[0].message == "Discrepancy found and corrected: 4 units adjusted."
    # Then 4
    assert messages[0].details == result
    # Then 5
    assert messages[1].type.value == "success"
    assert messages[1].message == "Snapshot updated to match ledger."
    assert messages[1].details is None


# [claude] LSV-RINV-03
def test_lsv_rinv_03__adjusted_snapshot_and_adjustment_row_committed_as_the_current_user_no_event(
    db, s
):
    """LSV-RINV-03 — adjusted: the snapshot and the adjustment row are committed as the current user, no event.
    Rules: reconcile_inventory R1, R6; TC1"""
    snap = isnap(db, s)
    commit_point(db)
    result, _messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["status"] == "adjusted"
    # Then 2
    db.rollback()
    assert reread_isnap(db, snap.id).qty == 0
    # Then 3
    rows = il_rows_bucket(db, s)
    assert len(rows) == 1
    # Then 4
    assert rows[0].transaction_type == "inventory_adjustment"
    assert rows[0].source_type == "reconciliation"
    assert rows[0].performed_by == s.U2.id
    assert rows[0].qty_after == 0
    # Then 5
    assert rows[0].notes.startswith(
        "Reconciliation adjustment: Snapshot was 4, ledger shows 0. Discrepancy: -4"
    )
    # Then 6
    assert mae_count(db) == 0


# [claude] LSV-RINV-04
def test_lsv_rinv_04__adjusted_with_discrepancy_0_two_messages_the_warning_carries_the_result(
    db, s
):
    """LSV-RINV-04 — adjusted with discrepancy 0: two messages, the warning carries the result, committed.
    Rules: reconcile_inventory R4 (bug-independent part), R6"""
    r = {
        "status": "adjusted",
        "ledger_qty": 10,
        "snapshot_qty": 10,
        "discrepancy": 0,
        "adjustment_created": True,
    }
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert len(messages) == 2
    # Then 3
    assert messages[0].type.value == "warning"
    assert messages[0].details == r
    # Then 4
    assert messages[1].type.value == "success"
    assert messages[1].message == "Snapshot updated to match ledger."
    # Then 5
    db.rollback()
    assert dept_count(db, "Extra") == 1


# [claude] LSV-RINV-05
@pytest.mark.xfail(strict=True, reason=BUG_3042)
def test_lsv_rinv_05__bug_3042_a_price_only_correction_names_the_average_price(db, s):
    """LSV-RINV-05 — BUG-3042: a price-only correction names the average price.
    Rules: reconcile_inventory R4 [BUG-3042]"""
    r = {
        "status": "adjusted",
        "ledger_qty": 10,
        "snapshot_qty": 10,
        "discrepancy": 0,
        "adjustment_created": True,
    }
    commit_point(db)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        _result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert len(messages) == 2
    # Then 2
    assert (
        messages[0].message
        == "Discrepancy found and corrected: average price updated to match ledger."
    )


# [claude] LSV-RINV-06
def test_lsv_rinv_06__a_positive_non_zero_discrepancy_keeps_the_units_text(db, s):
    """LSV-RINV-06 — a positive non-zero discrepancy keeps the units text.
    Rules: reconcile_inventory R3"""
    r = {
        "status": "adjusted",
        "ledger_qty": 13,
        "snapshot_qty": 10,
        "discrepancy": 3,
        "adjustment_created": True,
    }
    commit_point(db)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert len(messages) == 2
    # Then 3
    assert messages[0].message == "Discrepancy found and corrected: 3 units adjusted."


# [claude] LSV-RINV-07
def test_lsv_rinv_07__error_one_warning_with_the_managers_text_committed(db, s):
    """LSV-RINV-07 — error: one warning with the manager's text, committed.
    Rules: reconcile_inventory R5"""
    r = {
        "status": "error",
        "ledger_qty": 12,
        "snapshot_qty": 0,
        "discrepancy": 12,
        "adjustment_created": False,
        "error": "Snapshot missing for item with ledger transactions",
    }
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].type.value == "warning"
    assert (
        messages[0].message
        == "Reconciliation issue: Snapshot missing for item with ledger transactions"
    )
    assert messages[0].details is None
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 1


# [claude] LSV-RINV-08
def test_lsv_rinv_08__an_error_result_without_an_error_text_says_unknown_error(db, s):
    """LSV-RINV-08 — an error result without an error text says "Unknown error".
    Rules: reconcile_inventory R5"""
    r = {
        "status": "error",
        "ledger_qty": 3,
        "snapshot_qty": 0,
        "discrepancy": 3,
        "adjustment_created": False,
    }
    commit_point(db)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert len(messages) == 1
    # Then 3
    assert messages[0].message == "Reconciliation issue: Unknown error"


# [claude] LSV-RINV-09
def test_lsv_rinv_09__any_other_status_gives_no_message_and_still_commits(db, s):
    """LSV-RINV-09 — any other status gives no message and still commits.
    Rules: reconcile_inventory R5"""
    r = {
        "status": "pending",
        "ledger_qty": 3,
        "snapshot_qty": 3,
        "discrepancy": 0,
        "adjustment_created": False,
    }
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        result, messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result is r
    # Then 2
    assert messages == []
    # Then 3
    db.rollback()
    assert dept_count(db, "Extra") == 1


# [claude] LSV-RINV-10
def test_lsv_rinv_10__an_empty_bucket_with_no_snapshot_one_message_nothing_written_committed(
    db, s
):
    """LSV-RINV-10 — an empty bucket with no snapshot: one message, nothing written, committed.
    Rules: reconcile_inventory R2, R5 (bug-independent part of BUG-649)"""
    commit_point(db)
    extra_x(db, s)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["ledger_qty"] == 0
    assert result["adjustment_created"] is False
    # Then 2
    assert len(messages) == 1
    # Then 3
    db.rollback()
    assert dept_count(db, "Extra") == 1
    # Then 4
    assert inv_count(db, s) == 0
    # Then 5
    assert il_count_w1(db, s) == 0


# [claude] LSV-RINV-11
@pytest.mark.xfail(strict=True, reason=BUG_649)
def test_lsv_rinv_11__pass_through_bug_649_an_empty_bucket_is_balanced_at_0_units(
    db, s
):
    """LSV-RINV-11 — pass-through BUG-649: an empty bucket is balanced at 0 units.
    Rules: reconcile_inventory R2 [BUG-649]"""
    commit_point(db)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert len(messages) == 1
    # Then 2
    assert messages[0].type.value == "success"
    assert messages[0].message == "Inventory is balanced at 0 units."
    # Then 3
    assert result["status"] == "balanced"


# [claude] LSV-RINV-12
def test_lsv_rinv_12__an_exception_after_the_manager_wrote_rolled_back_same_object_nothing_saved(
    db, s
):
    """LSV-RINV-12 — an exception after the manager wrote: rolled back, same object, nothing saved.
    Rules: reconcile_inventory R6; TC3"""
    snap = isnap(db, s)
    commit_point(db)
    extra_x(db, s)
    with writes_then_raises("reconcile_inventory") as err:
        with spies(db) as (_cm, rb):
            with pytest.raises(RuntimeError) as exc:
                svc.reconcile_inventory(
                    db,
                    factory_id=s.F1.id,
                    item_id=s.I1.id,
                    inventory_type=InventoryTypeEnum.STORAGE,
                    workspace_id=s.W1.id,
                    current_user=s.U2,
                )
    # Then 1
    assert exc.value is err
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    db.rollback()
    row = reread_isnap(db, snap.id)
    assert row.qty == 4
    assert row.updated_by == s.U1.id
    # Then 4
    assert il_count_w1(db, s) == 0
    # Then 5
    assert dept_count(db, "Extra") == 0
    # Then 6
    assert usable(db)


# [claude] LSV-RINV-13
def test_lsv_rinv_13__an_exception_while_building_the_messages_rolls_back(db, s):
    """LSV-RINV-13 — an exception while building the messages rolls back.
    Rules: reconcile_inventory R6; TC3"""
    r = {"status": "balanced"}
    commit_point(db)
    extra_x(db, s)
    with patch.object(svc.ledger_manager, "reconcile_inventory", return_value=r):
        with spies(db) as (cm, rb):
            with pytest.raises(KeyError) as exc:
                svc.reconcile_inventory(
                    db,
                    factory_id=s.F1.id,
                    item_id=s.I1.id,
                    inventory_type=InventoryTypeEnum.STORAGE,
                    workspace_id=s.W1.id,
                    current_user=s.U2,
                )
    # Then 1
    assert exc.value.args == ("ledger_qty",)
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert cm.call_count == 0
    # Then 4
    db.rollback()
    assert dept_count(db, "Extra") == 0


# [claude] LSV-RINV-14
def test_lsv_rinv_14__a_failing_commit_is_rolled_back_and_re_raised_nothing_saved(
    db, s
):
    """LSV-RINV-14 — a failing commit is rolled back and re-raised, nothing saved.
    Rules: reconcile_inventory R6; TC4"""
    snap = isnap(db, s)
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with (
            patch.object(db, "commit", side_effect=RuntimeError("boom")),
            patch.object(db, "rollback", wraps=db.rollback) as rb,
        ):
            svc.reconcile_inventory(
                db,
                factory_id=s.F1.id,
                item_id=s.I1.id,
                inventory_type=InventoryTypeEnum.STORAGE,
                workspace_id=s.W1.id,
                current_user=s.U2,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread_isnap(db, snap.id).qty == 4
    # Then 4
    assert il_count_w1(db, s) == 0


# [claude] LSV-RINV-15
@pytest.mark.xfail(strict=True, reason=BUG_644)
def test_lsv_rinv_15__bug_644_the_snapshot_is_read_with_for_update_of_inventory(db, s):
    """LSV-RINV-15 — BUG-644: the snapshot is read with FOR UPDATE OF inventory.
    Rules: reconcile_inventory R7 [BUG-644]; HR-10"""
    isnap(db, s)
    commit_point(db)
    with recorder(db) as stmts:
        result, _messages = svc.reconcile_inventory(
            db,
            factory_id=s.F1.id,
            item_id=s.I1.id,
            inventory_type=InventoryTypeEnum.STORAGE,
            workspace_id=s.W1.id,
            current_user=s.U2,
        )
    # Then 1
    assert result["status"] == "adjusted"
    # Then 2
    found = selects_from(stmts, "inventory")
    for st in found:
        assert _collapse(st).endswith("for update of inventory")
    # Then 3
    for st in found:
        assert "SKIP LOCKED" not in st.upper()
        assert "NOWAIT" not in st.upper()
        assert _collapse(st).count("for update") == 1


# [claude] LSV-RINV-16
def test_lsv_rinv_16__pass_through_bug_655_a_bucket_with_history_reconciles_and_commits(
    db, s
):
    """LSV-RINV-16 — pass-through BUG-655: a bucket with history reconciles and commits.
    Rules: reconcile_inventory R1, R3, R6 [BUG-655]"""
    ientry(db, s, qty_after=12, avg_price_after=Decimal("6.50"), performed_at=T(1))
    snap = isnap(db, s, qty=10, avg_price=Decimal("6.50"))
    commit_point(db)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result == {
        "status": "adjusted",
        "ledger_qty": 12,
        "snapshot_qty": 10,
        "discrepancy": 2,
        "adjustment_created": True,
    }
    # Then 2
    assert messages[0].message == "Discrepancy found and corrected: 2 units adjusted."
    # Then 3
    db.rollback()
    assert reread_isnap(db, snap.id).qty == 12


# [claude] LSV-RINV-17
@pytest.mark.xfail(strict=True, reason=f"{BUG_653}; {BUG_3042}")
def test_lsv_rinv_17__pass_through_bug_653_a_wrong_price_alone_is_corrected_and_named(
    db, s
):
    """LSV-RINV-17 — pass-through BUG-653: a wrong price alone is corrected and named.
    Rules: reconcile_inventory R4 [BUG-653, BUG-3042]"""
    snap = isnap(db, s, qty=0, avg_price=Decimal("5.00"))
    commit_point(db)
    result, messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["status"] == "adjusted"
    assert result["discrepancy"] == 0
    # Then 2
    assert (
        messages[0].message
        == "Discrepancy found and corrected: average price updated to match ledger."
    )
    # Then 3
    db.rollback()
    assert reread_isnap(db, snap.id).avg_price == Decimal("0.00")


# [claude] LSV-RINV-18
@pytest.mark.xfail(strict=True, reason=BUG_652)
def test_lsv_rinv_18__pass_through_bug_652_the_committed_snapshot_names_the_reconciling_user(
    db, s
):
    """LSV-RINV-18 — pass-through BUG-652: the committed snapshot names the reconciling user.
    Rules: reconcile_inventory R1, R6 [BUG-652]"""
    snap = isnap(db, s)
    commit_point(db)
    result, _messages = svc.reconcile_inventory(
        db,
        factory_id=s.F1.id,
        item_id=s.I1.id,
        inventory_type=InventoryTypeEnum.STORAGE,
        workspace_id=s.W1.id,
        current_user=s.U2,
    )
    # Then 1
    assert result["status"] == "adjusted"
    # Then 2
    db.rollback()
    assert reread_isnap(db, snap.id).updated_by == s.U2.id


# =========================================================================== #
# LedgerService.get_attachment_ledger
# =========================================================================== #


# [claude] LSV-GAL-01
def test_lsv_gal_01__only_the_workspace_every_w1_entry_newest_first(db, s):
    """LSV-GAL-01 — only the workspace: every W1 entry newest first, W0 and W2 left out.
    Rules: get_attachment_ledger R1; HR-16"""
    l0(db, s)
    r1 = l1(db, s)
    r2 = l2(db, s)
    r3 = l3(db, s)
    l9(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [r3.id, r2.id, r1.id]


# [claude] LSV-GAL-02
def test_lsv_gal_02__attachment_id_reaches_the_manager(db, s):
    """LSV-GAL-02 — attachment_id reaches the manager.
    Rules: get_attachment_ledger R1"""
    r1 = l1(db, s)
    r2 = l2(db, s)
    l3(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id, attachment_id=s.A1.id)
    # Then 1
    assert ids(result) == [r2.id, r1.id]


# [claude] LSV-GAL-03
def test_lsv_gal_03__entity_type_reaches_the_manager(db, s):
    """LSV-GAL-03 — entity_type reaches the manager.
    Rules: get_attachment_ledger R1"""
    r1 = l1(db, s)
    l2(db, s)
    r3 = l3(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id, entity_type="machine")
    # Then 1
    assert ids(result) == [r3.id, r1.id]


# [claude] LSV-GAL-04
def test_lsv_gal_04__transaction_type_reaches_the_manager(db, s):
    """LSV-GAL-04 — transaction_type reaches the manager.
    Rules: get_attachment_ledger R1"""
    l1(db, s)
    r2 = l2(db, s)
    r3 = l3(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(
        db, workspace_id=s.W1.id, transaction_type="deleted"
    )
    # Then 1
    assert ids(result) == [r3.id, r2.id]


# [claude] LSV-GAL-05
def test_lsv_gal_05__start_date_alone_reaches_the_manager(db, s):
    """LSV-GAL-05 — start_date alone reaches the manager.
    Rules: get_attachment_ledger R1"""
    l1(db, s)
    r2 = l2(db, s)
    r3 = l3(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id, start_date=TA(2))
    # Then 1
    assert ids(result) == [r3.id, r2.id]


# [claude] LSV-GAL-06
def test_lsv_gal_06__end_date_alone_reaches_the_manager(db, s):
    """LSV-GAL-06 — end_date alone reaches the manager.
    Rules: get_attachment_ledger R1"""
    r1 = l1(db, s)
    r2 = l2(db, s)
    l3(db, s)
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id, end_date=TA(2))
    # Then 1
    assert ids(result) == [r2.id, r1.id]


# [claude] LSV-GAL-07
def test_lsv_gal_07__skip_and_limit_reach_the_manager_in_their_places(db, s):
    """LSV-GAL-07 — skip and limit reach the manager in their places.
    Rules: get_attachment_ledger R1"""
    l1(db, s)
    r2 = l2(db, s)
    r3 = l3(db, s)
    aentry(db, s, performed_at=TA(4))
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id, skip=1, limit=2)
    # Then 1
    assert ids(result) == [r3.id, r2.id]


# [claude] LSV-GAL-08
def test_lsv_gal_08__the_default_limit_is_100(db, s):
    """LSV-GAL-08 — the default limit is 100.
    Rules: get_attachment_ledger R1 (defaults)"""
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    q = {k: aentry(db, s, performed_at=base + timedelta(minutes=k)) for k in range(101)}
    commit_point(db)
    result = svc.get_attachment_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert q[0].id not in [r.id for r in result]


# [claude] LSV-GAL-09
def test_lsv_gal_09__the_read_neither_commits_nor_rolls_back(db, s):
    """LSV-GAL-09 — the read neither commits nor rolls back.
    Rules: get_attachment_ledger R2; TC6"""
    l1(db, s)
    r2 = l2(db, s)
    commit_point(db)
    q = pending_q(db, s)
    edit_e(r2)
    with spies(db) as (cm, rb):
        result = svc.get_attachment_ledger(db, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 2
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert r2 in db.dirty
    # Then 6
    assert len(db.dirty) == 1


# =========================================================================== #
# LedgerService.get_item_movement_summary
# =========================================================================== #


# [claude] LSV-IMS-01
def test_lsv_ims_01__with_both_dates_the_three_lists_in_range_of_the_workspace(db, s):
    """LSV-IMS-01 — with both dates: the three lists, in range, of the workspace.
    Rules: get_item_movement_summary R1, Returns; HR-16"""
    em1 = mentry(db, s, performed_at=T(5))
    mentry(db, s, performed_at=T(20))
    ei1 = ientry(db, s, performed_at=T(6))
    mentry(
        db,
        s,
        workspace_id=s.W2.id,
        machine_id=s.M9.id,
        item_id=s.I9.id,
        performed_at=T(5),
    )
    commit_point(db)
    result = svc.get_item_movement_summary(
        db, item_id=s.I1.id, workspace_id=s.W1.id, start_date=T(1), end_date=T(10)
    )
    # Then 1
    assert set(result.keys()) == {"machine", "project", "inventory"}
    # Then 2
    assert ids(result["machine"]) == [em1.id]
    # Then 3
    assert ids(result["inventory"]) == [ei1.id]
    # Then 4
    assert result["project"] == []


# [claude] LSV-IMS-02
@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_lsv_ims_02__pass_through_bug_341_another_items_entries_are_left_out(db, s):
    """LSV-IMS-02 — pass-through BUG-341: another item's entries are left out.
    Rules: get_item_movement_summary R1 [BUG-341]"""
    em1 = mentry(db, s, performed_at=T(5))
    mentry(db, s, item_id=s.I2.id, performed_at=T(6))
    commit_point(db)
    result = svc.get_item_movement_summary(
        db, item_id=s.I1.id, workspace_id=s.W1.id, start_date=T(1), end_date=T(10)
    )
    # Then 1
    assert em1.id in [r.id for r in result["machine"]]
    # Then 2
    assert ids(result["machine"]) == [em1.id]


# [claude] LSV-IMS-03
@pytest.mark.xfail(strict=True, reason=BUG_646)
def test_lsv_ims_03__pass_through_bug_646_without_dates_the_items_entries_come_back(
    db, s
):
    """LSV-IMS-03 — pass-through BUG-646: without dates the item's entries come back.
    Rules: get_item_movement_summary R1 [BUG-646]"""
    em1 = mentry(db, s, performed_at=T(5))
    em2 = mentry(db, s, performed_at=T(20))
    ei1 = ientry(db, s, performed_at=T(6))
    commit_point(db)
    result = svc.get_item_movement_summary(db, item_id=s.I1.id, workspace_id=s.W1.id)
    # Then 1
    assert set(result.keys()) == {"machine", "project", "inventory"}
    # Then 2
    assert ids(result["machine"]) == [em2.id, em1.id]
    # Then 3
    assert ids(result["inventory"]) == [ei1.id]


# [claude] LSV-IMS-04
@pytest.mark.xfail(strict=True, reason=BUG_648)
def test_lsv_ims_04__bug_648_skip_and_limit_reach_the_manager(db, s):
    """LSV-IMS-04 — BUG-648: skip and limit reach the manager.
    Rules: get_item_movement_summary R2 [BUG-648]"""
    em = {k: mentry(db, s, performed_at=T(k + 1)) for k in range(1, 4)}
    commit_point(db)
    result = svc.get_item_movement_summary(
        db,
        item_id=s.I1.id,
        workspace_id=s.W1.id,
        start_date=T(1),
        end_date=T(10),
        skip=1,
        limit=1,
    )
    # Then 1
    assert ids(result["machine"]) == [em[2].id]


# [claude] LSV-IMS-05
def test_lsv_ims_05__by_default_at_most_100_entries_per_list(db, s):
    """LSV-IMS-05 — by default at most 100 entries per list.
    Rules: get_item_movement_summary R1, R2 (default 100, holds today and after BUG-648)"""
    q = {k: mentry(db, s, performed_at=TM(2, k)) for k in range(101)}
    commit_point(db)
    result = svc.get_item_movement_summary(
        db, item_id=s.I1.id, workspace_id=s.W1.id, start_date=T(1), end_date=T(10)
    )
    # Then 1
    assert len(result["machine"]) == 100
    # Then 2
    assert q[0].id not in [r.id for r in result["machine"]]


# [claude] LSV-IMS-06
def test_lsv_ims_06__the_report_neither_commits_nor_rolls_back(db, s):
    """LSV-IMS-06 — the report neither commits nor rolls back.
    Rules: get_item_movement_summary R3; TC6"""
    em1 = mentry(db, s, performed_at=T(5))
    commit_point(db)
    q = pending_q(db, s)
    edit_e(em1)
    with spies(db) as (cm, rb):
        result = svc.get_item_movement_summary(
            db, item_id=s.I1.id, workspace_id=s.W1.id, start_date=T(1), end_date=T(10)
        )
    # Then 1
    assert len(result["machine"]) == 1
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new
    # Then 5
    assert em1 in db.dirty


# =========================================================================== #
# LedgerService.get_transactions_by_user
# =========================================================================== #


# [claude] LSV-TBU-01
@pytest.mark.xfail(strict=True, reason=BUG_645)
def test_lsv_tbu_01__pass_through_bug_645_the_users_entries_per_ledger(db, s):
    """LSV-TBU-01 — pass-through BUG-645: the user's entries per ledger.
    Rules: get_transactions_by_user R1 [BUG-645]"""
    mu = mentry(db, s, performed_by=s.U2.id, performed_at=T(2))
    mentry(db, s, performed_at=T(3))
    iu = ientry(db, s, performed_by=s.U2.id, performed_at=T(4))
    ientry(db, s, performed_at=T(5))
    commit_point(db)
    result = svc.get_transactions_by_user(db, user_id=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert set(result.keys()) == {"machine", "project", "inventory"}
    # Then 2
    assert ids(result["machine"]) == [mu.id]
    # Then 3
    assert ids(result["inventory"]) == [iu.id]
    # Then 4
    assert result["project"] == []


# [claude] LSV-TBU-02
@pytest.mark.xfail(strict=True, reason=BUG_645)
def test_lsv_tbu_02__pass_through_bug_645_a_non_member_id_is_accepted_only_w1_entries(
    db, s
):
    """LSV-TBU-02 — pass-through BUG-645: a non-member id is accepted and only W1 entries can come back.
    Rules: get_transactions_by_user R2 [BUG-645]; HR-16"""
    mentry(
        db,
        s,
        workspace_id=s.W2.id,
        machine_id=s.M9.id,
        item_id=s.I9.id,
        performed_by=s.U9.id,
    )
    ientry(
        db,
        s,
        workspace_id=s.W2.id,
        factory_id=s.F9.id,
        item_id=s.I9.id,
        performed_by=s.U9.id,
    )
    commit_point(db)
    result = svc.get_transactions_by_user(db, user_id=s.U9.id, workspace_id=s.W1.id)
    # Then 1
    assert result == {"machine": [], "project": [], "inventory": []}


# [claude] LSV-TBU-03
def test_lsv_tbu_03__an_exception_from_the_manager_passes_on_without_commit_or_rollback(
    db, s
):
    """LSV-TBU-03 — an exception from the manager passes on with no commit and no rollback.
    Rules: get_transactions_by_user R3; TC6"""
    err = RuntimeError("mgr")
    commit_point(db)
    q = pending_q(db, s)
    with patch.object(svc.ledger_manager, "get_transactions_by_user", side_effect=err):
        with spies(db) as (cm, rb):
            with pytest.raises(RuntimeError) as exc:
                svc.get_transactions_by_user(db, user_id=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert exc.value is err
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert q in db.new


# Manager signature the card binds the call to (TBU-04)
def _mgr_tbu_sig(session, user_id, workspace_id, start_date, end_date, skip, limit):
    pass


# [claude] LSV-TBU-04
def test_lsv_tbu_04__without_skip_and_limit_the_defaults_0_and_100_reach_the_manager(
    db, s
):
    """LSV-TBU-04 — without skip and limit the defaults 0 and 100 reach the manager.
    Rules: get_transactions_by_user R1 (defaults)"""
    r = {"machine": [], "project": [], "inventory": []}
    commit_point(db)
    with patch.object(
        svc.ledger_manager, "get_transactions_by_user", return_value=r
    ) as mgr:
        result = svc.get_transactions_by_user(db, user_id=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is r
    # Then 2
    assert mgr.call_count == 1
    # Then 3
    bound = (
        inspect.signature(_mgr_tbu_sig)
        .bind(*mgr.call_args.args, **mgr.call_args.kwargs)
        .arguments
    )
    assert bound["skip"] == 0
    # Then 4
    assert bound["limit"] == 100
    # Then 5
    assert bound["start_date"] is None
    assert bound["end_date"] is None
    assert bound["user_id"] == s.U2.id
    assert bound["workspace_id"] == s.W1.id
