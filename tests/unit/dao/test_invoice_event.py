"""Unit tests for app/dao/invoice_event.py.

Implements tests/unit/dao/invoice_event.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is patched (Conventions,
Externals: None); the **rolled back** card wraps `db.commit` in a spy that still
calls it. `created_at` is the model's Python default (`utcnow`); IEV-CE-02 checks
it against the database's real clock.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.dao.invoice_event import invoice_event_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.invoice_event import InvoiceEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton invoice_event_dao"
dao = invoice_event_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T10, T11, T12" (naive)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)

# Convention "KEYS"
KEYS = {"id", "workspace_id", "invoice_id", "event_type", "description", "metadata_json", "performed_by", "performed_by_name", "created_at"}

BUG_638 = "BUG-638: Events and line items with tied sort keys come back in no fixed order"
NON_STRICT = " (non-strict: today's order of tied rows is the plan's physical order, which can match by accident)"


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test; inserted and flushed in this order)
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


@pytest.fixture
def u1(db, w2):
    return make_profile(db, name="Rahim")


@pytest.fixture
def u2(db, u1):
    return make_profile(db, name="Karim")


@pytest.fixture
def ac1(db, w1, u2):
    return _add(db, Account(workspace_id=w1.id, name="Acme"))


@pytest.fixture
def ac9(db, w2, ac1):
    return _add(db, Account(workspace_id=w2.id, name="Far"))


def _invoice(workspace_id, account_id):
    return AccountInvoice(
        workspace_id=workspace_id, account_id=account_id, invoice_type="payable", invoice_amount=100,
        invoice_date=date(2026, 3, 1),
    )


@pytest.fixture
def inv1(db, w1, ac1, ac9):
    return _add(db, _invoice(w1.id, ac1.id))


@pytest.fixture
def inv2(db, w1, ac1, inv1):
    return _add(db, _invoice(w1.id, ac1.id))


@pytest.fixture
def inv9(db, w2, ac9, inv2):
    return _add(db, _invoice(w2.id, ac9.id))


@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, ac1, ac9, inv1, inv2, inv9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _event(w1, inv1, created_at, **columns):
    return InvoiceEvent(**{
        "workspace_id": w1.id, "invoice_id": inv1.id, "event_type": "created", "description": "Invoice created",
        "performed_by": None, "metadata_json": None, "created_at": created_at, **columns,
    })


# Convention "event": W1, INV1, "created", "Invoice created"; the card gives created_at and the columns after "but"
@pytest.fixture
def mk_event(db, w1, inv1):
    """mk_event(created_at=..., **columns) -> InvoiceEvent, added and flushed."""
    def _mk(*, created_at, **columns):
        return _add(db, _event(w1, inv1, created_at, **columns))
    return _mk


# Convention "bumpE(X)"
def bump_e(db, x):
    db.execute(text("UPDATE invoice_events SET description = description || '!' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# Convention "seqscan": three steps, in this order
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [r["id"] for r in result]


def _id_of(row):
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(InvoiceEvent).where(InvoiceEvent.id == row_id)).scalar_one_or_none()


# Convention "stored_json(X)"
def stored_json(db, x):
    return db.scalar(text("SELECT metadata_json::text FROM invoice_events WHERE id = :i"), {"i": _id_of(x)})


# Convention "is_sql_null(X)"
def is_sql_null(db, x):
    return db.scalar(text("SELECT metadata_json IS NULL FROM invoice_events WHERE id = :i"), {"i": _id_of(x)})


# Convention "UTC_CLOCK": read after the call
def utc_clock(db):
    return db.scalar(text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))


# Convention "nothing written": the number of invoice_events rows (all workspaces)
def written_count(db):
    return db.scalar(select(func.count()).select_from(InvoiceEvent.__table__))


# "count:" lines: rows of invoice_events with the filter stated
def count_rows(db, *where):
    return db.scalar(select(func.count()).select_from(InvoiceEvent.__table__).where(*where))


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

    def sql(self):
        """The one SELECT from `invoice_events`; fails loudly unless there is exactly one."""
        [statement] = [
            s for s in self.statements if s.lstrip().upper().startswith("SELECT") and "FROM invoice_events" in s
        ]
        return statement


# Convention "order_part": the text of `sql` after its ORDER BY
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# InvoiceEventDAO.create_event
# --------------------------------------------------------------------------- #


# [claude] IEV-CE-01
def test_iev_ce_01__a_row_is_created_with_every_given_value(db, w1, u1, inv1):
    """IEV-CE-01 — a row is created with every given value.
    Rules: `create_event` R1, R2, Returns, Side effects"""
    result = dao.create_event(
        db, workspace_id=w1.id, invoice_id=inv1.id, event_type="payment_recorded", description="Payment recorded",
        performed_by=u1.id, metadata={"amount": "40.00", "method": "cash"},
    )

    # Then 1
    assert isinstance(result, InvoiceEvent)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.invoice_id == inv1.id
    assert row.performed_by == u1.id
    # Then 4
    assert row.event_type == "payment_recorded"
    assert row.description == "Payment recorded"
    # Then 5
    assert row.metadata_json == {"amount": "40.00", "method": "cash"}
    # Then 6
    assert count_rows(db, InvoiceEvent.invoice_id == inv1.id) == 1


# [claude] IEV-CE-02
def test_iev_ce_02__created_at_is_the_real_moment_in_utc_naive(db, w1, inv1):
    """IEV-CE-02 — created_at is the real moment in UTC, naive.
    Rules: `create_event` R1"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description="Invoice created")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_at.tzinfo is None
    # Then 3
    assert abs(utc_clock(db) - row.created_at) < timedelta(seconds=5)


