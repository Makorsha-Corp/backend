"""Unit tests for app/dao/invoice_item.py.

Implements tests/unit/dao/invoice_item.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None). II-DA-08 spies on `db.commit`, as the Conventions' "rolled back" asks.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.invoice_item import invoice_item_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.invoice_item import InvoiceItem
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton invoice_item_dao" (a module-level name, not a fixture)
dao = invoice_item_dao

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
def ac1(db, w1, w2):
    return _add(db, Account(workspace_id=w1.id, name="Acme"))


@pytest.fixture
def ac9(db, w2, ac1):
    return _add(db, Account(workspace_id=w2.id, name="Acme"))


@pytest.fixture
def in1(db, w1, ac1, ac9):
    return _add(db, AccountInvoice(workspace_id=w1.id, account_id=ac1.id, invoice_type="payable", invoice_status="draft", invoice_amount=0, paid_amount=0, invoice_date=date(2026, 3, 1), payment_status="unpaid", allow_payments=True))


@pytest.fixture
def in2(db, w1, ac1, in1):
    return _add(db, AccountInvoice(workspace_id=w1.id, account_id=ac1.id, invoice_type="payable", invoice_status="draft", invoice_amount=0, paid_amount=0, invoice_date=date(2026, 3, 1), payment_status="unpaid", allow_payments=True))


@pytest.fixture
def inc(db, w1, ac1, in2):
    return _add(db, AccountInvoice(workspace_id=w1.id, account_id=ac1.id, invoice_type="payable", invoice_status="confirmed", invoice_amount=0, paid_amount=0, invoice_date=date(2026, 3, 1), payment_status="unpaid", allow_payments=True))


@pytest.fixture
def in9(db, w2, ac9, inc):
    return _add(db, AccountInvoice(workspace_id=w2.id, account_id=ac9.id, invoice_type="payable", invoice_status="draft", invoice_amount=0, paid_amount=0, invoice_date=date(2026, 3, 1), payment_status="unpaid", allow_payments=True))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, ac1, ac9, in1, in2, inc, in9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "line": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_line(db, w1, in1):
    """mk_line(line_number=..., **columns) -> InvoiceItem. Keywords only."""
    def _mk(*, line_number, **columns):
        fields = {"workspace_id": w1.id, "invoice_id": in1.id, "description": "Line", "quantity": Decimal("1.00"), "unit_price": Decimal("2.00"), "line_subtotal": Decimal("2.00"), "line_number": line_number}
        fields.update(columns)
        return _add(db, InvoiceItem(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, in1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [InvoiceItem(workspace_id=w1.id, invoice_id=in1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=k)
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


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    model = type(row)
    key = sa_inspect(row).identity[0]
    db.expire_all()
    return db.query(model).filter(model.id == key).one()


# Convention "nothing written": the number of invoice_items rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(InvoiceItem.__table__)).scalar_one()


# The `count:` lines: stored invoice_items rows with these column values (all workspaces)
def row_count(db, **where):
    table = InvoiceItem.__table__
    query = select(func.count()).select_from(table).where(*[table.c[name] == value for name, value in where.items()])
    return db.execute(query).scalar_one()


# Convention "seqscan": transaction-local, gone with the rollback
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


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
        """The one SELECT from invoice_items; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "invoice_items" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# InvoiceItemDAO.get_by_invoice
# --------------------------------------------------------------------------- #


# [claude] II-GI-01
def test_ii_gi_01__returns_a_list_of_the_invoice_s_lines(db, w1, in1, mk_line):
    """II-GI-01 — returns a list of the invoice's lines.
    Rules: `get_by_invoice` R1, Returns"""
    a = mk_line(line_number=1)
    b = mk_line(line_number=2)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], InvoiceItem)


# [claude] II-GI-02
def test_ii_gi_02__a_line_of_another_invoice_of_the_same_workspace_is_not_returned_though(db, w1, in1, in2, mk_line):
    """II-GI-02 — a line of another invoice of the same workspace is not returned, though it sorts first.
    Rules: `get_by_invoice` R1"""
    a = mk_line(line_number=2)
    mk_line(line_number=1, invoice_id=in2.id)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] II-GI-03
