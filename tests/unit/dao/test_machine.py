"""Unit tests for app/dao/machine.py.

Implements tests/unit/dao/machine.cases.md, one test per case. Real Postgres
session (`db` fixture). The only thing patched is the clock:
`app.dao.machine.utcnow` returns NOW in every test (spec: Externals).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/machine.helpers.md as its only view of this file.
"""
# ruff: noqa: SIM117, DTZ001  (prescribed by the cards: nested with, naive datetimes)
from datetime import datetime
from unittest.mock import patch  # commit spy of MCH-SD-08 and MCH-RS-12 only

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.machine import machine_dao
from app.models.enums import MachineEventTypeEnum
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.machine import MachineCreate, MachineUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_dao" (a module-level name, not a fixture)
dao = machine_dao

# Convention "IDLE, RUNNING, OFF, MAINTENANCE = the four members of MachineEventTypeEnum"
IDLE = MachineEventTypeEnum.IDLE
RUNNING = MachineEventTypeEnum.RUNNING
OFF = MachineEventTypeEnum.OFF
MAINTENANCE = MachineEventTypeEnum.MAINTENANCE

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0", "T1 ... T3", "NOW" (all naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
NOW = datetime(2026, 3, 1, 10, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (actors and the eleven standing rows)
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 creates the Given machines, U2 acts)
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def _factory(db, name, abbreviation, workspace_id, is_active=True, is_deleted=False):
    return _add(db, Factory(name=name, abbreviation=abbreviation, workspace_id=workspace_id,
                            is_active=is_active, is_deleted=is_deleted))


def _section(db, name, factory_id, workspace_id, is_active=True, is_deleted=False):
    return _add(db, FactorySection(name=name, factory_id=factory_id, workspace_id=workspace_id,
                                   is_active=is_active, is_deleted=is_deleted))


# Convention "F1, F2, F9, FD, FI" (standing factories; FD soft-deleted, FI inactive but live).
# Each fixture depends on the one before it, so the ids rise in the order written.
@pytest.fixture
def f1(db, w1):
    return _factory(db, "Factory One", "F1", w1.id)


@pytest.fixture
def f2(db, w1, f1):
    return _factory(db, "Factory Two", "F2", w1.id)


@pytest.fixture
def f9(db, w2, f2):
    return _factory(db, "Factory Nine", "F9", w2.id)


@pytest.fixture
def fd(db, w1, f9):
    return _factory(db, "Old Plant", "OP", w1.id, is_deleted=True)


@pytest.fixture
def fi(db, w1, fd):
    return _factory(db, "Idle Plant", "IP", w1.id, is_active=False)


# Convention "S1, S2, S3, SX, SI, S9" (standing sections; SX soft-deleted, SI inactive but live)
@pytest.fixture
def s1(db, w1, f1, fi):
    return _section(db, "Section One", f1.id, w1.id)


@pytest.fixture
def s2(db, w1, f1, s1):
    return _section(db, "Section Two", f1.id, w1.id)


@pytest.fixture
def s3(db, w1, f2, s2):
    return _section(db, "Section Three", f2.id, w1.id)


@pytest.fixture
def sx(db, w1, f1, s3):
    return _section(db, "Old Section", f1.id, w1.id, is_deleted=True)


@pytest.fixture
def si(db, w1, f1, sx):
    return _section(db, "Idle Section", f1.id, w1.id, is_active=False)


@pytest.fixture
def s9(db, w2, f9, si):
    return _section(db, "Section Nine", f9.id, w2.id)


# Convention "These eleven rows exist in every test and need no Given line" and
# Externals "app.dao.machine.utcnow is patched to return NOW in every test"
@pytest.fixture(autouse=True)
def standing_rows(db, monkeypatch, w1, w2, u1, u2, f1, f2, f9, fd, fi, s1, s2, s3, sx, si, s9):
    monkeypatch.setattr("app.dao.machine.utcnow", lambda: NOW)


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Conventions "machine" and "deleted" (said of a machine)
@pytest.fixture
def mk_machine(db, w1, u1, f1):
    """mk_machine(name=..., **columns) -> Machine. Keywords only.

    `deleted=True` is the Conventions word "deleted": is_deleted True,
    is_active False, deleted_at T0, deleted_by U1.id. `created_at` is left to
    the database unless the card gives it.
    """
    def _mk(*, name, deleted=False, **columns):
        fields = {
            "workspace_id": w1.id, "factory_id": f1.id, "name": name, "is_running": False,
            "model_number": None, "manufacturer": None, "note": None,
            "created_by": u1.id, "updated_by": None, "updated_at": None,
            "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None,
        }
        if deleted:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "assignment of M to S" (db.expire_all() right after the flush)
@pytest.fixture
def mk_assignment(db):
    """mk_assignment(of=<machine>, to=<section>) -> MachineSectionAssignment. Keywords only."""
    def _mk(*, of, to):
        row = _add(db, MachineSectionAssignment(workspace_id=of.workspace_id, machine_id=of.id,
                                                factory_section_id=to.id))
        db.expire_all()
        return row
    return _mk


