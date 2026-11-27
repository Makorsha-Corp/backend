"""Unit tests for app/managers/factory_manager.py.

Implements tests/unit/managers/factory_manager.cases.md, one test per case.
Real Postgres session (`db` fixture). The only thing patched in every test is
the clock: `app.dao.factory.utcnow` returns NOW (Conventions, Externals). The
four race-simulation cards (FAC-C-31, C-32, U-50, U-51) additionally patch one
of the manager's own duplicate checks, as Conventions allow.

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/managers/factory_manager.helpers.md as its only view of this file;
tests below a `# [claude] <ID>` comment are the `Author: claude` cards, written
by hand in the finishing step.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import date, datetime
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
from sqlalchemy.exc import DataError, IntegrityError

from app.managers.factory_manager import FactoryManager, factory_manager
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.production_batch import ProductionBatch
from app.models.production_line import ProductionLine
from app.schemas.factory import FactoryCreate, FactoryUpdate
from tests.unit.factories import make_profile, make_subscription_plan, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton factory_manager" (a module-level name, not a fixture)
M = factory_manager

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T0", "NOW" (both naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 3, 1, 10, 0, 0)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (the five standing rows)
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows". Each fixture depends on the one
# before it, so the ids rise in the order Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "W3 = a third workspaces row whose subscription plan row has max_factories 1"
@pytest.fixture
def w3(db, w2):
    plan = make_subscription_plan(db, max_factories=1)
    return make_workspace(db, subscription_plan_id=plan.id)


# Convention "U1, U2 = two profiles rows" (U1 creates the Given factories, U2 acts)
@pytest.fixture
def u1(db, w3):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "W1, W2, W3, U1 and U2 exist in every test and need no Given line" and
# Externals "app.dao.factory.utcnow is patched to return NOW in every test"
@pytest.fixture(autouse=True)
def standing_rows(db, monkeypatch, w1, w2, w3, u1, u2):
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
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, Machine(**fields))
    return _mk


# Convention "section of F"
@pytest.fixture
def mk_section(db):
    """mk_section(of=<factory>, name=..., **columns) -> FactorySection. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name,
                  "is_active": True, "is_deleted": False}
        fields.update(columns)
        return _add(db, FactorySection(**fields))
    return _mk


# Convention "line of F"
@pytest.fixture
def mk_line(db):
    """mk_line(of=<factory>, name=..., **columns) -> ProductionLine. Keywords only."""
    def _mk(*, of, name, **columns):
        fields = {"workspace_id": of.workspace_id, "factory_id": of.id, "name": name, "is_active": True}
        fields.update(columns)
        return _add(db, ProductionLine(**fields))
    return _mk


