"""Unit tests for app/services/app_settings_service.py.

Implements tests/unit/services/app_settings_service.cases.md (revision 1), one
test per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the service's commits are safe and the fixture's
outer rollback discards everything. Nothing is patched except what Conventions
name: the failing commit / failing refresh wraps and the commit / rollback
spies (both still call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (A -> a, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
import re
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError

from app.models.app_settings import AppSettings
from app.schemas.app_settings import (
    AppSettingsBase,
    AppSettingsCreate,
    AppSettingsUpdate,
)
from app.services.app_settings_service import app_settings_service
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants and actors
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton app_settings_service"
svc = app_settings_service

MISSING = 999999999


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# W1, W2 exist in every test
@pytest.fixture(autouse=True)
def actors(w2):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "setting": one row, flushed
@pytest.fixture
def mk_setting(db, w1):
    def _mk(**but):
        fields = {"workspace_id": w1.id, "name": "feat", "enabled": True}
        fields.update(but)
        row = AppSettings(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(AppSettings).where(AppSettings.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = AppSettings.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


# Convention "count:" lines: app_settings rows (all workspaces), with the filter stated
def count_settings(db, **filters):
    query = select(func.count()).select_from(AppSettings)
    for column, value in filters.items():
        query = query.where(getattr(AppSettings, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_settings(db)


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# Convention "Statement recorder": the statements the session sends during the When
@contextmanager
def record_sql(db):
    connection = db.connection()
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


# Convention "sql" = the one SELECT from app_settings
def the_select(sql_log):
    [sql] = [s for s in sql_log if s.lstrip().upper().startswith("SELECT") and "app_settings" in s]
    return sql


# Convention "order_part" = the text after ORDER BY and before LIMIT ("" when there is none)
def order_part_of(sql):
    if "ORDER BY" not in sql:
        return ""
    after = sql.split("ORDER BY", 1)[1]
    return after.split("LIMIT", 1)[0].strip()


# --------------------------------------------------------------------------- #
# AppSettingsService.get_settings
# --------------------------------------------------------------------------- #

# [claude] ASV-L-01
def test_asv_l_01__only_the_workspaces_settings_are_listed(db, w1, w2, mk_setting):
    """ASV-L-01 — only the workspace's settings are listed.
    Rules: `get_settings` R1"""
    mk_setting(workspace_id=w2.id, name="early")
    a = mk_setting()
    b = mk_setting(name="beta")
    mk_setting(workspace_id=w2.id, name="late")
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] ASV-L-02
def test_asv_l_02__limit_0_gives_an_empty_list(db, w1, mk_setting):
    """ASV-L-02 — limit=0 gives an empty list.
    Rules: `get_settings` R1"""
    mk_setting()
    mk_setting(name="beta")
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ASV-L-03
def test_asv_l_03__limit_1_gives_one_setting(db, w1, mk_setting):
    """ASV-L-03 — limit=1 gives one setting.
    Rules: `get_settings` R1"""
    mk_setting()
    mk_setting(name="beta")
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] ASV-L-04
def test_asv_l_04__skip_1_with_limit_1000_gives_the_rest(db, w1, mk_setting):
    """ASV-L-04 — skip=1 with limit=1000 gives the rest.
    Rules: `get_settings` R1"""
    mk_setting()
    mk_setting(name="beta")
    mk_setting(name="gamma")
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id, skip=1, limit=1000)

    # Then 1
    assert len(result) == 2


# [claude] ASV-L-05
@pytest.mark.xfail(strict=False, reason="BUG-1525: App settings list has no display order")
def test_asv_l_05__settings_come_by_name_case_insensitive_ascending(db, w1, mk_setting):
    """ASV-L-05 — settings come by name, case-insensitive ascending.
    Rules: `get_settings` R2 [BUG-1525]"""
    z = mk_setting(name="zeta")
    a = mk_setting(name="Alpha")
    b = mk_setting(name="beta")
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [z.id, a.id, b.id]
    # Then 2
    assert [r.name for r in result] == ["Alpha", "beta", "zeta"]


# [claude] ASV-L-06
@pytest.mark.xfail(strict=True, reason="BUG-1525: App settings list has no display order")
def test_asv_l_06__the_query_orders_by_lower_name_then_id_last_before_the_page(db, w1, mk_setting):
    """ASV-L-06 — the query orders by lower(name), then id last, before the page.
    Rules: `get_settings` R2 [BUG-1525]"""
    a = mk_setting()
    commit_point(db)
    with record_sql(db) as sql_log:
        result = svc.get_settings(db, workspace_id=w1.id, skip=0, limit=10)
    sql = the_select(sql_log)
    order_part = order_part_of(sql)

    # Then 1
    assert [r.id for r in result] == [a.id]
    # Then 2
    assert "lower(" in order_part.lower()
    # Then 3
    assert "ORDER BY" in sql
    # Then 4
    assert order_part.lower().index("name") < order_part.lower().index(".id")
    # Then 5
    assert re.search(r"\.id(\s+asc)?\s*$", order_part, re.IGNORECASE) is not None
    # Then 6
    assert sql.index("ORDER BY") < sql.index("LIMIT")


# [claude] ASV-L-07
def test_asv_l_07__a_negative_limit_raises_dataerror_and_leaves_the_session_aborted(db, w1, mk_setting):
    """ASV-L-07 — a negative limit raises DataError and leaves the session aborted.
    Rules: `get_settings` R3, Errors; S5"""
    mk_setting()
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        svc.get_settings(db, workspace_id=w1.id, limit=-1)
    # Then 2
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT 1"))


# [claude] ASV-L-08
def test_asv_l_08__the_list_neither_commits_nor_rolls_back(db, w1, w2, mk_setting):
    """ASV-L-08 — the list neither commits nor rolls back.
    Rules: `get_settings` R3; S5"""
    a = mk_setting()
    b = mk_setting(workspace_id=w2.id, name="other")
    commit_point(db)
    p = mk_setting(name="pending")
    b.enabled = False
    with spies(db) as (cm, rb):
        result = svc.get_settings(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == sorted([a.id, p.id])
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    db.rollback()
    assert count_settings(db, name="pending") == 0


# [claude] ASV-L-09
def test_asv_l_09__with_the_default_limit_101_settings_give_100(db, w1):
    """ASV-L-09 — with the default limit 101 settings give 100.
    Rules: `get_settings` R1"""
    db.add_all([AppSettings(workspace_id=w1.id, name=f"s{k:03d}", enabled=True) for k in range(101)])
    db.flush()
    commit_point(db)
    result = svc.get_settings(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# --------------------------------------------------------------------------- #
# AppSettingsService.get_by_id
# --------------------------------------------------------------------------- #

# [claude] ASV-G-01
def test_asv_g_01__the_setting_of_that_id_in_that_workspace_is_returned(db, w1, mk_setting):
    """ASV-G-01 — the setting of that id in that workspace is returned.
    Rules: `get_by_id` R1"""
    a = mk_setting(enabled=False)
    commit_point(db)
    result = svc.get_by_id(db, setting_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, AppSettings)
    # Then 2
    assert result.id == a.id
    assert result.name == "feat"
    assert result.enabled is False


# [claude] ASV-G-02
def test_asv_g_02__another_workspaces_id_returns_none(db, w1, w2, mk_setting):
    """ASV-G-02 — another workspace's id returns None.
    Rules: `get_by_id` R2"""
    mk_setting()
    z = mk_setting(workspace_id=w2.id)
    commit_point(db)
    result = svc.get_by_id(db, setting_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASV-G-03
def test_asv_g_03__id_0_returns_none_no_error(db, w1, mk_setting):
    """ASV-G-03 — id 0 returns None, no error.
    Rules: `get_by_id` R2"""
    mk_setting()
    commit_point(db)
    result = svc.get_by_id(db, setting_id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASV-G-04
def test_asv_g_04__the_read_neither_commits_nor_rolls_back(db, w1, mk_setting):
    """ASV-G-04 — the read neither commits nor rolls back.
    Rules: `get_by_id` R3; S5"""
    mk_setting()
    b = mk_setting(name="other")
    commit_point(db)
    mk_setting(name="pending")
    b.enabled = False
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, setting_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    db.rollback()
    assert count_settings(db, name="pending") == 0


# --------------------------------------------------------------------------- #
# AppSettingsService.get_by_name
# --------------------------------------------------------------------------- #

# [claude] ASV-N-01
def test_asv_n_01__an_exact_name_returns_the_workspaces_setting(db, w1, w2, mk_setting):
    """ASV-N-01 — an exact name returns the workspace's setting.
    Rules: `get_by_name` R1"""
    mk_setting(workspace_id=w2.id)
    a = mk_setting()
    commit_point(db)
    result = svc.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] ASV-N-02
def test_asv_n_02__the_name_in_capitals_finds_nothing(db, w1, mk_setting):
    """ASV-N-02 — the name in capitals finds nothing.
    Rules: `get_by_name` R1"""
    mk_setting()
    commit_point(db)
    result = svc.get_by_name(db, name="FEAT", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASV-N-03
def test_asv_n_03__another_workspaces_name_finds_nothing(db, w1, w2, mk_setting):
    """ASV-N-03 — another workspace's name finds nothing.
    Rules: `get_by_name` R1"""
    mk_setting(workspace_id=w2.id, name="beta")
    mk_setting()
    commit_point(db)
    result = svc.get_by_name(db, name="beta", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ASV-N-04
def test_asv_n_04__the_read_neither_commits_nor_rolls_back(db, w1, mk_setting):
    """ASV-N-04 — the read neither commits nor rolls back.
    Rules: `get_by_name` R2; S5"""
    a = mk_setting()
    b = mk_setting(name="other")
    commit_point(db)
    mk_setting(name="pending")
    b.enabled = False
    with spies(db) as (cm, rb):
        result = svc.get_by_name(db, name="feat", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    db.rollback()
    assert count_settings(db, name="pending") == 0


# --------------------------------------------------------------------------- #
# AppSettingsService.create_setting
# --------------------------------------------------------------------------- #

# [claude] ASV-C-01
def test_asv_c_01__a_new_setting_is_committed_and_returned_re_read(db, w1):
    """ASV-C-01 — a new setting is committed and returned re-read.
    Rules: `create_setting` R1; S1, S3"""
    commit_point(db)
    result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=False), workspace_id=w1.id)

    # Then 1
    assert "id" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "enabled" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    # Then 2
    assert isinstance(result, AppSettings)
    # Then 3
    assert result.id is not None
    assert result.name == "feat"
    assert result.enabled is False
    assert result.workspace_id == w1.id
    # Then 4
    result_id = result.id
    db.rollback()
    row = db.execute(select(AppSettings).where(AppSettings.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "feat"
    assert row.enabled is False
    assert row.workspace_id == w1.id
    # Then 5
    assert count_settings(db, workspace_id=w1.id) == 1


# [claude] ASV-C-02
def test_asv_c_02__no_acting_user_is_recorded_the_table_has_no_such_column(db, w1):
    """ASV-C-02 — no acting user is recorded: the table has no such column.
    Rules: `create_setting` R2"""
    commit_point(db)
    result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=w1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert not any(c.name in ("created_by", "updated_by", "user_id") for c in AppSettings.__table__.columns)


# [claude] ASV-C-03
@pytest.mark.xfail(strict=True, reason="BUG-1524: App setting names are stored untrimmed, and blank names are accepted")
def test_asv_c_03__a_whitespace_only_name_is_refused_by_the_schema(db, w1):
    """ASV-C-03 — a whitespace-only name is refused by the schema.
    Rules: `create_setting` R3 [BUG-1524], Errors"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AppSettingsCreate(name="   ", enabled=True)
    # Then 2
    assert written(db) == before


