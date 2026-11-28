"""Unit tests for app/dao/account_tag.py.

Implements tests/unit/dao/account_tag.cases.md, one test per case, in card order.
Real Postgres session (`db` fixture). Nothing is patched (Conventions, Externals:
None); the **rolled back** cards wrap `db.commit` in a spy that still calls it.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`)
import re
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.account_tag import account_tag_dao
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.schemas.account_tag import AccountTagCreate, AccountTagUpdate
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton account_tag_dao"
dao = account_tag_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (W1, W2; every test)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _tag(default_workspace_id, name, tag_code, **columns):
    return AccountTag(**{
        "workspace_id": default_workspace_id, "is_system_tag": False, "is_active": True, "usage_count": 0,
        "name": name, "tag_code": tag_code, **columns,
    })


# Convention "tag": W1, not a system tag, active, usage_count 0; name and tag_code from the card
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name=..., tag_code=..., **columns) -> AccountTag, added and flushed."""
    def _mk(*, name, tag_code, **columns):
        return _add(db, _tag(w1.id, name, tag_code, **columns))
    return _mk


# Convention "system tag" = a tag, but is_system_tag True
@pytest.fixture
def mk_system_tag(db, w1):
    """mk_system_tag(name=..., tag_code=..., **columns) -> AccountTag, added and flushed."""
    def _mk(*, name, tag_code, **columns):
        return _add(db, _tag(w1.id, name, tag_code, is_system_tag=True, **columns))
    return _mk


# Given lines "N tags ... built with add_all and flushed"
def add_many(db, rows):
    db.add_all(rows)
    db.flush()
    return rows


# Convention "bumpT(X)"
def bump_t(db, x):
    db.execute(text("UPDATE account_tags SET description = coalesce(description, '') || '!' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# Convention "seqscan": three steps, in this order
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)" / "names(result)": in the order returned
def ids(result):
    return [t.id for t in result]


def names(result):
    return [t.name for t in result]


def _id_of(row):
    return sa_inspect(row).identity[0]


# Convention "stored_count(T)": the database value, without expiring T
def stored_count(db, t):
    return db.scalar(select(AccountTag.usage_count).where(AccountTag.id == _id_of(t)))


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(type(row)).where(type(row).id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table, after expire_all
def snap(db, row):
    table = type(row).__table__
    row_id = _id_of(row)
    db.expire_all()
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of account_tags rows (all workspaces)
def written_count(db):
    return db.scalar(select(func.count()).select_from(AccountTag.__table__))


# "count:" lines: rows in all workspaces, with the filter stated
def count_rows(db, model, *where):
    return db.scalar(select(func.count()).select_from(model.__table__).where(*where))


# Convention "rolled back": the spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# Convention "Statement recorder": SQL the session's connection sends during the When
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

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def updates(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("UPDATE")]

    def sql(self):
        """The one SELECT from `account_tags`; fails loudly unless there is exactly one."""
        [statement] = [
            s for s in self.statements if s.lstrip().upper().startswith("SELECT") and "FROM account_tags" in s
        ]
        return statement


# Convention "relative update" (BUG-1484, ATG-INC-06, DEC-08): an UPDATE of account_tags whose
# SET computes the counter from the stored column (`usage_count = usage_count + / - ...`);
# for the decrease, the same statement's WHERE also tests the stored column (`usage_count >`).
_REL_INC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:account_tags\.)?usage_count\s*\+", re.IGNORECASE)
_REL_DEC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:account_tags\.)?usage_count\s*-", re.IGNORECASE)
_DEC_GUARD = re.compile(r"WHERE.*usage_count\s*>", re.IGNORECASE | re.DOTALL)


# Convention "order_part": the text of `sql` after ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AccountTagDAO.get_by_tag_code_in_workspace
# --------------------------------------------------------------------------- #


