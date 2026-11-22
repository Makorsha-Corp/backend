"""Unit tests for app/services/factory_section_service.py.

Implements tests/unit/services/factory_section_service.cases.md, one test per
case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps and the race simulation of FSS-C-11.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (A -> a, MA1 ->
ma1, `W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate
from app.services.factory_section_service import factory_section_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton factory_section_service"
svc = factory_section_service

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "T0" (naive)
T0 = datetime(2025, 12, 1, 8, 0, 0)  # noqa: DTZ001


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows, in Conventions order (every test)
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 created every Given row
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# U2 = the acting user
@pytest.fixture
def u2(db, u1):
    return make_profile(db)


def _factory(db, ws, u1, name, abbreviation, **but):
    return _add(db, Factory(
        workspace_id=ws.id, name=name, abbreviation=abbreviation, created_by=u1.id,
        is_active=but.pop("is_active", True), is_deleted=but.pop("is_deleted", False), **but,
    ))


@pytest.fixture
def f1(db, w1, u1, u2):
    return _factory(db, w1, u1, "Main Plant", "MP")


@pytest.fixture
def f2(db, w1, u1, f1):
    return _factory(db, w1, u1, "North Yard", "NY")


@pytest.fixture
def f9(db, w2, u1, f2):
    return _factory(db, w2, u1, "Far Depot", "FR")


@pytest.fixture
def fd(db, w1, u1, f9):
    return _factory(db, w1, u1, "Old Plant", "OP", is_deleted=True, deleted_at=T0, deleted_by=u1.id)


@pytest.fixture
def fi(db, w1, u1, fd):
    return _factory(db, w1, u1, "Idle Plant", "IP", is_active=False)


@pytest.fixture(autouse=True)
def standing_rows(fi):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "gone" (after "but")
@pytest.fixture
def gone(u1):
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": u1.id}


def _section_fields(w1, f1, u1, name, but):
    fields = {
        "workspace_id": w1.id, "factory_id": f1.id, "name": name, "created_by": u1.id,
        "is_active": True, "is_deleted": False,
        "updated_by": None, "updated_at": None, "deleted_at": None, "deleted_by": None,
    }
    fields.update(but)
    return fields


# Convention "section": one row, flushed
@pytest.fixture
def mk_section(db, w1, f1, u1):
    def _mk(name, **but):
        return _add(db, FactorySection(**_section_fields(w1, f1, u1, name, but)))
    return _mk


# Convention "n rows, by add_all"
@pytest.fixture
def mk_sections(db, w1, f1, u1):
    def _mk(names):
        rows = [FactorySection(**_section_fields(w1, f1, u1, name, {})) for name in names]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "machine of F"
@pytest.fixture
def mk_machine(db):
    def _mk(factory, name):
        return _add(db, Machine(
            workspace_id=factory.workspace_id, factory_id=factory.id, name=name, is_active=True, is_deleted=False,
        ))
    return _mk


# Convention "assignment of MA to S"
@pytest.fixture
def mk_assignment(db, u1):
    def _mk(machine, section):
        return _add(db, MachineSectionAssignment(
            workspace_id=machine.workspace_id, machine_id=machine.id, factory_section_id=section.id,
            created_by=u1.id,
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


# Convention "re-read X" (sections)
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(FactorySection).where(FactorySection.id == row_id)).scalar_one_or_none()


def _columns(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, row)


# ... and after a re-read
def snap(db, row):
    db.expire_all()
    return _columns(db, row)


# Convention "count:" lines: factory_sections rows (all workspaces), with the filter stated
def count_sections(db, **filters):
    query = select(func.count()).select_from(FactorySection)
    for column, value in filters.items():
        query = query.where(getattr(FactorySection, column) == value)
    return db.execute(query).scalar_one()


_WRITTEN = (FactorySection, Factory, Machine, MachineSectionAssignment)


# Convention "nothing written": row counts of the four tables (all workspaces)
def written(db):
    return {m.__tablename__: db.execute(select(func.count()).select_from(m)).scalar_one() for m in _WRITTEN}


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "names(x)"
def names(rows):
    return [r.name for r in rows]


# Convention "rows_of_section(S)"
def rows_of_section(db, section):
    section_id = _id_of(section)
    db.expire_all()
    query = select(MachineSectionAssignment).where(MachineSectionAssignment.factory_section_id == section_id)
    return list(db.execute(query).scalars())


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# FactorySectionService.create_factory_section
# --------------------------------------------------------------------------- #

# [claude] FSS-C-01
def test_fss_c_01__a_new_section_is_committed_and_returned_re_read(db, w1, u2, f1):
    """FSS-C-01 — a new section is committed and returned re-read.
    Rules: `create_factory_section` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_factory_section(
        db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "factory_id" not in unloaded(result)
    assert "created_by" not in unloaded(result)
    # Then 2
    assert isinstance(result, FactorySection)
    # Then 3
    assert result.id is not None
    assert result.created_at is not None
    # Then 4
    assert result.name == "Paint"
    assert result.factory_id == f1.id
    assert result.created_by == u2.id
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(FactorySection).where(FactorySection.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    assert row.workspace_id == w1.id
    assert row.is_deleted is False
    # Then 6
    assert count_sections(db) == 1


# [claude] FSS-C-02
def test_fss_c_02__an_unknown_factory_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, f2, mk_section,
):
    """FSS-C-02 — an unknown factory: the 404 passes unchanged and the session is rolled back.
    Rules: `create_factory_section` R2; TC3"""
    a = mk_section("Cutting")
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_section("Extra", factory_id=f2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="Paint", factory_id=MISSING), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert count_sections(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, a) == before_a
    # Then 7
    assert usable(db)


# [claude] FSS-C-03
def test_fss_c_03__a_soft_deleted_factory_the_400_passes_unchanged_nothing_saved(db, w1, u2, fd):
    """FSS-C-03 — a soft-deleted factory: the 400 passes unchanged, nothing saved.
    Rules: `create_factory_section` R2"""
    commit_point(db)
    before = written(db)
    before_fd = snap_before(db, fd)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="Paint", factory_id=fd.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create section for deleted factory"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, fd) == before_fd


# [claude] FSS-C-04
def test_fss_c_04__a_name_taken_in_the_factory_the_409_passes_unchanged_nothing_saved(
    db, w1, u2, f1, mk_section,
):
    """FSS-C-04 — a name taken in the factory: the 409 passes unchanged, nothing saved.
    Rules: `create_factory_section` R2"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert count_sections(db, name="Paint") == 1
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before


# [claude] FSS-C-05
def test_fss_c_05__a_database_error_at_the_flush_passes_unchanged_and_nothing_is_saved(
    db, w1, f1, f2, mk_section,
):
    """FSS-C-05 — a database error at the flush passes unchanged and nothing is saved.
    Rules: `create_factory_section` Errors (database errors unchanged); TC3"""
    mk_section("Cutting")
    commit_point(db)
    before = written(db)
    mk_section("Extra", factory_id=f2.id)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=MISSING,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_sections(db, name="Paint") == 0
    # Then 4
    assert count_sections(db, name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] FSS-C-06
def test_fss_c_06__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u2, f1):
    """FSS-C-06 — a failing commit is rolled back and re-raised.
    Rules: `create_factory_section` R3; TC4"""
    commit_point(db)
    before = written(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_factory_section(
                db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id,
                user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_sections(db) == 0
    # Then 4
    assert written(db) == before


# [claude] FSS-C-07
def test_fss_c_07__a_failing_re_read_after_the_commit_leaves_the_section_saved(db, w1, u2, f1):
    """FSS-C-07 — a failing re-read after the commit leaves the section saved.
    Rules: `create_factory_section` R3; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_factory_section(
                db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id,
                user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_sections(db) == 1
    # Then 3
    row = db.execute(select(FactorySection)).scalar_one()
    assert row.name == "Paint"
    assert row.created_by == u2.id


# [claude] FSS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-915: Blank / whitespace-only section names accepted; names stored untrimmed")
def test_fss_c_08__pass_through_bug_915_a_padded_name_is_stored_trimmed(db, w1, u2, f1):
    """FSS-C-08 — pass-through BUG-915: a padded name is stored trimmed.
    Rules: `create_factory_section` R1 [BUG-915]"""
    commit_point(db)
    data = FactorySectionCreate(name="  Paint ", factory_id=f1.id)
    result = svc.create_factory_section(db, section_in=data, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(FactorySection).where(FactorySection.id == result_id)).scalar_one()
    assert row.name == "Paint"


# [claude] FSS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-912: Section duplicate-name check is case- and whitespace-sensitive")
def test_fss_c_09__pass_through_bug_912_a_name_in_another_case_is_refused_with_the_submitted_name(
    db, w1, u2, f1, mk_section,
):
    """FSS-C-09 — pass-through BUG-912: a name in another case is refused with the submitted name.
    Rules: `create_factory_section` R1, R2 [BUG-912]"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'paint' already exists in this factory"
    # Then 4
    assert count_sections(db) == 1
    # Then 5
    assert snap(db, a) == before_a


# [claude] FSS-C-10
@pytest.mark.xfail(
    strict=False, reason="BUG-911: Section duplicate-name check only scans the first 100 sections of the factory",
)
def test_fss_c_10__pass_through_bug_911_a_duplicate_that_is_the_101st_live_section_is_still_refused(
    db, w1, u2, f1, mk_section, mk_sections,
):
    """FSS-C-10 — pass-through BUG-911: a duplicate that is the 101st live section is still refused.
    Rules: `create_factory_section` R1, R2 [BUG-911]"""
    mk_sections([f"Bay {k:03d}" for k in range(1, 101)])
    mk_section("Late")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_factory_section(
            db, section_in=FactorySectionCreate(name="Late", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Late' already exists in this factory"
    # Then 4
    assert count_sections(db, name="Late") == 1
    # Then 5
    assert count_sections(db) == 101


# [claude] FSS-C-11
@pytest.mark.xfail(strict=True, reason="BUG-913: Section name uniqueness per factory not enforced by the database")
def test_fss_c_11__pass_through_bug_913_a_create_that_loses_the_race_gets_the_409_nothing_saved(
    db, w1, u2, f1, mk_section,
):
    """FSS-C-11 — pass-through BUG-913: a create that loses the race gets the 409, nothing saved.
    Rules: `create_factory_section` R1, R2 [BUG-913]"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(svc.factory_section_manager, "_check_name_exists_in_factory", return_value=False):
            svc.create_factory_section(
                db, section_in=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id,
                user_id=u2.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert count_sections(db, name="Paint") == 1
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# --------------------------------------------------------------------------- #
# FactorySectionService.get_factory_section
# --------------------------------------------------------------------------- #

# [claude] FSS-G-01
def test_fss_g_01__a_live_section_of_the_workspace_in_a_live_factory_is_returned(db, w1, w2, f1, f9, mk_section):
    """FSS-G-01 — a live section of the workspace in a live factory is returned.
    Rules: `get_factory_section` R1"""
    mk_section("Packing", factory_id=f9.id, workspace_id=w2.id)
    a = mk_section("Paint")
    commit_point(db)
    result = svc.get_factory_section(db, section_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, FactorySection)
    # Then 2
    assert result.id == a.id
    assert result.name == "Paint"
    assert result.factory_id == f1.id


# [claude] FSS-G-02
def test_fss_g_02__another_workspaces_id_the_404_passes_unchanged(db, w1, w2, f9, mk_section):
    """FSS-G-02 — another workspace's id: the 404 passes unchanged.
    Rules: `get_factory_section` R5, Errors row 1"""
    mk_section("Paint")
    z = mk_section("Packing", factory_id=f9.id, workspace_id=w2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory_section(db, section_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {z.id} not found"
    # Then 4
    assert snap(db, z) == before_z


# [claude] FSS-G-03
def test_fss_g_03__an_unknown_id_the_404_passes_unchanged(db, w1, mk_section):
    """FSS-G-03 — an unknown id: the 404 passes unchanged.
    Rules: `get_factory_section` R5, Errors row 1"""
    mk_section("Paint")
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory_section(db, section_id=MISSING, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"


# [claude] FSS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-916: `get_factory_section` returns soft-deleted sections")
def test_fss_g_04__a_soft_deleted_section_is_hidden_by_default(db, w1, gone, mk_section):
    """FSS-G-04 — a soft-deleted section is hidden by default.
    Rules: `get_factory_section` R2 [BUG-916], Errors row 1"""
    a = mk_section("Old Line", **gone)
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory_section(db, section_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {a.id} not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-916: `get_factory_section` returns soft-deleted sections")
def test_fss_g_05__include_deleted_true_returns_a_soft_deleted_section(db, w1, gone, mk_section):
    """FSS-G-05 — include_deleted=True returns a soft-deleted section.
    Rules: `get_factory_section` R3 [BUG-916]"""
    a = mk_section("Old Line", **gone)
    commit_point(db)
    result = svc.get_factory_section(db, section_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True
    assert result.name == "Old Line"


# [claude] FSS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-916: `get_factory_section` returns soft-deleted sections")
def test_fss_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, w2, f9, gone, mk_section):
    """FSS-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_factory_section` R3 [BUG-916], Errors row 1"""
    z = mk_section("Old Bin", factory_id=f9.id, workspace_id=w2.id, **gone)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory_section(db, section_id=z.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {z.id} not found"


# [claude] FSS-G-07
@pytest.mark.xfail(strict=True, reason="BUG-925: A section of a soft-deleted factory can still be opened by id")
def test_fss_g_07__a_live_section_of_a_soft_deleted_factory_is_hidden_by_default(db, w1, fd, mk_section):
    """FSS-G-07 — a live section of a soft-deleted factory is hidden by default.
    Rules: `get_factory_section` R4 [BUG-925], Errors row 1"""
    h = mk_section("Paint", factory_id=fd.id)
    commit_point(db)
    before_h = snap_before(db, h)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_factory_section(db, section_id=h.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {h.id} not found"
    # Then 4
    assert snap(db, h) == before_h


# [claude] FSS-G-08
@pytest.mark.xfail(strict=True, reason="BUG-925: A section of a soft-deleted factory can still be opened by id")
def test_fss_g_08__include_deleted_true_returns_a_live_section_of_a_soft_deleted_factory(db, w1, fd, mk_section):
    """FSS-G-08 — include_deleted=True returns a live section of a soft-deleted factory.
    Rules: `get_factory_section` R4 [BUG-925]"""
    h = mk_section("Paint", factory_id=fd.id)
    commit_point(db)
    result = svc.get_factory_section(db, section_id=h.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == h.id
    # Then 2
    assert result.factory_id == fd.id
    assert result.is_deleted is False


# [claude] FSS-G-09
def test_fss_g_09__the_read_neither_commits_nor_rolls_back(db, w1, f2, mk_section):
    """FSS-G-09 — the read neither commits nor rolls back.
    Rules: `get_factory_section` R5; TC6"""
    a = mk_section("Paint")
    b = mk_section("Cutting")
    commit_point(db)
    mk_section("Pending", factory_id=f2.id)
    b.name = "Edited"
    result = svc.get_factory_section(db, section_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_sections(db, name="Pending") == 1
    # Then 5
    db.rollback()
    assert count_sections(db, name="Pending") == 0
    # Then 6
    assert reread(db, b).name == "Cutting"


# --------------------------------------------------------------------------- #
# FactorySectionService.get_factory_sections
# --------------------------------------------------------------------------- #

# [claude] FSS-L-01
def test_fss_l_01__factory_id_reaches_the_manager(db, w1, w2, f1, f2, f9, mk_section):
    """FSS-L-01 — factory_id reaches the manager.
    Rules: `get_factory_sections` R1"""
    a = mk_section("Paint")
    mk_section("Cutting", factory_id=f2.id)
    mk_section("Packing", factory_id=f9.id, workspace_id=w2.id)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] FSS-L-02
def test_fss_l_02__the_search_reaches_the_manager_and_only_the_workspaces_matches_come_back(
    db, w1, w2, f2, f9, mk_section,
):
    """FSS-L-02 — the search reaches the manager and only the workspace's matches come back.
    Rules: `get_factory_sections` R1"""
    a = mk_section("Paint")
    mk_section("Cutting")
    c = mk_section("Main Hall", factory_id=f2.id)
    mk_section("Drain Bay", factory_id=f9.id, workspace_id=w2.id)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, search="ain")

    # Then 1
    assert ids(result) == [a.id, c.id]


# [claude] FSS-L-03
def test_fss_l_03__with_the_defaults_101_live_sections_give_100(db, w1, mk_sections):
    """FSS-L-03 — with the defaults 101 live sections give 100.
    Rules: `get_factory_sections` R1"""
    mk_sections([f"Bay {k:03d}" for k in range(1, 102)])
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] FSS-L-04
def test_fss_l_04__limit_reaches_the_manager(db, w1, mk_section):
    """FSS-L-04 — limit reaches the manager.
    Rules: `get_factory_sections` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_section(name)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2


# [claude] FSS-L-05
def test_fss_l_05__skip_reaches_the_manager_limit_1000_takes_the_rest(db, w1, mk_section):
    """FSS-L-05 — skip reaches the manager, limit=1000 takes the rest.
    Rules: `get_factory_sections` R1"""
    for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
        mk_section(name)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, skip=4, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] FSS-L-06
def test_fss_l_06__by_default_a_soft_deleted_section_is_left_out(db, w1, gone, mk_section):
    """FSS-L-06 — by default a soft-deleted section is left out.
    Rules: `get_factory_sections` R2"""
    a = mk_section("Paint")
    mk_section("Old Line", **gone)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert [r.id for r in result] == [a.id]


# [claude] FSS-L-07
@pytest.mark.xfail(strict=True, reason="BUG-920: Section list `include_deleted` flag unreachable from the API")
def test_fss_l_07__include_deleted_true_lists_soft_deleted_sections_too(db, w1, gone, mk_section):
    """FSS-L-07 — include_deleted=True lists soft-deleted sections too.
    Rules: `get_factory_sections` R2 [BUG-920]"""
    a = mk_section("Paint")
    d = mk_section("Old Line", **gone)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert ids(result) == [a.id, d.id]


# [claude] FSS-L-08
def test_fss_l_08__the_list_neither_commits_nor_rolls_back(db, w1, w2, f9, mk_section):
    """FSS-L-08 — the list neither commits nor rolls back.
    Rules: `get_factory_sections` R3; TC6"""
    a = mk_section("Paint")
    b = mk_section("Packing", factory_id=f9.id, workspace_id=w2.id)
    commit_point(db)
    p = mk_section("Pending")
    b.name = "Edited"
    result = svc.get_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_sections(db, name="Pending") == 0
    # Then 5
    assert reread(db, b).name == "Packing"


# [claude] FSS-L-09
@pytest.mark.xfail(strict=False, reason="BUG-903: Section list of a factory has no sort order")
def test_fss_l_09__pass_through_bug_903_with_a_factory_names_come_case_insensitive_ascending(
    db, w1, f1, mk_section,
):
    """FSS-L-09 — pass-through BUG-903: with a factory, names come case-insensitive ascending.
    Rules: `get_factory_sections` R1 [BUG-903]"""
    for name in ("Delta", "alpha", "echo", "Bravo", "charlie"):
        mk_section(name)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]


# [claude] FSS-L-10
@pytest.mark.xfail(strict=True, reason="BUG-904: Sections of a soft-deleted factory are still returned")
def test_fss_l_10__pass_through_bug_904_filtered_by_a_soft_deleted_factory_its_live_section_is_hidden(
    db, w1, fd, mk_section,
):
    """FSS-L-10 — pass-through BUG-904: filtered by a soft-deleted factory, its live section is hidden.
    Rules: `get_factory_sections` R1 [BUG-904]"""
    h = mk_section("Cutting", factory_id=fd.id)
    commit_point(db)
    before_h = snap_before(db, h)
    result = svc.get_factory_sections(db, workspace_id=w1.id, factory_id=fd.id)

    # Then 1
    assert result == []
    # Then 2
    assert snap(db, h) == before_h


# [claude] FSS-L-11
@pytest.mark.xfail(strict=False, reason="BUG-917: Section list drops deleted rows and applies the search after paging")
def test_fss_l_11__pass_through_bug_917_a_deleted_section_takes_no_place_in_the_page(
    db, w1, f2, gone, mk_section,
):
    """FSS-L-11 — pass-through BUG-917: a deleted section takes no place in the page.
    Rules: `get_factory_sections` R1 [BUG-917]"""
    mk_section("Old Line", **gone)
    a = mk_section("Paint")
    b = mk_section("Welding", factory_id=f2.id)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] FSS-L-12
@pytest.mark.xfail(strict=False, reason="BUG-918: Workspace-wide section list has no sort order")
def test_fss_l_12__pass_through_bug_918_without_a_factory_names_come_case_insensitive_ascending(
    db, w1, f2, mk_section,
):
    """FSS-L-12 — pass-through BUG-918: without a factory, names come case-insensitive ascending.
    Rules: `get_factory_sections` R1 [BUG-918]"""
    mk_section("Delta")
    mk_section("alpha", factory_id=f2.id)
    mk_section("echo")
    mk_section("Bravo", factory_id=f2.id)
    mk_section("charlie")
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]


# [claude] FSS-L-13
@pytest.mark.xfail(strict=True, reason="BUG-921: Section search text is not trimmed")
def test_fss_l_13__pass_through_bug_921_a_search_of_only_spaces_applies_no_filter(db, w1, mk_section):
    """FSS-L-13 — pass-through BUG-921: a search of only spaces applies no filter.
    Rules: `get_factory_sections` R1 [BUG-921]"""
    a = mk_section("Main Hall")
    b = mk_section("Paint")
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, search="   ")

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] FSS-L-14
@pytest.mark.xfail(strict=True, reason="BUG-922: Section list treats `factory_id=0` as \"no factory filter\"")
def test_fss_l_14__pass_through_bug_922_factory_id_0_filters_like_any_id(db, w1, f2, mk_section):
    """FSS-L-14 — pass-through BUG-922: factory_id 0 filters like any id.
    Rules: `get_factory_sections` R1 [BUG-922]"""
    mk_section("Paint")
    mk_section("Cutting", factory_id=f2.id)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id, factory_id=0)

    # Then 1
    assert result == []


# [claude] FSS-L-15
@pytest.mark.xfail(strict=True, reason="BUG-924: Workspace-wide section list shows sections of a soft-deleted factory")
def test_fss_l_15__pass_through_bug_924_without_a_factory_a_section_of_a_soft_deleted_factory_is_hidden(
    db, w1, fd, mk_section,
):
    """FSS-L-15 — pass-through BUG-924: without a factory, a section of a soft-deleted factory is hidden.
    Rules: `get_factory_sections` R1 [BUG-924]"""
    a = mk_section("Paint")
    mk_section("Cutting", factory_id=fd.id)
    commit_point(db)
    result = svc.get_factory_sections(db, workspace_id=w1.id)

    # Then 1
    assert a.id in [r.id for r in result]
    # Then 2
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# FactorySectionService.update_factory_section
# --------------------------------------------------------------------------- #

# [claude] FSS-U-01
def test_fss_u_01__a_rename_is_committed_and_returned_re_read_with_updated_at(db, w1, u1, u2, f1, mk_section):
    """FSS-U-01 — a rename is committed and returned re-read with updated_at.
    Rules: `update_factory_section` R1, Returns; TC1, TC2"""
    a = mk_section("Paint")
    commit_point(db)
    result = svc.update_factory_section(
        db, section_id=a.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    assert "name" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.name == "Spray"
    assert result.updated_by == u2.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.name == "Spray"
    assert row.updated_by == u2.id
    assert row.updated_at is not None
    # Then 5
    row = reread(db, a)
    assert row.factory_id == f1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False


# [claude] FSS-U-02
def test_fss_u_02__another_workspaces_id_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u2, f2, f9, mk_section,
):
    """FSS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back.
    Rules: `update_factory_section` R2; TC3"""
    mk_section("Paint")
    z = mk_section("Packing", factory_id=f9.id, workspace_id=w2.id)
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_section("Extra", factory_id=f2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=z.id, section_in=FactorySectionUpdate(name="Hacked"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {z.id} not found"
    # Then 4
    assert count_sections(db, name="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] FSS-U-03
def test_fss_u_03__a_deleted_section_the_400_passes_unchanged_nothing_saved(db, w1, u2, gone, mk_section):
    """FSS-U-03 — a deleted section: the 400 passes unchanged, nothing saved.
    Rules: `update_factory_section` R2"""
    a = mk_section("Old Line", **gone)
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-U-04
def test_fss_u_04__a_move_to_an_unknown_factory_the_404_passes_unchanged_nothing_saved(db, w1, u2, mk_section):
    """FSS-U-04 — a move to an unknown factory: the 404 passes unchanged, nothing saved.
    Rules: `update_factory_section` R2"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(factory_id=MISSING), workspace_id=w1.id,
            user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-U-05
def test_fss_u_05__a_move_to_a_soft_deleted_factory_the_400_passes_unchanged_nothing_saved(
    db, w1, u2, fd, mk_section,
):
    """FSS-U-05 — a move to a soft-deleted factory: the 400 passes unchanged, nothing saved.
    Rules: `update_factory_section` R2"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(factory_id=fd.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move section to deleted factory"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-U-06
def test_fss_u_06__a_name_taken_in_the_factory_the_409_passes_unchanged_nothing_saved(db, w1, u2, mk_section):
    """FSS-U-06 — a name taken in the factory: the 409 passes unchanged, nothing saved.
    Rules: `update_factory_section` R2"""
    mk_section("Paint")
    b = mk_section("Cutting")
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=b.id, section_in=FactorySectionUpdate(name="Paint"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert snap(db, b) == before_b


# [claude] FSS-U-07
@pytest.mark.xfail(strict=True, reason="BUG-914: Moving a section into a factory where its name is taken is not checked")
def test_fss_u_07__pass_through_bug_914_a_plain_move_into_a_factory_where_the_name_is_taken_is_refused(
    db, w1, u2, f1, f2, mk_section,
):
    """FSS-U-07 — pass-through BUG-914: a plain move into a factory where the name is taken is refused.
    Rules: `update_factory_section` R1, R2 [BUG-914]"""
    a = mk_section("Paint")
    b = mk_section("Paint", factory_id=f2.id)
    commit_point(db)
    before_b = snap_before(db, b)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Section with name 'Paint' already exists in this factory"
    # Then 4
    assert reread(db, a).factory_id == f1.id
    # Then 5
    assert snap(db, b) == before_b


# [claude] FSS-U-08
@pytest.mark.xfail(strict=True, reason="BUG-919: `updated_by` stamped on no-op section updates")
def test_fss_u_08__pass_through_bug_919_an_empty_update_does_not_stamp_updated_by(db, w1, u2, mk_section):
    """FSS-U-08 — pass-through BUG-919: an empty update does not stamp updated_by.
    Rules: `update_factory_section` R1 [BUG-919]"""
    a = mk_section("Paint")
    commit_point(db)
    result = svc.update_factory_section(
        db, section_id=a.id, section_in=FactorySectionUpdate(), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).updated_by is None


# [claude] FSS-U-09
@pytest.mark.xfail(strict=True, reason="BUG-923: Updating a section with `factory_id=0` crashes instead of 404")
def test_fss_u_09__pass_through_bug_923_factory_id_0_gets_the_404(db, w1, u2, mk_section):
    """FSS-U-09 — pass-through BUG-923: factory_id 0 gets the 404.
    Rules: `update_factory_section` R2 [BUG-923]"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(factory_id=0), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory with ID 0 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-U-10
@pytest.mark.xfail(
    strict=True, reason="BUG-926: A section inside a soft-deleted factory can still be renamed or moved out",
)
def test_fss_u_10__pass_through_bug_926_a_section_of_a_soft_deleted_factory_cannot_be_renamed(
    db, w1, u2, fd, mk_section,
):
    """FSS-U-10 — pass-through BUG-926: a section of a soft-deleted factory cannot be renamed.
    Rules: `update_factory_section` R1, R2 [BUG-926]"""
    h = mk_section("Paint", factory_id=fd.id)
    commit_point(db)
    before_h = snap_before(db, h)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=h.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update deleted factory section"
    # Then 4
    assert snap(db, h) == before_h


# [claude] FSS-U-11
@pytest.mark.xfail(strict=True, reason="BUG-928: Moving a section to another factory links its machines across factories")
def test_fss_u_11__pass_through_bug_928_a_section_with_an_assigned_machine_cannot_be_moved(
    db, w1, u2, f1, f2, mk_section, mk_machine, mk_assignment,
):
    """FSS-U-11 — pass-through BUG-928: a section with an assigned machine cannot be moved.
    Rules: `update_factory_section` R2 [BUG-928]"""
    a = mk_section("Paint")
    ma = mk_machine(f1, "Lathe")
    as_ = mk_assignment(ma, a)
    commit_point(db)
    before_as = snap_before(db, as_)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_factory_section(
            db, section_id=a.id, section_in=FactorySectionUpdate(factory_id=f2.id), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot move a section that has machines assigned"
    # Then 4
    assert reread(db, a).factory_id == f1.id
    # Then 5
    assert snap(db, as_) == before_as


# --------------------------------------------------------------------------- #
# FactorySectionService.delete_factory_section
# --------------------------------------------------------------------------- #

# [claude] FSS-D-01
def test_fss_d_01__a_soft_delete_is_committed_and_returned_re_read(db, w1, u2, f1, mk_section):
    """FSS-D-01 — a soft delete is committed and returned re-read.
    Rules: `delete_factory_section` R1, Returns; TC1, TC2"""
    a = mk_section("Paint")
    commit_point(db)
    result = svc.delete_factory_section(db, section_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert "is_deleted" not in unloaded(result)
    assert "deleted_at" not in unloaded(result)
    assert "deleted_by" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.is_deleted is True
    assert result.deleted_by == u2.id
    assert result.deleted_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    assert row.deleted_at is not None
    # Then 5
    row = reread(db, a)
    assert row.name == "Paint"
    assert row.factory_id == f1.id


# [claude] FSS-D-02
def test_fss_d_02__an_already_deleted_section_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, f2, gone, mk_section,
):
    """FSS-D-02 — an already deleted section: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_factory_section` R2; TC3"""
    a = mk_section("Old Line", **gone)
    commit_point(db)
    before_a = snap_before(db, a)
    mk_section("Extra", factory_id=f2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_factory_section(db, section_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section is already deleted"
    # Then 4
    assert count_sections(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] FSS-D-03
def test_fss_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u2, mk_section):
    """FSS-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_factory_section` R2"""
    a = mk_section("Paint")
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_factory_section(db, section_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Factory section with ID 999999999 not found"
    # Then 4
    assert snap(db, a) == before_a


# [claude] FSS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-908: Deleting a section permanently erases its machines' assignments")
def test_fss_d_04__pass_through_bug_908_the_machine_assignments_of_the_deleted_section_are_kept(
    db, w1, u2, f1, mk_section, mk_machine, mk_assignment,
):
    """FSS-D-04 — pass-through BUG-908: the machine assignments of the deleted section are kept.
    Rules: `delete_factory_section` R1 [BUG-908]"""
    a = mk_section("Paint")
    ma1 = mk_machine(f1, "Lathe")
    ma2 = mk_machine(f1, "Press")
    as1 = mk_assignment(ma1, a)
    mk_assignment(ma2, a)
    commit_point(db)
    before_as1 = snap_before(db, as1)
    result = svc.delete_factory_section(db, section_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).is_deleted is True
    # Then 3
    assert len(rows_of_section(db, a)) == 2
    # Then 4
    assert snap(db, as1) == before_as1


# [claude] FSS-D-05
@pytest.mark.xfail(strict=True, reason="BUG-927: A section inside a soft-deleted factory can still be deleted")
def test_fss_d_05__pass_through_bug_927_a_section_of_a_soft_deleted_factory_cannot_be_deleted(
    db, w1, u2, fd, mk_section,
):
    """FSS-D-05 — pass-through BUG-927: a section of a soft-deleted factory cannot be deleted.
    Rules: `delete_factory_section` R2 [BUG-927]"""
    h = mk_section("Paint", factory_id=fd.id)
    commit_point(db)
    before_h = snap_before(db, h)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_factory_section(db, section_id=h.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a section of a deleted factory"
    # Then 4
    assert snap(db, h) == before_h
