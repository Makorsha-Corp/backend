"""Unit tests for app/dao/purchase_order_return.py.

Implements tests/unit/dao/purchase_order_return.cases.md (revision 2), one test
per case, in card order. Real Postgres session (`db` fixture). The only patch is
the Conventions' clock(L, U) in the `CW` cards; nothing else is mocked. The
commit spy of PRT-CW-16 wraps the real `db.commit`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()` and naive datetimes)
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.purchase_order_return import (
    purchase_order_return_dao,
    purchase_order_return_item_dao,
)
from app.models.item import Item
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_return import (
    PurchaseOrderReturn,
    PurchaseOrderReturnItem,
)
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao" (module-level singletons, not fixtures)
dao = purchase_order_return_dao
idao = purchase_order_return_item_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

# Convention "IVA, IVB, IVC": credit-note invoice ids no account_invoices row has
IVA, IVB, IVC = 880000001, 880000002, 880000003

# Convention "T1 ... T5" (naive)
T1 = datetime(2026, 3, 4, 9, 0)
T2 = datetime(2026, 3, 4, 10, 0)
T3 = datetime(2026, 3, 4, 11, 0)
T4 = datetime(2026, 3, 4, 12, 0)
T5 = datetime(2026, 3, 4, 13, 0)

# Convention "A CW card without a clock line runs under clock(JUNE, JUNE)"
JUNE = datetime(2026, 6, 1, 12, 0)


def high_id(db, table):
    """Convention "HIGH_ID(table)": max(greatest id or 0, last_value of <table>_id_seq) + 1000001."""
    max_id = db.scalar(text(f"SELECT coalesce(max(id), 0) FROM {table}"))
    last_value = db.scalar(text(f"SELECT last_value FROM {table}_id_seq"))
    return max(max_id, last_value) + 1000001


# --------------------------------------------------------------------------- #
# Conventions -> Externals: clock(L, U)
# --------------------------------------------------------------------------- #


@contextmanager
def clock(local, utc):
    """Convention "clock(L, U)": the module's `datetime.now()` returns L; both
    `app.dao.purchase_order_return.utcnow` (create=True) and `app.utils.time.utcnow` return U."""

    class _LocalClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return local

    with (
        patch("app.dao.purchase_order_return.datetime", _LocalClock),
        patch("app.dao.purchase_order_return.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> "unchecked" and the standing rows
# --------------------------------------------------------------------------- #


@contextmanager
def unchecked(db):
    """Convention "unchecked: ...": foreign-key triggers off for the rows built inside."""
    db.execute(text("SET LOCAL session_replication_role = replica"))
    yield
    db.execute(text("SET LOCAL session_replication_role = origin"))


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "Standing rows" 1-3, in their order. `s.W1`, `s.O2`, `s.I1`, ...
@pytest.fixture
def s(db):
    r = SimpleNamespace()
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2, r.U3 = make_profile(db), make_profile(db), make_profile(db)
    r.I1 = _add(
        db, Item(workspace_id=r.W1.id, name="Bolt", name_normalized="bolt", unit="pcs")
    )
    with unchecked(db):
        for name, ws, number in (
            ("O0", r.W0, "PO-T-000"),
            ("O1", r.W1, "PO-T-001"),
            ("O2", r.W1, "PO-T-002"),
            ("O3", r.W1, "PO-T-003"),
            ("O9", r.W2, "PO-T-009"),
        ):
            setattr(
                r,
                name,
                _add(
                    db,
                    PurchaseOrder(
                        workspace_id=ws.id,
                        po_number=number,
                        destination_type="storage",
                        destination_id=MISSING,
                        subtotal=0,
                        total_amount=0,
                        current_status_id=MISSING,
                        created_by=r.U1.id,
                    ),
                ),
            )
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Conventions "completed" and "voided" (on a return)
COMPLETED = {"status": "completed", "completed_at": T4}
VOIDED = {"status": "voided", "paid": False, "updated_at": T4}


def completed(s):
    return {**COMPLETED, "completed_by": s.U1.id}


def mk_return(db, s, number, **cols):
    """Convention "return N"; `cols` = the columns after "but" (`id=HIGH` for HIGH_ID).
    A return with `invoice_id` set is built unchecked. Added and flushed."""
    fields = {
        "workspace_id": s.W1.id,
        "purchase_order_id": s.O2.id,
        "return_number": number,
        "return_type": "refund",
        "created_by": s.U1.id,
    }
    fields.update(cols)
    if fields.get("id") == "HIGH":
        fields["id"] = high_id(db, "purchase_order_returns")
    if fields.get("invoice_id") is not None:
        with unchecked(db):
            return _add(db, PurchaseOrderReturn(**fields))
    return _add(db, PurchaseOrderReturn(**fields))


def mk_line(db, s, ret, **cols):
    """Convention "line of R" (always unchecked); `cols` = the columns after "but"
    (`id=HIGH` for HIGH_ID). Added and flushed."""
    fields = {
        "workspace_id": s.W1.id,
        "return_id": ret.id,
        "po_item_id": MISSING,
        "item_id": s.I1.id,
        "quantity_returned": Decimal("2.00"),
    }
    fields.update(cols)
    if fields.get("id") == "HIGH":
        fields["id"] = high_id(db, "purchase_order_return_items")
    with unchecked(db):
        return _add(db, PurchaseOrderReturnItem(**fields))


def bump_r(db, x):
    """Convention "bumpR(X)"."""
    db.execute(
        text("UPDATE purchase_order_returns SET reason = reason WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


def bump_l(db, x):
    """Convention "bumpL(X)" (unchecked)."""
    with unchecked(db):
        db.execute(
            text("UPDATE purchase_order_return_items SET notes = notes WHERE id = :i"),
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
    return db.scalar(select(PurchaseOrderReturn).where(PurchaseOrderReturn.id == x.id))


def snap(db, x):
    """Convention "unchanged(X)": every column of the re-read return."""
    row = reread(db, x)
    return {
        c.key: getattr(row, c.key)
        for c in sa_inspect(PurchaseOrderReturn).mapper.column_attrs
    }


def wcount(db, ws):
    """Convention "wcount(W)"."""
    return db.scalar(
        text("SELECT count(*) FROM purchase_order_returns WHERE workspace_id = :w"),
        {"w": ws.id},
    )


def totals(db):
    """Convention "nothing written": row numbers of both tables, all workspaces."""
    return (
        db.scalar(select(func.count()).select_from(PurchaseOrderReturn)),
        db.scalar(select(func.count()).select_from(PurchaseOrderReturnItem)),
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
        return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]

    @property
    def lock_part(self):
        sql = self.sql
        return sql.split("FOR UPDATE", 1)[1] if "FOR UPDATE" in sql else ""


def _w0(s):
    """The "but `workspace_id W0.id`, `purchase_order_id O0.id`" pair."""
    return {"workspace_id": s.W0.id, "purchase_order_id": s.O0.id}


def _w2(s):
    """The "but `workspace_id W2.id`, `purchase_order_id O9.id`" pair."""
    return {"workspace_id": s.W2.id, "purchase_order_id": s.O9.id}


# =========================================================================== #
# DAOPurchaseOrderReturn.generate_return_number
# =========================================================================== #


# [claude] PRT-GN-01
def test_prt_gn_01__first_number_whatever_others_hold(db, s):
    """PRT-GN-01 — no return yet gives PR-2026-001, whatever the other workspaces hold.
    Rules: generate_return_number R1, R3, Returns."""
    mk_return(db, s, "PR-2026-005", **_w0(s))
    mk_return(db, s, "PR-2026-006", **_w0(s))
    mk_return(db, s, "PR-2026-007", **_w2(s))
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-001"


# [claude] PRT-GN-02
def test_prt_gn_02__one_return_gives_002(db, s):
    """PRT-GN-02 — one return gives PR-2026-002.
    Rules: generate_return_number R1."""
    mk_return(db, s, "PR-2026-001")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-002"


# [claude] PRT-GN-03
def test_prt_gn_03__only_w1_counts(db, s):
    """PRT-GN-03 — only W1's returns count, with more returns in W0 and W2 than in W1.
    Rules: generate_return_number R3."""
    for number in ("PR-2026-011", "PR-2026-012", "PR-2026-013"):
        mk_return(db, s, number, **_w0(s))
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002")
    for number in ("PR-2026-021", "PR-2026-022", "PR-2026-023"):
        mk_return(db, s, number, **_w2(s))
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-003"


# [claude] PRT-GN-04
def test_prt_gn_04__w2_ignores_w0_and_w1(db, s):
    """PRT-GN-04 — asked for W2, the earlier W1 and W0 returns do not count.
    Rules: generate_return_number R3."""
    mk_return(db, s, "PR-2026-011", **_w0(s))
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002")
    mk_return(db, s, "PR-2026-021", **_w2(s))
    result = dao.generate_return_number(db, workspace_id=s.W2.id, year=2026)
    # Then 1
    assert result == "PR-2026-002"


# [claude] PRT-GN-05
def test_prt_gn_05__w0_ignores_w1_and_w2(db, s):
    """PRT-GN-05 — asked for W0, the later W1 and W2 returns do not count.
    Rules: generate_return_number R3."""
    mk_return(db, s, "PR-2026-011", **_w0(s))
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002")
    mk_return(db, s, "PR-2026-021", **_w2(s))
    mk_return(db, s, "PR-2026-022", **_w2(s))
    result = dao.generate_return_number(db, workspace_id=s.W0.id, year=2026)
    # Then 1
    assert result == "PR-2026-002"


# [claude] PRT-GN-06
def test_prt_gn_06__every_status_counts(db, s):
    """PRT-GN-06 — pending, completed and voided returns all count.
    Rules: generate_return_number R2."""
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002", **completed(s))
    mk_return(db, s, "PR-2026-003", **VOIDED)
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-004"


# [claude] PRT-GN-07
def test_prt_gn_07__hand_made_xyz_counts(db, s):
    """PRT-GN-07 — a hand-made PR-2026-XYZ counts as one.
    Rules: generate_return_number R2."""
    mk_return(db, s, "PR-2026-XYZ")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-002"


# [claude] PRT-GN-08
def test_prt_gn_08__other_years_do_not_count(db, s):
    """PRT-GN-08 — returns of the year before and after do not count.
    Rules: generate_return_number R3."""
    mk_return(db, s, "PR-2025-001")
    mk_return(db, s, "PR-2027-001")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-001"


# [claude] PRT-GN-09
def test_prt_gn_09__year_2099(db, s):
    """PRT-GN-09 — year 2099 starts at 001 while 2026 has returns.
    Rules: generate_return_number R3."""
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2099)
    # Then 1
    assert result == "PR-2099-001"


# [claude] PRT-GN-10
def test_prt_gn_10__year_1_as_given(db, s):
    """PRT-GN-10 — year 1 is used as given, and PR-10- does not count for it.
    Rules: generate_return_number Inputs (year), R1."""
    mk_return(db, s, "PR-1-005")
    mk_return(db, s, "PR-10-001")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=1)
    # Then 1
    assert result == "PR-1-002"


# [claude] PRT-GN-11
def test_prt_gn_11__only_prefix_counts(db, s):
    """PRT-GN-11 — only numbers that start with the prefix count.
    Rules: generate_return_number R1."""
    mk_return(db, s, "XPR-2026-001")
    mk_return(db, s, " PR-2026-002")
    mk_return(db, s, "PR-2026003")
    mk_return(db, s, "OLD-PR-2026-004")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-001"


# [claude] PRT-GN-12
def test_prt_gn_12__count_8_gives_009(db, s):
    """PRT-GN-12 — a count of 8 gives 009.
    Rules: generate_return_number R4."""
    for k in range(1, 9):
        db.add(
            PurchaseOrderReturn(
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                return_number=f"PR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
            )
        )
        db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-009"


# [claude] PRT-GN-13
def test_prt_gn_13__count_9_gives_010(db, s):
    """PRT-GN-13 — a count of 9 gives 010.
    Rules: generate_return_number R4."""
    for k in range(1, 10):
        db.add(
            PurchaseOrderReturn(
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                return_number=f"PR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
            )
        )
        db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-010"


# [claude] PRT-GN-14
def test_prt_gn_14__count_998_gives_999(db, s):
    """PRT-GN-14 — a count of 998 gives 999.
    Rules: generate_return_number R4."""
    for k in range(1, 999):
        db.add(
            PurchaseOrderReturn(
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                return_number=f"PR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
            )
        )
    db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-999"


# [claude] PRT-GN-15
def test_prt_gn_15__count_999_gives_1000(db, s):
    """PRT-GN-15 — a count of 999 gives 1000.
    Rules: generate_return_number R4."""
    for k in range(1, 1000):
        db.add(
            PurchaseOrderReturn(
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                return_number=f"PR-2026-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
            )
        )
    db.flush()
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-1000"


# [claude] PRT-GN-16
def test_prt_gn_16__writes_nothing(db, s):
    """PRT-GN-16 — writes nothing: a pending return stays pending and is not counted, an unflushed edit stays unflushed.
    Rules: generate_return_number R5."""
    b = mk_return(db, s, "PR-2025-001")
    b.reason = "Edited"
    p = PurchaseOrderReturn(
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        return_number="PR-2026-001",
        return_type="refund",
        created_by=s.U1.id,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-001"
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
    # Then 7
    assert totals(db) == before


# [claude] PRT-GN-17
def test_prt_gn_17__prefix_case_sensitive(db, s):
    """PRT-GN-17 — lower- and mixed-case pr-2026- numbers do not count (the prefix is case-sensitive).
    Rules: generate_return_number R1a."""
    mk_return(db, s, "pr-2026-001")
    mk_return(db, s, "Pr-2026-002")
    mk_return(db, s, "PR-2026-003")
    result = dao.generate_return_number(db, workspace_id=s.W1.id, year=2026)
    # Then 1
    assert result == "PR-2026-002"


# =========================================================================== #
# DAOPurchaseOrderReturn.create_with_user
# =========================================================================== #


# [claude] PRT-CW-01
def test_prt_cw_01__created_pending_with_fields(db, s):
    """PRT-CW-01 — a return is created pending with the given fields and the first number.
    Rules: create_with_user R1, R2a, Returns."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U2.id,
            return_type="replace",
            reason="Damaged",
            notes="Box crushed",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == s.W1.id
    assert row.purchase_order_id == s.O2.id
    assert row.return_type == "replace"
    assert row.reason == "Damaged"
    assert row.notes == "Box crushed"
    # Then 3
    row = reread(db, result)
    assert row.created_by == s.U2.id
    assert row.status == "pending"
    assert row.paid is False
    assert row.return_number == "PR-2026-001"
    # Then 4
    row = reread(db, result)
    assert row.invoice_id is None
    assert row.completed_at is None
    assert row.completed_by is None
    assert row.updated_by is None
    assert row.updated_at is None


