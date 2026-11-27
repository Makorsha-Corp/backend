"""Unit tests for app/dao/machine_section_assignment.py.

Implements tests/unit/dao/machine_section_assignment.cases.md, one test per
case. Real Postgres session (`db` fixture). Nothing is patched (Conventions,
Externals: None).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/machine_section_assignment.helpers.md as its only view of this
file; tests below a `# [claude] <ID>` comment are the `Author: claude` cards,
written by hand at finishing.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import event, func, insert, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.machine_section_assignment import machine_section_assignment_dao
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.machine_section_assignment import MachineSectionAssignmentCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_section_assignment_dao" (a module-level name, not a fixture)
dao = machine_section_assignment_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (W1, W2, U1, U2 and the fifteen standing rows)
# Each fixture depends on the one before it, so the ids rise in the order the
# Conventions list them.
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 = created_by of every Given assignment, U2 acts)
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "F1 / F2 / F9 = factories rows"
def _factory(db, name, abbreviation, workspace_id):
    return _add(db, Factory(name=name, abbreviation=abbreviation, workspace_id=workspace_id))


@pytest.fixture
def f1(db, w1, u2):
    return _factory(db, "Main Plant", "MP", w1.id)


@pytest.fixture
def f2(db, w1, f1):
    return _factory(db, "North Yard", "NY", w1.id)


@pytest.fixture
def f9(db, w2, f2):
    return _factory(db, "Far Depot", "FR", w2.id)


# Convention "S1 / S2 / S3 / SX / S9 = factory_sections rows"
def _section(db, name, factory, is_deleted=False):
    return _add(db, FactorySection(name=name, factory_id=factory.id, workspace_id=factory.workspace_id,
                                   is_deleted=is_deleted))


@pytest.fixture
def s1(db, f1, f9):
    return _section(db, "Cutting", f1)


@pytest.fixture
def s2(db, f1, s1):
    return _section(db, "Paint", f1)


@pytest.fixture
def s3(db, f2, s2):
    return _section(db, "Welding", f2)


@pytest.fixture
def sx(db, f1, s3):
    return _section(db, "Old Line", f1, is_deleted=True)


@pytest.fixture
def s9(db, f9, sx):
    return _section(db, "Packing", f9)


# Convention "M1 / M2 / M3 / MD / M9 = machines rows"
def _machine(db, name, factory, is_deleted=False):
    return _add(db, Machine(name=name, factory_id=factory.id, workspace_id=factory.workspace_id,
                            is_active=True, is_deleted=is_deleted, is_running=False))


@pytest.fixture
def m1(db, f1, s9):
    return _machine(db, "Lathe", f1)


@pytest.fixture
def m2(db, f1, m1):
    return _machine(db, "Press", f1)


@pytest.fixture
def m3(db, f1, m2):
    return _machine(db, "Drill", f1)


@pytest.fixture
def md(db, f1, m3):
    return _machine(db, "Old Saw", f1, is_deleted=True)


@pytest.fixture
def m9(db, f9, md):
    return _machine(db, "Grinder", f9)


# Convention "These fifteen rows exist in every test ... and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, f1, f2, f9, s1, s2, s3, sx, s9, m1, m2, m3, md, m9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builder (fixture; inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Convention "assignment of M to S": workspace_id = M's, created_by U1.id,
# updated_by / updated_at None, created_at left to the database.
@pytest.fixture
def mk_assignment(db, u1):
    """mk_assignment(of=<machine>, to=<section>, **columns) -> MachineSectionAssignment. Keywords only.

    Each column the card lists after "but" is one more keyword (`workspace_id=w2.id`).
    """
    def _mk(*, of, to, **columns):
        fields = {"workspace_id": of.workspace_id, "machine_id": of.id, "factory_section_id": to.id,
                  "created_by": u1.id, "updated_by": None, "updated_at": None}
        fields.update(columns)
        return _add(db, MachineSectionAssignment(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__
           for model in (MachineSectionAssignment, Machine, FactorySection, Factory)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id from its own table
def reread(db, row):
    """Fresh copy of `row` (assignment, machine, section or factory) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "rows_of(M)": expire_all, then every assignment row of machine M (any workspace)
def rows_of(db, machine):
    machine_id = _id_of(machine)
    db.expire_all()
    stmt = (select(MachineSectionAssignment).where(MachineSectionAssignment.machine_id == machine_id)
            .order_by(MachineSectionAssignment.id))
    return list(db.execute(stmt).scalars().all())


# Convention "count:" lines: rows of the named table in all workspaces, with the
# filter stated as keywords (`count_rows(db, "machine_section_assignments", id=a1_id)`)
def count_rows(db, table_name, **where):
    table = _TABLES[table_name]
    stmt = select(func.count()).select_from(table)
    for column, value in where.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": row counts of machine_section_assignments, machines,
# factory_sections and factories, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "ids(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


