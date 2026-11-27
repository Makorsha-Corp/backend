"""Unit tests for app/dao/attachment_ledger.py.

Implements tests/unit/dao/attachment_ledger.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture).
Nothing is mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.attachment_ledger import attachment_ledger_dao
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton attachment_ledger_dao" (a module-level name, not a fixture)
dao = attachment_ledger_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "H9 ... H14": aware UTC moments, before the US clock change
H9 = datetime(2026, 3, 5, 9, 0, 0, tzinfo=timezone.utc)
H10 = datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc)
H11 = datetime(2026, 3, 5, 11, 0, 0, tzinfo=timezone.utc)
H12 = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
H13 = datetime(2026, 3, 5, 13, 0, 0, tzinfo=timezone.utc)
H14 = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)

# Convention "US, P6, M5"
US = timedelta(microseconds=1)
P6 = timezone(timedelta(hours=6))
M5 = timezone(timedelta(hours=-5))

# Convention "T12": naive
T12 = datetime(2026, 3, 4, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Conventions list these rows in this order; each fixture depends on the one before,
# so the rows are flushed one at a time and ids rise in that order.
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
def at1(db, w1, u1):
    return _add(db, Attachment(workspace_id=w1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=u1.id))


@pytest.fixture
def at2(db, w1, u1, at1):
    return _add(db, Attachment(workspace_id=w1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=u1.id))


@pytest.fixture
def at9(db, w2, u1, at2):
    return _add(db, Attachment(workspace_id=w2.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=u1.id))


@pytest.fixture
def atd(db, w1, u1, at9):
    return _add(db, Attachment(workspace_id=w1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=u1.id, is_deleted=True, deleted_at=T12, deleted_by=u1.id))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, at1, at2, at9, atd):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "entry": the columns the Conventions say are not passed stay out of the constructor
@pytest.fixture
def mk_entry(db, w1, at1):
    """mk_entry(performed_at=..., **columns) -> AttachmentLedger. Keywords only."""
    def _mk(*, performed_at, **columns):
        fields = {"workspace_id": w1.id, "attachment_id": at1.id, "transaction_type": "ready", "file_name": "file.png", "mime_type": "image/png", "file_size": 100, "entity_type": "purchase_order", "performed_at": performed_at}
        fields.update(columns)
        return _add(db, AttachmentLedger(**fields))
    return _mk


# The "built with add_all" Given lines
@pytest.fixture
def mk_many(db, w1, at1):
    """mk_many(count) -> `in_order`: the ids of the rows, in the card's order."""
    def _mk(count):
        rows = [AttachmentLedger(workspace_id=w1.id, attachment_id=at1.id, transaction_type="ready", file_name="file.png", mime_type="image/png", file_size=100, entity_type="purchase_order", performed_at=H10 + timedelta(minutes=k))
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


# Convention "nothing written": the number of attachment_ledger rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(AttachmentLedger.__table__)).scalar_one()


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
        """The one SELECT from attachment_ledger; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "attachment_ledger" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AttachmentLedgerDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] ATL-G-01
def test_atl_g_01__returns_a_list_of_the_workspace_s_entries_newest_first(db, w1, mk_entry):
    """ATL-G-01 — returns a list of the workspace's entries, newest first.
    Rules: `get_by_workspace` R1, Returns"""
    a = mk_entry(performed_at=H11)
    b = mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], AttachmentLedger)


# [claude] ATL-G-02
def test_atl_g_02__a_newer_entry_of_another_workspace_is_not_returned(db, w1, w2, at9, mk_entry):
    """ATL-G-02 — a newer entry of another workspace is not returned.
    Rules: `get_by_workspace` R1"""
    a = mk_entry(performed_at=H11)
    mk_entry(performed_at=H12, workspace_id=w2.id, attachment_id=at9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-03
def test_atl_g_03__another_workspace_returns_an_empty_list(db, w2, mk_entry):
    """ATL-G-03 — another workspace returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] ATL-G-04
