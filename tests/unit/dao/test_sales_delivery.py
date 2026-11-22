"""Unit tests for app/dao/sales_delivery.py.

Implements tests/unit/dao/sales_delivery.cases.md (revision 2), one test per case,
in card order. Real Postgres session (`db` fixture).

Patched: only the clock of the `CW` cards (Conventions, Externals: clock(L, U)
patches `app.dao.sales_delivery.datetime`, `app.dao.sales_delivery.utcnow` with
`create=True` and `app.utils.time.utcnow`). A `CW` card runs under
clock(2026-06-01 12:00, 2026-06-01 12:00) unless it has its own clock line or
says "no clock" (CW-11, CW-12: nothing patched; `created_at` checked by window).
No race simulations.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`, and naive datetimes for the clock values)
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.sales_delivery import sales_delivery_dao
from app.models.account import Account
from app.models.delivery_method import DeliveryMethod
from app.models.factory import Factory
from app.models.sales_delivery import SalesDelivery
from app.models.sales_order import SalesOrder
from app.models.status import Status
from app.schemas.sales_delivery import SalesDeliveryCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton sales_delivery_dao"
dao = sales_delivery_dao

# Convention "MISSING"
MISSING = 999999999

# Convention "DA, DB, DC"
DA = date(2026, 7, 1)
DB = date(2026, 7, 2)
DC = date(2026, 7, 3)

# Convention "A CW card runs under clock(2026-06-01 12:00, 2026-06-01 12:00) unless ..."
DEFAULT_CLOCK = (datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0))


def utc_now():
    """The cards' `datetime.now(timezone.utc).replace(tzinfo=None)`."""
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
    """The standing rows by their Conventions names: g.W0 ... g.DM9, plus g.TAG.

    Order: W0, W1, W2, U1, U2, U3; per workspace k in 0, 1, 2: ACk, Fk, Sk;
    orders SO0 (W0), SO1, SO2, SO3 (W1), SO9 (W2); DM1 (W1), DM9 (W2).
    """
    n = SimpleNamespace(TAG=uuid.uuid4().hex[:8])
    n.W0, n.W1, n.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    n.U1, n.U2, n.U3 = make_profile(db), make_profile(db), make_profile(db)
    for k in (0, 1, 2):
        ws = getattr(n, f"W{k}")
        setattr(n, f"AC{k}", _add(db, Account(workspace_id=ws.id, name="Acme")))
        setattr(
            n,
            f"F{k}",
            _add(db, Factory(workspace_id=ws.id, name="Plant", abbreviation=f"P{k}")),
        )
        setattr(
            n,
            f"S{k}",
            _add(db, Status(workspace_id=ws.id, name="Draft", comment="Stage")),
        )
    for name, k, suffix in (
        ("SO0", 0, "0"),
        ("SO1", 1, "1"),
        ("SO2", 1, "2"),
        ("SO3", 1, "3"),
        ("SO9", 2, "9"),
    ):
        order = SalesOrder(
            workspace_id=getattr(n, f"W{k}").id,
            sales_order_number=f"SO-{n.TAG}-{suffix}",
            account_id=getattr(n, f"AC{k}").id,
            factory_id=getattr(n, f"F{k}").id,
            order_date=date(2026, 3, 1),
            total_amount=0,
            current_status_id=getattr(n, f"S{k}").id,
            created_by=n.U1.id,
        )
        setattr(n, name, _add(db, order))
    n.DM1 = _add(db, DeliveryMethod(workspace_id=n.W1.id, name="Courier"))
    n.DM9 = _add(db, DeliveryMethod(workspace_id=n.W2.id, name="Truck"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given-row builders and steps
# --------------------------------------------------------------------------- #


@pytest.fixture
def mk_delivery(db, g):
    """Convention "delivery": mk_delivery(name, **but) -> SalesDelivery, flushed.

    Defaults: workspace W1, order SO2, number f"DV-{TAG}-<name>", status "planned", creator U1.
    """

    def _mk(name, **columns):
        fields = {
            "workspace_id": g.W1.id,
            "sales_order_id": g.SO2.id,
            "delivery_number": f"DV-{g.TAG}-{name}",
            "delivery_status": "planned",
            "created_by": g.U1.id,
        }
        fields.update(columns)
        return _add(db, SalesDelivery(**fields))

    return _mk


def add_many(db, g, numbers):
    """The cards' `for k in ...: db.add(SalesDelivery(W1, SO2, <number>, "planned", U1))`, then one flush."""
    for number in numbers:
        db.add(
            SalesDelivery(
                workspace_id=g.W1.id,
                sales_order_id=g.SO2.id,
                delivery_number=number,
                delivery_status="planned",
                created_by=g.U1.id,
            )
        )
    db.flush()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "bump(X)"
def bump(db, row):
    db.execute(
        text("UPDATE sales_deliveries SET notes = notes WHERE id = :i"), {"i": row.id}
    )


# Convention "Dhaka"
def dhaka(db):
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# Convention "clock(L, U)"
@contextmanager
def clock(local, utc):
    class _LocalClock(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return local

    with patch("app.dao.sales_delivery.datetime", _LocalClock):
        with patch("app.dao.sales_delivery.utcnow", create=True, return_value=utc):
            with patch("app.utils.time.utcnow", return_value=utc):
                yield


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #


# Convention "ids(result)" / "idset(result)"
def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


# Convention "re-read X"
def reread(db, row_id):
    db.expire_all()
    return db.execute(
        select(SalesDelivery).where(SalesDelivery.id == row_id)
    ).scalar_one()


# Convention "count(Wk)"
def count(db, ws):
    return db.scalar(
        text("SELECT count(*) FROM sales_deliveries WHERE workspace_id = :w"),
        {"w": ws.id},
    )


# Convention "nothing written": count(W0), count(W1), count(W2)
def counts(db, g):
    return (count(db, g.W0), count(db, g.W1), count(db, g.W2))


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
        """The one SELECT from sales_deliveries; fails loudly unless there is exactly one."""
        [statement] = [
            s
            for s in self.statements
            if s.lstrip().upper().startswith("SELECT") and "sales_deliveries" in s
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


def create_w1(db, g, **schema_fields):
    """The CW cards' `create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2, delivery_method_id=DM1, ...), W1, U1)`."""
    fields = {"sales_order_id": g.SO2.id, "delivery_method_id": g.DM1.id}
    fields.update(schema_fields)
    return dao.create_with_user(
        db, obj_in=SalesDeliveryCreate(**fields), workspace_id=g.W1.id, user_id=g.U1.id
    )


# --------------------------------------------------------------------------- #
# DAOSalesDelivery.generate_delivery_number
# --------------------------------------------------------------------------- #


# [claude] SDV-GN-01
def test_sdv_gn_01__no_delivery_gives_001(db, g):
    """SDV-GN-01 — no delivery yet gives DEL-2026-001.
    Rules: `generate_delivery_number` R1, Returns"""
    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-001"


# [claude] SDV-GN-02
def test_sdv_gn_02__two_deliveries_give_003(db, g, mk_delivery):
    """SDV-GN-02 — two deliveries give DEL-2026-003.
    Rules: `generate_delivery_number` R1"""
    mk_delivery("A", delivery_number="DEL-2026-001")
    mk_delivery("B", delivery_number="DEL-2026-002")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-003"


# [claude] SDV-GN-03, GN-04
@pytest.mark.parametrize(
    ("n", "expected"),
    [
        pytest.param(9, "DEL-2026-010", id="SDV-GN-03"),
        pytest.param(999, "DEL-2026-1000", id="SDV-GN-04"),
    ],
)
def test_sdv_gn_03_04__count_boundaries(db, g, n, expected):
    """SDV-GN-03 / GN-04 — nine deliveries give DEL-2026-010 (padded); 999 give DEL-2026-1000 (not cut).
    Rules: `generate_delivery_number` R1"""
    add_many(db, g, [f"DEL-2026-{k:03d}" for k in range(1, n + 1)])

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == expected


# [claude] SDV-GN-05
def test_sdv_gn_05__w0_and_w2_do_not_count_for_w1(db, g, mk_delivery):
    """SDV-GN-05 — deliveries of W0 and W2 do not count for W1.
    Rules: `generate_delivery_number` R2"""
    mk_delivery(
        "X0",
        workspace_id=g.W0.id,
        sales_order_id=g.SO0.id,
        delivery_number=f"DEL-2026-{g.TAG}a",
    )
    mk_delivery(
        "X1",
        workspace_id=g.W0.id,
        sales_order_id=g.SO0.id,
        delivery_number=f"DEL-2026-{g.TAG}b",
    )
    mk_delivery("A", delivery_number="DEL-2026-001")
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number=f"DEL-2026-{g.TAG}c",
    )
    mk_delivery(
        "X3",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number=f"DEL-2026-{g.TAG}d",
    )

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"


# [claude] SDV-GN-06
def test_sdv_gn_06__w0_ignores_later_w1_and_w2(db, g, mk_delivery):
    """SDV-GN-06 — asked for W0, the later W1 and W2 deliveries do not count.
    Rules: `generate_delivery_number` R2"""
    mk_delivery("A", delivery_number=f"DEL-2026-{g.TAG}a")
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number=f"DEL-2026-{g.TAG}c",
    )

    result = dao.generate_delivery_number(db, workspace_id=g.W0.id, year=2026)

    # Then 1
    assert result == "DEL-2026-001"


# [claude] SDV-GN-07
def test_sdv_gn_07__w2_counts_only_its_own(db, g, mk_delivery):
    """SDV-GN-07 — asked for W2, only W2's deliveries count, not the earlier W0 and W1 ones.
    Rules: `generate_delivery_number` R2"""
    mk_delivery(
        "X0",
        workspace_id=g.W0.id,
        sales_order_id=g.SO0.id,
        delivery_number=f"DEL-2026-{g.TAG}a",
    )
    mk_delivery("A", delivery_number=f"DEL-2026-{g.TAG}b")
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number=f"DEL-2026-{g.TAG}c",
    )

    result = dao.generate_delivery_number(db, workspace_id=g.W2.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"


# [claude] SDV-GN-08
def test_sdv_gn_08__every_status_counts(db, g, mk_delivery):
    """SDV-GN-08 — delivered, cancelled and other statuses all count.
    Rules: `generate_delivery_number` R2"""
    mk_delivery("A", delivery_number="DEL-2026-001", delivery_status="delivered")
    mk_delivery("B", delivery_number="DEL-2026-002", delivery_status="cancelled")
    mk_delivery("C", delivery_number="DEL-2026-003", delivery_status="on hold")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-004"


# [claude] SDV-GN-09
def test_sdv_gn_09__other_years_do_not_count(db, g, mk_delivery):
    """SDV-GN-09 — deliveries of 2025 and 2027 do not count for 2026.
    Rules: `generate_delivery_number` R3"""
    mk_delivery("A", delivery_number="DEL-2025-001")
    mk_delivery("B", delivery_number="DEL-2025-002")
    mk_delivery("C", delivery_number="DEL-2027-001")
    mk_delivery("D", delivery_number="DEL-2026-001")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"


# [claude] SDV-GN-10
def test_sdv_gn_10__year_202_printed_as_given(db, g, mk_delivery):
    """SDV-GN-10 — year 202 is printed as given and does not count DEL-2026 numbers.
    Rules: `generate_delivery_number` R3, Inputs (`year` not padded)"""
    mk_delivery("A", delivery_number="DEL-2026-001")
    mk_delivery("B", delivery_number="DEL-2026-002")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=202)

    # Then 1
    assert result == "DEL-202-001"


# [claude] SDV-GN-11
def test_sdv_gn_11__every_suffix_counts(db, g, mk_delivery):
    """SDV-GN-11 — every suffix counts: letters, a gap and a changed number.
    Rules: `generate_delivery_number` R4"""
    mk_delivery("A", delivery_number="DEL-2026-abc")
    mk_delivery("B", delivery_number="DEL-2026-009")
    mk_delivery("C", delivery_number="DEL-2026-")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-004"


# [claude] SDV-GN-12
def test_sdv_gn_12__only_exact_prefix_counts(db, g, mk_delivery):
    """SDV-GN-12 — only numbers that start with the exact prefix count.
    Rules: `generate_delivery_number` R1, R3, R3a"""
    mk_delivery("A", delivery_number="XDEL-2026-001")
    mk_delivery("B", delivery_number="del-2026-002")
    mk_delivery("C", delivery_number=" DEL-2026-003")
    mk_delivery("D", delivery_number="DEL-20260-004")
    mk_delivery("E", delivery_number="DEL_2026_005")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-001"


# [claude] SDV-GN-13
def test_sdv_gn_13__writes_nothing(db, g, mk_delivery):
    """SDV-GN-13 — writes nothing: a pending delivery is not counted and stays pending, an unflushed edit stays unflushed.
    Rules: `generate_delivery_number` R5, Side effects"""
    b = mk_delivery("B", delivery_number="DEL-2026-001")
    b.notes = "Edited"
    p = SalesDelivery(
        workspace_id=g.W1.id,
        sales_order_id=g.SO2.id,
        delivery_number="DEL-2026-002",
        delivery_status="planned",
        created_by=g.U1.id,
    )
    db.add(p)
    before = counts(db, g)

    with StatementRecorder(db) as rec:
        result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"
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
    assert counts(db, g) == before


# [claude] SDV-GN-14
def test_sdv_gn_14__takes_no_row_lock(db, g, mk_delivery):
    """SDV-GN-14 — takes no row lock.
    Rules: `generate_delivery_number` R5"""
    mk_delivery("A", delivery_number="DEL-2026-001")

    with StatementRecorder(db) as rec:
        result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"
    # Then 2
    assert "FOR UPDATE" not in rec.sql


# [claude] SDV-GN-15
def test_sdv_gn_15__positional_arguments_raise_type_error(db, g):
    """SDV-GN-15 — positional arguments raise TypeError.
    Rules: `generate_delivery_number` R6"""
    before = counts(db, g)

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.generate_delivery_number(db, g.W1.id, 2026)
    assert isinstance(exc.value, TypeError)
    # Then 2
    assert counts(db, g) == before


# [claude] SDV-GN-16
def test_sdv_gn_16__prefix_is_case_sensitive(db, g, mk_delivery):
    """SDV-GN-16 — the prefix is case-sensitive: lower- and mixed-case numbers do not count, the upper-case one does.
    Rules: `generate_delivery_number` R3a"""
    mk_delivery("A", delivery_number="del-2026-001")
    mk_delivery("B", delivery_number="DEL-2026-001")
    mk_delivery("C", delivery_number="Del-2026-002")
    mk_delivery("D", delivery_number="del-2026-002")

    result = dao.generate_delivery_number(db, workspace_id=g.W1.id, year=2026)

    # Then 1
    assert result == "DEL-2026-002"


# --------------------------------------------------------------------------- #
# DAOSalesDelivery.create_with_user
# --------------------------------------------------------------------------- #


# [claude] SDV-CW-01
def test_sdv_cw_01__stores_every_field(db, g):
    """SDV-CW-01 — a delivery is stored with every field of the schema, its workspace, creator and number.
    Rules: `create_with_user` R1, Returns"""
    with clock(*DEFAULT_CLOCK):
        result = dao.create_with_user(
            db,
            obj_in=SalesDeliveryCreate(
                sales_order_id=g.SO2.id,
                delivery_method_id=g.DM1.id,
                scheduled_date=DA,
                tracking_number="TRK-1",
                notes="Fragile",
            ),
            workspace_id=g.W1.id,
            user_id=g.U2.id,
        )

    # Then 1
    assert isinstance(result, SalesDelivery)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result.id)
    assert row.workspace_id == g.W1.id
    assert row.sales_order_id == g.SO2.id
    assert row.delivery_method_id == g.DM1.id
    assert row.created_by == g.U2.id
    # Then 4
    assert row.scheduled_date == DA
    assert row.tracking_number == "TRK-1"
    assert row.notes == "Fragile"
    # Then 5
    assert row.delivery_number == "DEL-2026-001"
    assert row.delivery_status == "planned"
    # Then 6
    assert count(db, g.W1) == 1


