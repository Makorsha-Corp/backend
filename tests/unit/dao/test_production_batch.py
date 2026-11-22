"""Unit tests for app/dao/production_batch.py.

Implements tests/unit/dao/production_batch.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture).
Only the clock of generate_batch_number is patched (Conventions, clocks(L, U)).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from psycopg2.errors import NotNullViolation, UniqueViolation
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.production_batch import production_batch_dao
from app.models.factory import Factory
from app.models.production_batch import ProductionBatch
from app.models.production_formula import ProductionFormula
from app.models.production_line import ProductionLine
from app.schemas.production_batch import ProductionBatchCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_batch_dao" (a module-level name, not a fixture)
dao = production_batch_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0": a past stamp
T0 = datetime(2026, 1, 15, 9, 0, 0)

# Conventions: fixed values
D1 = date(2026, 3, 1)
D2 = date(2026, 3, 2)
D3 = date(2026, 3, 3)
D4 = date(2026, 3, 4)
D5 = date(2026, 3, 5)
T9 = datetime(2026, 3, 4, 9, 0, 0)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)
CK = datetime(2026, 6, 1, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Given lines "built with add_all"
def add_many(db, rows):
    db.add_all(rows)
    db.flush()


# Conventions list these rows in this order; each fixture depends on the one before,
# so they are flushed one at a time in that order and the ids rise in that order.
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
def f2(db, w1, f1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory Two", abbreviation="F2"))


@pytest.fixture
def fd(db, w1, u1, f2):
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True, deleted_at=T0, deleted_by=u1.id))


@pytest.fixture
def fi(db, w1, fd):
    return _add(db, Factory(workspace_id=w1.id, name="Idle Plant", abbreviation="IP", is_active=False))


@pytest.fixture
def f9(db, w2, fi):
    return _add(db, Factory(workspace_id=w2.id, name="Far Plant", abbreviation="F9"))


@pytest.fixture
def l1(db, w1, f1, f9):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Line One"))


@pytest.fixture
def l2(db, w1, f1, l1):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Line Two"))


@pytest.fixture
def lf(db, w1, f2, l2):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f2.id, name="Line Three"))


@pytest.fixture
def ln(db, w1, f1, lf):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Off Line", is_active=False))


@pytest.fixture
def ld(db, w1, fd, ln):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=fd.id, name="Lost Line"))


@pytest.fixture
def li(db, w1, fi, ld):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=fi.id, name="Quiet Line"))


@pytest.fixture
def l9(db, w2, f9, li):
    return _add(db, ProductionLine(workspace_id=w2.id, factory_id=f9.id, name="Far Line"))


@pytest.fixture
def pf1(db, w1, l9):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-1", name="Yarn"))


@pytest.fixture
def pf2(db, w1, pf1):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-2", name="Rope"))


@pytest.fixture
def pfd(db, w1, pf2):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-3", name="Twine", is_active=False, is_default=False))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, f1, f2, fd, fi, f9, l1, l2, lf, ln, ld, li, l9, pf1, pf2, pfd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each mk_ flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "batch"
@pytest.fixture
def new_batch(w1, l1):
    """new_batch(batch_number=..., **columns) -> ProductionBatch, not added."""
    def _new(*, batch_number, **columns):
        return ProductionBatch(**{"workspace_id": w1.id, "production_line_id": l1.id, "batch_date": D3, "status": "draft", "batch_number": batch_number, **columns})
    return _new


@pytest.fixture
def mk_batch(db, new_batch):
    """mk_batch(...) = new_batch(...), added and flushed."""
    def _mk(**columns):
        return _add(db, new_batch(**columns))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
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


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    db.expire_all()
    return db.get(type(row), sa_inspect(row).identity[0])


# Convention "nothing written": the number of `production_batches` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(ProductionBatch.__table__))


# Convention "count:": rows in all workspaces, with the filter stated
def count_rows(db, model, *where):
    return db.scalar(select(func.count()).select_from(model.__table__).where(*where))


# Convention "seq scan": three steps at that place in the Given
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# Convention "clocks(L, U)": during the When
@contextmanager
def clocks(local, utc):
    with patch("app.dao.production_batch.datetime", create=True) as clock, \
            patch("app.dao.production_batch.utcnow", create=True, return_value=utc):
        clock.now.return_value = local
        yield


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends from recorder.start() (the start of the When) to the end of the test.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []
        self.started = False

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def start(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        self.started = True

    def stop(self):
        if self.started:
            event.remove(self.bind, "before_cursor_execute", self._record)
            self.started = False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from `production_batches`; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "FROM production_batches" in s]
        return statement


@pytest.fixture
def recorder(db):
    statement_recorder = StatementRecorder(db)
    yield statement_recorder
    statement_recorder.stop()


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] BAT-GW-01
def test_bat_gw_01__returns_a_list_of_the_workspace_s_batches_of_every_status(db, w1, mk_batch):
    """BAT-GW-01 — returns a list of the workspace's batches, of every status.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4, status="in_progress")
    c = mk_batch(batch_number="B-C", batch_date=D3, status="completed")
    d = mk_batch(batch_number="B-D", batch_date=D2, status="cancelled")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id, c.id, d.id]
    # Then 3
    assert isinstance(result[0], ProductionBatch)


# [claude] BAT-GW-02
def test_bat_gw_02__a_newer_batch_of_another_workspace_is_not_returned(db, w1, w2, l9, mk_batch):
    """BAT-GW-02 — a newer batch of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    a = mk_batch(batch_number="B-A", batch_date=D4)
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D5)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-03
def test_bat_gw_03__an_earlier_id_batch_of_another_workspace_is_not_returned(db, w1, w2, l9, mk_batch):
    """BAT-GW-03 — an earlier-id batch of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D5)
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-04
def test_bat_gw_04__a_batch_of_an_inactive_line_is_returned(db, w1, ln, mk_batch):
    """BAT-GW-04 — a batch of an inactive line is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, production_line_id=ln.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-05
def test_bat_gw_05__a_batch_of_an_inactive_formula_is_returned(db, w1, pfd, mk_batch):
    """BAT-GW-05 — a batch of an inactive formula is returned.
    Rules: `get_by_workspace` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pfd.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-06
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gw_06__a_batch_of_a_soft_deleted_factory_is_not_returned(db, w1, ld, mk_batch):
    """BAT-GW-06 — a batch of a soft-deleted factory is not returned.
    Rules: `get_by_workspace` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-07
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gw_07__a_w2_batch_on_a_line_of_a_soft_deleted_w1_factory_is_hidden_too(db, w2, ld, mk_batch):
    """BAT-GW-07 — a W2 batch on a line of a soft-deleted W1 factory is hidden too.
    Rules: `get_by_workspace` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GW-08
def test_bat_gw_08__reading_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, ld, mk_batch, recorder):
    """BAT-GW-08 — reading with a soft-deleted factory changes nothing.
    Rules: `get_by_workspace` R2b"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    before_x = snap(db, x)
    before_ld = snap(db, ld)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, ld) == before_ld
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert recorder.written() == []


# [claude] BAT-GW-09
def test_bat_gw_09__an_inactive_factory_hides_nothing(db, w1, li, mk_batch):
    """BAT-GW-09 — an inactive factory hides nothing.
    Rules: `get_by_workspace` R2b"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=li.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] BAT-GW-10
def test_bat_gw_10__once_the_factory_is_live_again_the_batch_is_back_unchanged(db, w1, fd, ld, mk_batch):
    """BAT-GW-10 — once the factory is live again the batch is back, unchanged.
    Rules: `get_by_workspace` R2b"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] BAT-GW-11
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gw_11__hidden_whatever_the_status(db, w1, ld, mk_batch):
    """BAT-GW-11 — hidden whatever the status.
    Rules: `get_by_workspace` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id, status="in_progress")
    mk_batch(batch_number="B-Y", batch_date=D5, production_line_id=ld.id, status="completed")
    mk_batch(batch_number="B-V", batch_date=D5, production_line_id=ld.id, status="cancelled")
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GW-12
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gw_12__a_hidden_batch_takes_no_place_in_the_page(db, w1, ld, mk_batch):
    """BAT-GW-12 — a hidden batch takes no place in the page.
    Rules: `get_by_workspace` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GW-13
@pytest.mark.xfail(strict=True, reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order")
def test_bat_gw_13__the_query_orders_by_batch_date_then_id_both_descending(db, w1, mk_batch, recorder):
    """BAT-GW-13 — the query orders by batch_date, then id, both descending.
    Rules: `get_by_workspace` R3 [BUG-1321]"""
    a = mk_batch(batch_number="B-A", batch_date=D5)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "batch_date" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("batch_date") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] BAT-GW-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gw_14__on_a_tied_date_the_highest_id_comes_first_when_the_lowest_ids_were_upd(db, w1, mk_batch):
    """BAT-GW-14 — on a tied date the highest id comes first, when the lowest ids were updated.
    Rules: `get_by_workspace` R3 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D3)
    c = mk_batch(batch_number="B-C", batch_date=D3)
    d = mk_batch(batch_number="B-D", batch_date=D3)
    a.notes = "Changed"
    b.notes = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] BAT-GW-15
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gw_15__on_a_tied_date_the_id_decides_when_number_shift_quantity_and_stamp_wou(db, w1, mk_batch):
    """BAT-GW-15 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id.
    Rules: `get_by_workspace` R3 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-M", batch_date=D3, shift="B", expected_output_quantity=7, created_at=T11)
    b = mk_batch(batch_number="B-Z", batch_date=D3, shift="C", expected_output_quantity=9, created_at=T9)
    c = mk_batch(batch_number="B-A", batch_date=D3, shift="A", expected_output_quantity=5, created_at=T10)
    d = mk_batch(batch_number="B-N", batch_date=D2, created_at=T12)
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] BAT-GW-16
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the rows have no fixed order; which row is on which page rests on physical row order)",
)
def test_bat_gw_16__rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_batch):
    """BAT-GW-16 — rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R3 [BUG-1321], R4"""
    seqscan(db)
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D3)
    c = mk_batch(batch_number="B-C", batch_date=D3)
    d = mk_batch(batch_number="B-D", batch_date=D3)
    e = mk_batch(batch_number="B-E", batch_date=D3)
    a.notes = "Changed"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] BAT-GW-17
def test_bat_gw_17__the_later_date_comes_first_whatever_the_ids(db, w1, mk_batch):
    """BAT-GW-17 — the later date comes first, whatever the ids.
    Rules: `get_by_workspace` R3a"""
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] BAT-GW-18
def test_bat_gw_18__an_older_date_with_the_higher_id_comes_after(db, w1, mk_batch):
    """BAT-GW-18 — an older date with the higher id comes after.
    Rules: `get_by_workspace` R3a"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] BAT-GW-19
