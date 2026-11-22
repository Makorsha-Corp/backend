"""Unit tests for app/dao/payment_transaction.py.

Implements tests/unit/dao/payment_transaction.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is mocked and
no clock is patched (Conventions, Externals: None).

This file is the owner's reference for the coming SSLCommerz subscription
portal: every lookup the gateway callbacks, the reconciliation sweep and risk
resolution rely on is pinned here. Read it top to bottom:

  1. Conventions -> constants, the standing rows and the row builder `st.txn`.
  2. Named checks -> small reading helpers (counts, re-read, SQL recorder).
  3. One section per DAO method, each test a card of the cases file.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment, and every numbered Then line of a card is a `# Then N` comment directly
before its assertions.

Conventions mapping (card says -> code):
  dao                  -> `dao` (the `payment_transaction_dao` singleton)
  W0, W1, W2, U1, U2   -> `st.W0` ... `st.U2` (fixture `st`, autouse)
  TAG, tid(k)          -> `st.TAG`, `st.tid(k)`
  txn(k), but ...      -> `st.txn(k, column=value, ...)`; `paid` -> `**PAID`
  raw_insert(s)        -> `st.raw_insert(s)`
  zone(Z), seqscan     -> `st.zone(Z)`, `st.seqscan()`
  bump(X)              -> `st.bump(X)`
  clean2001            -> `st.clean2001()` (first step of every SI / OQ25 test)
  re-read X            -> `st.reread(X.id)`
  nothing written      -> `before = st.counts()` ... `assert st.counts() == before`
  count_tid(s)         -> `st.count_tid(s)`; the W1 count -> `st.count_ws(st.W1.id)`
  near_utc(v)          -> `near_utc(v)`
  Statement recorder   -> `with StatementRecorder(db) as rec:` around the When;
                          `rec.selects`, `rec.sql`, `rec.lock_part`,
                          `rec.order_part`, `rec.written`
  commit spy           -> `sp = db.begin_nested()` + `patch.object(db, "commit", wraps=db.commit)`
  ids / idset / pairs  -> `ids(result)`, `idset(result)`, `pairs(result)`
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, naive datetimes, and the cards' Decimal("990") literals)
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from sqlalchemy import event, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.payment_transaction import payment_transaction_dao
from app.models.payment_transaction import PaymentTransaction
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

dao = payment_transaction_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "T1 ... T4" (naive UTC)
T1 = datetime(2026, 3, 4, 10, 0, 0)
T2 = datetime(2026, 3, 4, 11, 0, 0)
T3 = datetime(2026, 3, 4, 12, 0, 0)
T4 = datetime(2026, 3, 4, 13, 0, 0)

# Convention "Sweep times" (year 2001 on purpose, see clean2001)
CUT = datetime(2001, 3, 1, 12, 0, 0)
S1 = datetime(2001, 3, 1, 9, 0, 0)
S2 = datetime(2001, 3, 1, 10, 0, 0)
S3 = datetime(2001, 3, 1, 11, 0, 0)
OLD = datetime(2001, 1, 1, 9, 0, 0)
US = timedelta(microseconds=1)
CUTZ = datetime(2001, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

# Convention "paid" (used after "but")
PAID = {
    "status": "VALIDATED_SUCCESS",
    "val_id": "val-ok-1",
    "bank_tran_id": "bank-1",
    "card_type": "VISA-Dutch Bangla",
    "validated_at": T2,
}

# The columns a fresh checkout row leaves empty (PTX-CR-01 Then 8)
EMPTY_COLUMNS = (
    "cus_name",
    "cus_email",
    "cus_phone",
    "value_a",
    "value_b",
    "value_c",
    "value_d",
    "session_key",
    "gateway_page_url",
    "val_id",
    "risk_level",
    "risk_title",
    "card_type",
    "bank_tran_id",
    "verify_sign",
    "last_ipn_payload",
    "risk_resolved_by",
    "initiated_by",
    "risk_resolved_at",
    "validated_at",
    "risk_resolution_note",
)

R029 = "BUG-029: Risk-hold resolution does not lock the row"
R2401 = "BUG-2401: A payment transaction written without its times gets the database's local clock"
R2402 = "BUG-2402: Payments of one creation time come back in no fixed order in the ledger list"
R2403 = "BUG-2403: The sweep picks its batch of stuck payments in no fixed order when start times tie"


# Convention "utc_now()" and "near_utc(v)"
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def near_utc(v):
    return abs(utc_now() - v) < timedelta(minutes=5)


# --------------------------------------------------------------------------- #
# Conventions -> standing rows, Given rows and steps
# --------------------------------------------------------------------------- #


class Standing:
    """The standing rows of every test, plus the Given-row builders and steps.

    W0, W1, W2 are made in that order (W0.id < W1.id < W2.id); U1 is "Rahim",
    U2 is "Karim". TAG is new per test, so every tran_id is unique.
    """

    def __init__(self, db):
        self.db = db
        self.W0 = make_workspace(db)
        self.W1 = make_workspace(db)
        self.W2 = make_workspace(db)
        self.U1 = make_profile(db, name="Rahim")
        self.U2 = make_profile(db, name="Karim")
        self.TAG = "ab" + secrets.token_hex(11)

    # Convention "tid(k)": 27 characters
    def tid(self, k):
        return f"tx{k}{self.TAG}"

    # Convention "txn(k)": a checkout row of W1 by U1 at T1; keywords override columns
    def txn(self, k, **cols):
        fields = {
            "workspace_id": self.W1.id,
            "tran_id": self.tid(k),
            "amount": Decimal("990.00"),
            "currency": "BDT",
            "initiated_by": self.U1.id,
            "initiated_at": T1,
            "created_at": T1,
            "updated_at": T1,
        }
        fields.update(cols)
        row = PaymentTransaction(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    # The "pending row P" of the writes-nothing cards: added, not flushed
    def pending(self, k, **cols):
        row = PaymentTransaction(
            workspace_id=self.W1.id,
            tran_id=self.tid(k),
            amount=Decimal("990.00"),
            currency="BDT",
            **cols,
        )
        self.db.add(row)
        return row

    # Convention "raw_insert(s)": no time columns, no status; returns the new id
    def raw_insert(self, s):
        return self.db.scalar(
            text(
                "INSERT INTO payment_transactions (workspace_id, tran_id, amount, currency) "
                "VALUES (:w, :t, 990.00, 'BDT') RETURNING id"
            ),
            {"w": self.W1.id, "t": s},
        )

    # Convention "zone(Z)"
    def zone(self, z):
        self.db.execute(text(f"SET LOCAL TimeZone = '{z}'"))

    # Convention "seqscan"
    def seqscan(self):
        self.db.execute(text("SET LOCAL enable_indexscan = off"))
        self.db.execute(text("SET LOCAL enable_bitmapscan = off"))
        self.db.execute(text("SET LOCAL enable_indexonlyscan = off"))

    # Convention "bump(X)": moves X's row to the end of the table
    def bump(self, row):
        self.db.execute(
            text("UPDATE payment_transactions SET currency = currency WHERE id = :i"),
            {"i": row.id},
        )
        self.db.expire_all()

    # Convention "clean2001": a precondition, not a numbered check
    def clean2001(self):
        assert (
            self.db.scalar(
                text(
                    "SELECT count(*) FROM payment_transactions WHERE initiated_at < '2002-01-01' "
                    "AND workspace_id NOT IN (:a, :b, :c)"
                ),
                {"a": self.W0.id, "b": self.W1.id, "c": self.W2.id},
            )
            == 0
        )

    # Convention "re-read X"
    def reread(self, row_id):
        self.db.expire_all()
        return self.db.get(PaymentTransaction, row_id)

    # Convention "count_tid(s)"
    def count_tid(self, s):
        return self.db.scalar(
            text("SELECT count(*) FROM payment_transactions WHERE tran_id = :t"),
            {"t": s},
        )

    # The cards' "count of W1's payment transactions"
    def count_ws(self, workspace_id):
        return self.db.scalar(
            text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"),
            {"w": workspace_id},
        )

    # Convention "nothing written": rows of W0, W1, W2 and all profiles
    def counts(self):
        return {
            "W0": self.count_ws(self.W0.id),
            "W1": self.count_ws(self.W1.id),
            "W2": self.count_ws(self.W2.id),
            "profiles": self.db.scalar(text("SELECT count(*) FROM profiles")),
        }


@pytest.fixture(autouse=True)
def st(db):
    """Standing rows (Conventions): W0, W1, W2, then U1 "Rahim", U2 "Karim"."""
    return Standing(db)


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


def pairs(result):
    return [(t.id, name) for t, name in result]


# Convention "Statement recorder"
class StatementRecorder:
    """Records the SQL the session sends while the `with` block runs."""

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

    @property
    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [
            s
            for s in self.statements
            if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]

    @property
    def sql(self):
        """The one SELECT that reads payment_transactions; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects if "FROM payment_transactions" in s]
        return statement

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]

    @property
    def lock_part(self):
        sql = self.sql
        if "FOR UPDATE" not in sql:
            return ""
        return sql[sql.index("FOR UPDATE") :]


# --------------------------------------------------------------------------- #
# Inherited `create` (model facts of `payment_transactions`)
# --------------------------------------------------------------------------- #