# [claude] SDV-CW-02
def test_sdv_cw_02__unset_fields_null_defaults_set(db, g):
    """SDV-CW-02 — unset fields are NULL and the defaults are set.
    Rules: `create_with_user` R1, R4"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.scheduled_date is None
    assert row.tracking_number is None
    assert row.notes is None
    # Then 3
    assert row.actual_delivery_date is None
    assert row.completion_code is None
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 4
    assert row.delivery_status == "planned"
    # Then 5
    assert row.created_at is not None


# [claude] SDV-CW-03
def test_sdv_cw_03__third_gets_003(db, g, mk_delivery):
    """SDV-CW-03 — after two deliveries of the year the third gets DEL-2026-003.
    Rules: `create_with_user` R1"""
    mk_delivery("A", delivery_number="DEL-2026-001")
    mk_delivery("B", delivery_number="DEL-2026-002")

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).delivery_number == "DEL-2026-003"
    # Then 3
    assert count(db, g.W1) == 3


# [claude] SDV-CW-04
def test_sdv_cw_04__w0_and_w2_do_not_move_w1(db, g, mk_delivery):
    """SDV-CW-04 — deliveries of W0 and W2 do not move W1's number.
    Rules: `create_with_user` R1, R5"""
    mk_delivery(
        "X0",
        workspace_id=g.W0.id,
        sales_order_id=g.SO0.id,
        delivery_number=f"DEL-2026-{g.TAG}a",
    )
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number=f"DEL-2026-{g.TAG}c",
    )

    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.delivery_number == "DEL-2026-001"
    assert row.workspace_id == g.W1.id


# [claude] SDV-CW-05
@pytest.mark.xfail(
    strict=True,
    reason="BUG-726: the delivery number is unique across all workspaces, not per workspace",
)
def test_sdv_cw_05__w2_number_does_not_stop_w1(db, g, mk_delivery):
    """SDV-CW-05 — W2 holding DEL-2026-001 does not stop W1's first delivery.
    Rules: `create_with_user` R5 [BUG-726]"""
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number="DEL-2026-001",
    )

    # Then 1 (the call raises IntegrityError today, so the failure lands here)
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.delivery_number == "DEL-2026-001"
    assert row.workspace_id == g.W1.id
    # Then 3
    assert count(db, g.W1) == 1


# [claude] SDV-CW-06
@pytest.mark.xfail(
    strict=True,
    reason="BUG-726: the delivery number is unique across all workspaces, not per workspace",
)
def test_sdv_cw_06__w0_number_does_not_stop_w1(db, g, mk_delivery):
    """SDV-CW-06 — W0 holding DEL-2026-001 does not stop W1's first delivery.
    Rules: `create_with_user` R5 [BUG-726]"""
    mk_delivery(
        "X0",
        workspace_id=g.W0.id,
        sales_order_id=g.SO0.id,
        delivery_number="DEL-2026-001",
    )

    # Then 1 (the call raises IntegrityError today, so the failure lands here)
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g)
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.delivery_number == "DEL-2026-001"
    assert row.workspace_id == g.W1.id
    # Then 3
    assert count(db, g.W1) == 1


# [claude] SDV-CW-07
def test_sdv_cw_07__number_used_in_same_workspace_fails(db, g, mk_delivery):
    """SDV-CW-07 — a computed number already used in the same workspace fails at flush and saves nothing.
    Rules: `create_with_user` R5, Errors (number already used)"""
    mk_delivery("A", delivery_number="DEL-2026-001")
    mk_delivery("B", delivery_number="DEL-2026-002")
    mk_delivery("C", delivery_number="DEL-2026-004")

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                create_w1(db, g)
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert count(db, g.W1) == 3


# [claude] SDV-CW-08
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the delivery number takes the server's local year, not the UTC year",
)
def test_sdv_cw_08__utc_year_when_local_next_year(db, g):
    """SDV-CW-08 — the year is UTC's when the local clock is already in the next year.
    Rules: `create_with_user` R2 [BUG-2440]"""
    with clock(datetime(2027, 1, 1, 5, 0), datetime(2026, 12, 31, 23, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).delivery_number == "DEL-2026-001"


# [claude] SDV-CW-09
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2440: the delivery number takes the server's local year, not the UTC year",
)
def test_sdv_cw_09__utc_year_when_local_old_year(db, g):
    """SDV-CW-09 — the year is UTC's when the local clock is still in the old year.
    Rules: `create_with_user` R2 [BUG-2440]"""
    with clock(datetime(2026, 12, 31, 20, 0), datetime(2027, 1, 1, 1, 0)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).delivery_number == "DEL-2027-001"


# [claude] SDV-CW-10
def test_sdv_cw_10__year_comes_from_the_clock(db, g, mk_delivery):
    """SDV-CW-10 — the year comes from the clock: both clocks in 2031 give DEL-2031-001.
    Rules: `create_with_user` R1, R2"""
    mk_delivery("A", delivery_number="DEL-2026-001")

    with clock(datetime(2031, 1, 1, 0, 30), datetime(2031, 1, 1, 0, 30)):
        result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).delivery_number == "DEL-2031-001"


# [claude] SDV-CW-11
def test_sdv_cw_11__created_at_is_current_utc_naive(db, g):
    """SDV-CW-11 — created_at is the current time in UTC, naive (no clock).
    Rules: `create_with_user` R4"""
    before = utc_now()

    result = create_w1(db, g)
    after = utc_now()

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.created_at.tzinfo is None
    # Then 3
    assert before <= row.created_at <= after


# [claude] SDV-CW-12
def test_sdv_cw_12__created_at_utc_under_dhaka(db, g):
    """SDV-CW-12 — created_at stays UTC when the database runs in Asia/Dhaka (no clock).
    Rules: `create_with_user` R4"""
    dhaka(db)
    before = utc_now()

    result = create_w1(db, g)
    after = utc_now()

    # Then 1
    assert result.id is not None
    # Then 2
    assert before <= reread(db, result.id).created_at <= after


# [claude] SDV-CW-13, CW-14
@pytest.mark.xfail(
    strict=True,
    reason="BUG-722: create_with_user stores the schema's delivery_status instead of always 'planned'",
)
@pytest.mark.parametrize(
    "status",
    [
        pytest.param("shipped", id="SDV-CW-13"),
        pytest.param("delivered", id="SDV-CW-14"),
    ],
)
def test_sdv_cw_13_14__schema_status_still_makes_planned(db, g, status):
    """SDV-CW-13 / CW-14 — a schema carrying status "shipped" / "delivered" still makes a planned delivery.
    Rules: `create_with_user` R3 [BUG-722]"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, delivery_status=status)

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).delivery_status == "planned"


