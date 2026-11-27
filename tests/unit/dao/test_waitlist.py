"""Unit tests for app/dao/waitlist.py.

Implements tests/unit/dao/waitlist.cases.md, one test per case, in card order.
Real Postgres session (`db` fixture). Nothing is mocked and no clock is patched
(Conventions, Externals: None); the two commit spies wrap `db.commit` and keep
it callable.

`waitlist_signups` is shared and not workspace-scoped: every email carries the
test's own TAG, every filtered card searches for it, and the "no filter" cards
compare `total` with N0, a count taken inside the same test.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import uuid
from datetime import datetime, timezone
from unittest import mock

import pytest
from sqlalchemy import event, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.waitlist import waitlist_dao

# Spec gap 1: the cases assume `app.models.waitlist`; the model lives in
# `app.models.waitlist_signup` (same class name).
from app.models.waitlist_signup import WaitlistSignup

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton waitlist_dao"
dao = waitlist_dao

# Convention "T1, T2, T3"
T1 = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc)


# Convention "TAG = uuid.uuid4().hex[:10], once per test"
@pytest.fixture
def TAG():
    return uuid.uuid4().hex[:10]


# Convention "N0": the number of waitlist_signups rows, read where the card says
def read_n0(db):
    return db.execute(text("SELECT count(*) FROM waitlist_signups")).scalar()


# --------------------------------------------------------------------------- #
# Conventions -> row builders (each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "signup": the card gives email; wants_product_updates, status,
# created_at are passed only when the card lists them after "but".
def _signup_fields(email, columns):
    fields = {"email": email, "first_name": "Zed", "last_name": "Ray", "company_name": "Acme",
              "source": "landing", "ip_hash": "h1"}
    fields.update(columns)
    return fields


@pytest.fixture
def mk_signup(db):
    """mk_signup(email, **columns) -> WaitlistSignup, inserted and flushed."""
    def _mk(email, **columns):
        row = WaitlistSignup(**_signup_fields(email, columns))
        db.add(row)
        db.flush()
        return row
    return _mk


# The "101 signups E1 ... E101, built with add_all" Given of LS-19, LS-20
@pytest.fixture
def mk_101(db):
    """mk_101(tag) -> `newest`: the ids of E101, E100, ... E1."""
    def _mk(tag):
        rows = [WaitlistSignup(**_signup_fields(
                    f"e{k}.{tag}@x.com",
                    {"created_at": datetime(2026, 3, 1, 9, k // 60, k % 60, tzinfo=timezone.utc)}))
                for k in range(1, 102)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "idset(items)"
def idset(items):
    return {r.id for r in items}


# Convention "ids(items)": in the order returned
def ids(items):
    return [r.id for r in items]


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row_id):
    db.expire_all()
    return db.get(WaitlistSignup, row_id)


# Convention "unchanged(X) except c": every column of X, straight from the table
def snap(db, row):
    table = WaitlistSignup.__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of waitlist_signups rows stored
def stored_count(db):
    return db.execute(text("SELECT count(*) FROM waitlist_signups")).scalar()


def count_where(db, sql, **params):
    return db.execute(text(f"SELECT count(*) FROM waitlist_signups WHERE {sql}"), params).scalar()


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

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from waitlist_signups with LIMIT (the page); fails loudly unless exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "waitlist_signups" in s and "LIMIT" in s]
        return statement


# Convention "order_part"
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return mock.patch.object(db, "commit", wraps=db.commit)


# --------------------------------------------------------------------------- #
# WaitlistDAO.get_by_email
# --------------------------------------------------------------------------- #


# [claude] WLS-GE-01
def test_wls_ge_01__the_signup_with_exactly_that_email_is_returned(db, TAG, mk_signup):
    """WLS-GE-01 — the signup with exactly that email is returned.
    Rules: `get_by_email` R1, Returns"""
    mk_signup(f"amy.{TAG}@x.com")
    a = mk_signup(f"zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")

    # Then 1
    assert isinstance(result, WaitlistSignup)
    # Then 2
    assert result.id == a.id


# [claude] WLS-GE-02
def test_wls_ge_02__the_email_in_capitals_gives_none(db, TAG, mk_signup):
    """WLS-GE-02 — the email in capitals gives None.
    Rules: `get_by_email` R1"""
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"Zed.{TAG}@x.com")

    # Then 1
    assert result is None


# [claude] WLS-GE-03
def test_wls_ge_03__the_email_with_a_leading_space_gives_none(db, TAG, mk_signup):
    """WLS-GE-03 — the email with a leading space gives None.
    Rules: `get_by_email` R1"""
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f" zed.{TAG}@x.com")

    # Then 1
    assert result is None


# [claude] WLS-GE-04
def test_wls_ge_04__part_of_an_email_gives_none(db, TAG, mk_signup):
    """WLS-GE-04 — part of an email gives None.
    Rules: `get_by_email` R1"""
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"zed.{TAG}@x")

    # Then 1
    assert result is None


# [claude] WLS-GE-05
def test_wls_ge_05__is_no_wildcard_in_an_email(db, TAG, mk_signup):
    """WLS-GE-05 — _ is no wildcard in an email.
    Rules: `get_by_email` R1"""
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"zed_{TAG}@x.com")

    # Then 1
    assert result is None


# [claude] WLS-GE-06
def test_wls_ge_06__a_stored_email_with_a_leading_space_is_not_found_without_it(db, TAG, mk_signup):
    """WLS-GE-06 — a stored email with a leading space is not found without it.
    Rules: `get_by_email` R1"""
    mk_signup(f" zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")

    # Then 1
    assert result is None


# [claude] WLS-GE-07
def test_wls_ge_07__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, TAG, mk_signup):
    """WLS-GE-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_email` Side effects"""
    a = mk_signup(f"zed.{TAG}@x.com")
    b = mk_signup(f"amy.{TAG}@x.com")
    p = WaitlistSignup(email=f"pen.{TAG}@x.com", first_name="Pen", last_name="Ray", company_name="Acme", source="landing", ip_hash="h1")
    db.add(p)
    b.status = "CONTACTED"

    with StatementRecorder(db) as recorder:
        result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")
    written = recorder.written()

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
    assert not db.deleted
    # Then 7
    assert written == []


# [claude] WLS-GE-08
def test_wls_ge_08__a_stored_email_with_capitals_is_not_found_by_the_lower_case_one(db, TAG, mk_signup):
    """WLS-GE-08 — a stored email with capitals is not found by the lower-case one.
    Rules: `get_by_email` R1"""
    mk_signup(f"Zed.{TAG}@x.com")

    result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# WaitlistDAO.list_signups
# --------------------------------------------------------------------------- #


# [claude] WLS-LS-01
def test_wls_ls_01__with_no_filter_every_signup_is_counted_and_paged(db, TAG, mk_signup):
    """WLS-LS-01 — with no filter every signup is counted and paged.
    Rules: `list_signups` R1, Returns"""
    n0 = read_n0(db)
    a = mk_signup(f"zed.{TAG}@x.com")
    b = mk_signup(f"amy.{TAG}@x.com", status="CONTACTED")

    result = dao.list_signups(db, limit=1000)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert isinstance(result[0], list)
    # Then 3
    assert result[1] == n0 + 2
    # Then 4
    assert {a.id, b.id} <= idset(result[0])


# [claude] WLS-LS-02
def test_wls_ls_02__the_search_is_trimmed_and_ignores_case(db, TAG, mk_signup):
    """WLS-LS-02 — the search is trimmed and ignores case.
    Rules: `list_signups` R2"""
    a = mk_signup(f"BIG.{TAG}@Y.ORG")
    mk_signup(f"small.{TAG}@x.com")

    result = dao.list_signups(db, search=f" big.{TAG}@")

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-03
def test_wls_ls_03__the_search_text_in_the_middle_of_an_email_finds_it(db, TAG, mk_signup):
    """WLS-LS-03 — the search text in the middle of an email finds it.
    Rules: `list_signups` R2"""
    a = mk_signup(f"zed.{TAG}.mid@x.com")
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.list_signups(db, search=f"{TAG}.mid")

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-04
@pytest.mark.xfail(strict=True, reason="BUG-1410: `%` and `_` in the waitlist search act as wildcards")
def test_wls_ls_04__in_the_search_matches_only_a_literal(db, TAG, mk_signup):
    """WLS-LS-04 — _ in the search matches only a literal _.
    Rules: `list_signups` R2 [BUG-1410]"""
    a = mk_signup(f"a_b.{TAG}@x.com")
    mk_signup(f"axb.{TAG}@x.com")

    result = dao.list_signups(db, search=f"a_b.{TAG}")

    # Then 1
    assert isinstance(result[0], list)
    # Then 2
    assert ids(result[0]) == [a.id]
    # Then 3
    assert result[1] == 1


# [claude] WLS-LS-05
@pytest.mark.xfail(strict=True, reason="BUG-1410: `%` and `_` in the waitlist search act as wildcards")
def test_wls_ls_05__in_the_search_matches_only_a_literal(db, TAG, mk_signup):
    """WLS-LS-05 — % in the search matches only a literal %.
    Rules: `list_signups` R2 [BUG-1410]"""
    a = mk_signup(f"p%q.{TAG}@x.com")
    mk_signup(f"pzzq.{TAG}@x.com")

    result = dao.list_signups(db, search=f"p%q.{TAG}")

    # Then 1
    assert isinstance(result[0], list)
    # Then 2
    assert ids(result[0]) == [a.id]
    # Then 3
    assert result[1] == 1


# [claude] WLS-LS-06
@pytest.mark.xfail(strict=True, reason="BUG-1410: `%` and `_` in the waitlist search act as wildcards (a backslash escapes the next character)")
def test_wls_ls_06__a_backslash_in_the_search_matches_only_a_literal_backslash(db, TAG, mk_signup):
    """WLS-LS-06 — a backslash in the search matches only a literal backslash.
    Rules: `list_signups` R2 [BUG-1410]"""
    a = mk_signup("c\\d." + TAG + "@x.com")
    mk_signup(f"cd.{TAG}@x.com")

    result = dao.list_signups(db, search="c\\d." + TAG)

    # Then 1
    assert isinstance(result[0], list)
    # Then 2
    assert ids(result[0]) == [a.id]
    # Then 3
    assert result[1] == 1


# [claude] WLS-LS-07
def test_wls_ls_07__only_the_email_is_searched_not_names_or_company(db, TAG, mk_signup):
    """WLS-LS-07 — only the email is searched, not names or company.
    Rules: `list_signups` R2a"""
    mk_signup(f"zed.{TAG}@x.com", first_name=f"n{TAG}q", last_name=f"n{TAG}q", company_name=f"n{TAG}q")

    result = dao.list_signups(db, search=f"n{TAG}q")

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 0


# [claude] WLS-LS-08
def test_wls_ls_08__an_empty_search_applies_no_filter(db, TAG, mk_signup):
    """WLS-LS-08 — an empty search applies no filter.
    Rules: `list_signups` R2a"""
    n0 = read_n0(db)
    a = mk_signup(f"zed.{TAG}@x.com")
    b = mk_signup(f"amy.{TAG}@x.com")

    result = dao.list_signups(db, search="", limit=1000)

    # Then 1
    assert result[1] == n0 + 2
    # Then 2
    assert {a.id, b.id} <= idset(result[0])


# [claude] WLS-LS-09
def test_wls_ls_09__a_search_of_only_spaces_matches_every_row(db, TAG, mk_signup):
    """WLS-LS-09 — a search of only spaces matches every row.
    Rules: `list_signups` R2a"""
    n0 = read_n0(db)
    a = mk_signup(f"zed.{TAG}@x.com")
    b = mk_signup(f"amy.{TAG}@x.com")

    result = dao.list_signups(db, search="   ", limit=1000)

    # Then 1
    assert result[1] == n0 + 2
    # Then 2
    assert {a.id, b.id} <= idset(result[0])


# [claude] WLS-LS-10
def test_wls_ls_10__wants_product_updates_false_keeps_only_rows_with_false(db, TAG, mk_signup):
    """WLS-LS-10 — wants_product_updates=False keeps only rows with False.
    Rules: `list_signups` R3"""
    mk_signup(f"zed.{TAG}@x.com", wants_product_updates=True)
    b = mk_signup(f"amy.{TAG}@x.com", wants_product_updates=False)

    result = dao.list_signups(db, search=TAG, wants_product_updates=False)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-11
def test_wls_ls_11__wants_product_updates_true_keeps_only_rows_with_true(db, TAG, mk_signup):
    """WLS-LS-11 — wants_product_updates=True keeps only rows with True.
    Rules: `list_signups` R3"""
    a = mk_signup(f"zed.{TAG}@x.com", wants_product_updates=True)
    mk_signup(f"amy.{TAG}@x.com", wants_product_updates=False)

    result = dao.list_signups(db, search=TAG, wants_product_updates=True)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-12
def test_wls_ls_12__status_keeps_rows_with_exactly_that_text_case_sensitive(db, TAG, mk_signup):
    """WLS-LS-12 — status keeps rows with exactly that text, case-sensitive.
    Rules: `list_signups` R4"""
    mk_signup(f"zed.{TAG}@x.com", status="CONTACTED")
    b = mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status="contacted")

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-13
def test_wls_ls_13__part_of_a_status_finds_nothing(db, TAG, mk_signup):
    """WLS-LS-13 — part of a status finds nothing.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status="contact")

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 0


# [claude] WLS-LS-14
def test_wls_ls_14__newest_first_by_created_at_whatever_the_ids(db, TAG, mk_signup):
    """WLS-LS-14 — newest first by created_at, whatever the ids.
    Rules: `list_signups` R5"""
    a = mk_signup(f"a.{TAG}@x.com", created_at=T2)
    b = mk_signup(f"b.{TAG}@x.com", created_at=T3)
    c = mk_signup(f"c.{TAG}@x.com", created_at=T1)

    result = dao.list_signups(db, search=TAG)

    # Then 1
    assert ids(result[0]) == [b.id, a.id, c.id]


# [claude] WLS-LS-15
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1411: Waitlist signups with one timestamp come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_wls_ls_15__on_a_tie_the_higher_id_comes_first_also_after_the_lowest_id_was_upda(db, TAG, mk_signup):
    """WLS-LS-15 — on a tie the higher id comes first, also after the lowest id was updated.
    Rules: `list_signups` R5 [BUG-1411]"""
    a = mk_signup(f"a.{TAG}@x.com", created_at=T2)
    b = mk_signup(f"b.{TAG}@x.com", created_at=T2)
    c = mk_signup(f"c.{TAG}@x.com", created_at=T2)
    a.first_name = "Amy"
    db.flush()
    db.expire_all()

    result = dao.list_signups(db, search=TAG)

    # Then 1
    assert len(result[0]) == 3
    # Then 2
    assert ids(result[0]) == [c.id, b.id, a.id]


# [claude] WLS-LS-16
@pytest.mark.xfail(strict=True, reason="BUG-1411: Waitlist signups with one timestamp come back in no fixed order")
def test_wls_ls_16__the_query_orders_by_created_at_then_id_both_descending(db, TAG, mk_signup):
    """WLS-LS-16 — the query orders by created_at, then id, both descending.
    Rules: `list_signups` R5 [BUG-1411]"""
    a = mk_signup(f"a.{TAG}@x.com")

    with StatementRecorder(db) as recorder:
        result = dao.list_signups(db, search=TAG)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "created_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] WLS-LS-17
def test_wls_ls_17__total_counts_every_match_not_only_the_page(db, TAG, mk_signup):
    """WLS-LS-17 — total counts every match, not only the page.
    Rules: `list_signups` R6"""
    mk_signup(f"a.{TAG}@x.com", created_at=T3)
    b = mk_signup(f"b.{TAG}@x.com", created_at=T2)
    mk_signup(f"c.{TAG}@x.com", created_at=T1)

    result = dao.list_signups(db, search=TAG, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 3


# [claude] WLS-LS-18
def test_wls_ls_18__limit_0_gives_an_empty_page_with_the_total(db, TAG, mk_signup):
    """WLS-LS-18 — limit=0 gives an empty page with the total.
    Rules: `list_signups` R6"""
    mk_signup(f"a.{TAG}@x.com")
    mk_signup(f"b.{TAG}@x.com")

    result = dao.list_signups(db, search=TAG, limit=0)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 2


# [claude] WLS-LS-19
def test_wls_ls_19__with_the_default_limit_101_matches_give_100_rows_and_a_total_of_101(db, TAG, mk_101):
    """WLS-LS-19 — with the default limit 101 matches give 100 rows and a total of 101.
    Rules: `list_signups` R6"""
    newest = mk_101(TAG)

    result = dao.list_signups(db, search=TAG)

    # Then 1
    assert len(result[0]) == 100
    # Then 2
    assert result[1] == 101
    # Then 3
    assert ids(result[0]) == newest[:100]


# [claude] WLS-LS-20
def test_wls_ls_20__limit_1000_gives_all_101(db, TAG, mk_101):
    """WLS-LS-20 — limit=1000 gives all 101.
    Rules: `list_signups` R6"""
    mk_101(TAG)

    result = dao.list_signups(db, search=TAG, limit=1000)

    # Then 1
    assert len(result[0]) == 101
    # Then 2
    assert result[1] == 101


# [claude] WLS-LS-21
def test_wls_ls_21__a_negative_limit_raises_dataerror_2201w(db, TAG, mk_signup):
    """WLS-LS-21 — a negative limit raises DataError 2201W.
    Rules: `list_signups` R6, Errors"""
    mk_signup(f"a.{TAG}@x.com")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_signups(db, search=TAG, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored_count(db) == before


# [claude] WLS-LS-22
def test_wls_ls_22__a_negative_skip_raises_dataerror_2201x(db, TAG, mk_signup):
    """WLS-LS-22 — a negative skip raises DataError 2201X.
    Rules: `list_signups` R6, Errors"""
    mk_signup(f"a.{TAG}@x.com")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_signups(db, search=TAG, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored_count(db) == before


# [claude] WLS-LS-23
def test_wls_ls_23__filters_combine_with_and(db, TAG, mk_signup):
    """WLS-LS-23 — filters combine with AND.
    Rules: `list_signups` R7"""
    a = mk_signup(f"a.{TAG}@x.com", wants_product_updates=True, status="CONTACTED")
    mk_signup(f"b.{TAG}@x.com", wants_product_updates=False, status="CONTACTED")
    mk_signup(f"c.{TAG}@x.com", wants_product_updates=True)
    mk_signup(f"d.other{TAG[:5]}@x.com", wants_product_updates=True, status="CONTACTED")

    result = dao.list_signups(db, search=TAG, wants_product_updates=True, status="CONTACTED")

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# [claude] WLS-LS-24
def test_wls_ls_24__a_filter_is_applied_before_the_page_a_hidden_newer_row_takes_no_plac(db, TAG, mk_signup):
    """WLS-LS-24 — a filter is applied before the page: a hidden newer row takes no place in it.
    Rules: `list_signups` R6, R7"""
    mk_signup(f"x.{TAG}@x.com", created_at=T3, wants_product_updates=False)
    mk_signup(f"a.{TAG}@x.com", created_at=T2, wants_product_updates=True)
    b = mk_signup(f"b.{TAG}@x.com", created_at=T1, wants_product_updates=True)

    result = dao.list_signups(db, search=TAG, wants_product_updates=True, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [b.id]
    # Then 2
    assert result[1] == 2


# [claude] WLS-LS-25
def test_wls_ls_25__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, TAG, mk_signup):
    """WLS-LS-25 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `list_signups` Side effects"""
    a = mk_signup(f"a.{TAG}@x.com")
    b = mk_signup(f"b.other@{TAG}.org")
    p = WaitlistSignup(email=f"p.{TAG}@x.com", first_name="Pen", last_name="Ray", company_name="Acme", source="landing", ip_hash="h1")
    db.add(p)
    b.status = "CONTACTED"

    with StatementRecorder(db) as recorder:
        result = dao.list_signups(db, search=f"a.{TAG}")
    written = recorder.written()

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# [claude] WLS-LS-26
def test_wls_ls_26__a_status_with_a_leading_space_finds_nothing(db, TAG, mk_signup):
    """WLS-LS-26 — a status with a leading space finds nothing.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status=" contacted")

    # Then 1
    assert result == ([], 0)


# [claude] WLS-LS-27
def test_wls_ls_27__is_no_wildcard_in_a_status(db, TAG, mk_signup):
    """WLS-LS-27 — _ is no wildcard in a status.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status="contacte_")

    # Then 1
    assert result == ([], 0)


# [claude] WLS-LS-28
def test_wls_ls_28__the_end_of_a_status_finds_nothing(db, TAG, mk_signup):
    """WLS-LS-28 — the end of a status finds nothing.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status="tacted")

    # Then 1
    assert result == ([], 0)


# [claude] WLS-LS-29
def test_wls_ls_29__status_is_a_filter_and_finds_nothing(db, TAG, mk_signup):
    """WLS-LS-29 — status="" is a filter and finds nothing.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status="contacted")

    result = dao.list_signups(db, search=TAG, status="")

    # Then 1
    assert result == ([], 0)


# [claude] WLS-LS-30
def test_wls_ls_30__a_stored_status_with_a_leading_space_is_not_found_without_it(db, TAG, mk_signup):
    """WLS-LS-30 — a stored status with a leading space is not found without it.
    Rules: `list_signups` R4"""
    mk_signup(f"amy.{TAG}@x.com", status=" contacted")

    result = dao.list_signups(db, search=TAG, status="contacted")

    # Then 1
    assert result == ([], 0)


# [claude] WLS-LS-31
def test_wls_ls_31__a_trailing_space_in_the_search_is_trimmed(db, TAG, mk_signup):
    """WLS-LS-31 — a trailing space in the search is trimmed.
    Rules: `list_signups` R2"""
    a = mk_signup(f"zed.{TAG}.mid@x.com")
    mk_signup(f"zed.{TAG}@x.com")

    result = dao.list_signups(db, search=f"{TAG}.mid ")

    # Then 1
    assert ids(result[0]) == [a.id]
    # Then 2
    assert result[1] == 1


# --------------------------------------------------------------------------- #
# WaitlistDAO.create_signup
# --------------------------------------------------------------------------- #


# [claude] WLS-CS-01
def test_wls_cs_01__one_row_with_exactly_the_given_values_nothing_trimmed_pending_an_awar(db, TAG):
    """WLS-CS-01 — one row with exactly the given values, nothing trimmed; PENDING; an aware created_at.
    Rules: `create_signup` R1, Returns"""
    result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name=" Z ", last_name="", company_name="Acme", wants_product_updates=True, source="landing", ip_hash="h1")

    # Then 1
    assert isinstance(result, WaitlistSignup)
    # Then 2
    assert result.id is not None
    # Then 3
    assert result.status == "PENDING"
    # Then 4
    assert result.created_at.tzinfo is not None
    # Then 5
    row = reread(db, result.id)
    assert row.email == f"new.{TAG}@x.com"
    assert row.first_name == " Z "
    assert row.last_name == ""
    assert row.company_name == "Acme"
    # Then 6
    assert row.wants_product_updates is True
    assert row.source == "landing"
    assert row.ip_hash == "h1"
    assert row.status == "PENDING"


# [claude] WLS-CS-02
def test_wls_cs_02__wants_product_updates_none_is_stored_false(db, TAG):
    """WLS-CS-02 — wants_product_updates=None is stored False.
    Rules: `create_signup` R2"""
    result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name=None, wants_product_updates=None, source=None, ip_hash=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.wants_product_updates is False
    assert row.company_name is None


# [claude] WLS-CS-03
def test_wls_cs_03__a_taken_email_raises_integrityerror_23505_and_writes_nothing(db, TAG, mk_signup):
    """WLS-CS-03 — a taken email raises IntegrityError 23505 and writes nothing.
    Rules: `create_signup` R3, Errors"""
    mk_signup(f"zed.{TAG}@x.com")
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create_signup(db, email=f"zed.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert stored_count(db) == before


# [claude] WLS-CS-04
def test_wls_cs_04__the_same_email_in_other_capitals_is_a_second_row(db, TAG, mk_signup):
    """WLS-CS-04 — the same email in other capitals is a second row.
    Rules: `create_signup` R3"""
    a = mk_signup(f"zed.{TAG}@x.com")

    result = dao.create_signup(db, email=f"Zed.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")

    # Then 1
    assert result.id != a.id
    # Then 2
    assert reread(db, result.id).email == f"Zed.{TAG}@x.com"
    # Then 3
    assert count_where(db, "lower(email) = :e", e=f"zed.{TAG}@x.com") == 2


# [claude] WLS-CS-05
def test_wls_cs_05__a_first_name_of_101_characters_raises_dataerror_22001_and_writes_noth(db, TAG):
    """WLS-CS-05 — a first name of 101 characters raises DataError 22001 and writes nothing.
    Rules: `create_signup` R4, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="f" * 101, last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] WLS-CS-06
def test_wls_cs_06__a_first_name_of_100_characters_is_stored_whole(db, TAG):
    """WLS-CS-06 — a first name of 100 characters is stored whole.
    Rules: `create_signup` R4"""
    result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="f" * 100, last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).first_name == "f" * 100


# [claude] WLS-CS-07
def test_wls_cs_07__leaving_out_a_keyword_raises_typeerror(db, TAG):
    """WLS-CS-07 — leaving out a keyword raises TypeError.
    Rules: `create_signup` R5, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing")
    # Then 2
    assert stored_count(db) == before


# [claude] WLS-CS-08
def test_wls_cs_08__the_row_is_flushed_not_committed(db, TAG):
    """WLS-CS-08 — the row is flushed, not committed.
    Rules: `create_signup` Side effects"""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_where(db, "email = :e", e=f"new.{TAG}@x.com") == 1
        sp.rollback()
        # Then 3
        assert count_where(db, "email = :e", e=f"new.{TAG}@x.com") == 0
        # Then 4
        spy.assert_not_called()


# --------------------------------------------------------------------------- #
# WaitlistDAO.update_status
# --------------------------------------------------------------------------- #


# [claude] WLS-US-01
def test_wls_us_01__the_status_is_set_and_nothing_else_changes_the_same_object_is_return(db, TAG, mk_signup):
    """WLS-US-01 — the status is set and nothing else changes; the same object is returned.
    Rules: `update_status` R1, Returns"""
    s = mk_signup(f"zed.{TAG}@x.com")
    before_s = snap(db, s)

    result = dao.update_status(db, signup=s, status="CONTACTED")

    # Then 1
    assert result is s
    # Then 2
    assert reread(db, s.id).status == "CONTACTED"
    # Then 3
    after_s = snap(db, s)
    assert {k: v for k, v in after_s.items() if k != "status"} == {k: v for k, v in before_s.items() if k != "status"}


# [claude] WLS-US-02
def test_wls_us_02__free_text_of_exactly_20_characters_is_accepted(db, TAG, mk_signup):
    """WLS-US-02 — free text of exactly 20 characters is accepted.
    Rules: `update_status` R1"""
    s = mk_signup(f"zed.{TAG}@x.com")

    result = dao.update_status(db, signup=s, status="w" * 20)

    # Then 1
    assert result is s
    # Then 2
    assert reread(db, s.id).status == "w" * 20


# [claude] WLS-US-03
def test_wls_us_03__21_characters_raise_dataerror_22001_and_the_stored_status_stays(db, TAG, mk_signup):
    """WLS-US-03 — 21 characters raise DataError 22001 and the stored status stays.
    Rules: `update_status` R2, Errors"""
    s = mk_signup(f"zed.{TAG}@x.com")

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.update_status(db, signup=s, status="w" * 21)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert reread(db, s.id).status == "PENDING"


# [claude] WLS-US-04
def test_wls_us_04__the_change_is_flushed_not_committed(db, TAG, mk_signup):
    """WLS-US-04 — the change is flushed, not committed.
    Rules: `update_status` R1, Side effects"""
    s = mk_signup(f"zed.{TAG}@x.com")

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.update_status(db, signup=s, status="ACCEPTED")

        # Then 1
        assert result is s
        # Then 2
        assert db.execute(text("SELECT status FROM waitlist_signups WHERE id = :id"), {"id": s.id}).scalar() == "ACCEPTED"
        sp.rollback()
        # Then 3
        assert db.execute(text("SELECT status FROM waitlist_signups WHERE id = :id"), {"id": s.id}).scalar() == "PENDING"
        # Then 4
        spy.assert_not_called()


# [claude] WLS-US-05
def test_wls_us_05__the_same_status_again_is_accepted(db, TAG, mk_signup):
    """WLS-US-05 — the same status again is accepted.
    Rules: `update_status` R1"""
    s = mk_signup(f"zed.{TAG}@x.com")

    result = dao.update_status(db, signup=s, status="PENDING")

    # Then 1
    assert result is s
    # Then 2
    assert reread(db, s.id).status == "PENDING"
