"""Unit tests for app/dao/work_order_type.py.

Implements tests/unit/dao/work_order_type.cases.md, one test per case, in card
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

from app.dao.work_order_type import work_order_type_dao
from app.models.work_order_type import WorkOrderType
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton work_order_type_dao" (a module-level name, not a fixture)
dao = work_order_type_dao

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
    with patch("app.dao.work_order_type.utcnow", return_value=NOW):
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
    """mk_row(gone=False, **columns) -> WorkOrderType. Keywords only."""
    def _mk(*, gone=False, **columns):
        fields = {"workspace_id": w1.id, "name": "Repair"}
        if gone:
            fields.update(is_deleted=True, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, WorkOrderType(**fields))
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
# DAOWorkOrderType.soft_delete
# --------------------------------------------------------------------------- #


# [claude] WOT-SD-01
def test_wot_sd_01__sets_the_three_stamps_and_returns_the_same_row(db, u2, mk_row):
    """WOT-SD-01 — sets the three stamps and returns the same row.
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


# [claude] WOT-SD-02
def test_wot_sd_02__nothing_else_changes_updated_by_is_not_stamped_with_the_deleter(db, u1, u2, u3, mk_row):
    """WOT-SD-02 — nothing else changes: updated_by is not stamped with the deleter.
    Rules: `soft_delete` R3"""
    a = mk_row(created_by=u1.id, updated_by=u3.id)
    before_a = snap(db, a)

    result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.name == "Repair"
    assert row.is_active is True
    # Then 3
    row = reread(db, a)
    assert row.created_by == u1.id
    assert row.updated_by == u3.id
    # Then 4
    db.expire_all()
    assert without(snap(db, a), "is_deleted", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "deleted_at", "deleted_by", "updated_at")


# [claude] WOT-SD-03
def test_wot_sd_03__an_inactive_row_stays_inactive_and_empty_stamps_stay_empty(db, u2, mk_row):
    """WOT-SD-03 — an inactive row stays inactive, and empty stamps stay empty.
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


# [claude] WOT-SD-04
def test_wot_sd_04__updated_at_goes_from_null_to_a_value(db, u2, mk_row):
    """WOT-SD-04 — updated_at goes from NULL to a value.
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


# [claude] WOT-SD-05
def test_wot_sd_05__a_row_already_deleted_is_deleted_again_the_stamps_are_overwritten(db, u2, mk_row):
    """WOT-SD-05 — a row already deleted is deleted again: the stamps are overwritten.
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


# [claude] WOT-SD-06
def test_wot_sd_06__a_row_of_another_workspace_is_deleted_by_a_profile_with_no_link_to_it(db, w2, u1, mk_row):
    """WOT-SD-06 — a row of another workspace is deleted, by a profile with no link to it.
    Rules: `soft_delete` R5"""
    a = mk_row()
    z = mk_row(workspace_id=w2.id, name="Install")
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


# [claude] WOT-SD-07
def test_wot_sd_07__an_unknown_deleted_by_raises_and_nothing_changes(db, mk_row):
    """WOT-SD-07 — an unknown deleted_by raises and nothing changes.
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
    assert "work_order_types_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    db.refresh(a)
    assert snap(db, a) == before_a
    # Then 5
    db.refresh(a)
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] WOT-SD-08
def test_wot_sd_08__deleted_by_none_is_stored(db, mk_row):
    """WOT-SD-08 — deleted_by=None is stored.
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


# [claude] WOT-SD-09
def test_wot_sd_09__the_raw_base_reads_still_return_the_row(db, w1, u2, mk_row):
    """WOT-SD-09 — the raw base reads still return the row.
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


# [claude] WOT-SD-10
def test_wot_sd_10__the_delete_is_flushed_not_committed_a_rollback_removes_all_three_stamp(db, u2, mk_row):
    """WOT-SD-10 — the delete is flushed, not committed: a rollback removes all three stamps.
    Rules: `soft_delete` R2, Side effects"""
    a = mk_row()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, "work_order_types", id=a.id, is_deleted=True) == 1
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