# [claude] PRT-CW-02
def test_prt_cw_02__created_at_naive_utc_under_dhaka(db, s):
    """PRT-CW-02 — created_at is naive UTC at the flush, not the database's local clock.
    Rules: create_with_user R1."""
    dhaka(db)
    before = utcnow()
    result = dao.create_with_user(
        db,
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        user_id=s.U1.id,
        return_type="refund",
    )
    after = utcnow()
    # Then 1
    row = reread(db, result)
    assert row.created_at.tzinfo is None
    # Then 2
    assert before <= row.created_at <= after


# [claude] PRT-CW-03
def test_prt_cw_03__reason_and_notes_default_none(db, s):
    """PRT-CW-03 — reason and notes default to None.
    Rules: create_with_user Inputs (reason, notes), R1."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.reason is None
    assert row.notes is None
    assert row.return_type == "refund"


# [claude] PRT-CW-04
def test_prt_cw_04__empty_strings_kept(db, s):
    """PRT-CW-04 — empty reason and notes are stored as empty strings.
    Rules: create_with_user Inputs (reason, notes), R1."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
            reason="",
            notes="",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.reason == ""
    assert row.notes == ""


# [claude] PRT-CW-05
def test_prt_cw_05__unknown_return_type_stored(db, s):
    """PRT-CW-05 — an unknown return_type is stored as given.
    Rules: create_with_user Inputs (return_type)."""
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="banana",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_type == "banana"


