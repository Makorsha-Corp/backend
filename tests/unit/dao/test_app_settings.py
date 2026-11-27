"""Unit tests for app/dao/app_settings.py.

Implements tests/unit/dao/app_settings.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.app_settings import app_settings_dao
from app.models.app_settings import AppSettings
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton app_settings_dao" (a module-level name, not a fixture)
dao = app_settings_dao


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


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "setting"
@pytest.fixture
def mk_setting(db, w1):
    """mk_setting(**columns) -> AppSettings. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "name": "feat", "enabled": True}
        fields.update(columns)
        return _add(db, AppSettings(**fields))
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


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one()


# Convention "nothing written": the number of `app_settings` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(AppSettings.__table__))


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
# DAOAppSettings.get_by_name
# --------------------------------------------------------------------------- #


# [claude] ASG-GN-01
def test_asg_gn_01__returns_the_row_with_that_name_not_the_workspace_s_first_row(db, w1, mk_setting):
    """ASG-GN-01 — returns the row with that name, not the workspace's first row.
    Rules: `get_by_name` R1, Returns"""
    mk_setting(name="alpha", enabled=False)
    a = mk_setting()

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, AppSettings)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "feat"
    assert result.workspace_id == w1.id
    # Then 4
    assert result.enabled is True


# [claude] ASG-GN-02
def test_asg_gn_02__a_switched_off_flag_is_returned_too(db, w1, mk_setting):
    """ASG-GN-02 — a switched-off flag is returned too.
    Rules: `get_by_name` R1"""
    a = mk_setting(enabled=False)

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.enabled is False


# [claude] ASG-GN-03
def test_asg_gn_03__an_earlier_row_of_the_same_name_in_another_workspace_is_not_returned(db, w1, w2, mk_setting):
    """ASG-GN-03 — an earlier row of the same name in another workspace is not returned.
    Rules: `get_by_name` R2"""
    mk_setting(workspace_id=w2.id)
    a = mk_setting()

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.workspace_id == w1.id


