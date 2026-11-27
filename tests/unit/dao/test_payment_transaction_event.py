"""Unit tests for app/dao/payment_transaction_event.py.

Implements tests/unit/dao/payment_transaction_event.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (Conventions prescribe naive datetimes)
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.dao.payment_transaction_event import payment_transaction_event_dao
from app.models.payment_transaction import PaymentTransaction
from app.models.payment_transaction_event import PaymentTransactionEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton payment_transaction_event_dao" (a module-level name, not a fixture)
dao = payment_transaction_event_dao

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


# Convention "TX1"
@pytest.fixture
def tx1(db, w1):
    return _add(db, PaymentTransaction(workspace_id=w1.id, tran_id="TXN-1", amount=Decimal("100.00"), currency="BDT"))


# Convention "TX2"
@pytest.fixture
def tx2(db, w1):
    return _add(db, PaymentTransaction(workspace_id=w1.id, tran_id="TXN-2", amount=Decimal("100.00"), currency="BDT"))


# Convention "TX9"
@pytest.fixture
def tx9(db, w2):
    return _add(db, PaymentTransaction(workspace_id=w2.id, tran_id="TXN-9", amount=Decimal("100.00"), currency="BDT"))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, tx1, tx2, tx9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "event": W1, TX1, initiated, "Logged"; metadata_json and performed_by not passed
@pytest.fixture
def mk_event(db, w1, tx1):
    """mk_event(created_at=..., **columns) -> PaymentTransactionEvent. Keywords only."""
    def _mk(*, created_at, **columns):
        fields = {"workspace_id": w1.id, "payment_transaction_id": tx1.id, "event_type": "initiated",
                  "description": "Logged", "created_at": created_at}
        fields.update(columns)
        return _add(db, PaymentTransactionEvent(**fields))
    return _mk


# The "158 events E1 ... E158, built with add_all" Given
@pytest.fixture
def mk_log(db, w1, tx1):
    """mk_log(count) -> `oldest_first`: the ids of E1 ... Ecount, Ek at T1 + k minutes."""
    def _mk(count):
        rows = [PaymentTransactionEvent(workspace_id=w1.id, payment_transaction_id=tx1.id, event_type="initiated",
                                        description="Logged", created_at=T1 + timedelta(minutes=k))
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
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


# Convention "nothing written": the number of payment_transaction_events rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(PaymentTransactionEvent.__table__)).scalar_one()


# Convention "stored_json(X)": the stored text; None for SQL NULL, "null" for JSON null
def stored_json(db, row):
    return db.scalar(text("SELECT metadata_json::text FROM payment_transaction_events WHERE id = :i"), {"i": row.id})


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
        """The one SELECT from payment_transaction_events; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "payment_transaction_events" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# PaymentTransactionEventDAO.get_by_payment_transaction
# --------------------------------------------------------------------------- #


# [claude] PTE-G-01
def test_pte_g_01__returns_a_list_of_the_payment_transaction_s_rows_of_every_event_type(db, tx1, mk_event):
    """PTE-G-01 — returns a list of the payment transaction's rows of every event type.
    Rules: `get_by_payment_transaction` R1, Returns"""
    a = mk_event(created_at=T1, event_type="initiated")
    b = mk_event(created_at=T2, event_type="ipn_received")
    c = mk_event(created_at=T3, event_type="validated_success")

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]
    # Then 3
    assert isinstance(result[0], PaymentTransactionEvent)


