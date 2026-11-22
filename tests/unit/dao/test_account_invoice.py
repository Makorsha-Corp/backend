"""Unit tests for app/dao/account_invoice.py.

Implements tests/unit/dao/account_invoice.cases.md (Revision 4), one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is mocked and
no clock is patched (Conventions, Externals: None): the overdue cards pass
`today=TD` themselves.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment, and every numbered Then line of a card is a `# Then N` comment directly
before its assertions.

Conventions mapping (card says -> code):
  dao                     -> `dao` (the `account_invoice_dao` singleton)
  W0, W1, W2, U1 ... U3   -> `st.W0` ... `st.U3` (fixture `st`)
  AC0, AC1, AC2           -> `st.AC0`, `st.AC1`, `st.AC2`
  TAG, XID(k), GN(n), AR(n) -> `st.TAG`, `XID(k)`, `GN(n)`, `AR(n)`
  acct(name), but ...     -> `st.acct(name, inactive=True | closed=True | half_closed=True)`
  inv, but ...            -> `st.inv(column=value, ...)`; `partial(p)` -> `partial=p`,
                             `paid` -> `paid=True`, `draft` -> `draft=True`,
                             `voided` -> `voided=True`
  inv of W0 / of W2       -> `st.inv0(...)` / `st.inv2(...)`
  invs(n), accts(n)       -> `st.invs(n)`, `st.accts(n)`
  po / eo / so / wo(n)    -> `st.po(n, ...)` ... (always unchecked); `of=0` / `of=2`
                             for "of W0" / "of W2"; `voided=True` = "voided order";
                             `deleted=True` = "deleted wo"
  hubclean                -> `st.hubclean()`
  ids / idset             -> `ids(x)`, `idset(x)`; hub: `hids(result)`, `pay(result, A)`, `rec(result, A)`
  re-read X               -> `st.reread(X.id)`; unchanged(X) -> `st.snap(X.id)` before and after
  Statement recorder      -> `with StatementRecorder(db) as rec:` around the When;
                             `rec.sql(table)`, `rec.sql(table, ordered=True)`,
                             `rec.sqls(table)`, `order_part(sql)`, `rec.written`
  commit spy              -> `sp = db.begin_nested()` + `patch.object(db, "commit", wraps=db.commit)`
"""

# ruff: noqa: DTZ001, FURB157  (Conventions prescribe naive datetimes and the cards' Decimal("0") literals)
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, select, text

from app.dao.account_invoice import account_invoice_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.purchase_order import PurchaseOrder
from app.models.sales_order import SalesOrder
from app.models.work_order import WorkOrder
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

dao = account_invoice_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "D1 ... D5", "PASTDUE", "FARDUE", "T1"
D1 = date(2026, 3, 1)
D2 = date(2026, 3, 2)
D3 = date(2026, 3, 3)
D4 = date(2026, 3, 4)
D5 = date(2026, 3, 5)
PASTDUE = date(2020, 1, 1)
FARDUE = date(2099, 12, 31)
T1 = datetime(2026, 3, 6, 9, 0)

# Convention "TD", "TDM1", "TDP1" (the `today=` of the overdue cards)
TD = date(2031, 6, 15)
TDM1 = TD - timedelta(days=1)
TDP1 = TD + timedelta(days=1)

R622 = "BUG-622: Invoice/account search filters are not HR-8 safe"
R623 = "BUG-623: Accounts-hub page ordered by account name case-sensitively"
R634 = "BUG-634: Draft invoices counted as open balances and in summary totals"
R635 = 'BUG-635: No invoice ever becomes "overdue"'
R636 = (
    'BUG-636: Hub "accounts with open balance" KPI counts accounts the hub list hides'
)
R637 = "BUG-637: Whitespace-only invoice-number search returns almost nothing"
R2690 = (
    "BUG-2690: An invoice on another workspace's account is listed, "
    "found by that account's name and counted in totals"
)
R2691 = "BUG-2691: A soft-deleted work order's number still finds its invoice"
R2692 = "BUG-2692: Account invoice summary adds payables and receivables into one total"


# Convention "XID(k)": an explicit id no other run uses
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# Convention "GN(n)": sales and expense numbers are unique across workspaces
def GN(n):
    return f"{n}-{os.getpid()}"


# Convention "AR(n)": n in Arabic-Indic digits
def AR(n):
    return "".join(chr(0x660 + int(c)) for c in str(n))


# --------------------------------------------------------------------------- #
# Conventions -> standing rows and Given-row builders
# --------------------------------------------------------------------------- #


class Standing:
    """Standing rows of every test (W0 < W1 < W2, U1 ... U3, AC0 ... AC2) and the
    Given-row builders. Every builder flushes before it returns."""

    def __init__(self, db):
        self.db = db
        self.W0 = make_workspace(db)
        self.W1 = make_workspace(db)
        self.W2 = make_workspace(db)
        self.U1 = make_profile(db)
        self.U2 = make_profile(db)
        self.U3 = make_profile(db)
        self.TAG = uuid.uuid4().hex[:8]
        self.AC0 = self._account(self.W0.id, f"Acme {self.TAG}")
        self.AC1 = self._account(self.W1.id, f"Acme {self.TAG}")
        self.AC2 = self._account(self.W2.id, f"Acme {self.TAG}")

    def _account(self, workspace_id, name, **cols):
        fields = {
            "workspace_id": workspace_id,
            "name": name,
            "is_active": True,
            "is_deleted": False,
        }
        fields.update(cols)
        row = Account(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    # Convention "acct(name)"; inactive / closed / half-closed
    def acct(self, name, *, inactive=False, closed=False, half_closed=False):
        cols = {}
        if inactive:
            cols["is_active"] = False
        if closed:
            cols.update(
                is_deleted=True, is_active=False, deleted_at=T1, deleted_by=self.U1.id
            )
        if half_closed:
            cols["is_deleted"] = True
        return self._account(self.W1.id, name, **cols)

    def _inv_fields(
        self,
        ws,
        account,
        *,
        partial=None,
        paid=False,
        draft=False,
        voided=False,
        **cols,
    ):
        fields = {
            "workspace_id": ws.id,
            "account_id": account.id,
            "invoice_type": "payable",
            "invoice_status": "confirmed",
            "payment_status": "unpaid",
            "invoice_amount": Decimal("100.00"),
            "paid_amount": Decimal("0.00"),
            "invoice_date": D2,
            "created_by": self.U1.id,
        }
        if partial is not None:
            fields.update(payment_status="partial", paid_amount=partial)
        if draft:
            fields["invoice_status"] = "draft"
        if voided:
            fields.update(
                invoice_status="voided",
                void_note="Wrong amount",
                paid_amount=Decimal("0.00"),
                payment_status="unpaid",
                updated_by=self.U1.id,
                updated_at=T1,
            )
        fields.update(cols)
        if paid:
            fields.update(payment_status="paid", paid_amount=fields["invoice_amount"])
        return fields

    # Convention "inv" (W1, AC1); "inv of W0" / "inv of W2"
    def inv(self, **but):
        return self._add(AccountInvoice(**self._inv_fields(self.W1, self.AC1, **but)))

    def inv0(self, **but):
        return self._add(AccountInvoice(**self._inv_fields(self.W0, self.AC0, **but)))

    def inv2(self, **but):
        return self._add(AccountInvoice(**self._inv_fields(self.W2, self.AC2, **but)))

    def _add(self, row):
        self.db.add(row)
        self.db.flush()
        return row

    # Convention "invs(n)": one flush after the loop
    def invs(self, n):
        for i in range(n):
            self.db.add(
                AccountInvoice(
                    **self._inv_fields(
                        self.W1, self.AC1, invoice_number=f"BULK-{i:04d}"
                    )
                )
            )
        self.db.flush()

    # Convention "accts(n)": one flush after the loop
    def accts(self, n):
        for i in range(n):
            self.db.add(
                Account(
                    workspace_id=self.W1.id,
                    name=f"Bulk {i:04d} {self.TAG}",
                    is_active=True,
                    is_deleted=False,
                )
            )
        self.db.flush()

    # Convention "unchecked: ..."
    def unchecked(self, row):
        self.db.execute(text("SET LOCAL session_replication_role = replica"))
        self.db.add(row)
        self.db.flush()
        self.db.execute(text("SET LOCAL session_replication_role = origin"))
        return row

    def _ws(self, of):
        return {0: self.W0, 1: self.W1, 2: self.W2}[of]

    def _voided_order(self):
        return {
            "voided": True,
            "void_note": "Cancelled",
            "voided_at": T1,
            "voided_by": self.U1.id,
        }

    # Convention "po(n)"
    def po(self, n, *, of=1, voided=False, **cols):
        fields = {
            "workspace_id": self._ws(of).id,
            "po_number": n,
            "destination_type": "storage",
            "destination_id": MISSING,
            "subtotal": 0,
            "total_amount": 0,
            "current_status_id": MISSING,
            "created_by": self.U1.id,
        }
        if voided:
            fields.update(self._voided_order())
        fields.update(cols)
        return self.unchecked(PurchaseOrder(**fields))

    # Convention "eo(n)"
    def eo(self, n, *, of=1, voided=False, **cols):
        fields = {
            "workspace_id": self._ws(of).id,
            "expense_number": GN(n),
            "expense_category": "other",
            "expense_date": D1,
            "created_by": self.U1.id,
        }
        if voided:
            fields.update(self._voided_order())
        fields.update(cols)
        return self.unchecked(ExpenseOrder(**fields))

    # Convention "so(n)"
    def so(self, n, *, of=1, **cols):
        fields = {
            "workspace_id": self._ws(of).id,
            "sales_order_number": GN(n),
            "account_id": self.AC1.id,
            "factory_id": MISSING,
            "order_date": D1,
            "current_status_id": MISSING,
            "created_by": self.U1.id,
        }
        fields.update(cols)
        return self.unchecked(SalesOrder(**fields))

    # Convention "wo(n)"; "deleted wo"
    def wo(self, n, *, of=1, deleted=False, **cols):
        fields = {
            "workspace_id": self._ws(of).id,
            "work_order_number": n,
            "work_order_type_id": MISSING,
            "title": "Oil change",
            "factory_id": MISSING,
            "created_by": self.U1.id,
        }
        if deleted:
            fields.update(
                is_active=False, is_deleted=True, deleted_at=T1, deleted_by=self.U1.id
            )
        fields.update(cols)
        return self.unchecked(WorkOrder(**fields))

    # Convention "hubclean"
    def hubclean(self):
        self.AC1.is_active = False
        self.db.flush()

    # Convention "re-read X"
    def reread(self, invoice_id):
        self.db.expire_all()
        return self.db.execute(
            select(AccountInvoice).where(AccountInvoice.id == invoice_id)
        ).scalar_one()

    # Convention "unchanged(X)": every column after re-read
    def snap(self, invoice_id):
        row = self.reread(invoice_id)
        return {c.key: getattr(row, c.key) for c in AccountInvoice.__table__.columns}

    # Convention "nothing written": rows of account_invoices, all workspaces
    def inv_count(self):
        return self.db.scalar(text("SELECT count(*) FROM account_invoices"))


@pytest.fixture
def st(db):
    return Standing(db)


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #


def ids(x):
    return [r.id for r in x]


def idset(x):
    return {r.id for r in x}


def hids(result):
    return [row[0].id for row in result[0]]


def pay(result, a):
    [row] = [row for row in result[0] if row[0].id == a.id]
    return row[1]


def rec(result, a):
    [row] = [row for row in result[0] if row[0].id == a.id]
    return row[2]


def order_part(sql):
    """Text of `sql` after its last ORDER BY, before any LIMIT / OFFSET ("" if none)."""
    if "ORDER BY" not in sql:
        return ""
    tail = sql.rsplit("ORDER BY", 1)[1]
    return tail.split("LIMIT", 1)[0].split("OFFSET", 1)[0]


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

    def sqls(self, table):
        """Every SELECT that reads `table`."""
        return [s for s in self.selects if f"FROM {table}" in s]

    def sql(self, table, *, ordered=False):
        """The one SELECT reading `table` (with an ORDER BY, if `ordered`); fails unless exactly one."""
        found = [s for s in self.sqls(table) if not ordered or "ORDER BY" in s]
        [statement] = found
        return statement


# --------------------------------------------------------------------------- #
# _escape_ilike
# --------------------------------------------------------------------------- #


# [claude] AIV-ES-01
def test_aiv_es_01__backslash_percent_underscore_escaped(st):
    """AIV-ES-01 — backslash, percent and underscore are escaped, backslash first.
    Rules: _escape_ilike R1"""
    result = dao._escape_ilike(r"a%b_c\d")

    # Then 1
    assert result == r"a\%b\_c\\d"


# [claude] AIV-ES-02
def test_aiv_es_02__escaped_percent_gets_backslash_doubled(st):
    """AIV-ES-02 — an escaped percent in the input gets its backslash doubled, not reused.
    Rules: _escape_ilike R1"""
    result = dao._escape_ilike(r"\%\_")

    # Then 1
    assert result == r"\\\%\\\_"


# [claude] AIV-ES-03
def test_aiv_es_03__case_and_whitespace_kept(st):
    """AIV-ES-03 — case, inner and outer whitespace are kept.
    Rules: _escape_ilike R1"""
    result = dao._escape_ilike(" Ab  Cd ")

    # Then 1
    assert result == " Ab  Cd "


# [claude] AIV-ES-04
def test_aiv_es_04__empty_stays_empty(st):
    """AIV-ES-04 — the empty string stays empty.
    Rules: _escape_ilike R1"""
    result = dao._escape_ilike("")

    # Then 1
    assert result == ""


# --------------------------------------------------------------------------- #
# _invoice_number_search_ilike_term
# --------------------------------------------------------------------------- #


# [claude] AIV-ST-01
def test_aiv_st_01__padded_term_trimmed_and_wrapped(st):
    """AIV-ST-01 — a padded term is trimmed and wrapped in percent signs, case kept.
    Rules: _invoice_number_search_ilike_term R1, R2"""
    result = dao._invoice_number_search_ilike_term(" PO-1 ")

    # Then 1
    assert result == "%PO-1%"


# [claude] AIV-ST-02
def test_aiv_st_02__percent_escaped_inside_wrapper(st):
    """AIV-ST-02 — a percent sign in the term is escaped inside the wrapper.
    Rules: _invoice_number_search_ilike_term R2"""
    result = dao._invoice_number_search_ilike_term("50%")

    # Then 1
    assert result == r"%50\%%"


# [claude] AIV-ST-03
def test_aiv_st_03__underscore_and_backslash_escaped(st):
    """AIV-ST-03 — underscore and backslash are escaped too.
    Rules: _invoice_number_search_ilike_term R2"""
    result = dao._invoice_number_search_ilike_term(r"Ab_c\D")

    # Then 1
    assert result == r"%Ab\_c\\D%"


# [claude] AIV-ST-04
def test_aiv_st_04__whitespace_only_gives_empty_pattern(st):
    """AIV-ST-04 — whitespace only gives the empty pattern, not %%.
    Rules: _invoice_number_search_ilike_term R1"""
    result = dao._invoice_number_search_ilike_term("  \t ")

    # Then 1
    assert result == ""


# [claude] AIV-ST-05
def test_aiv_st_05__empty_gives_empty_pattern(st):
    """AIV-ST-05 — the empty string gives the empty pattern.
    Rules: _invoice_number_search_ilike_term R1"""
    result = dao._invoice_number_search_ilike_term("")

    # Then 1
    assert result == ""


# --------------------------------------------------------------------------- #
# _outstanding_amount_expr
# --------------------------------------------------------------------------- #


# [claude] AIV-OE-01
def test_aiv_oe_01__amount_minus_paid_exact(db, st):
    """AIV-OE-01 — amount minus paid, exact.
    Rules: _outstanding_amount_expr R1"""
    n = st.inv(partial=Decimal("30.05"))

    result = db.scalar(
        select(dao._outstanding_amount_expr()).where(AccountInvoice.id == n.id)
    )

    # Then 1
    assert result == Decimal("69.95")


# [claude] AIV-OE-02
def test_aiv_oe_02__voided_not_treated_as_zero(db, st):
    """AIV-OE-02 — a voided invoice is not treated as zero.
    Rules: _outstanding_amount_expr R1"""
    n = st.inv(voided=True)

    result = db.scalar(
        select(dao._outstanding_amount_expr()).where(AccountInvoice.id == n.id)
    )

    # Then 1
    assert result == Decimal("100.00")


# [claude] AIV-OE-03
def test_aiv_oe_03__overpaid_gives_negative(db, st):
    """AIV-OE-03 — an overpaid invoice gives a negative value.
    Rules: _outstanding_amount_expr R1"""
    n = st.inv(
        invoice_amount=Decimal("10.00"),
        paid_amount=Decimal("15.00"),
        payment_status="paid",
    )

    result = db.scalar(
        select(dao._outstanding_amount_expr()).where(AccountInvoice.id == n.id)
    )

    # Then 1
    assert result == Decimal("-5.00")


# --------------------------------------------------------------------------- #
# _reshape_accounts_hub_row
# --------------------------------------------------------------------------- #


# [claude] AIV-RH-01
def test_aiv_rh_01__every_position_lands_in_its_attribute(st):
    """AIV-RH-01 — every position lands in its own attribute.
    Rules: _reshape_accounts_hub_row R1, R2"""
    ac1 = st.AC1
    row = (ac1, ac1.id, Decimal("12.50"), 2, 1, ac1.id, Decimal("7.25"), 3, 0)

    result = dao._reshape_accounts_hub_row(row)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0] is ac1
    # Then 3
    assert result[1].outstanding_total == Decimal("12.50")
    assert result[1].open_count == 2
    assert result[1].has_overdue is True
    # Then 4
    assert result[2].outstanding_total == Decimal("7.25")
    assert result[2].open_count == 3
    assert result[2].has_overdue is False
    # Then 5
    assert isinstance(result[1].outstanding_total, Decimal)


