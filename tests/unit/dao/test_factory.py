"""Unit tests for app/dao/factory.py.

Implements tests/unit/dao/factory.cases.md, one test per case. Real Postgres
session (`db` fixture). The only thing patched is the clock:
`app.dao.factory.utcnow` returns NOW in every test (Conventions, Externals).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/factory.helpers.md as its only view of this file; tests below a
`# [claude] <ID>` comment are the `Author: claude` cards, written by hand at
finishing (bulk loops, the commit spy, follow-up DAO calls, round trips).
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import datetime
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.factory import factory_dao
from app.dao.machine import machine_dao
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.schemas.factory import FactoryCreate, FactoryUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton factory_dao" (a module-level name, not a fixture)
dao = factory_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0", "NOW" (both naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the four standing rows)
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows". Each fixture depends on the one
# before it, so the ids rise in the order Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 creates the Given factories, U2 acts)
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "W1, W2, U1 and U2 exist in every test and need no Given line" and
# Externals "app.dao.factory.utcnow is patched to return NOW in every test"
@pytest.fixture(autouse=True)
def standing_rows(db, monkeypatch, w1, w2, u1, u2):
    monkeypatch.setattr("app.dao.factory.utcnow", lambda: NOW)


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Conventions "factory" and "deleted" (said of a factory)
@pytest.fixture
def mk_factory(db, w1, u1):
    """mk_factory(name=..., abbreviation=..., **columns) -> Factory. Keywords only.

    `deleted=True` is the Conventions word "deleted": is_deleted True,
    deleted_at T0, deleted_by U1.id (is_active stays True). `created_at` is
    left to the database.
    """
    def _mk(*, name, abbreviation, deleted=False, **columns):
        fields = {
            "workspace_id": w1.id, "name": name, "abbreviation": abbreviation,
            "created_by": u1.id, "updated_by": None, "updated_at": None,
            "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None,
        }
        if deleted:
            fields.update(is_deleted=True, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        return _add(db, Factory(**fields))
    return _mk


# Convention "machine of F"
@pytest.fixture
def mk_machine(db):
    """mk_machine(of=<factory>, name=..., **columns) -> Machine. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name,
                  "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None}
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "section of F"
@pytest.fixture
def mk_section(db):
    """mk_section(of=<factory>, name=..., **columns) -> FactorySection. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name,
                  "is_active": True, "is_deleted": False, "deleted_at": None, "deleted_by": None}
        fields.update(columns)
        return _add(db, FactorySection(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__ for model in (Factory, Machine, FactorySection)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` (factory, machine or section) from the database, or None if it is gone."""
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


# Convention "nothing written": row counts of factories, machines and factory_sections, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "ids(result)" / "names(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "by_id(result, X)": the one element of result whose id == X.id
def by_id(result, row):
    (found,) = [f for f in result if f.id == row.id]
    return found


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; the first six are shown verbatim in factory.helpers.md)
# --------------------------------------------------------------------------- #

def test_fcd_gw_05__a_soft_deleted_factory_is_returned_along_with_a_live_one(db, w1, mk_factory):
    """FCD-GW-05 — a soft-deleted factory is returned along with a live one.
    Rules: `get_by_workspace` R4 (P1)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fd.id]
    # Then 2
    assert by_id(result, fd).is_deleted is True
    # Then 3
    assert by_id(result, f1).is_deleted is False


@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fcd_gw_22__factories_come_back_in_id_order_not_in_name_order_and_not_in_the(db, w1, mk_factory):
    """FCD-GW-22 — factories come back in id order, not in name order and not in the table's physical order.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="apple", abbreviation="AP")
    f1.abbreviation = "ZX"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 2
    assert ids(result) == [f1.id, f2.id]


def test_fcd_ga_22__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_factory):
    """FCD-GA-22 — negative limit is rejected by the database and nothing changes.
    Rules: `get_active_factories` R5, Errors (negative `limit`, as `get_by_workspace`)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_active_factories(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, f1) == before_f1


def test_fcd_sd_10__a_factory_of_another_workspace_is_deleted_all_the_same(db, w2, u2, mk_factory):
    """FCD-SD-10 — a factory of another workspace is deleted all the same.
    Rules: `soft_delete` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f1 = snap(db, f1)

    result = dao.soft_delete(db, db_obj=f9, deleted_by=u2.id)

    # Then 1
    assert result is f9
    # Then 2
    row = reread(db, f9)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert row.workspace_id == w2.id
    # Then 5
    assert snap(db, f1) == before_f1


def test_fcd_rs_02__no_other_column_of_the_factory_is_changed_by_the_restore(db, w1, u1, mk_factory):
    """FCD-RS-02 — no other column of the factory is changed by the restore.
    Rules: `restore` R2"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    created_before = fd.created_at

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.name == "Old Plant"
    assert row.abbreviation == "OP"
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.created_at == created_before
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert row.is_deleted is False


def test_fcd_rs_08__a_factory_that_is_already_live_loaded_from_the_database_is_left(db, mk_factory):
    """FCD-RS-08 — a factory that is already live, loaded from the database, is left exactly as it is with no UPDATE.
    Rules: `restore` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    db.refresh(f1)
    before_f1 = snap(db, f1)

    result = dao.restore(db, db_obj=f1)

    # Then 1
    assert result is f1
    # Then 2
    assert snap(db, f1) == before_f1
    # Then 3
    row = reread(db, f1)
    assert row.updated_at is None
    # Then 4
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "factories") == 1


# Hand-written and not shown in factory.helpers.md: the tool's "a standing row the
# card names must be used" check reads the abbreviation "U2" of this card as the
# profile U2 and would reject the faithful test (it uses no `u2`).
def test_fcd_inh_06__update_with_an_explicit_null_name_changes_only_the_abbreviation(db, mk_factory):
    """FCD-INH-06 — update with an explicit null name changes only the abbreviation.
    Rules: inherited R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.update(db, db_obj=f1, obj_in=FactoryUpdate(name=None, abbreviation="U2"))

    # Then 1
    assert result.id == f1.id
    # Then 2
    row = reread(db, f1)
    assert row.abbreviation == "U2"
    # Then 3
    assert row.name == "Main Plant"


# [local-coder] FCD-GW-06
def test_fcd_gw_06__soft_deleted_factories_count_toward_limit(db, w1, mk_factory):
    """FCD-GW-06 — soft-deleted factories count toward limit.
    Rules: `get_by_workspace` R4 (P1), R2"""
    fd1 = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    fd2 = mk_factory(name="Shut Mill", abbreviation="SM", deleted=True)
    f3 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sum(1 for f in result if f.is_deleted) >= 1
    # Then 3
    assert set(ids(result)) <= {fd1.id, fd2.id, f3.id}


# [local-coder] FCD-GW-21
def test_fcd_gw_21__a_factory_that_was_updated_after_a_later_one_was_created_is_still(db, w1, mk_factory):
    """FCD-GW-21 — a factory that was updated after a later one was created is still returned exactly once.
    Rules: `get_by_workspace` R1, R3"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="apple", abbreviation="AP")
    f1.abbreviation = "ZX"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 3
    assert by_id(result, f1).abbreviation == "ZX"