def test_atl_g_04__an_unknown_workspace_returns_an_empty_list(db, mk_entry):
    """ATL-G-04 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] ATL-G-05
def test_atl_g_05__attachment_id_keeps_that_attachment_s_entries_a_newer_one_of_another_a(db, w1, at1, at2, mk_entry):
    """ATL-G-05 — attachment_id keeps that attachment's entries; a newer one of another attachment is not returned.
    Rules: `get_by_workspace` R2"""
    a = mk_entry(performed_at=H11)
    mk_entry(performed_at=H12, attachment_id=at2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-06
def test_atl_g_06__attachment_id_0_is_a_real_filter_and_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-06 — attachment_id=0 is a real filter and returns an empty list.
    Rules: `get_by_workspace` R2"""
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=0)

    # Then 1
    assert result == []


# [claude] ATL-G-07
def test_atl_g_07__attachment_id_none_applies_no_filter(db, w1, at2, mk_entry):
    """ATL-G-07 — attachment_id=None applies no filter.
    Rules: `get_by_workspace` R2"""
    a = mk_entry(performed_at=H11)
    b = mk_entry(performed_at=H12, attachment_id=at2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-08
def test_atl_g_08__an_attachment_of_another_workspace_reaches_nothing(db, w1, w2, at9, mk_entry):
    """ATL-G-08 — an attachment of another workspace reaches nothing.
    Rules: `get_by_workspace` R2"""
    mk_entry(performed_at=H11, workspace_id=w2.id, attachment_id=at9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=at9.id)

    # Then 1
    assert result == []


# [claude] ATL-G-09
def test_atl_g_09__entity_type_keeps_exact_matches_another_value_and_null_are_left_out(db, w1, mk_entry):
    """ATL-G-09 — entity_type keeps exact matches: another value and NULL are left out.
    Rules: `get_by_workspace` R3"""
    a = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, entity_type="sales_order")
    mk_entry(performed_at=H12, entity_type=None)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase_order")

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-10
def test_atl_g_10__entity_type_none_applies_no_filter_a_null_row_is_kept(db, w1, mk_entry):
    """ATL-G-10 — entity_type=None applies no filter: a NULL row is kept.
    Rules: `get_by_workspace` R3"""
    a = mk_entry(performed_at=H10)
    b = mk_entry(performed_at=H11, entity_type="sales_order")
    c = mk_entry(performed_at=H12, entity_type=None)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type=None)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] ATL-G-11
def test_atl_g_11__entity_type_applies_no_filter_a_null_row_is_kept(db, w1, mk_entry):
    """ATL-G-11 — entity_type="" applies no filter: a NULL row is kept.
    Rules: `get_by_workspace` R3"""
    a = mk_entry(performed_at=H10)
    b = mk_entry(performed_at=H11, entity_type="sales_order")
    c = mk_entry(performed_at=H12, entity_type=None)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="")

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] ATL-G-12
def test_atl_g_12__entity_type_in_another_case_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-12 — entity_type in another case returns an empty list.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, entity_type="sales_order")
    mk_entry(performed_at=H12, entity_type=None)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="PURCHASE_ORDER")

    # Then 1
    assert result == []


# [claude] ATL-G-13
def test_atl_g_13__an_unknown_entity_type_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-13 — an unknown entity_type returns an empty list.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, entity_type="sales_order")
    mk_entry(performed_at=H12, entity_type=None)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="nothing")

    # Then 1
    assert result == []


