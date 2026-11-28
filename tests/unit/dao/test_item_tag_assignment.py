"""Unit tests for app/dao/item_tag_assignment.py.

Implements tests/unit/dao/item_tag_assignment.cases.md, one test per case. Real
Postgres session (`db` fixture). Nothing is patched (Conventions, Externals:
None).

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/dao/item_tag_assignment.helpers.md as its only view of this file;
tests below a `# [claude] <ID>` comment are the `Author: claude` cards,
written by hand at finishing.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.item_tag_assignment import item_tag_assignment_dao
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.schemas.item_tag_assignment import (
    ItemTagAssignmentCreate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton item_tag_assignment_dao" (a module-level name, not a fixture)
dao = item_tag_assignment_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> fixtures (W1, W2, U1, U2 and the nine standing rows)
# Each fixture depends on the one before it, so the ids rise in the order the
# Conventions list them: I1, I2, IX, I9, then T1, T2, TS, TD, T9.
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows" (U1 = assigned_by of every Given link)
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "item" = items row: workspace W1, unit "pcs", is_active True; name and name_normalized from the card
def _item_fields(default_workspace_id, name, name_normalized, **columns):
    fields = {"workspace_id": default_workspace_id, "name": name, "name_normalized": name_normalized,
              "unit": "pcs", "is_active": True}
    fields.update(columns)
    return fields


# Convention "tag" = item_tags row: workspace W1, not a system tag, active, usage_count 0,
# color / icon / description / created_by None; name and tag_code from the card
def _tag_fields(default_workspace_id, name, tag_code, **columns):
    fields = {
        "workspace_id": default_workspace_id, "name": name, "tag_code": tag_code,
        "is_system_tag": False, "is_active": True, "usage_count": 0,
        "color": None, "icon": None, "description": None, "created_by": None,
    }
    fields.update(columns)
    return fields


# Standing items I1, I2, IX (deleted), I9 (W2)
@pytest.fixture
def i1(db, w1, u2):
    return _add(db, Item(**_item_fields(w1.id, "Bolt M8", "bolt m8")))


@pytest.fixture
def i2(db, w1, i1):
    return _add(db, Item(**_item_fields(w1.id, "Washer 10", "washer 10")))


@pytest.fixture
def ix(db, w1, i2):
    return _add(db, Item(**_item_fields(w1.id, "Old Rivet", "old rivet", is_active=False)))


@pytest.fixture
def i9(db, w2, ix):
    return _add(db, Item(**_item_fields(w2.id, "Far Spring", "far spring")))


# Standing tags T1, T2, TS (system), TD (deleted), T9 (W2)
@pytest.fixture
def t1(db, w1, i9):
    return _add(db, ItemTag(**_tag_fields(w1.id, "Spare Part", "spare_part")))


@pytest.fixture
def t2(db, w1, t1):
    return _add(db, ItemTag(**_tag_fields(w1.id, "Hex Bolt", "hex_bolt")))


@pytest.fixture
def ts(db, w1, t2):
    return _add(db, ItemTag(**_tag_fields(w1.id, "Raw Material", "raw_material", is_system_tag=True)))


@pytest.fixture
def td(db, w1, ts):
    return _add(db, ItemTag(**_tag_fields(w1.id, "Obsolete", "obsolete", is_active=False)))


@pytest.fixture
def t9(db, w2, td):
    return _add(db, ItemTag(**_tag_fields(w2.id, "Far Crate", "far_crate")))


# Convention "These rows exist in every test, inserted in this order, and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, i1, i2, ix, i9, t1, t2, ts, td, t9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each inserts one row and flushes)
# --------------------------------------------------------------------------- #

# Convention "item" (a further item I3 a card builds)
@pytest.fixture
def mk_item(db, w1):
    """mk_item(name=..., name_normalized=..., **columns) -> Item. Keywords only."""
    def _mk(*, name, name_normalized, **columns):
        return _add(db, Item(**_item_fields(w1.id, name, name_normalized, **columns)))
    return _mk


# Convention "tag" (further tags K1, K2, ... a card builds)
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name=..., tag_code=..., **columns) -> ItemTag. Keywords only."""
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


# Convention "link of I to T": workspace_id = I's, assigned_by U1.id, assigned_at left to the model default
@pytest.fixture
def mk_link(db, u1):
    """mk_link(of=<item>, to=<tag>, **columns) -> ItemTagAssignment. Keywords only.

    Each column the card lists after "but" is one more keyword (`workspace_id=w2.id`).
    """
    def _mk(*, of, to, **columns):
        fields = {"workspace_id": of.workspace_id, "item_id": of.id, "tag_id": to.id, "assigned_by": u1.id}
        fields.update(columns)
        return _add(db, ItemTagAssignment(**fields))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

_TABLES = {model.__tablename__: model.__table__ for model in (ItemTagAssignment, Item, ItemTag)}


