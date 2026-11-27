"""Unit tests for app/services/delivery_method_service.py.

Implements tests/unit/services/delivery_method_service.cases.md (revision 1),
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

from app.models.delivery_method import DeliveryMethod
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate
from app.services.delivery_method_service import delivery_method_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton delivery_method_service"
svc = delivery_method_service

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


def _method_fields(w1, u2, but):
    fields = {"workspace_id": w1.id, "name": "Courier", "created_by": u2.id}
    fields.update(but)
    return fields


# Convention "method": one row, flushed
@pytest.fixture
def mk_method(db, w1, u2):
    def _mk(**but):
        row = DeliveryMethod(**_method_fields(w1, u2, but))
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "n rows, by add_all"
@pytest.fixture
def mk_methods(db, w1, u2):
    def _mk(list_of_but):
        rows = [DeliveryMethod(**_method_fields(w1, u2, but)) for but in list_of_but]
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
    return db.execute(select(DeliveryMethod).where(DeliveryMethod.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = DeliveryMethod.__table__
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


# Convention "count:" lines: delivery_methods rows (all workspaces), with the filter stated
def count_methods(db, **filters):
    query = select(func.count()).select_from(DeliveryMethod)
    for column, value in filters.items():
        query = query.where(getattr(DeliveryMethod, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_methods(db)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# DeliveryMethodService.create_delivery_method
# --------------------------------------------------------------------------- #

# [claude] DMS-C-01
def test_dms_c_01__a_new_method_is_committed_and_returned_re_read(db, w1, u1):
    """DMS-C-01 — a new method is committed and returned re-read.
    Rules: `create_delivery_method` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    assert "created_by" not in unloaded(result)
    # Then 2
    assert isinstance(result, DeliveryMethod)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.name == "Courier"
    assert result.workspace_id == w1.id
    assert result.created_by == u1.id
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(DeliveryMethod).where(DeliveryMethod.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "Courier"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False
    # Then 6
    assert count_methods(db, workspace_id=w1.id) == 1


# [claude] DMS-C-02
def test_dms_c_02__a_live_duplicate_the_managers_409_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, mk_method,
):
    """DMS-C-02 — a live duplicate: the manager's 409 passes unchanged and the session is rolled back.
    Rules: `create_delivery_method` R2, Errors; TC3"""
    a = mk_method()
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_method(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert count_methods(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] DMS-C-03
def test_dms_c_03__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u1):
    """DMS-C-03 — a failing commit is rolled back and re-raised.
    Rules: `create_delivery_method` R4; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_delivery_method(
                db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_methods(db, workspace_id=w1.id) == 0


# [claude] DMS-C-04
def test_dms_c_04__a_failing_re_read_after_the_commit_leaves_the_method_saved(db, w1, u1):
    """DMS-C-04 — a failing re-read after the commit leaves the method saved.
    Rules: `create_delivery_method` R4; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_delivery_method(
                db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_methods(db, workspace_id=w1.id) == 1
    # Then 3
    db.expire_all()
    row = db.execute(select(DeliveryMethod).where(DeliveryMethod.workspace_id == w1.id)).scalar_one()
    assert row.name == "Courier"
    assert row.created_by == u1.id


# [claude] DMS-C-05
def test_dms_c_05__a_name_used_only_by_a_soft_deleted_method_is_accepted(db, w1, u1, u2, mk_method):
    """DMS-C-05 — a name used only by a soft-deleted method is accepted.
    Rules: `create_delivery_method` R3"""
    a = mk_method(**gone(u2))
    commit_point(db)
    result = svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id != a.id
    # Then 2
    assert result.name == "Courier"
    assert result.is_deleted is False
    # Then 3
    db.rollback()
    assert count_methods(db, workspace_id=w1.id, name="Courier") == 2
    # Then 4
    assert reread(db, a).is_deleted is True


# [claude] DMS-C-06
def test_dms_c_06__a_database_error_at_the_flush_passes_unchanged_and_nothing_is_saved(db, w1, mk_method):
    """DMS-C-06 — a database error at the flush passes unchanged and nothing is saved.
    Rules: `create_delivery_method` Errors; TC3"""
    mk_method(name="Pickup")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_methods(db, name="Courier") == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# --------------------------------------------------------------------------- #
# DeliveryMethodService.get_delivery_method
# --------------------------------------------------------------------------- #

# [claude] DMS-G-01
def test_dms_g_01__a_live_method_of_the_workspace_is_returned(db, w1, w2, mk_method):
    """DMS-G-01 — a live method of the workspace is returned.
    Rules: `get_delivery_method` R1"""
    mk_method(workspace_id=w2.id, name="Far")
    a = mk_method()
    commit_point(db)
    result = svc.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, DeliveryMethod)
    # Then 2
    assert result.id == a.id
    assert result.name == "Courier"