# Convention "event of M"
@pytest.fixture
def mk_event(db):
    """mk_event(of=<machine>, created_at=..., metadata_json=..., **columns) -> MachineActivityEvent. Keywords only."""
    def _mk(*, of, created_at, metadata_json, **columns):
        fields = {
            "workspace_id": of.workspace_id, "machine_id": of.id, "event_type": "status_updated",
            "description": "status", "performed_by": None,
            "created_at": created_at, "metadata_json": metadata_json,
        }
        fields.update(columns)
        return _add(db, MachineActivityEvent(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__
           for model in (Machine, MachineSectionAssignment, MachineActivityEvent, Factory, FactorySection)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` from the database, or None if it is gone."""
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


# Convention "nothing written": row counts of the five tables, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "ids(result)" / "names(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "by_id(result, X)": the one element of result whose id == X.id
def by_id(result, row):
    (found,) = [m for m in result if m.id == row.id]
    return found


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in machine.helpers.md)
# --------------------------------------------------------------------------- #

def test_mch_gs_05__the_workspace_filter_follows_the_machine_not_the_section(db, w2, f9, s1, mk_machine, mk_assignment):
    """MCH-GS-05 — the workspace filter follows the machine, not the section.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)
    mk_assignment(of=m9, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [m9.id]


def test_mch_sd_01__a_live_machine_is_marked_deleted_with_the_clock_value_and_the_acting(db, u2, mk_machine):
    """MCH-SD-01 — a live machine is marked deleted with the clock value and the acting user.
    Rules: `soft_delete` R1, R5"""
    m1 = mk_machine(name="Press 4")

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    assert row.deleted_at == NOW
    # Then 4
    assert row.deleted_by == u2.id
    # Then 5
    assert count_rows(db, "machines") == 1


def test_mch_gf_24__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_machine):
    """MCH-GF-24 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 1"""
    m1 = mk_machine(name="Lathe")
    before = written(db)
    before_m1 = snap(db, m1)

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
    assert snap(db, m1) == before_m1


def test_mch_inh_13__a_refused_update_leaves_an_existing_assignment_pointing_at_its_old(db, s1, s2, mk_machine, mk_assignment):
    """MCH-INH-13 — a refused update leaves an existing assignment pointing at its old section.
    Rules: inherited R4"""
    m1 = mk_machine(name="Press")
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before_m1 = snap(db, m1)

    # Then 1
    with pytest.raises(AttributeError):
        dao.update(db, db_obj=m1, obj_in={"factory_section_id": s2.id})

    # Then 2
    assert snap(db, a1) == before_a1
    # Then 3
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert snap(db, m1) == before_m1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1


def test_mch_sa_72__the_newest_status_change_decides_the_machine_matches_its_newest_status(db, w1, mk_machine, mk_event):
    """MCH-SA-72 — the newest status change decides: the machine matches its newest status.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "IDLE"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert ids(result) == [m1.id]


# Revision 1 exemplar for `restore` (hand-written; not printed in machine.helpers.md,
# which points at MCH-SD-01 for the shape — the sheet is at its size limit).
def test_mch_rs_01__a_deleted_machine_is_made_live_again_and_its_deletion_stamp_is_cleared(db, mk_machine):
    """MCH-RS-01 — a deleted machine is made live again and its deletion stamp is cleared.
    Rules: `restore` R1, R5"""
    m1 = mk_machine(name="Press 4", deleted=True)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    # Then 4
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "machines") == 1


# --------------------------------------------------------------------------- #
# `Author: claude` cards (hand-written): bulk setup of 101 rows, the six
# non-strict BUG-343 order cards, and the savepoint + commit-spy card
# --------------------------------------------------------------------------- #

# Given "101 machines N1 … N101": Nk has name f"M{k:03d}" and is otherwise the default machine.
def mk_101(mk_machine, descending=False):
    """Insert N1 … N101 in that order (descending=True: N101 first, N1 last). Returns {k: Nk}."""
    order = range(101, 0, -1) if descending else range(1, 102)
    return {k: mk_machine(name=f"M{k:03d}") for k in order}


# Convention "Rolled back": spy that wraps (does not replace) db.commit.
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# Convention "FD made live again" (revision 1; `Author: claude` cards only): the
# standing row FD is changed directly, never through a factory DAO, then flushed.
# "re-read FD" is `reread(db, fd)`, "unchanged(FD)" is `snap(db, fd)`.
def fd_made_live_again(db, fd):
    fd.is_deleted = False
    fd.deleted_at = None
    fd.deleted_by = None
    db.flush()


def test_mch_gf_15__default_limit_returns_exactly_100_of_101_machines(db, w1, f1, mk_machine):
    """MCH-GF-15 — default limit returns exactly 100 of 101 machines.
    Rules: `get_by_factory` R4"""
    n = mk_101(mk_machine)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= {n[k].id for k in range(1, 102)}


def test_mch_gf_16__an_explicit_limit_of_101_returns_all_101_machines(db, w1, f1, mk_machine):
    """MCH-GF-16 — an explicit limit of 101 returns all 101 machines.
    Rules: `get_by_factory` R4"""
    n = mk_101(mk_machine)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == [n[k].id for k in range(1, 102)]


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gf_20__a_middle_window_holds_the_machine_that_is_second_by_name(db, w1, f1, mk_machine):
    """MCH-GF-20 — a middle window holds the machine that is second by name.
    Rules: `get_by_factory` R4, R6 [BUG-343]"""
    mk_machine(name="Zulu")
    mk_machine(name="apple")
    mk_machine(name="Mango")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert names(result) == ["Mango"]


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gf_26__machines_come_back_by_name_case_insensitive_ascending(db, w1, f1, mk_machine):
    """MCH-GF-26 — machines come back by name, case-insensitive ascending.
    Rules: `get_by_factory` R6 [BUG-343]"""
    mk_machine(name="Zulu")
    mk_machine(name="apple")
    mk_machine(name="Banana")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gf_27__names_that_differ_only_in_case_come_back_in_id_order(db, w1, f1, mk_machine):
    """MCH-GF-27 — names that differ only in case come back in id order.
    Rules: `get_by_factory` R6 [BUG-343]"""
    m1 = mk_machine(name="bolt")
    m2 = mk_machine(name="Zulu")
    m3 = mk_machine(name="Bolt")
    m4 = mk_machine(name="apple")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m4.id, m1.id, m3.id, m2.id]


def test_mch_gs_17__default_limit_returns_exactly_100_of_101_assigned_machines(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-17 — default limit returns exactly 100 of 101 assigned machines.
    Rules: `get_by_section` R5"""
    n = mk_101(mk_machine)
    for k in range(1, 102):
        mk_assignment(of=n[k], to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= {n[k].id for k in range(1, 102)}


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gs_21__a_middle_window_holds_the_machine_that_is_second_by_name(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-21 — a middle window holds the machine that is second by name.
    Rules: `get_by_section` R5, R7 [BUG-343]"""
    m1 = mk_machine(name="Zulu")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="apple")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Mango")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert names(result) == ["Mango"]


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gs_27__machines_come_back_by_name_case_insensitive_ascending(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-27 — machines come back by name, case-insensitive ascending.
    Rules: `get_by_section` R7 [BUG-343]"""
    m1 = mk_machine(name="Zulu")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="apple")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Banana")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


@pytest.mark.xfail(strict=False, reason="BUG-343: Section/factory machine list has no sort order")
def test_mch_gs_28__names_that_differ_only_in_case_come_back_in_id_order(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-28 — names that differ only in case come back in id order.
    Rules: `get_by_section` R7 [BUG-343]"""
    m1 = mk_machine(name="bolt")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Zulu")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Bolt")
    mk_assignment(of=m3, to=s1)
    m4 = mk_machine(name="apple")
    mk_assignment(of=m4, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m4.id, m1.id, m3.id, m2.id]


def test_mch_sd_08__the_delete_is_flushed_but_not_committed_a_rollback_makes_the_machine_live_again(db, u2, mk_machine):
    """MCH-SD-08 — the delete is flushed but not committed: a rollback makes the machine live again.
    Rules: `soft_delete` R5"""
    m1 = mk_machine(name="Lathe")
    with commit_spy(db) as spy:
        sp = db.begin_nested()

        result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

        # Then 1
        assert result is m1
        # Then 2
        row = reread(db, m1)
        assert row.is_deleted is True
        sp.rollback()
        # Then 3
        row = reread(db, m1)
        assert row.is_deleted is False
        assert row.is_active is True
        # Then 4
        assert row.deleted_at is None
        assert row.deleted_by is None
    # Then 5
    assert spy.call_count == 0


def test_mch_sa_116__default_limit_returns_the_first_100_of_101_machines_by_name(db, w1, mk_machine):
    """MCH-SA-116 — default limit returns the first 100 of 101 machines by name.
    Rules: `search_advanced` R17"""
    mk_101(mk_machine, descending=True)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].name == "M001"
    # Then 3
    assert result[99].name == "M100"
    # Then 4
    assert "M101" not in names(result)


def test_mch_sa_117__an_explicit_limit_of_101_returns_all_101_machines(db, w1, mk_machine):
    """MCH-SA-117 — an explicit limit of 101 returns all 101 machines.
    Rules: `search_advanced` R17"""
    mk_101(mk_machine, descending=True)

    result = dao.search_advanced(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].name == "M001"
    # Then 3
    assert result[100].name == "M101"


# --------------------------------------------------------------------------- #
# Revision 1 — `Author: claude` cards (hand-written): the standing row FD is
# changed directly (MCH-GF-30, GS-30, RS-16, RS-19, SA-128, SA-129), savepoint +
# commit spy (MCH-RS-12), a Given that runs `dao.soft_delete` (MCH-RS-20, RS-21)
# --------------------------------------------------------------------------- #

def test_mch_gf_30__once_the_factory_is_no_longer_deleted_its_machine_is_returned_again_unchanged(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-GF-30 — once the factory is no longer deleted its machine is returned again, unchanged.
    Rules: `get_by_factory` R3b"""
    mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id, is_running=True, model_number="P-4")
    ad = mk_assignment(of=md, to=s1)
    fd_made_live_again(db, fd)
    before = written(db)
    before_md = snap(db, md)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [md.id]
    # Then 2
    assert result[0].is_running is True
    # Then 3
    assert result[0].model_number == "P-4"
    # Then 4
    assert result[0].factory_section_id == s1.id
    # Then 5
    assert snap(db, md) == before_md
    # Then 6
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 7
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert row.updated_at is None
    # Then 9
    row_ad = reread(db, ad)
    assert row_ad.machine_id == md.id
    assert row_ad.factory_section_id == s1.id
    # Then 10
    assert written(db) == before


def test_mch_gs_30__once_the_factory_is_no_longer_deleted_its_machine_is_returned_again_still_assigned(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-GS-30 — once the factory is no longer deleted its machine is returned again, still assigned to the same section.
    Rules: `get_by_section` R3b"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    md = mk_machine(name="Press", factory_id=fd.id, is_running=True, model_number="P-4")
    ad = mk_assignment(of=md, to=s1)
    fd_made_live_again(db, fd)
    before_md = snap(db, md)
    before_ad = snap(db, ad)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, md.id]
    # Then 2
    assert by_id(result, md).factory_section_id == s1.id
    # Then 3
    assert by_id(result, md).factory_section_name == "Section One"
    # Then 4
    assert by_id(result, md).is_running is True
    # Then 5
    assert snap(db, md) == before_md
    # Then 6
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 7
    assert row.model_number == "P-4"
    assert row.updated_at is None
    # Then 8
    assert snap(db, ad) == before_ad
    # Then 9
    row_ad = reread(db, ad)
    assert row_ad.machine_id == md.id
    assert row_ad.factory_section_id == s1.id
    # Then 10
    assert count_rows(db, "machine_section_assignments") == 2


def test_mch_rs_12__the_restore_is_flushed_but_not_committed_a_rollback_makes_the_machine_deleted_again(db, u1, mk_machine):
    """MCH-RS-12 — the restore is flushed but not committed: a rollback makes the machine deleted again.
    Rules: `restore` R5"""
    m1 = mk_machine(name="Lathe", deleted=True)
    with commit_spy(db) as spy:
        sp = db.begin_nested()

        result = dao.restore(db, db_obj=m1)

        # Then 1
        assert result is m1
        # Then 2
        row = reread(db, m1)
        assert row.is_deleted is False
        assert row.is_active is True
        sp.rollback()
        # Then 3
        row = reread(db, m1)
        assert row.is_deleted is True
        assert row.is_active is False
        # Then 4
        assert row.deleted_at == T0
        # Then 5
        assert row.deleted_by == u1.id
    # Then 6
    assert spy.call_count == 0


def test_mch_rs_16__a_deleted_machine_of_a_soft_deleted_factory_is_restored_and_the_factory_row_is_not_touched(db, u1, fd, mk_machine):
    """MCH-RS-16 — a deleted machine of a soft-deleted factory is restored and the factory row is not touched.
    Rules: `restore` R7"""
    fd.deleted_at = T0
    fd.deleted_by = u1.id
    db.flush()
    md = mk_machine(name="Press", factory_id=fd.id, deleted=True)
    before_fd = snap(db, fd)

    result = dao.restore(db, db_obj=md)

    # Then 1
    assert result is md
    # Then 2
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.factory_id == fd.id
    # Then 5
    assert snap(db, fd) == before_fd
    # Then 6
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is True
    # Then 7
    assert row_fd.deleted_at == T0
    assert row_fd.deleted_by == u1.id
    # Then 8
    assert count_rows(db, "factories") == 5


def test_mch_rs_19__the_restored_machine_appears_in_the_three_lists_once_its_factory_is_no_longer_deleted(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-RS-19 — the restored machine appears in the three lists once its factory is no longer deleted.
    Rules: `restore` R7a (second sentence — holds today), R7"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    md = mk_machine(name="Press", factory_id=fd.id, deleted=True)
    mk_assignment(of=md, to=s1)

    result = dao.restore(db, db_obj=md)

    # Then 1
    assert result is md
    # Then 2
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    after_md = snap(db, md)
    fd_made_live_again(db, fd)
    # Then 3
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is False
    # Then 4
    assert ids(dao.search_advanced(db, workspace_id=w1.id)) == [m1.id, md.id]
    # Then 5
    assert ids(dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)) == [md.id]
    # Then 6
    assert sorted(ids(dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id))) == [m1.id, md.id]
    # Then 7
    assert snap(db, md) == after_md


def test_mch_rs_20__delete_then_restore_gives_back_the_same_value_in_every_column_except_updated_at(db, w1, u1, u2, f2, mk_machine):
    """MCH-RS-20 — delete then restore gives back the same value in every column except updated_at.
    Rules: `restore` R8, `soft_delete` R5"""
    m1 = mk_machine(name="Press 4", factory_id=f2.id, model_number="MX-1", manufacturer="Siemens", note="n1",
                    is_running=True, updated_by=u1.id, created_at=T1)
    before_m1 = snap(db, m1)
    dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    after_m1 = snap(db, m1)
    assert ({column: value for column, value in after_m1.items() if column != "updated_at"}
            == {column: value for column, value in before_m1.items() if column != "updated_at"})
    # Then 3
    row = reread(db, m1)
    assert row.name == "Press 4"
    assert row.factory_id == f2.id
    assert row.workspace_id == w1.id
    # Then 4
    assert row.created_by == u1.id
    assert row.updated_by == u1.id
    # Then 5
    assert row.model_number == "MX-1"
    assert row.manufacturer == "Siemens"
    assert row.note == "n1"
    # Then 6
    assert row.is_running is True
    assert row.created_at == T1
    # Then 7
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 8
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 9
    assert row.updated_at is not None


def test_mch_rs_21__delete_then_restore_keeps_the_same_assignment_row_and_the_machine_is_listed_again(db, w1, u2, f1, s1, mk_machine, mk_assignment):
    """MCH-RS-21 — delete then restore keeps the same assignment row and the machine is listed again where it was.
    Rules: `restore` R8, `soft_delete` R5"""
    m1 = mk_machine(name="Lathe")
    a1 = mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)
    before_a1 = snap(db, a1)
    dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s1.id
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 2
    # Then 6
    assert sorted(ids(dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id))) == [m1.id, m2.id]
    # Then 7
    assert sorted(ids(dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id))) == [m1.id, m2.id]
    # Then 8
    assert ids(dao.search_advanced(db, workspace_id=w1.id)) == [m1.id, m2.id]


def test_mch_sa_128__once_the_factory_is_no_longer_deleted_its_machine_is_listed_again_exactly_as_it_was(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-SA-128 — once the factory is no longer deleted its machine is listed again, exactly as it was.
    Rules: `search_advanced` R3c"""
    mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id, is_running=True, model_number="P-4")
    ad = mk_assignment(of=md, to=s1)
    fd_made_live_again(db, fd)
    before = written(db)
    before_md = snap(db, md)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Lathe", "Press"]
    # Then 2
    assert by_id(result, md).is_running is True
    # Then 3
    assert by_id(result, md).model_number == "P-4"
    # Then 4
    assert by_id(result, md).factory_section_id == s1.id
    # Then 5
    assert by_id(result, md).factory_section_name == "Section One"
    # Then 6
    assert snap(db, md) == before_md
    # Then 7
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 8
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 9
    assert row.updated_at is None
    # Then 10
    row_ad = reread(db, ad)
    assert row_ad.machine_id == md.id
    assert row_ad.factory_section_id == s1.id
    # Then 11
    assert written(db) == before


def test_mch_sa_129__once_the_factory_is_no_longer_deleted_its_id_works_as_the_factory_filter_again(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-SA-129 — once the factory is no longer deleted its id works as the factory filter again.
    Rules: `search_advanced` R3c, R4"""
    mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id, is_running=True, model_number="P-4")
    mk_assignment(of=md, to=s1)
    fd_made_live_again(db, fd)
    before_md = snap(db, md)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert ids(result) == [md.id]
    # Then 2
    assert result[0].is_running is True
    # Then 3
    assert result[0].model_number == "P-4"
    # Then 4
    assert result[0].factory_section_name == "Section One"
    # Then 5
    assert snap(db, md) == before_md
    # Then 6
    row = reread(db, md)
    assert row.factory_id == fd.id
    assert row.is_deleted is False


# MCH-SA-130 is a local-model card that the tool handed back (its text check compares
# the evaluated "\tbolt\n" with the card's source text and rejects the faithful test).
def test_mch_sa_130__a_tab_before_and_a_newline_after_the_search_text_are_removed_before_matching(db, w1, mk_machine):
    """MCH-SA-130 — a tab before and a newline after the search text are removed before matching.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="\tbolt\n")

    # Then 1
    assert ids(result) == [m1.id]


# --------------------------------------------------------------------------- #
# Local-model tests (one per `# [local-coder] <ID>` comment): the 15 trial
# cards first, then the rest in cases-file order
# --------------------------------------------------------------------------- #

# [local-coder] MCH-GF-04
def test_mch_gf_04__a_machine_of_another_workspace_carrying_this_factory_s_id_is_not(db, w1, w2, f1, mk_machine):
    """MCH-GF-04 — a machine of another workspace carrying this factory's id is not returned.
    Rules: `get_by_factory` R1"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Stray", workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-GF-14
def test_mch_gf_14__a_lookup_leaves_the_machine_of_a_soft_deleted_factory_untouched(db, w1, f1, fd, mk_machine):
    """MCH-GF-14 — a lookup leaves the machine of a soft-deleted factory untouched.
    Rules: `get_by_factory` R3b, R1"""
    m1 = mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id)
    before_md = snap(db, md)
    before = written(db)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert snap(db, md) == before_md
    # Then 3
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "machines") == 2


# [local-coder] MCH-GS-01
def test_mch_gs_01__returns_a_list_of_the_machines_assigned_to_that_section_each_once(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-01 — returns a list of the machines assigned to that section, each once.
    Rules: `get_by_section` R1, R6"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Drill")
    mk_assignment(of=m3, to=s2)
    mk_machine(name="Saw")

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [m1.id, m2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], Machine)


# [local-coder] MCH-GS-29
def test_mch_gs_29__every_returned_machine_reports_the_section_it_was_found_through(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-29 — every returned machine reports the section it was found through.
    Rules: `get_by_section` R8"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s2)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s2)
    m3 = mk_machine(name="Drill")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m2.id]
    # Then 2
    assert by_id(result, m1).factory_section_id == s2.id
    # Then 3
    assert by_id(result, m1).factory_section_name == "Section Two"
    # Then 4
    assert by_id(result, m2).factory_section_id == s2.id
    # Then 5
    assert by_id(result, m2).factory_section_name == "Section Two"


# [local-coder] MCH-SD-02
def test_mch_sd_02__no_other_column_of_the_machine_is_changed_and_a_running_machine_stays(db, u2, f2, u1, w1, mk_machine):
    """MCH-SD-02 — no other column of the machine is changed and a running machine stays running.
    Rules: `soft_delete` R2"""
    m1 = mk_machine(name="Press 4", factory_id=f2.id, model_number="MX-1", manufacturer="Siemens", note="n1", is_running=True, updated_by=u1.id, created_at=T1)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Press 4"
    assert row.factory_id == f2.id
    assert row.workspace_id == w1.id
    # Then 3
    assert row.model_number == "MX-1"
    assert row.manufacturer == "Siemens"
    assert row.note == "n1"
    # Then 4
    assert row.created_by == u1.id
    assert row.updated_by == u1.id
    # Then 5
    assert row.created_at == T1
    # Then 6
    assert row.is_running is True
    # Then 7
    assert row.updated_at is not None
    # Then 8
    assert row.is_deleted is True


# [local-coder] MCH-SD-04
def test_mch_sd_04__the_section_assignment_row_is_kept(db, u2, s1, mk_machine, mk_assignment):
    """MCH-SD-04 — the section assignment row is kept.
    Rules: `soft_delete` R3"""
    m1 = mk_machine(name="Press 4")
    a1 = mk_assignment(of=m1, to=s1)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s1.id
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 4
    row_a1 = reread(db, a1)
    assert row_a1.machine_id == m1.id
    assert row_a1.factory_section_id == s1.id
    # Then 5
    row_m1 = reread(db, m1)
    assert row_m1.is_deleted is True
    # Then 6
    assert row_m1.factory_section_id == s1.id


# [local-coder] MCH-SD-10
def test_mch_sd_10__a_deleted_by_that_is_no_profile_id_fails_on_flush_and_nothing_is_saved(db, mk_machine):
    """MCH-SD-10 — a deleted_by that is no profile id fails on flush and nothing is saved.
    Rules: `soft_delete` R7, Errors row 1"""
    m1 = mk_machine(name="Press 4")
    before_m1 = snap(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=m1, deleted_by=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert snap(db, m1) == before_m1
    # Then 4
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert row.updated_at is None
    # Then 7
    assert written(db) == before


# [local-coder] MCH-SA-40
def test_mch_sa_40__a_search_of_a_space_a_tab_and_a_newline_applies_no_search_filter(db, w1, mk_machine):
    """MCH-SA-40 — a search of a space, a tab and a newline applies no search filter.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    m2 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search=" \t\n")

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-50
def test_mch_sa_50__a_match_in_any_one_of_name_model_number_or_manufacturer_is_enough(db, w1, mk_machine):
    """MCH-SA-50 — a match in any one of name, model number or manufacturer is enough.
    Rules: `search_advanced` R9, R13a"""
    m1 = mk_machine(name="Bolt cutter")
    m2 = mk_machine(name="Lathe", model_number="BOLT-9")
    m3 = mk_machine(name="Press", manufacturer="Boltco")
    mk_machine(name="Drill", model_number="QR-7", manufacturer="Bosch")

    result = dao.search_advanced(db, workspace_id=w1.id, search="bolt")

    # Then 1
    assert ids(result) == [m1.id, m2.id, m3.id]


# [local-coder] MCH-SA-61
def test_mch_sa_61__has_model_number_true_keeps_machines_with_a_non_empty_model_number(db, w1, mk_machine):
    """MCH-SA-61 — has_model_number True keeps machines with a non-empty model number, spaces included.
    Rules: `search_advanced` R10"""
    m1 = mk_machine(name="Alpha", model_number="MX-1")
    mk_machine(name="Bravo")
    mk_machine(name="Charlie", model_number="")
    m4 = mk_machine(name="Delta", model_number="   ")

    result = dao.search_advanced(db, workspace_id=w1.id, has_model_number=True)

    # Then 1
    assert ids(result) == [m1.id, m4.id]


# [local-coder] MCH-SA-77
def test_mch_sa_77__a_machine_with_only_events_of_other_types_never_matches(db, w1, mk_machine, mk_event):
    """MCH-SA-77 — a machine with only events of other types never matches.
    Rules: `search_advanced` R12b [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"}, event_type="created")
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-123
def test_mch_sa_123__all_filters_combine_with_and_a_machine_failing_any_one_filter_is_left(db, w1, f1, f2, s1, s2, mk_machine, mk_assignment):
    """MCH-SA-123 — all filters combine with AND: a machine failing any one filter is left out.
    Rules: `search_advanced` R13a, R4, R5, R7, R9, R10, R11"""
    m1 = mk_machine(name="Bolt A", is_running=True, model_number="MX-1", manufacturer="Acme")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Bolt B", factory_id=f2.id, is_running=True, model_number="MX-1", manufacturer="Acme")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Bolt C", is_running=True, model_number="MX-1", manufacturer="Acme")
    mk_assignment(of=m3, to=s2)
    m4 = mk_machine(name="Bolt D", model_number="MX-1", manufacturer="Acme")
    mk_assignment(of=m4, to=s1)
    m5 = mk_machine(name="Nut E", is_running=True, model_number="MX-1", manufacturer="Acme")
    mk_assignment(of=m5, to=s1)
    m6 = mk_machine(name="Bolt F", is_running=True, manufacturer="Acme")
    mk_assignment(of=m6, to=s1)
    m7 = mk_machine(name="Bolt G", is_running=True, model_number="MX-1")
    mk_assignment(of=m7, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, factory_section_id=s1.id, is_running=True, search="bolt", has_model_number=True, has_manufacturer=True)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-127
def test_mch_sa_127__a_filter_a_created_at_descending_sort_and_paging_work_together(db, w1, mk_machine):
    """MCH-SA-127 — a filter, a created_at descending sort and paging work together.
    Rules: `search_advanced` R13a, R16, R17"""
    m1 = mk_machine(name="Alpha", is_running=True, created_at=T1)
    mk_machine(name="Bravo", created_at=T3)
    mk_machine(name="Charlie", is_running=True, created_at=T3)
    m4 = mk_machine(name="Delta", is_running=True, created_at=T2)

    result = dao.search_advanced(db, workspace_id=w1.id, is_running=True, sort_by="created_at", sort_dir="desc", skip=1, limit=2)

    # Then 1
    assert ids(result) == [m4.id, m1.id]


# [local-coder] MCH-INH-01
def test_mch_inh_01__create_with_a_dict_of_the_three_required_values_stores_a_machine_with(db, w1, f1):
    """MCH-INH-01 — create with a dict of the three required values stores a machine with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Press", "factory_id": f1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.factory_section_id is None
    # Then 3
    row = reread(db, result)
    assert row.name == "Press"
    assert row.workspace_id == w1.id
    assert row.factory_id == f1.id
    # Then 4
    assert row.is_running is False
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 5
    assert row.created_at is not None
    assert row.updated_at is None
    # Then 6
    assert row.model_number is None
    assert row.manufacturer is None
    assert row.note is None
    # Then 7
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert count_rows(db, "machines") == 1
    # Then 9
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MCH-INH-10
def test_mch_inh_10__update_with_a_dict_holding_a_section_id_raises_and_saves_nothing(db, s1, mk_machine):
    """MCH-INH-10 — update with a dict holding a section id raises and saves nothing.
    Rules: inherited R4, Errors row 1"""
    m1 = mk_machine(name="Press")
    before_m1 = snap(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.update(db, db_obj=m1, obj_in={"name": "B", "factory_section_id": s1.id})

    # Then 2
    assert snap(db, m1) == before_m1
    # Then 3
    row = reread(db, m1)
    assert row.name == "Press"
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert written(db) == before
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MCH-GF-01
def test_mch_gf_01__returns_a_list_of_the_machines_of_that_factory(db, w1, f1, f2, mk_machine):
    """MCH-GF-01 — returns a list of the machines of that factory.
    Rules: `get_by_factory` R1, R7"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Press")
    mk_machine(name="Drill", factory_id=f2.id)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [m1.id, m2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], Machine)


# [local-coder] MCH-GF-02
def test_mch_gf_02__a_call_for_the_other_factory_returns_only_that_factory_s_machine(db, w1, f2, mk_machine):
    """MCH-GF-02 — a call for the other factory returns only that factory's machine.
    Rules: `get_by_factory` R1"""
    mk_machine(name="Lathe")
    mk_machine(name="Press")
    m3 = mk_machine(name="Drill", factory_id=f2.id)

    result = dao.get_by_factory(db, factory_id=f2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m3.id]


# [local-coder] MCH-GF-03
def test_mch_gf_03__another_workspace_s_machine_is_not_returned_when_its_factory_id_is(db, w1, w2, f9, mk_machine):
    """MCH-GF-03 — another workspace's machine is not returned when its factory id is given.
    Rules: `get_by_factory` R1"""
    mk_machine(name="Lathe")
    mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-05
def test_mch_gf_05__a_call_for_the_other_workspace_returns_only_that_workspace_s_machine(db, w2, f9, mk_machine):
    """MCH-GF-05 — a call for the other workspace returns only that workspace's machine.
    Rules: `get_by_factory` R1"""
    mk_machine(name="Lathe")
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [m9.id]


# [local-coder] MCH-GF-06
def test_mch_gf_06__an_unknown_workspace_id_returns_an_empty_list(db, f1, mk_machine):
    """MCH-GF-06 — an unknown workspace id returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_machine(name="Lathe")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-07
def test_mch_gf_07__a_soft_deleted_machine_is_not_returned(db, w1, f1, mk_machine):
    """MCH-GF-07 — a soft-deleted machine is not returned.
    Rules: `get_by_factory` R2"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Press", deleted=True)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-GF-08
def test_mch_gf_08__an_inactive_live_machine_and_a_running_machine_are_returned(db, w1, f1, mk_machine):
    """MCH-GF-08 — an inactive live machine and a running machine are returned.
    Rules: `get_by_factory` R2"""
    m1 = mk_machine(name="Lathe", is_active=False)
    m2 = mk_machine(name="Press", is_running=True)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m2.id]


# [local-coder] MCH-GF-09
def test_mch_gf_09__a_factory_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_machine):
    """MCH-GF-09 — a factory id that does not exist returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_machine(name="Lathe")

    result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-10
def test_mch_gf_10__factory_id_0_returns_an_empty_list(db, w1, f2, mk_machine):
    """MCH-GF-10 — factory_id 0 returns an empty list.
    Rules: `get_by_factory` R3"""
    mk_machine(name="Lathe")
    mk_machine(name="Drill", factory_id=f2.id)

    result = dao.get_by_factory(db, factory_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-11
def test_mch_gf_11__a_factory_whose_only_machine_is_soft_deleted_returns_an_empty_list(db, w1, f2, mk_machine):
    """MCH-GF-11 — a factory whose only machine is soft-deleted returns an empty list.
    Rules: `get_by_factory` R3, R2"""
    mk_machine(name="Lathe")
    mk_machine(name="Drill", factory_id=f2.id, deleted=True)

    result = dao.get_by_factory(db, factory_id=f2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-12
def test_mch_gf_12__the_live_machine_of_a_soft_deleted_factory_is_not_returned(db, w1, fd, mk_machine):
    """MCH-GF-12 — the live machine of a soft-deleted factory is not returned.
    Rules: `get_by_factory` R3a [BUG-891]"""
    mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id)
    before_md = snap(db, md)

    result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 1
    assert snap(db, md) == before_md
    # Then 2
    assert result == []


# [local-coder] MCH-GF-13
def test_mch_gf_13__the_machine_of_a_live_but_inactive_factory_is_returned(db, w1, fi, mk_machine):
    """MCH-GF-13 — the machine of a live but inactive factory is returned.
    Rules: `get_by_factory` R3b"""
    mk_machine(name="Lathe")
    mi = mk_machine(name="Press", factory_id=fi.id)

    result = dao.get_by_factory(db, factory_id=fi.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [mi.id]


# [local-coder] MCH-GF-17
def test_mch_gf_17__a_soft_deleted_machine_does_not_use_up_a_place_in_the_page(db, w1, f1, mk_machine):
    """MCH-GF-17 — a soft-deleted machine does not use up a place in the page.
    Rules: `get_by_factory` R4, R2"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Mill", deleted=True)
    m3 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m3.id]


# [local-coder] MCH-GF-18
def test_mch_gf_18__limit_2_of_three_machines_returns_two_different_machines(db, w1, f1, mk_machine):
    """MCH-GF-18 — limit 2 of three machines returns two different machines.
    Rules: `get_by_factory` R4"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Mill")
    m3 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {m1.id, m2.id, m3.id}


# [local-coder] MCH-GF-19
def test_mch_gf_19__the_last_window_is_short(db, w1, f1, mk_machine):
    """MCH-GF-19 — the last window is short.
    Rules: `get_by_factory` R4"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Mill")
    m3 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [m1.id, m2.id, m3.id]


# [local-coder] MCH-GF-21
def test_mch_gf_21__limit_0_returns_an_empty_list(db, w1, f1, mk_machine):
    """MCH-GF-21 — limit 0 returns an empty list.
    Rules: `get_by_factory` R5"""
    mk_machine(name="Lathe")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-22
def test_mch_gf_22__skip_equal_to_the_number_of_matching_machines_returns_an_empty_list(db, w1, f1, mk_machine):
    """MCH-GF-22 — skip equal to the number of matching machines returns an empty list.
    Rules: `get_by_factory` R5"""
    mk_machine(name="Lathe")
    mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] MCH-GF-23
def test_mch_gf_23__skip_one_below_the_number_of_matching_machines_returns_one_machine(db, w1, f1, mk_machine):
    """MCH-GF-23 — skip one below the number of matching machines returns one machine.
    Rules: `get_by_factory` R5, R4"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [m1.id, m2.id]


# [local-coder] MCH-GF-25
def test_mch_gf_25__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_machine):
    """MCH-GF-25 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 2"""
    m1 = mk_machine(name="Lathe")
    before = written(db)
    before_m1 = snap(db, m1)

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
    assert snap(db, m1) == before_m1


# [local-coder] MCH-GF-28
def test_mch_gf_28__a_machine_with_an_assignment_and_one_without_are_each_returned_once(db, w1, f1, s1, mk_machine, mk_assignment):
    """MCH-GF-28 — a machine with an assignment and one without are each returned once.
    Rules: `get_by_factory` R7"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [m1.id, m2.id]


# [local-coder] MCH-GF-29
def test_mch_gf_29__section_id_and_name_are_readable_on_an_assigned_machine_and_none_on(db, w1, f1, s2, mk_machine, mk_assignment):
    """MCH-GF-29 — section id and name are readable on an assigned machine and None on an unassigned one.
    Rules: `get_by_factory` R8"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s2)
    m2 = mk_machine(name="Press")

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert by_id(result, m1).factory_section_id == s2.id
    # Then 2
    assert by_id(result, m1).factory_section_name == "Section Two"
    # Then 3
    assert by_id(result, m2).factory_section_id is None
    # Then 4
    assert by_id(result, m2).factory_section_name is None


# [local-coder] MCH-GS-02
def test_mch_gs_02__a_call_for_the_other_section_returns_only_that_section_s_machine(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-02 — a call for the other section returns only that section's machine.
    Rules: `get_by_section` R1"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Drill")
    mk_assignment(of=m2, to=s2)
    mk_machine(name="Saw")

    result = dao.get_by_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-GS-03
def test_mch_gs_03__a_section_with_no_assigned_machine_returns_an_empty_list(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-03 — a section with no assigned machine returns an empty list.
    Rules: `get_by_section` R3, R1"""
    mk_machine(name="Saw")
    m2 = mk_machine(name="Drill")
    mk_assignment(of=m2, to=s2)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-04
def test_mch_gs_04__a_machine_of_another_workspace_assigned_to_this_section_is_not(db, w1, w2, f9, s1, mk_machine, mk_assignment):
    """MCH-GS-04 — a machine of another workspace assigned to this section is not returned.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)
    mk_assignment(of=m9, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-GS-06
def test_mch_gs_06__an_unknown_workspace_id_returns_an_empty_list(db, s1, mk_machine, mk_assignment):
    """MCH-GS-06 — an unknown workspace id returns an empty list.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-07
def test_mch_gs_07__a_soft_deleted_machine_is_not_returned_although_its_assignment_still(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-07 — a soft-deleted machine is not returned although its assignment still exists.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press", deleted=True)
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 2


# [local-coder] MCH-GS-08
def test_mch_gs_08__an_inactive_live_machine_and_a_running_machine_are_returned(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-08 — an inactive live machine and a running machine are returned.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe", is_active=False)
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press", is_running=True)
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m2.id]


# [local-coder] MCH-GS-09
def test_mch_gs_09__a_section_id_that_does_not_exist_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-09 — a section id that does not exist returns an empty list.
    Rules: `get_by_section` R3"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-10
def test_mch_gs_10__factory_section_id_0_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-10 — factory_section_id 0 returns an empty list.
    Rules: `get_by_section` R3"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    mk_machine(name="Saw")

    result = dao.get_by_section(db, factory_section_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-11
def test_mch_gs_11__a_section_whose_only_assigned_machine_is_soft_deleted_returns_an(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-11 — a section whose only assigned machine is soft-deleted returns an empty list.
    Rules: `get_by_section` R3, R2"""
    m1 = mk_machine(name="Lathe", deleted=True)
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Drill")
    mk_assignment(of=m2, to=s2)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-12
def test_mch_gs_12__a_machine_whose_factory_is_soft_deleted_is_not_returned(db, w1, s1, fd, mk_machine, mk_assignment):
    """MCH-GS-12 — a machine whose factory is soft-deleted is not returned.
    Rules: `get_by_section` R3a [BUG-891]"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    md = mk_machine(name="Press", factory_id=fd.id)
    mk_assignment(of=md, to=s1)
    before_md = snap(db, md)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert snap(db, md) == before_md
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 2
    # Then 3
    assert ids(result) == [m1.id]


# [local-coder] MCH-GS-13
def test_mch_gs_13__a_machine_whose_factory_is_live_but_inactive_is_returned(db, w1, fi, s1, mk_machine, mk_assignment):
    """MCH-GS-13 — a machine whose factory is live but inactive is returned.
    Rules: `get_by_section` R3b"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    mi = mk_machine(name="Press", factory_id=fi.id)
    mk_assignment(of=mi, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, mi.id]


# [local-coder] MCH-GS-14
def test_mch_gs_14__a_lookup_leaves_the_machine_of_a_soft_deleted_factory_and_its(db, w1, fd, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-14 — a lookup leaves the machine of a soft-deleted factory and its assignment untouched.
    Rules: `get_by_section` R3b, R1"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s2)
    md = mk_machine(name="Press", factory_id=fd.id)
    mk_assignment(of=md, to=s1)
    before_md = snap(db, md)
    before = written(db)

    result = dao.get_by_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert snap(db, md) == before_md
    # Then 3
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 2


# [local-coder] MCH-GS-15
def test_mch_gs_15__a_soft_deleted_section_returns_an_empty_list_although_an_assignment(db, w1, sx, s1, mk_machine, mk_assignment):
    """MCH-GS-15 — a soft-deleted section returns an empty list although an assignment still points at it.
    Rules: `get_by_section` R4 [BUG-889]"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=sx)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=sx.id, workspace_id=w1.id)

    # Then 1
    assert count_rows(db, "machine_section_assignments") == 2
    # Then 2
    assert result == []


# [local-coder] MCH-GS-16
def test_mch_gs_16__a_live_but_inactive_section_returns_its_machines_and_the_assignment(db, w1, si, s1, mk_machine, mk_assignment):
    """MCH-GS-16 — a live but inactive section returns its machines and the assignment is not changed.
    Rules: `get_by_section` R4"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=si)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)
    before = written(db)

    result = dao.get_by_section(db, factory_section_id=si.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 2
    # Then 3
    assert written(db) == before


# [local-coder] MCH-GS-18
def test_mch_gs_18__a_soft_deleted_machine_does_not_use_up_a_place_in_the_page(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-18 — a soft-deleted machine does not use up a place in the page.
    Rules: `get_by_section` R5, R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Mill", deleted=True)
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Press")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m3.id]


# [local-coder] MCH-GS-19
def test_mch_gs_19__limit_2_of_three_assigned_machines_returns_two_different_machines(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-19 — limit 2 of three assigned machines returns two different machines.
    Rules: `get_by_section` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Mill")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Press")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {m1.id, m2.id, m3.id}


# [local-coder] MCH-GS-20
def test_mch_gs_20__the_last_window_is_short(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-20 — the last window is short.
    Rules: `get_by_section` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Mill")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Press")
    mk_assignment(of=m3, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [m1.id, m2.id, m3.id]


# [local-coder] MCH-GS-22
def test_mch_gs_22__limit_0_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-22 — limit 0 returns an empty list.
    Rules: `get_by_section` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-23
def test_mch_gs_23__skip_equal_to_the_number_of_assigned_machines_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-23 — skip equal to the number of assigned machines returns an empty list.
    Rules: `get_by_section` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] MCH-GS-24
def test_mch_gs_24__skip_one_below_the_number_of_assigned_machines_returns_one_machine(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-24 — skip one below the number of assigned machines returns one machine.
    Rules: `get_by_section` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [m1.id, m2.id]


# [local-coder] MCH-GS-25
def test_mch_gs_25__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-25 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_section` R5, Errors (negative `limit`, as `get_by_factory`)"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    before = written(db)
    before_m1 = snap(db, m1)

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
    assert snap(db, m1) == before_m1


# [local-coder] MCH-GS-26
def test_mch_gs_26__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, s1, mk_machine, mk_assignment):
    """MCH-GS-26 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_section` R5, Errors (negative `skip`, as `get_by_factory`)"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    before = written(db)
    before_m1 = snap(db, m1)

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
    assert snap(db, m1) == before_m1


# [local-coder] MCH-SD-03
def test_mch_sd_03__updated_by_is_not_stamped_and_a_stopped_machine_stays_stopped(db, u1, u2, mk_machine):
    """MCH-SD-03 — updated_by is not stamped and a stopped machine stays stopped.
    Rules: `soft_delete` R2"""
    m1 = mk_machine(name="Press 4")

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    assert row.is_running is False
    # Then 4
    assert row.model_number is None
    assert row.manufacturer is None
    assert row.note is None
    # Then 5
    assert row.created_by == u1.id
    # Then 6
    assert row.is_deleted is True


# [local-coder] MCH-SD-05
def test_mch_sd_05__an_already_deleted_machine_gets_a_new_deletion_stamp_without_an_error(db, u2, mk_machine):
    """MCH-SD-05 — an already deleted machine gets a new deletion stamp without an error.
    Rules: `soft_delete` R4"""
    m1 = mk_machine(name="Press 4", deleted=True)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.deleted_at == NOW
    # Then 3
    assert row.deleted_by == u2.id
    # Then 4
    assert row.is_deleted is True
    assert row.is_active is False


# [local-coder] MCH-SD-06
def test_mch_sd_06__after_the_delete_the_machine_is_gone_from_the_three_lists_in_the_same(db, w1, u2, f1, s1, mk_machine, mk_assignment):
    """MCH-SD-06 — after the delete the machine is gone from the three lists in the same session.
    Rules: `soft_delete` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert ids(dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)) == [m2.id]
    # Then 3
    assert ids(dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)) == [m2.id]
    # Then 4
    assert ids(dao.search_advanced(db, workspace_id=w1.id)) == [m2.id]


# [local-coder] MCH-SD-07
def test_mch_sd_07__after_the_delete_the_machine_is_still_found_by_the_raw_id_lookup(db, u2, w1, mk_machine):
    """MCH-SD-07 — after the delete the machine is still found by the raw id lookup.
    Rules: `soft_delete` R5"""
    m1 = mk_machine(name="Lathe")

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    assert dao.get_by_id_and_workspace(db, id=m1.id, workspace_id=w1.id).id == m1.id
    # Then 3
    assert dao.get_by_id_and_workspace(db, id=m1.id, workspace_id=w1.id).is_deleted is True


# [local-coder] MCH-SD-09
def test_mch_sd_09__a_machine_of_another_workspace_is_deleted_all_the_same(db, w2, f9, u2, mk_machine):
    """MCH-SD-09 — a machine of another workspace is deleted all the same.
    Rules: `soft_delete` R6"""
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)

    result = dao.soft_delete(db, db_obj=m9, deleted_by=u2.id)

    # Then 1
    assert result is m9
    # Then 2
    row = reread(db, m9)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert row.workspace_id == w2.id


# [local-coder] MCH-SD-11
def test_mch_sd_11__deleted_by_none_is_stored_as_null(db, mk_machine):
    """MCH-SD-11 — deleted_by None is stored as NULL.
    Rules: `soft_delete` R1 (Inputs: `deleted_by`)"""
    m1 = mk_machine(name="Press 4")

    result = dao.soft_delete(db, db_obj=m1, deleted_by=None)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.deleted_by is None
    # Then 3
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 4
    assert row.deleted_at == NOW


# [local-coder] MCH-SD-12
def test_mch_sd_12__only_that_machine_row_is_touched_and_no_activity_event_is_written(db, u2, mk_machine):
    """MCH-SD-12 — only that machine row is touched and no activity event is written.
    Rules: `soft_delete` Side effects, R2"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Press")
    before_m2 = snap(db, m2)
    before_written = written(db)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, m2) == before_m2
    # Then 4
    row = reread(db, m2)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 5
    assert written(db) == before_written
    # Then 6
    assert count_rows(db, "machines") == 2
    # Then 7
    assert count_rows(db, "machine_activity_events") == 0


# [local-coder] MCH-SD-13
def test_mch_sd_13__an_inactive_live_machine_is_deleted_like_any_other(db, u2, mk_machine):
    """MCH-SD-13 — an inactive live machine is deleted like any other.
    Rules: `soft_delete` R1"""
    m1 = mk_machine(name="Press 4", is_active=False)

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id


# [local-coder] MCH-SA-01
def test_mch_sa_01__with_no_filter_returns_a_list_of_the_workspace_s_live_machines_by(db, w1, mk_machine):
    """MCH-SA-01 — with no filter, returns a list of the workspace's live machines by name ascending.
    Rules: `search_advanced` R3, R13, R15"""
    m1 = mk_machine(name="Press")
    m2 = mk_machine(name="Drill")
    m3 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [m2.id, m3.id, m1.id]
    # Then 3
    assert isinstance(result[0], Machine)


# [local-coder] MCH-SA-02
def test_mch_sa_02__a_machine_of_another_workspace_is_not_returned(db, w1, w2, f9, mk_machine):
    """MCH-SA-02 — a machine of another workspace is not returned.
    Rules: `search_advanced` R1"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Lathe Two", workspace_id=w2.id, factory_id=f9.id)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-03
def test_mch_sa_03__a_call_for_the_other_workspace_returns_only_that_workspace_s_machine(db, w2, f9, mk_machine):
    """MCH-SA-03 — a call for the other workspace returns only that workspace's machine.
    Rules: `search_advanced` R1"""
    mk_machine(name="Lathe")
    m9 = mk_machine(name="Lathe Two", workspace_id=w2.id, factory_id=f9.id)

    result = dao.search_advanced(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [m9.id]


# [local-coder] MCH-SA-04
def test_mch_sa_04__another_workspace_s_machine_is_not_returned_when_its_factory_id_is(db, w1, w2, f9, mk_machine):
    """MCH-SA-04 — another workspace's machine is not returned when its factory id is the filter.
    Rules: `search_advanced` R1, R4"""
    mk_machine(name="Lathe")
    mk_machine(name="Lathe Two", workspace_id=w2.id, factory_id=f9.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f9.id)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-05
def test_mch_sa_05__a_machine_of_another_workspace_carrying_this_workspace_s_factory_id(db, w1, w2, f1, mk_machine):
    """MCH-SA-05 — a machine of another workspace carrying this workspace's factory id is not returned.
    Rules: `search_advanced` R1, R4"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Stray", workspace_id=w2.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-06
def test_mch_sa_06__a_machine_of_another_workspace_assigned_to_this_workspace_s_section(db, w1, w2, f9, s1, mk_machine, mk_assignment):
    """MCH-SA-06 — a machine of another workspace assigned to this workspace's section is not returned.
    Rules: `search_advanced` R1, R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)
    mk_assignment(of=m9, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=s1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-07
def test_mch_sa_07__a_machine_of_another_workspace_is_not_returned_when_the_search_text(db, w1, w2, f9, mk_machine):
    """MCH-SA-07 — a machine of another workspace is not returned when the search text matches it.
    Rules: `search_advanced` R1, R9"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Lathe Two", workspace_id=w2.id, factory_id=f9.id, model_number="LT-2", manufacturer="Lathex")

    result = dao.search_advanced(db, workspace_id=w1.id, search="lathe")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-08
def test_mch_sa_08__an_unknown_workspace_id_returns_an_empty_list(db, mk_machine):
    """MCH-SA-08 — an unknown workspace id returns an empty list.
    Rules: `search_advanced` R1"""
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-09
def test_mch_sa_09__a_soft_deleted_machine_is_not_returned(db, w1, mk_machine):
    """MCH-SA-09 — a soft-deleted machine is not returned.
    Rules: `search_advanced` R2"""
    m1 = mk_machine(name="Lathe")
    mk_machine(name="Press", deleted=True)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-10
def test_mch_sa_10__a_soft_deleted_machine_does_not_use_up_a_place_in_the_page(db, w1, mk_machine):
    """MCH-SA-10 — a soft-deleted machine does not use up a place in the page.
    Rules: `search_advanced` R2, R17"""
    mk_machine(name="Alpha", deleted=True)
    m2 = mk_machine(name="Bravo")
    mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-11
def test_mch_sa_11__a_soft_deleted_machine_is_not_returned_when_every_filter_matches_it(db, w1, f1, mk_machine):
    """MCH-SA-11 — a soft-deleted machine is not returned when every filter matches it.
    Rules: `search_advanced` R2"""
    mk_machine(name="Press", is_running=True, model_number="MX-1", deleted=True)
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, is_running=True, search="press", has_model_number=True)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-12
def test_mch_sa_12__an_inactive_live_machine_is_returned(db, w1, mk_machine):
    """MCH-SA-12 — an inactive live machine is returned.
    Rules: `search_advanced` R2"""
    m1 = mk_machine(name="Lathe", is_active=False)
    m2 = mk_machine(name="Press")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-13
def test_mch_sa_13__assigned_and_unassigned_machines_of_every_factory_are_each_returned(db, w1, f2, s1, s3, mk_machine, mk_assignment):
    """MCH-SA-13 — assigned and unassigned machines of every factory are each returned once.
    Rules: `search_advanced` R3"""
    m1 = mk_machine(name="Alpha")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Bravo")
    m3 = mk_machine(name="Charlie", factory_id=f2.id, is_running=True)
    mk_assignment(of=m3, to=s3)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [m1.id, m2.id, m3.id]


# [local-coder] MCH-SA-14
def test_mch_sa_14__section_id_and_name_are_readable_on_an_assigned_machine_and_none_on(db, w1, s2, mk_machine, mk_assignment):
    """MCH-SA-14 — section id and name are readable on an assigned machine and None on an unassigned one.
    Rules: `search_advanced` Returns, R3"""
    m1 = mk_machine(name="Alpha")
    mk_assignment(of=m1, to=s2)
    m2 = mk_machine(name="Bravo")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id, m2.id]
    # Then 2
    assert result[0].factory_section_id == s2.id
    # Then 3
    assert result[0].factory_section_name == "Section Two"
    # Then 4
    assert result[1].factory_section_id is None
    # Then 5
    assert result[1].factory_section_name is None


# [local-coder] MCH-SA-15
def test_mch_sa_15__the_machine_of_a_soft_deleted_factory_is_not_listed(db, w1, fd, mk_machine):
    """MCH-SA-15 — the machine of a soft-deleted factory is not listed.
    Rules: `search_advanced` R3a [BUG-890]"""
    mk_machine(name="Lathe")
    mk_machine(name="Press", factory_id=fd.id)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["Lathe"]


# [local-coder] MCH-SA-16
def test_mch_sa_16__the_id_of_a_soft_deleted_factory_as_the_filter_returns_an_empty_list(db, w1, fd, mk_machine):
    """MCH-SA-16 — the id of a soft-deleted factory as the filter returns an empty list.
    Rules: `search_advanced` R3a [BUG-890]"""
    mk_machine(name="Lathe")
    mk_machine(name="Press", factory_id=fd.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-17
def test_mch_sa_17__the_machine_of_a_soft_deleted_factory_does_not_use_up_a_place_in_the(db, w1, fd, mk_machine):
    """MCH-SA-17 — the machine of a soft-deleted factory does not use up a place in the page.
    Rules: `search_advanced` R3a [BUG-890]"""
    mk_machine(name="Lathe")
    mk_machine(name="Press", factory_id=fd.id)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc", limit=1)

    # Then 1
    assert names(result) == ["Lathe"]


# [local-coder] MCH-SA-18
def test_mch_sa_18__the_machine_of_a_soft_deleted_factory_is_not_returned_when_the_other(db, w1, s1, fd, mk_machine, mk_assignment):
    """MCH-SA-18 — the machine of a soft-deleted factory is not returned when the other filters match it.
    Rules: `search_advanced` R3a [BUG-890]"""
    m1 = mk_machine(name="Press One", is_running=True)
    mk_assignment(of=m1, to=s1)
    md = mk_machine(name="Press Two", factory_id=fd.id, is_running=True)
    mk_assignment(of=md, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=s1.id, is_running=True, search="press")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-19
def test_mch_sa_19__the_machine_of_a_live_but_inactive_factory_is_listed_like_any_other(db, w1, fi, mk_machine):
    """MCH-SA-19 — the machine of a live but inactive factory is listed like any other.
    Rules: `search_advanced` R3b"""
    m1 = mk_machine(name="Lathe")
    mi = mk_machine(name="Press", factory_id=fi.id)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id, mi.id]


# [local-coder] MCH-SA-20
def test_mch_sa_20__the_id_of_a_live_but_inactive_factory_works_as_the_factory_filter(db, w1, fi, mk_machine):
    """MCH-SA-20 — the id of a live but inactive factory works as the factory filter.
    Rules: `search_advanced` R3b, R4"""
    mk_machine(name="Lathe")
    mi = mk_machine(name="Press", factory_id=fi.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=fi.id)

    # Then 1
    assert ids(result) == [mi.id]


# [local-coder] MCH-SA-21
def test_mch_sa_21__searching_changes_nothing_the_machine_of_a_soft_deleted_factory_stays(db, w1, f1, fd, mk_machine):
    """MCH-SA-21 — searching changes nothing: the machine of a soft-deleted factory stays as it was.
    Rules: `search_advanced` R3b"""
    m1 = mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id)
    before_md = snap(db, md)
    before_m1 = snap(db, m1)
    before_written = written(db)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert snap(db, md) == before_md
    # Then 3
    row = reread(db, md)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 4
    assert snap(db, m1) == before_m1
    # Then 5
    assert written(db) == before_written
    # Then 6
    assert count_rows(db, "machines") == 2


# [local-coder] MCH-SA-22
def test_mch_sa_22__factory_id_filter_keeps_only_that_factory(db, w1, f2, mk_machine):
    """MCH-SA-22 — factory_id filter keeps only that factory.
    Rules: `search_advanced` R4"""
    m1 = mk_machine(name="Press", factory_id=f2.id)
    mk_machine(name="Lathe")
    m3 = mk_machine(name="Drill", factory_id=f2.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f2.id)

    # Then 1
    assert ids(result) == [m3.id, m1.id]


# [local-coder] MCH-SA-23
def test_mch_sa_23__a_factory_id_that_does_not_exist_returns_an_empty_list(db, w1, mk_machine):
    """MCH-SA-23 — a factory id that does not exist returns an empty list.
    Rules: `search_advanced` R4"""
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-24
def test_mch_sa_24__factory_id_0_filters_and_returns_an_empty_list(db, w1, f2, mk_machine):
    """MCH-SA-24 — factory_id 0 filters and returns an empty list.
    Rules: `search_advanced` R4"""
    mk_machine(name="Lathe")
    mk_machine(name="Drill", factory_id=f2.id)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-25
def test_mch_sa_25__explicit_none_for_every_optional_filter_applies_no_filter(db, w1, s1, f2, mk_machine, mk_assignment):
    """MCH-SA-25 — explicit None for every optional filter applies no filter.
    Rules: `search_advanced` R4, R5, R7, R8, R10, R11, R12"""
    m1 = mk_machine(name="Alpha")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Bravo", factory_id=f2.id, is_running=True, model_number="MX-1", manufacturer="Acme")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=None, factory_section_id=None, is_running=None, search=None, has_model_number=None, has_manufacturer=None, latest_event_type=None)

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-26
def test_mch_sa_26__factory_section_id_filter_keeps_only_the_machines_assigned_to_that(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-SA-26 — factory_section_id filter keeps only the machines assigned to that section.
    Rules: `search_advanced` R5"""
    m1 = mk_machine(name="Press")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Drill")
    mk_assignment(of=m2, to=s2)
    mk_machine(name="Saw")
    m4 = mk_machine(name="Lathe")
    mk_assignment(of=m4, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=s1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [m4.id, m1.id]
    # Then 3
    assert result[0].factory_section_id == s1.id


# [local-coder] MCH-SA-27
def test_mch_sa_27__a_section_id_that_does_not_exist_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-SA-27 — a section id that does not exist returns an empty list.
    Rules: `search_advanced` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    mk_machine(name="Saw")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-28
def test_mch_sa_28__factory_section_id_0_filters_and_returns_an_empty_list(db, w1, s1, mk_machine, mk_assignment):
    """MCH-SA-28 — factory_section_id 0 filters and returns an empty list.
    Rules: `search_advanced` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    mk_machine(name="Saw")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=0)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-29
def test_mch_sa_29__the_id_of_a_live_but_inactive_section_works_as_the_section_filter(db, w1, si, s1, mk_machine, mk_assignment):
    """MCH-SA-29 — the id of a live but inactive section works as the section filter.
    Rules: `search_advanced` R5"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=si)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=si.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-30
def test_mch_sa_30__factory_and_section_filters_must_both_match_the_machine(db, w1, f1, f2, s1, mk_machine, mk_assignment):
    """MCH-SA-30 — factory and section filters must both match the machine.
    Rules: `search_advanced` R6, R13a"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press", factory_id=f2.id)
    mk_assignment(of=m2, to=s1)
    mk_machine(name="Saw")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, factory_section_id=s1.id)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-31