# [claude] ATL-G-14
def test_atl_g_14__transaction_type_keeps_exact_matches(db, w1, mk_entry):
    """ATL-G-14 — transaction_type keeps exact matches.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, transaction_type="failed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="ready")

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-15
def test_atl_g_15__transaction_type_none_applies_no_filter(db, w1, mk_entry):
    """ATL-G-15 — transaction_type=None applies no filter.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=H10)
    b = mk_entry(performed_at=H11, transaction_type="failed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-16
def test_atl_g_16__transaction_type_applies_no_filter(db, w1, mk_entry):
    """ATL-G-16 — transaction_type="" applies no filter.
    Rules: `get_by_workspace` R4"""
    a = mk_entry(performed_at=H10)
    b = mk_entry(performed_at=H11, transaction_type="failed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="")

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-17
def test_atl_g_17__transaction_type_in_another_case_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-17 — transaction_type in another case returns an empty list.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, transaction_type="failed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="READY")

    # Then 1
    assert result == []


# [claude] ATL-G-18
def test_atl_g_18__an_unknown_transaction_type_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-18 — an unknown transaction_type returns an empty list.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, transaction_type="failed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="nothing")

    # Then 1
    assert result == []


# [claude] ATL-G-19
def test_atl_g_19__start_date_keeps_the_row_at_that_moment_and_later_one_microsecond_befo(db, w1, mk_entry):
    """ATL-G-19 — start_date keeps the row at that moment and later; one microsecond before is left out.
    Rules: `get_by_workspace` R5"""
    mk_entry(performed_at=H12 - US)
    b = mk_entry(performed_at=H12)
    c = mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H12)

    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] ATL-G-20
def test_atl_g_20__end_date_keeps_the_row_at_that_moment_and_earlier_one_microsecond_afte(db, w1, mk_entry):
    """ATL-G-20 — end_date keeps the row at that moment and earlier; one microsecond after is left out.
    Rules: `get_by_workspace` R6"""
    a = mk_entry(performed_at=H12 - US)
    b = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=H12)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-21
def test_atl_g_21__start_date_equal_to_end_date_keeps_the_rows_at_that_moment_only(db, w1, mk_entry):
    """ATL-G-21 — start_date equal to end_date keeps the rows at that moment only.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=H12 - US)
    b = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H12, end_date=H12)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ATL-G-22
def test_atl_g_22__start_date_after_end_date_returns_an_empty_list_with_no_error(db, w1, mk_entry):
    """ATL-G-22 — start_date after end_date returns an empty list, with no error.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=H12 - US)
    mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H13, end_date=H11)

    # Then 1
    assert result == []


# [claude] ATL-G-23
def test_atl_g_23__start_date_one_microsecond_after_end_date_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-23 — start_date one microsecond after end_date returns an empty list.
    Rules: `get_by_workspace` R6"""
    mk_entry(performed_at=H12 - US)
    mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H12 + US, end_date=H12)

    # Then 1
    assert result == []


# [claude] ATL-G-24
def test_atl_g_24__a_day_apart_bounds_compare_the_whole_moment_not_the_time_of_day(db, w1, mk_entry):
    """ATL-G-24 — a day apart: bounds compare the whole moment, not the time of day.
    Rules: `get_by_workspace` R5, R6"""
    mk_entry(performed_at=H12 - timedelta(days=1))
    b = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + timedelta(days=1))

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H11, end_date=H13)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ATL-G-25
def test_atl_g_25__end_date_with_a_zone_is_an_exact_moment_under_utc(db, w1, mk_entry):
    """ATL-G-25 — end_date with a zone is an exact moment under UTC.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-26
def test_atl_g_26__end_date_with_a_zone_is_an_exact_moment_under_asia_dhaka(db, w1, mk_entry):
    """ATL-G-26 — end_date with a zone is an exact moment under Asia/Dhaka.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-27
def test_atl_g_27__end_date_with_a_zone_is_an_exact_moment_under_america_new_york(db, w1, mk_entry):
    """ATL-G-27 — end_date with a zone is an exact moment under America/New_York.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 + US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-28
def test_atl_g_28__start_date_with_a_zone_is_an_exact_moment_under_utc(db, w1, mk_entry):
    """ATL-G-28 — start_date with a zone is an exact moment under UTC.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 - US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-29
def test_atl_g_29__start_date_with_a_zone_is_an_exact_moment_under_asia_dhaka(db, w1, mk_entry):
    """ATL-G-29 — start_date with a zone is an exact moment under Asia/Dhaka.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 - US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-30
