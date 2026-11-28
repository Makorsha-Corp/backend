"""Unit tests for app/managers/machine_section_assignment_manager.py.

Implements tests/unit/managers/machine_section_assignment_manager.cases.md, one
test per case. Real Postgres session (`db` fixture). Nothing is patched
(Conventions, Externals: None).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/managers/machine_section_assignment_manager.helpers.md as its only
view of this file; tests below a `# [claude] <ID>` comment are the
`Author: claude` cards and the cards the local model handed back, written by
hand at finishing.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
# ruff: noqa: F841  (Given code lines such as `loaded = M1.factory_section_id` run as written; they load the section)
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy import func, insert, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.managers.machine_section_assignment_manager import (
    machine_section_assignment_manager,
)
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "mgr = the singleton machine_section_assignment_manager" (a module-level name, not a fixture)
mgr = machine_section_assignment_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (W1, W2, U1, U2 and the eighteen standing rows)
# Each fixture depends on the one before it, so the ids rise in the order the
# Conventions list them: F1 F2 F9 FD, S1 S2 S3 SX S9 SF, M1 M2 M3 MD M9 MF.
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


# Convention "F1 / F2 / F9 / FD = factories rows"
def _factory(db, name, abbreviation, workspace_id, is_deleted=False):
    return _add(db, Factory(name=name, abbreviation=abbreviation, workspace_id=workspace_id,
                            is_deleted=is_deleted))


@pytest.fixture
def f1(db, w1, u2):
    return _factory(db, "Main Plant", "MP", w1.id)


@pytest.fixture
def f2(db, w1, f1):
    return _factory(db, "North Yard", "NY", w1.id)


@pytest.fixture
def f9(db, w2, f2):
    return _factory(db, "Far Depot", "FR", w2.id)


@pytest.fixture
def fd(db, w1, f9):
    return _factory(db, "Closed Mill", "CM", w1.id, is_deleted=True)


# Convention "S1 / S2 / S3 / SX / S9 / SF = factory_sections rows"
def _section(db, name, factory, is_deleted=False):
    return _add(db, FactorySection(name=name, factory_id=factory.id, workspace_id=factory.workspace_id,
                                   is_active=True, is_deleted=is_deleted))


@pytest.fixture
def s1(db, f1, fd):
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


@pytest.fixture
def sf(db, fd, s9):
    return _section(db, "Boiler Room", fd)


# Convention "M1 / M2 / M3 / MD / M9 / MF = machines rows"
def _machine(db, name, factory, is_deleted=False):
    return _add(db, Machine(name=name, factory_id=factory.id, workspace_id=factory.workspace_id,
                            is_active=True, is_deleted=is_deleted, is_running=False))


@pytest.fixture
def m1(db, f1, sf):
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


@pytest.fixture
def mf(db, fd, m9):
    return _machine(db, "Kiln", fd)


# Convention "These eighteen rows exist in every test ... and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, f1, f2, f9, fd, s1, s2, s3, sx, s9, sf, m1, m2, m3, md, m9, mf):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
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


# Convention "extra factory": workspace_id W1.id, is_active True, is_deleted False
@pytest.fixture
def mk_factory(db, w1):
    """mk_factory(name=..., abbreviation=..., **columns) -> Factory. Keywords only."""
    def _mk(*, name, abbreviation, **columns):
        fields = {"workspace_id": w1.id, "name": name, "abbreviation": abbreviation,
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, Factory(**fields))
    return _mk


# Convention "section of F": workspace_id = F's, factory_id F.id, is_active True, is_deleted False
@pytest.fixture
def mk_section(db):
    """mk_section(of=<factory>, name=..., **columns) -> FactorySection. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name,
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, FactorySection(**fields))
    return _mk


# Convention "machine of F": workspace_id = F's, factory_id F.id, is_active True,
# is_deleted False, is_running False
@pytest.fixture
def mk_machine(db):
    """mk_machine(of=<factory>, name=...) -> Machine. Keywords only."""
    def _mk(*, of, name):
        return _add(db, Machine(workspace_id=of.workspace_id, factory_id=of.id, name=name,
                                is_active=True, is_deleted=False, is_running=False))
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


