"""Unit tests for app/dao/sales_order_return.py.

Implements tests/unit/dao/sales_order_return.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). The only patch is the
Conventions' clock(L, U) in the `CW` cards; nothing else is mocked. The commit
spy of SRT-CW-18 wraps the real `db.commit`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()` and naive datetimes)
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.sales_order_return import (
    sales_order_return_dao,
    sales_order_return_item_dao,
)
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.factory import Factory
from app.models.item import Item
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.status import Status
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao" (module-level singletons, not fixtures)
dao = sales_order_return_dao
idao = sales_order_return_item_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "T1 ... T5" (naive, one hour apart)
T1 = datetime(2026, 1, 1, 9, 0)
T2 = datetime(2026, 1, 1, 10, 0)
T3 = datetime(2026, 1, 1, 11, 0)
T4 = datetime(2026, 1, 1, 12, 0)
T5 = datetime(2026, 1, 1, 13, 0)

# Convention "A CW card without a clock line runs under clock(JUNE, JUNE)"
JUNE = datetime(2026, 6, 1, 12, 0)


# --------------------------------------------------------------------------- #
# Conventions -> Externals: clock(L, U)
# --------------------------------------------------------------------------- #


@contextmanager
def clock(local, utc):
    """Convention "clock(L, U)": the module's `datetime.now()` returns L; both
    `app.dao.sales_order_return.utcnow` (create=True) and `app.utils.time.utcnow` return U."""

    class _LocalClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return local

    with (
        patch("app.dao.sales_order_return.datetime", _LocalClock),
        patch("app.dao.sales_order_return.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> the standing rows of every test
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "Standing rows" 1-5, in their order. `s.W1`, `s.SO2`, `s.INV1`, ...
@pytest.fixture
def s(db):
    tag = uuid.uuid4().hex[:8]  # Convention "TAG", made once per test
    r = SimpleNamespace(TAG=tag)
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2, r.U3 = make_profile(db), make_profile(db), make_profile(db)
    for suffix, ws in (("0", r.W0), ("1", r.W1), ("9", r.W2)):
        setattr(r, f"AC{suffix}", _add(db, Account(workspace_id=ws.id, name="Acme")))
        setattr(
            r,
            f"F{suffix}",
            _add(
                db, Factory(workspace_id=ws.id, name="Factory One", abbreviation="F1")
            ),
        )
        setattr(
            r,
            f"S{suffix}",
            _add(db, Status(workspace_id=ws.id, name="Draft", comment="Stage")),
        )
    for name, suffix, ws in (
        ("SO0", "0", r.W0),
        ("SO1", "1", r.W1),
        ("SO2", "1", r.W1),
        ("SO3", "1", r.W1),
        ("SO9", "9", r.W2),
    ):
        setattr(
            r,
            name,
            _add(
                db,
                SalesOrder(
                    workspace_id=ws.id,
                    sales_order_number=f"SO-{tag}-{name}",
                    account_id=getattr(r, f"AC{suffix}").id,
                    factory_id=getattr(r, f"F{suffix}").id,
                    order_date=date(2026, 3, 1),
                    total_amount=0,
                    current_status_id=getattr(r, f"S{suffix}").id,
                    created_by=r.U1.id,
                ),
            ),
        )
    r.IT1 = _add(
        db, Item(workspace_id=r.W1.id, name="Bolt", name_normalized="bolt", unit="pcs")
    )
    r.L1 = _add(
        db,
        SalesOrderItem(
            workspace_id=r.W1.id,
            sales_order_id=r.SO1.id,
            description="Line",
            quantity_ordered=Decimal("5.00"),
            unit_price=Decimal("2.00"),
            line_total=Decimal("10.00"),
        ),
    )
    r.INV1, r.INV2, r.INV3 = (
        _add(
            db,
            AccountInvoice(
                workspace_id=r.W1.id,
                account_id=r.AC1.id,
                invoice_type="payable",
                invoice_amount=100,
                invoice_date=date(2026, 3, 1),
            ),
        )
        for _ in range(3)
    )
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def mk_return(db, s, number, of=None, **cols):
    """Convention "return N" ("of W0" / "of W2" with `of="W0"` / `of="W2"`); `cols` = the
    columns after "but". Added and flushed."""
    fields = {
        "workspace_id": s.W1.id,
        "sales_order_id": s.SO2.id,
        "return_number": number,
        "return_type": "refund",
        "created_by": s.U1.id,
        "created_at": T1,
    }
    if of == "W0":
        fields.update(workspace_id=s.W0.id, sales_order_id=s.SO0.id)
    elif of == "W2":
        fields.update(workspace_id=s.W2.id, sales_order_id=s.SO9.id)
    fields.update(cols)
    return _add(db, SalesOrderReturn(**fields))


def mk_line(db, s, ret, **cols):
    """Convention "line on R"; `cols` = the columns after "but". Added and flushed."""
    fields = {
        "workspace_id": s.W1.id,
        "return_id": ret.id,
        "so_item_id": s.L1.id,
        "item_id": None,
        "quantity_returned": Decimal("1.00"),
        "unit_price": Decimal("2.00"),
    }
    fields.update(cols)
    return _add(db, SalesOrderReturnItem(**fields))


def bump(db, x):
    """Convention "bump(X)"."""
    db.execute(
        text("UPDATE sales_order_returns SET notes = 'bumped' WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


def bump_l(db, x):
    """Convention "bumpL(X)"."""
    db.execute(
        text("UPDATE sales_order_return_items SET notes = 'bumped' WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def dhaka(db):
    """Convention "Dhaka"."""
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# --------------------------------------------------------------------------- #
# Conventions -> Named checks
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


def reread(db, x):
    """Convention "re-read X": expire, then SELECT the return by id."""
    db.expire_all()
    return db.scalar(select(SalesOrderReturn).where(SalesOrderReturn.id == x.id))


def snap(db, x):
    """Convention "unchanged(X)": every column of the re-read return."""
    row = reread(db, x)
    return {
        c.key: getattr(row, c.key)
        for c in sa_inspect(SalesOrderReturn).mapper.column_attrs
    }


def n(db, ws):
    """Convention "n(W)"."""
    return db.scalar(
        select(func.count())
        .select_from(SalesOrderReturn)
        .where(SalesOrderReturn.workspace_id == ws.id)
    )


def totals(db):
    """Convention "nothing written": row numbers of both tables, all workspaces."""
    return (
        db.scalar(select(func.count()).select_from(SalesOrderReturn)),
        db.scalar(select(func.count()).select_from(SalesOrderReturnItem)),
    )


class StatementRecorder:
    """Convention "Statement recorder": the SQL the session's connection sends while the block runs."""

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
        return [
            st for st in self.statements if st.lstrip().upper().startswith("SELECT")
        ]

    @property
    def written(self):
        return [
            st
            for st in self.statements
            if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]

    @property
    def sql(self):
        """The one SELECT sent; fails loudly unless there is exactly one."""
        [statement] = self.selects
        return statement

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        part = sql.split("ORDER BY", 1)[1]
        return part.split("LIMIT", 1)[0]

    @property
    def lock_part(self):
        sql = self.sql
        return sql.split("FOR UPDATE", 1)[1] if "FOR UPDATE" in sql else ""