# [claude] PTX-CR-01
def test_ptx_cr_01__checkout_row_gets_initiated_and_three_utc_times(db, st):
    """PTX-CR-01 — a checkout row gets status INITIATED, three naive UTC times and nothing else.
    Rules: inherited `create` R1 (each time in the call's window; never asserted equal), Side effects"""
    assert st.count_ws(st.W1.id) == 0
    before = utc_now()

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("990.00"),
            "currency": "BDT",
        },
    )
    after = utc_now()

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.status == "INITIATED"
    # Then 3
    assert row.workspace_id == st.W1.id
    assert row.tran_id == st.tid(1)
    assert row.amount == Decimal("990.00")
    assert row.currency == "BDT"
    # Then 4
    assert row.initiated_at.tzinfo is None
    assert row.created_at.tzinfo is None
    assert row.updated_at.tzinfo is None
    # Then 5
    assert before <= row.initiated_at <= after
    # Then 6
    assert before <= row.created_at <= after
    # Then 7
    assert before <= row.updated_at <= after
    # Then 8
    assert {c: getattr(row, c) for c in EMPTY_COLUMNS} == dict.fromkeys(EMPTY_COLUMNS)
    # Then 9
    assert st.count_ws(st.W1.id) == 1


# [claude] PTX-CR-02
def test_ptx_cr_02__new_row_is_flushed(db, st):
    """PTX-CR-02 — the new row is flushed: a raw query in the same session finds it.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("990.00"),
            "currency": "BDT",
            "initiated_by": st.U1.id,
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert result not in db.new
    # Then 3
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM payment_transactions WHERE id = :i AND tran_id = :t AND initiated_by = :u"
            ),
            {"i": result.id, "t": st.tid(1), "u": st.U1.id},
        )
        == 1
    )


# [claude] PTX-CR-03
def test_ptx_cr_03__create_flushes_but_never_commits(db, st):
    """PTX-CR-03 — create flushes but never commits.
    Rules: inherited `create` R1 ("not committed")"""
    assert st.count_ws(st.W1.id) == 0

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.create(
            db,
            obj_in={
                "workspace_id": st.W1.id,
                "tran_id": st.tid(1),
                "amount": Decimal("990.00"),
                "currency": "BDT",
            },
        )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.count_tid(st.tid(1)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert st.count_tid(st.tid(1)) == 0


# [claude] PTX-CR-04
def test_ptx_cr_04__amount_2_125_stored_as_2_13(db, st):
    """PTX-CR-04 — an amount of 2.125 is stored as 2.13 (half up, not half to even).
    Rules: inherited `create` R3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("2.125"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.amount == Decimal("2.13")
    # Then 3
    assert str(row.amount) == "2.13"


# [claude] PTX-CR-05
def test_ptx_cr_05__amount_0_005_stored_as_0_01(db, st):
    """PTX-CR-05 — an amount of 0.005 is stored as 0.01, not 0.00.
    Rules: inherited `create` R3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("0.005"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).amount == Decimal("0.01")


# [claude] PTX-CR-06
def test_ptx_cr_06__amount_minus_1_005_stored_as_minus_1_01(db, st):
    """PTX-CR-06 — an amount of -1.005 is stored as -1.01 (away from zero).
    Rules: inherited `create` R3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("-1.005"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).amount == Decimal("-1.01")


# [claude] PTX-CR-07
def test_ptx_cr_07__amount_2_124_stored_as_2_12(db, st):
    """PTX-CR-07 — an amount of 2.124 is stored as 2.12 (control: below the half).
    Rules: inherited `create` R3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("2.124"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).amount == Decimal("2.12")


# [claude] PTX-CR-08
def test_ptx_cr_08__whole_amount_stored_with_two_decimals(db, st):
    """PTX-CR-08 — a whole amount is stored with two decimals.
    Rules: inherited `create` R3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("990"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert str(st.reread(result.id).amount) == "990.00"


# [claude] PTX-CR-09
def test_ptx_cr_09__tran_id_of_other_workspace_fails_at_flush(db, st):
    """PTX-CR-09 — a tran_id already used in another workspace fails at flush and saves nothing.
    Rules: inherited `create` R2, Errors row 1"""
    a = st.txn(1, workspace_id=st.W2.id)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in={
                    "workspace_id": st.W1.id,
                    "tran_id": st.tid(1),
                    "amount": Decimal("500.00"),
                    "currency": "BDT",
                },
            )
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert st.count_tid(st.tid(1)) == 1
    # Then 3
    row = st.reread(a.id)
    assert row.workspace_id == st.W2.id
    assert row.amount == Decimal("990.00")
    # Then 4
    assert st.count_ws(st.W1.id) == 0


# [claude] PTX-CR-10
def test_ptx_cr_10__tran_id_of_same_workspace_fails_at_flush(db, st):
    """PTX-CR-10 — a tran_id already used in the same workspace fails at flush.
    Rules: inherited `create` R2, Errors row 1"""
    a = st.txn(1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in={
                    "workspace_id": st.W1.id,
                    "tran_id": st.tid(1),
                    "amount": Decimal("500.00"),
                    "currency": "BDT",
                },
            )
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert st.count_tid(st.tid(1)) == 1
    # Then 3
    assert st.reread(a.id).amount == Decimal("990.00")


# [claude] PTX-CR-11
def test_ptx_cr_11__tran_id_in_capitals_is_different(db, st):
    """PTX-CR-11 — the same tran_id in capitals is a different tran_id.
    Rules: inherited `create` R2"""
    st.txn(1)

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1).upper(),
            "amount": Decimal("500.00"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).tran_id == st.tid(1).upper()
    # Then 3
    assert st.count_tid(st.tid(1)) == 1


# [claude] PTX-CR-12
def test_ptx_cr_12__tran_id_of_30_characters_stored(db, st):
    """PTX-CR-12 — a tran_id of exactly 30 characters is stored.
    Rules: inherited `create` R2 (boundary)"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1) + "xyz",
            "amount": Decimal("990.00"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.tran_id == st.tid(1) + "xyz"
    # Then 3
    assert len(row.tran_id) == 30


# [claude] PTX-CR-13
def test_ptx_cr_13__tran_id_of_31_characters_fails_22001(db, st):
    """PTX-CR-13 — a tran_id of 31 characters fails at flush with DataError 22001 and saves nothing.
    Rules: inherited `create` R2, Errors row 2"""
    assert st.count_ws(st.W1.id) == 0

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in={
                    "workspace_id": st.W1.id,
                    "tran_id": st.tid(1) + "wxyz",
                    "amount": Decimal("990.00"),
                    "currency": "BDT",
                },
            )
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert st.count_tid(st.tid(1) + "wxyz") == 0
    # Then 3
    assert st.count_ws(st.W1.id) == 0


# [claude] PTX-CR-14
def test_ptx_cr_14__any_status_text_stored(db, st):
    """PTX-CR-14 — any status text is stored as given.
    Rules: inherited `create` R3"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("990.00"),
            "currency": "BDT",
            "status": "whatever",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).status == "whatever"


# [claude] PTX-CR-15
def test_ptx_cr_15__negative_amount_stored(db, st):
    """PTX-CR-15 — a negative amount is stored.
    Rules: inherited `create` R3"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("-5"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).amount == Decimal("-5.00")


# [claude] PTX-CR-16
def test_ptx_cr_16__raw_insert_gets_status_initiated(db, st):
    """PTX-CR-16 — a row inserted without its times gets the status INITIATED from the database.
    Rules: inherited `create` R1 (database default of `status`), R1a"""
    st.zone("UTC")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM payment_transactions WHERE id = :i AND status = 'INITIATED'"
            ),
            {"i": new_id},
        )
        == 1
    )


# [claude] PTX-CR-17
def test_ptx_cr_17__raw_insert_under_utc_gets_utc_times(db, st):
    """PTX-CR-17 — under a UTC session a raw insert gets UTC times (control, today and after the fix).
    Rules: inherited `create` R1a"""
    st.zone("UTC")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    row = st.reread(new_id)
    assert near_utc(row.initiated_at)
    # Then 3
    assert near_utc(row.created_at)
    # Then 4
    assert near_utc(row.updated_at)


# [claude] PTX-CR-18
@pytest.mark.xfail(strict=True, reason=R2401)
def test_ptx_cr_18__raw_insert_under_dhaka_initiated_at_is_utc(db, st):
    """PTX-CR-18 — under Asia/Dhaka a raw insert's initiated_at is still UTC.
    Rules: inherited `create` R1a [BUG-2401]"""
    st.zone("Asia/Dhaka")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    assert near_utc(st.reread(new_id).initiated_at)


# [claude] PTX-CR-19
@pytest.mark.xfail(strict=True, reason=R2401)
def test_ptx_cr_19__raw_insert_under_dhaka_created_at_is_utc(db, st):
    """PTX-CR-19 — under Asia/Dhaka a raw insert's created_at is still UTC.
    Rules: inherited `create` R1a [BUG-2401]"""
    st.zone("Asia/Dhaka")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    assert near_utc(st.reread(new_id).created_at)


# [claude] PTX-CR-20
@pytest.mark.xfail(strict=True, reason=R2401)
def test_ptx_cr_20__raw_insert_under_dhaka_updated_at_is_utc(db, st):
    """PTX-CR-20 — under Asia/Dhaka a raw insert's updated_at is still UTC.
    Rules: inherited `create` R1a [BUG-2401]"""
    st.zone("Asia/Dhaka")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    assert near_utc(st.reread(new_id).updated_at)


# [claude] PTX-CR-21
@pytest.mark.xfail(strict=True, reason=R2401)
def test_ptx_cr_21__raw_insert_under_new_york_initiated_at_is_utc(db, st):
    """PTX-CR-21 — under America/New_York a raw insert's initiated_at is still UTC (behind as well as ahead).
    Rules: inherited `create` R1a [BUG-2401]"""
    st.zone("America/New_York")

    new_id = st.raw_insert(st.tid(1))

    # Then 1
    assert new_id is not None
    # Then 2
    assert near_utc(st.reread(new_id).initiated_at)


# [claude] PTX-CR-22
def test_ptx_cr_22__amount_with_13_integer_digits_stored(db, st):
    """PTX-CR-22 — an amount with 13 integer digits is stored as is.
    Rules: inherited `create` R1b"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(
        db,
        obj_in={
            "workspace_id": st.W1.id,
            "tran_id": st.tid(1),
            "amount": Decimal("9999999999999.99"),
            "currency": "BDT",
        },
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).amount == Decimal("9999999999999.99")


