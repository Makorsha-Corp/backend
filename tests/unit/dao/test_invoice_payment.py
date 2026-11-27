"""Unit tests for app/dao/invoice_payment.py.

Implements tests/unit/dao/invoice_payment.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is mocked and
no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment, and every numbered Then line is a `# Then N` comment before its
assertions.

Conventions mapping (card says -> code):
  W0, W1, W2, U1 "Rahim", U2 "Karim", U3 "Salma" -> `st.W0` ... `st.U3` (autouse fixture `st`)
  AC0, AC1, AC2; N0, NA, N1, NB, N9                -> `st.AC0` ...; `st.N0`, `st.NA`, `st.N1`, `st.NB`, `st.N9`
  payment, but ... / voided, but ...              -> `st.payment(**cols)` / `st.voided(**cols)`
  bump(X)                                         -> `st.bump(X)`
  Dhaka / NewYork                                 -> `st.zone("Asia/Dhaka")` / `st.zone("America/New_York")`
  re-read X                                       -> `st.reread(X.id)`
  nothing written                                 -> `before = st.counts()` ... `assert st.counts() == before`
  tids / tidset / names                           -> `tids(result)`, `tidset(result)`, `names(result)`
  close to now                                    -> `close_to_now(value, now)`, `now = utcnow()` right after the When
  Statement recorder                              -> `with StatementRecorder(db) as rec:` around the When
  commit spy                                      -> `sp = db.begin_nested()` + `patch.object(db, "commit", wraps=db.commit)`
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, naive datetimes, and the cards' Decimal("100") literal)
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.invoice_payment import invoice_payment_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.invoice_payment import InvoicePayment
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

dao = invoice_payment_dao

MISSING = 999999999
D1 = date(2026, 3, 1)
D2 = date(2026, 3, 2)
D3 = date(2026, 3, 3)
D4 = date(2026, 3, 4)
D5 = date(2026, 3, 5)
T1 = datetime(2026, 3, 6, 9, 0, 0)

R600 = "BUG-600: Invoice payment list ordered by date only, no tie-breaker"
R2400 = "BUG-2400: A payment's \"recorded at\" time is the database's local clock"


# --------------------------------------------------------------------------- #
# Conventions -> standing rows, Given rows and steps
# --------------------------------------------------------------------------- #


class Standing:
    """Standing rows: W0 < W1 < W2; U1 "Rahim", U2 "Karim", U3 "Salma";
    accounts AC0, AC1, AC2; invoices N0 (W0), NA, N1, NB (W1, ids rising), N9 (W2)."""

    def __init__(self, db):
        self.db = db
        self.TAG = uuid.uuid4().hex[:8]
        self.W0 = make_workspace(db)
        self.W1 = make_workspace(db)
        self.W2 = make_workspace(db)
        self.U1 = make_profile(db, name="Rahim")
        self.U2 = make_profile(db, name="Karim")
        self.U3 = make_profile(db, name="Salma")
        self.AC0 = self._add(Account(workspace_id=self.W0.id, name=f"Acme {self.TAG}"))
        self.AC1 = self._add(Account(workspace_id=self.W1.id, name=f"Acme {self.TAG}"))
        self.AC2 = self._add(Account(workspace_id=self.W2.id, name=f"Acme {self.TAG}"))
        self.N0 = self._invoice(self.W0, self.AC0)
        self.NA = self._invoice(self.W1, self.AC1)
        self.N1 = self._invoice(self.W1, self.AC1)
        self.NB = self._invoice(self.W1, self.AC1)
        self.N9 = self._invoice(self.W2, self.AC2)

    def _add(self, row):
        self.db.add(row)
        self.db.flush()
        return row

    def _invoice(self, ws, account):
        return self._add(
            AccountInvoice(
                workspace_id=ws.id,
                account_id=account.id,
                invoice_type="payable",
                invoice_amount=Decimal("100"),
                invoice_date=D1,
            )
        )

    # Convention "payment": 10.00 on N1 of W1, dated D2, recorded by U1
    def payment(self, **cols):
        fields = {
            "workspace_id": self.W1.id,
            "invoice_id": self.N1.id,
            "payment_amount": Decimal("10.00"),
            "payment_date": D2,
            "created_by": self.U1.id,
        }
        fields.update(cols)
        return self._add(InvoicePayment(**fields))

    # Convention "voided": a payment with all four void fields written
    def voided(self, **cols):
        fields = {
            "is_voided": True,
            "voided_at": T1,
            "voided_by": self.U2.id,
            "void_note": "Duplicate",
        }
        fields.update(cols)
        return self.payment(**fields)

    # The unflushed payment P of the writes-nothing cards
    def pending(self, **cols):
        fields = {
            "workspace_id": self.W1.id,
            "invoice_id": self.N1.id,
            "payment_amount": Decimal("7.00"),
            "payment_date": D5,
            "created_by": self.U1.id,
        }
        fields.update(cols)
        row = InvoicePayment(**fields)
        self.db.add(row)
        return row

    # Convention "bump(X)": moves X's row to the end of the table
    def bump(self, row):
        self.db.execute(
            text("UPDATE invoice_payments SET notes = 'x' WHERE id = :i"), {"i": row.id}
        )
        self.db.expire_all()

    # Convention "Dhaka" / "NewYork"
    def zone(self, z):
        self.db.execute(text(f"SET LOCAL TimeZone = '{z}'"))

    # Convention "re-read X"
    def reread(self, row_id):
        self.db.expire_all()
        return self.db.get(InvoicePayment, row_id)

    def count_ws(self, workspace_id):
        return self.db.scalar(
            text("SELECT count(*) FROM invoice_payments WHERE workspace_id = :w"),
            {"w": workspace_id},
        )

    def count_id(self, payment_id):
        return self.db.scalar(
            text("SELECT count(*) FROM invoice_payments WHERE id = :i"),
            {"i": payment_id},
        )

    # Convention "nothing written": invoice_payments and account_invoices, all workspaces
    def counts(self):
        return {
            "invoice_payments": self.db.scalar(
                text("SELECT count(*) FROM invoice_payments")
            ),
            "account_invoices": self.db.scalar(
                text("SELECT count(*) FROM account_invoices")
            ),
        }


@pytest.fixture(autouse=True)
def st(db):
    """Standing rows (Conventions), made in the order written."""
    return Standing(db)


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers
# --------------------------------------------------------------------------- #


def tids(result):
    return [r[0].id for r in result]


def tidset(result):
    return {r[0].id for r in result}


def names(result):
    return [r[1] for r in result]


# Convention "close to now"
def close_to_now(value, now):
    return abs(value - now) < timedelta(minutes=1)


# The create payload most CR cards use
def new_payment(st, **overrides):
    fields = {
        "workspace_id": st.W1.id,
        "invoice_id": st.N1.id,
        "payment_amount": Decimal("25.50"),
        "payment_date": D3,
        "created_by": st.U1.id,
    }
    fields.update(overrides)
    return fields


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
        """The one SELECT from invoice_payments; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects if "FROM invoice_payments" in s]
        return statement

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0].split("OFFSET", 1)[0]

    @property
    def lock_part(self):
        sql = self.sql
        if "FOR UPDATE" not in sql:
            return ""
        return sql.split("FOR UPDATE", 1)[1]


