# ruff: noqa: DTZ001, RUF059, SIM117, FURB157, C408
# (naive datetimes are prescribed by the Conventions; setup helpers return every
# row of a Given and not every test reads each; POST(...) + pytest.raises are kept
# as two `with` blocks so the "# Then 1" comment sits on the raises line;
# Decimal("…") literals are the cards' own; dict(k=v) mirrors the cards' column lists.)
"""Unit tests for app/managers/transfer_order_manager.py.

Implements tests/unit/managers/transfer_order_manager.cases.md (revision 2c),
one test per case. Real Postgres session (`db` fixture, rolled back).
Externals (Conventions): `utcnow` patched to NOW in every test; the transfer
number DAO call patched to a unique TNUM in every test (NUMP); MC cards patch
`post_transfer_order_inventory` as `pm`.
"""
import inspect
import os
import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect

from app.managers.transfer_order_manager import transfer_order_manager as M
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.transfer_order_item import TransferOrderItem
from app.models.workspace_member import WorkspaceMember
from app.schemas.transfer_order import (
    TransferOrderCreate,
    TransferOrderItemCreate,
    TransferOrderItemUpdate,
    TransferOrderUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

MISSING = 999999999
DONE = datetime(2026, 3, 20, 9, 0)
TOLD = datetime(2026, 3, 22, 8, 0)
NOW = datetime(2026, 3, 25, 12, 0)


def GN(s):
    return f"{s}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def TS(h):
    return datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)


def naive(v):
    """A stamp `== X` compares the re-read value with any tzinfo removed."""
    return v.replace(tzinfo=None) if v is not None else None


def xfail(*bugs):
    return pytest.mark.xfail(strict=True, reason="; ".join(bugs))


# --------------------------------------------------------------------------- #
# Conventions -> externals (every test)
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def clock():
    """`app.managers.transfer_order_manager.utcnow` -> NOW."""
    with patch("app.managers.transfer_order_manager.utcnow", return_value=NOW) as m:
        yield m


@pytest.fixture(autouse=True)
def TNUM():
    """NUMP: the DAO's get_next_number returns a unique TNUM (made once per test).

    The card's dotted target `app.managers.transfer_order_manager.to_dao` is the
    manager instance's `to_dao` attribute (the module has no `to_dao` name), so
    the same DAO object is patched with patch.object.
    """
    tnum = GN("TR-NEW")
    with patch.object(M.to_dao, "get_next_number", return_value=tnum):
        yield tnum


ERR = HTTPException(status_code=400, detail="Insufficient stock for Motor")


@contextmanager
def POST(n=None, err=None):
    """MC cards: `pm` = patched post_transfer_order_inventory (POST(n) / POSTERR)."""
    kw = {"side_effect": err} if err is not None else {"return_value": n}
    with patch("app.managers.transfer_order_manager.post_transfer_order_inventory", **kw) as pm:
        yield pm


def posted(pm):
    return inspect.signature(
        lambda session, to, items, workspace_id, user_id: None
    ).bind(*pm.call_args.args, **pm.call_args.kwargs).arguments


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def S(db):
    s = SimpleNamespace()
    s.W0, s.W1, s.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    s.U1 = make_profile(db, name="Karim Ahmed")
    s.U2 = make_profile(db, name="Nadia Islam")
    s.U3 = make_profile(db, name="Rahim Uddin")
    s.U4 = make_profile(db, name="Sumi Akter")
    s.U5 = make_profile(db, name="Tanvir Hasan")
    for u, ws, st, pos in (
        (s.U1, s.W1, "active", "Store Manager"), (s.U2, s.W1, "active", "Factory Head"),
        (s.U3, s.W1, "active", None), (s.U4, s.W1, "inactive", "Clerk"), (s.U5, s.W2, "active", "Boss"),
    ):
        _add(db, WorkspaceMember(workspace_id=ws.id, user_id=u.id, role="member", status=st, position=pos))
    s.S0 = _add(db, Status(workspace_id=s.W0.id, name="Open", comment="stage"))
    s.S1 = _add(db, Status(workspace_id=s.W1.id, name="Open", comment="stage"))
    s.S2 = _add(db, Status(workspace_id=s.W2.id, name="Open", comment="stage"))
    s.F0 = _add(db, Factory(workspace_id=s.W0.id, name="Zulu Depot", abbreviation="ZD"))
    s.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Alpha Works", abbreviation="AW"))
    s.FB = _add(db, Factory(workspace_id=s.W1.id, name="Bravo Yard", abbreviation="BY"))
    s.FD = _add(db, Factory(workspace_id=s.W1.id, name="Old Shed", abbreviation="OS",
                            is_deleted=True, deleted_at=TS(0), deleted_by=s.U1.id))
    s.F2 = _add(db, Factory(workspace_id=s.W2.id, name="Yankee Store", abbreviation="YS"))
    s.M1 = _add(db, Machine(id=XID(1), workspace_id=s.W1.id, factory_id=s.F1.id, name="Press Kilo"))
    s.MD = _add(db, Machine(id=XID(2), workspace_id=s.W1.id, factory_id=s.F1.id, name="Old Lathe",
                            is_deleted=True, is_active=False, deleted_at=TS(0), deleted_by=s.U1.id))
    s.M0 = _add(db, Machine(id=XID(3), workspace_id=s.W0.id, factory_id=s.F0.id, name="Drill Oscar"))
    s.M2 = _add(db, Machine(id=XID(4), workspace_id=s.W2.id, factory_id=s.F2.id, name="Saw Romeo"))
    s.PJ1 = _add(db, Project(workspace_id=s.W1.id, factory_id=s.F1.id, name="Tower One", description="Main"))
    s.C1 = _add(db, ProjectComponent(id=XID(5), workspace_id=s.W1.id, project_id=s.PJ1.id, name="Span Delta"))
    s.PJ2 = _add(db, Project(workspace_id=s.W2.id, factory_id=s.F2.id, name="Tower Nine", description="Main"))
    s.C2 = _add(db, ProjectComponent(id=XID(6), workspace_id=s.W2.id, project_id=s.PJ2.id, name="Pier Sierra"))
    s.I1 = _add(db, Item(workspace_id=s.W1.id, name="Motor", name_normalized="motor", unit="pcs"))
    s.I2 = _add(db, Item(workspace_id=s.W1.id, name="Bearing", name_normalized="bearing", unit="pcs"))
    s.IN = _add(db, Item(workspace_id=s.W1.id, name="Nut", name_normalized="nut", unit="pcs"))
    s.I0 = _add(db, Item(workspace_id=s.W0.id, name="Gear", name_normalized="gear", unit="pcs"))
    s.IX = _add(db, Item(workspace_id=s.W2.id, name="Valve", name_normalized="valve", unit="pcs"))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def order(db, S, which="O", *, completed=False, **over):
    """order O / O2 / O0 / O9; `completed=True` = completed_at DONE, completed_by U1."""
    if which in ("O", "O2"):
        f = dict(workspace_id=S.W1.id, transfer_number=GN("TR-" + which),
                 source_location_type="storage", source_location_id=S.F1.id,
                 destination_location_type="storage", destination_location_id=S.FB.id,
                 current_status_id=S.S1.id)
    elif which == "O0":
        f = dict(workspace_id=S.W0.id, transfer_number=GN("TR-O0"),
                 source_location_type="storage", source_location_id=S.F0.id,
                 destination_location_type="machine", destination_location_id=S.M0.id,
                 current_status_id=S.S0.id)
    elif which == "O9":
        f = dict(workspace_id=S.W2.id, transfer_number=GN("TR-O9"),
                 source_location_type="storage", source_location_id=S.F2.id,
                 destination_location_type="machine", destination_location_id=S.M2.id,
                 current_status_id=S.S2.id)
    else:
        raise ValueError(which)
    f.update(created_by=S.U1.id, description="Old text", created_at=TS(1))
    if completed:
        f.update(completed_at=DONE, completed_by=S.U1.id)
    f.update(over)
    return _add(db, TransferOrder(**f))


def line(db, S, T, k, **over):
    """line(T, k): I1 on W1 orders, I0 on O0, IX on O9; quantity 10.00."""
    item = {S.W1.id: S.I1, S.W0.id: S.I0, S.W2.id: S.IX}[T.workspace_id]
    f = dict(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=k,
             item_id=item.id, quantity=Decimal("10.00"))
    f.update(over)
    return _add(db, TransferOrderItem(**f))


def apr(db, S, T, U, h, *, approved=False, **over):
    """apr(T, U, h); `approved=True` = approved True, approved_at TOLD."""
    f = dict(workspace_id=T.workspace_id, transfer_order_id=T.id, user_id=U.id,
             assigned_by=S.U1.id, approved=False, approved_at=None, assigned_at=TS(h))
    if approved:
        f.update(approved=True, approved_at=TOLD)
    f.update(over)
    return _add(db, TransferOrderApprover(**f))


def ev(db, T, type_, h, **over):
    f = dict(workspace_id=T.workspace_id, transfer_order_id=T.id, event_type=type_,
             description="Logged", created_at=TS(h))
    f.update(over)
    return _add(db, TransferOrderEvent(**f))


def RT(**over):
    f = dict(source_location_type="storage", source_location_id=11,
             destination_location_type="machine", destination_location_id=22)
    f.update(over)
    return TransferOrder(**f)


# --------------------------------------------------------------------------- #
# Conventions -> requests
# --------------------------------------------------------------------------- #

def CREATE(S, **over):
    f = dict(source_location_type="storage", source_location_id=S.F1.id,
             destination_location_type="storage", destination_location_id=S.FB.id,
             current_status_id=S.S1.id, description="Monthly move")
    f.update(over)
    return TransferOrderCreate(**f)


_NO = object()


def ITEM(I, q, notes=_NO):
    if notes is _NO:
        return TransferOrderItemCreate(item_id=I.id, quantity=Decimal(q))
    return TransferOrderItemCreate(item_id=I.id, quantity=Decimal(q), notes=notes)


def UPD(**k):
    return TransferOrderUpdate(**k)


def IU(**k):
    return TransferOrderItemUpdate(**k)


def CH(f, l, a, b):
    return {"field": f, "label": l, "from_value": a, "to_value": b}


def DEL(db, S, to_id):
    kw = dict(to_id=to_id, workspace_id=S.W1.id)
    if "user_id" in inspect.signature(M.delete_transfer_order).parameters:
        kw["user_id"] = S.U2.id
    return M.delete_transfer_order(db, **kw)


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def ids(result):
    return [r.id for r in result]


def reread(db, model, id_):
    db.flush()
    db.expire_all()
    return db.execute(select(model).where(model.id == id_)).scalars().first()


def _cols(row):
    return {a.key: getattr(row, a.key) for a in sa_inspect(type(row)).column_attrs}


def snap(db, row):
    """Snapshot of every column of `row` after the last Given line (from the database)."""
    return _cols(reread(db, type(row), row.id))


def unchanged(db, row, before):
    fresh = reread(db, type(row), before["id"])
    assert fresh is not None
    assert _cols(fresh) == before


def session_clean(db):
    assert not db.new
    assert not db.dirty
    assert not db.deleted


_COUNT_TABLES = ("transfer_orders", "transfer_order_items", "transfer_order_approvers",
                 "transfer_order_events", "workspace_audit_logs", "inventory_ledger")


def counts(db):
    """`nothing written` = these row counts (all workspaces) are unchanged."""
    db.flush()
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in _COUNT_TABLES}


def count_where(db, model, **eq):
    db.flush()
    q = select(func.count()).select_from(model)
    for k, v in eq.items():
        q = q.where(getattr(model, k) == v)
    return db.execute(q).scalar()


def ev_rows(db, to_id):
    db.flush()
    db.expire_all()
    return db.execute(select(TransferOrderEvent).where(TransferOrderEvent.transfer_order_id == to_id)
                      .order_by(TransferOrderEvent.id)).scalars().all()


def evs(db, to_id):
    return [(e.event_type, e.description, e.performed_by, e.metadata_json) for e in ev_rows(db, to_id)]


def SUMMARY(db, to_id):
    return M.approval_summary(db, reread(db, TransferOrder, to_id))


def AUDIT(db, to_id):
    return db.execute(text(
        "SELECT workspace_id, user_id, action, resource_type, resource_id, metadata "
        "FROM workspace_audit_logs WHERE resource_type = 'transfer_order' AND resource_id = :i"
    ), {"i": to_id}).all()


def lines_of(db, to_id):
    db.flush()
    db.expire_all()
    return db.execute(select(TransferOrderItem).where(TransferOrderItem.transfer_order_id == to_id)
                      .order_by(TransferOrderItem.line_number)).scalars().all()


def approvers_of(db, to_id):
    db.flush()
    db.expire_all()
    return db.execute(select(TransferOrderApprover).where(TransferOrderApprover.transfer_order_id == to_id)
                      .order_by(TransferOrderApprover.id)).scalars().all()


class Recorder:
    """Statement recorder: a before_cursor_execute listener from the start of the When."""

    def __init__(self, db):
        self.engine = db.get_bind().engine
        self.statements = []

    def _on(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)
        return False

    @property
    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    @property
    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sel(self, table):
        pat = re.compile(r"\bFROM\b.*\b" + re.escape(table) + r"\b", re.DOTALL | re.IGNORECASE)
        return [s for s in self.selects if pat.search(s)]

    def no_lock(self):
        return not any("FOR UPDATE" in s.upper() for s in self.selects)

    def locks_before_first_write(self, table):
        first_write = next((i for i, s in enumerate(self.statements) if s in self.written), len(self.statements))
        for i, s in enumerate(self.statements):
            if i >= first_write:
                break
            u = s.upper()
            norm = " ".join(s.split())
            # exact clause FOR UPDATE OF <table> (spec G13)
            if (s in self.sel(table) and norm.endswith(f"FOR UPDATE OF {table}")
                    and "SKIP LOCKED" not in u and "NOWAIT" not in u):
                return True
        return False


# =========================================================================== #
# _is_completed
# =========================================================================== #

def test_tom_ic_01__set_stamp_is_completed():
    """TOM-IC-01 — a set completion stamp means completed.
    Rules: _is_completed R1."""
    T = TransferOrder(completed_at=DONE)
    result = M._is_completed(T)
    # Then 1
    assert result is True


def test_tom_ic_02__no_stamp_not_completed():
    """TOM-IC-02 — no completion stamp means not completed.
    Rules: _is_completed R1."""
    T = TransferOrder(completed_at=None)
    result = M._is_completed(T)
    # Then 1
    assert result is False


def test_tom_ic_03__old_stamp_counts():
    """TOM-IC-03 — any stamp counts, even a very old one.
    Rules: _is_completed R1."""
    T = TransferOrder(completed_at=datetime(1970, 1, 1, 0, 0))
    result = M._is_completed(T)
    # Then 1
    assert result is True


# =========================================================================== #
# _route_defined
# =========================================================================== #

@pytest.mark.parametrize("over, expected", [
    pytest.param({}, True, id="TOM-RD-01"),
    pytest.param({"source_location_type": ""}, False, id="TOM-RD-02"),
    pytest.param({"destination_location_type": None}, False, id="TOM-RD-03"),
    pytest.param({"source_location_id": 0}, False, id="TOM-RD-04"),
    pytest.param({"destination_location_id": None}, False, id="TOM-RD-05"),
])
def test_tom_rd__route_defined(over, expected):
    """TOM-RD-01..05 — all four route parts must be truthy.
    Rules: _route_defined R1."""
    T = RT(**over)
    result = M._route_defined(T)
    # Then 1
    assert result is expected


# =========================================================================== #
# _route_valid
# =========================================================================== #

@pytest.mark.parametrize("st, si, dt, di, expected", [
    pytest.param("storage", 11, "machine", 0, False, id="TOM-RVL-01"),
    pytest.param("storage", 11, "storage", 11, False, id="TOM-RVL-02"),
    pytest.param("storage", 11, "damaged", 11, True, id="TOM-RVL-03"),
    pytest.param("storage", 11, "Storage", 11, True, id="TOM-RVL-04"),
    pytest.param("storage", 11, "storage", 12, True, id="TOM-RVL-05"),
])
def test_tom_rvl__route_valid(st, si, dt, di, expected):
    """TOM-RVL-01..05 — undefined or same type+id is invalid; comparison exact.
    Rules: _route_valid R1, R2."""
    T = TransferOrder(source_location_type=st, source_location_id=si,
                      destination_location_type=dt, destination_location_id=di)
    result = M._route_valid(T)
    # Then 1
    assert result is expected


# =========================================================================== #
# _order_items
# =========================================================================== #

def test_tom_oi_01__by_line_number(db, S):
    """TOM-OI-01 — lines come by line number, not by insert order.
    Rules: _order_items R1."""
    O = order(db, S)
    L3 = line(db, S, O, 3)
    L1 = line(db, S, O, 1)
    L2 = line(db, S, O, 2)
    result = M._order_items(db, O, S.W1.id)
    # Then 1
    assert ids(result) == [L1.id, L2.id, L3.id]


def test_tom_oi_02__other_workspaces_and_orders_excluded(db, S):
    """TOM-OI-02 — lines under other workspaces and of another order are not returned.
    Rules: _order_items R1."""
    O = order(db, S)
    O2 = order(db, S, "O2")
    line(db, S, O, 1, workspace_id=S.W0.id, item_id=S.I0.id)
    L2 = line(db, S, O, 2)
    line(db, S, O, 3, workspace_id=S.W2.id, item_id=S.IX.id)
    line(db, S, O2, 1)
    result = M._order_items(db, O, S.W1.id)
    # Then 1
    assert ids(result) == [L2.id]


def test_tom_oi_03__no_lines_empty(db, S):
    """TOM-OI-03 — an order with no lines gives an empty list.
    Rules: _order_items R1."""
    O = order(db, S)
    result = M._order_items(db, O, S.W1.id)
    # Then 1
    assert list(result) == []


# =========================================================================== #
# _ready_for_approval
# =========================================================================== #

def test_tom_rfa_01__valid_route_and_line_ready(db, S):
    """TOM-RFA-01 — a valid route and one line is ready.
    Rules: _ready_for_approval R1."""
    O = order(db, S)
    line(db, S, O, 1)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is True


def test_tom_rfa_02__no_line_not_ready(db, S):
    """TOM-RFA-02 — no line is not ready.
    Rules: _ready_for_approval R1."""
    O = order(db, S)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is False


def test_tom_rfa_03__same_route_not_ready(db, S):
    """TOM-RFA-03 — a route with source = destination is not ready.
    Rules: _ready_for_approval R1."""
    O = order(db, S, destination_location_id=S.F1.id)
    line(db, S, O, 1)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is False


