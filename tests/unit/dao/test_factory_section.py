"""Unit tests for app/dao/factory_section.py.

Implements tests/unit/dao/factory_section.cases.md, one test per case. Real
Postgres session (`db` fixture). The only thing patched is the clock:
`app.dao.factory_section.utcnow` returns NOW in every test (Conventions, Externals).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/factory_section.helpers.md as its only view of this file; tests
below a `# [claude] <ID>` comment are the `Author: claude` cards, written by
hand at finishing (bulk loops, the commit spy, the clock spy, the statement
recorder, edits of the standing row FD, follow-up DAO calls, round trips).
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
)
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.factory_section import factory_section_dao
from app.dao.machine import machine_dao
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton factory_section_dao" (a module-level name, not a fixture)
dao = factory_section_dao

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


# Convention "U1, U2 = two profiles rows" (U1 creates the Given sections, U2 acts)
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, name, abbreviation, workspace_id, **columns):
    fields = {"name": name, "abbreviation": abbreviation, "workspace_id": workspace_id,
              "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None}
    fields.update(columns)
    return _add(db, Factory(**fields))


# Convention "five factories rows": F1 (live, W1), F2 (second live factory of W1),
# F9 (the factory of W2), FD (soft-deleted, W1; is_active stays True), FI (live but inactive, W1)
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
def fd(db, w1, u1, f9):
    return _factory(db, "Old Plant", "OP", w1.id, is_deleted=True, deleted_at=T0, deleted_by=u1.id)


@pytest.fixture
def fi(db, w1, fd):
    return _factory(db, "Idle Plant", "IP", w1.id, is_active=False)


# Externals "app.dao.factory_section.utcnow is patched to return NOW in every test".
# The mock is a fixture of its own so that a card can look at its calls (FSD-RS-05).
@pytest.fixture
def clock(monkeypatch):
    mock = MagicMock(name="utcnow", return_value=NOW)
    monkeypatch.setattr("app.dao.factory_section.utcnow", mock)
    return mock


# Convention "These nine rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(clock, w1, w2, u1, u2, f1, f2, f9, fd, fi):
    return None


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
    """mk_machine(of=<factory>, name=...) -> Machine. Keywords only."""
    def _mk(*, of, name):
        return _add(db, Machine(workspace_id=of.workspace_id, factory_id=of.id, name=name))
    return _mk


# Convention "assignment of M to S"
@pytest.fixture
def mk_assignment(db):
    """mk_assignment(of=<machine>, to=<section>) -> MachineSectionAssignment. Keywords only."""
    def _mk(*, of, to):
        return _add(db, MachineSectionAssignment(workspace_id=of.workspace_id, machine_id=of.id,
                                                 factory_section_id=to.id))
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


# Convention "ids(result)" / "names(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "by_id(result, X)": the one element of result whose id == X.id
def by_id(result, row):
    (found,) = [s for s in result if s.id == row.id]
    return found


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in factory_section.helpers.md)
# --------------------------------------------------------------------------- #

def test_fsd_gf_04__the_other_workspace_gets_its_own_section(db, w2, f9, mk_section):
    """FSD-GF-04 — the other workspace gets its own section.
    Rules: `get_by_factory` R1"""
    mk_section(name="Cutting")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s9.id]
    # Then 2
    assert result[0].workspace_id == w2.id


def test_fsd_gf_10__a_soft_deleted_section_is_not_returned(db, w1, f1, mk_section):
    """FSD-GF-10 — a soft-deleted section is not returned.
    Rules: `get_by_factory` R2 [BUG-905]"""
    s1 = mk_section(name="Cutting")
    mk_section(name="Old Line", deleted=True)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert ids(result) == [s1.id]


def test_fsd_gf_30__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_section):
    """FSD-GF-30 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 1"""
    s1 = mk_section(name="Cutting")
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, s1) == before_s1


def test_fsd_sd_06__the_machine_its_assignment_row_and_the_factory_of_the_deleted_section(db, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSD-SD-06 — the machine, its assignment row and the factory of the deleted section are left exactly as they were.
    Rules: `soft_delete` R3"""
    s1 = mk_section(name="Cutting")
    m1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before_m1 = snap(db, m1)
    before_f1 = snap(db, f1)
    before = written(db)

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 6
    assert snap(db, m1) == before_m1
    # Then 7
    assert count_rows(db, "machines") == 1
    # Then 8
    assert snap(db, f1) == before_f1
    # Then 9
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 10
    assert written(db) == before


def test_fsd_rs_02__no_other_column_of_the_section_is_changed_by_the_restore(db, w1, u1, f1, mk_section):
    """FSD-RS-02 — no other column of the section is changed by the restore.
    Rules: `restore` R2"""
    sx = mk_section(name="Old Line", deleted=True)
    created_before = sx.created_at

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.name == "Old Line"
    assert row.factory_id == f1.id
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.created_at == created_before
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert row.is_deleted is False


def test_fsd_inh_09__update_with_an_explicit_null_name_changes_only_the_factory(db, w1, f2, mk_section):
    """FSD-INH-09 — update with an explicit null name changes only the factory.
    Rules: inherited R3"""
    s1 = mk_section(name="Cutting")

    result = dao.update(db, db_obj=s1, obj_in=FactorySectionUpdate(name=None, factory_id=f2.id))

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.factory_id == f2.id
    # Then 3
    assert row.name == "Cutting"
    # Then 4
    assert row.workspace_id == w1.id


# [local-coder] FSD-GF-01
def test_fsd_gf_01__returns_a_list_of_the_sections_of_that_factory(db, w1, f1, f2, mk_section):
    """FSD-GF-01 — returns a list of the sections of that factory.
    Rules: `get_by_factory` R1, Returns"""
    s1 = mk_section(name="Cutting")
    s2 = mk_section(name="Paint")
    mk_section(name="Welding", factory_id=f2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [s1.id, s2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], FactorySection)


# [local-coder] FSD-GF-12
def test_fsd_gf_12__soft_deleted_sections_do_not_use_up_a_place_under_limit(db, w1, f1, mk_section):
    """FSD-GF-12 — soft-deleted sections do not use up a place under limit.
    Rules: `get_by_factory` R2 [BUG-905], R4"""
    mk_section(name="Old Line", deleted=True)
    mk_section(name="Shut Bay", deleted=True)
    mk_section(name="Scrap Row", deleted=True)
    l1 = mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [l1.id]