# [claude] PRT-CW-06
def test_prt_cw_06__second_gets_next_number(db, s):
    """PRT-CW-06 — the second return gets the next number.
    Rules: create_with_user R2a."""
    a = mk_return(db, s, "PR-2026-001")
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id != a.id
    # Then 2
    assert reread(db, result).return_number == "PR-2026-002"
    # Then 3
    assert wcount(db, s.W1) == 2


# [claude] PRT-CW-07
def test_prt_cw_07__other_workspaces_do_not_count(db, s):
    """PRT-CW-07 — returns of W0 and W2 do not count toward W1's number.
    Rules: create_with_user R2a."""
    mk_return(db, s, "PR-2026-005", **_w0(s))
    mk_return(db, s, "PR-2026-006", **_w2(s))
    with clock(JUNE, JUNE):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "PR-2026-001"
    assert row.workspace_id == s.W1.id


# [claude] PRT-CW-08
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2428: a return number's year comes from the server's local clock",
)
def test_prt_cw_08__utc_year_local_already_next(db, s):
    """PRT-CW-08 — the year comes from UTC when the local clock is already in the next year.
    Rules: create_with_user R2 [BUG-2428]."""
    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "PR-2026-001"


# [claude] PRT-CW-09
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2428: a return number's year comes from the server's local clock",
)
def test_prt_cw_09__utc_year_local_still_before(db, s):
    """PRT-CW-09 — the year comes from UTC when the local clock is still in the year before.
    Rules: create_with_user R2 [BUG-2428]."""
    with clock(datetime(2026, 12, 31, 22, 0), datetime(2027, 1, 1, 3, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "PR-2027-001"


# [claude] PRT-CW-10
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2426: return numbers unique across all workspaces instead of per workspace",
)
def test_prt_cw_10__number_held_by_w2(db, s):
    """PRT-CW-10 — W1's first return succeeds while W2 already has PR-2026-001.
    Rules: create_with_user R4 [BUG-2426]."""
    mk_return(db, s, "PR-2026-001", **_w2(s))
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "PR-2026-001"
    assert row.workspace_id == s.W1.id
    # Then 3
    assert wcount(db, s.W2) == 1


# [claude] PRT-CW-11
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2426: return numbers unique across all workspaces instead of per workspace",
)
def test_prt_cw_11__number_held_by_w0(db, s):
    """PRT-CW-11 — W1's first return succeeds while W0 already has PR-2026-001.
    Rules: create_with_user R4 [BUG-2426]."""
    mk_return(db, s, "PR-2026-001", **_w0(s))
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number == "PR-2026-001"
    assert row.workspace_id == s.W1.id
    # Then 3
    assert wcount(db, s.W0) == 1


