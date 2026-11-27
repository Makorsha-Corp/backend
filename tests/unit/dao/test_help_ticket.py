"""Unit tests for app/dao/help_ticket.py.

Implements tests/unit/dao/help_ticket.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Only the clock of the `CW` cards
is patched (Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes for the clock)
import uuid
from contextlib import contextmanager
from datetime import datetime
from unittest import mock

import pydantic
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.help_ticket import help_ticket_dao
from app.models.help_ticket import HelpTicket
from app.schemas.help_ticket import HelpTicketCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton"
dao = help_ticket_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

BUG_1441 = "BUG-1441: A help ticket number's year comes from the server's local clock"
BUG_1442 = "BUG-1442: Help tickets of one creation time come back in no fixed order"
BUG_1443 = "BUG-1443: `%` and `_` in the support inbox search match every ticket"


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

# Convention "TAG = uuid.uuid4().hex[:8], made once at the start of each test"
@pytest.fixture
def TAG():
    return uuid.uuid4().hex[:8]


# Convention "W1 = make_workspace(name=f"Gamma {TAG}"), W2 = make_workspace(name=f"Delta {TAG}")"
@pytest.fixture
def w1(db, TAG):
    return make_workspace(db, name=f"Gamma {TAG}")


@pytest.fixture
def w2(db, w1, TAG):
    return make_workspace(db, name=f"Delta {TAG}")


# Convention "U1 = make_profile(name="Rahim"), U2 = make_profile(name="Karim")"
@pytest.fixture
def u1(db, w2):
    return make_profile(db, name="Rahim")


@pytest.fixture
def u2(db, u1):
    return make_profile(db, name="Karim")


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders and Given steps
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


def _ticket_fields(w1, u1, ticket_number, columns):
    fields = {"workspace_id": w1.id, "ticket_number": ticket_number, "title": "Printer jam",
              "description": "It jams", "created_by": u1.id}
    fields.update(columns)
    return fields


# Convention "ticket": status and type left to their model defaults "pending" and "support"
@pytest.fixture
def mk_ticket(db, w1, u1):
    """mk_ticket(ticket_number, **columns) -> HelpTicket, flushed."""
    def _mk(ticket_number, **columns):
        return _add(db, HelpTicket(**_ticket_fields(w1, u1, ticket_number, columns)))
    return _mk


# The "N tickets E1 ... EN, built with add_all and flushed" Givens
@pytest.fixture
def mk_many_tickets(db, w1, u1):
    """mk_many_tickets(count) -> [E1, ... Ecount], Ek numbered f"HELP-2026-{k:03d}"."""
    def _mk(count):
        rows = [HelpTicket(**_ticket_fields(w1, u1, f"HELP-2026-{k:03d}", {})) for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# Convention "newer(X, h)"
def newer(db, row, h):
    db.execute(text("UPDATE help_tickets SET created_at = now() + make_interval(hours => :h) WHERE id = :i"),
               {"h": h, "i": row.id})
    db.expire_all()


# Convention "bumpT(X)"
def bump_t(db, row):
    db.execute(text("UPDATE help_tickets SET title = title WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "clock(L, U)": datetime.now() of the module returns L; utcnow returns U
@contextmanager
def clock(local, utc):
    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return local

    with mock.patch("app.dao.help_ticket.datetime", _Clock, create=True), \
            mock.patch("app.dao.help_ticket.utcnow", create=True, return_value=utc), \
            mock.patch("app.utils.time.utcnow", return_value=utc):
        yield


# Convention "A CW card without a clock line runs under clock(datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0))"
def default_clock():
    return clock(datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)"
def ids(result):
    return [r.id for r in result]


# Convention "tids(result)" (platform tuples)
def tids(result):
    return [r[0].id for r in result]


# Convention "own(result)": the result's tickets that the card's Given made (OWN), in the order returned
def own(result, own_ids):
    return [r[0].id for r in result if r[0].id in own_ids]


# Convention "re-read X"
def reread(db, row_id):
    db.expire_all()
    return db.execute(select(HelpTicket).where(HelpTicket.id == row_id)).scalar_one_or_none()


# Convention "NOW_DB"
def now_db(db):
    return db.scalar(text("SELECT now()"))


# Convention "w1_count"
def w1_count(db, w1):
    return db.scalar(text("SELECT count(*) FROM help_tickets WHERE workspace_id = :w"), {"w": w1.id})


# Convention "nothing written": the numbers of help_tickets rows of W1 and of W2
def ws_counts(db, w1, w2):
    def count(ws):
        return db.scalar(select(func.count()).select_from(HelpTicket.__table__)
                         .where(HelpTicket.__table__.c.workspace_id == ws.id))
    return (count(w1), count(w2))


# Convention "Statement recorder"
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
        """The one SELECT from help_tickets; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "help_tickets" in s]
        return statement


# Convention "order_part"
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# Convention "NoType": an input object with no `type` field
class NoType(pydantic.BaseModel):
    title: str
    description: str
    category: str | None = None


# Convention "WithStatus": an input object that carries a `status` field
class WithStatus(pydantic.BaseModel):
    title: str
    description: str
    category: str | None = None
    status: str


def new_pending(db, w1, u1, ticket_number):
    """The Given lines `P = HelpTicket(...)` and `db.add(P)` (not flushed)."""
    p = HelpTicket(workspace_id=w1.id, ticket_number=ticket_number, title="Printer jam", description="It jams",
                   created_by=u1.id)
    db.add(p)
    return p


# --------------------------------------------------------------------------- #
# DAOHelpTicket.generate_ticket_number
# --------------------------------------------------------------------------- #


# [claude] HLP-GN-01
def test_hlp_gn_01__no_ticket_yet_gives_help_2026_001(db, w1):
    """HLP-GN-01 — no ticket yet gives HELP-2026-001.
    Rules: `generate_ticket_number` R1, Returns"""
    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "HELP-2026-001"


# [claude] HLP-GN-02
def test_hlp_gn_02__two_tickets_give_help_2026_003(db, w1, mk_ticket):
    """HLP-GN-02 — two tickets give HELP-2026-003.
    Rules: `generate_ticket_number` R1"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-003"


# [claude] HLP-GN-03
def test_hlp_gn_03__999_tickets_give_help_2026_1000(db, w1, mk_many_tickets):
    """HLP-GN-03 — 999 tickets give HELP-2026-1000.
    Rules: `generate_ticket_number` R1"""
    mk_many_tickets(999)

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-1000"


# [claude] HLP-GN-04
def test_hlp_gn_04__another_workspace_s_tickets_do_not_count(db, w1, w2, mk_ticket):
    """HLP-GN-04 — another workspace's tickets do not count.
    Rules: `generate_ticket_number` R2"""
    mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-002", workspace_id=w2.id)

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-001"


# [claude] HLP-GN-05
def test_hlp_gn_05__another_year_s_tickets_do_not_count(db, w1, mk_ticket):
    """HLP-GN-05 — another year's tickets do not count.
    Rules: `generate_ticket_number` R2"""
    mk_ticket("HELP-2025-001")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-001"


# [claude] HLP-GN-06
def test_hlp_gn_06__year_1_is_used_as_given_and_help_10_does_not_count_for_it(db, w1, mk_ticket):
    """HLP-GN-06 — year 1 is used as given, and "HELP-10-" does not count for it.
    Rules: `generate_ticket_number` R2"""
    mk_ticket("HELP-10-001")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=1)

    # Then 1
    assert result == "HELP-1-001"


# [claude] HLP-GN-07
def test_hlp_gn_07__a_number_changed_to_009_still_counts_as_one(db, w1, mk_ticket):
    """HLP-GN-07 — a number changed to 009 still counts as one.
    Rules: `generate_ticket_number` R3"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-009")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-003"