# [local-coder] FSD-GF-15
def test_fsd_gf_15__the_live_section_of_a_soft_deleted_factory_is_hidden(db, w1, fd, mk_section):
    """FSD-GF-15 — the live section of a soft-deleted factory is hidden.
    Rules: `get_by_factory` R3a [BUG-904] (P1)"""
    mk_section(name="Cutting", factory_id=fd.id)
    mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-37
def test_fsd_gf_37__a_section_with_machines_assigned_and_one_without_are_each_returned(db, w1, f1, mk_section, mk_machine, mk_assignment):
    """FSD-GF-37 — a section with machines assigned and one without are each returned once, and nothing is written.
    Rules: `get_by_factory` R7"""
    s1 = mk_section(name="Cutting")
    m1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=m1, to=s1)
    m2 = mk_machine(of=f1, name="Press")
    mk_assignment(of=m2, to=s1)
    s2 = mk_section(name="Paint")
    before = written(db)
    before_s1 = snap(db, s1)
    before_a1 = snap(db, a1)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [s1.id, s2.id]
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    assert snap(db, a1) == before_a1
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 2


# [local-coder] FSD-SD-02
def test_fsd_sd_02__no_other_column_of_the_section_is_changed_by_the_delete(db, w1, u1, u2, f1, mk_section):
    """FSD-SD-02 — no other column of the section is changed by the delete.
    Rules: `soft_delete` R2"""
    s1 = mk_section(name="Cutting", updated_by=u1.id)
    created_before = s1.created_at

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.name == "Cutting"
    assert row.factory_id == f1.id
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.updated_by == u1.id
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert row.created_at == created_before
    # Then 7
    assert row.is_deleted is True


# [local-coder] FSD-SD-10
def test_fsd_sd_10__a_section_of_a_soft_deleted_factory_is_deleted_all_the_same_and_the(db, u1, u2, fd, mk_section):
    """FSD-SD-10 — a section of a soft-deleted factory is deleted all the same and the factory is not touched.
    Rules: `soft_delete` R6, R3"""
    sh = mk_section(name="Cutting", factory_id=fd.id)
    before_fd = snap(db, fd)

    result = dao.soft_delete(db, db_obj=sh, deleted_by=u2.id)

    # Then 1
    assert result is sh
    # Then 2
    row = reread(db, sh)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    row = reread(db, fd)
    assert row.is_deleted is True
    # Then 6
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [local-coder] FSD-SD-12
def test_fsd_sd_12__a_deleted_by_that_is_no_profile_id_fails_on_flush_and_the_section(db, mk_section):
    """FSD-SD-12 — a deleted_by that is no profile id fails on flush and the section stays live.
    Rules: `soft_delete` R7, Errors row 1"""
    s1 = mk_section(name="Cutting")
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=s1, deleted_by=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    row = reread(db, s1)
    assert row.is_deleted is False
    # Then 6
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 7
    assert row.updated_at is None
    # Then 8
    assert written(db) == before


# [local-coder] FSD-RS-03
def test_fsd_rs_03__updated_by_keeps_the_value_it_had(db, u2, mk_section):
    """FSD-RS-03 — updated_by keeps the value it had.
    Rules: `restore` R2a (P3)"""
    sx = mk_section(name="Old Line", updated_by=u2.id, deleted=True)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.updated_by == u2.id
    # Then 3
    assert row.is_deleted is False


# [local-coder] FSD-RS-08
def test_fsd_rs_08__a_section_that_is_already_live_loaded_from_the_database_is_left(db, mk_section):
    """FSD-RS-08 — a section that is already live, loaded from the database, is left exactly as it is with no UPDATE.
    Rules: `restore` R4"""
    s1 = mk_section(name="Cutting")
    db.refresh(s1)
    before_s1 = snap(db, s1)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    assert snap(db, s1) == before_s1
    # Then 3
    row = reread(db, s1)
    assert row.updated_at is None
    # Then 4
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSD-RS-12
def test_fsd_rs_12__other_deleted_sections_stay_deleted_and_a_live_one_is_not_touched(db, u1, f2, mk_section):
    """FSD-RS-12 — other deleted sections stay deleted and a live one is not touched.
    Rules: `restore` R6, Side effects"""
    sx1 = mk_section(name="Old Line", deleted=True)
    sx2 = mk_section(name="Shut Bay", deleted=True)
    s3 = mk_section(name="Cutting")
    sx4 = mk_section(name="Scrap Row", factory_id=f2.id, deleted=True)
    before_sx2 = snap(db, sx2)
    before_s3 = snap(db, s3)
    before_sx4 = snap(db, sx4)
    before = written(db)

    result = dao.restore(db, db_obj=sx1)

    # Then 1
    assert result is sx1
    # Then 2
    row = reread(db, sx1)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, sx2) == before_sx2
    # Then 4
    row = reread(db, sx2)
    assert row.is_deleted is True
    # Then 5
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 6
    assert snap(db, s3) == before_s3
    # Then 7
    row = reread(db, s3)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 8
    assert snap(db, sx4) == before_sx4
    # Then 9
    row = reread(db, sx4)
    assert row.is_deleted is True
    # Then 10
    assert written(db) == before
    # Then 11
    assert count_rows(db, "factory_sections") == 4


# [local-coder] FSD-RS-15
def test_fsd_rs_15__a_deleted_section_of_a_soft_deleted_factory_is_restored_and_the(db, u1, fd, mk_section):
    """FSD-RS-15 — a deleted section of a soft-deleted factory is restored and the factory row stays as it was.
    Rules: `restore` R7b"""
    sh = mk_section(name="Old Line", factory_id=fd.id, deleted=True)
    before_fd = snap(db, fd)

    result = dao.restore(db, db_obj=sh)

    # Then 1
    assert result is sh
    # Then 2
    row = reread(db, sh)
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.factory_id == fd.id
    # Then 5
    assert snap(db, fd) == before_fd
    # Then 6
    row = reread(db, fd)
    assert row.is_deleted is True
    # Then 7
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [local-coder] FSD-INH-01
def test_fsd_inh_01__create_with_a_dict_of_the_three_required_values_stores_a_section_with(db, w1, f1):
    """FSD-INH-01 — create with a dict of the three required values stores a section with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Cutting", "factory_id": f1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Cutting"
    assert row.factory_id == f1.id
    assert row.workspace_id == w1.id
    # Then 3
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 4
    assert row.created_at is not None
    # Then 5
    assert row.created_by is None
    assert row.updated_by is None
    # Then 6
    assert row.updated_at is None
    # Then 7
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSD-INH-02
def test_fsd_inh_02__create_with_a_factorysectioncreate_schema_fails_on_flush_and_saves_no(db, f1):
    """FSD-INH-02 — create with a FactorySectionCreate schema fails on flush and saves no section.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=FactorySectionCreate(name="Cutting", factory_id=f1.id))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSD-INH-04
