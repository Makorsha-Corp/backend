"""Unit tests for app/dao/production_batch_stage_log.py.

Implements tests/unit/dao/production_batch_stage_log.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
from datetime import date

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.production_batch_stage_log import production_batch_stage_log_dao
from app.models.factory import Factory
from app.models.production_batch import ProductionBatch
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.models.production_formula import ProductionFormula
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_line import ProductionLine
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_batch_stage_log_dao" (a module-level name, not a fixture)
dao = production_batch_stage_log_dao

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
def f1(db, w1, w2):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def pl1(db, w1, f1):
    return _add(db, ProductionLine(workspace_id=w1.id, factory_id=f1.id, name="Line One"))


@pytest.fixture
def pf1(db, w1, pl1):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-T-001", name="Mix"))


@pytest.fixture
def b1(db, w1, pl1, pf1):
    return _add(db, ProductionBatch(workspace_id=w1.id, batch_number="PB-T-001", production_line_id=pl1.id, batch_date=date(2026, 3, 1), status="draft"))


@pytest.fixture
def b2(db, w1, pl1, b1):
    return _add(db, ProductionBatch(workspace_id=w1.id, batch_number="PB-T-002", production_line_id=pl1.id, batch_date=date(2026, 3, 1), status="draft"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, f1, pl1, pf1, b1, b2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "log": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_log(db, w1, b1):
    """mk_log(stage_order=..., **columns) -> ProductionBatchStageLog. Keywords only."""
    def _mk(*, stage_order, **columns):
        fields = {"workspace_id": w1.id, "batch_id": b1.id, "stage_name": "Stage", "stage_order": stage_order}
        fields.update(columns)
        return _add(db, ProductionBatchStageLog(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, b1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [ProductionBatchStageLog(workspace_id=w1.id, batch_id=b1.id, stage_name="Stage", stage_order=k)
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


# Convention "nothing written": the number of production_batch_stage_logs rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProductionBatchStageLog.__table__)).scalar_one()


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
        """The one SELECT from production_batch_stage_logs; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "production_batch_stage_logs" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# ProductionBatchStageLogDAO.get_by_batch
# --------------------------------------------------------------------------- #


# [claude] PBL-G-01
def test_pbl_g_01__returns_a_list_of_the_batch_s_logs(db, w1, b1, mk_log):
    """PBL-G-01 — returns a list of the batch's logs.
    Rules: `get_by_batch` R1, Returns"""
    a = mk_log(stage_order=1)
    b = mk_log(stage_order=2)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionBatchStageLog)


# [claude] PBL-G-02
def test_pbl_g_02__a_log_of_another_batch_of_the_same_workspace_is_not_returned_though_it(db, w1, b1, b2, mk_log):
    """PBL-G-02 — a log of another batch of the same workspace is not returned, though it sorts first.
    Rules: `get_by_batch` R1"""
    a = mk_log(stage_order=2)
    mk_log(stage_order=1, batch_id=b2.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PBL-G-03
def test_pbl_g_03__the_right_batch_under_another_workspace_returns_an_empty_list(db, w2, b1, mk_log):
    """PBL-G-03 — the right batch under another workspace returns an empty list.
    Rules: `get_by_batch` R1"""
    mk_log(stage_order=1)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PBL-G-04
def test_pbl_g_04__an_unknown_workspace_returns_an_empty_list(db, b1, mk_log):
    """PBL-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_batch` R1"""
    mk_log(stage_order=1)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PBL-G-05
def test_pbl_g_05__a_w2_row_on_a_w1_batch_is_returned_for_w2_only_the_row_s_workspace_is(db, w2, b1, mk_log):
    """PBL-G-05 — a W2 row on a W1 batch is returned for W2: only the row's workspace is compared.
    Rules: `get_by_batch` R1"""
    a = mk_log(stage_order=1, workspace_id=w2.id)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PBL-G-06
def test_pbl_g_06__a_w2_row_on_a_w1_batch_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, b1, mk_log):
    """PBL-G-06 — a W2 row on a W1 batch is not returned for W1, though it sorts first.
    Rules: `get_by_batch` R1"""
    mk_log(stage_order=1, workspace_id=w2.id)
    a = mk_log(stage_order=2)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PBL-G-07
def test_pbl_g_07__an_unknown_batch_id_returns_an_empty_list(db, w1, mk_log):
    """PBL-G-07 — an unknown batch id returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_log(stage_order=1)

    result = dao.get_by_batch(db, batch_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PBL-G-08
def test_pbl_g_08__batch_id_0_returns_an_empty_list(db, w1, mk_log):
    """PBL-G-08 — batch id 0 returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_log(stage_order=1)

    result = dao.get_by_batch(db, batch_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PBL-G-09
def test_pbl_g_09__a_batch_with_no_rows_returns_an_empty_list(db, w1, b2, mk_log):
    """PBL-G-09 — a batch with no rows returns an empty list.
    Rules: `get_by_batch` R2"""
    mk_log(stage_order=1)

    result = dao.get_by_batch(db, batch_id=b2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PBL-G-10
def test_pbl_g_10__orders_2_1_1_0_give_the_0_row_the_two_1_rows_by_id_then_the_2_row(db, w1, b1, mk_log):
    """PBL-G-10 — orders 2, 1, 1, 0 give the 0 row, the two 1 rows by id, then the 2 row.
    Rules: `get_by_batch` R3"""
    a = mk_log(stage_order=2, stage_name="Alpha")
    b = mk_log(stage_order=1, stage_name="Zeta")
    c = mk_log(stage_order=1, stage_name="Mid")
    d = mk_log(stage_order=0, stage_name="Beta")

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, b.id, c.id, a.id]


# [claude] PBL-G-11
def test_pbl_g_11__the_tied_pair_keeps_its_order_after_the_lower_id_is_updated(db, w1, b1, mk_log):
    """PBL-G-11 — the tied pair keeps its order after the lower id is updated.
    Rules: `get_by_batch` R3"""
    a = mk_log(stage_order=2, stage_name="Alpha")
    b = mk_log(stage_order=1, stage_name="Zeta")
    c = mk_log(stage_order=1, stage_name="Mid")
    d = mk_log(stage_order=0, stage_name="Beta")
    b.stage_name = "Omega"
    db.flush()
    db.expire_all()
    seqscan(db)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, b.id, c.id, a.id]


