"""Unit tests for app/managers/work_order_type_manager.py.

Implements tests/unit/managers/work_order_type_manager.cases.md (revision 2), one
test per case. Real Postgres session (`db` fixture). Only mock: the spec's
external `app.dao.work_order_type.utcnow` (every test), plus the listed race
simulations (`WorkOrderTypeManager._check_name_exists` -> False).
"""
import re
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.managers.work_order_type_manager import (
    WorkOrderTypeManager,
    work_order_type_manager,
)
from app.models.work_order_type import WorkOrderType
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate
from tests.unit.factories import make_profile, make_workspace

# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "MISSING", "T0", "NOW" (both naive)
MISSING = 999999999
T0 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 1, 15, 10, 30, 0)  # noqa: DTZ001

BUG_1214 = "BUG-1214: A deleted work order type's name cannot be used again"
BUG_1521 = "BUG-1521: A deleted work order type is returned by id"
BUG_1706 = "BUG-1706: Duplicate work order type name check only scans the first 100 rows"
BUG_1707 = "BUG-1707: Work order type name check is case- and whitespace-sensitive"
BUG_1708 = "BUG-1708: Blank work order type names accepted, names stored untrimmed"
BUG_1709 = "BUG-1709: Work order type list filters deleted rows and the search after paging"
BUG_1710 = "BUG-1710: Work order type list has no sort order"
BUG_1711 = "BUG-1711: updated_by stamped on no-op work order type updates"


def _row_order(bug):
    """Reason for a non-strict card: its failure today rests on physical row order."""
    return (
        f"{bug} (non-strict: today's outcome rests on physical row order, which the query does "
        "not fix, so another order can make it pass by accident)"
    )


# Convention "Externals": every test patches app.dao.work_order_type.utcnow -> NOW
@pytest.fixture(autouse=True)
def _utcnow():
    with patch("app.dao.work_order_type.utcnow", return_value=NOW) as m:
        yield m


# Convention "Race simulations": only WOTM-C-12, C-13, U-21 use this
@pytest.fixture
def race():
    with patch.object(WorkOrderTypeManager, "_check_name_exists", return_value=False) as m:
        yield m


# Convention "W1, W2 = two workspaces rows made in that order (W1.id < W2.id)"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 acts, U2 created every Given row)
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "M = the singleton work_order_type_manager"
@pytest.fixture
def M():
    return work_order_type_manager


# Convention "type" / "gone": inserted directly, one flush per row, so ids rise
# in Given order. Defaults: workspace W1, created_by U2, is_active True,
# is_deleted False, updated_by / deleted_at / deleted_by None.
@pytest.fixture
def wot(db, w1, w2, u2):
    def _mk(name, *, ws=None, gone=False, updated_by=None):
        row = WorkOrderType(
            workspace_id=(ws or w1).id,
            name=name,
            created_by=u2.id,
            is_active=True,
            is_deleted=gone,
            updated_by=None if updated_by is None else updated_by.id,
            deleted_at=T0 if gone else None,
            deleted_by=u2.id if gone else None,
        )
        db.add(row)
        db.flush()
        return row

    return _mk


# Convention "N rows, by add_all": one add_all, one flush, ids rise in list order
@pytest.fixture
def wots_add_all(db, w1, u2):
    def _mk(names, *, gone=False):
        rows = [
            WorkOrderType(
                workspace_id=w1.id,
                name=n,
                created_by=u2.id,
                is_active=True,
                is_deleted=gone,
                deleted_at=T0 if gone else None,
                deleted_by=u2.id if gone else None,
            )
            for n in names
        ]
        db.add_all(rows)
        db.flush()
        return rows

    return _mk


# Convention "re-read X": db.expire_all(), then SELECT X by id
def reread(db, row_id):
    db.expire_all()
    return db.execute(select(WorkOrderType).where(WorkOrderType.id == row_id)).scalar_one()


# Convention "unchanged(X)": every column of X, read from the database
def snap(db, row_id):
    r = reread(db, row_id)
    return {c.key: getattr(r, c.key) for c in WorkOrderType.__table__.columns}


# Convention "count:" rows of a workspace (optionally of one name), fresh query
def count_ws(db, ws, name=None):
    db.expire_all()
    q = select(func.count()).select_from(WorkOrderType).where(WorkOrderType.workspace_id == ws.id)
    if name is not None:
        q = q.where(WorkOrderType.name == name)
    return db.scalar(q)


# Convention "nothing written": work_order_types rows of all workspaces
def count_all(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(WorkOrderType))


# Convention "ids(result)" / "names(result)": in the order returned
def ids(result):
    return [r.id for r in result]


def names(result):
    return [r.name for r in result]


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
def commit_spy(db, monkeypatch):
    spy = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# Convention "sql_log": a before_cursor_execute listener on db.connection(); removed after the call
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


# --------------------------------------------------------------------------- #
# create_work_order_type
# --------------------------------------------------------------------------- #

def test_wotm_c_01__new_type_stored(db, M, w1, u1):
    """WOTM-C-01 — a new type is stored with its name, workspace and creator.
    Rules: create_work_order_type R1, R5, Side effects."""
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert isinstance(result, WorkOrderType)
    assert result.id is not None
    # Then 2
    assert result.name == "Repair"
    new_id = result.id
    # Then 3
    row = reread(db, new_id)
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    row = reread(db, new_id)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.updated_by is None
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert count_ws(db, w1) == 1