# [claude] ATG-CODE-01
def test_atg_code_01__returns_the_workspace_s_tag_with_that_code(db, w1, mk_tag):
    """ATG-CODE-01 — returns the workspace's tag with that code.
    Rules: `get_by_tag_code_in_workspace` R1, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    mk_tag(name="Client", tag_code="client")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert isinstance(result, AccountTag)
    # Then 2
    assert result.id == t1.id


# [claude] ATG-CODE-02
def test_atg_code_02__another_workspace_s_tags_with_that_code_before_and_after_by_id_are(db, w1, w2, mk_tag):
    """ATG-CODE-02 — another workspace's tags with that code, before and after by id, are never returned.
    Rules: `get_by_tag_code_in_workspace` R1"""
    mk_tag(name="Supplier", tag_code="supplier", workspace_id=w2.id)
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    mk_tag(name="Supplier", tag_code="supplier", workspace_id=w2.id)

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result.id == t1.id


# [claude] ATG-CODE-03
def test_atg_code_03__a_code_that_exists_only_in_another_workspace_returns_none(db, w1, w2, mk_tag):
    """ATG-CODE-03 — a code that exists only in another workspace returns None.
    Rules: `get_by_tag_code_in_workspace` R1"""
    mk_tag(name="Vendor", tag_code="vendor", workspace_id=w2.id)

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="vendor")

    # Then 1
    assert result is None


# [claude] ATG-CODE-04
def test_atg_code_04__an_unknown_workspace_returns_none(db, mk_tag):
    """ATG-CODE-04 — an unknown workspace returns None.
    Rules: `get_by_tag_code_in_workspace` R1"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=MISSING, tag_code="supplier")

    # Then 1
    assert result is None


# [claude] ATG-CODE-05
def test_atg_code_05__argument_with_capitals_returns_none(db, w1, mk_tag):
    """ATG-CODE-05 — argument with capitals returns None.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="Supplier")

    # Then 1
    assert result is None


# [claude] ATG-CODE-06
def test_atg_code_06__argument_with_a_leading_space_returns_none(db, w1, mk_tag):
    """ATG-CODE-06 — argument with a leading space returns None.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code=" supplier")

    # Then 1
    assert result is None


# [claude] ATG-CODE-07
def test_atg_code_07__a_part_of_the_code_returns_none(db, w1, mk_tag):
    """ATG-CODE-07 — a part of the code returns None.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="sup")

    # Then 1
    assert result is None


# [claude] ATG-CODE-08
def test_atg_code_08__sup_is_not_a_pattern(db, w1, mk_tag):
    """ATG-CODE-08 — "sup%" is not a pattern.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="sup%")

    # Then 1
    assert result is None


# [claude] ATG-CODE-09
def test_atg_code_09__s_pplier_is_not_a_pattern(db, w1, mk_tag):
    """ATG-CODE-09 — "s_pplier" is not a pattern.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="s_pplier")

    # Then 1
    assert result is None


# [claude] ATG-CODE-10
def test_atg_code_10__a_code_of_none_returns_none(db, w1, mk_tag):
    """ATG-CODE-10 — a code of None returns None.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code=None)

    # Then 1
    assert result is None


# [claude] ATG-CODE-11
def test_atg_code_11__stored_side_capitals_or_a_leading_space_in_the_stored_code_are_not(db, w1, mk_tag):
    """ATG-CODE-11 — stored side: capitals or a leading space in the stored code are not matched by the plain code.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier A", tag_code="Supplier")
    mk_tag(name="Supplier B", tag_code=" supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result is None


# [claude] ATG-CODE-12
def test_atg_code_12__a_deleted_tag_and_a_system_tag_are_found_by_their_codes(db, w1, mk_system_tag):
    """ATG-CODE-12 — a deleted tag and a system tag are found by their codes.
    Rules: `get_by_tag_code_in_workspace` R3 (P1)"""
    td = mk_system_tag(name="Vendor", tag_code="vendor", is_active=False)

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="vendor")

    # Then 1
    assert result.id == td.id
    # Then 2
    assert result.is_active is False


# [claude] ATG-CODE-13
def test_atg_code_13__two_tags_with_one_code_one_of_them_the_read_writes_nothing(db, w1, mk_tag):
    """ATG-CODE-13 — two tags with one code: one of them; the read writes nothing.
    Rules: `get_by_tag_code_in_workspace` R4, Side effects"""
    t1 = mk_tag(name="Bank A", tag_code="bank")
    t2 = mk_tag(name="Bank B", tag_code="bank")
    t2.name = "Bank Edited"
    p = AccountTag(workspace_id=w1.id, name="Pending", tag_code="bank", is_system_tag=False, is_active=True, usage_count=0)
    db.add(p)

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="bank")

    # Then 1
    assert result.id in {t1.id, t2.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1


# [claude] ATG-CODE-14
def test_atg_code_14__argument_with_a_trailing_space_returns_none(db, w1, mk_tag):
    """ATG-CODE-14 — argument with a trailing space returns None.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="supplier ")

    # Then 1
    assert result is None


