"""Unit tests for app/managers/delivery_method_manager.py.

Implements tests/unit/managers/delivery_method_manager.cases.md (revision 2), one
test per case. Real Postgres session (`db` fixture). Only mock: the spec's
external `app.dao.delivery_method.utcnow` (every test), plus the listed race
simulations (`DeliveryMethodManager._check_name_exists` -> False).
"""
import re
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app.managers.delivery_method_manager import (
    DeliveryMethodManager,
    delivery_method_manager,
)
from app.models.delivery_method import DeliveryMethod
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate
from tests.unit.factories import make_profile, make_workspace

# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "MISSING", "T0", "NOW" (both naive)
MISSING = 999999999
T0 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 1, 15, 10, 30, 0)  # noqa: DTZ001

BUG_1219 = "BUG-1219: Delivery method name uniqueness not enforced by the database"
BUG_1523 = "BUG-1523: A deleted delivery method is returned by id"
BUG_1700 = "BUG-1700: Duplicate delivery method name check only scans the first 100 rows"
BUG_1701 = "BUG-1701: Delivery method name check is case- and whitespace-sensitive"
BUG_1702 = "BUG-1702: Blank delivery method names accepted, names stored untrimmed"
BUG_1703 = "BUG-1703: Delivery method list filters deleted rows and the search after paging"
BUG_1704 = "BUG-1704: Delivery method list has no sort order"
BUG_1705 = "BUG-1705: updated_by stamped on no-op delivery method updates"


def _row_order(bug):
    """Reason for a non-strict card: its failure today rests on physical row order."""
    return (
        f"{bug} (non-strict: today's outcome rests on physical row order, which the query does "
        "not fix, so another order can make it pass by accident)"
    )


# Convention "Externals": every test patches app.dao.delivery_method.utcnow -> NOW
@pytest.fixture(autouse=True)
def _utcnow():
    with patch("app.dao.delivery_method.utcnow", return_value=NOW) as m:
        yield m


# Convention "Race simulations": only DMM-C-12, C-13, U-21 use this
@pytest.fixture
def race():
    with patch.object(DeliveryMethodManager, "_check_name_exists", return_value=False) as m:
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


# Convention "M = the singleton delivery_method_manager"
@pytest.fixture
def M():
    return delivery_method_manager


