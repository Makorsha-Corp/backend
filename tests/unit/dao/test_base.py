"""Unit tests for app/dao/base.py.

Implements tests/unit/dao/base.cases.md (revision 5), one test per case.
Real Postgres session (`db` fixture). Nothing mocked (spec: no externals, no
race simulations); `db.commit` is only *wrapped* by a spy for the
"not committed" checks.
"""
from itertools import pairwise
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import String, event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.dao.base import BaseDAO
from app.models.department import Department
from app.models.workspace import Workspace
from tests.unit.factories import make_profile, make_workspace

BUG_100 = "BUG-100: BaseDAO list methods have no sort order"
BUG_101 = "BUG-101: Removing a non-existent id raises instead of returning None"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "DAOs": dao = BaseDAO(Department); wdao = BaseDAO(Workspace)
dao = BaseDAO(Department)
wdao = BaseDAO(Workspace)


# Convention "Ad-hoc schemas"
class DeptIn(BaseModel):
    title: str = Field(alias="name")
    workspace_id: int | None = None
    is_active: bool = False
    created_by: int | None = None


class DeptPatch(BaseModel):
    title: str | None = Field(None, alias="name")
    is_active: bool = True


class CreatorIn(BaseModel):
    id: int


class DeptNested(BaseModel):
    name: str
    workspace_id: int
    creator: CreatorIn


# Convention "Test-local mapped class (BASE-G-06 only)": own DeclarativeBase,
# never created in the DB, no `id` attribute.
class _ProbeBase(DeclarativeBase):
    pass


class NoIdThing(_ProbeBase):
    __tablename__ = "base_dao_no_id_probe"
    code: Mapped[str] = mapped_column(String, primary_key=True)


# Convention "N0": department rows visible before any setup of the case.
# Requested first by every test that needs it, so it runs before w1/w2/w3 setup.
@pytest.fixture
def n0(db):
    return count_all(db)


# Convention "W1, W2, W3 = three existing workspaces (fresh per test)"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def w3(db):
    return make_workspace(db)


# Convention "P1 = an existing profile"
@pytest.fixture
def p1(db):
    return make_profile(db)


# Convention "D "Sales" (W1)" / "(deleted)": insert + flush, one at a time.
def mk(db, ws, name, *, deleted=False, **cols):
    row = Department(workspace_id=ws.id, name=name, is_deleted=deleted, **cols)
    db.add(row)
    db.flush()
    return row


# Convention "k own rows": "R001", "R002", ... in insertion order.
def own_rows(db, ws, k):
    return [mk(db, ws, f"R{i:03d}") for i in range(1, k + 1)]


# Convention "MISSING" / "MISSING_PROFILE"
def missing(db):
    return (db.execute(text("SELECT max(id) FROM departments")).scalar() or 0) + 1000


def missing_profile(db):
    return (db.execute(text("SELECT max(id) FROM profiles")).scalar() or 0) + 1000


# Convention "Re-read": expire_all, then raw SELECT on departments by id.
def reread(db, dept_id):
    db.expire_all()
    return db.execute(
        text("SELECT * FROM departments WHERE id = :i"), {"i": dept_id}
    ).mappings().first()


def raw_row(db, dept_id):
    """Raw SELECT by id without expiring (used before a savepoint rollback)."""
    return db.execute(
        text("SELECT * FROM departments WHERE id = :i"), {"i": dept_id}
    ).mappings().first()


def count_all(db):
    return db.execute(text("SELECT count(*) FROM departments")).scalar()


def count_ws(db, ws):
    return db.execute(
        text("SELECT count(*) FROM departments WHERE workspace_id = :w"), {"w": ws.id}
    ).scalar()


def count_named(db, name):
    return db.execute(
        text("SELECT count(*) FROM departments WHERE name = :n"), {"n": name}
    ).scalar()


def ids(rows):
    return [r.id for r in rows]


# Convention "Not committed checks": spy that wraps (does not replace) db.commit.
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# Convention "Planner settings (BASE-GM-04, BASE-GW-05 only)"
def force_seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# SQL statement counter (BASE-GW-13): before_cursor_execute listener on the engine.
class StatementCounter:
    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def _on(self, *args, **kwargs):
        self.count += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False


# BUG-100 setup: A "Zeta", B "Alpha", C "Mid", then A renamed "Zulu" (flushed UPDATE).
def heap_disorder(db, ws):
    a = mk(db, ws, "Zeta")
    b = mk(db, ws, "Alpha")
    c = mk(db, ws, "Mid")
    a.name = "Zulu"
    db.flush()
    return a, b, c


