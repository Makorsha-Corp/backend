"""Unit tests for app/services/factory_service.py.

Implements tests/unit/services/factory_service.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture): a `commit()` only releases a
savepoint, so the service's commits are safe and the fixture's outer rollback
discards everything. Nothing is patched except what Conventions name: the
failing commit / failing refresh wraps, the delete patch (FAS-D-04), the create
patch (FAS-C-10) and the race simulation of FAS-C-09.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (A -> a, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ValidationError as AppValidationError
from app.models.factory import Factory
from app.models.production_batch import ProductionBatch
from app.models.production_line import ProductionLine
from app.schemas.factory import FactoryCreate, FactoryUpdate
from app.services.factory_service import factory_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton factory_service"
svc = factory_service

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001

# Convention "delete patch" (FAS-D-04)
BLOCKERS = [{"type": "production_batch", "id": 7}, {"type": "other_workspace"}]


def _add(db, row):
    db.add(row)
    db.flush()
    return row


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


def _fac_fields(w1, u2, but):
    fields = {"workspace_id": w1.id, "name": "Main Plant", "abbreviation": "MP", "created_by": u2.id}
    fields.update(but)
    return fields


# Convention "fac": one row, flushed
@pytest.fixture
def mk_fac(db, w1, u2):
    def _mk(**but):
        return _add(db, Factory(**_fac_fields(w1, u2, but)))
    return _mk


# Convention "n rows, by add_all"
@pytest.fixture
def mk_facs(db, w1, u2):
    def _mk(list_of_but):
        rows = [Factory(**_fac_fields(w1, u2, but)) for but in list_of_but]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "line of F"
@pytest.fixture
def mk_line(db, w1):
    def _mk(factory):
        return _add(db, ProductionLine(workspace_id=w1.id, factory_id=factory.id, name="Line A", is_active=True))
    return _mk


# Convention "batch on L"; the card gives `status`
@pytest.fixture
def mk_batch(db, w1):
    def _mk(line, status):
        return _add(db, ProductionBatch(
            workspace_id=w1.id, production_line_id=line.id, batch_number="BATCH-2026-001",
            batch_date=date(2026, 2, 1), status=status,
        ))
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
def reread(db, row, model=Factory):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns(db, model, row_id):
    table = model.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row, model=Factory):
    return _columns(db, model, _id_of(row))


# ... and after a re-read
def snap(db, row, model=Factory):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, model, row_id)


# Convention "count:" lines: factories rows (all workspaces), with the filter stated
def count_facs(db, **filters):
    query = select(func.count()).select_from(Factory)
    for column, value in filters.items():
        query = query.where(getattr(Factory, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written": factories, production_lines, production_batches (all workspaces)
def written(db):
    return {
        model.__tablename__: db.execute(select(func.count()).select_from(model)).scalar_one()
        for model in (Factory, ProductionLine, ProductionBatch)
    }


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


FIVE = [("Alpha", "AL"), ("Bravo", "BR"), ("Charlie", "CH"), ("Delta", "DL"), ("Echo", "EC")]


# --------------------------------------------------------------------------- #
# FactoryService.create_factory
# --------------------------------------------------------------------------- #

# [claude] FAS-C-01
def test_fas_c_01__a_new_factory_is_committed_and_returned_re_read(db, w1, u1):
    """FAS-C-01 — a new factory is committed and returned re-read.
    Rules: `create_factory` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_factory(
        db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "abbreviation" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    assert "created_by" not in unloaded(result)
    # Then 2
    assert isinstance(result, Factory)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.name == "Main Plant"
    assert result.abbreviation == "MP"
    assert result.created_by == u1.id
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(Factory).where(Factory.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False
    # Then 6
    assert count_facs(db, workspace_id=w1.id) == 1


# [claude] FAS-C-02
def test_fas_c_02__a_duplicate_name_the_managers_409_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, mk_fac,
):
    """FAS-C-02 — a duplicate name: the manager's 409 passes unchanged and the session is rolled back.
    Rules: `create_factory` R2, Errors row 1; TC3"""
    a = mk_fac()
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_fac(name="Extra", abbreviation="EX")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory(
            db, factory_in=FactoryCreate(name="Main Plant", abbreviation="NP"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert count_facs(db, name="Extra") == 0
    # Then 5
    assert count_facs(db, workspace_id=w1.id, name="Main Plant") == 1
    # Then 6
    assert written(db) == before
    # Then 7
    assert snap(db, a) == before_a
    # Then 8
    assert usable(db)


# [claude] FAS-C-03
def test_fas_c_03__a_database_error_at_the_flush_passes_unchanged_and_nothing_is_saved(db, w1, mk_fac):
    """FAS-C-03 — a database error at the flush passes unchanged and nothing is saved.
    Rules: `create_factory` Errors row 2; TC3"""
    mk_fac(name="Ops Yard", abbreviation="OY")
    commit_point(db)
    before = written(db)
    mk_fac(name="Extra", abbreviation="EX")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_factory(
            db, factory_in=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=w1.id, user_id=MISSING,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_facs(db, name="North Yard") == 0
    # Then 4
    assert count_facs(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] FAS-C-04
def test_fas_c_04__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u1):
    """FAS-C-04 — a failing commit is rolled back and re-raised.
    Rules: `create_factory` R3; TC4"""
    commit_point(db)
    before = written(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_factory(
                db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_facs(db, workspace_id=w1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] FAS-C-05
def test_fas_c_05__a_failing_re_read_after_the_commit_leaves_the_factory_saved(db, w1, u1):
    """FAS-C-05 — a failing re-read after the commit leaves the factory saved.
    Rules: `create_factory` R3; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_factory(
                db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_facs(db, workspace_id=w1.id) == 1
    # Then 3
    db.expire_all()
    row = db.execute(select(Factory).where(Factory.workspace_id == w1.id)).scalar_one()
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    assert row.created_by == u1.id


# [claude] FAS-C-06
@pytest.mark.xfail(
    strict=True,
    reason="BUG-896: Blank / whitespace-only factory names and abbreviations accepted; values stored untrimmed",
)
def test_fas_c_06__pass_through_bug_896_a_padded_name_is_stored_trimmed(db, w1, u1):
    """FAS-C-06 — pass-through BUG-896: a padded name is stored trimmed.
    Rules: `create_factory` R1 [BUG-896]"""
    commit_point(db)
    data = FactoryCreate(name=" Main Plant ", abbreviation="MP")
    result = svc.create_factory(db, factory_in=data, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(Factory).where(Factory.id == result_id)).scalar_one()
    assert row.name == "Main Plant"


# [claude] FAS-C-07
@pytest.mark.xfail(strict=True, reason="BUG-894: Factory duplicate checks are case- and whitespace-sensitive")
def test_fas_c_07__pass_through_bug_894_a_name_in_another_case_is_refused_with_the_submitted_name(
    db, w1, u1, mk_fac,
):
    """FAS-C-07 — pass-through BUG-894: a name in another case is refused with the submitted name.
    Rules: `create_factory` R1, R2 [BUG-894]"""
    a = mk_fac()
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory(
            db, factory_in=FactoryCreate(name="main plant", abbreviation="MX"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'main plant' already exists"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a) == before_a


# [claude] FAS-C-08
@pytest.mark.xfail(strict=False, reason="BUG-893: Duplicate name / abbreviation checks only scan the first 100 factories")
def test_fas_c_08__pass_through_bug_893_a_duplicate_behind_100_deleted_rows_is_still_refused(
    db, w1, u1, u2, mk_fac, mk_facs,
):
    """FAS-C-08 — pass-through BUG-893: a duplicate behind 100 deleted rows is still refused.
    Rules: `create_factory` R1, R2 [BUG-893]"""
    mk_facs([{"name": f"Old {k:03d}", "abbreviation": f"O{k:03d}", **gone(u2)} for k in range(1, 101)])
    mk_fac(name="Late", abbreviation="LT")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory(
            db, factory_in=FactoryCreate(name="Late", abbreviation="LX"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Late' already exists"
    # Then 4
    assert count_facs(db, workspace_id=w1.id, name="Late") == 1
    # Then 5
    assert count_facs(db, workspace_id=w1.id) == 101


# [claude] FAS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-895: Factory name / abbreviation uniqueness not enforced by the database")
def test_fas_c_09__pass_through_bug_895_a_create_that_loses_the_race_gets_the_409_nothing_saved(
    db, w1, u1, mk_fac,
):
    """FAS-C-09 — pass-through BUG-895: a create that loses the race gets the 409, nothing saved.
    Rules: `create_factory` R2 [BUG-895]"""
    mk_fac()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.factory_manager, "_check_name_exists", return_value=False):
            svc.create_factory(
                db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert count_facs(db, workspace_id=w1.id, name="Main Plant") == 1
    # Then 5
    assert usable(db)


# [claude] FAS-C-10
def test_fas_c_10__a_valueerror_from_create_is_not_translated_only_delete_translates(db, w1, u1, mk_fac):
    """FAS-C-10 — a ValueError from create is not translated: only delete translates.
    Rules: `create_factory` R2; `delete_factory` R3"""
    mk_fac()
    commit_point(db)
    before = written(db)
    mk_fac(name="Extra", abbreviation="EX")
    with pytest.raises(ValueError) as exc:
        with patch.object(svc.factory_manager, "create_factory", side_effect=ValueError("x", [])):
            svc.create_factory(
                db, factory_in=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 1
    assert type(exc.value) is ValueError
    # Then 2
    assert exc.value.args == ("x", [])
    # Then 3
    assert count_facs(db, name="Extra") == 0
    # Then 4
    assert written(db) == before


# --------------------------------------------------------------------------- #
# FactoryService.get_factory
# --------------------------------------------------------------------------- #

# [claude] FAS-G-01
def test_fas_g_01__a_live_factory_of_the_workspace_is_returned(db, w1, w2, mk_fac):
    """FAS-G-01 — a live factory of the workspace is returned.
    Rules: `get_factory` R1"""
    mk_fac(workspace_id=w2.id, name="Far Depot", abbreviation="FD")
    a = mk_fac()
    commit_point(db)
    result = svc.get_factory(db, factory_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Factory)
    # Then 2
    assert result.id == a.id
    assert result.name == "Main Plant"
    assert result.workspace_id == w1.id


# [claude] FAS-G-02
def test_fas_g_02__another_workspaces_id_the_managers_404_passes_unchanged(db, w1, w2, mk_fac):
    """FAS-G-02 — another workspace's id: the manager's 404 passes unchanged.
    Rules: `get_factory` R4, Errors row 1"""
    mk_fac()
    z = mk_fac(workspace_id=w2.id, name="Far Depot", abbreviation="FD")
    commit_point(db)
    before_z = snap_before(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory(db, factory_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {z.id} not found"
    # Then 4
    assert snap(db, z) == before_z


# [claude] FAS-G-03
def test_fas_g_03__id_0_gets_the_404(db, w1, mk_fac):
    """FAS-G-03 — id 0 gets the 404.
    Rules: `get_factory` R4, Errors row 1"""
    mk_fac()
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory(db, factory_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"


# [claude] FAS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-897: `get_factory` returns soft-deleted factories")
def test_fas_g_04__a_soft_deleted_factory_is_hidden_by_default(db, w1, u2, mk_fac):
    """FAS-G-04 — a soft-deleted factory is hidden by default.
    Rules: `get_factory` R2 [BUG-897], Errors row 1"""
    a = mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory(db, factory_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FAS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-897: `get_factory` returns soft-deleted factories")
def test_fas_g_05__include_deleted_true_returns_a_soft_deleted_factory(db, w1, u2, mk_fac):
    """FAS-G-05 — include_deleted=True returns a soft-deleted factory.
    Rules: `get_factory` R3 [BUG-897]"""
    a = mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    result = svc.get_factory(db, factory_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True
    assert result.name == "Old Plant"


# [claude] FAS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-897: `get_factory` returns soft-deleted factories")
def test_fas_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, w2, u2, mk_fac):
    """FAS-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_factory` R3 [BUG-897], Errors row 1"""
    z = mk_fac(workspace_id=w2.id, name="Far Depot", abbreviation="FD", **gone(u2))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory(db, factory_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {z.id} not found"


# [claude] FAS-G-07
def test_fas_g_07__the_read_neither_commits_nor_rolls_back(db, w1, mk_fac):
    """FAS-G-07 — the read neither commits nor rolls back.
    Rules: `get_factory` R5; TC6"""
    a = mk_fac()
    b = mk_fac(name="North Yard", abbreviation="NY")
    commit_point(db)
    mk_fac(name="Pending", abbreviation="PD")
    b.name = "Edited"
    result = svc.get_factory(db, factory_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_facs(db, name="Pending") == 1
    # Then 5
    db.rollback()
    assert count_facs(db, name="Pending") == 0
    # Then 6
    assert reread(db, b).name == "North Yard"


# --------------------------------------------------------------------------- #
# FactoryService.get_factories
# --------------------------------------------------------------------------- #

# [claude] FAS-L-01
def test_fas_l_01__the_search_reaches_the_manager_and_only_the_workspaces_matches_come_back(
    db, w1, w2, mk_fac,
):
    """FAS-L-01 — the search reaches the manager and only the workspace's matches come back.
    Rules: `get_factories` R1"""
    a = mk_fac()
    mk_fac(name="North Yard", abbreviation="NY")
    c = mk_fac(name="Plant Two", abbreviation="PT")
    mk_fac(workspace_id=w2.id, name="Far Plant", abbreviation="FP")
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, search="plant")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, c.id]


# [claude] FAS-L-02
def test_fas_l_02__with_the_defaults_101_live_factories_give_100(db, w1, mk_facs):
    """FAS-L-02 — with the defaults 101 live factories give 100.
    Rules: `get_factories` R1"""
    mk_facs([{"name": f"Plant {k:03d}", "abbreviation": f"P{k:03d}"} for k in range(1, 102)])
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] FAS-L-03
def test_fas_l_03__limit_reaches_the_manager(db, w1, mk_fac):
    """FAS-L-03 — limit reaches the manager.
    Rules: `get_factories` R1"""
    for name, abbreviation in FIVE:
        mk_fac(name=name, abbreviation=abbreviation)
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] FAS-L-04
def test_fas_l_04__skip_reaches_the_manager_limit_1000_takes_the_rest(db, w1, mk_fac):
    """FAS-L-04 — skip reaches the manager, limit=1000 takes the rest.
    Rules: `get_factories` R1"""
    for name, abbreviation in FIVE:
        mk_fac(name=name, abbreviation=abbreviation)
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] FAS-L-05
def test_fas_l_05__by_default_a_soft_deleted_factory_is_left_out(db, w1, u2, mk_fac):
    """FAS-L-05 — by default a soft-deleted factory is left out.
    Rules: `get_factories` R2"""
    a = mk_fac()
    mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] FAS-L-06
@pytest.mark.xfail(strict=True, reason="BUG-901: Factory list `include_deleted` flag unreachable from the API")
def test_fas_l_06__include_deleted_true_lists_soft_deleted_factories_too(db, w1, u2, mk_fac):
    """FAS-L-06 — include_deleted=True lists soft-deleted factories too.
    Rules: `get_factories` R2 [BUG-901]"""
    a = mk_fac()
    d = mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [a.id, d.id]


# [claude] FAS-L-07
def test_fas_l_07__the_list_neither_commits_nor_rolls_back(db, w1, w2, mk_fac):
    """FAS-L-07 — the list neither commits nor rolls back.
    Rules: `get_factories` R3; TC6"""
    a = mk_fac()
    b = mk_fac(workspace_id=w2.id, name="North Yard", abbreviation="NY")
    commit_point(db)
    p = mk_fac(name="Pending", abbreviation="PD")
    b.name = "Edited"
    result = svc.get_factories(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_facs(db, name="Pending") == 0
    # Then 5
    assert reread(db, b).name == "North Yard"


# [claude] FAS-L-08
@pytest.mark.xfail(strict=False, reason="BUG-898: Factory list drops deleted rows and applies the search after paging")
def test_fas_l_08__pass_through_bug_898_deleted_rows_take_no_place_in_the_page(db, w1, u2, mk_fac):
    """FAS-L-08 — pass-through BUG-898: deleted rows take no place in the page.
    Rules: `get_factories` R1 [BUG-898]"""
    mk_fac(name="Old A", abbreviation="OA", **gone(u2))
    mk_fac(name="Old B", abbreviation="OB", **gone(u2))
    mk_fac(name="Old C", abbreviation="OC", **gone(u2))
    a = mk_fac(name="North Yard", abbreviation="NY")
    b = mk_fac()
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] FAS-L-09
@pytest.mark.xfail(strict=False, reason="BUG-899: Factory list has no sort order")
def test_fas_l_09__pass_through_bug_899_names_come_case_insensitive_ascending(db, w1, mk_fac):
    """FAS-L-09 — pass-through BUG-899: names come case-insensitive ascending.
    Rules: `get_factories` R1 [BUG-899]"""
    mk_fac(name="Delta", abbreviation="DL")
    mk_fac(name="alpha", abbreviation="AL")
    mk_fac(name="echo", abbreviation="EC")
    mk_fac(name="Bravo", abbreviation="BR")
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert [r.name for r in result] == ["alpha", "Bravo", "Delta", "echo"]


# [claude] FAS-L-10
@pytest.mark.xfail(strict=True, reason="BUG-902: Factory search text is not trimmed")
def test_fas_l_10__pass_through_bug_902_a_search_of_only_spaces_applies_no_filter(db, w1, mk_fac):
    """FAS-L-10 — pass-through BUG-902: a search of only spaces applies no filter.
    Rules: `get_factories` R1 [BUG-902]"""
    a = mk_fac()
    b = mk_fac(name="Camp Site", abbreviation="CS")
    c = mk_fac(name="North Yard", abbreviation="NY")
    commit_point(db)
    result = svc.get_factories(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]


# --------------------------------------------------------------------------- #
# FactoryService.update_factory
# --------------------------------------------------------------------------- #

# [claude] FAS-U-01
def test_fas_u_01__a_rename_is_committed_and_returned_re_read_with_updated_at(db, w1, u1, u2, mk_fac):
    """FAS-U-01 — a rename is committed and returned re-read with updated_at.
    Rules: `update_factory` R1, Returns; TC1, TC2"""
    a = mk_fac(name="Ops Yard", abbreviation="OY")
    commit_point(db)
    result = svc.update_factory(
        db, factory_id=a.id, factory_in=FactoryUpdate(name="Operations Yard"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Operations Yard"
    assert result.updated_by == u1.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.name == "Operations Yard"
    assert row.updated_by == u1.id
    assert row.updated_at is not None
    # Then 5
    row = reread(db, a)
    assert row.abbreviation == "OY"
    assert row.created_by == u2.id
    assert row.is_deleted is False


# [claude] FAS-U-02
def test_fas_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u1, mk_fac,
):
    """FAS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_factory` R2, Errors; TC3"""
    mk_fac()
    z = mk_fac(workspace_id=w2.id, name="Far Depot", abbreviation="FD")
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_fac(name="Extra", abbreviation="EX")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory(
            db, factory_id=z.id, factory_in=FactoryUpdate(name="Hacked"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory with ID {z.id} not found"
    # Then 4
    assert count_facs(db, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] FAS-U-03
def test_fas_u_03__a_deleted_factory_the_400_passes_unchanged_nothing_saved(db, w1, u1, u2, mk_fac):
    """FAS-U-03 — a deleted factory: the 400 passes unchanged, nothing saved.
    Rules: `update_factory` R2, Errors"""
    a = mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory(
            db, factory_id=a.id, factory_in=FactoryUpdate(name="Revived"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FAS-U-04
def test_fas_u_04__a_name_taken_the_409_passes_unchanged_nothing_saved(db, w1, u1, mk_fac):
    """FAS-U-04 — a name taken: the 409 passes unchanged, nothing saved.
    Rules: `update_factory` R2, Errors"""
    mk_fac()
    b = mk_fac(name="North Yard", abbreviation="NY")
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory(
            db, factory_id=b.id, factory_in=FactoryUpdate(name="Main Plant"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Factory with name 'Main Plant' already exists"
    # Then 4
    assert snap(db, b) == before_b


# [claude] FAS-U-05
@pytest.mark.xfail(strict=True, reason="BUG-900: `updated_by` stamped on no-op factory updates")
def test_fas_u_05__pass_through_bug_900_an_empty_update_does_not_stamp_updated_by(db, w1, u1, u2, mk_fac):
    """FAS-U-05 — pass-through BUG-900: an empty update does not stamp updated_by.
    Rules: `update_factory` R1 [BUG-900]"""
    a = mk_fac(updated_by=u2.id)
    commit_point(db)
    result = svc.update_factory(db, factory_id=a.id, factory_in=FactoryUpdate(), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).updated_by == u2.id


# --------------------------------------------------------------------------- #
# FactoryService.delete_factory
# --------------------------------------------------------------------------- #

# [claude] FAS-D-01
def test_fas_d_01__a_soft_delete_is_committed_and_returned_re_read(db, w1, u1, mk_fac):
    """FAS-D-01 — a soft delete is committed and returned re-read.
    Rules: `delete_factory` R1, Returns; TC1, TC2"""
    a = mk_fac(name="Ops Yard", abbreviation="OY")
    commit_point(db)
    result = svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=u1.id)

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
    assert result.is_active is True
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u1.id
    assert row.deleted_at is not None
    # Then 5
    row = reread(db, a)
    assert row.is_active is True
    assert row.name == "Ops Yard"


# [claude] FAS-D-02
def test_fas_d_02__an_already_deleted_factory_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, u2, mk_fac,
):
    """FAS-D-02 — an already deleted factory: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_factory` R1, Errors row 2; TC3"""
    a = mk_fac(name="Old Plant", abbreviation="OP", **gone(u2))
    commit_point(db)
    before_a = snap_before(db, a)
    mk_fac(name="Extra", abbreviation="EX")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory is already deleted"
    # Then 4
    assert count_facs(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] FAS-D-03
def test_fas_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u1, mk_fac):
    """FAS-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_factory` R1, Errors row 1"""
    a = mk_fac()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_factory(db, factory_id=MISSING, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FAS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fas_d_04__the_managers_open_batch_valueerror_becomes_the_400_with_the_blockers_as_given_after_a_rollback(
    db, w1, u1, mk_fac,
):
    """FAS-D-04 — the manager's open-batch ValueError becomes the 400 with the blockers as given, after a rollback.
    Rules: `delete_factory` R2 [BUG-1331], Errors row 3"""
    a = mk_fac()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_fac(name="Extra", abbreviation="EX")
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(
            svc.factory_manager, "delete_factory",
            side_effect=ValueError("Factory has open production batches", BLOCKERS),
        ):
            svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory has open production batches"
    # Then 4
    assert exc.value.errors == [{"type": "production_batch", "id": 7}, {"type": "other_workspace"}]
    # Then 5
    assert count_facs(db, name="Extra") == 0
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] FAS-D-05
@pytest.mark.xfail(strict=True, reason="BUG-1331: Factory with open production batches can be deleted")
def test_fas_d_05__end_to_end_a_draft_batch_blocks_the_delete_with_a_400_that_lists_it(
    db, w1, u1, mk_fac, mk_line, mk_batch,
):
    """FAS-D-05 — end to end: a draft batch blocks the delete with a 400 that lists it.
    Rules: `delete_factory` R2 [BUG-1331], Errors row 3"""
    a = mk_fac()
    l1 = mk_line(a)
    b1 = mk_batch(l1, status="draft")
    commit_point(db)
    before_a = snap_before(db, a)
    before_b1 = snap_before(db, b1, ProductionBatch)
    before = written(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory has open production batches"
    # Then 4
    assert exc.value.errors == [{"type": "production_batch", "id": b1.id}]
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert snap(db, b1, ProductionBatch) == before_b1
    # Then 7
    assert written(db) == before


# [claude] FAS-D-06
def test_fas_d_06__a_database_error_at_the_flush_passes_unchanged_the_factory_stays_live(db, w1, mk_fac):
    """FAS-D-06 — a database error at the flush passes unchanged; the factory stays live.
    Rules: `delete_factory` R1, Errors row 4; TC3"""
    a = mk_fac()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    row = reread(db, a)
    assert row.is_deleted is False
    assert row.deleted_by is None
    # Then 5
    assert usable(db)


# [claude] FAS-D-07
def test_fas_d_07__a_factory_with_a_completed_batch_is_deleted_only_open_batches_block(
    db, w1, u1, mk_fac, mk_line, mk_batch,
):
    """FAS-D-07 — a factory with a completed batch is deleted: only open batches block.
    Rules: `delete_factory` R1, R2"""
    a = mk_fac()
    l1 = mk_line(a)
    b1 = mk_batch(l1, status="completed")
    commit_point(db)
    result = svc.delete_factory(db, factory_id=a.id, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id == a.id
    assert result.is_deleted is True
    # Then 2
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u1.id
    # Then 3
    batch = reread(db, b1, ProductionBatch)
    assert batch.status == "completed"
    assert batch.production_line_id == l1.id