# Convention "batch on L"
@pytest.fixture
def mk_batch(db):
    """mk_batch(on=<line>, batch_number=..., status=..., **columns) -> ProductionBatch. Keywords only."""
    def _mk(*, on, batch_number, status, **columns):
        fields = {"workspace_id": on.workspace_id, "production_line_id": on.id, "batch_number": batch_number,
                  "batch_date": date(2026, 2, 1), "status": status}
        fields.update(columns)
        return _add(db, ProductionBatch(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__ for model in (Factory, Machine, FactorySection, ProductionLine, ProductionBatch)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` (any model above) from the database, or None if it is gone."""
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


# Convention "nothing written": row counts of the five tables above, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "ids(result)" / "names(result)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in factory_manager.helpers.md)
# --------------------------------------------------------------------------- #

def test_fac_c_01__create_stores_a_factory_with_the_name_abbreviation_workspace_and(db, w1, u2):
    """FAC-C-01 — create stores a factory with the name, abbreviation, workspace and creator given.
    Rules: `create_factory` R1, Side effects"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, Factory)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 4
    assert row.workspace_id == w1.id
    # Then 5
    assert row.created_by == u2.id
    # Then 6
    assert count_rows(db, "factories") == 1


@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_18__an_empty_abbreviation_is_rejected_by_factorycreate(db):
    """FAC-C-18 — an empty abbreviation is rejected by FactoryCreate.
    Rules: `create_factory` R7a [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="Main Plant", abbreviation="")

    # Then 2
    assert count_rows(db, "factories") == 0


@pytest.mark.xfail(strict=True, reason="BUG-900: updated_by stamped on no-op factory updates")
def test_fac_u_34__an_empty_request_keeps_the_previous_updated_by(db, w1, u1, u2, mk_factory):
    """FAC-U-34 — an empty request keeps the previous updated_by.
    Rules: `update_factory` R11 [BUG-900]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.updated_by == u1.id
    # Then 3
    assert row.updated_at is None


def test_fac_u_43__a_factory_of_the_second_workspace_is_renamed_from_its_own_workspace(db, w2, u2, mk_factory):
    """FAC-U-43 — a factory of the second workspace is renamed from its own workspace.
    Rules: `update_factory` R4, R13"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f1 = snap(db, f1)

    result = M.update_factory(db, factory_id=f9.id, factory_data=FactoryUpdate(name="West Yard"), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result is f9
    # Then 2
    row = reread(db, f9)
    assert row.name == "West Yard"
    assert row.abbreviation == "FD"
    # Then 3
    assert row.workspace_id == w2.id
    assert row.updated_by == u2.id
    # Then 4
    assert snap(db, f1) == before_f1


def test_fac_s_38__a_matching_soft_deleted_factory_is_returned_by_a_search_with_include(db, w1, mk_factory):
    """FAC-S-38 — a matching soft-deleted factory is returned by a search with include_deleted=True.
    Rules: `search_factories` R8, R5 [BUG-901]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="plant", include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fd.id]


def test_fac_d_08__an_already_deleted_factory_is_answered_with_400_and_keeps_its(db, w1, u1, u2, mk_factory):
    """FAC-D-08 — an already deleted factory is answered with 400 and keeps its deletion stamp.
    Rules: `delete_factory` R2, Errors row 2"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_fd = snap(db, fd)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=fd.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory is already deleted"
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    row = reread(db, fd)
    assert row.deleted_at == T0
    # Then 6
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before


# [local-coder] FAC-C-02
def test_fac_c_02__a_new_factory_is_active_not_deleted_and_carries_no_update_or_deletion(db, w1, u2):
    """FAC-C-02 — a new factory is active, not deleted, and carries no update or deletion stamp.
    Rules: `create_factory` R2"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

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


# [local-coder] FAC-C-04
def test_fac_c_04__a_name_used_by_a_live_factory_of_the_workspace_is_refused_with_409(db, w1, u2, mk_factory):
    """FAC-C-04 — a name used by a live factory of the workspace is refused with 409.
    Rules: `create_factory` R3, Errors row 1, Side effects; `_check_name_exists` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 1
    # Then 6
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-15
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_15__a_name_of_three_spaces_is_rejected_by_factorycreate(db):
    """FAC-C-15 — a name of three spaces is rejected by FactoryCreate.
    Rules: `create_factory` R7 [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="   ", abbreviation="MP")

    # Then 2
    assert count_rows(db, "factories") == 0


# [local-coder] FAC-C-34
def test_fac_c_34__a_user_id_that_is_no_profile_id_fails_on_flush_and_no_factory_is_saved(db, w1):
    """FAC-C-34 — a user_id that is no profile id fails on flush and no factory is saved.
    Rules: `create_factory` R10, Errors row 4"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factories_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 0


# [local-coder] FAC-U-01
def test_fac_u_01__a_new_name_is_stored_and_the_editor_is_recorded(db, w1, u2, mk_factory):
    """FAC-U-01 — a new name is stored and the editor is recorded.
    Rules: `update_factory` R4, R11, R12, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "North Yard"
    # Then 3
    assert row.abbreviation == "MP"
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-U-06
def test_fac_u_06__a_soft_deleted_factory_is_answered_with_400_and_not_changed(db, w1, u2, mk_factory):
    """FAC-U-06 — a soft-deleted factory is answered with 400 and not changed.
    Rules: `update_factory` R3, Errors row 2"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_fd = snap(db, fd)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=fd.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory"
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    row = reread(db, fd)
    assert row.name == "Old Plant"
    assert row.updated_by is None
    # Then 6
    assert written(db) == before


# [local-coder] FAC-U-31
@pytest.mark.xfail(strict=True, reason="BUG-900: updated_by stamped on no-op factory updates")
def test_fac_u_31__an_empty_request_does_not_stamp_updated_by(db, w1, u2, mk_factory):
    """FAC-U-31 — an empty request does not stamp updated_by.
    Rules: `update_factory` R11 [BUG-900]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] FAC-U-38
def test_fac_u_38__nothing_but_the_name_and_the_update_stamp_is_modified_and_the_other(db, w1, u1, u2, mk_factory):
    """FAC-U-38 — nothing but the name and the update stamp is modified, and the other factory is untouched.
    Rules: `update_factory` R13, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", is_active=False)
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)
    created_before = f1.created_at

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "North Yard"
    assert row.abbreviation == "MP"
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.is_active is False
    assert row.is_deleted is False
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert row.created_at == created_before
    # Then 7
    assert snap(db, f2) == before_f2
    # Then 8
    row2 = reread(db, f2)
    assert row2.updated_at is None
    assert row2.updated_by is None
    # Then 9
    assert count_rows(db, "factories") == 2


# [local-coder] FAC-U-44
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_u_44__a_new_name_that_differs_only_in_case_from_another_live_factory_s_name(db, w1, u2, mk_factory):
    """FAC-U-44 — a new name that differs only in case from another live factory's name is refused with 409.
    Rules: `update_factory` R6, Errors row 3; `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="MAIN PLANT"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'MAIN PLANT' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.name == "Second"


# [local-coder] FAC-G-01
def test_fac_g_01__a_live_factory_of_the_workspace_is_returned_and_nothing_is_changed(db, w1, mk_factory):
    """FAC-G-01 — a live factory of the workspace is returned and nothing is changed.
    Rules: `get_factory` R1, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    result = M.get_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Factory)
    # Then 2
    assert result.id == f1.id
    # Then 3
    assert result.name == "Main Plant"
    assert result.abbreviation == "MP"
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    assert written(db) == before


# [local-coder] FAC-G-07
@pytest.mark.xfail(strict=True, reason="BUG-897: get_factory returns soft-deleted factories")
def test_fac_g_07__include_deleted_true_returns_a_soft_deleted_factory_of_the_workspace(db, w1, mk_factory):
    """FAC-G-07 — include_deleted=True returns a soft-deleted factory of the workspace.
    Rules: `get_factory` R4 [BUG-897]"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = M.get_factory(db, factory_id=fd.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == fd.id
    # Then 2
    assert result.is_deleted is True


# [local-coder] FAC-S-01
def test_fac_s_01__without_a_search_every_factory_of_the_workspace_is_returned_as_a_list(db, w1, mk_factory):
    """FAC-S-01 — without a search every factory of the workspace is returned as a list.
    Rules: `search_factories` R1, R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]
    # Then 3
    assert isinstance(result[0], Factory)


# [local-coder] FAC-S-08
def test_fac_s_08__include_deleted_true_lists_soft_deleted_factories_along_with_live_ones(db, w1, mk_factory):
    """FAC-S-08 — include_deleted=True lists soft-deleted factories along with live ones.
    Rules: `search_factories` R5 [BUG-901]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = M.search_factories(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fd.id]


# [local-coder] FAC-S-09
def test_fac_s_09__include_deleted_true_does_not_list_a_soft_deleted_factory_of_another(db, w1, w2, mk_factory):
    """FAC-S-09 — include_deleted=True does not list a soft-deleted factory of another workspace.
    Rules: `search_factories` R5 [BUG-901], R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)

    result = M.search_factories(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-36
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fac_s_36__a_tab_before_and_a_newline_after_the_search_text_are_removed_before(db, w1, mk_factory):
    """FAC-S-36 — a tab before and a newline after the search text are removed before matching.
    Rules: `search_factories` R7 [BUG-902]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="\tPLANT\n")

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-45
def test_fac_s_45__a_negative_limit_is_rejected_by_the_database(db, w1, mk_factory):
    """FAC-S-45 — a negative limit is rejected by the database.
    Rules: `search_factories` R9, Errors row 1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factories(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] FAC-D-01
def test_fac_d_01__a_live_factory_is_marked_deleted_with_the_clock_value_and_the_acting(db, w1, u2, mk_factory):
    """FAC-D-01 — a live factory is marked deleted with the clock value and the acting user.
    Rules: `delete_factory` R3, R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

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
    assert row.is_active is True
    # Then 6
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-D-09
def test_fac_d_09__a_factory_with_machines_is_deleted_and_its_machines_are_left_exactly(db, w1, u2, mk_factory, mk_machine):
    """FAC-D-09 — a factory with machines is deleted and its machines are left exactly as they were.
    Rules: `delete_factory` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    ma1 = mk_machine(of=f1, name="Lathe")
    ma2 = mk_machine(of=f1, name="Press", is_active=False)
    before_ma1 = snap(db, ma1)
    before_ma2 = snap(db, ma2)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, ma1) == before_ma1
    # Then 4
    row_ma1 = reread(db, ma1)
    assert row_ma1.is_deleted is False
    assert row_ma1.is_active is True
    # Then 5
    assert snap(db, ma2) == before_ma2
    # Then 6
    row_ma2 = reread(db, ma2)
    assert row_ma2.is_deleted is False
    assert row_ma2.is_active is False
    # Then 7
    assert count_rows(db, "machines") == 2


# [local-coder] FAC-D-12
def test_fac_d_12__after_the_delete_the_name_and_the_abbreviation_count_as_free(db, w1, u2, mk_factory):
    """FAC-D-12 — after the delete the name and the abbreviation count as free.
    Rules: `delete_factory` R6; `_check_name_exists` R3; `_check_abbreviation_exists` R3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    assert M._check_name_exists(db, workspace_id=w1.id, name="Main Plant") is False
    # Then 3
    assert M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP") is False


# [local-coder] FAC-CN-01
def test_fac_cn_01__a_live_factory_of_the_workspace_with_that_name_gives_true_and_nothing(db, w1, mk_factory):
    """FAC-CN-01 — a live factory of the workspace with that name gives True and nothing is changed.
    Rules: `_check_name_exists` R1, R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)
    before = written(db)

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant")

    # Then 1
    assert result is True
    # Then 2
    assert snap(db, f1) == before_f1
    # Then 3
    assert written(db) == before


# [local-coder] FAC-CA-10
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_ca_10__the_abbreviation_with_a_trailing_newline_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CA-10 — the abbreviation with a trailing newline matches the live factory.
    Rules: `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP\n")

    # Then 1
    assert result is True


# [local-coder] FAC-C-03
def test_fac_c_03__the_factory_is_created_in_the_workspace_passed_as_argument(db, w2, u2, mk_factory):
    """FAC-C-03 — the factory is created in the workspace passed as argument.
    Rules: `create_factory` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    result = M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.name == "North Yard"
    assert row.abbreviation == "NY"
    # Then 3
    assert count_rows(db, "factories") == 2
    # Then 4
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-05
def test_fac_c_05__an_abbreviation_used_by_a_live_factory_of_the_workspace_is_refused(db, w1, u2, mk_factory):
    """FAC-C-05 — an abbreviation used by a live factory of the workspace is refused with 409.
    Rules: `create_factory` R4, Errors row 2; `_check_abbreviation_exists` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 1
    # Then 6
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-06
def test_fac_c_06__name_and_abbreviation_both_taken_by_one_factory_the_name_error_is(db, w1, u2, mk_factory):
    """FAC-C-06 — name and abbreviation both taken by one factory: the name error is raised.
    Rules: `create_factory` R5"""
    mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-C-07
def test_fac_c_07__name_taken_by_one_factory_and_abbreviation_by_another_the_name_error(db, w1, u2, mk_factory):
    """FAC-C-07 — name taken by one factory and abbreviation by another: the name error is raised.
    Rules: `create_factory` R5"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="North Yard", abbreviation="NY")
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="NY"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 2


# [local-coder] FAC-C-08
def test_fac_c_08__the_same_name_and_abbreviation_in_another_workspace_do_not_block_the(db, w1, w2, u2, mk_factory):
    """FAC-C-08 — the same name and abbreviation in another workspace do not block the create.
    Rules: `create_factory` R6; `_check_name_exists` R2; `_check_abbreviation_exists` R2"""
    f9 = mk_factory(name="Main Plant", abbreviation="MP", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != f9.id
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 4
    assert count_rows(db, "factories") == 2
    # Then 5
    assert snap(db, f9) == before_f9


# [local-coder] FAC-C-09
def test_fac_c_09__the_name_and_abbreviation_of_a_soft_deleted_factory_can_be_used_again(db, w1, u2, mk_factory):
    """FAC-C-09 — the name and abbreviation of a soft-deleted factory can be used again.
    Rules: `create_factory` R6; `_check_name_exists` R3; `_check_abbreviation_exists` R3"""
    fd = mk_factory(name="Main Plant", abbreviation="MP", deleted=True)
    before_fd = snap(db, fd)

    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.id != fd.id
    # Then 3
    row = reread(db, result)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    assert row.is_deleted is False
    # Then 4
    assert count_rows(db, "factories") == 2
    # Then 5
    assert snap(db, fd) == before_fd
    # Then 6
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is True


# [local-coder] FAC-C-10
def test_fac_c_10__a_name_equal_to_another_factory_s_abbreviation_is_accepted(db, w1, u2, mk_factory):
    """FAC-C-10 — a name equal to another factory's abbreviation is accepted.
    Rules: `create_factory` R6; `_check_name_exists` R7"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M.create_factory(db, factory_data=FactoryCreate(name="MP", abbreviation="MX"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "MP"
    assert row.abbreviation == "MX"
    # Then 3
    assert count_rows(db, "factories") == 2


# [local-coder] FAC-C-11
def test_fac_c_11__an_abbreviation_equal_to_another_factory_s_name_is_accepted(db, w1, u2, mk_factory):
    """FAC-C-11 — an abbreviation equal to another factory's name is accepted.
    Rules: `create_factory` R6; `_check_abbreviation_exists` R7"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="Main Plant"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "North Yard"
    assert row.abbreviation == "Main Plant"
    # Then 3
    assert count_rows(db, "factories") == 2


# [local-coder] FAC-C-12
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_12__the_name_is_stored_trimmed(db, w1, u2):
    """FAC-C-12 — the name is stored trimmed.
    Rules: `create_factory` R7 [BUG-896]"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="  Main Plant ", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Main Plant"


# [local-coder] FAC-C-13
def test_fac_c_13__inner_whitespace_and_case_of_the_name_and_the_abbreviation_are_kept(db, w1, u2):
    """FAC-C-13 — inner whitespace and case of the name and the abbreviation are kept.
    Rules: `create_factory` R1, R7, R7a"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="main  PLANT", abbreviation="mP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "main  PLANT"
    # Then 3
    assert row.abbreviation == "mP"


# [local-coder] FAC-C-14
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_14__an_empty_name_is_rejected_by_factorycreate(db):
    """FAC-C-14 — an empty name is rejected by FactoryCreate.
    Rules: `create_factory` R7 [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="", abbreviation="MP")

    # Then 2
    assert count_rows(db, "factories") == 0


# [local-coder] FAC-C-16
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_16__a_name_of_one_tab_is_rejected_by_factorycreate(db):
    """FAC-C-16 — a name of one tab is rejected by FactoryCreate.
    Rules: `create_factory` R7 [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="\t", abbreviation="MP")

    # Then 2
    assert count_rows(db, "factories") == 0


# [local-coder] FAC-C-17
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_17__the_abbreviation_is_stored_trimmed_with_its_case_kept(db, w1, u2):
    """FAC-C-17 — the abbreviation is stored trimmed with its case kept.
    Rules: `create_factory` R7a [BUG-896]"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation=" mp "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.abbreviation == "mp"


# [local-coder] FAC-C-19
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_19__an_abbreviation_of_two_spaces_is_rejected_by_factorycreate(db):
    """FAC-C-19 — an abbreviation of two spaces is rejected by FactoryCreate.
    Rules: `create_factory` R7a [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="Main Plant", abbreviation="  ")

    # Then 2
    assert count_rows(db, "factories") == 0


# [local-coder] FAC-C-20
def test_fac_c_20__a_one_character_name_and_abbreviation_are_accepted_by_factorycreate():
    """FAC-C-20 — a one-character name and abbreviation are accepted by FactoryCreate.
    Rules: `create_factory` R7, R7a"""
    result = FactoryCreate(name="a", abbreviation="b")

    # Then 1
    assert result.name == "a"
    # Then 2
    assert result.abbreviation == "b"


# [local-coder] FAC-C-21
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_c_21__a_name_that_differs_only_in_case_from_a_live_factory_s_name_is(db, w1, u2, mk_factory):
    """FAC-C-21 — a name that differs only in case from a live factory's name is refused with 409.
    Rules: `create_factory` R3, Errors row 1; `_check_name_exists` R4 [BUG-894]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="main plant", abbreviation="MX"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'main plant' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-22
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_22__a_name_that_differs_only_by_a_trailing_space_is_refused_with_409_and(db, w1, u2, mk_factory):
    """FAC-C-22 — a name that differs only by a trailing space is refused with 409 and the trimmed name in the message.
    Rules: `create_factory` R3, R7 [BUG-896]; `_check_name_exists` R4 [BUG-894]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Main Plant ", abbreviation="MX"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-23
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_c_23__an_abbreviation_that_differs_only_in_case_from_a_live_factory_s(db, w1, u2, mk_factory):
    """FAC-C-23 — an abbreviation that differs only in case from a live factory's abbreviation is refused with 409.
    Rules: `create_factory` R4, Errors row 2; `_check_abbreviation_exists` R4 [BUG-894]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="mp"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'mp' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-24
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_c_24__an_abbreviation_that_differs_only_by_outer_spaces_is_refused_with_409(db, w1, u2, mk_factory):
    """FAC-C-24 — an abbreviation that differs only by outer spaces is refused with 409 and the trimmed value in the message.
    Rules: `create_factory` R4, R7a [BUG-896]; `_check_abbreviation_exists` R4 [BUG-894]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation=" MP "), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [claude] FAC-C-25
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_c_25__a_duplicate_name_is_refused_also_when_the_live_factory_is_the_101st(db, w1, u2, mk_factory):
    """FAC-C-25 — a duplicate name is refused also when the live factory is the 101st row of the workspace.
    Rules: `create_factory` R3; `_check_name_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Late", abbreviation="LX"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Late' already exists"
    # Then 4
    assert count_rows(db, "factories") == 101


# [claude] FAC-C-26
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_c_26__a_duplicate_abbreviation_is_refused_also_when_the_live_factory_is_the(db, w1, u2, mk_factory):
    """FAC-C-26 — a duplicate abbreviation is refused also when the live factory is the 101st row of the workspace.
    Rules: `create_factory` R4; `_check_abbreviation_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_factory(db, factory_data=FactoryCreate(name="Other", abbreviation="LT"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'LT' already exists"
    # Then 4
    assert count_rows(db, "factories") == 101


# [claude] FAC-C-27
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_c_27__the_database_refuses_a_second_live_row_whose_name_differs_only_in_case(db, w1, u1, mk_factory):
    """FAC-C-27 — the database refuses a second live row whose name differs only in case.
    Rules: `create_factory` R8 [BUG-895]"""
    mk_factory(name="Main Plant", abbreviation="MP")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Factory(workspace_id=w1.id, name="main plant", abbreviation="MX", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "factories") == 1


# [claude] FAC-C-28
def test_fac_c_28__the_database_accepts_a_soft_deleted_row_with_the_name_and(db, w1, u1, mk_factory):
    """FAC-C-28 — the database accepts a soft-deleted row with the name and abbreviation of a live factory.
    Rules: `create_factory` R8, R8a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    db.add(Factory(workspace_id=w1.id, name="Main Plant", abbreviation="MP", created_by=u1.id, is_deleted=True, deleted_at=T0, deleted_by=u1.id))
    db.flush()

    # Then 1
    assert count_rows(db, "factories") == 2
    # Then 2
    assert snap(db, f1) == before_f1


# [claude] FAC-C-29
def test_fac_c_29__the_database_accepts_a_row_of_another_workspace_with_the_name_and(db, w2, u1, mk_factory):
    """FAC-C-29 — the database accepts a row of another workspace with the name and abbreviation of a live factory.
    Rules: `create_factory` R8, R8a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    db.add(Factory(workspace_id=w2.id, name="Main Plant", abbreviation="MP", created_by=u1.id))
    db.flush()

    # Then 1
    assert count_rows(db, "factories") == 2
    # Then 2
    assert snap(db, f1) == before_f1


# [claude] FAC-C-30
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_c_30__the_database_refuses_a_second_live_row_whose_abbreviation_differs(db, w1, u1, mk_factory):
    """FAC-C-30 — the database refuses a second live row whose abbreviation differs only in case.
    Rules: `create_factory` R8a [BUG-895]"""
    mk_factory(name="Main Plant", abbreviation="MP")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Factory(workspace_id=w1.id, name="North Yard", abbreviation="mp", created_by=u1.id))
            db.flush()

    # Then 2
    assert count_rows(db, "factories") == 1


# [claude] FAC-C-31
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_c_31__a_duplicate_name_that_passed_the_python_check_is_answered_with_409(db, w1, u2, mk_factory):
    """FAC-C-31 — a duplicate name that passed the Python check is answered with 409, not a database error.
    Rules: `create_factory` R8 [BUG-895], Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    with patch.object(FactoryManager, "_check_name_exists", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [claude] FAC-C-32
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_c_32__a_duplicate_abbreviation_that_passed_the_python_check_is_answered(db, w1, u2, mk_factory):
    """FAC-C-32 — a duplicate abbreviation that passed the Python check is answered with 409, not a database error.
    Rules: `create_factory` R8a [BUG-895], Errors row 2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    with patch.object(FactoryManager, "_check_abbreviation_exists", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert count_rows(db, "factories") == 1
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-C-33
def test_fac_c_33__a_third_factory_is_created_in_a_workspace_whose_plan_allows_one(db, w3, u2, mk_factory):
    """FAC-C-33 — a third factory is created in a workspace whose plan allows one factory.
    Rules: `create_factory` R9"""
    mk_factory(name="Main Plant", abbreviation="MP", workspace_id=w3.id)
    mk_factory(name="North Yard", abbreviation="NY", workspace_id=w3.id)

    result = M.create_factory(db, factory_data=FactoryCreate(name="South Dock", abbreviation="SD"), workspace_id=w3.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w3.id
    assert row.name == "South Dock"
    assert row.abbreviation == "SD"
    # Then 3
    assert count_rows(db, "factories") == 3


# [local-coder] FAC-C-35
def test_fac_c_35__a_workspace_id_that_is_no_workspace_id_fails_on_flush_and_no_factory(db, u2):
    """FAC-C-35 — a workspace_id that is no workspace id fails on flush and no factory is saved.
    Rules: `create_factory` R10, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=MISSING, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "factories_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "factories") == 0


# [claude] FAC-C-36
def test_fac_c_36__the_create_is_flushed_but_not_committed_a_rollback_removes_the(db, w1, u2):
    """FAC-C-36 — the create is flushed but not committed: a rollback removes the factory.
    Rules: `create_factory` Side effects"""
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert count_rows(db, "factories") == 1
        sp.rollback()
        # Then 2
        assert count_rows(db, "factories") == 0
        # Then 3
        assert commit_spy.call_count == 0


# [local-coder] FAC-U-02
def test_fac_u_02__a_new_abbreviation_is_stored_and_the_name_is_kept(db, w1, u2, mk_factory):
    """FAC-U-02 — a new abbreviation is stored and the name is kept.
    Rules: `update_factory` R4, R9, R11, R12"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(abbreviation="NY"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.abbreviation == "NY"
    # Then 3
    assert row.name == "Main Plant"
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert row.updated_at is not None


# [local-coder] FAC-U-03
def test_fac_u_03__name_and_abbreviation_are_changed_in_one_call(db, w1, u2, mk_factory):
    """FAC-U-03 — name and abbreviation are changed in one call.
    Rules: `update_factory` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard", abbreviation="NY"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "North Yard"
    assert row.abbreviation == "NY"
    # Then 3
    assert row.updated_by == u2.id


# [local-coder] FAC-U-04
def test_fac_u_04__an_id_that_no_factory_has_is_answered_with_404(db, w1, u2, mk_factory):
    """FAC-U-04 — an id that no factory has is answered with 404.
    Rules: `update_factory` R1, Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=MISSING, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-05
def test_fac_u_05__a_factory_of_another_workspace_is_answered_with_404_and_not_changed(db, w1, w2, u2, mk_factory):
    """FAC-U-05 — a factory of another workspace is answered with 404 and not changed.
    Rules: `update_factory` R2, Errors row 1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f9.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert snap(db, f9) == before_f9
    # Then 5
    row = reread(db, f9)
    assert row.name == "Far Depot"
    assert row.updated_by is None


# [local-coder] FAC-U-07
def test_fac_u_07__a_soft_deleted_factory_is_answered_with_400_also_when_the_requested(db, w1, u2, mk_factory):
    """FAC-U-07 — a soft-deleted factory is answered with 400 also when the requested name is taken.
    Rules: `update_factory` R3"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_fd = snap(db, fd)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=fd.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory"
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-08
def test_fac_u_08__a_soft_deleted_factory_is_answered_with_400_also_for_an_empty_request(db, w1, u2, mk_factory):
    """FAC-U-08 — a soft-deleted factory is answered with 400 also for an empty request.
    Rules: `update_factory` R3"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_fd = snap(db, fd)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=fd.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory"
    # Then 4
    assert snap(db, fd) == before_fd


# [local-coder] FAC-U-09
def test_fac_u_09__a_soft_deleted_factory_of_another_workspace_is_answered_with_404_not(db, w1, w2, u2, mk_factory):
    """FAC-U-09 — a soft-deleted factory of another workspace is answered with 404, not 400.
    Rules: `update_factory` R2"""
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)
    before_fd9 = snap(db, fd9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=fd9.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd9.id} not found"
    # Then 4
    assert snap(db, fd9) == before_fd9


# [local-coder] FAC-U-10
def test_fac_u_10__sending_the_current_name_is_accepted_and_the_name_stays(db, w1, u2, mk_factory):
    """FAC-U-10 — sending the current name is accepted and the name stays.
    Rules: `update_factory` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-U-11
def test_fac_u_11__sending_the_current_abbreviation_is_accepted_and_the_abbreviation(db, w1, u2, mk_factory):
    """FAC-U-11 — sending the current abbreviation is accepted and the abbreviation stays.
    Rules: `update_factory` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-U-12
def test_fac_u_12__changing_only_the_case_of_the_factory_s_own_name_is_stored(db, w1, u2, mk_factory):
    """FAC-U-12 — changing only the case of the factory's own name is stored.
    Rules: `update_factory` R5; `_check_name_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)

    result = M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="SECOND"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f2
    # Then 2
    row = reread(db, f2)
    assert row.name == "SECOND"
    # Then 3
    assert row.abbreviation == "SC"
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-13
def test_fac_u_13__changing_only_the_case_of_the_factory_s_own_abbreviation_is_stored(db, w1, u2, mk_factory):
    """FAC-U-13 — changing only the case of the factory's own abbreviation is stored.
    Rules: `update_factory` R5; `_check_abbreviation_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)

    result = M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation="sc"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f2
    # Then 2
    row = reread(db, f2)
    assert row.abbreviation == "sc"
    # Then 3
    assert row.name == "Second"
    # Then 4
    assert row.updated_by == u2.id
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-14
def test_fac_u_14__a_name_used_by_another_live_factory_is_refused_with_409_and_the(db, w1, u2, mk_factory):
    """FAC-U-14 — a name used by another live factory is refused with 409 and the abbreviation sent with it is not applied.
    Rules: `update_factory` R6, Errors row 3, Side effects; `_check_name_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="S2"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.name == "Second"
    assert row.abbreviation == "SC"
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    assert written(db) == before


# [local-coder] FAC-U-15
def test_fac_u_15__an_abbreviation_used_by_another_live_factory_is_refused_with_409_and(db, w1, u2, mk_factory):
    """FAC-U-15 — an abbreviation used by another live factory is refused with 409 and the name sent with it is not applied.
    Rules: `update_factory` R7, Errors row 4; `_check_abbreviation_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Third", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.name == "Second"
    assert row.abbreviation == "SC"
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    assert written(db) == before