def test_ii_gi_03__the_right_invoice_under_another_workspace_returns_an_empty_list(db, w2, in1, mk_line):
    """II-GI-03 — the right invoice under another workspace returns an empty list.
    Rules: `get_by_invoice` R2"""
    mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] II-GI-04
def test_ii_gi_04__an_unknown_workspace_returns_an_empty_list(db, in1, mk_line):
    """II-GI-04 — an unknown workspace returns an empty list.
    Rules: `get_by_invoice` R2"""
    mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] II-GI-05
def test_ii_gi_05__a_w2_row_on_a_w1_invoice_is_returned_for_w2_only_the_row_s_workspace_i(db, w2, in1, mk_line):
    """II-GI-05 — a W2 row on a W1 invoice is returned for W2: only the row's workspace is compared.
    Rules: `get_by_invoice` R2"""
    a = mk_line(line_number=1, workspace_id=w2.id)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] II-GI-06
def test_ii_gi_06__a_w2_row_on_a_w1_invoice_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, in1, mk_line):
    """II-GI-06 — a W2 row on a W1 invoice is not returned for W1, though it sorts first.
    Rules: `get_by_invoice` R2"""
    mk_line(line_number=1, workspace_id=w2.id)
    a = mk_line(line_number=2)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] II-GI-07
def test_ii_gi_07__an_unknown_invoice_id_returns_an_empty_list(db, w1, mk_line):
    """II-GI-07 — an unknown invoice id returns an empty list.
    Rules: `get_by_invoice` R3"""
    mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] II-GI-08
def test_ii_gi_08__invoice_id_0_returns_an_empty_list(db, w1, mk_line):
    """II-GI-08 — invoice id 0 returns an empty list.
    Rules: `get_by_invoice` R3"""
    mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] II-GI-09
def test_ii_gi_09__an_invoice_with_no_rows_returns_an_empty_list(db, w1, in2, mk_line):
    """II-GI-09 — an invoice with no rows returns an empty list.
    Rules: `get_by_invoice` R3"""
    mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=in2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] II-GI-10
def test_ii_gi_10__a_line_comes_back_with_its_stored_money_values(db, w1, in1, mk_line):
    """II-GI-10 — a line comes back with its stored money values.
    Rules: `get_by_invoice` R1"""
    a = mk_line(line_number=4, description="Press plate", quantity=Decimal("2.50"), unit_price=Decimal("1.25"), line_subtotal=Decimal("3.13"), item_id=77, source_order_item_id=88)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].invoice_id == in1.id
    assert result[0].workspace_id == w1.id
    assert result[0].line_number == 4
    # Then 3
    assert result[0].description == "Press plate"
    assert result[0].item_id == 77
    assert result[0].source_order_item_id == 88
    # Then 4
    assert result[0].quantity == Decimal("2.50")
    assert result[0].unit_price == Decimal("1.25")
    assert result[0].line_subtotal == Decimal("3.13")


# [claude] II-GI-11
def test_ii_gi_11__lines_are_ordered_by_line_number_ascending_whatever_their_ids_and_as_n(db, w1, in1, mk_line):
    """II-GI-11 — lines are ordered by line_number ascending, whatever their ids, and as numbers.
    Rules: `get_by_invoice` R4"""
    a = mk_line(line_number=10)
    b = mk_line(line_number=2)
    c = mk_line(line_number=1)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] II-GI-12
def test_ii_gi_12__line_number_decides_not_the_description_or_the_money_values(db, w1, in1, mk_line):
    """II-GI-12 — line_number decides, not the description or the money values.
    Rules: `get_by_invoice` R4"""
    a = mk_line(line_number=2, description="Alpha", line_subtotal=Decimal("1.00"))
    b = mk_line(line_number=1, description="Zeta", line_subtotal=Decimal("9.00"))

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] II-GI-13
def test_ii_gi_13__on_a_tie_both_lines_are_returned_after_the_lower_line_number(db, w1, in1, mk_line):
    """II-GI-13 — on a tie both lines are returned, after the lower line_number.
    Rules: `get_by_invoice` R5, R4"""
    a = mk_line(line_number=2)
    b = mk_line(line_number=2)
    c = mk_line(line_number=1)
    a.quantity = Decimal("3.00")
    db.flush()
    db.expire_all()

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:]} == {a.id, b.id}