# [claude] WOT-SD-11
def test_wot_sd_11__one_update_of_one_work_order_type_and_no_other_statement_writes(db, u2, mk_row):
    """WOT-SD-11 — one UPDATE of one work order type, and no other statement writes.
    Rules: `soft_delete` Side effects"""
    a = mk_row()
    b = mk_row(name="Install")
    before_b = snap(db, b)

    with StatementRecorder(db) as recorder:
        result = dao.soft_delete(db, db_obj=a, deleted_by=u2.id)
    written = recorder.written()

    # Then 1
    assert result is a
    # Then 2
    assert len(written) == 1
    # Then 3
    assert written[0].startswith("UPDATE work_order_types")
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] WOT-SD-12
def test_wot_sd_12__a_row_already_deleted_with_deleted_by_none_the_old_deleter_is_overwrit(db, mk_row):
    """WOT-SD-12 — a row already deleted, with deleted_by=None: the old deleter is overwritten.
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
# DAOWorkOrderType.restore
# --------------------------------------------------------------------------- #


# [claude] WOT-RS-01
def test_wot_rs_01__clears_the_three_stamps_and_returns_the_same_row(db, mk_row):
    """WOT-RS-01 — clears the three stamps and returns the same row.
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


# [claude] WOT-RS-02
def test_wot_rs_02__a_row_soft_deleted_through_the_dao_comes_back(db, u2, mk_row):
    """WOT-RS-02 — a row soft-deleted through the DAO comes back.
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


# [claude] WOT-RS-03
def test_wot_rs_03__nothing_else_changes_and_nobody_is_recorded(db, u2, u3, mk_row):
    """WOT-RS-03 — nothing else changes, and nobody is recorded.
    Rules: `restore` R2"""
    a = mk_row(gone=True, created_by=u2.id, updated_by=u3.id)
    before_a = snap(db, a)

    result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.name == "Repair"
    assert row.is_active is True
    # Then 3
    row = reread(db, a)
    assert row.created_by == u2.id
    assert row.updated_by == u3.id
    # Then 4
    db.expire_all()
    assert without(snap(db, a), "is_deleted", "deleted_at", "deleted_by", "updated_at") == without(before_a, "is_deleted", "deleted_at", "deleted_by", "updated_at")


# [claude] WOT-RS-04
def test_wot_rs_04__an_inactive_row_stays_inactive_and_empty_stamps_stay_empty(db, mk_row):
    """WOT-RS-04 — an inactive row stays inactive, and empty stamps stay empty.
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


# [claude] WOT-RS-05
def test_wot_rs_05__updated_at_goes_from_null_to_a_value(db, mk_row):
    """WOT-RS-05 — updated_at goes from NULL to a value.
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


# [claude] WOT-RS-06
def test_wot_rs_06__the_restore_is_flushed_not_committed_a_rollback_brings_the_deleted_sta(db, u1, mk_row):
    """WOT-RS-06 — the restore is flushed, not committed: a rollback brings the deleted state back.
    Rules: `restore` R3, Side effects"""
    a = mk_row(gone=True)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.restore(db, db_obj=a)

    # Then 1
    assert result is a
    # Then 2
    assert count_rows(db, "work_order_types", id=a.id, is_deleted=False) == 1
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


# [claude] WOT-RS-07
def test_wot_rs_07__a_live_row_is_accepted_and_nothing_is_sent(db, u1, mk_row):
    """WOT-RS-07 — a live row is accepted and nothing is sent.
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


# [claude] WOT-RS-08
def test_wot_rs_08__a_row_of_another_workspace_is_restored(db, w2, mk_row):
    """WOT-RS-08 — a row of another workspace is restored.
    Rules: `restore` R5"""
    a = mk_row(gone=True)
    z = mk_row(gone=True, workspace_id=w2.id, name="Install")
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