def test_fsd_inh_04__create_with_a_dict_that_has_no_name_fails_on_flush_and_saves_no(db, w1, f1):
    """FSD-INH-04 — create with a dict that has no name fails on flush and saves no section.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "factory_id": f1.id})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "name"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSD-INH-11
def test_fsd_inh_11__get_returns_the_section_of_another_workspace(db, w2, f9, mk_section):
    """FSD-INH-11 — get returns the section of another workspace.
    Rules: inherited R4 (P2)"""
    mk_section(name="Cutting")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get(db, s9.id)

    # Then 1
    assert result.id == s9.id
    # Then 2
    assert result.workspace_id == w2.id
    # Then 3
    assert result.name == "Packing"


# [local-coder] FSD-INH-17
def test_fsd_inh_17__get_by_workspace_returns_deleted_sections_and_sections_of_a_deleted(db, w1, fd, f9, w2, mk_section):
    """FSD-INH-17 — get_by_workspace returns deleted sections and sections of a deleted factory along with the rest.
    Rules: inherited R4 (P2)"""
    s1 = mk_section(name="Cutting")
    sx = mk_section(name="Old Line", deleted=True)
    sh = mk_section(name="Paint", factory_id=fd.id)
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, sx.id, sh.id]
    # Then 2
    assert len(result) == 3
    # Then 3
    assert by_id(result, sx).is_deleted is True
    # Then 4
    assert by_id(result, sh).factory_id == fd.id


# [local-coder] FSD-GF-38
def test_fsd_gf_38__the_lookup_writes_nothing_and_leaves_a_soft_deleted_section_as_it_was(db, w1, f1, u1, mk_section):
    """FSD-GF-38 — the lookup writes nothing and leaves a soft-deleted section as it was.
    Rules: `get_by_factory` R7, Side effects"""
    s1 = mk_section(name="Cutting")
    sx = mk_section(name="Old Line", deleted=True)
    before = written(db)
    before_s1 = snap(db, s1)
    before_sx = snap(db, sx)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert set(ids(result)) <= {s1.id, sx.id}
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, s1) == before_s1
    # Then 5
    row = reread(db, s1)
    assert row.updated_at is None
    # Then 6
    assert snap(db, sx) == before_sx
    # Then 7
    row = reread(db, sx)
    assert row.is_deleted is True
    # Then 8
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [local-coder] FSD-SD-11
def test_fsd_sd_11__only_that_section_row_is_touched(db, u1, u2, mk_section):
    """FSD-SD-11 — only that section row is touched.
    Rules: `soft_delete` R6, Side effects"""
    s1 = mk_section(name="Cutting")
    s2 = mk_section(name="Paint")
    sx = mk_section(name="Old Line", deleted=True)
    before_s2 = snap(db, s2)
    before_sx = snap(db, sx)
    before = written(db)

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, s2) == before_s2
    # Then 4
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 5
    assert snap(db, sx) == before_sx
    # Then 6
    row = reread(db, sx)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before
    # Then 8
    assert count_rows(db, "factory_sections") == 3


# [local-coder] FSD-RS-07
def test_fsd_rs_07__a_deleted_section_with_is_active_false_comes_back_live_and_still(db, mk_section):
    """FSD-RS-07 — a deleted section with is_active False comes back live and still inactive.
    Rules: `restore` R3 (Q2)"""
    sx = mk_section(name="Shut Bay", is_active=False, deleted=True)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FSD-INH-10
def test_fsd_inh_10__update_with_a_dict_can_switch_is_active_off_and_changes_nothing_else(db, f1, mk_section):
    """FSD-INH-10 — update with a dict can switch is_active off and changes nothing else.
    Rules: inherited R3"""
    s1 = mk_section(name="Cutting")

    result = dao.update(db, db_obj=s1, obj_in={"is_active": False})

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.name == "Cutting"
    assert row.factory_id == f1.id
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FSD-GF-02
def test_fsd_gf_02__a_call_for_the_other_factory_returns_only_that_factory_s_section(db, w1, f2, mk_section):
    """FSD-GF-02 — a call for the other factory returns only that factory's section.
    Rules: `get_by_factory` R1"""
    mk_section(name="Cutting")
    mk_section(name="Paint")
    s3 = mk_section(name="Welding", factory_id=f2.id)

    result = dao.get_by_factory(db, factory_id=f2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s3.id]
    # Then 2
    assert result[0].name == "Welding"


# [local-coder] FSD-GF-03
def test_fsd_gf_03__another_workspace_s_section_is_not_returned_when_its_factory_id_is(db, w1, w2, f9, mk_section):
    """FSD-GF-03 — another workspace's section is not returned when its factory id is given.
    Rules: `get_by_factory` R1"""
    mk_section(name="Cutting")
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-05
def test_fsd_gf_05__a_factory_id_asked_for_with_another_workspace_id_returns_an_empty_list(db, w2, f1, f9, mk_section):
    """FSD-GF-05 — a factory id asked for with another workspace id returns an empty list.
    Rules: `get_by_factory` R1"""
    mk_section(name="Cutting")
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-06
def test_fsd_gf_06__a_factory_with_no_sections_returns_an_empty_list(db, w1, f2, mk_section):
    """FSD-GF-06 — a factory with no sections returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-07
def test_fsd_gf_07__an_unknown_factory_id_returns_an_empty_list(db, w1, mk_section):
    """FSD-GF-07 — an unknown factory id returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-08
def test_fsd_gf_08__factory_id_0_returns_an_empty_list(db, w1, mk_section):
    """FSD-GF-08 — factory id 0 returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-09