# [claude] ATG-CODE-15
def test_atg_code_15__stored_side_in_the_stored_code_is_not_a_wildcard(db, w1, mk_tag):
    """ATG-CODE-15 — stored side: "_" in the stored code is not a wildcard.
    Rules: `get_by_tag_code_in_workspace` R2"""
    mk_tag(name="Supplier", tag_code="s_pplier")

    result = dao.get_by_tag_code_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# AccountTagDAO.get_active_tags_in_workspace
# --------------------------------------------------------------------------- #


# [claude] ATG-ACT-01
def test_atg_act_01__returns_a_list_of_the_workspace_s_active_system_and_user_tags(db, w1, mk_tag, mk_system_tag):
    """ATG-ACT-01 — returns a list of the workspace's active system and user tags.
    Rules: `get_active_tags_in_workspace` R1, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    s1 = mk_system_tag(name="Client", tag_code="client")

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [t1.id, s1.id]
    # Then 3
    assert isinstance(result[0], AccountTag)


# [claude] ATG-ACT-02
def test_atg_act_02__deleted_user_and_system_tags_are_not_returned(db, w1, mk_tag, mk_system_tag):
    """ATG-ACT-02 — deleted user and system tags are not returned.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Old", tag_code="old", is_active=False)
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    mk_system_tag(name="Seed", tag_code="seed", is_active=False)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [claude] ATG-ACT-03
def test_atg_act_03__another_workspace_s_tags_are_not_returned(db, w1, w2, mk_tag):
    """ATG-ACT-03 — another workspace's tags are not returned.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Far", tag_code="far", workspace_id=w2.id)
    t1 = mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


# [claude] ATG-ACT-04
def test_atg_act_04__an_unknown_workspace_returns_an_empty_list(db, mk_tag):
    """ATG-ACT-04 — an unknown workspace returns an empty list.
    Rules: `get_active_tags_in_workspace` R1"""
    mk_tag(name="Supplier", tag_code="supplier")

    result = dao.get_active_tags_in_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] ATG-ACT-05
def test_atg_act_05__every_active_tag_is_returned_101_give_101(db, w1):
    """ATG-ACT-05 — every active tag is returned: 101 give 101.
    Rules: `get_active_tags_in_workspace` R2 [BUG-1485]"""
    add_many(db, [_tag(w1.id, f"Tag {k:03d}", f"tag_{k:03d}") for k in range(1, 102)])

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 101


# [claude] ATG-ACT-06
def test_atg_act_06__a_deleted_tag_ahead_of_100_active_ones_does_not_take_a_place(db, w1, mk_system_tag):
    """ATG-ACT-06 — a deleted tag ahead of 100 active ones does not take a place.
    Rules: `get_active_tags_in_workspace` R1, R2 (filter before the cap; holds today and after the fix)"""
    td = mk_system_tag(name="Aaa", tag_code="aaa", is_active=False)
    add_many(db, [_tag(w1.id, f"Tag {k:03d}", f"tag_{k:03d}") for k in range(1, 101)])

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert td.id not in ids(result)


# [claude] ATG-ACT-07
def test_atg_act_07__every_system_tag_comes_before_every_user_tag(db, w1, mk_tag, mk_system_tag):
    """ATG-ACT-07 — every system tag comes before every user tag.
    Rules: `get_active_tags_in_workspace` R3 [BUG-1482]"""
    t1 = mk_tag(name="Alpha", tag_code="alpha")
    t2 = mk_tag(name="Bravo", tag_code="bravo")
    s1 = mk_system_tag(name="Zed", tag_code="zed")
    seqscan(db)
    bump_t(db, s1)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id, s1.id]
    # Then 2
    assert ids(result) == [s1.id, t1.id, t2.id]


# [claude] ATG-ACT-08
def test_atg_act_08__within_a_group_name_case_insensitive_then_id(db, w1, mk_tag):
    """ATG-ACT-08 — within a group: name case-insensitive, then id.
    Rules: `get_active_tags_in_workspace` R4 [BUG-1482]"""
    t1 = mk_tag(name="bravo", tag_code="bravo")
    t2 = mk_tag(name="Alpha", tag_code="alpha_upper")
    t3 = mk_tag(name="alpha", tag_code="alpha_lower")
    t4 = mk_tag(name="Charlie", tag_code="charlie")
    seqscan(db)
    bump_t(db, t2)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id, t3.id, t4.id]
    # Then 2
    assert ids(result) == [t2.id, t3.id, t1.id, t4.id]


# [claude] ATG-ACT-09
def test_atg_act_09__the_query_orders_by_system_first_then_name_case_insensitive_then_id(db, w1, mk_tag):
    """ATG-ACT-09 — the query orders by system first, then name case-insensitive, then id.
    Rules: `get_active_tags_in_workspace` R3, R4 [BUG-1482]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")

    with StatementRecorder(db) as recorder:
        result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "account_tags.is_system_tag DESC" in order_part
    # Then 4
    assert "lower(account_tags.name)" in order_part
    # Then 5
    assert "account_tags.id" in order_part