# [claude] AIV-RH-02
def test_aiv_rh_02__no_payable_subrow_gives_zeros(st):
    """AIV-RH-02 — no payable sub-row gives 0, 0, False on the payable side only.
    Rules: _reshape_accounts_hub_row R2"""
    ac1 = st.AC1
    row = (ac1, None, None, None, None, ac1.id, Decimal("7.25"), 3, 1)

    result = dao._reshape_accounts_hub_row(row)

    # Then 1
    assert result[1].outstanding_total == 0
    assert result[1].open_count == 0
    assert result[1].has_overdue is False
    # Then 2
    assert result[2].outstanding_total == Decimal("7.25")
    assert result[2].open_count == 3
    assert result[2].has_overdue is True


# [claude] AIV-RH-03
def test_aiv_rh_03__no_receivable_subrow_gives_zeros(st):
    """AIV-RH-03 — no receivable sub-row gives 0, 0, False on the receivable side only.
    Rules: _reshape_accounts_hub_row R2"""
    ac1 = st.AC1
    row = (ac1, ac1.id, Decimal("12.50"), 2, 0, None, None, None, None)

    result = dao._reshape_accounts_hub_row(row)

    # Then 1
    assert result[1].outstanding_total == Decimal("12.50")
    assert result[1].open_count == 2
    assert result[1].has_overdue is False
    # Then 2
    assert result[2].outstanding_total == 0
    assert result[2].open_count == 0
    assert result[2].has_overdue is False


# [claude] AIV-RH-04
def test_aiv_rh_04__zero_outstanding_passed_through(st):
    """AIV-RH-04 — a zero outstanding total is passed through, not replaced.
    Rules: _reshape_accounts_hub_row R2"""
    ac1 = st.AC1
    row = (ac1, ac1.id, Decimal("0.00"), 1, 0, ac1.id, Decimal("-5.00"), 1, 0)

    result = dao._reshape_accounts_hub_row(row)

    # Then 1
    assert result[1].outstanding_total == Decimal("0.00")
    assert result[1].open_count == 1
    # Then 2
    assert result[2].outstanding_total == Decimal("-5.00")


# --------------------------------------------------------------------------- #
# _order_number_search_conditions (through list_invoices)
# --------------------------------------------------------------------------- #