# =========================================================================== #
# DAOSalesOrderReturn.generate_return_number
# =========================================================================== #


# [claude] SRT-GN-01
def test_srt_gn_01__no_return_gives_001(db, s):
    """SRT-GN-01 — no return yet gives SR-2026-001.
    Rules: generate_return_number R1, Returns."""
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-001"


# [claude] SRT-GN-02
def test_srt_gn_02__two_returns_give_003(db, s):
    """SRT-GN-02 — two returns give SR-2026-003.
    Rules: generate_return_number R1."""
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-002")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-003"


# [claude] SRT-GN-03
def test_srt_gn_03__every_status_counts(db, s):
    """SRT-GN-03 — pending, completed and voided returns all count.
    Rules: generate_return_number R2."""
    mk_return(db, s, "SR-2026-001")
    mk_return(
        db, s, "SR-2026-002", status="completed", completed_at=T2, completed_by=s.U1.id
    )
    mk_return(db, s, "SR-2026-003", status="voided", updated_at=T2)
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-004"


# [claude] SRT-GN-04
def test_srt_gn_04__non_numeric_tail_counts(db, s):
    """SRT-GN-04 — a hand-made number with a non-numeric tail counts as one.
    Rules: generate_return_number R2."""
    mk_return(db, s, "SR-2026-XYZ")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-002"


# [claude] SRT-GN-05
def test_srt_gn_05__w0_and_w2_not_counted_for_w1(db, s):
    """SRT-GN-05 — returns of W0 and of W2 are not counted for W1.
    Rules: generate_return_number R3."""
    mk_return(db, s, "SR-2026-101", of="W0")
    mk_return(db, s, "SR-2026-102", of="W0")
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-201", of="W2")
    mk_return(db, s, "SR-2026-202", of="W2")
    mk_return(db, s, "SR-2026-203", of="W2")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-002"


# [claude] SRT-GN-06
def test_srt_gn_06__w0_and_w1_not_counted_for_w2(db, s):
    """SRT-GN-06 — asked for W2, the returns of W0 and W1 are not counted.
    Rules: generate_return_number R3."""
    mk_return(db, s, "SR-2026-101", of="W0")
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-002")
    mk_return(db, s, "SR-2026-201", of="W2")
    result = dao.generate_return_number(db, workspace_id=s.W2.id, year=2026)
    # Then 1
    assert result == "SR-2026-002"


# [claude] SRT-GN-07
def test_srt_gn_07__w1_and_w2_not_counted_for_w0(db, s):
    """SRT-GN-07 — asked for W0, the returns of W1 and W2 are not counted.
    Rules: generate_return_number R3."""
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-201", of="W2")
    mk_return(db, s, "SR-2026-202", of="W2")
    result = dao.generate_return_number(db, workspace_id=s.W0.id, year=2026)
    # Then 1
    assert result == "SR-2026-001"


# [claude] SRT-GN-08
def test_srt_gn_08__unknown_workspace_gives_001(db, s):
    """SRT-GN-08 — an unknown workspace gives -001.
    Rules: generate_return_number R3, Inputs (workspace_id not checked)."""
    mk_return(db, s, "SR-2026-001")
    result = dao.generate_return_number(db, workspace_id=MISSING, year=2026)
    # Then 1
    assert result == "SR-2026-001"


# [claude] SRT-GN-09
def test_srt_gn_09__other_years_not_counted(db, s):
    """SRT-GN-09 — the years before and after are not counted.
    Rules: generate_return_number R3."""
    mk_return(db, s, "SR-2025-001")
    mk_return(db, s, "SR-2027-001")
    mk_return(db, s, "SR-2027-002")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-001"


# [claude] SRT-GN-10
def test_srt_gn_10__year_2099(db, s):
    """SRT-GN-10 — year 2099 with rows of 2026 gives SR-2099-001.
    Rules: generate_return_number R3, Inputs (year not range-checked)."""
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-002")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2099)
    # Then 1
    assert result == "SR-2099-001"


# [claude] SRT-GN-11
def test_srt_gn_11__year_1_as_written(db, s):
    """SRT-GN-11 — year 1 is used as written, and SR-10- does not count for it.
    Rules: generate_return_number R1, Inputs (year)."""
    mk_return(db, s, "SR-10-001")
    mk_return(db, s, "SR-1-001")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=1)
    # Then 1
    assert result == "SR-1-002"


# [claude] SRT-GN-12
def test_srt_gn_12__exact_prefix_only(db, s):
    """SRT-GN-12 — only numbers that start with exactly SR-2026- count.
    Rules: generate_return_number R1."""
    for number in (
        "XSR-2026-001",
        "sr-2026-002",
        " SR-2026-003",
        "PR-2026-004",
        "SR_2026-005",
        "SR-20261-006",
        "SR-2026-007",
    ):
        mk_return(db, s, number)
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-002"


# [claude] SRT-GN-13
def test_srt_gn_13__009_then_010(db, s):
    """SRT-GN-13 — eight returns give -009 and nine give -010.
    Rules: generate_return_number R4."""
    for k in range(1, 9):
        db.add(
            SalesOrderReturn(
                workspace_id=s.W1.id,
                sales_order_id=s.SO2.id,
                return_number=f"SR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
                created_at=T1,
            )
        )
    db.flush()
    r8 = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    db.add(
        SalesOrderReturn(
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            return_number="SR-2026-009",
            return_type="refund",
            created_by=s.U1.id,
            created_at=T1,
        )
    )
    db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert r8 == "SR-2026-009"
    # Then 2
    assert result == "SR-2026-010"


