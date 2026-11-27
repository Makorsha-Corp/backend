"""Unit tests for app/dao/work_order.py.

Implements tests/unit/dao/work_order.cases.md (revision 2), one test per case,
in card order. Real Postgres session (`db` fixture).

Patched: only the clocks of the Conventions' Externals. clockN(L, U) (`NN`
cards) patches `datetime.datetime` (a subclass whose `now()` returns L),
`app.utils.time.utcnow` and `app.dao.work_order.utcnow` (`create=True`).
clockD(L, U) (every `status_scope="planned"` card) patches
`app.dao.work_order.date` (a subclass whose `today()` returns L),
`app.dao.work_order.utcnow` (`create=True`) and `app.utils.time.utcnow`.
SD-08 patches the two `utcnow`s. No race simulations.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe nested clock patches and `with pytest.raises(...)`
# around `with db.begin_nested()`, and naive datetimes for the stored timestamps and clock values)
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from app.dao.work_order import work_order_dao
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.work_order import WorkOrder
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_type import WorkOrderType
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = work_order_dao"; "ST", "PR"
dao = work_order_dao
ST = WorkOrderStatusEnum
PR = WorkOrderPriorityEnum

# Convention "MISSING"
MISSING = 999999999


# Convention "XID(k)": an id above any sequence id, per process
def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


# Convention "Dn" = date(2026, 3, n)
def D(n):
    return date(2026, 3, n)


D4, D5, D9, D10, D11, D12, D13, D20 = (D(n) for n in (4, 5, 9, 10, 11, 12, 13, 20))


# Convention "Cn" = datetime(2026, 3, 4, n, 0)
def C(n):
    return datetime(2026, 3, 4, n, 0)


C9, C10, C11, C12, C13, C14 = (C(n) for n in (9, 10, 11, 12, 13, 14))


# Convention "KD(n)" = a creation stamp on day Dn
def KD(n):
    return datetime(2026, 3, n, 9, 0)


# Convention "DT0", "SDT"
DT0 = datetime(2026, 3, 5, 9, 0)
SDT = datetime(2031, 1, 2, 3, 4, 5)


# Convention "Yn" = date(2031, 3, n)
def Y(n):
    return date(2031, 3, n)


Y9, Y10, Y11, Y12 = (Y(n) for n in (9, 10, 11, 12))

# Convention "An NN card without a clock line runs under clockN(2031-06-01 12:00, 2031-06-01 12:00)"
JUNE = datetime(2031, 6, 1, 12, 0)
# The clockD value of most "planned" cards
MAR10 = datetime(2031, 3, 10, 12, 0)


# Convention "utc_now()"
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Conventions -> Externals (clocks), Dhaka, seqscan
# --------------------------------------------------------------------------- #


@contextmanager
def clockN(local, utc):
    """Convention "clockN(L, U)"."""

    class _LocalClock(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return local

    with patch("datetime.datetime", _LocalClock):
        with patch("app.utils.time.utcnow", return_value=utc):
            with patch("app.dao.work_order.utcnow", create=True, return_value=utc):
                yield


@contextmanager
def clockD(local, utc):
    """Convention "clockD(L, U)"."""

    class _LocalDate(date):
        @classmethod
        def today(cls):
            return local

    with patch("app.dao.work_order.date", _LocalDate):
        with patch("app.dao.work_order.utcnow", create=True, return_value=utc):
            with patch("app.utils.time.utcnow", return_value=utc):
                yield


def dhaka(db):
    """Convention "Dhaka"."""
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order, each flushed)
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def g(db):
    """The standing rows by their Conventions names (g.W0 ... g.P2), plus the
    "completed" / "voided" / "started" / "deleted" column sets."""
    n = SimpleNamespace()
    n.W0, n.W1, n.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    n.U1, n.U2, n.U3 = make_profile(db), make_profile(db), make_profile(db)

    def _ws_rows(k, ws):
        f = _add(
            db, Factory(workspace_id=ws.id, name="Main Plant", abbreviation=f"MP{k}")
        )
        t = _add(db, WorkOrderType(workspace_id=ws.id, name="Repair"))
        m = _add(db, Machine(workspace_id=ws.id, name=f"Press {k}", factory_id=f.id))
        p = _add(
            db,
            WorkOrderTemplate(
                workspace_id=ws.id, template_name="Oil change", work_order_type_id=t.id
            ),
        )
        return f, t, m, p

    n.F0, n.T0, n.M0, n.P0 = _ws_rows(0, n.W0)
    w1 = n.W1.id
    n.FA = _add(db, Factory(workspace_id=w1, name="East Yard", abbreviation="EY"))
    n.F1 = _add(db, Factory(workspace_id=w1, name="Main Plant", abbreviation="MP1"))
    n.FB = _add(db, Factory(workspace_id=w1, name="North Yard", abbreviation="NY"))
    n.TA = _add(db, WorkOrderType(workspace_id=w1, name="Calibration"))
    n.T1 = _add(db, WorkOrderType(workspace_id=w1, name="Repair"))
    n.TB = _add(db, WorkOrderType(workspace_id=w1, name="Inspection"))
    n.MA = _add(db, Machine(workspace_id=w1, name="Press A", factory_id=n.F1.id))
    n.M1 = _add(db, Machine(workspace_id=w1, name="Press 1", factory_id=n.F1.id))
    n.MB = _add(db, Machine(workspace_id=w1, name="Press B", factory_id=n.F1.id))
    n.MX = _add(db, Machine(workspace_id=w1, name="Press X", factory_id=n.FA.id))
    n.MY = _add(db, Machine(workspace_id=w1, name="Press Y", factory_id=n.FB.id))
    for attr, name in (
        ("PA", "Belt check"),
        ("P1", "Oil change"),
        ("PB", "Filter swap"),
    ):
        setattr(
            n,
            attr,
            _add(
                db,
                WorkOrderTemplate(
                    workspace_id=w1, template_name=name, work_order_type_id=n.T1.id
                ),
            ),
        )
    n.F2, n.T2, n.M2, n.P2 = _ws_rows(2, n.W2)

    # Conventions "completed", "voided", "started", "deleted"
    n.completed = {
        "status": "COMPLETED",
        "completed_by": n.U1.id,
        "completed_by_names": "Karim",
        "completed_at": DT0,
    }
    n.voided = {
        "status": "VOIDED",
        "void_note": "cancelled",
        "voided_at": DT0,
        "voided_by": n.U1.id,
    }
    n.started = {"status": "IN_PROGRESS", "started_at": DT0, "started_by": n.U1.id}
    n.deleted = {
        "is_deleted": True,
        "is_active": False,
        "deleted_at": DT0,
        "deleted_by": n.U1.id,
    }
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given-row builders
# --------------------------------------------------------------------------- #


def _row(g, number, k=1, **columns):
    """Convention "order N" (k=1), "order of W0" (k=0), "order of W2" (k=2); `columns` are the "but" columns."""
    fields = {
        "workspace_id": getattr(g, f"W{k}").id,
        "work_order_number": number,
        "work_order_type_id": getattr(g, f"T{k}").id,
        "title": "Oil change",
        "factory_id": getattr(g, f"F{k}").id,
        "machine_id": getattr(g, f"M{k}").id,
        "created_by": g.U1.id,
    }
    fields.update(columns)
    return WorkOrder(**fields)


@pytest.fixture
def mk(db, g):
    """mk(number, k=1, **but) -> WorkOrder, flushed."""

    def _mk(number, k=1, **columns):
        return _add(db, _row(g, number, k, **columns))

    return _mk


@pytest.fixture
def draft(db, g):
    """Convention "draft of P1 on d, number N": draft(d, N, **but) -> WorkOrder, flushed."""

    def _mk(d, number, **columns):
        fields = {"work_order_template_id": g.P1.id, "planned_date": d}
        fields.update(columns)
        return _add(db, _row(g, number, 1, **fields))

    return _mk


@pytest.fixture
def mk_orders(db, g):
    """Convention "orders(W, prefix, n)": n orders numbered f"{prefix}{i:03d}", one flush after the loop."""

    def _mk(k, prefix, n):
        for i in range(1, n + 1):
            db.add(_row(g, f"{prefix}{i:03d}", k))
        db.flush()

    return _mk


def dirty_pending(db, g, o1):
    """Convention "dirty+pending": O1.title edited, P added with no flush. Returns P."""
    o1.title = "Edited"
    p = _row(g, "WO-T-900")
    db.add(p)
    return p


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


def reread(db, row_id):
    """Convention "re-read X"."""
    db.expire_all()
    return db.execute(select(WorkOrder).where(WorkOrder.id == row_id)).scalar_one()


class StatementRecorder:
    """Convention "Statement recorder"."""

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
        """The one SELECT that reads work_orders; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects if "work_orders" in s]
        return statement

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        part = sql.split("ORDER BY", 1)[1]
        for stop in ("LIMIT", "OFFSET"):
            part = part.split(stop, 1)[0]
        return part.strip()


# --------------------------------------------------------------------------- #
# _work_order_calendar_date_expr
# --------------------------------------------------------------------------- #


# [claude] WKO-CE-01
def test_wko_ce_01__dated_on_planned_day_undated_on_creation_day(db, g, mk):
    """WKO-CE-01 — a dated order counts on its planned day, an undated one on its creation day.
    Rules: `_work_order_calendar_date_expr` R1, R2; `count_by_calendar_date_for_sheet` R1"""
    mk("WO-T-001", planned_date=D12, created_at=KD(4))
    mk("WO-T-002", created_at=KD(4))

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {D12: 1, D4: 1}


# [claude] WKO-CE-02
def test_wko_ce_02__creation_day_as_stored_under_dhaka(db, g, mk):
    """WKO-CE-02 — the creation day is the date of created_at as stored, also late in the evening under Dhaka.
    Rules: `_work_order_calendar_date_expr` R2"""
    dhaka(db)
    mk("WO-T-001", created_at=datetime(2026, 3, 4, 23, 30))
    mk("WO-T-002", created_at=datetime(2026, 3, 5, 0, 30))

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {D4: 1, D5: 1}


# [claude] WKO-CE-03
def test_wko_ce_03__sheet_uses_planned_day_not_creation_day(db, g, mk):
    """WKO-CE-03 — on the sheet a dated order sits on its planned day, not its creation day.
    Rules: `_work_order_calendar_date_expr` R1; `_apply_sheet_list_filters` R3, R4"""
    mk("WO-T-001", planned_date=D12, created_at=KD(4))
    b = mk("WO-T-002", created_at=KD(4))

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        planned_date_from=D4,
        planned_date_to=D4,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert ids(result) == [b.id]


# --------------------------------------------------------------------------- #
# _sheet_base_query
# --------------------------------------------------------------------------- #


# [claude] WKO-SB-01
def test_wko_sb_01__only_w1_rows(db, g, mk):
    """WKO-SB-01 — only W1's rows, with rows of W0 built before and W2 after.
    Rules: `_sheet_base_query` R1; `list_for_sheet` R1"""
    mk("WO-T-001", k=0)
    a = mk("WO-T-001")
    b = mk("WO-T-002")
    mk("WO-T-001", k=2)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SB-02