# [local-coder] FAC-U-16
def test_fac_u_16__a_taken_abbreviation_is_refused_with_409_when_no_name_is_sent(db, w1, u2, mk_factory):
    """FAC-U-16 — a taken abbreviation is refused with 409 when no name is sent.
    Rules: `update_factory` R7"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.abbreviation == "SC"


# [local-coder] FAC-U-17
def test_fac_u_17__a_taken_abbreviation_is_refused_with_409_when_the_current_name_is(db, w1, u2, mk_factory):
    """FAC-U-17 — a taken abbreviation is refused with 409 when the current name is sent with it.
    Rules: `update_factory` R7, R5"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Second", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.abbreviation == "SC"


# [local-coder] FAC-U-18
def test_fac_u_18__new_name_and_new_abbreviation_both_taken_the_name_error_is_raised(db, w1, u2, mk_factory):
    """FAC-U-18 — new name and new abbreviation both taken: the name error is raised.
    Rules: `update_factory` R8"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")
    f3 = mk_factory(name="Third", abbreviation="TH")
    before_f3 = snap(db, f3)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f3.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="SC"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert snap(db, f3) == before_f3
    # Then 5
    row = reread(db, f3)
    assert row.name == "Third"
    assert row.abbreviation == "TH"


# [local-coder] FAC-U-19
def test_fac_u_19__an_explicit_null_name_is_left_unchanged_while_the_abbreviation_is(db, w1, u2, mk_factory):
    """FAC-U-19 — an explicit null name is left unchanged while the abbreviation is changed.
    Rules: `update_factory` R9"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name=None, abbreviation="T4"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    # Then 3
    assert row.abbreviation == "T4"
    # Then 4
    assert row.updated_by == u2.id


# [local-coder] FAC-U-20
def test_fac_u_20__an_explicit_null_abbreviation_is_left_unchanged_while_the_name_is(db, w1, u2, mk_factory):
    """FAC-U-20 — an explicit null abbreviation is left unchanged while the name is changed.
    Rules: `update_factory` R9"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="Fourth", abbreviation=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Fourth"
    # Then 3
    assert row.abbreviation == "MP"
    # Then 4
    assert row.updated_by == u2.id


# [local-coder] FAC-U-21
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_21__a_sent_name_is_stored_trimmed(db, w1, u2, mk_factory):
    """FAC-U-21 — a sent name is stored trimmed.
    Rules: `update_factory` R10 [BUG-896]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name=" Ops "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Ops"