# =========================================================================== #
# BaseDAO.get
# =========================================================================== #


def test_base_g_01__returns_row_by_id(db, w1):
    """BASE-G-01 — get returns the row with that id (not another one).
    Rules: get R1."""
    d1 = mk(db, w1, "Sales")
    mk(db, w1, "Ops")
    got = dao.get(db, id=d1.id)
    assert isinstance(got, Department)
    assert got.id == d1.id
    assert got.name == "Sales"


def test_base_g_02__missing_id_returns_none(db, w1):
    """BASE-G-02 — get of a non-existent id returns None without raising.
    Rules: get R2."""
    mk(db, w1, "Sales")
    assert dao.get(db, id=missing(db)) is None


def test_base_g_03__soft_deleted_row_returned(db, w1):
    """BASE-G-03 — get returns a soft-deleted row.
    Rules: get R3."""
    d1 = mk(db, w1, "Gone", deleted=True)
    got = dao.get(db, id=d1.id)
    assert got.id == d1.id
    assert got.is_deleted is True


def test_base_g_04__no_workspace_filter(db, w1, w2):
    """BASE-G-04 — get returns a row of any workspace.
    Rules: get R4."""
    mk(db, w1, "Sales")
    e1 = mk(db, w2, "Other")
    got = dao.get(db, id=e1.id)
    assert got.id == e1.id
    assert got.workspace_id == w2.id
    assert got.name == "Other"


def test_base_g_05__pending_row_not_found_until_flushed(db, w1):
    """BASE-G-05 — get does not see a pending (unflushed) row; after flush it returns it.
    Rules: get R5."""
    mid = missing(db)
    obj = Department(id=mid, name="Unflushed", workspace_id=w1.id)
    db.add(obj)
    # (a) pending: not found, and get did not flush
    assert dao.get(db, id=mid) is None
    assert raw_row(db, mid) is None
    db.flush()
    # (b) after explicit flush: the same object, row now in the DB
    got = dao.get(db, id=mid)
    assert got is obj
    assert got.name == "Unflushed"
    assert raw_row(db, mid) is not None


def test_base_g_06__model_without_id_raises(db, n0):
    """BASE-G-06 — get on a model with no `id` attribute raises AttributeError.
    Rules: get Errors row (no id)."""
    with pytest.raises(AttributeError) as exc:
        BaseDAO(NoIdThing).get(db, id=1)
    assert "id" in str(exc.value)
    assert count_all(db) == n0


# =========================================================================== #
# BaseDAO.get_multi
# =========================================================================== #


def test_base_gm_01__default_limit_caps_at_100(db, n0, w1):
    """BASE-GM-01 — default limit is 100: 101 rows -> 100 returned.
    Rules: get_multi R1."""
    own_rows(db, w1, 101)
    a = dao.get_multi(db)
    assert isinstance(a, list)
    assert len(a) == 100
    assert all(isinstance(r, Department) for r in a)
    b = dao.get_multi(db, skip=n0)
    assert len(b) == 100


def test_base_gm_02__exactly_100_rows_all_returned(db, n0, w1):
    """BASE-GM-02 — 100 rows past skip -> all 100 returned.
    Rules: get_multi R1."""
    own_rows(db, w1, 100)
    assert len(dao.get_multi(db, skip=n0)) == 100


def test_base_gm_03__skip_limit_pages(db, n0, w1):
    """BASE-GM-03 — skip/limit page; short last page.
    Rules: get_multi R1."""
    own_rows(db, w1, 5)
    assert len(dao.get_multi(db, skip=n0, limit=3)) == 3
    assert len(dao.get_multi(db, skip=n0 + 3, limit=3)) == 2


@pytest.mark.xfail(strict=True, reason=BUG_100)
def test_base_gm_04__ordered_by_id(db, n0, w1):
    """BASE-GM-04 — get_multi returns rows in id order; pages are stable.
    Rules: get_multi R2 [BUG-100]."""
    a, b, c = heap_disorder(db, w1)
    force_seqscan(db)
    # (a)
    assert ids(dao.get_multi(db, skip=n0, limit=100)) == [a.id, b.id, c.id]
    # (b)
    p1_ = ids(dao.get_multi(db, skip=n0, limit=2))
    p2_ = ids(dao.get_multi(db, skip=n0 + 2, limit=2))
    assert p1_ == [a.id, b.id]
    assert p2_ == [c.id]
    assert p1_ + p2_ == [a.id, b.id, c.id]
    # (c)
    all_ids = ids(dao.get_multi(db, limit=n0 + 3))
    assert all(x < y for x, y in pairwise(all_ids))