# [claude] DMS-G-02
def test_dms_g_02__another_workspaces_id_the_404_passes_unchanged(db, w1, w2, mk_method):
    """DMS-G-02 — another workspace's id: the 404 passes unchanged.
    Rules: `get_delivery_method` R4, Errors"""
    mk_method()
    z = mk_method(workspace_id=w2.id, name="Far")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_delivery_method(db, delivery_method_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"


# [claude] DMS-G-03
def test_dms_g_03__id_0_gets_the_404(db, w1, mk_method):
    """DMS-G-03 — id 0 gets the 404.
    Rules: `get_delivery_method` R4, Errors"""
    mk_method()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_delivery_method(db, delivery_method_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 0 not found"


# [claude] DMS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-1523: A deleted delivery method is returned by id")
def test_dms_g_04__a_soft_deleted_method_is_hidden_by_default(db, w1, u2, mk_method):
    """DMS-G-04 — a soft-deleted method is hidden by default.
    Rules: `get_delivery_method` R2 [BUG-1523], Errors"""
    a = mk_method(**gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {a.id} not found"


# [claude] DMS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-1523: A deleted delivery method is returned by id")
def test_dms_g_05__include_deleted_true_returns_a_soft_deleted_method(db, w1, u2, mk_method):
    """DMS-G-05 — include_deleted=True returns a soft-deleted method.
    Rules: `get_delivery_method` R3 [BUG-1523]"""
    a = mk_method(**gone(u2))
    commit_point(db)
    result = svc.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] DMS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-1523: A deleted delivery method is returned by id")
def test_dms_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, w2, u2, mk_method):
    """DMS-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_delivery_method` R3 [BUG-1523], Errors"""
    z = mk_method(workspace_id=w2.id, name="Far", **gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_delivery_method(db, delivery_method_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"


# [claude] DMS-G-07
def test_dms_g_07__the_read_neither_commits_nor_rolls_back(db, w1, mk_method):
    """DMS-G-07 — the read neither commits nor rolls back.
    Rules: `get_delivery_method` R5; TC6"""
    a = mk_method()
    b = mk_method(name="Pickup")
    commit_point(db)
    mk_method(name="Pending")
    b.name = "Edited"
    result = svc.get_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_methods(db, name="Pending") == 1
    # Then 5
    db.rollback()
    assert count_methods(db, name="Pending") == 0
    # Then 6
    assert reread(db, b).name == "Pickup"


# --------------------------------------------------------------------------- #
# DeliveryMethodService.get_delivery_methods
# --------------------------------------------------------------------------- #

# [claude] DMS-L-01
def test_dms_l_01__the_search_reaches_the_manager_and_only_the_workspaces_match_comes_back(
    db, w1, w2, mk_method,
):
    """DMS-L-01 — the search reaches the manager and only the workspace's match comes back.
    Rules: `get_delivery_methods` R1"""
    a = mk_method()
    mk_method(name="Pickup")
    mk_method(workspace_id=w2.id)
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id, search="Courier")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert [r.id for r in result] == [a.id]


# [claude] DMS-L-02
def test_dms_l_02__with_the_defaults_101_live_methods_give_100(db, w1, mk_methods):
    """DMS-L-02 — with the defaults 101 live methods give 100.
    Rules: `get_delivery_methods` R1"""
    mk_methods([{"name": f"Method {k:03d}"} for k in range(1, 102)])
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] DMS-L-03
def test_dms_l_03__limit_reaches_the_manager(db, w1, mk_method):
    """DMS-L-03 — limit reaches the manager.
    Rules: `get_delivery_methods` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_method(name=name)
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] DMS-L-04
def test_dms_l_04__skip_reaches_the_manager_limit_1000_takes_the_rest(db, w1, mk_method):
    """DMS-L-04 — skip reaches the manager, limit=1000 takes the rest.
    Rules: `get_delivery_methods` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_method(name=name)
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] DMS-L-05
def test_dms_l_05__by_default_a_soft_deleted_method_is_left_out(db, w1, u2, mk_method):
    """DMS-L-05 — by default a soft-deleted method is left out.
    Rules: `get_delivery_methods` R2"""
    a = mk_method()
    mk_method(name="Old Method", **gone(u2))
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] DMS-L-06
@pytest.mark.xfail(strict=True, reason="BUG-1522: Deleted delivery methods cannot be listed through the API")
def test_dms_l_06__include_deleted_true_lists_soft_deleted_methods_too(db, w1, u2, mk_method):
    """DMS-L-06 — include_deleted=True lists soft-deleted methods too.
    Rules: `get_delivery_methods` R2 [BUG-1522]"""
    a = mk_method()
    d = mk_method(name="Old Method", **gone(u2))
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert sorted(r.id for r in result) == [a.id, d.id]