# [local-coder] FAC-U-22
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_22__the_current_name_sent_with_outer_spaces_counts_as_the_current_name(db, w1, u2, mk_factory):
    """FAC-U-22 — the current name sent with outer spaces counts as the current name.
    Rules: `update_factory` R10 [BUG-896], R5"""
    f1 = mk_factory(name="Ops", abbreviation="OP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name=" Ops "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Ops"


# [local-coder] FAC-U-23
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_23__an_empty_name_is_rejected_by_factoryupdate(db, mk_factory):
    """FAC-U-23 — an empty name is rejected by FactoryUpdate.
    Rules: `update_factory` R10 [BUG-896], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(ValidationError):
        FactoryUpdate(name="")

    # Then 2
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-24
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_24__a_name_of_three_spaces_is_rejected_by_factoryupdate(db, mk_factory):
    """FAC-U-24 — a name of three spaces is rejected by FactoryUpdate.
    Rules: `update_factory` R10 [BUG-896], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(ValidationError):
        FactoryUpdate(name="   ")

    # Then 2
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-25
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_25__a_name_of_one_tab_is_rejected_by_factoryupdate(db, mk_factory):
    """FAC-U-25 — a name of one tab is rejected by FactoryUpdate.
    Rules: `update_factory` R10 [BUG-896], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(ValidationError):
        FactoryUpdate(name="\t")

    # Then 2
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-26
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_26__a_sent_abbreviation_is_stored_trimmed_with_its_case_kept(db, w1, u2, mk_factory):
    """FAC-U-26 — a sent abbreviation is stored trimmed with its case kept.
    Rules: `update_factory` R10a [BUG-896]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(abbreviation=" t4 "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.abbreviation == "t4"


# [local-coder] FAC-U-27
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_27__an_empty_abbreviation_is_rejected_by_factoryupdate(db, mk_factory):
    """FAC-U-27 — an empty abbreviation is rejected by FactoryUpdate.
    Rules: `update_factory` R10a [BUG-896], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(ValidationError):
        FactoryUpdate(abbreviation="")

    # Then 2
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-28
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_28__an_abbreviation_of_two_spaces_is_rejected_by_factoryupdate(db, mk_factory):
    """FAC-U-28 — an abbreviation of two spaces is rejected by FactoryUpdate.
    Rules: `update_factory` R10a [BUG-896], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(ValidationError):
        FactoryUpdate(abbreviation="  ")

    # Then 2
    assert snap(db, f1) == before_f1


# [local-coder] FAC-U-29
def test_fac_u_29__a_one_character_name_and_abbreviation_are_accepted_by_factoryupdate():
    """FAC-U-29 — a one-character name and abbreviation are accepted by FactoryUpdate.
    Rules: `update_factory` R10, R10a"""
    result = FactoryUpdate(name="a", abbreviation="b")

    # Then 1
    assert result.name == "a"
    # Then 2
    assert result.abbreviation == "b"


# [local-coder] FAC-U-30
def test_fac_u_30__factoryupdate_without_fields_has_name_none_and_abbreviation_none():
    """FAC-U-30 — FactoryUpdate without fields has name None and abbreviation None.
    Rules: `update_factory` R9"""
    result = FactoryUpdate()

    # Then 1
    assert result.name is None
    # Then 2
    assert result.abbreviation is None


# [local-coder] FAC-U-32
@pytest.mark.xfail(strict=True, reason="BUG-900: updated_by stamped on no-op factory updates")
def test_fac_u_32__a_request_with_only_null_fields_does_not_stamp_updated_by(db, w1, u2, mk_factory):
    """FAC-U-32 — a request with only null fields does not stamp updated_by.
    Rules: `update_factory` R11 [BUG-900]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name=None, abbreviation=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] FAC-U-33
@pytest.mark.xfail(strict=True, reason="BUG-900: updated_by stamped on no-op factory updates")
def test_fac_u_33__a_request_with_the_current_values_does_not_stamp_updated_by(db, w1, u2, mk_factory):
    """FAC-U-33 — a request with the current values does not stamp updated_by.
    Rules: `update_factory` R11 [BUG-900]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert row.updated_by is None
    # Then 4
    assert row.updated_at is None


# [local-coder] FAC-U-35
def test_fac_u_35__an_empty_request_succeeds_and_leaves_name_and_abbreviation_as_they_are(db, w1, u2, mk_factory):
    """FAC-U-35 — an empty request succeeds and leaves name and abbreviation as they are.
    Rules: `update_factory` R9, R11"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-U-36
def test_fac_u_36__a_request_with_only_null_fields_succeeds_and_leaves_name_and(db, w1, u2, mk_factory):
    """FAC-U-36 — a request with only null fields succeeds and leaves name and abbreviation as they are.
    Rules: `update_factory` R9, R11"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name=None, abbreviation=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 3
    assert count_rows(db, "factories") == 1


# [local-coder] FAC-U-37
def test_fac_u_37__a_real_change_replaces_a_previous_updated_by_with_the_acting_user(db, w1, u1, u2, mk_factory):
    """FAC-U-37 — a real change replaces a previous updated_by with the acting user.
    Rules: `update_factory` R11, R12"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "North Yard"
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None


# [local-coder] FAC-U-39
def test_fac_u_39__the_name_and_abbreviation_of_a_soft_deleted_factory_can_be_taken_over(db, w1, u2, mk_factory):
    """FAC-U-39 — the name and abbreviation of a soft-deleted factory can be taken over.
    Rules: `update_factory` R15; `_check_name_exists` R3; `_check_abbreviation_exists` R3"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_fd = snap(db, fd)

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="Old Plant", abbreviation="OP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Old Plant"
    assert row.abbreviation == "OP"
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    row_fd = reread(db, fd)
    assert row_fd.is_deleted is True


# [local-coder] FAC-U-40
def test_fac_u_40__the_name_and_abbreviation_of_a_factory_of_another_workspace_can_be(db, w1, w2, u2, mk_factory):
    """FAC-U-40 — the name and abbreviation of a factory of another workspace can be taken over.
    Rules: `update_factory` R15; `_check_name_exists` R2; `_check_abbreviation_exists` R2"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="Far Depot", abbreviation="FD"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.name == "Far Depot"
    assert row.abbreviation == "FD"
    # Then 3
    assert snap(db, f9) == before_f9


# [local-coder] FAC-U-41
def test_fac_u_41__a_change_by_a_user_id_that_is_no_profile_id_fails_on_flush_and(db, w1, mk_factory):
    """FAC-U-41 — a change by a user_id that is no profile id fails on flush and nothing is saved.
    Rules: `update_factory` R16, Errors row 6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)

    # Then 3
    assert snap(db, f1) == before_f1

    # Then 4
    row = reread(db, f1)
    assert row.name == "Main Plant"
    assert row.updated_by is None

    # Then 5
    assert written(db) == before


# [local-coder] FAC-U-42
@pytest.mark.xfail(strict=True, reason="BUG-900: updated_by stamped on no-op factory updates")
def test_fac_u_42__an_empty_request_by_a_user_id_that_is_no_profile_id_succeeds_because(db, w1, mk_factory):
    """FAC-U-42 — an empty request by a user_id that is no profile id succeeds, because nothing is stamped.
    Rules: `update_factory` R11 [BUG-900], R16"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.updated_by is None


# [local-coder] FAC-U-45
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_45__a_new_name_that_differs_only_by_a_trailing_space_is_refused_with_409(db, w1, u2, mk_factory):
    """FAC-U-45 — a new name that differs only by a trailing space is refused with 409 and the trimmed name in the message.
    Rules: `update_factory` R6, R10 [BUG-896]; `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Main Plant "), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.name == "Second"


# [local-coder] FAC-U-46
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_u_46__a_new_abbreviation_that_differs_only_in_case_from_another_live(db, w1, u2, mk_factory):
    """FAC-U-46 — a new abbreviation that differs only in case from another live factory's abbreviation is refused with 409.
    Rules: `update_factory` R7, Errors row 4; `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation="mp"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'mp' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.abbreviation == "SC"


# [local-coder] FAC-U-47
@pytest.mark.xfail(strict=True, reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed")
def test_fac_u_47__a_new_abbreviation_that_differs_only_by_outer_spaces_is_refused_with(db, w1, u2, mk_factory):
    """FAC-U-47 — a new abbreviation that differs only by outer spaces is refused with 409 and the trimmed value in the message.
    Rules: `update_factory` R7, R10a [BUG-896]; `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation=" MP "), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.abbreviation == "SC"


# [claude] FAC-U-48
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_u_48__a_rename_to_a_taken_name_is_refused_also_when_its_live_owner_is_the(db, w1, u2, mk_factory):
    """FAC-U-48 — a rename to a taken name is refused also when its live owner is the 101st row of the workspace.
    Rules: `update_factory` R6; `_check_name_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")
    f2 = mk_factory(name="Second", abbreviation="SC")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Late"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Late' already exists"
    # Then 4
    row = reread(db, f2)
    assert row.name == "Second"
    # Then 5
    assert count_rows(db, "factories") == 102


# [claude] FAC-U-49
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_u_49__a_change_to_a_taken_abbreviation_is_refused_also_when_its_live_owner(db, w1, u2, mk_factory):
    """FAC-U-49 — a change to a taken abbreviation is refused also when its live owner is the 101st row of the workspace.
    Rules: `update_factory` R7; `_check_abbreviation_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")
    f2 = mk_factory(name="Second", abbreviation="SC")

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation="LT"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'LT' already exists"
    # Then 4
    row = reread(db, f2)
    assert row.abbreviation == "SC"
    # Then 5
    assert count_rows(db, "factories") == 102


# [claude] FAC-U-50
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_u_50__a_rename_to_a_taken_name_that_passed_the_python_check_is_answered(db, w1, u2, mk_factory):
    """FAC-U-50 — a rename to a taken name that passed the Python check is answered with 409, not a database error.
    Rules: `update_factory` R14 [BUG-895], Errors row 3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)
    before_f2 = snap(db, f2)

    with patch.object(FactoryManager, "_check_name_exists", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.name == "Second"
    # Then 6
    assert snap(db, f1) == before_f1


# [claude] FAC-U-51
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fac_u_51__a_change_to_a_taken_abbreviation_that_passed_the_python_check_is(db, w1, u2, mk_factory):
    """FAC-U-51 — a change to a taken abbreviation that passed the Python check is answered with 409, not a database error.
    Rules: `update_factory` R14a [BUG-895], Errors row 4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)
    before_f2 = snap(db, f2)

    with patch.object(FactoryManager, "_check_abbreviation_exists", return_value=False):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            with db.begin_nested():
                M.update_factory(db, factory_id=f2.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with abbreviation 'MP' already exists"
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    row = reread(db, f2)
    assert row.abbreviation == "SC"
    # Then 6
    assert snap(db, f1) == before_f1


# [claude] FAC-U-52
def test_fac_u_52__the_update_is_flushed_but_not_committed_a_rollback_brings_the_old(db, w1, u2, mk_factory):
    """FAC-U-52 — the update is flushed but not committed: a rollback brings the old name back.
    Rules: `update_factory` Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)

        # Then 1
        row = reread(db, f1)
        assert row.name == "North Yard"
        sp.rollback()
        # Then 2
        row = reread(db, f1)
        assert row.name == "Main Plant"
        # Then 3
        assert row.updated_by is None
        # Then 4
        assert commit_spy.call_count == 0


# [local-coder] FAC-G-02
def test_fac_g_02__a_live_factory_with_is_active_false_is_returned(db, w1, mk_factory):
    """FAC-G-02 — a live factory with is_active False is returned.
    Rules: `get_factory` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", is_active=False)

    result = M.get_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == f1.id
    # Then 2
    assert result.is_active is False


# [local-coder] FAC-G-03
def test_fac_g_03__an_id_that_no_factory_has_is_answered_with_404(db, w1, mk_factory):
    """FAC-G-03 — an id that no factory has is answered with 404.
    Rules: `get_factory` R2, Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory(db, factory_id=MISSING, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, f1) == before_f1


# [local-coder] FAC-G-04
def test_fac_g_04__a_factory_of_another_workspace_is_answered_with_404(db, w1, w2, mk_factory):
    """FAC-G-04 — a factory of another workspace is answered with 404.
    Rules: `get_factory` R2, Errors row 1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory(db, factory_id=f9.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert snap(db, f9) == before_f9


# [local-coder] FAC-G-05
def test_fac_g_05__a_factory_of_the_second_workspace_is_returned_to_its_own_workspace(db, w2, mk_factory):
    """FAC-G-05 — a factory of the second workspace is returned to its own workspace.
    Rules: `get_factory` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M.get_factory(db, factory_id=f9.id, workspace_id=w2.id)

    # Then 1
    assert result.id == f9.id
    # Then 2
    assert result.name == "Far Depot"
    # Then 3
    assert result.workspace_id == w2.id


# [local-coder] FAC-G-06
@pytest.mark.xfail(strict=True, reason="BUG-897: get_factory returns soft-deleted factories")
def test_fac_g_06__a_soft_deleted_factory_is_answered_with_404_by_default(db, w1, mk_factory):
    """FAC-G-06 — a soft-deleted factory is answered with 404 by default.
    Rules: `get_factory` R3 [BUG-897], Errors row 1"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_fd = snap(db, fd)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory(db, factory_id=fd.id, workspace_id=w1.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd.id} not found"
    # Then 4
    assert snap(db, fd) == before_fd


# [local-coder] FAC-G-08
@pytest.mark.xfail(strict=True, reason="BUG-897: get_factory returns soft-deleted factories")
def test_fac_g_08__include_deleted_true_still_answers_404_for_a_soft_deleted_factory_of(db, w1, w2, mk_factory):
    """FAC-G-08 — include_deleted=True still answers 404 for a soft-deleted factory of another workspace.
    Rules: `get_factory` R4 [BUG-897]"""
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)
    before_fd9 = snap(db, fd9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_factory(db, factory_id=fd9.id, workspace_id=w1.id, include_deleted=True)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd9.id} not found"
    # Then 4
    assert snap(db, fd9) == before_fd9


# [local-coder] FAC-G-09
@pytest.mark.xfail(strict=True, reason="BUG-897: get_factory returns soft-deleted factories")
def test_fac_g_09__include_deleted_true_returns_a_live_factory_as_well(db, w1, mk_factory):
    """FAC-G-09 — include_deleted=True returns a live factory as well.
    Rules: `get_factory` R4 [BUG-897], R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.get_factory(db, factory_id=f1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == f1.id
    # Then 2
    assert result.is_deleted is False


# [local-coder] FAC-S-02
def test_fac_s_02__a_factory_of_another_workspace_is_not_listed(db, w1, w2, mk_factory):
    """FAC-S-02 — a factory of another workspace is not listed.
    Rules: `search_factories` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-03
def test_fac_s_03__a_call_for_the_second_workspace_lists_only_that_workspace_s_factory(db, w2, mk_factory):
    """FAC-S-03 — a call for the second workspace lists only that workspace's factory.
    Rules: `search_factories` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M.search_factories(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [f9.id]


# [local-coder] FAC-S-04
def test_fac_s_04__an_unknown_workspace_id_returns_an_empty_list(db, mk_factory):
    """FAC-S-04 — an unknown workspace id returns an empty list.
    Rules: `search_factories` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M.search_factories(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] FAC-S-05
def test_fac_s_05__a_live_factory_with_is_active_false_is_listed(db, w1, mk_factory):
    """FAC-S-05 — a live factory with is_active False is listed.
    Rules: `search_factories` R1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", is_active=False)
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id]


# [local-coder] FAC-S-06
def test_fac_s_06__a_soft_deleted_factory_is_not_listed_by_default_and_the_call_changes(db, w1, mk_factory):
    """FAC-S-06 — a soft-deleted factory is not listed by default and the call changes nothing.
    Rules: `search_factories` R4, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_f1 = snap(db, f1)
    before_fd = snap(db, fd)
    before = written(db)

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [f1.id]
    # Then 2
    assert snap(db, f1) == before_f1
    # Then 3
    assert snap(db, fd) == before_fd
    # Then 4
    assert written(db) == before


# [local-coder] FAC-S-07
def test_fac_s_07__a_workspace_whose_only_factory_is_soft_deleted_returns_an_empty_list(db, w1, mk_factory):
    """FAC-S-07 — a workspace whose only factory is soft-deleted returns an empty list.
    Rules: `search_factories` R4, R9"""
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] FAC-S-10
def test_fac_s_10__an_explicit_include_deleted_false_hides_the_soft_deleted_factory(db, w1, mk_factory):
    """FAC-S-10 — an explicit include_deleted=False hides the soft-deleted factory.
    Rules: `search_factories` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = M.search_factories(db, workspace_id=w1.id, include_deleted=False)

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-11
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident)")
def test_fac_s_11__a_soft_deleted_factory_does_not_use_up_a_place_in_the_page(db, w1, mk_factory):
    """FAC-S-11 — a soft-deleted factory does not use up a place in the page.
    Rules: `search_factories` R4 [BUG-898], R2 [BUG-898]"""
    mk_factory(name="Alpha", abbreviation="AL", deleted=True)
    f2 = mk_factory(name="Bravo", abbreviation="BR")
    f3 = mk_factory(name="Charlie", abbreviation="CH")

    result = M.search_factories(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [f2.id, f3.id]


# [local-coder] FAC-S-12
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident)")
def test_fac_s_12__a_search_finds_a_matching_factory_that_lies_outside_the_first_page_of(db, w1, mk_factory):
    """FAC-S-12 — a search finds a matching factory that lies outside the first page of rows.
    Rules: `search_factories` R2 [BUG-898], R6"""
    mk_factory(name="Alpha", abbreviation="AL")
    mk_factory(name="Bravo", abbreviation="BR")
    f3 = mk_factory(name="Camp Site", abbreviation="CS")

    result = M.search_factories(db, workspace_id=w1.id, search="camp", limit=2)

    # Then 1
    assert ids(result) == [f3.id]


# [local-coder] FAC-S-13
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident)")
def test_fac_s_13__skip_counts_live_factories_only(db, w1, mk_factory):
    """FAC-S-13 — skip counts live factories only.
    Rules: `search_factories` R2 [BUG-898], R4 [BUG-898]"""
    mk_factory(name="Alpha", abbreviation="AL", deleted=True)
    mk_factory(name="Bravo", abbreviation="BR")
    f3 = mk_factory(name="Charlie", abbreviation="CH")

    result = M.search_factories(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [f3.id]


# [local-coder] FAC-S-14
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident)")
def test_fac_s_14__skip_counts_matching_factories_only(db, w1, mk_factory):
    """FAC-S-14 — skip counts matching factories only.
    Rules: `search_factories` R2 [BUG-898]"""
    mk_factory(name="Alpha", abbreviation="AL")
    mk_factory(name="Bravo Plant", abbreviation="BP")
    f3 = mk_factory(name="Delta Plant", abbreviation="DP")

    result = M.search_factories(db, workspace_id=w1.id, search="plant", skip=1)

    # Then 1
    assert ids(result) == [f3.id]


# [claude] FAC-S-15
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_s_15__the_default_list_shows_a_live_factory_that_is_the_101st_row_of_the(db, w1, mk_factory):
    """FAC-S-15 — the default list shows a live factory that is the 101st row of the workspace.
    Rules: `search_factories` R2 [BUG-898], R4 [BUG-898]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    late = mk_factory(name="Late", abbreviation="LT")

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [late.id]


# [claude] FAC-S-16
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_s_16__a_search_finds_a_live_factory_that_is_the_101st_row_of_the_workspace(db, w1, mk_factory):
    """FAC-S-16 — a search finds a live factory that is the 101st row of the workspace.
    Rules: `search_factories` R2 [BUG-898], R6"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    late = mk_factory(name="Late", abbreviation="LT")

    result = M.search_factories(db, workspace_id=w1.id, search="late")

    # Then 1
    assert ids(result) == [late.id]


# [claude] FAC-S-17
def test_fac_s_17__the_default_list_shows_a_live_factory_that_is_the_100th_row_of_the(db, w1, mk_factory):
    """FAC-S-17 — the default list shows a live factory that is the 100th row of the workspace.
    Rules: `search_factories` R2, R4"""
    for k in range(1, 100):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    late = mk_factory(name="Late", abbreviation="LT")

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [late.id]


# [claude] FAC-S-18
def test_fac_s_18__the_default_limit_returns_exactly_100_of_101_live_factories(db, w1, mk_factory):
    """FAC-S-18 — the default limit returns exactly 100 of 101 live factories.
    Rules: `search_factories` R9"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(set(ids(result))) == 100
    # Then 3
    assert set(ids(result)) <= set(all_ids)


# [claude] FAC-S-19
def test_fac_s_19__an_explicit_limit_of_101_returns_all_101_live_factories(db, w1, mk_factory):
    """FAC-S-19 — an explicit limit of 101 returns all 101 live factories.
    Rules: `search_factories` R9"""
    all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]

    result = M.search_factories(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == all_ids


# [local-coder] FAC-S-20
def test_fac_s_20__the_search_text_is_found_in_the_abbreviation_of_one_factory_and_in(db, w1, mk_factory):
    """FAC-S-20 — the search text is found in the abbreviation of one factory and in the name of another.
    Rules: `search_factories` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="mp")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id]


# [local-coder] FAC-S-21
def test_fac_s_21__the_search_ignores_case_and_finds_text_at_the_end_of_a_name(db, w1, mk_factory):
    """FAC-S-21 — the search ignores case and finds text at the end of a name.
    Rules: `search_factories` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="PLANT")

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-22
def test_fac_s_22__a_match_in_the_abbreviation_alone_is_enough(db, w1, mk_factory):
    """FAC-S-22 — a match in the abbreviation alone is enough.
    Rules: `search_factories` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="ny")

    # Then 1
    assert ids(result) == [f3.id]


# [local-coder] FAC-S-23
def test_fac_s_23__a_search_text_that_no_factory_contains_returns_an_empty_list(db, w1, mk_factory):
    """FAC-S-23 — a search text that no factory contains returns an empty list.
    Rules: `search_factories` R6, R9"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="zzz")

    # Then 1
    assert result == []


