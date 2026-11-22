"""Unit tests for app/managers/department_manager.py.

Implements tests/unit/managers/department_manager.cases.md (revision 5), one
test per case. Real Postgres session (`db` fixture). Only mock: the spec's
external `app.dao.department.utcnow` (every test), plus the listed race
simulations (`DepartmentManager._check_name_exists` -> False).
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

from app.managers.department_manager import DepartmentManager
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from tests.unit.factories import make_profile, make_workspace

# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "T0" and "NOW" (both naive)
T0 = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001
NOW = datetime(2026, 1, 15, 10, 30, 0)  # noqa: DTZ001

BUG_001 = "BUG-001: Duplicate-name check only scans the first 100 departments"
BUG_002 = "BUG-002: Duplicate-name check is case- and whitespace-sensitive"
BUG_003 = "BUG-003: Department name uniqueness not enforced by the database"
BUG_004 = "BUG-004: Blank / whitespace-only department names accepted"
BUG_005 = "BUG-005: get_department returns soft-deleted departments"
BUG_006 = "BUG-006: Department list drops deleted rows after paging"
BUG_007 = "BUG-007: Department name search only searches the current page"
BUG_008 = "BUG-008: Department list has no sort order"
BUG_008_ORDER = (
    f"{BUG_008} (non-strict: compares an order the query does not fix, so physical row order "
    "can make it pass by accident; DEPT-S-26 is the strict alarm)"
)
BUG_009 = "BUG-009: updated_by stamped on no-op updates"


def _row_order(bug):
    """Reason for a non-strict card whose failure today needs its row to fall outside the fetched page."""
    return (
        f"{bug} (non-strict: today it fails only while physical row order keeps the target row outside "
        "the fetched page, and the query fixes no order, so another order can make it pass by accident)"
    )

SNAP_COLS = (
    "name", "workspace_id", "created_by", "updated_by",
    "is_deleted", "is_active", "deleted_at", "deleted_by",
)


# Convention "Externals": every test patches app.dao.department.utcnow -> NOW
@pytest.fixture(autouse=True)
def _utcnow():
    with patch("app.dao.department.utcnow", return_value=NOW) as m:
        yield m


# Convention "Race simulations": only DEPT-C-17, C-19, U-22, U-23 use this
@pytest.fixture
def race():
    with patch.object(DepartmentManager, "_check_name_exists", return_value=False) as m:
        yield m


# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1, U2, U3 = three profiles rows" (global; no membership rows)
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


@pytest.fixture
def u3(db):
    return make_profile(db)


# Convention "M = a DepartmentManager() instance"
@pytest.fixture
def M():
    return DepartmentManager()


# Convention "live X" / "deleted X": inserted directly, one flush per row, so
# ids increase in insertion order. created_by = U2 (U3 for W2 rows);
# deleted rows: deleted_at = T0, deleted_by = U2.
@pytest.fixture
def dept(db, w1, w2, u2, u3):
    def _mk(ws, name, *, deleted=False, updated_by=None):
        row = Department(
            workspace_id=ws.id,
            name=name,
            is_active=True,
            is_deleted=deleted,
            created_by=u3.id if ws is w2 else u2.id,
            updated_by=None if updated_by is None else updated_by.id,
            deleted_at=T0 if deleted else None,
            deleted_by=u2.id if deleted else None,
        )
        db.add(row)
        db.flush()
        return row

    return _mk


# Convention "MISSING = highest existing id + 1000"
def missing_id(db):
    return (db.scalar(select(func.max(Department.id))) or 0) + 1000


# Convention "re-read": expire the session and SELECT the row by id again
def reread(db, dept_id):
    db.expire_all()
    return db.execute(select(Department).where(Department.id == dept_id)).scalar_one()


# Convention "W1 count": all rows of the workspace, deleted included, fresh query
def w_count(db, ws):
    db.expire_all()
    return db.scalar(
        select(func.count()).select_from(Department).where(Department.workspace_id == ws.id)
    )


def ws_rows(db, ws):
    db.expire_all()
    return db.execute(
        select(Department).where(Department.workspace_id == ws.id).order_by(Department.id)
    ).scalars().all()


# Convention "unchanged": every Given column has the same value on re-read
def snap(db, dept_id):
    r = reread(db, dept_id)
    return {c: getattr(r, c) for c in SNAP_COLS}


def names(rows):
    return {r.name for r in rows}


def in_order(rows):
    return [r.name for r in rows]


def not_found(dept_id):
    return f"Department with ID {dept_id} not found"


def exists_msg(name):
    return f"Department with name '{name}' already exists"


# --------------------------------------------------------------------------- #
# create_department
# --------------------------------------------------------------------------- #

def test_dept_c_01__create_happy_path(db, M, w1, u1):
    """DEPT-C-01 — creating a new name stores it with audit fields and defaults.
    Rules: create_department R1, R5."""
    dep = M.create_department(db, DepartmentCreate(name="Sales"), w1.id, u1.id)
    assert isinstance(dep, Department)
    assert dep.id is not None
    assert dep.name == "Sales"
    r = reread(db, dep.id)
    assert r.name == "Sales"
    assert r.workspace_id == w1.id
    assert r.created_by == u1.id
    assert r.is_deleted is False
    assert r.is_active is True
    assert r.updated_by is None
    assert r.deleted_at is None
    assert r.deleted_by is None
    assert w_count(db, w1) == 1


def test_dept_c_02__duplicate_name_rejected(db, M, dept, w1, u1, u2):
    """DEPT-C-02 — creating an existing live name raises 409 and creates nothing.
    Rules: create_department R2; Errors row 1."""
    sales = dept(w1, "Sales")
    before = snap(db, sales.id)
    with pytest.raises(HTTPException) as exc:
        M.create_department(db, DepartmentCreate(name="Sales"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Sales")
    assert w_count(db, w1) == 1
    assert snap(db, sales.id) == before
    assert reread(db, sales.id).created_by == u2.id


def test_dept_c_03__same_name_other_workspace_allowed(db, M, dept, w1, w2, u1):
    """DEPT-C-03 — a name used in another workspace does not block creation.
    Rules: create_department R3."""
    w2_sales = dept(w2, "Sales")
    before = snap(db, w2_sales.id)
    dep = M.create_department(db, DepartmentCreate(name="Sales"), w1.id, u1.id)
    assert isinstance(dep, Department)
    r = reread(db, dep.id)
    assert r.name == "Sales"
    assert r.workspace_id == w1.id
    assert w_count(db, w1) == 1
    assert snap(db, w2_sales.id) == before


def test_dept_c_04__deleted_name_does_not_block(db, M, dept, w1, u1, u2):
    """DEPT-C-04 — a soft-deleted department's name can be reused; old row untouched.
    Rules: create_department R3."""
    old = dept(w1, "Sales", deleted=True)
    dep = M.create_department(db, DepartmentCreate(name="Sales"), w1.id, u1.id)
    assert isinstance(dep, Department)
    assert dep.id != old.id
    new = reread(db, dep.id)
    assert new.name == "Sales"
    assert new.is_deleted is False
    o = reread(db, old.id)
    assert o.is_deleted is True
    assert o.deleted_at == T0
    assert o.deleted_by == u2.id
    assert w_count(db, w1) == 2


@pytest.mark.xfail(strict=True, reason=BUG_002)
def test_dept_c_05__case_only_duplicate_rejected(db, M, dept, w1, u1):
    """DEPT-C-05 — a name differing only in case is a duplicate (409, submitted name).
    Rules: create_department R2; Errors row 1 [BUG-002]."""
    dept(w1, "Sales")
    with pytest.raises(HTTPException) as exc:
        M.create_department(db, DepartmentCreate(name="sales"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("sales")
    assert w_count(db, w1) == 1


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_001))
def test_dept_c_06__duplicate_beyond_first_100_rows_rejected(db, M, dept, w1, u1):
    """DEPT-C-06 — a live duplicate at row 110 of 120 is still detected.
    Rules: create_department R2 [BUG-001]."""
    for i in range(1, 31):
        dept(w1, f"Archived {i:02d}", deleted=True)
    for i in range(1, 80):
        dept(w1, f"Team {i:02d}")
    dept(w1, "Logistics")  # 110th row
    for i in range(1, 11):
        dept(w1, f"Unit {i:02d}")
    with pytest.raises(HTTPException) as exc:
        M.create_department(db, DepartmentCreate(name="Logistics"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Logistics")
    assert w_count(db, w1) == 120
    live_logistics = [r for r in ws_rows(db, w1) if r.name == "Logistics" and not r.is_deleted]
    assert len(live_logistics) == 1


@pytest.mark.xfail(strict=True, reason=BUG_004)
@pytest.mark.parametrize("blank", [
    pytest.param("", id="DEPT-C-07"),
    pytest.param("   ", id="DEPT-C-08"),
])
def test_dept_c_07_08__blank_name_rejected_by_schema(db, w1, blank):
    """DEPT-C-07 / DEPT-C-08 — DepartmentCreate rejects an empty / whitespace-only name.
    Rules: create_department R4; Errors row 2 [BUG-004]."""
    with pytest.raises(ValidationError):
        DepartmentCreate(name=blank)
    assert w_count(db, w1) == 0


def test_dept_c_09__one_char_name_accepted(db, M, w1, u1):
    """DEPT-C-09 — a one-character name builds and is stored.
    Rules: create_department R4."""
    data = DepartmentCreate(name="a")
    assert data.name == "a"
    dep = M.create_department(db, data, w1.id, u1.id)
    assert reread(db, dep.id).name == "a"


@pytest.mark.xfail(strict=True, reason=BUG_004)
def test_dept_c_10__padded_name_stored_trimmed(db, M, w1, u1):
    """DEPT-C-10 — leading/trailing whitespace is stripped by the schema and stored trimmed.
    Rules: create_department R4 [BUG-004]."""
    data = DepartmentCreate(name=" Sales ")
    assert data.name == "Sales"
    dep = M.create_department(db, data, w1.id, u1.id)
    assert reread(db, dep.id).name == "Sales"


@pytest.mark.xfail(strict=True, reason=BUG_004)
def test_dept_c_11__inner_whitespace_kept(db, M, w1, u1):
    """DEPT-C-11 — trimming keeps inner whitespace.
    Rules: create_department R4 [BUG-004]."""
    data = DepartmentCreate(name="  Sales  Team ")
    assert data.name == "Sales  Team"
    dep = M.create_department(db, data, w1.id, u1.id)
    assert reread(db, dep.id).name == "Sales  Team"


def test_dept_c_12__case_kept_as_typed(db, M, w1, u1):
    """DEPT-C-12 — the name is stored without case change.
    Rules: create_department R4."""
    dep = M.create_department(db, DepartmentCreate(name="sALES dept"), w1.id, u1.id)
    assert reread(db, dep.id).name == "sALES dept"


@pytest.mark.xfail(strict=True, reason=BUG_004)
def test_dept_c_13__padded_duplicate_rejected(db, M, dept, w1, u1):
    """DEPT-C-13 — " Sales " is trimmed and then detected as a duplicate of "Sales".
    Rules: create_department R2, R4 [BUG-004]."""
    dept(w1, "Sales")
    data = DepartmentCreate(name=" Sales ")
    with pytest.raises(HTTPException) as exc:
        M.create_department(db, data, w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Sales")
    assert w_count(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_c_14__db_rejects_second_live_same_name(db, dept, w1, u2):
    """DEPT-C-14 — the database rejects a second live "Finance" in the same workspace.
    Rules: create_department R6 [BUG-003]."""
    dept(w1, "Finance")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Department(workspace_id=w1.id, name="Finance", created_by=u2.id))
            db.flush()
    rows = [r for r in ws_rows(db, w1) if r.name == "Finance"]
    assert len(rows) == 1


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_c_15__db_rejects_case_variant(db, dept, w1, u2):
    """DEPT-C-15 — the database constraint is on the normalised name ("FINANCE" vs "Finance").
    Rules: create_department R6 [BUG-003]."""
    dept(w1, "Finance")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Department(workspace_id=w1.id, name="FINANCE", created_by=u2.id))
            db.flush()
    assert w_count(db, w1) == 1


def test_dept_c_16__db_allows_live_next_to_deleted_and_other_ws(db, dept, w1, w2, u2):
    """DEPT-C-16 — a deleted same-name row and another workspace's row do not block an insert.
    Rules: create_department R6."""
    dept(w1, "Finance", deleted=True)
    w2_fin = dept(w2, "Finance")
    db.add(Department(workspace_id=w1.id, name="Finance", created_by=u2.id))
    db.flush()
    assert w_count(db, w1) == 2
    assert sorted((r.name, r.is_deleted) for r in ws_rows(db, w1)) == [
        ("Finance", False), ("Finance", True),
    ]
    r = reread(db, w2_fin.id)
    assert r.name == "Finance"
    assert r.workspace_id == w2.id
    assert r.is_deleted is False


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_c_17__race_duplicate_maps_to_409(db, M, dept, w1, u1, race):
    """DEPT-C-17 — a duplicate reaching the insert (race) raises 409, not IntegrityError.
    Rules: create_department R6; Errors row 1 [BUG-003]."""
    dept(w1, "Finance")
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_department(db, DepartmentCreate(name="Finance"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Finance")
    assert len([r for r in ws_rows(db, w1) if r.name == "Finance"]) == 1
    assert w_count(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=f"{BUG_002}; {BUG_004}")
def test_dept_c_18__padded_case_variant_rejected(db, M, dept, w1, u1):
    """DEPT-C-18 — " sales " is trimmed to "sales" and rejected as duplicate of "Sales".
    Rules: create_department R2, R4; Errors row 1 [BUG-002] [BUG-004]."""
    dept(w1, "Sales")
    data = DepartmentCreate(name=" sales ")
    assert data.name == "sales"
    with pytest.raises(HTTPException) as exc:
        M.create_department(db, data, w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("sales")
    assert w_count(db, w1) == 1


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_c_19__race_case_variant_maps_to_409(db, M, dept, w1, u1, race):
    """DEPT-C-19 — a case-variant duplicate reaching the insert raises 409 with the submitted name.
    Rules: create_department R6; Errors row 1 [BUG-003]."""
    dept(w1, "Finance")
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.create_department(db, DepartmentCreate(name="FINANCE"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("FINANCE")
    assert w_count(db, w1) == 1
    assert [r.name for r in ws_rows(db, w1)] == ["Finance"]


def test_dept_c_20__inner_whitespace_kept_unpadded(db, M, w1, u1):
    """DEPT-C-20 — a name with inner double space (no padding) builds and is stored as typed.
    Rules: create_department R4."""
    data = DepartmentCreate(name="Sales  Team")
    assert data.name == "Sales  Team"
    dep = M.create_department(db, data, w1.id, u1.id)
    assert reread(db, dep.id).name == "Sales  Team"


# --------------------------------------------------------------------------- #
# update_department
# --------------------------------------------------------------------------- #

def test_dept_u_01__rename_happy_path(db, M, dept, w1, u1, u2):
    """DEPT-U-01 — renaming sets the name and updated_by, nothing else.
    Rules: update_department R4, R9, R10."""
    ops = dept(w1, "Ops", updated_by=u2)
    res = M.update_department(db, ops.id, DepartmentUpdate(name="Operations"), w1.id, u1.id)
    assert isinstance(res, Department)
    assert res.id == ops.id
    assert res.name == "Operations"
    r = reread(db, ops.id)
    assert r.name == "Operations"
    assert r.updated_by == u1.id
    assert r.workspace_id == w1.id
    assert r.created_by == u2.id
    assert r.is_deleted is False
    assert r.is_active is True
    assert r.deleted_at is None
    assert r.deleted_by is None


def test_dept_u_02__missing_id_404(db, M, dept, w1, u1, u2):
    """DEPT-U-02 — updating an unknown id raises 404 and changes nothing.
    Rules: update_department R1; Errors row 1."""
    ops = dept(w1, "Ops", updated_by=u2)
    before = snap(db, ops.id)
    missing = missing_id(db)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, missing, DepartmentUpdate(name="X"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(missing)
    assert snap(db, ops.id) == before
    assert w_count(db, w1) == 1


def test_dept_u_03__other_workspace_404(db, M, dept, w1, w2, u1, u3):
    """DEPT-U-03 — a department of another workspace is reported as not found.
    Rules: update_department R2; Errors row 1."""
    ops = dept(w2, "Ops", updated_by=u3)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, ops.id, DepartmentUpdate(name="Hacked"), w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(ops.id)
    r = reread(db, ops.id)
    assert r.name == "Ops"
    assert r.updated_by == u3.id
    assert r.workspace_id == w2.id


def test_dept_u_04__deleted_department_400(db, M, dept, w1, u1, u2):
    """DEPT-U-04 — updating a soft-deleted department raises 400 and changes nothing.
    Rules: update_department R3; Errors row 2."""
    leg = dept(w1, "Legacy", deleted=True, updated_by=u2)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, leg.id, DepartmentUpdate(name="Revived"), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot update deleted department"
    r = reread(db, leg.id)
    assert r.name == "Legacy"
    assert r.updated_by == u2.id
    assert r.is_deleted is True
    assert r.deleted_at == T0
    assert r.deleted_by == u2.id


def test_dept_u_05__deleted_check_before_duplicate_check(db, M, dept, w1, u1, u2):
    """DEPT-U-05 — a deleted department renamed to a taken name gets 400, not 409.
    Rules: update_department R3."""
    leg = dept(w1, "Legacy", deleted=True, updated_by=u2)
    sales = dept(w1, "Sales")
    leg_before, sales_before = snap(db, leg.id), snap(db, sales.id)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, leg.id, DepartmentUpdate(name="Sales"), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot update deleted department"
    assert snap(db, leg.id) == leg_before
    assert snap(db, sales.id) == sales_before


def test_dept_u_06__deleted_department_empty_body_400(db, M, dept, w1, u1, u2):
    """DEPT-U-06 — even an empty update of a deleted department raises 400.
    Rules: update_department R3."""
    leg = dept(w1, "Legacy", deleted=True, updated_by=u2)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, leg.id, DepartmentUpdate(), w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot update deleted department"
    r = reread(db, leg.id)
    assert r.name == "Legacy"
    assert r.updated_by == u2.id


def test_dept_u_07__rename_to_taken_name_409(db, M, dept, w1, u1, u2):
    """DEPT-U-07 — renaming to another live department's name raises 409.
    Rules: update_department R6; Errors row 3."""
    sales = dept(w1, "Sales")
    ops = dept(w1, "Ops", updated_by=u2)
    sales_before = snap(db, sales.id)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, ops.id, DepartmentUpdate(name="Sales"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Sales")
    r = reread(db, ops.id)
    assert r.name == "Ops"
    assert r.updated_by == u2.id
    assert snap(db, sales.id) == sales_before


def test_dept_u_08__name_taken_in_other_workspace_ok(db, M, dept, w1, w2, u1, u2):
    """DEPT-U-08 — a name used only in another workspace can be taken.
    Rules: update_department R6."""
    w2_sales = dept(w2, "Sales")
    ops = dept(w1, "Ops", updated_by=u2)
    w2_before = snap(db, w2_sales.id)
    M.update_department(db, ops.id, DepartmentUpdate(name="Sales"), w1.id, u1.id)
    r = reread(db, ops.id)
    assert r.name == "Sales"
    assert r.updated_by == u1.id
    assert snap(db, w2_sales.id) == w2_before


def test_dept_u_09__name_of_deleted_department_ok(db, M, dept, w1, u1, u2):
    """DEPT-U-09 — a name held only by a deleted department can be taken.
    Rules: update_department R6."""
    del_sales = dept(w1, "Sales", deleted=True)
    ops = dept(w1, "Ops", updated_by=u2)
    del_before = snap(db, del_sales.id)
    M.update_department(db, ops.id, DepartmentUpdate(name="Sales"), w1.id, u1.id)
    r = reread(db, ops.id)
    assert r.name == "Sales"
    assert r.updated_by == u1.id
    assert snap(db, del_sales.id) == del_before


def test_dept_u_10__case_change_of_own_name_ok(db, M, dept, w1, u1, u2):
    """DEPT-U-10 — the department itself is excluded from the duplicate check.
    Rules: update_department R6."""
    hr = dept(w1, "HR", updated_by=u2)
    M.update_department(db, hr.id, DepartmentUpdate(name="hr"), w1.id, u1.id)
    r = reread(db, hr.id)
    assert r.name == "hr"
    assert r.updated_by == u1.id


@pytest.mark.xfail(strict=True, reason=BUG_002)
def test_dept_u_11__rename_to_case_variant_409(db, M, dept, w1, u1, u2):
    """DEPT-U-11 — renaming to a case variant of a taken name raises 409 with the submitted name.
    Rules: update_department R6; Errors row 3 [BUG-002]."""
    dept(w1, "Sales")
    ops = dept(w1, "Ops", updated_by=u2)
    with pytest.raises(HTTPException) as exc:
        M.update_department(db, ops.id, DepartmentUpdate(name="SALES"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("SALES")
    r = reread(db, ops.id)
    assert r.name == "Ops"
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_009)
def test_dept_u_12__empty_body_keeps_updated_by(db, M, dept, w1, u1, u2):
    """DEPT-U-12 — an empty update leaves updated_by unchanged (name checks: DEPT-U-24).
    Rules: update_department R9 [BUG-009]."""
    hr = dept(w1, "HR", updated_by=u2)
    M.update_department(db, hr.id, DepartmentUpdate(), w1.id, u1.id)
    r = reread(db, hr.id)
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_009)
def test_dept_u_13__null_name_keeps_updated_by(db, M, dept, w1, u1, u2):
    """DEPT-U-13 — name=None leaves updated_by unchanged (name checks: DEPT-U-25).
    Rules: update_department R9 [BUG-009]."""
    hr = dept(w1, "HR", updated_by=u2)
    M.update_department(db, hr.id, DepartmentUpdate(name=None), w1.id, u1.id)
    r = reread(db, hr.id)
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_009)
def test_dept_u_14__same_name_keeps_updated_by(db, M, dept, w1, u1, u2):
    """DEPT-U-14 — sending the current name leaves updated_by unchanged (name checks: DEPT-U-26).
    Rules: update_department R9 [BUG-009]."""
    hr = dept(w1, "HR", updated_by=u2)
    M.update_department(db, hr.id, DepartmentUpdate(name="HR"), w1.id, u1.id)
    r = reread(db, hr.id)
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=f"{BUG_004}; {BUG_009}")
def test_dept_u_15__padded_same_name_is_noop(db, M, dept, w1, u1, u2):
    """DEPT-U-15 — " HR " is trimmed to the current name: no change, updated_by kept.
    Rules: update_department R5, R8, R9 [BUG-004] [BUG-009]."""
    hr = dept(w1, "HR", updated_by=u2)
    data = DepartmentUpdate(name=" HR ")
    assert data.name == "HR"
    M.update_department(db, hr.id, data, w1.id, u1.id)
    r = reread(db, hr.id)
    assert r.name == "HR"
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_004)
@pytest.mark.parametrize("blank", [
    pytest.param("", id="DEPT-U-16"),
    pytest.param("   ", id="DEPT-U-17"),
])
def test_dept_u_16_17__blank_name_rejected_by_schema(db, dept, w1, blank):
    """DEPT-U-16 / DEPT-U-17 — DepartmentUpdate rejects an empty / whitespace-only name.
    Rules: update_department R8; Errors row 4 [BUG-004]."""
    ops = dept(w1, "Ops")
    with pytest.raises(ValidationError):
        DepartmentUpdate(name=blank)
    assert reread(db, ops.id).name == "Ops"


@pytest.mark.xfail(strict=True, reason=BUG_004)
def test_dept_u_18__padded_new_name_stored_trimmed(db, M, dept, w1, u1, u2):
    """DEPT-U-18 — a padded new name is trimmed by the schema and stored trimmed.
    Rules: update_department R8 [BUG-004]."""
    team = dept(w1, "Team", updated_by=u2)
    data = DepartmentUpdate(name=" Ops ")
    assert data.name == "Ops"
    M.update_department(db, team.id, data, w1.id, u1.id)
    r = reread(db, team.id)
    assert r.name == "Ops"
    assert r.updated_by == u1.id


def test_dept_u_19__one_char_name_accepted(db, M, dept, w1, u1, u2):
    """DEPT-U-19 — a one-character new name builds and is stored.
    Rules: update_department R8."""
    ops = dept(w1, "Ops", updated_by=u2)
    data = DepartmentUpdate(name="a")
    M.update_department(db, ops.id, data, w1.id, u1.id)
    r = reread(db, ops.id)
    assert r.name == "a"
    assert r.updated_by == u1.id


def test_dept_u_20__omitted_and_null_name_build():
    """DEPT-U-20 — DepartmentUpdate() and DepartmentUpdate(name=None) both build with name None.
    Rules: update_department R7."""
    a = DepartmentUpdate()
    b = DepartmentUpdate(name=None)
    assert a.name is None
    assert b.name is None


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_u_21__db_rejects_rename_to_live_name(db, dept, w1):
    """DEPT-U-21 — the database rejects renaming "Budget" to live "Finance".
    Rules: update_department R11 [BUG-003]."""
    dept(w1, "Finance")
    budget = dept(w1, "Budget")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            budget.name = "Finance"
            db.flush()
    assert reread(db, budget.id).name == "Budget"


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_u_22__race_rename_maps_to_409(db, M, dept, w1, u1, u2, race):
    """DEPT-U-22 — a duplicate rename reaching the flush (race) raises 409, not IntegrityError.
    Rules: update_department R11; Errors row 3 [BUG-003]."""
    dept(w1, "Finance")
    budget = dept(w1, "Budget", updated_by=u2)
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.update_department(db, budget.id, DepartmentUpdate(name="Finance"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("Finance")
    r = reread(db, budget.id)
    assert r.name == "Budget"
    assert r.updated_by == u2.id


@pytest.mark.xfail(strict=True, reason=BUG_003)
def test_dept_u_23__race_case_variant_rename_maps_to_409(db, M, dept, w1, u1, u2, race):
    """DEPT-U-23 — a case-variant rename reaching the flush raises 409 with the submitted name.
    Rules: update_department R11; Errors row 3 [BUG-003]."""
    fin = dept(w1, "Finance")
    budget = dept(w1, "Budget", updated_by=u2)
    fin_before = snap(db, fin.id)
    with pytest.raises(HTTPException) as exc:
        with db.begin_nested():
            M.update_department(db, budget.id, DepartmentUpdate(name="finance"), w1.id, u1.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == exists_msg("finance")
    r = reread(db, budget.id)
    assert r.name == "Budget"
    assert r.updated_by == u2.id
    assert snap(db, fin.id) == fin_before


def test_dept_u_24__empty_body_leaves_name_unchanged(db, M, dept, w1, u1, u2):
    """DEPT-U-24 — an empty update succeeds and leaves the row unchanged (updated_by not checked).
    Rules: update_department R7, R10."""
    hr = dept(w1, "HR", updated_by=u2)
    res = M.update_department(db, hr.id, DepartmentUpdate(), w1.id, u1.id)
    assert isinstance(res, Department)
    assert res.id == hr.id
    assert res.name == "HR"
    r = reread(db, hr.id)
    assert r.name == "HR"
    assert r.workspace_id == w1.id
    assert r.created_by == u2.id
    assert r.is_deleted is False
    assert r.is_active is True
    assert r.deleted_at is None
    assert r.deleted_by is None
    assert w_count(db, w1) == 1
    # updated_by deliberately not asserted (BUG-009, see DEPT-U-12)


def test_dept_u_25__explicit_null_name_leaves_name_unchanged(db, M, dept, w1, u1, u2):
    """DEPT-U-25 — name=None succeeds, writes no NULL, leaves the row unchanged (updated_by not checked).
    Rules: update_department R7, R10."""
    hr = dept(w1, "HR", updated_by=u2)
    res = M.update_department(db, hr.id, DepartmentUpdate(name=None), w1.id, u1.id)
    assert isinstance(res, Department)
    assert res.id == hr.id
    assert res.name == "HR"
    r = reread(db, hr.id)
    assert r.name == "HR"
    assert r.workspace_id == w1.id
    assert r.created_by == u2.id
    assert r.is_deleted is False
    assert r.is_active is True
    assert r.deleted_at is None
    assert r.deleted_by is None
    assert w_count(db, w1) == 1
    # updated_by deliberately not asserted (BUG-009, see DEPT-U-13)


def test_dept_u_26__same_name_no_self_collision(db, M, dept, w1, u1, u2):
    """DEPT-U-26 — sending the current name succeeds (no 409) and leaves the row unchanged (updated_by not checked).
    Rules: update_department R5, R10."""
    hr = dept(w1, "HR", updated_by=u2)
    res = M.update_department(db, hr.id, DepartmentUpdate(name="HR"), w1.id, u1.id)
    assert isinstance(res, Department)
    assert res.id == hr.id
    assert res.name == "HR"
    r = reread(db, hr.id)
    assert r.name == "HR"
    assert r.workspace_id == w1.id
    assert r.created_by == u2.id
    assert r.is_deleted is False
    assert r.is_active is True
    assert r.deleted_at is None
    assert r.deleted_by is None
    assert w_count(db, w1) == 1
    # updated_by deliberately not asserted (BUG-009, see DEPT-U-14)


# --------------------------------------------------------------------------- #
# get_department
# --------------------------------------------------------------------------- #

def test_dept_g_01__get_live_department(db, M, dept, w1):
    """DEPT-G-01 — a live department of the workspace is returned.
    Rules: get_department R1."""
    sales = dept(w1, "Sales")
    res = M.get_department(db, sales.id, w1.id)
    assert isinstance(res, Department)
    assert res.id == sales.id
    assert res.name == "Sales"
    assert res.workspace_id == w1.id


def test_dept_g_02__missing_id_404(db, M, dept, w1):
    """DEPT-G-02 — an unknown id raises 404.
    Rules: get_department R2; Errors row 1."""
    dept(w1, "Sales")
    missing = missing_id(db)
    with pytest.raises(HTTPException) as exc:
        M.get_department(db, missing, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(missing)


def test_dept_g_03__other_workspace_404(db, M, dept, w1, w2):
    """DEPT-G-03 — a department of another workspace raises 404.
    Rules: get_department R2; Errors row 1."""
    sales = dept(w2, "Sales")
    with pytest.raises(HTTPException) as exc:
        M.get_department(db, sales.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(sales.id)


@pytest.mark.xfail(strict=True, reason=BUG_005)
def test_dept_g_04__deleted_department_404_by_default(db, M, dept, w1):
    """DEPT-G-04 — a soft-deleted department is not found by default.
    Rules: get_department R3; Errors row 1 [BUG-005]."""
    leg = dept(w1, "Legacy", deleted=True)
    with pytest.raises(HTTPException) as exc:
        M.get_department(db, leg.id, w1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(leg.id)


@pytest.mark.xfail(strict=True, reason=BUG_005)
def test_dept_g_05__include_deleted_returns_deleted(db, M, dept, w1):
    """DEPT-G-05 — include_deleted=True returns a soft-deleted department.
    Rules: get_department R4 [BUG-005]."""
    leg = dept(w1, "Legacy", deleted=True)
    res = M.get_department(db, leg.id, w1.id, include_deleted=True)
    assert isinstance(res, Department)
    assert res.id == leg.id
    assert res.name == "Legacy"
    assert res.is_deleted is True


@pytest.mark.xfail(strict=True, reason=BUG_005)
def test_dept_g_06__include_deleted_keeps_workspace_isolation(db, M, dept, w1, w2):
    """DEPT-G-06 — include_deleted=True still raises 404 for another workspace's department.
    Rules: get_department R4 [BUG-005]."""
    sales = dept(w2, "Sales")
    with pytest.raises(HTTPException) as exc:
        M.get_department(db, sales.id, w1.id, include_deleted=True)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(sales.id)


# --------------------------------------------------------------------------- #
# search_departments
# --------------------------------------------------------------------------- #

@pytest.fixture
def five(dept, w1):
    """Setup of DEPT-S-08..S-11: live Alpha, Bravo, Charlie, Delta, Echo (in order)."""
    return [dept(w1, n) for n in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")]


@pytest.fixture
def old_then_live(dept, w1):
    """Setup of DEPT-S-04/S-05: deleted Old A, Old B, Old C, then live Ops, Sales."""
    for n in ("Old A", "Old B", "Old C"):
        dept(w1, n, deleted=True)
    return [dept(w1, "Ops"), dept(w1, "Sales")]


def test_dept_s_01__only_own_workspace(db, M, dept, w1, w2):
    """DEPT-S-01 — only the workspace's departments are listed.
    Rules: search_departments R1."""
    own = [dept(w1, "Ops"), dept(w1, "Sales")]
    dept(w2, "Sales")
    dept(w2, "Finance")
    res = M.search_departments(db, w1.id)
    assert names(res) == {"Ops", "Sales"}
    assert all(d.workspace_id == w1.id for d in res)
    assert {d.id for d in res} == {d.id for d in own}


def test_dept_s_02__deleted_hidden_by_default(db, M, dept, w1):
    """DEPT-S-02 — soft-deleted departments are not listed by default.
    Rules: search_departments R4."""
    dept(w1, "Ops")
    dept(w1, "Sales")
    dept(w1, "Legacy", deleted=True)
    assert names(M.search_departments(db, w1.id)) == {"Ops", "Sales"}


def test_dept_s_03__include_deleted_lists_deleted(db, M, dept, w1):
    """DEPT-S-03 — include_deleted=True keeps soft-deleted departments.
    Rules: search_departments R5."""
    dept(w1, "Ops")
    dept(w1, "Sales")
    dept(w1, "Legacy", deleted=True)
    res = M.search_departments(db, w1.id, include_deleted=True)
    assert names(res) == {"Ops", "Sales", "Legacy"}


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_006))
def test_dept_s_04__deleted_do_not_take_page_slots(db, M, w1, old_then_live):
    """DEPT-S-04 — deleted rows are excluded before limit is applied.
    Rules: search_departments R2, R4 [BUG-006]."""
    res = M.search_departments(db, w1.id, limit=2)
    assert in_order(res) == ["Ops", "Sales"]
    assert len(res) == 2


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_006))
def test_dept_s_05__deleted_not_counted_by_skip(db, M, w1, old_then_live):
    """DEPT-S-05 — skip counts only returnable departments.
    Rules: search_departments R2, R4 [BUG-006]."""
    res = M.search_departments(db, w1.id, skip=1, limit=1)
    assert in_order(res) == ["Sales"]


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_007))
def test_dept_s_06__search_before_limit(db, M, dept, w1):
    """DEPT-S-06 — the name search covers the whole workspace before limit.
    Rules: search_departments R2, R6 [BUG-007]."""
    for n in ("Accounts", "Budget", "Customs", "Warehouse"):
        dept(w1, n)
    res = M.search_departments(db, w1.id, search="ware", limit=2)
    assert in_order(res) == ["Warehouse"]


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_007))
def test_dept_s_07__search_before_skip(db, M, dept, w1):
    """DEPT-S-07 — skip counts only matching departments (sorted Resale, Sales, Wholesale).
    Rules: search_departments R2, R6 [BUG-007]."""
    for n in ("Resale", "Admin", "Wholesale", "Billing", "Sales"):
        dept(w1, n)
    res = M.search_departments(db, w1.id, search="ale", skip=1, limit=1)
    assert in_order(res) == ["Sales"]


def test_dept_s_08__full_page_when_exactly_enough(db, M, w1, five):
    """DEPT-S-08 — skip + limit == number of matches gives a full page.
    Rules: search_departments R2."""
    assert len(M.search_departments(db, w1.id, skip=2, limit=3)) == 3


def test_dept_s_09__short_last_page(db, M, w1, five):
    """DEPT-S-09 — skip + limit past the matches gives the remainder.
    Rules: search_departments R2."""
    assert len(M.search_departments(db, w1.id, skip=3, limit=3)) == 2


def test_dept_s_10__skip_past_last_match_empty(db, M, w1, five):
    """DEPT-S-10 — skip equal to the number of matches returns [].
    Rules: search_departments R8."""
    assert M.search_departments(db, w1.id, skip=5) == []


def test_dept_s_11__skip_to_last_match(db, M, w1, five):
    """DEPT-S-11 — skip one before the end returns one item.
    Rules: search_departments R8."""
    assert len(M.search_departments(db, w1.id, skip=4)) == 1


def test_dept_s_12__default_limit_100(db, M, dept, w1):
    """DEPT-S-12 — the default limit returns at most 100 departments.
    Rules: search_departments R2."""
    for i in range(1, 102):
        dept(w1, f"Dept {i:03d}")
    assert len(M.search_departments(db, w1.id)) == 100


@pytest.mark.xfail(strict=False, reason=BUG_008_ORDER)
def test_dept_s_13__ordered_by_name_case_insensitive(db, M, dept, w1):
    """DEPT-S-13 — results are ordered by name, case-insensitive.
    Rules: search_departments R3 [BUG-008]."""
    for n in ("Sales", "accounting", "HR", "beta"):
        dept(w1, n)
    res = M.search_departments(db, w1.id)
    assert in_order(res) == ["accounting", "beta", "HR", "Sales"]


@pytest.mark.xfail(strict=False, reason=BUG_008_ORDER)
def test_dept_s_14__equal_names_tie_broken_by_id(db, M, dept, w1):
    """DEPT-S-14 — names equal ignoring case are ordered by id ascending.
    Rules: search_departments R3 [BUG-008]."""
    a = dept(w1, "sales", deleted=True)
    acc = dept(w1, "Accounting")
    hr = dept(w1, "HR")
    b = dept(w1, "Sales")
    assert b.id > a.id
    res = M.search_departments(db, w1.id, include_deleted=True)
    assert [(d.name, d.id) for d in res] == [
        ("Accounting", acc.id), ("HR", hr.id), ("sales", a.id), ("Sales", b.id),
    ]


@pytest.mark.xfail(strict=False, reason=BUG_008_ORDER)
def test_dept_s_15__pages_neither_repeat_nor_skip(db, M, dept, w1):
    """DEPT-S-15 — ordering is applied before paging; pages are disjoint and complete.
    Rules: search_departments R3 [BUG-008]."""
    rows = [dept(w1, n) for n in ("Echo", "delta", "Charlie", "bravo", "Alpha")]
    p1 = M.search_departments(db, w1.id, skip=0, limit=2)
    p2 = M.search_departments(db, w1.id, skip=2, limit=2)
    p3 = M.search_departments(db, w1.id, skip=4, limit=2)
    assert in_order(p1) == ["Alpha", "bravo"]
    assert in_order(p2) == ["Charlie", "delta"]
    assert in_order(p3) == ["Echo"]
    all_ids = [d.id for d in p1 + p2 + p3]
    assert len(set(all_ids)) == 5
    assert set(all_ids) == {r.id for r in rows}


def test_dept_s_16__substring_search(db, M, dept, w1):
    """DEPT-S-16 — search matches a substring of the name.
    Rules: search_departments R6."""
    for n in ("Sales", "Marketing", "Resale"):
        dept(w1, n)
    assert names(M.search_departments(db, w1.id, search="ale")) == {"Sales", "Resale"}


def test_dept_s_17__search_case_insensitive(db, M, dept, w1):
    """DEPT-S-17 — search ignores case.
    Rules: search_departments R6."""
    dept(w1, "sales team")
    dept(w1, "Ops")
    assert names(M.search_departments(db, w1.id, search="SALES")) == {"sales team"}


def test_dept_s_18__search_whitespace_significant(db, M, dept, w1):
    """DEPT-S-18 — a trailing space in search is significant.
    Rules: search_departments R6."""
    dept(w1, "Sales")
    dept(w1, "Sales Team")
    assert names(M.search_departments(db, w1.id, search="sales ")) == {"Sales Team"}


def test_dept_s_19__search_none_no_filter(db, M, dept, w1):
    """DEPT-S-19 — search=None applies no filter.
    Rules: search_departments R7."""
    dept(w1, "Ops")
    dept(w1, "Sales")
    assert names(M.search_departments(db, w1.id, search=None)) == {"Ops", "Sales"}


def test_dept_s_20__search_empty_no_filter(db, M, dept, w1):
    """DEPT-S-20 — search="" applies no filter.
    Rules: search_departments R7."""
    dept(w1, "Ops")
    dept(w1, "Sales")
    assert names(M.search_departments(db, w1.id, search="")) == {"Ops", "Sales"}


def test_dept_s_21__empty_workspace(db, M, dept, w1, w2):
    """DEPT-S-21 — a workspace with no departments returns [].
    Rules: search_departments R8."""
    dept(w2, "Sales")
    assert M.search_departments(db, w1.id) == []


def test_dept_s_22__no_match(db, M, dept, w1):
    """DEPT-S-22 — a search with no match returns [].
    Rules: search_departments R8."""
    dept(w1, "Ops")
    assert M.search_departments(db, w1.id, search="xyz") == []


def test_dept_s_23__percent_is_literal(db, M, dept, w1):
    """DEPT-S-23 — "%" in search matches only a literal percent sign.
    Rules: search_departments R6a (HR-8); regression guard for the BUG-007 fix."""
    for n in ("Growth 100%", "Sales", "Ops"):
        dept(w1, n)
    assert names(M.search_departments(db, w1.id, search="%")) == {"Growth 100%"}


def test_dept_s_24__underscore_is_literal(db, M, dept, w1):
    """DEPT-S-24 — "_" in search matches only a literal underscore.
    Rules: search_departments R6a (HR-8); regression guard for the BUG-007 fix."""
    for n in ("R_D", "RnD", "Ops"):
        dept(w1, n)
    assert names(M.search_departments(db, w1.id, search="_")) == {"R_D"}


def test_dept_s_25__underscore_literal_case_insensitive(db, M, dept, w1):
    """DEPT-S-25 — "r_d" matches "R_D" but not "RnD".
    Rules: search_departments R6a (HR-8); regression guard for the BUG-007 fix."""
    for n in ("R_D", "RnD", "Ops"):
        dept(w1, n)
    assert names(M.search_departments(db, w1.id, search="r_d")) == {"R_D"}


# --------------------------------------------------------------------------- #
# delete_department
# --------------------------------------------------------------------------- #

def test_dept_d_01__soft_delete_happy_path(db, M, dept, w1, u1, u2):
    """DEPT-D-01 — deleting stamps is_deleted/deleted_at/deleted_by and keeps the row.
    Rules: delete_department R3, R4."""
    ops = dept(w1, "Ops", updated_by=u2)
    res = M.delete_department(db, ops.id, w1.id, u1.id)
    assert isinstance(res, Department)
    assert res.id == ops.id
    assert res.is_deleted is True
    r = reread(db, ops.id)
    assert r.is_deleted is True
    assert r.deleted_at == NOW
    assert r.deleted_at.tzinfo is None
    assert r.deleted_by == u1.id
    assert r.name == "Ops"
    assert r.updated_by == u2.id
    assert r.is_active is True
    assert r.created_by == u2.id
    assert r.workspace_id == w1.id
    assert w_count(db, w1) == 1


def test_dept_d_02__missing_id_404(db, M, dept, w1, u1):
    """DEPT-D-02 — deleting an unknown id raises 404 and deletes nothing.
    Rules: delete_department R1; Errors row 1."""
    ops = dept(w1, "Ops")
    missing = missing_id(db)
    with pytest.raises(HTTPException) as exc:
        M.delete_department(db, missing, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(missing)
    r = reread(db, ops.id)
    assert r.is_deleted is False
    assert r.deleted_at is None
    assert r.deleted_by is None


def test_dept_d_03__other_workspace_404(db, M, dept, w1, w2, u1):
    """DEPT-D-03 — another workspace's department is reported as not found.
    Rules: delete_department R1; Errors row 1."""
    ops = dept(w2, "Ops")
    with pytest.raises(HTTPException) as exc:
        M.delete_department(db, ops.id, w1.id, u1.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == not_found(ops.id)
    r = reread(db, ops.id)
    assert r.is_deleted is False
    assert r.deleted_at is None
    assert r.deleted_by is None


def test_dept_d_04__already_deleted_400(db, M, dept, w1, u1, u2):
    """DEPT-D-04 — deleting a deleted department raises 400 and keeps its stamps.
    Rules: delete_department R2; Errors row 2."""
    leg = dept(w1, "Legacy", deleted=True)
    with pytest.raises(HTTPException) as exc:
        M.delete_department(db, leg.id, w1.id, u1.id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Department is already deleted"
    r = reread(db, leg.id)
    assert r.is_deleted is True
    assert r.deleted_at == T0
    assert r.deleted_by == u2.id


# --------------------------------------------------------------------------- #
# _check_name_exists
# --------------------------------------------------------------------------- #

def test_dept_n_01__empty_workspace_false(db, M, dept, w1, w2):
    """DEPT-N-01 — a workspace with no departments has no name.
    Rules: _check_name_exists R7."""
    dept(w2, "Sales")
    assert M._check_name_exists(db, w1.id, "Sales") is False


def test_dept_n_02__live_match_true(db, M, dept, w1):
    """DEPT-N-02 — a live department with the name gives True (exclude_id=None).
    Rules: _check_name_exists R1, R6."""
    dept(w1, "Sales")
    assert M._check_name_exists(db, w1.id, "Sales", exclude_id=None) is True


def test_dept_n_03__other_workspace_ignored(db, M, dept, w1, w2):
    """DEPT-N-03 — a match in another workspace is not considered.
    Rules: _check_name_exists R2."""
    dept(w2, "Sales")
    dept(w1, "Ops")
    assert M._check_name_exists(db, w1.id, "Sales") is False


def test_dept_n_04__deleted_ignored(db, M, dept, w1):
    """DEPT-N-04 — a soft-deleted match is ignored.
    Rules: _check_name_exists R3."""
    dept(w1, "Sales", deleted=True)
    assert M._check_name_exists(db, w1.id, "Sales") is False


def test_dept_n_05__deleted_and_live_true(db, M, dept, w1):
    """DEPT-N-05 — a live match counts even next to a deleted one.
    Rules: _check_name_exists R3."""
    dept(w1, "Sales", deleted=True)
    dept(w1, "Sales")
    assert M._check_name_exists(db, w1.id, "Sales") is True


@pytest.mark.xfail(strict=True, reason=BUG_002)
@pytest.mark.parametrize("variant", [
    pytest.param("sales", id="DEPT-N-06"),
    pytest.param("SALES", id="DEPT-N-07"),
    pytest.param("Sales ", id="DEPT-N-08"),
    pytest.param(" Sales", id="DEPT-N-09"),
])
def test_dept_n_06_09__case_and_outer_whitespace_ignored(db, M, dept, w1, variant):
    """DEPT-N-06..N-09 — case and leading/trailing whitespace are ignored when matching.
    Rules: _check_name_exists R4 [BUG-002]."""
    dept(w1, "Sales")
    assert M._check_name_exists(db, w1.id, variant) is True


def test_dept_n_10__inner_difference_no_match(db, M, dept, w1):
    """DEPT-N-10 — "Sales Team" does not match "Sales".
    Rules: _check_name_exists R4."""
    dept(w1, "Sales")
    assert M._check_name_exists(db, w1.id, "Sales Team") is False


def test_dept_n_11__match_at_row_100(db, M, dept, w1):
    """DEPT-N-11 — a live match at the 100th row is found.
    Rules: _check_name_exists R5."""
    for i in range(1, 31):
        dept(w1, f"Archived {i:02d}", deleted=True)
    for i in range(1, 70):
        dept(w1, f"Team {i:02d}")
    dept(w1, "Logistics")  # 100th row
    assert M._check_name_exists(db, w1.id, "Logistics") is True


@pytest.mark.xfail(strict=False, reason=_row_order(BUG_001))
def test_dept_n_12__match_at_row_101(db, M, dept, w1):
    """DEPT-N-12 — a live match at the 101st row is found.
    Rules: _check_name_exists R5 [BUG-001]."""
    for i in range(1, 31):
        dept(w1, f"Archived {i:02d}", deleted=True)
    for i in range(1, 71):
        dept(w1, f"Team {i:02d}")
    dept(w1, "Logistics")  # 101st row
    assert M._check_name_exists(db, w1.id, "Logistics") is True


def test_dept_n_13__exclude_id_ignores_self(db, M, dept, w1):
    """DEPT-N-13 — the excluded department is ignored even if its name matches.
    Rules: _check_name_exists R6."""
    a = dept(w1, "Sales")
    assert M._check_name_exists(db, w1.id, "Sales", exclude_id=a.id) is False


def test_dept_n_14__exclude_other_id_still_true(db, M, dept, w1):
    """DEPT-N-14 — excluding a different department still finds the match.
    Rules: _check_name_exists R6."""
    dept(w1, "Sales")
    b = dept(w1, "Ops")
    assert M._check_name_exists(db, w1.id, "Sales", exclude_id=b.id) is True

# --------------------------------------------------------------------------- #
# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
# --------------------------------------------------------------------------- #
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


# [claude] DEPT-C-21
def test_dept_c_21__create_flushed_not_committed(db, M, w1, u1, monkeypatch):
    """DEPT-C-21 — the create is flushed but not committed: a rollback removes the row.
    Rules: create_department Side effects (no commit)."""
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    res = M.create_department(db, DepartmentCreate(name="Sales"), w1.id, u1.id)
    # Then 1
    assert res.id is not None
    # Then 2
    assert w_count(db, w1) == 1
    sp.rollback()
    # Then 3
    assert w_count(db, w1) == 0
    # Then 4
    spy.assert_not_called()


# [claude] DEPT-U-27
def test_dept_u_27__update_flushed_not_committed(db, M, dept, w1, u1, u2, monkeypatch):
    """DEPT-U-27 — the update is flushed but not committed: a rollback restores the row.
    Rules: update_department Side effects (no commit)."""
    ops = dept(w1, "Ops", updated_by=u2)
    ops_id = ops.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    res = M.update_department(db, ops_id, DepartmentUpdate(name="Operations"), w1.id, u1.id)
    # Then 1
    assert res.name == "Operations"
    # Then 2
    assert reread(db, ops_id).name == "Operations"
    sp.rollback()
    # Then 3
    r = reread(db, ops_id)
    assert r.name == "Ops"
    assert r.updated_by == u2.id
    # Then 4
    spy.assert_not_called()


# [claude] DEPT-D-05
def test_dept_d_05__delete_flushed_not_committed(db, M, dept, w1, u1, monkeypatch):
    """DEPT-D-05 — the soft delete is flushed but not committed: a rollback makes the row live.
    Rules: delete_department Side effects (no commit)."""
    ops = dept(w1, "Ops")
    ops_id = ops.id
    sp = db.begin_nested()
    spy = commit_spy(db, monkeypatch)
    res = M.delete_department(db, ops_id, w1.id, u1.id)
    # Then 1
    assert res.is_deleted is True
    # Then 2
    assert reread(db, ops_id).is_deleted is True
    sp.rollback()
    # Then 3
    r = reread(db, ops_id)
    assert r.is_deleted is False
    assert r.deleted_at is None
    assert r.deleted_by is None
    # Then 4
    spy.assert_not_called()


# [claude] DEPT-S-26
@pytest.mark.xfail(strict=True, reason=BUG_008)
def test_dept_s_26__list_query_orders_by_name_then_id(db, M, dept, w1):
    """DEPT-S-26 — the list statement orders by lower(name), then id (strict alarm for BUG-008).
    Rules: search_departments R3 [BUG-008]."""
    dept(w1, "Ops")
    dept(w1, "Sales")
    with record_sql(db) as sql_log:
        rows = M.search_departments(db, w1.id)
    # Then 1
    assert names(rows) == {"Ops", "Sales"}
    # Then 2
    assert any(
        re.search(r"FROM departments\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL | re.IGNORECASE)
        for s in sql_log
    )