# [claude] SDV-CW-15
def test_sdv_cw_15__other_workspace_order_stored_as_given(db, g):
    """SDV-CW-15 — an order of another workspace is stored as given.
    Rules: `create_with_user` R6"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, sales_order_id=g.SO9.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.sales_order_id == g.SO9.id
    assert row.workspace_id == g.W1.id


# [claude] SDV-CW-16
def test_sdv_cw_16__other_workspace_method_stored_as_given(db, g):
    """SDV-CW-16 — another workspace's delivery method is stored as given.
    Rules: `create_with_user` R6"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, delivery_method_id=g.DM9.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.delivery_method_id == g.DM9.id
    assert row.workspace_id == g.W1.id


# [claude] SDV-CW-17, CW-18, CW-19
@pytest.mark.parametrize(
    "missing",
    [
        pytest.param("sales_order_id", id="SDV-CW-17"),
        pytest.param("delivery_method_id", id="SDV-CW-18"),
        pytest.param("user_id", id="SDV-CW-19"),
    ],
)
def test_sdv_cw_17_18_19__unknown_link_fails_with_23503(db, g, missing):
    """SDV-CW-17 / 18 / 19 — an unknown order / delivery method / user fails at flush with 23503 and saves nothing.
    Rules: `create_with_user` R6, Errors"""
    fields = {"sales_order_id": g.SO2.id, "delivery_method_id": g.DM1.id}
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
                    obj_in=SalesDeliveryCreate(**fields),
                    workspace_id=g.W1.id,
                    user_id=user_id,
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert counts(db, g) == before