# [claude] ASV-C-04
@pytest.mark.xfail(strict=True, reason="BUG-1524: App setting names are stored untrimmed, and blank names are accepted")
def test_asv_c_04__a_padded_name_is_stored_trimmed(db, w1):
    """ASV-C-04 — a padded name is stored trimmed.
    Rules: `create_setting` R3 [BUG-1524]"""
    data = AppSettingsCreate(name=" Feat ", enabled=True)
    commit_point(db)
    result = svc.create_setting(db, setting_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(AppSettings).where(AppSettings.id == result_id)).scalar_one()
    assert row.name == "Feat"


# [claude] ASV-C-05
def test_asv_c_05__the_base_schema_still_reads_a_blank_name(db, w1):
    """ASV-C-05 — the base schema still reads a blank name.
    Rules: `create_setting` R3"""
    commit_point(db)
    data = AppSettingsBase(name="   ", enabled=True)

    # Then 1
    assert data.name == "   "


# [claude] ASV-C-06
@pytest.mark.xfail(strict=True, reason="BUG-1225: One workspace can hold two settings of one name")
def test_asv_c_06__a_name_already_used_in_the_workspace_is_refused_by_the_database_after_the_rollback(
    db, w1, mk_setting,
):
    """ASV-C-06 — a name already used in the workspace is refused by the database after the rollback.
    Rules: `create_setting` R4 [BUG-1225], Errors"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=False), workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_settings(db, workspace_id=w1.id) == 1
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert usable(db)


# [claude] ASV-C-07
@pytest.mark.xfail(strict=True, reason="BUG-1225: One workspace can hold two settings of one name")
def test_asv_c_07__the_same_name_in_other_case_and_with_spaces_collides_too(db, w1, mk_setting):
    """ASV-C-07 — the same name in other case and with spaces collides too.
    Rules: `create_setting` R4 [BUG-1225], Errors"""
    mk_setting()
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_setting(db, setting_in=AppSettingsCreate(name=" FEAT ", enabled=False), workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_settings(db, workspace_id=w1.id) == 1


# [claude] ASV-C-08
def test_asv_c_08__the_same_name_in_another_workspace_is_stored(db, w1, w2, mk_setting):
    """ASV-C-08 — the same name in another workspace is stored.
    Rules: `create_setting` R4"""
    z = mk_setting(workspace_id=w2.id)
    commit_point(db)
    result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=w1.id)

    # Then 1
    assert result.workspace_id == w1.id
    # Then 2
    db.rollback()
    assert count_settings(db, name="feat") == 2
    # Then 3
    row = reread(db, z)
    assert row.workspace_id == w2.id
    assert row.name == "feat"


# [claude] ASV-C-09
def test_asv_c_09__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, mk_setting,
):
    """ASV-C-09 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `create_setting` R5; S2"""
    mk_setting(name="other")
    commit_point(db)
    before = written(db)
    mk_setting(name="extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_settings(db, name="feat") == 0
    # Then 4
    assert count_settings(db, name="extra") == 0
    # Then 5
    assert written(db) == before


# [claude] ASV-C-10
def test_asv_c_10__a_failing_re_read_after_the_commit_leaves_the_setting_saved(db, w1):
    """ASV-C-10 — a failing re-read after the commit leaves the setting saved.
    Rules: `create_setting` R5; S3"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_settings(db, workspace_id=w1.id, name="feat") == 1