# [claude] ATG-ACT-10
def test_atg_act_10__the_read_writes_nothing_and_keeps_the_caller_s_pending_changes(db, w1, w2, mk_tag):
    """ATG-ACT-10 — the read writes nothing and keeps the caller's pending changes.
    Rules: `get_active_tags_in_workspace` Side effects"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client", workspace_id=w2.id)
    t2.name = "Client Edited"
    p = AccountTag(workspace_id=w1.id, name="Pending", tag_code="pending", is_system_tag=False, is_active=True, usage_count=0)
    db.add(p)
    before = written_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert written_count(db) == before


# --------------------------------------------------------------------------- #
# AccountTagDAO.get_system_tags_in_workspace
# --------------------------------------------------------------------------- #


# [claude] ATG-SYS-01
def test_atg_sys_01__returns_a_list_of_the_workspace_s_system_tags_no_user_tag(db, w1, mk_tag, mk_system_tag):
    """ATG-SYS-01 — returns a list of the workspace's system tags, no user tag.
    Rules: `get_system_tags_in_workspace` R1, Returns"""
    s1 = mk_system_tag(name="Supplier", tag_code="supplier")
    mk_tag(name="Custom", tag_code="custom")
    s3 = mk_system_tag(name="Client", tag_code="client")

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [s1.id, s3.id]
    # Then 3
    assert isinstance(result[0], AccountTag)


# [claude] ATG-SYS-02
def test_atg_sys_02__another_workspace_s_system_tags_are_not_returned(db, w1, w2, mk_system_tag):
    """ATG-SYS-02 — another workspace's system tags are not returned.
    Rules: `get_system_tags_in_workspace` R1"""
    mk_system_tag(name="Far", tag_code="far", workspace_id=w2.id)
    s1 = mk_system_tag(name="Supplier", tag_code="supplier")

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]


# [claude] ATG-SYS-03
def test_atg_sys_03__an_unknown_workspace_returns_an_empty_list(db, mk_system_tag):
    """ATG-SYS-03 — an unknown workspace returns an empty list.
    Rules: `get_system_tags_in_workspace` R1"""
    mk_system_tag(name="Supplier", tag_code="supplier")

    result = dao.get_system_tags_in_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] ATG-SYS-04
def test_atg_sys_04__no_limit_101_system_tags_give_101(db, w1):
    """ATG-SYS-04 — no limit: 101 system tags give 101.
    Rules: `get_system_tags_in_workspace` R1"""
    add_many(db, [_tag(w1.id, f"Seed {k:03d}", f"seed_{k:03d}", is_system_tag=True) for k in range(1, 102)])

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101


# [claude] ATG-SYS-05
def test_atg_sys_05__a_deleted_system_tag_is_not_returned(db, w1, mk_system_tag):
    """ATG-SYS-05 — a deleted system tag is not returned.
    Rules: `get_system_tags_in_workspace` R2 [BUG-1483]"""
    mk_system_tag(name="Old Seed", tag_code="old_seed", is_active=False)
    s1 = mk_system_tag(name="Supplier", tag_code="supplier")

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert ids(result) == [s1.id]


# [claude] ATG-SYS-06
def test_atg_sys_06__ordered_by_name_case_insensitive_then_id(db, w1, mk_system_tag):
    """ATG-SYS-06 — ordered by name case-insensitive, then id.
    Rules: `get_system_tags_in_workspace` R3 [BUG-1482]"""
    s1 = mk_system_tag(name="Utility", tag_code="utility")
    s2 = mk_system_tag(name="client", tag_code="client")
    s3 = mk_system_tag(name="Bank", tag_code="bank")
    seqscan(db)
    bump_t(db, s3)

    result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [s1.id, s2.id, s3.id]
    # Then 2
    assert names(result) == ["Bank", "client", "Utility"]


# [claude] ATG-SYS-07
def test_atg_sys_07__the_query_orders_by_name_case_insensitive_then_id(db, w1, mk_system_tag):
    """ATG-SYS-07 — the query orders by name case-insensitive, then id.
    Rules: `get_system_tags_in_workspace` R3 [BUG-1482]"""
    s1 = mk_system_tag(name="Supplier", tag_code="supplier")

    with StatementRecorder(db) as recorder:
        result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(account_tags.name)" in order_part
    # Then 4
    assert "account_tags.id" in order_part
    # Then 5
    assert "DESC" not in order_part.upper()


# [claude] ATG-SYS-08
def test_atg_sys_08__the_read_writes_nothing_and_keeps_the_caller_s_pending_changes(db, w1, mk_tag, mk_system_tag):
    """ATG-SYS-08 — the read writes nothing and keeps the caller's pending changes.
    Rules: `get_system_tags_in_workspace` Side effects"""
    s1 = mk_system_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    t2.name = "Client Edited"
    p = AccountTag(workspace_id=w1.id, name="Pending", tag_code="pending", is_system_tag=True, is_active=True, usage_count=0)
    db.add(p)
    before = written_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_system_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert written_count(db) == before


# --------------------------------------------------------------------------- #
# AccountTagDAO.increment_usage_count
# --------------------------------------------------------------------------- #


# [claude] ATG-INC-01
def test_atg_inc_01__the_counter_goes_up_by_one_flushed_and_the_session_s_object_is(db, w1, mk_tag):
    """ATG-INC-01 — the counter goes up by one, flushed, and the session's object is returned.
    Rules: `increment_usage_count` R1, R6, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    t2 = mk_tag(name="Client", tag_code="client", usage_count=2)
    before_t2 = snap(db, t2)
    before = written_count(db)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 3
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert snap(db, t2) == before_t2
    # Then 5
    assert written_count(db) == before