def test_bat_gw_19__the_order_is_applied_before_the_page_is_cut(db, w1, mk_batch):
    """BAT-GW-19 — the order is applied before the page is cut.
    Rules: `get_by_workspace` R3a"""
    mk_batch(batch_number="B-A", batch_date=D3)
    mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] BAT-GW-20
def test_bat_gw_20__with_the_defaults_101_rows_give_100(db, w1, new_batch):
    """BAT-GW-20 — with the defaults 101 rows give 100.
    Rules: `get_by_workspace` R4"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] BAT-GW-21
def test_bat_gw_21__limit_1000_gives_all_101(db, w1, new_batch):
    """BAT-GW-21 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R4"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] BAT-GW-22
def test_bat_gw_22__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_batch):
    """BAT-GW-22 — skip and limit cut one row from the middle.
    Rules: `get_by_workspace` R4"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    mk_batch(batch_number="B-C", batch_date=D3)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GW-23
def test_bat_gw_23__limit_0_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GW-23 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] BAT-GW-24
def test_bat_gw_24__limit_1_returns_one_row(db, w1, mk_batch):
    """BAT-GW-24 — limit=1 returns one row.
    Rules: `get_by_workspace` R5"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] BAT-GW-25
def test_bat_gw_25__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GW-25 — skip at the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GW-26
def test_bat_gw_26__skip_at_the_last_row_returns_one_row(db, w1, mk_batch):
    """BAT-GW-26 — skip at the last row returns one row.
    Rules: `get_by_workspace` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GW-27
def test_bat_gw_27__a_negative_limit_raises(db, w1, mk_batch):
    """BAT-GW-27 — a negative limit raises.
    Rules: `get_by_workspace` R6, Errors row 1"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GW-28
def test_bat_gw_28__a_negative_skip_raises(db, w1, mk_batch):
    """BAT-GW-28 — a negative skip raises.
    Rules: `get_by_workspace` R6, Errors row 2"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GW-29
def test_bat_gw_29__an_unknown_workspace_returns_an_empty_list(db, mk_batch):
    """BAT-GW-29 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] BAT-GW-30
def test_bat_gw_30__a_workspace_with_no_rows_returns_an_empty_list(db, w2, mk_batch):
    """BAT-GW-30 — a workspace with no rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GW-31
def test_bat_gw_31__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, l1, mk_batch, recorder):
    """BAT-GW-31 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D4)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GW-32
def test_bat_gw_32__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_batch):
    """BAT-GW-32 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    b.notes = "Edited"

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GW-33
def test_bat_gw_33__another_workspace_s_row_sorts_first_and_takes_no_place_in_the_page(db, w1, w2, l9, mk_batch):
    """BAT-GW-33 — another workspace's row sorts first and takes no place in the page.
    Rules: `get_by_workspace` R1"""
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D5)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.get_by_production_line
# --------------------------------------------------------------------------- #


# [claude] BAT-GL-01
def test_bat_gl_01__returns_a_list_of_the_line_s_batches(db, w1, l1, mk_batch):
    """BAT-GL-01 — returns a list of the line's batches.
    Rules: `get_by_production_line` R1, Returns"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionBatch)


# [claude] BAT-GL-02
def test_bat_gl_02__a_newer_batch_of_another_line_is_not_returned(db, w1, l1, l2, mk_batch):
    """BAT-GL-02 — a newer batch of another line is not returned.
    Rules: `get_by_production_line` R1"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=l2.id)
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GL-03
def test_bat_gl_03__the_right_line_under_another_workspace_returns_an_empty_list(db, w2, l1, mk_batch):
    """BAT-GL-03 — the right line under another workspace returns an empty list.
    Rules: `get_by_production_line` R1"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-04
def test_bat_gl_04__a_w2_row_on_a_w1_line_is_returned_for_w2(db, w2, l1, mk_batch):
    """BAT-GL-04 — a W2 row on a W1 line is returned for W2.
    Rules: `get_by_production_line` R1"""
    a = mk_batch(batch_number="B-A", batch_date=D5, workspace_id=w2.id)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w2.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GL-05
def test_bat_gl_05__a_w2_row_on_a_w1_line_is_not_returned_for_w1(db, w1, w2, l1, mk_batch):
    """BAT-GL-05 — a W2 row on a W1 line is not returned for W1.
    Rules: `get_by_production_line` R1"""
    mk_batch(batch_number="B-A", batch_date=D5, workspace_id=w2.id)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-06
def test_bat_gl_06__a_batch_of_an_inactive_line_is_returned(db, w1, ln, mk_batch):
    """BAT-GL-06 — a batch of an inactive line is returned.
    Rules: `get_by_production_line` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, production_line_id=ln.id)

    result = dao.get_by_production_line(db, production_line_id=ln.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GL-07
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gl_07__a_batch_of_a_soft_deleted_factory_is_not_returned(db, w1, ld, mk_batch):
    """BAT-GL-07 — a batch of a soft-deleted factory is not returned.
    Rules: `get_by_production_line` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=ld.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-08
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gl_08__a_w2_batch_on_a_line_of_a_soft_deleted_w1_factory_is_hidden_too(db, w2, ld, mk_batch):
    """BAT-GL-08 — a W2 batch on a line of a soft-deleted W1 factory is hidden too.
    Rules: `get_by_production_line` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id, workspace_id=w2.id)

    result = dao.get_by_production_line(db, production_line_id=ld.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-09
def test_bat_gl_09__reading_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, ld, mk_batch, recorder):
    """BAT-GL-09 — reading with a soft-deleted factory changes nothing.
    Rules: `get_by_production_line` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    before_x = snap(db, x)
    before_ld = snap(db, ld)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_production_line(db, production_line_id=ld.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, ld) == before_ld
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert recorder.written() == []


# [claude] BAT-GL-10
def test_bat_gl_10__an_inactive_factory_hides_nothing(db, w1, li, mk_batch):
    """BAT-GL-10 — an inactive factory hides nothing.
    Rules: `get_by_production_line` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=li.id)

    result = dao.get_by_production_line(db, production_line_id=li.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] BAT-GL-11
def test_bat_gl_11__once_the_factory_is_live_again_the_batch_is_back_unchanged(db, w1, fd, ld, mk_batch):
    """BAT-GL-11 — once the factory is live again the batch is back, unchanged.
    Rules: `get_by_production_line` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_production_line(db, production_line_id=ld.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] BAT-GL-12
def test_bat_gl_12__an_unknown_line_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GL-12 — an unknown line returns an empty list.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_production_line(db, production_line_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-13
def test_bat_gl_13__production_line_id_0_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GL-13 — production_line_id=0 returns an empty list.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_production_line(db, production_line_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-14
def test_bat_gl_14__a_line_with_no_batches_returns_an_empty_list(db, w1, l2, mk_batch):
    """BAT-GL-14 — a line with no batches returns an empty list.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_production_line(db, production_line_id=l2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GL-15
@pytest.mark.xfail(strict=True, reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order")
def test_bat_gl_15__the_query_orders_by_batch_date_then_id_both_descending(db, w1, l1, mk_batch, recorder):
    """BAT-GL-15 — the query orders by batch_date, then id, both descending.
    Rules: `get_by_production_line` R4 [BUG-1321]"""
    a = mk_batch(batch_number="B-A", batch_date=D5)

    recorder.start()
    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "batch_date" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("batch_date") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] BAT-GL-16
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gl_16__on_a_tied_date_the_highest_id_comes_first_when_the_lowest_ids_were_upd(db, w1, l1, mk_batch):
    """BAT-GL-16 — on a tied date the highest id comes first, when the lowest ids were updated.
    Rules: `get_by_production_line` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D3)
    c = mk_batch(batch_number="B-C", batch_date=D3)
    d = mk_batch(batch_number="B-D", batch_date=D3)
    a.notes = "Changed"
    b.notes = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] BAT-GL-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gl_17__on_a_tied_date_the_id_decides_when_number_shift_quantity_and_stamp_wou(db, w1, l1, mk_batch):
    """BAT-GL-17 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id.
    Rules: `get_by_production_line` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-M", batch_date=D3, shift="B", expected_output_quantity=7, created_at=T11)
    b = mk_batch(batch_number="B-Z", batch_date=D3, shift="C", expected_output_quantity=9, created_at=T9)
    c = mk_batch(batch_number="B-A", batch_date=D3, shift="A", expected_output_quantity=5, created_at=T10)
    d = mk_batch(batch_number="B-N", batch_date=D2, created_at=T12)
    db.expire_all()

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] BAT-GL-18
def test_bat_gl_18__the_later_date_comes_first_whatever_the_ids(db, w1, l1, mk_batch):
    """BAT-GL-18 — the later date comes first, whatever the ids.
    Rules: `get_by_production_line` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] BAT-GL-19
