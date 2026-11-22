"""Unit tests for app/services/machine_item_service.py.

Implements tests/unit/services/machine_item_service.cases.md (revision 1), one
test per case, in card order (there is no MIS-D-05). Real Postgres session
(`db` fixture): a `commit()` only releases a savepoint, so the service's commits
are safe and the fixture's outer rollback discards everything. Nothing is
patched except what Conventions name: the failing commit / failing refresh
wraps, the manager patch of MIS-D-03 and the create patch of MIS-C-14.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, MI ->
mi, `W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.exceptions import ValidationError as AppValidationError
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_item import MachineItem
from app.models.machine_item_ledger import MachineItemLedger
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_type import WorkOrderType
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate
from app.services.machine_item_service import machine_item_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton machine_item_service"
svc = machine_item_service

MISSING = 999999999

# Convention "manager patch" (MIS-D-03)
BLOCKERS = [{"type": "work_order", "id": 3}, {"type": "other_workspace"}]


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows, in Conventions order
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 created every Given row; U2 = the acting user
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, ws, u1, name, abbreviation, **but):
    return _add(db, Factory(workspace_id=ws.id, name=name, abbreviation=abbreviation, created_by=u1.id, **but))


@pytest.fixture
def f1(db, w1, u1, u2):
    return _factory(db, w1, u1, "Main Plant", "MP")


@pytest.fixture
def fd(db, w1, u1, f1):
    return _factory(db, w1, u1, "Closed Mill", "CM", is_deleted=True)


@pytest.fixture
def f9(db, w2, u1, fd):
    return _factory(db, w2, u1, "Far Depot", "FR")


def _item(db, ws, u1, name, name_normalized, **but):
    return _add(db, Item(
        workspace_id=ws.id, name=name, name_normalized=name_normalized, unit="pcs", created_by=u1.id, **but,
    ))


@pytest.fixture
def i1(db, w1, u1, f9):
    return _item(db, w1, u1, "Bolt M8", "bolt m8")


@pytest.fixture
def i2(db, w1, u1, i1):
    return _item(db, w1, u1, "Washer Ten", "washer ten")


@pytest.fixture
def ix(db, w1, u1, i2):
    return _item(db, w1, u1, "Old Rivet", "old rivet", is_active=False)


@pytest.fixture
def i9(db, w2, u1, ix):
    return _item(db, w2, u1, "Far Spring", "far spring")


def _machine(db, ws, factory, u1, name, **but):
    return _add(db, Machine(
        workspace_id=ws.id, factory_id=factory.id, name=name, is_running=False, created_by=u1.id, **but,
    ))


@pytest.fixture
def m1(db, w1, f1, u1, i9):
    return _machine(db, w1, f1, u1, "Lathe")


@pytest.fixture
def m2(db, w1, f1, u1, m1):
    return _machine(db, w1, f1, u1, "Press")


@pytest.fixture
def mx(db, w1, f1, u1, m2):
    return _machine(db, w1, f1, u1, "Old Saw", is_deleted=True, is_active=False)


@pytest.fixture
def mf(db, w1, fd, u1, mx):
    return _machine(db, w1, fd, u1, "Kiln")


@pytest.fixture
def m9(db, w2, f9, u1, mf):
    return _machine(db, w2, f9, u1, "Grinder")


@pytest.fixture
def wt1(db, w1, u1, m9):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair", created_by=u1.id))


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(wt1):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "stock of M, I"
@pytest.fixture
def mk_stock(db, w1):
    def _mk(machine, item, qty, **but):
        fields = {
            "workspace_id": w1.id, "machine_id": machine.id, "item_id": item.id,
            "qty": qty, "req_qty": None, "defective_qty": None,
        }
        fields.update(but)
        return _add(db, MachineItem(**fields))
    return _mk


# Convention "bulk(n)"
@pytest.fixture
def bulk(db, w1, u1, m1):
    def _bulk(n):
        new_items = [
            Item(
                workspace_id=w1.id, name=f"P{k:05d}", name_normalized=f"P{k:05d}", unit="pcs",
                is_active=True, created_by=u1.id,
            )
            for k in range(n)
        ]
        db.add_all(new_items)
        db.flush()
        db.add_all([
            MachineItem(workspace_id=w1.id, machine_id=m1.id, item_id=item.id, qty=1, req_qty=None, defective_qty=None)
            for item in new_items
        ])
        db.flush()
    return _bulk


# Convention "work order of M"
@pytest.fixture
def mk_order(db, w1, wt1, f1):
    def _mk(machine, given_name, status):
        return _add(db, WorkOrder(
            workspace_id=w1.id, work_order_number="WO-" + given_name, work_order_type_id=wt1.id, title="Service",
            factory_id=f1.id, machine_id=machine.id, is_deleted=False, status=status,
        ))
    return _mk


# Convention "source line of O"
@pytest.fixture
def mk_source_line(db, w1, i1, m1):
    def _mk(order):
        return _add(db, WorkOrderItem(
            workspace_id=w1.id, work_order_id=order.id, item_id=i1.id, quantity=2, uses_inventory=True,
            consumed_at=None, source_location_type="machine", source_location_id=m1.id, replaced_item_id=None,
            is_deleted=False,
        ))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(MachineItem).where(MachineItem.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = MachineItem.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


_TABLES = {
    "machine_items": MachineItem,
    "machine_item_ledger": MachineItemLedger,
    "machine_activity_events": MachineActivityEvent,
}


# Convention "count:" lines: rows of the named table (all workspaces), with the filter stated
def count_rows(db, table_name, **filters):
    model = _TABLES[table_name]
    query = select(func.count()).select_from(model)
    for column, value in filters.items():
        query = query.where(getattr(model, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "entries_of(M, I)"
def entries_of(db, machine, item):
    machine_id, item_id = _id_of(machine), _id_of(item)
    db.expire_all()
    query = select(MachineItemLedger).where(
        MachineItemLedger.machine_id == machine_id, MachineItemLedger.item_id == item_id,
    )
    return list(db.execute(query.order_by(MachineItemLedger.id)).scalars())


# Convention "events_of(M)"; event_type is the card's "with" filter
def events_of(db, machine, event_type=None):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    if event_type is not None:
        query = query.where(MachineActivityEvent.event_type == event_type)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# MachineItemService.get_machine_item
# --------------------------------------------------------------------------- #

# [claude] MIS-G-01
def test_mis_g_01__a_row_of_the_workspace_is_returned_as_the_manager_returns_it(db, w1, m1, i1, mk_stock):
    """MIS-G-01 — a row of the workspace is returned as the manager returns it.
    Rules: `get_machine_item` R1"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    result = svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineItem)
    # Then 2
    assert result.id == mi.id
    assert result.qty == 5
    assert result.item_id == i1.id