# [claude] SDV-CW-20
def test_sdv_cw_20__text_stored_exactly(db, g):
    """SDV-CW-20 — text values are stored exactly as the schema gives them.
    Rules: `create_with_user` R1"""
    with clock(*DEFAULT_CLOCK):
        result = create_w1(db, g, tracking_number=" Trk_1 ", notes=" Leave_At Gate")

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.tracking_number == " Trk_1 "
    assert row.notes == " Leave_At Gate"


# [claude] SDV-CW-21
def test_sdv_cw_21__flushed_not_committed(db, g):
    """SDV-CW-21 — flushed, not committed: a rollback removes the delivery.
    Rules: `create_with_user` Returns, Side effects (flush only)"""
    sp = db.begin_nested()
    with clock(*DEFAULT_CLOCK):
        with patch.object(db, "commit", wraps=db.commit) as cm:
            result = create_w1(db, g)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, g.W1) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert count(db, g.W1) == 0


# [claude] SDV-CW-22
def test_sdv_cw_22__positional_arguments_raise_type_error(db, g):
    """SDV-CW-22 — positional arguments raise TypeError and save nothing.
    Rules: `create_with_user` R7"""
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(TypeError) as exc:
            dao.create_with_user(
                db,
                SalesDeliveryCreate(
                    sales_order_id=g.SO2.id, delivery_method_id=g.DM1.id
                ),
                g.W1.id,
                g.U1.id,
            )
    assert isinstance(exc.value, TypeError)
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert counts(db, g) == before