def test_mch_sa_31__a_section_of_another_factory_than_factory_id_returns_an_empty_list(db, w1, f1, f2, s1, s3, mk_machine, mk_assignment):
    """MCH-SA-31 — a section of another factory than factory_id returns an empty list.
    Rules: `search_advanced` R6"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press", factory_id=f2.id)
    mk_assignment(of=m2, to=s3)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, factory_section_id=s3.id)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-32
def test_mch_sa_32__the_matching_factory_and_section_pair_of_the_other_factory_returns(db, w1, f2, s1, s3, mk_machine, mk_assignment):
    """MCH-SA-32 — the matching factory and section pair of the other factory returns its machine.
    Rules: `search_advanced` R6"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press", factory_id=f2.id)
    mk_assignment(of=m2, to=s3)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f2.id, factory_section_id=s3.id)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-33
def test_mch_sa_33__the_id_of_a_soft_deleted_section_as_the_filter_returns_an_empty_list(db, w1, sx, s1, mk_machine, mk_assignment):
    """MCH-SA-33 — the id of a soft-deleted section as the filter returns an empty list.
    Rules: `search_advanced` R6a [BUG-889]"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=sx)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=sx.id)

    # Then 1
    assert count_rows(db, "machine_section_assignments") == 2
    # Then 2
    assert result == []


# [local-coder] MCH-SA-34
def test_mch_sa_34__without_a_section_filter_a_machine_with_a_left_over_assignment_to_a(db, w1, s1, sx, mk_machine, mk_assignment):
    """MCH-SA-34 — without a section filter a machine with a left-over assignment to a deleted section is listed.
    Rules: `search_advanced` R6a"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=sx)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id, m2.id]
    # Then 2
    assert count_rows(db, "machine_section_assignments") == 2