def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id from its own table
def reread(db, row):
    """Fresh copy of `row` (link, item or tag) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "links_of(I)": expire_all, then every link row of item I (any workspace), by id
def links_of(db, item):
    item_id = _id_of(item)
    db.expire_all()
    stmt = (select(ItemTagAssignment).where(ItemTagAssignment.item_id == item_id)
            .order_by(ItemTagAssignment.id))
    return list(db.execute(stmt).scalars().all())


# Convention "count:" lines: rows of the named table in all workspaces, with the
# filter stated as keywords (`count_rows(db, "item_tag_assignments", tag_id=k1.id)`)
def count_rows(db, table_name, **where):
    table = _TABLES[table_name]
    stmt = select(func.count()).select_from(table)
    for column, value in where.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": row counts of item_tag_assignments, items and item_tags, all workspaces
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "ids(x)" / "names(x)": in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


def names(result):
    return [row.name for row in result]


# Convention "close to now"
def close_to_now(value):
    return abs(datetime.now(timezone.utc).replace(tzinfo=None) - value) < timedelta(minutes=5)


# --------------------------------------------------------------------------- #
# Reading helpers of the `Author: claude` cards (not in the helper sheet)
# --------------------------------------------------------------------------- #

# Convention "Statement recorder" (`Author: claude` cards TFS-04, TFS-19, TFI-14, INH-15):
# the SQL text of every statement the session's connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.connection()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def sql(self):
        """Text of the one SELECT sent (fails loudly if there is not exactly one)."""
        (one,) = [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]
        return one


# Convention "order_part": the text of `sql` after `ORDER BY` ("" when there is none)
def order_part_of(sql):
    """Text of `sql` after ORDER BY ("" when there is none)."""
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# Exemplar tests (hand-written; shown verbatim in item_tag_assignment.helpers.md)
# --------------------------------------------------------------------------- #

def test_ita_tfs_16__lower_case_names_come_back_alphabetically_within_each_item_the_system(db, w1, i1, i2, mk_tag, mk_system_tag, mk_link):
    """ITA-TFS-16 — lower-case names come back alphabetically within each item, the system tag not first.
    Rules: `get_tags_for_items` R6 (the part that holds today: names with one case only; system tags not grouped first), R2"""
    k1 = mk_tag(name="delta", tag_code="delta")
    k2 = mk_tag(name="alpha", tag_code="alpha")
    k3 = mk_tag(name="charlie", tag_code="charlie")
    k4 = mk_system_tag(name="zulu", tag_code="zulu")
    mk_link(of=i1, to=k1)
    mk_link(of=i1, to=k4)
    mk_link(of=i1, to=k2)
    mk_link(of=i2, to=k3)
    mk_link(of=i2, to=k2)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id], workspace_id=w1.id)

    # Then 1
    assert names(result[i1.id]) == ["alpha", "delta", "zulu"]
    # Then 2
    assert names(result[i2.id]) == ["alpha", "charlie"]


def test_ita_tfi_15__a_link_added_but_not_flushed_is_not_seen(db, w1, u1, i1, t1, t2, mk_link):
    """ITA-TFI-15 — a link added but not flushed is not seen.
    Rules: `get_tags_for_item` R5"""
    mk_link(of=i1, to=t1)
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i1.id, tag_id=t2.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


def test_ita_ex_01__an_existing_link_gives_true_and_nothing_is_written(db, w1, i1, t1, mk_link):
    """ITA-EX-01 — an existing link gives True and nothing is written.
    Rules: `assignment_exists` R1, R5"""
    l1 = mk_link(of=i1, to=t1)
    before = written(db)
    before_l1 = snap(db, l1)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is True
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, l1) == before_l1


def test_ita_cnt_01__counts_the_live_items_of_each_tag_system_and_user_tags_alike_and(db, w1, i1, i2, t1, t2, ts, mk_item, mk_link):
    """ITA-CNT-01 — counts the live items of each tag, system and user tags alike, and writes nothing.
    Rules: `count_active_items_per_tag` R1, R5 (system tags), R6, Returns"""
    i3 = mk_item(name="Spring Pin", name_normalized="spring pin")
    mk_link(of=i1, to=t1)
    mk_link(of=i2, to=t1)
    mk_link(of=i3, to=t1)
    mk_link(of=i1, to=t2)
    mk_link(of=i2, to=ts)
    before = written(db)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert result == {t1.id: 3, t2.id: 1, ts.id: 1}
    # Then 3
    assert written(db) == before


def test_ita_rm_05__a_link_of_the_same_item_recorded_under_another_workspace_stays(db, w1, w2, i1, t1, t2, mk_link):
    """ITA-RM-05 — a link of the same item recorded under another workspace stays.
    Rules: `remove_all_tags_from_item` R3"""
    mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=t2, workspace_id=w2.id)
    before_l2 = snap(db, l2)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert len(links_of(db, i1)) == 1
    # Then 3
    assert snap(db, l2) == before_l2
    # Then 4
    row = reread(db, l2)
    assert row.workspace_id == w2.id
    assert row.tag_id == t2.id


def test_ita_inh_04__a_second_link_for_the_same_item_and_tag_fails_on_flush_and_the_first(db, w1, i1, t1, mk_link):
    """ITA-INH-04 — a second link for the same item and tag fails on flush and the first stays.
    Rules: inherited R2, Errors row 2"""
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id})

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_item_tag" in str(exc.value.orig)
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert len(links_of(db, i1)) == 1


def test_ita_inh_17__update_with_a_dict_sets_the_given_column_and_nothing_else(db, w1, u2, i1, t1, mk_link):
    """ITA-INH-17 — update with a dict sets the given column and nothing else.
    Rules: inherited R5"""
    l1 = mk_link(of=i1, to=t1)
    at_before = l1.assigned_at

    result = dao.update(db, db_obj=l1, obj_in={"assigned_by": u2.id})

    # Then 1
    assert result.id == l1.id
    # Then 2
    row = reread(db, l1)
    assert row.assigned_by == u2.id
    # Then 3
    assert row.assigned_at == at_before
    # Then 4
    assert row.item_id == i1.id
    assert row.tag_id == t1.id
    assert row.workspace_id == w1.id


# --------------------------------------------------------------------------- #
# ItemTagAssignmentDAO.get_tags_for_items
# --------------------------------------------------------------------------- #


# [local-coder] ITA-TFS-01
def test_ita_tfs_01__returns_a_dict_of_the_active_tags_per_requested_item_and_writes(db, w1, i1, i2, t1, t2, ts, mk_link):
    """ITA-TFS-01 — returns a dict of the active tags per requested item and writes nothing.
    Rules: `get_tags_for_items` R2, R3, R7, Returns"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=ts)
    mk_link(of=i2, to=t2)
    before = written(db)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id], workspace_id=w1.id)

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert list(result.keys()) == [i1.id, i2.id]
    # Then 3
    assert sorted(ids(result[i1.id])) == [t1.id, ts.id]
    # Then 4
    assert ids(result[i2.id]) == [t2.id]
    # Then 5
    assert isinstance(result[i1.id][0], ItemTag)
    # Then 6
    assert written(db) == before


# [local-coder] ITA-TFS-02
def test_ita_tfs_02__an_empty_list_of_item_ids_returns_an_empty_dict(db, w1, i1, t1, mk_link):
    """ITA-TFS-02 — an empty list of item ids returns an empty dict.
    Rules: `get_tags_for_items` R1"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_items(db, item_ids=[], workspace_id=w1.id)

    # Then 1
    assert result == {}


# [local-coder] ITA-TFS-03
def test_ita_tfs_03__item_ids_none_returns_an_empty_dict(db, w1, i1, t1, mk_link):
    """ITA-TFS-03 — item ids None returns an empty dict.
    Rules: `get_tags_for_items` R1"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_items(db, item_ids=None, workspace_id=w1.id)

    # Then 1
    assert result == {}


