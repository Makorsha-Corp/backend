"""Unit tests for app/dao/sales_order.py.

Implements tests/unit/dao/sales_order.cases.md (revision 2), one test per case,
in card order. Real Postgres session (`db` fixture).

Patched: only the clock of the `CW` cards (Conventions, Externals: clock(L, U)
patches `app.dao.sales_order.datetime`, `app.dao.sales_order.utcnow` with
`create=True` and `app.utils.time.utcnow`). `GI` and `GN` cards patch nothing.
No race simulations.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`, naive datetimes for the clock values, and the Decimal strings as carded)
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.sales_order import sales_order_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.sales_order import SalesOrder
from app.models.status import Status
from app.schemas.sales_order import SalesOrderCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton sales_order_dao"
dao = sales_order_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "D1, D2, D3"
D1 = date(2026, 1, 5)
D2 = date(2026, 3, 1)
D3 = date(2026, 3, 20)

# Convention "A CW card without a clock line runs under clock(2026-06-01 12:00, 2026-06-01 12:00)"
DEFAULT_CLOCK = (datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0))


# Convention "utc_now()"
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def g(db):
    """The standing rows, by their Conventions names: g.W0 ... g.V9, plus g.TAG.

    Order: W0, W1, W2, U1, U2, U3; then per workspace k in 0, 1, 2: Ak, Fk, Sk;
    then invoices V0 (W0), V1, V2, V3 (W1), V9 (W2).
    """
    n = SimpleNamespace(TAG=uuid.uuid4().hex[:8])
    n.W0, n.W1, n.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    n.U1, n.U2, n.U3 = make_profile(db), make_profile(db), make_profile(db)
    for k in (0, 1, 2):
        ws = getattr(n, f"W{k}")
        setattr(n, f"A{k}", _add(db, Account(workspace_id=ws.id, name=f"Acme {n.TAG}")))
        setattr(
            n,
            f"F{k}",
            _add(
                db,
                Factory(workspace_id=ws.id, name="Main Plant", abbreviation=f"MP{k}"),
            ),
        )
        setattr(
            n,
            f"S{k}",
            _add(db, Status(workspace_id=ws.id, name="Open", comment="open")),
        )
    for name, k in (("V0", 0), ("V1", 1), ("V2", 1), ("V3", 1), ("V9", 2)):
        ws, acc = getattr(n, f"W{k}"), getattr(n, f"A{k}")
        inv = AccountInvoice(
            workspace_id=ws.id,
            account_id=acc.id,
            invoice_type="receivable",
            invoice_amount=Decimal("100.00"),
            invoice_date=D1,
        )
        setattr(n, name, _add(db, inv))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given-row builders
# --------------------------------------------------------------------------- #


def _order_row(g, k, number, **columns):
    """Convention "order": an order of Wk (default W1); `columns` are the "but" columns."""
    fields = {
        "workspace_id": getattr(g, f"W{k}").id,
        "sales_order_number": number,
        "account_id": getattr(g, f"A{k}").id,
        "factory_id": getattr(g, f"F{k}").id,
        "order_date": D1,
        "current_status_id": getattr(g, f"S{k}").id,
        "created_by": g.U1.id,
    }
    fields.update(columns)
    return SalesOrder(**fields)


@pytest.fixture
def mk_order(db, g):
    """mk_order(number, k=1, **but) -> SalesOrder, flushed. `k` = 0, 1 or 2 ("of W0" / W1 / "of W2")."""

    def _mk(number, k=1, **columns):
        return _add(db, _order_row(g, k, number, **columns))

    return _mk


@pytest.fixture
def mk_orders(db, g):
    """Convention "orders(W, prefix, n)": n orders numbered f"{prefix}{i:03d}", one flush after the loop."""

    def _mk(k, prefix, n):
        for i in range(1, n + 1):
            db.add(_order_row(g, k, f"{prefix}{i:03d}"))
        db.flush()

    return _mk


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "Dhaka"
def dhaka(db):
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# Convention "HIGH_ID"
def high_id(db):
    return db.execute(
        text(
            "SELECT GREATEST((SELECT COALESCE(MAX(id), 0) FROM sales_orders), (SELECT last_value FROM sales_orders_id_seq)) + 1000001"
        )
    ).scalar_one()


# Convention "clock(L, U)"
@contextmanager
def clock(local, utc):
    class _LocalClock(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return local

    with patch("app.dao.sales_order.datetime", _LocalClock):
        with patch("app.dao.sales_order.utcnow", create=True, return_value=utc):
            with patch("app.utils.time.utcnow", return_value=utc):
                yield


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #


# Convention "re-read X"
def reread(db, row_id):
    db.expire_all()
    return db.execute(select(SalesOrder).where(SalesOrder.id == row_id)).scalar_one()


# Convention "count(W)"
def count(db, ws):
    return db.scalar(
        select(func.count())
        .select_from(SalesOrder)
        .where(SalesOrder.workspace_id == ws.id)
    )


# Convention "nothing written": count(W0), count(W1), count(W2)
def counts(db, g):
    return (count(db, g.W0), count(db, g.W1), count(db, g.W2))


# "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    table = SalesOrder.__table__
    found = (
        db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0]))
        .mappings()
        .one_or_none()
    )
    return dict(found) if found is not None else None


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

    @property
    def written(self):
        return [
            s
            for s in self.statements
            if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]

    @property
    def sql(self):
        """The one SELECT from sales_orders; fails loudly unless there is exactly one."""
        [statement] = [
            s
            for s in self.statements
            if s.lstrip().upper().startswith("SELECT") and "sales_orders" in s
        ]
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
        return sql.split("FOR UPDATE", 1)[1] if "FOR UPDATE" in sql else ""


def create_w1(db, g, user=None, **schema_fields):
    """The CW cards' `SalesOrderCreate(account_id=A1, factory_id=F1, order_date=D2, current_status_id=S1, ...)`."""
    fields = {
        "account_id": g.A1.id,
        "factory_id": g.F1.id,
        "order_date": D2,
        "current_status_id": g.S1.id,
    }
    fields.update(schema_fields)
    return dao.create_with_user(
        db,
        obj_in=SalesOrderCreate(**fields),
        workspace_id=g.W1.id,
        user_id=(user or g.U1).id,
    )