def test_base_gm_05__soft_deleted_included_and_counted(db, n0, w1):
    """BASE-GM-05 — soft-deleted rows are returned and counted by skip.
    Rules: get_multi R3."""
    d1 = mk(db, w1, "One")
    d2 = mk(db, w1, "Two", deleted=True)
    d3 = mk(db, w1, "Three")
    a = dao.get_multi(db, limit=n0 + 100)
    assert len(a) == n0 + 3
    assert {d1.id, d2.id, d3.id} <= set(ids(a))
    assert len(dao.get_multi(db, skip=n0 + 2, limit=100)) == 1


def test_base_gm_06__no_workspace_filter(db, n0, w1, w2):
    """BASE-GM-06 — get_multi returns rows of every workspace.
    Rules: get_multi R4."""
    d1 = mk(db, w1, "Sales")
    e1 = mk(db, w2, "Other")
    got = dao.get_multi(db, limit=n0 + 100)
    assert d1.id in ids(got)
    assert e1.id in ids(got)
    assert len(got) == n0 + 2


def test_base_gm_07__skip_at_or_past_end(db, n0, w1):
    """BASE-GM-07 — skip at the end -> []; one before -> 1 row.
    Rules: get_multi R5."""
    own_rows(db, w1, 2)
    assert dao.get_multi(db, skip=n0 + 2) == []
    assert len(dao.get_multi(db, skip=n0 + 1)) == 1


def test_base_gm_08__limit_zero(db, n0, w1):
    """BASE-GM-08 — limit=0 -> []; limit=1 -> 1 row.
    Rules: get_multi R5."""
    own_rows(db, w1, 2)
    assert dao.get_multi(db, limit=0) == []
    assert len(dao.get_multi(db, skip=n0, limit=1)) == 1


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"skip": -1}, "OFFSET must not be negative", id="BASE-GM-09"),
        pytest.param({"limit": -1}, "LIMIT must not be negative", id="BASE-GM-10"),
    ],
)
def test_base_gm_09_10__negative_skip_or_limit_raises(db, n0, w1, kwargs, message):
    """BASE-GM-09 / BASE-GM-10 — negative skip / limit raises DataError.
    Rules: get_multi R6; Errors row (negative)."""
    own_rows(db, w1, 2)
    with pytest.raises(DataError) as exc, db.begin_nested():
        dao.get_multi(db, **kwargs)
    assert message in str(exc.value)
    assert count_all(db) == n0 + 2


# =========================================================================== #
# BaseDAO.create
# =========================================================================== #


def test_base_c_01__create_from_dict(db, w1):
    """BASE-C-01 — create from a dict inserts and flushes the row.
    Rules: create R1."""
    got = dao.create(db, obj_in={"name": "Sales", "workspace_id": w1.id})
    assert isinstance(got, Department)
    assert isinstance(got.id, int)
    assert raw_row(db, got.id) is not None
    row = reread(db, got.id)
    assert row["name"] == "Sales"
    assert row["workspace_id"] == w1.id


def test_base_c_02__create_from_schema_by_alias_with_defaults(db, w1):
    """BASE-C-02 — schema input dumped by alias, schema defaults applied.
    Rules: create R2."""
    got = dao.create(db, obj_in=DeptIn(name="Ops", workspace_id=w1.id))
    assert isinstance(got, Department)
    assert got.id is not None
    row = reread(db, got.id)
    assert row["name"] == "Ops"
    assert row["is_active"] is False
    assert row["created_by"] is None
    assert row["workspace_id"] == w1.id


def test_base_c_03__model_defaults_applied(db, w1):
    """BASE-C-03 — omitted columns get their model/database defaults.
    Rules: create R3."""
    got = dao.create(db, obj_in={"name": "Plain", "workspace_id": w1.id})
    assert isinstance(got, Department)
    assert isinstance(got.id, int)
    assert got.name == "Plain"
    row = reread(db, got.id)
    assert row["is_active"] is True
    assert row["is_deleted"] is False
    assert row["created_at"] is not None
    assert row["updated_at"] is None
    assert row["created_by"] is None
    assert row["updated_by"] is None
    assert row["deleted_by"] is None