# [claude] PRT-CW-12
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2427: two returns started at once can get the same number "
    "(R3a: a taken next number fails the call)",
)
def test_prt_cw_12__taken_number_gets_free_one(db, s):
    """PRT-CW-12 — a taken next number never fails the call: the return gets a free number.
    Rules: create_with_user R3a [BUG-2427], R2a."""
    mk_return(db, s, "PR-2026-001")
    mk_return(db, s, "PR-2026-002")
    mk_return(db, s, "PR-2026-004")
    with clock(JUNE, JUNE):
        # Then 1 (the When raises today: IntegrityError 23505 on -004)
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.return_number.startswith("PR-2026-")
    # Then 3
    assert row.return_number not in {"PR-2026-001", "PR-2026-002", "PR-2026-004"}
    # Then 4
    assert wcount(db, s.W1) == 4
    # Then 5
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM purchase_order_returns WHERE workspace_id = :w AND return_number = :n"
            ),
            {"w": s.W1.id, "n": result.return_number},
        )
        == 1
    )


# [claude] PRT-CW-13
def test_prt_cw_13__user_none_fails_not_null(db, s):
    """PRT-CW-13 — user_id None fails NOT NULL at the flush and saves nothing.
    Rules: create_with_user Inputs (user_id), R5, Errors (user_id is None)."""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=s.W1.id,
                    purchase_order_id=s.O2.id,
                    user_id=None,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert wcount(db, s.W1) == 0


# [claude] PRT-CW-14
def test_prt_cw_14__unknown_order_fails_fk(db, s):
    """PRT-CW-14 — an unknown purchase order fails the foreign key at the flush and saves nothing.
    Rules: create_with_user Inputs (purchase_order_id), R5, Errors (unknown order)."""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=s.W1.id,
                    purchase_order_id=MISSING,
                    user_id=s.U1.id,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert wcount(db, s.W1) == 0


# [claude] PRT-CW-15
def test_prt_cw_15__unknown_workspace_fails_fk(db, s):
    """PRT-CW-15 — an unknown workspace fails the foreign key at the flush and saves nothing.
    Rules: create_with_user R5, Errors (unknown workspace)."""
    before = db.scalar(text("SELECT count(*) FROM purchase_order_returns"))
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with clock(JUNE, JUNE):
                dao.create_with_user(
                    db,
                    workspace_id=MISSING,
                    purchase_order_id=s.O2.id,
                    user_id=s.U1.id,
                    return_type="refund",
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert db.scalar(text("SELECT count(*) FROM purchase_order_returns")) == before


# [claude] PRT-CW-16
def test_prt_cw_16__flushed_not_committed(db, s):
    """PRT-CW-16 — flushed, not committed: a rollback removes the return.
    Rules: create_with_user R5, Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        with clock(JUNE, JUNE):
            result = dao.create_with_user(
                db,
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                user_id=s.U1.id,
                return_type="refund",
            )
    # Then 1
    assert result.id is not None
    # Then 2
    assert wcount(db, s.W1) == 1
    sp.rollback()
    # Then 3
    assert wcount(db, s.W1) == 0
    # Then 4
    assert cm.call_count == 0


# [claude] PRT-CW-17
def test_prt_cw_17__one_return_row_only(db, s):
    """PRT-CW-17 — writes one return row and nothing else.
    Rules: create_with_user Side effects."""
    a = mk_return(db, s, "PR-2026-001")
    before_a = snap(db, a)
    items_before = db.scalar(text("SELECT count(*) FROM purchase_order_return_items"))
    with clock(JUNE, JUNE), StatementRecorder(db) as rec:
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert len(rec.written) == 1
    # Then 3
    assert (
        rec.written[0].lstrip().upper().startswith("INSERT INTO PURCHASE_ORDER_RETURNS")
    )
    # Then 4
    assert wcount(db, s.W1) == 2
    # Then 5
    assert (
        db.scalar(text("SELECT count(*) FROM purchase_order_return_items"))
        == items_before
    )
    # Then 6
    assert snap(db, a) == before_a


# [claude] PRT-CW-18
def test_prt_cw_18__same_number_same_workspace_refused(db, s):
    """PRT-CW-18 — the database refuses a second row with the same number in one workspace (direct insert).
    Rules: create_with_user R4 (database fact kept under R3a), Errors (number already used)."""
    a = mk_return(db, s, "PR-2026-001")
    before_a = snap(db, a)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(
                PurchaseOrderReturn(
                    workspace_id=s.W1.id,
                    purchase_order_id=s.O2.id,
                    return_number="PR-2026-001",
                    return_type="refund",
                    created_by=s.U1.id,
                )
            )
            db.flush()
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert wcount(db, s.W1) == 1
    # Then 3
    assert snap(db, a) == before_a


# [claude] PRT-CW-19
def test_prt_cw_19__both_clocks_2031_give_2031(db, s):
    """PRT-CW-19 — the current year goes into the number: both clocks in 2031 give PR-2031-001.
    Rules: create_with_user R2, R2a."""
    mk_return(db, s, "PR-2026-001")
    with clock(datetime(2031, 1, 1, 5, 0), datetime(2031, 1, 1, 5, 0)):
        result = dao.create_with_user(
            db,
            workspace_id=s.W1.id,
            purchase_order_id=s.O2.id,
            user_id=s.U1.id,
            return_type="refund",
        )
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).return_number == "PR-2031-001"


# =========================================================================== #
# DAOPurchaseOrderReturn.get_by_purchase_order
# =========================================================================== #


# [claude] PRT-PO-01
def test_prt_po_01__every_status_newest_first(db, s):
    """PRT-PO-01 — every return of the order is returned, whatever its status, newest first.
    Rules: get_by_purchase_order R1, R3."""
    a = mk_return(db, s, "PR-T-01", created_at=T1)
    b = mk_return(db, s, "PR-T-02", created_at=T2, **completed(s))
    c = mk_return(db, s, "PR-T-03", created_at=T3, **VOIDED)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] PRT-PO-02
def test_prt_po_02__neighbour_orders_not_returned(db, s):
    """PRT-PO-02 — returns of the orders just below and above are not returned.
    Rules: get_by_purchase_order R1, R2."""
    mk_return(db, s, "PR-T-01", purchase_order_id=s.O1.id, created_at=T5)
    a = mk_return(db, s, "PR-T-02", created_at=T2)
    mk_return(db, s, "PR-T-03", purchase_order_id=s.O3.id, created_at=T4)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] PRT-PO-03
def test_prt_po_03__other_workspaces_same_order_id(db, s):
    """PRT-PO-03 — a return of the same order id under W0 or W2 is not returned.
    Rules: get_by_purchase_order R2."""
    mk_return(db, s, "PR-T-00", workspace_id=s.W0.id, created_at=T5)
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    mk_return(db, s, "PR-T-09", workspace_id=s.W2.id, created_at=T4)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] PRT-PO-04
def test_prt_po_04__w2_gets_only_its_own(db, s):
    """PRT-PO-04 — asked for W2, only the W2 return is returned, though the W1 and W0 returns are earlier.
    Rules: get_by_purchase_order R2."""
    mk_return(db, s, "PR-T-00", workspace_id=s.W0.id, created_at=T5)
    mk_return(db, s, "PR-T-01", created_at=T4)
    x9 = mk_return(db, s, "PR-T-09", workspace_id=s.W2.id, created_at=T2)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W2.id
    )
    # Then 1
    assert ids(result) == [x9.id]


# [claude] PRT-PO-05
def test_prt_po_05__wrong_workspace_empty(db, s):
    """PRT-PO-05 — the right order with another workspace's id returns an empty list.
    Rules: get_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01", created_at=T2)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W2.id
    )
    # Then 1
    assert result == []


