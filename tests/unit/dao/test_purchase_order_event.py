"""Unit tests for app/dao/purchase_order_event.py.

Implements tests/unit/dao/purchase_order_event.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (Conventions prescribe naive datetimes)
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.purchase_order_event import purchase_order_event_dao
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.status import Status
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton purchase_order_event_dao" (a module-level name, not a fixture)
dao = purchase_order_event_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T1, T2, T3"
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 5, 10, 0, 0)
T3 = datetime(2026, 3, 6, 10, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1 = a profiles row"
@pytest.fixture
def u1(db):
    return make_profile(db)


# Convention "ST1"
@pytest.fixture
def st1(db, w1):
    return _add(db, Status(workspace_id=w1.id, name="Open", comment="Open order"))


# Convention "ST9"
@pytest.fixture
def st9(db, w2):
    return _add(db, Status(workspace_id=w2.id, name="Open", comment="Open order"))


# Convention "O1"
@pytest.fixture
def o1(db, w1, st1, u1):
    return _add(db, PurchaseOrder(workspace_id=w1.id, po_number="PO-1", destination_type="storage", destination_id=1,
                                 current_status_id=st1.id, created_by=u1.id))


# Convention "O2"
@pytest.fixture
def o2(db, w1, st1, u1):
    return _add(db, PurchaseOrder(workspace_id=w1.id, po_number="PO-2", destination_type="storage", destination_id=1,
                                 current_status_id=st1.id, created_by=u1.id))


# Convention "O9"
@pytest.fixture
def o9(db, w2, st9, u1):
    return _add(db, PurchaseOrder(workspace_id=w2.id, po_number="PO-9", destination_type="storage", destination_id=1,
                                 current_status_id=st9.id, created_by=u1.id))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, st1, st9, o1, o2, o9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "event": W1, O1, created, "Logged"; metadata_json and performed_by not passed
@pytest.fixture
def mk_event(db, w1, o1):
    """mk_event(created_at=..., **columns) -> PurchaseOrderEvent. Keywords only."""
    def _mk(*, created_at, **columns):
        fields = {"workspace_id": w1.id, "purchase_order_id": o1.id, "event_type": "created",
                  "description": "Logged", "created_at": created_at}
        fields.update(columns)
        return _add(db, PurchaseOrderEvent(**fields))
    return _mk


# The "158 events E1 ... E158, built with add_all" Given
@pytest.fixture
def mk_log(db, w1, o1):
    """mk_log(count) -> `newest_first`: the ids of Ecount ... E1, Ek at T1 + k minutes."""
    def _mk(count):
        rows = [PurchaseOrderEvent(workspace_id=w1.id, purchase_order_id=o1.id, event_type="created",
                                   description="Logged", created_at=T1 + timedelta(minutes=k))
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of purchase_order_events rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(PurchaseOrderEvent.__table__)).scalar_one()


# Convention "stored_json(X)": the stored text; None for SQL NULL, "null" for JSON null
def stored_json(db, row):
    return db.scalar(text("SELECT metadata::text FROM purchase_order_events WHERE id = :i"), {"i": row.id})


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
        """The one SELECT from purchase_order_events; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "purchase_order_events" in s]
        return statement


# --------------------------------------------------------------------------- #
# PurchaseOrderEventDAO.get_by_order
# --------------------------------------------------------------------------- #


# [claude] POE-G-01
def test_poe_g_01__returns_a_list_of_the_purchase_order_s_rows_of_every_event_type(db, w1, o1, mk_event):
    """POE-G-01 — returns a list of the purchase order's rows of every event type.
    Rules: `get_by_order` R1, Returns"""
    a = mk_event(created_at=T1, event_type="created")
    b = mk_event(created_at=T2, event_type="all_received")
    c = mk_event(created_at=T3, event_type="attachment_added")

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]
    # Then 3
    assert isinstance(result[0], PurchaseOrderEvent)