# --------------------------------------------------------------------------- #
# DAOSalesOrder.get_by_invoice_id
# --------------------------------------------------------------------------- #


# [claude] SLO-GI-01
def test_slo_gi_01__returns_the_order_of_the_invoice(db, g, mk_order):
    """SLO-GI-01 — returns the order of the invoice, with the invoice in the middle.
    Rules: `get_by_invoice_id` R1"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    o2 = mk_order(f"SO-2026-002-{g.TAG}", invoice_id=g.V2.id)
    mk_order(f"SO-2026-003-{g.TAG}", invoice_id=g.V3.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V2.id, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, SalesOrder)
    # Then 2
    assert result.id == o2.id
    # Then 3
    assert result.sales_order_number == f"SO-2026-002-{g.TAG}"


# [claude] SLO-GI-02
def test_slo_gi_02__earlier_workspace_order_not_returned(db, g, mk_order):
    """SLO-GI-02 — an order of the earlier workspace with its own invoice is not returned for W1.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-010-{g.TAG}", k=0, invoice_id=g.V0.id)
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V0.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-03
def test_slo_gi_03__later_workspace_order_not_returned(db, g, mk_order):
    """SLO-GI-03 — an order of the later workspace with its own invoice is not returned for W1.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-020-{g.TAG}", k=2, invoice_id=g.V9.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V9.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-04
def test_slo_gi_04__w2_gets_its_own_order(db, g, mk_order):
    """SLO-GI-04 — asked for W2, its own order is returned, though W0 and W1 orders come earlier.
    Rules: `get_by_invoice_id` R1, R2"""
    mk_order(f"SO-2026-010-{g.TAG}", k=0, invoice_id=g.V0.id)
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    x2 = mk_order(f"SO-2026-020-{g.TAG}", k=2, invoice_id=g.V9.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V9.id, workspace_id=g.W2.id)

    # Then 1
    assert result.id == x2.id


# [claude] SLO-GI-05
def test_slo_gi_05__w0_gets_its_own_order(db, g, mk_order):
    """SLO-GI-05 — asked for W0, its own order is returned, though W1 and W2 orders come later.
    Rules: `get_by_invoice_id` R1, R2"""
    x0 = mk_order(f"SO-2026-010-{g.TAG}", k=0, invoice_id=g.V0.id)
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-020-{g.TAG}", k=2, invoice_id=g.V9.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V0.id, workspace_id=g.W0.id)

    # Then 1
    assert result.id == x0.id


# [claude] SLO-GI-06
def test_slo_gi_06__invoice_without_order_returns_none(db, g, mk_order):
    """SLO-GI-06 — an invoice with no order returns None.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-003-{g.TAG}", invoice_id=g.V3.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V2.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-07