# [claude] SRT-GN-14
def test_srt_gn_14__999_then_1000(db, s):
    """SRT-GN-14 — 998 returns give -999 and 999 give -1000.
    Rules: generate_return_number R4."""
    for k in range(1, 999):
        db.add(
            SalesOrderReturn(
                workspace_id=s.W1.id,
                sales_order_id=s.SO2.id,
                return_number=f"SR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
                created_at=T1,
            )
        )
    db.flush()
    r998 = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    db.add(
        SalesOrderReturn(
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            return_number="SR-2026-999",
            return_type="refund",
            created_by=s.U1.id,
            created_at=T1,
        )
    )
    db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert r998 == "SR-2026-999"
    # Then 2
    assert result == "SR-2026-1000"


# [claude] SRT-GN-15
def test_srt_gn_15__writes_nothing(db, s):
    """SRT-GN-15 — writes nothing: a pending return is not counted and stays pending, an unflushed edit stays unflushed.
    Rules: generate_return_number R5."""
    b = mk_return(db, s, "SR-2025-001")
    b.notes = "Edited"
    p = SalesOrderReturn(
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        return_number="SR-2026-001",
        return_type="refund",
        created_by=s.U1.id,
        created_at=T1,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-001"
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
    # Then 8
    assert totals(db) == before


# [claude] SRT-GN-16
def test_srt_gn_16__one_select_on_returns(db, s):
    """SRT-GN-16 — the count reads only the returns table, in one SELECT.
    Rules: generate_return_number R1, R5."""
    mk_return(db, s, "SR-2026-001")
    with StatementRecorder(db) as rec:
        result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-002"
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "sales_order_returns" in rec.sql
    # Then 4
    assert "sales_orders" not in rec.sql
    # Then 5
    assert "FOR UPDATE" not in rec.sql


# [claude] SRT-GN-17
def test_srt_gn_17__prefix_case_sensitive(db, s):
    """SRT-GN-17 — the prefix is case-sensitive: lower- and mixed-case numbers do not count.
    Rules: generate_return_number R1a."""
    mk_return(db, s, "sr-2026-001")
    mk_return(db, s, "Sr-2026-002")
    mk_return(db, s, "sR-2026-003")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "SR-2026-001"


# =========================================================================== #
# DAOSalesOrderReturn.create_with_user
# =========================================================================== #


# [claude] SRT-CW-01
def test_srt_cw_01__created_pending_with_fields(db, s):
    """SRT-CW-01 — a return is created pending with the given fields and number -001.
    Rules: create_with_user R1, R2a, Returns, Side effects."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U2.id,
            return_type="replace",
            reason="Damaged",
            notes="Box torn",
        )
    # Then 1
    assert isinstance(result, SalesOrderReturn)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.sales_order_id == s.SO2.id
    assert row.return_number == "SR-2026-001"
    assert row.return_type == "replace"
    assert row.reason == "Damaged"
    assert row.notes == "Box torn"
    # Then 4
    row = reread(db, result)
    assert row.created_by == s.U2.id
    assert row.status == "pending"
    assert row.paid is False
    # Then 5
    row = reread(db, result)
    assert row.invoice_id is None
    assert row.completed_at is None
    assert row.completed_by is None
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 6
    assert n(db, s.W1) == 1
    # Then 7
    assert db.scalar(select(func.count()).select_from(SalesOrderReturnItem)) == 0


# [claude] SRT-CW-02
def test_srt_cw_02__second_gets_002(db, s):
    """SRT-CW-02 — the second return of the workspace gets -002.
    Rules: create_with_user R2a."""
    mk_return(db, s, "SR-2026-001")
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "SR-2026-002"
    # Then 3
    assert n(db, s.W1) == 2


# [claude] SRT-CW-03
def test_srt_cw_03__other_workspaces_do_not_count(db, s):
    """SRT-CW-03 — returns of W0 and W2 do not count: W1's first return is -001.
    Rules: create_with_user R2a, generate_return_number R3."""
    mk_return(db, s, "SR-2026-101", of="W0")
    mk_return(db, s, "SR-2026-201", of="W2")
    mk_return(db, s, "SR-2026-202", of="W2")
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "SR-2026-001"
    assert row.workspace_id == s.W1.id


# [claude] SRT-CW-04
def test_srt_cw_04__reason_and_notes_default_null(db, s):
    """SRT-CW-04 — reason and notes not passed are stored as NULL.
    Rules: create_with_user R1, Inputs (defaults)."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.reason is None
    assert row.notes is None


# [claude] SRT-CW-05
def test_srt_cw_05__empty_and_spaces_kept(db, s):
    """SRT-CW-05 — empty reason and notes stay empty strings, spaces are kept.
    Rules: create_with_user R1, Inputs (reason, notes as given)."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
            reason="",
            notes="  Late ",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.reason == ""
    assert row.notes == "  Late "


# [claude] SRT-CW-06
def test_srt_cw_06__any_return_type_stored(db, s):
    """SRT-CW-06 — any return_type is stored as given.
    Rules: create_with_user R1, Inputs (return_type not checked)."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="banana",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_type == "banana"


# [claude] SRT-CW-07
def test_srt_cw_07__created_at_naive_utc(db, s):
    """SRT-CW-07 — created_at is naive UTC at flush.
    Rules: create_with_user R1."""
    before = utcnow()
    result = dao.create_with_user(
        db,
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        user_id=s.U1.id,
        return_type="refund",
    )
    after = utcnow()
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_at.tzinfo is None
    # Then 3
    assert before <= row.created_at <= after
    # Then 4
    assert row.return_number.endswith("-001")


# [claude] SRT-CW-08
def test_srt_cw_08__created_at_naive_utc_under_dhaka(db, s):
    """SRT-CW-08 — created_at is naive UTC also when the database runs in Asia/Dhaka.
    Rules: create_with_user R1."""
    dhaka(db)
    before = utcnow()
    result = dao.create_with_user(
        db,
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        user_id=s.U1.id,
        return_type="refund",
    )
    after = utcnow()
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.created_at.tzinfo is None
    # Then 3
    assert before <= row.created_at <= after


# [claude] SRT-CW-09
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2422: a return number's year comes from the server's local clock",
)
def test_srt_cw_09__utc_year_local_already_next(db, s):
    """SRT-CW-09 — the year is UTC's, when the local clock is already in the next year.
    Rules: create_with_user R2 [BUG-2422]."""
    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "SR-2026-001"


