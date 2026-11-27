"""Unit tests for app/dao/project_component_item.py.

Implements tests/unit/dao/project_component_item.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime

import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.project_component_item import project_component_item_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item import ProjectComponentItem
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton project_component_item_dao" (a module-level name, not a fixture)
dao = project_component_item_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T12"
T12 = datetime(2026, 3, 4, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Conventions list these rows in this order; each fixture depends on the one before,
# so the rows are flushed one at a time and ids rise in that order.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def pj1(db, w1, f1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project One", description="Main"))


@pytest.fixture
def pj2(db, w1, f1, pj1):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project Two", description="Main"))


@pytest.fixture
def pjd(db, w1, u1, f1, pj2):
    return _add(db, Project(workspace_id=w1.id, factory_id=f1.id, name="Project Three", description="Main", is_deleted=True, deleted_at=T12, deleted_by=u1.id))


@pytest.fixture
def c1(db, w1, pj1, pjd):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Roof"))


@pytest.fixture
def c2(db, w1, pj1, c1):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pj1.id, name="Wall"))


@pytest.fixture
def cd(db, w1, pjd, c2):
    return _add(db, ProjectComponent(workspace_id=w1.id, project_id=pjd.id, name="Floor"))


@pytest.fixture
def i1(db, w1, cd):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, pj1, pj2, pjd, c1, c2, cd, i1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "entry": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_entry(db, w1, c1, i1):
    """mk_entry(**columns) -> ProjectComponentItem. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "project_component_id": c1.id, "item_id": i1.id, "qty": 1}
        fields.update(columns)
        return _add(db, ProjectComponentItem(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, c1, i1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [ProjectComponentItem(workspace_id=w1.id, project_component_id=c1.id, item_id=i1.id, qty=1)
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of project_component_items rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProjectComponentItem.__table__)).scalar_one()


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from project_component_items; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "project_component_items" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DAOProjectComponentItem.get_by_component
# --------------------------------------------------------------------------- #


# [claude] PCI-G-01
def test_pci_g_01__returns_a_list_of_the_component_s_rows_one_item_twice_included(db, w1, c1, mk_entry):
    """PCI-G-01 — returns a list of the component's rows, one item twice included.
    Rules: `get_by_component` R1, Returns"""
    a = mk_entry()
    b = mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert set(ids(result)) == {a.id, b.id}
    # Then 4
    assert isinstance(result[0], ProjectComponentItem)


# [claude] PCI-G-02
def test_pci_g_02__a_row_of_another_component_of_the_same_workspace_is_not_returned_thoug(db, w1, c1, c2, mk_entry):
    """PCI-G-02 — a row of another component of the same workspace is not returned, though it sorts first.
    Rules: `get_by_component` R1"""
    mk_entry(project_component_id=c2.id)
    a = mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCI-G-03
def test_pci_g_03__the_right_component_under_another_workspace_returns_an_empty_list(db, w2, c1, mk_entry):
    """PCI-G-03 — the right component under another workspace returns an empty list.
    Rules: `get_by_component` R1"""
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PCI-G-04
def test_pci_g_04__an_unknown_workspace_returns_an_empty_list(db, c1, mk_entry):
    """PCI-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_component` R1"""
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PCI-G-05
def test_pci_g_05__a_w2_row_on_a_w1_component_is_returned_for_w2_only_the_row_s_workspace(db, w2, c1, mk_entry):
    """PCI-G-05 — a W2 row on a W1 component is returned for W2: only the row's workspace is compared.
    Rules: `get_by_component` R1"""
    a = mk_entry(workspace_id=w2.id)

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCI-G-06
def test_pci_g_06__a_w2_row_on_a_w1_component_is_not_returned_for_w1_though_it_sorts_firs(db, w1, w2, c1, mk_entry):
    """PCI-G-06 — a W2 row on a W1 component is not returned for W1, though it sorts first.
    Rules: `get_by_component` R1"""
    mk_entry(workspace_id=w2.id)
    a = mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCI-G-07
def test_pci_g_07__an_unknown_component_id_returns_an_empty_list(db, w1, mk_entry):
    """PCI-G-07 — an unknown component id returns an empty list.
    Rules: `get_by_component` R2"""
    mk_entry()

    result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCI-G-08
def test_pci_g_08__component_id_0_returns_an_empty_list(db, w1, mk_entry):
    """PCI-G-08 — component id 0 returns an empty list.
    Rules: `get_by_component` R2"""
    mk_entry()

    result = dao.get_by_component(db, project_component_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCI-G-09
def test_pci_g_09__a_component_with_no_rows_returns_an_empty_list(db, w1, c2, mk_entry):
    """PCI-G-09 — a component with no rows returns an empty list.
    Rules: `get_by_component` R2"""
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PCI-G-10
def test_pci_g_10__the_component_filter_comes_before_paging_a_hidden_row_does_not_use_up(db, w1, c1, c2, mk_entry):
    """PCI-G-10 — the component filter comes before paging: a hidden row does not use up the skip.
    Rules: `get_by_component` R1, R4"""
    mk_entry(project_component_id=c2.id)
    a = mk_entry()
    b = mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCI-G-11
def test_pci_g_11__the_workspace_filter_comes_before_paging_a_hidden_row_does_not_use_up(db, w1, w2, c1, mk_entry):
    """PCI-G-11 — the workspace filter comes before paging: a hidden row does not use up the skip.
    Rules: `get_by_component` R1, R4"""
    mk_entry(workspace_id=w2.id)
    a = mk_entry()
    b = mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=1, limit=10)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id}