# [claude] PTX-CR-23
def test_ptx_cr_23__amount_rounding_up_to_14_digits_fails_22003(db, st):
    """PTX-CR-23 — an amount that rounds up to 14 integer digits fails at flush with DataError 22003 and saves nothing.
    Rules: inherited `create` R1b, Errors row 3, HR-15"""
    assert st.count_ws(st.W1.id) == 0

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in={
                    "workspace_id": st.W1.id,
                    "tran_id": st.tid(1),
                    "amount": Decimal("9999999999999.995"),
                    "currency": "BDT",
                },
            )
    assert exc.value.orig.pgcode == "22003"
    # Then 2
    assert st.count_tid(st.tid(1)) == 0
    # Then 3
    assert st.count_ws(st.W1.id) == 0


# [claude] PTX-CR-24
def test_ptx_cr_24__amount_with_14_integer_digits_fails_22003(db, st):
    """PTX-CR-24 — an amount with 14 integer digits fails at flush with DataError 22003 and saves nothing.
    Rules: inherited `create` R1b, Errors row 3"""
    assert st.count_ws(st.W1.id) == 0

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in={
                    "workspace_id": st.W1.id,
                    "tran_id": st.tid(1),
                    "amount": Decimal("10000000000000"),
                    "currency": "BDT",
                },
            )
    assert exc.value.orig.pgcode == "22003"
    # Then 2
    assert st.count_tid(st.tid(1)) == 0
    # Then 3
    assert st.count_ws(st.W1.id) == 0


# --------------------------------------------------------------------------- #
# get_by_tran_id — unscoped, exact match (fresh tran_id check, mock gateway pages)
# --------------------------------------------------------------------------- #


# [claude] PTX-TI-01
def test_ptx_ti_01__returns_row_with_exactly_this_tran_id(db, st):
    """PTX-TI-01 — returns the row with exactly this tran_id.
    Rules: `get_by_tran_id` R1"""
    st.txn(1)
    b = st.txn(2)
    st.txn(3)

    result = dao.get_by_tran_id(db, tran_id=st.tid(2))

    # Then 1
    assert result.id == b.id
    # Then 2
    assert result.tran_id == st.tid(2)


# [claude] PTX-TI-02
def test_ptx_ti_02__row_of_earlier_workspace_returned(db, st):
    """PTX-TI-02 — a row of an earlier workspace is returned (unscoped).
    Rules: `get_by_tran_id` R1, R3"""
    a = st.txn(1, workspace_id=st.W0.id)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.workspace_id == st.W0.id


# [claude] PTX-TI-03
def test_ptx_ti_03__row_of_later_workspace_returned(db, st):
    """PTX-TI-03 — a row of a later workspace is returned (unscoped).
    Rules: `get_by_tran_id` R1, R3"""
    a = st.txn(1, workspace_id=st.W2.id)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.workspace_id == st.W2.id


# [claude] PTX-TI-04
def test_ptx_ti_04__paid_row_returned_whatever_status(db, st):
    """PTX-TI-04 — a paid row is returned whatever its status.
    Rules: `get_by_tran_id` R1"""
    a = st.txn(1, **PAID)
    st.txn(2, status="RISK_HOLD", risk_level=1, risk_title="Card from abroad")

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "VALIDATED_SUCCESS"


# [claude] PTX-TI-05
def test_ptx_ti_05__unknown_tran_id_returns_none(db, st):
    """PTX-TI-05 — an unknown tran_id returns None.
    Rules: `get_by_tran_id` R1"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(9))

    # Then 1
    assert result is None


# [claude] PTX-TI-06
def test_ptx_ti_06__empty_tran_id_returns_none(db, st):
    """PTX-TI-06 — an empty tran_id returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id="")

    # Then 1
    assert result is None


# [claude] PTX-TI-07
def test_ptx_ti_07__tran_id_in_capitals_returns_none(db, st):
    """PTX-TI-07 — the tran_id in capitals returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1).upper())

    # Then 1
    assert result is None


# [claude] PTX-TI-08
def test_ptx_ti_08__trailing_space_returns_none(db, st):
    """PTX-TI-08 — the tran_id with a trailing space returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1) + " ")

    # Then 1
    assert result is None


# [claude] PTX-TI-09
def test_ptx_ti_09__leading_space_returns_none(db, st):
    """PTX-TI-09 — the tran_id with a leading space returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=" " + st.tid(1))

    # Then 1
    assert result is None


# [claude] PTX-TI-10
def test_ptx_ti_10__without_last_character_returns_none(db, st):
    """PTX-TI-10 — the tran_id without its last character returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1)[:-1])

    # Then 1
    assert result is None


# [claude] PTX-TI-11
def test_ptx_ti_11__middle_part_returns_none(db, st):
    """PTX-TI-11 — a middle part of the tran_id returns None.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1)[3:20])

    # Then 1
    assert result is None


# [claude] PTX-TI-12
def test_ptx_ti_12__underscore_is_no_wildcard(db, st):
    """PTX-TI-12 — "_" in place of one character is no wildcard.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1)[:5] + "_" + st.tid(1)[6:])

    # Then 1
    assert result is None


# [claude] PTX-TI-13
def test_ptx_ti_13__percent_is_no_wildcard(db, st):
    """PTX-TI-13 — "%" after the start of the tran_id is no wildcard.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1)[:6] + "%")

    # Then 1
    assert result is None


# [claude] PTX-TI-14
def test_ptx_ti_14__stored_leading_space_not_found_by_plain(db, st):
    """PTX-TI-14 — a stored tran_id with a leading space is not found by the plain one.
    Rules: `get_by_tran_id` R2 (stored side)"""
    st.txn(1, tran_id=" " + st.tid(1))

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result is None


# [claude] PTX-TI-15
def test_ptx_ti_15__stored_capitals_not_found_by_lower_case(db, st):
    """PTX-TI-15 — a stored tran_id in capitals is not found by the lower-case one.
    Rules: `get_by_tran_id` R2 (stored side)"""
    st.txn(1, tran_id=st.tid(1).upper())

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result is None


# [claude] PTX-TI-16
def test_ptx_ti_16__40_character_string_returns_none(db, st):
    """PTX-TI-16 — a 40-character string that starts with a tran_id returns None and raises nothing.
    Rules: `get_by_tran_id` R2"""
    st.txn(1)

    result = dao.get_by_tran_id(db, tran_id=st.tid(1) + "x" * 13)

    # Then 1
    assert result is None


# [claude] PTX-TI-17
def test_ptx_ti_17__one_select_no_lock_nothing_written(db, st):
    """PTX-TI-17 — one SELECT, no lock, nothing written.
    Rules: `get_by_tran_id` R3"""
    a = st.txn(1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_tran_id(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part == ""
    # Then 4
    assert rec.written == []


# [claude] PTX-TI-18
def test_ptx_ti_18__writes_nothing(db, st):
    """PTX-TI-18 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_tran_id` R3, Side effects"""
    a = st.txn(1)
    b = st.txn(2)
    b.cus_name = "Edited"
    p = st.pending(3)
    before = st.counts()

    result = dao.get_by_tran_id(db, tran_id=st.tid(1))

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
    assert st.counts() == before


# --------------------------------------------------------------------------- #
# get_by_tran_id_for_update — the idempotency wall of every gateway callback
# --------------------------------------------------------------------------- #


# [claude] PTX-TU-01
def test_ptx_tu_01__returns_row_with_exactly_this_tran_id(db, st):
    """PTX-TU-01 — returns the row with exactly this tran_id.
    Rules: `get_by_tran_id_for_update` R1"""
    st.txn(1)
    b = st.txn(2)
    st.txn(3)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(2))

    # Then 1
    assert result.id == b.id


# [claude] PTX-TU-02
def test_ptx_tu_02__row_of_earlier_workspace_returned(db, st):
    """PTX-TU-02 — a row of an earlier workspace is returned (unscoped).
    Rules: `get_by_tran_id_for_update` R1"""
    a = st.txn(1, workspace_id=st.W0.id)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id


# [claude] PTX-TU-03
def test_ptx_tu_03__paid_row_of_later_workspace_returned(db, st):
    """PTX-TU-03 — a paid row of a later workspace is returned (any workspace, any status).
    Rules: `get_by_tran_id_for_update` R1"""
    a = st.txn(1, workspace_id=st.W2.id, **PAID)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "VALIDATED_SUCCESS"


# [claude] PTX-TU-04
def test_ptx_tu_04__unknown_tran_id_returns_none(db, st):
    """PTX-TU-04 — an unknown tran_id returns None.
    Rules: `get_by_tran_id_for_update` R1, R3"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(9))

    # Then 1
    assert result is None


# [claude] PTX-TU-05
def test_ptx_tu_05__empty_tran_id_returns_none(db, st):
    """PTX-TU-05 — an empty tran_id returns None.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id="")

    # Then 1
    assert result is None


# [claude] PTX-TU-06
def test_ptx_tu_06__tran_id_in_capitals_returns_none(db, st):
    """PTX-TU-06 — the tran_id in capitals returns None.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1).upper())

    # Then 1
    assert result is None


# [claude] PTX-TU-07
def test_ptx_tu_07__trailing_space_returns_none(db, st):
    """PTX-TU-07 — the tran_id with a trailing space returns None.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1) + " ")

    # Then 1
    assert result is None


# [claude] PTX-TU-08
def test_ptx_tu_08__underscore_is_no_wildcard(db, st):
    """PTX-TU-08 — "_" in place of one character is no wildcard.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(
        db, tran_id=st.tid(1)[:5] + "_" + st.tid(1)[6:]
    )

    # Then 1
    assert result is None


# [claude] PTX-TU-09
def test_ptx_tu_09__without_last_character_returns_none(db, st):
    """PTX-TU-09 — the tran_id without its last character returns None.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1)[:-1])

    # Then 1
    assert result is None


# [claude] PTX-TU-10
def test_ptx_tu_10__40_character_string_returns_none(db, st):
    """PTX-TU-10 — a 40-character string that starts with a tran_id returns None and raises nothing.
    Rules: `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1) + "x" * 13)

    # Then 1
    assert result is None