def test_wko_sb_02__asked_for_w2_only_w2_row(db, g, mk):
    """WKO-SB-02 — asked for W2, only W2's row, though W0 and W1 rows come earlier.
    Rules: `_sheet_base_query` R1"""
    mk("WO-T-001", k=0)
    mk("WO-T-001")
    x2 = mk("WO-T-001", k=2)

    result = dao.list_for_sheet(
        db, workspace_id=g.W2.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [x2.id]


# [claude] WKO-SB-03
def test_wko_sb_03__asked_for_w0_only_w0_row(db, g, mk):
    """WKO-SB-03 — asked for W0, only W0's row, though W1 and W2 rows come later.
    Rules: `_sheet_base_query` R1"""
    x0 = mk("WO-T-001", k=0)
    mk("WO-T-001")
    mk("WO-T-001", k=2)

    result = dao.list_for_sheet(
        db, workspace_id=g.W0.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [x0.id]


# [claude] WKO-SB-04
def test_wko_sb_04__soft_deleted_not_on_sheet(db, g, mk):
    """WKO-SB-04 — a soft-deleted order is not on the sheet.
    Rules: `_sheet_base_query` R2"""
    a = mk("WO-T-001")
    mk("WO-T-002", **g.deleted)
    c = mk("WO-T-003")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert idset(result) == {a.id, c.id}


# [claude] WKO-SB-05
def test_wko_sb_05__machine_less_not_on_sheet(db, g, mk):
    """WKO-SB-05 — an order with no machine is not on the sheet.
    Rules: `_sheet_base_query` R3"""
    a = mk("WO-T-001")
    mk("WO-T-002", machine_id=None)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SB-06
def test_wko_sb_06__count_leaves_out_other_ws_deleted_machine_less(db, g, mk):
    """WKO-SB-06 — the count leaves out other workspaces, deleted and machine-less orders.
    Rules: `_sheet_base_query` R1, R2, R3; `count_for_sheet` R1"""
    mk("WO-T-001", k=0)
    mk("WO-T-001")
    mk("WO-T-002", **g.deleted)
    mk("WO-T-003", machine_id=None)
    mk("WO-T-004")
    mk("WO-T-001", k=2)

    result = dao.count_for_sheet(db, workspace_id=g.W1.id, exclude_completed=False)

    # Then 1
    assert result == 2


# --------------------------------------------------------------------------- #
# _apply_sheet_list_filters
# --------------------------------------------------------------------------- #


# [claude] WKO-SF-01
def test_wko_sf_01__factory_filter(db, g, mk):
    """WKO-SF-01 — factory_id keeps that factory only, between a lower and a higher factory.
    Rules: `_apply_sheet_list_filters` R1"""
    mk("WO-T-001", factory_id=g.FA.id, machine_id=g.MX.id)
    b = mk("WO-T-002")
    mk("WO-T-003", factory_id=g.FB.id, machine_id=g.MY.id)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, factory_id=g.F1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-SF-02
def test_wko_sf_02__machine_filter(db, g, mk):
    """WKO-SF-02 — machine_id keeps that machine only, between a lower and a higher machine.
    Rules: `_apply_sheet_list_filters` R1"""
    mk("WO-T-001", machine_id=g.MA.id)
    b = mk("WO-T-002")
    mk("WO-T-003", machine_id=g.MB.id)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, machine_id=g.M1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-SF-03
def test_wko_sf_03__type_filter(db, g, mk):
    """WKO-SF-03 — work_order_type_id keeps that type only, between a lower and a higher type.
    Rules: `_apply_sheet_list_filters` R2"""
    mk("WO-T-001", work_order_type_id=g.TA.id)
    b = mk("WO-T-002")
    mk("WO-T-003", work_order_type_id=g.TB.id)

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        work_order_type_id=g.T1.id,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-SF-04
def test_wko_sf_04__priority_filter(db, g, mk):
    """WKO-SF-04 — priority keeps that priority only.
    Rules: `_apply_sheet_list_filters` R2"""
    mk("WO-T-001", priority=PR.LOW)
    mk("WO-T-002", priority=PR.MEDIUM)
    c = mk("WO-T-003", priority=PR.HIGH)
    mk("WO-T-004", priority=PR.URGENT)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, priority=PR.HIGH, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [c.id]


# [claude] WKO-SF-05
def test_wko_sf_05__falsy_filters_filter_nothing(db, g, mk):
    """WKO-SF-05 — falsy filters (0 and "") filter nothing.
    Rules: `_apply_sheet_list_filters` Purpose (a falsy argument is skipped)"""
    a = mk(
        "WO-T-001", factory_id=g.FA.id, machine_id=g.MX.id, work_order_type_id=g.TA.id
    )
    b = mk("WO-T-002")

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        factory_id=0,
        machine_id=0,
        work_order_type_id=0,
        search="",
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SF-06
def test_wko_sf_06__date_from_inclusive_on_calendar_day(db, g, mk):
    """WKO-SF-06 — planned_date_from is inclusive on the calendar day and keeps an undated order created that day.
    Rules: `_apply_sheet_list_filters` R3"""
    mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    c = mk("WO-T-003", planned_date=D11)
    e = mk("WO-T-004", created_at=KD(10))
    mk("WO-T-005", created_at=KD(9))

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        planned_date_from=D10,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert idset(result) == {b.id, c.id, e.id}


# [claude] WKO-SF-07
def test_wko_sf_07__date_to_inclusive_on_calendar_day(db, g, mk):
    """WKO-SF-07 — planned_date_to is inclusive on the calendar day.
    Rules: `_apply_sheet_list_filters` R4"""
    a = mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", planned_date=D11)
    e = mk("WO-T-004", created_at=KD(10))
    mk("WO-T-005", created_at=KD(11))

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        planned_date_to=D10,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert idset(result) == {a.id, b.id, e.id}


# [claude] WKO-SF-08
def test_wko_sf_08__from_after_to_gives_nothing(db, g, mk):
    """WKO-SF-08 — from after to gives nothing.
    Rules: `_apply_sheet_list_filters` R4"""
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-002", planned_date=D11)

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        planned_date_from=D11,
        planned_date_to=D10,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert result == []


# [claude] WKO-SF-09
def test_wko_sf_09__status_filter(db, g, mk):
    """WKO-SF-09 — status keeps exactly that status.
    Rules: `_apply_sheet_list_filters` R5"""
    mk("WO-T-001")
    b = mk("WO-T-002", **g.started)
    mk("WO-T-003", **g.completed)
    mk("WO-T-004", **g.voided)

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        status=ST.IN_PROGRESS,
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-SF-10
def test_wko_sf_10__planned_keeps_future_drafts_only(db, g, mk):
    """WKO-SF-10 — "planned" keeps drafts planned strictly after today only.
    Rules: `_apply_sheet_list_filters` R6"""
    mk("WO-T-001", planned_date=Y9)
    mk("WO-T-002", planned_date=Y10)
    c = mk("WO-T-003", planned_date=Y11)
    mk("WO-T-004")
    mk("WO-T-005", planned_date=Y11, **g.started)

    with clockD(Y10, MAR10):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status_scope="planned",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert ids(result) == [c.id]


# [claude] WKO-SF-11
def test_wko_sf_11__planned_replaces_status(db, g, mk):
    """WKO-SF-11 — "planned" replaces a status sent with it.
    Rules: `_apply_sheet_list_filters` R6"""
    a = mk("WO-T-001", planned_date=Y11)
    mk("WO-T-002", planned_date=Y11, **g.completed)

    with clockD(Y10, MAR10):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status=ST.COMPLETED,
            status_scope="planned",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-12
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2673: "Planned" work orders are counted from the server\'s local date',
)
def test_wko_sf_12__planned_uses_utc_date_local_behind(db, g, mk):
    """WKO-SF-12 — "planned" uses the UTC date: local 10 Nov, UTC 11 Nov, a draft for 11 Nov is not planned.
    Rules: `_apply_sheet_list_filters` R6 [BUG-2673]"""
    mk("WO-T-001", planned_date=date(2031, 11, 11))
    b = mk("WO-T-002", planned_date=date(2031, 11, 12))

    with clockD(date(2031, 11, 10), datetime(2031, 11, 11, 3, 0)):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status_scope="planned",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert b.id in idset(result)
    # Then 2
    assert idset(result) == {b.id}


# [claude] WKO-SF-13
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2673: "Planned" work orders are counted from the server\'s local date',
)
def test_wko_sf_13__planned_uses_utc_date_local_ahead(db, g, mk):
    """WKO-SF-13 — "planned" uses the UTC date: local 11 Nov, UTC 10 Nov, a draft for 11 Nov is planned.
    Rules: `_apply_sheet_list_filters` R6 [BUG-2673]"""
    a = mk("WO-T-001", planned_date=date(2031, 11, 11))
    b = mk("WO-T-002", planned_date=date(2031, 11, 12))

    with clockD(date(2031, 11, 11), datetime(2031, 11, 10, 22, 0)):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status_scope="planned",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert b.id in idset(result)
    # Then 2
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SF-14
def test_wko_sf_14__unknown_scope_ignored_status_applies(db, g, mk):
    """WKO-SF-14 — an unknown status_scope is ignored and the status filter applies.
    Rules: `_apply_sheet_list_filters` R7 (the DAO half)"""
    a = mk("WO-T-001", planned_date=Y9)
    b = mk("WO-T-002")
    mk("WO-T-003", planned_date=Y11, **g.started)

    with clockD(Y10, MAR10):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status=ST.DRAFT,
            status_scope="bogus",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SF-15
def test_wko_sf_15__capital_planned_filters_nothing(db, g, mk):
    """WKO-SF-15 — status_scope "Planned" (capital P) is not "planned" and filters nothing.
    Rules: `_apply_sheet_list_filters` R7"""
    a = mk("WO-T-001", planned_date=Y9)
    b = mk("WO-T-002", planned_date=Y11, **g.completed)

    with clockD(Y10, MAR10):
        result = dao.list_for_sheet(
            db,
            workspace_id=g.W1.id,
            status_scope="Planned",
            exclude_completed=False,
            limit=100,
        )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SF-16
def test_wko_sf_16__exclude_completed_drops_completed_only(db, g, mk):
    """WKO-SF-16 — exclude_completed drops COMPLETED only.
    Rules: `_apply_sheet_list_filters` R8"""
    a = mk("WO-T-001")
    b = mk("WO-T-002", **g.started)
    mk("WO-T-003", **g.completed)
    e = mk("WO-T-004", **g.voided)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=True, limit=100
    )

    # Then 1
    assert idset(result) == {a.id, b.id, e.id}


# [claude] WKO-SF-17
def test_wko_sf_17__exclude_completed_with_status_completed_empty(db, g, mk):
    """WKO-SF-17 — exclude_completed with status COMPLETED leaves nothing.
    Rules: `_apply_sheet_list_filters` R8"""
    mk("WO-T-001", **g.completed)
    mk("WO-T-002")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, status=ST.COMPLETED, exclude_completed=True, limit=100
    )

    # Then 1
    assert result == []


# [claude] WKO-SF-18
def test_wko_sf_18__search_number_middle_any_case(db, g, mk):
    """WKO-SF-18 — search finds a part in the middle of the number, any case, with NULL description and assignee.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-T-731")
    mk("WO-T-845")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="t-73", exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-19
def test_wko_sf_19__search_description_capitals(db, g, mk):
    """WKO-SF-19 — search finds a part in the middle of the description, typed in capitals.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-T-001", description="Replace hydraulic seal")
    mk("WO-T-002", description="Replace belt")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="HYDRAULIC", exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-20