# [local-coder] MCH-SA-35
def test_mch_sa_35__is_running_true_keeps_only_running_machines(db, w1, mk_machine):
    """MCH-SA-35 — is_running True keeps only running machines.
    Rules: `search_advanced` R7"""
    m1 = mk_machine(name="Press", is_running=True)
    mk_machine(name="Lathe")
    m3 = mk_machine(name="Drill", is_running=True)

    result = dao.search_advanced(db, workspace_id=w1.id, is_running=True)

    # Then 1
    assert ids(result) == [m3.id, m1.id]


# [local-coder] MCH-SA-36
def test_mch_sa_36__is_running_false_keeps_only_machines_that_are_not_running(db, w1, mk_machine):
    """MCH-SA-36 — is_running False keeps only machines that are not running.
    Rules: `search_advanced` R7"""
    mk_machine(name="Press", is_running=True)
    m2 = mk_machine(name="Lathe")
    m3 = mk_machine(name="Drill")

    result = dao.search_advanced(db, workspace_id=w1.id, is_running=False)

    # Then 1
    assert ids(result) == [m3.id, m2.id]


# [local-coder] MCH-SA-37
def test_mch_sa_37__search_none_applies_no_search_filter(db, w1, mk_machine):
    """MCH-SA-37 — search None applies no search filter.
    Rules: `search_advanced` R8"""
    m1 = mk_machine(name="Bolt cutter")
    m2 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search=None)

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-38
def test_mch_sa_38__an_empty_search_text_applies_no_search_filter(db, w1, mk_machine):
    """MCH-SA-38 — an empty search text applies no search filter.
    Rules: `search_advanced` R8"""
    m1 = mk_machine(name="Bolt cutter")
    m2 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="")

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-39
def test_mch_sa_39__a_search_of_three_spaces_applies_no_search_filter(db, w1, mk_machine):
    """MCH-SA-39 — a search of three spaces applies no search filter.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    m2 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-41
def test_mch_sa_41__spaces_around_the_search_text_are_removed_before_matching(db, w1, mk_machine):
    """MCH-SA-41 — spaces around the search text are removed before matching.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search=" bolt ")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-42
