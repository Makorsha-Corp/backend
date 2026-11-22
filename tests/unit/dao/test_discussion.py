"""Unit tests for app/dao/discussion.py.

Implements tests/unit/dao/discussion.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None); `created_at` comes from the
database. The one spy is the `db.commit` wrapper of DSC-CR-10.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.discussion import discussion_dao
from app.models.discussion import Discussion
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton discussion_dao"
dao = discussion_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows; U1 = a profiles row", ids rising in that order.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "msg"; "reply on X" = msg, but parent_id X.id
@pytest.fixture
def mk_msg(db, w1, u1):
    """mk_msg(**columns) -> Discussion; the card's "but" columns as keywords."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "entity_type": "project", "entity_id": 501,
                  "user_id": u1.id, "message": "Hello"}
        fields.update(columns)
        return _add(db, Discussion(**fields))
    return _mk


# The "51 roots E1 ... E51, built with add_all and flushed" Given of DSC-GE-09, GE-10
@pytest.fixture
def mk_many(db, w1, u1):
    """mk_many(count) -> [E1, ... Ecount]; Ek = msg, but message f"Post {k}"."""
    def _mk(count):
        rows = [Discussion(workspace_id=w1.id, entity_type="project", entity_id=501,
                           user_id=u1.id, message=f"Post {k}")
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "older(X, h)"
def older(db, row, h):
    db.execute(text("UPDATE discussions SET created_at = now() - make_interval(hours => :h) WHERE id = :i"),
               {"h": h, "i": row.id})
    db.expire_all()


# Convention "bumpD(X)"
def bump(db, row):
    db.execute(text("UPDATE discussions SET message = message || '!' WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(x)": in the order returned
def ids(rows):
    return [row.id for row in rows]


# Convention "reply_ids(r)": in the order of r.replies
def reply_ids(root):
    return [row.id for row in root.replies]


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    row_id = row.id
    db.expire_all()
    return db.execute(select(Discussion).where(Discussion.id == row_id)).scalar_one_or_none()


# Convention "NOW_DB"
def now_db(db):
    return db.scalar(text("SELECT now()"))


# Convention "nothing written": the number of discussions rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(Discussion.__table__))


# The "count:" lines of DSC-CR-01, CR-10: discussions rows (all workspaces) with that entity_id
def count_with_entity(db, entity_id):
    table = Discussion.__table__
    return db.scalar(select(func.count()).select_from(table).where(table.c.entity_id == entity_id))


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
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

    def _selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def page_sql(self):
        """`page_sql`: the one recorded SELECT that contains LIMIT; fails loudly otherwise."""
        [statement] = [s for s in self._selects() if "LIMIT" in s]
        return statement

    def reply_sql(self):
        """`reply_sql`: the recorded SELECT that contains `parent_id IN` ("" when none was sent).

        Today none is sent during the call: `replies` is a self-referential
        `selectin` without `join_depth`, which SQLAlchemy skips (BUG-1490); the
        replies load lazily, one query per root, when first read.
        """
        found = [s for s in self._selects() if "parent_id IN" in s]
        return found[0] if found else ""  # the first one is the roots' replies

    def sql(self):
        """`sql`: the one SELECT from discussions sent by get_by_id (not the replies' load)."""
        [statement] = [s for s in self._selects() if "FROM discussions" in s and "parent_id IN" not in s]
        return statement


# Convention "order_part": the text of page_sql after its first ORDER BY and before LIMIT
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# DiscussionDAO.get_by_entity
# --------------------------------------------------------------------------- #


# [claude] DSC-GE-01
def test_dsc_ge_01__returns_the_record_s_roots_with_their_replies_and_the_number_of_roots(db, w1, mk_msg):
    """DSC-GE-01 — returns the record's roots with their replies, and the number of roots
    Rules: `get_by_entity` R1, Returns"""
    a = mk_msg()
    b = mk_msg(message="Second")
    r = mk_msg(parent_id=a.id)
    db.expire_all()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert isinstance(result[0], list)
    # Then 4
    assert isinstance(result[1], int)
    # Then 5
    assert set(ids(result[0])) == {a.id, b.id}
    # Then 6
    assert result[1] == 2
    # Then 7
    assert [i for i in result[0] if i.id == a.id][0].replies[0].id == r.id  # noqa: RUF015 (the card's expression)


# [claude] DSC-GE-02
def test_dsc_ge_02__a_root_of_another_workspace_is_not_matched(db, w1, w2, mk_msg):
    """DSC-GE-02 — a root of another workspace is not matched
    Rules: `get_by_entity` R3"""
    a = mk_msg()
    mk_msg(workspace_id=w2.id)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-03
def test_dsc_ge_03__a_root_of_another_entity_id_is_not_matched(db, w1, mk_msg):
    """DSC-GE-03 — a root of another entity id is not matched
    Rules: `get_by_entity` R3"""
    a = mk_msg()
    mk_msg(entity_id=502)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-04
def test_dsc_ge_04__a_root_of_another_entity_type_is_not_matched(db, w1, mk_msg):
    """DSC-GE-04 — a root of another entity type is not matched
    Rules: `get_by_entity` R3"""
    a = mk_msg()
    mk_msg(entity_type="machine")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-05
def test_dsc_ge_05__the_entity_type_with_a_capital_matches_nothing(db, w1, mk_msg):
    """DSC-GE-05 — the entity type with a capital matches nothing
    Rules: `get_by_entity` R3"""
    mk_msg()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="Project", entity_id=501)

    # Then 1
    assert result == ([], 0)


# [claude] DSC-GE-06
def test_dsc_ge_06__a_part_of_the_entity_type_matches_nothing(db, w1, mk_msg):
    """DSC-GE-06 — a part of the entity type matches nothing
    Rules: `get_by_entity` R3"""
    mk_msg()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="proj", entity_id=501)

    # Then 1
    assert result == ([], 0)


# [claude] DSC-GE-07
def test_dsc_ge_07__is_no_wildcard_a_stored_purchase_order_is_not_matched(db, w1, mk_msg):
    """DSC-GE-07 — _ is no wildcard: a stored "purchase-order" is not matched
    Rules: `get_by_entity` R3"""
    mk_msg(entity_type="purchase-order")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == ([], 0)


# [claude] DSC-GE-08
def test_dsc_ge_08__a_stored_type_with_a_leading_space_is_not_matched(db, w1, mk_msg):
    """DSC-GE-08 — a stored type with a leading space is not matched
    Rules: `get_by_entity` R3"""
    a = mk_msg()
    mk_msg(entity_type=" project")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-09
def test_dsc_ge_09__with_the_default_limit_51_roots_give_50_items_and_a_total_of_51(db, w1, mk_many):
    """DSC-GE-09 — with the default limit 51 roots give 50 items and a total of 51
    Rules: `get_by_entity` R2"""
    mk_many(51)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert len(result[0]) == 50
    # Then 2
    assert result[1] == 51


# [claude] DSC-GE-10
def test_dsc_ge_10__limit_1000_gives_all_51_roots(db, w1, mk_many):
    """DSC-GE-10 — limit=1000 gives all 51 roots
    Rules: `get_by_entity` R2"""
    mk_many(51)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, limit=1000)

    # Then 1
    assert len(result[0]) == 51
    # Then 2
    assert result[1] == 51