def test_slo_gi_07__unknown_invoice_returns_none(db, g, mk_order):
    """SLO-GI-07 — an unknown invoice id returns None.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)

    result = dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-08
def test_slo_gi_08__invoice_id_zero_returns_none(db, g, mk_order):
    """SLO-GI-08 — invoice id 0 returns None.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-002-{g.TAG}")

    result = dao.get_by_invoice_id(db, invoice_id=0, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-09
def test_slo_gi_09__unknown_workspace_returns_none(db, g, mk_order):
    """SLO-GI-09 — an unknown workspace id returns None.
    Rules: `get_by_invoice_id` R2"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=MISSING)

    # Then 1
    assert result is None


# [claude] SLO-GI-10
def test_slo_gi_10__two_orders_on_one_invoice_one_returned(db, g, mk_order):
    """SLO-GI-10 — with two orders on one invoice, one of them is returned.
    Rules: `get_by_invoice_id` R1, R3"""
    oa = mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    ob = mk_order(f"SO-2026-002-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-003-{g.TAG}", invoice_id=g.V2.id)

    result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=g.W1.id)

    # Then 1
    assert result.id in {oa.id, ob.id}


# [claude] SLO-GI-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2441: an invoice's sales order is looked up with no ORDER BY (physical row order)",
)
def test_slo_gi_11__lowest_id_wins_after_lower_one_updated(db, g, mk_order):
    """SLO-GI-11 — on two orders of one invoice the lowest id wins, also after the lower one was updated.
    Rules: `get_by_invoice_id` R3 [BUG-2441]"""
    seqscan(db)
    oa = mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-002-{g.TAG}", invoice_id=g.V1.id)
    oa.description = "Edited"
    db.flush()
    oa_id = oa.id
    db.expire_all()

    result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=g.W1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == oa_id


# [claude] SLO-GI-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2441: an invoice's sales order is looked up with no ORDER BY (physical row order)",
)
def test_slo_gi_12__lowest_id_wins_when_higher_inserted_first(db, g, mk_order):
    """SLO-GI-12 — on two orders of one invoice the lowest id wins, when the higher id was inserted first.
    Rules: `get_by_invoice_id` R3 [BUG-2441]"""
    seqscan(db)
    mk_order(f"SO-2026-002-{g.TAG}", id=high_id(db), invoice_id=g.V1.id)
    oa = mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    oa_id = oa.id
    db.expire_all()

    result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=g.W1.id)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == oa_id


# [claude] SLO-GI-13
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2441: an invoice's sales order is looked up with no ORDER BY (physical row order)",
)
def test_slo_gi_13__lookup_orders_by_id_ascending(db, g, mk_order):
    """SLO-GI-13 — the lookup orders by sales_orders.id ascending.
    Rules: `get_by_invoice_id` R3 [BUG-2441]"""
    o1 = mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=g.W1.id)

    # Then 1
    assert result.id == o1.id
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "sales_orders.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0


# [claude] SLO-GI-14
def test_slo_gi_14__none_returns_the_order_without_invoice(db, g, mk_order):
    """SLO-GI-14 — invoice_id None returns the workspace's order that has no invoice.
    Rules: `get_by_invoice_id` R4"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    o2 = mk_order(f"SO-2026-002-{g.TAG}")
    mk_order(f"SO-2026-003-{g.TAG}", invoice_id=g.V3.id)
    mk_order(f"SO-2026-020-{g.TAG}", k=2)

    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=g.W1.id)

    # Then 1
    assert result.id == o2.id


# [claude] SLO-GI-15
def test_slo_gi_15__none_returns_none_when_all_have_invoice(db, g, mk_order):
    """SLO-GI-15 — invoice_id None returns None when every order of the workspace has an invoice.
    Rules: `get_by_invoice_id` R4"""
    mk_order(f"SO-2026-010-{g.TAG}", k=0)
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    mk_order(f"SO-2026-002-{g.TAG}", invoice_id=g.V2.id)
    mk_order(f"SO-2026-020-{g.TAG}", k=2)

    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] SLO-GI-16
def test_slo_gi_16__positional_arguments_raise_type_error(db, g, mk_order):
    """SLO-GI-16 — positional arguments raise TypeError.
    Rules: `get_by_invoice_id` R5"""
    mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    before = counts(db, g)

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_invoice_id(db, g.V1.id, g.W1.id)
    assert isinstance(exc.value, TypeError)
    # Then 2
    assert counts(db, g) == before


# [claude] SLO-GI-17
def test_slo_gi_17__writes_nothing(db, g, mk_order):
    """SLO-GI-17 — writes nothing: a pending order stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_invoice_id` Side effects"""
    o1 = mk_order(f"SO-2026-001-{g.TAG}", invoice_id=g.V1.id)
    o1.description = "Edited"
    p = SalesOrder(
        workspace_id=g.W1.id,
        sales_order_number=f"SO-2026-009-{g.TAG}",
        account_id=g.A1.id,
        factory_id=g.F1.id,
        order_date=D1,
        current_status_id=g.S1.id,
        created_by=g.U1.id,
        invoice_id=g.V2.id,
    )
    db.add(p)

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=g.V1.id, workspace_id=g.W1.id)

    # Then 1
    assert result.id == o1.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert o1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []


# [claude] SLO-GI-18
def test_slo_gi_18__pending_order_not_found_no_lock(db, g):
    """SLO-GI-18 — the pending order is not found, and no row lock is taken.
    Rules: `get_by_invoice_id` R2, Side effects (Overview: takes no lock)"""
    p = SalesOrder(
        workspace_id=g.W1.id,
        sales_order_number=f"SO-2026-009-{g.TAG}",
        account_id=g.A1.id,
        factory_id=g.F1.id,
        order_date=D1,
        current_status_id=g.S1.id,
        created_by=g.U1.id,
        invoice_id=g.V2.id,
    )
    db.add(p)

    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=g.V2.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert "FOR UPDATE" not in rec.sql
    # Then 3
    assert p in db.new