# [claude] PTX-TU-11
def test_ptx_tu_11__plain_for_update_at_end_of_one_select(db, st):
    """PTX-TU-11 — the row is read with a plain FOR UPDATE at the end of the one SELECT.
    Rules: `get_by_tran_id_for_update` R2"""
    a = st.txn(1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.sql.rstrip().endswith("FOR UPDATE")
    # Then 4
    assert "NOWAIT" not in rec.sql.upper()
    # Then 5
    assert "SKIP LOCKED" not in rec.sql.upper()
    # Then 6
    assert rec.written == []


# [claude] PTX-TU-12
def test_ptx_tu_12__unknown_tran_id_sends_same_locked_select(db, st):
    """PTX-TU-12 — an unknown tran_id sends the same locked SELECT and returns None.
    Rules: `get_by_tran_id_for_update` R2, R3"""
    st.txn(1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(9))

    # Then 1
    assert result is None
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part.strip() == "FOR UPDATE"


# [claude] PTX-TU-13
def test_ptx_tu_13__writes_nothing(db, st):
    """PTX-TU-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_tran_id_for_update` Side effects"""
    a = st.txn(1)
    b = st.txn(2)
    b.cus_name = "Edited"
    p = st.pending(3)
    before = st.counts()

    result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1))

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
    assert st.counts() == before


# [claude] PTX-TU-14
def test_ptx_tu_14__locked_read_never_commits(db, st):
    """PTX-TU-14 — the locked read never commits (a commit would release the callback's lock).
    Rules: `get_by_tran_id_for_update` R2 ("held until the caller's transaction commits or rolls back")"""
    a = st.txn(1)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.get_by_tran_id_for_update(db, tran_id=st.tid(1))

    # Then 1
    assert result.id == a.id
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert st.count_tid(st.tid(1)) == 1


# --------------------------------------------------------------------------- #
# get_by_id_and_workspace_with_initiator — risk resolution's read (BUG-029: for_update)
# --------------------------------------------------------------------------- #


# [claude] PTX-IW-01
def test_ptx_iw_01__returns_pair_transaction_and_initiator_name(db, st):
    """PTX-IW-01 — returns the pair (transaction, initiator's name).
    Rules: `get_by_id_and_workspace_with_initiator` R1, Returns"""
    a = st.txn(1, status="RISK_HOLD", risk_level=1, risk_title="Card from abroad")

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0].id == a.id
    # Then 3
    assert result[1] == "Rahim"
    # Then 4
    assert tuple(result) == (result[0], "Rahim")


# [claude] PTX-IW-02
def test_ptx_iw_02__name_is_initiator_not_resolver(db, st):
    """PTX-IW-02 — the name is the initiator's, not the risk resolver's.
    Rules: `get_by_id_and_workspace_with_initiator` R1"""
    a = st.txn(
        1,
        initiated_by=st.U2.id,
        risk_resolved_by=st.U1.id,
        risk_resolved_at=T2,
        risk_resolution_note="Checked with the bank",
        **PAID,
    )

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[1] == "Karim"


# [claude] PTX-IW-03
def test_ptx_iw_03__row_without_initiator_has_name_none(db, st):
    """PTX-IW-03 — a row without an initiator is returned, with name None.
    Rules: `get_by_id_and_workspace_with_initiator` R2"""
    a = st.txn(1, initiated_by=None)

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is not None
    # Then 2
    assert result[0].id == a.id
    # Then 3
    assert result[1] is None


# [claude] PTX-IW-04
def test_ptx_iw_04__deleted_initiator_profile_gives_name_none(db, st):
    """PTX-IW-04 — after the initiator's profile is deleted, the row is returned with name None.
    Rules: `get_by_id_and_workspace_with_initiator` R2 (`ON DELETE SET NULL`)"""
    u3 = make_profile(db, name="Salma")
    a = st.txn(1, initiated_by=u3.id)
    db.execute(text("DELETE FROM profiles WHERE id = :i"), {"i": u3.id})
    db.expire_all()

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[0].initiated_by is None
    # Then 3
    assert result[1] is None