# [local-coder] FCD-GW-23
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fcd_gw_23__the_first_window_of_one_holds_the_factory_with_the_lowest_id(db, w1, mk_factory):
    """FCD-GW-23 — the first window of one holds the factory with the lowest id.
    Rules: `get_by_workspace` R3 [BUG-100], R2"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    mk_factory(name="apple", abbreviation="AP")
    f1.abbreviation = "ZX"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=0, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [f1.id]


# [local-coder] FCD-GW-24
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fcd_gw_24__the_second_window_of_one_holds_the_factory_with_the_next_id(db, w1, mk_factory):
    """FCD-GW-24 — the second window of one holds the factory with the next id.
    Rules: `get_by_workspace` R3 [BUG-100], R2"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="apple", abbreviation="AP")
    f1.abbreviation = "ZX"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [f2.id]


# [local-coder] FCD-GW-25
def test_fcd_gw_25__the_lookup_writes_nothing(db, w1, u1, mk_factory):
    """FCD-GW-25 — the lookup writes nothing.
    Rules: `get_by_workspace` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before = written(db)
    before_f1 = snap(db, f1)
    before_fd = snap(db, fd)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, f1) == before_f1
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    row = reread(db, f1)
    assert row.updated_at is None
    # Then 6
    row = reread(db, fd)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [claude] FCD-GW-26
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_fcd_gw_26__the_list_query_asks_the_database_for_an_order(db, w1, mk_factory):
    """FCD-GW-26 — the list query asks the database for an order.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
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
    assert ids(result) == [f1.id]
    # Then 2
    selects = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()


# [local-coder] FCD-GI-12
def test_fcd_gi_12__a_soft_deleted_factory_with_is_active_false_is_returned(db, w1, mk_factory):
    """FCD-GI-12 — a soft-deleted factory with is_active False is returned.
    Rules: `get_by_id_and_workspace` R4 (P1), R5"""
    fx = mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)

    result = dao.get_by_id_and_workspace(db, id=fx.id, workspace_id=w1.id)

    # Then 1
    assert result.id == fx.id
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert result.is_active is False


# [local-coder] FCD-GA-08
def test_fcd_ga_08__of_the_four_combinations_of_active_and_deleted_only_the_active_live(db, w1, mk_factory):
    """FCD-GA-08 — of the four combinations of active and deleted only the active live factory is returned.
    Rules: `get_active_factories` R1a, R2 (Q3)"""
    mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)
    f4 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f4.id]
    # Then 2
    assert result[0].is_active is True
    # Then 3
    assert result[0].is_deleted is False