# [claude] MIS-G-02
def test_mis_g_02__another_workspaces_call_the_404_passes_unchanged(db, w2, m1, i1, mk_stock):
    """MIS-G-02 — another workspace's call: the 404 passes unchanged.
    Rules: `get_machine_item` R1, Errors"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"


# [claude] MIS-G-03
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mis_g_03__a_row_of_a_soft_deleted_machine_is_hidden_by_default(db, w1, mx, i1, mk_stock):
    """MIS-G-03 — a row of a soft-deleted machine is hidden by default.
    Rules: `get_machine_item` R2 [BUG-1077], Errors"""
    mi = mk_stock(mx, i1, qty=5)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"


# [claude] MIS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mis_g_04__include_deleted_true_returns_a_row_of_a_soft_deleted_machine(db, w1, mx, i1, mk_stock):
    """MIS-G-04 — include_deleted=True returns a row of a soft-deleted machine.
    Rules: `get_machine_item` R3 [BUG-1077]"""
    mi = mk_stock(mx, i1, qty=5)
    commit_point(db)
    result = svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == mi.id
    # Then 2
    assert result.qty == 5


# [claude] MIS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-1077: A hidden machine stock row still opens by id")
def test_mis_g_05__include_deleted_true_does_not_show_a_row_with_another_workspaces_item(db, w1, m1, i9, mk_stock):
    """MIS-G-05 — include_deleted=True does not show a row with another workspace's item.
    Rules: `get_machine_item` R3 [BUG-1077], Errors"""
    mi = mk_stock(m1, i9, qty=5)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"


# [claude] MIS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-1086: A stored stock row with another workspace's item shows that item's name and id")
def test_mis_g_06__pass_through_bug_1086_a_row_with_another_workspaces_item_is_not_found(db, w1, m1, i9, mk_stock):
    """MIS-G-06 — pass-through BUG-1086: a row with another workspace's item is not found.
    Rules: `get_machine_item` R1 [BUG-1086]"""
    mi = mk_stock(m1, i9, qty=5)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"


# [claude] MIS-G-07
def test_mis_g_07__the_read_neither_commits_nor_rolls_back(db, w1, m1, m2, i1, i2, mk_stock):
    """MIS-G-07 — the read neither commits nor rolls back.
    Rules: `get_machine_item` R4; TC6"""
    a = mk_stock(m1, i1, qty=5)
    b = mk_stock(m1, i2, qty=4)
    commit_point(db)
    mk_stock(m2, i1, qty=9)
    b.qty = 40
    result = svc.get_machine_item(db, machine_item_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m2.id) == 1
    # Then 5
    db.rollback()
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 6
    assert reread(db, b).qty == 4


# --------------------------------------------------------------------------- #
# MachineItemService.get_machine_items
# --------------------------------------------------------------------------- #

# [claude] MIS-L-01
def test_mis_l_01__machine_id_reaches_the_manager(db, w1, m1, m2, i1, i2, mk_stock):
    """MIS-L-01 — machine_id reaches the manager.
    Rules: `get_machine_items` R1"""
    a = mk_stock(m1, i1, qty=5)
    mk_stock(m2, i2, qty=5)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] MIS-L-02
def test_mis_l_02__with_the_defaults_101_rows_give_100(db, w1, bulk):
    """MIS-L-02 — with the defaults 101 rows give 100.
    Rules: `get_machine_items` R1"""
    bulk(101)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MIS-L-03
def test_mis_l_03__limit_1000_reaches_the_manager_and_gives_all_101(db, w1, bulk):
    """MIS-L-03 — limit=1000 reaches the manager and gives all 101.
    Rules: `get_machine_items` R1"""
    bulk(101)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101


# [claude] MIS-L-04
def test_mis_l_04__skip_reaches_the_manager(db, w1, bulk):
    """MIS-L-04 — skip reaches the manager.
    Rules: `get_machine_items` R1"""
    bulk(101)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id, skip=100)

    # Then 1
    assert len(result) == 1


# [claude] MIS-L-05
def test_mis_l_05__the_list_neither_commits_nor_rolls_back(db, w1, m1, m2, i1, i2, mk_stock):
    """MIS-L-05 — the list neither commits nor rolls back.
    Rules: `get_machine_items` R2; TC6"""
    a = mk_stock(m1, i1, qty=5)
    b = mk_stock(m1, i2, qty=4)
    commit_point(db)
    mk_stock(m2, i1, qty=9)
    b.qty = 40
    result = svc.get_machine_items(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 5
    assert reread(db, b).qty == 4


# [claude] MIS-L-06
@pytest.mark.xfail(strict=True, reason="BUG-1074: `machine_id=0` lists the whole workspace's machine stock")
def test_mis_l_06__pass_through_bug_1074_machine_id_0_filters_like_any_integer(db, w1, m1, i1, mk_stock):
    """MIS-L-06 — pass-through BUG-1074: machine_id 0 filters like any integer.
    Rules: `get_machine_items` R1 [BUG-1074]"""
    mk_stock(m1, i1, qty=5)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id, machine_id=0)

    # Then 1
    assert result == []


# [claude] MIS-L-07
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1070: Workspace-wide machine stock list shows rows of deleted machines, deleted factories "
    "and removed items",
)
def test_mis_l_07__pass_through_bug_1070_a_row_of_a_soft_deleted_machine_is_left_out(
    db, w1, mx, m2, i1, i2, mk_stock,
):
    """MIS-L-07 — pass-through BUG-1070: a row of a soft-deleted machine is left out.
    Rules: `get_machine_items` R1 [BUG-1070]"""
    mk_stock(mx, i1, qty=5)
    b = mk_stock(m2, i2, qty=5)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MIS-L-08
@pytest.mark.xfail(strict=False, reason="BUG-1071: Workspace-wide machine stock list has no display order")
def test_mis_l_08__pass_through_bug_1071_rows_come_in_item_name_order_case_insensitive(
    db, w1, u1, m1, m2, mk_stock,
):
    """MIS-L-08 — pass-through BUG-1071: rows come in item-name order, case-insensitive.
    Rules: `get_machine_items` R1 [BUG-1071]"""
    iz = _item(db, w1, u1, "Zulu", "zulu")
    ia = _item(db, w1, u1, "apple", "apple")
    ib = _item(db, w1, u1, "Banana", "banana")
    mk_stock(m1, iz, qty=1)
    mk_stock(m1, ia, qty=1)
    mk_stock(m2, ib, qty=1)
    commit_point(db)
    result = svc.get_machine_items(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert [r.item_id for r in result] == [ia.id, ib.id, iz.id]


# --------------------------------------------------------------------------- #
# MachineItemService.create_machine_item
# --------------------------------------------------------------------------- #

# [claude] MIS-C-01
def test_mis_c_01__a_new_stock_row_its_ledger_entry_and_activity_row_are_committed_the_row_is_returned_re_read(
    db, w1, u2, m1, i1,
):
    """MIS-C-01 — a new stock row, its ledger entry and activity row are committed; the row is returned re-read.
    Rules: `create_machine_item` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_machine_item(
        db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5, req_qty=7),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert "qty" not in unloaded(result)
    assert "req_qty" not in unloaded(result)
    assert "machine_id" not in unloaded(result)
    assert "item_id" not in unloaded(result)
    # Then 2
    assert isinstance(result, MachineItem)
    # Then 3
    assert result.qty == 5
    assert result.req_qty == 7
    assert result.machine_id == m1.id
    # Then 4
    result_id = result.id
    db.rollback()
    row = db.execute(select(MachineItem).where(MachineItem.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.qty == 5
    assert row.req_qty == 7
    assert row.workspace_id == w1.id
    # Then 5
    entries = entries_of(db, m1, i1)
    assert len(entries) == 1
    # Then 6
    assert entries[0].transaction_type == "manual_add"
    assert entries[0].quantity == 5
    assert entries[0].performed_by == u2.id
    # Then 7
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 8
    assert rows[0].event_type == "item_added"
    assert rows[0].performed_by == u2.id


# [claude] MIS-C-02
def test_mis_c_02__another_workspaces_machine_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, m1, m2, m9, i1, i2, mk_stock,
):
    """MIS-C-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back.
    Rules: `create_machine_item` R2, Errors; TC3"""
    a = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_stock(m2, i2, qty=3)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=m9.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine not found in this workspace"
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] MIS-C-03
def test_mis_c_03__a_soft_deleted_machine_the_400_passes_unchanged_nothing_saved(db, w1, u2, mx, i1):
    """MIS-C-03 — a soft-deleted machine: the 400 passes unchanged, nothing saved.
    Rules: `create_machine_item` R2, Errors"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=mx.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MIS-C-04
def test_mis_c_04__the_item_already_on_the_machine_the_409_passes_unchanged_nothing_saved(
    db, w1, u2, m1, i1, mk_stock,
):
    """MIS-C-04 — the item already on the machine: the 409 passes unchanged, nothing saved.
    Rules: `create_machine_item` R2, Errors"""
    a = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=2), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "This item already exists on this machine. Update the existing record instead."
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MIS-C-05
def test_mis_c_05__a_dataerror_at_the_flush_passes_unchanged_nothing_saved_the_session_is_usable(
    db, w1, u2, m1, i1,
):
    """MIS-C-05 — a DataError at the flush passes unchanged; nothing saved; the session is usable.
    Rules: `create_machine_item` R3, Errors; TC3"""
    data = MachineItemCreate.model_construct(
        machine_id=m1.id, item_id=i1.id, qty=2**31, req_qty=None, defective_qty=None,
    )
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(DataError):
        svc.create_machine_item(db, item_in=data, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert written(db) == before
    # Then 3
    assert usable(db)


# [claude] MIS-C-06
def test_mis_c_06__a_failing_commit_is_rolled_back_and_re_raised_no_row_entry_or_activity_is_saved(
    db, w1, u2, m1, i1,
):
    """MIS-C-06 — a failing commit is rolled back and re-raised: no row, entry or activity is saved.
    Rules: `create_machine_item` R4; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_machine_item(
                db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5),
                workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_rows(db, "machine_items") == 0
    # Then 4
    assert len(entries_of(db, m1, i1)) == 0
    # Then 5
    assert len(events_of(db, m1)) == 0


