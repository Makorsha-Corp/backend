"""Unit tests for app/managers/factory_section_manager.py.

Implements tests/unit/managers/factory_section_manager.cases.md, one test per
case. Real Postgres session (`db` fixture). The only thing patched in every
test is the clock: `app.dao.factory_section.utcnow` returns NOW (Conventions,
Externals). The three race-simulation cards (FSM-C-29, U-50, U-51)
additionally patch the manager's own duplicate check, as Conventions allow.

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/managers/factory_section_manager.helpers.md as its only view of
this file; tests below a `# [claude] <ID>` comment are the `Author: claude`
cards, written by hand in the finishing step.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
)

from app.managers.factory_section_manager import (
    FactorySectionManager,
    factory_section_manager,
)
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton factory_section_manager" (a module-level name, not a fixture)
M = factory_section_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0", "NOW" (both naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the nine standing rows)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". Each fixture depends on the one
# before it, so the ids rise in the order Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 creates every Given row, U2 acts)
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, u1, name, abbreviation, workspace_id, **columns):
    fields = {"name": name, "abbreviation": abbreviation, "workspace_id": workspace_id,
              "created_by": u1.id, "is_active": True, "is_deleted": False,
              "deleted_at": None, "deleted_by": None}
    fields.update(columns)
    return _add(db, Factory(**fields))


# Convention "five factories rows (all created_by U1.id)": F1 (live, W1), F2 (second
# live factory of W1), F9 (the factory of W2), FD (soft-deleted, W1; is_active stays
# True), FI (live but inactive, W1)
@pytest.fixture
def f1(db, w1, u1, u2):
    return _factory(db, u1, "Main Plant", "MP", w1.id)


@pytest.fixture
def f2(db, w1, u1, f1):
    return _factory(db, u1, "North Yard", "NY", w1.id)


@pytest.fixture
def f9(db, w2, u1, f2):
    return _factory(db, u1, "Far Depot", "FR", w2.id)


@pytest.fixture
def fd(db, w1, u1, f9):
    return _factory(db, u1, "Old Plant", "OP", w1.id, is_deleted=True, deleted_at=T0, deleted_by=u1.id)


@pytest.fixture
def fi(db, w1, u1, fd):
    return _factory(db, u1, "Idle Plant", "IP", w1.id, is_active=False)


# Convention "These nine rows exist in every test and need no Given line" and
# Externals "app.dao.factory_section.utcnow is patched to return NOW in every test"
@pytest.fixture(autouse=True)
def standing_rows(monkeypatch, w1, w2, u1, u2, f1, f2, f9, fd, fi):
    monkeypatch.setattr("app.dao.factory_section.utcnow", lambda: NOW)


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Conventions "section" and "deleted" (said of a section)
@pytest.fixture
def mk_section(db, w1, u1, f1):
    """mk_section(name=..., **columns) -> FactorySection. Keywords only.

    `deleted=True` is the Conventions word "deleted": is_deleted True,
    deleted_at T0, deleted_by U1.id (is_active stays True). `created_at` is
    left to the database.
    """
    def _mk(*, name, deleted=False, **columns):
        fields = {
            "workspace_id": w1.id, "factory_id": f1.id, "name": name,
            "created_by": u1.id, "updated_by": None, "updated_at": None,
            "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None,
        }
        if deleted:
            fields.update(is_deleted=True, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, FactorySection(**fields))
    return _mk


# Convention "machine of F"
@pytest.fixture
def mk_machine(db):
    """mk_machine(of=<factory>, name=..., **columns) -> Machine. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name,
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "assignment of MA to S"
@pytest.fixture
def mk_assignment(db, u1):
    """mk_assignment(of=<machine>, to=<section>) -> MachineSectionAssignment. Keywords only."""
    def _mk(*, of, to):
        return _add(db, MachineSectionAssignment(workspace_id=of.workspace_id, machine_id=of.id,
                                                 factory_section_id=to.id, created_by=u1.id))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__
           for model in (FactorySection, Factory, Machine, MachineSectionAssignment)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id from its own table
def reread(db, row):
    """Fresh copy of `row` (section, factory, machine or assignment) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of the named table in all workspaces
def count_rows(db, table_name):
    return db.execute(select(func.count()).select_from(_TABLES[table_name])).scalar_one()


# Convention "nothing written": row counts of factory_sections, factories, machines
# and machine_section_assignments, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "rows_of_section(S)": expire_all, then every assignment row of S (any workspace)
def rows_of_section(db, section):
    db.expire_all()
    a = MachineSectionAssignment
    return list(db.execute(select(a).where(a.factory_section_id == _id_of(section))).scalars())


# Convention "ids(result)" / "names(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "Statement recorder" (Author: claude cards only): every SQL statement
# the session sends inside the block, lower-cased, whitespace collapsed to one space
@contextmanager
def recorded_sql(db):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.lower().split()))

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


def section_selects(statements):
    """The recorded SELECT statements that read factory_sections."""
    return [s for s in statements if s.startswith("select") and " from factory_sections" in s]


def where_clause(statement):
    """Convention "its WHERE clause": the text after the first ' where ' up to the
    next ' order by ', ' limit ', ' offset ' or the end, whichever comes first."""
    if " where " not in statement:
        return ""
    rest = statement.split(" where ", 1)[1]
    ends = [rest.find(word) for word in (" order by ", " limit ", " offset ") if word in rest]
    return rest[:min(ends)] if ends else rest


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in factory_section_manager.helpers.md)
# --------------------------------------------------------------------------- #

def test_fsm_c_01__create_stores_a_section_with_the_name_factory_workspace_and_creator(db, w1, u2, f1):
    """FSM-C-01 — create stores a section with the name, factory, workspace and creator given.
    Rules: `create_factory_section` R1, Returns, Side effects"""
    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, FactorySection)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 4
    assert row.workspace_id == w1.id
    # Then 5
    assert row.created_by == u2.id
    # Then 6
    assert count_rows(db, "factory_sections") == 1


@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_c_18__an_empty_name_is_rejected_by_factorysectioncreate(db, f1):
    """FSM-C-18 — an empty name is rejected by FactorySectionCreate.
    Rules: `create_factory_section` R8 [BUG-915], Errors row 4"""
    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionCreate(name="", factory_id=f1.id)

    # Then 2
    assert count_rows(db, "factory_sections") == 0


def test_fsm_u_03__a_section_of_another_workspace_is_answered_with_404_and_not_changed(db, w1, w2, u2, f9, mk_section):
    """FSM-U-03 — a section of another workspace is answered with 404 and not changed.
    Rules: `update_factory_section` R2, Errors row 1"""
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s9.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert snap(db, s9) == before_s9
    # Then 5
    row = reread(db, s9)
    assert row.name == "Packing"
    assert row.updated_by is None


def test_fsm_u_14__a_new_name_taken_in_the_target_factory_refuses_the_move_with_409_and(db, w1, u2, f1, f2, mk_section):
    """FSM-U-14 — a new name taken in the target factory refuses the move with 409 and the factory stays.
    Rules: `update_factory_section` R6, Errors row 6"""
    s1 = mk_section(name="Paint")
    s3 = mk_section(name="Welding", factory_id=f2.id)
    before_s1 = snap(db, s1)
    before_s3 = snap(db, s3)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Welding' already exists in this factory"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 6
    assert snap(db, s3) == before_s3


@pytest.mark.xfail(strict=True, reason="BUG-919: updated_by stamped on no-op section updates")
def test_fsm_u_46__an_empty_request_keeps_the_previous_updated_by(db, w1, u1, u2, mk_section):
    """FSM-U-46 — an empty request keeps the previous updated_by.
    Rules: `update_factory_section` R13 [BUG-919]"""
    s1 = mk_section(name="Paint", updated_by=u1.id)
    db.refresh(s1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.updated_by == u1.id
    # Then 3
    assert row.updated_at is None


def test_fsm_g_06__a_section_of_the_second_workspace_is_returned_to_its_own_workspace(db, w2, f9, mk_section):
    """FSM-G-06 — a section of the second workspace is returned to its own workspace.
    Rules: `get_factory_section` R1"""
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M.get_factory_section(db, section_id=s9.id, workspace_id=w2.id)

    # Then 1
    assert result.id == s9.id
    # Then 2
    assert result.workspace_id == w2.id


def test_fsm_s_45__limit_1_of_two_sections_returns_one_of_them(db, w1, f1, mk_section):
    """FSM-S-45 — limit 1 of two sections returns one of them.
    Rules: `search_factory_sections` R11"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {s1.id, s2.id}


def test_fsm_d_06__an_already_deleted_section_is_answered_with_400_and_keeps_its(db, w1, u1, u2, mk_section):
    """FSM-D-06 — an already deleted section is answered with 400 and keeps its deletion stamp.
    Rules: `delete_factory_section` R2, Errors row 2"""
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=sx.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section is already deleted"
    # Then 4
    assert snap(db, sx) == before_sx
    # Then 5
    row = reread(db, sx)
    assert row.deleted_at == T0
    # Then 6
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before