def test_fsd_gf_09__an_unknown_workspace_id_returns_an_empty_list(db, f1, mk_section):
    """FSD-GF-09 — an unknown workspace id returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] FSD-GF-11
def test_fsd_gf_11__100_soft_deleted_sections_in_front_of_one_live_section_do_not_fill_the_default_page(db, w1, f1, mk_section):
    """FSD-GF-11 — 100 soft-deleted sections in front of one live section do not fill the default page.
    Rules: `get_by_factory` R2 [BUG-905]"""
    for k in range(1, 101):
        mk_section(name=f"Old {k:03d}", deleted=True)
    late = mk_section(name="Late")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [late.id]


# [local-coder] FSD-GF-13
def test_fsd_gf_13__a_soft_deleted_section_does_not_count_toward_skip(db, w1, f1, mk_section):
    """FSD-GF-13 — a soft-deleted section does not count toward skip.
    Rules: `get_by_factory` R2 [BUG-905], R5"""
    mk_section(name="Old Line", deleted=True)
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-14
def test_fsd_gf_14__a_live_section_with_is_active_false_is_returned(db, w1, f1, mk_section):
    """FSD-GF-14 — a live section with is_active False is returned.
    Rules: `get_by_factory` R2a"""
    s1 = mk_section(name="Cutting")
    si = mk_section(name="Idle Bay", is_active=False)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, si.id]
    # Then 2
    assert by_id(result, si).is_active is False
    # Then 3
    assert by_id(result, si).is_deleted is False


# [local-coder] FSD-GF-16
def test_fsd_gf_16__the_section_of_a_live_factory_is_returned_while_another_factory_of(db, w1, f1, fd, mk_section):
    """FSD-GF-16 — the section of a live factory is returned while another factory of the workspace is soft-deleted.
    Rules: `get_by_factory` R1, R3a (the side that holds today)"""
    mk_section(name="Cutting", factory_id=fd.id)
    s1 = mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert result[0].name == "Paint"


# [local-coder] FSD-GF-17
def test_fsd_gf_17__a_lookup_leaves_the_sections_of_a_soft_deleted_factory_exactly_as(db, w1, fd, mk_section):
    """FSD-GF-17 — a lookup leaves the sections of a soft-deleted factory exactly as they were.
    Rules: `get_by_factory` R3b (1), R7"""
    sh = mk_section(name="Cutting", factory_id=fd.id)
    shi = mk_section(name="Paint", factory_id=fd.id, is_active=False)
    before_sh = snap(db, sh)
    before_shi = snap(db, shi)
    before_fd = snap(db, fd)
    before = written(db)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) <= {sh.id, shi.id}
    # Then 3
    assert snap(db, sh) == before_sh
    # Then 4
    row = reread(db, sh)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert row.updated_at is None
    # Then 7
    assert snap(db, shi) == before_shi
    # Then 8
    row = reread(db, shi)
    assert row.is_deleted is False
    assert row.is_active is False
    # Then 9
    assert snap(db, fd) == before_fd
    # Then 10
    assert written(db) == before


# [local-coder] FSD-GF-18
def test_fsd_gf_18__a_live_but_inactive_factory_hides_nothing(db, w1, fi, mk_section):
    """FSD-GF-18 — a live but inactive factory hides nothing.
    Rules: `get_by_factory` R3b (2)"""
    sf = mk_section(name="Cutting", factory_id=fi.id)
    mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=fi.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [sf.id]
    # Then 2
    assert result[0].is_deleted is False


# [claude] FSD-GF-19
def test_fsd_gf_19__once_the_factory_is_no_longer_deleted_its_section_is_returned_again_unchanged(db, w1, u2, fd, mk_section):
    """FSD-GF-19 — once the factory is no longer deleted its section is returned again, unchanged.
    Rules: `get_by_factory` R3b (3)"""
    sh = mk_section(name="Cutting", factory_id=fd.id, updated_by=u2.id)
    mk_section(name="Paint")
    before_sh = snap(db, sh)
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    before = written(db)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [sh.id]
    # Then 2
    assert snap(db, sh) == before_sh
    # Then 3
    row = reread(db, sh)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 4
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert row.updated_by == u2.id
    # Then 6
    assert row.updated_at is None
    # Then 7
    assert written(db) == before


# [local-coder] FSD-GF-20
def test_fsd_gf_20__sections_of_other_factories_and_workspaces_do_not_use_up_a_place_in(db, w1, w2, f1, f2, f9, mk_section):
    """FSD-GF-20 — sections of other factories and workspaces do not use up a place in the page.
    Rules: `get_by_factory` R4"""
    mk_section(name="Welding", factory_id=f2.id)
    mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    l1 = mk_section(name="Cutting")
    l2 = mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [l1.id, l2.id]


# [local-coder] FSD-GF-21
def test_fsd_gf_21__skip_counts_only_the_sections_of_that_factory(db, w1, f1, f2, mk_section):
    """FSD-GF-21 — skip counts only the sections of that factory.
    Rules: `get_by_factory` R4, R5"""
    mk_section(name="Welding", factory_id=f2.id)
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert result == []


# [claude] FSD-GF-22
def test_fsd_gf_22__default_limit_returns_exactly_100_of_101_sections(db, w1, f1, mk_section):
    """FSD-GF-22 — default limit returns exactly 100 of 101 sections.
    Rules: `get_by_factory` R4"""
    all_ids = [mk_section(name=f"N{k:03d}").id for k in range(1, 102)]

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= set(all_ids)


# [claude] FSD-GF-23
def test_fsd_gf_23__an_explicit_limit_of_101_returns_all_101_sections(db, w1, f1, mk_section):
    """FSD-GF-23 — an explicit limit of 101 returns all 101 sections.
    Rules: `get_by_factory` R4"""
    all_ids = [mk_section(name=f"N{k:03d}").id for k in range(1, 102)]

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == all_ids


# [local-coder] FSD-GF-24
def test_fsd_gf_24__limit_2_of_three_sections_returns_two_different_sections(db, w1, f1, mk_section):
    """FSD-GF-24 — limit 2 of three sections returns two different sections.
    Rules: `get_by_factory` R4"""
    s1 = mk_section(name="Cutting")
    s2 = mk_section(name="Paint")
    s3 = mk_section(name="Welding")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {s1.id, s2.id, s3.id}


# [local-coder] FSD-GF-25
def test_fsd_gf_25__the_last_window_is_short(db, w1, f1, mk_section):
    """FSD-GF-25 — the last window is short.
    Rules: `get_by_factory` R4"""
    s1 = mk_section(name="Cutting")
    s2 = mk_section(name="Paint")
    s3 = mk_section(name="Welding")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [s1.id, s2.id, s3.id]


# [local-coder] FSD-GF-26
def test_fsd_gf_26__limit_0_returns_an_empty_list(db, w1, f1, mk_section):
    """FSD-GF-26 — limit 0 returns an empty list.
    Rules: `get_by_factory` R5"""
    mk_section(name="Cutting")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-27
def test_fsd_gf_27__skip_equal_to_the_number_of_sections_returns_an_empty_list(db, w1, f1, mk_section):
    """FSD-GF-27 — skip equal to the number of sections returns an empty list.
    Rules: `get_by_factory` R5"""
    mk_section(name="Cutting")
    mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-28
def test_fsd_gf_28__skip_one_below_the_number_of_sections_returns_one_section(db, w1, f1, mk_section):
    """FSD-GF-28 — skip one below the number of sections returns one section.
    Rules: `get_by_factory` R5, R4"""
    s1 = mk_section(name="Cutting")
    s2 = mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [s1.id, s2.id]


# [local-coder] FSD-GF-29
def test_fsd_gf_29__skip_past_the_number_of_sections_returns_an_empty_list(db, w1, f1, mk_section):
    """FSD-GF-29 — skip past the number of sections returns an empty list.
    Rules: `get_by_factory` R5"""
    mk_section(name="Cutting")
    mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] FSD-GF-31
def test_fsd_gf_31__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_section):
    """FSD-GF-31 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 2"""
    s1 = mk_section(name="Cutting")
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, s1) == before_s1


# [claude] FSD-GF-32
def test_fsd_gf_32__sections_come_back_by_name_case_insensitive_ascending(db, w1, f1, mk_section):
    """FSD-GF-32 — sections come back by name, case-insensitive ascending.
    Rules: `get_by_factory` R6 [BUG-903]"""
    s1 = mk_section(name="Zulu")
    s2 = mk_section(name="bolt")
    s3 = mk_section(name="apple")
    s4 = mk_section(name="Banana")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id, s3.id, s4.id]
    # Then 2
    assert names(result) == ["apple", "Banana", "bolt", "Zulu"]


# [claude] FSD-GF-33
def test_fsd_gf_33__names_that_differ_only_in_case_come_back_in_id_order(db, w1, f1, mk_section):
    """FSD-GF-33 — names that differ only in case come back in id order.
    Rules: `get_by_factory` R6 [BUG-903]"""
    s1 = mk_section(name="Zulu")
    s2 = mk_section(name="bolt")
    s3 = mk_section(name="apple")
    s4 = mk_section(name="Bolt")
    s5 = mk_section(name="Banana")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id, s3.id, s4.id, s5.id]
    # Then 2
    assert ids(result) == [s3.id, s5.id, s2.id, s4.id, s1.id]


# [claude] FSD-GF-34
def test_fsd_gf_34__a_middle_window_holds_the_second_and_third_section_by_name(db, w1, f1, mk_section):
    """FSD-GF-34 — a middle window holds the second and third section by name.
    Rules: `get_by_factory` R6 [BUG-903], R4"""
    mk_section(name="Zulu")
    mk_section(name="bolt")
    mk_section(name="apple")
    mk_section(name="Banana")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert names(result) == ["Banana", "bolt"]


# [claude] FSD-GF-35
def test_fsd_gf_35__the_first_window_holds_the_first_two_sections_by_name(db, w1, f1, mk_section):
    """FSD-GF-35 — the first window holds the first two sections by name.
    Rules: `get_by_factory` R6 [BUG-903], R4"""
    mk_section(name="Zulu")
    mk_section(name="bolt")
    mk_section(name="apple")
    mk_section(name="Banana")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert names(result) == ["apple", "Banana"]


# [claude] FSD-GF-36
def test_fsd_gf_36__the_by_factory_query_asks_the_database_for_an_order(db, w1, f1, mk_section):
    """FSD-GF-36 — the by-factory query asks the database for an order.
    Rules: `get_by_factory` R6 [BUG-903]"""
    s1 = mk_section(name="Cutting")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    selects = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()


# [local-coder] FSD-SD-01
def test_fsd_sd_01__a_live_section_is_marked_deleted_with_the_clock_value_and_the_acting(db, u2, mk_section):
    """FSD-SD-01 — a live section is marked deleted with the clock value and the acting user.
    Rules: `soft_delete` R1, R5"""
    s1 = mk_section(name="Cutting")

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

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


# [local-coder] FSD-SD-03
def test_fsd_sd_03__the_delete_does_not_stamp_updated_by(db, u2, mk_section):
    """FSD-SD-03 — the delete does not stamp updated_by.
    Rules: `soft_delete` R2"""
    s1 = mk_section(name="Cutting")

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.updated_by is None
    # Then 3
    assert row.updated_at is not None
    # Then 4
    assert row.is_deleted is True


# [local-coder] FSD-SD-04
def test_fsd_sd_04__an_active_section_still_says_active_after_the_delete(db, u2, mk_section):
    """FSD-SD-04 — an active section still says active after the delete.
    Rules: `soft_delete` R2a (Q1)"""
    s1 = mk_section(name="Cutting")

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is True


# [local-coder] FSD-SD-05
def test_fsd_sd_05__a_live_section_with_is_active_false_is_deleted_and_stays_inactive(db, u2, mk_section):
    """FSD-SD-05 — a live section with is_active False is deleted and stays inactive.
    Rules: `soft_delete` R2a (Q1), R1"""
    si = mk_section(name="Idle Bay", is_active=False)

    result = dao.soft_delete(db, db_obj=si, deleted_by=u2.id)

    # Then 1
    assert result is si
    # Then 2
    row = reread(db, si)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is False
    # Then 4
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id


# [local-coder] FSD-SD-07
def test_fsd_sd_07__an_already_deleted_section_gets_a_new_deletion_stamp_without_an_error(db, u2, mk_section):
    """FSD-SD-07 — an already deleted section gets a new deletion stamp without an error.
    Rules: `soft_delete` R4"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.soft_delete(db, db_obj=sx, deleted_by=u2.id)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.deleted_at == NOW
    # Then 3
    assert row.deleted_by == u2.id
    # Then 4
    assert row.is_deleted is True