# [claude] MIS-C-07
def test_mis_c_07__a_failing_re_read_after_the_commit_leaves_the_row_entry_and_activity_saved(
    db, w1, u2, m1, i1,
):
    """MIS-C-07 — a failing re-read after the commit leaves the row, entry and activity saved.
    Rules: `create_machine_item` R4; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_machine_item(
                db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5),
                workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_rows(db, "machine_items", machine_id=m1.id) == 1
    # Then 3
    assert len(entries_of(db, m1, i1)) == 1
    # Then 4
    assert len(events_of(db, m1)) == 1


# [claude] MIS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-1076: Stock can be added to a machine of a soft-deleted factory")
def test_mis_c_08__pass_through_bug_1076_a_live_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, mf, i1):
    """MIS-C-08 — pass-through BUG-1076: a live machine in a soft-deleted factory is refused.
    Rules: `create_machine_item` R2 [BUG-1076]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=mf.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add items to a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MIS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-1010: Machine stock accepts another workspace's item and shows its name")
def test_mis_c_09__pass_through_bug_1010_an_unknown_item_gets_the_404(db, w1, u2, m1):
    """MIS-C-09 — pass-through BUG-1010: an unknown item gets the 404.
    Rules: `create_machine_item` R2 [BUG-1010]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=m1.id, item_id=MISSING, qty=5), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MIS-C-10
@pytest.mark.xfail(strict=True, reason="BUG-1085: A removed catalog item can be added to a machine")
def test_mis_c_10__pass_through_bug_1085_a_removed_item_is_refused(db, w1, u2, m1, ix):
    """MIS-C-10 — pass-through BUG-1085: a removed item is refused.
    Rules: `create_machine_item` R2 [BUG-1085]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=m1.id, item_id=ix.id, qty=5), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot add a removed item to a machine"
    # Then 4
    assert written(db) == before