# --------------------------------------------------------------------------- #
# DAOSalesOrder.generate_sales_order_number
# --------------------------------------------------------------------------- #


# [claude] SLO-GN-01
def test_slo_gn_01__no_order_gives_001(db, g):
    """SLO-GN-01 — no order yet gives SO-2026-001.
    Rules: `generate_sales_order_number` R1, Returns"""
    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "SO-2026-001"


# [claude] SLO-GN-02
def test_slo_gn_02__two_orders_give_003(db, g, mk_order):
    """SLO-GN-02 — two orders give SO-2026-003.
    Rules: `generate_sales_order_number` R1"""
    mk_order("SO-2026-001")
    mk_order("SO-2026-002")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-003"


# [claude] SLO-GN-03, GN-04, GN-05, GN-06
@pytest.mark.parametrize(
    ("n", "expected"),
    [
        pytest.param(9, "SO-2026-010", id="SLO-GN-03"),
        pytest.param(99, "SO-2026-100", id="SLO-GN-04"),
        pytest.param(998, "SO-2026-999", id="SLO-GN-05"),
        pytest.param(999, "SO-2026-1000", id="SLO-GN-06"),
    ],
)
def test_slo_gn_03_to_06__count_boundaries(db, g, mk_orders, n, expected):
    """SLO-GN-03 … GN-06 — 9 / 99 / 998 / 999 orders give 010 / 100 / 999 / 1000 (not cut to three digits).
    Rules: `generate_sales_order_number` R1"""
    mk_orders(1, "SO-2026-", n)

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == expected


def _gn_isolation_rows(mk_order):
    """The Given rows of SLO-GN-07 and GN-08."""
    mk_order("SO-2026-001", k=0)
    mk_order("SO-2026-002", k=0)
    mk_order("SO-2026-003", k=0)
    mk_order("SO-2026-006")
    mk_order("SO-2026-004", k=2)
    mk_order("SO-2026-005", k=2)


# [claude] SLO-GN-07
def test_slo_gn_07__only_w1_orders_count(db, g, mk_order):
    """SLO-GN-07 — only W1's orders count, with more orders in W0 and W2.
    Rules: `generate_sales_order_number` R2"""
    _gn_isolation_rows(mk_order)

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"


# [claude] SLO-GN-08
def test_slo_gn_08__only_w2_orders_count(db, g, mk_order):
    """SLO-GN-08 — asked for W2, only W2's orders count.
    Rules: `generate_sales_order_number` R2"""
    _gn_isolation_rows(mk_order)

    result = dao.generate_sales_order_number(db, workspace_id=g.W2.id, year=2026)

    # Then 1
    assert result == "SO-2026-003"


# [claude] SLO-GN-09
def test_slo_gn_09__unknown_workspace_gets_001(db, g, mk_order):
    """SLO-GN-09 — an unknown workspace gets SO-2026-001.
    Rules: `generate_sales_order_number` R2"""
    mk_order("SO-2026-001")

    result = dao.generate_sales_order_number(db, workspace_id=MISSING, year=2026)

    # Then 1
    assert result == "SO-2026-001"


# [claude] SLO-GN-10
def test_slo_gn_10__other_years_do_not_count(db, g, mk_order):
    """SLO-GN-10 — orders of the year before and the year after do not count.
    Rules: `generate_sales_order_number` R3"""
    mk_order("SO-2025-001")
    mk_order("SO-2027-001")
    mk_order("SO-2026-001")
    mk_order("SO-2025-002")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"


# [claude] SLO-GN-11
def test_slo_gn_11__year_202_does_not_count_2026(db, g, mk_order):
    """SLO-GN-11 — year 202 does not count SO-2026 numbers.
    Rules: `generate_sales_order_number` R3"""
    mk_order("SO-2026-001")
    mk_order("SO-2026-002")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=202)

    # Then 1
    assert result == "SO-202-001"


# [claude] SLO-GN-12
def test_slo_gn_12__year_1_printed_as_is(db, g, mk_order):
    """SLO-GN-12 — year 1 is printed as is, and SO-10 numbers do not count for it.
    Rules: `generate_sales_order_number` R3"""
    mk_order("SO-10-001")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=1)

    # Then 1
    assert result == "SO-1-001"


# [claude] SLO-GN-13
def test_slo_gn_13__year_1_counts_its_own(db, g, mk_order):
    """SLO-GN-13 — year 1 counts its own SO-1 numbers.
    Rules: `generate_sales_order_number` R1, R3"""
    mk_order("SO-1-001")
    mk_order("SO-10-001")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=1)

    # Then 1
    assert result == "SO-1-002"


# [claude] SLO-GN-14
def test_slo_gn_14__longer_year_does_not_count(db, g, mk_order):
    """SLO-GN-14 — a number with a longer year (SO-20261-) does not count for 2026.
    Rules: `generate_sales_order_number` R3"""
    mk_order("SO-20261-001")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-001"