def test_wko_sf_20__search_assigned_to(db, g, mk):
    """WKO-SF-20 — search finds a part in the middle of assigned_to.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-T-001", assigned_to="Karim Uddin")
    mk("WO-T-002", assigned_to="Rahim Ali")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="rim ud", exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-21
def test_wko_sf_21__search_trimmed_stored_leading_space_matches(db, g, mk):
    """WKO-SF-21 — the search text is trimmed; a stored value with a leading space still matches.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-T-001", description=" hydraulic seal")
    mk("WO-T-002", description="Replace belt")

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        search="  hydraulic  ",
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-22
def test_wko_sf_22__match_in_any_field(db, g, mk):
    """WKO-SF-22 — a match in any one of number, description or assignee is enough.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-ZETA-1")
    b = mk("WO-T-002", description="zeta drive")
    c = mk("WO-T-003", assigned_to="Zeta Team")
    mk("WO-T-004", description="belt", assigned_to="Ali")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="Zeta", exclude_completed=False, limit=100
    )

    # Then 1
    assert idset(result) == {a.id, b.id, c.id}


# [claude] WKO-SF-23
def test_wko_sf_23__title_not_searched(db, g, mk):
    """WKO-SF-23 — the title is not searched.
    Rules: `_apply_sheet_list_filters` R9 (Q5)"""
    mk("WO-T-001")
    mk("WO-T-002", title="Belt swap")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="Oil", exclude_completed=False, limit=100
    )

    # Then 1
    assert result == []


# [claude] WKO-SF-24
def test_wko_sf_24__whitespace_search_keeps_all(db, g, mk):
    """WKO-SF-24 — a whitespace-only search keeps every row.
    Rules: `_apply_sheet_list_filters` R9"""
    a = mk("WO-T-001")
    b = mk("WO-T-002", description="belt")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="   ", exclude_completed=False, limit=100
    )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-SF-25
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2672: `%` and `_` in the work order sheet search act as wildcards",
)
def test_wko_sf_25__underscore_literal(db, g, mk):
    """WKO-SF-25 — `_` in the search matches only a real underscore.
    Rules: `_apply_sheet_list_filters` R10 [BUG-2672]"""
    a = mk("WO-T-001", description="belt_a")
    mk("WO-T-002", description="beltxa")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="t_a", exclude_completed=False, limit=100
    )

    # Then 1
    assert a.id in idset(result)
    # Then 2
    assert idset(result) == {a.id}


# [claude] WKO-SF-26
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2672: `%` and `_` in the work order sheet search act as wildcards",
)
def test_wko_sf_26__percent_literal(db, g, mk):
    """WKO-SF-26 — `%` in the search matches only a real percent sign.
    Rules: `_apply_sheet_list_filters` R10 [BUG-2672]"""
    a = mk("WO-T-001", description="50% wear")
    mk("WO-T-002", description="50 mm wear")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="50% w", exclude_completed=False, limit=100
    )

    # Then 1
    assert a.id in idset(result)
    # Then 2
    assert idset(result) == {a.id}


# [claude] WKO-SF-27
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2672: `%` and `_` in the work order sheet search act as wildcards",
)
def test_wko_sf_27__backslash_literal(db, g, mk):
    """WKO-SF-27 — a backslash in the search matches a real backslash.
    Rules: `_apply_sheet_list_filters` R10 [BUG-2672]"""
    a = mk("WO-T-001", description="C:\\tmp")
    mk("WO-T-002", description="C:tmp")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="C:\\tmp", exclude_completed=False, limit=100
    )

    # Then 1
    assert idset(result) == {a.id}


# [claude] WKO-SF-28
def test_wko_sf_28__letters_next_to_underscore_match(db, g, mk):
    """WKO-SF-28 — plain letters next to an underscore in the stored text still match.
    Rules: `_apply_sheet_list_filters` R9, R10"""
    a = mk("WO-T-001", description="belt_a")
    mk("WO-T-002", description="gear")

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, search="belt", exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-SF-29
def test_wko_sf_29__filters_combine_with_and(db, g, mk):
    """WKO-SF-29 — filters combine with AND.
    Rules: `_apply_sheet_list_filters` Purpose (AND); `_sheet_base_query` R4"""
    a = mk("WO-T-001", description="seal")
    mk("WO-T-002", description="seal", machine_id=g.MB.id)
    mk("WO-T-003", description="seal", **g.started)
    mk("WO-T-004", description="belt")

    result = dao.list_for_sheet(
        db,
        workspace_id=g.W1.id,
        machine_id=g.M1.id,
        status=ST.DRAFT,
        search="seal",
        exclude_completed=False,
        limit=100,
    )

    # Then 1
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# WorkOrderDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] WKO-GW-01
def test_wko_gw_01__newest_first(db, g, mk):
    """WKO-GW-01 — the workspace's orders, newest first, with an older row holding a higher id.
    Rules: `get_by_workspace` R1, R11 (the part that holds today), Returns"""
    a = mk("WO-T-001", created_at=C10)
    b = mk("WO-T-002", created_at=C12)
    c = mk("WO-T-003", created_at=C9)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert all(isinstance(r, WorkOrder) for r in result)
    # Then 2
    assert ids(result) == [b.id, a.id, c.id]


# [claude] WKO-GW-02
def test_wko_gw_02__only_w1_rows(db, g, mk):
    """WKO-GW-02 — only W1's rows, with W0 built before and W2 after.
    Rules: `get_by_workspace` R1"""
    mk("WO-T-001", k=0)
    a = mk("WO-T-001")
    mk("WO-T-001", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-GW-03
def test_wko_gw_03__asked_for_w2(db, g, mk):
    """WKO-GW-03 — asked for W2, only W2's row.
    Rules: `get_by_workspace` R1"""
    mk("WO-T-001", k=0)
    mk("WO-T-001")
    x2 = mk("WO-T-001", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W2.id)

    # Then 1
    assert ids(result) == [x2.id]


# [claude] WKO-GW-04
def test_wko_gw_04__asked_for_w0(db, g, mk):
    """WKO-GW-04 — asked for W0, only W0's row.
    Rules: `get_by_workspace` R1"""
    x0 = mk("WO-T-001", k=0)
    mk("WO-T-001")
    mk("WO-T-001", k=2)

    result = dao.get_by_workspace(db, workspace_id=g.W0.id)

    # Then 1
    assert ids(result) == [x0.id]


# [claude] WKO-GW-05
def test_wko_gw_05__soft_deleted_left_out(db, g, mk):
    """WKO-GW-05 — soft-deleted orders are left out.
    Rules: `get_by_workspace` R1"""
    a = mk("WO-T-001", created_at=C9)
    mk("WO-T-002", created_at=C10, **g.deleted)
    c = mk("WO-T-003", created_at=C11)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [c.id, a.id]


# [claude] WKO-GW-06
def test_wko_gw_06__machine_less_included(db, g, mk):
    """WKO-GW-06 — an order with no machine is included.
    Rules: `get_by_workspace` R1"""
    a = mk("WO-T-001", created_at=C9)
    b = mk("WO-T-002", created_at=C10, machine_id=None)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] WKO-GW-07
def test_wko_gw_07__type_filter(db, g, mk):
    """WKO-GW-07 — work_order_type_id keeps that type only, between a lower and a higher type.
    Rules: `get_by_workspace` R2"""
    mk("WO-T-001", work_order_type_id=g.TA.id)
    b = mk("WO-T-002")
    mk("WO-T-003", work_order_type_id=g.TB.id)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, work_order_type_id=g.T1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-08
def test_wko_gw_08__falsy_ids_filter_nothing(db, g, mk):
    """WKO-GW-08 — falsy type, factory and machine ids filter nothing.
    Rules: `get_by_workspace` R2, R5"""
    a = mk(
        "WO-T-001", work_order_type_id=g.TA.id, factory_id=g.FA.id, machine_id=g.MX.id
    )
    b = mk("WO-T-002")

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, work_order_type_id=0, factory_id=0, machine_id=0
    )

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-GW-09
def test_wko_gw_09__status_filter(db, g, mk):
    """WKO-GW-09 — status keeps that status only.
    Rules: `get_by_workspace` R3"""
    mk("WO-T-001")
    b = mk("WO-T-002", **g.started)
    mk("WO-T-003", **g.completed)
    mk("WO-T-004", **g.voided)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, status=ST.IN_PROGRESS)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-10
def test_wko_gw_10__no_status_gives_every_status(db, g, mk):
    """WKO-GW-10 — no status gives every status, VOIDED included.
    Rules: `get_by_workspace` R3"""
    a = mk("WO-T-001")
    b = mk("WO-T-002", **g.started)
    c = mk("WO-T-003", **g.completed)
    e = mk("WO-T-004", **g.voided)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, status=None)

    # Then 1
    assert idset(result) == {a.id, b.id, c.id, e.id}


# [claude] WKO-GW-11
def test_wko_gw_11__priority_filter(db, g, mk):
    """WKO-GW-11 — priority keeps that priority only.
    Rules: `get_by_workspace` R4"""
    mk("WO-T-001", priority=PR.LOW)
    mk("WO-T-002", priority=PR.MEDIUM)
    mk("WO-T-003", priority=PR.HIGH)
    e = mk("WO-T-004", priority=PR.URGENT)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, priority=PR.URGENT)

    # Then 1
    assert ids(result) == [e.id]


# [claude] WKO-GW-12
def test_wko_gw_12__factory_filter(db, g, mk):
    """WKO-GW-12 — factory_id keeps that factory only, between a lower and a higher factory.
    Rules: `get_by_workspace` R5"""
    mk("WO-T-001", factory_id=g.FA.id, machine_id=g.MX.id)
    b = mk("WO-T-002")
    mk("WO-T-003", factory_id=g.FB.id, machine_id=g.MY.id)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, factory_id=g.F1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-13
def test_wko_gw_13__machine_filter(db, g, mk):
    """WKO-GW-13 — machine_id keeps that machine only, between a lower and a higher machine.
    Rules: `get_by_workspace` R5"""
    mk("WO-T-001", machine_id=g.MA.id)
    b = mk("WO-T-002")
    mk("WO-T-003", machine_id=g.MB.id)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, machine_id=g.M1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-14
def test_wko_gw_14__template_filter(db, g, mk):
    """WKO-GW-14 — work_order_template_id keeps that template only, between a lower and a higher template.
    Rules: `get_by_workspace` R6"""
    mk("WO-T-001", work_order_template_id=g.PA.id)
    b = mk("WO-T-002", work_order_template_id=g.P1.id)
    mk("WO-T-003", work_order_template_id=g.PB.id)
    mk("WO-T-004")

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, work_order_template_id=g.P1.id
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-15
def test_wko_gw_15__template_zero_matches_nothing(db, g, mk):
    """WKO-GW-15 — work_order_template_id 0 filters and matches nothing.
    Rules: `get_by_workspace` R6"""
    mk("WO-T-001", work_order_template_id=g.P1.id)
    mk("WO-T-002")

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, work_order_template_id=0)

    # Then 1
    assert result == []


# [claude] WKO-GW-16
def test_wko_gw_16__no_template_filter_keeps_both(db, g, mk):
    """WKO-GW-16 — no template filter keeps orders with and without a template.
    Rules: `get_by_workspace` R6"""
    a = mk("WO-T-001", work_order_template_id=g.P1.id)
    b = mk("WO-T-002")

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, work_order_template_id=None)

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-GW-17
def test_wko_gw_17__filters_combine_with_and(db, g, mk):
    """WKO-GW-17 — filters combine with AND.
    Rules: `get_by_workspace` R7"""
    a = mk("WO-T-001")
    mk("WO-T-002", **g.started)
    mk("WO-T-003", work_order_type_id=g.TB.id)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, work_order_type_id=g.T1.id, status=ST.DRAFT
    )

    # Then 1
    assert ids(result) == [a.id]


# [claude] WKO-GW-18
def test_wko_gw_18__date_from_inclusive_drops_undated(db, g, mk):
    """WKO-GW-18 — planned_date_from is inclusive and drops undated orders.
    Rules: `get_by_workspace` R8"""
    mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    c = mk("WO-T-003", planned_date=D11)
    mk("WO-T-004", created_at=KD(10))

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, planned_date_from=D10)

    # Then 1
    assert idset(result) == {b.id, c.id}


# [claude] WKO-GW-19
def test_wko_gw_19__date_to_inclusive_drops_undated(db, g, mk):
    """WKO-GW-19 — planned_date_to is inclusive and drops undated orders.
    Rules: `get_by_workspace` R9"""
    a = mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", planned_date=D11)
    mk("WO-T-004", created_at=KD(10))

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, planned_date_to=D10)

    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] WKO-GW-20
def test_wko_gw_20__both_bounds_one_day(db, g, mk):
    """WKO-GW-20 — both bounds on one day give that day only.
    Rules: `get_by_workspace` R8, R9"""
    mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", planned_date=D11)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, planned_date_from=D10, planned_date_to=D10
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-21
def test_wko_gw_21__from_after_to_gives_nothing(db, g, mk):
    """WKO-GW-21 — from after to gives nothing.
    Rules: `get_by_workspace` R8, R9"""
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-002", planned_date=D11)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, planned_date_from=D11, planned_date_to=D10
    )

    # Then 1
    assert result == []


# [claude] WKO-GW-22
def test_wko_gw_22__skip_and_limit(db, g, mk):
    """WKO-GW-22 — skip and limit page the newest-first order.
    Rules: `get_by_workspace` R10"""
    mk("WO-T-001", created_at=C9)
    mk("WO-T-002", created_at=C10)
    c = mk("WO-T-003", created_at=C11)
    e = mk("WO-T-004", created_at=C12)
    mk("WO-T-005", created_at=C13)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [e.id, c.id]


# [claude] WKO-GW-23
def test_wko_gw_23__default_limit_100(db, g, mk_orders):
    """WKO-GW-23 — by default the first 100 rows come back.
    Rules: `get_by_workspace` R10"""
    mk_orders(1, "WO-T-", 101)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 100


# [claude] WKO-GW-24
def test_wko_gw_24__limit_1000_of_1001(db, g, mk_orders):
    """WKO-GW-24 — limit=1000 returns 1000 of 1001 rows.
    Rules: `get_by_workspace` R10"""
    mk_orders(1, "WO-T-", 1001)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id, limit=1000)

    # Then 1
    assert len(result) == 1000


# [claude] WKO-GW-25
def test_wko_gw_25__filters_before_paging(db, g, mk):
    """WKO-GW-25 — filters apply before paging: a newer deleted row and a newer W2 row do not take a place.
    Rules: `get_by_workspace` R1, R7, R10 (HR-5)"""
    mk("WO-T-001", created_at=C9)
    b = mk("WO-T-002", created_at=C10)
    mk("WO-T-003", created_at=C11)
    mk("WO-T-004", created_at=C13, **g.deleted)
    mk("WO-T-001", k=2, created_at=C14)
    mk("WO-T-005", created_at=C12, **g.started)

    result = dao.get_by_workspace(
        db, workspace_id=g.W1.id, status=ST.DRAFT, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-GW-26
def test_wko_gw_26__sql_orders_by_created_at_desc_first(db, g, mk):
    """WKO-GW-26 — the SQL orders by created_at descending first.
    Rules: `get_by_workspace` R11 (the part that holds today and after the fix)"""
    a = mk("WO-T-001")
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [a_id]
    # Then 2
    assert rec.order_part.startswith("work_orders.created_at DESC")


# [claude] WKO-GW-27
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2670: Work order list has no tie-breaker when creation times tie",
)
def test_wko_gw_27__sql_breaks_tie_by_id_desc(db, g, mk):
    """WKO-GW-27 — the SQL breaks a created_at tie by id descending.
    Rules: `get_by_workspace` R11 [BUG-2670]"""
    a = mk("WO-T-001")
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [a_id]
    # Then 2
    assert "work_orders.id DESC" in rec.order_part


# [claude] WKO-GW-28
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2670: Work order list has no tie-breaker when creation times tie",
)
def test_wko_gw_28__tie_higher_id_first(db, g, mk):
    """WKO-GW-28 — two orders made in one transaction come back higher id first.
    Rules: `get_by_workspace` R11 [BUG-2670]"""
    a = mk("WO-T-001")
    b = mk("WO-T-002")
    seqscan(db)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] WKO-GW-29
def test_wko_gw_29__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-GW-29 — one SELECT, no lock, nothing written.
    Rules: `get_by_workspace` Side effects (none); Overview (no lock)"""
    a = mk("WO-T-001")
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=w1_id)

    # Then 1
    assert ids(result) == [a_id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] WKO-GW-30