# [claude] MIS-C-11
@pytest.mark.xfail(strict=True, reason="BUG-1079: Negative machine stock quantities are accepted")
def test_mis_c_11__pass_through_bug_1079_a_negative_qty_is_refused_by_the_schema(db, m1, i1):
    """MIS-C-11 — pass-through BUG-1079: a negative qty is refused by the schema.
    Rules: `create_machine_item` R1 [BUG-1079]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=-1)
    # Then 2
    assert written(db) == before


# [claude] MIS-C-12
@pytest.mark.xfail(strict=True, reason="BUG-1078: A machine stock quantity beyond 32 bits crashes")
def test_mis_c_12__pass_through_bug_1078_a_qty_of_2147483648_is_refused_by_the_schema(db, m1, i1):
    """MIS-C-12 — pass-through BUG-1078: a qty of 2147483648 is refused by the schema.
    Rules: `create_machine_item` R1 [BUG-1078]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=2147483648)
    # Then 2
    assert written(db) == before


# [claude] MIS-C-13
def test_mis_c_13__the_schema_still_accepts_qty_2147483647(db, m1, i1):
    """MIS-C-13 — the schema still accepts qty 2147483647.
    Rules: `create_machine_item` R1"""
    commit_point(db)
    data = MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=2147483647)

    # Then 1
    assert data.qty == 2147483647