# [claude] FSD-SD-08
def test_fsd_sd_08__the_delete_is_flushed_but_not_committed_visible_in_the_session_undone_by_a_rollback(db, w1, u2, mk_section):
    """FSD-SD-08 — the delete is flushed but not committed: visible to the by-id lookup in the session, undone by a rollback.
    Rules: `soft_delete` R5"""
    s1 = mk_section(name="Cutting")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

        # Then 1
        assert result is s1
        # Then 2
        row = reread(db, s1)
        assert row.is_deleted is True
        # Then 3
        assert dao.get_by_id_and_workspace(db, id=s1.id, workspace_id=w1.id).is_deleted is True
        sp.rollback()
        # Then 4
        row = reread(db, s1)
        assert row.is_deleted is False
        assert row.is_active is True
        # Then 5
        assert row.deleted_at is None
        assert row.deleted_by is None
        # Then 6
        assert commit_spy.call_count == 0


# [local-coder] FSD-SD-09
def test_fsd_sd_09__a_section_of_another_workspace_is_deleted_all_the_same(db, w2, u2, f9, mk_section):
    """FSD-SD-09 — a section of another workspace is deleted all the same.
    Rules: `soft_delete` R6"""
    s1 = mk_section(name="Cutting")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)
    before_s1 = snap(db, s1)

    result = dao.soft_delete(db, db_obj=s9, deleted_by=u2.id)

    # Then 1
    assert result is s9
    # Then 2
    row = reread(db, s9)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert row.workspace_id == w2.id
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] FSD-SD-13
def test_fsd_sd_13__deleted_by_none_is_stored_as_null_and_the_section_is_deleted(db, mk_section):
    """FSD-SD-13 — deleted_by None is stored as NULL and the section is deleted.
    Rules: `soft_delete` R8"""
    s1 = mk_section(name="Cutting")

    result = dao.soft_delete(db, db_obj=s1, deleted_by=None)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.deleted_by is None
    # Then 3
    assert row.is_deleted is True
    # Then 4
    assert row.deleted_at == NOW