def test_atl_g_30__start_date_with_a_zone_is_an_exact_moment_under_america_new_york(db, w1, mk_entry):
    """ATL-G-30 — start_date with a zone is an exact moment under America/New_York.
    Rules: `get_by_workspace` R7"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H12 - US)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-31
def test_atl_g_31__a_naive_end_date_means_utc_under_utc(db, w1, mk_entry):
    """ATL-G-31 — a naive end_date means UTC, under UTC.
    Rules: `get_by_workspace` R7a"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H13)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-32
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_32__a_naive_end_date_means_utc_under_asia_dhaka(db, w1, mk_entry):
    """ATL-G-32 — a naive end_date means UTC, under Asia/Dhaka.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H13)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-33
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_33__a_naive_end_date_means_utc_under_america_new_york(db, w1, mk_entry):
    """ATL-G-33 — a naive end_date means UTC, under America/New_York.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H13)

    result = dao.get_by_workspace(db, workspace_id=w1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-34
def test_atl_g_34__a_naive_start_date_means_utc_under_utc(db, w1, mk_entry):
    """ATL-G-34 — a naive start_date means UTC, under UTC.
    Rules: `get_by_workspace` R7a"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-35
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_35__a_naive_start_date_means_utc_under_asia_dhaka(db, w1, mk_entry):
    """ATL-G-35 — a naive start_date means UTC, under Asia/Dhaka.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-36
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_36__a_naive_start_date_means_utc_under_america_new_york(db, w1, mk_entry):
    """ATL-G-36 — a naive start_date means UTC, under America/New_York.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-37
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_37__a_naive_start_date_with_an_aware_end_date_each_bound_keeps_its_own_mea(db, w1, mk_entry):
    """ATL-G-37 — a naive start_date with an aware end_date: each bound keeps its own meaning.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H11)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=datetime(2026, 3, 5, 12, 0, 0), end_date=H12)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-38