# [claude] ITA-TFS-04
def test_ita_tfs_04__an_empty_list_of_item_ids_sends_no_query(db, w1, i1, t1, mk_link):
    """ITA-TFS-04 — an empty list of item ids sends no query.
    Rules: `get_tags_for_items` R1 ("nothing is queried")"""
    mk_link(of=i1, to=t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_tags_for_items(db, item_ids=[], workspace_id=w1.id)
    statements = recorder.statements

    # Then 1
    assert result == {}
    # Then 2
    assert statements == []


# [local-coder] ITA-TFS-05
def test_ita_tfs_05__the_keys_follow_the_order_of_the_request_not_the_order_of_the_ids(db, w1, i1, i2, t1, t2, mk_link):
    """ITA-TFS-05 — the keys follow the order of the request, not the order of the ids.
    Rules: `get_tags_for_items` R2"""
    mk_link(of=i1, to=t1)
    mk_link(of=i2, to=t2)

    result = dao.get_tags_for_items(db, item_ids=[i2.id, i1.id], workspace_id=w1.id)

    # Then 1
    assert list(result.keys()) == [i2.id, i1.id]
    # Then 2
    assert ids(result[i2.id]) == [t2.id]
    # Then 3
    assert ids(result[i1.id]) == [t1.id]


# [local-coder] ITA-TFS-06
def test_ita_tfs_06__an_id_given_twice_is_one_key_and_its_tag_is_listed_once(db, w1, i1, i2, t1, mk_link):
    """ITA-TFS-06 — an id given twice is one key and its tag is listed once.
    Rules: `get_tags_for_items` R2"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id, i1.id], workspace_id=w1.id)

    # Then 1
    assert list(result.keys()) == [i1.id, i2.id]
    # Then 2
    assert ids(result[i1.id]) == [t1.id]
    # Then 3
    assert result[i2.id] == []


# [local-coder] ITA-TFS-07
def test_ita_tfs_07__an_unknown_item_id_maps_to_an_empty_list(db, w1, i1, t1, mk_link):
    """ITA-TFS-07 — an unknown item id maps to an empty list.
    Rules: `get_tags_for_items` R2"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, MISSING], workspace_id=w1.id)

    # Then 1
    assert list(result.keys()) == [i1.id, MISSING]
    # Then 2
    assert result[MISSING] == []
    # Then 3
    assert ids(result[i1.id]) == [t1.id]


# [local-coder] ITA-TFS-08
def test_ita_tfs_08__an_item_without_tags_maps_to_an_empty_list(db, w1, i1, i2, t1, mk_link):
    """ITA-TFS-08 — an item without tags maps to an empty list.
    Rules: `get_tags_for_items` R2"""
    mk_link(of=i2, to=t1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert result == {i1.id: []}


# [local-coder] ITA-TFS-09
def test_ita_tfs_09__a_deleted_tag_is_never_listed_an_item_with_only_a_deleted_tag_maps_to(db, w1, i1, i2, t1, td, mk_link):
    """ITA-TFS-09 — a deleted tag is never listed; an item with only a deleted tag maps to an empty list.
    Rules: `get_tags_for_items` R2, R3"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)
    mk_link(of=i2, to=td)
    before_td = snap(db, td)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id], workspace_id=w1.id)

    # Then 1
    assert ids(result[i1.id]) == [t1.id]
    # Then 2
    assert result[i2.id] == []
    # Then 3
    assert snap(db, td) == before_td


# [local-coder] ITA-TFS-10
def test_ita_tfs_10__a_link_recorded_under_another_workspace_is_ignored(db, w1, w2, i1, t1, mk_link):
    """ITA-TFS-10 — a link recorded under another workspace is ignored.
    Rules: `get_tags_for_items` R3, R2"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert result == {i1.id: []}


# [local-coder] ITA-TFS-11
def test_ita_tfs_11__the_link_s_own_workspace_decides_asked_under_the_link_s_workspace_the(db, w2, i1, t1, mk_link):
    """ITA-TFS-11 — the link's own workspace decides: asked under the link's workspace, the tag is listed.
    Rules: `get_tags_for_items` R3, R4"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w2.id)

    # Then 1
    assert ids(result[i1.id]) == [t1.id]


# [local-coder] ITA-TFS-12
def test_ita_tfs_12__the_tags_of_a_deleted_item_are_listed_like_those_of_a_live_one(db, w1, ix, t1, mk_link):
    """ITA-TFS-12 — the tags of a deleted item are listed like those of a live one.
    Rules: `get_tags_for_items` R4 (P1)"""
    mk_link(of=ix, to=t1)
    before_ix = snap(db, ix)

    result = dao.get_tags_for_items(db, item_ids=[ix.id], workspace_id=w1.id)

    # Then 1
    assert ids(result[ix.id]) == [t1.id]
    # Then 2
    assert snap(db, ix) == before_ix


# [local-coder] ITA-TFS-13
def test_ita_tfs_13__a_tag_of_another_workspace_reached_through_a_link_of_this_workspace(db, w1, i1, t9, mk_link):
    """ITA-TFS-13 — a tag of another workspace reached through a link of this workspace is listed.
    Rules: `get_tags_for_items` R4 (P1)"""
    mk_link(of=i1, to=t9)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert ids(result[i1.id]) == [t9.id]


# [local-coder] ITA-TFS-14
def test_ita_tfs_14__an_item_of_another_workspace_reached_through_a_link_of_this_workspace(db, w1, i9, t1, mk_link):
    """ITA-TFS-14 — an item of another workspace reached through a link of this workspace gets its tag.
    Rules: `get_tags_for_items` R4 (P1)"""
    mk_link(of=i9, to=t1, workspace_id=w1.id)

    result = dao.get_tags_for_items(db, item_ids=[i9.id], workspace_id=w1.id)

    # Then 1
    assert ids(result[i9.id]) == [t1.id]


# [local-coder] ITA-TFS-15
def test_ita_tfs_15__a_tag_on_two_items_is_the_same_object_in_both_lists(db, w1, i1, i2, t1, mk_link):
    """ITA-TFS-15 — a tag on two items is the same object in both lists.
    Rules: `get_tags_for_items` R5"""
    mk_link(of=i1, to=t1)
    mk_link(of=i2, to=t1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id], workspace_id=w1.id)

    # Then 1
    assert len(result[i1.id]) == 1
    # Then 2
    assert result[i1.id][0].id == t1.id
    # Then 3
    assert result[i1.id][0] is result[i2.id][0]


# [claude] ITA-TFS-17
def test_ita_tfs_17__names_that_differ_only_in_case_come_back_in_id_order_then_the_other(db, w1, i1, mk_tag, mk_system_tag, mk_link):
    """ITA-TFS-17 — names that differ only in case come back in id order, then the other names case-insensitively.
    Rules: `get_tags_for_items` R6 [BUG-933]"""
    k1 = mk_tag(name="bravo", tag_code="bravo")
    k2 = mk_tag(name="Alpha", tag_code="alpha_upper")
    k3 = mk_tag(name="alpha", tag_code="alpha_lower")
    k4 = mk_system_tag(name="Charlie", tag_code="charlie")
    mk_link(of=i1, to=k1)
    mk_link(of=i1, to=k2)
    mk_link(of=i1, to=k3)
    mk_link(of=i1, to=k4)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result[i1.id])) == [k1.id, k2.id, k3.id, k4.id]
    # Then 2
    assert ids(result[i1.id]) == [k2.id, k3.id, k1.id, k4.id]


# [claude] ITA-TFS-18
def test_ita_tfs_18__two_tags_with_the_same_name_come_back_lower_id_first(db, w1, i1, mk_tag, mk_link):
    """ITA-TFS-18 — two tags with the same name come back lower id first.
    Rules: `get_tags_for_items` R6 [BUG-933]"""
    k1 = mk_tag(name="Bolt", tag_code="bolt_a")
    k2 = mk_tag(name="Bolt", tag_code="bolt_b")
    mk_link(of=i1, to=k2)
    mk_link(of=i1, to=k1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result[i1.id])) == [k1.id, k2.id]
    # Then 2
    assert ids(result[i1.id]) == [k1.id, k2.id]


# [claude] ITA-TFS-19
def test_ita_tfs_19__the_tags_of_items_query_asks_for_name_case_insensitive_then_id(db, w1, i1, t1, mk_link):
    """ITA-TFS-19 — the tags-of-items query asks for name case-insensitive, then id.
    Rules: `get_tags_for_items` R6 [BUG-933]"""
    mk_link(of=i1, to=t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert list(result.keys()) == [i1.id]
    # Then 2
    assert ids(result[i1.id]) == [t1.id]
    # Then 3
    assert "ORDER BY" in sql
    # Then 4
    assert "lower(item_tags.name)" in order_part
    # Then 5
    assert "item_tags.id" in order_part


# [local-coder] ITA-TFS-20
def test_ita_tfs_20__a_link_added_but_not_flushed_is_not_seen(db, w1, i1, t1, t2, u1, mk_link):
    """ITA-TFS-20 — a link added but not flushed is not seen.
    Rules: `get_tags_for_items` R7"""
    mk_link(of=i1, to=t1)
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i1.id, tag_id=t2.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.get_tags_for_items(db, item_ids=[i1.id], workspace_id=w1.id)

    # Then 1
    assert ids(result[i1.id]) == [t1.id]


# --------------------------------------------------------------------------- #
# ItemTagAssignmentDAO.get_tags_for_item
# --------------------------------------------------------------------------- #


# [local-coder] ITA-TFI-01
def test_ita_tfi_01__returns_a_list_of_the_item_s_active_tags_system_and_user_alike_and(db, w1, i1, i2, t1, t2, ts, mk_link):
    """ITA-TFI-01 — returns a list of the item's active tags, system and user alike, and writes nothing.
    Rules: `get_tags_for_item` R1, R2, R5, Returns"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    mk_link(of=i1, to=ts)
    mk_link(of=i2, to=t1)
    before = written(db)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [t1.id, t2.id, ts.id]
    # Then 3
    assert isinstance(result[0], ItemTag)
    # Then 4
    assert written(db) == before


# [local-coder] ITA-TFI-02
def test_ita_tfi_02__an_item_without_links_returns_an_empty_list(db, w1, i1, i2, t1, mk_link):
    """ITA-TFI-02 — an item without links returns an empty list.
    Rules: `get_tags_for_item` R1"""
    mk_link(of=i2, to=t1)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ITA-TFI-03
def test_ita_tfi_03__an_unknown_item_id_returns_an_empty_list(db, w1, i1, t1, mk_link):
    """ITA-TFI-03 — an unknown item id returns an empty list.
    Rules: `get_tags_for_item` R1"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ITA-TFI-04
def test_ita_tfi_04__asked_under_another_workspace_the_item_s_links_are_not_used(db, w2, i1, t1, mk_link):
    """ITA-TFI-04 — asked under another workspace, the item's links are not used.
    Rules: `get_tags_for_item` R1"""
    mk_link(of=i1, to=t1)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] ITA-TFI-05
def test_ita_tfi_05__a_link_recorded_under_another_workspace_is_not_used(db, w1, w2, i1, t1, mk_link):
    """ITA-TFI-05 — a link recorded under another workspace is not used.
    Rules: `get_tags_for_item` R1"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ITA-TFI-06
def test_ita_tfi_06__the_link_s_own_workspace_decides_asked_under_the_link_s_workspace_the(db, w2, i1, t1, mk_link):
    """ITA-TFI-06 — the link's own workspace decides: asked under the link's workspace, the tag is returned.
    Rules: `get_tags_for_item` R1, R3"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [t1.id]


# [local-coder] ITA-TFI-07
def test_ita_tfi_07__a_deleted_tag_is_not_returned_and_left_as_it_was(db, w1, i1, t1, td, mk_link):
    """ITA-TFI-07 — a deleted tag is not returned and left as it was.
    Rules: `get_tags_for_item` R2"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)
    before_td = snap(db, td)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert snap(db, td) == before_td


# [local-coder] ITA-TFI-08
def test_ita_tfi_08__an_item_whose_only_tag_is_deleted_returns_an_empty_list(db, w1, i1, td, mk_link):
    """ITA-TFI-08 — an item whose only tag is deleted returns an empty list.
    Rules: `get_tags_for_item` R2"""
    mk_link(of=i1, to=td)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ITA-TFI-09
def test_ita_tfi_09__the_tags_of_a_deleted_item_are_returned(db, w1, ix, t1, t2, mk_link):
    """ITA-TFI-09 — the tags of a deleted item are returned.
    Rules: `get_tags_for_item` R3 (P1)"""
    mk_link(of=ix, to=t1)
    mk_link(of=ix, to=t2)
    before_ix = snap(db, ix)

    result = dao.get_tags_for_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id]
    # Then 2
    assert snap(db, ix) == before_ix


# [local-coder] ITA-TFI-10
def test_ita_tfi_10__a_tag_of_another_workspace_reached_through_a_link_of_this_workspace(db, w1, i1, t9, mk_link):
    """ITA-TFI-10 — a tag of another workspace reached through a link of this workspace is returned.
    Rules: `get_tags_for_item` R3 (P1)"""
    mk_link(of=i1, to=t9)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t9.id]