# [local-coder] FSD-RS-01
def test_fsd_rs_01__a_deleted_section_is_made_live_again_and_its_deletion_stamp_is_cleared(db, mk_section):
    """FSD-RS-01 — a deleted section is made live again and its deletion stamp is cleared.
    Rules: `restore` R1, R5"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    # Then 4
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSD-RS-04
def test_fsd_rs_04__an_empty_updated_by_stays_empty_nobody_is_recorded_as_having_restored(db, mk_section):
    """FSD-RS-04 — an empty updated_by stays empty: nobody is recorded as having restored.
    Rules: `restore` R2a (P3)"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.updated_by is None
    # Then 3
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 4
    row = reread(db, sx)
    assert row.deleted_by is None


# [claude] FSD-RS-05
def test_fsd_rs_05__the_restore_does_not_read_the_clock(db, clock, mk_section):
    """FSD-RS-05 — the restore does not read the clock.
    Rules: `restore` R2a ("The clock is not read")"""
    sx = mk_section(name="Old Line", deleted=True)
    calls_before = clock.call_count

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    assert clock.call_count == calls_before
    # Then 4
    assert row.deleted_at is None


# [local-coder] FSD-RS-06
def test_fsd_rs_06__a_section_deleted_while_active_comes_back_active(db, mk_section):
    """FSD-RS-06 — a section deleted while active comes back active.
    Rules: `restore` R3 (Q2)"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_active is True
    # Then 3
    row = reread(db, sx)
    assert row.is_deleted is False


# [local-coder] FSD-RS-09
def test_fsd_rs_09__a_live_but_inactive_section_loaded_from_the_database_stays_inactive(db, mk_section):
    """FSD-RS-09 — a live but inactive section, loaded from the database, stays inactive with no UPDATE.
    Rules: `restore` R4, R3 (Q2)"""
    si = mk_section(name="Idle Bay", is_active=False)
    db.refresh(si)
    before = snap(db, si)

    result = dao.restore(db, db_obj=si)

    # Then 1
    assert result is si
    # Then 2
    assert snap(db, si) == before
    # Then 3
    row = reread(db, si)
    assert row.updated_at is None
    # Then 4
    assert row.is_active is False
    # Then 5
    assert row.is_deleted is False


# [claude] FSD-RS-10
def test_fsd_rs_10__the_restore_is_flushed_but_not_committed_visible_in_the_session_undone_by_a_rollback(db, w1, u1, f1, mk_section):
    """FSD-RS-10 — the restore is flushed but not committed: visible to the by-factory list in the session, undone by a rollback.
    Rules: `restore` R5"""
    sx = mk_section(name="Old Line", deleted=True)
    s2 = mk_section(name="Cutting")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.restore(db, db_obj=sx)

        # Then 1
        assert result is sx
        # Then 2
        row = reread(db, sx)
        assert row.is_deleted is False
        # Then 3
        listed = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)
        assert sorted(ids(listed)) == [sx.id, s2.id]
        # Then 4
        assert by_id(listed, sx).is_deleted is False
        sp.rollback()
        # Then 5
        row = reread(db, sx)
        assert row.is_deleted is True
        # Then 6
        assert row.deleted_at == T0
        # Then 7
        assert row.deleted_by == u1.id
        # Then 8
        assert commit_spy.call_count == 0


# [local-coder] FSD-RS-11
def test_fsd_rs_11__a_section_of_another_workspace_is_restored_all_the_same(db, w2, f9, mk_section):
    """FSD-RS-11 — a section of another workspace is restored all the same.
    Rules: `restore` R6"""
    s1 = mk_section(name="Cutting")
    sx9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id, deleted=True)
    before_s1 = snap(db, s1)

    result = dao.restore(db, db_obj=sx9)

    # Then 1
    assert result is sx9
    # Then 2
    row = reread(db, sx9)
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.workspace_id == w2.id
    # Then 5
    assert snap(db, s1) == before_s1


# [claude] FSD-RS-13
def test_fsd_rs_13__after_delete_and_restore_the_machine_and_its_assignment_are_as_before(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSD-RS-13 — after delete and restore the machine and its assignment are as before and the machine lookup returns the machine.
    Rules: `restore` R7; `soft_delete` R3"""
    s1 = mk_section(name="Cutting")
    m1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=m1, to=s1)
    before_m = snap(db, m1)
    before_a = snap(db, a1)
    dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, m1) == before_m
    # Then 4
    assert snap(db, a1) == before_a
    # Then 5
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 7
    assert sorted(m.id for m in machine_dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)) == [m1.id]