def test_base_c_04__explicit_none_gets_defaults(db, w1):
    """BASE-C-04 — explicit None for defaulted columns still gets the defaults.
    Rules: create R3."""
    got = dao.create(
        db,
        obj_in={
            "name": "Nones", "workspace_id": w1.id, "is_active": None,
            "is_deleted": None, "created_at": None, "created_by": None,
        },
    )
    assert isinstance(got, Department)
    assert isinstance(got.id, int)
    assert got.name == "Nones"
    row = reread(db, got.id)
    assert row["is_active"] is True
    assert row["is_deleted"] is False
    assert row["created_at"] is not None
    assert row["created_by"] is None


def test_base_c_05__flushed_not_committed(db, w1):
    """BASE-C-05 — create flushes but never commits.
    Rules: create R4."""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        got = dao.create(db, obj_in={"name": "Temp", "workspace_id": w1.id})
        new_id = got.id
        assert raw_row(db, new_id) is not None
        spy.assert_not_called()
        sp.rollback()
    assert reread(db, new_id) is None
    assert count_ws(db, w1) == 0


def test_base_c_06__unknown_key_raises_type_error(db, n0, w1):
    """BASE-C-06 — an unknown key raises TypeError and nothing is inserted.
    Rules: create R5; Errors row (unknown key)."""
    with pytest.raises(TypeError) as exc, db.begin_nested():
        dao.create(db, obj_in={"nmae": "Ops", "name": "Ops", "workspace_id": w1.id})
    assert "'nmae' is an invalid keyword argument for Department" in str(exc.value)
    db.expire_all()
    assert count_ws(db, w1) == 0
    assert count_all(db) == n0


def test_base_c_07__missing_workspace_id_integrity_error(db, n0, w1):
    """BASE-C-07 — no workspace_id -> IntegrityError (not filled in automatically).
    Rules: create R6, R8; Errors row (constraint)."""
    with pytest.raises(IntegrityError), db.begin_nested():
        dao.create(db, obj_in={"name": "NoWs"})
    db.expire_all()
    assert count_named(db, "NoWs") == 0
    assert count_all(db) == n0