# --------------------------------------------------------------------------- #
# get_by_invoice
# --------------------------------------------------------------------------- #


# [claude] IVP-GI-01
def test_ivp_gi_01__pairs_newest_date_first_voided_included(db, st):
    """IVP-GI-01 — an invoice's payments come back as (payment, name) pairs, newest date first, voided included.
    Rules: `get_by_invoice` R1, R2, R3"""
    p1 = st.payment(payment_date=D1)
    p2 = st.payment(payment_date=D3)
    p3 = st.voided(payment_date=D2)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p2.id, p3.id, p1.id]
    # Then 2
    assert names(result) == ["Rahim", "Rahim", "Rahim"]
    # Then 3
    assert type(result) is list


# [claude] IVP-GI-02
def test_ivp_gi_02__each_element_is_plain_2_tuple(db, st):
    """IVP-GI-02 — each element is a plain 2-tuple of the payment and the name.
    Rules: `get_by_invoice` Returns"""
    st.payment()

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert type(result[0]) is tuple
    # Then 3
    assert len(result[0]) == 2
    # Then 4
    assert isinstance(result[0][0], InvoicePayment)
    # Then 5
    assert result[0][0].payment_amount == Decimal("10.00")
    # Then 6
    assert result[0][1] == "Rahim"


# [claude] IVP-GI-03
def test_ivp_gi_03__voided_payment_listed_with_void_fields(db, st):
    """IVP-GI-03 — a voided payment is listed with its void fields.
    Rules: `get_by_invoice` R1"""
    p1 = st.voided()

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]
    # Then 2
    assert result[0][0].is_voided is True
    assert result[0][0].voided_at == T1
    assert result[0][0].voided_by == st.U2.id
    assert result[0][0].void_note == "Duplicate"


# [claude] IVP-GI-04
def test_ivp_gi_04__neighbour_invoices_not_listed(db, st):
    """IVP-GI-04 — payments of the invoices just below and just above are not listed.
    Rules: `get_by_invoice` R1"""
    st.payment(invoice_id=st.NA.id, payment_date=D4)
    p1 = st.payment(payment_date=D2)
    st.payment(invoice_id=st.NB.id, payment_date=D5)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]


# [claude] IVP-GI-05
def test_ivp_gi_05__w0_payment_on_invoice_not_listed(db, st):
    """IVP-GI-05 — a payment of the lower workspace W0 on this invoice is not listed.
    Rules: `get_by_invoice` R1"""
    st.payment(workspace_id=st.W0.id, payment_date=D5)
    p1 = st.payment(payment_date=D2)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]


# [claude] IVP-GI-06
def test_ivp_gi_06__w2_payment_on_invoice_not_listed(db, st):
    """IVP-GI-06 — a payment of the higher workspace W2 on this invoice is not listed.
    Rules: `get_by_invoice` R1"""
    p1 = st.payment(payment_date=D2)
    st.payment(workspace_id=st.W2.id, payment_date=D5)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]


# [claude] IVP-GI-07
def test_ivp_gi_07__asked_for_w2_only_w2_row(db, st):
    """IVP-GI-07 — asked for W2, only W2's row on the invoice is listed, though W1's row is earlier.
    Rules: `get_by_invoice` R1"""
    st.payment(payment_date=D2)
    x2 = st.payment(workspace_id=st.W2.id, payment_date=D1)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W2.id)

    # Then 1
    assert tids(result) == [x2.id]


# [claude] IVP-GI-08
def test_ivp_gi_08__invoice_without_payments_empty(db, st):
    """IVP-GI-08 — an invoice without payments gives an empty list.
    Rules: `get_by_invoice` R1"""
    st.payment(invoice_id=st.NA.id)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] IVP-GI-09
def test_ivp_gi_09__unknown_invoice_empty(db, st):
    """IVP-GI-09 — an unknown invoice id gives an empty list.
    Rules: `get_by_invoice` R1"""
    st.payment()

    result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] IVP-GI-10