# [claude] HLP-GN-08
def test_hlp_gn_08__a_non_numeric_suffix_counts(db, w1, mk_ticket):
    """HLP-GN-08 — a non-numeric suffix counts.
    Rules: `generate_ticket_number` R3"""
    mk_ticket("HELP-2026-ABC")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-002"


# [claude] HLP-GN-09
def test_hlp_gn_09__only_numbers_that_start_with_the_prefix_count(db, w1, mk_ticket):
    """HLP-GN-09 — only numbers that start with the prefix count.
    Rules: `generate_ticket_number` R1"""
    mk_ticket("XHELP-2026-001")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-001"


# [claude] HLP-GN-10
def test_hlp_gn_10__writes_nothing_a_pending_ticket_stays_pending_and_is_not_counted_an_unflushed_edit(
        db, w1, w2, u1, mk_ticket):
    """HLP-GN-10 — writes nothing: a pending ticket stays pending and is not counted, an unflushed edit stays unflushed.
    Rules: `generate_ticket_number` Side effects"""
    b = mk_ticket("HELP-2025-001")
    b.title = "Edited"
    p = HelpTicket(workspace_id=w1.id, ticket_number="HELP-2026-001", title="Printer jam", description="It jams",
                   created_by=u1.id)
    db.add(p)
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-001"
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
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-GN-11
def test_hlp_gn_11__asked_for_w2_the_earlier_w1_ticket_does_not_count(db, w2, mk_ticket):
    """HLP-GN-11 — asked for W2, the earlier W1 ticket does not count.
    Rules: `generate_ticket_number` R2"""
    mk_ticket("HELP-2026-001")

    result = dao.generate_ticket_number(db, workspace_id=w2.id, year=2026)

    # Then 1
    assert result == "HELP-2026-001"


# [claude] HLP-GN-12
def test_hlp_gn_12__every_status_and_both_types_count_in_one_sequence(db, w1, mk_ticket):
    """HLP-GN-12 — every status and both types count, in one sequence.
    Rules: `generate_ticket_number` R2a"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002", status="opened", type="feedback")
    mk_ticket("HELP-2026-003", status="closed", type="feedback")
    mk_ticket("HELP-2026-004", status="closed")

    result = dao.generate_ticket_number(db, workspace_id=w1.id, year=2026)

    # Then 1
    assert result == "HELP-2026-005"


# --------------------------------------------------------------------------- #
# DAOHelpTicket.create_with_user
# --------------------------------------------------------------------------- #


# [claude] HLP-CW-01
def test_hlp_cw_01__a_ticket_is_opened_with_the_schema_s_fields_the_next_number_status_pending_and_type_support(
        db, w1, u1):
    """HLP-CW-01 — a ticket is opened with the schema's fields, the next number, status pending and type support.
    Rules: `create_with_user` R1, R1a, R1b, Returns, Side effects"""
    with default_clock():
        result = dao.create_with_user(
            db, obj_in=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"),
            workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert isinstance(result, HelpTicket)
    # Then 2
    assert result.id is not None
    # Then 3
    assert type(result.status) is str
    assert result.status == "pending"
    # Then 4
    assert type(result.type) is str
    assert result.type == "support"
    # Then 5
    row = reread(db, result.id)
    assert row.ticket_number == "HELP-2026-001"
    assert row.status == "pending"
    assert row.type == "support"
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 6
    row = reread(db, result.id)
    assert type(row.status) is str
    assert type(row.type) is str
    # Then 7
    row = reread(db, result.id)
    assert row.title == "Printer jam"
    assert row.description == "It jams"
    assert row.category == "hardware"
    # Then 8
    row = reread(db, result.id)
    assert row.closed_at is None
    assert row.closed_by is None
    # Then 9
    row = reread(db, result.id)
    assert row.created_at == now_db(db)
    assert row.updated_at == now_db(db)
    # Then 10
    assert w1_count(db, w1) == 1


# [claude] HLP-CW-02
def test_hlp_cw_02__the_second_ticket_gets_the_next_number(db, w1, u2, mk_ticket):
    """HLP-CW-02 — the second ticket gets the next number.
    Rules: `create_with_user` R1"""
    mk_ticket("HELP-2026-001")

    with default_clock():
        result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"),
                                      workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ticket_number == "HELP-2026-002"
    assert row.created_by == u2.id


# [claude] HLP-CW-03
@pytest.mark.xfail(strict=True, reason=BUG_1441)
def test_hlp_cw_03__the_year_comes_from_utc_not_the_server_s_local_clock(db, w1, u1):
    """HLP-CW-03 — the year comes from UTC, not the server's local clock.
    Rules: `create_with_user` R2 [BUG-1441]"""
    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Printer jam", description="It jams"),
                                      workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ticket_number == "HELP-2026-001"


# [claude] HLP-CW-04
def test_hlp_cw_04__a_computed_number_already_taken_fails_at_the_flush_and_saves_nothing(db, w1, u1, mk_ticket):
    """HLP-CW-04 — a computed number already taken fails at the flush and saves nothing.
    Rules: `create_with_user` R4, Errors"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002")
    mk_ticket("HELP-2026-004")

    with default_clock():
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"),
                                     workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert "uq_help_tickets_workspace_number" in str(exc.value.orig)
    # Then 3
    assert w1_count(db, w1) == 3


# [claude] HLP-CW-05
def test_hlp_cw_05__an_unknown_user_raises_integrityerror_23503(db, w1, w2):
    """HLP-CW-05 — an unknown user raises IntegrityError 23503.
    Rules: `create_with_user` R5, Errors"""
    before = ws_counts(db, w1, w2)

    with default_clock():
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"),
                                     workspace_id=w1.id, user_id=MISSING)

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-CW-06
def test_hlp_cw_06__an_unknown_workspace_raises_integrityerror_23503(db, w1, w2, u1):
    """HLP-CW-06 — an unknown workspace raises IntegrityError 23503.
    Rules: `create_with_user` R5, Errors"""
    before = ws_counts(db, w1, w2)

    with default_clock():
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"),
                                     workspace_id=MISSING, user_id=u1.id)

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-CW-07
def test_hlp_cw_07__values_are_stored_as_the_schema_gives_them_untrimmed(db, w1, u1):
    """HLP-CW-07 — values are stored as the schema gives them, untrimmed.
    Rules: `create_with_user` R5"""
    with default_clock():
        result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="  Jam  ", description=" It jams "),
                                      workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.title == "  Jam  "
    assert row.description == " It jams "


# [claude] HLP-CW-08
def test_hlp_cw_08__flushed_not_committed_a_rollback_removes_the_ticket(db, w1, u1):
    """HLP-CW-08 — flushed, not committed: a rollback removes the ticket.
    Rules: `create_with_user` R1, Side effects"""
    with mock.patch.object(db, "commit", wraps=db.commit) as commit_spy:
        with default_clock():
            sp = db.begin_nested()
            result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"),
                                          workspace_id=w1.id, user_id=u1.id)

        # Then 1
        assert result.id is not None
        # Then 2
        assert w1_count(db, w1) == 1
        # Then 3
        sp.rollback()
        assert w1_count(db, w1) == 0
        # Then 4
        assert commit_spy.call_count == 0