def test_base_c_08__bad_fk_integrity_error(db, w1):
    """BASE-C-08 — created_by pointing at no profile -> IntegrityError.
    Rules: create R6; Errors row (constraint)."""
    bad = missing_profile(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        dao.create(
            db, obj_in={"name": "BadFk", "workspace_id": w1.id, "created_by": bad}
        )
    db.expire_all()
    assert count_ws(db, w1) == 0


def test_base_c_09__nested_relationship_value_raises(db, n0, w1, p1):
    """BASE-C-09 — nested schema value for a relationship raises AttributeError at construction.
    Rules: create R7; Errors row (nested value for relationship)."""
    sp = db.begin_nested()
    with pytest.raises(AttributeError) as exc:
        dao.create(
            db,
            obj_in=DeptNested(name="Nest", workspace_id=w1.id, creator=CreatorIn(id=p1.id)),
        )
    assert "'dict' object has no attribute '_sa_instance_state'" in str(exc.value)
    assert not any(isinstance(o, Department) for o in db.new)
    sp.rollback()
    db.expire_all()
    assert count_named(db, "Nest") == 0
    assert count_all(db) == n0


# =========================================================================== #
# BaseDAO.update
# =========================================================================== #


@pytest.fixture
def d_old(db, w1):
    """Convention: all update cases start from D "Old" (W1), flushed, updated_at NULL."""
    return mk(db, w1, "Old")


def test_base_u_01__dict_applies_all_keys_including_none(db, w1, p1):
    """BASE-U-01 — dict input applies every key, None included.
    Rules: update R1."""
    d = mk(db, w1, "Old", created_by=p1.id)
    got = dao.update(db, db_obj=d, obj_in={"name": "New", "created_by": None})
    assert got is d
    row = reread(db, d.id)
    assert row["name"] == "New"
    assert row["created_by"] is None


def test_base_u_02__schema_only_set_fields_by_alias(db, w1):
    """BASE-U-02 — schema input: only set fields applied, by alias.
    Rules: update R2."""
    d = mk(db, w1, "Old", is_active=False)
    got = dao.update(db, db_obj=d, obj_in=DeptPatch(name="New"))
    assert got is d
    row = reread(db, d.id)
    assert row["name"] == "New"
    assert row["is_active"] is False


def test_base_u_03__schema_explicit_none_ignored(db, d_old):
    """BASE-U-03 — schema input: explicit None ignored, other set fields applied.
    Rules: update R3."""
    got = dao.update(db, db_obj=d_old, obj_in=DeptPatch(name=None, is_active=False))
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "Old"
    assert row["is_active"] is False


def test_base_u_04__unknown_key_skipped_others_applied(db, d_old):
    """BASE-U-04 — unknown key silently skipped, known key applied.
    Rules: update R4."""
    got = dao.update(db, db_obj=d_old, obj_in={"nmae": "Ops", "name": "New"})
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "New"
    assert hasattr(d_old, "nmae") is False


def test_base_u_05__only_unknown_key_no_change(db, d_old):
    """BASE-U-05 — only an unknown key: no error, nothing changes.
    Rules: update R4."""
    got = dao.update(db, db_obj=d_old, obj_in={"nmae": "Ops"})
    assert got is d_old
    assert reread(db, d_old.id)["name"] == "Old"


def test_base_u_06__any_attribute_assignable(db, d_old, w1, w2, p1):
    """BASE-U-06 — workspace_id / is_deleted / audit fields can be changed.
    Rules: update R5."""
    got = dao.update(
        db, db_obj=d_old,
        obj_in={"workspace_id": w2.id, "is_deleted": True, "updated_by": p1.id},
    )
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["workspace_id"] == w2.id
    assert row["is_deleted"] is True
    assert row["updated_by"] == p1.id
    assert dao.get_by_id_and_workspace(db, id=d_old.id, workspace_id=w1.id) is None


def test_base_u_07__relationship_assignable(db, d_old, p1):
    """BASE-U-07 — a relationship (creator) can be assigned.
    Rules: update R5."""
    got = dao.update(db, db_obj=d_old, obj_in={"creator": p1})
    assert got is d_old
    assert reread(db, d_old.id)["created_by"] == p1.id


def test_base_u_08__empty_dict_no_change(db, d_old):
    """BASE-U-08 — empty dict: no error, no change, updated_at stays NULL.
    Rules: update R6."""
    got = dao.update(db, db_obj=d_old, obj_in={})
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "Old"
    assert row["updated_at"] is None


def test_base_u_09__empty_schema_no_change(db, d_old):
    """BASE-U-09 — schema with nothing set: no change, updated_at stays NULL.
    Rules: update R6."""
    got = dao.update(db, db_obj=d_old, obj_in=DeptPatch())
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "Old"
    assert row["is_active"] is True
    assert row["updated_at"] is None


def test_base_u_10__real_change_sets_updated_at(db, d_old):
    """BASE-U-10 — a real change sets updated_at.
    Rules: update R7."""
    got = dao.update(db, db_obj=d_old, obj_in={"name": "New"})
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "New"
    assert row["updated_at"] is not None


def test_base_u_11__same_value_no_updated_at(db, d_old):
    """BASE-U-11 — assigning the same value issues no UPDATE; updated_at stays NULL.
    Rules: update R7."""
    got = dao.update(db, db_obj=d_old, obj_in={"name": "Old"})
    assert got is d_old
    row = reread(db, d_old.id)
    assert row["name"] == "Old"
    assert row["updated_at"] is None


def test_base_u_12__flushed_not_committed(db, d_old):
    """BASE-U-12 — update flushes but never commits.
    Rules: update R8."""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        dao.update(db, db_obj=d_old, obj_in={"name": "New"})
        assert raw_row(db, d_old.id)["name"] == "New"
        spy.assert_not_called()
        sp.rollback()
    assert reread(db, d_old.id)["name"] == "Old"


def test_base_u_13__not_null_violation(db, d_old):
    """BASE-U-13 — name=None -> IntegrityError at flush.
    Rules: update R9; Errors row (constraint)."""
    with pytest.raises(IntegrityError), db.begin_nested():
        dao.update(db, db_obj=d_old, obj_in={"name": None})
    assert reread(db, d_old.id)["name"] == "Old"


def test_base_u_14__fk_violation(db, d_old):
    """BASE-U-14 — created_by pointing at no profile -> IntegrityError.
    Rules: update R9; Errors row (constraint)."""
    bad = missing_profile(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        dao.update(db, db_obj=d_old, obj_in={"created_by": bad})
    row = reread(db, d_old.id)
    assert row["created_by"] is None
    assert row["name"] == "Old"


def test_base_u_15__no_audit_stamping(db, w1, p1):
    """BASE-U-15 — update does not stamp updated_by / deleted_by.
    Rules: update R10."""
    d = mk(db, w1, "Old", created_by=p1.id)
    got = dao.update(db, db_obj=d, obj_in={"name": "New"})
    assert got is d
    row = reread(db, d.id)
    assert row["name"] == "New"
    assert row["updated_by"] is None
    assert row["deleted_by"] is None
    assert row["created_by"] == p1.id


# =========================================================================== #
# BaseDAO.remove
# =========================================================================== #

pytestmark_remove = pytest.mark.filterwarnings("ignore::sqlalchemy.exc.LegacyAPIWarning")


@pytestmark_remove
def test_base_r_01__physical_delete(db, w1):
    """BASE-R-01 — remove physically deletes the row and returns it.
    Rules: remove R1, R2."""
    d1 = mk(db, w1, "One")
    d2 = mk(db, w1, "Two")
    d1_id, d2_id = d1.id, d2.id
    got = dao.remove(db, id=d1_id)
    assert isinstance(got, Department)
    assert got.id == d1_id
    assert reread(db, d1_id) is None
    assert reread(db, d2_id)["name"] == "Two"


@pytestmark_remove
def test_base_r_02__flushed_not_committed(db, w1):
    """BASE-R-02 — remove flushes but never commits.
    Rules: remove R2."""
    d1 = mk(db, w1, "One")
    d1_id = d1.id
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        dao.remove(db, id=d1_id)
        assert raw_row(db, d1_id) is None
        spy.assert_not_called()
        sp.rollback()
    assert reread(db, d1_id)["name"] == "One"


@pytestmark_remove
@pytest.mark.xfail(strict=True, reason=BUG_101)
def test_base_r_03__missing_id_returns_none(db, n0, w1):
    """BASE-R-03 — remove of a missing id returns None, deletes nothing.
    Rules: remove R3 [BUG-101]."""
    d1 = mk(db, w1, "One")
    got = dao.remove(db, id=missing(db))
    assert got is None
    assert reread(db, d1.id)["name"] == "One"
    assert count_all(db) == n0 + 1


@pytestmark_remove
def test_base_r_04__fk_restrict_raises(db, w1):
    """BASE-R-04 — a RESTRICT child row blocks the delete with IntegrityError.
    Rules: remove R4; Errors row (FK restrict)."""
    d1 = mk(db, w1, "One")
    d1_id = d1.id
    db.execute(text("SET LOCAL lock_timeout = '10s'"))
    db.execute(text(
        "CREATE TABLE tmp_restrict_child (id serial primary key, department_id int not null "
        "references departments(id) on delete restrict)"
    ))
    db.execute(text("INSERT INTO tmp_restrict_child (department_id) VALUES (:d)"), {"d": d1_id})
    with pytest.raises(IntegrityError), db.begin_nested():
        dao.remove(db, id=d1_id)
    assert reread(db, d1_id) is not None
    assert db.execute(
        text("SELECT count(*) FROM tmp_restrict_child WHERE department_id = :d"), {"d": d1_id}
    ).scalar() == 1


@pytestmark_remove
def test_base_r_05__fk_cascade_deletes_children(db, w1):
    """BASE-R-05 — CASCADE child rows are removed with the department.
    Rules: remove R4."""
    d1 = mk(db, w1, "One")
    d1_id = d1.id
    db.execute(text("SET LOCAL lock_timeout = '10s'"))
    db.execute(text(
        "CREATE TABLE tmp_cascade_child (id serial primary key, department_id int not null "
        "references departments(id) on delete cascade)"
    ))
    db.execute(
        text("INSERT INTO tmp_cascade_child (department_id) VALUES (:d), (:d)"), {"d": d1_id}
    )
    got = dao.remove(db, id=d1_id)
    assert got.id == d1_id
    assert reread(db, d1_id) is None
    assert db.execute(text("SELECT count(*) FROM tmp_cascade_child")).scalar() == 0


@pytestmark_remove
def test_base_r_06__no_workspace_check(db, w1, w2):
    """BASE-R-06 — remove deletes a row of any workspace.
    Rules: remove R5."""
    d1 = mk(db, w1, "One")
    e1 = mk(db, w2, "Other")
    d1_id, e1_id = d1.id, e1.id
    got = dao.remove(db, id=e1_id)
    assert got.id == e1_id
    assert reread(db, e1_id) is None
    assert reread(db, d1_id) is not None


@pytestmark_remove
def test_base_r_07__soft_deleted_row_physically_deleted(db, w1):
    """BASE-R-07 — a soft-deleted row is physically deleted too.
    Rules: remove R2."""
    d1 = mk(db, w1, "Gone", deleted=True)
    d1_id = d1.id
    got = dao.remove(db, id=d1_id)
    assert got.id == d1_id
    assert reread(db, d1_id) is None


# =========================================================================== #
# BaseDAO.get_by_workspace
# =========================================================================== #


def gw(db, ws_id, **kw):
    return dao.get_by_workspace(db, workspace_id=ws_id, **kw)


def test_base_gw_01__workspace_filter(db, w1, w2):
    """BASE-GW-01 — only rows of the given workspace are returned.
    Rules: get_by_workspace R1."""
    d1 = mk(db, w1, "A")
    d2 = mk(db, w1, "B")
    mk(db, w2, "C")
    got = gw(db, w1.id)
    assert isinstance(got, list)
    assert len(got) == 2
    assert set(ids(got)) == {d1.id, d2.id}
    assert all(r.workspace_id == w1.id for r in got)


def test_base_gw_02__default_limit_100(db, w1):
    """BASE-GW-02 — 101 rows: default page 100, skip=100 -> 1.
    Rules: get_by_workspace R2."""
    own_rows(db, w1, 101)
    assert len(gw(db, w1.id)) == 100
    assert len(gw(db, w1.id, skip=100)) == 1


def test_base_gw_03__exactly_100_all_returned(db, w1):
    """BASE-GW-03 — 100 rows: all returned.
    Rules: get_by_workspace R2."""
    rows = own_rows(db, w1, 100)
    got = gw(db, w1.id)
    assert len(got) == 100
    assert set(ids(got)) == set(ids(rows))


def test_base_gw_04__skip_limit_pages(db, w1):
    """BASE-GW-04 — skip/limit page within the workspace.
    Rules: get_by_workspace R2."""
    own_rows(db, w1, 5)
    a = gw(db, w1.id, limit=3)
    b = gw(db, w1.id, skip=3, limit=3)
    assert len(a) == 3
    assert len(b) == 2
    assert all(r.workspace_id == w1.id for r in a + b)


@pytest.mark.xfail(strict=True, reason=BUG_100)
def test_base_gw_05__ordered_by_id(db, w1):
    """BASE-GW-05 — get_by_workspace returns rows in id order; pages are stable.
    Rules: get_by_workspace R3 [BUG-100]."""
    a, b, c = heap_disorder(db, w1)
    force_seqscan(db)
    # (a)
    got = ids(gw(db, w1.id))
    assert got == [a.id, b.id, c.id]
    assert all(x < y for x, y in pairwise(got))
    # (b)
    p1_ = ids(gw(db, w1.id, skip=0, limit=2))
    p2_ = ids(gw(db, w1.id, skip=2, limit=2))
    assert p1_ == [a.id, b.id]
    assert p2_ == [c.id]
    assert p1_ + p2_ == [a.id, b.id, c.id]


def test_base_gw_06__soft_deleted_included_and_counted(db, w1):
    """BASE-GW-06 — soft-deleted rows returned and counted by skip.
    Rules: get_by_workspace R4."""
    d1 = mk(db, w1, "One")
    d2 = mk(db, w1, "Two", deleted=True)
    d3 = mk(db, w1, "Three")
    got = gw(db, w1.id)
    assert len(got) == 3
    assert set(ids(got)) == {d1.id, d2.id, d3.id}
    assert next(r for r in got if r.id == d2.id).is_deleted is True
    assert len(gw(db, w1.id, skip=2)) == 1


def test_base_gw_07__empty_workspace(db, w1, w3):
    """BASE-GW-07 — a workspace without rows -> [].
    Rules: get_by_workspace R5."""
    mk(db, w1, "A")
    assert gw(db, w3.id) == []


def test_base_gw_08__nonexistent_workspace(db, w1):
    """BASE-GW-08 — a non-existent workspace id -> [].
    Rules: get_by_workspace R5."""
    mk(db, w1, "A")
    w404 = (db.scalar(select(func.max(Workspace.id))) or 0) + 1000
    assert gw(db, w404) == []


def test_base_gw_09__skip_at_or_past_end(db, w1):
    """BASE-GW-09 — skip at end -> []; skip=1 -> 1 row.
    Rules: get_by_workspace R5."""
    own_rows(db, w1, 2)
    assert gw(db, w1.id, skip=2) == []
    assert len(gw(db, w1.id, skip=1)) == 1


def test_base_gw_10__limit_zero(db, w1):
    """BASE-GW-10 — limit=0 -> []; limit=1 -> 1 row.
    Rules: get_by_workspace R5."""
    own_rows(db, w1, 2)
    assert gw(db, w1.id, limit=0) == []
    assert len(gw(db, w1.id, limit=1)) == 1


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"skip": -1}, "OFFSET must not be negative", id="BASE-GW-11"),
        pytest.param({"limit": -1}, "LIMIT must not be negative", id="BASE-GW-12"),
    ],
)
def test_base_gw_11_12__negative_skip_or_limit_raises(db, w1, kwargs, message):
    """BASE-GW-11 / BASE-GW-12 — negative skip / limit raises DataError.
    Rules: get_by_workspace R6; Errors row (negative)."""
    own_rows(db, w1, 2)
    with pytest.raises(DataError) as exc, db.begin_nested():
        gw(db, w1.id, **kwargs)
    assert message in str(exc.value)
    assert count_ws(db, w1) == 2


