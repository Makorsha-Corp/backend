"""Unit tests for app/dao/work_order_item.py.

Implements tests/unit/dao/work_order_item.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (naive datetimes)
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect

from app.dao.work_order_item import work_order_item_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.work_order_type import WorkOrderType
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton work_order_item_dao" (a module-level name, not a fixture)
dao = work_order_item_dao

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
def i1(db, w1, f1):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


@pytest.fixture
def i2(db, w1, i1):
    return _add(db, Item(workspace_id=w1.id, name="Nut", name_normalized="nut", unit="pcs"))


@pytest.fixture
def wt1(db, w1, i2):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))


@pytest.fixture
def wo1(db, w1, u1, f1, wt1):
    return _add(db, WorkOrder(workspace_id=w1.id, work_order_number="WO-T-001", title="Order One", factory_id=f1.id, work_order_type_id=wt1.id, created_by=u1.id))


@pytest.fixture
def wo2(db, w1, u1, f1, wt1, wo1):
    return _add(db, WorkOrder(workspace_id=w1.id, work_order_number="WO-T-002", title="Order One", factory_id=f1.id, work_order_type_id=wt1.id, created_by=u1.id))


@pytest.fixture
def wod(db, w1, u1, f1, wt1, wo2):
    return _add(db, WorkOrder(workspace_id=w1.id, work_order_number="WO-T-003", title="Order One", factory_id=f1.id, work_order_type_id=wt1.id, created_by=u1.id, is_deleted=True, is_active=False, deleted_at=T12, deleted_by=u1.id))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, i1, i2, wt1, wo1, wo2, wod):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_line(db, w1, i1, wo1):
    """mk_line(**columns) -> WorkOrderItem. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "work_order_id": wo1.id, "item_id": i1.id, "quantity": Decimal("1.00")}
        fields.update(columns)
        return _add(db, WorkOrderItem(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, i1, wo1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [WorkOrderItem(workspace_id=w1.id, work_order_id=wo1.id, item_id=i1.id, quantity=Decimal("1.00"))
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


# Convention "nothing written": the number of work_order_items rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(WorkOrderItem.__table__)).scalar_one()


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
        """The one SELECT from work_order_items; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "work_order_items" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# WorkOrderItemDAO.get_by_work_order
# --------------------------------------------------------------------------- #


# [claude] WOI-G-01
def test_woi_g_01__returns_a_list_of_the_order_s_lines(db, w1, wo1, mk_line):
    """WOI-G-01 — returns a list of the order's lines.
    Rules: `get_by_work_order` R1, Returns"""
    a = mk_line()
    b = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert set(ids(result)) == {a.id, b.id}
    # Then 4
    assert isinstance(result[0], WorkOrderItem)


# [claude] WOI-G-02
def test_woi_g_02__a_line_of_another_order_of_the_same_workspace_is_not_returned_though_i(db, w1, wo1, wo2, mk_line):
    """WOI-G-02 — a line of another order of the same workspace is not returned, though it sorts first.
    Rules: `get_by_work_order` R1"""
    mk_line(work_order_id=wo2.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-03
def test_woi_g_03__the_right_order_under_another_workspace_returns_an_empty_list(db, w2, wo1, mk_line):
    """WOI-G-03 — the right order under another workspace returns an empty list.
    Rules: `get_by_work_order` R1"""
    mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] WOI-G-04
def test_woi_g_04__an_unknown_workspace_returns_an_empty_list(db, wo1, mk_line):
    """WOI-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_work_order` R1"""
    mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] WOI-G-05
def test_woi_g_05__a_w2_row_on_a_w1_order_is_returned_for_w2_only_the_row_s_workspace_is(db, w2, wo1, mk_line):
    """WOI-G-05 — a W2 row on a W1 order is returned for W2: only the row's workspace is compared.
    Rules: `get_by_work_order` R1"""
    a = mk_line(workspace_id=w2.id)

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-06
def test_woi_g_06__a_w2_row_on_a_w1_order_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, wo1, mk_line):
    """WOI-G-06 — a W2 row on a W1 order is not returned for W1, though it sorts first.
    Rules: `get_by_work_order` R1"""
    mk_line(workspace_id=w2.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-07
def test_woi_g_07__an_unknown_order_id_returns_an_empty_list(db, w1, mk_line):
    """WOI-G-07 — an unknown order id returns an empty list.
    Rules: `get_by_work_order` R2"""
    mk_line()

    result = dao.get_by_work_order(db, work_order_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] WOI-G-08
def test_woi_g_08__order_id_0_returns_an_empty_list(db, w1, mk_line):
    """WOI-G-08 — order id 0 returns an empty list.
    Rules: `get_by_work_order` R2"""
    mk_line()

    result = dao.get_by_work_order(db, work_order_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] WOI-G-09
def test_woi_g_09__an_order_with_no_rows_returns_an_empty_list(db, w1, wo2, mk_line):
    """WOI-G-09 — an order with no rows returns an empty list.
    Rules: `get_by_work_order` R2"""
    mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] WOI-G-10
def test_woi_g_10__left_out_include_deleted_hides_a_soft_deleted_line_that_sorts_first(db, w1, u1, wo1, mk_line):
    """WOI-G-10 — left out, include_deleted hides a soft-deleted line that sorts first.
    Rules: `get_by_work_order` R3"""
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-11
def test_woi_g_11__include_deleted_false_hides_a_soft_deleted_line_that_sorts_first(db, w1, u1, wo1, mk_line):
    """WOI-G-11 — include_deleted=False hides a soft-deleted line that sorts first.
    Rules: `get_by_work_order` R3"""
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id, include_deleted=False)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-12
def test_woi_g_12__include_deleted_none_acts_as_false(db, w1, u1, wo1, mk_line):
    """WOI-G-12 — include_deleted=None acts as False.
    Rules: `get_by_work_order` R3"""
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id, include_deleted=None)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-13
def test_woi_g_13__an_order_with_only_soft_deleted_lines_returns_an_empty_list(db, w1, u1, wo1, mk_line):
    """WOI-G-13 — an order with only soft-deleted lines returns an empty list.
    Rules: `get_by_work_order` R3"""
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] WOI-G-14
def test_woi_g_14__include_deleted_true_returns_soft_deleted_lines_with_the_live_ones(db, w1, u1, wo1, mk_line):
    """WOI-G-14 — include_deleted=True returns soft-deleted lines with the live ones.
    Rules: `get_by_work_order` R4"""
    b = mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)
    a = mk_line()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert set(ids(result)) == {a.id, b.id}


# [claude] WOI-G-15
def test_woi_g_15__include_deleted_true_still_keeps_to_that_order_and_workspace(db, w1, w2, u1, wo1, wo2, mk_line):
    """WOI-G-15 — include_deleted=True still keeps to that order and workspace.
    Rules: `get_by_work_order` R4"""
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id, work_order_id=wo2.id)
    mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id, workspace_id=w2.id)
    a = mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-16
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1272: A work order's lines have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_woi_g_16__rows_come_back_by_id_ascending_when_the_lowest_id_was_updated(db, w1, i2, wo1, mk_line):
    """WOI-G-16 — rows come back by id ascending, when the lowest id was updated.
    Rules: `get_by_work_order` R5 [BUG-1272]"""
    a = mk_line(quantity=Decimal("9.00"), item_id=i2.id)
    b = mk_line(quantity=Decimal("1.00"))
    a.quantity = Decimal("3.00")
    db.flush()
    db.expire_all()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] WOI-G-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1272: A work order's lines have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_woi_g_17__rows_come_back_by_id_ascending_with_no_update(db, w1, i2, wo1, mk_line):
    """WOI-G-17 — rows come back by id ascending, with no update.
    Rules: `get_by_work_order` R5 [BUG-1272]"""
    a = mk_line(quantity=Decimal("9.00"), item_id=i2.id)
    b = mk_line(quantity=Decimal("1.00"))
    db.expire_all()

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] WOI-G-18
@pytest.mark.xfail(strict=True, reason="BUG-1272: A work order's lines have no sort order")
def test_woi_g_18__the_query_orders_by_id_ascending(db, w1, wo1, mk_line):
    """WOI-G-18 — the query orders by id ascending.
    Rules: `get_by_work_order` R5 [BUG-1272]"""
    a = mk_line()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)
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


# [claude] WOI-G-19
def test_woi_g_19__there_is_no_cap_101_lines_give_101_rows(db, w1, wo1, mk_many):
    """WOI-G-19 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_work_order` R6"""
    in_order = mk_many(101)

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == set(in_order)


# [claude] WOI-G-20
def test_woi_g_20__the_live_lines_of_a_soft_deleted_order_are_returned(db, w1, wod, mk_line):
    """WOI-G-20 — the live lines of a soft-deleted order are returned.
    Rules: `get_by_work_order` R7"""
    a = mk_line(work_order_id=wod.id)

    result = dao.get_by_work_order(db, work_order_id=wod.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOI-G-21
def test_woi_g_21__a_positional_work_order_id_raises_typeerror(db, w1, wo1):
    """WOI-G-21 — a positional `work_order_id` raises TypeError.
    Rules: `get_by_work_order` R8"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_work_order(db, wo1.id, workspace_id=w1.id)
    # Then 2
    assert stored_count(db) == before


# [claude] WOI-G-22
def test_woi_g_22__writes_nothing_a_pending_row_stays_pending_and_alone_in_the_session(db, w1, i1, wo1, mk_line):
    """WOI-G-22 — writes nothing: a pending row stays pending and alone in the session.
    Rules: `get_by_work_order` Side effects"""
    a = mk_line()
    p = WorkOrderItem(workspace_id=w1.id, work_order_id=wo1.id, item_id=i1.id, quantity=Decimal("1.00"))
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)
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
    assert "work_orders" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOI-G-23
def test_woi_g_23__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, wo1, wo2, mk_line):
    """WOI-G-23 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_work_order` Side effects"""
    a = mk_line()
    b = mk_line(work_order_id=wo2.id)
    b.quantity = Decimal("5.00")

    result = dao.get_by_work_order(db, work_order_id=wo1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.quantity == Decimal("5.00")


# --------------------------------------------------------------------------- #
# WorkOrderItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] WOI-I-01
def test_woi_i_01__returns_the_line_of_that_id_not_the_first_line(db, w1, mk_line):
    """WOI-I-01 — returns the line of that id, not the first line.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_line()
    b = mk_line()

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, WorkOrderItem)


# [claude] WOI-I-02
def test_woi_i_02__another_workspace_returns_none(db, w2, mk_line):
    """WOI-I-02 — another workspace returns None.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_line()

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] WOI-I-03
def test_woi_i_03__an_unknown_id_returns_none_and_nothing_is_created(db, w1, mk_line):
    """WOI-I-03 — an unknown id returns None and nothing is created.
    Rules: `get_by_id_and_workspace` R1"""
    mk_line()
    before = stored_count(db)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] WOI-I-04
