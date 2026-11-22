"""Unit tests for app/dao/workspace.py.

Implements tests/unit/dao/workspace.cases.md, one test per case, in card
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

from app.dao.workspace import workspace_dao
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.utils.time import utcnow
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton workspace_dao" (a module-level name, not a fixture)
dao = workspace_dao


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


# Convention "nothing written": the number of `workspaces` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(Workspace.__table__))


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
# WorkspaceDAO.get_by_slug
# --------------------------------------------------------------------------- #


# [claude] WSP-GS-01
def test_wsp_gs_01__returns_the_workspace_with_that_slug_not_the_first_workspace(db):
    """WSP-GS-01 — returns the workspace with that slug, not the first workspace.
    Rules: `get_by_slug` R1, Returns"""
    make_workspace(db, slug="beta-co")
    a = make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme-co")

    # Then 1
    assert isinstance(result, Workspace)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.slug == "acme-co"


# [claude] WSP-GS-02
def test_wsp_gs_02__capitals_do_not_find_a_lower_case_slug(db):
    """WSP-GS-02 — capitals do not find a lower-case slug.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="ACME-CO")

    # Then 1
    assert result is None


# [claude] WSP-GS-03
def test_wsp_gs_03__a_leading_space_finds_nothing(db):
    """WSP-GS-03 — a leading space finds nothing.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug=" acme-co")

    # Then 1
    assert result is None


# [claude] WSP-GS-04
def test_wsp_gs_04__a_trailing_space_finds_nothing(db):
    """WSP-GS-04 — a trailing space finds nothing.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme-co ")

    # Then 1
    assert result is None


# [claude] WSP-GS-05
def test_wsp_gs_05__a_mixed_case_slug_is_found_as_typed(db):
    """WSP-GS-05 — a mixed-case slug is found as typed.
    Rules: `get_by_slug` R2"""
    a = make_workspace(db, slug="MiXeD")

    result = dao.get_by_slug(db, slug="MiXeD")

    # Then 1
    assert result.id == a.id


# [claude] WSP-GS-06
def test_wsp_gs_06__a_mixed_case_slug_is_not_found_in_lower_case(db):
    """WSP-GS-06 — a mixed-case slug is not found in lower case.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="MiXeD")

    result = dao.get_by_slug(db, slug="mixed")

    # Then 1
    assert result is None


# [claude] WSP-GS-07
def test_wsp_gs_07__is_no_wildcard(db):
    """WSP-GS-07 — % is no wildcard.
    Rules: `get_by_slug` R3"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme%")

    # Then 1
    assert result is None


# [claude] WSP-GS-08
def test_wsp_gs_08__is_no_wildcard(db):
    """WSP-GS-08 — _ is no wildcard.
    Rules: `get_by_slug` R3"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme_co")

    # Then 1
    assert result is None


# [claude] WSP-GS-09
def test_wsp_gs_09__an_unknown_slug_returns_none(db):
    """WSP-GS-09 — an unknown slug returns None.
    Rules: `get_by_slug` R4"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="no-such-slug")

    # Then 1
    assert result is None


# [claude] WSP-GS-10
def test_wsp_gs_10__an_empty_slug_returns_none(db):
    """WSP-GS-10 — an empty slug returns None.
    Rules: `get_by_slug` R4"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="")

    # Then 1
    assert result is None


# [claude] WSP-GS-11
def test_wsp_gs_11__a_none_slug_returns_none(db):
    """WSP-GS-11 — a None slug returns None.
    Rules: `get_by_slug` R4"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug=None)

    # Then 1
    assert result is None


# [claude] WSP-GS-12
def test_wsp_gs_12__a_workspace_nobody_belongs_to_is_found(db):
    """WSP-GS-12 — a workspace nobody belongs to is found.
    Rules: `get_by_slug` R5"""
    a = make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme-co")

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, "workspace_members", workspace_id=a.id) == 0


# [claude] WSP-GS-13
def test_wsp_gs_13__a_workspace_whose_subscription_ended_is_found(db):
    """WSP-GS-13 — a workspace whose subscription ended is found.
    Rules: `get_by_slug` R5"""
    a = make_workspace(db, slug="acme-co", subscription_status="cancelled")

    result = dao.get_by_slug(db, slug="acme-co")

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.subscription_status == "cancelled"