def test_mch_sa_42__leading_spaces_of_the_search_text_are_removed_before_matching(db, w1, mk_machine):
    """MCH-SA-42 — leading spaces of the search text are removed before matching.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="  bolt")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-43
def test_mch_sa_43__a_trailing_space_of_the_search_text_is_removed_before_matching(db, w1, mk_machine):
    """MCH-SA-43 — a trailing space of the search text is removed before matching.
    Rules: `search_advanced` R8 [BUG-892]"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="cutter ")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-44
def test_mch_sa_44__inner_whitespace_of_the_search_text_is_kept_and_matches_as_typed(db, w1, mk_machine):
    """MCH-SA-44 — inner whitespace of the search text is kept and matches as typed.
    Rules: `search_advanced` R8"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Boltcutter")

    result = dao.search_advanced(db, workspace_id=w1.id, search="bolt cutter")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-45
def test_mch_sa_45__two_inner_spaces_do_not_match_a_name_with_one_space(db, w1, mk_machine):
    """MCH-SA-45 — two inner spaces do not match a name with one space.
    Rules: `search_advanced` R8"""
    mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="bolt  cutter")

    # Then 1
    assert result == []


# [local-coder] MCH-SA-46
def test_mch_sa_46__the_search_is_case_insensitive_and_matches_anywhere_in_the_name(db, w1, mk_machine):
    """MCH-SA-46 — the search is case-insensitive and matches anywhere in the name.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Steel bolt")
    m2 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="BOLT")

    # Then 1
    assert ids(result) == [m2.id, m1.id]


# [local-coder] MCH-SA-47
def test_mch_sa_47__a_text_from_the_middle_of_the_name_matches(db, w1, mk_machine):
    """MCH-SA-47 — a text from the middle of the name matches.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="olt cut")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-48
def test_mch_sa_48__the_search_matches_the_model_number(db, w1, mk_machine):
    """MCH-SA-48 — the search matches the model number.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Lathe", model_number="MX-500")
    mk_machine(name="Press", model_number="QR-7")
    mk_machine(name="Drill")

    result = dao.search_advanced(db, workspace_id=w1.id, search="x-5")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-49
def test_mch_sa_49__the_search_matches_the_manufacturer(db, w1, mk_machine):
    """MCH-SA-49 — the search matches the manufacturer.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Lathe", manufacturer="Siemens")
    mk_machine(name="Press", manufacturer="Bosch")
    mk_machine(name="Drill")

    result = dao.search_advanced(db, workspace_id=w1.id, search="sie")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-51
def test_mch_sa_51__a_text_that_no_machine_contains_returns_an_empty_list_null_fields(db, w1, mk_machine):
    """MCH-SA-51 — a text that no machine contains returns an empty list, NULL fields included.
    Rules: `search_advanced` R9"""
    mk_machine(name="Lathe")
    mk_machine(name="Press", model_number="QR-7")

    result = dao.search_advanced(db, workspace_id=w1.id, search="sie")

    # Then 1
    assert result == []


# [local-coder] MCH-SA-52
def test_mch_sa_52__the_note_is_not_searched(db, w1, mk_machine):
    """MCH-SA-52 — the note is not searched.
    Rules: `search_advanced` R9"""
    mk_machine(name="Lathe", note="bolt spare")
    mk_machine(name="Press")

    result = dao.search_advanced(db, workspace_id=w1.id, search="bolt")

    # Then 1
    assert result == []


# [local-coder] MCH-SA-53
def test_mch_sa_53__the_factory_name_is_not_searched(db, w1, mk_machine):
    """MCH-SA-53 — the factory name is not searched.
    Rules: `search_advanced` R9"""
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, search="Factory")

    # Then 1
    assert result == []


# [local-coder] MCH-SA-54
def test_mch_sa_54__the_section_name_is_not_searched(db, w1, s1, mk_machine, mk_assignment):
    """MCH-SA-54 — the section name is not searched.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)

    result = dao.search_advanced(db, workspace_id=w1.id, search="Section")

    # Then 1
    assert result == []


# [local-coder] MCH-SA-55
def test_mch_sa_55__a_percent_sign_alone_finds_only_machines_that_contain_a_percent_sign(db, w1, mk_machine):
    """MCH-SA-55 — a percent sign alone finds only machines that contain a percent sign.
    Rules: `search_advanced` R9 [BUG-888]"""
    m1 = mk_machine(name="Lathe", model_number="50%")
    mk_machine(name="Press", model_number="QR-7")

    result = dao.search_advanced(db, workspace_id=w1.id, search="%")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-56
def test_mch_sa_56__a_percent_sign_inside_the_text_is_not_a_wildcard(db, w1, mk_machine):
    """MCH-SA-56 — a percent sign inside the text is not a wildcard.
    Rules: `search_advanced` R9 [BUG-888]"""
    m1 = mk_machine(name="Lathe", model_number="50%")
    mk_machine(name="Press", model_number="500")

    result = dao.search_advanced(db, workspace_id=w1.id, search="50%")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-57
def test_mch_sa_57__a_text_with_a_percent_sign_finds_the_machine_that_contains_it(db, w1, mk_machine):
    """MCH-SA-57 — a text with a percent sign finds the machine that contains it.
    Rules: `search_advanced` R9"""
    m1 = mk_machine(name="Lathe", model_number="50%")
    mk_machine(name="Press", model_number="QR-7")

    result = dao.search_advanced(db, workspace_id=w1.id, search="50%")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-58
def test_mch_sa_58__an_underscore_alone_finds_only_machines_that_contain_an_underscore(db, w1, mk_machine):
    """MCH-SA-58 — an underscore alone finds only machines that contain an underscore.
    Rules: `search_advanced` R9 [BUG-888]"""
    m1 = mk_machine(name="Lathe_2")
    mk_machine(name="Press")

    result = dao.search_advanced(db, workspace_id=w1.id, search="_")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-59
def test_mch_sa_59__an_underscore_inside_the_text_is_not_a_wildcard(db, w1, mk_machine):
    """MCH-SA-59 — an underscore inside the text is not a wildcard.
    Rules: `search_advanced` R9 [BUG-888]"""
    m1 = mk_machine(name="Lathe", manufacturer="ACME_1")
    mk_machine(name="Press", manufacturer="ACME-1")

    result = dao.search_advanced(db, workspace_id=w1.id, search="acme_1")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-60
def test_mch_sa_60__a_backslash_in_the_text_is_matched_literally(db, w1, mk_machine):
    """MCH-SA-60 — a backslash in the text is matched literally.
    Rules: `search_advanced` R9 [BUG-888]"""
    m1 = mk_machine(name="a\\b")
    mk_machine(name="ab")

    result = dao.search_advanced(db, workspace_id=w1.id, search="a\\b")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-62
def test_mch_sa_62__has_model_number_false_keeps_machines_whose_model_number_is_null_or(db, w1, mk_machine):
    """MCH-SA-62 — has_model_number False keeps machines whose model number is NULL or empty.
    Rules: `search_advanced` R10"""
    mk_machine(name="Alpha", model_number="MX-1")
    m2 = mk_machine(name="Bravo")
    m3 = mk_machine(name="Charlie", model_number="")
    mk_machine(name="Delta", model_number="   ")

    result = dao.search_advanced(db, workspace_id=w1.id, has_model_number=False)

    # Then 1
    assert ids(result) == [m2.id, m3.id]


