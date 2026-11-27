"""Unit tests for app/dao/item_tag.py.

Implements tests/unit/dao/item_tag.cases.md, one test per case. Real Postgres
session (`db` fixture). Nothing is patched (Conventions, Externals: None).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/item_tag.helpers.md as its only view of this file; tests below a
`# [claude] <ID>` comment are the `Author: claude` cards, written by hand at
finishing.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    NotNullViolation,
    StringDataRightTruncation,
)
from sqlalchemy import event, func, insert, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.item_tag import item_tag_dao
from app.models.item_tag import ItemTag
from app.schemas.item_tag import ItemTagCreate, ItemTagUpdate
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton item_tag_dao" (a module-level name, not a fixture)
dao = item_tag_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (W1, W2: they exist in every test)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise
# in the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "They exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

def _tag_fields(default_workspace_id, name, tag_code, **columns):
    fields = {
        "workspace_id": default_workspace_id, "name": name, "tag_code": tag_code,
        "is_system_tag": False, "is_active": True, "usage_count": 0,
        "color": None, "icon": None, "description": None, "created_by": None,
    }
    fields.update(columns)
    return fields


# Convention "tag" (and "deleted" = the keyword is_active=False, written out by every card)
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name=..., tag_code=..., **columns) -> ItemTag. Keywords only.

    Conventions defaults: W1, not a system tag, active, usage_count 0, colour /
    icon / description / created_by None; `created_at` is left to the model
    default. Each column the card lists after "but" is one more keyword.
    """
    def _mk(*, name, tag_code, **columns):
        return _add(db, ItemTag(**_tag_fields(w1.id, name, tag_code, **columns)))
    return _mk


# Convention "system tag" = a tag, but is_system_tag True
@pytest.fixture
def mk_system_tag(db, w1):
    """mk_system_tag(name=..., tag_code=..., **columns) -> ItemTag. Keywords only."""
    def _mk(*, name, tag_code, **columns):
        return _add(db, ItemTag(**_tag_fields(w1.id, name, tag_code, is_system_tag=True, **columns)))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {"item_tags": ItemTag.__table__}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of the tag `row` from the database, or None if it is gone."""
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(ItemTag).where(ItemTag.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = ItemTag.__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "stored_count(T)": the database value, without expiring or refreshing T
def stored_count(db, row):
    return db.scalar(select(ItemTag.usage_count).where(ItemTag.id == _id_of(row)))


# Convention "count:" lines: rows of item_tags in all workspaces, with the filter stated
def count_rows(db, table_name, **where):
    table = _TABLES[table_name]
    stmt = select(func.count()).select_from(table)
    for column, value in where.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": the number of item_tags rows (all workspaces)
def written(db):
    return count_rows(db, "item_tags")


# Convention "ids(result)" / "names(result)": in the order returned
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "close to now" (Spec gap 6): within 5 minutes of the test's clock
def close_to_now(value):
    return abs(datetime.now(timezone.utc).replace(tzinfo=None) - value) < timedelta(minutes=5)


# --------------------------------------------------------------------------- #
# Setup and reading helpers of the `Author: claude` cards (not in the helper sheet)
# --------------------------------------------------------------------------- #

# Bulk Given rows of ITG-SYS-07 (system tags) and ITG-ACT-08 (tags): one multi-row INSERT
# with the Conventions "tag" columns; ids rise in list order. `created_at` is left to the
# model's Python default (applied per row by the Core insert).
def bulk_tags(db, workspace, rows, *, is_system_tag):
    """Insert one tag per (name, tag_code) pair, in order. Returns their ids in insertion order."""
    table = ItemTag.__table__
    inserted = db.execute(
        insert(table).returning(table.c.id, sort_by_parameter_order=True),
        [_tag_fields(workspace.id, name, tag_code, is_system_tag=is_system_tag) for name, tag_code in rows],
    ).scalars().all()
    return list(inserted)


# "Statement recorder" (Conventions; ITG-SYS-10, ACT-13, INH-19): the SQL text of every
# statement the session's connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def updates(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("UPDATE")]


# Convention "relative update" (BUG-931, ITG-INC-11, DEC-13): an UPDATE of item_tags whose
# SET computes the counter from the stored column (`usage_count = usage_count + / - ...`);
# for the decrease, the same statement's WHERE also tests the stored column (`usage_count >`).
_REL_INC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:item_tags\.)?usage_count\s*\+", re.IGNORECASE)
_REL_DEC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:item_tags\.)?usage_count\s*-", re.IGNORECASE)
_DEC_GUARD = re.compile(r"WHERE.*usage_count\s*>", re.IGNORECASE | re.DOTALL)


# Convention "order_part": the text of `sql` after `ORDER BY` ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in item_tag.helpers.md)
# --------------------------------------------------------------------------- #

def test_itg_code_03__the_same_code_in_two_workspaces_each_workspace_gets_its_own_tag(db, w2, mk_tag):
    """ITG-CODE-03 — the same code in two workspaces: each workspace gets its own tag.
    Rules: `get_by_code_in_workspace` R1"""
    mk_tag(name="Raw Material", tag_code="raw_material")
    t9 = mk_tag(name="Raw Stock", tag_code="raw_material", workspace_id=w2.id)

    result = dao.get_by_code_in_workspace(db, workspace_id=w2.id, tag_code="raw_material")

    # Then 1
    assert result.id == t9.id
    # Then 2
    assert result.workspace_id == w2.id


def test_itg_act_01__returns_a_list_of_the_system_and_user_tags_of_the_workspace_and(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-01 — returns a list of the system and user tags of the workspace and writes nothing.
    Rules: `get_active_tags_in_workspace` R1, R5, Returns"""
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")
    t2 = mk_tag(name="Spare Part", tag_code="spare_part")
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    before = written(db)
    before_t1 = snap(db, t1)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [t1.id, t2.id, s1.id]
    # Then 3
    assert isinstance(result[0], ItemTag)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, t1) == before_t1