def test_ivp_gi_10__invoice_id_0_empty(db, st):
    """IVP-GI-10 — invoice id 0 gives an empty list and raises nothing.
    Rules: `get_by_invoice` R1"""
    st.payment()

    result = dao.get_by_invoice(db, invoice_id=0, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] IVP-GI-11
def test_ivp_gi_11__w2_invoice_under_w1_empty(db, st):
    """IVP-GI-11 — W2's invoice asked under W1 gives an empty list.
    Rules: `get_by_invoice` R1"""
    st.payment(workspace_id=st.W2.id, invoice_id=st.N9.id)

    result = dao.get_by_invoice(db, invoice_id=st.N9.id, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] IVP-GI-12
def test_ivp_gi_12__name_is_recorder_or_none(db, st):
    """IVP-GI-12 — the name is each recorder's profile name, or None without a recorder.
    Rules: `get_by_invoice` R2"""
    p1 = st.payment(payment_date=D3, created_by=st.U2.id)
    p2 = st.payment(payment_date=D2, created_by=None)
    p3 = st.payment(payment_date=D1, created_by=st.U3.id)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id, p2.id, p3.id]
    # Then 2
    assert names(result) == ["Karim", None, "Salma"]


# [claude] IVP-GI-13
def test_ivp_gi_13__name_is_recorder_not_voider(db, st):
    """IVP-GI-13 — the name is the recorder's, not the voider's.
    Rules: `get_by_invoice` R2"""
    p1 = st.voided(created_by=st.U3.id)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]
    # Then 2
    assert names(result) == ["Salma"]


# [claude] IVP-GI-14
def test_ivp_gi_14__newest_date_first_whatever_ids_and_amounts(db, st):
    """IVP-GI-14 — newest date first, whatever the ids and amounts.
    Rules: `get_by_invoice` R3"""
    p1 = st.payment(payment_date=D1, payment_amount=Decimal("90.00"))
    p2 = st.payment(payment_date=D4, payment_amount=Decimal("10.00"))
    p3 = st.payment(payment_date=D2, payment_amount=Decimal("50.00"))
    p4 = st.payment(payment_date=D3, payment_amount=Decimal("5.00"))

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p2.id, p4.id, p3.id, p1.id]


# [claude] IVP-GI-15
def test_ivp_gi_15__tied_payments_between_newer_and_older(db, st):
    """IVP-GI-15 — tied payments sit between the newer and the older one, each once.
    Rules: `get_by_invoice` R3"""
    po = st.payment(payment_date=D1)
    pa = st.payment(payment_date=D3)
    pn = st.payment(payment_date=D5)
    pb = st.payment(payment_date=D3)
    st.bump(pa)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert tids(result)[0] == pn.id
    # Then 3
    assert tids(result)[3] == po.id
    # Then 4
    assert set(tids(result)[1:3]) == {pa.id, pb.id}


# [claude] IVP-GI-16
@pytest.mark.xfail(strict=False, reason=R600)
def test_ivp_gi_16__one_date_highest_id_first(db, st):
    """IVP-GI-16 — payments of one date: the highest id first, when the lowest id was updated.
    Rules: `get_by_invoice` R3 [BUG-600]"""
    p1 = st.payment(payment_date=D2)
    p2 = st.payment(payment_date=D2)
    p3 = st.payment(payment_date=D2)
    p4 = st.payment(payment_date=D2)
    st.bump(p1)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert tids(result) == [p4.id, p3.id, p2.id, p1.id]


# [claude] IVP-GI-17
@pytest.mark.xfail(strict=False, reason=R600)
def test_ivp_gi_17__one_date_id_decides(db, st):
    """IVP-GI-17 — payments of one date: the id decides, not amount, creator, method or void state.
    Rules: `get_by_invoice` R3 [BUG-600]"""
    p1 = st.payment(
        payment_date=D2,
        payment_amount=Decimal("50.00"),
        created_by=st.U2.id,
        payment_method="cash",
    )
    p2 = st.voided(
        payment_date=D2,
        payment_amount=Decimal("90.00"),
        created_by=st.U3.id,
        payment_method="bank",
    )
    p3 = st.payment(
        payment_date=D2, payment_amount=Decimal("5.00"), payment_method="Card"
    )
    st.bump(p1)
    st.bump(p3)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert tids(result) == [p3.id, p2.id, p1.id]


# [claude] IVP-GI-18
@pytest.mark.xfail(strict=False, reason=R600)
def test_ivp_gi_18__one_date_paged_one_at_a_time(db, st):
    """IVP-GI-18 — payments of one date paged one at a time neither repeat nor miss a row.
    Rules: `get_by_invoice` R3, R4 [BUG-600]"""
    p1, p2, p3, p4, p5 = (st.payment(payment_date=D2) for _ in range(5))
    st.bump(p1)
    st.bump(p3)

    pages = [
        dao.get_by_invoice(
            db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=k, limit=1
        )
        for k in range(5)
    ]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0][0].id for p in pages] == [p5.id, p4.id, p3.id, p2.id, p1.id]


# [claude] IVP-GI-19
@pytest.mark.xfail(strict=True, reason=R600)
def test_ivp_gi_19__orders_by_payment_date_then_id_descending(db, st):
    """IVP-GI-19 — the query orders by payment_date, then id, both descending.
    Rules: `get_by_invoice` R3 [BUG-600]"""
    p1 = st.payment()

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "payment_date" in rec.order_part
    # Then 4
    assert "invoice_payments.id" in rec.order_part
    # Then 5
    assert rec.order_part.index("payment_date") < rec.order_part.index(
        "invoice_payments.id"
    )
    # Then 6
    assert rec.order_part.upper().count("DESC") == 2
    # Then 7
    assert rec.order_part.count(",") == 1