# [claude] MIS-C-14
def test_mis_c_14__a_valueerror_from_create_is_not_translated_only_delete_translates(db, w1, u2, m1, i1):
    """MIS-C-14 — a ValueError from create is not translated: only delete translates.
    Rules: `create_machine_item` R3; `delete_machine_item` R2 (scope, Q1)"""
    commit_point(db)
    before = written(db)
    with pytest.raises(ValueError) as exc:
        with patch.object(svc.machine_item_manager, "create_machine_item", side_effect=ValueError("x", [])):
            svc.create_machine_item(
                db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5),
                workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert type(exc.value) is ValueError
    # Then 2
    assert exc.value.args == ("x", [])
    # Then 3
    assert written(db) == before


# [claude] MIS-C-15
def test_mis_c_15__an_unknown_user_the_integrityerror_passes_unchanged_nothing_saved_the_session_is_usable(
    db, w1, m1, m2, i1, i2, mk_stock,
):
    """MIS-C-15 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable.
    Rules: `create_machine_item` R3, Errors; TC3"""
    a = mk_stock(m1, i2, qty=4)
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_stock(m2, i2, qty=3)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_machine_item(
            db, item_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id, qty=5), workspace_id=w1.id, user_id=MISSING,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, "machine_items", item_id=i1.id) == 0
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# --------------------------------------------------------------------------- #
# MachineItemService.update_machine_item
# --------------------------------------------------------------------------- #