# [claude] POE-G-02
def test_poe_g_02__a_newer_row_of_another_purchase_order_is_not_returned(db, w1, o1, o2, mk_event):
    """POE-G-02 — a newer row of another purchase order is not returned.
    Rules: `get_by_order` R1"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, purchase_order_id=o2.id)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] POE-G-03
def test_poe_g_03__the_right_purchase_order_under_another_workspace_returns_an_empty_list(db, w2, o1, mk_event):
    """POE-G-03 — the right purchase order under another workspace returns an empty list.
    Rules: `get_by_order` R2"""
    mk_event(created_at=T1)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] POE-G-04
def test_poe_g_04__a_newer_w2_row_on_the_same_purchase_order_is_not_returned(db, w1, w2, o1, mk_event):
    """POE-G-04 — a newer W2 row on the same purchase order is not returned.
    Rules: `get_by_order` R2"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, workspace_id=w2.id)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] POE-G-05
def test_poe_g_05__a_w2_row_on_a_purchase_order_of_w1_is_returned_for_w2_only_the_row_s_wo(db, w2, o1, mk_event):
    """POE-G-05 — a W2 row on a purchase order of W1 is returned for W2: only the row's workspace is compared.
    Rules: `get_by_order` R2"""
    z = mk_event(created_at=T1, workspace_id=w2.id)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] POE-G-06
def test_poe_g_06__a_w2_row_on_a_purchase_order_of_w1_is_not_returned_for_w1(db, w1, w2, o1, mk_event):
    """POE-G-06 — a W2 row on a purchase order of W1 is not returned for W1.
    Rules: `get_by_order` R2"""
    mk_event(created_at=T1, workspace_id=w2.id)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] POE-G-07
def test_poe_g_07__an_unknown_purchase_order_id_returns_an_empty_list(db, w1, mk_event):
    """POE-G-07 — an unknown purchase order id returns an empty list.
    Rules: `get_by_order` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_order(db, purchase_order_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] POE-G-08
def test_poe_g_08__purchase_order_id_0_returns_an_empty_list(db, w1, mk_event):
    """POE-G-08 — purchase_order_id=0 returns an empty list.
    Rules: `get_by_order` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_order(db, purchase_order_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] POE-G-09
def test_poe_g_09__an_unknown_workspace_returns_an_empty_list(db, o1, mk_event):
    """POE-G-09 — an unknown workspace returns an empty list.
    Rules: `get_by_order` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] POE-G-10
def test_poe_g_10__a_purchase_order_with_no_events_returns_an_empty_list(db, w1, o2, mk_event):
    """POE-G-10 — a purchase order with no events returns an empty list.
    Rules: `get_by_order` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_order(db, purchase_order_id=o2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] POE-G-11
def test_poe_g_11__after_a_hard_delete_of_the_purchase_order_its_rows_are_gone_and_the_cal(db, w1, o1, o2, mk_event):
    """POE-G-11 — after a hard delete of the purchase order its rows are gone and the call returns an empty list.
    Rules: `get_by_order` R4"""
    mk_event(created_at=T1)
    mk_event(created_at=T2)
    mk_event(created_at=T3, purchase_order_id=o2.id)
    db.execute(text("DELETE FROM purchase_orders WHERE id = :i"), {"i": o1.id})

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert db.scalar(text("SELECT count(*) FROM purchase_order_events WHERE purchase_order_id = :i"), {"i": o1.id}) == 0
    # Then 3
    assert db.scalar(text("SELECT count(*) FROM purchase_order_events WHERE purchase_order_id = :i"), {"i": o2.id}) == 1


# [claude] POE-G-12
def test_poe_g_12__rows_are_ordered_by_created_at_descending_then_id_descending(db, w1, o1, mk_event):
    """POE-G-12 — rows are ordered by created_at descending, then id descending.
    Rules: `get_by_order` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    c = mk_event(created_at=T1)
    d = mk_event(created_at=T3)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] POE-G-13
def test_poe_g_13__on_a_created_at_tie_with_no_update_the_higher_id_comes_first(db, w1, o1, mk_event):
    """POE-G-13 — on a created_at tie with no update the higher id comes first.
    Rules: `get_by_order` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] POE-G-14