# [claude] PTE-G-02
def test_pte_g_02__a_newer_row_of_another_payment_transaction_is_not_returned(db, tx1, tx2, mk_event):
    """PTE-G-02 — a newer row of another payment transaction is not returned.
    Rules: `get_by_payment_transaction` R1"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, payment_transaction_id=tx2.id)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PTE-G-03
@pytest.mark.xfail(strict=True, reason="BUG-1191: Payment event read has no workspace filter")
def test_pte_g_03__a_row_of_w1_on_a_transaction_of_w2_is_not_returned_for_w2(db, w2, tx9, mk_event):
    """PTE-G-03 — a row of W1 on a transaction of W2 is not returned for W2.
    Rules: `get_by_payment_transaction` R2 [BUG-1191]"""
    mk_event(created_at=T1, payment_transaction_id=tx9.id)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx9.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PTE-G-04
@pytest.mark.xfail(strict=True, reason="BUG-1191: Payment event read has no workspace filter")
def test_pte_g_04__a_call_with_another_workspace_returns_an_empty_list(db, w2, tx1, mk_event):
    """PTE-G-04 — a call with another workspace returns an empty list.
    Rules: `get_by_payment_transaction` R2 [BUG-1191]"""
    mk_event(created_at=T1)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] PTE-G-05
@pytest.mark.xfail(strict=True, reason="BUG-1191: Payment event read has no workspace filter")
def test_pte_g_05__only_the_rows_of_that_workspace_are_returned(db, w1, w2, tx1, mk_event):
    """PTE-G-05 — only the rows of that workspace are returned.
    Rules: `get_by_payment_transaction` R2 [BUG-1191]"""
    a = mk_event(created_at=T1)
    mk_event(created_at=T2, workspace_id=w2.id)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PTE-G-06
@pytest.mark.xfail(strict=True, reason="BUG-1191: Payment event read has no workspace filter")
def test_pte_g_06__workspace_id_is_required(db, tx1, mk_event):
    """PTE-G-06 — workspace_id is required.
    Rules: `get_by_payment_transaction` R2 [BUG-1191]"""
    mk_event(created_at=T1)

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)
    # Then 2
    assert "workspace_id" in str(exc.value)


# [claude] PTE-G-07
def test_pte_g_07__an_unknown_payment_transaction_id_returns_an_empty_list(db, mk_event):
    """PTE-G-07 — an unknown payment transaction id returns an empty list.
    Rules: `get_by_payment_transaction` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=MISSING)

    # Then 1
    assert result == []


# [claude] PTE-G-08
def test_pte_g_08__payment_transaction_id_0_returns_an_empty_list(db, mk_event):
    """PTE-G-08 — payment_transaction_id=0 returns an empty list.
    Rules: `get_by_payment_transaction` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=0)

    # Then 1
    assert result == []


# [claude] PTE-G-09
def test_pte_g_09__a_payment_transaction_with_no_events_returns_an_empty_list(db, tx2, mk_event):
    """PTE-G-09 — a payment transaction with no events returns an empty list.
    Rules: `get_by_payment_transaction` R3"""
    mk_event(created_at=T1)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx2.id)

    # Then 1
    assert result == []


# [claude] PTE-G-10
def test_pte_g_10__nothing_about_the_transaction_hides_its_rows_the_read_does_not_touch_th(db, tx1, mk_event):
    """PTE-G-10 — nothing about the transaction hides its rows: the read does not touch the parent table.
    Rules: `get_by_payment_transaction` R4"""
    a = mk_event(created_at=T1)
    b = mk_event(created_at=T2)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id, b.id]
    # Then 2
    assert len(selects) == 1
    # Then 3
    assert "payment_transactions" not in sql


# [claude] PTE-G-11
def test_pte_g_11__rows_are_ordered_by_created_at_ascending_oldest_first(db, tx1, mk_event):
    """PTE-G-11 — rows are ordered by created_at ascending, oldest first.
    Rules: `get_by_payment_transaction` R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T3)
    c = mk_event(created_at=T1)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [c.id, a.id, b.id]


# [claude] PTE-G-12
def test_pte_g_12__on_a_tie_both_rows_are_returned_after_the_older_row(db, tx1, mk_event):
    """PTE-G-12 — on a tie both rows are returned, after the older row.
    Rules: `get_by_payment_transaction` R6, R5"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)
    c = mk_event(created_at=T1)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:]} == {a.id, b.id}


# [claude] PTE-G-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1190: Payment timeline steps with one timestamp come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_pte_g_13__on_a_created_at_tie_the_lower_id_comes_first_after_the_lower_row_is_upd(db, tx1, mk_event):
    """PTE-G-13 — on a created_at tie the lower id comes first after the lower row is updated.
    Rules: `get_by_payment_transaction` R6 [BUG-1190]"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)
    a.description = "Edited"
    db.flush()
    db.expire_all()

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PTE-G-14
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1190: Payment timeline steps with one timestamp come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_pte_g_14__on_a_created_at_tie_with_no_update_the_lower_id_comes_first(db, tx1, mk_event):
    """PTE-G-14 — on a created_at tie with no update the lower id comes first.
    Rules: `get_by_payment_transaction` R6 [BUG-1190]"""
    a = mk_event(created_at=T2)
    b = mk_event(created_at=T2)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] PTE-G-15
@pytest.mark.xfail(strict=True, reason="BUG-1190: Payment timeline steps with one timestamp come back in no fixed order")
def test_pte_g_15__the_query_asks_the_database_for_an_order_that_includes_id(db, tx1, mk_event):
    """PTE-G-15 — the query asks the database for an order that includes id.
    Rules: `get_by_payment_transaction` R6 [BUG-1190]"""
    a = mk_event(created_at=T1)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part