# [local-coder] FAC-S-24
def test_fac_s_24__two_inner_spaces_in_the_search_text_do_not_match_a_name_with_one_space(db, w1, mk_factory):
    """FAC-S-24 — two inner spaces in the search text do not match a name with one space.
    Rules: `search_factories` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="main  plant")

    # Then 1
    assert result == []


# [local-coder] FAC-S-25
def test_fac_s_25__one_inner_space_in_the_search_text_matches_the_space_inside_a_name(db, w1, mk_factory):
    """FAC-S-25 — one inner space in the search text matches the space inside a name.
    Rules: `search_factories` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="n p")

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-26
def test_fac_s_26__a_percent_sign_in_the_search_text_matches_only_a_percent_sign(db, w1, mk_factory):
    """FAC-S-26 — a percent sign in the search text matches only a percent sign.
    Rules: `search_factories` R6a"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="100% Cotton", abbreviation="HC")

    result = M.search_factories(db, workspace_id=w1.id, search="%")

    # Then 1
    assert ids(result) == [f2.id]


# [local-coder] FAC-S-27
def test_fac_s_27__a_percent_sign_finds_nothing_when_no_factory_contains_one(db, w1, mk_factory):
    """FAC-S-27 — a percent sign finds nothing when no factory contains one.
    Rules: `search_factories` R6a"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, search="%")

    # Then 1
    assert result == []


# [local-coder] FAC-S-28
def test_fac_s_28__an_underscore_in_the_search_text_matches_only_an_underscore(db, w1, mk_factory):
    """FAC-S-28 — an underscore in the search text matches only an underscore.
    Rules: `search_factories` R6a"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Dye_House", abbreviation="DH")

    result = M.search_factories(db, workspace_id=w1.id, search="_")

    # Then 1
    assert ids(result) == [f2.id]


# [local-coder] FAC-S-29
def test_fac_s_29__a_backslash_in_the_search_text_matches_only_a_backslash(db, w1, mk_factory):
    """FAC-S-29 — a backslash in the search text matches only a backslash.
    Rules: `search_factories` R6a"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="A\\B Works", abbreviation="AB")

    result = M.search_factories(db, workspace_id=w1.id, search="\\")

    # Then 1
    assert ids(result) == [f2.id]


# [local-coder] FAC-S-30
def test_fac_s_30__search_none_applies_no_search_filter(db, w1, mk_factory):
    """FAC-S-30 — search=None applies no search filter.
    Rules: `search_factories` R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search=None)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]


# [local-coder] FAC-S-31
def test_fac_s_31__an_empty_search_text_applies_no_search_filter(db, w1, mk_factory):
    """FAC-S-31 — an empty search text applies no search filter.
    Rules: `search_factories` R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]


# [local-coder] FAC-S-32
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fac_s_32__a_search_of_three_spaces_applies_no_search_filter(db, w1, mk_factory):
    """FAC-S-32 — a search of three spaces applies no search filter.
    Rules: `search_factories` R7 [BUG-902]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]


# [local-coder] FAC-S-33
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fac_s_33__a_search_of_one_tab_applies_no_search_filter(db, w1, mk_factory):
    """FAC-S-33 — a search of one tab applies no search filter.
    Rules: `search_factories` R7 [BUG-902]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="\t")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]


# [local-coder] FAC-S-34
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fac_s_34__a_search_of_a_space_a_newline_and_a_space_applies_no_search_filter(db, w1, mk_factory):
    """FAC-S-34 — a search of a space, a newline and a space applies no search filter.
    Rules: `search_factories` R7 [BUG-902]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    f3 = mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search=" \n ")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id, f3.id]


# [local-coder] FAC-S-35
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fac_s_35__spaces_around_the_search_text_are_removed_before_matching(db, w1, mk_factory):
    """FAC-S-35 — spaces around the search text are removed before matching.
    Rules: `search_factories` R7 [BUG-902]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Camp Site", abbreviation="CS")
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search=" mp ")

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id]


# [local-coder] FAC-S-37
def test_fac_s_37__a_matching_soft_deleted_factory_is_not_returned_by_a_search(db, w1, mk_factory):
    """FAC-S-37 — a matching soft-deleted factory is not returned by a search.
    Rules: `search_factories` R8"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="plant")

    # Then 1
    assert ids(result) == [f1.id]


# [local-coder] FAC-S-39
def test_fac_s_39__a_workspace_without_factories_returns_an_empty_list(db, w1):
    """FAC-S-39 — a workspace without factories returns an empty list.
    Rules: `search_factories` R9"""
    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert result == []


# [local-coder] FAC-S-40
def test_fac_s_40__skip_equal_to_the_number_of_factories_returns_an_empty_list(db, w1, mk_factory):
    """FAC-S-40 — skip equal to the number of factories returns an empty list.
    Rules: `search_factories` R9"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [local-coder] FAC-S-41
def test_fac_s_41__skip_past_the_number_of_factories_returns_an_empty_list(db, w1, mk_factory):
    """FAC-S-41 — skip past the number of factories returns an empty list.
    Rules: `search_factories` R9"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, skip=5)

    # Then 1
    assert result == []


# [local-coder] FAC-S-42
def test_fac_s_42__skip_1_of_two_factories_returns_one_of_them(db, w1, mk_factory):
    """FAC-S-42 — skip 1 of two factories returns one of them.
    Rules: `search_factories` R9"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id]


# [local-coder] FAC-S-43
def test_fac_s_43__limit_1_of_two_factories_returns_one_of_them(db, w1, mk_factory):
    """FAC-S-43 — limit 1 of two factories returns one of them.
    Rules: `search_factories` R9"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [f1.id, f2.id]


# [local-coder] FAC-S-44
def test_fac_s_44__limit_0_returns_an_empty_list(db, w1, mk_factory):
    """FAC-S-44 — limit 0 returns an empty list.
    Rules: `search_factories` R9"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M.search_factories(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [local-coder] FAC-S-46