# [claude] ASV-C-11
def test_asv_c_11__a_database_error_at_the_flush_is_rolled_back_and_passed_on_the_session_is_usable(
    db, w1, mk_setting,
):
    """ASV-C-11 — a database error at the flush is rolled back and passed on; the session is usable.
    Rules: `create_setting` R5, Errors; S2"""
    mk_setting(name="other")
    data = AppSettingsCreate.model_construct(name=None, enabled=True)
    commit_point(db)
    before = written(db)
    mk_setting(name="extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_setting(db, setting_in=data, workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_settings(db, name="extra") == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# --------------------------------------------------------------------------- #
# AppSettingsService.update_setting
# --------------------------------------------------------------------------- #

# [claude] ASV-U-01
def test_asv_u_01__enabled_is_written_committed_and_returned_re_read(db, w1, mk_setting):
    """ASV-U-01 — enabled is written, committed and returned re-read.
    Rules: `update_setting` R2; S1, S3"""
    a = mk_setting()
    commit_point(db)
    result = svc.update_setting(db, setting_id=a.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=w1.id)

    # Then 1
    assert "enabled" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    assert result.enabled is False
    # Then 3
    db.rollback()
    row = reread(db, a)
    assert row.enabled is False
    assert row.name == "feat"


# [claude] ASV-U-02
def test_asv_u_02__another_workspaces_id_returns_none_writes_nothing_neither_commits_nor_rolls_back(
    db, w1, w2, mk_setting,
):
    """ASV-U-02 — another workspace's id returns None, writes nothing, neither commits nor rolls back.
    Rules: `update_setting` R1; S4"""
    mk_setting()
    z = mk_setting(workspace_id=w2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    mk_setting(name="extra")
    with spies(db) as (cm, rb):
        result = svc.update_setting(
            db, setting_id=z.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=w1.id,
        )

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_settings(db, name="extra") == 1
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    db.rollback()
    assert count_settings(db, name="extra") == 0


# [claude] ASV-U-03
def test_asv_u_03__id_0_returns_none(db, w1, mk_setting):
    """ASV-U-03 — id 0 returns None.
    Rules: `update_setting` R1"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.update_setting(db, setting_id=0, setting_in=AppSettingsUpdate(enabled=False), workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, a) == before_a


# [claude] ASV-U-04
def test_asv_u_04__enabled_omitted_leaves_the_setting_unchanged_and_returns_it(db, w1, mk_setting):
    """ASV-U-04 — enabled omitted leaves the setting unchanged and returns it.
    Rules: `update_setting` R3"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.update_setting(db, setting_id=a.id, setting_in=AppSettingsUpdate(), workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    assert result.enabled is True
    # Then 2
    assert snap(db, a) == before_a


# [claude] ASV-U-05
def test_asv_u_05__enabled_null_leaves_the_setting_unchanged_and_returns_it(db, w1, mk_setting):
    """ASV-U-05 — enabled null leaves the setting unchanged and returns it.
    Rules: `update_setting` R3"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.update_setting(db, setting_id=a.id, setting_in=AppSettingsUpdate(enabled=None), workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    assert result.enabled is True
    # Then 2
    assert snap(db, a) == before_a


# [claude] ASV-U-06
def test_asv_u_06__a_name_in_the_body_is_ignored(db, w1, mk_setting):
    """ASV-U-06 — a name in the body is ignored.
    Rules: `update_setting` R3"""
    a = mk_setting()
    data = AppSettingsUpdate.model_validate({"name": "renamed", "enabled": False})
    commit_point(db)
    result = svc.update_setting(db, setting_id=a.id, setting_in=data, workspace_id=w1.id)

    # Then 1
    assert result.enabled is False
    # Then 2
    db.rollback()
    row = reread(db, a)
    assert row.name == "feat"
    assert row.enabled is False


# [claude] ASV-U-07
def test_asv_u_07__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, mk_setting,
):
    """ASV-U-07 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `update_setting` R4; S2"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_setting(name="extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_setting(db, setting_id=a.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert count_settings(db, name="extra") == 0


# --------------------------------------------------------------------------- #
# AppSettingsService.delete_setting
# --------------------------------------------------------------------------- #

# [claude] ASV-D-01
def test_asv_d_01__a_found_setting_is_hard_deleted_and_committed_true_is_returned(db, w1, mk_setting):
    """ASV-D-01 — a found setting is hard-deleted and committed; True is returned.
    Rules: `delete_setting` R2; S1"""
    a = mk_setting()
    b = mk_setting(name="other")
    a_id = a.id
    commit_point(db)
    result = svc.delete_setting(db, setting_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert count_settings(db, id=a_id) == 0
    # Then 3
    assert reread(db, b).name == "other"


# [claude] ASV-D-02
def test_asv_d_02__another_workspaces_id_returns_false_its_row_stays_neither_commit_nor_rollback(
    db, w1, w2, mk_setting,
):
    """ASV-D-02 — another workspace's id returns False; its row stays; neither commit nor rollback.
    Rules: `delete_setting` R1; S4"""
    mk_setting()
    z = mk_setting(workspace_id=w2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    mk_setting(name="extra")
    with spies(db) as (cm, rb):
        result = svc.delete_setting(db, setting_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_settings(db, name="extra") == 1
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    db.rollback()
    assert count_settings(db, name="extra") == 0


# [claude] ASV-D-03
def test_asv_d_03__id_0_returns_false(db, w1, mk_setting):
    """ASV-D-03 — id 0 returns False.
    Rules: `delete_setting` R1"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.delete_setting(db, setting_id=0, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert snap(db, a) == before_a


# [claude] ASV-D-04
def test_asv_d_04__a_failing_commit_is_rolled_back_and_re_raised_the_setting_stays(db, w1, mk_setting):
    """ASV-D-04 — a failing commit is rolled back and re-raised: the setting stays.
    Rules: `delete_setting` R3; S2"""
    a = mk_setting()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_setting(name="extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_setting(db, setting_id=a.id, workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert count_settings(db, name="extra") == 0