# [claude] PTX-IW-05
def test_ptx_iw_05__row_of_earlier_workspace_returns_none(db, st):
    """PTX-IW-05 — a row of an earlier workspace (lower id) returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    x0 = st.txn(1, workspace_id=st.W0.id)
    st.txn(2)

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=x0.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-IW-06
def test_ptx_iw_06__row_of_later_workspace_returns_none(db, st):
    """PTX-IW-06 — a row of a later workspace (higher id) returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    st.txn(1)
    x2 = st.txn(2, workspace_id=st.W2.id)

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=x2.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-IW-07
def test_ptx_iw_07__w1_row_under_w0_or_w2_returns_none(db, st):
    """PTX-IW-07 — W1's row asked for under W0 or W2 returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    a = st.txn(1)

    result = [
        dao.get_by_id_and_workspace_with_initiator(db, id=a.id, workspace_id=w)
        for w in (st.W0.id, st.W2.id)
    ]

    # Then 1
    assert result == [None, None]


# [claude] PTX-IW-08
def test_ptx_iw_08__unknown_id_returns_none(db, st):
    """PTX-IW-08 — an unknown id returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    st.txn(1)

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=MISSING, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-IW-09
def test_ptx_iw_09__id_0_returns_none(db, st):
    """PTX-IW-09 — id 0 returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    st.txn(1)

    result = dao.get_by_id_and_workspace_with_initiator(db, id=0, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] PTX-IW-10
def test_ptx_iw_10__expired_row_returned(db, st):
    """PTX-IW-10 — status does not matter: an expired row is returned.
    Rules: `get_by_id_and_workspace_with_initiator` R3"""
    a = st.txn(1, status="EXPIRED")

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[0].status == "EXPIRED"


# [claude] PTX-IW-11
def test_ptx_iw_11__without_for_update_one_select_no_lock(db, st):
    """PTX-IW-11 — without for_update: one SELECT, no lock, nothing written.
    Rules: `get_by_id_and_workspace_with_initiator` R4"""
    a = st.txn(1)
    db.expunge_all()  # clear the session before a one-query check

    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace_with_initiator(
            db, id=a.id, workspace_id=st.W1.id
        )

    # Then 1
    assert result[1] == "Rahim"
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part == ""
    # Then 4
    assert rec.written == []


# [claude] PTX-IW-12
def test_ptx_iw_12__writes_nothing(db, st):
    """PTX-IW-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_id_and_workspace_with_initiator` Side effects"""
    a = st.txn(1)
    b = st.txn(2)
    b.risk_resolution_note = "Edited"
    p = st.pending(3)
    before = st.counts()

    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id
    )

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
    assert not db.deleted
    # Then 7
    assert st.counts() == before


# [claude] PTX-IW-13
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_13__for_update_locks_only_transaction_row(db, st):
    """PTX-IW-13 — for_update=True locks only the transaction row: FOR UPDATE OF payment_transactions.
    Rules: `get_by_id_and_workspace_with_initiator` R5 [BUG-029]"""
    a = st.txn(1, status="RISK_HOLD", risk_level=1, risk_title="Card from abroad")

    with StatementRecorder(db) as rec:
        # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
        result = dao.get_by_id_and_workspace_with_initiator(
            db, id=a.id, workspace_id=st.W1.id, for_update=True
        )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[1] == "Rahim"
    # Then 3
    assert len(rec.selects) == 1
    # Then 4
    assert "FOR UPDATE OF payment_transactions" in rec.sql
    # Then 5
    assert "profiles" not in rec.lock_part
    # Then 6 (no SKIP LOCKED, no NOWAIT: HR-10, the second caller waits)
    assert rec.lock_part.strip() == "FOR UPDATE OF payment_transactions"


# [claude] PTX-IW-14
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_14__for_update_without_initiator_keeps_outer_join(db, st):
    """PTX-IW-14 — for_update=True with no initiator still returns the row, name None (the outer join is kept).
    Rules: `get_by_id_and_workspace_with_initiator` R5, R2 [BUG-029]"""
    a = st.txn(1, initiated_by=None, status="RISK_HOLD")

    # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=a.id, workspace_id=st.W1.id, for_update=True
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[1] is None


# [claude] PTX-IW-15
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_15__for_update_on_other_workspace_row_returns_none(db, st):
    """PTX-IW-15 — for_update=True on another workspace's row returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R5, R3 [BUG-029]"""
    x0 = st.txn(1, workspace_id=st.W0.id, status="RISK_HOLD")
    x2 = st.txn(2, workspace_id=st.W2.id, status="RISK_HOLD")

    # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
    result = [
        dao.get_by_id_and_workspace_with_initiator(
            db, id=x, workspace_id=st.W1.id, for_update=True
        )
        for x in (x0.id, x2.id)
    ]

    # Then 1
    assert result == [None, None]


# [claude] PTX-IW-16
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_16__for_update_with_unknown_id_returns_none(db, st):
    """PTX-IW-16 — for_update=True with an unknown id returns None.
    Rules: `get_by_id_and_workspace_with_initiator` R5, R3 [BUG-029]"""
    st.txn(1)

    # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
    result = dao.get_by_id_and_workspace_with_initiator(
        db, id=MISSING, workspace_id=st.W1.id, for_update=True
    )

    # Then 1
    assert result is None


# [claude] PTX-IW-17
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_17__for_update_false_takes_no_lock(db, st):
    """PTX-IW-17 — for_update=False takes no lock.
    Rules: `get_by_id_and_workspace_with_initiator` R4, R5 [BUG-029]"""
    a = st.txn(1)

    with StatementRecorder(db) as rec:
        # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
        result = dao.get_by_id_and_workspace_with_initiator(
            db, id=a.id, workspace_id=st.W1.id, for_update=False
        )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert rec.lock_part == ""


# [claude] PTX-IW-18
@pytest.mark.xfail(strict=True, reason=R029)
def test_ptx_iw_18__for_update_writes_nothing_and_never_commits(db, st):
    """PTX-IW-18 — for_update=True writes nothing and never commits.
    Rules: `get_by_id_and_workspace_with_initiator` R5, Side effects [BUG-029]"""
    a = st.txn(1, status="RISK_HOLD")

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        # Fails today here (card: Then 1): there is no `for_update` keyword (TypeError).
        result = dao.get_by_id_and_workspace_with_initiator(
            db, id=a.id, workspace_id=st.W1.id, for_update=True
        )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    assert st.count_tid(st.tid(1)) == 1


# --------------------------------------------------------------------------- #
# get_by_tran_id_and_workspace_with_initiator — the detail page, workspace-scoped (HR-16)
# --------------------------------------------------------------------------- #


# [claude] PTX-TW-01
def test_ptx_tw_01__returns_pair_transaction_and_initiator_name(db, st):
    """PTX-TW-01 — returns the pair (transaction, initiator's name).
    Rules: `get_by_tran_id_and_workspace_with_initiator` R1, Returns"""
    a = st.txn(1, **PAID)
    st.txn(2)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

    # Then 1
    assert len(result) == 2
    # Then 2
    assert result[0].id == a.id
    # Then 3
    assert result[1] == "Rahim"


# [claude] PTX-TW-02
def test_ptx_tw_02__name_is_initiator_not_resolver(db, st):
    """PTX-TW-02 — the name is the initiator's, not the risk resolver's.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R1"""
    a = st.txn(
        1, initiated_by=st.U2.id, risk_resolved_by=st.U1.id, risk_resolved_at=T2, **PAID
    )

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[1] == "Karim"


# [claude] PTX-TW-03
def test_ptx_tw_03__row_without_initiator_has_name_none(db, st):
    """PTX-TW-03 — a row without an initiator is returned, with name None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R1 (name as `get_by_id_and_workspace_with_initiator` R2)"""
    a = st.txn(1, initiated_by=None)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[1] is None


# [claude] PTX-TW-04
def test_ptx_tw_04__tran_id_of_earlier_workspace_returns_none(db, st):
    """PTX-TW-04 — a tran_id of an earlier workspace returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2, HR-16"""
    st.txn(1, workspace_id=st.W0.id)
    st.txn(2)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-05
def test_ptx_tw_05__tran_id_of_later_workspace_returns_none(db, st):
    """PTX-TW-05 — a tran_id of a later workspace returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2, HR-16"""
    st.txn(1)
    st.txn(2, workspace_id=st.W2.id)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(2), workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-06
def test_ptx_tw_06__w1_tran_id_under_w0_or_w2_returns_none(db, st):
    """PTX-TW-06 — W1's tran_id asked for under W0 or W2 returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2, HR-16"""
    st.txn(1)

    result = [
        dao.get_by_tran_id_and_workspace_with_initiator(
            db, tran_id=st.tid(1), workspace_id=w
        )
        for w in (st.W0.id, st.W2.id)
    ]

    # Then 1
    assert result == [None, None]


# [claude] PTX-TW-07
def test_ptx_tw_07__unknown_tran_id_or_workspace_returns_none(db, st):
    """PTX-TW-07 — an unknown tran_id or workspace returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2"""
    st.txn(1)

    result = [
        dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=t, workspace_id=w)
        for t, w in ((st.tid(9), st.W1.id), (st.tid(1), MISSING))
    ]

    # Then 1
    assert result == [None, None]


# [claude] PTX-TW-08
def test_ptx_tw_08__empty_tran_id_returns_none(db, st):
    """PTX-TW-08 — an empty tran_id returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id="", workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-09
def test_ptx_tw_09__40_character_string_returns_none(db, st):
    """PTX-TW-09 — a 40-character string that starts with a tran_id returns None and raises nothing.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1) + "x" * 13, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-10
def test_ptx_tw_10__tran_id_in_capitals_returns_none(db, st):
    """PTX-TW-10 — the tran_id in capitals returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1).upper(), workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-11
def test_ptx_tw_11__trailing_space_returns_none(db, st):
    """PTX-TW-11 — the tran_id with a trailing space returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1) + " ", workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-12
def test_ptx_tw_12__underscore_is_no_wildcard(db, st):
    """PTX-TW-12 — "_" in place of one character is no wildcard.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1)[:5] + "_" + st.tid(1)[6:], workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-13
def test_ptx_tw_13__without_last_character_returns_none(db, st):
    """PTX-TW-13 — the tran_id without its last character returns None.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)"""
    st.txn(1)

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1)[:-1], workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] PTX-TW-14
def test_ptx_tw_14__risk_held_row_returned(db, st):
    """PTX-TW-14 — status does not matter: a risk-held row is returned.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R1"""
    a = st.txn(1, status="RISK_HOLD", risk_level=1, risk_title="Card from abroad")

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert result[0].status == "RISK_HOLD"


# [claude] PTX-TW-15
def test_ptx_tw_15__one_select_no_lock_nothing_written(db, st):
    """PTX-TW-15 — one SELECT, no lock, nothing written.
    Rules: `get_by_tran_id_and_workspace_with_initiator` R3"""
    a = st.txn(1)
    db.expunge_all()  # clear the session before a one-query check

    with StatementRecorder(db) as rec:
        result = dao.get_by_tran_id_and_workspace_with_initiator(
            db, tran_id=st.tid(1), workspace_id=st.W1.id
        )

    # Then 1
    assert result[0].id == a.id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part == ""
    # Then 4
    assert rec.written == []


# [claude] PTX-TW-16
def test_ptx_tw_16__writes_nothing(db, st):
    """PTX-TW-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_tran_id_and_workspace_with_initiator` Side effects"""
    a = st.txn(1)
    b = st.txn(2)
    b.cus_name = "Edited"
    p = st.pending(3)
    before = st.counts()

    result = dao.get_by_tran_id_and_workspace_with_initiator(
        db, tran_id=st.tid(1), workspace_id=st.W1.id
    )

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
    assert not db.deleted
    # Then 7
    assert st.counts() == before


# --------------------------------------------------------------------------- #
# list_by_workspace_with_initiator — the ledger list, newest first (BUG-2402: then id)
# --------------------------------------------------------------------------- #


# [claude] PTX-LW-01
def test_ptx_lw_01__only_w1_rows(db, st):
    """PTX-LW-01 — only W1's rows; newer rows of W0 and W2 are left out.
    Rules: `list_by_workspace_with_initiator` R1"""
    st.txn(1, workspace_id=st.W0.id, created_at=T4)
    a = st.txn(2, created_at=T1)
    st.txn(3, workspace_id=st.W2.id, created_at=T4)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert pairs(result) == [(a.id, "Rahim")]


# [claude] PTX-LW-02
def test_ptx_lw_02__w0_and_w2_each_get_own_row(db, st):
    """PTX-LW-02 — asked for W0 or W2, each gets only its own row.
    Rules: `list_by_workspace_with_initiator` R1"""
    x0 = st.txn(1, workspace_id=st.W0.id, created_at=T1)
    st.txn(2, created_at=T4)
    x2 = st.txn(3, workspace_id=st.W2.id, created_at=T1)

    result = [
        pairs(dao.list_by_workspace_with_initiator(db, workspace_id=w))
        for w in (st.W0.id, st.W2.id)
    ]

    # Then 1
    assert result == [[(x0.id, "Rahim")], [(x2.id, "Rahim")]]


# [claude] PTX-LW-03
def test_ptx_lw_03__every_status_listed(db, st):
    """PTX-LW-03 — every status is listed.
    Rules: `list_by_workspace_with_initiator` R1"""
    a = st.txn(1, created_at=T1)
    b = st.txn(2, created_at=T1 + timedelta(minutes=1), **PAID)
    c = st.txn(3, created_at=T1 + timedelta(minutes=2), status="VALIDATED_FAILED")
    d = st.txn(4, created_at=T1 + timedelta(minutes=3), status="CANCELLED")
    e = st.txn(5, created_at=T1 + timedelta(minutes=4), status="EXPIRED")
    f = st.txn(
        6,
        created_at=T1 + timedelta(minutes=5),
        status="RISK_HOLD",
        risk_level=1,
        risk_title="Card from abroad",
    )
    g = st.txn(7, created_at=T1 + timedelta(minutes=6), status="INIT_FAILED")

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert [t.id for t, _ in result] == [g.id, f.id, e.id, d.id, c.id, b.id, a.id]


# [claude] PTX-LW-04
def test_ptx_lw_04__empty_and_unknown_workspace_give_empty_list(db, st):
    """PTX-LW-04 — a workspace without payments, and an unknown workspace, give [].
    Rules: `list_by_workspace_with_initiator` R1"""
    st.txn(1, workspace_id=st.W0.id)

    result = [
        dao.list_by_workspace_with_initiator(db, workspace_id=w)
        for w in (st.W1.id, MISSING)
    ]

    # Then 1
    assert result == [[], []]


# [claude] PTX-LW-05
def test_ptx_lw_05__names_per_row_and_plain_2_tuples(db, st):
    """PTX-LW-05 — each name is the row's initiator's, or None without one; items are plain 2-tuples.
    Rules: `list_by_workspace_with_initiator` R2, Returns"""
    a = st.txn(1, created_at=T1)
    b = st.txn(
        2,
        created_at=T2,
        initiated_by=st.U2.id,
        risk_resolved_by=st.U1.id,
        risk_resolved_at=T3,
    )
    c = st.txn(3, created_at=T3, initiated_by=None)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert type(result) is list
    # Then 2
    assert [type(r) for r in result] == [tuple, tuple, tuple]
    # Then 3
    assert [len(r) for r in result] == [2, 2, 2]
    # Then 4
    assert pairs(result) == [(c.id, None), (b.id, "Karim"), (a.id, "Rahim")]


# [claude] PTX-LW-06
def test_ptx_lw_06__newest_created_at_first(db, st):
    """PTX-LW-06 — newest created_at first, whatever the ids.
    Rules: `list_by_workspace_with_initiator` R3"""
    b = st.txn(1, created_at=T2)
    d = st.txn(2, created_at=T4)
    a = st.txn(3, created_at=T1)
    c = st.txn(4, created_at=T3)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert [t.id for t, _ in result] == [d.id, c.id, b.id, a.id]


# [claude] PTX-LW-07
def test_ptx_lw_07__key_is_created_at(db, st):
    """PTX-LW-07 — the key is created_at, not initiated_at, updated_at, amount or tran_id.
    Rules: `list_by_workspace_with_initiator` R3"""
    a = st.txn(
        1, created_at=T1, initiated_at=T3, updated_at=T3, amount=Decimal("300.00")
    )
    b = st.txn(
        2, created_at=T3, initiated_at=T1, updated_at=T1, amount=Decimal("100.00")
    )
    c = st.txn(
        3, created_at=T2, initiated_at=T4, updated_at=T1, amount=Decimal("50.00")
    )

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert [t.id for t, _ in result] == [b.id, c.id, a.id]


# [claude] PTX-LW-08
def test_ptx_lw_08__tied_rows_each_once_between_newer_and_older(db, st):
    """PTX-LW-08 — on a tie, the tied rows each come once, between the newer and the older row.
    Rules: `list_by_workspace_with_initiator` R3, R4 (the part that holds today)"""
    a = st.txn(1, created_at=T2)
    o = st.txn(2, created_at=T1)
    n = st.txn(3, created_at=T3)
    b = st.txn(4, created_at=T2)
    c = st.txn(5, created_at=T2)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0][0].id == n.id
    # Then 3
    assert result[4][0].id == o.id
    # Then 4
    assert {t.id for t, _ in result[1:4]} == {a.id, b.id, c.id}


# [claude] PTX-LW-09
@pytest.mark.xfail(strict=False, reason=R2402)
def test_ptx_lw_09__tie_highest_id_first_after_update(db, st):
    """PTX-LW-09 — on a tie the highest id comes first, even after the lowest id was updated.
    Rules: `list_by_workspace_with_initiator` R4 [BUG-2402]"""
    a = st.txn(1, created_at=T2)
    b = st.txn(2, created_at=T2)
    c = st.txn(3, created_at=T2)
    st.seqscan()
    st.bump(a)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert [t.id for t, _ in result] == [c.id, b.id, a.id]


# [claude] PTX-LW-10
@pytest.mark.xfail(strict=False, reason=R2402)
def test_ptx_lw_10__tie_id_decides_over_other_columns(db, st):
    """PTX-LW-10 — on a tie the id decides, when tran_id, amount, name and the other times would sort otherwise.
    Rules: `list_by_workspace_with_initiator` R4 [BUG-2402]"""
    a = st.txn(
        3,
        created_at=T2,
        initiated_at=T3,
        updated_at=T1,
        amount=Decimal("100.00"),
        initiated_by=st.U2.id,
    )
    b = st.txn(
        1, created_at=T2, initiated_at=T1, updated_at=T3, amount=Decimal("300.00")
    )
    c = st.txn(
        2,
        created_at=T2,
        initiated_at=T2,
        updated_at=T2,
        amount=Decimal("200.00"),
        initiated_by=None,
    )
    st.seqscan()
    st.bump(a)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert pairs(result) == [(c.id, None), (b.id, "Rahim"), (a.id, "Karim")]


# [claude] PTX-LW-11
@pytest.mark.xfail(strict=False, reason=R2402)
def test_ptx_lw_11__tied_rows_paged_one_at_a_time(db, st):
    """PTX-LW-11 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: `list_by_workspace_with_initiator` R4, R5 [BUG-2402]"""
    a = st.txn(1, created_at=T2)
    b = st.txn(2, created_at=T2)
    c = st.txn(3, created_at=T2)
    d = st.txn(4, created_at=T2)
    e = st.txn(5, created_at=T2)
    st.seqscan()
    st.bump(a)
    st.bump(c)

    pages = [
        dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, skip=k, limit=1)
        for k in range(5)
    ]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0][0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] PTX-LW-12
@pytest.mark.xfail(strict=True, reason=R2402)
def test_ptx_lw_12__orders_by_created_at_then_id_descending(db, st):
    """PTX-LW-12 — the query orders by created_at, then id, both descending.
    Rules: `list_by_workspace_with_initiator` R3, R4 [BUG-2402]"""
    a = st.txn(1, created_at=T2)

    with StatementRecorder(db) as rec:
        result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert pairs(result) == [(a.id, "Rahim")]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "created_at" in rec.order_part
    # Then 4
    assert "payment_transactions.id" in rec.order_part
    # Then 5
    assert rec.order_part.index("created_at") < rec.order_part.index(
        "payment_transactions.id"
    )
    # Then 6
    assert rec.order_part.upper().count("DESC") == 2
    # Then 7
    assert rec.order_part.count(",") == 1


# [claude] PTX-LW-13
def test_ptx_lw_13__skip_and_limit_cut_a_page(db, st):
    """PTX-LW-13 — skip and limit cut a page out of the ordered list.
    Rules: `list_by_workspace_with_initiator` R5"""
    c = st.txn(1, created_at=T3)
    st.txn(2, created_at=T1)
    st.txn(3, created_at=T4 + timedelta(hours=1))
    st.txn(4, created_at=T2)
    d = st.txn(5, created_at=T4)

    result = dao.list_by_workspace_with_initiator(
        db, workspace_id=st.W1.id, skip=1, limit=2
    )

    # Then 1
    assert [t.id for t, _ in result] == [d.id, c.id]


# Given of PTX-LW-14 / LW-15: 101 rows b000 ... b100, one minute apart, one flush
def add_101_ledger_rows(db, st):
    for k in range(101):
        db.add(
            PaymentTransaction(
                workspace_id=st.W1.id,
                tran_id=f"b{k:03d}{st.TAG}",
                amount=Decimal("990.00"),
                currency="BDT",
                initiated_by=st.U1.id,
                initiated_at=T1,
                created_at=T1 + timedelta(minutes=k),
                updated_at=T1,
            )
        )
    db.flush()


# [claude] PTX-LW-14
def test_ptx_lw_14__defaults_give_100_newest_of_101(db, st):
    """PTX-LW-14 — with the defaults, 101 rows give the 100 newest.
    Rules: `list_by_workspace_with_initiator` R5 (default `limit=100`)"""
    add_101_ledger_rows(db, st)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0][0].tran_id == f"b100{st.TAG}"
    # Then 3
    assert result[99][0].tran_id == f"b001{st.TAG}"


# [claude] PTX-LW-15
def test_ptx_lw_15__limit_1000_gives_all_101(db, st):
    """PTX-LW-15 — limit=1000 gives all 101 rows.
    Rules: `list_by_workspace_with_initiator` R5"""
    add_101_ledger_rows(db, st)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[100][0].tran_id == f"b000{st.TAG}"


# [claude] PTX-LW-16
def test_ptx_lw_16__limit_0_returns_empty_list(db, st):
    """PTX-LW-16 — limit=0 returns an empty list.
    Rules: `list_by_workspace_with_initiator` R5"""
    st.txn(1)

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] PTX-LW-17
def test_ptx_lw_17__skip_past_end_and_just_short_of_it(db, st):
    """PTX-LW-17 — a skip past the end returns an empty list; a skip just short of it returns the last row.
    Rules: `list_by_workspace_with_initiator` R5"""
    a = st.txn(1, created_at=T1)
    st.txn(2, created_at=T2)

    result = [
        dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, skip=s)
        for s in (1, 2)
    ]

    # Then 1
    assert [[t.id for t, _ in page] for page in result] == [[a.id], []]


# [claude] PTX-LW-18
def test_ptx_lw_18__workspace_filter_before_the_page(db, st):
    """PTX-LW-18 — the workspace filter comes before the page: newer rows of W0 and W2 take no place.
    Rules: `list_by_workspace_with_initiator` R1, R5 (HR-5)"""
    st.txn(1, workspace_id=st.W0.id, created_at=T4)
    a = st.txn(2, created_at=T2)
    st.txn(3, created_at=T1)
    st.txn(4, workspace_id=st.W2.id, created_at=T3)

    result = dao.list_by_workspace_with_initiator(
        db, workspace_id=st.W1.id, skip=0, limit=1
    )

    # Then 1
    assert pairs(result) == [(a.id, "Rahim")]


# [claude] PTX-LW-19
def test_ptx_lw_19__negative_limit_raises_2201w(db, st):
    """PTX-LW-19 — a negative limit raises DataError 2201W.
    Rules: `list_by_workspace_with_initiator` R6, Errors row 1"""
    st.txn(1)
    before = st.counts()

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, limit=-1)
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 2
    assert st.counts() == before


# [claude] PTX-LW-20
def test_ptx_lw_20__negative_skip_raises_2201x(db, st):
    """PTX-LW-20 — a negative skip raises DataError 2201X.
    Rules: `list_by_workspace_with_initiator` R6, Errors row 1"""
    st.txn(1)
    before = st.counts()

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id, skip=-1)
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 2
    assert st.counts() == before


# [claude] PTX-LW-21
def test_ptx_lw_21__one_select_carries_names(db, st):
    """PTX-LW-21 — one SELECT carries the names, no lock, nothing written.
    Rules: `list_by_workspace_with_initiator` R7, R2"""
    a = st.txn(1, created_at=T1)
    b = st.txn(2, created_at=T2, initiated_by=st.U2.id)
    db.expunge_all()  # clear the session before a one-query check

    with StatementRecorder(db) as rec:
        result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert pairs(result) == [(b.id, "Karim"), (a.id, "Rahim")]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part == ""
    # Then 4
    assert rec.written == []


# [claude] PTX-LW-22
def test_ptx_lw_22__writes_nothing(db, st):
    """PTX-LW-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `list_by_workspace_with_initiator` Side effects"""
    a = st.txn(1)
    b = st.txn(2, workspace_id=st.W2.id)
    b.cus_name = "Edited"
    p = st.pending(3)
    before = st.counts()

    result = dao.list_by_workspace_with_initiator(db, workspace_id=st.W1.id)

    # Then 1
    assert pairs(result) == [(a.id, "Rahim")]
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
    assert st.counts() == before


# --------------------------------------------------------------------------- #
# get_stuck_initiated — the reconciliation sweep's batch, all workspaces, oldest first
# (BUG-2403: then id). Every test starts with clean2001.
# --------------------------------------------------------------------------- #


# [claude] PTX-SI-01
def test_ptx_si_01__initiated_rows_before_cutoff_oldest_first(db, st):
    """PTX-SI-01 — INITIATED rows started before the cutoff come back oldest first, whatever the ids.
    Rules: `get_stuck_initiated` R1, R3, Returns"""
    st.clean2001()
    b = st.txn(1, initiated_at=S2)
    c = st.txn(2, initiated_at=S3)
    a = st.txn(3, initiated_at=S1)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert type(result) is list
    # Then 2
    assert all(isinstance(r, PaymentTransaction) for r in result)
    # Then 3
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PTX-SI-02
def test_ptx_si_02__exactly_at_cutoff_left_out(db, st):
    """PTX-SI-02 — a row started exactly at the cutoff is left out; one microsecond earlier is kept.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=CUT)
    b = st.txn(2, initiated_at=CUT - US)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PTX-SI-03