def test_itg_inc_01__the_counter_goes_up_by_one_flushed_and_the_session_s_tag_object_is(db, w1, mk_tag):
    """ITG-INC-01 — the counter goes up by one, flushed, and the session's tag object is returned.
    Rules: `increment_usage_count` R1, R6, Returns"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=2)
    before = written(db)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 3
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert written(db) == before


def test_itg_dec_04__at_0_nothing_is_flushed_another_pending_change_stays_unsaved(db, w1, mk_tag):
    """ITG-DEC-04 — at 0 nothing is flushed: another pending change stays unsaved.
    Rules: `decrement_usage_count` R2"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")
    t1.name = "Lock Nut"

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Hex Bolt"
    # Then 3
    assert row.usage_count == 0


def test_itg_inh_05__create_with_an_unknown_workspace_id_fails_on_flush_and_saves_nothing(db):
    """ITG-INH-05 — create with an unknown workspace_id fails on flush and saves nothing.
    Rules: inherited R2, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "name": "Spare Part", "tag_code": "spare_part"})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tags_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


def test_itg_inh_01__create_with_a_dict_stores_a_tag_with_the_model_defaults(db, w1):
    """ITG-INH-01 — create with a dict stores a tag with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Spare Part"
    assert row.tag_code == "spare_part"
    # Then 3
    assert row.is_system_tag is False
    assert row.is_active is True
    assert row.usage_count == 0
    # Then 4
    assert row.created_by is None
    assert row.color is None
    assert row.icon is None
    assert row.description is None
    # Then 5
    assert row.created_at.tzinfo is None
    # Then 6
    assert close_to_now(row.created_at)
    # Then 7
    assert count_rows(db, "item_tags") == 1


# --------------------------------------------------------------------------- #
# ItemTagDAO.get_by_code_in_workspace
# --------------------------------------------------------------------------- #


# [local-coder] ITG-CODE-01
def test_itg_code_01__returns_the_tag_of_the_workspace_with_that_code_and_writes_nothing(db, w1, mk_tag):
    """ITG-CODE-01 — returns the tag of the workspace with that code and writes nothing.
    Rules: `get_by_code_in_workspace` R1, R5"""
    t1 = mk_tag(name="Raw Material", tag_code="raw_material")
    mk_tag(name="Machine Part", tag_code="machine_part")
    before = written(db)
    before_t1 = snap(db, t1)

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw_material")

    # Then 1
    assert isinstance(result, ItemTag)
    # Then 2
    assert result.id == t1.id
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, t1) == before_t1


# [local-coder] ITG-CODE-02
def test_itg_code_02__a_tag_of_another_workspace_with_that_code_is_not_returned(db, w1, w2, mk_tag):
    """ITG-CODE-02 — a tag of another workspace with that code is not returned.
    Rules: `get_by_code_in_workspace` R1"""
    mk_tag(name="Raw Material", tag_code="raw_material")
    mk_tag(name="Spare Part", tag_code="spare_part", workspace_id=w2.id)

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="spare_part")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-04
def test_itg_code_04__an_unknown_workspace_id_returns_none(db, mk_tag):
    """ITG-CODE-04 — an unknown workspace id returns None.
    Rules: `get_by_code_in_workspace` R1"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=MISSING, tag_code="raw_material")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-05
def test_itg_code_05__a_code_differing_in_the_case_of_some_letters_returns_none(db, w1, mk_tag):
    """ITG-CODE-05 — a code differing in the case of some letters returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="Raw_Material")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-06
def test_itg_code_06__an_all_capitals_code_returns_none(db, w1, mk_tag):
    """ITG-CODE-06 — an all-capitals code returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="RAW_MATERIAL")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-07
def test_itg_code_07__a_leading_space_returns_none(db, w1, mk_tag):
    """ITG-CODE-07 — a leading space returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code=" raw_material")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-08
def test_itg_code_08__a_trailing_space_returns_none(db, w1, mk_tag):
    """ITG-CODE-08 — a trailing space returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw_material ")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-09
def test_itg_code_09__a_prefix_of_the_code_returns_none(db, w1, mk_tag):
    """ITG-CODE-09 — a prefix of the code returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-10
def test_itg_code_10__the_code_with_one_more_character_returns_none(db, w1, mk_tag):
    """ITG-CODE-10 — the code with one more character returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw_material_")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-11
def test_itg_code_11__a_like_pattern_is_not_a_pattern_raw_returns_none(db, w1, mk_tag):
    """ITG-CODE-11 — a LIKE pattern is not a pattern: "raw%" returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw%")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-12
def test_itg_code_12__an_empty_code_finds_a_tag_stored_with_an_empty_code(db, w1, mk_tag):
    """ITG-CODE-12 — an empty code finds a tag stored with an empty code.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")
    t2 = mk_tag(name="Blank Mark", tag_code="")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="")

    # Then 1
    assert result.id == t2.id
    # Then 2
    assert result.tag_code == ""


# [local-coder] ITG-CODE-13
def test_itg_code_13__an_empty_code_returns_none_when_no_tag_has_an_empty_code(db, w1, mk_tag):
    """ITG-CODE-13 — an empty code returns None when no tag has an empty code.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="")

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-14
def test_itg_code_14__a_code_of_none_returns_none(db, w1, mk_tag):
    """ITG-CODE-14 — a code of None returns None.
    Rules: `get_by_code_in_workspace` R2"""
    mk_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code=None)

    # Then 1
    assert result is None


# [local-coder] ITG-CODE-15
def test_itg_code_15__a_deleted_tag_is_found_by_its_code_and_left_as_it_was(db, w1, mk_tag):
    """ITG-CODE-15 — a deleted tag is found by its code and left as it was.
    Rules: `get_by_code_in_workspace` R3 (P1), R5"""
    td = mk_tag(name="Spare Part", tag_code="spare_part", is_active=False)
    before_td = snap(db, td)

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="spare_part")

    # Then 1
    assert result.id == td.id
    # Then 2
    assert result.is_active is False
    # Then 3
    assert snap(db, td) == before_td