# [claude] II-GI-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-638: Events and line items with tied sort keys come back in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_ii_gi_14__on_a_tie_the_lowest_id_comes_first_when_the_lower_id_was_updated(db, w1, in1, mk_line):
    """II-GI-14 — on a tie the lowest id comes first, when the lower id was updated.
    Rules: `get_by_invoice` R5 [BUG-638]"""
    a = mk_line(line_number=1)
    b = mk_line(line_number=1)
    a.quantity = Decimal("3.00")
    db.flush()
    db.expire_all()
    seqscan(db)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] II-GI-15
@pytest.mark.xfail(
    strict=False,
    reason="BUG-638: Events and line items with tied sort keys come back in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_ii_gi_15__on_a_tie_the_lowest_id_comes_first_when_text_and_money_would_sort_the(db, w1, in1, mk_line):
    """II-GI-15 — on a tie the lowest id comes first, when text and money would sort the other way.
    Rules: `get_by_invoice` R5 [BUG-638]"""
    a = mk_line(line_number=1, description="Zeta", line_subtotal=Decimal("9.00"))
    b = mk_line(line_number=1, description="Alpha", line_subtotal=Decimal("1.00"))
    db.expire_all()

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] II-GI-16
@pytest.mark.xfail(strict=True, reason="BUG-638: Events and line items with tied sort keys come back in no fixed order")
def test_ii_gi_16__the_query_orders_by_line_number_then_id_ascending(db, w1, in1, mk_line):
    """II-GI-16 — the query orders by line_number, then id ascending.
    Rules: `get_by_invoice` R5 [BUG-638]"""
    a = mk_line(line_number=1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "line_number" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("line_number") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()


# [claude] II-GI-17
def test_ii_gi_17__there_is_no_cap_101_lines_give_101_rows(db, w1, in1, mk_many):
    """II-GI-17 — there is no cap: 101 lines give 101 rows.
    Rules: `get_by_invoice` R6"""
    in_order = mk_many(101)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] II-GI-18