# [local-coder] MCH-SA-63
def test_mch_sa_63__has_manufacturer_true_keeps_machines_with_a_non_empty_manufacturer(db, w1, mk_machine):
    """MCH-SA-63 — has_manufacturer True keeps machines with a non-empty manufacturer, spaces included.
    Rules: `search_advanced` R11"""
    m1 = mk_machine(name="Alpha", manufacturer="Acme")
    mk_machine(name="Bravo")
    mk_machine(name="Charlie", manufacturer="")
    m4 = mk_machine(name="Delta", manufacturer="   ")

    result = dao.search_advanced(db, workspace_id=w1.id, has_manufacturer=True)

    # Then 1
    assert ids(result) == [m1.id, m4.id]


# [local-coder] MCH-SA-64
def test_mch_sa_64__has_manufacturer_false_keeps_machines_whose_manufacturer_is_null_or(db, w1, mk_machine):
    """MCH-SA-64 — has_manufacturer False keeps machines whose manufacturer is NULL or empty.
    Rules: `search_advanced` R11"""
    mk_machine(name="Alpha", manufacturer="Acme")
    m2 = mk_machine(name="Bravo")
    m3 = mk_machine(name="Charlie", manufacturer="")
    mk_machine(name="Delta", manufacturer="   ")

    result = dao.search_advanced(db, workspace_id=w1.id, has_manufacturer=False)

    # Then 1
    assert ids(result) == [m2.id, m3.id]


# [local-coder] MCH-SA-65
def test_mch_sa_65__has_model_number_true_with_has_manufacturer_false_looks_at_each(db, w1, mk_machine):
    """MCH-SA-65 — has_model_number True with has_manufacturer False looks at each column on its own.
    Rules: `search_advanced` R11, R10, R13a"""
    mk_machine(name="Alpha", model_number="MX-1", manufacturer="Acme")
    m2 = mk_machine(name="Bravo", model_number="MX-2")
    mk_machine(name="Charlie", manufacturer="Bosch")
    mk_machine(name="Delta")

    result = dao.search_advanced(db, workspace_id=w1.id, has_model_number=True, has_manufacturer=False)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-66
def test_mch_sa_66__has_model_number_false_with_has_manufacturer_true_looks_at_each(db, w1, mk_machine):
    """MCH-SA-66 — has_model_number False with has_manufacturer True looks at each column on its own.
    Rules: `search_advanced` R11, R10, R13a"""
    mk_machine(name="Alpha", model_number="MX-1", manufacturer="Acme")
    mk_machine(name="Bravo", model_number="MX-2")
    m3 = mk_machine(name="Charlie", manufacturer="Bosch")
    mk_machine(name="Delta")

    result = dao.search_advanced(db, workspace_id=w1.id, has_model_number=False, has_manufacturer=True)

    # Then 1
    assert ids(result) == [m3.id]


# [local-coder] MCH-SA-67
def test_mch_sa_67__latest_event_type_running_returns_the_machine_whose_latest_status_is(db, w1, mk_machine, mk_event):
    """MCH-SA-67 — latest_event_type RUNNING returns the machine whose latest status is RUNNING.
    Rules: `search_advanced` R12 [BUG-886], Errors row 3"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "IDLE"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "OFF"})
    m4 = mk_machine(name="Delta")
    mk_event(of=m4, created_at=T1, metadata_json={"status": "MAINTENANCE"})
    mk_machine(name="Echo")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-68
def test_mch_sa_68__latest_event_type_idle_returns_the_machine_whose_latest_status_is_idle(db, w1, mk_machine, mk_event):
    """MCH-SA-68 — latest_event_type IDLE returns the machine whose latest status is IDLE.
    Rules: `search_advanced` R12 [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "IDLE"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "OFF"})
    m4 = mk_machine(name="Delta")
    mk_event(of=m4, created_at=T1, metadata_json={"status": "MAINTENANCE"})
    mk_machine(name="Echo")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-69
def test_mch_sa_69__latest_event_type_off_returns_the_machine_whose_latest_status_is_off(db, w1, mk_machine, mk_event):
    """MCH-SA-69 — latest_event_type OFF returns the machine whose latest status is OFF.
    Rules: `search_advanced` R12 [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "IDLE"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "OFF"})
    m4 = mk_machine(name="Delta")
    mk_event(of=m4, created_at=T1, metadata_json={"status": "MAINTENANCE"})
    mk_machine(name="Echo")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=OFF)

    # Then 1
    assert ids(result) == [m3.id]


# [local-coder] MCH-SA-70
def test_mch_sa_70__latest_event_type_maintenance_returns_the_machine_whose_latest_status(db, w1, mk_machine, mk_event):
    """MCH-SA-70 — latest_event_type MAINTENANCE returns the machine whose latest status is MAINTENANCE.
    Rules: `search_advanced` R12 [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "IDLE"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "OFF"})
    m4 = mk_machine(name="Delta")
    mk_event(of=m4, created_at=T1, metadata_json={"status": "MAINTENANCE"})
    mk_machine(name="Echo")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=MAINTENANCE)

    # Then 1
    assert ids(result) == [m4.id]


# [local-coder] MCH-SA-71
def test_mch_sa_71__without_a_status_filter_machines_with_several_status_events_are_each(db, w1, mk_machine, mk_event):
    """MCH-SA-71 — without a status filter, machines with several status events are each listed once.
    Rules: `search_advanced` R12, R3"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "IDLE"})
    m2 = mk_machine(name="Bravo")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-73
def test_mch_sa_73__the_newest_status_change_decides_the_machine_does_not_match_an_older(db, w1, mk_machine, mk_event):
    """MCH-SA-73 — the newest status change decides: the machine does not match an older status.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "IDLE"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-74
def test_mch_sa_74__latest_goes_by_created_at_not_by_the_order_of_insertion(db, w1, mk_machine, mk_event):
    """MCH-SA-74 — "latest" goes by created_at, not by the order of insertion.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T2, metadata_json={"status": "IDLE"})
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T3, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-75
def test_mch_sa_75__on_a_created_at_tie_the_status_change_with_the_greater_id_decides(db, w1, mk_machine, mk_event):
    """MCH-SA-75 — on a created_at tie the status change with the greater id decides.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "OFF"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=OFF)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-76
def test_mch_sa_76__on_a_created_at_tie_the_status_change_with_the_lower_id_does_not_match(db, w1, mk_machine, mk_event):
    """MCH-SA-76 — on a created_at tie the status change with the lower id does not match.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "OFF"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-78
def test_mch_sa_78__a_newer_event_of_another_type_does_not_replace_the_latest_status(db, w1, mk_machine, mk_event):
    """MCH-SA-78 — a newer event of another type does not replace the latest status.
    Rules: `search_advanced` R12b [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "OFF"}, event_type="updated")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-79