# [claude] SRT-CW-10
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2422: a return number's year comes from the server's local clock",
)
def test_srt_cw_10__utc_year_local_still_old(db, s):
    """SRT-CW-10 — the year is UTC's, when the local clock is still in the old year.
    Rules: create_with_user R2 [BUG-2422]."""
    mk_return(db, s, "SR-2026-001")
    with clock(datetime(2026, 12, 31, 23, 0), datetime(2027, 1, 1, 1, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "SR-2027-001"


# [claude] SRT-CW-11
def test_srt_cw_11__year_2031(db, s):
    """SRT-CW-11 — the current year goes into the number: both clocks in 2031 give SR-2031-001.
    Rules: create_with_user R2, R2a."""
    mk_return(db, s, "SR-2026-001")
    with clock(datetime(2031, 1, 1, 5, 0), datetime(2031, 1, 1, 5, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "SR-2031-001"


# [claude] SRT-CW-12
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2420: return numbers unique across all workspaces instead of per workspace",
)
def test_srt_cw_12__number_held_by_w0(db, s):
    """SRT-CW-12 — W1's first return is -001 although W0 already has SR-2026-001.
    Rules: create_with_user R4 [BUG-2420]."""
    mk_return(db, s, "SR-2026-001", of="W0")
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "SR-2026-001"
    assert row.workspace_id == s.W1.id
    # Then 3
    assert n(db, s.W1) == 1
    # Then 4
    assert n(db, s.W0) == 1


# [claude] SRT-CW-13
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2420: return numbers unique across all workspaces instead of per workspace",
)
def test_srt_cw_13__number_held_by_w2(db, s):
    """SRT-CW-13 — W1's first return is -001 although W2 already has SR-2026-001.
    Rules: create_with_user R4 [BUG-2420]."""
    mk_return(db, s, "SR-2026-001", of="W2")
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "SR-2026-001"
    assert row.workspace_id == s.W1.id
    # Then 3
    assert n(db, s.W1) == 1
    # Then 4
    assert n(db, s.W2) == 1


# [claude] SRT-CW-14
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2421: two returns started at once can get the same number "
    "(R3a: a taken next number fails the call)",
)
def test_srt_cw_14__taken_number_gets_free_one(db, s):
    """SRT-CW-14 — a computed number already taken in the same workspace does not fail the call: a free number is used.
    Rules: create_with_user R3a [BUG-2421]."""
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-002")
    mk_return(db, s, "SR-2026-004")
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505 on -004)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number.startswith("SR-2026-")
    # Then 3
    assert row.return_number not in {"SR-2026-001", "SR-2026-002", "SR-2026-004"}
    # Then 4
    assert (
        db.scalar(
            select(func.count())
            .select_from(SalesOrderReturn)
            .where(
                SalesOrderReturn.workspace_id == s.W1.id,
                SalesOrderReturn.return_number == result.return_number,
            )
        )
        == 1
    )
    # Then 5
    assert n(db, s.W1) == 4