# [claude] PRT-PO-06
def test_prt_po_06__unknown_order_empty(db, s):
    """PRT-PO-06 — an unknown order returns an empty list.
    Rules: get_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01", created_at=T2)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=MISSING, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PRT-PO-07
def test_prt_po_07__order_without_returns_empty(db, s):
    """PRT-PO-07 — an order without returns returns an empty list.
    Rules: get_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01", created_at=T2)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O3.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PRT-PO-08
def test_prt_po_08__newest_first_whatever_ids(db, s):
    """PRT-PO-08 — newest first, whatever the ids.
    Rules: get_by_purchase_order R3."""
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    b = mk_return(db, s, "PR-T-02", created_at=T4)
    c = mk_return(db, s, "PR-T-03", created_at=T1)
    d = mk_return(db, s, "PR-T-04", created_at=T3)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [b.id, d.id, a.id, c.id]


# [claude] PRT-PO-09
def test_prt_po_09__tie_sits_between(db, s):
    """PRT-PO-09 — on a tie both returns sit between the newer and the older one.
    Rules: get_by_purchase_order R3."""
    a = mk_return(db, s, "PR-T-01", created_at=T1)
    b = mk_return(db, s, "PR-T-02", created_at=T2)
    c = mk_return(db, s, "PR-T-03", created_at=T2)
    d = mk_return(db, s, "PR-T-04", created_at=T3)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == d.id
    # Then 3
    assert {result[1].id, result[2].id} == {b.id, c.id}
    # Then 4
    assert result[3].id == a.id


# [claude] PRT-PO-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2429: an order's returns of one creation time come back in no fixed order",
)
def test_prt_po_10__tie_highest_id_first(db, s):
    """PRT-PO-10 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: get_by_purchase_order R3 [BUG-2429]."""
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    b = mk_return(db, s, "PR-T-02", created_at=T2)
    c = mk_return(db, s, "PR-T-03", created_at=T2)
    d = mk_return(db, s, "PR-T-04", created_at=T2)
    seqscan(db)
    bump_r(db, a)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, c.id, b.id, a.id]


# [claude] PRT-PO-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2429: an order's returns of one creation time come back in no fixed order",
)
def test_prt_po_11__tie_id_decides(db, s):
    """PRT-PO-11 — on a tie the id decides, when number, type, status, creator and reason would sort otherwise.
    Rules: get_by_purchase_order R3 [BUG-2429]."""
    a = mk_return(
        db,
        s,
        "PR-T-09",
        created_at=T2,
        return_type="replace",
        created_by=s.U3.id,
        reason="Zinc",
    )
    b = mk_return(
        db,
        s,
        "PR-T-01",
        created_at=T2,
        **completed(s),
        created_by=s.U2.id,
        reason="Alpha",
    )
    c = mk_return(db, s, "PR-T-05", created_at=T2, **VOIDED, reason="Mid")
    seqscan(db)
    bump_r(db, a)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] PRT-PO-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2429: an order's returns of one creation time come back in no fixed order",
)
def test_prt_po_12__tie_high_explicit_id_first(db, s):
    """PRT-PO-12 — on a tie a row with a high explicit id comes first.
    Rules: get_by_purchase_order R3 [BUG-2429]."""
    eb = mk_return(db, s, "PR-T-01", created_at=T2)
    ec = mk_return(db, s, "PR-T-02", created_at=T2, id="HIGH")
    ea = mk_return(db, s, "PR-T-03", created_at=T2)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [ec.id, ea.id, eb.id]