def test_wko_gw_30__pending_and_dirty_untouched(db, g, mk):
    """WKO-GW-30 — a pending order stays pending and unlisted; an unflushed edit stays unflushed.
    Rules: `get_by_workspace` Side effects (none)"""
    o1 = mk("WO-T-001")
    p = dirty_pending(db, g, o1)

    result = dao.get_by_workspace(db, workspace_id=g.W1.id)

    # Then 1
    assert len(db.new) == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert o1 in db.dirty
    # Then 4
    assert len(db.dirty) == 1
    # Then 5
    assert not db.deleted
    # Then 6
    assert ids(result) == [o1.id]


# --------------------------------------------------------------------------- #
# WorkOrderDAO.list_future_drafts_for_template_machine
# --------------------------------------------------------------------------- #


def _future(db, g, **overrides):
    """The FD cards' When: `dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id,
    work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`; `overrides` replace keywords."""
    kwargs = {
        "workspace_id": g.W1.id,
        "work_order_template_id": g.P1.id,
        "machine_id": g.M1.id,
        "after_date": D10,
    }
    kwargs.update(overrides)
    return dao.list_future_drafts_for_template_machine(db, **kwargs)


# [claude] WKO-FD-01
def test_wko_fd_01__future_drafts_by_planned_date(db, g, draft):
    """WKO-FD-01 — the template's future drafts on the machine, by planned date, whatever the insert order.
    Rules: `list_future_drafts_for_template_machine` R1, R3"""
    a = draft(D13, "WO-T-001")
    b = draft(D11, "WO-T-002")
    c = draft(D12, "WO-T-003")

    result = _future(db, g)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] WKO-FD-02
def test_wko_fd_02__after_date_exclusive(db, g, draft):
    """WKO-FD-02 — a draft on after_date itself or before is left out; the next day is in.
    Rules: `list_future_drafts_for_template_machine` R1, R2"""
    draft(D9, "WO-T-001")
    draft(D10, "WO-T-002")
    c = draft(D11, "WO-T-003")

    result = _future(db, g)

    # Then 1
    assert ids(result) == [c.id]


# [claude] WKO-FD-03
def test_wko_fd_03__non_drafts_left_out(db, g, draft):
    """WKO-FD-03 — IN_PROGRESS, COMPLETED and VOIDED orders are left out.
    Rules: `list_future_drafts_for_template_machine` R2"""
    draft(D12, "WO-T-001", **g.started)
    draft(D12, "WO-T-002", **g.completed)
    draft(D12, "WO-T-003", **g.voided)
    e = draft(D12, "WO-T-004")

    result = _future(db, g)

    # Then 1
    assert ids(result) == [e.id]