def test_ptx_si_03__one_microsecond_after_cutoff_left_out(db, st):
    """PTX-SI-03 — a row started one microsecond after the cutoff is left out.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=CUT + US)
    b = st.txn(2, initiated_at=S1)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PTX-SI-04
def test_ptx_si_04__cutoff_compared_with_initiated_at(db, st):
    """PTX-SI-04 — the cutoff is compared with initiated_at, not created_at or updated_at.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    a = st.txn(1, initiated_at=S1, created_at=T1, updated_at=T1)
    st.txn(2, initiated_at=T1, created_at=S1, updated_at=S1)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PTX-SI-05
def test_ptx_si_05__lower_case_status_left_out(db, st):
    """PTX-SI-05 — status "initiated" in lower case is left out.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=S1, status="initiated")
    b = st.txn(2, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PTX-SI-06
def test_ptx_si_06__status_with_space_left_out(db, st):
    """PTX-SI-06 — a status with a leading or a trailing space is left out.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=S1, status=" INITIATED")
    st.txn(2, initiated_at=S1, status="INITIATED ")
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-SI-07
def test_ptx_si_07__partial_status_left_out(db, st):
    """PTX-SI-07 — a status that only starts with, or is part of, INITIATED is left out.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=S1, status="INITIATE")
    st.txn(2, initiated_at=S1, status="INITIATED_X")
    st.txn(3, initiated_at=S1, status="INITIATE_")
    d = st.txn(4, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [d.id]


# [claude] PTX-SI-08
def test_ptx_si_08__paid_row_left_out(db, st):
    """PTX-SI-08 — a paid row is left out.
    Rules: `get_stuck_initiated` R1"""
    st.clean2001()
    st.txn(1, initiated_at=S1, **PAID)
    b = st.txn(2, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [b.id]


# [claude] PTX-SI-09
def test_ptx_si_09__every_workspace_together_oldest_first(db, st):
    """PTX-SI-09 — rows of every workspace come back together, oldest first.
    Rules: `get_stuck_initiated` R2, R3"""
    st.clean2001()
    x2 = st.txn(1, workspace_id=st.W2.id, initiated_at=S1)
    a = st.txn(2, initiated_at=S3)
    x0 = st.txn(3, workspace_id=st.W0.id, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [x2.id, x0.id, a.id]


# [claude] PTX-SI-10
def test_ptx_si_10__tied_rows_each_once_between_older_and_newer(db, st):
    """PTX-SI-10 — on a tie, the tied rows each come once, between the older and the newer row.
    Rules: `get_stuck_initiated` R3 (the part that holds today)"""
    st.clean2001()
    a = st.txn(1, initiated_at=S2)
    n = st.txn(2, initiated_at=S3)
    o = st.txn(3, initiated_at=S1)
    b = st.txn(4, initiated_at=S2)
    c = st.txn(5, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == o.id
    # Then 3
    assert result[4].id == n.id
    # Then 4
    assert idset(result[1:4]) == {a.id, b.id, c.id}


# [claude] PTX-SI-11
@pytest.mark.xfail(strict=False, reason=R2403)
def test_ptx_si_11__tie_lowest_id_first_over_other_columns(db, st):
    """PTX-SI-11 — on a tie the lowest id comes first, when tran_id, amount and created_at would sort otherwise.
    Rules: `get_stuck_initiated` R3 [BUG-2403]"""
    st.clean2001()
    a = st.txn(
        3,
        initiated_at=S2,
        created_at=T3,
        amount=Decimal("300.00"),
        initiated_by=st.U2.id,
    )
    b = st.txn(1, initiated_at=S2, created_at=T1, amount=Decimal("100.00"))
    c = st.txn(
        2, initiated_at=S2, created_at=T2, amount=Decimal("200.00"), initiated_by=None
    )
    st.seqscan()
    st.bump(a)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PTX-SI-12
@pytest.mark.xfail(strict=False, reason=R2403)
def test_ptx_si_12__tie_across_workspaces_lowest_id_first(db, st):
    """PTX-SI-12 — on a tie across workspaces the lowest id comes first.
    Rules: `get_stuck_initiated` R2, R3 [BUG-2403]"""
    st.clean2001()
    x2 = st.txn(1, workspace_id=st.W2.id, initiated_at=S2)
    x0 = st.txn(2, workspace_id=st.W0.id, initiated_at=S2)
    a = st.txn(3, initiated_at=S2)
    st.seqscan()
    st.bump(x2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [x2.id, x0.id, a.id]


# [claude] PTX-SI-13
@pytest.mark.xfail(strict=False, reason=R2403)
def test_ptx_si_13__lowest_ids_fill_the_batch(db, st):
    """PTX-SI-13 — with more tied rows than the limit, the lowest ids fill the batch.
    Rules: `get_stuck_initiated` R3, R4 [BUG-2403]"""
    st.clean2001()
    a = st.txn(1, initiated_at=S2)
    b = st.txn(2, initiated_at=S2)
    st.txn(3, initiated_at=S2)
    st.seqscan()
    st.bump(a)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] PTX-SI-14
@pytest.mark.xfail(strict=True, reason=R2403)
def test_ptx_si_14__orders_by_initiated_at_then_id_ascending(db, st):
    """PTX-SI-14 — the query orders by initiated_at, then id, both ascending.
    Rules: `get_stuck_initiated` R3 [BUG-2403]"""
    st.clean2001()
    a = st.txn(1, initiated_at=S1)

    with StatementRecorder(db) as rec:
        result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "initiated_at" in rec.order_part
    # Then 4
    assert "payment_transactions.id" in rec.order_part
    # Then 5
    assert rec.order_part.index("initiated_at") < rec.order_part.index(
        "payment_transactions.id"
    )
    # Then 6
    assert "DESC" not in rec.order_part.upper()
    # Then 7
    assert rec.order_part.count(",") == 1


# [claude] PTX-SI-15
def test_ptx_si_15__limit_2_gives_two_oldest(db, st):
    """PTX-SI-15 — limit=2 with three stuck rows gives the two oldest.
    Rules: `get_stuck_initiated` R4"""
    st.clean2001()
    st.txn(1, initiated_at=S3)
    a = st.txn(2, initiated_at=S1)
    b = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=2)

    # Then 1
    assert ids(result) == [a.id, b.id]


# Given of PTX-SI-16 / SI-17: 201 stuck rows b000 ... b200, one minute apart from OLD, one flush
def add_201_stuck_rows(db, st):
    for k in range(201):
        db.add(
            PaymentTransaction(
                workspace_id=st.W1.id,
                tran_id=f"b{k:03d}{st.TAG}",
                amount=Decimal("990.00"),
                currency="BDT",
                initiated_by=st.U1.id,
                initiated_at=OLD + timedelta(minutes=k),
                created_at=T1,
                updated_at=T1,
            )
        )
    db.flush()


# [claude] PTX-SI-16
def test_ptx_si_16__default_limit_gives_200_oldest_of_201(db, st):
    """PTX-SI-16 — with the default limit, 201 stuck rows give the 200 oldest.
    Rules: `get_stuck_initiated` R4 (default `limit=200`)"""
    st.clean2001()
    add_201_stuck_rows(db, st)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert len(result) == 200
    # Then 2
    assert result[0].tran_id == f"b000{st.TAG}"
    # Then 3
    assert result[199].tran_id == f"b199{st.TAG}"


# [claude] PTX-SI-17
def test_ptx_si_17__limit_1000_gives_all_201(db, st):
    """PTX-SI-17 — limit=1000 gives all 201 stuck rows.
    Rules: `get_stuck_initiated` R4"""
    st.clean2001()
    add_201_stuck_rows(db, st)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=1000)

    # Then 1
    assert len(result) == 201
    # Then 2
    assert result[200].tran_id == f"b200{st.TAG}"


# [claude] PTX-SI-18
def test_ptx_si_18__limit_0_returns_empty_list(db, st):
    """PTX-SI-18 — limit=0 returns an empty list.
    Rules: `get_stuck_initiated` R4"""
    st.clean2001()
    st.txn(1, initiated_at=S1)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=0)

    # Then 1
    assert result == []


# [claude] PTX-SI-19
def test_ptx_si_19__negative_limit_raises_2201w(db, st):
    """PTX-SI-19 — a negative limit raises DataError 2201W.
    Rules: `get_stuck_initiated` R4, Errors row 1"""
    st.clean2001()
    st.txn(1, initiated_at=S1)
    before = st.counts()

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_stuck_initiated(db, older_than=CUT, limit=-1)
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 2
    assert st.counts() == before


# [claude] PTX-SI-20
def test_ptx_si_20__filters_before_the_limit(db, st):
    """PTX-SI-20 — the filters come before the limit: older rows that are not candidates take no place.
    Rules: `get_stuck_initiated` R1, R4 (HR-5)"""
    st.clean2001()
    st.txn(1, initiated_at=OLD, **PAID)
    st.txn(2, initiated_at=OLD, status="initiated")
    c = st.txn(3, initiated_at=S2)
    st.txn(4, initiated_at=S3)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-SI-21
def test_ptx_si_21__one_select_no_lock_nothing_written(db, st):
    """PTX-SI-21 — one SELECT, no lock, nothing written.
    Rules: `get_stuck_initiated` R5"""
    st.clean2001()
    a = st.txn(1, initiated_at=S1)

    with StatementRecorder(db) as rec:
        result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert rec.lock_part == ""
    # Then 4
    assert rec.written == []


# [claude] PTX-SI-22
def test_ptx_si_22__writes_nothing(db, st):
    """PTX-SI-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_stuck_initiated` Side effects"""
    st.clean2001()
    a = st.txn(1, initiated_at=S1)
    b = st.txn(2, initiated_at=T1)
    b.cus_name = "Edited"
    p = st.pending(3, initiated_at=S2, created_at=T1, updated_at=T1)
    before = st.counts()

    result = dao.get_stuck_initiated(db, older_than=CUT)

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
    assert not db.deleted
    # Then 7
    assert st.counts() == before


# [claude] PTX-SI-23
def test_ptx_si_23__naive_cutoff_compared_as_stored(db, st):
    """PTX-SI-23 — a naive cutoff is compared as stored, whatever the session's time zone.
    Rules: `get_stuck_initiated` R6"""
    st.clean2001()
    st.zone("Asia/Dhaka")
    a = st.txn(1, initiated_at=CUT - US)
    st.txn(2, initiated_at=CUT)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PTX-SI-24
def test_ptx_si_24__aware_utc_cutoff_under_utc_session(db, st):
    """PTX-SI-24 — an aware UTC cutoff under a UTC session splits at the same instant.
    Rules: `get_stuck_initiated` R6"""
    st.clean2001()
    st.zone("UTC")
    a = st.txn(1, initiated_at=CUT - US)
    st.txn(2, initiated_at=CUT)

    result = dao.get_stuck_initiated(db, older_than=CUTZ)

    # Then 1
    assert ids(result) == [a.id]


# [claude] PTX-SI-25
def test_ptx_si_25__aware_cutoff_under_dhaka_read_in_dhaka_time(db, st):
    """PTX-SI-25 — an aware cutoff under Asia/Dhaka is read in Dhaka time (today's documented behaviour).
    Rules: `get_stuck_initiated` R6"""
    st.clean2001()
    st.zone("Asia/Dhaka")
    a = st.txn(1, initiated_at=datetime(2001, 3, 1, 17, 59, 59, 999999))
    st.txn(2, initiated_at=datetime(2001, 3, 1, 18, 0, 0))
    c = st.txn(3, initiated_at=S3)

    result = dao.get_stuck_initiated(db, older_than=CUTZ)

    # Then 1
    assert ids(result) == [c.id, a.id]


# --------------------------------------------------------------------------- #
# Deferred to the payment portal — OQ-25 (get_stuck_initiated R7, today's behaviour)
# When the portal decides which closed rows the sweep re-checks, only these
# six tests change.
# --------------------------------------------------------------------------- #


# [claude] PTX-OQ25-01
def test_ptx_oq25_01__expired_rows_not_candidates(db, st):
    """PTX-OQ25-01 — EXPIRED rows, recent or old, are not candidates.
    Rules: `get_stuck_initiated` R7 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(1, initiated_at=OLD, status="EXPIRED")
    st.txn(2, initiated_at=S3, status="EXPIRED")
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-OQ25-02
def test_ptx_oq25_02__cancelled_rows_not_candidates(db, st):
    """PTX-OQ25-02 — CANCELLED rows, recent or old, are not candidates.
    Rules: `get_stuck_initiated` R7 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(1, initiated_at=OLD, status="CANCELLED")
    st.txn(2, initiated_at=S3, status="CANCELLED")
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-OQ25-03
def test_ptx_oq25_03__validated_failed_rows_not_candidates(db, st):
    """PTX-OQ25-03 — VALIDATED_FAILED rows, recent or old, are not candidates.
    Rules: `get_stuck_initiated` R7 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(1, initiated_at=OLD, status="VALIDATED_FAILED", val_id="val-fail-1")
    st.txn(2, initiated_at=S3, status="VALIDATED_FAILED")
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-OQ25-04
def test_ptx_oq25_04__init_failed_rows_not_candidates(db, st):
    """PTX-OQ25-04 — INIT_FAILED rows are not candidates.
    Rules: `get_stuck_initiated` R7 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(1, initiated_at=OLD, status="INIT_FAILED")
    st.txn(2, initiated_at=S3, status="INIT_FAILED")
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-OQ25-05
def test_ptx_oq25_05__risk_hold_rows_not_candidates(db, st):
    """PTX-OQ25-05 — RISK_HOLD rows are not candidates.
    Rules: `get_stuck_initiated` R7 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(
        1,
        initiated_at=OLD,
        status="RISK_HOLD",
        val_id="val-hold-1",
        risk_level=1,
        risk_title="Card from abroad",
        validated_at=S1,
    )
    st.txn(
        2,
        initiated_at=S3,
        status="RISK_HOLD",
        val_id="val-hold-2",
        risk_level=1,
        risk_title="Card from abroad",
        validated_at=S3,
    )
    c = st.txn(3, initiated_at=S2)

    result = dao.get_stuck_initiated(db, older_than=CUT)

    # Then 1
    assert ids(result) == [c.id]


# [claude] PTX-OQ25-06
def test_ptx_oq25_06__older_closed_rows_take_no_place_in_batch_of_one(db, st):
    """PTX-OQ25-06 — older closed rows take no place in a batch of one.
    Rules: `get_stuck_initiated` R7, R4 (deferred: OQ-25)"""
    st.clean2001()
    st.txn(1, initiated_at=S1, status="EXPIRED")
    st.txn(2, initiated_at=S1, status="CANCELLED")
    st.txn(3, initiated_at=S1, status="VALIDATED_FAILED")
    d = st.txn(4, initiated_at=S3)

    result = dao.get_stuck_initiated(db, older_than=CUT, limit=1)

    # Then 1
    assert ids(result) == [d.id]