# [claude] PTE-G-16
def test_pte_g_16__every_matching_row_is_returned_158_rows_give_158(db, tx1, mk_log):
    """PTE-G-16 — every matching row is returned: 158 rows give 158.
    Rules: `get_by_payment_transaction` R7"""
    oldest_first = mk_log(158)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert len(result) == 158
    # Then 2
    assert ids(result) == oldest_first


# [claude] PTE-G-17
def test_pte_g_17__a_row_comes_back_as_stored_with_its_performer(db, w1, u1, tx1, mk_event):
    """PTE-G-17 — a row comes back as stored, with its performer.
    Rules: `get_by_payment_transaction` R8"""
    a = mk_event(created_at=T2, event_type="ipn_received", description="Step done", metadata_json={"status": "DONE", "note": "Shift 1"}, performed_by=u1.id)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].workspace_id == w1.id
    assert result[0].payment_transaction_id == tx1.id
    assert result[0].event_type == "ipn_received"
    # Then 3
    assert result[0].description == "Step done"
    assert result[0].created_at == T2
    # Then 4
    assert result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}
    # Then 5
    assert result[0].performer.id == u1.id


# [claude] PTE-G-18
def test_pte_g_18__sql_null_and_json_null_metadata_both_read_back_as_none_and_no_performer(db, tx1, mk_event):
    """PTE-G-18 — SQL NULL and JSON null metadata both read back as None, and no performer gives None.
    Rules: `get_by_payment_transaction` R8"""
    a = mk_event(created_at=T1)
    b = mk_event(created_at=T2, metadata_json=None)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]
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


# [claude] PTE-G-19
def test_pte_g_19__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_returned(db, w1, tx1, mk_event):
    """PTE-G-19 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_by_payment_transaction` R8, Side effects, Overview"""
    a = mk_event(created_at=T1)
    p = PaymentTransactionEvent(workspace_id=w1.id, payment_transaction_id=tx1.id, event_type="initiated", description="Pending", created_at=T2)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)
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


# [claude] PTE-G-20
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1190: Payment timeline steps with one timestamp come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_pte_g_20__on_a_created_at_tie_id_decides_not_event_type_description_or_performer(db, u1, tx1, mk_event):
    """PTE-G-20 — on a created_at tie id decides, not event_type, description or performer.
    Rules: `get_by_payment_transaction` R6 [BUG-1190]"""
    u2 = make_profile(db)
    u3 = make_profile(db)
    a = mk_event(created_at=T2, event_type="b", description="b", performed_by=u2.id)
    b = mk_event(created_at=T2, event_type="a", description="a", performed_by=u1.id)
    c = mk_event(created_at=T2, event_type="c", description="c", performed_by=u3.id)
    db.expire_all()

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PTE-G-21
def test_pte_g_21__one_microsecond_inside_one_day_decides_the_order_against_id(db, tx1, mk_event):
    """PTE-G-21 — one microsecond inside one day decides the order, against id.
    Rules: `get_by_payment_transaction` R5"""
    a = mk_event(created_at=T2 + timedelta(microseconds=1))
    b = mk_event(created_at=T2)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] PTE-G-22
def test_pte_g_22__writes_nothing_with_an_empty_result_the_pending_row_is_still_alone_in_t(db, w1, tx1, tx2, mk_event):
    """PTE-G-22 — writes nothing: with an empty result the pending row is still alone in the session.
    Rules: `get_by_payment_transaction` R8, Side effects"""
    mk_event(created_at=T1)
    p = PaymentTransactionEvent(workspace_id=w1.id, payment_transaction_id=tx1.id, event_type="initiated", description="Pending", created_at=T2)
    db.add(p)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx2.id)

    # Then 1
    assert result == []
    # Then 2
    assert len(db.new) == 1


# [claude] PTE-G-23
def test_pte_g_23__created_at_decides_not_event_type_description_or_performer(db, u1, tx1, mk_event):
    """PTE-G-23 — created_at decides, not event_type, description or performer.
    Rules: `get_by_payment_transaction` R5"""
    u2 = make_profile(db)
    u3 = make_profile(db)
    a = mk_event(created_at=T1, event_type="b", description="b", performed_by=u2.id)
    b = mk_event(created_at=T2, event_type="a", description="a", performed_by=u1.id)
    c = mk_event(created_at=T3, event_type="c", description="c", performed_by=u3.id)

    result = dao.get_by_payment_transaction(db, payment_transaction_id=tx1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]