# [claude] WKO-FD-04
def test_wko_fd_04__undated_draft_left_out(db, g, mk, draft):
    """WKO-FD-04 — an undated draft is left out.
    Rules: `list_future_drafts_for_template_machine` R2"""
    mk("WO-T-001", work_order_template_id=g.P1.id)
    b = draft(D12, "WO-T-002")

    result = _future(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-FD-05
def test_wko_fd_05__other_templates_left_out(db, g, mk, draft):
    """WKO-FD-05 — drafts of a lower and a higher template, and of no template, are left out.
    Rules: `list_future_drafts_for_template_machine` R2"""
    draft(D12, "WO-T-001", work_order_template_id=g.PA.id)
    b = draft(D12, "WO-T-002")
    draft(D12, "WO-T-003", work_order_template_id=g.PB.id)
    mk("WO-T-004", planned_date=D12)

    result = _future(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-FD-06
def test_wko_fd_06__other_machines_left_out(db, g, draft):
    """WKO-FD-06 — drafts on a lower and a higher machine are left out.
    Rules: `list_future_drafts_for_template_machine` R2"""
    draft(D12, "WO-T-001", machine_id=g.MA.id)
    b = draft(D12, "WO-T-002")
    draft(D12, "WO-T-003", machine_id=g.MB.id)

    result = _future(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-FD-07
def test_wko_fd_07__asked_for_w0_nothing(db, g, mk, draft):
    """WKO-FD-07 — asked for W0 with W1's template and machine, nothing comes back.
    Rules: `list_future_drafts_for_template_machine` R2 (other workspaces)"""
    mk("WO-T-001", k=0, work_order_template_id=g.P0.id, planned_date=D12)
    draft(D12, "WO-T-002")

    result = _future(db, g, workspace_id=g.W0.id)

    # Then 1
    assert result == []


# [claude] WKO-FD-08
def test_wko_fd_08__asked_for_w2_nothing(db, g, mk, draft):
    """WKO-FD-08 — asked for W2 with W1's template and machine, nothing comes back.
    Rules: `list_future_drafts_for_template_machine` R2 (other workspaces)"""
    draft(D12, "WO-T-002")
    mk("WO-T-001", k=2, work_order_template_id=g.P2.id, planned_date=D12)

    result = _future(db, g, workspace_id=g.W2.id)

    # Then 1
    assert result == []


# [claude] WKO-FD-09
def test_wko_fd_09__soft_deleted_left_out(db, g, draft):
    """WKO-FD-09 — a soft-deleted draft is left out.
    Rules: `list_future_drafts_for_template_machine` R1, R2"""
    draft(D11, "WO-T-001", **g.deleted)
    b = draft(D12, "WO-T-002")

    result = _future(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-FD-10
def test_wko_fd_10__same_date_lower_id_first(db, g, draft):
    """WKO-FD-10 — on one planned date the lower id comes first, also when the higher id was inserted first.
    Rules: `list_future_drafts_for_template_machine` R3"""
    h = draft(D12, "WO-T-001", id=XID(1))
    lo = draft(D12, "WO-T-002")
    seqscan(db)

    result = _future(db, g)

    # Then 1
    assert ids(result) == [lo.id, h.id]


# [claude] WKO-FD-11
def test_wko_fd_11__no_limit_150(db, g):
    """WKO-FD-11 — no limit: all 150 future drafts come back.
    Rules: `list_future_drafts_for_template_machine` R3"""
    for i in range(150):
        db.add(
            _row(g, f"WO-T-{i:03d}", work_order_template_id=g.P1.id, planned_date=D12)
        )
    db.flush()

    result = _future(db, g)

    # Then 1
    assert len(result) == 150


# [claude] WKO-FD-12
def test_wko_fd_12__one_select_no_lock_nothing_written(db, g, draft):
    """WKO-FD-12 — one SELECT, no lock, nothing written.
    Rules: `list_future_drafts_for_template_machine` Side effects (none)"""
    b = draft(D12, "WO-T-001")
    b_id = b.id
    kwargs = {
        "workspace_id": g.W1.id,
        "work_order_template_id": g.P1.id,
        "machine_id": g.M1.id,
    }
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_future_drafts_for_template_machine(
            db, **kwargs, after_date=D10
        )

    # Then 1
    assert ids(result) == [b_id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# --------------------------------------------------------------------------- #
# WorkOrderDAO.list_drafts_outside_range_for_template_machine
# --------------------------------------------------------------------------- #


def _outside(db, g, **overrides):
    """The OR cards' When: `dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id,
    work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`; `overrides` replace keywords."""
    kwargs = {
        "workspace_id": g.W1.id,
        "work_order_template_id": g.P1.id,
        "machine_id": g.M1.id,
        "range_start": D10,
        "range_end": D12,
    }
    kwargs.update(overrides)
    return dao.list_drafts_outside_range_for_template_machine(db, **kwargs)


# [claude] WKO-OR-01
def test_wko_or_01__before_and_after_by_date(db, g, draft):
    """WKO-OR-01 — drafts before the start and after the end, by date; the range's inside and both edges stay out.
    Rules: `list_drafts_outside_range_for_template_machine` R1, R2, R4"""
    a = draft(D13, "WO-T-001")
    draft(D10, "WO-T-002")
    draft(D11, "WO-T-003")
    draft(D12, "WO-T-004")
    gg = draft(D9, "WO-T-005")

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [gg.id, a.id]


# [claude] WKO-OR-02
def test_wko_or_02__non_drafts_left_out(db, g, draft):
    """WKO-OR-02 — IN_PROGRESS, COMPLETED and VOIDED orders outside the range are left out.
    Rules: `list_drafts_outside_range_for_template_machine` R2"""
    draft(D9, "WO-T-001", **g.started)
    draft(D9, "WO-T-002", **g.completed)
    draft(D9, "WO-T-003", **g.voided)
    e = draft(D9, "WO-T-004")

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [e.id]


# [claude] WKO-OR-03
def test_wko_or_03__undated_left_out(db, g, mk, draft):
    """WKO-OR-03 — an undated draft is left out.
    Rules: `list_drafts_outside_range_for_template_machine` R2"""
    mk("WO-T-001", work_order_template_id=g.P1.id)
    b = draft(D13, "WO-T-002")

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-OR-04
def test_wko_or_04__other_templates_left_out(db, g, mk, draft):
    """WKO-OR-04 — drafts of a lower and a higher template, and of no template, are left out.
    Rules: `list_drafts_outside_range_for_template_machine` R2"""
    draft(D13, "WO-T-001", work_order_template_id=g.PA.id)
    b = draft(D13, "WO-T-002")
    draft(D13, "WO-T-003", work_order_template_id=g.PB.id)
    mk("WO-T-004", planned_date=D13)

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-OR-05
def test_wko_or_05__other_machines_left_out(db, g, draft):
    """WKO-OR-05 — drafts on a lower and a higher machine are left out.
    Rules: `list_drafts_outside_range_for_template_machine` R2"""
    draft(D13, "WO-T-001", machine_id=g.MA.id)
    b = draft(D13, "WO-T-002")
    draft(D13, "WO-T-003", machine_id=g.MB.id)

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-OR-06
def test_wko_or_06__asked_for_w0_nothing(db, g, mk, draft):
    """WKO-OR-06 — asked for W0 with W1's template and machine, nothing comes back.
    Rules: `list_drafts_outside_range_for_template_machine` R2 (other workspaces)"""
    mk("WO-T-001", k=0, work_order_template_id=g.P0.id, planned_date=D13)
    draft(D13, "WO-T-002")

    result = _outside(db, g, workspace_id=g.W0.id)

    # Then 1
    assert result == []


# [claude] WKO-OR-07
def test_wko_or_07__asked_for_w2_nothing(db, g, mk, draft):
    """WKO-OR-07 — asked for W2 with W1's template and machine, nothing comes back.
    Rules: `list_drafts_outside_range_for_template_machine` R2 (other workspaces)"""
    draft(D13, "WO-T-002")
    mk("WO-T-001", k=2, work_order_template_id=g.P2.id, planned_date=D13)

    result = _outside(db, g, workspace_id=g.W2.id)

    # Then 1
    assert result == []


# [claude] WKO-OR-08
def test_wko_or_08__soft_deleted_left_out(db, g, draft):
    """WKO-OR-08 — a soft-deleted draft outside the range is left out.
    Rules: `list_drafts_outside_range_for_template_machine` R1, R2"""
    draft(D9, "WO-T-001", **g.deleted)
    b = draft(D13, "WO-T-002")

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-OR-09
def test_wko_or_09__start_after_end_returns_every_dated_draft(db, g, draft):
    """WKO-OR-09 — start after end returns every dated draft.
    Rules: `list_drafts_outside_range_for_template_machine` R3"""
    a = draft(D9, "WO-T-001")
    b = draft(D10, "WO-T-002")
    c = draft(D11, "WO-T-003")
    e = draft(D12, "WO-T-004")
    gg = draft(D13, "WO-T-005")

    result = _outside(db, g, range_start=D12, range_end=D10)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id, e.id, gg.id]


# [claude] WKO-OR-10
def test_wko_or_10__one_day_range(db, g, draft):
    """WKO-OR-10 — a one-day range keeps that day out and returns the days around it.
    Rules: `list_drafts_outside_range_for_template_machine` R1, R2"""
    a = draft(D10, "WO-T-001")
    draft(D11, "WO-T-002")
    c = draft(D12, "WO-T-003")

    result = _outside(db, g, range_start=D11, range_end=D11)

    # Then 1
    assert ids(result) == [a.id, c.id]


# [claude] WKO-OR-11
def test_wko_or_11__same_date_lower_id_first(db, g, draft):
    """WKO-OR-11 — on one planned date the lower id comes first, also when the higher id was inserted first.
    Rules: `list_drafts_outside_range_for_template_machine` R4"""
    h = draft(D13, "WO-T-001", id=XID(1))
    lo = draft(D13, "WO-T-002")
    seqscan(db)

    result = _outside(db, g)

    # Then 1
    assert ids(result) == [lo.id, h.id]


# [claude] WKO-OR-12
def test_wko_or_12__no_limit_150(db, g):
    """WKO-OR-12 — no limit: all 150 drafts outside the range come back.
    Rules: `list_drafts_outside_range_for_template_machine` R4"""
    for i in range(150):
        db.add(
            _row(g, f"WO-T-{i:03d}", work_order_template_id=g.P1.id, planned_date=D13)
        )
    db.flush()

    result = _outside(db, g)

    # Then 1
    assert len(result) == 150


# [claude] WKO-OR-13
def test_wko_or_13__one_select_no_lock_nothing_written(db, g, draft):
    """WKO-OR-13 — one SELECT, no lock, nothing written.
    Rules: `list_drafts_outside_range_for_template_machine` Side effects (none)"""
    b = draft(D13, "WO-T-001")
    b_id = b.id
    kwargs = {
        "workspace_id": g.W1.id,
        "work_order_template_id": g.P1.id,
        "machine_id": g.M1.id,
    }
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_drafts_outside_range_for_template_machine(
            db, **kwargs, range_start=D10, range_end=D12
        )

    # Then 1
    assert ids(result) == [b_id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# --------------------------------------------------------------------------- #
# WorkOrderDAO.get_by_machine_date_type
# --------------------------------------------------------------------------- #


def _mdt(db, g, workspace=None):
    """The MD cards' When: `dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id,
    planned_date=D10, work_order_type_id=T1.id)`; `workspace` replaces W1."""
    return dao.get_by_machine_date_type(
        db,
        workspace_id=(workspace or g.W1).id,
        machine_id=g.M1.id,
        planned_date=D10,
        work_order_type_id=g.T1.id,
    )


# [claude] WKO-MD-01
def test_wko_md_01__draft_found(db, g, draft):
    """WKO-MD-01 — a draft of the same machine, day and type is found.
    Rules: `get_by_machine_date_type` R1"""
    draft(D9, "WO-T-001")
    b = draft(D10, "WO-T-002")
    draft(D11, "WO-T-003")

    result = _mdt(db, g)

    # Then 1
    assert isinstance(result, WorkOrder)
    # Then 2
    assert result.id == b.id


# [claude] WKO-MD-02
def test_wko_md_02__manual_order_counts(db, g, mk):
    """WKO-MD-02 — a manual order (no template) counts.
    Rules: `get_by_machine_date_type` R1"""
    a = mk("WO-T-001", planned_date=D10)

    result = _mdt(db, g)

    # Then 1
    assert result.id == a.id


# [claude] WKO-MD-03
def test_wko_md_03__in_progress_counts(db, g, mk):
    """WKO-MD-03 — an IN_PROGRESS order counts.
    Rules: `get_by_machine_date_type` R1"""
    a = mk("WO-T-001", planned_date=D10, **g.started)

    result = _mdt(db, g)

    # Then 1
    assert result.id == a.id


# [claude] WKO-MD-04
def test_wko_md_04__completed_counts(db, g, mk):
    """WKO-MD-04 — a COMPLETED order counts.
    Rules: `get_by_machine_date_type` R1"""
    a = mk("WO-T-001", planned_date=D10, **g.completed)

    result = _mdt(db, g)

    # Then 1
    assert result.id == a.id


# [claude] WKO-MD-05
def test_wko_md_05__voided_alone_none(db, g, mk):
    """WKO-MD-05 — a VOIDED order alone gives None.
    Rules: `get_by_machine_date_type` R1, R2"""
    mk("WO-T-001", planned_date=D10, **g.voided)

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-06
def test_wko_md_06__completed_beside_newer_voided(db, g, mk):
    """WKO-MD-06 — next to a newer VOIDED order, the COMPLETED one is returned.
    Rules: `get_by_machine_date_type` R1, R2"""
    a = mk("WO-T-001", planned_date=D10, created_at=C9, **g.completed)
    mk("WO-T-002", planned_date=D10, created_at=C12, **g.voided)

    result = _mdt(db, g)

    # Then 1
    assert result.id == a.id


# [claude] WKO-MD-07
def test_wko_md_07__soft_deleted_alone_none(db, g, mk):
    """WKO-MD-07 — a soft-deleted match alone gives None.
    Rules: `get_by_machine_date_type` R2"""
    mk("WO-T-001", planned_date=D10, **g.deleted)

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-08
def test_wko_md_08__other_machines_none(db, g, mk):
    """WKO-MD-08 — orders on a lower and a higher machine give None.
    Rules: `get_by_machine_date_type` R2"""
    mk("WO-T-001", planned_date=D10, machine_id=g.MA.id)
    mk("WO-T-002", planned_date=D10, machine_id=g.MB.id)

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-09
def test_wko_md_09__day_before_and_after_none(db, g, mk):
    """WKO-MD-09 — orders on the day before and the day after give None.
    Rules: `get_by_machine_date_type` R2"""
    mk("WO-T-001", planned_date=D9)
    mk("WO-T-002", planned_date=D11)

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-10
def test_wko_md_10__other_types_none(db, g, mk):
    """WKO-MD-10 — orders of a lower and a higher type give None.
    Rules: `get_by_machine_date_type` R2"""
    mk("WO-T-001", planned_date=D10, work_order_type_id=g.TA.id)
    mk("WO-T-002", planned_date=D10, work_order_type_id=g.TB.id)

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-11
def test_wko_md_11__undated_created_that_day_none(db, g, mk):
    """WKO-MD-11 — an undated order created that day gives None.
    Rules: `get_by_machine_date_type` R2"""
    mk("WO-T-001", created_at=KD(10))

    result = _mdt(db, g)

    # Then 1
    assert result is None


# [claude] WKO-MD-12
def test_wko_md_12__asked_for_w0_none(db, g, mk):
    """WKO-MD-12 — asked for W0 with W1's machine and type, None.
    Rules: `get_by_machine_date_type` R2 (other workspace)"""
    mk("WO-T-001", k=0, planned_date=D10)
    mk("WO-T-001", planned_date=D10)

    result = _mdt(db, g, workspace=g.W0)

    # Then 1
    assert result is None


# [claude] WKO-MD-13
def test_wko_md_13__asked_for_w2_none(db, g, mk):
    """WKO-MD-13 — asked for W2 with W1's machine and type, None.
    Rules: `get_by_machine_date_type` R2 (other workspace)"""
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-001", k=2, planned_date=D10)

    result = _mdt(db, g, workspace=g.W2)

    # Then 1
    assert result is None


# [claude] WKO-MD-14
def test_wko_md_14__newer_match_returned(db, g, mk):
    """WKO-MD-14 — of two matches the newer one is returned, though the older has the higher id.
    Rules: `get_by_machine_date_type` R3 (the part that holds today)"""
    a = mk("WO-T-001", planned_date=D10, created_at=C12)
    mk("WO-T-002", planned_date=D10, created_at=C9)

    result = _mdt(db, g)

    # Then 1
    assert result.id == a.id


# [claude] WKO-MD-15
def test_wko_md_15__tie_returns_one_of_them(db, g, mk):
    """WKO-MD-15 — of two matches made in one transaction, one of them is returned.
    Rules: `get_by_machine_date_type` R1, R3 (the part that holds today)"""
    a = mk("WO-T-001", planned_date=D10)
    b = mk("WO-T-002", planned_date=D10)

    result = _mdt(db, g)

    # Then 1
    assert result.id in {a.id, b.id}


# [claude] WKO-MD-16
@pytest.mark.xfail(
    strict=False,
    reason='BUG-2671: "Existing order for machine, day and type" is arbitrary among tied rows',
)
def test_wko_md_16__tie_returns_higher_id(db, g, mk):
    """WKO-MD-16 — of two matches made in one transaction, the higher id is returned.
    Rules: `get_by_machine_date_type` R3 [BUG-2671]"""
    mk("WO-T-001", planned_date=D10)
    b = mk("WO-T-002", planned_date=D10)
    seqscan(db)

    result = _mdt(db, g)

    # Then 1
    assert result.id == b.id


# [claude] WKO-MD-17
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2671: "Existing order for machine, day and type" is arbitrary among tied rows',
)
def test_wko_md_17__sql_orders_created_at_then_id_desc(db, g, mk):
    """WKO-MD-17 — the SQL orders by created_at descending, then id descending.
    Rules: `get_by_machine_date_type` R3 [BUG-2671]"""
    a = mk("WO-T-001", planned_date=D10)
    a_id = a.id
    kwargs = {
        "workspace_id": g.W1.id,
        "machine_id": g.M1.id,
        "work_order_type_id": g.T1.id,
    }
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_machine_date_type(db, planned_date=D10, **kwargs)

    # Then 1
    assert result.id == a_id
    # Then 2
    assert rec.order_part.startswith("work_orders.created_at DESC")
    # Then 3
    assert "work_orders.id DESC" in rec.order_part


# [claude] WKO-MD-18
def test_wko_md_18__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-MD-18 — one SELECT, no lock, nothing written.
    Rules: `get_by_machine_date_type` Side effects (none)"""
    a = mk("WO-T-001", planned_date=D10)
    a_id = a.id
    kwargs = {
        "workspace_id": g.W1.id,
        "machine_id": g.M1.id,
        "work_order_type_id": g.T1.id,
    }
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_machine_date_type(db, planned_date=D10, **kwargs)

    # Then 1
    assert result.id == a_id
    # Then 2
    assert rec.order_part.startswith("work_orders.created_at DESC")
    # Then 3
    assert len(rec.selects) == 1
    # Then 4
    assert "FOR UPDATE" not in rec.sql
    # Then 5
    assert rec.written == []


# --------------------------------------------------------------------------- #
# WorkOrderDAO.list_for_sheet
# --------------------------------------------------------------------------- #


# [claude] WKO-LS-01
def test_wko_ls_01__ordered_by_day_created_at_id_desc(db, g, mk):
    """WKO-LS-01 — ordered by calendar day, then created_at, then id, all descending.
    Rules: `list_for_sheet` R2"""
    gg = mk("WO-T-001", planned_date=D10, created_at=C11)
    c = mk("WO-T-002", planned_date=D10, created_at=C11)
    b = mk("WO-T-003", created_at=KD(12))
    a = mk("WO-T-004", planned_date=D10, created_at=C9)
    e = mk("WO-T-005", planned_date=D10, created_at=C11, id=XID(1))

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert ids(result) == [b.id, e.id, c.id, gg.id, a.id]


# [claude] WKO-LS-02
def test_wko_ls_02__skip_and_limit(db, g, mk):
    """WKO-LS-02 — skip and limit page that order.
    Rules: `list_for_sheet` R3"""
    mk("WO-T-001", planned_date=D9)
    mk("WO-T-002", planned_date=D10)
    c = mk("WO-T-003", planned_date=D11)
    e = mk("WO-T-004", planned_date=D12)
    mk("WO-T-005", planned_date=D13)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, skip=1, limit=2
    )

    # Then 1
    assert ids(result) == [e.id, c.id]


# [claude] WKO-LS-03
def test_wko_ls_03__default_limit_50(db, g, mk_orders):
    """WKO-LS-03 — without a limit the first 50 rows come back.
    Rules: `list_for_sheet` R3"""
    mk_orders(1, "WO-T-", 51)

    result = dao.list_for_sheet(db, workspace_id=g.W1.id, exclude_completed=False)

    # Then 1
    assert len(result) == 50


# [claude] WKO-LS-04
def test_wko_ls_04__limit_1000_of_1001(db, g, mk_orders):
    """WKO-LS-04 — limit=1000 returns 1000 of 1001 rows.
    Rules: `list_for_sheet` R3"""
    mk_orders(1, "WO-T-", 1001)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=1000
    )

    # Then 1
    assert len(result) == 1000


# [claude] WKO-LS-05
def test_wko_ls_05__filters_before_paging(db, g, mk):
    """WKO-LS-05 — filters apply before paging: hidden rows that sort first take no place.
    Rules: `list_for_sheet` R1, R3 (HR-5)"""
    mk("WO-T-001", planned_date=D9)
    b = mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", planned_date=D11)
    mk("WO-T-004", planned_date=D20, **g.deleted)
    mk("WO-T-005", planned_date=D20, machine_id=None)
    mk("WO-T-001", k=2, planned_date=D20)
    mk("WO-T-006", planned_date=D20, **g.completed)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=True, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] WKO-LS-06
def test_wko_ls_06__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-LS-06 — one SELECT, no lock, nothing written.
    Rules: `list_for_sheet` Side effects (none)"""
    a = mk("WO-T-001")
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.list_for_sheet(
            db, workspace_id=w1_id, exclude_completed=False, limit=100
        )

    # Then 1
    assert ids(result) == [a_id]
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] WKO-LS-07
def test_wko_ls_07__pending_and_dirty_untouched(db, g, mk):
    """WKO-LS-07 — a pending order stays pending and unlisted; an unflushed edit stays unflushed.
    Rules: `list_for_sheet` Side effects (none)"""
    o1 = mk("WO-T-001")
    p = dirty_pending(db, g, o1)

    result = dao.list_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=False, limit=100
    )

    # Then 1
    assert len(db.new) == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert o1 in db.dirty
    # Then 4
    assert len(db.dirty) == 1
    # Then 5
    assert not db.deleted
    # Then 6
    assert ids(result) == [o1.id]


# [claude] WKO-LS-08
def test_wko_ls_08__no_filter_lists_completed(db, g, mk):
    """WKO-LS-08 — with no filter sent, completed orders are listed (exclude_completed defaults to False).
    Rules: `list_for_sheet` R4"""
    a = mk("WO-T-001", planned_date=D10, **g.completed)
    b = mk("WO-T-002", planned_date=D11)
    c = mk("WO-T-003", planned_date=D12, **g.started)

    result = dao.list_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# --------------------------------------------------------------------------- #
# WorkOrderDAO.count_for_sheet
# --------------------------------------------------------------------------- #


# [claude] WKO-CS-01
def test_wko_cs_01__counts_over_all_pages(db, g, mk_orders):
    """WKO-CS-01 — counts what the list shows over all pages, past the list's default page of 50.
    Rules: `count_for_sheet` R1"""
    mk_orders(1, "WO-T-", 60)

    result = dao.count_for_sheet(db, workspace_id=g.W1.id, exclude_completed=False)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 60


# [claude] WKO-CS-02
def test_wko_cs_02__nothing_matches_gives_0(db, g, mk):
    """WKO-CS-02 — nothing matches gives the int 0.
    Rules: `count_for_sheet` R2"""
    mk("WO-T-001", description="belt")

    result = dao.count_for_sheet(
        db, workspace_id=g.W1.id, search="seal", exclude_completed=False
    )

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 0


# [claude] WKO-CS-03
def test_wko_cs_03__list_filters_apply(db, g, mk):
    """WKO-CS-03 — the list's filters apply: search, hide completed, status and machine.
    Rules: `count_for_sheet` R1"""
    mk("WO-T-001", description="seal")
    mk("WO-T-002", description="seal", **g.started)
    mk("WO-T-003", description="seal", **g.completed)
    mk("WO-T-004", description="seal", machine_id=g.MB.id)
    mk("WO-T-005", description="belt")

    result = dao.count_for_sheet(
        db,
        workspace_id=g.W1.id,
        machine_id=g.M1.id,
        search="seal",
        exclude_completed=True,
    )

    # Then 1
    assert result == 2


# [claude] WKO-CS-04
def test_wko_cs_04__planned_counts_future_drafts(db, g, mk):
    """WKO-CS-04 — "planned" counts only future drafts.
    Rules: `count_for_sheet` R1; `_apply_sheet_list_filters` R6"""
    mk("WO-T-001", planned_date=Y10)
    mk("WO-T-002", planned_date=Y11)
    mk("WO-T-003", planned_date=Y12)

    with clockD(Y10, MAR10):
        result = dao.count_for_sheet(
            db, workspace_id=g.W1.id, status_scope="planned", exclude_completed=False
        )

    # Then 1
    assert result == 2


# [claude] WKO-CS-05
def test_wko_cs_05__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-CS-05 — one SELECT, no lock, nothing written.
    Rules: `count_for_sheet` Side effects (none)"""
    mk("WO-T-001")
    w1_id = g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.count_for_sheet(db, workspace_id=w1_id, exclude_completed=False)

    # Then 1
    assert result == 1
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] WKO-CS-06
def test_wko_cs_06__no_filter_counts_completed(db, g, mk):
    """WKO-CS-06 — with no filter sent, completed orders are counted (exclude_completed defaults to False).
    Rules: `count_for_sheet` R3"""
    mk("WO-T-001", planned_date=D10, **g.completed)
    mk("WO-T-002", planned_date=D11)

    result = dao.count_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == 2


# --------------------------------------------------------------------------- #
# WorkOrderDAO.count_by_calendar_date_for_sheet
# --------------------------------------------------------------------------- #


# [claude] WKO-DC-01
def test_wko_dc_01__counts_per_calendar_day(db, g, mk):
    """WKO-DC-01 — counts per calendar day; days without orders are absent.
    Rules: `count_by_calendar_date_for_sheet` R1, Returns"""
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", planned_date=D12)
    mk("WO-T-004", created_at=KD(13))

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert result == {D10: 2, D12: 1, D13: 1}


# [claude] WKO-DC-02
def test_wko_dc_02__nothing_gives_empty_dict(db, g):
    """WKO-DC-02 — nothing matches gives {}.
    Rules: `count_by_calendar_date_for_sheet` Returns"""
    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {}


# [claude] WKO-DC-03
def test_wko_dc_03__other_ws_deleted_machine_less_not_counted(db, g, mk):
    """WKO-DC-03 — other workspaces, deleted and machine-less orders are not counted.
    Rules: `count_by_calendar_date_for_sheet` R1"""
    mk("WO-T-001", k=0, planned_date=D10)
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-002", planned_date=D10, **g.deleted)
    mk("WO-T-003", planned_date=D10, machine_id=None)
    mk("WO-T-001", k=2, planned_date=D10)

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {D10: 1}


# [claude] WKO-DC-04
def test_wko_dc_04__asked_for_w2(db, g, mk):
    """WKO-DC-04 — asked for W2, only W2's orders are counted.
    Rules: `count_by_calendar_date_for_sheet` R1"""
    mk("WO-T-001", k=0, planned_date=D9)
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-001", k=2, planned_date=D11)

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W2.id)

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-05
def test_wko_dc_05__factory_filter(db, g, mk):
    """WKO-DC-05 — factory_id counts that factory only.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D10, factory_id=g.FA.id, machine_id=g.MX.id)
    mk("WO-T-002", planned_date=D11)
    mk("WO-T-003", planned_date=D12, factory_id=g.FB.id, machine_id=g.MY.id)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, factory_id=g.F1.id
    )

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-06
def test_wko_dc_06__machine_filter(db, g, mk):
    """WKO-DC-06 — machine_id counts that machine only.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D10, machine_id=g.MA.id)
    mk("WO-T-002", planned_date=D11)
    mk("WO-T-003", planned_date=D12, machine_id=g.MB.id)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, machine_id=g.M1.id
    )

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-07
def test_wko_dc_07__type_filter(db, g, mk):
    """WKO-DC-07 — work_order_type_id counts that type only.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D10, work_order_type_id=g.TA.id)
    mk("WO-T-002", planned_date=D11)
    mk("WO-T-003", planned_date=D12, work_order_type_id=g.TB.id)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, work_order_type_id=g.T1.id
    )

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-08
def test_wko_dc_08__priority_filter(db, g, mk):
    """WKO-DC-08 — priority counts that priority only.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D10, priority=PR.LOW)
    mk("WO-T-002", planned_date=D11, priority=PR.HIGH)
    mk("WO-T-003", planned_date=D12, priority=PR.URGENT)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, priority=PR.HIGH
    )

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-09
def test_wko_dc_09__status_filter(db, g, mk):
    """WKO-DC-09 — status counts that status only.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D10)
    mk("WO-T-002", planned_date=D11, **g.started)
    mk("WO-T-003", planned_date=D12, **g.voided)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, status=ST.IN_PROGRESS
    )

    # Then 1
    assert result == {D11: 1}