# [claude] ATG-INC-02
def test_atg_inc_02__an_unknown_id_returns_none_and_writes_nothing(db, w1, mk_tag):
    """ATG-INC-02 — an unknown id returns None and writes nothing.
    Rules: `increment_usage_count` R2 (P4)"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    before_t1 = snap(db, t1)

    result = dao.increment_usage_count(db, tag_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t1) == before_t1


# [claude] ATG-INC-03
def test_atg_inc_03__another_workspace_s_tag_returns_none_and_its_counter_stays(db, w1, w2, mk_tag):
    """ATG-INC-03 — another workspace's tag returns None and its counter stays.
    Rules: `increment_usage_count` R2 (P4)"""
    z1 = mk_tag(name="Far", tag_code="far", workspace_id=w2.id, usage_count=5)

    result = dao.increment_usage_count(db, tag_id=z1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db, z1) == 5


# [claude] ATG-INC-04
def test_atg_inc_04__a_deleted_system_tag_is_counted_like_any_other(db, w1, mk_system_tag):
    """ATG-INC-04 — a deleted system tag is counted like any other.
    Rules: `increment_usage_count` R3 (P2)"""
    td = mk_system_tag(name="Old", tag_code="old", is_active=False, usage_count=0)

    result = dao.increment_usage_count(db, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is td
    # Then 2
    row = reread(db, td)
    assert row.usage_count == 1
    # Then 3
    assert row.is_active is False
    assert row.is_system_tag is True


# [claude] ATG-INC-05
def test_atg_inc_05__a_negative_stored_counter_goes_up_by_one(db, w1, mk_tag):
    """ATG-INC-05 — a negative stored counter goes up by one.
    Rules: `increment_usage_count` R4"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=-2)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == -1