def test_ii_gi_18__a_positional_invoice_id_raises_typeerror(db, w1, in1):
    """II-GI-18 — a positional `invoice_id` raises TypeError.
    Rules: `get_by_invoice` R7"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_invoice(db, in1.id, workspace_id=w1.id)
    # Then 2
    assert stored_count(db) == before


# [claude] II-GI-19
def test_ii_gi_19__the_invoice_s_status_is_not_looked_at_the_lines_of_a_confirmed_invoice(db, w1, inc, mk_line):
    """II-GI-19 — the invoice's status is not looked at: the lines of a confirmed invoice are returned.
    Rules: `get_by_invoice` Overview"""
    a = mk_line(line_number=1, invoice_id=inc.id)

    result = dao.get_by_invoice(db, invoice_id=inc.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] II-GI-20
def test_ii_gi_20__writes_nothing_a_pending_line_that_sorts_first_stays_pending_and_alone(db, w1, in1, mk_line):
    """II-GI-20 — writes nothing: a pending line that sorts first stays pending and alone in the session.
    Rules: `get_by_invoice` Side effects, Overview"""
    a = mk_line(line_number=2)
    p = InvoiceItem(workspace_id=w1.id, invoice_id=in1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)
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
    assert "account_invoices" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] II-GI-21
def test_ii_gi_21__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, in1, in2, mk_line):
    """II-GI-21 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_invoice` Side effects"""
    a = mk_line(line_number=1)
    b = mk_line(line_number=1, invoice_id=in2.id)
    b.description = "Edited"

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# --------------------------------------------------------------------------- #
# InvoiceItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] II-GW-01
def test_ii_gw_01__returns_the_line_of_that_id_not_the_first_line(db, w1, mk_line):
    """II-GW-01 — returns the line of that id, not the first line.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_line(line_number=1)
    b = mk_line(line_number=2)

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, InvoiceItem)


# [claude] II-GW-02
def test_ii_gw_02__another_workspace_returns_none(db, w2, mk_line):
    """II-GW-02 — another workspace returns None.
    Rules: `get_by_id_and_workspace` R1"""
    mk_line(line_number=1)
    b = mk_line(line_number=2)

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] II-GW-03
def test_ii_gw_03__an_unknown_id_returns_none_and_nothing_is_created(db, w1, mk_line):
    """II-GW-03 — an unknown id returns None and nothing is created.
    Rules: `get_by_id_and_workspace` R1"""
    mk_line(line_number=1)
    before = stored_count(db)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] II-GW-04
def test_ii_gw_04__writes_nothing_a_read_that_finds_its_line_leaves_the_session_as_it_was(db, w1, in1, mk_line):
    """II-GW-04 — writes nothing: a read that finds its line leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(line_number=1)
    p = InvoiceItem(workspace_id=w1.id, invoice_id=in1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)
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


# [claude] II-GW-05
def test_ii_gw_05__a_w2_line_at_the_earlier_id_is_not_returned_for_w1(db, w1, w2, in9, mk_line):
    """II-GW-05 — a W2 line at the earlier id is not returned for W1.
    Rules: `get_by_id_and_workspace` R1"""
    z = mk_line(line_number=1, workspace_id=w2.id, invoice_id=in9.id)
    mk_line(line_number=2)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] II-GW-06
def test_ii_gw_06__the_invoice_s_status_is_not_looked_at_and_the_invoice_is_not_joined_a(db, w1, inc, mk_line):
    """II-GW-06 — the invoice's status is not looked at and the invoice is not joined: a line of a confirmed invoice is returned.
    Rules: `get_by_id_and_workspace` Overview"""
    a = mk_line(line_number=1, invoice_id=inc.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert "account_invoices" not in sql


# [claude] II-GW-07
def test_ii_gw_07__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, mk_line):
    """II-GW-07 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_line(line_number=1)
    b = mk_line(line_number=2)
    b.description = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.description == "Edited"


# --------------------------------------------------------------------------- #
# InvoiceItemDAO.delete_all_for_invoice
# --------------------------------------------------------------------------- #


# [claude] II-DA-01
def test_ii_da_01__every_line_of_the_invoice_is_deleted_lines_of_another_invoice_stay(db, in1, in2, mk_line):
    """II-DA-01 — every line of the invoice is deleted; lines of another invoice stay.
    Rules: `delete_all_for_invoice` R1, Returns"""
    mk_line(line_number=1)
    mk_line(line_number=2)
    c = mk_line(line_number=1, invoice_id=in2.id)
    before_c = snap(db, c)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=in1.id) == 0
    # Then 3
    assert row_count(db, invoice_id=in2.id) == 1
    # Then 4
    db.expire_all()
    assert snap(db, c) == before_c


# [claude] II-DA-02
def test_ii_da_02__lines_of_another_invoice_in_another_workspace_stay(db, w2, in1, in9, mk_line):
    """II-DA-02 — lines of another invoice in another workspace stay.
    Rules: `delete_all_for_invoice` R1"""
    mk_line(line_number=1)
    c = mk_line(line_number=1, workspace_id=w2.id, invoice_id=in9.id)
    before_c = snap(db, c)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=in1.id) == 0
    # Then 3
    assert row_count(db, invoice_id=in9.id) == 1
    # Then 4
    db.expire_all()
    assert snap(db, c) == before_c


# [claude] II-DA-03
def test_ii_da_03__no_workspace_filter_a_w2_row_carrying_this_invoice_id_is_deleted_too(db, w2, in1, mk_line):
    """II-DA-03 — no workspace filter: a W2 row carrying this invoice id is deleted too.
    Rules: `delete_all_for_invoice` R2"""
    mk_line(line_number=1)
    mk_line(line_number=2, workspace_id=w2.id)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=in1.id) == 0
    # Then 3
    assert row_count(db, workspace_id=w2.id) == 0


# [claude] II-DA-04
def test_ii_da_04__an_unknown_invoice_id_deletes_nothing_and_raises_nothing(db, mk_line):
    """II-DA-04 — an unknown invoice id deletes nothing and raises nothing.
    Rules: `delete_all_for_invoice` R3"""
    a = mk_line(line_number=1)
    before = stored_count(db)
    before_a = snap(db, a)

    result = dao.delete_all_for_invoice(db, invoice_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] II-DA-05
def test_ii_da_05__invoice_id_0_deletes_nothing_and_raises_nothing(db, mk_line):
    """II-DA-05 — invoice id 0 deletes nothing and raises nothing.
    Rules: `delete_all_for_invoice` R3"""
    a = mk_line(line_number=1)
    before = stored_count(db)
    before_a = snap(db, a)

    result = dao.delete_all_for_invoice(db, invoice_id=0)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] II-DA-06
def test_ii_da_06__an_invoice_with_no_lines_deletes_nothing_and_raises_nothing(db, in2, mk_line):
    """II-DA-06 — an invoice with no lines deletes nothing and raises nothing.
    Rules: `delete_all_for_invoice` R3"""
    a = mk_line(line_number=1)
    before = stored_count(db)
    before_a = snap(db, a)

    result = dao.delete_all_for_invoice(db, invoice_id=in2.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] II-DA-07
def test_ii_da_07__the_status_is_not_looked_at_the_lines_of_a_confirmed_invoice_are_delet(db, inc, mk_line):
    """II-DA-07 — the status is not looked at: the lines of a confirmed invoice are deleted, and the invoice is not touched.
    Rules: `delete_all_for_invoice` R4, Side effects"""
    mk_line(line_number=1, invoice_id=inc.id)
    mk_line(line_number=2, invoice_id=inc.id)
    before_inc = snap(db, inc)

    result = dao.delete_all_for_invoice(db, invoice_id=inc.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=inc.id) == 0
    # Then 3
    db.expire_all()
    assert snap(db, inc) == before_inc
    # Then 4
    row = reread(db, inc)
    assert row.invoice_status == "confirmed"


# [claude] II-DA-08
def test_ii_da_08__the_delete_is_flushed_not_committed_gone_in_the_session_back_after_a_r(db, in1, mk_line):
    """II-DA-08 — the delete is flushed, not committed: gone in the session, back after a rollback.
    Rules: `delete_all_for_invoice` R5, Side effects"""
    a = mk_line(line_number=1, line_subtotal=Decimal("7.25"))
    mk_line(line_number=2)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=in1.id) == 0
    # Then 3
    sp.rollback()
    assert row_count(db, invoice_id=in1.id) == 2
    # Then 4
    row = reread(db, a)
    assert row.line_subtotal == Decimal("7.25")
    # Then 5
    commit_spy.assert_not_called()


# [claude] II-DA-09
def test_ii_da_09__the_method_flushes_a_line_of_another_invoice_waiting_in_the_session_is(db, w1, in1, in2, mk_line):
    """II-DA-09 — the method flushes: a line of another invoice waiting in the session is stored by the call.
    Rules: `delete_all_for_invoice` R5"""
    mk_line(line_number=1)
    p = InvoiceItem(workspace_id=w1.id, invoice_id=in2.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)
    db.add(p)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert p not in db.new
    # Then 3
    assert p.id is not None
    # Then 4
    assert row_count(db, invoice_id=in1.id) == 0
    # Then 5
    assert row_count(db, invoice_id=in2.id) == 1


# [claude] II-DA-10
def test_ii_da_10__one_delete_statement_on_this_table_only_with_no_workspace_and_no_invoi(db, in1, mk_line):
    """II-DA-10 — one DELETE statement, on this table only, with no workspace and no invoice read.
    Rules: `delete_all_for_invoice` Side effects, R2, R4"""
    mk_line(line_number=1)
    mk_line(line_number=2)

    with StatementRecorder(db) as recorder:
        result = dao.delete_all_for_invoice(db, invoice_id=in1.id)
    written = recorder.written()
    selects = recorder.selects()

    # Then 1
    assert result is None
    # Then 2
    assert len(written) == 1
    # Then 3
    assert written[0].upper().startswith("DELETE")
    # Then 4
    assert "invoice_items" in written[0]
    # Then 5
    assert "workspace_id" not in written[0]
    # Then 6
    assert "account_invoices" not in written[0]
    # Then 7
    assert selects == []


# [claude] II-DA-11
def test_ii_da_11__after_the_delete_db_get_returns_the_stale_instance_with_no_query(db, in1, mk_line):
    """II-DA-11 — after the delete, db.get returns the stale instance with no query.
    Rules: `delete_all_for_invoice` R6"""
    a = mk_line(line_number=1, description="Stale")
    a_id = a.id
    dao.delete_all_for_invoice(db, invoice_id=in1.id)

    with StatementRecorder(db) as recorder:
        result = db.get(InvoiceItem, a_id)
    selects = recorder.selects()

    # Then 1
    assert result is a
    # Then 2
    assert result.description == "Stale"
    # Then 3
    assert selects == []


# [claude] II-DA-12
def test_ii_da_12__after_the_delete_get_by_invoice_runs_a_query_and_does_not_find_the_lin(db, w1, in1, mk_line):
    """II-DA-12 — after the delete, get_by_invoice runs a query and does not find the line.
    Rules: `delete_all_for_invoice` R6"""
    mk_line(line_number=1)
    dao.delete_all_for_invoice(db, invoice_id=in1.id)

    result = dao.get_by_invoice(db, invoice_id=in1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] II-DA-13
def test_ii_da_13__after_the_delete_get_by_id_and_workspace_runs_a_query_and_does_not_fin(db, w1, in1, mk_line):
    """II-DA-13 — after the delete, get_by_id_and_workspace runs a query and does not find the line.
    Rules: `delete_all_for_invoice` R6"""
    a = mk_line(line_number=1)
    a_id = a.id
    dao.delete_all_for_invoice(db, invoice_id=in1.id)

    result = dao.get_by_id_and_workspace(db, id=a_id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] II-DA-14
@pytest.mark.xfail(strict=True, reason="BUG-1283: Clearing an invoice's lines keeps a line added but not yet flushed")
def test_ii_da_14__a_line_of_the_same_invoice_waiting_in_the_session_is_deleted_too_and_t(db, w1, in1, mk_line):
    """II-DA-14 — a line of the same invoice waiting in the session is deleted too, and the flush does not store it.
    Rules: `delete_all_for_invoice` R7 [BUG-1283]"""
    mk_line(line_number=1)
    p = InvoiceItem(workspace_id=w1.id, invoice_id=in1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)
    db.add(p)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert row_count(db, invoice_id=in1.id) == 0


# [claude] II-DA-15
def test_ii_da_15__with_a_pending_line_of_each_invoice_the_other_invoice_s_line_is_still(db, w1, in1, in2, mk_line):
    """II-DA-15 — with a pending line of each invoice, the other invoice's line is still stored by the flush.
    Rules: `delete_all_for_invoice` R7"""
    mk_line(line_number=1)
    p1 = InvoiceItem(workspace_id=w1.id, invoice_id=in1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)
    db.add(p1)
    p2 = InvoiceItem(workspace_id=w1.id, invoice_id=in2.id, description="Other", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)
    db.add(p2)

    result = dao.delete_all_for_invoice(db, invoice_id=in1.id)

    # Then 1
    assert result is None
    # Then 2
    assert p2 not in db.new
    # Then 3
    assert p2.id is not None
    # Then 4
    assert row_count(db, invoice_id=in2.id) == 1