# [claude] SLO-GN-15
def test_slo_gn_15__non_numeric_suffix_counts(db, g, mk_order):
    """SLO-GN-15 — a non-numeric suffix counts as one order.
    Rules: `generate_sales_order_number` R4"""
    mk_order("SO-2026-abc")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"


# [claude] SLO-GN-16
def test_slo_gn_16__count_not_highest_number_decides(db, g, mk_order):
    """SLO-GN-16 — the count, not the highest number, decides: SO-2026-009 alone gives 002.
    Rules: `generate_sales_order_number` R4"""
    mk_order("SO-2026-009")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"


# [claude] SLO-GN-17, GN-18, GN-19, GN-21
@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("so-2026-001", id="SLO-GN-17"),
        pytest.param(" SO-2026-001", id="SLO-GN-18"),
        pytest.param("XSO-2026-001", id="SLO-GN-19"),
        pytest.param("SO-2026", id="SLO-GN-21"),
    ],
)
def test_slo_gn_17_18_19_21__near_miss_numbers_do_not_count(db, g, mk_order, stored):
    """SLO-GN-17 / 18 / 19 / 21 — a lowercase prefix, a leading space, the prefix in the middle,
    the prefix without its closing dash: none counts.
    Rules: `generate_sales_order_number` R1, R3 (GN-17 also R3a)"""
    mk_order(stored)

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-001"


# [claude] SLO-GN-20
def test_slo_gn_20__underscore_for_dash_does_not_count(db, g, mk_order):
    """SLO-GN-20 — a stored _ where the prefix has a dash does not count.
    Rules: `generate_sales_order_number` R1, R3"""
    mk_order("SO_2026-001")
    mk_order("SO-2026_001")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-001"


# [claude] SLO-GN-22
def test_slo_gn_22__writes_nothing(db, g, mk_order):
    """SLO-GN-22 — writes nothing: a pending order stays pending and is not counted, an unflushed edit stays unflushed.
    Rules: `generate_sales_order_number` R5, Side effects"""
    b = mk_order("SO-2025-001")
    b.description = "Edited"
    p = SalesOrder(
        workspace_id=g.W1.id,
        sales_order_number="SO-2026-001",
        account_id=g.A1.id,
        factory_id=g.F1.id,
        order_date=D1,
        current_status_id=g.S1.id,
        created_by=g.U1.id,
    )
    db.add(p)

    with StatementRecorder(db) as rec:
        result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-001"
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


# [claude] SLO-GN-23
def test_slo_gn_23__reads_with_no_row_lock(db, g, mk_order):
    """SLO-GN-23 — reads with no row lock.
    Rules: `generate_sales_order_number` R5"""
    mk_order("SO-2026-001")

    with StatementRecorder(db) as rec:
        result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"
    # Then 2
    assert "FOR UPDATE" not in rec.sql
    # Then 3
    assert rec.written == []


# [claude] SLO-GN-24
def test_slo_gn_24__positional_arguments_raise_type_error(db, g):
    """SLO-GN-24 — positional arguments raise TypeError.
    Rules: `generate_sales_order_number` R6"""
    before = counts(db, g)

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.generate_sales_order_number(db, g.W1.id, 2026)
    assert isinstance(exc.value, TypeError)
    # Then 2
    assert counts(db, g) == before


# [claude] SLO-GN-25
def test_slo_gn_25__mixed_case_prefix_does_not_count(db, g, mk_order):
    """SLO-GN-25 — a mixed-case stored prefix (So-) does not count.
    Rules: `generate_sales_order_number` R3a"""
    mk_order("So-2026-001")
    mk_order("SO-2026-002")

    result = dao.generate_sales_order_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "SO-2026-002"


# --------------------------------------------------------------------------- #
# DAOSalesOrder.create_with_user
# --------------------------------------------------------------------------- #


# [claude] SLO-CW-01
def test_slo_cw_01__stores_every_field(db, g):
    """SLO-CW-01 — stores every given field, the workspace, the creator and the first number.
    Rules: `create_with_user` R1, Returns"""
    with clock(*DEFAULT_CLOCK):
        result = dao.create_with_user(
            db,
            obj_in=SalesOrderCreate(
                account_id=g.A1.id,
                factory_id=g.F1.id,
                order_date=D2,
                expected_delivery_date=D3,
                contact_name="Rahim",
                contact_phone="01711000000",
                description="Ten chairs",
                total_amount=Decimal("1500.00"),
                current_status_id=g.S1.id,
            ),
            workspace_id=g.W1.id,
            user_id=g.U2.id,
        )

    # Then 1
    assert isinstance(result, SalesOrder)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result.id)
    assert row.workspace_id == g.W1.id
    assert row.created_by == g.U2.id
    assert row.sales_order_number == "SO-2026-001"
    # Then 4
    assert row.account_id == g.A1.id
    assert row.factory_id == g.F1.id
    assert row.current_status_id == g.S1.id
    # Then 5
    assert row.order_date == D2
    assert row.expected_delivery_date == D3
    # Then 6
    assert row.contact_name == "Rahim"
    assert row.contact_phone == "01711000000"
    assert row.description == "Ten chairs"
    # Then 7
    assert row.total_amount == Decimal("1500.00")
    # Then 8
    assert count(db, g.W1) == 1