# [local-coder] ITG-CODE-16
def test_itg_code_16__a_system_tag_is_found_by_its_code(db, w1, mk_system_tag):
    """ITG-CODE-16 — a system tag is found by its code.
    Rules: `get_by_code_in_workspace` R3"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw_material")

    # Then 1
    assert result.id == s1.id
    # Then 2
    assert result.is_system_tag is True


# [local-coder] ITG-CODE-17
def test_itg_code_17__two_tags_with_one_code_one_of_them_is_returned(db, w1, mk_tag):
    """ITG-CODE-17 — two tags with one code: one of them is returned.
    Rules: `get_by_code_in_workspace` R4"""
    t1 = mk_tag(name="Bolt Small", tag_code="bolt_part")
    t2 = mk_tag(name="Bolt Large", tag_code="bolt_part")
    before = written(db)

    result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="bolt_part")

    # Then 1
    assert result.id in {t1.id, t2.id}
    # Then 2
    assert written(db) == before


# --------------------------------------------------------------------------- #
# ItemTagDAO.get_system_tags_in_workspace
# --------------------------------------------------------------------------- #


# [local-coder] ITG-SYS-01
def test_itg_sys_01__returns_a_list_of_the_system_tags_of_the_workspace_no_user_tag_and(db, w1, mk_tag, mk_system_tag):
    """ITG-SYS-01 — returns a list of the system tags of the workspace, no user tag, and writes nothing.
    Rules: `get_system_tags_in_workspace` R1, R4, Returns"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    s2 = mk_system_tag(name="Machine Part", tag_code="machine_part")
    mk_tag(name="Custom Bin", tag_code="custom_bin")
    before = written(db)
    before_s1 = snap(db, s1)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [s1.id, s2.id]
    # Then 3
    assert isinstance(result[0], ItemTag)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, s1) == before_s1


# [local-coder] ITG-SYS-02
def test_itg_sys_02__a_deleted_system_tag_is_not_returned(db, w1, mk_system_tag):
    """ITG-SYS-02 — a deleted system tag is not returned.
    Rules: `get_system_tags_in_workspace` R1"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    sd = mk_system_tag(name="Old Seed", tag_code="old_seed", is_active=False)
    before_sd = snap(db, sd)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert snap(db, sd) == before_sd


# [local-coder] ITG-SYS-03
def test_itg_sys_03__a_system_tag_of_another_workspace_is_not_returned(db, w1, w2, mk_system_tag):
    """ITG-SYS-03 — a system tag of another workspace is not returned.
    Rules: `get_system_tags_in_workspace` R1"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    mk_system_tag(name="Far Seed", tag_code="far_seed", workspace_id=w2.id)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [local-coder] ITG-SYS-04
def test_itg_sys_04__the_other_workspace_gets_only_its_own_system_tag(db, w2, mk_system_tag):
    """ITG-SYS-04 — the other workspace gets only its own system tag.
    Rules: `get_system_tags_in_workspace` R1"""
    mk_system_tag(name="Raw Material", tag_code="raw_material")
    s9 = mk_system_tag(name="Far Seed", tag_code="far_seed", workspace_id=w2.id)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s9.id]


# [local-coder] ITG-SYS-05
def test_itg_sys_05__an_unknown_workspace_id_returns_an_empty_list(db, mk_system_tag):
    """ITG-SYS-05 — an unknown workspace id returns an empty list.
    Rules: `get_system_tags_in_workspace` R1"""
    mk_system_tag(name="Raw Material", tag_code="raw_material")

    result = dao.get_system_tags_in_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] ITG-SYS-06
def test_itg_sys_06__a_workspace_with_only_user_tags_and_a_deleted_system_tag_returns_an(db, w1, mk_tag, mk_system_tag):
    """ITG-SYS-06 — a workspace with only user tags and a deleted system tag returns an empty list.
    Rules: `get_system_tags_in_workspace` R1"""
    mk_tag(name="Custom Bin", tag_code="custom_bin")
    mk_system_tag(name="Old Seed", tag_code="old_seed", is_active=False)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] ITG-SYS-07
def test_itg_sys_07__all_101_system_tags_are_returned_no_limit(db, w1):
    """ITG-SYS-07 — all 101 system tags are returned (no limit).
    Rules: `get_system_tags_in_workspace` R2"""
    n_ids = bulk_tags(db, w1, [(f"Seed {k:03d}", f"seed_{k:03d}") for k in range(1, 102)], is_system_tag=True)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(n_ids)


# [claude] ITG-SYS-08
@pytest.mark.xfail(
    strict=False,
    reason="BUG-929: System tag list has no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_itg_sys_08__system_tags_come_back_by_name_case_insensitive_ascending(db, w1, mk_system_tag):
    """ITG-SYS-08 — system tags come back by name, case-insensitive ascending.
    Rules: `get_system_tags_in_workspace` R3 [BUG-929]"""
    s1 = mk_system_tag(name="Tool", tag_code="tool")
    s2 = mk_system_tag(name="consumable", tag_code="consumable")
    s3 = mk_system_tag(name="Bolt", tag_code="bolt")

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id, s3.id]
    # Then 2
    assert names(result) == ["Bolt", "consumable", "Tool"]


# [claude] ITG-SYS-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-929: System tag list has no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_itg_sys_09__system_tags_whose_names_differ_only_in_case_come_back_in_id_order(db, w1, mk_system_tag):
    """ITG-SYS-09 — system tags whose names differ only in case come back in id order.
    Rules: `get_system_tags_in_workspace` R3 [BUG-929]"""
    s1 = mk_system_tag(name="Alpha", tag_code="alpha_upper")
    s2 = mk_system_tag(name="alpha", tag_code="alpha_lower")
    s1.description = "moved"
    db.flush()

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id]
    # Then 2
    assert ids(result) == [s1.id, s2.id]