# [claude] IVP-GI-20
def test_ivp_gi_20__one_statement_left_outer_join(db, st):
    """IVP-GI-20 — one statement, the creator joined with a LEFT OUTER JOIN.
    Rules: `get_by_invoice` R5"""
    st.payment(payment_date=D2)
    st.payment(payment_date=D1, created_by=None)
    n1_id, w1_id = (
        st.N1.id,
        st.W1.id,
    )  # read before expiring: an expired id would reload its row
    db.expire_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice(db, invoice_id=n1_id, workspace_id=w1_id)
        n = names(result)

    # Then 1
    assert n == ["Rahim", None]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "LEFT OUTER JOIN profiles" in rec.sql


# [claude] IVP-GI-21
def test_ivp_gi_21__no_lock(db, st):
    """IVP-GI-21 — no lock is taken.
    Rules: `get_by_invoice` R5"""
    p1 = st.payment()

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]
    # Then 2
    assert "FOR UPDATE" not in rec.sql
    # Then 3
    assert rec.lock_part == ""


# [claude] IVP-GI-22
def test_ivp_gi_22__invoice_row_not_read(db, st):
    """IVP-GI-22 — the invoice row is not read: the query does not touch account_invoices.
    Rules: `get_by_invoice` R5"""
    p1 = st.payment()

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [p1.id]
    # Then 2
    assert "account_invoices" not in rec.sql
    # Then 3
    assert len(rec.selects) == 1


# Given of IVP-GI-23 / GI-24: 101 payments, payment k dated 2026-01-01 + k days
def add_101_payments(st):
    for k in range(101):
        st.payment(payment_date=date(2026, 1, 1) + timedelta(days=k))


# [claude] IVP-GI-23
def test_ivp_gi_23__default_limit_gives_100_of_101(db, st):
    """IVP-GI-23 — with the default limit, 101 payments give 100.
    Rules: `get_by_invoice` R4"""
    add_101_payments(st)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0][0].payment_date == date(2026, 4, 11)
    # Then 3
    assert result[99][0].payment_date == date(2026, 1, 2)


# [claude] IVP-GI-24
def test_ivp_gi_24__limit_1000_gives_all_101(db, st):
    """IVP-GI-24 — limit=1000 gives all 101.
    Rules: `get_by_invoice` R4"""
    add_101_payments(st)

    result = dao.get_by_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id, limit=1000
    )

    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[100][0].payment_date == date(2026, 1, 1)


# [claude] IVP-GI-25
def test_ivp_gi_25__skip_1_limit_2(db, st):
    """IVP-GI-25 — skip=1, limit=2 gives the second and third by date.
    Rules: `get_by_invoice` R4"""
    p1 = st.payment(payment_date=D3)
    st.payment(payment_date=D1)
    st.payment(payment_date=D4)
    p4 = st.payment(payment_date=D2)

    result = dao.get_by_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=1, limit=2
    )

    # Then 1
    assert tids(result) == [p1.id, p4.id]


# [claude] IVP-GI-26
def test_ivp_gi_26__limit_0_empty(db, st):
    """IVP-GI-26 — limit=0 gives an empty list.
    Rules: `get_by_invoice` R4"""
    st.payment()

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] IVP-GI-27
def test_ivp_gi_27__skip_past_end_empty(db, st):
    """IVP-GI-27 — skip past the end gives an empty list.
    Rules: `get_by_invoice` R4"""
    st.payment(payment_date=D1)
    st.payment(payment_date=D2)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=2)

    # Then 1
    assert result == []


# [claude] IVP-GI-28
def test_ivp_gi_28__skip_1_gives_older(db, st):
    """IVP-GI-28 — skip=1 with two payments gives the older one.
    Rules: `get_by_invoice` R4"""
    p1 = st.payment(payment_date=D1)
    st.payment(payment_date=D2)

    result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=1)

    # Then 1
    assert tids(result) == [p1.id]


# [claude] IVP-GI-29
def test_ivp_gi_29__negative_limit_raises(db, st):
    """IVP-GI-29 — a negative limit raises DataError.
    Rules: `get_by_invoice` R4, Errors"""
    st.payment()
    before = st.counts()

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id, limit=-1)
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert st.counts() == before


# [claude] IVP-GI-30
def test_ivp_gi_30__negative_skip_raises(db, st):
    """IVP-GI-30 — a negative skip raises DataError.
    Rules: `get_by_invoice` R4, Errors"""
    st.payment()
    before = st.counts()

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=-1)
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert st.counts() == before


# [claude] IVP-GI-31
def test_ivp_gi_31__invoice_filter_before_page(db, st):
    """IVP-GI-31 — the invoice filter comes before the page: a newer payment of another invoice takes no place.
    Rules: `get_by_invoice` R1, R4"""
    st.payment(payment_date=D2)
    p2 = st.payment(payment_date=D1)
    st.payment(invoice_id=st.NB.id, payment_date=D5)

    result = dao.get_by_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=1, limit=1
    )

    # Then 1
    assert tids(result) == [p2.id]


# [claude] IVP-GI-32
def test_ivp_gi_32__workspace_filter_before_page(db, st):
    """IVP-GI-32 — the workspace filter comes before the page: a newer W2 payment on this invoice takes no place.
    Rules: `get_by_invoice` R1, R4"""
    st.payment(payment_date=D2)
    p2 = st.payment(payment_date=D1)
    st.payment(workspace_id=st.W2.id, payment_date=D5)

    result = dao.get_by_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id, skip=1, limit=1
    )

    # Then 1
    assert tids(result) == [p2.id]