# Bulk Given rows of the `Author: claude` cards MSA-GS-10, GS-11 (501) and CL-06 (10 001):
# "machine Nk is M1 but `name`" and "assignment of Nk to S1", each set in one multi-row
# INSERT (ids rise in list order). Setup only; not in the helper sheet.
def bulk_assigned_machines(db, *, names, factory, section, created_by):
    """Insert one machine per name (M1's columns, `name` replaced), then one assignment of each
    to `section` (Conventions defaults). Returns (machine_ids, assignment_ids) in insertion order."""
    machines = Machine.__table__
    machine_ids = db.execute(
        insert(machines).returning(machines.c.id, sort_by_parameter_order=True),
        [{"name": name, "factory_id": factory.id, "workspace_id": factory.workspace_id, "is_active": True,
          "is_deleted": False, "is_running": False} for name in names],
    ).scalars().all()
    assignments = MachineSectionAssignment.__table__
    assignment_ids = db.execute(
        insert(assignments).returning(assignments.c.id, sort_by_parameter_order=True),
        [{"workspace_id": factory.workspace_id, "machine_id": machine_id, "factory_section_id": section.id,
          "created_by": created_by.id, "updated_by": None, "updated_at": None} for machine_id in machine_ids],
    ).scalars().all()
    return list(machine_ids), list(assignment_ids)


# "Statement recorder" (Conventions; `Author: claude` cards MSA-GS-22, INH-07): the SQL text
# of every statement the session's connection sends while the block runs.
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


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in machine_section_assignment.helpers.md)
# --------------------------------------------------------------------------- #

def test_msa_gm_06__the_row_s_own_workspace_id_decides_asked_in_the_row_s_workspace(db, w2, m1, s1, mk_assignment):
    """MSA-GM-06 — the row's own workspace_id decides: asked in the row's workspace returns it.
    Rules: `get_by_machine` R1"""
    a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert result.workspace_id == w2.id


def test_msa_up_01__a_machine_without_an_assignment_gets_one_new_row(db, w1, u2, m1, s1):
    """MSA-UP-01 — a machine without an assignment gets one new row.
    Rules: `upsert_for_machine` R1, Returns"""
    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineSectionAssignment)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert row.created_by == u2.id
    # Then 5
    assert row.created_at is not None
    # Then 6
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 7
    assert len(rows_of(db, m1)) == 1
    # Then 8
    assert count_rows(db, "machine_section_assignments") == 1


@pytest.mark.xfail(strict=True, reason="BUG-909: Re-saving a machine's current section deletes and re-creates its assignment")
def test_msa_up_03__re_saving_the_section_the_machine_already_has_leaves_its_row_untouched(db, w1, u1, u2, m1, s1, mk_assignment):
    """MSA-UP-03 — re-saving the section the machine already has leaves its row untouched.
    Rules: `upsert_for_machine` R3 [BUG-909]"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s1.id
    # Then 2
    assert len(rows_of(db, m1)) == 1
    # Then 3
    assert result.id == a1_id
    # Then 4
    row = rows_of(db, m1)[0]
    assert row.id == a1_id
    # Then 5
    assert row.created_by == u1.id


def test_msa_up_17__a_factory_section_id_that_is_no_section_fails_on_flush_and_the(db, w1, u1, u2, m1, s1, mk_assignment):
    """MSA-UP-17 — a factory_section_id that is no section fails on flush and the machine's previous row is back.
    Rules: `upsert_for_machine` R8, Errors row 3"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_factory_section_id_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row = reread(db, a1)
    assert row.factory_section_id == s1.id
    assert row.created_by == u1.id
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert written(db) == before


def test_msa_cl_01__every_row_of_the_section_is_deleted_and_its_machine_ids_are_returned(db, w1, f1, m1, m2, m3, s1, s2, mk_assignment):
    """MSA-CL-01 — every row of the section is deleted and its machine ids are returned.
    Rules: `clear_for_section` R1, R2, R3, Returns"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a3 = snap(db, a3)
    before_s1 = snap(db, s1)
    before_m1 = snap(db, m1)
    before_f1 = snap(db, f1)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(result) == [m1.id, m2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 0
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 6
    assert snap(db, a3) == before_a3
    # Then 7
    assert snap(db, s1) == before_s1
    # Then 8
    assert snap(db, m1) == before_m1
    # Then 9
    assert snap(db, f1) == before_f1


def test_msa_inh_04__update_with_a_dict_sets_the_given_columns_and_updated_at(db, u1, u2, m1, s1, s2, mk_assignment):
    """MSA-INH-04 — update with a dict sets the given columns and updated_at.
    Rules: inherited R2"""
    a1 = mk_assignment(of=m1, to=s1)

    result = dao.update(db, db_obj=a1, obj_in={"factory_section_id": s2.id, "updated_by": u2.id})

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.factory_section_id == s2.id
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None
    # Then 5
    assert row.created_by == u1.id
    assert row.machine_id == m1.id
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MSA-GM-01
def test_msa_gm_01__returns_the_assignment_row_of_the_machine_and_writes_nothing(db, w1, m1, m2, s1, s2, mk_assignment):
    """MSA-GM-01 — returns the assignment row of the machine and writes nothing.
    Rules: `get_by_machine` R1, R3"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s2)
    before_a1 = snap(db, a1)
    before = written(db)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineSectionAssignment)
    # Then 2
    assert result.id == a1.id
    # Then 3
    assert result.factory_section_id == s1.id
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSA-GM-07
def test_msa_gm_07__the_row_of_a_soft_deleted_machine_is_returned(db, w1, md, s1, mk_assignment):
    """MSA-GM-07 — the row of a soft-deleted machine is returned.
    Rules: `get_by_machine` R2 (P2)"""
    ad = mk_assignment(of=md, to=s1)

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert result.id == ad.id
    # Then 2
    assert result.factory_section_id == s1.id