# [claude] SRT-CW-15
def test_srt_cw_15__user_none_fails_not_null(db, s):
    """SRT-CW-15 — user_id None fails NOT NULL at the flush and saves nothing.
    Rules: create_with_user R5, Errors (user_id is None)."""
    before = totals(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=s.W1.id,
                    sales_order_id=s.SO2.id,
                    user_id=None,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert "created_by" in str(exc.value.orig)
    # Then 3
    assert n(db, s.W1) == 0
    # Then 4
    assert totals(db) == before


# [claude] SRT-CW-16
def test_srt_cw_16__unknown_order_fails_fk(db, s):
    """SRT-CW-16 — an unknown sales order fails the foreign key at the flush.
    Rules: create_with_user R5, Errors (unknown sales_order_id)."""
    before = totals(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=s.W1.id,
                    sales_order_id=MISSING,
                    user_id=s.U1.id,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert "sales_order_id" in str(exc.value.orig)
    # Then 3
    assert n(db, s.W1) == 0
    # Then 4
    assert totals(db) == before


# [claude] SRT-CW-17
def test_srt_cw_17__unknown_workspace_fails_fk(db, s):
    """SRT-CW-17 — an unknown workspace fails the foreign key at the flush.
    Rules: create_with_user R5, Errors (unknown workspace_id)."""
    before = totals(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=MISSING,
                    sales_order_id=s.SO2.id,
                    user_id=s.U1.id,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert "workspace_id" in str(exc.value.orig)
    # Then 3
    assert totals(db) == before


# [claude] SRT-CW-18
def test_srt_cw_18__flushed_not_committed(db, s):
    """SRT-CW-18 — flushed, not committed: a rollback removes the return.
    Rules: create_with_user R5, Returns."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock(JUNE, JUNE):
            result = dao.create_with_user(
                db,
                workspace_id=s.W1.id,
                sales_order_id=s.SO2.id,
                user_id=s.U1.id,
                return_type="refund",
            )
    # Then 1
    assert result.id is not None
    # Then 2
    assert n(db, s.W1) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert n(db, s.W1) == 0


# [claude] SRT-CW-19
def test_srt_cw_19__one_insert_only(db, s):
    """SRT-CW-19 — one INSERT into the returns table and nothing else is written.
    Rules: create_with_user Side effects."""
    b = mk_return(db, s, "SR-2025-001")
    before_b = snap(db, b)
    with clock(JUNE, JUNE), StatementRecorder(db) as rec:
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rec.written) == 1
    # Then 3
    assert rec.written[0].upper().startswith("INSERT INTO SALES_ORDER_RETURNS")
    # Then 4
    assert snap(db, b) == before_b


# [claude] SRT-CW-20
def test_srt_cw_20__pending_and_unpaid_always(db, s):
    """SRT-CW-20 — the status is pending whatever the database default, and paid is False.
    Rules: create_with_user R1."""
    mk_return(db, s, "SR-2026-001", status="completed", paid=True)
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            sales_order_id=s.SO2.id,
            user_id=s.U3.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.status == "pending"
    assert row.paid is False
    assert row.created_by == s.U3.id
    assert row.return_number == "SR-2026-002"


# [claude] SRT-CW-21
def test_srt_cw_21__same_number_same_workspace_refused(db, s):
    """SRT-CW-21 — the database refuses a second row with the same number in one workspace (direct insert).
    Rules: create_with_user R4 (database fact), R3a, Errors (number already used)."""
    a = mk_return(db, s, "SR-2026-001")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(
                SalesOrderReturn(
                    workspace_id=s.W1.id,
                    sales_order_id=s.SO2.id,
                    return_number="SR-2026-001",
                    return_type="refund",
                    created_by=s.U1.id,
                    created_at=T2,
                )
            )
            db.flush()
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert n(db, s.W1) == 1
    # Then 3
    row = reread(db, a)
    assert row.return_number == "SR-2026-001"
    assert row.created_at == T1


# =========================================================================== #
# DAOSalesOrderReturn.get_by_sales_order
# =========================================================================== #


# [claude] SRT-BS-01
def test_srt_bs_01__every_status_newest_first(db, s):
    """SRT-BS-01 — every return of the order is returned, whatever its status, newest first.
    Rules: get_by_sales_order R1, R3."""
    a = mk_return(db, s, "SR-2026-001", created_at=T2)
    b = mk_return(
        db,
        s,
        "SR-2026-002",
        created_at=T3,
        status="completed",
        completed_at=T4,
        completed_by=s.U1.id,
    )
    c = mk_return(db, s, "SR-2026-003", created_at=T1, status="voided", updated_at=T2)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] SRT-BS-02
def test_srt_bs_02__other_orders_not_returned(db, s):
    """SRT-BS-02 — returns of the orders with a lower and a higher id are not returned.
    Rules: get_by_sales_order R2."""
    mk_return(db, s, "SR-2026-001", sales_order_id=s.SO1.id, created_at=T3)
    b = mk_return(db, s, "SR-2026-002", created_at=T1)
    mk_return(db, s, "SR-2026-003", sales_order_id=s.SO3.id, created_at=T4)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [b.id]


# [claude] SRT-BS-03
def test_srt_bs_03__other_workspaces_same_order_not_returned(db, s):
    """SRT-BS-03 — returns of W0 and W2 on the same order id are not returned.
    Rules: get_by_sales_order R2."""
    mk_return(db, s, "SR-2026-101", of="W0", sales_order_id=s.SO2.id, created_at=T4)
    a = mk_return(db, s, "SR-2026-001", created_at=T1)
    mk_return(db, s, "SR-2026-201", of="W2", sales_order_id=s.SO2.id, created_at=T5)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]


# [claude] SRT-BS-04
def test_srt_bs_04__wrong_workspace_empty(db, s):
    """SRT-BS-04 — the right order with another workspace's id returns an empty list.
    Rules: get_by_sales_order R2."""
    mk_return(db, s, "SR-2026-001")
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W2.id)
    # Then 1
    assert result == []


# [claude] SRT-BS-05
def test_srt_bs_05__w0_gets_only_its_own(db, s):
    """SRT-BS-05 — asked for W0, only W0's return on the order is returned.
    Rules: get_by_sales_order R2."""
    z1 = mk_return(
        db, s, "SR-2026-101", of="W0", sales_order_id=s.SO2.id, created_at=T1
    )
    mk_return(db, s, "SR-2026-001", created_at=T2)
    mk_return(db, s, "SR-2026-201", of="W2", sales_order_id=s.SO2.id, created_at=T3)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W0.id)
    # Then 1
    assert ids(result) == [z1.id]


# [claude] SRT-BS-06
def test_srt_bs_06__no_returns_and_unknown_order_empty(db, s):
    """SRT-BS-06 — an order without returns and an unknown order return empty lists.
    Rules: get_by_sales_order R2."""
    mk_return(db, s, "SR-2026-001")
    result = (
        dao.get_by_sales_order(db, sales_order_id=s.SO3.id, workspace_id=s.W1.id),
        dao.get_by_sales_order(db, sales_order_id=MISSING, workspace_id=s.W1.id),
    )
    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == []


# [claude] SRT-BS-07
def test_srt_bs_07__newest_first_whatever_ids(db, s):
    """SRT-BS-07 — newest first whatever the ids: an older return with a higher id comes last.
    Rules: get_by_sales_order R3."""
    a = mk_return(db, s, "SR-2026-009", created_at=T3)
    b = mk_return(db, s, "SR-2026-002", created_at=T4, created_by=s.U3.id)
    c = mk_return(
        db, s, "SR-2026-003", created_at=T1 + timedelta(minutes=30), created_by=s.U2.id
    )
    d = mk_return(db, s, "SR-2026-004", created_at=T1)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [b.id, a.id, c.id, d.id]


# [claude] SRT-BS-08
def test_srt_bs_08__tie_sits_between(db, s):
    """SRT-BS-08 — on a tie both returns sit between the newer and the older one.
    Rules: get_by_sales_order R3."""
    a = mk_return(db, s, "SR-2026-001", created_at=T2)
    nn = mk_return(db, s, "SR-2026-002", created_at=T3)
    b = mk_return(db, s, "SR-2026-003", created_at=T2)
    o = mk_return(db, s, "SR-2026-004", created_at=T1)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == nn.id
    # Then 3
    assert {result[1].id, result[2].id} == {a.id, b.id}
    # Then 4
    assert result[3].id == o.id


# [claude] SRT-BS-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2423: an order's returns of one creation time come back in no fixed order",
)
def test_srt_bs_09__tie_highest_id_first(db, s):
    """SRT-BS-09 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: get_by_sales_order R3 [BUG-2423]."""
    a = mk_return(db, s, "SR-2026-001", created_at=T2)
    b = mk_return(db, s, "SR-2026-002", created_at=T2)
    c = mk_return(db, s, "SR-2026-003", created_at=T2)
    d = mk_return(db, s, "SR-2026-004", created_at=T3)
    seqscan(db)
    bump(db, a)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] SRT-BS-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2423: an order's returns of one creation time come back in no fixed order",
)
def test_srt_bs_10__tie_id_decides(db, s):
    """SRT-BS-10 — on a tie the id decides, not the number, status or creator.
    Rules: get_by_sales_order R3 [BUG-2423]."""
    a = mk_return(
        db,
        s,
        "SR-2026-009",
        created_at=T2,
        status="voided",
        updated_at=T2,
        created_by=s.U3.id,
    )
    b = mk_return(db, s, "SR-2026-001", created_at=T2, created_by=s.U1.id)
    c = mk_return(
        db, s, "SR-2026-005", created_at=T2, status="completed", created_by=s.U2.id
    )
    seqscan(db)
    bump(db, a)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] SRT-BS-11
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2423: an order's returns of one creation time come back in no fixed order",
)
def test_srt_bs_11__orders_by_created_at_then_id_desc(db, s):
    """SRT-BS-11 — the query orders by created_at, then id, both descending.
    Rules: get_by_sales_order R3 [BUG-2423]."""
    a = mk_return(db, s, "SR-2026-001")
    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "created_at" in rec.order_part
    # Then 4
    assert ".id" in rec.order_part
    # Then 5
    assert rec.order_part.index("created_at") < rec.order_part.index(".id")
    # Then 6
    assert rec.order_part.upper().count("DESC") == 2


# [claude] SRT-BS-12
def test_srt_bs_12__no_paging(db, s):
    """SRT-BS-12 — no paging: 101 returns all come back.
    Rules: get_by_sales_order R1 (no paging)."""
    for k in range(1, 102):
        db.add(
            SalesOrderReturn(
                workspace_id=s.W1.id,
                sales_order_id=s.SO2.id,
                return_number=f"SR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
                created_at=T1 + timedelta(minutes=k),
            )
        )
    db.flush()
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].return_number == "SR-2026-101"
    # Then 3
    assert result[100].return_number == "SR-2026-001"


# [claude] SRT-BS-13
def test_srt_bs_13__writes_nothing(db, s):
    """SRT-BS-13 — writes nothing: a pending return is not listed and stays pending, an unflushed edit stays unflushed.
    Rules: get_by_sales_order Side effects."""
    a = mk_return(db, s, "SR-2026-001")
    a.notes = "Edited"
    p = SalesOrderReturn(
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        return_number="SR-2026-002",
        return_type="refund",
        created_by=s.U1.id,
        created_at=T2,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert totals(db) == before


# [claude] SRT-BS-14
def test_srt_bs_14__no_join_of_sales_order(db, s):
    """SRT-BS-14 — the list does not join the sales order.
    Rules: get_by_sales_order R1, R2."""
    a = mk_return(db, s, "SR-2026-001")
    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "sales_orders" not in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] SRT-BS-15
def test_srt_bs_15__invoiced_and_paid_listed(db, s):
    """SRT-BS-15 — a return with an invoice and paid is listed like any other.
    Rules: get_by_sales_order R1."""
    a = mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id, paid=True, created_at=T2)
    b = mk_return(db, s, "SR-2026-002", created_at=T1)
    result = dao.get_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id, b.id]


# =========================================================================== #
# DAOSalesOrderReturn.get_open_by_sales_order
# =========================================================================== #


# [claude] SRT-OP-01
def test_srt_op_01__only_pending(db, s):
    """SRT-OP-01 — only the pending returns are returned.
    Rules: get_open_by_sales_order R1."""
    a = mk_return(db, s, "SR-2026-001")
    mk_return(
        db, s, "SR-2026-002", status="completed", completed_at=T2, completed_by=s.U1.id
    )
    mk_return(db, s, "SR-2026-003", status="voided", updated_at=T2)
    d = mk_return(db, s, "SR-2026-004", created_at=T2)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert idset(result) == {a.id, d.id}
    # Then 2
    assert len(result) == 2


# [claude] SRT-OP-02
def test_srt_op_02__exactly_pending(db, s):
    """SRT-OP-02 — the status must be exactly "pending": case, spaces and look-alikes do not match.
    Rules: get_open_by_sales_order R1."""
    for k, status in enumerate(
        (
            "Pending",
            "PENDING",
            " pending",
            "pending ",
            "pend",
            "xpendingx",
            "pending_old",
        ),
        start=1,
    ):
        mk_return(db, s, f"SR-2026-{k:03d}", status=status)
    k_row = mk_return(db, s, "SR-2026-008")
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [k_row.id]


# [claude] SRT-OP-03
def test_srt_op_03__no_pending_empty(db, s):
    """SRT-OP-03 — no pending return gives an empty list.
    Rules: get_open_by_sales_order R1."""
    mk_return(
        db, s, "SR-2026-002", status="completed", completed_at=T2, completed_by=s.U1.id
    )
    mk_return(db, s, "SR-2026-003", status="voided", updated_at=T2)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] SRT-OP-04
def test_srt_op_04__other_orders_not_returned(db, s):
    """SRT-OP-04 — pending returns of the orders with a lower and a higher id are not returned.
    Rules: get_open_by_sales_order R2."""
    mk_return(db, s, "SR-2026-001", sales_order_id=s.SO1.id)
    b = mk_return(db, s, "SR-2026-002")
    mk_return(db, s, "SR-2026-003", sales_order_id=s.SO3.id)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [b.id]


# [claude] SRT-OP-05
def test_srt_op_05__other_workspaces_not_returned(db, s):
    """SRT-OP-05 — pending returns of W0 and W2 on the same order id are not returned.
    Rules: get_open_by_sales_order R2."""
    mk_return(db, s, "SR-2026-101", of="W0", sales_order_id=s.SO2.id)
    a = mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-201", of="W2", sales_order_id=s.SO2.id)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] SRT-OP-06
def test_srt_op_06__wrong_workspace_or_unknown_empty(db, s):
    """SRT-OP-06 — another workspace's id or an unknown order returns empty lists.
    Rules: get_open_by_sales_order R2."""
    mk_return(db, s, "SR-2026-001")
    result = (
        dao.get_open_by_sales_order(db, sales_order_id=s.SO2.id, workspace_id=s.W2.id),
        dao.get_open_by_sales_order(db, sales_order_id=MISSING, workspace_id=s.W1.id),
    )
    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == []


# [claude] SRT-OP-07
@pytest.mark.xfail(
    strict=False, reason="BUG-2424: an order's open returns have no sort order"
)
def test_srt_op_07__id_ascending_after_update(db, s):
    """SRT-OP-07 — pending returns come back by id ascending, when the lowest id was updated.
    Rules: get_open_by_sales_order R3 [BUG-2424]."""
    a = mk_return(db, s, "SR-2026-001", created_at=T3)
    b = mk_return(db, s, "SR-2026-002", created_at=T1)
    c = mk_return(db, s, "SR-2026-003", created_at=T2)
    seqscan(db)
    bump(db, a)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] SRT-OP-08
@pytest.mark.xfail(
    strict=True, reason="BUG-2424: an order's open returns have no sort order"
)
def test_srt_op_08__orders_by_id_ascending(db, s):
    """SRT-OP-08 — the query orders by id ascending.
    Rules: get_open_by_sales_order R3 [BUG-2424]."""
    a = mk_return(db, s, "SR-2026-001")
    with StatementRecorder(db) as rec:
        result = dao.get_open_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert ".id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert "created_at" not in rec.order_part


# [claude] SRT-OP-09
def test_srt_op_09__writes_nothing(db, s):
    """SRT-OP-09 — writes nothing: a pending new return is not listed, an unflushed edit stays unflushed.
    Rules: get_open_by_sales_order Side effects."""
    a = mk_return(db, s, "SR-2026-001")
    a.status = "voided"
    p = SalesOrderReturn(
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        return_number="SR-2026-002",
        return_type="refund",
        created_by=s.U1.id,
        created_at=T2,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_open_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert totals(db) == before


# [claude] SRT-OP-10
def test_srt_op_10__no_join_no_lock(db, s):
    """SRT-OP-10 — the list does not join the sales order and takes no lock.
    Rules: get_open_by_sales_order R1, R2."""
    a = mk_return(db, s, "SR-2026-001")
    with StatementRecorder(db) as rec:
        result = dao.get_open_by_sales_order(
            db, sales_order_id=s.SO2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "sales_orders" not in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] SRT-OP-11
def test_srt_op_11__w0_gets_only_its_own(db, s):
    """SRT-OP-11 — asked for W0, only W0's pending return on the order is returned.
    Rules: get_open_by_sales_order R2."""
    z1 = mk_return(db, s, "SR-2026-101", of="W0", sales_order_id=s.SO2.id)
    mk_return(db, s, "SR-2026-001")
    mk_return(db, s, "SR-2026-201", of="W2", sales_order_id=s.SO2.id)
    result = dao.get_open_by_sales_order(
        db, sales_order_id=s.SO2.id, workspace_id=s.W0.id
    )
    # Then 1
    assert ids(result) == [z1.id]


# =========================================================================== #
# DAOSalesOrderReturn.get_by_invoice_id
# =========================================================================== #


# [claude] SRT-IV-01
def test_srt_iv_01__found_by_credit_note(db, s):
    """SRT-IV-01 — the return whose credit note is the invoice is returned.
    Rules: get_by_invoice_id R1."""
    mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    b = mk_return(
        db,
        s,
        "SR-2026-002",
        invoice_id=s.INV2.id,
        status="completed",
        completed_at=T2,
        completed_by=s.U1.id,
    )
    mk_return(db, s, "SR-2026-003", invoice_id=s.INV3.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, SalesOrderReturn)
    # Then 2
    assert result.id == b.id


# [claude] SRT-IV-02
def test_srt_iv_02__voided_still_found(db, s):
    """SRT-IV-02 — a voided return is still found by its credit note.
    Rules: get_by_invoice_id R1."""
    a = mk_return(
        db, s, "SR-2026-001", invoice_id=s.INV2.id, status="voided", updated_at=T2
    )
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id


# [claude] SRT-IV-03
def test_srt_iv_03__neighbour_invoices_do_not_answer(db, s):
    """SRT-IV-03 — returns on the invoices with a lower and a higher id do not answer.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    mk_return(db, s, "SR-2026-003", invoice_id=s.INV3.id)
    mk_return(db, s, "SR-2026-004")
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] SRT-IV-04
def test_srt_iv_04__other_workspaces_do_not_answer(db, s):
    """SRT-IV-04 — returns of W0 and W2 holding the invoice do not answer for W1.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "SR-2026-101", of="W0", invoice_id=s.INV2.id)
    mk_return(db, s, "SR-2026-201", of="W2", invoice_id=s.INV2.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] SRT-IV-05
def test_srt_iv_05__w1_gets_its_own(db, s):
    """SRT-IV-05 — with W0, W1 and W2 returns on the invoice, W1 gets its own.
    Rules: get_by_invoice_id R1, R2."""
    mk_return(db, s, "SR-2026-101", of="W0", invoice_id=s.INV2.id)
    a = mk_return(db, s, "SR-2026-001", invoice_id=s.INV2.id)
    mk_return(db, s, "SR-2026-201", of="W2", invoice_id=s.INV2.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id


# [claude] SRT-IV-06
def test_srt_iv_06__unused_and_unknown_invoice_none(db, s):
    """SRT-IV-06 — an invoice no return points to, and an unknown invoice, give None.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    result = (
        dao.get_by_invoice_id(db, invoice_id=s.INV3.id, workspace_id=s.W1.id),
        dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=s.W1.id),
    )
    # Then 1
    assert result[0] is None
    # Then 2
    assert result[1] is None


# [claude] SRT-IV-07
def test_srt_iv_07__two_on_one_invoice_one_returned(db, s):
    """SRT-IV-07 — two returns on one invoice: one of them is returned.
    Rules: get_by_invoice_id R3."""
    a = mk_return(db, s, "SR-2026-001", invoice_id=s.INV2.id)
    b = mk_return(db, s, "SR-2026-002", invoice_id=s.INV2.id)
    result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is not None
    # Then 2
    assert result.id in {a.id, b.id}


# [claude] SRT-IV-08
def test_srt_iv_08__writes_nothing(db, s):
    """SRT-IV-08 — writes nothing: a pending return is not found, an unflushed edit stays unflushed.
    Rules: get_by_invoice_id Side effects."""
    a = mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    a.paid = True
    p = SalesOrderReturn(
        workspace_id=s.W1.id,
        sales_order_id=s.SO2.id,
        return_number="SR-2026-002",
        return_type="refund",
        created_by=s.U1.id,
        created_at=T1,
        invoice_id=s.INV2.id,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert totals(db) == before


# [claude] SRT-IV-09
def test_srt_iv_09__reads_only_returns_no_lock(db, s):
    """SRT-IV-09 — the lookup reads only the returns table and takes no lock.
    Rules: get_by_invoice_id R1."""
    a = mk_return(db, s, "SR-2026-001", invoice_id=s.INV2.id)
    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=s.INV2.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "account_invoices" not in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] SRT-IV-10
def test_srt_iv_10__none_finds_return_whose_note_was_deleted(db, s):
    """SRT-IV-10 — invoice_id None finds the workspace's return whose credit note was deleted.
    Rules: get_by_invoice_id R4, R2."""
    mk_return(db, s, "SR-2026-101", of="W0")
    mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    b = mk_return(
        db,
        s,
        "SR-2026-002",
        invoice_id=s.INV3.id,
        status="completed",
        completed_at=T2,
        completed_by=s.U1.id,
    )
    mk_return(db, s, "SR-2026-201", of="W2")
    db.execute(text("DELETE FROM account_invoices WHERE id = :i"), {"i": s.INV3.id})
    db.expire_all()
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result.id == b.id
    # Then 2
    assert result.invoice_id is None


# [claude] SRT-IV-11
def test_srt_iv_11__none_when_every_return_has_note(db, s):
    """SRT-IV-11 — invoice_id None gives None when every return of the workspace has a credit note.
    Rules: get_by_invoice_id R4."""
    mk_return(db, s, "SR-2026-101", of="W0")
    mk_return(db, s, "SR-2026-001", invoice_id=s.INV1.id)
    mk_return(db, s, "SR-2026-002", invoice_id=s.INV2.id)
    mk_return(db, s, "SR-2026-201", of="W2")
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# DAOSalesOrderReturnItem.get_by_return
# =========================================================================== #


# [claude] SRT-RI-01
def test_srt_ri_01__every_line(db, s):
    """SRT-RI-01 — every line of the return is returned, with and without a catalog item.
    Rules: get_by_return R1."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(db, s, r)
    b = mk_line(
        db,
        s,
        r,
        item_id=s.IT1.id,
        quantity_returned=Decimal("3.00"),
        unit_price=None,
        notes="Cracked",
    )
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {a.id, b.id}
    # Then 2
    assert len(result) == 2
    # Then 3
    assert all(isinstance(x, SalesOrderReturnItem) for x in result)


# [claude] SRT-RI-02
def test_srt_ri_02__other_returns_not_listed(db, s):
    """SRT-RI-02 — lines of the returns with a lower and a higher id are not returned.
    Rules: get_by_return R1."""
    ra = mk_return(db, s, "SR-2026-001")
    rb = mk_return(db, s, "SR-2026-002")
    rc = mk_return(db, s, "SR-2026-003")
    mk_line(db, s, ra)
    b = mk_line(db, s, rb)
    mk_line(db, s, rc)
    result = idao.get_by_return(db, return_id=rb.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [b.id]


# [claude] SRT-RI-03
def test_srt_ri_03__other_workspace_lines_not_listed(db, s):
    """SRT-RI-03 — lines of W0 and W2 on the same return are not returned.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "SR-2026-001")
    mk_line(db, s, r, workspace_id=s.W0.id)
    a = mk_line(db, s, r)
    mk_line(db, s, r, workspace_id=s.W2.id)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]


