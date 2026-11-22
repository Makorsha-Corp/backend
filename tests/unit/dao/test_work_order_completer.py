"""Unit tests for app/dao/work_order_completer.py.

Implements tests/unit/dao/work_order_completer.cases.md, one test per case, in
card order (the assignee cards with the spec's substitutions; no GU cards, the
single-order read is dead code here). Real Postgres session (`db` fixture). Nothing is mocked and no
clock is patched (Conventions, Externals: None); the `db.commit` spy of the
"rolled back" convention wraps the real method.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from unittest import mock

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.work_order_completer import work_order_completer_dao
from app.models.factory import Factory
from app.models.work_order import WorkOrder
from app.models.work_order_completer import WorkOrderCompleter as Row
from app.models.work_order_type import WorkOrderType
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton work_order_completer_dao" (a module-level name, not a fixture)
dao = work_order_completer_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

TABLE = "work_order_completers"


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# The Conventions list these rows in this order; each fixture depends on the one
# before, so the rows are flushed one at a time and ids rise in that order.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


@pytest.fixture
def u4(db, u3):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u4):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def f9(db, w2, f1):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


@pytest.fixture
def wt1(db, w1, f9):
    return _add(db, WorkOrderType(workspace_id=w1.id, name="Repair"))


@pytest.fixture
def wt9(db, w2, wt1):
    return _add(db, WorkOrderType(workspace_id=w2.id, name="Repair"))


def _work_order(workspace, factory, wo_type, **columns):
    fields = {"workspace_id": workspace.id, "work_order_number": "WO-1", "title": "Fix press",
              "factory_id": factory.id, "work_order_type_id": wo_type.id}
    fields.update(columns)
    return WorkOrder(**fields)


@pytest.fixture
def wo1(db, w1, f1, wt1, wt9):
    return _add(db, _work_order(w1, f1, wt1))


@pytest.fixture
def wo2(db, w1, f1, wt1, wo1):
    return _add(db, _work_order(w1, f1, wt1, work_order_number="WO-2"))


@pytest.fixture
def wod(db, w1, f1, wt1, wo2):
    return _add(db, _work_order(w1, f1, wt1, work_order_number="WO-3", is_deleted=True))


@pytest.fixture
def wo9(db, w2, f9, wt9, wod):
    return _add(db, _work_order(w2, f9, wt9, work_order_number="WO-9"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3, u4, f1, f9, wt1, wt9, wo1, wo2, wod, wo9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "row"
@pytest.fixture
def mk_row(db, w1, wo1):
    """mk_row(user_id=..., **columns) -> Row. Keywords only."""
    def _mk(*, user_id, **columns):
        fields = {"workspace_id": w1.id, "work_order_id": wo1.id, "user_id": user_id}
        fields.update(columns)
        return _add(db, Row(**fields))
    return _mk


# Convention "bumpC(X)"
def bump(db, row):
    db.execute(text(f"UPDATE {TABLE} SET user_id = user_id WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "users_of(wo, ws)"
def users_of(db, wo, ws):
    return list(db.scalars(text(f"SELECT user_id FROM {TABLE} WHERE work_order_id = :w AND workspace_id = :s ORDER BY id"),
                           {"w": wo, "s": ws}))


# `X.id` of a row the call deleted: read from the identity key, which outlives the row
# (a plain `X.id` after `expire_all()` would try to reload a row that is gone).
def id_of(row):
    return sa_inspect(row).identity[0]


# Convention "row_ids_of(wo)"
def row_ids_of(db, wo):
    return set(db.scalars(text(f"SELECT id FROM {TABLE} WHERE work_order_id = :w"), {"w": wo}))


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(Row.__table__))


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

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from the module's table; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if f"FROM {TABLE}" in s]
        return statement


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
@pytest.fixture
def commit_spy(db, monkeypatch):
    spy = mock.MagicMock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", spy)
    return spy


# --------------------------------------------------------------------------- #
# WorkOrderCompleterDAO.get_user_ids_by_orders
# --------------------------------------------------------------------------- #


# [claude] WOC-GO-01
def test_woc_go_01__a_map_from_each_order_to_its_people_in_row_order(db, w1, u1, u2, u3, wo1, wo2, mk_row):
    """WOC-GO-01 — a map from each order to its people, in row order.
    Rules: `get_user_ids_by_orders` R2, R3, Returns"""
    mk_row(user_id=u2.id)
    mk_row(user_id=u1.id)
    mk_row(user_id=u3.id, work_order_id=wo2.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id, wo2.id], workspace_id=w1.id)

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert result == {wo1.id: [u2.id, u1.id], wo2.id: [u3.id]}


# [claude] WOC-GO-02
def test_woc_go_02__an_empty_list_returns_empty_dict_with_no_query(db, w1, u1, mk_row):
    """WOC-GO-02 — an empty list returns {} with no query.
    Rules: `get_user_ids_by_orders` R1"""
    mk_row(user_id=u1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_user_ids_by_orders(db, work_order_ids=[], workspace_id=w1.id)

    # Then 1
    assert result == {}
    # Then 2
    assert recorder.selects() == []


# [claude] WOC-GO-03
def test_woc_go_03__an_order_with_no_rows_and_an_unknown_id_map_to_empty(db, w1, u1, wo2, mk_row):
    """WOC-GO-03 — an order with no rows and an unknown id map to [].
    Rules: `get_user_ids_by_orders` R2"""
    mk_row(user_id=u1.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo2.id, MISSING], workspace_id=w1.id)

    # Then 1
    assert result == {wo2.id: [], MISSING: []}


# [claude] WOC-GO-04
def test_woc_go_04__an_id_given_twice_is_one_key_keys_in_first_given_order(db, w1, u1, wo1, wo2, mk_row):
    """WOC-GO-04 — an id given twice is one key; keys come in the order first given.
    Rules: `get_user_ids_by_orders` R2"""
    mk_row(user_id=u1.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo2.id, wo1.id, wo2.id], workspace_id=w1.id)

    # Then 1
    assert list(result.keys()) == [wo2.id, wo1.id]
    # Then 2
    assert result[wo1.id] == [u1.id]
    # Then 3
    assert result[wo2.id] == []


# [claude] WOC-GO-05
def test_woc_go_05__row_id_order_holds_when_the_first_row_was_updated(db, w1, u1, u2, u3, wo1, mk_row):
    """WOC-GO-05 — row-id order holds when the first row was updated.
    Rules: `get_user_ids_by_orders` R3"""
    a = mk_row(user_id=u2.id)
    mk_row(user_id=u1.id)
    mk_row(user_id=u3.id)
    seqscan(db)
    bump(db, a)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id], workspace_id=w1.id)

    # Then 1
    assert result == {wo1.id: [u2.id, u1.id, u3.id]}


# [claude] WOC-GO-06
def test_woc_go_06__asked_for_w2_an_order_of_w1_maps_to_empty(db, w2, u1, wo1, mk_row):
    """WOC-GO-06 — asked for W2, an order of W1 maps to [].
    Rules: `get_user_ids_by_orders` R4"""
    mk_row(user_id=u1.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id], workspace_id=w2.id)

    # Then 1
    assert result == {wo1.id: []}


# [claude] WOC-GO-07
def test_woc_go_07__a_w2_row_on_a_w1_order_is_not_read_for_w1(db, w1, w2, u1, u3, wo1, mk_row):
    """WOC-GO-07 — a W2 row on a W1 order is not read for W1.
    Rules: `get_user_ids_by_orders` R4"""
    mk_row(user_id=u1.id)
    mk_row(user_id=u3.id, workspace_id=w2.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id], workspace_id=w1.id)

    # Then 1
    assert result == {wo1.id: [u1.id]}


# [claude] WOC-GO-08
def test_woc_go_08__a_w2_row_on_a_w1_order_is_read_for_w2(db, w2, u1, u3, wo1, mk_row):
    """WOC-GO-08 — a W2 row on a W1 order is read for W2.
    Rules: `get_user_ids_by_orders` R4"""
    mk_row(user_id=u1.id)
    mk_row(user_id=u3.id, workspace_id=w2.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id], workspace_id=w2.id)

    # Then 1
    assert result == {wo1.id: [u3.id]}


# [claude] WOC-GO-09
def test_woc_go_09__the_people_of_a_soft_deleted_order_are_returned(db, w1, u1, wod, mk_row):
    """WOC-GO-09 — the people of a soft-deleted order are returned.
    Rules: `get_user_ids_by_orders` R5"""
    mk_row(user_id=u1.id, work_order_id=wod.id)

    result = dao.get_user_ids_by_orders(db, work_order_ids=[wod.id], workspace_id=w1.id)

    # Then 1
    assert result == {wod.id: [u1.id]}


# [claude] WOC-GO-10
def test_woc_go_10__one_statement_whatever_the_number_of_ids(db, w1, u1, u2, wo1, wo2, wod, mk_row):
    """WOC-GO-10 — one statement, whatever the number of ids.
    Rules: `get_user_ids_by_orders` R6"""
    mk_row(user_id=u1.id)
    mk_row(user_id=u2.id, work_order_id=wo2.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id, wo2.id, wod.id], workspace_id=w1.id)

    # Then 1
    assert result == {wo1.id: [u1.id], wo2.id: [u2.id], wod.id: []}
    # Then 2
    assert len(recorder.selects()) == 1
    # Then 3
    assert "ORDER BY" in recorder.sql()


# [claude] WOC-GO-11
def test_woc_go_11__writes_nothing_a_pending_row_stays_pending(db, w1, u1, u2, u3, u4, wo1, wo2, mk_row):
    """WOC-GO-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_user_ids_by_orders` Side effects"""
    mk_row(user_id=u1.id)
    b = mk_row(user_id=u2.id, work_order_id=wo2.id)
    b.user_id = u3.id
    p = Row(workspace_id=w1.id, work_order_id=wo1.id, user_id=u4.id)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_user_ids_by_orders(db, work_order_ids=[wo1.id], workspace_id=w1.id)

    # Then 1
    assert result == {wo1.id: [u1.id]}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert stored_count(db) == before


# --------------------------------------------------------------------------- #
# WorkOrderCompleterDAO.replace_for_order
# --------------------------------------------------------------------------- #


# [claude] WOC-RP-01
def test_woc_rp_01__the_people_become_the_distinct_ids_given_in_first_seen_order(db, w1, u1, u2, u3, wo1, mk_row):
    """WOC-RP-01 — the people become the distinct ids given, in first-seen order, on new rows.
    Rules: `replace_for_order` R1, Returns, Side effects"""
    a = mk_row(user_id=u1.id)
    b = mk_row(user_id=u2.id)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u3.id, u1.id, u3.id, u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u3.id, u1.id, u2.id]
    # Then 3
    db.expire_all()
    assert row_ids_of(db, wo1.id).isdisjoint({id_of(a), id_of(b)})


# [claude] WOC-RP-02
def test_woc_rp_02__saving_the_same_list_again_keeps_the_people_on_new_rows(db, w1, u1, u2, wo1, mk_row):
    """WOC-RP-02 — saving the same list again keeps the people and their order, on new rows.
    Rules: `replace_for_order` R2"""
    a = mk_row(user_id=u1.id)
    b = mk_row(user_id=u2.id)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u1.id, u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u1.id, u2.id]
    # Then 3
    db.expire_all()
    assert row_ids_of(db, wo1.id).isdisjoint({id_of(a), id_of(b)})


# [claude] WOC-RP-03
def test_woc_rp_03__a_shorter_list_removes_the_others(db, w1, u1, u2, wo1, mk_row):
    """WOC-RP-03 — a shorter list removes the others.
    Rules: `replace_for_order` R2"""
    mk_row(user_id=u1.id)
    mk_row(user_id=u2.id)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u2.id]


# [claude] WOC-RP-04
def test_woc_rp_04__empty_list_removes_everyone(db, w1, u1, u2, wo1, mk_row):
    """WOC-RP-04 — [] removes everyone.
    Rules: `replace_for_order` R2"""
    mk_row(user_id=u1.id)
    mk_row(user_id=u2.id)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[])

    # Then 1
    assert result is None
    # Then 2
    assert row_ids_of(db, wo1.id) == set()


# [claude] WOC-RP-05
def test_woc_rp_05__another_order_s_rows_are_untouched(db, w1, u1, u2, u3, wo1, wo2, mk_row):
    """WOC-RP-05 — another order's rows are untouched.
    Rules: `replace_for_order` R3"""
    c = mk_row(user_id=u3.id, work_order_id=wo2.id)
    mk_row(user_id=u1.id)
    before_c = snap(db, c)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, c) == before_c
    # Then 3
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u2.id]


# [claude] WOC-RP-06
def test_woc_rp_06__a_call_under_w2_deletes_nothing_of_w1_and_writes_under_w2(db, w2, u1, u2, wo1, mk_row):
    """WOC-RP-06 — a call under W2 deletes nothing of W1 and writes its rows under W2.
    Rules: `replace_for_order` R3"""
    a = mk_row(user_id=u1.id)
    before_a = snap(db, a)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w2.id, user_ids=[u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 3
    db.expire_all()
    assert users_of(db, wo1.id, w2.id) == [u2.id]


# [claude] WOC-RP-07
def test_woc_rp_07__a_w2_row_on_the_order_is_not_deleted(db, w1, w2, u1, u2, u3, wo1, mk_row):
    """WOC-RP-07 — a W2 row on the order is not deleted.
    Rules: `replace_for_order` R4"""
    z = mk_row(user_id=u3.id, workspace_id=w2.id)
    mk_row(user_id=u2.id)
    before_z = snap(db, z)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u1.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert snap(db, z) == before_z
    # Then 3
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u1.id]


# [claude] WOC-RP-08
def test_woc_rp_08__inserting_the_user_of_a_kept_w2_row_raises_23505(db, w1, w2, u1, u2, wo1, mk_row):
    """WOC-RP-08 — inserting the user of a kept W2 row raises 23505; the delete is undone too.
    Rules: `replace_for_order` R4, Errors"""
    z = mk_row(user_id=u1.id, workspace_id=w2.id)
    mk_row(user_id=u2.id)
    before_z = snap(db, z)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u1.id])

    # Then 1
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert "uq_wo_completer_wo_user" in str(exc.value.orig)
    # Then 3
    db.expire_all()
    assert snap(db, z) == before_z
    # Then 4
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u2.id]


# [claude] WOC-RP-09
def test_woc_rp_09__an_unknown_user_raises_23503_the_delete_is_undone_too(db, w1, u1, u2, wo1, mk_row):
    """WOC-RP-09 — an unknown user raises 23503; the delete is undone too.
    Rules: `replace_for_order` R5, Errors"""
    a = mk_row(user_id=u1.id)
    before_a = snap(db, a)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u2.id, MISSING])

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u1.id]
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOC-RP-10
def test_woc_rp_10__an_unknown_order_with_people_raises_23503(db, w1, u1, mk_row):
    """WOC-RP-10 — an unknown order with people raises 23503.
    Rules: `replace_for_order` R5, Errors"""
    mk_row(user_id=u1.id)
    before = stored_count(db)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.replace_for_order(db, work_order_id=MISSING, workspace_id=w1.id, user_ids=[u1.id])

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] WOC-RP-11
def test_woc_rp_11__an_unknown_order_with_empty_list_raises_nothing(db, w1, u1, mk_row):
    """WOC-RP-11 — an unknown order with [] raises nothing.
    Rules: `replace_for_order` R5"""
    mk_row(user_id=u1.id)
    before = stored_count(db)

    result = dao.replace_for_order(db, work_order_id=MISSING, workspace_id=w1.id, user_ids=[])

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] WOC-RP-12
def test_woc_rp_12__any_existing_profile_is_accepted(db, w1, u4, wo1):
    """WOC-RP-12 — any existing profile is accepted.
    Rules: `replace_for_order` R6"""
    # U4 belongs to no workspace: it is a standing row.

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u4.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u4.id]


# [claude] WOC-RP-13
def test_woc_rp_13__a_collection_loaded_before_the_call_stays_stale(db, w1, u1, u2, wo1, mk_row):
    """WOC-RP-13 — a collection loaded before the call stays stale; a fresh query sees the new rows.
    Rules: `replace_for_order` R7"""
    mk_row(user_id=u1.id)
    loaded = list(wo1.completer_links)  # noqa: F841  (the card's Given line, kept as written: it loads the collection)

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u2.id])  # noqa: F841  (the card's When line; no Then reads `result`)

    # Then 1
    assert [l.user_id for l in wo1.completer_links] == [u1.id]
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u2.id]


# [claude] WOC-RP-14
def test_woc_rp_14__flushed_not_committed_a_rollback_restores_the_old_rows(db, w1, u1, u2, wo1, mk_row, commit_spy):
    """WOC-RP-14 — flushed, not committed: a rollback restores the old rows.
    Rules: `replace_for_order` R8, Side effects"""
    mk_row(user_id=u1.id)
    sp = db.begin_nested()

    result = dao.replace_for_order(db, work_order_id=wo1.id, workspace_id=w1.id, user_ids=[u2.id])

    # Then 1
    assert result is None
    # Then 2
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u2.id]
    # Then 3
    sp.rollback()
    db.expire_all()
    assert users_of(db, wo1.id, w1.id) == [u1.id]
    # Then 4
    commit_spy.assert_not_called()