# Convention "method" / "gone": inserted directly, one flush per row, so ids rise
# in Given order. Defaults: workspace W1, created_by U2, is_active True,
# is_deleted False, updated_by / deleted_at / deleted_by None.
@pytest.fixture
def method(db, w1, w2, u2):
    def _mk(name, *, ws=None, gone=False, updated_by=None):
        row = DeliveryMethod(
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
def methods_add_all(db, w1, u2):
    def _mk(names, *, gone=False):
        rows = [
            DeliveryMethod(
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
    return db.execute(select(DeliveryMethod).where(DeliveryMethod.id == row_id)).scalar_one()


# Convention "unchanged(X)": every column of X, read from the database
def snap(db, row_id):
    r = reread(db, row_id)
    return {c.key: getattr(r, c.key) for c in DeliveryMethod.__table__.columns}


# Convention "count:" rows of a workspace (optionally of one name), fresh query
def count_ws(db, ws, name=None):
    db.expire_all()
    q = select(func.count()).select_from(DeliveryMethod).where(DeliveryMethod.workspace_id == ws.id)
    if name is not None:
        q = q.where(DeliveryMethod.name == name)
    return db.scalar(q)


# Convention "nothing written": delivery_methods rows of all workspaces
def count_all(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(DeliveryMethod))


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
# create_delivery_method
# --------------------------------------------------------------------------- #

def test_dmm_c_01__new_method_stored(db, M, w1, u1):
    """DMM-C-01 — a new method is stored with its name, workspace and creator.
    Rules: create_delivery_method R1, R5, Side effects."""
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert isinstance(result, DeliveryMethod)
    assert result.id is not None
    # Then 2
    assert result.name == "Courier"
    new_id = result.id
    # Then 3
    row = reread(db, new_id)
    assert row.name == "Courier"
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


def test_dmm_c_02__live_duplicate_409(db, M, method, w1, u1):
    """DMM-C-02 — a live method of the same name is refused with 409.
    Rules: create_delivery_method R2, Errors row 1."""
    a = method("Courier")
    before_all = count_all(db)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert count_all(db) == before_all
    # Then 5
    assert snap(db, a.id) == before_a


def test_dmm_c_03__same_name_other_workspace_ok(db, M, method, w1, w2, u1):
    """DMM-C-03 — the same name in another workspace does not block.
    Rules: create_delivery_method R3, R1."""
    z = method("Courier", ws=w2)
    before_z = snap(db, z.id)
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id != z.id
    new_id = result.id
    # Then 2
    row = reread(db, new_id)
    assert row.name == "Courier"
    assert row.workspace_id == w1.id
    # Then 3
    assert count_ws(db, w1) == 1
    # Then 4
    assert snap(db, z.id) == before_z


def test_dmm_c_04__deleted_name_reusable(db, M, method, w1, u1, u2):
    """DMM-C-04 — a soft-deleted method's name can be used again.
    Rules: create_delivery_method R3, R6 (a deleted row does not count)."""
    d = method("Courier", gone=True)
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id != d.id
    new_id = result.id
    # Then 2
    row = reread(db, new_id)
    assert row.name == "Courier"
    assert row.is_deleted is False
    # Then 3
    row = reread(db, d.id)
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u2.id
    # Then 4
    assert count_ws(db, w1) == 2


@pytest.mark.xfail(strict=True, reason=BUG_1701)
def test_dmm_c_05__case_variant_409(db, M, method, w1, u1):
    """DMM-C-05 — a live name in other case is refused, the detail shows the submitted name.
    Rules: create_delivery_method R2, Errors row 1 [BUG-1701]."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'courier' already exists"
    # Then 4
    assert count_ws(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_c_06__padded_duplicate_409(db, M, method, w1, u1):
    """DMM-C-06 — a padded live name is trimmed by the schema and refused.
    Rules: create_delivery_method R2, R4 [BUG-1702]."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name=" Courier "), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert count_ws(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_c_07__empty_name_rejected_by_schema(db, w1):
    """DMM-C-07 — an empty name is refused by the schema.
    Rules: create_delivery_method R4, Errors row 2 [BUG-1702]."""
    # Then 1
    with pytest.raises(ValidationError):
        DeliveryMethodCreate(name="")
    # Then 2
    assert count_ws(db, w1) == 0


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_c_08__whitespace_name_rejected_by_schema(db, w1):
    """DMM-C-08 — a whitespace-only name is refused by the schema.
    Rules: create_delivery_method R4, Errors row 2 [BUG-1702]."""
    # Then 1
    with pytest.raises(ValidationError):
        DeliveryMethodCreate(name="   ")
    # Then 2
    assert count_ws(db, w1) == 0


def test_dmm_c_09__one_char_name_accepted(db, M, w1, u1):
    """DMM-C-09 — a one-character name is accepted.
    Rules: create_delivery_method R4."""
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="a"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "a"
    # Then 2
    assert reread(db, result.id).name == "a"


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_c_10__padded_name_stored_trimmed(db, M, w1, u1):
    """DMM-C-10 — outer spaces are trimmed before the name is stored.
    Rules: create_delivery_method R4 [BUG-1702]."""
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name=" Own Fleet "), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Own Fleet"
    # Then 2
    assert reread(db, result.id).name == "Own Fleet"


def test_dmm_c_11__case_and_inner_spaces_kept(db, M, w1, u1):
    """DMM-C-11 — case and inner spaces are stored as typed.
    Rules: create_delivery_method R4."""
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="own  FLEET"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "own  FLEET"
    # Then 2
    assert reread(db, result.id).name == "own  FLEET"


@pytest.mark.xfail(strict=True, reason=BUG_1219)
def test_dmm_c_12__race_duplicate_409(db, M, method, w1, u1, race):
    """DMM-C-12 — a duplicate past the Python check is refused by the database as 409.
    Rules: create_delivery_method R6, Errors row 1 [BUG-1219]."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert count_ws(db, w1, name="Courier") == 1


@pytest.mark.xfail(strict=True, reason=BUG_1219)
def test_dmm_c_13__race_case_variant_409(db, M, method, w1, u1, race):
    """DMM-C-13 — the database also refuses a case variant past the Python check.
    Rules: create_delivery_method R6, Errors row 1 [BUG-1219]."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="COURIER"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'COURIER' already exists"
    # Then 4
    assert count_ws(db, w1) == 1


# [claude] DMM-C-14
def test_dmm_c_14__create_flushed_not_committed(db, M, w1, u1, monkeypatch):
    """DMM-C-14 — create flushes and never commits.
    Rules: create_delivery_method Side effects (no commit)."""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_ws(db, w1) == 1
    sp.rollback()
    # Then 3
    assert count_ws(db, w1) == 0
    # Then 4
    spy.assert_not_called()


# --------------------------------------------------------------------------- #
# update_delivery_method
# --------------------------------------------------------------------------- #

def test_dmm_u_01__rename_happy_path(db, M, method, w1, u1, u2):
    """DMM-U-01 — a rename changes the name and stamps updated_by, nothing else.
    Rules: update_delivery_method R4, R9, R10, Side effects."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="Express Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Express Courier"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Express Courier"
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


def test_dmm_u_02__unknown_id_404(db, M, method, w1, u1):
    """DMM-U-02 — an unknown id gets 404.
    Rules: update_delivery_method R1, Errors row 1."""
    a = method("Courier")
    before_all = count_all(db)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=MISSING, delivery_method_data=DeliveryMethodUpdate(name="Pickup"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 999999999 not found"
    # Then 4
    assert count_all(db) == before_all
    # Then 5
    assert snap(db, a.id) == before_a


def test_dmm_u_03__other_workspace_404(db, M, method, w1, w2, u1):
    """DMM-U-03 — another workspace's method gets 404 and is not touched.
    Rules: update_delivery_method R2, Errors row 1."""
    z = method("Courier", ws=w2)
    before_z = snap(db, z.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=z.id, delivery_method_data=DeliveryMethodUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"
    # Then 4
    assert snap(db, z.id) == before_z


def test_dmm_u_04__deleted_400_before_name_check(db, M, method, w1, u1):
    """DMM-U-04 — a deleted method gets 400 before any name check.
    Rules: update_delivery_method R3, Errors row 2."""
    a = method("Pickup")
    d = method("Courier", gone=True)
    before_d = snap(db, d.id)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=d.id, delivery_method_data=DeliveryMethodUpdate(name="Pickup"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted delivery method"
    # Then 4
    assert snap(db, d.id) == before_d
    # Then 5
    assert snap(db, a.id) == before_a


def test_dmm_u_05__deleted_400_empty_body(db, M, method, w1, u1, u2):
    """DMM-U-05 — a deleted method gets 400 also with an empty body.
    Rules: update_delivery_method R3, Errors row 2."""
    d = method("Courier", gone=True, updated_by=u2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=d.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted delivery method"
    # Then 4
    row = reread(db, d.id)
    assert row.name == "Courier"
    assert row.updated_by == u2.id
    assert row.is_deleted is True


def test_dmm_u_06__rename_to_live_name_409(db, M, method, w1, u1, u2):
    """DMM-U-06 — a name another live method has is refused with 409.
    Rules: update_delivery_method R6, Errors row 3."""
    a = method("Courier")
    b = method("Pickup", updated_by=u2)
    before_b = snap(db, b.id)
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=b.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert snap(db, b.id) == before_b
    # Then 5
    assert snap(db, a.id) == before_a


def test_dmm_u_07__name_in_other_workspace_free(db, M, method, w1, w2, u1):
    """DMM-U-07 — a name used only in another workspace is free.
    Rules: update_delivery_method R6, R4."""
    z = method("Courier", ws=w2)
    b = method("Pickup")
    before_z = snap(db, z.id)
    result = M.update_delivery_method(db, delivery_method_id=b.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Courier"
    # Then 2
    row = reread(db, b.id)
    assert row.name == "Courier"
    assert row.updated_by == u1.id
    # Then 3
    assert snap(db, z.id) == before_z


def test_dmm_u_08__name_of_deleted_method_free(db, M, method, w1, u1):
    """DMM-U-08 — a name used only by a deleted method is free.
    Rules: update_delivery_method R6, R4."""
    d = method("Courier", gone=True)
    b = method("Pickup")
    before_d = snap(db, d.id)
    result = M.update_delivery_method(db, delivery_method_id=b.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Courier"
    # Then 2
    row = reread(db, b.id)
    assert row.name == "Courier"
    assert row.updated_by == u1.id
    # Then 3
    assert snap(db, d.id) == before_d


def test_dmm_u_09__own_name_case_change(db, M, method, w1, u1):
    """DMM-U-09 — a method may change the case of its own name.
    Rules: update_delivery_method R6 (this method excluded), R4."""
    a = method("Courier")
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "courier"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "courier"
    assert row.updated_by == u1.id


@pytest.mark.xfail(strict=True, reason=BUG_1701)
def test_dmm_u_10__rename_to_case_variant_409(db, M, method, w1, u1):
    """DMM-U-10 — another live method's name in other case is refused with 409.
    Rules: update_delivery_method R6, Errors row 3 [BUG-1701]."""
    a = method("Courier")
    method("Pickup")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="PICKUP"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'PICKUP' already exists"
    # Then 4
    assert reread(db, a.id).name == "Courier"


def test_dmm_u_11__empty_body_leaves_row(db, M, method, w1, u1, u2):
    """DMM-U-11 — an empty body leaves the name and other fields alone (updated_by not checked).
    Rules: update_delivery_method R7, R10."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Courier"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Courier"
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


def test_dmm_u_12__null_name_leaves_row(db, M, method, w1, u1, u2):
    """DMM-U-12 — an explicit null name leaves the name alone (updated_by not checked).
    Rules: update_delivery_method R7, R10."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name=None), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Courier"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Courier"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False


def test_dmm_u_13__current_name_not_duplicate(db, M, method, w1, u1, u2):
    """DMM-U-13 — the current name is not a duplicate of itself (updated_by not checked).
    Rules: update_delivery_method R5, R10."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    assert result.name == "Courier"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "Courier"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_deleted is False


@pytest.mark.xfail(strict=True, reason=BUG_1705)
def test_dmm_u_14__empty_body_keeps_updated_by(db, M, method, w1, u1, u2):
    """DMM-U-14 — an empty body does not stamp updated_by.
    Rules: update_delivery_method R9 [BUG-1705]."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1705)
def test_dmm_u_15__null_name_keeps_updated_by(db, M, method, w1, u1, u2):
    """DMM-U-15 — an explicit null name does not stamp updated_by.
    Rules: update_delivery_method R9 [BUG-1705]."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name=None), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1705)
def test_dmm_u_16__same_name_keeps_updated_by(db, M, method, w1, u1, u2):
    """DMM-U-16 — the unchanged name does not stamp updated_by.
    Rules: update_delivery_method R9 [BUG-1705]."""
    a = method("Courier", updated_by=u2)
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert reread(db, a.id).updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_u_17__padded_current_name_trimmed(db, M, method, w1, u1):
    """DMM-U-17 — the current name with outer spaces is trimmed and counts as unchanged.
    Rules: update_delivery_method R5, R8 [BUG-1702]."""
    a = method("Courier")
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name=" Courier "), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Courier"
    # Then 2
    assert reread(db, a.id).name == "Courier"


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_u_18__empty_name_rejected_by_update_schema(db, method):
    """DMM-U-18 — an empty name is refused by the update schema.
    Rules: update_delivery_method R8, Errors row 4 [BUG-1702]."""
    a = method("Courier")
    # Then 1
    with pytest.raises(ValidationError):
        DeliveryMethodUpdate(name="")
    # Then 2
    assert reread(db, a.id).name == "Courier"


@pytest.mark.xfail(strict=True, reason=BUG_1702)
def test_dmm_u_19__whitespace_name_rejected_by_update_schema(db, method):
    """DMM-U-19 — a whitespace-only name is refused by the update schema.
    Rules: update_delivery_method R8, Errors row 4 [BUG-1702]."""
    a = method("Courier")
    # Then 1
    with pytest.raises(ValidationError):
        DeliveryMethodUpdate(name="   ")
    # Then 2
    assert reread(db, a.id).name == "Courier"


def test_dmm_u_20__one_char_new_name(db, M, method, w1, u1):
    """DMM-U-20 — a one-character new name is accepted.
    Rules: update_delivery_method R8, R4."""
    a = method("Courier")
    result = M.update_delivery_method(db, delivery_method_id=a.id, delivery_method_data=DeliveryMethodUpdate(name="a"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "a"
    # Then 2
    row = reread(db, a.id)
    assert row.name == "a"
    assert row.updated_by == u1.id


@pytest.mark.xfail(strict=True, reason=BUG_1219)
def test_dmm_u_21__race_rename_409(db, M, method, w1, u1, u2, race):
    """DMM-U-21 — a rename onto a live duplicate past the Python check is refused by the database as 409.
    Rules: update_delivery_method R11, Errors row 3 [BUG-1219]."""
    method("Courier")
    b = method("Pickup", updated_by=u2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.update_delivery_method(db, delivery_method_id=b.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    row = reread(db, b.id)
    assert row.name == "Pickup"
    assert row.updated_by == u2.id


# [claude] DMM-U-22
def test_dmm_u_22__update_flushed_not_committed(db, M, method, w1, u1, u2, monkeypatch):
    """DMM-U-22 — update flushes and never commits.
    Rules: update_delivery_method Side effects (no commit)."""
    a = method("Courier", updated_by=u2)
    a_id = a.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.update_delivery_method(db, delivery_method_id=a_id, delivery_method_data=DeliveryMethodUpdate(name="Express"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert result.name == "Express"
    # Then 2
    assert reread(db, a_id).name == "Express"
    sp.rollback()
    # Then 3
    row = reread(db, a_id)
    assert row.name == "Courier"
    assert row.updated_by == u2.id
    # Then 4
    spy.assert_not_called()


# --------------------------------------------------------------------------- #
# get_delivery_method
# --------------------------------------------------------------------------- #

def test_dmm_g_01__live_method_by_id(db, M, method, w1):
    """DMM-G-01 — a live method is returned by its id.
    Rules: get_delivery_method R1."""
    method("Air")
    t = method("Courier")
    method("Pickup")
    result = M.get_delivery_method(db, delivery_method_id=t.id, workspace_id=w1.id)
    # Then 1
    assert isinstance(result, DeliveryMethod)
    # Then 2
    assert result.id == t.id
    assert result.name == "Courier"
    assert result.workspace_id == w1.id


def test_dmm_g_02__unknown_id_404(db, M, method, w1):
    """DMM-G-02 — an unknown id gets 404.
    Rules: get_delivery_method R2, Errors."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 999999999 not found"


def test_dmm_g_03__id_zero_404(db, M, method, w1):
    """DMM-G-03 — id 0 gets 404.
    Rules: get_delivery_method R2, Errors."""
    method("Courier")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 0 not found"


def test_dmm_g_04__higher_workspace_404(db, M, method, w1, w2):
    """DMM-G-04 — a method of a workspace with a higher id gets 404.
    Rules: get_delivery_method R2, Errors."""
    method("Courier")
    z = method("Pickup", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"


def test_dmm_g_05__lower_workspace_404(db, M, method, w2):
    """DMM-G-05 — a method of a workspace with a lower id gets 404.
    Rules: get_delivery_method R2, Errors."""
    a = method("Courier")
    method("Pickup", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {a.id} not found"


@pytest.mark.xfail(strict=True, reason=BUG_1523)
def test_dmm_g_06__deleted_hidden_by_default(db, M, method, w1):
    """DMM-G-06 — a soft-deleted method is hidden by default.
    Rules: get_delivery_method R3, Errors [BUG-1523]."""
    d = method("Courier", gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=d.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {d.id} not found"


@pytest.mark.xfail(strict=True, reason=BUG_1523)
def test_dmm_g_07__include_deleted_returns_deleted(db, M, method, w1):
    """DMM-G-07 — include_deleted=True returns a soft-deleted method.
    Rules: get_delivery_method R4 [BUG-1523]."""
    d = method("Courier", gone=True)
    result = M.get_delivery_method(db, delivery_method_id=d.id, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert result.id == d.id
    # Then 2
    assert result.is_deleted is True


@pytest.mark.xfail(strict=True, reason=BUG_1523)
def test_dmm_g_08__include_deleted_keeps_isolation(db, M, method, w1, w2):
    """DMM-G-08 — include_deleted=True does not reach another workspace.
    Rules: get_delivery_method R4, Errors [BUG-1523]."""
    z = method("Courier", ws=w2, gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_delivery_method(db, delivery_method_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"


def test_dmm_g_09__read_keeps_unflushed_edits(db, M, method, w1, u2):
    """DMM-G-09 — the read writes nothing and keeps the caller's unflushed edits.
    Rules: get_delivery_method Side effects."""
    a = method("Courier")
    b = method("Pickup")
    b.name = "Edited"
    p = DeliveryMethod(workspace_id=w1.id, name="Pending", created_by=u2.id)
    db.add(p)
    result = M.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id)
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
# search_delivery_methods
# --------------------------------------------------------------------------- #

FIVE = ("Alpha", "Bravo", "Charlie", "Delta", "Echo")


def test_dmm_s_01__own_workspace_other_higher(db, M, method, w1, w2):
    """DMM-S-01 — only the workspace's methods are listed (other workspace has the higher id).
    Rules: search_delivery_methods R1."""
    a = method("Courier")
    b = method("Pickup")
    method("Own Fleet", ws=w2)
    result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_dmm_s_02__own_workspace_other_lower(db, M, method, w2):
    """DMM-S-02 — only the workspace's methods are listed (other workspace has the lower id).
    Rules: search_delivery_methods R1."""
    method("Courier")
    z = method("Own Fleet", ws=w2)
    result = M.search_delivery_methods(db, workspace_id=w2.id)
    # Then 1
    assert ids(result) == [z.id]


def test_dmm_s_03__deleted_left_out(db, M, method, w1):
    """DMM-S-03 — soft-deleted methods are left out by default.
    Rules: search_delivery_methods R4."""
    a = method("Courier")
    method("Pickup", gone=True)
    result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]


def test_dmm_s_04__include_deleted_keeps_deleted(db, M, method, w1):
    """DMM-S-04 — include_deleted=True keeps soft-deleted methods.
    Rules: search_delivery_methods R5."""
    a = method("Courier")
    d = method("Pickup", gone=True)
    result = M.search_delivery_methods(db, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert sorted(ids(result)) == [a.id, d.id]


# [claude] DMM-S-05
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1703))
def test_dmm_s_05__deleted_take_no_place_in_page(db, M, method, w1):
    """DMM-S-05 — deleted methods take no place in the page (limit).
    Rules: search_delivery_methods R2, R4 [BUG-1703]."""
    method("Air 1", gone=True)
    method("Air 2", gone=True)
    method("Air 3", gone=True)
    a = method("Courier")
    b = method("Pickup")
    result = M.search_delivery_methods(db, workspace_id=w1.id, limit=2)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] DMM-S-06
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1703))
def test_dmm_s_06__deleted_not_counted_by_skip(db, M, method, w1):
    """DMM-S-06 — deleted methods are not counted by skip.
    Rules: search_delivery_methods R2, R4 [BUG-1703]."""
    method("Air 1", gone=True)
    method("Air 2", gone=True)
    method("Air 3", gone=True)
    a = method("Courier")
    b = method("Pickup")
    result = M.search_delivery_methods(db, workspace_id=w1.id, skip=1, limit=1000)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] DMM-S-07
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1703))
def test_dmm_s_07__search_past_first_page(db, M, method, w1):
    """DMM-S-07 — the search looks past the first page.
    Rules: search_delivery_methods R2, R6 [BUG-1703]."""
    method("Air 1")
    method("Bike")
    method("Car")
    x = method("Courier")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="our", limit=2)
    # Then 1
    assert ids(result) == [x.id]


def test_dmm_s_08__full_page(db, M, method, w1):
    """DMM-S-08 — a page is full when skip + limit equals the matches.
    Rules: search_delivery_methods R2."""
    for n in FIVE:
        method(n)
    result = M.search_delivery_methods(db, workspace_id=w1.id, skip=2, limit=3)
    # Then 1
    assert len(result) == 3


def test_dmm_s_09__short_page(db, M, method, w1):
    """DMM-S-09 — a page is short when skip + limit passes the matches.
    Rules: search_delivery_methods R2."""
    for n in FIVE:
        method(n)
    result = M.search_delivery_methods(db, workspace_id=w1.id, skip=3, limit=3)
    # Then 1
    assert len(result) == 2


def test_dmm_s_10__skip_at_matches_empty(db, M, method, w1):
    """DMM-S-10 — skip at the number of matches gives an empty list.
    Rules: search_delivery_methods R8."""
    for n in FIVE:
        method(n)
    result = M.search_delivery_methods(db, workspace_id=w1.id, skip=5)
    # Then 1
    assert result == []


def test_dmm_s_11__default_limit_100(db, M, methods_add_all, w1):
    """DMM-S-11 — the default limit is 100.
    Rules: search_delivery_methods R2 (default limit)."""
    methods_add_all([f"Method {k:03d}" for k in range(1, 102)])
    result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert len(result) == 100


def test_dmm_s_12__limit_1000_past_100(db, M, methods_add_all, w1):
    """DMM-S-12 — limit=1000 lists past 100.
    Rules: search_delivery_methods R2."""
    methods_add_all([f"Method {k:03d}" for k in range(1, 102)])
    result = M.search_delivery_methods(db, workspace_id=w1.id, limit=1000)
    # Then 1
    assert len(result) == 101


def test_dmm_s_13__substring_ignoring_case(db, M, method, w1):
    """DMM-S-13 — search matches a part of the name, ignoring case on both sides.
    Rules: search_delivery_methods R6."""
    a = method("Courier")
    b = method("SKYCOURIER")
    method("Pickup")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="Our")
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_dmm_s_14__leading_space_counts(db, M, method, w1):
    """DMM-S-14 — a leading space in the search counts.
    Rules: search_delivery_methods R6."""
    a = method("Courier Express")
    method("Expedite")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search=" exp")
    # Then 1
    assert ids(result) == [a.id]


def test_dmm_s_15__percent_literal(db, M, method, w1):
    """DMM-S-15 — `%` in the search matches only itself.
    Rules: search_delivery_methods R6a (HR-8)."""
    a = method("Fast 100%")
    method("Pickup")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="%")
    # Then 1
    assert ids(result) == [a.id]


def test_dmm_s_16__underscore_literal(db, M, method, w1):
    """DMM-S-16 — `_` in the search matches only itself.
    Rules: search_delivery_methods R6a (HR-8)."""
    a = method("Own_Fleet")
    method("OwnXFleet")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="n_f")
    # Then 1
    assert ids(result) == [a.id]


def test_dmm_s_17__empty_search_no_filter(db, M, method, w1):
    """DMM-S-17 — an empty search is no filter.
    Rules: search_delivery_methods R7."""
    a = method("Courier")
    b = method("Pickup")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="")
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


def test_dmm_s_18__empty_workspace(db, M, method, w1, w2):
    """DMM-S-18 — a workspace with no methods gives an empty list.
    Rules: search_delivery_methods R8."""
    method("Courier", ws=w2)
    result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert result == []


def test_dmm_s_19__no_match(db, M, method, w1):
    """DMM-S-19 — a search with no match gives an empty list.
    Rules: search_delivery_methods R8."""
    method("Courier")
    result = M.search_delivery_methods(db, workspace_id=w1.id, search="xyz")
    # Then 1
    assert result == []


# [claude] DMM-S-20
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1704))
def test_dmm_s_20__sorted_by_name_then_id(db, M, method, w1):
    """DMM-S-20 — the list is sorted by name ignoring case, ties by id.
    Rules: search_delivery_methods R3 [BUG-1704]."""
    p = method("Pickup")
    c = method("Courier")
    c2 = method("courier", gone=True)
    c3 = method("COURIER", gone=True)
    f = method("Air Freight")
    result = M.search_delivery_methods(db, workspace_id=w1.id, include_deleted=True)
    # Then 1
    assert ids(result) == [f.id, c.id, c2.id, c3.id, p.id]


# [claude] DMM-S-21
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1704))
def test_dmm_s_21__sort_before_paging(db, M, method, w1):
    """DMM-S-21 — the sort is applied before paging.
    Rules: search_delivery_methods R3 [BUG-1704]."""
    for n in ("Echo", "delta", "Charlie", "bravo", "Alpha"):
        method(n)
    result = M.search_delivery_methods(db, workspace_id=w1.id, skip=2, limit=2)
    # Then 1
    assert names(result) == ["Charlie", "delta"]


# [claude] DMM-S-22
@pytest.mark.xfail(strict=True, reason=BUG_1704)
def test_dmm_s_22__query_orders_by_lower_name_then_id(db, M, method, w1):
    """DMM-S-22 — the list query orders by lower(name), then id.
    Rules: search_delivery_methods R3 [BUG-1704]."""
    a = method("Courier")
    b = method("Pickup")
    with record_sql(db) as sql_log:
        result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert any(
        re.search(r"FROM delivery_methods\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
    )


# [claude] DMM-S-23
@pytest.mark.xfail(strict=True, reason=BUG_1703)
def test_dmm_s_23__query_filters_deleted_in_sql(db, M, method, w1):
    """DMM-S-23 — the list query filters soft-deleted rows in SQL.
    Rules: search_delivery_methods R2, R4 [BUG-1703]."""
    a = method("Courier")
    method("Pickup", gone=True)
    with record_sql(db) as sql_log:
        result = M.search_delivery_methods(db, workspace_id=w1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert any(
        re.search(r"FROM delivery_methods\b.*\bWHERE\b.*\bis_deleted\b", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
    )


def test_dmm_s_24__list_keeps_unflushed_edits(db, M, method, w1, u2):
    """DMM-S-24 — the list writes nothing and keeps the caller's unflushed edits.
    Rules: search_delivery_methods Side effects."""
    a = method("Courier")
    b = method("Pickup")
    b.name = "Edited"
    p = DeliveryMethod(workspace_id=w1.id, name="Pending", created_by=u2.id)
    db.add(p)
    result = M.search_delivery_methods(db, workspace_id=w1.id)
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
# delete_delivery_method
# --------------------------------------------------------------------------- #

def test_dmm_d_01__soft_delete_keeps_row(db, M, method, w1, u1, u2):
    """DMM-D-01 — a live method is soft-deleted and kept.
    Rules: delete_delivery_method R3, R4, Side effects."""
    a = method("Courier", updated_by=u2)
    result = M.delete_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id, user_id=u1.id)
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
    assert row.name == "Courier"
    assert row.is_active is True
    assert row.updated_by == u2.id
    assert row.created_by == u2.id
    assert row.workspace_id == w1.id
    # Then 4
    assert count_ws(db, w1) == 1


def test_dmm_d_02__unknown_id_404(db, M, method, w1, u1):
    """DMM-D-02 — an unknown id gets 404.
    Rules: delete_delivery_method R1, Errors row 1."""
    a = method("Courier")
    before_a = snap(db, a.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_delivery_method(db, delivery_method_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 999999999 not found"
    # Then 4
    assert snap(db, a.id) == before_a


def test_dmm_d_03__other_workspace_404(db, M, method, w1, w2, u1):
    """DMM-D-03 — another workspace's method gets 404 and is not deleted.
    Rules: delete_delivery_method R1, Errors row 1."""
    z = method("Courier", ws=w2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_delivery_method(db, delivery_method_id=z.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"
    # Then 4
    row = reread(db, z.id)
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None


def test_dmm_d_04__already_deleted_400(db, M, method, w1, u1, u2):
    """DMM-D-04 — an already deleted method gets 400, its stamps stay.
    Rules: delete_delivery_method R2, Errors row 2."""
    d = method("Courier", gone=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_delivery_method(db, delivery_method_id=d.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Delivery method is already deleted"
    # Then 4
    row = reread(db, d.id)
    assert row.is_deleted is True
    assert row.deleted_at == T0
    assert row.deleted_by == u2.id


# [claude] DMM-D-05
def test_dmm_d_05__delete_flushed_not_committed(db, M, method, w1, u1, monkeypatch):
    """DMM-D-05 — delete flushes and never commits.
    Rules: delete_delivery_method Side effects (no commit)."""
    a = method("Courier")
    a_id = a.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    result = M.delete_delivery_method(db, delivery_method_id=a_id, workspace_id=w1.id, user_id=u1.id)
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

def test_dmm_n_01__empty_workspace_false(db, M, method, w1, w2):
    """DMM-N-01 — a workspace with no methods has no name.
    Rules: _check_name_exists R7."""
    method("Courier", ws=w2)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier")
    # Then 1
    assert result is False


def test_dmm_n_02__live_match_true(db, M, method, w1):
    """DMM-N-02 — a live method of the name is found.
    Rules: _check_name_exists R1, R6 (exclude_id=None)."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier", exclude_id=None)
    # Then 1
    assert result is True


def test_dmm_n_03__other_workspace_ignored(db, M, method, w1, w2):
    """DMM-N-03 — the name in another workspace is not considered.
    Rules: _check_name_exists R2."""
    method("Pickup")
    method("Courier", ws=w2)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier")
    # Then 1
    assert result is False


def test_dmm_n_04__deleted_ignored(db, M, method, w1):
    """DMM-N-04 — a soft-deleted method of the name is ignored.
    Rules: _check_name_exists R3."""
    method("Courier", gone=True)
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier")
    # Then 1
    assert result is False


def test_dmm_n_05__live_behind_deleted_true(db, M, method, w1):
    """DMM-N-05 — a live match is found behind a deleted one.
    Rules: _check_name_exists R3, R1."""
    method("Courier", gone=True)
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1701)
def test_dmm_n_06__capitals_match(db, M, method, w1):
    """DMM-N-06 — the name matches in capitals.
    Rules: _check_name_exists R4 [BUG-1701]."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="COURIER")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1701)
def test_dmm_n_07__leading_space_match(db, M, method, w1):
    """DMM-N-07 — the name matches with a leading space.
    Rules: _check_name_exists R4 [BUG-1701]."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name=" Courier")
    # Then 1
    assert result is True


@pytest.mark.xfail(strict=True, reason=BUG_1701)
def test_dmm_n_08__padded_stored_name_matches_other_case(db, M, method, w1):
    """DMM-N-08 — a stored name with outer spaces matches in other case.
    Rules: _check_name_exists R4 [BUG-1701]."""
    method(" Courier ")
    result = M._check_name_exists(db, workspace_id=w1.id, name="courier")
    # Then 1
    assert result is True


def test_dmm_n_09__longer_name_no_match(db, M, method, w1):
    """DMM-N-09 — a longer name containing the stored one does not match.
    Rules: _check_name_exists R4."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier Express")
    # Then 1
    assert result is False


def test_dmm_n_10__part_no_match(db, M, method, w1):
    """DMM-N-10 — a part of the stored name does not match.
    Rules: _check_name_exists R4."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="ourie")
    # Then 1
    assert result is False


def test_dmm_n_11__underscore_not_wildcard(db, M, method, w1):
    """DMM-N-11 — `_` in the name is not a wildcard.
    Rules: _check_name_exists R4."""
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Cour_er")
    # Then 1
    assert result is False


def test_dmm_n_12__match_on_row_100(db, M, method, methods_add_all, w1):
    """DMM-N-12 — a match on the 100th row is found.
    Rules: _check_name_exists R5."""
    methods_add_all([f"Archived {k:02d}" for k in range(1, 31)], gone=True)
    methods_add_all([f"Team {k:02d}" for k in range(1, 70)])
    method("Logistics")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Logistics")
    # Then 1
    assert result is True


# [claude] DMM-N-13
@pytest.mark.xfail(strict=False, reason=_row_order(BUG_1700))
def test_dmm_n_13__match_beyond_row_100(db, M, method, methods_add_all, w1):
    """DMM-N-13 — a match beyond the 100th row is found.
    Rules: _check_name_exists R5 [BUG-1700]."""
    methods_add_all([f"Archived {k:02d}" for k in range(1, 31)], gone=True)
    methods_add_all([f"Team {k:02d}" for k in range(1, 71)])
    method("Logistics")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Logistics")
    # Then 1
    assert result is True


def test_dmm_n_14__excluded_own_name_ignored(db, M, method, w1):
    """DMM-N-14 — the excluded method's own name is ignored.
    Rules: _check_name_exists R6."""
    a = method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier", exclude_id=a.id)
    # Then 1
    assert result is False


def test_dmm_n_15__exclude_higher_id_still_true(db, M, method, w1):
    """DMM-N-15 — excluding a method with a higher id still finds the match.
    Rules: _check_name_exists R6."""
    method("Courier")
    b = method("Pickup")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier", exclude_id=b.id)
    # Then 1
    assert result is True


def test_dmm_n_16__exclude_lower_id_still_true(db, M, method, w1):
    """DMM-N-16 — excluding a method with a lower id still finds the match.
    Rules: _check_name_exists R6."""
    b = method("Pickup")
    method("Courier")
    result = M._check_name_exists(db, workspace_id=w1.id, name="Courier", exclude_id=b.id)
    # Then 1
    assert result is True


# [claude] DMM-N-17
@pytest.mark.xfail(strict=True, reason=BUG_1700)
def test_dmm_n_17__no_capped_scan_of_workspace(db, M, method, w1):
    """DMM-N-17 — the name check sends no capped scan of the workspace.
    Rules: _check_name_exists R5 [BUG-1700]."""
    method("Courier")
    with record_sql(db) as sql_log:
        result = M._check_name_exists(db, workspace_id=w1.id, name="Courier")
    # Then 1
    assert result is True
    # Then 2
    assert any(re.search(r"FROM delivery_methods", s, re.IGNORECASE) for s in sql_log)
    # Then 3
    assert not any(
        re.search(r"LIMIT", s, re.IGNORECASE) and not re.search(r"WHERE.*name", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
        if re.search(r"FROM delivery_methods", s, re.IGNORECASE)
    )