# [claude] ATG-INC-06
def test_atg_inc_06__the_increase_applies_to_the_stored_value_not_the_loaded_one(db, w1, mk_tag):
    """ATG-INC-06 — the increase applies to the stored value, not the loaded one.
    Rules: `increment_usage_count` R5 [BUG-1484]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": t1.id})

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


# [claude] ATG-INC-07
def test_atg_inc_07__with_the_object_expired_first_the_increase_starts_from_the_stored_value(db, w1, mk_tag):
    """ATG-INC-07 — with the object expired first, the increase starts from the stored value.
    Rules: `increment_usage_count` R5 (control that holds today), R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": t1.id})
    db.expire(t1)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert stored_count(db, t1) == 11


# [claude] ATG-INC-08
def test_atg_inc_08__the_flush_also_saves_another_pending_change_of_the_session(db, w1, mk_tag):
    """ATG-INC-08 — the flush also saves another pending change of the session.
    Rules: `increment_usage_count` R6"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    t1.name = "Suppliers"

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Suppliers"
    # Then 3
    assert row.usage_count == 3


# [claude] ATG-INC-09
def test_atg_inc_09__flushed_not_committed_a_rollback_restores_the_old_value(db, w1, mk_tag):
    """ATG-INC-09 — flushed, not committed: a rollback restores the old value.
    Rules: `increment_usage_count` R6"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

        # Then 1
        assert result is t1
        # Then 2
        assert stored_count(db, t1) == 3
        # Then 3
        sp.rollback()
        row = reread(db, t1)
        assert row.usage_count == 2
        # Then 4
        assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# AccountTagDAO.decrement_usage_count
# --------------------------------------------------------------------------- #


# [claude] ATG-DEC-01
def test_atg_dec_01__the_counter_goes_down_by_one_flushed_and_the_tag_is_returned(db, w1, mk_tag):
    """ATG-DEC-01 — the counter goes down by one, flushed, and the tag is returned.
    Rules: `decrement_usage_count` R1, R7, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    t2 = mk_tag(name="Client", tag_code="client", usage_count=3)
    before_t2 = snap(db, t2)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 2
    # Then 3
    assert stored_count(db, t1) == 2
    # Then 4
    assert snap(db, t2) == before_t2


# [claude] ATG-DEC-02
def test_atg_dec_02__a_counter_of_1_becomes_0(db, w1, mk_tag):
    """ATG-DEC-02 — a counter of 1 becomes 0.
    Rules: `decrement_usage_count` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=1)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.usage_count == 0


# [claude] ATG-DEC-03
def test_atg_dec_03__at_0_nothing_is_written_or_flushed_and_the_tag_is_returned_with_0(db, w1, mk_tag):
    """ATG-DEC-03 — at 0 nothing is written or flushed and the tag is returned with 0.
    Rules: `decrement_usage_count` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t1.name = "Suppliers"

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 0
    # Then 3
    row = reread(db, t1)
    assert row.name == "Supplier"
    # Then 4
    assert row.usage_count == 0


# [claude] ATG-DEC-04
def test_atg_dec_04__a_negative_stored_counter_is_left_as_it_is(db, w1, mk_tag):
    """ATG-DEC-04 — a negative stored counter is left as it is.
    Rules: `decrement_usage_count` R3"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=-2)

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == -2
    # Then 3
    row = reread(db, t1)
    assert row.usage_count == -2