def test_bat_gl_19__an_older_date_with_the_higher_id_comes_after(db, w1, l1, mk_batch):
    """BAT-GL-19 — an older date with the higher id comes after.
    Rules: `get_by_production_line` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] BAT-GL-20
def test_bat_gl_20__the_order_is_applied_before_the_page_is_cut(db, w1, l1, mk_batch):
    """BAT-GL-20 — the order is applied before the page is cut.
    Rules: `get_by_production_line` R4"""
    mk_batch(batch_number="B-A", batch_date=D3)
    mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] BAT-GL-21
def test_bat_gl_21__the_line_filter_runs_before_the_page_skip_2_past_the_two_visible_rows_(db, w1, l1, l2, mk_batch):
    """BAT-GL-21 — the line filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_production_line` R1"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=l2.id)
    mk_batch(batch_number="B-A", batch_date=D4)
    mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GL-22
def test_bat_gl_22__the_line_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, l1, l2, mk_batch):
    """BAT-GL-22 — the line filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_production_line` R1"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=l2.id)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert x.id not in ids(result)


# [claude] BAT-GL-23
def test_bat_gl_23__with_the_defaults_101_rows_give_100(db, w1, l1, new_batch):
    """BAT-GL-23 — with the defaults 101 rows give 100.
    Rules: `get_by_production_line` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] BAT-GL-24
def test_bat_gl_24__limit_1000_gives_all_101(db, w1, l1, new_batch):
    """BAT-GL-24 — limit=1000 gives all 101.
    Rules: `get_by_production_line` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] BAT-GL-25
def test_bat_gl_25__skip_and_limit_cut_one_row_from_the_middle(db, w1, l1, mk_batch):
    """BAT-GL-25 — skip and limit cut one row from the middle.
    Rules: `get_by_production_line` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    mk_batch(batch_number="B-C", batch_date=D3)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GL-26
def test_bat_gl_26__limit_0_returns_an_empty_list(db, w1, l1, mk_batch):
    """BAT-GL-26 — limit=0 returns an empty list.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] BAT-GL-27
def test_bat_gl_27__limit_1_returns_one_row(db, w1, l1, mk_batch):
    """BAT-GL-27 — limit=1 returns one row.
    Rules: `get_by_production_line` R3"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] BAT-GL-28
def test_bat_gl_28__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, l1, mk_batch):
    """BAT-GL-28 — skip at the number of rows returns an empty list.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GL-29
def test_bat_gl_29__skip_at_the_last_row_returns_one_row(db, w1, l1, mk_batch):
    """BAT-GL-29 — skip at the last row returns one row.
    Rules: `get_by_production_line` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GL-30
def test_bat_gl_30__a_negative_limit_raises(db, w1, l1, mk_batch):
    """BAT-GL-30 — a negative limit raises.
    Rules: `get_by_production_line` R6, Errors row 1"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GL-31
def test_bat_gl_31__a_negative_skip_raises(db, w1, l1, mk_batch):
    """BAT-GL-31 — a negative skip raises.
    Rules: `get_by_production_line` R6, Errors row 2"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GL-32
def test_bat_gl_32__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, l1, mk_batch, recorder):
    """BAT-GL-32 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_production_line` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D4)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GL-33
def test_bat_gl_33__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, l1, mk_batch):
    """BAT-GL-33 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_production_line` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    b.notes = "Edited"

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GL-34
def test_bat_gl_34__another_workspace_s_row_sorts_first_and_takes_no_place_in_the_page(db, w1, w2, l1, mk_batch):
    """BAT-GL-34 — another workspace's row sorts first and takes no place in the page.
    Rules: `get_by_production_line` R1"""
    mk_batch(batch_number="B-Z", batch_date=D5, workspace_id=w2.id)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_production_line(db, production_line_id=l1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.get_by_formula
# --------------------------------------------------------------------------- #


# [claude] BAT-GF-01
def test_bat_gf_01__returns_a_list_of_the_formula_s_batches(db, w1, pf1, mk_batch):
    """BAT-GF-01 — returns a list of the formula's batches.
    Rules: `get_by_formula` R1, Returns"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionBatch)


# [claude] BAT-GF-02
def test_bat_gf_02__a_newer_batch_of_another_formula_is_not_returned(db, w1, pf1, pf2, mk_batch):
    """BAT-GF-02 — a newer batch of another formula is not returned.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf2.id)
    a = mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GF-03
def test_bat_gf_03__a_batch_with_no_formula_is_never_returned(db, w1, pf1, mk_batch):
    """BAT-GF-03 — a batch with no formula is never returned.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-X", batch_date=D5)
    a = mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GF-04
def test_bat_gf_04__another_workspace_returns_an_empty_list(db, w2, pf1, mk_batch):
    """BAT-GF-04 — another workspace returns an empty list.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GF-05
def test_bat_gf_05__a_batch_of_an_inactive_formula_is_returned(db, w1, pfd, mk_batch):
    """BAT-GF-05 — a batch of an inactive formula is returned.
    Rules: `get_by_formula` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pfd.id)

    result = dao.get_by_formula(db, formula_id=pfd.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GF-06
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gf_06__a_batch_of_a_soft_deleted_factory_is_not_returned(db, w1, ld, pf1, mk_batch):
    """BAT-GF-06 — a batch of a soft-deleted factory is not returned.
    Rules: `get_by_formula` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=ld.id)
    a = mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GF-07
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gf_07__a_w2_batch_on_a_line_of_a_soft_deleted_w1_factory_is_hidden_too(db, w2, ld, pf1, mk_batch):
    """BAT-GF-07 — a W2 batch on a line of a soft-deleted W1 factory is hidden too.
    Rules: `get_by_formula` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=ld.id, workspace_id=w2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GF-08
def test_bat_gf_08__reading_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, ld, pf1, mk_batch, recorder):
    """BAT-GF-08 — reading with a soft-deleted factory changes nothing.
    Rules: `get_by_formula` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=ld.id)
    before_x = snap(db, x)
    before_ld = snap(db, ld)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, ld) == before_ld
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert recorder.written() == []


# [claude] BAT-GF-09
def test_bat_gf_09__an_inactive_factory_hides_nothing(db, w1, li, pf1, mk_batch):
    """BAT-GF-09 — an inactive factory hides nothing.
    Rules: `get_by_formula` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=li.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] BAT-GF-10
def test_bat_gf_10__once_the_factory_is_live_again_the_batch_is_back_unchanged(db, w1, fd, ld, pf1, mk_batch):
    """BAT-GF-10 — once the factory is live again the batch is back, unchanged.
    Rules: `get_by_formula` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=ld.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] BAT-GF-11
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gf_11__a_hidden_batch_takes_no_place_in_the_page(db, w1, ld, pf1, mk_batch):
    """BAT-GF-11 — a hidden batch takes no place in the page.
    Rules: `get_by_formula` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf1.id, production_line_id=ld.id)
    mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D3, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GF-12
def test_bat_gf_12__an_unknown_formula_returns_an_empty_list(db, w1, pf1, mk_batch):
    """BAT-GF-12 — an unknown formula returns an empty list.
    Rules: `get_by_formula` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GF-13
