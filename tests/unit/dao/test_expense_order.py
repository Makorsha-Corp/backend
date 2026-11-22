"""Unit tests for app/dao/expense_order.py.

Implements tests/unit/dao/expense_order.cases.md (revision 3), one test per case,
in card order. Real Postgres session (`db` fixture).

Patched (Conventions, Externals): clockN(L, U) in the `NX` cards patches
`datetime.datetime` (the function imports it at call time) and
`app.dao.expense_order.utcnow`; clockD(U) in the `SA`, `UP`, `DW`, `OQ43` and
`OQ44` cards patches `app.dao.expense_order.utcnow`. Nothing else is mocked. No
race simulations.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`, naive datetimes for the clock values, and the Decimal strings as carded)
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from app.dao.expense_order import (
    _category_label,
    _due_date_bucket,
    _due_window_dates,
    _expense_order_stage_key_expr,
    expense_order_dao,
    expense_order_item_dao,
)
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_item import ExpenseOrderItem
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao"
dao = expense_order_dao
idao = expense_order_item_dao

# Convention "MISSING"
MISSING = 999999999

# Convention "D1, D2, D3"
D1 = date(2031, 3, 1)
D2 = date(2031, 3, 10)
D3 = date(2031, 3, 20)

# Convention "T1 ... T5" (naive)
T1 = datetime(2031, 3, 4, 9, 0)
T2 = datetime(2031, 3, 4, 10, 0)
T3 = datetime(2031, 3, 4, 11, 0)
T4 = datetime(2031, 3, 4, 12, 0)
T5 = datetime(2031, 3, 4, 13, 0)

# Convention "TODAY, EOW, EOM, NOWX"
TODAY = date(2031, 11, 11)
EOW = date(2031, 11, 16)
EOM = date(2031, 11, 30)
NOWX = datetime(2031, 11, 11, 12, 0)

# Convention "An NX card without a clock line runs under clockN(JUNE, JUNE)"
JUNE = datetime(2031, 6, 1, 12, 0)


# Convention "GN(n)" (per-process suffix: expense numbers are globally unique, BUG-749)
def GN(n):
    return f"{n}-{os.getpid()}"


# --------------------------------------------------------------------------- #
# Conventions -> externals
# --------------------------------------------------------------------------- #


# Convention "clockN(L, U)"
@contextmanager
def clockN(local, utc):
    class _Fake(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return local

    with patch("datetime.datetime", _Fake):
        with patch("app.dao.expense_order.utcnow", return_value=utc):
            yield


# Convention "clockD(U)"
@contextmanager
def clockD(utc=NOWX):
    with patch("app.dao.expense_order.utcnow", return_value=utc):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def g(db):
    """Standing rows: W0, W1, W2, U1, U2, U3; accounts A0 (W0), K1, K2, K3 (W1), A2 (W2)."""
    n = SimpleNamespace()
    n.W0, n.W1, n.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    n.U1, n.U2, n.U3 = make_profile(db), make_profile(db), make_profile(db)
    n.A0 = _add(db, Account(workspace_id=n.W0.id, name="Foreign Co"))
    n.K1 = _add(db, Account(workspace_id=n.W1.id, name="Alder Supplies"))
    n.K2 = _add(db, Account(workspace_id=n.W1.id, name="Birch Traders"))
    n.K3 = _add(db, Account(workspace_id=n.W1.id, name="Cedar Hub"))
    n.A2 = _add(db, Account(workspace_id=n.W2.id, name="Overseas Ltd"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given-row builders
# --------------------------------------------------------------------------- #


def _order_row(g, k, number, completed, voided, columns):
    fields = {
        "workspace_id": getattr(g, f"W{k}").id,
        "expense_number": number,
        "expense_category": "factory",
        "expense_date": D2,
        "subtotal": Decimal("0.00"),
        "total_amount": Decimal("10.00"),
        "created_by": g.U1.id,
    }
    if completed:  # Convention "completed"
        fields.update(
            approved_at=T2, approved_by=g.U1.id, completed_at=T3, completed_by=g.U1.id
        )
    if voided:  # Convention "voided"
        fields.update(
            voided=True, voided_at=T4, voided_by=g.U1.id, void_note="duplicate"
        )
    fields.update(columns)
    return ExpenseOrder(**fields)


@pytest.fixture
def row(g):
    """Convention "order N", not added: row(N, k=1, completed=False, voided=False, **but)."""

    def _mk(name, k=1, completed=False, voided=False, **columns):
        return _order_row(g, k, GN(name), completed, voided, columns)

    return _mk


@pytest.fixture
def order(db, g):
    """Convention "order N" (stores GN(N)), flushed. k=0 / 2 = "of W0" / "of W2"."""

    def _mk(name, k=1, completed=False, voided=False, **columns):
        return _add(db, _order_row(g, k, GN(name), completed, voided, columns))

    return _mk


@pytest.fixture
def numbered(db, g):
    """Convention "numbered N" (stores N exactly), flushed."""

    def _mk(name, k=1, completed=False, voided=False, **columns):
        return _add(db, _order_row(g, k, name, completed, voided, columns))

    return _mk


@pytest.fixture
def inv(db, g):
    """Convention "inv(W, amount)"; state = None (draft), "confirmed", "locked" or "invvoid"."""
    accounts = {0: "A0", 1: "K1", 2: "A2"}

    def _mk(k, amount, state=None, **columns):
        fields = {
            "workspace_id": getattr(g, f"W{k}").id,
            "account_id": getattr(g, accounts[k]).id,
            "invoice_type": "payable",
            "invoice_amount": Decimal(amount),
            "invoice_date": D1,
        }
        if state in ("confirmed", "locked"):
            fields["invoice_status"] = state
        elif state == "invvoid":
            fields.update(
                invoice_status="voided",
                void_note="duplicate",
                paid_amount=Decimal("0.00"),
                payment_status="unpaid",
            )
        fields.update(columns)
        return _add(db, AccountInvoice(**fields))

    return _mk


@pytest.fixture
def deleted_account(db, g):
    """Convention "deleted account N" (every column a real soft delete writes)."""

    def _mk(name):
        return _add(
            db,
            Account(
                workspace_id=g.W1.id,
                name=name,
                is_deleted=True,
                is_active=False,
                deleted_at=T4,
                deleted_by=g.U1.id,
            ),
        )

    return _mk


@pytest.fixture
def line(db, g):
    """Convention "line(O, n)", flushed; `columns` are the "but" columns."""

    def _mk(o, n, **columns):
        fields = {
            "workspace_id": g.W1.id,
            "expense_order_id": o.id,
            "line_number": n,
            "quantity": Decimal("1.00"),
            "description": f"Line {n}",
        }
        fields.update(columns)
        return _add(db, ExpenseOrderItem(**fields))

    return _mk


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "Dhaka"
def dhaka(db):
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# Convention "HIGH_ID(table)"
def high_id(db, table):
    return db.execute(
        text(
            f"SELECT GREATEST((SELECT COALESCE(MAX(id), 0) FROM {table}), "
            f"(SELECT last_value FROM {table}_id_seq)) + 1000001"
        )
    ).scalar_one()


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #


# Convention "ids(result)"
def ids(result):
    return [r.id for r in result]


# Convention "idset(result)"
def idset(result):
    return {r.id for r in result}


# Convention "bucket(result, part, key)"
def bucket(result, part, key):
    [found] = [b for b in result[part] if b["key"] == key]
    return found


# Convention "Statement recorder"
class StatementRecorder:
    def __init__(self, db, table="expense_orders"):
        self.bind = db.get_bind()
        self.table = table
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
        """The one SELECT from the table; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects if self.table in s]
        return statement

    @property
    def order_part(self):
        return order_part_of(self.sql)


def order_part_of(sql):
    """Text after the first ORDER BY, before any LIMIT ("" if none)."""
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


# Convention "Z3": the stage pipeline with nothing in it
Z3 = [
    {"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")},
    {"key": "invoiced", "label": "Invoiced", "count": 0, "total_value": Decimal("0")},
    {"key": "complete", "label": "Complete", "count": 0, "total_value": Decimal("0")},
]


# --------------------------------------------------------------------------- #
# _expense_order_stage_key_expr
# --------------------------------------------------------------------------- #


# [claude] EXO-SK-01
def test_exo_sk_01__complete_wins_then_invoiced_else_draft(db, g, order, inv):
    """EXO-SK-01 — complete wins over invoice; invoiced without completion; else draft.
    Rules: `_expense_order_stage_key_expr` R1"""
    v1 = inv(1, "50.00")
    oa = order("EXP-T-001", completed=True)
    ob = order("EXP-T-002", completed=True, invoice_id=v1.id)
    oc = order("EXP-T-003", invoice_id=v1.id)
    od = order("EXP-T-004")

    result = dict(
        db.execute(
            select(ExpenseOrder.id, _expense_order_stage_key_expr()).where(
                ExpenseOrder.workspace_id == g.W1.id
            )
        ).all()
    )

    # Then 1
    assert result[oa.id] == "complete"
    # Then 2
    assert result[ob.id] == "complete"
    # Then 3
    assert result[oc.id] == "invoiced"
    # Then 4
    assert result[od.id] == "draft"


# [claude] EXO-SK-02
def test_exo_sk_02__voiding_does_not_change_stage(db, g, order, inv):
    """EXO-SK-02 — voiding does not change the stage.
    Rules: `_expense_order_stage_key_expr` R1"""
    v1 = inv(1, "50.00")
    oa = order("EXP-T-001", completed=True, voided=True)
    ob = order("EXP-T-002", voided=True, invoice_id=v1.id)
    oc = order("EXP-T-003", voided=True)

    result = dict(
        db.execute(
            select(ExpenseOrder.id, _expense_order_stage_key_expr()).where(
                ExpenseOrder.workspace_id == g.W1.id
            )
        ).all()
    )

    # Then 1
    assert result[oa.id] == "complete"
    # Then 2
    assert result[ob.id] == "invoiced"
    # Then 3
    assert result[oc.id] == "draft"


# --------------------------------------------------------------------------- #
# _category_label
# --------------------------------------------------------------------------- #


# [claude] EXO-CL-01 … CL-08
@pytest.mark.parametrize(
    ("slug", "label"),
    [
        pytest.param("factory", "Factory", id="EXO-CL-01"),
        pytest.param("department", "Department", id="EXO-CL-02"),
        pytest.param("other", "Other", id="EXO-CL-03"),
        pytest.param("office_rent", "Office Rent", id="EXO-CL-04"),
        pytest.param("utilities", "Utilities", id="EXO-CL-05"),
        pytest.param("", "", id="EXO-CL-06"),
        pytest.param("FACTORY", "Factory", id="EXO-CL-07"),
        pytest.param("oFFICE_rENT", "Office Rent", id="EXO-CL-08"),
    ],
)
def test_exo_cl_01_08__category_label(g, slug, label):
    """EXO-CL-01 … CL-08 — the three known slugs keep their label; other slugs have "_" replaced and are title-cased.
    Rules: `_category_label` R1, R2"""
    result = _category_label(slug)

    # Then 1
    assert result == label


# [claude] EXO-CL-09
def test_exo_cl_09__non_string_raises_attribute_error(g):
    """EXO-CL-09 — a non-string raises AttributeError.
    Rules: `_category_label` Errors"""
    # Then 1
    with pytest.raises(AttributeError) as exc:
        _category_label(None)
    assert isinstance(exc.value, AttributeError)


# --------------------------------------------------------------------------- #
# _due_date_bucket
# --------------------------------------------------------------------------- #


# [claude] EXO-DB-01 … DB-07
@pytest.mark.parametrize(
    ("due", "expected"),
    [
        pytest.param(None, "no_due_date", id="EXO-DB-01"),
        pytest.param(date(2031, 11, 10), "overdue", id="EXO-DB-02"),
        pytest.param(TODAY, "due_this_week", id="EXO-DB-03"),
        pytest.param(EOW, "due_this_week", id="EXO-DB-04"),
        pytest.param(date(2031, 11, 17), "due_later_this_month", id="EXO-DB-05"),
        pytest.param(EOM, "due_later_this_month", id="EXO-DB-06"),
        pytest.param(date(2031, 12, 1), "beyond_scope", id="EXO-DB-07"),
    ],
)
def test_exo_db_01_07__due_date_bucket(g, due, expected):
    """EXO-DB-01 … DB-07 — every bucket edge on both sides with TODAY / EOW / EOM.
    Rules: `_due_date_bucket` R1–R5"""
    result = _due_date_bucket(due, today=TODAY, end_of_week=EOW, end_of_month=EOM)

    # Then 1
    assert result == expected


# [claude] EXO-DB-08
def test_exo_db_08__week_ending_next_month(g):
    """EXO-DB-08 — a week ending in the next month puts that month's first days in due this week.
    Rules: `_due_date_bucket` R5"""
    result = _due_date_bucket(
        date(2031, 8, 2),
        today=date(2031, 7, 31),
        end_of_week=date(2031, 8, 3),
        end_of_month=date(2031, 7, 31),
    )

    # Then 1
    assert result == "due_this_week"


# [claude] EXO-DB-09
def test_exo_db_09__positional_window_dates_raise_type_error(g):
    """EXO-DB-09 — positional window dates raise TypeError.
    Rules: `_due_date_bucket` R6"""
    # Then 1
    with pytest.raises(TypeError) as exc:
        _due_date_bucket(TODAY, TODAY, EOW, EOM)
    assert isinstance(exc.value, TypeError)


# --------------------------------------------------------------------------- #
# _due_window_dates
# --------------------------------------------------------------------------- #


# [claude] EXO-DW-01
def test_exo_dw_01__tuesday(g):
    """EXO-DW-01 — a Tuesday gives today, the coming Sunday and the month's last day.
    Rules: `_due_window_dates` R1, R2, R3, R4"""
    with clockD(datetime(2031, 11, 11, 12, 0)):
        result = _due_window_dates()

    # Then 1
    assert result == (date(2031, 11, 11), date(2031, 11, 16), date(2031, 11, 30))
    # Then 2
    assert type(result[0]) is date


# [claude] EXO-DW-02 … DW-06
@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param(
            datetime(2031, 11, 16, 8, 0),
            (date(2031, 11, 16), date(2031, 11, 16), date(2031, 11, 30)),
            id="EXO-DW-02",
        ),
        pytest.param(
            datetime(2031, 11, 10, 8, 0),
            (date(2031, 11, 10), date(2031, 11, 16), date(2031, 11, 30)),
            id="EXO-DW-03",
        ),
        pytest.param(
            datetime(2032, 2, 10, 12, 0),
            (date(2032, 2, 10), date(2032, 2, 15), date(2032, 2, 29)),
            id="EXO-DW-04",
        ),
        pytest.param(
            datetime(2031, 2, 10, 12, 0),
            (date(2031, 2, 10), date(2031, 2, 16), date(2031, 2, 28)),
            id="EXO-DW-05",
        ),
        pytest.param(
            datetime(2031, 7, 31, 12, 0),
            (date(2031, 7, 31), date(2031, 8, 3), date(2031, 7, 31)),
            id="EXO-DW-06",
        ),
    ],
)
def test_exo_dw_02_06__due_window_dates(g, now, expected):
    """EXO-DW-02 … DW-06 — Sunday, Monday, leap and common February, a week running into the next month.
    Rules: `_due_window_dates` R2, R3"""
    with clockD(now):
        result = _due_window_dates()

    # Then 1
    assert result == expected


# [claude] EXO-DW-07
def test_exo_dw_07__utc_date_late_on_new_years_eve(db, g):
    """EXO-DW-07 — today is the UTC date, also late in the UTC evening of New Year's Eve.
    Rules: `_due_window_dates` R1"""
    dhaka(db)
    with clockD(datetime(2031, 12, 31, 23, 30)):
        result = _due_window_dates()

    # Then 1
    assert result == (date(2031, 12, 31), date(2032, 1, 4), date(2031, 12, 31))


# --------------------------------------------------------------------------- #
# _apply_expense_order_hub_filters (through list_for_hub)
# --------------------------------------------------------------------------- #


# [claude] EXO-HF-01
def test_exo_hf_01__only_w1_orders(db, g, order):
    """EXO-HF-01 — only W1's orders, with orders of W0 and W2 on both sides.
    Rules: `_apply_expense_order_hub_filters` R1"""
    order("EXP-T-900", k=0)
    o1 = order("EXP-T-001")
    o2 = order("EXP-T-002")
    order("EXP-T-902", k=2)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert idset(result) == {o1.id, o2.id}


# [claude] EXO-HF-02
def test_exo_hf_02__asked_for_w0(db, g, order):
    """EXO-HF-02 — asked for W0, only W0's order, though W1 and W2 orders come later.
    Rules: `_apply_expense_order_hub_filters` R1"""
    x0 = order("EXP-T-900", k=0)
    order("EXP-T-001")
    order("EXP-T-902", k=2)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W0.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert idset(result) == {x0.id}


# [claude] EXO-HF-03
def test_exo_hf_03__asked_for_w2(db, g, order):
    """EXO-HF-03 — asked for W2, only W2's order, though W0 and W1 orders come earlier.
    Rules: `_apply_expense_order_hub_filters` R1"""
    order("EXP-T-900", k=0)
    order("EXP-T-001")
    x2 = order("EXP-T-902", k=2)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W2.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert idset(result) == {x2.id}