def test_fsm_d_08__a_section_with_assigned_machines_is_deleted_machines_factory_and_the(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-D-08 — a section with assigned machines is deleted; machines, factory and the other section are untouched.
    Rules: `delete_factory_section` R5 (the side that holds today), R6, Side effects"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    ma1 = mk_machine(of=f1, name="Lathe")
    ma2 = mk_machine(of=f1, name="Press")
    mk_assignment(of=ma1, to=s1)
    a3 = mk_assignment(of=ma2, to=s2)
    before_ma1 = snap(db, ma1)
    before_ma2 = snap(db, ma2)
    before_f1 = snap(db, f1)
    before_s2 = snap(db, s2)
    before_a3 = snap(db, a3)

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    assert snap(db, ma1) == before_ma1
    # Then 4
    assert snap(db, ma2) == before_ma2
    # Then 5
    assert snap(db, f1) == before_f1
    # Then 6
    assert snap(db, s2) == before_s2
    # Then 7
    assert snap(db, a3) == before_a3
    # Then 8
    assert count_rows(db, "machines") == 2


# [local-coder] FSM-C-05
def test_fsm_c_05__a_factory_of_another_workspace_is_answered_with_404(db, w1, u2, f9):
    """FSM-C-05 — a factory of another workspace is answered with 404.
    Rules: `create_factory_section` R3, Errors row 1"""
    before = written(db)
    before_f9 = snap(db, f9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f9.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, f9) == before_f9


# [local-coder] FSM-C-16
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_c_16__the_name_is_stored_trimmed(db, w1, u2, f1):
    """FSM-C-16 — the name is stored trimmed.
    Rules: `create_factory_section` R8 [BUG-915]"""
    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="  Paint ", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Paint"


# [local-coder] FSM-C-30
def test_fsm_c_30__a_user_id_that_is_no_profile_id_fails_on_flush_and_no_section_is_saved(db, w1, f1):
    """FSM-C-30 — a user_id that is no profile id fails on flush and no section is saved.
    Rules: `create_factory_section` R10, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSM-U-24
@pytest.mark.xfail(strict=True, reason="BUG-923: Updating a section with factory_id=0 crashes instead of 404")
def test_fsm_u_24__factory_id_0_is_checked_like_any_id_and_answered_with_404(db, w1, u2, mk_section):
    """FSM-U-24 — factory id 0 is checked like any id and answered with 404.
    Rules: `update_factory_section` R8a [BUG-923], Errors row 3"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=0), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-29
@pytest.mark.xfail(strict=True, reason="BUG-928: Moving a section to another factory links its machines across factories")
def test_fsm_u_29__the_assignment_of_a_soft_deleted_machine_also_blocks_the_move(db, w1, u2, f1, f2, mk_section, mk_machine, mk_assignment):
    """FSM-U-29 — the assignment of a soft-deleted machine also blocks the move.
    Rules: `update_factory_section` R10 [BUG-928]"""
    s1 = mk_section(name="Paint")
    md = mk_machine(of=f1, name="Old Saw", is_deleted=True)
    a1 = mk_assignment(of=md, to=s1)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move a section that has machines assigned"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] FSM-U-41
def test_fsm_u_41__a_one_character_name_is_accepted_by_factorysectionupdate():
    """FSM-U-41 — a one-character name is accepted by FactorySectionUpdate.
    Rules: `update_factory_section` R12"""
    result = FactorySectionUpdate(name="a")

    # Then 1
    assert result.name == "a"
    # Then 2
    assert result.factory_id is None


# [local-coder] FSM-U-49
def test_fsm_u_49__nothing_but_the_name_and_the_update_stamp_is_modified_by_a_rename(db, w1, u1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-U-49 — nothing but the name and the update stamp is modified by a rename.
    Rules: `update_factory_section` R14"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    ma1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=ma1, to=s2)
    created_before = s1.created_at
    before_s2 = snap(db, s2)
    before_a1 = snap(db, a1)
    before_ma1 = snap(db, ma1)
    before_f1 = snap(db, f1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.created_at == created_before
    # Then 3
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 4
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert snap(db, s2) == before_s2
    # Then 6
    assert snap(db, a1) == before_a1
    # Then 7
    assert snap(db, ma1) == before_ma1
    # Then 8
    assert snap(db, f1) == before_f1


# [local-coder] FSM-G-08
@pytest.mark.xfail(strict=True, reason="BUG-916: get_factory_section returns soft-deleted sections")
def test_fsm_g_08__include_deleted_true_returns_a_soft_deleted_section_of_the_workspace(db, w1, mk_section):
    """FSM-G-08 — include_deleted=True returns a soft-deleted section of the workspace.
    Rules: `get_factory_section` R4 [BUG-916]"""
    sx = mk_section(name="Old Line", deleted=True)

    result = M.get_factory_section(db, section_id=sx.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == sx.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] FSM-G-13
def test_fsm_g_13__the_id_and_workspace_can_be_passed_by_position_as_the_service_does(db, w1, mk_section):
    """FSM-G-13 — the id and workspace can be passed by position, as the service does.
    Rules: `get_factory_section` R1; Facts (positional call by the service)"""
    s1 = mk_section(name="Paint")

    result = M.get_factory_section(db, s1.id, w1.id)

    # Then 1
    assert result.id == s1.id


# [local-coder] FSM-S-17
def test_fsm_s_17__include_deleted_true_does_not_list_a_soft_deleted_section_of_another(db, w1, w2, f9, mk_section):
    """FSM-S-17 — include_deleted=True does not list a soft-deleted section of another workspace.
    Rules: `search_factory_sections` R6, R1"""
    s1 = mk_section(name="Paint")
    mk_section(name="Old Bin", factory_id=f9.id, workspace_id=w2.id, deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-37
@pytest.mark.xfail(strict=True, reason="BUG-921: Section search text is not trimmed")
def test_fsm_s_37__a_search_of_one_tab_applies_no_search_filter(db, w1, mk_section):
    """FSM-S-37 — a search of one tab applies no search filter.
    Rules: `search_factory_sections` R9 [BUG-921] (P1)"""
    s1 = mk_section(name="Main Hall")
    s2 = mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="\t")

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]


# [local-coder] FSM-S-51
def test_fsm_s_51__without_a_factory_a_negative_skip_is_rejected_by_the_database(db, w1, mk_section):
    """FSM-S-51 — without a factory a negative skip is rejected by the database.
    Rules: `search_factory_sections` R11, Errors row 2"""
    mk_section(name="Paint")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factory_sections(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] FSM-D-07
@pytest.mark.xfail(strict=True, reason="BUG-908: Deleting a section permanently erases its machines' assignments")
def test_fsm_d_07__the_machine_assignments_of_the_deleted_section_are_kept(db, w1, u1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-D-07 — the machine assignments of the deleted section are kept.
    Rules: `delete_factory_section` R5 [BUG-908], R5a [BUG-908]"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    ma2 = mk_machine(of=f1, name="Press")
    a1 = mk_assignment(of=ma1, to=s1)
    a2 = mk_assignment(of=ma2, to=s1)
    before_a1 = snap(db, a1)
    before_a2 = snap(db, a2)

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert len(rows_of_section(db, s1)) == 2
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row_a1 = reread(db, a1)
    assert row_a1.machine_id == ma1.id
    assert row_a1.factory_section_id == s1.id
    assert row_a1.created_by == u1.id
    # Then 6
    assert snap(db, a2) == before_a2


# [local-coder] FSM-D-09
@pytest.mark.xfail(strict=True, reason="BUG-908: Deleting a section permanently erases its machines' assignments")
def test_fsm_d_09__a_machine_whose_section_was_read_before_the_delete_still_reports_that(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-D-09 — a machine whose section was read before the delete still reports that section.
    Rules: `delete_factory_section` R5b [BUG-908]"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    mk_assignment(of=ma1, to=s1)
    loaded_section_id = ma1.factory_section_id  # noqa: F841  (a Given step of FSM-D-09, run as written)

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    assert ma1.factory_section_id == s1.id


# [local-coder] FSM-CN-11
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_cn_11__the_name_with_a_trailing_newline_matches_the_live_section(db, w1, f1, mk_section):
    """FSM-CN-11 — the name with a trailing newline matches the live section.
    Rules: `_check_name_exists_in_factory` R4 [BUG-912]"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint\n")

    # Then 1
    assert result is True


# [local-coder] FSM-C-02
def test_fsm_c_02__a_new_section_is_active_not_deleted_and_carries_no_update_or_deletion(db, w1, u2, f1):
    """FSM-C-02 — a new section is active, not deleted, and carries no update or deletion stamp.
    Rules: `create_factory_section` R2"""
    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    assert row.created_at is not None
    # Then 4
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FSM-C-03
def test_fsm_c_03__a_section_is_created_in_the_second_workspace_for_that_workspace_s(db, w2, u2, f9, mk_section):
    """FSM-C-03 — a section is created in the second workspace for that workspace's factory.
    Rules: `create_factory_section` R1"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Packing", factory_id=f9.id), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.factory_id == f9.id
    assert row.name == "Packing"
    # Then 3
    assert count_rows(db, "factory_sections") == 2
    # Then 4
    assert snap(db, s1) == before_s1


# [local-coder] FSM-C-04
def test_fsm_c_04__a_factory_id_that_no_factory_has_is_answered_with_404(db, w1, u2):
    """FSM-C-04 — a factory id that no factory has is answered with 404.
    Rules: `create_factory_section` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSM-C-06
def test_fsm_c_06__factory_id_0_is_answered_with_404(db, w1, u2):
    """FSM-C-06 — factory id 0 is answered with 404.
    Rules: `create_factory_section` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=0), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert written(db) == before


# [local-coder] FSM-C-07
def test_fsm_c_07__a_negative_factory_id_is_answered_with_404(db, w1, u2):
    """FSM-C-07 — a negative factory id is answered with 404.
    Rules: `create_factory_section` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=-1), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID -1 not found"
    # Then 4
    assert written(db) == before


# [local-coder] FSM-C-08
def test_fsm_c_08__an_unknown_workspace_id_finds_no_factory_and_is_answered_with_404(db, u2, f1):
    """FSM-C-08 — an unknown workspace id finds no factory and is answered with 404.
    Rules: `create_factory_section` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=MISSING, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f1.id} not found"
    # Then 4
    assert written(db) == before


# [local-coder] FSM-C-09
def test_fsm_c_09__a_soft_deleted_factory_is_answered_with_400(db, w1, u2, fd):
    """FSM-C-09 — a soft-deleted factory is answered with 400.
    Rules: `create_factory_section` R4, Errors row 2"""
    before = written(db)
    before_fd = snap(db, fd)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create section for deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, fd) == before_fd


# [local-coder] FSM-C-10
def test_fsm_c_10__a_soft_deleted_factory_is_answered_with_400_also_when_the_name_is(db, w1, u2, fd, mk_section):
    """FSM-C-10 — a soft-deleted factory is answered with 400 also when the name is taken there.
    Rules: `create_factory_section` R4"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create section for deleted factory"
    # Then 4
    assert count_rows(db, "factory_sections") == 1
    # Then 5
    assert snap(db, sh) == before_sh


# [local-coder] FSM-C-11
def test_fsm_c_11__a_live_but_inactive_factory_is_accepted(db, w1, u2, fi):
    """FSM-C-11 — a live but inactive factory is accepted.
    Rules: `create_factory_section` R5"""
    before_fi = snap(db, fi)

    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=fi.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_id == fi.id
    assert row.name == "Paint"
    # Then 3
    assert snap(db, fi) == before_fi


# [local-coder] FSM-C-12
def test_fsm_c_12__a_name_used_by_a_live_section_of_the_factory_is_refused_with_409(db, w1, u2, f1, mk_section):
    """FSM-C-12 — a name used by a live section of the factory is refused with 409.
    Rules: `create_factory_section` R6, Errors row 3; `_check_name_exists_in_factory` R1"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 1
    # Then 6
    assert snap(db, s1) == before_s1


# [local-coder] FSM-C-13
def test_fsm_c_13__the_same_name_in_another_factory_of_the_workspace_does_not_block_the(db, w1, f1, f2, u2, mk_section):
    """FSM-C-13 — the same name in another factory of the workspace does not block the create.
    Rules: `create_factory_section` R7; `_check_name_exists_in_factory` R2"""
    s3 = mk_section(name="Paint", factory_id=f2.id)
    before_s3 = snap(db, s3)

    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != s3.id
    # Then 3
    row = reread(db, result)
    assert row.factory_id == f1.id
    assert row.name == "Paint"
    # Then 4
    assert count_rows(db, "factory_sections") == 2
    # Then 5
    assert snap(db, s3) == before_s3


# [local-coder] FSM-C-14
def test_fsm_c_14__the_name_of_a_soft_deleted_section_of_the_factory_can_be_used_again(db, w1, u2, f1, mk_section):
    """FSM-C-14 — the name of a soft-deleted section of the factory can be used again.
    Rules: `create_factory_section` R7; `_check_name_exists_in_factory` R3"""
    sx = mk_section(name="Paint", deleted=True)
    before_sx = snap(db, sx)

    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != sx.id
    # Then 3
    row = reread(db, result)
    assert row.name == "Paint"
    assert row.is_deleted is False
    assert row.created_by == u2.id
    # Then 4
    assert count_rows(db, "factory_sections") == 2
    # Then 5
    assert snap(db, sx) == before_sx


# [local-coder] FSM-C-15
def test_fsm_c_15__the_same_name_in_another_workspace_does_not_block_the_create(db, w1, w2, u2, f1, f9, mk_section):
    """FSM-C-15 — the same name in another workspace does not block the create.
    Rules: `create_factory_section` R7; `_check_name_exists_in_factory` R2"""
    s9 = mk_section(name="Paint", factory_id=f9.id, workspace_id=w2.id)
    before_s9 = snap(db, s9)

    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    assert row.name == "Paint"
    # Then 3
    assert count_rows(db, "factory_sections") == 2
    # Then 4
    assert snap(db, s9) == before_s9


# [local-coder] FSM-C-17
def test_fsm_c_17__inner_whitespace_and_case_of_the_name_are_kept(db, w1, u2, f1):
    """FSM-C-17 — inner whitespace and case of the name are kept.
    Rules: `create_factory_section` R1, R8"""
    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="spray  BAY", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "spray  BAY"


# [local-coder] FSM-C-19
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_c_19__a_name_of_three_spaces_is_rejected_by_factorysectioncreate(db, f1):
    """FSM-C-19 — a name of three spaces is rejected by FactorySectionCreate.
    Rules: `create_factory_section` R8 [BUG-915], Errors row 4"""
    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionCreate(name="   ", factory_id=f1.id)

    # Then 2
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSM-C-20
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_c_20__a_name_of_one_tab_is_rejected_by_factorysectioncreate(db, f1):
    """FSM-C-20 — a name of one tab is rejected by FactorySectionCreate.
    Rules: `create_factory_section` R8 [BUG-915], Errors row 4"""
    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionCreate(name="\t", factory_id=f1.id)

    # Then 2
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSM-C-21
def test_fsm_c_21__a_one_character_name_is_accepted_by_factorysectioncreate(f1):
    """FSM-C-21 — a one-character name is accepted by FactorySectionCreate.
    Rules: `create_factory_section` R8"""
    result = FactorySectionCreate(name="a", factory_id=f1.id)

    # Then 1
    assert result.name == "a"
    # Then 2
    assert result.factory_id == f1.id


# [local-coder] FSM-C-22
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_c_22__a_name_that_differs_only_in_case_from_a_live_section_s_name_is(db, w1, u2, f1, mk_section):
    """FSM-C-22 — a name that differs only in case from a live section's name is refused with 409.
    Rules: `create_factory_section` R6, Errors row 3; `_check_name_exists_in_factory` R4 [BUG-912]"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'paint' already exists in this factory"
    # Then 4
    assert count_rows(db, "factory_sections") == 1
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] FSM-C-23
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_c_23__a_name_that_differs_only_by_a_trailing_space_is_refused_with_409_and(db, w1, u2, f1, mk_section):
    """FSM-C-23 — a name that differs only by a trailing space is refused with 409 and the trimmed name in the message.
    Rules: `create_factory_section` R6, R8 [BUG-915]; `_check_name_exists_in_factory` R4 [BUG-912]"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint ", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert count_rows(db, "factory_sections") == 1
    # Then 5
    assert snap(db, s1) == before_s1