def test_mch_sa_79__the_status_in_a_newer_event_of_another_type_is_not_matched(db, w1, mk_machine, mk_event):
    """MCH-SA-79 — the status in a newer event of another type is not matched.
    Rules: `search_advanced` R12b [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "OFF"}, event_type="updated")

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=OFF)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-80
def test_mch_sa_80__a_latest_status_change_without_metadata_matches_nothing_and_the_older(db, w1, mk_machine, mk_event):
    """MCH-SA-80 — a latest status change without metadata matches nothing and the older one is not used.
    Rules: `search_advanced` R12c [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json=None)
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-81
def test_mch_sa_81__a_latest_status_change_without_a_status_key_matches_nothing_and_the(db, w1, mk_machine, mk_event):
    """MCH-SA-81 — a latest status change without a "status" key matches nothing and the older one is not used.
    Rules: `search_advanced` R12c [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"note": "x"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-82
def test_mch_sa_82__a_status_change_recorded_in_another_workspace_is_not_counted(db, w1, w2, mk_machine, mk_event):
    """MCH-SA-82 — a status change recorded in another workspace is not counted.
    Rules: `search_advanced` R12d [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "IDLE"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"}, workspace_id=w2.id)

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-83
def test_mch_sa_83__the_status_of_a_change_recorded_in_another_workspace_is_not_matched(db, w1, w2, mk_machine, mk_event):
    """MCH-SA-83 — the status of a change recorded in another workspace is not matched.
    Rules: `search_advanced` R12d [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "IDLE"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"}, workspace_id=w2.id)

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-84
def test_mch_sa_84__two_newest_status_changes_with_the_same_status_list_the_machine_once(db, w1, mk_machine, mk_event):
    """MCH-SA-84 — two newest status changes with the same status list the machine once.
    Rules: `search_advanced` R12e [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-85
def test_mch_sa_85__the_status_filter_combines_with_the_factory_filter(db, w1, f1, f2, mk_machine, mk_event):
    """MCH-SA-85 — the status filter combines with the factory filter.
    Rules: `search_advanced` R12e [BUG-886], R13a"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo", factory_id=f2.id)
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "IDLE"})

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-86
def test_mch_sa_86__the_status_filter_combines_with_the_search_text(db, w1, mk_machine, mk_event):
    """MCH-SA-86 — the status filter combines with the search text.
    Rules: `search_advanced` R12e [BUG-886], R13a"""
    m1 = mk_machine(name="Bolt cutter")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Lathe")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})
    m3 = mk_machine(name="Bolt press")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "IDLE"})

    result = dao.search_advanced(db, workspace_id=w1.id, search="bolt", latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-87
def test_mch_sa_87__the_status_filter_is_sorted_and_paged_like_any_other_result(db, w1, mk_machine, mk_event):
    """MCH-SA-87 — the status filter is sorted and paged like any other result.
    Rules: `search_advanced` R12e [BUG-886], R17"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})
    m3 = mk_machine(name="Charlie")
    mk_event(of=m3, created_at=T1, metadata_json={"status": "RUNNING"})
    m4 = mk_machine(name="Delta")
    mk_event(of=m4, created_at=T1, metadata_json={"status": "IDLE"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING, sort_dir="desc", skip=1, limit=1)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-88
def test_mch_sa_88__with_the_status_filter_a_machine_of_another_workspace_is_not_returned(db, w1, w2, f9, mk_machine, mk_event):
    """MCH-SA-88 — with the status filter a machine of another workspace is not returned.
    Rules: `search_advanced` R1, R12 [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)
    mk_event(of=m9, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-89
def test_mch_sa_89__with_the_status_filter_a_soft_deleted_machine_is_not_returned(db, w1, mk_machine, mk_event):
    """MCH-SA-89 — with the status filter a soft-deleted machine is not returned.
    Rules: `search_advanced` R2, R12 [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    m2 = mk_machine(name="Bravo", deleted=True)
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=RUNNING)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-90
def test_mch_sa_90__sort_by_name_with_sort_dir_asc_sorts_by_name_ascending(db, w1, mk_machine):
    """MCH-SA-90 — sort_by "name" with sort_dir "asc" sorts by name ascending.
    Rules: `search_advanced` R13, R15"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="name", sort_dir="asc")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-91
def test_mch_sa_91__sort_by_created_at_puts_the_earliest_created_machine_first(db, w1, mk_machine):
    """MCH-SA-91 — sort_by "created_at" puts the earliest created machine first.
    Rules: `search_advanced` R13, R16"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="created_at")

    # Then 1
    assert ids(result) == [m3.id, m1.id, m2.id]


# [local-coder] MCH-SA-92
def test_mch_sa_92__sort_by_maintenance_date_sorts_by_name_without_an_error(db, w1, mk_machine):
    """MCH-SA-92 — sort_by "maintenance_date" sorts by name without an error.
    Rules: `search_advanced` R13"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="maintenance_date")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-93
def test_mch_sa_93__sort_by_createdat_sorts_by_name_without_an_error(db, w1, mk_machine):
    """MCH-SA-93 — sort_by "createdAt" sorts by name without an error.
    Rules: `search_advanced` R13"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="createdAt")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-94
def test_mch_sa_94__an_empty_sort_by_sorts_by_name_without_an_error(db, w1, mk_machine):
    """MCH-SA-94 — an empty sort_by sorts by name without an error.
    Rules: `search_advanced` R13"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-95
def test_mch_sa_95__sort_by_created_at_in_upper_case_sorts_by_name(db, w1, mk_machine):
    """MCH-SA-95 — sort_by "CREATED_AT" in upper case sorts by name.
    Rules: `search_advanced` R13"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="CREATED_AT")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-96
def test_mch_sa_96__an_unknown_sort_by_with_sort_dir_desc_sorts_by_name_descending(db, w1, mk_machine):
    """MCH-SA-96 — an unknown sort_by with sort_dir "desc" sorts by name descending.
    Rules: `search_advanced` R13, R15"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="createdAt", sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m3.id, m2.id]


# [local-coder] MCH-SA-97
def test_mch_sa_97__names_of_mixed_case_sort_case_insensitively_ascending(db, w1, mk_machine):
    """MCH-SA-97 — names of mixed case sort case-insensitively, ascending.
    Rules: `search_advanced` R14"""
    mk_machine(name="Zulu")
    mk_machine(name="apple")
    mk_machine(name="Banana")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["apple", "Banana", "Zulu"]


# [local-coder] MCH-SA-98
def test_mch_sa_98__names_of_mixed_case_sort_case_insensitively_descending(db, w1, mk_machine):
    """MCH-SA-98 — names of mixed case sort case-insensitively, descending.
    Rules: `search_advanced` R14, R15"""
    mk_machine(name="Zulu")
    mk_machine(name="apple")
    mk_machine(name="Banana")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc")

    # Then 1
    assert names(result) == ["Zulu", "Banana", "apple"]


# [local-coder] MCH-SA-99
def test_mch_sa_99__ascending_names_that_differ_only_in_case_come_back_in_id_order(db, w1, mk_machine):
    """MCH-SA-99 — ascending, names that differ only in case come back in id order.
    Rules: `search_advanced` R14 [BUG-887]"""
    m1 = mk_machine(name="Bolt")
    m2 = mk_machine(name="bolt")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-100
def test_mch_sa_100__descending_names_that_differ_only_in_case_come_back_in_id_order(db, w1, mk_machine):
    """MCH-SA-100 — descending, names that differ only in case come back in id order.
    Rules: `search_advanced` R14 [BUG-887]"""
    m1 = mk_machine(name="bolt")
    m2 = mk_machine(name="Bolt")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m2.id]


# [local-coder] MCH-SA-101
def test_mch_sa_101__ascending_identical_names_come_back_in_id_order(db, w1, mk_machine):
    """MCH-SA-101 — ascending, identical names come back in id order.
    Rules: `search_advanced` R14"""
    m1 = mk_machine(name="Bolt")
    m2 = mk_machine(name="Bolt")
    m3 = mk_machine(name="Apex")

    result = dao.search_advanced(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m3.id, m1.id, m2.id]


# [local-coder] MCH-SA-102
def test_mch_sa_102__descending_identical_names_still_come_back_in_ascending_id_order(db, w1, mk_machine):
    """MCH-SA-102 — descending, identical names still come back in ascending id order.
    Rules: `search_advanced` R14, R15"""
    m1 = mk_machine(name="Bolt")
    m2 = mk_machine(name="Bolt")
    m3 = mk_machine(name="Apex")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m2.id, m3.id]


# [local-coder] MCH-SA-103
def test_mch_sa_103__sort_dir_desc_sorts_by_name_descending(db, w1, mk_machine):
    """MCH-SA-103 — sort_dir "desc" sorts by name descending.
    Rules: `search_advanced` R15"""
    m1 = mk_machine(name="Press")
    m2 = mk_machine(name="Drill")
    m3 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m3.id, m2.id]


# [local-coder] MCH-SA-104
def test_mch_sa_104__sort_dir_desc_in_upper_case_sorts_ascending(db, w1, mk_machine):
    """MCH-SA-104 — sort_dir "DESC" in upper case sorts ascending.
    Rules: `search_advanced` R15"""
    m1 = mk_machine(name="Press")
    m2 = mk_machine(name="Drill")
    m3 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="DESC")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-105
def test_mch_sa_105__sort_dir_descending_sorts_ascending(db, w1, mk_machine):
    """MCH-SA-105 — sort_dir "descending" sorts ascending.
    Rules: `search_advanced` R15"""
    m1 = mk_machine(name="Press")
    m2 = mk_machine(name="Drill")
    m3 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="descending")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-106
def test_mch_sa_106__an_empty_sort_dir_sorts_ascending(db, w1, mk_machine):
    """MCH-SA-106 — an empty sort_dir sorts ascending.
    Rules: `search_advanced` R15"""
    m1 = mk_machine(name="Press")
    m2 = mk_machine(name="Drill")
    m3 = mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-107
def test_mch_sa_107__sort_by_created_at_descending_puts_the_earliest_created_machine_last(db, w1, mk_machine):
    """MCH-SA-107 — sort_by "created_at" descending puts the earliest created machine last.
    Rules: `search_advanced` R16, R15"""
    m1 = mk_machine(name="Press", created_at=T2)
    m2 = mk_machine(name="Drill", created_at=T3)
    m3 = mk_machine(name="Lathe", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="created_at", sort_dir="desc")

    # Then 1
    assert ids(result) == [m2.id, m1.id, m3.id]


# [local-coder] MCH-SA-108
def test_mch_sa_108__ascending_by_created_at_machines_created_at_the_same_time_come_back(db, w1, mk_machine):
    """MCH-SA-108 — ascending by created_at, machines created at the same time come back in id order.
    Rules: `search_advanced` R16"""
    m1 = mk_machine(name="Zulu", created_at=T2)
    m2 = mk_machine(name="Mango", created_at=T1)
    m3 = mk_machine(name="Apex", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="created_at")

    # Then 1
    assert ids(result) == [m2.id, m3.id, m1.id]


# [local-coder] MCH-SA-109
def test_mch_sa_109__descending_by_created_at_machines_created_at_the_same_time_still_come(db, w1, mk_machine):
    """MCH-SA-109 — descending by created_at, machines created at the same time still come back in ascending id order.
    Rules: `search_advanced` R16"""
    m1 = mk_machine(name="Zulu", created_at=T2)
    m2 = mk_machine(name="Mango", created_at=T1)
    m3 = mk_machine(name="Apex", created_at=T1)

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="created_at", sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m2.id, m3.id]


# [local-coder] MCH-SA-110
def test_mch_sa_110__machines_inserted_in_one_transaction_share_created_at_and_come_back(db, w1, mk_machine):
    """MCH-SA-110 — machines inserted in one transaction share created_at and come back in id order.
    Rules: `search_advanced` R16"""
    m1 = mk_machine(name="Zulu")
    m2 = mk_machine(name="Mango")
    m3 = mk_machine(name="Apex")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_by="created_at", sort_dir="desc")

    # Then 1
    assert ids(result) == [m1.id, m2.id, m3.id]


# [local-coder] MCH-SA-111
def test_mch_sa_111__first_window_of_two(db, w1, mk_machine):
    """MCH-SA-111 — first window of two.
    Rules: `search_advanced` R17"""
    mk_machine(name="Echo")
    m2 = mk_machine(name="Alpha")
    mk_machine(name="Delta")
    m4 = mk_machine(name="Bravo")
    mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert ids(result) == [m2.id, m4.id]


# [local-coder] MCH-SA-112
def test_mch_sa_112__second_window_of_two_continues_without_repeat_or_gap(db, w1, mk_machine):
    """MCH-SA-112 — second window of two continues without repeat or gap.
    Rules: `search_advanced` R17"""
    mk_machine(name="Echo")
    mk_machine(name="Alpha")
    m3 = mk_machine(name="Delta")
    mk_machine(name="Bravo")
    m5 = mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert ids(result) == [m5.id, m3.id]


# [local-coder] MCH-SA-113
def test_mch_sa_113__last_window_is_short(db, w1, mk_machine):
    """MCH-SA-113 — last window is short.
    Rules: `search_advanced` R17"""
    m1 = mk_machine(name="Echo")
    mk_machine(name="Alpha")
    mk_machine(name="Delta")
    mk_machine(name="Bravo")
    mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, skip=4, limit=2)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-114
def test_mch_sa_114__skip_and_limit_are_applied_after_filtering(db, w1, f1, f2, mk_machine):
    """MCH-SA-114 — skip and limit are applied after filtering.
    Rules: `search_advanced` R17, R4"""
    mk_machine(name="Alpha")
    mk_machine(name="Bravo", factory_id=f2.id)
    m3 = mk_machine(name="Charlie")
    mk_machine(name="Delta", factory_id=f2.id)
    mk_machine(name="Echo")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [m3.id]


# [local-coder] MCH-SA-115
def test_mch_sa_115__skip_and_limit_are_applied_after_ordering(db, w1, mk_machine):
    """MCH-SA-115 — skip and limit are applied after ordering.
    Rules: `search_advanced` R17, R15"""
    mk_machine(name="Echo")
    mk_machine(name="Alpha")
    m3 = mk_machine(name="Delta")
    mk_machine(name="Bravo")
    m5 = mk_machine(name="Charlie")

    result = dao.search_advanced(db, workspace_id=w1.id, sort_dir="desc", skip=1, limit=2)

    # Then 1
    assert ids(result) == [m3.id, m5.id]


# [local-coder] MCH-SA-118
def test_mch_sa_118__limit_0_returns_an_empty_list(db, w1, mk_machine):
    """MCH-SA-118 — limit 0 returns an empty list.
    Rules: `search_advanced` R18"""
    mk_machine(name="Lathe")

    result = dao.search_advanced(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-119
def test_mch_sa_119__skip_equal_to_the_number_of_matching_machines_returns_an_empty_list(db, w1, mk_machine):
    """MCH-SA-119 — skip equal to the number of matching machines returns an empty list.
    Rules: `search_advanced` R18"""
    mk_machine(name="Lathe")
    mk_machine(name="Press")

    result = dao.search_advanced(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] MCH-SA-120
def test_mch_sa_120__skip_one_below_the_number_of_matching_machines_returns_the_last(db, w1, mk_machine):
    """MCH-SA-120 — skip one below the number of matching machines returns the last machine.
    Rules: `search_advanced` R18, R17"""
    mk_machine(name="Lathe")
    m2 = mk_machine(name="Press")

    result = dao.search_advanced(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [m2.id]


# [local-coder] MCH-SA-121
def test_mch_sa_121__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_machine):
    """MCH-SA-121 — negative limit is rejected by the database and nothing changes.
    Rules: `search_advanced` R18, Errors row 1"""
    m1 = mk_machine(name="Lathe")
    before = written(db)
    before_m1 = snap(db, m1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.search_advanced(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [local-coder] MCH-SA-122
def test_mch_sa_122__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_machine):
    """MCH-SA-122 — negative skip is rejected by the database and nothing changes.
    Rules: `search_advanced` R18, Errors row 2"""
    m1 = mk_machine(name="Lathe")
    before = written(db)
    before_m1 = snap(db, m1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.search_advanced(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, m1) == before_m1


# [local-coder] MCH-SA-124
def test_mch_sa_124__the_three_search_alternatives_are_one_group_a_match_in_another(db, w1, f1, f2, mk_machine):
    """MCH-SA-124 — the three search alternatives are one group: a match in another factory is not returned.
    Rules: `search_advanced` R13a, R9, R4"""
    m1 = mk_machine(name="Bolt cutter")
    mk_machine(name="Lathe", factory_id=f2.id, model_number="BOLT-9")
    mk_machine(name="Press", factory_id=f2.id, manufacturer="Boltco")
    mk_machine(name="Drill")

    result = dao.search_advanced(db, workspace_id=w1.id, factory_id=f1.id, search="bolt")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-125
def test_mch_sa_125__the_search_alternatives_stay_one_group_next_to_the_soft_delete_filter(db, w1, mk_machine):
    """MCH-SA-125 — the search alternatives stay one group next to the soft-delete filter and is_running.
    Rules: `search_advanced` R13a, R9, R2, R7"""
    m1 = mk_machine(name="Bolt cutter", is_running=True)
    mk_machine(name="Lathe", manufacturer="Boltco")
    mk_machine(name="Press", is_running=True, manufacturer="Boltco", deleted=True)
    mk_machine(name="Drill", is_running=True)

    result = dao.search_advanced(db, workspace_id=w1.id, is_running=True, search="bolt")

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-SA-126
def test_mch_sa_126__section_and_is_running_filters_combine_with_and(db, w1, s1, s2, mk_machine, mk_assignment):
    """MCH-SA-126 — section and is_running filters combine with AND.
    Rules: `search_advanced` R13a, R5, R7"""
    m1 = mk_machine(name="Alpha", is_running=True)
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Bravo")
    mk_assignment(of=m2, to=s1)
    m3 = mk_machine(name="Charlie", is_running=True)
    mk_assignment(of=m3, to=s2)
    mk_machine(name="Delta", is_running=True)

    result = dao.search_advanced(db, workspace_id=w1.id, factory_section_id=s1.id, is_running=True)

    # Then 1
    assert ids(result) == [m1.id]


# [local-coder] MCH-INH-02
def test_mch_inh_02__create_with_a_machinecreate_schema_raises_and_adds_no_machine(db, f1):
    """MCH-INH-02 — create with a MachineCreate schema raises and adds no machine.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.create(db, obj_in=MachineCreate(name="Press", factory_id=f1.id))

    # Then 2
    assert written(db) == before
    # Then 3
    assert count_rows(db, "machines") == 0


# [local-coder] MCH-INH-03
def test_mch_inh_03__create_with_a_dict_holding_factory_section_id_none_raises_and_adds_no(db, w1, f1):
    """MCH-INH-03 — create with a dict holding factory_section_id None raises and adds no machine.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.create(db, obj_in={"workspace_id": w1.id, "name": "Press", "factory_id": f1.id, "factory_section_id": None})

    # Then 2
    assert written(db) == before
    # Then 3
    assert count_rows(db, "machines") == 0


# [local-coder] MCH-INH-04
def test_mch_inh_04__create_with_a_dict_holding_a_real_section_id_raises_and_adds_no(db, w1, f1, s1):
    """MCH-INH-04 — create with a dict holding a real section id raises and adds no machine or assignment.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.create(db, obj_in={"workspace_id": w1.id, "name": "Press", "factory_id": f1.id, "factory_section_id": s1.id})

    # Then 2
    assert written(db) == before
    # Then 3
    assert count_rows(db, "machines") == 0
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MCH-INH-05
def test_mch_inh_05__update_with_a_dict_of_real_columns_sets_them(db, u2, f1, mk_machine):
    """MCH-INH-05 — update with a dict of real columns sets them.
    Rules: inherited R3"""
    m1 = mk_machine(name="Press")

    result = dao.update(db, db_obj=m1, obj_in={"name": "B", "updated_by": u2.id})

    # Then 1
    assert result.id == m1.id
    # Then 2
    row = reread(db, m1)
    assert row.name == "B"
    assert row.updated_by == u2.id
    # Then 3
    assert row.updated_at is not None
    # Then 4
    assert row.factory_id == f1.id
    assert row.is_running is False


# [local-coder] MCH-INH-06
def test_mch_inh_06__update_with_a_dict_sets_is_running(db, mk_machine):
    """MCH-INH-06 — update with a dict sets is_running.
    Rules: inherited R3"""
    m1 = mk_machine(name="Press")

    result = dao.update(db, db_obj=m1, obj_in={"is_running": True})

    # Then 1
    assert result.id == m1.id
    # Then 2
    row = reread(db, m1)
    assert row.is_running is True
    # Then 3
    assert row.name == "Press"
    assert row.updated_by is None


# [local-coder] MCH-INH-07
def test_mch_inh_07__update_with_the_current_value_issues_no_update_and_leaves_updated_at(db, mk_machine):
    """MCH-INH-07 — update with the current value issues no UPDATE and leaves updated_at empty.
    Rules: inherited R3"""
    m1 = mk_machine(name="Press")

    result = dao.update(db, db_obj=m1, obj_in={"name": "Press"})

    # Then 1
    assert result.id == m1.id
    # Then 2
    row = reread(db, m1)
    assert row.name == "Press"
    # Then 3
    assert row.updated_at is None


# [local-coder] MCH-INH-08
def test_mch_inh_08__update_with_a_machineupdate_that_does_not_set_factory_section_id(db, s1, mk_machine, mk_assignment):
    """MCH-INH-08 — update with a MachineUpdate that does not set factory_section_id applies the other field.
    Rules: inherited R3"""
    m1 = mk_machine(name="Press")
    a1 = mk_assignment(of=m1, to=s1)

    result = dao.update(db, db_obj=m1, obj_in=MachineUpdate(name="B"))

    # Then 1
    assert result.id == m1.id
    # Then 2
    row = reread(db, m1)
    assert row.name == "B"
    # Then 3
    row_a1 = reread(db, a1)
    assert row_a1.factory_section_id == s1.id
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MCH-INH-09
def test_mch_inh_09__update_with_a_machineupdate_whose_factory_section_id_is_none_applies(db, s1, mk_machine, mk_assignment):
    """MCH-INH-09 — update with a MachineUpdate whose factory_section_id is None applies the other field.
    Rules: inherited R3"""
    m1 = mk_machine(name="Press")
    a1 = mk_assignment(of=m1, to=s1)

    result = dao.update(db, db_obj=m1, obj_in=MachineUpdate(name="B", factory_section_id=None))

    # Then 1
    assert result.id == m1.id
    # Then 2
    row = reread(db, m1)
    assert row.name == "B"
    # Then 3
    row_a1 = reread(db, a1)
    assert row_a1.factory_section_id == s1.id
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MCH-INH-11
def test_mch_inh_11__update_with_a_dict_holding_factory_section_id_none_raises_and_saves(db, mk_machine):
    """MCH-INH-11 — update with a dict holding factory_section_id None raises and saves nothing.
    Rules: inherited R4, Errors row 1"""
    m1 = mk_machine(name="Press")
    before_m1 = snap(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.update(db, db_obj=m1, obj_in={"name": "B", "factory_section_id": None})

    # Then 2
    assert snap(db, m1) == before_m1
    # Then 3
    row = reread(db, m1)
    assert row.name == "Press"
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert written(db) == before


# [local-coder] MCH-INH-12
def test_mch_inh_12__update_with_a_machineupdate_whose_factory_section_id_is_a_number(db, s1, mk_machine):
    """MCH-INH-12 — update with a MachineUpdate whose factory_section_id is a number raises and saves nothing.
    Rules: inherited R4, Errors row 1"""
    m1 = mk_machine(name="Press")
    before_m1 = snap(db, m1)
    before = written(db)

    # Then 1
    with pytest.raises(AttributeError):
        dao.update(db, db_obj=m1, obj_in=MachineUpdate(name="B", factory_section_id=s1.id))

    # Then 2
    assert snap(db, m1) == before_m1
    # Then 3
    row = reread(db, m1)
    assert row.name == "Press"
    # Then 4
    assert row.updated_at is None
    # Then 5
    assert written(db) == before
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 0


# [local-coder] MCH-INH-14
def test_mch_inh_14__get_returns_a_soft_deleted_machine(db, mk_machine):
    """MCH-INH-14 — get returns a soft-deleted machine.
    Rules: inherited R5"""
    m1 = mk_machine(name="Press", deleted=True)

    result = dao.get(db, m1.id)

    # Then 1
    assert result.id == m1.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] MCH-INH-15
def test_mch_inh_15__get_returns_the_machine_of_a_soft_deleted_factory(db, fd, mk_machine):
    """MCH-INH-15 — get returns the machine of a soft-deleted factory.
    Rules: inherited R5"""
    md = mk_machine(name="Press", factory_id=fd.id)

    result = dao.get(db, md.id)

    # Then 1
    assert result.id == md.id
    # Then 2
    assert result.factory_id == fd.id


# [local-coder] MCH-INH-16
def test_mch_inh_16__get_by_id_and_workspace_returns_a_soft_deleted_machine(db, w1, mk_machine):
    """MCH-INH-16 — get_by_id_and_workspace returns a soft-deleted machine.
    Rules: inherited R5"""
    m1 = mk_machine(name="Press", deleted=True)

    result = dao.get_by_id_and_workspace(db, id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == m1.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] MCH-INH-17
def test_mch_inh_17__get_by_id_and_workspace_returns_the_machine_of_a_soft_deleted_factory(db, w1, fd, mk_machine):
    """MCH-INH-17 — get_by_id_and_workspace returns the machine of a soft-deleted factory.
    Rules: inherited R5"""
    md = mk_machine(name="Press", factory_id=fd.id)

    result = dao.get_by_id_and_workspace(db, id=md.id, workspace_id=w1.id)

    # Then 1
    assert result.id == md.id
    # Then 2
    assert result.factory_id == fd.id


# [local-coder] MCH-INH-18
def test_mch_inh_18__get_by_workspace_returns_soft_deleted_machines_and_machines_of_a_soft(db, w1, fd, w2, f9, mk_machine):
    """MCH-INH-18 — get_by_workspace returns soft-deleted machines and machines of a soft-deleted factory.
    Rules: inherited R5"""
    m1 = mk_machine(name="Lathe")
    m2 = mk_machine(name="Press", deleted=True)
    md = mk_machine(name="Drill", factory_id=fd.id)
    mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [m1.id, m2.id, md.id]


# --------------------------------------------------------------------------- #
# Revision 1 — local-model tests, in the order the tool wrote them
# --------------------------------------------------------------------------- #

# [local-coder] MCH-GF-31
def test_mch_gf_31__a_lookup_leaves_the_section_assignment_of_a_soft_deleted_factory_s(db, w1, f1, fd, s1, mk_machine, mk_assignment):
    """MCH-GF-31 — a lookup leaves the section assignment of a soft-deleted factory's machine untouched.
    Rules: `get_by_factory` R3b"""
    m1 = mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id)
    ad = mk_assignment(of=md, to=s1)
    before_ad = snap(db, ad)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert snap(db, ad) == before_ad
    # Then 3
    row = reread(db, ad)
    assert row.machine_id == md.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 1


# [local-coder] MCH-GS-31
def test_mch_gs_31__a_lookup_leaves_the_assignment_row_of_a_soft_deleted_factory_s(db, w1, fd, s1, s2, mk_machine, mk_assignment):
    """MCH-GS-31 — a lookup leaves the assignment row of a soft-deleted factory's machine as it was.
    Rules: `get_by_section` R3b"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s2)
    md = mk_machine(name="Press", factory_id=fd.id)
    ad = mk_assignment(of=md, to=s1)

    before_ad = snap(db, ad)

    result = dao.get_by_section(db, factory_section_id=s2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [m1.id]
    # Then 2
    assert snap(db, ad) == before_ad
    # Then 3
    row = reread(db, ad)
    assert row.machine_id == md.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert count_rows(db, "machine_section_assignments") == 2


# [local-coder] MCH-RS-02
def test_mch_rs_02__no_other_column_of_the_machine_is_changed_and_a_running_machine_comes(db, u1, f2, w1, mk_machine):
    """MCH-RS-02 — no other column of the machine is changed and a running machine comes back running.
    Rules: `restore` R2"""
    m1 = mk_machine(name="Press 4", factory_id=f2.id, model_number="MX-1", manufacturer="Siemens", note="n1", is_running=True, created_at=T1, deleted=True)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.name == "Press 4"
    assert row.factory_id == f2.id
    assert row.workspace_id == w1.id
    # Then 3
    assert row.model_number == "MX-1"
    assert row.manufacturer == "Siemens"
    assert row.note == "n1"
    # Then 4
    assert row.created_by == u1.id
    # Then 5
    assert row.created_at == T1
    # Then 6
    assert row.is_running is True
    # Then 7
    assert row.updated_at is not None
    # Then 8
    assert row.is_deleted is False


# [local-coder] MCH-RS-03
def test_mch_rs_03__a_stopped_machine_comes_back_stopped_and_its_empty_texts_stay_empty(db, u1, w1, f1, mk_machine):
    """MCH-RS-03 — a stopped machine comes back stopped and its empty texts stay empty.
    Rules: `restore` R2"""
    m1 = mk_machine(name="Press 4", deleted=True)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_running is False
    # Then 3
    assert row.model_number is None
    assert row.manufacturer is None
    assert row.note is None
    # Then 4
    assert row.name == "Press 4"
    assert row.factory_id == f1.id
    assert row.workspace_id == w1.id
    # Then 5
    assert row.created_by == u1.id
    # Then 6
    assert row.is_deleted is False


# [local-coder] MCH-RS-04
def test_mch_rs_04__updated_by_keeps_the_value_it_had(db, u2, mk_machine):
    """MCH-RS-04 — updated_by keeps the value it had.
    Rules: `restore` R2a (Q8)"""
    m1 = mk_machine(name="Press 4", updated_by=u2.id, deleted=True)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by == u2.id
    # Then 3
    assert row.is_deleted is False


# [local-coder] MCH-RS-05
def test_mch_rs_05__an_empty_updated_by_stays_empty_nobody_is_recorded_as_having_restored(db, mk_machine):
    """MCH-RS-05 — an empty updated_by stays empty: nobody is recorded as having restored.
    Rules: `restore` R2a (Q8)"""
    m1 = mk_machine(name="Press 4", deleted=True)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.updated_by is None
    # Then 3
    assert row.is_deleted is False


# [local-coder] MCH-RS-06
def test_mch_rs_06__no_activity_entry_is_written_and_no_other_table_is_touched(db, mk_machine, mk_event):
    """MCH-RS-06 — no activity entry is written and no other table is touched.
    Rules: `restore` R2a (Q8), Side effects"""
    m1 = mk_machine(name="Press 4", deleted=True)
    mk_event(of=m1, created_at=T0, metadata_json=None, event_type="deactivated")
    before = written(db)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is False
    # Then 3
    assert count_rows(db, "machine_activity_events") == 1
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "machines") == 1


# [local-coder] MCH-RS-07
def test_mch_rs_07__the_section_assignment_of_the_restored_machine_is_the_same_row_as(db, s1, mk_machine, mk_assignment):
    """MCH-RS-07 — the section assignment of the restored machine is the same row as before.
    Rules: `restore` R3"""
    m1 = mk_machine(name="Press 4", deleted=True)
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id == s1.id
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 6
    row = reread(db, m1)
    assert row.is_deleted is False
    # Then 7
    assert row.factory_section_id == s1.id


# [local-coder] MCH-RS-08
def test_mch_rs_08__a_machine_without_an_assignment_still_has_none_after_the_restore(db, s1, mk_machine, mk_assignment):
    """MCH-RS-08 — a machine without an assignment still has none after the restore.
    Rules: `restore` R3"""
    m1 = mk_machine(name="Press 4", deleted=True)
    m2 = mk_machine(name="Lathe")
    mk_assignment(of=m2, to=s1)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    assert result.factory_section_id is None
    # Then 3
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 4
    row = reread(db, m1)
    assert row.is_deleted is False
    # Then 5
    assert row.factory_section_id is None


# [local-coder] MCH-RS-09
def test_mch_rs_09__a_machine_that_is_already_live_and_active_is_left_exactly_as_it_is(db, mk_machine):
    """MCH-RS-09 — a machine that is already live and active is left exactly as it is, with no UPDATE.
    Rules: `restore` R4"""
    m1 = mk_machine(name="Press 4")
    before_m1 = snap(db, m1)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    assert snap(db, m1) == before_m1
    # Then 3
    row = reread(db, m1)
    assert row.updated_at is None
    # Then 4
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "machines") == 1


# [local-coder] MCH-RS-10
def test_mch_rs_10__a_live_but_inactive_machine_is_made_active_and_stays_not_deleted(db, mk_machine):
    """MCH-RS-10 — a live but inactive machine is made active and stays not deleted.
    Rules: `restore` R4"""
    m1 = mk_machine(name="Press 4", is_active=False)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_active is True
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert row.updated_at is not None


# [local-coder] MCH-RS-11
def test_mch_rs_11__after_the_restore_the_machine_is_back_in_the_three_lists_in_the_same(db, w1, s1, f1, mk_machine, mk_assignment):
    """MCH-RS-11 — after the restore the machine is back in the three lists in the same session.
    Rules: `restore` R5"""
    m1 = mk_machine(name="Lathe", deleted=True)
    mk_assignment(of=m1, to=s1)
    m2 = mk_machine(name="Press")
    mk_assignment(of=m2, to=s1)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    assert sorted(ids(dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id))) == [m1.id, m2.id]
    # Then 3
    assert sorted(ids(dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id))) == [m1.id, m2.id]
    # Then 4
    assert ids(dao.search_advanced(db, workspace_id=w1.id)) == [m1.id, m2.id]


# [local-coder] MCH-RS-13
def test_mch_rs_13__a_machine_of_another_workspace_is_restored_all_the_same(db, w2, f9, mk_machine):
    """MCH-RS-13 — a machine of another workspace is restored all the same.
    Rules: `restore` R6"""
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id, deleted=True)

    result = dao.restore(db, db_obj=m9)

    # Then 1
    assert result is m9
    # Then 2
    row = reread(db, m9)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.workspace_id == w2.id
    assert row.factory_id == f9.id


# [local-coder] MCH-RS-14
def test_mch_rs_14__a_second_deleted_machine_of_the_same_factory_stays_deleted(db, u1, mk_machine):
    """MCH-RS-14 — a second deleted machine of the same factory stays deleted.
    Rules: `restore` R6"""
    m1 = mk_machine(name="Lathe", deleted=True)
    m2 = mk_machine(name="Press", deleted=True)
    before_m2 = snap(db, m2)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row_m1 = reread(db, m1)
    assert row_m1.is_deleted is False
    # Then 3
    assert snap(db, m2) == before_m2
    # Then 4
    row_m2 = reread(db, m2)
    assert row_m2.is_deleted is True
    assert row_m2.is_active is False
    # Then 5
    assert row_m2.deleted_at == T0
    assert row_m2.deleted_by == u1.id
    # Then 6
    assert row_m2.updated_at is None
    # Then 7
    assert count_rows(db, "machines") == 2


# [local-coder] MCH-RS-15
def test_mch_rs_15__a_deleted_machine_of_another_factory_and_a_live_machine_are_not(db, f2, mk_machine):
    """MCH-RS-15 — a deleted machine of another factory and a live machine are not touched.
    Rules: `restore` R6"""
    m1 = mk_machine(name="Lathe", deleted=True)
    m3 = mk_machine(name="Drill", factory_id=f2.id, deleted=True)
    m4 = mk_machine(name="Saw")
    before_m3 = snap(db, m3)
    before_m4 = snap(db, m4)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, m3) == before_m3
    # Then 4
    row = reread(db, m3)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 5
    assert snap(db, m4) == before_m4
    # Then 6
    row = reread(db, m4)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 7
    assert count_rows(db, "machines") == 3


# [local-coder] MCH-RS-17
def test_mch_rs_17__a_machine_restored_inside_a_soft_deleted_factory_stays_hidden_from(db, w1, fd, mk_machine):
    """MCH-RS-17 — a machine restored inside a soft-deleted factory stays hidden from the machine search.
    Rules: `restore` R7a [BUG-890]"""
    mk_machine(name="Lathe")
    md = mk_machine(name="Press", factory_id=fd.id, deleted=True)

    result = dao.restore(db, db_obj=md)

    # Then 1
    assert result is md
    # Then 2
    row = reread(db, md)
    assert row.is_deleted is False
    # Then 3
    assert names(dao.search_advanced(db, workspace_id=w1.id)) == ["Lathe"]
    # Then 4
    assert dao.search_advanced(db, workspace_id=w1.id, factory_id=fd.id) == []


# [local-coder] MCH-RS-18
def test_mch_rs_18__a_machine_restored_inside_a_soft_deleted_factory_stays_hidden_from(db, w1, fd, s1, mk_machine, mk_assignment):
    """MCH-RS-18 — a machine restored inside a soft-deleted factory stays hidden from the factory and section lookups.
    Rules: `restore` R7a [BUG-891]"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    md = mk_machine(name="Press", factory_id=fd.id, deleted=True)
    mk_assignment(of=md, to=s1)

    result = dao.restore(db, db_obj=md)

    # Then 1
    assert result is md
    # Then 2
    row = reread(db, md)
    assert row.is_deleted is False
    # Then 3
    assert dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id) == []
    # Then 4
    assert ids(dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id)) == [m1.id]


# [local-coder] MCH-RS-22
def test_mch_rs_22__a_machine_is_restored_although_another_live_machine_of_the_factory(db, w1, f1, mk_machine):
    """MCH-RS-22 — a machine is restored although another live machine of the factory now has its name.
    Rules: `restore` R9 (Q9)"""
    m1 = mk_machine(name="Press 4", deleted=True)
    m2 = mk_machine(name="Press 4")
    before_m2 = snap(db, m2)

    result = dao.restore(db, db_obj=m1)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.name == "Press 4"
    # Then 4
    assert snap(db, m2) == before_m2
    # Then 5
    row2 = reread(db, m2)
    assert row2.name == "Press 4"
    assert row2.is_deleted is False
    # Then 6
    assert row2.updated_at is None
    # Then 7
    assert sorted(ids(dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id))) == [m1.id, m2.id]
    # Then 8
    assert count_rows(db, "machines") == 2