# [local-coder] ITA-TFI-11
def test_ita_tfi_11__an_item_of_another_workspace_reached_through_a_link_of_this_workspace(db, w1, i9, t1, mk_link):
    """ITA-TFI-11 — an item of another workspace reached through a link of this workspace gets its tag.
    Rules: `get_tags_for_item` R3 (P1)"""
    mk_link(of=i9, to=t1, workspace_id=w1.id)

    result = dao.get_tags_for_item(db, item_id=i9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [claude] ITA-TFI-12
def test_ita_tfi_12__names_that_differ_only_in_case_come_back_in_id_order_then_the_other(db, w1, i1, mk_tag, mk_system_tag, mk_link):
    """ITA-TFI-12 — names that differ only in case come back in id order, then the other names case-insensitively.
    Rules: `get_tags_for_item` R4 [BUG-932]"""
    k1 = mk_tag(name="bravo", tag_code="bravo")
    k2 = mk_tag(name="Alpha", tag_code="alpha_upper")
    k3 = mk_tag(name="alpha", tag_code="alpha_lower")
    k4 = mk_system_tag(name="Charlie", tag_code="charlie")
    mk_link(of=i1, to=k1)
    mk_link(of=i1, to=k2)
    mk_link(of=i1, to=k3)
    mk_link(of=i1, to=k4)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [k1.id, k2.id, k3.id, k4.id]
    # Then 2
    assert ids(result) == [k2.id, k3.id, k1.id, k4.id]


# [claude] ITA-TFI-13
def test_ita_tfi_13__two_tags_with_the_same_name_come_back_lower_id_first(db, w1, i1, mk_tag, mk_link):
    """ITA-TFI-13 — two tags with the same name come back lower id first.
    Rules: `get_tags_for_item` R4 [BUG-932]"""
    k1 = mk_tag(name="Bolt", tag_code="bolt_a")
    k2 = mk_tag(name="Bolt", tag_code="bolt_b")
    mk_link(of=i1, to=k2)
    mk_link(of=i1, to=k1)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [k1.id, k2.id]
    # Then 2
    assert ids(result) == [k1.id, k2.id]


# [claude] ITA-TFI-14
def test_ita_tfi_14__the_tags_of_one_item_query_asks_for_name_case_insensitive_then_id(db, w1, i1, t1, mk_link):
    """ITA-TFI-14 — the tags-of-one-item query asks for name case-insensitive, then id.
    Rules: `get_tags_for_item` R4 [BUG-932]"""
    mk_link(of=i1, to=t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(item_tags.name)" in order_part
    # Then 4
    assert "item_tags.id" in order_part


# --------------------------------------------------------------------------- #
# ItemTagAssignmentDAO.assignment_exists
# --------------------------------------------------------------------------- #


# [local-coder] ITA-EX-02
def test_ita_ex_02__another_tag_of_the_same_item_gives_false(db, w1, i1, t1, t2, mk_link):
    """ITA-EX-02 — another tag of the same item gives False.
    Rules: `assignment_exists` R1"""
    mk_link(of=i1, to=t1)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t2.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [local-coder] ITA-EX-03
def test_ita_ex_03__the_same_tag_on_another_item_gives_false(db, w1, i1, i2, t1, mk_link):
    """ITA-EX-03 — the same tag on another item gives False.
    Rules: `assignment_exists` R1"""
    mk_link(of=i2, to=t1)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [local-coder] ITA-EX-04
def test_ita_ex_04__unknown_ids_give_false(db, w1, i1, t1, mk_link):
    """ITA-EX-04 — unknown ids give False.
    Rules: `assignment_exists` R1"""
    mk_link(of=i1, to=t1)

    result = dao.assignment_exists(db, item_id=MISSING, tag_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is False


# [local-coder] ITA-EX-05
def test_ita_ex_05__a_link_recorded_only_under_another_workspace_gives_false(db, w1, w2, i1, t1, mk_link):
    """ITA-EX-05 — a link recorded only under another workspace gives False.
    Rules: `assignment_exists` R2"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [local-coder] ITA-EX-06
def test_ita_ex_06__the_link_s_own_workspace_decides_asked_under_the_link_s_workspace(db, w2, i1, t1, mk_link):
    """ITA-EX-06 — the link's own workspace decides: asked under the link's workspace gives True.
    Rules: `assignment_exists` R2"""
    mk_link(of=i1, to=t1, workspace_id=w2.id)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w2.id)

    # Then 1
    assert result is True


# [local-coder] ITA-EX-07
def test_ita_ex_07__a_link_to_a_deleted_tag_gives_true(db, w1, i1, td, mk_link):
    """ITA-EX-07 — a link to a deleted tag gives True.
    Rules: `assignment_exists` R3 (P1)"""
    mk_link(of=i1, to=td)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# [local-coder] ITA-EX-08
def test_ita_ex_08__a_link_of_a_deleted_item_gives_true(db, w1, ix, t1, mk_link):
    """ITA-EX-08 — a link of a deleted item gives True.
    Rules: `assignment_exists` R3 (P1)"""
    mk_link(of=ix, to=t1)

    result = dao.assignment_exists(db, item_id=ix.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# [local-coder] ITA-EX-09
def test_ita_ex_09__a_link_of_this_workspace_to_a_tag_of_another_workspace_gives_true(db, w1, i1, t9, mk_link):
    """ITA-EX-09 — a link of this workspace to a tag of another workspace gives True.
    Rules: `assignment_exists` R3 (P1)"""
    mk_link(of=i1, to=t9)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t9.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# [local-coder] ITA-EX-10
def test_ita_ex_10__a_link_added_but_not_flushed_gives_false(db, w1, u1, i1, t1):
    """ITA-EX-10 — a link added but not flushed gives False.
    Rules: `assignment_exists` R4"""
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i1.id, tag_id=t1.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# --------------------------------------------------------------------------- #
# ItemTagAssignmentDAO.count_active_items_per_tag
# --------------------------------------------------------------------------- #


# [local-coder] ITA-CNT-02
def test_ita_cnt_02__links_to_a_deleted_item_are_not_counted_a_tag_only_on_deleted_items(db, w1, i1, ix, t1, t2, mk_link):
    """ITA-CNT-02 — links to a deleted item are not counted; a tag only on deleted items has no entry.
    Rules: `count_active_items_per_tag` R2"""
    mk_link(of=i1, to=t1)
    mk_link(of=ix, to=t1)
    mk_link(of=ix, to=t2)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t1.id: 1}
    # Then 2
    assert t2.id not in result


# [local-coder] ITA-CNT-03
def test_ita_cnt_03__a_tag_without_links_has_no_entry(db, w1, i1, t1, t2, mk_link):
    """ITA-CNT-03 — a tag without links has no entry.
    Rules: `count_active_items_per_tag` R2"""
    mk_link(of=i1, to=t1)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t1.id: 1}
    # Then 2
    assert t2.id not in result


# [local-coder] ITA-CNT-04
def test_ita_cnt_04__links_of_another_workspace_are_not_counted(db, w1, i1, i9, t1, t9, mk_link):
    """ITA-CNT-04 — links of another workspace are not counted.
    Rules: `count_active_items_per_tag` R3"""
    mk_link(of=i1, to=t1)
    mk_link(of=i9, to=t9)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t1.id: 1}


# [local-coder] ITA-CNT-05
def test_ita_cnt_05__the_other_workspace_gets_only_its_own_count(db, w2, i1, i9, t1, t9, mk_link):
    """ITA-CNT-05 — the other workspace gets only its own count.
    Rules: `count_active_items_per_tag` R3"""
    mk_link(of=i1, to=t1)
    mk_link(of=i9, to=t9)

    result = dao.count_active_items_per_tag(db, workspace_id=w2.id)

    # Then 1
    assert result == {t9.id: 1}


# [local-coder] ITA-CNT-06
def test_ita_cnt_06__an_unknown_workspace_returns_an_empty_dict(db, i1, t1, mk_link):
    """ITA-CNT-06 — an unknown workspace returns an empty dict.
    Rules: `count_active_items_per_tag` R3"""
    mk_link(of=i1, to=t1)

    result = dao.count_active_items_per_tag(db, workspace_id=MISSING)

    # Then 1
    assert result == {}


# [local-coder] ITA-CNT-07
def test_ita_cnt_07__a_workspace_without_links_returns_an_empty_dict(db, w2, i1, t1, mk_link):
    """ITA-CNT-07 — a workspace without links returns an empty dict.
    Rules: `count_active_items_per_tag` R3"""
    mk_link(of=i1, to=t1)

    result = dao.count_active_items_per_tag(db, workspace_id=w2.id)

    # Then 1
    assert result == {}


# [local-coder] ITA-CNT-08
def test_ita_cnt_08__an_item_of_another_workspace_linked_under_this_workspace_is_counted(db, w1, i9, t1, mk_link):
    """ITA-CNT-08 — an item of another workspace linked under this workspace is counted.
    Rules: `count_active_items_per_tag` R4"""
    mk_link(of=i9, to=t1, workspace_id=w1.id)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t1.id: 1}


# [local-coder] ITA-CNT-09
def test_ita_cnt_09__a_deleted_tag_with_links_to_live_items_has_an_entry(db, w1, i1, i2, td, mk_link):
    """ITA-CNT-09 — a deleted tag with links to live items has an entry.
    Rules: `count_active_items_per_tag` R5 (P1)"""
    mk_link(of=i1, to=td)
    mk_link(of=i2, to=td)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {td.id: 2}


# [local-coder] ITA-CNT-10
def test_ita_cnt_10__a_tag_of_another_workspace_linked_under_this_workspace_has_an_entry(db, w1, i1, t9, mk_link):
    """ITA-CNT-10 — a tag of another workspace linked under this workspace has an entry.
    Rules: `count_active_items_per_tag` R5 (P1)"""
    mk_link(of=i1, to=t9)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t9.id: 1}


# [local-coder] ITA-CNT-11
def test_ita_cnt_11__a_link_added_but_not_flushed_is_not_counted(db, w1, i1, i2, t1, u1, mk_link):
    """ITA-CNT-11 — a link added but not flushed is not counted.
    Rules: `count_active_items_per_tag` R6"""
    mk_link(of=i1, to=t1)
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i2.id, tag_id=t1.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert result == {t1.id: 1}


# --------------------------------------------------------------------------- #
# ItemTagAssignmentDAO.remove_all_tags_from_item
# --------------------------------------------------------------------------- #


# [local-coder] ITA-RM-01
def test_ita_rm_01__every_link_of_the_item_is_deleted_and_their_number_returned(db, w1, i1, t1, t2, ts, mk_link):
    """ITA-RM-01 — every link of the item is deleted and their number returned.
    Rules: `remove_all_tags_from_item` R1, Returns, Side effects"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    mk_link(of=i1, to=ts)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 3
    # Then 2
    assert len(links_of(db, i1)) == 0
    # Then 3
    assert count_rows(db, "item_tag_assignments") == 0


# [local-coder] ITA-RM-02
def test_ita_rm_02__a_link_to_a_deleted_tag_is_deleted_and_counted_too_the_tag_stays(db, w1, i1, t1, td, mk_link):
    """ITA-RM-02 — a link to a deleted tag is deleted and counted too; the tag stays deleted.
    Rules: `remove_all_tags_from_item` R2"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=td)
    before_td = snap(db, td)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 2
    # Then 2
    assert len(links_of(db, i1)) == 0
    # Then 3
    assert snap(db, td) == before_td
    # Then 4
    row = reread(db, td)
    assert row.is_active is False


# [local-coder] ITA-RM-03
def test_ita_rm_03__the_links_of_a_deleted_item_are_deleted_the_item_is_not_touched(db, w1, ix, t1, t2, mk_link):
    """ITA-RM-03 — the links of a deleted item are deleted; the item is not touched.
    Rules: `remove_all_tags_from_item` R2"""
    mk_link(of=ix, to=t1)
    mk_link(of=ix, to=t2)
    before_ix = snap(db, ix)

    result = dao.remove_all_tags_from_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert result == 2
    # Then 2
    assert len(links_of(db, ix)) == 0
    # Then 3
    assert snap(db, ix) == before_ix


# [local-coder] ITA-RM-04
def test_ita_rm_04__the_links_of_other_items_stay(db, w1, i1, i2, t1, t2, mk_link):
    """ITA-RM-04 — the links of other items stay.
    Rules: `remove_all_tags_from_item` R3"""
    mk_link(of=i1, to=t1)
    l2 = mk_link(of=i2, to=t1)
    l3 = mk_link(of=i2, to=t2)
    before_l2 = snap(db, l2)
    before_l3 = snap(db, l3)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert len(links_of(db, i1)) == 0
    # Then 3
    assert len(links_of(db, i2)) == 2
    # Then 4
    assert snap(db, l2) == before_l2
    # Then 5
    assert snap(db, l3) == before_l3


# [local-coder] ITA-RM-06
def test_ita_rm_06__the_item_and_tag_rows_are_not_written_and_the_tag_counter_stays(db, w1, i1, mk_tag, mk_link):
    """ITA-RM-06 — the item and tag rows are not written and the tag counter stays.
    Rules: `remove_all_tags_from_item` R3"""
    k1 = mk_tag(name="Gasket", tag_code="gasket", usage_count=4)
    mk_link(of=i1, to=k1)
    before_k1 = snap(db, k1)
    before_i1 = snap(db, i1)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    row_k1 = reread(db, k1)
    assert row_k1.usage_count == 4
    # Then 3
    assert snap(db, k1) == before_k1
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert count_rows(db, "items") == 4
    # Then 6
    assert count_rows(db, "item_tags") == 6


# [local-coder] ITA-RM-07
def test_ita_rm_07__an_item_without_links_returns_0_and_nothing_is_written(db, w1, i1, i2, t1, mk_link):
    """ITA-RM-07 — an item without links returns 0 and nothing is written.
    Rules: `remove_all_tags_from_item` R4"""
    l2 = mk_link(of=i2, to=t1)
    before = written(db)
    before_l2 = snap(db, l2)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, l2) == before_l2


# [local-coder] ITA-RM-08
def test_ita_rm_08__an_unknown_item_id_returns_0_and_nothing_is_written(db, w1, i1, t1, mk_link):
    """ITA-RM-08 — an unknown item id returns 0 and nothing is written.
    Rules: `remove_all_tags_from_item` R4"""
    l1 = mk_link(of=i1, to=t1)
    before = written(db)
    before_l1 = snap(db, l1)

    result = dao.remove_all_tags_from_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, l1) == before_l1


# [claude] ITA-RM-09
def test_ita_rm_09__the_deletion_is_flushed_but_not_committed_gone_in_the_session_back(db, w1, u1, i1, t1, t2, mk_link):
    """ITA-RM-09 — the deletion is flushed but not committed: gone in the session, back after a rollback.
    Rules: `remove_all_tags_from_item` R5"""
    l1 = mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

        # Then 1
        assert result == 2
        # Then 2
        assert len(links_of(db, i1)) == 0
        sp.rollback()
        # Then 3
        assert len(links_of(db, i1)) == 2
        # Then 4
        row = reread(db, l1)
        assert row.tag_id == t1.id
        assert row.assigned_by == u1.id
        # Then 5
        assert commit_spy.call_count == 0


# [local-coder] ITA-RM-10
def test_ita_rm_10__a_link_added_but_not_flushed_is_not_deleted_and_is_saved_by_the(db, w1, i1, t2, u1):
    """ITA-RM-10 — a link added but not flushed is not deleted and is saved by the method's flush.
    Rules: `remove_all_tags_from_item` R5"""
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i1.id, tag_id=t2.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert len(links_of(db, i1)) == 1
    # Then 3
    row = links_of(db, i1)[0]
    assert row.tag_id == t2.id


# [local-coder] ITA-RM-11
def test_ita_rm_11__the_deleted_link_objects_leave_the_session_a_link_of_another_item(db, w1, i1, i2, t1, t2, mk_link):
    """ITA-RM-11 — the deleted link objects leave the session; a link of another item stays in it.
    Rules: `remove_all_tags_from_item` R6"""
    l1 = mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=t2)
    l3 = mk_link(of=i2, to=t1)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 2
    # Then 2
    assert l1 not in db
    # Then 3
    assert l2 not in db
    # Then 4
    assert l3 in db


# [local-coder] ITA-RM-12
def test_ita_rm_12__an_item_whose_tag_links_were_already_loaded_still_lists_them(db, w1, i1, t1, t2, mk_link):
    """ITA-RM-12 — an item whose tag links were already loaded still lists them.
    Rules: `remove_all_tags_from_item` R6"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    _loaded = len(i1.tag_assignments)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 2
    # Then 2
    assert len(i1.tag_assignments) == 2
    # Then 3
    assert len(links_of(db, i1)) == 0


# [claude] ITA-RM-13
def test_ita_rm_13__a_later_flush_of_the_item_does_not_bring_the_deleted_links_back(db, w1, i1, t1, t2, mk_link):
    """ITA-RM-13 — a later flush of the item does not bring the deleted links back.
    Rules: `remove_all_tags_from_item` R6"""
    mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    loaded = len(i1.tag_assignments)  # noqa: F841  (Given step 3: loads the collection into the session)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 2
    # Then 2
    i1.name = "Bolt M8 Long"
    db.flush()
    assert len(links_of(db, i1)) == 0
    # Then 3
    assert count_rows(db, "item_tag_assignments") == 0


# [claude] ITA-RM-14
def test_ita_rm_14__the_same_item_and_tag_can_be_linked_again_right_after_the_new_link(db, w1, i1, t1, mk_link):
    """ITA-RM-14 — the same item and tag can be linked again right after; the new link has a new id.
    Rules: `remove_all_tags_from_item` R6"""
    l1 = mk_link(of=i1, to=t1)
    l1_id = l1.id

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    new = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id})
    assert new.id != l1_id
    # Then 3
    assert len(links_of(db, i1)) == 1
    # Then 4
    row = links_of(db, i1)[0]
    assert row.id != l1_id
    assert row.tag_id == t1.id


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on ItemTagAssignment
# --------------------------------------------------------------------------- #


# [local-coder] ITA-INH-01
def test_ita_inh_01__create_with_a_dict_stores_a_link_with_assigned_at_set_and_assigned_by(db, w1, i1, t1):
    """ITA-INH-01 — create with a dict stores a link with assigned_at set and assigned_by None.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.item_id == i1.id
    assert row.tag_id == t1.id
    # Then 3
    assert row.assigned_by is None
    # Then 4
    assert row.assigned_at.tzinfo is None
    # Then 5
    assert close_to_now(row.assigned_at)
    # Then 6
    assert count_rows(db, "item_tag_assignments") == 1


# [local-coder] ITA-INH-02
def test_ita_inh_02__create_with_assigned_by_stores_it(db, w1, u2, i1, t1):
    """ITA-INH-02 — create with assigned_by stores it.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id, "assigned_by": u2.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.assigned_by == u2.id
    # Then 3
    assert row.assigned_at is not None


# [local-coder] ITA-INH-03
def test_ita_inh_03__create_with_an_itemtagassignmentcreate_schema_fails_on_flush_and(db, i1, t1):
    """ITA-INH-03 — create with an ItemTagAssignmentCreate schema fails on flush and saves nothing.
    Rules: inherited R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=ItemTagAssignmentCreate(item_id=i1.id, tag_id=t1.id))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert count_rows(db, "item_tag_assignments") == 0


# [local-coder] ITA-INH-05
def test_ita_inh_05__a_second_link_for_the_same_item_and_tag_fails_also_under_another(db, w2, i1, t1, mk_link):
    """ITA-INH-05 — a second link for the same item and tag fails also under another workspace.
    Rules: inherited R2, Errors row 2"""
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w2.id, "item_id": i1.id, "tag_id": t1.id})

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_item_tag" in str(exc.value.orig)
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert len(links_of(db, i1)) == 1


# [local-coder] ITA-INH-06
def test_ita_inh_06__create_with_an_unknown_item_id_fails_on_flush_and_saves_nothing(db, w1, t1):
    """ITA-INH-06 — create with an unknown item_id fails on flush and saves nothing.
    Rules: inherited R2, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": MISSING, "tag_id": t1.id})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tag_assignments_item_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] ITA-INH-07
def test_ita_inh_07__create_with_an_unknown_tag_id_fails_on_flush_and_saves_nothing(db, w1, i1):
    """ITA-INH-07 — create with an unknown tag_id fails on flush and saves nothing.
    Rules: inherited R2, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tag_assignments_tag_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] ITA-INH-08
def test_ita_inh_08__create_with_an_unknown_workspace_id_fails_on_flush_and_saves_nothing(db, i1, t1):
    """ITA-INH-08 — create with an unknown workspace_id fails on flush and saves nothing.
    Rules: inherited R2, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "item_id": i1.id, "tag_id": t1.id})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tag_assignments_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] ITA-INH-09