# [claude] FSM-C-24
@pytest.mark.xfail(strict=False, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory (non-strict: today's result depends on the physical row order)")
def test_fsm_c_24__a_duplicate_name_is_refused_also_when_its_live_owner_is_the_101st(db, w1, u2, f1, mk_section):
    """FSM-C-24 — a duplicate name is refused also when its live owner is the 101st live section of the factory.
    Rules: `create_factory_section` R6; `_check_name_exists_in_factory` R5 [BUG-911]"""
    for k in range(1, 101):
        mk_section(name=f"Bay {k:03d}")
    mk_section(name="Late")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Late", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Late' already exists in this factory"
    # Then 4
    assert count_rows(db, "factory_sections") == 101


# [claude] FSM-C-25
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fsm_c_25__the_database_refuses_a_second_live_section_with_the_same_name_in_one(db, w1, u1, f1, mk_section):
    """FSM-C-25 — the database refuses a second live section with the same name in one factory.
    Rules: `create_factory_section` R9 [BUG-913]"""
    mk_section(name="Paint")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(FactorySection(workspace_id=w1.id, factory_id=f1.id, name="Paint", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "factory_sections") == 1


# [claude] FSM-C-26
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fsm_c_26__the_database_refuses_a_second_live_section_whose_name_differs_only_in(db, w1, u1, f1, mk_section):
    """FSM-C-26 — the database refuses a second live section whose name differs only in case and outer spaces.
    Rules: `create_factory_section` R9 [BUG-913]"""
    mk_section(name="Paint")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(FactorySection(workspace_id=w1.id, factory_id=f1.id, name="PAINT ", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "factory_sections") == 1


# [claude] FSM-C-27
def test_fsm_c_27__the_database_accepts_a_soft_deleted_section_with_the_name_of_a_live(db, w1, u1, f1, mk_section):
    """FSM-C-27 — the database accepts a soft-deleted section with the name of a live one.
    Rules: `create_factory_section` R9"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    db.add(FactorySection(workspace_id=w1.id, factory_id=f1.id, name="Paint", created_by=u1.id, is_deleted=True, deleted_at=T0, deleted_by=u1.id))
    db.flush()

    # Then 1
    assert count_rows(db, "factory_sections") == 2
    # Then 2
    assert snap(db, s1) == before_s1


# [claude] FSM-C-28
def test_fsm_c_28__the_database_accepts_a_live_section_of_another_factory_with_the_same(db, w1, u1, f2, mk_section):
    """FSM-C-28 — the database accepts a live section of another factory with the same name.
    Rules: `create_factory_section` R9"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    db.add(FactorySection(workspace_id=w1.id, factory_id=f2.id, name="Paint", created_by=u1.id))
    db.flush()

    # Then 1
    assert count_rows(db, "factory_sections") == 2
    # Then 2
    assert snap(db, s1) == before_s1


# [claude] FSM-C-29
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fsm_c_29__a_duplicate_name_that_passed_the_python_check_is_answered_with_409(db, w1, u2, f1, mk_section):
    """FSM-C-29 — a duplicate name that passed the Python check is answered with 409, not a database error.
    Rules: `create_factory_section` R9 [BUG-913], Errors row 3"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    with patch.object(FactorySectionManager, "_check_name_exists_in_factory", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert count_rows(db, "factory_sections") == 1
    # Then 5
    assert snap(db, s1) == before_s1


# [claude] FSM-C-31
def test_fsm_c_31__the_create_is_flushed_but_not_committed_a_rollback_removes_the(db, w1, u2, f1):
    """FSM-C-31 — the create is flushed but not committed: a rollback removes the section.
    Rules: `create_factory_section` Returns, Side effects"""
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert count_rows(db, "factory_sections") == 1
        sp.rollback()
        # Then 2
        assert count_rows(db, "factory_sections") == 0
        # Then 3
        assert commit_spy.call_count == 0


# [local-coder] FSM-U-01
def test_fsm_u_01__a_new_name_is_stored_and_the_editor_is_recorded(db, w1, u2, f1, mk_section):
    """FSM-U-01 — a new name is stored and the editor is recorded.
    Rules: `update_factory_section` R4, R11, R13, R14, Returns"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"
    # Then 3
    assert row.factory_id == f1.id
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSM-U-02
def test_fsm_u_02__an_id_that_no_section_has_is_answered_with_404(db, w1, u2, mk_section):
    """FSM-U-02 — an id that no section has is answered with 404.
    Rules: `update_factory_section` R1, Errors row 1"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=MISSING, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-04
def test_fsm_u_04__a_soft_deleted_section_is_answered_with_400_and_not_changed(db, w1, u2, mk_section):
    """FSM-U-04 — a soft-deleted section is answered with 400 and not changed.
    Rules: `update_factory_section` R3, Errors row 2"""
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sx.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sx) == before_sx
    # Then 5
    assert written(db) == before


# [local-coder] FSM-U-05
def test_fsm_u_05__a_soft_deleted_section_is_answered_with_400_also_when_the_requested(db, w1, u2, mk_section):
    """FSM-U-05 — a soft-deleted section is answered with 400 also when the requested name is taken.
    Rules: `update_factory_section` R3"""
    sx = mk_section(name="Old Line", deleted=True)
    s2 = mk_section(name="Paint")
    before_sx = snap(db, sx)
    before_s2 = snap(db, s2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sx.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sx) == before_sx
    # Then 5
    assert snap(db, s2) == before_s2


# [local-coder] FSM-U-06
def test_fsm_u_06__a_soft_deleted_section_is_answered_with_400_also_when_it_is_moved_to(db, w1, u2, fd, mk_section):
    """FSM-U-06 — a soft-deleted section is answered with 400 also when it is moved to a soft-deleted factory.
    Rules: `update_factory_section` R3"""
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sx.id, section_data=FactorySectionUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sx) == before_sx


# [local-coder] FSM-U-07
@pytest.mark.xfail(strict=True, reason="BUG-926: A section inside a soft-deleted factory can still be renamed or moved out")
def test_fsm_u_07__a_section_of_a_soft_deleted_factory_cannot_be_renamed(db, w1, u2, fd, mk_section):
    """FSM-U-07 — a section of a soft-deleted factory cannot be renamed.
    Rules: `update_factory_section` R3a [BUG-926], Errors row 2"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sh.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sh) == before_sh
    # Then 5
    row = reread(db, sh)
    assert row.name == "Paint"
    assert row.updated_by is None


# [local-coder] FSM-U-08
@pytest.mark.xfail(strict=True, reason="BUG-926: A section inside a soft-deleted factory can still be renamed or moved out")
def test_fsm_u_08__a_section_of_a_soft_deleted_factory_is_refused_also_when_its_own(db, w1, u2, fd, mk_section):
    """FSM-U-08 — a section of a soft-deleted factory is refused also when its own factory id is sent.
    Rules: `update_factory_section` R3a [BUG-926]"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sh.id, section_data=FactorySectionUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sh) == before_sh


# [local-coder] FSM-U-09
@pytest.mark.xfail(strict=True, reason="BUG-926: A section inside a soft-deleted factory can still be renamed or moved out")
def test_fsm_u_09__a_section_of_a_soft_deleted_factory_cannot_be_moved_out_to_a_live(db, w1, u2, f1, fd, mk_section):
    """FSM-U-09 — a section of a soft-deleted factory cannot be moved out to a live factory.
    Rules: `update_factory_section` R3a [BUG-926]"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=sh.id, section_data=FactorySectionUpdate(factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, sh) == before_sh
    # Then 5
    row = reread(db, sh)
    assert row.factory_id == fd.id


# [local-coder] FSM-U-10
def test_fsm_u_10__a_section_of_a_live_but_inactive_factory_is_renamed(db, w1, u2, fi, mk_section):
    """FSM-U-10 — a section of a live but inactive factory is renamed.
    Rules: `update_factory_section` R3a (the side that holds today), R4"""
    sf = mk_section(name="Paint", factory_id=fi.id)

    result = M.update_factory_section(db, section_id=sf.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is sf
    # Then 2
    row = reread(db, sf)
    assert row.name == "Spray"
    assert row.factory_id == fi.id
    # Then 3
    row = reread(db, sf)
    assert row.updated_by == u2.id


# [local-coder] FSM-U-11
def test_fsm_u_11__sending_the_current_name_without_a_move_is_accepted_and_the_name_stays(db, w1, u2, f1, mk_section):
    """FSM-U-11 — sending the current name without a move is accepted and the name stays.
    Rules: `update_factory_section` R5"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSM-U-12
def test_fsm_u_12__changing_only_the_case_of_the_section_s_own_name_is_stored(db, w1, u2, mk_section):
    """FSM-U-12 — changing only the case of the section's own name is stored.
    Rules: `update_factory_section` R5; `_check_name_exists_in_factory` R6"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s2 = snap(db, s2)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="PAINT"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "PAINT"
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert snap(db, s2) == before_s2


# [local-coder] FSM-U-13
def test_fsm_u_13__a_name_used_by_another_live_section_of_the_factory_is_refused_with_409(db, w1, u2, mk_section):
    """FSM-U-13 — a name used by another live section of the factory is refused with 409.
    Rules: `update_factory_section` R6, Errors row 6; `_check_name_exists_in_factory` R6"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s2 = snap(db, s2)
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s2.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert snap(db, s2) == before_s2
    # Then 5
    row = reread(db, s2)
    assert row.name == "Welding"
    # Then 6
    assert snap(db, s1) == before_s1
    # Then 7
    assert written(db) == before


# [local-coder] FSM-U-15
def test_fsm_u_15__a_name_used_only_in_the_old_factory_does_not_block_a_move_with_that(db, w1, u2, f2, mk_section):
    """FSM-U-15 — a name used only in the old factory does not block a move with that new name.
    Rules: `update_factory_section` R6"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s2 = snap(db, s2)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Welding"
    assert row.factory_id == f2.id
    # Then 3
    assert snap(db, s2) == before_s2


# [local-coder] FSM-U-16
def test_fsm_u_16__a_name_used_in_another_factory_can_be_taken_by_a_rename_without_a_move(db, w1, u2, f1, f2, mk_section):
    """FSM-U-16 — a name used in another factory can be taken by a rename without a move.
    Rules: `update_factory_section` R16"""
    s1 = mk_section(name="Paint")
    s3 = mk_section(name="Welding", factory_id=f2.id)
    before_s3 = snap(db, s3)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Welding"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Welding"
    assert row.factory_id == f1.id
    # Then 3
    assert snap(db, s3) == before_s3


# [local-coder] FSM-U-17
def test_fsm_u_17__a_section_without_machines_is_moved_to_another_live_factory(db, w1, u2, f1, f2, mk_section):
    """FSM-U-17 — a section without machines is moved to another live factory.
    Rules: `update_factory_section` R7, R10 (the side that holds today), R14"""
    s1 = mk_section(name="Paint")
    before_f1 = snap(db, f1)
    before_f2 = snap(db, f2)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.factory_id == f2.id
    # Then 3
    assert row.name == "Paint"
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert snap(db, f1) == before_f1
    # Then 6
    assert snap(db, f2) == before_f2


# [local-coder] FSM-U-18
def test_fsm_u_18__a_move_to_a_factory_id_that_no_factory_has_is_answered_with_404(db, w1, u2, mk_section):
    """FSM-U-18 — a move to a factory id that no factory has is answered with 404.
    Rules: `update_factory_section` R7, Errors row 3"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert written(db) == before


# [local-coder] FSM-U-19
def test_fsm_u_19__a_move_to_a_factory_of_another_workspace_is_answered_with_404(db, w1, u2, f1, f9, mk_section):
    """FSM-U-19 — a move to a factory of another workspace is answered with 404.
    Rules: `update_factory_section` R7, Errors row 3"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f9.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    row = reread(db, s1)
    assert row.factory_id == f1.id


# [local-coder] FSM-U-20
def test_fsm_u_20__a_move_to_a_negative_factory_id_is_answered_with_404(db, w1, u2, mk_section):
    """FSM-U-20 — a move to a negative factory id is answered with 404.
    Rules: `update_factory_section` R7, Errors row 3"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=-1), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID -1 not found"
    # Then 4
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-21
def test_fsm_u_21__a_move_to_a_live_but_inactive_factory_is_accepted(db, w1, u2, fi, mk_section):
    """FSM-U-21 — a move to a live but inactive factory is accepted.
    Rules: `update_factory_section` R7"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=fi.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.factory_id == fi.id


# [local-coder] FSM-U-22
def test_fsm_u_22__a_move_to_a_soft_deleted_factory_is_answered_with_400(db, w1, u2, fd, mk_section):
    """FSM-U-22 — a move to a soft-deleted factory is answered with 400.
    Rules: `update_factory_section` R8, Errors row 4"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move section to deleted factory"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert written(db) == before


# [local-coder] FSM-U-23
def test_fsm_u_23__a_move_to_a_soft_deleted_factory_is_answered_with_400_also_when_the(db, w1, u2, fd, mk_section):
    """FSM-U-23 — a move to a soft-deleted factory is answered with 400 also when the new name is taken there.
    Rules: `update_factory_section` R8"""
    s1 = mk_section(name="Paint")
    sh = mk_section(name="Welding", factory_id=fd.id)
    before_s1 = snap(db, s1)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move section to deleted factory"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert snap(db, sh) == before_sh


# [local-coder] FSM-U-25
@pytest.mark.xfail(strict=True, reason="BUG-914: Moving a section into a factory where its name is taken is not checked")
def test_fsm_u_25__a_plain_move_into_a_factory_where_the_name_is_taken_is_refused_with(db, w1, u2, f1, f2, mk_section):
    """FSM-U-25 — a plain move into a factory where the name is taken is refused with 409.
    Rules: `update_factory_section` R9 [BUG-914], Errors row 6"""
    s1 = mk_section(name="Paint")
    s3 = mk_section(name="Paint", factory_id=f2.id)
    before_s3 = snap(db, s3)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id
    # Then 5
    assert snap(db, s3) == before_s3


# [local-coder] FSM-U-26
@pytest.mark.xfail(strict=True, reason="BUG-914: Moving a section into a factory where its name is taken is not checked")
def test_fsm_u_26__a_move_that_re_sends_the_current_name_into_a_factory_where_it_is(db, w1, u2, f1, f2, mk_section):
    """FSM-U-26 — a move that re-sends the current name into a factory where it is taken is refused with 409.
    Rules: `update_factory_section` R9 [BUG-914], Errors row 6"""
    s1 = mk_section(name="Paint")
    s3 = mk_section(name="Paint", factory_id=f2.id)
    before_s3 = snap(db, s3)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Paint", factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id
    # Then 5
    assert snap(db, s3) == before_s3


# [local-coder] FSM-U-27
def test_fsm_u_27__a_move_into_a_factory_where_the_name_belongs_only_to_a_soft_deleted(db, w1, u2, f2, mk_section):
    """FSM-U-27 — a move into a factory where the name belongs only to a soft-deleted section is accepted.
    Rules: `update_factory_section` R9 (the side that holds today), R16"""
    s1 = mk_section(name="Paint")
    sx3 = mk_section(name="Paint", factory_id=f2.id, deleted=True)
    before_sx3 = snap(db, sx3)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.factory_id == f2.id
    assert row.name == "Paint"
    # Then 3
    assert snap(db, sx3) == before_sx3


# [local-coder] FSM-U-28
@pytest.mark.xfail(strict=True, reason="BUG-928: Moving a section to another factory links its machines across factories")
def test_fsm_u_28__a_section_with_an_assigned_machine_cannot_be_moved_to_another_factory(db, w1, u2, f1, f2, mk_section, mk_machine, mk_assignment):
    """FSM-U-28 — a section with an assigned machine cannot be moved to another factory.
    Rules: `update_factory_section` R10 [BUG-928], Errors row 5"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=ma1, to=s1)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move a section that has machines assigned"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] FSM-U-30
def test_fsm_u_30__a_section_with_an_assigned_machine_is_renamed_and_its_assignment_is(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-U-30 — a section with an assigned machine is renamed and its assignment is left as it was.
    Rules: `update_factory_section` R10 (rename not affected), R14"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=ma1, to=s1)
    before_a1 = snap(db, a1)
    before_ma1 = snap(db, ma1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"
    assert row.factory_id == f1.id
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    assert len(rows_of_section(db, s1)) == 1
    # Then 5
    assert snap(db, ma1) == before_ma1


# [local-coder] FSM-U-31
def test_fsm_u_31__a_section_with_an_assigned_machine_moved_to_a_soft_deleted_factory(db, w1, u2, f1, fd, mk_section, mk_machine, mk_assignment):
    """FSM-U-31 — a section with an assigned machine moved to a soft-deleted factory gets the "deleted factory" message.
    Rules: `update_factory_section` R8, R10 (checked after R8)"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=ma1, to=s1)
    before_s1 = snap(db, s1)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move section to deleted factory"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] FSM-U-32
def test_fsm_u_32__a_section_with_an_assigned_machine_moved_to_an_unknown_factory_gets(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-U-32 — a section with an assigned machine moved to an unknown factory gets 404.
    Rules: `update_factory_section` R7, R10 (checked after R7)"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=ma1, to=s1)
    before_s1 = snap(db, s1)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=MISSING), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] FSM-U-33
@pytest.mark.xfail(strict=True, reason="BUG-928: Moving a section to another factory links its machines across factories")
def test_fsm_u_33__the_machine_refusal_comes_before_the_name_check_of_the_target_factory(db, w1, u2, f1, f2, mk_section, mk_machine, mk_assignment):
    """FSM-U-33 — the machine refusal comes before the name check of the target factory.
    Rules: `update_factory_section` R10 [BUG-928] (checked before R9)"""
    s1 = mk_section(name="Paint")
    mk_section(name="Paint", factory_id=f2.id)
    ma1 = mk_machine(of=f1, name="Lathe")
    mk_assignment(of=ma1, to=s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move a section that has machines assigned"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id


# [local-coder] FSM-U-34
def test_fsm_u_34__an_explicit_null_name_is_left_unchanged_while_the_factory_is_changed(db, w1, u2, f2, mk_section):
    """FSM-U-34 — an explicit null name is left unchanged while the factory is changed.
    Rules: `update_factory_section` R11"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name=None, factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    # Then 3
    assert row.factory_id == f2.id


# [local-coder] FSM-U-35
def test_fsm_u_35__an_explicit_null_factory_id_is_left_unchanged_while_the_name_is(db, w1, u2, f1, mk_section):
    """FSM-U-35 — an explicit null factory id is left unchanged while the name is changed.
    Rules: `update_factory_section` R11"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray", factory_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"
    # Then 3
    assert row.factory_id == f1.id


# [local-coder] FSM-U-36
def test_fsm_u_36__the_current_factory_id_sent_with_a_new_name_keeps_the_factory(db, w1, u2, f1, mk_section):
    """FSM-U-36 — the current factory id sent with a new name keeps the factory.
    Rules: `update_factory_section` R11"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"
    assert row.factory_id == f1.id


# [local-coder] FSM-U-37
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_u_37__a_sent_name_is_stored_trimmed(db, w1, u2, mk_section):
    """FSM-U-37 — a sent name is stored trimmed.
    Rules: `update_factory_section` R12 [BUG-915]"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name=" Spray "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"


# [local-coder] FSM-U-38
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_u_38__the_current_name_sent_with_outer_spaces_counts_as_the_current_name(db, w1, u2, mk_section):
    """FSM-U-38 — the current name sent with outer spaces counts as the current name.
    Rules: `update_factory_section` R12 [BUG-915], R5"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name=" Paint "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"


# [local-coder] FSM-U-39
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_u_39__an_empty_name_is_rejected_by_factorysectionupdate(db, mk_section):
    """FSM-U-39 — an empty name is rejected by FactorySectionUpdate.
    Rules: `update_factory_section` R12 [BUG-915], Errors row 7"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionUpdate(name="")

    # Then 2
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-40
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_u_40__a_name_of_three_spaces_is_rejected_by_factorysectionupdate(db, mk_section):
    """FSM-U-40 — a name of three spaces is rejected by FactorySectionUpdate.
    Rules: `update_factory_section` R12 [BUG-915], Errors row 7"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionUpdate(name="   ")

    # Then 2
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-42
def test_fsm_u_42__factorysectionupdate_without_fields_has_name_none_and_factory_id_none():
    """FSM-U-42 — FactorySectionUpdate without fields has name None and factory_id None.
    Rules: `update_factory_section` Inputs, R11"""
    result = FactorySectionUpdate()

    # Then 1
    assert result.name is None
    # Then 2
    assert result.factory_id is None


# [local-coder] FSM-U-43
@pytest.mark.xfail(strict=True, reason="BUG-919: updated_by stamped on no-op section updates")
def test_fsm_u_43__an_empty_request_does_not_stamp_updated_by(db, w1, u2, f1, mk_section):
    """FSM-U-43 — an empty request does not stamp updated_by.
    Rules: `update_factory_section` R13 [BUG-919]"""
    s1 = mk_section(name="Paint")
    db.refresh(s1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] FSM-U-44
@pytest.mark.xfail(strict=True, reason="BUG-919: updated_by stamped on no-op section updates")
def test_fsm_u_44__a_request_with_only_null_fields_does_not_stamp_updated_by(db, w1, u2, f1, mk_section):
    """FSM-U-44 — a request with only null fields does not stamp updated_by.
    Rules: `update_factory_section` R13 [BUG-919]"""
    s1 = mk_section(name="Paint")
    db.refresh(s1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name=None, factory_id=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    row = reread(db, s1)
    assert row.updated_by is None
    # Then 4
    row = reread(db, s1)
    assert row.updated_at is None


# [local-coder] FSM-U-45
@pytest.mark.xfail(strict=True, reason="BUG-919: updated_by stamped on no-op section updates")
def test_fsm_u_45__a_request_with_the_current_values_does_not_stamp_updated_by(db, w1, u2, f1, mk_section):
    """FSM-U-45 — a request with the current values does not stamp updated_by.
    Rules: `update_factory_section` R13 [BUG-919]"""
    s1 = mk_section(name="Paint")
    db.refresh(s1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] FSM-U-47
def test_fsm_u_47__an_empty_request_succeeds_and_leaves_name_and_factory_as_they_are(db, w1, u2, f1, mk_section):
    """FSM-U-47 — an empty request succeeds and leaves name and factory as they are.
    Rules: `update_factory_section` R11, R13 (the side that holds today)"""
    s1 = mk_section(name="Paint")

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSM-U-48
def test_fsm_u_48__a_real_change_replaces_a_previous_updated_by_with_the_acting_user(db, w1, u1, u2, mk_section):
    """FSM-U-48 — a real change replaces a previous updated_by with the acting user.
    Rules: `update_factory_section` R13"""
    s1 = mk_section(name="Paint", updated_by=u1.id)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Spray"
    # Then 3
    assert row.updated_by == u2.id


# [claude] FSM-U-50
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fsm_u_50__a_rename_to_a_taken_name_that_passed_the_python_check_is_answered(db, w1, u2, mk_section):
    """FSM-U-50 — a rename to a taken name that passed the Python check is answered with 409, not a database error.
    Rules: `update_factory_section` R15 [BUG-913], Errors row 6"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s1 = snap(db, s1)

    with patch.object(FactorySectionManager, "_check_name_exists_in_factory", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.update_factory_section(db, section_id=s2.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    row = reread(db, s2)
    assert row.name == "Welding"
    # Then 5
    assert snap(db, s1) == before_s1


# [claude] FSM-U-51
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fsm_u_51__a_move_whose_name_is_taken_in_the_target_and_passed_the_python_check(db, w1, u2, f1, f2, mk_section):
    """FSM-U-51 — a move whose name is taken in the target and passed the Python check is answered with 409.
    Rules: `update_factory_section` R15 [BUG-913], Errors row 6"""
    s1 = mk_section(name="Paint")
    s3 = mk_section(name="Paint", factory_id=f2.id)
    before_s3 = snap(db, s3)

    with patch.object(FactorySectionManager, "_check_name_exists_in_factory", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    row = reread(db, s1)
    assert row.factory_id == f1.id
    # Then 5
    assert snap(db, s3) == before_s3


# [local-coder] FSM-U-52
def test_fsm_u_52__the_name_of_a_soft_deleted_section_of_the_factory_can_be_taken_by_a(db, w1, u2, mk_section):
    """FSM-U-52 — the name of a soft-deleted section of the factory can be taken by a rename.
    Rules: `update_factory_section` R16"""
    s1 = mk_section(name="Paint")
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Old Line"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Old Line"
    # Then 3
    assert snap(db, sx) == before_sx


# [local-coder] FSM-U-53
def test_fsm_u_53__the_name_of_a_section_of_another_workspace_can_be_taken_by_a_rename(db, w1, w2, u2, f9, mk_section):
    """FSM-U-53 — the name of a section of another workspace can be taken by a rename.
    Rules: `update_factory_section` R16"""
    s1 = mk_section(name="Paint")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s9 = snap(db, s9)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Packing"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Packing"
    # Then 3
    assert snap(db, s9) == before_s9


# [local-coder] FSM-U-54
def test_fsm_u_54__a_rename_by_a_user_id_that_is_no_profile_id_fails_on_flush_and(db, w1, mk_section):
    """FSM-U-54 — a rename by a user_id that is no profile id fails on flush and nothing is saved.
    Rules: `update_factory_section` R17, Errors row 8"""
    s1 = mk_section(name="Paint")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_updated_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, s1)
    assert row.name == "Paint"
    # Then 5
    assert row.updated_by is None


# [local-coder] FSM-U-55
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_u_55__a_new_name_that_differs_only_in_case_from_another_live_section_s_name(db, w1, u2, mk_section):
    """FSM-U-55 — a new name that differs only in case from another live section's name is refused with 409.
    Rules: `update_factory_section` R6, Errors row 6; `_check_name_exists_in_factory` R4 [BUG-912]"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s2.id, section_data=FactorySectionUpdate(name="paint"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'paint' already exists in this factory"
    # Then 4
    row = reread(db, s2)
    assert row.name == "Welding"
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] FSM-U-56
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fsm_u_56__a_new_name_that_differs_only_by_a_trailing_space_is_refused_with_409(db, w1, u2, mk_section):
    """FSM-U-56 — a new name that differs only by a trailing space is refused with 409 and the trimmed name in the message.
    Rules: `update_factory_section` R6, R12 [BUG-915]; `_check_name_exists_in_factory` R4 [BUG-912]"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s2.id, section_data=FactorySectionUpdate(name="Paint "), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    row = reread(db, s2)
    assert row.name == "Welding"
    # Then 5
    assert snap(db, s1) == before_s1


# [claude] FSM-U-57
@pytest.mark.xfail(strict=False, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory (non-strict: today's result depends on the physical row order)")
def test_fsm_u_57__a_rename_to_a_taken_name_is_refused_also_when_its_live_owner_is_the(db, w1, u2, mk_section):
    """FSM-U-57 — a rename to a taken name is refused also when its live owner is the 101st live section of the factory.
    Rules: `update_factory_section` R6; `_check_name_exists_in_factory` R5 [BUG-911]"""
    for k in range(1, 101):
        mk_section(name=f"Bay {k:03d}")
    mk_section(name="Late")
    s2 = mk_section(name="Welding")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s2.id, section_data=FactorySectionUpdate(name="Late"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Late' already exists in this factory"
    # Then 4
    row = reread(db, s2)
    assert row.name == "Welding"


# [claude] FSM-U-58
def test_fsm_u_58__the_update_is_flushed_but_not_committed_a_rollback_brings_the_old(db, w1, u2, mk_section):
    """FSM-U-58 — the update is flushed but not committed: a rollback brings the old name back.
    Rules: `update_factory_section` Returns, Side effects"""
    s1 = mk_section(name="Paint")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)

        # Then 1
        row = reread(db, s1)
        assert row.name == "Spray"
        sp.rollback()
        # Then 2
        row = reread(db, s1)
        assert row.name == "Paint"
        # Then 3
        assert row.updated_by is None
        # Then 4
        assert commit_spy.call_count == 0


# [local-coder] FSM-U-59
def test_fsm_u_59__a_section_of_the_second_workspace_is_renamed_from_its_own_workspace(db, w2, u2, f9, mk_section):
    """FSM-U-59 — a section of the second workspace is renamed from its own workspace.
    Rules: `update_factory_section` R2, R4"""
    s1 = mk_section(name="Paint")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s1 = snap(db, s1)

    result = M.update_factory_section(db, section_id=s9.id, section_data=FactorySectionUpdate(name="Boxing"), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result is s9
    # Then 2
    row = reread(db, s9)
    assert row.name == "Boxing"
    assert row.factory_id == f9.id
    # Then 3
    assert snap(db, s1) == before_s1


# [local-coder] FSM-G-01
def test_fsm_g_01__a_live_section_of_the_workspace_is_returned_and_nothing_is_changed(db, w1, f1, mk_section):
    """FSM-G-01 — a live section of the workspace is returned and nothing is changed.
    Rules: `get_factory_section` R1, Side effects"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    result = M.get_factory_section(db, section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, FactorySection)
    # Then 2
    assert result.id == s1.id
    # Then 3
    assert result.name == "Paint"
    assert result.factory_id == f1.id
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert written(db) == before


# [local-coder] FSM-G-02
def test_fsm_g_02__a_live_section_with_is_active_false_is_returned(db, w1, mk_section):
    """FSM-G-02 — a live section with is_active False is returned.
    Rules: `get_factory_section` R1"""
    si = mk_section(name="Idle Bay", is_active=False)

    result = M.get_factory_section(db, section_id=si.id, workspace_id=w1.id)

    # Then 1
    assert result.id == si.id
    # Then 2
    assert result.is_active is False


# [local-coder] FSM-G-03
def test_fsm_g_03__a_section_of_a_live_but_inactive_factory_is_returned(db, w1, fi, mk_section):
    """FSM-G-03 — a section of a live but inactive factory is returned.
    Rules: `get_factory_section` R1, R5 (inactive factory hides nothing)"""
    sf = mk_section(name="Paint", factory_id=fi.id)

    result = M.get_factory_section(db, section_id=sf.id, workspace_id=w1.id)

    # Then 1
    assert result.id == sf.id
    # Then 2
    assert result.factory_id == fi.id


# [local-coder] FSM-G-04
def test_fsm_g_04__an_id_that_no_section_has_is_answered_with_404(db, w1, mk_section):
    """FSM-G-04 — an id that no section has is answered with 404.
    Rules: `get_factory_section` R2, Errors row 1"""
    mk_section(name="Paint")
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory_section(db, section_id=MISSING, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [local-coder] FSM-G-05
def test_fsm_g_05__a_section_of_another_workspace_is_answered_with_404(db, w1, w2, f9, mk_section):
    """FSM-G-05 — a section of another workspace is answered with 404.
    Rules: `get_factory_section` R2, Errors row 1"""
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory_section(db, section_id=s9.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert snap(db, s9) == before_s9


# [local-coder] FSM-G-07
@pytest.mark.xfail(strict=True, reason="BUG-916: get_factory_section returns soft-deleted sections")
def test_fsm_g_07__a_soft_deleted_section_is_answered_with_404_by_default(db, w1, mk_section):
    """FSM-G-07 — a soft-deleted section is answered with 404 by default.
    Rules: `get_factory_section` R3 [BUG-916], Errors row 1"""
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory_section(db, section_id=sx.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {sx.id} not found"
    # Then 4
    assert snap(db, sx) == before_sx


# [local-coder] FSM-G-09
@pytest.mark.xfail(strict=True, reason="BUG-916: get_factory_section returns soft-deleted sections")
def test_fsm_g_09__include_deleted_true_still_answers_404_for_a_soft_deleted_section_of(db, w1, w2, f9, mk_section):
    """FSM-G-09 — include_deleted=True still answers 404 for a soft-deleted section of another workspace.
    Rules: `get_factory_section` R4 [BUG-916]"""
    sx9 = mk_section(name="Old Bin", factory_id=f9.id, workspace_id=w2.id, deleted=True)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory_section(db, section_id=sx9.id, workspace_id=w1.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {sx9.id} not found"


# [local-coder] FSM-G-10
@pytest.mark.xfail(strict=True, reason="BUG-916: get_factory_section returns soft-deleted sections")
def test_fsm_g_10__include_deleted_true_returns_a_live_section_as_well(db, w1, mk_section):
    """FSM-G-10 — include_deleted=True returns a live section as well.
    Rules: `get_factory_section` R4 [BUG-916], R1"""
    s1 = mk_section(name="Paint")

    result = M.get_factory_section(db, section_id=s1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.is_deleted is False


# [local-coder] FSM-G-11
@pytest.mark.xfail(strict=True, reason="BUG-925: A section of a soft-deleted factory can still be opened by id")
def test_fsm_g_11__a_live_section_of_a_soft_deleted_factory_is_answered_with_404_by(db, w1, fd, mk_section):
    """FSM-G-11 — a live section of a soft-deleted factory is answered with 404 by default.
    Rules: `get_factory_section` R5 [BUG-925], Errors row 1"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory_section(db, section_id=sh.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {sh.id} not found"
    # Then 4
    assert snap(db, sh) == before_sh


# [local-coder] FSM-G-12
@pytest.mark.xfail(strict=True, reason="BUG-925: A section of a soft-deleted factory can still be opened by id")
def test_fsm_g_12__include_deleted_true_returns_a_live_section_of_a_soft_deleted_factory(db, w1, fd, mk_section):
    """FSM-G-12 — include_deleted=True returns a live section of a soft-deleted factory.
    Rules: `get_factory_section` R5 [BUG-925]"""
    sh = mk_section(name="Paint", factory_id=fd.id)

    result = M.get_factory_section(db, section_id=sh.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == sh.id
    # Then 2
    assert result.factory_id == fd.id


# [local-coder] FSM-S-01
def test_fsm_s_01__without_a_factory_every_section_of_the_workspace_is_returned_as_a_list(db, w1, f2, mk_section):
    """FSM-S-01 — without a factory every section of the workspace is returned as a list.
    Rules: `search_factory_sections` R1, R9 (`search=None`)"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    s3 = mk_section(name="Cutting", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [s1.id, s2.id, s3.id]
    # Then 3
    assert isinstance(result[0], FactorySection)


# [local-coder] FSM-S-02
def test_fsm_s_02__a_section_of_another_workspace_is_not_listed(db, w1, w2, f9, mk_section):
    """FSM-S-02 — a section of another workspace is not listed.
    Rules: `search_factory_sections` R1"""
    s1 = mk_section(name="Paint")
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-03
def test_fsm_s_03__a_call_for_the_second_workspace_lists_only_that_workspace_s_section(db, w2, f9, mk_section):
    """FSM-S-03 — a call for the second workspace lists only that workspace's section.
    Rules: `search_factory_sections` R1"""
    mk_section(name="Paint")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M.search_factory_sections(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s9.id]


# [local-coder] FSM-S-04
def test_fsm_s_04__an_unknown_workspace_id_returns_an_empty_list(db, mk_section):
    """FSM-S-04 — an unknown workspace id returns an empty list.
    Rules: `search_factory_sections` R1"""
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] FSM-S-05
def test_fsm_s_05__a_live_section_with_is_active_false_is_listed(db, w1, mk_section):
    """FSM-S-05 — a live section with is_active False is listed.
    Rules: `search_factory_sections` R1"""
    s1 = mk_section(name="Paint")
    si = mk_section(name="Idle Bay", is_active=False)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, si.id]


# [local-coder] FSM-S-06
def test_fsm_s_06__with_a_factory_only_that_factory_s_sections_are_returned(db, w1, f1, f2, mk_section):
    """FSM-S-06 — with a factory only that factory's sections are returned.
    Rules: `search_factory_sections` R2"""
    s1 = mk_section(name="Paint")
    mk_section(name="Cutting", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-07
def test_fsm_s_07__a_call_for_the_other_factory_returns_only_its_section(db, w1, f2, mk_section):
    """FSM-S-07 — a call for the other factory returns only its section.
    Rules: `search_factory_sections` R2"""
    mk_section(name="Paint")
    s3 = mk_section(name="Cutting", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert ids(result) == [s3.id]


# [local-coder] FSM-S-08
def test_fsm_s_08__an_unknown_factory_id_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-08 — an unknown factory id returns an empty list.
    Rules: `search_factory_sections` R2"""
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] FSM-S-09
def test_fsm_s_09__a_negative_factory_id_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-09 — a negative factory id returns an empty list.
    Rules: `search_factory_sections` R2"""
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=-1)

    # Then 1
    assert result == []


# [local-coder] FSM-S-10
def test_fsm_s_10__a_factory_of_another_workspace_returns_an_empty_list(db, w1, w2, f9, mk_section):
    """FSM-S-10 — a factory of another workspace returns an empty list.
    Rules: `search_factory_sections` R2"""
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f9.id)

    # Then 1
    assert result == []


# [local-coder] FSM-S-11
@pytest.mark.xfail(strict=True, reason="BUG-922: Section list treats factory_id=0 as 'no factory filter'")
def test_fsm_s_11__factory_id_0_filters_like_any_id_and_returns_an_empty_list(db, w1, f2, mk_section):
    """FSM-S-11 — factory id 0 filters like any id and returns an empty list.
    Rules: `search_factory_sections` R2a [BUG-922]"""
    mk_section(name="Paint")
    mk_section(name="Cutting", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] FSM-S-12
def test_fsm_s_12__without_a_factory_a_soft_deleted_section_is_not_listed_and_the_call(db, w1, mk_section):
    """FSM-S-12 — without a factory a soft-deleted section is not listed and the call changes nothing.
    Rules: `search_factory_sections` R5, Side effects"""
    s1 = mk_section(name="Paint")
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)
    before = written(db)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert snap(db, sx) == before_sx
    # Then 3
    assert written(db) == before


# [local-coder] FSM-S-13
def test_fsm_s_13__with_a_factory_a_soft_deleted_section_is_not_listed(db, w1, f1, mk_section):
    """FSM-S-13 — with a factory a soft-deleted section is not listed.
    Rules: `search_factory_sections` R5"""
    s1 = mk_section(name="Paint")
    mk_section(name="Old Line", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-14
def test_fsm_s_14__a_workspace_whose_only_section_is_soft_deleted_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-14 — a workspace whose only section is soft-deleted returns an empty list.
    Rules: `search_factory_sections` R5, R11"""
    mk_section(name="Old Line", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSM-S-15
def test_fsm_s_15__include_deleted_true_without_a_factory_lists_soft_deleted_sections(db, w1, mk_section):
    """FSM-S-15 — include_deleted=True without a factory lists soft-deleted sections along with live ones.
    Rules: `search_factory_sections` R6 [BUG-920] (the manager part, holds today)"""
    s1 = mk_section(name="Paint")
    sx = mk_section(name="Old Line", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sx.id]


# [local-coder] FSM-S-16
def test_fsm_s_16__include_deleted_true_with_a_factory_lists_its_soft_deleted_sections(db, w1, f1, mk_section):
    """FSM-S-16 — include_deleted=True with a factory lists its soft-deleted sections along with live ones.
    Rules: `search_factory_sections` R6 [BUG-920] (the manager part, holds today)"""
    s1 = mk_section(name="Paint")
    sx = mk_section(name="Old Line", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sx.id]


# [local-coder] FSM-S-18
def test_fsm_s_18__an_explicit_include_deleted_false_hides_the_soft_deleted_section(db, w1, mk_section):
    """FSM-S-18 — an explicit include_deleted=False hides the soft-deleted section.
    Rules: `search_factory_sections` R5"""
    s1 = mk_section(name="Paint")
    mk_section(name="Old Line", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, include_deleted=False)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-19
@pytest.mark.xfail(strict=True, reason="BUG-924: Workspace-wide section list shows sections of a soft-deleted factory")
def test_fsm_s_19__without_a_factory_the_live_section_of_a_soft_deleted_factory_is_hidden(db, w1, fd, mk_section):
    """FSM-S-19 — without a factory the live section of a soft-deleted factory is hidden.
    Rules: `search_factory_sections` R7 [BUG-924] (P4)"""
    s1 = mk_section(name="Paint")
    sh = mk_section(name="Cutting", factory_id=fd.id)
    before_sh = snap(db, sh)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert ids(result) == [s1.id]
    # Then 3
    assert snap(db, sh) == before_sh


# [local-coder] FSM-S-20
@pytest.mark.xfail(strict=True, reason="BUG-904: Sections of a soft-deleted factory are still returned")
def test_fsm_s_20__with_the_soft_deleted_factory_as_filter_its_live_section_is_hidden(db, w1, fd, mk_section):
    """FSM-S-20 — with the soft-deleted factory as filter its live section is hidden.
    Rules: `search_factory_sections` R7 [BUG-904]"""
    sh = mk_section(name="Cutting", factory_id=fd.id)
    before_sh = snap(db, sh)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert result == []
    # Then 2
    assert snap(db, sh) == before_sh


# [local-coder] FSM-S-21
def test_fsm_s_21__include_deleted_true_without_a_factory_lists_the_section_of_a_soft(db, w1, fd, mk_section):
    """FSM-S-21 — include_deleted=True without a factory lists the section of a soft-deleted factory.
    Rules: `search_factory_sections` R7"""
    s1 = mk_section(name="Paint")
    sh = mk_section(name="Cutting", factory_id=fd.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sh.id]


# [local-coder] FSM-S-22
def test_fsm_s_22__include_deleted_true_with_the_soft_deleted_factory_as_filter_lists(db, w1, fd, mk_section):
    """FSM-S-22 — include_deleted=True with the soft-deleted factory as filter lists its section.
    Rules: `search_factory_sections` R7"""
    sh = mk_section(name="Cutting", factory_id=fd.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=fd.id, include_deleted=True)

    # Then 1
    assert ids(result) == [sh.id]


# [local-coder] FSM-S-23
def test_fsm_s_23__the_section_of_a_live_but_inactive_factory_is_listed(db, w1, fi, mk_section):
    """FSM-S-23 — the section of a live but inactive factory is listed.
    Rules: `search_factory_sections` R7 (an inactive factory hides nothing)"""
    s1 = mk_section(name="Paint")
    sf = mk_section(name="Cutting", factory_id=fi.id)

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sf.id]


# [claude] FSM-S-24
def test_fsm_s_24__once_its_factory_is_no_longer_deleted_the_section_is_listed_again(db, w1, fd, mk_section):
    """FSM-S-24 — once its factory is no longer deleted the section is listed again, unchanged.
    Rules: `search_factory_sections` R7 (rows untouched, listed again)"""
    sh = mk_section(name="Cutting", factory_id=fd.id)
    before_sh = snap(db, sh)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [sh.id]
    # Then 2
    assert snap(db, sh) == before_sh


# [local-coder] FSM-S-25
def test_fsm_s_25__the_search_ignores_case_and_finds_the_text_in_the_names_of_two(db, w1, f2, mk_section):
    """FSM-S-25 — the search ignores case and finds the text in the names of two factories' sections.
    Rules: `search_factory_sections` R8"""
    s1 = mk_section(name="Main Hall")
    mk_section(name="Paint")
    s3 = mk_section(name="Side hall", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, search="HALL")

    # Then 1
    assert sorted(ids(result)) == [s1.id, s3.id]


# [local-coder] FSM-S-26
def test_fsm_s_26__the_search_finds_text_in_the_middle_of_a_name(db, w1, mk_section):
    """FSM-S-26 — the search finds text in the middle of a name.
    Rules: `search_factory_sections` R8"""
    mk_section(name="Main Hall")
    s2 = mk_section(name="Cutting")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="utt")

    # Then 1
    assert ids(result) == [s2.id]


# [local-coder] FSM-S-27
def test_fsm_s_27__the_factory_s_name_is_not_searched(db, w1, mk_section):
    """FSM-S-27 — the factory's name is not searched.
    Rules: `search_factory_sections` R8"""
    mk_section(name="Cutting")
    mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="plant")

    # Then 1
    assert result == []


# [local-coder] FSM-S-28
def test_fsm_s_28__two_inner_spaces_in_the_search_text_do_not_match_a_name_with_one_space(db, w1, mk_section):
    """FSM-S-28 — two inner spaces in the search text do not match a name with one space.
    Rules: `search_factory_sections` R8"""
    mk_section(name="Main Hall")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="main  hall")

    # Then 1
    assert result == []


# [local-coder] FSM-S-29
def test_fsm_s_29__one_inner_space_in_the_search_text_matches_the_space_inside_a_name(db, w1, mk_section):
    """FSM-S-29 — one inner space in the search text matches the space inside a name.
    Rules: `search_factory_sections` R8"""
    s1 = mk_section(name="Main Hall")
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="n h")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-30
def test_fsm_s_30__a_percent_sign_in_the_search_text_matches_only_a_percent_sign(db, w1, mk_section):
    """FSM-S-30 — a percent sign in the search text matches only a percent sign.
    Rules: `search_factory_sections` R8a (HR-8)"""
    s1 = mk_section(name="50% zone")
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="%")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-31
def test_fsm_s_31__a_percent_sign_finds_nothing_when_no_section_contains_one(db, w1, mk_section):
    """FSM-S-31 — a percent sign finds nothing when no section contains one.
    Rules: `search_factory_sections` R8a (HR-8)"""
    mk_section(name="Paint")
    mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="%")

    # Then 1
    assert result == []


# [local-coder] FSM-S-32
def test_fsm_s_32__an_underscore_in_the_search_text_matches_only_an_underscore(db, w1, mk_section):
    """FSM-S-32 — an underscore in the search text matches only an underscore.
    Rules: `search_factory_sections` R8a (HR-8)"""
    s1 = mk_section(name="Bay_2")
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="_")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-33
def test_fsm_s_33__the_search_combines_with_the_factory_filter(db, w1, f2, mk_section):
    """FSM-S-33 — the search combines with the factory filter.
    Rules: `search_factory_sections` R2, R8"""
    mk_section(name="Main Hall")
    s3 = mk_section(name="Side hall", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f2.id, search="hall")

    # Then 1
    assert ids(result) == [s3.id]


# [local-coder] FSM-S-34
def test_fsm_s_34__search_none_applies_no_search_filter(db, w1, mk_section):
    """FSM-S-34 — search=None applies no search filter.
    Rules: `search_factory_sections` R9"""
    s1 = mk_section(name="Main Hall")
    s2 = mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search=None)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]


# [local-coder] FSM-S-35
def test_fsm_s_35__an_empty_search_text_applies_no_search_filter(db, w1, mk_section):
    """FSM-S-35 — an empty search text applies no search filter.
    Rules: `search_factory_sections` R9"""
    s1 = mk_section(name="Main Hall")
    s2 = mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="")

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]


# [local-coder] FSM-S-36
@pytest.mark.xfail(strict=True, reason="BUG-921: Section search text is not trimmed")
def test_fsm_s_36__a_search_of_three_spaces_applies_no_search_filter(db, w1, mk_section):
    """FSM-S-36 — a search of three spaces applies no search filter.
    Rules: `search_factory_sections` R9 [BUG-921] (P1)"""
    s1 = mk_section(name="Main Hall")
    s2 = mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]


# [local-coder] FSM-S-38
@pytest.mark.xfail(strict=True, reason="BUG-921: Section search text is not trimmed")
def test_fsm_s_38__spaces_around_the_search_text_are_removed_before_matching(db, w1, mk_section):
    """FSM-S-38 — spaces around the search text are removed before matching.
    Rules: `search_factory_sections` R9 [BUG-921] (P1)"""
    s1 = mk_section(name="Main Hall")
    mk_section(name="Paint")

    result = M.search_factory_sections(db, workspace_id=w1.id, search=" hall ")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-39
def test_fsm_s_39__a_matching_soft_deleted_section_is_not_returned_by_a_search(db, w1, mk_section):
    """FSM-S-39 — a matching soft-deleted section is not returned by a search.
    Rules: `search_factory_sections` R10"""
    s1 = mk_section(name="Main Hall")
    mk_section(name="Old Hall", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, search="hall")

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] FSM-S-40
def test_fsm_s_40__a_matching_soft_deleted_section_is_returned_by_a_search_with_include(db, w1, mk_section):
    """FSM-S-40 — a matching soft-deleted section is returned by a search with include_deleted=True.
    Rules: `search_factory_sections` R10, R6"""
    s1 = mk_section(name="Main Hall")
    sx = mk_section(name="Old Hall", deleted=True)

    result = M.search_factory_sections(db, workspace_id=w1.id, search="hall", include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sx.id]


# [local-coder] FSM-S-41
def test_fsm_s_41__a_workspace_without_sections_returns_an_empty_list(db, w1):
    """FSM-S-41 — a workspace without sections returns an empty list.
    Rules: `search_factory_sections` R11"""
    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSM-S-42
def test_fsm_s_42__skip_equal_to_the_number_of_sections_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-42 — skip equal to the number of sections returns an empty list.
    Rules: `search_factory_sections` R11"""
    mk_section(name="Paint")
    mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] FSM-S-43
def test_fsm_s_43__skip_past_the_number_of_sections_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-43 — skip past the number of sections returns an empty list.
    Rules: `search_factory_sections` R11"""
    mk_section(name="Paint")
    mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] FSM-S-44
def test_fsm_s_44__skip_1_of_two_sections_returns_one_of_them(db, w1, mk_section):
    """FSM-S-44 — skip 1 of two sections returns one of them.
    Rules: `search_factory_sections` R11"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {s1.id, s2.id}


# [local-coder] FSM-S-46
def test_fsm_s_46__limit_0_returns_an_empty_list(db, w1, mk_section):
    """FSM-S-46 — limit 0 returns an empty list.
    Rules: `search_factory_sections` R11"""
    mk_section(name="Paint")
    mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FSM-S-47
def test_fsm_s_47__without_a_factory_the_default_limit_returns_exactly_100_of_101_live(db, w1, mk_section):
    """FSM-S-47 — without a factory the default limit returns exactly 100 of 101 live sections.
    Rules: `search_factory_sections` R11"""
    bays = [mk_section(name=f"Bay {k:03d}") for k in range(1, 102)]

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= {b.id for b in bays}


# [claude] FSM-S-48
def test_fsm_s_48__with_a_factory_the_default_limit_returns_exactly_100_of_101_live(db, w1, f1, mk_section):
    """FSM-S-48 — with a factory the default limit returns exactly 100 of 101 live sections.
    Rules: `search_factory_sections` R11"""
    bays = [mk_section(name=f"Bay {k:03d}") for k in range(1, 102)]

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= {b.id for b in bays}


# [local-coder] FSM-S-49
def test_fsm_s_49__without_a_factory_a_negative_limit_is_rejected_by_the_database(db, w1, mk_section):
    """FSM-S-49 — without a factory a negative limit is rejected by the database.
    Rules: `search_factory_sections` R11, Errors row 1"""
    mk_section(name="Paint")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factory_sections(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] FSM-S-50
def test_fsm_s_50__with_a_factory_a_negative_limit_is_rejected_by_the_database(db, w1, f1, mk_section):
    """FSM-S-50 — with a factory a negative limit is rejected by the database.
    Rules: `search_factory_sections` R11, Errors row 1"""
    mk_section(name="Paint")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] FSM-S-52
def test_fsm_s_52__with_a_factory_a_negative_skip_is_rejected_by_the_database(db, w1, f1, mk_section):
    """FSM-S-52 — with a factory a negative skip is rejected by the database.
    Rules: `search_factory_sections` R11, Errors row 2"""
    mk_section(name="Paint")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] FSM-S-53
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging (non-strict: today's result depends on the physical row order)")
def test_fsm_s_53__a_soft_deleted_section_does_not_use_up_a_place_in_the_page(db, w1, f2, mk_section):
    """FSM-S-53 — a soft-deleted section does not use up a place in the page.
    Rules: `search_factory_sections` R3 [BUG-917], R5 [BUG-917]"""
    mk_section(name="Old Line", deleted=True)
    s2 = mk_section(name="Paint")
    s3 = mk_section(name="Welding", factory_id=f2.id)

    result = M.search_factory_sections(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [s2.id, s3.id]


# [claude] FSM-S-54
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging (non-strict: today's result depends on the physical row order)")
def test_fsm_s_54__a_search_finds_a_matching_section_that_lies_outside_the_first_page(db, w1, mk_section):
    """FSM-S-54 — a search finds a matching section that lies outside the first page of rows.
    Rules: `search_factory_sections` R3 [BUG-917], R8"""
    mk_section(name="Cutting")
    mk_section(name="Paint")
    s3 = mk_section(name="Main Hall")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="hall", limit=2)

    # Then 1
    assert ids(result) == [s3.id]


# [claude] FSM-S-55
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging (non-strict: today's result depends on the physical row order)")
def test_fsm_s_55__skip_counts_live_sections_only(db, w1, f1, mk_section):
    """FSM-S-55 — skip counts live sections only.
    Rules: `search_factory_sections` R3 [BUG-917], R5 [BUG-917]"""
    mk_section(name="Old Line", deleted=True)
    s2 = mk_section(name="Paint")
    s3 = mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {s2.id, s3.id}


# [claude] FSM-S-56
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging (non-strict: today's result depends on the physical row order)")
def test_fsm_s_56__with_a_factory_the_default_list_shows_a_live_section_that_comes_after(db, w1, f1, mk_section):
    """FSM-S-56 — with a factory the default list shows a live section that comes after 100 deleted ones.
    Rules: `search_factory_sections` R3 [BUG-917], R5 [BUG-917]"""
    for k in range(1, 101):
        mk_section(name=f"Old {k:03d}", deleted=True)
    late = mk_section(name="Late")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [late.id]


# [claude] FSM-S-57
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging (non-strict: today's result depends on the physical row order)")
def test_fsm_s_57__without_a_factory_a_search_finds_a_live_section_that_comes_after_100(db, w1, mk_section):
    """FSM-S-57 — without a factory a search finds a live section that comes after 100 deleted ones.
    Rules: `search_factory_sections` R3 [BUG-917], R5 [BUG-917], R8"""
    for k in range(1, 101):
        mk_section(name=f"Old {k:03d}", deleted=True)
    late = mk_section(name="Late")

    result = M.search_factory_sections(db, workspace_id=w1.id, search="late")

    # Then 1
    assert ids(result) == [late.id]


# [claude] FSM-S-58
@pytest.mark.xfail(strict=True, reason="BUG-917: Section list drops deleted rows and applies the search after paging")
def test_fsm_s_58__without_a_factory_the_list_query_leaves_out_soft_deleted_sections_in(db, w1, mk_section):
    """FSM-S-58 — without a factory the list query leaves out soft-deleted sections in the database, before the page.
    Rules: `search_factory_sections` R3 [BUG-917], R5 [BUG-917]"""
    s1 = mk_section(name="Paint")
    mk_section(name="Old Line", deleted=True)

    with recorded_sql(db) as statements:
        result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert any("factory_sections.is_deleted" in where_clause(s) for s in section_selects(statements))


# [claude] FSM-S-59
@pytest.mark.xfail(strict=True, reason="BUG-917: Section list drops deleted rows and applies the search after paging")
def test_fsm_s_59__with_a_factory_the_search_text_is_a_condition_of_the_query_before_the(db, w1, f1, mk_section):
    """FSM-S-59 — with a factory the search text is a condition of the query, before the page.
    Rules: `search_factory_sections` R3 [BUG-917], R8"""
    s1 = mk_section(name="Main Hall")
    mk_section(name="Paint")

    with recorded_sql(db) as statements:
        result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, search="hall")

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert any("like" in where_clause(s) for s in section_selects(statements))


# [claude] FSM-S-60
@pytest.mark.xfail(strict=False, reason="BUG-918: Workspace-wide section list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fsm_s_60__without_a_factory_the_list_is_ordered_by_name_ignoring_case(db, w1, f2, mk_section):
    """FSM-S-60 — without a factory the list is ordered by name ignoring case.
    Rules: `search_factory_sections` R4 [BUG-918]"""
    mk_section(name="Delta")
    mk_section(name="alpha", factory_id=f2.id)
    mk_section(name="echo")
    mk_section(name="Bravo", factory_id=f2.id)
    mk_section(name="charlie")

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]


# [claude] FSM-S-61
@pytest.mark.xfail(strict=False, reason="BUG-918: Workspace-wide section list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fsm_s_61__without_a_factory_names_equal_ignoring_case_come_back_in_id_order(db, w1, f2, mk_section):
    """FSM-S-61 — without a factory names equal ignoring case come back in id order.
    Rules: `search_factory_sections` R4 [BUG-918]"""
    s1 = mk_section(name="Zinc Room")
    s2 = mk_section(name="paint", factory_id=f2.id)
    s3 = mk_section(name="Paint")
    s4 = mk_section(name="Assembly")

    result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s4.id, s2.id, s3.id, s1.id]


# [claude] FSM-S-62
@pytest.mark.xfail(strict=False, reason="BUG-918: Workspace-wide section list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fsm_s_62__deleted_sections_are_ordered_together_with_live_ones(db, w1, mk_section):
    """FSM-S-62 — deleted sections are ordered together with live ones.
    Rules: `search_factory_sections` R4 [BUG-918], R6"""
    s1 = mk_section(name="Zinc Room")
    sx = mk_section(name="Mango", deleted=True)
    s3 = mk_section(name="apple")
    s4 = mk_section(name="mango")

    result = M.search_factory_sections(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [s3.id, sx.id, s4.id, s1.id]


# [claude] FSM-S-63
@pytest.mark.xfail(strict=False, reason="BUG-918: Workspace-wide section list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fsm_s_63__without_a_factory_a_middle_page_holds_the_second_and_third_section_by(db, w1, f2, mk_section):
    """FSM-S-63 — without a factory a middle page holds the second and third section by name.
    Rules: `search_factory_sections` R4 [BUG-918], R11"""
    mk_section(name="Delta")
    mk_section(name="alpha", factory_id=f2.id)
    mk_section(name="echo")
    mk_section(name="Bravo", factory_id=f2.id)
    mk_section(name="charlie")

    result = M.search_factory_sections(db, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert names(result) == ["Bravo", "charlie"]


# [claude] FSM-S-64
@pytest.mark.xfail(strict=False, reason="BUG-903: Section list of a factory has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fsm_s_64__with_a_factory_the_list_is_ordered_by_name_ignoring_case(db, w1, f1, mk_section):
    """FSM-S-64 — with a factory the list is ordered by name ignoring case.
    Rules: `search_factory_sections` R4 [BUG-903]"""
    mk_section(name="Delta")
    mk_section(name="alpha")
    mk_section(name="echo")
    mk_section(name="Bravo")
    mk_section(name="charlie")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]


# [claude] FSM-S-65
@pytest.mark.xfail(strict=True, reason="BUG-918: Workspace-wide section list has no sort order")
def test_fsm_s_65__without_a_factory_the_list_query_asks_the_database_for_a_name_order(db, w1, mk_section):
    """FSM-S-65 — without a factory the list query asks the database for a name order.
    Rules: `search_factory_sections` R4 [BUG-918]"""
    s1 = mk_section(name="Paint")

    with recorded_sql(db) as statements:
        result = M.search_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert any(" order by " in s and "name" in s.split(" order by ", 1)[1] for s in section_selects(statements))


# [claude] FSM-S-66
@pytest.mark.xfail(strict=True, reason="BUG-903: Section list of a factory has no sort order")
def test_fsm_s_66__with_a_factory_the_list_query_asks_the_database_for_a_name_order(db, w1, f1, mk_section):
    """FSM-S-66 — with a factory the list query asks the database for a name order.
    Rules: `search_factory_sections` R4 [BUG-903]"""
    s1 = mk_section(name="Paint")

    with recorded_sql(db) as statements:
        result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert any(" order by " in s and "name" in s.split(" order by ", 1)[1] for s in section_selects(statements))


# [local-coder] FSM-D-01
def test_fsm_d_01__a_live_section_is_marked_deleted_with_the_clock_value_and_the_acting(db, w1, u2, mk_section):
    """FSM-D-01 — a live section is marked deleted with the clock value and the acting user.
    Rules: `delete_factory_section` R3, Returns"""
    s1 = mk_section(name="Paint")

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    # Then 4
    assert row.deleted_by == u2.id
    # Then 5
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSM-D-02
def test_fsm_d_02__no_other_column_of_the_section_is_changed_by_the_delete(db, w1, u1, u2, f1, mk_section):
    """FSM-D-02 — no other column of the section is changed by the delete.
    Rules: `delete_factory_section` R4"""
    s1 = mk_section(name="Paint", updated_by=u1.id)
    created_before = s1.created_at

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.updated_by == u1.id
    # Then 5
    assert row.created_at == created_before
    # Then 6
    assert row.is_active is True
    # Then 7
    assert row.updated_at is not None


# [local-coder] FSM-D-03
def test_fsm_d_03__a_live_section_with_is_active_false_is_deleted_and_stays_inactive(db, w1, u2, mk_section):
    """FSM-D-03 — a live section with is_active False is deleted and stays inactive.
    Rules: `delete_factory_section` R3, R4"""
    si = mk_section(name="Idle Bay", is_active=False)

    result = M.delete_factory_section(db, section_id=si.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is si
    # Then 2
    row = reread(db, si)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is False


# [local-coder] FSM-D-04
def test_fsm_d_04__an_id_that_no_section_has_is_answered_with_404(db, w1, u2, mk_section):
    """FSM-D-04 — an id that no section has is answered with 404.
    Rules: `delete_factory_section` R1, Errors row 1"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] FSM-D-05
def test_fsm_d_05__a_section_of_another_workspace_is_answered_with_404_and_not_deleted(db, w1, w2, f9, u2, mk_section):
    """FSM-D-05 — a section of another workspace is answered with 404 and not deleted.
    Rules: `delete_factory_section` R1, Errors row 1"""
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=s9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert snap(db, s9) == before_s9
    # Then 5
    row = reread(db, s9)
    assert row.is_deleted is False
    assert row.deleted_at is None


# [claude] FSM-D-10
def test_fsm_d_10__after_the_delete_the_section_leaves_the_default_list_its_name_is_free(db, w1, u2, f1, mk_section):
    """FSM-D-10 — after the delete the section leaves the default list, its name is free, and update and delete answer 400.
    Rules: `delete_factory_section` R7; `search_factory_sections` R5, R6; `create_factory_section` R7; `update_factory_section` R3"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    assert ids(M.search_factory_sections(db, workspace_id=w1.id)) == [s2.id]
    # Then 3
    assert sorted(ids(M.search_factory_sections(db, workspace_id=w1.id, include_deleted=True))) == [s1.id, s2.id]
    # Then 4
    new = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)
    assert new.id != s1.id
    # Then 5
    with pytest.raises(HTTPException) as exc:
        M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id)
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 6
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)
    assert exc.value.detail == "Factory section is already deleted"


# [claude] FSM-D-11
def test_fsm_d_11__the_delete_is_flushed_but_not_committed_a_rollback_makes_the_section(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-D-11 — the delete is flushed but not committed: a rollback makes the section live again.
    Rules: `delete_factory_section` R8, Returns"""
    s1 = mk_section(name="Paint")
    ma1 = mk_machine(of=f1, name="Lathe")
    mk_assignment(of=ma1, to=s1)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert result is s1
        # Then 2
        row = reread(db, s1)
        assert row.is_deleted is True
        sp.rollback()
        # Then 3
        row = reread(db, s1)
        assert row.is_deleted is False
        assert row.deleted_at is None
        assert row.deleted_by is None
        # Then 4
        assert len(rows_of_section(db, s1)) == 1
        # Then 5
        assert commit_spy.call_count == 0


# [local-coder] FSM-D-12
def test_fsm_d_12__a_user_id_that_is_no_profile_id_fails_on_flush_and_the_section_stays(db, w1, mk_section):
    """FSM-D-12 — a user_id that is no profile id fails on flush and the section stays live.
    Rules: `delete_factory_section` R9, Errors row 4"""
    s1 = mk_section(name="Paint")

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    row = reread(db, s1)
    assert row.is_deleted is False
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FSM-D-13
@pytest.mark.xfail(strict=True, reason="BUG-927: A section inside a soft-deleted factory can still be deleted")
def test_fsm_d_13__a_live_section_of_a_soft_deleted_factory_cannot_be_deleted(db, w1, u2, fd, mk_section):
    """FSM-D-13 — a live section of a soft-deleted factory cannot be deleted.
    Rules: `delete_factory_section` R10 [BUG-927], Errors row 3"""
    sh = mk_section(name="Paint", factory_id=fd.id)
    before_sh = snap(db, sh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=sh.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a section of a deleted factory"
    # Then 4
    assert snap(db, sh) == before_sh
    # Then 5
    row = reread(db, sh)
    assert row.is_deleted is False


# [local-coder] FSM-D-14
def test_fsm_d_14__a_section_of_a_live_but_inactive_factory_is_deleted(db, w1, u2, fi, mk_section):
    """FSM-D-14 — a section of a live but inactive factory is deleted.
    Rules: `delete_factory_section` R10 (an inactive factory is not refused), R3"""
    sf = mk_section(name="Paint", factory_id=fi.id)

    result = M.delete_factory_section(db, section_id=sf.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is sf
    # Then 2
    row = reread(db, sf)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id


# [local-coder] FSM-D-15
def test_fsm_d_15__an_already_deleted_section_of_a_soft_deleted_factory_gets_the_already(db, w1, u2, fd, mk_section):
    """FSM-D-15 — an already deleted section of a soft-deleted factory gets the "already deleted" message.
    Rules: `delete_factory_section` R2, R10 (checked after R2)"""
    sxh = mk_section(name="Old Line", factory_id=fd.id, deleted=True)
    before_sxh = snap(db, sxh)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=sxh.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section is already deleted"
    # Then 4
    assert snap(db, sxh) == before_sxh


# [local-coder] FSM-D-16
def test_fsm_d_16__only_that_section_row_is_touched(db, w1, u2, f1, mk_section):
    """FSM-D-16 — only that section row is touched.
    Rules: `delete_factory_section` Side effects"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    before_s2 = snap(db, s2)
    before_f1 = snap(db, f1)

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, s2) == before_s2
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    assert count_rows(db, "factory_sections") == 2


# [local-coder] FSM-D-17
def test_fsm_d_17__a_section_of_the_second_workspace_is_deleted_from_its_own_workspace(db, w2, f9, u2, mk_section):
    """FSM-D-17 — a section of the second workspace is deleted from its own workspace.
    Rules: `delete_factory_section` R3"""
    s1 = mk_section(name="Paint")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s1 = snap(db, s1)

    result = M.delete_factory_section(db, section_id=s9.id, workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result is s9
    # Then 2
    row = reread(db, s9)
    assert row.is_deleted is True
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 3
    assert snap(db, s1) == before_s1


# [local-coder] FSM-CN-01
def test_fsm_cn_01__a_live_section_of_the_factory_with_that_name_gives_true_and_nothing(db, w1, f1, mk_section):
    """FSM-CN-01 — a live section of the factory with that name gives True and nothing is changed.
    Rules: `_check_name_exists_in_factory` R1, Side effects"""
    s1 = mk_section(name="Paint")
    before_s1 = snap(db, s1)
    before = written(db)

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is True
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    assert written(db) == before


# [local-coder] FSM-CN-02
def test_fsm_cn_02__a_name_that_no_section_of_the_factory_has_gives_false(db, w1, f1, mk_section):
    """FSM-CN-02 — a name that no section of the factory has gives False.
    Rules: `_check_name_exists_in_factory` R1"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Welding")

    # Then 1
    assert result is False


# [local-coder] FSM-CN-03
def test_fsm_cn_03__a_section_of_another_factory_with_that_name_is_not_considered(db, w1, f1, f2, mk_section):
    """FSM-CN-03 — a section of another factory with that name is not considered.
    Rules: `_check_name_exists_in_factory` R2"""
    mk_section(name="Paint", factory_id=f2.id)

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is False


# [local-coder] FSM-CN-04
def test_fsm_cn_04__a_section_of_another_workspace_is_not_considered(db, w1, w2, f9, mk_section):
    """FSM-CN-04 — a section of another workspace is not considered.
    Rules: `_check_name_exists_in_factory` R2"""
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f9.id, name="Packing")

    # Then 1
    assert result is False


# [local-coder] FSM-CN-05
def test_fsm_cn_05__the_check_for_the_second_workspace_finds_that_workspace_s_section(db, w2, f9, mk_section):
    """FSM-CN-05 — the check for the second workspace finds that workspace's section.
    Rules: `_check_name_exists_in_factory` R1, R2"""
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M._check_name_exists_in_factory(db, workspace_id=w2.id, factory_id=f9.id, name="Packing")

    # Then 1
    assert result is True


# [local-coder] FSM-CN-06
def test_fsm_cn_06__a_soft_deleted_section_with_that_name_is_ignored(db, w1, f1, mk_section):
    """FSM-CN-06 — a soft-deleted section with that name is ignored.
    Rules: `_check_name_exists_in_factory` R3"""
    mk_section(name="Paint", deleted=True)

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is False


# [local-coder] FSM-CN-07
def test_fsm_cn_07__a_soft_deleted_and_a_live_section_with_that_name_give_true(db, w1, f1, mk_section):
    """FSM-CN-07 — a soft-deleted and a live section with that name give True.
    Rules: `_check_name_exists_in_factory` R3, R1"""
    mk_section(name="Paint", deleted=True)
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is True


# [local-coder] FSM-CN-08
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_cn_08__the_name_in_lower_case_matches_the_live_section(db, w1, f1, mk_section):
    """FSM-CN-08 — the name in lower case matches the live section.
    Rules: `_check_name_exists_in_factory` R4 [BUG-912]"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="paint")

    # Then 1
    assert result is True


# [local-coder] FSM-CN-09
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_cn_09__the_name_in_upper_case_matches_the_live_section(db, w1, f1, mk_section):
    """FSM-CN-09 — the name in upper case matches the live section.
    Rules: `_check_name_exists_in_factory` R4 [BUG-912]"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="PAINT")

    # Then 1
    assert result is True


# [local-coder] FSM-CN-10
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fsm_cn_10__the_name_with_outer_spaces_matches_the_live_section(db, w1, f1, mk_section):
    """FSM-CN-10 — the name with outer spaces matches the live section.
    Rules: `_check_name_exists_in_factory` R4 [BUG-912]"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name=" Paint ")

    # Then 1
    assert result is True


# [local-coder] FSM-CN-12
def test_fsm_cn_12__the_name_with_an_inner_space_does_not_match(db, w1, f1, mk_section):
    """FSM-CN-12 — the name with an inner space does not match.
    Rules: `_check_name_exists_in_factory` R4"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Pa int")

    # Then 1
    assert result is False


# [local-coder] FSM-CN-13
def test_fsm_cn_13__a_longer_name_that_starts_with_the_section_name_does_not_match(db, w1, f1, mk_section):
    """FSM-CN-13 — a longer name that starts with the section name does not match.
    Rules: `_check_name_exists_in_factory` R4"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint 2")

    # Then 1
    assert result is False


# [claude] FSM-CN-14
def test_fsm_cn_14__a_live_section_that_is_the_100th_live_section_of_the_factory_is_found(db, w1, f1, mk_section):
    """FSM-CN-14 — a live section that is the 100th live section of the factory is found.
    Rules: `_check_name_exists_in_factory` R5"""
    for k in range(1, 100):
        mk_section(name=f"Bay {k:03d}")
    mk_section(name="Late")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Late")

    # Then 1
    assert result is True


# [claude] FSM-CN-15
@pytest.mark.xfail(strict=False, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory (non-strict: today's result depends on the physical row order)")
def test_fsm_cn_15__a_live_section_that_comes_after_100_soft_deleted_ones_is_found(db, w1, f1, mk_section):
    """FSM-CN-15 — a live section that comes after 100 soft-deleted ones is found.
    Rules: `_check_name_exists_in_factory` R5 [BUG-911], R3"""
    for k in range(1, 101):
        mk_section(name=f"Old {k:03d}", deleted=True)
    mk_section(name="Late")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Late")

    # Then 1
    assert result is True


# [claude] FSM-CN-16
@pytest.mark.xfail(strict=False, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory (non-strict: today's result depends on the physical row order)")
def test_fsm_cn_16__a_live_section_that_is_the_101st_live_section_of_the_factory_is_found(db, w1, f1, mk_section):
    """FSM-CN-16 — a live section that is the 101st live section of the factory is found.
    Rules: `_check_name_exists_in_factory` R5 [BUG-911]"""
    for k in range(1, 101):
        mk_section(name=f"Bay {k:03d}")
    mk_section(name="Late")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Late")

    # Then 1
    assert result is True


# [claude] FSM-CN-17
@pytest.mark.xfail(strict=True, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory")
def test_fsm_cn_17__the_duplicate_check_does_not_read_a_capped_page_of_sections(db, w1, f1, mk_section):
    """FSM-CN-17 — the duplicate check does not read a capped page of sections.
    Rules: `_check_name_exists_in_factory` R5 [BUG-911]"""
    mk_section(name="Paint")

    with recorded_sql(db) as statements:
        result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is True
    # Then 2
    assert any(" limit " not in s or "name" in where_clause(s) for s in section_selects(statements))


# [local-coder] FSM-CN-18
def test_fsm_cn_18__the_section_named_by_exclude_id_is_ignored(db, w1, f1, mk_section):
    """FSM-CN-18 — the section named by exclude_id is ignored.
    Rules: `_check_name_exists_in_factory` R6"""
    s1 = mk_section(name="Paint")
    mk_section(name="Welding")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint", exclude_id=s1.id)

    # Then 1
    assert result is False


# [local-coder] FSM-CN-19
def test_fsm_cn_19__excluding_another_section_still_gives_true(db, w1, f1, mk_section):
    """FSM-CN-19 — excluding another section still gives True.
    Rules: `_check_name_exists_in_factory` R6"""
    mk_section(name="Paint")
    s2 = mk_section(name="Welding")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint", exclude_id=s2.id)

    # Then 1
    assert result is True


# [local-coder] FSM-CN-20
def test_fsm_cn_20__an_explicit_exclude_id_none_ignores_nothing(db, w1, f1, mk_section):
    """FSM-CN-20 — an explicit exclude_id=None ignores nothing.
    Rules: `_check_name_exists_in_factory` R6"""
    mk_section(name="Paint")

    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint", exclude_id=None)

    # Then 1
    assert result is True


# [local-coder] FSM-CN-21
def test_fsm_cn_21__a_factory_without_sections_gives_false(db, w1, f1):
    """FSM-CN-21 — a factory without sections gives False.
    Rules: `_check_name_exists_in_factory` R7"""
    result = M._check_name_exists_in_factory(db, workspace_id=w1.id, factory_id=f1.id, name="Paint")

    # Then 1
    assert result is False