# Bulk Given rows of the `Author: claude` card MSM-CLR-09 (10 001): "machine Nk is M1 but
# `name`" and "assignment of Nk to S1", each set in one multi-row INSERT (ids rise in list
# order). Copied from tests/unit/dao/test_machine_section_assignment.py. Setup only; not in
# the helper sheet.
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


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in machine_section_assignment_manager.helpers.md)
# --------------------------------------------------------------------------- #

def test_msm_set_01__a_machine_without_a_section_is_put_into_a_live_section_of_its_factory(db, w1, u2, f1, m1, s1):
    """MSM-SET-01 — a machine without a section is put into a live section of its factory.
    Rules: `set_assignment` R1, Returns"""
    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineSectionAssignment)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    assert row.workspace_id == w1.id
    # Then 4
    assert row.created_by == u2.id
    # Then 5
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert count_rows(db, "machine_section_assignments") == 1


def test_msm_set_08__re_saving_the_section_the_machine_already_has_leaves_its_link(db, w1, u1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-08 — re-saving the section the machine already has leaves its link untouched.
    Rules: `set_assignment` R4 [BUG-909]"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

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


def test_msm_set_13__a_section_of_another_workspace_is_answered_with_the_same_404(db, w1, u2, f9, m1, s1, s9, mk_assignment):
    """MSM-SET-13 — a section of another workspace is answered with the same 404.
    Rules: `set_assignment` R6, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f9.id, factory_section_id=s9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1
    # Then 6
    assert snap(db, s9) == before_s9


def test_msm_set_15__a_soft_deleted_section_is_refused_with_400_and_the_machine_keeps_its(db, w1, u2, f1, m1, s1, sx, mk_assignment):
    """MSM-SET-15 — a soft-deleted section is refused with 400 and the machine keeps its link.
    Rules: `set_assignment` R7, Errors row 2"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)
    before_sx = snap(db, sx)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=sx.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1
    # Then 6
    assert snap(db, sx) == before_sx


def test_msm_set_29__a_machine_whose_link_has_another_workspace_id_hits_the_one_link_per(db, w1, w2, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-29 — a machine whose link has another workspace_id hits the one-link-per-machine constraint and nothing changes.
    Rules: `set_assignment` R11, Errors row 7"""
    a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

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


def test_msm_clr_01__every_link_of_the_section_is_deleted_and_its_machine_ids_are_returned(db, w1, f1, m1, m2, m3, s1, s2, mk_assignment):
    """MSM-CLR-01 — every link of the section is deleted and its machine ids are returned; section, machines and factory are not written.
    Rules: `clear_for_section` R1, R4, Returns"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a3 = snap(db, a3)
    before_s1 = snap(db, s1)
    before_m1 = snap(db, m1)
    before_m2 = snap(db, m2)
    before_f1 = snap(db, f1)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

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
    assert snap(db, m2) == before_m2
    # Then 10
    assert snap(db, f1) == before_f1


# [local-coder] MSM-SET-02
def test_msm_set_02__moving_a_machine_to_another_section_of_its_factory_replaces_its_link(db, w1, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-02 — moving a machine to another section of its factory replaces its link with a new one.
    Rules: `set_assignment` R2"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

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
    assert count_rows(db, "machine_section_assignments", id=a1_id) == 0


# [local-coder] MSM-SET-04
def test_msm_set_04__clearing_validates_nothing_an_unknown_factory_id_and_an_unknown_user(db, w1, m1, s1, mk_assignment):
    """MSM-SET-04 — clearing validates nothing: an unknown factory_id and an unknown user_id still delete the link.
    Rules: `set_assignment` R3 (Inputs: `factory_id` ignored and `user_id` unused when clearing)"""
    mk_assignment(of=m1, to=s1)
    before_s1 = snap(db, s1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=MISSING, factory_section_id=None, workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert snap(db, s1) == before_s1


# [local-coder] MSM-SET-05
def test_msm_set_05__clearing_a_machine_without_a_link_returns_none_and_writes_nothing(db, w1, u2, f1, m1, m2, s1, mk_assignment):
    """MSM-SET-05 — clearing a machine without a link returns None and writes nothing.
    Rules: `set_assignment` R3"""
    a2 = mk_assignment(of=m2, to=s1)
    before = written(db)
    before_a2 = snap(db, a2)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a2) == before_a2
    # Then 4
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSM-SET-07
def test_msm_set_07__clearing_with_an_unknown_workspace_id_leaves_the_machine_s_link_of_w1(db, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-07 — clearing with an unknown workspace_id leaves the machine's link of W1 in place.
    Rules: `set_assignment` R3 (assignment DAO `upsert_for_machine` R7: the link is looked for only in the given workspace)"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=None, workspace_id=MISSING, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    assert len(rows_of(db, m1)) == 1


# [local-coder] MSM-SET-11
def test_msm_set_11__section_id_0_is_looked_up_not_taken_as_clear_and_answered_with_404(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-11 — section id 0 is looked up, not taken as "clear", and answered with 404.
    Rules: `set_assignment` R5, Errors row 1 (boundary: `0` is validated, only `None` clears)"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=0, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 0 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-19
@pytest.mark.xfail(strict=True, reason="BUG-910: A machine can be assigned to a section of a soft-deleted factory")
def test_msm_set_19__a_live_section_of_a_soft_deleted_factory_is_refused_like_a_deleted(db, w1, u2, fd, mf, sf, mk_assignment, mk_section):
    """MSM-SET-19 — a live section of a soft-deleted factory is refused like a deleted section.
    Rules: `set_assignment` R9 [BUG-910] (P1), Errors row 4"""
    sg = mk_section(of=fd, name="Dry Store")
    af = mk_assignment(of=mf, to=sg)
    before_af = snap(db, af)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=mf.id, factory_id=fd.id, factory_section_id=sf.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, af) == before_af
    # Then 6
    assert len(rows_of(db, mf)) == 1


# [local-coder] MSM-SET-21
def test_msm_set_21__a_section_of_a_live_but_inactive_factory_is_accepted(db, w1, u2, mk_factory, mk_section, mk_machine):
    """MSM-SET-21 — a section of a live but inactive factory is accepted.
    Rules: `set_assignment` R9 (an inactive-but-live factory is not refused)"""
    fq = mk_factory(name="Quiet Works", abbreviation="QW", is_active=False)
    sq = mk_section(of=fq, name="Night Shift")
    mq = mk_machine(of=fq, name="Planer")

    result = mgr.set_assignment(db, machine_id=mq.id, factory_id=fq.id, factory_section_id=sq.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == mq.id
    assert row.factory_section_id == sq.id
    # Then 3
    assert len(rows_of(db, mq)) == 1


# [local-coder] MSM-SET-23
def test_msm_set_23__an_inactive_section_of_a_live_factory_is_accepted_like_an_active_one(db, w1, u2, f1, m1, mk_section):
    """MSM-SET-23 — an inactive section of a live factory is accepted like an active one.
    Rules: `set_assignment` R9a"""
    si = mk_section(of=f1, name="Spare Bay", is_active=False)
    before_si = snap(db, si)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=si.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.factory_section_id == si.id
    # Then 3
    assert snap(db, si) == before_si


# [local-coder] MSM-SET-27
def test_msm_set_27__a_machine_id_that_is_no_machine_fails_on_flush_and_nothing_changes(db, w1, u2, f1, m2, s1, mk_assignment):
    """MSM-SET-27 — a machine_id that is no machine fails on flush and nothing changes.
    Rules: `set_assignment` R11 (Q1), Errors row 5"""
    a2 = mk_assignment(of=m2, to=s1)
    before_a2 = snap(db, a2)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            mgr.set_assignment(db, machine_id=MISSING, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a2) == before_a2


# [local-coder] MSM-SET-30
def test_msm_set_30__user_id_none_is_stored_as_null(db, w1, f1, m1, s1):
    """MSM-SET-30 — user_id None is stored as NULL.
    Rules: `set_assignment` R1 (Inputs: `None` is stored as `NULL`)"""
    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_by is None
    # Then 3
    assert row.factory_section_id == s1.id


# [local-coder] MSM-SET-31
def test_msm_set_31__a_machine_whose_section_was_already_read_still_reports_the_old(db, w1, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-31 — a machine whose section was already read still reports the old section after a move.
    Rules: `set_assignment` R12 (P2)"""
    mk_assignment(of=m1, to=s1)
    loaded = m1.factory_section_id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s2.id
    # Then 2
    assert m1.factory_section_id == s1.id
    # Then 3
    row = rows_of(db, m1)[0]
    assert row.factory_section_id == s2.id


# [local-coder] MSM-SET-36
def test_msm_set_36__a_move_touches_only_the_machine_s_own_link(db, w1, u2, f1, m1, m2, m3, s1, s2, mk_assignment):
    """MSM-SET-36 — a move touches only the machine's own link.
    Rules: `set_assignment` R13, Side effects"""
    mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a2 = snap(db, a2)
    before_a3 = snap(db, a3)
    before_m1 = snap(db, m1)
    before_s1 = snap(db, s1)
    before_s2 = snap(db, s2)
    before_f1 = snap(db, f1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

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


# [local-coder] MSM-CLR-04
def test_msm_clr_04__a_link_of_another_workspace_pointing_at_the_same_section_is_not(db, w1, m1, m9, s1, mk_assignment):
    """MSM-CLR-04 — a link of another workspace pointing at the same section is not touched.
    Rules: `clear_for_section` R1"""
    mk_assignment(of=m1, to=s1)
    a9 = mk_assignment(of=m9, to=s1)
    before_a9 = snap(db, a9)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    assert snap(db, a9) == before_a9
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MSM-CLR-10
def test_msm_clr_10__machines_whose_section_was_already_read_report_no_section_right_after(db, w1, m1, m2, m3, s1, s2, mk_assignment):
    """MSM-CLR-10 — machines whose section was already read report no section right after the call; others keep theirs.
    Rules: `clear_for_section` R5"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    mk_assignment(of=m3, to=s2)
    loaded1 = m1.factory_section_id
    loaded2 = m2.factory_section_id
    loaded3 = m3.factory_section_id

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == [m1.id, m2.id]
    # Then 2
    assert m1.factory_section_id is None
    # Then 3
    assert m2.factory_section_id is None
    # Then 4
    assert m3.factory_section_id == s2.id


# [local-coder] MSM-CLR-11
def test_msm_clr_11__a_name_changed_in_memory_before_the_call_keeps_its_new_value(db, w1, f1, s1, mk_machine, mk_assignment):
    """MSM-CLR-11 — a name changed in memory before the call keeps its new value.
    Rules: `clear_for_section` R5"""
    mn = mk_machine(of=f1, name="Belt Sander")
    mk_assignment(of=mn, to=s1)
    loaded = mn.factory_section_id
    mn.name = "Edge Trimmer"

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == [mn.id]
    # Then 2
    assert mn.name == "Edge Trimmer"
    # Then 3
    assert mn.factory_section_id is None


# [local-coder] MSM-CLR-12
def test_msm_clr_12__machines_not_loaded_in_the_session_before_the_call_report_no_section(db, w1, m1, m2, s1, mk_assignment):
    """MSM-CLR-12 — machines not loaded in the session before the call report no section afterwards.
    Rules: `clear_for_section` R6"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    m1_id, m2_id, s1_id, w1_id = m1.id, m2.id, s1.id, w1.id
    db.expunge_all()

    result = mgr.clear_for_section(db, factory_section_id=s1_id, workspace_id=w1_id)

    # Then 1
    assert sorted(result) == [m1_id, m2_id]
    # Then 2
    assert all(db.get(Machine, mid) is not None for mid in result)
    # Then 3
    assert db.get(Machine, m1_id).factory_section_id is None
    # Then 4
    assert db.get(Machine, m2_id).factory_section_id is None


# [local-coder] MSM-SET-03
def test_msm_set_03__clearing_a_machine_s_section_deletes_its_link_and_returns_none(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-03 — clearing a machine's section deletes its link and returns None.
    Rules: `set_assignment` R3, Returns"""
    mk_assignment(of=m1, to=s1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MSM-SET-06
def test_msm_set_06__clearing_an_unknown_machine_id_returns_none_and_writes_nothing(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-06 — clearing an unknown machine id returns None and writes nothing.
    Rules: `set_assignment` R3"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    result = mgr.set_assignment(db, machine_id=MISSING, factory_id=f1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-09
def test_msm_set_09__re_saving_the_same_section_keeps_exactly_one_link_of_that_machine_to(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-09 — re-saving the same section keeps exactly one link of that machine to that section.
    Rules: `set_assignment` R4 (the part that holds today and after the BUG-909 fix)"""
    mk_assignment(of=m1, to=s1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

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


# [local-coder] MSM-SET-10
def test_msm_set_10__a_section_id_that_no_section_has_is_answered_with_404_and_the_machine(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-10 — a section id that no section has is answered with 404 and the machine keeps its link.
    Rules: `set_assignment` R5, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-12
def test_msm_set_12__a_negative_section_id_is_answered_with_404(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-12 — a negative section id is answered with 404.
    Rules: `set_assignment` R5, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=-1, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID -1 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-14
def test_msm_set_14__the_same_section_is_accepted_from_its_own_workspace(db, w2, u2, f9, m9, s9):
    """MSM-SET-14 — the same section is accepted from its own workspace.
    Rules: `set_assignment` R6, R1 (other side of the workspace check)"""
    result = mgr.set_assignment(db, machine_id=m9.id, factory_id=f9.id, factory_section_id=s9.id, workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == m9.id
    assert row.factory_section_id == s9.id
    assert row.workspace_id == w2.id
    # Then 3
    assert len(rows_of(db, m9)) == 1


# [local-coder] MSM-SET-16
def test_msm_set_16__a_soft_deleted_section_of_another_factory_gets_the_deleted_message(db, w1, u2, f2, m1, sx):
    """MSM-SET-16 — a soft-deleted section of another factory gets the "deleted" message, not the factory message.
    Rules: `set_assignment` R7, Errors row 2 (the deleted check comes first)"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f2.id, factory_section_id=sx.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot assign a machine to a deleted factory section"
    # Then 4
    assert written(db) == before
    # Then 5
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSM-SET-17
def test_msm_set_17__a_live_section_of_another_factory_is_refused_with_400_and_the_machine(db, w1, u2, f1, m1, s1, s3, mk_assignment):
    """MSM-SET-17 — a live section of another factory is refused with 400 and the machine keeps its link.
    Rules: `set_assignment` R8, Errors row 3"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s3.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-18
def test_msm_set_18__a_factory_id_that_names_no_factory_is_refused_with_the_factory_message(db, w1, u2, m1, s1, s2, mk_assignment):
    """MSM-SET-18 — a factory_id that names no factory is refused with the factory message.
    Rules: `set_assignment` R8, Errors row 3"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=MISSING, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] MSM-SET-20
def test_msm_set_20__a_section_of_the_soft_deleted_factory_with_another_factory_id_gets(db, w1, u2, f1, m1, sf):
    """MSM-SET-20 — a section of the soft-deleted factory with another factory_id gets the factory message.
    Rules: `set_assignment` R9 (order: the R8 check comes first), R8, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=sf.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section does not belong to this machine's factory"
    # Then 4
    assert written(db) == before


# [local-coder] MSM-SET-22
def test_msm_set_22__clearing_the_section_of_a_machine_of_the_soft_deleted_factory_is(db, w1, u2, fd, sf, mf, mk_assignment):
    """MSM-SET-22 — clearing the section of a machine of the soft-deleted factory is allowed.
    Rules: `set_assignment` R9 (clearing stays allowed), R3"""
    mk_assignment(of=mf, to=sf)
    before_sf = snap(db, sf)
    before_fd = snap(db, fd)

    result = mgr.set_assignment(db, machine_id=mf.id, factory_id=fd.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert len(rows_of(db, mf)) == 0
    # Then 3
    assert snap(db, sf) == before_sf
    # Then 4
    assert snap(db, fd) == before_fd


# [local-coder] MSM-SET-24
def test_msm_set_24__a_soft_deleted_machine_is_not_refused(db, w1, u2, f1, md, s1):
    """MSM-SET-24 — a soft-deleted machine is not refused.
    Rules: `set_assignment` R10 (Q1)"""
    before_md = snap(db, md)

    result = mgr.set_assignment(db, machine_id=md.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == md.id
    assert row.factory_section_id == s1.id
    # Then 3
    assert snap(db, md) == before_md


# [local-coder] MSM-SET-25
def test_msm_set_25__a_machine_whose_own_factory_differs_from_factory_id_is_not_refused(db, w1, u2, f2, m1, s3):
    """MSM-SET-25 — a machine whose own factory differs from factory_id is not refused.
    Rules: `set_assignment` R10 (Q1)"""
    before_m1 = snap(db, m1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f2.id, factory_section_id=s3.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s3.id
    # Then 3
    assert snap(db, m1) == before_m1


# [claude] MSM-SET-26 (handed back by the local model)
def test_msm_set_26__a_machine_of_another_workspace_is_not_refused_and_the_link_is_stored(db, w1, u2, f1, m9, s1):
    """MSM-SET-26 — a machine of another workspace is not refused and the link is stored in the caller's workspace.
    Rules: `set_assignment` R10 (Q1)"""
    result = mgr.set_assignment(db, machine_id=m9.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == m9.id
    assert row.factory_section_id == s1.id
    # Then 3
    assert row.workspace_id == w1.id


# [local-coder] MSM-SET-28
def test_msm_set_28__a_user_id_that_is_no_profile_fails_on_flush_and_the_machine_s(db, w1, u1, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-28 — a user_id that is no profile fails on flush and the machine's previous link is back.
    Rules: `set_assignment` R11, Errors row 6"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=MISSING)

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


# [local-coder] MSM-SET-32
def test_msm_set_32__a_machine_whose_section_was_already_read_still_reports_it_after(db, w1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-32 — a machine whose section was already read still reports it after clearing.
    Rules: `set_assignment` R12 (P2), R3"""
    mk_assignment(of=m1, to=s1)
    loaded = m1.factory_section_id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert m1.factory_section_id == s1.id
    # Then 3
    assert len(rows_of(db, m1)) == 0


# [local-coder] MSM-SET-33
def test_msm_set_33__a_machine_read_without_a_section_still_reports_no_section_after_a(db, w1, u2, f1, m1, s1):
    """MSM-SET-33 — a machine read without a section still reports no section after a first set.
    Rules: `set_assignment` R12 (P2), R1"""
    loaded = m1.factory_section_id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s1.id
    # Then 2
    assert m1.factory_section_id is None
    # Then 3
    assert len(rows_of(db, m1)) == 1


# [claude] MSM-SET-34
def test_msm_set_34__once_the_machine_is_expired_it_reports_the_new_section(db, w1, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-34 — once the machine is expired it reports the new section.
    Rules: `set_assignment` R12 (P2)"""
    mk_assignment(of=m1, to=s1)
    loaded = m1.factory_section_id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s2.id
    # Then 2
    db.expire(m1)
    assert m1.factory_section_id == s2.id


# [claude] MSM-SET-35
def test_msm_set_35__the_move_is_flushed_but_not_committed_a_fresh_select_sees_it_a_rollback_undoes_it(db, w1, u1, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-35 — the move is flushed but not committed: a fresh SELECT sees it, a rollback undoes it.
    Rules: `set_assignment` R13, Side effects"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert result.factory_section_id == s2.id
        # Then 2
        row = rows_of(db, m1)[0]
        assert row.id == result.id
        assert row.factory_section_id == s2.id
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


# [local-coder] MSM-SET-37
def test_msm_set_37__clearing_touches_only_the_machine_s_own_link(db, w1, u2, f1, m1, m2, s1, mk_assignment):
    """MSM-SET-37 — clearing touches only the machine's own link.
    Rules: `set_assignment` R13, R3"""
    mk_assignment(of=m1, to=s1)
    a2 = mk_assignment(of=m2, to=s1)
    before_a2 = snap(db, a2)
    before_m1 = snap(db, m1)
    before_s1 = snap(db, s1)
    before_f1 = snap(db, f1)

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=None, workspace_id=w1.id, user_id=u2.id)

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
    # Then 6
    assert snap(db, f1) == before_f1


# [claude] MSM-CLR-02 (handed back by the local model)
def test_msm_clr_02__the_link_of_a_soft_deleted_machine_is_deleted_and_listed_too(db, w1, m1, md, s1, mk_assignment):
    """MSM-CLR-02 — the link of a soft-deleted machine is deleted and listed too.
    Rules: `clear_for_section` R1, R4"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=md, to=s1)
    before_md = snap(db, md)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == [m1.id, md.id]
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 0
    # Then 3
    assert snap(db, md) == before_md


# [local-coder] MSM-CLR-03
def test_msm_clr_03__the_links_of_a_soft_deleted_section_are_deleted_and_the_section_is(db, w1, m1, sx, mk_assignment):
    """MSM-CLR-03 — the links of a soft-deleted section are deleted and the section is not written.
    Rules: `clear_for_section` R1, R4"""
    mk_assignment(of=m1, to=sx)
    before_sx = snap(db, sx)

    result = mgr.clear_for_section(db, factory_section_id=sx.id, workspace_id=w1.id)

    # Then 1
    assert result == [m1.id]
    # Then 2
    assert len(rows_of(db, m1)) == 0
    # Then 3
    assert snap(db, sx) == before_sx


# [local-coder] MSM-CLR-05
def test_msm_clr_05__the_other_workspace_s_call_removes_only_its_own_link(db, w2, m1, m9, s1, mk_assignment):
    """MSM-CLR-05 — the other workspace's call removes only its own link.
    Rules: `clear_for_section` R1"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m9, to=s1)
    before_a1 = snap(db, a1)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w2.id)

    # Then 1
    assert result == [m9.id]
    # Then 2
    assert snap(db, a1) == before_a1
    # Then 3
    assert len(rows_of(db, m9)) == 0


# [local-coder] MSM-CLR-06
def test_msm_clr_06__an_unknown_section_id_returns_an_empty_list_and_writes_nothing(db, w1, m1, s1, mk_assignment):
    """MSM-CLR-06 — an unknown section id returns an empty list and writes nothing.
    Rules: `clear_for_section` R2"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    result = mgr.clear_for_section(db, factory_section_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] MSM-CLR-07
def test_msm_clr_07__a_section_without_links_returns_an_empty_list_and_writes_nothing(db, w1, m1, s1, s2, mk_assignment):
    """MSM-CLR-07 — a section without links returns an empty list and writes nothing.
    Rules: `clear_for_section` R2"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)

    result = mgr.clear_for_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] MSM-CLR-08
def test_msm_clr_08__a_section_whose_only_link_is_in_another_workspace_returns_an_empty(db, w1, m9, s1, mk_assignment):
    """MSM-CLR-08 — a section whose only link is in another workspace returns an empty list.
    Rules: `clear_for_section` R2"""
    a9 = mk_assignment(of=m9, to=s1)
    before_a9 = snap(db, a9)
    before = written(db)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a9) == before_a9


# [claude] MSM-CLR-09
@pytest.mark.xfail(strict=True, reason='BUG-907: "Unassign every machine of a section" stops at 10 000')
def test_msm_clr_09__all_10_001_links_of_a_section_are_deleted_and_listed(db, w1, u1, f1, s1):
    """MSM-CLR-09 — all 10 001 links of a section are deleted and listed.
    Rules: `clear_for_section` R3 [BUG-907]"""
    machine_ids, _ = bulk_assigned_machines(
        db, names=[f"Bulk {k:05d}" for k in range(1, 10002)], factory=f1, section=s1, created_by=u1)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert len(set(result)) == len(result)
    # Then 2
    assert set(result) <= set(machine_ids)
    # Then 3
    assert len(result) == 10001
    # Then 4
    assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 0


# [claude] MSM-CLR-13
def test_msm_clr_13__the_machine_ids_come_back_in_the_order_of_the_link_ids(db, w1, u2, m1, m2, m3, s1, mk_assignment):
    """MSM-CLR-13 — the machine ids come back in the order of the link ids.
    Rules: `clear_for_section` R7 [BUG-906]"""
    a1 = mk_assignment(of=m3, to=s1)
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a1.created_by = u2.id
    db.flush()

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == [m1.id, m2.id, m3.id]
    # Then 2
    assert result == [m3.id, m1.id, m2.id]


# [claude] MSM-CLR-14
def test_msm_clr_14__the_removal_is_flushed_but_not_committed_a_fresh_select_sees_no_link_a_rollback_brings_every_link_back(db, w1, u1, m1, m2, s1, mk_assignment):
    """MSM-CLR-14 — the removal is flushed but not committed: a fresh SELECT sees no link, a rollback brings every link back.
    Rules: `clear_for_section` R8, Side effects"""
    a1 = mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

        # Then 1
        assert sorted(result) == [m1.id, m2.id]
        # Then 2
        assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 0
        sp.rollback()
        # Then 3
        assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 2
        # Then 4
        row = reread(db, a1)
        assert row.machine_id == m1.id
        assert row.created_by == u1.id
        # Then 5
        assert commit_spy.call_count == 0
