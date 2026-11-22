"""Unit tests for app/dao/department.py.

Implements tests/unit/dao/department.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). The clock is patched
to NOW in every test (Conventions, Externals); nothing else is mocked.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import event, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.department import department_dao
from app.models.department import Department
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton department_dao" (a module-level name, not a fixture)
dao = department_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0, NOW" (naive)
T0 = datetime(2020, 1, 2, 3, 4, 5)
NOW = datetime(2031, 5, 6, 7, 8, 9)


# --------------------------------------------------------------------------- #
# Conventions -> the clock, in every test
# --------------------------------------------------------------------------- #

# Convention "Externals": a card never patches anything itself
@pytest.fixture(autouse=True)
def clock():
    with patch("app.dao.department.utcnow", return_value=NOW):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2, U3 = three profiles rows", ids rising in that order. None of
# them has a workspace_members row.
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


# Convention "They exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "row", and "gone" (after "but"): is_active as it was, updated_at not passed
@pytest.fixture
def mk_row(db, w1, u1):
    """mk_row(gone=False, **columns) -> Department. Keywords only."""
    def _mk(*, gone=False, **columns):
        fields = {"workspace_id": w1.id, "name": "Sales"}
        if gone:
            fields.update(is_deleted=True, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, Department(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X) except c, ...": the same, leaving out the columns named
def without(columns, *names):
    return {key: value for key, value in columns.items() if key not in names}


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one()


# The `count:` lines: SELECT count(*) through db.scalar(text(...)), with the filter stated
def count_rows(db, table, **filters):
    where = " AND ".join(f"{column} = :{column}" for column in filters) or "TRUE"
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {where}"), filters)


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

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


# --------------------------------------------------------------------------- #
# DAODepartment.soft_delete
# --------------------------------------------------------------------------- #


# [claude] DEP-SD-01
def test_dep_sd_01__sets_the_three_stamps_and_returns_the_same_row(db, u2, mk_row):
    """DEP-SD-01 — sets the three stamps and returns the same row.
    Rules: `soft_delete` R1, R2, Returns"""
    a = mk_row()

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW
    # Then 4
    row = reread(db, a)
    assert row.deleted_by == u2.id


# [claude] DEP-SD-02
def test_dep_sd_02__nothing_else_changes_updated_by_is_not_stamped_with_the_deleter(db, u1, u2, u3, mk_row):
    """DEP-SD-02 — nothing else changes: updated_by is not stamped with the deleter.
    Rules: `soft_delete` R3"""
    a = mk_row(created_by=u1.id, updated_by=u3.id)
    before_a = snap(db, a)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.name == "Sales"
    assert row.is_active is True
    # Then 3
    row = reread(db, a)
    assert row.created_by == u1.id
    assert row.updated_by == u3.id
    # Then 4
    db.expire_all()
    assert without(snap(db, a), "is_deleted", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "deleted_at", "deleted_by", "updated_at")


# [claude] DEP-SD-03
def test_dep_sd_03__an_inactive_row_stays_inactive_and_empty_stamps_stay_empty(db, u2, mk_row):
    """DEP-SD-03 — an inactive row stays inactive, and empty stamps stay empty.
    Rules: `soft_delete` R3"""
    a = mk_row(is_active=False)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.created_by is None
    assert row.updated_by is None
    # Then 4
    row = reread(db, a)
    assert row.is_deleted is True


# [claude] DEP-SD-04
def test_dep_sd_04__updated_at_goes_from_null_to_a_value(db, u2, mk_row):
    """DEP-SD-04 — updated_at goes from NULL to a value.
    Rules: `soft_delete` R3"""
    a = mk_row()
    db.refresh(a)
    a0 = snap(db, a)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert a0["updated_at"] is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is not None


# [claude] DEP-SD-05
def test_dep_sd_05__a_row_already_deleted_is_deleted_again_the_stamps_are_overwritten(db, u2, mk_row):
    """DEP-SD-05 — a row already deleted is deleted again: the stamps are overwritten.
    Rules: `soft_delete` R4"""
    a = mk_row(gone=True)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW
    # Then 4
    row = reread(db, a)
    assert row.deleted_by == u2.id


# [claude] DEP-SD-06
def test_dep_sd_06__a_row_of_another_workspace_is_deleted_by_a_profile_with_no_link_to_it(db, w2, u1, mk_row):
    """DEP-SD-06 — a row of another workspace is deleted, by a profile with no link to it.
    Rules: `soft_delete` R5"""
    a = mk_row()
    z = mk_row(workspace_id=w2.id, name="Ops")
    before_a = snap(db, a)

    result = dao.soft_delete(db, db_obj=z, deleted_by=u1.id)

    # Then 1
    assert result is z
    # Then 2
    row = reread(db, z)
    assert row.is_deleted is True
    assert row.deleted_at == NOW
    assert row.deleted_by == u1.id
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] DEP-SD-07
def test_dep_sd_07__an_unknown_deleted_by_raises_and_nothing_changes(db, mk_row):
    """DEP-SD-07 — an unknown deleted_by raises and nothing changes.
    Rules: `soft_delete` R6, Errors row 1"""
    a = mk_row()
    db.refresh(a)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=a, deleted_by=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert "departments_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    db.refresh(a)
    assert snap(db, a) == before_a
    # Then 5
    db.refresh(a)
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] DEP-SD-08
def test_dep_sd_08__deleted_by_none_is_stored(db, mk_row):
    """DEP-SD-08 — deleted_by=None is stored.
    Rules: `soft_delete` R7"""
    a = mk_row()

    result = dao.soft_delete(db, db_obj=a, deleted_by=None)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW
    # Then 4
    row = reread(db, a)
    assert row.deleted_by is None


# [claude] DEP-SD-09
def test_dep_sd_09__the_raw_base_reads_still_return_the_row(db, w1, u2, mk_row):
    """DEP-SD-09 — the raw base reads still return the row.
    Rules: `soft_delete` R8"""
    a = mk_row()

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert dao.get(db, a.id) is a
    # Then 3
    assert dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id) is a
    # Then 4
    assert [r.id for r in dao.get_by_workspace(db, workspace_id=w1.id)] == [a.id]


# [claude] DEP-SD-10
def test_dep_sd_10__the_delete_is_flushed_not_committed_a_rollback_removes_all_three_stamp(db, u2, mk_row):
    """DEP-SD-10 — the delete is flushed, not committed: a rollback removes all three stamps.
    Rules: `soft_delete` R2, Side effects"""
    a = mk_row()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, "departments", id=a.id, is_deleted=True) == 1
    # Then 3
    sp.rollback()
    db.refresh(a)
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 4
    row = reread(db, a)
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert commit_spy.call_count == 0


# [claude] DEP-SD-11
def test_dep_sd_11__one_update_of_one_department_and_no_other_statement_writes(db, u2, mk_row):
    """DEP-SD-11 — one UPDATE of one department, and no other statement writes.
    Rules: `soft_delete` Side effects"""
    a = mk_row()
    b = mk_row(name="Ops")
    before_b = snap(db, b)

    with StatementRecorder(db) as recorder:
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)
    written = recorder.written()

    # Then 1
    assert result is a
    # Then 2
    assert len(written) == 1
    # Then 3
    assert written[0].startswith("UPDATE departments")
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] DEP-SD-12
def test_dep_sd_12__a_row_already_deleted_with_deleted_by_none_the_old_deleter_is_overwrit(db, mk_row):
    """DEP-SD-12 — a row already deleted, with deleted_by=None: the old deleter is overwritten.
    Rules: `soft_delete` R4, R7"""
    a = mk_row(gone=True)

    result = dao.soft_delete(db, db_obj=a, deleted_by=None)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 3
    row = reread(db, a)
    assert row.deleted_at == NOW
    # Then 4
    row = reread(db, a)
    assert row.deleted_by is None


# --------------------------------------------------------------------------- #
# DAODepartment.restore
# --------------------------------------------------------------------------- #


# [claude] DEP-RS-01
def test_dep_rs_01__clears_the_three_stamps_and_returns_the_same_row(db, mk_row):
    """DEP-RS-01 — clears the three stamps and returns the same row.
    Rules: `restore` R1, R3, Returns"""
    a = mk_row(gone=True)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_at is None
    # Then 4
    row = reread(db, a)
    assert row.deleted_by is None


# [claude] DEP-RS-02
def test_dep_rs_02__a_row_soft_deleted_through_the_dao_comes_back(db, u2, mk_row):
    """DEP-RS-02 — a row soft-deleted through the DAO comes back.
    Rules: `restore` R1"""
    a = mk_row()
    dao.soft_delete(db, db_obj=a, deleted_by=u2.id)
    db.refresh(a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 3
    row = reread(db, a)
    assert row.deleted_at is None
    # Then 4
    row = reread(db, a)
    assert row.deleted_by is None


# [claude] DEP-RS-03
def test_dep_rs_03__nothing_else_changes_and_nobody_is_recorded(db, u2, u3, mk_row):
    """DEP-RS-03 — nothing else changes, and nobody is recorded.
    Rules: `restore` R2"""
    a = mk_row(gone=True, created_by=u2.id, updated_by=u3.id)
    before_a = snap(db, a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.name == "Sales"
    assert row.is_active is True
    # Then 3
    row = reread(db, a)
    assert row.created_by == u2.id
    assert row.updated_by == u3.id
    # Then 4
    db.expire_all()
    assert without(snap(db, a), "is_deleted", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "deleted_at", "deleted_by", "updated_at")


# [claude] DEP-RS-04
def test_dep_rs_04__an_inactive_row_stays_inactive_and_empty_stamps_stay_empty(db, mk_row):
    """DEP-RS-04 — an inactive row stays inactive, and empty stamps stay empty.
    Rules: `restore` R2"""
    a = mk_row(gone=True, is_active=False)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_active is False
    # Then 3
    row = reread(db, a)
    assert row.created_by is None
    assert row.updated_by is None
    # Then 4
    row = reread(db, a)
    assert row.is_deleted is False


# [claude] DEP-RS-05
def test_dep_rs_05__updated_at_goes_from_null_to_a_value(db, mk_row):
    """DEP-RS-05 — updated_at goes from NULL to a value.
    Rules: `restore` R2"""
    a = mk_row(gone=True)
    db.refresh(a)
    a0 = snap(db, a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert a0["updated_at"] is None
    # Then 3
    row = reread(db, a)
    assert row.updated_at is not None


# [claude] DEP-RS-06
def test_dep_rs_06__the_restore_is_flushed_not_committed_a_rollback_brings_the_deleted_sta(db, u1, mk_row):
    """DEP-RS-06 — the restore is flushed, not committed: a rollback brings the deleted state back.
    Rules: `restore` R3, Side effects"""
    a = mk_row(gone=True)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, "departments", id=a.id, is_deleted=False) == 1
    # Then 3
    sp.rollback()
    db.refresh(a)
    row = reread(db, a)
    assert row.is_deleted is True
    # Then 4
    row = reread(db, a)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 5
    assert commit_spy.call_count == 0


# [claude] DEP-RS-07
def test_dep_rs_07__a_live_row_is_accepted_and_nothing_is_sent(db, u1, mk_row):
    """DEP-RS-07 — a live row is accepted and nothing is sent.
    Rules: `restore` R4"""
    a = mk_row(created_by=u1.id)
    db.refresh(a)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.restore(db, db_obj=a)
    written = recorder.written()

    # Then 1
    assert result is a
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 3
    row = reread(db, a)
    assert row.updated_at is None
    # Then 4
    assert written == []


# [claude] DEP-RS-08
def test_dep_rs_08__a_row_of_another_workspace_is_restored(db, w2, mk_row):
    """DEP-RS-08 — a row of another workspace is restored.
    Rules: `restore` R5"""
    a = mk_row(gone=True)
    z = mk_row(gone=True, workspace_id=w2.id, name="Ops")
    before_a = snap(db, a)

    result = dao.restore(db, db_obj=z)

    # Then 1
    assert result is z
    # Then 2
    row = reread(db, z)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] DEP-RS-09
def test_dep_rs_09__one_update_of_one_department_and_no_other_statement_writes(db, mk_row):
    """DEP-RS-09 — one UPDATE of one department, and no other statement writes.
    Rules: `restore` Side effects"""
    a = mk_row(gone=True)
    b = mk_row(gone=True, name="Ops")
    before_b = snap(db, b)

    with StatementRecorder(db) as recorder:
        result = dao.restore(db, db_obj=a)
    written = recorder.written()

    # Then 1
    assert result is a
    # Then 2
    assert len(written) == 1
    # Then 3
    assert written[0].startswith("UPDATE departments")
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] DEP-RS-10
@pytest.mark.xfail(strict=True, reason="BUG-003: Department name uniqueness not enforced by the database")
def test_dep_rs_10__restoring_next_to_a_live_row_of_that_name_is_refused(db, u1, mk_row):
    """DEP-RS-10 — restoring next to a live row of that name is refused.
    Rules: `restore` R6 [BUG-003], Errors row 1"""
    a = mk_row(gone=True, name="Dup")
    b = mk_row(name="Dup")
    db.refresh(a)
    before_b = snap(db, b)

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            dao.restore(db, db_obj=a)
    # Then 2
    db.refresh(a)
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 3
    db.refresh(b)
    assert snap(db, b) == before_b


# [claude] DEP-RS-11
def test_dep_rs_11__another_deleted_row_of_that_name_does_not_block_a_restore(db, mk_row):
    """DEP-RS-11 — another deleted row of that name does not block a restore.
    Rules: `restore` R6"""
    a = mk_row(gone=True, name="Dup")
    b = mk_row(gone=True, name="Dup")
    before_b = snap(db, b)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] DEP-RS-12
def test_dep_rs_12__a_live_row_of_that_name_in_another_workspace_does_not_block_a_restore(db, w2, mk_row):
    """DEP-RS-12 — a live row of that name in another workspace does not block a restore.
    Rules: `restore` R6"""
    a = mk_row(gone=True, name="Dup")
    b = mk_row(workspace_id=w2.id, name="Dup")
    before_b = snap(db, b)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.is_deleted is False
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b