# [claude] PRT-PO-13
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2429: an order's returns of one creation time come back in no fixed order",
)
def test_prt_po_13__orders_by_created_at_then_id_desc(db, s):
    """PRT-PO-13 — the query orders by created_at, then id, both descending.
    Rules: get_by_purchase_order R3 [BUG-2429]."""
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    with StatementRecorder(db) as rec:
        result = dao.get_by_purchase_order(
            db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "created_at" in rec.order_part
    # Then 3
    assert ".id" in rec.order_part
    # Then 4
    assert rec.order_part.index("created_at") < rec.order_part.index(".id")
    # Then 5
    assert rec.order_part.upper().count("DESC") == 2
    # Then 6
    assert rec.order_part.count(",") == 1


# [claude] PRT-PO-14
def test_prt_po_14__created_at_desc_first(db, s):
    """PRT-PO-14 — the query orders by created_at descending first.
    Rules: get_by_purchase_order R3."""
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    with StatementRecorder(db) as rec:
        result = dao.get_by_purchase_order(
            db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert rec.order_part.lstrip().split()[0].endswith("created_at")
    # Then 3
    assert rec.order_part.upper().split()[1].rstrip(",") == "DESC"


# [claude] PRT-PO-15
def test_prt_po_15__writes_nothing_no_order_read(db, s):
    """PRT-PO-15 — writes nothing and does not read the purchase order.
    Rules: get_by_purchase_order Side effects, R1."""
    a = mk_return(db, s, "PR-T-01", created_at=T2)
    a.reason = "Edited"
    p = PurchaseOrderReturn(
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        return_number="PR-T-02",
        return_type="refund",
        created_by=s.U1.id,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_purchase_order(
            db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
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
    assert "purchase_orders" not in rec.sql
    # Then 8
    assert totals(db) == before
    # Then 9
    assert "FOR UPDATE" not in rec.sql


# [claude] PRT-PO-16
def test_prt_po_16__no_paging(db, s):
    """PRT-PO-16 — no paging: 101 returns are all returned.
    Rules: get_by_purchase_order R1."""
    for k in range(101):
        db.add(
            PurchaseOrderReturn(
                workspace_id=s.W1.id,
                purchase_order_id=s.O2.id,
                return_number=f"PR-T-{k:03d}",
                return_type="refund",
                created_by=s.U1.id,
                created_at=T1 + timedelta(minutes=k),
            )
        )
    db.flush()
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 101
    # Then 2
    assert result[0].return_number == "PR-T-100"
    # Then 3
    assert result[100].return_number == "PR-T-000"


# [claude] PRT-PO-17
def test_prt_po_17__higher_order_not_mixed(db, s):
    """PRT-PO-17 — asked for the higher order O3, the returns of O2 below it are not mixed in.
    Rules: get_by_purchase_order R1, R2."""
    mk_return(db, s, "PR-T-01", created_at=T2)
    mk_return(db, s, "PR-T-02", created_at=T3)
    x3 = mk_return(db, s, "PR-T-03", purchase_order_id=s.O3.id, created_at=T1)
    result = dao.get_by_purchase_order(
        db, purchase_order_id=s.O3.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [x3.id]


# =========================================================================== #
# DAOPurchaseOrderReturn.get_open_by_purchase_order
# =========================================================================== #


# [claude] PRT-OP-01
def test_prt_op_01__only_pending(db, s):
    """PRT-OP-01 — only the pending return is returned, not the completed or voided one.
    Rules: get_open_by_purchase_order R1."""
    mk_return(db, s, "PR-T-01", **completed(s))
    a = mk_return(db, s, "PR-T-02")
    mk_return(db, s, "PR-T-03", **VOIDED)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] PRT-OP-02
def test_prt_op_02__two_pending(db, s):
    """PRT-OP-02 — two pending returns are both returned.
    Rules: get_open_by_purchase_order R1."""
    a = mk_return(db, s, "PR-T-01")
    mk_return(db, s, "PR-T-02", **completed(s))
    b = mk_return(db, s, "PR-T-03")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 2
    # Then 2
    assert idset(result) == {a.id, b.id}


# [claude] PRT-OP-03
def test_prt_op_03__capital_pending_not_open(db, s):
    """PRT-OP-03 — a hand-set "Pending" in capitals is not open.
    Rules: get_open_by_purchase_order R1."""
    mk_return(db, s, "PR-T-01", status="Pending")
    b = mk_return(db, s, "PR-T-02")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [b.id]


# [claude] PRT-OP-04
def test_prt_op_04__look_alikes_not_open(db, s):
    """PRT-OP-04 — a status with a leading space or a trailing letter is not open.
    Rules: get_open_by_purchase_order R1."""
    mk_return(db, s, "PR-T-01", status=" pending")
    mk_return(db, s, "PR-T-02", status="pendings")
    mk_return(db, s, "PR-T-03", status="pend")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PRT-OP-05
def test_prt_op_05__neighbour_orders_not_returned(db, s):
    """PRT-OP-05 — pending returns of the orders just below and above are not returned.
    Rules: get_open_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01", purchase_order_id=s.O1.id)
    a = mk_return(db, s, "PR-T-02")
    mk_return(db, s, "PR-T-03", purchase_order_id=s.O3.id)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] PRT-OP-06
def test_prt_op_06__other_workspaces_same_order_id(db, s):
    """PRT-OP-06 — a pending return of the same order id under W0 or W2 is not returned.
    Rules: get_open_by_purchase_order R2."""
    mk_return(db, s, "PR-T-00", workspace_id=s.W0.id)
    a = mk_return(db, s, "PR-T-01")
    mk_return(db, s, "PR-T-09", workspace_id=s.W2.id)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] PRT-OP-07
def test_prt_op_07__w2_gets_only_its_own(db, s):
    """PRT-OP-07 — asked for W2, only the W2 pending return is returned.
    Rules: get_open_by_purchase_order R2."""
    mk_return(db, s, "PR-T-00", workspace_id=s.W0.id)
    mk_return(db, s, "PR-T-01")
    x9 = mk_return(db, s, "PR-T-09", workspace_id=s.W2.id)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W2.id
    )
    # Then 1
    assert ids(result) == [x9.id]


# [claude] PRT-OP-08
def test_prt_op_08__unknown_order_empty(db, s):
    """PRT-OP-08 — an unknown order returns an empty list.
    Rules: get_open_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=MISSING, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PRT-OP-09
def test_prt_op_09__all_closed_empty(db, s):
    """PRT-OP-09 — an order whose returns are all completed or voided returns an empty list.
    Rules: get_open_by_purchase_order R1."""
    mk_return(db, s, "PR-T-01", **completed(s))
    mk_return(db, s, "PR-T-02", **VOIDED)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PRT-OP-10
@pytest.mark.xfail(
    strict=False, reason="BUG-2430: an order's open returns have no sort order"
)
def test_prt_op_10__id_ascending_after_update(db, s):
    """PRT-OP-10 — ids ascending, when the lowest id was updated.
    Rules: get_open_by_purchase_order R3 [BUG-2430]."""
    a = mk_return(db, s, "PR-T-01", created_at=T1)
    b = mk_return(db, s, "PR-T-02", created_at=T3)
    c = mk_return(db, s, "PR-T-03", created_at=T2)
    seqscan(db)
    bump_r(db, a)
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PRT-OP-11
@pytest.mark.xfail(
    strict=False, reason="BUG-2430: an order's open returns have no sort order"
)
def test_prt_op_11__high_explicit_id_last(db, s):
    """PRT-OP-11 — a row with a high explicit id comes last.
    Rules: get_open_by_purchase_order R3 [BUG-2430]."""
    eb = mk_return(db, s, "PR-T-01")
    ec = mk_return(db, s, "PR-T-02", id="HIGH")
    ea = mk_return(db, s, "PR-T-03")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [eb.id, ea.id, ec.id]


# [claude] PRT-OP-12
@pytest.mark.xfail(
    strict=True, reason="BUG-2430: an order's open returns have no sort order"
)
def test_prt_op_12__orders_by_id_ascending(db, s):
    """PRT-OP-12 — the query orders by id ascending.
    Rules: get_open_by_purchase_order R3 [BUG-2430]."""
    a = mk_return(db, s, "PR-T-01")
    with StatementRecorder(db) as rec:
        result = dao.get_open_by_purchase_order(
            db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
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
    assert rec.order_part.count(",") == 0


# [claude] PRT-OP-13
def test_prt_op_13__writes_nothing_no_order_read(db, s):
    """PRT-OP-13 — writes nothing and does not read the purchase order.
    Rules: get_open_by_purchase_order Side effects."""
    a = mk_return(db, s, "PR-T-01")
    a.notes = "Edited"
    p = PurchaseOrderReturn(
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        return_number="PR-T-02",
        return_type="refund",
        created_by=s.U1.id,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_open_by_purchase_order(
            db, purchase_order_id=s.O2.id, workspace_id=s.W1.id
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
    assert "purchase_orders" not in rec.sql
    # Then 8
    assert totals(db) == before
    # Then 9
    assert "FOR UPDATE" not in rec.sql


# [claude] PRT-OP-14
def test_prt_op_14__wrong_workspace_empty(db, s):
    """PRT-OP-14 — the right order with another workspace's id returns an empty list.
    Rules: get_open_by_purchase_order R2."""
    mk_return(db, s, "PR-T-01")
    result = dao.get_open_by_purchase_order(
        db, purchase_order_id=s.O2.id, workspace_id=s.W0.id
    )
    # Then 1
    assert result == []


# =========================================================================== #
# DAOPurchaseOrderReturn.get_by_invoice_id
# =========================================================================== #


# [claude] PRT-IN-01
def test_prt_in_01__found_between_neighbours(db, s):
    """PRT-IN-01 — the return whose credit note is the invoice is returned, between neighbours below and above.
    Rules: get_by_invoice_id R1."""
    mk_return(db, s, "PR-T-01", invoice_id=IVA)
    a = mk_return(db, s, "PR-T-02", invoice_id=IVB)
    mk_return(db, s, "PR-T-03", invoice_id=IVC)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id


# [claude] PRT-IN-02
def test_prt_in_02__completed_found(db, s):
    """PRT-IN-02 — a completed return is found by its credit note.
    Rules: get_by_invoice_id R1."""
    a = mk_return(db, s, "PR-T-01", invoice_id=IVB, **completed(s))
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "completed"


# [claude] PRT-IN-03
def test_prt_in_03__voided_found(db, s):
    """PRT-IN-03 — a voided return is found by its credit note.
    Rules: get_by_invoice_id R1."""
    a = mk_return(db, s, "PR-T-01", invoice_id=IVB, **VOIDED)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status == "voided"


# [claude] PRT-IN-04
def test_prt_in_04__unheld_invoice_none(db, s):
    """PRT-IN-04 — an invoice no return holds returns None, with returns on the invoices below and above.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "PR-T-01", invoice_id=IVA)
    mk_return(db, s, "PR-T-03", invoice_id=IVC)
    mk_return(db, s, "PR-T-02")
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PRT-IN-05
def test_prt_in_05__unknown_invoice_none(db, s):
    """PRT-IN-05 — an unknown invoice id returns None.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "PR-T-01", invoice_id=IVB)
    result = dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PRT-IN-06
def test_prt_in_06__w2_note_not_found_from_w1(db, s):
    """PRT-IN-06 — the credit note of a W2 return is not found from W1.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "PR-T-09", **_w2(s), invoice_id=IVB)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PRT-IN-07
def test_prt_in_07__w0_note_not_found_from_w1(db, s):
    """PRT-IN-07 — the credit note of a W0 return is not found from W1.
    Rules: get_by_invoice_id R2."""
    mk_return(db, s, "PR-T-00", **_w0(s), invoice_id=IVB)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] PRT-IN-08
def test_prt_in_08__w2_finds_its_own(db, s):
    """PRT-IN-08 — asked for W2, the W2 return is found, though W0 and W1 hold the same invoice id earlier.
    Rules: get_by_invoice_id R1, R2."""
    mk_return(db, s, "PR-T-00", **_w0(s), invoice_id=IVB)
    mk_return(db, s, "PR-T-01", invoice_id=IVB)
    x9 = mk_return(db, s, "PR-T-09", **_w2(s), invoice_id=IVB)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W2.id)
    # Then 1
    assert result.id == x9.id


# [claude] PRT-IN-09
def test_prt_in_09__two_on_one_invoice(db, s):
    """PRT-IN-09 — two returns on one invoice: one of them is returned.
    Rules: get_by_invoice_id R3."""
    a = mk_return(db, s, "PR-T-01", invoice_id=IVB)
    b = mk_return(db, s, "PR-T-02", invoice_id=IVB)
    result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result.id in {a.id, b.id}


# [claude] PRT-IN-10
def test_prt_in_10__writes_nothing(db, s):
    """PRT-IN-10 — writes nothing: a pending return stays pending, an unflushed edit stays unflushed.
    Rules: get_by_invoice_id Side effects."""
    a = mk_return(db, s, "PR-T-01", invoice_id=IVB)
    a.reason = "Edited"
    p = PurchaseOrderReturn(
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        return_number="PR-T-02",
        return_type="refund",
        created_by=s.U1.id,
    )
    db.add(p)
    before = totals(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
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
    # Then 8
    assert "FOR UPDATE" not in rec.sql


# [claude] PRT-IN-11
def test_prt_in_11__none_finds_w1_return_without_note(db, s):
    """PRT-IN-11 — invoice_id None returns W1's return without a credit note, not those of W0 or W2.
    Rules: get_by_invoice_id R4."""
    mk_return(db, s, "PR-T-90", **_w0(s))
    mk_return(db, s, "PR-T-01", invoice_id=IVB)
    a = mk_return(db, s, "PR-T-02")
    mk_return(db, s, "PR-T-99", **_w2(s))
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.invoice_id is None


# [claude] PRT-IN-12
def test_prt_in_12__none_when_every_w1_return_has_note(db, s):
    """PRT-IN-12 — invoice_id None returns None when every W1 return has a credit note.
    Rules: get_by_invoice_id R4."""
    mk_return(db, s, "PR-T-90", **_w0(s))
    mk_return(db, s, "PR-T-01", invoice_id=IVA)
    mk_return(db, s, "PR-T-02", invoice_id=IVB)
    mk_return(db, s, "PR-T-99", **_w2(s))
    result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# DAOPurchaseOrderReturnItem.get_by_return
# =========================================================================== #


# [claude] PRT-RI-01
def test_prt_ri_01__every_line_of_the_return(db, s):
    """PRT-RI-01 — every line of the return is returned, not the lines of the returns just below and above.
    Rules: get_by_return R1, R2."""
    ra = mk_return(db, s, "PR-T-01")
    r = mk_return(db, s, "PR-T-02")
    rc = mk_return(db, s, "PR-T-03")
    mk_line(db, s, ra)
    l1 = mk_line(db, s, r)
    l2 = mk_line(db, s, r, quantity_returned=Decimal("3.00"))
    l3 = mk_line(db, s, r, unit_price=Decimal("4.50"), notes="Cracked")
    mk_line(db, s, rc)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert idset(result) == {l1.id, l2.id, l3.id}


# [claude] PRT-RI-02
def test_prt_ri_02__other_workspace_lines_not_returned(db, s):
    """PRT-RI-02 — a line of W0 or W2 on the same return is not returned.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "PR-T-01")
    mk_line(db, s, r, workspace_id=s.W0.id)
    l1 = mk_line(db, s, r)
    mk_line(db, s, r, workspace_id=s.W2.id)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [l1.id]


# [claude] PRT-RI-03
def test_prt_ri_03__w2_gets_only_its_line(db, s):
    """PRT-RI-03 — asked for W2, only the W2 line is returned.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "PR-T-01")
    mk_line(db, s, r, workspace_id=s.W0.id)
    mk_line(db, s, r)
    x9 = mk_line(db, s, r, workspace_id=s.W2.id)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [x9.id]


# [claude] PRT-RI-04
def test_prt_ri_04__unknown_return_empty(db, s):
    """PRT-RI-04 — an unknown return returns an empty list.
    Rules: get_by_return R2."""
    r = mk_return(db, s, "PR-T-01")
    mk_line(db, s, r)
    result = idao.get_by_return(db, return_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PRT-RI-05
def test_prt_ri_05__return_without_lines_empty(db, s):
    """PRT-RI-05 — a return without lines returns an empty list.
    Rules: get_by_return R1."""
    r = mk_return(db, s, "PR-T-01")
    rb = mk_return(db, s, "PR-T-02")
    mk_line(db, s, r)
    result = idao.get_by_return(db, return_id=rb.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PRT-RI-06
def test_prt_ri_06__no_paging(db, s):
    """PRT-RI-06 — no paging: 101 lines are all returned.
    Rules: get_by_return R1."""
    r = mk_return(db, s, "PR-T-01")
    with unchecked(db):
        for _ in range(101):
            db.add(
                PurchaseOrderReturnItem(
                    workspace_id=s.W1.id,
                    return_id=r.id,
                    po_item_id=MISSING,
                    item_id=s.I1.id,
                    quantity_returned=Decimal("2.00"),
                )
            )
        db.flush()
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 101


# [claude] PRT-RI-07
def test_prt_ri_07__half_up_storage(db, s):
    """PRT-RI-07 — stored quantities and prices come back rounded half up, as exact Decimals.
    Rules: get_by_return R1; Model facts (quantity_returned, unit_price Numeric(15,2)); HR-15."""
    r = mk_return(db, s, "PR-T-01")
    la = mk_line(
        db, s, r, quantity_returned=Decimal("2.125"), unit_price=Decimal("0.005")
    )
    lb = mk_line(
        db, s, r, quantity_returned=Decimal("1.00"), unit_price=Decimal("-1.005")
    )
    db.expire_all()
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {la.id, lb.id}
    # Then 2
    assert {x.id: x.quantity_returned for x in result}[la.id] == Decimal("2.13")
    # Then 3
    assert {x.id: x.unit_price for x in result}[la.id] == Decimal("0.01")
    # Then 4
    assert {x.id: x.unit_price for x in result}[lb.id] == Decimal("-1.01")
    # Then 5
    assert isinstance({x.id: x.quantity_returned for x in result}[la.id], Decimal)


# [claude] PRT-RI-08
@pytest.mark.xfail(strict=False, reason="BUG-2431: a return's lines have no sort order")
def test_prt_ri_08__id_ascending_after_update(db, s):
    """PRT-RI-08 — ids ascending, when the lowest id was updated.
    Rules: get_by_return R3 [BUG-2431]."""
    r = mk_return(db, s, "PR-T-01")
    a = mk_line(db, s, r, quantity_returned=Decimal("9.00"))
    b = mk_line(db, s, r, quantity_returned=Decimal("1.00"))
    c = mk_line(db, s, r, quantity_returned=Decimal("5.00"))
    seqscan(db)
    bump_l(db, a)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] PRT-RI-09
@pytest.mark.xfail(strict=False, reason="BUG-2431: a return's lines have no sort order")
def test_prt_ri_09__high_explicit_id_last(db, s):
    """PRT-RI-09 — a line with a high explicit id comes last.
    Rules: get_by_return R3 [BUG-2431]."""
    r = mk_return(db, s, "PR-T-01")
    eb = mk_line(db, s, r)
    ec = mk_line(db, s, r, id="HIGH")
    ea = mk_line(db, s, r)
    result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [eb.id, ea.id, ec.id]


# [claude] PRT-RI-10
@pytest.mark.xfail(strict=True, reason="BUG-2431: a return's lines have no sort order")
def test_prt_ri_10__orders_by_id_ascending(db, s):
    """PRT-RI-10 — the query orders by id ascending.
    Rules: get_by_return R3 [BUG-2431]."""
    r = mk_return(db, s, "PR-T-01")
    l1 = mk_line(db, s, r)
    with StatementRecorder(db) as rec:
        result = idao.get_by_return(db, return_id=r.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [l1.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert ".id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0


# [claude] PRT-RI-11
def test_prt_ri_11__writes_nothing_and_rounds_down(db, s):
    """PRT-RI-11 — writes nothing, does not read the return, and a 2.124 quantity comes back as 2.12.
    Rules: get_by_return Side effects, R1; HR-15 (control)."""
    r = mk_return(db, s, "PR-T-01")
    l1 = mk_line(db, s, r, quantity_returned=Decimal("2.124"))
    db.expire_all()
    r.notes = "Edited"
    p = PurchaseOrderReturn(
        workspace_id=s.W1.id,
        purchase_order_id=s.O2.id,
        return_number="PR-T-02",
        return_type="refund",
        created_by=s.U1.id,
    )
    db.add(p)
    before = totals(db)
    # R and W1 were expired above: read their ids now, so the recorder sees only the When's SQL
    r_id, w1_id = r.id, s.W1.id
    with StatementRecorder(db) as rec:
        result = idao.get_by_return(db, return_id=r_id, workspace_id=w1_id)
    # Then 1
    assert ids(result) == [l1.id]
    # Then 2
    assert result[0].quantity_returned == Decimal("2.12")
    # Then 3
    assert p in db.new
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert r in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert rec.written == []
    # Then 8
    assert "purchase_order_returns" not in rec.sql
    # Then 9
    assert totals(db) == before
    # Then 10
    assert "FOR UPDATE" not in rec.sql