# [claude] IEV-CE-03
def test_iev_ce_03__performed_by_and_metadata_default_to_none_none_is_stored_as_json_null(db, w1, inv1):
    """IEV-CE-03 — performed_by and metadata default to None; None is stored as JSON null.
    Rules: `create_event` R2"""
    result = dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description="Invoice created")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_by is None
    assert row.metadata_json is None
    # Then 3
    assert stored_json(db, result) == "null"
    # Then 4
    assert is_sql_null(db, result) is False


# [claude] IEV-CE-04
def test_iev_ce_04__a_list_in_metadata_is_stored_and_read_back_as_given(db, w1, inv1):
    """IEV-CE-04 — a list in metadata is stored and read back as given.
    Rules: `create_event` R2"""
    result = dao.create_event(
        db, workspace_id=w1.id, invoice_id=inv1.id, event_type="items_synced", description="Items synced",
        metadata=[{"line": 1}, "x", 2],
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.metadata_json == [{"line": 1}, "x", 2]


# [claude] IEV-CE-05
def test_iev_ce_05__an_empty_description_and_a_50_character_event_type_are_stored(db, w1, inv1):
    """IEV-CE-05 — an empty description and a 50-character event type are stored.
    Rules: `create_event` R3"""
    result = dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="e" * 50, description="")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.event_type == "e" * 50
    assert row.description == ""


# [claude] IEV-CE-06
def test_iev_ce_06__an_empty_event_type_is_stored(db, w1, inv1):
    """IEV-CE-06 — an empty event type is stored.
    Rules: `create_event` R3"""
    result = dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="", description="Invoice created")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.event_type == ""


# [claude] IEV-CE-07
def test_iev_ce_07__the_invoice_s_workspace_is_not_compared_a_row_is_stored_under_another(db, w2, inv1):
    """IEV-CE-07 — the invoice's workspace is not compared: a row is stored under another workspace.
    Rules: `create_event` R3"""
    result = dao.create_event(db, workspace_id=w2.id, invoice_id=inv1.id, event_type="created", description="Invoice created")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.invoice_id == inv1.id


# [claude] IEV-CE-08
def test_iev_ce_08__an_event_type_of_51_characters_raises_dataerror_22001_and_saves_nothing(db, w1, inv1):
    """IEV-CE-08 — an event type of 51 characters raises DataError 22001 and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="e" * 51, description="Invoice created")
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-09
def test_iev_ce_09__description_none_raises_integrityerror_23502_and_saves_nothing(db, w1, inv1):
    """IEV-CE-09 — description None raises IntegrityError 23502 and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description=None)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-10
def test_iev_ce_10__an_unknown_invoice_raises_integrityerror_23503_and_saves_nothing(db, w1):
    """IEV-CE-10 — an unknown invoice raises IntegrityError 23503 and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=w1.id, invoice_id=MISSING, event_type="created", description="Invoice created")
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-11
def test_iev_ce_11__an_unknown_performer_raises_integrityerror_23503_and_saves_nothing(db, w1, inv1):
    """IEV-CE-11 — an unknown performer raises IntegrityError 23503 and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(
                db, workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description="Invoice created",
                performed_by=MISSING,
            )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-12