# [local-coder] FSD-RS-14
def test_fsd_rs_14__the_restore_writes_nothing_to_the_machine_or_the_assignment_row_of(db, f1, mk_section, mk_machine, mk_assignment):
    """FSD-RS-14 — the restore writes nothing to the machine or the assignment row of the section.
    Rules: `restore` R7, Side effects"""
    sx = mk_section(name="Old Line", deleted=True)
    m1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=m1, to=sx)
    before_a1 = snap(db, a1)
    before_m1 = snap(db, m1)
    before = written(db)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == sx.id
    # Then 5
    assert snap(db, m1) == before_m1
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 7
    assert written(db) == before


# [claude] FSD-RS-16
def test_fsd_rs_16__a_section_restored_inside_a_soft_deleted_factory_stays_hidden_from_the_by_factory_list(db, w1, fd, mk_section):
    """FSD-RS-16 — a section restored inside a soft-deleted factory stays hidden from the by-factory list.
    Rules: `restore` R7c [BUG-904] (P1); `get_by_factory` R3a"""
    shx = mk_section(name="Old Line", factory_id=fd.id, deleted=True)

    result = dao.restore(db, db_obj=shx)

    # Then 1
    assert result is shx
    # Then 2
    row = reread(db, shx)
    assert row.is_deleted is False
    # Then 3
    assert dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id) == []


# [claude] FSD-RS-17
def test_fsd_rs_17__a_section_restored_inside_a_soft_deleted_factory_is_listed_once_the_factory_is_no_longer_deleted(db, w1, fd, mk_section):
    """FSD-RS-17 — a section restored inside a soft-deleted factory is listed once the factory is no longer deleted.
    Rules: `restore` R7c (second sentence — holds today); `get_by_factory` R3b (3)"""
    shx = mk_section(name="Old Line", factory_id=fd.id, deleted=True)

    result = dao.restore(db, db_obj=shx)

    # Then 1
    assert result is shx
    # Then 2
    row = reread(db, shx)
    assert row.is_deleted is False
    # Then 3
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()
    assert ids(dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)) == [shx.id]
    # Then 4
    row = reread(db, shx)
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] FSD-RS-18
def test_fsd_rs_18__delete_then_restore_gives_back_the_same_value_in_every_column_except_updated_at(db, u1, u2, f1, mk_section):
    """FSD-RS-18 — delete then restore gives back the same value in every column except updated_at.
    Rules: `restore` R8 (Q2); `soft_delete` R5"""
    s1 = mk_section(name="Cutting", updated_by=u1.id)
    before = snap(db, s1)
    dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    result = dao.restore(db, db_obj=s1)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    after = snap(db, s1)
    assert {c: v for c, v in after.items() if c != "updated_at"} == {c: v for c, v in before.items() if c != "updated_at"}
    # Then 3
    assert row.name == "Cutting"
    assert row.factory_id == f1.id
    # Then 4
    assert row.updated_by == u1.id
    # Then 5
    assert row.is_active is True
    # Then 6
    assert row.is_deleted is False
    # Then 7
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert row.updated_at is not None


# [claude] FSD-RS-19
def test_fsd_rs_19__delete_then_restore_of_an_inactive_section_gives_back_an_inactive_section(db, u1, u2, mk_section):
    """FSD-RS-19 — delete then restore of an inactive section gives back an inactive section.
    Rules: `restore` R8 (Q2), R3 (Q2); `soft_delete` R2a (Q1)"""
    si = mk_section(name="Idle Bay", is_active=False, updated_by=u1.id)
    before = snap(db, si)
    dao.soft_delete(db, db_obj=si, deleted_by=u2.id)

    result = dao.restore(db, db_obj=si)

    # Then 1
    assert result is si
    # Then 2
    row = reread(db, si)
    after = snap(db, si)
    assert {c: v for c, v in after.items() if c != "updated_at"} == {c: v for c, v in before.items() if c != "updated_at"}
    # Then 3
    assert row.is_active is False
    # Then 4
    assert row.updated_by == u1.id
    # Then 5
    assert row.is_deleted is False
    # Then 6
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FSD-RS-20
def test_fsd_rs_20__a_section_is_restored_although_a_live_section_of_the_same_factory_has(db, mk_section):
    """FSD-RS-20 — a section is restored although a live section of the same factory has its name.
    Rules: `restore` R9 (P4)"""
    sx = mk_section(name="Paint", deleted=True)
    s2 = mk_section(name="Paint")
    before_s2 = snap(db, s2)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    row = reread(db, sx)
    assert row.name == "Paint"
    # Then 4
    assert snap(db, s2) == before_s2
    # Then 5
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 6
    row = reread(db, s2)
    assert row.name == "Paint"
    # Then 7
    assert count_rows(db, "factory_sections") == 2


# [local-coder] FSD-RS-21
def test_fsd_rs_21__a_section_is_restored_although_another_soft_deleted_section_of_the(db, mk_section):
    """FSD-RS-21 — a section is restored although another soft-deleted section of the factory has its name.
    Rules: `restore` R9 (P4), R6"""
    sx = mk_section(name="Paint", deleted=True)
    sx2 = mk_section(name="Paint", deleted=True)
    before_sx2 = snap(db, sx2)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    assert row.name == "Paint"
    # Then 4
    assert snap(db, sx2) == before_sx2
    # Then 5
    row = reread(db, sx2)
    assert row.is_deleted is True
    # Then 6
    assert count_rows(db, "factory_sections") == 2


# [local-coder] FSD-RS-22
def test_fsd_rs_22__a_section_is_restored_although_a_live_section_of_another_factory_has(db, f1, f2, mk_section):
    """FSD-RS-22 — a section is restored although a live section of another factory has its name.
    Rules: `restore` R9 (P4)"""
    sx = mk_section(name="Paint", deleted=True)
    s2 = mk_section(name="Paint", factory_id=f2.id)
    before_s2 = snap(db, s2)

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.is_deleted is False
    # Then 3
    row = reread(db, sx)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 4
    assert snap(db, s2) == before_s2
    # Then 5
    row = reread(db, s2)
    assert row.is_deleted is False
    assert row.updated_at is None


# [local-coder] FSD-INH-03
def test_fsd_inh_03__create_with_a_dict_that_has_no_factory_id_fails_on_flush_and_saves_no(db, w1):
    """FSD-INH-03 — create with a dict that has no factory_id fails on flush and saves no section.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Cutting"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "factory_id" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSD-INH-05
def test_fsd_inh_05__create_with_a_factory_id_that_is_no_factory_id_fails_on_flush_and(db, w1):
    """FSD-INH-05 — create with a factory_id that is no factory id fails on flush and saves no section.
    Rules: inherited R2, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Cutting", "factory_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_factory_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSD-INH-06