# [claude] WOT-RS-09
def test_wot_rs_09__one_update_of_one_work_order_type_and_no_other_statement_writes(db, mk_row):
    """WOT-RS-09 — one UPDATE of one work order type, and no other statement writes.
    Rules: `restore` Side effects"""
    a = mk_row(gone=True)
    b = mk_row(gone=True, name="Install")
    before_b = snap(db, b)

    with StatementRecorder(db) as recorder:
        result = dao.restore(db, db_obj=a)
    written = recorder.written()

    # Then 1
    assert result is a
    # Then 2
    assert len(written) == 1
    # Then 3
    assert written[0].startswith("UPDATE work_order_types")
    # Then 4
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] WOT-RS-10
@pytest.mark.xfail(strict=True, reason="BUG-1214: A deleted work order type's name cannot be used again")
def test_wot_rs_10__restoring_next_to_a_live_row_of_that_name_is_refused_the_case_differin(db, u1, mk_row):
    """WOT-RS-10 — restoring next to a live row of that name is refused, the case differing.
    Rules: `restore` R6 [BUG-1214], Errors row 1"""
    a = mk_row(gone=True, name="Dup")
    b = mk_row(name="dup")
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


# [claude] WOT-RS-11
def test_wot_rs_11__a_live_row_of_that_name_in_another_workspace_does_not_block_a_restore(db, w2, mk_row):
    """WOT-RS-11 — a live row of that name in another workspace does not block a restore.
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


# [claude] WOT-RS-12
def test_wot_rs_12__another_deleted_row_of_that_name_the_case_differing_does_not_block_a_r(db, mk_row):
    """WOT-RS-12 — another deleted row of that name, the case differing, does not block a restore.
    Rules: `restore` R6"""
    a = mk_row(gone=True, name="Dup")
    b = mk_row(gone=True, name="dup")
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


# --------------------------------------------------------------------------- #
# Inherited BaseDAO.create on work_order_types
# --------------------------------------------------------------------------- #


# [claude] WOT-IN-01
def test_wot_in_01__a_second_live_row_of_one_name_is_refused(db, w1, mk_row):
    """WOT-IN-01 — a second live row of one name is refused.
    Rules: `create` N1"""
    a = mk_row()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Repair"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "work_order_types", workspace_id=w1.id, name="Repair") == 1
    # Then 4
    db.refresh(a)
    assert snap(db, a) == before_a


# [claude] WOT-IN-02
@pytest.mark.xfail(strict=True, reason="BUG-1214: A deleted work order type's name cannot be used again")
def test_wot_in_02__a_name_held_only_by_a_soft_deleted_row_can_be_used_again(db, w1, mk_row):
    """WOT-IN-02 — a name held only by a soft-deleted row can be used again.
    Rules: `create` N2 [BUG-1214]"""
    a = mk_row(gone=True)
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Repair"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Repair"
    assert row.is_deleted is False
    # Then 3
    assert count_rows(db, "work_order_types", workspace_id=w1.id, name="Repair") == 2
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOT-IN-03
@pytest.mark.xfail(strict=True, reason="BUG-1214: A deleted work order type's name cannot be used again")
def test_wot_in_03__names_that_differ_only_in_case_collide_among_live_rows(db, w1, mk_row):
    """WOT-IN-03 — names that differ only in case collide among live rows.
    Rules: `create` N3 [BUG-1214]"""
    a = mk_row(name="Same")
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "same"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "work_order_types", workspace_id=w1.id) == 1
    # Then 4
    db.refresh(a)
    assert snap(db, a) == before_a


# [claude] WOT-IN-04
@pytest.mark.xfail(strict=True, reason="BUG-1214: A deleted work order type's name cannot be used again")
def test_wot_in_04__names_that_differ_only_in_outer_spaces_collide_among_live_rows(db, w1, mk_row):
    """WOT-IN-04 — names that differ only in outer spaces collide among live rows.
    Rules: `create` N3 [BUG-1214]"""
    a = mk_row(name="Same")
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": " Same "})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "work_order_types", workspace_id=w1.id) == 1
    # Then 4
    db.refresh(a)
    assert snap(db, a) == before_a


# [claude] WOT-IN-05
def test_wot_in_05__the_same_name_in_another_workspace_is_stored(db, w2, mk_row):
    """WOT-IN-05 — the same name in another workspace is stored.
    Rules: `create` N1"""
    a = mk_row()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w2.id, "name": "Repair"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.name == "Repair"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOT-IN-06
def test_wot_in_06__another_name_in_the_same_workspace_is_stored(db, w1, mk_row):
    """WOT-IN-06 — another name in the same workspace is stored.
    Rules: `create` N1"""
    a = mk_row()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Install"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Install"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a