# [claude] WKO-DC-10
def test_wko_dc_10__date_bounds_inclusive(db, g, mk):
    """WKO-DC-10 — date bounds are inclusive on the calendar day, an undated order on its creation day.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-001", planned_date=D9)
    mk("WO-T-002", planned_date=D10)
    mk("WO-T-003", created_at=KD(11))
    mk("WO-T-004", planned_date=D12)

    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, planned_date_from=D10, planned_date_to=D11
    )

    # Then 1
    assert result == {D10: 1, D11: 1}


# [claude] WKO-DC-11
def test_wko_dc_11__no_bound_every_day_no_row_limit(db, g, mk):
    """WKO-DC-11 — no date bound counts every day, years apart, and has no row limit.
    Rules: `count_by_calendar_date_for_sheet` R2"""
    mk("WO-T-A01", planned_date=date(2025, 1, 2))
    mk("WO-T-A02", planned_date=date(2027, 12, 30))
    for i in range(120):
        db.add(_row(g, f"WO-T-{i:03d}", planned_date=D10))
    db.flush()

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {date(2025, 1, 2): 1, date(2027, 12, 30): 1, D10: 120}


# [claude] WKO-DC-12
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2675: Sheet calendar dots ignore "hide completed", "Planned" and the search',
)
def test_wko_dc_12__exclude_completed_drops_completed(db, g, mk):
    """WKO-DC-12 — exclude_completed drops completed orders from the dots.
    Rules: `count_by_calendar_date_for_sheet` R3 [BUG-2675]"""
    mk("WO-T-001", planned_date=D10, **g.completed)
    mk("WO-T-002", planned_date=D11)

    # Then 1 (today the call itself raises TypeError)
    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, exclude_completed=True
    )

    assert result == {D11: 1}


# [claude] WKO-DC-13
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2675: Sheet calendar dots ignore "hide completed", "Planned" and the search',
)
def test_wko_dc_13__search_narrows_dots(db, g, mk):
    """WKO-DC-13 — search narrows the dots as it narrows the list.
    Rules: `count_by_calendar_date_for_sheet` R3 [BUG-2675]"""
    mk("WO-T-001", planned_date=D10, description="seal")
    mk("WO-T-002", planned_date=D11, description="belt")

    # Then 1 (today the call itself raises TypeError)
    result = dao.count_by_calendar_date_for_sheet(
        db, workspace_id=g.W1.id, search="SEAL"
    )

    assert result == {D10: 1}


# [claude] WKO-DC-14
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2675: Sheet calendar dots ignore "hide completed", "Planned" and the search',
)
def test_wko_dc_14__planned_narrows_dots(db, g, mk):
    """WKO-DC-14 — status_scope "planned" narrows the dots to future drafts.
    Rules: `count_by_calendar_date_for_sheet` R3 [BUG-2675]"""
    mk("WO-T-001", planned_date=Y9)
    mk("WO-T-002", planned_date=Y11)
    mk("WO-T-003", planned_date=Y12, **g.started)

    with clockD(Y10, MAR10):
        # Then 1 (today the call itself raises TypeError)
        result = dao.count_by_calendar_date_for_sheet(
            db, workspace_id=g.W1.id, status_scope="planned"
        )

    assert result == {Y11: 1}


# [claude] WKO-DC-15
def test_wko_dc_15__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-DC-15 — one SELECT, no lock, nothing written.
    Rules: `count_by_calendar_date_for_sheet` Side effects (none)"""
    mk("WO-T-001", planned_date=D10)
    w1_id = g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.count_by_calendar_date_for_sheet(db, workspace_id=w1_id)

    # Then 1
    assert result == {D10: 1}
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] WKO-DC-16
def test_wko_dc_16__no_new_keyword_counts_all(db, g, mk):
    """WKO-DC-16 — with none of the new keywords sent, completed, non-planned and every-text orders are counted.
    Rules: `count_by_calendar_date_for_sheet` R3 (defaults; holds today and after the BUG-2675 fix)"""
    mk("WO-T-001", planned_date=D10, **g.completed)
    mk("WO-T-002", planned_date=D11, description="belt", **g.started)
    mk("WO-T-003", planned_date=D11, description="seal")

    result = dao.count_by_calendar_date_for_sheet(db, workspace_id=g.W1.id)

    # Then 1
    assert result == {D10: 1, D11: 2}