# [claude] AIV-ON-01
def test_aiv_on_01__po_number_finds_invoice_forward(db, st):
    """AIV-ON-01 — a purchase order's number finds its invoice through the forward link.
    Rules: _order_number_search_conditions R1; _build_filtered_query R9"""
    p = st.po("PO-SRCH-77")
    st.inv()
    n2 = st.inv(order_type="purchase_order", order_id=p.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="srch-7"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-02
def test_aiv_on_02__eo_number_finds_invoice_forward(db, st):
    """AIV-ON-02 — an expense order's number finds its invoice through the forward link.
    Rules: _order_number_search_conditions R1"""
    e = st.eo("EX-SRCH-77")
    st.inv()
    n2 = st.inv(order_type="expense_order", order_id=e.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="srch-7"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-03
def test_aiv_on_03__so_number_finds_invoice_forward(db, st):
    """AIV-ON-03 — a sales order's number finds its invoice through the forward link.
    Rules: _order_number_search_conditions R1"""
    s = st.so("SO-SRCH-77")
    st.inv()
    n2 = st.inv(invoice_type="receivable", order_type="sales_order", order_id=s.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="srch-7"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-04
def test_aiv_on_04__wo_number_finds_invoice_forward(db, st):
    """AIV-ON-04 — a work order's number finds its invoice through the forward link.
    Rules: _order_number_search_conditions R1"""
    o = st.wo("WO-SRCH-77")
    st.inv()
    n2 = st.inv(order_type="work_order", order_id=o.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="srch-7"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-05
def test_aiv_on_05__po_pointing_at_invoice_finds_it(db, st):
    """AIV-ON-05 — a purchase order pointing at the invoice finds it (reverse link).
    Rules: _order_number_search_conditions R1"""
    st.inv()
    n2 = st.inv()
    st.inv()
    st.po("PO-SRCH-77", invoice_id=n2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-06
def test_aiv_on_06__eo_pointing_at_invoice_finds_it(db, st):
    """AIV-ON-06 — an expense order pointing at the invoice finds it (reverse link).
    Rules: _order_number_search_conditions R1"""
    st.inv()
    n2 = st.inv()
    st.inv()
    st.eo("EX-SRCH-77", invoice_id=n2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-07
def test_aiv_on_07__so_pointing_at_invoice_finds_it(db, st):
    """AIV-ON-07 — a sales order pointing at the invoice finds it (reverse link).
    Rules: _order_number_search_conditions R1"""
    st.inv()
    n2 = st.inv(invoice_type="receivable")
    st.inv()
    st.so("SO-SRCH-77", invoice_id=n2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-08
def test_aiv_on_08__wo_pointing_at_invoice_finds_it(db, st):
    """AIV-ON-08 — a work order pointing at the invoice finds it (reverse link).
    Rules: _order_number_search_conditions R1"""
    st.inv()
    n2 = st.inv()
    st.inv()
    st.wo("WO-SRCH-77", invoice_id=n2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-09
def test_aiv_on_09__matching_order_without_link_finds_nothing(db, st):
    """AIV-ON-09 — a matching order with no invoice and no forward link finds nothing.
    Rules: _order_number_search_conditions R1"""
    st.inv()
    st.inv()
    st.po("PO-SRCH-77")

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert result == []


# [claude] AIV-ON-10
def test_aiv_on_10__order_type_other_case_does_not_match(db, st):
    """AIV-ON-10 — a forward link whose order_type has other letter case does not match.
    Rules: _order_number_search_conditions R3"""
    p = st.po("PO-SRCH-77")
    st.inv(order_type="Purchase_Order", order_id=p.id)
    n2 = st.inv(order_type="purchase_order", order_id=p.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-11
def test_aiv_on_11__other_kind_with_same_order_id_does_not_match(db, st):
    """AIV-ON-11 — a forward link of another kind with the same order id does not match.
    Rules: _order_number_search_conditions R1"""
    st.po("PO-SRCH-77", id=XID(1))
    st.inv(order_type="expense_order", order_id=XID(1))
    st.inv(order_type="work_order", order_id=XID(1))

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert result == []


# [claude] AIV-ON-12
def test_aiv_on_12__voided_po_number_still_finds_invoice(db, st):
    """AIV-ON-12 — a voided purchase order's number still finds its invoice.
    Rules: _order_number_search_conditions R4"""
    p = st.po("PO-SRCH-77", voided=True)
    st.inv()
    n2 = st.inv(order_type="purchase_order", order_id=p.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-13
def test_aiv_on_13__voided_eo_number_still_finds_invoice(db, st):
    """AIV-ON-13 — a voided expense order's number still finds its invoice.
    Rules: _order_number_search_conditions R4"""
    st.inv()
    n2 = st.inv()
    st.eo("EX-SRCH-77", voided=True, invoice_id=n2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-ON-14
@pytest.mark.xfail(strict=True, reason=R2691)
def test_aiv_on_14__deleted_wo_number_does_not_find_forward(db, st):
    """AIV-ON-14 — a deleted work order's number does not find its invoice (forward link).
    Rules: _order_number_search_conditions R4 [BUG-2691]"""
    o = st.wo("WO-DEL-77", deleted=True)
    st.inv(order_type="work_order", order_id=o.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="wo-del-7"
    )

    # Then 1
    assert result == []


# [claude] AIV-ON-15
@pytest.mark.xfail(strict=True, reason=R2691)
def test_aiv_on_15__deleted_wo_number_does_not_find_reverse(db, st):
    """AIV-ON-15 — a deleted work order's number does not find its invoice (reverse link).
    Rules: _order_number_search_conditions R4 [BUG-2691]"""
    n1 = st.inv()
    st.inv()
    st.wo("WO-DEL-77", deleted=True, invoice_id=n1.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="wo-del-7"
    )

    # Then 1
    assert result == []


# [claude] AIV-ON-16
def test_aiv_on_16__invoice_of_deleted_wo_found_by_own_number(db, st):
    """AIV-ON-16 — an invoice linked to a deleted work order is still found by its own number.
    Rules: _order_number_search_conditions R4; _build_filtered_query R9"""
    o = st.wo("WO-DEL-77", deleted=True)
    n1 = st.inv(invoice_number="INV-KEEP-5", order_type="work_order", order_id=o.id)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="keep-5"
    )

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-ON-17
def test_aiv_on_17__other_workspaces_orders_add_nothing(db, st):
    """AIV-ON-17 — orders of W0 and W2 with the number, on their own invoices, add nothing to W1.
    Rules: _order_number_search_conditions R2"""
    x0 = st.inv0()
    st.po("PO-SRCH-77", of=0, invoice_id=x0.id)
    st.inv()
    p2 = st.po("PO-SRCH-77", of=2)
    st.inv2(order_type="purchase_order", order_id=p2.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="SRCH-77"
    )

    # Then 1
    assert result == []


# [claude] AIV-ON-18
def test_aiv_on_18__underscore_in_order_search_is_literal(db, st):
    """AIV-ON-18 — an underscore in an order-number search is literal.
    Rules: _order_number_search_conditions R1; _build_filtered_query R9"""
    n1 = st.inv()
    n2 = st.inv()
    st.po("PO_77", invoice_id=n1.id)
    st.po("POX77", invoice_id=n2.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="PO_7")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-ON-19
def test_aiv_on_19__every_order_subselect_scoped_to_workspace(db, st):
    """AIV-ON-19 — every order sub-select of the search is scoped to the workspace.
    Rules: _order_number_search_conditions R2"""
    st.inv()
    w1_id = st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_invoices(db, workspace_id=w1_id, invoice_number_search="SRCH")
    sql = rec.sql("account_invoices")

    # Then 1
    assert result == []
    # Then 2
    assert "purchase_orders.workspace_id" in sql
    # Then 3
    assert "expense_orders.workspace_id" in sql
    # Then 4
    assert "sales_orders.workspace_id" in sql
    # Then 5
    assert "work_orders.workspace_id" in sql
    # Then 6
    assert "FOR UPDATE" not in sql


# --------------------------------------------------------------------------- #
# _build_filtered_query (through list_invoices)
# --------------------------------------------------------------------------- #


# [claude] AIV-FQ-01
def test_aiv_fq_01__only_w1_invoices(db, st):
    """AIV-FQ-01 — only W1's invoices, with invoices of W0 and W2 on both sides.
    Rules: _build_filtered_query R1"""
    st.inv0()
    n1 = st.inv()
    n2 = st.inv()
    st.inv2()

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-02
def test_aiv_fq_02__asked_for_w2_only_w2(db, st):
    """AIV-FQ-02 — asked for W2, only W2's invoice, though W0 and W1 come earlier.
    Rules: _build_filtered_query R1"""
    st.inv0()
    st.inv()
    x2 = st.inv2()

    result = dao.list_invoices(db, workspace_id=st.W2.id)

    # Then 1
    assert ids(result) == [x2.id]


# [claude] AIV-FQ-03
def test_aiv_fq_03__asked_for_w0_only_w0(db, st):
    """AIV-FQ-03 — asked for W0, only W0's invoice, though W1 and W2 come later.
    Rules: _build_filtered_query R1"""
    x0 = st.inv0()
    st.inv()
    st.inv2()

    result = dao.list_invoices(db, workspace_id=st.W0.id)

    # Then 1
    assert ids(result) == [x0.id]


# [claude] AIV-FQ-04
def test_aiv_fq_04__closed_account_out_inactive_kept(db, st):
    """AIV-FQ-04 — an invoice of a closed account is left out, one of an inactive account is kept.
    Rules: _build_filtered_query R2"""
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    ai = st.acct(f"Idle {st.TAG}", inactive=True)
    n1 = st.inv()
    st.inv(account_id=ax.id)
    n3 = st.inv(account_id=ai.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {n1.id, n3.id}


# [claude] AIV-FQ-05
def test_aiv_fq_05__deleted_but_active_account_out(db, st):
    """AIV-FQ-05 — an invoice of a deleted but still active account is left out.
    Rules: _build_filtered_query R2"""
    ax = st.acct(f"Half {st.TAG}", half_closed=True)
    n1 = st.inv()
    st.inv(account_id=ax.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {n1.id}


# [claude] AIV-FQ-06
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_fq_06__invoice_on_w2_account_not_listed(db, st):
    """AIV-FQ-06 — a W1 invoice on W2's account is not listed.
    Rules: _build_filtered_query R2a [BUG-2690]"""
    n1 = st.inv()
    st.inv(account_id=st.AC2.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert n1.id in idset(result)
    # Then 2
    assert idset(result) == {n1.id}


# [claude] AIV-FQ-07
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_fq_07__invoice_on_w0_account_not_listed(db, st):
    """AIV-FQ-07 — a W1 invoice on W0's account is not listed.
    Rules: _build_filtered_query R2a [BUG-2690]"""
    n1 = st.inv()
    st.inv(account_id=st.AC0.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert n1.id in idset(result)
    # Then 2
    assert idset(result) == {n1.id}


# [claude] AIV-FQ-08
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_fq_08__foreign_account_name_does_not_find(db, st):
    """AIV-FQ-08 — a foreign account's name does not find a W1 invoice placed on it.
    Rules: _build_filtered_query R2a, R11 [BUG-2690]"""
    az = st._account(st.W2.id, f"Zulu {st.TAG}")
    st.inv()
    st.inv(account_id=az.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_name_search="zulu")

    # Then 1
    assert result == []


# [claude] AIV-FQ-09
def test_aiv_fq_09__all_statuses_listed_without_filter(db, st):
    """AIV-FQ-09 — draft, confirmed and voided invoices are all listed with no filter.
    Rules: _build_filtered_query R3"""
    n1 = st.inv(draft=True)
    n2 = st.inv()
    n3 = st.inv(voided=True)
    n4 = st.inv(paid=True)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {n1.id, n2.id, n3.id, n4.id}


# [claude] AIV-FQ-10
def test_aiv_fq_10__account_id_keeps_one_account(db, st):
    """AIV-FQ-10 — account_id keeps one account, with accounts of lower and higher id.
    Rules: _build_filtered_query R4"""
    al = st.acct(f"Lima {st.TAG}")
    am = st.acct(f"Mike {st.TAG}")
    an = st.acct(f"Nova {st.TAG}")
    st.inv(account_id=al.id)
    n2 = st.inv(account_id=am.id)
    st.inv(account_id=an.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_id=am.id)

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-11
def test_aiv_fq_11__account_id_zero_is_a_filter(db, st):
    """AIV-FQ-11 — account_id 0 is a filter, not "no filter".
    Rules: _build_filtered_query R4"""
    st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_id=0)

    # Then 1
    assert result == []


# [claude] AIV-FQ-12
def test_aiv_fq_12__invoice_type_exact(db, st):
    """AIV-FQ-12 — invoice_type is exact equality.
    Rules: _build_filtered_query R5"""
    st.inv()
    n2 = st.inv(invoice_type="receivable")
    st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_type="receivable")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-13
def test_aiv_fq_13__invoice_type_case_sensitive(db, st):
    """AIV-FQ-13 — invoice_type is case-sensitive.
    Rules: _build_filtered_query R5"""
    st.inv()
    st.inv(invoice_type="receivable")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_type="Payable")

    # Then 1
    assert result == []


# [claude] AIV-FQ-14
def test_aiv_fq_14__unknown_invoice_type_matches_nothing(db, st):
    """AIV-FQ-14 — an unknown invoice_type matches nothing.
    Rules: _build_filtered_query R5"""
    st.inv()
    st.inv(invoice_type="receivable")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_type="bogus")

    # Then 1
    assert result == []


# [claude] AIV-FQ-15
def test_aiv_fq_15__empty_strings_are_no_filter(db, st):
    """AIV-FQ-15 — empty strings for type, payment status and invoice status are no filter.
    Rules: _build_filtered_query R5"""
    n1 = st.inv()
    n2 = st.inv(invoice_type="receivable", partial=Decimal("1.00"), draft=True)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_type="", payment_status="", invoice_status=""
    )

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-16
def test_aiv_fq_16__payment_status_exact(db, st):
    """AIV-FQ-16 — payment_status is exact equality.
    Rules: _build_filtered_query R5"""
    st.inv()
    n2 = st.inv(partial=Decimal("10.00"))
    st.inv(paid=True)

    result = dao.list_invoices(db, workspace_id=st.W1.id, payment_status="partial")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-17
def test_aiv_fq_17__payment_status_capitals_match_nothing(db, st):
    """AIV-FQ-17 — payment_status in capitals matches nothing.
    Rules: _build_filtered_query R5"""
    st.inv(partial=Decimal("10.00"))

    result = dao.list_invoices(db, workspace_id=st.W1.id, payment_status="PARTIAL")

    # Then 1
    assert result == []


# [claude] AIV-FQ-18
def test_aiv_fq_18__invoice_status_exact(db, st):
    """AIV-FQ-18 — invoice_status is exact equality.
    Rules: _build_filtered_query R5"""
    st.inv(draft=True)
    st.inv()
    n3 = st.inv(voided=True)

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_status="voided")

    # Then 1
    assert ids(result) == [n3.id]


# [claude] AIV-FQ-19
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_fq_19__overdue_lists_confirmed_open_due_before_today(db, st):
    """AIV-FQ-19 — "overdue" lists confirmed open invoices due before today.
    Rules: _build_filtered_query R5a [BUG-635]"""
    n1 = st.inv(due_date=PASTDUE)
    n2 = st.inv(partial=Decimal("10.00"), due_date=PASTDUE)
    st.inv(due_date=FARDUE)
    st.inv(paid=True, due_date=PASTDUE)
    st.inv(draft=True, due_date=PASTDUE)
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, payment_status="overdue", today=TD
    )

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-20
def test_aiv_fq_20__invoice_date_bounds_inclusive(db, st):
    """AIV-FQ-20 — invoice date bounds are inclusive on both sides.
    Rules: _build_filtered_query R6"""
    st.inv(invoice_date=D1)
    n2 = st.inv(invoice_date=D2)
    n3 = st.inv(invoice_date=D3)
    n4 = st.inv(invoice_date=D4)
    st.inv(invoice_date=D5)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_date_from=D2, invoice_date_to=D4
    )

    # Then 1
    assert idset(result) == {n2.id, n3.id, n4.id}


# [claude] AIV-FQ-21
def test_aiv_fq_21__lower_due_bound_keeps_day_drops_undated(db, st):
    """AIV-FQ-21 — a lower due-date bound keeps the bound day and drops undated invoices.
    Rules: _build_filtered_query R7"""
    st.inv(due_date=D1)
    n2 = st.inv(due_date=D2)
    n3 = st.inv(due_date=D3)
    st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, due_date_from=D2)

    # Then 1
    assert idset(result) == {n2.id, n3.id}


# [claude] AIV-FQ-22
def test_aiv_fq_22__upper_due_bound_keeps_day_drops_undated(db, st):
    """AIV-FQ-22 — an upper due-date bound keeps the bound day and drops undated invoices.
    Rules: _build_filtered_query R7"""
    n1 = st.inv(due_date=D1)
    n2 = st.inv(due_date=D2)
    st.inv(due_date=D3)
    st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, due_date_to=D2)

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-23
def test_aiv_fq_23__amount_bounds_inclusive(db, st):
    """AIV-FQ-23 — amount bounds are inclusive, one cent outside is out.
    Rules: _build_filtered_query R8"""
    st.inv(invoice_amount=Decimal("99.99"))
    n2 = st.inv(invoice_amount=Decimal("100.00"))
    n3 = st.inv(invoice_amount=Decimal("200.00"))
    st.inv(invoice_amount=Decimal("200.01"))

    result = dao.list_invoices(
        db,
        workspace_id=st.W1.id,
        amount_min=Decimal("100.00"),
        amount_max=Decimal("200.00"),
    )

    # Then 1
    assert idset(result) == {n2.id, n3.id}


# [claude] AIV-FQ-24
def test_aiv_fq_24__amount_max_zero_is_a_bound(db, st):
    """AIV-FQ-24 — amount_max 0 is a bound, not "no filter".
    Rules: _build_filtered_query R8"""
    n1 = st.inv(invoice_amount=Decimal("0.00"))
    st.inv(invoice_amount=Decimal("0.01"))

    result = dao.list_invoices(db, workspace_id=st.W1.id, amount_max=Decimal("0"))

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-25
def test_aiv_fq_25__amount_min_zero_is_a_bound(db, st):
    """AIV-FQ-25 — amount_min 0 is a bound, not "no filter".
    Rules: _build_filtered_query R8"""
    st.inv(invoice_amount=Decimal("-0.01"))
    n2 = st.inv(invoice_amount=Decimal("0.00"))

    result = dao.list_invoices(db, workspace_id=st.W1.id, amount_min=Decimal("0"))

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-26
def test_aiv_fq_26__number_search_middle_any_case(db, st):
    """AIV-FQ-26 — invoice number search matches the middle of the number, any case.
    Rules: _build_filtered_query R9"""
    st.inv(invoice_number="INV-Beta-1")
    n2 = st.inv(invoice_number="INV-Alpha-77")
    st.inv(invoice_number="INV-Gamma-3")

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="aLPHA-7"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-27
def test_aiv_fq_27__vendor_number_searched_too(db, st):
    """AIV-FQ-27 — the vendor invoice number is searched too.
    Rules: _build_filtered_query R9"""
    st.inv(invoice_number="INV-1")
    n2 = st.inv(vendor_invoice_number="VEND-Kilo-9")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="kilo")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-28
def test_aiv_fq_28__number_search_trimmed(db, st):
    """AIV-FQ-28 — the invoice number search is trimmed.
    Rules: _build_filtered_query R9; _invoice_number_search_ilike_term R1"""
    n1 = st.inv(invoice_number="INV-Alpha-77")
    st.inv(invoice_number="INV-Beta-1")

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search="  alpha "
    )

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-29
def test_aiv_fq_29__percent_in_number_search_literal(db, st):
    """AIV-FQ-29 — a percent sign in the number search is literal.
    Rules: _build_filtered_query R9 (HR-8)"""
    n1 = st.inv(invoice_number="50%OFF")
    st.inv(invoice_number="50XOFF")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="50%o")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-30
def test_aiv_fq_30__underscore_in_number_search_literal(db, st):
    """AIV-FQ-30 — an underscore in the number search is literal.
    Rules: _build_filtered_query R9 (HR-8)"""
    n1 = st.inv(invoice_number="A_B-7")
    st.inv(invoice_number="AXB-7")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="a_b")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-31
def test_aiv_fq_31__backslash_in_number_search_literal(db, st):
    """AIV-FQ-31 — a backslash in the number search is literal.
    Rules: _build_filtered_query R9 (HR-8)"""
    n1 = st.inv(invoice_number=r"A\B-7")
    st.inv(invoice_number="AB-7")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search=r"a\b")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-32
def test_aiv_fq_32__no_numbers_do_not_match(db, st):
    """AIV-FQ-32 — invoices with no numbers simply do not match.
    Rules: _build_filtered_query R9"""
    st.inv()
    n2 = st.inv(invoice_number="INV-Alpha-77")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="alpha")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-33
@pytest.mark.xfail(strict=True, reason=R637)
def test_aiv_fq_33__whitespace_only_number_search_no_filter(db, st):
    """AIV-FQ-33 — a whitespace-only number search is no filter.
    Rules: _build_filtered_query R9a [BUG-637]"""
    n1 = st.inv(invoice_number="INV-1")
    n2 = st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="   ")

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-34
def test_aiv_fq_34__empty_number_search_no_filter(db, st):
    """AIV-FQ-34 — an empty number search is no filter.
    Rules: _build_filtered_query R9a"""
    n1 = st.inv(invoice_number="INV-1")
    n2 = st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="")

    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] AIV-FQ-35
def test_aiv_fq_35__ascii_digits_match_invoice_id(db, st):
    """AIV-FQ-35 — an ASCII-digit search also matches the invoice id.
    Rules: _build_filtered_query R10"""
    st.inv()
    n2 = st.inv()
    st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search=str(n2.id)
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-36
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_fq_36__superscript_digit_searched_as_text(db, st):
    """AIV-FQ-36 — a superscript digit is searched as text and never raises.
    Rules: _build_filtered_query R10 [BUG-622]"""
    n1 = st.inv(invoice_number="INV-²")
    st.inv(invoice_number="INV-2")

    result = dao.list_invoices(db, workspace_id=st.W1.id, invoice_number_search="²")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-37
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_fq_37__arabic_indic_digits_do_not_match_id(db, st):
    """AIV-FQ-37 — Arabic-Indic digits do not match the invoice id.
    Rules: _build_filtered_query R10 [BUG-622]"""
    st.inv()
    n2 = st.inv()

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, invoice_number_search=AR(n2.id)
    )

    # Then 1
    assert result == []


# [claude] AIV-FQ-38
def test_aiv_fq_38__account_name_search_middle_any_case(db, st):
    """AIV-FQ-38 — account name search matches the middle of the name, any case.
    Rules: _build_filtered_query R11"""
    ab = st.acct(f"Big Bravo Traders {st.TAG}")
    st.inv()
    n2 = st.inv(account_id=ab.id)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, account_name_search="bRAVO tr"
    )

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-39
def test_aiv_fq_39__account_name_search_not_trimmed(db, st):
    """AIV-FQ-39 — account name search is not trimmed: a leading space is part of the text.
    Rules: _build_filtered_query R11"""
    ab = st.acct(f"Big Acme {st.TAG}")
    st.inv()
    n2 = st.inv(account_id=ab.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_name_search=" acme")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-40
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_fq_40__percent_in_account_name_search_literal(db, st):
    """AIV-FQ-40 — a percent sign in the account name search is literal.
    Rules: _build_filtered_query R11 [BUG-622]"""
    ap = st.acct(f"50% Off {st.TAG}")
    st.inv()
    n2 = st.inv(account_id=ap.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_name_search="%")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-41
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_fq_41__underscore_in_account_name_search_literal(db, st):
    """AIV-FQ-41 — an underscore in the account name search is literal.
    Rules: _build_filtered_query R11 [BUG-622]"""
    au = st.acct(f"A_B {st.TAG}")
    st.inv()
    n2 = st.inv(account_id=au.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_name_search="_")

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-FQ-42
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_fq_42__backslash_in_account_name_search_literal(db, st):
    """AIV-FQ-42 — a backslash in the account name search is literal.
    Rules: _build_filtered_query R11 [BUG-622]"""
    a_s = st.acct(r"Back\Slash " + st.TAG)
    a_t = st.acct(f"BackSlash {st.TAG}")
    n1 = st.inv(account_id=a_s.id)
    st.inv(account_id=a_t.id)

    result = dao.list_invoices(db, workspace_id=st.W1.id, account_name_search=r"k\S")

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-43
def test_aiv_fq_43__all_filters_combine_with_and(db, st):
    """AIV-FQ-43 — all filters combine with AND.
    Rules: _build_filtered_query R13"""
    ab = st.acct(f"Beta {st.TAG}")
    n1 = st.inv(invoice_type="receivable", invoice_date=D3)
    st.inv(invoice_type="receivable", invoice_date=D1)
    st.inv(invoice_date=D3)
    st.inv(account_id=ab.id, invoice_type="receivable", invoice_date=D3)

    result = dao.list_invoices(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        invoice_type="receivable",
        invoice_date_from=D2,
    )

    # Then 1
    assert ids(result) == [n1.id]