# [claude] SRT-RI-04
def test_srt_ri_04__empty_cases(db, s):
    """SRT-RI-04 — another workspace's id, a return without lines and an unknown return give empty lists.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "SR-2026-001")
    r2 = mk_return(db, s, "SR-2026-002")
    mk_line(db, s, r)
    result = (
        idao.get_by_return(db, return_id=r.id, workspace_id=s.W2.id),
        idao.get_by_return(db, return_id=r2.id, workspace_id=s.W1.id),
        idao.get_by_return(db, return_id=MISSING, workspace_id=s.W1.id),
    )
    # Then 1
    assert result[0] == []
    # Then 2
    assert result[1] == []
    # Then 3
    assert result[2] == []


# [claude] SRT-RI-05
def test_srt_ri_05__half_up_storage(db, s):
    """SRT-RI-05 — quantities and prices come back half up, as the columns store them.
    Rules: get_by_return R1; model facts (Numeric(15,2)); HR-15."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(
        db, s, r, quantity_returned=Decimal("2.125"), unit_price=Decimal("0.005")
    )
    db.expire_all()
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].quantity_returned == Decimal("2.13")
    # Then 3
    assert result[0].unit_price == Decimal("0.01")


# [claude] SRT-RI-06
def test_srt_ri_06__negative_away_from_zero_and_round_down(db, s):
    """SRT-RI-06 — a negative price rounds away from zero, and 2.124 rounds down.
    Rules: get_by_return R1; model facts (Numeric(15,2)); HR-15."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(
        db, s, r, quantity_returned=Decimal("2.124"), unit_price=Decimal("-1.005")
    )
    db.expire_all()
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].quantity_returned == Decimal("2.12")
    # Then 3
    assert result[0].unit_price == Decimal("-1.01")


# [claude] SRT-RI-07
@pytest.mark.xfail(strict=False, reason="BUG-2425: a return's lines have no sort order")
def test_srt_ri_07__id_ascending_after_update(db, s):
    """SRT-RI-07 — lines come back by id ascending, when the lowest id was updated.
    Rules: get_by_return R3 [BUG-2425]."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(db, s, r, quantity_returned=Decimal("3.00"))
    b = mk_line(db, s, r, quantity_returned=Decimal("1.00"))
    c = mk_line(db, s, r, quantity_returned=Decimal("2.00"))
    seqscan(db)
    bump_l(db, a)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] SRT-RI-08