# [claude] SDV-CW-23
def test_sdv_cw_23__dict_obj_in_raises_attribute_error(db, g):
    """SDV-CW-23 — a plain dict as obj_in raises AttributeError and saves nothing.
    Rules: `create_with_user` R7"""
    before = counts(db, g)

    # Then 1
    with clock(*DEFAULT_CLOCK):
        with pytest.raises(AttributeError) as exc:
            dao.create_with_user(
                db,
                obj_in={"sales_order_id": g.SO2.id, "delivery_method_id": g.DM1.id},
                workspace_id=g.W1.id,
                user_id=g.U1.id,
            )
    assert isinstance(exc.value, AttributeError)
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert counts(db, g) == before


# [claude] SDV-CW-24
def test_sdv_cw_24__w2_counts_only_its_own(db, g, mk_delivery):
    """SDV-CW-24 — created in W2, the number counts W2's deliveries only.
    Rules: `create_with_user` R1, R5"""
    mk_delivery("A", delivery_number=f"DEL-2026-{g.TAG}a")
    mk_delivery("B", delivery_number=f"DEL-2026-{g.TAG}b")
    mk_delivery(
        "X2",
        workspace_id=g.W2.id,
        sales_order_id=g.SO9.id,
        delivery_number="DEL-2026-001",
    )

    with clock(*DEFAULT_CLOCK):
        result = dao.create_with_user(
            db,
            obj_in=SalesDeliveryCreate(
                sales_order_id=g.SO9.id, delivery_method_id=g.DM9.id
            ),
            workspace_id=g.W2.id,
            user_id=g.U1.id,
        )

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.delivery_number == "DEL-2026-002"
    assert row.workspace_id == g.W2.id
    # Then 3
    assert count(db, g.W2) == 2


# [claude] SDV-CW-25
def test_sdv_cw_25__unknown_workspace_fails_with_23503(db, g):
    """SDV-CW-25 — an unknown workspace fails at flush with 23503 and saves nothing.
    Rules: `create_with_user` R6a, Errors (unknown workspace)"""
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM sales_deliveries WHERE delivery_number = 'DEL-2091-001'"
            )
        )
        == 0
    )  # precondition
    before = counts(db, g)

    # Then 1
    with clock(datetime(2091, 6, 1, 12, 0), datetime(2091, 6, 1, 12, 0)):
        with pytest.raises(IntegrityError) as exc:
            with db.begin_nested():
                dao.create_with_user(
                    db,
                    obj_in=SalesDeliveryCreate(
                        sales_order_id=g.SO2.id, delivery_method_id=g.DM1.id
                    ),
                    workspace_id=MISSING,
                    user_id=g.U1.id,
                )
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert (
        db.scalar(
            text("SELECT count(*) FROM sales_deliveries WHERE workspace_id = :w"),
            {"w": MISSING},
        )
        == 0
    )
    # Then 4
    assert counts(db, g) == before


# --------------------------------------------------------------------------- #
# DAOSalesDelivery.get_by_sales_order
# --------------------------------------------------------------------------- #


# [claude] SDV-SO-01
def test_sdv_so_01__only_the_orders_deliveries(db, g, mk_delivery):
    """SDV-SO-01 — only the order's deliveries, not those of a lower or a higher order id.
    Rules: `get_by_sales_order` R1"""
    mk_delivery("A", sales_order_id=g.SO1.id)
    b = mk_delivery("B")
    mk_delivery("C", sales_order_id=g.SO3.id)
    d = mk_delivery("D")

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {b.id, d.id}
    # Then 3
    assert len(result) == 2


# [claude] SDV-SO-02
def test_sdv_so_02__every_status_returned(db, g, mk_delivery):
    """SDV-SO-02 — deliveries in every status are returned.
    Rules: `get_by_sales_order` R1"""
    a = mk_delivery("A")
    b = mk_delivery("B", delivery_status="delivered")
    c = mk_delivery("C", delivery_status="cancelled")
    d = mk_delivery("D", delivery_status="on hold")

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert idset(result) == {a.id, b.id, c.id, d.id}