@pytest.mark.xfail(strict=True, reason="BUG-1281: Attachment ledger date filter with no time zone depends on the database's time-zone setting")
def test_atl_g_38__an_aware_start_date_with_a_naive_end_date_each_bound_keeps_its_own_mea(db, w1, mk_entry):
    """ATL-G-38 — an aware start_date with a naive end_date: each bound keeps its own meaning.
    Rules: `get_by_workspace` R7a [BUG-1281]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_entry(performed_at=H12)
    mk_entry(performed_at=H13)

    result = dao.get_by_workspace(db, workspace_id=w1.id, start_date=H12, end_date=datetime(2026, 3, 5, 12, 0, 0))

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-39
def test_atl_g_39__entries_are_ordered_by_performed_at_descending_against_id_and_text(db, w1, mk_entry):
    """ATL-G-39 — entries are ordered by performed_at descending, against id and text.
    Rules: `get_by_workspace` R8"""
    a = mk_entry(performed_at=H12, file_name="alpha.png")
    b = mk_entry(performed_at=H13, file_name="zeta.png")
    c = mk_entry(performed_at=H11, file_name="mid.png")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] ATL-G-40
def test_atl_g_40__one_microsecond_inside_one_day_decides_the_order_against_id(db, w1, mk_entry):
    """ATL-G-40 — one microsecond inside one day decides the order, against id.
    Rules: `get_by_workspace` R8"""
    a = mk_entry(performed_at=H12 + US)
    b = mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] ATL-G-41
def test_atl_g_41__on_a_tie_both_entries_are_returned_before_the_older_one(db, w1, mk_entry):
    """ATL-G-41 — on a tie both entries are returned, before the older one.
    Rules: `get_by_workspace` R8"""
    a = mk_entry(performed_at=H12)
    b = mk_entry(performed_at=H12)
    c = mk_entry(performed_at=H11)
    a.file_size = 200
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[2].id == c.id
    # Then 3
    assert {r.id for r in result[:2]} == {a.id, b.id}


# [claude] ATL-G-42
@pytest.mark.xfail(
    strict=False,
    reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_atl_g_42__on_a_tie_the_higher_id_comes_first_when_the_higher_id_was_updated(db, w1, mk_entry):
    """ATL-G-42 — on a tie the higher id comes first, when the higher id was updated.
    Rules: `get_by_workspace` R8 [BUG-640]"""
    a = mk_entry(performed_at=H12, file_name="zeta.png")
    b = mk_entry(performed_at=H12, file_name="alpha.png")
    b.file_size = 200
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-43
@pytest.mark.xfail(
    strict=False,
    reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order"
    " (non-strict: the order rests on physical row order, which can match by accident)",
)
def test_atl_g_43__on_a_tie_the_higher_id_comes_first_with_no_update(db, w1, mk_entry):
    """ATL-G-43 — on a tie the higher id comes first, with no update.
    Rules: `get_by_workspace` R8 [BUG-640]"""
    a = mk_entry(performed_at=H12, file_name="zeta.png")
    b = mk_entry(performed_at=H12, file_name="alpha.png")
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [b.id, a.id]


# [claude] ATL-G-44
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by `performed_at` only; ties in no fixed order")
def test_atl_g_44__the_query_orders_by_performed_at_then_id_both_descending(db, w1, mk_entry):
    """ATL-G-44 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_workspace` R8 [BUG-640]"""
    a = mk_entry(performed_at=H12)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "performed_at DESC" in order_part
    # Then 3
    assert ".id DESC" in order_part
    # Then 4
    assert order_part.index("performed_at") < order_part.index(".id")


# [claude] ATL-G-45
def test_atl_g_45__with_the_default_limit_105_rows_give_100(db, w1, mk_many):
    """ATL-G-45 — with the default limit 105 rows give 100.
    Rules: `get_by_workspace` R9"""
    in_order = mk_many(105)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == in_order[:100]


# [claude] ATL-G-46
def test_atl_g_46__limit_1000_gives_all_105_rows(db, w1, mk_many):
    """ATL-G-46 — limit=1000 gives all 105 rows.
    Rules: `get_by_workspace` R9"""
    in_order = mk_many(105)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 105
    # Then 2
    assert ids(result) == in_order


# [claude] ATL-G-47
def test_atl_g_47__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-47 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R10"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11)
    mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ATL-G-48
def test_atl_g_48__skip_past_the_end_returns_an_empty_list(db, w1, mk_entry):
    """ATL-G-48 — skip past the end returns an empty list.
    Rules: `get_by_workspace` R10"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11)
    mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] ATL-G-49
def test_atl_g_49__a_negative_limit_is_refused_by_postgres(db, w1, mk_entry):
    """ATL-G-49 — a negative limit is refused by Postgres.
    Rules: `get_by_workspace` R11, Errors row 1 (negative `limit`)"""
    mk_entry(performed_at=H10)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] ATL-G-50
def test_atl_g_50__a_negative_skip_is_refused_by_postgres(db, w1, mk_entry):
    """ATL-G-50 — a negative skip is refused by Postgres.
    Rules: `get_by_workspace` R11, Errors row 2 (negative `skip`)"""
    mk_entry(performed_at=H10)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] ATL-G-51
def test_atl_g_51__limit_1_returns_the_newest_row_the_other_side_of_limit_0(db, w1, mk_entry):
    """ATL-G-51 — limit=1 returns the newest row: the other side of limit=0.
    Rules: `get_by_workspace` R10, R8"""
    mk_entry(performed_at=H10)
    mk_entry(performed_at=H11)
    c = mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] ATL-G-52
def test_atl_g_52__skip_2_of_three_rows_returns_the_oldest_the_other_side_of_skip_past_th(db, w1, mk_entry):
    """ATL-G-52 — skip=2 of three rows returns the oldest: the other side of skip past the end.
    Rules: `get_by_workspace` R10, R8"""
    a = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11)
    mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-53
def test_atl_g_53__all_filters_combine_a_row_failing_any_one_of_them_is_left_out(db, w1, w2, at1, at2, at9, mk_entry):
    """ATL-G-53 — all filters combine: a row failing any one of them is left out.
    Rules: `get_by_workspace` R12"""
    m = mk_entry(performed_at=H11)
    mk_entry(performed_at=H12, attachment_id=at2.id)
    mk_entry(performed_at=H12, entity_type="sales_order")
    mk_entry(performed_at=H12, transaction_type="failed")
    mk_entry(performed_at=H14)
    mk_entry(performed_at=H9)
    mk_entry(performed_at=H12, workspace_id=w2.id, attachment_id=at9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=at1.id, entity_type="purchase_order", transaction_type="ready", start_date=H10, end_date=H13)

    # Then 1
    assert ids(result) == [m.id]


# [claude] ATL-G-54
def test_atl_g_54__filters_apply_before_skip_and_limit_hidden_rows_that_sort_first_use_up(db, w1, w2, at1, at2, at9, mk_entry):
    """ATL-G-54 — filters apply before skip and limit: hidden rows that sort first use up no skip.
    Rules: `get_by_workspace` R12, R8"""
    m1 = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11)
    mk_entry(performed_at=H12, attachment_id=at2.id)
    mk_entry(performed_at=H12, entity_type="sales_order")
    mk_entry(performed_at=H12, transaction_type="failed")
    mk_entry(performed_at=H14)
    mk_entry(performed_at=H12, workspace_id=w2.id, attachment_id=at9.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=at1.id, entity_type="purchase_order", transaction_type="ready", start_date=H10, end_date=H13, skip=1, limit=1)

    # Then 1
    assert ids(result) == [m1.id]


# [claude] ATL-G-55
def test_atl_g_55__every_entry_of_a_soft_deleted_attachment_is_returned(db, w1, atd, mk_entry):
    """ATL-G-55 — every entry of a soft-deleted attachment is returned.
    Rules: `get_by_workspace` R13"""
    a = mk_entry(performed_at=H10, attachment_id=atd.id, transaction_type="pending")
    b = mk_entry(performed_at=H11, attachment_id=atd.id, transaction_type="ready")
    c = mk_entry(performed_at=H12, attachment_id=atd.id, transaction_type="deleted")

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=atd.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] ATL-G-56
def test_atl_g_56__writes_nothing_a_newer_pending_row_stays_pending_and_alone_in_the_sess(db, w1, at1, mk_entry):
    """ATL-G-56 — writes nothing: a newer pending row stays pending and alone in the session.
    Rules: `get_by_workspace` Side effects, R13"""
    a = mk_entry(performed_at=H11)
    p = AttachmentLedger(workspace_id=w1.id, attachment_id=at1.id, transaction_type="ready", file_name="file.png", mime_type="image/png", file_size=100, performed_at=H12)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert not db.dirty
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []
    # Then 8
    assert len(selects) == 1
    # Then 9
    assert "FOR UPDATE" not in sql.upper()
    # Then 10
    assert "attachments" not in sql
    # Then 11
    assert stored_count(db) == before
    # Then 12
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] ATL-G-57
def test_atl_g_57__entity_type_purchase_order_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-57 — entity_type=" purchase_order" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type=" purchase_order")

    # Then 1
    assert result == []


# [claude] ATL-G-58
def test_atl_g_58__entity_type_purchase_order_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-58 — entity_type="purchase_order " returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase_order ")

    # Then 1
    assert result == []


# [claude] ATL-G-59
def test_atl_g_59__entity_type_purchase_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-59 — entity_type="purchase" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase")

    # Then 1
    assert result == []


# [claude] ATL-G-60
def test_atl_g_60__entity_type_order_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-60 — entity_type="order" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="order")

    # Then 1
    assert result == []


# [claude] ATL-G-61
def test_atl_g_61__entity_type_purchase_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-61 — entity_type="purchase%" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase%")

    # Then 1
    assert result == []


# [claude] ATL-G-62
def test_atl_g_62__entity_type_purchase_orde_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-62 — entity_type="purchase_orde_" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R3"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase_orde_")

    # Then 1
    assert result == []


# [claude] ATL-G-63
def test_atl_g_63__entity_type_matches_the_stored_value_exactly_case_spaces_longer_values(db, w1, mk_entry):
    """ATL-G-63 — entity_type matches the stored value exactly: case, spaces, longer values and look-alikes are left out.
    Rules: `get_by_workspace` R3"""
    m = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, entity_type="PURCHASE_ORDER")
    mk_entry(performed_at=H11, entity_type=" purchase_order")
    mk_entry(performed_at=H11, entity_type="purchase_order ")
    mk_entry(performed_at=H11, entity_type="purchase_orderX")
    mk_entry(performed_at=H11, entity_type="Xpurchase_order")
    mk_entry(performed_at=H11, entity_type="purchaseXorder")

    result = dao.get_by_workspace(db, workspace_id=w1.id, entity_type="purchase_order")

    # Then 1
    assert ids(result) == [m.id]


# [claude] ATL-G-64
def test_atl_g_64__transaction_type_ready_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-64 — transaction_type=" ready" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type=" ready")

    # Then 1
    assert result == []


# [claude] ATL-G-65
def test_atl_g_65__transaction_type_ready_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-65 — transaction_type="ready " returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="ready ")

    # Then 1
    assert result == []


# [claude] ATL-G-66
def test_atl_g_66__transaction_type_rea_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-66 — transaction_type="rea" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="rea")

    # Then 1
    assert result == []


# [claude] ATL-G-67
def test_atl_g_67__transaction_type_dy_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-67 — transaction_type="dy" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="dy")

    # Then 1
    assert result == []


# [claude] ATL-G-68
def test_atl_g_68__transaction_type_rea_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-68 — transaction_type="rea%" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="rea%")

    # Then 1
    assert result == []


# [claude] ATL-G-69
def test_atl_g_69__transaction_type_r_ady_returns_an_empty_list_the_compare_is_exact(db, w1, mk_entry):
    """ATL-G-69 — transaction_type="r_ady" returns an empty list: the compare is exact.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10)

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="r_ady")

    # Then 1
    assert result == []


# [claude] ATL-G-70
def test_atl_g_70__transaction_type_matches_the_stored_value_exactly_case_spaces_and_long(db, w1, mk_entry):
    """ATL-G-70 — transaction_type matches the stored value exactly: case, spaces and longer values are left out.
    Rules: `get_by_workspace` R4"""
    m = mk_entry(performed_at=H10)
    mk_entry(performed_at=H11, transaction_type="READY")
    mk_entry(performed_at=H11, transaction_type=" ready")
    mk_entry(performed_at=H11, transaction_type="ready ")
    mk_entry(performed_at=H11, transaction_type="readyX")
    mk_entry(performed_at=H11, transaction_type="Xready")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="ready")

    # Then 1
    assert ids(result) == [m.id]


# [claude] ATL-G-71
def test_atl_g_71__an_underscore_in_transaction_type_is_a_plain_character(db, w1, mk_entry):
    """ATL-G-71 — an underscore in transaction_type is a plain character.
    Rules: `get_by_workspace` R4"""
    mk_entry(performed_at=H10, transaction_type="pendingX")

    result = dao.get_by_workspace(db, workspace_id=w1.id, transaction_type="pending_")

    # Then 1
    assert result == []


# [claude] ATL-G-72
def test_atl_g_72__attachment_id_keeps_the_higher_attachment_s_entries_an_entry_of_the_lo(db, w1, at2, mk_entry):
    """ATL-G-72 — attachment_id keeps the higher attachment's entries; an entry of the lower attachment is not returned.
    Rules: `get_by_workspace` R2"""
    a = mk_entry(performed_at=H11, attachment_id=at2.id)
    mk_entry(performed_at=H12)

    result = dao.get_by_workspace(db, workspace_id=w1.id, attachment_id=at2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ATL-G-73
def test_atl_g_73__writes_nothing_an_unflushed_edit_of_another_row_stays_unflushed_and_is(db, w1, mk_entry):
    """ATL-G-73 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded.
    Rules: `get_by_workspace` Side effects"""
    a = mk_entry(performed_at=H10)
    b = mk_entry(performed_at=H11)
    b.file_name = "edited.png"

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert b.file_name == "edited.png"