# [claude] WKO-DC-17
@pytest.mark.xfail(
    strict=True,
    reason='BUG-2675: Sheet calendar dots ignore "hide completed", "Planned" and the search',
)
def test_wko_dc_17__new_keywords_at_defaults(db, g, mk):
    """WKO-DC-17 — the new keywords sent at their defaults count exactly as no keyword.
    Rules: `count_by_calendar_date_for_sheet` R3 [BUG-2675]"""
    mk("WO-T-001", planned_date=D10, **g.completed)
    mk("WO-T-002", planned_date=D11, description="belt", **g.started)
    mk("WO-T-003", planned_date=D11, description="seal")

    # Then 1 (today the call itself raises TypeError)
    result = dao.count_by_calendar_date_for_sheet(
        db,
        workspace_id=g.W1.id,
        status_scope=None,
        exclude_completed=False,
        search=None,
    )

    assert result == {D10: 1, D11: 2}


# --------------------------------------------------------------------------- #
# WorkOrderDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] WKO-GI-01
def test_wko_gi_01__returns_row_by_id(db, g, mk):
    """WKO-GI-01 — returns the row by id, between a lower and a higher id.
    Rules: `get_by_id_and_workspace` R1"""
    mk("WO-T-001")
    b = mk("WO-T-002")
    mk("WO-T-003")

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, WorkOrder)
    # Then 2
    assert result.id == b.id
    # Then 3
    assert result.work_order_number == "WO-T-002"


# [claude] WKO-GI-02
def test_wko_gi_02__soft_deleted_returned(db, g, mk):
    """WKO-GI-02 — a soft-deleted row is returned.
    Rules: `get_by_id_and_workspace` R1"""
    a = mk("WO-T-001", **g.deleted)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=g.W1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] WKO-GI-03
def test_wko_gi_03__unknown_id_none(db, g, mk):
    """WKO-GI-03 — an unknown id gives None.
    Rules: `get_by_id_and_workspace` R2"""
    mk("WO-T-001")

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] WKO-GI-04
def test_wko_gi_04__w0_row_with_w1_none(db, g, mk):
    """WKO-GI-04 — W0's row asked with W1 gives None.
    Rules: `get_by_id_and_workspace` R2"""
    x0 = mk("WO-T-001", k=0)
    mk("WO-T-001")

    result = dao.get_by_id_and_workspace(db, id=x0.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] WKO-GI-05
def test_wko_gi_05__w2_row_with_w1_none(db, g, mk):
    """WKO-GI-05 — W2's row asked with W1 gives None.
    Rules: `get_by_id_and_workspace` R2"""
    mk("WO-T-001")
    x2 = mk("WO-T-001", k=2)

    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=g.W1.id)

    # Then 1
    assert result is None


# [claude] WKO-GI-06
def test_wko_gi_06__w2_own_row(db, g, mk):
    """WKO-GI-06 — asked with W2, W2's own row comes back, though a W1 row comes earlier.
    Rules: `get_by_id_and_workspace` R1, R2"""
    mk("WO-T-001")
    x2 = mk("WO-T-001", k=2)

    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=g.W2.id)

    # Then 1
    assert result.id == x2.id