# [claude] HLP-CW-09
def test_hlp_cw_09__type_feedback_from_the_schema_is_stored_as_the_plain_string_feedback(db, w1, u1):
    """HLP-CW-09 — type "feedback" from the schema is stored as the plain string "feedback".
    Rules: `create_with_user` R1a, R1b"""
    with default_clock():
        result = dao.create_with_user(
            db, obj_in=HelpTicketCreate(title="Idea", description="Add dark mode", type="feedback"),
            workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert type(result.type) is str
    assert result.type == "feedback"
    # Then 3
    assert type(result.status) is str
    assert result.status == "pending"
    # Then 4
    row = reread(db, result.id)
    assert row.type == "feedback"
    assert row.status == "pending"
    assert row.ticket_number == "HELP-2026-001"
    # Then 5
    row = reread(db, result.id)
    assert type(row.type) is str
    # Then 6
    assert db.scalar(text("SELECT count(*) FROM help_tickets WHERE workspace_id = :w AND type = 'feedback'"),
                     {"w": w1.id}) == 1


# [claude] HLP-CW-10
def test_hlp_cw_10__a_type_that_is_already_a_plain_string_is_stored_as_given(db, w1, u1):
    """HLP-CW-10 — a type that is already a plain string is stored as given.
    Rules: `create_with_user` R1a, R1b"""
    with default_clock():
        result = dao.create_with_user(
            db, obj_in=HelpTicketCreate.model_construct(title="Idea", description="Add dark mode", category=None,
                                                        type="feedback"),
            workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert type(result.type) is str
    assert result.type == "feedback"
    # Then 3
    row = reread(db, result.id)
    assert row.type == "feedback"
    assert row.status == "pending"
    assert row.title == "Idea"


# [claude] HLP-CW-11
def test_hlp_cw_11__an_input_object_with_no_type_field_gives_type_support(db, w1, u1):
    """HLP-CW-11 — an input object with no type field gives type "support".
    Rules: `create_with_user` R1a"""
    with default_clock():
        result = dao.create_with_user(db, obj_in=NoType(title="Leak", description="Drips"),
                                      workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.type == "support"
    # Then 3
    row = reread(db, result.id)
    assert row.type == "support"
    assert row.status == "pending"
    assert row.title == "Leak"
    assert row.description == "Drips"
    assert row.category is None


# [claude] HLP-CW-12
def test_hlp_cw_12__a_type_of_17_characters_fails_at_the_flush_with_dataerror_22001_and_saves_nothing(
        db, w1, w2, u1):
    """HLP-CW-12 — a type of 17 characters fails at the flush with DataError 22001 and saves nothing.
    Rules: `create_with_user` R1c, Errors"""
    before = ws_counts(db, w1, w2)

    with default_clock():
        with pytest.raises(DataError) as exc:
            with db.begin_nested():
                dao.create_with_user(
                    db, obj_in=HelpTicketCreate.model_construct(title="Idea", description="Add dark mode",
                                                                category=None, type="f" * 17),
                    workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert ws_counts(db, w1, w2) == before
    # Then 3
    assert w1_count(db, w1) == 0


# [claude] HLP-CW-13
def test_hlp_cw_13__a_type_of_exactly_16_characters_is_stored(db, w1, u1):
    """HLP-CW-13 — a type of exactly 16 characters is stored.
    Rules: `create_with_user` R1c, R1a"""
    with default_clock():
        result = dao.create_with_user(
            db, obj_in=HelpTicketCreate.model_construct(title="Idea", description="Add dark mode", category=None,
                                                        type="f" * 16),
            workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.type == "ffffffffffffffff"
    # Then 3
    assert w1_count(db, w1) == 1


# [claude] HLP-CW-14
def test_hlp_cw_14__a_non_schema_input_carrying_a_status_raises_typeerror_and_inserts_nothing(db, w1, w2, u1):
    """HLP-CW-14 — a non-schema input carrying a status raises TypeError and inserts nothing.
    Rules: `create_with_user` R1d"""
    before = ws_counts(db, w1, w2)

    with default_clock():
        with StatementRecorder(db) as recorder:
            with pytest.raises(TypeError) as exc:
                dao.create_with_user(db, obj_in=WithStatus(title="Leak", description="Drips", status="closed"),
                                     workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert "multiple values for keyword argument 'status'" in str(exc.value)
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert [s for s in recorder.written() if s.lstrip().upper().startswith("INSERT")] == []
    # Then 4
    assert ws_counts(db, w1, w2) == before
    # Then 5
    assert w1_count(db, w1) == 0


# [claude] HLP-CW-15
def test_hlp_cw_15__helpticketcreate_model_construct_drops_a_status_so_the_ticket_is_pending(db, w1, u1):
    """HLP-CW-15 — HelpTicketCreate.model_construct drops a status, so the ticket is pending.
    Rules: `create_with_user` R1d, R1"""
    with default_clock():
        result = dao.create_with_user(
            db, obj_in=HelpTicketCreate.model_construct(title="Idea", description="Add dark mode", category=None,
                                                        type="feedback", status="closed"),
            workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert result.status == "pending"
    # Then 3
    row = reread(db, result.id)
    assert row.status == "pending"
    assert row.type == "feedback"
    assert row.ticket_number == "HELP-2026-001"
    # Then 4
    assert w1_count(db, w1) == 1


# --------------------------------------------------------------------------- #
# DAOHelpTicket.get_by_id
# --------------------------------------------------------------------------- #


# [claude] HLP-GB-01
def test_hlp_gb_01__returns_the_ticket_with_its_creator_in_one_query(db, u1, mk_ticket):
    """HLP-GB-01 — returns the ticket with its creator, in one query.
    Rules: `get_by_id` R1, Returns"""
    a = mk_ticket("HELP-2026-001")
    a_id = a.id  # read before expire_all(): an expired id would reload inside the recorder
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id(db, ticket_id=a_id)

    # Then 1
    assert isinstance(result, HelpTicket)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert "creator" not in sa_inspect(result).unloaded
    # Then 4
    assert len(recorder.selects()) == 1
    # Then 5
    assert result.creator.id == u1.id


# [claude] HLP-GB-02
def test_hlp_gb_02__a_ticket_of_another_workspace_is_returned(db, w2, mk_ticket):
    """HLP-GB-02 — a ticket of another workspace is returned.
    Rules: `get_by_id` R1"""
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)

    result = dao.get_by_id(db, ticket_id=z.id)

    # Then 1
    assert result.id == z.id


# [claude] HLP-GB-03
def test_hlp_gb_03__an_unknown_id_returns_none(db, mk_ticket):
    """HLP-GB-03 — an unknown id returns None.
    Rules: `get_by_id` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_by_id(db, ticket_id=MISSING)

    # Then 1
    assert result is None


# [claude] HLP-GB-04
def test_hlp_gb_04__id_0_returns_none(db, mk_ticket):
    """HLP-GB-04 — id 0 returns None.
    Rules: `get_by_id` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_by_id(db, ticket_id=0)

    # Then 1
    assert result is None


# [claude] HLP-GB-05
def test_hlp_gb_05__writes_nothing_a_pending_ticket_stays_pending_an_unflushed_edit_stays_unflushed(
        db, w1, w2, u1, mk_ticket):
    """HLP-GB-05 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_id` Side effects"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    b.title = "Edited"
    p = new_pending(db, w1, u1, "HELP-2026-003")
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id(db, ticket_id=a.id)

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
    assert recorder.written() == []
    # Then 7
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-GB-06
def test_hlp_gb_06__a_ticket_without_a_creator_is_returned_with_creator_none(db, mk_ticket):
    """HLP-GB-06 — a ticket without a creator is returned, with creator None.
    Rules: `get_by_id` R1"""
    a = mk_ticket("HELP-2026-001", created_by=None)

    result = dao.get_by_id(db, ticket_id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.creator is None


# --------------------------------------------------------------------------- #
# DAOHelpTicket.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] HLP-GW-01
def test_hlp_gw_01__returns_the_ticket_with_its_creator_in_one_statement_with_a_left_outer_join(db, w1, mk_ticket):
    """HLP-GW-01 — returns the ticket with its creator, in one statement with a LEFT OUTER JOIN.
    Rules: `get_by_id_and_workspace` R1, R2, Returns"""
    a = mk_ticket("HELP-2026-001")
    a_id, w1_id = a.id, w1.id  # read before expire_all(): an expired id would reload inside the recorder
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a_id, workspace_id=w1_id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert "creator" not in sa_inspect(result).unloaded
    # Then 3
    assert len(recorder.selects()) == 1
    # Then 4
    assert "LEFT OUTER JOIN" in recorder.sql().upper()
    # Then 5
    assert "profiles" in recorder.sql()


# [claude] HLP-GW-02
def test_hlp_gw_02__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_ticket):
    """HLP-GW-02 — another workspace's id returns None, when that row is the earlier one.
    Rules: `get_by_id_and_workspace` R1"""
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    mk_ticket("HELP-2026-001")

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] HLP-GW-03
def test_hlp_gw_03__another_workspace_s_id_returns_none_when_that_row_is_the_later_one(db, w1, w2, mk_ticket):
    """HLP-GW-03 — another workspace's id returns None, when that row is the later one.
    Rules: `get_by_id_and_workspace` R1"""
    mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] HLP-GW-04
def test_hlp_gw_04__the_id_under_another_workspace_returns_none(db, w2, mk_ticket):
    """HLP-GW-04 — the id under another workspace returns None.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk_ticket("HELP-2026-001")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] HLP-GW-05
def test_hlp_gw_05__an_unknown_id_returns_none(db, w1, mk_ticket):
    """HLP-GW-05 — an unknown id returns None.
    Rules: `get_by_id_and_workspace` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] HLP-GW-06
def test_hlp_gw_06__id_0_returns_none(db, w1, mk_ticket):
    """HLP-GW-06 — id 0 returns None.
    Rules: `get_by_id_and_workspace` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] HLP-GW-07
def test_hlp_gw_07__a_ticket_without_a_creator_is_returned_with_creator_none(db, w1, mk_ticket):
    """HLP-GW-07 — a ticket without a creator is returned with creator None.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_ticket("HELP-2026-001", created_by=None)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.creator is None


# [claude] HLP-GW-08
def test_hlp_gw_08__writes_nothing_a_pending_ticket_stays_pending_an_unflushed_edit_stays_unflushed(
        db, w1, w2, u1, mk_ticket):
    """HLP-GW-08 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_id_and_workspace` Side effects"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    b.title = "Edited"
    p = new_pending(db, w1, u1, "HELP-2026-003")
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

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
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert ws_counts(db, w1, w2) == before


# --------------------------------------------------------------------------- #
# DAOHelpTicket.list_by_workspace
# --------------------------------------------------------------------------- #


# [claude] HLP-LW-01
def test_hlp_lw_01__returns_a_list_of_the_workspace_s_tickets(db, w1, mk_ticket):
    """HLP-LW-01 — returns a list of the workspace's tickets.
    Rules: `list_by_workspace` R1, Returns"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {a.id, b.id}
    # Then 3
    assert isinstance(result[0], HelpTicket)


# [claude] HLP-LW-02
def test_hlp_lw_02__a_newer_ticket_of_another_workspace_is_not_returned(db, w1, w2, mk_ticket):
    """HLP-LW-02 — a newer ticket of another workspace is not returned.
    Rules: `list_by_workspace` R1"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    newer(db, z, 1)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] HLP-LW-03
def test_hlp_lw_03__status_closed_keeps_the_closed_tickets_only(db, w1, mk_ticket):
    """HLP-LW-03 — status "closed" keeps the closed tickets only.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001")
    c = mk_ticket("HELP-2026-002", status="closed")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="closed")

    # Then 1
    assert ids(result) == [c.id]


# [claude] HLP-LW-04
def test_hlp_lw_04__status_keeps_none(db, w1, mk_ticket):
    """HLP-LW-04 — status "" keeps none.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="")

    # Then 1
    assert result == []


# [claude] HLP-LW-05
def test_hlp_lw_05__status_pending_in_capitals_keeps_none(db, w1, mk_ticket):
    """HLP-LW-05 — status "PENDING" in capitals keeps none.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="PENDING")

    # Then 1
    assert result == []


# [claude] HLP-LW-06
def test_hlp_lw_06__created_by_keeps_that_creator_s_tickets_only(db, w1, u2, mk_ticket):
    """HLP-LW-06 — created_by keeps that creator's tickets only.
    Rules: `list_by_workspace` R3"""
    mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002", created_by=u2.id)

    result = dao.list_by_workspace(db, workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] HLP-LW-07
def test_hlp_lw_07__created_by_0_is_a_filter_and_keeps_none(db, w1, mk_ticket):
    """HLP-LW-07 — created_by=0 is a filter and keeps none.
    Rules: `list_by_workspace` R3"""
    mk_ticket("HELP-2026-001")

    result = dao.list_by_workspace(db, workspace_id=w1.id, created_by=0)

    # Then 1
    assert result == []


# [claude] HLP-LW-08
def test_hlp_lw_08__status_and_created_by_combine_with_and(db, w1, u2, mk_ticket):
    """HLP-LW-08 — status and created_by combine with AND.
    Rules: `list_by_workspace` R3"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002", status="closed")
    mk_ticket("HELP-2026-003", created_by=u2.id)
    d = mk_ticket("HELP-2026-004", status="closed", created_by=u2.id)

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="closed", created_by=u2.id)

    # Then 1
    assert ids(result) == [d.id]


# [claude] HLP-LW-09
def test_hlp_lw_09__with_the_defaults_101_tickets_give_100(db, w1, mk_many_tickets):
    """HLP-LW-09 — with the defaults 101 tickets give 100.
    Rules: `list_by_workspace` R4"""
    mk_many_tickets(101)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] HLP-LW-10
def test_hlp_lw_10__limit_1000_gives_all_101(db, w1, mk_many_tickets):
    """HLP-LW-10 — limit=1000 gives all 101.
    Rules: `list_by_workspace` R4"""
    rows = mk_many_tickets(101)
    all_ids = {row.id for row in rows}

    result = dao.list_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] HLP-LW-11
def test_hlp_lw_11__limit_0_returns_an_empty_list(db, w1, mk_ticket):
    """HLP-LW-11 — limit=0 returns an empty list.
    Rules: `list_by_workspace` R4"""
    mk_ticket("HELP-2026-001")

    result = dao.list_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] HLP-LW-12
def test_hlp_lw_12__skip_past_the_end_returns_an_empty_list(db, w1, mk_ticket):
    """HLP-LW-12 — skip past the end returns an empty list.
    Rules: `list_by_workspace` R4"""
    mk_ticket("HELP-2026-001")

    result = dao.list_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert result == []


# [claude] HLP-LW-13
def test_hlp_lw_13__a_negative_limit_raises_dataerror(db, w1, w2, mk_ticket):
    """HLP-LW-13 — a negative limit raises DataError.
    Rules: `list_by_workspace` R4, Errors"""
    mk_ticket("HELP-2026-001")
    before = ws_counts(db, w1, w2)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_by_workspace(db, workspace_id=w1.id, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LW-14
def test_hlp_lw_14__a_negative_skip_raises_dataerror(db, w1, w2, mk_ticket):
    """HLP-LW-14 — a negative skip raises DataError.
    Rules: `list_by_workspace` R4, Errors"""
    mk_ticket("HELP-2026-001")
    before = ws_counts(db, w1, w2)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_by_workspace(db, workspace_id=w1.id, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LW-15
def test_hlp_lw_15__newest_first_whatever_the_ids(db, w1, mk_ticket):
    """HLP-LW-15 — newest first, whatever the ids.
    Rules: `list_by_workspace` R5"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    c = mk_ticket("HELP-2026-003")
    newer(db, b, 2)
    newer(db, c, 1)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] HLP-LW-16
def test_hlp_lw_16__on_a_tie_both_tickets_sit_between_the_newer_and_the_older_one(db, w1, mk_ticket):
    """HLP-LW-16 — on a tie both tickets sit between the newer and the older one.
    Rules: `list_by_workspace` R5"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    c = mk_ticket("HELP-2026-003")
    d = mk_ticket("HELP-2026-004")
    newer(db, c, 1)
    newer(db, d, -1)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert set(ids(result)[1:3]) == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] HLP-LW-17
@pytest.mark.xfail(strict=False, reason=BUG_1442)
def test_hlp_lw_17__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, w1, mk_ticket):
    """HLP-LW-17 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `list_by_workspace` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    c = mk_ticket("HELP-2026-003")
    d = mk_ticket("HELP-2026-004")
    newer(db, d, 1)
    seqscan(db)
    bump_t(db, a)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] HLP-LW-18
@pytest.mark.xfail(strict=True, reason=BUG_1442)
def test_hlp_lw_18__the_query_orders_by_created_at_then_id_both_descending(db, w1, mk_ticket):
    """HLP-LW-18 — the query orders by created_at, then id, both descending.
    Rules: `list_by_workspace` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001")

    with StatementRecorder(db) as recorder:
        result = dao.list_by_workspace(db, workspace_id=w1.id)

    order_part = order_part_of(recorder.sql())
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "created_at" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 5
    assert order_part.upper().count("DESC") == 2


# [claude] HLP-LW-19
def test_hlp_lw_19__the_status_filter_comes_before_the_page_a_newer_closed_ticket_takes_no_place(db, w1, mk_ticket):
    """HLP-LW-19 — the status filter comes before the page: a newer closed ticket takes no place.
    Rules: `list_by_workspace` R2, R5"""
    x = mk_ticket("HELP-2026-001", status="closed")
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="pending", skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] HLP-LW-20
def test_hlp_lw_20__the_creator_filter_comes_before_the_page_a_newer_ticket_of_another_creator_takes_no_place(
        db, w1, u1, u2, mk_ticket):
    """HLP-LW-20 — the creator filter comes before the page: a newer ticket of another creator takes no place.
    Rules: `list_by_workspace` R3, R5"""
    x = mk_ticket("HELP-2026-001", created_by=u2.id)
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_by_workspace(db, workspace_id=w1.id, created_by=u1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] HLP-LW-21
def test_hlp_lw_21__each_ticket_s_creator_is_loaded_in_the_same_query(db, w1, mk_ticket):
    """HLP-LW-21 — each ticket's creator is loaded in the same query.
    Rules: `list_by_workspace` R6"""
    a = mk_ticket("HELP-2026-001")
    w1_id = w1.id  # read before expire_all(): an expired id would reload inside the recorder
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.list_by_workspace(db, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "creator" not in sa_inspect(result[0]).unloaded
    # Then 3
    assert len(recorder.selects()) == 1
    # Then 4
    assert "profiles" in recorder.sql()


# [claude] HLP-LW-22
def test_hlp_lw_22__writes_nothing_a_pending_ticket_stays_pending_an_unflushed_edit_stays_unflushed(
        db, w1, w2, u1, mk_ticket):
    """HLP-LW-22 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed.
    Rules: `list_by_workspace` Side effects"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    b.title = "Edited"
    p = new_pending(db, w1, u1, "HELP-2026-003")
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.list_by_workspace(db, workspace_id=w1.id)

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
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LW-23
def test_hlp_lw_23__in_the_status_is_no_wildcard(db, w1, mk_ticket):
    """HLP-LW-23 — _ in the status is no wildcard.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001", status="closed")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="clos_d")

    # Then 1
    assert result == []


# [claude] HLP-LW-24
def test_hlp_lw_24__a_leading_space_in_the_status_keeps_none(db, w1, mk_ticket):
    """HLP-LW-24 — a leading space in the status keeps none.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001", status="closed")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status=" closed")

    # Then 1
    assert result == []


# [claude] HLP-LW-25
def test_hlp_lw_25__a_stored_status_with_a_leading_space_is_not_kept(db, w1, mk_ticket):
    """HLP-LW-25 — a stored status with a leading space is not kept.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001", status=" closed")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="closed")

    # Then 1
    assert result == []


# [claude] HLP-LW-26
def test_hlp_lw_26__asked_for_w2_only_the_w2_ticket_is_returned_though_the_w1_ticket_is_earlier(db, w2, mk_ticket):
    """HLP-LW-26 — asked for W2, only the W2 ticket is returned, though the W1 ticket is earlier.
    Rules: `list_by_workspace` R1"""
    mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)

    result = dao.list_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] HLP-LW-27
@pytest.mark.xfail(strict=False, reason=BUG_1442)
def test_hlp_lw_27__on_a_tie_the_id_decides_not_the_title(db, w1, mk_ticket):
    """HLP-LW-27 — on a tie the id decides, not the title.
    Rules: `list_by_workspace` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001", title="Alpha")
    b = mk_ticket("HELP-2026-002", title="Bravo")
    c = mk_ticket("HELP-2026-003", title="Charlie")
    d = mk_ticket("HELP-2026-004", title="Delta")
    newer(db, d, 1)
    seqscan(db)
    bump_t(db, a)

    result = dao.list_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] HLP-LW-28
def test_hlp_lw_28__the_retired_status_open_keeps_none_not_even_an_opened_ticket(db, w1, mk_ticket):
    """HLP-LW-28 — the retired status "open" keeps none, not even an "opened" ticket.
    Rules: `list_by_workspace` R2"""
    mk_ticket("HELP-2026-001", status="opened")
    mk_ticket("HELP-2026-002")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="open")

    # Then 1
    assert result == []


# [claude] HLP-LW-29
def test_hlp_lw_29__ticket_type_feedback_keeps_the_feedback_tickets_only(db, w1, mk_ticket):
    """HLP-LW-29 — ticket_type "feedback" keeps the feedback tickets only.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001")
    f = mk_ticket("HELP-2026-002", type="feedback")
    mk_ticket("HELP-2026-003")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="feedback")

    # Then 1
    assert ids(result) == [f.id]


# [claude] HLP-LW-30
def test_hlp_lw_30__ticket_type_none_keeps_both_types(db, w1, mk_ticket):
    """HLP-LW-30 — ticket_type None keeps both types.
    Rules: `list_by_workspace` R2a"""
    a = mk_ticket("HELP-2026-001")
    f = mk_ticket("HELP-2026-002", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type=None)

    # Then 1
    assert set(ids(result)) == {a.id, f.id}


# [claude] HLP-LW-31
def test_hlp_lw_31__ticket_type_is_a_filter_and_keeps_none(db, w1, mk_ticket):
    """HLP-LW-31 — ticket_type "" is a filter and keeps none.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001")
    mk_ticket("HELP-2026-002", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="")

    # Then 1
    assert result == []


# [claude] HLP-LW-32
def test_hlp_lw_32__ticket_type_feedback_with_a_capital_keeps_none(db, w1, mk_ticket):
    """HLP-LW-32 — ticket_type "Feedback" with a capital keeps none.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="Feedback")

    # Then 1
    assert result == []


# [claude] HLP-LW-33
def test_hlp_lw_33__a_part_of_a_type_feed_keeps_none(db, w1, mk_ticket):
    """HLP-LW-33 — a part of a type ("feed") keeps none.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="feed")

    # Then 1
    assert result == []


# [claude] HLP-LW-34
def test_hlp_lw_34__a_stored_type_with_a_leading_space_is_not_kept(db, w1, mk_ticket):
    """HLP-LW-34 — a stored type with a leading space is not kept.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001", type=" feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="feedback")

    # Then 1
    assert result == []


# [claude] HLP-LW-35
def test_hlp_lw_35__the_type_filter_comes_before_the_page_a_newer_feedback_ticket_takes_no_place(
        db, w1, mk_ticket):
    """HLP-LW-35 — the type filter comes before the page: a newer feedback ticket takes no place.
    Rules: `list_by_workspace` R2a, R5"""
    x = mk_ticket("HELP-2026-001", type="feedback")
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="support", skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] HLP-LW-36
def test_hlp_lw_36__status_ticket_type_and_created_by_combine_with_and(db, w1, w2, u2, mk_ticket):
    """HLP-LW-36 — status, ticket_type and created_by combine with AND.
    Rules: `list_by_workspace` R3, R2, R2a"""
    mk_ticket("HELP-2026-001", created_by=u2.id)
    mk_ticket("HELP-2026-002", type="feedback")
    mk_ticket("HELP-2026-003", status="closed", type="feedback", created_by=u2.id)
    d = mk_ticket("HELP-2026-004", type="feedback", created_by=u2.id)
    mk_ticket("HELP-2026-005", workspace_id=w2.id, type="feedback", created_by=u2.id)

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="pending", ticket_type="feedback",
                                   created_by=u2.id)

    # Then 1
    assert ids(result) == [d.id]


# [claude] HLP-LW-37
def test_hlp_lw_37__status_opened_with_ticket_type_feedback_and_no_opened_feedback_keeps_none(db, w1, mk_ticket):
    """HLP-LW-37 — status "opened" with ticket_type "feedback" and no opened feedback keeps none.
    Rules: `list_by_workspace` R3, R2, R2a"""
    mk_ticket("HELP-2026-001", status="opened")
    mk_ticket("HELP-2026-002", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, status="opened", ticket_type="feedback")

    # Then 1
    assert result == []


# [claude] HLP-LW-38
def test_hlp_lw_38___in_ticket_type_is_no_wildcard(db, w1, mk_ticket):
    """HLP-LW-38 — _ in ticket_type is no wildcard.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type="feed_ack")

    # Then 1
    assert result == []


# [claude] HLP-LW-39
def test_hlp_lw_39__a_leading_space_in_ticket_type_keeps_none(db, w1, mk_ticket):
    """HLP-LW-39 — a leading space in ticket_type keeps none.
    Rules: `list_by_workspace` R2a"""
    mk_ticket("HELP-2026-001", type="feedback")

    result = dao.list_by_workspace(db, workspace_id=w1.id, ticket_type=" feedback")

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# DAOHelpTicket.list_platform
# --------------------------------------------------------------------------- #


# [claude] HLP-LP-01
def test_hlp_lp_01__every_workspace_s_tickets_come_back_as_ticket_workspace_name_creator_name(
        db, w2, u2, TAG, mk_ticket):
    """HLP-LP-01 — every workspace's tickets come back as (ticket, workspace name, creator name).
    Rules: `list_platform` R1, Returns"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=u2.id)
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(own(result, own_ids)) == {a.id, z.id}
    # Then 3
    assert [tuple(r[1:]) for r in result if r[0].id == a.id] == [(f"Gamma {TAG}", "Rahim")]
    # Then 4
    assert [tuple(r[1:]) for r in result if r[0].id == z.id] == [(f"Delta {TAG}", "Karim")]


# [claude] HLP-LP-02
def test_hlp_lp_02__a_ticket_without_a_creator_has_creator_name_none(db, TAG, mk_ticket):
    """HLP-LP-02 — a ticket without a creator has creator name None.
    Rules: `list_platform` Returns"""
    a = mk_ticket("HELP-2026-001", created_by=None)
    own_ids = {a.id}

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert own(result, own_ids) == [a.id]
    # Then 2
    assert result[0][2] is None


# [claude] HLP-LP-03
def test_hlp_lp_03__status_keeps_exactly_that_status(db, TAG, mk_ticket):
    """HLP-LP-03 — status keeps exactly that status.
    Rules: `list_platform` R2"""
    a = mk_ticket("HELP-2026-001")
    c = mk_ticket("HELP-2026-002", status="closed")
    own_ids = {a.id, c.id}

    result = dao.list_platform(db, status="closed", search=TAG)

    # Then 1
    assert own(result, own_ids) == [c.id]


# [claude] HLP-LP-04
def test_hlp_lp_04__search_none_applies_no_filter(db, w2, mk_ticket):
    """HLP-LP-04 — search None applies no filter.
    Rules: `list_platform` R3"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id, title="Leak")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=None, limit=1000)

    # Then 1
    assert set(own(result, own_ids)) == {a.id, z.id}


# [claude] HLP-LP-05
def test_hlp_lp_05__search_applies_no_filter(db, w2, mk_ticket):
    """HLP-LP-05 — search "" applies no filter.
    Rules: `list_platform` R3"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id, title="Leak")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search="", limit=1000)

    # Then 1
    assert set(own(result, own_ids)) == {a.id, z.id}


# [claude] HLP-LP-06
def test_hlp_lp_06__the_middle_of_a_workspace_name_in_capitals_finds_that_workspace_s_tickets(
        db, w2, TAG, mk_ticket):
    """HLP-LP-06 — the middle of a workspace name, in capitals, finds that workspace's tickets.
    Rules: `list_platform` R3"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"MMA {TAG.upper()}")

    # Then 1
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-07
def test_hlp_lp_07__the_middle_of_a_title_padded_with_spaces_and_in_capitals_finds_it(db, TAG, mk_ticket):
    """HLP-LP-07 — the middle of a title, padded with spaces and in capitals, finds it.
    Rules: `list_platform` R3"""
    a = mk_ticket("HELP-2026-001", title=f"Printer jam {TAG}")
    z = mk_ticket("HELP-2026-002", title=f"Leak {TAG}")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"  NTER JAM {TAG.upper()}  ")

    # Then 1
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-08
def test_hlp_lp_08__a_lowercase_part_of_a_ticket_number_finds_it(db, TAG, mk_ticket):
    """HLP-LP-08 — a lowercase part of a ticket number finds it.
    Rules: `list_platform` R3"""
    a = mk_ticket(f"HELP-2026-{TAG.upper()}")
    z = mk_ticket("HELP-2026-002")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"elp-2026-{TAG.lower()}")

    # Then 1
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-09
def test_hlp_lp_09__the_middle_of_a_description_finds_it(db, TAG, mk_ticket):
    """HLP-LP-09 — the middle of a description finds it.
    Rules: `list_platform` R3"""
    a = mk_ticket("HELP-2026-001", description=f"It jams {TAG} daily")
    z = mk_ticket("HELP-2026-002", description="Drips")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"JAMS {TAG.upper()} DA")

    # Then 1
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-10
def test_hlp_lp_10__a_search_of_only_spaces_matches_every_ticket(db, w2, mk_ticket):
    """HLP-LP-10 — a search of only spaces matches every ticket.
    Rules: `list_platform` R4"""
    a = mk_ticket("HELP-2026-001")
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id, title="Leak")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search="   ", limit=1000)

    # Then 1
    assert set(own(result, own_ids)) == {a.id, z.id}


# [claude] HLP-LP-11
@pytest.mark.xfail(strict=True, reason=BUG_1443)
def test_hlp_lp_11__in_the_search_matches_only_a_real(db, TAG, mk_ticket):
    """HLP-LP-11 — _ in the search matches only a real _.
    Rules: `list_platform` R6 [BUG-1443]"""
    a = mk_ticket("HELP-2026-001", title=f"a_b {TAG}")
    z = mk_ticket("HELP-2026-002", title=f"axb {TAG}")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"a_b {TAG}")

    # Then 1
    assert a.id in own(result, own_ids)
    # Then 2
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-12
@pytest.mark.xfail(strict=True, reason=BUG_1443)
def test_hlp_lp_12__in_the_search_matches_only_a_real(db, TAG, mk_ticket):
    """HLP-LP-12 — % in the search matches only a real %.
    Rules: `list_platform` R6 [BUG-1443]"""
    a = mk_ticket("HELP-2026-001", title=f"50% {TAG}")
    z = mk_ticket("HELP-2026-002", title=f"50 x {TAG}")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"50% {TAG}")

    # Then 1
    assert a.id in own(result, own_ids)
    # Then 2
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-13
@pytest.mark.xfail(strict=True, reason=BUG_1443)
def test_hlp_lp_13__a_backslash_in_the_search_matches_only_a_real_backslash(db, TAG, mk_ticket):
    """HLP-LP-13 — a backslash in the search matches only a real backslash.
    Rules: `list_platform` R6 [BUG-1443]"""
    a = mk_ticket("HELP-2026-001", title=f"a\\b {TAG}")
    z = mk_ticket("HELP-2026-002", title=f"ab {TAG}")
    own_ids = {a.id, z.id}

    result = dao.list_platform(db, search=f"a\\b {TAG}")

    # Then 1
    assert own(result, own_ids) == [a.id]


# [claude] HLP-LP-14
def test_hlp_lp_14__with_the_defaults_101_matching_tickets_give_100(db, TAG, mk_many_tickets):
    """HLP-LP-14 — with the defaults 101 matching tickets give 100.
    Rules: `list_platform` R5"""
    mk_many_tickets(101)

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert len(result) == 100


# [claude] HLP-LP-15
def test_hlp_lp_15__limit_1000_gives_all_101(db, TAG, mk_many_tickets):
    """HLP-LP-15 — limit=1000 gives all 101.
    Rules: `list_platform` R5"""
    mk_many_tickets(101)

    result = dao.list_platform(db, search=TAG, limit=1000)

    # Then 1
    assert len(result) == 101


# [claude] HLP-LP-16
def test_hlp_lp_16__limit_0_returns_an_empty_list(db, TAG, mk_ticket):
    """HLP-LP-16 — limit=0 returns an empty list.
    Rules: `list_platform` R5"""
    mk_ticket("HELP-2026-001")

    result = dao.list_platform(db, search=TAG, limit=0)

    # Then 1
    assert result == []


# [claude] HLP-LP-17
def test_hlp_lp_17__a_negative_limit_raises_dataerror(db, w1, w2, TAG, mk_ticket):
    """HLP-LP-17 — a negative limit raises DataError.
    Rules: `list_platform` R5, Errors"""
    mk_ticket("HELP-2026-001")
    before = ws_counts(db, w1, w2)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_platform(db, search=TAG, limit=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LP-18
def test_hlp_lp_18__a_negative_skip_raises_dataerror(db, w1, w2, TAG, mk_ticket):
    """HLP-LP-18 — a negative skip raises DataError.
    Rules: `list_platform` R5, Errors"""
    mk_ticket("HELP-2026-001")
    before = ws_counts(db, w1, w2)

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_platform(db, search=TAG, skip=-1)

    # Then 1
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LP-19
def test_hlp_lp_19__newest_first_whatever_the_ids(db, TAG, mk_ticket):
    """HLP-LP-19 — newest first, whatever the ids.
    Rules: `list_platform` R5"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    c = mk_ticket("HELP-2026-003")
    newer(db, b, 2)
    newer(db, c, 1)

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert tids(result) == [b.id, c.id, a.id]


# [claude] HLP-LP-20
@pytest.mark.xfail(strict=False, reason=BUG_1442)
def test_hlp_lp_20__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, TAG, mk_ticket):
    """HLP-LP-20 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `list_platform` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    c = mk_ticket("HELP-2026-003")
    d = mk_ticket("HELP-2026-004")
    newer(db, d, 1)
    seqscan(db)
    bump_t(db, a)

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert tids(result) == [d.id, c.id, b.id, a.id]


# [claude] HLP-LP-21
@pytest.mark.xfail(strict=True, reason=BUG_1442)
def test_hlp_lp_21__the_query_orders_by_created_at_then_id_both_descending(db, TAG, mk_ticket):
    """HLP-LP-21 — the query orders by created_at, then id, both descending.
    Rules: `list_platform` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001")

    with StatementRecorder(db) as recorder:
        result = dao.list_platform(db, search=TAG)

    order_part = order_part_of(recorder.sql())
    # Then 1
    assert tids(result) == [a.id]
    # Then 2
    assert "created_at" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 5
    assert order_part.upper().count("DESC") == 2


# [claude] HLP-LP-22
def test_hlp_lp_22__the_status_filter_comes_before_the_page_a_newer_closed_ticket_takes_no_place(
        db, TAG, mk_ticket):
    """HLP-LP-22 — the status filter comes before the page: a newer closed ticket takes no place.
    Rules: `list_platform` R2, R5"""
    x = mk_ticket("HELP-2026-001", status="closed")
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_platform(db, status="pending", search=TAG, skip=1, limit=1)

    # Then 1
    assert tids(result) == [b.id]


# [claude] HLP-LP-23
def test_hlp_lp_23__the_search_comes_before_the_page_a_newer_ticket_of_another_workspace_takes_no_place(
        db, w2, TAG, mk_ticket):
    """HLP-LP-23 — the search comes before the page: a newer ticket of another workspace takes no place.
    Rules: `list_platform` R3, R5"""
    x = mk_ticket("HELP-2026-001", workspace_id=w2.id)
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_platform(db, search=f"Gamma {TAG}", skip=1, limit=1)

    # Then 1
    assert tids(result) == [b.id]


# [claude] HLP-LP-24
def test_hlp_lp_24__writes_nothing_a_pending_ticket_stays_pending_an_unflushed_edit_stays_unflushed(
        db, w1, w2, u1, TAG, mk_ticket):
    """HLP-LP-24 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed.
    Rules: `list_platform` Side effects"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-002")
    b.title = "Edited"
    p = new_pending(db, w1, u1, "HELP-2026-003")
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.list_platform(db, search=f"Gamma {TAG}")

    # Then 1
    assert set(tids(result)) == {a.id, b.id}
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
    assert ws_counts(db, w1, w2) == before


# [claude] HLP-LP-25
def test_hlp_lp_25__status_is_a_filter_and_keeps_none(db, TAG, mk_ticket):
    """HLP-LP-25 — status "" is a filter and keeps none.
    Rules: `list_platform` R2"""
    a = mk_ticket("HELP-2026-001")
    own_ids = {a.id}

    result = dao.list_platform(db, status="", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-26
@pytest.mark.xfail(strict=False, reason=BUG_1442)
def test_hlp_lp_26__on_a_tie_the_id_decides_not_the_title(db, TAG, mk_ticket):
    """HLP-LP-26 — on a tie the id decides, not the title.
    Rules: `list_platform` R5 [BUG-1442]"""
    a = mk_ticket("HELP-2026-001", title="Alpha")
    b = mk_ticket("HELP-2026-002", title="Bravo")
    c = mk_ticket("HELP-2026-003", title="Charlie")
    d = mk_ticket("HELP-2026-004", title="Delta")
    newer(db, d, 1)
    seqscan(db)
    bump_t(db, a)

    result = dao.list_platform(db, search=TAG)

    # Then 1
    assert tids(result) == [d.id, c.id, b.id, a.id]


# [claude] HLP-LP-27
def test_hlp_lp_27__the_retired_status_open_keeps_none_not_even_an_opened_ticket(db, TAG, mk_ticket):
    """HLP-LP-27 — the retired status "open" keeps none, not even an "opened" ticket.
    Rules: `list_platform` R2"""
    a = mk_ticket("HELP-2026-001", status="opened")
    b = mk_ticket("HELP-2026-002")
    own_ids = {a.id, b.id}

    result = dao.list_platform(db, status="open", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-28
def test_hlp_lp_28__ticket_type_feedback_keeps_the_feedback_tickets_of_every_workspace(db, w2, TAG, mk_ticket):
    """HLP-LP-28 — ticket_type "feedback" keeps the feedback tickets of every workspace.
    Rules: `list_platform` R2a, R1"""
    a = mk_ticket("HELP-2026-001")
    f1 = mk_ticket("HELP-2026-002", type="feedback")
    f2 = mk_ticket("HELP-2026-001", workspace_id=w2.id, type="feedback")
    s2 = mk_ticket("HELP-2026-002", workspace_id=w2.id)
    own_ids = {a.id, f1.id, f2.id, s2.id}

    result = dao.list_platform(db, ticket_type="feedback", search=TAG)

    # Then 1
    assert set(own(result, own_ids)) == {f1.id, f2.id}


# [claude] HLP-LP-29
def test_hlp_lp_29__ticket_type_is_a_filter_and_keeps_none(db, TAG, mk_ticket):
    """HLP-LP-29 — ticket_type "" is a filter and keeps none.
    Rules: `list_platform` R2a"""
    a = mk_ticket("HELP-2026-001")
    f = mk_ticket("HELP-2026-002", type="feedback")
    own_ids = {a.id, f.id}

    result = dao.list_platform(db, ticket_type="", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-30
def test_hlp_lp_30__ticket_type_and_search_combine_with_and_one_workspace_s_feedback_only(
        db, w2, TAG, mk_ticket):
    """HLP-LP-30 — ticket_type and search combine with AND: one workspace's feedback only.
    Rules: `list_platform` R2a, R3"""
    mk_ticket("HELP-2026-001")
    f1 = mk_ticket("HELP-2026-002", type="feedback")
    mk_ticket("HELP-2026-001", workspace_id=w2.id, type="feedback")

    result = dao.list_platform(db, ticket_type="feedback", search=f"Gamma {TAG}")

    # Then 1
    assert tids(result) == [f1.id]


# [claude] HLP-LP-31
def test_hlp_lp_31__the_type_filter_comes_before_the_page_a_newer_feedback_ticket_takes_no_place(
        db, TAG, mk_ticket):
    """HLP-LP-31 — the type filter comes before the page: a newer feedback ticket takes no place.
    Rules: `list_platform` R2a, R5"""
    x = mk_ticket("HELP-2026-001", type="feedback")
    a = mk_ticket("HELP-2026-002")
    b = mk_ticket("HELP-2026-003")
    newer(db, x, 3)
    newer(db, a, 2)
    newer(db, b, 1)

    result = dao.list_platform(db, ticket_type="support", search=TAG, skip=1, limit=1)

    # Then 1
    assert tids(result) == [b.id]


# [claude] HLP-LP-32
def test_hlp_lp_32__status_and_ticket_type_combine_with_and(db, TAG, mk_ticket):
    """HLP-LP-32 — status and ticket_type combine with AND.
    Rules: `list_platform` R2a, R2"""
    a = mk_ticket("HELP-2026-001", type="feedback")
    c = mk_ticket("HELP-2026-002", status="closed", type="feedback")
    s = mk_ticket("HELP-2026-003", status="closed")
    own_ids = {a.id, c.id, s.id}

    result = dao.list_platform(db, status="closed", ticket_type="feedback", search=TAG)

    # Then 1
    assert own(result, own_ids) == [c.id]


# [claude] HLP-LP-33
def test_hlp_lp_33__ticket_type_feedback_with_a_capital_keeps_none(db, TAG, mk_ticket):
    """HLP-LP-33 — ticket_type "Feedback" with a capital keeps none.
    Rules: `list_platform` R2a"""
    f = mk_ticket("HELP-2026-001", type="feedback")
    own_ids = {f.id}

    result = dao.list_platform(db, ticket_type="Feedback", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-34
def test_hlp_lp_34___in_ticket_type_is_no_wildcard(db, TAG, mk_ticket):
    """HLP-LP-34 — _ in ticket_type is no wildcard.
    Rules: `list_platform` R2a"""
    f = mk_ticket("HELP-2026-001", type="feedback")
    own_ids = {f.id}

    result = dao.list_platform(db, ticket_type="feed_ack", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-35
def test_hlp_lp_35__a_leading_space_in_ticket_type_keeps_none(db, TAG, mk_ticket):
    """HLP-LP-35 — a leading space in ticket_type keeps none.
    Rules: `list_platform` R2a"""
    f = mk_ticket("HELP-2026-001", type="feedback")
    own_ids = {f.id}

    result = dao.list_platform(db, ticket_type=" feedback", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# [claude] HLP-LP-36
def test_hlp_lp_36__a_stored_type_with_a_leading_space_is_not_kept(db, TAG, mk_ticket):
    """HLP-LP-36 — a stored type with a leading space is not kept.
    Rules: `list_platform` R2a"""
    f = mk_ticket("HELP-2026-001", type=" feedback")
    own_ids = {f.id}

    result = dao.list_platform(db, ticket_type="feedback", search=TAG)

    # Then 1
    assert own(result, own_ids) == []


# --------------------------------------------------------------------------- #
# DAOHelpTicket.get_platform_by_id
# --------------------------------------------------------------------------- #


# [claude] HLP-GP-01
def test_hlp_gp_01__returns_ticket_workspace_name_creator_name(db, TAG, mk_ticket):
    """HLP-GP-01 — returns (ticket, workspace name, creator name).
    Rules: `get_platform_by_id` R1, Returns"""
    a = mk_ticket("HELP-2026-001")

    result = dao.get_platform_by_id(db, ticket_id=a.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == a.id
    # Then 3
    assert result[1] == f"Gamma {TAG}"
    # Then 4
    assert result[2] == "Rahim"


# [claude] HLP-GP-02
def test_hlp_gp_02__a_ticket_of_another_workspace_is_returned(db, w2, u2, TAG, mk_ticket):
    """HLP-GP-02 — a ticket of another workspace is returned.
    Rules: `get_platform_by_id` R1"""
    z = mk_ticket("HELP-2026-001", workspace_id=w2.id, created_by=u2.id)

    result = dao.get_platform_by_id(db, ticket_id=z.id)

    # Then 1
    assert result[0].id == z.id
    # Then 2
    assert result[1] == f"Delta {TAG}"
    # Then 3
    assert result[2] == "Karim"


# [claude] HLP-GP-03
def test_hlp_gp_03__a_ticket_without_a_creator_has_creator_name_none(db, mk_ticket):
    """HLP-GP-03 — a ticket without a creator has creator name None.
    Rules: `get_platform_by_id` R1"""
    a = mk_ticket("HELP-2026-001", created_by=None)

    result = dao.get_platform_by_id(db, ticket_id=a.id)

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[2] is None


# [claude] HLP-GP-04
def test_hlp_gp_04__an_unknown_id_returns_none(db, mk_ticket):
    """HLP-GP-04 — an unknown id returns None.
    Rules: `get_platform_by_id` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_platform_by_id(db, ticket_id=MISSING)

    # Then 1
    assert result is None


# [claude] HLP-GP-05
def test_hlp_gp_05__id_0_returns_none(db, mk_ticket):
    """HLP-GP-05 — id 0 returns None.
    Rules: `get_platform_by_id` R1"""
    mk_ticket("HELP-2026-001")

    result = dao.get_platform_by_id(db, ticket_id=0)

    # Then 1
    assert result is None


# [claude] HLP-GP-06
def test_hlp_gp_06__writes_nothing_a_pending_ticket_stays_pending_an_unflushed_edit_stays_unflushed(
        db, w1, w2, u1, mk_ticket):
    """HLP-GP-06 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed.
    Rules: `get_platform_by_id` Side effects"""
    a = mk_ticket("HELP-2026-001")
    b = mk_ticket("HELP-2026-003")
    b.title = "Edited"
    p = new_pending(db, w1, u1, "HELP-2026-002")
    before = ws_counts(db, w1, w2)

    with StatementRecorder(db) as recorder:
        result = dao.get_platform_by_id(db, ticket_id=a.id)

    # Then 1
    assert result[0].id == a.id
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
    assert ws_counts(db, w1, w2) == before