def test_base_gw_13__model_without_workspace_id_raises(db, engine, w1):
    """BASE-GW-13 — model without workspace_id raises AttributeError before any SQL.
    Rules: get_by_workspace R7; Errors row (no workspace_id)."""
    with StatementCounter(engine) as counter, pytest.raises(AttributeError) as exc:
        wdao.get_by_workspace(db, workspace_id=w1.id)
    assert str(exc.value) == "type object 'Workspace' has no attribute 'workspace_id'"
    assert counter.count == 0
    db.expire_all()
    assert db.execute(
        text("SELECT count(*) FROM workspaces WHERE id = :i"), {"i": w1.id}
    ).scalar() == 1


# =========================================================================== #
# BaseDAO.get_by_id_and_workspace
# =========================================================================== #


def test_base_giw_01__match(db, w1):
    """BASE-GIW-01 — id + matching workspace returns the row.
    Rules: get_by_id_and_workspace R1."""
    d1 = mk(db, w1, "Sales")
    mk(db, w1, "Ops")
    got = dao.get_by_id_and_workspace(db, id=d1.id, workspace_id=w1.id)
    assert isinstance(got, Department)
    assert got.id == d1.id
    assert got.name == "Sales"
    assert got.workspace_id == w1.id


def test_base_giw_02__other_workspace_none(db, w1, w2):
    """BASE-GIW-02 — id of another workspace -> None, row still exists.
    Rules: get_by_id_and_workspace R2."""
    d1 = mk(db, w1, "Sales")
    mk(db, w2, "Other")
    assert dao.get_by_id_and_workspace(db, id=d1.id, workspace_id=w2.id) is None
    still = dao.get(db, id=d1.id)
    assert still is not None and still.id == d1.id