# [claude] SLO-CW-02
def test_slo_cw_02__unset_optional_fields_are_null(db, g):
    """SLO-CW-02 — unset optional fields are stored as NULL.
    Rules: `create_with_user` R1"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.expected_delivery_date is None
    assert row.contact_name is None
    assert row.contact_phone is None
    assert row.description is None


# [claude] SLO-CW-03
def test_slo_cw_03__next_number_of_the_year(db, g, mk_order):
    """SLO-CW-03 — the second and third orders of the year get the next number.
    Rules: `create_with_user` R1"""
    mk_order("SO-2026-001")
    mk_order("SO-2026-002")

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2026-003"
    # Then 3
    assert count(db, g.W1) == 3


# [claude] SLO-CW-04
def test_slo_cw_04__number_counts_this_workspace_only(db, g, mk_order):
    """SLO-CW-04 — the number counts this workspace only, with more orders in W0 and W2.
    Rules: `create_with_user` R1"""
    mk_order("SO-2026-007", k=0)
    mk_order("SO-2026-008", k=0)
    mk_order("SO-2026-001")
    mk_order("SO-2026-009", k=2)
    mk_order("SO-2026-010", k=2)

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.sales_order_number == "SO-2026-002"
    assert row.workspace_id == g.W1.id
    # Then 3
    assert count(db, g.W0) == 2
    # Then 4
    assert count(db, g.W2) == 2


# [claude] SLO-CW-05
def test_slo_cw_05__current_year_last_year_not_counted(db, g, mk_order):
    """SLO-CW-05 — the number takes the current year, and last year's orders do not count.
    Rules: `create_with_user` R1, R2"""
    mk_order("SO-2025-001")
    mk_order("SO-2025-002")

    with clock(datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2026-001"


# [claude] SLO-CW-06
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the sales order number takes the server's local year, not the UTC year",
)
def test_slo_cw_06__utc_year_when_local_already_next_year(db, g):
    """SLO-CW-06 — the year comes from UTC when the local clock is already in the next year.
    Rules: `create_with_user` R2 [BUG-2440]"""
    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2026-001"


# [claude] SLO-CW-07
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the sales order number takes the server's local year, not the UTC year",
)
def test_slo_cw_07__utc_year_when_local_still_old_year(db, g):
    """SLO-CW-07 — the year comes from UTC when the local clock is still in the old year.
    Rules: `create_with_user` R2 [BUG-2440]"""
    with clock(datetime(2026, 12, 31, 20, 0), datetime(2027, 1, 1, 2, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2027-001"


# [claude] SLO-CW-08
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the sales order number takes the server's local year, not the UTC year",
)
def test_slo_cw_08__new_years_eve_utc_counts_utc_year(db, g, mk_order):
    """SLO-CW-08 — on New Year's Eve in UTC the UTC year's orders are counted.
    Rules: `create_with_user` R1, R2 [BUG-2440]"""
    mk_order("SO-2026-001")
    mk_order("SO-2026-002")

    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2026-003"


# [claude] SLO-CW-31
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the sales order number takes the server's local year, not the UTC year",
)
def test_slo_cw_31__new_years_day_utc_old_year_not_counted(db, g, mk_order):
    """SLO-CW-31 — on New Year's Day in UTC the old year's orders are not counted.
    Rules: `create_with_user` R1, R2 [BUG-2440]"""
    mk_order("SO-2026-001")
    mk_order("SO-2026-002")

    with clock(datetime(2026, 12, 31, 20, 0), datetime(2027, 1, 1, 2, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2027-001"


# [claude] SLO-CW-09
def test_slo_cw_09__omitted_total_stored_as_zero(db, g):
    """SLO-CW-09 — total_amount omitted is stored as 0.00.
    Rules: `create_with_user` R3"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).total_amount == Decimal("0.00")


# [claude] SLO-CW-10, CW-11, CW-12, CW-13, CW-14
@pytest.mark.parametrize(
    ("sent", "stored"),
    [
        pytest.param(Decimal("2.125"), Decimal("2.13"), id="SLO-CW-10"),
        pytest.param(Decimal("0.005"), Decimal("0.01"), id="SLO-CW-11"),
        pytest.param(Decimal("-1.005"), Decimal("-1.01"), id="SLO-CW-12"),
        pytest.param(Decimal("2.124"), Decimal("2.12"), id="SLO-CW-13"),
        pytest.param(Decimal("1.005"), Decimal("1.01"), id="SLO-CW-14"),
    ],
)
def test_slo_cw_10_to_14__total_rounds_half_up(db, g, sent, stored):
    """SLO-CW-10 … CW-14 — 2.125 → 2.13, 0.005 → 0.01, -1.005 → -1.01, 2.124 → 2.12, 1.005 → 1.01.
    Rules: `create_with_user` R3 (HR-15)"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, total_amount=sent)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).total_amount == stored


# [claude] SLO-CW-15
def test_slo_cw_15__zero_amount_accepted(db, g):
    """SLO-CW-15 — a zero amount is accepted and stored as 0.00.
    Rules: `create_with_user` R3"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, total_amount=Decimal("0"))

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).total_amount == Decimal("0.00")
    # Then 3
    assert count(db, g.W1) == 1