def test_ita_inh_09__create_with_an_unknown_assigned_by_fails_on_flush_and_saves_nothing(db, w1, i1, t1):
    """ITA-INH-09 — create with an unknown assigned_by fails on flush and saves nothing.
    Rules: inherited R2, Errors row 3"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id, "assigned_by": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tag_assignments_assigned_by_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [local-coder] ITA-INH-10
def test_ita_inh_10__create_saves_a_link_to_a_deleted_tag(db, w1, i1, td):
    """ITA-INH-10 — create saves a link to a deleted tag.
    Rules: inherited R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": td.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.tag_id == td.id
    # Then 3
    assert len(links_of(db, i1)) == 1


# [local-coder] ITA-INH-11
def test_ita_inh_11__create_saves_a_link_of_a_deleted_item(db, w1, ix, t1):
    """ITA-INH-11 — create saves a link of a deleted item.
    Rules: inherited R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": ix.id, "tag_id": t1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_id == ix.id
    # Then 3
    assert len(links_of(db, ix)) == 1


# [local-coder] ITA-INH-12
def test_ita_inh_12__create_saves_a_link_between_an_item_and_a_tag_of_different_workspaces(db, w1, i1, t9):
    """ITA-INH-12 — create saves a link between an item and a tag of different workspaces.
    Rules: inherited R3"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t9.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.item_id == i1.id
    assert row.tag_id == t9.id