# [claude] MIS-U-01
def test_mis_u_01__a_qty_change_with_its_entry_and_activity_is_committed_the_row_is_returned_re_read(
    db, w1, u2, m1, i1, mk_stock,
):
    """MIS-U-01 — a qty change with its entry and activity is committed; the row is returned re-read.
    Rules: `update_machine_item` R1, Returns; TC1, TC2"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    result = svc.update_machine_item(
        db, machine_item_id=mi.id, item_in=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert "qty" not in unloaded(result)
    assert "req_qty" not in unloaded(result)
    # Then 2
    assert result.id == mi.id
    # Then 3
    assert result.qty == 12
    # Then 4
    db.rollback()
    assert reread(db, mi).qty == 12
    # Then 5
    assert len(entries_of(db, m1, i1)) == 1
    # Then 6
    assert len(events_of(db, m1, event_type="item_updated")) == 1
    # Then 7
    assert len(events_of(db, m1, event_type="inventory_adjusted")) == 1


# [claude] MIS-U-02
def test_mis_u_02__another_workspaces_call_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w2, u2, m1, m2, i1, i2, mk_stock,
):
    """MIS-U-02 — another workspace's call: the 404 passes unchanged and the session is rolled back.
    Rules: `update_machine_item` R2, Errors; TC3"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    mk_stock(m2, i2, qty=3)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine_item(
            db, machine_item_id=mi.id, item_in=MachineItemUpdate(qty=12), workspace_id=w2.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 5
    assert snap(db, mi) == before_mi
    # Then 6
    assert written(db) == before