# [claude] ITG-SYS-10
@pytest.mark.xfail(strict=True, reason="BUG-929: System tag list has no sort order")
def test_itg_sys_10__the_system_tag_query_asks_the_database_for_name_case_insensitive_then_id(db, w1, mk_system_tag):
    """ITG-SYS-10 — the system-tag query asks the database for name case-insensitive, then id.
    Rules: `get_system_tags_in_workspace` R3 [BUG-929]"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")

    with StatementRecorder(db) as recorder:
        result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(item_tags.name)" in order_part
    # Then 4
    assert "item_tags.id" in order_part


# --------------------------------------------------------------------------- #
# ItemTagDAO.get_active_tags_in_workspace
# --------------------------------------------------------------------------- #


# [local-coder] ITG-ACT-02
def test_itg_act_02__a_deleted_user_tag_is_not_returned(db, w1, mk_tag):
    """ITG-ACT-02 — a deleted user tag is not returned.
    Rules: `get_active_tags_in_workspace` R1"""
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False)
    before_td = snap(db, td)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert snap(db, td) == before_td


# [local-coder] ITG-ACT-03
def test_itg_act_03__a_deleted_system_tag_is_not_returned(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-03 — a deleted system tag is not returned.
    Rules: `get_active_tags_in_workspace` R1"""
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")
    mk_system_tag(name="Old Seed", tag_code="old_seed", is_active=False)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [local-coder] ITG-ACT-04
def test_itg_act_04__a_tag_of_another_workspace_is_not_returned(db, w1, w2, mk_tag):
    """ITG-ACT-04 — a tag of another workspace is not returned.
    Rules: `get_active_tags_in_workspace` R1"""
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")
    mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [local-coder] ITG-ACT-05
def test_itg_act_05__the_other_workspace_gets_only_its_own_tag(db, w2, mk_tag):
    """ITG-ACT-05 — the other workspace gets only its own tag.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Custom Bin", tag_code="custom_bin")
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [t9.id]


# [local-coder] ITG-ACT-06
def test_itg_act_06__an_unknown_workspace_id_returns_an_empty_list(db, mk_tag):
    """ITG-ACT-06 — an unknown workspace id returns an empty list.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Custom Bin", tag_code="custom_bin")

    result = dao.get_active_tags_in_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [local-coder] ITG-ACT-07
def test_itg_act_07__a_workspace_without_tags_returns_an_empty_list(db, w1, w2, mk_tag):
    """ITG-ACT-07 — a workspace without tags returns an empty list.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] ITG-ACT-08
def test_itg_act_08__all_101_tags_are_returned_no_limit(db, w1):
    """ITG-ACT-08 — all 101 tags are returned (no limit).
    Rules: `get_active_tags_in_workspace` R2"""
    n_ids = bulk_tags(db, w1, [(f"Crate {k:03d}", f"crate_{k:03d}") for k in range(1, 102)], is_system_tag=False)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(n_ids)


# [local-coder] ITG-ACT-09
def test_itg_act_09__every_system_tag_comes_before_every_user_tag(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-09 — every system tag comes before every user tag.
    Rules: `get_active_tags_in_workspace` R3"""
    mk_tag(name="Anchor", tag_code="anchor")
    mk_tag(name="Bracket", tag_code="bracket")
    s1 = mk_system_tag(name="Zinc Plate", tag_code="zinc_plate")
    s2 = mk_system_tag(name="Yarn Spool", tag_code="yarn_spool")

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert [t.is_system_tag for t in result] == [True, True, False, False]
    # Then 2
    assert sorted(t.id for t in result[:2]) == [s1.id, s2.id]