def test_bat_gf_13__formula_id_0_returns_an_empty_list(db, w1, pf1, mk_batch):
    """BAT-GF-13 — formula_id=0 returns an empty list.
    Rules: `get_by_formula` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GF-14
@pytest.mark.xfail(strict=True, reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order")
def test_bat_gf_14__the_query_orders_by_batch_date_then_id_both_descending(db, w1, pf1, mk_batch, recorder):
    """BAT-GF-14 — the query orders by batch_date, then id, both descending.
    Rules: `get_by_formula` R4 [BUG-1321]"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "batch_date" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("batch_date") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] BAT-GF-15
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gf_15__on_a_tied_date_the_highest_id_comes_first_when_the_lowest_ids_were_upd(db, w1, pf1, mk_batch):
    """BAT-GF-15 — on a tied date the highest id comes first, when the lowest ids were updated.
    Rules: `get_by_formula` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-A", batch_date=D3, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D3, formula_id=pf1.id)
    c = mk_batch(batch_number="B-C", batch_date=D3, formula_id=pf1.id)
    d = mk_batch(batch_number="B-D", batch_date=D3, formula_id=pf1.id)
    a.notes = "Changed"
    b.notes = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] BAT-GF-16
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gf_16__on_a_tied_date_the_id_decides_when_number_shift_quantity_and_stamp_wou(db, w1, pf1, mk_batch):
    """BAT-GF-16 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id.
    Rules: `get_by_formula` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-M", batch_date=D3, formula_id=pf1.id, shift="B", expected_output_quantity=7, created_at=T11)
    b = mk_batch(batch_number="B-Z", batch_date=D3, formula_id=pf1.id, shift="C", expected_output_quantity=9, created_at=T9)
    c = mk_batch(batch_number="B-A", batch_date=D3, formula_id=pf1.id, shift="A", expected_output_quantity=5, created_at=T10)
    d = mk_batch(batch_number="B-N", batch_date=D2, formula_id=pf1.id, created_at=T12)
    db.expire_all()

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] BAT-GF-17
def test_bat_gf_17__the_later_date_comes_first_whatever_the_ids(db, w1, pf1, mk_batch):
    """BAT-GF-17 — the later date comes first, whatever the ids.
    Rules: `get_by_formula` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D3, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D5, formula_id=pf1.id)
    c = mk_batch(batch_number="B-C", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] BAT-GF-18
def test_bat_gf_18__an_older_date_with_the_higher_id_comes_after(db, w1, pf1, mk_batch):
    """BAT-GF-18 — an older date with the higher id comes after.
    Rules: `get_by_formula` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] BAT-GF-19
def test_bat_gf_19__the_order_is_applied_before_the_page_is_cut(db, w1, pf1, mk_batch):
    """BAT-GF-19 — the order is applied before the page is cut.
    Rules: `get_by_formula` R4"""
    mk_batch(batch_number="B-A", batch_date=D3, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D5, formula_id=pf1.id)
    c = mk_batch(batch_number="B-C", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] BAT-GF-20
def test_bat_gf_20__the_formula_filter_runs_before_the_page_skip_2_past_the_two_visible_ro(db, w1, pf1, pf2, mk_batch):
    """BAT-GF-20 — the formula filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf2.id)
    mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D3, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GF-21
def test_bat_gf_21__the_formula_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, pf1, pf2, mk_batch):
    """BAT-GF-21 — the formula filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_formula` R1"""
    x = mk_batch(batch_number="B-X", batch_date=D5, formula_id=pf2.id)
    mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D3, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert x.id not in ids(result)


# [claude] BAT-GF-22
def test_bat_gf_22__with_the_defaults_101_rows_give_100(db, w1, pf1, new_batch):
    """BAT-GF-22 — with the defaults 101 rows give 100.
    Rules: `get_by_formula` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k), formula_id=pf1.id) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] BAT-GF-23
def test_bat_gf_23__limit_1000_gives_all_101(db, w1, pf1, new_batch):
    """BAT-GF-23 — limit=1000 gives all 101.
    Rules: `get_by_formula` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k), formula_id=pf1.id) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] BAT-GF-24
def test_bat_gf_24__skip_and_limit_cut_one_row_from_the_middle(db, w1, pf1, mk_batch):
    """BAT-GF-24 — skip and limit cut one row from the middle.
    Rules: `get_by_formula` R5"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)
    mk_batch(batch_number="B-C", batch_date=D3, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GF-25
def test_bat_gf_25__limit_0_returns_an_empty_list(db, w1, pf1, mk_batch):
    """BAT-GF-25 — limit=0 returns an empty list.
    Rules: `get_by_formula` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] BAT-GF-26
def test_bat_gf_26__limit_1_returns_one_row(db, w1, pf1, mk_batch):
    """BAT-GF-26 — limit=1 returns one row.
    Rules: `get_by_formula` R3"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] BAT-GF-27
def test_bat_gf_27__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, pf1, mk_batch):
    """BAT-GF-27 — skip at the number of rows returns an empty list.
    Rules: `get_by_formula` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GF-28
def test_bat_gf_28__skip_at_the_last_row_returns_one_row(db, w1, pf1, mk_batch):
    """BAT-GF-28 — skip at the last row returns one row.
    Rules: `get_by_formula` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GF-29
def test_bat_gf_29__a_negative_limit_raises(db, w1, pf1, mk_batch):
    """BAT-GF-29 — a negative limit raises.
    Rules: `get_by_formula` R6, Errors row 1"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GF-30
def test_bat_gf_30__a_negative_skip_raises(db, w1, pf1, mk_batch):
    """BAT-GF-30 — a negative skip raises.
    Rules: `get_by_formula` R6, Errors row 2"""
    mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GF-31
def test_bat_gf_31__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, l1, pf1, mk_batch, recorder):
    """BAT-GF-31 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_formula` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft", formula_id=pf1.id)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GF-32