# [claude] ASG-GN-04
def test_asg_gn_04__the_name_under_another_workspace_returns_none(db, w2, mk_setting):
    """ASG-GN-04 — the name under another workspace returns None.
    Rules: `get_by_name` R2"""
    mk_setting()

    result = dao.get_by_name(db, name="feat", workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-05
def test_asg_gn_05__workspace_id_0_returns_none(db, mk_setting):
    """ASG-GN-05 — workspace_id=0 returns None.
    Rules: `get_by_name` R2"""
    mk_setting()

    result = dao.get_by_name(db, name="feat", workspace_id=0)

    # Then 1
    assert result is None


# [claude] ASG-GN-06
def test_asg_gn_06__capitals_do_not_find_a_lower_case_name(db, w1, mk_setting):
    """ASG-GN-06 — capitals do not find a lower-case name.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="FEAT", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-07
def test_asg_gn_07__a_leading_space_finds_nothing(db, w1, mk_setting):
    """ASG-GN-07 — a leading space finds nothing.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name=" feat", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-08
def test_asg_gn_08__a_trailing_space_finds_nothing(db, w1, mk_setting):
    """ASG-GN-08 — a trailing space finds nothing.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="feat ", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-09
def test_asg_gn_09__is_no_wildcard(db, w1, mk_setting):
    """ASG-GN-09 — % is no wildcard.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="fe%", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-10
def test_asg_gn_10__an_empty_name_returns_none(db, w1, mk_setting):
    """ASG-GN-10 — an empty name returns None.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-11
def test_asg_gn_11__a_none_name_returns_none(db, w1, mk_setting):
    """ASG-GN-11 — a None name returns None.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name=None, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-12
def test_asg_gn_12__writes_nothing_a_pending_row_stays_pending_and_is_not_found(db, w1, mk_setting):
    """ASG-GN-12 — writes nothing: a pending row stays pending and is not found.
    Rules: `get_by_name` R3, Side effects"""
    a = mk_setting()
    p = AppSettings(workspace_id=w1.id, name="pending", enabled=True)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_name(db, name="pending", workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert stored_count(db) == before
    # Then 6
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 7
    assert written == []


# [claude] ASG-GN-13
def test_asg_gn_13__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, mk_setting):
    """ASG-GN-13 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_name` Side effects"""
    a = mk_setting()
    p = AppSettings(workspace_id=w1.id, name="pending", enabled=True)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_name(db, name="feat", workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert stored_count(db) == before
    # Then 5
    assert written == []


# [claude] ASG-GN-14
def test_asg_gn_14__the_start_of_a_name_finds_nothing(db, w1, mk_setting):
    """ASG-GN-14 — the start of a name finds nothing.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="fe", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-15
def test_asg_gn_15__the_end_of_a_name_finds_nothing(db, w1, mk_setting):
    """ASG-GN-15 — the end of a name finds nothing.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="at", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-16
def test_asg_gn_16__is_no_wildcard(db, w1, mk_setting):
    """ASG-GN-16 — _ is no wildcard.
    Rules: `get_by_name` R3"""
    mk_setting()

    result = dao.get_by_name(db, name="fe_t", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-17
def test_asg_gn_17__a_stored_name_in_another_case_is_not_found_the_stored_side_is_not_norm(db, w1, mk_setting):
    """ASG-GN-17 — a stored name in another case is not found: the stored side is not normalised.
    Rules: `get_by_name` R3, R4"""
    mk_setting(name="Feat")

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-18
def test_asg_gn_18__a_stored_name_with_a_space_is_not_found_the_stored_side_is_not_trimmed(db, w1, mk_setting):
    """ASG-GN-18 — a stored name with a space is not found: the stored side is not trimmed.
    Rules: `get_by_name` R3, R4"""
    mk_setting(name=" feat")

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASG-GN-19
def test_asg_gn_19__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_setting):
    """ASG-GN-19 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_name` Side effects"""
    a = mk_setting()
    b = mk_setting(name="beta")
    b.enabled = False

    result = dao.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# Inherited BaseDAO.create on app_settings
# --------------------------------------------------------------------------- #


# [claude] ASG-CR-01
@pytest.mark.xfail(strict=True, reason="BUG-1225: One workspace can hold two settings of one name")
def test_asg_cr_01__a_second_row_of_one_name_in_one_workspace_is_refused(db, w1, mk_setting):
    """ASG-CR-01 — a second row of one name in one workspace is refused.
    Rules: `create` N1 [BUG-1225]; `get_by_name` R4 [BUG-1225]"""
    a = mk_setting()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "feat", "enabled": False})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "app_settings", workspace_id=w1.id, name="feat") == 1
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ASG-CR-02
@pytest.mark.xfail(strict=True, reason="BUG-1225: One workspace can hold two settings of one name")
def test_asg_cr_02__the_compare_is_case_insensitive_after_trimming(db, w1, mk_setting):
    """ASG-CR-02 — the compare is case-insensitive after trimming.
    Rules: `create` N2 [BUG-1225]; `get_by_name` R4 [BUG-1225]"""
    a = mk_setting(name="Feat")
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": " feat ", "enabled": False})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "app_settings", workspace_id=w1.id) == 1
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ASG-CR-03
def test_asg_cr_03__the_same_name_in_another_workspace_is_stored(db, w2, mk_setting):
    """ASG-CR-03 — the same name in another workspace is stored.
    Rules: `create` N1"""
    a = mk_setting()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w2.id, "name": "feat", "enabled": False})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.name == "feat"
    assert row.enabled is False
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ASG-CR-04
def test_asg_cr_04__another_name_in_the_same_workspace_is_stored(db, w1, mk_setting):
    """ASG-CR-04 — another name in the same workspace is stored.
    Rules: `create` N1"""
    a = mk_setting()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "feat two", "enabled": False})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "feat two"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a