# [claude] PCI-G-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1276: A component's items have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pci_g_12__rows_come_back_by_id_ascending_when_the_lowest_id_was_updated(db, w1, c1, mk_entry):
    """PCI-G-12 — rows come back by id ascending, when the lowest id was updated.
    Rules: `get_by_component` R3 [BUG-1276]"""
    a = mk_entry(qty=9)
    b = mk_entry(qty=5)
    c = mk_entry(qty=1)
    a.qty = 3
    db.flush()
    db.expire_all()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PCI-G-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1276: A component's items have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pci_g_13__rows_come_back_by_id_ascending_with_no_update(db, w1, c1, mk_entry):
    """PCI-G-13 — rows come back by id ascending, with no update.
    Rules: `get_by_component` R3 [BUG-1276]"""
    a = mk_entry(qty=9)
    b = mk_entry(qty=5)
    c = mk_entry(qty=1)
    db.expire_all()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PCI-G-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1276: A component's items have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_pci_g_14__the_order_comes_before_paging_and_the_hidden_row_does_not_use_up_the_s(db, w1, c1, c2, mk_entry):
    """PCI-G-14 — the order comes before paging, and the hidden row does not use up the skip.
    Rules: `get_by_component` R3 [BUG-1276]"""
    mk_entry(project_component_id=c2.id)
    a = mk_entry()
    b = mk_entry()
    mk_entry()
    a.qty = 3
    db.flush()
    db.expire_all()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] PCI-G-15
@pytest.mark.xfail(strict=True, reason="BUG-1276: A component's items have no sort order")
def test_pci_g_15__the_query_orders_by_id_ascending(db, w1, c1, mk_entry):
    """PCI-G-15 — the query orders by id ascending.
    Rules: `get_by_component` R3 [BUG-1276]"""
    a = mk_entry()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()


# [claude] PCI-G-16
def test_pci_g_16__with_the_default_limit_102_rows_give_100(db, w1, c1, mk_many):
    """PCI-G-16 — with the default limit 102 rows give 100.
    Rules: `get_by_component` R4"""
    mk_many(102)

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] PCI-G-17
def test_pci_g_17__limit_1000_gives_all_102_rows(db, w1, c1, mk_many):
    """PCI-G-17 — limit=1000 gives all 102 rows.
    Rules: `get_by_component` R4"""
    in_order = mk_many(102)

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 102
    # Then 2
    assert set(ids(result)) == set(in_order)


# [claude] PCI-G-18
def test_pci_g_18__limit_0_returns_an_empty_list(db, w1, c1, mk_entry):
    """PCI-G-18 — limit=0 returns an empty list.
    Rules: `get_by_component` R5"""
    mk_entry()
    mk_entry()
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PCI-G-19
def test_pci_g_19__limit_1_returns_one_row_the_other_side_of_limit_0(db, w1, c1, mk_entry):
    """PCI-G-19 — limit=1 returns one row: the other side of limit=0.
    Rules: `get_by_component` R5"""
    mk_entry()
    mk_entry()
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] PCI-G-20
def test_pci_g_20__skip_past_the_end_returns_an_empty_list(db, w1, c1, mk_entry):
    """PCI-G-20 — skip past the end returns an empty list.
    Rules: `get_by_component` R5"""
    mk_entry()
    mk_entry()
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] PCI-G-21
def test_pci_g_21__skip_2_of_three_rows_leaves_one_row_the_other_side_of_skip_past_the_en(db, w1, c1, mk_entry):
    """PCI-G-21 — skip=2 of three rows leaves one row: the other side of skip past the end.
    Rules: `get_by_component` R5"""
    mk_entry()
    mk_entry()
    mk_entry()

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert len(result) == 1


# [claude] PCI-G-22
def test_pci_g_22__a_negative_limit_is_refused_by_postgres(db, w1, c1, mk_entry):
    """PCI-G-22 — a negative limit is refused by Postgres.
    Rules: `get_by_component` R6, Errors row 1 (negative `limit`)"""
    mk_entry()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCI-G-23
def test_pci_g_23__a_negative_skip_is_refused_by_postgres(db, w1, c1, mk_entry):
    """PCI-G-23 — a negative skip is refused by Postgres.
    Rules: `get_by_component` R6, Errors row 2 (negative `skip`)"""
    mk_entry()
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] PCI-G-24
def test_pci_g_24__the_rows_of_a_component_of_a_soft_deleted_project_are_returned(db, w1, cd, mk_entry):
    """PCI-G-24 — the rows of a component of a soft-deleted project are returned.
    Rules: `get_by_component` R7"""
    a = mk_entry(project_component_id=cd.id)

    result = dao.get_by_component(db, project_component_id=cd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PCI-G-25
def test_pci_g_25__writes_nothing_a_pending_row_stays_pending_and_alone_in_the_session(db, w1, c1, i1, mk_entry):
    """PCI-G-25 — writes nothing: a pending row stays pending and alone in the session.
    Rules: `get_by_component` Side effects"""
    a = mk_entry()
    p = ProjectComponentItem(workspace_id=w1.id, project_component_id=c1.id, item_id=i1.id, qty=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []
    # Then 8
    assert len(selects) == 1
    # Then 9
    assert "FOR UPDATE" not in sql.upper()
    # Then 10
    assert "projects" not in sql
    # Then 11
    assert "project_components" not in sql
    # Then 12
    assert stored_count(db) == before
    # Then 13
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PCI-G-26
def test_pci_g_26__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, c1, c2, mk_entry):
    """PCI-G-26 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_component` Side effects"""
    a = mk_entry()
    b = mk_entry(project_component_id=c2.id)
    b.qty = 5

    result = dao.get_by_component(db, project_component_id=c1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.qty == 5