def test_fac_s_46__a_negative_skip_is_rejected_by_the_database(db, w1, mk_factory):
    """FAC-S-46 — a negative skip is rejected by the database.
    Rules: `search_factories` R9, Errors row 2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            M.search_factories(db, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] FAC-S-47
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fac_s_47__the_list_is_ordered_by_name_ignoring_case(db, w1, mk_factory):
    """FAC-S-47 — the list is ordered by name ignoring case.
    Rules: `search_factories` R3 [BUG-899]"""
    mk_factory(name="Delta", abbreviation="DL")
    mk_factory(name="alpha", abbreviation="AL")
    mk_factory(name="echo", abbreviation="EC")
    mk_factory(name="Bravo", abbreviation="BR")
    mk_factory(name="charlie", abbreviation="CH")

    result = M.search_factories(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]


# [local-coder] FAC-S-48
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fac_s_48__equal_names_come_back_in_id_order_and_deleted_factories_are_ordered(db, w1, mk_factory):
    """FAC-S-48 — equal names come back in id order and deleted factories are ordered together with live ones.
    Rules: `search_factories` R3 [BUG-899], R5 [BUG-901]"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    d2 = mk_factory(name="Mango", abbreviation="MG", deleted=True)
    f3 = mk_factory(name="apple", abbreviation="AP")
    f4 = mk_factory(name="mango", abbreviation="MX")

    result = M.search_factories(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [f3.id, d2.id, f4.id, f1.id]


# [local-coder] FAC-S-49
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fac_s_49__a_middle_page_holds_the_second_and_third_factory_by_name(db, w1, mk_factory):
    """FAC-S-49 — a middle page holds the second and third factory by name.
    Rules: `search_factories` R3 [BUG-899], R9"""
    mk_factory(name="Delta", abbreviation="DL")
    mk_factory(name="alpha", abbreviation="AL")
    mk_factory(name="echo", abbreviation="EC")
    mk_factory(name="Bravo", abbreviation="BR")
    mk_factory(name="charlie", abbreviation="CH")

    result = M.search_factories(db, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert names(result) == ["Bravo", "charlie"]


# [local-coder] FAC-S-50
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fac_s_50__the_last_page_holds_the_last_factory_by_name(db, w1, mk_factory):
    """FAC-S-50 — the last page holds the last factory by name.
    Rules: `search_factories` R3 [BUG-899], R9"""
    mk_factory(name="Delta", abbreviation="DL")
    mk_factory(name="alpha", abbreviation="AL")
    mk_factory(name="echo", abbreviation="EC")
    mk_factory(name="Bravo", abbreviation="BR")
    mk_factory(name="charlie", abbreviation="CH")

    result = M.search_factories(db, workspace_id=w1.id, skip=4, limit=2)

    # Then 1
    assert names(result) == ["echo"]


# [local-coder] FAC-S-51
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")
def test_fac_s_51__search_results_are_ordered_by_name_ignoring_case(db, w1, mk_factory):
    """FAC-S-51 — search results are ordered by name ignoring case.
    Rules: `search_factories` R3 [BUG-899], R6"""
    mk_factory(name="Zinc Plant", abbreviation="ZP")
    mk_factory(name="alpha plant", abbreviation="AP")
    mk_factory(name="Mid Plant", abbreviation="MD")
    mk_factory(name="Depot", abbreviation="DP")

    result = M.search_factories(db, workspace_id=w1.id, search="plant")

    # Then 1
    assert names(result) == ["alpha plant", "Mid Plant", "Zinc Plant"]


# [claude] FAC-S-52
@pytest.mark.xfail(strict=True, reason="BUG-898: Factory list drops deleted rows and applies the search after paging")
def test_fac_s_52__the_list_query_leaves_out_soft_deleted_factories_in_the_database(db, w1, mk_factory):
    """FAC-S-52 — the list query leaves out soft-deleted factories in the database, before the page.
    Rules: `search_factories` R4 [BUG-898], R2 [BUG-898]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = M.search_factories(db, workspace_id=w1.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [f1.id]
    # Then 2
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    factory_selects = [stmt for stmt in flat if stmt.startswith("SELECT") and " FROM FACTORIES" in stmt]
    assert any(" WHERE " in stmt and "IS_DELETED" in stmt.split(" WHERE ", 1)[1] for stmt in factory_selects)


# [claude] FAC-S-53
@pytest.mark.xfail(strict=True, reason="BUG-899: Factory list has no sort order")
def test_fac_s_53__the_list_query_asks_the_database_for_an_order(db, w1, mk_factory):
    """FAC-S-53 — the list query asks the database for an order.
    Rules: `search_factories` R3 [BUG-899]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = M.search_factories(db, workspace_id=w1.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [f1.id]
    # Then 2
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    factory_selects = [stmt for stmt in flat if stmt.startswith("SELECT") and " FROM FACTORIES" in stmt]
    assert any(" ORDER BY " in stmt for stmt in factory_selects)


# [local-coder] FAC-D-02
def test_fac_d_02__no_other_column_of_the_factory_is_changed_by_the_delete(db, w1, u1, u2, mk_factory):
    """FAC-D-02 — no other column of the factory is changed by the delete.
    Rules: `delete_factory` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)
    created_before = f1.created_at

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

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


# [local-coder] FAC-D-03
def test_fac_d_03__the_delete_does_not_stamp_updated_by(db, w1, u2, mk_factory):
    """FAC-D-03 — the delete does not stamp updated_by.
    Rules: `delete_factory` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.updated_by is None
    # Then 3
    assert row.updated_at is not None
    # Then 4
    assert row.is_deleted is True


# [local-coder] FAC-D-04
def test_fac_d_04__a_live_factory_with_is_active_false_is_deleted_and_stays_inactive(db, w1, u2, mk_factory):
    """FAC-D-04 — a live factory with is_active False is deleted and stays inactive.
    Rules: `delete_factory` R3, R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", is_active=False)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.is_active is False
    # Then 4
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id


# [local-coder] FAC-D-05
def test_fac_d_05__an_id_that_no_factory_has_is_answered_with_404(db, w1, u2, mk_factory):
    """FAC-D-05 — an id that no factory has is answered with 404.
    Rules: `delete_factory` R1, Errors row 1"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, f1) == before_f1
    # Then 6
    row = reread(db, f1)
    assert row.is_deleted is False


# [local-coder] FAC-D-06
def test_fac_d_06__a_factory_of_another_workspace_is_answered_with_404_and_not_deleted(db, w1, w2, u2, mk_factory):
    """FAC-D-06 — a factory of another workspace is answered with 404 and not deleted.
    Rules: `delete_factory` R1, Errors row 1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f9 = snap(db, f9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=f9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f9.id} not found"
    # Then 4
    assert snap(db, f9) == before_f9
    # Then 5
    row = reread(db, f9)
    assert row.is_deleted is False
    # Then 6
    assert row.deleted_at is None
    assert row.deleted_by is None


# [local-coder] FAC-D-07
def test_fac_d_07__a_soft_deleted_factory_of_another_workspace_is_answered_with_404_not(db, w1, w2, u1, u2, mk_factory):
    """FAC-D-07 — a soft-deleted factory of another workspace is answered with 404, not 400.
    Rules: `delete_factory` R1"""
    fd9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id, deleted=True)
    before_fd9 = snap(db, fd9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=fd9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {fd9.id} not found"
    # Then 4
    assert snap(db, fd9) == before_fd9
    # Then 5
    row = reread(db, fd9)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [local-coder] FAC-D-10
def test_fac_d_10__a_factory_with_sections_is_deleted_and_its_sections_are_left_exactly(db, w1, u2, mk_factory, mk_section):
    """FAC-D-10 — a factory with sections is deleted and its sections are left exactly as they were.
    Rules: `delete_factory` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    sc1 = mk_section(of=f1, name="Assembly")
    sc2 = mk_section(of=f1, name="Paint", is_active=False)
    before_sc1 = snap(db, sc1)
    before_sc2 = snap(db, sc2)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

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
    assert snap(db, sc2) == before_sc2
    # Then 6
    row = reread(db, sc2)
    assert row.is_deleted is False
    assert row.is_active is False
    # Then 7
    assert count_rows(db, "factory_sections") == 2


# [local-coder] FAC-D-11
def test_fac_d_11__after_the_delete_the_factory_is_gone_from_the_default_list_and_shown(db, w1, u2, mk_factory):
    """FAC-D-11 — after the delete the factory is gone from the default list and shown with include_deleted=True.
    Rules: `delete_factory` R6; `search_factories` R4, R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    assert ids(M.search_factories(db, workspace_id=w1.id)) == [f2.id]
    # Then 3
    assert sorted(ids(M.search_factories(db, workspace_id=w1.id, include_deleted=True))) == [f1.id, f2.id]


# [claude] FAC-D-13
def test_fac_d_13__after_the_delete_a_new_factory_can_take_the_name_and_abbreviation_and(db, w1, u2, mk_factory):
    """FAC-D-13 — after the delete a new factory can take the name and abbreviation, and an update of the deleted one answers 400.
    Rules: `delete_factory` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    new = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)
    assert new.id != f1.id
    # Then 3
    row = reread(db, new)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    assert row.is_deleted is False
    # Then 4
    with pytest.raises(HTTPException) as exc:
        M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=w1.id, user_id=u2.id)
    assert exc.value.status_code == 400
    # Then 5
    assert exc.value.detail == "Cannot update deleted factory"
    # Then 6
    assert count_rows(db, "factories") == 2


# [claude] FAC-D-14
def test_fac_d_14__the_delete_is_flushed_but_not_committed_a_rollback_makes_the_factory(db, w1, u2, mk_factory):
    """FAC-D-14 — the delete is flushed but not committed: a rollback makes the factory live again.
    Rules: `delete_factory` R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

        # Then 1
        assert result is f1
        # Then 2
        row = reread(db, f1)
        assert row.is_deleted is True
        sp.rollback()
        # Then 3
        row = reread(db, f1)
        assert row.is_deleted is False
        # Then 4
        assert row.deleted_at is None
        assert row.deleted_by is None
        # Then 5
        assert commit_spy.call_count == 0


# [local-coder] FAC-D-15
def test_fac_d_15__only_that_factory_row_is_touched(db, w1, u2, mk_factory):
    """FAC-D-15 — only that factory row is touched.
    Rules: `delete_factory` R7, Side effects"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    before_f2 = snap(db, f2)
    before = written(db)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)

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
    assert written(db) == before
    # Then 6
    assert count_rows(db, "factories") == 2


# [local-coder] FAC-D-16
def test_fac_d_16__a_user_id_that_is_no_profile_id_fails_on_flush_and_the_factory_stays(db, w1, mk_factory):
    """FAC-D-16 — a user_id that is no profile id fails on flush and the factory stays live.
    Rules: `delete_factory` R8, Errors row 3"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=MISSING)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)

    # Then 3
    assert snap(db, f1) == before_f1

    # Then 4
    row = reread(db, f1)
    assert row.is_deleted is False

    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None

    # Then 6
    assert written(db) == before


# [local-coder] FAC-D-17
def test_fac_d_17__a_factory_of_the_second_workspace_is_deleted_from_its_own_workspace(db, w2, u2, mk_factory):
    """FAC-D-17 — a factory of the second workspace is deleted from its own workspace.
    Rules: `delete_factory` R3, R7"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f1 = snap(db, f1)

    result = M.delete_factory(db, factory_id=f9.id, workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result is f9
    # Then 2
    row = reread(db, f9)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    row_f1 = reread(db, f1)
    assert row_f1.is_deleted is False


# [local-coder] FAC-CN-02
def test_fac_cn_02__a_name_that_no_factory_of_the_workspace_has_gives_false(db, w1, mk_factory):
    """FAC-CN-02 — a name that no factory of the workspace has gives False.
    Rules: `_check_name_exists` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="North Yard")

    # Then 1
    assert result is False


# [local-coder] FAC-CN-03
def test_fac_cn_03__a_factory_of_another_workspace_with_that_name_is_not_considered(db, w1, w2, mk_factory):
    """FAC-CN-03 — a factory of another workspace with that name is not considered.
    Rules: `_check_name_exists` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M._check_name_exists(db, workspace_id=w1.id, name="Far Depot")

    # Then 1
    assert result is False


# [local-coder] FAC-CN-04
def test_fac_cn_04__the_check_for_the_second_workspace_finds_that_workspace_s_factory(db, w2, mk_factory):
    """FAC-CN-04 — the check for the second workspace finds that workspace's factory.
    Rules: `_check_name_exists` R2, R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M._check_name_exists(db, workspace_id=w2.id, name="Far Depot")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-05
def test_fac_cn_05__a_soft_deleted_factory_with_that_name_is_ignored(db, w1, mk_factory):
    """FAC-CN-05 — a soft-deleted factory with that name is ignored.
    Rules: `_check_name_exists` R3"""
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Old Plant")

    # Then 1
    assert result is False


# [local-coder] FAC-CN-06
def test_fac_cn_06__a_soft_deleted_and_a_live_factory_with_that_name_give_true(db, w1, mk_factory):
    """FAC-CN-06 — a soft-deleted and a live factory with that name give True.
    Rules: `_check_name_exists` R3, R1"""
    mk_factory(name="Main Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-07
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_cn_07__the_name_in_lower_case_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CN-07 — the name in lower case matches the live factory.
    Rules: `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="main plant")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-08
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_cn_08__the_name_in_upper_case_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CN-08 — the name in upper case matches the live factory.
    Rules: `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="MAIN PLANT")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-09
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_cn_09__the_name_with_a_trailing_space_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CN-09 — the name with a trailing space matches the live factory.
    Rules: `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant ")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-10
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_cn_10__the_name_with_a_leading_tab_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CN-10 — the name with a leading tab matches the live factory.
    Rules: `_check_name_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="\tMain Plant")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-11
def test_fac_cn_11__the_name_with_two_inner_spaces_does_not_match(db, w1, mk_factory):
    """FAC-CN-11 — the name with two inner spaces does not match.
    Rules: `_check_name_exists` R4"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main  Plant")

    # Then 1
    assert result is False