# [local-coder] ITG-ACT-10
def test_itg_act_10__within_each_group_lower_case_names_come_back_in_alphabetical_order(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-10 — within each group, lower-case names come back in alphabetical order.
    Rules: `get_active_tags_in_workspace` R3, R4 (the part that holds today: names with one case only)"""
    mk_tag(name="delta", tag_code="delta")
    mk_tag(name="alpha", tag_code="alpha")
    mk_system_tag(name="yarn", tag_code="yarn")
    mk_system_tag(name="bolt", tag_code="bolt")

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert names(result) == ["bolt", "yarn", "alpha", "delta"]


# [claude] ITG-ACT-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-930: Active tag list sorted by collation name with no tie-break "
    "(non-strict: the outcome depends on the server's collation, not on this code alone)",
)
def test_itg_act_11__names_that_differ_only_in_case_come_back_in_id_order_then_the_other_names(db, w1, mk_tag):
    """ITG-ACT-11 — names that differ only in case come back in id order, then the other names case-insensitively.
    Rules: `get_active_tags_in_workspace` R4 [BUG-930]"""
    t1 = mk_tag(name="bravo", tag_code="bravo")
    t2 = mk_tag(name="Alpha", tag_code="alpha_upper")
    t3 = mk_tag(name="alpha", tag_code="alpha_lower")
    t4 = mk_tag(name="Charlie", tag_code="charlie")

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id, t3.id, t4.id]
    # Then 2
    assert ids(result) == [t2.id, t3.id, t1.id, t4.id]


# [claude] ITG-ACT-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-930: Active tag list sorted by collation name with no tie-break "
    "(non-strict: today's order of equal names is the physical row order, which can match by accident)",
)
def test_itg_act_12__two_tags_with_the_same_name_come_back_lower_id_first(db, w1, mk_tag):
    """ITG-ACT-12 — two tags with the same name come back lower id first.
    Rules: `get_active_tags_in_workspace` R4 [BUG-930]"""
    t1 = mk_tag(name="Bolt", tag_code="bolt_a")
    t2 = mk_tag(name="Bolt", tag_code="bolt_b")
    t1.description = "moved"
    db.flush()

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id]
    # Then 2
    assert ids(result) == [t1.id, t2.id]


# [claude] ITG-ACT-13
@pytest.mark.xfail(strict=True, reason="BUG-930: Active tag list sorted by collation name with no tie-break")
def test_itg_act_13__the_active_tag_query_asks_for_system_first_then_name_case_insensitive(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-13 — the active-tag query asks for system first, then name case-insensitive, then id.
    Rules: `get_active_tags_in_workspace` R3, R4 [BUG-930]"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")

    with StatementRecorder(db) as recorder:
        result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [s1.id, t1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "item_tags.is_system_tag DESC" in order_part
    # Then 4
    assert "lower(item_tags.name)" in order_part
    # Then 5
    assert "item_tags.id" in order_part


# --------------------------------------------------------------------------- #
# ItemTagDAO.increment_usage_count
# --------------------------------------------------------------------------- #


# [local-coder] ITG-INC-02
def test_itg_inc_02__a_counter_of_0_becomes_1(db, w1, mk_tag):
    """ITG-INC-02 — a counter of 0 becomes 1.
    Rules: `increment_usage_count` R1"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == 1


# [local-coder] ITG-INC-03
def test_itg_inc_03__an_unknown_tag_id_returns_none_writes_nothing_and_raises_nothing(db, w1, mk_tag):
    """ITG-INC-03 — an unknown tag id returns None, writes nothing and raises nothing.
    Rules: `increment_usage_count` R2 (Q2)"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=2)
    before = written(db)
    before_t1 = snap(db, t1)

    result = dao.increment_usage_count(db, tag_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, t1) == before_t1


# [local-coder] ITG-INC-04
def test_itg_inc_04__a_tag_of_another_workspace_returns_none_and_its_counter_stays(db, w1, w2, mk_tag):
    """ITG-INC-04 — a tag of another workspace returns None and its counter stays.
    Rules: `increment_usage_count` R2 (Q2)"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id, usage_count=5)
    before_t9 = snap(db, t9)

    result = dao.increment_usage_count(db, tag_id=t9.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db, t9) == 5
    # Then 3
    assert snap(db, t9) == before_t9


# [local-coder] ITG-INC-05
def test_itg_inc_05__the_tag_s_own_workspace_counts_it(db, w2, mk_tag):
    """ITG-INC-05 — the tag's own workspace counts it.
    Rules: `increment_usage_count` R1"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id, usage_count=5)

    result = dao.increment_usage_count(db, tag_id=t9.id, workspace_id=w2.id)

    # Then 1
    assert result is t9
    # Then 2
    row = reread(db, t9)
    assert row.usage_count == 6


# [local-coder] ITG-INC-06
def test_itg_inc_06__a_deleted_tag_is_counted_like_any_other(db, w1, mk_tag):
    """ITG-INC-06 — a deleted tag is counted like any other.
    Rules: `increment_usage_count` R3 (P2)"""
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False, usage_count=2)

    result = dao.increment_usage_count(db, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is td
    # Then 2
    row = reread(db, td)
    assert row.usage_count == 3
    # Then 3
    assert row.is_active is False


# [local-coder] ITG-INC-07
def test_itg_inc_07__a_system_tag_is_counted_like_any_other(db, w1, mk_system_tag):
    """ITG-INC-07 — a system tag is counted like any other.
    Rules: `increment_usage_count` R3"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material", usage_count=4)

    result = dao.increment_usage_count(db, tag_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.usage_count == 5


# [local-coder] ITG-INC-08
def test_itg_inc_08__a_negative_stored_counter_goes_up_by_one(db, w1, mk_tag):
    """ITG-INC-08 — a negative stored counter goes up by one.
    Rules: `increment_usage_count` R4"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=-2)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == -1


# [local-coder] ITG-INC-09
def test_itg_inc_09__only_the_counter_of_that_tag_changes(db, w1, mk_tag):
    """ITG-INC-09 — only the counter of that tag changes.
    Rules: `increment_usage_count` Side effects"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=4, color="#AA3300", icon="bolt", description="M8 bolts")
    t2 = mk_tag(name="Lock Nut", tag_code="lock_nut", usage_count=4)
    before = written(db)
    before_t2 = snap(db, t2)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == 5
    # Then 3
    assert row.name == "Hex Bolt"
    assert row.tag_code == "hex_bolt"
    assert row.workspace_id == w1.id
    # Then 4
    assert row.color == "#AA3300"
    assert row.icon == "bolt"
    assert row.description == "M8 bolts"
    # Then 5
    assert row.is_active is True
    assert row.is_system_tag is False
    assert row.created_by is None
    # Then 6
    assert snap(db, t2) == before_t2
    # Then 7
    assert written(db) == before


# [local-coder] ITG-INC-10
def test_itg_inc_10__the_flush_also_saves_another_pending_change_of_the_same_tag(db, w1, mk_tag):
    """ITG-INC-10 — the flush also saves another pending change of the same tag.
    Rules: `increment_usage_count` R6"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=2)
    t1.name = "Lock Nut"

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Lock Nut"
    # Then 3
    assert row.usage_count == 3


# [claude] ITG-INC-11
@pytest.mark.xfail(strict=True, reason="BUG-931: Tag usage counter can lose concurrent changes")
def test_itg_inc_11__the_increase_is_applied_to_the_stored_value_not_to_the_loaded_one(db, w1, mk_tag):
    """ITG-INC-11 — the increase is applied to the stored value, not to the loaded one.
    Rules: `increment_usage_count` R5 [BUG-931]"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": t1.id})

    with StatementRecorder(db) as recorder:
        result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 11
    # Then 3
    assert stored_count(db, t1) == 11
    # Then 4
    assert any(_REL_INC.search(s) for s in recorder.updates())