# [claude] SLO-CW-16
def test_slo_cw_16__negative_amount_accepted(db, g):
    """SLO-CW-16 — a negative amount is accepted and stored as given.
    Rules: `create_with_user` R3"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, total_amount=Decimal("-50.00"))

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).total_amount == Decimal("-50.00")


# [claude] SLO-CW-17
def test_slo_cw_17__flags_false_later_fields_empty(db, g):
    """SLO-CW-17 — the new order's flags are false and its later fields empty.
    Rules: `create_with_user` R4"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.is_fully_delivered is False
    assert row.is_invoiced is False
    assert row.paid is False
    assert row.order_info_confirmed is False
    # Then 3
    assert row.items_confirmed is False
    assert row.invoice_confirmed is False
    assert row.order_completed is False
    # Then 4
    assert row.invoice_id is None
    assert row.required_approvals is None
    assert row.completed_at is None
    assert row.completed_by is None
    # Then 5
    assert row.updated_by is None
    assert row.updated_at is None
    assert row.items_updated_at is None


# [claude] SLO-CW-18
def test_slo_cw_18__created_at_is_current_utc_naive(db, g):
    """SLO-CW-18 — created_at is the current UTC time, naive.
    Rules: `create_with_user` R4"""
    before = utc_now()

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)
    after = utc_now()

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.created_at.tzinfo is None
    # Then 3
    assert before <= row.created_at <= after


# [claude] SLO-CW-19
def test_slo_cw_19__created_at_utc_under_dhaka(db, g):
    """SLO-CW-19 — created_at is UTC also when the database's time zone is Asia/Dhaka.
    Rules: `create_with_user` R4"""
    dhaka(db)
    before = utc_now()

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)
    after = utc_now()

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.created_at.tzinfo is None
    # Then 3
    assert before <= row.created_at <= after


# [claude] SLO-CW-20
@pytest.mark.xfail(
    strict=True,
    reason="BUG-726: the sales order number is unique across all workspaces, not per workspace",
)
def test_slo_cw_20__w0_number_does_not_stop_w1(db, g, mk_order):
    """SLO-CW-20 — W0's SO-2026-001 does not stop W1's first order of 2026.
    Rules: `create_with_user` R5 [BUG-726]"""
    mk_order("SO-2026-001", k=0)

    # Then 1 (the call raises IntegrityError today, so the failure lands here)
    with clock(*DEFAULT_CLOCK):
        with db.begin_nested():
            result = create_w1(db, g)
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.sales_order_number == "SO-2026-001"
    assert row.workspace_id == g.W1.id
    # Then 3
    assert count(db, g.W0) == 1


# [claude] SLO-CW-21
@pytest.mark.xfail(
    strict=True,
    reason="BUG-726: the sales order number is unique across all workspaces, not per workspace",
)
def test_slo_cw_21__w2_number_does_not_stop_w1(db, g, mk_order):
    """SLO-CW-21 — W2's SO-2026-001 does not stop W1's first order of 2026.
    Rules: `create_with_user` R5 [BUG-726]"""
    mk_order("SO-2026-001", k=2)

    # Then 1 (the call raises IntegrityError today, so the failure lands here)
    with clock(*DEFAULT_CLOCK):
        with db.begin_nested():
            result = create_w1(db, g)
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.sales_order_number == "SO-2026-001"
    assert row.workspace_id == g.W1.id
    # Then 3
    assert count(db, g.W2) == 1


# [claude] SLO-CW-22
def test_slo_cw_22__computed_number_already_used_fails(db, g, mk_order):
    """SLO-CW-22 — a computed number already used in the workspace fails at the flush and saves nothing.
    Rules: `generate_sales_order_number` R4, `create_with_user` Errors (number already used)"""
    mk_order("SO-2026-002")
    mk_order("SO-2026-003")
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                create_w1(db, g)
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert count(db, g.W1) == 2
    # Then 3
    assert counts(db, g) == before