# [local-coder] MSA-GS-01
def test_msa_gs_01__returns_a_list_of_the_rows_of_that_section_and_writes_nothing(db, w1, m1, m2, m3, s1, s2, mk_assignment):
    """MSA-GS-01 — returns a list of the rows of that section and writes nothing.
    Rules: `get_by_section` R1, R7, Returns"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    mk_assignment(of=m3, to=s2)
    before_a1 = snap(db, a1)
    before = written(db)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], MachineSectionAssignment)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a1) == before_a1


# [local-coder] MSA-GS-03
def test_msa_gs_03__the_other_workspace_gets_only_its_own_row_for_the_same_section_id(db, w2, s1, m1, m9, mk_assignment):
    """MSA-GS-03 — the other workspace gets only its own row for the same section id.
    Rules: `get_by_section` R1"""
    mk_assignment(of=m1, to=s1)
    a9 = mk_assignment(of=m9, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a9.id]
    # Then 2
    assert result[0].machine_id == m9.id


# [local-coder] MSA-GS-09
def test_msa_gs_09__rows_of_other_sections_and_other_workspaces_do_not_use_up_a_place_in(db, w1, m1, m2, m3, m9, s1, s2, mk_assignment):
    """MSA-GS-09 — rows of other sections and other workspaces do not use up a place in the page.
    Rules: `get_by_section` R4"""
    mk_assignment(of=m1, to=s2)
    mk_assignment(of=m9, to=s1)
    a3 = mk_assignment(of=m2, to=s1)
    a4 = mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [a3.id, a4.id]


# [local-coder] MSA-GS-13
def test_msa_gs_13__the_last_window_is_short(db, w1, m1, m2, m3, s1, mk_assignment):
    """MSA-GS-13 — the last window is short.
    Rules: `get_by_section` R4"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [a1.id, a2.id, a3.id]


# [local-coder] MSA-GS-19
def test_msa_gs_19__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, m1, s1, mk_assignment):
    """MSA-GS-19 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_section` R5, Errors row 2"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a1) == before_a1


# [local-coder] MSA-UP-02
def test_msa_up_02__moving_to_another_section_replaces_the_row_with_a_new_one(db, w1, u2, m1, s1, s2, mk_assignment):
    """MSA-UP-02 — moving to another section replaces the row with a new one.
    Rules: `upsert_for_machine` R2 (Q2)"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s2.id
    # Then 2
    assert result.id != a1_id
    # Then 3
    assert len(rows_of(db, m1)) == 1
    # Then 4
    row = rows_of(db, m1)[0]
    assert row.id == result.id
    assert row.factory_section_id == s2.id
    # Then 5
    assert row.created_by == u2.id
    # Then 6
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 7
    assert count_rows(db, "machine_section_assignments", id=a1_id) == 0


# [local-coder] MSA-UP-06
def test_msa_up_06__clearing_a_machine_without_an_assignment_writes_nothing_and_does_not(db, w1, m1, m2, s1, mk_assignment):
    """MSA-UP-06 — clearing a machine without an assignment writes nothing and does not use user_id.
    Rules: `upsert_for_machine` R4"""
    a2 = mk_assignment(of=m2, to=s1)
    before_a2 = snap(db, a2)
    before = written(db)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a2) == before_a2
    # Then 4
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSA-UP-08
def test_msa_up_08__a_move_touches_only_the_machine_s_own_row(db, w1, u2, m1, m2, m3, s1, s2, f1, mk_assignment):
    """MSA-UP-08 — a move touches only the machine's own row.
    Rules: `upsert_for_machine` R5"""
    mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a2 = snap(db, a2)
    before_a3 = snap(db, a3)
    before_m1 = snap(db, m1)
    before_s1 = snap(db, s1)
    before_s2 = snap(db, s2)
    before_f1 = snap(db, f1)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.machine_id == m1.id
    # Then 2
    assert snap(db, a2) == before_a2
    # Then 3
    assert snap(db, a3) == before_a3
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 3
    # Then 5
    assert snap(db, m1) == before_m1
    # Then 6
    assert snap(db, s1) == before_s1
    # Then 7
    assert snap(db, s2) == before_s2
    # Then 8
    assert snap(db, f1) == before_f1


# [local-coder] MSA-UP-15
def test_msa_up_15__a_machine_whose_row_has_another_workspace_id_hits_the_one_row_per(db, w1, w2, u2, m1, s1, s2, mk_assignment):
    """MSA-UP-15 — a machine whose row has another workspace_id hits the one-row-per-machine constraint and nothing changes.
    Rules: `upsert_for_machine` R7, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_machine_section_assignment_machine" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row = reread(db, a1)
    assert row.workspace_id == w2.id
    assert row.factory_section_id == s1.id
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert written(db) == before


# [local-coder] MSA-UP-21
def test_msa_up_21__a_machine_whose_section_was_already_read_still_reports_the_old(db, w1, u2, m1, s1, s2, mk_assignment):
    """MSA-UP-21 — a machine whose section was already read still reports the old section after a move.
    Rules: `upsert_for_machine` R10 (Q1)"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s2.id
    # Then 2
    assert m1.factory_section_id == s1.id
    # Then 3
    row = rows_of(db, m1)[0]
    assert row.factory_section_id == s2.id


