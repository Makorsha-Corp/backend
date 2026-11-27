"""Unit tests for app/dao/production_formula_stage.py.

Implements tests/unit/dao/production_formula_stage.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect

from app.dao.production_formula_stage import production_formula_stage_dao
from app.models.production_formula import ProductionFormula
from app.models.production_formula_stage import ProductionFormulaStage
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton production_formula_stage_dao" (a module-level name, not a fixture)
dao = production_formula_stage_dao

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
def pf1(db, w1, w2):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-T-001", name="Mix"))


@pytest.fixture
def pf2(db, w1, pf1):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-T-002", name="Mix"))


@pytest.fixture
def pfd(db, w1, pf2):
    return _add(db, ProductionFormula(workspace_id=w1.id, formula_code="FM-T-003", name="Mix", is_active=False))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, pf1, pf2, pfd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "stage": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_stage(db, w1, pf1):
    """mk_stage(stage_order=..., **columns) -> ProductionFormulaStage. Keywords only."""
    def _mk(*, stage_order, **columns):
        fields = {"workspace_id": w1.id, "formula_id": pf1.id, "name": "Stage", "stage_order": stage_order}
        fields.update(columns)
        return _add(db, ProductionFormulaStage(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, pf1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, name="Stage", stage_order=k)
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


# Convention "nothing written": the number of production_formula_stages rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ProductionFormulaStage.__table__)).scalar_one()


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
        """The one SELECT from production_formula_stages; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "production_formula_stages" in s]
        return statement


# --------------------------------------------------------------------------- #
# ProductionFormulaStageDAO.get_by_formula
# --------------------------------------------------------------------------- #


# [claude] PFS-G-01
def test_pfs_g_01__returns_a_list_of_the_formula_s_stages(db, w1, pf1, mk_stage):
    """PFS-G-01 — returns a list of the formula's stages.
    Rules: `get_by_formula` R1, Returns"""
    a = mk_stage(stage_order=1)
    b = mk_stage(stage_order=2)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ProductionFormulaStage)


# [claude] PFS-G-02
def test_pfs_g_02__a_stage_of_another_formula_of_the_same_workspace_is_not_returned_thoug(db, w1, pf1, pf2, mk_stage):
    """PFS-G-02 — a stage of another formula of the same workspace is not returned, though it sorts first.
    Rules: `get_by_formula` R1"""
    a = mk_stage(stage_order=2)
    mk_stage(stage_order=1, formula_id=pf2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PFS-G-03
def test_pfs_g_03__the_right_formula_under_another_workspace_returns_an_empty_list(db, w2, pf1, mk_stage):
    """PFS-G-03 — the right formula under another workspace returns an empty list.
    Rules: `get_by_formula` R1"""
    mk_stage(stage_order=1)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PFS-G-04
def test_pfs_g_04__an_unknown_workspace_returns_an_empty_list(db, pf1, mk_stage):
    """PFS-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_formula` R1"""
    mk_stage(stage_order=1)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] PFS-G-05
def test_pfs_g_05__a_w2_row_on_a_w1_formula_is_returned_for_w2_only_the_row_s_workspace_i(db, w2, pf1, mk_stage):
    """PFS-G-05 — a W2 row on a W1 formula is returned for W2: only the row's workspace is compared.
    Rules: `get_by_formula` R1"""
    a = mk_stage(stage_order=1, workspace_id=w2.id)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PFS-G-06
def test_pfs_g_06__a_w2_row_on_a_w1_formula_is_not_returned_for_w1_though_it_sorts_first(db, w1, w2, pf1, mk_stage):
    """PFS-G-06 — a W2 row on a W1 formula is not returned for W1, though it sorts first.
    Rules: `get_by_formula` R1"""
    mk_stage(stage_order=1, workspace_id=w2.id)
    a = mk_stage(stage_order=2)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PFS-G-07