# [claude] DSC-GE-11
def test_dsc_ge_11__limit_0_gives_no_items_and_the_full_total(db, w1, mk_msg):
    """DSC-GE-11 — limit=0 gives no items and the full total
    Rules: `get_by_entity` R2"""
    mk_msg()
    mk_msg(message="Second")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, limit=0)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-12
def test_dsc_ge_12__skip_past_the_end_gives_no_items_and_the_full_total(db, w1, mk_msg):
    """DSC-GE-12 — skip past the end gives no items and the full total
    Rules: `get_by_entity` R5"""
    mk_msg()
    mk_msg(message="Second")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=2)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-13
def test_dsc_ge_13__skip_at_the_last_root_returns_it(db, w1, mk_msg):
    """DSC-GE-13 — skip at the last root returns it
    Rules: `get_by_entity` R5"""
    a = mk_msg()
    b = mk_msg(message="Second")
    older(db, a, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-14
def test_dsc_ge_14__limit_1_returns_one_root(db, w1, mk_msg):
    """DSC-GE-14 — limit=1 returns one root
    Rules: `get_by_entity` R2"""
    mk_msg()
    mk_msg(message="Second")

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, limit=1)

    # Then 1
    assert len(result[0]) == 1
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-15
def test_dsc_ge_15__a_negative_limit_raises_dataerror(db, w1, mk_msg):
    """DSC-GE-15 — a negative limit raises DataError
    Rules: `get_by_entity` R5, Errors"""
    mk_msg()
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-GE-16
def test_dsc_ge_16__a_negative_skip_raises_dataerror(db, w1, mk_msg):
    """DSC-GE-16 — a negative skip raises DataError
    Rules: `get_by_entity` R5, Errors"""
    mk_msg()
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-GE-17
def test_dsc_ge_17__roots_come_oldest_first_whatever_the_ids(db, w1, mk_msg):
    """DSC-GE-17 — roots come oldest first, whatever the ids
    Rules: `get_by_entity` R4"""
    a = mk_msg()
    b = mk_msg(message="Second")
    c = mk_msg(message="Third")
    older(db, b, 2)
    older(db, c, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [b.id, c.id, a.id]


# [claude] DSC-GE-18
def test_dsc_ge_18__the_hour_older_root_comes_first_then_the_tied_ones(db, w1, mk_msg):
    """DSC-GE-18 — the hour-older root comes first, then the tied ones
    Rules: `get_by_entity` R4"""
    a = mk_msg()
    b = mk_msg(message="Second")
    c = mk_msg(message="Third")
    d = mk_msg(message="Old")
    older(db, d, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert len(result[0]) == 4
    # Then 2
    assert result[0][0].id == d.id
    # Then 3
    assert set(ids(result[0])[1:]) == {a.id, b.id, c.id}


# [claude] DSC-GE-19
@pytest.mark.xfail(strict=False, reason="BUG-1438: Discussion messages of one time come back in no fixed order")
def test_dsc_ge_19__tied_roots_come_in_id_order_also_after_the_first_was_updated(db, w1, mk_msg):
    """DSC-GE-19 — tied roots come in id order, also after the first was updated
    Rules: `get_by_entity` R4 [BUG-1438]"""
    a = mk_msg()
    b = mk_msg(message="Second")
    c = mk_msg(message="Third")
    d = mk_msg(message="Old")
    older(db, d, 1)
    seqscan(db)
    bump(db, a)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert len(result[0]) == 4
    # Then 2
    assert ids(result[0]) == [d.id, a.id, b.id, c.id]


# [claude] DSC-GE-20
@pytest.mark.xfail(strict=False, reason="BUG-1438: Discussion messages of one time come back in no fixed order")
def test_dsc_ge_20__tied_roots_paged_one_at_a_time_neither_repeat_nor_miss_a_root(db, w1, mk_msg):
    """DSC-GE-20 — tied roots paged one at a time neither repeat nor miss a root
    Rules: `get_by_entity` R4 [BUG-1438]"""
    a = mk_msg()
    b = mk_msg(message="Second")
    c = mk_msg(message="Third")
    d = mk_msg(message="Fourth")
    seqscan(db)
    bump(db, a)

    pages = [dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=k, limit=1)[0] for k in range(4)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [a.id, b.id, c.id, d.id]


# [claude] DSC-GE-21
@pytest.mark.xfail(strict=True, reason="BUG-1438: Discussion messages of one time come back in no fixed order")
def test_dsc_ge_21__the_page_query_orders_by_created_at_then_id_ascending(db, w1, mk_msg):
    """DSC-GE-21 — the page query orders by created_at, then id, ascending
    Rules: `get_by_entity` R4 [BUG-1438]"""
    a = mk_msg()

    with StatementRecorder(db) as rec:
        result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert "created_at" in order_part_of(rec.page_sql())
    # Then 3
    assert ".id" in order_part_of(rec.page_sql())
    # Then 4
    assert order_part_of(rec.page_sql()).index("created_at") < order_part_of(rec.page_sql()).index(".id")
    # Then 5
    assert "DESC" not in order_part_of(rec.page_sql()).upper()


# [claude] DSC-GE-22
def test_dsc_ge_22__replies_are_filtered_before_the_page_an_older_reply_takes_no_place(db, w1, mk_msg):
    """DSC-GE-22 — replies are filtered before the page: an older reply takes no place
    Rules: `get_by_entity` R1, R4"""
    a = mk_msg()
    b = mk_msg(message="Second")
    x = mk_msg(parent_id=a.id)
    older(db, x, 3)
    older(db, a, 2)
    older(db, b, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-23
def test_dsc_ge_23__another_entity_s_root_is_filtered_before_the_page_and_takes_no_place(db, w1, mk_msg):
    """DSC-GE-23 — another entity's root is filtered before the page and takes no place
    Rules: `get_by_entity` R3, R4"""
    x = mk_msg(entity_id=502)
    a = mk_msg()
    b = mk_msg(message="Second")
    older(db, x, 3)
    older(db, a, 2)
    older(db, b, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] DSC-GE-24
@pytest.mark.xfail(strict=False, reason="BUG-1439: Replies in a discussion thread have no order")
def test_dsc_ge_24__tied_replies_come_in_id_order_also_after_the_first_was_updated(db, w1, mk_msg):
    """DSC-GE-24 — tied replies come in id order, also after the first was updated
    Rules: `get_by_entity` R6 [BUG-1439]"""
    a = mk_msg()
    r1 = mk_msg(parent_id=a.id)
    r2 = mk_msg(parent_id=a.id, message="Two")
    r3 = mk_msg(parent_id=a.id, message="Three")
    seqscan(db)
    bump(db, r1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert reply_ids(result[0][0]) == [r1.id, r2.id, r3.id]


# [claude] DSC-GE-25
@pytest.mark.xfail(strict=False, reason="BUG-1439: Replies in a discussion thread have no order")
def test_dsc_ge_25__replies_come_oldest_first_whatever_the_ids(db, w1, mk_msg):
    """DSC-GE-25 — replies come oldest first, whatever the ids
    Rules: `get_by_entity` R6 [BUG-1439]"""
    a = mk_msg()
    r1 = mk_msg(parent_id=a.id)
    r2 = mk_msg(parent_id=a.id, message="Two")
    r3 = mk_msg(parent_id=a.id, message="Three")
    older(db, r2, 2)
    older(db, r3, 1)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert reply_ids(result[0][0]) == [r2.id, r3.id, r1.id]


# [claude] DSC-GE-26
@pytest.mark.xfail(strict=True, reason="BUG-1439: Replies in a discussion thread have no order; "
                                       "BUG-1490: A discussion page loads its replies one query per message")
def test_dsc_ge_26__the_replies_query_has_an_order_by(db, w1, mk_msg):
    """DSC-GE-26 — the replies' query has an ORDER BY
    Rules: `get_by_entity` R6 [BUG-1439] [BUG-1490]"""
    a = mk_msg()
    r1 = mk_msg(parent_id=a.id)
    db.expire_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert reply_ids(result[0][0]) == [r1.id]
    # Then 2
    assert "parent_id IN" in rec.reply_sql()
    # Then 3
    assert "ORDER BY" in rec.reply_sql()


# [claude] DSC-GE-27
def test_dsc_ge_27__every_reply_of_the_root_is_loaded_none_is_an_item(db, w1, mk_msg):
    """DSC-GE-27 — every reply of the root is loaded, none is an item
    Rules: `get_by_entity` R1, R6"""
    a = mk_msg()
    r1 = mk_msg(parent_id=a.id)
    r2 = mk_msg(parent_id=a.id, message="Two")
    r3 = mk_msg(parent_id=a.id, message="Three")
    db.expire_all()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert set(reply_ids(result[0][0])) == {r1.id, r2.id, r3.id}
    # Then 3
    assert result[1] == 1


# [claude] DSC-GE-28
def test_dsc_ge_28__a_reply_under_w2_and_a_reply_on_another_entity_still_load_with_the_roo(db, w1, w2, mk_msg):
    """DSC-GE-28 — a reply under W2 and a reply on another entity still load with the root
    Rules: `get_by_entity` R6a"""
    a = mk_msg()
    r1 = mk_msg(parent_id=a.id, workspace_id=w2.id)
    r2 = mk_msg(parent_id=a.id, entity_id=502)
    db.expire_all()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert set(reply_ids(result[0][0])) == {r1.id, r2.id}


# [claude] DSC-GE-29
def test_dsc_ge_29__the_record_is_not_looked_at_an_unknown_type_and_a_negative_id_are_list(db, w1, mk_msg):
    """DSC-GE-29 — the record is not looked at: an unknown type and a negative id are listed
    Rules: `get_by_entity` R7"""
    a = mk_msg(entity_type="unknown_type", entity_id=-5)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="unknown_type", entity_id=-5)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-30
def test_dsc_ge_30__writes_nothing_a_pending_root_stays_pending_an_unflushed_edit_stays_un(db, w1, u1, mk_msg):
    """DSC-GE-30 — writes nothing: a pending root stays pending, an unflushed edit stays unflushed
    Rules: `get_by_entity` Side effects"""
    a = mk_msg()
    b = mk_msg(entity_id=502)
    b.message = "Edited"
    p = Discussion(workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="Pending")
    db.add(p)
    before_count = stored_count(db)

    with StatementRecorder(db) as rec:
        result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written() == []
    # Then 7
    assert "FOR UPDATE" not in rec.page_sql().upper()
    # Then 8
    assert stored_count(db) == before_count


# [claude] DSC-GE-31
def test_dsc_ge_31__asked_for_w2_only_the_w2_root_is_listed_though_the_w1_root_is_earlier(db, w2, mk_msg):
    """DSC-GE-31 — asked for W2, only the W2 root is listed, though the W1 root is earlier
    Rules: `get_by_entity` R3"""
    mk_msg()
    z = mk_msg(workspace_id=w2.id)

    result = dao.get_by_entity(db, workspace_id=w2.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [z.id]
    # Then 2
    assert result[1] == 1


# [claude] DSC-GE-32
def test_dsc_ge_32__a_leading_space_in_the_argument_matches_nothing(db, w1, mk_msg):
    """DSC-GE-32 — a leading space in the argument matches nothing
    Rules: `get_by_entity` R3"""
    mk_msg()

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type=" project", entity_id=501)

    # Then 1
    assert result == ([], 0)


# [claude] DSC-GE-33
def test_dsc_ge_33__a_root_of_a_lower_entity_id_is_not_matched(db, w1, mk_msg):
    """DSC-GE-33 — a root of a lower entity id is not matched
    Rules: `get_by_entity` R3"""
    a = mk_msg()
    mk_msg(entity_id=500)

    result = dao.get_by_entity(db, workspace_id=w1.id, entity_type="project", entity_id=501)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# --------------------------------------------------------------------------- #
# DiscussionDAO.get_by_id
# --------------------------------------------------------------------------- #


# [claude] DSC-GI-01
def test_dsc_gi_01__a_root_is_returned_the_instance_the_session_holds_positional_call(db, w1, mk_msg):
    """DSC-GI-01 — a root is returned, the instance the session holds (positional call)
    Rules: `get_by_id` R1, Returns"""
    mk_msg(message="Second")
    a = mk_msg()

    result = dao.get_by_id(db, a.id, w1.id)

    # Then 1
    assert isinstance(result, Discussion)
    # Then 2
    assert result is a


# [claude] DSC-GI-02
def test_dsc_gi_02__a_reply_is_returned(db, w1, mk_msg):
    """DSC-GI-02 — a reply is returned
    Rules: `get_by_id` R1"""
    a = mk_msg()
    r = mk_msg(parent_id=a.id)

    result = dao.get_by_id(db, discussion_id=r.id, workspace_id=w1.id)

    # Then 1
    assert result.id == r.id


# [claude] DSC-GI-03
def test_dsc_gi_03__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_msg):
    """DSC-GI-03 — another workspace's id returns None, when that row is the earlier one
    Rules: `get_by_id` R2"""
    z = mk_msg(workspace_id=w2.id)
    mk_msg()

    result = dao.get_by_id(db, discussion_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] DSC-GI-04
def test_dsc_gi_04__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, mk_msg):
    """DSC-GI-04 — another workspace's id returns None, when that row is the later one
    Rules: `get_by_id` R2"""
    mk_msg()
    z = mk_msg(workspace_id=w2.id)

    result = dao.get_by_id(db, discussion_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] DSC-GI-05
def test_dsc_gi_05__the_id_under_another_workspace_returns_none(db, w2, mk_msg):
    """DSC-GI-05 — the id under another workspace returns None
    Rules: `get_by_id` R2"""
    a = mk_msg()

    result = dao.get_by_id(db, discussion_id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] DSC-GI-06
def test_dsc_gi_06__an_unknown_id_returns_none(db, w1, mk_msg):
    """DSC-GI-06 — an unknown id returns None
    Rules: `get_by_id` R2"""
    mk_msg()

    result = dao.get_by_id(db, discussion_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] DSC-GI-07
def test_dsc_gi_07__id_0_returns_none(db, w1, mk_msg):
    """DSC-GI-07 — id 0 returns None
    Rules: `get_by_id` R2"""
    mk_msg()

    result = dao.get_by_id(db, discussion_id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] DSC-GI-08
def test_dsc_gi_08__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u1, mk_msg):
    """DSC-GI-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
    Rules: `get_by_id` Side effects"""
    a = mk_msg()
    b = mk_msg(message="Second")
    b.message = "Edited"
    p = Discussion(workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="Pending")
    db.add(p)
    before_count = stored_count(db)

    with StatementRecorder(db) as rec:
        result = dao.get_by_id(db, discussion_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written() == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql().upper()
    # Then 8
    assert stored_count(db) == before_count


# --------------------------------------------------------------------------- #
# DiscussionDAO.create
# --------------------------------------------------------------------------- #


# [claude] DSC-CR-01
def test_dsc_cr_01__a_root_is_stored_with_exactly_the_given_values_positional_call(db, w1, u1):
    """DSC-CR-01 — a root is stored with exactly the given values (positional call)
    Rules: `create` R1, R4, Returns, Side effects"""

    result = dao.create(db, w1.id, "project", 501, u1.id, "Hello")

    # Then 1
    assert isinstance(result, Discussion)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.entity_type == "project"
    assert row.entity_id == 501
    # Then 4
    assert row.user_id == u1.id
    assert row.message == "Hello"
    assert row.parent_id is None
    # Then 5
    assert row.created_at == now_db(db)
    # Then 6
    assert count_with_entity(db, 501) == 1


# [claude] DSC-CR-02
def test_dsc_cr_02__a_reply_stores_its_parent(db, w1, u1, mk_msg):
    """DSC-CR-02 — a reply stores its parent
    Rules: `create` R1"""
    a = mk_msg()

    result = dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="Reply", parent_id=a.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.parent_id == a.id
    assert row.message == "Reply"


# [claude] DSC-CR-03
def test_dsc_cr_03__nothing_is_validated_an_empty_message_a_30_character_type_a_negative_i(db, w1):
    """DSC-CR-03 — nothing is validated: an empty message, a 30-character type, a negative id, no user
    Rules: `create` R2"""

    result = dao.create(db, workspace_id=w1.id, entity_type="x" * 30, entity_id=-5, user_id=None, message="")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.entity_type == "x" * 30
    assert row.entity_id == -5
    # Then 3
    assert row.user_id is None
    assert row.message == ""


# [claude] DSC-CR-04
def test_dsc_cr_04__a_reply_to_a_reply_on_another_entity_is_stored(db, w1, u1, mk_msg):
    """DSC-CR-04 — a reply to a reply, on another entity, is stored
    Rules: `create` R2"""
    a = mk_msg()
    r = mk_msg(parent_id=a.id)

    result = dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=502, user_id=u1.id, message="Deep", parent_id=r.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.parent_id == r.id
    assert row.entity_id == 502


# [claude] DSC-CR-05
def test_dsc_cr_05__a_reply_under_another_workspace_than_its_parent_is_stored(db, w2, u1, mk_msg):
    """DSC-CR-05 — a reply under another workspace than its parent is stored
    Rules: `create` R2"""
    a = mk_msg()

    result = dao.create(db, workspace_id=w2.id, entity_type="project", entity_id=501, user_id=u1.id, message="Far", parent_id=a.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.parent_id == a.id


# [claude] DSC-CR-06
def test_dsc_cr_06__an_entity_type_of_31_characters_raises_dataerror(db, w1, u1):
    """DSC-CR-06 — an entity type of 31 characters raises DataError
    Rules: `create` R3, Errors"""
    before_count = stored_count(db)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, workspace_id=w1.id, entity_type="x" * 31, entity_id=501, user_id=u1.id, message="Hello")

    # Then 1
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-CR-07
def test_dsc_cr_07__message_none_raises_integrityerror_23502(db, w1, u1):
    """DSC-CR-07 — message None raises IntegrityError 23502
    Rules: `create` R3, Errors"""
    before_count = stored_count(db)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message=None)

    # Then 1
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-CR-08
def test_dsc_cr_08__an_unknown_parent_raises_integrityerror_23503(db, w1, u1):
    """DSC-CR-08 — an unknown parent raises IntegrityError 23503
    Rules: `create` R3, Errors"""
    before_count = stored_count(db)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="Hello", parent_id=MISSING)

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-CR-09
def test_dsc_cr_09__an_unknown_user_raises_integrityerror_23503(db, w1):
    """DSC-CR-09 — an unknown user raises IntegrityError 23503
    Rules: `create` R3, Errors"""
    before_count = stored_count(db)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=MISSING, message="Hello")

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before_count


# [claude] DSC-CR-10
def test_dsc_cr_10__flushed_not_committed_a_rollback_removes_the_row(db, w1, u1):
    """DSC-CR-10 — flushed, not committed: a rollback removes the row
    Rules: `create` R5, Side effects"""
    with patch.object(db, "commit", wraps=db.commit) as spy:
        sp = db.begin_nested()
        result = dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="Hello")

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_with_entity(db, 501) == 1
        sp.rollback()
        # Then 3
        assert count_with_entity(db, 501) == 0
    # Then 4
    assert spy.call_count == 0


# [claude] DSC-CR-11
def test_dsc_cr_11__a_message_with_spaces_around_it_is_stored_as_given(db, w1, u1):
    """DSC-CR-11 — a message with spaces around it is stored as given
    Rules: `create` R1, R2"""

    result = dao.create(db, workspace_id=w1.id, entity_type="project", entity_id=501, user_id=u1.id, message="  Hi  ")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.message == "  Hi  "