# [claude] SDV-SO-03
def test_sdv_so_03__w0_and_w2_rows_not_returned_for_w1(db, g, mk_delivery):
    """SDV-SO-03 — rows of W0 and W2 on the same order are not returned for W1.
    Rules: `get_by_sales_order` R2"""
    mk_delivery("X2", workspace_id=g.W2.id)
    b = mk_delivery("B")
    mk_delivery("X0", workspace_id=g.W0.id)

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] SDV-SO-04
def test_sdv_so_04__w2_row_returned_only_for_w2(db, g, mk_delivery):
    """SDV-SO-04 — a row recorded under W2 on W1's order is returned only for W2.
    Rules: `get_by_sales_order` R2"""
    mk_delivery("X0", workspace_id=g.W0.id)
    mk_delivery("B")
    x2 = mk_delivery("X2", workspace_id=g.W2.id)

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W2.id)

    # Then 1
    assert ids(result) == [x2.id]


# [claude] SDV-SO-05, SO-06, SO-07
@pytest.mark.parametrize(
    "order",
    [
        pytest.param("MISSING", id="SDV-SO-05"),
        pytest.param("0", id="SDV-SO-06"),
        pytest.param("SO3", id="SDV-SO-07"),
    ],
)
def test_sdv_so_05_06_07__no_deliveries_empty_list(db, g, mk_delivery, order):
    """SDV-SO-05 / 06 / 07 — an unknown order, order id 0, an order without deliveries: an empty list.
    Rules: `get_by_sales_order` R2 (SO-07: R1, Returns)"""
    mk_delivery("A")
    order_id = {"MISSING": MISSING, "0": 0, "SO3": g.SO3.id}[order]

    result = dao.get_by_sales_order(db, sales_order_id=order_id, workspace_id=g.W1.id)

    # Then 1
    assert result == []


# [claude] SDV-SO-08
def test_sdv_so_08__no_cap(db, g):
    """SDV-SO-08 — no cap: 102 deliveries give 102 rows.
    Rules: `get_by_sales_order` R4"""
    add_many(db, g, [f"DV-{g.TAG}-{k}" for k in range(102)])

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 102
    # Then 2
    assert len(idset(result)) == 102


# [claude] SDV-SO-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2442: an order's deliveries are listed with no ORDER BY (physical row order)",
)
def test_sdv_so_09__id_ascending_after_lowest_updated(db, g, mk_delivery):
    """SDV-SO-09 — id ascending, also after the lowest id was updated.
    Rules: `get_by_sales_order` R3 [BUG-2442]"""
    a = mk_delivery("A")
    b = mk_delivery("B")
    c = mk_delivery("C")
    expected = [a.id, b.id, c.id]
    seqscan(db)
    bump(db, a)
    db.expire_all()

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == expected


# [claude] SDV-SO-10
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2442: an order's deliveries are listed with no ORDER BY (physical row order)",
)
def test_sdv_so_10__id_decides_over_other_columns(db, g, mk_delivery):
    """SDV-SO-10 — id decides, when number, date, creator and status would each sort otherwise.
    Rules: `get_by_sales_order` R3 [BUG-2442]"""
    a = mk_delivery(
        "A",
        delivery_number=f"DV-{g.TAG}-3",
        scheduled_date=DC,
        created_by=g.U3.id,
        delivery_status="planned",
    )
    b = mk_delivery(
        "B",
        delivery_number=f"DV-{g.TAG}-2",
        scheduled_date=DB,
        created_by=g.U2.id,
        delivery_status="delivered",
    )
    c = mk_delivery(
        "C",
        delivery_number=f"DV-{g.TAG}-1",
        scheduled_date=DA,
        created_by=g.U1.id,
        delivery_status="cancelled",
    )
    expected = [a.id, b.id, c.id]
    seqscan(db)
    bump(db, a)
    db.expire_all()

    result = dao.get_by_sales_order(db, sales_order_id=g.SO2.id, workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == expected


# [claude] SDV-SO-11
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2442: an order's deliveries are listed with no ORDER BY (physical row order)",
)
def test_sdv_so_11__orders_by_id_ascending(db, g, mk_delivery):
    """SDV-SO-11 — the query orders by sales_deliveries.id ascending.
    Rules: `get_by_sales_order` R3 [BUG-2442]"""
    a = mk_delivery("A")

    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=g.SO2.id, workspace_id=g.W1.id
        )

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "sales_deliveries.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0