# [claude] AIV-FQ-44
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_fq_44__overdue_day_boundary(db, st):
    """AIV-FQ-44 — "overdue" day boundary: due the day before today is overdue, due today or tomorrow is not.
    Rules: _build_filtered_query R5a [BUG-635]"""
    n1 = st.inv(due_date=TDM1)
    st.inv(due_date=TD)
    st.inv(due_date=TDP1)
    st.inv()
    n5 = st.inv(partial=Decimal("10.00"), due_date=TDM1)
    st.inv(paid=True, due_date=TDM1)

    result = dao.list_invoices(
        db, workspace_id=st.W1.id, payment_status="overdue", today=TD
    )

    # Then 1
    assert idset(result) == {n1.id, n5.id}


# --------------------------------------------------------------------------- #
# list_invoices
# --------------------------------------------------------------------------- #


# [claude] AIV-LI-01
def test_aiv_li_01__newest_date_first_ties_by_higher_id(db, st):
    """AIV-LI-01 — newest invoice date first, ties by higher id, an older invoice with the highest id last.
    Rules: list_invoices R1, R2"""
    n1 = st.inv(invoice_date=D2)
    n2 = st.inv(invoice_date=D3)
    n3 = st.inv(invoice_date=D2)
    n4 = st.inv(invoice_date=D1)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert type(result) is list
    # Then 2
    assert ids(result) == [n2.id, n3.id, n1.id, n4.id]


# [claude] AIV-LI-02
def test_aiv_li_02__default_limit_is_100(db, st):
    """AIV-LI-02 — the default limit is 100.
    Rules: list_invoices R3"""
    st.invs(101)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert result[0].invoice_number == "BULK-0100"
    # Then 3
    assert result[-1].invoice_number == "BULK-0001"


# [claude] AIV-LI-03
def test_aiv_li_03__skip_and_limit_cut_ordered_list(db, st):
    """AIV-LI-03 — skip and limit cut the ordered list.
    Rules: list_invoices R3"""
    st.invs(6)

    result = dao.list_invoices(db, workspace_id=st.W1.id, skip=2, limit=3)

    # Then 1
    assert [r.invoice_number for r in result] == ["BULK-0003", "BULK-0002", "BULK-0001"]