def test_poe_g_14__on_a_created_at_tie_the_higher_id_still_comes_first_after_the_lower_row(db, w1, o1, mk_event):
    """POE-G-14 — on a created_at tie the higher id still comes first after the lower row is updated.
    Rules: `get_by_order` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] POE-G-15
def test_poe_g_15__every_matching_row_is_returned_158_rows_give_158(db, w1, o1, mk_log):
    """POE-G-15 — every matching row is returned: 158 rows give 158.
    Rules: `get_by_order` R6"""
    newest_first = mk_log(158)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 158
    # Then 2
    assert ids(result) == newest_first


# [claude] POE-G-16
def test_poe_g_16__a_row_comes_back_as_stored_with_its_performer(db, w1, u1, o1, mk_event):
    """POE-G-16 — a row comes back as stored, with its performer.
    Rules: `get_by_order` R7"""
    a = mk_event(created_at=T2, event_type="all_received", description="Step done", metadata_json={"status": "DONE", "note": "Shift 1"}, performed_by=u1.id)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].workspace_id == w1.id
    assert result[0].purchase_order_id == o1.id
    assert result[0].event_type == "all_received"
    # Then 3
    assert result[0].description == "Step done"
    assert result[0].created_at == T2
    # Then 4
    assert result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}
    # Then 5
    assert result[0].performer.id == u1.id


# [claude] POE-G-17
def test_poe_g_17__sql_null_and_json_null_metadata_both_read_back_as_none_and_no_performer(db, w1, o1, mk_event):
    """POE-G-17 — SQL NULL and JSON null metadata both read back as None, and no performer gives None.
    Rules: `get_by_order` R7"""
    a = mk_event(created_at=T1)
    b = mk_event(created_at=T2, metadata_json=None)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]
    # Then 2
    assert result[0].metadata_json is None
    # Then 3
    assert result[1].metadata_json is None
    # Then 4
    db.expire_all()
    assert stored_json(db, a) is None
    # Then 5
    db.expire_all()
    assert stored_json(db, b) == "null"
    # Then 6
    assert result[0].performer is None


# [claude] POE-G-18
def test_poe_g_18__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_returned(db, w1, o1, mk_event):
    """POE-G-18 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_by_order` R7, Side effects, Overview, R1, Branch map"""
    a = mk_event(created_at=T1)
    p = PurchaseOrderEvent(workspace_id=w1.id, purchase_order_id=o1.id, event_type="created", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)
    written = recorder.written()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    assert len(db.new) == 1
    # Then 6
    assert not db.dirty and not db.deleted
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 8
    assert written == []
    # Then 9
    assert "FOR" not in sql.upper().split()
    # Then 10
    assert "purchase_orders" not in sql


# [claude] POE-G-19
def test_poe_g_19__on_a_created_at_tie_id_decides_not_event_type_description_or_performer(db, w1, u1, o1, mk_event):
    """POE-G-19 — on a created_at tie id decides, not event_type, description or performer.
    Rules: `get_by_order` R5"""
    u2 = make_profile(db)
    u3 = make_profile(db)
    a = mk_event(created_at=T2, event_type="b", description="b", performed_by=u2.id)
    b = mk_event(created_at=T2, event_type="a", description="a", performed_by=u1.id)
    c = mk_event(created_at=T2, event_type="c", description="c", performed_by=u3.id)
    db.expire_all()

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] POE-G-20
def test_poe_g_20__one_microsecond_inside_one_day_decides_the_order_against_id(db, w1, o1, mk_event):
    """POE-G-20 — one microsecond inside one day decides the order, against id.
    Rules: `get_by_order` R5"""
    a = mk_event(created_at=T2 + timedelta(microseconds=1))
    b = mk_event(created_at=T2)

    result = dao.get_by_order(db, purchase_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] POE-G-21
def test_poe_g_21__writes_nothing_with_an_empty_result_the_pending_row_is_still_alone_in_t(db, w1, o1, o2, mk_event):
    """POE-G-21 — writes nothing: with an empty result the pending row is still alone in the session.
    Rules: `get_by_order` R7, Side effects"""
    mk_event(created_at=T1)
    p = PurchaseOrderEvent(workspace_id=w1.id, purchase_order_id=o1.id, event_type="created", description="Pending", created_at=T2)
    db.add(p)

    result = dao.get_by_order(db, purchase_order_id=o2.id, workspace_id=w1.id)

    # Then 1
    assert result == []
    # Then 2
    assert len(db.new) == 1