def test_pfs_g_07__an_unknown_formula_id_returns_an_empty_list(db, w1, mk_stage):
    """PFS-G-07 — an unknown formula id returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_stage(stage_order=1)

    result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFS-G-08
def test_pfs_g_08__formula_id_0_returns_an_empty_list(db, w1, mk_stage):
    """PFS-G-08 — formula id 0 returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_stage(stage_order=1)

    result = dao.get_by_formula(db, formula_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFS-G-09
def test_pfs_g_09__a_formula_with_no_rows_returns_an_empty_list(db, w1, pf2, mk_stage):
    """PFS-G-09 — a formula with no rows returns an empty list.
    Rules: `get_by_formula` R2"""
    mk_stage(stage_order=1)

    result = dao.get_by_formula(db, formula_id=pf2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] PFS-G-10
def test_pfs_g_10__stages_are_ordered_by_stage_order_ascending_negative_and_zero_included(db, w1, pf1, mk_stage):
    """PFS-G-10 — stages are ordered by stage_order ascending, negative and zero included, whatever the insert order or the name.
    Rules: `get_by_formula` R3"""
    a = mk_stage(stage_order=3, name="Alpha")
    b = mk_stage(stage_order=-1, name="Zeta")
    c = mk_stage(stage_order=0, name="Mid")

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] PFS-G-11
def test_pfs_g_11__there_is_no_cap_101_stages_give_101_rows(db, w1, pf1, mk_many):
    """PFS-G-11 — there is no cap: 101 stages give 101 rows.
    Rules: `get_by_formula` R4"""
    in_order = mk_many(101)

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] PFS-G-12
def test_pfs_g_12__the_stages_of_a_deactivated_formula_are_returned(db, w1, pfd, mk_stage):
    """PFS-G-12 — the stages of a deactivated formula are returned.
    Rules: `get_by_formula` R5"""
    a = mk_stage(stage_order=1, formula_id=pfd.id)

    result = dao.get_by_formula(db, formula_id=pfd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PFS-G-13
def test_pfs_g_13__writes_nothing_a_pending_stage_that_sorts_first_stays_pending_and_alon(db, w1, pf1, mk_stage):
    """PFS-G-13 — writes nothing: a pending stage that sorts first stays pending and alone in the session.
    Rules: `get_by_formula` Side effects"""
    a = mk_stage(stage_order=2)
    p = ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, stage_order=1, name="Pending")
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)
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
    assert "production_formulas" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] PFS-G-14
def test_pfs_g_14__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, pf1, pf2, mk_stage):
    """PFS-G-14 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_formula` Side effects"""
    a = mk_stage(stage_order=1)
    b = mk_stage(stage_order=1, formula_id=pf2.id)
    b.name = "Edited"

    result = dao.get_by_formula(db, formula_id=pf1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.name == "Edited"


# --------------------------------------------------------------------------- #
# ProductionFormulaStageDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] PFS-I-01
def test_pfs_i_01__returns_the_stage_of_that_id_not_the_first_stage(db, w1, mk_stage):
    """PFS-I-01 — returns the stage of that id, not the first stage.
    Rules: `get_by_id_and_workspace` R1, Returns"""
    mk_stage(stage_order=1)
    b = mk_stage(stage_order=2)

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, ProductionFormulaStage)


# [claude] PFS-I-02
def test_pfs_i_02__another_workspace_returns_none(db, w2, mk_stage):
    """PFS-I-02 — another workspace returns None.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_stage(stage_order=1)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] PFS-I-03
def test_pfs_i_03__an_unknown_id_returns_none_and_nothing_is_created(db, w1, mk_stage):
    """PFS-I-03 — an unknown id returns None and nothing is created.
    Rules: `get_by_id_and_workspace` R1"""
    mk_stage(stage_order=1)
    before = stored_count(db)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] PFS-I-04
def test_pfs_i_04__writes_nothing_a_read_that_finds_its_stage_leaves_the_session_as_it_wa(db, w1, pf1, mk_stage):
    """PFS-I-04 — writes nothing: a read that finds its stage leaves the session as it was.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_stage(stage_order=1)
    p = ProductionFormulaStage(workspace_id=w1.id, formula_id=pf1.id, stage_order=2, name="Pending")
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


# [claude] PFS-I-05
def test_pfs_i_05__a_w2_stage_at_the_earlier_id_is_not_returned_for_w1(db, w1, w2, mk_stage):
    """PFS-I-05 — a W2 stage at the earlier id is not returned for W1.
    Rules: `get_by_id_and_workspace` R1"""
    z = mk_stage(stage_order=1, workspace_id=w2.id)
    mk_stage(stage_order=2)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] PFS-I-06
def test_pfs_i_06__a_stage_of_a_deactivated_formula_is_returned_and_the_formula_is_not_jo(db, w1, pfd, mk_stage):
    """PFS-I-06 — a stage of a deactivated formula is returned, and the formula is not joined.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_stage(stage_order=1, formula_id=pfd.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
    sql = recorder.sql()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert "production_formulas" not in sql


# [claude] PFS-I-07
def test_pfs_i_07__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, mk_stage):
    """PFS-I-07 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_stage(stage_order=1)
    b = mk_stage(stage_order=2)
    b.name = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.name == "Edited"