# [local-coder] FCD-GA-25
@pytest.mark.xfail(
    strict=False,
    reason="BUG-706: Incoming summary processes factories with no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fcd_ga_25__names_that_differ_only_in_case_come_back_in_id_order(db, w1, mk_factory):
    """FCD-GA-25 — names that differ only in case come back in id order.
    Rules: `get_active_factories` R6 [BUG-706]"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="bolt", abbreviation="BO")
    f3 = mk_factory(name="apple", abbreviation="AP")
    f4 = mk_factory(name="Bolt", abbreviation="BT")
    f5 = mk_factory(name="Banana", abbreviation="BA")

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id, f4.id, f5.id]
    # Then 2
    assert ids(result) == [f3.id, f5.id, f2.id, f4.id, f1.id]


# [local-coder] FCD-GA-27
def test_fcd_ga_27__a_factory_with_machines_and_sections_and_one_without_are_each(db, w1, mk_factory, mk_machine, mk_section):
    """FCD-GA-27 — a factory with machines and sections and one without are each returned once, and nothing is written.
    Rules: `get_active_factories` R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    ma1 = mk_machine(of=f1, name="Lathe")
    mk_machine(of=f1, name="Press")
    sc1 = mk_section(of=f1, name="Assembly")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    before = written(db)
    before_f1 = snap(db, f1)
    before_ma1 = snap(db, ma1)
    before_sc1 = snap(db, sc1)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    assert snap(db, ma1) == before_ma1
    # Then 6
    assert snap(db, sc1) == before_sc1


# [claude] FCD-GA-28
@pytest.mark.xfail(strict=True, reason="BUG-706: Incoming summary processes factories with no sort order")
def test_fcd_ga_28__the_active_list_query_asks_the_database_for_an_order(db, w1, mk_factory):
    """FCD-GA-28 — the active-list query asks the database for an order.
    Rules: `get_active_factories` R6 [BUG-706]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = dao.get_active_factories(db, workspace_id=w1.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [f1.id]
    # Then 2
    selects = [stmt for stmt in statements if stmt.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    assert "ORDER BY" in selects[0].upper()


# [local-coder] FCD-SD-06
def test_fcd_sd_06__the_machines_of_the_deleted_factory_are_left_exactly_as_they_were(db, u2, mk_factory, mk_machine):
    """FCD-SD-06 — the machines of the deleted factory are left exactly as they were.
    Rules: `soft_delete` R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    ma1 = mk_machine(of=f1, name="Lathe")
    ma2 = mk_machine(of=f1, name="Press", is_active=False)
    before_ma1 = snap(db, ma1)
    before_ma2 = snap(db, ma2)

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, ma1) == before_ma1
    # Then 4
    row = reread(db, ma1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert snap(db, ma2) == before_ma2
    # Then 7
    row = reread(db, ma2)
    assert row.is_deleted is False
    assert row.is_active is False
    # Then 8
    assert count_rows(db, "machines") == 2


# [local-coder] FCD-SD-12
def test_fcd_sd_12__a_deleted_by_that_is_no_profile_id_fails_on_flush_and_the_factory(db, mk_factory):
    """FCD-SD-12 — a deleted_by that is no profile id fails on flush and the factory stays live.
    Rules: `soft_delete` R7, Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.soft_delete(db, db_obj=f1, deleted_by=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factories_deleted_by_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    row = reread(db, f1)
    assert row.is_deleted is False
    # Then 6
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 7
    assert row.updated_at is None
    # Then 8
    assert written(db) == before


# [local-coder] FCD-RS-09
def test_fcd_rs_09__a_live_but_inactive_factory_loaded_from_the_database_stays_inactive(db, mk_factory):
    """FCD-RS-09 — a live but inactive factory, loaded from the database, stays inactive with no UPDATE.
    Rules: `restore` R4, R3 (Q2)"""
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)
    db.refresh(fi)
    before_fi = snap(db, fi)

    result = dao.restore(db, db_obj=fi)

    # Then 1
    assert result is fi
    # Then 2
    assert snap(db, fi) == before_fi
    # Then 3
    row = reread(db, fi)
    assert row.updated_at is None
    # Then 4
    assert row.is_active is False
    # Then 5
    assert row.is_deleted is False


# [local-coder] FCD-RS-13
def test_fcd_rs_13__the_machine_and_the_section_of_the_restored_factory_are_exactly_as(db, mk_factory, mk_machine, mk_section):
    """FCD-RS-13 — the machine and the section of the restored factory are exactly as they were.
    Rules: `restore` R7"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    ma1 = mk_machine(of=fd, name="Lathe")
    sc1 = mk_section(of=fd, name="Assembly")
    before_ma1 = snap(db, ma1)
    before_sc1 = snap(db, sc1)
    before = written(db)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.is_deleted is False
    # Then 3
    assert snap(db, ma1) == before_ma1
    # Then 4
    row = reread(db, ma1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert snap(db, sc1) == before_sc1
    # Then 7
    row = reread(db, sc1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 8
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 9
    assert written(db) == before


# [local-coder] FCD-RS-19
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fcd_rs_19__the_database_refuses_a_restore_whose_name_is_used_by_another_live(db, u1, mk_factory):
    """FCD-RS-19 — the database refuses a restore whose name is used by another live factory of the workspace.
    Rules: `restore` R9a [BUG-895], Errors row 1"""
    fd = mk_factory(name="Main Plant", abbreviation="MP", deleted=True)
    f2 = mk_factory(name="main plant", abbreviation="XX")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.restore(db, db_obj=fd)

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    row = reread(db, fd)
    assert row.is_deleted is True
    # Then 4
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 5
    assert snap(db, f2) == before_f2


# [local-coder] FCD-INH-01
def test_fcd_inh_01__create_with_a_dict_of_the_three_required_values_stores_a_factory_with(db, w1):
    """FCD-INH-01 — create with a dict of the three required values stores a factory with the model defaults.
    Rules: inherited R1"""

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Main Plant", "abbreviation": "MP"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
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
    assert count_rows(db, "factories") == 1


# [local-coder] FCD-INH-02
def test_fcd_inh_02__create_with_a_factorycreate_schema_fails_on_flush_and_saves_no_factory(db):
    """FCD-INH-02 — create with a FactoryCreate schema fails on flush and saves no factory.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=FactoryCreate(name="Main Plant", abbreviation="MP"))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 0


# [local-coder] FCD-INH-08
def test_fcd_inh_08__get_returns_the_factory_of_another_workspace(db, w2, mk_factory):
    """FCD-INH-08 — get returns the factory of another workspace.
    Rules: inherited R4 (Q4)"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get(db, f9.id)

    # Then 1
    assert result.id == f9.id
    # Then 2
    assert result.workspace_id == w2.id
    # Then 3
    assert result.name == "Far Depot"


# [local-coder] FCD-GW-01
def test_fcd_gw_01__returns_a_list_of_the_factories_of_that_workspace(db, w1, w2, mk_factory):
    """FCD-GW-01 — returns a list of the factories of that workspace.
    Rules: `get_by_workspace` R1, Returns"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], Factory)


# [local-coder] FCD-GW-02
def test_fcd_gw_02__a_call_for_the_other_workspace_returns_only_that_workspace_s_factory(db, w2, mk_factory):
    """FCD-GW-02 — a call for the other workspace returns only that workspace's factory.
    Rules: `get_by_workspace` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [f9.id]


# [local-coder] FCD-GW-03
def test_fcd_gw_03__a_workspace_with_no_factories_returns_an_empty_list(db, w2, mk_factory):
    """FCD-GW-03 — a workspace with no factories returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] FCD-GW-04
def test_fcd_gw_04__an_unknown_workspace_id_returns_an_empty_list(db, mk_factory):
    """FCD-GW-04 — an unknown workspace id returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] FCD-GW-07
def test_fcd_gw_07__soft_deleted_factories_count_toward_skip(db, w1, mk_factory):
    """FCD-GW-07 — soft-deleted factories count toward skip.
    Rules: `get_by_workspace` R4 (P1), R2"""
    fd1 = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    fd2 = mk_factory(name="Shut Mill", abbreviation="SM", deleted=True)
    f3 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {fd1.id, fd2.id, f3.id}


# [claude] FCD-GW-08
def test_fcd_gw_08__100_deleted_factories_in_front_of_one_live_factory_fill_the_default_page(db, w1, mk_factory):
    """FCD-GW-08 — 100 deleted factories in front of one live factory fill the default page.
    Rules: `get_by_workspace` R4 (P1), R2"""
    all_ids = [mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True).id for k in range(1, 101)]
    late = mk_factory(name="Late", abbreviation="LT")
    all_ids.append(late.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert sum(1 for f in result if f.is_deleted) >= 99
    # Then 3
    assert set(ids(result)) <= set(all_ids)


# [local-coder] FCD-GW-09
def test_fcd_gw_09__a_live_factory_with_is_active_false_is_returned(db, w1, mk_factory):
    """FCD-GW-09 — a live factory with is_active False is returned.
    Rules: `get_by_workspace` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fi.id]
    # Then 2
    assert by_id(result, fi).is_active is False


# [local-coder] FCD-GW-10
def test_fcd_gw_10__all_four_combinations_of_active_and_deleted_are_returned(db, w1, mk_factory):
    """FCD-GW-10 — all four combinations of active and deleted are returned.
    Rules: `get_by_workspace` R4 (P1), R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    fx = mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fi.id, fd.id, fx.id]
    # Then 2
    assert len(result) == 4


# [claude] FCD-GW-11
def test_fcd_gw_11__default_limit_returns_exactly_100_of_101_factories(db, w1, mk_factory):
    """FCD-GW-11 — default limit returns exactly 100 of 101 factories.
    Rules: `get_by_workspace` R2"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= set(all_ids)


# [claude] FCD-GW-12
def test_fcd_gw_12__an_explicit_limit_of_101_returns_all_101_factories(db, w1, mk_factory):
    """FCD-GW-12 — an explicit limit of 101 returns all 101 factories.
    Rules: `get_by_workspace` R2"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == all_ids


# [local-coder] FCD-GW-13
def test_fcd_gw_13__limit_2_of_three_factories_returns_two_different_factories(db, w1, mk_factory):
    """FCD-GW-13 — limit 2 of three factories returns two different factories.
    Rules: `get_by_workspace` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    f3 = mk_factory(name="South Dock", abbreviation="SD")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {f1.id, f2.id, f3.id}


# [local-coder] FCD-GW-14
def test_fcd_gw_14__the_last_window_is_short(db, w1, mk_factory):
    """FCD-GW-14 — the last window is short.
    Rules: `get_by_workspace` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    f3 = mk_factory(name="South Dock", abbreviation="SD")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id, f3.id]