# [claude] PBL-G-12
def test_pbl_g_12__the_query_orders_by_stage_order_then_id_ascending(db, w1, b1, mk_log):
    """PBL-G-12 — the query orders by stage_order, then id ascending.
    Rules: `get_by_batch` R3"""
    a = mk_log(stage_order=1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "stage_order" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("stage_order") < order_part.index(".id")
    # Then 5
    assert "DESC" not in order_part.upper()


# [claude] PBL-G-13
def test_pbl_g_13__there_is_no_cap_101_logs_give_101_rows(db, w1, b1, mk_many):
    """PBL-G-13 — there is no cap: 101 logs give 101 rows.
    Rules: `get_by_batch` R4"""
    in_order = mk_many(101)

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] PBL-G-14
def test_pbl_g_14__a_log_whose_formula_stage_was_removed_is_still_returned_with_its_name(db, w1, pf1, b1, mk_log):
    """PBL-G-14 — a log whose formula stage was removed is still returned, with its name.
    Rules: `get_by_batch` R5"""
    fs1 = _add(db, ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, stage_order=1, name="Mixing"))
    a = mk_log(stage_order=1, formula_stage_id=fs1.id, stage_name="Mixing")
    db.delete(fs1)
    db.flush()
    db.expire_all()

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].formula_stage_id is None
    # Then 3
    assert result[0].stage_name == "Mixing"


# [claude] PBL-G-15
def test_pbl_g_15__writes_nothing_a_pending_log_that_sorts_first_stays_pending_and_alone(db, w1, b1, mk_log):
    """PBL-G-15 — writes nothing: a pending log that sorts first stays pending and alone in the session.
    Rules: `get_by_batch` Side effects"""
    a = mk_log(stage_order=2)
    p = ProductionBatchStageLog(workspace_id=w1.id, batch_id=b1.id, stage_name="Pending", stage_order=1)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)
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
    assert stored_count(db) == before
    # Then 11
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 12
    assert "production_batches" not in sql


# [claude] PBL-G-16
def test_pbl_g_16__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, b1, b2, mk_log):
    """PBL-G-16 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_batch` Side effects"""
    a = mk_log(stage_order=1)
    b = mk_log(stage_order=1, batch_id=b2.id)
    b.stage_name = "Edited"

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.stage_name == "Edited"


# [claude] PBL-G-17
def test_pbl_g_17__a_formula_stage_removed_by_a_raw_delete_leaves_its_log_nulled_by_the_d(db, w1, pf1, b1, mk_log):
    """PBL-G-17 — a formula stage removed by a raw DELETE leaves its log, nulled by the database.
    Rules: `get_by_batch` R5"""
    fs1 = _add(db, ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, stage_order=1, name="Mixing"))
    a = mk_log(stage_order=1, formula_stage_id=fs1.id, stage_name="Mixing")
    db.execute(text("DELETE FROM production_formula_stages WHERE id = :i"), {"i": fs1.id})
    db.expire_all()

    result = dao.get_by_batch(db, batch_id=b1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].formula_stage_id is None
    # Then 3
    assert result[0].stage_name == "Mixing"


# --------------------------------------------------------------------------- #
# ProductionBatchStageLogDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PBL-I-01
def test_pbl_i_01__returns_the_log_of_that_id_not_the_first_log(db, w1, mk_log):
    """PBL-I-01 — returns the log of that id, not the first log.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_log(stage_order=1)
    b = mk_log(stage_order=2)

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, ProductionBatchStageLog)


# [claude] PBL-I-02
def test_pbl_i_02__another_workspace_returns_none(db, w2, mk_log):
    """PBL-I-02 — another workspace returns None.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_log(stage_order=1)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PBL-I-03
def test_pbl_i_03__an_unknown_id_returns_none_and_nothing_is_created(db, w1, mk_log):
    """PBL-I-03 — an unknown id returns None and nothing is created.
    Rules: `get_by_id_and_workspace` R1"""
    mk_log(stage_order=1)
    before = stored_count(db)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] PBL-I-04
def test_pbl_i_04__writes_nothing_a_read_that_finds_its_log_leaves_the_session_as_it_was(db, w1, b1, mk_log):
    """PBL-I-04 — writes nothing: a read that finds its log leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_log(stage_order=1)
    p = ProductionBatchStageLog(workspace_id=w1.id, batch_id=b1.id, stage_name="Pending", stage_order=2)
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
    # Then 12
    assert "production_batches" not in sql


# [claude] PBL-I-05
def test_pbl_i_05__a_w2_log_at_the_earlier_id_is_not_returned_for_w1(db, w1, w2, mk_log):
    """PBL-I-05 — a W2 log at the earlier id is not returned for W1.
    Rules: `get_by_id_and_workspace` R1"""
    z = mk_log(stage_order=1, workspace_id=w2.id)
    mk_log(stage_order=2)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PBL-I-06
def test_pbl_i_06__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, mk_log):
    """PBL-I-06 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_log(stage_order=1)
    b = mk_log(stage_order=2)
    b.stage_name = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.stage_name == "Edited"