# [claude] ATG-DEC-05
def test_atg_dec_05__an_unknown_id_returns_none_and_writes_nothing(db, w1, mk_tag):
    """ATG-DEC-05 — an unknown id returns None and writes nothing.
    Rules: `decrement_usage_count` R4 (P4)"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    before_t1 = snap(db, t1)

    result = dao.decrement_usage_count(db, tag_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, t1) == before_t1


# [claude] ATG-DEC-06
def test_atg_dec_06__another_workspace_s_tag_returns_none_and_its_counter_stays(db, w1, w2, mk_tag):
    """ATG-DEC-06 — another workspace's tag returns None and its counter stays.
    Rules: `decrement_usage_count` R4 (P4)"""
    z1 = mk_tag(name="Far", tag_code="far", workspace_id=w2.id, usage_count=5)

    result = dao.decrement_usage_count(db, tag_id=z1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db, z1) == 5


# [claude] ATG-DEC-07
def test_atg_dec_07__a_deleted_system_tag_is_decremented_like_any_other(db, w1, mk_system_tag):
    """ATG-DEC-07 — a deleted system tag is decremented like any other.
    Rules: `decrement_usage_count` R5 (P2)"""
    td = mk_system_tag(name="Old", tag_code="old", is_active=False, usage_count=2)

    result = dao.decrement_usage_count(db, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is td
    # Then 2
    row = reread(db, td)
    assert row.usage_count == 1


# [claude] ATG-DEC-08
def test_atg_dec_08__the_decrease_applies_to_the_stored_value_not_the_loaded_one(db, w1, mk_tag):
    """ATG-DEC-08 — the decrease applies to the stored value, not the loaded one.
    Rules: `decrement_usage_count` R6 [BUG-1484]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": t1.id})

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


# [claude] ATG-DEC-09
def test_atg_dec_09__the_not_below_0_check_uses_the_stored_value_stored_0_stays_0(db, w1, mk_tag):
    """ATG-DEC-09 — the "not below 0" check uses the stored value: stored 0 stays 0.
    Rules: `decrement_usage_count` R6 [BUG-1484]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    db.execute(text("UPDATE account_tags SET usage_count = 0 WHERE id = :i"), {"i": t1.id})

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 0
    # Then 3
    assert stored_count(db, t1) == 0


# [claude] ATG-DEC-10
def test_atg_dec_10__when_written_the_flush_also_saves_another_pending_change(db, w1, mk_tag):
    """ATG-DEC-10 — when written, the flush also saves another pending change.
    Rules: `decrement_usage_count` R7"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    t1.name = "Suppliers"

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Suppliers"
    # Then 3
    assert row.usage_count == 2


# [claude] ATG-DEC-11
def test_atg_dec_11__flushed_not_committed_a_rollback_restores_the_old_value(db, w1, mk_tag):
    """ATG-DEC-11 — flushed, not committed: a rollback restores the old value.
    Rules: `decrement_usage_count` R7"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

        # Then 1
        assert result is t1
        # Then 2
        assert stored_count(db, t1) == 2
        # Then 3
        sp.rollback()
        row = reread(db, t1)
        assert row.usage_count == 3
        # Then 4
        assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on AccountTag
# --------------------------------------------------------------------------- #


# [claude] ATG-INH-01
def test_atg_inh_01__create_with_a_dict_stores_a_tag_with_the_model_defaults(db, w1):
    """ATG-INH-01 — create with a dict stores a tag with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Supplier", "tag_code": "supplier"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Supplier"
    assert row.tag_code == "supplier"
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
    assert row.created_at is not None


# [claude] ATG-INH-02
def test_atg_inh_02__create_with_an_accounttagcreate_fails_on_flush_no_workspace_id_and(db):
    """ATG-INH-02 — create with an AccountTagCreate fails on flush (no workspace_id) and saves nothing.
    Rules: inherited R1"""
    before = written_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=AccountTagCreate(name="Supplier", tag_code="supplier"))
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 3
    assert written_count(db) == before