# [claude] EXO-HF-04
def test_exo_hf_04__category_exact_match(db, g, order):
    """EXO-HF-04 — expense_category is an exact match.
    Rules: `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-001")
    ob = order("EXP-T-002", expense_category="department")
    order("EXP-T-003", expense_category="other")
    order("EXP-T-902", k=2, expense_category="department")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="department",
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-05
def test_exo_hf_05__category_case_sensitive(db, g, order):
    """EXO-HF-05 — expense_category is case-sensitive: "Department" keeps nothing.
    Rules: `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-001")
    order("EXP-T-002", expense_category="department")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="Department",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-06
def test_exo_hf_06__category_no_partial_match(db, g, order):
    """EXO-HF-06 — expense_category does not match a part of the value.
    Rules: `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-002", expense_category="department")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="depart",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-07
def test_exo_hf_07__category_leading_space(db, g, order):
    """EXO-HF-07 — expense_category with a leading space keeps nothing.
    Rules: `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-001")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category=" factory",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-08
def test_exo_hf_08__category_underscore_not_wildcard(db, g, order):
    """EXO-HF-08 — expense_category "_" is not a wildcard.
    Rules: `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-001", expense_category="office-rent")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="office_rent",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-09
def test_exo_hf_09__empty_category_no_filter(db, g, order):
    """EXO-HF-09 — expense_category "" applies no filter.
    Rules: `_apply_expense_order_hub_filters` R2"""
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", expense_category="department")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="",
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-HF-10
def test_exo_hf_10__account_id_middle_account(db, g, order):
    """EXO-HF-10 — account_id keeps the middle account's orders only.
    Rules: `_apply_expense_order_hub_filters` R3"""
    order("EXP-T-001", account_id=g.K1.id)
    ob = order("EXP-T-002", account_id=g.K2.id)
    order("EXP-T-003", account_id=g.K3.id)
    order("EXP-T-004")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        account_id=g.K2.id,
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-11
def test_exo_hf_11__account_id_zero_keeps_nothing(db, g, order):
    """EXO-HF-11 — account_id 0 keeps nothing.
    Rules: `_apply_expense_order_hub_filters` R3"""
    order("EXP-T-001", account_id=g.K1.id)
    order("EXP-T-004")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        account_id=0,
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-12
def test_exo_hf_12__invoice_id_middle_invoice(db, g, order, inv):
    """EXO-HF-12 — invoice_id keeps the middle invoice's order only.
    Rules: `_apply_expense_order_hub_filters` R4"""
    v1 = inv(1, "10.00")
    v2 = inv(1, "20.00")
    v3 = inv(1, "30.00")
    order("EXP-T-001", invoice_id=v1.id)
    ob = order("EXP-T-002", invoice_id=v2.id)
    order("EXP-T-003", invoice_id=v3.id)
    order("EXP-T-004")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        invoice_id=v2.id,
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-13
def test_exo_hf_13__date_from_inclusive(db, g, order):
    """EXO-HF-13 — date_from includes its own day and later days.
    Rules: `_apply_expense_order_hub_filters` R5"""
    order("EXP-T-001", expense_date=date(2031, 3, 9))
    ob = order("EXP-T-002", expense_date=date(2031, 3, 10))
    oc = order("EXP-T-003", expense_date=date(2031, 3, 11))

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        date_from=date(2031, 3, 10),
    )

    # Then 1
    assert idset(result) == {ob.id, oc.id}


# [claude] EXO-HF-14
def test_exo_hf_14__date_to_inclusive(db, g, order):
    """EXO-HF-14 — date_to includes its own day and earlier days.
    Rules: `_apply_expense_order_hub_filters` R5"""
    oa = order("EXP-T-001", expense_date=date(2031, 3, 9))
    ob = order("EXP-T-002", expense_date=date(2031, 3, 10))
    order("EXP-T-003", expense_date=date(2031, 3, 11))

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        date_to=date(2031, 3, 10),
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


@pytest.fixture
def four_stages(order, inv):
    """The Given of EXO-HF-15 … HF-17: V1; OA draft, OB invoiced, OC completed, OD completed + invoiced."""
    v1 = inv(1, "10.00")
    return SimpleNamespace(
        OA=order("EXP-T-001"),
        OB=order("EXP-T-002", invoice_id=v1.id),
        OC=order("EXP-T-003", completed=True),
        OD=order("EXP-T-004", completed=True, invoice_id=v1.id),
    )


# [claude] EXO-HF-15
def test_exo_hf_15__stage_1_draft(db, g, four_stages):
    """EXO-HF-15 — stage 1 keeps orders neither completed nor invoiced.
    Rules: `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1"""
    s = four_stages

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[1],
    )

    # Then 1
    assert idset(result) == {s.OA.id}


# [claude] EXO-HF-16
def test_exo_hf_16__stage_2_invoiced(db, g, four_stages):
    """EXO-HF-16 — stage 2 keeps invoiced orders that are not completed.
    Rules: `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1"""
    s = four_stages

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[2],
    )

    # Then 1
    assert idset(result) == {s.OB.id}


# [claude] EXO-HF-17
def test_exo_hf_17__stage_3_complete(db, g, four_stages):
    """EXO-HF-17 — stage 3 keeps completed orders, with or without an invoice.
    Rules: `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1"""
    s = four_stages

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[3],
    )

    # Then 1
    assert idset(result) == {s.OC.id, s.OD.id}


# [claude] EXO-HF-18
def test_exo_hf_18__two_stages_or(db, g, order, inv):
    """EXO-HF-18 — two stage ids are alternatives (OR).
    Rules: `_apply_expense_order_stage_filter` R1"""
    v1 = inv(1, "10.00")
    oa = order("EXP-T-001")
    order("EXP-T-002", invoice_id=v1.id)
    oc = order("EXP-T-003", completed=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[1, 3],
    )

    # Then 1
    assert idset(result) == {oa.id, oc.id}


# [claude] EXO-HF-19
def test_exo_hf_19__only_unknown_stage_ids(db, g, order, inv):
    """EXO-HF-19 — only unknown stage ids apply no stage filter.
    Rules: `_apply_expense_order_stage_filter` R2"""
    v1 = inv(1, "10.00")
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", invoice_id=v1.id)
    oc = order("EXP-T-003", completed=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[9],
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id, oc.id}


# [claude] EXO-HF-20
def test_exo_hf_20__unknown_beside_known_ignored(db, g, order, inv):
    """EXO-HF-20 — an unknown id beside a known one is ignored.
    Rules: `_apply_expense_order_stage_filter` R2"""
    v1 = inv(1, "10.00")
    order("EXP-T-001")
    ob = order("EXP-T-002", invoice_id=v1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[2, 9],
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-21
def test_exo_hf_21__repeated_stage_id(db, g, order, inv):
    """EXO-HF-21 — a repeated stage id behaves like one.
    Rules: `_apply_expense_order_stage_filter` R3"""
    v1 = inv(1, "10.00")
    oa = order("EXP-T-001")
    order("EXP-T-002", invoice_id=v1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[1, 1],
    )

    # Then 1
    assert ids(result) == [oa.id]


# [claude] EXO-HF-22
def test_exo_hf_22__empty_status_ids(db, g, order, inv):
    """EXO-HF-22 — an empty status_ids list applies no filter.
    Rules: `_apply_expense_order_hub_filters` R6"""
    v1 = inv(1, "10.00")
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", invoice_id=v1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[],
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-HF-23
def test_exo_hf_23__stage_3_with_exclude_complete(db, g, order):
    """EXO-HF-23 — stage 3 with exclude_complete true keeps nothing.
    Rules: `_apply_expense_order_hub_filters` R9"""
    order("EXP-T-001")
    order("EXP-T-003", completed=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=True,
        exclude_voided=False,
        status_ids=[3],
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-24
def test_exo_hf_24__voided_draft_passes_stage_1(db, g, order):
    """EXO-HF-24 — voiding is not a stage: a voided draft passes stage 1.
    Rules: `_apply_expense_order_stage_filter` R1"""
    oa = order("EXP-T-001", voided=True)
    order("EXP-T-002", completed=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        status_ids=[1],
    )

    # Then 1
    assert idset(result) == {oa.id}


@pytest.fixture
def two_invoicing(order, inv):
    """The Given of EXO-HF-25 … HF-28: V1; OA without invoice, OB with V1."""
    v1 = inv(1, "10.00")
    return SimpleNamespace(
        OA=order("EXP-T-001"), OB=order("EXP-T-002", invoice_id=v1.id)
    )


# [claude] EXO-HF-25
def test_exo_hf_25__invoice_filter_invoiced(db, g, two_invoicing):
    """EXO-HF-25 — invoice_filter "invoiced" keeps orders with an invoice.
    Rules: `_apply_expense_order_hub_filters` R7"""
    s = two_invoicing

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        invoice_filter="invoiced",
    )

    # Then 1
    assert idset(result) == {s.OB.id}


# [claude] EXO-HF-26
def test_exo_hf_26__invoice_filter_not_invoiced(db, g, two_invoicing):
    """EXO-HF-26 — invoice_filter "not_invoiced" keeps orders with no invoice.
    Rules: `_apply_expense_order_hub_filters` R7"""
    s = two_invoicing

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        invoice_filter="not_invoiced",
    )

    # Then 1
    assert idset(result) == {s.OA.id}


# [claude] EXO-HF-27, HF-28
@pytest.mark.parametrize(
    "value",
    [pytest.param("Invoiced", id="EXO-HF-27"), pytest.param("all", id="EXO-HF-28")],
)
def test_exo_hf_27_28__other_invoice_filter_no_filter(db, g, two_invoicing, value):
    """EXO-HF-27, HF-28 — invoice_filter "Invoiced" (capital) or "all" applies no filter.
    Rules: `_apply_expense_order_hub_filters` R7"""
    s = two_invoicing

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        invoice_filter=value,
    )

    # Then 1
    assert idset(result) == {s.OA.id, s.OB.id}


# [claude] EXO-HF-29
def test_exo_hf_29__exclude_voided_true(db, g, order):
    """EXO-HF-29 — exclude_voided true leaves voided orders out.
    Rules: `_apply_expense_order_hub_filters` R8"""
    oa = order("EXP-T-001")
    order("EXP-T-002", voided=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=True,
    )

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-30
def test_exo_hf_30__exclude_voided_false(db, g, order):
    """EXO-HF-30 — exclude_voided false includes voided orders.
    Rules: `_apply_expense_order_hub_filters` R8"""
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", voided=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-HF-31
def test_exo_hf_31__exclude_complete_true(db, g, order):
    """EXO-HF-31 — exclude_complete true leaves completed orders out.
    Rules: `_apply_expense_order_hub_filters` R9"""
    oa = order("EXP-T-001")
    order("EXP-T-002", completed=True)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=True,
        exclude_voided=False,
    )

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-32
def test_exo_hf_32__dao_defaults_exclude_both(db, g, order):
    """EXO-HF-32 — with neither flag passed, completed and voided orders are both left out.
    Rules: `list_for_hub` R1 (DAO defaults); `_apply_expense_order_hub_filters` R8, R9"""
    oa = order("EXP-T-001")
    order("EXP-T-002", completed=True)
    order("EXP-T-003", voided=True)

    result = dao.list_for_hub(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-33
def test_exo_hf_33__search_number_middle(db, g, order):
    """EXO-HF-33 — search matches the middle of the number, case-insensitively.
    Rules: `_apply_expense_order_hub_filters` R10"""
    oa = order("EXP-Q7Z-1")
    order("EXP-T-002")
    order("EXP-Q7Z-9", k=2)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="q7z",
    )

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-34
def test_exo_hf_34__search_account_name_middle(db, g, order):
    """EXO-HF-34 — search matches the middle of the account's name, case-insensitively.
    Rules: `_apply_expense_order_hub_filters` R10"""
    order("EXP-T-001", account_id=g.K1.id)
    ob = order("EXP-T-002", account_id=g.K2.id)
    order("EXP-T-003")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="RCH TR",
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-35
def test_exo_hf_35__search_category_middle(db, g, order):
    """EXO-HF-35 — search matches the middle of the category, case-insensitively.
    Rules: `_apply_expense_order_hub_filters` R10"""
    order("EXP-T-001")
    ob = order("EXP-T-002", expense_category="department")
    order("EXP-T-003", expense_category="other")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="PARTM",
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-HF-36
def test_exo_hf_36__search_o(db, g, order):
    """EXO-HF-36 — search "o" matches the factory and other orders, not department.
    Rules: `_apply_expense_order_hub_filters` R10"""
    oa = order("EXP-T-001")
    order("EXP-T-002", expense_category="department")
    oc = order("EXP-T-003", expense_category="other")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="o",
    )

    # Then 1
    assert idset(result) == {oa.id, oc.id}


# [claude] EXO-HF-37
def test_exo_hf_37__search_trimmed(db, g, order):
    """EXO-HF-37 — the search text is trimmed.
    Rules: `_apply_expense_order_hub_filters` R10"""
    oa = order("EXP-Q7Z-1")
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="  Q7Z  ",
    )

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-38
def test_exo_hf_38__whitespace_search_no_filter(db, g, order):
    """EXO-HF-38 — a whitespace-only search applies no filter.
    Rules: `_apply_expense_order_hub_filters` R10"""
    oa = order("EXP-Q7Z-1")
    ob = order("EXP-T-002", account_id=g.K2.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="   ",
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-HF-39
def test_exo_hf_39__empty_search_no_filter(db, g, order):
    """EXO-HF-39 — an empty search applies no filter.
    Rules: `_apply_expense_order_hub_filters` R10"""
    oa = order("EXP-Q7Z-1")
    ob = order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="",
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-HF-40
def test_exo_hf_40__other_workspace_account_name(db, g, order):
    """EXO-HF-40 — a search matching another workspace's own account name finds nothing for W1.
    Rules: `_apply_expense_order_hub_filters` R1, R10"""
    order("EXP-T-900", k=0, account_id=g.A0.id)
    order("EXP-T-001", account_id=g.K1.id)
    order("EXP-T-902", k=2, account_id=g.A2.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="Overseas",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-41
def test_exo_hf_41__underscore_search_finds_its_order(db, g, order):
    """EXO-HF-41 — a search with "_" finds the order whose number has it.
    Rules: `_apply_expense_order_hub_filters` R10 [BUG-745] (the part that holds today)"""
    oa = order("EXP-T_9")
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="T_9",
    )

    # Then 1
    assert oa.id in idset(result)


BUG_745 = "BUG-745: Hub search text is an unescaped `ILIKE` pattern"


# [claude] EXO-HF-42
@pytest.mark.xfail(strict=True, reason=BUG_745)
def test_exo_hf_42__underscore_literal_only(db, g, order):
    """EXO-HF-42 — "_" matches only a literal underscore.
    Rules: `_apply_expense_order_hub_filters` R10 [BUG-745]"""
    oa = order("EXP-T_9")
    order("EXP-T-002")
    order("EXP-T-003", account_id=g.K1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="_",
    )

    # Then 1
    assert oa.id in idset(result)
    # Then 2
    assert idset(result) == {oa.id}


# [claude] EXO-HF-43
@pytest.mark.xfail(strict=True, reason=BUG_745)
def test_exo_hf_43__percent_literal_only(db, g, order):
    """EXO-HF-43 — "%" matches only a literal percent sign.
    Rules: `_apply_expense_order_hub_filters` R10 [BUG-745]"""
    oa = order("EXP-50%-1")
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="%",
    )

    # Then 1
    assert oa.id in idset(result)
    # Then 2
    assert idset(result) == {oa.id}


# [claude] EXO-HF-44
@pytest.mark.xfail(strict=True, reason=BUG_745)
def test_exo_hf_44__t_underscore_0_not_t_dash_0(db, g, order):
    """EXO-HF-44 — "T_0" does not match "T-0".
    Rules: `_apply_expense_order_hub_filters` R10 [BUG-745]"""
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="T_0",
    )

    # Then 1
    assert result == []


BUG_2714 = "BUG-2714: Expense hub uses another workspace's account and invoice"


# [claude] EXO-HF-45, HF-46
@pytest.mark.xfail(strict=True, reason=BUG_2714)
@pytest.mark.parametrize(
    ("acct", "term"),
    [
        pytest.param("A0", "Foreign", id="EXO-HF-45"),
        pytest.param("A2", "Overseas", id="EXO-HF-46"),
    ],
)
def test_exo_hf_45_46__foreign_account_name_no_match(db, g, order, acct, term):
    """EXO-HF-45, HF-46 — an account of W0 / W2 linked to a W1 order: its name does not match.
    Rules: `_apply_expense_order_hub_filters` R11 [BUG-2714] (HR-16)"""
    order(
        "EXP-T-001", account_id=getattr(g, acct).id
    )  # invalid data: another workspace's account
    order("EXP-T-002", account_id=g.K1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search=term,
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-47
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2715: Expense hub search matches a soft-deleted account's name",
)
def test_exo_hf_47__deleted_account_name_no_match(db, g, order, deleted_account):
    """EXO-HF-47 — a soft-deleted account's name does not match.
    Rules: `_apply_expense_order_hub_filters` R12 [BUG-2715] (HR-4)"""
    kg = deleted_account("Gone Ltd")
    order("EXP-T-001", account_id=kg.id)
    order("EXP-T-002", account_id=g.K1.id)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="Gone",
    )

    # Then 1
    assert result == []


# [claude] EXO-HF-48
def test_exo_hf_48__deleted_account_order_matches_number(db, g, order, deleted_account):
    """EXO-HF-48 — an order of a soft-deleted account still matches on its number.
    Rules: `_apply_expense_order_hub_filters` R12, R10"""
    kg = deleted_account("Gone Ltd")
    oa = order("EXP-Q7Z-1", account_id=kg.id)
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="Q7Z",
    )

    # Then 1
    assert idset(result) == {oa.id}


# [claude] EXO-HF-49
def test_exo_hf_49__unknown_filter_keyword(db, g, order):
    """EXO-HF-49 — an unknown filter keyword raises TypeError.
    Rules: `_apply_expense_order_hub_filters` R13; `list_for_hub` Errors"""
    order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.list_for_hub(db, workspace_id=g.W1.id, limit=1000, colour="red")
    assert isinstance(exc.value, TypeError)


# [claude] EXO-HF-50
def test_exo_hf_50__search_category_slug_middle(db, g, order):
    """EXO-HF-50 — a search finds a category outside the three labels in the middle of its slug, ignoring case.
    Rules: `_apply_expense_order_hub_filters` R10 (category substring)"""
    oa = order("EXP-T-001", expense_category="office_rent")
    order("EXP-T-002")

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
        search="FICE",
    )

    # Then 1
    assert idset(result) == {oa.id}


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] EXO-GW-01
def test_exo_gw_01__w1_orders_voided_and_completed_included(db, g, order):
    """EXO-GW-01 — returns W1's orders, voided and completed included, not W0's or W2's.
    Rules: `get_by_workspace` R1"""
    order("EXP-T-900", k=0)
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", completed=True)
    oc = order("EXP-T-003", voided=True)
    order("EXP-T-902", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert idset(result) == {oa.id, ob.id, oc.id}


# [claude] EXO-GW-02
def test_exo_gw_02__asked_for_w0(db, g, order):
    """EXO-GW-02 — asked for W0, only W0's order.
    Rules: `get_by_workspace` R1"""
    x0 = order("EXP-T-900", k=0)
    order("EXP-T-001")
    order("EXP-T-902", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W0.id, limit=1000)

    # Then 1
    assert idset(result) == {x0.id}


# [claude] EXO-GW-03
def test_exo_gw_03__asked_for_w2(db, g, order):
    """EXO-GW-03 — asked for W2, only W2's order.
    Rules: `get_by_workspace` R1"""
    order("EXP-T-900", k=0)
    order("EXP-T-001")
    x2 = order("EXP-T-902", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W2.id, limit=1000)

    # Then 1
    assert idset(result) == {x2.id}


# [claude] EXO-GW-04
def test_exo_gw_04__category_exact_match(db, g, order):
    """EXO-GW-04 — expense_category is an exact match.
    Rules: `get_by_workspace` R2"""
    order("EXP-T-001")
    ob = order("EXP-T-002", expense_category="department")
    order("EXP-T-902", k=2, expense_category="department")

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, expense_category="department", limit=1000
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-GW-05
def test_exo_gw_05__category_capital_keeps_nothing(db, g, order):
    """EXO-GW-05 — expense_category "Department" (capital) keeps nothing.
    Rules: `get_by_workspace` R2"""
    order("EXP-T-002", expense_category="department")

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, expense_category="Department", limit=1000
    )

    # Then 1
    assert result == []


# [claude] EXO-GW-06
def test_exo_gw_06__empty_category_no_filter(db, g, order):
    """EXO-GW-06 — expense_category "" applies no filter.
    Rules: `get_by_workspace` R2"""
    oa = order("EXP-T-001")
    ob = order("EXP-T-002", expense_category="department")

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, expense_category="", limit=1000
    )

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-GW-07
def test_exo_gw_07__account_id_middle_account(db, g, order):
    """EXO-GW-07 — account_id keeps the middle account's orders only.
    Rules: `get_by_workspace` R3"""
    order("EXP-T-001", account_id=g.K1.id)
    ob = order("EXP-T-002", account_id=g.K2.id)
    order("EXP-T-003", account_id=g.K3.id)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, account_id=g.K2.id, limit=1000
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-GW-08
def test_exo_gw_08__account_id_zero_no_filter(db, g, order):
    """EXO-GW-08 — account_id 0 applies no filter (unlike the hub).
    Rules: `get_by_workspace` R3"""
    oa = order("EXP-T-001", account_id=g.K1.id)
    ob = order("EXP-T-002")

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, account_id=0, limit=1000)

    # Then 1
    assert idset(result) == {oa.id, ob.id}


# [claude] EXO-GW-09
def test_exo_gw_09__invoice_id_middle_invoice(db, g, order, inv):
    """EXO-GW-09 — invoice_id keeps the middle invoice's order only.
    Rules: `get_by_workspace` R4"""
    v1 = inv(1, "10.00")
    v2 = inv(1, "20.00")
    v3 = inv(1, "30.00")
    order("EXP-T-001", invoice_id=v1.id)
    ob = order("EXP-T-002", invoice_id=v2.id)
    order("EXP-T-003", invoice_id=v3.id)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, invoice_id=v2.id, limit=1000
    )

    # Then 1
    assert idset(result) == {ob.id}


# [claude] EXO-GW-10
def test_exo_gw_10__invoice_id_zero_keeps_nothing(db, g, order, inv):
    """EXO-GW-10 — invoice_id 0 keeps nothing.
    Rules: `get_by_workspace` R4"""
    v1 = inv(1, "10.00")
    order("EXP-T-001", invoice_id=v1.id)
    order("EXP-T-002")

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, invoice_id=0, limit=1000)

    # Then 1
    assert result == []


# [claude] EXO-GW-11
def test_exo_gw_11__newest_created_first(db, g, order):
    """EXO-GW-11 — newest created_at first, ids not rising with the stamps.
    Rules: `get_by_workspace` R6 (the part that holds today)"""
    oa = order("EXP-T-001", created_at=T2)
    ob = order("EXP-T-002", created_at=T5)
    oc = order("EXP-T-003", created_at=T1)
    od = order("EXP-T-004", created_at=T4)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert ids(result) == [ob.id, od.id, oa.id, oc.id]


# [claude] EXO-GW-12
def test_exo_gw_12__skip_and_limit(db, g, order):
    """EXO-GW-12 — skip and limit take the second and third newest of five.
    Rules: `get_by_workspace` R5"""
    order("EXP-T-001", created_at=T2)
    order("EXP-T-002", created_at=T5)
    order("EXP-T-003", created_at=T1)
    od = order("EXP-T-004", created_at=T4)
    oe = order("EXP-T-005", created_at=T3)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [od.id, oe.id]


# [claude] EXO-GW-13
def test_exo_gw_13__default_limit_100(db, g, row):
    """EXO-GW-13 — the default limit is 100.
    Rules: `get_by_workspace` R5"""
    for i in range(1, 102):
        db.add(row(f"EXP-L-{i:03d}"))
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 100


# [claude] EXO-GW-14
def test_exo_gw_14__invoice_filter_before_paging(db, g, order, inv):
    """EXO-GW-14 — the invoice filter runs before paging.
    Rules: `get_by_workspace` R4, R5"""
    v1 = inv(1, "10.00")
    v2 = inv(1, "20.00")
    order("EXP-T-002", invoice_id=v2.id, created_at=T5)
    order("EXP-T-001", invoice_id=v1.id, created_at=T3)
    oc = order("EXP-T-003", invoice_id=v1.id, created_at=T1)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, invoice_id=v1.id, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [oc.id]


BUG_2711 = (
    "BUG-2711: The expense order found for an invoice is arbitrary when two share it "
    "and their creation times tie"
)


# [claude] EXO-GW-15
@pytest.mark.xfail(strict=False, reason=BUG_2711)
def test_exo_gw_15__equal_created_at_higher_id_first(db, g, order):
    """EXO-GW-15 — equal created_at: the higher id comes first.
    Rules: `get_by_workspace` R6 [BUG-2711]"""
    seqscan(db)
    oa_id = order("EXP-T-001", created_at=T3).id
    ob_id = order("EXP-T-002", created_at=T3).id
    w1_id = g.W1.id
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1_id, limit=1000)

    # Then 1
    assert ids(result) == [ob_id, oa_id]


# [claude] EXO-GW-16
@pytest.mark.xfail(strict=True, reason=BUG_2711)
def test_exo_gw_16__orders_by_created_at_then_id(db, g, order):
    """EXO-GW-16 — the query orders by created_at, then id, both descending.
    Rules: `get_by_workspace` R6 [BUG-2711]"""
    oa = order("EXP-T-001")

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert ids(result) == [oa.id]
    # Then 2
    assert "expense_orders.created_at DESC" in rec.order_part
    # Then 3
    assert "expense_orders.id DESC" in rec.order_part


# [claude] EXO-GW-17
def test_exo_gw_17__positional_arguments(db, g, order):
    """EXO-GW-17 — positional arguments raise TypeError.
    Rules: `get_by_workspace` R7"""
    order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_workspace(db, g.W1.id)
    assert isinstance(exc.value, TypeError)


# [claude] EXO-GW-18
def test_exo_gw_18__writes_nothing_no_lock_pending_stays(db, g, order):
    """EXO-GW-18 — writes nothing and takes no lock; a pending order and an unflushed edit stay.
    Rules: `get_by_workspace` Side effects; Overview (no lock)"""
    oa = order("EXP-T-001")
    oa.description = "Edited"
    p = ExpenseOrder(
        workspace_id=g.W1.id,
        expense_number=GN("EXP-T-009"),
        expense_category="factory",
        expense_date=D2,
        subtotal=Decimal("0.00"),
        total_amount=Decimal("10.00"),
        created_by=g.U1.id,
    )
    db.add(p)

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert ids(result) == [oa.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert oa in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.list_for_hub
# --------------------------------------------------------------------------- #


@pytest.fixture
def five_dated(order):
    """The Given of EXO-LH-01, LH-02: R1 … R5 with (expense_date, created_at)."""
    return SimpleNamespace(
        R1=order("EXP-T-001", expense_date=D2, created_at=T3),
        R2=order("EXP-T-002", expense_date=D3, created_at=T1),
        R3=order("EXP-T-003", expense_date=D2, created_at=T5),
        R4=order("EXP-T-004", expense_date=D2, created_at=T3),
        R5=order("EXP-T-005", expense_date=D1, created_at=T5),
    )


# [claude] EXO-LH-01
def test_exo_lh_01__ordered_by_date_created_id_desc(db, g, five_dated):
    """EXO-LH-01 — ordered by expense_date, then created_at, then id, all descending.
    Rules: `list_for_hub` R2"""
    s = five_dated

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        limit=1000,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert ids(result) == [s.R2.id, s.R3.id, s.R4.id, s.R1.id, s.R5.id]


# [claude] EXO-LH-02
def test_exo_lh_02__skip_1_limit_2(db, g, five_dated):
    """EXO-LH-02 — skip 1, limit 2 of five.
    Rules: `list_for_hub` R3"""
    s = five_dated

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        skip=1,
        limit=2,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert ids(result) == [s.R3.id, s.R4.id]


# [claude] EXO-LH-03
def test_exo_lh_03__default_limit_50(db, g, row):
    """EXO-LH-03 — the default limit is 50.
    Rules: `list_for_hub` R3"""
    for i in range(1, 52):
        db.add(row(f"EXP-L-{i:03d}"))
    db.flush()

    result = dao.list_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert len(result) == 50


# [claude] EXO-LH-04
def test_exo_lh_04__skip_past_end(db, g, row):
    """EXO-LH-04 — skip past the end gives [].
    Rules: `list_for_hub` R3"""
    for i in range(1, 6):
        db.add(row(f"EXP-L-{i:03d}"))
    db.flush()

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        skip=5,
        limit=10,
        exclude_complete=False,
        exclude_voided=False,
    )

    # Then 1
    assert result == []


# [claude] EXO-LH-05
def test_exo_lh_05__filters_before_paging(db, g, order):
    """EXO-LH-05 — the filters run before paging; the hidden order sorts first.
    Rules: `list_for_hub` R1, R3"""
    order("EXP-T-001", expense_category="department", expense_date=D3)
    order("EXP-T-002", expense_date=D2)
    f2 = order("EXP-T-003", expense_date=D1)

    result = dao.list_for_hub(
        db,
        workspace_id=g.W1.id,
        skip=1,
        limit=1,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="factory",
    )

    # Then 1
    assert ids(result) == [f2.id]


# [claude] EXO-LH-06
def test_exo_lh_06__writes_nothing_no_lock(db, g, order):
    """EXO-LH-06 — writes nothing and takes no lock.
    Rules: `list_for_hub` Side effects; Overview (no lock)"""
    oa = order("EXP-T-001")
    oa.description = "Edited"

    with StatementRecorder(db) as rec:
        result = dao.list_for_hub(
            db,
            workspace_id=g.W1.id,
            limit=1000,
            exclude_complete=False,
            exclude_voided=False,
        )

    # Then 1
    assert ids(result) == [oa.id]
    # Then 2
    assert oa in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert rec.written == []
    # Then 5
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.count_for_hub
# --------------------------------------------------------------------------- #


# [claude] EXO-CH-01
def test_exo_ch_01__counts_w1_only(db, g, order):
    """EXO-CH-01 — counts W1's orders only, as an int.
    Rules: `count_for_hub` R1"""
    order("EXP-T-900", k=0)
    order("EXP-T-001")
    order("EXP-T-002")
    order("EXP-T-003")
    order("EXP-T-902", k=2)

    result = dao.count_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 3


# [claude] EXO-CH-02
def test_exo_ch_02__nothing_gives_zero(db, g, order):
    """EXO-CH-02 — no order passing gives 0, not None.
    Rules: `count_for_hub` R1"""
    order("EXP-T-902", k=2)

    result = dao.count_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 0


# [claude] EXO-CH-03
def test_exo_ch_03__no_paging(db, g, row):
    """EXO-CH-03 — no paging: 60 orders count 60.
    Rules: `count_for_hub` R1"""
    for i in range(1, 61):
        db.add(row(f"EXP-L-{i:03d}"))
    db.flush()

    result = dao.count_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == 60


# [claude] EXO-CH-04
def test_exo_ch_04__number_and_account_match_counted_once(db, g, order):
    """EXO-CH-04 — an order matching the search on number and account is counted once.
    Rules: `count_for_hub` R1 (distinct)"""
    order("EXP-BIRCH-1", account_id=g.K2.id)
    order("EXP-T-002", account_id=g.K2.id)
    order("EXP-T-003", account_id=g.K1.id)

    result = dao.count_for_hub(
        db,
        workspace_id=g.W1.id,
        exclude_complete=False,
        exclude_voided=False,
        search="birch",
    )

    # Then 1
    assert result == 2


# [claude] EXO-CH-05
def test_exo_ch_05__filters_and_dao_defaults(db, g, order):
    """EXO-CH-05 — applies the filters and the DAO defaults.
    Rules: `count_for_hub` R1; `_apply_expense_order_hub_filters` R2, R8, R9"""
    order("EXP-T-001")
    order("EXP-T-002", expense_category="department")
    order("EXP-T-003", completed=True)
    order("EXP-T-004", voided=True)

    result = dao.count_for_hub(db, workspace_id=g.W1.id, expense_category="factory")

    # Then 1
    assert result == 1


# [claude] EXO-CH-06
def test_exo_ch_06__unknown_filter_keyword(db, g, order):
    """EXO-CH-06 — an unknown filter keyword raises TypeError.
    Rules: `count_for_hub` Errors"""
    order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.count_for_hub(db, workspace_id=g.W1.id, colour="red")
    assert isinstance(exc.value, TypeError)


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.list_recent_for_hub
# --------------------------------------------------------------------------- #

BUG_746 = (
    """BUG-746: "Recent orders" widget sorts by the wrong key and has no tie-breaker"""
)


# [claude] EXO-RC-01
@pytest.mark.xfail(strict=True, reason=BUG_746)
def test_exo_rc_01__last_change_decides(db, g, order):
    """EXO-RC-01 — the last change decides: an edited order beats a newer never-edited one.
    Rules: `list_recent_for_hub` R2 [BUG-746]"""
    a = order("EXP-T-001", created_at=T1, updated_at=T5)
    b = order("EXP-T-002", created_at=T3)
    c = order("EXP-T-003", created_at=T2, updated_at=T4)

    result = dao.list_recent_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert ids(result) == [a.id, c.id, b.id]


# [claude] EXO-RC-02
def test_exo_rc_02__latest_edit_first(db, g, order):
    """EXO-RC-02 — among edited orders, the latest edit first.
    Rules: `list_recent_for_hub` R2 (the part that holds today)"""
    a = order("EXP-T-001", created_at=T1, updated_at=T5)
    c = order("EXP-T-002", created_at=T3, updated_at=T4)
    d = order("EXP-T-003", created_at=T2, updated_at=T3)

    result = dao.list_recent_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert ids(result) == [a.id, c.id, d.id]


# [claude] EXO-RC-03
def test_exo_rc_03__never_edited_newest_created_first(db, g, order):
    """EXO-RC-03 — among never-edited orders, the newest created first.
    Rules: `list_recent_for_hub` R2 (the part that holds today)"""
    b = order("EXP-T-001", created_at=T3)
    f = order("EXP-T-002", created_at=T1)
    g3 = order("EXP-T-003", created_at=T2)

    result = dao.list_recent_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert ids(result) == [b.id, g3.id, f.id]


# [claude] EXO-RC-04
def test_exo_rc_04__default_limit_10(db, g, order, row):
    """EXO-RC-04 — the default limit is 10: of 11, the oldest is left out.
    Rules: `list_recent_for_hub` R1"""
    z = order("EXP-L-000", created_at=datetime(2031, 3, 4, 8, 0))
    for i in range(1, 11):
        db.add(row(f"EXP-L-{i:03d}", created_at=datetime(2031, 3, 4, 9, i)))
    db.flush()

    result = dao.list_recent_for_hub(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert len(result) == 10
    # Then 2
    assert z.id not in idset(result)


# [claude] EXO-RC-05
def test_exo_rc_05__limit_2(db, g, order):
    """EXO-RC-05 — limit 2 gives the two newest.
    Rules: `list_recent_for_hub` R1"""
    b = order("EXP-T-001", created_at=T3)
    order("EXP-T-002", created_at=T1)
    g3 = order("EXP-T-003", created_at=T2)

    result = dao.list_recent_for_hub(
        db, workspace_id=g.W1.id, limit=2, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert ids(result) == [b.id, g3.id]


# [claude] EXO-RC-06
def test_exo_rc_06__filters_and_defaults(db, g, order):
    """EXO-RC-06 — applies the filters and the DAO defaults; newer hidden orders do not take places.
    Rules: `list_recent_for_hub` R1; `_apply_expense_order_hub_filters` R1, R8, R9"""
    order("EXP-T-900", k=0, created_at=T5)
    oa = order("EXP-T-001", created_at=T1)
    order("EXP-T-003", completed=True, created_at=T4)
    order("EXP-T-004", voided=True, created_at=T3)
    order("EXP-T-902", k=2, created_at=T5)

    result = dao.list_recent_for_hub(db, workspace_id=g.W1.id, limit=1)

    # Then 1
    assert ids(result) == [oa.id]


# [claude] EXO-RC-07
@pytest.mark.xfail(strict=False, reason=BUG_746)
def test_exo_rc_07__equal_last_change_higher_id_first(db, g, order):
    """EXO-RC-07 — equal last change: the higher id first.
    Rules: `list_recent_for_hub` R2 [BUG-746]"""
    seqscan(db)
    oa_id = order("EXP-T-001", created_at=T3).id
    ob_id = order("EXP-T-002", created_at=T3).id
    w1_id = g.W1.id
    db.expire_all()

    result = dao.list_recent_for_hub(
        db, workspace_id=w1_id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert ids(result) == [ob_id, oa_id]


# [claude] EXO-RC-08
@pytest.mark.xfail(strict=True, reason=BUG_746)
def test_exo_rc_08__orders_by_coalesce_then_id(db, g, order):
    """EXO-RC-08 — the query orders by coalesce(updated_at, created_at), then id, descending.
    Rules: `list_recent_for_hub` R2 [BUG-746]"""
    oa = order("EXP-T-001")

    with StatementRecorder(db) as rec:
        result = dao.list_recent_for_hub(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert ids(result) == [oa.id]
    # Then 2
    assert "coalesce" in rec.order_part.lower()
    # Then 3
    assert rec.order_part.strip().endswith("expense_orders.id DESC")


# [claude] EXO-RC-09
def test_exo_rc_09__no_lock_writes_nothing(db, g, order):
    """EXO-RC-09 — takes no lock and writes nothing.
    Rules: `list_recent_for_hub` Side effects; Overview (no lock)"""
    oa = order("EXP-T-001")

    with StatementRecorder(db) as rec:
        result = dao.list_recent_for_hub(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert ids(result) == [oa.id]
    # Then 2
    assert rec.written == []
    # Then 3
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.aggregate_hub_stats
# --------------------------------------------------------------------------- #


# [claude] EXO-HS-01
def test_exo_hs_01__totals_open_not_invoiced(db, g, order, inv):
    """EXO-HS-01 — totals, open and not-invoiced over draft, invoiced and completed orders.
    Rules: `aggregate_hub_stats` R1, R2, R3"""
    v1 = inv(1, "1000.05")
    order("EXP-T-001", total_amount=Decimal("0.10"))
    order("EXP-T-002", total_amount=Decimal("0.20"), invoice_id=v1.id)
    order(
        "EXP-T-003", total_amount=Decimal("1000.05"), completed=True, invoice_id=v1.id
    )

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == (3, Decimal("1000.35"), 2, Decimal("0.30"), 1)
    # Then 2
    assert isinstance(result[1], Decimal)
    # Then 3
    assert isinstance(result[3], Decimal)


# [claude] EXO-HS-02
def test_exo_hs_02__other_workspaces_not_counted(db, g, order):
    """EXO-HS-02 — W0's and W2's amounts are not counted.
    Rules: `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R1"""
    order("EXP-T-900", k=0, total_amount=Decimal("500.00"))
    order("EXP-T-001", total_amount=Decimal("0.10"))
    order("EXP-T-902", k=2, total_amount=Decimal("700.00"))

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == (1, Decimal("0.10"), 1, Decimal("0.10"), 1)


# [claude] EXO-HS-03
def test_exo_hs_03__nothing_gives_zeros(db, g, order):
    """EXO-HS-03 — no order passing gives zeros with Decimal values.
    Rules: `aggregate_hub_stats` R4"""
    order("EXP-T-902", k=2, total_amount=Decimal("700.00"))

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == (0, Decimal("0"), 0, Decimal("0"), 0)
    # Then 2
    assert isinstance(result[1], Decimal)
    # Then 3
    assert isinstance(result[3], Decimal)


# [claude] EXO-HS-04
def test_exo_hs_04__negative_and_zero_added(db, g, order):
    """EXO-HS-04 — negative and zero totals are added as they are.
    Rules: `aggregate_hub_stats` R4"""
    order("EXP-T-001", total_amount=Decimal("-5.25"))
    order("EXP-T-002", total_amount=Decimal("0.00"))
    order("EXP-T-003", total_amount=Decimal("5.26"))

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == (3, Decimal("0.01"), 3, Decimal("0.01"), 3)


# [claude] EXO-HS-05
def test_exo_hs_05__ten_times_0_10(db, g, row):
    """EXO-HS-05 — ten amounts of 0.10 add up to exactly 1.00.
    Rules: `aggregate_hub_stats` R4 (HR-15)"""
    for i in range(1, 11):
        db.add(row(f"EXP-L-{i:03d}", total_amount=Decimal("0.10")))
    db.flush()

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result[1] == Decimal("1.00")
    # Then 2
    assert result[3] == Decimal("1.00")


# [claude] EXO-HS-06
def test_exo_hs_06__completed_without_invoice(db, g, order, inv):
    """EXO-HS-06 — a completed order without an invoice is not open but is not invoiced.
    Rules: `aggregate_hub_stats` R2, R3"""
    v1 = inv(1, "3.00")
    order("EXP-T-001", total_amount=Decimal("7.00"), completed=True)
    order("EXP-T-002", total_amount=Decimal("3.00"), invoice_id=v1.id)

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result == (2, Decimal("10.00"), 1, Decimal("3.00"), 1)


# [claude] EXO-HS-07
def test_exo_hs_07__default_leaves_completed_out(db, g, order):
    """EXO-HS-07 — with no flags passed, completed orders are left out (DAO default).
    Rules: `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R9"""
    order("EXP-T-001", total_amount=Decimal("1.00"))
    order("EXP-T-002", total_amount=Decimal("2.00"), completed=True)

    result = dao.aggregate_hub_stats(db, workspace_id=g.W1.id)

    # Then 1
    assert result == (1, Decimal("1.00"), 1, Decimal("1.00"), 1)


# [claude] EXO-HS-08
def test_exo_hs_08__category_filter_limits_every_figure(db, g, order):
    """EXO-HS-08 — a category filter limits every figure.
    Rules: `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R2"""
    order("EXP-T-001", total_amount=Decimal("1.00"))
    order("EXP-T-002", total_amount=Decimal("2.00"), expense_category="department")

    result = dao.aggregate_hub_stats(
        db,
        workspace_id=g.W1.id,
        exclude_complete=False,
        exclude_voided=False,
        expense_category="department",
    )

    # Then 1
    assert result == (1, Decimal("2.00"), 1, Decimal("2.00"), 1)


# [claude] EXO-HS-09
def test_exo_hs_09__unknown_filter_keyword(db, g, order):
    """EXO-HS-09 — an unknown filter keyword raises TypeError.
    Rules: `aggregate_hub_stats` Errors"""
    order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.aggregate_hub_stats(db, workspace_id=g.W1.id, colour="red")
    assert isinstance(exc.value, TypeError)


# [claude] EXO-HS-10
def test_exo_hs_10__no_lock_writes_nothing(db, g, order):
    """EXO-HS-10 — takes no lock and writes nothing.
    Rules: `aggregate_hub_stats` Side effects; Overview (no lock)"""
    order("EXP-T-001")

    with StatementRecorder(db) as rec:
        result = dao.aggregate_hub_stats(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert result[0] == 1
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in s for s in rec.selects)


# [claude] EXO-HS-11
def test_exo_hs_11__voided_counts_in_total_and_not_invoiced(db, g, order):
    """EXO-HS-11 — with exclude_voided false, a voided order counts in total and not invoiced.
    Rules: `aggregate_hub_stats` R1, R3 (the counts that follow `exclude_voided`)"""
    order("EXP-T-001", total_amount=Decimal("100.00"))
    order("EXP-T-003", total_amount=Decimal("30.00"), voided=True)

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[4] == 2


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.aggregate_financial_snapshot_filtered (with _filtered_orders_query)
# --------------------------------------------------------------------------- #


# [claude] EXO-SF-01
def test_exo_sf_01__category_breakdown_by_total_desc(db, g, order):
    """EXO-SF-01 — category breakdown: one entry per category, by total descending.
    Rules: `aggregate_financial_snapshot_filtered` R1, R2"""
    order("EXP-T-001", total_amount=Decimal("0.10"))
    order("EXP-T-002", total_amount=Decimal("0.20"))
    order("EXP-T-003", total_amount=Decimal("5.00"), expense_category="department")
    order("EXP-T-004", total_amount=Decimal("0.05"), expense_category="other")

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "department",
            "label": "Department",
            "count": 1,
            "total_value": Decimal("5.00"),
        },
        {
            "key": "factory",
            "label": "Factory",
            "count": 2,
            "total_value": Decimal("0.30"),
        },
        {"key": "other", "label": "Other", "count": 1, "total_value": Decimal("0.05")},
    ]


# [claude] EXO-SF-02
def test_exo_sf_02__nothing_passing(db, g, order):
    """EXO-SF-02 — nothing passing: empty breakdown, three zero stages, empty open by account.
    Rules: `aggregate_financial_snapshot_filtered` R4, R5"""
    order("EXP-T-902", k=2, account_id=g.A2.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == []
    # Then 2
    assert result["stage_pipeline"] == Z3
    # Then 3
    assert result["open_by_account"] == []
    # Then 4
    assert set(result) == {"category_breakdown", "stage_pipeline", "open_by_account"}


CATS = [
    ("rent", "7.00"),
    ("water", "6.00"),
    ("power", "5.00"),
    ("fuel", "4.00"),
    ("tax", "3.00"),
    ("fees", "2.00"),
    ("misc", "1.00"),
    ("tolls", "0.50"),
]


def _category_orders(order, n):
    """Orders "EXP-C-001" … with the first n (expense_category, total_amount) pairs of CATS."""
    for i, (cat, total) in enumerate(CATS[:n], start=1):
        order(f"EXP-C-{i:03d}", expense_category=cat, total_amount=Decimal(total))


# [claude] EXO-SF-03
def test_exo_sf_03__six_categories_kept(db, g, order):
    """EXO-SF-03 — six categories are kept as they are.
    Rules: `aggregate_financial_snapshot_filtered` R3"""
    _category_orders(order, 6)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["key"] for e in result["category_breakdown"]] == [
        "rent",
        "water",
        "power",
        "fuel",
        "tax",
        "fees",
    ]
    # Then 2
    assert [e["label"] for e in result["category_breakdown"]] == [
        "Rent",
        "Water",
        "Power",
        "Fuel",
        "Tax",
        "Fees",
    ]


# [claude] EXO-SF-04
def test_exo_sf_04__seventh_merged_into_other(db, g, order):
    """EXO-SF-04 — a seventh category is merged into a trailing Other entry.
    Rules: `aggregate_financial_snapshot_filtered` R3"""
    _category_orders(order, 7)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert len(result["category_breakdown"]) == 7
    # Then 2
    assert result["category_breakdown"][5] == {
        "key": "fees",
        "label": "Fees",
        "count": 1,
        "total_value": Decimal("2.00"),
    }
    # Then 3
    assert result["category_breakdown"][6] == {
        "key": "other",
        "label": "Other",
        "count": 1,
        "total_value": Decimal("1.00"),
    }


# [claude] EXO-SF-05
def test_exo_sf_05__seventh_and_eighth_added(db, g, order):
    """EXO-SF-05 — the seventh and eighth categories are added together.
    Rules: `aggregate_financial_snapshot_filtered` R3"""
    _category_orders(order, 8)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert len(result["category_breakdown"]) == 7
    # Then 2
    assert result["category_breakdown"][6] == {
        "key": "other",
        "label": "Other",
        "count": 2,
        "total_value": Decimal("1.50"),
    }


BUG_2712 = "BUG-2712: Expense hub category breakdown has unordered ties"


# [claude] EXO-SF-06
@pytest.mark.xfail(strict=False, reason=BUG_2712)
def test_exo_sf_06__equal_category_totals_key_ascending(db, g, order):
    """EXO-SF-06 — equal category totals: key ascending.
    Rules: `aggregate_financial_snapshot_filtered` R2 [BUG-2712]"""
    seqscan(db)
    order("EXP-T-001", total_amount=Decimal("5.00"))
    order("EXP-T-002", total_amount=Decimal("5.00"), expense_category="department")
    w1_id = g.W1.id
    db.expire_all()

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=w1_id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["key"] for e in result["category_breakdown"]] == ["department", "factory"]


# [claude] EXO-SF-07
@pytest.mark.xfail(strict=True, reason=BUG_2712)
def test_exo_sf_07__category_query_ties_by_category(db, g, order):
    """EXO-SF-07 — the category query breaks ties by the category.
    Rules: `aggregate_financial_snapshot_filtered` R2 [BUG-2712]"""
    order("EXP-T-001", total_amount=Decimal("5.00"))

    with StatementRecorder(db) as rec:
        result = dao.aggregate_financial_snapshot_filtered(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert len(result["category_breakdown"]) == 1
    # Then 2
    [cat_sql] = [
        s for s in rec.selects if "GROUP BY expense_orders.expense_category" in s
    ]
    assert "expense_orders.expense_category" in cat_sql.split("ORDER BY", 1)[1]


# [claude] EXO-SF-08
def test_exo_sf_08__stage_pipeline(db, g, order, inv):
    """EXO-SF-08 — stage pipeline: draft, invoiced, complete with counts and exact sums.
    Rules: `aggregate_financial_snapshot_filtered` R5; `_expense_order_stage_key_expr` R1"""
    v1 = inv(1, "7.00")
    order("EXP-T-001", total_amount=Decimal("0.10"))
    order("EXP-T-002", total_amount=Decimal("0.20"))
    order("EXP-T-003", total_amount=Decimal("7.00"), invoice_id=v1.id)
    order("EXP-T-004", total_amount=Decimal("3.00"), completed=True)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["stage_pipeline"] == [
        {"key": "draft", "label": "Draft", "count": 2, "total_value": Decimal("0.30")},
        {
            "key": "invoiced",
            "label": "Invoiced",
            "count": 1,
            "total_value": Decimal("7.00"),
        },
        {
            "key": "complete",
            "label": "Complete",
            "count": 1,
            "total_value": Decimal("3.00"),
        },
    ]


# [claude] EXO-SF-09
def test_exo_sf_09__empty_stage_listed_with_zeros(db, g, order, inv):
    """EXO-SF-09 — a stage with no orders is still listed, with zeros.
    Rules: `aggregate_financial_snapshot_filtered` R5"""
    v1 = inv(1, "7.00")
    order("EXP-T-003", total_amount=Decimal("7.00"), invoice_id=v1.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["stage_pipeline"] == [
        {"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")},
        {
            "key": "invoiced",
            "label": "Invoiced",
            "count": 1,
            "total_value": Decimal("7.00"),
        },
        {
            "key": "complete",
            "label": "Complete",
            "count": 0,
            "total_value": Decimal("0"),
        },
    ]


# [claude] EXO-SF-10
def test_exo_sf_10__open_by_account(db, g, order):
    """EXO-SF-10 — open by account: per account, completed and account-less orders left out.
    Rules: `aggregate_financial_snapshot_filtered` R6, R7, R8"""
    order("EXP-T-001", total_amount=Decimal("0.10"), account_id=g.K1.id)
    order("EXP-T-002", total_amount=Decimal("0.20"), account_id=g.K1.id)
    order("EXP-T-003", total_amount=Decimal("5.00"), account_id=g.K2.id)
    order("EXP-T-004", total_amount=Decimal("9.00"))
    order(
        "EXP-T-005", total_amount=Decimal("50.00"), account_id=g.K3.id, completed=True
    )

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["open_by_account"] == [
        {
            "account_id": g.K2.id,
            "account_name": "Birch Traders",
            "count": 1,
            "total_value": Decimal("5.00"),
        },
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 2,
            "total_value": Decimal("0.30"),
        },
    ]


# [claude] EXO-SF-11
def test_exo_sf_11__at_most_five_accounts(db, g, order):
    """EXO-SF-11 — at most five accounts, the smallest sixth dropped.
    Rules: `aggregate_financial_snapshot_filtered` R8"""
    kd = _add(db, Account(workspace_id=g.W1.id, name="Dune Mart"))
    ke = _add(db, Account(workspace_id=g.W1.id, name="Elm Yard"))
    kf = _add(db, Account(workspace_id=g.W1.id, name="Fern Bay"))
    pairs = [
        (g.K3, "6.00"),
        (kf, "1.00"),
        (g.K1, "5.00"),
        (kd, "4.00"),
        (g.K2, "3.00"),
        (ke, "2.00"),
    ]
    for i, (acct, total) in enumerate(pairs, start=1):
        order(f"EXP-A-{i:03d}", account_id=acct.id, total_amount=Decimal(total))

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["account_id"] for e in result["open_by_account"]] == [
        g.K3.id,
        g.K1.id,
        kd.id,
        g.K2.id,
        ke.id,
    ]


BUG_747 = 'BUG-747: Dashboard "open by account" top-5 has unordered ties'


# [claude] EXO-SF-12
@pytest.mark.xfail(strict=False, reason=BUG_747)
def test_exo_sf_12__equal_account_totals_name_ci(db, g, order):
    """EXO-SF-12 — equal account totals: name case-insensitive ascending.
    Rules: `aggregate_financial_snapshot_filtered` R8 [BUG-747]"""
    seqscan(db)
    kb = _add(db, Account(workspace_id=g.W1.id, name="Beta Supply"))
    ka = _add(db, Account(workspace_id=g.W1.id, name="alpha supply"))
    order("EXP-T-001", total_amount=Decimal("5.00"), account_id=kb.id)
    order("EXP-T-002", total_amount=Decimal("5.00"), account_id=ka.id)
    w1_id = g.W1.id
    db.expire_all()

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=w1_id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["account_name"] for e in result["open_by_account"]] == [
        "alpha supply",
        "Beta Supply",
    ]


# [claude] EXO-SF-13
@pytest.mark.xfail(strict=True, reason=BUG_747)
def test_exo_sf_13__account_query_ties_by_name_then_id(db, g, order):
    """EXO-SF-13 — the open-by-account query breaks ties by name, then account id.
    Rules: `aggregate_financial_snapshot_filtered` R8 [BUG-747]"""
    order("EXP-T-001", account_id=g.K1.id)

    with StatementRecorder(db) as rec:
        result = dao.aggregate_financial_snapshot_filtered(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert len(result["open_by_account"]) == 1
    # Then 2
    [acct_sql] = [s for s in rec.selects if "GROUP BY expense_orders.account_id" in s]
    assert "accounts.name" in acct_sql.split("ORDER BY", 1)[1]
    # Then 3
    assert "accounts.id" in acct_sql.split("ORDER BY", 1)[1]


# [claude] EXO-SF-14
@pytest.mark.xfail(strict=True, reason=BUG_2714)
def test_exo_sf_14__w0_account_left_out_of_open_by_account(db, g, order):
    """EXO-SF-14 — a W1 order linked to W0's account is left out of open by account.
    Rules: `aggregate_financial_snapshot_filtered` R9 [BUG-2714] (HR-16)"""
    order("EXP-T-001", total_amount=Decimal("4.00"), account_id=g.A0.id)  # invalid data
    order("EXP-T-002", total_amount=Decimal("1.00"), account_id=g.K1.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 2,
            "total_value": Decimal("5.00"),
        }
    ]
    # Then 2
    assert result["open_by_account"] == [
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 1,
            "total_value": Decimal("1.00"),
        }
    ]


# [claude] EXO-SF-15
@pytest.mark.xfail(strict=True, reason=BUG_2714)
def test_exo_sf_15__w2_account_left_out_of_open_by_account(db, g, order):
    """EXO-SF-15 — a W1 order linked to W2's account is left out of open by account.
    Rules: `aggregate_financial_snapshot_filtered` R9 [BUG-2714] (HR-16)"""
    order("EXP-T-001", total_amount=Decimal("4.00"), account_id=g.A2.id)  # invalid data
    order("EXP-T-002", total_amount=Decimal("1.00"), account_id=g.K1.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["open_by_account"] == [
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 1,
            "total_value": Decimal("1.00"),
        }
    ]


# [claude] EXO-SF-16
def test_exo_sf_16__foreign_account_order_still_in_categories(db, g, order):
    """EXO-SF-16 — an order linked to another workspace's account still counts in the category breakdown.
    Rules: `aggregate_financial_snapshot_filtered` R1, R9 (the part that holds today)"""
    order("EXP-T-001", total_amount=Decimal("4.00"), account_id=g.A0.id)  # invalid data
    order("EXP-T-002", total_amount=Decimal("1.00"), account_id=g.K1.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 2,
            "total_value": Decimal("5.00"),
        }
    ]
    # Then 2
    assert {
        "account_id": g.K1.id,
        "account_name": "Alder Supplies",
        "count": 1,
        "total_value": Decimal("1.00"),
    } in result["open_by_account"]


# [claude] EXO-SF-17
def test_exo_sf_17__deleted_own_account_still_counts(db, g, order, deleted_account):
    """EXO-SF-17 — an order of a soft-deleted own account still counts under its name.
    Rules: `aggregate_financial_snapshot_filtered` R10"""
    kg = deleted_account("Gone Ltd")
    order("EXP-T-001", total_amount=Decimal("4.00"), account_id=kg.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["open_by_account"] == [
        {
            "account_id": kg.id,
            "account_name": "Gone Ltd",
            "count": 1,
            "total_value": Decimal("4.00"),
        }
    ]


# [claude] EXO-SF-18
def test_exo_sf_18__search_through_join_counts_once(db, g, order):
    """EXO-SF-18 — a search through the account join counts each order once in every part.
    Rules: `_filtered_orders_query` R1; `aggregate_financial_snapshot_filtered` R1, R6"""
    order("EXP-BIRCH-1", total_amount=Decimal("2.00"), account_id=g.K2.id)
    order("EXP-T-002", total_amount=Decimal("3.00"), account_id=g.K2.id)
    order("EXP-T-003", total_amount=Decimal("9.00"), account_id=g.K1.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db,
        workspace_id=g.W1.id,
        exclude_complete=False,
        exclude_voided=False,
        search="birch",
    )

    # Then 1
    assert result["open_by_account"] == [
        {
            "account_id": g.K2.id,
            "account_name": "Birch Traders",
            "count": 2,
            "total_value": Decimal("5.00"),
        }
    ]
    # Then 2
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 2,
            "total_value": Decimal("5.00"),
        }
    ]
    # Then 3
    assert result["stage_pipeline"][0] == {
        "key": "draft",
        "label": "Draft",
        "count": 2,
        "total_value": Decimal("5.00"),
    }


# [claude] EXO-SF-19
def test_exo_sf_19__other_workspaces_in_no_part(db, g, order):
    """EXO-SF-19 — W0's and W2's orders count in no part.
    Rules: `_filtered_orders_query` R1; `_apply_expense_order_hub_filters` R1"""
    order("EXP-T-900", k=0, total_amount=Decimal("50.00"), account_id=g.A0.id)
    order("EXP-T-001", total_amount=Decimal("1.00"), account_id=g.K1.id)
    order("EXP-T-902", k=2, total_amount=Decimal("70.00"), account_id=g.A2.id)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 1,
            "total_value": Decimal("1.00"),
        }
    ]
    # Then 2
    assert result["stage_pipeline"][0] == {
        "key": "draft",
        "label": "Draft",
        "count": 1,
        "total_value": Decimal("1.00"),
    }
    # Then 3
    assert result["open_by_account"] == [
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 1,
            "total_value": Decimal("1.00"),
        }
    ]


# [claude] EXO-SF-20
def test_exo_sf_20__default_leaves_completed_out(db, g, order):
    """EXO-SF-20 — with no flags passed, completed orders are left out of every part.
    Rules: `_filtered_orders_query` R1 (DAO defaults)"""
    order("EXP-T-001", total_amount=Decimal("1.00"))
    order("EXP-T-002", total_amount=Decimal("2.00"), completed=True)

    result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=g.W1.id)

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 1,
            "total_value": Decimal("1.00"),
        }
    ]
    # Then 2
    assert result["stage_pipeline"][2] == {
        "key": "complete",
        "label": "Complete",
        "count": 0,
        "total_value": Decimal("0"),
    }


# [claude] EXO-SF-21
def test_exo_sf_21__unknown_filter_keyword(db, g, order):
    """EXO-SF-21 — an unknown filter keyword raises TypeError.
    Rules: `aggregate_financial_snapshot_filtered` Errors; `_filtered_orders_query` Errors"""
    order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.aggregate_financial_snapshot_filtered(
            db, workspace_id=g.W1.id, colour="red"
        )
    assert isinstance(exc.value, TypeError)


# [claude] EXO-SF-22
def test_exo_sf_22__no_lock_writes_nothing(db, g, order):
    """EXO-SF-22 — takes no lock and writes nothing.
    Rules: `aggregate_financial_snapshot_filtered` Side effects; Overview (no lock)"""
    order("EXP-T-001", account_id=g.K1.id)

    with StatementRecorder(db) as rec:
        result = dao.aggregate_financial_snapshot_filtered(
            db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
        )

    # Then 1
    assert len(result["open_by_account"]) == 1
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in s for s in rec.selects)


# [claude] EXO-SF-23
@pytest.mark.xfail(strict=False, reason=BUG_747)
def test_exo_sf_23__same_name_equal_totals_lower_id_first(db, g, order):
    """EXO-SF-23 — two accounts with the same name and equal totals: the lower account id first.
    Rules: `aggregate_financial_snapshot_filtered` R8 [BUG-747]"""
    seqscan(db)
    kh = _add(
        db, Account(workspace_id=g.W1.id, name="Twin Co", id=high_id(db, "accounts"))
    )
    kl = _add(db, Account(workspace_id=g.W1.id, name="Twin Co"))
    order("EXP-T-001", total_amount=Decimal("5.00"), account_id=kh.id)
    order("EXP-T-002", total_amount=Decimal("5.00"), account_id=kl.id)
    kh_id, kl_id, w1_id = kh.id, kl.id, g.W1.id
    db.expire_all()

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=w1_id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["account_id"] for e in result["open_by_account"]] == [kl_id, kh_id]


# [claude] EXO-SF-24
def test_exo_sf_24__zero_order_exact_zero(db, g, order):
    """EXO-SF-24 — a 0.00 order gives exactly 0.00 in its category, its stage and its open account.
    Rules: `aggregate_financial_snapshot_filtered` R1, R5, R6 (HR-15)"""
    order(
        "EXP-T-001",
        total_amount=Decimal("0.00"),
        expense_category="department",
        account_id=g.K1.id,
    )
    order(
        "EXP-T-002", total_amount=Decimal("10.00"), account_id=g.K2.id, completed=True
    )

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 1,
            "total_value": Decimal("10.00"),
        },
        {
            "key": "department",
            "label": "Department",
            "count": 1,
            "total_value": Decimal("0.00"),
        },
    ]
    # Then 2
    assert result["stage_pipeline"] == [
        {"key": "draft", "label": "Draft", "count": 1, "total_value": Decimal("0.00")},
        {
            "key": "invoiced",
            "label": "Invoiced",
            "count": 0,
            "total_value": Decimal("0"),
        },
        {
            "key": "complete",
            "label": "Complete",
            "count": 1,
            "total_value": Decimal("10.00"),
        },
    ]
    # Then 3
    assert result["open_by_account"] == [
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 1,
            "total_value": Decimal("0.00"),
        }
    ]


# [claude] EXO-SF-25
def test_exo_sf_25__five_accounts_beside_accountless_order(db, g, order):
    """EXO-SF-25 — five accounts are all listed although a larger open order has no account.
    Rules: `aggregate_financial_snapshot_filtered` R7, R8"""
    k4 = _add(db, Account(workspace_id=g.W1.id, name="Dogwood Co"))
    k5 = _add(db, Account(workspace_id=g.W1.id, name="Elm Works"))
    order("EXP-T-001", total_amount=Decimal("5.00"), account_id=g.K1.id)
    order("EXP-T-002", total_amount=Decimal("4.00"), account_id=g.K2.id)
    order("EXP-T-003", total_amount=Decimal("3.00"), account_id=g.K3.id)
    order("EXP-T-004", total_amount=Decimal("2.00"), account_id=k4.id)
    order("EXP-T-005", total_amount=Decimal("1.00"), account_id=k5.id)
    order("EXP-T-006", total_amount=Decimal("100.00"))

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert [e["account_id"] for e in result["open_by_account"]] == [
        g.K1.id,
        g.K2.id,
        g.K3.id,
        k4.id,
        k5.id,
    ]
    # Then 2
    assert [e["total_value"] for e in result["open_by_account"]] == [
        Decimal("5.00"),
        Decimal("4.00"),
        Decimal("3.00"),
        Decimal("2.00"),
        Decimal("1.00"),
    ]


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.aggregate_financial_snapshot_actionable — due timeline
# (default clock: clockD(NOWX))
# --------------------------------------------------------------------------- #


# [claude] EXO-SA-01
def test_exo_sa_01__empty_workspace(db, g, order):
    """EXO-SA-01 — an empty workspace gives four empty timeline buckets and three empty pipeline buckets.
    Rules: `aggregate_financial_snapshot_actionable` R1, R7"""
    order("EXP-T-902", k=2, due_date=TODAY)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert result["due_timeline"] == [
        {
            "key": "overdue",
            "label": "Overdue",
            "count": 0,
            "total_value": Decimal("0"),
            "samples": [],
        },
        {
            "key": "due_this_week",
            "label": "Due this week",
            "count": 0,
            "total_value": Decimal("0"),
            "samples": [],
        },
        {
            "key": "due_later_this_month",
            "label": "Due later this month",
            "count": 0,
            "total_value": Decimal("0"),
            "samples": [],
        },
        {
            "key": "no_due_date",
            "label": "No due date",
            "count": 0,
            "total_value": Decimal("0"),
            "samples": [],
        },
    ]
    # Then 2
    assert result["unpaid_pipeline"] == [
        {
            "key": "unpaid",
            "label": "Unpaid",
            "count": 0,
            "outstanding_value": Decimal("0"),
            "samples": [],
        },
        {
            "key": "partial",
            "label": "Partial",
            "count": 0,
            "outstanding_value": Decimal("0"),
            "samples": [],
        },
        {
            "key": "overdue",
            "label": "Overdue",
            "count": 0,
            "outstanding_value": Decimal("0"),
            "samples": [],
        },
    ]
    # Then 3
    assert set(result) == {"due_timeline", "unpaid_pipeline"}


def _cv(result, part, key):
    """(count, total_value) of one bucket."""
    b = bucket(result, part, key)
    return (b["count"], b["total_value"])


# [claude] EXO-SA-02
def test_exo_sa_02__every_bucket_boundary(db, g, order):
    """EXO-SA-02 — every bucket boundary on both sides; an order due next month is in none.
    Rules: `aggregate_financial_snapshot_actionable` R2; `_due_date_bucket` R1–R5"""
    order("EXP-T-001", due_date=date(2031, 11, 10), total_amount=Decimal("1.00"))
    order("EXP-T-002", due_date=date(2031, 11, 11), total_amount=Decimal("2.00"))
    order("EXP-T-003", due_date=date(2031, 11, 16), total_amount=Decimal("4.00"))
    order("EXP-T-004", due_date=date(2031, 11, 17), total_amount=Decimal("8.00"))
    order("EXP-T-005", due_date=date(2031, 11, 30), total_amount=Decimal("16.00"))
    order("EXP-T-006", due_date=date(2031, 12, 1), total_amount=Decimal("64.00"))
    order("EXP-T-007", total_amount=Decimal("32.00"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert _cv(result, "due_timeline", "overdue") == (1, Decimal("1.00"))
    # Then 2
    assert _cv(result, "due_timeline", "due_this_week") == (2, Decimal("6.00"))
    # Then 3
    assert _cv(result, "due_timeline", "due_later_this_month") == (2, Decimal("24.00"))
    # Then 4
    assert _cv(result, "due_timeline", "no_due_date") == (1, Decimal("32.00"))
    # Then 5
    assert [b["key"] for b in result["due_timeline"]] == [
        "overdue",
        "due_this_week",
        "due_later_this_month",
        "no_due_date",
    ]


# [claude] EXO-SA-03
def test_exo_sa_03__samples_first_three_by_due_then_number(db, g, order):
    """EXO-SA-03 — samples: the first three by due date, then number as text.
    Rules: `aggregate_financial_snapshot_actionable` R6"""
    sa = order("EXP-S-999", due_date=date(2031, 11, 20), total_amount=Decimal("1.00"))
    sb = order("EXP-S-500", due_date=date(2031, 11, 18), total_amount=Decimal("2.00"))
    sc = order("EXP-S-1000", due_date=date(2031, 11, 20), total_amount=Decimal("3.00"))
    order("EXP-S-100", due_date=date(2031, 11, 25), total_amount=Decimal("4.00"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_later_this_month")["count"] == 4
    # Then 2
    assert bucket(result, "due_timeline", "due_later_this_month")[
        "total_value"
    ] == Decimal("10.00")
    # Then 3
    assert bucket(result, "due_timeline", "due_later_this_month")["samples"] == [
        {
            "id": sb.id,
            "order_number": GN("EXP-S-500"),
            "total_value": Decimal("2.00"),
            "sublabel": "2031-11-18",
        },
        {
            "id": sc.id,
            "order_number": GN("EXP-S-1000"),
            "total_value": Decimal("3.00"),
            "sublabel": "2031-11-20",
        },
        {
            "id": sa.id,
            "order_number": GN("EXP-S-999"),
            "total_value": Decimal("1.00"),
            "sublabel": "2031-11-20",
        },
    ]


# [claude] EXO-SA-04
def test_exo_sa_04__no_due_date_sample_sublabel_none(db, g, order):
    """EXO-SA-04 — a no-due-date sample has sublabel None.
    Rules: `aggregate_financial_snapshot_actionable` R6"""
    oz = order("EXP-T-007", total_amount=Decimal("32.00"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "no_due_date")["samples"] == [
        {
            "id": oz.id,
            "order_number": GN("EXP-T-007"),
            "total_value": Decimal("32.00"),
            "sublabel": None,
        }
    ]


# [claude] EXO-SA-05
def test_exo_sa_05__week_into_next_month(db, g, order):
    """EXO-SA-05 — a week ending in the next month: its first days are due this week, later days in none.
    Rules: `aggregate_financial_snapshot_actionable` R2; `_due_date_bucket` R5"""
    order("EXP-T-001", due_date=date(2031, 8, 3), total_amount=Decimal("1.00"))
    order("EXP-T-002", due_date=date(2031, 8, 4), total_amount=Decimal("2.00"))

    with clockD(datetime(2031, 7, 31, 12, 0)):
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "1.00"
    )
    # Then 3
    assert bucket(result, "due_timeline", "due_later_this_month")["count"] == 0


# [claude] EXO-SA-06
def test_exo_sa_06__other_workspaces_never_count(db, g, order):
    """EXO-SA-06 — orders of W0 and W2 never count.
    Rules: `aggregate_financial_snapshot_actionable` R3"""
    order("EXP-T-900", k=0, due_date=date(2031, 11, 10), total_amount=Decimal("50.00"))
    order("EXP-T-001", due_date=date(2031, 11, 10), total_amount=Decimal("1.00"))
    order("EXP-T-902", k=2, due_date=date(2031, 11, 10), total_amount=Decimal("70.00"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "overdue")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("1.00")


# [claude] EXO-SA-07
def test_exo_sa_07__exact_sum(db, g, order):
    """EXO-SA-07 — amounts add exactly: 0.10 + 0.20 = 0.30.
    Rules: `aggregate_financial_snapshot_actionable` R5 (HR-15)"""
    order("EXP-T-001", due_date=date(2031, 11, 1), total_amount=Decimal("0.10"))
    order("EXP-T-002", due_date=date(2031, 11, 2), total_amount=Decimal("0.20"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("0.30")
    # Then 2
    assert isinstance(bucket(result, "due_timeline", "overdue")["total_value"], Decimal)


# [claude] EXO-SA-08
def test_exo_sa_08__utc_date_decides(db, g, order):
    """EXO-SA-08 — today is the UTC date: late on 10 November UTC, an order due that day is not overdue.
    Rules: `_due_window_dates` R1; `aggregate_financial_snapshot_actionable` R2"""
    dhaka(db)
    order("EXP-T-001", due_date=date(2031, 11, 10), total_amount=Decimal("1.00"))

    with clockD(datetime(2031, 11, 10, 23, 30)):
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "overdue")["count"] == 0


# [claude] EXO-SA-09
def test_exo_sa_09__filter_keyword_raises(db, g, order):
    """EXO-SA-09 — takes no filters: a filter keyword raises TypeError.
    Rules: `aggregate_financial_snapshot_actionable` Purpose (no filters)"""
    order("EXP-T-001")

    # Then 1
    with clockD():
        with pytest.raises(TypeError) as exc:
            dao.aggregate_financial_snapshot_actionable(
                db, workspace_id=g.W1.id, search="x"
            )
    assert isinstance(exc.value, TypeError)


# [claude] EXO-SA-10
def test_exo_sa_10__no_lock_writes_nothing(db, g, order):
    """EXO-SA-10 — takes no lock and writes nothing.
    Rules: `aggregate_financial_snapshot_actionable` Side effects; Overview (no lock)"""
    order("EXP-T-001", due_date=TODAY)

    with StatementRecorder(db) as rec:
        with clockD():
            result = dao.aggregate_financial_snapshot_actionable(
                db, workspace_id=g.W1.id
            )

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in s for s in rec.selects)


# [claude] EXO-SA-11
def test_exo_sa_11__partly_paid_counted_once_each(db, g, order, inv):
    """EXO-SA-11 — open orders with a partly paid confirmed or locked invoice are counted once each.
    Rules: `aggregate_financial_snapshot_actionable` R4 (count; holds before and after BUG-2719)"""
    va = inv(
        1,
        "300.00",
        "confirmed",
        payment_status="partial",
        paid_amount=Decimal("100.00"),
    )
    order(
        "EXP-T-001",
        total_amount=Decimal("300.00"),
        due_date=date(2031, 11, 12),
        invoice_id=va.id,
    )
    vb = inv(
        1, "300.00", "locked", payment_status="partial", paid_amount=Decimal("299.99")
    )
    order(
        "EXP-T-002",
        total_amount=Decimal("300.00"),
        due_date=date(2031, 11, 13),
        invoice_id=vb.id,
    )

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 2


# [claude] EXO-SA-12
def test_exo_sa_12__draft_and_voided_invoice_count_order_total(db, g, order, inv):
    """EXO-SA-12 — open orders with a draft or a voided invoice count at the order total, not the invoice amount.
    Rules: `aggregate_financial_snapshot_actionable` R4, R5 (HR-15)"""
    va = inv(1, "80.00")
    vb = inv(1, "20.00", "invvoid")
    order(
        "EXP-T-001",
        total_amount=Decimal("100.10"),
        due_date=date(2031, 11, 12),
        invoice_id=va.id,
    )
    order(
        "EXP-T-002",
        total_amount=Decimal("50.20"),
        due_date=date(2031, 11, 13),
        invoice_id=vb.id,
    )

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 2
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "150.30"
    )


# [claude] EXO-SA-13
def test_exo_sa_13__zero_order_exact_zero(db, g, order):
    """EXO-SA-13 — a 0.00 order gives exactly 0.00 in its timeline bucket and its sample.
    Rules: `aggregate_financial_snapshot_actionable` R5, R6 (HR-15)"""
    oa = order("EXP-T-001", total_amount=Decimal("0.00"), due_date=date(2031, 11, 12))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "0.00"
    )
    # Then 3
    assert bucket(result, "due_timeline", "due_this_week")["samples"] == [
        {
            "id": oa.id,
            "order_number": GN("EXP-T-001"),
            "total_value": Decimal("0.00"),
            "sublabel": "2031-11-12",
        }
    ]


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.aggregate_financial_snapshot_actionable — unpaid pipeline
# --------------------------------------------------------------------------- #


# [claude] EXO-UP-01
def test_exo_up_01__confirmed_invoices_by_payment_status(db, g, order, inv):
    """EXO-UP-01 — confirmed invoices go to the bucket of their payment status, at amount minus paid.
    Rules: `aggregate_financial_snapshot_actionable` R7, R8, R9, R11"""
    va = inv(1, "100.00", "confirmed")
    vb = inv(
        1, "50.00", "confirmed", payment_status="partial", paid_amount=Decimal("20.10")
    )
    vc = inv(
        1, "70.00", "confirmed", payment_status="overdue", paid_amount=Decimal("0.05")
    )
    oa = order("EXP-T-001", invoice_id=va.id)
    ob = order("EXP-T-002", invoice_id=vb.id)
    oc = order("EXP-T-003", invoice_id=vc.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert result["unpaid_pipeline"][0] == {
        "key": "unpaid",
        "label": "Unpaid",
        "count": 1,
        "outstanding_value": Decimal("100.00"),
        "samples": [
            {
                "id": oa.id,
                "order_number": GN("EXP-T-001"),
                "total_value": Decimal("100.00"),
                "sublabel": "unpaid",
            }
        ],
    }
    # Then 2
    assert result["unpaid_pipeline"][1] == {
        "key": "partial",
        "label": "Partial",
        "count": 1,
        "outstanding_value": Decimal("29.90"),
        "samples": [
            {
                "id": ob.id,
                "order_number": GN("EXP-T-002"),
                "total_value": Decimal("29.90"),
                "sublabel": "partial",
            }
        ],
    }
    # Then 3
    assert result["unpaid_pipeline"][2] == {
        "key": "overdue",
        "label": "Overdue",
        "count": 1,
        "outstanding_value": Decimal("69.95"),
        "samples": [
            {
                "id": oc.id,
                "order_number": GN("EXP-T-003"),
                "total_value": Decimal("69.95"),
                "sublabel": "overdue",
            }
        ],
    }


# [claude] EXO-UP-02
def test_exo_up_02__paid_invoice_in_no_bucket(db, g, order, inv):
    """EXO-UP-02 — a paid invoice puts its order in no bucket.
    Rules: `aggregate_financial_snapshot_actionable` R8"""
    va = inv(
        1, "40.00", "confirmed", payment_status="paid", paid_amount=Decimal("40.00")
    )
    order("EXP-T-001", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert [b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]


# [claude] EXO-UP-03
def test_exo_up_03__voided_invoice_in_no_bucket(db, g, order, inv):
    """EXO-UP-03 — a voided invoice puts its order in no bucket.
    Rules: `aggregate_financial_snapshot_actionable` R8"""
    va = inv(1, "40.00", "invvoid")
    order("EXP-T-001", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert [b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]


# [claude] EXO-UP-04
def test_exo_up_04__overpaid_adds_negative(db, g, order, inv):
    """EXO-UP-04 — an overpaid invoice adds a negative outstanding.
    Rules: `aggregate_financial_snapshot_actionable` R9"""
    va = inv(
        1, "10.00", "confirmed", payment_status="partial", paid_amount=Decimal("12.50")
    )
    vb = inv(
        1, "5.00", "confirmed", payment_status="partial", paid_amount=Decimal("1.00")
    )
    order("EXP-T-001", invoice_id=va.id)
    order("EXP-T-002", invoice_id=vb.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "partial")["count"] == 2
    # Then 2
    assert bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal(
        "1.50"
    )


# [claude] EXO-UP-05
def test_exo_up_05__samples_three_largest(db, g, order, inv):
    """EXO-UP-05 — samples: the three largest outstanding amounts first.
    Rules: `aggregate_financial_snapshot_actionable` R11"""
    va = inv(1, "5.00", "confirmed")
    vb = inv(1, "40.00", "confirmed")
    vc = inv(1, "20.00", "confirmed")
    vd = inv(1, "30.00", "confirmed")
    order("EXP-T-001", invoice_id=va.id)
    ob = order("EXP-T-002", invoice_id=vb.id)
    oc = order("EXP-T-003", invoice_id=vc.id)
    od = order("EXP-T-004", invoice_id=vd.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 4
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "95.00"
    )
    # Then 3
    assert [
        s["id"] for s in bucket(result, "unpaid_pipeline", "unpaid")["samples"]
    ] == [
        ob.id,
        od.id,
        oc.id,
    ]


BUG_748 = 'BUG-748: Dashboard "unpaid pipeline" samples have unordered ties'


# [claude] EXO-UP-06
@pytest.mark.xfail(strict=False, reason=BUG_748)
def test_exo_up_06__equal_outstanding_lower_id_first(db, g, order, inv):
    """EXO-UP-06 — equal outstanding amounts: the lower order id first.
    Rules: `aggregate_financial_snapshot_actionable` R11 [BUG-748]"""
    seqscan(db)
    va = inv(1, "30.00", "confirmed")
    vb = inv(1, "30.00", "confirmed")
    ob_id = order("EXP-T-002", id=high_id(db, "expense_orders"), invoice_id=vb.id).id
    oa_id = order("EXP-T-001", invoice_id=va.id).id
    w1_id = g.W1.id
    db.expire_all()

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=w1_id)

    # Then 1
    assert [
        s["id"] for s in bucket(result, "unpaid_pipeline", "unpaid")["samples"]
    ] == [
        oa_id,
        ob_id,
    ]


# [claude] EXO-UP-07
@pytest.mark.xfail(strict=True, reason=BUG_748)
def test_exo_up_07__pipeline_query_ties_by_order_id(db, g, order, inv):
    """EXO-UP-07 — the pipeline query breaks ties by order id ascending.
    Rules: `aggregate_financial_snapshot_actionable` R11 [BUG-748]"""
    va = inv(1, "30.00", "confirmed")
    order("EXP-T-001", invoice_id=va.id)

    with StatementRecorder(db) as rec:
        with clockD():
            result = dao.aggregate_financial_snapshot_actionable(
                db, workspace_id=g.W1.id
            )

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1
    # Then 2
    pipe = next(s for s in rec.selects if "account_invoices" in s)
    tail = pipe.split("ORDER BY", 1)[1].strip()
    assert tail.endswith(("expense_orders.id", "expense_orders.id ASC"))


# [claude] EXO-UP-08, UP-09
@pytest.mark.xfail(strict=True, reason=BUG_2714)
@pytest.mark.parametrize(
    "k", [pytest.param(0, id="EXO-UP-08"), pytest.param(2, id="EXO-UP-09")]
)
def test_exo_up_08_09__foreign_invoice_left_out(db, g, order, inv, k):
    """EXO-UP-08, UP-09 — a W1 order linked to W0's / W2's invoice is left out of the pipeline.
    Rules: `aggregate_financial_snapshot_actionable` R10 [BUG-2714] (HR-16)"""
    vx = inv(
        k, "80.00", "confirmed", payment_status="partial", paid_amount=Decimal("30.00")
    )
    order("EXP-T-001", invoice_id=vx.id)  # invalid data: another workspace's invoice

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "partial")["count"] == 0
    # Then 2
    assert bucket(result, "unpaid_pipeline", "partial")["samples"] == []


# [claude] EXO-UP-10
def test_exo_up_10__shared_invoice_counted_per_order(db, g, order, inv):
    """EXO-UP-10 — two orders sharing one invoice each count its full outstanding.
    Rules: `aggregate_financial_snapshot_actionable` R12"""
    va = inv(1, "30.00", "confirmed")
    order("EXP-T-001", invoice_id=va.id)
    order("EXP-T-002", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 2
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "60.00"
    )


# [claude] EXO-UP-11
def test_exo_up_11__other_workspaces_do_not_count(db, g, order, inv):
    """EXO-UP-11 — W0's and W2's own orders and invoices do not count for W1.
    Rules: `aggregate_financial_snapshot_actionable` R8 (of this workspace)"""
    v0 = inv(0, "10.00", "confirmed")
    order("EXP-T-900", k=0, invoice_id=v0.id)
    va = inv(1, "1.00", "confirmed")
    order("EXP-T-001", invoice_id=va.id)
    v9 = inv(2, "20.00", "confirmed")
    order("EXP-T-902", k=2, invoice_id=v9.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "1.00"
    )


# [claude] EXO-UP-12
def test_exo_up_12__locked_partial_open_order(db, g, order, inv):
    """EXO-UP-12 — an open order with a locked partial invoice is in Partial at amount minus paid.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9"""
    va = inv(
        1, "100.00", "locked", payment_status="partial", paid_amount=Decimal("40.00")
    )
    order("EXP-T-001", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "partial")["count"] == 1
    # Then 2
    assert bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal(
        "60.00"
    )


# [claude] EXO-UP-13
def test_exo_up_13__zero_invoice_exact_zero(db, g, order, inv):
    """EXO-UP-13 — a confirmed 0.00 invoice with nothing paid gives exactly 0.00 outstanding.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9, R11 (HR-15)"""
    va = inv(1, "0.00", "confirmed")
    oa = order("EXP-T-001", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "0.00"
    )
    # Then 3
    assert bucket(result, "unpaid_pipeline", "unpaid")["samples"] == [
        {
            "id": oa.id,
            "order_number": GN("EXP-T-001"),
            "total_value": Decimal("0.00"),
            "sublabel": "unpaid",
        }
    ]


# [claude] EXO-UP-14
def test_exo_up_14__samples_by_what_is_owed(db, g, order, inv):
    """EXO-UP-14 — samples are ordered by what is still owed, not by the invoice amount.
    Rules: `aggregate_financial_snapshot_actionable` R9, R11"""
    va = inv(
        1, "100.00", "confirmed", payment_status="partial", paid_amount=Decimal("90.00")
    )
    vb = inv(
        1, "50.00", "confirmed", payment_status="partial", paid_amount=Decimal("10.00")
    )
    oa = order("EXP-T-001", invoice_id=va.id)
    ob = order("EXP-T-002", invoice_id=vb.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal(
        "50.00"
    )
    # Then 2
    assert [
        s["id"] for s in bucket(result, "unpaid_pipeline", "partial")["samples"]
    ] == [
        ob.id,
        oa.id,
    ]
    # Then 3
    assert [
        s["total_value"]
        for s in bucket(result, "unpaid_pipeline", "partial")["samples"]
    ] == [
        Decimal("40.00"),
        Decimal("10.00"),
    ]


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] EXO-GI-01
def test_exo_gi_01__returns_middle_of_three(db, g, order):
    """EXO-GI-01 — returns the order of this workspace, the middle of three.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R1"""
    order("EXP-T-001")
    o2 = order("EXP-T-002")
    order("EXP-T-003")

    result = dao.get_by_id_and_workspace(db, id=o2.id, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, ExpenseOrder)
    # Then 2
    assert result.id == o2.id
    # Then 3
    assert result.expense_number == GN("EXP-T-002")


# [claude] EXO-GI-02
def test_exo_gi_02__w0_order_for_w1_is_none(db, g, order):
    """EXO-GI-02 — W0's order asked for W1 is None.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R1"""
    x0 = order("EXP-T-900", k=0)
    order("EXP-T-001")

    result = dao.get_by_id_and_workspace(db, id=x0.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-GI-03
def test_exo_gi_03__w2_order_for_w1_is_none(db, g, order):
    """EXO-GI-03 — W2's order asked for W1 is None.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R1"""
    order("EXP-T-001")
    x2 = order("EXP-T-902", k=2)

    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-GI-04
def test_exo_gi_04__completed_and_voided_returned(db, g, order):
    """EXO-GI-04 — a completed and voided order is still returned.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R1"""
    o1 = order("EXP-T-001", completed=True, voided=True)

    result = dao.get_by_id_and_workspace(db, id=o1.id, workspace_id=g.W1.id)

    # Then 1
    assert result.id == o1.id


# [claude] EXO-GI-05
def test_exo_gi_05__unknown_id_is_none(db, g, order):
    """EXO-GI-05 — an unknown id is None.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R1"""
    order("EXP-T-001")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-GI-06
def test_exo_gi_06__positional_arguments(db, g, order):
    """EXO-GI-06 — positional arguments raise TypeError.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` R2"""
    o1 = order("EXP-T-001")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_id_and_workspace(db, o1.id, g.W1.id)
    assert isinstance(exc.value, TypeError)


# [claude] EXO-GI-07
def test_exo_gi_07__one_select_no_lock(db, g, order):
    """EXO-GI-07 — one SELECT, no lock.
    Rules: `ExpenseOrderDAO.get_by_id_and_workspace` Side effects; Overview (no lock)"""
    o1 = order("EXP-T-001")
    o1_id, w1_id = o1.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace(db, id=o1_id, workspace_id=w1_id)

    # Then 1
    assert result.id == o1_id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# --------------------------------------------------------------------------- #
# ExpenseOrderDAO.get_next_number (exact numbers; default clock clockN(JUNE, JUNE))
# --------------------------------------------------------------------------- #


# [claude] EXO-NX-01
def test_exo_nx_01__no_number_yet(db, g):
    """EXO-NX-01 — no number yet gives EXP-2031-001.
    Rules: `get_next_number` R1, R2"""
    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "EXP-2031-001"


# [claude] EXO-NX-02 … NX-06, NX-08
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        pytest.param(["EXP-2031-002"], "EXP-2031-003", id="EXO-NX-02"),
        pytest.param(
            ["EXP-2031-009", "EXP-2031-001", "EXP-2031-002"],
            "EXP-2031-010",
            id="EXO-NX-03",
        ),
        pytest.param(["EXP-2031-998"], "EXP-2031-999", id="EXO-NX-04"),
        pytest.param(["EXP-2031-999"], "EXP-2031-1000", id="EXO-NX-05"),
        pytest.param(["EXP-2031-1000"], "EXP-2031-1001", id="EXO-NX-06"),
        pytest.param(["EXP-2031-abc"], "EXP-2031-001", id="EXO-NX-08"),
    ],
)
def test_exo_nx_02_08__next_after_stored(db, g, numbered, stored, expected):
    """EXO-NX-02 … NX-06, NX-08 — the highest stored number plus one, not cut to three digits; a non-numeric suffix alone gives 001.
    Rules: `get_next_number` R3"""
    for number in stored:
        numbered(number)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == expected


BUG_749 = (
    "BUG-749: Expense-number generation is globally unique, text-sorted, and race-prone"
)


# [claude] EXO-NX-07, NX-09
@pytest.mark.xfail(strict=True, reason=BUG_749)
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        pytest.param(
            ["EXP-2031-999", "EXP-2031-1000"], "EXP-2031-1001", id="EXO-NX-07"
        ),
        pytest.param(["EXP-2031-004", "EXP-2031-abc"], "EXP-2031-005", id="EXO-NX-09"),
    ],
)
def test_exo_nx_07_09__numeric_maximum(db, g, numbered, stored, expected):
    """EXO-NX-07, NX-09 — the numeric maximum decides (999 and 1000 → 1001); a non-numeric suffix beside 004 is ignored (005).
    Rules: `get_next_number` R3 [BUG-749]"""
    for number in stored:
        numbered(number)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == expected


# [claude] EXO-NX-10, NX-11, NX-12
@pytest.mark.parametrize(
    ("numbers", "asked", "expected"),
    [
        pytest.param(
            ("EXP-2031-050", "EXP-2031-003", "EXP-2031-070"),
            1,
            "EXP-2031-004",
            id="EXO-NX-10",
        ),
        pytest.param(
            ("EXP-2031-090", "EXP-2031-080", "EXP-2031-070"),
            2,
            "EXP-2031-071",
            id="EXO-NX-11",
        ),
        pytest.param(
            ("EXP-2031-050", "EXP-2031-080", "EXP-2031-090"),
            0,
            "EXP-2031-051",
            id="EXO-NX-12",
        ),
    ],
)
def test_exo_nx_10_12__only_asked_workspace_counts(
    db, g, numbered, numbers, asked, expected
):
    """EXO-NX-10 … NX-12 — X0 of W0, O1 of W1, X2 of W2: only the asked workspace's numbers count.
    Rules: `get_next_number` R2"""
    numbered(numbers[0], k=0)
    numbered(numbers[1])
    numbered(numbers[2], k=2)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=getattr(g, f"W{asked}").id)

    # Then 1
    assert result == expected


# [claude] EXO-NX-13
def test_exo_nx_13__unknown_workspace(db, g, numbered):
    """EXO-NX-13 — an unknown workspace gets 001.
    Rules: `get_next_number` R2"""
    numbered("EXP-2031-005")

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=MISSING)

    # Then 1
    assert result == "EXP-2031-001"


# [claude] EXO-NX-14 … NX-18
@pytest.mark.parametrize(
    "stored",
    [
        pytest.param(["EXP-2030-500", "EXP-2032-600"], id="EXO-NX-14"),
        pytest.param(["exp-2031-005"], id="EXO-NX-15"),
        pytest.param([" EXP-2031-005"], id="EXO-NX-16"),
        pytest.param(["XEXP-2031-005"], id="EXO-NX-17"),
        pytest.param(["EXP-20311-005"], id="EXO-NX-18"),
    ],
)
def test_exo_nx_14_18__other_prefixes_do_not_count(db, g, numbered, stored):
    """EXO-NX-14 … NX-18 — other years, a lowercase prefix, a leading space, the prefix mid-number and a longer year do not count.
    Rules: `get_next_number` R2"""
    for number in stored:
        numbered(number)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2031-001"


# [claude] EXO-NX-19
def test_exo_nx_19__voided_and_completed_counted(db, g, numbered):
    """EXO-NX-19 — voided and completed orders keep their numbers counted.
    Rules: `get_next_number` R3"""
    numbered("EXP-2031-006", completed=True)
    numbered("EXP-2031-007", voided=True)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2031-008"


# [claude] EXO-NX-20
def test_exo_nx_20__year_from_clock(db, g, numbered):
    """EXO-NX-20 — the year comes from the clock: both clocks in 2032, last year's numbers ignored.
    Rules: `get_next_number` R1, R2"""
    numbered("EXP-2031-005")

    with clockN(datetime(2032, 3, 1, 12, 0), datetime(2032, 3, 1, 12, 0)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2032-001"


BUG_2710 = "BUG-2710: An expense number's year comes from the server's local clock"


# [claude] EXO-NX-21
@pytest.mark.xfail(strict=True, reason=BUG_2710)
def test_exo_nx_21__utc_year_local_already_next_year(db, g, numbered):
    """EXO-NX-21 — the year is UTC's when the local clock is already in the next year.
    Rules: `get_next_number` R1 [BUG-2710]"""
    numbered("EXP-2031-005")

    with clockN(datetime(2032, 1, 1, 5, 0), datetime(2031, 12, 31, 23, 0)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2031-006"


# [claude] EXO-NX-22
@pytest.mark.xfail(strict=True, reason=BUG_2710)
def test_exo_nx_22__utc_year_local_still_old_year(db, g, numbered):
    """EXO-NX-22 — the year is UTC's when the local clock is still in the old year.
    Rules: `get_next_number` R1 [BUG-2710]"""
    numbered("EXP-2031-005")

    with clockN(datetime(2031, 12, 31, 23, 0), datetime(2032, 1, 1, 1, 0)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2032-001"


# [claude] EXO-NX-23
def test_exo_nx_23__pending_order_not_counted(db, g, numbered):
    """EXO-NX-23 — writes nothing: a pending order is not counted and stays pending.
    Rules: `get_next_number` R4, Side effects"""
    o1 = numbered("EXP-2031-002")
    o1.description = "Edited"
    p = ExpenseOrder(
        workspace_id=g.W1.id,
        expense_number="EXP-2031-009",
        expense_category="factory",
        expense_date=D2,
        subtotal=Decimal("0.00"),
        total_amount=Decimal("10.00"),
        created_by=g.U1.id,
    )
    db.add(p)

    with StatementRecorder(db) as rec:
        with clockN(JUNE, JUNE):
            result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "EXP-2031-003"
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert o1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []


# [claude] EXO-NX-24
def test_exo_nx_24__no_row_lock(db, g, numbered):
    """EXO-NX-24 — reads with no row lock.
    Rules: `get_next_number` R4 [BUG-749] (no lock — the part that holds today)"""
    numbered("EXP-2031-002")
    w1_id = g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        with clockN(JUNE, JUNE):
            result = dao.get_next_number(db, workspace_id=w1_id)

    # Then 1
    assert result == "EXP-2031-003"
    # Then 2
    assert "FOR UPDATE" not in rec.sql


# [claude] EXO-NX-25
def test_exo_nx_25__positional_arguments(db, g):
    """EXO-NX-25 — positional arguments raise TypeError.
    Rules: `get_next_number` R5"""
    # Then 1
    with clockN(JUNE, JUNE):
        with pytest.raises(TypeError) as exc:
            dao.get_next_number(db, g.W1.id)
    assert isinstance(exc.value, TypeError)


# [claude] EXO-NX-26
def test_exo_nx_26__same_number_same_workspace_refused(db, g, numbered):
    """EXO-NX-26 — the same number twice in one workspace is refused by the database.
    Rules: `get_next_number` R4a (`uq_eo_workspace_number`)"""
    numbered("EXP-2031-001")

    # Then 1
    with clockN(JUNE, JUNE):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                db.add(
                    ExpenseOrder(
                        workspace_id=g.W1.id,
                        expense_number="EXP-2031-001",
                        expense_category="factory",
                        expense_date=D2,
                        subtotal=Decimal("0.00"),
                        total_amount=Decimal("10.00"),
                        created_by=g.U1.id,
                    )
                )
                db.flush()
    assert exc.value.orig.pgcode == "23505"


# [claude] EXO-NX-27
@pytest.mark.xfail(strict=True, reason=BUG_749)
def test_exo_nx_27__same_number_other_workspace_accepted(db, g, numbered):
    """EXO-NX-27 — the same number in another workspace is accepted.
    Rules: `get_next_number` R4a [BUG-749] (per-workspace uniqueness)"""
    numbered("EXP-2031-001")

    x2 = ExpenseOrder(
        workspace_id=g.W2.id,
        expense_number="EXP-2031-001",
        expense_category="factory",
        expense_date=D2,
        subtotal=Decimal("0.00"),
        total_amount=Decimal("10.00"),
        created_by=g.U1.id,
    )
    with clockN(JUNE, JUNE):
        with db.begin_nested():
            db.add(x2)
            db.flush()

    # Then 1
    assert x2.id is not None
    # Then 2
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM expense_orders WHERE expense_number = 'EXP-2031-001'"
            )
        )
        == 2
    )


# --------------------------------------------------------------------------- #
# ExpenseOrderItemDAO.get_by_order
# --------------------------------------------------------------------------- #


# [claude] EXO-GO-01
def test_exo_go_01__by_line_number_ascending(db, g, order, line):
    """EXO-GO-01 — lines by line number ascending, inserted out of order.
    Rules: `get_by_order` R1, R2"""
    o1 = order("EXP-T-001")
    l3 = line(o1, 3)
    l1 = line(o1, 1)
    l2 = line(o1, 2)

    result = idao.get_by_order(db, expense_order_id=o1.id, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [l1.id, l2.id, l3.id]


# [claude] EXO-GO-02
def test_exo_go_02__only_asked_order(db, g, order, line):
    """EXO-GO-02 — only the asked order's lines, with lower and higher orders around it.
    Rules: `get_by_order` R1"""
    o1 = order("EXP-T-001")
    o2 = order("EXP-T-002")
    o3 = order("EXP-T-003")
    line(o1, 1)
    lb = line(o2, 1)
    line(o3, 1)

    result = idao.get_by_order(db, expense_order_id=o2.id, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [lb.id]


# [claude] EXO-GO-03, GO-04
@pytest.mark.parametrize(
    "k", [pytest.param(0, id="EXO-GO-03"), pytest.param(2, id="EXO-GO-04")]
)
def test_exo_go_03_04__line_of_other_workspace_left_out(db, g, order, line, k):
    """EXO-GO-03, GO-04 — a line stored with W0's / W2's workspace_id is left out.
    Rules: `get_by_order` R1"""
    o1 = order("EXP-T-001")
    la = line(o1, 1)
    line(o1, 2, workspace_id=getattr(g, f"W{k}").id)  # invalid data

    result = idao.get_by_order(db, expense_order_id=o1.id, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [la.id]


# [claude] EXO-GO-05
def test_exo_go_05__w1_order_asked_for_w2(db, g, order, line):
    """EXO-GO-05 — W1's order asked for W2 gives [].
    Rules: `get_by_order` R1"""
    o1 = order("EXP-T-001")
    line(o1, 1)

    result = idao.get_by_order(db, expense_order_id=o1.id, workspace_id=g.W2.id)

    # Then 1
    assert result == []


# [claude] EXO-GO-06
def test_exo_go_06__unknown_order(db, g, order, line):
    """EXO-GO-06 — an unknown order gives [].
    Rules: `get_by_order` R1"""
    o1 = order("EXP-T-001")
    line(o1, 1)

    result = idao.get_by_order(db, expense_order_id=MISSING, workspace_id=g.W1.id)

    # Then 1
    assert result == []


BUG_2713 = "BUG-2713: Expense lines with one line number have no order"


# [claude] EXO-GO-07
@pytest.mark.xfail(strict=False, reason=BUG_2713)
def test_exo_go_07__equal_line_numbers_lower_id_first(db, g, order, line):
    """EXO-GO-07 — equal line numbers: the lower id first.
    Rules: `get_by_order` R2 [BUG-2713]"""
    seqscan(db)
    o1 = order("EXP-T-001")
    lh_id = line(o1, 3, id=high_id(db, "expense_order_items")).id
    ll_id = line(o1, 3).id
    o1_id, w1_id = o1.id, g.W1.id
    db.expire_all()

    result = idao.get_by_order(db, expense_order_id=o1_id, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [ll_id, lh_id]


# [claude] EXO-GO-08
@pytest.mark.xfail(strict=True, reason=BUG_2713)
def test_exo_go_08__orders_by_line_number_then_id(db, g, order, line):
    """EXO-GO-08 — the query orders by line number, then id.
    Rules: `get_by_order` R2 [BUG-2713]"""
    o1 = order("EXP-T-001")
    la = line(o1, 1)

    with StatementRecorder(db, "expense_order_items") as rec:
        result = idao.get_by_order(db, expense_order_id=o1.id, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [la.id]
    # Then 2
    assert "expense_order_items.line_number" in rec.order_part
    # Then 3
    assert "expense_order_items.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()


# [claude] EXO-GO-09
def test_exo_go_09__line_money_rounded_half_up(db, g, order, line):
    """EXO-GO-09 — line money comes back as stored, rounded half up.
    Rules: `get_by_order` R1 (HR-15, `Numeric(15, 2)`)"""
    o1 = order("EXP-T-001")
    line(o1, 1, unit_price=Decimal("2.125"), line_subtotal=Decimal("0.005"))
    line(o1, 2, unit_price=Decimal("-1.005"), line_subtotal=Decimal("2.124"))
    o1_id, w1_id = o1.id, g.W1.id
    db.expunge_all()

    result = idao.get_by_order(db, expense_order_id=o1_id, workspace_id=w1_id)

    # Then 1
    assert result[0].unit_price == Decimal("2.13")
    # Then 2
    assert result[0].line_subtotal == Decimal("0.01")
    # Then 3
    assert result[1].unit_price == Decimal("-1.01")
    # Then 4
    assert result[1].line_subtotal == Decimal("2.12")


# [claude] EXO-GO-10
def test_exo_go_10__one_select_no_lock_no_join(db, g, order, line):
    """EXO-GO-10 — one SELECT, no lock, no parent join.
    Rules: `get_by_order` Side effects; Overview (no lock)"""
    o1 = order("EXP-T-001")
    la_id = line(o1, 1).id
    o1_id, w1_id = o1.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db, "expense_order_items") as rec:
        result = idao.get_by_order(db, expense_order_id=o1_id, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [la_id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert "JOIN" not in rec.sql.upper()


# --------------------------------------------------------------------------- #
# ExpenseOrderItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] EXO-II-01
def test_exo_ii_01__returns_middle_line(db, g, order, line):
    """EXO-II-01 — returns the line of this workspace, the middle of three.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R1"""
    o1 = order("EXP-T-001")
    line(o1, 1)
    lb = line(o1, 2)
    line(o1, 3)

    result = idao.get_by_id_and_workspace(db, id=lb.id, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, ExpenseOrderItem)
    # Then 2
    assert result.id == lb.id


# [claude] EXO-II-02
def test_exo_ii_02__w0_line_for_w1_is_none(db, g, order, line):
    """EXO-II-02 — a line of W0 asked for W1 is None.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R1"""
    x0 = order("EXP-T-900", k=0)
    lx = line(x0, 1, workspace_id=g.W0.id)
    o1 = order("EXP-T-001")
    line(o1, 1)

    result = idao.get_by_id_and_workspace(db, id=lx.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-II-03
def test_exo_ii_03__w2_line_for_w1_is_none(db, g, order, line):
    """EXO-II-03 — a line of W2 asked for W1 is None.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R1"""
    o1 = order("EXP-T-001")
    line(o1, 1)
    x2 = order("EXP-T-902", k=2)
    lx = line(x2, 1, workspace_id=g.W2.id)

    result = idao.get_by_id_and_workspace(db, id=lx.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-II-04
def test_exo_ii_04__unknown_id_is_none(db, g, order, line):
    """EXO-II-04 — an unknown id is None.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R1"""
    o1 = order("EXP-T-001")
    line(o1, 1)

    result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] EXO-II-05
def test_exo_ii_05__positional_arguments(db, g, order, line):
    """EXO-II-05 — positional arguments raise TypeError.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R2"""
    o1 = order("EXP-T-001")
    la = line(o1, 1)

    # Then 1
    with pytest.raises(TypeError) as exc:
        idao.get_by_id_and_workspace(db, la.id, g.W1.id)
    assert isinstance(exc.value, TypeError)


# [claude] EXO-II-06
def test_exo_ii_06__one_select_no_lock_parent_not_read(db, g, order, line):
    """EXO-II-06 — one SELECT, no lock, the parent order not read.
    Rules: `ExpenseOrderItemDAO.get_by_id_and_workspace` R1 (parent not looked at); Overview (no lock)"""
    o1 = order("EXP-T-001")
    la_id = line(o1, 1).id
    w1_id = g.W1.id
    db.expunge_all()

    with StatementRecorder(db, "expense_order_items") as rec:
        result = idao.get_by_id_and_workspace(db, id=la_id, workspace_id=w1_id)

    # Then 1
    assert result.id == la_id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert "expense_orders." not in rec.sql


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-42 → BUG-2717
# --------------------------------------------------------------------------- #

BUG_2717 = "BUG-2717: Expense hub money figures count voided orders"


# [claude] EXO-OQ42-01
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_01__stats_leave_voided_out_of_money(db, g, order):
    """EXO-OQ42-01 — stats leave a voided order out of total value and open, but count it in total and not invoiced.
    Rules: `aggregate_hub_stats` R1, R2, R3 [BUG-2717]"""
    order("EXP-T-001", total_amount=Decimal("100.00"))
    order("EXP-T-002", total_amount=Decimal("50.00"))
    order("EXP-T-003", total_amount=Decimal("30.00"), voided=True)

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result[0] == 3
    # Then 2
    assert result[4] == 3
    # Then 3
    assert result[1] == Decimal("150.00")
    # Then 4
    assert result[2] == 2
    # Then 5
    assert result[3] == Decimal("150.00")


# [claude] EXO-OQ42-02
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_02__voided_invoiced_not_open(db, g, order, inv):
    """EXO-OQ42-02 — a voided invoiced order is not open and adds no value.
    Rules: `aggregate_hub_stats` R1, R2, R3 [BUG-2717]"""
    v1 = inv(1, "30.00")
    order("EXP-T-001", total_amount=Decimal("100.00"))
    order("EXP-T-003", total_amount=Decimal("30.00"), voided=True, invoice_id=v1.id)

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result[0] == 2
    # Then 2
    assert result[4] == 1
    # Then 3
    assert result[1] == Decimal("100.00")
    # Then 4
    assert result[2] == 1
    # Then 5
    assert result[3] == Decimal("100.00")


# [claude] EXO-OQ42-03
def test_exo_oq42_03__exclude_voided_true_leaves_voided_out(db, g, order):
    """EXO-OQ42-03 — with exclude_voided true, stats leave the voided order out.
    Rules: `aggregate_hub_stats` R3a; `_apply_expense_order_hub_filters` R8"""
    order("EXP-T-001", total_amount=Decimal("100.00"))
    order("EXP-T-002", total_amount=Decimal("50.00"))
    order("EXP-T-003", total_amount=Decimal("30.00"), voided=True)

    result = dao.aggregate_hub_stats(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=True
    )

    # Then 1
    assert result == (2, Decimal("150.00"), 2, Decimal("150.00"), 2)


# [claude] EXO-OQ42-04
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_04__category_leaves_voided_out(db, g, order):
    """EXO-OQ42-04 — the category breakdown leaves a voided order out of its category.
    Rules: `aggregate_financial_snapshot_filtered` R1 [BUG-2717]"""
    order("EXP-T-001", total_amount=Decimal("10.00"))
    order("EXP-T-002", total_amount=Decimal("5.00"), voided=True)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 1,
            "total_value": Decimal("10.00"),
        }
    ]


# [claude] EXO-OQ42-05
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_05__stage_pipeline_no_voided(db, g, order, inv):
    """EXO-OQ42-05 — the stage pipeline counts no voided order in any stage.
    Rules: `aggregate_financial_snapshot_filtered` R5 [BUG-2717]; `_expense_order_stage_key_expr` R1"""
    v1 = inv(1, "2.00")
    order("EXP-T-001", total_amount=Decimal("1.00"), voided=True)
    order("EXP-T-002", total_amount=Decimal("2.00"), voided=True, invoice_id=v1.id)
    order("EXP-T-003", total_amount=Decimal("4.00"), voided=True, completed=True)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["stage_pipeline"] == [
        {"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")},
        {
            "key": "invoiced",
            "label": "Invoiced",
            "count": 0,
            "total_value": Decimal("0"),
        },
        {
            "key": "complete",
            "label": "Complete",
            "count": 0,
            "total_value": Decimal("0"),
        },
    ]


# [claude] EXO-OQ42-06
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_06__open_by_account_leaves_voided_out(db, g, order):
    """EXO-OQ42-06 — open by account leaves a voided order of the account out.
    Rules: `aggregate_financial_snapshot_filtered` R6a [BUG-2717]"""
    order("EXP-T-001", total_amount=Decimal("10.00"), account_id=g.K1.id)
    order("EXP-T-002", total_amount=Decimal("5.00"), account_id=g.K1.id, voided=True)

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["open_by_account"] == [
        {
            "account_id": g.K1.id,
            "account_name": "Alder Supplies",
            "count": 1,
            "total_value": Decimal("10.00"),
        }
    ]


# [claude] EXO-OQ42-07
@pytest.mark.xfail(strict=True, reason=BUG_2717)
def test_exo_oq42_07__category_of_only_voided_has_no_entry(db, g, order):
    """EXO-OQ42-07 — a category with only voided orders has no entry.
    Rules: `aggregate_financial_snapshot_filtered` R1 [BUG-2717]"""
    order("EXP-T-001", total_amount=Decimal("10.00"))
    order(
        "EXP-T-002",
        total_amount=Decimal("7.00"),
        expense_category="department",
        voided=True,
    )

    result = dao.aggregate_financial_snapshot_filtered(
        db, workspace_id=g.W1.id, exclude_complete=False, exclude_voided=False
    )

    # Then 1
    assert result["category_breakdown"] == [
        {
            "key": "factory",
            "label": "Factory",
            "count": 1,
            "total_value": Decimal("10.00"),
        }
    ]


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-43 → BUG-2718 (default clock clockD(NOWX))
# --------------------------------------------------------------------------- #

BUG_2718 = (
    'BUG-2718: Expense "unpaid pipeline" shows only draft invoices, never payable bills'
)


# [claude] EXO-OQ43-01
@pytest.mark.xfail(strict=True, reason=BUG_2718)
def test_exo_oq43_01__draft_invoice_not_in_pipeline(db, g, order, inv):
    """EXO-OQ43-01 — a draft invoice is not in the pipeline.
    Rules: `aggregate_financial_snapshot_actionable` R8 [BUG-2718]"""
    va = inv(1, "100.00")
    order("EXP-T-001", invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 0
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "0"
    )
    # Then 3
    assert bucket(result, "unpaid_pipeline", "unpaid")["samples"] == []


# [claude] EXO-OQ43-02
@pytest.mark.xfail(strict=True, reason=BUG_2718)
def test_exo_oq43_02__completed_order_still_owed_in_partial(db, g, order, inv):
    """EXO-OQ43-02 — a completed order with 60.00 still owed is in Partial.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9, R11 [BUG-2718]"""
    va = inv(
        1, "100.00", "confirmed", payment_status="partial", paid_amount=Decimal("40.00")
    )
    oa = order("EXP-T-001", completed=True, invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert result["unpaid_pipeline"][1] == {
        "key": "partial",
        "label": "Partial",
        "count": 1,
        "outstanding_value": Decimal("60.00"),
        "samples": [
            {
                "id": oa.id,
                "order_number": GN("EXP-T-001"),
                "total_value": Decimal("60.00"),
                "sublabel": "partial",
            }
        ],
    }


# [claude] EXO-OQ43-03
@pytest.mark.xfail(strict=True, reason=BUG_2718)
def test_exo_oq43_03__completed_unpaid_confirmed_adds(db, g, order, inv):
    """EXO-OQ43-03 — a completed order with an unpaid confirmed invoice adds to Unpaid.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]"""
    va = inv(1, "100.00", "confirmed")
    order("EXP-T-001", completed=True, invoice_id=va.id)
    vb = inv(1, "7.00", "confirmed")
    order("EXP-T-002", invoice_id=vb.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 2
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "107.00"
    )


# [claude] EXO-OQ43-04
def test_exo_oq43_04__voided_order_left_out(db, g, order, inv):
    """EXO-OQ43-04 — a voided order with a confirmed partial invoice is left out.
    Rules: `aggregate_financial_snapshot_actionable` R8"""
    va = inv(
        1, "50.00", "confirmed", payment_status="partial", paid_amount=Decimal("10.00")
    )
    order("EXP-T-001", voided=True, invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert [b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]


# [claude] EXO-OQ43-05
@pytest.mark.xfail(strict=True, reason=BUG_2718)
def test_exo_oq43_05__draft_beside_confirmed_adds_nothing(db, g, order, inv):
    """EXO-OQ43-05 — beside a confirmed 0.20, a draft 0.10 adds nothing.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]"""
    va = inv(1, "0.10")
    vb = inv(1, "0.20", "confirmed")
    order("EXP-T-001", invoice_id=va.id)
    order("EXP-T-002", invoice_id=vb.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1
    # Then 2
    assert bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal(
        "0.20"
    )


# [claude] EXO-OQ43-06
@pytest.mark.xfail(strict=True, reason=BUG_2718)
def test_exo_oq43_06__completed_locked_partial_in_partial(db, g, order, inv):
    """EXO-OQ43-06 — a completed order with a locked partial invoice is in Partial.
    Rules: `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]"""
    va = inv(
        1, "100.00", "locked", payment_status="partial", paid_amount=Decimal("40.00")
    )
    order("EXP-T-001", completed=True, invoice_id=va.id)

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "unpaid_pipeline", "partial")["count"] == 1
    # Then 2
    assert bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal(
        "60.00"
    )


# --------------------------------------------------------------------------- #
# Answered by the owner — OQ-44 → BUG-2719 (default clock clockD(NOWX))
# --------------------------------------------------------------------------- #

BUG_2719 = (
    "BUG-2719: Expense due timeline drops completed orders and ignores what is paid"
)


# [claude] EXO-OQ44-01
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_01__completed_due_yesterday_overdue(db, g, order, inv):
    """EXO-OQ44-01 — a completed order due yesterday, nothing paid, is overdue.
    Rules: `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]"""
    va = inv(1, "500.00", "confirmed")
    order(
        "EXP-T-001",
        total_amount=Decimal("500.00"),
        due_date=date(2031, 11, 10),
        completed=True,
        invoice_id=va.id,
    )

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "overdue")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("500.00")


# [claude] EXO-OQ44-02
def test_exo_oq44_02__voided_due_tomorrow_not_counted(db, g, order):
    """EXO-OQ44-02 — a voided order due tomorrow is not due this week.
    Rules: `aggregate_financial_snapshot_actionable` R4"""
    order(
        "EXP-T-001",
        total_amount=Decimal("300.00"),
        due_date=date(2031, 11, 12),
        voided=True,
    )
    order("EXP-T-002", total_amount=Decimal("1.00"), due_date=date(2031, 11, 12))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "1.00"
    )


def _partly_paid(order, inv, state, status, paid):
    """The OQ44-03 … 09 Given: VA = inv(W1, "300.00"), but <state>, status, paid; OA due 2031-11-12."""
    va = inv(1, "300.00", state, payment_status=status, paid_amount=Decimal(paid))
    return order(
        "EXP-T-001",
        total_amount=Decimal("300.00"),
        due_date=date(2031, 11, 12),
        invoice_id=va.id,
    )


# [claude] EXO-OQ44-03
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_03__partly_paid_counts_what_is_left(db, g, order, inv):
    """EXO-OQ44-03 — a partly paid confirmed invoice: the timeline counts what is still to pay.
    Rules: `aggregate_financial_snapshot_actionable` R5 [BUG-2719]"""
    _partly_paid(order, inv, "confirmed", "partial", "100.00")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "200.00"
    )


# [claude] EXO-OQ44-04
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_04__sample_shows_what_is_left(db, g, order, inv):
    """EXO-OQ44-04 — the sample of a partly paid order shows what is still to pay.
    Rules: `aggregate_financial_snapshot_actionable` R6 [BUG-2719]"""
    oa = _partly_paid(order, inv, "confirmed", "partial", "100.00")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["samples"] == [
        {
            "id": oa.id,
            "order_number": GN("EXP-T-001"),
            "total_value": Decimal("200.00"),
            "sublabel": "2031-11-12",
        }
    ]


# [claude] EXO-OQ44-05
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_05__completed_no_invoice_no_due_date(db, g, order):
    """EXO-OQ44-05 — a completed order with no invoice and no due date is in No due date.
    Rules: `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]"""
    order("EXP-T-001", total_amount=Decimal("40.00"), completed=True)
    order("EXP-T-002", total_amount=Decimal("2.00"))

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "no_due_date")["count"] == 2
    # Then 2
    assert bucket(result, "due_timeline", "no_due_date")["total_value"] == Decimal(
        "42.00"
    )


# [claude] EXO-OQ44-06
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_06__paid_invoice_in_no_bucket(db, g, order, inv):
    """EXO-OQ44-06 — an open order whose invoice is paid is in no bucket.
    Rules: `aggregate_financial_snapshot_actionable` R4 [BUG-2719]"""
    _partly_paid(order, inv, "confirmed", "paid", "300.00")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 0
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "0"
    )


# [claude] EXO-OQ44-07
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_07__nothing_left_partial_in_no_bucket(db, g, order, inv):
    """EXO-OQ44-07 — nothing left to pay (0.00) with status partial is in no bucket.
    Rules: `aggregate_financial_snapshot_actionable` R4 [BUG-2719]"""
    _partly_paid(order, inv, "confirmed", "partial", "300.00")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 0


# [claude] EXO-OQ44-08
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_08__one_cent_left_counts_one_cent(db, g, order, inv):
    """EXO-OQ44-08 — 0.01 left to pay counts as 0.01.
    Rules: `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719] (HR-15)"""
    _partly_paid(order, inv, "confirmed", "partial", "299.99")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "0.01"
    )


# [claude] EXO-OQ44-09
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_09__locked_partly_paid_counts_what_is_left(db, g, order, inv):
    """EXO-OQ44-09 — a locked partly paid invoice counts what is still to pay.
    Rules: `aggregate_financial_snapshot_actionable` R5 [BUG-2719]"""
    _partly_paid(order, inv, "locked", "partial", "100.00")

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "200.00"
    )


# [claude] EXO-OQ44-10
@pytest.mark.xfail(strict=True, reason=BUG_2719)
def test_exo_oq44_10__completed_voided_invoice_full_total(db, g, order, inv):
    """EXO-OQ44-10 — a completed order whose invoice is voided counts at its full order total.
    Rules: `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]"""
    va = inv(1, "30.00", "invvoid")
    order(
        "EXP-T-001",
        total_amount=Decimal("70.00"),
        due_date=date(2031, 11, 12),
        completed=True,
        invoice_id=va.id,
    )

    with clockD():
        result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=g.W1.id)

    # Then 1
    assert bucket(result, "due_timeline", "due_this_week")["count"] == 1
    # Then 2
    assert bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal(
        "70.00"
    )