def test_tom_rfa_04__undefined_route_not_ready(db, S):
    """TOM-RFA-04 — an undefined route is not ready.
    Rules: _ready_for_approval R1."""
    O = order(db, S, destination_location_id=0)
    line(db, S, O, 1)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is False


def test_tom_rfa_05__foreign_line_does_not_count(db, S):
    """TOM-RFA-05 — a line stored under another workspace does not count.
    Rules: _ready_for_approval R1."""
    O = order(db, S)
    line(db, S, O, 1, workspace_id=S.W2.id, item_id=S.IX.id)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is False


def test_tom_rfa_06__approvals_not_looked_at(db, S):
    """TOM-RFA-06 — approvals are not looked at.
    Rules: _ready_for_approval R1."""
    O = order(db, S, required_approvals=5)
    line(db, S, O, 1)
    apr(db, S, O, S.U1, 1)
    result = M._ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is True


# =========================================================================== #
# _validate_ready_for_approval
# =========================================================================== #

def test_tom_vra_01__undefined_route_first(db, S):
    """TOM-VRA-01 — an undefined route is refused first.
    Rules: _validate_ready_for_approval R1, R4."""
    O = order(db, S, destination_location_id=0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ready_for_approval(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Set source and destination before approving"


def test_tom_vra_02__same_route_refused(db, S):
    """TOM-VRA-02 — source = destination is refused.
    Rules: _validate_ready_for_approval R2."""
    O = order(db, S, destination_location_id=S.F1.id)
    line(db, S, O, 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ready_for_approval(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Source and destination cannot be the same"


def test_tom_vra_03__no_line_refused(db, S):
    """TOM-VRA-03 — no line is refused.
    Rules: _validate_ready_for_approval R3."""
    O = order(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ready_for_approval(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Add at least one item before approving"


def test_tom_vra_04__route_message_wins(db, S):
    """TOM-VRA-04 — same route and no line: the route message wins.
    Rules: _validate_ready_for_approval R4."""
    O = order(db, S, destination_location_id=S.F1.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._validate_ready_for_approval(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Source and destination cannot be the same"


def test_tom_vra_05__ready_passes(db, S):
    """TOM-VRA-05 — a ready order passes.
    Rules: _validate_ready_for_approval R4."""
    O = order(db, S)
    line(db, S, O, 1)
    result = M._validate_ready_for_approval(db, O, S.W1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# _has_any_approval
# =========================================================================== #

def test_tom_haa_01__one_approved_of_two(db, S):
    """TOM-HAA-01 — one approved approver among two.
    Rules: _has_any_approval R1."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U2, 2, approved=True)
    result = M._has_any_approval(db, O)
    # Then 1
    assert result is True


def test_tom_haa_02__none_approved(db, S):
    """TOM-HAA-02 — approvers but none approved.
    Rules: _has_any_approval R1."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U2, 2)
    result = M._has_any_approval(db, O)
    # Then 1
    assert result is False


def test_tom_haa_03__no_approvers(db, S):
    """TOM-HAA-03 — no approvers.
    Rules: _has_any_approval R1."""
    O = order(db, S)
    result = M._has_any_approval(db, O)
    # Then 1
    assert result is False


def test_tom_haa_04__foreign_approved_rows_ignored(db, S):
    """TOM-HAA-04 — approved rows stored under other workspaces do not count.
    Rules: _has_any_approval R1."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U3, 2, workspace_id=S.W0.id, approved=True)
    apr(db, S, O, S.U2, 3, workspace_id=S.W2.id, approved=True)
    result = M._has_any_approval(db, O)
    # Then 1
    assert result is False


def test_tom_haa_05__other_order_approval_ignored(db, S):
    """TOM-HAA-05 — an approval on another order does not count.
    Rules: _has_any_approval R1."""
    O = order(db, S)
    O2 = order(db, S, "O2")
    apr(db, S, O, S.U1, 1)
    apr(db, S, O2, S.U1, 2, approved=True)
    result = M._has_any_approval(db, O)
    # Then 1
    assert result is False


# =========================================================================== #
# _format_scalar_value
# =========================================================================== #

@pytest.mark.parametrize("field, value, expected", [
    pytest.param("description", None, "—", id="TOM-FSV-01"),
    pytest.param("description", date(2026, 3, 4), "2026-03-04", id="TOM-FSV-02"),
    pytest.param("description", datetime(2026, 3, 4, 9, 0), "2026-03-04T09:00:00", id="TOM-FSV-03"),
    pytest.param("quantity", Decimal("5.00"), "5", id="TOM-FSV-04"),
    pytest.param("quantity", Decimal("100.00"), "100", id="TOM-FSV-05"),
    pytest.param("quantity", Decimal("2.50"), "2.5", id="TOM-FSV-06"),
    pytest.param("description", "  Ship Monday  ", "Ship Monday", id="TOM-FSV-07"),
    pytest.param("description", "   ", "—", id="TOM-FSV-08"),
    pytest.param("description", "", "—", id="TOM-FSV-09"),
    pytest.param("approved", True, "True", id="TOM-FSV-10"),
    pytest.param("required_approvals", None, "—", id="TOM-FSV-11"),
])
def test_tom_fsv__format_scalar_value(field, value, expected):
    """TOM-FSV-01..11 — scalar display text.
    Rules: _format_scalar_value R1-R5."""
    result = M._format_scalar_value(field, value)
    # Then 1
    assert result == expected


# =========================================================================== #
# _format_location_id
# =========================================================================== #

@pytest.mark.parametrize("ltype, key, expected", [
    pytest.param("storage", None, "—", id="TOM-FLI-01"),
    pytest.param("storage", "F1", "Alpha Works", id="TOM-FLI-02"),
    pytest.param("damaged", "FB", "Bravo Yard", id="TOM-FLI-03"),
    pytest.param("STORAGE", "F1", "Alpha Works", id="TOM-FLI-04"),
    pytest.param("storage", MISSING, "Factory #999999999", id="TOM-FLI-05"),
    pytest.param("storage", "FD", "Old Shed", id="TOM-FLI-06"),
    pytest.param("machine", "M1", "Press Kilo", id="TOM-FLI-07"),
    pytest.param("machine", MISSING, "Machine #999999999", id="TOM-FLI-08"),
    pytest.param("machine", "MD", "Old Lathe", id="TOM-FLI-09"),
    pytest.param("machine", "F1", "Machine #{F1}", id="TOM-FLI-10"),
    pytest.param("project", "C1", "Span Delta", id="TOM-FLI-11"),
    pytest.param("project", MISSING, "Project component #999999999", id="TOM-FLI-12"),
    pytest.param("warehouse", "F1", "#{F1}", id="TOM-FLI-13"),
    pytest.param(None, 5, "#5", id="TOM-FLI-14"),
    pytest.param("storage", "F0", "Factory #{F0}", id="TOM-FLI-15"),
    pytest.param("damaged", "F2", "Factory #{F2}", id="TOM-FLI-16"),
    pytest.param("machine", "M2", "Machine #{M2}", id="TOM-FLI-17"),
    pytest.param("machine", "M0", "Machine #{M0}", id="TOM-FLI-18"),
    pytest.param("project", "C2", "Project component #{C2}", id="TOM-FLI-19"),
])
def test_tom_fli__format_location_id(db, S, ltype, key, expected):
    """TOM-FLI-01..19 — location labels; deleted rows named; other workspaces never named.
    Rules: _format_location_id R1-R7."""
    loc_id = getattr(S, key).id if isinstance(key, str) else key
    want = expected.format(**{k: getattr(S, k).id for k in ("F0", "F1", "F2", "M0", "M2", "C2")})
    result = M._format_location_id(db, S.W1.id, ltype, loc_id)
    # Then 1
    assert result == want


# =========================================================================== #
# _format_field_value
# =========================================================================== #

@pytest.mark.parametrize("field, value, st, dt, expected", [
    pytest.param("source_location_type", "storage", "storage", "storage", "Storage", id="TOM-FFV-01"),
    pytest.param("destination_location_type", "machine", "storage", "storage", "Machine", id="TOM-FFV-02"),
    pytest.param("source_location_type", "damaged", "storage", "storage", "Damaged", id="TOM-FFV-03"),
    pytest.param("destination_location_type", "project", "storage", "storage", "Project", id="TOM-FFV-04"),
    pytest.param("source_location_type", "STORAGE", "storage", "storage", "Storage", id="TOM-FFV-05"),
    pytest.param("destination_location_type", "Warehouse", "storage", "storage", "Warehouse", id="TOM-FFV-06"),
    pytest.param("source_location_type", "", "storage", "storage", "—", id="TOM-FFV-07"),
    pytest.param("destination_location_type", None, "storage", "storage", "—", id="TOM-FFV-08"),
    pytest.param("source_location_id", "F1", "storage", "machine", "Alpha Works", id="TOM-FFV-09"),
    pytest.param("destination_location_id", "M1", "storage", "machine", "Press Kilo", id="TOM-FFV-10"),
    pytest.param("destination_location_id", "F1", "storage", "machine", "Machine #{F1}", id="TOM-FFV-11"),
    pytest.param("required_approvals", None, "storage", "storage", "All assigned", id="TOM-FFV-12"),
    pytest.param("required_approvals", 0, "storage", "storage", "0", id="TOM-FFV-13"),
    pytest.param("required_approvals", 2, "storage", "storage", "2", id="TOM-FFV-14"),
    pytest.param("description", "  New text ", "storage", "storage", "New text", id="TOM-FFV-15"),
    pytest.param("description", None, "storage", "storage", "—", id="TOM-FFV-16"),
])
def test_tom_ffv__format_field_value(db, S, field, value, st, dt, expected):
    """TOM-FFV-01..16 — field display values.
    Rules: _format_field_value R1-R4."""
    if field.endswith("_location_id"):
        value = getattr(S, value).id
    want = expected.format(F1=S.F1.id)
    result = M._format_field_value(db, S.W1.id, field, value, source_type=st, destination_type=dt)
    # Then 1
    assert result == want


# =========================================================================== #
# _collect_field_changes
# =========================================================================== #

def test_tom_cfc_01__six_fields_fixed_order(db, S):
    """TOM-CFC-01 — all six logged fields, in the fixed order with their labels.
    Rules: _collect_field_changes R1, R3."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {
        "required_approvals": 2, "description": "New text", "destination_location_id": S.F1.id,
        "destination_location_type": "damaged", "source_location_id": S.M1.id, "source_location_type": "machine"})
    # Then 1
    assert result == [
        CH("source_location_type", "Source type", "Storage", "Machine"),
        CH("source_location_id", "Source location", "Alpha Works", "Press Kilo"),
        CH("destination_location_type", "Destination type", "Storage", "Damaged"),
        CH("destination_location_id", "Destination location", "Bravo Yard", "Alpha Works"),
        CH("description", "Description", "Old text", "New text"),
        CH("required_approvals", "Required approvals", "All assigned", "2"),
    ]


def test_tom_cfc_02__other_keys_ignored(db, S):
    """TOM-CFC-02 — other keys are ignored.
    Rules: _collect_field_changes R1, R5."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {"current_status_id": S.S0.id, "notes": "x"})
    # Then 1
    assert result == []


def test_tom_cfc_03__equal_value_no_entry(db, S):
    """TOM-CFC-03 — a value equal to the stored one gives no entry.
    Rules: _collect_field_changes R2."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {"description": "Old text", "destination_location_id": S.FB.id})
    # Then 1
    assert result == []


def test_tom_cfc_04__empty_update(db, S):
    """TOM-CFC-04 — an empty update gives no entry.
    Rules: _collect_field_changes R2, R5."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {})
    # Then 1
    assert result == []


def test_tom_cfc_05__to_machine_labels_new_id_as_machine(db, S):
    """TOM-CFC-05 — moving a route end to a machine labels the new id as a machine.
    Rules: _collect_field_changes R4."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {"destination_location_type": "machine", "destination_location_id": S.M1.id})
    # Then 1
    assert result == [CH("destination_location_type", "Destination type", "Storage", "Machine"),
                      CH("destination_location_id", "Destination location", "Bravo Yard", "Press Kilo")]


def test_tom_cfc_06__from_machine_labels_old_id_as_machine(db, S):
    """TOM-CFC-06 — moving a machine end to a factory labels the old id as a machine.
    Rules: _collect_field_changes R4."""
    O = order(db, S, destination_location_type="machine", destination_location_id=S.M1.id)
    result = M._collect_field_changes(db, S.W1.id, O, {"destination_location_type": "storage", "destination_location_id": S.FB.id})
    # Then 1
    assert result == [CH("destination_location_type", "Destination type", "Machine", "Storage"),
                      CH("destination_location_id", "Destination location", "Press Kilo", "Bravo Yard")]


def test_tom_cfc_07__id_change_uses_stored_type(db, S):
    """TOM-CFC-07 — an id change alone uses the stored type for both values.
    Rules: _collect_field_changes R4."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {"source_location_id": S.FB.id})
    # Then 1
    assert result == [CH("source_location_id", "Source location", "Alpha Works", "Bravo Yard")]


def test_tom_cfc_08__type_change_same_id(db, S):
    """TOM-CFC-08 — a type change with the same id gives only the type entry.
    Rules: _collect_field_changes R2, R4."""
    O = order(db, S)
    result = M._collect_field_changes(db, S.W1.id, O, {"destination_location_type": "damaged", "destination_location_id": S.FB.id})
    # Then 1
    assert result == [CH("destination_location_type", "Destination type", "Storage", "Damaged")]


def test_tom_cfc_09__required_number_to_number(db, S):
    """TOM-CFC-09 — required approvals from a number to another number.
    Rules: _collect_field_changes R3."""
    O = order(db, S, required_approvals=2)
    result = M._collect_field_changes(db, S.W1.id, O, {"required_approvals": 0})
    # Then 1
    assert result == [CH("required_approvals", "Required approvals", "2", "0")]


# =========================================================================== #
# _log_field_change_event
# =========================================================================== #

def test_tom_lfc_01__no_changes_no_event(db, S):
    """TOM-LFC-01 — no changes, no event.
    Rules: _log_field_change_event R1, R3."""
    O = order(db, S)
    result = M._log_field_change_event(db, O.id, S.W1.id, S.U2.id, "updated", "Order details updated", [])
    # Then 1
    assert not db.new
    # Then 2
    assert result is None
    # Then 3
    assert count_where(db, TransferOrderEvent, transfer_order_id=O.id) == 0


def test_tom_lfc_02__changes_give_one_event(db, S):
    """TOM-LFC-02 — changes give one event with the changes as metadata.
    Rules: _log_field_change_event R2, R3."""
    O = order(db, S)
    result = M._log_field_change_event(db, O.id, S.W1.id, S.U2.id, "updated", "Order details updated",
                                       [CH("description", "Description", "Old text", "New text")])
    # Then 1
    assert result is None
    # Then 2
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id,
                              {"changes": [CH("description", "Description", "Old text", "New text")]})]
    # Then 3
    assert ev_rows(db, O.id)[0].workspace_id == S.W1.id


# =========================================================================== #
# _guard_confirmed_updates
# =========================================================================== #

def test_tom_gcu_01__completed_refuses_non_empty(db, S):
    """TOM-GCU-01 — a completed order refuses any non-empty update.
    Rules: _guard_confirmed_updates R1."""
    O = order(db, S, completed=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {"description": "New text"})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete and cannot be edited"
    # Then 3
    session_clean(db)


def test_tom_gcu_02__completed_lets_empty_through(db, S):
    """TOM-GCU-02 — a completed order lets an empty update through.
    Rules: _guard_confirmed_updates R2."""
    O = order(db, S, completed=True)
    before = snap(db, O)
    M._guard_confirmed_updates(db, O, {})
    # Then 1
    unchanged(db, O, before)


def test_tom_gcu_03__status_refused(db, S):
    """TOM-GCU-03 — sending current_status_id is refused.
    Rules: _guard_confirmed_updates R3."""
    O = order(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {"current_status_id": S.S1.id})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Status is derived from workflow state — use Mark complete instead"
    # Then 3
    session_clean(db)


def test_tom_gcu_04__completion_before_status(db, S):
    """TOM-GCU-04 — completion is checked before the status.
    Rules: _guard_confirmed_updates R5."""
    O = order(db, S, completed=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {"current_status_id": S.S1.id})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete and cannot be edited"


def test_tom_gcu_05__status_before_approval_lock(db, S):
    """TOM-GCU-05 — the status is checked before the approval lock.
    Rules: _guard_confirmed_updates R5."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {"description": "New text", "current_status_id": S.S1.id})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Status is derived from workflow state — use Mark complete instead"


def test_tom_gcu_06__approval_locks_source_type(db, S):
    """TOM-GCU-06 — with an approval, a source type edit is refused.
    Rules: _guard_confirmed_updates R4."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {"source_location_type": "damaged"})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing order details"
    # Then 3
    session_clean(db)


@pytest.mark.parametrize("key, val", [
    pytest.param("source_location_id", "FB", id="TOM-GCU-07"),
    pytest.param("destination_location_type", "machine", id="TOM-GCU-08"),
    pytest.param("destination_location_id", "F1", id="TOM-GCU-09"),
    pytest.param("description", "New text", id="TOM-GCU-10"),
    pytest.param("description", "Old text", id="TOM-GCU-11"),
])
def test_tom_gcu__approval_locks_route_fields(db, S, key, val):
    """TOM-GCU-07..11 — with an approval, route / description edits are refused (equal value counts as sent).
    Rules: _guard_confirmed_updates R4, R5."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    value = getattr(S, val).id if key.endswith("_location_id") else val
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_confirmed_updates(db, O, {key: value})
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing order details"


def test_tom_gcu_12__required_alone_passes(db, S):
    """TOM-GCU-12 — required approvals alone passes while approvals are given.
    Rules: _guard_confirmed_updates R4 (OQ-55)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    before = snap(db, O)
    M._guard_confirmed_updates(db, O, {"required_approvals": 1})
    # Then 1
    unchanged(db, O, before)


def test_tom_gcu_13__no_approval_route_passes(db, S):
    """TOM-GCU-13 — without an approval, route and description edits pass.
    Rules: _guard_confirmed_updates R4, R7."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U2, 2)
    before = snap(db, O)
    result = M._guard_confirmed_updates(db, O, {"destination_location_id": S.F1.id, "description": "New text"})
    # Then 1
    assert result is None
    # Then 2
    session_clean(db)
    # Then 3
    unchanged(db, O, before)


# =========================================================================== #
# _guard_item_mutations
# =========================================================================== #

def test_tom_gim_01__completed_refused(db, S):
    """TOM-GIM-01 — a completed order refuses item changes.
    Rules: _guard_item_mutations R1."""
    O = order(db, S, completed=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_item_mutations(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"


def test_tom_gim_02__completion_before_approvals(db, S):
    """TOM-GIM-02 — completion is checked before approvals.
    Rules: _guard_item_mutations R1, R2."""
    O = order(db, S, completed=True)
    apr(db, S, O, S.U1, 1, approved=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_item_mutations(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"


def test_tom_gim_03__approval_refused(db, S):
    """TOM-GIM-03 — an approval refuses item changes.
    Rules: _guard_item_mutations R2."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U2, 2, approved=True)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._guard_item_mutations(db, O, S.W1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing transfer items"


def test_tom_gim_04__unapproved_approvers_pass(db, S):
    """TOM-GIM-04 — approvers with no approval pass.
    Rules: _guard_item_mutations R3."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    before = snap(db, O)
    result = M._guard_item_mutations(db, O, S.W1.id)
    # Then 1
    assert result is None
    # Then 2
    session_clean(db)
    # Then 3
    unchanged(db, O, before)


def test_tom_gim_05__no_approvers_pass(db, S):
    """TOM-GIM-05 — no approvers pass.
    Rules: _guard_item_mutations R3."""
    O = order(db, S)
    before = snap(db, O)
    result = M._guard_item_mutations(db, O, S.W1.id)
    # Then 1
    assert result is None
    # Then 2
    session_clean(db)
    # Then 3
    unchanged(db, O, before)


# =========================================================================== #
# create_transfer_order
# =========================================================================== #

def _create(db, S, data):
    return M.create_transfer_order(db, data=data, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_c_01__order_stored_with_sent_fields(db, S, TNUM):
    """TOM-C-01 — the order is stored with the sent fields.
    Rules: create_transfer_order R2."""
    result = _create(db, S, CREATE(S, items=[ITEM(S.I1, "10")]))
    # Then 1
    assert result.id is not None
    # Then 2
    o = reread(db, TransferOrder, result.id)
    assert o.workspace_id == S.W1.id
    assert o.transfer_number == TNUM
    assert o.created_by == S.U2.id
    # Then 3
    assert o.source_location_type == "storage"
    assert o.source_location_id == S.F1.id
    assert o.destination_location_type == "storage"
    assert o.destination_location_id == S.FB.id
    # Then 4
    assert o.description == "Monthly move"
    assert o.current_status_id == S.S1.id
    # Then 5
    assert o.required_approvals is None
    assert o.completed_at is None
    assert o.completed_by is None


def test_tom_c_02__lines_numbered_in_sent_order(db, S):
    """TOM-C-02 — lines are numbered in the sent order.
    Rules: create_transfer_order R5."""
    result = _create(db, S, CREATE(S, items=[ITEM(S.I2, "5", notes="Fragile"), ITEM(S.I1, "10")]))
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_where(db, TransferOrderItem, transfer_order_id=result.id) == 2
    # Then 3
    ls = {r.line_number: r for r in lines_of(db, result.id)}
    assert ls[1].item_id == S.I2.id
    assert ls[1].quantity == Decimal("5.00")
    assert ls[1].notes == "Fragile"
    assert ls[1].workspace_id == S.W1.id
    # Then 4
    assert ls[2].item_id == S.I1.id
    assert ls[2].quantity == Decimal("10.00")
    assert ls[2].notes is None
    assert ls[2].workspace_id == S.W1.id
    # Then 5
    for r in (ls[1], ls[2]):
        assert r.approved is False
        assert r.transferred_at is None
        assert r.transferred_by is None


def test_tom_c_03__creator_is_unapproved_approver(db, S):
    """TOM-C-03 — the creator is the one unapproved approver.
    Rules: create_transfer_order R3 (Q4)."""
    result = _create(db, S, CREATE(S))
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_where(db, TransferOrderApprover, transfer_order_id=result.id) == 1
    # Then 3
    a = approvers_of(db, result.id)[0]
    assert a.user_id == S.U2.id
    assert a.assigned_by == S.U2.id
    assert a.approved is False
    assert a.approved_at is None
    assert a.workspace_id == S.W1.id


def test_tom_c_04__one_created_event(db, S):
    """TOM-C-04 — one `created` event, and no item events.
    Rules: create_transfer_order R7."""
    result = _create(db, S, CREATE(S, items=[ITEM(S.I1, "10"), ITEM(S.I2, "3")]))
    # Then 1
    assert result.id is not None
    # Then 2
    assert evs(db, result.id) == [("created", "Transfer order created", S.U2.id, None)]


@pytest.mark.parametrize("items", [
    pytest.param(None, id="TOM-C-05"),
    pytest.param([], id="TOM-C-06"),
])
def test_tom_c__no_items_draft(db, S, items):
    """TOM-C-05/06 — no items (None or empty) gives a draft with no lines.
    Rules: create_transfer_order R6."""
    result = _create(db, S, CREATE(S, items=items))
    # Then 1
    assert result.id is not None
    # Then 2
    assert count_where(db, TransferOrderItem, transfer_order_id=result.id) == 0


def test_tom_c_07__same_route_refused(db, S):
    """TOM-C-07 — source equal to destination is refused.
    Rules: create_transfer_order R1; Errors 1."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, destination_location_id=S.F1.id, items=[ITEM(S.I1, "10")]))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Source and destination cannot be the same"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_c_08__same_id_other_type_accepted(db, S):
    """TOM-C-08 — the same id with another type is accepted.
    Rules: create_transfer_order R1."""
    result = _create(db, S, CREATE(S, destination_location_type="damaged", destination_location_id=S.F1.id))
    # Then 1
    assert result.id is not None
    # Then 2
    o = reread(db, TransferOrder, result.id)
    assert o.source_location_type == "storage"
    assert o.destination_location_type == "damaged"
    assert o.destination_location_id == S.F1.id


def test_tom_c_09__live_machine_destination_accepted(db, S):
    """TOM-C-09 — a live machine of the workspace is accepted as destination.
    Rules: create_transfer_order R2, R2a."""
    result = _create(db, S, CREATE(S, destination_location_type="machine", destination_location_id=S.M1.id))
    # Then 1
    assert result.id is not None
    # Then 2
    o = reread(db, TransferOrder, result.id)
    assert o.destination_location_type == "machine"
    assert o.destination_location_id == S.M1.id


def test_tom_c_10__duplicate_item_refused_with_name(db, S):
    """TOM-C-10 — the same catalog item twice is refused with its name.
    Rules: create_transfer_order R4; Errors 2."""
    n_items = counts(db)["transfer_order_items"]
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, items=[ITEM(S.I1, "10"), ITEM(S.I2, "1"), ITEM(S.I1, "4")]))
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Motor appears more than once on this order"
    # Then 3
    assert counts(db)["transfer_order_items"] == n_items


@xfail("BUG-2889")
def test_tom_c_11__duplicate_check_writes_nothing(db, S, TNUM):
    """TOM-C-11 — the duplicate check writes nothing.
    Rules: create_transfer_order R4, R4b [BUG-2889] (R2e)."""
    n_apr = counts(db)["transfer_order_approvers"]
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, items=[ITEM(S.I1, "10"), ITEM(S.I1, "4")]))
    assert exc.value.status_code == 409
    # Then 2
    assert count_where(db, TransferOrder, transfer_number=TNUM) == 0
    # Then 3
    assert counts(db)["transfer_order_approvers"] == n_apr


@pytest.mark.parametrize("over, kind, key, clean", [
    pytest.param({"source_location_id": "F2"}, "Factory", "F2", True, id="TOM-C-13"),
    pytest.param({"destination_location_type": "damaged", "destination_location_id": "F0"}, "Factory", "F0", True, id="TOM-C-14"),
    pytest.param({"destination_location_id": MISSING}, "Factory", MISSING, False, id="TOM-C-15"),
    pytest.param({"source_location_id": "FD"}, "Factory", "FD", False, id="TOM-C-16"),
    pytest.param({"destination_location_type": "machine", "destination_location_id": "M2"}, "Machine", "M2", True, id="TOM-C-17"),
    pytest.param({"source_location_type": "machine", "source_location_id": "M0"}, "Machine", "M0", False, id="TOM-C-18"),
    pytest.param({"destination_location_type": "machine", "destination_location_id": "MD"}, "Machine", "MD", False, id="TOM-C-19"),
    pytest.param({"destination_location_type": "machine", "destination_location_id": "FB"}, "Machine", "FB", False, id="TOM-C-20"),
])
@xfail("BUG-2894")
def test_tom_c__route_end_not_live_in_workspace_refused(db, S, over, kind, key, clean):
    """TOM-C-13..20 — a foreign / missing / deleted route end is refused 404.
    Rules: create_transfer_order R2a [BUG-2894] (HR-16); Errors 3."""
    over = {k: (getattr(S, v).id if isinstance(v, str) and k.endswith("_id") else v) for k, v in over.items()}
    loc_id = getattr(S, key).id if isinstance(key, str) else key
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, **over))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"{kind} with ID {loc_id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


@pytest.mark.parametrize("key, clean", [
    pytest.param("S2", True, id="TOM-C-21"),
    pytest.param("S0", False, id="TOM-C-22"),
])
@xfail("BUG-1018")
def test_tom_c__foreign_status_refused(db, S, key, clean):
    """TOM-C-21/22 — a status of another workspace is refused 404.
    Rules: create_transfer_order R2b [BUG-1018]; Errors 4."""
    st = getattr(S, key)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, current_status_id=st.id))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Status with ID {st.id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


@pytest.mark.parametrize("items, bad, clean", [
    pytest.param([("I1", "1"), ("IX", "2")], "IX", True, id="TOM-C-23"),
    pytest.param([("I0", "2")], "I0", False, id="TOM-C-24"),
    pytest.param([("IX", "1"), ("IX", "2")], "IX", True, id="TOM-C-34"),
])
@xfail("BUG-1018")
def test_tom_c__foreign_line_item_refused(db, S, items, bad, clean):
    """TOM-C-23/24/34 — a line item of another workspace is refused 404 (before the duplicate check).
    Rules: create_transfer_order R2b [BUG-1018], R2e; Errors 4."""
    bad_id = getattr(S, bad).id
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, items=[ITEM(getattr(S, k), q) for k, q in items]))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {bad_id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


@xfail("BUG-825")
def test_tom_c_25__project_destination_refused(db, S):
    """TOM-C-25 — a project destination is refused.
    Rules: create_transfer_order R2c [BUG-825] (Q7); Errors 5."""
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _create(db, S, CREATE(S, destination_location_type="project", destination_location_id=S.C1.id))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Project destination is not yet supported"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


@pytest.mark.parametrize("st, dt", [
    pytest.param("machine", "damaged", id="TOM-C-26"),
    pytest.param("storage", "project", id="TOM-C-37"),
])
def test_tom_c__create_schema_accepts_known_types(st, dt):
    """TOM-C-26/37 — the create schema accepts the known types (project as destination).
    Rules: create_transfer_order R2d [BUG-823] (the side that holds today)."""
    result = TransferOrderCreate(source_location_type=st, source_location_id=1,
                                 destination_location_type=dt, destination_location_id=2)
    # Then 1
    assert result.source_location_type == st
    assert result.destination_location_type == dt


@pytest.mark.parametrize("st, dt, loc", [
    pytest.param("warehouse", "storage", "source_location_type", id="TOM-C-27"),
    pytest.param("storage", "shelf", "destination_location_type", id="TOM-C-28"),
    pytest.param("project", "storage", "source_location_type", id="TOM-C-35"),
    pytest.param("Storage", "storage", "source_location_type", id="TOM-C-36"),
    pytest.param("storage", "", "destination_location_type", id="TOM-C-38"),
])
@xfail("BUG-823")
def test_tom_c__create_schema_refuses_unknown_types(st, dt, loc):
    """TOM-C-27/28/35/36/38 — the create schema refuses unknown / non-exact types.
    Rules: create_transfer_order R2d [BUG-823] (G7)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderCreate(source_location_type=st, source_location_id=1,
                            destination_location_type=dt, destination_location_id=2)
    assert exc.value.errors()[0]["loc"] == (loc,)


def test_tom_c_29__line_schema_accepts_whole_quantity():
    """TOM-C-29 — a line schema accepts whole quantities above 0.
    Rules: create_transfer_order R2d [BUG-824] (the side that holds today)."""
    result = TransferOrderItemCreate(item_id=1, quantity=Decimal("1"))
    # Then 1
    assert result.quantity == Decimal("1")


@pytest.mark.parametrize("q", [
    pytest.param("0", id="TOM-C-30"),
    pytest.param("-1", id="TOM-C-31"),
    pytest.param("2.5", id="TOM-C-32"),
])
@xfail("BUG-824")
def test_tom_c__line_schema_refuses_bad_quantity(q):
    """TOM-C-30..32 — a line schema refuses 0, negative and fractional quantities.
    Rules: create_transfer_order R2d [BUG-824]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemCreate(item_id=1, quantity=Decimal(q))
    assert exc.value.errors()[0]["loc"] == ("quantity",)


def test_tom_c_33__create_does_not_commit(db, S, TNUM):
    """TOM-C-33 — create does not commit.
    Rules: create_transfer_order Returns (flushed, not committed)."""
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _create(db, S, CREATE(S))
        # Then 1
        assert result.id is not None
        # Then 2
        assert count_where(db, TransferOrder, transfer_number=TNUM) == 1
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert count_where(db, TransferOrder, transfer_number=TNUM) == 0


# =========================================================================== #
# update_transfer_order
# =========================================================================== #

def _upd(db, S, to_id, data):
    return M.update_transfer_order(db, to_id=to_id, data=data, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_u_01__description_stored_stamped_logged(db, S):
    """TOM-U-01 — a description edit is stored, stamped and logged.
    Rules: update_transfer_order R4, R5, R7."""
    O = order(db, S)
    result = _upd(db, S, O.id, UPD(description="New text"))
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.description == "New text"
    assert o.updated_by == S.U2.id
    # Then 3
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id,
                              {"changes": [CH("description", "Description", "Old text", "New text")]})]


def test_tom_u_02__destination_to_machine_logged_with_labels(db, S):
    """TOM-U-02 — a destination moved to a machine is stored and logged with labels.
    Rules: update_transfer_order R4, R5."""
    O = order(db, S)
    result = _upd(db, S, O.id, UPD(destination_location_type="machine", destination_location_id=S.M1.id))
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.destination_location_type == "machine"
    assert o.destination_location_id == S.M1.id
    # Then 3
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id, {"changes": [
        CH("destination_location_type", "Destination type", "Storage", "Machine"),
        CH("destination_location_id", "Destination location", "Bravo Yard", "Press Kilo")]})]


def test_tom_u_03__missing_order_404(db, S):
    """TOM-U-03 — a missing order is 404.
    Rules: update_transfer_order R1."""
    order(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, MISSING, UPD(description="New text"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order with ID 999999999 not found"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_u_04__higher_workspace_order_404(db, S):
    """TOM-U-04 — an order of a higher workspace is 404.
    Rules: update_transfer_order R1."""
    O9 = order(db, S, "O9")
    before = snap(db, O9)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O9.id, UPD(description="New text"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {O9.id} not found"
    # Then 3
    session_clean(db)
    # Then 4
    unchanged(db, O9, before)


def test_tom_u_05__lower_workspace_order_404(db, S):
    """TOM-U-05 — an order of a lower workspace is 404.
    Rules: update_transfer_order R1."""
    O0 = order(db, S, "O0")
    before = snap(db, O0)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O0.id, UPD(description="New text"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {O0.id} not found"
    # Then 3
    unchanged(db, O0, before)


def test_tom_u_06__omitted_fields_unchanged(db, S):
    """TOM-U-06 — omitted fields are left unchanged.
    Rules: update_transfer_order R2, R2a (omitted fields)."""
    O = order(db, S, required_approvals=2)
    result = _upd(db, S, O.id, UPD(description="New text"))
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.source_location_type == "storage"
    assert o.source_location_id == S.F1.id
    assert o.destination_location_type == "storage"
    assert o.destination_location_id == S.FB.id
    # Then 3
    assert o.required_approvals == 2
    assert o.current_status_id == S.S1.id


@xfail("BUG-2895")
def test_tom_u_07__null_clears_description(db, S):
    """TOM-U-07 — an explicit null clears the description.
    Rules: update_transfer_order R2a [BUG-2895]."""
    O = order(db, S)
    result = _upd(db, S, O.id, UPD(description=None))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).description is None
    # Then 3
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id,
                              {"changes": [CH("description", "Description", "Old text", "—")]})]


@xfail("BUG-2895")
def test_tom_u_08__null_resets_required_to_all_assigned(db, S):
    """TOM-U-08 — an explicit null sets required approvals back to "All assigned".
    Rules: update_transfer_order R2a [BUG-2895]."""
    O = order(db, S, required_approvals=2)
    result = _upd(db, S, O.id, UPD(required_approvals=None))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals is None
    # Then 3
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id,
                              {"changes": [CH("required_approvals", "Required approvals", "2", "All assigned")]})]


@pytest.mark.parametrize("field", [
    pytest.param("source_location_type", id="TOM-U-09"),
    pytest.param("source_location_id", id="TOM-U-10"),
    pytest.param("destination_location_type", id="TOM-U-11"),
    pytest.param("destination_location_id", id="TOM-U-12"),
])
@xfail("BUG-2895")
def test_tom_u__null_route_field_refused_by_schema(field):
    """TOM-U-09..12 — null for a route field is refused by the schema.
    Rules: update_transfer_order R2a [BUG-2895]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderUpdate(**{field: None})
    assert exc.value.errors()[0]["loc"] == (field,)


def test_tom_u_13__completed_refuses_edit(db, S):
    """TOM-U-13 — a completed order refuses an edit.
    Rules: update_transfer_order R3 (_guard_confirmed_updates R1)."""
    O = order(db, S, completed=True)
    before_o = snap(db, O)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(description="New text"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete and cannot be edited"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    unchanged(db, O, before_o)


def test_tom_u_14__empty_update_on_completed_passes(db, S):
    """TOM-U-14 — an empty update of a completed order goes through without a change.
    Rules: update_transfer_order R3 (_guard_confirmed_updates R2), R4."""
    O = order(db, S, completed=True)
    result = _upd(db, S, O.id, UPD())
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.description == "Old text"
    assert naive(o.completed_at) == DONE
    # Then 3
    assert evs(db, O.id) == []


@pytest.mark.parametrize("completed, data", [
    pytest.param(True, {}, id="TOM-U-15"),
    pytest.param(False, {}, id="TOM-U-16"),
    pytest.param(False, {"description": "Old text"}, id="TOM-U-18"),
])
@xfail("BUG-2893")
def test_tom_u__no_change_no_updated_by_stamp(db, S, completed, data):
    """TOM-U-15/16/18 — an update that changes nothing does not stamp updated_by.
    Rules: update_transfer_order R7 [BUG-2893] (HR-9)."""
    O = order(db, S, completed=completed)
    result = _upd(db, S, O.id, UPD(**data))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).updated_by is None


def test_tom_u_17__unchanged_value_no_event(db, S):
    """TOM-U-17 — an unchanged value writes no event.
    Rules: update_transfer_order R4."""
    O = order(db, S)
    result = _upd(db, S, O.id, UPD(description="Old text", destination_location_id=S.FB.id))
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.description == "Old text"
    assert o.destination_location_id == S.FB.id
    # Then 3
    assert evs(db, O.id) == []


def test_tom_u_19__status_refused(db, S):
    """TOM-U-19 — sending current_status_id is refused.
    Rules: update_transfer_order R3 (_guard_confirmed_updates R3)."""
    O = order(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(current_status_id=S.S1.id))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Status is derived from workflow state — use Mark complete instead"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_u_20__approval_locks_route(db, S):
    """TOM-U-20 — with an approval, a route edit is refused.
    Rules: update_transfer_order R3 (_guard_confirmed_updates R4)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    before_o = snap(db, O)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(destination_location_id=S.F1.id))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing order details"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    unchanged(db, O, before_o)


def test_tom_u_21__approval_locks_resent_description(db, S):
    """TOM-U-21 — with an approval, resending the stored description is still refused.
    Rules: update_transfer_order R3 (_guard_confirmed_updates R5)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(description="Old text"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing order details"
    # Then 3
    assert counts(db) == before


def test_tom_u_22__required_changes_while_approved(db, S):
    """TOM-U-22 — required approvals can change while approvals are given.
    Rules: update_transfer_order R3, R4, R5 (OQ-55)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U3, 2)
    result = _upd(db, S, O.id, UPD(required_approvals=1))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals == 1
    # Then 3
    upd_rows = [e for e in ev_rows(db, O.id) if e.event_type == "updated"]
    assert len(upd_rows) == 1
    # Then 4
    assert upd_rows[0].description == "Order details updated"
    assert upd_rows[0].performed_by == S.U2.id
    assert upd_rows[0].metadata_json == {"changes": [CH("required_approvals", "Required approvals", "All assigned", "1")]}
    # Then 5
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 2


@xfail("BUG-2903")
def test_tom_u_23__real_change_wipes_approvals(db, S):
    """TOM-U-23 — a real change of required approvals wipes the approvals given.
    Rules: update_transfer_order R6a [BUG-2903] (owner, OQ-55), R6c."""
    O = order(db, S)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U3, 2)
    result = _upd(db, S, O.id, UPD(required_approvals=1))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 2
    # Then 3
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is False
    assert a1.approved_at is None
    # Then 4
    assert evs(db, O.id) == [
        ("updated", "Order details updated", S.U2.id, {"changes": [CH("required_approvals", "Required approvals", "All assigned", "1")]}),
        ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", S.U2.id, None)]
    # Then 5
    assert SUMMARY(db, O.id) == (0, 1, False)


@xfail("BUG-2903")
def test_tom_u_24__wipe_counts_every_cleared(db, S):
    """TOM-U-24 — the wipe counts every cleared approval.
    Rules: update_transfer_order R6a [BUG-2903]."""
    O = order(db, S, required_approvals=2)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    A2 = apr(db, S, O, S.U3, 2, approved=True)
    result = _upd(db, S, O.id, UPD(required_approvals=1))
    # Then 1
    assert result.id == O.id
    # Then 2
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is False
    assert a1.approved_at is None
    # Then 3
    a2 = reread(db, TransferOrderApprover, A2.id)
    assert a2.approved is False
    assert a2.approved_at is None
    # Then 4
    assert evs(db, O.id) == [
        ("updated", "Order details updated", S.U2.id, {"changes": [CH("required_approvals", "Required approvals", "2", "1")]}),
        ("approvals_reset", "Required approvals changed (2 approval(s) cleared)", S.U2.id, None)]


@xfail("BUG-2903", "BUG-2895")
def test_tom_u_25__clear_to_null_wipes(db, S):
    """TOM-U-25 — clearing required approvals to null is a change that wipes.
    Rules: update_transfer_order R6a [BUG-2903], R2a [BUG-2895]."""
    O = order(db, S, required_approvals=1)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    result = _upd(db, S, O.id, UPD(required_approvals=None))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals is None
    # Then 3
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is False
    assert a1.approved_at is None
    # Then 4
    assert evs(db, O.id) == [
        ("updated", "Order details updated", S.U2.id, {"changes": [CH("required_approvals", "Required approvals", "1", "All assigned")]}),
        ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", S.U2.id, None)]


@xfail("BUG-2903")
def test_tom_u_26__zero_wipes_and_is_met(db, S):
    """TOM-U-26 — setting 0 wipes, and 0 is met at once.
    Rules: update_transfer_order R6, R6a [BUG-2903]."""
    O = order(db, S)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    result = _upd(db, S, O.id, UPD(required_approvals=0))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals == 0
    # Then 3
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is False
    assert a1.approved_at is None
    # Then 4
    assert SUMMARY(db, O.id) == (0, 0, True)
    # Then 5
    assert evs(db, O.id) == [
        ("updated", "Order details updated", S.U2.id, {"changes": [CH("required_approvals", "Required approvals", "All assigned", "0")]}),
        ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", S.U2.id, None)]


def test_tom_u_27__change_without_approval_no_reset_event(db, S):
    """TOM-U-27 — a change with no approval given writes no reset event.
    Rules: update_transfer_order R4, R6a (n = 0)."""
    O = order(db, S, required_approvals=2)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U3, 2)
    result = _upd(db, S, O.id, UPD(required_approvals=1))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert evs(db, O.id) == [("updated", "Order details updated", S.U2.id,
                              {"changes": [CH("required_approvals", "Required approvals", "2", "1")]})]


def test_tom_u_28__new_number_used_by_summary(db, S):
    """TOM-U-28 — the new number is what the summary uses.
    Rules: update_transfer_order R6."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U3, 2)
    result = _upd(db, S, O.id, UPD(required_approvals=1))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert SUMMARY(db, O.id) == (0, 1, False)


def test_tom_u_29__resending_number_keeps_approvals(db, S):
    """TOM-U-29 — resending the stored number keeps the approvals.
    Rules: update_transfer_order R6b, R4."""
    O = order(db, S, required_approvals=2)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U3, 2)
    result = _upd(db, S, O.id, UPD(required_approvals=2))
    # Then 1
    assert result.id == O.id
    # Then 2
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is True
    assert naive(a1.approved_at) == TOLD
    # Then 3
    assert evs(db, O.id) == []


@xfail("BUG-2893")
def test_tom_u_30__resending_number_no_stamp(db, S):
    """TOM-U-30 — resending the stored number does not stamp updated_by.
    Rules: update_transfer_order R6b, R7 [BUG-2893]."""
    O = order(db, S, required_approvals=2)
    apr(db, S, O, S.U1, 1, approved=True)
    result = _upd(db, S, O.id, UPD(required_approvals=2))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).updated_by is None


def test_tom_u_31__null_when_all_assigned_keeps_approvals(db, S):
    """TOM-U-31 — null when already "All assigned" keeps the approvals.
    Rules: update_transfer_order R6b."""
    O = order(db, S)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    result = _upd(db, S, O.id, UPD(required_approvals=None))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals is None
    # Then 3
    a1 = reread(db, TransferOrderApprover, A1.id)
    assert a1.approved is True
    assert naive(a1.approved_at) == TOLD
    # Then 4
    assert evs(db, O.id) == []


@xfail("BUG-2901")
def test_tom_u_32__negative_required_refused_by_schema():
    """TOM-U-32 — a negative required number is refused by the schema.
    Rules: approval_summary R2a [BUG-2901]; update_transfer_order Errors (schema 422)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderUpdate(required_approvals=-1)
    assert exc.value.errors()[0]["loc"] == ("required_approvals",)


def test_tom_u_33__zero_required_builds():
    """TOM-U-33 — 0 and positive required numbers build.
    Rules: approval_summary R2a [BUG-2901] (the side that holds today)."""
    result = TransferOrderUpdate(required_approvals=0)
    # Then 1
    assert result.required_approvals == 0


@pytest.mark.parametrize("data, kind, key, clean, keep", [
    pytest.param({"destination_location_id": "F2"}, "Factory", "F2", True, True, id="TOM-U-34"),
    pytest.param({"source_location_type": "machine", "source_location_id": "M0"}, "Machine", "M0", False, True, id="TOM-U-35"),
    pytest.param({"destination_location_id": "FD"}, "Factory", "FD", False, False, id="TOM-U-36"),
    pytest.param({"destination_location_type": "machine"}, "Machine", "FB", False, True, id="TOM-U-37"),
])
@xfail("BUG-2894")
def test_tom_u__route_end_not_live_refused(db, S, data, kind, key, clean, keep):
    """TOM-U-34..37 — a route end changed to a foreign / deleted location (merged route) is refused 404.
    Rules: update_transfer_order R3a [BUG-2894] (HR-16)."""
    O = order(db, S)
    data = {k: (getattr(S, v).id if k.endswith("_id") else v) for k, v in data.items()}
    loc_id = getattr(S, key).id
    before_o = snap(db, O)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(**data))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"{kind} with ID {loc_id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before
    if keep:
        # Then 4 / 5
        unchanged(db, O, before_o)


@xfail("BUG-825")
def test_tom_u_38__project_destination_refused(db, S):
    """TOM-U-38 — a project destination is refused on update.
    Rules: update_transfer_order R3a (BUG-825 as create R2c)."""
    O = order(db, S)
    before_o = snap(db, O)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(destination_location_type="project", destination_location_id=S.C1.id))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Project destination is not yet supported"
    # Then 3
    assert counts(db) == before
    # Then 4
    unchanged(db, O, before_o)


@xfail("BUG-823")
def test_tom_u_39__update_schema_refuses_unknown_type():
    """TOM-U-39 — the update schema refuses an unknown type.
    Rules: update_transfer_order R3a (BUG-823 as create R2d)."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderUpdate(source_location_type="warehouse")
    assert exc.value.errors()[0]["loc"] == ("source_location_type",)


@pytest.mark.parametrize("data, clean", [
    pytest.param({"destination_location_id": "F1"}, True, id="TOM-U-40"),
    pytest.param({"source_location_id": "FB"}, False, id="TOM-U-41"),
])
@xfail("BUG-2899")
def test_tom_u__merged_route_same_refused(db, S, data, clean):
    """TOM-U-40/41 — an edit making the merged route's source equal its destination is refused.
    Rules: update_transfer_order R3b [BUG-2899]."""
    O = order(db, S)
    data = {k: getattr(S, v).id for k, v in data.items()}
    before_o = snap(db, O)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _upd(db, S, O.id, UPD(**data))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Source and destination cannot be the same"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before
    # Then 4 / 5
    unchanged(db, O, before_o)


def test_tom_u_42__same_id_other_type_accepted(db, S):
    """TOM-U-42 — the same id with another type is accepted on update.
    Rules: update_transfer_order R3b, R5."""
    O = order(db, S)
    result = _upd(db, S, O.id, UPD(destination_location_type="damaged", destination_location_id=S.F1.id))
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert o.destination_location_type == "damaged"
    assert o.destination_location_id == S.F1.id


def test_tom_u_43__update_does_not_commit(db, S):
    """TOM-U-43 — update does not commit.
    Rules: update_transfer_order Returns (flushed, not committed)."""
    O = order(db, S)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _upd(db, S, oid, UPD(description="New text"))
        # Then 1
        assert result.id == oid
        # Then 2
        assert reread(db, TransferOrder, oid).description == "New text"
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert reread(db, TransferOrder, oid).description == "Old text"


@xfail("BUG-2892")
def test_tom_u_44__order_row_locked_before_guards(db, S):
    """TOM-U-44 — the order row is locked before the guards.
    Rules: _guard_confirmed_updates R6 [BUG-2892] (HR-10)."""
    O = order(db, S)
    oid, w1, u2 = O.id, S.W1.id, S.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.update_transfer_order(db, to_id=oid, data=UPD(description="New text"), workspace_id=w1, user_id=u2)
        # Then 1
        assert result.id == oid
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_u_45__zero_stored_and_met(db, S):
    """TOM-U-45 — required approvals 0 is stored and met at once.
    Rules: update_transfer_order R5, R6."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    result = _upd(db, S, O.id, UPD(required_approvals=0))
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrder, O.id).required_approvals == 0
    # Then 3
    assert SUMMARY(db, O.id) == (0, 0, True)


# =========================================================================== #
# get_transfer_order
# =========================================================================== #

def test_tom_g_01__order_returned_with_status_loaded(db, S):
    """TOM-G-01 — the order of the workspace is returned (current_status joined-loaded).
    Rules: get_transfer_order R1."""
    O = order(db, S, completed=True)
    oid, w1, s1 = O.id, S.W1.id, S.S1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.get_transfer_order(db, to_id=oid, workspace_id=w1)
        # Then 1
        assert result.id == oid
        assert result.workspace_id == w1
        # Then 2
        n = len(rec.selects)
        assert result.current_status.id == s1
        assert result.current_status.name == "Open"
        # Then 3
        assert len(rec.selects) == n


@pytest.mark.parametrize("which", [
    pytest.param(None, id="TOM-G-02"),
    pytest.param("O9", id="TOM-G-03"),
    pytest.param("O0", id="TOM-G-04"),
])
def test_tom_g__not_in_workspace_404(db, S, which):
    """TOM-G-02..04 — a missing order, or one of another workspace, is 404.
    Rules: get_transfer_order R2."""
    T = order(db, S, which or "O")
    to_id = T.id if which else MISSING
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_transfer_order(db, to_id=to_id, workspace_id=S.W1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {to_id} not found"


def test_tom_g_05__read_writes_nothing_no_lock(db, S):
    """TOM-G-05 — the read writes nothing and takes no lock.
    Rules: get_transfer_order R1 (reads)."""
    O = order(db, S)
    oid, w1 = O.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.get_transfer_order(db, to_id=oid, workspace_id=w1)
    # Then 1
    assert result.id == oid
    # Then 2
    assert rec.written == []
    # Then 3
    assert rec.no_lock()


# =========================================================================== #
# Hub reads (TOD = transfer_order_dao, used only to compute expected values)
# =========================================================================== #

def hubrow(db, S, k, **over):
    """hubrow(k) = order O, but transfer_number GN(f"TR-H{k}"), created_at TS(k)."""
    f = dict(transfer_number=GN(f"TR-H{k}"), created_at=TS(k))
    f.update(over)
    return order(db, S, **f)


def _tod():
    from app.dao.transfer_order import transfer_order_dao
    return transfer_order_dao


def test_tom_hub_01__list_default_50(db, S):
    """TOM-HUB-01 — the hub list is the DAO's list, 50 rows by default.
    Rules: Hub reads R1, R2."""
    TOD = _tod()
    for k in range(1, 52):
        hubrow(db, S, k)
    order(db, S, "O9")
    order(db, S, "O0")
    result = M.list_transfer_orders_for_hub(db, workspace_id=S.W1.id)
    # Then 1
    assert len(result) == 50
    # Then 2
    assert result == TOD.list_for_hub(db, workspace_id=S.W1.id, skip=0, limit=50)


def test_tom_hub_02__count_is_dao_count(db, S):
    """TOM-HUB-02 — the hub count is the DAO's count.
    Rules: Hub reads R1."""
    TOD = _tod()
    for k in (1, 2, 3):
        hubrow(db, S, k)
    order(db, S, "O9")
    order(db, S, "O0")
    result = M.count_transfer_orders_for_hub(db, workspace_id=S.W1.id)
    # Then 1
    assert result == 3
    # Then 2
    assert result == TOD.count_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_03__stats_are_dao_stats(db, S):
    """TOM-HUB-03 — the hub stats are the DAO's stats.
    Rules: Hub reads R1."""
    TOD = _tod()
    hubrow(db, S, 1)
    hubrow(db, S, 2, completed_at=DONE, completed_by=S.U1.id)
    order(db, S, "O9")
    result = M.transfer_order_hub_stats(db, workspace_id=S.W1.id)
    # Then 1
    assert result == TOD.aggregate_hub_stats(db, workspace_id=S.W1.id)


def test_tom_hub_04__recent_default_10(db, S):
    """TOM-HUB-04 — the recent list is the DAO's, 10 rows by default.
    Rules: Hub reads R1, R2."""
    TOD = _tod()
    for k in range(1, 12):
        hubrow(db, S, k)
    result = M.list_transfer_orders_recent_for_hub(db, workspace_id=S.W1.id)
    # Then 1
    assert len(result) == 10
    # Then 2
    assert result == TOD.list_recent_for_hub(db, workspace_id=S.W1.id, limit=10)


def test_tom_hub_05__machine_count_is_dao(db, S):
    """TOM-HUB-05 — the machine-involved count is the DAO's.
    Rules: Hub reads R1."""
    TOD = _tod()
    hubrow(db, S, 1, destination_location_type="machine", destination_location_id=S.M1.id)
    hubrow(db, S, 2)
    order(db, S, "O9")
    result = M.count_transfer_orders_machine_involved_for_hub(db, workspace_id=S.W1.id)
    # Then 1
    assert result == TOD.count_machine_involved_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_06__pending_highlights_are_dao(db, S):
    """TOM-HUB-06 — the pending highlights are the DAO's.
    Rules: Hub reads R1."""
    TOD = _tod()
    h1 = hubrow(db, S, 1)
    line(db, S, h1, 1)
    hubrow(db, S, 2, completed_at=DONE, completed_by=S.U1.id)
    result = M.transfer_order_pending_highlights_for_hub(db, workspace_id=S.W1.id)
    # Then 1
    assert result == TOD.get_pending_highlights_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_07__list_passes_filter_and_paging(db, S):
    """TOM-HUB-07 — the hub list passes its filter and paging to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    hubrow(db, S, 1, destination_location_type="machine", destination_location_id=S.M1.id)
    hubrow(db, S, 2)
    hubrow(db, S, 3)
    result = M.list_transfer_orders_for_hub(db, workspace_id=S.W1.id, skip=0, limit=5, destination_location_type="machine")
    # Then 1
    assert result == TOD.list_for_hub(db, workspace_id=S.W1.id, skip=0, limit=5, destination_location_type="machine")
    # Then 2
    assert len(result) != len(TOD.list_for_hub(db, workspace_id=S.W1.id, skip=0, limit=5))


def test_tom_hub_08__count_passes_exclude_complete(db, S):
    """TOM-HUB-08 — the hub count passes `exclude_complete=False` to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    hubrow(db, S, 1)
    hubrow(db, S, 2, completed_at=DONE, completed_by=S.U1.id)
    result = M.count_transfer_orders_for_hub(db, workspace_id=S.W1.id, exclude_complete=False)
    # Then 1
    assert result == TOD.count_for_hub(db, workspace_id=S.W1.id, exclude_complete=False)
    # Then 2
    assert result != TOD.count_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_09__stats_pass_filter(db, S):
    """TOM-HUB-09 — the hub stats pass their filter to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    hubrow(db, S, 1, source_location_type="machine", source_location_id=S.M1.id)
    hubrow(db, S, 2)
    hubrow(db, S, 3, completed_at=DONE, completed_by=S.U1.id)
    result = M.transfer_order_hub_stats(db, workspace_id=S.W1.id, source_location_type="machine")
    # Then 1
    assert result == TOD.aggregate_hub_stats(db, workspace_id=S.W1.id, source_location_type="machine")
    # Then 2
    assert result != TOD.aggregate_hub_stats(db, workspace_id=S.W1.id)


def test_tom_hub_10__recent_passes_search_and_limit(db, S):
    """TOM-HUB-10 — the recent list passes its search and limit to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    for k in (1, 2, 3):
        hubrow(db, S, k)
    result = M.list_transfer_orders_recent_for_hub(db, workspace_id=S.W1.id, limit=5, search="TR-H2-")
    # Then 1
    assert result == TOD.list_recent_for_hub(db, workspace_id=S.W1.id, limit=5, search="TR-H2-")
    # Then 2
    assert len(result) != len(TOD.list_recent_for_hub(db, workspace_id=S.W1.id, limit=5))


def test_tom_hub_11__machine_count_passes_exclude_complete(db, S):
    """TOM-HUB-11 — the machine-involved count passes `exclude_complete=False` to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    hubrow(db, S, 1, destination_location_type="machine", destination_location_id=S.M1.id,
           completed_at=DONE, completed_by=S.U1.id)
    hubrow(db, S, 2, destination_location_type="machine", destination_location_id=S.M1.id)
    result = M.count_transfer_orders_machine_involved_for_hub(db, workspace_id=S.W1.id, exclude_complete=False)
    # Then 1
    assert result == TOD.count_machine_involved_for_hub(db, workspace_id=S.W1.id, exclude_complete=False)
    # Then 2
    assert result != TOD.count_machine_involved_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_12__pending_highlights_pass_search(db, S):
    """TOM-HUB-12 — the pending highlights pass their search to the DAO.
    Rules: Hub reads R1, R3 (G2)."""
    TOD = _tod()
    h1 = hubrow(db, S, 1)
    line(db, S, h1, 1)
    h2 = hubrow(db, S, 2)
    line(db, S, h2, 1)
    result = M.transfer_order_pending_highlights_for_hub(db, workspace_id=S.W1.id, search="TR-H1-")
    # Then 1
    assert result == TOD.get_pending_highlights_for_hub(db, workspace_id=S.W1.id, search="TR-H1-")
    # Then 2
    assert result != TOD.get_pending_highlights_for_hub(db, workspace_id=S.W1.id)


def test_tom_hub_13__unknown_keyword_type_error(db, S):
    """TOM-HUB-13 — an unknown filter keyword raises TypeError.
    Rules: Hub reads R3 (G2)."""
    hubrow(db, S, 1)
    # Then 1
    with pytest.raises(TypeError):
        M.count_transfer_orders_for_hub(db, workspace_id=S.W1.id, colour="red")


# =========================================================================== #
# delete_transfer_order
# =========================================================================== #

def _raw_count(db, table, col, val):
    db.flush()
    return db.execute(text(f"SELECT count(*) FROM {table} WHERE {col} = :v"), {"v": val}).scalar()


def test_tom_d_01__order_goes_with_children(db, S):
    """TOM-D-01 — the order goes with its lines, approvers and events, approvals or not.
    Rules: delete_transfer_order R3."""
    O = order(db, S)
    line(db, S, O, 1)
    line(db, S, O, 2, item_id=S.I2.id)
    apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U3, 2)
    ev(db, O, "created", 1)
    ev(db, O, "item_added", 2)
    O2 = order(db, S, "O2")
    line(db, S, O2, 1)
    apr(db, S, O2, S.U1, 3)
    ev(db, O2, "created", 3)
    oid = O.id
    result = DEL(db, S, oid)
    # Then 1
    assert result is None
    # Then 2
    assert _raw_count(db, "transfer_orders", "id", oid) == 0
    # Then 3
    assert _raw_count(db, "transfer_order_items", "transfer_order_id", oid) == 0
    # Then 4
    assert _raw_count(db, "transfer_order_approvers", "transfer_order_id", oid) == 0
    # Then 5
    assert _raw_count(db, "transfer_order_events", "transfer_order_id", oid) == 0
    # Then 6
    assert _raw_count(db, "transfer_order_items", "transfer_order_id", O2.id) == 1
    assert _raw_count(db, "transfer_order_approvers", "transfer_order_id", O2.id) == 1
    assert _raw_count(db, "transfer_order_events", "transfer_order_id", O2.id) == 1


@xfail("BUG-2890")
def test_tom_d_02__foreign_line_removed_with_order(db, S):
    """TOM-D-02 — a line stored under another workspace is removed with the order.
    Rules: delete_transfer_order R4 [BUG-2890] (HR-16)."""
    O = order(db, S)
    line(db, S, O, 1)
    line(db, S, O, 2, workspace_id=S.W2.id, item_id=S.IX.id)
    oid = O.id
    result = DEL(db, S, oid)
    # Then 1
    assert result is None
    # Then 2
    assert _raw_count(db, "transfer_order_items", "transfer_order_id", oid) == 0


@pytest.mark.parametrize("which, clean", [
    pytest.param(None, True, id="TOM-D-03"),
    pytest.param("O9", True, id="TOM-D-04"),
    pytest.param("O0", False, id="TOM-D-05"),
])
def test_tom_d__not_in_workspace_404(db, S, which, clean):
    """TOM-D-03..05 — a missing order, or one of another workspace, is 404 and stays.
    Rules: delete_transfer_order R1."""
    T = order(db, S, which or "O")
    if which == "O9":
        line(db, S, T, 1)
    to_id = T.id if which else MISSING
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, S, to_id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {to_id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


def test_tom_d_06__completed_cannot_be_deleted(db, S):
    """TOM-D-06 — a completed order cannot be deleted.
    Rules: delete_transfer_order R2."""
    O = order(db, S, completed=True)
    line(db, S, O, 1)
    apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Cannot delete a completed transfer order"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


@xfail("BUG-1194")
def test_tom_d_07__delete_leaves_audit_row(db, S):
    """TOM-D-07 — a delete leaves one audit row.
    Rules: delete_transfer_order R5 [BUG-1194] (owner, 2026-11-01)."""
    O = order(db, S)
    oid, number = O.id, O.transfer_number
    # Then 1 (the call is the When; today it raises TypeError: no user_id parameter)
    result = M.delete_transfer_order(db, to_id=oid, workspace_id=S.W1.id, user_id=S.U2.id)
    assert result is None
    # Then 2
    rows = AUDIT(db, oid)
    assert len(rows) == 1
    # Then 3
    r = rows[0]
    assert r.workspace_id == S.W1.id
    assert r.user_id == S.U2.id
    assert r.action == "transfer_order_deleted"
    assert r.resource_type == "transfer_order"
    assert r.resource_id == oid
    # Then 4
    assert r.metadata == {"number": number, "created_by": S.U1.id, "created_at": TS(1).isoformat()}


@xfail("BUG-1194")
def test_tom_d_08__refused_delete_no_audit(db, S):
    """TOM-D-08 — a refused delete leaves no audit row.
    Rules: delete_transfer_order R5 [BUG-1194]."""
    O = order(db, S, completed=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_transfer_order(db, to_id=O.id, workspace_id=S.W1.id, user_id=S.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert AUDIT(db, O.id) == []
    # Then 3
    assert counts(db) == before


@xfail("BUG-2892")
def test_tom_d_09__order_row_locked(db, S):
    """TOM-D-09 — the order row is locked before the completed check.
    Rules: delete_transfer_order R6 [BUG-2892] (HR-10)."""
    O = order(db, S)
    line(db, S, O, 1)
    oid = O.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = DEL(db, S, oid)
        # Then 1
        assert result is None
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_d_10__delete_does_not_commit(db, S):
    """TOM-D-10 — delete does not commit.
    Rules: delete_transfer_order R3 (flushed, never committed)."""
    O = order(db, S)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = DEL(db, S, oid)
        # Then 1
        assert result is None
        # Then 2
        assert _raw_count(db, "transfer_orders", "id", oid) == 0
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert _raw_count(db, "transfer_orders", "id", oid) == 1


# =========================================================================== #
# mark_order_complete
# =========================================================================== #

def ready(db, S, *, l1=None, l2=None, a1=None, **o_over):
    """Ready order: O, L1 = line(O, 1), L2 = line(O, 2) (I2, 5.00), A1 = apr(O, U1, 1) approved."""
    O = order(db, S, **o_over)
    L1 = line(db, S, O, 1, **(l1 or {}))
    L2 = line(db, S, O, 2, **{"item_id": S.I2.id, "quantity": Decimal("5.00"), **(l2 or {})})
    A1 = apr(db, S, O, S.U1, 1, **{"approved": True, **(a1 or {})})
    return O, L1, L2, A1


def _mc(db, S, to_id):
    return M.mark_order_complete(db, to_id=to_id, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_mc_01__stamps_order_and_lines(db, S):
    """TOM-MC-01 — completion stamps the order and every unrecorded line.
    Rules: mark_order_complete R5, R7."""
    O, L1, L2, A1 = ready(db, S)
    with POST(2):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    o = reread(db, TransferOrder, O.id)
    assert naive(o.completed_at) == NOW
    assert o.completed_by == S.U2.id
    assert o.updated_by == S.U2.id
    # Then 3
    assert naive(reread(db, TransferOrderItem, L1.id).transferred_at) == NOW
    # Then 4
    assert naive(reread(db, TransferOrderItem, L2.id).transferred_at) == NOW


def test_tom_mc_02__events_in_order(db, S):
    """TOM-MC-02 — completion writes the line, posting and completion events in order.
    Rules: mark_order_complete R5, R8."""
    O, L1, L2, A1 = ready(db, S)
    with POST(2):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert evs(db, O.id) == [
        ("transfer_recorded", "Item #1 transfer recorded", S.U2.id, {"line_number": 1, "item_id": S.I1.id}),
        ("transfer_recorded", "Item #2 transfer recorded", S.U2.id, {"line_number": 2, "item_id": S.I2.id}),
        ("inventory_posted", "2 item(s) posted to inventory", S.U2.id, {"lines_posted": 2}),
        ("order_completed", "Transfer order marked complete", S.U2.id, None),
    ]


def test_tom_mc_03__posted_once_for_all_lines(db, S):
    """TOM-MC-03 — stock is posted once for all lines of the order.
    Rules: mark_order_complete R6."""
    O, L1, L2, A1 = ready(db, S)
    with POST(2) as pm:
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert pm.call_count == 1
    # Then 3
    p = posted(pm)
    assert p["to"].id == O.id
    assert {i.id for i in p["items"]} == {L1.id, L2.id}
    assert p["workspace_id"] == S.W1.id
    assert p["user_id"] == S.U2.id


def test_tom_mc_04__recorded_line_keeps_time(db, S):
    """TOM-MC-04 — a line already recorded keeps its time and gets no event.
    Rules: mark_order_complete R5 (Q5)."""
    O, L1, L2, A1 = ready(db, S, l1={"transferred_at": TOLD, "transferred_by": "Rahim"})
    with POST(2):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    r1 = reread(db, TransferOrderItem, L1.id)
    assert naive(r1.transferred_at) == TOLD
    assert r1.transferred_by == "Rahim"
    # Then 3
    assert naive(reread(db, TransferOrderItem, L2.id).transferred_at) == NOW
    # Then 4
    rec_rows = [e for e in ev_rows(db, O.id) if e.event_type == "transfer_recorded"]
    assert len(rec_rows) == 1
    assert rec_rows[0].description == "Item #2 transfer recorded"


def test_tom_mc_05__nothing_posted_no_posting_event(db, S):
    """TOM-MC-05 — nothing posted: no posting event, the completion event still.
    Rules: mark_order_complete R8."""
    O, L1, L2, A1 = ready(db, S, l1={"transferred_at": TOLD}, l2={"transferred_at": TOLD})
    with POST(0):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert evs(db, O.id) == [("order_completed", "Transfer order marked complete", S.U2.id, None)]
    # Then 3
    assert naive(reread(db, TransferOrder, O.id).completed_at) == NOW


def test_tom_mc_06__posting_event_counts_reported_lines(db, S):
    """TOM-MC-06 — the posting event counts the lines the posting reports.
    Rules: mark_order_complete R8."""
    O, L1, L2, A1 = ready(db, S)
    with POST(1):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    rows = [e for e in ev_rows(db, O.id) if e.event_type == "inventory_posted"]
    assert len(rows) == 1
    # Then 3
    assert rows[0].description == "1 item(s) posted to inventory"
    assert rows[0].metadata_json == {"lines_posted": 1}
    assert rows[0].performed_by == S.U2.id


def test_tom_mc_07__missing_order_404(db, S):
    """TOM-MC-07 — a missing order is 404.
    Rules: mark_order_complete R1."""
    ready(db, S)
    before = counts(db)
    with POST(2) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, MISSING)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order with ID 999999999 not found"
    # Then 3
    assert pm.call_count == 0
    # Then 4
    assert counts(db) == before


def test_tom_mc_08__higher_workspace_404(db, S):
    """TOM-MC-08 — an order of a higher workspace is 404.
    Rules: mark_order_complete R1."""
    O9 = order(db, S, "O9")
    line(db, S, O9, 1)
    apr(db, S, O9, S.U5, 1, approved=True)
    before = snap(db, O9)
    with POST(1) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O9.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {O9.id} not found"
    # Then 3
    assert pm.call_count == 0
    # Then 4
    unchanged(db, O9, before)


def test_tom_mc_09__lower_workspace_404(db, S):
    """TOM-MC-09 — an order of a lower workspace is 404.
    Rules: mark_order_complete R1."""
    O0 = order(db, S, "O0")
    line(db, S, O0, 1, item_id=S.I0.id)
    before = snap(db, O0)
    with POST(1):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O0.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {O0.id} not found"
    # Then 3
    unchanged(db, O0, before)


def test_tom_mc_10__completed_returned_unchanged(db, S):
    """TOM-MC-10 — an already completed order is returned unchanged, before any other check.
    Rules: mark_order_complete R2."""
    O = order(db, S, completed=True)
    with POST(0) as pm:
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    session_clean(db)
    # Then 3
    o = reread(db, TransferOrder, O.id)
    assert naive(o.completed_at) == DONE
    assert o.completed_by == S.U1.id
    assert o.updated_by is None
    # Then 4
    assert evs(db, O.id) == []
    # Then 5
    assert pm.call_count == 0


def test_tom_mc_11__approvals_not_met_refused(db, S):
    """TOM-MC-11 — approvals not met are refused.
    Rules: mark_order_complete R3."""
    O, L1, L2, A1 = ready(db, S, a1={"approved": False, "approved_at": None})
    before = counts(db)
    with POST(2) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Required approvals are not met"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert pm.call_count == 0


def test_tom_mc_12__no_line_refused(db, S):
    """TOM-MC-12 — an order with no line is refused.
    Rules: mark_order_complete R4."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    with POST(0):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Add at least one item before completing"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_mc_13__approvals_before_lines(db, S):
    """TOM-MC-13 — approvals are checked before lines.
    Rules: mark_order_complete R3, R4."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    with POST(0):
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Required approvals are not met"


def test_tom_mc_14__required_zero_waives(db, S):
    """TOM-MC-14 — required 0 waives approval.
    Rules: mark_order_complete R3; approval_summary R2."""
    O, L1, L2, A1 = ready(db, S, required_approvals=0, a1={"approved": False, "approved_at": None})
    with POST(2):
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert naive(reread(db, TransferOrder, O.id).completed_at) == NOW


@xfail("BUG-1203")
def test_tom_mc_15__no_approvers_cannot_complete(db, S):
    """TOM-MC-15 — no approvers and "All assigned" cannot complete.
    Rules: mark_order_complete R3; approval_summary R4 [BUG-1203]."""
    O = order(db, S)
    line(db, S, O, 1)
    before = counts(db)
    with POST(1) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Required approvals are not met"
    # Then 3
    assert counts(db) == before
    # Then 4
    assert pm.call_count == 0


@xfail("BUG-2899")
def test_tom_mc_16__stored_same_route_refused(db, S):
    """TOM-MC-16 — a stored route with source = destination is refused.
    Rules: mark_order_complete R4a [BUG-2899]."""
    O = order(db, S, destination_location_id=S.F1.id, required_approvals=0)
    line(db, S, O, 1)
    before = counts(db)
    with POST(1) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Source and destination cannot be the same"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert pm.call_count == 0


def test_tom_mc_17__posting_error_unchanged(db, S):
    """TOM-MC-17 — a posting error reaches the caller unchanged.
    Rules: mark_order_complete R6."""
    O, L1, L2, A1 = ready(db, S)
    with POST(err=ERR) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value is ERR
    # Then 2
    assert pm.call_count == 1


def test_tom_mc_18__foreign_lines_not_stamped_nor_posted(db, S):
    """TOM-MC-18 — lines stored under another workspace are neither stamped nor posted.
    Rules: mark_order_complete R5, R6; _order_items R1."""
    O, L1, L2, A1 = ready(db, S)
    LB = line(db, S, O, 3, workspace_id=S.W2.id, item_id=S.IX.id)
    with POST(2) as pm:
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    assert reread(db, TransferOrderItem, LB.id).transferred_at is None
    # Then 3
    assert {i.id for i in posted(pm)["items"]} == {L1.id, L2.id}


@xfail("BUG-821")
def test_tom_mc_19__order_row_locked(db, S):
    """TOM-MC-19 — the order row is locked before the completed check.
    Rules: mark_order_complete R9 [BUG-821] (HR-10)."""
    O, L1, L2, A1 = ready(db, S)
    oid = O.id
    db.expunge_all()
    with POST(2), Recorder(db) as rec:
        result = _mc(db, S, oid)
        # Then 1
        assert result.id == oid
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_mc_20__completion_does_not_commit(db, S):
    """TOM-MC-20 — completion does not commit.
    Rules: mark_order_complete Side effects (flushed, not committed)."""
    O, L1, L2, A1 = ready(db, S)
    oid = O.id
    with POST(2), patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _mc(db, S, oid)
        # Then 1
        assert result.id == oid
        # Then 2
        assert naive(reread(db, TransferOrder, oid).completed_at) == NOW
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert reread(db, TransferOrder, oid).completed_at is None


def test_tom_mc_21__completed_same_route_returned_unchanged(db, S):
    """TOM-MC-21 — a completed order with source = destination is returned unchanged.
    Rules: mark_order_complete R2, R4b (G6)."""
    O = order(db, S, completed=True, destination_location_id=S.F1.id, required_approvals=0)
    line(db, S, O, 1)
    with POST(1) as pm:
        result = _mc(db, S, O.id)
    # Then 1
    assert result.id == O.id
    # Then 2
    session_clean(db)
    # Then 3
    o = reread(db, TransferOrder, O.id)
    assert naive(o.completed_at) == DONE
    assert o.completed_by == S.U1.id
    # Then 4
    assert evs(db, O.id) == []
    # Then 5
    assert pm.call_count == 0


def test_tom_mc_22__unmet_approvals_win_over_same_route(db, S):
    """TOM-MC-22 — unmet approvals win over source = destination.
    Rules: mark_order_complete R3, R4b (G6)."""
    O = order(db, S, destination_location_id=S.F1.id)
    line(db, S, O, 1)
    apr(db, S, O, S.U1, 1)
    before = counts(db)
    with POST(1) as pm:
        # Then 1
        with pytest.raises(HTTPException) as exc:
            _mc(db, S, O.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Required approvals are not met"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    assert pm.call_count == 0


# =========================================================================== #
# _ensure_catalog_item_not_on_to
# =========================================================================== #

def test_tom_eci_01__item_on_order_refused(db, S):
    """TOM-ECI-01 — an item already on the order is refused with its name.
    Rules: _ensure_catalog_item_not_on_to R1."""
    O = order(db, S)
    line(db, S, O, 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._ensure_catalog_item_not_on_to(db, O.id, S.I1.id, S.W1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Motor is already on this order"


def test_tom_eci_02__item_not_on_order_passes(db, S):
    """TOM-ECI-02 — an item not on the order passes.
    Rules: _ensure_catalog_item_not_on_to R2."""
    O = order(db, S)
    line(db, S, O, 1)
    result = M._ensure_catalog_item_not_on_to(db, O.id, S.I2.id, S.W1.id)
    # Then 1
    assert result is None


def test_tom_eci_03__excluded_line_does_not_count(db, S):
    """TOM-ECI-03 — the excluded line does not count.
    Rules: _ensure_catalog_item_not_on_to R1, R2."""
    O = order(db, S)
    L1 = line(db, S, O, 1)
    result = M._ensure_catalog_item_not_on_to(db, O.id, S.I1.id, S.W1.id, exclude_item_id=L1.id)
    # Then 1
    assert result is None


def test_tom_eci_04__foreign_item_named_by_id(db, S):
    """TOM-ECI-04 — an item outside the workspace is named by its id.
    Rules: _ensure_catalog_item_not_on_to R1."""
    O = order(db, S)
    line(db, S, O, 1, item_id=S.IX.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M._ensure_catalog_item_not_on_to(db, O.id, S.IX.id, S.W1.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == f"Item #{S.IX.id} is already on this order"


def test_tom_eci_05__foreign_lines_do_not_count(db, S):
    """TOM-ECI-05 — a line stored under other workspaces does not count.
    Rules: _ensure_catalog_item_not_on_to R1."""
    O = order(db, S)
    line(db, S, O, 1, workspace_id=S.W0.id)
    line(db, S, O, 2, workspace_id=S.W2.id)
    result = M._ensure_catalog_item_not_on_to(db, O.id, S.I1.id, S.W1.id)
    # Then 1
    assert result is None


def test_tom_eci_06__other_order_does_not_count(db, S):
    """TOM-ECI-06 — the same item on another order does not count.
    Rules: _ensure_catalog_item_not_on_to R1."""
    O = order(db, S)
    O2 = order(db, S, "O2")
    line(db, S, O2, 1)
    result = M._ensure_catalog_item_not_on_to(db, O.id, S.I1.id, S.W1.id)
    # Then 1
    assert result is None


# =========================================================================== #
# add_item
# =========================================================================== #

def _add_item(db, S, to_id, data):
    return M.add_item(db, to_id=to_id, data=data, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_ai_01__highest_plus_one_gaps_kept(db, S):
    """TOM-AI-01 — the new line takes the highest number + 1, gaps kept.
    Rules: add_item R4, R6."""
    O = order(db, S)
    line(db, S, O, 1)
    line(db, S, O, 3, item_id=S.I2.id)
    apr(db, S, O, S.U1, 1)
    result = _add_item(db, S, O.id, ITEM(S.IN, "7", notes="Top shelf"))
    # Then 1
    assert isinstance(result, TransferOrderItem)
    assert result.id is not None
    assert result.transfer_order_id == O.id
    assert result.item_id == S.IN.id
    assert result.line_number == 4
    assert result.notes == "Top shelf"
    # Then 2
    assert count_where(db, TransferOrderItem, transfer_order_id=O.id, workspace_id=S.W1.id) == 3
    # Then 3
    r = reread(db, TransferOrderItem, result.id)
    assert r.item_id == S.IN.id
    assert r.line_number == 4
    assert r.quantity == Decimal("7.00")
    assert r.notes == "Top shelf"
    assert r.workspace_id == S.W1.id


def test_tom_ai_02__first_line_is_one(db, S):
    """TOM-AI-02 — the first line of an empty order is number 1.
    Rules: add_item R4."""
    O = order(db, S)
    _add_item(db, S, O.id, ITEM(S.I1, "10"))
    # Then 1
    assert count_where(db, TransferOrderItem, transfer_order_id=O.id) == 1
    # Then 2
    r = lines_of(db, O.id)[0]
    assert r.line_number == 1
    assert r.item_id == S.I1.id


def test_tom_ai_03__item_added_event(db, S):
    """TOM-AI-03 — adding writes one item_added event.
    Rules: add_item R5."""
    O = order(db, S)
    line(db, S, O, 1)
    _add_item(db, S, O.id, ITEM(S.I2, "3"))
    # Then 1
    assert count_where(db, TransferOrderItem, transfer_order_id=O.id) == 2
    # Then 2
    assert evs(db, O.id) == [("item_added", "Item #2 added", S.U2.id, {"item_id": S.I2.id, "line_number": 2})]


@pytest.mark.parametrize("which, clean", [
    pytest.param(None, True, id="TOM-AI-04"),
    pytest.param("O9", False, id="TOM-AI-05"),
    pytest.param("O0", False, id="TOM-AI-06"),
])
def test_tom_ai__order_not_in_workspace_404(db, S, which, clean):
    """TOM-AI-04..06 — a missing order, or one of another workspace, is 404.
    Rules: add_item R1."""
    T = order(db, S, which or "O")
    to_id = T.id if which else MISSING
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_item(db, S, to_id, ITEM(S.I1, "1"))
    assert exc.value.status_code == 404
    if clean:
        # Then 2
        session_clean(db)
    # Then 2 / 3
    assert counts(db) == before


@pytest.mark.parametrize("completed, approved, item, status_code, detail", [
    pytest.param(True, False, "I1", 400, "Transfer order is complete", id="TOM-AI-07"),
    pytest.param(False, True, "I1", 400, "Withdraw all approvals before editing transfer items", id="TOM-AI-08"),
    pytest.param(True, False, "IX", 400, "Transfer order is complete", id="TOM-AI-15"),
])
def test_tom_ai__guards_refuse(db, S, completed, approved, item, status_code, detail):
    """TOM-AI-07/08/15 — completed or approved orders refuse a new line (guard before the item check).
    Rules: add_item R2, R4b (_guard_item_mutations R1, R2)."""
    O = order(db, S, completed=completed)
    if approved:
        apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_item(db, S, O.id, ITEM(getattr(S, item), "1"))
    assert exc.value.status_code == status_code
    # Then 2
    assert exc.value.detail == detail
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ai_09__item_already_on_order_refused(db, S):
    """TOM-AI-09 — an item already on the order is refused.
    Rules: add_item R3."""
    O = order(db, S)
    line(db, S, O, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_item(db, S, O.id, ITEM(S.I1, "2"))
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "Motor is already on this order"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


@pytest.mark.parametrize("item, on_line, clean", [
    pytest.param("IX", False, True, id="TOM-AI-10"),
    pytest.param("I0", False, False, id="TOM-AI-11"),
    pytest.param("IX", True, True, id="TOM-AI-14"),
    pytest.param(MISSING, False, True, id="TOM-AI-16"),
])
@xfail("BUG-1018")
def test_tom_ai__item_not_in_workspace_refused(db, S, item, on_line, clean):
    """TOM-AI-10/11/14/16 — an item of another workspace, or missing, is refused 404 (before the duplicate check).
    Rules: add_item R4a [BUG-1018], R4b."""
    O = order(db, S)
    if on_line:
        line(db, S, O, 1, item_id=S.IX.id)
    item_id = getattr(S, item).id if isinstance(item, str) else item
    data = (TransferOrderItemCreate(item_id=MISSING, quantity=Decimal("1")) if item == MISSING
            else ITEM(getattr(S, item), "2" if on_line else "1"))
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _add_item(db, S, O.id, data)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Item with ID {item_id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


@xfail("BUG-2892")
def test_tom_ai_12__order_row_locked(db, S):
    """TOM-AI-12 — the order row is locked before the item guards.
    Rules: _guard_item_mutations R4 [BUG-2892] (HR-10), via add_item."""
    O = order(db, S)
    oid, i1 = O.id, S.I1
    data = ITEM(i1, "1")
    w1, u2 = S.W1.id, S.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        M.add_item(db, to_id=oid, data=data, workspace_id=w1, user_id=u2)
    # Then 1
    assert count_where(db, TransferOrderItem, transfer_order_id=oid) == 1
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_ai_13__add_item_does_not_commit(db, S):
    """TOM-AI-13 — add_item does not commit.
    Rules: add_item (flushed, never committed)."""
    O = order(db, S)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        _add_item(db, S, oid, ITEM(S.I1, "1"))
        # Then 1
        assert count_where(db, TransferOrderItem, transfer_order_id=oid) == 1
        sp.rollback()
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert count_where(db, TransferOrderItem, transfer_order_id=oid) == 0


# =========================================================================== #
# update_item
# =========================================================================== #

def open_line(db, S, **l_over):
    """Open line: order O, L1 = line(O, 1), no approvers, no events."""
    O = order(db, S)
    return O, line(db, S, O, 1, **l_over)


def met_line(db, S, **l_over):
    """Met line: order O, L1 = line(O, 1), A1 = apr(O, U1, 1) approved, no events."""
    O = order(db, S)
    L1 = line(db, S, O, 1, **l_over)
    return O, L1, apr(db, S, O, S.U1, 1, approved=True)


def _ui(db, S, item_id, data):
    return M.update_item(db, item_id=item_id, data=data, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_ui_01__quantity_change_stored(db, S):
    """TOM-UI-01 — a quantity change is stored.
    Rules: update_item R3, R5, R10."""
    O, L1 = open_line(db, S)
    result = _ui(db, S, L1.id, IU(quantity=Decimal("25")))
    # Then 1
    assert result is L1
    assert result.quantity == Decimal("25")
    # Then 2
    assert L1 not in db.dirty
    # Then 3
    r = reread(db, TransferOrderItem, L1.id)
    assert r.quantity == Decimal("25.00")
    assert r.notes is None
    assert r.transferred_at is None


def test_tom_ui_02__notes_change_stored(db, S):
    """TOM-UI-02 — a notes change is stored.
    Rules: update_item R3, R5."""
    O, L1 = open_line(db, S)
    _ui(db, S, L1.id, IU(notes="Fragile"))
    # Then 1
    r = reread(db, TransferOrderItem, L1.id)
    assert r.notes == "Fragile"
    assert r.quantity == Decimal("10.00")


def test_tom_ui_03__missing_line_404(db, S):
    """TOM-UI-03 — a missing line is 404.
    Rules: update_item R1."""
    open_line(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, MISSING, IU(notes="x"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order item not found"
    # Then 3
    assert counts(db) == before


@pytest.mark.parametrize("which, clean", [
    pytest.param("O9", True, id="TOM-UI-04"),
    pytest.param("O0", False, id="TOM-UI-05"),
])
def test_tom_ui__foreign_line_404(db, S, which, clean):
    """TOM-UI-04/05 — a line of another workspace is 404.
    Rules: update_item R1."""
    T = order(db, S, which)
    N = line(db, S, T, 1)
    before = snap(db, N)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, N.id, IU(notes="x"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order item not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    unchanged(db, N, before)


def test_tom_ui_06__w1_line_on_foreign_order_404_on_order(db, S):
    """TOM-UI-06 — a W1 line on another workspace's order is 404 on the order.
    Rules: update_item R1."""
    O9 = order(db, S, "O9")
    LX = line(db, S, O9, 1, workspace_id=S.W1.id, item_id=S.I1.id)
    before = snap(db, LX)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, LX.id, IU(notes="x"))
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {O9.id} not found"
    # Then 3
    unchanged(db, LX, before)


def test_tom_ui_07__completed_refuses_every_edit(db, S):
    """TOM-UI-07 — a completed order refuses every line edit, even the transfer name.
    Rules: update_item R1."""
    O = order(db, S, completed=True)
    L1 = line(db, S, O, 1)
    before = snap(db, L1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, L1.id, IU(transferred_by="Rahim"))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"
    # Then 3
    session_clean(db)
    # Then 4
    unchanged(db, L1, before)


@pytest.mark.parametrize("data, clean", [
    pytest.param({"quantity": Decimal("25")}, True, id="TOM-UI-08"),
    pytest.param({"notes": "Fragile"}, False, id="TOM-UI-09"),
])
def test_tom_ui__approval_locks_quantity_and_notes(db, S, data, clean):
    """TOM-UI-08/09 — with an approval, a quantity or notes edit is refused.
    Rules: update_item R3."""
    O, L1, A1 = met_line(db, S)
    before = snap(db, L1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, L1.id, IU(**data))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Withdraw all approvals before editing transfer items"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    unchanged(db, L1, before)


def test_tom_ui_10__transfer_name_not_locked(db, S):
    """TOM-UI-10 — with an approval, the transfer name is not locked.
    Rules: update_item R3, R5."""
    O, L1, A1 = met_line(db, S)
    _ui(db, S, L1.id, IU(transferred_by="Rahim"))
    # Then 1
    r = reread(db, TransferOrderItem, L1.id)
    assert r.transferred_by == "Rahim"
    assert r.transferred_at is None
    # Then 2
    assert evs(db, O.id) == []


def test_tom_ui_11__recording_time_stored_and_logged(db, S):
    """TOM-UI-11 — recording a transfer time stores it and logs it.
    Rules: update_item R4, R5, R7, R9."""
    O, L1, A1 = met_line(db, S)
    n_ledger = counts(db)["inventory_ledger"]
    _ui(db, S, L1.id, IU(transferred_at=TOLD, transferred_by="Rahim"))
    # Then 1
    r = reread(db, TransferOrderItem, L1.id)
    assert naive(r.transferred_at) == TOLD
    assert r.transferred_by == "Rahim"
    # Then 2
    assert evs(db, O.id) == [("transfer_recorded", "Item #1 transfer recorded", S.U2.id, {"line_number": 1, "item_id": S.I1.id})]
    # Then 3
    assert counts(db)["inventory_ledger"] == n_ledger
    # Then 4
    assert reread(db, TransferOrder, O.id).completed_at is None


def test_tom_ui_12__recording_needs_approvals(db, S):
    """TOM-UI-12 — recording a transfer needs the approvals met.
    Rules: update_item R4."""
    O, L1 = open_line(db, S)
    apr(db, S, O, S.U1, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ui(db, S, L1.id, IU(transferred_at=TOLD))
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Required approvals are not met"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ui_13__future_time_accepted(db, S):
    """TOM-UI-13 — a future transfer time is accepted.
    Rules: update_item R4."""
    O, L1, A1 = met_line(db, S)
    _ui(db, S, L1.id, IU(transferred_at=datetime(2030, 1, 1, 8, 0)))
    # Then 1
    assert naive(reread(db, TransferOrderItem, L1.id).transferred_at) == datetime(2030, 1, 1, 8, 0)


def test_tom_ui_14__replacing_time_no_event(db, S):
    """TOM-UI-14 — replacing a recorded time stores the new one with no event.
    Rules: update_item R4, R7."""
    O, L1, A1 = met_line(db, S, transferred_at=TOLD)
    _ui(db, S, L1.id, IU(transferred_at=DONE))
    # Then 1
    assert naive(reread(db, TransferOrderItem, L1.id).transferred_at) == DONE
    # Then 2
    assert evs(db, O.id) == []


def test_tom_ui_15__unsent_fields_unchanged(db, S):
    """TOM-UI-15 — fields not sent are left unchanged.
    Rules: update_item R2, R2a (omitted fields)."""
    O, L1, A1 = met_line(db, S, transferred_at=TOLD, transferred_by="Rahim", notes="Top shelf")
    _ui(db, S, L1.id, IU(transferred_by="Karim"))
    # Then 1
    r = reread(db, TransferOrderItem, L1.id)
    assert r.transferred_by == "Karim"
    assert naive(r.transferred_at) == TOLD
    assert r.notes == "Top shelf"
    assert r.quantity == Decimal("10.00")


@xfail("BUG-2895")
def test_tom_ui_16__null_clears_transfer_and_logs(db, S):
    """TOM-UI-16 — an explicit null clears a recorded transfer and logs it.
    Rules: update_item R2a [BUG-2895], R8."""
    O, L1, A1 = met_line(db, S, transferred_at=TOLD, transferred_by="Rahim")
    _ui(db, S, L1.id, IU(transferred_at=None, transferred_by=None))
    # Then 1
    r = reread(db, TransferOrderItem, L1.id)
    assert r.transferred_at is None
    assert r.transferred_by is None
    # Then 2
    assert evs(db, O.id) == [("transfer_cleared", "Item #1 transfer cleared", S.U2.id, None)]


@xfail("BUG-2895")
def test_tom_ui_17__null_clears_notes(db, S):
    """TOM-UI-17 — an explicit null clears the notes.
    Rules: update_item R2a [BUG-2895]."""
    O, L1 = open_line(db, S, notes="Top shelf")
    _ui(db, S, L1.id, IU(notes=None))
    # Then 1
    assert reread(db, TransferOrderItem, L1.id).notes is None


@xfail("BUG-2895")
def test_tom_ui_18__null_quantity_refused_by_schema():
    """TOM-UI-18 — a null quantity is refused by the schema.
    Rules: update_item R2a [BUG-2895]."""
    # Then 1
    with pytest.raises(ValidationError) as exc:
        TransferOrderItemUpdate(quantity=None)
    assert exc.value.errors()[0]["loc"] == ("quantity",)


@xfail("BUG-2896")
def test_tom_ui_19__approved_flag_gone_from_schema():
    """TOM-UI-19 — the line `approved` flag is gone from the schema.
    Rules: update_item R6 [BUG-2896]."""
    fields = TransferOrderItemUpdate.model_fields
    # Then 1
    assert "approved" not in fields


@pytest.mark.parametrize("data, field, col, label, a, b", [
    pytest.param({"quantity": Decimal("25")}, "quantity", Decimal("25.00"), "Quantity", "10", "25", id="TOM-UI-20"),
    pytest.param({"notes": "Fragile"}, "notes", "Fragile", "Notes", "—", "Fragile", id="TOM-UI-21"),
])
@xfail("BUG-2900")
def test_tom_ui__change_logged_as_item_updated(db, S, data, field, col, label, a, b):
    """TOM-UI-20/21 — a quantity or notes change is logged as item_updated.
    Rules: update_item R8a [BUG-2900] (Q2)."""
    O, L1 = open_line(db, S)
    _ui(db, S, L1.id, IU(**data))
    # Then 1
    assert getattr(reread(db, TransferOrderItem, L1.id), field) == col
    # Then 2
    assert evs(db, O.id) == [("item_updated", "Item #1 updated", S.U2.id,
                              {"line_number": 1, "item_id": S.I1.id, "changes": [CH(field, label, a, b)]})]


def test_tom_ui_22__unchanged_quantity_no_event(db, S):
    """TOM-UI-22 — an unchanged quantity writes no event.
    Rules: update_item R8a (no change)."""
    O, L1 = open_line(db, S)
    _ui(db, S, L1.id, IU(quantity=Decimal("10")))
    # Then 1
    assert reread(db, TransferOrderItem, L1.id).quantity == Decimal("10.00")
    # Then 2
    assert evs(db, O.id) == []


@xfail("BUG-2892")
def test_tom_ui_23__order_row_locked(db, S):
    """TOM-UI-23 — the order row is locked before the item guards.
    Rules: _guard_item_mutations R4 [BUG-2892] (HR-10), via update_item."""
    O, L1 = open_line(db, S)
    lid, w1, u2 = L1.id, S.W1.id, S.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        M.update_item(db, item_id=lid, data=IU(quantity=Decimal("25")), workspace_id=w1, user_id=u2)
    # Then 1
    assert reread(db, TransferOrderItem, lid).quantity == Decimal("25.00")
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_ui_24__update_item_does_not_commit(db, S):
    """TOM-UI-24 — update_item does not commit.
    Rules: update_item (flushed, never committed)."""
    O, L1 = open_line(db, S)
    lid = L1.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        _ui(db, S, lid, IU(notes="Fragile"))
        # Then 1
        assert reread(db, TransferOrderItem, lid).notes == "Fragile"
        sp.rollback()
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert reread(db, TransferOrderItem, lid).notes is None


# =========================================================================== #
# remove_item
# =========================================================================== #

def _ri(db, S, item_id):
    return M.remove_item(db, item_id=item_id, workspace_id=S.W1.id, user_id=S.U2.id)


def test_tom_ri_01__line_deleted_others_keep_numbers(db, S):
    """TOM-RI-01 — the line is deleted, the others keep their numbers.
    Rules: remove_item R3."""
    O = order(db, S)
    L1 = line(db, S, O, 1)
    L2 = line(db, S, O, 2, item_id=S.I2.id)
    L3 = line(db, S, O, 3, item_id=S.IN.id)
    l2id = L2.id
    result = _ri(db, S, l2id)
    # Then 1
    assert result.id == l2id
    # Then 2
    assert count_where(db, TransferOrderItem, id=l2id) == 0
    # Then 3
    assert reread(db, TransferOrderItem, L1.id).line_number == 1
    # Then 4
    assert reread(db, TransferOrderItem, L3.id).line_number == 3
    # Then 5
    assert evs(db, O.id) == [("item_removed", "Item #2 removed", S.U2.id, None)]


def test_tom_ri_02__missing_line_404(db, S):
    """TOM-RI-02 — a missing line is 404.
    Rules: remove_item R1."""
    O = order(db, S)
    line(db, S, O, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, S, MISSING)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order item not found"
    # Then 3
    assert counts(db) == before


def test_tom_ri_03__foreign_line_404_and_stays(db, S):
    """TOM-RI-03 — a line of another workspace is 404 and stays.
    Rules: remove_item R1."""
    O9 = order(db, S, "O9")
    N1 = line(db, S, O9, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, S, N1.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order item not found"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ri_04__w1_line_on_foreign_order_404(db, S):
    """TOM-RI-04 — a W1 line on another workspace's order is 404.
    Rules: remove_item R1."""
    O9 = order(db, S, "O9")
    LX = line(db, S, O9, 1, workspace_id=S.W1.id, item_id=S.I1.id)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, S, LX.id)
    assert exc.value.status_code == 404
    # Then 2
    assert counts(db) == before


@pytest.mark.parametrize("completed, detail", [
    pytest.param(True, "Transfer order is complete", id="TOM-RI-05"),
    pytest.param(False, "Withdraw all approvals before editing transfer items", id="TOM-RI-06"),
])
def test_tom_ri__guards_keep_lines(db, S, completed, detail):
    """TOM-RI-05/06 — a completed or approved order keeps its lines.
    Rules: remove_item R2 (_guard_item_mutations R1, R2)."""
    O = order(db, S, completed=completed)
    L1 = line(db, S, O, 1)
    if not completed:
        apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ri(db, S, L1.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == detail
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ri_07__remove_item_does_not_commit(db, S):
    """TOM-RI-07 — remove_item does not commit.
    Rules: remove_item (flushed, never committed)."""
    O = order(db, S)
    L1 = line(db, S, O, 1)
    lid = L1.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _ri(db, S, lid)
        # Then 1
        assert result.id == lid
        # Then 2
        assert count_where(db, TransferOrderItem, id=lid) == 0
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert count_where(db, TransferOrderItem, id=lid) == 1


@xfail("BUG-2892")
def test_tom_ri_08__order_row_locked(db, S):
    """TOM-RI-08 — the order row is locked before the item guards.
    Rules: _guard_item_mutations R4 [BUG-2892] (HR-10), via remove_item."""
    O = order(db, S)
    L1 = line(db, S, O, 1)
    lid, w1, u2 = L1.id, S.W1.id, S.U2.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.remove_item(db, item_id=lid, workspace_id=w1, user_id=u2)
        # Then 1
        assert result.id == lid
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


# =========================================================================== #
# get_items
# =========================================================================== #

def test_tom_gi_01__lines_by_number(db, S):
    """TOM-GI-01 — the order's lines by line number.
    Rules: get_items R2."""
    O = order(db, S)
    L2 = line(db, S, O, 2, item_id=S.I2.id)
    L1 = line(db, S, O, 1)
    line(db, S, O, 3, workspace_id=S.W2.id, item_id=S.IX.id)
    result = M.get_items(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert ids(result) == [L1.id, L2.id]


def test_tom_gi_02__no_lines_empty(db, S):
    """TOM-GI-02 — no lines gives an empty list.
    Rules: get_items R2."""
    O = order(db, S)
    result = M.get_items(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert list(result) == []


@pytest.mark.parametrize("which", [
    pytest.param(None, id="TOM-GI-03"),
    pytest.param("O9", id="TOM-GI-04"),
])
def test_tom_gi__order_not_in_workspace_404(db, S, which):
    """TOM-GI-03/04 — a missing order, or one of another workspace, is 404.
    Rules: get_items R1."""
    T = order(db, S, which or "O")
    if which:
        line(db, S, T, 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, to_id=T.id if which else MISSING, workspace_id=S.W1.id)
    assert exc.value.status_code == 404


# =========================================================================== #
# list_approvers
# =========================================================================== #

def trip(result):
    return [(a.id, p.id if p else None, pos) for a, p, pos in result]


def test_tom_la_01__by_assignment_time(db, S):
    """TOM-LA-01 — approvers by assignment time, with profile and position.
    Rules: list_approvers R2, R3."""
    O = order(db, S)
    A1 = apr(db, S, O, S.U1, 5)
    A2 = apr(db, S, O, S.U2, 2)
    result = M.list_approvers(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert trip(result) == [(A2.id, S.U2.id, "Factory Head"), (A1.id, S.U1.id, "Store Manager")]


def test_tom_la_02__position_any_status(db, S):
    """TOM-LA-02 — the position comes whatever the membership status; none without one.
    Rules: list_approvers R3."""
    O = order(db, S)
    A4 = apr(db, S, O, S.U4, 1)
    A3 = apr(db, S, O, S.U3, 2)
    result = M.list_approvers(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert trip(result) == [(A4.id, S.U4.id, "Clerk"), (A3.id, S.U3.id, None)]


def test_tom_la_03__other_workspace_membership_no_position(db, S):
    """TOM-LA-03 — a membership in another workspace gives no position.
    Rules: list_approvers R3."""
    O = order(db, S)
    A5 = apr(db, S, O, S.U5, 1)
    result = M.list_approvers(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert trip(result) == [(A5.id, S.U5.id, None)]


def test_tom_la_04__foreign_rows_not_listed(db, S):
    """TOM-LA-04 — approver rows stored under other workspaces are not listed.
    Rules: list_approvers R2."""
    O = order(db, S)
    apr(db, S, O, S.U3, 1, workspace_id=S.W0.id)
    A1 = apr(db, S, O, S.U1, 2)
    apr(db, S, O, S.U2, 3, workspace_id=S.W2.id)
    result = M.list_approvers(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert trip(result) == [(A1.id, S.U1.id, "Store Manager")]


@pytest.mark.parametrize("which", [
    pytest.param(None, id="TOM-LA-05"),
    pytest.param("O9", id="TOM-LA-06"),
])
def test_tom_la__order_not_in_workspace_404(db, S, which):
    """TOM-LA-05/06 — a missing order, or one of another workspace, is 404.
    Rules: list_approvers R1."""
    T = order(db, S, which or "O")
    if which:
        apr(db, S, T, S.U5, 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_approvers(db, to_id=T.id if which else MISSING, workspace_id=S.W1.id)
    assert exc.value.status_code == 404


@xfail("BUG-2902")
def test_tom_la_07__profiles_and_members_read_together(db, S):
    """TOM-LA-07 — profiles and memberships are read together.
    Rules: list_approvers R4 [BUG-2902]."""
    O = order(db, S)
    for i, u in enumerate((S.U1, S.U2, S.U3), start=1):
        apr(db, S, O, u, i)
    oid, w1 = O.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.list_approvers(db, to_id=oid, workspace_id=w1)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert len(rec.sel("profiles")) <= 1
    # Then 3
    assert len(rec.sel("workspace_members")) <= 1


# =========================================================================== #
# approval_summary / approvals_met
# =========================================================================== #

@pytest.mark.parametrize("required, aprs, expected", [
    pytest.param(None, [("U1", True), ("U2", False)], (1, 2, False), id="TOM-AS-01"),
    pytest.param(None, [("U1", True), ("U2", True)], (2, 2, True), id="TOM-AS-02"),
    pytest.param(1, [("U1", True), ("U2", False)], (1, 1, True), id="TOM-AS-03"),
    pytest.param(0, [("U1", False)], (0, 0, True), id="TOM-AS-04"),
    pytest.param(3, [("U1", True), ("U2", True)], (2, 3, False), id="TOM-AS-05"),
])
def test_tom_as__summary(db, S, required, aprs, expected):
    """TOM-AS-01..05 — approved count, required (explicit or approver count) and met.
    Rules: approval_summary R1, R2, R3."""
    O = order(db, S, required_approvals=required)
    for h, (u, ok) in enumerate(aprs, start=1):
        apr(db, S, O, getattr(S, u), h, approved=ok)
    result = M.approval_summary(db, O)
    # Then 1
    assert result == expected


def test_tom_as_06__foreign_approvals_not_counted(db, S):
    """TOM-AS-06 — approvals stored under other workspaces are not counted.
    Rules: approval_summary R1."""
    O = order(db, S, required_approvals=1)
    apr(db, S, O, S.U3, 1, workspace_id=S.W0.id, approved=True)
    apr(db, S, O, S.U1, 2)
    apr(db, S, O, S.U2, 3, workspace_id=S.W2.id, approved=True)
    result = M.approval_summary(db, O)
    # Then 1
    assert result == (0, 1, False)


def test_tom_as_07__order_own_workspace_used(db, S):
    """TOM-AS-07 — the order's own workspace is used, not a fixed one.
    Rules: approval_summary R1."""
    O9 = order(db, S, "O9")
    apr(db, S, O9, S.U5, 1, approved=True)
    result = M.approval_summary(db, O9)
    # Then 1
    assert result == (1, 1, True)


@xfail("BUG-1203")
def test_tom_as_08__no_approvers_all_assigned_not_met(db, S):
    """TOM-AS-08 — no approvers and "All assigned" is 0 of 1, not met.
    Rules: approval_summary R4 [BUG-1203] (owner)."""
    O = order(db, S)
    result = M.approval_summary(db, O)
    # Then 1
    assert result == (0, 1, False)


@pytest.mark.parametrize("second, expected", [
    pytest.param(False, True, id="TOM-AM-01"),
    pytest.param(True, False, id="TOM-AM-02"),
])
def test_tom_am__met_returned(db, S, second, expected):
    """TOM-AM-01/02 — approvals_met returns the summary's met.
    Rules: approvals_met R1."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    if second:
        apr(db, S, O, S.U2, 2)
    result = M.approvals_met(db, O)
    # Then 1
    assert result is expected


# =========================================================================== #
# add_approver
# =========================================================================== #

def _aa(db, S, to_id, user_id):
    return M.add_approver(db, to_id=to_id, user_id=user_id, workspace_id=S.W1.id, assigned_by=S.U1.id)


def test_tom_aa_01__active_member_added_and_logged(db, S):
    """TOM-AA-01 — an active member is added and logged.
    Rules: add_approver R4."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    result = _aa(db, S, O.id, S.U2.id)
    # Then 1
    assert result.user_id == S.U2.id
    assert result.id is not None
    # Then 2
    r = reread(db, TransferOrderApprover, result.id)
    assert r.transfer_order_id == O.id
    assert r.workspace_id == S.W1.id
    assert r.assigned_by == S.U1.id
    assert r.approved is False
    # Then 3
    assert evs(db, O.id) == [("approver_added", "Added Nadia Islam as approver", S.U1.id,
                              {"user_id": S.U2.id, "user_name": "Nadia Islam"})]


def test_tom_aa_02__adding_raises_all_assigned(db, S):
    """TOM-AA-02 — adding raises "All assigned".
    Rules: add_approver R4."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    result = _aa(db, S, O.id, S.U2.id)
    # Then 1
    assert result.user_id == S.U2.id
    # Then 2
    assert SUMMARY(db, O.id) == (1, 2, False)


@pytest.mark.parametrize("which, clean", [
    pytest.param(None, False, id="TOM-AA-03"),
    pytest.param("O9", True, id="TOM-AA-04"),
])
def test_tom_aa__order_not_in_workspace_404(db, S, which, clean):
    """TOM-AA-03/04 — a missing order, or one of another workspace, is 404.
    Rules: add_approver R1."""
    T = order(db, S, which or "O")
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _aa(db, S, T.id if which else MISSING, S.U2.id)
    assert exc.value.status_code == 404
    if clean:
        # Then 2
        session_clean(db)
    # Then 2 / 3
    assert counts(db) == before


@pytest.mark.parametrize("user, clean", [
    pytest.param("U5", True, id="TOM-AA-05"),
    pytest.param("U4", False, id="TOM-AA-06"),
])
def test_tom_aa__not_active_member_refused(db, S, user, clean):
    """TOM-AA-05/06 — a member of another workspace only, or an inactive member, is refused.
    Rules: add_approver R2."""
    O = order(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _aa(db, S, O.id, getattr(S, user).id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "User is not an active member of this workspace"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


def test_tom_aa_07__existing_approver_refused(db, S):
    """TOM-AA-07 — an existing approver is refused.
    Rules: add_approver R3."""
    O = order(db, S)
    apr(db, S, O, S.U2, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _aa(db, S, O.id, S.U2.id)
    assert exc.value.status_code == 409
    # Then 2
    assert exc.value.detail == "User is already an approver for this order"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_aa_08__approver_of_other_order_does_not_count(db, S):
    """TOM-AA-08 — being an approver of another order does not count.
    Rules: add_approver R3."""
    O = order(db, S)
    O2 = order(db, S, "O2")
    apr(db, S, O2, S.U2, 1)
    result = _aa(db, S, O.id, S.U2.id)
    # Then 1
    assert result.user_id == S.U2.id
    # Then 2
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 1


@xfail("BUG-2897")
def test_tom_aa_09__completed_refuses_new_approver(db, S):
    """TOM-AA-09 — a completed order refuses a new approver.
    Rules: add_approver R5 [BUG-2897]."""
    O = order(db, S, completed=True)
    apr(db, S, O, S.U1, 1, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _aa(db, S, O.id, S.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_aa_10__add_approver_does_not_commit(db, S):
    """TOM-AA-10 — add_approver does not commit.
    Rules: add_approver (flushed, never committed)."""
    O = order(db, S)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _aa(db, S, oid, S.U2.id)
        # Then 1
        assert result.user_id == S.U2.id
        # Then 2
        assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 1
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 0


@xfail("BUG-2892")
def test_tom_aa_11__order_row_locked(db, S):
    """TOM-AA-11 — the order row is locked before the completed check.
    Rules: add_approver R6 [BUG-2892] (HR-10, G10)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    oid, u1, u2, w1 = O.id, S.U1.id, S.U2.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        M.add_approver(db, to_id=oid, user_id=u2, workspace_id=w1, assigned_by=u1)
    # Then 1
    assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 2
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_aa_12__empty_profile_name_used(db, S):
    """TOM-AA-12 — an empty profile name is used as stored.
    Rules: add_approver R4, R4a (G4)."""
    U6 = make_profile(db, name="")
    _add(db, WorkspaceMember(workspace_id=S.W1.id, user_id=U6.id, role="member", status="active", position=None))
    O = order(db, S)
    result = _aa(db, S, O.id, U6.id)
    # Then 1
    assert result.user_id == U6.id
    # Then 2
    assert evs(db, O.id) == [("approver_added", "Added  as approver", S.U1.id, {"user_id": U6.id, "user_name": ""})]


# =========================================================================== #
# remove_approver
# =========================================================================== #

def _ra(db, S, to_id, user_id):
    return M.remove_approver(db, to_id=to_id, user_id=user_id, workspace_id=S.W1.id, performed_by=S.U1.id)


def test_tom_ra_01__approved_approver_removed_and_logged(db, S):
    """TOM-RA-01 — an approved approver is removed and logged.
    Rules: remove_approver R2, R2b."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    A2 = apr(db, S, O, S.U2, 2, approved=True)
    a2id = A2.id
    result = _ra(db, S, O.id, S.U2.id)
    # Then 1
    assert result is None
    # Then 2
    assert count_where(db, TransferOrderApprover, id=a2id) == 0
    # Then 3
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 1
    # Then 4
    assert evs(db, O.id) == [("approver_removed", "Removed Nadia Islam as approver", S.U1.id,
                              {"user_id": S.U2.id, "user_name": "Nadia Islam"})]


def test_tom_ra_02__no_performed_by_no_performer(db, S):
    """TOM-RA-02 — without performed_by the event has no performer.
    Rules: remove_approver R2."""
    O = order(db, S)
    apr(db, S, O, S.U2, 1)
    M.remove_approver(db, to_id=O.id, user_id=S.U2.id, workspace_id=S.W1.id)
    # Then 1
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 0
    # Then 2
    rows = ev_rows(db, O.id)
    assert len(rows) == 1
    assert rows[0].event_type == "approver_removed"
    assert rows[0].performed_by is None


def test_tom_ra_03__not_an_approver_404(db, S):
    """TOM-RA-03 — someone not an approver is 404.
    Rules: remove_approver R1."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ra(db, S, O.id, S.U2.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ra_04__foreign_order_approver_404(db, S):
    """TOM-RA-04 — an approver of another workspace's order is 404.
    Rules: remove_approver R1."""
    O9 = order(db, S, "O9")
    apr(db, S, O9, S.U5, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ra(db, S, O9.id, S.U5.id)
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Approver not found"
    # Then 3
    assert counts(db) == before


def test_tom_ra_05__removal_can_make_approvals_met(db, S):
    """TOM-RA-05 — removing the other approver can make approvals met.
    Rules: remove_approver R3."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U2, 2)
    _ra(db, S, O.id, S.U2.id)
    # Then 1
    assert count_where(db, TransferOrderApprover, transfer_order_id=O.id) == 1
    # Then 2
    assert SUMMARY(db, O.id) == (1, 1, True)


@xfail("BUG-2897")
def test_tom_ra_06__completed_keeps_approvers(db, S):
    """TOM-RA-06 — a completed order keeps its approvers.
    Rules: remove_approver R4 [BUG-2897]."""
    O = order(db, S, completed=True)
    apr(db, S, O, S.U1, 1, approved=True)
    apr(db, S, O, S.U2, 2, approved=True)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _ra(db, S, O.id, S.U2.id)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_ra_07__remove_approver_does_not_commit(db, S):
    """TOM-RA-07 — remove_approver does not commit.
    Rules: remove_approver (flushed, never committed)."""
    O = order(db, S)
    apr(db, S, O, S.U2, 1)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        _ra(db, S, oid, S.U2.id)
        # Then 1
        assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 0
        sp.rollback()
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 1


@xfail("BUG-2892")
def test_tom_ra_08__order_row_locked(db, S):
    """TOM-RA-08 — the order row is locked before the completed check.
    Rules: remove_approver R5 [BUG-2892] (HR-10, G10)."""
    O = order(db, S)
    apr(db, S, O, S.U1, 1)
    apr(db, S, O, S.U2, 2)
    oid, u1, u2, w1 = O.id, S.U1.id, S.U2.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        M.remove_approver(db, to_id=oid, user_id=u2, workspace_id=w1, performed_by=u1)
    # Then 1
    assert count_where(db, TransferOrderApprover, transfer_order_id=oid) == 1
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


# =========================================================================== #
# set_approval
# =========================================================================== #

def ready_to_approve(db, S, *, a1_approved=False, **o_over):
    """Ready to approve: order O, L1 = line(O, 1), A1 = apr(O, U1, 1) (not approved), no events."""
    O = order(db, S, **o_over)
    L1 = line(db, S, O, 1)
    return O, L1, apr(db, S, O, S.U1, 1, approved=a1_approved)


def _sa(db, S, to_id, user_id, approved):
    return M.set_approval(db, to_id=to_id, user_id=user_id, workspace_id=S.W1.id, approved=approved)


def test_tom_sa_01__approving_stamps_and_logs(db, S):
    """TOM-SA-01 — approving stamps the row and logs it.
    Rules: set_approval R3, R4."""
    O, L1, A1 = ready_to_approve(db, S)
    result = _sa(db, S, O.id, S.U1.id, True)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is True
    assert naive(a.approved_at) == NOW
    # Then 3
    assert evs(db, O.id) == [("approved", "Approved transfer order", S.U1.id, None)]


def test_tom_sa_02__withdrawing_clears_and_logs(db, S):
    """TOM-SA-02 — withdrawing clears the stamp and logs it.
    Rules: set_approval R4."""
    O, L1, A1 = ready_to_approve(db, S, a1_approved=True)
    result = _sa(db, S, O.id, S.U1.id, False)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is False
    assert a.approved_at is None
    # Then 3
    assert evs(db, O.id) == [("approval_withdrawn", "Withdrew approval", S.U1.id, None)]


def test_tom_sa_03__not_an_approver_refused(db, S):
    """TOM-SA-03 — someone not an approver is refused.
    Rules: set_approval R1."""
    O, L1, A1 = ready_to_approve(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, O.id, S.U2.id, True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before


def test_tom_sa_04__foreign_order_approver_refused(db, S):
    """TOM-SA-04 — an approver of another workspace's order is refused.
    Rules: set_approval R1."""
    O9 = order(db, S, "O9")
    line(db, S, O9, 1)
    Z1 = apr(db, S, O9, S.U5, 1)
    before = snap(db, Z1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, O9.id, S.U5.id, True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 3
    unchanged(db, Z1, before)


def test_tom_sa_05__approver_check_before_order_lookup(db, S):
    """TOM-SA-05 — the approver check runs before the order lookup.
    Rules: set_approval R1."""
    ready_to_approve(db, S)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, MISSING, S.U1.id, True)
    assert exc.value.status_code == 403
    # Then 2
    assert exc.value.detail == "You are not an assigned approver for this order"


def test_tom_sa_06__approver_row_order_not_in_workspace_404(db, S):
    """TOM-SA-06 — an approver row whose order is not in the workspace is 404.
    Rules: set_approval R2."""
    O9 = order(db, S, "O9")
    line(db, S, O9, 1)
    AX = apr(db, S, O9, S.U1, 1, workspace_id=S.W1.id)
    before = snap(db, AX)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, O9.id, S.U1.id, True)
    assert exc.value.status_code == 404
    # Then 2
    unchanged(db, AX, before)


@pytest.mark.parametrize("dest, lines, detail, clean", [
    pytest.param(0, True, "Set source and destination before approving", True, id="TOM-SA-07"),
    pytest.param("F1", True, "Source and destination cannot be the same", False, id="TOM-SA-08"),
    pytest.param(None, False, "Add at least one item before approving", False, id="TOM-SA-09"),
])
def test_tom_sa__approving_needs_readiness(db, S, dest, lines, detail, clean):
    """TOM-SA-07..09 — approving needs a defined route that goes somewhere, and a line.
    Rules: set_approval R3."""
    over = {}
    if dest is not None:
        over["destination_location_id"] = getattr(S, dest).id if isinstance(dest, str) else dest
    O = order(db, S, **over)
    if lines:
        line(db, S, O, 1)
    apr(db, S, O, S.U1, 1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, O.id, S.U1.id, True)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == detail
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


def test_tom_sa_10__withdrawing_no_readiness_check(db, S):
    """TOM-SA-10 — withdrawing has no readiness check.
    Rules: set_approval R3."""
    O = order(db, S, destination_location_id=0)
    A1 = apr(db, S, O, S.U1, 1, approved=True)
    result = _sa(db, S, O.id, S.U1.id, False)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is False
    assert a.approved_at is None


@xfail("BUG-2898")
def test_tom_sa_11__approving_twice_keeps_first_stamp(db, S):
    """TOM-SA-11 — approving twice keeps the first stamp and logs nothing.
    Rules: set_approval R6 [BUG-2898]."""
    O, L1, A1 = ready_to_approve(db, S, a1_approved=True)
    result = _sa(db, S, O.id, S.U1.id, True)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is True
    # Then 3
    assert naive(a.approved_at) == TOLD
    # Then 4
    assert evs(db, O.id) == []


def test_tom_sa_12__approving_twice_still_approved(db, S):
    """TOM-SA-12 — approving twice still leaves the row approved.
    Rules: set_approval R4, R6 (the side that holds today)."""
    O, L1, A1 = ready_to_approve(db, S, a1_approved=True)
    result = _sa(db, S, O.id, S.U1.id, True)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is True
    assert a.approved_at is not None


@xfail("BUG-2898")
def test_tom_sa_13__withdrawing_unapproved_logs_nothing(db, S):
    """TOM-SA-13 — withdrawing when not approved logs nothing.
    Rules: set_approval R6 [BUG-2898]."""
    O, L1, A1 = ready_to_approve(db, S)
    result = _sa(db, S, O.id, S.U1.id, False)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is False
    assert a.approved_at is None
    # Then 3
    assert evs(db, O.id) == []


@pytest.mark.parametrize("a1_approved, approved", [
    pytest.param(False, True, id="TOM-SA-14"),
    pytest.param(True, False, id="TOM-SA-15"),
])
@xfail("BUG-2897")
def test_tom_sa__completed_refuses_both_directions(db, S, a1_approved, approved):
    """TOM-SA-14/15 — a completed order refuses an approval and a withdrawal.
    Rules: set_approval R5 [BUG-2897]."""
    O, L1, A1 = ready_to_approve(db, S, a1_approved=a1_approved, completed=True)
    before_a = snap(db, A1)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        _sa(db, S, O.id, S.U1.id, approved)
    assert exc.value.status_code == 400
    # Then 2
    assert exc.value.detail == "Transfer order is complete"
    # Then 3
    session_clean(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    unchanged(db, A1, before_a)


@xfail("BUG-2892")
def test_tom_sa_16__order_row_locked(db, S):
    """TOM-SA-16 — the order row is locked before the checks.
    Rules: set_approval R7 [BUG-2892] (HR-10)."""
    O, L1, A1 = ready_to_approve(db, S)
    oid, aid, u1, w1 = O.id, A1.id, S.U1.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.set_approval(db, to_id=oid, user_id=u1, workspace_id=w1, approved=True)
        # Then 1
        assert result.id == aid
    # Then 2
    assert rec.locks_before_first_write("transfer_orders")


def test_tom_sa_17__set_approval_does_not_commit(db, S):
    """TOM-SA-17 — set_approval does not commit.
    Rules: set_approval (flushed, never committed)."""
    O, L1, A1 = ready_to_approve(db, S)
    oid, aid = O.id, A1.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = _sa(db, S, oid, S.U1.id, True)
        # Then 1
        assert result.id == aid
        # Then 2
        assert reread(db, TransferOrderApprover, aid).approved is True
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert reread(db, TransferOrderApprover, aid).approved is False


def test_tom_sa_18__withdrawing_unapproved_still_unapproved(db, S):
    """TOM-SA-18 — withdrawing when not approved still leaves the row unapproved.
    Rules: set_approval R4, R6 (the side that holds today)."""
    O, L1, A1 = ready_to_approve(db, S)
    result = _sa(db, S, O.id, S.U1.id, False)
    # Then 1
    assert result.id == A1.id
    # Then 2
    a = reread(db, TransferOrderApprover, A1.id)
    assert a.approved is False
    assert a.approved_at is None


# =========================================================================== #
# log_event
# =========================================================================== #

def test_tom_le_01__one_row_with_given_values(db, S):
    """TOM-LE-01 — one row with the given values.
    Rules: log_event R1."""
    O = order(db, S)
    result = M.log_event(db, to_id=O.id, workspace_id=S.W1.id, event_type="attachment_added",
                         description="File added", performed_by=S.U2.id, metadata={"file": "a.pdf", "n": 2})
    # Then 1
    assert result.id is not None
    # Then 2
    r = reread(db, TransferOrderEvent, result.id)
    assert r.transfer_order_id == O.id
    assert r.workspace_id == S.W1.id
    assert r.event_type == "attachment_added"
    assert r.description == "File added"
    assert r.performed_by == S.U2.id
    # Then 3
    assert r.metadata_json == {"file": "a.pdf", "n": 2}
    assert r.created_at is not None


def test_tom_le_02__defaults_none(db, S):
    """TOM-LE-02 — performer and metadata default to none.
    Rules: log_event R1."""
    O = order(db, S)
    result = M.log_event(db, to_id=O.id, workspace_id=S.W1.id, event_type="note", description="Plain")
    # Then 1
    assert result.id is not None
    # Then 2
    r = reread(db, TransferOrderEvent, result.id)
    assert r.performed_by is None
    assert r.metadata_json is None
    assert r.event_type == "note"


@pytest.mark.parametrize("which, clean", [
    pytest.param("O9", True, id="TOM-LE-03"),
    pytest.param("O0", False, id="TOM-LE-04"),
])
@xfail("BUG-1192")
def test_tom_le__foreign_order_refused(db, S, which, clean):
    """TOM-LE-03/04 — an order of another workspace is refused.
    Rules: log_event R2 [BUG-1192] (HR-16)."""
    T = order(db, S, which)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.log_event(db, to_id=T.id, workspace_id=S.W1.id, event_type="note", description="Plain")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {T.id} not found"
    if clean:
        # Then 3
        session_clean(db)
    # Then 3 / 4
    assert counts(db) == before


@xfail("BUG-1192")
def test_tom_le_05__missing_order_404_not_db_error(db, S):
    """TOM-LE-05 — a missing order is 404, not a database error.
    Rules: log_event R2 [BUG-1192]."""
    order(db, S)
    before = counts(db)
    # Then 1
    with pytest.raises(HTTPException) as exc, db.begin_nested():
        M.log_event(db, to_id=MISSING, workspace_id=S.W1.id, event_type="note", description="Plain")
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Transfer order with ID 999999999 not found"
    # Then 3
    assert counts(db) == before


def test_tom_le_06__log_event_does_not_commit(db, S):
    """TOM-LE-06 — log_event does not commit.
    Rules: log_event R1 (flushes, never commits)."""
    O = order(db, S)
    oid = O.id
    with patch.object(db, "commit", wraps=db.commit) as cm:
        sp = db.begin_nested()
        result = M.log_event(db, to_id=oid, workspace_id=S.W1.id, event_type="note", description="Plain")
        # Then 1
        assert result.id is not None
        # Then 2
        assert count_where(db, TransferOrderEvent, transfer_order_id=oid) == 1
        sp.rollback()
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert count_where(db, TransferOrderEvent, transfer_order_id=oid) == 0


# =========================================================================== #
# list_events
# =========================================================================== #

def pairs(result):
    return [(e.id, p.id if p else None) for e, p in result]


def test_tom_lev_01__newest_first_ties_by_id(db, S):
    """TOM-LEV-01 — newest first, ties by id descending, with the performer's profile.
    Rules: list_events R2, R3."""
    O = order(db, S)
    E1 = ev(db, O, "created", 2, performed_by=S.U2.id)
    E2 = ev(db, O, "note", 5)
    E3 = ev(db, O, "note", 2, performed_by=S.U1.id)
    result = M.list_events(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert pairs(result) == [(E2.id, None), (E3.id, S.U1.id), (E1.id, S.U2.id)]


def test_tom_lev_02__foreign_events_not_listed(db, S):
    """TOM-LEV-02 — events stored under other workspaces are not listed.
    Rules: list_events R2."""
    O = order(db, S)
    ev(db, O, "note", 3, workspace_id=S.W0.id)
    E1 = ev(db, O, "created", 1)
    ev(db, O, "note", 4, workspace_id=S.W2.id)
    result = M.list_events(db, to_id=O.id, workspace_id=S.W1.id)
    # Then 1
    assert pairs(result) == [(E1.id, None)]


@pytest.mark.parametrize("which", [
    pytest.param(None, id="TOM-LEV-03"),
    pytest.param("O9", id="TOM-LEV-04"),
])
def test_tom_lev__order_not_in_workspace_404(db, S, which):
    """TOM-LEV-03/04 — a missing order, or one of another workspace, is 404.
    Rules: list_events R1."""
    T = order(db, S, which or "O")
    if which:
        ev(db, T, "created", 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.list_events(db, to_id=T.id if which else MISSING, workspace_id=S.W1.id)
    assert exc.value.status_code == 404


@xfail("BUG-2902")
def test_tom_lev_05__performers_read_together(db, S):
    """TOM-LEV-05 — performers are read together.
    Rules: list_events R4 [BUG-2902]."""
    O = order(db, S)
    for h, u in enumerate((S.U1, S.U2, S.U3), start=1):
        ev(db, O, "note", h, performed_by=u.id)
    oid, w1 = O.id, S.W1.id
    db.expunge_all()
    with Recorder(db) as rec:
        result = M.list_events(db, to_id=oid, workspace_id=w1)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert len(rec.sel("profiles")) <= 1