@pytest.mark.xfail(strict=True, reason="BUG-2425: a return's lines have no sort order")
def test_srt_ri_08__orders_by_id_ascending(db, s):
    """SRT-RI-08 — the query orders by id ascending.
    Rules: get_by_return R3 [BUG-2425]."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(db, s, r)
    with StatementRecorder(db) as rec:
        result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert ".id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()


# [claude] SRT-RI-09
def test_srt_ri_09__writes_nothing(db, s):
    """SRT-RI-09 — writes nothing: a pending line is not listed, an unflushed edit stays unflushed.
    Rules: get_by_return Side effects."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(db, s, r)
    a.notes = "Edited"
    p = SalesOrderReturnItem(
        workspace_id=s.W1.id,
        return_id=r.id,
        so_item_id=s.L1.id,
        item_id=None,
        quantity_returned=Decimal("1.00"),
        unit_price=Decimal("2.00"),
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert totals(db) == before


# [claude] SRT-RI-10
def test_srt_ri_10__no_join_of_return(db, s):
    """SRT-RI-10 — the list does not join the return.
    Rules: get_by_return R1, R2."""
    r = mk_return(db, s, "SR-2026-001")
    a = mk_line(db, s, r)
    with StatementRecorder(db) as rec:
        result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "sales_order_returns" not in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] SRT-RI-11
def test_srt_ri_11__w2_gets_only_its_line(db, s):
    """SRT-RI-11 — asked for W2, only the W2 line on the return is returned.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "SR-2026-001")
    mk_line(db, s, r, workspace_id=s.W0.id)
    mk_line(db, s, r)
    x = mk_line(db, s, r, workspace_id=s.W2.id)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [x.id]