# [claude] SLO-CW-23, CW-24, CW-25, CW-26
@pytest.mark.parametrize(
    "missing",
    [
        pytest.param("account_id", id="SLO-CW-23"),
        pytest.param("factory_id", id="SLO-CW-24"),
        pytest.param("current_status_id", id="SLO-CW-25"),
        pytest.param("user_id", id="SLO-CW-26"),
    ],
)
def test_slo_cw_23_to_26__unknown_link_fails_with_23503(db, g, missing):
    """SLO-CW-23 … CW-26 — an unknown account / factory / status / user fails at the flush with 23503 and saves nothing.
    Rules: `create_with_user` R6, Errors"""
    fields = {
        "account_id": g.A1.id,
        "factory_id": g.F1.id,
        "order_date": D2,
        "current_status_id": g.S1.id,
    }
    user_id = g.U1.id
    if missing == "user_id":
        user_id = MISSING
    else:
        fields[missing] = MISSING
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create_with_user(
                    db,
                    obj_in=SalesOrderCreate(**fields),
                    workspace_id=g.W1.id,
                    user_id=user_id,
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert count(db, g.W1) == 0
    # Then 3
    assert counts(db, g) == before


# [claude] SLO-CW-27
def test_slo_cw_27__positional_arguments_raise_type_error(db, g):
    """SLO-CW-27 — positional arguments raise TypeError and save nothing.
    Rules: `create_with_user` R7"""
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(TypeError) as exc:
            dao.create_with_user(
                db,
                SalesOrderCreate(
                    account_id=g.A1.id,
                    factory_id=g.F1.id,
                    order_date=D2,
                    current_status_id=g.S1.id,
                ),
                g.W1.id,
                g.U1.id,
            )
    assert isinstance(exc.value, TypeError)
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db, g) == before


# [claude] SLO-CW-28
def test_slo_cw_28__dict_obj_in_raises_attribute_error(db, g):
    """SLO-CW-28 — a plain dict as obj_in raises AttributeError and saves nothing.
    Rules: `create_with_user` R7"""
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(AttributeError) as exc:
            dao.create_with_user(
                db,
                obj_in={
                    "account_id": g.A1.id,
                    "factory_id": g.F1.id,
                    "order_date": D2,
                    "current_status_id": g.S1.id,
                },
                workspace_id=g.W1.id,
                user_id=g.U1.id,
            )
    assert isinstance(exc.value, AttributeError)
    # Then 2
    assert not db.new
    # Then 3
    assert counts(db, g) == before


# [claude] SLO-CW-29
def test_slo_cw_29__flushed_not_committed(db, g):
    """SLO-CW-29 — flushed, not committed: a rollback removes the order.
    Rules: `create_with_user` Returns, Side effects"""
    sp = db.begin_nested()
    with clock(*DEFAULT_CLOCK):
        with patch.object(db, "commit", wraps=db.commit) as cm:
            result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, g.W1) == 1
    sp.rollback()
    # Then 3
    assert count(db, g.W1) == 0
    # Then 4
    assert cm.call_count == 0


# [claude] SLO-CW-30
def test_slo_cw_30__inserts_one_row_touches_no_other(db, g, mk_order):
    """SLO-CW-30 — inserts exactly one row and touches no other order.
    Rules: `create_with_user` Side effects"""
    mk_order("SO-2026-011", k=0)
    o1 = mk_order("SO-2026-001")
    mk_order("SO-2026-012", k=2)
    before_o1 = snap(db, o1)

    with clock(*DEFAULT_CLOCK):
        with StatementRecorder(db) as rec:
            result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rec.written) == 1
    # Then 3
    assert rec.written[0].lstrip().upper().startswith("INSERT INTO SALES_ORDERS")
    # Then 4
    assert count(db, g.W0) == 1
    # Then 5
    assert count(db, g.W1) == 2
    # Then 6
    assert count(db, g.W2) == 1
    # Then 7
    assert snap(db, o1) == before_o1


# [claude] SLO-CW-32
def test_slo_cw_32__schema_turns_numbers_into_unrounded_decimal(db, g):
    """SLO-CW-32 — the schema turns an int, a float and a numeric string into an unrounded Decimal.
    Rules: `create_with_user` Inputs (`total_amount` is `Decimal | None`)"""
    before = counts(db, g)

    with clock(*DEFAULT_CLOCK):
        result = [
            SalesOrderCreate(
                account_id=g.A1.id, factory_id=g.F1.id, order_date=D2, total_amount=v
            ).total_amount
            for v in (990, 2.5, "2.125")
        ]

    # Then 1
    assert [type(v) for v in result] == [Decimal, Decimal, Decimal]
    # Then 2
    assert result[0] == Decimal("990")
    # Then 3
    assert result[1] == Decimal("2.5")
    # Then 4
    assert result[2] == Decimal("2.125")
    # Then 5
    assert counts(db, g) == before


# [claude] SLO-CW-33
def test_slo_cw_33__int_amount_stored_with_two_decimals(db, g):
    """SLO-CW-33 — an int amount is stored as a Decimal with two decimals.
    Rules: `create_with_user` R3, HR-15"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, total_amount=990)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.total_amount == Decimal("990.00")
    # Then 3
    assert str(row.total_amount) == "990.00"


# [claude] SLO-CW-34
def test_slo_cw_34__year_comes_from_the_clock(db, g, mk_order):
    """SLO-CW-34 — the year comes from the clock: both clocks in 2031 give SO-2031-001.
    Rules: `create_with_user` R1, R2"""
    mk_order("SO-2026-001")

    with clock(datetime(2031, 1, 1, 0, 30), datetime(2031, 1, 1, 0, 30)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).sales_order_number == "SO-2031-001"