# [local-coder] FCD-GW-15
def test_fcd_gw_15__limit_0_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GW-15 — limit 0 returns an empty list.
    Rules: `get_by_workspace` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] FCD-GW-16
def test_fcd_gw_16__skip_equal_to_the_number_of_factories_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GW-16 — skip equal to the number of factories returns an empty list.
    Rules: `get_by_workspace` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] FCD-GW-17
def test_fcd_gw_17__skip_one_below_the_number_of_factories_returns_one_factory(db, w1, mk_factory):
    """FCD-GW-17 — skip one below the number of factories returns one factory.
    Rules: `get_by_workspace` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id]


# [local-coder] FCD-GW-18
def test_fcd_gw_18__skip_past_the_number_of_factories_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GW-18 — skip past the number of factories returns an empty list.
    Rules: `get_by_workspace` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] FCD-GW-19
def test_fcd_gw_19__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_factory):
    """FCD-GW-19 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_workspace` R2, Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, f1) == before_f1


# [local-coder] FCD-GW-20
def test_fcd_gw_20__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_factory):
    """FCD-GW-20 — negative skip is rejected by the database and nothing changes.
    Rules: `get_by_workspace` R2, Errors row 2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, f1) == before_f1


# [local-coder] FCD-GI-01
def test_fcd_gi_01__a_factory_of_the_workspace_is_returned_by_its_id(db, w1, mk_factory):
    """FCD-GI-01 — a factory of the workspace is returned by its id.
    Rules: `get_by_id_and_workspace` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_id_and_workspace(db, id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Factory)
    # Then 2
    assert result.id == f1.id
    # Then 3
    assert result.name == "Main Plant"
    # Then 4
    assert result.abbreviation == "MP"


# [local-coder] FCD-GI-02
def test_fcd_gi_02__of_two_factories_the_one_with_the_given_id_is_returned(db, w1, mk_factory):
    """FCD-GI-02 — of two factories the one with the given id is returned.
    Rules: `get_by_id_and_workspace` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_by_id_and_workspace(db, id=f2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == f2.id
    # Then 2
    assert result.name == "North Yard"


# [local-coder] FCD-GI-03
def test_fcd_gi_03__a_factory_of_another_workspace_is_not_found(db, w1, w2, mk_factory):
    """FCD-GI-03 — a factory of another workspace is not found.
    Rules: `get_by_id_and_workspace` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=f9.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-04
def test_fcd_gi_04__a_factory_of_the_first_workspace_is_not_found_from_the_second(db, w2, mk_factory):
    """FCD-GI-04 — a factory of the first workspace is not found from the second.
    Rules: `get_by_id_and_workspace` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=f1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-05
def test_fcd_gi_05__a_factory_of_the_second_workspace_is_found_from_its_own_workspace(db, w2, mk_factory):
    """FCD-GI-05 — a factory of the second workspace is found from its own workspace.
    Rules: `get_by_id_and_workspace` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=f9.id, workspace_id=w2.id)

    # Then 1
    assert result.id == f9.id
    # Then 2
    assert result.workspace_id == w2.id


# [local-coder] FCD-GI-06
def test_fcd_gi_06__an_id_that_no_factory_has_returns_none(db, w1, mk_factory):
    """FCD-GI-06 — an id that no factory has returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-07
def test_fcd_gi_07__id_0_returns_none(db, w1, mk_factory):
    """FCD-GI-07 — id 0 returns None.
    Rules: `get_by_id_and_workspace` R3"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-08
def test_fcd_gi_08__an_unknown_workspace_id_returns_none_for_an_existing_factory_id(db, mk_factory):
    """FCD-GI-08 — an unknown workspace id returns None for an existing factory id.
    Rules: `get_by_id_and_workspace` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_by_id_and_workspace(db, id=f1.id, workspace_id=MISSING)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-09
def test_fcd_gi_09__a_soft_deleted_factory_of_the_workspace_is_returned(db, w1, u1, mk_factory):
    """FCD-GI-09 — a soft-deleted factory of the workspace is returned.
    Rules: `get_by_id_and_workspace` R4 (P1)"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get_by_id_and_workspace(db, id=fd.id, workspace_id=w1.id)

    # Then 1
    assert result.id == fd.id
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert result.deleted_at == T0
    # Then 4
    assert result.deleted_by == u1.id


# [local-coder] FCD-GI-10
def test_fcd_gi_10__a_soft_deleted_factory_of_another_workspace_is_not_found(db, w1, w2, mk_factory):
    """FCD-GI-10 — a soft-deleted factory of another workspace is not found.
    Rules: `get_by_id_and_workspace` R2"""
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)

    result = dao.get_by_id_and_workspace(db, id=fd9.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] FCD-GI-11
def test_fcd_gi_11__a_live_factory_with_is_active_false_is_returned(db, w1, mk_factory):
    """FCD-GI-11 — a live factory with is_active False is returned.
    Rules: `get_by_id_and_workspace` R5"""
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)

    result = dao.get_by_id_and_workspace(db, id=fi.id, workspace_id=w1.id)

    # Then 1
    assert result.id == fi.id
    # Then 2
    assert result.is_active is False
    # Then 3
    assert result.is_deleted is False


# [local-coder] FCD-GI-13
def test_fcd_gi_13__the_lookup_writes_nothing(db, w1, mk_factory):
    """FCD-GI-13 — the lookup writes nothing.
    Rules: `get_by_id_and_workspace` Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before = written(db)
    before_fd = snap(db, fd)
    before_f1 = snap(db, f1)

    result = dao.get_by_id_and_workspace(db, id=fd.id, workspace_id=w1.id)

    # Then 1
    assert result.id == fd.id
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    row = reread(db, fd)
    assert row.updated_at is None


# [local-coder] FCD-GA-01
def test_fcd_ga_01__returns_a_list_of_the_active_live_factories_of_that_workspace(db, w1, w2, mk_factory):
    """FCD-GA-01 — returns a list of the active live factories of that workspace.
    Rules: `get_active_factories` R1, Returns"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], Factory)


# [local-coder] FCD-GA-02
def test_fcd_ga_02__a_call_for_the_other_workspace_returns_only_that_workspace_s_factory(db, w2, mk_factory):
    """FCD-GA-02 — a call for the other workspace returns only that workspace's factory.
    Rules: `get_active_factories` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = dao.get_active_factories(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [f9.id]


# [local-coder] FCD-GA-03
def test_fcd_ga_03__a_workspace_with_no_factories_returns_an_empty_list(db, w2, mk_factory):
    """FCD-GA-03 — a workspace with no factories returns an empty list.
    Rules: `get_active_factories` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_active_factories(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-04
def test_fcd_ga_04__an_unknown_workspace_id_returns_an_empty_list(db, mk_factory):
    """FCD-GA-04 — an unknown workspace id returns an empty list.
    Rules: `get_active_factories` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_active_factories(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-05
def test_fcd_ga_05__a_soft_deleted_factory_that_still_says_active_is_not_returned(db, w1, mk_factory):
    """FCD-GA-05 — a soft-deleted factory that still says active is not returned.
    Rules: `get_active_factories` R1a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FCD-GA-06
def test_fcd_ga_06__a_soft_deleted_factory_with_is_active_false_is_not_returned(db, w1, mk_factory):
    """FCD-GA-06 — a soft-deleted factory with is_active False is not returned.
    Rules: `get_active_factories` R1a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FCD-GA-07
def test_fcd_ga_07__a_live_factory_with_is_active_false_is_not_returned(db, w1, mk_factory):
    """FCD-GA-07 — a live factory with is_active False is not returned.
    Rules: `get_active_factories` R2 (Q3)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FCD-GA-09
def test_fcd_ga_09__a_workspace_whose_factories_are_all_inactive_or_deleted_returns_an(db, w1, mk_factory):
    """FCD-GA-09 — a workspace whose factories are all inactive or deleted returns an empty list.
    Rules: `get_active_factories` R1, R1a, R2 (Q3)"""
    mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-10
def test_fcd_ga_10__soft_deleted_factories_in_front_do_not_use_up_a_place_in_the_page(db, w1, mk_factory):
    """FCD-GA-10 — soft-deleted factories in front do not use up a place in the page.
    Rules: `get_active_factories` R3, R1a"""
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Shut Mill", abbreviation="SM", deleted=True)
    l1 = mk_factory(name="Main Plant", abbreviation="MP")
    l2 = mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_active_factories(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [l1.id, l2.id]


# [local-coder] FCD-GA-11
def test_fcd_ga_11__inactive_factories_in_front_do_not_use_up_a_place_in_the_page(db, w1, mk_factory):
    """FCD-GA-11 — inactive factories in front do not use up a place in the page.
    Rules: `get_active_factories` R3, R2 (Q3)"""
    mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)
    mk_factory(name="Quiet Works", abbreviation="QW", is_active=False)
    l1 = mk_factory(name="Main Plant", abbreviation="MP")
    l2 = mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_active_factories(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [l1.id, l2.id]


# [local-coder] FCD-GA-12
def test_fcd_ga_12__skip_counts_only_the_matching_factories(db, w1, mk_factory):
    """FCD-GA-12 — skip counts only the matching factories.
    Rules: `get_active_factories` R3, R5"""
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert result == []


# [claude] FCD-GA-13
def test_fcd_ga_13__one_active_live_factory_behind_100_deleted_and_100_inactive_ones_is_returned(db, w1, mk_factory):
    """FCD-GA-13 — one active live factory behind 100 deleted and 100 inactive ones is returned by the default call.
    Rules: `get_active_factories` R3, R2 (Q3)"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    for k in range(1, 101):
        mk_factory(name=f"Idle {k:03d}", abbreviation=f"I{k:03d}", is_active=False)
    late = mk_factory(name="Late", abbreviation="LT")

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [late.id]


# [claude] FCD-GA-14
def test_fcd_ga_14__default_limit_returns_exactly_100_of_101_active_live_factories(db, w1, mk_factory):
    """FCD-GA-14 — default limit returns exactly 100 of 101 active live factories.
    Rules: `get_active_factories` R4"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= set(all_ids)


# [claude] FCD-GA-15
def test_fcd_ga_15__a_limit_of_500_returns_all_101_active_live_factories(db, w1, mk_factory):
    """FCD-GA-15 — a limit of 500 returns all 101 active live factories.
    Rules: `get_active_factories` R4"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = dao.get_active_factories(db, workspace_id=w1.id, limit=500)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == all_ids


# [local-coder] FCD-GA-16
def test_fcd_ga_16__limit_2_of_three_factories_returns_two_different_factories(db, w1, mk_factory):
    """FCD-GA-16 — limit 2 of three factories returns two different factories.
    Rules: `get_active_factories` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    f3 = mk_factory(name="South Dock", abbreviation="SD")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len(set(ids(result))) == 2
    # Then 3
    assert set(ids(result)) <= {f1.id, f2.id, f3.id}


# [local-coder] FCD-GA-17
def test_fcd_ga_17__the_last_window_is_short(db, w1, mk_factory):
    """FCD-GA-17 — the last window is short.
    Rules: `get_active_factories` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    f3 = mk_factory(name="South Dock", abbreviation="SD")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id, f3.id]


# [local-coder] FCD-GA-18
def test_fcd_ga_18__limit_0_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GA-18 — limit 0 returns an empty list.
    Rules: `get_active_factories` R5"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.get_active_factories(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-19
def test_fcd_ga_19__skip_equal_to_the_number_of_matching_factories_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GA-19 — skip equal to the number of matching factories returns an empty list.
    Rules: `get_active_factories` R5"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-20
def test_fcd_ga_20__skip_one_below_the_number_of_matching_factories_returns_one_factory(db, w1, mk_factory):
    """FCD-GA-20 — skip one below the number of matching factories returns one factory.
    Rules: `get_active_factories` R5, R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id]


# [local-coder] FCD-GA-21
def test_fcd_ga_21__skip_past_the_number_of_matching_factories_returns_an_empty_list(db, w1, mk_factory):
    """FCD-GA-21 — skip past the number of matching factories returns an empty list.
    Rules: `get_active_factories` R5"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] FCD-GA-23
def test_fcd_ga_23__negative_skip_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_factory):
    """FCD-GA-23 — negative skip is rejected by the database and nothing changes.
    Rules: `get_active_factories` R5, Errors (negative `skip`, as `get_by_workspace`)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_active_factories(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, f1) == before_f1


# [local-coder] FCD-GA-24
@pytest.mark.xfail(
    strict=False,
    reason="BUG-706: Incoming summary processes factories with no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_fcd_ga_24__factories_come_back_by_name_case_insensitive_ascending(db, w1, mk_factory):
    """FCD-GA-24 — factories come back by name, case-insensitive ascending.
    Rules: `get_active_factories` R6 [BUG-706]"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="bolt", abbreviation="BO")
    f3 = mk_factory(name="apple", abbreviation="AP")
    f4 = mk_factory(name="Banana", abbreviation="BA")

    result = dao.get_active_factories(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id, f4.id]
    # Then 2
    assert names(result) == ["apple", "Banana", "bolt", "Zulu"]


# [claude] FCD-GA-26
@pytest.mark.xfail(
    strict=False,
    reason="BUG-706: Incoming summary processes factories with no sort order "
           "(non-strict: a page of the physical row order can equal the intended page by accident)",
)
def test_fcd_ga_26__a_middle_window_holds_the_second_and_third_factory_by_name(db, w1, mk_factory):
    """FCD-GA-26 — a middle window holds the second and third factory by name.
    Rules: `get_active_factories` R6 [BUG-706], R4"""
    mk_factory(name="Zulu", abbreviation="ZU")
    mk_factory(name="bolt", abbreviation="BO")
    mk_factory(name="apple", abbreviation="AP")
    mk_factory(name="Banana", abbreviation="BA")

    result = dao.get_active_factories(db, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert names(result) == ["Banana", "bolt"]


# [local-coder] FCD-SD-01
def test_fcd_sd_01__a_live_factory_is_marked_deleted_with_the_clock_value_and_the_acting(db, u2, mk_factory):
    """FCD-SD-01 — a live factory is marked deleted with the clock value and the acting user.
    Rules: `soft_delete` R1, R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    # Then 4
    assert row.deleted_by == u2.id
    # Then 5
    assert count_rows(db, "factories") == 1


# [local-coder] FCD-SD-02
def test_fcd_sd_02__no_other_column_of_the_factory_is_changed_by_the_delete(db, w1, u1, u2, mk_factory):
    """FCD-SD-02 — no other column of the factory is changed by the delete.
    Rules: `soft_delete` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)
    created_before = f1.created_at

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
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


# [local-coder] FCD-SD-03
def test_fcd_sd_03__the_delete_does_not_stamp_updated_by(db, u2, mk_factory):
    """FCD-SD-03 — the delete does not stamp updated_by.
    Rules: `soft_delete` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.updated_by is None
    # Then 3
    assert row.updated_at is not None
    # Then 4
    assert row.is_deleted is True


# [local-coder] FCD-SD-04
def test_fcd_sd_04__an_active_factory_still_says_active_after_the_delete(db, u2, mk_factory):
    """FCD-SD-04 — an active factory still says active after the delete.
    Rules: `soft_delete` R2a (Q1)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is True


# [local-coder] FCD-SD-05
def test_fcd_sd_05__a_live_factory_with_is_active_false_is_deleted_and_stays_inactive(db, u2, mk_factory):
    """FCD-SD-05 — a live factory with is_active False is deleted and stays inactive.
    Rules: `soft_delete` R2a (Q1), R1"""
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)

    result = dao.soft_delete(db, db_obj=fi, deleted_by=u2.id)

    # Then 1
    assert result is fi
    # Then 2
    row = reread(db, fi)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is False
    # Then 4
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id


# [local-coder] FCD-SD-07
def test_fcd_sd_07__the_sections_of_the_deleted_factory_are_left_exactly_as_they_were(db, u2, mk_factory, mk_section):
    """FCD-SD-07 — the sections of the deleted factory are left exactly as they were.
    Rules: `soft_delete` R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    sc1 = mk_section(of=f1, name="Assembly")
    sc2 = mk_section(of=f1, name="Paint", is_active=False)
    before_sc1 = snap(db, sc1)
    before_sc2 = snap(db, sc2)

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, sc1) == before_sc1
    # Then 4
    row = reread(db, sc1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert snap(db, sc2) == before_sc2
    # Then 7
    row = reread(db, sc2)
    assert row.is_deleted is False
    assert row.is_active is False
    # Then 8
    assert count_rows(db, "factory_sections") == 2


# [local-coder] FCD-SD-08
def test_fcd_sd_08__an_already_deleted_factory_gets_a_new_deletion_stamp_without_an_error(db, u2, mk_factory):
    """FCD-SD-08 — an already deleted factory gets a new deletion stamp without an error.
    Rules: `soft_delete` R4"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.soft_delete(db, db_obj=fd, deleted_by=u2.id)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.deleted_at == NOW
    # Then 3
    assert row.deleted_by == u2.id
    # Then 4
    assert row.is_deleted is True


# [claude] FCD-SD-09
def test_fcd_sd_09__the_delete_is_flushed_but_not_committed_visible_in_the_session_undone_by_a_rollback(db, w1, u2, mk_factory):
    """FCD-SD-09 — the delete is flushed but not committed: visible to the lookups in the session, undone by a rollback.
    Rules: `soft_delete` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

        # Then 1
        assert result is f1
        # Then 2
        row = reread(db, f1)
        assert row.is_deleted is True
        # Then 3
        assert ids(dao.get_active_factories(db, workspace_id=w1.id)) == [f2.id]
        # Then 4
        assert sorted(ids(dao.get_by_workspace(db, workspace_id=w1.id))) == [f1.id, f2.id]
        # Then 5
        assert dao.get_by_id_and_workspace(db, id=f1.id, workspace_id=w1.id).is_deleted is True
        sp.rollback()
        # Then 6
        row = reread(db, f1)
        assert row.is_deleted is False
        assert row.is_active is True
        # Then 7
        assert row.deleted_at is None
        assert row.deleted_by is None
        # Then 8
        assert commit_spy.call_count == 0


# [local-coder] FCD-SD-11
def test_fcd_sd_11__only_that_factory_row_is_touched(db, u1, u2, mk_factory):
    """FCD-SD-11 — only that factory row is touched.
    Rules: `soft_delete` R6, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="North Yard", abbreviation="NY")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_f2 = snap(db, f2)
    before_fd = snap(db, fd)
    before = written(db)

    result = dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, f2) == before_f2
    # Then 4
    row = reread(db, f2)
    assert row.is_deleted is False
    assert row.updated_at is None
    # Then 5
    assert snap(db, fd) == before_fd
    # Then 6
    row = reread(db, fd)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before
    # Then 8
    assert count_rows(db, "factories") == 3


# [local-coder] FCD-SD-13
def test_fcd_sd_13__deleted_by_none_is_stored_as_null_and_the_factory_is_deleted(db, mk_factory):
    """FCD-SD-13 — deleted_by None is stored as NULL and the factory is deleted.
    Rules: `soft_delete` R8"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.soft_delete(db, db_obj=f1, deleted_by=None)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.deleted_by is None
    # Then 3
    assert row.is_deleted is True
    # Then 4
    assert row.deleted_at == NOW


# [local-coder] FCD-RS-01
def test_fcd_rs_01__a_deleted_factory_is_made_live_again_and_its_deletion_stamp_is_cleared(db, mk_factory):
    """FCD-RS-01 — a deleted factory is made live again and its deletion stamp is cleared.
    Rules: `restore` R1, R5"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    # Then 4
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, "factories") == 1


# [local-coder] FCD-RS-03
def test_fcd_rs_03__updated_by_keeps_the_value_it_had(db, u2, mk_factory):
    """FCD-RS-03 — updated_by keeps the value it had.
    Rules: `restore` R2a (P2)"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", updated_by=u2.id, deleted=True)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.updated_by == u2.id
    # Then 3
    assert row.is_deleted is False


# [local-coder] FCD-RS-04
def test_fcd_rs_04__an_empty_updated_by_stays_empty_nobody_is_recorded_as_having_restored(db, mk_factory):
    """FCD-RS-04 — an empty updated_by stays empty: nobody is recorded as having restored.
    Rules: `restore` R2a (P2)"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.updated_by is None
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.deleted_by is None


# [local-coder] FCD-RS-05
def test_fcd_rs_05__a_factory_deleted_while_active_comes_back_active(db, mk_factory):
    """FCD-RS-05 — a factory deleted while active comes back active.
    Rules: `restore` R3 (Q2)"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.is_active is True
    # Then 3
    assert row.is_deleted is False


# [local-coder] FCD-RS-06
def test_fcd_rs_06__a_deleted_factory_with_is_active_false_comes_back_live_and_still(db, mk_factory):
    """FCD-RS-06 — a deleted factory with is_active False comes back live and still inactive.
    Rules: `restore` R3 (Q2)"""
    fx = mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)

    result = dao.restore(db, db_obj=fx)

    # Then 1
    assert result is fx
    # Then 2
    row = reread(db, fx)
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.deleted_at is None
    assert row.deleted_by is None


# [claude] FCD-RS-07
def test_fcd_rs_07__a_restored_inactive_factory_is_found_by_the_two_raw_lookups_and_not_by_the_active_list(db, w1, mk_factory):
    """FCD-RS-07 — a restored inactive factory is found by the two raw lookups and not by the active list.
    Rules: `restore` R3 (Q2); `get_active_factories` R2 (Q3)"""
    fx = mk_factory(name="Shut Mill", abbreviation="SM", is_active=False, deleted=True)
    f2 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.restore(db, db_obj=fx)

    # Then 1
    assert result is fx
    # Then 2
    row = reread(db, fx)
    assert row.is_deleted is False
    assert row.is_active is False
    # Then 3
    assert sorted(ids(dao.get_by_workspace(db, workspace_id=w1.id))) == [fx.id, f2.id]
    # Then 4
    assert dao.get_by_id_and_workspace(db, id=fx.id, workspace_id=w1.id).id == fx.id
    # Then 5
    assert ids(dao.get_active_factories(db, workspace_id=w1.id)) == [f2.id]


# [claude] FCD-RS-10
def test_fcd_rs_10__the_restore_is_flushed_but_not_committed_visible_in_the_session_undone_by_a_rollback(db, w1, u1, mk_factory):
    """FCD-RS-10 — the restore is flushed but not committed: visible to the active list in the session, undone by a rollback.
    Rules: `restore` R5"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    f2 = mk_factory(name="Main Plant", abbreviation="MP")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.restore(db, db_obj=fd)

        # Then 1
        assert result is fd
        # Then 2
        row = reread(db, fd)
        assert row.is_deleted is False
        # Then 3
        assert sorted(ids(dao.get_active_factories(db, workspace_id=w1.id))) == [fd.id, f2.id]
        sp.rollback()
        # Then 4
        row = reread(db, fd)
        assert row.is_deleted is True
        # Then 5
        assert row.deleted_at == T0
        # Then 6
        assert row.deleted_by == u1.id
        # Then 7
        assert commit_spy.call_count == 0


# [local-coder] FCD-RS-11
def test_fcd_rs_11__a_factory_of_another_workspace_is_restored_all_the_same(db, w2, mk_factory):
    """FCD-RS-11 — a factory of another workspace is restored all the same.
    Rules: `restore` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)
    before_f1 = snap(db, f1)

    result = dao.restore(db, db_obj=fd9)

    # Then 1
    assert result is fd9
    # Then 2
    row = reread(db, fd9)
    assert row.is_deleted is False
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.workspace_id == w2.id
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FCD-RS-12
def test_fcd_rs_12__a_second_deleted_factory_stays_deleted_and_a_live_one_is_not_touched(db, u1, mk_factory):
    """FCD-RS-12 — a second deleted factory stays deleted and a live one is not touched.
    Rules: `restore` R6, Side effects"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    fd2 = mk_factory(name="Shut Mill", abbreviation="SM", deleted=True)
    f3 = mk_factory(name="Main Plant", abbreviation="MP")
    before_fd2 = snap(db, fd2)
    before_f3 = snap(db, f3)
    before_written = written(db)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is False
    # Then 3
    assert snap(db, fd2) == before_fd2
    # Then 4
    row_fd2 = reread(db, fd2)
    assert row_fd2.is_deleted is True
    # Then 5
    assert row_fd2.deleted_at == T0
    assert row_fd2.deleted_by == u1.id
    # Then 6
    assert snap(db, f3) == before_f3
    # Then 7
    row_f3 = reread(db, f3)
    assert row_f3.is_deleted is False
    assert row_f3.updated_at is None
    # Then 8
    assert written(db) == before_written
    # Then 9
    assert count_rows(db, "factories") == 3


# [claude] FCD-RS-14
def test_fcd_rs_14__after_the_restore_the_machine_lookup_returns_the_factory_s_live_machines(db, w1, mk_factory, mk_machine):
    """FCD-RS-14 — after the restore the machine lookup returns the factory's live machines.
    Rules: `restore` R7"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    ma1 = mk_machine(of=fd, name="Lathe")
    ma2 = mk_machine(of=fd, name="Press")
    ma3 = mk_machine(of=fd, name="Drill", is_deleted=True, is_active=False)
    before_ma3 = snap(db, ma3)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.is_deleted is False
    # Then 3
    assert sorted(m.id for m in machine_dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id)) == [ma1.id, ma2.id]
    # Then 4
    assert snap(db, ma3) == before_ma3
    # Then 5
    assert count_rows(db, "machines") == 3


# [claude] FCD-RS-15
def test_fcd_rs_15__delete_then_restore_gives_back_the_same_value_in_every_column_except_updated_at(db, u1, u2, mk_factory):
    """FCD-RS-15 — delete then restore gives back the same value in every column except updated_at.
    Rules: `restore` R8 (Q2); `soft_delete` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)
    before = snap(db, f1)
    dao.soft_delete(db, db_obj=f1, deleted_by=u2.id)

    result = dao.restore(db, db_obj=f1)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    after = snap(db, f1)
    assert {c: v for c, v in after.items() if c != "updated_at"} == {c: v for c, v in before.items() if c != "updated_at"}
    # Then 3
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
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


# [claude] FCD-RS-16
def test_fcd_rs_16__delete_then_restore_of_an_inactive_factory_gives_back_an_inactive_factory(db, u1, u2, mk_factory):
    """FCD-RS-16 — delete then restore of an inactive factory gives back an inactive factory.
    Rules: `restore` R8 (Q2), R3 (Q2); `soft_delete` R2a (Q1)"""
    fi = mk_factory(name="Idle Plant", abbreviation="IP", is_active=False, updated_by=u1.id)
    before = snap(db, fi)
    dao.soft_delete(db, db_obj=fi, deleted_by=u2.id)

    result = dao.restore(db, db_obj=fi)

    # Then 1
    assert result is fi
    # Then 2
    row = reread(db, fi)
    after = snap(db, fi)
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


# [local-coder] FCD-RS-17
def test_fcd_rs_17__a_factory_is_restored_although_another_soft_deleted_factory_of_the(db, mk_factory):
    """FCD-RS-17 — a factory is restored although another soft-deleted factory of the workspace has its name and abbreviation.
    Rules: `restore` R9 (P3)"""
    fd = mk_factory(name="Main Plant", abbreviation="MP", deleted=True)
    fd2 = mk_factory(name="Main Plant", abbreviation="MP", deleted=True)
    before_fd2 = snap(db, fd2)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.is_deleted is False
    # Then 3
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 4
    assert snap(db, fd2) == before_fd2
    # Then 5
    row2 = reread(db, fd2)
    assert row2.is_deleted is True
    # Then 6
    assert count_rows(db, "factories") == 2


# [local-coder] FCD-RS-18
def test_fcd_rs_18__a_factory_is_restored_although_a_live_factory_of_another_workspace(db, w2, mk_factory):
    """FCD-RS-18 — a factory is restored although a live factory of another workspace has its name and abbreviation.
    Rules: `restore` R9 (P3)"""
    fd = mk_factory(name="Main Plant", abbreviation="MP", deleted=True)
    f9 = mk_factory(name="Main Plant", abbreviation="MP", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is False
    # Then 3
    assert row_fd.name == "Main Plant"
    assert row_fd.abbreviation == "MP"
    # Then 4
    assert snap(db, f9) == before_f9
    # Then 5
    row_f9 = reread(db, f9)
    assert row_f9.is_deleted is False
    assert row_f9.updated_at is None


# [local-coder] FCD-RS-20
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fcd_rs_20__the_database_refuses_a_restore_whose_abbreviation_is_used_by_another(db, u1, mk_factory):
    """FCD-RS-20 — the database refuses a restore whose abbreviation is used by another live factory of the workspace.
    Rules: `restore` R9a [BUG-895], Errors row 1"""
    fd = mk_factory(name="Old Site", abbreviation="MP", deleted=True)
    f2 = mk_factory(name="New Site", abbreviation=" mp")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.restore(db, db_obj=fd)

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    row = reread(db, fd)
    assert row.is_deleted is True
    # Then 4
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 5
    assert snap(db, f2) == before_f2


# [local-coder] FCD-INH-03
def test_fcd_inh_03__create_with_a_dict_that_has_no_abbreviation_fails_on_flush_and_saves(db, w1):
    """FCD-INH-03 — create with a dict that has no abbreviation fails on flush and saves no factory.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Main Plant"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "abbreviation" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 0


# [local-coder] FCD-INH-04
def test_fcd_inh_04__create_with_a_workspace_id_that_is_no_workspace_id_fails_on_flush_and(db):
    """FCD-INH-04 — create with a workspace_id that is no workspace id fails on flush and saves no factory.
    Rules: inherited R2, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "name": "Main Plant", "abbreviation": "MP"})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factories_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 0


# [local-coder] FCD-INH-05
def test_fcd_inh_05__update_with_a_factoryupdate_that_sets_only_the_name_changes_only_the(db, mk_factory):
    """FCD-INH-05 — update with a FactoryUpdate that sets only the name changes only the name.
    Rules: inherited R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.update(db, db_obj=f1, obj_in=FactoryUpdate(name="B"))

    # Then 1
    assert result.id == f1.id
    # Then 2
    row = reread(db, f1)
    assert row.name == "B"
    # Then 3
    assert row.abbreviation == "MP"
    # Then 4
    assert row.is_active is True
    assert row.is_deleted is False


# [local-coder] FCD-INH-07
def test_fcd_inh_07__update_with_a_dict_can_switch_is_active_off_and_changes_nothing_else(db, mk_factory):
    """FCD-INH-07 — update with a dict can switch is_active off and changes nothing else.
    Rules: inherited R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = dao.update(db, db_obj=f1, obj_in={"is_active": False})

    # Then 1
    assert result.id == f1.id
    # Then 2
    row = reread(db, f1)
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    # Then 4
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FCD-INH-09
def test_fcd_inh_09__get_returns_a_soft_deleted_factory(db, mk_factory):
    """FCD-INH-09 — get returns a soft-deleted factory.
    Rules: inherited R4 (Q4)"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get(db, fd.id)

    # Then 1
    assert result.id == fd.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] FCD-INH-10
def test_fcd_inh_10__get_returns_a_soft_deleted_factory_of_another_workspace(db, w2, mk_factory):
    """FCD-INH-10 — get returns a soft-deleted factory of another workspace.
    Rules: inherited R4 (Q4)"""
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)

    result = dao.get(db, fd9.id)

    # Then 1
    assert result.id == fd9.id
    # Then 2
    assert result.is_deleted is True
    # Then 3
    assert result.workspace_id == w2.id