def test_wotm_c_02__live_duplicate_409(db, M, wot, w1, u1):
    """WOTM-C-02 — a live type of the same name is refused with 409.
    Rules: create_work_order_type R2, Errors row 1."""
    a = wot("Repair")
    before_all = count_all(db)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'Repair' already exists"
    # Then 4
    assert count_all(db) == before_all
    # Then 5
    assert snap(db, a.id) == before_a


def test_wotm_c_03__same_name_other_workspace_ok(db, M, wot, w1, w2, u1):
    """WOTM-C-03 — the same name in another workspace does not block.
    Rules: create_work_order_type R3a, R1."""
    z = wot("Repair", ws=w2)
    before_z = snap(db, z.id)
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id != z.id
    new_id = result.id
    # Then 2
    row = reread(db, new_id)
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    # Then 3
    assert count_ws(db, w1) == 1
    # Then 4
    assert snap(db, z.id) == before_z


@pytest.mark.xfail(strict=True, reason=BUG_1214)
def test_wotm_c_04__deleted_exact_name_reusable(db, M, wot, w1, u1, u2):
    """WOTM-C-04 — a soft-deleted type's exact name can be used again.
    Rules: create_work_order_type R3 [BUG-1214]."""
    d = wot("Repair", gone=True)
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id != d.id
    new_id = result.id
    # Then 2
    row = reread(db, new_id)
    assert row.name == "Repair"
    assert row.is_deleted is False
    # Then 3
    row = reread(db, d.id)
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u2.id
    # Then 4
    assert count_ws(db, w1) == 2


@pytest.mark.xfail(strict=True, reason=BUG_1707)
def test_wotm_c_05__case_variant_409(db, M, wot, w1, u1):
    """WOTM-C-05 — a live name in other case is refused, the detail shows the submitted name.
    Rules: create_work_order_type R2, Errors row 1 [BUG-1707]."""
    wot("Repair")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'repair' already exists"
    # Then 4
    assert count_ws(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_c_06__padded_duplicate_409(db, M, wot, w1, u1):
    """WOTM-C-06 — a padded live name is trimmed by the schema and refused.
    Rules: create_work_order_type R2, R4 [BUG-1708]."""
    wot("Repair")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name=" Repair "), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'Repair' already exists"
    # Then 4
    assert count_ws(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_c_07__empty_name_rejected_by_schema(db, w1):
    """WOTM-C-07 — an empty name is refused by the schema.
    Rules: create_work_order_type R4, Errors row 3 [BUG-1708]."""
    # Then 1
    with pytest.raises(ValidationError):
        WorkOrderTypeCreate(name="")
    # Then 2
    assert count_ws(db, w1) == 0


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_c_08__whitespace_name_rejected_by_schema(db, w1):
    """WOTM-C-08 — a whitespace-only name is refused by the schema.
    Rules: create_work_order_type R4, Errors row 3 [BUG-1708]."""
    # Then 1
    with pytest.raises(ValidationError):
        WorkOrderTypeCreate(name="   ")
    # Then 2
    assert count_ws(db, w1) == 0


def test_wotm_c_09__one_char_name_accepted(db, M, w1, u1):
    """WOTM-C-09 — a one-character name is accepted.
    Rules: create_work_order_type R4."""
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="a"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "a"
    # Then 2
    assert reread(db, result.id).name == "a"


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_c_10__padded_name_stored_trimmed(db, M, w1, u1):
    """WOTM-C-10 — outer spaces are trimmed before the name is stored.
    Rules: create_work_order_type R4 [BUG-1708]."""
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name=" Field Repair "), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Field Repair"
    # Then 2
    assert reread(db, result.id).name == "Field Repair"


def test_wotm_c_11__case_and_inner_spaces_kept(db, M, w1, u1):
    """WOTM-C-11 — case and inner spaces are stored as typed.
    Rules: create_work_order_type R4."""
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="field  REPAIR"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "field  REPAIR"
    # Then 2
    assert reread(db, result.id).name == "field  REPAIR"


# [claude] WOTM-C-12
def test_wotm_c_12__race_duplicate_refused_by_constraint(db, M, wot, w1, u1, race):
    """WOTM-C-12 — a duplicate past the Python check is refused by the database constraint.
    Rules: create_work_order_type R6, Errors row 2."""
    wot("Repair")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert exc.value.orig.diag.constraint_name == "uq_wo_type_workspace_name"
    # Then 4
    assert count_ws(db, w1, name="Repair") == 1
    # Then 5
    assert count_ws(db, w1) == 1


# [claude] WOTM-C-13
@pytest.mark.xfail(strict=True, reason=BUG_1214)
def test_wotm_c_13__race_case_variant_refused_by_constraint(db, M, wot, w1, u1, race):
    """WOTM-C-13 — the database also refuses a case variant past the Python check.
    Rules: create_work_order_type R6a, Errors row 2 [BUG-1214]."""
    wot("Repair")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_ws(db, w1) == 1


# [claude] WOTM-C-14
def test_wotm_c_14__create_flushed_not_committed(db, M, w1, u1, monkeypatch):
    """WOTM-C-14 — create flushes and never commits.
    Rules: create_work_order_type Side effects (no commit)."""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_ws(db, w1) == 1
    sp.rollback()
    # Then 3
    assert count_ws(db, w1) == 0
    # Then 4
    spy.assert_not_called()