def test_woi_i_04__a_soft_deleted_line_is_returned(db, w1, u1, mk_line):
    """WOI-I-04 — a soft-deleted line is returned.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_line(is_deleted=True, deleted_at=T12, deleted_by=u1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] WOI-I-05
def test_woi_i_05__writes_nothing_a_read_that_finds_its_line_leaves_the_session_as_it_was(db, w1, i1, wo1, mk_line):
    """WOI-I-05 — writes nothing: a read that finds its line leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line()
    p = WorkOrderItem(workspace_id=w1.id, work_order_id=wo1.id, item_id=i1.id, quantity=Decimal("1.00"))
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
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
    assert stored_count(db) == before
    # Then 11
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOI-I-06
def test_woi_i_06__a_w2_line_at_the_earlier_id_is_not_returned_for_w1(db, w1, w2, mk_line):
    """WOI-I-06 — a W2 line at the earlier id is not returned for W1.
    Rules: `get_by_id_and_workspace` R1"""
    z = mk_line(workspace_id=w2.id)
    mk_line()

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] WOI-I-07
def test_woi_i_07__a_line_of_a_soft_deleted_order_is_returned_and_the_order_is_not_joined(db, w1, wod, mk_line):
    """WOI-I-07 — a line of a soft-deleted order is returned, and the order is not joined.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_line(work_order_id=wod.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert "work_orders" not in sql


# [claude] WOI-I-08
def test_woi_i_08__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, mk_line):
    """WOI-I-08 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line()
    b = mk_line()
    b.quantity = Decimal("5.00")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.quantity == Decimal("5.00")