# [claude] ATG-INH-03
def test_atg_inh_03__create_checks_no_uniqueness_a_second_tag_with_the_same_name_and_code(db, w1, mk_tag):
    """ATG-INH-03 — create checks no uniqueness: a second tag with the same name and code is saved.
    Rules: inherited R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Supplier", "tag_code": "supplier"})

    # Then 1
    assert result.id != t1.id
    # Then 2
    assert count_rows(db, AccountTag, AccountTag.workspace_id == w1.id, AccountTag.tag_code == "supplier") == 2


# [claude] ATG-INH-04
def test_atg_inh_04__update_with_an_accounttagupdate_applies_only_the_fields_set_to_a_value(db, mk_tag):
    """ATG-INH-04 — update with an AccountTagUpdate applies only the fields set to a value.
    Rules: inherited R3"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", color="#AA3300")

    result = dao.update(db, db_obj=t1, obj_in=AccountTagUpdate(name="Suppliers", color=None))

    # Then 1
    assert result.id == t1.id
    # Then 2
    row = reread(db, t1)
    assert row.name == "Suppliers"
    # Then 3
    assert row.color == "#AA3300"


# [claude] ATG-INH-05
def test_atg_inh_05__update_with_is_active_false_deletes_the_tag_the_raw_lookup_still_finds(db, w1, mk_tag):
    """ATG-INH-05 — update with {"is_active": False} deletes the tag; the raw lookup still finds it.
    Rules: inherited R3, R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")

    result = dao.update(db, db_obj=t1, obj_in={"is_active": False})

    # Then 1
    assert result.id == t1.id
    # Then 2
    row = reread(db, t1)
    assert row.is_active is False
    # Then 3
    assert dao.get_by_id_and_workspace(db, id=t1.id, workspace_id=w1.id).id == t1.id


# [claude] ATG-INH-06
def test_atg_inh_06__remove_of_a_tag_with_an_assignment_raises_23502_and_deletes_nothing(db, w1, mk_tag):
    """ATG-INH-06 — remove of a tag with an assignment raises 23502 and deletes nothing.
    Rules: inherited R6"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = _add(db, Account(workspace_id=w1.id, name="Acme"))
    _add(db, AccountTagAssignment(workspace_id=w1.id, account_id=a1.id, tag_id=t1.id))
    t1_id = t1.id

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.remove(db, id=t1_id)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert count_rows(db, AccountTag, AccountTag.id == t1_id) == 1
    # Then 3
    assert count_rows(db, AccountTagAssignment, AccountTagAssignment.tag_id == t1_id) == 1


# [claude] ATG-INH-07
def test_atg_inh_07__remove_of_a_tag_with_no_assignment_deletes_it_and_returns_it(db, mk_tag):
    """ATG-INH-07 — remove of a tag with no assignment deletes it and returns it.
    Rules: inherited R6"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    t1_id = t1.id

    result = dao.remove(db, id=t1_id)

    # Then 1
    assert result.id == t1_id
    # Then 2
    assert count_rows(db, AccountTag, AccountTag.id == t1_id) == 0
    # Then 3
    assert count_rows(db, AccountTag, AccountTag.id == t2.id) == 1


# [claude] ATG-INH-08
def test_atg_inh_08__a_sql_delete_of_a_tag_cascades_to_its_assignments(db, w1, mk_tag):
    """ATG-INH-08 — a SQL DELETE of a tag cascades to its assignments.
    Rules: inherited R6 (database side)"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = _add(db, Account(workspace_id=w1.id, name="Acme"))
    _add(db, AccountTagAssignment(workspace_id=w1.id, account_id=a1.id, tag_id=t1.id))
    t1_id = t1.id

    db.execute(text("DELETE FROM account_tags WHERE id = :i"), {"i": t1_id})

    # Then 1
    assert count_rows(db, AccountTag, AccountTag.id == t1_id) == 0
    # Then 2
    assert count_rows(db, AccountTagAssignment, AccountTagAssignment.tag_id == t1_id) == 0
    # Then 3
    assert count_rows(db, Account, Account.id == a1.id) == 1