def test_wotm_c_15__deleted_name_other_case_free(db, M, wot, w1, u1, u2):
    """WOTM-C-15 — a deleted type's name in other case does not block.
    Rules: create_work_order_type R3, R1."""
    d = wot("repair", gone=True)
    result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id != d.id
    new_id = result.id
    # Then 2
    row = reread(db, new_id)
    assert row.name == "Repair"
    assert row.is_deleted is False
    # Then 3
    row = reread(db, d.id)
    assert row.name == "repair"
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u2.id
    # Then 4
    assert count_ws(db, w1) == 2


# --------------------------------------------------------------------------- #
# update_work_order_type
# --------------------------------------------------------------------------- #

def test_wotm_u_01__rename_happy_path(db, M, wot, w1, u1, u2):
    """WOTM-U-01 — a rename changes the name and stamps updated_by, nothing else.
    Rules: update_work_order_type R4, R9, R10, Side effects."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="Field Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Field Repair"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Field Repair"
    assert row.updated_by == u1.id
    assert row.updated_at is not None
    # Then 3
    row = reread(db, a.id)
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None


def test_wotm_u_02__unknown_id_404(db, M, wot, w1, u1):
    """WOTM-U-02 — an unknown id gets 404.
    Rules: update_work_order_type R1, Errors row 1."""
    a = wot("Repair")
    before_all = count_all(db)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=MISSING, type_data=WorkOrderTypeUpdate(name="Inspection"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 999999999 not found"
    # Then 4
    assert count_all(db) == before_all
    # Then 5
    assert snap(db, a.id) == before_a


def test_wotm_u_03__other_workspace_404(db, M, wot, w1, w2, u1):
    """WOTM-U-03 — another workspace's type gets 404 and is not touched.
    Rules: update_work_order_type R2, Errors row 1."""
    z = wot("Repair", ws=w2)
    before_z = snap(db, z.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=z.id, type_data=WorkOrderTypeUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"
    # Then 4
    assert snap(db, z.id) == before_z


def test_wotm_u_04__deleted_400_before_name_check(db, M, wot, w1, u1):
    """WOTM-U-04 — a deleted type gets 400 before any name check.
    Rules: update_work_order_type R3, Errors row 2."""
    a = wot("Inspection")
    d = wot("Repair", gone=True)
    before_d = snap(db, d.id)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=d.id, type_data=WorkOrderTypeUpdate(name="Inspection"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted work order type"
    # Then 4
    assert snap(db, d.id) == before_d
    # Then 5
    assert snap(db, a.id) == before_a


def test_wotm_u_05__deleted_400_empty_body(db, M, wot, w1, u1, u2):
    """WOTM-U-05 — a deleted type gets 400 also with an empty body.
    Rules: update_work_order_type R3, Errors row 2."""
    d = wot("Repair", gone=True, updated_by=u2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=d.id, type_data=WorkOrderTypeUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted work order type"
    # Then 4
    row = reread(db, d.id)
    assert row.name == "Repair"
    assert row.updated_by == u2.id
    assert row.is_deleted is True


def test_wotm_u_06__rename_to_live_name_409(db, M, wot, w1, u1, u2):
    """WOTM-U-06 — a name another live type has is refused with 409.
    Rules: update_work_order_type R6, Errors row 3."""
    a = wot("Repair")
    b = wot("Inspection", updated_by=u2)
    before_b = snap(db, b.id)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=b.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'Repair' already exists"
    # Then 4
    assert snap(db, b.id) == before_b
    # Then 5
    assert snap(db, a.id) == before_a


def test_wotm_u_07__name_in_other_workspace_free(db, M, wot, w1, w2, u1):
    """WOTM-U-07 — a name used only in another workspace is free.
    Rules: update_work_order_type R6, R4."""
    z = wot("Repair", ws=w2)
    b = wot("Inspection")
    before_z = snap(db, z.id)
    result = M.update_work_order_type(db, type_id=b.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Repair"
    # Then 2
    row = reread(db, b.id)
    assert row.name == "Repair"
    assert row.updated_by == u1.id
    # Then 3
    assert snap(db, z.id) == before_z


@pytest.mark.xfail(strict=True, reason=BUG_1214)
def test_wotm_u_08__deleted_exact_name_taken_by_rename(db, M, wot, w1, u1):
    """WOTM-U-08 — a deleted type's exact name can be taken by a rename.
    Rules: update_work_order_type R6a [BUG-1214]."""
    d = wot("Repair", gone=True)
    b = wot("Inspection")
    before_d = snap(db, d.id)
    result = M.update_work_order_type(db, type_id=b.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Repair"
    # Then 2
    row = reread(db, b.id)
    assert row.name == "Repair"
    assert row.updated_by == u1.id
    # Then 3
    assert snap(db, d.id) == before_d


def test_wotm_u_09__own_name_case_change(db, M, wot, w1, u1):
    """WOTM-U-09 — a type may change the case of its own name.
    Rules: update_work_order_type R6 (this type excluded), R4."""
    a = wot("Repair")
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "repair"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "repair"
    assert row.updated_by == u1.id


@pytest.mark.xfail(strict=True, reason=BUG_1707)
def test_wotm_u_10__rename_to_case_variant_409(db, M, wot, w1, u1):
    """WOTM-U-10 — another live type's name in other case is refused with 409.
    Rules: update_work_order_type R6, Errors row 3 [BUG-1707]."""
    a = wot("Repair")
    wot("Inspection")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="INSPECTION"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'INSPECTION' already exists"
    # Then 4
    assert reread(db, a.id).name == "Repair"


def test_wotm_u_11__empty_body_leaves_row(db, M, wot, w1, u1, u2):
    """WOTM-U-11 — an empty body leaves the name and other fields alone (updated_by not checked).
    Rules: update_work_order_type R7, R10."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Repair"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    # Then 3
    row = reread(db, a.id)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert count_ws(db, w1) == 1