# [claude] IVP-GI-33
def test_ivp_gi_33__writes_nothing(db, st):
    """IVP-GI-33 — writes nothing: a pending payment stays pending and is not listed, an unflushed edit stays unflushed.
    Rules: `get_by_invoice` Side effects"""
    b = st.payment(payment_date=D1)
    b.notes = "Edited"
    p = st.pending()

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice(db, invoice_id=st.N1.id, workspace_id=st.W1.id)

    # Then 1
    assert tids(result) == [b.id]
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
    assert rec.written == []


# --------------------------------------------------------------------------- #
# get_by_id_and_workspace_with_creator
# --------------------------------------------------------------------------- #


# [claude] IVP-GC-01
def test_ivp_gc_01__plain_tuple_payment_and_name(db, st):
    """IVP-GC-01 — the workspace's payment comes back as a plain (payment, name) tuple.
    Rules: `get_by_id_and_workspace_with_creator` R1, Returns"""
    p1 = st.payment(payment_amount=Decimal("12.34"))

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=p1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert type(result) is tuple
    # Then 2
    assert len(result) == 2
    # Then 3
    assert result[0].id == p1.id
    # Then 4
    assert result[0].payment_amount == Decimal("12.34")
    # Then 5
    assert result[1] == "Rahim"


# [claude] IVP-GC-02
def test_ivp_gc_02__id_decides_not_neighbours(db, st):
    """IVP-GC-02 — the id itself decides: neighbours with lower and higher ids are not returned.
    Rules: `get_by_id_and_workspace_with_creator` R1"""
    st.payment(created_by=st.U2.id)
    p2 = st.payment(created_by=st.U3.id)
    st.payment()

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=p2.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == p2.id
    # Then 2
    assert result[1] == "Salma"


# [claude] IVP-GC-03
def test_ivp_gc_03__voided_payment_returned(db, st):
    """IVP-GC-03 — a voided payment is returned.
    Rules: `get_by_id_and_workspace_with_creator` R1"""
    p1 = st.voided()

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=p1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[0].id == p1.id
    # Then 2
    assert result[0].is_voided is True
    assert result[0].voided_by == st.U2.id
    # Then 3
    assert result[1] == "Rahim"


# [claude] IVP-GC-04
def test_ivp_gc_04__without_recorder_name_none(db, st):
    """IVP-GC-04 — a payment without a recorder comes back with name None.
    Rules: `get_by_id_and_workspace_with_creator` R1 (name per `get_by_invoice` R2)"""
    p1 = st.payment(created_by=None)

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=p1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is not None
    # Then 2
    assert result[0].id == p1.id
    # Then 3
    assert result[1] is None


# [claude] IVP-GC-05
def test_ivp_gc_05__name_is_recorder_not_voider(db, st):
    """IVP-GC-05 — the name is the recorder's, not the voider's.
    Rules: `get_by_id_and_workspace_with_creator` R1"""
    p1 = st.voided(created_by=st.U3.id)

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=p1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result[1] == "Salma"


# [claude] IVP-GC-06
def test_ivp_gc_06__w0_payment_under_w1_none(db, st):
    """IVP-GC-06 — a payment of the lower workspace W0 asked under W1 gives None.
    Rules: `get_by_id_and_workspace_with_creator` R2"""
    x0 = st.payment(workspace_id=st.W0.id, invoice_id=st.N0.id)

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=x0.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] IVP-GC-07
def test_ivp_gc_07__w2_payment_under_w1_none(db, st):
    """IVP-GC-07 — a payment of the higher workspace W2 asked under W1 gives None.
    Rules: `get_by_id_and_workspace_with_creator` R2"""
    x2 = st.payment(workspace_id=st.W2.id, invoice_id=st.N9.id)

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=x2.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] IVP-GC-08
def test_ivp_gc_08__w2_payment_under_w2_returned(db, st):
    """IVP-GC-08 — the same W2 payment asked under W2 is returned.
    Rules: `get_by_id_and_workspace_with_creator` R1"""
    x2 = st.payment(workspace_id=st.W2.id, invoice_id=st.N9.id)

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=x2.id, workspace_id=st.W2.id
    )

    # Then 1
    assert result[0].id == x2.id
    # Then 2
    assert result[1] == "Rahim"


# [claude] IVP-GC-09
def test_ivp_gc_09__unknown_id_none(db, st):
    """IVP-GC-09 — an unknown id gives None.
    Rules: `get_by_id_and_workspace_with_creator` R2"""
    st.payment()

    result = dao.get_by_id_and_workspace_with_creator(
        db, id=MISSING, workspace_id=st.W1.id
    )

    # Then 1
    assert result is None


# [claude] IVP-GC-10
def test_ivp_gc_10__id_0_none(db, st):
    """IVP-GC-10 — id 0 gives None and raises nothing.
    Rules: `get_by_id_and_workspace_with_creator` R2"""
    st.payment()

    result = dao.get_by_id_and_workspace_with_creator(db, id=0, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] IVP-GC-11
def test_ivp_gc_11__one_statement_outer_join_no_lock(db, st):
    """IVP-GC-11 — one statement with a LEFT OUTER JOIN of the creator, no lock.
    Rules: `get_by_id_and_workspace_with_creator` R3"""
    p1 = st.payment()
    p1_id, w1_id = (
        p1.id,
        st.W1.id,
    )  # read before expiring: an expired id would reload its row
    db.expire_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace_with_creator(
            db, id=p1_id, workspace_id=w1_id
        )
        n = result[1]

    # Then 1
    assert n == "Rahim"
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "LEFT OUTER JOIN profiles" in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] IVP-GC-12
def test_ivp_gc_12__writes_nothing(db, st):
    """IVP-GC-12 — writes nothing: a pending payment stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_id_and_workspace_with_creator` Side effects"""
    b = st.payment()
    b.notes = "Edited"
    p = st.pending()

    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace_with_creator(
            db, id=b.id, workspace_id=st.W1.id
        )

    # Then 1
    assert result[0].id == b.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []


# --------------------------------------------------------------------------- #
# get_total_paid_for_invoice — money: the invoice's paid_amount comes from here
# --------------------------------------------------------------------------- #


# [claude] IVP-TP-01
def test_ivp_tp_01__active_payments_summed_voided_left_out(db, st):
    """IVP-TP-01 — active payments are summed, a voided one is left out.
    Rules: `get_total_paid_for_invoice` R1, R2, Returns"""
    st.payment(payment_amount=Decimal("10.10"))
    st.voided(payment_amount=Decimal("5.00"))
    st.payment(payment_amount=Decimal("20.20"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("30.30")
    # Then 3
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-02
def test_ivp_tp_02__no_payment_gives_0_00(db, st):
    """IVP-TP-02 — no payment gives Decimal 0.00.
    Rules: `get_total_paid_for_invoice` R2"""
    st.payment(invoice_id=st.NA.id)

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")
    # Then 3
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-03
def test_ivp_tp_03__all_voided_gives_0_00(db, st):
    """IVP-TP-03 — every payment voided gives 0.00.
    Rules: `get_total_paid_for_invoice` R2"""
    st.voided(payment_amount=Decimal("40.00"))
    st.voided(payment_amount=Decimal("60.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("0.00")
    # Then 2
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-04
def test_ivp_tp_04__one_active_next_to_voided(db, st):
    """IVP-TP-04 — one active payment next to a voided one counts alone.
    Rules: `get_total_paid_for_invoice` R2"""
    st.voided(payment_amount=Decimal("40.00"))
    st.payment(payment_amount=Decimal("0.01"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("0.01")


# [claude] IVP-TP-05
def test_ivp_tp_05__unknown_invoice_gives_0_00(db, st):
    """IVP-TP-05 — an unknown invoice gives 0.00.
    Rules: `get_total_paid_for_invoice` R2"""
    st.payment()

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=MISSING, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("0.00")
    # Then 2
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-06
def test_ivp_tp_06__invoice_id_0_gives_0_00(db, st):
    """IVP-TP-06 — invoice id 0 gives 0.00 and raises nothing.
    Rules: `get_total_paid_for_invoice` R2"""
    st.payment()

    result = dao.get_total_paid_for_invoice(db, invoice_id=0, workspace_id=st.W1.id)

    # Then 1
    assert result == Decimal("0.00")


# [claude] IVP-TP-07
def test_ivp_tp_07__w2_payment_not_counted_for_w1(db, st):
    """IVP-TP-07 — a W2 payment of 1000.00 on this invoice is not counted for W1.
    Rules: `get_total_paid_for_invoice` R3"""
    st.payment(payment_amount=Decimal("10.10"))
    st.payment(payment_amount=Decimal("20.20"))
    st.payment(workspace_id=st.W2.id, payment_amount=Decimal("1000.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("30.30")


# [claude] IVP-TP-08
def test_ivp_tp_08__w0_payment_not_counted_for_w1(db, st):
    """IVP-TP-08 — a W0 payment of 1000.00 on this invoice is not counted for W1.
    Rules: `get_total_paid_for_invoice` R3"""
    st.payment(workspace_id=st.W0.id, payment_amount=Decimal("1000.00"))
    st.payment(payment_amount=Decimal("10.10"))
    st.payment(payment_amount=Decimal("20.20"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("30.30")


# [claude] IVP-TP-09
def test_ivp_tp_09__asked_for_w2_only_w2_counts(db, st):
    """IVP-TP-09 — asked for W2, only W2's row on the invoice counts.
    Rules: `get_total_paid_for_invoice` R1, R3"""
    st.payment(payment_amount=Decimal("10.10"))
    st.payment(workspace_id=st.W2.id, payment_amount=Decimal("1000.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W2.id
    )

    # Then 1
    assert result == Decimal("1000.00")


# [claude] IVP-TP-10
def test_ivp_tp_10__neighbour_invoices_not_counted(db, st):
    """IVP-TP-10 — payments of the invoices just below and just above are not counted.
    Rules: `get_total_paid_for_invoice` R1"""
    st.payment(invoice_id=st.NA.id, payment_amount=Decimal("300.00"))
    st.payment(payment_amount=Decimal("10.10"))
    st.payment(invoice_id=st.NB.id, payment_amount=Decimal("500.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("10.10")


# [claude] IVP-TP-11
def test_ivp_tp_11__single_zero_payment_gives_0_00(db, st):
    """IVP-TP-11 — a single 0.00 payment gives Decimal 0.00.
    Rules: `get_total_paid_for_invoice` R4"""
    st.payment(payment_amount=Decimal("0.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")
    # Then 3
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-12
def test_ivp_tp_12__zero_plus_negative(db, st):
    """IVP-TP-12 — 0.00 plus a stored -5.00 gives -5.00.
    Rules: `get_total_paid_for_invoice` R4"""
    st.payment(payment_amount=Decimal("0.00"))
    st.payment(payment_amount=Decimal("-5.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("-5.00")
    # Then 2
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-13
def test_ivp_tp_13__cancelling_amounts_give_0_00(db, st):
    """IVP-TP-13 — amounts that cancel to zero give 0.00.
    Rules: `get_total_paid_for_invoice` R4"""
    st.payment(payment_amount=Decimal("7.25"))
    st.payment(payment_amount=Decimal("-7.25"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("0.00")
    # Then 2
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-14
def test_ivp_tp_14__sum_beyond_column_width_not_capped(db, st):
    """IVP-TP-14 — two rows of 9999999999999.99 give 19999999999999.98, not capped.
    Rules: `get_total_paid_for_invoice` R5"""
    st.payment(payment_amount=Decimal("9999999999999.99"))
    st.payment(payment_amount=Decimal("9999999999999.99"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("19999999999999.98")


# [claude] IVP-TP-15
def test_ivp_tp_15__cents_summed_exactly(db, st):
    """IVP-TP-15 — cents are summed exactly: three 0.10 give 0.30.
    Rules: `get_total_paid_for_invoice` R4"""
    for _ in range(3):
        st.payment(payment_amount=Decimal("0.10"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.30")
    # Then 3
    assert str(result) == "0.30"


# [claude] IVP-TP-16
def test_ivp_tp_16__unflushed_payment_not_counted(db, st):
    """IVP-TP-16 — an unflushed payment is not counted and stays pending.
    Rules: `get_total_paid_for_invoice` R6"""
    st.payment(payment_amount=Decimal("10.00"))
    p = st.pending(payment_date=D2)

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("10.00")
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1


# [claude] IVP-TP-17
def test_ivp_tp_17__two_2_125_total_4_26(db, st):
    """IVP-TP-17 — two stored 2.125 amounts (kept as 2.13) total 4.26, half up.
    Rules: `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]"""
    st.payment(payment_amount=Decimal("2.125"))
    st.payment(payment_amount=Decimal("2.125"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("4.26")
    # Then 2
    assert result.as_tuple().exponent == -2


# [claude] IVP-TP-18
def test_ivp_tp_18__minus_1_005_and_0_005_total_minus_1_00(db, st):
    """IVP-TP-18 — stored -1.005 and 0.005 (kept as -1.01 and 0.01) total -1.00.
    Rules: `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]"""
    st.payment(payment_amount=Decimal("-1.005"))
    st.payment(payment_amount=Decimal("0.005"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("-1.00")


# [claude] IVP-TP-19
def test_ivp_tp_19__two_2_124_total_4_24(db, st):
    """IVP-TP-19 — control: stored 2.124 twice (kept as 2.12) totals 4.24.
    Rules: `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]"""
    st.payment(payment_amount=Decimal("2.124"))
    st.payment(payment_amount=Decimal("2.124"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("4.24")


# [claude] IVP-TP-20
def test_ivp_tp_20__stored_value_counts_not_unflushed_edit(db, st):
    """IVP-TP-20 — the stored value counts, not an unflushed edit of it.
    Rules: `get_total_paid_for_invoice` R6, Side effects"""
    p1 = st.payment(payment_amount=Decimal("10.00"))
    p1.payment_amount = Decimal("99.00")

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("10.00")
    # Then 2
    assert p1 in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert p1.payment_amount == Decimal("99.00")


# [claude] IVP-TP-21
def test_ivp_tp_21__one_select_no_lock_nothing_written(db, st):
    """IVP-TP-21 — one SELECT, no lock, nothing written.
    Rules: `get_total_paid_for_invoice` R6, Side effects"""
    st.payment()

    with StatementRecorder(db) as rec:
        result = dao.get_total_paid_for_invoice(
            db, invoice_id=st.N1.id, workspace_id=st.W1.id
        )

    # Then 1
    assert result == Decimal("10.00")
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] IVP-TP-22
def test_ivp_tp_22__voided_flag_decides(db, st):
    """IVP-TP-22 — the voided flag decides, not the void note or the voider.
    Rules: `get_total_paid_for_invoice` R1, R2"""
    st.payment(payment_amount=Decimal("8.00"), void_note="Checked twice")
    st.voided(payment_amount=Decimal("3.00"))

    result = dao.get_total_paid_for_invoice(
        db, invoice_id=st.N1.id, workspace_id=st.W1.id
    )

    # Then 1
    assert result == Decimal("8.00")


# --------------------------------------------------------------------------- #
# Inherited `create` and model facts
# --------------------------------------------------------------------------- #


# [claude] IVP-CR-01
def test_ivp_cr_01__create_stores_payment_not_voided(db, st):
    """IVP-CR-01 — create from a dict stores the payment, not voided, void fields empty.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st))

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.workspace_id == st.W1.id
    assert row.invoice_id == st.N1.id
    assert row.payment_amount == Decimal("25.50")
    assert row.payment_date == D3
    assert row.created_by == st.U1.id
    # Then 3
    assert row.is_voided is False
    assert row.voided_at is None
    assert row.voided_by is None
    assert row.void_note is None
    # Then 4
    assert row.payment_method is None
    assert row.payment_reference is None
    assert row.transaction_id is None
    assert row.bank_name is None
    assert row.notes is None


# [claude] IVP-CR-02
def test_ivp_cr_02__created_at_filled_and_naive(db, st):
    """IVP-CR-02 — created_at is filled and naive.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st))

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.created_at is not None
    # Then 3
    assert row.created_at.tzinfo is None


# [claude] IVP-CR-03
def test_ivp_cr_03__flushed_not_committed(db, st):
    """IVP-CR-03 — flushed, not committed: a rollback removes the payment.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0
    sp = db.begin_nested()

    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.create(db, obj_in=new_payment(st))

    # Then 1
    assert result.id is not None
    new_id = result.id
    # Then 2
    assert st.count_id(new_id) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert st.count_id(new_id) == 0


# [claude] IVP-CR-04
def test_ivp_cr_04__unknown_invoice_fails_23503(db, st):
    """IVP-CR-04 — an unknown invoice fails at flush with IntegrityError 23503.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0
    before = st.counts()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=new_payment(st, invoice_id=MISSING))
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert st.counts() == before


# [claude] IVP-CR-05
def test_ivp_cr_05__unknown_workspace_fails_23503(db, st):
    """IVP-CR-05 — an unknown workspace fails at flush with IntegrityError 23503.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0
    before = st.counts()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=new_payment(st, workspace_id=MISSING))
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert st.counts() == before


# [claude] IVP-CR-06
def test_ivp_cr_06__unknown_recorder_fails_23503(db, st):
    """IVP-CR-06 — an unknown recorder fails at flush with IntegrityError 23503.
    Rules: inherited `create` R1"""
    assert st.count_ws(st.W1.id) == 0
    before = st.counts()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=new_payment(st, created_by=MISSING))
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert st.counts() == before


# [claude] IVP-CR-07
@pytest.mark.xfail(strict=True, reason=R2400)
def test_ivp_cr_07__created_at_naive_utc_under_dhaka(db, st):
    """IVP-CR-07 — a new payment's created_at is naive UTC under Asia/Dhaka.
    Rules: inherited `create` R1a [BUG-2400]"""
    st.zone("Asia/Dhaka")
    a = InvoicePayment(
        workspace_id=st.W1.id,
        invoice_id=st.N1.id,
        payment_amount=Decimal("10.00"),
        payment_date=D2,
        created_by=st.U1.id,
    )

    db.add(a)
    db.flush()
    db.refresh(a)
    now = utcnow()

    # Then 1
    row = st.reread(a.id)
    assert row.created_at.tzinfo is None
    # Then 2
    assert close_to_now(row.created_at, now)


# [claude] IVP-CR-08
@pytest.mark.xfail(strict=True, reason=R2400)
def test_ivp_cr_08__created_at_naive_utc_under_new_york(db, st):
    """IVP-CR-08 — a new payment's created_at is naive UTC under America/New_York.
    Rules: inherited `create` R1a [BUG-2400]"""
    st.zone("America/New_York")
    a = InvoicePayment(
        workspace_id=st.W1.id,
        invoice_id=st.N1.id,
        payment_amount=Decimal("10.00"),
        payment_date=D2,
        created_by=st.U1.id,
    )

    db.add(a)
    db.flush()
    db.refresh(a)
    now = utcnow()

    # Then 1
    row = st.reread(a.id)
    assert row.created_at.tzinfo is None
    # Then 2
    assert close_to_now(row.created_at, now)


# [claude] IVP-CR-09
@pytest.mark.xfail(strict=True, reason=R2400)
def test_ivp_cr_09__dao_create_naive_utc_under_dhaka(db, st):
    """IVP-CR-09 — a payment created through the DAO gets naive UTC under Asia/Dhaka.
    Rules: inherited `create` R1a [BUG-2400]"""
    st.zone("Asia/Dhaka")

    result = dao.create(db, obj_in=new_payment(st))
    now = utcnow()

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.created_at.tzinfo is None
    # Then 3
    assert close_to_now(row.created_at, now)


# [claude] IVP-CR-10
@pytest.mark.xfail(strict=True, reason=R2400)
def test_ivp_cr_10__dao_create_naive_utc_under_new_york(db, st):
    """IVP-CR-10 — a payment created through the DAO gets naive UTC under America/New_York.
    Rules: inherited `create` R1a [BUG-2400]"""
    st.zone("America/New_York")

    result = dao.create(db, obj_in=new_payment(st))
    now = utcnow()

    # Then 1
    assert result.id is not None
    # Then 2
    row = st.reread(result.id)
    assert row.created_at.tzinfo is None
    # Then 3
    assert close_to_now(row.created_at, now)


# [claude] IVP-CR-11
def test_ivp_cr_11__2_125_stored_as_2_13(db, st):
    """IVP-CR-11 — 2.125 is stored as 2.13 (half up, not half even).
    Rules: model facts `payment_amount` [HR-15]"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st, payment_amount=Decimal("2.125")))

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).payment_amount == Decimal("2.13")


# [claude] IVP-CR-12
def test_ivp_cr_12__0_005_stored_as_0_01(db, st):
    """IVP-CR-12 — 0.005 is stored as 0.01.
    Rules: model facts `payment_amount` [HR-15]"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st, payment_amount=Decimal("0.005")))

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).payment_amount == Decimal("0.01")


# [claude] IVP-CR-13
def test_ivp_cr_13__minus_1_005_stored_as_minus_1_01(db, st):
    """IVP-CR-13 — -1.005 is stored as -1.01 (away from zero).
    Rules: model facts `payment_amount` [HR-15]"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st, payment_amount=Decimal("-1.005")))

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).payment_amount == Decimal("-1.01")


# [claude] IVP-CR-14
def test_ivp_cr_14__2_124_stored_as_2_12(db, st):
    """IVP-CR-14 — control: 2.124 is stored as 2.12.
    Rules: model facts `payment_amount` [HR-15]"""
    assert st.count_ws(st.W1.id) == 0

    result = dao.create(db, obj_in=new_payment(st, payment_amount=Decimal("2.124")))

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).payment_amount == Decimal("2.12")


# [claude] IVP-CR-15
def test_ivp_cr_15__zero_and_negative_amounts_stored(db, st):
    """IVP-CR-15 — the database stores 0.00 and negative amounts (no check constraint).
    Rules: model facts `payment_amount`"""
    p1 = st.payment(payment_amount=Decimal("0.00"))

    result = dao.create(db, obj_in=new_payment(st, payment_amount=Decimal("-5.00")))

    # Then 1
    assert result.id is not None
    # Then 2
    assert st.reread(result.id).payment_amount == Decimal("-5.00")
    # Then 3
    assert st.reread(p1.id).payment_amount == Decimal("0.00")