# [claude] SDV-SO-12
def test_sdv_so_12__writes_nothing(db, g, mk_delivery):
    """SDV-SO-12 — writes nothing: a pending delivery stays pending and is not returned, an unflushed edit stays unflushed.
    Rules: `get_by_sales_order` Side effects"""
    a = mk_delivery("A")
    b = mk_delivery("B")
    b.notes = "Edited"
    p = SalesDelivery(
        workspace_id=g.W1.id,
        sales_order_id=g.SO2.id,
        delivery_number=f"DV-{g.TAG}-P",
        delivery_status="planned",
        created_by=g.U1.id,
    )
    db.add(p)
    before = counts(db, g)

    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=g.SO2.id, workspace_id=g.W1.id
        )

    # Then 1
    assert idset(result) == {a.id, b.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert b.notes == "Edited"
    # Then 7
    assert rec.written == []
    # Then 8
    assert counts(db, g) == before


# [claude] SDV-SO-13
def test_sdv_so_13__does_not_join_orders(db, g, mk_delivery):
    """SDV-SO-13 — the query does not join the order table.
    Rules: `get_by_sales_order` R1"""
    a = mk_delivery("A")

    with StatementRecorder(db) as rec:
        result = dao.get_by_sales_order(
            db, sales_order_id=g.SO2.id, workspace_id=g.W1.id
        )

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "sales_orders" not in rec.sql


# [claude] SDV-SO-14
def test_sdv_so_14__positional_arguments_raise_type_error(db, g, mk_delivery):
    """SDV-SO-14 — positional arguments raise TypeError.
    Rules: `get_by_sales_order` R5"""
    mk_delivery("A")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_sales_order(db, g.SO2.id, g.W1.id)
    assert isinstance(exc.value, TypeError)


# --------------------------------------------------------------------------- #
# DAOSalesDelivery.get_by_status
# --------------------------------------------------------------------------- #


# [claude] SDV-ST-01
def test_sdv_st_01__planned_keeps_planned_only(db, g, mk_delivery):
    """SDV-ST-01 — "planned" keeps the planned deliveries only.
    Rules: `get_by_status` R1"""
    mk_delivery("A", delivery_status="delivered")
    b = mk_delivery("B")
    mk_delivery("C", delivery_status="cancelled")
    d = mk_delivery("D")

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {b.id, d.id}
    # Then 3
    assert len(result) == 2


# [claude] SDV-ST-02, ST-03, ST-04, ST-06, ST-07, ST-08
@pytest.mark.parametrize(
    "asked",
    [
        pytest.param("Planned", id="SDV-ST-02"),
        pytest.param("planned ", id="SDV-ST-03"),
        pytest.param(" planned", id="SDV-ST-04"),
        pytest.param("lann", id="SDV-ST-06"),
        pytest.param("plann_d", id="SDV-ST-07"),
        pytest.param("%", id="SDV-ST-08"),
    ],
)
def test_sdv_st_02_to_08__near_miss_status_keeps_none(db, g, mk_delivery, asked):
    """SDV-ST-02 / 03 / 04 / 06 / 07 / 08 — capitals, a trailing or leading space, part of the status,
    `_` and `%` (no wildcards): none kept.
    Rules: `get_by_status` R1"""
    mk_delivery("A")

    result = dao.get_by_status(db, delivery_status=asked, workspace_id=g.W1.id)

    # Then 1
    assert result == []


# [claude] SDV-ST-05
def test_sdv_st_05__stored_look_alikes_not_kept(db, g, mk_delivery):
    """SDV-ST-05 — stored look-alikes are not kept by "planned".
    Rules: `get_by_status` R1"""
    mk_delivery("A", delivery_status="Planned")
    mk_delivery("B", delivery_status=" planned")
    mk_delivery("C", delivery_status="planned_x")
    d = mk_delivery("D")

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [d.id]


# [claude] SDV-ST-09
def test_sdv_st_09__empty_status_keeps_none(db, g, mk_delivery):
    """SDV-ST-09 — an empty status keeps none.
    Rules: `get_by_status` R1"""
    mk_delivery("A")
    mk_delivery("B", delivery_status="delivered")

    result = dao.get_by_status(db, delivery_status="", workspace_id=g.W1.id)

    # Then 1
    assert result == []


# [claude] SDV-ST-10
def test_sdv_st_10__any_text_accepted(db, g, mk_delivery):
    """SDV-ST-10 — any text is accepted: "shipped" keeps the shipped delivery.
    Rules: `get_by_status` R1"""
    mk_delivery("A")
    b = mk_delivery("B", delivery_status="shipped")

    result = dao.get_by_status(db, delivery_status="shipped", workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [b.id]


def _st_isolation_rows(g, mk_delivery):
    """The Given rows of SDV-ST-11 and ST-12."""
    mk_delivery("X0", workspace_id=g.W0.id, sales_order_id=g.SO0.id)
    b = mk_delivery("B")
    x2 = mk_delivery("X2", workspace_id=g.W2.id, sales_order_id=g.SO9.id)
    return b, x2


# [claude] SDV-ST-11
def test_sdv_st_11__w0_and_w2_not_returned_for_w1(db, g, mk_delivery):
    """SDV-ST-11 — planned deliveries of W0 and W2 are not returned for W1.
    Rules: `get_by_status` R2"""
    b, _x2 = _st_isolation_rows(g, mk_delivery)

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] SDV-ST-12
def test_sdv_st_12__w2_gets_only_its_own(db, g, mk_delivery):
    """SDV-ST-12 — asked for W2, only W2's planned delivery is returned.
    Rules: `get_by_status` R2"""
    _b, x2 = _st_isolation_rows(g, mk_delivery)

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W2.id)

    # Then 1
    assert ids(result) == [x2.id]


# [claude] SDV-ST-13
def test_sdv_st_13__default_limit_gives_100(db, g):
    """SDV-ST-13 — with the defaults 102 matching deliveries give 100.
    Rules: `get_by_status` R4 (default limit)"""
    add_many(db, g, [f"DV-{g.TAG}-{k}" for k in range(102)])
    all_ids = set(
        db.scalars(
            select(SalesDelivery.id).where(SalesDelivery.workspace_id == g.W1.id)
        )
    )

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len(idset(result)) == 100
    # Then 3
    assert idset(result) <= all_ids


# [claude] SDV-ST-14
def test_sdv_st_14__limit_1000_gives_all(db, g):
    """SDV-ST-14 — limit=1000 gives all 102.
    Rules: `get_by_status` R4"""
    add_many(db, g, [f"DV-{g.TAG}-{k}" for k in range(102)])

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, limit=1000
    )

    # Then 1
    assert len(result) == 102
    # Then 2
    assert len(idset(result)) == 102


# [claude] SDV-ST-15
def test_sdv_st_15__limit_0_empty(db, g, mk_delivery):
    """SDV-ST-15 — limit=0 returns an empty list.
    Rules: `get_by_status` R4"""
    mk_delivery("A")

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, limit=0
    )

    # Then 1
    assert result == []


# [claude] SDV-ST-16, ST-17
@pytest.mark.parametrize(
    ("paging", "pgcode"),
    [
        pytest.param({"limit": -1}, "2201W", id="SDV-ST-16"),
        pytest.param({"skip": -1}, "2201X", id="SDV-ST-17"),
    ],
)
def test_sdv_st_16_17__negative_paging_raises_data_error(
    db, g, mk_delivery, paging, pgcode
):
    """SDV-ST-16 / ST-17 — a negative limit raises DataError 2201W; a negative skip 2201X.
    Rules: `get_by_status` R4, Errors"""
    mk_delivery("A")
    before = counts(db, g)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_status(
                db, delivery_status="planned", workspace_id=g.W1.id, **paging
            )
    assert exc.value.orig.pgcode == pgcode
    # Then 2
    assert counts(db, g) == before


# [claude] SDV-ST-18
def test_sdv_st_18__skip_past_end_empty(db, g, mk_delivery):
    """SDV-ST-18 — skip past the end returns an empty list.
    Rules: `get_by_status` R4"""
    mk_delivery("A")
    mk_delivery("B")

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, skip=2
    )

    # Then 1
    assert result == []