# [local-coder] MSA-UP-25
def test_msa_up_25__user_id_none_is_stored_as_null(db, w1, m1, s1):
    """MSA-UP-25 — user_id None is stored as NULL.
    Rules: `upsert_for_machine` R1 (Inputs: `None` is stored as `NULL`)"""
    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_by is None
    # Then 3
    assert row.factory_section_id == s1.id


# [local-coder] MSA-CL-04
def test_msa_cl_04__the_row_of_a_soft_deleted_machine_is_deleted_and_listed_too(db, w1, m1, md, s1, mk_assignment):
    """MSA-CL-04 — the row of a soft-deleted machine is deleted and listed too.
    Rules: `clear_for_section` R3 (P2)"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=md, to=s1)
    before_md = snap(db, md)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == [m1.id, md.id]
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 3
    assert snap(db, md) == before_md
    # Then 4
    row = reread(db, md)
    assert row.is_deleted is True


# [local-coder] MSA-CL-09
def test_msa_cl_09__a_machine_whose_section_was_already_read_still_reports_the_removed(db, w1, m1, s1, mk_assignment):
    """MSA-CL-09 — a machine whose section was already read still reports the removed section.
    Rules: `clear_for_section` R6 (Q1)"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    assert m1.factory_section_id == s1.id
    # Then 3
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSA-INH-01
def test_msa_inh_01__create_with_a_machinesectionassignmentcreate_schema_fails_on_flush(db, m1, s1):
    """MSA-INH-01 — create with a MachineSectionAssignmentCreate schema fails on flush and saves nothing.
    Rules: inherited R1, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=MachineSectionAssignmentCreate(machine_id=m1.id, factory_section_id=s1.id))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MSA-INH-02
def test_msa_inh_02__create_with_a_dict_stores_a_row_with_the_model_defaults(db, w1, m1, s1):
    """MSA-INH-02 — create with a dict stores a row with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "factory_section_id": s1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 3
    assert row.created_at is not None
    # Then 4
    assert row.created_by is None
    assert row.updated_by is None
    # Then 5
    assert row.updated_at is None
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MSA-INH-08
def test_msa_inh_08__get_returns_a_row_of_another_workspace(db, w2, m9, s9, mk_assignment):
    """MSA-INH-08 — get returns a row of another workspace.
    Rules: inherited R3 ("`get` … has no workspace filter")"""
    a9 = mk_assignment(of=m9, to=s9)

    result = dao.get(db, a9.id)

    # Then 1
    assert result.id == a9.id
    # Then 2
    assert result.workspace_id == w2.id


# [local-coder] MSA-GM-02
def test_msa_gm_02__a_machine_without_an_assignment_gives_none(db, w1, m1, m2, s1, mk_assignment):
    """MSA-GM-02 — a machine without an assignment gives None.
    Rules: `get_by_machine` R1"""
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] MSA-GM-03
def test_msa_gm_03__an_unknown_machine_id_gives_none(db, w1, m1, s1, mk_assignment):
    """MSA-GM-03 — an unknown machine id gives None.
    Rules: `get_by_machine` R1"""
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] MSA-GM-04
def test_msa_gm_04__the_machine_s_row_is_not_returned_for_another_workspace_id(db, w2, m1, s1, mk_assignment):
    """MSA-GM-04 — the machine's row is not returned for another workspace id.
    Rules: `get_by_machine` R1"""
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [local-coder] MSA-GM-05
def test_msa_gm_05__the_row_s_own_workspace_id_decides_not_the_machine_s_asked_in_the(db, w1, w2, m1, s1, mk_assignment):
    """MSA-GM-05 — the row's own workspace_id decides, not the machine's: asked in the machine's workspace gives None.
    Rules: `get_by_machine` R1"""
    mk_assignment(of=m1, to=s1, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] MSA-GM-08
def test_msa_gm_08__a_row_pointing_at_a_soft_deleted_section_is_returned(db, w1, m1, sx, mk_assignment):
    """MSA-GM-08 — a row pointing at a soft-deleted section is returned.
    Rules: `get_by_machine` R2 (P2)"""
    a1 = mk_assignment(of=m1, to=sx)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert result.factory_section_id == sx.id


# [local-coder] MSA-GM-09
def test_msa_gm_09__a_row_pointing_at_a_section_of_another_factory_is_returned(db, w1, m1, s3, mk_assignment):
    """MSA-GM-09 — a row pointing at a section of another factory is returned.
    Rules: `get_by_machine` R2 (P2)"""
    a1 = mk_assignment(of=m1, to=s3)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert result.factory_section_id == s3.id


# [local-coder] MSA-GM-10
def test_msa_gm_10__a_row_pointing_at_a_section_of_another_workspace_is_returned(db, w1, s9, m1, mk_assignment):
    """MSA-GM-10 — a row pointing at a section of another workspace is returned.
    Rules: `get_by_machine` R2 (P2)"""
    a1 = mk_assignment(of=m1, to=s9)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert result.factory_section_id == s9.id
    # Then 3
    assert result.workspace_id == w1.id