def test_wotm_u_12__null_name_leaves_row(db, M, wot, w1, u1, u2):
    """WOTM-U-12 — an explicit null name leaves the name alone (updated_by not checked).
    Rules: update_work_order_type R7, R10."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name=None), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Repair"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False


def test_wotm_u_13__current_name_not_duplicate(db, M, wot, w1, u1, u2):
    """WOTM-U-13 — the current name is not a duplicate of itself (updated_by not checked).
    Rules: update_work_order_type R5, R10."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Repair"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False


@pytest.mark.xfail(strict=True, reason=BUG_1711)
def test_wotm_u_14__empty_body_keeps_updated_by(db, M, wot, w1, u1, u2):
    """WOTM-U-14 — an empty body does not stamp updated_by.
    Rules: update_work_order_type R9 [BUG-1711]."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1711)
def test_wotm_u_15__null_name_keeps_updated_by(db, M, wot, w1, u1, u2):
    """WOTM-U-15 — an explicit null name does not stamp updated_by.
    Rules: update_work_order_type R9 [BUG-1711]."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name=None), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1711)
def test_wotm_u_16__same_name_keeps_updated_by(db, M, wot, w1, u1, u2):
    """WOTM-U-16 — the unchanged name does not stamp updated_by.
    Rules: update_work_order_type R9 [BUG-1711]."""
    a = wot("Repair", updated_by=u2)
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_u_17__padded_current_name_trimmed(db, M, wot, w1, u1):
    """WOTM-U-17 — the current name with outer spaces is trimmed and counts as unchanged.
    Rules: update_work_order_type R5, R8 [BUG-1708]."""
    a = wot("Repair")
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name=" Repair "), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Repair"
    # Then 2
    assert reread(db, a.id).name == "Repair"


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_u_18__empty_name_rejected_by_update_schema(db, wot):
    """WOTM-U-18 — an empty name is refused by the update schema.
    Rules: update_work_order_type R8, Errors row 5 [BUG-1708]."""
    a = wot("Repair")
    # Then 1
    with pytest.raises(ValidationError):
        WorkOrderTypeUpdate(name="")
    # Then 2
    assert reread(db, a.id).name == "Repair"


@pytest.mark.xfail(strict=True, reason=BUG_1708)
def test_wotm_u_19__whitespace_name_rejected_by_update_schema(db, wot):
    """WOTM-U-19 — a whitespace-only name is refused by the update schema.
    Rules: update_work_order_type R8, Errors row 5 [BUG-1708]."""
    a = wot("Repair")
    # Then 1
    with pytest.raises(ValidationError):
        WorkOrderTypeUpdate(name="   ")
    # Then 2
    assert reread(db, a.id).name == "Repair"