# [claude] ITG-INC-12
def test_itg_inc_12__with_the_object_expired_first_the_increase_starts_from_the_stored_value(db, w1, mk_tag):
    """ITG-INC-12 — with the object expired first, the increase starts from the stored value.
    Rules: `increment_usage_count` R5 (the control that holds today), R1"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": t1.id})
    db.expire(t1)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert stored_count(db, t1) == 11


# [claude] ITG-INC-13
def test_itg_inc_13__the_increase_is_flushed_but_not_committed_a_rollback_restores_the_old(db, w1, mk_tag):
    """ITG-INC-13 — the increase is flushed but not committed: a rollback restores the old value.
    Rules: `increment_usage_count` R6"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=2)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

        # Then 1
        assert result is t1
        # Then 2
        assert stored_count(db, t1) == 3
        sp.rollback()
        # Then 3
        row = reread(db, t1)
        assert row.usage_count == 2
        # Then 4
        assert commit_spy.call_count == 0


# --------------------------------------------------------------------------- #
# ItemTagDAO.decrement_usage_count
# --------------------------------------------------------------------------- #


# [local-coder] ITG-DEC-01
def test_itg_dec_01__the_counter_goes_down_by_one_flushed_and_the_session_s_tag_object_is(db, w1, mk_tag):
    """ITG-DEC-01 — the counter goes down by one, flushed, and the session's tag object is returned.
    Rules: `decrement_usage_count` R1, R7, Returns"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    before = written(db)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 2
    # Then 3
    assert stored_count(db, t1) == 2
    # Then 4
    assert written(db) == before


# [local-coder] ITG-DEC-02
def test_itg_dec_02__a_counter_of_1_becomes_0(db, w1, mk_tag):
    """ITG-DEC-02 — a counter of 1 becomes 0.
    Rules: `decrement_usage_count` R1"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=1)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == 0


# [local-coder] ITG-DEC-03
def test_itg_dec_03__a_counter_of_0_stays_0_and_the_tag_is_returned(db, w1, mk_tag):
    """ITG-DEC-03 — a counter of 0 stays 0 and the tag is returned.
    Rules: `decrement_usage_count` R2"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")
    before_t1 = snap(db, t1)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 0
    # Then 3
    row = reread(db, t1)
    assert row.usage_count == 0
    # Then 4
    assert snap(db, t1) == before_t1


# [local-coder] ITG-DEC-05
def test_itg_dec_05__a_negative_stored_counter_is_left_as_it_is_and_the_tag_is_returned(db, w1, mk_tag):
    """ITG-DEC-05 — a negative stored counter is left as it is and the tag is returned.
    Rules: `decrement_usage_count` R3"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=-2)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == -2
    # Then 3
    row = reread(db, t1)
    assert row.usage_count == -2


# [local-coder] ITG-DEC-06
def test_itg_dec_06__an_unknown_tag_id_returns_none_writes_nothing_and_raises_nothing(db, w1, mk_tag):
    """ITG-DEC-06 — an unknown tag id returns None, writes nothing and raises nothing.
    Rules: `decrement_usage_count` R4 (Q2)"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    before = written(db)
    before_t1 = snap(db, t1)

    result = dao.decrement_usage_count(db, tag_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, t1) == before_t1


# [local-coder] ITG-DEC-07
def test_itg_dec_07__a_tag_of_another_workspace_returns_none_and_its_counter_stays(db, w1, w2, mk_tag):
    """ITG-DEC-07 — a tag of another workspace returns None and its counter stays.
    Rules: `decrement_usage_count` R4 (Q2)"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id, usage_count=5)
    before_t9 = snap(db, t9)

    result = dao.decrement_usage_count(db, tag_id=t9.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db, t9) == 5
    # Then 3
    assert snap(db, t9) == before_t9


# [local-coder] ITG-DEC-08
def test_itg_dec_08__the_tag_s_own_workspace_decrements_it(db, w2, mk_tag):
    """ITG-DEC-08 — the tag's own workspace decrements it.
    Rules: `decrement_usage_count` R1"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id, usage_count=5)

    result = dao.decrement_usage_count(db, tag_id=t9.id, workspace_id=w2.id)

    # Then 1
    assert result is t9
    # Then 2
    row = reread(db, t9)
    assert row.usage_count == 4


# [local-coder] ITG-DEC-09
def test_itg_dec_09__a_deleted_tag_is_decremented_like_any_other(db, w1, mk_tag):
    """ITG-DEC-09 — a deleted tag is decremented like any other.
    Rules: `decrement_usage_count` R5 (P2)"""
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False, usage_count=3)

    result = dao.decrement_usage_count(db, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is td
    # Then 2
    row = reread(db, td)
    assert row.usage_count == 2
    # Then 3
    assert row.is_active is False


# [local-coder] ITG-DEC-10
def test_itg_dec_10__a_system_tag_is_decremented_like_any_other(db, w1, mk_system_tag):
    """ITG-DEC-10 — a system tag is decremented like any other.
    Rules: `decrement_usage_count` R5"""
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material", usage_count=4)

    result = dao.decrement_usage_count(db, tag_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.usage_count == 3


# [local-coder] ITG-DEC-11
def test_itg_dec_11__only_the_counter_of_that_tag_changes(db, w1, mk_tag):
    """ITG-DEC-11 — only the counter of that tag changes.
    Rules: `decrement_usage_count` Side effects"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=4, color="#AA3300", icon="bolt", description="M8 bolts")
    t2 = mk_tag(name="Lock Nut", tag_code="lock_nut", usage_count=4)
    before_t2 = snap(db, t2)
    before = written(db)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == 3
    # Then 3
    assert row.name == "Hex Bolt"
    assert row.tag_code == "hex_bolt"
    assert row.workspace_id == w1.id
    # Then 4
    assert row.color == "#AA3300"
    assert row.icon == "bolt"
    assert row.description == "M8 bolts"
    # Then 5
    assert row.is_active is True
    assert row.is_system_tag is False
    assert row.created_by is None
    # Then 6
    assert snap(db, t2) == before_t2
    # Then 7
    assert written(db) == before