# [local-coder] MSA-GS-02
def test_msa_gs_02__a_row_of_another_workspace_pointing_at_the_same_section_is_not(db, w1, s1, m1, m9, mk_assignment):
    """MSA-GS-02 — a row of another workspace pointing at the same section is not returned.
    Rules: `get_by_section` R1"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m9, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [local-coder] MSA-GS-04
def test_msa_gs_04__the_row_of_a_soft_deleted_machine_is_returned_and_left_as_it_was(db, w1, m1, md, s1, mk_assignment):
    """MSA-GS-04 — the row of a soft-deleted machine is returned and left as it was.
    Rules: `get_by_section` R2 (P2), R7"""
    a1 = mk_assignment(of=m1, to=s1)
    ad = mk_assignment(of=md, to=s1)
    before_ad = snap(db, ad)
    before_md = snap(db, md)
    before = written(db)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a1.id, ad.id]
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, ad) == before_ad
    # Then 4
    assert snap(db, md) == before_md


# [local-coder] MSA-GS-05
def test_msa_gs_05__the_rows_of_a_soft_deleted_section_are_returned(db, w1, m1, m2, sx, mk_assignment):
    """MSA-GS-05 — the rows of a soft-deleted section are returned.
    Rules: `get_by_section` R2 (P2)"""
    a1 = mk_assignment(of=m1, to=sx)
    a2 = mk_assignment(of=m2, to=sx)
    before_sx = snap(db, sx)

    result = dao.get_by_section(db, factory_section_id=sx.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 2
    assert snap(db, sx) == before_sx


# [local-coder] MSA-GS-06
def test_msa_gs_06__an_unknown_section_id_returns_an_empty_list(db, w1, m1, s1, mk_assignment):
    """MSA-GS-06 — an unknown section id returns an empty list.
    Rules: `get_by_section` R3"""
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MSA-GS-07
def test_msa_gs_07__a_section_with_no_rows_returns_an_empty_list(db, w1, m1, s1, s2, mk_assignment):
    """MSA-GS-07 — a section with no rows returns an empty list.
    Rules: `get_by_section` R3"""
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MSA-GS-08
def test_msa_gs_08__a_section_whose_rows_are_all_in_another_workspace_returns_an_empty(db, w1, s9, m9, mk_assignment):
    """MSA-GS-08 — a section whose rows are all in another workspace returns an empty list.
    Rules: `get_by_section` R3, R1"""
    mk_assignment(of=m9, to=s9)

    result = dao.get_by_section(db, factory_section_id=s9.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MSA-GS-10
def test_msa_gs_10__default_limit_returns_exactly_500_of_501_rows(db, w1, u1, f1, s1):
    """MSA-GS-10 — default limit returns exactly 500 of 501 rows.
    Rules: `get_by_section` R4"""
    _, assignment_ids = bulk_assigned_machines(
        db, names=[f"Unit {k:03d}" for k in range(1, 502)], factory=f1, section=s1, created_by=u1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 500
    # Then 2
    assert len(set(ids(result))) == 500
    # Then 3
    assert set(ids(result)) <= set(assignment_ids)


# [claude] MSA-GS-11
def test_msa_gs_11__an_explicit_limit_of_501_returns_all_501_rows(db, w1, u1, f1, s1):
    """MSA-GS-11 — an explicit limit of 501 returns all 501 rows.
    Rules: `get_by_section` R4"""
    _, assignment_ids = bulk_assigned_machines(
        db, names=[f"Unit {k:03d}" for k in range(1, 502)], factory=f1, section=s1, created_by=u1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=501)

    # Then 1
    assert len(result) == 501
    # Then 2
    assert sorted(ids(result)) == sorted(assignment_ids)


# [local-coder] MSA-GS-12
def test_msa_gs_12__limit_2_of_three_rows_returns_two_different_rows_of_the_section(db, w1, m1, m2, m3, s1, mk_assignment):
    """MSA-GS-12 — limit 2 of three rows returns two different rows of the section.
    Rules: `get_by_section` R4"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {a1.id, a2.id, a3.id}


# [local-coder] MSA-GS-14
def test_msa_gs_14__limit_0_returns_an_empty_list(db, w1, m1, s1, mk_assignment):
    """MSA-GS-14 — limit 0 returns an empty list.
    Rules: `get_by_section` R5"""
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] MSA-GS-15
def test_msa_gs_15__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, m1, m2, s1, mk_assignment):
    """MSA-GS-15 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_section` R5"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] MSA-GS-16
def test_msa_gs_16__skip_one_below_the_number_of_rows_returns_one_row(db, w1, m1, m2, s1, mk_assignment):
    """MSA-GS-16 — skip one below the number of rows returns one row.
    Rules: `get_by_section` R5, R4"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [a1.id, a2.id]