# [claude] WSP-GS-14
def test_wsp_gs_14__writes_nothing_a_pending_row_stays_pending_and_is_not_found(db):
    """WSP-GS-14 — writes nothing: a pending row stays pending and is not found.
    Rules: `get_by_slug` R4, Side effects"""
    a = make_workspace(db, slug="acme-co")
    p = Workspace(name="Pending", slug="pending-co", subscription_plan_id=a.subscription_plan_id)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_slug(db, slug="pending-co")
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


# [claude] WSP-GS-15
def test_wsp_gs_15__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db):
    """WSP-GS-15 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_slug` Side effects"""
    a = make_workspace(db, slug="acme-co")
    p = Workspace(name="Pending", slug="pending-co", subscription_plan_id=a.subscription_plan_id)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_slug(db, slug="acme-co")
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


# [claude] WSP-GS-16
def test_wsp_gs_16__a_positional_slug_raises_typeerror(db):
    """WSP-GS-16 — a positional slug raises TypeError.
    Rules: `get_by_slug` Inputs"""
    make_workspace(db, slug="acme-co")
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.get_by_slug(db, "acme-co")
    # Then 2
    assert stored_count(db) == before


# [claude] WSP-GS-17
def test_wsp_gs_17__the_start_of_a_slug_finds_nothing(db):
    """WSP-GS-17 — the start of a slug finds nothing.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="acme")

    # Then 1
    assert result is None


# [claude] WSP-GS-18
def test_wsp_gs_18__the_end_of_a_slug_finds_nothing(db):
    """WSP-GS-18 — the end of a slug finds nothing.
    Rules: `get_by_slug` R2"""
    make_workspace(db, slug="acme-co")

    result = dao.get_by_slug(db, slug="co")

    # Then 1
    assert result is None


# [claude] WSP-GS-19
def test_wsp_gs_19__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db):
    """WSP-GS-19 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_slug` Side effects"""
    a = make_workspace(db, slug="acme-co")
    b = make_workspace(db, slug="beta-co")
    b.name = "Edited"

    result = dao.get_by_slug(db, slug="acme-co")

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# Inherited methods on workspaces
# --------------------------------------------------------------------------- #


# [claude] WSP-IN-01
def test_wsp_in_01__create_from_a_workspacecreate_raises_typeerror_and_adds_nothing(db):
    """WSP-IN-01 — create from a WorkspaceCreate raises TypeError and adds nothing.
    Rules: `inherited` N1"""

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.create(db, obj_in=WorkspaceCreate(name="Acme", slug="acme-co", billing_email="owner@example.com"))
    # Then 2
    assert "'owner_position' is an invalid keyword argument for Workspace" in str(exc.value)
    # Then 3
    assert len(db.new) == 0
    # Then 4
    assert count_rows(db, "workspaces", slug="acme-co") == 0


# [claude] WSP-IN-02
def test_wsp_in_02__a_second_row_with_one_slug_is_refused(db):
    """WSP-IN-02 — a second row with one slug is refused.
    Rules: `inherited` N2"""
    a = make_workspace(db, slug="acme-co")
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"name": "Other", "slug": "acme-co", "subscription_plan_id": a.subscription_plan_id})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "ix_workspaces_slug" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "workspaces", slug="acme-co") == 1
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WSP-IN-03
def test_wsp_in_03__a_row_with_another_slug_is_stored(db):
    """WSP-IN-03 — a row with another slug is stored.
    Rules: `inherited` N2"""
    a = make_workspace(db, slug="acme-co")
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"name": "Other", "slug": "acme-co-2", "subscription_plan_id": a.subscription_plan_id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.slug == "acme-co-2"
    assert row.name == "Other"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WSP-IN-04
def test_wsp_in_04__update_of_settings_replaces_the_whole_value_and_moves_updated_at(db):
    """WSP-IN-04 — update of settings replaces the whole value and moves updated_at.
    Rules: `inherited` N3"""
    a = make_workspace(db, slug="acme-co", settings={"a": 1})
    db.refresh(a)
    u0 = a.updated_at
    while utcnow() <= u0:  # Given 4: the clock moves in ticks, so the update must not share the insert's
        pass
    before_a = snap(db, a)

    result = dao.update(db, db_obj=a, obj_in=WorkspaceUpdate(settings={"b": 2}))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.settings == {"b": 2}
    # Then 3
    row = reread(db, a)
    assert row.updated_at != u0
    # Then 4
    row = reread(db, a)
    assert row.updated_at > row.created_at
    # Then 5
    db.expire_all()
    assert without(snap(db, a), "settings", "updated_at") == without(before_a, "settings", "updated_at")