def test_wotm_u_20__one_char_new_name(db, M, wot, w1, u1):
    """WOTM-U-20 — a one-character new name is accepted.
    Rules: update_work_order_type R8, R4."""
    a = wot("Repair")
    result = M.update_work_order_type(db, type_id=a.id, type_data=WorkOrderTypeUpdate(name="a"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "a"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "a"
    assert row.updated_by == u1.id


# [claude] WOTM-U-21
def test_wotm_u_21__race_rename_refused_by_constraint(db, M, wot, w1, u1, u2, race):
    """WOTM-U-21 — a rename onto a live duplicate past the Python check is refused by the constraint.
    Rules: update_work_order_type R11, Errors row 4."""
    wot("Repair")
    b = wot("Inspection", updated_by=u2)
    b_id = b.id
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            M.update_work_order_type(db, type_id=b_id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert exc.value.orig.diag.constraint_name == "uq_wo_type_workspace_name"
    # Then 4
    row = reread(db, b_id)
    assert row.name == "Inspection"
    assert row.updated_by == u2.id


# [claude] WOTM-U-22
def test_wotm_u_22__update_flushed_not_committed(db, M, wot, w1, u1, u2, monkeypatch):
    """WOTM-U-22 — update flushes and never commits.
    Rules: update_work_order_type Side effects (no commit)."""
    a = wot("Repair", updated_by=u2)
    a_id = a.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.update_work_order_type(db, type_id=a_id, type_data=WorkOrderTypeUpdate(name="Overhaul"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Overhaul"
    # Then 2
    assert reread(db, a_id).name == "Overhaul"
    sp.rollback()
    # Then 3
    row = reread(db, a_id)
    assert row.name == "Repair"
    assert row.updated_by == u2.id
    # Then 4
    spy.assert_not_called()


def test_wotm_u_23__deleted_name_other_case_free_for_rename(db, M, wot, w1, u1):
    """WOTM-U-23 — a deleted type's name in other case is free for a rename.
    Rules: update_work_order_type R6, R4."""
    d = wot("repair", gone=True)
    b = wot("Inspection")
    before_d = snap(db, d.id)
    result = M.update_work_order_type(db, type_id=b.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Repair"
    # Then 2
    row = reread(db, b.id)
    assert row.name == "Repair"
    assert row.updated_by == u1.id
    # Then 3
    assert snap(db, d.id) == before_d


# --------------------------------------------------------------------------- #
# get_work_order_type
# --------------------------------------------------------------------------- #

def test_wotm_g_01__live_type_by_id(db, M, wot, w1):
    """WOTM-G-01 — a live type is returned by its id.
    Rules: get_work_order_type R1."""
    wot("Assembly")
    t = wot("Repair")
    wot("Service")
    result = M.get_work_order_type(db, type_id=t.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, WorkOrderType)
    # Then 2
    assert result.id == t.id
    assert result.name == "Repair"
    assert result.workspace_id == w1.id


def test_wotm_g_02__unknown_id_404(db, M, wot, w1):
    """WOTM-G-02 — an unknown id gets 404.
    Rules: get_work_order_type R2, Errors."""
    wot("Repair")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 999999999 not found"


def test_wotm_g_03__id_zero_404(db, M, wot, w1):
    """WOTM-G-03 — id 0 gets 404.
    Rules: get_work_order_type R2, Errors."""
    wot("Repair")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 0 not found"


def test_wotm_g_04__higher_workspace_404(db, M, wot, w1, w2):
    """WOTM-G-04 — a type of a workspace with a higher id gets 404.
    Rules: get_work_order_type R2, Errors."""
    wot("Repair")
    z = wot("Inspection", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"


def test_wotm_g_05__lower_workspace_404(db, M, wot, w2):
    """WOTM-G-05 — a type of a workspace with a lower id gets 404.
    Rules: get_work_order_type R2, Errors."""
    a = wot("Repair")
    wot("Inspection", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=a.id, workspace_id=w2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {a.id} not found"


@pytest.mark.xfail(strict=True, reason=BUG_1521)
def test_wotm_g_06__deleted_hidden_by_default(db, M, wot, w1):
    """WOTM-G-06 — a soft-deleted type is hidden by default.
    Rules: get_work_order_type R3, Errors [BUG-1521]."""
    d = wot("Repair", gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=d.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {d.id} not found"


@pytest.mark.xfail(strict=True, reason=BUG_1521)
def test_wotm_g_07__include_deleted_returns_deleted(db, M, wot, w1):
    """WOTM-G-07 — include_deleted=True returns a soft-deleted type.
    Rules: get_work_order_type R4 [BUG-1521]."""
    d = wot("Repair", gone=True)
    result = M.get_work_order_type(db, type_id=d.id, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert result.id == d.id
    # Then 2
    assert result.is_deleted is True


@pytest.mark.xfail(strict=True, reason=BUG_1521)
def test_wotm_g_08__include_deleted_keeps_isolation(db, M, wot, w1, w2):
    """WOTM-G-08 — include_deleted=True does not reach another workspace.
    Rules: get_work_order_type R4, Errors [BUG-1521]."""
    z = wot("Repair", ws=w2, gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_work_order_type(db, type_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"


def test_wotm_g_09__read_keeps_unflushed_edits(db, M, wot, w1, u2):
    """WOTM-G-09 — the read writes nothing and keeps the caller's unflushed edits.
    Rules: get_work_order_type Side effects."""
    a = wot("Repair")
    b = wot("Inspection")
    b.name = "Edited"
    p = WorkOrderType(workspace_id=w1.id, name="Pending", created_by=u2.id)
    db.add(p)
    result = M.get_work_order_type(db, type_id=a.id, workspace_id=w1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert p in db.new
    # Then 5
    assert len(db.new) == 1
    # Then 6
    assert not db.deleted


# --------------------------------------------------------------------------- #
# search_work_order_types
# --------------------------------------------------------------------------- #

FIVE = ("Alpha", "Bravo", "Charlie", "Delta", "Echo")


def test_wotm_s_01__own_workspace_other_higher(db, M, wot, w1, w2):
    """WOTM-S-01 — only the workspace's types are listed (other workspace has the higher id).
    Rules: search_work_order_types R1."""
    a = wot("Repair")
    b = wot("Inspection")
    wot("Service", ws=w2)
    result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_wotm_s_02__own_workspace_other_lower(db, M, wot, w2):
    """WOTM-S-02 — only the workspace's types are listed (other workspace has the lower id).
    Rules: search_work_order_types R1."""
    wot("Repair")
    z = wot("Service", ws=w2)
    result = M.search_work_order_types(db, workspace_id=w2.id)
    # Then 1
    assert ids(result) == [z.id]


def test_wotm_s_03__deleted_left_out(db, M, wot, w1):
    """WOTM-S-03 — soft-deleted types are left out by default.
    Rules: search_work_order_types R4."""
    a = wot("Repair")
    wot("Inspection", gone=True)
    result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]


def test_wotm_s_04__include_deleted_keeps_deleted(db, M, wot, w1):
    """WOTM-S-04 — include_deleted=True keeps soft-deleted types.
    Rules: search_work_order_types R5."""
    a = wot("Repair")
    d = wot("Inspection", gone=True)
    result = M.search_work_order_types(db, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert sorted(ids(result)) == [a.id, d.id]


# [claude] WOTM-S-05
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1709))
def test_wotm_s_05__deleted_take_no_place_in_page(db, M, wot, w1):
    """WOTM-S-05 — deleted types take no place in the page (limit).
    Rules: search_work_order_types R2, R4 [BUG-1709]."""
    wot("Audit 1", gone=True)
    wot("Audit 2", gone=True)
    wot("Audit 3", gone=True)
    a = wot("Inspection")
    b = wot("Repair")
    result = M.search_work_order_types(db, workspace_id=w1.id, limit=2)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] WOTM-S-06
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1709))
def test_wotm_s_06__deleted_not_counted_by_skip(db, M, wot, w1):
    """WOTM-S-06 — deleted types are not counted by skip.
    Rules: search_work_order_types R2, R4 [BUG-1709]."""
    wot("Audit 1", gone=True)
    wot("Audit 2", gone=True)
    wot("Audit 3", gone=True)
    a = wot("Inspection")
    b = wot("Repair")
    result = M.search_work_order_types(db, workspace_id=w1.id, skip=1, limit=1000)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] WOTM-S-07
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1709))
def test_wotm_s_07__search_past_first_page(db, M, wot, w1):
    """WOTM-S-07 — the search looks past the first page.
    Rules: search_work_order_types R2, R6 [BUG-1709]."""
    wot("Assembly")
    wot("Cleaning")
    wot("Inspection")
    x = wot("Repair")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="pair", limit=2)
    # Then 1
    assert ids(result) == [x.id]


def test_wotm_s_08__full_page(db, M, wot, w1):
    """WOTM-S-08 — a page is full when skip + limit equals the matches.
    Rules: search_work_order_types R2."""
    for n in FIVE:
        wot(n)
    result = M.search_work_order_types(db, workspace_id=w1.id, skip=2, limit=3)
    # Then 1
    assert len(result) == 3


def test_wotm_s_09__short_page(db, M, wot, w1):
    """WOTM-S-09 — a page is short when skip + limit passes the matches.
    Rules: search_work_order_types R2."""
    for n in FIVE:
        wot(n)
    result = M.search_work_order_types(db, workspace_id=w1.id, skip=3, limit=3)
    # Then 1
    assert len(result) == 2


def test_wotm_s_10__skip_at_matches_empty(db, M, wot, w1):
    """WOTM-S-10 — skip at the number of matches gives an empty list.
    Rules: search_work_order_types R8."""
    for n in FIVE:
        wot(n)
    result = M.search_work_order_types(db, workspace_id=w1.id, skip=5)
    # Then 1
    assert result == []


def test_wotm_s_11__default_limit_100(db, M, wots_add_all, w1):
    """WOTM-S-11 — the default limit is 100.
    Rules: search_work_order_types R2 (default limit)."""
    wots_add_all([f"Kind {k:03d}" for k in range(1, 102)])
    result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100


def test_wotm_s_12__limit_1000_past_100(db, M, wots_add_all, w1):
    """WOTM-S-12 — limit=1000 lists past 100.
    Rules: search_work_order_types R2."""
    wots_add_all([f"Kind {k:03d}" for k in range(1, 102)])
    result = M.search_work_order_types(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert len(result) == 101


def test_wotm_s_13__substring_ignoring_case(db, M, wot, w1):
    """WOTM-S-13 — search matches a part of the name, ignoring case on both sides.
    Rules: search_work_order_types R6."""
    a = wot("Repair")
    b = wot("PREREPAIR")
    wot("Inspection")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="Pai")
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_wotm_s_14__leading_space_counts(db, M, wot, w1):
    """WOTM-S-14 — a leading space in the search counts.
    Rules: search_work_order_types R6."""
    a = wot("Field Repair")
    wot("Repaint")
    result = M.search_work_order_types(db, workspace_id=w1.id, search=" rep")
    # Then 1
    assert ids(result) == [a.id]


def test_wotm_s_15__percent_literal(db, M, wot, w1):
    """WOTM-S-15 — `%` in the search matches only itself.
    Rules: search_work_order_types R6a (HR-8)."""
    a = wot("Check 100%")
    wot("Repair")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="%")
    # Then 1
    assert ids(result) == [a.id]


def test_wotm_s_16__underscore_literal(db, M, wot, w1):
    """WOTM-S-16 — `_` in the search matches only itself.
    Rules: search_work_order_types R6a (HR-8)."""
    a = wot("Pre_Check")
    wot("PreXCheck")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="e_c")
    # Then 1
    assert ids(result) == [a.id]


def test_wotm_s_17__empty_search_no_filter(db, M, wot, w1):
    """WOTM-S-17 — an empty search is no filter.
    Rules: search_work_order_types R7."""
    a = wot("Repair")
    b = wot("Inspection")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="")
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_wotm_s_18__empty_workspace(db, M, wot, w1, w2):
    """WOTM-S-18 — a workspace with no types gives an empty list.
    Rules: search_work_order_types R8."""
    wot("Repair", ws=w2)
    result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert result == []


def test_wotm_s_19__no_match(db, M, wot, w1):
    """WOTM-S-19 — a search with no match gives an empty list.
    Rules: search_work_order_types R8."""
    wot("Repair")
    result = M.search_work_order_types(db, workspace_id=w1.id, search="xyz")
    # Then 1
    assert result == []


# [claude] WOTM-S-20
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1710))
def test_wotm_s_20__sorted_by_name_then_id(db, M, wot, w1):
    """WOTM-S-20 — the list is sorted by name ignoring case, ties by id.
    Rules: search_work_order_types R3 [BUG-1710]."""
    s = wot("Service")
    r = wot("Repair")
    r2 = wot("repair", gone=True)
    r3 = wot("REPAIR", gone=True)
    a = wot("Assembly")
    result = M.search_work_order_types(db, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert ids(result) == [a.id, r.id, r2.id, r3.id, s.id]


# [claude] WOTM-S-21
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1710))
def test_wotm_s_21__sort_before_paging(db, M, wot, w1):
    """WOTM-S-21 — the sort is applied before paging.
    Rules: search_work_order_types R3 [BUG-1710]."""
    for n in ("Echo", "delta", "Charlie", "bravo", "Alpha"):
        wot(n)
    result = M.search_work_order_types(db, workspace_id=w1.id, skip=2, limit=2)
    # Then 1
    assert names(result) == ["Charlie", "delta"]