# [local-coder] FAC-CN-12
def test_fac_cn_12__a_longer_name_that_starts_with_the_factory_name_does_not_match(db, w1, mk_factory):
    """FAC-CN-12 — a longer name that starts with the factory name does not match.
    Rules: `_check_name_exists` R4"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant 2")

    # Then 1
    assert result is False


# [claude] FAC-CN-13
def test_fac_cn_13__a_live_factory_that_is_the_100th_row_of_the_workspace_is_found(db, w1, mk_factory):
    """FAC-CN-13 — a live factory that is the 100th row of the workspace is found.
    Rules: `_check_name_exists` R5"""
    for k in range(1, 100):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Late")

    # Then 1
    assert result is True


# [claude] FAC-CN-14
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_cn_14__a_live_factory_that_is_the_101st_row_of_the_workspace_is_found(db, w1, mk_factory):
    """FAC-CN-14 — a live factory that is the 101st row of the workspace is found.
    Rules: `_check_name_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Late")

    # Then 1
    assert result is True


# [local-coder] FAC-CN-15
def test_fac_cn_15__the_factory_named_by_exclude_id_is_ignored(db, w1, mk_factory):
    """FAC-CN-15 — the factory named by exclude_id is ignored.
    Rules: `_check_name_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant", exclude_id=f1.id)

    # Then 1
    assert result is False


# [local-coder] FAC-CN-16
def test_fac_cn_16__excluding_another_factory_still_gives_true(db, w1, mk_factory):
    """FAC-CN-16 — excluding another factory still gives True.
    Rules: `_check_name_exists` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant", exclude_id=f2.id)

    # Then 1
    assert result is True


# [local-coder] FAC-CN-17
def test_fac_cn_17__an_explicit_exclude_id_none_ignores_nothing(db, w1, mk_factory):
    """FAC-CN-17 — an explicit exclude_id=None ignores nothing.
    Rules: `_check_name_exists` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant", exclude_id=None)

    # Then 1
    assert result is True


# [local-coder] FAC-CN-18
def test_fac_cn_18__a_workspace_without_factories_gives_false(db, w1):
    """FAC-CN-18 — a workspace without factories gives False.
    Rules: `_check_name_exists` R7"""
    result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant")

    # Then 1
    assert result is False


# [local-coder] FAC-CN-19
def test_fac_cn_19__a_factory_whose_abbreviation_equals_the_name_looked_for_does_not_match(db, w1, mk_factory):
    """FAC-CN-19 — a factory whose abbreviation equals the name looked for does not match.
    Rules: `_check_name_exists` R7"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_name_exists(db, workspace_id=w1.id, name="MP")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-01
def test_fac_ca_01__a_live_factory_of_the_workspace_with_that_abbreviation_gives_true_and(db, w1, mk_factory):
    """FAC-CA-01 — a live factory of the workspace with that abbreviation gives True and nothing is changed.
    Rules: `_check_abbreviation_exists` R1, R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")
    before_f1 = snap(db, f1)
    before = written(db)

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP")

    # Then 1
    assert result is True
    # Then 2
    assert snap(db, f1) == before_f1
    # Then 3
    assert written(db) == before


# [local-coder] FAC-CA-02
def test_fac_ca_02__a_abbreviation_that_no_factory_of_the_workspace_has_gives_false(db, w1, mk_factory):
    """FAC-CA-02 — a abbreviation that no factory of the workspace has gives False.
    Rules: `_check_abbreviation_exists` R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="NY")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-03
def test_fac_ca_03__a_factory_of_another_workspace_with_that_abbreviation_is_not(db, w1, w2, mk_factory):
    """FAC-CA-03 — a factory of another workspace with that abbreviation is not considered.
    Rules: `_check_abbreviation_exists` R2"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="FD")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-04
def test_fac_ca_04__the_check_for_the_second_workspace_finds_that_workspace_s_factory(db, w2, mk_factory):
    """FAC-CA-04 — the check for the second workspace finds that workspace's factory.
    Rules: `_check_abbreviation_exists` R2, R1"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)

    result = M._check_abbreviation_exists(db, workspace_id=w2.id, abbreviation="FD")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-05
def test_fac_ca_05__a_soft_deleted_factory_with_that_abbreviation_is_ignored(db, w1, mk_factory):
    """FAC-CA-05 — a soft-deleted factory with that abbreviation is ignored.
    Rules: `_check_abbreviation_exists` R3"""
    mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="OP")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-06
def test_fac_ca_06__a_soft_deleted_and_a_live_factory_with_that_abbreviation_give_true(db, w1, mk_factory):
    """FAC-CA-06 — a soft-deleted and a live factory with that abbreviation give True.
    Rules: `_check_abbreviation_exists` R3, R1"""
    mk_factory(name="Old Plant", abbreviation="MP", deleted=True)
    mk_factory(name="Main Plant", abbreviation="MP")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-07
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_ca_07__the_abbreviation_in_lower_case_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CA-07 — the abbreviation in lower case matches the live factory.
    Rules: `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="mp")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-08
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_ca_08__the_abbreviation_in_mixed_case_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CA-08 — the abbreviation in mixed case matches the live factory.
    Rules: `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="Mp")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-09
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fac_ca_09__the_abbreviation_with_outer_spaces_matches_the_live_factory(db, w1, mk_factory):
    """FAC-CA-09 — the abbreviation with outer spaces matches the live factory.
    Rules: `_check_abbreviation_exists` R4 [BUG-894]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation=" MP ")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-11
def test_fac_ca_11__a_longer_abbreviation_that_starts_with_the_factory_abbreviation_does(db, w1, mk_factory):
    """FAC-CA-11 — a longer abbreviation that starts with the factory abbreviation does not match.
    Rules: `_check_abbreviation_exists` R4"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP2")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-12
def test_fac_ca_12__the_abbreviation_with_an_inner_space_does_not_match(db, w1, mk_factory):
    """FAC-CA-12 — the abbreviation with an inner space does not match.
    Rules: `_check_abbreviation_exists` R4"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="M P")

    # Then 1
    assert result is False


# [claude] FAC-CA-13
def test_fac_ca_13__a_live_factory_that_is_the_100th_row_of_the_workspace_is_found(db, w1, mk_factory):
    """FAC-CA-13 — a live factory that is the 100th row of the workspace is found.
    Rules: `_check_abbreviation_exists` R5"""
    for k in range(1, 100):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="LT")

    # Then 1
    assert result is True


# [claude] FAC-CA-14
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories (non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them)")
def test_fac_ca_14__a_live_factory_that_is_the_101st_row_of_the_workspace_is_found(db, w1, mk_factory):
    """FAC-CA-14 — a live factory that is the 101st row of the workspace is found.
    Rules: `_check_abbreviation_exists` R5 [BUG-893]"""
    for k in range(1, 101):
        mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)
    mk_factory(name="Late", abbreviation="LT")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="LT")

    # Then 1
    assert result is True


# [local-coder] FAC-CA-15
def test_fac_ca_15__the_factory_named_by_exclude_id_is_ignored(db, w1, mk_factory):
    """FAC-CA-15 — the factory named by exclude_id is ignored.
    Rules: `_check_abbreviation_exists` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP", exclude_id=f1.id)

    # Then 1
    assert result is False


# [local-coder] FAC-CA-16
def test_fac_ca_16__excluding_another_factory_still_gives_true(db, w1, mk_factory):
    """FAC-CA-16 — excluding another factory still gives True.
    Rules: `_check_abbreviation_exists` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP", exclude_id=f2.id)

    # Then 1
    assert result is True


# [local-coder] FAC-CA-17
def test_fac_ca_17__an_explicit_exclude_id_none_ignores_nothing(db, w1, mk_factory):
    """FAC-CA-17 — an explicit exclude_id=None ignores nothing.
    Rules: `_check_abbreviation_exists` R6"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP", exclude_id=None)

    # Then 1
    assert result is True


# [local-coder] FAC-CA-18
def test_fac_ca_18__a_workspace_without_factories_gives_false(db, w1):
    """FAC-CA-18 — a workspace without factories gives False.
    Rules: `_check_abbreviation_exists` R7"""

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP")

    # Then 1
    assert result is False


# [local-coder] FAC-CA-19
def test_fac_ca_19__a_factory_whose_name_equals_the_abbreviation_looked_for_does_not_match(db, w1, mk_factory):
    """FAC-CA-19 — a factory whose name equals the abbreviation looked for does not match.
    Rules: `_check_abbreviation_exists` R7"""
    mk_factory(name="Main Plant", abbreviation="MP")
    mk_factory(name="Second", abbreviation="SC")

    result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="Main Plant")

    # Then 1
    assert result is False


# [claude] FAC-D-18
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_18__a_factory_with_a_draft_batch_is_refused_and_the_batch_is_listed(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-18 — a factory with a draft batch is refused and the batch is listed.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, b1) == before_b1
    # Then 10
    assert written(db) == before


# [claude] FAC-D-19
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_19__a_factory_with_an_in_progress_batch_is_refused_and_the_batch_is_li(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-19 — a factory with an in_progress batch is refused and the batch is listed.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="in_progress")
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, b1) == before_b1
    # Then 10
    assert written(db) == before


# [claude] FAC-D-20
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_20__only_the_open_batches_are_listed_when_closed_ones_sit_between_them(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-20 — only the open batches are listed when closed ones sit between them.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    b2 = mk_batch(on=l1, batch_number="BATCH-2026-002", status="completed")
    b3 = mk_batch(on=l1, batch_number="BATCH-2026-003", status="in_progress")
    b4 = mk_batch(on=l1, batch_number="BATCH-2026-004", status="cancelled")
    before_f1 = snap(db, f1)
    before_b2 = snap(db, b2)
    before_b4 = snap(db, b4)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}, {"type": "production_batch", "id": b3.id}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, b2) == before_b2
    # Then 9
    assert snap(db, b4) == before_b4
    # Then 10
    assert written(db) == before


# [claude] FAC-D-21
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_21__the_blockers_are_sorted_by_id_as_numbers_on_two_lines_whatever_the(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-21 — the blockers are sorted by id as numbers, on two lines, whatever the other columns say.
    Rules: `delete_factory` R5b [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    l2 = mk_line(of=f1, name="Line B")
    mk_batch(on=l2, id=900000003, batch_number="BATCH-2026-002", batch_date=date(2026, 2, 1), status="in_progress")
    mk_batch(on=l2, id=99999999, batch_number="BATCH-2026-003", batch_date=date(2026, 2, 2), status="in_progress")
    mk_batch(on=l1, id=900000002, batch_number="BATCH-2026-001", batch_date=date(2026, 2, 3), status="draft")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": 99999999}, {"type": "production_batch", "id": 900000002}, {"type": "production_batch", "id": 900000003}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert written(db) == before


# [claude] FAC-D-22
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_22__a_batch_on_an_inactive_line_blocks(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-22 — a batch on an inactive line blocks.
    Rules: `delete_factory` R5a [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A", is_active=False)
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert written(db) == before


# [claude] FAC-D-23
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_23__all_101_open_batches_are_listed_not_a_first_page(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-23 — all 101 open batches are listed, not a first page.
    Rules: `delete_factory` R5b [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    batches = [mk_batch(on=l1, batch_number=f"BATCH-2026-{k:03d}", status="draft") for k in range(1, 102)]

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert len(exc.value.args[1]) == 101
    # Then 3
    assert exc.value.args[1] == [{"type": "production_batch", "id": b.id} for b in batches]
    # Then 4
    assert reread(db, f1).is_deleted is False


# [claude] FAC-D-24
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_24__an_open_batch_after_100_closed_ones_is_found(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-24 — an open batch after 100 closed ones is found.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    for k in range(1, 101):
        mk_batch(on=l1, batch_number=f"BATCH-2026-{k:03d}", status="completed")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-101", status="draft")

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 3
    assert reread(db, f1).is_deleted is False


# [claude] FAC-D-25
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_25__the_refusal_writes_nothing_the_pending_row_stays_pending_and_nothi(db, w1, u1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-25 — the refusal writes nothing: the pending row stays pending and nothing is dirty.
    Rules: `delete_factory` R5c [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    p1 = Factory(workspace_id=w1.id, name="Pending", abbreviation="PD", created_by=u1.id)
    db.add(p1)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert p1 in db.new
    # Then 5
    assert not db.dirty
    # Then 6
    assert not db.deleted
    # Then 7
    assert f1.is_deleted is False
    assert f1.deleted_at is None
    assert f1.deleted_by is None


# [claude] FAC-D-26
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_26__no_savepoint_hides_a_write_no_write_statement_no_savepoint_no_flus(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-26 — no savepoint hides a write: no write statement, no savepoint, no flush, commit or rollback.
    Rules: `delete_factory` R5c [BUG-1331]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="in_progress")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # Then 1
    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        with patch.object(db, "commit", wraps=db.commit) as commit_spy, \
                patch.object(db, "rollback", wraps=db.rollback) as rollback_spy, \
                patch.object(db, "flush", wraps=db.flush) as flush_spy:
            with pytest.raises(ValueError) as exc:
                M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    finally:
        event.remove(bind, "before_cursor_execute", record)
    # Then 2
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 3
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    assert not [stmt for stmt in flat if stmt.startswith(("UPDATE", "INSERT", "DELETE"))]
    # Then 4
    assert not [stmt for stmt in flat if stmt.startswith("SAVEPOINT")]
    # Then 5
    assert commit_spy.call_count == 0
    # Then 6
    assert rollback_spy.call_count == 0
    # Then 7
    assert flush_spy.call_count == 0


# [claude] FAC-D-27
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_27__the_refusal_comes_before_the_unknown_user_s_failure_on_flush(db, w1, mk_factory, mk_line, mk_batch):
    """FAC-D-27 — the refusal comes before the unknown user's failure on flush.
    Rules: `delete_factory` R5a [BUG-1331], R8"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    before_f1 = snap(db, f1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": b1.id}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, b1) == before_b1
    # Then 9
    assert written(db) == before


