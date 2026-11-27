"""Unit tests for app/services/transfer_order_service.py.

Implements tests/unit/services/transfer_order_service.cases.md (revision 2), one
test per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the test's own "commit point" and the service's
commits are safe and the fixture's outer rollback discards everything.

Patched, as Conventions name them: the manager clock (`utcnow` -> NOW, every
test), the number generator in create cards (NUMP), the stock posting in MC
cards (`pm`), the two notification helpers the service imported (NU / NA, only
in the "raise while notifying" cards), and the commit / rollback / refresh spies
and failures. Nothing else is mocked.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows are attributes of the namespace `s` (`s.W1`, `s.U1`);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe the nested `with` and naive datetimes; the cards write Decimal("7"))
import inspect
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.notification import Notification
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_approver import TransferOrderApprover
from app.models.transfer_order_event import TransferOrderEvent
from app.models.transfer_order_item import TransferOrderItem
from app.models.workspace import Workspace
from app.models.workspace_audit_log import WorkspaceAuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.transfer_order import (
    TransferOrderCreate,
    TransferOrderHubStatsResponse,
    TransferOrderItemCreate,
    TransferOrderItemUpdate,
    TransferOrderListResponse,
    TransferOrderUpdate,
)
from app.services.transfer_order_service import (
    transfer_order_service,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = transfer_order_service
M = svc.manager

MISSING = 999999999


def GN(prefix):
    return f"{prefix}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def XID(k):
    return 800_000_000 + (os.getpid() % 1_000_000) * 10 + k


def TS(h):
    return datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)


DONE = datetime(2026, 3, 20, 9, 0)
TOLD = datetime(2026, 3, 22, 8, 0)
NOW = datetime(2026, 3, 25, 12, 0)


def PEND(n, m):
    return f"{n} of {m} approval(s) collected"


GAP_ITEM = "Add at least one item before approvals can proceed"

BUG_3142 = (
    "BUG-3142: The 'was it ready for approval' check before a transfer order edit "
    "or line add is read without a row lock"
)
BUG_1194 = "BUG-1194: Deleted transfer order vanishes without trace"
BUG_2899 = (
    "BUG-2899: An edit can make a transfer's source and destination the same, "
    "which create refuses"
)
BUG_2903 = (
    "BUG-2903: Changing a transfer order's required approvals after approving "
    "started keeps the approvals already given"
)
BUG_2897 = "BUG-2897: Approvers and approvals can be changed on a completed transfer order"

COUNTED = (
    "transfer_orders",
    "transfer_order_items",
    "transfer_order_approvers",
    "transfer_order_events",
    "notifications",
    "workspace_audit_logs",
    "inventory_ledger",
)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


def stamp(v):
    return None if v is None else v.replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Externals (every test): the manager clock
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def clock():
    with patch("app.managers.transfer_order_manager.utcnow", return_value=NOW):
        yield


# TNUM, made once per test
@pytest.fixture
def tnum():
    return GN("TR-NEW")


# Convention NUMP
@contextmanager
def nump(tnum):
    with patch.object(M.to_dao, "get_next_number", return_value=tnum):
        yield


# Convention `pm`: the stock posting the manager imported
def pm_patch(**kw):
    return patch("app.managers.transfer_order_manager.post_transfer_order_inventory", **kw)


def err():
    return HTTPException(status_code=400, detail="Insufficient stock for Motor")


def _probe_row(db, w1_id, o_id):
    db.add(
        TransferOrderEvent(
            workspace_id=w1_id, transfer_order_id=o_id, event_type="probe", description="Probe"
        )
    )
    db.flush()


# Convention PROBE_OK
def probe_ok(db, w1_id, o_id):
    def _f(*args, **kwargs):
        _probe_row(db, w1_id, o_id)
        return 1

    return _f


# Convention PROBE_ERR (raises the given ERR instance)
def probe_err(db, w1_id, o_id, e):
    def _f(*args, **kwargs):
        _probe_row(db, w1_id, o_id)
        raise e

    return _f


# Convention NPROBE
def nprobe(db, w1_id, o_id):
    def _f(*args, **kwargs):
        _probe_row(db, w1_id, o_id)
        raise RuntimeError("notify boom")

    return _f


# Convention NU
def nu(side_effect):
    return patch(
        "app.services.transfer_order_service.handle_order_update_notifications",
        side_effect=side_effect,
    )


# Convention NA
def na(side_effect):
    return patch("app.services.transfer_order_service.handle_add_approver", side_effect=side_effect)


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db, name="Karim Ahmed")
    n.U2 = make_profile(db, name="Nadia Islam")
    n.U3 = make_profile(db, name="Rahim Uddin")
    n.U4 = make_profile(db, name="Sumi Akter")
    n.U5 = make_profile(db, name="Tanvir Hasan")
    for u, w, st, pos in (
        (n.U1, n.W1, "active", "Store Manager"),
        (n.U2, n.W1, "active", "Factory Head"),
        (n.U3, n.W1, "active", None),
        (n.U4, n.W1, "inactive", "Clerk"),
        (n.U5, n.W2, "active", "Boss"),
    ):
        _add(db, WorkspaceMember(workspace_id=w.id, user_id=u.id, role="member", status=st, position=pos))
    n.S0 = _add(db, Status(workspace_id=n.W0.id, name="Open", comment="stage"))
    n.S1 = _add(db, Status(workspace_id=n.W1.id, name="Open", comment="stage"))
    n.S2 = _add(db, Status(workspace_id=n.W2.id, name="Open", comment="stage"))
    n.F0 = _add(db, Factory(workspace_id=n.W0.id, name="Zulu Depot", abbreviation="ZD"))
    n.F1 = _add(db, Factory(workspace_id=n.W1.id, name="Alpha Works", abbreviation="AW"))
    n.FB = _add(db, Factory(workspace_id=n.W1.id, name="Bravo Yard", abbreviation="BY"))
    n.F2 = _add(db, Factory(workspace_id=n.W2.id, name="Yankee Store", abbreviation="YS"))
    n.M1 = _add(db, Machine(id=XID(1), workspace_id=n.W1.id, factory_id=n.F1.id, name="Press Kilo"))
    n.I1 = _add(db, Item(workspace_id=n.W1.id, name="Motor", name_normalized="motor", unit="pcs"))
    n.I2 = _add(db, Item(workspace_id=n.W1.id, name="Bearing", name_normalized="bearing", unit="pcs"))
    n.IX = _add(db, Item(workspace_id=n.W2.id, name="Valve", name_normalized="valve", unit="pcs"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def _o_fields(s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "transfer_number": GN("TR-O"),
        "source_location_type": "storage",
        "source_location_id": s.F1.id,
        "destination_location_type": "storage",
        "destination_location_id": s.FB.id,
        "current_status_id": s.S1.id,
        "created_by": s.U1.id,
        "description": "Old text",
        "created_at": TS(1),
    }
    fields.update(but)
    return fields


# Convention "order O"; "but" overrides columns
def order(db, s, **but):
    return _add(db, TransferOrder(**_o_fields(s, **but)))


# Convention "order O0"
def order_o0(db, s, **but):
    fields = {
        "workspace_id": s.W0.id,
        "transfer_number": GN("TR-O0"),
        "source_location_id": s.F0.id,
        "destination_location_type": "damaged",
        "destination_location_id": s.F0.id,
        "current_status_id": s.S0.id,
    }
    fields.update(but)
    return order(db, s, **fields)


# Convention "order O9"
def order_o9(db, s, **but):
    fields = {
        "workspace_id": s.W2.id,
        "transfer_number": GN("TR-O9"),
        "source_location_id": s.F2.id,
        "destination_location_type": "damaged",
        "destination_location_id": s.F2.id,
        "current_status_id": s.S2.id,
    }
    fields.update(but)
    return order(db, s, **fields)


# Convention "completed"
def completed(s):
    return {"completed_at": DONE, "completed_by": s.U1.id}


# Convention "looped" (source = destination)
def looped(s):
    return {"destination_location_id": s.F1.id}


# Convention "HO(k, h, **cols)": an unsaved hub order
def ho(s, k, h, **cols):
    return TransferOrder(**_o_fields(s, transfer_number=GN(f"TR-H{k}"), created_at=TS(h), **cols))


def add_ho(db, s, k, h, **cols):
    return _add(db, ho(s, k, h, **cols))


# Convention "line(T, k)"
def line(db, s, t, k, **but):
    fields = {
        "workspace_id": t.workspace_id,
        "transfer_order_id": t.id,
        "line_number": k,
        "item_id": s.IX.id if t.workspace_id == s.W2.id else s.I1.id,
        "quantity": Decimal("10.00"),
    }
    fields.update(but)
    return _add(db, TransferOrderItem(**fields))


# Convention "apr(T, U, h)"
def apr(db, s, t, u, h, **but):
    fields = {
        "workspace_id": t.workspace_id,
        "transfer_order_id": t.id,
        "user_id": u.id,
        "assigned_by": s.U1.id,
        "approved": False,
        "approved_at": None,
        "assigned_at": TS(h),
    }
    fields.update(but)
    return _add(db, TransferOrderApprover(**fields))


# Convention "approved"
APPROVED = {"approved": True, "approved_at": TOLD}


# Convention "ev(T, type, h)"
def ev(db, t, etype, h, **but):
    fields = {
        "workspace_id": t.workspace_id,
        "transfer_order_id": t.id,
        "event_type": etype,
        "description": "Logged",
        "created_at": TS(h),
    }
    fields.update(but)
    return _add(db, TransferOrderEvent(**fields))


# Convention "CREATE(k=v)"
def CREATE(s, **kw):
    fields = {
        "source_location_type": "storage",
        "source_location_id": s.F1.id,
        "destination_location_type": "storage",
        "destination_location_id": s.FB.id,
        "current_status_id": s.S1.id,
        "description": "Monthly move",
    }
    fields.update(kw)
    return TransferOrderCreate(**fields)


# Convention "ITEM(I, q)"
def ITEM(i, q):
    return TransferOrderItemCreate(item_id=i.id, quantity=Decimal(q))


# Conventions "UPD(k=v)" / "IU(k=v)": only listed fields are sent
def UPD(**kw):
    return TransferOrderUpdate(**kw)


def IU(**kw):
    return TransferOrderItemUpdate(**kw)


# Convention "DEL(id)"
def DEL(db, s, to_id):
    kw = {"to_id": to_id, "workspace_id": s.W1.id}
    if "user_id" in inspect.signature(svc.delete_transfer_order).parameters:
        kw["user_id"] = s.U2.id
    return svc.delete_transfer_order(db, **kw)


# Convention "X": a pending workspace, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Convention "commit point": the test commits; "nothing written" snapshot taken here
def commit_point(db):
    db.commit()
    return counts(db)


# --------------------------------------------------------------------------- #
# Named checks
# --------------------------------------------------------------------------- #


# "nothing written": row counts of the seven tables, all workspaces
def counts(db):
    return tuple(db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in COUNTED)


# "unchanged(X)": every column of the row, from the database
def snap(db, model, row_id):
    cols = [getattr(model, c.key) for c in sa_inspect(model).column_attrs]
    row = db.execute(select(*cols).where(model.id == row_id)).one_or_none()
    return None if row is None else tuple(row)


# "re-read X"
def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


def cnt(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


# "notes(T)"
def notes(db, to_id):
    rows = db.execute(
        select(
            Notification.notification_type,
            Notification.recipient_user_id,
            Notification.actor_user_id,
            Notification.source_type,
            Notification.source_id,
            Notification.preview,
        ).where(Notification.entity_type == "transfer_order", Notification.entity_id == to_id)
    ).all()
    return sorted(tuple(r) for r in rows)


# "types(T)"
def types(db, to_id):
    return list(
        db.execute(
            select(TransferOrderEvent.event_type)
            .where(TransferOrderEvent.transfer_order_id == to_id)
            .order_by(TransferOrderEvent.id)
        ).scalars()
    )


def events_of(db, to_id, etype):
    db.expire_all()
    return list(
        db.execute(
            select(TransferOrderEvent).where(
                TransferOrderEvent.transfer_order_id == to_id, TransferOrderEvent.event_type == etype
            )
        ).scalars()
    )


# "loaded(r)"
def loaded(r):
    return sa_inspect(r).expired_attributes.isdisjoint(
        {c.key for c in sa_inspect(type(r)).column_attrs}
    )


# "x_gone"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


# "usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# "spies"
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(
        db, "rollback", wraps=db.rollback
    ) as rb:
        yield cm, rb


# "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(
        db, "rollback", wraps=db.rollback
    ) as rb:
        yield rb


# "failing refresh"
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# "Statement recorder"
class record_sql:
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


def _norm(sql):
    return " ".join(sql.split())


def _select_from(sql, table):
    return sql.upper().startswith("SELECT") and re.search(rf"\bFROM {table}\b", sql) is not None


# "lock first", part 1: a `... FOR UPDATE OF transfer_orders` SELECT before the first items SELECT
def locked_before_items(statements):
    norm = [_norm(x) for x in statements]
    first_items = next(
        (i for i, x in enumerate(norm) if _select_from(x, "transfer_order_items")), len(norm)
    )
    return any(
        _select_from(x, "transfer_orders") and x.endswith("FOR UPDATE OF transfer_orders")
        for x in norm[:first_items]
    )


# "lock first", part 2: no NOWAIT / SKIP LOCKED anywhere
def no_nowait(statements):
    return not any("NOWAIT" in x.upper() or "SKIP LOCKED" in x.upper() for x in statements)


# --------------------------------------------------------------------------- #
# create_transfer_order
# --------------------------------------------------------------------------- #


# [claude] TOS-C-01
def test_tos_c_01__create_committed_reread(db, s, tnum):
    """TOS-C-01 — a new order is committed and returned re-read, with its creator approver and event.
    Rules: create_transfer_order R1; TC1, TC2."""
    commit_point(db)

    with nump(tnum):
        result = svc.create_transfer_order(db, to_in=CREATE(s), workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, TransferOrder)
    assert result.created_at is not None
    assert result.transfer_number == tnum
    rid = result.id
    # Then 3
    db.rollback()
    row = reread(db, TransferOrder, rid)
    assert row is not None
    assert row.workspace_id == s.W1.id
    assert row.created_by == s.U1.id
    assert row.description == "Monthly move"
    # Then 4
    aprs = list(
        db.execute(select(TransferOrderApprover).where(TransferOrderApprover.transfer_order_id == rid)).scalars()
    )
    assert len(aprs) == 1
    assert aprs[0].user_id == s.U1.id
    assert aprs[0].approved is False
    # Then 5
    assert types(db, rid) == ["created"]


# [claude] TOS-C-02
def test_tos_c_02__ready_at_once_no_notification(db, s, tnum):
    """TOS-C-02 — an order ready at once (route and a line) sends no notification.
    Rules: create_transfer_order R3."""
    commit_point(db)

    with nump(tnum):
        result = svc.create_transfer_order(
            db, to_in=CREATE(s, items=[ITEM(s.I1, "5")]), workspace_id=s.W1.id, user_id=s.U1.id
        )

    # Then 1
    assert result.id is not None
    rid = result.id
    # Then 2
    db.rollback()
    assert cnt(db, TransferOrderItem, TransferOrderItem.transfer_order_id == rid) == 1
    # Then 3
    assert notes(db, rid) == []


# [claude] TOS-C-03
def test_tos_c_03__same_route_refused(db, s, tnum):
    """TOS-C-03 — the same route is refused 400; the session is rolled back.
    Rules: create_transfer_order R2; TC3."""
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with nump(tnum):
            svc.create_transfer_order(
                db, to_in=CREATE(s, destination_location_id=s.F1.id), workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Source and destination cannot be the same"
    # Then 4
    assert not db.new
    # Then 5
    assert usable(db)
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-C-04
def test_tos_c_04__duplicate_item_refused(db, s, tnum):
    """TOS-C-04 — a duplicate item is refused 409; no order, approver, line or event is saved.
    Rules: create_transfer_order R2; TC3."""
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with nump(tnum):
            svc.create_transfer_order(
                db,
                to_in=CREATE(s, items=[ITEM(s.I1, "5"), ITEM(s.I1, "2")]),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Motor appears more than once on this order"
    # Then 4
    assert not db.new
    # Then 5
    assert cnt(db, TransferOrder, TransferOrder.transfer_number == tnum) == 0
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-C-05
def test_tos_c_05__db_error_passes_unchanged(db, s, tnum):
    """TOS-C-05 — a database error (unknown creator) passes unchanged and nothing is saved.
    Rules: create_transfer_order R2; TC3."""
    before = commit_point(db)
    _, x_id = mk_x(db)
    w1_id = s.W1.id

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with nump(tnum):
            svc.create_transfer_order(db, to_in=CREATE(s), workspace_id=w1_id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert usable(db)
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-C-06
def test_tos_c_06__failing_commit_rolled_back(db, s, tnum):
    """TOS-C-06 — a failing commit is rolled back and re-raised.
    Rules: create_transfer_order R4; TC4."""
    before = commit_point(db)
    to_in = CREATE(s, items=[ITEM(s.I1, "5")])
    w1_id, u1_id = s.W1.id, s.U1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            with nump(tnum):
                svc.create_transfer_order(db, to_in=to_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert cnt(db, TransferOrder, TransferOrder.transfer_number == tnum) == 0
    # Then 4
    assert counts(db) == before


# [claude] TOS-C-07
def test_tos_c_07__failing_refresh_keeps_order(db, s, tnum):
    """TOS-C-07 — a failing re-read after the commit leaves the order saved.
    Rules: create_transfer_order R4; TC5."""
    commit_point(db)
    to_in = CREATE(s)
    w1_id, u1_id = s.W1.id, s.U1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            with nump(tnum):
                svc.create_transfer_order(db, to_in=to_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    db.expire_all()
    rows = list(db.execute(select(TransferOrder).where(TransferOrder.transfer_number == tnum)).scalars())
    assert len(rows) == 1
    assert rows[0].created_by == u1_id


# --------------------------------------------------------------------------- #
# update_transfer_order
# --------------------------------------------------------------------------- #


# [claude] TOS-U-01
def test_tos_u_01__w0_order_404_rolled_back(db, s):
    """TOS-U-01 — an order of W0 (lower id) gets the 404, nothing is written, the session is rolled back.
    Rules: update_transfer_order R1, R1a; TC3."""
    z = order_o0(db, s)
    order(db, s)
    before = commit_point(db)
    z_before = snap(db, TransferOrder, z.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(db, to_id=z.id, to_in=UPD(description="New"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z.id} not found"
    # Then 4
    assert snap(db, TransferOrder, z.id) == z_before
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-02
def test_tos_u_02__w2_order_404_rolled_back(db, s):
    """TOS-U-02 — an order of W2 (higher id) gets the 404, nothing is written, the session is rolled back.
    Rules: update_transfer_order R1, R1a; TC3."""
    order(db, s)
    z = order_o9(db, s)
    before = commit_point(db)
    z_before = snap(db, TransferOrder, z.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(db, to_id=z.id, to_in=UPD(description="New"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z.id} not found"
    # Then 4
    assert snap(db, TransferOrder, z.id) == z_before
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-03
def test_tos_u_03__edit_committed_reread(db, s):
    """TOS-U-03 — an edit is committed and the order returned re-read.
    Rules: update_transfer_order R3; TC1, TC2."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(description="New text"), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == o.id
    assert result.description == "New text"
    # Then 3
    db.rollback()
    assert reread(db, TransferOrder, o.id).description == "New text"
    # Then 4
    assert types(db, o.id) == ["updated"]
    # Then 5
    assert notes(db, o.id) == []