# [local-coder] ITG-DEC-12
def test_itg_dec_12__when_a_value_is_written_the_flush_also_saves_another_pending_change(db, w1, mk_tag):
    """ITG-DEC-12 — when a value is written, the flush also saves another pending change of the same tag.
    Rules: `decrement_usage_count` R7"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    t1.name = "Lock Nut"

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Lock Nut"
    # Then 3
    assert row.usage_count == 2


# [claude] ITG-DEC-13
@pytest.mark.xfail(strict=True, reason="BUG-931: Tag usage counter can lose concurrent changes")
def test_itg_dec_13__the_decrease_is_applied_to_the_stored_value_not_to_the_loaded_one(db, w1, mk_tag):
    """ITG-DEC-13 — the decrease is applied to the stored value, not to the loaded one.
    Rules: `decrement_usage_count` R6 [BUG-931]"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": t1.id})

    with StatementRecorder(db) as recorder:
        result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 9
    # Then 3
    assert stored_count(db, t1) == 9
    # Then 4
    assert any(_REL_DEC.search(s) and _DEC_GUARD.search(s) for s in recorder.updates())


# [claude] ITG-DEC-14
@pytest.mark.xfail(strict=True, reason="BUG-931: Tag usage counter can lose concurrent changes")
def test_itg_dec_14__the_not_below_0_check_uses_the_stored_value_stored_0_stays_0(db, w1, mk_tag):
    """ITG-DEC-14 — the "not below 0" check uses the stored value: stored 0 stays 0.
    Rules: `decrement_usage_count` R6 [BUG-931]"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
    db.execute(text("update item_tags set usage_count = 0 where id = :i"), {"i": t1.id})

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 0
    # Then 3
    assert stored_count(db, t1) == 0


# [claude] ITG-DEC-15
def test_itg_dec_15__the_decrease_is_flushed_but_not_committed_a_rollback_restores_the_old(db, w1, mk_tag):
    """ITG-DEC-15 — the decrease is flushed but not committed: a rollback restores the old value.
    Rules: `decrement_usage_count` R7"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

        # Then 1
        assert result is t1
        # Then 2
        assert stored_count(db, t1) == 2
        sp.rollback()
        # Then 3
        row = reread(db, t1)
        assert row.usage_count == 3
        # Then 4
        assert commit_spy.call_count == 0


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ItemTag
# --------------------------------------------------------------------------- #


# [local-coder] ITG-INH-02
def test_itg_inh_02__create_with_an_itemtagcreate_schema_fails_on_flush_and_saves_nothing(db):
    """ITG-INH-02 — create with an ItemTagCreate schema fails on flush and saves nothing.
    Rules: inherited R2, Errors row 1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ItemTagCreate(name="Spare Part", tag_code="spare_part"))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-03
def test_itg_inh_03__create_with_a_dict_without_tag_code_fails_on_flush_and_saves_nothing(db, w1):
    """ITG-INH-03 — create with a dict without tag_code fails on flush and saves nothing.
    Rules: inherited R2, Errors row 1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "tag_code"' in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-04
def test_itg_inh_04__create_with_a_dict_without_name_fails_on_flush_and_saves_nothing(db, w1):
    """ITG-INH-04 — create with a dict without name fails on flush and saves nothing.
    Rules: inherited Errors row 1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "tag_code": "spare_part"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "name"' in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-06
def test_itg_inh_06__create_with_an_unknown_created_by_fails_on_flush_and_saves_nothing(db, w1):
    """ITG-INH-06 — create with an unknown created_by fails on flush and saves nothing.
    Rules: inherited R2, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part", "created_by": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tags_created_by_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-07
def test_itg_inh_07__a_color_of_8_characters_is_too_long_and_nothing_is_saved(db, w1):
    """ITG-INH-07 — a color of 8 characters is too long and nothing is saved.
    Rules: inherited R2, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#AA33001"})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-08
def test_itg_inh_08__a_color_of_exactly_7_characters_is_saved(db, w1):
    """ITG-INH-08 — a color of exactly 7 characters is saved.
    Rules: inherited R2"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#AA3300"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.color == "#AA3300"


# [local-coder] ITG-INH-09
def test_itg_inh_09__an_icon_of_51_characters_is_too_long_and_nothing_is_saved(db, w1):
    """ITG-INH-09 — an icon of 51 characters is too long and nothing is saved.
    Rules: inherited R2, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part", "icon": "i" * 51})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert count_rows(db, "item_tags") == 0


# [local-coder] ITG-INH-10
def test_itg_inh_10__an_icon_of_exactly_50_characters_is_saved(db, w1):
    """ITG-INH-10 — an icon of exactly 50 characters is saved.
    Rules: inherited R2"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part", "icon": "i" * 50})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.icon == "i" * 50


# [local-coder] ITG-INH-11
def test_itg_inh_11__a_500_character_name_and_a_60_character_code_are_saved_no_database(db, w1):
    """ITG-INH-11 — a 500-character name and a 60-character code are saved (no database length limit).
    Rules: inherited R2"""

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "N" * 500, "tag_code": "c" * 60})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "N" * 500
    # Then 3
    assert row.tag_code == "c" * 60