def test_fsd_inh_06__create_with_a_workspace_id_that_is_no_workspace_id_fails_on_flush_and(db, f1):
    """FSD-INH-06 — create with a workspace_id that is no workspace id fails on flush and saves no section.
    Rules: inherited R2, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "name": "Cutting", "factory_id": f1.id})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factory_sections_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factory_sections") == 0


# [local-coder] FSD-INH-07
def test_fsd_inh_07__create_saves_a_section_whose_factory_belongs_to_another_workspace_as(db, w1, f9):
    """FSD-INH-07 — create saves a section whose factory belongs to another workspace as given.
    Rules: inherited R2a"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Cutting", "factory_id": f9.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    # Then 3
    assert row.factory_id == f9.id
    # Then 4
    assert row.name == "Cutting"
    # Then 5
    assert count_rows(db, "factory_sections") == 1


# [local-coder] FSD-INH-08
def test_fsd_inh_08__update_with_a_factorysectionupdate_that_sets_only_the_name_changes(db, f1, mk_section):
    """FSD-INH-08 — update with a FactorySectionUpdate that sets only the name changes only the name.
    Rules: inherited R3"""
    s1 = mk_section(name="Cutting")

    result = dao.update(db, db_obj=s1, obj_in=FactorySectionUpdate(name="B"))

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.name == "B"
    # Then 3
    assert row.factory_id == f1.id
    # Then 4
    assert row.is_active is True
    assert row.is_deleted is False


# [local-coder] FSD-INH-12
def test_fsd_inh_12__get_returns_a_soft_deleted_section(db, mk_section):
    """FSD-INH-12 — get returns a soft-deleted section.
    Rules: inherited R4 (P2)"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.get(db, sx.id)

    # Then 1
    assert result.id == sx.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] FSD-INH-13
def test_fsd_inh_13__get_returns_the_section_of_a_soft_deleted_factory(db, fd, mk_section):
    """FSD-INH-13 — get returns the section of a soft-deleted factory.
    Rules: inherited R4 (P2)"""
    sh = mk_section(name="Cutting", factory_id=fd.id)

    result = dao.get(db, sh.id)

    # Then 1
    assert result.id == sh.id
    # Then 2
    assert result.factory_id == fd.id
    # Then 3
    assert result.is_deleted is False


# [local-coder] FSD-INH-14
def test_fsd_inh_14__get_by_id_and_workspace_returns_a_soft_deleted_section_of_the(db, w1, u1, mk_section):
    """FSD-INH-14 — get_by_id_and_workspace returns a soft-deleted section of the workspace.
    Rules: inherited R4 (P2)"""
    sx = mk_section(name="Old Line", deleted=True)

    result = dao.get_by_id_and_workspace(db, id=sx.id, workspace_id=w1.id)

    # Then 1
    assert result.id == sx.id
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert result.deleted_at == T0
    # Then 4
    assert result.deleted_by == u1.id


# [local-coder] FSD-INH-15
def test_fsd_inh_15__get_by_id_and_workspace_returns_the_section_of_a_soft_deleted_factory(db, w1, fd, mk_section):
    """FSD-INH-15 — get_by_id_and_workspace returns the section of a soft-deleted factory.
    Rules: inherited R4 (P2)"""
    sh = mk_section(name="Cutting", factory_id=fd.id)

    result = dao.get_by_id_and_workspace(db, id=sh.id, workspace_id=w1.id)

    # Then 1
    assert result.id == sh.id
    # Then 2
    assert result.factory_id == fd.id


# [local-coder] FSD-INH-16
def test_fsd_inh_16__get_by_id_and_workspace_returns_none_for_a_section_of_another(db, w1, w2, f9, mk_section):
    """FSD-INH-16 — get_by_id_and_workspace returns None for a section of another workspace.
    Rules: inherited R4"""
    mk_section(name="Cutting")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=s9.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] FSD-INH-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fsd_inh_18__get_by_workspace_returns_the_sections_in_id_order_not_in_name_order(db, w1, u2, mk_section):
    """FSD-INH-18 — get_by_workspace returns the sections in id order, not in name order.
    Rules: inherited R5 [BUG-100]"""
    s1 = mk_section(name="Zulu")
    s2 = mk_section(name="apple")
    s1.updated_by = u2.id
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]
    # Then 2
    assert ids(result) == [s1.id, s2.id]


# [claude] FSD-INH-19
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_fsd_inh_19__the_workspace_list_query_on_sections_asks_the_database_for_an_order(db, w1, mk_section):
    """FSD-INH-19 — the workspace list query on sections asks the database for an order.
    Rules: inherited R5 [BUG-100]"""
    s1 = mk_section(name="Cutting")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    selects = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()


# [claude] FSD-GF-39
def test_fsd_gf_39__a_section_that_names_a_factory_of_another_workspace_is_listed_for_its(db, w1, f9, mk_section):
    """FSD-GF-39 — a section of the workspace that names a factory of another workspace is listed for its own workspace.
    Rules: `get_by_factory` R1a"""
    sx = mk_section(name="Cutting", factory_id=f9.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [sx.id]
    # Then 2
    assert by_id(result, sx).workspace_id == w1.id
    # Then 3
    assert by_id(result, sx).factory_id == f9.id


# [claude] FSD-GF-40
def test_fsd_gf_40__a_section_that_names_a_factory_of_another_workspace_is_not_listed_for(db, w2, f9, mk_section):
    """FSD-GF-40 — a section that names a factory of another workspace is not listed for the factory's workspace.
    Rules: `get_by_factory` R1a, R1"""
    mk_section(name="Cutting", factory_id=f9.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] FSD-GF-41
def test_fsd_gf_41__assigned_machines_do_not_use_up_places_in_the_page(db, w1, f1, mk_section, mk_machine, mk_assignment):
    """FSD-GF-41 — assigned machines do not use up places in the page.
    Rules: `get_by_factory` R7, R4"""
    s1 = mk_section(name="Cutting")
    m1 = mk_machine(of=f1, name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(of=f1, name="Press")
    mk_assignment(of=m2, to=s1)
    s2 = mk_section(name="Paint")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [s1.id, s2.id]
