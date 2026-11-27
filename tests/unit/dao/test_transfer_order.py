"""Unit tests for app/dao/transfer_order.py.

Implements tests/unit/dao/transfer_order.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). The only patches are
the Conventions' clock(L, U) / utconly(U) in the `NN` cards; nothing else is
mocked.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()` and naive datetimes)
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.transfer_order import transfer_order_dao, transfer_order_item_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao"
dao = transfer_order_dao
idao = transfer_order_item_dao

# Convention "MISSING"
MISSING = 999999999


def GN(s):
    """Convention "GN(s)" = `f"{s}-{os.getpid()}"`."""
    return f"{s}-{os.getpid()}"


def XID(k):
    """Convention "XID(k)" = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`."""
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def TS(h):
    """Convention "TS(h)" = 2026-03-04 00:00 + h hours (naive UTC)."""
    return datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)


# Convention "DONE", "NOW31"
DONE = datetime(2026, 3, 20, 9, 0)
NOW31 = datetime(2031, 6, 1, 12, 0)

_F_KEYS = (
    "date_from",
    "date_to",
    "status_ids",
    "factory_id",
    "source_location_type",
    "destination_location_type",
    "search",
)


def F(**over):
    """Convention "F(...)": every hub filter keyword None, the given keys replaced."""
    unknown = set(over) - set(_F_KEYS)
    assert not unknown, unknown
    return {**dict.fromkeys(_F_KEYS), **over}


# --------------------------------------------------------------------------- #
# Conventions -> Externals: clock(L, U), utconly(U)
# --------------------------------------------------------------------------- #


@contextmanager
def clock(local, utc):
    """Convention "clock(L, U)": stdlib `datetime.datetime.now()` returns L;
    `app.dao.transfer_order.utcnow` (create=True) and `app.utils.time.utcnow` return U."""

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return local

    with (
        patch("datetime.datetime", FakeDT),
        patch("app.dao.transfer_order.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


@contextmanager
def utconly(utc):
    """Convention "utconly(U)": only the two `utcnow` patches."""
    with (
        patch("app.dao.transfer_order.utcnow", create=True, return_value=utc),
        patch("app.utils.time.utcnow", return_value=utc),
    ):
        yield


# --------------------------------------------------------------------------- #
# Conventions -> standing rows
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def s(db):
    """Convention "Standing rows" 1-6, in their order, each flushed."""
    r = SimpleNamespace()
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2 = make_profile(db), make_profile(db)

    def st(ws, name):
        return _add(db, Status(workspace_id=ws.id, name=name, comment="stage"))

    r.S0 = st(r.W0, "Draft")
    r.S1 = st(r.W1, "Draft")
    r.SP = st(r.W1, "Planned")
    r.SC = st(r.W1, "Completed")
    r.S2 = st(r.W2, "Draft")

    def fac(ws, name, abbr):
        return _add(db, Factory(workspace_id=ws.id, name=name, abbreviation=abbr))

    r.F0 = fac(r.W0, "Zulu Depot", "ZD")
    r.F1 = fac(r.W1, "Alpha Works", "AW")
    r.FB = fac(r.W1, "Bravo Yard", "BY")
    r.F2 = fac(r.W2, "Yankee Store", "YS")

    def mac(k, ws, f, name):
        return _add(
            db, Machine(id=XID(k), workspace_id=ws.id, factory_id=f.id, name=name)
        )

    r.M1 = mac(1, r.W1, r.F1, "Press Kilo")
    r.MB = mac(2, r.W1, r.FB, "Lathe Lima")
    r.M0 = mac(3, r.W0, r.F0, "Drill Oscar")
    r.M2 = mac(4, r.W2, r.F2, "Saw Romeo")

    def prj(ws, f, name):
        return _add(
            db,
            Project(workspace_id=ws.id, factory_id=f.id, name=name, description="Main"),
        )

    r.PJ1 = prj(r.W1, r.F1, "Tower One")
    r.PJB = prj(r.W1, r.FB, "Tower Two")
    r.PJ0 = prj(r.W0, r.F0, "Tower Zero")
    r.PJ2 = prj(r.W2, r.F2, "Tower Nine")

    def comp(k, ws, p, name):
        return _add(
            db,
            ProjectComponent(id=XID(k), workspace_id=ws.id, project_id=p.id, name=name),
        )

    r.C1 = comp(5, r.W1, r.PJ1, "Span Delta")
    r.CB = comp(6, r.W1, r.PJB, "Beam Echo")
    r.C0 = comp(7, r.W0, r.PJ0, "Deck Quebec")
    r.C2 = comp(8, r.W2, r.PJ2, "Pier Sierra")

    def itm(ws):
        return _add(
            db,
            Item(workspace_id=ws.id, name="Bolt", name_normalized="bolt", unit="pcs"),
        )

    r.I0, r.I1, r.I2 = itm(r.W0), itm(r.W1), itm(r.W2)
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def _ws_rows(s, ws):
    """(W, F, M, S) of "order n" / "of W0" / "of W2"."""
    return {
        0: (s.W0, s.F0, s.M0, s.S0),
        1: (s.W1, s.F1, s.M1, s.S1),
        2: (s.W2, s.F2, s.M2, s.S2),
    }[ws]


def _item_of(s, workspace_id):
    return {s.W0.id: s.I0, s.W1.id: s.I1, s.W2.id: s.I2}[workspace_id]


def order(
    db,
    s,
    n,
    *,
    ws=1,
    completed=False,
    draft=False,
    planned=False,
    flush=True,
    add=True,
    **cols,
):
    """Convention "order n" (`ws=0` / `ws=2` = "of W0" / "of W2"); `cols` = the
    columns after "but". `completed` / `draft` / `planned` are the conventions of
    those names (planned = line(T, 1) inserted right after the order).
    `flush=False`: added, not flushed. `add=False`: built, not added."""
    w, f, m, st = _ws_rows(s, ws)
    fields = {
        "workspace_id": w.id,
        "transfer_number": GN(f"TR-2026-{n:03d}"),
        "source_location_type": "storage",
        "source_location_id": f.id,
        "destination_location_type": "machine",
        "destination_location_id": m.id,
        "current_status_id": st.id,
        "created_by": s.U1.id,
        "created_at": TS(n),
    }
    if completed:
        fields["completed_at"] = DONE
    if draft:
        fields["destination_location_id"] = 0
    fields.update(cols)
    row = TransferOrder(**fields)
    if not add:
        return row
    db.add(row)
    if not flush:
        return row
    db.flush()
    if planned:
        line(db, s, row, 1)
    return row


def num(db, s, ws, number, *, created_at=None, add=True, flush=True, **cols):
    """Convention "num(W, s)": order 1 of W, but `transfer_number` exact (no GN)."""
    extra = {"created_at": created_at} if created_at is not None else {}
    return order(
        db, s, 1, ws=ws, add=add, flush=flush, transfer_number=number, **extra, **cols
    )


def line(db, s, t, k, *, flush=True, **cols):
    """Convention "line(T, k)"; `cols` = the columns after "but"."""
    fields = {
        "workspace_id": t.workspace_id,
        "transfer_order_id": t.id,
        "line_number": k,
        "item_id": _item_of(s, t.workspace_id).id,
        "quantity": Decimal("2.00"),
    }
    fields.update(cols)
    row = TransferOrderItem(**fields)
    db.add(row)
    if flush:
        db.flush()
    return row


def deleted(db, s, row):
    """Convention "deleted" (factory / machine / project), through the ORM, flushed."""
    row.is_deleted = True
    row.deleted_at = TS(0)
    row.deleted_by = s.U1.id
    if isinstance(row, Machine):
        row.is_active = False
    db.flush()


def numlock(db):
    """Convention "numlock"."""
    db.execute(text("SELECT pg_advisory_xact_lock(2650)"))


def seqscan(db):
    """Convention "seqscan"."""
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


def bump(db, x):
    """Convention "bump(X)"."""
    db.execute(
        text(
            "UPDATE transfer_orders SET transfer_number = transfer_number WHERE id = :i"
        ),
        {"i": x.id},
    )
    db.expire_all()


def bump_l(db, x):
    """Convention "bumpL(X)"."""
    db.execute(
        text("UPDATE transfer_order_items SET quantity = quantity WHERE id = :i"),
        {"i": x.id},
    )
    db.expire_all()


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


def hids(lst):
    return [e["id"] for e in lst]


def total(db):
    """Convention "total()"."""
    return db.scalar(select(func.count()).select_from(TransferOrder))


def loaded(x, attr):
    """Convention "loaded(X, a)"."""
    return attr not in sa_inspect(x).unloaded


class StatementRecorder:
    """Convention "Statement recorder": the SQL sent while the block runs.
    `table` = the card's table for `sql` / `order_part`."""

    def __init__(self, db, table="transfer_orders"):
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
        """The one SELECT from the card's table; fails loudly unless there is exactly one."""
        [statement] = [st for st in self.selects if f"FROM {self.table}" in st]
        return statement

    @property
    def order_part(self):
        return order_part_of(self.sql)


def order_part_of(sql):
    """Text after the first ORDER BY, before any LIMIT ("" if none)."""
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


def _x(bug, title, strict=True):
    return pytest.mark.xfail(strict=strict, reason=f"{bug}: {title}")


X2650 = _x(
    "BUG-2650", "Transfer numbers unique across all workspaces instead of per workspace"
)
X2651 = _x("BUG-2651", "Transfer numbering breaks after 999 in a year")
X2653 = _x("BUG-2653", "Transfer number's year comes from the server's local clock")
X2654 = _x("BUG-2654", "`%` and `_` in the transfer hub search match every order")
X2655 = _x(
    "BUG-2655",
    'Transfer hub "Recent" and pending samples list never-edited orders first',
)
X2656 = _x("BUG-2656", "Transfer orders with one timestamp come back in no fixed order")
X2656N = _x(
    "BUG-2656",
    "Transfer orders with one timestamp come back in no fixed order",
    strict=False,
)
X2657 = _x("BUG-2657", "Transfer lines with one line number have no order")
X2657N = _x(
    "BUG-2657", "Transfer lines with one line number have no order", strict=False
)
X2658 = _x(
    "BUG-2658",
    "Transfer hub's factory filter shows a transfer only under its destination's factory",
)
X2659 = _x(
    "BUG-2659", 'Transfer hub counts an order with a route but no lines as "Planned"'
)
X2660 = _x(
    "BUG-2660",
    "Transfer hub status filter compares the status stored at creation, which never changes",
)


def _list(db, ws, **kw):
    """The When of most HF / FF cards: `dao.list_for_hub(db, workspace_id=ws.id, **kw)`."""
    return dao.list_for_hub(db, workspace_id=ws.id, **kw)


# =========================================================================== #
# _apply_transfer_order_hub_filters (through list_for_hub / count_for_hub)
# =========================================================================== #


# [claude] TRO-HF-01
def test_tro_hf_01__only_w1_kept(db, s):
    """TRO-HF-01 — only W1's orders are kept, with orders of W0 and W2 on either side.
    Rules: _apply_transfer_order_hub_filters R1."""
    order(db, s, 9, ws=0)
    a = order(db, s, 1)
    b = order(db, s, 2)
    order(db, s, 8, ws=2)
    result = _list(db, s.W1, **F())
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-02
def test_tro_hf_02__w2_only(db, s):
    """TRO-HF-02 — asked for W2, only W2's order is kept, though W0 and W1 come earlier.
    Rules: _apply_transfer_order_hub_filters R1."""
    order(db, s, 9, ws=0)
    order(db, s, 1)
    x2 = order(db, s, 2, ws=2)
    result = _list(db, s.W2, **F())
    # Then 1
    assert ids(result) == [x2.id]


# [claude] TRO-HF-03
def test_tro_hf_03__w0_only(db, s):
    """TRO-HF-03 — asked for W0, only W0's order is kept, though W1 and W2 come later.
    Rules: _apply_transfer_order_hub_filters R1."""
    x0 = order(db, s, 1, ws=0)
    order(db, s, 9)
    order(db, s, 8, ws=2)
    result = _list(db, s.W0, **F())
    # Then 1
    assert ids(result) == [x0.id]


# [claude] TRO-HF-04
def test_tro_hf_04__date_from_midnight_inclusive(db, s):
    """TRO-HF-04 — date_from keeps 00:00:00 of that day and drops the last microsecond before it.
    Rules: _apply_transfer_order_hub_filters R2."""
    order(db, s, 1, created_at=datetime(2026, 3, 3, 23, 59, 59, 999999))
    b = order(db, s, 2, created_at=datetime(2026, 3, 4, 0, 0, 0))
    result = _list(db, s.W1, **F(date_from=date(2026, 3, 4)))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-05
def test_tro_hf_05__date_to_end_of_day_inclusive(db, s):
    """TRO-HF-05 — date_to keeps 23:59:59.999999 of that day and drops the next midnight.
    Rules: _apply_transfer_order_hub_filters R2."""
    a = order(db, s, 1, created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    order(db, s, 2, created_at=datetime(2026, 3, 5, 0, 0, 0))
    result = _list(db, s.W1, **F(date_to=date(2026, 3, 4)))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-06
def test_tro_hf_06__one_whole_day(db, s):
    """TRO-HF-06 — date_from equal to date_to covers that whole day only.
    Rules: _apply_transfer_order_hub_filters R2."""
    order(db, s, 1, created_at=datetime(2026, 3, 3, 23, 59, 59, 999999))
    b = order(db, s, 2, created_at=datetime(2026, 3, 4, 0, 0, 0))
    c = order(db, s, 3, created_at=datetime(2026, 3, 4, 12, 0, 0))
    e = order(db, s, 4, created_at=datetime(2026, 3, 4, 23, 59, 59, 999999))
    order(db, s, 5, created_at=datetime(2026, 3, 5, 0, 0, 0))
    result = _list(db, s.W1, **F(date_from=date(2026, 3, 4), date_to=date(2026, 3, 4)))
    # Then 1
    assert ids(result) == [e.id, c.id, b.id]


# [claude] TRO-HF-07
def test_tro_hf_07__from_after_to_keeps_nothing(db, s):
    """TRO-HF-07 — date_from after date_to keeps nothing and raises nothing.
    Rules: _apply_transfer_order_hub_filters R2."""
    order(db, s, 1, created_at=datetime(2026, 3, 4, 12, 0, 0))
    result = _list(db, s.W1, **F(date_from=date(2026, 3, 5), date_to=date(2026, 3, 4)))
    # Then 1
    assert result == []


# [claude] TRO-HF-08
def test_tro_hf_08__utc_days_under_dhaka(db, s):
    """TRO-HF-08 — days are UTC days, also when the session time zone is Dhaka.
    Rules: _apply_transfer_order_hub_filters R2."""
    dhaka(db)
    a = order(db, s, 1, created_at=datetime(2026, 3, 4, 20, 0, 0))
    order(db, s, 2, created_at=datetime(2026, 3, 5, 1, 0, 0))
    result = _list(db, s.W1, **F(date_from=date(2026, 3, 4), date_to=date(2026, 3, 4)))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-09
def test_tro_hf_09__status_ids_empty_is_no_filter(db, s):
    """TRO-HF-09 — status_ids [] is no status filter.
    Rules: _apply_transfer_order_hub_filters R3."""
    a = order(db, s, 1)
    b = order(db, s, 2, current_status_id=s.SP.id)
    result = _list(db, s.W1, **F(status_ids=[]))
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-10
def test_tro_hf_10__status_ids_none_is_no_filter(db, s):
    """TRO-HF-10 — status_ids None is no status filter.
    Rules: _apply_transfer_order_hub_filters R3."""
    a = order(db, s, 1, current_status_id=s.SC.id)
    b = order(db, s, 2, current_status_id=s.SP.id)
    result = _list(db, s.W1, **F(status_ids=None))
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-11
def test_tro_hf_11__source_type_filter(db, s):
    """TRO-HF-11 — source_location_type keeps only that source type.
    Rules: _apply_transfer_order_hub_filters R5."""
    order(db, s, 1, source_location_type="damaged")
    b = order(db, s, 2)
    order(db, s, 3, source_location_type="machine", source_location_id=s.MB.id)
    result = _list(db, s.W1, **F(source_location_type="storage"))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-12, HF-13, HF-14, HF-15
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("Storage", id="TRO-HF-12"),
        pytest.param("stor", id="TRO-HF-13"),
        pytest.param(" storage", id="TRO-HF-14"),
        pytest.param("st_rage", id="TRO-HF-15"),
    ],
)
def test_tro_hf_12_to_15__source_type_exact(db, s, value):
    """TRO-HF-12 … HF-15 — a capital letter, a part, a leading space, an underscore in the
    source type match nothing.
    Rules: _apply_transfer_order_hub_filters R5."""
    order(db, s, 1)
    result = _list(db, s.W1, **F(source_location_type=value))
    # Then 1
    assert result == []


# [claude] TRO-HF-16
def test_tro_hf_16__destination_type_filter(db, s):
    """TRO-HF-16 — destination_location_type keeps only that destination type.
    Rules: _apply_transfer_order_hub_filters R5."""
    a = order(
        db, s, 1, destination_location_type="project", destination_location_id=s.C1.id
    )
    order(db, s, 2)
    order(
        db, s, 3, destination_location_type="storage", destination_location_id=s.FB.id
    )
    result = _list(db, s.W1, **F(destination_location_type="project"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-17
def test_tro_hf_17__destination_type_capital(db, s):
    """TRO-HF-17 — destination_location_type with a capital letter matches nothing.
    Rules: _apply_transfer_order_hub_filters R5."""
    order(db, s, 1)
    result = _list(db, s.W1, **F(destination_location_type="Machine"))
    # Then 1
    assert result == []


# [claude] TRO-HF-18
def test_tro_hf_18__types_combine_with_and(db, s):
    """TRO-HF-18 — source and destination types together combine with AND.
    Rules: _apply_transfer_order_hub_filters R5, R11."""
    a = order(db, s, 1)
    order(
        db, s, 2, destination_location_type="project", destination_location_id=s.C1.id
    )
    order(db, s, 3, source_location_type="damaged")
    result = _list(
        db,
        s.W1,
        **F(source_location_type="storage", destination_location_type="machine"),
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-19
def test_tro_hf_19__empty_types_no_filter(db, s):
    """TRO-HF-19 — empty location types are no filter.
    Rules: _apply_transfer_order_hub_filters R5."""
    a = order(db, s, 1)
    b = order(
        db,
        s,
        2,
        source_location_type="damaged",
        destination_location_type="project",
        destination_location_id=s.C1.id,
    )
    result = _list(db, s.W1, **F(source_location_type="", destination_location_type=""))
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-20
def test_tro_hf_20__factory_zero_keeps_nothing(db, s):
    """TRO-HF-20 — factory_id 0 is a filter and keeps nothing.
    Rules: _apply_transfer_order_hub_filters R6."""
    order(db, s, 1)
    result = _list(db, s.W1, **F(factory_id=0))
    # Then 1
    assert result == []


# [claude] TRO-HF-21
def test_tro_hf_21__completed_dropped_by_default(db, s):
    """TRO-HF-21 — by default completed orders are dropped.
    Rules: _apply_transfer_order_hub_filters R7, list_for_hub R1."""
    a = order(db, s, 1)
    order(db, s, 2, completed=True)
    result = _list(db, s.W1, **F())  # exclude_complete not passed
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-22
def test_tro_hf_22__exclude_complete_false_keeps_completed(db, s):
    """TRO-HF-22 — exclude_complete=False keeps completed orders.
    Rules: _apply_transfer_order_hub_filters R7."""
    a = order(db, s, 1)
    b = order(db, s, 2, completed=True)
    result = _list(db, s.W1, exclude_complete=False, **F())
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-23, HF-24
@pytest.mark.parametrize(
    "term", [pytest.param("", id="TRO-HF-23"), pytest.param("   ", id="TRO-HF-24")]
)
def test_tro_hf_23_24__blank_search_no_filter(db, s, term):
    """TRO-HF-23, HF-24 — an empty or whitespace-only search is no search filter.
    Rules: _apply_transfer_order_hub_filters R8."""
    a = order(db, s, 1)
    b = order(db, s, 2, source_location_type="damaged", source_location_id=s.FB.id)
    result = _list(db, s.W1, **F(search=term))
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-HF-25
def test_tro_hf_25__number_middle_part(db, s):
    """TRO-HF-25 — the number is matched by a part in its middle.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(db, s, 7)
    order(db, s, 17)
    order(db, s, 70)
    result = _list(db, s.W1, **F(search="6-007"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-26
def test_tro_hf_26__lowercase_finds_number(db, s):
    """TRO-HF-26 — a lowercase search finds the uppercase number.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(db, s, 7)
    order(db, s, 17)
    result = _list(db, s.W1, **F(search="tr-2026-007"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-27
def test_tro_hf_27__uppercase_finds_machine(db, s):
    """TRO-HF-27 — an uppercase search finds a mixed-case machine name.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(db, s, 1)
    order(db, s, 2, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(search="KILO"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-28
def test_tro_hf_28__search_trimmed(db, s):
    """TRO-HF-28 — the search text is trimmed before matching.
    Rules: _apply_transfer_order_hub_filters R8."""
    a = order(db, s, 1)
    order(db, s, 2, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(search="  kilo  "))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-29
def test_tro_hf_29__source_type_text_searched(db, s):
    """TRO-HF-29 — the source type text is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(db, s, 1, source_location_type="damaged")
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="amag"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-30
def test_tro_hf_30__destination_type_text_searched(db, s):
    """TRO-HF-30 — the destination type text is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1)
    b = order(
        db, s, 2, destination_location_type="project", destination_location_id=s.C1.id
    )
    result = _list(db, s.W1, **F(search="roje"))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-31
def test_tro_hf_31__storage_source_factory_name(db, s):
    """TRO-HF-31 — the factory name at a storage source is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1)
    b = order(db, s, 2, source_location_id=s.FB.id)
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-32
def test_tro_hf_32__damaged_destination_factory_name(db, s):
    """TRO-HF-32 — the factory name at a damaged destination is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1)
    b = order(
        db, s, 2, destination_location_type="damaged", destination_location_id=s.FB.id
    )
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-33
def test_tro_hf_33__factory_id_under_machine_end(db, s):
    """TRO-HF-33 — a factory id under a machine end is not looked up as a factory.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1, destination_location_id=s.FB.id)
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert result == []


# [claude] TRO-HF-34
def test_tro_hf_34__machine_source_name(db, s):
    """TRO-HF-34 — the machine name at a machine source is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=s.MB.id,
        destination_location_type="storage",
        destination_location_id=s.F1.id,
    )
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="lima"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-35
def test_tro_hf_35__machine_id_under_storage_end(db, s):
    """TRO-HF-35 — a machine id under a storage end is not looked up as a machine.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1, source_location_id=s.MB.id)
    result = _list(db, s.W1, **F(search="lima"))
    # Then 1
    assert result == []


# [claude] TRO-HF-36
def test_tro_hf_36__component_destination_name(db, s):
    """TRO-HF-36 — the component name at a project destination is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(
        db, s, 1, destination_location_type="project", destination_location_id=s.CB.id
    )
    order(
        db, s, 2, destination_location_type="project", destination_location_id=s.C1.id
    )
    result = _list(db, s.W1, **F(search="echo"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-37
def test_tro_hf_37__unresolved_ids_not_found_by_name(db, s):
    """TRO-HF-37 — a known type whose id resolves to nothing is not found by a name.
    Rules: _apply_transfer_order_hub_filters R9."""
    order(db, s, 1, source_location_id=MISSING, destination_location_id=MISSING)
    b = order(db, s, 2)
    result = _list(db, s.W1, **F(search="alpha"))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-HF-38
def test_tro_hf_38__other_ws_factory_name_never_matches(db, s):
    """TRO-HF-38 — another workspace's factory name never matches (W2 factory id on a W1 order).
    Rules: _apply_transfer_order_hub_filters R9; HR-16."""
    order(
        db, s, 1, source_location_id=s.F2.id
    )  # invalid cross-workspace data, on purpose
    order(db, s, 2, ws=2)
    result = _list(db, s.W1, **F(search="yankee"))
    # Then 1
    assert result == []


# [claude] TRO-HF-39
def test_tro_hf_39__other_ws_machine_name_never_matches(db, s):
    """TRO-HF-39 — another workspace's machine name never matches (W0 machine id on a W1 order).
    Rules: _apply_transfer_order_hub_filters R9; HR-16."""
    order(
        db, s, 1, destination_location_id=s.M0.id
    )  # invalid cross-workspace data, on purpose
    result = _list(db, s.W1, **F(search="oscar"))
    # Then 1
    assert result == []


# [claude] TRO-HF-40
def test_tro_hf_40__other_ws_component_name_never_matches(db, s):
    """TRO-HF-40 — another workspace's component name never matches (W2 component on a W1 order).
    Rules: _apply_transfer_order_hub_filters R9; HR-16."""
    # invalid cross-workspace data, built on purpose
    order(
        db, s, 1, destination_location_type="project", destination_location_id=s.C2.id
    )
    result = _list(db, s.W1, **F(search="sierra"))
    # Then 1
    assert result == []


# [claude] TRO-HF-41
def test_tro_hf_41__deleted_factory_name_matches(db, s):
    """TRO-HF-41 — a soft-deleted factory's name still matches.
    Rules: _apply_transfer_order_hub_filters R9."""
    deleted(db, s, s.FB)
    a = order(db, s, 1, source_location_id=s.FB.id)
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-42
def test_tro_hf_42__deleted_machine_name_matches(db, s):
    """TRO-HF-42 — a soft-deleted machine's name still matches.
    Rules: _apply_transfer_order_hub_filters R9."""
    deleted(db, s, s.MB)
    a = order(db, s, 1, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(search="lima"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-43
def test_tro_hf_43__component_of_deleted_project_matches(db, s):
    """TRO-HF-43 — a component of a soft-deleted project still matches by its name.
    Rules: _apply_transfer_order_hub_filters R9."""
    deleted(db, s, s.PJB)
    a = order(
        db, s, 1, destination_location_type="project", destination_location_id=s.CB.id
    )
    result = _list(db, s.W1, **F(search="echo"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-44
def test_tro_hf_44__both_ends_listed_once(db, s):
    """TRO-HF-44 — an order matching at both ends is listed once.
    Rules: _apply_transfer_order_hub_filters R10."""
    a = order(
        db, s, 1, destination_location_type="storage", destination_location_id=s.F1.id
    )
    result = _list(db, s.W1, **F(search="alpha"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-45
def test_tro_hf_45__type_and_names_counted_once(db, s):
    """TRO-HF-45 — an order matching by type and by name at both ends is counted once.
    Rules: _apply_transfer_order_hub_filters R10, count_for_hub R1."""
    fa2 = _add(
        db, Factory(workspace_id=s.W1.id, name="Storage Annex", abbreviation="SA")
    )
    order(
        db,
        s,
        1,
        source_location_id=fa2.id,
        destination_location_type="storage",
        destination_location_id=fa2.id,
    )
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F(search="storage"))
    # Then 1
    assert result == 1


def _beta_works(db, s):
    """FU = Factory(W1, "Beta_Works", "BW")."""
    return _add(db, Factory(workspace_id=s.W1.id, name="Beta_Works", abbreviation="BW"))


# [claude] TRO-HF-46
@X2654
def test_tro_hf_46__underscore_matches_literal_only(db, s):
    """TRO-HF-46 — an underscore in the search matches only a literal underscore.
    Rules: _apply_transfer_order_hub_filters R10a [BUG-2654]."""
    fu = _beta_works(db, s)
    a = order(db, s, 1, source_location_id=fu.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="_"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-47
def test_tro_hf_47__underscore_still_finds_name(db, s):
    """TRO-HF-47 — an underscore search still finds the name that holds an underscore.
    Rules: _apply_transfer_order_hub_filters R9, R10a."""
    fu = _beta_works(db, s)
    a = order(db, s, 1, source_location_id=fu.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="_"))
    # Then 1
    assert a.id in idset(result)


# [claude] TRO-HF-48
@X2654
def test_tro_hf_48__percent_matches_literal_only(db, s):
    """TRO-HF-48 — a percent sign in the search matches only a literal percent sign.
    Rules: _apply_transfer_order_hub_filters R10a [BUG-2654]."""
    order(db, s, 1)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="%"))
    # Then 1
    assert result == []


def _beta_pair(db, s):
    """Given 1-4 of HF-49 / HF-50; returns A."""
    fu = _beta_works(db, s)
    fx = _add(db, Factory(workspace_id=s.W1.id, name="Betax Works", abbreviation="BX"))
    a = order(db, s, 1, source_location_id=fu.id)
    order(db, s, 2, source_location_id=fx.id)
    return a


# [claude] TRO-HF-49
@X2654
def test_tro_hf_49__beta_underscore_not_betax(db, s):
    """TRO-HF-49 — "beta_" finds Beta_Works and not Betax Works.
    Rules: _apply_transfer_order_hub_filters R10a [BUG-2654]."""
    a = _beta_pair(db, s)
    result = _list(db, s.W1, **F(search="beta_"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-50
def test_tro_hf_50__beta_underscore_finds_beta_works(db, s):
    """TRO-HF-50 — "beta_" still finds Beta_Works.
    Rules: _apply_transfer_order_hub_filters R9, R10a."""
    a = _beta_pair(db, s)
    result = _list(db, s.W1, **F(search="beta_"))
    # Then 1
    assert a.id in idset(result)


# [claude] TRO-HF-51
@X2654
def test_tro_hf_51__backslash_literal(db, s):
    """TRO-HF-51 — a backslash in the search matches a literal backslash.
    Rules: _apply_transfer_order_hub_filters R10a [BUG-2654]."""
    fs = _add(db, Factory(workspace_id=s.W1.id, name="Back\\Slash", abbreviation="BS"))
    a = order(db, s, 1, source_location_id=fs.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="\\"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-52
def test_tro_hf_52__search_type_date_and(db, s):
    """TRO-HF-52 — search, type and date filters combine with AND.
    Rules: _apply_transfer_order_hub_filters R11."""
    a = order(
        db, s, 1, source_location_id=s.FB.id, created_at=datetime(2026, 3, 4, 10, 0)
    )
    order(db, s, 2, source_location_id=s.FB.id, created_at=datetime(2026, 3, 6, 10, 0))
    order(
        db,
        s,
        3,
        source_location_type="damaged",
        source_location_id=s.FB.id,
        created_at=datetime(2026, 3, 4, 11, 0),
    )
    order(db, s, 4, created_at=datetime(2026, 3, 4, 12, 0))
    result = _list(
        db,
        s.W1,
        **F(search="bravo", source_location_type="storage", date_to=date(2026, 3, 4)),
    )
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-53
def test_tro_hf_53__only_workspace_id(db, s):
    """TRO-HF-53 — called with only workspace_id, no filter applies and completed orders are dropped.
    Rules: _apply_transfer_order_hub_filters R0, R7."""
    order(db, s, 1, ws=0)
    a = order(
        db,
        s,
        2,
        source_location_type="damaged",
        destination_location_type="warehouse",
        destination_location_id=0,
        current_status_id=s.SC.id,
    )
    order(db, s, 3, completed=True)
    c = order(db, s, 4, created_at=datetime(2020, 1, 1, 0, 0))
    order(db, s, 5, ws=2)
    result = dao.list_for_hub(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id, c.id]


# [claude] TRO-HF-54
def test_tro_hf_54__kpi_only_workspace_id(db, s):
    """TRO-HF-54 — the KPI totals called with only workspace_id drop completed orders.
    Rules: _apply_transfer_order_hub_filters R0, R7; aggregate_hub_stats R1."""
    order(db, s, 1, ws=0)
    order(db, s, 2)
    order(db, s, 3, completed=True)
    order(db, s, 4, ws=2)
    result = dao.aggregate_hub_stats(db, workspace_id=s.W1.id)
    # Then 1
    assert result == (1, 1, 0)


# [claude] TRO-HF-55, HF-56
@pytest.mark.parametrize(
    "term",
    [pytest.param("avo ya", id="TRO-HF-55"), pytest.param("yard", id="TRO-HF-56")],
)
def test_tro_hf_55_56__factory_name_middle_and_end(db, s, term):
    """TRO-HF-55, HF-56 — a factory name is matched by a part in its middle / by its end.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(db, s, 1, source_location_id=s.FB.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search=term))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-57, HF-58
@pytest.mark.parametrize(
    "term",
    [pytest.param("lathe", id="TRO-HF-57"), pytest.param("the li", id="TRO-HF-58")],
)
def test_tro_hf_57_58__machine_name_start_and_middle(db, s, term):
    """TRO-HF-57, HF-58 — a machine name is matched by its start / by a part in its middle.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(db, s, 1, destination_location_id=s.MB.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search=term))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-59, HF-60
@pytest.mark.parametrize(
    "term",
    [pytest.param("beam", id="TRO-HF-59"), pytest.param("am ec", id="TRO-HF-60")],
)
def test_tro_hf_59_60__component_name_start_and_middle(db, s, term):
    """TRO-HF-59, HF-60 — a component name is matched by its start / by a part in its middle.
    Rules: _apply_transfer_order_hub_filters R8, R9."""
    a = order(
        db, s, 1, destination_location_type="project", destination_location_id=s.CB.id
    )
    order(
        db, s, 2, destination_location_type="project", destination_location_id=s.C1.id
    )
    result = _list(db, s.W1, **F(search=term))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-61
def test_tro_hf_61__component_at_project_source(db, s):
    """TRO-HF-61 — the component name at a project source is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(db, s, 1, source_location_type="project", source_location_id=s.CB.id)
    order(
        db, s, 2, destination_location_type="project", destination_location_id=s.C1.id
    )
    result = _list(db, s.W1, **F(search="echo"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-62
def test_tro_hf_62__factory_at_damaged_source(db, s):
    """TRO-HF-62 — the factory name at a damaged source is searched.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(db, s, 1, source_location_type="damaged", source_location_id=s.FB.id)
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-HF-63
def test_tro_hf_63__factory_at_storage_destination(db, s):
    """TRO-HF-63 — the factory name at a storage destination is searched, with no storage source.
    Rules: _apply_transfer_order_hub_filters R9."""
    a = order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=s.M1.id,
        destination_location_type="storage",
        destination_location_id=s.FB.id,
    )
    order(db, s, 2)
    result = _list(db, s.W1, **F(search="bravo"))
    # Then 1
    assert ids(result) == [a.id]


# =========================================================================== #
# _apply_transfer_factory_filter (through list_for_hub)
# =========================================================================== #


# [claude] TRO-FF-01
def test_tro_ff_01__storage_destination_of_f1(db, s):
    """TRO-FF-01 — a storage destination of F1 is kept for F1.
    Rules: _apply_transfer_factory_filter R1, R1a."""
    a = order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="storage",
        destination_location_id=s.F1.id,
    )
    order(
        db,
        s,
        2,
        source_location_id=s.FB.id,
        destination_location_type="storage",
        destination_location_id=s.FB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-02
def test_tro_ff_02__damaged_destination_of_f1(db, s):
    """TRO-FF-02 — a damaged destination of F1 is kept for F1.
    Rules: _apply_transfer_factory_filter R1."""
    a = order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="damaged",
        destination_location_id=s.F1.id,
    )
    order(
        db,
        s,
        2,
        source_location_id=s.FB.id,
        destination_location_type="damaged",
        destination_location_id=s.FB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-03
def test_tro_ff_03__machine_destination_in_f1(db, s):
    """TRO-FF-03 — a machine destination in F1 is kept for F1, one in FB is not.
    Rules: _apply_transfer_factory_filter R1."""
    a = order(db, s, 1, source_location_id=s.FB.id)
    order(db, s, 2, source_location_id=s.FB.id, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-04
def test_tro_ff_04__project_destination_in_f1(db, s):
    """TRO-FF-04 — a project destination whose project is in F1 is kept for F1, one in FB is not.
    Rules: _apply_transfer_factory_filter R1."""
    a = order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="project",
        destination_location_id=s.C1.id,
    )
    order(
        db,
        s,
        2,
        source_location_id=s.FB.id,
        destination_location_type="project",
        destination_location_id=s.CB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-05
def test_tro_ff_05__unknown_destination_source_decides(db, s):
    """TRO-FF-05 — with an unknown destination type the source decides (machine of F1 → "warehouse").
    Rules: _apply_transfer_factory_filter R1, R1a."""
    a = order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=s.M1.id,
        destination_location_type="warehouse",
        destination_location_id=s.F1.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-06
def test_tro_ff_06__empty_destination_source_decides(db, s):
    """TRO-FF-06 — with an empty destination type the source decides (storage F1 → "").
    Rules: _apply_transfer_factory_filter R1, R1a."""
    a = order(db, s, 1, destination_location_type="", destination_location_id=s.M1.id)
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-07
def test_tro_ff_07__inside_f1_listed_once(db, s):
    """TRO-FF-07 — a transfer between two locations of F1 appears once.
    Rules: _apply_transfer_factory_filter R3."""
    a = order(db, s, 1)
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-08
def test_tro_ff_08__inside_f1_counted_once(db, s):
    """TRO-FF-08 — a transfer between two locations of F1 is counted once.
    Rules: _apply_transfer_factory_filter R3, count_for_hub R1."""
    order(
        db, s, 1, destination_location_type="project", destination_location_id=s.C1.id
    )
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F(factory_id=s.F1.id))
    # Then 1
    assert result == 1


# [claude] TRO-FF-09
def test_tro_ff_09__unknown_types_no_factory(db, s):
    """TRO-FF-09 — unknown types at both ends belong to no factory.
    Rules: _apply_transfer_factory_filter R2."""
    order(
        db,
        s,
        1,
        source_location_type="warehouse",
        source_location_id=s.F1.id,
        destination_location_type="warehouse",
        destination_location_id=s.F1.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert result == []


# [claude] TRO-FF-10
def test_tro_ff_10__unresolved_ids_no_factory(db, s):
    """TRO-FF-10 — known types whose ids resolve to nothing belong to no factory.
    Rules: _apply_transfer_factory_filter R2."""
    order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=MISSING,
        destination_location_type="project",
        destination_location_id=MISSING,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert result == []


# [claude] TRO-FF-11
def test_tro_ff_11__machine_id_under_storage(db, s):
    """TRO-FF-11 — a machine id under a storage destination is not read as a machine.
    Rules: _apply_transfer_factory_filter R1."""
    order(
        db,
        s,
        1,
        source_location_type="warehouse",
        destination_location_type="storage",
        destination_location_id=s.M1.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert result == []


# [claude] TRO-FF-12
def test_tro_ff_12__other_ws_machine_never_belongs(db, s):
    """TRO-FF-12 — another workspace's machine never makes an end belong (W2 machine on a W1 order).
    Rules: _apply_transfer_factory_filter R1; HR-16."""
    # invalid cross-workspace data, built on purpose
    order(db, s, 1, source_location_type="warehouse", destination_location_id=s.M2.id)
    result = _list(db, s.W1, **F(factory_id=s.F2.id))
    # Then 1
    assert result == []


# [claude] TRO-FF-13
def test_tro_ff_13__other_ws_component_never_belongs(db, s):
    """TRO-FF-13 — another workspace's component never makes an end belong (W0 component on W1).
    Rules: _apply_transfer_factory_filter R1; HR-16."""
    # invalid cross-workspace data, built on purpose
    order(
        db,
        s,
        1,
        source_location_type="warehouse",
        destination_location_type="project",
        destination_location_id=s.C0.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F0.id))
    # Then 1
    assert result == []


# [claude] TRO-FF-14
def test_tro_ff_14__deleted_machine_still_belongs(db, s):
    """TRO-FF-14 — a soft-deleted machine of F1 still makes the destination belong.
    Rules: _apply_transfer_factory_filter R1."""
    deleted(db, s, s.M1)
    a = order(db, s, 1, source_location_id=s.FB.id)
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-15
def test_tro_ff_15__component_of_deleted_project_belongs(db, s):
    """TRO-FF-15 — a component of a soft-deleted project of F1 still makes the destination belong.
    Rules: _apply_transfer_factory_filter R1."""
    deleted(db, s, s.PJ1)
    a = order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="project",
        destination_location_id=s.C1.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-16
def test_tro_ff_16__leaving_f1_kept_for_fb(db, s):
    """TRO-FF-16 — a transfer leaving F1's storage for FB's machine is still kept for FB.
    Rules: _apply_transfer_factory_filter R1, R1a."""
    a = order(db, s, 1, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(factory_id=s.FB.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-17
@X2658
def test_tro_ff_17__leaving_f1_kept_for_f1(db, s):
    """TRO-FF-17 — a transfer leaving F1's storage for FB's machine is kept for F1.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658]."""
    a = order(db, s, 1, destination_location_id=s.MB.id)
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-18
@X2658
def test_tro_ff_18__f1_damaged_to_fb_storage(db, s):
    """TRO-FF-18 — a transfer from F1's damaged stock to FB's storage is kept for F1.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658]."""
    a = order(
        db,
        s,
        1,
        source_location_type="damaged",
        destination_location_type="storage",
        destination_location_id=s.FB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-19
@X2658
def test_tro_ff_19__f1_machine_to_fb_component(db, s):
    """TRO-FF-19 — a transfer from F1's machine to FB's component is kept for F1.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658]."""
    a = order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=s.M1.id,
        destination_location_type="project",
        destination_location_id=s.CB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-20
@X2658
def test_tro_ff_20__f1_component_to_fb_storage(db, s):
    """TRO-FF-20 — a transfer from F1's component to FB's storage is kept for F1.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658]."""
    a = order(
        db,
        s,
        1,
        source_location_type="project",
        source_location_id=s.C1.id,
        destination_location_type="storage",
        destination_location_id=s.FB.id,
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-21
@X2658
def test_tro_ff_21__unresolved_destination_does_not_hide_source(db, s):
    """TRO-FF-21 — a known destination type resolving to nothing does not hide F1's source.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658]."""
    a = order(
        db, s, 1, destination_location_type="storage", destination_location_id=MISSING
    )
    result = _list(db, s.W1, **F(factory_id=s.F1.id))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-FF-22
@X2658
def test_tro_ff_22__count_includes_leaving_f1(db, s):
    """TRO-FF-22 — the count for F1 includes the transfer leaving F1.
    Rules: _apply_transfer_factory_filter R1a [BUG-2658], count_for_hub R1."""
    order(db, s, 1)
    order(db, s, 2, destination_location_id=s.MB.id)
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F(factory_id=s.F1.id))
    # Then 1
    assert result == 2


# =========================================================================== #
# TransferOrderDAO.list_for_hub
# =========================================================================== #


# [claude] TRO-LH-01
def test_tro_lh_01__newest_created_first(db, s):
    """TRO-LH-01 — newest created first, with an older order holding the higher id.
    Rules: list_for_hub R1, R2, Returns."""
    a = order(db, s, 2)
    b = order(db, s, 3)
    c = order(db, s, 1)
    result = _list(db, s.W1, **F())
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], TransferOrder)
    # Then 3
    assert ids(result) == [b.id, a.id, c.id]


# [claude] TRO-LH-02
def test_tro_lh_02__tie_broken_by_id_desc(db, s):
    """TRO-LH-02 — equal created_at is broken by id descending, after the lowest id was rewritten.
    Rules: list_for_hub R2."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5))
    b = order(db, s, 2, created_at=TS(5))
    c = order(db, s, 3, created_at=TS(5))
    e = order(db, s, 4, created_at=TS(1))
    aid, bid, cid, eid = a.id, b.id, c.id, e.id
    bump(db, a)
    result = _list(db, s.W1, **F())
    # Then 1
    assert ids(result) == [cid, bid, aid, eid]


# [claude] TRO-LH-03
def test_tro_lh_03__order_by_created_then_id(db, s):
    """TRO-LH-03 — the list query orders by created_at DESC, then id DESC.
    Rules: list_for_hub R2."""
    order(db, s, 1)
    db.expunge_all()
    with StatementRecorder(db) as rec:
        dao.list_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert "created_at DESC" in rec.order_part
    # Then 2
    assert rec.order_part.rstrip().endswith("transfer_orders.id DESC")
    # Then 3
    assert rec.order_part.index("created_at DESC") < rec.order_part.index(
        "transfer_orders.id DESC"
    )


# [claude] TRO-LH-04
def test_tro_lh_04__skip_and_limit(db, s):
    """TRO-LH-04 — skip and limit cut the sorted list.
    Rules: list_for_hub R3."""
    o = {n: order(db, s, n) for n in range(1, 6)}
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=1, limit=2, **F())
    # Then 1
    assert ids(result) == [o[4].id, o[3].id]


# [claude] TRO-LH-05
def test_tro_lh_05__default_page(db, s):
    """TRO-LH-05 — the default page is skip 0 and 50 rows.
    Rules: list_for_hub R3."""
    o = {n: order(db, s, n, flush=False) for n in range(1, 52)}
    db.flush()
    result = _list(db, s.W1, **F())
    # Then 1
    assert len(result) == 50
    # Then 2
    assert result[0].id == o[51].id
    # Then 3
    assert o[1].id not in idset(result)


# [claude] TRO-LH-06
def test_tro_lh_06__skip_past_end(db, s):
    """TRO-LH-06 — skip past the end returns [].
    Rules: list_for_hub R3."""
    order(db, s, 1)
    order(db, s, 2)
    order(db, s, 3)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=3, limit=10, **F())
    # Then 1
    assert result == []


# [claude] TRO-LH-07
def test_tro_lh_07__limit_1000(db, s):
    """TRO-LH-07 — limit=1000 returns every row.
    Rules: list_for_hub R3."""
    a = order(db, s, 1)
    b = order(db, s, 2)
    c = order(db, s, 3)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=0, limit=1000, **F())
    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] TRO-LH-08
def test_tro_lh_08__filters_before_paging(db, s):
    """TRO-LH-08 — filters apply before paging: hidden newer rows do not take a page slot.
    Rules: list_for_hub R3, _apply_transfer_order_hub_filters R11."""
    order(db, s, 1)
    b = order(db, s, 2)
    order(db, s, 3)
    order(db, s, 9, completed=True)
    order(db, s, 8, ws=2)
    result = dao.list_for_hub(db, workspace_id=s.W1.id, skip=1, limit=1, **F())
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-LH-09
def test_tro_lh_09__current_status_loaded(db, s):
    """TRO-LH-09 — current_status comes loaded.
    Rules: list_for_hub Returns."""
    order(db, s, 1, current_status_id=s.SP.id)
    w1 = s.W1.id
    db.expunge_all()
    result = dao.list_for_hub(db, workspace_id=w1, **F())
    # Then 1
    assert loaded(result[0], "current_status")
    # Then 2
    assert result[0].current_status.name == "Planned"


# [claude] TRO-LH-10
def test_tro_lh_10__unknown_keyword_type_error(db, s):
    """TRO-LH-10 — an unknown filter keyword raises TypeError.
    Rules: list_for_hub R4, Errors."""
    order(db, s, 1)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.list_for_hub(db, workspace_id=s.W1.id, colour="red", **F())
    # Then 2
    assert total(db) == before


# [claude] TRO-LH-11
def test_tro_lh_11__writes_nothing_no_lock(db, s):
    """TRO-LH-11 — writes nothing and takes no lock: a pending order stays pending, an
    unflushed edit stays unflushed.
    Rules: list_for_hub Side effects; HR-10 note."""
    e = order(db, s, 1)
    e.destination_location_id = s.MB.id
    p = order(db, s, 5, flush=False)
    with StatementRecorder(db) as rec:
        result = dao.list_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [e.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "FOR UPDATE" not in rec.sql


# [claude] TRO-LH-12
def test_tro_lh_12__empty_workspace(db, s):
    """TRO-LH-12 — a workspace with no orders gives [].
    Rules: list_for_hub R1."""
    order(db, s, 1, ws=0)
    order(db, s, 2, ws=2)
    result = _list(db, s.W1, **F())
    # Then 1
    assert result == []


# =========================================================================== #
# TransferOrderDAO.count_for_hub
# =========================================================================== #


# [claude] TRO-CH-01
def test_tro_ch_01__counts_w1_open_orders(db, s):
    """TRO-CH-01 — counts W1's open orders only, as an int.
    Rules: count_for_hub R1."""
    order(db, s, 9, ws=0)
    order(db, s, 1)
    order(db, s, 2)
    order(db, s, 3, completed=True)
    order(db, s, 8, ws=2)
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert type(result) is int
    # Then 2
    assert result == 2


# [claude] TRO-CH-02
def test_tro_ch_02__nothing_gives_zero(db, s):
    """TRO-CH-02 — nothing matching gives 0, not None.
    Rules: count_for_hub R1."""
    order(db, s, 1, ws=0)
    order(db, s, 2, ws=2)
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


# [claude] TRO-CH-03
def test_tro_ch_03__ignores_page_size(db, s):
    """TRO-CH-03 — the count ignores the list's page size.
    Rules: count_for_hub R1."""
    for n in range(1, 56):
        order(db, s, n, flush=False)
    db.flush()
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 55


# [claude] TRO-CH-04
def test_tro_ch_04__exclude_complete_false(db, s):
    """TRO-CH-04 — exclude_complete=False counts completed orders too.
    Rules: count_for_hub R1, _apply_transfer_order_hub_filters R7."""
    order(db, s, 1)
    order(db, s, 2)
    order(db, s, 3, completed=True)
    result = dao.count_for_hub(db, workspace_id=s.W1.id, exclude_complete=False, **F())
    # Then 1
    assert result == 3


# [claude] TRO-CH-05
def test_tro_ch_05__unknown_keyword_type_error(db, s):
    """TRO-CH-05 — an unknown filter keyword raises TypeError.
    Rules: count_for_hub Errors."""
    order(db, s, 1)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.count_for_hub(db, workspace_id=s.W1.id, colour="red", **F())
    # Then 2
    assert total(db) == before


# [claude] TRO-CH-06
def test_tro_ch_06__writes_nothing_no_lock(db, s):
    """TRO-CH-06 — writes nothing and takes no lock.
    Rules: count_for_hub Side effects; HR-10 note."""
    order(db, s, 1)
    with StatementRecorder(db) as rec:
        result = dao.count_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 1
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in st for st in rec.selects)


# =========================================================================== #
# TransferOrderDAO.list_recent_for_hub
# =========================================================================== #


# [claude] TRO-RC-01
def test_tro_rc_01__ten_most_recent_edits(db, s):
    """TRO-RC-01 — the default is the 10 most recently edited open orders of W1.
    Rules: list_recent_for_hub R1, R2."""
    hours = (53, 61, 57, 51, 62, 55, 59, 52, 60, 56, 54, 58)
    o = {n: order(db, s, n, updated_at=TS(h)) for n, h in enumerate(hours, start=1)}
    order(db, s, 13, completed=True, updated_at=TS(99))
    order(db, s, 14, ws=2, updated_at=TS(98))
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [
        o[5].id,
        o[2].id,
        o[9].id,
        o[7].id,
        o[12].id,
        o[3].id,
        o[10].id,
        o[6].id,
        o[11].id,
        o[1].id,
    ]


# [claude] TRO-RC-02
def test_tro_rc_02__limit_3(db, s):
    """TRO-RC-02 — limit=3 keeps the three most recent edits.
    Rules: list_recent_for_hub R1, R2."""
    order(db, s, 1, updated_at=TS(52))
    b = order(db, s, 2, updated_at=TS(55))
    order(db, s, 3, updated_at=TS(51))
    e = order(db, s, 4, updated_at=TS(54))
    g = order(db, s, 5, updated_at=TS(53))
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, limit=3, **F())
    # Then 1
    assert ids(result) == [b.id, e.id, g.id]


# [claude] TRO-RC-03
def test_tro_rc_03__limit_1000(db, s):
    """TRO-RC-03 — limit=1000 returns every row.
    Rules: list_recent_for_hub R1."""
    a = order(db, s, 1, updated_at=TS(52))
    b = order(db, s, 2, updated_at=TS(53))
    c = order(db, s, 3, updated_at=TS(51))
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, limit=1000, **F())
    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] TRO-RC-04
def test_tro_rc_04__current_status_loaded(db, s):
    """TRO-RC-04 — current_status comes loaded.
    Rules: list_recent_for_hub R1."""
    order(db, s, 1, current_status_id=s.SP.id)
    w1 = s.W1.id
    db.expunge_all()
    result = dao.list_recent_for_hub(db, workspace_id=w1, **F())
    # Then 1
    assert loaded(result[0], "current_status")
    # Then 2
    assert result[0].current_status.name == "Planned"


# [claude] TRO-RC-05
@X2655
def test_tro_rc_05__edited_before_never_edited(db, s):
    """TRO-RC-05 — an order edited later comes before an old never-edited one.
    Rules: list_recent_for_hub R2 [BUG-2655]."""
    a = order(db, s, 1)
    b = order(db, s, 2, updated_at=TS(30))
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-RC-06
@X2655
def test_tro_rc_06__never_edited_sorts_by_created(db, s):
    """TRO-RC-06 — a never-edited order sorts by its created_at among edited ones.
    Rules: list_recent_for_hub R2 [BUG-2655]."""
    c = order(db, s, 1, updated_at=TS(4))
    b = order(db, s, 2, updated_at=TS(8))
    a = order(db, s, 6)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [b.id, a.id, c.id]


# [claude] TRO-RC-07
@X2656N
def test_tro_rc_07__never_edited_ties_id_desc(db, s):
    """TRO-RC-07 — never-edited orders with equal created_at come by id descending.
    Rules: list_recent_for_hub R2 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5))
    b = order(db, s, 2, created_at=TS(5))
    c = order(db, s, 3, created_at=TS(5))
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [cid, bid, aid]


# [claude] TRO-RC-08
@X2656N
def test_tro_rc_08__same_edit_moment_id_desc(db, s):
    """TRO-RC-08 — orders edited at the same moment come by id descending.
    Rules: list_recent_for_hub R2 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5), updated_at=TS(9))
    b = order(db, s, 2, created_at=TS(5), updated_at=TS(9))
    c = order(db, s, 3, created_at=TS(5), updated_at=TS(9))
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [cid, bid, aid]


# [claude] TRO-RC-09
@X2656
def test_tro_rc_09__order_by_ends_with_id(db, s):
    """TRO-RC-09 — the recent query ends its ORDER BY with id DESC.
    Rules: list_recent_for_hub R2 [BUG-2656]."""
    order(db, s, 1)
    w1 = s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        dao.list_recent_for_hub(db, workspace_id=w1, **F())
    # Then 1
    assert rec.order_part.rstrip().endswith("transfer_orders.id DESC")


# [claude] TRO-RC-10
def test_tro_rc_10__unknown_keyword_type_error(db, s):
    """TRO-RC-10 — an unknown filter keyword raises TypeError.
    Rules: list_recent_for_hub Errors."""
    order(db, s, 1)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.list_recent_for_hub(db, workspace_id=s.W1.id, colour="red", **F())
    # Then 2
    assert total(db) == before


# [claude] TRO-RC-11
def test_tro_rc_11__writes_nothing_no_lock(db, s):
    """TRO-RC-11 — writes nothing and takes no lock.
    Rules: list_recent_for_hub Side effects; HR-10 note."""
    a = order(db, s, 1)
    with StatementRecorder(db) as rec:
        result = dao.list_recent_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in st for st in rec.selects)


# =========================================================================== #
# TransferOrderDAO.count_machine_involved_for_hub
# =========================================================================== #


# [claude] TRO-MI-01
def test_tro_mi_01__machine_at_either_end(db, s):
    """TRO-MI-01 — counts orders with a machine at either end, once each, in W1's open orders.
    Rules: count_machine_involved_for_hub R1."""
    order(db, s, 9, ws=0)
    order(
        db,
        s,
        1,
        source_location_type="machine",
        source_location_id=s.MB.id,
        destination_location_type="storage",
        destination_location_id=s.F1.id,
    )
    order(db, s, 2)
    order(
        db,
        s,
        3,
        source_location_type="machine",
        source_location_id=s.M1.id,
        destination_location_id=s.MB.id,
    )
    order(
        db, s, 4, destination_location_type="project", destination_location_id=s.C1.id
    )
    order(db, s, 5, completed=True)
    order(db, s, 8, ws=2)
    result = dao.count_machine_involved_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert type(result) is int
    # Then 2
    assert result == 3


# [claude] TRO-MI-02
def test_tro_mi_02__type_exact(db, s):
    """TRO-MI-02 — the type is compared exactly ("Machine", "machines" do not count).
    Rules: count_machine_involved_for_hub R1."""
    order(db, s, 1, destination_location_type="Machine")
    order(db, s, 2, destination_location_type="machines")
    result = dao.count_machine_involved_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 0


# [claude] TRO-MI-03
def test_tro_mi_03__machine_id_not_checked(db, s):
    """TRO-MI-03 — the machine id is not checked.
    Rules: count_machine_involved_for_hub R1."""
    order(db, s, 1, destination_location_id=MISSING)
    result = dao.count_machine_involved_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 1


# [claude] TRO-MI-04
def test_tro_mi_04__no_machine_zero(db, s):
    """TRO-MI-04 — no machine order gives 0.
    Rules: count_machine_involved_for_hub R1."""
    order(
        db, s, 1, destination_location_type="storage", destination_location_id=s.FB.id
    )
    result = dao.count_machine_involved_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 0
    # Then 2
    assert type(result) is int


# [claude] TRO-MI-05
def test_tro_mi_05__exclude_complete_false(db, s):
    """TRO-MI-05 — exclude_complete=False counts a completed machine order.
    Rules: count_machine_involved_for_hub R1."""
    order(db, s, 1, completed=True)
    order(db, s, 2)
    result = dao.count_machine_involved_for_hub(
        db, workspace_id=s.W1.id, exclude_complete=False, **F()
    )
    # Then 1
    assert result == 2


# [claude] TRO-MI-06
def test_tro_mi_06__search_narrows(db, s):
    """TRO-MI-06 — the search filter narrows the count.
    Rules: count_machine_involved_for_hub R1."""
    order(db, s, 7)
    order(db, s, 17)
    result = dao.count_machine_involved_for_hub(
        db, workspace_id=s.W1.id, **F(search="6-007")
    )
    # Then 1
    assert result == 1


# [claude] TRO-MI-07
def test_tro_mi_07__unknown_keyword_type_error(db, s):
    """TRO-MI-07 — an unknown filter keyword raises TypeError.
    Rules: count_machine_involved_for_hub Errors."""
    order(db, s, 1)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.count_machine_involved_for_hub(
            db, workspace_id=s.W1.id, colour="red", **F()
        )
    # Then 2
    assert total(db) == before


# [claude] TRO-MI-08
def test_tro_mi_08__writes_nothing_no_lock(db, s):
    """TRO-MI-08 — writes nothing and takes no lock.
    Rules: count_machine_involved_for_hub Side effects; HR-10 note."""
    order(db, s, 1)
    with StatementRecorder(db) as rec:
        result = dao.count_machine_involved_for_hub(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == 1
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in st for st in rec.selects)


# =========================================================================== #
# TransferOrderDAO.get_pending_highlights_for_hub
# =========================================================================== #


def _ph(db, s, **kw):
    """The When of the PH / OQ39 cards."""
    return dao.get_pending_highlights_for_hub(db, workspace_id=s.W1.id, **kw)


# [claude] TRO-PH-01
def test_tro_ph_01__keys_and_entries(db, s):
    """TRO-PH-01 — returns the five keys and entries of id, number, label and created_at.
    Rules: get_pending_highlights_for_hub Returns, R5."""
    p = order(db, s, 1, planned=True)
    r = order(db, s, 2, draft=True)
    result = _ph(db, s, **F())
    # Then 1
    assert set(result.keys()) == {
        "pending_planned_count",
        "pending_planned",
        "awaiting_setup_count",
        "awaiting_setup",
        "oldest_drafts",
    }
    # Then 2
    assert result["pending_planned_count"] == 1
    # Then 3
    assert result["awaiting_setup_count"] == 1
    # Then 4
    assert hids(result["pending_planned"]) == [p.id]
    # Then 5
    assert hids(result["awaiting_setup"]) == [r.id]
    # Then 6
    assert hids(result["oldest_drafts"]) == [r.id]
    # Then 7
    assert set(result["pending_planned"][0].keys()) == {
        "id",
        "order_number",
        "status_name",
        "created_at",
    }
    # Then 8
    assert result["pending_planned"][0]["order_number"] == GN("TR-2026-001")
    # Then 9
    assert result["pending_planned"][0]["created_at"] == TS(1)
    # Then 10
    assert result["oldest_drafts"][0]["order_number"] == GN("TR-2026-002")


# [claude] TRO-PH-02
def test_tro_ph_02__completed_left_out_always(db, s):
    """TRO-PH-02 — completed orders are left out even with exclude_complete=False.
    Rules: get_pending_highlights_for_hub R1."""
    a = order(db, s, 1, planned=True)
    order(db, s, 2, completed=True, planned=True)
    order(db, s, 3, draft=True, completed=True)
    result = _ph(db, s, exclude_complete=False, **F())
    # Then 1
    assert result["pending_planned_count"] == 1
    # Then 2
    assert hids(result["pending_planned"]) == [a.id]
    # Then 3
    assert result["awaiting_setup_count"] == 0
    # Then 4
    assert result["oldest_drafts"] == []


# [claude] TRO-PH-03
def test_tro_ph_03__filters_and_workspace_apply(db, s):
    """TRO-PH-03 — the hub filters and the workspace apply.
    Rules: get_pending_highlights_for_hub R1."""
    order(db, s, 9, ws=0, source_location_type="damaged", planned=True)
    a = order(db, s, 1, source_location_type="damaged", planned=True)
    order(db, s, 2, planned=True)
    order(db, s, 8, ws=2, source_location_type="damaged", draft=True)
    result = _ph(db, s, **F(source_location_type="damaged"))
    # Then 1
    assert result["pending_planned_count"] == 1
    # Then 2
    assert hids(result["pending_planned"]) == [a.id]
    # Then 3
    assert result["awaiting_setup_count"] == 0


# [claude] TRO-PH-04
def test_tro_ph_04__three_most_recent_planned(db, s):
    """TRO-PH-04 — pending_planned is the 3 most recently edited planned orders.
    Rules: get_pending_highlights_for_hub R4."""
    hours = (52, 55, 51, 54, 53)
    o = {
        n: order(db, s, n, updated_at=TS(h), planned=True)
        for n, h in enumerate(hours, start=1)
    }
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 5
    # Then 2
    assert hids(result["pending_planned"]) == [o[2].id, o[4].id, o[5].id]


# [claude] TRO-PH-05
def test_tro_ph_05__three_most_recent_drafts(db, s):
    """TRO-PH-05 — awaiting_setup is the 3 most recently edited drafts.
    Rules: get_pending_highlights_for_hub R4."""
    hours = (53, 51, 54, 52)
    o = {
        n: order(db, s, n, draft=True, updated_at=TS(h))
        for n, h in enumerate(hours, start=1)
    }
    result = _ph(db, s, **F())
    # Then 1
    assert result["awaiting_setup_count"] == 4
    # Then 2
    assert hids(result["awaiting_setup"]) == [o[3].id, o[1].id, o[4].id]


# [claude] TRO-PH-06
def test_tro_ph_06__five_oldest_drafts(db, s):
    """TRO-PH-06 — oldest_drafts is the 5 oldest drafts, oldest first, planned orders left out.
    Rules: get_pending_highlights_for_hub R5, R6."""
    order(db, s, 7, created_at=TS(0), planned=True)
    hours = (6, 2, 9, 1, 5, 3)
    o = {
        n: order(db, s, n, draft=True, created_at=TS(h))
        for n, h in enumerate(hours, start=1)
    }
    result = _ph(db, s, **F())
    # Then 1
    assert result["awaiting_setup_count"] == 6
    # Then 2
    assert hids(result["oldest_drafts"]) == [
        o[4].id,
        o[2].id,
        o[6].id,
        o[5].id,
        o[1].id,
    ]


# [claude] TRO-PH-07
def test_tro_ph_07__nothing_matching(db, s):
    """TRO-PH-07 — nothing matching gives zero counts and empty lists.
    Rules: get_pending_highlights_for_hub R7."""
    order(db, s, 1, ws=0, planned=True)
    order(db, s, 2, ws=2, draft=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result == {
        "pending_planned_count": 0,
        "pending_planned": [],
        "awaiting_setup_count": 0,
        "awaiting_setup": [],
        "oldest_drafts": [],
    }


# [claude] TRO-PH-08
@X2655
def test_tro_ph_08__planned_never_edited_by_created(db, s):
    """TRO-PH-08 — pending_planned sorts a never-edited order by its created_at.
    Rules: get_pending_highlights_for_hub R4 [BUG-2655]."""
    c = order(db, s, 1, updated_at=TS(4), planned=True)
    b = order(db, s, 2, updated_at=TS(8), planned=True)
    a = order(db, s, 6, planned=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 3
    # Then 2
    assert hids(result["pending_planned"]) == [b.id, a.id, c.id]


# [claude] TRO-PH-09
@X2655
def test_tro_ph_09__draft_never_edited_by_created(db, s):
    """TRO-PH-09 — awaiting_setup sorts a never-edited draft by its created_at.
    Rules: get_pending_highlights_for_hub R4 [BUG-2655]."""
    c = order(db, s, 1, draft=True, updated_at=TS(4))
    b = order(db, s, 2, draft=True, updated_at=TS(8))
    a = order(db, s, 6, draft=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result["awaiting_setup_count"] == 3
    # Then 2
    assert hids(result["awaiting_setup"]) == [b.id, a.id, c.id]


# [claude] TRO-PH-10
@X2656N
def test_tro_ph_10__tied_planned_id_desc(db, s):
    """TRO-PH-10 — tied planned orders come by id descending.
    Rules: get_pending_highlights_for_hub R4 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5), updated_at=TS(9), planned=True)
    b = order(db, s, 2, created_at=TS(5), updated_at=TS(9), planned=True)
    c = order(db, s, 3, created_at=TS(5), updated_at=TS(9), planned=True)
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = _ph(db, s, **F())
    # Then 1
    assert hids(result["pending_planned"]) == [cid, bid, aid]


# [claude] TRO-PH-11
@X2656N
def test_tro_ph_11__tied_oldest_drafts_id_asc(db, s):
    """TRO-PH-11 — oldest drafts with equal created_at come by id ascending.
    Rules: get_pending_highlights_for_hub R6 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, draft=True, created_at=TS(5))
    b = order(db, s, 2, draft=True, created_at=TS(5))
    c = order(db, s, 3, draft=True, created_at=TS(5))
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = _ph(db, s, **F())
    # Then 1
    assert hids(result["oldest_drafts"]) == [aid, bid, cid]


# [claude] TRO-PH-12
@X2656
def test_tro_ph_12__every_ordered_query_ends_with_id(db, s):
    """TRO-PH-12 — every ordered highlight query ends with an id tie-break.
    Rules: get_pending_highlights_for_hub R4, R6 [BUG-2656]."""
    order(db, s, 1, planned=True)
    order(db, s, 2, draft=True)
    w1 = s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        dao.get_pending_highlights_for_hub(db, workspace_id=w1, **F())
    # Then 1
    ordered = [
        st for st in rec.selects if "FROM transfer_orders" in st and "ORDER BY" in st
    ]
    assert len(ordered) >= 1
    # Then 2
    assert all(
        order_part_of(st)
        .strip()
        .endswith(
            ("transfer_orders.id DESC", "transfer_orders.id ASC", "transfer_orders.id")
        )
        for st in ordered
    )


# [claude] TRO-PH-13
def test_tro_ph_13__unknown_keyword_type_error(db, s):
    """TRO-PH-13 — an unknown filter keyword raises TypeError.
    Rules: get_pending_highlights_for_hub Errors."""
    order(db, s, 1, planned=True)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.get_pending_highlights_for_hub(
            db, workspace_id=s.W1.id, colour="red", **F()
        )
    # Then 2
    assert total(db) == before


# [claude] TRO-PH-14
def test_tro_ph_14__writes_nothing_no_lock(db, s):
    """TRO-PH-14 — writes nothing and takes no lock in any of its queries.
    Rules: get_pending_highlights_for_hub Side effects; HR-10 note."""
    order(db, s, 1, planned=True)
    order(db, s, 2, draft=True)
    with StatementRecorder(db) as rec:
        result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] + result["awaiting_setup_count"] == 2
    # Then 2
    assert len(rec.selects) >= 1
    # Then 3
    assert rec.written == []
    # Then 4
    assert all("FOR UPDATE" not in st for st in rec.selects)


# =========================================================================== #
# TransferOrderDAO.aggregate_hub_stats
# =========================================================================== #


def _agg(db, s, **kw):
    """The When of the AS cards."""
    return dao.aggregate_hub_stats(db, workspace_id=s.W1.id, **kw)


def _four_open_one_completed(db, s):
    """Given of AS-01 / AS-02: orders 1-4, order 5 completed."""
    for n in range(1, 5):
        order(db, s, n)
    order(db, s, 5, completed=True)


# [claude] TRO-AS-01
def test_tro_as_01__default_drops_completed(db, s):
    """TRO-AS-01 — by default completed orders are dropped: (4, 4, 0).
    Rules: aggregate_hub_stats R1, R3."""
    _four_open_one_completed(db, s)
    result = _agg(db, s, **F())
    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert result == (4, 4, 0)
    # Then 3
    assert all(type(v) is int for v in result)


# [claude] TRO-AS-02
def test_tro_as_02__split_open_completed(db, s):
    """TRO-AS-02 — exclude_complete=False splits open and completed: (5, 4, 1).
    Rules: aggregate_hub_stats R1, R2."""
    _four_open_one_completed(db, s)
    result = _agg(db, s, exclude_complete=False, **F())
    # Then 1
    assert result == (5, 4, 1)


# [claude] TRO-AS-03
def test_tro_as_03__no_orders_zeros(db, s):
    """TRO-AS-03 — no orders gives (0, 0, 0).
    Rules: aggregate_hub_stats R1."""
    order(db, s, 1, ws=0)
    order(db, s, 2, ws=2, completed=True)
    result = _agg(db, s, exclude_complete=False, **F())
    # Then 1
    assert result == (0, 0, 0)
    # Then 2
    assert all(type(v) is int for v in result)


# [claude] TRO-AS-04
def test_tro_as_04__only_completed(db, s):
    """TRO-AS-04 — only completed orders: (2, 0, 2).
    Rules: aggregate_hub_stats R2."""
    order(db, s, 1, completed=True)
    order(db, s, 2, completed=True)
    result = _agg(db, s, exclude_complete=False, **F())
    # Then 1
    assert result == (2, 0, 2)


# [claude] TRO-AS-05
def test_tro_as_05__other_workspaces_not_counted(db, s):
    """TRO-AS-05 — orders of W0 and W2 are not counted.
    Rules: aggregate_hub_stats R1, _apply_transfer_order_hub_filters R1."""
    order(db, s, 8, ws=0)
    order(db, s, 9, ws=0, completed=True)
    order(db, s, 1)
    order(db, s, 7, ws=2)
    order(db, s, 6, ws=2, completed=True)
    result = _agg(db, s, exclude_complete=False, **F())
    # Then 1
    assert result == (1, 1, 0)


# [claude] TRO-AS-06
def test_tro_as_06__stored_status_no_part(db, s):
    """TRO-AS-06 — the stored status plays no part.
    Rules: aggregate_hub_stats R2."""
    order(db, s, 1)
    order(db, s, 2, current_status_id=s.SC.id)
    order(db, s, 3, completed=True)
    result = _agg(db, s, exclude_complete=False, **F())
    # Then 1
    assert result == (3, 2, 1)


# [claude] TRO-AS-07
def test_tro_as_07__hub_filters_apply(db, s):
    """TRO-AS-07 — the hub filters apply.
    Rules: aggregate_hub_stats R1."""
    order(db, s, 1, source_location_id=s.FB.id)
    order(db, s, 2)
    order(db, s, 3, source_location_id=s.FB.id, completed=True)
    result = _agg(db, s, exclude_complete=False, **F(search="bravo"))
    # Then 1
    assert result == (2, 1, 1)


# [claude] TRO-AS-08
def test_tro_as_08__unknown_keyword_type_error(db, s):
    """TRO-AS-08 — an unknown filter keyword raises TypeError.
    Rules: aggregate_hub_stats Errors."""
    order(db, s, 1)
    before = total(db)
    # Then 1
    with pytest.raises(TypeError):
        dao.aggregate_hub_stats(db, workspace_id=s.W1.id, colour="red", **F())
    # Then 2
    assert total(db) == before


# [claude] TRO-AS-09
def test_tro_as_09__writes_nothing_no_lock(db, s):
    """TRO-AS-09 — writes nothing and takes no lock.
    Rules: aggregate_hub_stats Side effects; HR-10 note."""
    order(db, s, 1)
    with StatementRecorder(db) as rec:
        result = dao.aggregate_hub_stats(db, workspace_id=s.W1.id, **F())
    # Then 1
    assert result == (1, 1, 0)
    # Then 2
    assert rec.written == []
    # Then 3
    assert all("FOR UPDATE" not in st for st in rec.selects)


# =========================================================================== #
# TransferOrderDAO.list_touching_location_incomplete
# =========================================================================== #


def _touch(db, s, location_type, location_id):
    """The When of the TL cards (workspace W1)."""
    return dao.list_touching_location_incomplete(
        db, workspace_id=s.W1.id, location_type=location_type, location_id=location_id
    )


# [claude] TRO-TL-01
def test_tro_tl_01__either_end_newest_first(db, s):
    """TRO-TL-01 — orders with the location at either end, newest first, each once.
    Rules: list_touching_location_incomplete R1, R3."""
    a = order(db, s, 1, source_location_id=s.FB.id)
    b = order(
        db, s, 3, destination_location_type="storage", destination_location_id=s.FB.id
    )
    c = order(
        db,
        s,
        2,
        source_location_id=s.FB.id,
        destination_location_type="storage",
        destination_location_id=s.FB.id,
    )
    order(db, s, 4)
    result = _touch(db, s, "storage", s.FB.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] TRO-TL-02
def test_tro_tl_02__completed_left_out(db, s):
    """TRO-TL-02 — completed orders are left out.
    Rules: list_touching_location_incomplete R2."""
    order(db, s, 1, source_location_id=s.FB.id, completed=True)
    b = order(db, s, 2, source_location_id=s.FB.id)
    result = _touch(db, s, "storage", s.FB.id)
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-TL-03
def test_tro_tl_03__other_workspaces_left_out(db, s):
    """TRO-TL-03 — orders of W0 and W2 at the same type and id are left out.
    Rules: list_touching_location_incomplete R2."""
    order(db, s, 9, ws=0, source_location_id=MISSING)
    a = order(db, s, 1, source_location_id=MISSING)
    order(
        db,
        s,
        8,
        ws=2,
        destination_location_type="storage",
        destination_location_id=MISSING,
    )
    result = _touch(db, s, "storage", MISSING)
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-TL-04
def test_tro_tl_04__type_exact(db, s):
    """TRO-TL-04 — the type is compared exactly ("Storage" finds nothing).
    Rules: list_touching_location_incomplete R1."""
    order(db, s, 1, source_location_id=s.FB.id)
    result = _touch(db, s, "Storage", s.FB.id)
    # Then 1
    assert result == []


# [claude] TRO-TL-05
def test_tro_tl_05__same_id_other_type(db, s):
    """TRO-TL-05 — the same id under another type is not this location.
    Rules: list_touching_location_incomplete R1, R2."""
    order(db, s, 1, source_location_id=s.FB.id)
    result = _touch(db, s, "damaged", s.FB.id)
    # Then 1
    assert result == []


# [claude] TRO-TL-06
def test_tro_tl_06__current_status_loaded(db, s):
    """TRO-TL-06 — current_status comes loaded.
    Rules: list_touching_location_incomplete R1."""
    order(db, s, 1, current_status_id=s.SP.id)
    w1, m1 = s.W1.id, s.M1.id
    db.expunge_all()
    result = dao.list_touching_location_incomplete(
        db, workspace_id=w1, location_type="machine", location_id=m1
    )
    # Then 1
    assert loaded(result[0], "current_status")
    # Then 2
    assert result[0].current_status.name == "Planned"


# [claude] TRO-TL-07
def test_tro_tl_07__no_limit(db, s):
    """TRO-TL-07 — there is no limit.
    Rules: list_touching_location_incomplete R1."""
    for n in range(1, 56):
        order(db, s, n, flush=False)
    db.flush()
    result = _touch(db, s, "machine", s.M1.id)
    # Then 1
    assert len(result) == 55


# [claude] TRO-TL-08
@X2656N
def test_tro_tl_08__ties_id_desc(db, s):
    """TRO-TL-08 — orders with equal created_at come by id descending.
    Rules: list_touching_location_incomplete R3 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5))
    b = order(db, s, 2, created_at=TS(5))
    c = order(db, s, 3, created_at=TS(5))
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = _touch(db, s, "machine", s.M1.id)
    # Then 1
    assert ids(result) == [cid, bid, aid]


# [claude] TRO-TL-09
@X2656
def test_tro_tl_09__order_by_ends_with_id(db, s):
    """TRO-TL-09 — the query ends its ORDER BY with id DESC.
    Rules: list_touching_location_incomplete R3 [BUG-2656]."""
    order(db, s, 1)
    w1, m1 = s.W1.id, s.M1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        dao.list_touching_location_incomplete(
            db, workspace_id=w1, location_type="machine", location_id=m1
        )
    # Then 1
    assert "created_at DESC" in rec.order_part
    # Then 2
    assert rec.order_part.rstrip().endswith("transfer_orders.id DESC")


# [claude] TRO-TL-10
def test_tro_tl_10__writes_nothing_no_lock(db, s):
    """TRO-TL-10 — writes nothing and takes no lock.
    Rules: list_touching_location_incomplete Side effects."""
    e = order(db, s, 1)
    e.source_location_id = s.FB.id
    p = order(db, s, 5, flush=False)
    with StatementRecorder(db) as rec:
        result = _touch(db, s, "machine", s.M1.id)
    # Then 1
    assert ids(result) == [e.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql


# [claude] TRO-TL-11
def test_tro_tl_11__nothing_matching(db, s):
    """TRO-TL-11 — nothing matching gives [].
    Rules: list_touching_location_incomplete R2."""
    order(db, s, 1)
    result = _touch(db, s, "machine", s.MB.id)
    # Then 1
    assert result == []


# =========================================================================== #
# TransferOrderDAO.list_inbound_to_storage_incomplete
# =========================================================================== #


def _inbound(db, s, factory_id):
    """The When of the IB cards (workspace W1)."""
    return dao.list_inbound_to_storage_incomplete(
        db, workspace_id=s.W1.id, factory_id=factory_id
    )


def _into_f1(s):
    """ "but `source_location_id FB.id`, `destination_location_type "storage"`,
    `destination_location_id F1.id`"."""
    return {
        "source_location_id": s.FB.id,
        "destination_location_type": "storage",
        "destination_location_id": s.F1.id,
    }


# [claude] TRO-IB-01
def test_tro_ib_01__open_into_f1_newest_first(db, s):
    """TRO-IB-01 — open orders into F1's storage, newest first.
    Rules: list_inbound_to_storage_incomplete R1, R3."""
    a = order(db, s, 1, **_into_f1(s))
    b = order(db, s, 3, **_into_f1(s))
    c = order(
        db,
        s,
        2,
        source_location_type="machine",
        source_location_id=s.MB.id,
        destination_location_type="storage",
        destination_location_id=s.F1.id,
    )
    order(db, s, 4)
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] TRO-IB-02
def test_tro_ib_02__damaged_destination_left_out(db, s):
    """TRO-IB-02 — a damaged destination of the factory is left out.
    Rules: list_inbound_to_storage_incomplete R2."""
    order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="damaged",
        destination_location_id=s.F1.id,
    )
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert result == []


# [claude] TRO-IB-03
def test_tro_ib_03__storage_as_source_left_out(db, s):
    """TRO-IB-03 — the factory's storage as source is left out.
    Rules: list_inbound_to_storage_incomplete R2."""
    order(db, s, 1)
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert result == []


# [claude] TRO-IB-04
def test_tro_ib_04__completed_left_out(db, s):
    """TRO-IB-04 — completed orders are left out.
    Rules: list_inbound_to_storage_incomplete R2."""
    order(db, s, 1, completed=True, **_into_f1(s))
    b = order(db, s, 2, **_into_f1(s))
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-IB-05
def test_tro_ib_05__other_factory_left_out(db, s):
    """TRO-IB-05 — another factory's storage is left out.
    Rules: list_inbound_to_storage_incomplete R2."""
    order(
        db, s, 1, destination_location_type="storage", destination_location_id=s.FB.id
    )
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert result == []


# [claude] TRO-IB-06
def test_tro_ib_06__other_workspaces_left_out(db, s):
    """TRO-IB-06 — orders of W0 and W2 into the same storage id are left out.
    Rules: list_inbound_to_storage_incomplete R2."""
    into_missing = {
        "destination_location_type": "storage",
        "destination_location_id": MISSING,
    }
    order(db, s, 9, ws=0, **into_missing)
    a = order(db, s, 1, **into_missing)
    order(db, s, 8, ws=2, **into_missing)
    result = _inbound(db, s, MISSING)
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-IB-07
def test_tro_ib_07__type_exact(db, s):
    """TRO-IB-07 — the type is compared exactly ("Storage" is left out).
    Rules: list_inbound_to_storage_incomplete R1."""
    order(
        db,
        s,
        1,
        source_location_id=s.FB.id,
        destination_location_type="Storage",
        destination_location_id=s.F1.id,
    )
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert result == []


# [claude] TRO-IB-08
def test_tro_ib_08__stored_status_no_matter(db, s):
    """TRO-IB-08 — the stored status does not matter.
    Rules: list_inbound_to_storage_incomplete R1."""
    a = order(db, s, 1, current_status_id=s.SC.id, **_into_f1(s))
    b = order(db, s, 2, current_status_id=s.SP.id, **_into_f1(s))
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-IB-09
def test_tro_ib_09__status_loaded_no_limit(db, s):
    """TRO-IB-09 — current_status comes loaded, and there is no limit.
    Rules: list_inbound_to_storage_incomplete R1."""
    for n in range(1, 56):
        order(db, s, n, flush=False, **_into_f1(s))
    db.flush()
    w1, f1 = s.W1.id, s.F1.id
    db.expunge_all()
    result = dao.list_inbound_to_storage_incomplete(db, workspace_id=w1, factory_id=f1)
    # Then 1
    assert loaded(result[0], "current_status")
    # Then 2
    assert len(result) == 55


# [claude] TRO-IB-10
@X2656N
def test_tro_ib_10__ties_id_desc(db, s):
    """TRO-IB-10 — orders with equal created_at come by id descending.
    Rules: list_inbound_to_storage_incomplete R3 [BUG-2656]."""
    seqscan(db)
    a = order(db, s, 1, created_at=TS(5), **_into_f1(s))
    b = order(db, s, 2, created_at=TS(5), **_into_f1(s))
    c = order(db, s, 3, created_at=TS(5), **_into_f1(s))
    aid, bid, cid = a.id, b.id, c.id
    bump(db, a)
    result = _inbound(db, s, s.F1.id)
    # Then 1
    assert ids(result) == [cid, bid, aid]


# [claude] TRO-IB-11
@X2656
def test_tro_ib_11__order_by_ends_with_id(db, s):
    """TRO-IB-11 — the query ends its ORDER BY with id DESC.
    Rules: list_inbound_to_storage_incomplete R3 [BUG-2656]."""
    order(db, s, 1, **_into_f1(s))
    w1, f1 = s.W1.id, s.F1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        dao.list_inbound_to_storage_incomplete(db, workspace_id=w1, factory_id=f1)
    # Then 1
    assert "created_at DESC" in rec.order_part
    # Then 2
    assert rec.order_part.rstrip().endswith("transfer_orders.id DESC")


# [claude] TRO-IB-12
def test_tro_ib_12__writes_nothing_no_lock(db, s):
    """TRO-IB-12 — writes nothing and takes no lock.
    Rules: list_inbound_to_storage_incomplete Side effects."""
    e = order(db, s, 1, **_into_f1(s))
    e.source_location_id = MISSING
    p = order(
        db,
        s,
        5,
        flush=False,
        destination_location_type="storage",
        destination_location_id=s.F1.id,
    )
    with StatementRecorder(db) as rec:
        result = _inbound(db, s, s.F1.id)
    # Then 1
    assert ids(result) == [e.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql


# =========================================================================== #
# TransferOrderDAO.get_by_id_and_workspace
# =========================================================================== #


# [claude] TRO-GI-01
def test_tro_gi_01__returns_order_status_loaded(db, s):
    """TRO-GI-01 — returns the asked order, with current_status loaded.
    Rules: TransferOrderDAO.get_by_id_and_workspace R1."""
    order(db, s, 1)
    b = order(db, s, 2, current_status_id=s.SP.id)
    order(db, s, 3)
    bid, w1 = b.id, s.W1.id
    db.expunge_all()
    result = dao.get_by_id_and_workspace(db, id=bid, workspace_id=w1)
    # Then 1
    assert isinstance(result, TransferOrder)
    # Then 2
    assert loaded(result, "current_status")
    # Then 3
    assert result.id == bid
    # Then 4
    assert result.current_status.name == "Planned"


# [claude] TRO-GI-02
def test_tro_gi_02__w0_order_none_for_w1(db, s):
    """TRO-GI-02 — an order of the earlier workspace W0 is None for W1.
    Rules: TransferOrderDAO.get_by_id_and_workspace R2."""
    x0 = order(db, s, 1, ws=0)
    order(db, s, 2)
    result = dao.get_by_id_and_workspace(db, id=x0.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] TRO-GI-03
def test_tro_gi_03__w2_order_none_for_w1(db, s):
    """TRO-GI-03 — an order of the later workspace W2 is None for W1.
    Rules: TransferOrderDAO.get_by_id_and_workspace R2."""
    order(db, s, 1)
    x2 = order(db, s, 2, ws=2)
    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] TRO-GI-04
def test_tro_gi_04__w2_own_order(db, s):
    """TRO-GI-04 — asked for W2, its own order is returned.
    Rules: TransferOrderDAO.get_by_id_and_workspace R1."""
    order(db, s, 1)
    x2 = order(db, s, 2, ws=2)
    result = dao.get_by_id_and_workspace(db, id=x2.id, workspace_id=s.W2.id)
    # Then 1
    assert result.id == x2.id


# [claude] TRO-GI-05
def test_tro_gi_05__unknown_id_none(db, s):
    """TRO-GI-05 — an unknown id is None.
    Rules: TransferOrderDAO.get_by_id_and_workspace R2."""
    order(db, s, 1)
    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# [claude] TRO-GI-06
def test_tro_gi_06__completed_still_returned(db, s):
    """TRO-GI-06 — a completed order is still returned.
    Rules: TransferOrderDAO.get_by_id_and_workspace R1."""
    a = order(db, s, 1, completed=True)
    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=s.W1.id)
    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.completed_at == DONE


# [claude] TRO-GI-07
def test_tro_gi_07__no_lock_nothing_written(db, s):
    """TRO-GI-07 — no row lock is taken and nothing is written.
    Rules: TransferOrderDAO.get_by_id_and_workspace R3."""
    a = order(db, s, 1)
    aid, w1 = a.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = dao.get_by_id_and_workspace(db, id=aid, workspace_id=w1)
    # Then 1
    assert result.id == aid
    # Then 2
    assert all("FOR UPDATE" not in st for st in rec.selects)
    # Then 3
    assert rec.written == []


# =========================================================================== #
# TransferOrderDAO.get_next_number
# (every card starts with numlock; every call runs under clock(NOW31, NOW31)
#  unless the card gives its own clock line)
# =========================================================================== #


def _next(db, ws):
    """The When of the NN cards, under the default clock(NOW31, NOW31)."""
    with clock(NOW31, NOW31):
        return dao.get_next_number(db, workspace_id=ws)


# [claude] TRO-NN-01
def test_tro_nn_01__first_number(db, s):
    """TRO-NN-01 — no number yet gives TR-2031-001.
    Rules: get_next_number R2, Returns."""
    numlock(db)
    result = _next(db, s.W1.id)
    # Then 1
    assert isinstance(result, str)
    # Then 2
    assert result == "TR-2031-001"


# [claude] TRO-NN-02
def test_tro_nn_02__after_five(db, s):
    """TRO-NN-02 — after -001 … -005 comes -006.
    Rules: get_next_number R3."""
    numlock(db)
    for k in range(1, 6):
        num(db, s, 1, f"TR-2031-{k:03d}", created_at=TS(k))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-006"


# [claude] TRO-NN-03, NN-04, NN-05, NN-06, NN-07, NN-11, NN-18, NN-19
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        pytest.param("TR-2031-007", "TR-2031-008", id="TRO-NN-03"),
        pytest.param("TR-2031-009", "TR-2031-010", id="TRO-NN-04"),
        pytest.param("TR-2031-099", "TR-2031-100", id="TRO-NN-05"),
        pytest.param("TR-2031-998", "TR-2031-999", id="TRO-NN-06"),
        pytest.param("TR-2031-999", "TR-2031-1000", id="TRO-NN-07"),
        pytest.param("TR-2031-abc", "TR-2031-001", id="TRO-NN-11"),
        pytest.param("TR-20311-009", "TR-2031-001", id="TRO-NN-18"),
        pytest.param("XTR-2031-009", "TR-2031-001", id="TRO-NN-19"),
    ],
)
def test_tro_nn_one_stored_number(db, s, stored, expected):
    """TRO-NN-03 … NN-07, NN-11, NN-18, NN-19 — one stored number gives the next: the highest
    decides (-007 → -008), -009 → -010, -099 → -100, -998 → -999, -999 → -1000 (not cut);
    a non-numeric suffix alone, a longer year and a prefix in the middle give -001.
    Rules: get_next_number R2, R3, R4."""
    numlock(db)
    num(db, s, 1, stored)
    result = _next(db, s.W1.id)
    # Then 1
    assert result == expected


# [claude] TRO-NN-08
@X2651
def test_tro_nn_08__999_and_1000(db, s):
    """TRO-NN-08 — with -999 and -1000 stored the next is -1001.
    Rules: get_next_number R3 [BUG-2651]."""
    numlock(db)
    num(db, s, 1, "TR-2031-999", created_at=TS(1))
    num(db, s, 1, "TR-2031-1000", created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-1001"


# [claude] TRO-NN-09
@X2651
def test_tro_nn_09__1005_and_999(db, s):
    """TRO-NN-09 — with -1005 and -999 stored the next is -1006.
    Rules: get_next_number R3 [BUG-2651]."""
    numlock(db)
    num(db, s, 1, "TR-2031-1005", created_at=TS(1))
    num(db, s, 1, "TR-2031-999", created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-1006"


# [claude] TRO-NN-10
@X2651
def test_tro_nn_10__non_numeric_ignored_beside_005(db, s):
    """TRO-NN-10 — a non-numeric suffix is ignored beside -005.
    Rules: get_next_number R4 [BUG-2651]."""
    numlock(db)
    num(db, s, 1, "TR-2031-005", created_at=TS(1))
    num(db, s, 1, "TR-2031-abc", created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-006"


# [claude] TRO-NN-12
def test_tro_nn_12__only_w1_counts(db, s):
    """TRO-NN-12 — only W1's numbers count, with higher numbers in W0 and W2.
    Rules: get_next_number R2, R3."""
    numlock(db)
    num(db, s, 0, "TR-2031-011", created_at=TS(1))
    num(db, s, 0, "TR-2031-012", created_at=TS(2))
    num(db, s, 1, "TR-2031-010", created_at=TS(3))
    num(db, s, 2, "TR-2031-013", created_at=TS(4))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-011"


# [claude] TRO-NN-13
def test_tro_nn_13__only_w2_counts(db, s):
    """TRO-NN-13 — asked for W2, only W2's numbers count, with higher ones in W0 and W1.
    Rules: get_next_number R2, R3."""
    numlock(db)
    num(db, s, 0, "TR-2031-008", created_at=TS(1))
    num(db, s, 1, "TR-2031-007", created_at=TS(2))
    num(db, s, 2, "TR-2031-003", created_at=TS(3))
    result = _next(db, s.W2.id)
    # Then 1
    assert result == "TR-2031-004"


# [claude] TRO-NN-14
def test_tro_nn_14__only_w0_counts(db, s):
    """TRO-NN-14 — asked for W0, only W0's numbers count, with higher ones in W1 and W2.
    Rules: get_next_number R2, R3."""
    numlock(db)
    num(db, s, 0, "TR-2031-002", created_at=TS(1))
    num(db, s, 1, "TR-2031-005", created_at=TS(2))
    num(db, s, 2, "TR-2031-006", created_at=TS(3))
    result = _next(db, s.W0.id)
    # Then 1
    assert result == "TR-2031-003"


# [claude] TRO-NN-15
def test_tro_nn_15__empty_w1_beside_w2(db, s):
    """TRO-NN-15 — an empty W1 gets -001 although W2 holds -001 … -003.
    Rules: get_next_number R2."""
    numlock(db)
    for k in range(1, 4):
        num(db, s, 2, f"TR-2031-{k:03d}", created_at=TS(k))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-001"


# [claude] TRO-NN-16
def test_tro_nn_16__other_years_not_counted(db, s):
    """TRO-NN-16 — numbers of the year before and the year after are not counted.
    Rules: get_next_number R2, R3."""
    numlock(db)
    num(db, s, 1, "TR-2030-050", created_at=TS(1))
    num(db, s, 1, "TR-2032-060", created_at=TS(2))
    num(db, s, 1, "TR-2031-004", created_at=TS(3))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-005"


# [claude] TRO-NN-17
def test_tro_nn_17__only_other_years(db, s):
    """TRO-NN-17 — only other years' numbers give -001.
    Rules: get_next_number R2."""
    numlock(db)
    num(db, s, 1, "TR-2030-050", created_at=TS(1))
    num(db, s, 1, "TR-2032-060", created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-001"


# [claude] TRO-NN-20
def test_tro_nn_20__unknown_workspace(db, s):
    """TRO-NN-20 — an unknown workspace gets -001.
    Rules: get_next_number R2."""
    numlock(db)
    num(db, s, 1, "TR-2031-004")
    result = _next(db, MISSING)
    # Then 1
    assert result == "TR-2031-001"


# [claude] TRO-NN-21
def test_tro_nn_21__writes_nothing(db, s):
    """TRO-NN-21 — writes nothing: a pending order is not counted and stays pending, an
    unflushed edit stays unflushed.
    Rules: get_next_number Side effects."""
    numlock(db)
    e = num(db, s, 1, "TR-2031-002")
    e.destination_location_id = s.MB.id
    p = num(db, s, 1, "TR-2031-009", created_at=TS(2), flush=False)
    with StatementRecorder(db) as rec:
        result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-003"
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []


# [claude] TRO-NN-22
def test_tro_nn_22__one_query_no_lock(db, s):
    """TRO-NN-22 — one query, no row lock.
    Rules: get_next_number Side effects; HR-10 note."""
    numlock(db)
    num(db, s, 1, "TR-2031-004")
    w1 = s.W1.id
    db.expunge_all()
    with StatementRecorder(db) as rec:
        result = _next(db, w1)
    # Then 1
    assert result == "TR-2031-005"
    # Then 2
    assert len(rec.selects) == 1
    # Then 3
    assert "FOR UPDATE" not in rec.sql


# [claude] TRO-NN-23
def test_tro_nn_23__both_clocks_2033(db, s):
    """TRO-NN-23 — with both clocks in 2033 the number is TR-2033-…, and 2031's numbers do not count.
    Rules: get_next_number R1, R2, R3."""
    numlock(db)
    num(db, s, 1, "TR-2031-004", created_at=TS(1))
    num(db, s, 1, "TR-2033-002", created_at=TS(2))
    t2033 = datetime(2033, 6, 1, 12, 0)
    with clock(t2033, t2033):
        result = dao.get_next_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "TR-2033-003"


def _years_30_31(db, s):
    """Given 2-3 of NN-24 / NN-25."""
    num(db, s, 1, "TR-2030-004", created_at=TS(1))
    num(db, s, 1, "TR-2031-007", created_at=TS(2))


# [claude] TRO-NN-24
@X2653
def test_tro_nn_24__utc_year_local_already_next(db, s):
    """TRO-NN-24 — the year is the UTC year when the local clock is already in the next year.
    Rules: get_next_number R1 [BUG-2653]."""
    numlock(db)
    _years_30_31(db, s)
    local, utc = datetime(2031, 1, 1, 2, 0), datetime(2030, 12, 31, 20, 0)
    with clock(local, utc):
        result = dao.get_next_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "TR-2030-005"


# [claude] TRO-NN-25
@X2653
def test_tro_nn_25__utc_year_local_still_old(db, s):
    """TRO-NN-25 — the year is the UTC year when the local clock is still in the old year.
    Rules: get_next_number R1 [BUG-2653]."""
    numlock(db)
    _years_30_31(db, s)
    local, utc = datetime(2030, 12, 31, 18, 0), datetime(2031, 1, 1, 0, 30)
    with clock(local, utc):
        result = dao.get_next_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "TR-2031-008"


# [claude] TRO-NN-26
@X2653
def test_tro_nn_26__year_follows_utcnow(db, s):
    """TRO-NN-26 — the year follows utcnow(), not the local clock.
    Rules: get_next_number R1 [BUG-2653]."""
    numlock(db)
    num(db, s, 1, "TR-2033-004", created_at=TS(1))
    num(db, s, 1, "TR-2031-007", created_at=TS(2))
    with utconly(datetime(2033, 6, 1, 12, 0)):  # no default clock: real local clock
        result = dao.get_next_number(db, workspace_id=s.W1.id)
    # Then 1
    assert result == "TR-2033-005"


def _count_number(db, number):
    return db.scalar(
        select(func.count())
        .select_from(TransferOrder)
        .where(TransferOrder.transfer_number == number)
    )


# [claude] TRO-NN-27
@X2650
def test_tro_nn_27__w1_stores_number_held_by_w2(db, s):
    """TRO-NN-27 — W1 can store TR-2031-001 while the later workspace W2 holds it.
    Rules: get_next_number R5 [BUG-2650]."""
    numlock(db)
    num(db, s, 2, "TR-2031-001")
    t = num(db, s, 1, "TR-2031-001", add=False)
    # When (today it raises IntegrityError 23505 here, before Then 1 — see the card)
    with db.begin_nested():
        db.add(t)
        db.flush()
    # Then 1
    assert t.id is not None
    # Then 2
    assert _count_number(db, "TR-2031-001") == 2


# [claude] TRO-NN-28
@X2650
def test_tro_nn_28__w1_stores_number_held_by_w0(db, s):
    """TRO-NN-28 — W1 can store TR-2031-001 while the earlier workspace W0 holds it.
    Rules: get_next_number R5 [BUG-2650]."""
    numlock(db)
    num(db, s, 0, "TR-2031-001")
    t = num(db, s, 1, "TR-2031-001", add=False)
    # When (today it raises IntegrityError 23505 here, before Then 1 — see the card)
    with db.begin_nested():
        db.add(t)
        db.flush()
    # Then 1
    assert t.id is not None
    # Then 2
    assert _count_number(db, "TR-2031-001") == 2


# [claude] TRO-NN-29
def test_tro_nn_29__same_workspace_duplicate_refused(db, s):
    """TRO-NN-29 — the same number twice in one workspace is refused by the database.
    Rules: get_next_number R5."""
    numlock(db)
    num(db, s, 1, "TR-2031-001", created_at=TS(1))
    t = num(db, s, 1, "TR-2031-001", created_at=TS(2), add=False)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(t)
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert (
        db.scalar(
            select(func.count())
            .select_from(TransferOrder)
            .where(TransferOrder.workspace_id == s.W1.id)
        )
        == 1
    )


# [claude] TRO-NN-30, NN-31
@pytest.mark.parametrize(
    "other",
    [
        pytest.param("tr-2031-009", id="TRO-NN-30"),
        pytest.param("Tr-2031-009", id="TRO-NN-31"),
    ],
)
def test_tro_nn_30_31__prefix_case_sensitive(db, s, other):
    """TRO-NN-30, NN-31 — a lowercase / mixed-case prefix is not counted.
    Rules: get_next_number R2a."""
    numlock(db)
    num(db, s, 1, "TR-2031-003", created_at=TS(1))
    num(db, s, 1, other, created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-004"


# [claude] TRO-NN-32
@X2651
def test_tro_nn_32__inner_dash_suffix_ignored(db, s):
    """TRO-NN-32 — a suffix with an inner dash (TR-2031-0-5) alone is ignored and gives -001.
    Rules: get_next_number R2b, R4 [BUG-2651]."""
    numlock(db)
    num(db, s, 1, "TR-2031-0-5")
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-001"


# [claude] TRO-NN-33
def test_tro_nn_33__900_beside_inner_dash(db, s):
    """TRO-NN-33 — beside TR-2031-0-5, a higher plain number still decides (-900 gives -901).
    Rules: get_next_number R2b, R3."""
    numlock(db)
    num(db, s, 1, "TR-2031-0-5", created_at=TS(1))
    num(db, s, 1, "TR-2031-900", created_at=TS(2))
    result = _next(db, s.W1.id)
    # Then 1
    assert result == "TR-2031-901"


# =========================================================================== #
# TransferOrderItemDAO.get_by_order
# =========================================================================== #


def _lines(db, t, ws):
    """The When of the IO cards."""
    return idao.get_by_order(db, transfer_order_id=t, workspace_id=ws)


# [claude] TRO-IO-01
def test_tro_io_01__by_line_number(db, s):
    """TRO-IO-01 — returns the order's lines by line_number, with ids not in that order.
    Rules: TransferOrderItemDAO.get_by_order R1, R2."""
    t = order(db, s, 1)
    l2 = line(db, s, t, 2)
    l1 = line(db, s, t, 1)
    l3 = line(db, s, t, 3)
    result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert isinstance(result[0], TransferOrderItem)
    # Then 2
    assert ids(result) == [l1.id, l2.id, l3.id]


# [claude] TRO-IO-02
def test_tro_io_02__neighbour_orders_left_out(db, s):
    """TRO-IO-02 — lines of the orders just below and above are left out.
    Rules: TransferOrderItemDAO.get_by_order R1."""
    t0 = order(db, s, 1)
    t = order(db, s, 2)
    t3 = order(db, s, 3)
    line(db, s, t0, 1)
    k = line(db, s, t, 1)
    line(db, s, t3, 1)
    result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert ids(result) == [k.id]


# [claude] TRO-IO-03, IO-04
@pytest.mark.parametrize(
    "other", [pytest.param(2, id="TRO-IO-03"), pytest.param(0, id="TRO-IO-04")]
)
def test_tro_io_03_04__other_workspace_gets_nothing(db, s, other):
    """TRO-IO-03, IO-04 — asked for the later workspace W2 / the earlier W0, W1's lines are not
    returned.
    Rules: TransferOrderItemDAO.get_by_order R1."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    ws = {0: s.W0, 2: s.W2}[other]
    result = _lines(db, t.id, ws.id)
    # Then 1
    assert result == []


# [claude] TRO-IO-05
def test_tro_io_05__unknown_order(db, s):
    """TRO-IO-05 — an unknown order gives [].
    Rules: TransferOrderItemDAO.get_by_order R1."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    result = _lines(db, MISSING, s.W1.id)
    # Then 1
    assert result == []


# [claude] TRO-IO-06
def test_tro_io_06__no_limit(db, s):
    """TRO-IO-06 — there is no limit.
    Rules: TransferOrderItemDAO.get_by_order R1."""
    t = order(db, s, 1)
    for k in range(1, 56):
        line(db, s, t, k, flush=False)
    db.flush()
    result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert len(result) == 55


# [claude] TRO-IO-07
def test_tro_io_07__tied_numbers_both_before_higher(db, s):
    """TRO-IO-07 — two lines with one number are both returned, before the higher number.
    Rules: TransferOrderItemDAO.get_by_order R1, R2."""
    t = order(db, s, 1)
    lx = line(db, s, t, 2)
    la = line(db, s, t, 1)
    lb = line(db, s, t, 1)
    result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert {result[0].id, result[1].id} == {la.id, lb.id}
    # Then 2
    assert result[2].id == lx.id


# [claude] TRO-IO-08
@X2657N
def test_tro_io_08__tied_numbers_id_asc(db, s):
    """TRO-IO-08 — lines with one number come by id ascending.
    Rules: TransferOrderItemDAO.get_by_order R2 [BUG-2657]."""
    seqscan(db)
    t = order(db, s, 1)
    la = line(db, s, t, 1)
    lb = line(db, s, t, 1)
    lc = line(db, s, t, 1)
    tid, aid, bid, cid = t.id, la.id, lb.id, lc.id
    bump_l(db, la)
    result = _lines(db, tid, s.W1.id)
    # Then 1
    assert ids(result) == [aid, bid, cid]


# [claude] TRO-IO-09
@X2657
def test_tro_io_09__order_by_ends_with_line_id(db, s):
    """TRO-IO-09 — the line query ends its ORDER BY with the line id.
    Rules: TransferOrderItemDAO.get_by_order R2 [BUG-2657]."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    tid, w1 = t.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db, "transfer_order_items") as rec:
        idao.get_by_order(db, transfer_order_id=tid, workspace_id=w1)
    # Then 1
    assert "line_number" in rec.order_part
    # Then 2
    assert rec.order_part.rstrip().endswith(
        "transfer_order_items.id"
    ) or rec.order_part.rstrip().endswith("transfer_order_items.id ASC")


# [claude] TRO-IO-10
def test_tro_io_10__quantities_half_up(db, s):
    """TRO-IO-10 — quantities come back stored half up to two decimals.
    Rules: Standing decisions (HR-15 note: quantities Numeric(15, 2))."""
    t = order(db, s, 1)
    line(db, s, t, 1, quantity=Decimal("1.005"))
    line(db, s, t, 2, quantity=Decimal("2.125"))
    line(db, s, t, 3, quantity=Decimal("2.124"))
    db.expire_all()
    result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert result[0].quantity == Decimal("1.01")
    # Then 2
    assert result[1].quantity == Decimal("2.13")
    # Then 3
    assert result[2].quantity == Decimal("2.12")


# [claude] TRO-IO-11
def test_tro_io_11__writes_nothing_no_lock(db, s):
    """TRO-IO-11 — writes nothing and takes no lock.
    Rules: TransferOrderItemDAO.get_by_order Side effects."""
    t = order(db, s, 1)
    k = line(db, s, t, 1)
    k.quantity = Decimal("9.00")
    p = line(db, s, t, 2, flush=False)
    with StatementRecorder(db, "transfer_order_items") as rec:
        result = _lines(db, t.id, s.W1.id)
    # Then 1
    assert ids(result) == [k.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert k in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec.written == []
    # Then 7
    assert "FOR UPDATE" not in rec.sql


# =========================================================================== #
# TransferOrderItemDAO.get_by_transfer_order_ids
# =========================================================================== #


def _by_ids(db, ws, tids):
    """The When of the IT cards."""
    return idao.get_by_transfer_order_ids(db, workspace_id=ws, transfer_order_ids=tids)


# [claude] TRO-IT-01
def test_tro_it_01__empty_list_no_query(db, s):
    """TRO-IT-01 — an empty id list gives [] without a query.
    Rules: get_by_transfer_order_ids R1."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    with StatementRecorder(db, "transfer_order_items") as rec:
        result = _by_ids(db, s.W1.id, [])
    # Then 1
    assert result == []
    # Then 2
    assert len(rec.selects) == 0


# [claude] TRO-IT-02
def test_tro_it_02__by_order_then_line(db, s):
    """TRO-IT-02 — lines sorted by order id, then line number, with ids in neither order.
    Rules: get_by_transfer_order_ids R2, R3."""
    a = order(db, s, 1)
    b = order(db, s, 2)
    lb2 = line(db, s, b, 2)
    la2 = line(db, s, a, 2)
    lb1 = line(db, s, b, 1)
    la1 = line(db, s, a, 1)
    result = _by_ids(db, s.W1.id, [b.id, a.id])
    # Then 1
    assert ids(result) == [la1.id, la2.id, lb1.id, lb2.id]


# [claude] TRO-IT-03
def test_tro_it_03__unlisted_orders_left_out(db, s):
    """TRO-IT-03 — lines of orders not in the list are left out, below and above.
    Rules: get_by_transfer_order_ids R2."""
    t0 = order(db, s, 1)
    t = order(db, s, 2)
    t3 = order(db, s, 3)
    line(db, s, t0, 1)
    k = line(db, s, t, 1)
    line(db, s, t3, 1)
    result = _by_ids(db, s.W1.id, [t.id])
    # Then 1
    assert ids(result) == [k.id]


# [claude] TRO-IT-04
def test_tro_it_04__other_ws_order_ids_match_nothing(db, s):
    """TRO-IT-04 — ids of W0's and W2's orders match nothing in W1.
    Rules: get_by_transfer_order_ids R2."""
    x0 = order(db, s, 1, ws=0)
    line(db, s, x0, 1)
    t = order(db, s, 2)
    line(db, s, t, 1)
    x2 = order(db, s, 3, ws=2)
    line(db, s, x2, 1)
    result = _by_ids(db, s.W1.id, [x0.id, x2.id])
    # Then 1
    assert result == []


# [claude] TRO-IT-05, IT-06
@pytest.mark.parametrize(
    "other", [pytest.param(2, id="TRO-IT-05"), pytest.param(0, id="TRO-IT-06")]
)
def test_tro_it_05_06__w1_id_matches_nothing_elsewhere(db, s, other):
    """TRO-IT-05, IT-06 — asked for W2 / W0, W1's order id matches nothing.
    Rules: get_by_transfer_order_ids R2."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    ws = {0: s.W0, 2: s.W2}[other]
    result = _by_ids(db, ws.id, [t.id])
    # Then 1
    assert result == []


# [claude] TRO-IT-07
def test_tro_it_07__tied_numbers_before_next_order(db, s):
    """TRO-IT-07 — two lines with one number of one order are both returned, before the next order.
    Rules: get_by_transfer_order_ids R2, R3."""
    a = order(db, s, 1)
    b = order(db, s, 2)
    lx = line(db, s, b, 1)
    la = line(db, s, a, 1)
    lb = line(db, s, a, 1)
    result = _by_ids(db, s.W1.id, [a.id, b.id])
    # Then 1
    assert {result[0].id, result[1].id} == {la.id, lb.id}
    # Then 2
    assert result[2].id == lx.id


# [claude] TRO-IT-08
@X2657N
def test_tro_it_08__tied_id_asc(db, s):
    """TRO-IT-08 — lines with one order and number come by id ascending.
    Rules: get_by_transfer_order_ids R3 [BUG-2657]."""
    seqscan(db)
    t = order(db, s, 1)
    la = line(db, s, t, 1)
    lb = line(db, s, t, 1)
    lc = line(db, s, t, 1)
    tid, aid, bid, cid = t.id, la.id, lb.id, lc.id
    bump_l(db, la)
    result = _by_ids(db, s.W1.id, [tid])
    # Then 1
    assert ids(result) == [aid, bid, cid]


# [claude] TRO-IT-09
@X2657
def test_tro_it_09__order_by_ends_with_line_id(db, s):
    """TRO-IT-09 — the query ends its ORDER BY with the line id.
    Rules: get_by_transfer_order_ids R3 [BUG-2657]."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    tid, w1 = t.id, s.W1.id
    db.expunge_all()
    with StatementRecorder(db, "transfer_order_items") as rec:
        idao.get_by_transfer_order_ids(db, workspace_id=w1, transfer_order_ids=[tid])
    # Then 1
    assert "line_number" in rec.order_part
    # Then 2
    assert rec.order_part.rstrip().endswith(
        "transfer_order_items.id"
    ) or rec.order_part.rstrip().endswith("transfer_order_items.id ASC")


# [claude] TRO-IT-10
def test_tro_it_10__writes_nothing_no_lock(db, s):
    """TRO-IT-10 — writes nothing and takes no lock.
    Rules: get_by_transfer_order_ids Side effects."""
    t = order(db, s, 1)
    k = line(db, s, t, 1)
    k.quantity = Decimal("9.00")
    p = line(db, s, t, 2, flush=False)
    with StatementRecorder(db, "transfer_order_items") as rec:
        result = _by_ids(db, s.W1.id, [t.id])
    # Then 1
    assert ids(result) == [k.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert k in db.dirty
    # Then 4
    assert len(db.dirty) == 1
    # Then 5
    assert rec.written == []
    # Then 6
    assert "FOR UPDATE" not in rec.sql


# =========================================================================== #
# TransferOrderItemDAO.get_by_id_and_workspace
# =========================================================================== #


# [claude] TRO-II-01
def test_tro_ii_01__returns_line(db, s):
    """TRO-II-01 — returns the asked line.
    Rules: TransferOrderItemDAO.get_by_id_and_workspace R1."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    k2 = line(db, s, t, 2)
    line(db, s, t, 3)
    result = idao.get_by_id_and_workspace(db, id=k2.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, TransferOrderItem)
    # Then 2
    assert result.id == k2.id


# [claude] TRO-II-02, II-03
@pytest.mark.parametrize(
    "other", [pytest.param(2, id="TRO-II-02"), pytest.param(0, id="TRO-II-03")]
)
def test_tro_ii_02_03__other_workspace_none(db, s, other):
    """TRO-II-02, II-03 — asked for W2 / W0, W1's line is None.
    Rules: TransferOrderItemDAO.get_by_id_and_workspace R1."""
    t = order(db, s, 1)
    k = line(db, s, t, 1)
    ws = {0: s.W0, 2: s.W2}[other]
    result = idao.get_by_id_and_workspace(db, id=k.id, workspace_id=ws.id)
    # Then 1
    assert result is None


# [claude] TRO-II-04
def test_tro_ii_04__unknown_id_none(db, s):
    """TRO-II-04 — an unknown id is None.
    Rules: TransferOrderItemDAO.get_by_id_and_workspace R1."""
    t = order(db, s, 1)
    line(db, s, t, 1)
    result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# get_pending_highlights_for_hub — Planned / Draft stage (BUG-2659, OQ-39)
# =========================================================================== #


# [claude] TRO-OQ39-01
def test_tro_oq39_01__route_with_line_planned(db, s):
    """TRO-OQ39-01 — a route with a line is planned and labelled "Planned".
    Rules: get_pending_highlights_for_hub R2, R2a, R3."""
    order(db, s, 1, planned=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 1
    # Then 2
    assert result["pending_planned"][0]["status_name"] == "Planned"
    # Then 3
    assert result["awaiting_setup_count"] == 0


# [claude] TRO-OQ39-02
@X2659
def test_tro_oq39_02__route_without_lines_is_draft(db, s):
    """TRO-OQ39-02 — a route with no lines is a Draft, awaiting setup.
    Rules: get_pending_highlights_for_hub R2a, R3 [BUG-2659]."""
    a = order(db, s, 1)  # no line
    result = _ph(db, s, **F())
    # Then 1
    assert result["awaiting_setup_count"] == 1
    # Then 2
    assert result["pending_planned_count"] == 0
    # Then 3
    assert hids(result["awaiting_setup"]) == [a.id]
    # Then 4
    assert result["awaiting_setup"][0]["status_name"] == "Draft"
    # Then 5
    assert result["pending_planned"] == []


# [claude] TRO-OQ39-03
def test_tro_oq39_03__source_id_zero_draft(db, s):
    """TRO-OQ39-03 — source id 0 is awaiting setup, labelled "Draft" in both lists.
    Rules: get_pending_highlights_for_hub R2, R2a, R3."""
    order(db, s, 1, source_location_id=0, planned=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 0
    # Then 2
    assert result["awaiting_setup_count"] == 1
    # Then 3
    assert result["awaiting_setup"][0]["status_name"] == "Draft"
    # Then 4
    assert result["oldest_drafts"][0]["status_name"] == "Draft"


# [claude] TRO-OQ39-04, OQ39-05, OQ39-06, OQ39-07
@pytest.mark.parametrize(
    "cols",
    [
        pytest.param({"destination_location_id": 0}, id="TRO-OQ39-04"),
        pytest.param({"source_location_id": -1}, id="TRO-OQ39-05"),
        pytest.param({"source_location_type": ""}, id="TRO-OQ39-06"),
        pytest.param({"destination_location_type": ""}, id="TRO-OQ39-07"),
    ],
)
def test_tro_oq39_04_to_07__undefined_route_awaiting_setup(db, s, cols):
    """TRO-OQ39-04 … OQ39-07 — destination id 0, a negative source id, an empty source type or
    an empty destination type is awaiting setup, even with a line.
    Rules: get_pending_highlights_for_hub R2, R2a."""
    order(db, s, 1, planned=True, **cols)
    result = _ph(db, s, **F())
    # Then 1
    assert result["awaiting_setup_count"] == 1
    # Then 2
    assert result["pending_planned_count"] == 0


# [claude] TRO-OQ39-08, OQ39-09
@pytest.mark.parametrize(
    "cols",
    [
        pytest.param(
            {
                "source_location_type": "warehouse",
                "source_location_id": 1,
                "destination_location_type": "warehouse",
                "destination_location_id": 1,
            },
            id="TRO-OQ39-08",
        ),
        pytest.param({"destination_location_type": " "}, id="TRO-OQ39-09"),
    ],
)
def test_tro_oq39_08_09__defined_route(db, s, cols):
    """TRO-OQ39-08, OQ39-09 — ids of 1 with any non-empty types, and a one-space type, are a
    defined route.
    Rules: get_pending_highlights_for_hub R2, R2a."""
    order(db, s, 1, planned=True, **cols)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 1
    # Then 2
    assert result["awaiting_setup_count"] == 0


# [claude] TRO-OQ39-10
def test_tro_oq39_10__label_ignores_stored_status(db, s):
    """TRO-OQ39-10 — the label ignores the stored status.
    Rules: get_pending_highlights_for_hub R3."""
    order(db, s, 1, planned=True)  # stored status S1, named "Draft"
    order(db, s, 2, draft=True, current_status_id=s.SP.id)  # named "Planned"
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned"][0]["status_name"] == "Planned"
    # Then 2
    assert result["awaiting_setup"][0]["status_name"] == "Draft"
    # Then 3
    assert result["oldest_drafts"][0]["status_name"] == "Draft"


# [claude] TRO-OQ39-11
def test_tro_oq39_11__counts_add_up(db, s):
    """TRO-OQ39-11 — the two counts add up to the open orders, a route without a line included.
    Rules: get_pending_highlights_for_hub R1, R2a."""
    order(db, s, 1)  # no line
    order(db, s, 2, planned=True)
    order(db, s, 3, draft=True)
    order(db, s, 4, completed=True, planned=True)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] + result["awaiting_setup_count"] == 3


# [claude] TRO-OQ39-12
@X2659
def test_tro_oq39_12__oldest_drafts_include_route_without_line(db, s):
    """TRO-OQ39-12 — oldest_drafts includes an older route without a line, oldest first.
    Rules: get_pending_highlights_for_hub R5, R6 [BUG-2659]."""
    a = order(db, s, 1)  # no line
    r = order(db, s, 2, draft=True)
    result = _ph(db, s, **F())
    # Then 1
    assert hids(result["oldest_drafts"]) == [a.id, r.id]
    # Then 2
    assert result["oldest_drafts"][0]["status_name"] == "Draft"


# [claude] TRO-OQ39-13
@X2659
def test_tro_oq39_13__route_without_line_not_pending_planned(db, s):
    """TRO-OQ39-13 — beside a planned order, a route without a line is left out of pending_planned.
    Rules: get_pending_highlights_for_hub R2a, R4 [BUG-2659]."""
    p = order(db, s, 1, planned=True)
    a = order(db, s, 2)  # no line
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] == 1
    # Then 2
    assert hids(result["pending_planned"]) == [p.id]
    # Then 3
    assert hids(result["awaiting_setup"]) == [a.id]


def _foreign_line(db, s, t):
    """TransferOrderItem(W2, T, line 1, I2, 2.00) — invalid cross-workspace data, on purpose."""
    return _add(
        db,
        TransferOrderItem(
            workspace_id=s.W2.id,
            transfer_order_id=t.id,
            line_number=1,
            item_id=s.I2.id,
            quantity=Decimal("2.00"),
        ),
    )


# [claude] TRO-OQ39-14
@X2659
def test_tro_oq39_14__only_foreign_line_is_draft(db, s):
    """TRO-OQ39-14 — a route whose only line belongs to another workspace is a Draft.
    Rules: get_pending_highlights_for_hub R2a [BUG-2659]; HR-16."""
    a = order(db, s, 1)
    _foreign_line(db, s, a)
    result = _ph(db, s, **F())
    # Then 1
    assert result["pending_planned_count"] + result["awaiting_setup_count"] == 1
    # Then 2
    assert result["awaiting_setup_count"] == 1
    # Then 3
    assert result["pending_planned_count"] == 0
    # Then 4
    assert hids(result["awaiting_setup"]) == [a.id]
    # Then 5
    assert result["pending_planned"] == []


# =========================================================================== #
# _apply_transfer_order_hub_filters — status ticks by stage (BUG-2660, OQ-40)
# =========================================================================== #


def _status(db, s, name):
    """ST = Status(workspace_id=W1.id, name=<name>, comment="stage")."""
    return _add(db, Status(workspace_id=s.W1.id, name=name, comment="stage"))


# [claude] TRO-OQ40-01
@X2660
def test_tro_oq40_01__planned_tick_keeps_planned_stage(db, s):
    """TRO-OQ40-01 — ticking Planned keeps the Planned orders, not the one stored as Planned.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    a = order(db, s, 1, planned=True)  # stored S1
    order(db, s, 2, draft=True, current_status_id=s.SP.id)
    c = order(db, s, 3, current_status_id=s.SC.id, planned=True)
    result = _list(db, s.W1, **F(status_ids=[s.SP.id]))
    # Then 1
    assert ids(result) == [c.id, a.id]


# [claude] TRO-OQ40-02
@X2660
def test_tro_oq40_02__draft_and_planned_ticks(db, s):
    """TRO-OQ40-02 — ticking Draft and Planned keeps both stages, a completed order is left out.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    a = order(db, s, 1, current_status_id=s.SC.id, planned=True)
    b = order(db, s, 2, draft=True, current_status_id=s.SC.id)
    order(db, s, 3, completed=True, planned=True)  # stored S1
    result = _list(db, s.W1, exclude_complete=False, **F(status_ids=[s.S1.id, s.SP.id]))
    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] TRO-OQ40-03
def test_tro_oq40_03__unknown_status_id_nothing(db, s):
    """TRO-OQ40-03 — an id of no status matches nothing.
    Rules: _apply_transfer_order_hub_filters R4a."""
    order(db, s, 1, planned=True)
    order(db, s, 2, draft=True)
    result = _list(db, s.W1, **F(status_ids=[MISSING]))
    # Then 1
    assert result == []


# [claude] TRO-OQ40-04
def test_tro_oq40_04__w2_draft_status_nothing_in_w1(db, s):
    """TRO-OQ40-04 — the later workspace's "Draft" status matches nothing in W1, though W1 has a draft.
    Rules: _apply_transfer_order_hub_filters R4a, R1."""
    order(db, s, 1, draft=True)
    order(db, s, 2, ws=2, draft=True)
    result = _list(db, s.W1, **F(status_ids=[s.S2.id]))
    # Then 1
    assert result == []


# [claude] TRO-OQ40-05
@X2660
def test_tro_oq40_05__completed_tick_finds_completed(db, s):
    """TRO-OQ40-05 — ticking Completed finds a completed order stored as Draft.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    a = order(db, s, 1, completed=True)  # stored S1
    result = _list(db, s.W1, exclude_complete=False, **F(status_ids=[s.SC.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-06
@X2660
def test_tro_oq40_06__draft_tick_by_stage(db, s):
    """TRO-OQ40-06 — ticking Draft leaves out a completed order stored as Draft and keeps a
    draft stored as Completed.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    order(db, s, 1, completed=True)  # stored S1
    b = order(db, s, 2, draft=True, current_status_id=s.SC.id)
    result = _list(db, s.W1, exclude_complete=False, **F(status_ids=[s.S1.id]))
    # Then 1
    assert ids(result) == [b.id]


# [claude] TRO-OQ40-07
@X2660
def test_tro_oq40_07__count_by_stage(db, s):
    """TRO-OQ40-07 — the count keeps orders by stage.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660], count_for_hub R1."""
    order(db, s, 1, planned=True)  # stored S1
    order(db, s, 2, draft=True, current_status_id=s.SP.id)
    order(db, s, 3, planned=True)  # stored S1
    result = dao.count_for_hub(db, workspace_id=s.W1.id, **F(status_ids=[s.SP.id]))
    # Then 1
    assert result == 2


# [claude] TRO-OQ40-08
@X2660
def test_tro_oq40_08__kpi_by_stage(db, s):
    """TRO-OQ40-08 — the KPI totals keep orders by stage.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660], aggregate_hub_stats R1."""
    order(db, s, 1, completed=True, planned=True)  # stored S1
    order(db, s, 2, planned=True)  # stored S1
    order(db, s, 3, draft=True, current_status_id=s.SP.id)
    result = dao.aggregate_hub_stats(
        db,
        workspace_id=s.W1.id,
        exclude_complete=False,
        **F(status_ids=[s.SP.id, s.SC.id]),
    )
    # Then 1
    assert result == (2, 1, 1)


# [claude] TRO-OQ40-09, OQ40-10
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(" planned ", id="TRO-OQ40-09"),
        pytest.param("PLANNED", id="TRO-OQ40-10"),
    ],
)
@X2660
def test_tro_oq40_09_10__planned_name_trimmed_any_case(db, s, name):
    """TRO-OQ40-09, OQ40-10 — a status named " planned " / "PLANNED" ticks the Planned stage.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    st = _status(db, s, name)
    a = order(db, s, 1, planned=True)  # stored S1
    order(db, s, 2, draft=True)
    result = _list(db, s.W1, **F(status_ids=[st.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-11, OQ40-12, OQ40-13
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Review", id="TRO-OQ40-11"),
        pytest.param("Plan", id="TRO-OQ40-12"),
        pytest.param("Plann_d", id="TRO-OQ40-13"),
    ],
)
@X2660
def test_tro_oq40_11_to_13__other_name_matches_nothing(db, s, name):
    """TRO-OQ40-11 … OQ40-13 — a status of another name ("Review"), a part of a stage name
    ("Plan") or an underscore name ("Plann_d") matches nothing, even for the order stored with it.
    Rules: _apply_transfer_order_hub_filters R4a [BUG-2660]."""
    st = _status(db, s, name)
    order(db, s, 1, current_status_id=st.id, planned=True)
    result = _list(db, s.W1, **F(status_ids=[st.id]))
    # Then 1
    assert result == []


# [claude] TRO-OQ40-14
@X2660
def test_tro_oq40_14__completed_tick_default_exclude(db, s):
    """TRO-OQ40-14 — ticking Completed with the default exclude_complete gives nothing.
    Rules: _apply_transfer_order_hub_filters R4a, R7 [BUG-2660]."""
    order(db, s, 1, completed=True, planned=True)  # stored S1
    order(db, s, 2, current_status_id=s.SC.id, planned=True)
    result = _list(db, s.W1, **F(status_ids=[s.SC.id]))
    # Then 1
    assert result == []


# [claude] TRO-OQ40-15
@X2660
def test_tro_oq40_15__route_without_line_draft_tick(db, s):
    """TRO-OQ40-15 — a route without a line is in the Draft stage for the tick.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]."""
    a = order(db, s, 1, current_status_id=s.SP.id)  # no line
    order(db, s, 2, planned=True)  # stored S1
    result = _list(db, s.W1, **F(status_ids=[s.S1.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-16
def test_tro_oq40_16__draft_tick_draft_stored_draft(db, s):
    """TRO-OQ40-16 — ticking Draft keeps a draft stored as Draft and leaves out a planned order
    stored as Planned.
    Rules: _apply_transfer_order_hub_filters R4."""
    a = order(db, s, 1, draft=True)  # stored S1
    order(db, s, 2, current_status_id=s.SP.id, planned=True)
    result = _list(db, s.W1, **F(status_ids=[s.S1.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-17
def test_tro_oq40_17__w0_draft_status_nothing_in_w1(db, s):
    """TRO-OQ40-17 — the earlier workspace's "Draft" status matches nothing in W1, though W1 has a draft.
    Rules: _apply_transfer_order_hub_filters R4a, R1."""
    order(db, s, 1, ws=0, draft=True)
    order(db, s, 2, draft=True)
    result = _list(db, s.W1, **F(status_ids=[s.S0.id]))
    # Then 1
    assert result == []


# [claude] TRO-OQ40-18
@X2660
def test_tro_oq40_18__unknown_id_beside_planned(db, s):
    """TRO-OQ40-18 — an unknown id beside the Planned tick does not empty the result.
    Rules: _apply_transfer_order_hub_filters R4, R4a [BUG-2660]."""
    a = order(db, s, 1, planned=True)  # stored S1
    result = _list(db, s.W1, **F(status_ids=[MISSING, s.SP.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-19
@X2660
def test_tro_oq40_19__planned_tick_w1_only(db, s):
    """TRO-OQ40-19 — ticking Planned in W1 keeps W1's planned order, not W0's or W2's.
    Rules: _apply_transfer_order_hub_filters R4, R1 [BUG-2660]."""
    order(db, s, 1, ws=0, planned=True)
    a = order(db, s, 2, planned=True)  # stored S1
    order(db, s, 3, ws=2, planned=True)
    result = _list(db, s.W1, **F(status_ids=[s.SP.id]))
    # Then 1
    assert ids(result) == [a.id]


# [claude] TRO-OQ40-20
@X2660
def test_tro_oq40_20__only_foreign_line_draft_tick(db, s):
    """TRO-OQ40-20 — a route whose only line belongs to another workspace is in the Draft stage
    for the tick.
    Rules: _apply_transfer_order_hub_filters R4 [BUG-2660]; HR-16."""
    a = order(db, s, 1, current_status_id=s.SP.id)
    _foreign_line(db, s, a)
    order(db, s, 2, planned=True)  # stored S1
    result = _list(db, s.W1, **F(status_ids=[s.S1.id]))
    # Then 1
    assert ids(result) == [a.id]