# [claude] AIV-LI-04
def test_aiv_li_04__limit_1000_returns_1000_of_1001(db, st):
    """AIV-LI-04 — limit 1000 returns 1000 of 1001 rows.
    Rules: list_invoices R3"""
    st.invs(1001)

    result = dao.list_invoices(db, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 1000
    # Then 2
    assert result[-1].invoice_number == "BULK-0001"


# [claude] AIV-LI-05
def test_aiv_li_05__filtering_before_paging(db, st):
    """AIV-LI-05 — filtering happens before paging.
    Rules: list_invoices R3; _build_filtered_query R2 (HR-5)"""
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    st.inv(account_id=ax.id, invoice_date=D5)
    st.inv(invoice_date=D4)
    n2 = st.inv(invoice_date=D3)
    st.inv(invoice_date=D2)

    result = dao.list_invoices(db, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [n2.id]


# [claude] AIV-LI-06
def test_aiv_li_06__skip_past_end_empty_list(db, st):
    """AIV-LI-06 — a skip past the end returns an empty list.
    Rules: list_invoices R3"""
    st.inv()
    st.inv()

    result = dao.list_invoices(db, workspace_id=st.W1.id, skip=2)

    # Then 1
    assert result == []
    # Then 2
    assert type(result) is list


# [claude] AIV-LI-07
def test_aiv_li_07__query_orders_date_then_id_no_lock(db, st):
    """AIV-LI-07 — the query orders by date then id, both descending, with no row lock.
    Rules: list_invoices R2"""
    n1 = st.inv()
    n1_id, w1_id = n1.id, st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_invoices(db, workspace_id=w1_id)
    sql = rec.sql("account_invoices")

    # Then 1
    assert ids(result) == [n1_id]
    # Then 2
    assert "account_invoices.invoice_date DESC, account_invoices.id DESC" in order_part(
        sql
    )
    # Then 3
    assert "FOR UPDATE" not in sql
    # Then 4
    assert rec.written == []


# [claude] AIV-LI-08
def test_aiv_li_08__writes_nothing(db, st):
    """AIV-LI-08 — writes nothing: a pending invoice stays pending, an unflushed edit stays unflushed.
    Rules: list_invoices R1 (reader)"""
    x = st.inv(notes="before")
    x.notes = "edited"
    p = AccountInvoice(**st._inv_fields(st.W1, st.AC1, invoice_number="PEND-1"))
    db.add(p)

    result = dao.list_invoices(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [x.id]
    # Then 2
    assert p in db.new
    assert len(db.new) == 1
    # Then 3
    assert x in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert x.notes == "edited"


# --------------------------------------------------------------------------- #
# list_invoices_page
# --------------------------------------------------------------------------- #


# [claude] AIV-LP-01
def test_aiv_lp_01__every_invoice_of_account_and_total(db, st):
    """AIV-LP-01 — without open_balance_only, every invoice of the account and the total.
    Rules: list_invoices_page R1; list_invoices_page_filtered R1, R2"""
    al = st.acct(f"Lima {st.TAG}")
    n1 = st.inv(invoice_date=D1)
    n2 = st.inv(voided=True, invoice_date=D3)
    n3 = st.inv(paid=True, invoice_date=D2)
    st.inv(account_id=al.id)
    an = st.acct(f"Nova {st.TAG}")
    st.inv(account_id=an.id)

    result = dao.list_invoices_page(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert ids(result[0]) == [n2.id, n3.id, n1.id]
    # Then 2
    assert result[1] == 3


# [claude] AIV-LP-02
def test_aiv_lp_02__open_balance_only_unpaid_and_partial(db, st):
    """AIV-LP-02 — open_balance_only keeps confirmed unpaid and partial invoices only.
    Rules: list_invoices_page R1; _build_filtered_query R12"""
    n1 = st.inv()
    n2 = st.inv(partial=Decimal("10.00"))
    st.inv(paid=True)
    st.inv(voided=True)

    result = dao.list_invoices_page(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, open_balance_only=True
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n1.id]
    # Then 2
    assert result[1] == 2


# [claude] AIV-LP-03
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_lp_03__open_balance_only_leaves_drafts_out(db, st):
    """AIV-LP-03 — open_balance_only leaves drafts out.
    Rules: list_invoices_page R1; _build_filtered_query R12 [BUG-634]"""
    n1 = st.inv()
    st.inv(draft=True)

    result = dao.list_invoices_page(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, open_balance_only=True
    )

    # Then 1
    assert ids(result[0]) == [n1.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-LP-04
def test_aiv_lp_04__default_page_10_total_11(db, st):
    """AIV-LP-04 — the default page is 10 rows, the total counts all 11.
    Rules: list_invoices_page R1; list_invoices_page_filtered R4"""
    st.invs(11)

    result = dao.list_invoices_page(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert len(result[0]) == 10
    # Then 2
    assert result[0][-1].invoice_number == "BULK-0001"
    # Then 3
    assert result[1] == 11


# [claude] AIV-LP-05
def test_aiv_lp_05__skip_limit_cut_page_total_ignores(db, st):
    """AIV-LP-05 — skip and limit cut the page, the total ignores them.
    Rules: list_invoices_page R1; list_invoices_page_filtered R2, R4"""
    st.invs(6)

    result = dao.list_invoices_page(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, skip=2, limit=3
    )

    # Then 1
    assert [r.invoice_number for r in result[0]] == [
        "BULK-0003",
        "BULK-0002",
        "BULK-0001",
    ]
    # Then 2
    assert result[1] == 6


# [claude] AIV-LP-06
def test_aiv_lp_06__prioritised_order_invoices_first(db, st):
    """AIV-LP-06 — prioritize_purchase_order_id puts that order's invoices first.
    Rules: list_invoices_page R1; list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1, order_type="purchase_order", order_id=XID(1))
    n3 = st.inv(invoice_date=D3)

    result = dao.list_invoices_page(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=XID(1),
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n1.id, n3.id]
    # Then 2
    assert result[1] == 3


# [claude] AIV-LP-07
def test_aiv_lp_07__w1_does_not_see_w2_invoice(db, st):
    """AIV-LP-07 — W1 does not see W2's invoice when asking for W2's account.
    Rules: list_invoices_page R1; _build_filtered_query R1"""
    st.inv0()
    st.inv()
    st.inv2()

    result = dao.list_invoices_page(db, workspace_id=st.W1.id, account_id=st.AC2.id)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 0


# [claude] AIV-LP-08
def test_aiv_lp_08__w1_does_not_see_w0_invoice(db, st):
    """AIV-LP-08 — W1 does not see W0's invoice when asking for W0's account.
    Rules: list_invoices_page R1; _build_filtered_query R1"""
    st.inv0()
    st.inv()
    st.inv2()

    result = dao.list_invoices_page(db, workspace_id=st.W1.id, account_id=st.AC0.id)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 0


# [claude] AIV-LP-09
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_lp_09__w1_invoice_on_w2_account_not_listed(db, st):
    """AIV-LP-09 — a W1 invoice placed on W2's account is not listed under that account.
    Rules: list_invoices_page R1; _build_filtered_query R2a [BUG-2690]"""
    st.inv()
    st.inv(account_id=st.AC2.id)

    result = dao.list_invoices_page(db, workspace_id=st.W1.id, account_id=st.AC2.id)

    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == 0


# --------------------------------------------------------------------------- #
# list_invoices_page_filtered
# --------------------------------------------------------------------------- #


# [claude] AIV-PF-01
def test_aiv_pf_01__total_counts_all_page_cut_after_order(db, st):
    """AIV-PF-01 — total counts every match, the page is cut after ordering.
    Rules: list_invoices_page_filtered R1, R2, R4"""
    st.inv(invoice_date=D1)
    st.inv(invoice_date=D2)
    n3 = st.inv(invoice_date=D3)
    n4 = st.inv(invoice_date=D4)
    st.inv(invoice_date=D5)

    result = dao.list_invoices_page_filtered(db, workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result[0]) == [n4.id, n3.id]
    # Then 2
    assert result[1] == 5


# [claude] AIV-PF-02
def test_aiv_pf_02__newest_date_first_ties_by_higher_id(db, st):
    """AIV-PF-02 — newest date first, ties by higher id, an older invoice with the highest id last.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D2)
    n2 = st.inv(invoice_date=D3)
    n3 = st.inv(invoice_date=D2)
    n4 = st.inv(invoice_date=D1)

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, account_id=st.AC1.id
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n3.id, n1.id, n4.id]


# [claude] AIV-PF-03
def test_aiv_pf_03__prioritised_first_each_group_date_then_id(db, st):
    """AIV-PF-03 — prioritised invoices come first, each group by date then id, both descending.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1, order_type="purchase_order", order_id=XID(1))
    n3 = st.inv(invoice_date=D2, order_type="purchase_order", order_id=XID(1))
    n4 = st.inv(invoice_date=D1, order_type="purchase_order", order_id=XID(1))
    n5 = st.inv(invoice_date=D3)
    n6 = st.inv(invoice_date=D3, order_type="purchase_order", order_id=XID(2))

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=XID(1),
    )

    # Then 1
    assert ids(result[0]) == [n3.id, n4.id, n2.id, n1.id, n6.id, n5.id]
    # Then 2
    assert result[1] == 6


# [claude] AIV-PF-04
def test_aiv_pf_04__receivable_credit_note_prioritised_too(db, st):
    """AIV-PF-04 — a receivable credit note of the prioritised order is prioritised too.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(
        invoice_type="receivable",
        invoice_date=D1,
        order_type="purchase_order",
        order_id=XID(1),
    )

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=XID(1),
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n1.id]


# [claude] AIV-PF-05
def test_aiv_pf_05__reverse_link_only_not_prioritised(db, st):
    """AIV-PF-05 — an invoice linked only through the order's invoice_id is not prioritised.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1)
    p = st.po("PO-PRIO-1", invoice_id=n2.id)

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=p.id,
    )

    # Then 1
    assert ids(result[0]) == [n1.id, n2.id]


# [claude] AIV-PF-06
def test_aiv_pf_06__expense_link_same_id_not_prioritised(db, st):
    """AIV-PF-06 — an expense-order link with the same order id is not prioritised.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1, order_type="expense_order", order_id=XID(1))
    n3 = st.inv(invoice_date=D2, order_type="Purchase_Order", order_id=XID(1))

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=XID(1),
    )

    # Then 1
    assert ids(result[0]) == [n1.id, n3.id, n2.id]


# [claude] AIV-PF-07
def test_aiv_pf_07__prioritise_zero_is_given(db, st):
    """AIV-PF-07 — prioritize_purchase_order_id 0 is given, not "none".
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1, order_type="purchase_order", order_id=0)

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, prioritize_purchase_order_id=0
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n1.id]


# [claude] AIV-PF-08
def test_aiv_pf_08__prioritised_rows_paged_after_ordering(db, st):
    """AIV-PF-08 — prioritised rows are paged after ordering.
    Rules: list_invoices_page_filtered R3, R4"""
    n1 = st.inv(invoice_date=D5)
    n2 = st.inv(invoice_date=D1, order_type="purchase_order", order_id=XID(1))
    st.inv(invoice_date=D2, order_type="purchase_order", order_id=XID(1))
    st.inv(invoice_date=D4)

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        prioritize_purchase_order_id=XID(1),
        skip=1,
        limit=2,
    )

    # Then 1
    assert ids(result[0]) == [n2.id, n1.id]
    # Then 2
    assert result[1] == 4


# [claude] AIV-PF-09
def test_aiv_pf_09__default_page_is_10(db, st):
    """AIV-PF-09 — the default page is 10 rows.
    Rules: list_invoices_page_filtered R4"""
    st.invs(11)

    result = dao.list_invoices_page_filtered(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result[0]) == 10
    # Then 2
    assert result[0][-1].invoice_number == "BULK-0001"
    # Then 3
    assert result[1] == 11


# [claude] AIV-PF-10
def test_aiv_pf_10__limit_1000_of_1001_total_1001(db, st):
    """AIV-PF-10 — limit 1000 returns 1000 of 1001 rows, total 1001.
    Rules: list_invoices_page_filtered R2, R4"""
    st.invs(1001)

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, limit=1000
    )

    # Then 1
    assert len(result[0]) == 1000
    # Then 2
    assert result[1] == 1001


# [claude] AIV-PF-11
def test_aiv_pf_11__filtering_before_paging_and_total(db, st):
    """AIV-PF-11 — filtering happens before paging and before the total.
    Rules: list_invoices_page_filtered R1, R2 (HR-5)"""
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    st.inv(account_id=ax.id, invoice_date=D5)
    st.inv(invoice_date=D4)
    n2 = st.inv(invoice_date=D3)
    st.inv(invoice_date=D2)

    result = dao.list_invoices_page_filtered(db, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result[0]) == [n2.id]
    # Then 2
    assert result[1] == 3


# [claude] AIV-PF-12
def test_aiv_pf_12__payment_status_and_number_search_passed(db, st):
    """AIV-PF-12 — every filter is passed through: payment status and number search together.
    Rules: list_invoices_page_filtered R1"""
    n1 = st.inv(partial=Decimal("5.00"), invoice_number="INV-Alpha-1")
    st.inv(invoice_number="INV-Alpha-2")
    st.inv(partial=Decimal("5.00"), invoice_number="INV-Beta-3")

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        payment_status="partial",
        invoice_number_search="alpha",
    )

    # Then 1
    assert ids(result[0]) == [n1.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-PF-13
def test_aiv_pf_13__amount_bounds_and_name_search_passed(db, st):
    """AIV-PF-13 — amount bounds and account name search are passed through.
    Rules: list_invoices_page_filtered R1"""
    ab = st.acct(f"Bravo {st.TAG}")
    n1 = st.inv(account_id=ab.id, invoice_amount=Decimal("50.00"))
    st.inv(account_id=ab.id, invoice_amount=Decimal("500.00"))
    st.inv(invoice_amount=Decimal("50.00"))

    result = dao.list_invoices_page_filtered(
        db,
        workspace_id=st.W1.id,
        account_name_search="bravo",
        amount_max=Decimal("100.00"),
    )

    # Then 1
    assert ids(result[0]) == [n1.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-PF-14
def test_aiv_pf_14__open_balance_only_leaves_paid_voided_out(db, st):
    """AIV-PF-14 — open_balance_only leaves paid and voided invoices out.
    Rules: list_invoices_page_filtered R1; _build_filtered_query R12"""
    n1 = st.inv()
    st.inv(paid=True)
    st.inv(voided=True)
    n4 = st.inv(partial=Decimal("99.99"))

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, open_balance_only=True
    )

    # Then 1
    assert ids(result[0]) == [n4.id, n1.id]
    # Then 2
    assert result[1] == 2


# [claude] AIV-PF-15
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_pf_15__open_balance_only_leaves_drafts_out(db, st):
    """AIV-PF-15 — open_balance_only leaves drafts out.
    Rules: list_invoices_page_filtered R1; _build_filtered_query R12 [BUG-634]"""
    n1 = st.inv()
    st.inv(draft=True, partial=Decimal("10.00"))

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, open_balance_only=True
    )

    # Then 1
    assert ids(result[0]) == [n1.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-PF-16
def test_aiv_pf_16__w0_w2_neither_listed_nor_counted(db, st):
    """AIV-PF-16 — W0's and W2's invoices are neither listed nor counted.
    Rules: list_invoices_page_filtered R1, R2; _build_filtered_query R1"""
    st.inv0()
    n1 = st.inv()
    st.inv2()

    result = dao.list_invoices_page_filtered(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result[0]) == [n1.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-PF-17
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_pf_17__invoice_on_w0_account_neither_listed_nor_counted(db, st):
    """AIV-PF-17 — a W1 invoice on W0's account is neither listed nor counted.
    Rules: list_invoices_page_filtered R1, R2; _build_filtered_query R2a [BUG-2690]"""
    n1 = st.inv()
    st.inv(account_id=st.AC0.id)

    result = dao.list_invoices_page_filtered(db, workspace_id=st.W1.id)

    # Then 1
    assert n1.id in idset(result[0])
    # Then 2
    assert result[1] == 1
    # Then 3
    assert ids(result[0]) == [n1.id]


# [claude] AIV-PF-18
def test_aiv_pf_18__page_query_ends_in_id_no_lock(db, st):
    """AIV-PF-18 — the page query ends its order in id, with no row lock.
    Rules: list_invoices_page_filtered R3"""
    n1 = st.inv()
    n1_id, w1_id, ac1_id = n1.id, st.W1.id, st.AC1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_invoices_page_filtered(
            db, workspace_id=w1_id, account_id=ac1_id
        )
    sql = rec.sql("account_invoices", ordered=True)

    # Then 1
    assert ids(result[0]) == [n1_id]
    # Then 2
    assert order_part(sql).rstrip().endswith("account_invoices.id DESC")
    # Then 3
    assert "FOR UPDATE" not in sql
    # Then 4
    assert rec.written == []


# [claude] AIV-PF-19
def test_aiv_pf_19__without_open_balance_only_all_listed_and_counted(db, st):
    """AIV-PF-19 — open_balance_only not sent: paid, voided and draft invoices are all listed and counted.
    Rules: list_invoices_page_filtered R1 (default open_balance_only=False); _build_filtered_query R12"""
    n1 = st.inv()
    n2 = st.inv(paid=True)
    n3 = st.inv(voided=True)
    n4 = st.inv(draft=True)

    result = dao.list_invoices_page_filtered(
        db, workspace_id=st.W1.id, account_id=st.AC1.id
    )

    # Then 1
    assert ids(result[0]) == [n4.id, n3.id, n2.id, n1.id]
    # Then 2
    assert result[1] == 4


# --------------------------------------------------------------------------- #
# list_accounts_hub_page (with _open_balance_subquery)
# --------------------------------------------------------------------------- #


# [claude] AIV-AH-01
def test_aiv_ah_01__each_account_with_both_open_balances(db, st):
    """AIV-AH-01 — each account comes with its payable and receivable open balances.
    Rules: list_accounts_hub_page R1, R2; _open_balance_subquery R1, R2"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ac = st.acct(f"Charlie {st.TAG}")
    st.inv(account_id=ab.id, invoice_amount=Decimal("100.10"))
    st.inv(account_id=ab.id, invoice_amount=Decimal("200.20"), partial=Decimal("0.05"))
    st.inv(account_id=ab.id, invoice_amount=Decimal("50.00"), paid=True)
    st.inv(account_id=ab.id, invoice_amount=Decimal("70.00"), voided=True)
    st.inv(account_id=ab.id, invoice_type="receivable", invoice_amount=Decimal("0.10"))
    st.inv(account_id=ab.id, invoice_type="receivable", invoice_amount=Decimal("0.20"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id, ac.id]
    # Then 2
    assert result[1] == 2
    # Then 3
    assert pay(result, ab).outstanding_total == Decimal("300.25")
    assert pay(result, ab).open_count == 2
    assert pay(result, ab).has_overdue is False
    # Then 4
    assert rec(result, ab).outstanding_total == Decimal("0.30")
    assert rec(result, ab).open_count == 2
    assert rec(result, ab).has_overdue is False
    # Then 5
    assert pay(result, ac).outstanding_total == 0
    assert pay(result, ac).open_count == 0
    assert pay(result, ac).has_overdue is False
    # Then 6
    assert rec(result, ac).outstanding_total == 0
    assert rec(result, ac).open_count == 0
    # Then 7
    assert isinstance(pay(result, ab).outstanding_total, Decimal)


# [claude] AIV-AH-02
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_ah_02__draft_adds_nothing_to_open_balance(db, st):
    """AIV-AH-02 — a draft adds nothing to the open balance.
    Rules: _open_balance_subquery R1 [BUG-634]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv(account_id=ab.id, invoice_amount=Decimal("40.00"))
    st.inv(account_id=ab.id, draft=True)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert pay(result, ab).outstanding_total == Decimal("40.00")
    # Then 3
    assert pay(result, ab).open_count == 1


# [claude] AIV-AH-03
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_ah_03__open_invoice_due_before_today_sets_overdue(db, st):
    """AIV-AH-03 — an open invoice due before today sets has_overdue.
    Rules: _open_balance_subquery R2 [BUG-635]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv(account_id=ab.id, due_date=PASTDUE)
    st.inv(account_id=ab.id, due_date=FARDUE)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, today=TD)

    # Then 1
    assert pay(result, ab).open_count == 2
    # Then 2
    assert pay(result, ab).has_overdue is True


# [claude] AIV-AH-04
def test_aiv_ah_04__far_ahead_or_undated_never_overdue(db, st):
    """AIV-AH-04 — open invoices due far ahead or undated never set has_overdue.
    Rules: _open_balance_subquery R2"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv(account_id=ab.id, due_date=FARDUE)
    st.inv(account_id=ab.id, invoice_type="receivable")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert pay(result, ab).has_overdue is False
    # Then 2
    assert rec(result, ab).has_overdue is False


# [claude] AIV-AH-05
@pytest.mark.xfail(strict=True, reason=R636)
def test_aiv_ah_05__inactive_account_with_open_balance_shown(db, st):
    """AIV-AH-05 — an inactive account with an open balance is shown.
    Rules: list_accounts_hub_page R1 [BUG-636]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ai = st.acct(f"Idle {st.TAG}", inactive=True)
    st.inv(account_id=ai.id, invoice_amount=Decimal("12.34"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id, ai.id]
    # Then 2
    assert pay(result, ai).outstanding_total == Decimal("12.34")


# [claude] AIV-AH-06
def test_aiv_ah_06__inactive_account_nothing_open_not_shown(db, st):
    """AIV-AH-06 — an inactive account with nothing open is not shown.
    Rules: list_accounts_hub_page R1"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ai = st.acct(f"Idle {st.TAG}", inactive=True)
    st.inv(account_id=ai.id, paid=True)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-07
def test_aiv_ah_07__closed_account_not_shown(db, st):
    """AIV-AH-07 — a closed account is not shown, even with an open invoice.
    Rules: list_accounts_hub_page R1"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    st.inv(account_id=ax.id)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-08
def test_aiv_ah_08__deleted_active_account_not_shown(db, st):
    """AIV-AH-08 — a deleted but still active account is not shown.
    Rules: list_accounts_hub_page R1"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.acct(f"Half {st.TAG}", half_closed=True)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]


# [claude] AIV-AH-09
def test_aiv_ah_09__w1_hub_has_no_other_workspace_accounts(db, st):
    """AIV-AH-09 — W1's hub has none of W0's or W2's accounts.
    Rules: list_accounts_hub_page R1"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv0()
    st.inv2()

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-10
def test_aiv_ah_10__asked_for_w2_only_w2_account(db, st):
    """AIV-AH-10 — asked for W2, only W2's account, with its own balance.
    Rules: list_accounts_hub_page R1, R2"""
    st.inv0()
    st.inv()
    st.inv2(invoice_amount=Decimal("7.00"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W2.id)

    # Then 1
    assert hids(result) == [st.AC2.id]
    # Then 2
    assert pay(result, st.AC2).outstanding_total == Decimal("7.00")
    assert pay(result, st.AC2).open_count == 1


# [claude] AIV-AH-11
def test_aiv_ah_11__asked_for_w0_only_w0_account(db, st):
    """AIV-AH-11 — asked for W0, only W0's account, with its own balance.
    Rules: list_accounts_hub_page R1, R2"""
    st.inv0(invoice_amount=Decimal("8.00"))
    st.inv()
    st.inv2()

    result = dao.list_accounts_hub_page(db, workspace_id=st.W0.id)

    # Then 1
    assert hids(result) == [st.AC0.id]
    # Then 2
    assert pay(result, st.AC0).outstanding_total == Decimal("8.00")
    assert pay(result, st.AC0).open_count == 1


# [claude] AIV-AH-12
def test_aiv_ah_12__invoice_on_w2_account_on_no_w1_row(db, st):
    """AIV-AH-12 — a W1 invoice on W2's account shows on no W1 hub row.
    Rules: _open_balance_subquery R1a; list_accounts_hub_page R1"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv(account_id=ab.id, invoice_amount=Decimal("10.00"))
    st.inv(account_id=st.AC2.id, invoice_amount=Decimal("90.00"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert pay(result, ab).outstanding_total == Decimal("10.00")
    assert pay(result, ab).open_count == 1


# [claude] AIV-AH-13
def test_aiv_ah_13__section_payable(db, st):
    """AIV-AH-13 — section "payable" keeps accounts with a payable balance only.
    Rules: list_accounts_hub_page R3, R6"""
    st.hubclean()
    ap = st.acct(f"Papa {st.TAG}")
    ar = st.acct(f"Romeo {st.TAG}")
    st.acct(f"November {st.TAG}")
    st.inv(account_id=ap.id, invoice_amount=Decimal("10.00"))
    st.inv(account_id=ar.id, invoice_type="receivable", invoice_amount=Decimal("10.00"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="payable")

    # Then 1
    assert hids(result) == [ap.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-14
def test_aiv_ah_14__section_receivable(db, st):
    """AIV-AH-14 — section "receivable" keeps accounts with a receivable balance only.
    Rules: list_accounts_hub_page R3, R6"""
    st.hubclean()
    ap = st.acct(f"Papa {st.TAG}")
    ar = st.acct(f"Romeo {st.TAG}")
    st.acct(f"November {st.TAG}")
    st.inv(account_id=ap.id, invoice_amount=Decimal("10.00"))
    st.inv(account_id=ar.id, invoice_type="receivable", invoice_amount=Decimal("10.00"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="receivable")

    # Then 1
    assert hids(result) == [ar.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-15
def test_aiv_ah_15__section_overview_no_balance_filter(db, st):
    """AIV-AH-15 — section "overview" has no balance filter.
    Rules: list_accounts_hub_page R3"""
    st.hubclean()
    ap = st.acct(f"Papa {st.TAG}")
    an = st.acct(f"November {st.TAG}")
    st.inv(account_id=ap.id)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="overview")

    # Then 1
    assert hids(result) == [an.id, ap.id]
    # Then 2
    assert result[1] == 2


# [claude] AIV-AH-16
def test_aiv_ah_16__unknown_section_no_balance_filter(db, st):
    """AIV-AH-16 — an unknown section has no balance filter.
    Rules: list_accounts_hub_page R3"""
    st.hubclean()
    ap = st.acct(f"Papa {st.TAG}")
    an = st.acct(f"November {st.TAG}")
    st.inv(account_id=ap.id)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="Payable")

    # Then 1
    assert hids(result) == [an.id, ap.id]


# [claude] AIV-AH-17
def test_aiv_ah_17__empty_section_no_balance_filter(db, st):
    """AIV-AH-17 — an empty section has no balance filter.
    Rules: list_accounts_hub_page R3"""
    st.hubclean()
    ap = st.acct(f"Papa {st.TAG}")
    an = st.acct(f"November {st.TAG}")
    st.inv(account_id=ap.id)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="")

    # Then 1
    assert hids(result) == [an.id, ap.id]


# [claude] AIV-AH-18
def test_aiv_ah_18__zero_payable_balance_not_above_zero(db, st):
    """AIV-AH-18 — a payable balance of 0.00 is not "> 0", one of 0.01 is.
    Rules: list_accounts_hub_page R3"""
    st.hubclean()
    az = st.acct(f"Zero {st.TAG}")
    ao = st.acct(f"One {st.TAG}")
    st.inv(account_id=az.id, invoice_amount=Decimal("0.00"))
    st.inv(account_id=ao.id, invoice_amount=Decimal("0.01"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="payable")

    # Then 1
    assert hids(result) == [ao.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-19
def test_aiv_ah_19__search_middle_any_case(db, st):
    """AIV-AH-19 — search matches the middle of the account name, any case.
    Rules: list_accounts_hub_page R4, R6"""
    st.hubclean()
    ab = st.acct(f"Big Bravo Traders {st.TAG}")
    st.acct(f"Charlie {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, search="bRAVO tr")

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert result[1] == 1


# [claude] AIV-AH-20
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_ah_20__percent_in_hub_search_literal(db, st):
    """AIV-AH-20 — a percent sign in the hub search is literal.
    Rules: list_accounts_hub_page R4 [BUG-622]"""
    st.hubclean()
    ap = st.acct(f"50% Off {st.TAG}")
    st.acct(f"Charlie {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, search="%")

    # Then 1
    assert hids(result) == [ap.id]


# [claude] AIV-AH-21
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_ah_21__underscore_in_hub_search_literal(db, st):
    """AIV-AH-21 — an underscore in the hub search is literal.
    Rules: list_accounts_hub_page R4 [BUG-622]"""
    st.hubclean()
    au = st.acct(f"A_B {st.TAG}")
    st.acct(f"Charlie {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, search="_")

    # Then 1
    assert hids(result) == [au.id]


# [claude] AIV-AH-22
@pytest.mark.xfail(strict=True, reason=R622)
def test_aiv_ah_22__backslash_in_hub_search_literal(db, st):
    """AIV-AH-22 — a backslash in the hub search is literal.
    Rules: list_accounts_hub_page R4 [BUG-622]"""
    st.hubclean()
    a_s = st.acct(r"Back\Slash " + st.TAG)
    st.acct(f"BackSlash {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, search=r"k\S")

    # Then 1
    assert hids(result) == [a_s.id]


# [claude] AIV-AH-23
def test_aiv_ah_23__ordered_by_name_not_id(db, st):
    """AIV-AH-23 — accounts are ordered by name, not by id.
    Rules: list_accounts_hub_page R5"""
    st.hubclean()
    ad = st.acct(f"Delta {st.TAG}")
    ac = st.acct(f"Charlie {st.TAG}")
    ab = st.acct(f"Bravo {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id, ac.id, ad.id]


# [claude] AIV-AH-24
def test_aiv_ah_24__same_name_ordered_by_id(db, st):
    """AIV-AH-24 — accounts with the same name are ordered by id ascending.
    Rules: list_accounts_hub_page R5"""
    st.hubclean()
    e1 = st.acct(f"Echo {st.TAG}")
    e2 = st.acct(f"Echo {st.TAG}")
    e3 = st.acct(f"Echo {st.TAG}")
    e1_id, e2_id, e3_id = e1.id, e2.id, e3.id
    db.execute(text("UPDATE accounts SET name = name WHERE id = :i"), {"i": e1_id})
    db.expire_all()

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [e1_id, e2_id, e3_id]


# [claude] AIV-AH-25
@pytest.mark.xfail(strict=True, reason=R623)
def test_aiv_ah_25__case_only_names_case_insensitive_then_id(db, st):
    """AIV-AH-25 — names that differ only in case are ordered case-insensitively, then by id.
    Rules: list_accounts_hub_page R5 [BUG-623]"""
    st.hubclean()
    b1 = st.acct(f"Bravo {st.TAG}")
    b2 = st.acct(f"bravo {st.TAG}")
    b3 = st.acct(f"BRAVO {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [b1.id, b2.id, b3.id]


# [claude] AIV-AH-26
@pytest.mark.xfail(strict=True, reason=R623)
def test_aiv_ah_26__hub_query_orders_by_lower_name(db, st):
    """AIV-AH-26 — the hub query orders by the lower-cased name.
    Rules: list_accounts_hub_page R5 [BUG-623]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ab_id, w1_id = ab.id, st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_accounts_hub_page(db, workspace_id=w1_id)
    sql = rec.sql("accounts", ordered=True)

    # Then 1
    assert hids(result) == [ab_id]
    # Then 2
    assert "lower(accounts.name)" in order_part(sql).lower()


# [claude] AIV-AH-27
def test_aiv_ah_27__hub_query_ends_in_id_no_lock(db, st):
    """AIV-AH-27 — the hub query ends its order in accounts.id and takes no row lock.
    Rules: list_accounts_hub_page R5"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ab_id, w1_id = ab.id, st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_accounts_hub_page(db, workspace_id=w1_id)
    sql = rec.sql("accounts", ordered=True)

    # Then 1
    assert hids(result) == [ab_id]
    # Then 2
    assert order_part(sql).rstrip().endswith("accounts.id ASC")
    # Then 3
    assert "FOR UPDATE" not in sql
    # Then 4
    assert rec.written == []


# [claude] AIV-AH-28
def test_aiv_ah_28__total_all_page_cut_after_order(db, st):
    """AIV-AH-28 — total counts every account, the page is cut after ordering.
    Rules: list_accounts_hub_page R6"""
    st.hubclean()
    st.acct(f"Delta {st.TAG}")
    st.acct(f"Bravo {st.TAG}")
    ac = st.acct(f"Charlie {st.TAG}")

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert hids(result) == [ac.id]
    # Then 2
    assert result[1] == 3


# [claude] AIV-AH-29
def test_aiv_ah_29__default_page_50_total_51(db, st):
    """AIV-AH-29 — the default page is 50 accounts, the total counts all 51.
    Rules: list_accounts_hub_page R6"""
    st.hubclean()
    st.accts(51)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result[0]) == 50
    # Then 2
    assert result[0][-1][0].name == f"Bulk 0049 {st.TAG}"
    # Then 3
    assert result[1] == 51


# [claude] AIV-AH-30
def test_aiv_ah_30__limit_1000_returns_all_60(db, st):
    """AIV-AH-30 — limit 1000 returns all 60 accounts.
    Rules: list_accounts_hub_page R6"""
    st.hubclean()
    st.accts(60)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result[0]) == 60
    # Then 2
    assert result[1] == 60


# [claude] AIV-AH-31
def test_aiv_ah_31__section_filter_before_paging_and_total(db, st):
    """AIV-AH-31 — the section filter runs before paging and before the total.
    Rules: list_accounts_hub_page R3, R6 (HR-5)"""
    st.hubclean()
    st.acct(f"Bravo {st.TAG}")
    ap = st.acct(f"Charlie {st.TAG}")
    aq = st.acct(f"Delta {st.TAG}")
    ar = st.acct(f"Echo {st.TAG}")
    st.inv(account_id=ap.id)
    st.inv(account_id=aq.id)
    st.inv(account_id=ar.id)

    result = dao.list_accounts_hub_page(
        db, workspace_id=st.W1.id, section="payable", skip=1, limit=1
    )

    # Then 1
    assert hids(result) == [aq.id]
    # Then 2
    assert result[1] == 3


# [claude] AIV-AH-32
def test_aiv_ah_32__writes_nothing(db, st):
    """AIV-AH-32 — writes nothing: a pending account stays pending, an unflushed edit stays unflushed.
    Rules: list_accounts_hub_page R1 (reader)"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ab.name = f"Bravo edited {st.TAG}"
    p = Account(
        workspace_id=st.W1.id,
        name=f"Pending {st.TAG}",
        is_active=True,
        is_deleted=False,
    )
    db.add(p)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id)

    # Then 1
    assert hids(result) == [ab.id]
    # Then 2
    assert p in db.new
    assert len(db.new) == 1
    # Then 3
    assert ab in db.dirty
    assert len(db.dirty) == 1
    # Then 4
    assert not db.deleted
    # Then 5
    assert ab.name == f"Bravo edited {st.TAG}"


# [claude] AIV-AH-33
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_ah_33__due_day_before_today_sets_overdue_either_side(db, st):
    """AIV-AH-33 — the hub: an open invoice due the day before today sets has_overdue, on either side.
    Rules: _open_balance_subquery R2 [BUG-635]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    ac = st.acct(f"Charlie {st.TAG}")
    st.inv(account_id=ab.id, due_date=TDM1)
    st.inv(account_id=ac.id, invoice_type="receivable", due_date=TDM1)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, today=TD)

    # Then 1
    assert pay(result, ab).has_overdue is True
    # Then 2
    assert rec(result, ac).has_overdue is True


# [claude] AIV-AH-34
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_ah_34__due_today_tomorrow_or_undated_never_overdue(db, st):
    """AIV-AH-34 — the hub: due today, due tomorrow or undated never sets has_overdue.
    Rules: _open_balance_subquery R2 [BUG-635]"""
    st.hubclean()
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv(account_id=ab.id, due_date=TD)
    st.inv(account_id=ab.id, due_date=TDP1)
    st.inv(account_id=ab.id)
    st.inv(account_id=ab.id, invoice_type="receivable", due_date=TD)

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, today=TD)

    # Then 1
    assert pay(result, ab).has_overdue is False
    # Then 2
    assert rec(result, ab).has_overdue is False
    # Then 3
    assert pay(result, ab).open_count == 3


# [claude] AIV-AH-35
def test_aiv_ah_35__zero_receivable_balance_not_above_zero(db, st):
    """AIV-AH-35 — a receivable balance of 0.00 is not "> 0", one of 0.01 is.
    Rules: list_accounts_hub_page R3"""
    st.hubclean()
    az = st.acct(f"Zero {st.TAG}")
    ao = st.acct(f"One {st.TAG}")
    st.inv(account_id=az.id, invoice_type="receivable", invoice_amount=Decimal("0.00"))
    st.inv(account_id=ao.id, invoice_type="receivable", invoice_amount=Decimal("0.01"))

    result = dao.list_accounts_hub_page(db, workspace_id=st.W1.id, section="receivable")

    # Then 1
    assert hids(result) == [ao.id]
    # Then 2
    assert result[1] == 1
    # Then 3
    assert rec(result, ao).outstanding_total == Decimal("0.01")


# --------------------------------------------------------------------------- #
# summarize_open_hub_type
# --------------------------------------------------------------------------- #


# [claude] AIV-HS-01
def test_aiv_hs_01__open_count_sum_distinct_accounts(db, st):
    """AIV-HS-01 — open count, exact outstanding sum and distinct accounts of the payables.
    Rules: summarize_open_hub_type R1, R2; _outstanding_amount_expr R1"""
    ai = st.acct(f"Idle {st.TAG}", inactive=True)
    st.inv()
    st.inv(invoice_amount=Decimal("200.20"), partial=Decimal("50.05"))
    st.inv(account_id=ai.id, invoice_amount=Decimal("0.10"))
    st.inv(account_id=ai.id, invoice_amount=Decimal("0.20"))
    st.inv(paid=True)
    st.inv(voided=True)
    st.inv(invoice_type="receivable", invoice_amount=Decimal("999.00"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result[0] == 4
    # Then 2
    assert result[1] == Decimal("250.45")
    # Then 3
    assert result[2] == 0
    # Then 4
    assert result[3] == 2
    # Then 5
    assert isinstance(result[1], Decimal)


# [claude] AIV-HS-02
def test_aiv_hs_02__receivable_type_counts_receivables(db, st):
    """AIV-HS-02 — the receivable type counts receivables only.
    Rules: summarize_open_hub_type R1, R2"""
    st.inv()
    st.inv(invoice_type="receivable", invoice_amount=Decimal("30.00"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="receivable"
    )

    # Then 1
    assert result == (1, Decimal("30.00"), 0, 1)


# [claude] AIV-HS-03
def test_aiv_hs_03__nothing_open_gives_zeros(db, st):
    """AIV-HS-03 — nothing open gives zeros, the total as a Decimal.
    Rules: summarize_open_hub_type R2"""
    st.inv(paid=True)

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (0, Decimal("0"), 0, 0)
    # Then 2
    assert isinstance(result[1], Decimal)
    # Then 3
    assert type(result[0]) is int
    assert type(result[3]) is int


# [claude] AIV-HS-04
def test_aiv_hs_04__unknown_type_gives_zeros(db, st):
    """AIV-HS-04 — an unknown type gives (0, 0, 0, 0).
    Rules: summarize_open_hub_type R4"""
    st.inv()

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="Payable"
    )

    # Then 1
    assert result == (0, 0, 0, 0)


# [claude] AIV-HS-05
def test_aiv_hs_05__closed_and_half_closed_accounts_not_counted(db, st):
    """AIV-HS-05 — invoices of a closed account and of a deleted active account are not counted.
    Rules: summarize_open_hub_type R1"""
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    ah = st.acct(f"Half {st.TAG}", half_closed=True)
    st.inv()
    st.inv(account_id=ax.id)
    st.inv(account_id=ah.id)

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (1, Decimal("100.00"), 0, 1)


# [claude] AIV-HS-06
def test_aiv_hs_06__several_invoices_one_account_count_once(db, st):
    """AIV-HS-06 — several invoices of one account count it once.
    Rules: summarize_open_hub_type R2"""
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv()
    st.inv()
    st.inv()
    st.inv(account_id=ab.id)

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result[0] == 4
    # Then 2
    assert result[3] == 2


# [claude] AIV-HS-07
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_hs_07__draft_not_counted(db, st):
    """AIV-HS-07 — a draft is not counted.
    Rules: summarize_open_hub_type R1 [BUG-634]"""
    st.inv()
    st.inv(draft=True, invoice_amount=Decimal("50.00"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (1, Decimal("100.00"), 0, 1)


# [claude] AIV-HS-08
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_hs_08__overdue_counts_open_due_before_today(db, st):
    """AIV-HS-08 — overdue counts open invoices due before today.
    Rules: summarize_open_hub_type R3 [BUG-635]"""
    st.inv(due_date=PASTDUE)
    st.inv(due_date=FARDUE)
    st.inv()

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable", today=TD
    )

    # Then 1
    assert result[0] == 3
    # Then 2
    assert result[2] == 1


# [claude] AIV-HS-09
def test_aiv_hs_09__w0_w2_not_counted(db, st):
    """AIV-HS-09 — W0's and W2's open invoices are not counted.
    Rules: summarize_open_hub_type R1"""
    st.inv0()
    st.inv(invoice_amount=Decimal("10.00"))
    st.inv2()

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (1, Decimal("10.00"), 0, 1)


# [claude] AIV-HS-10
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_hs_10__invoice_on_w2_account_not_counted(db, st):
    """AIV-HS-10 — a W1 invoice on W2's account is not counted.
    Rules: summarize_open_hub_type R1; _build_filtered_query R2a [BUG-2690]"""
    st.inv(invoice_amount=Decimal("10.00"))
    st.inv(account_id=st.AC2.id, invoice_amount=Decimal("40.00"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (1, Decimal("10.00"), 0, 1)


# [claude] AIV-HS-11
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_hs_11__invoice_on_w0_account_not_counted(db, st):
    """AIV-HS-11 — a W1 invoice on W0's account is not counted.
    Rules: summarize_open_hub_type R1; _build_filtered_query R2a [BUG-2690]"""
    st.inv(invoice_amount=Decimal("10.00"))
    st.inv(account_id=st.AC0.id, invoice_amount=Decimal("40.00"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result == (1, Decimal("10.00"), 0, 1)


# [claude] AIV-HS-12
def test_aiv_hs_12__sum_adds_stored_half_up_amounts(db, st):
    """AIV-HS-12 — the sum adds stored half-up amounts: 33.335 and 0.005 give 33.35.
    Rules: summarize_open_hub_type R2 (HR-15)"""
    st.inv(invoice_amount=Decimal("33.335"))
    st.inv(invoice_amount=Decimal("0.005"))

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable"
    )

    # Then 1
    assert result[1] == Decimal("33.35")


# [claude] AIV-HS-13
def test_aiv_hs_13__kpi_query_no_row_lock(db, st):
    """AIV-HS-13 — the KPI query takes no row lock.
    Rules: summarize_open_hub_type R1"""
    st.inv()
    w1_id = st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.summarize_open_hub_type(
            db, workspace_id=w1_id, invoice_type="payable"
        )
    sqls = rec.sqls("account_invoices")

    # Then 1
    assert result[0] == 1
    # Then 2
    assert all("FOR UPDATE" not in sql for sql in sqls)
    # Then 3
    assert rec.written == []


# [claude] AIV-HS-14
@pytest.mark.xfail(strict=True, reason=R635)
def test_aiv_hs_14__overdue_day_boundary(db, st):
    """AIV-HS-14 — the KPI: overdue day boundary, due the day before today counts, due today or tomorrow does not.
    Rules: summarize_open_hub_type R3 [BUG-635]"""
    st.inv(due_date=TDM1)
    st.inv(due_date=TD)
    st.inv(due_date=TDP1)
    st.inv()
    st.inv(partial=Decimal("10.00"), due_date=TDM1)

    result = dao.summarize_open_hub_type(
        db, workspace_id=st.W1.id, invoice_type="payable", today=TD
    )

    # Then 1
    assert result[0] == 5
    # Then 2
    assert result[2] == 2


# --------------------------------------------------------------------------- #
# count_accounts_with_any_open_balance
# --------------------------------------------------------------------------- #


# [claude] AIV-CA-01
def test_aiv_ca_01__account_open_on_both_types_counts_once(db, st):
    """AIV-CA-01 — an account open on both types counts once.
    Rules: count_accounts_with_any_open_balance R1"""
    ab = st.acct(f"Bravo {st.TAG}")
    st.inv()
    st.inv(invoice_type="receivable")
    st.inv(account_id=ab.id)
    st.inv(account_id=ab.id, partial=Decimal("1.00"))

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 2


# [claude] AIV-CA-02
def test_aiv_ca_02__no_open_invoice_gives_zero_int(db, st):
    """AIV-CA-02 — no open invoice gives 0, an int.
    Rules: count_accounts_with_any_open_balance R1"""
    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


# [claude] AIV-CA-03
def test_aiv_ca_03__inactive_counts_closed_does_not(db, st):
    """AIV-CA-03 — an inactive account counts, a closed one does not.
    Rules: count_accounts_with_any_open_balance R1; _build_filtered_query R2"""
    ai = st.acct(f"Idle {st.TAG}", inactive=True)
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    st.inv(account_id=ai.id)
    st.inv(account_id=ax.id)

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 1


# [claude] AIV-CA-04
def test_aiv_ca_04__only_paid_or_voided_do_not_count(db, st):
    """AIV-CA-04 — accounts with only paid or voided invoices do not count.
    Rules: count_accounts_with_any_open_balance R1"""
    ab = st.acct(f"Bravo {st.TAG}")
    ad = st.acct(f"Delta {st.TAG}")
    st.inv(paid=True)
    st.inv(account_id=ab.id, voided=True)
    st.inv(account_id=ad.id)

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 1


# [claude] AIV-CA-05
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_ca_05__only_draft_does_not_count(db, st):
    """AIV-CA-05 — an account with only a draft does not count.
    Rules: count_accounts_with_any_open_balance R1; _build_filtered_query R12 [BUG-634]"""
    st.inv(draft=True)

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 0


# [claude] AIV-CA-06
def test_aiv_ca_06__other_workspaces_do_not_count(db, st):
    """AIV-CA-06 — W0's and W2's accounts do not count for W1.
    Rules: count_accounts_with_any_open_balance R1"""
    st.inv0()
    st.inv()
    st.inv2()

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 1


# [claude] AIV-CA-07
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_ca_07__invoice_on_w2_account_does_not_count(db, st):
    """AIV-CA-07 — a W1 invoice on W2's account does not make that account count.
    Rules: count_accounts_with_any_open_balance R1; _build_filtered_query R2a [BUG-2690]"""
    st.inv()
    st.inv(account_id=st.AC2.id)

    result = dao.count_accounts_with_any_open_balance(db, workspace_id=st.W1.id)

    # Then 1
    assert result == 1


# --------------------------------------------------------------------------- #
# summarize_invoices
# --------------------------------------------------------------------------- #


# [claude] AIV-SI-01
def test_aiv_si_01__count_all_money_of_non_voided(db, st):
    """AIV-SI-01 — count of all, exact money totals of the non-voided.
    Rules: summarize_invoices R1, R2, R3"""
    st.inv(invoice_amount=Decimal("100.05"))
    st.inv(invoice_amount=Decimal("0.10"), partial=Decimal("0.05"))
    st.inv(invoice_amount=Decimal("0.20"), paid=True)
    st.inv(invoice_amount=Decimal("70.00"), voided=True)

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[0] == 4
    # Then 2
    assert result[1] == Decimal("100.35")
    # Then 3
    assert result[2] == Decimal("0.25")
    # Then 4
    assert result[3] == Decimal("100.10")


# [claude] AIV-SI-02
def test_aiv_si_02__nothing_matching_gives_zeros(db, st):
    """AIV-SI-02 — nothing matching gives a zero count and three Decimal zeros.
    Rules: summarize_invoices R4"""
    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))
    # Then 2
    assert isinstance(result[1], Decimal)
    assert isinstance(result[2], Decimal)
    assert isinstance(result[3], Decimal)


# [claude] AIV-SI-03
def test_aiv_si_03__only_voided_counted_totals_zero(db, st):
    """AIV-SI-03 — only a voided invoice: counted, but every total is zero.
    Rules: summarize_invoices R2, R3, R4"""
    st.inv(voided=True)

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (1, Decimal("0"), Decimal("0"), Decimal("0"))


# [claude] AIV-SI-04
def test_aiv_si_04__overpaid_lowers_outstanding(db, st):
    """AIV-SI-04 — an overpaid invoice lowers the outstanding total.
    Rules: summarize_invoices R3; _outstanding_amount_expr R1"""
    st.inv(
        invoice_amount=Decimal("10.00"),
        paid_amount=Decimal("15.00"),
        payment_status="paid",
    )
    st.inv()

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (2, Decimal("110.00"), Decimal("15.00"), Decimal("95.00"))


# [claude] AIV-SI-05
def test_aiv_si_05__account_id_keeps_one_account(db, st):
    """AIV-SI-05 — account_id keeps one account, with accounts of lower and higher id.
    Rules: summarize_invoices R1"""
    al = st.acct(f"Lima {st.TAG}")
    am = st.acct(f"Mike {st.TAG}")
    an = st.acct(f"Nova {st.TAG}")
    st.inv(account_id=al.id, invoice_amount=Decimal("1.00"))
    st.inv(account_id=am.id, invoice_amount=Decimal("2.00"))
    st.inv(account_id=an.id, invoice_amount=Decimal("4.00"))

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=am.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (1, Decimal("2.00"), Decimal("0.00"), Decimal("2.00"))


# [claude] AIV-SI-06
def test_aiv_si_06__drafts_counted(db, st):
    """AIV-SI-06 — drafts are counted in invoice_count.
    Rules: summarize_invoices R2"""
    st.inv()
    st.inv(draft=True)

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[0] == 2


# [claude] AIV-SI-07
@pytest.mark.xfail(strict=True, reason=R634)
def test_aiv_si_07__drafts_add_nothing_to_money(db, st):
    """AIV-SI-07 — drafts add nothing to the money totals.
    Rules: summarize_invoices R3 [BUG-634]"""
    st.inv()
    st.inv(draft=True, invoice_amount=Decimal("50.00"))

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[1] == Decimal("100.00")
    # Then 3
    assert result[3] == Decimal("100.00")


# [claude] AIV-SI-08
def test_aiv_si_08__w0_w2_not_summed(db, st):
    """AIV-SI-08 — W0's and W2's invoices are not summed.
    Rules: summarize_invoices R1"""
    st.inv0()
    st.inv(invoice_amount=Decimal("10.00"))
    st.inv2()

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, invoice_type="payable")

    # Then 1
    assert result[:4] == (1, Decimal("10.00"), Decimal("0.00"), Decimal("10.00"))


# [claude] AIV-SI-09
@pytest.mark.xfail(strict=True, reason=R2690)
def test_aiv_si_09__invoice_on_w2_account_not_summed(db, st):
    """AIV-SI-09 — a W1 invoice placed on W2's account is not summed for that account.
    Rules: summarize_invoices R1; _build_filtered_query R2a [BUG-2690]"""
    st.inv()
    st.inv(account_id=st.AC2.id)

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC2.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))


# [claude] AIV-SI-10
def test_aiv_si_10__closed_account_not_summed(db, st):
    """AIV-SI-10 — a closed account's invoices are not summed.
    Rules: summarize_invoices R1; _build_filtered_query R2"""
    ax = st.acct(f"Gone {st.TAG}", closed=True)
    st.inv(account_id=ax.id)

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=ax.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))


# [claude] AIV-SI-11
def test_aiv_si_11__number_search_passed_through(db, st):
    """AIV-SI-11 — other filters are passed through: the number search.
    Rules: summarize_invoices R1"""
    st.inv(invoice_number="INV-Alpha-1", invoice_amount=Decimal("11.00"))
    st.inv(invoice_number="INV-Beta-2", invoice_amount=Decimal("22.00"))

    result = dao.summarize_invoices(
        db,
        workspace_id=st.W1.id,
        account_id=st.AC1.id,
        invoice_type="payable",
        invoice_number_search="alpha",
    )

    # Then 1
    assert result[:4] == (1, Decimal("11.00"), Decimal("0.00"), Decimal("11.00"))


# [claude] AIV-SI-12
def test_aiv_si_12__totals_add_stored_half_up_amounts(db, st):
    """AIV-SI-12 — totals add stored half-up amounts: 33.335 and 0.005 give 33.35.
    Rules: summarize_invoices R3 (HR-15)"""
    st.inv(invoice_amount=Decimal("33.335"))
    st.inv(invoice_amount=Decimal("0.005"))

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[1] == Decimal("33.35")
    # Then 2
    assert result[3] == Decimal("33.35")


# [claude] AIV-SI-13
def test_aiv_si_13__summary_query_no_row_lock(db, st):
    """AIV-SI-13 — the summary query takes no row lock.
    Rules: summarize_invoices R1"""
    st.inv()
    w1_id, ac1_id = st.W1.id, st.AC1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.summarize_invoices(
            db, workspace_id=w1_id, account_id=ac1_id, invoice_type="payable"
        )
    sqls = rec.sqls("account_invoices")

    # Then 1
    assert result[0] == 1
    # Then 2
    assert all("FOR UPDATE" not in sql for sql in sqls)
    # Then 3
    assert rec.written == []


# [claude] AIV-SI-14
def test_aiv_si_14__no_type_count_both_types(db, st):
    """AIV-SI-14 — with no type, invoice_count counts payables and receivables together.
    Rules: summarize_invoices R2, R5"""
    st.inv(invoice_amount=Decimal("1000.00"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("200.00"))
    st.inv(invoice_type="receivable", voided=True)

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert result[0] == 3


# [claude] AIV-SI-15
def test_aiv_si_15__receivable_type_counts_receivables(db, st):
    """AIV-SI-15 — with invoice_type "receivable", invoice_count counts the receivables only.
    Rules: summarize_invoices R1, R2"""
    st.inv(invoice_amount=Decimal("1000.00"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("200.00"))

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="receivable"
    )

    # Then 1
    assert result[0] == 1


# --------------------------------------------------------------------------- #
# update_paid_amount
# --------------------------------------------------------------------------- #


# [claude] AIV-UP-01
def test_aiv_up_01__first_payment_added_flushed_partial(db, st):
    """AIV-UP-01 — a first payment is added, the row flushed and marked partial.
    Rules: update_paid_amount R2, R4"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("20.50")
    )

    # Then 1
    assert result.id == n.id
    # Then 2
    assert result.payment_status == "partial"
    # Then 3
    assert db.scalar(
        text("SELECT paid_amount FROM account_invoices WHERE id = :i"), {"i": n.id}
    ) == Decimal("20.50")
    # Then 4
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("20.50")
    assert row.payment_status == "partial"


# [claude] AIV-UP-02
def test_aiv_up_02__payment_adds_to_already_paid(db, st):
    """AIV-UP-02 — a payment adds to what was already paid.
    Rules: update_paid_amount R2, R4"""
    n = st.inv(partial=Decimal("30.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("20.50")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("50.50")
    assert row.payment_status == "partial"


# [claude] AIV-UP-03
def test_aiv_up_03__paying_exactly_rest_marks_paid(db, st):
    """AIV-UP-03 — paying exactly the rest marks the invoice paid.
    Rules: update_paid_amount R3"""
    n = st.inv(partial=Decimal("60.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("40.00")
    )

    # Then 1
    assert result.payment_status == "paid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("100.00")
    assert row.payment_status == "paid"


# [claude] AIV-UP-04
def test_aiv_up_04__one_cent_short_stays_partial(db, st):
    """AIV-UP-04 — one cent short of the amount stays partial.
    Rules: update_paid_amount R3, R4"""
    n = st.inv(partial=Decimal("60.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("39.99")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("99.99")
    assert row.payment_status == "partial"


# [claude] AIV-UP-05
def test_aiv_up_05__paying_more_stored_and_paid(db, st):
    """AIV-UP-05 — paying more than the rest is stored and marks the invoice paid.
    Rules: update_paid_amount R3, R7"""
    n = st.inv(partial=Decimal("60.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("40.01")
    )

    # Then 1
    assert result.payment_status == "paid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("100.01")
    assert row.payment_status == "paid"


# [claude] AIV-UP-06
def test_aiv_up_06__zero_payment_on_zero_invoice_paid(db, st):
    """AIV-UP-06 — a zero payment on a 0.00 invoice marks it paid.
    Rules: update_paid_amount R3"""
    n = st.inv(invoice_amount=Decimal("0.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("0")
    )

    # Then 1
    assert result.payment_status == "paid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "paid"


# [claude] AIV-UP-07
def test_aiv_up_07__zero_payment_on_unpaid_keeps_status(db, st):
    """AIV-UP-07 — a zero payment on an unpaid invoice leaves the status as it was.
    Rules: update_paid_amount R5"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("0")
    )

    # Then 1
    assert result.payment_status == "unpaid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "unpaid"


# [claude] AIV-UP-08
def test_aiv_up_08__negative_to_zero_on_paid_keeps_paid(db, st):
    """AIV-UP-08 — a negative payment back to zero on a paid invoice keeps "paid".
    Rules: update_paid_amount R5"""
    n = st.inv(paid=True)

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("-100")
    )

    # Then 1
    assert result.payment_status == "paid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "paid"


# [claude] AIV-UP-09
def test_aiv_up_09__negative_to_zero_on_partial_keeps_partial(db, st):
    """AIV-UP-09 — a negative payment back to zero on a partial invoice keeps "partial".
    Rules: update_paid_amount R5"""
    n = st.inv(partial=Decimal("30.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("-30.00")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "partial"


# [claude] AIV-UP-10
def test_aiv_up_10__status_on_unrounded_sum(db, st):
    """AIV-UP-10 — the status is decided on the unrounded sum: 999.995 stays partial, stored 1000.00.
    Rules: update_paid_amount R2, R6 (HR-15)"""
    n = st.inv(invoice_amount=Decimal("1000.00"))

    result = dao.update_paid_amount(
        db,
        invoice_id=n.id,
        workspace_id=st.W1.id,
        additional_payment=Decimal("999.995"),
    )

    # Then 1
    assert result.paid_amount == Decimal("999.995")
    # Then 2
    assert result.payment_status == "partial"
    # Then 3
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("1000.00")
    assert row.payment_status == "partial"


# [claude] AIV-UP-11
def test_aiv_up_11__ten_plus_half_cent_stored_10_01(db, st):
    """AIV-UP-11 — 10.00 plus 0.005 is stored as 10.01 (half up, not half to even).
    Rules: update_paid_amount R2 (HR-15)"""
    n = st.inv(partial=Decimal("10.00"))

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("0.005")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    assert st.reread(n.id).paid_amount == Decimal("10.01")


# [claude] AIV-UP-12
def test_aiv_up_12__2_125_stored_2_13(db, st):
    """AIV-UP-12 — 2.125 is stored as 2.13 (half up, not half to even).
    Rules: update_paid_amount R2 (HR-15)"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("2.125")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    assert st.reread(n.id).paid_amount == Decimal("2.13")


# [claude] AIV-UP-13
def test_aiv_up_13__2_124_stored_2_12(db, st):
    """AIV-UP-13 — 2.124 is stored as 2.12 (the control).
    Rules: update_paid_amount R2 (HR-15)"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("2.124")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    assert st.reread(n.id).paid_amount == Decimal("2.12")


# [claude] AIV-UP-14
def test_aiv_up_14__minus_1_005_stored_minus_1_01(db, st):
    """AIV-UP-14 — -1.005 is stored as -1.01 (half away from zero), the status kept.
    Rules: update_paid_amount R2, R5 (HR-15)"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("-1.005")
    )

    # Then 1
    assert result.payment_status == "unpaid"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("-1.01")
    assert row.payment_status == "unpaid"


# [claude] AIV-UP-15
def test_aiv_up_15__unknown_id_none_writes_nothing(db, st):
    """AIV-UP-15 — an unknown id returns None and writes nothing.
    Rules: update_paid_amount R1"""
    n = st.inv()
    before = st.snap(n.id)

    result = dao.update_paid_amount(
        db,
        invoice_id=MISSING,
        workspace_id=st.W1.id,
        additional_payment=Decimal("10.00"),
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    assert not db.new
    # Then 3
    assert st.snap(n.id) == before


# [claude] AIV-UP-16
def test_aiv_up_16__w0_invoice_from_w1_none(db, st):
    """AIV-UP-16 — W0's invoice asked from W1 returns None and is not touched.
    Rules: update_paid_amount R1"""
    x0 = st.inv0()
    st.inv()
    st.inv2()

    result = dao.update_paid_amount(
        db, invoice_id=x0.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    row = st.reread(x0.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "unpaid"


# [claude] AIV-UP-17
def test_aiv_up_17__w2_invoice_from_w1_none(db, st):
    """AIV-UP-17 — W2's invoice asked from W1 returns None and is not touched.
    Rules: update_paid_amount R1"""
    st.inv0()
    st.inv()
    x2 = st.inv2()

    result = dao.update_paid_amount(
        db, invoice_id=x2.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    row = st.reread(x2.id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "unpaid"


# [claude] AIV-UP-18
def test_aiv_up_18__only_named_invoice_changes(db, st):
    """AIV-UP-18 — only the named invoice changes, not its neighbours of lower and higher id.
    Rules: update_paid_amount R2, R8"""
    n1 = st.inv()
    n2 = st.inv()
    n3 = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n2.id, workspace_id=st.W1.id, additional_payment=Decimal("5.00")
    )

    # Then 1
    assert result.id == n2.id
    # Then 2
    row1 = st.reread(n1.id)
    assert row1.paid_amount == Decimal("0.00")
    assert row1.payment_status == "unpaid"
    # Then 3
    row3 = st.reread(n3.id)
    assert row3.paid_amount == Decimal("0.00")
    assert row3.payment_status == "unpaid"
    # Then 4
    assert st.reread(n2.id).paid_amount == Decimal("5.00")


# [claude] AIV-UP-19
def test_aiv_up_19__voided_invoice_updated_too(db, st):
    """AIV-UP-19 — a voided invoice is updated too.
    Rules: update_paid_amount R7"""
    n = st.inv(voided=True)

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("10.00")
    assert row.payment_status == "partial"
    assert row.invoice_status == "voided"


# [claude] AIV-UP-20
def test_aiv_up_20__allow_payments_false_not_looked_at(db, st):
    """AIV-UP-20 — allow_payments False is not looked at.
    Rules: update_paid_amount R7"""
    n = st.inv(allow_payments=False, payment_locked_reason="Disputed")

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("10.00")
    assert row.allow_payments is False


# [claude] AIV-UP-21
def test_aiv_up_21__no_other_field_written(db, st):
    """AIV-UP-21 — no other field is written: updated_by, amount, status, notes stay.
    Rules: update_paid_amount R8"""
    n = st.inv(updated_by=st.U2.id, notes="keep", invoice_number="INV-7")
    u2_id = st.U2.id

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result.id == n.id
    # Then 2
    row = st.reread(n.id)
    assert row.updated_by == u2_id
    assert row.notes == "keep"
    assert row.invoice_number == "INV-7"
    # Then 3
    assert row.invoice_amount == Decimal("100.00")
    assert row.invoice_status == "confirmed"
    assert row.invoice_type == "payable"
    # Then 4
    assert row.updated_at is not None


# [claude] AIV-UP-22
def test_aiv_up_22__one_update_no_row_lock(db, st):
    """AIV-UP-22 — one UPDATE of the invoice and no row lock of its own.
    Rules: update_paid_amount R7"""
    n = st.inv()
    n_id, w1_id = n.id, st.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.update_paid_amount(
            db, invoice_id=n_id, workspace_id=w1_id, additional_payment=Decimal("10.00")
        )
    sql = rec.sql("account_invoices")

    # Then 1
    assert result.id == n_id
    # Then 2
    assert "FOR UPDATE" not in sql
    # Then 3
    assert len(rec.written) == 1
    # Then 4
    assert rec.written[0].startswith("UPDATE account_invoices")


# [claude] AIV-UP-23
def test_aiv_up_23__callers_locked_row_updated_and_returned(db, st):
    """AIV-UP-23 — the caller's locked row is the one updated and returned.
    Rules: update_paid_amount R7"""
    n = st.inv()
    locked = db.execute(
        select(AccountInvoice).where(AccountInvoice.id == n.id).with_for_update()
    ).scalar_one()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("10.00")
    )

    # Then 1
    assert result is locked
    # Then 2
    assert st.reread(n.id).paid_amount == Decimal("10.00")


# [claude] AIV-UP-24
def test_aiv_up_24__positional_arguments_raise_type_error(db, st):
    """AIV-UP-24 — positional arguments raise TypeError, nothing written.
    Rules: update_paid_amount R8"""
    n = st.inv()

    # Then 1
    with pytest.raises(TypeError):
        dao.update_paid_amount(db, n.id, st.W1.id, Decimal("10.00"))
    # Then 2
    assert not db.dirty
    # Then 3
    assert st.reread(n.id).paid_amount == Decimal("0.00")


# [claude] AIV-UP-25
def test_aiv_up_25__flushes_but_never_commits(db, st):
    """AIV-UP-25 — flushes but never commits.
    Rules: update_paid_amount R2 (Overview: never commits)"""
    n = st.inv()
    n_id, w1_id = n.id, st.W1.id

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.update_paid_amount(
            db, invoice_id=n_id, workspace_id=w1_id, additional_payment=Decimal("10.00")
        )

    # Then 1
    assert result.payment_status == "partial"
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    row = st.reread(n_id)
    assert row.paid_amount == Decimal("0.00")
    assert row.payment_status == "unpaid"


# [claude] AIV-UP-26
def test_aiv_up_26__one_cent_payment_on_unpaid_marks_partial(db, st):
    """AIV-UP-26 — a 0.01 payment on an unpaid invoice marks it partial.
    Rules: update_paid_amount R2, R4"""
    n = st.inv()

    result = dao.update_paid_amount(
        db, invoice_id=n.id, workspace_id=st.W1.id, additional_payment=Decimal("0.01")
    )

    # Then 1
    assert result.id == n.id
    # Then 2
    assert result.payment_status == "partial"
    # Then 3
    row = st.reread(n.id)
    assert row.paid_amount == Decimal("0.01")
    assert row.payment_status == "partial"


# --------------------------------------------------------------------------- #
# summarize_invoices R5 — split by invoice type (BUG-2692)
# --------------------------------------------------------------------------- #


# [claude] AIV-OQ41-01
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_01__no_type_two_separate_triples(db, st):
    """AIV-OQ41-01 — with no type, a 1,000.00 payable and a 200.00 receivable are two separate triples.
    Rules: summarize_invoices R5 [BUG-2692]"""
    st.inv(invoice_amount=Decimal("1000.00"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("200.00"))

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert len(result) == 7
    # Then 3
    assert result[1:4] == (Decimal("1000.00"), Decimal("0.00"), Decimal("1000.00"))
    # Then 4
    assert result[4:7] == (Decimal("200.00"), Decimal("0.00"), Decimal("200.00"))


# [claude] AIV-OQ41-02
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_02__no_type_paid_stays_on_own_side(db, st):
    """AIV-OQ41-02 — with no type, paid amounts stay on their own side too.
    Rules: summarize_invoices R5 [BUG-2692]"""
    st.inv(invoice_amount=Decimal("1000.00"), partial=Decimal("400.00"))
    st.inv(
        invoice_type="receivable",
        invoice_amount=Decimal("200.00"),
        partial=Decimal("50.00"),
    )

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert result[0] == 2
    # Then 2
    assert len(result) == 7
    # Then 3
    assert result[1:4] == (Decimal("1000.00"), Decimal("400.00"), Decimal("600.00"))
    # Then 4
    assert result[4:7] == (Decimal("200.00"), Decimal("50.00"), Decimal("150.00"))


# [claude] AIV-OQ41-03
def test_aiv_oq41_03__payable_type_first_four_values(db, st):
    """AIV-OQ41-03 — with invoice_type "payable", the count and the payable triple are the first four values.
    Rules: summarize_invoices R5 [BUG-2692] (the part that holds before and after the fix)"""
    st.inv(invoice_amount=Decimal("1000.00"), partial=Decimal("400.00"))
    st.inv(
        invoice_type="receivable",
        invoice_amount=Decimal("200.00"),
        partial=Decimal("50.00"),
    )

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (1, Decimal("1000.00"), Decimal("400.00"), Decimal("600.00"))


# [claude] AIV-OQ41-04
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_04__receivable_type_payable_triple_zero(db, st):
    """AIV-OQ41-04 — with invoice_type "receivable", the payable triple is zero and the receivable triple holds the sums.
    Rules: summarize_invoices R4, R5 [BUG-2692]"""
    st.inv(invoice_amount=Decimal("1000.00"), partial=Decimal("400.00"))
    st.inv(
        invoice_type="receivable",
        invoice_amount=Decimal("200.00"),
        partial=Decimal("50.00"),
    )

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="receivable"
    )

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1:4] == (Decimal("0"), Decimal("0"), Decimal("0"))
    # Then 3
    assert result[4:7] == (Decimal("200.00"), Decimal("50.00"), Decimal("150.00"))


# [claude] AIV-OQ41-05
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_05__payable_type_receivable_triple_zeros(db, st):
    """AIV-OQ41-05 — with invoice_type "payable", the receivable triple is three Decimal zeros.
    Rules: summarize_invoices R4, R5 [BUG-2692]"""
    st.inv(invoice_amount=Decimal("1000.00"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("200.00"))

    result = dao.summarize_invoices(
        db, workspace_id=st.W1.id, account_id=st.AC1.id, invoice_type="payable"
    )

    # Then 1
    assert result[:4] == (1, Decimal("1000.00"), Decimal("0.00"), Decimal("1000.00"))
    # Then 2
    assert result[4:7] == (Decimal("0"), Decimal("0"), Decimal("0"))
    # Then 3
    assert isinstance(result[4], Decimal)


# [claude] AIV-OQ41-06
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_06__each_triple_exact_half_up_sum(db, st):
    """AIV-OQ41-06 — each triple is an exact Decimal sum of stored half-up amounts.
    Rules: summarize_invoices R3, R5 [BUG-2692] (HR-15)"""
    st.inv(invoice_amount=Decimal("0.10"), partial=Decimal("0.05"))
    st.inv(invoice_amount=Decimal("0.20"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("33.335"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("0.005"))

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert result[0] == 4
    # Then 2
    assert len(result) == 7
    # Then 3
    assert result[1:4] == (Decimal("0.30"), Decimal("0.05"), Decimal("0.25"))
    # Then 4
    assert result[4:7] == (Decimal("33.35"), Decimal("0.00"), Decimal("33.35"))


# [claude] AIV-OQ41-07
@pytest.mark.xfail(strict=True, reason=R2692)
def test_aiv_oq41_07__voided_counted_add_nothing_to_triple(db, st):
    """AIV-OQ41-07 — voided invoices of either type are counted but add nothing to their own triple.
    Rules: summarize_invoices R2, R3, R5 [BUG-2692]"""
    st.inv()
    st.inv(invoice_amount=Decimal("70.00"), voided=True)
    st.inv(invoice_type="receivable", invoice_amount=Decimal("40.00"))
    st.inv(invoice_type="receivable", invoice_amount=Decimal("25.00"), voided=True)

    result = dao.summarize_invoices(db, workspace_id=st.W1.id, account_id=st.AC1.id)

    # Then 1
    assert result[0] == 4
    # Then 2
    assert len(result) == 7
    # Then 3
    assert result[1:4] == (Decimal("100.00"), Decimal("0.00"), Decimal("100.00"))
    # Then 4
    assert result[4:7] == (Decimal("40.00"), Decimal("0.00"), Decimal("40.00"))