# [claude] WKO-GI-07
def test_wko_gi_07__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-GI-07 — one SELECT, no lock, nothing written.
    Rules: `get_by_id_and_workspace` Side effects (none)"""
    a = mk("WO-T-001")
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace(db, id=a_id, workspace_id=w1_id)

    # Then 1
    assert result.id == a_id
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


@pytest.mark.parametrize(
    ("stored", "read_back"),
    [
        pytest.param("2.125", "2.13", id="WKO-GI-08"),
        pytest.param("0.005", "0.01", id="WKO-GI-09"),
        pytest.param("-1.005", "-1.01", id="WKO-GI-10"),
        pytest.param("2.124", "2.12", id="WKO-GI-11"),
    ],
)
# [claude] WKO-GI-08, GI-09, GI-10, GI-11
def test_wko_gi_08_11__cost_rounded_half_up(db, g, mk, stored, read_back):
    """WKO-GI-08 … GI-11 — cost 2.125 / 0.005 / -1.005 / 2.124 is stored and read back as 2.13 / 0.01 / -1.01 / 2.12.
    Rules: Overview model facts (`cost` Numeric(15, 2)); HR-15"""
    a = mk("WO-T-001", cost=Decimal(stored))
    a_id, w1_id = a.id, g.W1.id
    db.expunge_all()

    result = dao.get_by_id_and_workspace(db, id=a_id, workspace_id=w1_id)

    # Then 1
    assert result.cost == Decimal(read_back)


# --------------------------------------------------------------------------- #
# WorkOrderDAO.get_next_number
# --------------------------------------------------------------------------- #


# [claude] WKO-NN-01
def test_wko_nn_01__none_yet_gives_001(db, g):
    """WKO-NN-01 — no number of the year yet gives WO-2031-001.
    Rules: `get_next_number` R1, R2 (both clocks agree), Returns"""
    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "WO-2031-001"


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        pytest.param(("WO-2031-040", "WO-2031-041"), "WO-2031-042", id="WKO-NN-02"),
        pytest.param(("WO-2031-998",), "WO-2031-999", id="WKO-NN-04"),
        pytest.param(("WO-2031-998", "WO-2031-999"), "WO-2031-1000", id="WKO-NN-05"),
        pytest.param(("WO-2031-1000",), "WO-2031-1001", id="WKO-NN-06"),
        pytest.param(("WO-2031-abc",), "WO-2031-001", id="WKO-NN-10"),
        pytest.param(("wo-2031-050", "Wo-2031-060"), "WO-2031-001", id="WKO-NN-18"),
        pytest.param(
            ("XWO-2031-050", " WO-2031-060", "WO-20310-070", "WO-2031_080"),
            "WO-2031-001",
            id="WKO-NN-19",
        ),
    ],
)
# [claude] WKO-NN-02, NN-04, NN-05, NN-06, NN-10, NN-18, NN-19
def test_wko_nn_next_after_stored_numbers(db, g, mk, numbers, expected):
    """WKO-NN-02 / 04 / 05 / 06 / 10 / 18 / 19 — the next number after the W1 numbers stored.
    Rules: `get_next_number` R1, R3, R4, R5 (NN-02 -041 → -042; NN-04 -998 → -999; NN-05 -999 → -1000;
    NN-06 -1000 → -1001; NN-10 non-digit alone → -001; NN-18 case-sensitive prefix; NN-19 prefix elsewhere)"""
    for number in numbers:
        mk(number)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == expected


# [claude] WKO-NN-03
def test_wko_nn_03__after_009_comes_010(db, g, mk_orders):
    """WKO-NN-03 — after -009 comes -010.
    Rules: `get_next_number` R3 (padding)"""
    mk_orders(1, "WO-2031-", 9)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2031-010"


_BUG_2676 = "BUG-2676: Work order numbers stop working after 999 in a year"


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        pytest.param(("WO-2031-999", "WO-2031-1000"), "WO-2031-1001", id="WKO-NN-07"),
        pytest.param(("WO-2031-010", "WO-2031-5"), "WO-2031-011", id="WKO-NN-08"),
        pytest.param(("WO-2031-005", "WO-2031-abc"), "WO-2031-006", id="WKO-NN-09"),
        pytest.param(("WO-2031-005", "WO-2031-1-2"), "WO-2031-006", id="WKO-NN-26"),
        pytest.param(("WO-2031-005", "WO-2031-1_000"), "WO-2031-006", id="WKO-NN-27"),
    ],
)
@pytest.mark.xfail(strict=True, reason=_BUG_2676)
# [claude] WKO-NN-07, NN-08, NN-09, NN-26, NN-27
def test_wko_nn_numeric_highest_suffix(db, g, mk, numbers, expected):
    """WKO-NN-07 / 08 / 09 / 26 / 27 — the next number is the numerically highest all-digit suffix plus one.
    Rules: `get_next_number` R3, R3a, R4 [BUG-2676] (NN-07 -999 + -1000; NN-08 unpadded -5 + -010;
    NN-09 -abc beside -005; NN-26 inner dash -1-2 beside -005; NN-27 underscore -1_000 beside -005)"""
    for number in numbers:
        mk(number)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result.startswith("WO-2031-")
    # Then 2
    assert result == expected


# [claude] WKO-NN-11
def test_wko_nn_11__soft_deleted_still_counts(db, g, mk):
    """WKO-NN-11 — a soft-deleted -005 still counts.
    Rules: `get_next_number` R5"""
    mk("WO-2031-004")
    mk("WO-2031-005", **g.deleted)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2031-006"


# [claude] WKO-NN-12
def test_wko_nn_12__other_years_do_not_count(db, g, mk):
    """WKO-NN-12 — numbers of the year before and the year after do not count.
    Rules: `get_next_number` R5"""
    mk("WO-2030-050")
    mk("WO-2031-003")
    mk("WO-2032-070")

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2031-004"


# [claude] WKO-NN-13
def test_wko_nn_13__only_w1_numbers(db, g, mk):
    """WKO-NN-13 — only W1's numbers count, with higher numbers in W0 and W2.
    Rules: `get_next_number` R5, R6"""
    mk("WO-2031-020", k=0)
    mk("WO-2031-003")
    mk("WO-2031-030", k=2)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2031-004"


# [claude] WKO-NN-14
def test_wko_nn_14__asked_for_w2(db, g, mk):
    """WKO-NN-14 — asked for W2, only W2's numbers count.
    Rules: `get_next_number` R6"""
    mk("WO-2031-020", k=0)
    mk("WO-2031-040")
    mk("WO-2031-007", k=2)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W2.id)

    # Then 1
    assert result == "WO-2031-008"


# [claude] WKO-NN-15
def test_wko_nn_15__asked_for_w0(db, g, mk):
    """WKO-NN-15 — asked for W0, only W0's numbers count.
    Rules: `get_next_number` R6"""
    mk("WO-2031-007", k=0)
    mk("WO-2031-040")
    mk("WO-2031-050", k=2)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W0.id)

    # Then 1
    assert result == "WO-2031-008"


# [claude] WKO-NN-16
def test_wko_nn_16__another_ws_may_hold_the_number(db, g, mk):
    """WKO-NN-16 — another workspace may hold the number W1 gets, and W1 can store it.
    Rules: `get_next_number` R6 (unique per workspace)"""
    mk("WO-2031-001", k=2)
    with clockN(JUNE, JUNE):
        n = dao.get_next_number(db, workspace_id=g.W1.id)

    a = _row(g, n)
    db.add(a)
    db.flush()

    # Then 1
    assert n == "WO-2031-001"
    # Then 2
    row = reread(db, a.id)
    assert row.work_order_number == "WO-2031-001"
    assert row.workspace_id == g.W1.id


# [claude] WKO-NN-17
def test_wko_nn_17__same_number_twice_refused(db, g, mk):
    """WKO-NN-17 — the same number twice in one workspace is refused by the database.
    Rules: `get_next_number` R6; Overview model facts (`uq_wo_workspace_number`)"""
    mk("WO-2031-001")
    w1_id = g.W1.id
    duplicate = _row(g, "WO-2031-001")

    # Then 1
    with clockN(JUNE, JUNE):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                db.add(duplicate)
                db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert exc.value.orig.diag.constraint_name == "uq_wo_workspace_number"
    # Then 4
    assert (
        db.scalar(
            text("SELECT count(*) FROM work_orders WHERE workspace_id = :w"),
            {"w": w1_id},
        )
        == 1
    )


_BUG_2678 = "BUG-2678: A work order number's year comes from the server's local clock"


# [claude] WKO-NN-20
@pytest.mark.xfail(strict=True, reason=_BUG_2678)
def test_wko_nn_20__utc_year_local_already_next_year(db, g, mk):
    """WKO-NN-20 — the year comes from UTC when the local clock is already in the next year.
    Rules: `get_next_number` R2 [BUG-2678]"""
    mk("WO-2031-007")

    with clockN(datetime(2032, 1, 1, 5, 0), datetime(2031, 12, 31, 23, 0)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result.startswith("WO-")
    # Then 2
    assert result == "WO-2031-008"


# [claude] WKO-NN-21
@pytest.mark.xfail(strict=True, reason=_BUG_2678)
def test_wko_nn_21__utc_year_local_still_old_year(db, g, mk):
    """WKO-NN-21 — the year comes from UTC when the local clock is still in the old year.
    Rules: `get_next_number` R2 [BUG-2678]"""
    mk("WO-2031-007")

    with clockN(datetime(2031, 12, 31, 19, 0), datetime(2032, 1, 1, 0, 30)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result.startswith("WO-")
    # Then 2
    assert result == "WO-2032-001"


# [claude] WKO-NN-22
def test_wko_nn_22__both_clocks_2032(db, g, mk):
    """WKO-NN-22 — with both clocks in 2032, last year's numbers do not count.
    Rules: `get_next_number` R1, R2, R5"""
    mk("WO-2031-007")

    with clockN(datetime(2032, 3, 1, 12, 0), datetime(2032, 3, 1, 12, 0)):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2032-001"


# [claude] WKO-NN-23
def test_wko_nn_23__writes_nothing(db, g, mk):
    """WKO-NN-23 — writes nothing: a pending number is not counted and stays pending, an unflushed edit stays unflushed.
    Rules: `get_next_number` Side effects (reads only)"""
    o1 = mk("WO-2031-001")
    o1.title = "Edited"
    p = _row(g, "WO-2031-009")
    db.add(p)

    with clockN(JUNE, JUNE):
        result = dao.get_next_number(db, workspace_id=g.W1.id)

    # Then 1
    assert result == "WO-2031-002"
    # Then 2
    assert len(db.new) == 1
    # Then 3
    assert p in db.new
    # Then 4
    assert o1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted


# [claude] WKO-NN-24
def test_wko_nn_24__one_select_no_lock_nothing_written(db, g, mk):
    """WKO-NN-24 — one SELECT, no lock, nothing written.
    Rules: `get_next_number` Side effects; Overview (no lock)"""
    mk("WO-2031-001")
    w1_id = g.W1.id
    db.expunge_all()

    with clockN(JUNE, JUNE):
        with StatementRecorder(db) as rec:
            result = dao.get_next_number(db, workspace_id=w1_id)

    # Then 1
    assert result == "WO-2031-002"
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql
    # Then 4
    assert rec.written == []


# [claude] WKO-NN-25
def test_wko_nn_25__positional_arguments_raise(db, g):
    """WKO-NN-25 — positional arguments raise TypeError.
    Rules: `get_next_number` signature (keyword-only)"""
    # Then 1
    with clockN(JUNE, JUNE):
        with pytest.raises(TypeError):
            dao.get_next_number(db, g.W1.id)


# --------------------------------------------------------------------------- #
# WorkOrderDAO.soft_delete
# --------------------------------------------------------------------------- #


# [claude] WKO-SD-01
def test_wko_sd_01__sets_delete_fields_returns_same_object(db, g, mk):
    """WKO-SD-01 — sets the four delete fields and returns the same object.
    Rules: `soft_delete` R1, Returns"""
    o = mk("WO-T-001")

    result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert result is o
    # Then 2
    row = reread(db, o.id)
    assert row.is_active is False
    assert row.is_deleted is True
    assert row.deleted_by == g.U2.id
    # Then 3
    assert row.deleted_at is not None
    # Then 4
    assert isinstance(row.deleted_at, datetime)


# [claude] WKO-SD-02
def test_wko_sd_02__flushed(db, g, mk):
    """WKO-SD-02 — the change is flushed: a raw SELECT sees it with no flush by the test.
    Rules: `soft_delete` R1 (flushes)"""
    o = mk("WO-T-001")

    dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert o not in db.dirty
    # Then 2
    assert (
        db.scalar(text("SELECT is_deleted FROM work_orders WHERE id = :i"), {"i": o.id})
        is True
    )
    # Then 3
    assert (
        db.scalar(text("SELECT deleted_by FROM work_orders WHERE id = :i"), {"i": o.id})
        == g.U2.id
    )


# [claude] WKO-SD-03
def test_wko_sd_03__other_fields_unchanged(db, g, mk):
    """WKO-SD-03 — status and every other field are unchanged; updated_by is not written.
    Rules: `soft_delete` R2"""
    o = mk(
        "WO-T-001",
        status="IN_PROGRESS",
        description="seal",
        assigned_to="Karim",
        planned_date=D10,
        cost=Decimal("12.50"),
        priority=PR.HIGH,
        work_order_template_id=g.P1.id,
        created_at=C9,
        updated_by=g.U3.id,
    )

    result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert result is o
    # Then 2
    row = reread(db, o.id)
    assert row.status == "IN_PROGRESS"
    assert row.description == "seal"
    assert row.assigned_to == "Karim"
    assert row.title == "Oil change"
    # Then 3
    assert row.planned_date == D10
    assert row.cost == Decimal("12.50")
    assert row.priority == PR.HIGH
    # Then 4
    assert row.work_order_number == "WO-T-001"
    assert row.machine_id == g.M1.id
    assert row.factory_id == g.F1.id
    assert row.work_order_template_id == g.P1.id
    # Then 5
    assert row.created_at == C9
    assert row.created_by == g.U1.id
    # Then 6
    assert row.updated_by == g.U3.id


# [claude] WKO-SD-04
def test_wko_sd_04__only_one_update_of_work_orders(db, g, mk):
    """WKO-SD-04 — only the work order row is written: one UPDATE of work_orders, no DELETE.
    Rules: `soft_delete` R2 (lines and approvers untouched)"""
    o = mk("WO-T-001")
    u2_id = g.U2.id

    with StatementRecorder(db) as rec:
        result = dao.soft_delete(db, db_obj=o, deleted_by=u2_id)

    # Then 1
    assert result is o
    # Then 2
    assert len(rec.written) == 1
    # Then 3
    assert rec.written[0].lstrip().upper().startswith("UPDATE WORK_ORDERS")


# [claude] WKO-SD-05
def test_wko_sd_05__already_deleted_stamped_again(db, g, mk):
    """WKO-SD-05 — an already deleted row is stamped again.
    Rules: `soft_delete` R3"""
    o = mk("WO-T-001", **g.deleted)

    result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert result is o
    # Then 2
    row = reread(db, o.id)
    assert row.deleted_by == g.U2.id
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    assert row.deleted_at != DT0


# [claude] WKO-SD-06
def test_wko_sd_06__another_order_untouched(db, g, mk):
    """WKO-SD-06 — another order is not touched.
    Rules: `soft_delete` R2"""
    a = mk("WO-T-001")
    o = mk("WO-T-002")
    c = mk("WO-T-003")

    result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert result is o
    # Then 2
    row_a = reread(db, a.id)
    assert row_a.is_deleted is False
    assert row_a.is_active is True
    assert row_a.deleted_at is None
    assert row_a.deleted_by is None
    # Then 3
    row_c = reread(db, c.id)
    assert row_c.is_deleted is False
    assert row_c.is_active is True
    assert row_c.deleted_at is None
    assert row_c.deleted_by is None


# [claude] WKO-SD-07
def test_wko_sd_07__does_not_commit(db, g, mk):
    """WKO-SD-07 — does not commit.
    Rules: Overview (never commits)"""
    o = mk("WO-T-001")
    o_id, u2_id = o.id, g.U2.id

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.soft_delete(db, db_obj=o, deleted_by=u2_id)

    # Then 1
    assert result is o
    # Then 2
    assert cm.call_count == 0
    sp.rollback()
    # Then 3
    row = reread(db, o_id)
    assert row.is_deleted is False
    assert row.deleted_by is None
    assert row.deleted_at is None


_BUG_2679 = "BUG-2679: A work order's delete time depends on the database's time zone"


# [claude] WKO-SD-08
@pytest.mark.xfail(strict=True, reason=_BUG_2679)
def test_wko_sd_08__deleted_at_is_utcnow(db, g, mk):
    """WKO-SD-08 — deleted_at is utcnow(), not the database clock, under Dhaka.
    Rules: `soft_delete` R1a [BUG-2679]"""
    dhaka(db)
    o = mk("WO-T-001")

    with patch("app.dao.work_order.utcnow", create=True, return_value=SDT):
        with patch("app.utils.time.utcnow", return_value=SDT):
            result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)

    # Then 1
    assert result is o
    # Then 2
    row = reread(db, o.id)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == SDT


# [claude] WKO-SD-09
@pytest.mark.xfail(strict=True, reason=_BUG_2679)
def test_wko_sd_09__deleted_at_between_utc_reads(db, g, mk):
    """WKO-SD-09 — deleted_at falls between the UTC times read before and after the call, under Dhaka.
    Rules: `soft_delete` R1a [BUG-2679]"""
    dhaka(db)
    o = mk("WO-T-001")
    before = utc_now() - timedelta(seconds=1)

    result = dao.soft_delete(db, db_obj=o, deleted_by=g.U2.id)
    after = utc_now() + timedelta(seconds=1)

    # Then 1
    assert result is o
    # Then 2
    row = reread(db, o.id)
    assert row.deleted_at is not None
    # Then 3
    assert before <= row.deleted_at <= after