def test_bat_gf_32__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, pf1, mk_batch):
    """BAT-GF-32 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_formula` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D4, formula_id=pf1.id)
    b.notes = "Edited"

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GF-33
def test_bat_gf_33__another_workspace_s_row_sorts_first_and_takes_no_place_in_the_page(db, w1, w2, l9, pf1, mk_batch):
    """BAT-GF-33 — another workspace's row sorts first and takes no place in the page.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-Z", batch_date=D5, formula_id=pf1.id, workspace_id=w2.id, production_line_id=l9.id)
    mk_batch(batch_number="B-A", batch_date=D4, formula_id=pf1.id)
    b = mk_batch(batch_number="B-B", batch_date=D3, formula_id=pf1.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GF-34
def test_bat_gf_34__a_w2_batch_on_the_formula_is_not_returned_for_w1(db, w1, w2, l9, pf1, mk_batch):
    """BAT-GF-34 — a W2 batch on the formula is not returned for W1.
    Rules: `get_by_formula` R1"""
    mk_batch(batch_number="B-Z", batch_date=D5, formula_id=pf1.id, workspace_id=w2.id, production_line_id=l9.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.get_by_status
# --------------------------------------------------------------------------- #


# [claude] BAT-GS-01
def test_bat_gs_01__returns_a_list_of_the_batches_in_that_status(db, w1, mk_batch):
    """BAT-GS-01 — returns a list of the batches in that status.
    Rules: `get_by_status` R1, Returns"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-X", batch_date=D4, status="completed")
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionBatch)


# [claude] BAT-GS-02
def test_bat_gs_02__the_same_status_in_another_workspace_is_not_returned(db, w1, w2, l9, mk_batch):
    """BAT-GS-02 — the same status in another workspace is not returned.
    Rules: `get_by_status` R1"""
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D5)
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GS-03
def test_bat_gs_03__a_batch_of_an_inactive_line_is_returned(db, w1, ln, mk_batch):
    """BAT-GS-03 — a batch of an inactive line is returned.
    Rules: `get_by_status` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, production_line_id=ln.id)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GS-04
def test_bat_gs_04__a_batch_of_an_inactive_formula_is_returned(db, w1, pfd, mk_batch):
    """BAT-GS-04 — a batch of an inactive formula is returned.
    Rules: `get_by_status` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5, formula_id=pfd.id)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GS-05
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gs_05__a_batch_of_a_soft_deleted_factory_is_not_returned(db, w1, ld, mk_batch):
    """BAT-GS-05 — a batch of a soft-deleted factory is not returned.
    Rules: `get_by_status` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    a = mk_batch(batch_number="B-A", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GS-06
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gs_06__a_w2_batch_on_a_line_of_a_soft_deleted_w1_factory_is_hidden_too(db, w2, ld, mk_batch):
    """BAT-GS-06 — a W2 batch on a line of a soft-deleted W1 factory is hidden too.
    Rules: `get_by_status` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id, workspace_id=w2.id)

    result = dao.get_by_status(db, status="draft", workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-07
def test_bat_gs_07__reading_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, ld, mk_batch, recorder):
    """BAT-GS-07 — reading with a soft-deleted factory changes nothing.
    Rules: `get_by_status` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    before_x = snap(db, x)
    before_ld = snap(db, ld)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, ld) == before_ld
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert recorder.written() == []


# [claude] BAT-GS-08
def test_bat_gs_08__an_inactive_factory_hides_nothing(db, w1, li, mk_batch):
    """BAT-GS-08 — an inactive factory hides nothing.
    Rules: `get_by_status` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=li.id)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]


# [claude] BAT-GS-09
def test_bat_gs_09__once_the_factory_is_live_again_the_batch_is_back_unchanged(db, w1, fd, ld, mk_batch):
    """BAT-GS-09 — once the factory is live again the batch is back, unchanged.
    Rules: `get_by_status` R2a"""
    x = mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [x.id]
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] BAT-GS-10
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_gs_10__a_hidden_batch_takes_no_place_in_the_page(db, w1, ld, mk_batch):
    """BAT-GS-10 — a hidden batch takes no place in the page.
    Rules: `get_by_status` R2a [BUG-1330]"""
    mk_batch(batch_number="B-X", batch_date=D5, production_line_id=ld.id)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GS-11
def test_bat_gs_11__a_status_in_capitals_finds_nothing(db, w1, mk_batch):
    """BAT-GS-11 — a status in capitals finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="DRAFT", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-12
def test_bat_gs_12__a_leading_space_in_the_status_finds_nothing(db, w1, mk_batch):
    """BAT-GS-12 — a leading space in the status finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status=" draft", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-13
def test_bat_gs_13__the_start_of_a_status_finds_nothing(db, w1, mk_batch):
    """BAT-GS-13 — the start of a status finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="dra", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-14
def test_bat_gs_14__the_end_of_a_status_finds_nothing(db, w1, mk_batch):
    """BAT-GS-14 — the end of a status finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="aft", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-15
def test_bat_gs_15__is_no_wildcard_in_a_status(db, w1, mk_batch):
    """BAT-GS-15 — _ is no wildcard in a status.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="dr_ft", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-16
def test_bat_gs_16__is_no_wildcard_in_a_status(db, w1, mk_batch):
    """BAT-GS-16 — % is no wildcard in a status.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="%", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-17
def test_bat_gs_17__an_unknown_status_finds_nothing(db, w1, mk_batch):
    """BAT-GS-17 — an unknown status finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="nope", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-18
def test_bat_gs_18__the_status_finds_nothing(db, w1, mk_batch):
    """BAT-GS-18 — the status "" finds nothing.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-19
def test_bat_gs_19__a_stored_status_with_a_space_is_not_found_the_stored_side_is_not_trimm(db, w1, mk_batch):
    """BAT-GS-19 — a stored status with a space is not found: the stored side is not trimmed.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, status=" draft")

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-20
def test_bat_gs_20__a_stored_status_in_capitals_is_not_found(db, w1, mk_batch):
    """BAT-GS-20 — a stored status in capitals is not found.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5, status="DRAFT")

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] BAT-GS-21
def test_bat_gs_21__a_status_outside_the_four_is_matched_like_any_other(db, w1, mk_batch):
    """BAT-GS-21 — a status outside the four is matched like any other.
    Rules: `get_by_status` R3"""
    a = mk_batch(batch_number="B-A", batch_date=D5, status="weird")

    result = dao.get_by_status(db, status="weird", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] BAT-GS-22
@pytest.mark.xfail(strict=True, reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order")
def test_bat_gs_22__the_query_orders_by_batch_date_then_id_both_descending(db, w1, mk_batch, recorder):
    """BAT-GS-22 — the query orders by batch_date, then id, both descending.
    Rules: `get_by_status` R4 [BUG-1321]"""
    a = mk_batch(batch_number="B-A", batch_date=D5)

    recorder.start()
    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    sql = recorder.sql()
    order_part = order_part_of(sql)
    assert "ORDER BY" in sql
    # Then 3
    assert "batch_date" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("batch_date") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] BAT-GS-23
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gs_23__on_a_tied_date_the_highest_id_comes_first_when_the_lowest_ids_were_upd(db, w1, mk_batch):
    """BAT-GS-23 — on a tied date the highest id comes first, when the lowest ids were updated.
    Rules: `get_by_status` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D3)
    c = mk_batch(batch_number="B-C", batch_date=D3)
    d = mk_batch(batch_number="B-D", batch_date=D3)
    a.notes = "Changed"
    b.notes = "Changed"
    db.flush()
    db.expire_all()

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] BAT-GS-24
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1321: Batch lists ordered by date alone; batches of one date in no fixed order "
    "(non-strict: the result rests on physical row order, which can match the intended one by accident)",
)
def test_bat_gs_24__on_a_tied_date_the_id_decides_when_number_shift_quantity_and_stamp_wou(db, w1, mk_batch):
    """BAT-GS-24 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id.
    Rules: `get_by_status` R4 [BUG-1321]"""
    seqscan(db)
    a = mk_batch(batch_number="B-M", batch_date=D3, shift="B", expected_output_quantity=7, created_at=T11)
    b = mk_batch(batch_number="B-Z", batch_date=D3, shift="C", expected_output_quantity=9, created_at=T9)
    c = mk_batch(batch_number="B-A", batch_date=D3, shift="A", expected_output_quantity=5, created_at=T10)
    d = mk_batch(batch_number="B-N", batch_date=D2, created_at=T12)
    db.expire_all()

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] BAT-GS-25
def test_bat_gs_25__the_later_date_comes_first_whatever_the_ids(db, w1, mk_batch):
    """BAT-GS-25 — the later date comes first, whatever the ids.
    Rules: `get_by_status` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D3)
    b = mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] BAT-GS-26
def test_bat_gs_26__an_older_date_with_the_higher_id_comes_after(db, w1, mk_batch):
    """BAT-GS-26 — an older date with the higher id comes after.
    Rules: `get_by_status` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] BAT-GS-27
def test_bat_gs_27__the_order_is_applied_before_the_page_is_cut(db, w1, mk_batch):
    """BAT-GS-27 — the order is applied before the page is cut.
    Rules: `get_by_status` R4"""
    mk_batch(batch_number="B-A", batch_date=D3)
    mk_batch(batch_number="B-B", batch_date=D5)
    c = mk_batch(batch_number="B-C", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] BAT-GS-28
def test_bat_gs_28__the_status_filter_runs_before_the_page_skip_2_past_the_two_visible_row(db, w1, mk_batch):
    """BAT-GS-28 — the status filter runs before the page: skip=2 past the two visible rows gives nothing.
    Rules: `get_by_status` R1"""
    mk_batch(batch_number="B-X", batch_date=D5, status="completed")
    mk_batch(batch_number="B-A", batch_date=D4)
    mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GS-29
def test_bat_gs_29__the_status_filter_runs_before_the_page_skip_1_leaves_one_visible_row(db, w1, mk_batch):
    """BAT-GS-29 — the status filter runs before the page: skip=1 leaves one visible row.
    Rules: `get_by_status` R1"""
    x = mk_batch(batch_number="B-X", batch_date=D5, status="completed")
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert x.id not in ids(result)


# [claude] BAT-GS-30
def test_bat_gs_30__with_the_defaults_101_rows_give_100(db, w1, new_batch):
    """BAT-GS-30 — with the defaults 101 rows give 100.
    Rules: `get_by_status` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] BAT-GS-31
def test_bat_gs_31__limit_1000_gives_all_101(db, w1, new_batch):
    """BAT-GS-31 — limit=1000 gives all 101.
    Rules: `get_by_status` R5"""
    rows = [new_batch(batch_number=f"B-{k}", batch_date=D1 + timedelta(days=k)) for k in range(1, 102)]
    add_many(db, rows)
    newest = [row.id for row in reversed(rows)]

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] BAT-GS-32
def test_bat_gs_32__skip_and_limit_cut_one_row_from_the_middle(db, w1, mk_batch):
    """BAT-GS-32 — skip and limit cut one row from the middle.
    Rules: `get_by_status` R5"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    mk_batch(batch_number="B-C", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GS-33
def test_bat_gs_33__limit_0_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GS-33 — limit=0 returns an empty list.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] BAT-GS-34
def test_bat_gs_34__limit_1_returns_one_row(db, w1, mk_batch):
    """BAT-GS-34 — limit=1 returns one row.
    Rules: `get_by_status` R3"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] BAT-GS-35
def test_bat_gs_35__skip_at_the_number_of_rows_returns_an_empty_list(db, w1, mk_batch):
    """BAT-GS-35 — skip at the number of rows returns an empty list.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] BAT-GS-36
def test_bat_gs_36__skip_at_the_last_row_returns_one_row(db, w1, mk_batch):
    """BAT-GS-36 — skip at the last row returns one row.
    Rules: `get_by_status` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GS-37
def test_bat_gs_37__a_negative_limit_raises(db, w1, mk_batch):
    """BAT-GS-37 — a negative limit raises.
    Rules: `get_by_status` R6, Errors row 1"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(db, status="draft", workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GS-38
def test_bat_gs_38__a_negative_skip_raises(db, w1, mk_batch):
    """BAT-GS-38 — a negative skip raises.
    Rules: `get_by_status` R6, Errors row 2"""
    mk_batch(batch_number="B-A", batch_date=D5)
    mk_batch(batch_number="B-B", batch_date=D4)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] BAT-GS-39