# [claude] SDV-ST-19, ST-20
@pytest.mark.parametrize(
    ("paging", "size"),
    [
        pytest.param({"skip": 2, "limit": 2}, 2, id="SDV-ST-19"),
        pytest.param({"skip": 4}, 1, id="SDV-ST-20"),
    ],
)
def test_sdv_st_19_20__page_of_five(db, g, mk_delivery, paging, size):
    """SDV-ST-19 / ST-20 — skip=2, limit=2 of five gives two rows; skip=4 of five gives one row.
    Rules: `get_by_status` R4"""
    five = {mk_delivery(name).id for name in ("A", "B", "C", "D", "E")}

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, **paging
    )

    # Then 1
    assert len(result) == size
    # Then 2
    assert idset(result) <= five


# [claude] SDV-ST-21
def test_sdv_st_21__status_filter_before_page(db, g, mk_delivery):
    """SDV-ST-21 — the status filter comes before the page: earlier delivered rows take no place.
    Rules: `get_by_status` R1, R4 (HR-5)"""
    mk_delivery("H1", delivery_status="delivered")
    mk_delivery("H2", delivery_status="cancelled")
    b = mk_delivery("B")
    c = mk_delivery("C")

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, limit=2
    )

    # Then 1
    assert idset(result) == {b.id, c.id}


# [claude] SDV-ST-22
def test_sdv_st_22__workspace_filter_before_page(db, g, mk_delivery):
    """SDV-ST-22 — the workspace filter comes before the page: earlier rows of W0 and W2 take no place.
    Rules: `get_by_status` R2, R4 (HR-5)"""
    mk_delivery("X0", workspace_id=g.W0.id, sales_order_id=g.SO0.id)
    mk_delivery("X2", workspace_id=g.W2.id, sales_order_id=g.SO9.id)
    b = mk_delivery("B")
    c = mk_delivery("C")

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, limit=2
    )

    # Then 1
    assert idset(result) == {b.id, c.id}


# [claude] SDV-ST-23
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2443: deliveries by status are listed with no ORDER BY (physical row order)",
)
def test_sdv_st_23__id_ascending_after_lowest_updated(db, g, mk_delivery):
    """SDV-ST-23 — id ascending, when the lowest id was updated and the other columns sort otherwise.
    Rules: `get_by_status` R3 [BUG-2443]"""
    a = mk_delivery(
        "A",
        delivery_number=f"DV-{g.TAG}-3",
        scheduled_date=DC,
        created_by=g.U3.id,
        sales_order_id=g.SO3.id,
    )
    b = mk_delivery(
        "B", delivery_number=f"DV-{g.TAG}-2", scheduled_date=DB, created_by=g.U2.id
    )
    c = mk_delivery(
        "C",
        delivery_number=f"DV-{g.TAG}-1",
        scheduled_date=DA,
        created_by=g.U1.id,
        sales_order_id=g.SO1.id,
    )
    expected = [a.id, b.id, c.id]
    seqscan(db)
    bump(db, a)
    db.expire_all()

    result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == expected


# [claude] SDV-ST-24
@pytest.mark.xfail(
    strict=False,
    reason="BUG-2443: deliveries by status are listed with no ORDER BY (physical row order)",
)
def test_sdv_st_24__skip_1_limit_1_gives_second_by_id(db, g, mk_delivery):
    """SDV-ST-24 — skip=1, limit=1 gives the second delivery by id.
    Rules: `get_by_status` R3, R4 [BUG-2443]"""
    a = mk_delivery("A")
    b = mk_delivery("B")
    mk_delivery("C")
    b_id = b.id
    seqscan(db)
    bump(db, a)
    db.expire_all()

    result = dao.get_by_status(
        db, delivery_status="planned", workspace_id=g.W1.id, skip=1, limit=1
    )

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b_id]


# [claude] SDV-ST-25
@pytest.mark.xfail(
    strict=True,
    reason="BUG-2443: deliveries by status are listed with no ORDER BY (physical row order)",
)
def test_sdv_st_25__orders_by_id_ascending_before_limit(db, g, mk_delivery):
    """SDV-ST-25 — the query orders by sales_deliveries.id ascending, before LIMIT.
    Rules: `get_by_status` R3 [BUG-2443]"""
    a = mk_delivery("A")

    with StatementRecorder(db) as rec:
        result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "sales_deliveries.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0
    # Then 6
    assert rec.sql.index("ORDER BY") < rec.sql.index("LIMIT")


# [claude] SDV-ST-26
def test_sdv_st_26__writes_nothing(db, g, mk_delivery):
    """SDV-ST-26 — writes nothing: a pending delivery stays pending and is not returned, an unflushed edit stays unflushed.
    Rules: `get_by_status` Side effects"""
    a = mk_delivery("A")
    b = mk_delivery("B")
    b.notes = "Edited"
    p = SalesDelivery(
        workspace_id=g.W1.id,
        sales_order_id=g.SO2.id,
        delivery_number=f"DV-{g.TAG}-P",
        delivery_status="planned",
        created_by=g.U1.id,
    )
    db.add(p)
    before = counts(db, g)

    with StatementRecorder(db) as rec:
        result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert idset(result) == {a.id, b.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert b.notes == "Edited"
    # Then 7
    assert rec.written == []
    # Then 8
    assert counts(db, g) == before


# [claude] SDV-ST-27
def test_sdv_st_27__does_not_join_orders(db, g, mk_delivery):
    """SDV-ST-27 — the query does not join the order table.
    Rules: `get_by_status` R1"""
    a = mk_delivery("A")

    with StatementRecorder(db) as rec:
        result = dao.get_by_status(db, delivery_status="planned", workspace_id=g.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "sales_orders" not in rec.sql


# [claude] SDV-ST-28
def test_sdv_st_28__positional_arguments_raise_type_error(db, g, mk_delivery):
    """SDV-ST-28 — positional arguments raise TypeError.
    Rules: `get_by_status` R5"""
    mk_delivery("A")

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.get_by_status(db, "planned", g.W1.id)
    assert isinstance(exc.value, TypeError)