# [claude] TOS-U-04
def test_tos_u_04__becomes_ready_pending_to_active_approvers(db, s):
    """TOS-U-04 — not ready → ready: every pending active approver gets "approval pending", the actor included.
    Rules: update_transfer_order R2, R4a [companion of BUG-3142]."""
    o = order(db, s, **looped(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U2, 2)
    apr(db, s, o, s.U4, 3)
    commit_point(db)

    result = svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(destination_location_id=s.FB.id), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.destination_location_id == s.FB.id
    # Then 2
    db.rollback()
    assert notes(db, o.id) == [
        ("approval_pending", s.U1.id, s.U2.id, "order", o.id, PEND(0, 3)),
        ("approval_pending", s.U2.id, s.U2.id, "order", o.id, PEND(0, 3)),
    ]
    # Then 3
    assert reread(db, TransferOrder, o.id).destination_location_id == s.FB.id


# [claude] TOS-U-05
def test_tos_u_05__becomes_ready_by_non_approver(db, s):
    """TOS-U-05 — not ready → ready by an actor who is not an approver: both pending approvers are told.
    Rules: update_transfer_order R4a [companion of BUG-3142]."""
    o = order(db, s, required_approvals=2, **looped(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(destination_location_id=s.FB.id), workspace_id=s.W1.id, user_id=s.U3.id
    )

    # Then 1
    db.rollback()
    assert reread(db, TransferOrder, o.id).destination_location_id == s.FB.id
    # Then 2
    assert notes(db, o.id) == [
        ("approval_pending", s.U1.id, s.U3.id, "order", o.id, PEND(0, 2)),
        ("approval_pending", s.U2.id, s.U3.id, "order", o.id, PEND(0, 2)),
    ]


# [claude] TOS-U-06
def test_tos_u_06__ready_to_ready_sends_nothing(db, s):
    """TOS-U-06 — ready → ready (a description edit) sends nothing.
    Rules: update_transfer_order R4c."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    svc.update_transfer_order(db, to_id=o.id, to_in=UPD(description="Again"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    db.rollback()
    assert reread(db, TransferOrder, o.id).description == "Again"
    # Then 2
    assert notes(db, o.id) == []


# [claude] TOS-U-07
def test_tos_u_07__not_ready_to_not_ready_sends_nothing(db, s):
    """TOS-U-07 — not ready → not ready (no line) sends nothing.
    Rules: update_transfer_order R4c."""
    o = order(db, s, **looped(s))
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(destination_location_id=s.FB.id), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    db.rollback()
    assert reread(db, TransferOrder, o.id).destination_location_id == s.FB.id
    # Then 2
    assert notes(db, o.id) == []


# [claude] TOS-U-08
def test_tos_u_08__zero_required_sends_nothing(db, s):
    """TOS-U-08 — no approvals required (`required_approvals` 0): becoming ready sends nothing.
    Rules: update_transfer_order R4c."""
    o = order(db, s, required_approvals=0, **looped(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(destination_location_id=s.FB.id), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    db.rollback()
    assert reread(db, TransferOrder, o.id).destination_location_id == s.FB.id
    # Then 2
    assert notes(db, o.id) == []


# [claude] TOS-U-09
def test_tos_u_09__required_change_sends_nothing(db, s):
    """TOS-U-09 — a `required_approvals` change on a ready order with an approval sends nothing.
    Rules: update_transfer_order R5."""
    o = order(db, s, required_approvals=2)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    result = svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(required_approvals=1), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.required_approvals == 1
    # Then 2
    db.rollback()
    assert reread(db, TransferOrder, o.id).required_approvals == 1
    # Then 3
    assert notes(db, o.id) == []


# [claude] TOS-U-10
def test_tos_u_10__guard_refusal_rolled_back(db, s):
    """TOS-U-10 — a guard refusal (approval given, description edit) rolls back, nothing saved.
    Rules: update_transfer_order R6; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(db, to_id=o.id, to_in=UPD(description="New"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Withdraw all approvals before editing order details"
    # Then 4
    assert usable(db)
    # Then 5
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-15
def test_tos_u_15__completed_refused(db, s):
    """TOS-U-15 — a completed order is refused 400 and rolled back.
    Rules: update_transfer_order R6; TC3."""
    o = order(db, s, **completed(s))
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(db, to_id=o.id, to_in=UPD(description="New"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Transfer order is complete and cannot be edited"
    # Then 4
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-16
def test_tos_u_16__failing_commit_rolls_back_edit(db, s):
    """TOS-U-16 — a failing commit rolls back the edit, its event and its notifications.
    Rules: update_transfer_order R6, R7; TC4."""
    o = order(db, s, **looped(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id, fb_id = o.id, s.W1.id, s.U1.id, s.FB.id
    o_before = snap(db, TransferOrder, o_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_transfer_order(
                db, to_id=o_id, to_in=UPD(destination_location_id=fb_id), workspace_id=w1_id, user_id=u1_id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrder, o_id) == o_before
    # Then 4
    assert notes(db, o_id) == []
    # Then 5
    assert counts(db) == before


# [claude] TOS-U-17
def test_tos_u_17__failing_refresh_keeps_edit(db, s):
    """TOS-U-17 — a failing re-read after the commit leaves the edit saved.
    Rules: update_transfer_order R7; TC5."""
    o = order(db, s)
    commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_transfer_order(db, to_id=o_id, to_in=UPD(description="Kept"), workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, TransferOrder, o_id).description == "Kept"


# [claude] TOS-U-18
def test_tos_u_18__raise_while_notifying_rolls_back(db, s):
    """TOS-U-18 — a raise while notifying rolls back the edit, its event, the helper's writes and other pending changes.
    Rules: update_transfer_order R6; TC3."""
    o = order(db, s, **looped(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id, fb_id = o.id, s.W1.id, s.U1.id, s.FB.id
    o_before = snap(db, TransferOrder, o_id)
    _, x_id = mk_x(db)

    with nu(nprobe(db, w1_id, o_id)) as nh:
        with pytest.raises(RuntimeError) as exc:
            svc.update_transfer_order(
                db, to_id=o_id, to_in=UPD(destination_location_id=fb_id), workspace_id=w1_id, user_id=u1_id
            )

    # Then 1
    assert str(exc.value) == "notify boom"
    # Then 2
    assert nh.call_count == 1
    # Then 3
    assert usable(db)
    # Then 4
    assert snap(db, TransferOrder, o_id) == o_before
    # Then 5
    assert types(db, o_id) == []
    # Then 6
    assert notes(db, o_id) == []
    # Then 7
    assert counts(db) == before
    # Then 8
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-19
def test_tos_u_19__missing_id_404_rolled_back(db, s):
    """TOS-U-19 — an id that does not exist gets the 404, nothing is written, the session is rolled back.
    Rules: update_transfer_order R1, R1a; TC3."""
    o = order(db, s)
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(db, to_id=MISSING, to_in=UPD(description="New"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {MISSING} not found"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-U-11
def test_tos_u_11__ready_to_not_ready_confirm_sections(db, s):
    """TOS-U-11 — ready → not ready: the creator gets "confirm sections" (retire when BUG-2899 is fixed).
    Rules: update_transfer_order R4b."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U2, 1)
    commit_point(db)

    svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(destination_location_id=s.F1.id), workspace_id=s.W1.id, user_id=s.U3.id
    )

    # Then 1
    db.rollback()
    assert notes(db, o.id) == [("section_confirm", s.U1.id, s.U3.id, "section", o.id, GAP_ITEM)]


# [claude] TOS-U-12
@pytest.mark.xfail(strict=True, reason=BUG_2899)
def test_tos_u_12__same_route_edit_refused(db, s):
    """TOS-U-12 — pass-through BUG-2899: an edit to source = destination is refused, nothing sent.
    Rules: update_transfer_order R3, R6 [BUG-2899]."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U2, 1)
    commit_point(db)
    o_before = snap(db, TransferOrder, o.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_transfer_order(
            db, to_id=o.id, to_in=UPD(destination_location_id=s.F1.id), workspace_id=s.W1.id, user_id=s.U3.id
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Source and destination cannot be the same"
    # Then 4
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 5
    assert notes(db, o.id) == []


# [claude] TOS-U-13
@pytest.mark.xfail(strict=True, reason=BUG_3142)
def test_tos_u_13__lock_before_readiness(db, s):
    """TOS-U-13 — BUG-3142: the order row is locked before the readiness snapshot.
    Rules: update_transfer_order R2a [BUG-3142]."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id
    db.expunge_all()

    with record_sql(db) as rec:
        result = svc.update_transfer_order(
            db, to_id=o_id, to_in=UPD(description="New text"), workspace_id=w1_id, user_id=u1_id
        )

    # Then 1
    assert result.id == o_id
    # Then 2
    assert locked_before_items(rec.statements)
    assert no_nowait(rec.statements)
    # Then 3
    assert any(_select_from(_norm(x), "transfer_order_items") for x in rec.statements)


# [claude] TOS-U-14
@pytest.mark.xfail(strict=True, reason=BUG_2903)
def test_tos_u_14__required_change_wipes_approvals(db, s):
    """TOS-U-14 — pass-through BUG-2903: a `required_approvals` change commits the approval wipe.
    Rules: update_transfer_order R3, R5 [BUG-2903]."""
    o = order(db, s, required_approvals=2)
    line(db, s, o, 1)
    a1 = apr(db, s, o, s.U1, 1, **APPROVED)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    result = svc.update_transfer_order(
        db, to_id=o.id, to_in=UPD(required_approvals=1), workspace_id=s.W1.id, user_id=s.U2.id
    )

    # Then 1
    assert result.required_approvals == 1
    # Then 2
    db.rollback()
    row = reread(db, TransferOrderApprover, a1.id)
    assert row.approved is False
    assert row.approved_at is None
    # Then 3
    assert types(db, o.id) == ["updated", "approvals_reset"]
    # Then 4
    assert notes(db, o.id) == []


# --------------------------------------------------------------------------- #
# get_transfer_order
# --------------------------------------------------------------------------- #


# [claude] TOS-G-01
def test_tos_g_01__get_with_status_no_commit(db, s):
    """TOS-G-01 — returns the workspace's order with its status; the read neither commits nor rolls back.
    Rules: get_transfer_order R1; TC6."""
    order_o0(db, s)
    o = order(db, s)
    commit_point(db)
    o_id, w1_id = o.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_transfer_order(db, to_id=o_id, workspace_id=w1_id)

    # Then 1
    assert isinstance(result, TransferOrder)
    assert result.id == o_id
    # Then 2
    assert result.current_status.name == "Open"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db


# [claude] TOS-G-02
def test_tos_g_02__other_workspace_404_no_rollback(db, s):
    """TOS-G-02 — another workspace's order: the 404 passes unchanged, no rollback.
    Rules: get_transfer_order R1; TC6."""
    order(db, s)
    z = order_o9(db, s)
    commit_point(db)
    z_id, w1_id = z.id, s.W1.id
    x, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_transfer_order(db, to_id=z_id, workspace_id=w1_id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z_id} not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert x in db


# [claude] TOS-G-03
def test_tos_g_03__w0_order_404_no_rollback(db, s):
    """TOS-G-03 — an order of W0 (lower id): the 404 passes unchanged, no rollback.
    Rules: get_transfer_order R1; TC6; HR-16."""
    z = order_o0(db, s)
    order(db, s)
    commit_point(db)
    z_id, w1_id = z.id, s.W1.id
    x, _ = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.get_transfer_order(db, to_id=z_id, workspace_id=w1_id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z_id} not found"
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert x in db


# --------------------------------------------------------------------------- #
# list_transfer_orders
# --------------------------------------------------------------------------- #


# [claude] TOS-LT-01
def test_tos_lt_01__default_limit_100(db, s):
    """TOS-LT-01 — default limit is 100: 101 orders give 100 items and `has_more`.
    Rules: list_transfer_orders R1, R2."""
    db.add_all([ho(s, k, k) for k in range(1, 102)])
    db.flush()
    commit_point(db)

    result = svc.list_transfer_orders(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, TransferOrderListResponse)
    # Then 2
    assert len(result.items) == 100
    assert result.total == 101
    # Then 3
    assert result.skip == 0
    assert result.limit == 100
    assert result.has_more is True


# [claude] TOS-LT-02
def test_tos_lt_02__skip_limit_filter_passed_on(db, s):
    """TOS-LT-02 — skip, limit and a filter are passed on.
    Rules: list_transfer_orders R1."""
    a = add_ho(db, s, 1, 1)
    add_ho(db, s, 2, 2)
    add_ho(db, s, 3, 3, completed_at=DONE, completed_by=s.U1.id)
    commit_point(db)

    result = svc.list_transfer_orders(db, workspace_id=s.W1.id, skip=1, limit=1, exclude_complete=True)

    # Then 1
    assert result.total == 2
    # Then 2
    assert [i.id for i in result.items] == [a.id]
    # Then 3
    assert result.skip == 1
    assert result.limit == 1
    assert result.has_more is False


# [claude] TOS-LT-03
def test_tos_lt_03__unknown_filter_type_error(db, s):
    """TOS-LT-03 — an unknown filter keyword raises `TypeError`.
    Rules: list_transfer_orders R3."""
    add_ho(db, s, 1, 1)
    commit_point(db)

    # Then 1
    with pytest.raises(TypeError):
        svc.list_transfer_orders(db, workspace_id=s.W1.id, colour="red")


# --------------------------------------------------------------------------- #
# _hub_filter_kwargs
# --------------------------------------------------------------------------- #


# [claude] TOS-HF-01
def test_tos_hf_01__values_passed_as_given(db):
    """TOS-HF-01 — every value is passed as given, exactly eight keys.
    Rules: _hub_filter_kwargs R1."""
    result = svc._hub_filter_kwargs(
        date_from=TS(1),
        date_to=TS(2),
        status_ids=[7, 8],
        factory_id=5,
        source_location_type="storage",
        destination_location_type="machine",
        search="TR-",
        exclude_complete=True,
    )

    # Then 1
    assert result == {
        "date_from": TS(1),
        "date_to": TS(2),
        "status_ids": [7, 8],
        "factory_id": 5,
        "source_location_type": "storage",
        "destination_location_type": "machine",
        "search": "TR-",
        "exclude_complete": True,
    }


# [claude] TOS-HF-02
def test_tos_hf_02__no_arguments_defaults(db):
    """TOS-HF-02 — no arguments: all None and `exclude_complete` False.
    Rules: _hub_filter_kwargs R1, R2, R3."""
    result = svc._hub_filter_kwargs()

    # Then 1
    assert result == {
        "date_from": None,
        "date_to": None,
        "status_ids": None,
        "factory_id": None,
        "source_location_type": None,
        "destination_location_type": None,
        "search": None,
        "exclude_complete": False,
    }


# [claude] TOS-HF-03
def test_tos_hf_03__all_and_empty_mean_none(db):
    """TOS-HF-03 — `"all"` and `""` mean no location filter.
    Rules: _hub_filter_kwargs R2."""
    result = svc._hub_filter_kwargs(source_location_type="all", destination_location_type="")

    # Then 1
    assert result["source_location_type"] is None
    # Then 2
    assert result["destination_location_type"] is None


# [claude] TOS-HF-04
def test_tos_hf_04__other_spellings_kept(db):
    """TOS-HF-04 — other spellings are kept exactly: `"All"`, `" all"`, `"al"`, `"ALL"`.
    Rules: _hub_filter_kwargs R2 (D3)."""
    results = [
        svc._hub_filter_kwargs(source_location_type=v, destination_location_type=v)
        for v in ["All", " all", "al", "ALL"]
    ]

    # Then 1
    assert [r["source_location_type"] for r in results] == ["All", " all", "al", "ALL"]
    # Then 2
    assert [r["destination_location_type"] for r in results] == ["All", " all", "al", "ALL"]


# [claude] TOS-HF-05
def test_tos_hf_05__all_destination_empty_source_mean_none(db):
    """TOS-HF-05 — `"all"` as the destination and `""` as the source also mean no location filter.
    Rules: _hub_filter_kwargs R2."""
    result = svc._hub_filter_kwargs(source_location_type="", destination_location_type="all")

    # Then 1
    assert result["source_location_type"] is None
    # Then 2
    assert result["destination_location_type"] is None


# --------------------------------------------------------------------------- #
# list_transfer_orders_page
# --------------------------------------------------------------------------- #


# [claude] TOS-LP-01
def test_tos_lp_01__default_page(db, s):
    """TOS-LP-01 — default: completed orders included, other workspaces left out, limit 50; neither commit nor rollback.
    Rules: list_transfer_orders_page R1, R2, R4; _hub_filter_kwargs R3 (D2)."""
    order_o0(db, s)
    a = add_ho(db, s, 1, 1)
    c = add_ho(db, s, 2, 2, completed_at=DONE, completed_by=s.U1.id)
    order_o9(db, s)
    commit_point(db)
    a_id, c_id, w1_id = a.id, c.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_transfer_orders_page(db, workspace_id=w1_id)

    # Then 1
    assert isinstance(result, TransferOrderListResponse)
    # Then 2
    assert [i.id for i in result.items] == [c_id, a_id]
    # Then 3
    assert result.total == 2
    assert result.skip == 0
    assert result.limit == 50
    assert result.has_more is False
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert rb.call_count == 0
    # Then 6
    assert x in db


# [claude] TOS-LP-02
def test_tos_lp_02__51_orders_has_more(db, s):
    """TOS-LP-02 — 51 orders: the default page holds 50 and `has_more` is true.
    Rules: list_transfer_orders_page R2, R3."""
    db.add_all([ho(s, k, k) for k in range(1, 52)])
    db.flush()
    commit_point(db)

    result = svc.list_transfer_orders_page(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.items) == 50
    assert result.total == 51
    assert result.has_more is True


# [claude] TOS-LP-03
def test_tos_lp_03__exclude_complete_reaches_count_and_list(db, s):
    """TOS-LP-03 — the same filter reaches count and list: `exclude_complete=True`.
    Rules: list_transfer_orders_page R1, R2."""
    a = add_ho(db, s, 1, 1)
    add_ho(db, s, 2, 2, completed_at=DONE, completed_by=s.U1.id)
    b = add_ho(db, s, 3, 3)
    commit_point(db)

    result = svc.list_transfer_orders_page(db, workspace_id=s.W1.id, exclude_complete=True)

    # Then 1
    assert [i.id for i in result.items] == [b.id, a.id]
    # Then 2
    assert result.total == 2


# [claude] TOS-LP-04
def test_tos_lp_04__all_lists_every_type(db, s):
    """TOS-LP-04 — `"all"` source type lists every type; `"All"` finds nothing.
    Rules: list_transfer_orders_page R1; _hub_filter_kwargs R2 (D3)."""
    add_ho(db, s, 1, 1)
    add_ho(db, s, 2, 2, source_location_type="machine", source_location_id=s.M1.id)
    commit_point(db)

    results = [
        svc.list_transfer_orders_page(db, workspace_id=s.W1.id, source_location_type=v)
        for v in ["all", "All", "machine"]
    ]

    # Then 1
    assert [r.total for r in results] == [2, 0, 1]
    # Then 2
    assert [len(r.items) for r in results] == [2, 0, 1]


# [claude] TOS-LP-05
def test_tos_lp_05__has_more_true(db, s):
    """TOS-LP-05 — `has_more` true while `skip + len(items) < total`.
    Rules: list_transfer_orders_page R3."""
    add_ho(db, s, 1, 1)
    b = add_ho(db, s, 2, 2)
    c = add_ho(db, s, 3, 3)
    commit_point(db)

    results = [
        svc.list_transfer_orders_page(db, workspace_id=s.W1.id, skip=sk, limit=li) for sk, li in [(0, 2), (1, 1)]
    ]

    # Then 1
    assert [[i.id for i in r.items] for r in results] == [[c.id, b.id], [b.id]]
    # Then 2
    assert [r.has_more for r in results] == [True, True]


# [claude] TOS-LP-06
def test_tos_lp_06__has_more_false_at_end(db, s):
    """TOS-LP-06 — `has_more` false when `skip + len(items) == total`.
    Rules: list_transfer_orders_page R3."""
    a = add_ho(db, s, 1, 1)
    b = add_ho(db, s, 2, 2)
    add_ho(db, s, 3, 3)
    commit_point(db)

    results = [
        svc.list_transfer_orders_page(db, workspace_id=s.W1.id, skip=sk, limit=li) for sk, li in [(1, 2), (2, 1)]
    ]

    # Then 1
    assert [[i.id for i in r.items] for r in results] == [[b.id, a.id], [a.id]]
    # Then 2
    assert [r.has_more for r in results] == [False, False]
    # Then 3
    assert [r.total for r in results] == [3, 3]


# [claude] TOS-LP-07
def test_tos_lp_07__skip_past_end(db, s):
    """TOS-LP-07 — skip past the end: no items, `has_more` false.
    Rules: list_transfer_orders_page R2, R3."""
    add_ho(db, s, 1, 1)
    add_ho(db, s, 2, 2)
    commit_point(db)

    result = svc.list_transfer_orders_page(db, workspace_id=s.W1.id, skip=5, limit=2)

    # Then 1
    assert result.items == []
    assert result.total == 2
    assert result.skip == 5
    assert result.has_more is False


# --------------------------------------------------------------------------- #
# get_transfer_order_hub_stats
# --------------------------------------------------------------------------- #


# [claude] TOS-HS-01
def test_tos_hs_01__stats_of_workspace(db, s):
    """TOS-HS-01 — stats of a workspace: counts, machine count, recent, highlights; neither commit nor rollback.
    Rules: get_transfer_order_hub_stats R2, R3, R4, R5; TC6."""
    order_o0(db, s)
    a = add_ho(db, s, 1, 1, destination_location_type="machine", destination_location_id=s.M1.id)
    line(db, s, a, 1)
    b = add_ho(db, s, 2, 2, source_location_id=0)
    c = add_ho(db, s, 3, 3, completed_at=DONE, completed_by=s.U1.id)
    order_o9(db, s)
    commit_point(db)
    a_id, b_id, c_id, w1_id = a.id, b.id, c.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_transfer_order_hub_stats(db, workspace_id=w1_id)

    # Then 1
    assert isinstance(result, TransferOrderHubStatsResponse)
    # Then 2
    assert (result.total_count, result.open_count, result.completed_count) == (3, 2, 1)
    # Then 3
    assert result.machine_involved_count == 1
    # Then 4
    assert {r.id for r in result.recent_orders} == {a_id, b_id, c_id}
    # Then 5
    assert {r.status_name for r in result.recent_orders} == {"Open"}
    # Then 6
    assert (result.pending_planned_count, result.awaiting_setup_count) == (1, 1)
    # Then 7
    assert [(h.id, h.status_name) for h in result.pending_planned] == [(a_id, "Planned")]
    # Then 8
    assert [(h.id, h.status_name) for h in result.awaiting_setup] == [(b_id, "Draft")]
    # Then 9
    assert [h.id for h in result.oldest_drafts] == [b_id]
    # Then 10
    assert cm.call_count == 0
    # Then 11
    assert rb.call_count == 0
    # Then 12
    assert x in db


# [claude] TOS-HS-02
def test_tos_hs_02__filter_reaches_every_read(db, s):
    """TOS-HS-02 — a filter that differs from the DAO's defaults reaches every hub read, the machine count included.
    Rules: get_transfer_order_hub_stats R1, R2; _hub_filter_kwargs R3 (D2)."""
    a = add_ho(db, s, 1, 1, destination_location_type="machine", destination_location_id=s.M1.id)
    line(db, s, a, 1)
    add_ho(db, s, 2, 2, source_location_id=0)
    c = add_ho(
        db, s, 3, 3,
        destination_location_type="machine", destination_location_id=s.M1.id,
        completed_at=DONE, completed_by=s.U1.id,
    )
    commit_point(db)

    result = svc.get_transfer_order_hub_stats(
        db, workspace_id=s.W1.id, destination_location_type="machine", exclude_complete=False
    )

    # Then 1
    assert (result.total_count, result.open_count, result.completed_count) == (2, 1, 1)
    # Then 2
    assert result.machine_involved_count == 2
    # Then 3
    assert {r.id for r in result.recent_orders} == {a.id, c.id}
    # Then 4
    assert (result.pending_planned_count, result.awaiting_setup_count) == (1, 0)
    # Then 5
    assert result.awaiting_setup == []
    assert result.oldest_drafts == []


# [claude] TOS-HS-03
def test_tos_hs_03__at_most_ten_recent(db, s):
    """TOS-HS-03 — at most 10 recent orders.
    Rules: get_transfer_order_hub_stats R3."""
    rows = [ho(s, k, k) for k in range(1, 12)]
    db.add_all(rows)
    db.flush()
    all_ids = {r.id for r in rows}
    commit_point(db)

    result = svc.get_transfer_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result.recent_orders) == 10
    # Then 2
    assert len({r.id for r in result.recent_orders}) == 10
    assert {r.id for r in result.recent_orders} <= all_ids
    # Then 3
    assert result.total_count == 11


# [claude] TOS-HS-04
def test_tos_hs_04__empty_workspace(db, s):
    """TOS-HS-04 — an empty workspace: zeros and empty lists.
    Rules: get_transfer_order_hub_stats R2, R3, R4."""
    order_o9(db, s)
    commit_point(db)

    result = svc.get_transfer_order_hub_stats(db, workspace_id=s.W1.id)

    # Then 1
    assert (
        result.total_count, result.open_count, result.completed_count, result.machine_involved_count
    ) == (0, 0, 0, 0)
    # Then 2
    assert (result.pending_planned_count, result.awaiting_setup_count) == (0, 0)
    # Then 3
    assert result.recent_orders == []
    assert result.pending_planned == []
    assert result.awaiting_setup == []
    assert result.oldest_drafts == []


# [claude] TOS-HS-05
def test_tos_hs_05__capital_all_matches_nothing(db, s):
    """TOS-HS-05 — `"All"` as a location type matches nothing in the stats.
    Rules: get_transfer_order_hub_stats R1; _hub_filter_kwargs R2 (D3)."""
    add_ho(db, s, 1, 1)
    commit_point(db)

    results = [
        svc.get_transfer_order_hub_stats(db, workspace_id=s.W1.id, source_location_type=v) for v in ["all", "All"]
    ]

    # Then 1
    assert [r.total_count for r in results] == [1, 0]


# --------------------------------------------------------------------------- #
# delete_transfer_order
# --------------------------------------------------------------------------- #


# [claude] TOS-D-01
def test_tos_d_01__delete_committed(db, s):
    """TOS-D-01 — a delete is committed: order, lines, approvers and events are gone.
    Rules: delete_transfer_order R1, R4; TC1."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    ev(db, o, "created", 1)
    o_id = o.id
    commit_point(db)
    n_notes = cnt(db, Notification)

    result = DEL(db, s, o_id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    db.expire_all()
    assert db.get(TransferOrder, o_id) is None
    # Then 3
    assert cnt(db, TransferOrderItem, TransferOrderItem.transfer_order_id == o_id) == 0
    # Then 4
    assert cnt(db, TransferOrderApprover, TransferOrderApprover.transfer_order_id == o_id) == 0
    # Then 5
    assert cnt(db, TransferOrderEvent, TransferOrderEvent.transfer_order_id == o_id) == 0
    # Then 6
    assert cnt(db, Notification) == n_notes


# [claude] TOS-D-02
def test_tos_d_02__completed_refused(db, s):
    """TOS-D-02 — a completed order is refused 400 and the session rolled back.
    Rules: delete_transfer_order R2; TC3."""
    o = order(db, s, **completed(s))
    line(db, s, o, 1)
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, o.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot delete a completed transfer order"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-D-03
def test_tos_d_03__other_workspace_404(db, s):
    """TOS-D-03 — another workspace's order gets the 404, rolled back.
    Rules: delete_transfer_order R2; TC3."""
    order(db, s)
    z = order_o9(db, s)
    before = commit_point(db)
    z_before = snap(db, TransferOrder, z.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        DEL(db, s, z.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z.id} not found"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrder, z.id) == z_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-D-04
def test_tos_d_04__failing_commit_keeps_order(db, s):
    """TOS-D-04 — a failing commit leaves the order in place.
    Rules: delete_transfer_order R4; TC4."""
    o = order(db, s)
    line(db, s, o, 1)
    before = commit_point(db)
    o_id = o.id
    o_before = snap(db, TransferOrder, o_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            DEL(db, s, o_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrder, o_id) == o_before
    # Then 4
    assert counts(db) == before


# [claude] TOS-D-05
@pytest.mark.xfail(strict=True, reason=BUG_1194)
def test_tos_d_05__deleter_audit_row_committed(db, s):
    """TOS-D-05 — BUG-1194: the deleter is passed on and the audit row is committed.
    Rules: delete_transfer_order R3 [BUG-1194]."""
    o = order(db, s)
    o_id, num = o.id, o.transfer_number
    commit_point(db)

    # Then 1 (today the call itself raises TypeError: no `user_id` parameter)
    result = svc.delete_transfer_order(db, to_id=o_id, workspace_id=s.W1.id, user_id=s.U2.id)
    assert result is None
    # Then 2
    db.rollback()
    db.expire_all()
    assert db.get(TransferOrder, o_id) is None
    # Then 3
    logs = list(
        db.execute(
            select(WorkspaceAuditLog).where(
                WorkspaceAuditLog.resource_type == "transfer_order", WorkspaceAuditLog.resource_id == o_id
            )
        ).scalars()
    )
    assert len(logs) == 1
    assert logs[0].workspace_id == s.W1.id
    assert logs[0].user_id == s.U2.id
    assert logs[0].action == "transfer_order_deleted"
    # Then 4
    assert logs[0].metadata_json["number"] == num
    assert logs[0].metadata_json["created_by"] == s.U1.id


# [claude] TOS-D-06
@pytest.mark.xfail(strict=True, reason=BUG_1194)
def test_tos_d_06__user_id_required_parameter(db):
    """TOS-D-06 — BUG-1194: `user_id` is a required parameter.
    Rules: delete_transfer_order R3 [BUG-1194]."""
    params = inspect.signature(svc.delete_transfer_order).parameters

    # Then 1
    assert "user_id" in params
    # Then 2
    assert params["user_id"].default is inspect.Parameter.empty


# --------------------------------------------------------------------------- #
# mark_order_complete
# --------------------------------------------------------------------------- #


# [claude] TOS-MC-01
def test_tos_mc_01__completion_committed(db, s):
    """TOS-MC-01 — a completion is committed and the order returned re-read; no notification.
    Rules: mark_order_complete R1, R4; TC1, TC2."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    commit_point(db)

    with pm_patch(return_value=1) as pm:
        result = svc.mark_order_complete(db, to_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == o.id
    assert result.completed_at is not None
    # Then 3
    assert pm.call_count == 1
    # Then 4
    db.rollback()
    row = reread(db, TransferOrder, o.id)
    assert stamp(row.completed_at) == NOW
    assert row.completed_by == s.U2.id
    # Then 5
    assert stamp(reread(db, TransferOrderItem, l1.id).transferred_at) == NOW
    # Then 6
    assert types(db, o.id) == ["transfer_recorded", "inventory_posted", "order_completed"]
    # Then 7
    assert notes(db, o.id) == []


# [claude] TOS-MC-02
def test_tos_mc_02__already_completed_returned_commits(db, s):
    """TOS-MC-02 — an already completed order is returned unchanged and the call still commits.
    Rules: mark_order_complete R2."""
    o = order(db, s, **completed(s))
    line(db, s, o, 1)
    before = commit_point(db)
    o_id, w1_id, u2_id = o.id, s.W1.id, s.U2.id
    o_before = snap(db, TransferOrder, o_id)

    with pm_patch(return_value=1) as pm:
        with spies(db) as (cm, _rb):
            result = svc.mark_order_complete(db, to_id=o_id, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert result.id == o_id
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert pm.call_count == 0
    # Then 4
    assert snap(db, TransferOrder, o_id) == o_before
    # Then 5
    assert counts(db) == before


# [claude] TOS-MC-03
def test_tos_mc_03__unmet_approvals_refused(db, s):
    """TOS-MC-03 — unmet approvals: 400, rolled back.
    Rules: mark_order_complete R3; TC3."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    l1_before = snap(db, TransferOrderItem, l1.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with pm_patch(return_value=1):
            svc.mark_order_complete(db, to_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Required approvals are not met"
    # Then 4
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 5
    assert snap(db, TransferOrderItem, l1.id) == l1_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-MC-04
def test_tos_mc_04__posting_error_rolls_back_everything(db, s):
    """TOS-MC-04 — a stock-posting error rolls back every write of the call, the posting's own included.
    Rules: mark_order_complete R3; TC3."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    o_id, l1_id, w1_id, u2_id = o.id, l1.id, s.W1.id, s.U2.id
    e = err()
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with pm_patch(side_effect=probe_err(db, w1_id, o_id, e)):
            svc.mark_order_complete(db, to_id=o_id, workspace_id=w1_id, user_id=u2_id)
    # Then 2
    assert exc.value is e
    # Then 3
    assert usable(db)
    # Then 4
    row = reread(db, TransferOrder, o_id)
    assert row.completed_at is None
    assert row.completed_by is None
    # Then 5
    assert reread(db, TransferOrderItem, l1_id).transferred_at is None
    # Then 6
    assert cnt(db, TransferOrderEvent, TransferOrderEvent.event_type == "probe") == 0
    # Then 7
    assert counts(db) == before
    # Then 8
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-MC-05
def test_tos_mc_05__no_line_refused(db, s):
    """TOS-MC-05 — no line: 400, rolled back.
    Rules: mark_order_complete R3; TC3."""
    o = order(db, s, required_approvals=0)
    before = commit_point(db)
    o_before = snap(db, TransferOrder, o.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with pm_patch(return_value=0):
            svc.mark_order_complete(db, to_id=o.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Add at least one item before completing"
    # Then 4
    assert snap(db, TransferOrder, o.id) == o_before
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-MC-06
def test_tos_mc_06__other_workspace_404(db, s):
    """TOS-MC-06 — another workspace's order: 404, rolled back.
    Rules: mark_order_complete R3; TC3."""
    z = order_o0(db, s)
    commit_point(db)
    z_before = snap(db, TransferOrder, z.id)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        with pm_patch(return_value=1):
            svc.mark_order_complete(db, to_id=z.id, workspace_id=s.W1.id, user_id=s.U2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z.id} not found"
    # Then 4
    assert snap(db, TransferOrder, z.id) == z_before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-MC-07
def test_tos_mc_07__failing_commit_rolls_back_posting(db, s):
    """TOS-MC-07 — a failing commit rolls back the completion and the posting's writes.
    Rules: mark_order_complete R5; TC4."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    o_id, l1_id, w1_id, u2_id = o.id, l1.id, s.W1.id, s.U2.id

    with pm_patch(side_effect=probe_ok(db, w1_id, o_id)):
        with pytest.raises(RuntimeError) as exc:
            with failing_commit(db) as rb:
                svc.mark_order_complete(db, to_id=o_id, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert reread(db, TransferOrder, o_id).completed_at is None
    # Then 4
    assert reread(db, TransferOrderItem, l1_id).transferred_at is None
    # Then 5
    assert cnt(db, TransferOrderEvent, TransferOrderEvent.event_type == "probe") == 0
    # Then 6
    assert counts(db) == before


# [claude] TOS-MC-08
def test_tos_mc_08__failing_refresh_keeps_completion(db, s):
    """TOS-MC-08 — a failing re-read after the commit leaves the completion saved.
    Rules: mark_order_complete R5; TC5."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    commit_point(db)
    o_id, w1_id, u2_id = o.id, s.W1.id, s.U2.id

    with pm_patch(return_value=1):
        with pytest.raises(RuntimeError) as exc:
            with failing_refresh(db):
                svc.mark_order_complete(db, to_id=o_id, workspace_id=w1_id, user_id=u2_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert stamp(reread(db, TransferOrder, o_id).completed_at) == NOW


# --------------------------------------------------------------------------- #
# add_item
# --------------------------------------------------------------------------- #


# [claude] TOS-AI-01
def test_tos_ai_01__line_committed_reread(db, s):
    """TOS-AI-01 — a line is committed and returned re-read.
    Rules: add_item R3, R6; TC1, TC2."""
    o = order(db, s, **looped(s))
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, TransferOrderItem)
    assert result.line_number == 1
    assert result.item_id == s.I1.id
    rid = result.id
    # Then 3
    db.rollback()
    row = reread(db, TransferOrderItem, rid)
    assert row is not None
    assert row.transfer_order_id == o.id
    assert row.quantity == Decimal("5.00")
    # Then 4
    assert types(db, o.id) == ["item_added"]
    # Then 5
    assert notes(db, o.id) == []


# [claude] TOS-AI-02
def test_tos_ai_02__first_line_pending_creator(db, s):
    """TOS-AI-02 — the first line on a routed order: the pending creator gets "approval pending".
    Rules: add_item R2, R4 [companion of BUG-3142]."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    assert result.line_number == 1
    # Then 2
    db.rollback()
    assert notes(db, o.id) == [("approval_pending", s.U1.id, s.U1.id, "order", o.id, PEND(0, 1))]


# [claude] TOS-AI-03
def test_tos_ai_03__first_line_active_pending_told(db, s):
    """TOS-AI-03 — the first line: every active pending approver is told, an inactive one is not.
    Rules: add_item R4 [companion of BUG-3142]."""
    o = order(db, s, required_approvals=2)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U4, 2)
    apr(db, s, o, s.U3, 3)
    commit_point(db)

    svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U2.id)

    # Then 1
    db.rollback()
    assert notes(db, o.id) == [
        ("approval_pending", s.U1.id, s.U2.id, "order", o.id, PEND(0, 2)),
        ("approval_pending", s.U3.id, s.U2.id, "order", o.id, PEND(0, 2)),
    ]


# [claude] TOS-AI-04
def test_tos_ai_04__second_line_sends_nothing(db, s):
    """TOS-AI-04 — a second line (ready → ready) sends nothing.
    Rules: add_item R4."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.add_item(db, to_id=o.id, item_in=ITEM(s.I2, "3"), workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    assert result.line_number == 2
    # Then 2
    db.rollback()
    assert notes(db, o.id) == []


# [claude] TOS-AI-05
def test_tos_ai_05__invalid_route_sends_nothing(db, s):
    """TOS-AI-05 — a line on an order without a valid route sends nothing.
    Rules: add_item R4."""
    o = order(db, s, **looped(s))
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    db.rollback()
    assert cnt(db, TransferOrderItem, TransferOrderItem.transfer_order_id == o.id) == 1
    # Then 2
    assert notes(db, o.id) == []


# [claude] TOS-AI-06
def test_tos_ai_06__w0_order_404_rolled_back(db, s):
    """TOS-AI-06 — another workspace's order (W0) gets the 404, the session is rolled back.
    Rules: add_item R1; TC3."""
    z = order_o0(db, s)
    order(db, s)
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, to_id=z.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {z.id} not found"
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-07
def test_tos_ai_07__approval_given_refused(db, s):
    """TOS-AI-07 — an approval given: 400, no line, no notification, other pending changes discarded.
    Rules: add_item R5; TC3."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Withdraw all approvals before editing transfer items"
    # Then 4
    assert usable(db)
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-08
def test_tos_ai_08__completed_refused(db, s):
    """TOS-AI-08 — a completed order: 400, rolled back.
    Rules: add_item R5; TC3."""
    o = order(db, s, **completed(s))
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Transfer order is complete"
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-09
def test_tos_ai_09__item_already_on_order(db, s):
    """TOS-AI-09 — the item already on the order: 409, rolled back.
    Rules: add_item R5; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, to_id=o.id, item_in=ITEM(s.I1, "2"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Motor is already on this order"
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-10
def test_tos_ai_10__failing_commit_rolls_back_line(db, s):
    """TOS-AI-10 — a failing commit rolls back the line, its event and its notification.
    Rules: add_item R5, R6; TC4."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id
    item_in = ITEM(s.I1, "5")

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_item(db, to_id=o_id, item_in=item_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert notes(db, o_id) == []
    # Then 4
    assert counts(db) == before


# [claude] TOS-AI-12
def test_tos_ai_12__failing_refresh_keeps_line(db, s):
    """TOS-AI-12 — a failing re-read after the commit leaves the line saved.
    Rules: add_item R6; TC5."""
    o = order(db, s, **looped(s))
    commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id
    item_in = ITEM(s.I1, "5")

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.add_item(db, to_id=o_id, item_in=item_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert cnt(db, TransferOrderItem, TransferOrderItem.transfer_order_id == o_id) == 1


# [claude] TOS-AI-13
def test_tos_ai_13__raise_while_notifying_rolls_back(db, s):
    """TOS-AI-13 — a raise while notifying rolls back the line, its event, the helper's writes and other pending changes.
    Rules: add_item R5; TC3."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id
    item_in = ITEM(s.I1, "5")
    _, x_id = mk_x(db)

    with nu(nprobe(db, w1_id, o_id)) as nh:
        with pytest.raises(RuntimeError) as exc:
            svc.add_item(db, to_id=o_id, item_in=item_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "notify boom"
    # Then 2
    assert nh.call_count == 1
    # Then 3
    assert usable(db)
    # Then 4
    assert cnt(db, TransferOrderItem, TransferOrderItem.transfer_order_id == o_id) == 0
    # Then 5
    assert types(db, o_id) == []
    # Then 6
    assert notes(db, o_id) == []
    # Then 7
    assert counts(db) == before
    # Then 8
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-14
def test_tos_ai_14__missing_id_404_rolled_back(db, s):
    """TOS-AI-14 — an id that does not exist gets the 404, the session is rolled back.
    Rules: add_item R1; TC3."""
    order(db, s)
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_item(db, to_id=MISSING, item_in=ITEM(s.I1, "5"), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Transfer order with ID {MISSING} not found"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AI-11
@pytest.mark.xfail(strict=True, reason=BUG_3142)
def test_tos_ai_11__lock_before_readiness(db, s):
    """TOS-AI-11 — BUG-3142: the order row is locked before the readiness snapshot.
    Rules: add_item R2a [BUG-3142]."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    commit_point(db)
    o_id, w1_id, u1_id = o.id, s.W1.id, s.U1.id
    item_in = ITEM(s.I1, "5")
    db.expunge_all()

    with record_sql(db) as rec:
        result = svc.add_item(db, to_id=o_id, item_in=item_in, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert result.line_number == 1
    # Then 2
    assert locked_before_items(rec.statements)
    assert no_nowait(rec.statements)


# --------------------------------------------------------------------------- #
# update_item
# --------------------------------------------------------------------------- #


# [claude] TOS-UI-01
def test_tos_ui_01__quantity_change_committed(db, s):
    """TOS-UI-01 — a quantity change is committed and the line returned re-read; no notification.
    Rules: update_item R1, R2; TC1, TC2."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.update_item(
        db, item_id=l1.id, item_in=IU(quantity=Decimal("7")), workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == l1.id
    assert result.quantity == Decimal("7.00")
    # Then 3
    db.rollback()
    assert reread(db, TransferOrderItem, l1.id).quantity == Decimal("7.00")
    # Then 4
    assert notes(db, o.id) == []


# [claude] TOS-UI-02
def test_tos_ui_02__approval_given_refused(db, s):
    """TOS-UI-02 — an approval given: 400 on a quantity change, rolled back.
    Rules: update_item R3; TC3."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    l1_before = snap(db, TransferOrderItem, l1.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_item(db, item_id=l1.id, item_in=IU(quantity=Decimal("7")), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Withdraw all approvals before editing transfer items"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrderItem, l1.id) == l1_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-UI-03
def test_tos_ui_03__other_workspace_line_404(db, s):
    """TOS-UI-03 — another workspace's line: 404, rolled back.
    Rules: update_item R3; TC3."""
    z = order_o9(db, s)
    lz = line(db, s, z, 1)
    commit_point(db)
    lz_before = snap(db, TransferOrderItem, lz.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_item(db, item_id=lz.id, item_in=IU(quantity=Decimal("7")), workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Transfer order item not found"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrderItem, lz.id) == lz_before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-UI-04
def test_tos_ui_04__failing_commit_line_unchanged(db, s):
    """TOS-UI-04 — a failing commit leaves the line unchanged.
    Rules: update_item R3; TC4."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    commit_point(db)
    l1_id, w1_id, u1_id = l1.id, s.W1.id, s.U1.id
    l1_before = snap(db, TransferOrderItem, l1_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_item(db, item_id=l1_id, item_in=IU(quantity=Decimal("7")), workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrderItem, l1_id) == l1_before


# [claude] TOS-UI-05
def test_tos_ui_05__failing_refresh_keeps_change(db, s):
    """TOS-UI-05 — a failing re-read after the commit leaves the change saved.
    Rules: update_item R3; TC5."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    commit_point(db)
    l1_id, w1_id, u1_id = l1.id, s.W1.id, s.U1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.update_item(db, item_id=l1_id, item_in=IU(quantity=Decimal("7")), workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, TransferOrderItem, l1_id).quantity == Decimal("7.00")


# --------------------------------------------------------------------------- #
# remove_item
# --------------------------------------------------------------------------- #


# [claude] TOS-RI-01
def test_tos_ri_01__last_line_removed_no_notice(db, s):
    """TOS-RI-01 — the last line is removed and committed; no notification although the order stops being ready.
    Rules: remove_item R1, R2; TC1."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U2, 1)
    l1_id = l1.id
    commit_point(db)

    result = svc.remove_item(db, item_id=l1_id, workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    assert result.id == l1_id
    # Then 2
    db.rollback()
    db.expire_all()
    assert db.get(TransferOrderItem, l1_id) is None
    # Then 3
    assert types(db, o.id) == ["item_removed"]
    # Then 4
    assert notes(db, o.id) == []


# [claude] TOS-RI-02
def test_tos_ri_02__removed_line_returned_without_reread(db, s):
    """TOS-RI-02 — the removed line is returned without a re-read.
    Rules: remove_item R3."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    l1_id = l1.id
    commit_point(db)
    w1_id, u1_id = s.W1.id, s.U1.id

    with patch.object(db, "refresh", wraps=db.refresh) as rf:
        result = svc.remove_item(db, item_id=l1_id, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert rf.call_count == 0
    # Then 2
    assert isinstance(result, TransferOrderItem)
    assert result.id == l1_id


# [claude] TOS-RI-03
def test_tos_ri_03__approval_given_refused(db, s):
    """TOS-RI-03 — an approval given: 400, the line stays, rolled back.
    Rules: remove_item R4; TC3."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)
    l1_before = snap(db, TransferOrderItem, l1.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=l1.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Withdraw all approvals before editing transfer items"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrderItem, l1.id) == l1_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-RI-04
def test_tos_ri_04__unknown_line_404(db, s):
    """TOS-RI-04 — an unknown line: 404, rolled back.
    Rules: remove_item R4; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_item(db, item_id=MISSING, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Transfer order item not found"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-RI-05
def test_tos_ri_05__failing_commit_keeps_line(db, s):
    """TOS-RI-05 — a failing commit keeps the line.
    Rules: remove_item R4; TC4."""
    o = order(db, s)
    l1 = line(db, s, o, 1)
    before = commit_point(db)
    l1_id, w1_id, u1_id = l1.id, s.W1.id, s.U1.id
    l1_before = snap(db, TransferOrderItem, l1_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_item(db, item_id=l1_id, workspace_id=w1_id, user_id=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrderItem, l1_id) == l1_before
    # Then 4
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# Reads: get_items, list_events, list_approvers, approval_summary_for
# --------------------------------------------------------------------------- #


# [claude] TOS-GI-01
def test_tos_gi_01__lines_by_number(db, s):
    """TOS-GI-01 — `get_items` returns the order's lines by number; neither commit nor rollback.
    Rules: get_items R1; TC6."""
    o = order(db, s)
    l2 = line(db, s, o, 2)
    l1 = line(db, s, o, 1, item_id=s.I2.id)
    commit_point(db)
    o_id, l1_id, l2_id, w1_id = o.id, l1.id, l2.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_items(db, to_id=o_id, workspace_id=w1_id)

    # Then 1
    assert [r.id for r in result] == [l1_id, l2_id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db


# [claude] TOS-LE-01
def test_tos_le_01__events_newest_first(db, s):
    """TOS-LE-01 — `list_events` returns (event, profile) pairs newest first; neither commit nor rollback.
    Rules: list_events R1; TC6."""
    o = order(db, s)
    e1 = ev(db, o, "created", 1, performed_by=s.U2.id)
    e2 = ev(db, o, "updated", 2)
    commit_point(db)
    o_id, e1_id, e2_id, u2_id, w1_id = o.id, e1.id, e2.id, s.U2.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_events(db, to_id=o_id, workspace_id=w1_id)

    # Then 1
    assert [e.id for e, _ in result] == [e2_id, e1_id]
    # Then 2
    assert result[0][1] is None
    assert result[1][1].id == u2_id
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db


# [claude] TOS-LA-01
def test_tos_la_01__approvers_with_profile_position(db, s):
    """TOS-LA-01 — `list_approvers` returns (approver, profile, position); neither commit nor rollback.
    Rules: list_approvers R1; TC6."""
    o = order(db, s)
    a2 = apr(db, s, o, s.U2, 2)
    a1 = apr(db, s, o, s.U1, 1)
    commit_point(db)
    o_id, a1_id, a2_id, u1_id, u2_id, w1_id = o.id, a1.id, a2.id, s.U1.id, s.U2.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.list_approvers(db, to_id=o_id, workspace_id=w1_id)

    # Then 1
    assert [(a.id, p.id, pos) for a, p, pos in result] == [
        (a1_id, u1_id, "Store Manager"),
        (a2_id, u2_id, "Factory Head"),
    ]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db


# [claude] TOS-AS-01
def test_tos_as_01__summary_tuple(db, s):
    """TOS-AS-01 — `approval_summary_for` returns (approved, required, met); neither commit nor rollback.
    Rules: approval_summary_for R2; TC6."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1, **APPROVED)
    apr(db, s, o, s.U2, 2)
    commit_point(db)
    o_id, w1_id = o.id, s.W1.id
    x, _ = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.approval_summary_for(db, to_id=o_id, workspace_id=w1_id)

    # Then 1
    assert tuple(result) == (1, 2, False)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db


# [claude] TOS-AS-02
def test_tos_as_02__other_workspace_404_pending_stays(db, s):
    """TOS-AS-02 — another workspace's order: 404; neither commit nor rollback, pending changes stay.
    Rules: approval_summary_for R1; TC6."""
    order(db, s)
    z = order_o9(db, s)
    commit_point(db)
    z_id, w1_id = z.id, s.W1.id
    x, _ = mk_x(db)

    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.approval_summary_for(db, to_id=z_id, workspace_id=w1_id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {z_id} not found"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db


# [claude] TOS-AS-03
def test_tos_as_03__w0_order_404_pending_stays(db, s):
    """TOS-AS-03 — an order of W0 (lower id): 404; neither commit nor rollback, pending changes stay.
    Rules: approval_summary_for R1; TC6; HR-16."""
    z = order_o0(db, s)
    order(db, s)
    commit_point(db)
    z_id, w1_id = z.id, s.W1.id
    x, _ = mk_x(db)

    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.approval_summary_for(db, to_id=z_id, workspace_id=w1_id)

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == f"Transfer order with ID {z_id} not found"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db


# --------------------------------------------------------------------------- #
# add_approver
# --------------------------------------------------------------------------- #


# [claude] TOS-AA-01
def test_tos_aa_01__new_approver_ready_order(db, s):
    """TOS-AA-01 — a new approver on a ready order is committed and gets "assigned · ready" with the new count.
    Rules: add_approver R1, R2a, R2b; TC1, TC2."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U1.id)

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, TransferOrderApprover)
    assert result.user_id == s.U2.id
    assert result.approved is False
    rid = result.id
    # Then 3
    db.rollback()
    row = reread(db, TransferOrderApprover, rid)
    assert row is not None
    assert row.assigned_by == s.U1.id
    # Then 4
    assert types(db, o.id) == ["approver_added"]
    # Then 5
    assert notes(db, o.id) == [
        (
            "approval_assigned", s.U2.id, s.U1.id, "approver", rid,
            "Assigned by Karim Ahmed · ready for your approval · 0 of 2 approval(s) collected",
        )
    ]


# [claude] TOS-AA-02
def test_tos_aa_02__other_pending_told_actor_not(db, s):
    """TOS-AA-02 — ready order: every other pending approver gets "approval pending", the actor does not.
    Rules: add_approver R2b."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U3, 2)
    commit_point(db)

    result = svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U1.id)

    # Then 1
    assert result.user_id == s.U2.id
    rid = result.id
    # Then 2
    db.rollback()
    assert notes(db, o.id) == [
        (
            "approval_assigned", s.U2.id, s.U1.id, "approver", rid,
            "Assigned by Karim Ahmed · ready for your approval · 0 of 3 approval(s) collected",
        ),
        ("approval_pending", s.U3.id, s.U1.id, "order", o.id, PEND(0, 3)),
    ]


# [claude] TOS-AA-03
def test_tos_aa_03__not_ready_assigned_and_confirm(db, s):
    """TOS-AA-03 — not ready: the new approver gets "assigned on TO-<id>" and the creator gets "confirm sections".
    Rules: add_approver R2a, R2c."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U3.id)

    # Then 1
    assert result.user_id == s.U2.id
    rid = result.id
    # Then 2
    db.rollback()
    assert notes(db, o.id) == [
        ("approval_assigned", s.U2.id, s.U3.id, "approver", rid, f"Assigned by Rahim Uddin on TO-{o.id}"),
        ("section_confirm", s.U1.id, s.U3.id, "section", o.id, GAP_ITEM),
    ]


# [claude] TOS-AA-04
def test_tos_aa_04__inactive_member_refused(db, s):
    """TOS-AA-04 — a user who is not an active member: 400, rolled back, no notification.
    Rules: add_approver R3; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_approver(db, to_id=o.id, user_id=s.U4.id, workspace_id=s.W1.id, assigned_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "User is not an active member of this workspace"
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AA-05
def test_tos_aa_05__already_approver_409(db, s):
    """TOS-AA-05 — already an approver: 409, rolled back.
    Rules: add_approver R3; TC3."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U2, 2)
    before = commit_point(db)
    _, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "User is already an approver for this order"
    # Then 4
    assert counts(db) == before
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-AA-06
def test_tos_aa_06__failing_commit_rolls_back_approver(db, s):
    """TOS-AA-06 — a failing commit rolls back the row, its event and the notifications.
    Rules: add_approver R4; TC4."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id, u2_id = o.id, s.W1.id, s.U1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.add_approver(db, to_id=o_id, user_id=u2_id, workspace_id=w1_id, assigned_by=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert notes(db, o_id) == []
    # Then 4
    assert counts(db) == before


# [claude] TOS-AA-07
def test_tos_aa_07__failing_refresh_keeps_approver(db, s):
    """TOS-AA-07 — a failing re-read after the commit leaves the approver saved.
    Rules: add_approver R4; TC5."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    commit_point(db)
    o_id, w1_id, u1_id, u2_id = o.id, s.W1.id, s.U1.id, s.U2.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.add_approver(db, to_id=o_id, user_id=u2_id, workspace_id=w1_id, assigned_by=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert cnt(
        db, TransferOrderApprover,
        TransferOrderApprover.transfer_order_id == o_id, TransferOrderApprover.user_id == u2_id,
    ) == 1


# [claude] TOS-AA-08
@pytest.mark.xfail(strict=True, reason=BUG_2897)
def test_tos_aa_08__completed_refuses_new_approver(db, s):
    """TOS-AA-08 — pass-through BUG-2897: a completed order refuses a new approver, nothing sent.
    Rules: add_approver R1, R3 [BUG-2897]."""
    o = order(db, s, **completed(s))
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Transfer order is complete"
    # Then 4
    assert counts(db) == before


# [claude] TOS-AA-09
def test_tos_aa_09__approved_approver_not_pending(db, s):
    """TOS-AA-09 — ready order: an approver who already approved gets no "approval pending".
    Rules: add_approver R2a, R2b."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    apr(db, s, o, s.U3, 2)
    commit_point(db)

    result = svc.add_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, assigned_by=s.U2.id)

    # Then 1
    assert result.user_id == s.U2.id
    rid = result.id
    # Then 2
    db.rollback()
    assert notes(db, o.id) == [
        (
            "approval_assigned", s.U2.id, s.U2.id, "approver", rid,
            "Assigned by Nadia Islam · ready for your approval · 1 of 3 approval(s) collected",
        ),
        ("approval_pending", s.U3.id, s.U2.id, "order", o.id, PEND(1, 3)),
    ]


# [claude] TOS-AA-10
def test_tos_aa_10__raise_while_notifying_rolls_back(db, s):
    """TOS-AA-10 — a raise while notifying rolls back the approver, its event, the helper's writes and other pending changes.
    Rules: add_approver R3; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, w1_id, u1_id, u2_id = o.id, s.W1.id, s.U1.id, s.U2.id
    _, x_id = mk_x(db)

    with na(nprobe(db, w1_id, o_id)) as nh:
        with pytest.raises(RuntimeError) as exc:
            svc.add_approver(db, to_id=o_id, user_id=u2_id, workspace_id=w1_id, assigned_by=u1_id)

    # Then 1
    assert str(exc.value) == "notify boom"
    # Then 2
    assert nh.call_count == 1
    # Then 3
    assert usable(db)
    # Then 4
    assert cnt(
        db, TransferOrderApprover,
        TransferOrderApprover.transfer_order_id == o_id, TransferOrderApprover.user_id == u2_id,
    ) == 0
    # Then 5
    assert types(db, o_id) == []
    # Then 6
    assert notes(db, o_id) == []
    # Then 7
    assert counts(db) == before
    # Then 8
    db.rollback()
    assert x_gone(db, x_id)


# --------------------------------------------------------------------------- #
# remove_approver
# --------------------------------------------------------------------------- #


# [claude] TOS-RA-01
def test_tos_ra_01__removal_committed_with_performer(db, s):
    """TOS-RA-01 — a removal is committed with the performer; no notice although approvals become met.
    Rules: remove_approver R1, R2; TC1."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1, **APPROVED)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    result = svc.remove_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, performed_by=s.U1.id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert cnt(
        db, TransferOrderApprover,
        TransferOrderApprover.transfer_order_id == o.id, TransferOrderApprover.user_id == s.U2.id,
    ) == 0
    # Then 3
    evs = events_of(db, o.id, "approver_removed")
    assert len(evs) == 1
    assert evs[0].performed_by == s.U1.id
    # Then 4
    assert notes(db, o.id) == []


# [claude] TOS-RA-02
def test_tos_ra_02__no_performer(db, s):
    """TOS-RA-02 — without `performed_by` the event has no performer.
    Rules: remove_approver R1."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    apr(db, s, o, s.U2, 2)
    commit_point(db)

    svc.remove_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id)

    # Then 1
    db.rollback()
    evs = events_of(db, o.id, "approver_removed")
    assert len(evs) == 1
    assert evs[0].performed_by is None


# [claude] TOS-RA-03
def test_tos_ra_03__no_such_approver_404(db, s):
    """TOS-RA-03 — no such approver: 404, rolled back.
    Rules: remove_approver R3; TC3."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_approver(db, to_id=o.id, user_id=s.U3.id, workspace_id=s.W1.id, performed_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Approver not found"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-RA-04
def test_tos_ra_04__failing_commit_keeps_approver(db, s):
    """TOS-RA-04 — a failing commit keeps the approver.
    Rules: remove_approver R3; TC4."""
    o = order(db, s)
    apr(db, s, o, s.U1, 1)
    a2 = apr(db, s, o, s.U2, 2)
    before = commit_point(db)
    o_id, a2_id, w1_id, u1_id, u2_id = o.id, a2.id, s.W1.id, s.U1.id, s.U2.id
    a2_before = snap(db, TransferOrderApprover, a2_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.remove_approver(db, to_id=o_id, user_id=u2_id, workspace_id=w1_id, performed_by=u1_id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrderApprover, a2_id) == a2_before
    # Then 4
    assert counts(db) == before


# [claude] TOS-RA-05
@pytest.mark.xfail(strict=True, reason=BUG_2897)
def test_tos_ra_05__completed_refuses_removal(db, s):
    """TOS-RA-05 — pass-through BUG-2897: a completed order refuses the removal.
    Rules: remove_approver R3 [BUG-2897]."""
    o = order(db, s, **completed(s))
    apr(db, s, o, s.U1, 1, **APPROVED)
    a2 = apr(db, s, o, s.U2, 2)
    before = commit_point(db)
    a2_before = snap(db, TransferOrderApprover, a2.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.remove_approver(db, to_id=o.id, user_id=s.U2.id, workspace_id=s.W1.id, performed_by=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Transfer order is complete"
    # Then 4
    assert snap(db, TransferOrderApprover, a2.id) == a2_before
    # Then 5
    assert counts(db) == before


# --------------------------------------------------------------------------- #
# set_approval
# --------------------------------------------------------------------------- #


# [claude] TOS-SA-01
def test_tos_sa_01__approving_committed(db, s):
    """TOS-SA-01 — approving is committed and the row returned re-read; no notice when approvals become met.
    Rules: set_approval R1, R2; TC1, TC2."""
    o = order(db, s)
    line(db, s, o, 1)
    a1 = apr(db, s, o, s.U1, 1)
    commit_point(db)

    result = svc.set_approval(db, to_id=o.id, user_id=s.U1.id, workspace_id=s.W1.id, approved=True)

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == a1.id
    assert result.approved is True
    # Then 3
    db.rollback()
    row = reread(db, TransferOrderApprover, a1.id)
    assert row.approved is True
    assert stamp(row.approved_at) == NOW
    # Then 4
    assert types(db, o.id) == ["approved"]
    # Then 5
    assert notes(db, o.id) == []


# [claude] TOS-SA-02
def test_tos_sa_02__withdrawing_committed(db, s):
    """TOS-SA-02 — withdrawing is committed; no notice.
    Rules: set_approval R1, R2."""
    o = order(db, s)
    line(db, s, o, 1)
    a1 = apr(db, s, o, s.U1, 1, **APPROVED)
    commit_point(db)

    result = svc.set_approval(db, to_id=o.id, user_id=s.U1.id, workspace_id=s.W1.id, approved=False)

    # Then 1
    assert result.approved is False
    # Then 2
    db.rollback()
    row = reread(db, TransferOrderApprover, a1.id)
    assert row.approved is False
    assert row.approved_at is None
    # Then 3
    assert notes(db, o.id) == []


# [claude] TOS-SA-03
def test_tos_sa_03__not_an_approver_403(db, s):
    """TOS-SA-03 — not an approver: 403, rolled back.
    Rules: set_approval R3; TC3."""
    o = order(db, s)
    line(db, s, o, 1)
    apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_approval(db, to_id=o.id, user_id=s.U3.id, workspace_id=s.W1.id, approved=True)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "You are not an assigned approver for this order"
    # Then 4
    assert x not in db
    # Then 5
    assert counts(db) == before
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-SA-04
def test_tos_sa_04__no_line_refused(db, s):
    """TOS-SA-04 — approving an order with no line: 400, rolled back.
    Rules: set_approval R3; TC3."""
    o = order(db, s)
    a1 = apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    a1_before = snap(db, TransferOrderApprover, a1.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.set_approval(db, to_id=o.id, user_id=s.U1.id, workspace_id=s.W1.id, approved=True)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Add at least one item before approving"
    # Then 4
    assert x not in db
    # Then 5
    assert snap(db, TransferOrderApprover, a1.id) == a1_before
    # Then 6
    assert counts(db) == before
    # Then 7
    db.rollback()
    assert x_gone(db, x_id)


# [claude] TOS-SA-05
def test_tos_sa_05__failing_commit_keeps_unset(db, s):
    """TOS-SA-05 — a failing commit keeps the approval unset.
    Rules: set_approval R3; TC4."""
    o = order(db, s)
    line(db, s, o, 1)
    a1 = apr(db, s, o, s.U1, 1)
    before = commit_point(db)
    o_id, a1_id, w1_id, u1_id = o.id, a1.id, s.W1.id, s.U1.id
    a1_before = snap(db, TransferOrderApprover, a1_id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.set_approval(db, to_id=o_id, user_id=u1_id, workspace_id=w1_id, approved=True)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, TransferOrderApprover, a1_id) == a1_before
    # Then 4
    assert counts(db) == before


# [claude] TOS-SA-06
def test_tos_sa_06__failing_refresh_keeps_approval(db, s):
    """TOS-SA-06 — a failing re-read after the commit leaves the approval saved.
    Rules: set_approval R3; TC5."""
    o = order(db, s)
    line(db, s, o, 1)
    a1 = apr(db, s, o, s.U1, 1)
    commit_point(db)
    o_id, a1_id, w1_id, u1_id = o.id, a1.id, s.W1.id, s.U1.id

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.set_approval(db, to_id=o_id, user_id=u1_id, workspace_id=w1_id, approved=True)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, TransferOrderApprover, a1_id).approved is True
