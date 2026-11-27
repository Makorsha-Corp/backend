"""Unit tests for app/services/department_service.py.

Implements tests/unit/services/department_service.cases.md, one test per case,
in card order. Real Postgres session (`db` fixture): a `commit()` only releases
a savepoint, so the service's commits are safe and the fixture's outer rollback
discards everything. Nothing is patched except what Conventions name: the
failing commit / failing refresh wraps and the race simulation of DSV-C-09.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (A -> a, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.department_service import department_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton department_service"
svc = department_service

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> actors: W1, W2, U1, U2, U3 exist in every test
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 = the acting user
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# U2 = created_by of the Given rows
@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


@pytest.fixture(autouse=True)
def actors(u3):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "gone" (after "but")
def gone(u2):
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": u2.id}


def _dept_fields(w1, u2, but):
    fields = {"workspace_id": w1.id, "name": "Sales", "created_by": u2.id}
    fields.update(but)
    return fields


# Convention "dept": one row, flushed
@pytest.fixture
def mk_dept(db, w1, u2):
    def _mk(**but):
        row = Department(**_dept_fields(w1, u2, but))
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "n rows, by add_all"
@pytest.fixture
def mk_depts(db, w1, u2):
    def _mk(list_of_but):
        rows = [Department(**_dept_fields(w1, u2, but)) for but in list_of_but]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(Department).where(Department.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = Department.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


# Convention "count:" lines: departments rows (all workspaces), with the filter stated
def count_depts(db, **filters):
    query = select(func.count()).select_from(Department)
    for column, value in filters.items():
        query = query.where(getattr(Department, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written": departments rows of all workspaces
def written(db):
    return count_depts(db)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# DepartmentService.create_department
# --------------------------------------------------------------------------- #

# [claude] DSV-C-01
def test_dsv_c_01__a_new_department_is_committed_and_returned_re_read(db, w1, u1):
    """DSV-C-01 — a new department is committed and returned re-read.
    Rules: `create_department` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    assert "created_by" not in unloaded(result)
    # Then 2
    assert isinstance(result, Department)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.name == "Sales"
    assert result.workspace_id == w1.id
    assert result.created_by == u1.id
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(Department).where(Department.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "Sales"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False
    # Then 6
    assert count_depts(db, workspace_id=w1.id) == 1


# [claude] DSV-C-02
def test_dsv_c_02__a_duplicate_name_the_managers_409_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, mk_dept,
):
    """DSV-C-02 — a duplicate name: the manager's 409 passes unchanged and the session is rolled back.
    Rules: `create_department` R2, Errors row 1; TC3"""
    a = mk_dept()
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_dept(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Department with name 'Sales' already exists"
    # Then 4
    assert count_depts(db, name="Extra") == 0
    # Then 5
    assert count_depts(db, workspace_id=w1.id, name="Sales") == 1
    # Then 6
    assert written(db) == before
    # Then 7
    assert snap(db, a) == before_a
    # Then 8
    assert usable(db)


# [claude] DSV-C-03
def test_dsv_c_03__a_database_error_at_the_flush_passes_unchanged_and_nothing_is_saved(db, w1, mk_dept):
    """DSV-C-03 — a database error at the flush passes unchanged and nothing is saved.
    Rules: `create_department` Errors row 2; TC3"""
    mk_dept(name="Ops")
    commit_point(db)
    before = written(db)
    mk_dept(name="Extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_depts(db, name="Sales") == 0
    # Then 4
    assert count_depts(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] DSV-C-04
def test_dsv_c_04__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u1):
    """DSV-C-04 — a failing commit is rolled back and re-raised.
    Rules: `create_department` R3; TC4"""
    commit_point(db)
    before = written(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_department(
                db, department_in=DepartmentCreate(name="Sales"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_depts(db, workspace_id=w1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] DSV-C-05
def test_dsv_c_05__a_failing_re_read_after_the_commit_leaves_the_department_saved(db, w1, u1):
    """DSV-C-05 — a failing re-read after the commit leaves the department saved.
    Rules: `create_department` R3; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_department(
                db, department_in=DepartmentCreate(name="Sales"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_depts(db, workspace_id=w1.id) == 1
    # Then 3
    db.expire_all()
    row = db.execute(select(Department).where(Department.workspace_id == w1.id)).scalar_one()
    assert row.name == "Sales"
    assert row.created_by == u1.id


# [claude] DSV-C-06
@pytest.mark.xfail(strict=True, reason="BUG-002: Duplicate-name check is case- and whitespace-sensitive")
def test_dsv_c_06__pass_through_bug_002_a_name_in_another_case_is_refused_with_the_submitted_name(
    db, w1, u1, mk_dept,
):
    """DSV-C-06 — pass-through BUG-002: a name in another case is refused with the submitted name.
    Rules: `create_department` R1, R2 [BUG-002]"""
    mk_dept()
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_department(db, department_in=DepartmentCreate(name="sales"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Department with name 'sales' already exists"
    # Then 4
    assert written(db) == before


# [claude] DSV-C-07
@pytest.mark.xfail(strict=True, reason="BUG-004: Blank / whitespace-only department names accepted")
def test_dsv_c_07__pass_through_bug_004_a_padded_name_is_stored_trimmed(db, w1, u1):
    """DSV-C-07 — pass-through BUG-004: a padded name is stored trimmed.
    Rules: `create_department` R1 [BUG-004]"""
    data = DepartmentCreate(name=" Sales ")
    commit_point(db)
    result = svc.create_department(db, department_in=data, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(Department).where(Department.id == result_id)).scalar_one()
    assert row.name == "Sales"


# [claude] DSV-C-08
@pytest.mark.xfail(strict=False, reason="BUG-001: Duplicate-name check only scans the first 100 departments")
def test_dsv_c_08__pass_through_bug_001_a_duplicate_past_the_first_100_rows_is_still_refused(
    db, w1, u1, u2, mk_dept, mk_depts,
):
    """DSV-C-08 — pass-through BUG-001: a duplicate past the first 100 rows is still refused.
    Rules: `create_department` R1, R2 [BUG-001]"""
    mk_depts([{"name": f"Archived {k:02d}", **gone(u2)} for k in range(1, 31)])
    mk_depts([{"name": f"Team {k:02d}"} for k in range(1, 80)])
    mk_dept(name="Logistics")
    mk_depts([{"name": f"Unit {k:02d}"} for k in range(1, 11)])
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_department(
            db, department_in=DepartmentCreate(name="Logistics"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Department with name 'Logistics' already exists"
    # Then 4
    assert count_depts(db, workspace_id=w1.id, name="Logistics") == 1
    # Then 5
    assert count_depts(db, workspace_id=w1.id) == 120


# [claude] DSV-C-09
@pytest.mark.xfail(strict=True, reason="BUG-003: Department name uniqueness not enforced by the database")
def test_dsv_c_09__pass_through_bug_003_a_create_that_loses_the_race_gets_the_409_nothing_saved(
    db, w1, u1, mk_dept,
):
    """DSV-C-09 — pass-through BUG-003: a create that loses the race gets the 409, nothing saved.
    Rules: `create_department` R1, R2 [BUG-003]"""
    mk_dept(name="Finance")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.department_manager, "_check_name_exists", return_value=False):
            svc.create_department(
                db, department_in=DepartmentCreate(name="Finance"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Department with name 'Finance' already exists"
    # Then 4
    assert count_depts(db, workspace_id=w1.id, name="Finance") == 1
    # Then 5
    assert usable(db)


# --------------------------------------------------------------------------- #
# DepartmentService.get_department
# --------------------------------------------------------------------------- #

# [claude] DSV-G-01
def test_dsv_g_01__a_live_department_of_the_workspace_is_returned(db, w1, w2, mk_dept):
    """DSV-G-01 — a live department of the workspace is returned.
    Rules: `get_department` R1"""
    mk_dept(workspace_id=w2.id, name="Far")
    a = mk_dept()
    commit_point(db)
    result = svc.get_department(db, department_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Department)
    # Then 2
    assert result.id == a.id
    assert result.name == "Sales"
    assert result.workspace_id == w1.id


# [claude] DSV-G-02
def test_dsv_g_02__another_workspaces_id_the_managers_404_passes_unchanged(db, w1, w2, mk_dept):
    """DSV-G-02 — another workspace's id: the manager's 404 passes unchanged.
    Rules: `get_department` R4, Errors row 1"""
    mk_dept()
    z = mk_dept(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_department(db, department_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Department with ID {z.id} not found"
    # Then 4
    assert snap(db, z) == before_z


# [claude] DSV-G-03
def test_dsv_g_03__id_0_gets_the_404(db, w1, mk_dept):
    """DSV-G-03 — id 0 gets the 404.
    Rules: `get_department` R4, Errors row 1"""
    mk_dept()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_department(db, department_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Department with ID 0 not found"


# [claude] DSV-G-04
@pytest.mark.xfail(strict=True, reason="BUG-005: `get_department` returns soft-deleted departments")
def test_dsv_g_04__a_soft_deleted_department_is_hidden_by_default(db, w1, u2, mk_dept):
    """DSV-G-04 — a soft-deleted department is hidden by default.
    Rules: `get_department` R2 [BUG-005], Errors row 1"""
    a = mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_department(db, department_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Department with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] DSV-G-05
@pytest.mark.xfail(strict=True, reason="BUG-005: `get_department` returns soft-deleted departments")
def test_dsv_g_05__include_deleted_true_returns_a_soft_deleted_department(db, w1, u2, mk_dept):
    """DSV-G-05 — include_deleted=True returns a soft-deleted department.
    Rules: `get_department` R3 [BUG-005]"""
    a = mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    result = svc.get_department(db, department_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True
    assert result.name == "Legacy"


# [claude] DSV-G-06
@pytest.mark.xfail(strict=True, reason="BUG-005: `get_department` returns soft-deleted departments")
def test_dsv_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, w2, u2, mk_dept):
    """DSV-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_department` R3 [BUG-005], Errors row 1"""
    z = mk_dept(workspace_id=w2.id, name="Far", **gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_department(db, department_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Department with ID {z.id} not found"


# [claude] DSV-G-07
def test_dsv_g_07__the_read_neither_commits_nor_rolls_back(db, w1, mk_dept):
    """DSV-G-07 — the read neither commits nor rolls back.
    Rules: `get_department` R5; TC6"""
    a = mk_dept()
    b = mk_dept(name="Ops")
    commit_point(db)
    mk_dept(name="Pending")
    b.name = "Edited"
    result = svc.get_department(db, department_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_depts(db, name="Pending") == 1
    # Then 5
    db.rollback()
    assert count_depts(db, name="Pending") == 0
    # Then 6
    assert reread(db, b).name == "Ops"


# --------------------------------------------------------------------------- #
# DepartmentService.get_departments
# --------------------------------------------------------------------------- #

# [claude] DSV-L-01
def test_dsv_l_01__the_search_reaches_the_manager_and_only_the_workspaces_matches_come_back(
    db, w1, w2, mk_dept,
):
    """DSV-L-01 — the search reaches the manager and only the workspace's matches come back.
    Rules: `get_departments` R1"""
    a = mk_dept()
    mk_dept(name="Marketing")
    c = mk_dept(name="Resale")
    mk_dept(workspace_id=w2.id, name="Wholesale")
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, search="ale")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(r.id for r in result) == [a.id, c.id]


# [claude] DSV-L-02
def test_dsv_l_02__with_the_defaults_101_live_departments_give_100(db, w1, mk_depts):
    """DSV-L-02 — with the defaults 101 live departments give 100.
    Rules: `get_departments` R1"""
    mk_depts([{"name": f"Dept {k:03d}"} for k in range(1, 102)])
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] DSV-L-03
def test_dsv_l_03__limit_reaches_the_manager(db, w1, mk_dept):
    """DSV-L-03 — limit reaches the manager.
    Rules: `get_departments` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_dept(name=name)
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] DSV-L-04
def test_dsv_l_04__skip_reaches_the_manager_limit_1000_takes_the_rest(db, w1, mk_dept):
    """DSV-L-04 — skip reaches the manager, limit=1000 takes the rest.
    Rules: `get_departments` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_dept(name=name)
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] DSV-L-05
def test_dsv_l_05__by_default_a_soft_deleted_department_is_left_out(db, w1, u2, mk_dept):
    """DSV-L-05 — by default a soft-deleted department is left out.
    Rules: `get_departments` R2"""
    a = mk_dept()
    mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] DSV-L-06
@pytest.mark.xfail(strict=True, reason="BUG-010: List `include_deleted` flag unreachable from the API")
def test_dsv_l_06__include_deleted_true_lists_soft_deleted_departments_too(db, w1, u2, mk_dept):
    """DSV-L-06 — include_deleted=True lists soft-deleted departments too.
    Rules: `get_departments` R2 [BUG-010]"""
    a = mk_dept()
    d = mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(r.id for r in result) == [a.id, d.id]


# [claude] DSV-L-07
def test_dsv_l_07__the_list_neither_commits_nor_rolls_back(db, w1, w2, mk_dept):
    """DSV-L-07 — the list neither commits nor rolls back.
    Rules: `get_departments` R3; TC6"""
    a = mk_dept()
    b = mk_dept(workspace_id=w2.id, name="Ops")
    commit_point(db)
    p = mk_dept(name="Pending")
    b.name = "Edited"
    result = svc.get_departments(db, workspace_id=w1.id)

    # Then 1
    assert sorted(r.id for r in result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_depts(db, name="Pending") == 0
    # Then 5
    assert reread(db, b).name == "Ops"


# [claude] DSV-L-08
@pytest.mark.xfail(strict=False, reason="BUG-006: Department list drops deleted rows after paging")
def test_dsv_l_08__pass_through_bug_006_deleted_rows_take_no_place_in_the_page(db, w1, u2, mk_dept):
    """DSV-L-08 — pass-through BUG-006: deleted rows take no place in the page.
    Rules: `get_departments` R1 [BUG-006]"""
    mk_dept(name="Old A", **gone(u2))
    mk_dept(name="Old B", **gone(u2))
    mk_dept(name="Old C", **gone(u2))
    a = mk_dept(name="Ops")
    b = mk_dept()
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(r.id for r in result) == [a.id, b.id]


# [claude] DSV-L-09
@pytest.mark.xfail(strict=False, reason="BUG-007: Department name search only searches the current page")
def test_dsv_l_09__pass_through_bug_007_the_search_covers_the_whole_workspace_not_the_page(db, w1, mk_dept):
    """DSV-L-09 — pass-through BUG-007: the search covers the whole workspace, not the page.
    Rules: `get_departments` R1 [BUG-007]"""
    mk_dept(name="Accounts")
    mk_dept(name="Budget")
    mk_dept(name="Customs")
    a = mk_dept(name="Warehouse")
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id, search="ware", limit=2)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] DSV-L-10
@pytest.mark.xfail(strict=False, reason="BUG-008: Department list has no sort order")
def test_dsv_l_10__pass_through_bug_008_names_come_case_insensitive_ascending(db, w1, mk_dept):
    """DSV-L-10 — pass-through BUG-008: names come case-insensitive ascending.
    Rules: `get_departments` R1 [BUG-008]"""
    mk_dept()
    mk_dept(name="accounting")
    mk_dept(name="HR")
    mk_dept(name="beta")
    commit_point(db)
    result = svc.get_departments(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert [r.name for r in result] == ["accounting", "beta", "HR", "Sales"]


# --------------------------------------------------------------------------- #
# DepartmentService.update_department
# --------------------------------------------------------------------------- #

# [claude] DSV-U-01
def test_dsv_u_01__a_rename_is_committed_and_returned_re_read_with_updated_at(db, w1, u1, u2, mk_dept):
    """DSV-U-01 — a rename is committed and returned re-read with updated_at.
    Rules: `update_department` R1, Returns; TC1, TC2"""
    a = mk_dept(name="Ops")
    commit_point(db)
    result = svc.update_department(
        db, department_id=a.id, department_in=DepartmentUpdate(name="Operations"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Operations"
    assert result.updated_by == u1.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.name == "Operations"
    assert row.updated_by == u1.id
    assert row.updated_at is not None
    # Then 5
    row = reread(db, a)
    assert row.created_by == u2.id
    assert row.is_deleted is False


# [claude] DSV-U-02
def test_dsv_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u1, mk_dept,
):
    """DSV-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_department` R2, Errors; TC3"""
    mk_dept()
    z = mk_dept(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_dept(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_department(
            db, department_id=z.id, department_in=DepartmentUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Department with ID {z.id} not found"
    # Then 4
    assert count_depts(db, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] DSV-U-03
def test_dsv_u_03__a_deleted_department_the_400_passes_unchanged_nothing_saved(db, w1, u1, u2, mk_dept):
    """DSV-U-03 — a deleted department: the 400 passes unchanged, nothing saved.
    Rules: `update_department` R2, Errors"""
    a = mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_department(
            db, department_id=a.id, department_in=DepartmentUpdate(name="Revived"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted department"
    # Then 4
    assert snap(db, a) == before_a


# [claude] DSV-U-04
def test_dsv_u_04__a_name_taken_the_409_passes_unchanged_nothing_saved(db, w1, u1, mk_dept):
    """DSV-U-04 — a name taken: the 409 passes unchanged, nothing saved.
    Rules: `update_department` R2, Errors"""
    mk_dept()
    b = mk_dept(name="Ops")
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_department(
            db, department_id=b.id, department_in=DepartmentUpdate(name="Sales"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Department with name 'Sales' already exists"
    # Then 4
    assert snap(db, b) == before_b


# [claude] DSV-U-05
@pytest.mark.xfail(strict=True, reason="BUG-009: `updated_by` stamped on no-op updates")
def test_dsv_u_05__pass_through_bug_009_an_empty_update_does_not_stamp_updated_by(db, w1, u1, u2, mk_dept):
    """DSV-U-05 — pass-through BUG-009: an empty update does not stamp updated_by.
    Rules: `update_department` R1 [BUG-009]"""
    a = mk_dept(name="HR", updated_by=u2.id)
    commit_point(db)
    result = svc.update_department(
        db, department_id=a.id, department_in=DepartmentUpdate(), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).updated_by == u2.id


# --------------------------------------------------------------------------- #
# DepartmentService.delete_department
# --------------------------------------------------------------------------- #

# [claude] DSV-D-01
def test_dsv_d_01__a_soft_delete_is_committed_and_returned_re_read(db, w1, u1, mk_dept):
    """DSV-D-01 — a soft delete is committed and returned re-read.
    Rules: `delete_department` R1, Returns; TC1, TC2"""
    a = mk_dept(name="Ops")
    commit_point(db)
    result = svc.delete_department(db, department_id=a.id, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert "is_deleted" not in unloaded(result)
    assert "deleted_at" not in unloaded(result)
    assert "deleted_by" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.is_deleted is True
    assert result.deleted_by == u1.id
    assert result.deleted_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u1.id
    assert row.deleted_at is not None
    # Then 5
    assert reread(db, a).name == "Ops"


# [claude] DSV-D-02
def test_dsv_d_02__an_already_deleted_department_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, u2, mk_dept,
):
    """DSV-D-02 — an already deleted department: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_department` R2, Errors; TC3"""
    a = mk_dept(name="Legacy", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    mk_dept(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_department(db, department_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Department is already deleted"
    # Then 4
    assert count_depts(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] DSV-D-03
def test_dsv_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u1, mk_dept):
    """DSV-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_department` R2, Errors"""
    a = mk_dept()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_department(db, department_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Department with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a