# [local-coder] MSA-GS-17
def test_msa_gs_17__skip_past_the_number_of_rows_returns_an_empty_list(db, w1, m1, m2, s1, mk_assignment):
    """MSA-GS-17 — skip past the number of rows returns an empty list.
    Rules: `get_by_section` R5"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] MSA-GS-18
def test_msa_gs_18__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, m1, s1, mk_assignment):
    """MSA-GS-18 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_section` R5, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a1) == before_a1


# [claude] MSA-GS-20
@pytest.mark.xfail(
    strict=False,
    reason="BUG-906: Assignment rows of a section have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_msa_gs_20__rows_come_back_by_id_ascending(db, w1, u2, m1, m2, m3, s1, mk_assignment):
    """MSA-GS-20 — rows come back by id ascending.
    Rules: `get_by_section` R6 [BUG-906]"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s1)
    a1.created_by = u2.id
    db.flush()

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id, a3.id]
    # Then 2
    assert ids(result) == [a1.id, a2.id, a3.id]


# [claude] MSA-GS-21
@pytest.mark.xfail(
    strict=False,
    reason="BUG-906: Assignment rows of a section have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_msa_gs_21__a_middle_window_holds_the_second_and_third_row_by_id(db, w1, u2, m1, m2, m3, s1, mk_assignment):
    """MSA-GS-21 — a middle window holds the second and third row by id.
    Rules: `get_by_section` R6 [BUG-906], R4"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s1)
    a1.created_by = u2.id
    db.flush()

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [a2.id, a3.id]


# [claude] MSA-GS-22
@pytest.mark.xfail(strict=True, reason="BUG-906: Assignment rows of a section have no sort order")
def test_msa_gs_22__the_by_section_query_asks_the_database_for_an_order(db, w1, m1, s1, mk_assignment):
    """MSA-GS-22 — the by-section query asks the database for an order.
    Rules: `get_by_section` R6 [BUG-906]; `clear_for_section` R7 [BUG-906] (same query)"""
    a1 = mk_assignment(of=m1, to=s1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    selects = recorder.selects()
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()


# [local-coder] MSA-UP-04
def test_msa_up_04__re_saving_the_same_section_keeps_exactly_one_row_of_that_machine_for(db, w1, u2, m1, s1, mk_assignment):
    """MSA-UP-04 — re-saving the same section keeps exactly one row of that machine for that section.
    Rules: `upsert_for_machine` R3 (the part that holds today and after the BUG-909 fix)"""
    mk_assignment(of=m1, to=s1)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s1.id
    # Then 2
    assert result.machine_id == m1.id
    # Then 3
    assert len(rows_of(db, m1)) == 1
    # Then 4
    row = rows_of(db, m1)[0]
    assert row.factory_section_id == s1.id
    assert row.workspace_id == w1.id
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MSA-UP-05
def test_msa_up_05__clearing_a_machine_s_section_deletes_its_row_and_returns_none(db, w1, u2, m1, s1, mk_assignment):
    """MSA-UP-05 — clearing a machine's section deletes its row and returns None.
    Rules: `upsert_for_machine` R4 (Q2)"""
    mk_assignment(of=m1, to=s1)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MSA-UP-07
def test_msa_up_07__clearing_with_a_user_id_that_is_no_profile_still_deletes_the_row(db, w1, m1, s1, mk_assignment):
    """MSA-UP-07 — clearing with a user_id that is no profile still deletes the row.
    Rules: `upsert_for_machine` R4"""
    mk_assignment(of=m1, to=s1)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSA-UP-09
def test_msa_up_09__clearing_touches_only_the_machine_s_own_row(db, w1, u2, m1, m2, s1, mk_assignment):
    """MSA-UP-09 — clearing touches only the machine's own row.
    Rules: `upsert_for_machine` R5, R4"""
    mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    before_a2 = snap(db, a2)
    before_m1 = snap(db, m1)
    before_s1 = snap(db, s1)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, a2) == before_a2
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 4
    assert snap(db, m1) == before_m1
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] MSA-UP-10
def test_msa_up_10__a_section_of_another_factory_is_accepted(db, w1, u2, m1, s3):
    """MSA-UP-10 — a section of another factory is accepted.
    Rules: `upsert_for_machine` R6"""
    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s3.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s3.id
    # Then 3
    assert len(rows_of(db, m1)) == 1


# [local-coder] MSA-UP-11
def test_msa_up_11__a_soft_deleted_section_is_accepted(db, w1, u2, m1, sx):
    """MSA-UP-11 — a soft-deleted section is accepted.
    Rules: `upsert_for_machine` R6"""
    before_sx = snap(db, sx)

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=sx.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_section_id == sx.id
    # Then 3
    assert snap(db, sx) == before_sx


# [local-coder] MSA-UP-12
def test_msa_up_12__a_section_of_another_workspace_is_accepted_and_the_row_gets_the_given(db, w1, u2, m1, s9):
    """MSA-UP-12 — a section of another workspace is accepted and the row gets the given workspace.
    Rules: `upsert_for_machine` R6"""
    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_section_id == s9.id
    # Then 3
    assert row.workspace_id == w1.id


# [local-coder] MSA-UP-13
def test_msa_up_13__a_soft_deleted_machine_is_accepted(db, w1, u2, md, s1):
    """MSA-UP-13 — a soft-deleted machine is accepted.
    Rules: `upsert_for_machine` R6"""
    before_md = snap(db, md)

    result = dao.upsert_for_machine(db, machine_id=md.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == md.id
    assert row.factory_section_id == s1.id
    # Then 3
    assert snap(db, md) == before_md


# [local-coder] MSA-UP-14
def test_msa_up_14__a_machine_of_another_workspace_is_accepted_and_stored_with_the_given(db, w1, u2, m9, s1):
    """MSA-UP-14 — a machine of another workspace is accepted and stored with the given workspace.
    Rules: `upsert_for_machine` R6"""
    result = dao.upsert_for_machine(db, machine_id=m9.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == m9.id
    assert row.factory_section_id == s1.id
    # Then 3
    assert row.workspace_id == w1.id


# [local-coder] MSA-UP-16
def test_msa_up_16__a_machine_id_that_is_no_machine_fails_on_flush_and_nothing_changes(db, w1, u2, m2, s1, mk_assignment):
    """MSA-UP-16 — a machine_id that is no machine fails on flush and nothing changes.
    Rules: `upsert_for_machine` R8, Errors row 2"""
    a2 = mk_assignment(of=m2, to=s1)
    before_a2 = snap(db, a2)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=MISSING, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a2) == before_a2


# [local-coder] MSA-UP-18
def test_msa_up_18__a_user_id_that_is_no_profile_fails_on_flush_and_the_machine_s(db, w1, u1, m1, s1, s2, mk_assignment):
    """MSA-UP-18 — a user_id that is no profile fails on flush and the machine's previous row is back.
    Rules: `upsert_for_machine` R8, Errors row 4"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row = reread(db, a1)
    assert row.factory_section_id == s1.id
    assert row.created_by == u1.id
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert written(db) == before


# [claude] MSA-UP-19 (handed back by the local model)
def test_msa_up_19__a_workspace_id_that_is_no_workspace_fails_on_flush_and_nothing_changes(db, u2, m1, m2, s1, mk_assignment):
    """MSA-UP-19 — a workspace_id that is no workspace fails on flush and nothing changes.
    Rules: `upsert_for_machine` R8, Errors row 5"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=m2.id, factory_section_id=s1.id, workspace_id=MISSING, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert len(rows_of(db, m2)) == 0
    # Then 5
    assert snap(db, a1) == before_a1
    # Then 6
    assert written(db) == before


# [claude] MSA-UP-20
def test_msa_up_20__the_move_is_flushed_but_not_committed_visible_to_get_by_machine_undone_by_a_rollback(db, w1, u1, u2, m1, s1, s2, mk_assignment):
    """MSA-UP-20 — the move is flushed but not committed: visible to get_by_machine in the session, undone by a rollback.
    Rules: `upsert_for_machine` R9"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert result.factory_section_id == s2.id
        # Then 2
        assert dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id).id == result.id
        sp.rollback()
        # Then 3
        assert len(rows_of(db, m1)) == 1
        # Then 4
        row = rows_of(db, m1)[0]
        assert row.id == a1_id
        assert row.factory_section_id == s1.id
        # Then 5
        assert row.created_by == u1.id
        # Then 6
        assert commit_spy.call_count == 0


# [claude] MSA-UP-22
def test_msa_up_22__once_the_machine_is_expired_it_reports_the_new_section(db, w1, u2, m1, s1, s2, mk_assignment):
    """MSA-UP-22 — once the machine is expired it reports the new section.
    Rules: `upsert_for_machine` R10 (Q1)"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s2.id
    # Then 2
    db.expire(m1)
    assert m1.factory_section_id == s2.id


# [local-coder] MSA-UP-23
def test_msa_up_23__a_machine_whose_section_was_already_read_still_reports_it_after(db, w1, u2, m1, s1, mk_assignment):
    """MSA-UP-23 — a machine whose section was already read still reports it after clearing.
    Rules: `upsert_for_machine` R10 (Q1), R4"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert m1.factory_section_id == s1.id
    # Then 3
    assert len(rows_of(db, m1)) == 0


# [claude] MSA-UP-24
def test_msa_up_24__a_later_flush_of_the_loaded_machine_does_not_bring_the_deleted_row_back(db, w1, u2, m1, s1, mk_assignment):
    """MSA-UP-24 — a later flush of the loaded machine does not bring the deleted row back.
    Rules: `upsert_for_machine` R10 (Q1)"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    m1.name = "Renamed Unit"
    db.flush()
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MSA-CL-02
def test_msa_cl_02__a_row_of_another_workspace_pointing_at_the_same_section_is_not_touched(db, w1, m1, m9, s1, mk_assignment):
    """MSA-CL-02 — a row of another workspace pointing at the same section is not touched.
    Rules: `clear_for_section` R2"""
    mk_assignment(of=m1, to=s1)
    a9 = mk_assignment(of=m9, to=s1)
    before_a9 = snap(db, a9)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    assert snap(db, a9) == before_a9
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MSA-CL-03
def test_msa_cl_03__the_other_workspace_s_call_removes_only_its_own_row(db, w2, m1, m9, s1, mk_assignment):
    """MSA-CL-03 — the other workspace's call removes only its own row.
    Rules: `clear_for_section` R2, R1"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m9, to=s1)
    before_a1 = snap(db, a1)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w2.id)

    # Then 1
    assert result == [m9.id]
    # Then 2
    assert snap(db, a1) == before_a1
    # Then 3
    assert len(rows_of(db, m9)) == 0


# [local-coder] MSA-CL-05
def test_msa_cl_05__the_rows_of_a_soft_deleted_section_are_deleted_and_the_section_is_not(db, w1, m1, sx, mk_assignment):
    """MSA-CL-05 — the rows of a soft-deleted section are deleted and the section is not touched.
    Rules: `clear_for_section` R3 (P2)"""
    mk_assignment(of=m1, to=sx)
    before_sx = snap(db, sx)

    result = dao.clear_for_section(db, factory_section_id=sx.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert snap(db, sx) == before_sx
    # Then 4
    row = reread(db, sx)
    assert row.is_deleted is True


# [claude] MSA-CL-06
@pytest.mark.xfail(strict=True, reason='BUG-907: "Unassign every machine of a section" stops at 10 000')
def test_msa_cl_06__all_10_001_rows_of_a_section_are_deleted_and_listed(db, w1, u1, f1, s1):
    """MSA-CL-06 — all 10 001 rows of a section are deleted and listed.
    Rules: `clear_for_section` R4 [BUG-907] (P1)"""
    machine_ids, _ = bulk_assigned_machines(
        db, names=[f"Bulk {k:05d}" for k in range(1, 10002)], factory=f1, section=s1, created_by=u1)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert len(set(result)) == len(result)
    # Then 2
    assert set(result) <= set(machine_ids)
    # Then 3
    assert len(result) == 10001
    # Then 4
    assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 0


# [local-coder] MSA-CL-07
def test_msa_cl_07__an_unknown_section_id_returns_an_empty_list_and_writes_nothing(db, w1, m1, s1, mk_assignment):
    """MSA-CL-07 — an unknown section id returns an empty list and writes nothing.
    Rules: `clear_for_section` R5"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    result = dao.clear_for_section(db, factory_section_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] MSA-CL-08
def test_msa_cl_08__a_section_with_no_rows_returns_an_empty_list_and_writes_nothing(db, w1, m1, s1, s2, mk_assignment):
    """MSA-CL-08 — a section with no rows returns an empty list and writes nothing.
    Rules: `clear_for_section` R5"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    result = dao.clear_for_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1


# [claude] MSA-CL-10
def test_msa_cl_10__once_the_machine_is_expired_it_reports_no_section(db, w1, m1, s1, mk_assignment):
    """MSA-CL-10 — once the machine is expired it reports no section.
    Rules: `clear_for_section` R6 (Q1)"""
    mk_assignment(of=m1, to=s1)
    _loaded = m1.factory_section_id

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    db.expire(m1)
    assert m1.factory_section_id is None


# [claude] MSA-CL-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-906: Assignment rows of a section have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_msa_cl_11__the_machine_ids_come_back_in_the_order_of_the_row_ids(db, w1, u2, m1, m2, m3, s1, mk_assignment):
    """MSA-CL-11 — the machine ids come back in the order of the row ids.
    Rules: `clear_for_section` R7 [BUG-906]"""
    a1 = mk_assignment(of=m3, to=s1)
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a1.created_by = u2.id
    db.flush()

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == [m1.id, m2.id, m3.id]
    # Then 2
    assert result == [m3.id, m1.id, m2.id]


# [claude] MSA-CL-12
def test_msa_cl_12__the_removal_is_flushed_but_not_committed_get_by_section_sees_no_row_a_rollback_brings_every_row_back(db, w1, u1, m1, m2, s1, mk_assignment):
    """MSA-CL-12 — the removal is flushed but not committed: get_by_section sees no row in the session, a rollback brings every row back.
    Rules: `clear_for_section` R8"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

        # Then 1
        assert sorted(result) == [m1.id, m2.id]
        # Then 2
        assert dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id) == []
        sp.rollback()
        # Then 3
        assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 2
        # Then 4
        row = reread(db, a1)
        assert row.machine_id == m1.id
        assert row.created_by == u1.id
        # Then 5
        assert commit_spy.call_count == 0


# [local-coder] MSA-INH-03
def test_msa_inh_03__create_of_a_second_row_for_the_same_machine_fails_on_flush_and_the(db, w1, m1, s1, s2, mk_assignment):
    """MSA-INH-03 — create of a second row for the same machine fails on flush and the first row stays.
    Rules: inherited R1, Errors row 2"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "factory_section_id": s2.id})

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_machine_section_assignment_machine" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    assert len(rows_of(db, m1)) == 1
    # Then 6
    assert written(db) == before


# [local-coder] MSA-INH-05
def test_msa_inh_05__get_by_workspace_returns_the_rows_of_that_workspace_only(db, w1, m1, m2, m9, s1, s2, s9, mk_assignment):
    """MSA-INH-05 — get_by_workspace returns the rows of that workspace only.
    Rules: inherited R3 (the part that holds today)"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s2)
    mk_assignment(of=m9, to=s9)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 2
    assert len(result) == 2


# [claude] MSA-INH-06
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_msa_inh_06__get_by_workspace_returns_the_rows_in_id_order(db, w1, u2, m1, m2, s1, s2, mk_assignment):
    """MSA-INH-06 — get_by_workspace returns the rows in id order.
    Rules: inherited R3 [BUG-100]"""
    a1 = mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s2)
    a1.created_by = u2.id
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 2
    assert ids(result) == [a1.id, a2.id]


# [claude] MSA-INH-07
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_msa_inh_07__the_workspace_list_query_on_assignments_asks_the_database_for_an_order(db, w1, m1, s1, mk_assignment):
    """MSA-INH-07 — the workspace list query on assignments asks the database for an order.
    Rules: inherited R3 [BUG-100]"""
    a1 = mk_assignment(of=m1, to=s1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    selects = recorder.selects()
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()
