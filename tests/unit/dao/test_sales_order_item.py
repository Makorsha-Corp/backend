"""Unit tests for app/dao/sales_order_item.py.

Implements tests/unit/dao/sales_order_item.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect

from app.dao.sales_order_item import sales_order_item_dao
from app.models.account import Account
from app.models.factory import Factory
from app.models.item import Item
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.status import Status
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton sales_order_item_dao" (a module-level name, not a fixture)
dao = sales_order_item_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


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
def ac1(db, w1, u1):
    return _add(db, Account(workspace_id=w1.id, name="Acme"))


@pytest.fixture
def f1(db, w1, ac1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def s1(db, w1, f1):
    return _add(db, Status(workspace_id=w1.id, name="Draft", comment="Stage"))


@pytest.fixture
def so1(db, w1, u1, ac1, f1, s1):
    return _add(db, SalesOrder(workspace_id=w1.id, sales_order_number="SO-T-001", account_id=ac1.id, factory_id=f1.id, order_date=date(2026, 3, 1), total_amount=0, current_status_id=s1.id, created_by=u1.id))


@pytest.fixture
def so2(db, w1, u1, ac1, f1, s1, so1):
    return _add(db, SalesOrder(workspace_id=w1.id, sales_order_number="SO-T-002", account_id=ac1.id, factory_id=f1.id, order_date=date(2026, 3, 1), total_amount=0, current_status_id=s1.id, created_by=u1.id))


@pytest.fixture
def ir(db, w1, so2):
    return _add(db, Item(workspace_id=w1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, ac1, f1, s1, so1, so2, ir):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_line(db, w1, so1):
    """mk_line(**columns) -> SalesOrderItem. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "sales_order_id": so1.id, "description": "Line", "quantity_ordered": Decimal("1.00"), "unit_price": Decimal("2.00"), "line_total": Decimal("2.00")}
        fields.update(columns)
        return _add(db, SalesOrderItem(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, so1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [SalesOrderItem(workspace_id=w1.id, sales_order_id=so1.id, description="Line", quantity_ordered=Decimal("1.00"), unit_price=Decimal("2.00"), line_total=Decimal("2.00"))
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


# Convention "nothing written": the number of sales_order_items rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(SalesOrderItem.__table__)).scalar_one()


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
        """The one SELECT from sales_order_items; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "sales_order_items" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DAOSalesOrderItem.get_by_sales_order
# --------------------------------------------------------------------------- #


# [claude] SOI-G-01
def test_soi_g_01__returns_a_list_of_the_order_s_lines(db, w1, so1, mk_line):
    """SOI-G-01 — returns a list of the order's lines.
    Rules: `get_by_sales_order` R1, Returns"""
    a = mk_line()
    b = mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert set(ids(result)) == {a.id, b.id}
    # Then 4
    assert isinstance(result[0], SalesOrderItem)


# [claude] SOI-G-02
def test_soi_g_02__a_line_of_another_order_of_the_same_workspace_is_not_returned_though_i(db, w1, so1, so2, mk_line):
    """SOI-G-02 — a line of another order of the same workspace is not returned, though it sorts first.
    Rules: `get_by_sales_order` R1"""
    mk_line(sales_order_id=so2.id)
    a = mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] SOI-G-03
def test_soi_g_03__the_right_order_under_another_workspace_returns_an_empty_list(db, w2, so1, mk_line):
    """SOI-G-03 — the right order under another workspace returns an empty list.
    Rules: `get_by_sales_order` R1"""
    mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] SOI-G-04
def test_soi_g_04__an_unknown_workspace_returns_an_empty_list(db, so1, mk_line):
    """SOI-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_sales_order` R1"""
    mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] SOI-G-05
def test_soi_g_05__a_w2_row_on_a_w1_order_is_returned_for_w2_only_the_row_s_workspace_is(db, w2, so1, mk_line):
    """SOI-G-05 — a W2 row on a W1 order is returned for W2: only the row's workspace is compared.
    Rules: `get_by_sales_order` R1"""
    a = mk_line(workspace_id=w2.id)

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] SOI-G-06
def test_soi_g_06__a_w2_row_on_a_w1_order_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, so1, mk_line):
    """SOI-G-06 — a W2 row on a W1 order is not returned for W1, though it sorts first.
    Rules: `get_by_sales_order` R1"""
    mk_line(workspace_id=w2.id)
    a = mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] SOI-G-07
def test_soi_g_07__an_unknown_order_id_returns_an_empty_list(db, w1, mk_line):
    """SOI-G-07 — an unknown order id returns an empty list.
    Rules: `get_by_sales_order` R2"""
    mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] SOI-G-08
def test_soi_g_08__order_id_0_returns_an_empty_list(db, w1, mk_line):
    """SOI-G-08 — order id 0 returns an empty list.
    Rules: `get_by_sales_order` R2"""
    mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] SOI-G-09
def test_soi_g_09__an_order_with_no_rows_returns_an_empty_list(db, w1, so2, mk_line):
    """SOI-G-09 — an order with no rows returns an empty list.
    Rules: `get_by_sales_order` R2"""
    mk_line()

    result = dao.get_by_sales_order(db, sales_order_id=so2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] SOI-G-10
def test_soi_g_10__a_free_text_line_is_returned_with_its_description_as_item_name(db, w1, so1, mk_line):
    """SOI-G-10 — a free-text line is returned, with its description as item_name.
    Rules: `get_by_sales_order` R1"""
    a = mk_line(description="Custom bracket")

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_id is None
    # Then 3
    assert result[0].item_name == "Custom bracket"


# [claude] SOI-G-11
def test_soi_g_11__a_line_on_an_inactive_item_is_returned_with_that_item_s_name(db, w1, so1, ir, mk_line):
    """SOI-G-11 — a line on an inactive item is returned, with that item's name.
    Rules: `get_by_sales_order` R5"""
    a = mk_line(item_id=ir.id, description=None)

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_id == ir.id
    # Then 3
    assert result[0].item_name == "Old Gasket"


# [claude] SOI-G-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1270: A sales order's lines have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_soi_g_12__rows_come_back_by_id_ascending_when_the_lowest_id_was_updated(db, w1, so1, mk_line):
    """SOI-G-12 — rows come back by id ascending, when the lowest id was updated.
    Rules: `get_by_sales_order` R3 [BUG-1270]"""
    a = mk_line(description="Zeta")
    b = mk_line(description="Mid")
    c = mk_line(description="Alpha")
    a.quantity_ordered = Decimal("3.00")
    db.flush()
    db.expire_all()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] SOI-G-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1270: A sales order's lines have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_soi_g_13__rows_come_back_by_id_ascending_with_no_update(db, w1, so1, mk_line):
    """SOI-G-13 — rows come back by id ascending, with no update.
    Rules: `get_by_sales_order` R3 [BUG-1270]"""
    a = mk_line(description="Zeta")
    b = mk_line(description="Mid")
    c = mk_line(description="Alpha")
    db.expire_all()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] SOI-G-14
@pytest.mark.xfail(strict=True, reason="BUG-1270: A sales order's lines have no sort order")
def test_soi_g_14__the_query_orders_by_id_ascending(db, w1, so1, mk_line):
    """SOI-G-14 — the query orders by id ascending.
    Rules: `get_by_sales_order` R3 [BUG-1270]"""
    a = mk_line()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)
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


# [claude] SOI-G-15
def test_soi_g_15__there_is_no_cap_103_lines_give_103_rows(db, w1, so1, mk_many):
    """SOI-G-15 — there is no cap: 103 lines give 103 rows.
    Rules: `get_by_sales_order` R4"""
    in_order = mk_many(103)

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 103
    # Then 2
    assert set(ids(result)) == set(in_order)


# [claude] SOI-G-16
def test_soi_g_16__a_positional_sales_order_id_raises_typeerror(db, w1, so1):
    """SOI-G-16 — a positional `sales_order_id` raises TypeError.
    Rules: `get_by_sales_order` R6"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_sales_order(db, so1.id, workspace_id=w1.id)
    # Then 2
    assert stored_count(db) == before


# [claude] SOI-G-17
def test_soi_g_17__writes_nothing_a_pending_row_stays_pending_and_alone_in_the_session(db, w1, so1, mk_line):
    """SOI-G-17 — writes nothing: a pending row stays pending and alone in the session.
    Rules: `get_by_sales_order` Side effects"""
    a = mk_line()
    p = SalesOrderItem(workspace_id=w1.id, sales_order_id=so1.id, description="Line", quantity_ordered=Decimal("1.00"), unit_price=Decimal("2.00"), line_total=Decimal("2.00"))
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)
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
    assert "sales_orders" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] SOI-G-18
def test_soi_g_18__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, so1, so2, mk_line):
    """SOI-G-18 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_sales_order` Side effects"""
    a = mk_line()
    b = mk_line(sales_order_id=so2.id)
    b.description = "Edited"

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# [claude] SOI-G-19
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1270: A sales order's lines have no sort order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_soi_g_19__rows_come_back_by_id_ascending_when_price_would_sort_the_other_way(db, w1, so1, mk_line):
    """SOI-G-19 — rows come back by id ascending, when price would sort the other way.
    Rules: `get_by_sales_order` R3 [BUG-1270]"""
    a = mk_line(unit_price=Decimal("9.00"), line_total=Decimal("9.00"))
    b = mk_line(unit_price=Decimal("1.00"), line_total=Decimal("1.00"))
    db.expire_all()

    result = dao.get_by_sales_order(db, sales_order_id=so1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]
