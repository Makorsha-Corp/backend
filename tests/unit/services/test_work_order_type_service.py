"""Unit tests for app/services/work_order_type_service.py.

Implements tests/unit/services/work_order_type_service.cases.md (revision 1),
one test per case, in card order. Real Postgres session (`db` fixture): a
`commit()` only releases a savepoint, so the service's commits are safe and the
fixture's outer rollback discards everything. Nothing is patched except the
failing commit / failing refresh wraps that Conventions name.

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

from app.models.work_order_type import WorkOrderType
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate
from app.services.work_order_type_service import work_order_type_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton work_order_type_service"
svc = work_order_type_service

# Convention "MISSING"
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# Conventions -> actors: W1, W2, U1, U2 exist in every test
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


@pytest.fixture(autouse=True)
def actors(u2):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "gone" (after "but")
def gone(u2):
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": u2.id}


def _type_fields(w1, u2, but):
    fields = {"workspace_id": w1.id, "name": "Repair", "created_by": u2.id}
    fields.update(but)
    return fields


# Convention "type": one row, flushed
@pytest.fixture
def mk_type(db, w1, u2):
    def _mk(**but):
        row = WorkOrderType(**_type_fields(w1, u2, but))
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "n rows, by add_all"
@pytest.fixture
def mk_types(db, w1, u2):
    def _mk(list_of_but):
        rows = [WorkOrderType(**_type_fields(w1, u2, but)) for but in list_of_but]
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
    return db.execute(select(WorkOrderType).where(WorkOrderType.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = WorkOrderType.__table__
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


# Convention "count:" lines: work_order_types rows (all workspaces), with the filter stated
def count_types(db, **filters):
    query = select(func.count()).select_from(WorkOrderType)
    for column, value in filters.items():
        query = query.where(getattr(WorkOrderType, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_types(db)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# WorkOrderTypeService.create_work_order_type
# --------------------------------------------------------------------------- #

# [claude] WSV-C-01
def test_wsv_c_01__a_new_type_is_committed_and_returned_re_read(db, w1, u1):
    """WSV-C-01 — a new type is committed and returned re-read.
    Rules: `create_work_order_type` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    assert "created_by" not in unloaded(result)
    # Then 2
    assert isinstance(result, WorkOrderType)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.name == "Repair"
    assert result.workspace_id == w1.id
    assert result.created_by == u1.id
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(WorkOrderType).where(WorkOrderType.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "Repair"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False
    # Then 6
    assert count_types(db, workspace_id=w1.id) == 1


# [claude] WSV-C-02
def test_wsv_c_02__a_live_duplicate_the_managers_409_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, mk_type,
):
    """WSV-C-02 — a live duplicate: the manager's 409 passes unchanged and the session is rolled back.
    Rules: `create_work_order_type` R2, Errors; TC3"""
    a = mk_type()
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_type(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'Repair' already exists"
    # Then 4
    assert count_types(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] WSV-C-03
def test_wsv_c_03__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u1):
    """WSV-C-03 — a failing commit is rolled back and re-raised.
    Rules: `create_work_order_type` R4; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_work_order_type(
                db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_types(db, workspace_id=w1.id) == 0


# [claude] WSV-C-04
def test_wsv_c_04__a_failing_re_read_after_the_commit_leaves_the_type_saved(db, w1, u1):
    """WSV-C-04 — a failing re-read after the commit leaves the type saved.
    Rules: `create_work_order_type` R4; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_work_order_type(
                db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_types(db, workspace_id=w1.id) == 1
    # Then 3
    db.expire_all()
    row = db.execute(select(WorkOrderType).where(WorkOrderType.workspace_id == w1.id)).scalar_one()
    assert row.name == "Repair"
    assert row.created_by == u1.id


# [claude] WSV-C-05
@pytest.mark.xfail(strict=True, reason="BUG-1214: A deleted work order type's name cannot be used again")
def test_wsv_c_05__pass_through_bug_1214_a_deleted_types_name_can_be_used_again(db, w1, u1, u2, mk_type):
    """WSV-C-05 — pass-through BUG-1214: a deleted type's name can be used again.
    Rules: `create_work_order_type` R3 [BUG-1214]"""
    a = mk_type(**gone(u2))
    commit_point(db)
    result = svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id != a.id
    # Then 2
    assert result.name == "Repair"
    assert result.is_deleted is False
    # Then 3
    db.rollback()
    assert count_types(db, workspace_id=w1.id, name="Repair") == 2
    # Then 4
    assert reread(db, a).is_deleted is True


# [claude] WSV-C-06
def test_wsv_c_06__a_database_error_at_the_flush_passes_unchanged_and_nothing_is_saved(db, w1, mk_type):
    """WSV-C-06 — a database error at the flush passes unchanged and nothing is saved.
    Rules: `create_work_order_type` Errors; TC3"""
    mk_type(name="Inspection")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_types(db, name="Repair") == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# --------------------------------------------------------------------------- #
# WorkOrderTypeService.get_work_order_type
# --------------------------------------------------------------------------- #

# [claude] WSV-G-01
def test_wsv_g_01__a_live_type_of_the_workspace_is_returned(db, w1, w2, mk_type):
    """WSV-G-01 — a live type of the workspace is returned.
    Rules: `get_work_order_type` R1"""
    mk_type(workspace_id=w2.id, name="Far")
    a = mk_type()
    commit_point(db)
    result = svc.get_work_order_type(db, type_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, WorkOrderType)
    # Then 2
    assert result.id == a.id
    assert result.name == "Repair"


# [claude] WSV-G-02
def test_wsv_g_02__another_workspaces_id_the_404_passes_unchanged(db, w1, w2, mk_type):
    """WSV-G-02 — another workspace's id: the 404 passes unchanged.
    Rules: `get_work_order_type` R4, Errors"""
    mk_type()
    z = mk_type(workspace_id=w2.id, name="Far")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order_type(db, type_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"


# [claude] WSV-G-03
def test_wsv_g_03__id_0_gets_the_404(db, w1, mk_type):
    """WSV-G-03 — id 0 gets the 404.
    Rules: `get_work_order_type` R4, Errors"""
    mk_type()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order_type(db, type_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 0 not found"


# [claude] WSV-G-04
@pytest.mark.xfail(strict=True, reason="BUG-1521: A deleted work order type is returned by id")
def test_wsv_g_04__a_soft_deleted_type_is_hidden_by_default(db, w1, u2, mk_type):
    """WSV-G-04 — a soft-deleted type is hidden by default.
    Rules: `get_work_order_type` R2 [BUG-1521], Errors"""
    a = mk_type(**gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order_type(db, type_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {a.id} not found"


# [claude] WSV-G-05
@pytest.mark.xfail(strict=True, reason="BUG-1521: A deleted work order type is returned by id")
def test_wsv_g_05__include_deleted_true_returns_a_soft_deleted_type(db, w1, u2, mk_type):
    """WSV-G-05 — include_deleted=True returns a soft-deleted type.
    Rules: `get_work_order_type` R3 [BUG-1521]"""
    a = mk_type(**gone(u2))
    commit_point(db)
    result = svc.get_work_order_type(db, type_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] WSV-G-06
@pytest.mark.xfail(strict=True, reason="BUG-1521: A deleted work order type is returned by id")
def test_wsv_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, w2, u2, mk_type):
    """WSV-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_work_order_type` R3 [BUG-1521], Errors"""
    z = mk_type(workspace_id=w2.id, name="Far", **gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_work_order_type(db, type_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"


# [claude] WSV-G-07
def test_wsv_g_07__the_read_neither_commits_nor_rolls_back(db, w1, mk_type):
    """WSV-G-07 — the read neither commits nor rolls back.
    Rules: `get_work_order_type` R5; TC6"""
    a = mk_type()
    b = mk_type(name="Inspection")
    commit_point(db)
    mk_type(name="Pending")
    b.name = "Edited"
    result = svc.get_work_order_type(db, type_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_types(db, name="Pending") == 1
    # Then 5
    db.rollback()
    assert count_types(db, name="Pending") == 0
    # Then 6
    assert reread(db, b).name == "Inspection"


# --------------------------------------------------------------------------- #
# WorkOrderTypeService.get_work_order_types
# --------------------------------------------------------------------------- #

# [claude] WSV-L-01
def test_wsv_l_01__the_search_reaches_the_manager_and_only_the_workspaces_match_comes_back(
    db, w1, w2, mk_type,
):
    """WSV-L-01 — the search reaches the manager and only the workspace's match comes back.
    Rules: `get_work_order_types` R1"""
    a = mk_type()
    mk_type(name="Inspection")
    mk_type(workspace_id=w2.id)
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id, search="Repair")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert [r.id for r in result] == [a.id]


# [claude] WSV-L-02
def test_wsv_l_02__with_the_defaults_101_live_types_give_100(db, w1, mk_types):
    """WSV-L-02 — with the defaults 101 live types give 100.
    Rules: `get_work_order_types` R1"""
    mk_types([{"name": f"Kind {k:03d}"} for k in range(1, 102)])
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] WSV-L-03
def test_wsv_l_03__limit_reaches_the_manager(db, w1, mk_type):
    """WSV-L-03 — limit reaches the manager.
    Rules: `get_work_order_types` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_type(name=name)
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] WSV-L-04
def test_wsv_l_04__skip_reaches_the_manager_limit_1000_takes_the_rest(db, w1, mk_type):
    """WSV-L-04 — skip reaches the manager, limit=1000 takes the rest.
    Rules: `get_work_order_types` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_type(name=name)
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] WSV-L-05
def test_wsv_l_05__by_default_a_soft_deleted_type_is_left_out(db, w1, u2, mk_type):
    """WSV-L-05 — by default a soft-deleted type is left out.
    Rules: `get_work_order_types` R2"""
    a = mk_type()
    mk_type(name="Old Kind", **gone(u2))
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] WSV-L-06
@pytest.mark.xfail(strict=True, reason="BUG-1520: Deleted work order types cannot be listed through the API")
def test_wsv_l_06__include_deleted_true_lists_soft_deleted_types_too(db, w1, u2, mk_type):
    """WSV-L-06 — include_deleted=True lists soft-deleted types too.
    Rules: `get_work_order_types` R2 [BUG-1520]"""
    a = mk_type()
    d = mk_type(name="Old Kind", **gone(u2))
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(r.id for r in result) == [a.id, d.id]


# [claude] WSV-L-07
def test_wsv_l_07__the_list_neither_commits_nor_rolls_back(db, w1, w2, mk_type):
    """WSV-L-07 — the list neither commits nor rolls back.
    Rules: `get_work_order_types` R3; TC6"""
    a = mk_type()
    b = mk_type(workspace_id=w2.id, name="Inspection")
    commit_point(db)
    p = mk_type(name="Pending")
    b.name = "Edited"
    result = svc.get_work_order_types(db, workspace_id=w1.id)

    # Then 1
    assert sorted(r.id for r in result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_types(db, name="Pending") == 0
    # Then 5
    assert reread(db, b).name == "Inspection"


# [claude] WSV-L-08
def test_wsv_l_08__a_case_insensitive_part_of_the_name_reaches_the_manager_as_the_search(db, w1, mk_type):
    """WSV-L-08 — a case-insensitive part of the name reaches the manager as the search.
    Rules: `get_work_order_types` R1"""
    a = mk_type()
    mk_type(name="Inspection")
    commit_point(db)
    result = svc.get_work_order_types(db, workspace_id=w1.id, search="PAIR")

    # Then 1
    assert [r.id for r in result] == [a.id]


# --------------------------------------------------------------------------- #
# WorkOrderTypeService.update_work_order_type
# --------------------------------------------------------------------------- #

# [claude] WSV-U-01
def test_wsv_u_01__a_rename_is_committed_and_returned_re_read_with_updated_at(db, w1, u1, mk_type):
    """WSV-U-01 — a rename is committed and returned re-read with updated_at.
    Rules: `update_work_order_type` R1, Returns; TC1, TC2"""
    a = mk_type()
    commit_point(db)
    result = svc.update_work_order_type(
        db, type_id=a.id, type_in=WorkOrderTypeUpdate(name="Overhaul"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Overhaul"
    assert result.updated_by == u1.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.name == "Overhaul"
    assert row.updated_by == u1.id
    assert row.updated_at is not None


# [claude] WSV-U-02
def test_wsv_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u1, mk_type,
):
    """WSV-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_work_order_type` R2, Errors; TC3"""
    mk_type()
    z = mk_type(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_type(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_work_order_type(
            db, type_id=z.id, type_in=WorkOrderTypeUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Work order type with ID {z.id} not found"
    # Then 4
    assert count_types(db, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before


# [claude] WSV-U-03
def test_wsv_u_03__a_deleted_type_the_400_passes_unchanged_nothing_saved(db, w1, u1, u2, mk_type):
    """WSV-U-03 — a deleted type: the 400 passes unchanged, nothing saved.
    Rules: `update_work_order_type` R2, Errors"""
    a = mk_type(**gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_work_order_type(
            db, type_id=a.id, type_in=WorkOrderTypeUpdate(name="Revived"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted work order type"
    # Then 4
    assert snap(db, a) == before_a


# [claude] WSV-U-04
def test_wsv_u_04__a_name_taken_the_409_passes_unchanged_nothing_saved(db, w1, u1, mk_type):
    """WSV-U-04 — a name taken: the 409 passes unchanged, nothing saved.
    Rules: `update_work_order_type` R2, Errors"""
    mk_type()
    b = mk_type(name="Inspection")
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_work_order_type(
            db, type_id=b.id, type_in=WorkOrderTypeUpdate(name="Repair"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Work order type 'Repair' already exists"
    # Then 4
    assert snap(db, b) == before_b


# --------------------------------------------------------------------------- #
# WorkOrderTypeService.delete_work_order_type
# --------------------------------------------------------------------------- #

# [claude] WSV-D-01
def test_wsv_d_01__a_soft_delete_is_committed_and_returned_re_read(db, w1, u1, mk_type):
    """WSV-D-01 — a soft delete is committed and returned re-read.
    Rules: `delete_work_order_type` R1, Returns; TC1, TC2"""
    a = mk_type()
    commit_point(db)
    result = svc.delete_work_order_type(db, type_id=a.id, workspace_id=w1.id, user_id=u1.id)

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


# [claude] WSV-D-02
def test_wsv_d_02__an_already_deleted_type_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, u2, mk_type,
):
    """WSV-D-02 — an already deleted type: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_work_order_type` R2, Errors; TC3"""
    a = mk_type(**gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    mk_type(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_work_order_type(db, type_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Work order type is already deleted"
    # Then 4
    assert count_types(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] WSV-D-03
def test_wsv_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u1, mk_type):
    """WSV-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_work_order_type` R2, Errors"""
    a = mk_type()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_work_order_type(db, type_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Work order type with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a