# [local-coder] ITA-INH-13
def test_ita_inh_13__get_by_workspace_returns_the_links_of_that_workspace_only(db, w1, i1, i2, i9, t1, t2, t9, mk_link):
    """ITA-INH-13 — get_by_workspace returns the links of that workspace only.
    Rules: inherited R4 (the part that holds today)"""
    l1 = mk_link(of=i1, to=t1)
    l2 = mk_link(of=i2, to=t2)
    mk_link(of=i9, to=t9)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [l1.id, l2.id]
    # Then 2
    assert len(result) == 2


# [claude] ITA-INH-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order and the plan's, which can match by accident)",
)
def test_ita_inh_14__get_by_workspace_returns_the_links_in_id_order(db, w1, u2, i1, i2, t1, t2, mk_link):
    """ITA-INH-14 — get_by_workspace returns the links in id order.
    Rules: inherited R4 [BUG-100]"""
    l1 = mk_link(of=i1, to=t1)
    l2 = mk_link(of=i2, to=t2)
    l1.assigned_by = u2.id
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [l1.id, l2.id]
    # Then 2
    assert ids(result) == [l1.id, l2.id]


# [claude] ITA-INH-15
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_ita_inh_15__the_workspace_list_query_on_links_asks_the_database_for_id_order(db, w1, i1, t1, mk_link):
    """ITA-INH-15 — the workspace list query on links asks the database for id order.
    Rules: inherited R4 [BUG-100]"""
    l1 = mk_link(of=i1, to=t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [l1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "item_tag_assignments.id" in order_part


# [local-coder] ITA-INH-16
def test_ita_inh_16__remove_deletes_one_link_for_good(db, i1, t1, t2, mk_link):
    """ITA-INH-16 — remove deletes one link for good.
    Rules: inherited R5"""
    l1 = mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=t2)
    l1_id = l1.id
    before_l2 = snap(db, l2)

    result = dao.remove(db, id=l1_id)

    # Then 1
    assert result.id == l1_id
    # Then 2
    assert count_rows(db, "item_tag_assignments", id=l1_id) == 0
    # Then 3
    assert snap(db, l2) == before_l2


# [claude] ITA-INH-18
def test_ita_inh_18__deleting_a_tag_row_in_the_database_deletes_its_links(db, i1, t1, mk_tag, mk_link):
    """ITA-INH-18 — deleting a tag row in the database deletes its links.
    Rules: Overview model facts ("hard-deleting … a tag … deletes its links (`ON DELETE CASCADE`)")"""
    k1 = mk_tag(name="Scrap", tag_code="scrap")
    mk_link(of=i1, to=k1)
    l2 = mk_link(of=i1, to=t1)
    k1_id = k1.id  # taken before the When: after the DELETE and an expire, k1.id raises ObjectDeletedError

    db.execute(text("delete from item_tags where id = :i"), {"i": k1.id})

    # Then 1
    assert len(links_of(db, i1)) == 1
    # Then 2
    row = reread(db, l2)
    assert row.tag_id == t1.id
    # Then 3
    assert count_rows(db, "item_tag_assignments", tag_id=k1_id) == 0