# [claude] DMS-L-07
def test_dms_l_07__the_list_neither_commits_nor_rolls_back(db, w1, w2, mk_method):
    """DMS-L-07 — the list neither commits nor rolls back.
    Rules: `get_delivery_methods` R3; TC6"""
    a = mk_method()
    b = mk_method(workspace_id=w2.id, name="Pickup")
    commit_point(db)
    p = mk_method(name="Pending")
    b.name = "Edited"
    result = svc.get_delivery_methods(db, workspace_id=w1.id)

    # Then 1
    assert sorted(r.id for r in result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_methods(db, name="Pending") == 0
    # Then 5
    assert reread(db, b).name == "Pickup"


# [claude] DMS-L-08
def test_dms_l_08__a_case_insensitive_part_of_the_name_reaches_the_manager_as_the_search(db, w1, mk_method):
    """DMS-L-08 — a case-insensitive part of the name reaches the manager as the search.
    Rules: `get_delivery_methods` R1"""
    a = mk_method()
    mk_method(name="Pickup")
    commit_point(db)
    result = svc.get_delivery_methods(db, workspace_id=w1.id, search="OURI")

    # Then 1
    assert [r.id for r in result] == [a.id]


# --------------------------------------------------------------------------- #
# DeliveryMethodService.update_delivery_method
# --------------------------------------------------------------------------- #

# [claude] DMS-U-01
def test_dms_u_01__a_rename_is_committed_and_returned_re_read_with_updated_at(db, w1, u1, mk_method):
    """DMS-U-01 — a rename is committed and returned re-read with updated_at.
    Rules: `update_delivery_method` R1, Returns; TC1, TC2"""
    a = mk_method()
    commit_point(db)
    result = svc.update_delivery_method(
        db, delivery_method_id=a.id, delivery_method_in=DeliveryMethodUpdate(name="Own Fleet"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Own Fleet"
    assert result.updated_by == u1.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.name == "Own Fleet"
    assert row.updated_by == u1.id
    assert row.updated_at is not None


# [claude] DMS-U-02
def test_dms_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u1, mk_method,
):
    """DMS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_delivery_method` R2, Errors; TC3"""
    mk_method()
    z = mk_method(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_method(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_delivery_method(
            db, delivery_method_id=z.id, delivery_method_in=DeliveryMethodUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Delivery method with ID {z.id} not found"
    # Then 4
    assert count_methods(db, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before


# [claude] DMS-U-03
def test_dms_u_03__a_deleted_method_the_400_passes_unchanged_nothing_saved(db, w1, u1, u2, mk_method):
    """DMS-U-03 — a deleted method: the 400 passes unchanged, nothing saved.
    Rules: `update_delivery_method` R2, Errors"""
    a = mk_method(**gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_delivery_method(
            db, delivery_method_id=a.id, delivery_method_in=DeliveryMethodUpdate(name="Revived"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted delivery method"
    # Then 4
    assert snap(db, a) == before_a


# [claude] DMS-U-04
def test_dms_u_04__a_name_taken_the_409_passes_unchanged_nothing_saved(db, w1, u1, mk_method):
    """DMS-U-04 — a name taken: the 409 passes unchanged, nothing saved.
    Rules: `update_delivery_method` R2, Errors"""
    mk_method()
    b = mk_method(name="Pickup")
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_delivery_method(
            db, delivery_method_id=b.id, delivery_method_in=DeliveryMethodUpdate(name="Courier"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Delivery method with name 'Courier' already exists"
    # Then 4
    assert snap(db, b) == before_b


# --------------------------------------------------------------------------- #
# DeliveryMethodService.delete_delivery_method
# --------------------------------------------------------------------------- #

# [claude] DMS-D-01
def test_dms_d_01__a_soft_delete_is_committed_and_returned_re_read(db, w1, u1, mk_method):
    """DMS-D-01 — a soft delete is committed and returned re-read.
    Rules: `delete_delivery_method` R1, Returns; TC1, TC2"""
    a = mk_method()
    commit_point(db)
    result = svc.delete_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id, user_id=u1.id)

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


# [claude] DMS-D-02
def test_dms_d_02__an_already_deleted_method_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, u2, mk_method,
):
    """DMS-D-02 — an already deleted method: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_delivery_method` R2, Errors; TC3"""
    a = mk_method(**gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    mk_method(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_delivery_method(db, delivery_method_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Delivery method is already deleted"
    # Then 4
    assert count_methods(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] DMS-D-03
def test_dms_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u1, mk_method):
    """DMS-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_delivery_method` R2, Errors"""
    a = mk_method()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_delivery_method(db, delivery_method_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Delivery method with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a