def test_base_giw_03__missing_id_none(db, w1):
    """BASE-GIW-03 — a missing id -> None.
    Rules: get_by_id_and_workspace R3."""
    mk(db, w1, "Sales")
    assert dao.get_by_id_and_workspace(db, id=missing(db), workspace_id=w1.id) is None


def test_base_giw_04__soft_deleted_returned(db, w1):
    """BASE-GIW-04 — a soft-deleted row is returned.
    Rules: get_by_id_and_workspace R4."""
    d1 = mk(db, w1, "Gone", deleted=True)
    got = dao.get_by_id_and_workspace(db, id=d1.id, workspace_id=w1.id)
    assert got.id == d1.id
    assert got.is_deleted is True


def test_base_giw_05__model_without_workspace_id_raises(db, w1):
    """BASE-GIW-05 — model without workspace_id raises AttributeError.
    Rules: get_by_id_and_workspace R5; Errors row (no workspace_id)."""
    with pytest.raises(AttributeError) as exc:
        wdao.get_by_id_and_workspace(db, id=w1.id, workspace_id=w1.id)
    assert str(exc.value) == "type object 'Workspace' has no attribute 'workspace_id'"
    db.expire_all()
    assert db.execute(
        text("SELECT count(*) FROM workspaces WHERE id = :i"), {"i": w1.id}
    ).scalar() == 1