# [claude] FAC-D-28
def test_fac_d_28__an_already_deleted_factory_with_an_open_batch_is_answered_with_400(db, w1, u1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-28 — an already deleted factory with an open batch is answered with 400, not refused with blockers.
    Rules: `delete_factory` R2, R5a"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    l1 = mk_line(of=fd, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    before_fd = snap(db, fd)
    before_b1 = snap(db, b1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=fd.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory is already deleted"
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert snap(db, b1) == before_b1
    # Then 6
    row = reread(db, fd)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id


# [claude] FAC-D-29
def test_fac_d_29__a_factory_of_another_workspace_with_an_open_batch_is_answered_with(db, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-29 — a factory of another workspace with an open batch is answered with 404, not refused with blockers.
    Rules: `delete_factory` R1, R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")
    before_f1 = snap(db, f1)
    before_b1 = snap(db, b1)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w2.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {f1.id} not found"
    # Then 4
    assert snap(db, f1) == before_f1
    # Then 5
    assert snap(db, b1) == before_b1


# [claude] FAC-D-30
def test_fac_d_30__a_completed_batch_does_not_block_and_is_left_as_it_was(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-30 — a completed batch does not block and is left as it was.
    Rules: `delete_factory` R5, R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="completed")
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert snap(db, b1) == before_b1
    # Then 6
    assert reread(db, b1).status == "completed"


# [claude] FAC-D-31
def test_fac_d_31__a_cancelled_batch_does_not_block_and_is_left_as_it_was(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-31 — a cancelled batch does not block and is left as it was.
    Rules: `delete_factory` R5, R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="cancelled")
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert snap(db, b1) == before_b1
    # Then 6
    assert reread(db, b1).status == "cancelled"


# [claude] FAC-D-32
def test_fac_d_32__a_production_line_without_batches_does_not_block_and_is_left_as_it(db, w1, u2, mk_factory, mk_line):
    """FAC-D-32 — a production line without batches does not block and is left as it was.
    Rules: `delete_factory` R5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    before_l1 = snap(db, l1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert reread(db, l1).is_active is True


# [claude] FAC-D-33
def test_fac_d_33__an_open_batch_of_another_factory_of_the_workspace_does_not_block(db, w1, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-33 — an open batch of another factory of the workspace does not block.
    Rules: `delete_factory` R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f2 = mk_factory(name="Second", abbreviation="SC")
    l2 = mk_line(of=f2, name="Line B")
    b2 = mk_batch(on=l2, batch_number="BATCH-2026-001", status="draft")
    before_f2 = snap(db, f2)
    before_l2 = snap(db, l2)
    before_b2 = snap(db, b2)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, f2) == before_f2
    # Then 5
    assert snap(db, l2) == before_l2
    # Then 6
    assert snap(db, b2) == before_b2


# [claude] FAC-D-34
def test_fac_d_34__an_open_batch_of_a_factory_of_another_workspace_does_not_block(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-34 — an open batch of a factory of another workspace does not block.
    Rules: `delete_factory` R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    l9 = mk_line(of=f9, name="Line Z")
    b9 = mk_batch(on=l9, batch_number="BATCH-2026-001", status="in_progress")
    before_f9 = snap(db, f9)
    before_l9 = snap(db, l9)
    before_b9 = snap(db, b9)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, f9) == before_f9
    # Then 5
    assert snap(db, l9) == before_l9
    # Then 6
    assert snap(db, b9) == before_b9


# [claude] FAC-D-35
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_35__a_draft_batch_of_another_workspace_on_the_factory_s_own_line_gives(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-35 — a draft batch of another workspace on the factory's own line gives one generic entry.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft", workspace_id=w2.id)
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, b1) == before_b1
    # Then 10
    assert written(db) == before


# [claude] FAC-D-36
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_36__an_in_progress_batch_of_another_workspace_on_another_workspace_s_l(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-36 — an in_progress batch of another workspace on another workspace's line of the factory gives one generic entry.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A", workspace_id=w2.id)
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="in_progress")
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, b1) == before_b1
    # Then 10
    assert written(db) == before


# [claude] FAC-D-37
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_37__a_batch_of_the_factory_s_workspace_on_another_workspace_s_line_of(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-37 — a batch of the factory's workspace on another workspace's line of the factory gives one generic entry, not its id.
    Rules: `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A", workspace_id=w2.id)
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft", workspace_id=w1.id)
    before_f1 = snap(db, f1)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert snap(db, l1) == before_l1
    # Then 9
    assert snap(db, b1) == before_b1
    # Then 10
    assert written(db) == before


# [claude] FAC-D-38
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_38__two_cross_workspace_batches_give_the_generic_entry_once(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-38 — two cross-workspace batches give the generic entry once.
    Rules: `delete_factory` R5b [BUG-1331], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft", workspace_id=w2.id)
    mk_batch(on=l1, batch_number="BATCH-2026-002", status="in_progress", workspace_id=w2.id)
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "other_workspace"}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert written(db) == before


# [claude] FAC-D-39
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fac_d_39__the_generic_entry_comes_last_also_when_the_foreign_batch_has_the_l(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-39 — the generic entry comes last, also when the foreign batch has the lower id.
    Rules: `delete_factory` R5b [BUG-1331], Errors row 5"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft", workspace_id=w2.id)
    bo = mk_batch(on=l1, batch_number="BATCH-2026-002", status="in_progress")
    before_f1 = snap(db, f1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert type(exc.value) is ValueError
    # Then 3
    assert len(exc.value.args) == 2
    # Then 4
    assert exc.value.args[0] == "Factory has open production batches"
    # Then 5
    assert exc.value.args[1] == [{"type": "production_batch", "id": bo.id}, {"type": "other_workspace"}]
    # Then 6
    assert snap(db, f1) == before_f1
    # Then 7
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 8
    assert written(db) == before


# [claude] FAC-D-40
def test_fac_d_40__a_completed_batch_of_another_workspace_on_the_factory_s_own_line_d(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-40 — a completed batch of another workspace on the factory's own line does not block.
    Rules: `delete_factory` R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A")
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="completed", workspace_id=w2.id)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert snap(db, b1) == before_b1


# [claude] FAC-D-41
def test_fac_d_41__a_cancelled_batch_of_another_workspace_on_another_workspace_s_line(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-41 — a cancelled batch of another workspace on another workspace's line of the factory does not block.
    Rules: `delete_factory` R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A", workspace_id=w2.id)
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="cancelled")
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert snap(db, b1) == before_b1


# [claude] FAC-D-42
def test_fac_d_42__a_completed_batch_of_the_factory_s_workspace_on_another_workspace(db, w1, w2, u2, mk_factory, mk_line, mk_batch):
    """FAC-D-42 — a completed batch of the factory's workspace on another workspace's line of the factory does not block.
    Rules: `delete_factory` R5a"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    l1 = mk_line(of=f1, name="Line A", workspace_id=w2.id)
    b1 = mk_batch(on=l1, batch_number="BATCH-2026-001", status="completed", workspace_id=w1.id)
    before_l1 = snap(db, l1)
    before_b1 = snap(db, b1)

    result = M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert snap(db, b1) == before_b1


# [claude] FAC-CN-20
@pytest.mark.xfail(strict=True, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories")
def test_fac_cn_20__the_name_check_does_not_read_a_capped_page_of_the_workspace(db, w1, mk_factory):
    """FAC-CN-20 — the name check does not read a capped page of the workspace.
    Rules: `_check_name_exists` R5 [BUG-893]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant")
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert result is True
    # Then 2
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    factory_selects = [stmt for stmt in flat if stmt.startswith("SELECT") and " FROM FACTORIES" in stmt]
    where = [stmt.split(" WHERE ", 1)[1].split(" ORDER BY ")[0].split(" LIMIT ")[0] for stmt in factory_selects if " WHERE " in stmt]
    assert any('NAME' in clause for clause in where) or not any(" LIMIT " in stmt for stmt in factory_selects)


# [claude] FAC-CA-20
@pytest.mark.xfail(strict=True, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories")
def test_fac_ca_20__the_abbreviation_check_does_not_read_a_capped_page_of_the_workspace(db, w1, mk_factory):
    """FAC-CA-20 — the abbreviation check does not read a capped page of the workspace.
    Rules: `_check_abbreviation_exists` R5 [BUG-893]"""
    mk_factory(name="Main Plant", abbreviation="MP")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP")
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert result is True
    # Then 2
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    factory_selects = [stmt for stmt in flat if stmt.startswith("SELECT") and " FROM FACTORIES" in stmt]
    where = [stmt.split(" WHERE ", 1)[1].split(" ORDER BY ")[0].split(" LIMIT ")[0] for stmt in factory_selects if " WHERE " in stmt]
    assert any('ABBREVIATION' in clause for clause in where) or not any(" LIMIT " in stmt for stmt in factory_selects)


# [claude] FAC-S-54
@pytest.mark.xfail(strict=True, reason="BUG-898: Factory list drops deleted rows and applies the search after paging")
def test_fac_s_54__the_search_text_is_applied_in_the_list_query(db, w1, mk_factory):
    """FAC-S-54 — the search text is applied in the list query.
    Rules: `search_factories` R2 [BUG-898], R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = M.search_factories(db, workspace_id=w1.id, search="plant")
    finally:
        event.remove(bind, "before_cursor_execute", record)

    # Then 1
    assert ids(result) == [f1.id]
    # Then 2
    flat = [" ".join(stmt.upper().split()) for stmt in statements]
    factory_selects = [stmt for stmt in flat if stmt.startswith("SELECT") and " FROM FACTORIES" in stmt]
    where = [stmt.split(" WHERE ", 1)[1].split(" ORDER BY ")[0].split(" LIMIT ")[0] for stmt in factory_selects if " WHERE " in stmt]
    assert any("NAME" in clause for clause in where)