# [claude] WOTM-S-22
@pytest.mark.xfail(strict=True, reason=BUG_1710)
def test_wotm_s_22__query_orders_by_lower_name_then_id(db, M, wot, w1):
    """WOTM-S-22 — the list query orders by lower(name), then id.
    Rules: search_work_order_types R3 [BUG-1710]."""
    a = wot("Repair")
    b = wot("Inspection")
    with record_sql(db) as sql_log:
        result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert any(
        re.search(r"FROM work_order_types\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
    )


# [claude] WOTM-S-23
@pytest.mark.xfail(strict=True, reason=BUG_1709)
def test_wotm_s_23__query_filters_deleted_in_sql(db, M, wot, w1):
    """WOTM-S-23 — the list query filters soft-deleted rows in SQL.
    Rules: search_work_order_types R2, R4 [BUG-1709]."""
    a = wot("Repair")
    wot("Inspection", gone=True)
    with record_sql(db) as sql_log:
        result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert any(
        re.search(r"FROM work_order_types\b.*\bWHERE\b.*\bis_deleted\b", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
    )


def test_wotm_s_24__list_keeps_unflushed_edits(db, M, wot, w1, u2):
    """WOTM-S-24 — the list writes nothing and keeps the caller's unflushed edits.
    Rules: search_work_order_types Side effects."""
    a = wot("Repair")
    b = wot("Inspection")
    b.name = "Edited"
    p = WorkOrderType(workspace_id=w1.id, name="Pending", created_by=u2.id)
    db.add(p)
    result = M.search_work_order_types(db, workspace_id=w1.id)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert p in db.new
    # Then 5
    assert len(db.new) == 1
    # Then 6
    assert not db.deleted


# --------------------------------------------------------------------------- #
# delete_work_order_type
# --------------------------------------------------------------------------- #

def test_wotm_d_01__soft_delete_keeps_row(db, M, wot, w1, u1, u2):
    """WOTM-D-01 — a live type is soft-deleted and kept.
    Rules: delete_work_order_type R3, R4, Side effects."""
    a = wot("Repair", updated_by=u2)
    result = M.delete_work_order_type(db, type_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.is_deleted is True
    # Then 2
    row = reread(db, a.id)
    assert row.is_deleted is True
    assert row.deleted_at == NOW
    assert row.deleted_at.tzinfo is None
    assert row.deleted_by == u1.id
    # Then 3
    row = reread(db, a.id)
    assert row.name == "Repair"
    assert row.is_active is True
    assert row.updated_by == u2.id
    assert row.created_by == u2.id
    assert row.workspace_id == w1.id
    # Then 4
    assert count_ws(db, w1) == 1


def test_wotm_d_02__unknown_id_404(db, M, wot, w1, u1):
    """WOTM-D-02 — an unknown id gets 404.
    Rules: delete_work_order_type R1, Errors row 1."""
    a = wot("Repair")
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_work_order_type(db, type_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 999999999 not found"
    # Then 4
    assert snap(db, a.id) == before_a


def test_wotm_d_03__other_workspace_404(db, M, wot, w1, w2, u1):
    """WOTM-D-03 — another workspace's type gets 404 and is not deleted.
    Rules: delete_work_order_type R1, Errors row 1."""
    z = wot("Repair", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_work_order_type(db, type_id=z.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"
    # Then 4
    row = reread(db, z.id)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None


def test_wotm_d_04__already_deleted_400(db, M, wot, w1, u1, u2):
    """WOTM-D-04 — an already deleted type gets 400, its stamps stay.
    Rules: delete_work_order_type R2, Errors row 2."""
    d = wot("Repair", gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_work_order_type(db, type_id=d.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order type is already deleted"
    # Then 4
    row = reread(db, d.id)
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u2.id


# [claude] WOTM-D-05
def test_wotm_d_05__delete_flushed_not_committed(db, M, wot, w1, u1, monkeypatch):
    """WOTM-D-05 — delete flushes and never commits.
    Rules: delete_work_order_type Side effects (no commit)."""
    a = wot("Repair")
    a_id = a.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.delete_work_order_type(db, type_id=a_id, workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.is_deleted is True
    # Then 2
    assert reread(db, a_id).is_deleted is True
    sp.rollback()
    # Then 3
    row = reread(db, a_id)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    spy.assert_not_called()


# --------------------------------------------------------------------------- #
# _check_name_exists
# --------------------------------------------------------------------------- #

def test_wotm_n_01__empty_workspace_false(db, M, wot, w1, w2):
    """WOTM-N-01 — a workspace with no types has no name.
    Rules: _check_name_exists R7."""
    wot("Repair", ws=w2)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair")
    # Then 1
    assert result is False


def test_wotm_n_02__live_match_true(db, M, wot, w1):
    """WOTM-N-02 — a live type of the name is found.
    Rules: _check_name_exists R1, R6 (exclude_id=None)."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair", exclude_id=None)
    # Then 1
    assert result is True


def test_wotm_n_03__other_workspace_ignored(db, M, wot, w1, w2):
    """WOTM-N-03 — the name in another workspace is not considered.
    Rules: _check_name_exists R2."""
    wot("Inspection")
    wot("Repair", ws=w2)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair")
    # Then 1
    assert result is False


def test_wotm_n_04__deleted_ignored(db, M, wot, w1):
    """WOTM-N-04 — a soft-deleted type of the name is ignored.
    Rules: _check_name_exists R3."""
    wot("Repair", gone=True)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair")
    # Then 1
    assert result is False


def test_wotm_n_05__live_behind_deleted_other_case_true(db, M, wot, w1):
    """WOTM-N-05 — a live match is found behind a deleted row in other case.
    Rules: _check_name_exists R3, R1."""
    wot("repair", gone=True)
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1707)
def test_wotm_n_06__capitals_match(db, M, wot, w1):
    """WOTM-N-06 — the name matches in capitals.
    Rules: _check_name_exists R4 [BUG-1707]."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="REPAIR")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1707)
def test_wotm_n_07__leading_space_match(db, M, wot, w1):
    """WOTM-N-07 — the name matches with a leading space.
    Rules: _check_name_exists R4 [BUG-1707]."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name=" Repair")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1707)
def test_wotm_n_08__padded_stored_name_matches_other_case(db, M, wot, w1):
    """WOTM-N-08 — a stored name with outer spaces matches in other case.
    Rules: _check_name_exists R4 [BUG-1707]."""
    wot(" Repair ")
    result = M._check_name_exists(db, workspace_id=w1.id, name="repair")
    # Then 1
    assert result is True


def test_wotm_n_09__longer_name_no_match(db, M, wot, w1):
    """WOTM-N-09 — a longer name containing the stored one does not match.
    Rules: _check_name_exists R4."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair Urgent")
    # Then 1
    assert result is False


def test_wotm_n_10__part_no_match(db, M, wot, w1):
    """WOTM-N-10 — a part of the stored name does not match.
    Rules: _check_name_exists R4."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="epai")
    # Then 1
    assert result is False


def test_wotm_n_11__underscore_not_wildcard(db, M, wot, w1):
    """WOTM-N-11 — `_` in the name is not a wildcard.
    Rules: _check_name_exists R4."""
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Rep_ir")
    # Then 1
    assert result is False


def test_wotm_n_12__match_on_row_100(db, M, wot, wots_add_all, w1):
    """WOTM-N-12 — a match on the 100th row is found.
    Rules: _check_name_exists R5."""
    wots_add_all([f"Archived {k:02d}" for k in range(1, 31)], gone=True)
    wots_add_all([f"Team {k:02d}" for k in range(1, 70)])
    wot("Logistics")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Logistics")
    # Then 1
    assert result is True


# [claude] WOTM-N-13
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1706))
def test_wotm_n_13__match_beyond_row_100(db, M, wot, wots_add_all, w1):
    """WOTM-N-13 — a match beyond the 100th row is found.
    Rules: _check_name_exists R5 [BUG-1706]."""
    wots_add_all([f"Archived {k:02d}" for k in range(1, 31)], gone=True)
    wots_add_all([f"Team {k:02d}" for k in range(1, 71)])
    wot("Logistics")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Logistics")
    # Then 1
    assert result is True


def test_wotm_n_14__excluded_own_name_ignored(db, M, wot, w1):
    """WOTM-N-14 — the excluded type's own name is ignored.
    Rules: _check_name_exists R6."""
    a = wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair", exclude_id=a.id)
    # Then 1
    assert result is False


def test_wotm_n_15__exclude_higher_id_still_true(db, M, wot, w1):
    """WOTM-N-15 — excluding a type with a higher id still finds the match.
    Rules: _check_name_exists R6."""
    wot("Repair")
    b = wot("Inspection")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair", exclude_id=b.id)
    # Then 1
    assert result is True


def test_wotm_n_16__exclude_lower_id_still_true(db, M, wot, w1):
    """WOTM-N-16 — excluding a type with a lower id still finds the match.
    Rules: _check_name_exists R6."""
    b = wot("Inspection")
    wot("Repair")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Repair", exclude_id=b.id)
    # Then 1
    assert result is True


# [claude] WOTM-N-17
@pytest.mark.xfail(strict=True, reason=BUG_1706)
def test_wotm_n_17__no_capped_scan_of_workspace(db, M, wot, w1):
    """WOTM-N-17 — the name check sends no capped scan of the workspace.
    Rules: _check_name_exists R5 [BUG-1706]."""
    wot("Repair")
    with record_sql(db) as sql_log:
        result = M._check_name_exists(db, workspace_id=w1.id, name="Repair")
    # Then 1
    assert result is True
    # Then 2
    assert any(re.search(r"FROM work_order_types", s, re.IGNORECASE) for s in sql_log)
    # Then 3
    assert not any(
        re.search(r"LIMIT", s, re.IGNORECASE) and not re.search(r"WHERE.*name", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
        if re.search(r"FROM work_order_types", s, re.IGNORECASE)
    )