# [claude] MIS-U-03
@pytest.mark.xfail(strict=True, reason="BUG-1083: Stock on a deleted machine can still be edited")
def test_mis_u_03__pass_through_bug_1083_a_row_of_a_soft_deleted_machine_is_refused(db, w1, u2, mx, i1, mk_stock):
    """MIS-U-03 — pass-through BUG-1083: a row of a soft-deleted machine is refused.
    Rules: `update_machine_item` R2 [BUG-1083]"""
    mi = mk_stock(mx, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_machine_item(
            db, machine_item_id=mi.id, item_in=MachineItemUpdate(qty=12), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update items of a deleted machine"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIS-U-04
@pytest.mark.xfail(strict=True, reason="BUG-1075: A machine's target and defect count cannot be cleared")
def test_mis_u_04__pass_through_bug_1075_an_explicit_null_clears_req_qty(db, w1, u2, m1, i1, mk_stock):
    """MIS-U-04 — pass-through BUG-1075: an explicit null clears req_qty.
    Rules: `update_machine_item` R1 [BUG-1075]"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7)
    commit_point(db)
    result = svc.update_machine_item(
        db, machine_item_id=mi.id, item_in=MachineItemUpdate(req_qty=None), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == mi.id
    # Then 2
    db.rollback()
    assert reread(db, mi).req_qty is None


# [claude] MIS-U-05
def test_mis_u_05__an_update_of_req_qty_alone_is_committed_without_a_ledger_entry(db, w1, u2, m1, i1, mk_stock):
    """MIS-U-05 — an update of req_qty alone is committed without a ledger entry.
    Rules: `update_machine_item` R1"""
    mi = mk_stock(m1, i1, qty=5, req_qty=7)
    commit_point(db)
    result = svc.update_machine_item(
        db, machine_item_id=mi.id, item_in=MachineItemUpdate(req_qty=9), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.req_qty == 9
    # Then 2
    db.rollback()
    row = reread(db, mi)
    assert row.req_qty == 9
    assert row.qty == 5
    # Then 3
    assert len(entries_of(db, m1, i1)) == 0
    # Then 4
    assert len(events_of(db, m1)) == 1


# --------------------------------------------------------------------------- #
# MachineItemService.delete_machine_item
# --------------------------------------------------------------------------- #

# [claude] MIS-D-01
def test_mis_d_01__a_delete_with_its_final_entry_and_activity_is_committed_none_is_returned(
    db, w1, u2, m1, i1, mk_stock,
):
    """MIS-D-01 — a delete with its final entry and activity is committed; None is returned.
    Rules: `delete_machine_item` R1, Returns; TC1"""
    mi = mk_stock(m1, i1, qty=5)
    mi_id = mi.id
    commit_point(db)
    result = svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    entries = entries_of(db, m1, i1)
    assert len(entries) == 1
    # Then 4
    assert entries[0].transaction_type == "inventory_adjustment"
    assert entries[0].qty_before == 5
    assert entries[0].qty_after == 0
    # Then 5
    assert len(events_of(db, m1, event_type="item_removed")) == 1


# [claude] MIS-D-02
def test_mis_d_02__another_workspaces_call_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w2, u2, m1, m2, i1, i2, mk_stock,
):
    """MIS-D-02 — another workspace's call: the 404 passes unchanged and the session is rolled back.
    Rules: `delete_machine_item` R4, Errors row 2; TC3"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    mk_stock(m2, i2, qty=3)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w2.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Machine item not found"
    # Then 4
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 5
    assert snap(db, mi) == before_mi
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] MIS-D-03
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mis_d_03__the_managers_in_use_valueerror_becomes_the_400_validationerror_with_the_blockers_as_given_after_a_rollback(
    db, w1, u2, m1, m2, i1, i2, mk_stock,
):
    """MIS-D-03 — the manager's in-use ValueError becomes the 400 ValidationError with the blockers as given, after a rollback.
    Rules: `delete_machine_item` R2 [BUG-1081], Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    mk_stock(m2, i2, qty=3)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(
            svc.machine_item_manager, "delete_machine_item",
            side_effect=ValueError("Machine item has open orders", BLOCKERS),
        ):
            svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine item has open orders"
    # Then 4
    assert exc.value.errors == [{"type": "work_order", "id": 3}, {"type": "other_workspace"}]
    # Then 5
    assert count_rows(db, "machine_items", machine_id=m2.id) == 0
    # Then 6
    assert snap(db, mi) == before_mi


# [claude] MIS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-1081: Machine stock row is removed while open orders still need it")
def test_mis_d_04__end_to_end_an_open_work_order_blocks_the_delete_with_a_400_that_lists_it(
    db, w1, u2, m1, i1, mk_stock, mk_order, mk_source_line,
):
    """MIS-D-04 — end to end: an open work order blocks the delete with a 400 that lists it.
    Rules: `delete_machine_item` R2 [BUG-1081], Errors row 1"""
    mi = mk_stock(m1, i1, qty=5)
    o1 = mk_order(m1, "A", status="DRAFT")
    mk_source_line(o1)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Machine item has open orders"
    # Then 4
    assert exc.value.errors == [{"type": "work_order", "id": o1.id}]
    # Then 5
    assert snap(db, mi) == before_mi
    # Then 6
    assert written(db) == before


# [claude] MIS-D-06
@pytest.mark.xfail(strict=True, reason="BUG-1084: Stock on a deleted machine can still be removed")
def test_mis_d_06__pass_through_bug_1084_a_row_of_a_soft_deleted_machine_is_refused(db, w1, u2, mx, i1, mk_stock):
    """MIS-D-06 — pass-through BUG-1084: a row of a soft-deleted machine is refused.
    Rules: `delete_machine_item` R4 [BUG-1084], Errors row 2"""
    mi = mk_stock(mx, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot remove items from a deleted machine"
    # Then 4
    assert snap(db, mi) == before_mi
    # Then 5
    assert written(db) == before


# [claude] MIS-D-07
@pytest.mark.xfail(strict=True, reason="BUG-1080: Removing a negative stock row leaves the ledger negative")
def test_mis_d_07__pass_through_bug_1080_a_row_below_0_books_its_final_adjustment_to_0(
    db, w1, u2, m1, i1, mk_stock,
):
    """MIS-D-07 — pass-through BUG-1080: a row below 0 books its final adjustment to 0.
    Rules: `delete_machine_item` R1 [BUG-1080]"""
    mi = mk_stock(m1, i1, qty=-3)
    mi_id = mi.id
    commit_point(db)
    result = svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert count_rows(db, "machine_items", id=mi_id) == 0
    # Then 3
    entries = entries_of(db, m1, i1)
    assert len(entries) == 1
    # Then 4
    assert entries[0].qty_before == -3
    assert entries[0].qty_after == 0


# [claude] MIS-D-08
def test_mis_d_08__a_failing_commit_on_delete_is_rolled_back_the_row_stays(db, w1, u2, m1, i1, mk_stock):
    """MIS-D-08 — a failing commit on delete is rolled back: the row stays.
    Rules: `delete_machine_item` R5; TC4"""
    mi = mk_stock(m1, i1, qty=5)
    commit_point(db)
    before_mi = snap_before(db, mi)
    before = written(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_machine_item(db, machine_item_id=mi.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, mi) == before_mi
    # Then 4
    assert written(db) == before