# [local-coder] ITG-INH-12
def test_itg_inh_12__create_checks_no_uniqueness_a_second_tag_with_the_same_name_and_code(db, w1, mk_tag):
    """ITG-INH-12 — create checks no uniqueness: a second tag with the same name and code is saved.
    Rules: inherited R3"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")
    before_t1 = snap(db, t1)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part"})

    # Then 1
    assert result.id != t1.id
    # Then 2
    assert count_rows(db, "item_tags", tag_code="spare_part") == 2
    # Then 3
    assert snap(db, t1) == before_t1


# [local-coder] ITG-INH-13
def test_itg_inh_13__update_with_an_itemtagupdate_changes_the_name_and_keeps_a_colour_sent(db, mk_tag):
    """ITG-INH-13 — update with an ItemTagUpdate changes the name and keeps a colour sent as None.
    Rules: inherited R4"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part", color="#AA3300")

    result = dao.update(db, db_obj=t1, obj_in=ItemTagUpdate(name="Spare Kit", color=None))

    # Then 1
    assert result.id == t1.id
    # Then 2
    row = reread(db, t1)
    assert row.name == "Spare Kit"
    # Then 3
    assert row.color == "#AA3300"


# [local-coder] ITG-INH-14
def test_itg_inh_14__update_with_the_dict_is_active_false_deletes_the_tag(db, mk_tag):
    """ITG-INH-14 — update with the dict {"is_active": False} deletes the tag.
    Rules: inherited R4"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")

    result = dao.update(db, db_obj=t1, obj_in={"is_active": False})

    # Then 1
    assert result.id == t1.id
    # Then 2
    row = reread(db, t1)
    assert row.is_active is False
    # Then 3
    assert row.name == "Spare Part"
    assert row.tag_code == "spare_part"
    # Then 4
    assert count_rows(db, "item_tags") == 1


# [local-coder] ITG-INH-15
def test_itg_inh_15__update_with_the_dict_is_active_true_brings_a_deleted_tag_back(db, mk_tag):
    """ITG-INH-15 — update with the dict {"is_active": True} brings a deleted tag back.
    Rules: inherited R4"""
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False)

    result = dao.update(db, db_obj=td, obj_in={"is_active": True})

    # Then 1
    assert result.id == td.id
    # Then 2
    row = reread(db, td)
    assert row.is_active is True


# [local-coder] ITG-INH-16
def test_itg_inh_16__update_with_the_dict_color_none_clears_the_colour(db, mk_tag):
    """ITG-INH-16 — update with the dict {"color": None} clears the colour.
    Rules: inherited R4"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part", color="#AA3300")

    result = dao.update(db, db_obj=t1, obj_in={"color": None})

    # Then 1
    assert result.id == t1.id
    # Then 2
    row = reread(db, t1)
    assert row.color is None
    # Then 3
    assert row.name == "Spare Part"


# [local-coder] ITG-INH-17
def test_itg_inh_17__get_by_workspace_returns_the_workspace_s_tags_deleted_ones_included(db, w1, w2, mk_tag):
    """ITG-INH-17 — get_by_workspace returns the workspace's tags, deleted ones included, and no tag of another workspace.
    Rules: inherited R5 (the part that holds today), R6"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False)
    mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, td.id]
    # Then 2
    assert len(result) == 2


# [claude] ITG-INH-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_itg_inh_18__get_by_workspace_returns_the_tags_in_id_order(db, w1, mk_tag):
    """ITG-INH-18 — get_by_workspace returns the tags in id order.
    Rules: inherited R5 [BUG-100]"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")
    t2 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")
    t1.description = "moved"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id]
    # Then 2
    assert ids(result) == [t1.id, t2.id]


# [claude] ITG-INH-19
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_itg_inh_19__the_workspace_list_query_on_tags_asks_the_database_for_id_order(db, w1, mk_tag):
    """ITG-INH-19 — the workspace list query on tags asks the database for id order.
    Rules: inherited R5 [BUG-100]"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "item_tags.id" in order_part


# [local-coder] ITG-INH-20
def test_itg_inh_20__get_returns_a_deleted_tag(db, mk_tag):
    """ITG-INH-20 — get returns a deleted tag.
    Rules: inherited R6"""
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False)

    result = dao.get(db, td.id)

    # Then 1
    assert result.id == td.id
    # Then 2
    assert result.is_active is False


# [local-coder] ITG-INH-21
def test_itg_inh_21__get_returns_a_tag_of_any_workspace(db, w2, mk_tag):
    """ITG-INH-21 — get returns a tag of any workspace.
    Rules: inherited R6"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get(db, t9.id)

    # Then 1
    assert result.id == t9.id
    # Then 2
    assert result.workspace_id == w2.id


# [local-coder] ITG-INH-22
def test_itg_inh_22__get_by_id_and_workspace_returns_a_deleted_tag(db, w1, mk_tag):
    """ITG-INH-22 — get_by_id_and_workspace returns a deleted tag.
    Rules: inherited R6"""
    td = mk_tag(name="Obsolete", tag_code="obsolete", is_active=False)

    result = dao.get_by_id_and_workspace(db, id=td.id, workspace_id=w1.id)

    # Then 1
    assert result.id == td.id
    # Then 2
    assert result.is_active is False


# [local-coder] ITG-INH-23
def test_itg_inh_23__get_by_id_and_workspace_returns_none_for_a_tag_of_another_workspace(db, w1, w2, mk_tag):
    """ITG-INH-23 — get_by_id_and_workspace returns None for a tag of another workspace.
    Rules: inherited R6"""
    t9 = mk_tag(name="Far Crate", tag_code="far_crate", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=t9.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] ITG-INH-24
def test_itg_inh_24__remove_deletes_the_tag_row_for_good(db, mk_tag):
    """ITG-INH-24 — remove deletes the tag row for good.
    Rules: inherited R7 (the tag row; the cascade is Spec gap 4)"""
    t1 = mk_tag(name="Spare Part", tag_code="spare_part")
    t2 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")
    t1_id = t1.id
    before_t2 = snap(db, t2)

    result = dao.remove(db, id=t1_id)

    # Then 1
    assert result.id == t1_id
    # Then 2
    assert count_rows(db, "item_tags", id=t1_id) == 0
    # Then 3
    assert snap(db, t2) == before_t2