def test_iev_ce_12__an_unknown_workspace_raises_integrityerror_23503_and_saves_nothing(db, inv1):
    """IEV-CE-12 — an unknown workspace raises IntegrityError 23503 and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_event(db, workspace_id=MISSING, invoice_id=inv1.id, event_type="created", description="Invoice created")
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-13
def test_iev_ce_13__a_decimal_in_metadata_raises_statementerror_wrapping_typeerror_and_saves(db, w1, inv1):
    """IEV-CE-13 — a Decimal in metadata raises StatementError wrapping TypeError and saves nothing.
    Rules: `create_event` R4, Errors"""
    before = written_count(db)

    # Then 1
    with pytest.raises(StatementError) as exc:
        with db.begin_nested():
            dao.create_event(
                db, workspace_id=w1.id, invoice_id=inv1.id, event_type="payment_recorded", description="Payment recorded",
                metadata={"amount": Decimal("40.00")},
            )
    assert isinstance(exc.value.orig, TypeError)
    # Then 2
    assert written_count(db) == before


# [claude] IEV-CE-14
def test_iev_ce_14__flushed_not_committed_a_rollback_removes_the_row(db, w1, inv1):
    """IEV-CE-14 — flushed, not committed: a rollback removes the row.
    Rules: `create_event` R5, Side effects"""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.create_event(db, workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description="Invoice created")

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_rows(db, InvoiceEvent.invoice_id == inv1.id) == 1
        # Then 3
        sp.rollback()
        assert count_rows(db, InvoiceEvent.invoice_id == inv1.id) == 0
        # Then 4
        assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# InvoiceEventDAO.get_by_invoice
# --------------------------------------------------------------------------- #


# [claude] IEV-GI-01
def test_iev_gi_01__returns_a_list_of_dicts_with_exactly_the_stated_keys_and_the_stored(db, w1, u1, inv1, mk_event):
    """IEV-GI-01 — returns a list of dicts with exactly the stated keys and the stored values.
    Rules: `get_by_invoice` R1, R4, R6, Returns"""
    a = mk_event(
        created_at=T10, event_type="payment_recorded", description="Payment recorded", performed_by=u1.id,
        metadata_json={"amount": "40.00"},
    )

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]
    # Then 3
    assert set(result[0].keys()) == KEYS
    # Then 4
    assert result[0]["workspace_id"] == w1.id
    assert result[0]["invoice_id"] == inv1.id
    # Then 5
    assert result[0]["event_type"] == "payment_recorded"
    assert result[0]["description"] == "Payment recorded"
    # Then 6
    assert result[0]["metadata_json"] == {"amount": "40.00"}
    # Then 7
    assert result[0]["performed_by"] == u1.id
    assert result[0]["performed_by_name"] == "Rahim"
    # Then 8
    assert result[0]["created_at"] == T10
    # Then 9
    assert result[0]["created_at"].tzinfo is None


# [claude] IEV-GI-02
def test_iev_gi_02__another_invoice_s_events_are_not_returned(db, w1, inv1, inv2, mk_event):
    """IEV-GI-02 — another invoice's events are not returned.
    Rules: `get_by_invoice` R1"""
    a = mk_event(created_at=T10)
    mk_event(created_at=T12, invoice_id=inv2.id)

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] IEV-GI-03
def test_iev_gi_03__an_event_of_this_invoice_stored_under_another_workspace_is_not_returned(db, w1, w2, inv1, mk_event):
    """IEV-GI-03 — an event of this invoice stored under another workspace is not returned.
    Rules: `get_by_invoice` R1"""
    mk_event(created_at=T12, workspace_id=w2.id)
    a = mk_event(created_at=T10)
    mk_event(created_at=T11, workspace_id=w2.id)

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] IEV-GI-04
def test_iev_gi_04__asking_with_that_other_workspace_returns_only_the_event_stored_under_it(db, w2, inv1, mk_event):
    """IEV-GI-04 — asking with that other workspace returns only the event stored under it.
    Rules: `get_by_invoice` R1"""
    mk_event(created_at=T10)
    z = mk_event(created_at=T11, workspace_id=w2.id)

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] IEV-GI-05
def test_iev_gi_05__the_other_workspace_s_own_invoice_is_not_returned_when_asking_with_w1(db, w1, w2, inv9, mk_event):
    """IEV-GI-05 — the other workspace's own invoice is not returned when asking with W1.
    Rules: `get_by_invoice` R1"""
    mk_event(created_at=T10, workspace_id=w2.id, invoice_id=inv9.id)

    result = dao.get_by_invoice(db, invoice_id=inv9.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] IEV-GI-06
def test_iev_gi_06__an_unknown_invoice_id_returns_an_empty_list(db, w1, mk_event):
    """IEV-GI-06 — an unknown invoice id returns an empty list.
    Rules: `get_by_invoice` R1"""
    mk_event(created_at=T10)

    result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] IEV-GI-07
def test_iev_gi_07__invoice_id_0_returns_an_empty_list(db, w1, mk_event):
    """IEV-GI-07 — invoice id 0 returns an empty list.
    Rules: `get_by_invoice` R1"""
    mk_event(created_at=T10)

    result = dao.get_by_invoice(db, invoice_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] IEV-GI-08
def test_iev_gi_08__newest_first_by_created_at_also_when_the_older_event_has_the_higher_id(db, w1, inv1, mk_event):
    """IEV-GI-08 — newest first by created_at, also when the older event has the higher id.
    Rules: `get_by_invoice` R3 (the part that holds today)"""
    a = mk_event(created_at=T11, description="b")
    b = mk_event(created_at=T12, description="a")
    c = mk_event(created_at=T10, description="c")

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] IEV-GI-09
@pytest.mark.xfail(strict=False, reason=BUG_638 + NON_STRICT)
def test_iev_gi_09__events_of_one_time_come_back_highest_id_first_also_after_the_lowest_was(db, w1, inv1, mk_event):
    """IEV-GI-09 — events of one time come back highest id first, also after the lowest was updated.
    Rules: `get_by_invoice` R3 [BUG-638]"""
    a = mk_event(created_at=T11)
    b = mk_event(created_at=T11)
    c = mk_event(created_at=T11)
    d = mk_event(created_at=T12)
    seqscan(db)
    bump_e(db, a)

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] IEV-GI-10
@pytest.mark.xfail(strict=True, reason=BUG_638)
def test_iev_gi_10__the_query_orders_by_created_at_then_id_both_descending(db, w1, inv1, mk_event):
    """IEV-GI-10 — the query orders by created_at, then id, both descending.
    Rules: `get_by_invoice` R3 [BUG-638]"""
    a = mk_event(created_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "invoice_events.created_at" in order_part
    # Then 3
    assert "invoice_events.id" in order_part
    # Then 4
    assert order_part.index("invoice_events.created_at") < order_part.index("invoice_events.id")
    # Then 5
    assert order_part.upper().count("DESC") == 2


# [claude] IEV-GI-11
def test_iev_gi_11__every_event_is_returned_201_give_201(db, w1, inv1):
    """IEV-GI-11 — every event is returned: 201 give 201.
    Rules: `get_by_invoice` R2"""
    rows = [_event(w1, inv1, T10 + timedelta(minutes=k)) for k in range(1, 202)]
    db.add_all(rows)
    db.flush()
    e201 = rows[-1]

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 201
    # Then 2
    assert result[0]["id"] == e201.id


# [claude] IEV-GI-12
def test_iev_gi_12__no_performer_performed_by_and_performed_by_name_are_none(db, w1, inv1, mk_event):
    """IEV-GI-12 — no performer: performed_by and performed_by_name are None.
    Rules: `get_by_invoice` R4"""
    a = mk_event(created_at=T10)

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0]["performed_by"] is None
    # Then 3
    assert result[0]["performed_by_name"] is None


# [claude] IEV-GI-13
def test_iev_gi_13__the_performer_s_current_name_is_shown_a_deleted_performer_gives_none(db, w1, u1, u2, inv1, mk_event):
    """IEV-GI-13 — the performer's current name is shown; a deleted performer gives None.
    Rules: `get_by_invoice` R4 (P1)"""
    a = mk_event(created_at=T11, performed_by=u1.id)
    b = mk_event(created_at=T10, performed_by=u2.id)
    db.execute(text("UPDATE profiles SET name = 'Rahim Uddin' WHERE id = :i"), {"i": u1.id})
    db.execute(text("DELETE FROM profiles WHERE id = :i"), {"i": u2.id})
    db.expire_all()

    result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]
    # Then 2
    assert result[0]["performed_by"] == u1.id
    assert result[0]["performed_by_name"] == "Rahim Uddin"
    # Then 3
    assert result[1]["performed_by"] is None
    assert result[1]["performed_by_name"] is None


# [claude] IEV-GI-14
def test_iev_gi_14__the_invoice_row_is_not_read_no_join_to_account_invoices(db, w1, inv1, mk_event):
    """IEV-GI-14 — the invoice row is not read: no join to account_invoices.
    Rules: `get_by_invoice` R5 (P1; Spec gap 2)"""
    a = mk_event(created_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "account_invoices" not in sql


# [claude] IEV-GI-15
def test_iev_gi_15__writes_nothing_a_pending_event_stays_pending_an_unflushed_edit_stays(db, w1, inv1, inv2, mk_event):
    """IEV-GI-15 — writes nothing: a pending event stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_invoice` Side effects"""
    a = mk_event(created_at=T10)
    b = mk_event(created_at=T10, invoice_id=inv2.id)
    b.description = "Edited"
    p = InvoiceEvent(workspace_id=w1.id, invoice_id=inv1.id, event_type="created", description="Pending", created_at=T12)
    db.add(p)
    before = written_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_invoice(db, invoice_id=inv1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
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
    assert written_count(db) == before