def test_bat_gs_39__writes_nothing_a_pending_row_that_would_sort_first_stays_pending_and_i(db, w1, l1, mk_batch, recorder):
    """BAT-GS-39 — writes nothing: a pending row that would sort first stays pending and is not returned.
    Rules: `get_by_status` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D4)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GS-40
def test_bat_gs_40__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_batch):
    """BAT-GS-40 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_status` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    b.notes = "Edited"

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GS-41
def test_bat_gs_41__another_workspace_s_row_sorts_first_and_takes_no_place_in_the_page(db, w1, w2, l9, mk_batch):
    """BAT-GS-41 — another workspace's row sorts first and takes no place in the page.
    Rules: `get_by_status` R1"""
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D5)
    mk_batch(batch_number="B-A", batch_date=D4)
    b = mk_batch(batch_number="B-B", batch_date=D3)

    result = dao.get_by_status(db, status="draft", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] BAT-GS-42
def test_bat_gs_42__a_w1_batch_is_not_returned_for_w2(db, w2, mk_batch):
    """BAT-GS-42 — a W1 batch is not returned for W2.
    Rules: `get_by_status` R1"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_status(db, status="draft", workspace_id=w2.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.count_by_status
# --------------------------------------------------------------------------- #


# [claude] BAT-CS-01
def test_bat_cs_01__with_no_factory_counts_the_rows_of_that_workspace_and_status(db, w1, lf, mk_batch):
    """BAT-CS-01 — with no factory, counts the rows of that workspace and status.
    Rules: `count_by_status` R1, Returns"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-B", status="in_progress", production_line_id=lf.id)
    mk_batch(batch_number="B-X")
    mk_batch(batch_number="B-Y", status="completed")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 2
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-02
def test_bat_cs_02__rows_of_another_workspace_are_not_counted(db, w1, w2, l9, mk_batch):
    """BAT-CS-02 — rows of another workspace are not counted.
    Rules: `count_by_status` R1"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-03
def test_bat_cs_03__there_is_no_cap_101_rows_give_101(db, w1, new_batch):
    """BAT-CS-03 — there is no cap: 101 rows give 101.
    Rules: `count_by_status` R1"""
    rows = [new_batch(batch_number=f"B-{k}", status="in_progress") for k in range(1, 102)]
    add_many(db, rows)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 101
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-04
def test_bat_cs_04__with_a_factory_counts_only_the_batches_of_that_factory_s_lines(db, w1, f1, l2, lf, mk_batch):
    """BAT-CS-04 — with a factory, counts only the batches of that factory's lines.
    Rules: `count_by_status` R2"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-B", status="in_progress", production_line_id=l2.id)
    mk_batch(batch_number="B-X", status="in_progress", production_line_id=lf.id)
    mk_batch(batch_number="B-Y")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=f1.id)

    # Then 1
    assert result == 2
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-05
def test_bat_cs_05__factory_id_0_is_a_filter_0(db, w1, mk_batch):
    """BAT-CS-05 — factory_id=0 is a filter: 0.
    Rules: `count_by_status` R2"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=0)

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-06
def test_bat_cs_06__an_unknown_factory_gives_0(db, w1, mk_batch):
    """BAT-CS-06 — an unknown factory gives 0.
    Rules: `count_by_status` R2"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=MISSING)

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-07
def test_bat_cs_07__a_factory_with_no_matching_batch_gives_0(db, w1, f2, lf, mk_batch):
    """BAT-CS-07 — a factory with no matching batch gives 0.
    Rules: `count_by_status` R2"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-X", production_line_id=lf.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=f2.id)

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-08
def test_bat_cs_08__no_match_gives_0_never_none(db, w1, mk_batch):
    """BAT-CS-08 — no match gives 0, never None.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-X")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-09
def test_bat_cs_09__an_unknown_workspace_gives_0(db, mk_batch):
    """BAT-CS-09 — an unknown workspace gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=MISSING, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-10
def test_bat_cs_10__an_unknown_status_gives_0(db, w1, mk_batch):
    """BAT-CS-10 — an unknown status gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="nope")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-11
def test_bat_cs_11__a_status_in_capitals_gives_0(db, w1, mk_batch):
    """BAT-CS-11 — a status in capitals gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="IN_PROGRESS")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-12
def test_bat_cs_12__a_leading_space_gives_0(db, w1, mk_batch):
    """BAT-CS-12 — a leading space gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status=" in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-13
def test_bat_cs_13__a_part_of_the_status_gives_0(db, w1, mk_batch):
    """BAT-CS-13 — a part of the status gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_prog")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-14
def test_bat_cs_14__is_no_wildcard(db, w1, mk_batch):
    """BAT-CS-14 — % is no wildcard.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in%progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-15
def test_bat_cs_15__another_separator_gives_0(db, w1, mk_batch):
    """BAT-CS-15 — another separator gives 0.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in-progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-16
def test_bat_cs_16__a_batch_of_an_inactive_line_is_counted_with_no_factory(db, w1, ln, mk_batch):
    """BAT-CS-16 — a batch of an inactive line is counted, with no factory.
    Rules: `count_by_status` R4"""
    mk_batch(batch_number="B-A", status="in_progress", production_line_id=ln.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-17
def test_bat_cs_17__a_batch_of_an_inactive_line_is_counted_with_its_factory(db, w1, f1, ln, mk_batch):
    """BAT-CS-17 — a batch of an inactive line is counted, with its factory.
    Rules: `count_by_status` R4"""
    mk_batch(batch_number="B-A", status="in_progress", production_line_id=ln.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=f1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-18
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_cs_18__a_batch_of_a_soft_deleted_factory_is_not_counted_with_no_factory(db, w1, ld, mk_batch):
    """BAT-CS-18 — a batch of a soft-deleted factory is not counted, with no factory.
    Rules: `count_by_status` R4a [BUG-1330]"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-19
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_cs_19__a_batch_of_a_soft_deleted_factory_is_not_counted_with_that_factory_s_i(db, w1, fd, ld, mk_batch):
    """BAT-CS-19 — a batch of a soft-deleted factory is not counted, with that factory's id.
    Rules: `count_by_status` R4a [BUG-1330]"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=fd.id)

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-20
@pytest.mark.xfail(strict=True, reason="BUG-1330: Batches of a soft-deleted factory are listed and counted")
def test_bat_cs_20__a_w2_batch_on_a_line_of_a_soft_deleted_w1_factory_is_not_counted_for_w(db, w2, ld, mk_batch):
    """BAT-CS-20 — a W2 batch on a line of a soft-deleted W1 factory is not counted for W2.
    Rules: `count_by_status` R4a [BUG-1330]"""
    mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id, workspace_id=w2.id)

    result = dao.count_by_status(db, workspace_id=w2.id, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-21
def test_bat_cs_21__the_count_with_a_live_factory_is_the_same_today_and_after_the_fix(db, w1, f1, ld, mk_batch):
    """BAT-CS-21 — the count with a live factory is the same today and after the fix.
    Rules: `count_by_status` R4a"""
    mk_batch(batch_number="B-A", status="in_progress")
    mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=f1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-22
def test_bat_cs_22__counting_with_a_soft_deleted_factory_changes_nothing(db, w1, fd, ld, mk_batch, recorder):
    """BAT-CS-22 — counting with a soft-deleted factory changes nothing.
    Rules: `count_by_status` R4b"""
    x = mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id)
    before_x = snap(db, x)
    before_ld = snap(db, ld)
    before_fd = snap(db, fd)

    recorder.start()
    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert isinstance(result, int)
    # Then 2
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 3
    assert snap(db, ld) == before_ld
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert recorder.written() == []


# [claude] BAT-CS-23
def test_bat_cs_23__an_inactive_factory_hides_nothing_with_no_factory(db, w1, li, mk_batch):
    """BAT-CS-23 — an inactive factory hides nothing, with no factory.
    Rules: `count_by_status` R4b"""
    mk_batch(batch_number="B-A", status="in_progress", production_line_id=li.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-24
def test_bat_cs_24__an_inactive_factory_hides_nothing_with_its_id(db, w1, fi, li, mk_batch):
    """BAT-CS-24 — an inactive factory hides nothing, with its id.
    Rules: `count_by_status` R4b"""
    mk_batch(batch_number="B-A", status="in_progress", production_line_id=li.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=fi.id)

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-25
def test_bat_cs_25__once_the_factory_is_live_again_the_batch_is_counted(db, w1, fd, ld, mk_batch):
    """BAT-CS-25 — once the factory is live again the batch is counted.
    Rules: `count_by_status` R4b"""
    x = mk_batch(batch_number="B-X", status="in_progress", production_line_id=ld.id)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before_x = snap(db, x)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=fd.id)

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)
    # Then 3
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] BAT-CS-26
def test_bat_cs_26__a_w2_row_on_a_w1_line_is_counted_for_w2_under_the_w1_factory(db, w2, f1, mk_batch):
    """BAT-CS-26 — a W2 row on a W1 line is counted for W2 under the W1 factory.
    Rules: `count_by_status` R5"""
    mk_batch(batch_number="B-A", status="in_progress", workspace_id=w2.id)

    result = dao.count_by_status(db, workspace_id=w2.id, status="in_progress", factory_id=f1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-27
def test_bat_cs_27__a_w2_row_on_a_w1_line_is_not_counted_for_w1(db, w1, w2, f1, mk_batch):
    """BAT-CS-27 — a W2 row on a W1 line is not counted for W1.
    Rules: `count_by_status` R5"""
    mk_batch(batch_number="B-A", status="in_progress", workspace_id=w2.id)

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress", factory_id=f1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-28
def test_bat_cs_28__writes_nothing_a_pending_row_is_not_counted_and_stays_pending(db, w1, l1, mk_batch, recorder):
    """BAT-CS-28 — writes nothing: a pending row is not counted and stays pending.
    Rules: `count_by_status` Side effects"""
    a = mk_batch(batch_number="B-A", status="in_progress")
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=D3, status="in_progress")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-CS-29
def test_bat_cs_29__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_batch):
    """BAT-CS-29 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `count_by_status` Side effects"""
    mk_batch(batch_number="B-A", status="in_progress")
    b = mk_batch(batch_number="B-B", status="in_progress")
    b.notes = "Edited"

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 2
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-CS-30
def test_bat_cs_30__a_stored_status_in_capitals_is_not_counted(db, w1, mk_batch):
    """BAT-CS-30 — a stored status in capitals is not counted.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="IN_PROGRESS")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-31
def test_bat_cs_31__a_stored_status_with_a_leading_space_is_not_counted(db, w1, mk_batch):
    """BAT-CS-31 — a stored status with a leading space is not counted.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status=" in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# [claude] BAT-CS-32
def test_bat_cs_32__a_stored_status_that_ends_with_the_argument_is_not_counted(db, w1, mk_batch):
    """BAT-CS-32 — a stored status that ends with the argument is not counted.
    Rules: `count_by_status` R3"""
    mk_batch(batch_number="B-A", status="not_in_progress")

    result = dao.count_by_status(db, workspace_id=w1.id, status="in_progress")

    # Then 1
    assert result == 0
    # Then 2
    assert isinstance(result, int)


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] BAT-GI-01
def test_bat_gi_01__returns_the_row_with_that_id(db, w1, l1, mk_batch):
    """BAT-GI-01 — returns the row with that id.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_batch(batch_number="B-B", batch_date=D4)
    a = mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, ProductionBatch)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.batch_number == "B-A"
    assert result.workspace_id == w1.id
    assert result.production_line_id == l1.id
    # Then 4
    assert result.batch_date == D5
    assert result.status == "draft"


# [claude] BAT-GI-02
def test_bat_gi_02__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, l9, mk_batch):
    """BAT-GI-02 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R2"""
    mk_batch(batch_number="B-A", batch_date=D5)
    z = mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D4)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BAT-GI-03
def test_bat_gi_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, l9, mk_batch):
    """BAT-GI-03 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_batch(batch_number="B-Z", workspace_id=w2.id, production_line_id=l9.id, batch_date=D4)
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BAT-GI-04
def test_bat_gi_04__the_id_under_another_workspace_returns_none(db, w2, mk_batch):
    """BAT-GI-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] BAT-GI-05
def test_bat_gi_05__an_unknown_id_returns_none(db, w1, mk_batch):
    """BAT-GI-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BAT-GI-06
def test_bat_gi_06__id_0_returns_none(db, w1, mk_batch):
    """BAT-GI-06 — id=0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_batch(batch_number="B-A", batch_date=D5)

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] BAT-GI-07
def test_bat_gi_07__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, l1, mk_batch, recorder):
    """BAT-GI-07 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `get_by_id_and_workspace` R3, Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GI-08
def test_bat_gi_08__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, l1, mk_batch, recorder):
    """BAT-GI-08 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    p = ProductionBatch(workspace_id=w1.id, batch_number="B-P", production_line_id=l1.id, batch_date=date(2026, 3, 9), status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GI-09
def test_bat_gi_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_batch):
    """BAT-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_batch(batch_number="B-A", batch_date=D5)
    b = mk_batch(batch_number="B-B", batch_date=D4)
    b.notes = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GI-10
def test_bat_gi_10__a_cancelled_batch_is_returned(db, w1, mk_batch):
    """BAT-GI-10 — a cancelled batch is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5, status="cancelled")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "cancelled"


# [claude] BAT-GI-11
def test_bat_gi_11__a_batch_of_a_soft_deleted_factory_is_returned(db, w1, ld, mk_batch):
    """BAT-GI-11 — a batch of a soft-deleted factory is returned.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5, production_line_id=ld.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] BAT-GI-12
def test_bat_gi_12__the_query_does_not_read_the_parent_tables(db, w1, mk_batch, recorder):
    """BAT-GI-12 — the query does not read the parent tables.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_batch(batch_number="B-A", batch_date=D5)

    recorder.start()
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    sql = recorder.sql()
    assert "JOIN" not in sql
    # Then 3
    assert "factories" not in sql
    # Then 4
    assert "production_lines" not in sql


# --------------------------------------------------------------------------- #
# ProductionBatchDAO.generate_batch_number
# --------------------------------------------------------------------------- #


# [claude] BAT-GN-01
def test_bat_gn_01__with_no_rows_the_number_is_001(db, w1):
    """BAT-GN-01 — with no rows the number is 001.
    Rules: `generate_batch_number` R1, Returns"""
    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-02
def test_bat_gn_02__the_year_comes_through_when_both_clocks_agree(db, w1):
    """BAT-GN-02 — the year comes through when both clocks agree.
    Rules: `generate_batch_number` R2"""
    with clocks(datetime(2031, 3, 1, 12, 0, 0), datetime(2031, 3, 1, 12, 0, 0)):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2031-001"


# [claude] BAT-GN-03
@pytest.mark.xfail(strict=True, reason="BUG-1334: Batch number's year comes from the server's local clock")
def test_bat_gn_03__the_year_is_the_utc_year_when_the_local_clock_is_already_in_the_next_y(db, w1):
    """BAT-GN-03 — the year is the UTC year, when the local clock is already in the next year.
    Rules: `generate_batch_number` R2 [BUG-1334]"""
    with clocks(datetime(2031, 1, 1, 0, 30, 0), datetime(2030, 12, 31, 23, 30, 0)):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2030-001"


# [claude] BAT-GN-04
@pytest.mark.xfail(strict=True, reason="BUG-1334: Batch number's year comes from the server's local clock")
def test_bat_gn_04__the_year_is_the_utc_year_when_the_local_clock_is_still_in_the_last_yea(db, w1):
    """BAT-GN-04 — the year is the UTC year, when the local clock is still in the last year.
    Rules: `generate_batch_number` R2 [BUG-1334]"""
    with clocks(datetime(2030, 12, 31, 23, 30, 0), datetime(2031, 1, 1, 0, 30, 0)):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2031-001"


# [claude] BAT-GN-05
def test_bat_gn_05__after_001_and_007_comes_008(db, w1, mk_batch):
    """BAT-GN-05 — after 001 and 007 comes 008.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-001")
    mk_batch(batch_number="BATCH-2026-007")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-008"


# [claude] BAT-GN-06
def test_bat_gn_06__the_highest_number_decides_not_the_newest_row(db, w1, mk_batch):
    """BAT-GN-06 — the highest number decides, not the newest row.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-007")
    mk_batch(batch_number="BATCH-2026-001")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-008"


# [claude] BAT-GN-07
def test_bat_gn_07__after_009_comes_010_padded_to_three_digits(db, w1, mk_batch):
    """BAT-GN-07 — after 009 comes 010: padded to three digits.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-009")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-010"


# [claude] BAT-GN-08
def test_bat_gn_08__after_099_comes_100(db, w1, mk_batch):
    """BAT-GN-08 — after 099 comes 100.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-099")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-100"


# [claude] BAT-GN-09
def test_bat_gn_09__after_998_comes_999(db, w1, mk_batch):
    """BAT-GN-09 — after 998 comes 999.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-998")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-999"


# [claude] BAT-GN-10
def test_bat_gn_10__after_999_comes_1000(db, w1, mk_batch):
    """BAT-GN-10 — after 999 comes 1000.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-999")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-1000"


# [claude] BAT-GN-11
def test_bat_gn_11__after_1000_alone_comes_1001(db, w1, mk_batch):
    """BAT-GN-11 — after 1000 alone comes 1001.
    Rules: `generate_batch_number` R3"""
    mk_batch(batch_number="BATCH-2026-1000")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-1001"


# [claude] BAT-GN-12
def test_bat_gn_12__rows_of_another_year_do_not_count(db, w1, mk_batch):
    """BAT-GN-12 — rows of another year do not count.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2025-050")
    mk_batch(batch_number="BATCH-2027-060")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-13
def test_bat_gn_13__rows_of_another_workspace_do_not_count(db, w1, w2, l9, mk_batch):
    """BAT-GN-13 — rows of another workspace do not count.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-050", workspace_id=w2.id, production_line_id=l9.id)

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-14
def test_bat_gn_14__a_w1_row_counts_for_w1_only_when_w2_has_a_higher_number(db, w1, w2, l9, mk_batch):
    """BAT-GN-14 — a W1 row counts for W1 only, when W2 has a higher number.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-003")
    mk_batch(batch_number="BATCH-2026-050", workspace_id=w2.id, production_line_id=l9.id)

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-004"


# [claude] BAT-GN-15
def test_bat_gn_15__another_prefix_with_the_same_year_does_not_count(db, w1, mk_batch):
    """BAT-GN-15 — another prefix with the same year does not count.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="XBATCH-2026-009")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-16
def test_bat_gn_16__a_cancelled_batch_counts_its_number_is_never_reused(db, w1, mk_batch):
    """BAT-GN-16 — a cancelled batch counts: its number is never reused.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-004", status="cancelled")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"


# [claude] BAT-GN-17
def test_bat_gn_17__a_completed_batch_counts_its_number_is_never_reused(db, w1, mk_batch):
    """BAT-GN-17 — a completed batch counts: its number is never reused.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-004", status="completed")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"


# [claude] BAT-GN-18
def test_bat_gn_18__a_in_progress_batch_counts_its_number_is_never_reused(db, w1, mk_batch):
    """BAT-GN-18 — a in_progress batch counts: its number is never reused.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-004", status="in_progress")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"


# [claude] BAT-GN-19
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_19__with_999_and_1000_the_next_is_1001(db, w1, mk_batch):
    """BAT-GN-19 — with 999 and 1000 the next is 1001.
    Rules: `generate_batch_number` R5 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-999")
    mk_batch(batch_number="BATCH-2026-1000")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-1001"


# [claude] BAT-GN-20
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_20__with_1000_stored_before_999_the_next_is_1001(db, w1, mk_batch):
    """BAT-GN-20 — with 1000 stored before 999 the next is 1001.
    Rules: `generate_batch_number` R5 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-1000")
    mk_batch(batch_number="BATCH-2026-999")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-1001"


# [claude] BAT-GN-21
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_21__with_999_1000_and_1001_the_next_is_1002(db, w1, mk_batch):
    """BAT-GN-21 — with 999, 1000 and 1001 the next is 1002.
    Rules: `generate_batch_number` R5 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-999")
    mk_batch(batch_number="BATCH-2026-1000")
    mk_batch(batch_number="BATCH-2026-1001")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-1002"


# [claude] BAT-GN-22
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_22__with_9999_and_10000_the_next_is_10001(db, w1, mk_batch):
    """BAT-GN-22 — with 9999 and 10000 the next is 10001.
    Rules: `generate_batch_number` R5 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-9999")
    mk_batch(batch_number="BATCH-2026-10000")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-10001"


# [claude] BAT-GN-23
def test_bat_gn_23__a_batch_of_a_soft_deleted_factory_counts(db, w1, ld, mk_batch):
    """BAT-GN-23 — a batch of a soft-deleted factory counts.
    Rules: `generate_batch_number` R6"""
    mk_batch(batch_number="BATCH-2026-004", production_line_id=ld.id)

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"


# [claude] BAT-GN-24
def test_bat_gn_24__the_query_does_not_read_the_parent_tables(db, w1, ld, mk_batch, recorder):
    """BAT-GN-24 — the query does not read the parent tables.
    Rules: `generate_batch_number` R6"""
    mk_batch(batch_number="BATCH-2026-004", production_line_id=ld.id)

    recorder.start()
    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"
    # Then 2
    sql = recorder.sql()
    assert "factories" not in sql
    # Then 3
    assert "production_lines" not in sql


# [claude] BAT-GN-25
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_25__a_suffix_of_letters_alone_is_ignored(db, w1, mk_batch):
    """BAT-GN-25 — a suffix of letters alone is ignored.
    Rules: `generate_batch_number` R7 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-ABC")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-26
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_26__an_empty_suffix_alone_is_ignored(db, w1, mk_batch):
    """BAT-GN-26 — an empty suffix alone is ignored.
    Rules: `generate_batch_number` R7 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-27
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_27__a_mixed_suffix_alone_is_ignored(db, w1, mk_batch):
    """BAT-GN-27 — a mixed suffix alone is ignored.
    Rules: `generate_batch_number` R7 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-12a")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-001"


# [claude] BAT-GN-28
@pytest.mark.xfail(strict=True, reason="BUG-1333: Batch numbers stop working after 999 in a year")
def test_bat_gn_28__a_suffix_of_letters_beside_005_is_ignored(db, w1, mk_batch):
    """BAT-GN-28 — a suffix of letters beside 005 is ignored.
    Rules: `generate_batch_number` R7 [BUG-1333]"""
    mk_batch(batch_number="BATCH-2026-005")
    mk_batch(batch_number="BATCH-2026-ABC")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-006"


# [claude] BAT-GN-29
def test_bat_gn_29__an_empty_suffix_beside_005_sorts_below_it_006(db, w1, mk_batch):
    """BAT-GN-29 — an empty suffix beside 005 sorts below it: 006.
    Rules: `generate_batch_number` R7"""
    mk_batch(batch_number="BATCH-2026-005")
    mk_batch(batch_number="BATCH-2026-")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-006"


# [claude] BAT-GN-30
def test_bat_gn_30__two_calls_with_no_insert_between_give_the_same_number(db, w1, mk_batch):
    """BAT-GN-30 — two calls with no insert between give the same number.
    Rules: `generate_batch_number` R9"""
    mk_batch(batch_number="BATCH-2026-004")
    before = stored_count(db)

    with clocks(CK, CK):
        result = [dao.generate_batch_number(db, workspace_id=w1.id) for _ in range(2)]

    # Then 1
    assert result == ["BATCH-2026-005", "BATCH-2026-005"]
    # Then 2
    assert stored_count(db) == before


# [claude] BAT-GN-31
def test_bat_gn_31__writes_nothing_a_pending_row_with_a_higher_number_stays_pending_and_do(db, w1, l1, mk_batch, recorder):
    """BAT-GN-31 — writes nothing: a pending row with a higher number stays pending and does not count.
    Rules: `generate_batch_number` Side effects"""
    a = mk_batch(batch_number="BATCH-2026-004")
    p = ProductionBatch(workspace_id=w1.id, batch_number="BATCH-2026-050", production_line_id=l1.id, batch_date=D3, status="draft")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    recorder.start()
    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty and not db.deleted
    # Then 6
    assert stored_count(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert recorder.written() == []


# [claude] BAT-GN-32
def test_bat_gn_32__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_batch):
    """BAT-GN-32 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `generate_batch_number` Side effects"""
    mk_batch(batch_number="BATCH-2026-004")
    b = mk_batch(batch_number="BATCH-2026-002")
    b.notes = "Edited"

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w1.id)

    # Then 1
    assert result == "BATCH-2026-005"
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.notes == "Edited"


# [claude] BAT-GN-33
def test_bat_gn_33__a_w1_row_does_not_count_for_w2(db, w2, mk_batch):
    """BAT-GN-33 — a W1 row does not count for W2.
    Rules: `generate_batch_number` R4"""
    mk_batch(batch_number="BATCH-2026-007")

    with clocks(CK, CK):
        result = dao.generate_batch_number(db, workspace_id=w2.id)

    # Then 1
    assert result == "BATCH-2026-001"


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ProductionBatch
# --------------------------------------------------------------------------- #


# [claude] BAT-INH-01
def test_bat_inh_01__create_with_a_dict_gives_status_draft_and_the_stamps(db, w1, l1):
    """BAT-INH-01 — create with a dict gives status draft and the stamps.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_number": "B-1", "production_line_id": l1.id, "batch_date": D3})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.status == "draft"
    # Then 3
    row = reread(db, result)
    assert row.created_at is not None
    assert row.updated_at is not None


# [claude] BAT-INH-02
def test_bat_inh_02__create_is_flushed_not_committed_a_rollback_removes_the_row(db, w1, l1):
    """BAT-INH-02 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R1"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_number": "B-1", "production_line_id": l1.id, "batch_date": D3})

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, ProductionBatch) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, ProductionBatch) == 0
    # Then 4
    commit_spy.assert_not_called()


# [claude] BAT-INH-03
def test_bat_inh_03__update_is_flushed_not_committed_a_rollback_restores_the_row(db, mk_batch):
    """BAT-INH-03 — update is flushed, not committed: a rollback restores the row.
    Rules: `inherited` R1"""
    a = mk_batch(batch_number="B-A", status="draft")

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.update(db, db_obj=a, obj_in={"status": "in_progress"})

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, ProductionBatch, ProductionBatch.status == "in_progress") == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, ProductionBatch, ProductionBatch.status == "draft") == 1
    # Then 4
    commit_spy.assert_not_called()


# [claude] BAT-INH-04
def test_bat_inh_04__create_with_a_productionbatchcreate_fails_on_flush_and_saves_nothing(db, l1):
    """BAT-INH-04 — create with a ProductionBatchCreate fails on flush and saves nothing.
    Rules: `inherited` R2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ProductionBatchCreate(production_line_id=l1.id, batch_date=D3))
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert count_rows(db, ProductionBatch) == 0


# [claude] BAT-INH-05
def test_bat_inh_05__a_second_row_with_one_number_in_one_workspace_is_refused(db, w1, l1, mk_batch):
    """BAT-INH-05 — a second row with one number in one workspace is refused.
    Rules: `inherited` R3"""
    mk_batch(batch_number="B-1")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "batch_number": "B-1", "production_line_id": l1.id, "batch_date": D3})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    assert count_rows(db, ProductionBatch) == 1


# [claude] BAT-INH-06
def test_bat_inh_06__the_same_number_in_another_workspace_is_accepted(db, w2, l9, mk_batch):
    """BAT-INH-06 — the same number in another workspace is accepted.
    Rules: `inherited` R3"""
    a = mk_batch(batch_number="B-1")

    result = dao.create(db, obj_in={"workspace_id": w2.id, "batch_number": "B-1", "production_line_id": l9.id, "batch_date": D3})

    # Then 1
    assert result.id != a.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id


# [claude] BAT-INH-07
def test_bat_inh_07__a_status_outside_the_four_is_stored(db, w1, l1):
    """BAT-INH-07 — a status outside the four is stored.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "batch_number": "B-1", "production_line_id": l1.id, "batch_date": D3, "status": "weird"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.status == "weird"
